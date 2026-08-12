"""
Patient-case data model + CSV loader for the diagnostic-delay simulator.

Each PatientCase represents one clinical encounter. You provide the *observed*
diagnostic delay from the real hospital, plus the *counterfactual* delay you
expect under the virtual hospital (faster labs/imaging). The simulator
estimates complication risk under each and computes the per-patient benefit.

CSV schema (one row per patient):
    patient_id,condition_key,real_delay_hours,virtual_delay_hours

`real_delay_hours` and `virtual_delay_hours` can each be a single total value
OR a sum of components (lab_delay_hours + imaging_delay_hours). The helper
`load_cohort_from_csv` handles both shapes.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from deterioration_model import CONDITIONS


class PatientCase(BaseModel):
    """One patient encounter with observed + counterfactual diagnostic delay."""

    patient_id: str
    condition_key: str
    real_delay_hours: float = Field(ge=0)
    virtual_delay_hours: float = Field(ge=0)
    lab_delay_hours: Optional[float] = Field(default=None, ge=0)
    imaging_delay_hours: Optional[float] = Field(default=None, ge=0)
    actual_outcome: Optional[str] = Field(
        default=None,
        description="Optional. Free-text or coded observed outcome (for validation only).",
    )

    @field_validator("condition_key")
    @classmethod
    def _condition_must_exist(cls, v: str) -> str:
        if v not in CONDITIONS:
            raise ValueError(
                f"Unknown condition_key '{v}'. "
                f"Valid keys: {sorted(CONDITIONS.keys())}"
            )
        return v

    @model_validator(mode="after")
    def _delays_consistent(self) -> "PatientCase":
        # If component delays are given, they must add up to (or be present
        # alongside) the totals. We don't *force* equality because a clinician
        # might manually override, but we warn-log via exception if not.
        if self.lab_delay_hours is not None and self.imaging_delay_hours is not None:
            component_sum = self.lab_delay_hours + self.imaging_delay_hours
            # Allow 5% tolerance for rounding.
            if abs(component_sum - self.real_delay_hours) > 0.05 * max(component_sum, 1.0):
                raise ValueError(
                    f"real_delay_hours ({self.real_delay_hours}) disagrees with "
                    f"lab+imaging components ({component_sum}). "
                    f"Either set the total to the sum, or leave components blank."
                )
        return self


@dataclass
class PatientResult:
    """Per-patient counterfactual output."""

    patient_id: str
    condition_key: str
    real_delay_hours: float
    virtual_delay_hours: float
    real_risk: float
    virtual_risk: float
    absolute_risk_reduction: float
    relative_risk_reduction_pct: float


def load_cohort_from_csv(path: str | Path) -> List[PatientCase]:
    """
    Load a cohort of patients from CSV.

    Required columns: patient_id, condition_key, real_delay_hours, virtual_delay_hours
    Optional columns: lab_delay_hours, imaging_delay_hours, actual_outcome
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Cohort CSV not found: {path}")

    cases: List[PatientCase] = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        required = {"patient_id", "condition_key", "real_delay_hours", "virtual_delay_hours"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"CSV missing required columns: {sorted(missing)}. "
                f"Found: {reader.fieldnames}"
            )
        for i, row in enumerate(reader, start=2):  # start=2 accounts for header
            try:
                # Convert empty strings to None for optional fields.
                clean_row = {
                    k: (None if v == "" else v)
                    for k, v in row.items()
                }
                cases.append(PatientCase(**clean_row))
            except Exception as e:
                raise ValueError(f"Row {i} failed validation: {e}") from e
    return cases


def patients_to_jsonl(cases: Iterable[PatientCase]) -> str:
    """Serialize a cohort to JSONL — useful for piping into the batch API."""
    import json
    return "\n".join(c.model_dump_json() for c in cases)
