"""
ashm_population_health.py
────────────────────────────────────────────────────────────────────────────
Months 9-10: Population Health View. Aggregates real logged data from the
fellowship's own tables (AI-audit submissions, junior submissions, case
intake) into simple counts and accuracy views. Honest scope note: with a
small pilot cohort this will show a handful of rows, not "hundreds of
simulated cases" the proposal describes — the charts are built to scale up
automatically as more fellows/students generate real data over time; they
don't fabricate volume that isn't there yet.
"""

import requests
import streamlit as st
import pandas as pd

NAVY, BLUE, TEAL = "#0a2540", "#1a4f8a", "#0e7490"
GREEN, AMBER, RED = "#059669", "#d97706", "#dc2626"
SURFACE, BORDER, TEXT, MUTED = "#ffffff", "#e2e8f0", "#0f172a", "#64748b"


def _sb_creds():
    return st.secrets.get("SUPABASE_URL", ""), st.secrets.get("SUPABASE_KEY", "")


def _sb_available() -> bool:
    url, key = _sb_creds()
    return bool(url and key and not url.startswith("YOUR_"))


def _sb_headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _get(table, params=None):
    if not _sb_available():
        return []
    url, key = _sb_creds()
    try:
        r = requests.get(f"{url}/rest/v1/{table}", headers=_sb_headers(key),
                          params=params or {"select": "*"}, timeout=10)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def page_population_health():
    st.markdown("## 📊 Population Health View")
    st.caption("Months 9–10 · Analyze aggregated outcomes across all fellowship activity to date.")
    st.info("Numbers below reflect real logged activity in this hospital — they'll grow as more "
            "fellows and students use the AI-Auditing, Peer Teaching, and Case Intake modules. "
            "Nothing here is simulated or backfilled.")

    audits = _get("vh_ai_audit_submissions")
    juniors = _get("vh_junior_submissions")
    intake = _get("vh_case_intake")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("AI-audit submissions", len(audits))
        if audits:
            caught = sum(1 for a in audits if a.get("caught_error"))
            st.caption(f"{caught}/{len(audits)} caught the flaw ({caught/len(audits)*100:.0f}%)")
    with c2:
        st.metric("Junior case decisions logged", len(juniors))
        if juniors:
            reviewed = sum(1 for j in juniors if j.get("status") == "reviewed")
            st.caption(f"{reviewed}/{len(juniors)} reviewed")
    with c3:
        st.metric("Cases submitted to intake pipeline", len(intake))
        if intake:
            approved = sum(1 for i in intake if i.get("status") == "approved")
            st.caption(f"{approved}/{len(intake)} approved")

    st.markdown("---")

    if audits:
        st.markdown("#### AI-audit accuracy by case")
        df = pd.DataFrame(audits)
        by_case = df.groupby("case_key")["caught_error"].agg(["sum", "count"])
        by_case["accuracy_%"] = (by_case["sum"] / by_case["count"] * 100).round(0)
        st.bar_chart(by_case["accuracy_%"])
    else:
        st.caption("No AI-audit data yet — chart will populate once fellows start auditing cases.")

    if intake:
        st.markdown("#### Case intake by department")
        df2 = pd.DataFrame(intake)
        if "department" in df2.columns:
            st.bar_chart(df2["department"].value_counts())
    else:
        st.caption("No case intake data yet.")
