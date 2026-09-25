"""
ashm_peer_teaching.py
────────────────────────────────────────────────────────────────────────────
Months 7-8: Peer Teaching & Supervision.

WHO / WHAT / WHERE, made explicit (this was underspecified before):
  - WHO: each fellow supervises a defined roster of up to 5 named junior
    students (any hospital user with role="student"), not an open queue
    anyone can dump into. The fellow adds specific students by email in
    "My Mentees" below.
  - WHAT: mentees log real case decisions they made elsewhere in the
    hospital (which case, what they decided, why) for their assigned
    fellow — and only their assigned fellow — to review and give feedback on.
  - WHERE: this module, reached from ASHM Fellowship → Curriculum →
    Months 7–8, once a fellow has added at least one mentee.

Junior "submissions" are self-reported by students (there's no existing
shared diagnosis-submission table elsewhere in the hospital to hook into
instead) — a student logs a case decision, and only the fellow they're
assigned to sees and reviews it. If the hospital later adds a real shared
diagnosis-submission log, this module can be pointed at that instead with
no change to the review UI.

Requires four Supabase tables:

    create table vh_fellow_mentees (
      id            bigint generated always as identity primary key,
      fellow_email    text not null,
      student_email     text not null,
      added_at            timestamp default now(),
      unique (fellow_email, student_email)
    );

    create table vh_junior_submissions (
      id            bigint generated always as identity primary key,
      student_email   text,
      fellow_email      text,
      case_description    text,
      decision_made         text,
      reasoning                text,
      status                     text default 'pending',
      -- pending -> reviewed
      created_at                  timestamp default now()
    );

    create table vh_supervision_feedback (
      id             bigint generated always as identity primary key,
      submission_id    bigint,
      fellow_email       text,
      feedback              text,
      created_at              timestamp default now()
    );

    create table vh_morning_rounds (
      id           bigint generated always as identity primary key,
      fellow_email   text,
      round_date       date,
      notes              text,
      attendees            jsonb,
      created_at             timestamp default now()
    );
"""

import datetime
import requests
import streamlit as st

NAVY, BLUE, TEAL = "#0a2540", "#1a4f8a", "#0e7490"
GREEN, AMBER, RED = "#059669", "#d97706", "#dc2626"
SURFACE, BORDER, TEXT, MUTED = "#ffffff", "#e2e8f0", "#0f172a", "#64748b"

MENTEE_TABLE = "vh_fellow_mentees"
SUBMIT_TABLE = "vh_junior_submissions"
FEEDBACK_TABLE = "vh_supervision_feedback"
ROUNDS_TABLE = "vh_morning_rounds"
MAX_MENTEES = 5


def _sb_creds():
    return st.secrets.get("SUPABASE_URL", ""), st.secrets.get("SUPABASE_KEY", "")


def _sb_available() -> bool:
    url, key = _sb_creds()
    return bool(url and key and not url.startswith("YOUR_"))


def _sb_headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation"}


def _post(table, row):
    if not _sb_available():
        return False, "Supabase not configured."
    url, key = _sb_creds()
    try:
        r = requests.post(f"{url}/rest/v1/{table}", headers=_sb_headers(key), json=row, timeout=10)
        return (True, "Saved.") if r.status_code in (200, 201) else (False, f"Failed: {r.text[:200]}")
    except Exception as e:
        return False, f"Failed: {e}"


def _get(table, params):
    if not _sb_available():
        return []
    url, key = _sb_creds()
    try:
        r = requests.get(f"{url}/rest/v1/{table}", headers=_sb_headers(key), params=params, timeout=10)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def _patch(table, match_params, fields):
    if not _sb_available():
        return False
    url, key = _sb_creds()
    try:
        r = requests.patch(f"{url}/rest/v1/{table}", headers=_sb_headers(key), params=match_params, json=fields, timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False


def _delete(table, params):
    if not _sb_available():
        return False
    url, key = _sb_creds()
    try:
        r = requests.delete(f"{url}/rest/v1/{table}", headers=_sb_headers(key), params=params, timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False


def _my_mentees(fellow_email: str) -> list:
    rows = _get(MENTEE_TABLE, {"select": "*", "fellow_email": f"eq.{fellow_email}"})
    return [r["student_email"] for r in rows]


def _my_fellows(student_email: str) -> list:
    rows = _get(MENTEE_TABLE, {"select": "*", "student_email": f"eq.{student_email}"})
    return [r["fellow_email"] for r in rows]


def _render_mentee_roster_tab(fellow_email: str):
    st.markdown("#### 👨‍🎓 My Mentees")
    st.caption(f"Add up to {MAX_MENTEES} junior students to supervise. Only students on "
               f"this roster can submit case decisions to you, and you'll only see theirs.")
    mentees = _my_mentees(fellow_email)

    with st.form("add_mentee_form", clear_on_submit=True):
        new_email = st.text_input("Add a student by email")
        go = st.form_submit_button("➕ Add Mentee")
        if go:
            if len(mentees) >= MAX_MENTEES:
                st.error(f"Roster is full ({MAX_MENTEES} max). Remove someone first.")
            elif not new_email.strip():
                st.error("Enter a student email.")
            elif new_email.strip().lower() in mentees:
                st.warning("Already on your roster.")
            else:
                ok, msg = _post(MENTEE_TABLE, {"fellow_email": fellow_email,
                                                "student_email": new_email.strip().lower()})
                st.success("✅ Added.") if ok else st.error(msg)
                st.rerun()

    if mentees:
        for m in mentees:
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"- {m}")
            if c2.button("Remove", key=f"rm_mentee_{m}"):
                _delete(MENTEE_TABLE, {"fellow_email": f"eq.{fellow_email}", "student_email": f"eq.{m}"})
                st.rerun()
    else:
        st.info("No mentees yet — add students above to start supervising them.")


def _render_student_submit_tab(student_email: str):
    st.markdown("#### Log a case decision for your fellow-mentor")
    fellows = _my_fellows(student_email)
    if not fellows:
        st.warning("You haven't been added as a mentee by a fellow yet — ask your fellow "
                   "to add your email in their 'My Mentees' tab first.")
        return
    fellow = st.selectbox("Submitting to", fellows) if len(fellows) > 1 else fellows[0]
    if len(fellows) == 1:
        st.caption(f"Submitting to: **{fellow}**")

    with st.form("junior_submit_form"):
        case_desc = st.text_area("Case description")
        decision = st.text_input("Decision you made")
        reasoning = st.text_area("Your reasoning")
        go = st.form_submit_button("Submit for Review", type="primary")
        if go:
            if not all([case_desc.strip(), decision.strip(), reasoning.strip()]):
                st.error("All fields are required.")
            else:
                ok, msg = _post(SUBMIT_TABLE, {
                    "student_email": student_email, "fellow_email": fellow,
                    "case_description": case_desc.strip(),
                    "decision_made": decision.strip(), "reasoning": reasoning.strip(),
                })
                st.success(f"✅ Submitted to {fellow} for review.") if ok else st.error(msg)


def _render_review_queue_tab(fellow_email: str):
    st.markdown("#### Review queue — your mentees only")
    mentees = _my_mentees(fellow_email)
    if not mentees:
        st.info("Add mentees in the 'My Mentees' tab to start receiving submissions.")
        return
    pending = _get(SUBMIT_TABLE, {"select": "*", "status": "eq.pending",
                                   "fellow_email": f"eq.{fellow_email}", "order": "created_at.asc"})
    if not pending:
        st.info("Nothing pending review from your mentees right now.")
        return
    for sub in pending:
        with st.expander(f"{sub['student_email']} — Submission #{sub['id']}"):
            st.markdown(f"**Case:** {sub['case_description']}")
            st.markdown(f"**Decision:** {sub['decision_made']}")
            st.markdown(f"**Reasoning:** {sub['reasoning']}")
            feedback = st.text_area("Your feedback", key=f"fb_{sub['id']}")
            if st.button("Send feedback & mark reviewed", key=f"fb_btn_{sub['id']}"):
                if not feedback.strip():
                    st.error("Feedback is required.")
                else:
                    _post(FEEDBACK_TABLE, {"submission_id": sub["id"], "fellow_email": fellow_email,
                                            "feedback": feedback.strip()})
                    _patch(SUBMIT_TABLE, {"id": f"eq.{sub['id']}"}, {"status": "reviewed"})
                    st.rerun()


def _render_rounds_tab(fellow_email: str):
    st.markdown("#### Log a mock morning round")
    st.caption("Attendees should be your mentees, but any names can be logged.")
    with st.form("rounds_form"):
        round_date = st.date_input("Date", value=datetime.date.today())
        attendees_raw = st.text_input("Attendees (comma-separated)",
                                       value=", ".join(_my_mentees(fellow_email)))
        notes = st.text_area("Round notes / cases discussed")
        go = st.form_submit_button("Log Round", type="primary")
        if go:
            attendees = [a.strip() for a in attendees_raw.split(",") if a.strip()]
            ok, msg = _post(ROUNDS_TABLE, {
                "fellow_email": fellow_email, "round_date": round_date.isoformat(),
                "notes": notes.strip(), "attendees": attendees,
            })
            st.success("✅ Round logged.") if ok else st.error(msg)

    st.markdown("---")
    st.markdown("#### Past rounds")
    rounds = _get(ROUNDS_TABLE, {"select": "*", "fellow_email": f"eq.{fellow_email}", "order": "round_date.desc"})
    for r in rounds[:10]:
        st.markdown(f"**{r['round_date']}** — {', '.join(r.get('attendees') or [])}")
        st.caption(r.get("notes", ""))


def page_peer_teaching():
    st.markdown("## 👥 Peer Teaching & Supervision")
    st.caption("Months 7–8 · Supervise 3–5 named junior students, review their case "
               "decisions, and lead mock morning rounds with them specifically.")
    email = st.session_state.get("auth_user", {}).get("email", "unknown")
    role = st.session_state.get("auth_user", {}).get("role", "student")

    # Any user can hold both the "fellow" (My Mentees / Review) and
    # "student" (Log a Decision) tabs, since a fellow may also be someone
    # else's mentee in a different track.
    t1, t2, t3, t4 = st.tabs(["My Mentees", "Review Queue (as Fellow)",
                               "Log a Decision (as Student)", "Morning Rounds"])
    with t1: _render_mentee_roster_tab(email)
    with t2: _render_review_queue_tab(email)
    with t3: _render_student_submit_tab(email)
    with t4: _render_rounds_tab(email)
