"""
Diagnostic Delay -> Complication Risk Simulator
-------------------------------------------------
Models how complication/mortality risk changes as a function of time-to-diagnosis
(labs, imaging turnaround), based on published time-sensitivity relationships for
specific conditions.

IMPORTANT: The coefficients below are illustrative placeholders. Before using this
in anything beyond a prototype, replace them with values sourced directly from
published studies (see `source` field per condition) and have a clinician review
the curves. This tool produces SIMULATED / ESTIMATED risk trajectories, not real
predictions for real patients.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Dict, List, Optional


class RiskModel(Enum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    THRESHOLD = "threshold"  # risk stays flat until a critical window, then jumps


@dataclass
class ConditionProfile:
    name: str
    baseline_risk: float          # complication/mortality risk at t=0 (fraction, 0-1)
    time_coefficient: float       # risk increase per hour of delay (model-dependent)
    model: RiskModel
    critical_window_hours: float = None  # used only for THRESHOLD model
    source: str = ""              # citation placeholder - fill in with real reference


# Example condition library.
# Replace `time_coefficient` and `baseline_risk` with values pulled from literature
# specific to the diagnosis you're modeling (sepsis, stroke, MI, appendicitis, etc.)
CONDITIONS = {
    "sepsis": ConditionProfile(
        name="Sepsis",
        baseline_risk=0.10,
        time_coefficient=0.03,   # +3% relative risk per hour delay (placeholder)
        model=RiskModel.LINEAR,
        source="TODO: cite specific sepsis time-to-antibiotics mortality study",
    ),
    "ischemic_stroke": ConditionProfile(
        name="Ischemic Stroke",
        baseline_risk=0.15,
        time_coefficient=0.05,
        model=RiskModel.EXPONENTIAL,
        source="TODO: cite tPA time-to-treatment efficacy decay study",
    ),
    "stemi": ConditionProfile(
        name="STEMI (Heart Attack)",
        baseline_risk=0.08,
        time_coefficient=0.04,
        model=RiskModel.THRESHOLD,
        critical_window_hours=1.5,  # "door-to-balloon" style critical window
        source="TODO: cite door-to-balloon time outcome study",
    ),
    "appendicitis": ConditionProfile(
        name="Appendicitis",
        baseline_risk=0.05,
        time_coefficient=0.015,
        model=RiskModel.THRESHOLD,
        critical_window_hours=24,
        source="TODO: cite perforation-risk-by-delay study",
    ),
}


def compute_complication_risk(condition_key: str, delay_hours: float) -> float:
    """
    Returns an estimated complication risk (0-1) given a diagnostic delay in hours.
    """
    if condition_key not in CONDITIONS:
        raise ValueError(f"Unknown condition: {condition_key}")

    c = CONDITIONS[condition_key]

    if c.model == RiskModel.LINEAR:
        risk = c.baseline_risk + c.time_coefficient * delay_hours

    elif c.model == RiskModel.EXPONENTIAL:
        risk = c.baseline_risk * math.exp(c.time_coefficient * delay_hours)

    elif c.model == RiskModel.THRESHOLD:
        if delay_hours <= c.critical_window_hours:
            risk = c.baseline_risk
        else:
            overage = delay_hours - c.critical_window_hours
            risk = c.baseline_risk + c.time_coefficient * overage

    else:
        raise ValueError(f"Unhandled model type: {c.model}")

    return min(risk, 1.0)  # cap at 100%


def compare_real_vs_virtual(condition_key: str, real_delay_hours: float, virtual_delay_hours: float) -> dict:
    """
    Compares projected complication risk under real hospital turnaround time
    vs the virtual hospital's (presumably faster) turnaround time.
    """
    real_risk = compute_complication_risk(condition_key, real_delay_hours)
    virtual_risk = compute_complication_risk(condition_key, virtual_delay_hours)

    return {
        "condition": CONDITIONS[condition_key].name,
        "real_hospital": {
            "delay_hours": real_delay_hours,
            "estimated_complication_risk": round(real_risk, 4),
        },
        "virtual_hospital": {
            "delay_hours": virtual_delay_hours,
            "estimated_complication_risk": round(virtual_risk, 4),
        },
        "absolute_risk_reduction": round(real_risk - virtual_risk, 4),
        "relative_risk_reduction_pct": round(
            ((real_risk - virtual_risk) / real_risk * 100) if real_risk > 0 else 0, 2
        ),
        "disclaimer": "Simulated estimate based on modeled time-sensitivity coefficients, not a real clinical prediction.",
    }


# ----------------------------------------------------------------------
# Cohort-level analysis (added for virtual-hospital patient-data workflow)
# ----------------------------------------------------------------------

def analyze_patient(patient) -> Dict:
    """
    Run a single patient's counterfactual. `patient` is a PatientCase.
    Returns a PatientResult-shaped dict.
    """
    real_risk = compute_complication_risk(patient.condition_key, patient.real_delay_hours)
    virtual_risk = compute_complication_risk(patient.condition_key, patient.virtual_delay_hours)
    abs_reduction = real_risk - virtual_risk
    rel_reduction = (abs_reduction / real_risk * 100) if real_risk > 0 else 0.0

    return {
        "patient_id": patient.patient_id,
        "condition_key": patient.condition_key,
        "real_delay_hours": patient.real_delay_hours,
        "virtual_delay_hours": patient.virtual_delay_hours,
        "real_risk": round(real_risk, 4),
        "virtual_risk": round(virtual_risk, 4),
        "absolute_risk_reduction": round(abs_reduction, 4),
        "relative_risk_reduction_pct": round(rel_reduction, 2),
    }


def analyze_cohort(patients) -> Dict:
    """
    Run counterfactual analysis on a full cohort of PatientCase objects.
    Returns per-patient results + aggregate summary statistics.
    """
    from collections import defaultdict

    per_patient: List[Dict] = []
    by_condition_abs: Dict[str, List[float]] = defaultdict(list)
    by_condition_rel: Dict[str, List[float]] = defaultdict(list)

    all_abs: List[float] = []
    all_rel: List[float] = []

    # Track patients who would cross a meaningful threshold under real delay.
    # Threshold = baseline_risk * 2 (i.e. risk has at least doubled from
    # presentation). This is a reasonable default; make it configurable later.
    threshold_crossed_real = 0
    threshold_crossed_virtual = 0
    prevented_threshold_crossings = 0

    for p in patients:
        r = analyze_patient(p)
        per_patient.append(r)
        all_abs.append(r["absolute_risk_reduction"])
        all_rel.append(r["relative_risk_reduction_pct"])
        by_condition_abs[p.condition_key].append(r["absolute_risk_reduction"])
        by_condition_rel[p.condition_key].append(r["relative_risk_reduction_pct"])

        baseline = CONDITIONS[p.condition_key].baseline_risk
        threshold = min(baseline * 2, 0.5)  # cap at 50% so it's a meaningful signal
        if r["real_risk"] >= threshold:
            threshold_crossed_real += 1
        if r["virtual_risk"] >= threshold:
            threshold_crossed_virtual += 1
        if r["real_risk"] >= threshold and r["virtual_risk"] < threshold:
            prevented_threshold_crossings += 1

    n = len(per_patient)
    summary = {
        "n_patients": n,
        "mean_absolute_risk_reduction": round(sum(all_abs) / n, 4) if n else 0.0,
        "mean_relative_risk_reduction_pct": round(sum(all_rel) / n, 2) if n else 0.0,
        "total_absolute_risk_reduction": round(sum(all_abs), 4),
        "patients_crossing_threshold_real": threshold_crossed_real,
        "patients_crossing_threshold_virtual": threshold_crossed_virtual,
        "prevented_threshold_crossings": prevented_threshold_crossings,
        "by_condition": {
            ck: {
                "n": len(by_condition_abs[ck]),
                "mean_absolute_risk_reduction": round(
                    sum(by_condition_abs[ck]) / len(by_condition_abs[ck]), 4
                ) if by_condition_abs[ck] else 0.0,
                "mean_relative_risk_reduction_pct": round(
                    sum(by_condition_rel[ck]) / len(by_condition_rel[ck]), 2
                ) if by_condition_rel[ck] else 0.0,
            }
            for ck in by_condition_abs
        },
        "disclaimer": (
            "All values are simulated estimates from modeled time-sensitivity curves. "
            "Coefficients are placeholders and must be validated against clinical "
            "data before any operational use."
        ),
    }

    return {"summary": summary, "per_patient": per_patient}


if __name__ == "__main__":
    # Example usage
    result = compare_real_vs_virtual(
        condition_key="sepsis",
        real_delay_hours=6.0,      # e.g. real hospital took 6h to get labs back + diagnose
        virtual_delay_hours=1.5,   # virtual hospital simulated faster turnaround
    )
    import json
    print(json.dumps(result, indent=2))
