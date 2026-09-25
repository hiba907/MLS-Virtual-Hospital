"""
ashm_handoff.py
────────────────────────────────────────────────────────────────────────────
Months 3-4: Cross-Department Handoff. Reuses DeteriorationEngine for the
underlying patient (same as MedSim Room / Multi-Patient board), but frames
it as one patient's journey through department stages, requiring the fellow
to write a structured SBAR-style handoff note at each transition before the
"next department" accepts the patient.

Requires one new Supabase table:

    create table vh_handoff_notes (
      id           bigint generated always as identity primary key,
      fellow_email   text,
      room_id          text,
      from_dept          text,
      to_dept              text,
      situation              text,
      background               text,
      assessment                 text,
      recommendation               text,
      created_at                    timestamp default now()
    );
"""

import time
import requests
import streamlit as st

from deterioration import DeteriorationEngine, CASES

NAVY, BLUE, TEAL = "#0a2540", "#1a4f8a", "#0e7490"
GREEN, AMBER, RED = "#059669", "#d97706", "#dc2626"
SURFACE, BORDER, TEXT, MUTED = "#ffffff", "#e2e8f0", "#0f172a", "#64748b"

TABLE = "vh_handoff_notes"
DEPARTMENTS = ["Admission / ER", "ICU", "Post-Op / Ward"]


def _sb_creds():
    return st.secrets.get("SUPABASE_URL", ""), st.secrets.get("SUPABASE_KEY", "")


def _sb_available() -> bool:
    url, key = _sb_creds()
    return bool(url and key and not url.startswith("YOUR_"))


def _sb_headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation"}


def save_handoff_note(row: dict) -> tuple:
    if not _sb_available():
        return False, "Supabase not configured."
    url, key = _sb_creds()
    try:
        r = requests.post(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key), json=row, timeout=10)
        return (True, "Saved.") if r.status_code in (200, 201) else (False, f"Failed: {r.text[:200]}")
    except Exception as e:
        return False, f"Failed: {e}"


def list_handoff_notes(room_id: str) -> list:
    if not _sb_available():
        return []
    url, key = _sb_creds()
    try:
        r = requests.get(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key),
                          params={"select": "*", "room_id": f"eq.{room_id}", "order": "created_at.asc"}, timeout=10)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def _get_engine() -> DeteriorationEngine:
    if "ashm_handoff_engine" not in st.session_state:
        st.session_state.ashm_handoff_engine = DeteriorationEngine()
    return st.session_state.ashm_handoff_engine


def page_handoff_tracker():
    st.markdown("## 🔁 Cross-Department Handoff")
    st.caption("Months 3–4 · Follow one patient's full journey — Admission → ICU → Post-Op — "
               "writing a structured SBAR handoff at each transition.")

    engine = _get_engine()
    room_id = "ashm_handoff_1"
    email = st.session_state.get("auth_user", {}).get("email", "fellow")

    if room_id not in engine.active_rooms:
        case_id = st.selectbox("Select a patient case to follow", list(CASES.keys()),
                                format_func=lambda c: CASES[c].name)
        if st.button("▶ Admit Patient", type="primary"):
            engine.start_case(room_id, case_id)
            st.session_state.ashm_handoff_dept_idx = 0
            st.rerun()
        return

    state = engine.tick(room_id)
    dept_idx = st.session_state.get("ashm_handoff_dept_idx", 0)
    current_dept = DEPARTMENTS[dept_idx]

    st.markdown(
        f"<div style='background:linear-gradient(135deg,{NAVY},{BLUE});color:#fff;"
        f"border-radius:12px;padding:1rem 1.4rem;margin-bottom:1rem;'>"
        f"<b>{state['patient'].get('name','Patient')}</b> — currently in <b>{current_dept}</b>"
        f"</div>", unsafe_allow_html=True,
    )

    vcols = st.columns(5)
    for col, (label, key) in zip(vcols, [("HR", "hr"), ("BP", "bp"), ("SpO2", "spo2"),
                                          ("RR", "rr"), ("Rhythm", None)]):
        with col:
            st.metric(label, state["vitals"][key] if key else state["rhythm"])

    st.info(f"📋 {state['current_message']}")
    st.markdown("---")

    notes_so_far = list_handoff_notes(room_id)
    if notes_so_far:
        with st.expander(f"📄 Handoff history ({len(notes_so_far)} note(s))"):
            for n in notes_so_far:
                st.markdown(f"**{n['from_dept']} → {n['to_dept']}**  \n"
                            f"S: {n['situation']}  \nB: {n['background']}  \n"
                            f"A: {n['assessment']}  \nR: {n['recommendation']}")
                st.markdown("---")

    if dept_idx < len(DEPARTMENTS) - 1:
        next_dept = DEPARTMENTS[dept_idx + 1]
        st.markdown(f"### ✍️ Handoff note: {current_dept} → {next_dept}")
        st.caption("SBAR format — required before the patient can transfer.")
        with st.form(f"handoff_form_{dept_idx}"):
            situation = st.text_area("Situation", placeholder="Why is this patient transferring now?")
            background = st.text_area("Background", placeholder="Relevant history, course so far")
            assessment = st.text_area("Assessment", placeholder="Current clinical picture")
            recommendation = st.text_area("Recommendation", placeholder="What the receiving team should watch for / do")
            go = st.form_submit_button(f"Hand off to {next_dept} →", type="primary")
            if go:
                if not all([situation.strip(), background.strip(), assessment.strip(), recommendation.strip()]):
                    st.error("All four SBAR fields are required for a complete handoff.")
                else:
                    ok, msg = save_handoff_note({
                        "fellow_email": email, "room_id": room_id,
                        "from_dept": current_dept, "to_dept": next_dept,
                        "situation": situation.strip(), "background": background.strip(),
                        "assessment": assessment.strip(), "recommendation": recommendation.strip(),
                    })
                    if ok:
                        st.session_state.ashm_handoff_dept_idx = dept_idx + 1
                        st.success(f"✅ Handed off to {next_dept}.")
                        st.rerun()
                    else:
                        st.error(msg)
    else:
        st.success("✅ Patient journey complete — Admission → ICU → Post-Op, "
                    f"with {len(notes_so_far)} handoff notes on record.")
        if st.button("⏹ End Journey"):
            engine.stop_case(room_id)
            st.session_state.pop("ashm_handoff_dept_idx", None)
            st.rerun()

    time.sleep(2)
    st.rerun()
