"""
═══════════════════════════════════════════════════════════════════════════
  MLS Virtual Hospital — Image Practice Library (Phase 2)
  ─────────────────────────────────────────────────────────────────────────
  Bulk image practice library where students browse curated medical images
  (X-rays, CTs, ECGs, dermatology, etc.) and practice interpretation.
  Each image has clinical context, key findings, and diagnosis.
  Admin curates images via Faculty Portal.

  AUTHOR: Hiba Hamdar — Academy of Medical Learning Skills
  COPYRIGHT (c) 2026 — All Rights Reserved
═══════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import streamlit as st
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import uuid
import requests


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
MODALITIES = [
    "X-ray (CXR)", "X-ray (other)", "CT scan", "MRI", "Ultrasound",
    "ECG", "EEG", "Echocardiogram", "Endoscopy", "Dermatology photo",
    "Ophthalmology / fundus", "Histology / pathology", "Clinical photo (other)",
]

SYSTEMS = [
    "cardio", "respiratory", "abdomen", "neuro", "musculoskeletal",
    "endocrine", "renal", "hematology", "infectious", "dermatology",
    "ophthalmology", "ent", "obgyn", "pediatrics", "emergency",
    "trauma", "oncology", "general",
]

DIFFICULTIES = ["basic", "intermediate", "advanced"]


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def _safe_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def _supabase_url() -> str:
    return _safe_secret("SUPABASE_URL", "").rstrip("/")


def _supabase_key() -> str:
    return _safe_secret("SUPABASE_KEY", "")


def _sb_headers() -> dict:
    key = _supabase_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _sb_available() -> bool:
    return bool(_supabase_url() and _supabase_key())


def _get_user_id() -> str:
    auth = st.session_state.get("auth_user", {}) or {}
    return str(auth.get("id") or auth.get("email") or "anon")


def _get_user_name() -> str:
    auth = st.session_state.get("auth_user", {}) or {}
    return auth.get("name") or auth.get("email") or "Student"


def _is_admin() -> bool:
    auth = st.session_state.get("auth_user", {}) or {}
    role = (auth.get("role") or "").lower()
    if role in ("admin", "faculty"):
        return True
    admin_email = _safe_secret("ADMIN_EMAIL", "hamdarhiba95@gmail.com").strip().lower()
    user_email = (auth.get("email") or "").strip().lower()
    return bool(user_email and admin_email and user_email == admin_email)


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════════
def list_published_images(
    modality: Optional[str] = None,
    system: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/image_library"
    params = {
        "status": "eq.published",
        "select": "*",
        "order":  "created_at.desc",
        "limit":  str(limit),
    }
    if modality and modality != "All":
        params["modality"] = f"eq.{modality}"
    if system and system != "All":
        params["system"] = f"eq.{system}"
    if difficulty and difficulty != "All":
        params["difficulty"] = f"eq.{difficulty}"
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return r.json() or []
    except Exception as e:
        print(f"[image_library] list error: {e}")
    return []


def list_drafts() -> List[Dict[str, Any]]:
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/image_library"
    params = {"status": "eq.draft", "select": "*", "order": "created_at.desc"}
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return r.json() or []
    except Exception:
        pass
    return []


def get_pending_images_count() -> int:
    return len(list_drafts())


def list_images_for_case(case_id: str) -> List[Dict[str, Any]]:
    """Return all PUBLISHED images linked to a specific case."""
    if not _sb_available() or not case_id:
        return []
    url = f"{_supabase_url()}/rest/v1/image_library"
    params = {
        "status":  "eq.published",
        "case_id": f"eq.{case_id}",
        "select":  "*",
        "order":   "created_at.asc",
    }
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return r.json() or []
    except Exception as e:
        print(f"[image_library] list_for_case error: {e}")
    return []


def render_case_linked_images(case_id: str) -> bool:
    """Display all images linked to a case inline. Returns True if any were shown."""
    if not case_id:
        return False
    images = list_images_for_case(case_id)
    if not images:
        return False

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0e7490,#0369a1);color:white;
                border-radius:12px;padding:1rem 1.4rem;margin-top:1rem;margin-bottom:.6rem;">
      <div style="font-size:1.1rem;font-weight:800;">
        🩻 Imaging Studies ({len(images)})
      </div>
      <div style="font-size:.82rem;opacity:.9;margin-top:.2rem;">
        Real radiological images for this case. Examine them carefully.
      </div>
    </div>
    """, unsafe_allow_html=True)

    for img in images:
        image_id = img.get("image_id", "")
        title = img.get("title", "(no title)")
        url = img.get("image_url", "")
        modality = img.get("modality", "")

        st.markdown(f"**{title}** · _{modality}_")
        if url:
            try:
                st.image(url, use_column_width=True)
            except Exception:
                st.warning(f"⚠️ Could not load image. URL: {url[:60]}...")

        # Findings reveal mechanism per image
        reveal_key = f"reveal_case_img_{image_id}"
        if not st.session_state.get(reveal_key, False):
            if st.button(f"👁️ Reveal findings for this image",
                          key=f"crl_btn_{image_id}",
                          use_container_width=True):
                st.session_state[reveal_key] = True
                record_view(image_id)
                st.rerun()
        else:
            findings = img.get("key_findings", "")
            st.markdown(f"""
            <div style="background:#fffbeb;border-left:3px solid #f59e0b;
                        border-radius:6px;padding:.7rem .9rem;
                        font-size:.85rem;color:#78350f;line-height:1.5;
                        margin-bottom:.4rem;">
              <b style="color:#d97706;">🔍 Key findings:</b><br>{findings}
            </div>
            """, unsafe_allow_html=True)
            teaching = img.get("teaching_points", "")
            if teaching:
                st.markdown(f"""
                <div style="background:#f1f5f9;border-left:3px solid #475569;
                            border-radius:6px;padding:.6rem .8rem;
                            font-size:.78rem;color:#1e293b;line-height:1.5;
                            margin-bottom:.4rem;">
                  <b>📚 Teaching:</b> {teaching}
                </div>
                """, unsafe_allow_html=True)
            source = img.get("source", "")
            if source:
                st.caption(f"Source: {source}")
        st.markdown("---")
    return True


def list_cases_for_picker() -> List[Dict[str, str]]:
    """Return a list of all cases (xlsx + AI-generated) for the admin's
    case-picker dropdown. Returns dicts with 'case_id' and 'display_label'."""
    out = []
    try:
        import sys
        host = sys.modules.get("__main__")
        if host and hasattr(host, "load_cases"):
            df = host.load_cases()
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    cid = str(row.get("Case_ID", "")).strip()
                    title = str(row.get("Title", "")).strip()[:60]
                    diag = str(row.get("Final_Diagnosis", "")).strip()[:50]
                    if cid:
                        label = f"[{cid}] {title} → {diag}" if title else f"[{cid}] {diag}"
                        out.append({"case_id": cid, "display_label": label})
    except Exception as e:
        print(f"[image_library] could not load cases: {e}")
    return out


def insert_image(rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _sb_available():
        return None
    url = f"{_supabase_url()}/rest/v1/image_library"
    try:
        r = requests.post(url, headers=_sb_headers(), json=rec, timeout=8)
        if r.status_code in (200, 201):
            return rec
    except Exception as e:
        print(f"[image_library] insert error: {e}")
    return None


def update_image(image_id: str, updates: Dict[str, Any]) -> bool:
    if not _sb_available():
        return False
    url = f"{_supabase_url()}/rest/v1/image_library"
    try:
        r = requests.patch(url, headers=_sb_headers(),
                            params={"image_id": f"eq.{image_id}"},
                            json=updates, timeout=8)
        return r.status_code in (200, 204)
    except Exception:
        return False


def delete_image(image_id: str) -> bool:
    if not _sb_available():
        return False
    url = f"{_supabase_url()}/rest/v1/image_library"
    try:
        r = requests.delete(url, headers=_sb_headers(),
                             params={"image_id": f"eq.{image_id}"},
                             timeout=8)
        return r.status_code in (200, 204)
    except Exception:
        return False


def record_view(image_id: str) -> None:
    """Record that a student viewed an image (for analytics)."""
    if not _sb_available():
        return
    url = f"{_supabase_url()}/rest/v1/image_views"
    rec = {
        "view_id":    "iv_" + uuid.uuid4().hex[:10],
        "user_id":    _get_user_id(),
        "user_name":  _get_user_name(),
        "image_id":   image_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        requests.post(url, headers=_sb_headers(), json=rec, timeout=4)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# UI: STUDENT-FACING — IMAGE PRACTICE
# ═══════════════════════════════════════════════════════════════════════════
def render_image_practice_page() -> None:
    st.markdown(
        '<div class="section-header">🩻 Image Practice Library</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div style="background:linear-gradient(135deg,#0a2540,#0e7490);color:white;
                border-radius:14px;padding:1.4rem 1.6rem;margin-bottom:1rem;">
      <div style="font-size:1.3rem;font-weight:800;margin-bottom:.4rem;">
        Practice Medical Imaging Interpretation
      </div>
      <div style="font-size:.92rem;opacity:.92;line-height:1.5;">
        Browse curated medical images. For each one, try to identify findings
        on your own, then reveal the expert interpretation. Earn XP as you go.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Filters
    c1, c2, c3 = st.columns(3)
    with c1:
        mod_filter = st.selectbox(
            "Modality:", ["All"] + MODALITIES, key="img_mod_filter"
        )
    with c2:
        sys_filter = st.selectbox(
            "System:", ["All"] + SYSTEMS, key="img_sys_filter"
        )
    with c3:
        diff_filter = st.selectbox(
            "Difficulty:", ["All"] + DIFFICULTIES, key="img_diff_filter"
        )

    images = list_published_images(
        modality=mod_filter, system=sys_filter, difficulty=diff_filter
    )

    if not images:
        st.info(
            "No images available for these filters yet. Ask your admin to "
            "add more images, or try changing the filters."
        )
        return

    st.markdown(f"**{len(images)} image{'s' if len(images)!=1 else ''} found**")

    # Display in 2-column grid
    for i in range(0, len(images), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j < len(images):
                with col:
                    _render_image_card(images[i + j])


def _render_image_card(img: Dict[str, Any]) -> None:
    image_id = img.get("image_id", "")
    title = img.get("title", "(no title)")
    url = img.get("image_url", "")
    modality = img.get("modality", "")
    system = img.get("system", "")
    difficulty = img.get("difficulty", "")

    diff_colors = {"basic": "#10b981", "intermediate": "#f59e0b",
                    "advanced": "#dc2626"}
    diff_color = diff_colors.get(difficulty, "#64748b")

    st.markdown(f"""
    <div style="background:white;border:1.5px solid #e2e8f0;border-radius:12px;
                padding:.6rem .8rem;margin-bottom:.4rem;">
      <div style="display:flex;justify-content:space-between;align-items:center;
                  margin-bottom:.3rem;">
        <div style="font-weight:700;color:#0f172a;font-size:.92rem;">
          {title}
        </div>
        <span style="background:{diff_color}22;color:{diff_color};
                     padding:.15rem .55rem;border-radius:999px;
                     font-size:.65rem;font-weight:700;">
          {difficulty.upper()}
        </span>
      </div>
      <div style="font-size:.72rem;color:#64748b;">
        {modality} · {system}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Display image
    if url:
        try:
            st.image(url, use_column_width=True)
        except Exception:
            st.warning(f"⚠️ Could not load image. URL: {url[:60]}...")

    # Clinical context
    context = img.get("clinical_context", "")
    if context:
        st.markdown(f"""
        <div style="background:#f0f9ff;border-left:3px solid #0ea5e9;
                    border-radius:6px;padding:.6rem .8rem;
                    font-size:.82rem;color:#0c4a6e;line-height:1.4;
                    margin-bottom:.5rem;">
          <b>Clinical context:</b> {context}
        </div>
        """, unsafe_allow_html=True)

    # Reveal mechanism
    findings_key = f"reveal_findings_{image_id}"
    diagnosis_key = f"reveal_diagnosis_{image_id}"
    xp_awarded_key = f"xp_image_{image_id}"

    if not st.session_state.get(findings_key, False):
        if st.button("👁️ Reveal key findings",
                      key=f"rf_btn_{image_id}",
                      use_container_width=True):
            st.session_state[findings_key] = True
            record_view(image_id)
            st.rerun()
    else:
        findings = img.get("key_findings", "")
        st.markdown(f"""
        <div style="background:#fffbeb;border-left:3px solid #f59e0b;
                    border-radius:6px;padding:.7rem .9rem;
                    font-size:.85rem;color:#78350f;line-height:1.5;
                    margin-bottom:.5rem;">
          <b style="color:#d97706;">🔍 Key findings:</b><br>
          {findings or '(no findings recorded)'}
        </div>
        """, unsafe_allow_html=True)

        if not st.session_state.get(diagnosis_key, False):
            if st.button("💡 Reveal diagnosis",
                          key=f"rd_btn_{image_id}",
                          use_container_width=True,
                          type="primary"):
                st.session_state[diagnosis_key] = True
                # Award XP once per image
                if not st.session_state.get(xp_awarded_key, False):
                    try:
                        from tier1_features import award_xp
                        award_xp("image_practice", amount=10, toast=False)
                        st.session_state[xp_awarded_key] = True
                    except Exception:
                        pass
                st.rerun()
        else:
            diagnosis = img.get("diagnosis", "")
            teaching = img.get("teaching_points", "")
            st.markdown(f"""
            <div style="background:#dcfce7;border-left:3px solid #16a34a;
                        border-radius:6px;padding:.7rem .9rem;
                        font-size:.88rem;color:#14532d;line-height:1.55;
                        margin-bottom:.4rem;">
              <b style="color:#15803d;">✓ Diagnosis:</b> {diagnosis or '—'}
            </div>
            """, unsafe_allow_html=True)
            if teaching:
                st.markdown(f"""
                <div style="background:#f1f5f9;border-left:3px solid #475569;
                            border-radius:6px;padding:.6rem .8rem;
                            font-size:.78rem;color:#1e293b;line-height:1.5;
                            margin-bottom:.5rem;">
                  <b>📚 Teaching points:</b><br>
                  {teaching}
                </div>
                """, unsafe_allow_html=True)

            source = img.get("source", "")
            if source:
                st.caption(f"Source: {source}")

    st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════
# UI: ADMIN PANEL
# ═══════════════════════════════════════════════════════════════════════════
def render_image_admin_panel() -> None:
    if not _is_admin():
        st.error("This page is for admins only.")
        return

    st.markdown(
        '<div class="section-header">🩻 Image Library Manager</div>',
        unsafe_allow_html=True
    )

    drafts = list_drafts()
    published = list_published_images(limit=500)

    tabs = st.tabs([
        "➕ Add New Image",
        f"⏳ Drafts ({len(drafts)})",
        f"✓ Published ({len(published)})",
        "📊 Stats",
    ])

    with tabs[0]:
        _admin_add_new_tab()
    with tabs[1]:
        _admin_drafts_tab(drafts)
    with tabs[2]:
        _admin_published_tab(published)
    with tabs[3]:
        _admin_stats_tab()


def _admin_add_new_tab() -> None:
    st.markdown(
        "**Add a new image to the library.** Paste a direct image URL "
        "(from Radiopaedia, NIH Open-i, Wikimedia, or your own GitHub repo) "
        "and fill in the metadata."
    )
    st.caption(
        "💡 You can OPTIONALLY link this image to a specific case in your library. "
        "Linked images appear inline when students view that case AND in the "
        "general Image Practice library. Unlinked images only appear in Image Practice."
    )

    # Load cases for the picker
    cases_for_picker = list_cases_for_picker()
    case_options = ["— No case (standalone image) —"] + [
        c["display_label"] for c in cases_for_picker
    ]
    case_id_map = {"— No case (standalone image) —": ""}
    for c in cases_for_picker:
        case_id_map[c["display_label"]] = c["case_id"]

    with st.form("add_image_form"):
        title = st.text_input(
            "Title (short descriptive):",
            placeholder="e.g., 'Right Middle Lobe Pneumonia on CXR'",
        )
        url = st.text_input(
            "Image URL (direct link to .jpg/.png):",
            placeholder="https://prod-images-static.radiopaedia.org/...",
        )

        # Optional case link
        linked_case_label = st.selectbox(
            "🔗 Link to case (optional):",
            case_options,
            help="Leave as 'No case' for standalone images. Pick a case "
                  "to make this image appear inline when students view that case.",
        )
        linked_case_id = case_id_map.get(linked_case_label, "")

        col1, col2, col3 = st.columns(3)
        with col1:
            modality = st.selectbox("Modality:", MODALITIES, key="add_mod")
        with col2:
            system = st.selectbox("System:", SYSTEMS, key="add_sys")
        with col3:
            difficulty = st.selectbox("Difficulty:", DIFFICULTIES,
                                       index=1, key="add_diff")

        clinical_context = st.text_area(
            "Clinical context (patient history):",
            placeholder=(
                "e.g., '45-year-old male with 3 days of fever, productive "
                "cough, and right-sided chest pain.'"
            ),
            height=80,
        )

        key_findings = st.text_area(
            "Key findings (what students should notice):",
            placeholder=(
                "e.g., 'Right middle lobe consolidation with air bronchograms. "
                "No pleural effusion.'"
            ),
            height=100,
        )

        diagnosis = st.text_input(
            "Diagnosis:",
            placeholder="e.g., 'Community-acquired pneumonia'",
        )

        teaching_points = st.text_area(
            "Teaching points (optional):",
            placeholder=(
                "e.g., 'Air bronchograms suggest air-filled airways within "
                "consolidated lung tissue.'"
            ),
            height=80,
        )

        source = st.text_input(
            "Source / attribution (required for legal use):",
            placeholder="e.g., 'Radiopaedia case 12345 (CC BY-NC-SA)'",
        )

        submitted = st.form_submit_button(
            "💾 Save as draft", type="primary", use_container_width=True
        )

        if submitted:
            if not all([title.strip(), url.strip(), clinical_context.strip(),
                         key_findings.strip(), diagnosis.strip()]):
                st.error(
                    "Required: title, URL, clinical context, key findings, diagnosis."
                )
                return
            if not source.strip():
                st.warning("⚠️ Source attribution is empty. Add it before publishing.")

            image_id = "img_" + uuid.uuid4().hex[:12]
            record = {
                "image_id":         image_id,
                "title":            title.strip(),
                "image_url":        url.strip(),
                "case_id":          linked_case_id,
                "modality":         modality,
                "system":           system,
                "difficulty":       difficulty,
                "clinical_context": clinical_context.strip(),
                "key_findings":     key_findings.strip(),
                "diagnosis":        diagnosis.strip(),
                "teaching_points":  teaching_points.strip(),
                "source":           source.strip(),
                "status":           "draft",
                "added_by":         _get_user_name(),
                "view_count":       0,
                "created_at":       datetime.now(timezone.utc).isoformat(),
            }
            result = insert_image(record)
            if result:
                link_msg = (f" (linked to case {linked_case_id})"
                             if linked_case_id else " (standalone)")
                st.success(f"✅ Image saved as draft{link_msg}")
                st.info("Go to **⏳ Drafts** tab to review and publish.")
            else:
                st.error("Could not save. Check Supabase connection.")


def _admin_drafts_tab(drafts: List[Dict[str, Any]]) -> None:
    if not drafts:
        st.info("✓ No drafts. Use **➕ Add New Image** to add images.")
        return

    st.markdown(f"**{len(drafts)} draft{'s' if len(drafts)!=1 else ''} awaiting publication**")

    for img in drafts:
        image_id = img.get("image_id", "")
        title = img.get("title", "(no title)")
        with st.expander(f"📋 {title}", expanded=False):
            _render_editable_draft(img)


def _render_editable_draft(img: Dict[str, Any]) -> None:
    image_id = img.get("image_id", "")
    url = img.get("image_url", "")

    if url:
        try:
            st.image(url, caption=f"Preview: {img.get('title', '')}",
                      use_column_width=True)
        except Exception:
            st.warning(f"⚠️ Could not preview image. Check the URL.")

    # Load cases for the picker
    cases_for_picker = list_cases_for_picker()
    case_options = ["— No case (standalone image) —"] + [
        c["display_label"] for c in cases_for_picker
    ]
    case_id_map = {"— No case (standalone image) —": ""}
    label_for_id = {"": "— No case (standalone image) —"}
    for c in cases_for_picker:
        case_id_map[c["display_label"]] = c["case_id"]
        label_for_id[c["case_id"]] = c["display_label"]
    current_case_id = img.get("case_id", "") or ""
    current_label = label_for_id.get(current_case_id, "— No case (standalone image) —")
    if current_label not in case_options:
        case_options.insert(1, current_label)

    with st.form(f"edit_img_{image_id}"):
        title = st.text_input("Title:", value=img.get("title", ""),
                               key=f"t_{image_id}")
        url_edit = st.text_input("URL:", value=img.get("image_url", ""),
                                  key=f"u_{image_id}")

        linked_case_label = st.selectbox(
            "🔗 Link to case (optional):",
            case_options,
            index=case_options.index(current_label) if current_label in case_options else 0,
            key=f"lc_{image_id}",
        )
        linked_case_id = case_id_map.get(linked_case_label, current_case_id)

        col1, col2, col3 = st.columns(3)
        with col1:
            cur_mod = img.get("modality", MODALITIES[0])
            idx = MODALITIES.index(cur_mod) if cur_mod in MODALITIES else 0
            modality = st.selectbox("Modality:", MODALITIES, index=idx,
                                      key=f"m_{image_id}")
        with col2:
            cur_sys = img.get("system", SYSTEMS[0])
            idx = SYSTEMS.index(cur_sys) if cur_sys in SYSTEMS else 0
            system = st.selectbox("System:", SYSTEMS, index=idx,
                                    key=f"s_{image_id}")
        with col3:
            cur_diff = img.get("difficulty", "intermediate")
            idx = DIFFICULTIES.index(cur_diff) if cur_diff in DIFFICULTIES else 1
            difficulty = st.selectbox("Difficulty:", DIFFICULTIES, index=idx,
                                        key=f"d_{image_id}")

        clinical_context = st.text_area(
            "Clinical context:", value=img.get("clinical_context", ""),
            height=80, key=f"c_{image_id}")
        key_findings = st.text_area(
            "Key findings:", value=img.get("key_findings", ""),
            height=100, key=f"k_{image_id}")
        diagnosis = st.text_input(
            "Diagnosis:", value=img.get("diagnosis", ""),
            key=f"dx_{image_id}")
        teaching_points = st.text_area(
            "Teaching points:", value=img.get("teaching_points", ""),
            height=80, key=f"tp_{image_id}")
        source = st.text_input(
            "Source:", value=img.get("source", ""),
            key=f"src_{image_id}")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            publish = st.form_submit_button(
                "✓ Publish", type="primary", use_container_width=True
            )
        with col_b:
            save = st.form_submit_button("💾 Save edits",
                                          use_container_width=True)
        with col_c:
            reject = st.form_submit_button("✗ Delete",
                                            use_container_width=True)

        if publish or save or reject:
            updates = {
                "title":            title.strip(),
                "image_url":        url_edit.strip(),
                "case_id":          linked_case_id,
                "modality":         modality,
                "system":           system,
                "difficulty":       difficulty,
                "clinical_context": clinical_context.strip(),
                "key_findings":     key_findings.strip(),
                "diagnosis":        diagnosis.strip(),
                "teaching_points":  teaching_points.strip(),
                "source":           source.strip(),
            }
            if publish:
                updates["status"] = "published"
                updates["published_at"] = datetime.now(timezone.utc).isoformat()
                updates["published_by"] = _get_user_name()
                if update_image(image_id, updates):
                    st.success("✓ Published — students can now see it.")
                    st.rerun()
                else:
                    st.error("Could not publish.")
            elif reject:
                if delete_image(image_id):
                    st.warning("Deleted.")
                    st.rerun()
            elif save:
                if update_image(image_id, updates):
                    st.success("💾 Saved.")
                    st.rerun()


def _admin_published_tab(published: List[Dict[str, Any]]) -> None:
    if not published:
        st.info("No published images yet.")
        return

    st.markdown(f"**{len(published)} published images live in the library**")

    by_mod = {}
    for img in published:
        mod = img.get("modality", "Other")
        by_mod.setdefault(mod, []).append(img)

    for mod, imgs in sorted(by_mod.items()):
        with st.expander(f"📷 {mod} ({len(imgs)})", expanded=False):
            for img in imgs:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(
                        f"**{img.get('title', '?')}** · "
                        f"{img.get('system', '')} · "
                        f"{img.get('difficulty', '')} · "
                        f"Dx: {img.get('diagnosis', '?')}"
                    )
                with col2:
                    if st.button("Move to draft",
                                  key=f"unp_{img.get('image_id')}",
                                  use_container_width=True):
                        if update_image(img.get("image_id", ""),
                                          {"status": "draft"}):
                            st.info("Moved.")
                            st.rerun()
                    if st.button("🗑️ Delete",
                                  key=f"del_{img.get('image_id')}",
                                  use_container_width=True):
                        if delete_image(img.get("image_id", "")):
                            st.warning("Deleted.")
                            st.rerun()
                st.markdown("---")


def _admin_stats_tab() -> None:
    if not _sb_available():
        st.error("Database not configured.")
        return

    stats = {}
    for status in ["draft", "published"]:
        url = f"{_supabase_url()}/rest/v1/image_library"
        try:
            r = requests.get(url, headers=_sb_headers(),
                             params={"status": f"eq.{status}",
                                     "select": "image_id"},
                             timeout=8)
            stats[status] = len(r.json() or []) if r.status_code == 200 else 0
        except Exception:
            stats[status] = 0

    try:
        url = f"{_supabase_url()}/rest/v1/image_views"
        r = requests.get(url, headers=_sb_headers(),
                         params={"select": "view_id"}, timeout=8)
        views = len(r.json() or []) if r.status_code == 200 else 0
    except Exception:
        views = 0

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("📝 Drafts", stats["draft"])
    with c2:
        st.metric("✓ Published", stats["published"])
    with c3:
        st.metric("👁️ Total views", views)


# ═══════════════════════════════════════════════════════════════════════════
# SUPABASE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════
IMAGE_LIBRARY_SCHEMA = """
-- ─────────────────────────────────────────────────────────────────────
-- Image Practice Library — schema
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.image_library (
    image_id          text PRIMARY KEY,
    title             text NOT NULL,
    image_url         text NOT NULL,
    case_id           text DEFAULT '',
    modality          text DEFAULT '',
    system            text DEFAULT '',
    difficulty        text DEFAULT 'intermediate',
    clinical_context  text DEFAULT '',
    key_findings      text DEFAULT '',
    diagnosis         text DEFAULT '',
    teaching_points   text DEFAULT '',
    source            text DEFAULT '',
    status            text DEFAULT 'draft',
    added_by          text DEFAULT '',
    published_by      text DEFAULT '',
    published_at      timestamptz,
    view_count        integer DEFAULT 0,
    created_at        timestamptz DEFAULT now()
);

-- Migration for existing tables (adds case_id column if it doesn't exist)
ALTER TABLE public.image_library ADD COLUMN IF NOT EXISTS case_id text DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_img_status
    ON public.image_library(status, created_at);
CREATE INDEX IF NOT EXISTS idx_img_filters
    ON public.image_library(modality, system, difficulty);
CREATE INDEX IF NOT EXISTS idx_img_case_link
    ON public.image_library(case_id, status) WHERE case_id != '';

ALTER TABLE public.image_library ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all image_library" ON public.image_library;
CREATE POLICY "Allow all image_library" ON public.image_library
    FOR ALL USING (true) WITH CHECK (true);

CREATE TABLE IF NOT EXISTS public.image_views (
    view_id     text PRIMARY KEY,
    user_id     text NOT NULL,
    user_name   text DEFAULT '',
    image_id    text NOT NULL,
    created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_iv_user ON public.image_views(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_iv_img ON public.image_views(image_id);

ALTER TABLE public.image_views ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all image_views" ON public.image_views;
CREATE POLICY "Allow all image_views" ON public.image_views
    FOR ALL USING (true) WITH CHECK (true);
"""


if __name__ == "__main__":
    print("MLS Virtual Hospital — Image Practice Library")
    print("=" * 60)
    print(IMAGE_LIBRARY_SCHEMA)
