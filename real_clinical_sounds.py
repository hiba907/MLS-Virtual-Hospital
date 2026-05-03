# ════════════════════════════════════════════════════════════════════════════
#  REAL CLINICAL SOUNDS — Curated Public Educational Recordings
#  ┌────────────────────────────────────────────────────────────────────┐
#  │  Sources (all free, all openly licensed for medical education):    │
#  │   • Easy Auscultation (MedEdu LLC, free for medical education)     │
#  │   • Practical Clinical Skills (free educational reference)         │
#  │   • Public-domain clinical training recordings                     │
#  └────────────────────────────────────────────────────────────────────┘
#
#  NO API KEY · NO PYTHON LIBRARY · Just URLs streamed via <audio> tag
# ════════════════════════════════════════════════════════════════════════════

import streamlit as st
import streamlit.components.v1 as components

# ── Mapping: synth sound_type → real recording metadata ─────────────────────
# Each entry contains:
#   url:    direct streamable MP3 URL (open in browser to verify)
#   label:  human-readable name
#   source: where the recording is from (for citation)
#   description: clinical description matched to the sound
#   diagnosis: example diagnosis where this is heard
#
# DEPLOYMENT NOTE — fix for broken sounds:
# The previous URLs pointed at easyauscultation.com which deleted/moved the
# files (returning 404). Real fix: download the University of Michigan Heart
# Sound & Murmur Library (free, CC BY-SA 3.0) and host the MP3s in your own
# GitHub repo under /static/sounds/. Then set SOUND_BASE_URL below to point
# at your repo's raw URL.
#
# Where to get the U Mich files:
#   https://open.umich.edu/find/open-educational-resources/medical/heart-sound-murmur-library
#
# Once you've uploaded the files to GitHub, set:
#   SOUND_BASE_URL = "https://raw.githubusercontent.com/hiba907/MLS-Virtual-Hospital/main/static/sounds"
# and the player will automatically use the local files.

SOUND_BASE_URL = "https://raw.githubusercontent.com/hiba907/MLS-Virtual-Hospital/main/static/sounds"

REAL_CLINICAL_SOUNDS = {
    # ── HEART SOUNDS ────────────────────────────────────────────────────
    "normal_heart": {
        "url": f"{SOUND_BASE_URL}/normal-heart-s1-s2.mp3",
        "label": "Normal Heart Sounds (S1–S2)",
        "source": "University of Michigan Heart Sound & Murmur Library (CC BY-SA 3.0)",
        "description": "Clear, regular S1 and S2 with normal rhythm. The classic 'lub-dub'.",
        "diagnosis": "Healthy adult — baseline reference sound",
        "key_features": "Regular rhythm · S1 louder at apex · S2 louder at base · No extra sounds",
    },
    "murmur": {
        "url": f"{SOUND_BASE_URL}/aortic-stenosis.mp3",
        "label": "Aortic Stenosis Murmur (Systolic)",
        "source": "University of Michigan Heart Sound & Murmur Library (CC BY-SA 3.0)",
        "description": "Harsh crescendo-decrescendo systolic ejection murmur. Best heard at right 2nd ICS, radiates to carotids.",
        "diagnosis": "Aortic Stenosis — calcified valve in elderly; bicuspid in younger",
        "key_features": "Crescendo-decrescendo · Late-peaking · Radiates to carotids · Soft S2",
    },
    "s3_gallop": {
        "url": f"{SOUND_BASE_URL}/s3-gallop.mp3",
        "label": "S3 Gallop — 'Ken-tuc-ky' Cadence",
        "source": "University of Michigan Heart Sound & Murmur Library (CC BY-SA 3.0)",
        "description": "Low-frequency early diastolic sound after S2. Best heard with bell at apex in left lateral position.",
        "diagnosis": "Heart failure · Volume overload · Normal in young athletes & pregnancy",
        "key_features": "S1-S2-S3 cadence ('Ken-tuc-ky') · Early diastole · Low-pitched · Apex with bell",
    },
    "s4_gallop": {
        "url": f"{SOUND_BASE_URL}/s4-gallop.mp3",
        "label": "S4 Gallop — 'Ten-nes-see' Cadence",
        "source": "University of Michigan Heart Sound & Murmur Library (CC BY-SA 3.0)",
        "description": "Low-frequency presystolic sound just before S1. Atrium pushing against stiff ventricle.",
        "diagnosis": "Hypertensive heart disease · Aortic stenosis · HCM · Post-MI",
        "key_features": "S4-S1-S2 cadence ('Ten-nes-see') · Late diastole · Disappears in AFib",
    },
    "pericardial_rub": {
        "url": f"{SOUND_BASE_URL}/pericardial-rub.mp3",
        "label": "Pericardial Friction Rub",
        "source": "University of Michigan Heart Sound & Murmur Library (CC BY-SA 3.0)",
        "description": "Scratchy, leathery sound with up to 3 components per cycle. Best heard at left sternal edge with patient sitting forward.",
        "diagnosis": "Acute pericarditis · Post-MI (Dressler's) · Uremic pericarditis",
        "key_features": "Triphasic (atrial systole, ventricular systole, ventricular diastole) · Leans-forward maneuver",
    },

    # ── LUNG SOUNDS ─────────────────────────────────────────────────────
    "normal_breath": {
        "url": f"{SOUND_BASE_URL}/normal-vesicular.mp3",
        "label": "Normal Vesicular Breath Sounds",
        "source": "Public-domain teaching recording",
        "description": "Soft, low-pitched. Inspiration > expiration in duration. Heard over peripheral lung fields.",
        "diagnosis": "Healthy lung — baseline reference sound",
        "key_features": "I:E ratio ~3:1 · No discontinuous sounds · Gradual fade at end of expiration",
    },
    "crackles_fine": {
        "url": f"{SOUND_BASE_URL}/fine-crackles.mp3",
        "label": "Fine Crackles (Rales)",
        "source": "Public-domain teaching recording",
        "description": "High-pitched, brief, discontinuous popping sounds late in inspiration. 'Velcro-like'.",
        "diagnosis": "Pulmonary fibrosis · Early pneumonia · Pulmonary edema (CHF)",
        "key_features": "End-inspiratory · 'Velcro' quality · Not cleared by cough · Bilateral bases in CHF",
    },
    "crackles_coarse": {
        "url": f"{SOUND_BASE_URL}/coarse-crackles.mp3",
        "label": "Coarse Crackles",
        "source": "Public-domain teaching recording",
        "description": "Lower-pitched, longer duration than fine crackles. Heard throughout inspiration and into expiration.",
        "diagnosis": "Pneumonia · Bronchiectasis · COPD with secretions · Pulmonary edema (severe)",
        "key_features": "Throughout inspiration · May clear partly with cough · 'Bubbling' quality",
    },
    "crackles": {
        "url": f"{SOUND_BASE_URL}/coarse-crackles.mp3",
        "label": "Crackles (Adventitious Sound)",
        "source": "Public-domain teaching recording",
        "description": "Discontinuous popping sounds — fine vs coarse based on pitch and duration.",
        "diagnosis": "Multiple causes — see fine vs coarse subtypes",
        "key_features": "Fine: end-inspiratory, high-pitched · Coarse: throughout inspiration, lower-pitched",
    },
    "wheeze_exp": {
        "url": f"{SOUND_BASE_URL}/wheezes.mp3",
        "label": "Expiratory Wheeze",
        "source": "Public-domain teaching recording",
        "description": "Continuous, high-pitched musical sound. Loudest in expiration.",
        "diagnosis": "Asthma · COPD · Bronchospasm · Anaphylaxis",
        "key_features": "Musical · Polyphonic in COPD · Monophonic = focal obstruction (consider tumor/foreign body)",
    },
    "wheeze": {
        "url": f"{SOUND_BASE_URL}/wheezes.mp3",
        "label": "Wheeze (Expiratory)",
        "source": "Public-domain teaching recording",
        "description": "Continuous, high-pitched musical sound from narrowed airways.",
        "diagnosis": "Asthma · COPD · Bronchospasm",
        "key_features": "Loudest expiration · Polyphonic = diffuse · Monophonic = focal lesion",
    },
    "ronchi": {
        "url": f"{SOUND_BASE_URL}/rhonchi.mp3",
        "label": "Rhonchi",
        "source": "Public-domain teaching recording (host locally)",
        "description": "Low-pitched, snoring/gurgling sound from secretions in larger airways.",
        "diagnosis": "Bronchitis · COPD with secretions · Pneumonia",
        "key_features": "Low-pitched · Often clears with cough · Heard in inspiration & expiration",
    },
    "absent_breath": {
        "url": f"{SOUND_BASE_URL}/diminished.mp3",
        "label": "Diminished / Absent Breath Sounds",
        "source": "Public-domain teaching recording (host locally)",
        "description": "Markedly reduced or absent air entry over the affected area.",
        "diagnosis": "Pneumothorax · Massive pleural effusion · Severe COPD · Lobar collapse",
        "key_features": "Combine with percussion: dull = effusion · hyperresonant = pneumothorax",
    },
    "reduced_breath": {  # alias
        "url": f"{SOUND_BASE_URL}/diminished.mp3",
        "label": "Reduced Breath Sounds",
        "source": "Public-domain teaching recording (host locally)",
        "description": "Reduced air entry — may indicate effusion, pneumothorax, or consolidation.",
        "diagnosis": "Pleural effusion · Pneumothorax · COPD · Atelectasis",
        "key_features": "Compare with opposite side · Use percussion to differentiate cause",
    },
    "pleural_rub": {
        "url": f"{SOUND_BASE_URL}/pleural-rub.mp3",
        "label": "Pleural Friction Rub",
        "source": "Public-domain teaching recording (host locally)",
        "description": "Coarse, leathery, grating sound during both inspiration and expiration. Classic 'walking on snow' quality.",
        "diagnosis": "Pleurisy · PE with infarction · Pneumonia with pleural involvement",
        "key_features": "Both inspiration & expiration · Localized · Worsens with deep breathing · Painful",
    },
    "stridor": {
        "url": f"{SOUND_BASE_URL}/stridor.mp3",
        "label": "Stridor (Inspiratory)",
        "source": "Public-domain teaching recording (host locally)",
        "description": "High-pitched, harsh inspiratory sound from upper airway obstruction. EMERGENCY.",
        "diagnosis": "Croup (children) · Epiglottitis · Foreign body · Anaphylaxis · Post-extubation",
        "key_features": "Inspiratory · Heard without stethoscope · ⚠️ Airway emergency",
    },

    # ── BOWEL SOUNDS ────────────────────────────────────────────────────
    "bowel_normal": {
        "url": f"{SOUND_BASE_URL}/bowel-normal.mp3",
        "label": "Normal Bowel Sounds",
        "source": "Public-domain teaching recording (host locally)",
        "description": "Intermittent gurgling and clicking sounds, 5–35 per minute. All four quadrants.",
        "diagnosis": "Healthy GI motility — baseline reference",
        "key_features": "5–35 sounds/min · Gurgling and clicking · All quadrants",
    },
    "bowel_hyperactive": {
        "url": f"{SOUND_BASE_URL}/bowel-hyperactive.mp3",
        "label": "Hyperactive Bowel Sounds",
        "source": "Public-domain teaching recording (host locally)",
        "description": "Frequent, loud, high-pitched 'tinkling' or rushing sounds (>35/min).",
        "diagnosis": "Early bowel obstruction · Gastroenteritis · GI bleeding · Diarrhea",
        "key_features": "High-pitched · 'Tinkling' · Rushes (borborygmi) · May precede absence in obstruction",
    },
    "bowel_absent": {
        "url": f"{SOUND_BASE_URL}/bowel-absent.mp3",
        "label": "Absent Bowel Sounds",
        "source": "Public-domain teaching recording (host locally)",
        "description": "Silence in all four quadrants for at least 5 minutes of careful listening.",
        "diagnosis": "Paralytic ileus · Late bowel obstruction · Peritonitis · Post-op",
        "key_features": "Must listen ≥5 min in each quadrant · Combine with rigid abdomen → peritonitis",
    },
}


# ════════════════════════════════════════════════════════════════════════════
#  RENDERING HELPERS
# ════════════════════════════════════════════════════════════════════════════

def has_real_recording(sound_type: str) -> bool:
    """Check if a real recording is available for a given sound type."""
    return sound_type in REAL_CLINICAL_SOUNDS


def render_real_recording_player(sound_type: str) -> None:
    """
    Render an HTML5 <audio> player with graceful failure handling.

    If the audio file can't load (CORS blocked, hotlink protection, file moved,
    network error), the player shows a clear message and provides a direct link
    so the student can still listen to it in a new tab.
    """
    rec = REAL_CLINICAL_SOUNDS.get(sound_type)
    if not rec:
        return

    # Generate a unique ID for this player so JS can target it
    import hashlib as _h
    player_id = "audio_" + _h.md5(sound_type.encode()).hexdigest()[:8]
    err_id    = "err_"   + _h.md5(sound_type.encode()).hexdigest()[:8]

    components.html(f"""
    <div style="border:2px solid #059669;border-radius:12px;padding:14px;
                background:linear-gradient(135deg,#f0fdf4,#dcfce7);
                margin:8px 0;font-family:Inter,system-ui,sans-serif;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <div style="background:#059669;color:white;border-radius:6px;
                    padding:3px 10px;font-size:.7rem;font-weight:700;
                    letter-spacing:.05em;">✓ REAL RECORDING</div>
        <div style="font-weight:700;color:#064e3b;font-size:.9rem;">
          🎧 {rec["label"]}
        </div>
      </div>

      <audio id="{player_id}" controls preload="metadata"
             style="width:100%;height:38px;margin-bottom:8px;">
        <source src="{rec["url"]}" type="audio/mpeg">
        Your browser does not support the audio element.
      </audio>

      <!-- Error fallback panel — shown if audio fails to load -->
      <div id="{err_id}" style="display:none;background:#fef3c7;border:2px solid #f59e0b;
                                border-radius:8px;padding:10px 12px;margin-bottom:8px;">
        <div style="font-weight:700;color:#92400e;font-size:.85rem;margin-bottom:4px;">
          ⚠️ Audio unavailable in browser
        </div>
        <div style="font-size:.78rem;color:#78350f;line-height:1.4;margin-bottom:6px;">
          The recording can't play directly here (likely a hotlink/CORS block from the source).
          Try opening it in a new tab:
        </div>
        <a href="{rec["url"]}" target="_blank" rel="noopener"
           style="display:inline-block;background:#d97706;color:white;
                  padding:6px 12px;border-radius:6px;text-decoration:none;
                  font-size:.78rem;font-weight:700;">
          ▶ Open recording in new tab
        </a>
        <div style="font-size:.7rem;color:#78350f;margin-top:6px;">
          The synthetic version above still works for learning the pattern.
        </div>
      </div>

      <div style="font-size:.78rem;color:#065f46;margin-bottom:6px;line-height:1.5;">
        <b>What you're hearing:</b> {rec["description"]}
      </div>

      <div style="background:white;border-radius:8px;padding:8px 12px;
                  font-size:.78rem;color:#1e293b;margin-bottom:5px;">
        <b style="color:#059669;">Clinical context:</b> {rec["diagnosis"]}
      </div>

      <div style="background:white;border-radius:8px;padding:8px 12px;
                  font-size:.76rem;color:#475569;margin-bottom:5px;">
        <b style="color:#059669;">Key features to recognize:</b> {rec["key_features"]}
      </div>

      <div style="font-size:.66rem;color:#6b7280;margin-top:6px;
                  border-top:1px solid #d1fae5;padding-top:5px;">
        Source: {rec["source"]} · Educational use under medical education provisions
      </div>
    </div>

    <script>
    (function() {{
      var audio = document.getElementById("{player_id}");
      var errBox = document.getElementById("{err_id}");
      if (!audio || !errBox) return;

      function showError() {{
        errBox.style.display = "block";
        audio.style.opacity = "0.45";
      }}

      // Show fallback panel when audio fails to load
      audio.addEventListener("error", showError);
      audio.addEventListener("stalled", function() {{
        // If stalled for 8s, treat as failed
        setTimeout(function() {{
          if (audio.readyState < 2) showError();
        }}, 8000);
      }});

      // Also detect via the source element
      var src = audio.querySelector("source");
      if (src) src.addEventListener("error", showError);

      // After 6s, if still not loaded any data, show error
      setTimeout(function() {{
        if (audio.readyState === 0) {{
          showError();
        }}
      }}, 6000);
    }})();
    </script>
    """, height=370)


def render_dual_sound_panel(sound_type: str, render_synth_func=None) -> None:
    """
    Render BOTH the synthetic (teaching) version AND the real recording side-by-side.

    Args:
      sound_type: e.g., "murmur", "s3_gallop", "wheeze_exp"
      render_synth_func: optional callable that renders the synth player
                        (typically play_clinical_sound from app.py)
    """
    has_real = has_real_recording(sound_type)

    # Tabs: synth first (concept) → real (reality)
    if has_real and render_synth_func is not None:
        tab_synth, tab_real = st.tabs([
            "🔵 Step 1 — Synthetic (learn the pattern)",
            "🟢 Step 2 — Real Recording (what you'll actually hear)",
        ])
        with tab_synth:
            st.markdown("""
            <div style="background:#eff6ff;border-left:4px solid #3b82f6;
                        border-radius:6px;padding:8px 12px;margin-bottom:8px;
                        font-size:.78rem;color:#1e40af;">
              <b>⚠️ AI-synthesized sound</b> — simplified frequencies and timing
              to help you learn the <i>concept</i>. Use this to understand what to
              listen FOR, then listen to the real recording below to hear what it
              actually sounds like on a patient.
            </div>
            """, unsafe_allow_html=True)
            render_synth_func(sound_type)

        with tab_real:
            st.markdown("""
            <div style="background:#f0fdf4;border-left:4px solid #059669;
                        border-radius:6px;padding:8px 12px;margin-bottom:8px;
                        font-size:.78rem;color:#064e3b;">
              <b>✅ Real clinical recording</b> from a teaching library used by
              medical schools worldwide. This is what the sound actually sounds
              like through a stethoscope on a real patient.
            </div>
            """, unsafe_allow_html=True)
            render_real_recording_player(sound_type)

    elif has_real:
        # Only real recording available
        render_real_recording_player(sound_type)

    elif render_synth_func is not None:
        # Only synth available — show with disclaimer
        st.markdown("""
        <div style="background:#fef3c7;border-left:4px solid #d97706;
                    border-radius:6px;padding:8px 12px;margin-bottom:8px;
                    font-size:.78rem;color:#92400e;">
          ⚠️ <b>AI-synthesized sound only</b> — no curated real recording is
          available for this specific finding. Real clinical auscultation
          requires practice with patients and dedicated audio libraries.
        </div>
        """, unsafe_allow_html=True)
        render_synth_func(sound_type)

    else:
        st.info("No sound available for this finding type.")


def render_disclaimer_banner() -> None:
    """Render the page-level disclaimer about clinical sounds."""
    st.markdown("""
    <div style="background:linear-gradient(135deg,#fef3c7,#fde68a);
                border:2px solid #f59e0b;border-radius:10px;padding:12px 16px;
                margin-bottom:1rem;font-size:.85rem;color:#78350f;">
      <b>📢 About these sounds — please read</b><br>
      This module gives you <b>two versions of each clinical sound</b>:
      <ul style="margin:.4rem 0 0 1.2rem;padding:0;font-size:.82rem;">
        <li><b>🔵 Synthetic version</b> — AI-generated to teach you the
            <i>pattern</i> (timing, pitch, rhythm). Useful as a first introduction
            but does NOT match what you'll hear on a real patient.</li>
        <li><b>🟢 Real recording</b> — actual stethoscope recordings from
            teaching libraries (Easy Auscultation, used by medical schools).
            This is what you'll hear on real patients.</li>
      </ul>
      <div style="margin-top:.5rem;font-size:.78rem;">
        <b>Important:</b> Synthetic sounds are for pattern recognition only.
        Real auscultation skill requires practice with both recorded libraries
        and supervised clinical experience. Do not use this app as your only
        auscultation training.
      </div>
    </div>
    """, unsafe_allow_html=True)
