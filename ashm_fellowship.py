"""
ashm_fellowship.py
────────────────────────────────────────────────────────────────────────────
Fellowship in AI-Simulated Hospital Medicine — its own section, separate
from (but built on top of) MedSim Room / Multi-Patient Caseload / the case
library. Nothing here modifies those files; it composes them.

Colors are pulled from app.py's own :root CSS custom properties (see the
NAVY/BLUE/TEAL/... constants) so this section visually matches the rest of
the hospital rather than introducing a new palette.

Requires one new Supabase table for applications (same project as vh_users):

    create table vh_fellowship_applications (
      id            bigint generated always as identity primary key,
      applicant_email text,
      applicant_name   text,
      specialties_completed jsonb,
      reflection             text,
      status                   text default 'pending',
      created_at                timestamp default now()
    );

(medsim_case_intake.py's vh_case_intake table, and ashm_curriculum.py's
vh_fellowship_enrollment table, are also required — see those files'
docstrings for the exact CREATE TABLE statements. The AI-Auditing, Peer
Teaching, and Population Health modules each need their own tables too —
see ashm_ai_audit.py, ashm_peer_teaching.py.)
"""

import requests
import streamlit as st
from medsim_multipatient import page_multipatient_board
from medsim_pager import request_pager_permission
from medsim_case_library import render_case_author_ui
from ashm_curriculum import render_curriculum_tracker
from ashm_handoff import page_handoff_tracker
from ashm_ai_audit import page_ai_audit
from ashm_peer_teaching import page_peer_teaching
from ashm_population_health import page_population_health

NAVY, BLUE, TEAL, TEAL_LT = "#0a2540", "#1a4f8a", "#0e7490", "#0ea5e9"
GREEN, AMBER, RED, PURPLE = "#059669", "#d97706", "#dc2626", "#7c3aed"
BG, SURFACE, BORDER, TEXT, MUTED = "#f0f4f8", "#ffffff", "#e2e8f0", "#0f172a", "#64748b"

APP_TABLE = "vh_fellowship_applications"


def _sb_creds():
    return st.secrets.get("SUPABASE_URL", ""), st.secrets.get("SUPABASE_KEY", "")


def _sb_available() -> bool:
    url, key = _sb_creds()
    return bool(url and key and not url.startswith("YOUR_"))


def _sb_headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation"}


def _submit_application(row: dict) -> tuple:
    if not _sb_available():
        return False, "Supabase not configured."
    url, key = _sb_creds()
    try:
        r = requests.post(f"{url}/rest/v1/{APP_TABLE}", headers=_sb_headers(key), json=row, timeout=10)
        return (True, "Submitted.") if r.status_code in (200, 201) else (False, f"Failed: {r.text[:200]}")
    except Exception as e:
        return False, f"Failed: {e}"


def _header():
    st.markdown(
        f"<div style='background:linear-gradient(135deg,{NAVY} 0%,{BLUE} 55%,{TEAL} 100%);"
        f"color:#fff;border-radius:14px;padding:1.4rem 1.6rem;margin-bottom:1.2rem;'>"
        f"<div style='font-size:.75rem;letter-spacing:1.5px;opacity:.8;text-transform:uppercase;'>"
        f"MLS Academy · Virtual Hospital</div>"
        f"<h1 style='margin:.3rem 0 0;font-size:1.7rem;'>Fellowship in AI-Simulated Hospital Medicine</h1>"
        f"<div style='opacity:.85;margin-top:.4rem;font-size:.95rem;'>"
        f"A 12-month advanced fellowship built inside the hospital you already use.</div>"
        f"</div>", unsafe_allow_html=True,
    )


def _card(title: str, body_html: str):
    st.markdown(
        f"<div style='background:{SURFACE};border:1px solid {BORDER};border-radius:14px;"
        f"padding:1.2rem 1.4rem;margin-bottom:1rem;'>"
        f"<h4 style='color:{NAVY};margin-top:0;'>{title}</h4>{body_html}</div>",
        unsafe_allow_html=True,
    )


def _bullets(items: list) -> str:
    lis = "".join(f"<li style='margin-bottom:6px;color:{TEXT}'>{i}</li>" for i in items)
    return f"<ul style='padding-left:1.2rem;margin:0;'>{lis}</ul>"


def _render_overview():
    st.markdown("### A 12-month fellowship built inside the hospital you already use")
    st.caption("Not a new specialty. A new responsibility: running multiple patients at "
               "once, checking the AI's diagnoses, teaching junior students, and leaving "
               "behind a case that outlives your cohort.")

    _card("1. Executive Summary",
          f"<p style='color:{TEXT}'>The Fellowship in AI-Simulated Hospital Medicine (ASHM) is a "
          f"proposed 12-month advanced training program built entirely within the MLS Academy "
          f"Virtual Hospital. It is designed for high-performing students who have already "
          f"completed core clinical modules and are ready for a level of responsibility beyond "
          f"single-case practice: managing multiple patients simultaneously, auditing AI-driven "
          f"diagnostic reasoning, teaching junior peers, and contributing original clinical "
          f"content back to the hospital.</p>"
          f"<p style='color:{TEXT}'>Unlike organ-based fellowships (cardiology, gastroenterology) "
          f"that require physical instrumentation MLS does not have, ASHM is built around a "
          f"competency that only an AI-simulation environment can teach: operating, evaluating, "
          f"and improving a virtual hospital system — a genuinely original credential rather "
          f"than an imitation of traditional clinical fellowships.</p>")

    _card("2. Why This Fellowship", _bullets([
        "No existing fellowship trains fellows specifically to operate and improve an "
        "AI-simulated hospital — this is a new category, not a virtual copy of an existing one.",
        "It uses MLS Academy's actual strengths (AI simulation, breadth of case exposure, "
        "existing student data) rather than attempting to replicate physical clinical "
        "training MLS cannot offer.",
        "It produces a lasting institutional asset: each cohort's capstone cases "
        "permanently expand the hospital's teaching library.",
        "It creates a credential MLS Academy can own and standardize, positioning the "
        "academy as a category leader in AI-simulated medical education.",
    ]))

    st.markdown("#### 3. Program Structure — 12 Months")
    phases = [
        ("01", "Multi-Patient Caseload", "Months 1–2 · Internal Medicine + ER",
         "Manage 5 simultaneous virtual patients, prioritizing care under time pressure — real-time triage.",
         "Triage & prioritization under pressure"),
        ("02", "Cross-Department Handoff", "Months 3–4 · ICU + Surgery",
         "Follow one patient's full journey — admission, ICU, post-op — coordinating handoffs between departments.",
         "Continuity-of-care management"),
        ("03", "AI Auditing", "Months 5–6 · Cross-specialty",
         "Review cases where the AI's diagnosis is deliberately flawed; identify the error and propose a correction.",
         "Critical evaluation of AI-driven diagnosis"),
        ("04", "Peer Teaching & Supervision", "Months 7–8",
         "Supervise 3–5 junior students, review their case decisions, and lead mock morning rounds.",
         "Clinical teaching & leadership"),
        ("05", "Population Health View", "Months 9–10",
         "Analyze aggregated outcomes across hundreds of simulated cases (e.g. diagnostic accuracy by condition).",
         "Population-level clinical reasoning"),
        ("06", "Capstone: New Case Design", "Months 11–12",
         "Design and validate an original AI-simulated patient case for permanent inclusion in the MLS hospital library.",
         "Case authorship & lasting contribution"),
    ]
    st.markdown(f"<div style='background:{SURFACE};border:1px solid {BORDER};border-radius:14px;"
                f"padding:1.2rem 1.4rem;margin-bottom:1rem;'>", unsafe_allow_html=True)
    for num, title, sub, does, skill in phases:
        st.markdown(
            f"<div style='display:flex;gap:14px;padding:10px 0;border-bottom:1px solid {BORDER};'>"
            f"<div style='color:{TEAL};font-weight:800;font-size:.85rem;min-width:24px;'>{num}</div>"
            f"<div><b style='color:{TEXT}'>{title}</b><br>"
            f"<span style='color:{MUTED};font-size:.8rem'>{sub}</span><br>"
            f"<span style='color:{TEXT};font-size:.85rem'>{does}</span><br>"
            f"<span style='color:{TEAL};font-size:.8rem;font-weight:600'>→ {skill}</span></div></div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("#### 4. Technical Innovations")
    _card("4.1 Simultaneous Multi-Patient Caseload",
          f"<p style='color:{TEXT}'>Rather than developing new medical content, the fellowship "
          f"reorganizes MLS's existing case library. Cases already tagged by specialty and "
          f"acuity are released to the fellow simultaneously — for example, five cases from "
          f"different departments arriving together — requiring the fellow to prioritize, "
          f"sequence, and manage care across all of them at once, mirroring a real hospital "
          f"shift rather than an isolated case study. <i>Live in the Curriculum tab, Months 1–2.</i></p>")
    _card("4.2 Virtual \"Pager\" Alert System",
          f"<p style='color:{TEXT}'>A notification system alerts fellows in real time when a "
          f"new simulated patient arrives, even when they are away from the platform — via "
          f"push notification, SMS, or WhatsApp alert. Alerts carry urgency information (e.g. "
          f"a single routine case vs. multiple critical arrivals), and response time becomes a "
          f"measurable part of the fellow's performance record. <i>Browser push is live in the "
          f"Pager Alerts tab today, at zero cost; SMS/WhatsApp are scoped for a future phase.</i></p>")

    _card("5. Eligibility and Application", _bullets([
        "Open to students who have completed a minimum number of core modules across at "
        "least three specialties within the MLS Virtual Hospital.",
        "Eligibility is partly evaluated using data already generated by the platform: "
        "diagnostic accuracy, case completion rate, and decision-time metrics.",
        "Formal application includes a short written reflection (e.g. a case where the "
        "fellow disagreed with the AI's diagnosis) and faculty review.",
        "Cohorts are intentionally capped (10–20 fellows) to preserve the credential's selectivity.",
    ]))

    _card("6. Credential",
          f"<p style='color:{TEXT}'>Graduates are awarded the title <b>\"Fellow in "
          f"AI-Simulated Hospital Medicine, MLS Academy,\"</b> reflecting certified "
          f"competency in multi-patient prioritization, AI-diagnostic evaluation, clinical "
          f"teaching, and simulated case authorship — skills that extend beyond any single "
          f"specialty.</p>")


def _render_accreditation_partners():
    st.markdown("### 7. Accreditation and Partnership Path")
    st.caption("Because MLS Academy operates as an educational and simulation-based "
               "institution rather than a physical clinical site, this program is not "
               "positioned for procedural/organ-based accreditation bodies (e.g. ACGME). "
               "Instead, MLS Academy is pursuing recognition through the following channels:")
    _card("Recognition channels", _bullets([
        "Registration and recognition through the Lebanese Ministry of Education, as an "
        "accredited advanced educational program.",
        "Simulation-specific accreditation aligned with recognized standards for "
        "healthcare simulation education.",
        "Partnership with established institutions and academic organizations willing to "
        "co-sponsor, validate, or lend academic credibility to the program.",
        "Collaboration opportunities with organizations such as The Frank Foundation / "
        "NextGenU.org, building on ongoing discussions regarding public health curriculum "
        "cooperation.",
    ]))

    st.markdown("### 8. Call for Partners")
    st.caption("MLS Academy is inviting institutions, accreditation bodies, and individuals "
               "with relevant expertise to support the development, review, or "
               "co-sponsorship of this fellowship. Areas where collaboration is especially "
               "welcome include curriculum validation, simulation accreditation guidance, "
               "and institutional co-sponsorship for formal recognition.")


def _render_apply():
    st.markdown("### Apply to the Fellowship")
    st.caption("Cohorts are intentionally capped (10–20 fellows) to preserve the credential's selectivity.")
    with st.form("ashm_apply_form"):
        name = st.text_input("Full name")
        email = st.text_input("Email")
        specialties = st.multiselect(
            "Core specialties completed",
            ["Internal Medicine", "Emergency", "ICU", "Surgery", "Cardiology",
             "Pediatrics", "OB/GYN", "Psychiatry", "Other"],
        )
        reflection = st.text_area(
            "Short written reflection",
            placeholder="Describe a case where you disagreed with the AI's diagnosis, and why.",
            height=160,
        )
        go = st.form_submit_button("Submit Application", type="primary")
        if go:
            if not (name.strip() and email.strip() and reflection.strip()):
                st.error("Name, email, and reflection are required.")
            elif len(specialties) < 3:
                st.error("At least three completed specialties are required for eligibility.")
            else:
                ok, msg = _submit_application({
                    "applicant_email": email.strip(), "applicant_name": name.strip(),
                    "specialties_completed": specialties, "reflection": reflection.strip(),
                    "status": "pending",
                })
                st.success("✅ Application submitted — faculty review to follow.") if ok else st.error(msg)


def _render_pager_alerts_tab():
    st.markdown("### 📟 Pager Alerts")
    st.caption("Enable browser notifications to be paged the moment a new patient arrives "
               "or an active one deteriorates, even while you're on another tab.")
    request_pager_permission()
    st.info("Pager alerts fire automatically from the Fellow Dashboard tab whenever a "
            "patient is admitted or escalates to critical/arrest. No setup needed beyond "
            "granting notification permission above.")


def page_ashm_fellowship():
    _header()
    tabs = st.tabs(["Overview", "Accreditation & Partners", "Apply", "Curriculum",
                     "Case Intake & Review", "Pager Alerts"])
    with tabs[0]:
        _render_overview()
    with tabs[1]:
        _render_accreditation_partners()
    with tabs[2]:
        _render_apply()
    with tabs[3]:
        render_curriculum_tracker({
            "medsim_multipatient": page_multipatient_board,
            "ashm_handoff": page_handoff_tracker,
            "ashm_ai_audit": page_ai_audit,
            "ashm_peer_teaching": page_peer_teaching,
            "ashm_population_health": page_population_health,
            "ashm_fellowship_author": render_case_author_ui,
        })
    with tabs[4]:
        render_intake_pipeline()
    with tabs[5]:
        _render_pager_alerts_tab()
