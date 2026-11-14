"""
patient_chart.py - Patient Chart / Daily Rounds for the MLS Virtual Hospital (additive, standalone).

Ported from the MLS-PatientChart app for TEACHING. Students (and faculty) follow SIMULATED patients across days:
daily ward rounds and follow-up visits (SOAP-style notes with vitals, review of systems per system, exam, diagnosis,
prescriptions, plan, procedures, referrals, tests, follow-up), investigations with attached files, hospital-stay
episodes, the full history (allergies, chronic conditions, drug, surgical, family, social, obstetric, paediatric),
a timeline, trends, and a prescription PDF with the MLS Virtual Hospital stamp and signature block.
Faculty can share class patients and leave feedback on any note.

Safety by design:
  - simulated patients only: no fields for phone, national ID, date of birth, address or photo; a confirmation is
    required when a patient is created
  - nothing is rendered as raw HTML (all user text is shown as plain text)
  - no clinical reference values are shipped: lab ranges are only what the user types in
  - uploaded images are re-encoded (metadata stripped); every upload needs a de-identification confirmation
  - the prescription PDF always carries a SIMULATED watermark and banner (see patient_chart_pdf.py)

Files: patient_chart.py (this), patient_chart_sections.py (investigations, hospital stays, timeline, history,
paediatrics), patient_chart_pdf.py, and the SQL: patient_chart.sql then patient_chart_v2.sql.
Storage: Supabase (same SUPABASE_URL / SUPABASE_KEY secrets as the app); otherwise a labelled DEMO mode.

Hook-up in app.py:
    from patient_chart import render_patient_chart
    render_patient_chart(case_loader=load_cases, on_visit_saved=<optional callback>)
"""
import datetime as _dt
import json
import re
import requests
import streamlit as st

T = {"patients": "vh_pc_patients", "visits": "vh_pc_visits", "feedback": "vh_pc_feedback",
     "hospitalisations": "vh_pc_hospitalisations", "investigations": "vh_pc_investigations",
     "files": "vh_pc_files"}

SIM_BANNER = ("**Simulated patients only.** Never type a real patient's name, ID number, phone, date of birth, "
              "address or photo - or any detail that could identify a real person. This chart has no fields for "
              "those on purpose.")

VISIT_TYPES = ["Follow-up", "Daily ward round", "New complaint", "Routine check-up", "Emergency", "Procedure",
               "Results review", "Discharge review", "Other"]
SEXES = ["Female", "Male", "Other / not stated"]
BLOODS = ["Not recorded", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
ROS_SYSTEMS = [
    ("General (fever, weight loss, fatigue, night sweats)", "ros_general"),
    ("Cardiovascular (chest pain, palpitations, oedema, DOE)", "ros_cardio"),
    ("Respiratory (cough, dyspnoea, wheeze, haemoptysis)", "ros_resp"),
    ("GI (nausea, vomiting, diarrhoea, abdominal pain, bleeding)", "ros_gi"),
    ("Neurological (headache, dizziness, weakness, numbness, seizures)", "ros_neuro"),
    ("MSK (joint pain, swelling, stiffness, back pain)", "ros_msk"),
    ("Urinary (dysuria, frequency, haematuria, incontinence)", "ros_urinary"),
    ("Dermatological (rash, pruritus, skin changes)", "ros_derm"),
    ("ENT (sore throat, ear pain, nasal congestion, hearing loss)", "ros_ent"),
    ("Psychiatric (mood, sleep, anxiety, cognition)", "ros_psych"),
    ("Endocrine (polyuria, polydipsia, weight change, heat/cold intolerance)", "ros_endo"),
    ("Haematological (bruising, bleeding, lymphadenopathy)", "ros_haem"),
    ("Reproductive / Obstetric", "ros_repro"),
]
ROS_OPTIONS = [a for a, _ in ROS_SYSTEMS]
ROS_SLUG = dict(ROS_SYSTEMS)
ROS_BY_SLUG = {b: a for a, b in ROS_SYSTEMS}
FOLLOWUPS = ["", "1 week", "2 weeks", "1 month", "3 months", "6 months", "1 year", "As needed", "Custom"]
TREND_PARAMS = {"Blood pressure": ("bp_sys", "bp_dia"), "Heart rate": ("hr",), "Temperature": ("temp",),
                "SpO₂": ("spo2",), "Respiratory rate": ("rr",), "Weight": ("weight",), "Pain score": ("pain",)}
VITAL_LABEL = {"bp_sys": "Systolic", "bp_dia": "Diastolic", "hr": "HR", "temp": "Temp", "spo2": "SpO₂",
               "rr": "RR", "weight": "Weight", "pain": "Pain"}
RULES = [
    ("Simulated patients only",
     "Create fictional patients (or start from a Case Library case). Never enter a real patient's identity or "
     "details. Real patient care belongs in your hospital's own record system, not here."),
    ("What is saved",
     "Your patients, notes, vitals, investigations and files are saved in the hospital database under your "
     "account. Faculty can view all simulated patients to give feedback. Shared class patients are visible to "
     "every student."),
    ("Files",
     "Attach only de-identified images (JPG/PNG) or PDFs. Remove names, ID numbers, hospital labels and dates "
     "of birth first. Images are re-encoded to strip hidden metadata; PDFs are stored as uploaded. DICOM files "
     "are not accepted because they carry identifiers in their headers."),
    ("No reference values are supplied",
     "This chart does not ship normal ranges. If you type a reference range with a result, the chart flags "
     "values outside the range you entered - check the range against your lab's own source."),
    ("Prescription PDF",
     "The PDF carries a permanent SIMULATED watermark and banner. It is a training document and is not a valid "
     "prescription."),
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
    d = st.session_state.setdefault("pc_demo", {})
    for t in T:
        d.setdefault(t, [])
    return d


def _now():
    return _dt.datetime.utcnow().isoformat(timespec="seconds")


def _norm(x):
    return str(x).strip().lower()


def sel(t, eq=None, in_=None, order=None, limit=None, cols="*"):
    """Read rows. eq={col: value}; in_=(col, [values]); cols = PostgREST select list."""
    cfg = _sb()
    if cfg:
        base, k = cfg
        p = {"select": cols}
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
    return json.loads(json.dumps(rows[:limit] if limit else rows, default=str))


def ins(t, row):
    cfg = _sb()
    if cfg:
        base, k = cfg
        try:
            r = requests.post(f"{base}/rest/v1/{T[t]}", headers=_h(k), json=row, timeout=20)
            if r.status_code in (200, 201):
                j = r.json()
                return j[0] if j else row
            st.session_state["pc_last_err"] = f"{r.status_code}: {r.text[:200]}"
        except Exception as e:
            st.session_state["pc_last_err"] = str(e)[:200]
        st.error("Could not save. Check that patient_chart.sql and patient_chart_v2.sql have been run in "
                 f"Supabase. ({st.session_state.get('pc_last_err', '')})")
        return None
    d = _demo()
    row = dict(row)
    row["id"] = max([r["id"] for r in d[t]] or [0]) + 1
    row["created_at"] = _now()
    row.setdefault("archived", False)
    row.setdefault("shared", False)
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


def dele(t, rid):
    cfg = _sb()
    if cfg:
        base, k = cfg
        try:
            r = requests.delete(f"{base}/rest/v1/{T[t]}", headers=_h(k), params={"id": f"eq.{rid}"}, timeout=10)
            return r.status_code in (200, 204)
        except Exception:
            return False
    d = _demo()
    d[t] = [r for r in d[t] if str(r["id"]) != str(rid)]
    if t == "investigations":
        d["files"] = [r for r in d["files"] if str(r.get("investigation_id")) != str(rid)]
    return True


def _ready():
    """True when the Supabase tables exist (or in demo mode)."""
    if not _sb():
        return True
    if st.session_state.get("pc_ready"):
        return True
    base, k = _sb()
    ok = True
    for t in ("patients", "investigations"):
        try:
            r = requests.get(f"{base}/rest/v1/{T[t]}", headers=_h(k), params={"select": "id", "limit": "1"},
                             timeout=10)
            if r.status_code != 200:
                ok = False
                st.session_state["pc_last_err"] = f"{T[t]} -> {r.status_code}: {r.text[:160]}"
                break
        except Exception as e:
            ok = False
            st.session_state["pc_last_err"] = str(e)[:200]
            break
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


def _can_delete(u, pat, row):
    return _can_edit(u, pat) or _norm(row.get("author_email")) == u["email"]


def _is_paed(pat):
    n = _num(pat.get("age_years"))
    return n is not None and 0 < n < 18


def _fmt_age(a):
    n = _num(a)
    if n is None:
        return "age ?"
    return f"{int(n)} y" if n >= 1 and n == int(n) else f"{n:g} y"


def _drugs(pat):
    """Drug history as a list of dicts (older rows may hold plain strings)."""
    out = []
    for m in pat.get("drug_history") or []:
        out.append(m if isinstance(m, dict) else {"name": str(m), "status": "current"})
    return out


def _hist(pat):
    h = pat.get("history")
    return h if isinstance(h, dict) else {}


def _vitals_line(vt):
    p = []
    if vt.get("bp_sys") and vt.get("bp_dia"):
        p.append(f"BP {vt['bp_sys']:g}/{vt['bp_dia']:g} mmHg")
    for k, lab, unit in (("hr", "HR", "bpm"), ("rr", "RR", "/min"), ("temp", "Temp", "°C"),
                         ("spo2", "SpO₂", "%"), ("weight", "Wt", "kg"), ("height", "Ht", "cm"),
                         ("bmi", "BMI", ""), ("pain", "Pain", "/10")):
        if vt.get(k):
            p.append(f"{lab} {vt[k]:g} {unit}".strip())
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


def _visible_patients(u):
    if _is_mod(u):
        rows = sel("patients", order="created_at.desc")
    else:
        rows = {r["id"]: r for r in sel("patients", eq={"owner_email": u["email"]}, order="created_at.desc")}
        rows.update({r["id"]: r for r in sel("patients", eq={"shared": True}, order="created_at.desc")})
        rows = sorted(rows.values(), key=lambda r: str(r.get("created_at", "")), reverse=True)
    return [r for r in rows if not r.get("archived")]


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


# ─────────────── visit display ───────────────
@st.cache_data(show_spinner=False, max_entries=300)
def _rx_pdf(pat_json, visit_json, day, reviewer):
    from patient_chart_pdf import prescription_pdf
    return prescription_pdf(json.loads(pat_json), json.loads(visit_json), day=day, reviewer=reviewer)


def show_visit(v, pat, fbs, u, invs=None, ctx="visits", full=True):
    """Render one visit. ctx keeps widget keys unique when the same visit shows on several tabs."""
    d = v.get("data") or {}
    day = _day(pat, v.get("visit_date"))
    head = f"{v.get('visit_date')}" + (f" · Day {day}" if day else "") + f" · {v.get('visit_type', '')}"
    with st.container(border=True):
        st.markdown(f"**🗒 {head}**")
        st.caption(f"Written by {v.get('author_name') or 'unknown'}")
        if d.get("complaint"):
            st.markdown("**Chief complaint:** " + _md(d["complaint"]))
        vl = _vitals_line(d.get("vitals") or {})
        if vl:
            st.markdown("**Vitals:** " + _md(vl))
        sysn = d.get("ros_system_notes") or {}
        if d.get("ros_positive") or d.get("ros_notes"):
            st.markdown("**🔎 Review of systems:**")
            for lab in d.get("ros_positive", []):
                slug = ROS_SLUG.get(lab, "")
                short = lab.split("(")[0].strip()
                st.markdown(f"- **{_md(short)}**" + (": " + _md(sysn[slug]) if sysn.get(slug) else ""))
            if d.get("ros_notes"):
                st.markdown(_md(d["ros_notes"]))
        if d.get("exam"):
            st.markdown("**🔍 Examination:** " + _md(d["exam"]))
        st.markdown("**🏷️ Primary diagnosis:** " + _md(d.get("diagnosis") or "-") +
                    (("  \n**Secondary:** " + _md("; ".join(d["secondary_dx"]))) if d.get("secondary_dx") else ""))
        rx = [r for r in d.get("prescriptions", []) if r.get("drug")]
        if rx:
            st.markdown("**💊 Prescriptions:**  \n" + "  \n".join(
                "• " + _md(" ".join(x for x in (r.get("drug"), r.get("dose"), r.get("route"),
                                               r.get("frequency") or r.get("freq"),
                                               (f"× {r['duration']}" if r.get("duration") else ""),
                                               (f"({r['notes']})" if r.get("notes") else "")) if x))
                for r in rx))
        if d.get("plan"):
            st.markdown("**📋 Plan / management:** " + _md(d["plan"]))
        for lab, key in (("⚕️ Procedures", "procedures"), ("🔀 Referrals", "referrals"),
                         ("🧪 Tests ordered", "tests_ordered")):
            if d.get(key):
                st.markdown(f"**{lab}:** " + _md("; ".join(d[key])))
        linked = [i for i in (invs or []) if str(i.get("visit_id")) == str(v["id"])]
        for i in linked:
            lv = " | ".join(f"{x.get('name')}: {x.get('value')} {x.get('unit', '')}".strip()
                            for x in i.get("lab_values") or [])
            st.markdown(f"🔬 **{_md(i.get('label'))}** ({i.get('inv_date')})" + (" — " + _md(lv) if lv else ""))
        if d.get("followup_date") or d.get("followup_instructions"):
            st.markdown("**📆 Follow-up:** " + _md(" — ".join(
                x for x in (d.get("followup_date"), d.get("followup_instructions")) if x)))
        if d.get("clinical_notes"):
            st.markdown("**📝 Clinical notes:** " + _md(d["clinical_notes"]))
        if d.get("doctor_note"):
            st.markdown("**🗒️ Doctor's note:** " + _md(d["doctor_note"]))
        for f in fbs:
            st.info(f"🧑‍🏫 **{_md(f.get('author_name') or 'Faculty')}:** {_md(f.get('text', ''))}")
        if full and rx:
            try:
                pdf = _rx_pdf(json.dumps(pat, default=str), json.dumps(v, default=str), day,
                              (fbs[-1].get("author_name") if fbs else None))
                st.download_button("📄 Prescription PDF (simulation)", pdf, key=f"pc_pdf_{ctx}_{v['id']}",
                                   file_name=f"prescription_{pat['id']}_{v.get('visit_date')}.pdf",
                                   mime="application/pdf")
            except Exception as e:
                st.caption(f"PDF not available ({str(e)[:80]}).")
        if full and _is_mod(u):
            with st.form(f"pc_fb_{ctx}_{v['id']}", clear_on_submit=True):
                txt = st.text_input("Feedback for the student", key=f"pc_fbt_{ctx}_{v['id']}",
                                    placeholder="e.g. Good assessment - what would you recheck tomorrow?")
                if st.form_submit_button("Send feedback"):
                    if txt.strip():
                        ins("feedback", {"patient_id": pat["id"], "visit_id": v["id"], "author_email": u["email"],
                                         "author_name": u["name"], "text": txt.strip()[:1000]})
                        st.rerun()
                    else:
                        st.warning("Type some feedback first.")


# ─────────────── visit form ───────────────
def _form_n():
    return st.session_state.setdefault("pc_form_n", 0)


def _bump():
    st.session_state["pc_form_n"] = _form_n() + 1


def _visit_form(u, pat, on_saved):
    n = _form_n()
    k = f"{pat['id']}_{n}"
    cur = [m for m in _drugs(pat) if m.get("status", "current") == "current"]
    if cur:
        st.info("💊 **Current medications:** " + _md("; ".join(
            " ".join(x for x in (m.get("name"), m.get("dose"), m.get("frequency")) if x) for m in cur)))
    st.caption("Tip: on a phone, tap the microphone on your keyboard to dictate into any box. "
               "Leave a vital at 0 if it was not recorded.")

    st.markdown("##### 🔎 Review of systems")
    st.caption("Tick every system with positive findings; a findings box appears for each one.")
    ros = st.multiselect("Positive systems", ROS_OPTIONS, key=f"pcv_ros_{k}")
    for lab in ros:
        short = lab.split("(")[0].strip()
        st.text_area(f"Findings — {short}", key=f"pcv_rosn_{ROS_SLUG[lab]}_{k}", height=68)

    rxn = st.session_state.get(f"pcv_rxn_{k}", 3)
    with st.form(f"pc_visit_{k}"):
        st.markdown("##### 📅 Date & visit type")
        c1, c2 = st.columns(2)
        with c1:
            vdate = st.date_input("Visit date *", value=_dt.date.today(), key=f"pcv_date_{k}")
        with c2:
            vtype = st.selectbox("Visit type", VISIT_TYPES, key=f"pcv_type_{k}")
        st.markdown("##### 🗣 Presenting complaint")
        complaint = st.text_area("Chief complaint / interval history *", height=90, key=f"pcv_c_{k}",
                                 placeholder="e.g. 3-day history of productive cough with fever...")
        pain = st.slider("Pain score (0 = none, 10 = worst)", 0, 10, 0, key=f"pcv_pain_{k}")
        st.markdown("##### 🩺 Vitals (0 = not recorded)")
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            bps = st.number_input("BP systolic (mmHg)", 0, 300, 0, key=f"pcv_bps_{k}")
            bpd = st.number_input("BP diastolic (mmHg)", 0, 200, 0, key=f"pcv_bpd_{k}")
        with a2:
            hr = st.number_input("HR (bpm)", 0, 300, 0, key=f"pcv_hr_{k}")
            rr = st.number_input("RR (/min)", 0, 80, 0, key=f"pcv_rr_{k}")
        with a3:
            temp = st.number_input("Temp (°C)", 0.0, 45.0, 0.0, 0.1, format="%.1f", key=f"pcv_t_{k}")
            spo2 = st.number_input("SpO₂ (%)", 0, 100, 0, key=f"pcv_s_{k}")
        with a4:
            wt = st.number_input("Weight (kg)", 0.0, 400.0, 0.0, 0.5, format="%.1f", key=f"pcv_w_{k}")
            ht = st.number_input("Height (cm)", 0.0, 250.0, 0.0, 0.5, format="%.1f", key=f"pcv_h_{k}")
        ros_notes = st.text_area("General ROS notes (optional)", height=50, key=f"pcv_rosg_{k}")
        st.markdown("##### 🔍 Examination findings")
        exam = st.text_area("Examination findings", height=90, key=f"pcv_exam_{k}",
                            placeholder="e.g. Alert, no respiratory distress. Bilateral lower-zone crackles...")
        st.markdown("##### 🏷️ Diagnosis / assessment")
        dx = st.text_area("Primary diagnosis *", height=60, key=f"pcv_dx_{k}",
                          placeholder="e.g. Community-acquired pneumonia")
        dx2 = st.text_area("Secondary / co-existing diagnoses (one per line)", height=60, key=f"pcv_dx2_{k}")
        st.markdown("##### 💊 Prescription")
        st.caption("Drug · Dose · Route · Frequency · Duration · Notes")
        rx = []
        for i in range(rxn):
            r1, r2, r3, r4, r5, r6 = st.columns([3, 2, 1.5, 2, 2, 2])
            lv = "visible" if i == 0 else "collapsed"
            with r1: rd = st.text_input(f"Drug {i + 1}", key=f"pcv_rd{i}_{k}", label_visibility=lv)
            with r2: rdo = st.text_input(f"Dose {i + 1}", key=f"pcv_rdo{i}_{k}", label_visibility=lv)
            with r3: rro = st.text_input(f"Route {i + 1}", key=f"pcv_rro{i}_{k}", label_visibility=lv)
            with r4: rfr = st.text_input(f"Frequency {i + 1}", key=f"pcv_rfr{i}_{k}", label_visibility=lv)
            with r5: rdu = st.text_input(f"Duration {i + 1}", key=f"pcv_rdu{i}_{k}", label_visibility=lv)
            with r6: rno = st.text_input(f"Notes {i + 1}", key=f"pcv_rno{i}_{k}", label_visibility=lv)
            rx.append({"drug": rd.strip(), "dose": rdo.strip(), "route": rro.strip(), "frequency": rfr.strip(),
                       "duration": rdu.strip(), "notes": rno.strip()})
        add_rx = st.form_submit_button("➕ Add prescription row")
        plan = st.text_area("Plan / management notes", height=80, key=f"pcv_plan_{k}")
        st.markdown("##### ⚕️ Procedures & referrals")
        p1, p2 = st.columns(2)
        with p1:
            procs = st.text_area("Procedures performed (one per line)", height=70, key=f"pcv_proc_{k}")
        with p2:
            refs = st.text_area("Referrals made (one per line)", height=70, key=f"pcv_refs_{k}")
        st.markdown("##### 🧪 Tests ordered this visit")
        tests = st.text_area("Tests ordered (one per line)", height=70, key=f"pcv_tests_{k}")
        st.markdown("##### 📆 Follow-up")
        f1, f2 = st.columns(2)
        with f1:
            fu = st.selectbox("Return in", FOLLOWUPS, key=f"pcv_fu_{k}")
            fu_custom = st.text_input("If 'Custom': period or date", key=f"pcv_fuc_{k}")
        with f2:
            fnote = st.text_area("Follow-up instructions / safety netting", height=90, key=f"pcv_fn_{k}")
        st.markdown("##### 📝 Notes")
        cnotes = st.text_area("Clinical notes (free narrative)", height=70, key=f"pcv_cn_{k}")
        dnote = st.text_area("Doctor's visit note (typed memo)", height=70, key=f"pcv_dn_{k}")
        go_ = st.form_submit_button("💾 Save complete visit", use_container_width=True)

    if add_rx:
        st.session_state[f"pcv_rxn_{k}"] = rxn + 1
        st.rerun()
    if not go_:
        return
    if not complaint.strip():
        st.error("The chief complaint / interval history is required.")
        return
    if not dx.strip():
        st.error("The primary diagnosis is required.")
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
    for key, val in (("hr", hr), ("rr", rr), ("temp", temp), ("spo2", spo2), ("weight", wt), ("height", ht),
                     ("pain", pain)):
        if val:
            vitals[key] = float(val)
    if wt and ht:
        vitals["bmi"] = round(wt / ((ht / 100) ** 2), 1)
    sysn = {}
    for lab in ros:
        txt = (st.session_state.get(f"pcv_rosn_{ROS_SLUG[lab]}_{k}") or "").strip()
        if txt:
            sysn[ROS_SLUG[lab]] = txt
    data = {"complaint": complaint.strip(), "vitals": vitals, "ros_positive": ros, "ros_system_notes": sysn,
            "ros_notes": ros_notes.strip(), "exam": exam.strip(), "diagnosis": dx.strip(),
            "secondary_dx": _lines(dx2), "prescriptions": [r for r in rx if r["drug"]], "plan": plan.strip(),
            "procedures": _lines(procs), "referrals": _lines(refs), "tests_ordered": _lines(tests),
            "followup_date": (fu_custom.strip() if fu == "Custom" else fu), "followup_instructions": fnote.strip(),
            "clinical_notes": cnotes.strip(), "doctor_note": dnote.strip()}
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


# ─────────────── chart (one patient) ───────────────
def _chart_text(pat, visits, invs, hosps, fbs):
    L = [f"VIRTUAL PATIENT CHART - {pat.get('alias')} ({_fmt_age(pat.get('age_years'))}, {pat.get('sex')})",
         "SIMULATED PATIENT - teaching use only", f"Case: {pat.get('title') or '-'}",
         f"Day 1 (admission): {pat.get('admitted_on') or '-'}", ""]
    if pat.get("brief"):
        L += ["PRESENTATION", pat["brief"], ""]
    L.append("ALLERGIES: " + ("; ".join(a.get("substance", "") for a in pat.get("allergies", [])) or "none recorded"))
    L.append("CHRONIC: " + ("; ".join(pat.get("chronic", [])) or "none recorded"))
    L.append("MEDICATIONS: " + ("; ".join(
        " ".join(x for x in (m.get("name"), m.get("dose"), m.get("frequency")) if x) +
        ("" if m.get("status", "current") == "current" else " (past)") for m in _drugs(pat)) or "none recorded"))
    L.append("")
    for h in sorted(hosps, key=lambda x: str(x["admit_date"])):
        hd = h.get("data") or {}
        L.append(f"--- ADMISSION {h['admit_date']} -> {h.get('discharge_date') or 'ongoing'} - {hd.get('hospital_name', '')}")
        for lab, key in (("Reason", "reason_for_admission"), ("Admitting Dx", "admitting_diagnosis"),
                         ("Course", "in_hospital_course"), ("Discharge Dx", "discharge_diagnosis"),
                         ("Discharge meds", "discharge_medications"), ("Outcome", "outcome")):
            if hd.get(key):
                L.append(f"{lab}: {hd[key]}")
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
            L.append("Rx: " + " ".join(x for x in (r.get("drug"), r.get("dose"), r.get("route"),
                                                    r.get("frequency") or r.get("freq"), r.get("duration")) if x))
        for f in [f for f in fbs if str(f.get("visit_id")) == str(v["id"])]:
            L.append(f"Feedback ({f.get('author_name')}): {f.get('text')}")
        L.append("")
    for i in sorted(invs, key=lambda x: str(x["inv_date"])):
        L.append(f"--- {i.get('kind')} {i['inv_date']} {i.get('label') or ''}")
        if i.get("notes"):
            L.append(i["notes"])
        for r in i.get("lab_values") or []:
            L.append(f"{r.get('name')}: {r.get('value')} {r.get('unit', '')}".rstrip())
        L.append("")
    return "\n".join(L)


def _header(pat, visits, invs, hosps):
    st.subheader(f"{pat.get('alias')}  ·  {_fmt_age(pat.get('age_years'))}, {pat.get('sex') or ''}")
    st.caption("SIMULATED PATIENT" + (" · class patient (shared)" if pat.get("shared") else "") +
               (f" · {pat['title']}" if pat.get("title") else "") +
               (f" · Case Library #{pat['case_ref']}" if pat.get("case_ref") else "") +
               (f" · 🩸 {pat['blood_group']}" if pat.get("blood_group") else ""))
    if pat.get("allergies"):
        st.error("⚠️ **ALLERGIES:** " + _md("; ".join(
            a.get("substance", "") + (f" ({a['reaction']})" if a.get("reaction") else "") +
            (f" - {a['severity']}" if a.get("severity") else "") for a in pat["allergies"])))
    if _is_paed(pat):
        ph = _hist(pat).get("paediatric") or {}
        bits = [f"🧒 **PAEDIATRIC PATIENT** — age {_fmt_age(pat.get('age_years'))}"]
        if ph.get("birth_weight_g"): bits.append(f"BW {ph['birth_weight_g']} g")
        if ph.get("gestational_age_weeks"): bits.append(f"GA {ph['gestational_age_weeks']} wks")
        if ph.get("nicu_stay"): bits.append("NICU")
        if ph.get("growth_records"): bits.append(f"📏 {len(ph['growth_records'])} growth record(s)")
        if ph.get("immunisations"): bits.append(f"💉 {len(ph['immunisations'])} vaccine(s)")
        st.info(" | ".join(bits))
    if pat.get("chronic"):
        st.markdown("**🔁 Chronic:** " + _md(" · ".join(pat["chronic"])))
    sh = _hist(pat).get("social") or {}
    snip = []
    if sh.get("smoking_status", "never") != "never":
        snip.append(f"🚬 {sh['smoking_status']}" + (f" ({sh['pack_years']} pack-yrs)" if sh.get("pack_years") else ""))
    if sh.get("alcohol_status", "none") != "none":
        snip.append(f"🍷 {sh['alcohol_status']}")
    if sh.get("occupation"):
        snip.append(f"💼 {sh['occupation']}")
    if snip:
        st.caption(" · ".join(snip))
    today_day = _day(pat, _dt.date.today())
    st.markdown(f"🗒 **{len(visits)}** visit(s) · 🏥 **{len(hosps)}** admission(s) · 🔬 **{len(invs)}** "
                f"investigation(s)" + (f" · 📆 Hospital day **{today_day}**" if today_day and today_day > 0 else ""))


def _chart(u, pid, on_saved):
    import patient_chart_sections as S
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
    invs = sorted(sel("investigations", eq={"patient_id": pid}), key=lambda x: (str(x["inv_date"]), str(x.get("created_at"))))
    hosps = sorted(sel("hospitalisations", eq={"patient_id": pid}), key=lambda x: str(x["admit_date"]))
    fbs = sel("feedback", eq={"patient_id": pid}, order="created_at.asc")

    if st.button("← Back to patients", key="pc_back"):
        st.session_state.pop("pc_open", None)
        st.rerun()
    toast = st.session_state.pop("pc_toast", None)
    if toast:
        st.success(toast)
    _header(pat, visits, invs, hosps)

    labels = ["Overview", "➕ New visit", "Visits", "🔬 Investigations", "🏥 Admissions", "📅 Timeline", "📋 History"]
    paed = _is_paed(pat)
    if paed:
        labels.append("🧒 Paediatrics")
    labels.append("⚙️ Case")
    tabs = dict(zip(labels, st.tabs(labels)))

    def fbs_for(v):
        return [f for f in fbs if str(f.get("visit_id")) == str(v["id"])]

    with tabs["Overview"]:
        if pat.get("brief"):
            with st.expander("Presentation / admission note", expanded=not visits):
                st.markdown(_md(pat["brief"]))
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**💊 Drug history**")
            cur = [m for m in _drugs(pat) if m.get("status", "current") == "current"]
            if not cur:
                st.caption("No current medications.")
            for m in cur:
                st.markdown("• " + _md(" ".join(x for x in (m.get("name"), m.get("dose"), m.get("frequency")) if x)))
            if len(_drugs(pat)) > len(cur):
                st.caption(f"+ {len(_drugs(pat)) - len(cur)} past medication(s)")
        with c2:
            st.markdown("**🔪 Surgical history**")
            sg = _hist(pat).get("surgical") or []
            if not sg:
                st.caption("None recorded.")
            for s_ in sg[:3]:
                st.markdown(f"• {_md(s_.get('procedure'))} ({_md(s_.get('date') or '?')})")
        with c3:
            st.markdown("**👨‍👩‍👧 Family history**")
            fm = _hist(pat).get("family") or []
            if not fm:
                st.caption("None recorded.")
            for f in fm[:3]:
                st.markdown(f"• {_md(f.get('relation'))}: {_md(f.get('condition'))}")
        if hosps:
            st.markdown(f"##### 🏥 Recent admissions ({len(hosps)} total)")
            for h in list(reversed(hosps))[:2]:
                S.hosp_card(h, compact=True)
        st.markdown(f"##### 🗒 Recent visits ({len(visits)} total)")
        if not visits:
            st.info("No visits yet. Open **➕ New visit** to write the first note.")
        for v in list(reversed(visits))[:3]:
            show_visit(v, pat, fbs_for(v), u, invs, ctx="ov", full=False)
        if len(visits) > 3:
            st.caption(f"… and {len(visits) - 3} more — see the Visits or Timeline tab.")
        st.markdown(f"##### 🔬 Recent investigations ({len(invs)} total)")
        if not invs:
            st.caption("No investigations recorded yet.")
        for i in list(reversed(invs))[:3]:
            S.inv_card(i, pat, u, ctx="ov", full=False)
        if visits and any((v.get("data") or {}).get("vitals") for v in visits):
            pick = st.radio("Vital-sign trend", list(TREND_PARAMS), horizontal=True, key="pc_trend")
            fig = _trend_fig(visits, TREND_PARAMS[pick], pick)
            if fig:
                st.plotly_chart(fig, use_container_width=True, key="pc_vital_fig")
            else:
                st.caption(f"No {pick.lower()} values recorded yet.")
        st.download_button("⬇️ Download chart summary (.txt)", _chart_text(pat, visits, invs, hosps, fbs),
                           file_name=f"virtual_patient_{pid}.txt", mime="text/plain")

    with tabs["➕ New visit"]:
        if _can_write(u, pat):
            _visit_form(u, pat, on_saved)
        else:
            st.info("You can read this patient but not add notes.")

    with tabs["Visits"]:
        if not visits:
            st.caption("No visits yet.")
        for v in reversed(visits):
            show_visit(v, pat, fbs_for(v), u, invs, ctx="visits")

    with tabs["🔬 Investigations"]:
        S.render_investigations(u, pat, visits, invs, hosps)
    with tabs["🏥 Admissions"]:
        S.render_hospitalisations(u, pat, hosps)
    with tabs["📅 Timeline"]:
        S.render_timeline(u, pat, visits, invs, hosps, fbs)
    with tabs["📋 History"]:
        S.render_history(u, pat)
    if paed:
        with tabs["🧒 Paediatrics"]:
            S.render_paediatric(u, pat)
    with tabs["⚙️ Case"]:
        _case(u, pat)


def _case(u, pat):
    if not _can_edit(u, pat):
        st.caption("Only the owner or faculty can edit the case details.")
    st.markdown(f"**Day 1:** {pat.get('admitted_on') or 'not set'}  ·  Created by {_md(pat.get('owner_name') or '')}")
    with st.form(f"pc_info_{pat['id']}"):
        brief = st.text_area("Presentation / admission note", value=pat.get("brief") or "", height=140,
                             disabled=not _can_edit(u, pat))
        saved = st.form_submit_button("💾 Save", disabled=not _can_edit(u, pat))
    if saved and _can_edit(u, pat):
        if upd("patients", pat["id"], {"brief": brief.strip()}):
            st.session_state["pc_toast"] = "Case details saved."
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
    for v in sel("visits", in_=("patient_id", ids), cols="id,patient_id"):
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
        st.caption("More history (surgical, family, social, obstetric, paediatric) can be added in the History tab.")
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
        alist.append({"substance": p[0], "type": "other", "reaction": p[1] if len(p) > 1 else "",
                      "severity": (p[2].lower() if len(p) > 2 else "")})
    row = ins("patients", {"owner_email": u["email"], "owner_name": u["name"], "shared": bool(shared),
                           "alias": alias.strip(), "age_years": float(age), "sex": sex,
                           "blood_group": None if blood == BLOODS[0] else blood, "title": title.strip(),
                           "admitted_on": str(adm), "brief": brief.strip(), "allergies": alist,
                           "chronic": _lines(chronic),
                           "drug_history": [{"name": m, "dose": "", "frequency": "", "status": "current",
                                             "started": "", "reason_stopped": ""} for m in _lines(meds)],
                           "history": {}, "case_ref": lib["case_ref"] or None})
    if row:
        _bump()
        st.session_state["pc_open"] = row["id"]
        st.session_state["pc_toast"] = "Patient created. Open ➕ New visit to write the first note."
        st.rerun()


def render_patient_chart(case_loader=None, on_visit_saved=None):
    u = _user()
    st.markdown("### 🩺 Patient Chart — Daily Rounds")
    st.caption("Follow simulated patients day by day: visit notes, investigations, admissions, full history, "
               "timeline and trends, with a prescription PDF. Practice for ward rounds and follow-up clinics.")
    if not _sb():
        st.warning("DEMO MODE: Supabase is not configured, so nothing is saved after this session.")
    elif not _ready():
        st.error("The Patient Chart tables are not all in Supabase yet. Run **patient_chart.sql** and then "
                 "**patient_chart_v2.sql** in the Supabase SQL Editor, then reload this page. "
                 f"({st.session_state.get('pc_last_err', '')})")
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
