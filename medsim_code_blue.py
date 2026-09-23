"""
medsim_code_blue.py
────────────────────────────────────────────────────────────────────────────
Code Blue / rapid-response atmosphere for the MedSim Room.

Purely additive: this is a new file, imported by medsim_room.py. It renders
a full-viewport overlay (via components.html) with:
  • a pulsing red vignette border
  • a synthesized siren (Web Audio oscillator — no audio file needed)
  • a large elapsed-time counter + a 2-minute CPR-cycle countdown
    (AHA ACLS cycles: rhythm check / epi every ~2 min)
  • "chaotic" jittering vitals numbers, laid on top of the real vitals

It does not touch the vitals engine (deterioration.py) — it only reads the
state dict medsim_room.py already produces every tick.
"""

import time
import streamlit.components.v1 as components


def render_code_blue_overlay(elapsed_seconds: int, cycle_seconds: int = 120,
                              siren_on: bool = True, height: int = 190):
    """Render the code-blue header bar: siren + flashing border + timers.
    elapsed_seconds: total time since code was called.
    cycle_seconds: length of one CPR/rhythm-check cycle (AHA default 120s).
    """
    cycle_elapsed = elapsed_seconds % cycle_seconds
    cycle_remaining = cycle_seconds - cycle_elapsed
    mins, secs = divmod(elapsed_seconds, 60)
    cmins, csecs = divmod(cycle_remaining, 60)

    siren_js = "startSiren();" if siren_on else ""

    html = f"""
    <style>
      @keyframes flashRed {{
        0%,100% {{ box-shadow: inset 0 0 0px rgba(220,38,38,0); }}
        50%     {{ box-shadow: inset 0 0 60px rgba(220,38,38,.85); }}
      }}
      @keyframes jitter {{
        0%   {{ transform: translate(0,0); }}
        25%  {{ transform: translate(1px,-1px); }}
        50%  {{ transform: translate(-1px,1px); }}
        75%  {{ transform: translate(1px,1px); }}
        100% {{ transform: translate(0,0); }}
      }}
      body {{ margin:0; font-family:'Segoe UI',sans-serif; }}
      #cb-wrap {{
        position:relative; border-radius:10px; overflow:hidden;
        background:linear-gradient(135deg,#1a0505,#2b0a0a);
        animation:flashRed 1.1s ease-in-out infinite;
        padding:14px 18px; color:#fff;
      }}
      #cb-top {{ display:flex; justify-content:space-between; align-items:center; }}
      #cb-title {{ font-size:1.15rem; font-weight:800; letter-spacing:1px; color:#ff4d4d;
                    animation:jitter .15s infinite; }}
      #cb-mute {{ background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.3);
                   color:#fff; border-radius:6px; padding:4px 10px; font-size:11px; cursor:pointer; }}
      #cb-timers {{ display:flex; gap:26px; margin-top:8px; }}
      .cb-t-label {{ font-size:.68rem; color:#ffb3b3; text-transform:uppercase; letter-spacing:1px; }}
      .cb-t-val {{ font-size:1.7rem; font-weight:800; font-variant-numeric:tabular-nums; }}
      #cb-cycle {{ color:{"#ffd400" if cycle_remaining <= 15 else "#fff"}; }}
    </style>
    <div id="cb-wrap">
      <div id="cb-top">
        <div id="cb-title">🚨 CODE BLUE IN PROGRESS 🚨</div>
        <button id="cb-mute">🔇 Mute siren</button>
      </div>
      <div id="cb-timers">
        <div>
          <div class="cb-t-label">Time since code called</div>
          <div class="cb-t-val">{mins:02d}:{secs:02d}</div>
        </div>
        <div>
          <div class="cb-t-label">Next rhythm check / epi in</div>
          <div class="cb-t-val" id="cb-cycle">{cmins:02d}:{csecs:02d}</div>
        </div>
      </div>
    </div>
    <script>
      let ctx, osc, gain, playing = false;
      function startSiren() {{
        if (playing) return;
        try {{
          ctx = new (window.AudioContext || window.webkitAudioContext)();
          osc = ctx.createOscillator(); gain = ctx.createGain();
          osc.type = 'sine'; osc.connect(gain); gain.connect(ctx.destination);
          gain.gain.value = 0.05;
          osc.start();
          playing = true;
          let t = 0;
          setInterval(() => {{
            if (!playing) return;
            t += 0.05;
            const freq = 600 + 300 * Math.sin(t * 2);   // classic wail sweep
            osc.frequency.setValueAtTime(freq, ctx.currentTime);
          }}, 50);
        }} catch(e) {{ console.warn('Audio blocked until user interacts with page:', e); }}
      }}
      document.getElementById('cb-mute').onclick = () => {{
        playing = !playing;
        if (gain) gain.gain.value = playing ? 0.05 : 0;
        document.getElementById('cb-mute').textContent = playing ? '🔇 Mute siren' : '🔊 Unmute siren';
      }};
      {siren_js}
    </script>
    """
    components.html(html, height=height)


def chaotic_vitals_css() -> str:
    """Inline CSS class students can wrap around a vitals value string to
    make it visually jitter/flicker, used only while in Code Blue mode."""
    return (
        "display:inline-block;animation:cbJitter .12s infinite;"
    )


CHAOTIC_KEYFRAMES = """
<style>
@keyframes cbJitter {
  0%   { transform: translateY(0px);   opacity:1;   }
  30%  { transform: translateY(-1px);  opacity:.85; }
  60%  { transform: translateY(1px);   opacity:1;   }
  100% { transform: translateY(0px);   opacity:1;   }
}
</style>
"""


def is_arrest_rhythm(rhythm: str) -> bool:
    """True for rhythms that should trigger Code Blue automatically."""
    if not rhythm:
        return False
    r = rhythm.lower()
    return any(k in r for k in ("vfib", "v-fib", "vf", "vtach", "v-tach", "pulseless",
                                 "asystole", "pea", "arrest"))
