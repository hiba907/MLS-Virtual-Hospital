"""
═══════════════════════════════════════════════════════════════════════════
  MLS Virtual Hospital — Hybrid MCQ System (5 Q's per case)
  ─────────────────────────────────────────────────────────────────────────
  Active recall assessment after every case. Combines:
    • Pre-curated MCQ bank (admin-approved, free, fast)
    • AI-generated MCQs (Gemini, when bank empty for this case)
    • Quality control loop (students flag, admin approves/rejects)

  HOW IT WORKS
  ────────────
  Student finishes a case → submits diagnosis → MCQ session offered
   ↓
  System checks: does this case have ≥3 APPROVED MCQs?
   ├─ YES → serve approved bank (fast, free, vetted)
   └─ NO  → generate 5 MCQs live with AI → store as DRAFT for admin review
   ↓
  Student answers all 5 → instant feedback per question
   ↓
  Score recorded, XP awarded, wrong answers flagged for review
   ↓
  Admin (Dr. Hiba) reviews drafts in Faculty Portal:
   • Edit question text, choices, correct answer, explanation
   • Approve → moves to permanent bank, students see it next time
   • Reject → discarded
   • Students can also flag bad MCQs → admin reviews flags

  AUTHOR: Hiba Hamdar — Academy of Medical Learning Skills
  COPYRIGHT (c) 2026 — All Rights Reserved
═══════════════════════════════════════════════════════════════════════════

INTEGRATION
-----------
1. Save as `mcq_system.py` next to app.py
2. Add to top of app.py:
     try:
         from mcq_system import (
             render_mcq_session_page,
             render_mcq_admin_panel,
             render_post_diagnosis_mcq_button,
             generate_mcqs_for_case,
             get_mcq_count_for_case,
         )
         MCQ_SYSTEM_OK = True
     except Exception as e:
         MCQ_SYSTEM_OK = False
3. Run the SQL in MCQ_SCHEMA at the bottom of this file
4. Add sidebar entry routing to render_mcq_session_page()
5. Add Faculty Portal entry routing to render_mcq_admin_panel()
6. Hook render_post_diagnosis_mcq_button() into the diagnosis page
═══════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
import uuid
import json
import re
import requests


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
MCQS_PER_SESSION    = 5     # how many MCQs per case session
MIN_BANK_FOR_REUSE  = 3     # if bank has ≥ this, serve from bank (no AI call)
DRAFT_TARGET        = 5     # how many MCQs the AI should generate per request

MCQ_CATEGORIES = [
    "diagnosis",
    "differential",
    "investigation",
    "management",
    "pathophysiology",
    "complication",
    "anatomy",
    "general",
]


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def _safe_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def _supabase_url() -> str:
    return _safe_secret("SUPABASE_URL", "").rstrip("/")


def _supabase_key() -> str:
    return _safe_secret("SUPABASE_KEY", "")


def _sb_headers() -> dict:
    key = _supabase_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _sb_available() -> bool:
    return bool(_supabase_url() and _supabase_key())


def _get_user_id() -> str:
    auth = st.session_state.get("auth_user", {}) or {}
    return str(auth.get("id") or auth.get("email") or
               st.session_state.get("user_id", "anon"))


def _get_user_name() -> str:
    auth = st.session_state.get("auth_user", {}) or {}
    return auth.get("name") or auth.get("email") or "Student"


def _is_admin() -> bool:
    auth = st.session_state.get("auth_user", {}) or {}
    role = (auth.get("role") or "").lower()
    if role in ("admin", "faculty"):
        return True
    admin_email = _safe_secret("ADMIN_EMAIL", "hamdarhiba95@gmail.com").strip().lower()
    user_email = (auth.get("email") or "").strip().lower()
    return bool(user_email and admin_email and user_email == admin_email)


def _case_id_of(case: Optional[Dict[str, Any]]) -> str:
    """Stable identifier for a case from session state."""
    if not case:
        return "no_case"
    return str(case.get("Case_ID") or case.get("id") or
               case.get("row_num") or case.get("Title") or "no_case")[:80]


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════════
def get_mcq_count_for_case(case_id: str, status: str = "approved") -> int:
    """How many MCQs of given status exist for this case."""
    if not _sb_available():
        return 0
    url = f"{_supabase_url()}/rest/v1/case_mcqs"
    params = {
        "case_id": f"eq.{case_id}",
        "status":  f"eq.{status}",
        "select":  "mcq_id",
    }
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return len(r.json() or [])
    except Exception as e:
        print(f"[mcq_system] count error: {e}")
    return 0


def list_approved_mcqs(case_id: str, limit: int = MCQS_PER_SESSION
                        ) -> List[Dict[str, Any]]:
    """Return approved MCQs for this case (random order)."""
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/case_mcqs"
    params = {
        "case_id": f"eq.{case_id}",
        "status":  "eq.approved",
        "select":  "*",
    }
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            data = r.json() or []
            # Shuffle in Python (Supabase doesn't have RANDOM in URL filter)
            import random
            random.shuffle(data)
            return data[:limit]
    except Exception as e:
        print(f"[mcq_system] list_approved error: {e}")
    return []


def list_draft_mcqs(case_id: Optional[str] = None
                     ) -> List[Dict[str, Any]]:
    """Return all draft MCQs awaiting admin review."""
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/case_mcqs"
    params = {
        "status": "eq.draft",
        "select": "*",
        "order":  "created_at.desc",
    }
    if case_id:
        params["case_id"] = f"eq.{case_id}"
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return r.json() or []
    except Exception:
        pass
    return []


def list_flagged_mcqs() -> List[Dict[str, Any]]:
    """Return all approved MCQs that have been flagged by students."""
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/case_mcqs"
    params = {
        "flag_count": "gt.0",
        "select":     "*",
        "order":      "flag_count.desc",
    }
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return r.json() or []
    except Exception:
        pass
    return []


def insert_mcq(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Insert a single MCQ row."""
    if not _sb_available():
        return None
    url = f"{_supabase_url()}/rest/v1/case_mcqs"
    try:
        r = requests.post(url, headers=_sb_headers(), json=record, timeout=8)
        if r.status_code in (200, 201):
            return record
    except Exception as e:
        print(f"[mcq_system] insert error: {e}")
    return None


def update_mcq(mcq_id: str, updates: Dict[str, Any]) -> bool:
    """Update an MCQ row."""
    if not _sb_available():
        return False
    url = f"{_supabase_url()}/rest/v1/case_mcqs"
    try:
        r = requests.patch(url, headers=_sb_headers(),
                            params={"mcq_id": f"eq.{mcq_id}"},
                            json=updates, timeout=8)
        return r.status_code in (200, 204)
    except Exception:
        return False


def delete_mcq(mcq_id: str) -> bool:
    if not _sb_available():
        return False
    url = f"{_supabase_url()}/rest/v1/case_mcqs"
    try:
        r = requests.delete(url, headers=_sb_headers(),
                             params={"mcq_id": f"eq.{mcq_id}"},
                             timeout=8)
        return r.status_code in (200, 204)
    except Exception:
        return False


def flag_mcq(mcq_id: str, reason: str = "") -> bool:
    """Increment flag_count and append reason to flag_reasons."""
    if not _sb_available():
        return False
    # Fetch current row to update incrementally
    url = f"{_supabase_url()}/rest/v1/case_mcqs"
    try:
        r = requests.get(url, headers=_sb_headers(),
                         params={"mcq_id": f"eq.{mcq_id}",
                                 "select": "flag_count,flag_reasons"},
                         timeout=8)
        if r.status_code != 200 or not r.json():
            return False
        row = r.json()[0]
        cur = row.get("flag_count", 0) or 0
        cur_reasons = row.get("flag_reasons", "") or ""
        reporter = _get_user_name()
        new_reasons = cur_reasons + (
            f"\n[{datetime.now(timezone.utc).date().isoformat()}] "
            f"{reporter}: {reason[:200]}"
        )
        return update_mcq(mcq_id, {
            "flag_count":   cur + 1,
            "flag_reasons": new_reasons.strip()[:5000],
        })
    except Exception:
        return False


def record_attempt(mcq_id: str, case_id: str, was_correct: bool) -> None:
    """Record a student's MCQ attempt (for analytics)."""
    if not _sb_available():
        return
    url = f"{_supabase_url()}/rest/v1/mcq_attempts"
    record = {
        "attempt_id":  "att_" + uuid.uuid4().hex[:10],
        "user_id":     _get_user_id(),
        "user_name":   _get_user_name(),
        "mcq_id":      mcq_id,
        "case_id":     case_id,
        "was_correct": was_correct,
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }
    try:
        requests.post(url, headers=_sb_headers(), json=record, timeout=4)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# AI GENERATION
# ═══════════════════════════════════════════════════════════════════════════
def _build_mcq_prompt(case: Dict[str, Any], n: int = DRAFT_TARGET) -> str:
    """Build the prompt for the AI to generate MCQs about a specific case."""
    parts = [
        f"You are a medical education question writer. Generate exactly {n} "
        f"high-quality multiple-choice questions (MCQs) for medical students "
        f"based on the case below.",
        "",
        "─── CASE DETAILS ───",
        f"Title: {case.get('Title', '')}",
        f"Patient: {case.get('Age_Sex', '')}",
        f"Chief complaint: {case.get('Chief_Complaint', '')}",
        f"HPI: {case.get('HPI', '')}",
        f"Vitals: {case.get('Vitals', '')}",
        f"Physical findings: {case.get('Physical_Findings', '')}",
        f"Labs: {case.get('Labs', '')}",
        f"Imaging: {case.get('Imaging', '')}",
        f"FINAL DIAGNOSIS: {case.get('Final_Diagnosis', '')}",
        f"Treatment: {case.get('Treatment', '')}",
        "",
        "─── REQUIREMENTS ───",
        "• Cover diverse aspects: diagnosis, differential, investigations, "
        "management, pathophysiology, and complications. Vary across the 5.",
        "• Each question must have EXACTLY 4 choices labeled A, B, C, D.",
        "• Only ONE choice is correct. The other 3 must be plausible distractors.",
        "• Difficulty: medium (suitable for advanced medical students or junior residents).",
        "• Each explanation must be 1-3 sentences and teach why the correct answer is correct, "
        "and ideally why the most tempting wrong answer is wrong.",
        "• No 'all of the above' or 'none of the above'. No trick questions.",
        "• Don't reveal the diagnosis in the question stem if asking 'what is the diagnosis'.",
        "",
        "─── OUTPUT FORMAT ───",
        "Reply with ONLY a JSON array. No markdown, no preamble, no explanation outside JSON.",
        "Each item must have these exact keys:",
        '{"question": "...", "choice_a": "...", "choice_b": "...", '
        '"choice_c": "...", "choice_d": "...", "correct_answer": "A", '
        '"explanation": "...", "category": "diagnosis"}',
        "",
        "Categories must be one of: diagnosis, differential, investigation, "
        "management, pathophysiology, complication, anatomy, general.",
        "",
        "Now generate the JSON array of 5 MCQs:",
    ]
    return "\n".join(parts)


def _parse_ai_json(text: str) -> List[Dict[str, Any]]:
    """Safely parse a JSON array from AI output (handles markdown wrappers)."""
    if not text:
        return []
    t = text.strip()
    # Strip common markdown fences
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    # Find the first [ and last ] (greedy isolation of JSON array)
    s = t.find("[")
    e = t.rfind("]")
    if s == -1 or e == -1 or e <= s:
        return []
    candidate = t[s:e+1]
    try:
        data = json.loads(candidate)
        if isinstance(data, list):
            return data
    except Exception as ex:
        print(f"[mcq_system] JSON parse error: {ex}")
        # Try to fix common issues — trailing commas
        candidate2 = re.sub(r",(\s*[\]}])", r"\1", candidate)
        try:
            data = json.loads(candidate2)
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _validate_mcq(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Sanity-check an AI-generated MCQ. Returns clean record or None if invalid."""
    required = ["question", "choice_a", "choice_b", "choice_c", "choice_d",
                "correct_answer", "explanation"]
    if not all(k in item and item[k] for k in required):
        return None
    correct = str(item.get("correct_answer", "")).strip().upper()[:1]
    if correct not in ("A", "B", "C", "D"):
        return None
    cat = str(item.get("category", "general")).strip().lower()
    if cat not in MCQ_CATEGORIES:
        cat = "general"
    return {
        "question":       str(item["question"]).strip()[:1500],
        "choice_a":       str(item["choice_a"]).strip()[:500],
        "choice_b":       str(item["choice_b"]).strip()[:500],
        "choice_c":       str(item["choice_c"]).strip()[:500],
        "choice_d":       str(item["choice_d"]).strip()[:500],
        "correct_answer": correct,
        "explanation":    str(item["explanation"]).strip()[:2000],
        "category":       cat,
    }


def generate_mcqs_for_case(case: Dict[str, Any],
                            n: int = DRAFT_TARGET,
                            save_as_draft: bool = True
                            ) -> List[Dict[str, Any]]:
    """
    Use AI to generate MCQs for a case. Returns list of validated MCQ records.
    If save_as_draft=True, also writes them to Supabase as drafts.

    Falls back gracefully:
      • If AI call fails or returns garbage → returns []
      • If Supabase write fails → still returns the in-memory MCQs

    The function tries to use the host app's call_ai if available; if not,
    it falls back to a direct Gemini call using the same secrets.
    """
    case_id = _case_id_of(case)
    prompt = _build_mcq_prompt(case, n=n)

    # Try to use host app's call_ai (cleanest — uses same fallback chain)
    ai_text = ""
    try:
        import sys
        if "__main__" in sys.modules:
            host = sys.modules.get("__main__")
            if host and hasattr(host, "call_ai"):
                ai_text = host.call_ai(
                    "You are a medical education MCQ generator. Reply with valid JSON only.",
                    [{"role": "user", "content": prompt}],
                    max_tokens=2500,
                )
    except Exception as e:
        print(f"[mcq_system] host call_ai unavailable: {e}")

    # Fall back to a direct Gemini call if host call_ai didn't work
    if not ai_text or ai_text.startswith("!ERR"):
        ai_text = _direct_gemini_call(prompt)

    if not ai_text or ai_text.startswith("!ERR"):
        print(f"[mcq_system] AI generation failed: {ai_text[:200]}")
        return []

    raw_items = _parse_ai_json(ai_text)
    if not raw_items:
        print(f"[mcq_system] No valid JSON parsed from: {ai_text[:300]}")
        return []

    valid = []
    for item in raw_items:
        clean = _validate_mcq(item)
        if not clean:
            continue
        record = {
            "mcq_id":         "mcq_" + uuid.uuid4().hex[:12],
            "case_id":        case_id,
            "case_title":     str(case.get("Title", ""))[:200],
            "status":         "draft",
            "generated_by":   "ai",
            "generator_model": "gemini",
            "flag_count":     0,
            "flag_reasons":   "",
            "created_at":     datetime.now(timezone.utc).isoformat(),
            **clean,
        }
        valid.append(record)

    # Save drafts to Supabase
    if save_as_draft:
        for rec in valid:
            insert_mcq(rec)

    return valid


def _direct_gemini_call(prompt: str) -> str:
    """Fallback direct Gemini call if host's call_ai isn't reachable."""
    try:
        # Try to find any Gemini key from secrets
        keys = []
        for i in range(1, 21):
            k = _safe_secret(f"GEMINI_API_KEY_{i}", "")
            if k:
                keys.append(k)
        for k in keys[:5]:  # try at most 5 keys
            try:
                url = (
                    "https://generativelanguage.googleapis.com/v1beta/"
                    f"models/gemini-2.0-flash-lite:generateContent?key={k}"
                )
                payload = {
                    "contents": [{"role": "user",
                                   "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 2500,
                    },
                }
                r = requests.post(url, json=payload, timeout=60)
                if r.status_code == 200:
                    data = r.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                continue
        return ""
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════
# UI: STUDENT-FACING — POST-DIAGNOSIS HOOK
# ═══════════════════════════════════════════════════════════════════════════
def render_post_diagnosis_mcq_button() -> None:
    """Drop-in button shown on the diagnosis page after submission.
    Auto-prompts the student to test their knowledge."""
    case = st.session_state.get("selected_case")
    if not case:
        return
    case_id = _case_id_of(case)

    st.markdown("---")
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1e3a8a,#0e7490);color:white;
                border-radius:14px;padding:1.5rem 1.7rem;margin:1rem 0;
                box-shadow:0 4px 14px rgba(0,0,0,.1);">
      <div style="font-size:1.3rem;font-weight:800;margin-bottom:.4rem;">
        🧠 Test your knowledge — {MCQS_PER_SESSION} quick questions
      </div>
      <div style="font-size:.92rem;opacity:.92;line-height:1.5;">
        Active recall right after a case is the most efficient way to make
        learning stick. {MCQS_PER_SESSION} short MCQs about diagnosis,
        management, and pathophysiology of <b>{case.get('Title', 'this case')}</b>.
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("📝 Start MCQ Session", type="primary",
                 use_container_width=True, key="start_mcq_session"):
        # Clear any previous session state
        for k in list(st.session_state.keys()):
            if isinstance(k, str) and k.startswith("_mcq_"):
                del st.session_state[k]
        st.session_state["_mcq_active_case_id"] = case_id
        st.session_state.page = "mcq_session"
        st.rerun()


def render_mcq_session_page() -> None:
    """The main quiz interface — runs through 5 MCQs one by one."""
    case = st.session_state.get("selected_case")
    if not case:
        st.warning("No case loaded. Pick a case from the Case Library first.")
        if st.button("← Back to Library"):
            st.session_state.page = "library"
            st.rerun()
        return

    case_id = _case_id_of(case)

    # ── Initialize the session state if first visit ─────────────────────
    if "_mcq_questions" not in st.session_state or \
       st.session_state.get("_mcq_active_case_id") != case_id:
        with st.spinner("Loading MCQs..."):
            mcqs = _load_or_generate_mcqs(case)
        if not mcqs:
            st.error(
                "Could not load or generate MCQs for this case right now. "
                "This usually means the AI service is temporarily busy. "
                "Please try again in a minute."
            )
            if st.button("← Back to Diagnosis"):
                st.session_state.page = "diagnosis"
                st.rerun()
            return
        st.session_state["_mcq_questions"]    = mcqs
        st.session_state["_mcq_active_case_id"] = case_id
        st.session_state["_mcq_current_idx"]  = 0
        st.session_state["_mcq_answers"]      = {}   # idx -> chosen letter
        st.session_state["_mcq_revealed"]     = {}   # idx -> True/False
        st.session_state["_mcq_correct_count"] = 0

    mcqs = st.session_state["_mcq_questions"]
    idx  = st.session_state.get("_mcq_current_idx", 0)
    total = len(mcqs)

    # ── Header ──────────────────────────────────────────────────────────
    st.markdown(
        '<div class="section-header">📝 MCQ Session</div>',
        unsafe_allow_html=True
    )
    st.markdown(f"""
    <div style="background:white;border:1.5px solid #e2e8f0;border-radius:12px;
                padding:.9rem 1.2rem;margin-bottom:.8rem;
                display:flex;justify-content:space-between;align-items:center;">
      <div style="font-weight:700;color:#0f172a;">
        Case: <span style="color:#0e7490;">{case.get('Title','')[:80]}</span>
      </div>
      <div style="background:#f0f9ff;color:#0369a1;padding:.3rem .8rem;
                  border-radius:999px;font-size:.78rem;font-weight:700;">
        Question {min(idx+1, total)} of {total}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Progress bar
    progress = idx / max(1, total)
    st.markdown(f"""
    <div style="background:#e5e7eb;border-radius:6px;height:6px;
                overflow:hidden;margin-bottom:1.2rem;">
      <div style="background:linear-gradient(90deg,#0e7490,#06b6d4);
                  width:{progress*100}%;height:100%;
                  transition:width .3s ease;"></div>
    </div>
    """, unsafe_allow_html=True)

    # ── End of session ──────────────────────────────────────────────────
    if idx >= total:
        _render_session_results(mcqs)
        return

    # ── Render the current MCQ ─────────────────────────────────────────
    mcq = mcqs[idx]
    revealed = st.session_state["_mcq_revealed"].get(idx, False)
    chosen   = st.session_state["_mcq_answers"].get(idx)

    # Question card
    st.markdown(f"""
    <div style="background:white;border:1.5px solid #e2e8f0;border-radius:14px;
                padding:1.4rem 1.6rem;margin-bottom:1rem;
                box-shadow:0 2px 6px rgba(0,0,0,.04);">
      <div style="font-size:.72rem;color:#9ca3af;letter-spacing:.05em;
                  text-transform:uppercase;font-weight:700;margin-bottom:.3rem;">
        {mcq.get('category', 'general')}
      </div>
      <div style="font-size:1.05rem;color:#0f172a;line-height:1.55;font-weight:500;">
        {mcq.get('question', '')}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Choices
    letters = ["A", "B", "C", "D"]
    for letter in letters:
        choice_key = f"choice_{letter.lower()}"
        choice_text = mcq.get(choice_key, "")
        if not choice_text:
            continue

        # Determine button styling based on state
        is_chosen = (chosen == letter)
        is_correct_answer = (mcq.get("correct_answer") == letter)

        if revealed:
            # Show correct/wrong colors
            if is_correct_answer:
                bg, border, fg = "#dcfce7", "#16a34a", "#14532d"
                marker = "✓"
            elif is_chosen and not is_correct_answer:
                bg, border, fg = "#fee2e2", "#dc2626", "#7f1d1d"
                marker = "✗"
            else:
                bg, border, fg = "#f9fafb", "#e5e7eb", "#374151"
                marker = ""
        else:
            bg = "#f0f9ff" if is_chosen else "#ffffff"
            border = "#0ea5e9" if is_chosen else "#e2e8f0"
            fg = "#0c4a6e" if is_chosen else "#0f172a"
            marker = "●" if is_chosen else "○"

        # Render the choice
        if not revealed:
            if st.button(
                f"{marker}  **{letter}.** {choice_text}",
                key=f"choice_btn_{idx}_{letter}",
                use_container_width=True,
            ):
                st.session_state["_mcq_answers"][idx] = letter
                st.rerun()
        else:
            # Static display when revealed
            st.markdown(f"""
            <div style="background:{bg};border:2px solid {border};
                        border-radius:10px;padding:.7rem 1rem;margin-bottom:.4rem;
                        color:{fg};font-size:.92rem;line-height:1.4;">
              <b>{marker} {letter}.</b> {choice_text}
            </div>
            """, unsafe_allow_html=True)

    # ── Action buttons ─────────────────────────────────────────────────
    if not revealed:
        ca, cb = st.columns([1, 1])
        with ca:
            disabled = chosen is None
            if st.button(
                "✓ Submit Answer",
                key=f"submit_{idx}",
                type="primary",
                use_container_width=True,
                disabled=disabled,
            ):
                st.session_state["_mcq_revealed"][idx] = True
                # Check correctness
                was_correct = (chosen == mcq.get("correct_answer"))
                if was_correct:
                    st.session_state["_mcq_correct_count"] += 1
                # Record attempt
                record_attempt(mcq.get("mcq_id", ""), case_id, was_correct)
                st.rerun()
        with cb:
            if st.button("Skip question", key=f"skip_{idx}",
                          use_container_width=True):
                st.session_state["_mcq_revealed"][idx] = True
                st.session_state["_mcq_answers"][idx] = "_SKIPPED"
                st.rerun()
    else:
        # Show explanation
        is_correct = (chosen == mcq.get("correct_answer"))
        skipped = (chosen == "_SKIPPED")
        if skipped:
            box_color = "#64748b"
            box_bg    = "#f1f5f9"
            label     = "Skipped"
        elif is_correct:
            box_color = "#16a34a"
            box_bg    = "#f0fdf4"
            label     = "✓ Correct!"
        else:
            box_color = "#dc2626"
            box_bg    = "#fef2f2"
            label     = "✗ Incorrect"

        correct_letter = mcq.get("correct_answer", "")
        st.markdown(f"""
        <div style="background:{box_bg};border-left:4px solid {box_color};
                    border:1px solid {box_color}33;border-radius:10px;
                    padding:1rem 1.2rem;margin:1rem 0;">
          <div style="font-weight:800;color:{box_color};font-size:.95rem;
                      margin-bottom:.4rem;">
            {label} · Correct answer: {correct_letter}
          </div>
          <div style="color:#374151;line-height:1.55;font-size:.9rem;">
            {mcq.get('explanation', '')}
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Flag this MCQ option (for quality control)
        with st.expander("⚠️ Report this question (mistake / unclear)", expanded=False):
            reason = st.text_input(
                "What's wrong with this question?",
                placeholder="e.g., 'B is also a correct answer' or 'Question is ambiguous'",
                key=f"flag_reason_{idx}",
            )
            if st.button("Submit report", key=f"flag_submit_{idx}"):
                if reason.strip():
                    if flag_mcq(mcq.get("mcq_id", ""), reason.strip()):
                        st.success("Thank you — admin will review this.")
                    else:
                        st.error("Could not submit report.")
                else:
                    st.warning("Please describe the issue.")

        # Next button
        ca, cb = st.columns([1, 1])
        with ca:
            if st.button("Next question →",
                          key=f"next_{idx}",
                          type="primary",
                          use_container_width=True):
                st.session_state["_mcq_current_idx"] = idx + 1
                st.rerun()
        with cb:
            if st.button("End session early",
                          key=f"end_{idx}",
                          use_container_width=True):
                st.session_state["_mcq_current_idx"] = total
                st.rerun()


def _load_or_generate_mcqs(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Bank-first strategy:
      1. If approved bank has ≥ MIN_BANK_FOR_REUSE for this case → use bank
      2. Otherwise → generate new MCQs with AI and save as drafts
         (also serve them to this student immediately, so no wait)
    """
    case_id = _case_id_of(case)
    approved_count = get_mcq_count_for_case(case_id, status="approved")
    if approved_count >= MIN_BANK_FOR_REUSE:
        return list_approved_mcqs(case_id, limit=MCQS_PER_SESSION)
    # Generate new
    return generate_mcqs_for_case(case, n=MCQS_PER_SESSION, save_as_draft=True)


def _render_session_results(mcqs: List[Dict[str, Any]]) -> None:
    """End-of-session score screen with XP award."""
    correct = st.session_state.get("_mcq_correct_count", 0)
    total = len(mcqs)
    pct = round(correct / max(1, total) * 100)

    if pct >= 80:
        emoji, label, color = "🏆", "Excellent!", "#16a34a"
    elif pct >= 60:
        emoji, label, color = "👏", "Good effort", "#0ea5e9"
    elif pct >= 40:
        emoji, label, color = "📚", "Keep studying", "#f59e0b"
    else:
        emoji, label, color = "💪", "Review and try again", "#dc2626"

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{color}11,{color}22);
                border:2px solid {color};border-radius:14px;
                padding:2rem;text-align:center;margin:1rem 0;">
      <div style="font-size:3rem;">{emoji}</div>
      <div style="font-size:1.6rem;font-weight:800;color:{color};
                  margin-top:.4rem;">{label}</div>
      <div style="font-size:1.1rem;color:#0f172a;margin-top:.4rem;">
        You answered <b>{correct}</b> out of <b>{total}</b> correctly
        (<b>{pct}%</b>)
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Award XP
    if not st.session_state.get("_mcq_xp_awarded"):
        try:
            from tier1_features import award_xp
            xp = total * 5 + correct * 5  # 5 base + 5 per correct
            award_xp("mcq_session", amount=xp, toast=False)
            st.session_state["_mcq_xp_awarded"] = True
            st.success(f"🌟 You earned {xp} XP")
        except Exception:
            pass

    # Per-question recap
    st.markdown("### 📋 Your answers")
    for i, mcq in enumerate(mcqs):
        chosen   = st.session_state["_mcq_answers"].get(i)
        is_correct = (chosen == mcq.get("correct_answer"))
        skipped  = (chosen == "_SKIPPED")
        status_emoji = "⏭️" if skipped else ("✓" if is_correct else "✗")
        status_color = "#64748b" if skipped else ("#16a34a" if is_correct else "#dc2626")
        with st.expander(
            f"{status_emoji} Q{i+1}: {mcq.get('question', '')[:80]}...",
            expanded=False
        ):
            st.markdown(f"**Your answer:** {chosen if not skipped else '(skipped)'}")
            st.markdown(f"**Correct:** {mcq.get('correct_answer')}")
            st.markdown(f"**Explanation:** {mcq.get('explanation', '')}")

    # End buttons
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🔄 Retry MCQs", use_container_width=True):
            for k in list(st.session_state.keys()):
                if isinstance(k, str) and k.startswith("_mcq_"):
                    del st.session_state[k]
            st.rerun()
    with c2:
        if st.button("📚 New Case", use_container_width=True, type="primary"):
            st.session_state.selected_case = None
            for k in list(st.session_state.keys()):
                if isinstance(k, str) and k.startswith("_mcq_"):
                    del st.session_state[k]
            st.session_state.page = "library"
            st.rerun()
    with c3:
        if st.button("🏠 Home", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# UI: ADMIN PANEL
# ═══════════════════════════════════════════════════════════════════════════
def render_mcq_admin_panel() -> None:
    """Admin (Dr. Hiba) panel — review draft MCQs, manage approved bank,
    handle student flags."""
    if not _is_admin():
        st.error("This page is for admins only.")
        return

    st.markdown(
        '<div class="section-header">📝 MCQ Bank Management</div>',
        unsafe_allow_html=True
    )

    drafts  = list_draft_mcqs()
    flagged = list_flagged_mcqs()

    tabs = st.tabs([
        f"⏳ Pending Review ({len(drafts)})",
        f"🚩 Flagged by Students ({len(flagged)})",
        "✓ Approved Bank",
        "📊 Stats",
    ])

    with tabs[0]:
        _admin_drafts_tab(drafts)
    with tabs[1]:
        _admin_flagged_tab(flagged)
    with tabs[2]:
        _admin_approved_tab()
    with tabs[3]:
        _admin_stats_tab()


def _admin_drafts_tab(drafts: List[Dict[str, Any]]) -> None:
    if not drafts:
        st.info(
            "✓ No drafts awaiting review. Drafts appear here automatically "
            "when AI generates new MCQs for cases that don't have an approved bank yet."
        )
        return

    st.markdown(f"**{len(drafts)} draft MCQ{'s' if len(drafts)!=1 else ''} awaiting review**")
    st.caption(
        "Review each MCQ. Edit if needed, then click Approve to add it to "
        "the student-facing bank, or Reject to discard."
    )

    for mcq in drafts:
        mcq_id = mcq.get("mcq_id")
        with st.expander(
            f"📋 [{mcq.get('category', '?')}] {mcq.get('question', '')[:80]}...",
            expanded=False
        ):
            st.caption(f"Case: {mcq.get('case_title', '—')} · "
                        f"Generated: {mcq.get('created_at', '')[:10]}")

            # Editable form
            with st.form(f"edit_mcq_{mcq_id}"):
                q  = st.text_area("Question:", value=mcq.get("question", ""),
                                  height=80, key=f"q_{mcq_id}")
                ca = st.text_input("Choice A:", value=mcq.get("choice_a", ""),
                                    key=f"a_{mcq_id}")
                cb = st.text_input("Choice B:", value=mcq.get("choice_b", ""),
                                    key=f"b_{mcq_id}")
                cc = st.text_input("Choice C:", value=mcq.get("choice_c", ""),
                                    key=f"c_{mcq_id}")
                cd = st.text_input("Choice D:", value=mcq.get("choice_d", ""),
                                    key=f"d_{mcq_id}")
                col1, col2 = st.columns([1, 2])
                with col1:
                    correct = st.selectbox(
                        "Correct answer:",
                        ["A", "B", "C", "D"],
                        index=["A", "B", "C", "D"].index(
                            mcq.get("correct_answer", "A")),
                        key=f"corr_{mcq_id}",
                    )
                with col2:
                    cat = st.selectbox(
                        "Category:",
                        MCQ_CATEGORIES,
                        index=MCQ_CATEGORIES.index(
                            mcq.get("category", "general"))
                            if mcq.get("category") in MCQ_CATEGORIES else 0,
                        key=f"cat_{mcq_id}",
                    )
                expl = st.text_area("Explanation:", value=mcq.get("explanation", ""),
                                     height=100, key=f"e_{mcq_id}")

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    approve = st.form_submit_button("✓ Approve",
                                                     type="primary",
                                                     use_container_width=True)
                with col_b:
                    save = st.form_submit_button("💾 Save edits",
                                                  use_container_width=True)
                with col_c:
                    reject = st.form_submit_button("✗ Reject",
                                                    use_container_width=True)

                if approve or save or reject:
                    updates = {
                        "question":       q.strip(),
                        "choice_a":       ca.strip(),
                        "choice_b":       cb.strip(),
                        "choice_c":       cc.strip(),
                        "choice_d":       cd.strip(),
                        "correct_answer": correct,
                        "category":       cat,
                        "explanation":    expl.strip(),
                    }
                    if approve:
                        updates["status"]      = "approved"
                        updates["approved_at"] = datetime.now(timezone.utc).isoformat()
                        updates["approved_by"] = _get_user_name()
                        if update_mcq(mcq_id, updates):
                            st.success("✓ Approved — students will see this now.")
                            st.rerun()
                    elif reject:
                        if update_mcq(mcq_id, {"status": "rejected"}):
                            st.warning("✗ Rejected.")
                            st.rerun()
                    elif save:
                        if update_mcq(mcq_id, updates):
                            st.success("💾 Saved.")
                            st.rerun()


def _admin_flagged_tab(flagged: List[Dict[str, Any]]) -> None:
    if not flagged:
        st.info("✓ No flagged MCQs. Students haven't reported any issues.")
        return

    st.markdown(
        f"**{len(flagged)} flagged MCQ{'s' if len(flagged)!=1 else ''}** "
        "(students reported issues)"
    )

    for mcq in flagged:
        mcq_id = mcq.get("mcq_id")
        with st.expander(
            f"🚩 ({mcq.get('flag_count', 0)} flags) "
            f"{mcq.get('question', '')[:80]}...",
            expanded=True
        ):
            st.markdown(f"**Question:** {mcq.get('question', '')}")
            st.markdown(f"**Correct answer:** {mcq.get('correct_answer')} — "
                        f"{mcq.get('choice_' + mcq.get('correct_answer', 'a').lower(), '')}")
            st.markdown(f"**Explanation:** {mcq.get('explanation', '')}")
            st.markdown("**Reports from students:**")
            st.code(mcq.get("flag_reasons", ""), language=None)

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("✗ Remove this MCQ",
                              key=f"flagrm_{mcq_id}",
                              type="primary",
                              use_container_width=True):
                    if delete_mcq(mcq_id):
                        st.warning("Removed from bank.")
                        st.rerun()
            with c2:
                if st.button("📝 Edit & re-approve",
                              key=f"flagedit_{mcq_id}",
                              use_container_width=True):
                    if update_mcq(mcq_id, {"status": "draft", "flag_count": 0,
                                            "flag_reasons": ""}):
                        st.info("Moved back to drafts for editing.")
                        st.rerun()
            with c3:
                if st.button("Clear flags (false alarms)",
                              key=f"flagclr_{mcq_id}",
                              use_container_width=True):
                    if update_mcq(mcq_id, {"flag_count": 0,
                                            "flag_reasons": ""}):
                        st.info("Flags cleared.")
                        st.rerun()


def _admin_approved_tab() -> None:
    if not _sb_available():
        st.error("Database not configured.")
        return

    url = f"{_supabase_url()}/rest/v1/case_mcqs"
    params = {"status": "eq.approved", "select": "*",
              "order": "case_id.asc,created_at.desc"}
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        approved = r.json() or []
    except Exception:
        approved = []

    if not approved:
        st.info("No approved MCQs yet. Approve drafts in the Pending Review tab.")
        return

    # Group by case
    by_case = {}
    for m in approved:
        cid = m.get("case_id", "?")
        ctitle = m.get("case_title", cid)
        by_case.setdefault((cid, ctitle), []).append(m)

    st.markdown(f"**{len(approved)} approved MCQs across {len(by_case)} cases**")

    for (cid, ctitle), mcqs in sorted(by_case.items(), key=lambda x: x[0][1]):
        with st.expander(
            f"📚 {ctitle[:80]} ({len(mcqs)} MCQs)",
            expanded=False
        ):
            for mcq in mcqs:
                st.markdown(f"**Q:** {mcq.get('question', '')}")
                st.markdown(
                    f"A) {mcq.get('choice_a', '')}<br>"
                    f"B) {mcq.get('choice_b', '')}<br>"
                    f"C) {mcq.get('choice_c', '')}<br>"
                    f"D) {mcq.get('choice_d', '')}",
                    unsafe_allow_html=True
                )
                st.caption(f"Correct: **{mcq.get('correct_answer')}** · "
                            f"{mcq.get('category', 'general')}")
                if st.button("Remove from bank",
                              key=f"rem_appr_{mcq.get('mcq_id')}"):
                    if delete_mcq(mcq.get("mcq_id", "")):
                        st.warning("Removed.")
                        st.rerun()
                st.markdown("---")


def _admin_stats_tab() -> None:
    if not _sb_available():
        st.error("Database not configured.")
        return

    # Fetch counts for each status
    stats = {}
    for status in ["draft", "approved", "rejected"]:
        url = f"{_supabase_url()}/rest/v1/case_mcqs"
        try:
            r = requests.get(url, headers=_sb_headers(),
                             params={"status": f"eq.{status}",
                                     "select": "mcq_id"},
                             timeout=8)
            stats[status] = len(r.json() or []) if r.status_code == 200 else 0
        except Exception:
            stats[status] = 0

    # Attempts count
    try:
        url = f"{_supabase_url()}/rest/v1/mcq_attempts"
        r = requests.get(url, headers=_sb_headers(),
                         params={"select": "attempt_id"}, timeout=8)
        attempts = len(r.json() or []) if r.status_code == 200 else 0
    except Exception:
        attempts = 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("📝 Drafts", stats["draft"])
    with c2:
        st.metric("✓ Approved", stats["approved"])
    with c3:
        st.metric("✗ Rejected", stats["rejected"])
    with c4:
        st.metric("🎯 Total attempts", attempts)

    st.markdown("---")
    st.markdown("**Curation progress:**")
    total = sum(stats.values())
    if total > 0:
        appr_pct = round(stats["approved"] / total * 100)
        rej_pct  = round(stats["rejected"] / total * 100)
        drf_pct  = 100 - appr_pct - rej_pct
        st.markdown(f"""
        <div style="display:flex;height:24px;border-radius:6px;overflow:hidden;
                    background:#f1f5f9;font-size:.78rem;color:white;font-weight:700;">
          <div style="background:#16a34a;width:{appr_pct}%;
                      display:flex;align-items:center;justify-content:center;">
            {appr_pct}% approved
          </div>
          <div style="background:#f59e0b;width:{drf_pct}%;
                      display:flex;align-items:center;justify-content:center;">
            {drf_pct}% drafts
          </div>
          <div style="background:#dc2626;width:{rej_pct}%;
                      display:flex;align-items:center;justify-content:center;">
            {rej_pct}% rejected
          </div>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# REQUIRED SUPABASE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════
MCQ_SCHEMA = """
-- ─────────────────────────────────────────────────────────────────────
-- MCQ Hybrid System — schema
-- Run this in Supabase SQL Editor
-- ─────────────────────────────────────────────────────────────────────

-- 1. The MCQ bank itself
create table if not exists public.case_mcqs (
    mcq_id          text primary key,
    case_id         text not null,
    case_title      text default '',
    question        text not null,
    choice_a        text not null,
    choice_b        text not null,
    choice_c        text not null,
    choice_d        text not null,
    correct_answer  text not null,           -- 'A' / 'B' / 'C' / 'D'
    explanation     text not null,
    category        text default 'general',
    status          text default 'draft',    -- draft / approved / rejected
    generated_by    text default 'ai',       -- ai / manual / edited
    generator_model text default '',
    flag_count      integer default 0,
    flag_reasons    text default '',
    approved_at     timestamptz,
    approved_by     text default '',
    created_at      timestamptz default now()
);

create index if not exists idx_mcqs_case_status on public.case_mcqs(case_id, status);
create index if not exists idx_mcqs_status on public.case_mcqs(status, created_at);
create index if not exists idx_mcqs_flags on public.case_mcqs(flag_count) where flag_count > 0;

alter table public.case_mcqs enable row level security;
drop policy if exists "Allow all case_mcqs" on public.case_mcqs;
create policy "Allow all case_mcqs" on public.case_mcqs
    for all using (true) with check (true);

-- 2. Per-attempt tracking (for analytics)
create table if not exists public.mcq_attempts (
    attempt_id    text primary key,
    user_id       text not null,
    user_name     text default '',
    mcq_id        text not null,
    case_id       text not null,
    was_correct   boolean default false,
    created_at    timestamptz default now()
);

create index if not exists idx_attempts_user on public.mcq_attempts(user_id, created_at);
create index if not exists idx_attempts_mcq  on public.mcq_attempts(mcq_id);

alter table public.mcq_attempts enable row level security;
drop policy if exists "Allow all mcq_attempts" on public.mcq_attempts;
create policy "Allow all mcq_attempts" on public.mcq_attempts
    for all using (true) with check (true);
"""


if __name__ == "__main__":
    print("MLS Virtual Hospital — Hybrid MCQ System")
    print("=" * 60)
    print(MCQ_SCHEMA)
