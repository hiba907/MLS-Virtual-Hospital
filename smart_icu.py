"""
smart_icu.py - Smart ICU Management module for the MLS Virtual Hospital (additive).

SOURCE OF ALL FIGURES: "Smart 10-Bed ICU: Commercial Feasibility and Investment Proposal"
(Sept 2026), prepared by Dr. Navid Shafigh, Shahid Beheshti University of Medical Sciences,
for Dr. Ali Amirsavadkouhi, Iranian Critical Care Association. Used with the authors' permission.
All money figures are the authors' ILLUSTRATIVE 2026 US dollars, not market quotations.
Nothing here is invented: where the paper gives no number, the student types their own.

Hook-up in app.py:  from smart_icu import render_smart_icu ; render_smart_icu()
"""
import csv
import io
import streamlit as st

CREDIT = ("Source: Shafigh N. Smart 10-Bed ICU: Commercial Feasibility and Investment Proposal, "
          "Sept 2026 (Shahid Beheshti Univ. of Medical Sciences), used with the authors' permission. "
          "Figures are the authors' illustrative 2026 USD.")

BEDS = 10
# Paper section 10.2 (verbatim inputs)
SCEN = {
    "Conservative": dict(occ=50, rev=1200, fixed=2.10, var=650, cap=3.0),
    "Base":         dict(occ=70, rev=1800, fixed=2.20, var=700, cap=3.5),
    "Upside":       dict(occ=85, rev=2300, fixed=2.40, var=800, cap=4.5),
}
# Paper section 10.2 stated results (for comparison with our computation)
PAPER_RES = {
    "Conservative": dict(bd=1825, revm=2.19, opm=3.29, ebitda=-1.10, payback="Not achieved"),
    "Base":         dict(bd=2555, revm=4.60, opm=3.99, ebitda=0.61, payback="5.7 years"),
    "Upside":       dict(bd=3103, revm=7.14, opm=4.88, ebitda=2.26, payback="2.0 years"),
}
PAPER_BREAKEVEN_BASE = 60.3  # paper's stated figure

CAPEX = [  # section 10.3, USD millions (low, high)
    ("Construction and MEP adaptation", 0.8, 2.0, "Medical gases, electrical redundancy, HVAC, infection control, existing shell"),
    ("Bedside equipment", 0.8, 1.6, "Ventilators, monitors, beds, pumps, ultrasound, resuscitation"),
    ("Shared and support systems", 0.3, 0.8, "Central monitoring, blood gas, IT, tele-ICU, storage and transport"),
    ("Smart platform (AI monitoring, databank, dashboard, integration)", 0.15, 0.5,
     "Software licensing or development, servers/cloud, interoperability engineering, cybersecurity"),
    ("Pre-opening and training", 0.15, 0.4, "Recruitment, simulation, protocols, licensing and launch"),
    ("Contingency and working capital", 0.45, 1.2, "Import volatility, ramp-up losses, spares and consumables"),
]
PAPER_CAPEX_TOTAL = (2.85, 6.5)

GATES = [  # section 1 decision table: (signal, proceed when, pause/redesign when)
    ("Demand", "Documented unmet need and referral commitments support at least 60-65% occupancy within 12-18 months",
     "Demand is based mainly on population size or informal optimism"),
    ("Clinical platform", "24-hour intensivist governance, trained nurses, respiratory support, diagnostics and escalation pathways are funded",
     "The plan relies on equipment without a sustainable clinical team"),
    ("Technology platform", "AI monitoring and data governance are budgeted as a core clinical system, not an add-on",
     "Analytics is treated as marketing decoration with no clinical or operational integration"),
    ("Economics", "Base case reaches operating break-even at a realistic occupancy and net yield",
     "Break-even requires more than 80% occupancy or unverified premium pricing"),
    ("Hospital strategy", "ICU (and its data platform) unlocks surgery, emergency, cardiology, oncology, outpatient follow-up or other priority service lines",
     "ICU has no defined relationship to the hospital's growth plan"),
    ("Reputation", "Transparent outcomes and family communication are part of the product",
     "Marketing promises exceed measurable capability"),
]

THRESH = [  # section 10.4
    ("Occupancy ramp", "Below 45% at month 6, or below 60% at month 12", "60% by month 9-12 and 70% stabilized"),
    ("Net collection yield", "More than 10% below contracted or planned yield", "Weekly denial and collection control"),
    ("Length of stay", "Rising without acuity explanation or discharge pathway", "Case-mix adjusted LOS reviewed weekly"),
    ("Staff cost", "Overtime or agency cost structurally exceeds plan", "Core roster filled with sustainable leave coverage"),
    ("Referral concentration", "More than 35% of admissions depend on one doctor or source", "Diversified internal and external pipeline"),
    ("Quality events", "Infection or adverse-event trend undermines trust", "Rapid review, disclosure and corrective action"),
    ("Platform adoption", "Clinical staff bypass or distrust the AI monitoring tools", "Structured training, usability feedback loop and phased rollout"),
]

RISKS = [  # section 12
    ("Occupancy below plan", "Medium", "High", "Pre-opening referral commitments; staged opening; weekly funnel review"),
    ("Nursing shortage", "High", "High", "Recruit early; competency program; retention premium; safe surge policy"),
    ("Payer underpayment or delay", "Medium", "High", "Contract-level costing; preauthorization; denial management"),
    ("Construction or licensing delay", "Medium", "High", "Critical-path plan; regulator engagement; contingency"),
    ("Equipment downtime", "Medium", "High", "Service-level agreements; backup inventory; preventive maintenance"),
    ("Hospital-acquired infection", "Medium", "High", "Bundles, surveillance, staffing, isolation and audit"),
    ("Long-stay bed blockage", "High", "Medium", "Daily goals; early discharge planning; step-down network"),
    ("Referral conflict", "Low-Medium", "Medium", "Co-management charter and return-to-referrer policy"),
    ("Reputation crisis", "Low", "High", "Family communication, incident response and transparent governance"),
    ("Data breach or platform failure", "Low-Medium", "High",
     "Formal cybersecurity policy, access controls, backup systems and incident-response plan"),
]

ROADMAP = [  # section 13
    ("Validate", "Weeks 1-6", "Demand interviews, transfer audit, payer map, site gap analysis, preliminary model", "Evidence supports base case"),
    ("Design", "Weeks 7-14", "Clinical scope, layout, staffing, equipment, licensing, referral proposition, Smart ICU platform architecture", "Approved business case"),
    ("Build and recruit", "Months 4-9", "Construction, procurement, hiring, contracts, protocols, marketing preparation, platform build/integration", "Readiness review passed"),
    ("Commission", "Months 9-10", "Simulation, equipment validation, infection control, hotline, platform go-live testing and soft launch", "License and safe opening"),
    ("Stabilize", "Months 11-18", "8-bed opening if staged, weekly quality and commercial review, expansion to 10 beds, platform adoption review", "Occupancy and safety triggers met"),
    ("Optimize and extend", "Year 2 onward", "Service-line expansion, payer renegotiation, published dashboard, activation of outpatient/hospital-wide extension pathways", "Return and quality targets sustained"),
]

EXTENSIONS = [  # section 5.2
    ("Step-down / post-ICU ward monitoring", "Lighter-touch remote monitoring after ICU; frees ICU beds faster, reduces readmission"),
    ("Hospital-wide early-warning coverage", "Same alerting logic on general wards; fewer preventable arrests and unplanned ICU admissions"),
    ("Outpatient / follow-up clinic", "Post-sepsis recovery, ventilator-weaning follow-up, wound care, post-ICU rehabilitation"),
    ("Tele-ICU for referring hospitals", "Remote monitoring/teleconsultation for smaller facilities"),
    ("Registry and research value", "Standardized databank supports research, quality publications, registry participation"),
]

KPIS = {  # section 14
    "Demand": "Occupancy; admission source; referrals accepted, refused and lost; conversion rate; reasons for refusal",
    "Finance": "Net revenue per occupied day; contribution per case; collection cycle; denials; labor and consumable cost",
    "Flow": "Average length of stay; ventilator days; discharge delay; readmission; transfer turnaround",
    "Quality": "Risk-adjusted mortality where feasible; device infections; pressure injury; medication events; unexpected deterioration",
    "Experience": "Family update compliance; complaints; financial estimate accuracy; referrer satisfaction",
    "Workforce": "Vacancy; turnover; overtime; competency completion; sick leave; staff safety events",
    "Platform": "Alert accuracy and response time; data completeness; system uptime; user adoption; extension enrollment and outcomes",
}

DATASET = ["Admission source", "Diagnosis", "Severity", "Interventions", "Length of stay (days)", "Outcome"]  # section 4.1


def calc(occ_pct, rev, fixed_m, var, beds=BEDS):
    bd = beds * 365 * occ_pct / 100.0
    revenue = bd * rev
    opcost = fixed_m * 1e6 + bd * var
    ebitda = revenue - opcost
    contrib = rev - var
    be = (fixed_m * 1e6) / (beds * 365) / contrib * 100 if contrib > 0 else float("inf")
    return bd, revenue, opcost, ebitda, contrib, be


def _m(x):
    return f"{x/1e6:,.2f}m"


def _tab_calc():
    st.markdown("#### Direct ICU economics (paper section 10.1-10.2)")
    st.caption("Formulas from the paper: occupied bed-days = beds x 365 x occupancy; direct revenue = bed-days x net revenue/day; "
               "operating cost = fixed + bed-days x variable/day; EBITDA = revenue - cost; break-even occupancy = fixed / 3,650 / "
               "contribution per day; payback = capital / EBITDA.")
    pick = st.radio("Start from the paper's scenario", ["Base", "Conservative", "Upside", "My own inputs"], horizontal=True, key="sicu_pick")
    base = SCEN.get(pick, SCEN["Base"])
    c1, c2 = st.columns(2)
    with c1:
        occ = st.number_input("Occupancy (%)", 0.0, 100.0, float(base["occ"]), 1.0, key=f"sicu_occ_{pick}")
        rev = st.number_input("Net realized revenue per occupied day (USD)", 0.0, 100000.0, float(base["rev"]), 50.0, key=f"sicu_rev_{pick}")
    with c2:
        fixed = st.number_input("Annual fixed operating cost (USD millions)", 0.0, 100.0, float(base["fixed"]), 0.05, key=f"sicu_fix_{pick}")
        var = st.number_input("Variable cost per occupied day (USD)", 0.0, 100000.0, float(base["var"]), 25.0, key=f"sicu_var_{pick}")
    cap = st.number_input("Initial capital (USD millions)", 0.0, 100.0, float(base["cap"]), 0.1, key=f"sicu_cap_{pick}")
    bd, revenue, opcost, ebitda, contrib, be = calc(occ, rev, fixed, var)
    a, b, c = st.columns(3)
    a.metric("Occupied bed-days", f"{bd:,.0f}")
    b.metric("Direct revenue (USD)", _m(revenue))
    c.metric("Operating cost (USD)", _m(opcost))
    a.metric("Direct EBITDA (USD)", ("-" if ebitda < 0 else "") + _m(abs(ebitda)))
    b.metric("Contribution / occupied day", f"${contrib:,.0f}")
    c.metric("Break-even occupancy", f"{be:.1f}%")
    st.write("**Simple payback on direct EBITDA:** " +
             (f"{cap*1e6/ebitda:.1f} years" if ebitda > 0 else "not achieved (EBITDA is not positive)"))
    if be > 80:
        st.error("Break-even above 80% occupancy: the paper's rule says pause or redesign.")
    elif be > 65:
        st.warning("Break-even above 60-65% occupancy: outside the paper's 'proceed' range.")
    st.caption("Direct ICU only. The paper deliberately excludes the extension pathways (section 5) from this model, "
               "and says downstream benefits should be counted only when incremental and evidenced.")

    if pick in PAPER_RES:
        p = PAPER_RES[pick]
        st.markdown("**Check against the paper's table**")
        st.table({"Item": ["Occupied bed-days", "Direct revenue", "Operating cost", "Direct EBITDA", "Payback"],
                  "Paper says": [f"{p['bd']:,}", f"${p['revm']}m", f"${p['opm']}m", f"${p['ebitda']}m", p["payback"]],
                  "This app computes": [f"{bd:,.0f}", _m(revenue), _m(opcost), f"{ebitda/1e6:.2f}m",
                                        f"{cap*1e6/ebitda:.1f} years" if ebitda > 0 else "Not achieved"]})
    if pick == "Base":
        st.info(f"Break-even in the base case: the paper states about {PAPER_BREAKEVEN_BASE}%, but its own inputs "
                f"($2.2m fixed, $1,800 revenue, $700 variable) give {be:.1f}%. The other table values match. "
                "Worth confirming with the authors before the figure is taught as fact.")
    st.caption(CREDIT)


def _tab_gates():
    st.markdown("#### Go / pause decision (paper section 1)")
    st.caption("Tick the conditions your scenario meets. The paper recommends approving a six-week validation stage, "
               "not unconditional construction.")
    n = 0
    for i, (sig, proc, pause) in enumerate(GATES):
        ok = st.checkbox(f"**{sig}** - proceed when: {proc}", key=f"sicu_g{i}")
        st.caption(f"Pause or redesign when: {pause}")
        n += 1 if ok else 0
    st.metric("Conditions met", f"{n} / {len(GATES)}")
    if n == len(GATES):
        st.success("All six signals met: the paper would support moving past validation.")
    else:
        st.warning("Not all signals are met: per the paper, validate or redesign first.")
    st.markdown("**Warning thresholds once running (section 10.4)**")
    st.table({"Variable": [t[0] for t in THRESH], "Downside warning": [t[1] for t in THRESH], "Target": [t[2] for t in THRESH]})
    st.caption(CREDIT)


def _tab_capex():
    st.markdown("#### Capital planning range (paper section 10.3, USD millions, excluding land)")
    rows = []
    for name, lo, hi, drv in CAPEX:
        rows.append({"Category": name, "Low": lo, "High": hi, "Cost drivers": drv})
    st.table(rows)
    lo = sum(r[1] for r in CAPEX)
    hi = sum(r[2] for r in CAPEX)
    st.write(f"Sum of rows: **{lo:.2f}m - {hi:.1f}m**. The paper states {PAPER_CAPEX_TOTAL[0]}m - {PAPER_CAPEX_TOTAL[1]}m.")
    st.markdown("**Implementation roadmap (section 13)**")
    st.table({"Phase": [r[0] for r in ROADMAP], "Timing": [r[1] for r in ROADMAP],
              "Key outputs": [r[2] for r in ROADMAP], "Gate": [r[3] for r in ROADMAP]})
    st.markdown("**Extension beyond 10 beds (section 5.2)**")
    for n_, d in EXTENSIONS:
        st.write(f"- **{n_}:** {d}")
    st.caption("The paper says these are strategic options, each needing its own feasibility check, not guaranteed revenue. " + CREDIT)


def _tab_risk():
    st.markdown("#### Risk register (paper section 12)")
    st.table({"Risk": [r[0] for r in RISKS], "Likelihood": [r[1] for r in RISKS],
              "Impact": [r[2] for r in RISKS], "Control": [r[3] for r in RISKS]})
    st.markdown("**Marketing guardrails (section 8.5)**")
    for g in ["Do not promise survival, cure or guaranteed bed availability.",
              "Do not use patient stories, images or clinical details without valid consent.",
              "Do not pay for inappropriate clinical referrals or create incentives that distort admission decisions.",
              "Publish only verified capabilities and audited quality indicators with clear definitions, including for the AI platform.",
              "Separate clinical acceptance from financial counseling while running both quickly and transparently."]:
        st.write("- " + g)
    st.caption("The AI layer is decision support, not decision-making; final judgment stays with the intensivist team (section 4.3). " + CREDIT)


def _tab_databank():
    st.markdown("#### Patient databank - minimum data set (paper section 4.1)")
    st.caption("Practice entering admissions. This is a training exercise with simulated patients only: never enter real patient data. "
               "Entries stay in this session; download as CSV.")
    ss = st.session_state.setdefault("sicu_bank", [])
    with st.form("sicu_form", clear_on_submit=True):
        c = st.columns(3)
        src = c[0].text_input("Admission source")
        dx = c[1].text_input("Diagnosis")
        sev = c[2].text_input("Severity (score used + value)")
        iv = st.text_input("Interventions")
        d = st.columns(2)
        los = d[0].number_input("Length of stay (days)", 0.0, 365.0, 0.0, 0.5)
        out = d[1].selectbox("Outcome", ["Survived - discharged", "Died", "Transferred", "Still admitted"])
        if st.form_submit_button("Add simulated admission") and (src or dx):
            ss.append(dict(zip(DATASET, [src, dx, sev, iv, los, out])))
    if ss:
        st.table(ss)
        done = [r for r in ss if r["Outcome"] != "Still admitted"]
        st.write(f"Entries: **{len(ss)}** | Mean length of stay (finished stays): "
                 + (f"**{sum(r['Length of stay (days)'] for r in done)/len(done):.1f} days**" if done else "n/a")
                 + " | Deaths: " + str(sum(r["Outcome"] == "Died" for r in ss)))
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=DATASET)
        w.writeheader()
        w.writerows(ss)
        st.download_button("Download CSV", buf.getvalue(), "icu_databank_training.csv", "text/csv")
    st.markdown("**Management dashboard KPIs to track (section 14)**")
    for k, v in KPIS.items():
        st.write(f"- **{k}:** {v}")
    st.caption(CREDIT)


def render_smart_icu():
    st.markdown("### 🏥 Smart ICU Management")
    st.caption("A teaching module built on a published feasibility proposal for a 10-bed AI-enabled ICU. "
               "It teaches planning and governance. It is not a real ICU and the AI/early-warning ideas here are educational, "
               "not clinical decision support. All figures are illustrative.")
    t = st.tabs(["Calculator", "Go / pause", "Capital & roadmap", "Risks", "Databank & KPIs"])
    with t[0]:
        _tab_calc()
    with t[1]:
        _tab_gates()
    with t[2]:
        _tab_capex()
    with t[3]:
        _tab_risk()
    with t[4]:
        _tab_databank()
