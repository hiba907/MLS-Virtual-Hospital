"""
patient_chart_sections.py - the larger chart sections for the MLS Virtual Hospital Patient Chart:
investigations (with attached files), hospital-stay episodes, timeline, full history and paediatrics.
Used only by patient_chart.py. Simulated patients only; all user text is shown as plain text.
"""
import base64
import datetime as _dt
import io

import streamlit as st

import patient_chart as pc

INV_KINDS = ["Lab", "X-Ray", "CT", "MRI", "Ultrasound", "ECG", "Other"]
INV_ICON = {"Lab": "🧪", "X-Ray": "🩻", "CT": "🩻", "MRI": "🧲", "Ultrasound": "🔊", "ECG": "📈", "Other": "📄"}
OUTCOMES = ["", "Discharged home", "Transferred", "Deceased", "LAMA", "Absconded", "Still admitted"]
MAX_IMG_BYTES = 8 * 1024 * 1024
MAX_PDF_BYTES = 3 * 1024 * 1024
DEID = ("I confirm the attached file is de-identified: no names, ID or record numbers, hospital labels, dates of "
        "birth, faces or other identifying marks.")
SUGGESTIONS = {
    "gross_motor": ["Head control (3m)", "Sits unsupported (6m)", "Crawls (9m)", "Stands (12m)", "Walks (12–15m)",
                    "Runs (18m)", "Jumps (24m)", "Rides tricycle (3y)", "Skips (5y)"],
    "fine_motor": ["Reaches for objects (4m)", "Transfers objects (6m)", "Pincer grasp (9m)", "Stacks 2 blocks (12m)",
                   "Stacks 6 blocks (18m)", "Scribbles (18m)", "Draws circle (3y)", "Writes name (5y)"],
    "speech": ["Cooing (2m)", "Babbling (6m)", "Mama/dada (9m)", "First words (12m)", "2-word phrases (18m)",
               "50+ words (24m)", "3-word sentences (30m)", "Full sentences (3y)", "Clear speech 75% (4y)"],
    "social": ["Social smile (6w)", "Stranger anxiety (8m)", "Waves bye (12m)", "Parallel play (18m)",
               "Symbolic play (24m)", "Cooperative play (3y)", "Has friends (4y)"],
}
DOMAINS = {"gross_motor": "🏃 Gross motor", "fine_motor": "✋ Fine motor", "speech": "🗣 Speech & language",
           "social": "👥 Social & emotional"}
VACCINES = ["(custom)", "BCG", "Hepatitis B (birth)", "Hepatitis B (2m)", "Hepatitis B (6m)",
            "DTaP (2m)", "DTaP (4m)", "DTaP (6m)", "DTaP (18m)", "DTaP booster (4–6y)",
            "Hib (2m)", "Hib (4m)", "Hib (6m)", "Hib (18m)",
            "PCV13 (2m)", "PCV13 (4m)", "PCV13 (6m)", "PCV13 (12–15m)",
            "IPV (2m)", "IPV (4m)", "IPV (6–18m)", "IPV booster (4–6y)",
            "Rotavirus (2m)", "Rotavirus (4m)", "Rotavirus (6m)",
            "MMR (12–15m)", "MMR (4–6y)", "Varicella (12–15m)", "Varicella (4–6y)",
            "Hepatitis A (12m)", "Hepatitis A (18m)", "Influenza (annual)",
            "HPV (11–12y)", "Meningococcal", "Td booster (11–12y)", "COVID-19"]
_md = pc._md


# ─────────────── small helpers ───────────────
def _clean_image(data):
    """Re-encode an image: strips EXIF/GPS/camera metadata, fixes rotation, max 1200 px. Returns b64 or None."""
    try:
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((1200, 1200))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=82, optimize=True)
        return base64.b64encode(out.getvalue()).decode()
    except Exception:
        return None


def _save(pat, patch, msg=None):
    if pc.upd("patients", pat["id"], patch):
        if msg:
            st.session_state["pc_toast"] = msg
        st.rerun()
    else:
        st.error("Could not save.")


def _save_h(pat, key, value, msg=None):
    h = dict(pc._hist(pat))
    h[key] = value
    _save(pat, {"history": h}, msg)


def _row(text, key, can_edit):
    """One list line with an optional delete button. Returns True when delete was clicked."""
    if not can_edit:
        st.markdown(text)
        return False
    c1, c2 = st.columns([6, 1])
    with c1:
        st.markdown(text)
    with c2:
        return st.button("✕", key=key)


def _days(a, b):
    da, db = pc._date(a), pc._date(b)
    return (db - da).days if da and db else None


# ─────────────── hospital stays ───────────────
def hosp_card(h, compact=False):
    hd = h.get("data") or {}
    admit = h.get("admit_date") or "?"
    disch = h.get("discharge_date") or "ongoing"
    n = _days(h.get("admit_date"), h.get("discharge_date"))
    dur = f" ({n} day{'s' if n != 1 else ''})" if n is not None else ""
    with st.container(border=True):
        meta = " · ".join(x for x in (hd.get("hospital_name"), hd.get("ward"),
                                      f"Dr {hd['consultant']}" if hd.get("consultant") else "") if x)
        st.markdown(f"**🏥 {admit} → {disch}{dur}**" + (f" · {_md(meta)}" if meta else ""))

        def line(label, key, cut=None):
            v = hd.get(key)
            if v:
                v = v if not cut or len(v) <= cut else v[:cut] + "…"
                st.markdown(f"**{label}:** " + _md(v))

        line("Reason", "reason_for_admission")
        line("Admitting Dx", "admitting_diagnosis")
        if not compact:
            line("📖 In-hospital course", "in_hospital_course")
        else:
            line("Course", "in_hospital_course", 200)
        if hd.get("procedures_done"):
            st.markdown("**⚕️ Procedures:** " + _md("; ".join(hd["procedures_done"])))
        if not compact:
            line("🔬 Investigations summary", "investigations_summary")
        line("🏷️ Discharge Dx", "discharge_diagnosis")
        if not compact:
            line("💊 Discharge medications", "discharge_medications")
            line("📄 Discharge summary / instructions", "discharge_summary")
            line("⚠️ Complications", "complications")
        line("✅ Outcome", "outcome")
        if not compact:
            st.caption(f"Recorded by {h.get('author_name') or 'unknown'}")


def render_hospitalisations(u, pat, hosps):
    if hosps:
        st.markdown(f"##### Admissions ({len(hosps)})")
        for h in reversed(hosps):
            hosp_card(h)
            if pc._can_delete(u, pat, h):
                sure = st.checkbox("Confirm delete", key=f"pc_hdc_{h['id']}")
                if st.button("🗑 Delete this admission", key=f"pc_hdel_{h['id']}", disabled=not sure):
                    pc.dele("hospitalisations", h["id"])
                    st.rerun()
    else:
        st.caption("No admissions recorded yet.")
    if not pc._can_write(u, pat):
        return
    st.markdown("##### ➕ Record new admission")
    st.caption("An admission can be a stay before Day 1 or during the simulation. Use a fictional hospital name.")
    k = f"{pat['id']}_{pc._form_n()}"
    with st.form(f"pc_hosp_{k}"):
        c1, c2 = st.columns(2)
        with c1:
            admit = st.date_input("Admission date *", value=_dt.date.today(), key=f"pch_ad_{k}")
            hname = st.text_input("Hospital name *", key=f"pch_hn_{k}", placeholder="e.g. MLS Virtual Hospital")
        with c2:
            disch = st.date_input("Discharge date (leave empty if ongoing)", value=None, key=f"pch_dd_{k}")
            ward = st.text_input("Ward / unit", key=f"pch_wd_{k}", placeholder="e.g. CCU, Medical Ward 3, ICU")
        c1, c2 = st.columns(2)
        with c1:
            cons = st.text_input("Responsible consultant", key=f"pch_co_{k}", placeholder="e.g. Dr Smith")
        with c2:
            outcome = st.selectbox("Outcome / discharge status", OUTCOMES, key=f"pch_oc_{k}")
        reason = st.text_area("Reason for admission / presenting complaint *", height=70, key=f"pch_re_{k}")
        adx = st.text_input("Admitting diagnosis", key=f"pch_adx_{k}")
        course = st.text_area("In-hospital course (narrative)", height=120, key=f"pch_cr_{k}")
        procs = st.text_area("Procedures performed during admission (one per line)", height=80, key=f"pch_pr_{k}")
        invs_ = st.text_area("Key investigations summary", height=90, key=f"pch_iv_{k}")
        ddx = st.text_area("Discharge diagnosis (primary + secondary)", height=70, key=f"pch_dx_{k}")
        dmeds = st.text_area("Discharge medications", height=90, key=f"pch_dm_{k}")
        dsum = st.text_area("Discharge summary / instructions / follow-up plan", height=90, key=f"pch_ds_{k}")
        comp = st.text_input("Complications during admission (if any)", key=f"pch_cp_{k}")
        go_ = st.form_submit_button("💾 Save admission record", use_container_width=True)
    if not go_:
        return
    if not reason.strip():
        st.error("Reason for admission is required.")
        return
    if not hname.strip():
        st.error("Hospital name is required.")
        return
    if disch and disch < admit:
        st.error("The discharge date cannot be before the admission date.")
        return
    row = pc.ins("hospitalisations", {
        "patient_id": pat["id"], "author_email": u["email"], "author_name": u["name"],
        "admit_date": str(admit), "discharge_date": str(disch) if disch else None,
        "data": {"hospital_name": hname.strip(), "ward": ward.strip(), "consultant": cons.strip(),
                 "outcome": outcome, "reason_for_admission": reason.strip(), "admitting_diagnosis": adx.strip(),
                 "in_hospital_course": course.strip(), "procedures_done": pc._lines(procs),
                 "investigations_summary": invs_.strip(), "discharge_diagnosis": ddx.strip(),
                 "discharge_medications": dmeds.strip(), "discharge_summary": dsum.strip(),
                 "complications": comp.strip()}})
    if row:
        pc._bump()
        st.session_state["pc_toast"] = "Admission record saved."
        st.rerun()


# ─────────────── investigations ───────────────
def inv_card(i, pat, u, ctx="inv", full=True):
    with st.container(border=True):
        st.markdown(f"**{INV_ICON.get(i.get('kind'), '📄')} {_md(i.get('label'))}** · {i.get('kind')} · {i.get('inv_date')}")
        if i.get("notes"):
            st.markdown(_md(i["notes"]))
        for lv in i.get("lab_values") or []:
            rng = f" (ref {lv.get('ref_low') or '?'}–{lv.get('ref_high') or '?'})" if lv.get("ref_low") or lv.get("ref_high") else ""
            fl = pc._flag(lv.get("value"), lv.get("ref_low"), lv.get("ref_high"))
            st.markdown(f"• **{_md(lv.get('name'))}:** {lv.get('value'):g} {_md(lv.get('unit', ''))}{_md(rng)}"
                        + (f" — *{fl}*" if fl and fl != "within range" else "")
                        if isinstance(lv.get("value"), (int, float)) else
                        f"• **{_md(lv.get('name'))}:** {_md(lv.get('value'))} {_md(lv.get('unit', ''))}")
        f = i.get("file")
        if f:
            st.caption(f"📎 {f.get('name')} ({f.get('size_kb')} KB)")
            if full and st.toggle("Show attached file", key=f"pc_ft_{ctx}_{i['id']}"):
                rows = pc.sel("files", eq={"investigation_id": i["id"]}, limit=1)
                if not rows:
                    st.warning("The file could not be loaded.")
                else:
                    raw = base64.b64decode(rows[0]["b64"])
                    if str(rows[0].get("mime", "")).startswith("image/"):
                        st.image(raw)
                    st.download_button("⬇️ Download file", raw, key=f"pc_fd_{ctx}_{i['id']}",
                                       file_name=rows[0].get("file_name") or "investigation",
                                       mime=rows[0].get("mime") or "application/octet-stream")
        if full:
            st.caption(f"Recorded by {i.get('author_name') or 'unknown'}")
            if pc._can_delete(u, pat, i):
                sure = st.checkbox("Confirm delete", key=f"pc_idc_{ctx}_{i['id']}")
                if st.button("🗑 Delete", key=f"pc_idel_{ctx}_{i['id']}", disabled=not sure):
                    pc.dele("investigations", i["id"])
                    st.rerun()


def lab_trends(pat, invs, hosps, key):
    import plotly.graph_objects as go
    allv = {}
    for inv in invs:
        for lv in inv.get("lab_values") or []:
            allv.setdefault(lv["name"], []).append({"date": inv["inv_date"], "value": lv["value"],
                                                    "unit": lv.get("unit", ""), "low": lv.get("ref_low", ""),
                                                    "high": lv.get("ref_high", "")})
    st.markdown("##### 📈 Lab value trends")
    if not allv:
        st.caption("No numeric lab values recorded yet.")
        return
    metric = st.selectbox("Select metric", sorted(allv), key=f"pc_lm_{key}")
    series = sorted(allv[metric], key=lambda x: x["date"])
    fig = go.Figure(go.Scatter(x=[s["date"] for s in series], y=[s["value"] for s in series],
                               mode="lines+markers", name=metric))
    for h in hosps:
        a, d = h.get("admit_date"), h.get("discharge_date")
        if a and d and a != d:
            fig.add_vrect(x0=a, x1=d, fillcolor="rgba(136,14,79,0.10)", line_width=0,
                          annotation_text="🏥 Admitted", annotation_position="top left")
    lo, hi = pc._num(series[-1]["low"]), pc._num(series[-1]["high"])
    if lo is not None and hi is not None and lo < hi:
        fig.add_hrect(y0=lo, y1=hi, fillcolor="rgba(76,175,80,0.12)", line_width=0,
                      annotation_text="range you entered", annotation_position="top left")
    unit = series[-1]["unit"]
    fig.update_layout(title=f"{metric} trend", xaxis_title="Date", yaxis_title=f"{metric} ({unit})" if unit else metric,
                      height=300, margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True, key=f"pc_labfig_{key}")
    if hosps:
        st.caption("Pink areas = admission periods")


def render_investigations(u, pat, visits, invs, hosps):
    if invs:
        st.markdown(f"##### Investigations ({len(invs)})")
        for i in reversed(invs):
            inv_card(i, pat, u, ctx="inv")
    else:
        st.caption("No investigations recorded yet.")
    lab_trends(pat, invs, hosps, "inv")
    if not pc._can_write(u, pat):
        return
    st.markdown("##### ➕ Add investigation")
    st.caption("Use a dot for decimals. A reference range is optional - if you enter one, results outside it are "
               "flagged (this app supplies no ranges).")
    k = f"{pat['id']}_{pc._form_n()}"
    rows_n = st.session_state.get(f"pci_rows_{k}", 3)
    vopts = {"(not linked to a visit)": None}
    for v in reversed(visits):
        vopts[f"{v['visit_date']} — {(v.get('data') or {}).get('complaint', '')[:50]}"] = v["id"]
    with st.form(f"pc_inv_{k}"):
        c1, c2 = st.columns(2)
        with c1:
            kind = st.selectbox("Type *", INV_KINDS, key=f"pci_kind_{k}")
        with c2:
            idate = st.date_input("Date performed", value=_dt.date.today(), key=f"pci_date_{k}")
        label = st.text_input("Label / description *", key=f"pci_label_{k}",
                              placeholder="e.g. CBC with differential, Chest X-Ray PA")
        notes = st.text_area("Key findings / report summary", height=90, key=f"pci_notes_{k}")
        link = st.selectbox("Link to visit (optional)", list(vopts), key=f"pci_link_{k}")
        st.markdown("**📊 Lab values for trend tracking (optional)**")
        st.caption("Name · Value · Unit · Ref low · Ref high")
        lab_rows = []
        for r in range(rows_n):
            c1, c2, c3, c4, c5 = st.columns([3, 2, 1.5, 1.5, 1.5])
            lv = "visible" if r == 0 else "collapsed"
            with c1: ln = st.text_input(f"Metric {r + 1}", key=f"pci_ln{r}_{k}", placeholder="e.g. HbA1c", label_visibility=lv)
            with c2: lvv = st.number_input(f"Value {r + 1}", value=0.0, step=0.01, format="%g", key=f"pci_lv{r}_{k}", label_visibility=lv)
            with c3: lu = st.text_input(f"Unit {r + 1}", key=f"pci_lu{r}_{k}", label_visibility=lv)
            with c4: rl = st.text_input(f"Ref low {r + 1}", key=f"pci_rl{r}_{k}", label_visibility=lv)
            with c5: rh = st.text_input(f"Ref high {r + 1}", key=f"pci_rh{r}_{k}", label_visibility=lv)
            lab_rows.append({"name": ln.strip(), "value": float(lvv), "unit": lu.strip(),
                             "ref_low": rl.strip(), "ref_high": rh.strip()})
        add_row = st.form_submit_button("➕ Add row")
        up = st.file_uploader("Attach report / image (optional) — JPG, PNG or PDF", type=["jpg", "jpeg", "png", "pdf"],
                              key=f"pci_file_{k}")
        deid = st.checkbox(DEID, key=f"pci_deid_{k}")
        go_ = st.form_submit_button("💾 Save investigation", use_container_width=True)
    if add_row:
        st.session_state[f"pci_rows_{k}"] = rows_n + 1
        st.rerun()
    if not go_:
        return
    if not label.strip():
        st.error("Label / description is required.")
        return
    bad = [r["name"] for r in lab_rows if r["name"] and any(r[f] and pc._num(r[f]) is None for f in ("ref_low", "ref_high"))]
    if bad:
        st.error("Reference range values must be numbers: " + ", ".join(bad))
        return
    b64 = mime = None
    size_kb = 0
    if up is not None:
        if not deid:
            st.error("Please tick the de-identification confirmation to attach a file.")
            return
        raw = up.getvalue()
        name = up.name.lower()
        if name.endswith(".pdf"):
            if len(raw) > MAX_PDF_BYTES:
                st.error("PDF files must be 3 MB or smaller.")
                return
            if not raw.startswith(b"%PDF"):
                st.error("That file is not a valid PDF.")
                return
            b64, mime, size_kb = base64.b64encode(raw).decode(), "application/pdf", round(len(raw) / 1024, 1)
        else:
            if len(raw) > MAX_IMG_BYTES:
                st.error("Images must be 8 MB or smaller.")
                return
            b64 = _clean_image(raw)
            if not b64:
                st.error("That image could not be read.")
                return
            mime, size_kb = "image/jpeg", round(len(base64.b64decode(b64)) / 1024, 1)
    lab_values = [r for r in lab_rows if r["name"]]
    row = pc.ins("investigations", {
        "patient_id": pat["id"], "author_email": u["email"], "author_name": u["name"], "inv_date": str(idate),
        "kind": kind, "label": label.strip(), "notes": notes.strip(), "lab_values": lab_values,
        "visit_id": vopts[link], "file": ({"name": up.name, "mime": mime, "size_kb": size_kb} if up is not None else None)})
    if not row:
        return
    if up is not None:
        ok = pc.ins("files", {"patient_id": pat["id"], "investigation_id": row["id"], "author_email": u["email"],
                              "file_name": up.name, "mime": mime, "size_kb": size_kb, "b64": b64})
        if not ok:
            st.warning("The investigation was saved but the file could not be stored.")
    pc._bump()
    st.session_state["pc_toast"] = f"{kind} investigation saved."
    st.rerun()


# ─────────────── timeline ───────────────
def render_timeline(u, pat, visits, invs, hosps, fbs):
    entries = ([("Visit", v["visit_date"], v) for v in visits] +
               [(i["kind"], i["inv_date"], i) for i in invs] +
               [("Hospitalisation", h["admit_date"], h) for h in hosps])
    entries.sort(key=lambda e: str(e[1]), reverse=True)
    kinds = ["All"] + sorted({e[0] for e in entries})
    flt = st.selectbox("Filter", kinds, key="pc_tl_filter")
    shown = entries if flt == "All" else [e for e in entries if e[0] == flt]
    n_inv = len([e for e in entries if e[0] not in ("Visit", "Hospitalisation")])
    st.caption(f"🗒 {len(visits)} visits · 🏥 {len(hosps)} admissions · 🔬 {n_inv} investigations")
    st.markdown(f"##### 📅 {len(shown)} record(s)")
    for kind, d, row in shown:
        if kind == "Hospitalisation":
            hosp_card(row, compact=True)
        elif kind == "Visit":
            pc.show_visit(row, pat, [f for f in fbs if str(f.get("visit_id")) == str(row["id"])], u, invs,
                          ctx="tl", full=False)
        else:
            inv_card(row, pat, u, ctx="tl", full=False)
    lab_trends(pat, invs, hosps, "tl")


# ─────────────── history ───────────────
def render_history(u, pat):
    can = pc._can_edit(u, pat)
    h = pc._hist(pat)
    if not can:
        st.caption("Only the owner or faculty can edit the history.")

    # allergies
    st.markdown("#### ⚠️ Allergies")
    al = list(pat.get("allergies") or [])
    for i, a in enumerate(al):
        if _row(f"⚠ **{_md(a.get('substance'))}** | {_md(a.get('type') or '?')} | {_md(a.get('reaction') or '?')} | "
                f"{_md(a.get('severity') or '?')}", f"pc_dal_{i}", can):
            al.pop(i)
            _save(pat, {"allergies": al})
    if not al:
        st.caption("No allergies recorded.")
    if can:
        with st.form("pc_f_allergy", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            with c1: sub = st.text_input("Substance *", placeholder="Penicillin")
            with c2: typ = st.selectbox("Type", ["drug", "food", "latex", "other"])
            with c3: rea = st.text_input("Reaction", placeholder="rash")
            with c4: sev = st.selectbox("Severity", ["mild", "moderate", "severe"])
            if st.form_submit_button("➕ Add allergy") and sub.strip():
                al.append({"substance": sub.strip(), "type": typ, "reaction": rea.strip(), "severity": sev})
                _save(pat, {"allergies": al})

    # chronic
    st.markdown("#### 🔁 Chronic conditions")
    ch = list(pat.get("chronic") or [])
    for i, c in enumerate(ch):
        if _row(f"🔁 {_md(c)}", f"pc_dch_{i}", can):
            ch.pop(i)
            _save(pat, {"chronic": ch})
    if not ch:
        st.caption("None recorded.")
    if can:
        with st.form("pc_f_chronic", clear_on_submit=True):
            cond = st.text_input("Add condition", placeholder="e.g. DM Type 2, HTN, CKD…")
            if st.form_submit_button("➕ Add") and cond.strip():
                ch.append(cond.strip())
                _save(pat, {"chronic": ch})

    # drugs
    st.markdown("#### 💊 Drug history")
    dr = pc._drugs(pat)
    for i, m in enumerate(dr):
        cur = m.get("status", "current") == "current"
        txt = (f"💊 **{_md(m.get('name'))}** {_md(m.get('dose', ''))} {_md(m.get('frequency', ''))} — "
               + ("✅ Current" if cur else "🕐 Past")
               + (f" — started {_md(m['started'])}" if m.get("started") else "")
               + (f" — stopped: {_md(m['reason_stopped'])}" if m.get("reason_stopped") else ""))
        if _row(txt, f"pc_ddr_{i}", can):
            dr.pop(i)
            _save(pat, {"drug_history": dr})
    if not dr:
        st.caption("No medications recorded.")
    if can:
        with st.form("pc_f_drug", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1: dn = st.text_input("Drug name *", placeholder="Metformin")
            with c2: dd = st.text_input("Dose", placeholder="500 mg")
            with c3: df = st.text_input("Frequency", placeholder="BD")
            c1, c2, c3 = st.columns(3)
            with c1: ds = st.selectbox("Status", ["current", "past"])
            with c2: d0 = st.text_input("Started", placeholder="e.g. 2020")
            with c3: d1 = st.text_input("Stopped / reason", placeholder="side effects")
            if st.form_submit_button("➕ Add medication") and dn.strip():
                dr.append({"name": dn.strip(), "dose": dd.strip(), "frequency": df.strip(), "status": ds,
                           "started": d0.strip(), "reason_stopped": d1.strip() if ds == "past" else ""})
                _save(pat, {"drug_history": dr})

    # surgical
    st.markdown("#### 🔪 Surgical history")
    sg = list(h.get("surgical") or [])
    for i, s in enumerate(sg):
        txt = f"🔪 **{_md(s.get('procedure'))}** ({_md(s.get('date') or '?')})" + \
              (f" — {_md(s['hospital'])}" if s.get("hospital") else "") + \
              (f" — {_md(s['notes'])}" if s.get("notes") else "")
        if _row(txt, f"pc_dsg_{i}", can):
            sg.pop(i)
            _save_h(pat, "surgical", sg)
    if not sg:
        st.caption("None recorded.")
    if can:
        with st.form("pc_f_surg", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1: proc = st.text_input("Procedure *", placeholder="Appendectomy")
            with c2: sd = st.text_input("Date (approx)", placeholder="March 2018")
            c1, c2 = st.columns(2)
            with c1: surgeon = st.text_input("Surgeon", placeholder="optional")
            with c2: hosp = st.text_input("Hospital", placeholder="optional")
            sn = st.text_input("Notes", placeholder="e.g. laparoscopic, no complications")
            if st.form_submit_button("➕ Add surgery") and proc.strip():
                sg.append({"procedure": proc.strip(), "date": sd.strip(), "surgeon": surgeon.strip(),
                           "hospital": hosp.strip(), "notes": sn.strip()})
                _save_h(pat, "surgical", sg)

    # family
    st.markdown("#### 👨‍👩‍👧 Family history")
    fm = list(h.get("family") or [])
    for i, f in enumerate(fm):
        txt = f"👤 **{_md(f.get('relation'))}:** {_md(f.get('condition'))}" + (f" — {_md(f['notes'])}" if f.get("notes") else "")
        if _row(txt, f"pc_dfm_{i}", can):
            fm.pop(i)
            _save_h(pat, "family", fm)
    if not fm:
        st.caption("None recorded.")
    if can:
        with st.form("pc_f_fam", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1: rel = st.selectbox("Relation", ["Father", "Mother", "Brother", "Sister", "Son", "Daughter",
                                                     "Grandfather", "Grandmother", "Uncle", "Aunt", "Cousin", "Other"])
            with c2: cond = st.text_input("Condition *", placeholder="Diabetes, MI")
            with c3: fn = st.text_input("Notes", placeholder="optional")
            if st.form_submit_button("➕ Add family history") and cond.strip():
                fm.append({"relation": rel, "condition": cond.strip(), "notes": fn.strip()})
                _save_h(pat, "family", fm)

    # social
    st.markdown("#### 🏠 Social history")
    sh = {"smoking_status": "never", "pack_years": "", "years_quit": "", "alcohol_status": "none",
          "alcohol_details": "", "occupation": "", "employer": "", "residence": "", "marital_status": "",
          "education": "", "exercise": "", "diet": "", "recreational_drugs": "", "other_notes": ""}
    sh.update(h.get("social") or {})
    with st.form("pc_f_social"):
        st.markdown("**🚬 Smoking**")
        c1, c2, c3 = st.columns(3)
        smo = ["never", "ex-smoker", "current"]
        with c1: sm = st.selectbox("Smoking status", smo, index=smo.index(sh["smoking_status"]) if sh["smoking_status"] in smo else 0, disabled=not can)
        with c2: py = st.text_input("Pack-years", value=sh["pack_years"], disabled=not can)
        with c3: yq = st.text_input("Years since quitting", value=sh["years_quit"], disabled=not can)
        st.markdown("**🍷 Alcohol**")
        c1, c2 = st.columns(2)
        alo = ["none", "occasional", "regular", "heavy"]
        with c1: alc = st.selectbox("Alcohol use", alo, index=alo.index(sh["alcohol_status"]) if sh["alcohol_status"] in alo else 0, disabled=not can)
        with c2: ald = st.text_input("Alcohol details", value=sh["alcohol_details"], disabled=not can)
        st.markdown("**💼 Occupation & residence**")
        c1, c2 = st.columns(2)
        with c1: occ = st.text_input("Occupation", value=sh["occupation"], disabled=not can)
        with c2: emp = st.text_input("Employer", value=sh["employer"], disabled=not can)
        c1, c2 = st.columns(2)
        with c1: res = st.text_input("Residence (city / area only)", value=sh["residence"], disabled=not can)
        mso = ["", "Single", "Married", "Divorced", "Widowed", "Separated"]
        with c2: mar = st.selectbox("Marital status", mso, index=mso.index(sh["marital_status"]) if sh["marital_status"] in mso else 0, disabled=not can)
        st.markdown("**🎓 Lifestyle**")
        c1, c2 = st.columns(2)
        with c1: edu = st.text_input("Education", value=sh["education"], disabled=not can)
        with c2: exe = st.text_input("Exercise", value=sh["exercise"], disabled=not can)
        c1, c2 = st.columns(2)
        with c1: diet = st.text_input("Diet", value=sh["diet"], disabled=not can)
        with c2: rec = st.text_input("Recreational drugs", value=sh["recreational_drugs"], disabled=not can)
        oth = st.text_area("Other notes", value=sh["other_notes"], height=60, disabled=not can)
        if st.form_submit_button("💾 Save social history", disabled=not can):
            _save_h(pat, "social", {"smoking_status": sm, "pack_years": py.strip(), "years_quit": yq.strip(),
                                    "alcohol_status": alc, "alcohol_details": ald.strip(), "occupation": occ.strip(),
                                    "employer": emp.strip(), "residence": res.strip(), "marital_status": mar,
                                    "education": edu.strip(), "exercise": exe.strip(), "diet": diet.strip(),
                                    "recreational_drugs": rec.strip(), "other_notes": oth.strip()},
                    "Social history saved.")

    # obstetric
    if pat.get("sex") in ("Female", "Other / not stated"):
        st.markdown("#### 🤰 Obstetric & gynaecological history")
        ob = {"gravida": 0, "para": 0, "abortus": 0, "living": 0, "lmp": "", "menstrual_cycle": "",
              "cycle_length": "", "contraception": "", "menarche_age": "", "menopause_age": "", "pregnancies": []}
        ob.update(h.get("obstetric") or {})
        with st.form("pc_f_obs"):
            st.markdown("**📊 G / P / A / L**")
            c1, c2, c3, c4 = st.columns(4)
            with c1: g_ = st.number_input("Gravida (G)", 0, 30, int(ob["gravida"]), disabled=not can)
            with c2: p_ = st.number_input("Para (P)", 0, 30, int(ob["para"]), disabled=not can)
            with c3: a_ = st.number_input("Abortus (A)", 0, 30, int(ob["abortus"]), disabled=not can)
            with c4: l_ = st.number_input("Living (L)", 0, 30, int(ob["living"]), disabled=not can)
            st.markdown("**🗓 Menstrual history**")
            c1, c2, c3 = st.columns(3)
            mco = ["", "Regular", "Irregular", "Post-menopausal", "Amenorrhoea", "On contraception"]
            with c1: lmp = st.text_input("LMP", value=ob["lmp"], placeholder="15 June 2025", disabled=not can)
            with c2: mc = st.selectbox("Cycle regularity", mco, index=mco.index(ob["menstrual_cycle"]) if ob["menstrual_cycle"] in mco else 0, disabled=not can)
            with c3: cl = st.text_input("Cycle length", value=ob["cycle_length"], disabled=not can)
            c1, c2 = st.columns(2)
            with c1: mea = st.text_input("Age at menarche", value=ob["menarche_age"], disabled=not can)
            with c2: mpa = st.text_input("Age at menopause", value=ob["menopause_age"], disabled=not can)
            con = st.text_input("Contraception", value=ob["contraception"], disabled=not can)
            if st.form_submit_button("💾 Save obstetric summary", disabled=not can):
                ob2 = dict(ob)
                ob2.update({"gravida": g_, "para": p_, "abortus": a_, "living": l_, "lmp": lmp.strip(),
                            "menstrual_cycle": mc, "cycle_length": cl.strip(), "menarche_age": mea.strip(),
                            "menopause_age": mpa.strip(), "contraception": con.strip()})
                _save_h(pat, "obstetric", ob2, "Obstetric summary saved.")
        st.markdown("**🍼 Individual pregnancy records**")
        pr = list(ob.get("pregnancies") or [])
        for i, p in enumerate(pr):
            txt = f"🍼 {_md(p.get('year') or '?')} — {_md(p.get('outcome') or '?')} at {_md(p.get('gestation_weeks') or '?')} wks ({_md(p.get('mode', ''))})" + \
                  (f" — {_md(p['notes'])}" if p.get("notes") else "")
            if _row(txt, f"pc_dpr_{i}", can):
                pr.pop(i)
                ob2 = dict(ob)
                ob2["pregnancies"] = pr
                _save_h(pat, "obstetric", ob2)
        if not pr:
            st.caption("No pregnancy records yet.")
        if can:
            with st.form("pc_f_preg", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1: y = st.text_input("Year", placeholder="2019")
                with c2: o = st.selectbox("Outcome", ["Livebirth", "Miscarriage", "Stillbirth", "Ectopic", "TOP"])
                with c3: gw = st.text_input("Gestation (weeks)", placeholder="38")
                c1, c2 = st.columns(2)
                with c1: mo = st.selectbox("Delivery mode", ["SVD", "Caesarean section", "Forceps", "Vacuum", "N/A"])
                with c2: pn = st.text_input("Notes", placeholder="PPH, pre-eclampsia")
                if st.form_submit_button("➕ Add pregnancy") and y.strip():
                    pr.append({"year": y.strip(), "outcome": o, "gestation_weeks": gw.strip(), "mode": mo, "notes": pn.strip()})
                    ob2 = dict(ob)
                    ob2["pregnancies"] = pr
                    _save_h(pat, "obstetric", ob2)
    else:
        st.caption("ℹ️ Obstetric history is shown for female patients.")


# ─────────────── paediatrics ───────────────
def render_paediatric(u, pat):
    import plotly.graph_objects as go
    can = pc._can_edit(u, pat)
    if not can:
        st.caption("Only the owner or faculty can edit the paediatric history.")
    ph = {"birth_weight_g": "", "gestational_age_weeks": "", "delivery_mode": "", "nicu_stay": False,
          "nicu_days": "", "apgar_1min": "", "apgar_5min": "", "neonatal_complications": "", "breastfed": "",
          "breastfed_duration_months": "", "newborn_screening_done": False, "newborn_screening_results": "",
          "growth_records": [], "milestones": {"gross_motor": [], "fine_motor": [], "speech": [], "social": []},
          "immunisations": []}
    ph.update(pc._hist(pat).get("paediatric") or {})
    ph["milestones"] = {**{d: [] for d in DOMAINS}, **(ph.get("milestones") or {})}

    def put(msg=None):
        _save_h(pat, "paediatric", ph, msg)

    st.markdown("#### 🍼 Birth & neonatal details")
    with st.form("pc_f_birth"):
        c1, c2, c3 = st.columns(3)
        dmo = ["", "SVD", "Caesarean section", "Forceps", "Vacuum", "Water birth"]
        with c1:
            bw = st.text_input("Birth weight (g)", value=ph["birth_weight_g"], placeholder="3200", disabled=not can)
            ga = st.text_input("Gestational age (weeks)", value=ph["gestational_age_weeks"], placeholder="38", disabled=not can)
        with c2:
            dm = st.selectbox("Delivery mode", dmo, index=dmo.index(ph["delivery_mode"]) if ph["delivery_mode"] in dmo else 0, disabled=not can)
            nicu = st.checkbox("NICU stay required", value=bool(ph["nicu_stay"]), disabled=not can)
        with c3:
            nd = st.text_input("NICU days", value=ph["nicu_days"], disabled=not can)
            a1 = st.text_input("Apgar 1 min", value=ph["apgar_1min"], placeholder="0–10", disabled=not can)
            a5 = st.text_input("Apgar 5 min", value=ph["apgar_5min"], placeholder="0–10", disabled=not can)
        nc = st.text_area("Neonatal complications", value=ph["neonatal_complications"], height=60,
                          placeholder="e.g. jaundice → phototherapy, RDS, hypoglycaemia…", disabled=not can)
        st.markdown("**🤱 Feeding**")
        c1, c2 = st.columns(2)
        bfo = ["", "Yes", "No", "Mixed"]
        with c1: bf = st.selectbox("Breastfed", bfo, index=bfo.index(ph["breastfed"]) if ph["breastfed"] in bfo else 0, disabled=not can)
        with c2: bd = st.text_input("Duration (months)", value=ph["breastfed_duration_months"], disabled=not can)
        st.markdown("**🧪 Newborn screening**")
        c1, c2 = st.columns(2)
        with c1: nbs = st.checkbox("Newborn screening done", value=bool(ph["newborn_screening_done"]), disabled=not can)
        with c2: nbr = st.text_input("Results", value=ph["newborn_screening_results"], disabled=not can)
        if st.form_submit_button("💾 Save birth details", disabled=not can):
            ph.update({"birth_weight_g": bw.strip(), "gestational_age_weeks": ga.strip(), "delivery_mode": dm,
                       "nicu_stay": nicu, "nicu_days": nd.strip(), "apgar_1min": a1.strip(), "apgar_5min": a5.strip(),
                       "neonatal_complications": nc.strip(), "breastfed": bf, "breastfed_duration_months": bd.strip(),
                       "newborn_screening_done": nbs, "newborn_screening_results": nbr.strip()})
            put("Birth details saved.")

    st.markdown("#### 📏 Growth records")
    gr = list(ph["growth_records"])
    order = sorted(range(len(gr)), key=lambda i: gr[i].get("date", ""), reverse=True)
    for i in order:
        g = gr[i]
        parts = [f"📅 {_md(g.get('date', '?'))}"]
        if g.get("weight_kg"): parts.append(f"⚖️ {_md(g['weight_kg'])} kg")
        if g.get("height_cm"): parts.append(f"📏 {_md(g['height_cm'])} cm")
        if g.get("hc_cm"): parts.append(f"🔵 HC {_md(g['hc_cm'])} cm")
        if g.get("notes"): parts.append(f"📝 {_md(g['notes'])}")
        if _row(" | ".join(parts), f"pc_dgr_{i}", can):
            gr.pop(i)
            ph["growth_records"] = gr
            put()
    if not gr:
        st.caption("No growth records yet.")
    if can:
        with st.form("pc_f_growth", clear_on_submit=True):
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1: gd = st.date_input("Date", value=_dt.date.today())
            with c2: gw = st.text_input("Weight (kg)", placeholder="12.5")
            with c3: gh = st.text_input("Height (cm)", placeholder="90.0")
            with c4: gc = st.text_input("Head circ (cm)", placeholder="46.0")
            with c5: gn = st.text_input("Notes", placeholder="optional")
            if st.form_submit_button("➕ Add growth record"):
                gr.append({"date": str(gd), "weight_kg": gw.strip(), "height_cm": gh.strip(), "hc_cm": gc.strip(),
                           "notes": gn.strip()})
                ph["growth_records"] = gr
                put()
    if len(gr) >= 2:
        st.markdown("**📈 Growth trends**")
        mc = st.selectbox("Show", ["Weight (kg)", "Height (cm)", "Head circumference (cm)"], key="pc_growth_metric")
        dk = {"Weight (kg)": "weight_kg", "Height (cm)": "height_cm", "Head circumference (cm)": "hc_cm"}[mc]
        xs, ys = [], []
        for g in sorted(gr, key=lambda x: x.get("date", "")):
            v = pc._num(g.get(dk))
            if v is not None:
                xs.append(g["date"])
                ys.append(v)
        if ys:
            fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines+markers", name=mc))
            fig.update_layout(title=f"{mc} over time", xaxis_title="Date", yaxis_title=mc, height=260,
                              margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, use_container_width=True, key="pc_growth_fig")
        st.caption("Plotted from the values entered. No growth-chart percentiles or flags are shown.")

    st.markdown("#### 🧠 Developmental milestones")
    for dom, lab in DOMAINS.items():
        ms = list(ph["milestones"].get(dom, []))
        with st.expander(f"{lab} ({len(ms)} recorded)"):
            for i, m in enumerate(ms):
                if _row(f"✓ {_md(m.get('milestone', '?'))} @ {_md(m.get('age_months', '?'))} months" +
                        (f" — {_md(m['notes'])}" if m.get("notes") else ""), f"pc_dms_{dom}_{i}", can):
                    ms.pop(i)
                    ph["milestones"][dom] = ms
                    put()
            if not ms:
                st.caption("None recorded yet.")
            if can:
                with st.form(f"pc_f_ms_{dom}", clear_on_submit=True):
                    c1, c2, c3 = st.columns([3, 1, 2])
                    with c1:
                        sel_ = st.selectbox("Milestone", ["(custom)"] + SUGGESTIONS[dom], key=f"pc_mss_{dom}")
                        cust = st.text_input("Custom milestone (used when '(custom)' is selected)", key=f"pc_msc_{dom}")
                    with c2: age_m = st.number_input("Age (mo)", 0, 216, 12, key=f"pc_msa_{dom}")
                    with c3: mn = st.text_input("Notes", key=f"pc_msn_{dom}")
                    if st.form_submit_button("➕ Add"):
                        name = cust.strip() if sel_ == "(custom)" else sel_
                        if name:
                            ms.append({"milestone": name, "age_months": age_m, "notes": mn.strip()})
                            ph["milestones"][dom] = ms
                            put()

    st.markdown("#### 💉 Immunisation record")
    im = list(ph["immunisations"])
    for i in sorted(range(len(im)), key=lambda i: im[i].get("date_given", "")):
        v = im[i]
        txt = (f"💉 **{_md(v.get('vaccine', '?'))}** — {_md(v.get('date_given', '?'))}" +
               (f" [{_md(v['batch'])}]" if v.get("batch") else "") +
               (f" → next due: {_md(v['next_due'])}" if v.get("next_due") else "") +
               (f" — {_md(v['notes'])}" if v.get("notes") else ""))
        if _row(txt, f"pc_dim_{i}", can):
            im.pop(i)
            ph["immunisations"] = im
            put()
    if not im:
        st.caption("No vaccines recorded yet.")
    if can:
        with st.form("pc_f_vacc", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                vs = st.selectbox("Vaccine *", VACCINES, key="pc_vacc_sel")
                vc = st.text_input("Custom vaccine name (used when '(custom)' is selected)", key="pc_vacc_cust")
            with c2:
                vd = st.date_input("Date given", value=_dt.date.today(), key="pc_vacc_date")
                vn = st.text_input("Next due (optional)", placeholder="e.g. Jan 2026", key="pc_vacc_next")
            c1, c2 = st.columns(2)
            with c1: vb = st.text_input("Batch number", placeholder="AB1234", key="pc_vacc_batch")
            with c2: vt = st.text_input("Notes", placeholder="mild fever after", key="pc_vacc_notes")
            if st.form_submit_button("➕ Record vaccine"):
                name = vc.strip() if vs == "(custom)" else vs
                if name:
                    im.append({"vaccine": name, "date_given": str(vd), "batch": vb.strip(), "next_due": vn.strip(),
                               "notes": vt.strip()})
                    ph["immunisations"] = im
                    put("Vaccine recorded.")
