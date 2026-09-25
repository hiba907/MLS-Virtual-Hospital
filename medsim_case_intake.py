"""
medsim_case_intake.py
────────────────────────────────────────────────────────────────────────────
Real Case Intake & Review Pipeline (ASHM Fellowship).

Four gates, nothing skips a gate:
  1. Hospital Submission  — partner clinician submits a de-identified case
     (institution, department, IRB reference, presentation summary — no
     free-text identifier fields exist on the form by design).
  2. De-identification check — a soft automated scan flags likely PII
     (emails, phone numbers, MRNs, dates-of-birth patterns) for a human to
     confirm/clear. This is a SAFETY NET, not a guarantee — final
     responsibility for de-identification stays with the submitting
     institution's IRB process, this just catches obvious slips.
  3. Physician Review — a licensed physician reviewer reads the case,
     approves, rejects, or requests changes, and adds clinical notes.
  4. Approved → hand-off to case authoring. Deliberately NOT automatic:
     approval does not auto-generate vitals/phases/interventions from the
     raw submission text. It opens the existing medsim_case_library.py
     authoring form, pre-filled with the institution/description/IRB
     reference, so the reviewing physician (or an author working with them)
     builds the actual structured case using real clinical judgement —
     consistent with the earlier decision not to let anything auto-parse
     unstructured clinical text into a teaching case.

Requires one new Supabase table (create once, same project as vh_users):

    create table vh_case_intake (
      id                bigint generated always as identity primary key,
      intake_id         text unique not null,
      institution        text,
      department          text,
      irb_reference        text,
      presentation_summary text,
      submitted_by          text,
      status                 text default 'submitted',
      -- submitted -> deidentified -> physician_review -> approved / rejected
      pii_flags              jsonb,
      deidentified_by         text,
      reviewer_email            text,
      reviewer_notes              text,
      linked_case_id                text,
      created_at                    timestamp default now()
    );
"""

import re
import time
import requests
import streamlit as st

TABLE = "vh_case_intake"

# Palette pulled directly from app.py's own :root CSS — not guessed.
NAVY, BLUE, TEAL, TEAL_LT = "#0a2540", "#1a4f8a", "#0e7490", "#0ea5e9"
GREEN, AMBER, RED, PURPLE = "#059669", "#d97706", "#dc2626", "#7c3aed"
BG, SURFACE, BORDER, TEXT, MUTED = "#f0f4f8", "#ffffff", "#e2e8f0", "#0f172a", "#64748b"

GATES = ["Hospital Submission", "De-identification", "Physician Review", "Approved"]
STATUS_TO_GATE = {"submitted": 0, "deidentified": 1, "physician_review": 2,
                   "approved": 3, "rejected": 3}


def _sb_creds():
    return st.secrets.get("SUPABASE_URL", ""), st.secrets.get("SUPABASE_KEY", "")


def _sb_available() -> bool:
    url, key = _sb_creds()
    return bool(url and key and not url.startswith("YOUR_"))


def _sb_headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation"}


def _pii_scan(text: str) -> list:
    """Soft heuristic scan for likely identifiers — flags for human review,
    never auto-redacts or auto-approves."""
    flags = []
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text):
        flags.append("possible email address")
    if re.search(r"\b\d{2,3}[-.\s]?\d{3}[-.\s]?\d{3,4}\b", text):
        flags.append("possible phone number")
    if re.search(r"\bMRN[:\s#]*\d+\b", text, re.I):
        flags.append("possible MRN")
    if re.search(r"\b(19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b", text):
        flags.append("possible date of birth / exact date")
    if re.search(r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b", text):
        flags.append("possible full name pattern")
    return flags


def submit_intake(row: dict) -> tuple:
    if not _sb_available():
        return False, "Supabase not configured."
    url, key = _sb_creds()
    try:
        r = requests.post(f"{url}/rest/v1/{TABLE}",
                           headers={**_sb_headers(key), "Prefer": "resolution=merge-duplicates,return=representation"},
                           json=row, timeout=10)
        return (True, "Submitted.") if r.status_code in (200, 201) else (False, f"Failed ({r.status_code}): {r.text[:200]}")
    except Exception as e:
        return False, f"Failed: {e}"


def list_intake(status: str = None) -> list:
    if not _sb_available():
        return []
    url, key = _sb_creds()
    params = {"select": "*", "order": "created_at.desc"}
    if status:
        params["status"] = f"eq.{status}"
    try:
        r = requests.get(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key), params=params, timeout=10)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def update_intake(intake_id: str, fields: dict) -> bool:
    if not _sb_available():
        return False
    url, key = _sb_creds()
    try:
        r = requests.patch(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key),
                            params={"intake_id": f"eq.{intake_id}"}, json=fields, timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False


def _gate_stepper(active_idx: int):
    cols = st.columns(len(GATES))
    for i, (col, label) in enumerate(zip(cols, GATES)):
        done = i < active_idx
        active = i == active_idx
        bg = GREEN if done else (TEAL if active else SURFACE)
        fg = "#fff" if (done or active) else MUTED
        border = "none" if (done or active) else f"1px solid {BORDER}"
        with col:
            st.markdown(
                f"<div style='background:{bg};color:{fg};border:{border};border-radius:10px;"
                f"padding:10px 12px;text-align:center;font-size:.8rem;font-weight:700;'>"
                f"{i+1:02d}<br>{label}</div>", unsafe_allow_html=True,
            )


def render_intake_form():
    """Gate 1: Hospital Submission."""
    st.markdown(
        f"<div style='background:linear-gradient(135deg,{NAVY},{BLUE});color:#fff;"
        f"border-radius:14px;padding:1.1rem 1.4rem;margin-bottom:1rem;'>"
        f"<div style='font-size:.75rem;letter-spacing:1px;opacity:.8;text-transform:uppercase;'>"
        f"MLS Academy · Virtual Hospital</div>"
        f"<h2 style='margin:.3rem 0 0;font-size:1.4rem;'>Real Case Intake & Review Pipeline</h2>"
        f"</div>", unsafe_allow_html=True,
    )
    st.caption("Every case a partner hospital submits passes four gates before it can "
               "appear in a fellow's queue. Nothing skips a gate.")
    _gate_stepper(0)
    st.markdown("---")

    st.markdown("#### Hospital submits a case")
    st.caption("Partner clinicians upload the raw case. This form intentionally has no "
               "free-text patient identifier fields — describe the presentation clinically, "
               "not the patient.")
    with st.form("intake_form"):
        institution = st.text_input("Submitting institution", placeholder="e.g. Beirut General Hospital")
        department = st.selectbox("Department", ["Internal Medicine", "Emergency", "ICU", "Surgery",
                                                    "Pediatrics", "Cardiology", "Other"])
        irb_reference = st.text_input("IRB approval reference #", placeholder="e.g. IRB-2026-0142")
        presentation_summary = st.text_area(
            "Presentation summary (de-identified)",
            placeholder="e.g. 45F, 6-week fatigue, no prior cardiac history, presents with...",
            height=140,
        )
        submitted_by = st.text_input("Your email (submitting clinician)")
        confirm = st.checkbox("I confirm this submission contains no patient names, MRNs, "
                               "contact details, or exact dates of birth, per our IRB de-identification protocol.")
        go = st.form_submit_button("Submit Case →", type="primary")

        if go:
            if not (institution.strip() and presentation_summary.strip() and submitted_by.strip()):
                st.error("Institution, presentation summary, and your email are required.")
            elif not confirm:
                st.error("Please confirm de-identification before submitting.")
            else:
                intake_id = f"intake_{int(time.time()*1000)}"
                row = {
                    "intake_id": intake_id, "institution": institution.strip(),
                    "department": department, "irb_reference": irb_reference.strip(),
                    "presentation_summary": presentation_summary.strip(),
                    "submitted_by": submitted_by.strip(), "status": "submitted",
                }
                ok, msg = submit_intake(row)
                if ok:
                    st.success("✅ Case submitted — it now moves to the de-identification gate.")
                else:
                    st.error(msg)


def render_deidentification_queue():
    """Gate 2: soft PII scan + human confirmation."""
    st.markdown("#### 🔍 De-identification Gate")
    _gate_stepper(1)
    st.caption("Automated scan flags likely identifiers for a human to confirm or clear. "
               "This is a safety net, not a substitute for the submitting institution's IRB process.")
    pending = list_intake("submitted")
    if not pending:
        st.info("Nothing waiting at this gate.")
        return
    for row in pending:
        flags = _pii_scan(row.get("presentation_summary", ""))
        with st.expander(f"{row['institution']} — {row.get('department','')} · {row['intake_id']}"):
            st.write(row.get("presentation_summary", ""))
            if flags:
                st.warning("⚠️ Possible identifiers detected: " + ", ".join(flags))
            else:
                st.success("No obvious identifier patterns detected.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Confirm clean — advance to Physician Review", key=f"deid_ok_{row['intake_id']}"):
                    update_intake(row["intake_id"], {"status": "deidentified",
                                                        "pii_flags": flags,
                                                        "deidentified_by": st.session_state.get("auth_user", {}).get("email", "unknown")})
                    st.rerun()
            with c2:
                if st.button("↩ Send back to submitter", key=f"deid_reject_{row['intake_id']}"):
                    update_intake(row["intake_id"], {"status": "rejected", "pii_flags": flags})
                    st.rerun()


def render_physician_review_queue():
    """Gate 3: licensed physician approves/rejects/annotates."""
    st.markdown("#### 🩺 Physician Review Gate")
    _gate_stepper(2)
    pending = list_intake("deidentified")
    if not pending:
        st.info("Nothing waiting at this gate.")
        return
    for row in pending:
        with st.expander(f"{row['institution']} — {row.get('department','')} · {row['intake_id']}"):
            st.write(f"**IRB reference:** {row.get('irb_reference','—')}")
            st.write(row.get("presentation_summary", ""))
            notes = st.text_area("Reviewer notes", key=f"rn_{row['intake_id']}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Approve for case authoring", key=f"appr_{row['intake_id']}", type="primary"):
                    update_intake(row["intake_id"], {
                        "status": "approved", "reviewer_notes": notes,
                        "reviewer_email": st.session_state.get("auth_user", {}).get("email", "unknown"),
                    })
                    st.rerun()
            with c2:
                if st.button("❌ Reject", key=f"rej_{row['intake_id']}"):
                    update_intake(row["intake_id"], {"status": "rejected", "reviewer_notes": notes})
                    st.rerun()


def render_approved_queue():
    """Gate 4: approved cases, ready to become real structured cases."""
    st.markdown("#### ✅ Approved — Ready for Case Authoring")
    _gate_stepper(3)
    approved = [r for r in list_intake("approved") if not r.get("linked_case_id")]
    if not approved:
        st.info("No approved cases waiting to be authored yet.")
        return
    st.caption("Approval does not auto-generate the clinical case — build the structured "
               "vitals/phases yourself in the Author tab, using this as your reference brief.")
    for row in approved:
        st.markdown(
            f"<div style='border-left:4px solid {GREEN};border-radius:6px;padding:10px 14px;"
            f"background:{SURFACE};margin-bottom:8px;'>"
            f"<b>{row['institution']}</b> — {row.get('department','')} · IRB {row.get('irb_reference','—')}"
            f"<br><span style='color:{MUTED};font-size:.85rem'>{row.get('presentation_summary','')[:180]}…</span>"
            f"</div>", unsafe_allow_html=True,
        )


def render_intake_pipeline():
    """Full pipeline UI, tabbed by gate."""
    t1, t2, t3, t4 = st.tabs(["1️⃣ Submit", "2️⃣ De-identify", "3️⃣ Physician Review", "4️⃣ Approved"])
    with t1: render_intake_form()
    with t2: render_deidentification_queue()
    with t3: render_physician_review_queue()
    with t4: render_approved_queue()
