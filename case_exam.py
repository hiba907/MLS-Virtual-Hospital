"""
case_exam.py  —  Dr. Hiba Avatar Oral Exam
===========================================
Standalone module. Place next to app.py in:
    hiba907/MLS-Virtual-Hospital/

How to connect to app.py:
1. Add at the TOP of app.py (with other imports):
        from case_exam import page_case_exam

2. The router at the BOTTOM of app.py already has:
        elif p=="case_exam": page_case_exam()
   — nothing to change there.

Secrets needed in Streamlit (share.streamlit.io → app settings → Secrets):
    HF_TOKEN        = "hf_..."        # Hugging Face (for video clips)
    OPENROUTER_KEY  = "sk-or-..."     # OpenRouter (for AI grading)
"""

import streamlit as st
import streamlit.components.v1 as components
import requests

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
HF_USER      = "HamdarAI"
HF_DATASET   = "dr-hiba-clips"
GITHUB_API   = "https://api.github.com/repos/hiba907/Doctor-Avatar-Exam/contents/cases"
GITHUB_RAW   = "https://raw.githubusercontent.com/hiba907/Doctor-Avatar-Exam/main/cases"

# OpenRouter free model for grading — change if you want a different model
OPENROUTER_MODEL = "meta-llama/llama-3.1-8b-instruct:free"

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_clip_url(name: str) -> str:
    """Build a Hugging Face URL for a clip, appending the HF token."""
    try:
        token = st.secrets.get("HF_TOKEN", "")
    except Exception:
        token = ""
    url = (f"https://huggingface.co/datasets/{HF_USER}/{HF_DATASET}"
           f"/resolve/main/{name}.mp4")
    return url + f"?token={token}" if token else url


CLIPS = {k: _get_clip_url(k) for k in
         ["intro", "thinking", "correct", "incorrect",
          "question", "explaining", "nodding", "neutral"]}


def _pick_clip(text: str) -> str:
    """Choose the right body-language clip based on what Dr. Hiba is saying."""
    t = text.lower()
    if any(w in t for w in ["welcome", "i am dr", "begin", "start"]):
        return "intro"
    if any(w in t for w in ["correct", "well done", "excellent", "great", "perfect"]):
        return "correct"
    if any(w in t for w in ["incorrect", "wrong", "unfortunately", "missed"]):
        return "incorrect"
    if any(w in t for w in ["question", "what is", "how would",
                              "explain", "describe", "discuss"]):
        return "question"
    if any(w in t for w in ["because", "mechanism", "therefore", "this means"]):
        return "explaining"
    if any(w in t for w in ["goodbye", "conclude", "teaching", "well done completing"]):
        return "nodding"
    return "nodding"


@st.cache_data(ttl=300)
def _load_cases() -> list:
    """Fetch all JSON case files from hiba907/Doctor-Avatar-Exam/cases/"""
    try:
        r = requests.get(GITHUB_API, timeout=10)
        if r.status_code != 200:
            return []
        files = [f for f in r.json() if f["name"].endswith(".json")]
        cases = []
        for f in files:
            raw = requests.get(f"{GITHUB_RAW}/{f['name']}", timeout=10)
            if raw.status_code == 200:
                cases.append(raw.json())
        return cases
    except Exception:
        return []


def _grade(question: str, keywords: list,
           student_answer: str, case_context: str) -> str:
    """
    Grade student answer using OpenRouter (free Llama model).
    Falls back to Gemini if OpenRouter key is missing.
    """
    # ── Try OpenRouter first ──────────────────────────────────────────────────
    or_key = ""
    try:
        or_key = st.secrets.get("OPENROUTER_KEY", "").strip()
    except Exception:
        pass

    kw_text = " | ".join(keywords) if keywords else "none specified"
    prompt = (
        f"You are Dr. Hiba Hamdar, a medical examiner conducting an oral OSCE exam.\n\n"
        f"CASE CONTEXT:\n{case_context[:600]}\n\n"
        f"QUESTION: {question}\n"
        f"IDEAL ANSWER KEYWORDS: {kw_text}\n"
        f"STUDENT ANSWER: {student_answer}\n\n"
        f"Reply in exactly 3 short sentences:\n"
        f"1. Grade: Excellent / Good / Partial / Incorrect — one reason.\n"
        f"2. Key points they missed (if any).\n"
        f"3. The model answer in simple terms."
    )

    if or_key:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {or_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://mls-virtual-hospital.streamlit.app",
                    "X-Title": "MLS Virtual Hospital"
                },
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.4
                },
                timeout=30
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass  # fall through to Gemini

    # ── Fallback: Gemini ──────────────────────────────────────────────────────
    gem_key = ""
    try:
        for i in range(1, 21):
            k = st.secrets.get(f"GEMINI_KEY_{i}", "").strip()
            if not k:
                k = st.secrets.get(f"GEMINI_API_KEY_{i}", "").strip()
            if k:
                gem_key = k
                break
        if not gem_key:
            gem_key = st.secrets.get("GEMINI_API_KEY", "").strip()
    except Exception:
        pass

    if gem_key:
        for model in ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.0-flash-lite"]:
            try:
                url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                       f"{model}:generateContent?key={gem_key}")
                r = requests.post(
                    url,
                    json={"contents": [{"role": "user",
                                        "parts": [{"text": prompt}]}],
                          "generationConfig": {"maxOutputTokens": 300,
                                               "temperature": 0.4}},
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                if r.status_code == 200:
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                continue

    return "AI grading unavailable — please check your API keys in Streamlit secrets."


# ══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ══════════════════════════════════════════════════════════════════════════════

def _show_video(clip_name: str):
    """Render Dr. Hiba's video clip in the browser."""
    url = CLIPS.get(clip_name, CLIPS["neutral"])
    components.html(f"""
    <div style="display:flex;justify-content:center;">
      <video src="{url}" width="300" height="265"
        autoplay loop muted playsinline
        style="border-radius:16px;
               box-shadow:0 8px 32px rgba(10,37,64,.35);
               background:#0a2540;object-fit:cover;">
      </video>
    </div>
    <script>
      var v = document.querySelector('video');
      if(v) v.play().catch(function(){{ v.controls = true; }});
    </script>
    """, height=280)


def _speak(text: str):
    """Speak text using the browser Web Speech API (no server needed)."""
    import json as _j
    safe = _j.dumps(str(text))
    components.html(f"""<script>
    (function(){{
      window.speechSynthesis.cancel();
      var u = new SpeechSynthesisUtterance({safe});
      u.rate = 0.88; u.pitch = 1.05; u.volume = 1.0;
      function go() {{
        var vs = window.speechSynthesis.getVoices();
        var v = vs.find(function(x) {{
          return x.lang.startsWith('en') &&
            (x.name.includes('Female') || x.name.includes('Samantha') ||
             x.name.includes('Karen')  || x.name.includes('Moira'));
        }}) || vs.find(function(x) {{ return x.lang.startsWith('en'); }}) || vs[0];
        if(v) u.voice = v;
        window.speechSynthesis.speak(u);
      }}
      if(window.speechSynthesis.getVoices().length === 0)
        window.speechSynthesis.onvoiceschanged = go;
      else go();
    }})();
    </script>""", height=0)


def _mic_input():
    """Mic button using Web Speech API — result copied to clipboard for pasting."""
    components.html("""
    <div style="font-family:Inter,sans-serif;background:white;border-radius:12px;
                border:2px solid #0e7490;padding:14px;margin:8px 0;">
      <div id="st" style="font-size:.8rem;color:#6b7280;margin-bottom:8px;">
        🎤 Press the button and speak your answer
      </div>
      <div style="display:flex;gap:8px;">
        <button onclick="go()" style="
          background:linear-gradient(135deg,#0e7490,#0a2540);
          color:white;border:none;border-radius:8px;
          padding:8px 18px;font-size:.85rem;font-weight:600;
          cursor:pointer;flex:1;">
          🎤 Speak Answer
        </button>
        <button onclick="window.speechSynthesis.cancel()" style="
          background:#f1f5f9;color:#64748b;border:1px solid #e2e8f0;
          border-radius:8px;padding:8px 12px;font-size:.8rem;cursor:pointer;">
          🔇 Stop Voice
        </button>
      </div>
      <div id="tr" style="margin-top:10px;min-height:40px;background:#f8fafc;
        border-radius:8px;padding:8px 12px;font-size:.85rem;color:#0a2540;
        border:1px solid #e2e8f0;display:none;"></div>
      <div id="hint" style="font-size:.72rem;color:#9ca3af;
        margin-top:6px;display:none;">
        ✅ Copied to clipboard — paste it in the box below
      </div>
    </div>
    <script>
    var ft = "";
    function go() {
      if(!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)){
        document.getElementById("st").innerHTML =
          "⚠️ Voice not supported here. Use Chrome or Edge, then type below.";
        return;
      }
      var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      var r = new SR();
      r.lang = "en-US"; r.continuous = false; r.interimResults = true;
      document.getElementById("st").innerHTML = "🔴 Listening... speak now";
      r.onresult = function(e) {
        var interim = "", final = "";
        for(var i = e.resultIndex; i < e.results.length; i++) {
          if(e.results[i].isFinal) final += e.results[i][0].transcript;
          else interim += e.results[i][0].transcript;
        }
        if(final) ft += final;
        var tr = document.getElementById("tr");
        tr.style.display = "block";
        tr.innerText = ft + interim;
      };
      r.onend = function() {
        document.getElementById("st").innerHTML = "✅ Done — paste your answer below";
        document.getElementById("hint").style.display = "block";
        if(ft) navigator.clipboard.writeText(ft).catch(function(){});
      };
      r.onerror = function(e) {
        document.getElementById("st").innerHTML =
          "⚠️ " + e.error + " — type your answer below instead.";
      };
      ft = ""; r.start();
    }
    </script>
    """, height=195)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

def page_case_exam():
    """Main entry point — called from app.py router."""

    # ── Page header ───────────────────────────────────────────────────────────
    st.markdown("""
    <div class="main-header">
        <h1>🎓 Oral Exam with Dr. Hiba</h1>
        <p>Pick a case · Dr. Hiba asks questions · Speak your answer · Get instant AI feedback</p>
    </div>""", unsafe_allow_html=True)

    # ── Session state ─────────────────────────────────────────────────────────
    defaults = {
        "ce_state":       "select",   # select | intro | question | feedback | done
        "ce_case":        None,
        "ce_q_idx":       0,
        "ce_feedback":    "",
        "ce_clip":        "neutral",
        "ce_student_ans": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    state = st.session_state.ce_state

    # ══════════════════════════════════════════════════════════════════════════
    # STATE: SELECT CASE
    # ══════════════════════════════════════════════════════════════════════════
    if state == "select":
        st.markdown("### 📋 Choose a Case")
        with st.spinner("Loading cases from GitHub..."):
            cases = _load_cases()

        if not cases:
            st.error("No cases found — check `hiba907/Doctor-Avatar-Exam/cases/` is public.")
            return

        for i, case in enumerate(cases):
            title    = case.get("title", "Untitled")[:75]
            spec     = case.get("specialty", "Unknown")
            diff     = case.get("difficulty", "medium").title()
            n_q      = len(case.get("examiner_questions", []))
            est      = case.get("estimated_time_minutes", "?")
            dc = {"Easy": "#16a34a", "Medium": "#d97706",
                  "Hard": "#dc2626"}.get(diff, "#0e7490")

            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"""
                <div style="background:white;border-radius:12px;padding:1rem 1.2rem;
                            border-left:4px solid {dc};margin-bottom:.5rem;
                            box-shadow:0 2px 8px rgba(0,0,0,.07);">
                  <div style="font-weight:700;color:#0a2540;font-size:.9rem;">
                    {title}…</div>
                  <div style="font-size:.78rem;color:#64748b;margin-top:.2rem;">
                    🏥 {spec} &nbsp;·&nbsp;
                    <span style="color:{dc};font-weight:600;">{diff}</span>
                    &nbsp;·&nbsp; {n_q} questions &nbsp;·&nbsp; ~{est} min
                  </div>
                </div>""", unsafe_allow_html=True)
            with c2:
                if st.button("Start →", key=f"ce_start_{i}",
                             use_container_width=True, type="primary"):
                    st.session_state.ce_case  = case
                    st.session_state.ce_q_idx = 0
                    st.session_state.ce_state = "intro"
                    st.session_state.ce_clip  = "intro"
                    st.rerun()
        return

    # ── Active case setup ─────────────────────────────────────────────────────
    case = st.session_state.ce_case
    if not case:
        st.session_state.ce_state = "select"
        st.rerun()
        return

    questions = case.get("examiner_questions", [])
    q_idx     = st.session_state.ce_q_idx
    total_q   = len(questions)
    ctx = (
        f"Title: {case.get('title', '')}\n"
        f"Specialty: {case.get('specialty', '')}\n"
        f"Complaint: {case.get('presenting_complaint', '')[:300]}\n"
        f"History: {case.get('history_of_present_illness', '')[:300]}\n"
        f"Diagnosis: {case.get('final_diagnosis', '')}"
    )

    # ── Layout: video left | content right ───────────────────────────────────
    vid_col, main_col = st.columns([1, 2])

    with vid_col:
        _show_video(st.session_state.ce_clip)
        st.markdown("""
        <div style="text-align:center;margin-top:.5rem;">
          <div style="font-weight:700;color:#0a2540;font-size:.88rem;">
            Dr. Hiba Hamdar</div>
          <div style="font-size:.7rem;color:#0e7490;">Medical Examiner</div>
        </div>""", unsafe_allow_html=True)

        # Progress bar
        if total_q > 0:
            pct = int(q_idx / total_q * 100)
            st.markdown(f"""
            <div style="margin-top:.8rem;background:white;border-radius:8px;
                        padding:.6rem .8rem;border:1px solid #e2e8f0;">
              <div style="font-size:.72rem;color:#64748b;font-weight:600;
                          margin-bottom:.3rem;">Progress: {q_idx}/{total_q}</div>
              <div style="background:#e5e7eb;border-radius:999px;height:6px;">
                <div style="background:#0e7490;height:6px;border-radius:999px;
                            width:{pct}%;"></div>
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Restart", use_container_width=True, key="ce_restart"):
            for k, v in {
                "ce_state": "select", "ce_case": None, "ce_q_idx": 0,
                "ce_feedback": "", "ce_clip": "neutral", "ce_student_ans": ""
            }.items():
                st.session_state[k] = v
            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    with main_col:

        # ── INTRO ─────────────────────────────────────────────────────────────
        if state == "intro":
            intro = (
                f"Welcome to your oral exam. I am Dr. Hiba Hamdar. "
                f"Today's case is: {case.get('title', 'this case')[:60]}. "
                f"This is a {case.get('specialty', 'clinical')} case, "
                f"difficulty {case.get('difficulty', 'medium')}. "
                f"I will ask you {total_q} questions. Let us begin."
            )
            st.markdown(f"""
            <div style="background:#f0f9ff;border-left:4px solid #0e7490;
                        border-radius:0 12px 12px 0;
                        padding:1.2rem 1.4rem;margin-bottom:1rem;">
              <div style="font-weight:700;color:#0a2540;margin-bottom:.4rem;">
                👩‍⚕️ Dr. Hiba:</div>
              <div style="font-size:.92rem;color:#1e3a5f;line-height:1.7;">
                {intro}</div>
            </div>
            <div style="background:white;border-radius:12px;padding:1rem 1.2rem;
                        border:1px solid #e2e8f0;margin-bottom:1rem;
                        font-size:.84rem;color:#334155;">
              <b>📋 Case:</b> {case.get('title','?')}<br>
              <b>🏥 Specialty:</b> {case.get('specialty','?')} &nbsp;·&nbsp;
              <b>Difficulty:</b> {case.get('difficulty','?').title()} &nbsp;·&nbsp;
              <b>Questions:</b> {total_q}
            </div>""", unsafe_allow_html=True)
            _speak(intro)
            if st.button("▶️ Start First Question", type="primary",
                         use_container_width=True, key="ce_begin"):
                st.session_state.ce_state = "question"
                st.session_state.ce_clip  = "question"
                st.rerun()

        # ── QUESTION ──────────────────────────────────────────────────────────
        elif state == "question":
            if q_idx >= total_q:
                st.session_state.ce_state = "done"
                st.rerun()
                return

            q_data   = questions[q_idx]
            q_text   = q_data.get("question", "")
            keywords = q_data.get("ideal_answer_keywords", [])

            st.markdown(f"""
            <div style="background:#f0f9ff;border-left:4px solid #0e7490;
                        border-radius:0 12px 12px 0;
                        padding:1.2rem 1.4rem;margin-bottom:1rem;">
              <div style="font-size:.7rem;color:#0e7490;font-weight:700;
                          text-transform:uppercase;letter-spacing:.05em;
                          margin-bottom:.3rem;">
                Question {q_idx+1} of {total_q}</div>
              <div style="font-weight:700;color:#0a2540;margin-bottom:.3rem;">
                👩‍⚕️ Dr. Hiba asks:</div>
              <div style="font-size:.95rem;color:#1e3a5f;
                          line-height:1.75;font-style:italic;">
                "{q_text}"</div>
            </div>""", unsafe_allow_html=True)

            _speak(f"Question {q_idx+1}. {q_text}")

            st.markdown("**🎤 Your Answer:**")
            _mic_input()
            st.caption("💡 Speak above → auto-copied → paste below → Submit")

            with st.form(f"ce_form_{q_idx}", clear_on_submit=True):
                ans = st.text_area(
                    "Answer:", height=110, label_visibility="collapsed",
                    placeholder="Paste your spoken answer here, or type directly...")
                sub = st.form_submit_button(
                    "✅ Submit Answer", type="primary", use_container_width=True)

            if sub and ans.strip():
                with st.spinner("Dr. Hiba is reviewing your answer..."):
                    fb = _grade(q_text, keywords, ans.strip(), ctx)
                st.session_state.ce_feedback    = fb
                st.session_state.ce_student_ans = ans.strip()
                fb_l = fb.lower()
                if any(w in fb_l for w in ["excellent","perfect","correct",
                                            "well done","great"]):
                    st.session_state.ce_clip = "correct"
                elif any(w in fb_l for w in ["incorrect","wrong",
                                              "unfortunately","missed"]):
                    st.session_state.ce_clip = "incorrect"
                else:
                    st.session_state.ce_clip = "explaining"
                st.session_state.ce_state = "feedback"
                st.rerun()
            elif sub:
                st.warning("Please enter your answer before submitting.")

        # ── FEEDBACK ──────────────────────────────────────────────────────────
        elif state == "feedback":
            q_data   = questions[q_idx]
            q_text   = q_data.get("question", "")
            keywords = q_data.get("ideal_answer_keywords", [])
            fb       = st.session_state.ce_feedback
            fb_l     = fb.lower()

            if any(w in fb_l for w in ["excellent","perfect","correct",
                                        "well done","great"]):
                fc = "#059669"; fb_bg = "#f0fdf4"; fi = "✅"
            elif any(w in fb_l for w in ["incorrect","wrong",
                                          "unfortunately","missed"]):
                fc = "#dc2626"; fb_bg = "#fef2f2"; fi = "❌"
            else:
                fc = "#d97706"; fb_bg = "#fffbeb"; fi = "💬"

            st.markdown(f"""
            <div style="background:#f8fafc;border-radius:10px;padding:.7rem 1rem;
                        margin-bottom:.7rem;border:1px solid #e2e8f0;
                        font-size:.82rem;color:#64748b;">
              <b>Q{q_idx+1}:</b> {q_text}</div>
            <div style="background:#f0fdf4;border-left:4px solid #16a34a;
                        border-radius:0 10px 10px 0;padding:.8rem 1rem;
                        margin-bottom:.7rem;font-size:.84rem;color:#14532d;">
              <b>Your answer:</b> {st.session_state.ce_student_ans}</div>
            <div style="background:{fb_bg};border-left:4px solid {fc};
                        border-radius:0 12px 12px 0;
                        padding:1.2rem 1.4rem;margin-bottom:1rem;">
              <div style="font-weight:700;color:#0a2540;margin-bottom:.4rem;">
                {fi} Dr. Hiba's Feedback:</div>
              <div style="font-size:.9rem;color:#1e3a5f;line-height:1.75;">
                {fb}</div>
            </div>""", unsafe_allow_html=True)

            _speak(fb)

            # Key concepts chips
            if keywords:
                kw_html = "".join(
                    f'<span style="background:#e0f2fe;color:#0369a1;'
                    f'border-radius:999px;padding:2px 10px;font-size:.72rem;'
                    f'font-weight:600;margin:2px;display:inline-block;">'
                    f'{kw}</span>' for kw in keywords)
                st.markdown(f"""
                <div style="background:white;border-radius:10px;
                            padding:.8rem 1rem;border:1px solid #e2e8f0;
                            margin-bottom:1rem;">
                  <div style="font-size:.72rem;font-weight:700;color:#64748b;
                              text-transform:uppercase;letter-spacing:.05em;
                              margin-bottom:.3rem;">Key Concepts</div>
                  {kw_html}</div>""", unsafe_allow_html=True)

            ca, cb = st.columns(2)
            with ca:
                if st.button("🔄 Retry", use_container_width=True, key="ce_retry"):
                    st.session_state.ce_state = "question"
                    st.session_state.ce_clip  = "question"
                    st.rerun()
            with cb:
                lbl = ("Next Question →" if q_idx + 1 < total_q
                       else "Finish Exam ✅")
                if st.button(lbl, type="primary",
                             use_container_width=True, key="ce_next"):
                    st.session_state.ce_q_idx += 1
                    if st.session_state.ce_q_idx >= total_q:
                        st.session_state.ce_state = "done"
                        st.session_state.ce_clip  = "nodding"
                    else:
                        st.session_state.ce_state = "question"
                        st.session_state.ce_clip  = "question"
                    st.rerun()

        # ── DONE ──────────────────────────────────────────────────────────────
        elif state == "done":
            closing = (
                f"Congratulations! You have completed the oral exam on "
                f"{case.get('title', 'this case')[:50]}. "
                f"I hope this was a valuable learning experience. Goodbye!"
            )
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#f0fdf4,#ecfeff);
                        border-radius:14px;padding:1.5rem;text-align:center;
                        border:2px solid #0e7490;margin-bottom:1rem;">
              <div style="font-size:2rem;margin-bottom:.4rem;">🎓</div>
              <div style="font-weight:800;color:#0a2540;font-size:1.1rem;">
                Exam Complete!</div>
              <div style="font-size:.82rem;color:#0e7490;margin-top:.3rem;">
                {case.get('title','')[:60]}…</div>
            </div>
            <div style="background:#f0f9ff;border-left:4px solid #0e7490;
                        border-radius:0 12px 12px 0;
                        padding:1.2rem 1.4rem;margin-bottom:1rem;">
              <div style="font-weight:700;color:#0a2540;margin-bottom:.4rem;">
                👩‍⚕️ Dr. Hiba:</div>
              <div style="font-size:.9rem;color:#1e3a5f;line-height:1.7;">
                {closing}</div>
            </div>""", unsafe_allow_html=True)

            _speak(closing)

            teaching = case.get("teaching_points", [])
            if teaching:
                st.markdown("### 📚 Key Teaching Points")
                for tp in teaching:
                    st.markdown(f"""
                    <div style="background:white;border-left:3px solid #0e7490;
                                border-radius:0 8px 8px 0;padding:.6rem 1rem;
                                margin-bottom:.35rem;font-size:.84rem;color:#334155;">
                      • {tp}</div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔄 Retake", use_container_width=True, key="ce_retake"):
                    st.session_state.ce_q_idx = 0
                    st.session_state.ce_state = "intro"
                    st.session_state.ce_clip  = "intro"
                    st.rerun()
            with c2:
                if st.button("📋 New Case", type="primary",
                             use_container_width=True, key="ce_newcase"):
                    st.session_state.ce_state = "select"
                    st.session_state.ce_case  = None
                    st.session_state.ce_q_idx = 0
                    st.rerun()
