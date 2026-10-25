"""
research_hub.py - Research Hub for the MLS Virtual Hospital (additive, standalone).

Students and faculty propose research ideas, form teams with mentors, attach PubMed-verified
references, follow a stage-gated pathway (ethics before data), and keep an auditable update log.
Everything a student proposes is PENDING until faculty approve it.

Storage: Supabase tables from research_hub.sql (same SUPABASE_URL / SUPABASE_KEY secrets as the rest of
the app). If Supabase is not configured the hub runs in a clearly labelled DEMO mode (this session only).

Hook-up in app.py:  from research_hub import render_research_hub ; render_research_hub()
"""
import re
import requests
import streamlit as st

STAGES = ["Idea", "Literature review", "Protocol", "Ethics review", "Data collection",
          "Analysis", "Writing", "Submitted"]
FIELDS = ["Medical Laboratory Science", "Clinical Reasoning", "Critical Care", "Pathology", "Endoscopy",
          "Infectious Disease", "Endocrinology", "Cardiology", "Oncology", "Medical Education",
          "Simulation", "Public Health", "Other"]
STUDY_TYPES = ["Narrative review", "Systematic review / scoping review", "Case report / case series",
               "Educational or simulation study", "Audit / quality improvement",
               "Cross-sectional survey", "Laboratory method comparison", "Other"]
TEAM_ROLES = ["Co-investigator", "Data analyst", "Literature reviewer", "Writer / editor", "Clinical advisor",
              "Statistician", "Mentor"]
ETHICS = ["Not yet considered", "Not required (no human participants or data) - reason below",
          "Pending - submitted to committee", "Approved - reference below"]
DATA_GATE_OK = (ETHICS[1], ETHICS[3])

RULES = [
    ("Ethics comes before data",
     "Any project that collects data from people or uses patient records needs approval from the appropriate "
     "ethics committee BEFORE data collection. The hub will not let a project enter 'Data collection' until an "
     "ethics status of 'Not required (with reason)' or 'Approved (with reference)' is recorded."),
    ("No real patient information",
     "Never post names, ID numbers, photos, dates of birth, or any detail that could identify a patient, "
     "anywhere in the hub. Case material must be fully de-identified and consented."),
    ("Authorship follows ICMJE criteria",
     "Authors should meet all four ICMJE criteria: substantial contribution to design, data or analysis; "
     "drafting or critically revising the work; final approval; and accountability for the work. "
     "Agree author order and roles in writing early. Contributors who do not meet the criteria are acknowledged, "
     "not listed as authors. (Check the current ICMJE Recommendations at icmje.org.)"),
    ("References must be real",
     "Add references by PubMed ID so they can be checked. Never invent or guess a citation. "
     "If an AI tool helps you search or draft, you must check every claim and reference yourself and disclose the use."),
    ("Moderation",
     "New projects are reviewed by faculty before they appear on the board. Faculty may request changes, "
     "assign a mentor, or archive a project that breaks these rules."),
    ("Teaching platform, not a journal",
     "Projects here are student research training. Nothing posted is peer-reviewed publication, and no result "
     "should be used for clinical decisions."),
]

TABLES = {"projects": "vh_research_projects", "members": "vh_research_members",
          "refs": "vh_research_refs", "updates": "vh_research_updates"}


# ───────────────────────── data layer (Supabase or demo) ─────────────────────────
def _secret(k):
    try:
        return st.secrets.get(k, "")
    except Exception:
        return ""


def _sb():
    u, k = _secret("SUPABASE_URL"), _secret("SUPABASE_KEY")
    return (u.rstrip("/"), k) if u and k and not str(u).startswith("YOUR_") else None


def _h(k):
    return {"apikey": k, "Authorization": f"Bearer {k}", "Content-Type": "application/json",
            "Prefer": "return=representation"}


def _demo():
    return st.session_state.setdefault("rh_demo", {t: [] for t in TABLES})


def db_select(t, eq=None, order=None):
    cfg = _sb()
    if cfg:
        u, k = cfg
        p = {"select": "*"}
        for c, v in (eq or {}).items():
            p[c] = f"eq.{v}"
        if order:
            p["order"] = order
        try:
            r = requests.get(f"{u}/rest/v1/{TABLES[t]}", headers=_h(k), params=p, timeout=8)
            return r.json() if r.status_code == 200 else []
        except Exception:
            return []
    rows = [r for r in _demo()[t] if all(str(r.get(c)) == str(v) for c, v in (eq or {}).items())]
    if order:
        col, _, d = order.partition(".")
        rows = sorted(rows, key=lambda r: str(r.get(col, "")), reverse=(d == "desc"))
    return rows


def db_insert(t, row):
    cfg = _sb()
    if cfg:
        u, k = cfg
        try:
            r = requests.post(f"{u}/rest/v1/{TABLES[t]}", headers=_h(k), json=row, timeout=8)
            if r.status_code in (200, 201):
                j = r.json()
                return j[0] if j else row
        except Exception:
            pass
        st.error("Could not save. Check that research_hub.sql has been run in Supabase.")
        return None
    d = _demo()
    row = dict(row)
    row["id"] = len(d[t]) + 1
    row["created_at"] = __import__("datetime").datetime.utcnow().isoformat()
    d[t].append(row)
    return row


def db_update(t, rid, patch):
    cfg = _sb()
    if cfg:
        u, k = cfg
        try:
            r = requests.patch(f"{u}/rest/v1/{TABLES[t]}", headers=_h(k), params={"id": f"eq.{rid}"},
                               json=patch, timeout=8)
            return r.status_code in (200, 204)
        except Exception:
            return False
    for r in _demo()[t]:
        if str(r["id"]) == str(rid):
            r.update(patch)
    return True


# ───────────────────────── helpers ─────────────────────────
def _user():
    a = st.session_state.get("auth_user") or {}
    uid = str(a.get("id") or a.get("email") or "guest")
    return {"id": uid, "name": a.get("name") or a.get("email") or "Guest",
            "role": (a.get("role") or "student").lower(), "email": a.get("email", ""),
            "signed_in": bool(a)}


def _is_mod(u):
    return u["role"] in ("admin", "faculty")


def _pubmed(pmid):
    """Look up a PMID on PubMed (NCBI E-utilities). Returns dict or None."""
    pmid = pmid.strip()
    if not re.fullmatch(r"\d{4,9}", pmid):
        return None
    try:
        r = requests.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                         params={"db": "pubmed", "id": pmid, "retmode": "json"}, timeout=10)
        j = r.json()["result"][pmid]
        if "error" in j or not j.get("title"):
            return None
        au = [a["name"] for a in j.get("authors", [])]
        authors = ", ".join(au[:3]) + (" et al." if len(au) > 3 else "")
        doi = next((x["value"] for x in j.get("articleids", []) if x.get("idtype") == "doi"), "")
        return {"pmid": pmid, "title": j["title"].rstrip("."),
                "citation": f"{authors}. {j['title'].rstrip('.')}. {j.get('source', '')}. {j.get('pubdate', '')}.",
                "doi": doi}
    except Exception:
        return None


def _stage_bar(stage):
    i = STAGES.index(stage) if stage in STAGES else 0
    st.progress((i + 1) / len(STAGES), text=f"Stage {i + 1} of {len(STAGES)}: {stage}")


# ───────────────────────── pages ─────────────────────────
def _board(u):
    rows = [p for p in db_select("projects", order="created_at.desc") if p.get("status") == "approved"]
    c = st.columns(3)
    f = c[0].selectbox("Field", ["All"] + FIELDS, key="rh_f")
    s = c[1].selectbox("Stage", ["All"] + STAGES, key="rh_s")
    seek = c[2].checkbox("Looking for team members", key="rh_seek")
    for p in rows:
        if f != "All" and p.get("field") != f:
            continue
        if s != "All" and p.get("stage") != s:
            continue
        if seek and not p.get("seeking"):
            continue
        with st.container(border=True):
            st.markdown(f"**{p['title']}**  \n{p.get('field', '')} · {p.get('study_type', '')} · "
                        f"Stage: **{p.get('stage', '')}** · Lead: {p.get('owner_name', '')}")
            st.write(p.get("question", ""))
            if p.get("seeking"):
                st.caption("Looking for: " + p["seeking"])
            if st.button("Open project", key=f"rh_open_{p['id']}"):
                st.session_state["rh_open"] = p["id"]
                st.rerun()
    if not rows:
        st.info("No approved projects yet. Propose the first one in the next tab.")


def _propose(u):
    if not u["signed_in"]:
        st.warning("Sign in to propose a project.")
        return
    st.caption("Your proposal is reviewed by faculty before it appears on the board.")
    with st.form("rh_new"):
        title = st.text_input("Working title")
        question = st.text_area("Research question (one clear sentence; for clinical questions use PICO)", height=80)
        c = st.columns(2)
        field = c[0].selectbox("Field", FIELDS)
        stype = c[1].selectbox("Study type", STUDY_TYPES)
        background = st.text_area("Why does this matter? What is already known? (cite PubMed IDs later in the project page)",
                                  height=110)
        seeking = st.multiselect("Team members you need", TEAM_ROLES)
        st.markdown("**Required confirmations**")
        a1 = st.checkbox("This proposal contains no real patient identifiers or private data.")
        a2 = st.checkbox("I understand ethics approval is required before collecting any data from people or records.")
        a3 = st.checkbox("I will add only real, PubMed-checkable references, and will disclose any AI assistance.")
        if st.form_submit_button("Submit for faculty review", type="primary"):
            if not (title.strip() and question.strip() and background.strip()):
                st.error("Title, question and background are required.")
            elif not (a1 and a2 and a3):
                st.error("Please tick all three confirmations.")
            else:
                row = db_insert("projects", {
                    "title": title.strip(), "question": question.strip(), "field": field, "study_type": stype,
                    "background": background.strip(), "seeking": ", ".join(seeking), "stage": STAGES[0],
                    "status": "pending", "owner_id": u["id"], "owner_name": u["name"],
                    "ethics_status": ETHICS[0], "ethics_note": "", "mentor_name": "", "moderator_note": ""})
                if row:
                    db_insert("members", {"project_id": row["id"], "user_id": u["id"], "name": u["name"],
                                          "role": "Lead", "status": "accepted", "message": ""})
                    st.success("Submitted. Faculty will review it. You can follow it under 'My projects'.")


def _mine(u):
    if not u["signed_in"]:
        st.warning("Sign in to see your projects.")
        return
    mem = [m for m in db_select("members") if m.get("user_id") == u["id"]]
    ids = {str(m["project_id"]): m for m in mem}
    shown = False
    for p in db_select("projects", order="created_at.desc"):
        m = ids.get(str(p["id"]))
        if m:
            shown = True
            with st.container(border=True):
                st.markdown(f"**{p['title']}** · status: **{p.get('status')}** · your role: {m.get('role')} "
                            f"({m.get('status')})")
                if p.get("moderator_note"):
                    st.caption("Faculty note: " + p["moderator_note"])
                if st.button("Open", key=f"rh_my_{p['id']}"):
                    st.session_state["rh_open"] = p["id"]
                    st.rerun()
    if not shown:
        st.info("You are not in any project yet.")


def _project(u, pid):
    rows = db_select("projects", eq={"id": pid})
    if not rows:
        st.error("Project not found.")
        return
    p = rows[0]
    members = db_select("members", eq={"project_id": pid})
    mine = next((m for m in members if m.get("user_id") == u["id"]), None)
    is_owner = p.get("owner_id") == u["id"]
    can_edit = is_owner or _is_mod(u) or (mine and mine.get("status") == "accepted")
    if p.get("status") != "approved" and not (is_owner or _is_mod(u)):
        st.error("This project is not public.")
        return

    if st.button("← Back to board"):
        st.session_state.pop("rh_open", None)
        st.rerun()
    st.markdown(f"## {p['title']}")
    st.caption(f"{p.get('field')} · {p.get('study_type')} · Lead: {p.get('owner_name')} · "
               f"Status: {p.get('status')}"
               + (f" · Mentor: {p['mentor_name']}" if p.get("mentor_name") else ""))
    _stage_bar(p.get("stage", STAGES[0]))
    if p.get("status") == "pending":
        st.info("Waiting for faculty approval.")
    t = st.tabs(["Overview", "Team", "References", "Updates", "Ethics and authorship"])

    with t[0]:
        st.markdown("**Research question**")
        st.write(p.get("question"))
        st.markdown("**Background**")
        st.write(p.get("background"))
        if p.get("seeking"):
            st.caption("Looking for: " + p["seeking"])
        if can_edit:
            cur = STAGES.index(p.get("stage", STAGES[0]))
            new = st.selectbox("Move project stage", STAGES, index=cur, key=f"rh_stg_{pid}")
            if st.button("Save stage", key=f"rh_sv_{pid}") and new != p.get("stage"):
                if new in STAGES[4:] and p.get("ethics_status") not in DATA_GATE_OK:
                    st.error("Blocked: record an ethics status of 'Not required (with reason)' or "
                             "'Approved (with reference)' in the Ethics tab before data collection or later stages.")
                elif new in STAGES[4:] and not (p.get("ethics_note") or "").strip():
                    st.error("Blocked: add the reason or approval reference in the Ethics tab.")
                else:
                    db_update("projects", pid, {"stage": new})
                    db_insert("updates", {"project_id": pid, "author": u["name"],
                                          "text": f"Stage changed: {p.get('stage')} → {new}"})
                    st.rerun()

    with t[1]:
        for m in members:
            if m.get("status") == "accepted":
                st.write(f"- **{m['name']}** - {m['role']}")
        pend = [m for m in members if m.get("status") == "pending"]
        if (is_owner or _is_mod(u)) and pend:
            st.markdown("**Join requests**")
            for m in pend:
                c = st.columns([3, 1, 1])
                c[0].write(f"{m['name']} as {m['role']}: {m.get('message', '')}")
                if c[1].button("Accept", key=f"rh_ac_{m['id']}"):
                    db_update("members", m["id"], {"status": "accepted"})
                    st.rerun()
                if c[2].button("Decline", key=f"rh_dc_{m['id']}"):
                    db_update("members", m["id"], {"status": "declined"})
                    st.rerun()
        if u["signed_in"] and not mine and p.get("status") == "approved":
            with st.form(f"rh_join_{pid}"):
                role = st.selectbox("I can help as", TEAM_ROLES)
                msg = st.text_area("Short note (skills, availability)", height=70)
                if st.form_submit_button("Request to join"):
                    db_insert("members", {"project_id": pid, "user_id": u["id"], "name": u["name"],
                                          "role": role, "status": "pending", "message": msg})
                    st.success("Request sent to the project lead.")
        elif mine and mine.get("status") == "pending":
            st.caption("Your join request is pending.")

    with t[2]:
        st.caption("References are added by PubMed ID so anyone can check them.")
        for r in db_select("refs", eq={"project_id": pid}):
            link = f"https://pubmed.ncbi.nlm.nih.gov/{r['pmid']}/"
            st.markdown(f"- {r.get('citation')} [PMID {r['pmid']}]({link})"
                        + (f" · DOI {r['doi']}" if r.get("doi") else ""))
        if can_edit:
            pm = st.text_input("PubMed ID (digits only)", key=f"rh_pm_{pid}")
            if st.button("Look up and add", key=f"rh_pa_{pid}"):
                info = _pubmed(pm)
                if not info:
                    st.error("Could not verify that PubMed ID. Check the number. "
                             "Nothing was added; unverifiable references are not accepted.")
                else:
                    st.success(info["citation"])
                    db_insert("refs", {"project_id": pid, "pmid": info["pmid"], "title": info["title"],
                                       "citation": info["citation"], "doi": info["doi"], "added_by": u["name"]})
                    st.rerun()

    with t[3]:
        if can_edit:
            txt = st.text_area("Add a progress note (no patient identifiers)", key=f"rh_un_{pid}", height=80)
            if st.button("Post update", key=f"rh_up_{pid}") and txt.strip():
                db_insert("updates", {"project_id": pid, "author": u["name"], "text": txt.strip()})
                st.rerun()
        for x in db_select("updates", eq={"project_id": pid}, order="created_at.desc"):
            st.markdown(f"**{x.get('author')}** · {str(x.get('created_at', ''))[:16]}  \n{x.get('text')}")

    with t[4]:
        st.write(f"Ethics status: **{p.get('ethics_status')}**")
        if p.get("ethics_note"):
            st.write("Reason / reference: " + p["ethics_note"])
        if can_edit:
            es = st.selectbox("Ethics status", ETHICS, index=ETHICS.index(p.get("ethics_status", ETHICS[0])),
                              key=f"rh_es_{pid}")
            note = st.text_input("Reason (if not required) or approval reference", value=p.get("ethics_note", ""),
                                 key=f"rh_en_{pid}")
            if st.button("Save ethics record", key=f"rh_esv_{pid}"):
                db_update("projects", pid, {"ethics_status": es, "ethics_note": note})
                db_insert("updates", {"project_id": pid, "author": u["name"], "text": f"Ethics record: {es}. {note}"})
                st.rerun()
        st.markdown("**Authorship (ICMJE)**")
        st.write(RULES[2][1])
        st.caption("Faculty should confirm an ethics status; the hub records it but is not an ethics committee.")


def _moderate(u):
    if not _is_mod(u):
        st.info("Faculty only.")
        return
    seniors = []
    try:
        from mentor_directory import list_verified_seniors
        seniors = [s.get("name") for s in list_verified_seniors() if s.get("name")]
    except Exception:
        pass
    pend = [p for p in db_select("projects", order="created_at.asc") if p.get("status") == "pending"]
    if not pend:
        st.success("Nothing waiting for review.")
    for p in pend:
        with st.container(border=True):
            st.markdown(f"**{p['title']}** · {p.get('field')} · {p.get('study_type')} · by {p.get('owner_name')}")
            st.write(p.get("question"))
            st.caption(p.get("background"))
            note = st.text_input("Note to the student", key=f"rh_mn_{p['id']}")
            mentor = st.selectbox("Assign mentor (optional)", [""] + seniors, key=f"rh_mm_{p['id']}") if seniors \
                else st.text_input("Mentor name (optional)", key=f"rh_mm_{p['id']}")
            c = st.columns(3)
            if c[0].button("Approve", key=f"rh_ap_{p['id']}", type="primary"):
                db_update("projects", p["id"], {"status": "approved", "moderator_note": note, "mentor_name": mentor or ""})
                st.rerun()
            if c[1].button("Request changes", key=f"rh_ch_{p['id']}"):
                db_update("projects", p["id"], {"status": "changes", "moderator_note": note or "Please revise."})
                st.rerun()
            if c[2].button("Reject", key=f"rh_rj_{p['id']}"):
                db_update("projects", p["id"], {"status": "rejected", "moderator_note": note})
                st.rerun()


def _rules():
    for h, b in RULES:
        st.markdown(f"**{h}.** {b}")


def render_research_hub():
    u = _user()
    st.markdown("### 🔬 Research Hub")
    st.caption("Propose research ideas, build teams with mentors, and follow a stage-gated pathway "
               "from idea to submission. Student research training - not peer-reviewed publication.")
    if not _sb():
        st.warning("DEMO MODE: Supabase is not configured, so nothing is saved after this session.")
    if st.session_state.get("rh_open"):
        _project(u, st.session_state["rh_open"])
        return
    tabs = ["Project board", "Propose a project", "My projects", "Rules & ethics"]
    if _is_mod(u):
        tabs.append("Faculty review")
    t = st.tabs(tabs)
    with t[0]:
        _board(u)
    with t[1]:
        _propose(u)
    with t[2]:
        _mine(u)
    with t[3]:
        _rules()
    if _is_mod(u):
        with t[4]:
            _moderate(u)
