"""
medsim_case_library.py
────────────────────────────────────────────────────────────────────────────
Lets instructors author new deterioration cases (saved permanently to the
same Supabase project the hospital already uses for accounts) and search
PubMed for real case-report references to ground a case in.

Design boundary, on purpose:
  - PubMed search is for REFERENCE/CITATION only. It returns titles, journal,
    year, and a link — never auto-fills clinical fields.
  - The instructor manually enters the actual structured case (vitals,
    deterioration phases, correct interventions). Nothing here auto-generates
    clinical decision content from PubMed text — that risk isn't worth it
    for material students will practice real ACLS judgment against.

This file does NOT modify deterioration.py, app.py, or medsim_room.py's
existing built-in CASES. It's purely additive: custom cases saved here are
converted to the same Case/Phase/Vitals dataclasses deterioration.py already
uses, so DeteriorationEngine can run them exactly like a built-in case.

Requires one new Supabase table (create once in the Supabase dashboard,
same project as vh_users):

    create table vh_medsim_cases (
      id           bigint generated always as identity primary key,
      case_id      text unique not null,
      name         text not null,
      description  text,
      scenario_type text,
      learning_objectives jsonb,
      patient      jsonb,
      baseline_vitals jsonb,
      phases       jsonb,
      alerts       jsonb,
      interventions jsonb,
      debrief_points jsonb,
      pubmed_refs  jsonb,
      created_by   text,
      created_at   timestamp default now()
    );
"""

import json
import requests
import streamlit as st

from deterioration import Case, Phase, Vitals

TABLE = "vh_medsim_cases"


# ── Supabase plumbing (same credentials app.py already uses) ────────────────
def _sb_creds():
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    return url, key


def _sb_available() -> bool:
    url, key = _sb_creds()
    return bool(url and key and not url.startswith("YOUR_"))


def _sb_headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def save_case(case_dict: dict) -> tuple:
    """Insert or upsert a custom case. Returns (success, message)."""
    if not _sb_available():
        return False, "Supabase not configured — cannot save cases permanently."
    url, key = _sb_creds()
    try:
        r = requests.post(
            f"{url}/rest/v1/{TABLE}",
            headers={**_sb_headers(key), "Prefer": "resolution=merge-duplicates,return=representation"},
            json=case_dict, timeout=10,
        )
        if r.status_code in (200, 201):
            return True, "Case saved."
        return False, f"Save failed ({r.status_code}): {r.text[:200]}"
    except Exception as e:
        return False, f"Save failed: {e}"


def list_custom_cases() -> list:
    if not _sb_available():
        return []
    url, key = _sb_creds()
    try:
        r = requests.get(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key),
                          params={"select": "*", "order": "created_at.desc"}, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


def delete_case(case_id: str) -> bool:
    if not _sb_available():
        return False
    url, key = _sb_creds()
    try:
        r = requests.delete(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key),
                             params={"case_id": f"eq.{case_id}"}, timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False


def row_to_case(row: dict) -> Case:
    """Convert a saved Supabase row back into the exact dataclasses
    DeteriorationEngine.start_case() expects — a custom case runs through
    the identical engine as a built-in one."""
    bv = row.get("baseline_vitals", {}) or {}
    vitals = Vitals(
        hr=bv.get("hr", 80), bp_sys=bv.get("bp_sys", 120), bp_dia=bv.get("bp_dia", 80),
        spo2=bv.get("spo2", 98), rr=bv.get("rr", 16), temp=bv.get("temp", 37.0),
        etco2=bv.get("etco2", 35), rhythm=bv.get("rhythm", "sinus"),
    )
    phases = [Phase(**p) for p in row.get("phases", [])]
    return Case(
        case_id=row["case_id"], name=row["name"], description=row.get("description", ""),
        scenario_type=row.get("scenario_type", "Custom"),
        learning_objectives=row.get("learning_objectives", []) or [],
        patient=row.get("patient", {}) or {}, baseline_vitals=vitals, phases=phases,
        alerts=row.get("alerts", {}) or {}, interventions=row.get("interventions", {}) or {},
        debrief_points=row.get("debrief_points", []) or [],
    )


# ── PubMed search (NCBI E-utilities — free, public, reference only) ─────────
def search_pubmed(query: str, max_results: int = 8) -> list:
    """Return [{pmid, title, journal, year, url}] for a search query.
    Reference/citation lookup only — no clinical content is extracted or
    used to populate case fields automatically."""
    if not query.strip():
        return []
    try:
        api_key = st.secrets.get("PUBMED_API_KEY", "")
        base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        params = {"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"}
        if api_key:
            params["api_key"] = api_key
        r = requests.get(f"{base}/esearch.fcgi", params=params, timeout=10)
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        r2 = requests.get(f"{base}/esummary.fcgi",
                           params={"db": "pubmed", "id": ",".join(ids), "retmode": "json",
                                    **({"api_key": api_key} if api_key else {})}, timeout=10)
        result = r2.json().get("result", {})
        out = []
        for pmid in ids:
            item = result.get(pmid)
            if not item:
                continue
            out.append({
                "pmid": pmid,
                "title": item.get("title", "").strip(),
                "journal": item.get("fulljournalname", item.get("source", "")),
                "year": (item.get("pubdate", "") or "")[:4],
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        return out
    except Exception as e:
        st.warning(f"PubMed search failed: {e}")
        return []


# ── Streamlit UI ──────────────────────────────────────────────────────────
def render_pubmed_search():
    st.markdown("#### 🔎 Search PubMed for reference case reports")
    st.caption("Reference/citation only — attach real literature to ground your case. "
               "Does not auto-fill any clinical fields below.")
    q = st.text_input("Search terms", placeholder="e.g. witnessed VFib cardiac arrest gym",
                       key="pm_query")
    if st.button("Search PubMed", key="pm_search_btn"):
        st.session_state.pm_results = search_pubmed(q)

    results = st.session_state.get("pm_results", [])
    picked = st.session_state.setdefault("pm_picked_refs", [])
    for r in results:
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"**{r['title']}**  \n*{r['journal']}, {r['year']}* — "
                        f"[PMID {r['pmid']}]({r['url']})")
        with c2:
            already = any(p["pmid"] == r["pmid"] for p in picked)
            if st.button("✅ Added" if already else "➕ Attach", key=f"pm_add_{r['pmid']}",
                         disabled=already, use_container_width=True):
                picked.append(r)
                st.rerun()

    if picked:
        st.caption("Attached references:")
        for p in picked:
            st.markdown(f"- {p['title']} ({p['year']}) — [link]({p['url']})")


def render_case_author_ui():
    st.markdown("### ✍️ Author a New Case")
    render_pubmed_search()
    st.markdown("---")

    with st.form("case_author_form", clear_on_submit=False):
        st.markdown("#### Case details")
        col1, col2 = st.columns(2)
        with col1:
            case_id = st.text_input("Case ID (unique, no spaces)", placeholder="e.g. sepsis_65f")
            name = st.text_input("Case name", placeholder="e.g. Septic Shock - 65yo Female")
            scenario_type = st.selectbox("Scenario type", ["ACLS", "Emergency", "Post-Op", "Custom"])
        with col2:
            p_name = st.text_input("Patient name", placeholder="e.g. Maria Lopez")
            p_age = st.number_input("Patient age", min_value=0, max_value=120, value=60)
            p_sex = st.selectbox("Sex", ["F", "M"])

        description = st.text_area("Description / presenting scenario")
        learning_objectives = st.text_area("Learning objectives (one per line)")

        st.markdown("#### Baseline vitals")
        vcols = st.columns(6)
        hr = vcols[0].number_input("HR", value=90)
        bp_sys = vcols[1].number_input("BP sys", value=100)
        bp_dia = vcols[2].number_input("BP dia", value=60)
        spo2 = vcols[3].number_input("SpO2", value=94)
        rr = vcols[4].number_input("RR", value=22)
        temp = vcols[5].number_input("Temp", value=38.5, format="%.1f")
        rhythm = st.text_input("Initial rhythm", value="sinus tachycardia")

        st.markdown("#### Deterioration phases")
        st.caption("Add one row per timed phase. `vitals_delta` fields are optional "
                   "changes applied at that timestamp (e.g. hr:+10, spo2:-5).")
        n_phases = st.number_input("Number of phases", min_value=1, max_value=10, value=2)
        phases = []
        for i in range(int(n_phases)):
            st.markdown(f"**Phase {i+1}**")
            pc = st.columns([1, 1, 3, 2])
            t = pc[0].number_input(f"t (sec) #{i}", min_value=0, value=60 * (i + 1), key=f"ph_t_{i}")
            action = pc[1].selectbox(f"Action #{i}", ["stable", "deteriorate", "critical", "resolve"],
                                      key=f"ph_a_{i}")
            message = pc[2].text_input(f"Message #{i}", key=f"ph_m_{i}")
            correct_int = pc[3].text_input(f"Correct intervention #{i}", key=f"ph_ci_{i}")
            delta_raw = st.text_input(f"Vitals delta #{i} (JSON, optional)",
                                       placeholder='{"hr": 10, "spo2": -3}', key=f"ph_d_{i}")
            try:
                delta = json.loads(delta_raw) if delta_raw.strip() else {}
            except Exception:
                delta = {}
                st.warning(f"Phase {i+1}: vitals delta isn't valid JSON, ignoring it.")
            phases.append({"time_seconds": int(t), "action": action, "vitals_delta": delta,
                            "rhythm_change": None, "events": [], "message": message,
                            "correct_intervention": correct_int or None})

        debrief_points = st.text_area("Debrief points (one per line)")
        submitted = st.form_submit_button("💾 Save Case", type="primary")

        if submitted:
            if not case_id.strip() or not name.strip():
                st.error("Case ID and name are required.")
            else:
                row = {
                    "case_id": case_id.strip(), "name": name.strip(),
                    "description": description, "scenario_type": scenario_type,
                    "learning_objectives": [l for l in learning_objectives.splitlines() if l.strip()],
                    "patient": {"name": p_name, "age": int(p_age), "sex": p_sex},
                    "baseline_vitals": {"hr": int(hr), "bp_sys": int(bp_sys), "bp_dia": int(bp_dia),
                                        "spo2": int(spo2), "rr": int(rr), "temp": float(temp),
                                        "etco2": 35, "rhythm": rhythm},
                    "phases": phases,
                    "alerts": {}, "interventions": {},
                    "debrief_points": [l for l in debrief_points.splitlines() if l.strip()],
                    "pubmed_refs": st.session_state.get("pm_picked_refs", []),
                    "created_by": st.session_state.get("auth_user", {}).get("email", "unknown"),
                }
                ok, msg = save_case(row)
                if ok:
                    st.success("✅ Case saved — it will now appear in the MedSim Room case list.")
                    st.session_state.pop("pm_picked_refs", None)
                    st.session_state.pop("pm_results", None)
                else:
                    st.error(msg)
