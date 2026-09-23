"""
medsim_anatomy_viewer.py
────────────────────────────────────────────────────────────────────────────
Embeddable 3D anatomy explorer for the MedSim Room.

This is an ADDITIVE adaptation of ai-gestures/app.py: it reuses the same
Three.js + MediaPipe-gesture engine and landmark-marker concept, but exposes
it as a plain function — build_anatomy_html(...) — that any Streamlit page
(e.g. medsim_room.py) can drop into components.html(), instead of the
original standalone `streamlit run app.py` script.

Nothing in ai-gestures--main/app.py is modified. This file only imports the
*idea* (organ dict + Three.js viewer) and adds one new entry ("Forearm /
Vein Access") relevant to IV cannulation, so students can zoom into the
cephalic / basilic / median cubital veins before starting the needle
procedure.

Usage from another Streamlit page:

    from medsim_anatomy_viewer import render_anatomy_explorer

    render_anatomy_explorer(
        organ_key="🩸 Forearm / Vein Access",
        phase_label="Site Selection",
        height=560,
    )
"""

import json
import os
import base64
import streamlit as st
import streamlit.components.v1 as components

# ── Organ + phase data ───────────────────────────────────────────────────────
# Same structure/spirit as ai-gestures ORGANS dict (organ -> phases -> landmarks)
# plus one new organ added for IV access teaching.
ORGANS = {
    "🫀 Heart": {
        "color": "#e05a6a",
        "model": "heart.glb",
        "phases": [
            {"label": "Inspection", "instruction": "Observe chest wall for visible pulsations, precordial bulge, scars, or asymmetry.",
             "cameraZ": 5.0, "landmarks": [
                 {"label": "Aortic", "x": 0.4, "y": 0.5, "z": 0.2, "color": "#A1C9F4"},
                 {"label": "Pulmonic", "x": -0.3, "y": 0.5, "z": 0.2, "color": "#8DE5A1"},
                 {"label": "Tricuspid", "x": 0.2, "y": -0.1, "z": 0.2, "color": "#FFB482"},
                 {"label": "Mitral", "x": -0.4, "y": -0.2, "z": 0.2, "color": "#FF9F9B"},
             ]},
            {"label": "Auscultation", "instruction": "Listen at Aortic, Pulmonic, Tricuspid, Mitral areas. S1, S2, murmurs.",
             "cameraZ": 2.5, "landmarks": [
                 {"label": "Aortic", "x": 0.4, "y": 0.5, "z": 0.3, "color": "#A1C9F4"},
                 {"label": "Mitral", "x": -0.4, "y": -0.2, "z": 0.3, "color": "#FF9F9B"},
             ]},
        ],
    },
    "🩸 Forearm / Vein Access": {
        # New organ added for IV cannulation teaching. Structure mirrors the
        # original ai-gestures organs exactly so it drops into the same engine.
        "color": "#f28ba8",
        "model": "forearm_vein.glb",  # optional — placeholder sphere/vessel shown if absent
        "phases": [
            {"label": "Overview", "instruction": "Full antecubital fossa and forearm. Identify the venous map before touching the patient.",
             "cameraZ": 5.0, "landmarks": [
                 {"label": "Cephalic Vein", "x": 0.5, "y": 0.3, "z": 0.2, "color": "#5ac8fa"},
                 {"label": "Basilic Vein", "x": -0.5, "y": 0.2, "z": 0.2, "color": "#5ac8fa"},
                 {"label": "Median Cubital Vein", "x": 0.0, "y": 0.4, "z": 0.25, "color": "#ffd400"},
             ]},
            {"label": "Site Selection", "instruction": "Zoom into the median cubital vein — preferred site: straight, bouncy, non-mobile, away from joints.",
             "cameraZ": 2.5, "landmarks": [
                 {"label": "Median Cubital Vein", "x": 0.0, "y": 0.4, "z": 0.3, "color": "#ffd400"},
                 {"label": "Insertion Point", "x": 0.0, "y": 0.4, "z": 0.35, "color": "#ff5a5a"},
             ]},
            {"label": "Cross-Section", "instruction": "Toggle section view to see vein depth relative to skin and underlying tendon/nerve.",
             "cameraZ": 2.0, "landmarks": [
                 {"label": "Vein Lumen", "x": 0.0, "y": 0.4, "z": 0.3, "color": "#ffd400"},
             ]},
            {"label": "IV Insertion", "instruction": "Pinch to zoom in until comfortable, then click/tap the red marker to insert the needle at 15\u201330\u00b0 bevel-up.",
             "cameraZ": 2.2, "landmarks": [
                 {"label": "Median Cubital Vein", "x": 0.0, "y": 0.4, "z": 0.3, "color": "#ffd400"},
                 {"label": "Insertion Point", "x": 0.0, "y": 0.4, "z": 0.35, "color": "#ff5a5a", "insertable": True},
             ]},
        ],
    },
}


def _static_model_path(model_name: str) -> str:
    """Look for a .glb next to this file's own static/models/, or fall back
    to ai-gestures--main/static/models/ if that project sits alongside this
    one on disk. Never errors — placeholder geometry is used if not found."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "static", "models", model_name),
        os.path.join(here, "ai-gestures--main", "static", "models", model_name),
        os.path.join(here, "..", "ai-gestures--main", "static", "models", model_name),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return ""


def build_anatomy_html(organ_key: str, phase_idx: int = 0, glb_b64: str = "",
                        enable_gestures: bool = True) -> str:
    """Return a self-contained HTML string (Three.js viewer + optional
    MediaPipe hand-gesture control + landmark markers) for the given organ.
    Pass the result to streamlit.components.v1.html(...)."""

    organ = ORGANS.get(organ_key, list(ORGANS.values())[0])
    phases = organ["phases"]
    phase_idx = max(0, min(phase_idx, len(phases) - 1))

    if not glb_b64:
        path = _static_model_path(organ["model"])
        if path:
            with open(path, "rb") as fh:
                glb_b64 = base64.b64encode(fh.read()).decode("utf-8")

    phases_json = json.dumps(phases, ensure_ascii=True)
    color_json = json.dumps(organ["color"])
    name_json = json.dumps(organ_key)
    glb_b64_json = json.dumps(glb_b64)
    phase_idx_json = json.dumps(phase_idx)
    gestures_json = json.dumps(bool(enable_gestures))

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d1117;overflow:hidden;font-family:'Segoe UI',sans-serif;color:#e6edf3}
#wrap{position:relative;width:100%;height:100vh}
#video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transform:scaleX(-1);z-index:1}
#c3d{position:absolute;inset:0;width:100%;height:100%;z-index:2;pointer-events:none}
#cHand{position:absolute;inset:0;width:100%;height:100%;z-index:3;pointer-events:none}
#ui{position:absolute;inset:0;z-index:4}
#status{position:absolute;top:10px;left:10px;background:rgba(0,0,0,.75);border:1px solid rgba(255,255,255,.15);border-radius:8px;padding:5px 11px;font-size:12px;pointer-events:none}
#gest{position:absolute;top:10px;right:10px;background:rgba(0,0,0,.75);border:1px solid rgba(255,255,255,.15);border-radius:8px;padding:5px 11px;font-size:12px;pointer-events:none;text-align:right}
#btns{position:absolute;top:10px;left:50%;transform:translateX(-50%);display:flex;gap:6px}
.cb{background:rgba(20,20,30,.85);border:1px solid rgba(255,255,255,.2);color:#e6edf3;border-radius:6px;padding:4px 10px;font-size:11px;cursor:pointer;pointer-events:all}
.cb.on{background:#3a6df0;border-color:#3a6df0}
#load{position:absolute;inset:0;z-index:9;background:#0d1117;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px}
#load h3{color:#e6edf3}
#prog{width:240px;height:7px;background:#161b22;border-radius:4px;overflow:hidden}
#bar{height:100%;background:#3a6df0;width:0;border-radius:4px;transition:width .3s}
#lbl{color:#9091a4;font-size:12px}
#err{display:none;position:absolute;inset:0;z-index:10;background:rgba(13,17,23,.96);flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:24px}
#err.show{display:flex}
#err h2{color:#f04438;margin-bottom:10px}
#err p{color:#9091a4;font-size:13px;line-height:1.7;max-width:420px}
#retryBtn{margin-top:16px;background:#3a6df0;border:none;color:#fff;border-radius:8px;padding:9px 24px;font-size:13px;cursor:pointer;pointer-events:all}
</style>
</head>
<body>
<div id="wrap">
  <div id="load"><h3>Loading anatomy model…</h3><div id="prog"><div id="bar"></div></div><div id="lbl">Initialising…</div></div>
  <div id="err">
    <h2>Camera unavailable</h2>
    <p id="errMsg">Continuing in mouse/touch mode — drag to rotate, scroll to zoom.</p>
    <button id="retryBtn">Retry camera</button>
  </div>
  <video id="video" autoplay playsinline muted></video>
  <canvas id="c3d"></canvas>
  <canvas id="cHand"></canvas>
  <div id="ui">
    <div id="status">Starting…</div>
    <div id="gest">Gesture: —</div>
    <div id="btns">
      <button class="cb" id="bRot" onclick="toggleRotate()">Rotate</button>
      <button class="cb" id="bSec" onclick="toggleSection()">Cross-section</button>
      <button class="cb" id="bLmk" onclick="toggleLandmarks()">Landmarks</button>
      <button class="cb" onclick="nextPhase()">Next phase &gt;</button>
    </div>
    <div style="position:absolute;bottom:10px;left:10px;right:10px;text-align:center;font-size:11px;color:#9091a4;pointer-events:none;">
      🤏 Pinch thumb + index to zoom &nbsp;·&nbsp; 👆 Click/tap the red marker to insert
    </div>
  </div>
</div>

<script type="importmap">
{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}
</script>

<script type="module">
import * as THREE from 'three';
import { GLTFLoader }    from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const PHASES      = """ + phases_json + """;
const ORG_COLOR    = """ + color_json + """;
const ORG_NAME      = """ + name_json + """;
const GLB_B64        = """ + glb_b64_json + """;
const GESTURES_ON     = """ + gestures_json + """;
let   phaseIdx         = """ + phase_idx_json + """;

const $  = id => document.getElementById(id);
const setStatus = t => { $('status').textContent = t; };
const setGest   = t => { $('gest').textContent = t; };
const setBar    = p => { $('bar').style.width = p + '%'; $('lbl').textContent = Math.round(p) + '%…'; };
const hideLoad  = () => { $('load').style.display = 'none'; };
const showErr   = msg => { $('errMsg').textContent = msg; $('err').classList.add('show'); };

const canvas3d  = $('c3d');
const renderer  = new THREE.WebGLRenderer({ canvas: canvas3d, alpha: true, antialias: true });
renderer.setClearColor(0x000000, 0);
renderer.setPixelRatio(window.devicePixelRatio);
renderer.localClippingEnabled = true;

const scene  = new THREE.Scene();
const cam3d  = new THREE.PerspectiveCamera(45, 1, 0.01, 100);
cam3d.position.set(0, 0, 5);

const controls = new OrbitControls(cam3d, canvas3d);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.enableZoom    = true;
canvas3d.style.pointerEvents = 'all';

scene.add(new THREE.AmbientLight(0xffffff, 0.9));
const dl = new THREE.DirectionalLight(0xffffff, 1.3);
dl.position.set(5, 10, 7);
scene.add(dl);
const dl2 = new THREE.DirectionalLight(0xa1c9f4, 0.5);
dl2.position.set(-5, -5, -5);
scene.add(dl2);

function resize() {
  const w = $('wrap').clientWidth, h = $('wrap').clientHeight;
  renderer.setSize(w, h, false);
  cam3d.aspect = w / h;
  cam3d.updateProjectionMatrix();
  $('cHand').width = w; $('cHand').height = h;
}
window.addEventListener('resize', resize);
resize();

let organGroup   = null;
let lmkDots      = [];
let autoRotate   = false;
let showSec      = false;
let showLmk      = true;
let stream       = null;
let cooldown     = 0;
const COOL = 28;
const clipPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0.3);

function clearScene() {
  const rem = [];
  scene.traverse(o => { if (o !== scene && (o.isMesh || o.isGroup) && o !== dl && o !== dl2) rem.push(o); });
  rem.forEach(o => scene.remove(o));
  organGroup = null; lmkDots = [];
}

function placeholderModel(color) {
  clearScene();
  const geo = new THREE.CapsuleGeometry ? new THREE.CylinderGeometry(0.5, 0.6, 2.2, 24) : new THREE.IcosahedronGeometry(0.9, 2);
  const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.5, metalness: 0.1 });
  organGroup = new THREE.Mesh(geo, mat);
  organGroup.rotation.z = Math.PI / 2;
  scene.add(organGroup);
  setStatus('Placeholder shown — upload a .glb for the real model');
}

function loadGLB(b64) {
  if (!b64) { placeholderModel(ORG_COLOR); updatePhase(); return; }
  setStatus('Loading 3D model…');
  try {
    const bin    = atob(b64);
    const arr    = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    const blob   = new Blob([arr], { type: 'model/gltf-binary' });
    const url    = URL.createObjectURL(blob);
    new GLTFLoader().load(
      url,
      gltf => {
        clearScene();
        organGroup = gltf.scene;
        const box  = new THREE.Box3().setFromObject(organGroup);
        const size = box.getSize(new THREE.Vector3());
        const s    = 2.0 / Math.max(size.x, size.y, size.z, 0.001);
        organGroup.scale.setScalar(s);
        const ctr  = box.getCenter(new THREE.Vector3());
        organGroup.position.sub(ctr.multiplyScalar(s));
        organGroup.traverse(c => { if (c.isMesh) { c.material.clippingPlanes = []; c.material.clipShadows = true; } });
        scene.add(organGroup);
        URL.revokeObjectURL(url);
        setStatus(ORG_NAME + ' — model loaded');
        updatePhase();
      },
      xhr => { if (xhr.total) setStatus('Loading ' + Math.round(xhr.loaded/xhr.total*100) + '%…'); },
      err => { console.error(err); placeholderModel(ORG_COLOR); updatePhase(); }
    );
  } catch(e) { console.error(e); placeholderModel(ORG_COLOR); updatePhase(); }
}

function buildLandmarks(phase) {
  lmkDots.forEach(d => scene.remove(d));
  lmkDots = [];
  ivInserted = false;
  if (!phase.landmarks) return;
  phase.landmarks.forEach(lm => {
    const isInsertable = !!lm.insertable;
    const dot = new THREE.Mesh(
      new THREE.SphereGeometry(isInsertable ? 0.06 : 0.045, 16, 16),
      new THREE.MeshStandardMaterial({ color: lm.color, emissive: lm.color, emissiveIntensity: isInsertable ? 1.0 : 0.7 })
    );
    dot.position.set(lm.x, lm.y, lm.z);
    dot.visible = showLmk;
    dot.userData.label = lm.label;
    dot.userData.insertable = isInsertable;
    scene.add(dot);
    lmkDots.push(dot);
    if (isInsertable) {
      // gentle pulse ring to draw the eye to the clickable marker
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(0.09, 0.11, 32),
        new THREE.MeshBasicMaterial({ color: lm.color, transparent: true, opacity: 0.6, side: THREE.DoubleSide })
      );
      ring.position.copy(dot.position);
      ring.lookAt(cam3d.position);
      ring.userData.isPulse = true;
      scene.add(ring);
      lmkDots.push(ring);
    }
  });
}

// ── Needle insertion interaction (click/tap the red marker) ─────────────────
let ivInserted = false;
let needleMesh = null;
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

function insertNeedleAt(dot) {
  if (ivInserted) return;
  ivInserted = true;
  setStatus('Inserting… watch for flashback');

  // simple needle: thin cylinder animating in along -z toward the marker
  const geo = new THREE.CylinderGeometry(0.012, 0.012, 0.6, 12);
  const mat = new THREE.MeshStandardMaterial({ color: 0xd8d8e0, metalness: 0.8, roughness: 0.2 });
  needleMesh = new THREE.Mesh(geo, mat);
  needleMesh.rotation.x = Math.PI / 2.4; // ~15-30deg bevel-up approach angle
  const start = dot.position.clone().add(new THREE.Vector3(0.15, -0.05, 1.0));
  needleMesh.position.copy(start);
  scene.add(needleMesh);

  let t = 0;
  const anim = setInterval(() => {
    t += 0.05;
    needleMesh.position.lerpVectors(start, dot.position, Math.min(t, 1));
    if (t >= 1) {
      clearInterval(anim);
      flashback(dot);
    }
  }, 16);
}

function flashback(dot) {
  // red flashback pulse in the cannula chamber, then vein marker turns green (patent line)
  let pulses = 0;
  const orig = dot.material.color.getHex();
  const flashInt = setInterval(() => {
    dot.material.color.setHex(pulses % 2 === 0 ? 0xff2222 : orig);
    pulses++;
    if (pulses >= 6) {
      clearInterval(flashInt);
      dot.material.color.setHex(0x22c55e);
      dot.material.emissive.setHex(0x22c55e);
      setStatus('✅ Flashback confirmed — IV cannula in place');
      try { window.parent.postMessage({ medsimEvent: 'iv_inserted' }, '*'); } catch(e) {}
    }
  }, 180);
}

function onPointerDown(ev) {
  const rect = canvas3d.getBoundingClientRect();
  const cx = (ev.touches ? ev.touches[0].clientX : ev.clientX);
  const cy = (ev.touches ? ev.touches[0].clientY : ev.clientY);
  pointer.x = ((cx - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((cy - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, cam3d);
  const hits = raycaster.intersectObjects(lmkDots.filter(d => d.userData && d.userData.insertable));
  if (hits.length) insertNeedleAt(hits[0].object);
}
canvas3d.addEventListener('pointerdown', onPointerDown);

function updatePhase() {
  const p = PHASES[phaseIdx];
  if (!p) return;
  setStatus((ORG_NAME) + ' — ' + p.label + ': ' + p.instruction);
  gsap_camZ(p.cameraZ || 5);
  buildLandmarks(p);
}

window.nextPhase = () => { phaseIdx = (phaseIdx + 1) % PHASES.length; updatePhase(); };

function gsap_camZ(target) {
  const steps = 40; let i = 0;
  const ti = setInterval(() => {
    cam3d.position.z += (target - cam3d.position.z) * 0.12;
    if (++i >= steps) clearInterval(ti);
  }, 16);
}

window.toggleRotate = () => { autoRotate = !autoRotate; $('bRot').classList.toggle('on', autoRotate); };
window.toggleSection = () => {
  showSec = !showSec;
  $('bSec').classList.toggle('on', showSec);
  if (organGroup) organGroup.traverse(c => { if (c.isMesh) c.material.clippingPlanes = showSec ? [clipPlane] : []; });
};
window.toggleLandmarks = () => {
  showLmk = !showLmk;
  $('bLmk').classList.toggle('on', showLmk);
  lmkDots.forEach(d => d.visible = showLmk);
};

async function startCamera() {
  if (!GESTURES_ON) return false;
  setStatus('Requesting camera…');
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: {ideal:1280}, height:{ideal:720} }, audio:false });
    $('video').srcObject = stream;
    await new Promise(res => { $('video').onloadedmetadata = res; });
    $('video').play();
    return true;
  } catch(e) {
    showErr('Camera not available (' + e.name + '). You can still rotate/zoom with mouse or touch.');
    return false;
  }
}
$('retryBtn').onclick = () => { $('err').classList.remove('show'); startCamera(); };

let recognizer = null;
async function loadMediaPipe() {
  if (!GESTURES_ON) return false;
  setBar(10); $('lbl').textContent = 'Loading gesture AI…';
  try {
    const { GestureRecognizer, FilesetResolver } = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.8/vision_bundle.mjs');
    setBar(60);
    const fs = await FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.8/wasm');
    setBar(80);
    recognizer = await GestureRecognizer.createFromOptions(fs, {
      baseOptions: { modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task', delegate: 'GPU' },
      runningMode: 'VIDEO', numHands: 1,
      minHandDetectionConfidence: 0.35, minHandPresenceConfidence: 0.35, minTrackingConfidence: 0.35,
    });
    setBar(100);
    return true;
  } catch(e) { console.warn('Gesture AI unavailable:', e); return false; }
}

const HAND_CONNECTIONS = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[0,9],[9,10],[10,11],[11,12],[0,13],[13,14],[14,15],[15,16],[0,17],[17,18],[18,19],[19,20],[5,9],[9,13],[13,17]];
function drawHand(lms, w, h) {
  const ctx = $('cHand').getContext('2d');
  ctx.clearRect(0, 0, w, h);
  if (!lms || !lms.length) return;
  const pts = lms.map(lm => ({ x: (1 - lm.x) * w, y: lm.y * h }));
  ctx.strokeStyle = '#3a6df0'; ctx.lineWidth = 2;
  HAND_CONNECTIONS.forEach(([a, b]) => { ctx.beginPath(); ctx.moveTo(pts[a].x, pts[a].y); ctx.lineTo(pts[b].x, pts[b].y); ctx.stroke(); });
  pts.forEach((p, i) => { ctx.beginPath(); ctx.arc(p.x, p.y, i===4||i===8?7:4, 0, Math.PI*2); ctx.fillStyle = (i===4||i===8)?'#ffd400':'#a1c9f4'; ctx.fill(); });
}

function handleGesture(name, score) {
  if (cooldown > 0) { cooldown--; return; }
  const label = (name || '').toLowerCase();
  setGest(name + ' (' + Math.round(score*100) + '%)');
  if (label === 'pointing_up')  { toggleRotate();    cooldown = COOL; }
  if (label === 'victory')      { toggleSection();   cooldown = COOL; }
  if (label === 'ok')           { toggleLandmarks(); cooldown = COOL; }
  if (label === 'thumb_up')     { window.nextPhase(); cooldown = COOL; }
}

// ── Pinch-to-zoom: continuous zoom from raw thumb-tip/index-tip distance ────
// (the stock MediaPipe gesture set has no categorical "pinch" — this reads
// landmarks 4 and 8 directly for smooth, real-time zoom control.)
let pinchBaseline = null;
const PINCH_MIN = 0.02, PINCH_MAX = 0.28;   // normalised hand-space distance
const ZOOM_NEAR = 1.1, ZOOM_FAR = 6.0;

function applyPinchZoom(lms) {
  if (!lms || lms.length < 9) { pinchBaseline = null; return; }
  const dx = lms[4].x - lms[8].x, dy = lms[4].y - lms[8].y;
  const dist = Math.sqrt(dx*dx + dy*dy);
  const clamped = Math.max(PINCH_MIN, Math.min(PINCH_MAX, dist));
  const frac = (clamped - PINCH_MIN) / (PINCH_MAX - PINCH_MIN); // 0=pinched(near) .. 1=open(far)
  const targetZ = ZOOM_NEAR + frac * (ZOOM_FAR - ZOOM_NEAR);
  cam3d.position.z += (targetZ - cam3d.position.z) * 0.15;
}

let lastTs = 0;
function loop(ts) {
  requestAnimationFrame(loop);
  if (autoRotate && organGroup) organGroup.rotation.y += 0.008;
  lmkDots.forEach(o => { if (o.userData && o.userData.isPulse) { o.lookAt(cam3d.position); o.scale.setScalar(1 + 0.15*Math.sin(ts/250)); } });
  controls.update();
  renderer.render(scene, cam3d);
  if (recognizer && $('video').readyState >= 2 && ts - lastTs > 100) {
    lastTs = ts;
    try {
      const res = recognizer.recognizeForVideo($('video'), ts);
      const lms = res.landmarks?.[0];
      drawHand(lms, $('cHand').width, $('cHand').height);
      applyPinchZoom(lms);
      if (res.gestures?.[0]?.[0]) { const g = res.gestures[0][0]; handleGesture(g.categoryName, g.score); }
    } catch(e) {}
  }
}

async function boot() {
  const [mpOk, camOk] = await Promise.all([loadMediaPipe(), startCamera()]);
  hideLoad();
  loadGLB(GLB_B64);
  setStatus(mpOk ? 'Ready — gestures + mouse/touch enabled' : 'Ready — drag to rotate, scroll to zoom');
  loop(0);
}
boot();
</script>
</body>
</html>
"""


def render_anatomy_explorer(organ_key: str = "🩸 Forearm / Vein Access", phase_label: str = None,
                             height: int = 560, enable_gestures: bool = True, key: str = "anatomy"):
    """Streamlit helper: renders the organ selector + phase buttons + the
    embedded Three.js viewer. Call this directly from any hospital room."""
    organ = ORGANS.get(organ_key, list(ORGANS.values())[0])
    phases = organ["phases"]
    phase_labels = [p["label"] for p in phases]

    state_key = f"medsim_anatomy_phase_{key}"
    if phase_label and phase_label in phase_labels:
        st.session_state[state_key] = phase_labels.index(phase_label)
    phase_idx = st.session_state.get(state_key, 0)

    cols = st.columns(len(phase_labels))
    for i, (col, label) in enumerate(zip(cols, phase_labels)):
        with col:
            if st.button(("✅ " if i == phase_idx else "") + label, key=f"{key}_ph_{i}", use_container_width=True):
                st.session_state[state_key] = i
                phase_idx = i

    st.caption(f"🔬 {phases[phase_idx]['instruction']}")
    html = build_anatomy_html(organ_key, phase_idx=phase_idx, enable_gestures=enable_gestures)
    components.html(html, height=height, scrolling=False)

    current_phase = phases[phase_idx]
    has_insertable = any(lm.get("insertable") for lm in current_phase.get("landmarks", []))
    if has_insertable:
        st.caption("Once you see '✅ Flashback confirmed' on screen, confirm below to record the skill.")
        if st.button("✅ Confirm IV Inserted", key=f"{key}_confirm_iv"):
            st.session_state[f"{key}_iv_done"] = True
            st.success("IV access recorded.")
