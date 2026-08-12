# ════════════════════════════════════════════════════════════════════════════
#  DIAGNOSTIC DELAY → COMPLICATION RISK SIMULATOR
#  ┌──────────────────────────────────────────────────────────────────────┐
#  │  page_deterioration_simulator() — Streamlit page exposing the       │
#  │  deterioration model. Three modes:                                   │
#  │                                                                      │
#  │    1. 🎯 Single Patient  — pick condition, set delays, see risk     │
#  │    2. 📊 Cohort Analysis  — upload CSV, get aggregate metrics       │
#  │    3. 📚 Curves Library   — visualize all curve shapes side by side  │
#  │                                                                      │
#  │  Backed by deterioration_model.py + patient_data.py.                 │
#  └──────────────────────────────────────────────────────────────────────┘
#
#  HOW TO WIRE INTO app.py (3 easy steps):
#  ────────────────────────────────────────────────────────────────────────
#  STEP 1 — Add this import near the top of app.py (after existing imports):
#
#      from deterioration_simulator import page_deterioration_simulator
#
#  STEP 2 — Add a sidebar nav button (e.g. under "Advanced Learning"):
#
#      if st.button("⏱️ Diagnostic Delay Simulator", use_container_width=True,
#                   key="nav_deterioration"):
#          st.session_state.page = "deterioration"
#          st.rerun()
#
#  STEP 3 — Add this elif branch to the routing block at the bottom:
#
#      elif p == "deterioration": page_deterioration_simulator()
#
#  Required companion files (must sit next to app.py):
#      deterioration_model.py
#      patient_data.py
#  Required pip packages: pydantic, pandas, plotly
#  (plotly is already in requirements.txt; pydantic may need to be added.)
# ════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import io
from typing import List

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

from deterioration_model import (
    CONDITIONS,
    RiskModel,
    analyze_cohort,
    compare_real_vs_virtual,
    compute_complication_risk,
)
from patient_data import PatientCase, load_cohort_from_csv


# ── Risk curve generator (used by Single-Patient + Curves Library tabs) ─────
def _build_risk_curve(condition_key: str, max_hours: float = 48.0, n_points: int = 200):
    """Return (x_hours, y_risk) arrays for plotting the model's risk curve."""
    c = CONDITIONS[condition_key]
    xs = [max_hours * i / (n_points - 1) for i in range(n_points)]
    ys = [compute_complication_risk(condition_key, x) for x in xs]
    return xs, ys, c


def _render_curve_plot(
    conditions_to_plot: List[str],
    highlight_delay: float = None,
    highlight_label: str = None,
    title: str = "Risk vs. Diagnostic Delay",
    max_hours: float = 24.0,
):
    """Plot one or more risk curves on a single chart. Optional delay marker."""
    if not PLOTLY_OK:
        st.warning("Plotly is not installed — install it to see risk curves.")
        return

    fig = go.Figure()
    colors = ["#dc2626", "#2563eb", "#059669", "#d97706", "#7c3aed", "#0891b2"]

    for i, ck in enumerate(conditions_to_plot):
        if ck not in CONDITIONS:
            continue
        xs, ys, c = _build_risk_curve(ck, max_hours=max_hours)
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="lines",
            name=f"{c.name} ({c.model.value})",
            line=dict(color=colors[i % len(colors)], width=3),
            hovertemplate=(
                f"<b>{c.name}</b><br>"
                "Delay: %{x:.1f}h<br>"
                "Risk: %{y:.1%}<extra></extra>"
            ),
        ))

    if highlight_delay is not None:
        for ck in conditions_to_plot:
            if ck not in CONDITIONS:
                continue
            risk_at = compute_complication_risk(ck, highlight_delay)
            fig.add_trace(go.Scatter(
                x=[highlight_delay],
                y=[risk_at],
                mode="markers",
                marker=dict(size=14, color="black", symbol="x",
                            line=dict(width=2, color="white")),
                name=f"@{highlight_delay:.1f}h → {risk_at:.1%}" if highlight_label is None
                else f"{highlight_label} @{highlight_delay:.1f}h",
                showlegend=True,
                hovertemplate=(
                    f"<b>{CONDITIONS[ck].name}</b><br>"
                    f"Delay: {highlight_delay:.1f}h<br>"
                    f"Risk: {risk_at:.1%}<extra></extra>"
                ),
            ))

    fig.update_layout(
        title=title,
        xaxis_title="Diagnostic Delay (hours)",
        yaxis_title="Estimated Complication Risk",
        yaxis=dict(tickformat=".0%", range=[0, 1]),
        xaxis=dict(range=[0, max_hours]),
        hovermode="closest",
        height=460,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        margin=dict(l=40, r=20, t=50, b=80),
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Tab 1: Single-patient interactive simulator ─────────────────────────────
def _tab_single_patient():
    st.markdown(
        '<div class="section-header">🎯 Single-Patient Counterfactual</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Pick a condition, set the **real** hospital's diagnostic delay and the "
        "**virtual** hospital's delay, and see how much complication risk would "
        "drop. Drag the sliders — the chart and numbers update in real time."
    )

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        condition_key = st.selectbox(
            "Condition",
            options=list(CONDITIONS.keys()),
            format_func=lambda k: f"{CONDITIONS[k].name}  ({CONDITIONS[k].model.value})",
            key="sim_condition",
        )
        c = CONDITIONS[condition_key]
        st.markdown(
            f"<div class='alert-info' style='font-size:.8rem;'>"
            f"<b>{c.name}</b> · baseline {c.baseline_risk:.0%} · "
            f"{c.model.value} model"
            + (f" · critical window {c.critical_window_hours}h"
               if c.critical_window_hours else "")
            + f"<br><span style='color:#64748b;'>{c.source}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        real_delay = st.slider(
            "🏥 Real hospital diagnostic delay (hours)",
            min_value=0.0,
            max_value=24.0,
            value=6.0,
            step=0.25,
            help="Time from patient presentation to confirmed diagnosis "
                 "(sum of lab turnaround + imaging turnaround + clinician review).",
            key="sim_real_delay",
        )
        virtual_delay = st.slider(
            "💻 Virtual hospital diagnostic delay (hours)",
            min_value=0.0,
            max_value=24.0,
            value=1.5,
            step=0.25,
            key="sim_virtual_delay",
        )

        # ── Live results ────────────────────────────────────────────────
        result = compare_real_vs_virtual(condition_key, real_delay, virtual_delay)
        st.markdown("---")
        st.markdown("#### Estimated Complication Risk")

        m1, m2, m3 = st.columns(3)
        m1.metric("Real hospital", f"{result['real_hospital']['estimated_complication_risk']:.1%}")
        m2.metric("Virtual hospital", f"{result['virtual_hospital']['estimated_complication_risk']:.1%}")
        m3.metric(
            "Risk reduction",
            f"{result['absolute_risk_reduction']:.1%}",
            delta=f"{result['relative_risk_reduction_pct']:.1f}% relative",
        )

    with col2:
        st.markdown("#### Risk Curve")
        _render_curve_plot(
            conditions_to_plot=[condition_key],
            highlight_delay=real_delay,
            highlight_label="Real",
            max_hours=max(24.0, real_delay + 2),
            title=f"{c.name} — Risk vs. Delay",
        )
        if virtual_delay != real_delay:
            v_risk = compute_complication_risk(condition_key, virtual_delay)
            st.markdown(
                f"<div class='alert-good' style='font-size:.85rem;'>"
                f"💻 At <b>{virtual_delay:.1f}h</b> (virtual), risk drops to "
                f"<b>{v_risk:.1%}</b> — saving "
                f"<b>{result['absolute_risk_reduction']:.1%}</b> absolute risk."
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        "<div class='alert-info' style='font-size:.75rem;'>"
        "⚠️ <b>Disclaimer:</b> All risk values are simulated estimates from "
        "modeled time-sensitivity coefficients. These coefficients are "
        "placeholders and must be validated against published clinical data "
        "before any operational use."
        "</div>",
        unsafe_allow_html=True,
    )


# ── Tab 2: Cohort analysis (CSV upload) ─────────────────────────────────────
def _tab_cohort():
    st.markdown(
        '<div class="section-header">📊 Cohort Analysis — Real vs. Virtual Hospital</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Upload a CSV of patient encounters and get aggregate risk-reduction "
        "metrics comparing the real hospital against the virtual hospital."
    )

    with st.expander("📋 Required CSV schema", expanded=False):
        st.markdown("""
        | Column | Required | Description |
        |---|---|---|
        | `patient_id` | ✅ | Unique identifier |
        | `condition_key` | ✅ | One of: `sepsis`, `ischemic_stroke`, `stemi`, `appendicitis` |
        | `real_delay_hours` | ✅ | Observed total diagnostic delay at real hospital |
        | `virtual_delay_hours` | ✅ | Expected delay at virtual hospital |
        | `lab_delay_hours` | optional | Lab component (must sum with imaging) |
        | `imaging_delay_hours` | optional | Imaging component (must sum with imaging) |
        | `actual_outcome` | optional | Free-text observed outcome (for your records) |
        """)

    uploaded = st.file_uploader("Upload patient cohort CSV", type=["csv"],
                                key="sim_csv_upload")
    sample_btn = st.button("📥 Load a 10-patient sample", key="sim_load_sample")

    if sample_btn:
        # The sample CSV lives next to this module. We ship it for demos.
        import os
        sample_path = os.path.join(os.path.dirname(__file__), "sample_cohort.csv")
        try:
            cases = load_cohort_from_csv(sample_path)
            st.session_state["_sim_cohort_cases"] = cases
            st.success(f"Loaded {len(cases)} sample patients from sample_cohort.csv")
        except FileNotFoundError:
            st.error("sample_cohort.csv not found next to deterioration_simulator.py")

    if uploaded is not None:
        try:
            content = uploaded.read().decode("utf-8")
            cases = load_cohort_from_csv(io.StringIO(content))
            st.session_state["_sim_cohort_cases"] = cases
            st.success(f"Loaded {len(cases)} patients from upload")
        except ValueError as e:
            st.error(f"CSV validation failed: {e}")
            return
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
            return

    cases: List[PatientCase] | None = st.session_state.get("_sim_cohort_cases")
    if not cases:
        st.info("Upload a CSV or click 'Load sample' to see the cohort analysis.")
        return

    result = analyze_cohort(cases)
    summary = result["summary"]
    per_patient = result["per_patient"]

    # ── Top-line metrics ────────────────────────────────────────────────
    st.markdown("#### Headline numbers")
    a, b, c, d = st.columns(4)
    a.metric("Patients", summary["n_patients"])
    b.metric("Mean risk reduction",
             f"{summary['mean_absolute_risk_reduction']:.1%}",
             delta=f"{summary['mean_relative_risk_reduction_pct']:.1f}% relative")
    c.metric("Prevented threshold crossings",
             summary["prevented_threshold_crossings"],
             help="Patients whose risk would cross 2× baseline under the real "
                  "hospital but stay below under the virtual hospital.")
    d.metric("Total absolute risk saved",
             f"{summary['total_absolute_risk_reduction']:.2%}")

    # ── Per-condition breakdown ─────────────────────────────────────────
    st.markdown("#### Per-condition breakdown")
    cond_df = pd.DataFrame([
        {
            "Condition": CONDITIONS[ck]["name"] if isinstance(CONDITIONS[ck], dict)
                          else CONDITIONS[ck].name,
            "n": v["n"],
            "Mean absolute reduction": v["mean_absolute_risk_reduction"],
            "Mean relative reduction (%)": v["mean_relative_risk_reduction_pct"],
        }
        for ck, v in summary["by_condition"].items()
    ])
    st.dataframe(cond_df, use_container_width=True, hide_index=True)

    # ── Per-patient chart ──────────────────────────────────────────────
    if PLOTLY_OK and per_patient:
        st.markdown("#### Per-patient risk: Real vs. Virtual")
        pp_df = pd.DataFrame(per_patient)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Real hospital",
            x=pp_df["patient_id"],
            y=pp_df["real_risk"],
            marker_color="#dc2626",
            hovertemplate="<b>%{x}</b><br>Real risk: %{y:.1%}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            name="Virtual hospital",
            x=pp_df["patient_id"],
            y=pp_df["virtual_risk"],
            marker_color="#059669",
            hovertemplate="<b>%{x}</b><br>Virtual risk: %{y:.1%}<extra></extra>",
        ))
        fig.update_layout(
            barmode="group",
            yaxis=dict(tickformat=".0%", range=[0, 1]),
            xaxis_title="Patient",
            yaxis_title="Estimated complication risk",
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=-0.25,
                        xanchor="center", x=0.5),
            margin=dict(l=40, r=20, t=30, b=80),
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("View raw per-patient results", expanded=False):
            st.dataframe(pp_df, use_container_width=True, hide_index=True)


# ── Tab 3: Curves library (educational) ────────────────────────────────────
def _tab_curves_library():
    st.markdown(
        '<div class="section-header">📚 Risk Curves Library</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Side-by-side view of the three modeled time-sensitivity curves and "
        "every condition currently in the library. Useful for teaching the "
        "concept of time-to-treatment in acute care."
    )

    col1, col2 = st.columns([1, 2], gap="large")
    with col1:
        st.markdown("##### Curve shapes")
        st.markdown("""
        - **Linear** — risk rises steadily with delay (e.g. sepsis: every hour
          of delay adds a flat risk increment).
        - **Exponential** — risk grows faster the longer you wait (e.g. stroke:
          the tPA window decays exponentially).
        - **Threshold** — risk stays flat until a critical window, then jumps
          (e.g. STEMI: door-to-balloon).
        """)

        st.markdown("##### Conditions in the library")
        for k, c in CONDITIONS.items():
            st.markdown(
                f"<div style='font-size:.82rem;padding:.3rem 0;'>"
                f"<b>{c.name}</b> "
                f"<span class='badge' style='background:#e0e7ff;color:#3730a3;'>"
                f"{c.model.value}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    with col2:
        st.markdown("##### All conditions overlaid")
        _render_curve_plot(
            conditions_to_plot=list(CONDITIONS.keys()),
            max_hours=24.0,
            title="All conditions — risk vs. delay",
        )


# ── Main page entry point ───────────────────────────────────────────────────
def page_deterioration_simulator():
    st.markdown("""
    <div class="main-header">
      <h1>⏱️ Diagnostic Delay Risk Simulator</h1>
      <p>Compare complication risk between the real hospital and the virtual hospital ·
         Learn why time-to-diagnosis matters for acute conditions</p>
    </div>""", unsafe_allow_html=True)

    st.markdown(
        "<div class='alert-info' style='font-size:.8rem;'>"
        "📐 <b>What this is:</b> a counterfactual simulator. It estimates how "
        "complication risk changes with diagnostic delay, using published-style "
        "time-sensitivity coefficients for four acute conditions. Coefficients are "
        "placeholders — validate against your own data before any real use."
        "</div>",
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs([
        "🎯 Single Patient",
        "📊 Cohort Analysis",
        "📚 Curves Library",
    ])

    with tab1:
        _tab_single_patient()
    with tab2:
        _tab_cohort()
    with tab3:
        _tab_curves_library()


# ── Standalone smoke test ───────────────────────────────────────────────────
if __name__ == "__main__":
    # Quick sanity check when run directly (won't launch Streamlit).
    print("Conditions available:", list(CONDITIONS.keys()))
    for k in CONDITIONS:
        xs, ys, c = _build_risk_curve(k, max_hours=12.0)
        peak = max(ys)
        print(f"  {c.name:25s} ({c.model.value:11s}) peak at 12h = {peak:.1%}")
