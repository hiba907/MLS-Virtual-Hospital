"""
ashm_ai_audit.py
────────────────────────────────────────────────────────────────────────────
Months 5-6: AI Auditing. Fellows review cases where the platform's AI
diagnosis was deliberately seeded as flawed, must identify the error, and
propose the correct diagnosis with reasoning. Scored against a stored
correct answer written by faculty at seeding time — never generated
on-the-fly, since the whole point is a known, faculty-verified ground truth
to audit against.

Requires two new Supabase tables:

    create table vh_ai_audit_cases (
      id              bigint generated always as identity primary key,
      case_key           text unique not null,
      vignette              text not null,
      flawed_ai_diagnosis     text not null,
      flawed_ai_reasoning       text,
      correct_diagnosis           text not null,
      correct_reasoning             text not null,
      created_by                      text,
      created_at                       timestamp default now()
    );

    create table vh_ai_audit_submissions (
      id            bigint generated always as identity primary key,
      case_key        text,
      fellow_email      text,
      caught_error        boolean,
      proposed_diagnosis    text,
      rationale               text,
      submitted_at              timestamp default now()
    );
"""

import requests
import streamlit as st

NAVY, BLUE, TEAL = "#0a2540", "#1a4f8a", "#0e7490"
GREEN, AMBER, RED = "#059669", "#d97706", "#dc2626"
SURFACE, BORDER, TEXT, MUTED = "#ffffff", "#e2e8f0", "#0f172a", "#64748b"

CASES_TABLE = "vh_ai_audit_cases"
SUB_TABLE = "vh_ai_audit_submissions"


def _sb_creds():
    return st.secrets.get("SUPABASE_URL", ""), st.secrets.get("SUPABASE_KEY", "")


def _sb_available() -> bool:
    url, key = _sb_creds()
    return bool(url and key and not url.startswith("YOUR_"))


def _sb_headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation"}


def list_audit_cases() -> list:
    if not _sb_available():
        return []
    url, key = _sb_creds()
    try:
        r = requests.get(f"{url}/rest/v1/{CASES_TABLE}", headers=_sb_headers(key),
                          params={"select": "*", "order": "created_at.desc"}, timeout=10)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def save_audit_case(row: dict) -> tuple:
    if not _sb_available():
        return False, "Supabase not configured."
    url, key = _sb_creds()
    try:
        r = requests.post(f"{url}/rest/v1/{CASES_TABLE}",
                           headers={**_sb_headers(key), "Prefer": "resolution=merge-duplicates,return=representation"},
                           json=row, timeout=10)
        return (True, "Saved.") if r.status_code in (200, 201) else (False, f"Failed: {r.text[:200]}")
    except Exception as e:
        return False, f"Failed: {e}"


def submit_audit(row: dict) -> tuple:
    if not _sb_available():
        return False, "Supabase not configured."
    url, key = _sb_creds()
    try:
        r = requests.post(f"{url}/rest/v1/{SUB_TABLE}", headers=_sb_headers(key), json=row, timeout=10)
        return (True, "Submitted.") if r.status_code in (200, 201) else (False, f"Failed: {r.text[:200]}")
    except Exception as e:
        return False, f"Failed: {e}"


def _render_seed_case_form():
    st.markdown("#### ➕ Faculty: seed a new audit case")
    st.caption("Write both the flawed AI output AND the verified correct answer yourself — "
               "nothing here is auto-generated, since the ground truth has to be faculty-certain.")
    with st.form("ashm_seed_audit"):
        case_key = st.text_input("Case key (unique)", placeholder="e.g. audit_pe_missed_1")
        vignette = st.text_area("Patient vignette shown to the fellow", height=120)
        flawed_dx = st.text_input("AI's (flawed) diagnosis")
        flawed_reasoning = st.text_area("AI's (flawed) reasoning shown to the fellow", height=80)
        correct_dx = st.text_input("Correct diagnosis")
        correct_reasoning = st.text_area("Correct reasoning (revealed after submission)", height=100)
        go = st.form_submit_button("Save Audit Case", type="primary")
        if go:
            if not all([case_key.strip(), vignette.strip(), flawed_dx.strip(), correct_dx.strip(), correct_reasoning.strip()]):
                st.error("Case key, vignette, flawed diagnosis, correct diagnosis, and correct reasoning are required.")
            else:
                ok, msg = save_audit_case({
                    "case_key": case_key.strip(), "vignette": vignette.strip(),
                    "flawed_ai_diagnosis": flawed_dx.strip(), "flawed_ai_reasoning": flawed_reasoning.strip(),
                    "correct_diagnosis": correct_dx.strip(), "correct_reasoning": correct_reasoning.strip(),
                    "created_by": st.session_state.get("auth_user", {}).get("email", "unknown"),
                })
                st.success("✅ Audit case saved.") if ok else st.error(msg)


def page_ai_audit():
    st.markdown("## 🔍 AI Auditing")
    st.caption("Months 5–6 · Review cases where the AI's diagnosis is deliberately flawed; "
               "identify the error and propose a correction.")

    is_faculty = st.session_state.get("auth_user", {}).get("role", "") in ("faculty", "admin")
    if is_faculty:
        with st.expander("👨‍🏫 Faculty tools"):
            _render_seed_case_form()
        st.markdown("---")

    cases = list_audit_cases()
    if not cases:
        st.info("No AI-audit cases available yet. A faculty member needs to seed one above.")
        return

    email = st.session_state.get("auth_user", {}).get("email", "fellow")
    for c in cases:
        with st.expander(f"🧾 {c['case_key']}"):
            st.markdown(f"**Vignette:** {c['vignette']}")
            st.markdown(
                f"<div style='background:{AMBER}22;border-left:4px solid {AMBER};border-radius:6px;"
                f"padding:10px 14px;margin:10px 0;'>"
                f"<b>AI Diagnosis:</b> {c['flawed_ai_diagnosis']}<br>"
                f"<span style='color:{MUTED}'>{c.get('flawed_ai_reasoning','')}</span></div>",
                unsafe_allow_html=True,
            )
            result_key = f"audit_result_{c['case_key']}"
            if result_key in st.session_state:
                caught = st.session_state[result_key]
                if caught:
                    st.success(f"✅ Correct — the actual diagnosis is **{c['correct_diagnosis']}**")
                else:
                    st.error(f"❌ Not quite — the actual diagnosis is **{c['correct_diagnosis']}**")
                st.caption(c["correct_reasoning"])
            else:
                with st.form(f"audit_form_{c['case_key']}"):
                    agree = st.radio("Do you agree with the AI's diagnosis?", ["Agree", "Disagree"], key=f"agree_{c['case_key']}")
                    proposed = st.text_input("Your proposed diagnosis (if you disagree)")
                    rationale = st.text_area("Your rationale")
                    go = st.form_submit_button("Submit Audit")
                    if go:
                        caught = (agree == "Disagree" and
                                  proposed.strip().lower() == c["correct_diagnosis"].strip().lower())
                        submit_audit({
                            "case_key": c["case_key"], "fellow_email": email,
                            "caught_error": caught, "proposed_diagnosis": proposed.strip(),
                            "rationale": rationale.strip(),
                        })
                        st.session_state[result_key] = caught
                        st.rerun()
