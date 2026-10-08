"""
medsim_foley.py
────────────────────────────────────────────────────────────────────────────
Urinary (Foley) catheterization trainer — a guided, gesture-controlled 3D
procedure walkthrough, built on the same mechanics as medsim_anatomy_viewer.py
(MediaPipe hand-tracking → pinch-to-zoom, fist-drag → rotate) applied to a
step-by-step catheterization sequence instead of a single static organ.

HONEST SCOPE NOTE — read this before telling students what this is:
  This gives genuine anatomy orientation, correct procedural sequence, and
  decision-point quizzing. It does NOT give touch. A webcam can see where a
  student's hand is in the air; it cannot sense contact, resistance, or a
  catheter entering a lumen. There is no software fix for that — real tactile
  feedback needs a physical phantom (silicone urethra model + a real Foley
  catheter + embedded sensors), which is a separate, optional hardware module
  (see FoleyHardwareBridge below) that this file deliberately does NOT claim
  to have tested, matching how medsim_cpr.py's LiDAR tier is scoped.

No existing file is modified. Purely additive:
  - new file: medsim_foley.py (this file)
  - app.py needs only: an import-guard block + one sidebar entry + one
    `elif p=="foley_catheterization":` route, same pattern as medsim_room.

Requires one new Supabase table (optional — falls back to session-only
scoring if Supabase isn't configured, same fallback pattern used elsewhere):

    create table vh_foley_attempts (
      id           bigint generated always as identity primary key,
      student_email  text,
      case_sex         text,
      steps_completed    int,
      quiz_score            numeric,
      completed_at             timestamp default now()
    );
"""

import requests
import streamlit as st
import streamlit.components.v1 as components

NAVY, BLUE, TEAL = "#0a2540", "#1a4f8a", "#0e7490"
GREEN, AMBER, RED = "#059669", "#d97706", "#dc2626"

TABLE = "vh_foley_attempts"

STEPS = [
    {"title": "1. Prepare", "note": "Gather sterile kit, catheter size, gloves. Explain procedure, confirm consent/identity.",
     "why": "Preventing CAUTI (catheter-associated UTI) starts before you open the kit."},
    {"title": "2. Position", "note": "Supine, legs abducted (female) or supine (male). Drape for privacy and sterile field.",
     "why": "Correct positioning gives a clear, stable line of sight to the meatus."},
    {"title": "3. Sterile setup", "note": "Open kit using sterile no-touch technique. Don sterile gloves.",
     "why": "Break in sterile technique here is the single biggest CAUTI risk factor."},
    {"title": "4. Clean the meatus", "note": "Antiseptic swabs, single pass each, outward from meatus, non-dominant hand retracts/separates.",
     "why": "Reduces bacterial load being pushed into the urethra on insertion."},
    {"title": "5. Lubricate", "note": "Apply sterile lubricant (with anesthetic gel for male patients) to the catheter tip / urethra.",
     "why": "Minimizes mucosal trauma and patient discomfort."},
    {"title": "6. Insert gently", "note": "Advance catheter steadily until urine return — never force against resistance.",
     "why": "Forcing against resistance is how urethral injury happens."},
    {"title": "7. Confirm urine return", "note": "Watch for flow into the drainage bag/tubing before advancing further or inflating.",
     "why": "Urine return is your confirmation the tip is in the bladder, not just the urethra."},
    {"title": "8. Inflate the balloon", "note": "Only after confirmed urine return, inflate with the manufacturer-specified volume of sterile water.",
     "why": "Inflating before bladder placement is a classic cause of urethral injury."},
    {"title": "9. Secure & document", "note": "Secure tubing to the leg, position bag below bladder level, document time/size/output/tolerance.",
     "why": "Securing prevents traction injury; documentation drives ongoing CAUTI-prevention review."},
]

QUIZ = [
    {"q": "You feel firm resistance halfway through insertion. What do you do?",
     "options": ["Push a little harder, it usually passes", "Stop, do not force it, reassess/escalate", "Inflate the balloon early to anchor it"],
     "answer": 1,
     "explain": "Never force against resistance — that's how urethral trauma happens. Stop and reassess."},
    {"q": "When is it safe to inflate the retention balloon?",
     "options": ["As soon as the catheter is fully inserted", "Only after confirmed urine return", "Before insertion, to guide it"],
     "answer": 1,
     "explain": "Inflating before confirmed bladder placement risks inflating within the urethra."},
    {"q": "Why clean the meatus outward, away from it, rather than side to side?",
     "options": ["It's faster", "It avoids dragging bacteria back toward the meatus", "It doesn't matter clinically"],
     "answer": 1,
     "explain": "A single outward pass per swab avoids reintroducing bacteria into the field you just cleaned."},
]


# ── Supabase plumbing (optional — same pattern as the rest of the project) ──
def _sb_creds():
    try:
        return st.secrets.get("SUPABASE_URL", ""), st.secrets.get("SUPABASE_KEY", "")
    except Exception:
        # No secrets.toml configured at all (not just missing keys) — treat as
        # "Supabase not set up" rather than crashing the page.
        return "", ""


def _sb_available() -> bool:
    url, key = _sb_creds()
    return bool(url and key and not url.startswith("YOUR_"))


def _sb_headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation"}


def save_attempt(row: dict):
    if not _sb_available():
        return
    url, key = _sb_creds()
    try:
        requests.post(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key), json=row, timeout=10)
    except Exception:
        pass  # non-fatal — attempt still shown to the student this session


# ── 3D viewer: gesture-controlled camera over a simple labeled cutaway ──────
# Uses primitive Three.js geometry (not an imported anatomical mesh) so this
# never claims to be a licensed anatomical model — it's a schematic cutaway
# for orientation, same honesty standard as medsim_pathology.py's placeholder.
def _build_foley_html(sex: str, step_idx: int) -> str:
    step = STEPS[step_idx]
    female = sex == "Female"
    template = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d1117;overflow:hidden;font-family:'Segoe UI',sans-serif;color:#e6edf3}
#c{width:100%;height:100%;display:block}
#hud{position:absolute;top:10px;left:10px;background:rgba(0,0,0,.75);border:1px solid rgba(255,255,255,.15);
     border-radius:8px;padding:8px 14px;font-size:13px;max-width:320px}
#hint{position:absolute;bottom:10px;left:50%;transform:translateX(-50%);font-size:11px;color:#9091a4}
#gesturebox{position:absolute;top:10px;right:10px;width:160px;border-radius:8px;overflow:hidden;
            border:1px solid rgba(255,255,255,.2);display:none}
#toggle{position:absolute;bottom:10px;right:10px;background:rgba(20,20,30,.85);border:1px solid rgba(255,255,255,.2);
        color:#e6edf3;border-radius:6px;padding:6px 12px;font-size:12px;cursor:pointer}
</style></head>
<body>
<canvas id="c"></canvas>
<div id="hud"><b>__STEP_TITLE__</b></div>
<video id="gesturebox" autoplay muted playsinline></video>
<canvas id="gestureoverlay" style="display:none"></canvas>
<button id="toggle">🖐 Enable gesture camera (optional)</button>
<div id="hint">Drag to rotate &middot; scroll/pinch to zoom &middot; or enable gestures above</div>
<script type="importmap">
{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
"three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({canvas, antialias:true});
renderer.setSize(window.innerWidth, window.innerHeight);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0d1117);
const camera = new THREE.PerspectiveCamera(50, window.innerWidth/window.innerHeight, 0.1, 100);
camera.position.set(0, 0, 6);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

scene.add(new THREE.AmbientLight(0xffffff, 0.7));
const dl = new THREE.DirectionalLight(0xffffff, 0.8); dl.position.set(3,4,5); scene.add(dl);

// Schematic pelvic cutaway — primitive shapes only, labeled for orientation.
// NOT a licensed anatomical model; see file docstring.
const group = new THREE.Group();
const bladder = new THREE.Mesh(new THREE.SphereGeometry(1.1, 32, 32),
  new THREE.MeshStandardMaterial({color:0xd98a9a, transparent:true, opacity:0.55}));
bladder.position.set(0, 1.4, 0);
group.add(bladder);

const urethraLen = __FEMALE__ ? 1.4 : 3.2;
const urethraCurve = __FEMALE__ ? 0.1 : 0.9;
const pts = [];
for (let i=0;i<=20;i++){
  const t = i/20;
  pts.push(new THREE.Vector3(Math.sin(t*Math.PI)*urethraCurve*0.3, 1.4 - t*urethraLen, 0.2));
}
const curve = new THREE.CatmullRomCurve3(pts);
const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 40, 0.14, 12, false),
  new THREE.MeshStandardMaterial({color:0xf0b7c4, transparent:true, opacity:0.7}));
group.add(tube);

// Catheter — advances along the urethra curve based on current step.
const catheter = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 1, 16),
  new THREE.MeshStandardMaterial({color:0xffd400}));
const stepIdx = __STEP_IDX__;
const advance = Math.min(1, Math.max(0, (stepIdx - 4) / 3)); // visible from step 6 onward
const catPos = curve.getPoint(1 - advance*0.85);
catheter.position.copy(catPos);
catheter.visible = stepIdx >= 5;
group.add(catheter);

// Balloon — inflates only at step 8 (idx 7), matching the real safety rule.
if (stepIdx >= 7) {
  const balloon = new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 16),
    new THREE.MeshStandardMaterial({color:0xffffff}));
  balloon.position.copy(curve.getPoint(0.08));
  group.add(balloon);
}

scene.add(group);

function animate(){
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth/window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// ── Optional MediaPipe gesture camera: pinch to zoom, same math as
// medsim_anatomy_viewer.py. Entirely opt-in via the button — never auto-starts.
document.getElementById('toggle').onclick = async () => {
  const video = document.getElementById('gesturebox');
  video.style.display = 'block';
  try {
    const stream = await navigator.mediaDevices.getUserMedia({video:true});
    video.srcObject = stream;
    const { HandLandmarker, FilesetResolver } = await import(
      "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/+esm");
    const files = await FilesetResolver.forVisionTasks(
      "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm");
    const landmarker = await HandLandmarker.createFromOptions(files, {
      baseOptions: {modelAssetPath:
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"},
      numHands: 1, runningMode: "VIDEO",
    });
    let lastDist = null;
    function loop(ts) {
      if (video.readyState >= 2) {
        const res = landmarker.detectForVideo(video, ts);
        if (res.landmarks && res.landmarks[0]) {
          const lm = res.landmarks[0];
          const thumb = lm[4], index = lm[8];
          const dist = Math.hypot(thumb.x-index.x, thumb.y-index.y);
          if (lastDist !== null) {
            const delta = dist - lastDist;
            camera.position.z = Math.max(2, Math.min(12, camera.position.z - delta*20));
          }
          lastDist = dist;
        }
      }
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
  } catch (e) {
    alert("Camera unavailable: " + e.message);
  }
};
</script>
</body></html>"""
    return (template.replace("__STEP_TITLE__", step["title"])
                     .replace("__FEMALE__", "true" if female else "false")
                     .replace("__STEP_IDX__", str(step_idx)))


def render_foley_trainer():
    st.markdown("## 🩺 Urinary Catheterization (Foley) Trainer")
    st.info("🔒 **Teaching simulation — follow your institution's protocol.** "
            "This gives sequence, anatomy orientation and decision-point quizzing. "
            "It does not simulate touch or resistance — see the note below.")
    with st.expander("⚠️ What this is and isn't"):
        st.markdown(
            "- **Is:** a gesture/mouse-controlled 3D walkthrough of the 9-step procedure, "
            "a schematic (not licensed-anatomy) cutaway showing catheter advance and balloon "
            "timing, and a safety-reasoning quiz.\n"
            "- **Isn't:** a substitute for hands-on phantom practice. A webcam cannot sense "
            "contact, resistance, or depth of insertion — that needs a physical model with "
            "embedded sensors, which is a separate hardware add-on we haven't built or tested "
            "(same honesty boundary as the CPR depth-sensing tier)."
        )

    sex = st.radio("Case", ["Female", "Male"], horizontal=True, key="foley_sex")
    step_idx = st.session_state.get("foley_step", 0)

    cols = st.columns([1, 4, 1])
    with cols[0]:
        if st.button("⬅ Prev", disabled=step_idx == 0):
            st.session_state.foley_step = max(0, step_idx - 1)
            st.rerun()
    with cols[2]:
        if st.button("Next ➡", disabled=step_idx == len(STEPS) - 1):
            st.session_state.foley_step = min(len(STEPS) - 1, step_idx + 1)
            st.rerun()

    step = STEPS[step_idx]
    with cols[1]:
        st.progress((step_idx + 1) / len(STEPS), text=f"Step {step_idx+1} of {len(STEPS)}: {step['title']}")

    components.html(_build_foley_html(sex, step_idx), height=480, scrolling=False)

    st.markdown(f"**{step['title']}** — {step['note']}")
    st.caption(f"Why it matters: {step['why']}")

    st.markdown("---")
    if step_idx == len(STEPS) - 1:
        st.markdown("### 🧪 Safety Quiz")
        score = 0
        answers = []
        for i, q in enumerate(QUIZ):
            ans = st.radio(q["q"], q["options"], key=f"foley_q_{i}", index=None)
            answers.append(ans)
        if st.button("Submit Quiz", type="primary"):
            for i, q in enumerate(QUIZ):
                picked = answers[i]
                if picked is not None and q["options"].index(picked) == q["answer"]:
                    score += 1
                    st.success(f"✅ {q['q']} — {q['explain']}")
                else:
                    st.error(f"❌ {q['q']} — {q['explain']}")
            pct = round(100 * score / len(QUIZ), 1)
            st.metric("Quiz score", f"{pct}%")
            save_attempt({
                "student_email": st.session_state.get("auth_user", {}).get("email", "unknown"),
                "case_sex": sex, "steps_completed": len(STEPS), "quiz_score": pct,
            })


# ── Optional hardware bridge — scoped, NOT built/tested, same pattern as
# medsim_cpr.py's depth_hardware tier. Documented here only so a future
# phantom+ESP32 build has a clear, honest landing point; nothing below this
# line executes anything or claims hardware support exists today. ──────────
class FoleyHardwareBridge:
    """STUB. Would receive WebSocket events from an ESP32-driven silicone
    phantom (IR break-beam at meatus + bladder end, flow sensor for urine
    return) and advance the on-screen catheter/urine-return state to match
    real physical insertion. Never tested against real hardware — do not
    present this class as working. Kept here only as a scoped, honest
    starting point if the hardware phantom is built later."""
    pass
