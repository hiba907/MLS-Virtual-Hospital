"""
═══════════════════════════════════════════════════════════════════════════
  MLS Virtual Hospital — AI Case Creator (Phase 1 of Knowledge Expansion)
  ─────────────────────────────────────────────────────────────────────────
  Faculty-only tool to grow the case library quickly using AI assistance.

  THREE MODES:
  ────────────
  1. ✨ Create from scratch — type a 1-2 sentence description, AI generates
     a complete case (HPI, vitals, exam, labs, imaging, diagnosis, etc.)

  2. 🔧 Expand existing — pick from the 319 xlsx cases, AI fills in empty
     fields (learning objectives, teaching points, differential, reasoning)
     WITHOUT changing what you've already written.

  3. 📦 Bulk enrichment — process multiple existing cases in batches, each
     becomes a draft for your review.

  WORKFLOW:
  ─────────
  AI generates → saved as DRAFT in Supabase → admin reviews & approves →
  goes live for students.

  The Case Library in the app reads from BOTH the xlsx (original 319) AND
  the new `cases_extended` table (approved AI cases). Combined seamlessly.

  AUTHOR: Hiba Hamdar — Academy of Medical Learning Skills
  COPYRIGHT (c) 2026 — All Rights Reserved
═══════════════════════════════════════════════════════════════════════════

INTEGRATION
-----------
1. Save as `case_creator.py` next to app.py
2. Add to top of app.py (after MCQ import):
       try:
           from case_creator import (
               render_case_creator_panel,
               load_approved_cases_from_db,
               get_pending_cases_count,
           )
           CASE_CREATOR_OK = True
       except Exception as e:
           CASE_CREATOR_OK = False
3. Run the SQL in CASES_EXTENDED_SCHEMA at the bottom of this file
4. Add Faculty Portal sidebar entry → render_case_creator_panel()
5. (Optional) Merge approved DB cases into the main cases_df

═══════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import streamlit as st
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import uuid
import json
import re
import requests
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════
SYSTEMS = [
    "cardio", "respiratory", "abdomen", "neuro", "musculoskeletal",
    "endocrine", "renal", "hematology", "infectious", "psychiatry",
    "dermatology", "ent", "ophthalmology", "obgyn", "pediatrics",
    "emergency", "geriatrics", "general",
]

DIFFICULTIES = ["basic", "intermediate", "advanced"]


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


def _is_admin() -> bool:
    auth = st.session_state.get("auth_user", {}) or {}
    role = (auth.get("role") or "").lower()
    if role in ("admin", "faculty"):
        return True
    admin_email = _safe_secret("ADMIN_EMAIL", "hamdarhiba95@gmail.com").strip().lower()
    user_email  = (auth.get("email") or "").strip().lower()
    return bool(user_email and admin_email and user_email == admin_email)


def _admin_name() -> str:
    auth = st.session_state.get("auth_user", {}) or {}
    return auth.get("name") or auth.get("email") or "admin"


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════════
def list_drafts() -> List[Dict[str, Any]]:
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/cases_extended"
    params = {"status": "eq.draft", "select": "*", "order": "created_at.desc"}
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return r.json() or []
    except Exception as e:
        print(f"[case_creator] list_drafts error: {e}")
    return []


def list_approved() -> List[Dict[str, Any]]:
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/cases_extended"
    params = {"status": "eq.approved", "select": "*", "order": "approved_at.desc"}
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return r.json() or []
    except Exception:
        pass
    return []


def get_pending_cases_count() -> int:
    return len(list_drafts())


def get_case_by_id(case_id: str) -> Optional[Dict[str, Any]]:
    if not _sb_available():
        return None
    url = f"{_supabase_url()}/rest/v1/cases_extended"
    params = {"case_id": f"eq.{case_id}", "select": "*"}
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200 and r.json():
            return r.json()[0]
    except Exception:
        pass
    return None


def insert_case(rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _sb_available():
        return None
    url = f"{_supabase_url()}/rest/v1/cases_extended"
    try:
        r = requests.post(url, headers=_sb_headers(), json=rec, timeout=10)
        if r.status_code in (200, 201):
            return rec
    except Exception as e:
        print(f"[case_creator] insert error: {e}")
    return None


def update_case(case_id: str, updates: Dict[str, Any]) -> bool:
    if not _sb_available():
        return False
    url = f"{_supabase_url()}/rest/v1/cases_extended"
    try:
        r = requests.patch(url, headers=_sb_headers(),
                            params={"case_id": f"eq.{case_id}"},
                            json=updates, timeout=8)
        return r.status_code in (200, 204)
    except Exception:
        return False


def delete_case(case_id: str) -> bool:
    if not _sb_available():
        return False
    url = f"{_supabase_url()}/rest/v1/cases_extended"
    try:
        r = requests.delete(url, headers=_sb_headers(),
                             params={"case_id": f"eq.{case_id}"},
                             timeout=8)
        return r.status_code in (200, 204)
    except Exception:
        return False


def load_approved_cases_from_db() -> pd.DataFrame:
    """Return all approved AI-generated cases as a DataFrame matching the
    same columns as load_cases() in app.py, so they can be concatenated."""
    if not _sb_available():
        return pd.DataFrame()
    cases = list_approved()
    if not cases:
        return pd.DataFrame()

    rows = []
    for c in cases:
        rows.append({
            "Case_ID":           c.get("case_id", ""),
            "Title":             c.get("title", ""),
            "System":            (c.get("system") or "general").lower().strip(),
            "Difficulty":        (c.get("difficulty") or "basic").lower().strip(),
            "Age_Sex":           c.get("age_sex", ""),
            "Occupation":        c.get("occupation", ""),
            "Chief_Complaint":   c.get("chief_complaint", ""),
            "Duration":          c.get("duration", ""),
            "Context":           c.get("context", ""),
            "HPI":               c.get("hpi", ""),
            "PMH":               c.get("pmh", ""),
            "Family_Hx":         c.get("family_hx", ""),
            "Social_Hx":         c.get("social_hx", ""),
            "Medications":       c.get("medications", ""),
            "Vitals":            c.get("vitals", ""),
            "Appearance":        c.get("appearance", ""),
            "Physical_Findings": c.get("physical_findings", ""),
            "Labs":              c.get("labs", ""),
            "Urine":             c.get("urine", ""),
            "Imaging_Tests":     c.get("imaging_tests", ""),
            "XRay_Report":       c.get("xray_report", ""),
            "CT_Report":         c.get("ct_report", ""),
            "Final_Diagnosis":   c.get("final_diagnosis", ""),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Match the same filter/normalization that load_cases() does
    df = df[df["Chief_Complaint"].notna() & df["Final_Diagnosis"].notna()]
    df = df[df["Chief_Complaint"].astype(str).str.strip() != ""]
    return df.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════
# AI HELPERS — call_ai delegate (or direct fallback)
# ═══════════════════════════════════════════════════════════════════════════
def _call_ai(prompt: str, max_tokens: int = 2500) -> str:
    """Use host app's call_ai if available, else direct Gemini fallback."""
    try:
        import sys
        host = sys.modules.get("__main__")
        if host and hasattr(host, "call_ai"):
            text = host.call_ai(
                "You are a clinical medical education content generator. "
                "Reply only with the requested format.",
                [{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            if text and not text.startswith("!ERR"):
                return text
    except Exception:
        pass
    return _direct_gemini_call(prompt, max_tokens)


def _direct_gemini_call(prompt: str, max_tokens: int = 2500) -> str:
    """Direct Gemini fallback if host's call_ai isn't reachable."""
    keys = []
    for i in range(1, 21):
        k = _safe_secret(f"GEMINI_API_KEY_{i}", "")
        if k:
            keys.append(k)
    for k in keys[:5]:
        try:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.0-flash-lite:generateContent?key={k}"
            )
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.6,
                    "maxOutputTokens": max_tokens,
                },
            }
            r = requests.post(url, json=payload, timeout=60)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            continue
    return ""


def _parse_ai_json(text: str) -> Optional[Dict[str, Any]]:
    """Safely parse a JSON object from AI output."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    s = t.find("{")
    e = t.rfind("}")
    if s == -1 or e == -1 or e <= s:
        return None
    try:
        return json.loads(t[s:e+1])
    except Exception:
        candidate = re.sub(r",(\s*[\]}])", r"\1", t[s:e+1])
        try:
            return json.loads(candidate)
        except Exception:
            return None


# ═══════════════════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════════════════
def _prompt_create_from_scratch(brief: str, system: str, difficulty: str) -> str:
    return f"""
Generate a complete clinical teaching case for medical students based on this brief description:

BRIEF: {brief}
SYSTEM: {system}
DIFFICULTY: {difficulty}

Generate a realistic, clinically accurate case. Output ONLY a JSON object with these exact keys:

{{
  "title": "short descriptive case title (5-8 words)",
  "age_sex": "e.g. '58 year, male' or '34 yrs, female'",
  "occupation": "occupation if relevant, else blank",
  "chief_complaint": "1-line chief complaint",
  "duration": "duration and onset, e.g. '3 days, gradual' or 'sudden, 2 hours ago'",
  "context": "1-2 sentences of context/setting of presentation",
  "hpi": "2-4 sentences of history of present illness with relevant details",
  "pmh": "past medical history (or 'negative' if none)",
  "family_hx": "family history (or 'negative' if none)",
  "social_hx": "social history (smoking, alcohol, etc, or 'negative')",
  "medications": "current medications (or 'none')",
  "vitals": "BP, HR, Temp, RR, O2 Sat in shorthand e.g. 'BP 140/90, HR 110, T 38.5, RR 22, O2 92%'",
  "appearance": "1-line general appearance",
  "physical_findings": "2-3 sentences of relevant physical findings (system-focused)",
  "labs": "key lab results in shorthand e.g. 'WBC 14, neutro 80, Hb 12, plt 250, Cr 1.1, CRP 75'",
  "urine": "urine analysis if relevant, else 'not done' or 'normal'",
  "imaging_tests": "summary of imaging done and key findings, 1-2 sentences",
  "xray_report": "X-ray report if applicable, else blank",
  "ct_report": "CT report if applicable, else blank",
  "final_diagnosis": "the final diagnosis (2-5 words)",
  "learning_objectives": "3-5 bullet learning objectives separated by newlines",
  "differential": "3-5 differential diagnoses separated by newlines",
  "diagnostic_reasoning": "2-4 sentences explaining how clinical findings led to diagnosis",
  "teaching_points": "3-5 key teaching points separated by newlines",
  "treatment": "first-line treatment in 2-3 sentences",
  "tags": "comma-separated relevant keywords/tags"
}}

REQUIREMENTS:
- Clinically realistic: vitals and labs must match the diagnosis
- Difficulty-appropriate: basic = clear classic presentation; advanced = atypical/complex
- Use real clinical shorthand (BP, HR, WBC, etc.)
- Do NOT include patient-identifiable information
- Output ONLY the JSON, no preamble, no markdown
"""


def _prompt_expand_existing(case: Dict[str, Any]) -> str:
    """Expand an existing brief case — fill in missing fields without
    changing existing content."""
    parts = []
    for label, key in [
        ("Title", "title"), ("System", "system"), ("Age/Sex", "age_sex"),
        ("Occupation", "occupation"), ("Chief complaint", "chief_complaint"),
        ("Duration", "duration"), ("Context", "context"), ("HPI", "hpi"),
        ("PMH", "pmh"), ("Family Hx", "family_hx"), ("Social Hx", "social_hx"),
        ("Medications", "medications"), ("Vitals", "vitals"),
        ("Appearance", "appearance"), ("Physical findings", "physical_findings"),
        ("Labs", "labs"), ("Urine", "urine"),
        ("Imaging", "imaging_tests"), ("X-Ray", "xray_report"),
        ("CT", "ct_report"), ("Final diagnosis", "final_diagnosis"),
    ]:
        val = case.get(key, "")
        if val and str(val).strip().lower() not in ("nan", "none", ""):
            parts.append(f"  {label}: {val}")

    existing = "\n".join(parts)

    return f"""
You are expanding an existing brief clinical case into a complete teaching case.
The original brief data is below. Your task is to FILL IN the missing teaching
fields (learning objectives, differential, reasoning, teaching points, treatment, tags)
based on the diagnosis and findings — but DO NOT modify the existing clinical data.

EXISTING CASE DATA:
{existing}

Output ONLY a JSON object with these new teaching fields:

{{
  "learning_objectives": "3-5 bullet learning objectives, one per line",
  "differential": "3-5 differential diagnoses to consider, one per line",
  "diagnostic_reasoning": "2-4 sentences explaining how the findings support the diagnosis",
  "teaching_points": "3-5 key teaching points students should remember, one per line",
  "treatment": "first-line treatment in 2-3 sentences",
  "tags": "comma-separated keywords (e.g., 'pneumonia, sepsis, antibiotics, CXR')"
}}

REQUIREMENTS:
- Stay consistent with the diagnosis and findings already given
- Use educational language appropriate for medical students
- Be specific to THIS case, not generic
- Output ONLY the JSON, no preamble, no markdown
"""


# ═══════════════════════════════════════════════════════════════════════════
# AI GENERATION
# ═══════════════════════════════════════════════════════════════════════════
def generate_case_from_scratch(brief: str, system: str = "general",
                                difficulty: str = "intermediate"
                                ) -> Optional[Dict[str, Any]]:
    prompt = _prompt_create_from_scratch(brief, system, difficulty)
    text = _call_ai(prompt, max_tokens=3000)
    if not text:
        return None
    data = _parse_ai_json(text)
    if not data:
        return None
    # Always keep source fields the admin entered
    data["system"] = system
    data["difficulty"] = difficulty
    return data


def generate_expansion(existing_case: Dict[str, Any]
                        ) -> Optional[Dict[str, Any]]:
    """Generate teaching-field expansion for an existing case.
    Returns dict with only the new fields (learning_obj, differential, etc).
    """
    prompt = _prompt_expand_existing(existing_case)
    text = _call_ai(prompt, max_tokens=2000)
    if not text:
        return None
    return _parse_ai_json(text)


# ═══════════════════════════════════════════════════════════════════════════
# UI: MAIN PANEL
# ═══════════════════════════════════════════════════════════════════════════
def render_case_creator_panel() -> None:
    if not _is_admin():
        st.error("This page is for admins only.")
        return

    st.markdown(
        '<div class="section-header">🏥 AI Case Creator</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div style="background:linear-gradient(135deg,#0a2540,#0e7490);color:white;
                border-radius:14px;padding:1.4rem 1.6rem;margin-bottom:1rem;">
      <div style="font-size:1.3rem;font-weight:800;margin-bottom:.4rem;">
        Grow your case library with AI assistance
      </div>
      <div style="font-size:.92rem;opacity:.92;line-height:1.5;">
        Three modes: <b>Create from scratch</b> (type one line → AI generates
        a full case), <b>Expand existing</b> (fill in missing teaching fields
        on your existing 319 cases), or <b>Bulk enrichment</b> (process
        multiple cases at once). All AI output saves as drafts you review.
      </div>
    </div>
    """, unsafe_allow_html=True)

    drafts = list_drafts()
    approved = list_approved()

    tabs = st.tabs([
        "✨ Create from Scratch",
        "🔧 Expand Existing",
        "📦 Bulk Enrichment",
        f"⏳ Pending Drafts ({len(drafts)})",
        f"✓ Approved Bank ({len(approved)})",
    ])

    with tabs[0]:
        _tab_create_from_scratch()
    with tabs[1]:
        _tab_expand_existing()
    with tabs[2]:
        _tab_bulk_enrichment()
    with tabs[3]:
        _tab_pending_drafts(drafts)
    with tabs[4]:
        _tab_approved_bank(approved)


# ───────────────────────────────────────────────────────────────────────────
# TAB 1: Create from scratch
# ───────────────────────────────────────────────────────────────────────────
def _tab_create_from_scratch() -> None:
    st.markdown("**Type a 1-2 sentence description. AI will generate a full case.**")
    st.caption(
        "Example: *'65 year old male, smoker, presenting with crushing "
        "chest pain radiating to left arm and diaphoresis for 1 hour'*"
    )

    with st.form("create_from_scratch"):
        brief = st.text_area(
            "Brief case description:",
            placeholder=(
                "e.g., 50yo female with chronic productive cough, weight loss, "
                "and night sweats for 3 months. Recent immigrant from a "
                "high-prevalence area."
            ),
            height=100,
        )
        col1, col2 = st.columns(2)
        with col1:
            system = st.selectbox("System:", SYSTEMS, key="cfs_system")
        with col2:
            difficulty = st.selectbox("Difficulty:", DIFFICULTIES, index=1, key="cfs_diff")

        submitted = st.form_submit_button(
            "🤖 Generate full case with AI",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not brief or len(brief) < 20:
            st.warning("Please write a more detailed brief (at least 20 characters).")
            return

        with st.spinner("AI is generating a complete case... (10-30 seconds)"):
            data = generate_case_from_scratch(brief.strip(), system, difficulty)

        if not data:
            st.error(
                "Could not generate case — AI service may be temporarily busy. "
                "Try again in a minute."
            )
            return

        # Save as draft
        case_id = "AICASE-" + uuid.uuid4().hex[:10].upper()
        record = {
            "case_id":           case_id,
            "source_brief":      brief.strip()[:500],
            "source_mode":       "create_from_scratch",
            "status":            "draft",
            "created_by":        _admin_name(),
            "created_at":        datetime.now(timezone.utc).isoformat(),
            **{k: str(v)[:5000] for k, v in data.items() if v is not None},
        }
        result = insert_case(record)
        if result:
            st.success(f"✅ Case generated and saved as draft! Case ID: `{case_id}`")
            st.info("Go to the **⏳ Pending Drafts** tab to review and approve it.")
            with st.expander("Preview generated case", expanded=True):
                _render_case_preview(record)
        else:
            st.error(
                "Generated the case, but couldn't save to database. "
                "Check Supabase connection."
            )


# ───────────────────────────────────────────────────────────────────────────
# TAB 2: Expand existing
# ───────────────────────────────────────────────────────────────────────────
def _tab_expand_existing() -> None:
    st.markdown(
        "**Pick a case from your existing library. AI will add teaching fields "
        "(learning objectives, differential, reasoning, teaching points, treatment, tags) "
        "WITHOUT changing the clinical data you already wrote.**"
    )

    # Try to access cases_df from the host app
    cases_df = _get_host_cases_df()
    if cases_df is None or cases_df.empty:
        st.warning(
            "Could not access your existing case library. Make sure the app is "
            "loaded and the xlsx file is in place."
        )
        return

    st.caption(f"Library has **{len(cases_df)}** cases available.")

    # Search & pick
    search = st.text_input(
        "Search by title or diagnosis:",
        placeholder="e.g. pneumonia, fracture, MI",
        key="expand_search",
    )

    filtered = cases_df.copy()
    if search and search.strip():
        s = search.strip().lower()
        filtered = cases_df[
            cases_df["Title"].astype(str).str.lower().str.contains(s, na=False)
            | cases_df["Final_Diagnosis"].astype(str).str.lower().str.contains(s, na=False)
        ]

    if filtered.empty:
        st.info("No matching cases. Try a different search term.")
        return

    # Build picker options (limit to first 50 to avoid UI lag)
    options = []
    for idx, row in filtered.head(50).iterrows():
        case_id = str(row.get("Case_ID", "")).strip()
        title = str(row.get("Title", "")).strip()
        diag = str(row.get("Final_Diagnosis", "")).strip()
        label = f"[{case_id}] {title} → {diag}"
        options.append((label, idx))

    if not options:
        st.info("No cases to expand.")
        return

    selected_label = st.selectbox(
        f"Pick a case to expand (showing first 50 of {len(filtered)} matches):",
        [o[0] for o in options],
        key="expand_pick",
    )
    selected_idx = next(o[1] for o in options if o[0] == selected_label)
    selected_row = filtered.loc[selected_idx]

    # Preview existing case
    with st.expander("Current case data", expanded=False):
        for label, key in [
            ("Title", "Title"), ("System", "System"),
            ("Age/Sex", "Age_Sex"), ("Chief complaint", "Chief_Complaint"),
            ("HPI", "HPI"), ("Vitals", "Vitals"),
            ("Physical findings", "Physical_Findings"),
            ("Labs", "Labs"), ("Imaging", "Imaging_Tests"),
            ("Final diagnosis", "Final_Diagnosis"),
        ]:
            val = selected_row.get(key, "")
            if val and str(val).strip().lower() not in ("nan", "none", ""):
                st.markdown(f"**{label}:** {val}")

    if st.button("🤖 Expand this case with AI", type="primary",
                 use_container_width=True, key="expand_go"):
        existing = {
            "title":             str(selected_row.get("Title", "")),
            "system":            str(selected_row.get("System", "")),
            "age_sex":           str(selected_row.get("Age_Sex", "")),
            "occupation":        str(selected_row.get("Occupation", "")),
            "chief_complaint":   str(selected_row.get("Chief_Complaint", "")),
            "duration":          str(selected_row.get("Duration", "")),
            "context":           str(selected_row.get("Context", "")),
            "hpi":               str(selected_row.get("HPI", "")),
            "pmh":               str(selected_row.get("PMH", "")),
            "family_hx":         str(selected_row.get("Family_Hx", "")),
            "social_hx":         str(selected_row.get("Social_Hx", "")),
            "medications":       str(selected_row.get("Medications", "")),
            "vitals":            str(selected_row.get("Vitals", "")),
            "appearance":        str(selected_row.get("Appearance", "")),
            "physical_findings": str(selected_row.get("Physical_Findings", "")),
            "labs":              str(selected_row.get("Labs", "")),
            "urine":             str(selected_row.get("Urine", "")),
            "imaging_tests":     str(selected_row.get("Imaging_Tests", "")),
            "xray_report":       str(selected_row.get("XRay_Report", "")),
            "ct_report":         str(selected_row.get("CT_Report", "")),
            "final_diagnosis":   str(selected_row.get("Final_Diagnosis", "")),
        }

        with st.spinner("AI is expanding the case... (10-20 seconds)"):
            expansion = generate_expansion(existing)

        if not expansion:
            st.error("Could not generate expansion. Try again in a minute.")
            return

        case_id = "AIEXP-" + uuid.uuid4().hex[:10].upper()
        record = {
            "case_id":           case_id,
            "source_brief":      f"Expanded from existing case [{existing['title']}]",
            "source_mode":       "expand_existing",
            "source_case_ref":   str(selected_row.get("Case_ID", "")),
            "status":            "draft",
            "created_by":        _admin_name(),
            "created_at":        datetime.now(timezone.utc).isoformat(),
            # Existing clinical fields (preserve)
            **{k: str(v)[:5000] if v is not None else "" for k, v in existing.items()},
            # New expansion fields
            **{k: str(v)[:5000] if v is not None else "" for k, v in expansion.items()},
        }
        result = insert_case(record)
        if result:
            st.success(f"✅ Expanded case saved as draft! Case ID: `{case_id}`")
            st.info("Review and approve it in the **⏳ Pending Drafts** tab.")
            with st.expander("Preview expanded case", expanded=True):
                _render_case_preview(record)
        else:
            st.error("Could not save expansion to database.")


# ───────────────────────────────────────────────────────────────────────────
# TAB 3: Bulk enrichment
# ───────────────────────────────────────────────────────────────────────────
def _tab_bulk_enrichment() -> None:
    st.markdown(
        "**Process multiple existing cases in a batch. Each becomes a separate draft.**"
    )
    st.warning(
        "⚠️ This makes one AI call per case. **Default limit: 5 at a time** to "
        "avoid rate-limiting. Processing 20+ cases at once may hit Gemini's free-tier limits."
    )

    cases_df = _get_host_cases_df()
    if cases_df is None or cases_df.empty:
        st.warning("Could not access existing case library.")
        return

    col1, col2 = st.columns(2)
    with col1:
        n_cases = st.number_input(
            "How many cases to enrich:",
            min_value=1, max_value=20, value=5, step=1,
            key="bulk_n",
        )
    with col2:
        system_filter = st.selectbox(
            "Filter by system (optional):",
            ["all"] + SYSTEMS,
            key="bulk_system",
        )

    # Filter the dataframe
    filtered = cases_df.copy()
    if system_filter != "all":
        filtered = cases_df[
            cases_df["System"].astype(str).str.lower().str.contains(system_filter, na=False)
        ]

    # Only pick cases not yet expanded (heuristic: by reference)
    # We get already-processed case_refs from approved + drafts
    already_processed = set()
    for case in list_drafts() + list_approved():
        ref = case.get("source_case_ref", "")
        if ref:
            already_processed.add(str(ref))

    filtered = filtered[~filtered["Case_ID"].astype(str).isin(already_processed)]

    st.caption(
        f"**{len(filtered)}** cases available to enrich (not yet processed). "
        f"Will process the first {min(n_cases, len(filtered))}."
    )

    if filtered.empty:
        st.info("No unprocessed cases to enrich for this filter.")
        return

    if st.button(f"🤖 Bulk-enrich {min(n_cases, len(filtered))} cases",
                 type="primary", use_container_width=True, key="bulk_go"):
        to_process = filtered.head(int(n_cases))
        progress = st.progress(0.0)
        status_text = st.empty()
        success_count = 0
        fail_count = 0

        for i, (idx, row) in enumerate(to_process.iterrows()):
            status_text.markdown(
                f"Processing case **{i+1} of {len(to_process)}**: "
                f"_{row.get('Title', '')[:50]}_"
            )
            existing = {
                "title":             str(row.get("Title", "")),
                "system":            str(row.get("System", "")),
                "age_sex":           str(row.get("Age_Sex", "")),
                "occupation":        str(row.get("Occupation", "")),
                "chief_complaint":   str(row.get("Chief_Complaint", "")),
                "duration":          str(row.get("Duration", "")),
                "context":           str(row.get("Context", "")),
                "hpi":               str(row.get("HPI", "")),
                "pmh":               str(row.get("PMH", "")),
                "family_hx":         str(row.get("Family_Hx", "")),
                "social_hx":         str(row.get("Social_Hx", "")),
                "medications":       str(row.get("Medications", "")),
                "vitals":            str(row.get("Vitals", "")),
                "appearance":        str(row.get("Appearance", "")),
                "physical_findings": str(row.get("Physical_Findings", "")),
                "labs":              str(row.get("Labs", "")),
                "urine":             str(row.get("Urine", "")),
                "imaging_tests":     str(row.get("Imaging_Tests", "")),
                "xray_report":       str(row.get("XRay_Report", "")),
                "ct_report":         str(row.get("CT_Report", "")),
                "final_diagnosis":   str(row.get("Final_Diagnosis", "")),
            }
            expansion = generate_expansion(existing)
            if expansion:
                case_id = "AIBULK-" + uuid.uuid4().hex[:10].upper()
                record = {
                    "case_id":           case_id,
                    "source_brief":      f"Bulk-expanded from [{existing['title']}]",
                    "source_mode":       "bulk_enrichment",
                    "source_case_ref":   str(row.get("Case_ID", "")),
                    "status":            "draft",
                    "created_by":        _admin_name(),
                    "created_at":        datetime.now(timezone.utc).isoformat(),
                    **{k: str(v)[:5000] if v is not None else "" for k, v in existing.items()},
                    **{k: str(v)[:5000] if v is not None else "" for k, v in expansion.items()},
                }
                if insert_case(record):
                    success_count += 1
                else:
                    fail_count += 1
            else:
                fail_count += 1

            progress.progress((i + 1) / len(to_process))

        status_text.empty()
        progress.empty()
        st.success(
            f"✅ Bulk enrichment complete! **{success_count}** succeeded, "
            f"**{fail_count}** failed."
        )
        st.info("Review all new drafts in the **⏳ Pending Drafts** tab.")
        if fail_count > 0:
            st.warning(
                "Some cases failed — usually because Gemini was rate-limited. "
                "Wait a minute and bulk-process the remaining cases again."
            )


# ───────────────────────────────────────────────────────────────────────────
# TAB 4: Pending drafts
# ───────────────────────────────────────────────────────────────────────────
def _tab_pending_drafts(drafts: List[Dict[str, Any]]) -> None:
    if not drafts:
        st.info(
            "✓ No drafts awaiting review. Use **Create from Scratch** or "
            "**Expand Existing** to generate cases."
        )
        return

    st.markdown(f"**{len(drafts)} case draft(s) awaiting review**")
    st.caption(
        "Review each case. Edit any field, then click Approve to add it to "
        "the student library, or Reject to discard."
    )

    for case in drafts:
        case_id = case.get("case_id", "")
        title = case.get("title", "(no title)")
        diag = case.get("final_diagnosis", "(no diagnosis)")
        with st.expander(
            f"📋 [{case_id}] {title} → {diag}",
            expanded=False
        ):
            _render_editable_draft(case)


def _render_editable_draft(case: Dict[str, Any]) -> None:
    case_id = case.get("case_id", "")
    st.caption(
        f"Source: {case.get('source_mode', '?')} · "
        f"Created: {case.get('created_at', '')[:10]} · "
        f"By: {case.get('created_by', '?')}"
    )

    with st.form(f"edit_case_{case_id}"):
        # All editable fields
        title = st.text_input("Title:", value=case.get("title", ""),
                               key=f"t_{case_id}")
        col1, col2 = st.columns(2)
        with col1:
            cur_sys = case.get("system", "general").lower()
            sys_idx = SYSTEMS.index(cur_sys) if cur_sys in SYSTEMS else 17
            system = st.selectbox("System:", SYSTEMS, index=sys_idx,
                                    key=f"sy_{case_id}")
        with col2:
            cur_dif = case.get("difficulty", "intermediate").lower()
            dif_idx = DIFFICULTIES.index(cur_dif) if cur_dif in DIFFICULTIES else 1
            difficulty = st.selectbox("Difficulty:", DIFFICULTIES, index=dif_idx,
                                        key=f"d_{case_id}")

        st.markdown("**📋 Patient & Presentation**")
        age_sex = st.text_input("Age & Sex:", value=case.get("age_sex", ""),
                                  key=f"as_{case_id}")
        chief_complaint = st.text_input(
            "Chief complaint:", value=case.get("chief_complaint", ""),
            key=f"cc_{case_id}")
        col1, col2 = st.columns(2)
        with col1:
            occupation = st.text_input("Occupation:",
                                         value=case.get("occupation", ""),
                                         key=f"oc_{case_id}")
        with col2:
            duration = st.text_input("Duration:",
                                       value=case.get("duration", ""),
                                       key=f"du_{case_id}")
        context = st.text_area("Context:", value=case.get("context", ""),
                                 height=60, key=f"co_{case_id}")

        st.markdown("**📜 History**")
        hpi = st.text_area("HPI:", value=case.get("hpi", ""),
                              height=100, key=f"h_{case_id}")
        col1, col2 = st.columns(2)
        with col1:
            pmh = st.text_area("Past Medical Hx:", value=case.get("pmh", ""),
                                 height=70, key=f"p_{case_id}")
            family_hx = st.text_area("Family Hx:", value=case.get("family_hx", ""),
                                       height=70, key=f"f_{case_id}")
        with col2:
            social_hx = st.text_area("Social Hx:", value=case.get("social_hx", ""),
                                       height=70, key=f"so_{case_id}")
            medications = st.text_area("Medications:",
                                         value=case.get("medications", ""),
                                         height=70, key=f"m_{case_id}")

        st.markdown("**🩺 Examination**")
        vitals = st.text_input("Vitals:", value=case.get("vitals", ""),
                                 key=f"v_{case_id}")
        appearance = st.text_input("Appearance:",
                                      value=case.get("appearance", ""),
                                      key=f"ap_{case_id}")
        physical_findings = st.text_area(
            "Physical findings:", value=case.get("physical_findings", ""),
            height=80, key=f"pf_{case_id}")

        st.markdown("**🔬 Investigations**")
        labs = st.text_area("Labs:", value=case.get("labs", ""),
                              height=80, key=f"l_{case_id}")
        col1, col2 = st.columns(2)
        with col1:
            urine = st.text_input("Urine:", value=case.get("urine", ""),
                                    key=f"u_{case_id}")
        with col2:
            imaging_tests = st.text_input("Imaging:",
                                             value=case.get("imaging_tests", ""),
                                             key=f"i_{case_id}")
        col1, col2 = st.columns(2)
        with col1:
            xray_report = st.text_area("X-Ray report:",
                                          value=case.get("xray_report", ""),
                                          height=80, key=f"x_{case_id}")
        with col2:
            ct_report = st.text_area("CT report:", value=case.get("ct_report", ""),
                                        height=80, key=f"ct_{case_id}")

        st.markdown("**🎯 Diagnosis & Teaching**")
        final_diagnosis = st.text_input(
            "Final diagnosis:", value=case.get("final_diagnosis", ""),
            key=f"fd_{case_id}")
        learning_objectives = st.text_area(
            "Learning objectives:",
            value=case.get("learning_objectives", ""),
            height=80, key=f"lo_{case_id}")
        differential = st.text_area(
            "Differential diagnoses:", value=case.get("differential", ""),
            height=80, key=f"df_{case_id}")
        diagnostic_reasoning = st.text_area(
            "Diagnostic reasoning:",
            value=case.get("diagnostic_reasoning", ""),
            height=80, key=f"dr_{case_id}")
        teaching_points = st.text_area(
            "Teaching points:", value=case.get("teaching_points", ""),
            height=80, key=f"tp_{case_id}")
        treatment = st.text_area(
            "Treatment:", value=case.get("treatment", ""),
            height=80, key=f"tr_{case_id}")
        tags = st.text_input("Tags (comma-separated):",
                                value=case.get("tags", ""),
                                key=f"tg_{case_id}")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            approve = st.form_submit_button("✓ Approve & publish",
                                              type="primary",
                                              use_container_width=True)
        with col_b:
            save = st.form_submit_button("💾 Save edits (keep draft)",
                                          use_container_width=True)
        with col_c:
            reject = st.form_submit_button("✗ Reject",
                                            use_container_width=True)

        if approve or save or reject:
            updates = {
                "title": title.strip(),
                "system": system,
                "difficulty": difficulty,
                "age_sex": age_sex.strip(),
                "occupation": occupation.strip(),
                "chief_complaint": chief_complaint.strip(),
                "duration": duration.strip(),
                "context": context.strip(),
                "hpi": hpi.strip(),
                "pmh": pmh.strip(),
                "family_hx": family_hx.strip(),
                "social_hx": social_hx.strip(),
                "medications": medications.strip(),
                "vitals": vitals.strip(),
                "appearance": appearance.strip(),
                "physical_findings": physical_findings.strip(),
                "labs": labs.strip(),
                "urine": urine.strip(),
                "imaging_tests": imaging_tests.strip(),
                "xray_report": xray_report.strip(),
                "ct_report": ct_report.strip(),
                "final_diagnosis": final_diagnosis.strip(),
                "learning_objectives": learning_objectives.strip(),
                "differential": differential.strip(),
                "diagnostic_reasoning": diagnostic_reasoning.strip(),
                "teaching_points": teaching_points.strip(),
                "treatment": treatment.strip(),
                "tags": tags.strip(),
            }
            if approve:
                updates["status"] = "approved"
                updates["approved_at"] = datetime.now(timezone.utc).isoformat()
                updates["approved_by"] = _admin_name()
                if update_case(case_id, updates):
                    st.success(f"✓ Case approved — now live for students.")
                    st.rerun()
                else:
                    st.error("Update failed.")
            elif reject:
                if update_case(case_id, {"status": "rejected"}):
                    st.warning("✗ Rejected.")
                    st.rerun()
            elif save:
                if update_case(case_id, updates):
                    st.success("💾 Saved.")
                    st.rerun()


# ───────────────────────────────────────────────────────────────────────────
# TAB 5: Approved bank
# ───────────────────────────────────────────────────────────────────────────
def _tab_approved_bank(approved: List[Dict[str, Any]]) -> None:
    if not approved:
        st.info("No approved cases yet. Approve drafts to add them here.")
        return

    st.markdown(f"**{len(approved)} approved AI-generated cases live in the library**")
    st.caption(
        "These appear in your student case library alongside your original 319 cases."
    )

    for case in approved:
        case_id = case.get("case_id", "")
        title = case.get("title", "(no title)")
        diag = case.get("final_diagnosis", "")
        system = case.get("system", "")
        with st.expander(
            f"✓ [{case_id}] {title} → {diag} ({system})",
            expanded=False
        ):
            _render_case_preview(case)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Move back to draft",
                              key=f"unapprove_{case_id}",
                              use_container_width=True):
                    if update_case(case_id, {"status": "draft", "approved_at": None}):
                        st.info("Moved back to drafts.")
                        st.rerun()
            with col2:
                if st.button("🗑️ Delete permanently",
                              key=f"delete_{case_id}",
                              use_container_width=True):
                    if delete_case(case_id):
                        st.warning("Deleted.")
                        st.rerun()


# ───────────────────────────────────────────────────────────────────────────
# Render a case preview
# ───────────────────────────────────────────────────────────────────────────
def _render_case_preview(case: Dict[str, Any]) -> None:
    fields = [
        ("Title", "title"), ("System", "system"), ("Difficulty", "difficulty"),
        ("Age & Sex", "age_sex"), ("Occupation", "occupation"),
        ("Chief complaint", "chief_complaint"), ("Duration", "duration"),
        ("Context", "context"),
        ("HPI", "hpi"), ("PMH", "pmh"), ("Family Hx", "family_hx"),
        ("Social Hx", "social_hx"), ("Medications", "medications"),
        ("Vitals", "vitals"), ("Appearance", "appearance"),
        ("Physical findings", "physical_findings"),
        ("Labs", "labs"), ("Urine", "urine"), ("Imaging", "imaging_tests"),
        ("X-Ray", "xray_report"), ("CT", "ct_report"),
        ("Final diagnosis", "final_diagnosis"),
        ("Learning objectives", "learning_objectives"),
        ("Differential", "differential"),
        ("Diagnostic reasoning", "diagnostic_reasoning"),
        ("Teaching points", "teaching_points"),
        ("Treatment", "treatment"), ("Tags", "tags"),
    ]
    for label, key in fields:
        val = case.get(key, "")
        if val and str(val).strip():
            st.markdown(f"**{label}:** {val}")


# ───────────────────────────────────────────────────────────────────────────
# Access host app's cases_df
# ───────────────────────────────────────────────────────────────────────────
def _get_host_cases_df() -> Optional[pd.DataFrame]:
    """Try to fetch the host app's cases_df via cached load_cases()."""
    try:
        import sys
        host = sys.modules.get("__main__")
        if host and hasattr(host, "load_cases"):
            df = host.load_cases()
            if df is not None and not df.empty:
                return df
    except Exception as e:
        print(f"[case_creator] could not access cases_df: {e}")
    return None


# ═══════════════════════════════════════════════════════════════════════════
# SUPABASE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════
CASES_EXTENDED_SCHEMA = """
-- ─────────────────────────────────────────────────────────────────────
-- AI Case Creator — extended cases table
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.cases_extended (
    case_id              text PRIMARY KEY,
    title                text DEFAULT '',
    system               text DEFAULT 'general',
    difficulty           text DEFAULT 'basic',
    age_sex              text DEFAULT '',
    occupation           text DEFAULT '',
    chief_complaint      text DEFAULT '',
    duration             text DEFAULT '',
    context              text DEFAULT '',
    hpi                  text DEFAULT '',
    pmh                  text DEFAULT '',
    family_hx            text DEFAULT '',
    social_hx            text DEFAULT '',
    medications          text DEFAULT '',
    vitals               text DEFAULT '',
    appearance           text DEFAULT '',
    physical_findings    text DEFAULT '',
    labs                 text DEFAULT '',
    urine                text DEFAULT '',
    imaging_tests        text DEFAULT '',
    xray_report          text DEFAULT '',
    ct_report            text DEFAULT '',
    final_diagnosis      text DEFAULT '',
    learning_objectives  text DEFAULT '',
    differential         text DEFAULT '',
    diagnostic_reasoning text DEFAULT '',
    teaching_points      text DEFAULT '',
    treatment            text DEFAULT '',
    tags                 text DEFAULT '',
    status               text DEFAULT 'draft',
    source_brief         text DEFAULT '',
    source_mode          text DEFAULT '',
    source_case_ref      text DEFAULT '',
    created_by           text DEFAULT '',
    approved_by          text DEFAULT '',
    approved_at          timestamptz,
    created_at           timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cases_ext_status
    ON public.cases_extended(status, created_at);
CREATE INDEX IF NOT EXISTS idx_cases_ext_system
    ON public.cases_extended(system, difficulty);
CREATE INDEX IF NOT EXISTS idx_cases_ext_source
    ON public.cases_extended(source_case_ref) WHERE source_case_ref != '';

ALTER TABLE public.cases_extended ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all cases_extended" ON public.cases_extended;
CREATE POLICY "Allow all cases_extended" ON public.cases_extended
    FOR ALL USING (true) WITH CHECK (true);
"""


if __name__ == "__main__":
    print("MLS Virtual Hospital — AI Case Creator")
    print("=" * 60)
    print(CASES_EXTENDED_SCHEMA)
