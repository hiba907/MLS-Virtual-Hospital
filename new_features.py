# ════════════════════════════════════════════════════════════════════════════
#  NEW FEATURES — MLS Virtual Hospital
#  ┌─────────────────────────────────────────────────────┐
#  │  1. page_osce_exam()        — OSCE Exam Simulator   │
#  │  2. page_progress_notes()   — Progress Notes AI     │
#  │  3. page_flashcard_builder()— Flashcard Deck Builder│
#  └─────────────────────────────────────────────────────┘
#
#  HOW TO WIRE INTO app.py (3 easy steps):
#  ─────────────────────────────────────────────────────────────────────────
#  STEP 1 — Add this import near the top of app.py (after existing imports):
#
#      from new_features import page_osce_exam, page_progress_notes, page_flashcard_builder
#
#  STEP 2 — Add sidebar nav buttons inside the sidebar section of app.py:
#
#      if st.button("🩺 OSCE Exam",         use_container_width=True): st.session_state.page="osce";       st.rerun()
#      if st.button("📋 Progress Notes",     use_container_width=True): st.session_state.page="notes";      st.rerun()
#      if st.button("🃏 Flashcard Builder",  use_container_width=True): st.session_state.page="flashcards"; st.rerun()
#
#  STEP 3 — Add these elif branches to the routing block at the bottom:
#
#      elif p == "osce":       page_osce_exam()
#      elif p == "notes":      page_progress_notes()
#      elif p == "flashcards": page_flashcard_builder()
#
# ════════════════════════════════════════════════════════════════════════════

import streamlit as st
import requests
import json
import time
import random
from datetime import datetime

# ── Gemini helper (standalone, no circular import needed) ─────────────────────
def _nf_call_ai(system: str, user_prompt: str, max_tokens: int = 1200) -> str:
    """Calls Gemini API using the same key pool as the main app."""
    try:
        keys: list = []
        try:
            for i in range(1, 21):
                k = st.secrets.get(f"GEMINI_KEY_{i}", "").strip()
                if not k:
                    k = st.secrets.get(f"GEMINI_API_KEY_{i}", "").strip()
                if k:
                    keys.append(k)
            if not keys:
                for fb in ("GEMINI_API_KEY", "GEMINI_KEY"):
                    k = st.secrets.get(fb, "").strip()
                    if k:
                        keys.append(k)
                        break
        except Exception:
            pass
        manual = st.session_state.get("_gemini_key_manual", "").strip()
        if manual and manual not in keys:
            keys.append(manual)
        if not keys:
            return "!ERR No API keys configured."

        models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
        history = [
            {"role": "user",  "parts": [{"text": "INSTRUCTIONS: " + system + " Say: Ready."}]},
            {"role": "model", "parts": [{"text": "Ready."}]},
            {"role": "user",  "parts": [{"text": user_prompt}]},
        ]
        payload = {"contents": history,
                   "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7}}

        for model in models:
            for key in keys:
                try:
                    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                           f"{model}:generateContent?key={key}")
                    r = requests.post(url, headers={"Content-Type": "application/json"},
                                      json=payload, timeout=45)
                    if r.status_code == 200:
                        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    elif r.status_code == 429:
                        continue
                    else:
                        break
                except Exception:
                    continue
        return "!ERR All models/keys exhausted."
    except Exception as e:
        return f"!ERR {e}"


# ════════════════════════════════════════════════════════════════════════════
#  OSCE STATION DATA
# ════════════════════════════════════════════════════════════════════════════
OSCE_STATIONS = {
    "Chest Pain History": {
        "emoji": "💗",
        "duration": 8,
        "specialty": "Cardiology",
        "difficulty": "Medium",
        "color": "#dc2626",
        "brief": (
            "You are a 3rd-year medical student. The examiner will observe silently.\n\n"
            "**Patient:** Mr. Ahmad, 58-year-old accountant, presents with chest pain for 2 hours.\n\n"
            "**Your task:** Take a focused history. You have 8 minutes."
        ),
        "rubric": {
            "History of presenting complaint (SOCRATES)": 20,
            "Cardiovascular risk factors": 15,
            "Relevant past medical / surgical history": 10,
            "Drug history & allergies": 10,
            "Family & social history": 10,
            "Systematic review": 10,
            "Communication & rapport": 15,
            "Summary & differential diagnosis": 10,
        },
        "patient_persona": (
            "You are Mr. Ahmad, a 58-year-old accountant. You have crushing central chest pain radiating to your left arm "
            "that started 2 hours ago at rest. It is 8/10 severity. You also have mild sweating and nausea. "
            "You have hypertension (on amlodipine), Type 2 DM (on metformin), smoke 10 cigs/day x 30 years, "
            "drink 2 units/night. Father died of MI at 60. You are anxious and worried it's your heart. "
            "Answer student questions naturally and only reveal information when asked."
        ),
    },
    "Respiratory Examination": {
        "emoji": "🫁",
        "duration": 7,
        "specialty": "Respiratory",
        "difficulty": "Medium",
        "color": "#0e7490",
        "brief": (
            "**Patient:** Mrs. Lee, 45F, referred by GP for progressive breathlessness × 3 months.\n\n"
            "**Your task:** Perform a full respiratory examination. Verbalise findings as you go. 7 minutes."
        ),
        "rubric": {
            "General inspection & hands": 10,
            "Face & neck (JVP, trachea, lymph nodes)": 10,
            "Chest inspection": 15,
            "Palpation (expansion, tactile fremitus)": 15,
            "Percussion (correct technique & findings)": 15,
            "Auscultation (correct technique & findings)": 20,
            "Professional presentation & communication": 15,
        },
        "patient_persona": (
            "You are a medical examiner's assistant. The student is performing a clinical examination on a simulated patient. "
            "When they describe each examination step, confirm whether technique is correct, and provide realistic findings: "
            "reduced expansion on the right, stony dull percussion right base, reduced breath sounds right base. "
            "Give encouraging but accurate feedback for each step they describe."
        ),
    },
    "Acute Abdomen Clerking": {
        "emoji": "🩺",
        "duration": 10,
        "specialty": "Surgery",
        "difficulty": "Hard",
        "color": "#7c3aed",
        "brief": (
            "**Patient:** Miss Fatima, 22F, A&E with 12-hour RLQ pain, nausea, low-grade fever.\n\n"
            "**Your task:** Take a surgical history AND perform an abdominal examination. 10 minutes."
        ),
        "rubric": {
            "Presenting complaint & pain characterisation": 15,
            "Gynaecological history (LMP, cycles, pregnancy)": 10,
            "Systemic symptoms & relevant history": 10,
            "Abdominal inspection": 10,
            "Auscultation before palpation": 5,
            "Light & deep palpation technique": 15,
            "Special tests (Rovsing, psoas, obturator)": 15,
            "Differential diagnosis & management plan": 20,
        },
        "patient_persona": (
            "You are Miss Fatima, 22F medical student, woken by RLQ pain 12h ago. Pain is 7/10, sharp, worse with movement. "
            "Nausea, no vomiting. LMP 6 weeks ago (normally regular 28-day cycles). Sexually active, uses condoms. "
            "No discharge/bleeding PV. T 37.8°C on triage. You are scared. Answer questions truthfully but only what's asked. "
            "If the student asks to examine you, describe the findings: RLQ tenderness, guarding, positive Rovsing's sign."
        ),
    },
    "Communication: Breaking Bad News": {
        "emoji": "🤝",
        "duration": 8,
        "specialty": "Communication",
        "difficulty": "Hard",
        "color": "#d97706",
        "brief": (
            "**Scenario:** You are the FY2 doctor on the oncology ward. "
            "Mr. Hassan, 67M, had a CT scan yesterday following weight loss & haemoptysis. "
            "Results show a 4cm right upper lobe mass — highly suspicious for lung malignancy (radiologist report in notes). "
            "He is now asking you directly: *'Doctor, what did the scan show?'*\n\n"
            "**Your task:** Handle this conversation using the SPIKES framework. 8 minutes."
        ),
        "rubric": {
            "S – Setting (privacy, tissues, position)": 10,
            "P – Perception (what patient already knows)": 15,
            "I – Invitation (ask permission to share)": 10,
            "K – Knowledge (clear, jargon-free delivery)": 20,
            "E – Emotions (empathy, silence, validation)": 20,
            "S – Strategy & Summary (next steps, support)": 15,
            "Overall communication & professionalism": 10,
        },
        "patient_persona": (
            "You are Mr. Hassan, 67-year-old retired teacher. You smoked for 40 years, quit 5 years ago. "
            "You are scared but trying to stay calm. You suspect something serious. "
            "When the student tells you about the mass, react with shock, then ask 'Is it cancer?' 'How long do I have?'. "
            "Become emotional but controllable. Ask about your family (wife of 40 years, 3 children). "
            "Respond realistically to how the student handles you — be more distressed if they use jargon or seem rushed."
        ),
    },
    "Drug Prescription Review": {
        "emoji": "💊",
        "duration": 6,
        "specialty": "Pharmacology",
        "difficulty": "Easy",
        "color": "#059669",
        "brief": (
            "**Task:** Review the prescription chart for Mrs. Patel, 72F, admitted with UTI.\n\n"
            "**She has:** CKD Stage 3 (eGFR 32), Type 2 DM, Heart Failure (EF 35%).\n\n"
            "**Current medications:** Metformin 1g BD, Trimethoprim 200mg BD (started today), "
            "Furosemide 40mg OD, Ramipril 5mg OD, Aspirin 75mg OD.\n\n"
            "**Your task:** Identify ALL prescribing issues and suggest corrections. 6 minutes."
        ),
        "rubric": {
            "Identifies Metformin contraindicated in CKD eGFR <30": 20,
            "Identifies Trimethoprim — hyperkalaemia risk with Ramipril": 20,
            "Identifies Trimethoprim — dose reduction needed in CKD": 15,
            "Recommends appropriate antibiotic alternative (nitrofurantoin)": 15,
            "Notes nitrofurantoin also avoided in CKD < eGFR 45": 10,
            "Suggests monitoring plan (renal function, K+)": 10,
            "Communication of findings professionally": 10,
        },
        "patient_persona": (
            "You are the OSCE examiner. The student is reviewing a prescription chart. "
            "When they identify each issue, confirm if correct and prompt them with 'Anything else?' "
            "Award marks based on the rubric. Be encouraging but don't give answers away. "
            "If they miss something after 5 minutes, hint: 'Consider the renal function and each drug's interactions.'"
        ),
    },
}


# ════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — OSCE EXAM SIMULATOR
# ════════════════════════════════════════════════════════════════════════════
def page_osce_exam():
    st.markdown("""
    <div class="main-header">
      <h1>🩺 OSCE Exam Simulator</h1>
      <p>Timed clinical stations · AI examiner · Structured marking rubrics</p>
    </div>""", unsafe_allow_html=True)

    # ── Session state init ────────────────────────────────────────────────────
    for k, v in [
        ("osce_station", None), ("osce_started", False), ("osce_start_time", None),
        ("osce_chat", []), ("osce_done", False), ("osce_feedback", None),
        ("osce_score", None),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Station selection screen ──────────────────────────────────────────────
    if not st.session_state.osce_started:
        st.markdown('<div class="section-header">📋 Choose Your OSCE Station</div>',
                    unsafe_allow_html=True)

        cols = st.columns(3)
        for i, (name, info) in enumerate(OSCE_STATIONS.items()):
            with cols[i % 3]:
                diff_color = {"Easy": "#059669", "Medium": "#d97706", "Hard": "#dc2626"}
                st.markdown(f"""
                <div class="patient-card" style="border-top-color:{info['color']};">
                  <div style="font-size:1.8rem;text-align:center;margin-bottom:.4rem;">{info['emoji']}</div>
                  <div style="font-weight:700;font-size:.9rem;color:#0a2540;text-align:center;">{name}</div>
                  <div style="text-align:center;margin:.5rem 0;">
                    <span class="badge" style="background:{info['color']}22;color:{info['color']};">
                      {info['specialty']}
                    </span>
                    <span class="badge" style="background:{diff_color.get(info['difficulty'],'#64748b')}22;
                                                color:{diff_color.get(info['difficulty'],'#64748b')};">
                      {info['difficulty']}
                    </span>
                  </div>
                  <div style="font-size:.76rem;color:#64748b;text-align:center;">⏱ {info['duration']} minutes</div>
                </div>""", unsafe_allow_html=True)
                if st.button(f"Start Station →", key=f"osce_start_{i}",
                             use_container_width=True):
                    st.session_state.osce_station    = name
                    st.session_state.osce_started    = True
                    st.session_state.osce_start_time = time.time()
                    st.session_state.osce_chat       = []
                    st.session_state.osce_done       = False
                    st.session_state.osce_feedback   = None
                    st.session_state.osce_score      = None
                    st.rerun()
        return

    # ── Active station ────────────────────────────────────────────────────────
    station_name = st.session_state.osce_station
    station      = OSCE_STATIONS[station_name]
    elapsed      = time.time() - st.session_state.osce_start_time
    remaining    = max(0, station["duration"] * 60 - elapsed)
    mins, secs   = int(remaining // 60), int(remaining % 60)
    pct          = remaining / (station["duration"] * 60)

    # Auto-end when time runs out
    if remaining == 0 and not st.session_state.osce_done:
        st.session_state.osce_done = True

    # ── Header with live timer ────────────────────────────────────────────────
    timer_color = "#059669" if pct > .5 else "#d97706" if pct > .25 else "#dc2626"
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0a2540,#1a4f8a);border-radius:12px;
                padding:1.2rem 1.6rem;color:white;margin-bottom:1rem;
                display:flex;justify-content:space-between;align-items:center;">
      <div>
        <div style="font-size:1.1rem;font-weight:800;">{station['emoji']} {station_name}</div>
        <div style="font-size:.78rem;opacity:.7;">{station['specialty']} · {station['difficulty']}</div>
      </div>
      <div style="text-align:center;">
        <div style="font-size:2rem;font-weight:900;color:{timer_color};font-variant-numeric:tabular-nums;">
          {mins:02d}:{secs:02d}
        </div>
        <div style="font-size:.68rem;opacity:.6;">REMAINING</div>
      </div>
    </div>""", unsafe_allow_html=True)

    col_l, col_r = st.columns([3, 2])

    # ── Left: Chat / Interaction ──────────────────────────────────────────────
    with col_l:
        st.markdown('<div class="section-header">💬 Clinical Station</div>',
                    unsafe_allow_html=True)

        # Station brief in a nice card
        st.markdown(f"""
        <div class="alert-info" style="font-size:.84rem;margin-bottom:1rem;">
          {station['brief'].replace(chr(10),'<br>')}
        </div>""", unsafe_allow_html=True)

        # Chat history
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.osce_chat:
                if msg["role"] == "user":
                    st.markdown(f'<div class="chat-student">🧑‍⚕️ <b>You:</b> {msg["content"]}</div>',
                                unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="chat-patient">👤 <b>Patient/Examiner:</b> {msg["content"]}</div>',
                                unsafe_allow_html=True)

        if not st.session_state.osce_done:
            user_input = st.text_area("Your response / question / examination finding:",
                                      height=90, key="osce_input", placeholder="Type what you say or do...")
            c1, c2 = st.columns([3, 1])
            with c1:
                send = st.button("📤 Send", type="primary", use_container_width=True, key="osce_send")
            with c2:
                end  = st.button("🏁 End Station", use_container_width=True, key="osce_end")

            if send and user_input.strip():
                st.session_state.osce_chat.append({"role": "user", "content": user_input.strip()})
                history_text = "\n".join(
                    f"{'STUDENT' if m['role']=='user' else 'PATIENT/EXAMINER'}: {m['content']}"
                    for m in st.session_state.osce_chat
                )
                with st.spinner("Responding..."):
                    resp = _nf_call_ai(
                        system=station["patient_persona"],
                        user_prompt=f"Conversation so far:\n{history_text}\n\nStudent's latest: {user_input.strip()}\n\nRespond in character.",
                        max_tokens=300,
                    )
                st.session_state.osce_chat.append({"role": "assistant", "content": resp})
                st.rerun()

            if end:
                st.session_state.osce_done = True
                st.rerun()
        else:
            st.markdown('<div class="alert-warn">⏱ Station ended. Generating your examiner feedback...</div>',
                        unsafe_allow_html=True)
            if not st.session_state.osce_feedback:
                transcript = "\n".join(
                    f"{'STUDENT' if m['role']=='user' else 'PATIENT'}: {m['content']}"
                    for m in st.session_state.osce_chat
                )
                rubric_text = "\n".join(
                    f"  • {criterion} [{marks} marks]"
                    for criterion, marks in station["rubric"].items()
                )
                with st.spinner("Examiner is marking your performance..."):
                    fb = _nf_call_ai(
                        system=(
                            "You are a senior clinical OSCE examiner. "
                            "Score the student transcript against the rubric. "
                            "For each criterion give: marks awarded / total, and one line of specific feedback. "
                            "End with: TOTAL: X/100, GRADE: Pass/Borderline/Fail, and 3 bullet points of key learning."
                        ),
                        user_prompt=(
                            f"OSCE Station: {station_name}\n\n"
                            f"RUBRIC:\n{rubric_text}\n\n"
                            f"STUDENT TRANSCRIPT:\n{transcript or '(No interaction recorded)'}\n\n"
                            "Please mark this student."
                        ),
                        max_tokens=900,
                    )
                st.session_state.osce_feedback = fb
                st.rerun()

            if st.session_state.osce_feedback:
                fb = st.session_state.osce_feedback
                # Try to extract total score for display
                score_text = ""
                for line in fb.split("\n"):
                    if "TOTAL:" in line.upper():
                        score_text = line.strip()
                        break

                st.markdown(f"""
                <div class="patient-card" style="border-top-color:#059669;">
                  <div style="font-weight:800;font-size:.95rem;margin-bottom:.6rem;">📊 Examiner Feedback</div>
                  {score_text and f'<div class="alert-good" style="font-size:1rem;font-weight:700;">{score_text}</div>' or ""}
                  <pre style="white-space:pre-wrap;font-family:inherit;font-size:.82rem;color:#0f172a;margin-top:.6rem;">{fb}</pre>
                </div>""", unsafe_allow_html=True)

            if st.button("🔄 Try Another Station", type="primary", use_container_width=True):
                for k in ["osce_station","osce_started","osce_start_time",
                          "osce_chat","osce_done","osce_feedback","osce_score"]:
                    st.session_state[k] = None if "time" in k or "station" in k or "feedback" in k or "score" in k else False if k in ("osce_started","osce_done") else []
                st.rerun()

    # ── Right: Rubric ─────────────────────────────────────────────────────────
    with col_r:
        st.markdown('<div class="section-header">📊 Marking Rubric</div>', unsafe_allow_html=True)
        total_marks = sum(station["rubric"].values())
        for criterion, marks in station["rubric"].items():
            pct_bar = marks / total_marks
            st.markdown(f"""
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
                        padding:.6rem .9rem;margin:.35rem 0;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.3rem;">
                <span style="font-size:.78rem;font-weight:600;color:#0a2540;">{criterion}</span>
                <span style="font-size:.78rem;font-weight:800;color:#0e7490;">{marks} pts</span>
              </div>
              <div style="background:#e2e8f0;border-radius:999px;height:4px;">
                <div style="background:linear-gradient(90deg,#0e7490,#0ea5e9);height:4px;
                            border-radius:999px;width:{int(pct_bar*100)}%;"></div>
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div class="kpi-card" style="margin-top:1rem;">
          <div class="kpi-value">{total_marks}</div>
          <div class="kpi-label">Total marks available</div>
        </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("""
        <div class="alert-info" style="font-size:.78rem;">
          <b>💡 OSCE Tips</b><br>
          • Introduce yourself & get consent first<br>
          • Narrate what you're doing<br>
          • Use structured frameworks (SOCRATES, SPIKES)<br>
          • Summarise at the end
        </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  PROGRESS NOTES DATA
# ════════════════════════════════════════════════════════════════════════════
NOTE_FRAMEWORKS = {
    "SOAP Note": {
        "emoji": "📄",
        "sections": ["Subjective", "Objective", "Assessment", "Plan"],
        "placeholders": {
            "Subjective": "What the patient reports: symptoms, complaint, history of presenting illness...",
            "Objective": "Vital signs, examination findings, investigation results...",
            "Assessment": "Your clinical impression / diagnosis...",
            "Plan": "Management: investigations ordered, medications, referrals, follow-up...",
        },
        "guide": "SOAP is the standard clinical note format. Subjective = patient's story. Objective = what you find. Assessment = your diagnosis. Plan = what you do next.",
    },
    "SBAR Handover": {
        "emoji": "🔄",
        "sections": ["Situation", "Background", "Assessment", "Recommendation"],
        "placeholders": {
            "Situation": "Patient name, location, what is happening right now...",
            "Background": "Reason for admission, relevant history, current medications, allergies...",
            "Assessment": "Your clinical assessment of the situation and severity...",
            "Recommendation": "What you need: call to attend, specific orders, specialist referral...",
        },
        "guide": "SBAR is for clinical handover and urgent communication. Be concise and clear — the receiver needs to act quickly.",
    },
    "ICU Progress Note": {
        "emoji": "🏥",
        "sections": ["Neurological", "Respiratory", "Cardiovascular", "Renal/Fluid", "Infectious/Haematology", "Plan"],
        "placeholders": {
            "Neurological": "GCS, sedation score (RASS), pupils, pain score, delirium screen...",
            "Respiratory": "Ventilator settings / O2 requirement, SpO2, CXR findings, sputum...",
            "Cardiovascular": "HR, BP, vasopressor requirements, fluid balance, echo findings...",
            "Renal/Fluid": "Urine output, fluid balance, creatinine trend, dialysis...",
            "Infectious/Haematology": "Temp, WBC, CRP, cultures, antibiotics, Hb, coagulation...",
            "Plan": "24h goals, weaning plan, family update, senior review...",
        },
        "guide": "ICU notes are organ-system based. Be systematic. Every system reviewed every day. Document ventilator weaning readiness.",
    },
    "Discharge Summary": {
        "emoji": "🚪",
        "sections": ["Admission Diagnosis", "Investigations Summary", "Treatment Given", "Discharge Diagnosis", "Follow-up Plan"],
        "placeholders": {
            "Admission Diagnosis": "Why the patient was admitted...",
            "Investigations Summary": "Key results: bloods, imaging, procedures...",
            "Treatment Given": "Medications given, procedures performed, consultations...",
            "Discharge Diagnosis": "Final confirmed diagnosis on discharge...",
            "Follow-up Plan": "GP/specialist appointments, new medications, patient education, red flags to return...",
        },
        "guide": "Discharge summaries are sent to GPs. Be thorough but legible. Include all new medications and the follow-up plan.",
    },
}

SAMPLE_CASES_NOTES = [
    {
        "label": "STEMI Patient",
        "desc": "63M presented with 3h central crushing chest pain, diaphoresis. ECG: ST elevation V1-V4. Troponin 4.2. Had primary PCI - LAD stented. Now Day 2 post-procedure.",
    },
    {
        "label": "Septic Patient",
        "desc": "28F admitted with 2-day history of dysuria, rigors, temperature 39.2°C, HR 118, BP 88/54. Urine dip +++leucocytes, nitrites. Blood cultures taken. Started on IV Tazocin.",
    },
    {
        "label": "Post-op Day 1",
        "desc": "45M Day 1 post laparoscopic cholecystectomy. Procedure uncomplicated. Tolerating sips. Mild wound discomfort. Vitals stable. Drain output nil. Needs review for discharge.",
    },
    {
        "label": "DKA (ICU)",
        "desc": "19F, T1DM, admitted unconscious. pH 7.08, glucose 32, ketones 4+. On insulin infusion and IV fluids since 6h ago. GCS now 14. K+ 3.2 on repeat.",
    },
]


# ════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — PROGRESS NOTES GENERATOR
# ════════════════════════════════════════════════════════════════════════════
def page_progress_notes():
    st.markdown("""
    <div class="main-header">
      <h1>📋 Progress Notes Generator</h1>
      <p>Practice SOAP · SBAR · ICU · Discharge notes with AI review & feedback</p>
    </div>""", unsafe_allow_html=True)

    for k, v in [
        ("notes_framework", "SOAP Note"), ("notes_case", ""), ("notes_entries", {}),
        ("notes_feedback", None), ("notes_ai_draft", None),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

    col_left, col_right = st.columns([2, 3])

    # ── Left: Controls ────────────────────────────────────────────────────────
    with col_left:
        st.markdown('<div class="section-header">⚙️ Setup</div>', unsafe_allow_html=True)

        # Framework picker
        fw_options = list(NOTE_FRAMEWORKS.keys())
        fw_icons   = [NOTE_FRAMEWORKS[f]["emoji"] for f in fw_options]
        fw_cols    = st.columns(2)
        for i, fw in enumerate(fw_options):
            with fw_cols[i % 2]:
                active = st.session_state.notes_framework == fw
                btn_style = ("background:linear-gradient(135deg,#0e7490,#1a4f8a)!important;"
                             "color:white!important;" if active else "")
                if st.button(f"{NOTE_FRAMEWORKS[fw]['emoji']} {fw}",
                             key=f"fw_{i}", use_container_width=True):
                    st.session_state.notes_framework = fw
                    st.session_state.notes_entries   = {}
                    st.session_state.notes_feedback  = None
                    st.session_state.notes_ai_draft  = None
                    st.rerun()

        st.markdown("---")

        # Case context
        st.markdown('<div class="section-header">🧑‍⚕️ Patient Case</div>', unsafe_allow_html=True)
        st.caption("Quick load a sample case or type your own:")
        for sample in SAMPLE_CASES_NOTES:
            if st.button(f"📋 {sample['label']}", key=f"sample_{sample['label']}",
                         use_container_width=True):
                st.session_state.notes_case = sample["desc"]
                st.session_state.notes_entries = {}
                st.session_state.notes_feedback = None
                st.session_state.notes_ai_draft = None
                st.rerun()

        st.session_state.notes_case = st.text_area(
            "Case summary / brief:",
            value=st.session_state.notes_case,
            height=110,
            placeholder="Describe the patient scenario here...",
            key="notes_case_input",
        )

        # AI draft button
        st.markdown("---")
        if st.button("🤖 Generate AI Draft Note", type="primary",
                     use_container_width=True, key="gen_draft"):
            if not st.session_state.notes_case.strip():
                st.warning("Please enter a case summary first.")
            else:
                fw = st.session_state.notes_framework
                sections = NOTE_FRAMEWORKS[fw]["sections"]
                with st.spinner("Drafting clinical note..."):
                    draft_raw = _nf_call_ai(
                        system=(
                            "You are a senior registrar teaching medical students to write clinical notes. "
                            "Write an exemplary, realistic clinical note. Use medical abbreviations appropriately. "
                            "Be concise but thorough. Format each section with the section name on its own line followed by content."
                        ),
                        user_prompt=(
                            f"Framework: {fw}\nSections: {', '.join(sections)}\n\n"
                            f"Patient case:\n{st.session_state.notes_case}\n\n"
                            "Write a complete, high-quality clinical note using these sections."
                        ),
                        max_tokens=800,
                    )
                st.session_state.notes_ai_draft  = draft_raw
                st.session_state.notes_feedback  = None
                st.rerun()

        # Guide
        fw_info = NOTE_FRAMEWORKS[st.session_state.notes_framework]
        st.markdown(f"""
        <div class="alert-info" style="font-size:.78rem;margin-top:.8rem;">
          <b>📖 {st.session_state.notes_framework} Guide</b><br>
          {fw_info['guide']}
        </div>""", unsafe_allow_html=True)

    # ── Right: Note editor + AI draft ─────────────────────────────────────────
    with col_right:
        fw_info  = NOTE_FRAMEWORKS[st.session_state.notes_framework]
        sections = fw_info["sections"]

        # Show AI draft if exists
        if st.session_state.notes_ai_draft:
            st.markdown('<div class="section-header">🤖 AI Example Note</div>',
                        unsafe_allow_html=True)
            st.markdown(f"""
            <div class="patient-card" style="border-top-color:#7c3aed;">
              <pre style="white-space:pre-wrap;font-family:inherit;font-size:.82rem;color:#0f172a;margin:0;">{st.session_state.notes_ai_draft}</pre>
            </div>""", unsafe_allow_html=True)
            if st.button("✏️ Write My Own Note Now", key="clear_draft"):
                st.session_state.notes_ai_draft = None
                st.rerun()
            return

        # Note editor
        st.markdown(f'<div class="section-header">✏️ Write Your {st.session_state.notes_framework}</div>',
                    unsafe_allow_html=True)

        for section in sections:
            placeholder = fw_info["placeholders"].get(section, "")
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:.5rem;margin:.6rem 0 .2rem;">
              <div style="width:10px;height:10px;border-radius:50%;background:#0e7490;flex-shrink:0;"></div>
              <span style="font-weight:700;font-size:.85rem;color:#0a2540;">{section}</span>
            </div>""", unsafe_allow_html=True)
            st.session_state.notes_entries[section] = st.text_area(
                label=section,
                value=st.session_state.notes_entries.get(section, ""),
                height=80,
                placeholder=placeholder,
                key=f"note_sec_{section}",
                label_visibility="collapsed",
            )

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔍 Get AI Feedback", type="primary",
                         use_container_width=True, key="get_feedback"):
                filled = {k: v for k, v in st.session_state.notes_entries.items() if v.strip()}
                if not filled:
                    st.warning("Write at least one section before asking for feedback.")
                else:
                    note_text = "\n\n".join(f"**{k}:**\n{v}" for k, v in filled.items())
                    with st.spinner("AI reviewing your note..."):
                        fb = _nf_call_ai(
                            system=(
                                "You are a consultant physician reviewing a medical student's clinical note. "
                                "Give structured, educational feedback. Be specific — quote the student's words. "
                                "Comment on: clinical accuracy, completeness, clarity, use of abbreviations, safety. "
                                "Give a global grade: Excellent / Satisfactory / Needs Improvement. "
                                "End with 3 specific improvements they should make."
                            ),
                            user_prompt=(
                                f"Framework: {st.session_state.notes_framework}\n"
                                f"Case: {st.session_state.notes_case or 'Not specified'}\n\n"
                                f"Student's note:\n{note_text}"
                            ),
                            max_tokens=900,
                        )
                    st.session_state.notes_feedback = fb
                    st.rerun()
        with c2:
            if st.button("🗑 Clear Note", use_container_width=True, key="clear_note"):
                st.session_state.notes_entries  = {}
                st.session_state.notes_feedback = None
                st.rerun()

        # Feedback display
        if st.session_state.notes_feedback:
            st.markdown('<div class="section-header">💬 AI Feedback</div>', unsafe_allow_html=True)
            fb = st.session_state.notes_feedback
            grade_color = "#059669"
            if "needs improvement" in fb.lower():
                grade_color = "#dc2626"
            elif "satisfactory" in fb.lower():
                grade_color = "#d97706"

            st.markdown(f"""
            <div class="patient-card" style="border-top-color:{grade_color};">
              <pre style="white-space:pre-wrap;font-family:inherit;font-size:.83rem;color:#0f172a;margin:0;">{fb}</pre>
            </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  FLASHCARD DATA
# ════════════════════════════════════════════════════════════════════════════
FLASHCARD_TOPICS = {
    "Cardiology Essentials": {
        "emoji": "💗",
        "color": "#dc2626",
        "cards": [
            {"q": "What is the first-line treatment for STEMI?", "a": "Primary PCI (percutaneous coronary intervention) within 90 minutes of first medical contact. If PCI not available within 120 min → fibrinolysis with alteplase/tenecteplase."},
            {"q": "List the classical ECG features of hyperkalaemia in order of severity.", "a": "1. Peaked (tall) T waves → 2. Prolonged PR interval → 3. Wide QRS → 4. Sine wave pattern → 5. VF / asystole. Treat urgently with IV calcium gluconate (membrane stabilisation), insulin+dextrose, salbutamol."},
            {"q": "What is the TIMI risk score used for?", "a": "TIMI (Thrombolysis In Myocardial Infarction) risk score stratifies NSTEMI/unstable angina patients into low/intermediate/high risk to guide management intensity (conservative vs. early invasive)."},
            {"q": "What are the indications for temporary pacing?", "a": "Complete heart block, Mobitz type II, symptomatic bradycardia not responding to atropine, bifascicular block with syncope, asystole as bridge to permanent pacemaker."},
            {"q": "Name the 4 valvular lesions causing a mid-systolic ejection murmur.", "a": "1. Aortic stenosis (radiates to neck, slow-rising pulse) 2. Pulmonary stenosis (left upper sternal edge) 3. HCM (increases with Valsalva) 4. Atrial septal defect (fixed split S2)."},
        ],
    },
    "Respiratory Medicine": {
        "emoji": "🫁",
        "color": "#0e7490",
        "cards": [
            {"q": "What spirometry pattern is seen in COPD and what confirms reversibility?", "a": "Obstructive pattern: FEV1/FVC < 0.70. Post-bronchodilator FEV1/FVC still < 0.70 = fixed obstruction (confirms COPD). <12% improvement = not significantly reversible (unlike asthma)."},
            {"q": "What are the CURB-65 criteria for pneumonia severity?", "a": "C-Confusion (new), U-Urea >7mmol/L, R-RR ≥30/min, B-BP systolic <90 or diastolic ≤60, 65-Age ≥65. Score 0-1: home, 2: hospital, ≥3: consider ICU."},
            {"q": "What is the management of tension pneumothorax?", "a": "IMMEDIATE needle decompression: 2nd intercostal space, mid-clavicular line with 14-16G cannula. Then formal chest drain insertion (4th/5th ICS, mid-axillary line). Do NOT wait for CXR."},
            {"q": "Differentiate Type 1 vs Type 2 respiratory failure.", "a": "Type 1: PaO2 <8kPa, PaCO2 normal/low. Cause: V/Q mismatch (PE, pneumonia, pulmonary oedema). Type 2: PaO2 <8kPa, PaCO2 >6kPa. Cause: hypoventilation (COPD, neuromuscular disease, obesity hypoventilation)."},
            {"q": "What is Horner's syndrome and what lung pathology causes it?", "a": "Horner's: ptosis, miosis, anhidrosis — from sympathetic chain disruption. Lung cause: Pancoast tumour (superior sulcus), apical lung cancer compressing the cervical sympathetic chain."},
        ],
    },
    "Pharmacology Pearls": {
        "emoji": "💊",
        "color": "#059669",
        "cards": [
            {"q": "Which antibiotics are safe in penicillin-allergic patients and what is the cross-reactivity rate?", "a": "Cross-reactivity with cephalosporins is ~1-2% (not 10% as once thought — mainly from shared side chains, not beta-lactam ring). Carbapenems: <1% cross-reactivity. Monobactams (aztreonam): no significant cross-reactivity. Macrolides, quinolones: no cross-reactivity."},
            {"q": "What are the contraindications to metformin?", "a": "eGFR <30 (stop), eGFR 30-45 (halve dose). Iodinated contrast: hold 48h. Hepatic failure. Acute illness causing dehydration. General anaesthesia (hold perioperatively). Alcohol excess."},
            {"q": "How do ACE inhibitors cause hyperkalaemia?", "a": "ACE inhibitors block angiotensin II → reduced aldosterone production → reduced K+ excretion in collecting duct → hyperkalaemia. Effect amplified with NSAIDs, K+-sparing diuretics, renal impairment (triple whammy: ACEi + NSAID + diuretic = AKI risk)."},
            {"q": "What is the antidote for each: paracetamol, warfarin, heparin, benzodiazepine, opioid?", "a": "Paracetamol → N-acetylcysteine (NAC). Warfarin → Vitamin K + PCC (prothrombin complex concentrate). Heparin → Protamine sulphate. Benzodiazepine → Flumazenil. Opioid → Naloxone."},
            {"q": "List drugs that prolong the QT interval (mnemonic: ABCDE).", "a": "A-Antibiotics (macrolides, quinolones, azithromycin). B-Beta-blockers (not usually). C-anti-psychotics (Chlorpromazine, haloperidol). D-anti-Depressants (TCAs). E-electrolyte (hypokalaemia, hypomagnesaemia). Also amiodarone, methadone, ondansetron."},
        ],
    },
    "Emergency Medicine": {
        "emoji": "🚨",
        "color": "#7c3aed",
        "cards": [
            {"q": "What are the reversible causes of cardiac arrest? (4 H's and 4 T's)", "a": "4 H's: Hypoxia, Hypovolaemia, Hypo/hyperkalaemia (metabolic), Hypothermia. 4 T's: Tension pneumothorax, Tamponade (cardiac), Toxins, Thrombosis (PE/MI)."},
            {"q": "Define SIRS and Sepsis (Sepsis-3 criteria).", "a": "SIRS ≥2 of: Temp >38 or <36°C, HR >90, RR >20, WBC >12 or <4. Sepsis-3: life-threatening organ dysfunction (SOFA score ≥2) caused by infection. Septic shock: vasopressor needed to MAP ≥65 + lactate >2mmol/L despite fluids."},
            {"q": "What is the management of anaphylaxis?", "a": "1. Remove trigger, lie flat/raise legs. 2. Adrenaline 0.5mg IM (1:1000) anterolateral thigh — repeat at 5 min if no improvement. 3. High-flow O2. 4. IV access + 500-1000mL fluid bolus. 5. Chlorphenamine 10mg IV, hydrocortisone 200mg IV. 6. Monitor 6-12h minimum."},
            {"q": "What is the GCS and how is it calculated?", "a": "Glasgow Coma Scale: E(4) + V(5) + M(6) = max 15. Eyes: 4=spontaneous, 3=to voice, 2=to pain, 1=none. Voice: 5=oriented, 4=confused, 3=words, 2=sounds, 1=none. Motor: 6=obeys, 5=localises, 4=withdraws, 3=flexion, 2=extension, 1=none."},
            {"q": "When do you intubate? List 6 key indications.", "a": "1. Airway protection (GCS≤8, aspiration risk) 2. Respiratory failure (hypoxia/hypercapnia not responsive to NIV) 3. Impending airway obstruction (angio-oedema, burns) 4. Hemodynamic instability requiring sedation 5. Seizures not responding to benzodiazepines 6. RSI needed for procedure."},
        ],
    },
}


# ════════════════════════════════════════════════════════════════════════════
#  PAGE 3 — FLASHCARD DECK BUILDER
# ════════════════════════════════════════════════════════════════════════════
def page_flashcard_builder():
    st.markdown("""
    <div class="main-header">
      <h1>🃏 Flashcard Deck Builder</h1>
      <p>Spaced-repetition learning · AI-generated cards · Track your mastery</p>
    </div>""", unsafe_allow_html=True)

    # ── Session state ─────────────────────────────────────────────────────────
    for k, v in [
        ("fc_deck", None), ("fc_index", 0), ("fc_flipped", False),
        ("fc_mastered", set()), ("fc_review", set()),
        ("fc_custom_cards", []), ("fc_mode", "browse"),  # browse / quiz
        ("fc_quiz_q", 0), ("fc_quiz_score", 0), ("fc_quiz_done", False),
        ("fc_gen_topic", ""), ("fc_generated", []),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Left: Deck selector + AI generator ───────────────────────────────────
    col_l, col_r = st.columns([1, 2])

    with col_l:
        st.markdown('<div class="section-header">📚 Choose Deck</div>', unsafe_allow_html=True)
        for deck_name, deck_info in FLASHCARD_TOPICS.items():
            active = st.session_state.fc_deck == deck_name
            if st.button(f"{deck_info['emoji']} {deck_name}",
                         key=f"deck_{deck_name}", use_container_width=True):
                st.session_state.fc_deck     = deck_name
                st.session_state.fc_index    = 0
                st.session_state.fc_flipped  = False
                st.session_state.fc_mastered = set()
                st.session_state.fc_review   = set()
                st.session_state.fc_mode     = "browse"
                st.session_state.fc_quiz_done= False
                st.session_state.fc_generated= []
                st.rerun()

        st.markdown("---")
        st.markdown('<div class="section-header">🤖 AI Card Generator</div>',
                    unsafe_allow_html=True)
        st.session_state.fc_gen_topic = st.text_input(
            "Topic to generate cards on:",
            value=st.session_state.fc_gen_topic,
            placeholder="e.g. Liver failure, Paediatric doses...",
            key="fc_gen_input",
        )
        n_cards = st.slider("Number of cards:", 3, 10, 5, key="fc_n_cards")
        if st.button("✨ Generate Cards", type="primary",
                     use_container_width=True, key="fc_gen_btn"):
            topic = st.session_state.fc_gen_topic.strip()
            if not topic:
                st.warning("Enter a topic first.")
            else:
                with st.spinner(f"Generating {n_cards} flashcards on '{topic}'..."):
                    raw = _nf_call_ai(
                        system=(
                            "You are a medical educator creating high-yield flashcards. "
                            "Return ONLY a JSON array, no markdown, no preamble. "
                            "Each item: {\"q\": \"...\", \"a\": \"...\"}. "
                            "Questions should be clinical, concise, important. "
                            "Answers should be detailed, accurate, exam-relevant."
                        ),
                        user_prompt=f"Create {n_cards} high-yield flashcards on: {topic}",
                        max_tokens=1200,
                    )
                try:
                    clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    cards = json.loads(clean)
                    if isinstance(cards, list) and cards:
                        st.session_state.fc_generated = cards
                        st.session_state.fc_deck      = f"🤖 {topic}"
                        st.session_state.fc_index     = 0
                        st.session_state.fc_flipped   = False
                        st.session_state.fc_mastered  = set()
                        st.session_state.fc_review    = set()
                        st.session_state.fc_mode      = "browse"
                        st.session_state.fc_quiz_done = False
                        st.success(f"✅ Generated {len(cards)} cards!")
                        st.rerun()
                    else:
                        st.error("Could not parse cards. Try again.")
                except Exception:
                    st.error("JSON parse error. Try a more specific topic.")

        # Stats
        if st.session_state.fc_deck:
            deck = st.session_state.fc_deck
            if deck in FLASHCARD_TOPICS:
                total = len(FLASHCARD_TOPICS[deck]["cards"])
            else:
                total = len(st.session_state.fc_generated)
            mastered = len(st.session_state.fc_mastered)
            review   = len(st.session_state.fc_review)
            st.markdown("---")
            st.markdown(f"""
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:.5rem;margin-top:.5rem;">
              <div class="kpi-card">
                <div class="kpi-value">{total}</div>
                <div class="kpi-label">Total</div>
              </div>
              <div class="kpi-card" style="border-top-color:#059669;">
                <div class="kpi-value" style="color:#059669;">{mastered}</div>
                <div class="kpi-label">Mastered</div>
              </div>
              <div class="kpi-card" style="border-top-color:#d97706;">
                <div class="kpi-value" style="color:#d97706;">{review}</div>
                <div class="kpi-label">Review</div>
              </div>
            </div>""", unsafe_allow_html=True)

    # ── Right: Card viewer ────────────────────────────────────────────────────
    with col_r:
        if not st.session_state.fc_deck:
            st.markdown("""
            <div style="text-align:center;padding:3rem 1rem;color:#64748b;">
              <div style="font-size:3rem;margin-bottom:1rem;">🃏</div>
              <div style="font-weight:600;font-size:1rem;">Pick a deck or generate cards to begin</div>
              <div style="font-size:.84rem;margin-top:.5rem;">Use the AI generator for any medical topic</div>
            </div>""", unsafe_allow_html=True)
            return

        # Resolve cards
        deck = st.session_state.fc_deck
        if deck in FLASHCARD_TOPICS:
            cards     = FLASHCARD_TOPICS[deck]["cards"]
            card_color= FLASHCARD_TOPICS[deck]["color"]
        else:
            cards     = st.session_state.fc_generated
            card_color= "#7c3aed"

        if not cards:
            st.info("No cards in this deck.")
            return

        # Mode selector
        m1, m2 = st.columns(2)
        with m1:
            if st.button("📖 Browse Mode", use_container_width=True,
                         type="primary" if st.session_state.fc_mode=="browse" else "secondary",
                         key="mode_browse"):
                st.session_state.fc_mode = "browse"
                st.session_state.fc_index = 0
                st.session_state.fc_flipped = False
                st.rerun()
        with m2:
            if st.button("🧠 Quiz Mode", use_container_width=True,
                         type="primary" if st.session_state.fc_mode=="quiz" else "secondary",
                         key="mode_quiz"):
                st.session_state.fc_mode = "quiz"
                st.session_state.fc_quiz_q = 0
                st.session_state.fc_quiz_score = 0
                st.session_state.fc_quiz_done = False
                st.session_state.fc_flipped = False
                random.shuffle(cards)
                st.rerun()

        st.markdown("---")

        # ── BROWSE MODE ───────────────────────────────────────────────────────
        if st.session_state.fc_mode == "browse":
            idx   = st.session_state.fc_index % len(cards)
            card  = cards[idx]
            flipped = st.session_state.fc_flipped
            is_mastered = idx in st.session_state.fc_mastered
            is_review   = idx in st.session_state.fc_review

            # Progress bar
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;">
              <span style="font-size:.78rem;color:#64748b;">Card {idx+1} of {len(cards)}</span>
              <span style="font-size:.78rem;color:#64748b;">
                {'✅ Mastered' if is_mastered else '🔄 Review' if is_review else '–'}
              </span>
            </div>
            <div style="background:#e2e8f0;border-radius:999px;height:5px;margin-bottom:1rem;">
              <div style="background:{card_color};height:5px;border-radius:999px;width:{int((idx+1)/len(cards)*100)}%;"></div>
            </div>""", unsafe_allow_html=True)

            # Flashcard face
            if not flipped:
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#0a2540,#1a4f8a);
                            border-radius:16px;padding:2.5rem 2rem;
                            min-height:180px;display:flex;align-items:center;justify-content:center;
                            text-align:center;cursor:pointer;box-shadow:0 8px 24px rgba(10,37,64,.25);">
                  <div>
                    <div style="font-size:.72rem;letter-spacing:.1em;color:#67e8f9;
                                text-transform:uppercase;margin-bottom:1rem;">QUESTION</div>
                    <div style="font-size:1rem;font-weight:600;color:white;line-height:1.55;">
                      {card['q']}
                    </div>
                    <div style="font-size:.75rem;color:#94a3b8;margin-top:1.2rem;">Click to reveal answer ↓</div>
                  </div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#f0fdf4,#d1fae5);
                            border:2px solid {card_color};
                            border-radius:16px;padding:2rem 1.8rem;min-height:180px;
                            box-shadow:0 8px 24px rgba(5,150,105,.12);">
                  <div style="font-size:.72rem;letter-spacing:.1em;color:{card_color};
                              text-transform:uppercase;font-weight:700;margin-bottom:.8rem;">ANSWER</div>
                  <div style="font-size:.88rem;color:#0f172a;line-height:1.65;">{card['a']}</div>
                </div>""", unsafe_allow_html=True)

            # Action buttons
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("◀ Prev", use_container_width=True, key="fc_prev"):
                    st.session_state.fc_index  = (idx - 1) % len(cards)
                    st.session_state.fc_flipped= False
                    st.rerun()
            with b2:
                label = "👁 Hide" if flipped else "👁 Reveal"
                if st.button(label, use_container_width=True, key="fc_flip", type="primary"):
                    st.session_state.fc_flipped = not flipped
                    st.rerun()
            with b3:
                if st.button("Next ▶", use_container_width=True, key="fc_next"):
                    st.session_state.fc_index  = (idx + 1) % len(cards)
                    st.session_state.fc_flipped= False
                    st.rerun()

            # Mastery buttons
            m1, m2, m3 = st.columns(3)
            with m1:
                if st.button("✅ Mastered", use_container_width=True, key="fc_master"):
                    st.session_state.fc_mastered.add(idx)
                    st.session_state.fc_review.discard(idx)
                    st.session_state.fc_index  = (idx + 1) % len(cards)
                    st.session_state.fc_flipped= False
                    st.rerun()
            with m2:
                if st.button("🔄 Needs Review", use_container_width=True, key="fc_review_btn"):
                    st.session_state.fc_review.add(idx)
                    st.session_state.fc_mastered.discard(idx)
                    st.session_state.fc_index  = (idx + 1) % len(cards)
                    st.session_state.fc_flipped= False
                    st.rerun()
            with m3:
                if st.button("🔀 Random", use_container_width=True, key="fc_random"):
                    st.session_state.fc_index  = random.randint(0, len(cards)-1)
                    st.session_state.fc_flipped= False
                    st.rerun()

        # ── QUIZ MODE ─────────────────────────────────────────────────────────
        else:
            if st.session_state.fc_quiz_done:
                score = st.session_state.fc_quiz_score
                total = len(cards)
                pct   = int(score / total * 100)
                grade = "🏆 Excellent" if pct >= 80 else "👍 Good" if pct >= 60 else "📚 Keep Studying"
                st.markdown(f"""
                <div style="text-align:center;padding:2rem;">
                  <div style="font-size:3.5rem;margin-bottom:.5rem;">{grade.split()[0]}</div>
                  <div style="font-size:1.8rem;font-weight:900;color:#0a2540;">{score}/{total}</div>
                  <div style="font-size:1rem;color:#0e7490;margin:.3rem 0;">{pct}% — {grade.split(None,1)[1]}</div>
                  <div style="margin-top:1rem;background:#f0f9ff;border-radius:12px;padding:1rem;font-size:.85rem;color:#1e40af;">
                    Mastered: {score} cards · Needs more work: {total-score} cards
                  </div>
                </div>""", unsafe_allow_html=True)
                if st.button("🔄 Restart Quiz", type="primary",
                             use_container_width=True, key="quiz_restart"):
                    st.session_state.fc_quiz_q     = 0
                    st.session_state.fc_quiz_score = 0
                    st.session_state.fc_quiz_done  = False
                    st.session_state.fc_flipped    = False
                    random.shuffle(cards)
                    st.rerun()
                return

            q_idx = st.session_state.fc_quiz_q
            if q_idx >= len(cards):
                st.session_state.fc_quiz_done = True
                st.rerun()
                return

            card    = cards[q_idx]
            flipped = st.session_state.fc_flipped

            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.8rem;">
              <span style="font-weight:700;color:#0a2540;">Question {q_idx+1} / {len(cards)}</span>
              <span style="font-weight:700;color:#059669;">Score: {st.session_state.fc_quiz_score}</span>
            </div>
            <div style="background:#e2e8f0;border-radius:999px;height:5px;margin-bottom:1rem;">
              <div style="background:{card_color};height:5px;border-radius:999px;width:{int((q_idx)/len(cards)*100)}%;"></div>
            </div>""", unsafe_allow_html=True)

            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#0a2540,#1a4f8a);
                        border-radius:16px;padding:2rem 1.8rem;text-align:center;
                        box-shadow:0 8px 24px rgba(10,37,64,.25);margin-bottom:1rem;">
              <div style="font-size:.72rem;letter-spacing:.1em;color:#67e8f9;margin-bottom:.8rem;">QUESTION</div>
              <div style="font-size:1rem;font-weight:600;color:white;line-height:1.55;">{card['q']}</div>
            </div>""", unsafe_allow_html=True)

            if flipped:
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#f0fdf4,#d1fae5);border:2px solid {card_color};
                            border-radius:16px;padding:1.5rem 1.8rem;margin-bottom:1rem;">
                  <div style="font-size:.72rem;color:{card_color};font-weight:700;margin-bottom:.6rem;">ANSWER</div>
                  <div style="font-size:.88rem;color:#0f172a;line-height:1.65;">{card['a']}</div>
                </div>""", unsafe_allow_html=True)

                st.markdown("**Did you get it right?**")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Got it!", type="primary",
                                 use_container_width=True, key="quiz_correct"):
                        st.session_state.fc_quiz_score += 1
                        st.session_state.fc_quiz_q     += 1
                        st.session_state.fc_flipped     = False
                        st.rerun()
                with c2:
                    if st.button("❌ Missed it", use_container_width=True, key="quiz_wrong"):
                        st.session_state.fc_quiz_q  += 1
                        st.session_state.fc_flipped  = False
                        st.rerun()
            else:
                if st.button("💡 Reveal Answer", type="primary",
                             use_container_width=True, key="quiz_reveal"):
                    st.session_state.fc_flipped = True
                    st.rerun()
