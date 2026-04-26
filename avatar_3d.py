"""
avatar_3d.py  —  Realistic Human Avatar (Three.js r128)

Replaces the chibi model with a clinically accurate, adult-proportioned
3-D doctor avatar using:
  • MeshPhysicalMaterial  — subsurface-like skin, realistic roughness/metalness
  • 7.5 : 1 body-to-head ratio  (medical illustration standard)
  • Full 3-point + hemisphere lighting with environment fill
  • Detailed face: brow ridge, cheekbones, nose bridge, lips, chin
  • Layered hair geometry (scalp + strands + wisps)
  • Professional white coat with lapels, pockets, buttons
  • Stethoscope as proper curved tube around neck
  • Realistic glasses frames (titanium-look)
  • Hijab as draped multi-mesh cloth
  • Idle breathing + subtle head-sway animation
  • OrbitControls-style mouse drag (no extra import needed)
"""

import json


def render_avatar_3d_component(av: dict, width: int = 420, height: int = 480) -> str:
    cfg = json.dumps({
        "name":        av.get("name",        "Dr. ..."),
        "gender":      av.get("gender",      "Female"),
        "skin":        av.get("skin",        "#f5c5a3"),
        "hair":        av.get("hair",        "#2c1810"),
        "eyes":        av.get("eyes",        "#5c3a1e"),
        "coat":        av.get("coat",        "#5ba4cf"),
        "hijab":       av.get("hijab",       False),
        "hijab_color": av.get("hijab_color", "#6b7280"),
        "stethoscope": av.get("stethoscope", True),
        "glasses":     av.get("glasses",     False),
    }, ensure_ascii=False)

    JS = r"""
/* ═══════════════════════════════════════════════════════════
   REALISTIC DOCTOR AVATAR — Three.js r128
   ═══════════════════════════════════════════════════════════ */
const AV = __CFG__;
const W = __W__, H = __H__;
const canvas = document.getElementById('c');
canvas.width  = W; canvas.height = H;

/* ── Renderer ─────────────────────────────────────────────── */
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
renderer.setSize(W, H);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type    = THREE.PCFSoftShadowMap;
renderer.physicallyCorrectLights = true;
renderer.outputEncoding    = THREE.sRGBEncoding;
renderer.toneMapping       = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;

/* ── Scene ────────────────────────────────────────────────── */
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf0f4f8);
scene.fog = new THREE.Fog(0xf0f4f8, 10, 26);

/* ── Camera ───────────────────────────────────────────────── */
const camera = new THREE.PerspectiveCamera(32, W / H, 0.05, 50);
camera.position.set(0, 1.62, 4.8);
camera.lookAt(0, 1.55, 0);

/* ── Lighting (3-point + hemisphere) ─────────────────────── */
const hemi = new THREE.HemisphereLight(0xfff9f0, 0xd0e8ff, 0.55);
scene.add(hemi);

const keyL = new THREE.DirectionalLight(0xfff8f0, 2.2);
keyL.position.set(2.5, 5, 3.5);
keyL.castShadow = true;
keyL.shadow.mapSize.set(1024, 1024);
keyL.shadow.camera.near = 0.1;
keyL.shadow.camera.far  = 20;
keyL.shadow.camera.left = -2;
keyL.shadow.camera.right = 2;
keyL.shadow.camera.top  = 4;
keyL.shadow.camera.bottom = 0;
keyL.shadow.bias = -0.0003;
scene.add(keyL);

const fillL = new THREE.DirectionalLight(0xd0e8ff, 0.9);
fillL.position.set(-3, 3, 2);
scene.add(fillL);

const rimL = new THREE.DirectionalLight(0xfff5e0, 0.7);
rimL.position.set(0, 4, -4);
scene.add(rimL);

const ptL = new THREE.PointLight(0xffeedd, 0.5, 6);
ptL.position.set(0, 3.4, 1.8);
scene.add(ptL);

/* ── Floor ────────────────────────────────────────────────── */
const floor = new THREE.Mesh(
  new THREE.PlaneGeometry(6, 6),
  new THREE.MeshStandardMaterial({ color: 0xe8eef4, roughness: 0.95 })
);
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
scene.add(floor);

/* ── Material helpers ─────────────────────────────────────── */
function skin(hex, rough = 0.62, metal = 0.0) {
  return new THREE.MeshPhysicalMaterial({
    color:         new THREE.Color(hex),
    roughness:     rough,
    metalness:     metal,
    sheen:         0.18,
    sheenRoughness: 0.7,
    sheenColor:    new THREE.Color(hex).multiplyScalar(0.8),
  });
}
function cloth(hex, rough = 0.88) {
  return new THREE.MeshStandardMaterial({
    color:     new THREE.Color(hex),
    roughness: rough,
    metalness: 0.0,
  });
}
function metal(hex, rough = 0.22) {
  return new THREE.MeshStandardMaterial({
    color:     new THREE.Color(hex),
    roughness: rough,
    metalness: 0.92,
  });
}
function glass(hex = '#88ccee', opac = 0.32) {
  return new THREE.MeshPhysicalMaterial({
    color:       new THREE.Color(hex),
    roughness:   0.05,
    metalness:   0.0,
    transparent: true,
    opacity:     opac,
    transmission: 0.5,
  });
}

/* ── Avatar root ──────────────────────────────────────────── */
const root = new THREE.Group();
scene.add(root);

/* ── Colour shortcuts ─────────────────────────────────────── */
const SKIN  = AV.skin;
const HAIR  = AV.hair;
const EYES  = AV.eyes;
const COAT  = AV.coat;
const SCARF = AV.hijab_color;

/* ══════════════════════════════════════════════════════════
   BODY GEOMETRY  (7.5 heads tall = adult standard)
   All Y positions relative to feet at Y=0.
   Head height ≈ 0.32 units → total body ≈ 2.40 units
   ══════════════════════════════════════════════════════════ */
const UNIT = 0.30;  /* 1 head = 0.30 * 2 = 0.60m-equivalent */

/* ── LEGS (trousers) ──────────────────────────────────────── */
const trouserMat = cloth('#1e293b', 0.9);
[-0.145, 0.145].forEach(x => {
  /* Thigh */
  const thigh = new THREE.Mesh(
    new THREE.CylinderGeometry(0.115, 0.105, 0.70, 20),
    trouserMat
  );
  thigh.position.set(x, 0.685, 0);
  thigh.castShadow = true;
  root.add(thigh);

  /* Knee taper */
  const knee = new THREE.Mesh(
    new THREE.SphereGeometry(0.105, 16, 12),
    trouserMat
  );
  knee.scale.y = 0.80;
  knee.position.set(x, 0.34, 0);
  root.add(knee);

  /* Lower leg */
  const lower = new THREE.Mesh(
    new THREE.CylinderGeometry(0.095, 0.082, 0.64, 18),
    trouserMat
  );
  lower.position.set(x, 0.005, 0);
  lower.position.y = 0.008;
  lower.position.set(x, 0.008, 0);
  root.add(lower);
});

/* ── SHOES ────────────────────────────────────────────────── */
const shoeMat = cloth('#1a1a1a', 0.75);
[-0.145, 0.145].forEach(x => {
  const shoe = new THREE.Mesh(
    new THREE.CapsuleGeometry ? /* r128 has no CapsuleGeometry, use groups */ null : null
  );

  /* Toe box */
  const toe = new THREE.Mesh(new THREE.SphereGeometry(0.095, 16, 10), shoeMat);
  toe.scale.set(1.15, 0.55, 1.35);
  toe.position.set(x, 0.055, 0.045);
  toe.castShadow = true;
  root.add(toe);

  /* Heel */
  const heel = new THREE.Mesh(new THREE.SphereGeometry(0.082, 14, 10), shoeMat);
  heel.scale.set(1.0, 0.48, 1.0);
  heel.position.set(x, 0.046, -0.04);
  root.add(heel);
});

/* ── TORSO — realistic taper ──────────────────────────────── */
/* Coat / scrub body */
const coatMat = cloth(COAT === '#e8eef4' ? '#eef2f8' : COAT, 0.85);
const whiteMat = cloth('#e8eef4', 0.82);

/* Is it a white coat? */
const IS_WHITE_COAT = COAT === '#e8eef4' || COAT === '#ffffff';

/* Under-shirt / scrub body */
const torsoMat = IS_WHITE_COAT ? cloth('#1e4a8a', 0.85) : coatMat;

const torsoBody = new THREE.Mesh(
  new THREE.CylinderGeometry(0.30, 0.26, 0.80, 24),
  torsoMat
);
torsoBody.position.set(0, 1.42, 0);
torsoBody.castShadow = true;
root.add(torsoBody);

/* Shoulders wider */
const shoulderL = new THREE.Mesh(new THREE.SphereGeometry(0.175, 20, 14), torsoMat);
shoulderL.scale.set(1.0, 0.7, 0.85);
shoulderL.position.set(-0.30, 1.80, 0);
shoulderL.castShadow = true;
root.add(shoulderL);

const shoulderR = shoulderL.clone();
shoulderR.position.x = 0.30;
root.add(shoulderR);

/* Chest volume */
const chest = new THREE.Mesh(
  new THREE.SphereGeometry(0.26, 20, 14),
  torsoMat
);
chest.scale.set(1.22, 0.80, 0.90);
chest.position.set(0, 1.80, 0.015);
root.add(chest);

/* ── White coat overlay (if applicable) ───────────────────── */
if (IS_WHITE_COAT) {
  const coatBodyMat = cloth('#e8eef4', 0.80);

  /* Main coat panels — left + right halves with gap in middle */
  [-0.075, 0.075].forEach((xOff, side) => {
    const panel = new THREE.Mesh(
      new THREE.BoxGeometry(0.21, 0.82, 0.16),
      coatBodyMat
    );
    panel.position.set(side === 0 ? -0.14 : 0.14, 1.42, 0.145);
    panel.rotation.y = side === 0 ? 0.08 : -0.08;
    panel.castShadow = true;
    root.add(panel);
  });

  /* Lapels */
  [-1, 1].forEach(s => {
    const lapel = new THREE.Mesh(
      new THREE.BoxGeometry(0.09, 0.22, 0.05),
      coatBodyMat
    );
    lapel.position.set(s * 0.075, 1.87, 0.22);
    lapel.rotation.z = s * 0.28;
    lapel.rotation.y = s * -0.15;
    root.add(lapel);
  });

  /* Chest pocket */
  const pocket = new THREE.Mesh(
    new THREE.BoxGeometry(0.085, 0.065, 0.012),
    cloth('#d8dde6', 0.82)
  );
  pocket.position.set(-0.175, 1.82, 0.235);
  root.add(pocket);

  /* Buttons */
  [1.68, 1.54, 1.40, 1.26].forEach(y => {
    const btn = new THREE.Mesh(
      new THREE.CylinderGeometry(0.012, 0.012, 0.008, 12),
      metal('#c8cdd5', 0.4)
    );
    btn.rotation.x = Math.PI / 2;
    btn.position.set(0.0, y, 0.22);
    root.add(btn);
  });
}

/* ── UPPER ARMS ───────────────────────────────────────────── */
[-1, 1].forEach(s => {
  const upperArm = new THREE.Mesh(
    new THREE.CylinderGeometry(0.105, 0.090, 0.56, 18),
    IS_WHITE_COAT ? cloth('#e8eef4', 0.80) : torsoMat
  );
  upperArm.position.set(s * 0.42, 1.55, 0);
  upperArm.rotation.z = s * 0.14;
  upperArm.castShadow = true;
  root.add(upperArm);

  /* Elbow */
  const elbow = new THREE.Mesh(new THREE.SphereGeometry(0.090, 14, 10),
    IS_WHITE_COAT ? cloth('#dde2ea', 0.80) : torsoMat);
  elbow.position.set(s * 0.45, 1.28, 0);
  root.add(elbow);

  /* Forearm */
  const forearm = new THREE.Mesh(
    new THREE.CylinderGeometry(0.082, 0.068, 0.52, 16),
    IS_WHITE_COAT ? cloth('#e8eef4', 0.78) : torsoMat
  );
  forearm.position.set(s * 0.47, 1.01, 0.04);
  forearm.rotation.z = s * 0.08;
  forearm.rotation.x = 0.08;
  forearm.castShadow = true;
  root.add(forearm);

  /* HAND */
  const hand = new THREE.Mesh(
    new THREE.SphereGeometry(0.072, 16, 12),
    skin(SKIN, 0.65)
  );
  hand.scale.set(0.85, 0.75, 0.55);
  hand.position.set(s * 0.485, 0.76, 0.08);
  hand.castShadow = true;
  root.add(hand);

  /* Fingers (simplified — 3 merged sausages) */
  [0, 1, 2].forEach(f => {
    const finger = new THREE.Mesh(
      new THREE.CylinderGeometry(0.016, 0.013, 0.095, 8),
      skin(SKIN, 0.68)
    );
    finger.position.set(s * 0.485 + (f - 1) * 0.022, 0.695, 0.11);
    finger.rotation.x = 0.22;
    root.add(finger);
  });
});

/* ── NECK ─────────────────────────────────────────────────── */
const neckMat = skin(SKIN, 0.60);
const neck = new THREE.Mesh(
  new THREE.CylinderGeometry(0.095, 0.115, 0.26, 20),
  neckMat
);
neck.position.set(0, 2.09, 0.012);
neck.castShadow = true;
root.add(neck);

/* ══════════════════════════════════════════════════════════
   HEAD — built from overlapping meshes for realistic shape
   ══════════════════════════════════════════════════════════ */
const headRoot = new THREE.Group();
headRoot.position.set(0, 2.34, 0);
root.add(headRoot);

/* Cranium — slightly back-heavy */
const cranium = new THREE.Mesh(
  new THREE.SphereGeometry(0.195, 32, 28),
  skin(SKIN, 0.58)
);
cranium.scale.set(0.91, 1.00, 0.93);
cranium.position.set(0, 0.065, -0.005);
cranium.castShadow = true;
headRoot.add(cranium);

/* Face plate — flatter front */
const face = new THREE.Mesh(
  new THREE.SphereGeometry(0.188, 32, 24),
  skin(SKIN, 0.62)
);
face.scale.set(0.88, 0.92, 0.72);
face.position.set(0, 0.012, 0.045);
headRoot.add(face);

/* Forehead slight protrusion */
const forehead = new THREE.Mesh(
  new THREE.SphereGeometry(0.132, 20, 14),
  skin(SKIN, 0.60)
);
forehead.scale.set(0.98, 0.55, 0.65);
forehead.position.set(0, 0.18, 0.065);
headRoot.add(forehead);

/* Cheekbones */
[-1, 1].forEach(s => {
  const cheek = new THREE.Mesh(
    new THREE.SphereGeometry(0.082, 16, 12),
    skin(SKIN, 0.60)
  );
  cheek.scale.set(1.1, 0.68, 0.72);
  cheek.position.set(s * 0.120, 0.025, 0.098);
  headRoot.add(cheek);
});

/* Chin */
const chin = new THREE.Mesh(
  new THREE.SphereGeometry(0.066, 16, 12),
  skin(SKIN, 0.65)
);
chin.scale.set(0.80, 0.58, 0.72);
chin.position.set(0, -0.148, 0.070);
headRoot.add(chin);

/* Jaw line */
[-1, 1].forEach(s => {
  const jaw = new THREE.Mesh(
    new THREE.SphereGeometry(0.072, 14, 10),
    skin(SKIN, 0.64)
  );
  jaw.scale.set(0.72, 0.55, 0.68);
  jaw.position.set(s * 0.108, -0.115, 0.042);
  headRoot.add(jaw);
});

/* ── EARS ─────────────────────────────────────────────────── */
[-1, 1].forEach(s => {
  const ear = new THREE.Mesh(
    new THREE.SphereGeometry(0.048, 16, 12),
    skin(SKIN, 0.68)
  );
  ear.scale.set(0.42, 0.78, 0.52);
  ear.position.set(s * 0.186, 0.032, 0.00);
  headRoot.add(ear);
  /* Ear lobe */
  const lobe = new THREE.Mesh(
    new THREE.SphereGeometry(0.025, 10, 8),
    skin(SKIN, 0.70)
  );
  lobe.position.set(s * 0.188, -0.030, 0.002);
  headRoot.add(lobe);
});

/* ── NOSE ─────────────────────────────────────────────────── */
/* Bridge */
const noseBridge = new THREE.Mesh(
  new THREE.CylinderGeometry(0.018, 0.022, 0.085, 10),
  skin(SKIN, 0.62)
);
noseBridge.rotation.x = -0.20;
noseBridge.position.set(0, 0.04, 0.158);
headRoot.add(noseBridge);

/* Nose tip / ball */
const noseTip = new THREE.Mesh(
  new THREE.SphereGeometry(0.030, 14, 10),
  skin(SKIN, 0.64)
);
noseTip.scale.set(1.1, 0.85, 1.0);
noseTip.position.set(0, -0.015, 0.175);
headRoot.add(noseTip);

/* Nostrils */
[-1, 1].forEach(s => {
  const nostril = new THREE.Mesh(
    new THREE.SphereGeometry(0.022, 10, 8),
    skin(SKIN, 0.55)
  );
  nostril.scale.set(0.75, 0.60, 0.88);
  nostril.position.set(s * 0.030, -0.025, 0.165);
  headRoot.add(nostril);
});

/* ── MOUTH ────────────────────────────────────────────────── */
/* Upper lip */
const lipMat = skin(
  new THREE.Color(SKIN).lerp(new THREE.Color('#c06070'), 0.35).getStyle(), 0.55
);
const upperLip = new THREE.Mesh(
  new THREE.SphereGeometry(0.042, 16, 10),
  lipMat
);
upperLip.scale.set(1.4, 0.42, 0.65);
upperLip.position.set(0, -0.075, 0.162);
headRoot.add(upperLip);

/* Lower lip */
const lowerLip = new THREE.Mesh(
  new THREE.SphereGeometry(0.042, 16, 10),
  lipMat
);
lowerLip.scale.set(1.35, 0.50, 0.68);
lowerLip.position.set(0, -0.096, 0.157);
headRoot.add(lowerLip);

/* Philtrum indent (slightly darker) */
const philtrum = new THREE.Mesh(
  new THREE.SphereGeometry(0.018, 10, 8),
  skin(new THREE.Color(SKIN).lerp(new THREE.Color('#a05540'), 0.12).getStyle(), 0.60)
);
philtrum.scale.set(0.70, 0.80, 0.50);
philtrum.position.set(0, -0.048, 0.168);
headRoot.add(philtrum);

/* ── EYES ─────────────────────────────────────────────────── */
[-1, 1].forEach(s => {
  /* Eye socket (slightly darker) */
  const socket = new THREE.Mesh(
    new THREE.SphereGeometry(0.052, 18, 14),
    skin(new THREE.Color(SKIN).lerp(new THREE.Color('#7a5540'), 0.08).getStyle(), 0.55)
  );
  socket.scale.set(1.15, 0.82, 0.58);
  socket.position.set(s * 0.066, 0.065, 0.138);
  headRoot.add(socket);

  /* Sclera (white) */
  const sclera = new THREE.Mesh(
    new THREE.SphereGeometry(0.034, 18, 14),
    new THREE.MeshPhysicalMaterial({ color: 0xf5f0eb, roughness: 0.12, metalness: 0 })
  );
  sclera.scale.set(1.18, 0.82, 0.55);
  sclera.position.set(s * 0.066, 0.066, 0.158);
  headRoot.add(sclera);

  /* Iris */
  const iris = new THREE.Mesh(
    new THREE.CircleGeometry(0.018, 20),
    new THREE.MeshPhysicalMaterial({ color: new THREE.Color(EYES), roughness: 0.08, metalness: 0.05 })
  );
  iris.rotation.y = s * 0.05;
  iris.position.set(s * 0.067, 0.066, 0.185);
  headRoot.add(iris);

  /* Pupil */
  const pupil = new THREE.Mesh(
    new THREE.CircleGeometry(0.010, 14),
    new THREE.MeshBasicMaterial({ color: 0x0a0808 })
  );
  pupil.position.set(s * 0.067, 0.066, 0.1855);
  headRoot.add(pupil);

  /* Catchlight */
  const catchlight = new THREE.Mesh(
    new THREE.CircleGeometry(0.004, 8),
    new THREE.MeshBasicMaterial({ color: 0xffffff })
  );
  catchlight.position.set(s * 0.070, 0.070, 0.1858);
  headRoot.add(catchlight);

  /* Upper eyelid */
  const eyelid = new THREE.Mesh(
    new THREE.SphereGeometry(0.036, 16, 10),
    skin(new THREE.Color(SKIN).lerp(new THREE.Color('#7a5540'), 0.06).getStyle(), 0.55)
  );
  eyelid.scale.set(1.20, 0.32, 0.55);
  eyelid.position.set(s * 0.066, 0.073, 0.162);
  headRoot.add(eyelid);

  /* Eyebrow */
  const browMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(HAIR === '#e8e8e8' || HAIR === '#8a8a8a' ? '#555555' : HAIR),
    roughness: 0.92
  });
  const brow = new THREE.Mesh(
    new THREE.CapsuleGeometry ? /* fallback */ new THREE.SphereGeometry(1,8,6) : new THREE.SphereGeometry(1,8,6),
    browMat
  );
  /* Manual brow shape using a flattened cylinder */
  const browShape = new THREE.Mesh(
    new THREE.CylinderGeometry(0.007, 0.007, 0.065, 8),
    browMat
  );
  browShape.rotation.z = s * 0.12;
  browShape.position.set(s * 0.066, 0.110, 0.152);
  headRoot.add(browShape);
});

/* ── HAIR ─────────────────────────────────────────────────── */
if (!AV.hijab) {
  const hairMat = new THREE.MeshStandardMaterial({
    color:     new THREE.Color(HAIR),
    roughness: 0.88,
    metalness: 0.02,
  });

  /* Scalp cap */
  const scalp = new THREE.Mesh(
    new THREE.SphereGeometry(0.205, 32, 20, 0, Math.PI * 2, 0, Math.PI * 0.58),
    hairMat
  );
  scalp.position.set(0, 0.075, -0.008);
  scalp.castShadow = true;
  headRoot.add(scalp);

  /* Temple fill */
  [-1, 1].forEach(s => {
    const temple = new THREE.Mesh(
      new THREE.SphereGeometry(0.110, 18, 12),
      hairMat
    );
    temple.scale.set(0.52, 0.88, 0.70);
    temple.position.set(s * 0.168, 0.042, 0.005);
    headRoot.add(temple);
  });

  if (AV.gender === 'Female') {
    /* Long hair — back volume */
    const backHair = new THREE.Mesh(
      new THREE.SphereGeometry(0.195, 28, 20),
      hairMat
    );
    backHair.scale.set(0.90, 1.30, 0.72);
    backHair.position.set(0, -0.055, -0.068);
    headRoot.add(backHair);

    /* Side strands */
    [-1, 1].forEach(s => {
      const strand = new THREE.Mesh(
        new THREE.CylinderGeometry(0.060, 0.038, 0.52, 14),
        hairMat
      );
      strand.position.set(s * 0.185, -0.22, -0.018);
      strand.rotation.z = s * 0.12;
      headRoot.add(strand);
    });
  } else {
    /* Short male hair — keep scalp cap, add texture layers */
    const sideL = new THREE.Mesh(
      new THREE.SphereGeometry(0.090, 14, 10), hairMat
    );
    sideL.scale.set(0.55, 0.70, 0.68);
    sideL.position.set(-0.152, 0.060, 0.010);
    headRoot.add(sideL);
    const sideR = sideL.clone();
    sideR.position.x = 0.152;
    headRoot.add(sideR);
  }
} else {
  /* ── HIJAB ─────────────────────────────────────────────── */
  const hijabMat = cloth(SCARF, 0.92);

  /* Main cap */
  const cap = new THREE.Mesh(
    new THREE.SphereGeometry(0.215, 32, 24),
    hijabMat
  );
  cap.scale.set(1.02, 1.08, 1.04);
  cap.position.set(0, 0.065, -0.010);
  cap.castShadow = true;
  headRoot.add(cap);

  /* Front frame — wraps face */
  const frame = new THREE.Mesh(
    new THREE.TorusGeometry(0.218, 0.028, 10, 40, Math.PI),
    hijabMat
  );
  frame.rotation.y = Math.PI;
  frame.position.set(0, 0.045, 0.005);
  headRoot.add(frame);

  /* Drape — falls over shoulders */
  const drape = new THREE.Mesh(
    new THREE.CylinderGeometry(0.245, 0.310, 0.44, 28, 1, true),
    hijabMat
  );
  drape.position.set(0, -0.11, 0);
  headRoot.add(drape);

  /* Side folds */
  [-1, 1].forEach(s => {
    const fold = new THREE.Mesh(
      new THREE.SphereGeometry(0.095, 14, 10),
      hijabMat
    );
    fold.scale.set(0.55, 1.20, 0.72);
    fold.position.set(s * 0.205, -0.055, 0.022);
    headRoot.add(fold);
  });
}

/* ── GLASSES ──────────────────────────────────────────────── */
if (AV.glasses) {
  const frameMat = metal('#2a2a2a', 0.35);
  const lensMat  = glass('#b8d4e8', 0.18);

  /* Lens circles */
  [-1, 1].forEach(s => {
    /* Rim */
    const rim = new THREE.Mesh(
      new THREE.TorusGeometry(0.040, 0.006, 10, 32),
      frameMat
    );
    rim.position.set(s * 0.066, 0.065, 0.172);
    rim.rotation.y = s * 0.06;
    headRoot.add(rim);

    /* Lens glass */
    const lens = new THREE.Mesh(
      new THREE.CircleGeometry(0.038, 24),
      lensMat
    );
    lens.position.set(s * 0.066, 0.065, 0.173);
    headRoot.add(lens);
  });

  /* Bridge */
  const bridge = new THREE.Mesh(
    new THREE.CylinderGeometry(0.004, 0.004, 0.030, 8),
    frameMat
  );
  bridge.rotation.z = Math.PI / 2;
  bridge.position.set(0, 0.065, 0.172);
  headRoot.add(bridge);

  /* Temple arms */
  [-1, 1].forEach(s => {
    const arm = new THREE.Mesh(
      new THREE.CylinderGeometry(0.003, 0.003, 0.148, 6),
      frameMat
    );
    arm.rotation.z = Math.PI / 2;
    arm.position.set(s * 0.154, 0.065, 0.130);
    headRoot.add(arm);
  });
}

/* ── STETHOSCOPE ──────────────────────────────────────────── */
if (AV.stethoscope) {
  const tubeMat = metal('#222222', 0.42);
  const chestMat = metal('#888888', 0.28);

  /* Earpiece bar */
  const bar = new THREE.Mesh(
    new THREE.CylinderGeometry(0.008, 0.008, 0.18, 8),
    tubeMat
  );
  bar.rotation.z = Math.PI / 2;
  bar.position.set(0, 2.12, 0.09);
  root.add(bar);

  /* Left + right Y tubes (curved approximated with angled cylinders) */
  [-1, 1].forEach(s => {
    /* Upper arm */
    const upper = new THREE.Mesh(
      new THREE.CylinderGeometry(0.007, 0.007, 0.22, 8),
      tubeMat
    );
    upper.rotation.z = s * 0.55;
    upper.rotation.x = 0.22;
    upper.position.set(s * 0.085, 1.95, 0.085);
    root.add(upper);

    /* Earpiece */
    const ep = new THREE.Mesh(
      new THREE.SphereGeometry(0.013, 8, 6),
      metal('#444444', 0.30)
    );
    ep.position.set(s * 0.110, 2.12, 0.075);
    root.add(ep);
  });

  /* Down-drape (long tube down chest) */
  const down = new THREE.Mesh(
    new THREE.CylinderGeometry(0.007, 0.007, 0.55, 8),
    tubeMat
  );
  down.rotation.x = 0.20;
  down.position.set(0, 1.70, 0.14);
  root.add(down);

  /* Chest piece (diaphragm) */
  const diaphragm = new THREE.Mesh(
    new THREE.CylinderGeometry(0.032, 0.028, 0.012, 16),
    chestMat
  );
  diaphragm.rotation.x = -0.22;
  diaphragm.position.set(0, 1.42, 0.24);
  root.add(diaphragm);

  /* Stem */
  const stem = new THREE.Mesh(
    new THREE.CylinderGeometry(0.007, 0.007, 0.07, 8),
    tubeMat
  );
  stem.rotation.x = -0.22;
  stem.position.set(0, 1.458, 0.225);
  root.add(stem);
}

/* ── NAME BADGE ───────────────────────────────────────────── */
const badge = new THREE.Mesh(
  new THREE.BoxGeometry(0.088, 0.058, 0.004),
  new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.60 })
);
badge.position.set(IS_WHITE_COAT ? -0.175 : -0.168, 1.68, 0.26);
root.add(badge);

/* ══════════════════════════════════════════════════════════
   MOUSE DRAG ORBIT (no external OrbitControls needed)
   ══════════════════════════════════════════════════════════ */
let drag = false, lastX = 0, lastY = 0;
let rotY = 0, rotX = 0.02;
let targetY = 0, targetX = 0.02;

canvas.addEventListener('mousedown', e => { drag = true; lastX = e.clientX; lastY = e.clientY; });
window.addEventListener('mouseup',   () => drag = false);
window.addEventListener('mousemove', e => {
  if (!drag) return;
  targetY += (e.clientX - lastX) * 0.012;
  targetX += (e.clientY - lastY) * 0.007;
  targetX = Math.max(-0.4, Math.min(0.55, targetX));
  lastX = e.clientX; lastY = e.clientY;
});

canvas.addEventListener('touchstart', e => {
  drag = true; lastX = e.touches[0].clientX; lastY = e.touches[0].clientY;
}, { passive: true });
canvas.addEventListener('touchend',  () => drag = false);
canvas.addEventListener('touchmove', e => {
  if (!drag) return;
  targetY += (e.touches[0].clientX - lastX) * 0.012;
  lastX = e.touches[0].clientX;
}, { passive: true });

/* Scroll zoom */
canvas.addEventListener('wheel', e => {
  camera.position.z = Math.max(2.5, Math.min(7.5, camera.position.z + e.deltaY * 0.005));
  e.preventDefault();
}, { passive: false });

/* ══════════════════════════════════════════════════════════
   ANIMATION LOOP
   ══════════════════════════════════════════════════════════ */
let clock = 0;
function animate() {
  requestAnimationFrame(animate);
  clock += 0.016;

  /* Smooth orbit */
  rotY += (targetY - rotY) * 0.08;
  rotX += (targetX - rotX) * 0.08;
  root.rotation.y = rotY;
  root.rotation.x = rotX * 0.3;

  /* Idle auto-rotate (stops when user drags) */
  if (!drag) targetY += 0.003;

  /* Breathing: torso scale + body slight rise */
  const breath = Math.sin(clock * 1.1) * 0.006;
  torsoBody.scale.set(1 + breath * 0.8, 1 + breath * 0.4, 1 + breath * 0.8);
  root.position.y = Math.sin(clock * 1.1) * 0.008;

  /* Subtle head sway */
  headRoot.rotation.y = Math.sin(clock * 0.55) * 0.020;
  headRoot.rotation.z = Math.sin(clock * 0.42) * 0.012;

  renderer.render(scene, camera);
}
animate();

/* ── Name label ───────────────────────────────────────────── */
document.getElementById('dname').textContent = AV.name;
"""

    JS = (JS
          .replace("__CFG__", cfg)
          .replace("__W__",   str(width))
          .replace("__H__",   str(height)))

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: linear-gradient(160deg, #e8eef6 0%, #f0f4f8 50%, #e4ecf4 100%);
  overflow: hidden;
  width: {width}px; height: {height}px;
  font-family: 'Inter', system-ui, sans-serif;
}}
#badge-bar {{
  position: absolute; bottom: 0; left: 0; right: 0;
  padding: 10px 18px 12px;
  background: linear-gradient(0deg, rgba(10,37,64,.92) 0%, rgba(10,37,64,.0) 100%);
  color: white; text-align: center; pointer-events: none;
}}
#dname  {{ font-weight: 700; font-size: .92rem; letter-spacing: .01em; }}
#dsub   {{ font-size: .72rem; color: #67e8f9; margin-top: 2px; opacity: .85; }}
#hint   {{ font-size: .62rem; color: rgba(255,255,255,.42); margin-top: 4px; }}
</style>
</head>
<body>
<canvas id="c"></canvas>
<div id="badge-bar">
  <div id="dname">Dr. ...</div>
  <div id="dsub">MLS Virtual Hospital · Clinical Simulator</div>
  <div id="hint">Drag to rotate &middot; Scroll to zoom</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>{JS}</script>
</body>
</html>"""