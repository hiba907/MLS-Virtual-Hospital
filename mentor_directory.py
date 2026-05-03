"""
═══════════════════════════════════════════════════════════════════════════
  MLS Virtual Hospital — Mentor Directory v2 (Self-Registered Seniors)
  ─────────────────────────────────────────────────────────────────────────
  Connects Residents/Students with Senior Doctors who registered through
  the standard signup flow. Seniors require admin verification before
  appearing in the directory.

  HOW IT WORKS:
  ─────────────
  1. Anyone signs up with role = "senior" + their specialty + hospital
  2. Senior gets full app access immediately, but is_verified = False
  3. Admin (Dr. Hiba) sees pending Seniors in admin panel, clicks "Verify"
  4. Once verified, Senior appears in directory for residents/students to find
  5. Residents browse Seniors by specialty, request a session
  6. Senior gets notified, joins the embedded Jitsi call in-app

  AUTHOR: Hiba Hamdar — Academy of Medical Learning Skills
  COPYRIGHT (c) 2026 — All Rights Reserved
═══════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from urllib.parse import quote
import uuid
import requests


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
QUESTIONS_PER_CASE_LIMIT = 2

SPECIALTIES = [
    "General Medicine", "Cardiology",
    "Respiratory / Pulmonology", "Gastroenterology",
    "Endocrinology", "Neurology", "Nephrology",
    "Hematology / Oncology", "Infectious Diseases",
    "Rheumatology", "Emergency Medicine",
    "Critical Care / ICU", "General Surgery",
    "Orthopedics", "Obstetrics & Gynecology",
    "Pediatrics", "Psychiatry", "Dermatology",
    "Radiology", "Anesthesiology", "Family Medicine",
    "Other",
]

COMM_PREFERENCES = [
    "Embedded video call (in-app)",
    "WhatsApp message",
    "Email",
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
               st.session_state.get("user_id", "") or
               st.session_state.get("user_email", "") or "anon")


def _get_user_name() -> str:
    auth = st.session_state.get("auth_user", {}) or {}
    return auth.get("name") or auth.get("email") or "Student"


def _get_user_role() -> str:
    auth = st.session_state.get("auth_user", {}) or {}
    return (auth.get("role") or "student").lower()


def _is_admin() -> bool:
    auth = st.session_state.get("auth_user", {}) or {}
    role = (auth.get("role") or "").lower()
    if role in ("admin", "faculty"):
        return True
    admin_email = _safe_secret("ADMIN_EMAIL", "hamdarhiba95@gmail.com").strip().lower()
    user_email  = (auth.get("email") or "").strip().lower()
    return bool(user_email and admin_email and user_email == admin_email)


# ═══════════════════════════════════════════════════════════════════════════
# QUERIES
# ═══════════════════════════════════════════════════════════════════════════
def list_verified_seniors(specialty: Optional[str] = None) -> List[Dict[str, Any]]:
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/vh_users"
    params = {
        "role":        "eq.senior",
        "is_verified": "eq.true",
        "select":      "id,name,email,specialty,hospital,is_verified,created_at",
        "order":       "name.asc",
    }
    if specialty and specialty != "All":
        params["specialty"] = f"eq.{specialty}"
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return r.json() or []
    except Exception as e:
        print(f"[mentor_directory] list_verified_seniors error: {e}")
    return []


def list_unverified_seniors() -> List[Dict[str, Any]]:
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/vh_users"
    params = {
        "role":        "eq.senior",
        "is_verified": "eq.false",
        "select":      "id,name,email,specialty,hospital,is_verified,created_at",
        "order":       "created_at.desc",
    }
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return r.json() or []
    except Exception:
        pass
    return []


def get_unverified_senior_count() -> int:
    return len(list_unverified_seniors())


def verify_senior(user_id: str) -> bool:
    if not _is_admin() or not _sb_available():
        return False
    url = f"{_supabase_url()}/rest/v1/vh_users"
    try:
        r = requests.patch(url, headers=_sb_headers(),
                            params={"id": f"eq.{user_id}"},
                            json={"is_verified": True},
                            timeout=8)
        return r.status_code in (200, 204)
    except Exception:
        return False


def unverify_senior(user_id: str) -> bool:
    if not _is_admin() or not _sb_available():
        return False
    url = f"{_supabase_url()}/rest/v1/vh_users"
    try:
        r = requests.patch(url, headers=_sb_headers(),
                            params={"id": f"eq.{user_id}"},
                            json={"is_verified": False},
                            timeout=8)
        return r.status_code in (200, 204)
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════
# SESSIONS
# ═══════════════════════════════════════════════════════════════════════════
def get_session_count_for_case(*, senior_id: str, case_id: str) -> int:
    if not _sb_available():
        return 0
    user_id = _get_user_id()
    url = f"{_supabase_url()}/rest/v1/mentor_sessions"
    params = {
        "user_id":   f"eq.{user_id}",
        "senior_id": f"eq.{senior_id}",
        "case_id":   f"eq.{case_id}",
        "select":    "session_id",
    }
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return len(r.json() or [])
    except Exception:
        pass
    return 0


def request_session(
    *, senior_id: str, senior_name: str, senior_specialty: str,
    case_title: str, case_id: str,
    question_summary: str, preferred_slots: str = "",
    comm_method: str = "Embedded video call (in-app)",
) -> Optional[Dict[str, Any]]:
    if not _sb_available():
        return None
    if get_session_count_for_case(senior_id=senior_id, case_id=case_id) >= QUESTIONS_PER_CASE_LIMIT:
        return None

    session_id = "ses_" + uuid.uuid4().hex[:10]
    user_id = _get_user_id()
    jitsi_room = f"MLS-{user_id[:6]}-{senior_id[:6]}-{uuid.uuid4().hex[:8]}"

    record = {
        "session_id":       session_id,
        "user_id":          user_id,
        "user_name":        _get_user_name(),
        "user_role":        _get_user_role(),
        "senior_id":        senior_id,
        "senior_name":      senior_name,
        "senior_specialty": senior_specialty,
        "case_title":       case_title[:200] if case_title else "",
        "case_id":          case_id[:60] if case_id else "no_case",
        "question_summary": question_summary[:1000],
        "preferred_slots":  preferred_slots[:300],
        "comm_method":      comm_method,
        "jitsi_room":       jitsi_room,
        "status":           "pending",
        "created_at":       datetime.now(timezone.utc).isoformat(),
    }
    url = f"{_supabase_url()}/rest/v1/mentor_sessions"
    try:
        r = requests.post(url, headers=_sb_headers(), json=record, timeout=8)
        if r.status_code in (200, 201):
            return record
    except Exception as e:
        print(f"[mentor_directory] request_session error: {e}")
    return None


def list_sessions_for_user(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    user_id = user_id or _get_user_id()
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/mentor_sessions"
    params = {
        "or": f"(user_id.eq.{user_id},senior_id.eq.{user_id})",
        "select": "*",
        "order": "created_at.desc",
    }
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return r.json() or []
    except Exception:
        pass
    return []


def list_pending_sessions() -> List[Dict[str, Any]]:
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/mentor_sessions"
    params = {"status": "eq.pending", "select": "*", "order": "created_at.asc"}
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return r.json() or []
    except Exception:
        pass
    return []


def get_pending_session_count() -> int:
    return len(list_pending_sessions())


def update_session_status(session_id: str, *, status: str,
                           admin_notes: str = "") -> bool:
    if not _sb_available():
        return False
    update = {"status": status}
    if admin_notes:
        update["admin_notes"] = admin_notes
    if status == "completed":
        update["completed_at"] = datetime.now(timezone.utc).isoformat()
    url = f"{_supabase_url()}/rest/v1/mentor_sessions"
    try:
        r = requests.patch(url, headers=_sb_headers(),
                            params={"session_id": f"eq.{session_id}"},
                            json=update, timeout=8)
        return r.status_code in (200, 204)
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════
# UI: STUDENT-FACING DIRECTORY
# ═══════════════════════════════════════════════════════════════════════════
def render_mentor_directory_page() -> None:
    st.markdown(
        '<div class="section-header">👨‍⚕️ Mentor Directory — Find a Senior</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div style="background:linear-gradient(135deg,#0a2540,#1a4f8a);color:white;
                border-radius:14px;padding:1.4rem 1.6rem;margin-bottom:1rem;">
      <div style="font-size:1.3rem;font-weight:800;margin-bottom:.4rem;">
        Connect with Senior Doctors
      </div>
      <div style="font-size:.92rem;opacity:.92;line-height:1.5;">
        Browse verified senior doctors registered to mentor. Filter by specialty,
        send a question, and join an in-app video call when they accept.
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("⚠️ Important guidance — read once before booking", expanded=False):
        st.markdown("""
- Conversations are **educational only** — for learning, not for clinical advice on real patients
- Do NOT share patient-identifiable information (names, hospital IDs, photos)
- Senior doctors here volunteer their time — be respectful and prepared
- You can book up to **2 sessions per case per senior** — make them count
- If you need urgent help with a real patient, contact your local emergency service
        """)

    cf1, cf2 = st.columns([3, 1])
    with cf1:
        spec_filter = st.selectbox(
            "Filter by specialty:",
            ["All"] + SPECIALTIES,
            key="mentor_dir_specialty",
        )
    with cf2:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("🔄 Refresh", use_container_width=True, key="mentor_refresh"):
            st.rerun()

    seniors = list_verified_seniors(specialty=spec_filter)
    if not seniors:
        st.info(
            "No verified seniors are currently listed for this specialty. "
            "If you're a senior wanting to mentor, register and ask the admin to verify you."
        )
        return

    st.markdown(f"**{len(seniors)} verified senior{'s' if len(seniors)!=1 else ''}**")
    for s in seniors:
        _render_senior_card(s)


def _render_senior_card(senior: Dict[str, Any]) -> None:
    name      = senior.get("name", "")
    specialty = senior.get("specialty", "") or "General Medicine"
    hospital  = senior.get("hospital", "") or ""
    senior_id = str(senior.get("id", ""))
    initials = "".join([w[0].upper() for w in name.split()[:2]]) if name else "DR"

    st.markdown(f"""
    <div style="background:white;border:1.5px solid #e2e8f0;border-radius:14px;
                padding:1.2rem 1.4rem;margin-bottom:.8rem;
                box-shadow:0 2px 6px rgba(0,0,0,.04);">
      <div style="display:flex;gap:1rem;align-items:flex-start;">
        <div style="width:64px;height:64px;border-radius:50%;
                    background:linear-gradient(135deg,#0e7490,#0369a1);color:white;
                    display:flex;align-items:center;justify-content:center;
                    font-size:1.3rem;font-weight:800;flex-shrink:0;">
          {initials}
        </div>
        <div style="flex:1;min-width:0;">
          <div style="font-size:1.1rem;font-weight:800;color:#0f172a;">{name}</div>
          <div style="font-size:.88rem;color:#0e7490;font-weight:600;
                      margin-top:.15rem;">
            ✓ Verified Senior · {specialty}
          </div>
          {f'<div style="font-size:.82rem;color:#64748b;margin-top:.15rem;">{hospital}</div>' if hospital else ''}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    expander_key = f"book_expander_{senior_id}"
    if st.button(f"📅 Request a session with {name}",
                 key=f"book_btn_{senior_id}",
                 use_container_width=True):
        st.session_state[expander_key] = not st.session_state.get(expander_key, False)
        st.rerun()

    if st.session_state.get(expander_key):
        _render_booking_form(senior)


def _render_booking_form(senior: Dict[str, Any]) -> None:
    senior_id   = str(senior.get("id", ""))
    senior_name = senior.get("name", "")
    senior_spec = senior.get("specialty", "") or "General Medicine"

    case = st.session_state.get("selected_case") or {}
    case_title = case.get("Title") or case.get("Chief_Complaint") or "General question (no specific case loaded)"
    case_id    = str(case.get("Case_ID") or case.get("id") or "no_case")

    used = get_session_count_for_case(senior_id=senior_id, case_id=case_id)
    remaining = max(0, QUESTIONS_PER_CASE_LIMIT - used)

    st.markdown(f"""
    <div style="background:#f0f9ff;border:1.5px solid #0ea5e9;
                border-radius:10px;padding:1rem;margin-bottom:.6rem;">
      <div style="font-size:.9rem;color:#0369a1;font-weight:700;margin-bottom:.3rem;">
        📝 Request a session with {senior_name}
      </div>
      <div style="font-size:.78rem;color:#075985;">
        Case: <b>{case_title}</b> · Sessions remaining: <b>{remaining}/{QUESTIONS_PER_CASE_LIMIT}</b>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if remaining <= 0:
        st.warning(
            f"You've already used your {QUESTIONS_PER_CASE_LIMIT} sessions "
            f"with {senior_name} for this case. Try a different senior."
        )
        return

    with st.form(f"booking_form_{senior_id}"):
        question = st.text_area(
            "What's your question?",
            placeholder=(
                "Be specific. Example: 'I'm confused about ECG interpretation in this "
                "case — ST elevation in II/III/aVF but troponin decreasing. Could this "
                "be a reperfused inferior MI?'"
            ),
            height=120,
        )
        slots = st.text_input(
            "When are you available? (free text)",
            placeholder="Tue 6-8pm, Thu after 4pm",
        )
        method = st.radio(
            "How would you like to connect?",
            COMM_PREFERENCES,
            horizontal=False,
        )
        agree = st.checkbox(
            "✓ I understand this is for educational discussion only and not "
            "for clinical advice on real patients.",
            value=False,
        )
        submitted = st.form_submit_button(
            "📨 Send Request", type="primary", use_container_width=True
        )

        if submitted:
            if not question or len(question) < 30:
                st.error("Please write a more specific question (at least 30 characters).")
            elif not slots:
                st.error("Please tell us when you're available.")
            elif not agree:
                st.error("Please acknowledge the educational disclaimer.")
            else:
                rec = request_session(
                    senior_id=senior_id, senior_name=senior_name,
                    senior_specialty=senior_spec,
                    case_title=case_title, case_id=case_id,
                    question_summary=question, preferred_slots=slots,
                    comm_method=method,
                )
                if rec:
                    st.success(
                        f"✓ Request sent to {senior_name}! They'll see it in "
                        "their My Sessions page. Once accepted, you'll both get "
                        "an in-app video call link."
                    )
                    try:
                        from tier1_features import award_xp
                        award_xp("ai_tutor_session", amount=15, toast=False)
                    except Exception:
                        pass
                    st.session_state[f"book_expander_{senior_id}"] = False
                else:
                    st.error("Could not create session request. Try again.")


# ═══════════════════════════════════════════════════════════════════════════
# UI: MY SESSIONS (both student & senior)
# ═══════════════════════════════════════════════════════════════════════════
def render_my_sessions_page() -> None:
    st.markdown(
        '<div class="section-header">📋 My Mentor Sessions</div>',
        unsafe_allow_html=True
    )
    sessions = list_sessions_for_user()
    if not sessions:
        st.info(
            "You have no sessions yet. As a student/resident, browse the Mentor "
            "Directory to request one. As a senior, residents will request sessions with you."
        )
        return

    user_id = _get_user_id()
    role = _get_user_role()

    pending   = [s for s in sessions if s.get("status") == "pending"]
    accepted  = [s for s in sessions if s.get("status") in ("accepted", "scheduled")]
    completed = [s for s in sessions if s.get("status") in ("completed", "cancelled")]

    tabs = st.tabs([
        f"🟡 Pending ({len(pending)})",
        f"🟢 Active ({len(accepted)})",
        f"✓ Past ({len(completed)})",
    ])

    with tabs[0]:
        if not pending: st.info("No pending sessions.")
        for ses in pending:
            _render_session_card(ses, user_id, role)

    with tabs[1]:
        if not accepted:
            st.info("No active sessions. Once a senior accepts a request, "
                    "it'll appear here with a join button.")
        for ses in accepted:
            _render_session_card(ses, user_id, role)

    with tabs[2]:
        if not completed: st.info("No past sessions yet.")
        for ses in completed:
            _render_session_card(ses, user_id, role, compact=True)


def _render_session_card(ses: Dict[str, Any], user_id: str, role: str,
                          compact: bool = False) -> None:
    is_student = (str(ses.get("user_id")) == user_id)
    is_senior  = (str(ses.get("senior_id")) == user_id)
    status     = ses.get("status", "pending")
    other_party = (ses.get("senior_name") if is_student else ses.get("user_name")) or ""

    status_colors = {
        "pending":   ("#f59e0b", "Pending"),
        "accepted":  ("#10b981", "Accepted"),
        "scheduled": ("#10b981", "Scheduled"),
        "completed": ("#64748b", "Completed"),
        "cancelled": ("#dc2626", "Cancelled"),
    }
    color, label = status_colors.get(status, ("#64748b", status))

    st.markdown(f"""
    <div style="background:white;border-left:4px solid {color};
                border:1px solid #e2e8f0;border-radius:10px;
                padding:1rem 1.2rem;margin-bottom:.6rem;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div style="font-weight:700;color:#0f172a;">
          {('From: ' if is_senior else 'With: ')} {other_party}
        </div>
        <span style="background:{color}22;color:{color};
                     padding:.2rem .65rem;border-radius:999px;
                     font-size:.72rem;font-weight:700;">
          {label.upper()}
        </span>
      </div>
      <div style="font-size:.82rem;color:#64748b;margin-top:.3rem;">
        Case: {ses.get('case_title', '—')[:80]}
      </div>
      <div style="font-size:.85rem;color:#0f172a;margin-top:.5rem;line-height:1.5;">
        <b>Question:</b> {ses.get('question_summary', '—')[:300]}
      </div>
    </div>
    """, unsafe_allow_html=True)

    if compact:
        return

    if is_senior and status == "pending":
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✓ Accept", key=f"accept_{ses['session_id']}",
                          type="primary", use_container_width=True):
                if update_session_status(ses["session_id"], status="accepted"):
                    st.success("Accepted! Join the video call below.")
                    st.rerun()
        with c2:
            if st.button("✗ Decline", key=f"decline_{ses['session_id']}",
                          use_container_width=True):
                if update_session_status(ses["session_id"], status="cancelled",
                                          admin_notes="Declined by senior"):
                    st.warning("Session declined.")
                    st.rerun()

    if status in ("accepted", "scheduled") and (is_student or is_senior):
        if st.button(f"🎥 Join video call",
                      key=f"join_{ses['session_id']}",
                      type="primary", use_container_width=True):
            st.session_state["_active_jitsi_room"]    = ses.get("jitsi_room", "")
            st.session_state["_active_jitsi_subject"] = (
                f"Mentor session: {ses.get('case_title', 'discussion')}"
            )
            st.session_state["_active_jitsi_partner"] = other_party
            st.session_state["_active_jitsi_session_id"] = ses["session_id"]
            st.session_state.page = "jitsi_call"
            st.rerun()

    if status in ("accepted", "scheduled") and (is_student or is_senior):
        if st.button("Mark as completed",
                      key=f"complete_{ses['session_id']}",
                      use_container_width=True):
            if update_session_status(ses["session_id"], status="completed"):
                st.success("Marked complete. Thanks!")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# UI: EMBEDDED JITSI VIDEO CALL
# ═══════════════════════════════════════════════════════════════════════════
def render_jitsi_call_page() -> None:
    """Embedded Jitsi Meet — runs INSIDE the app, not a new tab."""
    room    = st.session_state.get("_active_jitsi_room", "")
    subject = st.session_state.get("_active_jitsi_subject", "Mentor Session")
    partner = st.session_state.get("_active_jitsi_partner", "")
    session_id = st.session_state.get("_active_jitsi_session_id", "")

    st.markdown(
        '<div class="section-header">🎥 In-App Video Call</div>',
        unsafe_allow_html=True
    )

    if not room:
        st.warning("No active call. Go to **My Sessions** to join one.")
        if st.button("← Back to My Sessions"):
            st.session_state.page = "my_sessions"
            st.rerun()
        return

    user_name = _get_user_name().replace('"', '').replace("'", "")[:50]

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0a2540,#1a4f8a);color:white;
                border-radius:12px;padding:1rem 1.4rem;margin-bottom:.6rem;">
      <div style="font-size:1rem;font-weight:700;">📞 {subject}</div>
      <div style="font-size:.82rem;opacity:.85;margin-top:.2rem;">
        With: {partner} · Powered by Jitsi Meet (free, encrypted)
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Jitsi iframe — embedded player
    components.html(f"""
    <div style="position:relative;width:100%;padding-top:65%;
                background:#000;border-radius:12px;overflow:hidden;">
      <iframe
        src="https://meet.jit.si/{room}#userInfo.displayName=%22{quote(user_name)}%22&config.prejoinPageEnabled=false"
        style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;"
        allow="camera; microphone; fullscreen; display-capture; autoplay"
        allowfullscreen>
      </iframe>
    </div>
    <div style="margin-top:.6rem;font-size:.78rem;color:#64748b;text-align:center;">
      If the call doesn't load,
      <a href="https://meet.jit.si/{room}" target="_blank" rel="noopener"
         style="color:#0e7490;font-weight:700;">open in new tab</a>.
    </div>
    """, height=600)

    st.markdown("---")
    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("← Back to My Sessions", use_container_width=True):
            st.session_state.page = "my_sessions"
            st.rerun()
    with cb2:
        if session_id and st.button("✓ End & Mark Complete",
                                     type="primary", use_container_width=True):
            if update_session_status(session_id, status="completed"):
                st.success("Session marked complete.")
                st.session_state.page = "my_sessions"
                st.rerun()


def render_book_session_button(*, label: str = "📅 Find a senior to discuss this") -> None:
    if st.button(label, use_container_width=True,
                  key=f"booksess_{uuid.uuid4().hex[:6]}"):
        st.session_state.page = "mentor_directory"
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# UI: ADMIN PANEL
# ═══════════════════════════════════════════════════════════════════════════
def render_admin_mentor_panel() -> None:
    if not _is_admin():
        st.error("This page is for admins only.")
        return

    st.markdown(
        '<div class="section-header">🛠️ Mentor Admin Panel</div>',
        unsafe_allow_html=True
    )

    pending_seniors  = list_unverified_seniors()
    verified_seniors = list_verified_seniors()
    pending_sessions = list_pending_sessions()

    tabs = st.tabs([
        f"⏳ Verify Seniors ({len(pending_seniors)})",
        f"👥 Verified Seniors ({len(verified_seniors)})",
        f"📋 All Sessions ({len(pending_sessions)})",
    ])

    with tabs[0]:
        _admin_pending_seniors_tab(pending_seniors)
    with tabs[1]:
        _admin_verified_seniors_tab(verified_seniors)
    with tabs[2]:
        _admin_sessions_tab(pending_sessions)


def _admin_pending_seniors_tab(pending: List[Dict[str, Any]]) -> None:
    if not pending:
        st.info("✓ No seniors awaiting verification right now.")
        return
    st.markdown(
        f"**{len(pending)} senior{'s' if len(pending)!=1 else ''} awaiting verification**"
    )
    st.caption(
        "Verify seniors **only** after confirming their credentials offline "
        "(medical license, hospital affiliation, etc.)."
    )
    for s in pending:
        with st.expander(
            f"{s.get('name', '—')} · {s.get('specialty', '—')} · {s.get('email', '—')}",
            expanded=True
        ):
            st.markdown(f"**Email:** {s.get('email', '—')}")
            st.markdown(f"**Specialty:** {s.get('specialty', '—')}")
            st.markdown(f"**Hospital:** {s.get('hospital', '—') or '*not provided*'}")
            st.caption(f"Registered: {s.get('created_at', '')}")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("✓ Verify this senior",
                              key=f"verify_{s.get('id')}",
                              type="primary",
                              use_container_width=True):
                    if verify_senior(str(s.get("id", ""))):
                        st.success(f"✓ {s.get('name')} verified.")
                        st.rerun()
                    else:
                        st.error("Could not update — check DB.")
            with c2:
                if st.button("✗ Leave unverified",
                              key=f"skip_{s.get('id')}",
                              use_container_width=True):
                    st.info("Left unverified.")


def _admin_verified_seniors_tab(verified: List[Dict[str, Any]]) -> None:
    if not verified:
        st.info("No verified seniors yet.")
        return
    st.markdown(f"**{len(verified)} verified senior{'s' if len(verified)!=1 else ''}**")
    for s in verified:
        with st.expander(f"{s.get('name', '—')} · {s.get('specialty', '—')}"):
            st.markdown(f"**Email:** {s.get('email', '—')}")
            st.markdown(f"**Hospital:** {s.get('hospital', '—') or '*not set*'}")
            st.caption(f"Registered: {s.get('created_at', '')}")
            if st.button("Revoke verification",
                          key=f"revoke_{s.get('id')}"):
                if unverify_senior(str(s.get("id", ""))):
                    st.warning("Verification revoked.")
                    st.rerun()


def _admin_sessions_tab(pending: List[Dict[str, Any]]) -> None:
    if not pending:
        st.info("No pending sessions in the system.")
        return
    st.markdown(f"**{len(pending)} pending session request{'s' if len(pending)!=1 else ''}**")
    for ses in pending:
        with st.expander(
            f"{ses.get('user_name', '?')} → {ses.get('senior_name', '?')} · "
            f"{ses.get('case_title', 'no case')[:50]}"
        ):
            st.markdown(f"**From:** {ses.get('user_name')} ({ses.get('user_role')})")
            st.markdown(f"**To:** {ses.get('senior_name')} ({ses.get('senior_specialty')})")
            st.markdown(f"**Question:** {ses.get('question_summary', '')}")
            st.markdown(f"**Available:** {ses.get('preferred_slots', '')}")
            st.markdown(f"**Method:** {ses.get('comm_method', '')}")
            st.caption(f"Requested: {ses.get('created_at', '')}")
            if st.button("🗑️ Cancel this request",
                          key=f"admin_cancel_{ses['session_id']}"):
                if update_session_status(ses["session_id"], status="cancelled",
                                          admin_notes="Cancelled by admin"):
                    st.warning("Cancelled.")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# REQUIRED SUPABASE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════
MENTOR_SCHEMA_V2 = """
-- ─────────────────────────────────────────────────────────────────────
-- Mentor Directory v2 — Self-Registered Seniors with Admin Verification
-- Run this in Supabase SQL Editor
-- ─────────────────────────────────────────────────────────────────────

-- 1. Add new columns to vh_users (idempotent)
alter table public.vh_users
    add column if not exists specialty   text default '',
    add column if not exists hospital    text default '',
    add column if not exists is_verified boolean default true;

-- 2. Default existing seniors to unverified
update public.vh_users set is_verified = false
    where role = 'senior' and is_verified is distinct from false;

-- 3. Sessions table
create table if not exists public.mentor_sessions (
    session_id        text primary key,
    user_id           text not null,
    user_name         text default '',
    user_role         text default 'student',
    senior_id         text not null,
    senior_name       text default '',
    senior_specialty  text default '',
    case_title        text default '',
    case_id           text default '',
    question_summary  text not null,
    preferred_slots   text default '',
    comm_method       text default '',
    jitsi_room        text default '',
    status            text default 'pending',
    admin_notes       text default '',
    completed_at      timestamptz,
    created_at        timestamptz default now()
);

create index if not exists idx_msess_status on public.mentor_sessions(status, created_at);
create index if not exists idx_msess_user   on public.mentor_sessions(user_id, senior_id, case_id);
create index if not exists idx_msess_senior on public.mentor_sessions(senior_id, status);

alter table public.mentor_sessions enable row level security;

drop policy if exists "Allow all mentor_sessions" on public.mentor_sessions;
create policy "Allow all mentor_sessions"
    on public.mentor_sessions for all using (true) with check (true);
"""

if __name__ == "__main__":
    print("MLS Virtual Hospital — Mentor Directory v2")
    print("=" * 60)
    print(MENTOR_SCHEMA_V2)
