"""
procedure_3d_viewer.py  —  Base 3D Procedure Viewer
────────────────────────────────────────────────────────────────────────────
Provides _build_3d_html(proc_name, step_idx) → complete self-contained HTML.

The guided wrapper (procedure_3d_viewer_guided.py) imports _build_3d_html
from this module and injects its simulation layer on top.

Supported procedures with 3D interactivity:
  • IV Cannulation
  • ABG Sampling

All other procedures show a reference view with anatomical labels.
No GLB files required — anatomy is fully procedural (Three.js primitives).
"""

import json


# ── Per-procedure config ───────────────────────────────────────────────────────
_PROC_CONFIG = {
    "IV Cannulation": {
        "subtitle":   "Peripheral Intravenous Cannula Insertion",
        "site":       "Dorsum of hand / antecubital fossa",
        "instruments": [
            ("tourniquet", "🩸 Tourniquet"),
            ("swab",       "🧼 Antiseptic Swab"),
            ("needle",     "💉 Needle (21G)"),
            ("cannula",    "🩹 Cannula / Stylet"),
            ("flush",      "💊 Saline Flush"),
        ],
        "steps": 6,
        "hint":  "Apply tourniquet → clean site → insert needle at 15° bevel-up → advance on flashback → slide cannula → flush.",
        "anatomy": "forearm",
        "veins":   True,
    },
    "ABG Sampling": {
        "subtitle":   "Arterial Blood Gas Sampling",
        "site":       "Radial artery at wrist",
        "instruments": [
            ("swab",    "🧼 Antiseptic Swab"),
            ("needle",  "💉 ABG Needle (23G)"),
            ("syringe", "🧪 Heparinised Syringe"),
            ("cap",     "🔴 Needle Cap"),
        ],
        "steps": 4,
        "hint":  "Perform Allen's test → clean site → palpate radial pulse → insert at 45° → allow arterial fill → withdraw → cap.",
        "anatomy": "wrist",
        "veins":   False,
    },
}

_DEFAULT_CONFIG = {
    "subtitle":    "Clinical Procedure Simulation",
    "site":        "See procedure guide",
    "instruments": [("tool", "🔧 Instrument")],
    "steps":       1,
    "hint":        "Follow the on-screen steps to complete the procedure.",
    "anatomy":     "generic",
    "veins":       False,
}


def _build_3d_html(proc_name: str, step_idx: int) -> str:
    """
    Return a complete self-contained HTML page for the given procedure.
    The guided wrapper injects its layer by searching for specific markers:
      </style>  |  <div class="drag-hint">  |  <!-- Anatomy hint -->  |  </body></html>
    """
    cfg   = _PROC_CONFIG.get(proc_name, _DEFAULT_CONFIG)
    steps = cfg["steps"]
    step_label = f"Step {step_idx + 1} of {steps}"

    # Serialise instrument list for JS
    instr_js = json.dumps([
        {"key": k, "label": lbl} for k, lbl in cfg["instruments"]
    ])
    has_veins  = "true" if cfg["veins"] else "false"
    anatomy    = cfg["anatomy"]
    site_text  = cfg["site"]
    hint_text  = cfg["hint"]
    subtitle   = cfg["subtitle"]

    # Build instrument tray HTML
    tray_html = ""
    for key, label in cfg["instruments"]:
        special = ' data-i="cannula"' if key == "cannula" else f' data-i="{key}"'
        # The guided wrapper searches for exactly this cannula string — keep format identical
        if key == "cannula":
            tray_html += (
                f'<div class="instr" data-i="cannula">'
                f'🩹 Cannula / Stylet<span class="arr">&#9654;</span></div>\n'
            )
        else:
            tray_html += (
                f'<div class="instr" data-i="{key}">'
                f'{label}<span class="arr">&#9654;</span></div>\n'
            )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{proc_name} — 3D Viewer</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<style>
/* ══════════════════════════════════════════════════
   BASE VIEWER STYLES
   ══════════════════════════════════════════════════ */
* {{ margin:0; padding:0; box-sizing:border-box; }}

html, body {{
    width:100%; height:100%;
    background:#07101e;
    font-family: system-ui, -apple-system, sans-serif;
    overflow: hidden;
    color: #c8dff0;
    user-select: none;
}}

/* ── Canvas wrapper ── */
#canvasWrap {{
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
}}
canvas {{
    display: block;
    touch-action: none;
}}

/* ── Header bar ── */
#header {{
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 38px;
    background: rgba(5,12,26,.95);
    border-bottom: 1px solid #0d2a45;
    display: flex;
    align-items: center;
    padding: 0 12px;
    gap: 10px;
    z-index: 30;
}}
#hTitle {{
    font-size: 13px;
    font-weight: 700;
    color: #e0f0ff;
    letter-spacing: .03em;
}}
#hSub {{
    font-size: 10px;
    color: #4a7090;
    flex: 1;
}}
#hStep {{
    font-size: 10px;
    font-weight: 600;
    color: #2d8fff;
    background: rgba(45,143,255,.12);
    border: .5px solid rgba(45,143,255,.3);
    border-radius: 10px;
    padding: 2px 9px;
}}
#resetBtn {{
    font-size: 10px;
    color: #4a7090;
    background: rgba(255,255,255,.04);
    border: .5px solid #1a3050;
    border-radius: 6px;
    padding: 3px 9px;
    cursor: pointer;
    transition: all .15s;
}}
#resetBtn:hover {{ color:#7ec8ff; border-color:#2d6090; }}

/* ── Instrument tray ── */
#tray {{
    position: absolute;
    top: 48px; right: 10px;
    width: 170px;
    background: rgba(5,12,26,.96);
    border: 1px solid #0d2a45;
    border-radius: 10px;
    padding: 8px 6px;
    z-index: 20;
    max-height: 82vh;
    overflow-y: auto;
}}
#trayTitle {{
    font-size: 9px;
    font-weight: 700;
    color: #2d6090;
    text-transform: uppercase;
    letter-spacing: .12em;
    margin-bottom: 6px;
    padding: 0 4px;
}}
.instr {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 7px 9px;
    border-radius: 7px;
    font-size: 11px;
    font-weight: 500;
    color: #8aaabb;
    cursor: pointer;
    transition: all .18s;
    border: .5px solid transparent;
    margin-bottom: 3px;
}}
.instr:hover {{
    background: rgba(45,100,180,.18);
    color: #aaccee;
    border-color: rgba(45,100,180,.3);
}}
.instr.sel {{
    background: rgba(45,143,255,.22);
    color: #7ec8ff;
    border-color: rgba(45,143,255,.5);
}}
.instr.placed {{
    background: rgba(0,150,80,.15);
    color: #00c060;
    border-color: rgba(0,150,80,.3);
    cursor: default;
}}
.arr {{
    font-size: 8px;
    color: #2d5070;
}}
.instr.sel .arr {{ color: #2d8fff; }}
.instr.placed .arr {{ color: #00a050; }}

/* ── Place hint banner ── */
#placeHint {{
    position: absolute;
    bottom: 54px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(45,143,255,.18);
    border: .5px solid rgba(45,143,255,.45);
    border-radius: 8px;
    padding: 6px 16px;
    font-size: 11px;
    color: #7ec8ff;
    z-index: 20;
    display: none;
    pointer-events: none;
    white-space: nowrap;
}}
body.placing #placeHint {{ display: block; }}

/* ── Drag hint ── */
<div class="drag-hint" style="display:none"></div>
.drag-hint-bar {{
    position: absolute;
    bottom: 10px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 9.5px;
    color: #2a4a6a;
    background: rgba(5,12,26,.7);
    border: .5px solid #0d2040;
    border-radius: 10px;
    padding: 3px 12px;
    pointer-events: none;
    z-index: 10;
    white-space: nowrap;
}}

/* ── Feedback toast ── */
#feedback {{
    position: absolute;
    bottom: 34px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(5,14,28,.95);
    border: 1px solid #1a4060;
    border-radius: 8px;
    padding: 7px 16px;
    font-size: 11px;
    color: #7aaabb;
    z-index: 25;
    max-width: 75%;
    text-align: center;
    pointer-events: none;
    opacity: 0;
    transition: opacity .3s;
}}

/* ── Anatomy hint (will be replaced by guided panel) ── */
#anatHintWrap {{
    position: absolute;
    right: 10px;
    bottom: 34px;
    z-index: 15;
}}

/* ── Highlight pulse animation ── */
@keyframes hlPulse {{
    0%,100% {{ opacity:.7; }}
    50%      {{ opacity:1; }}
}}
</style>
</head>
<body>

<!-- Header bar -->
<div id="header">
  <div id="hTitle">💉 {proc_name}</div>
  <div id="hSub">{subtitle}</div>
  <div id="hStep">{step_label}</div>
  <div id="resetBtn" onclick="resetScene()">↺ Reset</div>
</div>

<!-- Canvas wrapper -->
<div id="canvasWrap">
  <canvas id="c"></canvas>
</div>

<!-- Instrument tray -->
<div id="tray">
  <div id="trayTitle">Instruments</div>
  {tray_html}
</div>

<!-- Place hint -->
<span id="placeHint">Click on the model to place</span>

<!-- Anatomy hint (replaced by guided panel in v4) -->
<!-- Anatomy hint -->
<div id="anatHintWrap">
  <div style="background:rgba(5,12,26,.9);border:.5px solid #0d2a45;border-radius:8px;
              padding:8px 11px;font-size:10px;color:#4a7090;max-width:180px;">
    <div style="color:#2d6090;font-size:8.5px;text-transform:uppercase;
                letter-spacing:.1em;margin-bottom:4px;">📍 Site</div>
    {site_text}
    <div style="color:#2d6090;font-size:8.5px;text-transform:uppercase;
                letter-spacing:.1em;margin:6px 0 4px;">💡 Technique</div>
    <div style="color:#3a6a7a;font-size:9.5px;line-height:1.5;">{hint_text}</div>
  </div>
</div>
<!-- /Anatomy hint -->

<!-- Feedback toast -->
<div id="feedback"></div>

<!-- Drag hint (marker for guided wrapper injection) -->
<div class="drag-hint">
  <div class="drag-hint-bar">Drag to rotate · Scroll to zoom</div>
</div>

<!-- Completion overlay placeholder (filled by guided wrapper) -->
<div id="completeOverlay"></div>

<script>
/* ══════════════════════════════════════════════════════════════════════
   BASE 3D VIEWER  —  Three.js r128
   All globals referenced by procedure_3d_viewer_guided.py are defined here.
   ══════════════════════════════════════════════════════════════════════ */

/* ── Canvas / Renderer ───────────────────────────────────────────── */
const canvas   = document.getElementById('c');
const canvasWrap = document.getElementById('canvasWrap');

let W = canvasWrap.clientWidth  || window.innerWidth;
let H = canvasWrap.clientHeight || window.innerHeight - 38;
canvas.width  = W;
canvas.height = H;

const renderer = new THREE.WebGLRenderer({{ canvas, antialias: true, alpha: false }});
renderer.setSize(W, H);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type    = THREE.PCFSoftShadowMap;
renderer.physicallyCorrectLights = true;
renderer.outputEncoding    = THREE.sRGBEncoding;
renderer.toneMapping       = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;

/* ── Scene ───────────────────────────────────────────────────────── */
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x07101e);
scene.fog = new THREE.FogExp2(0x07101e, 0.18);

/* ── Camera ──────────────────────────────────────────────────────── */
const camera = new THREE.PerspectiveCamera(38, W / H, 0.01, 40);
camera.position.set(0, 0.3, 1.5);
camera.lookAt(0, 0, 0);

/* ── Lights ──────────────────────────────────────────────────────── */
const hemi = new THREE.HemisphereLight(0xfff4e8, 0x0d2040, 0.6);
scene.add(hemi);

const keyL = new THREE.DirectionalLight(0xfff8f0, 2.0);
keyL.position.set(1.5, 2.5, 1.5);
keyL.castShadow = true;
keyL.shadow.mapSize.set(1024, 1024);
keyL.shadow.camera.near = 0.1;
keyL.shadow.camera.far  = 10;
keyL.shadow.camera.left = keyL.shadow.camera.bottom = -1;
keyL.shadow.camera.right = keyL.shadow.camera.top   =  1;
scene.add(keyL);

const fillL = new THREE.DirectionalLight(0xc8e0ff, 0.7);
fillL.position.set(-1.5, 0.5, 1);
scene.add(fillL);

const rimL = new THREE.DirectionalLight(0x2040a0, 0.4);
rimL.position.set(0, -1, -2);
scene.add(rimL);

/* ── Model root (all anatomy lives here, gets reset on resetScene) ── */
let modelRoot = new THREE.Group();
scene.add(modelRoot);

/* ── Anatomy colours ─────────────────────────────────────────────── */
const MAT = {{
    skin:    new THREE.MeshPhysicalMaterial({{ color:0xd4825a, roughness:.75, metalness:.02,
                 subsurfaceScattering:true }}),
    skinPale:new THREE.MeshPhysicalMaterial({{ color:0xc27550, roughness:.8,  metalness:.02 }}),
    vein:    new THREE.MeshPhysicalMaterial({{ color:0x204880, roughness:.6,  metalness:.05,
                 transparent:true, opacity:.82 }}),
    artery:  new THREE.MeshPhysicalMaterial({{ color:0x8c1a1a, roughness:.5,  metalness:.04 }}),
    bone:    new THREE.MeshPhysicalMaterial({{ color:0xeee8d5, roughness:.85, metalness:.0  }}),
    tendon:  new THREE.MeshPhysicalMaterial({{ color:0xd4c090, roughness:.9,  metalness:.0  }}),
}};

/* ── Build anatomy for the procedure ─────────────────────────────── */
const ANATOMY_TYPE = "{anatomy}";
const HAS_VEINS    = {has_veins};

function buildAnatomy() {{
    modelRoot.clear();

    if (ANATOMY_TYPE === 'forearm') {{
        buildForearm();
    }} else if (ANATOMY_TYPE === 'wrist') {{
        buildWrist();
    }} else {{
        buildGeneric();
    }}
}}

/* ── Forearm / hand (IV Cannulation) ────────────────────────────── */
function buildForearm() {{
    /* Forearm cylinder */
    const armG = new THREE.CylinderGeometry(.115, .10, 0.82, 20, 4, false);
    const arm  = new THREE.Mesh(armG, MAT.skin.clone());
    arm.rotation.x = Math.PI / 2;
    arm.castShadow = arm.receiveShadow = true;
    arm.name = 'skin';
    modelRoot.add(arm);

    /* Wrist taper */
    const wristG = new THREE.CylinderGeometry(.085, .115, 0.18, 16, 1);
    const wrist  = new THREE.Mesh(wristG, MAT.skin.clone());
    wrist.rotation.x = Math.PI / 2;
    wrist.position.z = -0.5;
    wrist.castShadow = true;
    wrist.name = 'skin';
    modelRoot.add(wrist);

    /* Hand dorsum (flattened sphere) */
    const handG = new THREE.SphereGeometry(.14, 16, 12);
    const hand  = new THREE.Mesh(handG, MAT.skin.clone());
    hand.scale.set(1, .55, .85);
    hand.position.set(0, 0, -0.72);
    hand.castShadow = true;
    hand.name = 'skin';
    modelRoot.add(hand);

    /* Fingers (simple rounded cylinders) */
    const fingerPositions = [[-0.09,-0.01,-0.88],[-.03,0.01,-0.90],[.03,0.01,-0.91],[.09,-0.01,-0.89]];
    fingerPositions.forEach(([x,y,z]) => {{
        const fg = new THREE.CylinderGeometry(.018,.015,.18,8);
        const f  = new THREE.Mesh(fg, MAT.skin.clone());
        f.position.set(x,y,z);
        f.rotation.x = Math.PI/2;
        f.castShadow = true;
        f.name = 'skin';
        modelRoot.add(f);
    }});

    /* Thumb */
    const thumbG = new THREE.CylinderGeometry(.022,.016,.14,8);
    const thumb  = new THREE.Mesh(thumbG, MAT.skin.clone());
    thumb.position.set(-.16,.03,-0.62);
    thumb.rotation.set(Math.PI/2, 0, -0.5);
    thumb.name = 'skin';
    modelRoot.add(thumb);

    /* Radius bone (hint) */
    const radG = new THREE.CylinderGeometry(.022,.022,.80,8);
    const rad  = new THREE.Mesh(radG, MAT.bone);
    rad.rotation.x = Math.PI/2;
    rad.position.set(.055, -.04, 0);
    rad.name = 'bone';
    modelRoot.add(rad);

    /* Ulna bone */
    const ulnaG = new THREE.CylinderGeometry(.018,.018,.80,8);
    const ulna  = new THREE.Mesh(ulnaG, MAT.bone);
    ulna.rotation.x = Math.PI/2;
    ulna.position.set(-.06, -.04, 0);
    ulna.name = 'bone';
    modelRoot.add(ulna);

    /* Surface tendons */
    const tendons = [[.02,-.01],[-.02,-.01],[.06,-.02],[-.055,-.02]];
    tendons.forEach(([x,y]) => {{
        const tg = new THREE.CylinderGeometry(.007,.006,.85,6);
        const t  = new THREE.Mesh(tg, MAT.tendon);
        t.rotation.x = Math.PI/2;
        t.position.set(x, y+.11, 0);
        t.name = 'tendon';
        modelRoot.add(t);
    }});

    /* Veins — dorsal venous arch */
    if (HAS_VEINS) {{
        buildForearmVeins();
    }}

    /* Mesh registry for LAYERS */
    _buildLayerRegistry();
}}

/* Dorsal veins ─────────────────────────────────────────────────── */
let _veinMeshes = [];

function buildForearmVeins() {{
    _veinMeshes = [];

    /* Cephalic vein (radial / thumb side) */
    const ceph = _veinTube(
        [new THREE.Vector3(.09,.11,-.75), new THREE.Vector3(.10,.11,-.4),
         new THREE.Vector3(.105,.11,.05), new THREE.Vector3(.10,.10,.41)],
        0.013, 'vein_cephalic'
    );
    modelRoot.add(ceph);
    _veinMeshes.push(ceph);

    /* Basilic vein (ulnar / little finger side) */
    const basi = _veinTube(
        [new THREE.Vector3(-.09,.11,-.70), new THREE.Vector3(-.10,.11,-.38),
         new THREE.Vector3(-.105,.11,.04), new THREE.Vector3(-.10,.10,.40)],
        0.012, 'vein_basilic'
    );
    modelRoot.add(basi);
    _veinMeshes.push(basi);

    /* Median cubital vein (connects the two) */
    const medCub = _veinTube(
        [new THREE.Vector3(.095,.11,.28), new THREE.Vector3(.04,.115,.32),
         new THREE.Vector3(-.04,.115,.32), new THREE.Vector3(-.095,.11,.28)],
        0.010, 'vein_median_cubital'
    );
    modelRoot.add(medCub);
    _veinMeshes.push(medCub);

    /* Small dorsal metacarpal veins */
    [[-0.06,-.72],[-.02,-.74],[.02,-.74],[.06,-.72]].forEach(([x,z], i) => {{
        const v = _veinTube(
            [new THREE.Vector3(x,.103,z+.02), new THREE.Vector3(x,.103,z+.18)],
            0.006, 'vein_dorsal_' + i
        );
        modelRoot.add(v);
        _veinMeshes.push(v);
    }});

    /* Add subtle pulsing highlight to cephalic for interaction affordance */
    _highlightVein(ceph);
}}

function _veinTube(points, r, name) {{
    const curve = new THREE.CatmullRomCurve3(points);
    const geo   = new THREE.TubeGeometry(curve, 24, r, 6, false);
    const mat   = MAT.vein.clone();
    const mesh  = new THREE.Mesh(geo, mat);
    mesh.name   = name;
    mesh.castShadow = true;
    return mesh;
}}

let _hlInterval = null;
function _highlightVein(mesh) {{
    if (_hlInterval) clearInterval(_hlInterval);
    let t = 0;
    _hlInterval = setInterval(() => {{
        t += 0.06;
        const pulse = 0.5 + 0.5 * Math.sin(t);
        mesh.material.emissive = new THREE.Color(0, 0.04 * pulse, 0.12 * pulse);
        mesh.material.needsUpdate = true;
    }}, 33);
}}

/* ── Wrist (ABG) ─────────────────────────────────────────────────── */
function buildWrist() {{
    /* Wrist / forearm stub */
    const wG = new THREE.CylinderGeometry(.088,.10,.60,18,3);
    const w  = new THREE.Mesh(wG, MAT.skinPale.clone());
    w.rotation.x = Math.PI/2;
    w.castShadow = w.receiveShadow = true;
    w.name = 'skin';
    modelRoot.add(w);

    /* Radius bone hint */
    const rG = new THREE.CylinderGeometry(.020,.020,.65,8);
    const r  = new THREE.Mesh(rG, MAT.bone);
    r.rotation.x = Math.PI/2;
    r.position.set(.048,-.04, 0);
    r.name = 'bone';
    modelRoot.add(r);

    /* Radial artery */
    const artery = _veinTube(
        [new THREE.Vector3(.045,.088,-.28), new THREE.Vector3(.046,.09,.0),
         new THREE.Vector3(.045,.089,.28)],
        0.010, 'radial_artery'
    );
    artery.material = MAT.artery.clone();
    artery.material.emissive = new THREE.Color(0.15, 0, 0);
    modelRoot.add(artery);
    _veinMeshes.push(artery);

    _highlightVein(artery);
    _buildLayerRegistry();
}}

/* ── Generic ─────────────────────────────────────────────────────── */
function buildGeneric() {{
    const g = new THREE.SphereGeometry(.3, 16, 12);
    const m = new THREE.Mesh(g, MAT.skin.clone());
    m.name = 'skin';
    m.castShadow = true;
    modelRoot.add(m);
    _buildLayerRegistry();
}}

/* ── LAYERS registry (used by guided wrapper for vein engorgement) ── */
const LAYERS = {{
    skin:    {{ meshes: [] }},
    vessels: {{ meshes: [] }},
    bone:    {{ meshes: [] }},
    tendon:  {{ meshes: [] }},
}};

function _buildLayerRegistry() {{
    LAYERS.skin.meshes    = [];
    LAYERS.vessels.meshes = [];
    LAYERS.bone.meshes    = [];
    LAYERS.tendon.meshes  = [];

    modelRoot.traverse(obj => {{
        if (!(obj instanceof THREE.Mesh)) return;
        const n = obj.name || '';
        if (n.startsWith('vein') || n.startsWith('radial_artery') || n.startsWith('artery')) {{
            LAYERS.vessels.meshes.push(obj);
        }} else if (n === 'bone') {{
            LAYERS.bone.meshes.push(obj);
        }} else if (n === 'tendon') {{
            LAYERS.tendon.meshes.push(obj);
        }} else {{
            LAYERS.skin.meshes.push(obj);
        }}
    }});
}}

/* Build anatomy on startup */
buildAnatomy();

/* ── Placed instruments state ────────────────────────────────────── */
const placed = {{}};   // key → THREE.Object3D

/* ── Instrument mode ─────────────────────────────────────────────── */
let instrMode = null;

/* ── Needle animation state (watched by guided wrapper) ──────────── */
const needleAnim = {{ flashed: false, inserted: false }};

/* ── Preview ghost ───────────────────────────────────────────────── */
const preview = {{ group: null, key: null }};

function removePreview() {{
    if (preview.group) {{
        scene.remove(preview.group);
        preview.group = null;
        preview.key   = null;
    }}
}}

/* ── Feedback toast ──────────────────────────────────────────────── */
let _fbTimer = null;
function showFB(msg, ms) {{
    const el = document.getElementById('feedback');
    el.innerHTML = msg;
    el.style.opacity = '1';
    if (_fbTimer) clearTimeout(_fbTimer);
    _fbTimer = setTimeout(() => {{ el.style.opacity = '0'; }}, ms || 3500);
}}

/* ── Set instrument mode ─────────────────────────────────────────── */
function setMode(key) {{
    instrMode = key;
    document.querySelectorAll('.instr').forEach(el => el.classList.remove('sel'));
    if (key) {{
        const el = document.querySelector(`.instr[data-i="${{key}}"]`);
        if (el) el.classList.add('sel');
        document.getElementById('placeHint').style.display = 'block';
        document.body.classList.add('placing');
    }} else {{
        document.getElementById('placeHint').style.display = 'none';
        document.body.classList.remove('placing');
    }}
}}

/* ── Instrument click handlers ───────────────────────────────────── */
document.querySelectorAll('.instr').forEach(el => {{
    el.addEventListener('click', () => {{
        const key = el.dataset.i;
        if (el.classList.contains('placed')) return;
        if (instrMode === key) {{
            /* Deselect */
            instrMode = null;
            el.classList.remove('sel');
            document.body.classList.remove('placing');
            removePreview();
            return;
        }}
        setMode(key);
        buildPreviewGroup(key);
    }});
}});

/* ── Raycaster ───────────────────────────────────────────────────── */
const raycaster = new THREE.Raycaster();
const _mouse    = new THREE.Vector2();

function _getPointer(e) {{
    const rect = canvas.getBoundingClientRect();
    const cx   = (e.touches ? e.touches[0].clientX : e.clientX);
    const cy   = (e.touches ? e.touches[0].clientY : e.clientY);
    return new THREE.Vector2(
        ((cx - rect.left) / rect.width)  * 2 - 1,
        -((cy - rect.top)  / rect.height) * 2 + 1
    );
}}

/* ── Coordinate helpers ──────────────────────────────────────────── */
function toLocal(worldPoint) {{
    return modelRoot.worldToLocal(worldPoint.clone());
}}

function toLocalDir(worldDir) {{
    const mat3 = new THREE.Matrix3().getNormalMatrix(modelRoot.matrixWorld).invert();
    return worldDir.clone().applyMatrix3(mat3).normalize();
}}

/* ── Build preview ghost for instrument ─────────────────────────── */
function buildPreviewGroup(key) {{
    removePreview();
    const g = new THREE.Group();

    const ghostMat = new THREE.MeshPhysicalMaterial({{
        color: 0x5a9fff,
        transparent: true,
        opacity: 0.45,
        depthWrite: false,
    }});

    if (key === 'tourniquet') {{
        const ring = new THREE.Mesh(
            new THREE.TorusGeometry(.12, .012, 8, 24),
            ghostMat.clone()
        );
        ring.rotation.x = Math.PI / 2;
        g.add(ring);
    }} else if (key === 'swab') {{
        const pad = new THREE.Mesh(
            new THREE.BoxGeometry(.08, .005, .08),
            ghostMat.clone()
        );
        g.add(pad);
    }} else if (key === 'needle' || key === 'syringe') {{
        const barrel = new THREE.Mesh(
            new THREE.CylinderGeometry(.008, .008, .20, 8),
            ghostMat.clone()
        );
        barrel.rotation.z = Math.PI / 2;
        g.add(barrel);
        const tip = new THREE.Mesh(
            new THREE.ConeGeometry(.005, .04, 6),
            new THREE.MeshPhysicalMaterial({{ color:0xaaaacc, transparent:true, opacity:.6 }})
        );
        tip.rotation.z = -Math.PI / 2;
        tip.position.x = .12;
        g.add(tip);
    }} else if (key === 'cannula') {{
        const c = new THREE.Mesh(
            new THREE.CylinderGeometry(.009, .009, .15, 8),
            ghostMat.clone()
        );
        c.rotation.z = Math.PI / 2;
        g.add(c);
    }} else if (key === 'flush') {{
        const f = new THREE.Mesh(
            new THREE.CylinderGeometry(.018, .018, .14, 10),
            ghostMat.clone()
        );
        g.add(f);
    }} else {{
        const def = new THREE.Mesh(
            new THREE.SphereGeometry(.05, 8, 6),
            ghostMat.clone()
        );
        g.add(def);
    }}

    scene.add(g);
    preview.group = g;
    preview.key   = key;
}}

/* ── Place instrument at hit point ───────────────────────────────── */
function placeInstr(hit, allHits) {{
    if (!instrMode) return;
    const key = instrMode;
    const lp  = toLocal(hit.point);
    const wn  = hit.face ? hit.face.normal.clone().transformDirection(hit.object.matrixWorld)
                         : new THREE.Vector3(0,1,0);
    const ln  = toLocalDir(wn);

    /* Remove old placement */
    if (placed[key] && modelRoot) modelRoot.remove(placed[key]);

    let obj = null;

    if (key === 'tourniquet') {{
        const g = new THREE.Group();
        const ring = new THREE.Mesh(
            new THREE.TorusGeometry(.13, .013, 8, 28),
            new THREE.MeshPhysicalMaterial({{ color:0xcc4444, roughness:.7 }})
        );
        ring.rotation.x = Math.PI / 2;
        g.add(ring);
        g.position.copy(lp);
        obj = g;
        showFB('🩸 Tourniquet applied. Now clean the site.', 3500);
    }} else if (key === 'swab') {{
        const pad = new THREE.Mesh(
            new THREE.BoxGeometry(.075, .004, .075),
            new THREE.MeshPhysicalMaterial({{ color:0xeeeedd, roughness:.9, transparent:true, opacity:.85 }})
        );
        pad.position.copy(lp);
        pad.position.addScaledVector(ln, .005);
        obj = pad;
        showFB('🧼 Site cleaned with chlorhexidine. Allow 30 s to dry.', 3500);
    }} else if (key === 'needle') {{
        const g = new THREE.Group();
        const barrel = new THREE.Mesh(
            new THREE.CylinderGeometry(.007,.007,.18,8),
            new THREE.MeshPhysicalMaterial({{ color:0xccccdd, roughness:.3, metalness:.5 }})
        );
        barrel.rotation.z = Math.PI / 2;
        barrel.position.x = .06;
        g.add(barrel);
        const tip = new THREE.Mesh(
            new THREE.ConeGeometry(.004,.035,6),
            new THREE.MeshPhysicalMaterial({{ color:0xddddee, roughness:.2, metalness:.8 }})
        );
        tip.rotation.z = -Math.PI / 2;
        tip.position.x = .165;
        g.add(tip);
        /* Flashback chamber */
        const fb = new THREE.Mesh(
            new THREE.CylinderGeometry(.011,.011,.03,8),
            new THREE.MeshPhysicalMaterial({{ color:0xffffff, transparent:true, opacity:.7 }})
        );
        fb.rotation.z = Math.PI/2;
        fb.position.x = -.04;
        g.add(fb);
        g.name = 'needle_group';
        g.position.copy(lp);
        /* Tilt at 15° to skin surface */
        g.quaternion.setFromUnitVectors(new THREE.Vector3(1,0,0), ln.clone().negate());
        g.rotateZ(-0.26); /* ~15° */
        obj = g;

        /* Simulate needle insertion and flashback after delay */
        setTimeout(() => {{
            fb.material.color.setHex(0xcc0000);
            fb.material.opacity = .85;
            needleAnim.flashed  = true;
            showFB('🔴 Flashback — blood in chamber! Advance 2-3 mm then slide cannula.', 4000);
            setTimeout(() => {{ needleAnim.inserted = true; }}, 1200);
        }}, 1800);
        showFB('💉 Needle inserted at 15°. Watch for flashback...', 2000);
    }} else if (key === 'cannula') {{
        const g = new THREE.Group();
        const tube = new THREE.Mesh(
            new THREE.CylinderGeometry(.009,.009,.12,8),
            new THREE.MeshPhysicalMaterial({{ color:0x88ccee, transparent:true, opacity:.8, roughness:.1 }})
        );
        tube.rotation.z = Math.PI/2;
        tube.position.x = .04;
        g.add(tube);
        const hub = new THREE.Mesh(
            new THREE.CylinderGeometry(.016,.013,.025,10),
            new THREE.MeshPhysicalMaterial({{ color:0x3366cc, roughness:.5 }})
        );
        hub.rotation.z = Math.PI/2;
        hub.position.x = -.01;
        g.add(hub);
        g.position.copy(lp);
        if (placed.needle) {{
            g.position.copy(placed.needle.position);
            g.quaternion.copy(placed.needle.quaternion);
        }}
        obj = g;
        /* Retract needle visual */
        if (placed.needle && modelRoot) {{
            modelRoot.remove(placed.needle);
            delete placed.needle;
        }}
        showFB('🩹 Cannula advanced. Apply tourniquet release and connect IV line.', 4000);
    }} else if (key === 'flush') {{
        const g = new THREE.Group();
        const body = new THREE.Mesh(
            new THREE.CylinderGeometry(.017,.017,.13,10),
            new THREE.MeshPhysicalMaterial({{ color:0xcceeee, transparent:true, opacity:.75, roughness:.1 }})
        );
        g.add(body);
        const plunger = new THREE.Mesh(
            new THREE.CylinderGeometry(.014,.014,.06,8),
            new THREE.MeshPhysicalMaterial({{ color:0xffffff, roughness:.8 }})
        );
        plunger.position.y = .095;
        g.add(plunger);
        if (placed.cannula) {{
            g.position.copy(placed.cannula.position);
        }} else {{
            g.position.copy(lp);
        }}
        obj = g;
        showFB('💊 Flushing with 0.9% saline — push-pause technique. Secure with dressing.', 4000);
    }} else if (key === 'syringe') {{
        const g = new THREE.Group();
        const body = new THREE.Mesh(
            new THREE.CylinderGeometry(.018,.018,.16,10),
            new THREE.MeshPhysicalMaterial({{ color:0xddeeee, transparent:true, opacity:.8, roughness:.1 }})
        );
        g.add(body);
        g.rotation.z = Math.PI / 2;
        g.position.copy(lp);
        obj = g;
        showFB('🧪 ABG sample collecting — allow arterial pressure to fill syringe.', 4000);
    }} else {{
        const def = new THREE.Mesh(
            new THREE.SphereGeometry(.04, 8, 6),
            new THREE.MeshPhysicalMaterial({{ color:0x88aacc, roughness:.6 }})
        );
        def.position.copy(lp);
        obj = def;
        showFB('✅ Instrument placed.', 2500);
    }}

    if (obj) {{
        modelRoot.add(obj);
        placed[key] = obj;
    }}

    /* Reset instrument mode */
    instrMode = null;
    removePreview();
    document.querySelectorAll('.instr').forEach(el => el.classList.remove('sel'));
    document.getElementById('placeHint').style.display = 'none';
    document.body.classList.remove('placing');

    /* Mark as placed in tray */
    const trayEl = document.querySelector(`.instr[data-i="${{key}}"]`);
    if (trayEl) trayEl.classList.add('placed');
}}

/* ── Canvas click: raycast and place ────────────────────────────── */
canvas.addEventListener('click', e => {{
    if (_orbitActive) return;   /* suppress if just finished dragging */
    const ptr = _getPointer(e);
    raycaster.setFromCamera(ptr, camera);

    /* Collect all skin/vessel meshes as placement targets */
    const targets = [];
    modelRoot.traverse(obj => {{ if (obj instanceof THREE.Mesh) targets.push(obj); }});

    const hits = raycaster.intersectObjects(targets, false);
    if (hits.length && instrMode) {{
        placeInstr(hits[0], hits);
    }}
}});

/* Mouse move: update preview ghost position */
canvas.addEventListener('mousemove', e => {{
    if (!preview.group || !instrMode) return;
    const ptr = _getPointer(e);
    raycaster.setFromCamera(ptr, camera);
    const targets = [];
    modelRoot.traverse(obj => {{ if (obj instanceof THREE.Mesh) targets.push(obj); }});
    const hits = raycaster.intersectObjects(targets, false);
    if (hits.length) {{
        const lp = toLocal(hits[0].point);
        preview.group.position.copy(lp);
        const wn = hits[0].face
            ? hits[0].face.normal.clone().transformDirection(hits[0].object.matrixWorld)
            : new THREE.Vector3(0,1,0);
        preview.group.position.addScaledVector(toLocalDir(wn), .02);
    }}
}});

/* ── Camera orbit controls ───────────────────────────────────────── */
let _orbitActive = false;
let _orbiting    = false;
let _orbitStart  = {{ x:0, y:0 }};
let _theta = 0, _phi = 0.18;
const _RADIUS = 1.5;

function _updateCamera() {{
    camera.position.x = _RADIUS * Math.sin(_theta) * Math.cos(_phi);
    camera.position.y = _RADIUS * Math.sin(_phi);
    camera.position.z = _RADIUS * Math.cos(_theta) * Math.cos(_phi);
    camera.lookAt(0, 0.05, 0);
}}
_updateCamera();

canvas.addEventListener('mousedown', e => {{
    _orbiting   = true;
    _orbitActive = false;
    _orbitStart  = {{ x: e.clientX, y: e.clientY }};
}});
canvas.addEventListener('mousemove', e => {{
    if (!_orbiting) return;
    const dx = e.clientX - _orbitStart.x;
    const dy = e.clientY - _orbitStart.y;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) _orbitActive = true;
    _theta -= dx * 0.008;
    _phi    = Math.max(-.5, Math.min(.7, _phi + dy * 0.006));
    _orbitStart = {{ x: e.clientX, y: e.clientY }};
    _updateCamera();
}});
window.addEventListener('mouseup', () => {{
    _orbiting = false;
    setTimeout(() => {{ _orbitActive = false; }}, 50);
}});

/* Touch orbit */
let _tLast = null;
canvas.addEventListener('touchstart', e => {{
    _tLast = e.touches[0];
    _orbitActive = false;
}}, {{passive:true}});
canvas.addEventListener('touchmove', e => {{
    if (!_tLast) return;
    const t  = e.touches[0];
    const dx = t.clientX - _tLast.clientX;
    const dy = t.clientY - _tLast.clientY;
    _theta -= dx * 0.01;
    _phi    = Math.max(-.5, Math.min(.7, _phi + dy * 0.008));
    _tLast  = t;
    _updateCamera();
    _orbitActive = true;
}}, {{passive:true}});
canvas.addEventListener('touchend', () => {{
    _tLast = null;
    setTimeout(() => {{ _orbitActive = false; }}, 60);
}});

/* Scroll zoom */
canvas.addEventListener('wheel', e => {{
    const newR = Math.max(.5, Math.min(3, _RADIUS + e.deltaY * .001));
    camera.position.setLength(newR);
}}, {{passive:true}});

/* ── Reset scene ─────────────────────────────────────────────────── */
function resetScene() {{
    /* Clear placed objects */
    Object.keys(placed).forEach(k => {{
        if (placed[k] && modelRoot) modelRoot.remove(placed[k]);
        delete placed[k];
    }});
    needleAnim.flashed  = false;
    needleAnim.inserted = false;
    instrMode = null;
    removePreview();
    document.querySelectorAll('.instr').forEach(el => {{
        el.classList.remove('sel', 'placed');
    }});
    document.body.classList.remove('placing');
    /* Rebuild anatomy */
    buildAnatomy();
    showFB('Scene reset.', 2000);
}}

/* ── Resize handler ──────────────────────────────────────────────── */
window.addEventListener('resize', () => {{
    W = canvasWrap.clientWidth  || window.innerWidth;
    H = canvasWrap.clientHeight || window.innerHeight - 38;
    renderer.setSize(W, H);
    camera.aspect = W / H;
    camera.updateProjectionMatrix();
}});

/* ── Animation loop ──────────────────────────────────────────────── */
const _clock = new THREE.Clock();
function animate() {{
    requestAnimationFrame(animate);
    const dt = _clock.getDelta();

    /* Gentle auto-rotate when idle */
    if (!_orbiting && !instrMode) {{
        _theta += dt * 0.12;
        _updateCamera();
    }}

    renderer.render(scene, camera);
}}
animate();
</script>
</body></html>"""


# Alias — works as both base viewer and guided wrapper
build_guided_3d_html = _build_3d_html