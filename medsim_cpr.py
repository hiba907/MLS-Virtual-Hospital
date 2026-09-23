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

  2. "depth_hardware" (future): a placeholder tier for when real depth
     data is available — either a native iOS LiDAR app (see
     medsim_lidar_ios_SCOPE.md) or a dedicated depth camera / sensor
     manikin. This tier reads from `st.session_state.medsim_depth_stream`
     if something (a future bridge) populates it; otherwise it tells the
     student honestly that no depth device is connected and offers the
     webcam trainer instead.

NOTE_ON_LIDAR: Safari does not expose ARKit/LiDAR depth to JavaScript —
that data is only available to native iOS apps. So "use your iPhone's
camera in the browser" is, technically, the same RGB-only tier as any
other device. Real depth requires the native app project scoped separately.
"""

import time
import streamlit as st
import streamlit.components.v1 as components


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
        depth_stream = st.session_state.get("medsim_depth_stream")
        if not depth_stream:
            st.error(
                "No depth device connected yet. This tier is reserved for a future native "
                "iPhone LiDAR app (or a depth camera / sensor manikin) that streams real "
                "compression depth into this session — none is connected right now."
            )
            if st.button("← Use webcam trainer instead"):
                st.session_state.medsim_cpr_tier = "webcam"
                st.rerun()
            return
        # Future: render real depth-based feedback from depth_stream here.
        st.success("Depth device connected.")
        return

    # tier == "webcam"
    st.caption("Position your hand over the target circle on the manikin's chest and compress "
               "rhythmically. This measures **rate and position**, not depth/force.")
    components.html(_cpr_webcam_html(target_rate), height=height, scrolling=False)
    if st.button("← Back to device choice"):
        st.session_state.pop("medsim_cpr_tier", None)
        st.rerun()
