"""
Deterioration Engine - REAL Medical Cases & ACLS Scenarios
Based on actual medical simulation cases from AHA/ACLS guidelines
"""
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
import random


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    CODE_BLUE = "code_blue"


@dataclass
class Vitals:
    hr: int = 72
    bp_sys: int = 120
    bp_dia: int = 80
    spo2: int = 98
    rr: int = 16
    temp: float = 37.0
    etco2: int = 35
    rhythm: str = "sinus"

    def to_dict(self) -> Dict:
        return {
            "hr": self.hr,
            "bp": f"{self.bp_sys}/{self.bp_dia}",
            "spo2": self.spo2,
            "rr": self.rr,
            "temp": self.temp,
            "etco2": self.etco2,
            "rhythm": self.rhythm
        }

    def get_color(self, param: str) -> str:
        colors = {
            "hr": self._hr_color(),
            "bp": self._bp_color(),
            "spo2": self._spo2_color(),
            "rr": self._rr_color(),
            "temp": self._temp_color()
        }
        return colors.get(param, "green")

    def _hr_color(self) -> str:
        if 60 <= self.hr <= 100: return "green"
        if 50 <= self.hr <= 120: return "amber"
        return "red"

    def _bp_color(self) -> str:
        if 100 <= self.bp_sys <= 140: return "green"
        if 90 <= self.bp_sys <= 180: return "amber"
        return "red"

    def _spo2_color(self) -> str:
        if self.spo2 >= 95: return "green"
        if self.spo2 >= 90: return "amber"
        return "red"

    def _rr_color(self) -> str:
        if 12 <= self.rr <= 20: return "green"
        if 8 <= self.rr <= 30: return "amber"
        return "red"

    def _temp_color(self) -> str:
        if 36.5 <= self.temp <= 37.5: return "green"
        if 35 <= self.temp <= 39: return "amber"
        return "red"


@dataclass
class Phase:
    time_seconds: int
    action: str  # "stable", "deteriorate", "critical", "resolve"
    vitals_delta: Dict = field(default_factory=dict)
    rhythm_change: Optional[str] = None
    events: List[str] = field(default_factory=list)
    message: str = ""
    correct_intervention: Optional[str] = None


@dataclass
class Case:
    case_id: str
    name: str
    description: str
    scenario_type: str  # "ACLS", "Emergency", "Post-Op"
    learning_objectives: List[str]
    patient: Dict
    baseline_vitals: Vitals
    phases: List[Phase]
    alerts: Dict
    interventions: Dict
    debrief_points: List[str] = field(default_factory=list)


# ============================================================================
# REAL MEDICAL CASES - Based on AHA ACLS Guidelines & Medical Simulation
# ============================================================================

CASES = {

    # =========================================================================
    # CASE 1: WITNESSED VFib ARREST (55yo Male, Gym)
    # =========================================================================
    # Source: ACLS Hero / AHA Megacode - Witnessed VFib
    "vfib_witnessed": Case(
        case_id="vfib_witnessed",
        name="Witnessed VFib Arrest - 55yo Male at Gym",
        description="55-year-old male collapses at the gym. Bystander CPR in progress. AED shows VFib. Standard ACLS scenario.",
        scenario_type="ACLS",
        learning_objectives=[
            "Recognize VFib on monitor immediately",
            "Perform early defibrillation (< 2 min)",
            "Deliver stacked shocks: 200J → 200J → 200J biphasic",
            "Resume CPR immediately after each shock",
            "Administer Epinephrine 1mg after 2nd shock",
            "Consider Amiodarone 300mg after 3rd shock"
        ],
        patient={
            "name": "Michael Torres",
            "age": 55,
            "sex": "M",
            "weight_kg": 85,
            "diagnosis": "Sudden Cardiac Arrest - VFib",
            "history": "Hypertension, Hyperlipidemia",
            "allergies": ["Penicillin"],
            "code_status": "Full Code",
            "location": "Gym - Locker Room",
            "witness": "Bystander CPR started immediately"
        },
        baseline_vitals=Vitals(hr=0, bp_sys=0, bp_dia=0, spo2=0, rr=0, temp=37.0, rhythm="vf"),
        phases=[
            Phase(
                time_seconds=0,
                action="critical",
                rhythm_change="vf",
                message="📍 START: Patient found collapsed. AED attached - VFib confirmed.",
                events=["vfib_confirmed"],
                vitals_delta={}
            ),
            Phase(
                time_seconds=30,
                action="critical",
                rhythm_change="vf",
                message="⚡ First shock delivered - 200J biphasic",
                events=["shock_1"],
                correct_intervention="defibrillate_200j"
            ),
            Phase(
                time_seconds=90,
                action="critical",
                rhythm_change="vf",
                message="💓 CPR in progress. VF persists.",
                events=["cpr_started"]
            ),
            Phase(
                time_seconds=150,
                action="critical",
                rhythm_change="vf",
                message="⚡ Second shock delivered - 200J biphasic",
                events=["shock_2"],
                correct_intervention="defibrillate_200j"
            ),
            Phase(
                time_seconds=180,
                action="critical",
                rhythm_change="vt",
                message="💉 Epinephrine 1mg IV administered",
                events=["epi_given"],
                correct_intervention="epinephrine"
            ),
            Phase(
                time_seconds=240,
                action="critical",
                rhythm_change="vt",
                message="💓 CPR continues. Rhythm showing pVT.",
                events=["pvt_onset"]
            ),
            Phase(
                time_seconds=270,
                action="critical",
                rhythm_change="vt",
                message="⚡ Third shock delivered - 200J biphasic",
                events=["shock_3"],
                correct_intervention="defibrillate_200j"
            ),
            Phase(
                time_seconds=300,
                action="critical",
                rhythm_change="sinus",
                message="💊 Amiodarone 300mg IV administered",
                events=["amiodarone_given"],
                correct_intervention="amiodarone"
            ),
            Phase(
                time_seconds=360,
                action="critical",
                rhythm_change="sinus",
                message="💓 CPR continues. PEA now showing...",
                events=["pea_onset"]
            ),
            Phase(
                time_seconds=420,
                action="critical",
                rhythm_change="sinus",
                message="✅ ROSC ACHIEVED! Pulse present.",
                events=["rosc"],
                vitals_delta={"hr": 110, "bp_sys": 85, "bp_dia": 60, "spo2": 88}
            )
        ],
        alerts={
            "vfib_confirmed": {
                "severity": AlertSeverity.CODE_BLUE,
                "message": "VFib confirmed - NO PULSE - DEFIBRILLATE IMMEDIATELY",
                "action_required": "Clear bed, deliver shock within 10 seconds"
            },
            "shock_1": {"severity": AlertSeverity.CRITICAL, "message": "First shock delivered", "action_required": "Resume CPR 2 min"},
            "shock_2": {"severity": AlertSeverity.CRITICAL, "message": "Second shock delivered", "action_required": "Give Epinephrine 1mg"},
            "shock_3": {"severity": AlertSeverity.CRITICAL, "message": "Third shock delivered", "action_required": "Give Amiodarone 300mg"},
            "rosc": {"severity": AlertSeverity.INFO, "message": "ROSC achieved!", "action_required": "Post-cardiac arrest care"}
        },
        interventions={
            "vfib_confirmed": {"correct": "defibrillate_200j", "score": 20, "time_limit": 30},
            "shock_1": {"correct": "cpr", "score": 5},
            "shock_2": {"correct": "epinephrine", "score": 10},
            "shock_3": {"correct": "amiodarone", "score": 10},
            "pea_onset": {"correct": "continue_cpr", "score": 5},
            "rosc": {"correct": "rosc_care", "score": 15}
        },
        debrief_points=[
            "Early defibrillation is critical for VFib survival",
            "Minimize interruptions to chest compressions",
            "Epinephrine improves coronary perfusion pressure",
            "Amiodarone for refractory VF/pVT",
            "High-quality CPR: 100-120/min, 2-inch depth"
        ]
    ),

    # =========================================================================
    # CASE 2: PEA DUE TO HYPOVOLEMIA (Post-Op Hemorrhage)
    # =========================================================================
    # Source: ACLS scenarios - PEA ec Hypovolemia
    "pea_hypovolemia": Case(
        case_id="pea_hypovolemia",
        name="PEA Arrest - Post-Op Hemorrhage",
        description="68-year-old male, 4 hours post-abdominal surgery. Found unresponsive. Massive intra-abdominal bleeding suspected. PEA on monitor.",
        scenario_type="ACLS",
        learning_objectives=[
            "Recognize PEA (electrical activity with no pulse)",
            "Identify H's and T's - focus on hypovolemia",
            "Start high-quality CPR immediately",
            "Administer Epinephrine 1mg IV/IO",
            "Massive transfusion protocol activation",
            "Identify need for emergent surgical intervention"
        ],
        patient={
            "name": "James Richardson",
            "age": 68,
            "sex": "M",
            "weight_kg": 90,
            "diagnosis": "Post-Op Cardiac Arrest - PEA",
            "history": "Colon cancer, HTN, DM Type 2",
            "allergies": [],
            "code_status": "Full Code",
            "location": "SICU - 4 hours post-op",
            "surgery": "Right hemicolectomy",
            "blood_loss": "Suspected >2L intra-abdominal"
        },
        baseline_vitals=Vitals(hr=0, bp_sys=0, bp_dia=0, spo2=0, rr=0, temp=36.2, rhythm="pea"),
        phases=[
            Phase(
                time_seconds=0,
                action="critical",
                rhythm_change="pea",
                message="📍 START: Patient found unresponsive. PEA on monitor - NO PULSE.",
                events=["pea_confirmed"],
                vitals_delta={}
            ),
            Phase(
                time_seconds=30,
                action="critical",
                rhythm_change="pea",
                message="💓 CPR started. Team assigned roles.",
                events=["cpr_started"]
            ),
            Phase(
                time_seconds=60,
                action="critical",
                rhythm_change="pea",
                message="💉 IV access obtained. Epinephrine 1mg prepared.",
                events=["iv_access"]
            ),
            Phase(
                time_seconds=90,
                action="critical",
                rhythm_change="pea",
                message="💉 Epinephrine 1mg IV administered.",
                events=["epi_given"],
                correct_intervention="epinephrine"
            ),
            Phase(
                time_seconds=120,
                action="critical",
                rhythm_change="pea",
                message="🩸 Blood products ordered - MTP activated.",
                events=["mtp_activated"],
                correct_intervention="mtp_activation"
            ),
            Phase(
                time_seconds=180,
                action="critical",
                rhythm_change="pea",
                message="💓 Rhythm check - PEA persists. Continue CPR.",
                events=["rhythm_check_1"]
            ),
            Phase(
                time_seconds=210,
                action="critical",
                rhythm_change="pea",
                message="💉 Second Epinephrine 1mg IV.",
                events=["epi_given_2"],
                correct_intervention="epinephrine"
            ),
            Phase(
                time_seconds=270,
                action="critical",
                rhythm_change="asystole",
                message="📉 Rhythm deteriorating to asystole...",
                events=["asystole_onset"]
            ),
            Phase(
                time_seconds=330,
                action="critical",
                rhythm_change="asystole",
                message="💀 Asystole confirmed. Prolonged downtime suspected.",
                events=["asystole_confirmed"]
            )
        ],
        alerts={
            "pea_confirmed": {
                "severity": AlertSeverity.CODE_BLUE,
                "message": "PEA - NO PULSE - START CPR IMMEDIATELY",
                "action_required": "H's and T's: Think HYPOVOLEMIA"
            },
            "mtp_activated": {
                "severity": AlertSeverity.CRITICAL,
                "message": "Massive Transfusion Protocol activated",
                "action_required": "Prepare for emergent re-operation"
            },
            "asystole_onset": {
                "severity": AlertSeverity.CODE_BLUE,
                "message": "Rhythm deteriorating to Asystole",
                "action_required": "Consider termination if prolonged downtime"
            }
        },
        interventions={
            "pea_confirmed": {"correct": "cpr", "score": 10, "time_limit": 30},
            "iv_access": {"correct": "iv_access", "score": 5},
            "epi_given": {"correct": "epinephrine", "score": 10, "time_limit": 60},
            "mtp_activated": {"correct": "mtp_activation", "score": 15, "time_limit": 120},
            "rhythm_check_1": {"correct": "continue_cpr", "score": 5}
        },
        debrief_points=[
            "PEA requires identifying and treating reversible causes",
            "H's: Hypovolemia, Hypoxia, Hydrogen ion (acidosis), Hypo/Hyperkalemia",
            "T's: Tension pneumothorax, Tamponade (cardiac), Toxins, Thrombosis (PE), Thrombosis (ACS)",
            "Massive transfusion: 1:1:1 ratio pRBC:FFP:Platelets",
            "Early surgical consultation for ongoing hemorrhage"
        ]
    ),

    # =========================================================================
    # CASE 3: STEMI → VT → ROSC (54yo Police Officer)
    # =========================================================================
    # Source: EMSimCases - Police Officer with Chest Pain
    "stemi_vt": Case(
        case_id="stemi_vt",
        name="VT Arrest - Post-STEMI (Police Officer)",
        description="54-year-old male police officer, chest pain for 2 hours after hockey game. VT arrest on monitor placement. Requires multiple shocks. Post-ROSC STEMI.",
        scenario_type="ACLS",
        learning_objectives=[
            "Recognize wide-complex tachycardia (VT)",
            "Deliver synchronized cardioversion for pulseless VT",
            "Multiple defibrillation attempts",
            "Post-ROSC care including 12-lead ECG",
            "STEMI pre-activation for PCI",
            "Manage intermittent rearrest"
        ],
        patient={
            "name": "David Kowalski",
            "age": 54,
            "sex": "M",
            "weight_kg": 95,
            "occupation": "Police Officer",
            "diagnosis": "Acute STEMI - Ventricular Arrhythmia",
            "history": "No prior cardiac history, occasional chest pain",
            "allergies": [],
            "code_status": "Full Code",
            "location": "ED Resuscitation Bay",
            "event": "Collapsed while being placed on monitor"
        },
        baseline_vitals=Vitals(hr=170, bp_sys=90, bp_dia=60, spo2=94, rr=24, temp=37.0, rhythm="vt"),
        phases=[
            Phase(
                time_seconds=0,
                action="critical",
                rhythm_change="vt",
                message="📍 START: Patient VT on monitor. NO PULSE.",
                events=["vt_confirmed"],
                vitals_delta={"hr": 170, "bp_sys": 90}
            ),
            Phase(
                time_seconds=30,
                action="critical",
                rhythm_change="vt",
                message="⚡ Synchronized cardioversion - 150J biphasic",
                events=["cardioversion_1"],
                correct_intervention="synchronized_cardioversion"
            ),
            Phase(
                time_seconds=60,
                action="critical",
                rhythm_change="vt",
                message="💓 VT persists. CPR started.",
                events=["cpr_started"]
            ),
            Phase(
                time_seconds=90,
                action="critical",
                rhythm_change="vt",
                message="⚡ Second shock - 200J",
                events=["shock_2"],
                correct_intervention="defibrillate_200j"
            ),
            Phase(
                time_seconds=150,
                action="critical",
                rhythm_change="sinus",
                message="✅ ROSC achieved! Pulse present.",
                events=["rosc"],
                vitals_delta={"hr": 118, "bp_sys": 95, "bp_dia": 65, "spo2": 92}
            ),
            Phase(
                time_seconds=180,
                action="deteriorate",
                rhythm_change="vt",
                message="⚠️ REARREST! VT returned - NO PULSE",
                events=["rearrest"],
                vitals_delta={"hr": 165}
            ),
            Phase(
                time_seconds=210,
                action="critical",
                rhythm_change="vt",
                message="⚡ Third shock - 200J",
                events=["shock_3"],
                correct_intervention="defibrillate_200j"
            ),
            Phase(
                time_seconds=270,
                action="critical",
                rhythm_change="sinus",
                message="✅ ROSC again! Maintaining...",
                events=["rosc_2"],
                vitals_delta={"hr": 108, "bp_sys": 88}
            ),
            Phase(
                time_seconds=330,
                action="stable",
                rhythm_change="sinus",
                message="📋 12-lead ECG: STEMI - LAD occlusion",
                events=["stemi_diagnosed"],
                vitals_delta={"hr": 105, "bp_sys": 92, "spo2": 95}
            ),
            Phase(
                time_seconds=360,
                action="stable",
                rhythm_change="sinus",
                message="🏥 STEMI team activated. Cath lab prep.",
                events=["stemi_activation"]
            )
        ],
        alerts={
            "vt_confirmed": {
                "severity": AlertSeverity.CODE_BLUE,
                "message": "Pulseless VT - SYNCHRONIZED SHOCK IMMEDIATELY",
                "action_required": "Clear bed, deliver synchronized shock"
            },
            "rearrest": {
                "severity": AlertSeverity.CRITICAL,
                "message": "Patient rearrested - VT returned",
                "action_required": "Resume ACLS protocols"
            },
            "stemi_diagnosed": {
                "severity": AlertSeverity.WARNING,
                "message": "STEMI on ECG - LAD occlusion suspected",
                "action_required": "Activate STEMI team, prep for PCI"
            }
        },
        interventions={
            "vt_confirmed": {"correct": "synchronized_cardioversion", "score": 20, "time_limit": 30},
            "cardioversion_1": {"correct": "cpr", "score": 5},
            "shock_2": {"correct": "defibrillate_200j", "score": 15},
            "rosc": {"correct": "rosc_care", "score": 10},
            "shock_3": {"correct": "defibrillate_200j", "score": 15},
            "stemi_activation": {"correct": "stemi_protocol", "score": 10}
        },
        debrief_points=[
            "VT with pulse = synchronized cardioversion; VT without pulse = defibrillation",
            "Post-cardiac arrest patients often rearrest - be prepared",
            "STEMI with ventricular arrhythmia = high priority for PCI",
            "Goal: Door-to-balloon time < 90 minutes",
            "Post-ROSC care: Optimize oxygenation, hemodynamics, prevent rearrest"
        ]
    ),

    # =========================================================================
    # CASE 4: PULMONARY EMBOLISM → PEA (46yo Post-Op Ortho)
    # =========================================================================
    # Source: EMSimCases - PE with DVT
    "pe_pea": Case(
        case_id="pe_pea",
        name="Massive PE → PEA (Post-Orthopedic Surgery)",
        description="46-year-old male, 3 days post-left knee replacement. Sudden onset dyspnea and chest pain. Found pulseless. Suspected massive pulmonary embolism with PEA.",
        scenario_type="ACLS",
        learning_objectives=[
            "Recognize massive PE as cause of sudden cardiovascular collapse",
            "Identify PEA pattern on monitor",
            "Consider thrombolysis for massive PE with cardiac arrest",
            "H's and T's: Think THROMBOSIS (PE)",
            "Potential for ROSC with thrombolytic therapy"
        ],
        patient={
            "name": "Robert Chen",
            "age": 46,
            "sex": "M",
            "weight_kg": 100,
            "diagnosis": "Massive Pulmonary Embolism - PEA Arrest",
            "history": "Obesity, smoker, post-orthopedic surgery",
            "allergies": [],
            "code_status": "Full Code",
            "location": "Orthopedic Floor - Day 3 post-op",
            "risk_factors": "Recent surgery, immobility, DVT prophylaxis held"
        },
        baseline_vitals=Vitals(hr=115, bp_sys=85, bp_dia=55, spo2=82, rr=28, temp=37.2, rhythm="sinus_tachycardia"),
        phases=[
            Phase(
                time_seconds=0,
                action="deteriorate",
                rhythm_change="sinus_tachycardia",
                message="📍 START: Patient complaining of sudden dyspnea. Tachycardic, hypotensive.",
                events=["pe_suspected"],
                vitals_delta={"hr": 115, "bp_sys": 85, "spo2": 82}
            ),
            Phase(
                time_seconds=60,
                action="deteriorate",
                rhythm_change="sinus_tachycardia",
                message="⚠️ BP dropping further. Preparing for intubation.",
                events=["hemodynamic_deterioration"],
                vitals_delta={"bp_sys": -20, "spo2": -10}
            ),
            Phase(
                time_seconds=120,
                action="critical",
                rhythm_change="pea",
                message="💀 PULSELESS. PEA on monitor.",
                events=["pea_onset"],
                vitals_delta={"hr": 0, "bp_sys": 0, "spo2": 0}
            ),
            Phase(
                time_seconds=150,
                action="critical",
                rhythm_change="pea",
                message="💓 CPR started. Consider PE as cause.",
                events=["cpr_started"]
            ),
            Phase(
                time_seconds=180,
                action="critical",
                rhythm_change="pea",
                message="💉 Epinephrine 1mg IV.",
                events=["epi_given"],
                correct_intervention="epinephrine"
            ),
            Phase(
                time_seconds=240,
                action="critical",
                rhythm_change="pea",
                message="🩺 POCUS: RV dilation, D-sign positive. THROMBOLYSIS?",
                events=["tpa_consideration"],
                correct_intervention="thrombolysis"
            ),
            Phase(
                time_seconds=300,
                action="critical",
                rhythm_change="pea",
                message="💉 Alteplase 50mg IV started (weight-based).",
                events=["tpa_given"],
                correct_intervention="thrombolysis"
            ),
            Phase(
                time_seconds=360,
                action="critical",
                rhythm_change="sinus",
                message="💓 Rhythm improving...",
                events=["rhythm_improving"]
            ),
            Phase(
                time_seconds=420,
                action="critical",
                rhythm_change="sinus",
                message="✅ ROSC achieved! BP palpable.",
                events=["rosc"],
                vitals_delta={"hr": 95, "bp_sys": 78, "spo2": 78}
            )
        ],
        alerts={
            "pe_suspected": {
                "severity": AlertSeverity.WARNING,
                "message": "Suspected massive PE - hemodynamic instability",
                "action_required": "Prepare for arrest, consider thrombolysis"
            },
            "pea_onset": {
                "severity": AlertSeverity.CODE_BLUE,
                "message": "PEA - NO PULSE - Think THROMBOSIS (PE)",
                "action_required": "CPR + Epinephrine + Thrombolysis consideration"
            },
            "tpa_consideration": {
                "severity": AlertSeverity.CRITICAL,
                "message": "POCUS positive for PE - consider thrombolysis",
                "action_required": "Alteplase 50mg IV for massive PE arrest"
            },
            "rosc": {
                "severity": AlertSeverity.INFO,
                "message": "ROSC achieved after thrombolysis",
                "action_required": "Continue hemodynamic support, monitor for bleeding"
            }
        },
        interventions={
            "pea_onset": {"correct": "cpr", "score": 10, "time_limit": 30},
            "epi_given": {"correct": "epinephrine", "score": 10},
            "tpa_consideration": {"correct": "thrombolysis", "score": 15, "time_limit": 180},
            "rosc": {"correct": "rosc_care", "score": 15}
        },
        debrief_points=[
            "Massive PE can cause PEA/ cardiac arrest",
            "POCUS: RV dilation, D-sign, McConnell's sign",
            "Thrombolysis for PE cardiac arrest is controversial but can be life-saving",
            "Risk of bleeding must be weighed against risk of death",
            "Post-ROSC: Monitor for recurrent PE, bleeding complications"
        ]
    ),

    # =========================================================================
    # CASE 5: BRADYCARDIA → VF (57yo Female)
    # =========================================================================
    # Source: AHA Megacode - Bradycardia to VF
    "brady_vf": Case(
        case_id="brady_vf",
        name="Bradycardia → VF (57yo Female with AMI)",
        description="57-year-old female presenting with indigestion, cold sweats. Bradycardia with hypotension. Progresses to VF requiring defibrillation.",
        scenario_type="ACLS",
        learning_objectives=[
            "Recognize symptomatic bradycardia",
            "Appropriate use of atropine and transcutaneous pacing",
            "Watch for deterioration to lethal arrhythmia",
            "Prepare for rapid deterioration in ACS patients",
            "Early defibrillation when VF occurs"
        ],
        patient={
            "name": "Patricia Williams",
            "age": 57,
            "sex": "F",
            "weight_kg": 70,
            "diagnosis": "Acute Coronary Syndrome - Bradyarrhythmia",
            "history": "Diabetes, Hyperlipidemia, Smoking",
            "allergies": ["Sulfa"],
            "code_status": "Full Code",
            "location": "ED - Resuscitation Bay",
            "presentation": "Indigestion, cold sweats, near-syncope"
        },
        baseline_vitals=Vitals(hr=38, bp_sys=70, bp_dia=0, spo2=93, rr=16, temp=36.8, rhythm="sinus_bradycardia"),
        phases=[
            Phase(
                time_seconds=0,
                action="deteriorate",
                rhythm_change="sinus_bradycardia",
                message="📍 START: HR 38, BP 70/palpable. Patient diaphoretic, confused.",
                events=["severe_bradycardia"],
                vitals_delta={"hr": 38, "bp_sys": 70}
            ),
            Phase(
                time_seconds=60,
                action="deteriorate",
                rhythm_change="sinus_bradycardia",
                message="💊 Atropine 0.5mg IV given. No response yet.",
                events=["atropine_1"],
                correct_intervention="atropine"
            ),
            Phase(
                time_seconds=90,
                action="deteriorate",
                rhythm_change="sinus_bradycardia",
                message="💊 Second Atropine 0.5mg IV.",
                events=["atropine_2"],
                correct_intervention="atropine"
            ),
            Phase(
                time_seconds=120,
                action="deteriorate",
                rhythm_change="sinus_bradycardia",
                message="⏱️ Transcutaneous pacing being set up...",
                events=["pacing_setup"],
                correct_intervention="transcutaneous_pacing"
            ),
            Phase(
                time_seconds=150,
                action="critical",
                rhythm_change="vf",
                message="💀 PATIENT COLLSAPSED! VF on monitor - NO PULSE",
                events=["vf_sudden"],
                vitals_delta={"hr": 0, "bp_sys": 0, "spo2": 0}
            ),
            Phase(
                time_seconds=180,
                action="critical",
                rhythm_change="vf",
                message="⚡ DEFIBRILLATE - 200J biphasic IMMEDIATELY",
                events=["first_shock"],
                correct_intervention="defibrillate_200j"
            ),
            Phase(
                time_seconds=210,
                action="critical",
                rhythm_change="vt",
                message="💓 CPR in progress. VT showing.",
                events=["cpr_after_shock"]
            ),
            Phase(
                time_seconds=240,
                action="critical",
                rhythm_change="vt",
                message="⚡ Second shock - 200J",
                events=["second_shock"],
                correct_intervention="defibrillate_200j"
            ),
            Phase(
                time_seconds=300,
                action="critical",
                rhythm_change="sinus",
                message="✅ ROSC! Hypotensive but pulse present.",
                events=["rosc"],
                vitals_delta={"hr": 105, "bp_sys": 75, "spo2": 88}
            ),
            Phase(
                time_seconds=360,
                action="stable",
                rhythm_change="sinus",
                message="🏥 STEMI protocol activated. Urgent cath lab.",
                events=["stemi_preactivation"]
            )
        ],
        alerts={
            "severe_bradycardia": {
                "severity": AlertSeverity.CRITICAL,
                "message": "Severe bradycardia with hypotension - symptomatic",
                "action_required": "Atropine, prepare pacing, IV access"
            },
            "vf_sudden": {
                "severity": AlertSeverity.CODE_BLUE,
                "message": "VF - NO PULSE - DEFIBRILLATE IMMEDIATELY",
                "action_required": "Clear bed, shock within 10 seconds"
            },
            "rosc": {
                "severity": AlertSeverity.INFO,
                "message": "ROSC achieved",
                "action_required": "Post-arrest care, urgent cath lab"
            }
        },
        interventions={
            "severe_bradycardia": {"correct": "atropine", "score": 5, "time_limit": 120},
            "atropine_1": {"correct": "atropine", "score": 5},
            "atropine_2": {"correct": "transcutaneous_pacing", "score": 5},
            "vf_sudden": {"correct": "defibrillate_200j", "score": 20, "time_limit": 30},
            "first_shock": {"correct": "cpr", "score": 5},
            "second_shock": {"correct": "defibrillate_200j", "score": 15},
            "rosc": {"correct": "rosc_care", "score": 10}
        },
        debrief_points=[
            "Bradycardia in ACS can progress rapidly to complete heart block or VF",
            "Atropine first-line for symptomatic bradycardia (0.5mg, max 3mg)",
            "Transcutaneous pacing if atropine fails",
            "Always be prepared for sudden deterioration in ACS patients",
            "Early defibrillation remains the most important intervention for VF"
        ]
    ),

    # =========================================================================
    # CASE 6: SEPSIS → SEPTIC SHOCK (72yo Post-Op)
    # =========================================================================
    # Source: Medical simulation - Post-op sepsis
    "sepsis_shock": Case(
        case_id="sepsis_shock",
        name="Septic Shock - Post-Op Patient",
        description="72-year-old male, day 2 post-bowel resection. Developing fever, tachycardia, hypotension. Progressing to refractory septic shock.",
        scenario_type="Emergency",
        learning_objectives=[
            "Recognize early signs of sepsis",
            "Apply SSC bundles: cultures, antibiotics, fluids, lactate",
            "Identify septic shock refractory to fluids",
            "Initiate vasopressors (Norepinephrine)",
            "Source control considerations"
        ],
        patient={
            "name": "William Thompson",
            "age": 72,
            "sex": "M",
            "weight_kg": 80,
            "diagnosis": "Septic Shock - Post-operative",
            "history": "COPD, HTN, Colorectal cancer",
            "allergies": ["Morphine"],
            "code_status": "Full Code",
            "location": "SICU - Day 2 post-op",
            "surgery": "Elective colectomy for cancer"
        },
        baseline_vitals=Vitals(hr=88, bp_sys=110, bp_dia=70, spo2=96, rr=18, temp=37.8, rhythm="sinus_tachycardia"),
        phases=[
            Phase(
                time_seconds=0,
                action="stable",
                rhythm_change="sinus_tachycardia",
                message="📍 START: Mild fever (37.8°C), HR 88. Patient comfortable.",
                events=["sepsis_early"],
                vitals_delta={"temp": 37.8}
            ),
            Phase(
                time_seconds=90,
                action="deteriorate",
                rhythm_change="sinus_tachycardia",
                message="🌡️ Fever rising to 38.9°C. HR 105. New lethargy.",
                events=["sepsis_worsening"],
                vitals_delta={"temp": 1.1, "hr": 17, "bp_sys": -15, "spo2": -3}
            ),
            Phase(
                time_seconds=180,
                action="deteriorate",
                rhythm_change="sinus_tachycardia",
                message="🩸 Lactate 4.2 mmol/L (elevated). BP dropping.",
                events=["lactate_elevated", "hypotension_onset"],
                vitals_delta={"bp_sys": -25, "bp_dia": -15, "rr": 5}
            ),
            Phase(
                time_seconds=240,
                action="deteriorate",
                rhythm_change="sinus_tachycardia",
                message="💉 Fluids started - 30mL/kg bolus in progress",
                events=["fluids_started"],
                correct_intervention="fluid_resuscitation"
            ),
            Phase(
                time_seconds=300,
                action="deteriorate",
                rhythm_change="sinus_tachycardia",
                message="💊 Broad-spectrum antibiotics given. Source evaluation.",
                events=["antibiotics_given"],
                correct_intervention="antibiotics"
            ),
            Phase(
                time_seconds=360,
                action="critical",
                rhythm_change="sinus_tachycardia",
                message="🔴 BP 78/45 despite 2L fluids. Vasopressors needed!",
                events=["shock_refractory"],
                vitals_delta={"bp_sys": -40, "bp_dia": -25},
                correct_intervention="norepinephrine"
            ),
            Phase(
                time_seconds=420,
                action="critical",
                rhythm_change="sinus_tachycardia",
                message="💉 Norepinephrine started at 0.1 mcg/kg/min",
                events=["norepi_started"],
                correct_intervention="norepinephrine"
            ),
            Phase(
                time_seconds=480,
                action="deteriorate",
                rhythm_change="sinus_tachycardia",
                message="💓 BP improving to 88/55 on NE. Consider adding vasopressin.",
                events=["bp_improving"],
                vitals_delta={"bp_sys": 10, "bp_dia": 10}
            ),
            Phase(
                time_seconds=540,
                action="stable",
                rhythm_change="sinus_tachycardia",
                message="✅ BP stabilized at 95/60. Source: Anastomotic leak suspected. Surgical consult.",
                events=["stabilized"],
                vitals_delta={"hr": -15, "bp_sys": 15}
            )
        ],
        alerts={
            "sepsis_early": {
                "severity": AlertSeverity.INFO,
                "message": "qSOFA positive: RR 22, AMS. Evaluate for sepsis.",
                "action_required": "Labs, lactate, cultures"
            },
            "lactate_elevated": {
                "severity": AlertSeverity.WARNING,
                "message": "Lactate 4.2 mmol/L - tissue hypoperfusion",
                "action_required": "Aggressive fluid resuscitation"
            },
            "shock_refractory": {
                "severity": AlertSeverity.CRITICAL,
                "message": "Septic shock refractory to fluids - vasopressors needed",
                "action_required": "Start Norepinephrine immediately"
            },
            "stabilized": {
                "severity": AlertSeverity.INFO,
                "message": "Hemodynamically improving on vasopressors",
                "action_required": "Source control, ICU monitoring"
            }
        },
        interventions={
            "sepsis_early": {"correct": "sepsis_evaluation", "score": 5},
            "lactate_elevated": {"correct": "fluid_resuscitation", "score": 10, "time_limit": 180},
            "fluids_started": {"correct": "fluid_resuscitation", "score": 5},
            "antibiotics_given": {"correct": "antibiotics", "score": 10, "time_limit": 180},
            "shock_refractory": {"correct": "norepinephrine", "score": 15, "time_limit": 60},
            "norepi_started": {"correct": "norepinephrine", "score": 5},
            "stabilized": {"correct": "icu_care", "score": 5}
        },
        debrief_points=[
            "Hour-1 Bundle: Lactate, cultures, broad-spectrum antibiotics, 30mL/kg fluids",
            "Septic shock = fluids + vasopressors + source control",
            "Norepinephrine is first-line vasopressor",
            "Target MAP > 65 mmHg",
            "Source control is essential - surgery may be needed"
        ]
    ),

    # =========================================================================
    # CASE 7: TENSION PNEUMOTHORAX → PEA (Trauma)
    # =========================================================================
    # Source: ACLS - Trauma PEA
    "tension_pneumothorax": Case(
        case_id="tension_pneumothorax",
        name="Tension Pneumothorax → PEA (Trauma)",
        description="28-year-old male, GSW to chest. Progressive respiratory distress → PEA arrest. Tension pneumothorax suspected.",
        scenario_type="ACLS",
        learning_objectives=[
            "Recognize tension pneumothorax signs",
            "Emergency needle decompression",
            "PEA due to obstructive cause",
            "CPR + immediate decompression",
            "Preparation for chest tube insertion"
        ],
        patient={
            "name": "Jason Martinez",
            "age": 28,
            "sex": "M",
            "weight_kg": 85,
            "diagnosis": "GSW Chest - Tension Pneumothorax",
            "history": "Otherwise healthy",
            "allergies": [],
            "code_status": "Full Code",
            "location": "ED Trauma Bay",
            "injury": "GSW to left chest - entrance/exit wound"
        },
        baseline_vitals=Vitals(hr=130, bp_sys=85, bp_dia=50, spo2=78, rr=32, temp=36.5, rhythm="sinus_tachycardia"),
        phases=[
            Phase(
                time_seconds=0,
                action="deteriorate",
                rhythm_change="sinus_tachycardia",
                message="📍 START: GSW chest. Respiratory distress, hypotension. Lungs sounds absent left.",
                events=["tension_ptx_signs"],
                vitals_delta={"hr": 130, "bp_sys": 85, "spo2": 78}
            ),
            Phase(
                time_seconds=60,
                action="deteriorate",
                rhythm_change="sinus_tachycardia",
                message="⚠️ JVD present, tracheal deviation right. Tension pneumothorax!",
                events=["tension_ptx_confirmed"],
                correct_intervention="needle_decompression"
            ),
            Phase(
                time_seconds=90,
                action="critical",
                rhythm_change="pea",
                message="💀 PATIENT ARRESTED! PEA on monitor. NO PULSE.",
                events=["pea_onset"],
                vitals_delta={"hr": 0, "bp_sys": 0, "spo2": 0}
            ),
            Phase(
                time_seconds=120,
                action="critical",
                rhythm_change="pea",
                message="💓 CPR started. Prepare for immediate decompression!",
                events=["cpr_started"]
            ),
            Phase(
                time_seconds=150,
                action="critical",
                rhythm_change="pea",
                message="💉 NDL decompression - Left chest, 2nd ICS midclavicular!",
                events=["needle_decompression"],
                correct_intervention="needle_decompression"
            ),
            Phase(
                time_seconds=180,
                action="critical",
                rhythm_change="sinus",
                message="🫁 WHOOSH! Air escaping. Patient improving...",
                events=["decompression_success"],
                vitals_delta={"hr": 85, "bp_sys": 70, "spo2": 85}
            ),
            Phase(
                time_seconds=240,
                action="deteriorate",
                rhythm_change="sinus",
                message="✅ ROSC achieved. Prep for chest tube.",
                events=["rosc"],
                vitals_delta={"hr": 95, "bp_sys": 85, "spo2": 92}
            ),
            Phase(
                time_seconds=300,
                action="stable",
                rhythm_change="sinus",
                message="🏥 Chest tube placed. Patient stabilizing.",
                events=["chest_tube_placed"]
            )
        ],
        alerts={
            "tension_ptx_signs": {
                "severity": AlertSeverity.WARNING,
                "message": "Tension pneumothorax signs: absent lung sounds, JVD, tracheal deviation",
                "action_required": "Emergency needle decompression BEFORE arrest"
            },
            "pea_onset": {
                "severity": AlertSeverity.CODE_BLUE,
                "message": "PEA - NO PULSE - TENSION PNEUMOTHORAX is cause!",
                "action_required": "IMMEDIATE needle decompression"
            },
            "decompression_success": {
                "severity": AlertSeverity.INFO,
                "message": "Tension pneumothorax relieved",
                "action_required": "Prepare chest tube, continue resuscitation"
            }
        },
        interventions={
            "tension_ptx_confirmed": {"correct": "needle_decompression", "score": 15, "time_limit": 60},
            "pea_onset": {"correct": "cpr", "score": 5, "time_limit": 30},
            "needle_decompression": {"correct": "needle_decompression", "score": 20, "time_limit": 120},
            "rosc": {"correct": "rosc_care", "score": 10},
            "chest_tube_placed": {"correct": "chest_tube", "score": 10}
        },
        debrief_points=[
            "Tension pneumothorax is a clinical diagnosis - don't wait for imaging",
            "Bilateral breath sounds, JVD, tracheal deviation, hypotension",
            "Emergency needle decompression: 14-16 gauge, 2nd ICS MCL or 4th-5th ICS AAL",
            "PEA from tension pneumothorax = immediate decompression",
            "Follow with definitive chest tube insertion"
        ]
    )
}


class DeteriorationEngine:
    """Manages case progression and vitals over time"""

    def __init__(self):
        self.active_rooms: Dict[str, Dict] = {}
        self.callbacks: List[Callable] = []

    def start_case(self, room_id: str, case_id: str) -> Dict:
        """Initialize a room with a case"""
        if case_id not in CASES:
            raise ValueError(f"Unknown case: {case_id}")

        case = CASES[case_id]
        vitals = Vitals(
            hr=case.baseline_vitals.hr,
            bp_sys=case.baseline_vitals.bp_sys,
            bp_dia=case.baseline_vitals.bp_dia,
            spo2=case.baseline_vitals.spo2,
            rr=case.baseline_vitals.rr,
            temp=case.baseline_vitals.temp,
            etco2=case.baseline_vitals.etco2,
            rhythm=case.baseline_vitals.rhythm
        )

        self.active_rooms[room_id] = {
            "case_id": case_id,
            "case": case,
            "vitals": vitals,
            "start_time": time.time(),
            "current_phase": 0,
            "status": "stable",
            "alerts": [],
            "actions": [],
            "patient": case.patient.copy(),
            "occupied": False,
            "occupied_by": None
        }

        return self.active_rooms[room_id]

    def tick(self, room_id: str) -> Optional[Dict]:
        """Process one tick for a room - call every second"""
        if room_id not in self.active_rooms:
            return None

        room = self.active_rooms[room_id]
        elapsed = time.time() - room["start_time"]
        room["elapsed"] = int(elapsed)

        # Check phase transitions
        phases = room["case"].phases
        new_phase_idx = 0
        for i, phase in enumerate(phases):
            if elapsed >= phase.time_seconds:
                new_phase_idx = i

        # Process phase change
        if new_phase_idx != room["current_phase"]:
            room["current_phase"] = new_phase_idx
            phase = phases[new_phase_idx]

            # Apply vitals changes
            for key, delta in phase.vitals_delta.items():
                if hasattr(room["vitals"], key):
                    current = getattr(room["vitals"], key)
                    if isinstance(current, float):
                        setattr(room["vitals"], key, round(current + delta, 1))
                    else:
                        setattr(room["vitals"], key, current + delta)

            # Apply rhythm change
            if phase.rhythm_change:
                room["vitals"].rhythm = phase.rhythm_change

            # Trigger events
            for event in phase.events:
                alert = room["case"].alerts.get(event)
                if alert:
                    room["alerts"].append({
                        "time": int(elapsed),
                        "event": event,
                        **alert
                    })

                    # Notify callbacks
                    for cb in self.callbacks:
                        cb(room_id, event, alert)

            room["status"] = phase.action

        # Small random variations for realism
        room["vitals"].hr += random.randint(-1, 1)
        room["vitals"].bp_sys += random.randint(-1, 1)
        room["vitals"].bp_dia += random.randint(-1, 1)

        return self.get_room_state(room_id)

    def intervene(self, room_id: str, action: str, time_limit: int = None) -> Dict:
        """Record user intervention and score it"""
        if room_id not in self.active_rooms:
            return {"error": "Room not found"}

        room = self.active_rooms[room_id]
        elapsed = time.time() - room["start_time"]

        # Check if action was correct for current situation
        score = 0
        feedback = ""
        is_correct = False

        current_phase = room["case"].phases[room["current_phase"]]
        if current_phase.correct_intervention:
            if action == current_phase.correct_intervention:
                score = room["case"].interventions.get(current_phase.events[0], {}).get("score", 5)
                feedback = "✓ Correct intervention!"
                is_correct = True
            else:
                score = -5
                feedback = "✗ Not the optimal intervention"

        room["actions"].append({
            "time": int(elapsed),
            "action": action,
            "score": score,
            "feedback": feedback,
            "correct": is_correct
        })

        return {"action": action, "score": score, "feedback": feedback, "correct": is_correct}

    def get_room_state(self, room_id: str) -> Dict:
        """Get current state of a room"""
        if room_id not in self.active_rooms:
            return {"error": "Room not found"}

        room = self.active_rooms[room_id]
        current_phase = room["case"].phases[room["current_phase"]]

        return {
            "room_id": room_id,
            "case_id": room["case_id"],
            "patient": room["patient"],
            "vitals": room["vitals"].to_dict(),
            "vitals_colors": {
                "hr": room["vitals"].get_color("hr"),
                "bp": room["vitals"].get_color("bp"),
                "spo2": room["vitals"].get_color("spo2"),
                "rr": room["vitals"].get_color("rr"),
                "temp": room["vitals"].get_color("temp")
            },
            "rhythm": room["vitals"].rhythm,
            "status": room["status"],
            "elapsed": int(time.time() - room["start_time"]),
            "current_message": current_phase.message,
            "alerts": room["alerts"][-5:],
            "actions": room["actions"],
            "occupied": room["occupied"],
            "occupied_by": room["occupied_by"],
            "case_name": room["case"].name,
            "learning_objectives": room["case"].learning_objectives,
            "debrief_points": room["case"].debrief_points
        }

    def get_all_rooms(self) -> Dict[str, Dict]:
        """Get state of all active rooms"""
        return {rid: self.get_room_state(rid) for rid in self.active_rooms}

    def stop_case(self, room_id: str) -> Dict:
        """End a case and return final state"""
        if room_id not in self.active_rooms:
            return {"error": "Room not found"}

        room = self.active_rooms[room_id]
        total_score = sum(a["score"] for a in room["actions"])
        correct_actions = sum(1 for a in room["actions"] if a.get("correct"))

        result = {
            "case_id": room["case_id"],
            "case_name": room["case"].name,
            "patient": room["patient"],
            "duration": int(time.time() - room["start_time"]),
            "actions": room["actions"],
            "alerts": room["alerts"],
            "final_score": total_score,
            "interventions_made": len(room["actions"]),
            "correct_interventions": correct_actions,
            "critical_misses": sum(1 for a in room["actions"] if a["score"] < 0),
            "debrief_points": room["case"].debrief_points,
            "learning_objectives": room["case"].learning_objectives
        }

        del self.active_rooms[room_id]
        return result


# Singleton instance
engine = DeteriorationEngine()
