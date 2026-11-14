"""
patient_chart.py - Patient Chart / Daily Rounds for the MLS Virtual Hospital (additive, standalone).

Adapted from the MLS-PatientChart app for TEACHING: students (and faculty) follow SIMULATED patients across
days - daily ward rounds, follow-up visits - writing SOAP-style notes with vitals, review of systems,
prescriptions, plan and follow-up, recording lab panels, and watching vital-sign and lab trends build up.
Faculty can create shared class patients and leave feedback on any student's note.

Safety by design:
  - simulated patients only: no fields for phone, national ID, date of birth, address or photo;
    a confirmation is required when a patient is created
  - nothing is rendered as raw HTML (all user text is shown as plain text)
  - no clinical reference values are shipped: lab ranges are only what the user types in
  - the Case Library import copies presentation, history and medications but NOT the final diagnosis or results

Storage: Supabase tables from patient_chart.sql (same SUPABASE_URL / SUPABASE_KEY secrets as the app).
Without Supabase it runs in a clearly labelled DEMO mode (this session only).

Hook-up in app.py:
    from patient_chart import render_patient_chart
    render_patient_chart(case_loader=load_cases, on_visit_saved=<optional callback>)
"""
import datetime as _dt
import re
import requests
import streamlit as st

T = {"patients": "vh_pc_patients", "visits": "vh_pc_visits", "labs": "vh_pc_labs", "feedback": "vh_pc_feedback"}

SIM_BANNER = ("**Simulated patients only.** Never type a real patient's name, ID number, phone, date of birth, "
              "address or photo - or any detail that could identify a real person. This chart has no fields for "
              "those on purpose.")

VISIT_TYPES = ["Daily ward round", "Follow-up", "New complaint", "Routine check-up", "Emergency review",
               "Results review", "Procedure review", "Discharge review", "Other"]
SEXES = ["Female", "Male", "Other / not stated"]
BLOODS = ["Not recorded", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
ROS_OPTIONS = ["General (fever, weight loss, fatigue)", "Cardiovascular", "Respiratory", "Gastrointestinal",
               "Neurological", "Musculoskeletal", "Urinary", "Skin", "ENT", "Psychiatric", "Endocrine",
               "Haematological", "Reproductive / obstetric"]
TREND_PARAMS = {"Blood pressure": ("bp_sys", "bp_dia"), "Heart rate": ("hr",), "Temperature": ("temp",),
                "SpO₂": ("spo2",), "Respiratory rate": ("rr",), "Weight": ("weight",), "Pain score": ("pain",)}
VITAL_LABEL = {"bp_sys": "Systolic", "bp_dia": "Diastolic", "hr": "HR", "temp": "Temp", "spo2": "SpO₂",
               "rr": "RR", "weight": "Weight", "pain": "Pain"}
RULES = [
    ("Simulated patients only",
     "Create fictional patients (or start from a Case Library case). Never enter a real patient's identity or "
     "details. Real patient care belongs in your hospital's own record system, not here."),
    ("What is saved",
     "Your patients, notes, vitals and labs are saved in the hospital database under your account. Faculty can "
     "view all simulated patients to give feedback. Shared class patients are visible to every student."),
    ("No reference values are supplied",
     "This chart does not ship normal ranges. If you type a reference range with a lab result, the chart flags "
     "values outside the range you entered - check the range against your lab's own source."),
    ("Teaching tool, not clinical advice",
     "Nothing here should guide real treatment decisions. Doses and plans you write are practice."),
]


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
            "Prefer": "return=representation"}


def _demo():
    return st.session_state.setdefault("pc_demo", {t: [] for t in T})


def _now():
    return _dt.datetime.utcnow().isoformat(timespec="seconds")


def _norm(x):
    return str(x).strip().lower()


def sel(t, eq=None, in_=None, order=None, limit=None):
    """Read rows. eq={col: value}; in_=(col, [values])."""
    cfg = _sb()
    if cfg:
        base, k = cfg
        p = {"select": "*"}
        for c, v in (eq or {}).items():
            p[c] = f"eq.{str(v).lower() if isinstance(v, bool) else v}"
        if in_:
            col, vals = in_
            if not vals:
                return []
            p[col] = "in.(" + ",".join(str(x) for x in vals) + ")"
        if order:
            p["order"] = order
        if limit:
            p["limit"] = str(limit)
        try:
            r = requests.get(f"{base}/rest/v1/{T[t]}", headers=_h(k), params=p, timeout=10)
            return r.json() if r.status_code == 200 else []
        except Exception:
            return []
    rows = [r for r in _demo()[t] if all(_norm(r.get(c)) == _norm(v) for c, v in (eq or {}).items())]
    if in_:
        col, vals = in_
        sv = {_norm(x) for x in vals}
        rows = [r for r in rows if _norm(r.get(col)) in sv]
    if order:
        col, _, d = order.partition(".")
        rows = sorted(rows, key=lambda r: str(r.get(col, "")), reverse=(d == "desc"))
    return rows[:limit] if limit else rows


def ins(t, row):
    cfg = _sb()
    if cfg:
        base, k = cfg
        try:
            r = requests.post(f"{base}/rest/v1/{T[t]}", headers=_h(k), json=row, timeout=10)
            if r.status_code in (200, 201):
                j = r.json()
                return j[0] if j else row
            st.session_state["pc_last_err"] = f"{r.status_code}: {r.text[:200]}"
        except Exception as e:
            st.session_state["pc_last_err"] = str(e)[:200]
        st.error("Could not save. Check that patient_chart.sql has been run in Supabase. "
                 f"({st.session_state.get('pc_last_err', '')})")
        return None
    d = _demo()
    row = dict(row)
    row["id"] = len(d[t]) + 1
    row["created_at"] = _now()
    d[t].append(row)
    return row


def upd(t, rid, patch):
    cfg = _sb()
    if cfg:
        base, k = cfg
        try:
            r = requests.patch(f"{base}/rest/v1/{T[t]}", headers=_h(k), params={"id": f"eq.{rid}"},
                               json=patch, timeout=10)
            return r.status_code in (200, 204)
        except Exception:
            return False
    for r in _demo()[t]:
        if str(r["id"]) == str(rid):
            r.update(patch)
    return True


def _ready():
    """True when the Supabase tables exist (or when in demo mode)."""
    if not _sb():
        return True
    if st.session_state.get("pc_ready"):
        return True
    base, k = _sb()
    try:
        r = requests.get(f"{base}/rest/v1/{T['patients']}", headers=_h(k),
                         params={"select": "id", "limit": "1"}, timeout=10)
        ok = r.status_code == 200
        if not ok:
            st.session_state["pc_last_err"] = f"{r.status_code}: {r.text[:200]}"
    except Exception as e:
        ok = False
        st.session_state["pc_last_err"] = str(e)[:200]
    st.session_state["pc_ready"] = ok
    return ok


# ─────────────── helpers ───────────────
def _user():
    a = st.session_state.get("auth_user") or {}
    email = (a.get("email") or "").strip().lower()
    return {"email": email or "guest", "name": a.get("name") or a.get("email") or "Guest",
            "role": (a.get("role") or "student").lower()}


def _is_mod(u):
    return u["role"] in ("admin", "faculty")


def _md(s):
    """Escape user text so it shows as plain text (no markdown/HTML tricks)."""
    s = "" if s is None else str(s)
    s = re.sub(r"([\\`*_{}\[\]()#+\-!|<>~$])", r"\\\1", s)
    return s.replace("\n", "  \n")


def _num(s):
    try:
        return float(str(s).strip())
    except (TypeError, ValueError):
        return None


def _date(s):
    try:
        return _dt.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def _lines(txt):
    return [x.strip() for x in (txt or "").splitlines() if x.strip()]


def _day(pat, d):
    a, b = _date(pat.get("admitted_on")), _date(d)
    return (b - a).days + 1 if a and b else None


def _can_write(u, pat):
    return _is_mod(u) or pat.get("shared") or _norm(pat.get("owner_email")) == u["email"]


def _can_edit(u, pat):
    return _is_mod(u) or _norm(pat.get("owner_email")) == u["email"]


def _visible_patients(u):
    if _is_mod(u):
        rows = sel("patients", order="created_at.desc")
    else:
        rows = {r["id"]: r for r in sel("patients", eq={"owner_email": u["email"]}, order="created_at.desc")}
        rows.update({r["id"]: r for r in sel("patients", eq={"shared": True}, order="created_at.desc")})
        rows = sorted(rows.values(), key=lambda r: str(r.get("created_at", "")), reverse=True)
    return [r for r in rows if not r.get("archived")]


def _fmt_age(a):
    n = _num(a)
    if n is None:
        return "age ?"
    return f"{int(n)} y" if n >= 1 and n == int(n) else (f"{n:g} y")


def _vitals_line(vt):
    p = []
    if vt.get("bp_sys") and vt.get("bp_dia"):
        p.append(f"BP {vt['bp_sys']:g}/{vt['bp_dia']:g} mmHg")
    for k, lab, unit in (("hr", "HR", "bpm"), ("rr", "RR", "/min"), ("temp", "Temp", "°C"),
                         ("spo2", "SpO₂", "%"), ("weight", "Wt", "kg"), ("pain", "Pain", "/10")):
        if vt.get(k):
            p.append(f"{lab} {vt[k]:g} {unit}")
    return " · ".join(p)


def _flag(val, low, high):
    v, lo, hi = _num(val), _num(low), _num(high)
    if v is None:
        return ""
    if lo is not None and v < lo:
        return "↓ below range"
    if hi is not None and v > hi:
        return "↑ above range"
    return "within range" if (lo is not None or hi is not None) else ""


def _from_library(row):
    """Pre-fill values from a Case Library row. Final diagnosis and investigation results are NOT copied."""
    def g(k):
        v = row.get(k)
        try:
            if v != v:  # NaN
                return ""
        except Exception:
            pass
        return "" if v is None else str(v).strip()

    out = {"title": g("Title"), "age": 0.0, "sex": SEXES[0], "brief": "", "chronic": "", "meds": "",
           "case_ref": g("Case_ID")}
    if out["case_ref"].endswith(".0"):
        out["case_ref"] = out["case_ref"][:-2]
    low = g("Age_Sex").lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(year|yr|y|month|mo|week|wk|day|d)?", low)
    if m:
        n, unit = float(m.group(1)), (m.group(2) or "y")
        out["age"] = round(n / 12, 2) if unit.startswith(("month", "mo")) else \
            round(n / 52, 2) if unit.startswith(("week", "wk")) else \
            round(n / 365, 2) if unit.startswith("d") else n
    if "female" in low or re.search(r"\bf\b", low):
        out["sex"] = "Female"
    elif "male" in low or re.search(r"\bm\b", low):
        out["sex"] = "Male"
    parts = []
    cc, dur, ctx = g("Chief_Complaint"), g("Duration"), g("Context")
    if cc:
        parts.append(f"Presenting complaint: {cc}" + (f" ({dur})" if dur else "") + ".")
    if ctx:
        parts.append(f"Context: {ctx}")
    if g("HPI"):
        parts.append(f"History: {g('HPI')}")
    if g("Social_Hx") and g("Social_Hx").lower() not in ("none", "neg.", "neg", "clear"):
        parts.append(f"Social: {g('Social_Hx')}")
    out["brief"] = "\n".join(parts)
    pmh = g("PMH")
    if pmh and pmh.lower().strip(". ") not in ("neg", "none", "nil", "negative"):
        out["chronic"] = "\n".join(x.strip() for x in re.split(r"[,;\n]", pmh) if x.strip())
    meds = g("Medications")
    if meds and meds.lower().strip(". ") not in ("neg", "none", "nil", "negative"):
        out["meds"] = "\n".join(x.strip() for x in re.split(r"[,;\n]", meds) if x.strip())
    return out


# ─────────────── charts ───────────────
def _trend_fig(visits, keys, title):
    import plotly.graph_objects as go
    fig = go.Figure()
    for k in keys:
        pts = [(v["visit_date"], (v.get("data") or {}).get("vitals", {}).get(k)) for v in visits]
        pts = [(d, x) for d, x in pts if x is not None]
        if pts:
            fig.add_trace(go.Scatter(x=[d for d, _ in pts], y=[x for _, x in pts], mode="lines+markers",
                                     name=VITAL_LABEL.get(k, k)))
    if not fig.data:
        return None
    fig.update_layout(title=title, height=300, margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h"), hovermode="x unified")
    return fig


def _lab_series(labs):
    """{lowercase name: {'name','unit','pts':[(date, num, low, high)], 'all':[...]}} from lab panels."""
    out = {}
    for lab in sorted(labs, key=lambda x: (str(x.get("lab_date")), str(x.get("created_at")))):
        for r in lab.get("results") or []:
            nm = (r.get("name") or "").strip()
            if not nm:
                continue
            s = out.setdefault(nm.lower(), {"name": nm, "unit": r.get("unit", ""), "pts": []})
            n = _num(r.get("value"))
            if n is not None:
                s["pts"].append((lab["lab_date"], n, _num(r.get("low")), _num(r.get("high"))))
    return out


def _lab_fig(s):
    import plotly.graph_objects as go
    pts = s["pts"]
    if not pts:
        return None
    fig = go.Figure(go.Scatter(x=[p[0] for p in pts], y=[p[1] for p in pts], mode="lines+markers", name=s["name"]))
    lo, hi = pts[-1][2], pts[-1][3]
    if lo is not None and hi is not None and lo < hi:
        fig.add_hrect(y0=lo, y1=hi, fillcolor="green", opacity=0.10, line_width=0,
                      annotation_text="range you entered", annotation_position="top left")
    fig.update_layout(title=f"{s['name']}" + (f" ({s['unit']})" if s["unit"] else ""), height=300,
                      margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified")
    return fig


# ─────────────── visit display ───────────────
def _show_visit(v, pat, fbs, u):
    d = v.get("data") or {}
    day = _day(pat, v.get("visit_date"))
    head = f"{v.get('visit_date')}" + (f" · Day {day}" if day else "") + f" · {v.get('visit_type', '')}"
    with st.container(border=True):
        st.markdown(f"**{head}**")
        st.caption(f"Written by {v.get('author_name') or 'unknown'}")
        if d.get("complaint"):
            st.markdown("**Subjective:** " + _md(d["complaint"]))
        vl = _vitals_line(d.get("vitals") or {})
        if vl:
            st.markdown("**Vitals:** " + _md(vl))
        if d.get("ros_positive") or d.get("ros_notes"):
            st.markdown("**Review of systems:** " + _md(", ".join(d.get("ros_positive", []))) +
                        (("  \n" + _md(d["ros_notes"])) if d.get("ros_notes") else ""))
        if d.get("exam"):
            st.markdown("**Examination:** " + _md(d["exam"]))
        if d.get("diagnosis"):
            st.markdown("**Assessment:** " + _md(d["diagnosis"]) +
                        (("  \n*Also:* " + _md("; ".join(d["secondary_dx"]))) if d.get("secondary_dx") else ""))
        rx = [r for r in d.get("prescriptions", []) if r.get("drug")]
        if rx:
            st.markdown("**Prescriptions:**  \n" + "  \n".join(
                "• " + _md(" ".join(x for x in (r.get("drug"), r.get("dose"), r.get("route"), r.get("freq"),
                                               (f"× {r['duration']}" if r.get("duration") else ""),
                                               (f"({r['notes']})" if r.get("notes") else "")) if x))
                for r in rx))
        if d.get("plan"):
            st.markdown("**Plan:** " + _md(d["plan"]))
        for lab, key in (("Tests ordered", "tests"), ("Referrals", "referrals")):
            if d.get(key):
                st.markdown(f"**{lab}:** " + _md("; ".join(d[key])))
        if d.get("followup_date") or d.get("followup_note"):
            st.markdown("**Follow-up:** " + _md(" - ".join(x for x in (d.get("followup_date"), d.get("followup_note")) if x)))
        if d.get("notes"):
            st.markdown("**Learning notes:** " + _md(d["notes"]))
        for f in fbs:
            st.info(f"🧑‍🏫 **{_md(f.get('author_name') or 'Faculty')}:** {_md(f.get('text', ''))}")
        if _is_mod(u):
            with st.form(f"pc_fb_{v['id']}", clear_on_submit=True):
                txt = st.text_input("Feedback for the student", key=f"pc_fbt_{v['id']}",
                                    placeholder="e.g. Good assessment - what would you recheck tomorrow?")
                if st.form_submit_button("Send feedback"):
                    if txt.strip():
                        ins("feedback", {"patient_id": pat["id"], "visit_id": v["id"], "author_email": u["email"],
                                         "author_name": u["name"], "text": txt.strip()[:1000]})
                        st.rerun()
                    else:
                        st.warning("Type some feedback first.")


# ─────────────── forms ───────────────
def _form_n():
    return st.session_state.setdefault("pc_form_n", 0)


def _bump():
    st.session_state["pc_form_n"] = _form_n() + 1


def _visit_form(u, pat, on_saved):
    n = _form_n()
    k = f"{pat['id']}_{n}"
    if pat.get("drug_history"):
        st.info("💊 **Current medications:** " + _md("; ".join(pat["drug_history"])))
    st.caption("Tip: on a phone, tap the microphone on your keyboard to dictate into any box. "
               "Leave a vital at 0 if it was not recorded.")
    with st.form(f"pc_visit_{k}"):
        c1, c2 = st.columns(2)
        with c1:
            vdate = st.date_input("Visit date *", value=_dt.date.today(), key=f"pcv_date_{k}")
        with c2:
            vtype = st.selectbox("Visit type", VISIT_TYPES, key=f"pcv_type_{k}")
        complaint = st.text_area("Subjective - how is the patient since the last visit? *", height=90,
                                 key=f"pcv_c_{k}", placeholder="e.g. Cough improving, still febrile overnight...")
        pain = st.slider("Pain score (0 = none)", 0, 10, 0, key=f"pcv_pain_{k}")
        st.markdown("**Vitals** (0 = not recorded)")
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            bps = st.number_input("BP systolic", 0, 300, 0, key=f"pcv_bps_{k}")
            bpd = st.number_input("BP diastolic", 0, 200, 0, key=f"pcv_bpd_{k}")
        with a2:
            hr = st.number_input("HR (bpm)", 0, 300, 0, key=f"pcv_hr_{k}")
            rr = st.number_input("RR (/min)", 0, 80, 0, key=f"pcv_rr_{k}")
        with a3:
            temp = st.number_input("Temp (°C)", 0.0, 45.0, 0.0, 0.1, format="%.1f", key=f"pcv_t_{k}")
            spo2 = st.number_input("SpO₂ (%)", 0, 100, 0, key=f"pcv_s_{k}")
        with a4:
            wt = st.number_input("Weight (kg)", 0.0, 400.0, 0.0, 0.5, format="%.1f", key=f"pcv_w_{k}")
        ros = st.multiselect("Review of systems - positive findings", ROS_OPTIONS, key=f"pcv_ros_{k}")
        ros_notes = st.text_area("ROS details (optional)", height=60, key=f"pcv_rosn_{k}")
        exam = st.text_area("Examination findings", height=90, key=f"pcv_exam_{k}")
        dx = st.text_area("Assessment / working diagnosis *", height=60, key=f"pcv_dx_{k}")
        dx2 = st.text_area("Other problems (one per line)", height=60, key=f"pcv_dx2_{k}")
        st.markdown("**Prescriptions** (drug · dose · route · frequency · duration · notes)")
        rx = []
        for i in range(4):
            r1, r2, r3, r4, r5, r6 = st.columns([3, 2, 1.5, 2, 2, 2])
            lv = "visible" if i == 0 else "collapsed"
            with r1: rd = st.text_input(f"Drug {i + 1}", key=f"pcv_rd{i}_{k}", label_visibility=lv)
            with r2: rdo = st.text_input(f"Dose {i + 1}", key=f"pcv_rdo{i}_{k}", label_visibility=lv)
            with r3: rro = st.text_input(f"Route {i + 1}", key=f"pcv_rro{i}_{k}", label_visibility=lv)
            with r4: rfr = st.text_input(f"Freq {i + 1}", key=f"pcv_rfr{i}_{k}", label_visibility=lv)
            with r5: rdu = st.text_input(f"Duration {i + 1}", key=f"pcv_rdu{i}_{k}", label_visibility=lv)
            with r6: rno = st.text_input(f"Notes {i + 1}", key=f"pcv_rno{i}_{k}", label_visibility=lv)
            rx.append({"drug": rd.strip(), "dose": rdo.strip(), "route": rro.strip(), "freq": rfr.strip(),
                       "duration": rdu.strip(), "notes": rno.strip()})
        plan = st.text_area("Plan / management", height=80, key=f"pcv_plan_{k}")
        tests = st.text_area("Tests ordered (one per line)", height=60, key=f"pcv_tests_{k}")
        refs = st.text_area("Referrals (one per line)", height=50, key=f"pcv_refs_{k}")
        f1, f2 = st.columns(2)
        with f1:
            fdate = st.date_input("Follow-up date (optional)", value=None, key=f"pcv_fd_{k}")
        with f2:
            fnote = st.text_input("Follow-up instructions", key=f"pcv_fn_{k}")
        notes = st.text_area("Learning notes / your reasoning (optional)", height=60, key=f"pcv_notes_{k}")
        go_ = st.form_submit_button("💾 Save visit", use_container_width=True)
    if not go_:
        return
    if not complaint.strip():
        st.error("The subjective / interval history is required.")
        return
    if not dx.strip():
        st.error("The assessment / working diagnosis is required.")
        return
    if bps and bpd and bpd >= bps:
        st.error("Diastolic pressure must be lower than systolic. Check the BP values.")
        return
    if temp and temp < 25:
        st.error("That temperature looks wrong (below 25 °C). Check the value or leave 0.")
        return
    vitals = {}
    if bps and bpd:
        vitals["bp_sys"], vitals["bp_dia"] = float(bps), float(bpd)
    for key, val in (("hr", hr), ("rr", rr), ("temp", temp), ("spo2", spo2), ("weight", wt), ("pain", pain)):
        if val:
            vitals[key] = float(val)
    data = {"complaint": complaint.strip(), "vitals": vitals, "ros_positive": ros, "ros_notes": ros_notes.strip(),
            "exam": exam.strip(), "diagnosis": dx.strip(), "secondary_dx": _lines(dx2),
            "prescriptions": [r for r in rx if r["drug"]], "plan": plan.strip(), "tests": _lines(tests),
            "referrals": _lines(refs), "followup_date": str(fdate) if fdate else "",
            "followup_note": fnote.strip(), "notes": notes.strip()}
    first_today = not [v for v in sel("visits", eq={"patient_id": pat["id"], "author_email": u["email"]})
                       if str(v.get("visit_date")) == str(vdate)]
    row = ins("visits", {"patient_id": pat["id"], "author_email": u["email"], "author_name": u["name"],
                         "visit_date": str(vdate), "visit_type": vtype, "data": data})
    if row:
        if first_today and on_saved:
            try:
                on_saved()
            except Exception:
                pass
        _bump()
        st.session_state["pc_toast"] = "Visit saved."
        st.rerun()


def _lab_form(u, pat):
    n = _form_n()
    k = f"{pat['id']}_{n}"
    st.caption("Enter results you want to track. Use a dot for decimals. A reference range is optional - "
               "if you enter one, the chart flags values outside it (no ranges are supplied by this app).")
    with st.form(f"pc_lab_{k}"):
        c1, c2 = st.columns(2)
        with c1:
            ldate = st.date_input("Result date *", value=_dt.date.today(), key=f"pcl_d_{k}")
        with c2:
            panel = st.text_input("Panel / test name (e.g. CBC, U&E)", key=f"pcl_p_{k}")
        rows = []
        for i in range(8):
            r1, r2, r3, r4, r5 = st.columns([3, 2, 2, 1.5, 1.5])
            lv = "visible" if i == 0 else "collapsed"
            with r1: nm = st.text_input(f"Test {i + 1}", key=f"pcl_n{i}_{k}", label_visibility=lv)
            with r2: val = st.text_input(f"Value {i + 1}", key=f"pcl_v{i}_{k}", label_visibility=lv)
            with r3: un = st.text_input(f"Unit {i + 1}", key=f"pcl_u{i}_{k}", label_visibility=lv)
            with r4: lo = st.text_input(f"Low {i + 1}", key=f"pcl_l{i}_{k}", label_visibility=lv)
            with r5: hi = st.text_input(f"High {i + 1}", key=f"pcl_h{i}_{k}", label_visibility=lv)
            rows.append({"name": nm.strip(), "value": val.strip(), "unit": un.strip(), "low": lo.strip(),
                         "high": hi.strip()})
        go_ = st.form_submit_button("💾 Save results", use_container_width=True)
    if not go_:
        return
    used = [r for r in rows if r["name"] or r["value"]]
    if not used:
        st.error("Enter at least one test and value.")
        return
    if any(not r["name"] or not r["value"] for r in used):
        st.error("Each row needs both a test name and a value.")
        return
    bad = [r["name"] for r in used for fld in ("low", "high") if r[fld] and _num(r[fld]) is None]
    if bad:
        st.error("Reference range values must be numbers (use a dot for decimals): " + ", ".join(sorted(set(bad))))
        return
    if ins("labs", {"patient_id": pat["id"], "author_email": u["email"], "author_name": u["name"],
                    "lab_date": str(ldate), "panel": panel.strip(), "results": used}):
        _bump()
        st.session_state["pc_toast"] = "Results saved."
        st.rerun()


# ─────────────── chart (one patient) ───────────────
def _chart_text(pat, visits, labs, fbs):
    L = [f"VIRTUAL PATIENT CHART - {pat.get('alias')} ({_fmt_age(pat.get('age_years'))}, {pat.get('sex')})",
         "SIMULATED PATIENT - teaching use only", f"Case: {pat.get('title') or '-'}",
         f"Day 1 (admission): {pat.get('admitted_on') or '-'}", ""]
    if pat.get("brief"):
        L += ["PRESENTATION", pat["brief"], ""]
    L.append("ALLERGIES: " + ("; ".join(a.get("substance", "") for a in pat.get("allergies", [])) or "none recorded"))
    L.append("CHRONIC: " + ("; ".join(pat.get("chronic", [])) or "none recorded"))
    L.append("MEDICATIONS: " + ("; ".join(pat.get("drug_history", [])) or "none recorded"))
    L.append("")
    for v in sorted(visits, key=lambda x: (str(x["visit_date"]), str(x.get("created_at")))):
        d = v.get("data") or {}
        day = _day(pat, v["visit_date"])
        L.append(f"--- {v['visit_date']}" + (f" (Day {day})" if day else "") + f" - {v.get('visit_type')} - {v.get('author_name')}")
        for lab, key in (("S", "complaint"), ("Vitals", None), ("Exam", "exam"), ("A", "diagnosis"), ("P", "plan")):
            val = _vitals_line(d.get("vitals") or {}) if key is None else d.get(key)
            if val:
                L.append(f"{lab}: {val}")
        for r in d.get("prescriptions", []):
            L.append("Rx: " + " ".join(x for x in (r.get("drug"), r.get("dose"), r.get("route"), r.get("freq"), r.get("duration")) if x))
        for f in [f for f in fbs if str(f.get("visit_id")) == str(v["id"])]:
            L.append(f"Feedback ({f.get('author_name')}): {f.get('text')}")
        L.append("")
    for lab in sorted(labs, key=lambda x: str(x["lab_date"])):
        L.append(f"--- LAB {lab['lab_date']} {lab.get('panel') or ''}")
        for r in lab.get("results", []):
            L.append(f"{r['name']}: {r['value']} {r.get('unit', '')}".rstrip())
        L.append("")
    return "\n".join(L)


def _chart(u, pid, on_saved):
    pats = sel("patients", eq={"id": pid})
    if not pats:
        st.session_state.pop("pc_open", None)
        st.rerun()
        return
    pat = pats[0]
    if not (_is_mod(u) or pat.get("shared") or _norm(pat.get("owner_email")) == u["email"]):
        st.error("You do not have access to this patient.")
        if st.button("← Back to patients"):
            st.session_state.pop("pc_open", None)
            st.rerun()
        return
    visits = sorted(sel("visits", eq={"patient_id": pid}), key=lambda x: (str(x["visit_date"]), str(x.get("created_at"))))
    labs = sel("labs", eq={"patient_id": pid})
    fbs = sel("feedback", eq={"patient_id": pid}, order="created_at.asc")

    if st.button("← Back to patients", key="pc_back"):
        st.session_state.pop("pc_open", None)
        st.rerun()
    toast = st.session_state.pop("pc_toast", None)
    if toast:
        st.success(toast)
    st.subheader(f"{pat.get('alias')}  ·  {_fmt_age(pat.get('age_years'))}, {pat.get('sex') or ''}")
    st.caption("SIMULATED PATIENT" + (" · class patient (shared)" if pat.get("shared") else "") +
               (f" · {pat['title']}" if pat.get("title") else "") +
               (f" · Case Library #{pat['case_ref']}" if pat.get("case_ref") else ""))
    if pat.get("allergies"):
        st.error("⚠️ **Allergies:** " + _md("; ".join(
            a.get("substance", "") + (f" ({a['reaction']})" if a.get("reaction") else "") for a in pat["allergies"])))
    today_day = _day(pat, _dt.date.today())
    m1, m2, m3 = st.columns(3)
    m1.metric("Visits", len(visits))
    m2.metric("Lab panels", len(labs))
    m3.metric("Hospital day (today)", today_day if today_day and today_day > 0 else "-")

    t_over, t_new, t_vis, t_lab, t_time, t_info = st.tabs(
        ["Overview", "➕ New visit", "Visits", "Labs & trends", "Timeline", "Patient info"])

    with t_over:
        if pat.get("brief"):
            with st.expander("Presentation / admission note", expanded=not visits):
                st.markdown(_md(pat["brief"]))
        if not visits:
            st.info("No visits yet. Open **➕ New visit** to write the first note.")
        else:
            last = visits[-1]
            st.markdown(f"**Latest visit:** {last['visit_date']} · {last.get('visit_type', '')}")
            d = last.get("data") or {}
            if d.get("diagnosis"):
                st.markdown("**Assessment:** " + _md(d["diagnosis"]))
            if _vitals_line(d.get("vitals") or {}):
                st.markdown("**Vitals:** " + _md(_vitals_line(d["vitals"])))
            due = [(v.get("data") or {}).get("followup_date") for v in visits]
            due = [x for x in due if x and x >= str(_dt.date.today())]
            if due:
                st.caption(f"📆 Next follow-up: {min(due)}")
            probs = []
            for v in visits:
                dx = (v.get("data") or {}).get("diagnosis")
                if dx and dx not in probs:
                    probs.append(dx)
            if probs:
                st.markdown("**Assessments over time:** " + _md(" → ".join(probs)))
            if len([v for v in visits if (v.get("data") or {}).get("vitals")]) >= 1:
                pick = st.radio("Vital-sign trend", list(TREND_PARAMS), horizontal=True, key="pc_trend")
                fig = _trend_fig(visits, TREND_PARAMS[pick], pick)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.caption(f"No {pick.lower()} values recorded yet.")
        st.download_button("⬇️ Download chart summary (.txt)", _chart_text(pat, visits, labs, fbs),
                           file_name=f"virtual_patient_{pid}.txt", mime="text/plain")

    with t_new:
        if _can_write(u, pat):
            _visit_form(u, pat, on_saved)
        else:
            st.info("You can read this patient but not add notes.")

    with t_vis:
        if not visits:
            st.caption("No visits yet.")
        for v in reversed(visits):
            _show_visit(v, pat, [f for f in fbs if str(f.get("visit_id")) == str(v["id"])], u)

    with t_lab:
        series = _lab_series(labs)
        if series:
            names = sorted(series.values(), key=lambda s: s["name"].lower())
            pick = st.selectbox("Trend for", [s["name"] for s in names], key="pc_labpick")
            s = series[pick.lower()]
            fig = _lab_fig(s)
            if fig and len(s["pts"]) >= 1:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("This result is not numeric, so it is shown in the table only.")
            rows = []
            for lab in sorted(labs, key=lambda x: str(x["lab_date"]), reverse=True):
                for r in lab.get("results", []):
                    rng = " – ".join(x for x in (r.get("low"), r.get("high")) if x)
                    rows.append({"Date": lab["lab_date"], "Panel": lab.get("panel") or "", "Test": r.get("name"),
                                 "Value": r.get("value"), "Unit": r.get("unit"), "Range you entered": rng,
                                 "Flag": _flag(r.get("value"), r.get("low"), r.get("high"))})
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No lab results yet.")
        if _can_write(u, pat):
            with st.expander("➕ Add lab results", expanded=not labs):
                _lab_form(u, pat)

    with t_time:
        items = [(str(v["visit_date"]), "🩺 Visit", f"{v.get('visit_type', '')} — "
                  f"{(v.get('data') or {}).get('diagnosis', '')}") for v in visits]
        items += [(str(lb["lab_date"]), "🧪 Labs", lb.get("panel") or
                   ", ".join(r.get("name", "") for r in lb.get("results", [])[:4])) for lb in labs]
        if not items:
            st.caption("Nothing recorded yet.")
        for d, kind, txt in sorted(items, reverse=True):
            day = _day(pat, d)
            st.markdown(f"**{d}**" + (f" (Day {day})" if day else "") + f" · {kind} · " + _md(txt))

    with t_info:
        _info(u, pat)


def _info(u, pat):
    if not _can_edit(u, pat):
        st.caption("Only the owner or faculty can edit patient details.")
    st.markdown(f"**Blood group:** {pat.get('blood_group') or 'not recorded'}  ·  "
                f"**Day 1:** {pat.get('admitted_on') or 'not set'}  ·  Created by {pat.get('owner_name') or ''}")
    with st.form(f"pc_info_{pat['id']}"):
        brief = st.text_area("Presentation / admission note", value=pat.get("brief") or "", height=120,
                             disabled=not _can_edit(u, pat))
        allergies = st.text_area("Allergies (one per line: substance | reaction | severity)", height=80,
                                 value="\n".join(" | ".join(x for x in (a.get("substance"), a.get("reaction"), a.get("severity")) if x)
                                                 for a in pat.get("allergies", [])), disabled=not _can_edit(u, pat))
        chronic = st.text_area("Chronic conditions (one per line)", value="\n".join(pat.get("chronic", [])),
                               height=70, disabled=not _can_edit(u, pat))
        meds = st.text_area("Current medications (one per line)", value="\n".join(pat.get("drug_history", [])),
                            height=80, disabled=not _can_edit(u, pat))
        saved = st.form_submit_button("💾 Save patient details", disabled=not _can_edit(u, pat))
    if saved and _can_edit(u, pat):
        al = []
        for line in _lines(allergies):
            p = [x.strip() for x in line.split("|")]
            al.append({"substance": p[0], "reaction": p[1] if len(p) > 1 else "", "severity": p[2] if len(p) > 2 else ""})
        if upd("patients", pat["id"], {"brief": brief.strip(), "allergies": al, "chronic": _lines(chronic),
                                       "drug_history": _lines(meds)}):
            st.session_state["pc_toast"] = "Patient details saved."
            st.rerun()
        else:
            st.error("Could not save.")
    if _can_edit(u, pat):
        with st.expander("Archive this patient"):
            st.caption("Archiving hides the patient from the lists. Notes are kept in the database.")
            sure = st.checkbox("Yes, archive this patient", key=f"pc_arch_{pat['id']}")
            if st.button("Archive", disabled=not sure, key=f"pc_archbtn_{pat['id']}"):
                if upd("patients", pat["id"], {"archived": True}):
                    st.session_state.pop("pc_open", None)
                    st.rerun()


# ─────────────── patient list + create ───────────────
def _list(u):
    pats = _visible_patients(u)
    if not pats:
        st.info("No simulated patients yet. Create one in the **New simulated patient** tab"
                + (" - or ask faculty to share a class patient." if not _is_mod(u) else "."))
        return
    ids = [p["id"] for p in pats]
    vcount = {}
    for v in sel("visits", in_=("patient_id", ids)):
        vcount[str(v["patient_id"])] = vcount.get(str(v["patient_id"]), 0) + 1
    for p in pats:
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"**{_md(p.get('alias'))}** · {_fmt_age(p.get('age_years'))}, {p.get('sex') or ''}")
                bits = [p.get("title") or "", f"{vcount.get(str(p['id']), 0)} visit(s)",
                        "class patient" if p.get("shared") else "private"]
                if _is_mod(u) and not p.get("shared"):
                    bits.append(f"by {p.get('owner_name') or p.get('owner_email')}")
                st.caption(" · ".join(b for b in bits if b))
            with c2:
                if st.button("Open", key=f"pc_open_{p['id']}", use_container_width=True):
                    st.session_state["pc_open"] = p["id"]
                    st.rerun()


def _new_patient(u, case_loader):
    st.warning(SIM_BANNER)
    lib = None
    if case_loader:
        try:
            df = case_loader()
            if df is not None and len(df):
                opts = {"— start from scratch —": None}
                for i, row in df.iterrows():
                    cid = str(row.get("Case_ID", "")).replace(".0", "")
                    opts[f"#{cid} · {row.get('Title', '')} ({row.get('System', '')})"] = row
                pick = st.selectbox("Start from a Case Library case (optional)", list(opts), key="pc_libpick",
                                    help="Copies presentation, history and medications. The final diagnosis and "
                                         "investigation results are NOT copied, so you can work the case up yourself.")
                lib = _from_library(opts[pick]) if opts[pick] is not None else None
                if lib:
                    st.caption("Pre-filled from the Case Library. Give the patient a fictional name and check the details.")
        except Exception:
            lib = None
    lib = lib or {"title": "", "age": 0.0, "sex": SEXES[0], "brief": "", "chronic": "", "meds": "", "case_ref": ""}
    k = f"{_form_n()}_{lib['case_ref'] or 'x'}"
    with st.form(f"pc_new_{k}"):
        alias = st.text_input("Fictional name *", key=f"pcn_alias_{k}", placeholder='e.g. "Mr A (virtual)"')
        c1, c2, c3 = st.columns(3)
        with c1:
            age = st.number_input("Age (years) *", 0.0, 120.0, float(lib["age"]), 0.5, key=f"pcn_age_{k}",
                                  help="Use fractions for infants, e.g. 0.5 = six months.")
        with c2:
            sex = st.selectbox("Sex", SEXES, index=SEXES.index(lib["sex"]), key=f"pcn_sex_{k}")
        with c3:
            blood = st.selectbox("Blood group", BLOODS, key=f"pcn_bg_{k}")
        title = st.text_input("Case title", value=lib["title"], key=f"pcn_title_{k}")
        adm = st.date_input("Day 1 (admission / first visit)", value=_dt.date.today(), key=f"pcn_adm_{k}")
        brief = st.text_area("Presentation / admission note", value=lib["brief"], height=120, key=f"pcn_brief_{k}")
        al = st.text_area("Allergies (one per line: substance | reaction | severity)", height=70, key=f"pcn_al_{k}")
        chronic = st.text_area("Chronic conditions (one per line)", value=lib["chronic"], height=70, key=f"pcn_ch_{k}")
        meds = st.text_area("Current medications (one per line)", value=lib["meds"], height=70, key=f"pcn_me_{k}")
        shared = False
        if _is_mod(u):
            shared = st.checkbox("Share with all students as a class teaching patient", key=f"pcn_sh_{k}")
        sure = st.checkbox("I confirm this is a simulated patient and contains no real patient information.",
                           key=f"pcn_ok_{k}")
        go_ = st.form_submit_button("Create patient", use_container_width=True)
    if not go_:
        return
    if not alias.strip():
        st.error("Give the patient a fictional name.")
        return
    if age <= 0:
        st.error("Enter the age (use a fraction of a year for infants).")
        return
    if not sure:
        st.error("Please tick the confirmation that this is a simulated patient.")
        return
    alist = []
    for line in _lines(al):
        p = [x.strip() for x in line.split("|")]
        alist.append({"substance": p[0], "reaction": p[1] if len(p) > 1 else "", "severity": p[2] if len(p) > 2 else ""})
    row = ins("patients", {"owner_email": u["email"], "owner_name": u["name"], "shared": bool(shared),
                           "alias": alias.strip(), "age_years": float(age), "sex": sex,
                           "blood_group": None if blood == BLOODS[0] else blood, "title": title.strip(),
                           "admitted_on": str(adm), "brief": brief.strip(), "allergies": alist,
                           "chronic": _lines(chronic), "drug_history": _lines(meds),
                           "case_ref": lib["case_ref"] or None})
    if row:
        _bump()
        st.session_state["pc_open"] = row["id"]
        st.session_state["pc_toast"] = "Patient created. Open ➕ New visit to write the first note."
        st.rerun()


def render_patient_chart(case_loader=None, on_visit_saved=None):
    u = _user()
    st.markdown("### 🩺 Patient Chart — Daily Rounds")
    st.caption("Follow simulated patients day by day: write SOAP-style visit notes, record vitals and labs, "
               "and watch the trends build. Practice for ward rounds and follow-up clinics.")
    if not _sb():
        st.warning("DEMO MODE: Supabase is not configured, so nothing is saved after this session.")
    elif not _ready():
        st.error("The Patient Chart tables are not in Supabase yet. Run **patient_chart.sql** in the Supabase "
                 f"SQL Editor, then reload this page. ({st.session_state.get('pc_last_err', '')})")
        return
    if st.session_state.get("pc_open"):
        _chart(u, st.session_state["pc_open"], on_visit_saved)
        return
    toast = st.session_state.pop("pc_toast", None)
    if toast:
        st.success(toast)
    t = st.tabs(["My patients", "New simulated patient", "Rules"])
    with t[0]:
        _list(u)
    with t[1]:
        _new_patient(u, case_loader)
    with t[2]:
        st.warning(SIM_BANNER)
        for h, b in RULES:
            st.markdown(f"**{h}**")
            st.write(b)
