"""
medsim_cpr.py
────────────────────────────────────────────────────────────────────────────
CPR / cardiac-massage trainer for the MedSim Room.

Two tiers, both surfaced from the SAME screen so the student picks the
right one for their device — nothing is silently downgraded or upgraded:

  1. "webcam" (works today, any device): tracks the student's hand/wrist
     over the manikin's chest marker via MediaPipe, counts compressions,
     and scores CADENCE (target 100-120/min per AHA) and hand position.
     This is explicitly labeled as a rate/position trainer — it does NOT
     measure real compression depth or force, because no ordinary RGB
     camera (laptop, Android, or iPhone — including Pro/LiDAR models) can
     expose that to a browser. See NOTE_ON_LIDAR below for why.

  2. "depth_hardware": real depth data from the native iPhone LiDAR app
     (see ios_lidar_cpr/) — that app posts compressions directly to the
     `vh_cpr_depth_stream` Supabase table, tagged with a short session
     code. This tier generates that code, shows it to the student, and
     polls the table for matching rows. If the app hasn't posted anything
     yet, it says so plainly rather than showing a fake reading — the
     Swift app itself is a first draft (see ios_lidar_cpr/README.md),
     untested on real hardware, so this Python side has never seen real
     data flow through it either.

NOTE_ON_LIDAR: Safari does not expose ARKit/LiDAR depth to JavaScript —
that data is only available to native iOS apps. So "use your iPhone's
camera in the browser" is, technically, the same RGB-only tier as any
other device. Real depth requires the native app in ios_lidar_cpr/.

Requires one new Supabase table (see ios_lidar_cpr/README.md for the exact
CREATE TABLE statement): vh_cpr_depth_stream.
"""

import time
import uuid
import requests
import streamlit as st
import streamlit.components.v1 as components

DEPTH_TABLE = "vh_cpr_depth_stream"


def _sb_creds():
    return st.secrets.get("SUPABASE_URL", ""), st.secrets.get("SUPABASE_KEY", "")


def _sb_available() -> bool:
    url, key = _sb_creds()
    return bool(url and key and not url.startswith("YOUR_"))


def _sb_headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _poll_depth_stream(session_code: str, since_id: int = 0) -> list:
    if not _sb_available():
        return []
    url, key = _sb_creds()
    try:
        r = requests.get(f"{url}/rest/v1/{DEPTH_TABLE}", headers=_sb_headers(key),
                          params={"select": "*", "session_code": f"eq.{session_code}",
                                  "id": f"gt.{since_id}", "order": "id.asc"}, timeout=8)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def _cpr_webcam_html(target_rate: int = 110) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;overflow:hidden;font-family:'Segoe UI',sans-serif;color:#e6edf3}}
#wrap{{position:relative;width:100%;height:100%}}
video{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transform:scaleX(-1)}}
canvas{{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}}
#hud{{position:absolute;top:10px;left:10px;right:10px;display:flex;justify-content:space-between;
      background:rgba(0,0,0,.7);border-radius:8px;padding:10px 16px;font-size:13px}}
#rate{{font-size:1.6rem;font-weight:800}}
#rate.ok{{color:#22c55e}} #rate.slow{{color:#f59e0b}} #rate.fast{{color:#ef4444}}
#count{{font-size:1.6rem;font-weight:800;color:#a1c9f4}}
#target{{position:absolute;left:50%;top:50%;width:110px;height:110px;margin:-55px 0 0 -55px;
         border:3px dashed rgba(255,90,90,.7);border-radius:50%}}
#note{{position:absolute;bottom:8px;left:8px;right:8px;text-align:center;font-size:10.5px;color:#9091a4}}
</style></head>
<body>
<div id="wrap">
  <video id="video" autoplay playsinline muted></video>
  <canvas id="c"></canvas>
  <div id="target"></div>
  <div id="hud">
    <div>Rate: <span id="rate">--</span> /min <span style="color:#9091a4">(target {target_rate})</span></div>
    <div>Compressions: <span id="count">0</span></div>
  </div>
  <div id="note">Rate/position trainer only — not a certified depth or force measurement.</div>
</div>
<script type="module">
const video = document.getElementById('video');
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
let count = 0, lastY = null, lastPeakT = 0, rates = [];

async function boot() {{
  try {{
    const stream = await navigator.mediaDevices.getUserMedia({{ video: {{facingMode:'user'}}, audio:false }});
    video.srcObject = stream;
    await new Promise(r => video.onloadedmetadata = r);
    video.play();
  }} catch(e) {{ document.getElementById('note').textContent = 'Camera unavailable: ' + e.name; return; }}

  const {{ HandLandmarker, FilesetResolver }} = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.8/vision_bundle.mjs');
  const fs = await FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.8/wasm');
  const landmarker = await HandLandmarker.createFromOptions(fs, {{
    baseOptions: {{ modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task', delegate:'GPU' }},
    runningMode: 'VIDEO', numHands: 2,
  }});

  function resize() {{ canvas.width = video.clientWidth; canvas.height = video.clientHeight; }}
  window.addEventListener('resize', resize); resize();

  function loop(ts) {{
    requestAnimationFrame(loop);
    if (video.readyState < 2) return;
    ctx.clearRect(0,0,canvas.width,canvas.height);
    let res;
    try {{ res = landmarker.detectForVideo(video, ts); }} catch(e) {{ return; }}
    if (res.landmarks && res.landmarks.length) {{
      const wrist = res.landmarks[0][0]; // wrist landmark of first detected hand
      const y = wrist.y;
      ctx.beginPath(); ctx.arc((1-wrist.x)*canvas.width, y*canvas.height, 10, 0, Math.PI*2);
      ctx.fillStyle = '#ffd400'; ctx.fill();

      if (lastY !== null) {{
        // detect downward-then-upward motion = one compression
        const dy = y - lastY;
        if (dy < -0.015 && ts - lastPeakT > 250) {{ // upward rebound after a push
          count++;
          document.getElementById('count').textContent = count;
          const now = ts;
          if (lastPeakT) {{
            const rate = 60000 / (now - lastPeakT);
            rates.push(rate); if (rates.length > 5) rates.shift();
            const avg = rates.reduce((a,b)=>a+b,0)/rates.length;
            const el = document.getElementById('rate');
            el.textContent = Math.round(avg);
            el.className = avg < 95 ? 'slow' : (avg > 125 ? 'fast' : 'ok');
          }}
          lastPeakT = now;
        }}
      }}
      lastY = y;
    }}
  }}
  requestAnimationFrame(loop);
}}
boot();
</script>
</body></html>"""


def render_cpr_trainer(target_rate: int = 110, height: int = 460):
    """Streamlit UI: device-tier picker + the appropriate trainer."""
    st.markdown("### 💗 Cardiac Massage (CPR) Trainer")

    tier = st.session_state.get("medsim_cpr_tier")

    if not tier:
        st.warning(
            "⚠️ **Read before choosing:** no camera on any phone or laptop — including "
            "iPhone Pro models — can measure real compression depth or force through a "
            "web browser. Apple's LiDAR sensor is only accessible to native iPhone apps, "
            "not web pages. Both options below give you **rate and hand-position** "
            "feedback only."
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💻 Use this device's camera", use_container_width=True, type="primary"):
                st.session_state.medsim_cpr_tier = "webcam"
                st.rerun()
        with c2:
            if st.button("📱 I have the depth-sensing app installed", use_container_width=True):
                st.session_state.medsim_cpr_tier = "depth_hardware"
                st.rerun()
        return

    if tier == "depth_hardware":
        if not _sb_available():
            st.error("Supabase not configured — the depth stream needs it, same as everything else in this app.")
            return

        code = st.session_state.setdefault("medsim_cpr_session_code", uuid.uuid4().hex[:6].upper())
        st.info(f"📱 **Session code: `{code}`** — enter this exact code in the iPhone app "
                f"(ios_lidar_cpr) and tap Start there.")
        st.caption("This tier depends on the native iOS app in ios_lidar_cpr/, which was "
                   "written but never run on real hardware — if nothing shows up below after "
                   "you start the phone app, that's the first thing to debug on-device, not "
                   "necessarily this page.")

        since_id = st.session_state.get("medsim_cpr_last_id", 0)
        new_rows = _poll_depth_stream(code, since_id)
        if new_rows:
            st.session_state.medsim_cpr_last_id = new_rows[-1]["id"]
            st.session_state.setdefault("medsim_cpr_depth_history", [])
            st.session_state.medsim_cpr_depth_history.extend(new_rows)

        history = st.session_state.get("medsim_cpr_depth_history", [])
        if not history:
            st.warning("No compressions received yet. Waiting for the phone app to start streaming…")
        else:
            latest = history[-1]
            c1, c2, c3 = st.columns(3)
            depth = latest.get("depth_cm", 0) or 0
            rate = latest.get("rate_per_min", 0) or 0
            c1.metric("Depth", f"{depth:.1f} cm", delta="target 5-6 cm")
            c2.metric("Rate", f"{rate:.0f} /min", delta="target 100-120")
            c3.metric("Compressions", len(history))
            in_range = 5.0 <= depth <= 6.0 and 100 <= rate <= 120
            st.success("✅ In target range") if in_range else st.warning("Outside AHA target range")

        if st.button("← Back to device choice"):
            st.session_state.pop("medsim_cpr_tier", None)
            st.session_state.pop("medsim_cpr_session_code", None)
            st.session_state.pop("medsim_cpr_last_id", None)
            st.session_state.pop("medsim_cpr_depth_history", None)
            st.rerun()

        time.sleep(1)
        st.rerun()
        return

    # tier == "webcam"
    st.caption("Position your hand over the target circle on the manikin's chest and compress "
               "rhythmically. This measures **rate and position**, not depth/force.")
    components.html(_cpr_webcam_html(target_rate), height=height, scrolling=False)
    if st.button("← Back to device choice"):
        st.session_state.pop("medsim_cpr_tier", None)
        st.rerun()
