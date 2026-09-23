"""
medsim_room.py
────────────────────────────────────────────────────────────────────────────
The MedSim Room: a new page inside MLS Virtual Hospital that combines,
WITHOUT MODIFYING any of them:

  • deterioration.py               → live vitals / ACLS case engine
  • medsim_anatomy_viewer.py       → Three.js anatomy explorer with zoom +
                                      landmark markers (adapted from
                                      ai-gestures--main/app.py)
  • procedure_3d_viewer_guided.py  → the hospital's existing needle/marker/
                                      phantom IV-cannulation simulation
                                      (reached via page_procedure_sim_3d())

Flow:
  1. Vitals tick every rerun (deterioration.DeteriorationEngine).
  2. When the current case Phase calls for IV access (or a vital crosses a
     hard threshold), a banner is AUTO-SUGGESTED.
  3. Student explicitly confirms — nothing launches without a click.
  4. "Explore Anatomy" opens the zoomable vein/organ viewer.
  5. "Start IV Insertion" hands off to the hospital's existing procedure
     simulator (3D needle + phantom arm), by setting the same session_state
     keys app.py's router / page_procedure_sim_3d() already reads.

Add to the existing MLS-Virtual-Hospital app.py (pure additions only):

    from medsim_room import page_medsim_room          # near other imports

    elif p == "medsim_room":                          # near other elif branches
        page_medsim_room()

And add one sidebar/nav button anywhere convenient, e.g.:

    if st.sidebar.button("🩺 MedSim Room"):
        nav("medsim_room")
"""

import time
import streamlit as st

from deterioration import DeteriorationEngine, CASES
from medsim_anatomy_viewer import render_anatomy_explorer
from medsim_code_blue import render_code_blue_overlay, is_arrest_rhythm
from medsim_cpr import render_cpr_trainer

# Reuse ONE engine instance across reruns via session_state (Streamlit reruns
# the whole script on every interaction, so the engine must not be recreated).
def _get_engine() -> DeteriorationEngine:
    if "medsim_engine" not in st.session_state:
        st.session_state.medsim_engine = DeteriorationEngine()
    return st.session_state.medsim_engine


# Vitals that, if crossed, auto-suggest IV access regardless of scripted case
# events (covers cases where the student let the patient deteriorate off-script).
def _vitals_call_for_iv(vitals: dict) -> bool:
    try:
        sys_bp = int(str(vitals["bp"]).split("/")[0])
    except Exception:
        sys_bp = 120
    return sys_bp < 90 or vitals.get("spo2", 100) < 90


def _room_needs_iv(room_state: dict) -> bool:
    if "iv_access" in [a.get("event") for a in room_state.get("alerts", [])]:
        return False  # already flagged / done this session
    msg = (room_state.get("current_message") or "").lower()
    if "iv access" in msg or "iv line" in msg or "cannula" in msg:
        return True
    return _vitals_call_for_iv(room_state["vitals"])


def _vital_css(color: str) -> str:
    return {"green": "#059669", "amber": "#d97706", "red": "#dc2626"}.get(color, "#059669")


def page_medsim_room():
    st.markdown("## 🩺 MedSim Room")
    st.caption("Live deterioration engine → anatomy explorer → guided needle/IV insertion, in one flow.")

    engine = _get_engine()
    room_id = "medsim_room_1"

    # ── Case selection / start ──────────────────────────────────────────────
    if room_id not in engine.active_rooms:
        case_id = st.selectbox("Select a case", list(CASES.keys()),
                                format_func=lambda c: CASES[c].name)
        if st.button("▶ Start Case", type="primary"):
            engine.start_case(room_id, case_id)
            st.session_state.pop("medsim_iv_dismissed", None)
            st.rerun()
        return

    state = engine.tick(room_id)

    # ── Code Blue atmosphere ─────────────────────────────────────────────────
    if "medsim_code_started_at" not in st.session_state:
        st.session_state.medsim_code_started_at = None

    auto_arrest = is_arrest_rhythm(state.get("rhythm", ""))
    if auto_arrest and st.session_state.medsim_code_started_at is None:
        st.session_state.medsim_code_started_at = time.time()

    code_active = st.session_state.medsim_code_started_at is not None
    if not code_active:
        if st.button("🚨 Call Code Blue"):
            st.session_state.medsim_code_started_at = time.time()
            st.rerun()
    else:
        elapsed = int(time.time() - st.session_state.medsim_code_started_at)
        render_code_blue_overlay(elapsed)
        cc1, cc2 = st.columns([1, 5])
        with cc1:
            if st.button("✅ End Code"):
                st.session_state.medsim_code_started_at = None
                st.rerun()

    st.markdown("---")

    # ── Vitals monitor ───────────────────────────────────────────────────────
    v, vc = state["vitals"], state["vitals_colors"]
    cols = st.columns(6)
    labels = [("HR", "hr", " bpm"), ("BP", "bp", " mmHg"), ("SpO2", "spo2", "%"),
              ("RR", "rr", "/min"), ("Temp", "temp", "°C"), ("Rhythm", None, "")]
    for col, (label, key, unit) in zip(cols, labels):
        with col:
            if key is None:
                st.markdown(f"**{label}**")
                st.markdown(f"`{state['rhythm'].upper()}`")
            else:
                color = _vital_css(vc.get(key, "green"))
                st.markdown(f"**{label}**")
                st.markdown(f"<span style='color:{color};font-size:1.3rem;font-weight:700'>{v[key]}{unit}</span>",
                            unsafe_allow_html=True)

    st.info(f"📋 {state['current_message']}")

    if state["alerts"]:
        with st.expander("Recent alerts", expanded=False):
            for a in reversed(state["alerts"]):
                st.markdown(f"`t+{a['time']}s` {a.get('message', a['event'])}")

    st.markdown("---")

    # ── Auto-suggested IV / anatomy handoff ─────────────────────────────────
    needs_iv = _room_needs_iv(state) and not st.session_state.get("medsim_iv_dismissed")

    if needs_iv:
        st.markdown(
            "<div style='background:#fef3c7;border-left:4px solid #d97706;"
            "border-radius:0 8px 8px 0;padding:12px 16px;margin-bottom:10px;'>"
            "<b>⚠️ This patient likely needs IV access.</b> "
            "Do you want to establish it now?</div>",
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🔬 Explore Anatomy", use_container_width=True):
                st.session_state.medsim_show_anatomy = True
                st.session_state.medsim_anatomy_phase_medsim = 0  # start at Overview
        with c2:
            if st.button("💉 Insert IV Now (arm + gestures)", type="primary", use_container_width=True):
                st.session_state.medsim_show_anatomy = True
                st.session_state.medsim_anatomy_phase_medsim = 3  # jump to "IV Insertion" phase
        with c3:
            if st.button("Not now", use_container_width=True):
                st.session_state.medsim_iv_dismissed = True
                st.rerun()

    # ── Anatomy explorer: arm appears on screen, pinch to zoom, click the ───
    # marker on the model to insert. This is the primary IV-access flow now.
    if st.session_state.get("medsim_show_anatomy"):
        st.markdown("### 🔬 Anatomy Explorer — Forearm / Vein Access")
        render_anatomy_explorer(organ_key="🩸 Forearm / Vein Access", height=560, key="medsim")

        if st.session_state.get("medsim_iv_done"):
            engine.intervene(room_id, "iv_access")
            st.markdown("---")
            colA, colB = st.columns(2)
            with colA:
                if st.button("🩹 Detailed guided walkthrough (drag-and-drop, optional)", use_container_width=True):
                    # Existing needle/marker/phantom flow — untouched — for
                    # step-by-step practice of the fine motor technique.
                    st.session_state.proc_selected = "IV Cannulation"
                    st.session_state.proc_step = 0
                    st.session_state.page = "procedures"
                    st.rerun()
            with colB:
                if st.button("✅ Done — back to vitals", use_container_width=True):
                    st.session_state.medsim_show_anatomy = False
                    st.session_state.pop("medsim_iv_done", None)
                    st.rerun()

    st.markdown("---")

    # ── CPR trainer, auto-suggested during an active code ────────────────────
    if code_active:
        if st.session_state.get("medsim_show_cpr"):
            render_cpr_trainer()
            if st.button("✅ Done with CPR — back to code"):
                st.session_state.medsim_show_cpr = False
                st.rerun()
            st.markdown("---")
        else:
            if st.button("💗 Start Cardiac Massage (CPR)", type="primary"):
                st.session_state.medsim_show_cpr = True
                st.rerun()

    if st.button("⏹ End Case"):
        result = engine.stop_case(room_id)
        st.session_state.pop("medsim_show_anatomy", None)
        st.session_state.pop("medsim_iv_dismissed", None)
        st.session_state.pop("medsim_code_started_at", None)
        st.session_state.pop("medsim_show_cpr", None)
        st.session_state.pop("medsim_cpr_tier", None)
        st.success(f"Case ended. Score: {result['final_score']} · "
                   f"Correct interventions: {result['correct_interventions']}")

    # Live tick loop (rerun every ~2s while a case is active so vitals move
    # without extra clicks). Comment out if you prefer manual/button-driven ticking.
    time.sleep(2)
    st.rerun()
