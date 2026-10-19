"""
therapy_timeline.py  -  Therapy Timeline module for the MLS Virtual Hospital (additive).

Reads the workbook Therapy_Timeline_Cases.xlsx (same folder) and shows each case as a
stage-by-stage timeline of Give / Check / Danger boxes.

Modes: Read | Hide and recall | Change one thing | Spot the error.
Rules enforced here:
 - Only VERIFIED cases are shown to students; admins can tick "show UNVERIFIED" (clearly badged).
 - Every case shows its source, license text, attribution and known source discrepancies.
 - Every box shows its source tag (PAPER / GUIDELINE / AUTHOR). "NOT STATED IN PAPER" is shown as is.
 - Standing note: verify against your local protocol before any real-world use.

Hook-up in app.py (one added page):  from therapy_timeline import render_therapy_timeline
                                      render_therapy_timeline(is_admin=<bool>)
"""
import os
import streamlit as st

XLSX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Therapy_Timeline_Cases.xlsx")
ICON = {"Give": "💊 GIVE", "Check": "🔍 CHECK", "Danger": "⚠️ DANGER"}
NSP = "NOT STATED IN PAPER"


@st.cache_data(show_spinner=False)
def _load(path: str, mtime: float):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    out = {}
    for ws in wb:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        hdr = [str(h) for h in rows[0]]
        out[ws.title] = [dict(zip(hdr, r)) for r in rows[1:] if r and r[0] is not None]
    return out


def _s(v):
    return "" if v is None else str(v)


def _box_html(b):
    color = {"Give": "#0f766e", "Check": "#64748b", "Danger": "#dc2626"}.get(b["box_type"], "#64748b")
    dose = _s(b.get("dose_text"))
    route = _s(b.get("frequency_route"))
    return (f"<div style='border-left:5px solid {color};background:rgba(128,128,128,.08);"
            f"padding:8px 12px;margin:6px 0;border-radius:6px'>"
            f"<b style='color:{color}'>{ICON.get(b['box_type'], b['box_type'])}</b> &nbsp;<b>{_s(b['title'])}</b>"
            + (f"<br>{dose}" if dose else "") + (f"<br><i>{route}</i>" if route else "")
            + f"<br><small>source: {_s(b.get('content_source'))} · {_s(b.get('source_ref'))}</small></div>")


def render_therapy_timeline(is_admin: bool = False):
    st.markdown("### ⏱️ Therapy Timeline")
    st.caption("Learn real treatment sequences from published case reports. "
               "Teaching aid only — verify every dose against your local protocol before real-world use.")
    if not os.path.exists(XLSX):
        st.error("Therapy_Timeline_Cases.xlsx not found next to therapy_timeline.py.")
        return
    data = _load(XLSX, os.path.getmtime(XLSX))
    cases = data.get("Cases", [])
    show_unver = is_admin and st.checkbox("Admin: also show UNVERIFIED cases", value=False, key="tt_unver")
    cases = [c for c in cases if c.get("verify_status") == "VERIFIED" or show_unver]
    if not cases:
        st.info("No VERIFIED cases yet. A teacher must re-check each case against its paper and set "
                "verify_status = VERIFIED in the workbook.")
        return

    labels = {f"{c['case_id']} - {c['title']}": c for c in cases}
    case = labels[st.selectbox("Case", list(labels), key="tt_case")]
    cid = case["case_id"]
    if case.get("verify_status") != "VERIFIED":
        st.warning("UNVERIFIED — numbers not yet re-checked by a teacher.")
    mode = st.radio("Mode", ["Read", "Hide and recall", "Change one thing", "Spot the error"],
                    horizontal=True, key="tt_mode")

    with st.expander("Patient and source", expanded=(mode == "Read")):
        st.write(f"**{_s(case['patient_snapshot'])}**")
        st.write(_s(case["problem"]))
        st.caption(f"{_s(case['source_citation'])} · {_s(case['source_doi_pmid'])}")
        st.caption(f"License: {_s(case['source_license'])}")
        st.caption(_s(case["attribution_text"]))
        if case.get("known_source_issues"):
            st.warning("Discrepancies in the source paper: " + _s(case["known_source_issues"]))

    stages = sorted([s for s in data.get("Stages", []) if s["case_id"] == cid], key=lambda s: int(s["stage_order"]))
    boxes = [b for b in data.get("Boxes", []) if b["case_id"] == cid]
    links = {d["item_id"]: d for d in data.get("Danger_links", []) if d["case_id"] == cid}

    if mode in ("Read", "Hide and recall"):
        for s in stages:
            so = int(s["stage_order"])
            st.markdown(f"#### Stage {so}: {_s(s['stage_name'])}  \n<small>{_s(s['time_from_arrival'])}</small>",
                        unsafe_allow_html=True)
            st.write(_s(s["snapshot_labs_vitals"]))
            sb = [b for b in boxes if int(b["stage_order"]) == so]
            if mode == "Read":
                st.write(_s(s["summary"]))
                for b in sb:
                    st.markdown(_box_html(b), unsafe_allow_html=True)
                    if b["box_type"] == "Danger" and b["item_id"] in links:
                        st.caption("Linked decision-tree branch: " + _s(links[b["item_id"]].get("tree_branch_id")))
            else:
                st.caption("Recall before revealing: what would you give, check and watch for?")
                guess = st.text_area("Your plan", key=f"tt_g_{cid}_{so}", height=80)
                if st.toggle("Reveal", key=f"tt_r_{cid}_{so}"):
                    st.write(_s(s["summary"]))
                    for b in sb:
                        st.markdown(_box_html(b), unsafe_allow_html=True)
                elif guess:
                    st.caption("Saved in this session only. Tap Reveal to compare.")
    elif mode == "Change one thing":
        wi = [w for w in data.get("WhatIf", []) if w["case_id"] == cid]
        for w in wi:
            st.markdown(f"**What if:** {_s(w['change'])}  \n<small>affects: {_s(w['affects_item_id'])}</small>",
                        unsafe_allow_html=True)
            ans = _s(w["effect_on_plan"])
            if ans.startswith("["):
                st.info("Teacher answer not written yet — discuss with your tutor. (Teaching idea, not from the paper.)")
            else:
                st.write(ans + f"  \n*source: {_s(w['content_source'])}*")
    else:
        for e in [x for x in data.get("SpotError", []) if x["case_id"] == cid]:
            st.markdown(f"**Flawed plan:** {_s(e['flawed_plan'])}")
            if st.toggle("Show what is wrong", key=f"tt_e_{cid}"):
                st.error(_s(e["what_is_wrong"]))
                st.success(_s(e["correction"]))
                st.caption(f"source: {_s(e['content_source'])} · {_s(e['source_ref'])}")
