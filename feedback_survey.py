"""
feedback_survey.py - anonymous feedback for the MLS Virtual Hospital (additive, standalone).

Two short surveys: students/residents, and professors/clinicians (e.g. Lebanese University faculty).
Real responses only. The page has three parts:
  - the survey itself (any signed-in account; one response per account, enforced with a one-way code)
  - for the OWNER only: results (counts toward the target, averages, comments, anonymity-safe breakdowns),
    an Excel/CSV export laid out like the original Student_Responses sheet, and invitation messages
  - nothing here lets anyone type or edit responses on behalf of someone else

Privacy design (see feedback_survey.sql): answers are stored with a random id and a DATE only - no name, email,
account id or time of day. A separate table keeps a one-way code (HMAC of the account) only to stop duplicates;
it has no link to a response row. Breakdowns for groups smaller than MIN_CELL respondents are hidden.

Secrets used (Streamlit Secrets): SUPABASE_URL, SUPABASE_KEY (already set); optional FEEDBACK_SALT (keeps the
one-way codes stable; if missing, a value derived from SUPABASE_KEY is used), FEEDBACK_OWNER_EMAILS
(comma-separated; if set, only these admin accounts see the results), FEEDBACK_TARGET (default 500), APP_URL.

Hook-up in app.py:  from feedback_survey import render_feedback_survey ;  render_feedback_survey()
"""
import datetime as _dt
import hashlib
import hmac
import io
import json
import re
import uuid

import requests
import streamlit as st

T = {"responses": "vh_fb_responses", "tokens": "vh_fb_tokens"}
MIN_CELL = 5
YEARS = ["Year 1", "Year 2", "Year 3", "Year 4", "Year 5", "Year 6", "Intern / Resident"]
SPECIALTIES = ["Internal Medicine", "Emergency Medicine", "Cardiology", "General Surgery", "Pediatrics",
               "Obstetrics & Gynecology", "Neurology", "Pulmonology", "Infectious Diseases", "Psychiatry", "Other"]
MODULES = ["Clinical reasoning cases", "MedSim Room", "Therapy Timeline", "Research Hub", "Case Discussions",
           "Patient Chart (daily rounds)", "Case Exam with Dr. Hiba", "Procedure / skills simulators",
           "Drug prescribing", "Other"]
HOURS = ["Less than 1 hour", "1–5 hours", "5–10 hours", "More than 10 hours"]
RECOMMEND = ["Yes", "Maybe", "No"]
FACULTY_TITLES = ["Professor", "Associate professor", "Assistant professor", "Clinical instructor / lecturer",
                  "Consultant / specialist", "Resident / fellow", "Other"]
FACULTY_HOW = ["Reviewed a demonstration", "Tried the platform myself", "Used it with my students",
               "Reviewed specific cases for accuracy", "Other"]
STUDENT_ITEMS = [("q_overall", "Overall satisfaction"),
                 ("q_reasoning", "Value for developing clinical reasoning"),
                 ("q_realism", "Case realism and engagement"),
                 ("q_usability", "Interface and ease of use"),
                 ("q_ai", "Usefulness of the AI decision support")]
FACULTY_ITEMS = [("accuracy", "Clinical accuracy of the cases and content"),
                 ("value", "Educational value for students"),
                 ("fit", "Fit with our curriculum and learning outcomes"),
                 ("realism", "Realism of the clinical scenarios"),
                 ("assessment", "Usefulness for teaching or assessment (case discussion, OSCE practice)"),
                 ("ai_safety", "Appropriateness and safety of the AI decision support")]
SCALE_HELP = "1 = very poor · 2 = poor · 3 = acceptable · 4 = good · 5 = excellent"
INFO = ("This short survey takes about 2 minutes. It is **voluntary and anonymous**: your name and email are not "
        "saved with your answers, and answers are stored with the date only. A scrambled one-way code of your "
        "account is stored separately, only so that nobody can answer twice; it is not linked to your answers. "
        "Results will be summarised to evaluate and improve the platform and may be quoted in applications and "
        "publications in aggregate. **Please do not write patient details, names or other identifying information "
        "in the comment boxes.** Honest criticism is just as valuable as praise.")


# ─────────────── storage (Supabase or demo) ───────────────
def _secret(k, d=""):
    try:
        return st.secrets.get(k, d)
    except Exception:
        return d


def _sb():
    u, k = _secret("SUPABASE_URL"), _secret("SUPABASE_KEY")
    return (u.rstrip("/"), k) if u and k and not str(u).startswith("YOUR_") else None


def _h(k):
    return {"apikey": k, "Authorization": f"Bearer {k}", "Content-Type": "application/json",
            "Prefer": "return=minimal"}


def _demo():
    d = st.session_state.setdefault("fb_demo", {})
    for t in T:
        d.setdefault(t, [])
    return d


def _ready():
    if not _sb():
        return True
    if st.session_state.get("fb_ready"):
        return True
    base, k = _sb()
    try:
        r = requests.get(f"{base}/rest/v1/{T['responses']}", headers=_h(k), params={"select": "id", "limit": "1"},
                         timeout=10)
        ok = r.status_code == 200
        if not ok:
            st.session_state["fb_err"] = f"{r.status_code}: {r.text[:160]}"
    except Exception as e:
        ok = False
        st.session_state["fb_err"] = str(e)[:160]
    st.session_state["fb_ready"] = ok
    return ok


def _all_responses():
    """Every response row (pages of 1000)."""
    cfg = _sb()
    if not cfg:
        return list(_demo()["responses"])
    base, k = cfg
    out, off = [], 0
    while True:
        try:
            r = requests.get(f"{base}/rest/v1/{T['responses']}", headers=_h(k),
                             params={"select": "*", "limit": "1000", "offset": str(off)}, timeout=20)
        except Exception:
            break
        if r.status_code != 200:
            break
        rows = r.json()
        out += rows
        if len(rows) < 1000:
            break
        off += 1000
    return out


def _token(kind, email):
    salt = _secret("FEEDBACK_SALT") or ("fb|" + str(_secret("SUPABASE_KEY", "demo")))
    return hmac.new(salt.encode(), f"{kind}|{email}".encode(), hashlib.sha256).hexdigest()


def _has_responded(tok):
    cfg = _sb()
    if not cfg:
        return any(t["token"] == tok for t in _demo()["tokens"])
    base, k = cfg
    try:
        r = requests.get(f"{base}/rest/v1/{T['tokens']}", headers=_h(k),
                         params={"select": "token", "token": f"eq.{tok}", "limit": "1"}, timeout=10)
        return r.status_code == 200 and bool(r.json())
    except Exception:
        return False


def _submit(kind, tok, row):
    """Claim the one-way code, then store the answers. Returns 'ok', 'dup' or 'error'."""
    cfg = _sb()
    row = {k: v for k, v in row.items()}
    row["kind"] = kind
    if not cfg:
        d = _demo()
        if any(t["token"] == tok for t in d["tokens"]):
            return "dup"
        d["tokens"].append({"token": tok, "kind": kind})
        row["id"] = str(uuid.uuid4())
        row["submitted_on"] = str(_dt.date.today())
        d["responses"].append(row)
        return "ok"
    base, k = cfg
    try:
        r = requests.post(f"{base}/rest/v1/{T['tokens']}", headers=_h(k), json={"token": tok, "kind": kind},
                          timeout=10)
        if r.status_code == 409:
            return "dup"
        if r.status_code not in (200, 201, 204):
            st.session_state["fb_err"] = f"{r.status_code}: {r.text[:160]}"
            return "error"
        r2 = requests.post(f"{base}/rest/v1/{T['responses']}", headers=_h(k), json=row, timeout=10)
        if r2.status_code in (200, 201, 204):
            return "ok"
        st.session_state["fb_err"] = f"{r2.status_code}: {r2.text[:160]}"
        requests.delete(f"{base}/rest/v1/{T['tokens']}", headers=_h(k), params={"token": f"eq.{tok}"}, timeout=10)
    except Exception as e:
        st.session_state["fb_err"] = str(e)[:160]
        try:
            requests.delete(f"{base}/rest/v1/{T['tokens']}", headers=_h(k), params={"token": f"eq.{tok}"}, timeout=10)
        except Exception:
            pass
    return "error"


# ─────────────── helpers ───────────────
def _user():
    a = st.session_state.get("auth_user") or {}
    return {"email": (a.get("email") or "").strip().lower(), "role": (a.get("role") or "student").lower()}


def _is_owner(u):
    if u["role"] != "admin":
        return False
    owners = [x.strip().lower() for x in str(_secret("FEEDBACK_OWNER_EMAILS", "")).split(",") if x.strip()]
    return (u["email"] in owners) if owners else True


def _target():
    try:
        return int(_secret("FEEDBACK_TARGET", 500))
    except (TypeError, ValueError):
        return 500


def _app_url():
    return _secret("APP_URL") or "https://mls-virtual-hospital.streamlit.app"


def _clip(s, n=1000):
    return (s or "").strip()[:n]


def _rating(label, key, help_=None):
    v = st.radio(label, [1, 2, 3, 4, 5], index=None, horizontal=True, key=key, help=help_)
    return v


def status_of(q):
    if q is None:
        return ""
    return "Satisfied" if q >= 4 else ("Neutral" if q == 3 else "Dissatisfied")


def avg_score(r):
    vals = [r.get(k) for k, _ in STUDENT_ITEMS if r.get(k) is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


# ─────────────── surveys ───────────────
def _student_form(u):
    tok = _token("student", u["email"])
    if st.session_state.get("fb_done_student") or _has_responded(tok):
        st.success("Thank you - your response has been recorded. Each account can answer once.")
        return
    st.markdown(INFO)
    with st.form("fb_student"):
        c1, c2 = st.columns(2)
        with c1:
            year = st.selectbox("Year *", YEARS, index=None, placeholder="Choose…", key="fbs_year")
        with c2:
            spec = st.selectbox("Specialty / interest", SPECIALTIES, index=None, placeholder="Choose…", key="fbs_spec")
        st.markdown("**Rate each item** — " + SCALE_HELP)
        ratings = {k: _rating(lab + " *", f"fbs_{k}") for k, lab in STUDENT_ITEMS}
        rec = st.radio("Would you recommend the Virtual Hospital to other students? *", RECOMMEND, index=None,
                       horizontal=True, key="fbs_rec")
        st.markdown("**About your use** (optional)")
        mods = st.multiselect("Which parts did you use?", MODULES, key="fbs_mods")
        hours = st.selectbox("Roughly how much time have you spent on it?", HOURS, index=None,
                             placeholder="Choose…", key="fbs_hours")
        before = st.radio("Before this platform, how easy was it for you to practise clinical reasoning on realistic "
                          "cases? (1 = very difficult, 5 = very easy)", [1, 2, 3, 4, 5], index=None,
                          horizontal=True, key="fbs_before")
        gap = st.text_area("What gap, if any, did the platform fill for you?", height=70, key="fbs_gap")
        st.markdown("**In your own words** (optional, no names or patient details)")
        liked = st.text_area("What did you like most?", height=70, key="fbs_liked")
        disliked = st.text_area("What did you dislike, or what was difficult?", height=70, key="fbs_dis")
        sugg = st.text_area("What should we improve?", height=70, key="fbs_sugg")
        agree = st.checkbox("I understand this survey is voluntary and anonymous, and I agree that my answers may "
                            "be used as described above.", key="fbs_ok")
        go_ = st.form_submit_button("Submit anonymously", use_container_width=True)
    if not go_:
        return
    if not agree:
        st.error("Please tick the box to confirm you agree.")
        return
    if not year or any(v is None for v in ratings.values()) or rec is None:
        st.error("Please answer the Year, all five ratings and the recommendation question.")
        return
    row = {"year_level": year, "specialty": spec, **{k: int(v) for k, v in ratings.items()},
           "would_recommend": rec, "liked": _clip(liked), "disliked": _clip(disliked), "suggestions": _clip(sugg),
           "extra": {"modules": mods, "hours": hours, "access_before": before, "gap": _clip(gap)}}
    res = _submit("student", tok, row)
    if res == "ok":
        st.session_state["fb_done_student"] = True
        st.rerun()
    elif res == "dup":
        st.session_state["fb_done_student"] = True
        st.rerun()
    else:
        st.error(f"Could not save your response. Please try again later. ({st.session_state.get('fb_err', '')})")


def _faculty_form(u):
    tok = _token("faculty", u["email"])
    if st.session_state.get("fb_done_faculty") or _has_responded(tok):
        st.success("Thank you - your feedback has been recorded. Each account can answer once.")
        return
    st.markdown(INFO)
    with st.form("fb_faculty"):
        c1, c2 = st.columns(2)
        with c1:
            title = st.selectbox("Your role *", FACULTY_TITLES, index=None, placeholder="Choose…", key="fbf_title")
            inst = st.text_input("Institution", value="Lebanese University", key="fbf_inst")
        with c2:
            dept = st.text_input("Department / specialty", key="fbf_dept")
            how = st.selectbox("How did you evaluate the platform?", FACULTY_HOW, index=None,
                               placeholder="Choose…", key="fbf_how")
        st.markdown("**Rate each item** — " + SCALE_HELP)
        overall = _rating("Overall opinion of the platform *", "fbf_overall")
        items = {k: _rating(lab + " *", f"fbf_{k}") for k, lab in FACULTY_ITEMS}
        use = st.radio("Would you use it in your teaching? *", RECOMMEND, index=None, horizontal=True, key="fbf_use")
        rec = st.radio("Would you recommend it to other medical schools or hospitals? *", RECOMMEND, index=None,
                       horizontal=True, key="fbf_rec")
        st.markdown("**In your own words**")
        liked = st.text_area("Main strengths", height=80, key="fbf_liked")
        disliked = st.text_area("Concerns, errors or limitations you noticed (clinical accuracy, safety, "
                                "curriculum fit…)", height=80, key="fbf_dis")
        sugg = st.text_area("What would make it more useful for teaching?", height=80, key="fbf_sugg")
        st.markdown("**May we quote you?**")
        quote = st.radio("Attribution", ["Anonymous only", "You may quote my comments with my name and role"],
                         key="fbf_quote", label_visibility="collapsed")
        st.caption("A named comment is more credible to reviewers. If you choose named, add your name below; "
                   "your contact is optional and is seen only by the platform owner, to verify the feedback.")
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Name (only if you agree to be quoted)", key="fbf_name")
        with c2:
            contact = st.text_input("Contact for verification (optional, private)", key="fbf_contact")
        agree = st.checkbox("I understand my participation is voluntary and agree that my answers may be used as "
                            "described above.", key="fbf_ok")
        go_ = st.form_submit_button("Submit feedback", use_container_width=True)
    if not go_:
        return
    if not agree:
        st.error("Please tick the box to confirm you agree.")
        return
    if not title or overall is None or any(v is None for v in items.values()) or use is None or rec is None:
        st.error("Please answer your role, every rating, and both 'would you' questions.")
        return
    named = quote.startswith("You may")
    if named and not name.strip():
        st.error("You chose to be quoted by name - please add your name, or switch to 'Anonymous only'.")
        return
    row = {"specialty": _clip(dept, 120), "q_overall": int(overall), "would_recommend": rec,
           "liked": _clip(liked), "disliked": _clip(disliked), "suggestions": _clip(sugg),
           "extra": {"title": title, "institution": _clip(inst, 120), "evaluated_by": how, "use_in_teaching": use,
                     **{k: int(v) for k, v in items.items()}, "quote": "named" if named else "anonymous",
                     "name": _clip(name, 120) if named else "", "contact": _clip(contact, 160) if named else ""}}
    res = _submit("faculty", tok, row)
    if res in ("ok", "dup"):
        st.session_state["fb_done_faculty"] = True
        st.rerun()
    else:
        st.error(f"Could not save your feedback. Please try again later. ({st.session_state.get('fb_err', '')})")


# ─────────────── owner results ───────────────
def _as_date(v):
    try:
        return _dt.date.fromisoformat(str(v)[:10])
    except Exception:
        return v


def build_xlsx(students, faculty):
    """Excel export laid out like the original Student_Responses sheet (no names), plus faculty and summary."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Student_Responses"
    head_fill = PatternFill("solid", fgColor="1F4E78")
    ws.merge_cells("A1:O1")
    ws["A1"] = "Virtual Hospital Project — Student Feedback & Evaluation (anonymous responses)"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A2:O2")
    ws["A2"] = ("Responses collected through the in-app anonymous survey. No names or emails are stored; "
                "'Response code' is a running label added at export.")
    heads = ["Response code", "Year", "Specialty", "Date", "Overall Satisfaction (1-5)", "Satisfaction Status",
             "Clinical Reasoning Value (1-5)", "Case Realism & Engagement (1-5)", "Interface & Usability (1-5)",
             "AI Decision Support (1-5)", "Average Score", "Would Recommend?", "What Did You Like Most?",
             "What Did You Dislike / Challenges?", "Suggestions for Improvement"]
    for i, h in enumerate(heads, 1):
        c = ws.cell(row=4, column=i, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = head_fill
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for n, r in enumerate(sorted(students, key=lambda x: str(x.get("submitted_on"))), start=1):
        row = 4 + n
        vals = [f"S{n:03d}", r.get("year_level"), r.get("specialty"), _as_date(r.get("submitted_on")), r.get("q_overall"),
                None, r.get("q_reasoning"), r.get("q_realism"), r.get("q_usability"), r.get("q_ai"), None,
                r.get("would_recommend"), r.get("liked"), r.get("disliked"), r.get("suggestions")]
        for i, v in enumerate(vals, 1):
            ws.cell(row=row, column=i, value=v)
        ws.cell(row=row, column=4).number_format = "yyyy-mm-dd"
        ws.cell(row=row, column=6, value=f'=IF(E{row}="","",IF(E{row}>=4,"Satisfied",IF(E{row}=3,"Neutral","Dissatisfied")))')
        ws.cell(row=row, column=11, value=f'=IF(COUNT(E{row},G{row}:J{row})=0,"",AVERAGE(E{row},G{row}:J{row}))')
    for col, w in zip("ABCDEFGHIJKLMNO", [14, 16, 22, 12, 14, 16, 14, 14, 14, 14, 12, 14, 40, 40, 40]):
        ws.column_dimensions[col].width = w
    ws.row_dimensions[4].height = 45
    ws.freeze_panes = "B5"

    wf = wb.create_sheet("Faculty_Responses")
    fh = ["Response code", "Date", "Role", "Institution", "Department", "How evaluated", "Overall (1-5)"] + \
         [lab for _, lab in FACULTY_ITEMS] + ["Use in teaching?", "Recommend to others?", "Strengths",
                                              "Concerns / limitations", "Suggestions", "Attribution",
                                              "Name (only if consented)"]
    for i, h in enumerate(fh, 1):
        c = wf.cell(row=1, column=i, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = head_fill
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for n, r in enumerate(sorted(faculty, key=lambda x: str(x.get("submitted_on"))), start=1):
        x = r.get("extra") or {}
        vals = [f"F{n:03d}", _as_date(r.get("submitted_on")), x.get("title"), x.get("institution"), r.get("specialty"),
                x.get("evaluated_by"), r.get("q_overall")] + [x.get(k) for k, _ in FACULTY_ITEMS] + \
               [x.get("use_in_teaching"), r.get("would_recommend"), r.get("liked"), r.get("disliked"),
                r.get("suggestions"), x.get("quote"), x.get("name") if x.get("quote") == "named" else ""]
        for i, v in enumerate(vals, 1):
            wf.cell(row=1 + n, column=i, value=v)
    for i in range(1, len(fh) + 1):
        wf.column_dimensions[wf.cell(row=1, column=i).column_letter].width = 18
    wf.row_dimensions[1].height = 60
    wf.freeze_panes = "B2"

    wsum = wb.create_sheet("Summary", 0)
    wsum["A1"] = "Virtual Hospital — feedback summary (calculated from the response sheets)"
    wsum["A1"].font = Font(bold=True, size=14)
    rows = [("Student responses", "=COUNTA(Student_Responses!A5:A5000)"),
            ("Faculty / clinician responses", "=COUNTA(Faculty_Responses!A2:A5000)"),
            ("Mean overall satisfaction (students)", '=IFERROR(AVERAGE(Student_Responses!E5:E5000),"")'),
            ("% Satisfied (4-5)", '=IFERROR(COUNTIF(Student_Responses!F5:F5000,"Satisfied")/COUNTA(Student_Responses!A5:A5000),"")'),
            ("% Neutral (3)", '=IFERROR(COUNTIF(Student_Responses!F5:F5000,"Neutral")/COUNTA(Student_Responses!A5:A5000),"")'),
            ("% Dissatisfied (1-2)", '=IFERROR(COUNTIF(Student_Responses!F5:F5000,"Dissatisfied")/COUNTA(Student_Responses!A5:A5000),"")'),
            ("Mean clinical reasoning value", '=IFERROR(AVERAGE(Student_Responses!G5:G5000),"")'),
            ("Mean case realism & engagement", '=IFERROR(AVERAGE(Student_Responses!H5:H5000),"")'),
            ("Mean interface & usability", '=IFERROR(AVERAGE(Student_Responses!I5:I5000),"")'),
            ("Mean AI decision support", '=IFERROR(AVERAGE(Student_Responses!J5:J5000),"")'),
            ("% Would recommend (Yes)", '=IFERROR(COUNTIF(Student_Responses!L5:L5000,"Yes")/COUNTA(Student_Responses!A5:A5000),"")'),
            ("Faculty mean overall opinion", '=IFERROR(AVERAGE(Faculty_Responses!G2:G5000),"")')]
    for i, (lab, f) in enumerate(rows, start=3):
        wsum.cell(row=i, column=1, value=lab)
        c = wsum.cell(row=i, column=2, value=f)
        if lab.startswith("%"):
            c.number_format = "0.0%"
        elif lab.startswith(("Mean", "Faculty mean")):
            c.number_format = "0.00"
    wsum.column_dimensions["A"].width = 44
    wsum.column_dimensions["B"].width = 14
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _dist(rows, key):
    d = {i: 0 for i in range(1, 6)}
    for r in rows:
        v = r.get(key)
        if v in d:
            d[v] += 1
    return d


def _invite_texts():
    url = _app_url()
    student = (f"Dear students,\n\nWe are evaluating the MLS Virtual Hospital and would value your honest opinion. "
               f"The survey takes about 2 minutes, is voluntary and anonymous (no name or email is saved with your "
               f"answers). Critical feedback is just as helpful as praise.\n\n1) Open {url} and sign in\n"
               f"2) In the menu choose “📝 Feedback (anonymous)”\n3) Answer and press Submit\n\nThank you for helping "
               f"us improve it.")
    faculty = (f"Dear Professor,\n\nThe MLS Virtual Hospital is a simulation platform for clinical reasoning and "
               f"practical skills used by medical students. We would be grateful for your professional opinion on its "
               f"clinical accuracy, educational value and fit with the curriculum. It takes about 3 minutes; you may "
               f"answer anonymously or allow us to quote you by name.\n\n1) Open {url} and create or sign in to an "
               f"account\n2) In the menu choose “📝 Feedback (anonymous)” and select “Professor / clinician”\n"
               f"3) Complete the form\n\nYour critical comments, especially on clinical accuracy, are the most useful "
               f"part. Thank you for your time.")
    return student, faculty


def _results():
    rows = _all_responses()
    students = [r for r in rows if r.get("kind") == "student"]
    faculty = [r for r in rows if r.get("kind") == "faculty"]
    tgt = _target()
    st.markdown("#### Responses so far")
    c1, c2 = st.columns(2)
    c1.metric("Student responses", f"{len(students)} / {tgt}")
    c2.metric("Professor / clinician responses", len(faculty))
    st.progress(min(1.0, len(students) / tgt) if tgt else 0.0)
    st.caption("These are real submissions from signed-in accounts, one per account. Nothing on this page can be "
               "typed in or edited.")
    if not rows:
        st.info("No responses yet. Share the invitation messages (last tab) with students and professors.")
    t = st.tabs(["Student results", "Professor results", "Export", "Invitation messages"])

    with t[0]:
        if not students:
            st.caption("No student responses yet.")
        else:
            import plotly.graph_objects as go
            n = len(students)
            sat = [status_of(r.get("q_overall")) for r in students]
            st.markdown(f"**n = {n}**  ·  Satisfied {sat.count('Satisfied')} ({sat.count('Satisfied') / n:.0%})  ·  "
                        f"Neutral {sat.count('Neutral')} ({sat.count('Neutral') / n:.0%})  ·  "
                        f"Dissatisfied {sat.count('Dissatisfied')} ({sat.count('Dissatisfied') / n:.0%})")
            tbl = [{"Item": lab, "Mean (1-5)": _mean([r.get(k) for r in students]),
                    "% rating 4-5": f"{sum(1 for r in students if (r.get(k) or 0) >= 4) / n:.0%}"}
                   for k, lab in STUDENT_ITEMS]
            st.dataframe(tbl, hide_index=True, use_container_width=True, key="fb_tbl_items")
            fig = go.Figure(go.Bar(x=list(_dist(students, "q_overall")), y=list(_dist(students, "q_overall").values())))
            fig.update_layout(title="Overall satisfaction (count by rating)", height=260,
                              margin=dict(l=10, r=10, t=40, b=10), xaxis_title="Rating")
            st.plotly_chart(fig, use_container_width=True, key="fb_fig_overall")
            rec = {x: sum(1 for r in students if r.get("would_recommend") == x) for x in RECOMMEND}
            st.markdown("**Would recommend:** " + " · ".join(f"{k} {v} ({v / n:.0%})" for k, v in rec.items()))
            ab = [(r.get("extra") or {}).get("access_before") for r in students]
            if any(ab):
                st.markdown(f"**Ease of practising clinical reasoning before the platform (1 = very difficult, "
                           f"5 = very easy):** mean {_mean(ab)} (n = {len([a for a in ab if a])})")
            mods = {}
            for r in students:
                for m in (r.get("extra") or {}).get("modules", []):
                    mods[m] = mods.get(m, 0) + 1
            if mods:
                st.markdown("**Parts used:** " + " · ".join(f"{k} {v}" for k, v in sorted(mods.items(), key=lambda x: -x[1])))
            st.markdown("**By year** (groups smaller than %d are hidden to protect anonymity)" % MIN_CELL)
            by = []
            for y in YEARS:
                g = [r for r in students if r.get("year_level") == y]
                if len(g) >= MIN_CELL:
                    by.append({"Year": y, "n": len(g), "Mean overall": _mean([r.get("q_overall") for r in g])})
            st.dataframe(by, hide_index=True, use_container_width=True, key="fb_tbl_year") if by else \
                st.caption("No year group has enough responses to show yet.")
            with st.expander(f"Comments ({sum(1 for r in students for k in ('liked', 'disliked', 'suggestions') if r.get(k))})"):
                for lab, key in (("👍 Liked most", "liked"), ("👎 Disliked / challenges", "disliked"),
                                 ("💡 Suggestions", "suggestions")):
                    st.markdown(f"**{lab}**")
                    cs = [r[key] for r in students if r.get(key)]
                    for c in cs:
                        st.markdown("• " + re.sub(r"([\\`*_{}\[\]()#+\-!|<>~$])", r"\\\1", c))
                    if not cs:
                        st.caption("None yet.")

    with t[1]:
        if not faculty:
            st.caption("No professor / clinician responses yet.")
        else:
            nf = len(faculty)
            st.markdown(f"**n = {nf}**  ·  mean overall opinion {_mean([r.get('q_overall') for r in faculty])}")
            tbl = [{"Item": lab, "Mean (1-5)": _mean([(r.get('extra') or {}).get(k) for r in faculty])}
                   for k, lab in FACULTY_ITEMS]
            st.dataframe(tbl, hide_index=True, use_container_width=True, key="fb_tbl_fitems")
            use = {x: sum(1 for r in faculty if (r.get("extra") or {}).get("use_in_teaching") == x) for x in RECOMMEND}
            rec = {x: sum(1 for r in faculty if r.get("would_recommend") == x) for x in RECOMMEND}
            st.markdown("**Would use in teaching:** " + " · ".join(f"{k} {v}" for k, v in use.items()))
            st.markdown("**Would recommend to others:** " + " · ".join(f"{k} {v}" for k, v in rec.items()))
            st.markdown("**Named comments (quotable)**")
            named = [r for r in faculty if (r.get("extra") or {}).get("quote") == "named"]
            for r in named:
                x = r["extra"]
                st.markdown(f"**{x.get('name')}** — {x.get('title')}, {x.get('institution')}"
                            + (f" · contact: {x['contact']}" if x.get("contact") else ""))
                for lab, key in (("Strengths", "liked"), ("Concerns", "disliked"), ("Suggestions", "suggestions")):
                    if r.get(key):
                        st.markdown(f"> *{lab}:* " + re.sub(r"([\\`*_{}\[\]()#+\-!|<>~$])", r"\\\1", r[key]))
            if not named:
                st.caption("No one has agreed to be quoted by name yet.")
            with st.expander("Anonymous comments"):
                for r in [r for r in faculty if (r.get("extra") or {}).get("quote") != "named"]:
                    for lab, key in (("Strengths", "liked"), ("Concerns", "disliked"), ("Suggestions", "suggestions")):
                        if r.get(key):
                            st.markdown(f"• *{lab}:* " + re.sub(r"([\\`*_{}\[\]()#+\-!|<>~$])", r"\\\1", r[key]))

    with t[2]:
        st.caption("The Excel file has Summary, Student_Responses (same columns as your original sheet, with a "
                   "response code instead of a name) and Faculty_Responses. Summary and status columns are formulas.")
        st.download_button("⬇️ Download Excel (.xlsx)", build_xlsx(students, faculty), key="fb_dl_xlsx",
                           file_name=f"MLS_Virtual_Hospital_Feedback_{_dt.date.today()}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with t[3]:
        s_txt, f_txt = _invite_texts()
        st.markdown("**Message for students** (copy and send by WhatsApp, email or class group)")
        st.code(s_txt, language=None)
        st.markdown("**Message for professors / clinicians**")
        st.code(f_txt, language=None)
        st.caption("Tip: ask professors you know personally, and ask them to be quotable by name. Never ask anyone "
                   "to give a particular rating.")


# ─────────────── page ───────────────
def render_feedback_survey():
    u = _user()
    st.markdown("### 📝 Feedback (anonymous)")
    st.caption("Help us evaluate and improve the MLS Virtual Hospital. Real, honest answers only.")
    if not _sb():
        st.warning("DEMO MODE: Supabase is not configured, so responses are not saved after this session.")
    elif not _ready():
        st.error("The feedback tables are not in Supabase yet. Run **feedback_survey.sql** in the Supabase SQL "
                 f"Editor, then reload this page. ({st.session_state.get('fb_err', '')})")
        return
    if not u["email"]:
        st.info("Please sign in to give feedback (one response per account keeps the results trustworthy).")
        return
    labels = ["🎓 Student / resident", "👩‍🏫 Professor / clinician"]
    if _is_owner(u):
        labels.append("📊 Results (owner only)")
    tabs = st.tabs(labels)
    with tabs[0]:
        _student_form(u)
    with tabs[1]:
        _faculty_form(u)
    if _is_owner(u):
        with tabs[2]:
            _results()
