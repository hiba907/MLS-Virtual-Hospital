"""
medsim_multipatient.py
────────────────────────────────────────────────────────────────────────────
Multi-Patient Caseload board (ASHM Fellowship, Section 4.1 / Months 1-2).

Rebuilt on medsim_shared_state.py so this actually works across devices:
  - Admin/faculty: runs the real DeteriorationEngine, admits patients (one
    at a time or via a saved case combo from ashm_case_combo.py), and after
    every tick pushes the resulting state to Supabase — the single source
    of truth.
  - Everyone else (students): never touches the engine. They poll the
    shared state and render the same board read-only, firing their own
    local pager notification the moment they see a new patient or a status
    that got worse since their last poll.

This does not modify deterioration.py, medsim_case_library.py, or
ashm_case_combo.py — it composes them.
"""

import time
import streamlit as st

from deterioration import DeteriorationEngine, CASES
from medsim_case_library import list_custom_cases, row_to_case
from medsim_pager import request_pager_permission, fire_pager_alert
from medsim_code_blue import is_arrest_rhythm
from medsim_shared_state import push_room_state, pull_active_rooms, discharge_room
from ashm_case_combo import render_combo_builder, render_combo_list_with_release

WORSE_STATES = ("critical", "ARREST")


def _is_admin() -> bool:
    return st.session_state.get("auth_user", {}).get("role", "") in ("admin", "faculty")


def _get_engine() -> DeteriorationEngine:
    if "medsim_mp_engine" not in st.session_state:
        st.session_state.medsim_mp_engine = DeteriorationEngine()
    return st.session_state.medsim_mp_engine


def _start_room(engine: DeteriorationEngine, room_id: str, case_id: str, custom_rows: dict):
    if case_id in CASES:
        engine.start_case(room_id, case_id)
    else:
        from deterioration import Vitals
        case_obj = row_to_case(custom_rows[case_id])
        bv = case_obj.baseline_vitals
        engine.active_rooms[room_id] = {
            "case_id": case_id, "case": case_obj,
            "vitals": Vitals(hr=bv.hr, bp_sys=bv.bp_sys, bp_dia=bv.bp_dia,
                              spo2=bv.spo2, rr=bv.rr, temp=bv.temp,
                              etco2=bv.etco2, rhythm=bv.rhythm),
            "start_time": time.time(), "current_phase": 0, "status": "stable",
            "alerts": [], "actions": [], "patient": case_obj.patient.copy(),
            "occupied": False, "occupied_by": None,
        }


def _status_color(status: str) -> str:
    return {"stable": "#059669", "deteriorating": "#d97706",
            "critical": "#dc2626", "arrest": "#dc2626"}.get(status, "#6b7280")


def _render_board(rows: list):
    """Shared rendering for both admin and student views, from the shared
    state rows pulled out of Supabase."""
    if not rows:
        st.info("No active patients right now.")
        return

    st.markdown(f"### Active caseload — {len(rows)} patient(s)")
    cols = st.columns(min(3, len(rows)) or 1)
    seen = st.session_state.setdefault("mp_seen_status", {})

    for i, row in enumerate(rows):
        room_id, bed_label = row["room_id"], row["bed_label"]
        status = row.get("status", "stable")
        rhythm = row.get("rhythm", "")
        color = _status_color(status)
        if is_arrest_rhythm(rhythm):
            status, color = "ARREST", "#dc2626"

        prior = seen.get(room_id)
        if prior is None:
            fire_pager_alert(f"New patient — {bed_label}", row.get("case_name", ""), urgency="routine")
        elif prior != status and status in WORSE_STATES:
            fire_pager_alert(f"{bed_label} deteriorating", f"Now: {status}", urgency="critical")
        seen[room_id] = status

        col = cols[i % len(cols)]
        with col:
            v = row.get("vitals", {}) or {}
            st.markdown(
                f"<div style='border-left:5px solid {color};border-radius:6px;"
                f"padding:10px 14px;background:rgba(255,255,255,.03);'>"
                f"<b>{bed_label}</b> — {row.get('case_name','')}<br>"
                f"<span style='color:{color};font-weight:700'>{status.upper()}</span><br>"
                f"<span style='font-size:.85rem'>HR {v.get('hr','—')} · "
                f"BP {v.get('bp','—')} · SpO2 {v.get('spo2','—')}% · Rhythm {rhythm}</span>"
                f"</div>", unsafe_allow_html=True,
            )
            st.caption(row.get("current_message", ""))
            if _is_admin():
                if st.button("Discharge", key=f"mp_disc_{room_id}", use_container_width=True):
                    discharge_room(room_id)
                    engine = st.session_state.get("medsim_mp_engine")
                    if engine:
                        engine.stop_case(room_id)
                    st.session_state.get("mp_known_rooms", {}).pop(room_id, None)
                    st.rerun()


def page_multipatient_board():
    st.markdown("## 🏥 Multi-Patient Caseload")
    st.caption("ASHM Fellowship — Months 1–2 · Manage several simultaneous patients "
               "under time pressure. Shared across every device — everyone sees the "
               "same board and gets paged in real time.")

    request_pager_permission()
    email = st.session_state.get("auth_user", {}).get("email", "unknown")
    admin = _is_admin()

    if not admin:
        st.caption("👁 Read-only view — patients are admitted by an instructor/admin.")
        rows = pull_active_rooms()
        _render_board(rows)
        time.sleep(3)
        st.rerun()
        return

    # ── Admin/faculty view ────────────────────────────────────────────────
    engine = _get_engine()
    custom_rows = {c["case_id"]: c for c in list_custom_cases()}
    all_case_ids = list(CASES.keys()) + list(custom_rows.keys())

    def _fmt(cid):
        return f"📖 {CASES[cid].name}" if cid in CASES else f"✍️ {custom_rows[cid]['name']} (custom)"

    known = st.session_state.setdefault("mp_known_rooms", {})

    with st.expander("🚀 Release a case combo (multiple patients at once)"):
        render_combo_builder(all_case_ids, _fmt)
        st.markdown("---")

        def _release(combo):
            names = []
            for j, cid in enumerate(combo["case_ids"]):
                bed = f"Combo-{combo['name'][:8]}-{j+1}"
                room_id = f"mp_{bed.lower().replace(' ', '_')}"
                _start_room(engine, room_id, cid, custom_rows)
                known[room_id] = bed
                names.append(_fmt(cid))
            fire_pager_alert(f"🚨 {combo['name']} — {len(combo['case_ids'])} new patients",
                              combo.get("urgency_note") or ", ".join(names), urgency="critical")
            st.rerun()

        render_combo_list_with_release(_release)

    st.markdown("### Admit a single patient")
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        bed = st.text_input("Bed / room label", placeholder="e.g. Bed 3", key="mp_bed")
    with c2:
        case_id = st.selectbox("Case", all_case_ids, format_func=_fmt, key="mp_case")
    with c3:
        st.write(""); st.write("")
        if st.button("➕ Admit", type="primary", use_container_width=True):
            if bed.strip():
                room_id = f"mp_{bed.strip().lower().replace(' ', '_')}"
                _start_room(engine, room_id, case_id, custom_rows)
                known[room_id] = bed.strip()
                fire_pager_alert(f"New patient — {bed.strip()}", _fmt(case_id), urgency="routine")
                st.rerun()
            else:
                st.warning("Give the bed a label first.")

    st.markdown("---")

    # Tick every locally-known room and push the result to shared state —
    # this session is the sole authority for these rooms.
    for room_id, bed_label in list(known.items()):
        state = engine.tick(room_id)
        if state is None:
            known.pop(room_id, None)
            continue
        cid = state.get("case_id", "")
        case_label = _fmt(cid) if cid in CASES else custom_rows.get(cid, {}).get("name", "Custom case")
        push_room_state(room_id, bed_label, case_label, state, email)

    rows = pull_active_rooms()
    _render_board(rows)

    time.sleep(2)
    st.rerun()
