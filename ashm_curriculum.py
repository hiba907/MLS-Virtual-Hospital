"""
ashm_curriculum.py
────────────────────────────────────────────────────────────────────────────
12-month curriculum tracker for the ASHM Fellowship. This is the backbone
that makes the fellowship an actual sequenced program instead of a menu of
unrelated tools: a fellow enrolls once, the system computes which month
they're in from their enrollment date, and each month's card links straight
into the real working module for that phase.

Requires one new Supabase table (same project as vh_users):

    create table vh_fellowship_enrollment (
      id             bigint generated always as identity primary key,
      email            text unique not null,
      name               text,
      start_date           date not null,
      manual_month_override integer,
      created_at              timestamp default now()
    );

`manual_month_override` lets faculty manually advance/hold a fellow instead
of relying purely on calendar time — useful in a pilot cohort.
"""

import datetime
import requests
import streamlit as st

NAVY, BLUE, TEAL, TEAL_LT = "#0a2540", "#1a4f8a", "#0e7490", "#0ea5e9"
GREEN, AMBER, RED, PURPLE = "#059669", "#d97706", "#dc2626", "#7c3aed"
SURFACE, BORDER, TEXT, MUTED = "#ffffff", "#e2e8f0", "#0f172a", "#64748b"

TABLE = "vh_fellowship_enrollment"

CURRICULUM = [
    {"months": (1, 2), "key": "multipatient", "title": "Multi-Patient Caseload",
     "dept": "Internal Medicine + ER", "skill": "Triage & prioritization under pressure",
     "route": "medsim_multipatient", "route_label": "Open Multi-Patient Caseload"},
    {"months": (3, 4), "key": "handoff", "title": "Cross-Department Handoff",
     "dept": "ICU + Surgery", "skill": "Continuity-of-care management",
     "route": "ashm_handoff", "route_label": "Open Handoff Tracker"},
    {"months": (5, 6), "key": "audit", "title": "AI Auditing",
     "dept": "Cross-specialty", "skill": "Critical evaluation of AI-driven diagnosis",
     "route": "ashm_ai_audit", "route_label": "Open AI Auditing Queue"},
    {"months": (7, 8), "key": "teaching", "title": "Peer Teaching & Supervision",
     "dept": "", "skill": "Clinical teaching & leadership",
     "route": "ashm_peer_teaching", "route_label": "Open Supervision Queue"},
    {"months": (9, 10), "key": "population", "title": "Population Health View",
     "dept": "", "skill": "Population-level clinical reasoning",
     "route": "ashm_population_health", "route_label": "Open Population Health View"},
    {"months": (11, 12), "key": "capstone", "title": "Capstone: New Case Design",
     "dept": "", "skill": "Case authorship & lasting contribution",
     "route": "ashm_fellowship_author", "route_label": "Open Case Authoring"},
]


def _sb_creds():
    return st.secrets.get("SUPABASE_URL", ""), st.secrets.get("SUPABASE_KEY", "")


def _sb_available() -> bool:
    url, key = _sb_creds()
    return bool(url and key and not url.startswith("YOUR_"))


def _sb_headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation"}


def get_enrollment(email: str):
    if not _sb_available() or not email:
        return None
    url, key = _sb_creds()
    try:
        r = requests.get(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key),
                          params={"select": "*", "email": f"eq.{email}"}, timeout=10)
        rows = r.json() if r.status_code == 200 else []
        return rows[0] if rows else None
    except Exception:
        return None


def enroll(email: str, name: str, start_date: datetime.date) -> tuple:
    if not _sb_available():
        return False, "Supabase not configured."
    url, key = _sb_creds()
    try:
        r = requests.post(f"{url}/rest/v1/{TABLE}",
                           headers={**_sb_headers(key), "Prefer": "resolution=merge-duplicates,return=representation"},
                           json={"email": email, "name": name, "start_date": start_date.isoformat()}, timeout=10)
        return (True, "Enrolled.") if r.status_code in (200, 201) else (False, f"Failed: {r.text[:200]}")
    except Exception as e:
        return False, f"Failed: {e}"


def set_manual_month(email: str, month: int) -> bool:
    if not _sb_available():
        return False
    url, key = _sb_creds()
    try:
        r = requests.patch(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key),
                            params={"email": f"eq.{email}"}, json={"manual_month_override": month}, timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False


def current_month(enrollment: dict) -> int:
    if not enrollment:
        return 0
    if enrollment.get("manual_month_override"):
        return min(12, max(1, int(enrollment["manual_month_override"])))
    start = datetime.date.fromisoformat(enrollment["start_date"])
    elapsed_days = (datetime.date.today() - start).days
    month = max(1, elapsed_days // 30 + 1)
    return min(12, month)


def phase_for_month(month: int):
    for phase in CURRICULUM:
        if phase["months"][0] <= month <= phase["months"][1]:
            return phase
    return None


def render_enrollment_gate() -> dict:
    """Call at the top of the Curriculum tab. Returns the enrollment row, or
    renders an enroll form and returns None if the fellow isn't enrolled yet."""
    email = st.session_state.get("auth_user", {}).get("email", "")
    if not email:
        st.warning("Log in to access the fellowship curriculum.")
        return None

    enrollment = get_enrollment(email)
    if enrollment:
        return enrollment

    st.markdown("### 📋 Enroll in the 12-month track")
    st.caption("Enrollment starts your curriculum clock — each phase unlocks in sequence from your start date.")
    with st.form("ashm_enroll_form"):
        name = st.text_input("Full name")
        start = st.date_input("Fellowship start date", value=datetime.date.today())
        go = st.form_submit_button("Enroll", type="primary")
        if go:
            if not name.strip():
                st.error("Name is required.")
            else:
                ok, msg = enroll(email, name.strip(), start)
                if ok:
                    st.success("✅ Enrolled — your curriculum is now active.")
                    st.rerun()
                else:
                    st.error(msg)
    return None


def render_curriculum_tracker(module_renderers: dict = None):
    """Renders the month-by-month tracker. `module_renderers` maps each
    phase's `route` key to a zero-arg function that renders that module —
    when a fellow opens an unlocked phase, its module renders inline right
    here, keeping the whole 12-month program as one cohesive section rather
    than scattering across separate app pages."""
    enrollment = render_enrollment_gate()
    if not enrollment:
        return

    month = current_month(enrollment)
    st.markdown(
        f"<div style='background:linear-gradient(135deg,{NAVY},{BLUE});color:#fff;"
        f"border-radius:14px;padding:1rem 1.4rem;margin-bottom:1rem;'>"
        f"<b>{enrollment['name']}</b> — Month {month} of 12"
        f"</div>", unsafe_allow_html=True,
    )

    is_faculty = st.session_state.get("auth_user", {}).get("role", "") in ("faculty", "admin")
    if is_faculty:
        with st.expander("👨‍🏫 Faculty: adjust this fellow's month"):
            new_month = st.slider("Current month", 1, 12, month, key="ashm_month_override")
            if st.button("Apply override"):
                set_manual_month(enrollment["email"], new_month)
                st.rerun()

    module_renderers = module_renderers or {}
    open_key = st.session_state.get("ashm_open_module")

    for phase in CURRICULUM:
        lo, hi = phase["months"]
        if hi < month:
            status, color, badge = "completed", GREEN, "✅ Completed"
        elif lo <= month <= hi:
            status, color, badge = "current", TEAL, "▶ Current phase"
        else:
            status, color, badge = "locked", MUTED, "🔒 Locked"

        dept = f" · {phase['dept']}" if phase["dept"] else ""
        st.markdown(
            f"<div style='border:1px solid {BORDER};border-left:5px solid {color};"
            f"border-radius:8px;background:{SURFACE};padding:12px 16px;margin-bottom:6px;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
            f"<div><b style='color:{TEXT}'>Months {lo}–{hi} · {phase['title']}</b>{dept}<br>"
            f"<span style='color:{MUTED};font-size:.85rem'>→ {phase['skill']}</span></div>"
            f"<div style='color:{color};font-weight:700;font-size:.85rem;white-space:nowrap;'>{badge}</div>"
            f"</div></div>", unsafe_allow_html=True,
        )
        if status in ("current", "completed") and phase["route"] in module_renderers:
            if st.button(phase["route_label"], key=f"ashm_open_{phase['key']}"):
                st.session_state.ashm_open_module = phase["route"]
                st.rerun()
        st.write("")

    if open_key and open_key in module_renderers:
        st.markdown("---")
        st.markdown(f"## {next((p['title'] for p in CURRICULUM if p['route'] == open_key), '')}")
        if st.button("← Back to curriculum overview"):
            st.session_state.pop("ashm_open_module", None)
            st.rerun()
        module_renderers[open_key]()
