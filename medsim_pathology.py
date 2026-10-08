"""
medsim_pathology.py
────────────────────────────────────────────────────────────────────────────
Preclinical virtual microscope. A real pan/zoom viewer over an uploaded
slide image — not a static photo — with magnification presets (4x/10x/
40x/100x, matching real microscope objectives) and clickable pathology
annotations, the same landmark-marker concept already used in
medsim_anatomy_viewer.py, applied to a 2D slide instead of a 3D model.

HONEST SCOPE NOTE: this is a pan/zoom viewer for a single uploaded slide
image (a photo or cropped scan region, a few MB), not a true whole-slide-
imaging (WSI) gigapixel tile pyramid — that's different, heavier
infrastructure (a dedicated tile server) that a single image file can't
provide. For real microscope photos or reasonably-sized cropped scan
regions, this gives genuine zoom/pan/annotation functionality.

Requires one new Supabase table:

    create table vh_pathology_slides (
      id            bigint generated always as identity primary key,
      slide_id        text unique not null,
      name              text not null,
      specialty           text,
      diagnosis             text,
      description             text,
      image_b64                 text not null,
      -- base64-encoded JPG/PNG. Keep uploads reasonably sized (a few MB) —
      -- very large files may exceed default PostgREST request-size limits.
      annotations               jsonb,
      created_by                  text,
      created_at                    timestamp default now()
    );
"""

import base64
import json
import time
import requests
import streamlit as st
import streamlit.components.v1 as components

NAVY, BLUE, TEAL = "#0a2540", "#1a4f8a", "#0e7490"
GREEN, AMBER, RED = "#059669", "#d97706", "#dc2626"
SURFACE, BORDER, TEXT, MUTED = "#ffffff", "#e2e8f0", "#0f172a", "#64748b"

TABLE = "vh_pathology_slides"
MAGNIFICATIONS = [4, 10, 40, 100]


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


def save_slide(row: dict) -> tuple:
    if not _sb_available():
        return False, "Supabase not configured."
    url, key = _sb_creds()
    try:
        r = requests.post(f"{url}/rest/v1/{TABLE}",
                           headers={**_sb_headers(key), "Prefer": "resolution=merge-duplicates,return=representation"},
                           json=row, timeout=20)
        return (True, "Saved.") if r.status_code in (200, 201) else (False, f"Failed ({r.status_code}): {r.text[:200]}")
    except Exception as e:
        return False, f"Failed: {e}"


def list_slides() -> list:
    if not _sb_available():
        return []
    url, key = _sb_creds()
    try:
        r = requests.get(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key),
                          params={"select": "id,slide_id,name,specialty,diagnosis,description,annotations,created_at",
                                   "order": "created_at.desc"}, timeout=10)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def get_slide(slide_id: str):
    if not _sb_available():
        return None
    url, key = _sb_creds()
    try:
        r = requests.get(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key),
                          params={"select": "*", "slide_id": f"eq.{slide_id}"}, timeout=15)
        rows = r.json() if r.status_code == 200 else []
        return rows[0] if rows else None
    except Exception:
        return None


def delete_slide(slide_id: str) -> bool:
    if not _sb_available():
        return False
    url, key = _sb_creds()
    try:
        r = requests.delete(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key),
                             params={"slide_id": f"eq.{slide_id}"}, timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False


# ── Placeholder slide (used only until a real slide is uploaded) ────────────
def _placeholder_slide_svg_b64() -> str:
    """A schematic tissue pattern, clearly NOT a real pathology image —
    used only so the viewer has something to show before a real slide is
    uploaded. Never presented as diagnostic content."""
    import random
    random.seed(7)
    cells = []
    for _ in range(220):
        cx, cy = random.uniform(0, 1000), random.uniform(0, 1000)
        r = random.uniform(8, 16)
        cells.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.0f}" '
                      f'fill="#d88a9a" fill-opacity="0.55" stroke="#7a2f42" stroke-width="1"/>')
        cells.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r*0.4:.0f}" '
                      f'fill="#5b1a2e" fill-opacity="0.8"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000">'
           f'<rect width="1000" height="1000" fill="#f3d9de"/>{"".join(cells)}'
           f'<text x="500" y="980" text-anchor="middle" font-size="22" fill="#7a2f42" '
           f'font-family="sans-serif">PLACEHOLDER not a real pathology image</text></svg>')
    return base64.b64encode(svg.encode()).decode()


def _build_microscope_html(image_b64: str, is_svg: bool, annotations: list, slide_name: str) -> str:
    mime = "image/svg+xml" if is_svg else "image/jpeg"
    img_src = f"data:{mime};base64,{image_b64}"
    ann_json = json.dumps(annotations or [])

    template = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d1117;overflow:hidden;font-family:'Segoe UI',sans-serif;color:#e6edf3}
#stage{position:relative;width:100%;height:100%;overflow:hidden;cursor:grab;background:#000}
#stage.dragging{cursor:grabbing}
#slide{position:absolute;left:50%;top:50%;transform-origin:center center;user-select:none;
       pointer-events:none;}
#hud{position:absolute;top:10px;left:10px;background:rgba(0,0,0,.75);border:1px solid rgba(255,255,255,.15);
     border-radius:8px;padding:7px 12px;font-size:12px;pointer-events:none}
#mags{position:absolute;top:10px;right:10px;display:flex;gap:6px}
.magbtn{background:rgba(20,20,30,.85);border:1px solid rgba(255,255,255,.2);color:#e6edf3;
        border-radius:6px;padding:6px 12px;font-size:12px;cursor:pointer}
.magbtn.on{background:#3a6df0;border-color:#3a6df0}
.marker{position:absolute;width:18px;height:18px;border-radius:50%;background:#ffd400;
        border:2px solid #7a2f42;transform:translate(-50%,-50%);cursor:pointer;
        box-shadow:0 0 8px rgba(255,212,0,.8);}
#note{position:absolute;bottom:10px;left:10px;right:10px;background:rgba(0,0,0,.85);
      border:1px solid rgba(255,212,0,.4);border-radius:8px;padding:10px 14px;font-size:13px;
      display:none;}
#hint{position:absolute;bottom:10px;left:50%;transform:translateX(-50%);font-size:11px;
      color:#9091a4;pointer-events:none;}
</style></head>
<body>
<div id="stage">
  <div id="slide"><img id="img" src="__IMG_SRC__" draggable="false"></div>
  <div id="hud">__NAME__ &mdash; <span id="magLabel">4x</span></div>
  <div id="mags">
    <button class="magbtn on" data-m="4">4x</button>
    <button class="magbtn" data-m="10">10x</button>
    <button class="magbtn" data-m="40">40x</button>
    <button class="magbtn" data-m="100">100x</button>
  </div>
  <div id="note"></div>
  <div id="hint">Drag to pan &middot; scroll or pinch to zoom &middot; click markers for findings</div>
</div>
<script>
const ANNOTATIONS = __ANN_JSON__;
const stage = document.getElementById('stage');
const slide = document.getElementById('slide');
const img = document.getElementById('img');

let scale = 1, panX = 0, panY = 0;
let dragging = false, lastX = 0, lastY = 0;
const MAG_SCALE = {4:1, 10:2.5, 40:8, 100:18};

function apply() {
  slide.style.transform = 'translate(-50%,-50%) translate(' + panX + 'px,' + panY + 'px) scale(' + scale + ')';
}

img.onload = () => { placeMarkers(); apply(); };

function placeMarkers() {
  ANNOTATIONS.forEach((a) => {
    const dot = document.createElement('div');
    dot.className = 'marker';
    dot.style.left = (a.x * 100) + '%';
    dot.style.top = (a.y * 100) + '%';
    dot.title = a.label || '';
    dot.onclick = (e) => {
      e.stopPropagation();
      const note = document.getElementById('note');
      note.style.display = 'block';
      note.innerHTML = '<b>' + (a.label || 'Finding') + '</b><br>' + (a.description || '');
    };
    slide.appendChild(dot);
  });
}

stage.addEventListener('mousedown', e => { dragging = true; lastX = e.clientX; lastY = e.clientY; stage.classList.add('dragging'); });
window.addEventListener('mouseup', () => { dragging = false; stage.classList.remove('dragging'); });
window.addEventListener('mousemove', e => {
  if (!dragging) return;
  panX += (e.clientX - lastX) / scale; panY += (e.clientY - lastY) / scale;
  lastX = e.clientX; lastY = e.clientY;
  apply();
});
stage.addEventListener('wheel', e => {
  e.preventDefault();
  const delta = e.deltaY < 0 ? 1.1 : 0.9;
  scale = Math.max(0.5, Math.min(24, scale * delta));
  apply();
}, { passive: false });

let lastDist = null;
stage.addEventListener('touchstart', e => {
  if (e.touches.length === 1) { dragging = true; lastX = e.touches[0].clientX; lastY = e.touches[0].clientY; }
  if (e.touches.length === 2) { lastDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY); }
});
stage.addEventListener('touchmove', e => {
  e.preventDefault();
  if (e.touches.length === 1 && dragging) {
    panX += (e.touches[0].clientX - lastX) / scale; panY += (e.touches[0].clientY - lastY) / scale;
    lastX = e.touches[0].clientX; lastY = e.touches[0].clientY;
    apply();
  } else if (e.touches.length === 2 && lastDist) {
    const dist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
    scale = Math.max(0.5, Math.min(24, scale * (dist / lastDist)));
    lastDist = dist;
    apply();
  }
}, { passive: false });
stage.addEventListener('touchend', () => { dragging = false; lastDist = null; });

document.querySelectorAll('.magbtn').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('.magbtn').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    const m = parseInt(btn.dataset.m);
    scale = MAG_SCALE[m];
    panX = 0; panY = 0;
    document.getElementById('magLabel').textContent = m + 'x';
    apply();
  };
});
</script>
</body></html>"""
    return (template.replace("__IMG_SRC__", img_src)
                     .replace("__NAME__", slide_name)
                     .replace("__ANN_JSON__", ann_json))


def render_microscope(slide_row, height: int = 560):
    if not slide_row:
        b64 = _placeholder_slide_svg_b64()
        html = _build_microscope_html(b64, True, [
            {"x": 0.3, "y": 0.4, "label": "Placeholder marker",
             "description": "Upload a real slide to replace this demo pattern."},
        ], "Demo pattern (not a real slide)")
    else:
        html = _build_microscope_html(slide_row["image_b64"], False,
                                       slide_row.get("annotations") or [], slide_row["name"])
    components.html(html, height=height, scrolling=False)


def render_slide_upload_form():
    st.markdown("#### 📤 Upload a real pathology slide")
    st.caption("Keep files reasonably sized (a few MB) — this stores the image directly in "
               "the database, not a tile server, so very large scans may fail to upload.")
    uploaded = st.file_uploader("Slide image (JPG/PNG)", type=["jpg", "jpeg", "png"])
    name = st.text_input("Slide name", placeholder="e.g. Invasive Ductal Carcinoma — H&E")
    specialty = st.selectbox("Specialty", ["Oncology", "Hematology", "Dermatopathology",
                                            "Microbiology", "General Pathology", "Other"])
    diagnosis = st.text_input("Diagnosis")
    description = st.text_area("Description / teaching notes")

    st.markdown("##### Annotations (optional)")
    st.caption("Add a few key findings students should locate on the slide.")
    n_ann = st.number_input("Number of annotations", min_value=0, max_value=10, value=0)
    annotations = []
    for i in range(int(n_ann)):
        c1, c2, c3 = st.columns([1, 1, 2])
        x = c1.slider(f"X% #{i+1}", 0, 100, 50, key=f"path_ann_x_{i}") / 100
        y = c2.slider(f"Y% #{i+1}", 0, 100, 50, key=f"path_ann_y_{i}") / 100
        label = c3.text_input(f"Label #{i+1}", key=f"path_ann_l_{i}")
        desc = st.text_input(f"Finding description #{i+1}", key=f"path_ann_d_{i}")
        annotations.append({"x": x, "y": y, "label": label, "description": desc})

    if st.button("💾 Save Slide", type="primary"):
        if not uploaded or not name.strip():
            st.error("An image file and a slide name are required.")
        else:
            img_bytes = uploaded.read()
            if len(img_bytes) > 6 * 1024 * 1024:
                st.error("File too large (over 6MB) — compress or crop the image and try again.")
                return
            b64 = base64.b64encode(img_bytes).decode()
            slide_id = f"slide_{int(time.time()*1000)}"
            ok, msg = save_slide({
                "slide_id": slide_id, "name": name.strip(), "specialty": specialty,
                "diagnosis": diagnosis.strip(), "description": description.strip(),
                "image_b64": b64, "annotations": annotations,
                "created_by": st.session_state.get("auth_user", {}).get("email", "unknown"),
            })
            st.success("✅ Slide saved — it's now available in the slide picker.") if ok else st.error(msg)


def page_pathology_lab():
    st.markdown("## 🔬 Preclinical Pathology Lab")

    # The full Pathology Centre experience (leader-authored slides, quiz
    # scoring) now lives in the Simulation Hospital app as its own
    # department, alongside the other hands-on skill stations. This page is
    # kept working as a local fallback — nothing here was removed — but
    # points students to the real home for this feature first.
    try:
        _sim_url = st.secrets.get("SIMULATION_HOSPITAL_URL", "")
    except Exception:
        _sim_url = ""
    if _sim_url:
        st.info("🧪 **Pathology Centre has moved to the Simulation Hospital** — "
                "it now lives alongside the other hands-on skill stations there.")
        st.link_button("🧪 Open Pathology Centre in Simulation Hospital", _sim_url, use_container_width=True)
        st.markdown("---")
        st.caption("The viewer below still works locally as a fallback if you'd rather stay here.")
    else:
        st.caption("A real virtual microscope — pan and zoom into slide images across "
                   "magnification levels, with clickable pathology findings. (This feature's "
                   "main home is now the Simulation Hospital's Pathology Centre department — "
                   "set `SIMULATION_HOSPITAL_URL` in secrets to link directly to it.)")

    is_faculty = st.session_state.get("auth_user", {}).get("role", "") in ("faculty", "admin")
    if is_faculty:
        with st.expander("👨‍🏫 Faculty: manage slides"):
            render_slide_upload_form()
            st.markdown("---")
            for s in list_slides():
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**{s['name']}** — {s.get('specialty','')} · {s.get('diagnosis','')}")
                if c2.button("🗑 Delete", key=f"del_slide_{s['slide_id']}"):
                    delete_slide(s["slide_id"])
                    st.rerun()

    slides = list_slides()
    if not slides:
        st.info("No real slides uploaded yet — showing a placeholder pattern below so you "
                "can try the pan/zoom/annotation mechanics right now.")
        render_microscope(None)
        return

    labels = {s["slide_id"]: f"{s['name']} ({s.get('specialty','')})" for s in slides}
    picked_id = st.selectbox("Select a slide", list(labels.keys()), format_func=lambda k: labels[k])
    full_row = get_slide(picked_id)
    if full_row:
        if full_row.get("diagnosis"):
            st.caption(f"**Diagnosis:** {full_row['diagnosis']}")
        if full_row.get("description"):
            st.caption(full_row["description"])
        render_microscope(full_row)
    else:
        st.error("Could not load that slide.")
