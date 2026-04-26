# ════════════════════════════════════════════════════════════════════════════
#  CLINICAL HELPERS — Real Data + Specialist Models + Feedback Loop
#  ┌──────────────────────────────────────────────────────────────────────┐
#  │  1. PubMed Case Report Retrieval (real, verified, NCBI E-utilities)  │
#  │  2. TorchXRayVision Specialist Chest X-Ray Analysis (Path B)         │
#  │  3. Student Feedback Loop on AI Findings (Path A)                    │
#  └──────────────────────────────────────────────────────────────────────┘
#
#  WIRE-IN (app.py edits handled separately):
#  - This module is imported once at top of app.py
#  - DocCollab calls fetch_pubmed_case_reports() instead of AI generation
#  - Imaging page calls specialist_chest_xray_analysis() + render_finding_feedback()
# ════════════════════════════════════════════════════════════════════════════

import streamlit as st
import requests
import time
from datetime import datetime
import xml.etree.ElementTree as ET

# ── Optional specialist medical imaging model ────────────────────────────────
# TorchXRayVision: trained on NIH ChestX-ray14 + CheXpert + MIMIC-CXR + PadChest
# Outputs 18 pathology probabilities per image. ~150MB download on first use.
try:
    import torch
    import torchxrayvision as xrv
    import numpy as np
    from PIL import Image as _PILImage
    import io as _io
    XRV_OK = True
except Exception:
    XRV_OK = False


# ════════════════════════════════════════════════════════════════════════════
#  PART 1 — REAL PUBMED CASE REPORT RETRIEVAL
# ════════════════════════════════════════════════════════════════════════════

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Public NCBI API: 3 req/sec without API key, 10 req/sec with one.
# Get a free API key: https://www.ncbi.nlm.nih.gov/account/ → API Keys
# Then add to .streamlit/secrets.toml:
#   NCBI_API_KEY = "your_key_here"

def _ncbi_api_key() -> str:
    """Return NCBI API key from secrets if set, else empty string."""
    try:
        return str(st.secrets.get("NCBI_API_KEY", "")).strip()
    except Exception:
        return ""


def _build_pubmed_query(diagnosis: str, age_sex: str = "", presenting: str = "") -> str:
    """Build a focused PubMed query string for case reports."""
    q = diagnosis.strip()
    if not q:
        return ""
    # Strip noise
    for noise in ("?", "(suspected)", "[probable]"):
        q = q.replace(noise, "").strip()
    # Add filters: case reports + last 10 years + has abstract + English
    return (
        f'("{q}"[Title/Abstract] OR "{q}"[MeSH Terms]) '
        f'AND "case reports"[Publication Type] '
        f'AND "last 10 years"[PDat] '
        f'AND hasabstract[text] '
        f'AND english[Language]'
    )


def _esearch_pmids(query: str, retmax: int = 20) -> list:
    """Search PubMed and return list of PMIDs. Empty list on failure."""
    if not query:
        return []
    url = f"{NCBI_BASE}/esearch.fcgi"
    params = {
        "db":      "pubmed",
        "term":    query,
        "retmode": "json",
        "retmax":  retmax,
        "sort":    "relevance",
    }
    api_key = _ncbi_api_key()
    if api_key:
        params["api_key"] = api_key
    try:
        r = requests.get(url, params=params, timeout=8)
        if r.status_code == 200:
            return r.json().get("esearchresult", {}).get("idlist", [])
    except Exception:
        pass
    return []


def _efetch_case_details(pmids: list) -> list:
    """
    Fetch detailed metadata + abstract for a list of PMIDs.
    Returns list of dicts with: pmid, title, authors, journal, year, abstract, country, url
    """
    if not pmids:
        return []
    url = f"{NCBI_BASE}/efetch.fcgi"
    params = {
        "db":      "pubmed",
        "id":      ",".join(pmids),
        "retmode": "xml",
    }
    api_key = _ncbi_api_key()
    if api_key:
        params["api_key"] = api_key
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
    except Exception:
        return []

    results = []
    for art in root.findall(".//PubmedArticle"):
        try:
            pmid_el = art.find(".//PMID")
            pmid    = pmid_el.text if pmid_el is not None else ""

            title_el = art.find(".//ArticleTitle")
            title    = "".join(title_el.itertext()) if title_el is not None else "(no title)"

            # Abstract — may be split into multiple sections
            abs_parts = []
            for ab in art.findall(".//Abstract/AbstractText"):
                lbl = ab.get("Label", "")
                txt = "".join(ab.itertext()) if ab.text or list(ab) else ""
                if lbl and txt:
                    abs_parts.append(f"{lbl}: {txt}")
                elif txt:
                    abs_parts.append(txt)
            abstract = " ".join(abs_parts).strip()

            # Authors (first 3)
            authors = []
            for au in art.findall(".//AuthorList/Author")[:3]:
                last = au.find("LastName")
                init = au.find("Initials")
                if last is not None:
                    name = last.text or ""
                    if init is not None and init.text:
                        name += f" {init.text}"
                    authors.append(name)
            if len(art.findall(".//AuthorList/Author")) > 3:
                authors.append("et al.")
            author_str = ", ".join(authors) if authors else "Unknown authors"

            # Journal + year
            journal_el = art.find(".//Journal/Title") or art.find(".//Journal/ISOAbbreviation")
            journal    = journal_el.text if journal_el is not None else ""

            year_el = art.find(".//PubDate/Year") or art.find(".//PubDate/MedlineDate")
            year    = ""
            if year_el is not None and year_el.text:
                year = year_el.text[:4]

            # Country (from MedlineJournalInfo)
            country_el = art.find(".//MedlineJournalInfo/Country")
            country    = country_el.text if country_el is not None else ""

            results.append({
                "pmid":     pmid,
                "title":    title.strip(),
                "authors":  author_str,
                "journal":  journal.strip() if journal else "Unknown journal",
                "year":     year,
                "abstract": abstract or "(No abstract available)",
                "country":  country.strip() if country else "International",
                "url":      f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        except Exception:
            continue
    return results


def fetch_pubmed_case_reports(diagnosis: str, age_sex: str = "",
                              presenting: str = "", max_results: int = 15) -> dict:
    """
    Fetch real, verified case reports from PubMed.

    Returns:
      {
        "ok": True/False,
        "cases": [...],          # list of case dicts (see _efetch_case_details)
        "query": "...",          # the PubMed query string used
        "search_url": "...",     # link to do the same search on PubMed website
        "error": "..."           # if ok==False
      }
    """
    if not diagnosis or not diagnosis.strip() or diagnosis.strip() == "?":
        return {"ok": False, "cases": [], "query": "", "search_url": "",
                "error": "No diagnosis provided to search."}

    # Cache to avoid repeated lookups
    cache = st.session_state.setdefault("_pubmed_case_cache", {})
    cache_key = f"{diagnosis.strip().lower()}::{max_results}"
    if cache_key in cache:
        return cache[cache_key]

    query = _build_pubmed_query(diagnosis, age_sex, presenting)
    pmids = _esearch_pmids(query, retmax=max_results)

    # If strict query returned nothing, retry with broader query
    if not pmids:
        broad_query = f'"{diagnosis.strip()}"[Title/Abstract] AND hasabstract[text]'
        pmids = _esearch_pmids(broad_query, retmax=max_results)
        query = broad_query

    if not pmids:
        return {"ok": False, "cases": [], "query": query, "search_url": "",
                "error": f"No case reports found on PubMed for '{diagnosis}'."}

    # Small delay to respect NCBI rate limits between esearch and efetch
    time.sleep(0.34 if not _ncbi_api_key() else 0.1)
    cases = _efetch_case_details(pmids)

    # Build PubMed website search URL for "see all" link
    q_url = query.replace(" ", "+").replace('"', "%22")
    search_url = f"https://pubmed.ncbi.nlm.nih.gov/?term={q_url}"

    result = {
        "ok":         len(cases) > 0,
        "cases":      cases,
        "query":      query,
        "search_url": search_url,
        "error":      "" if cases else "PubMed returned PMIDs but no abstracts could be parsed.",
    }
    cache[cache_key] = result
    return result


def render_pubmed_case_card(case: dict, idx: int) -> None:
    """Render a single real PubMed case report as an expandable card."""
    title    = case.get("title", "Untitled")
    authors  = case.get("authors", "")
    journal  = case.get("journal", "")
    year     = case.get("year", "")
    country  = case.get("country", "")
    abstract = case.get("abstract", "")
    pmid     = case.get("pmid", "")
    url      = case.get("url", "#")

    # Truncate long abstract for preview
    abstract_preview = abstract[:600] + ("..." if len(abstract) > 600 else "")

    header = f"**Case {idx+1}** · {country} · {year} · {title[:80]}"
    with st.expander(header, expanded=(idx < 2)):
        st.markdown(f"""
        <div style="background:#f8fafc;border-radius:8px;padding:.8rem 1rem;margin-bottom:.6rem;">
          <div style="font-weight:700;color:#0a2540;font-size:.9rem;margin-bottom:.3rem;">{title}</div>
          <div style="font-size:.78rem;color:#475569;">
            <b>Authors:</b> {authors}<br>
            <b>Journal:</b> <i>{journal}</i> ({year})<br>
            <b>Country:</b> {country} · <b>PMID:</b> <code>{pmid}</code>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**Abstract:**")
        st.markdown(
            f"<div style='background:white;border-left:4px solid #0e7490;"
            f"padding:.7rem 1rem;border-radius:0 8px 8px 0;font-size:.83rem;"
            f"color:#1e293b;line-height:1.55;'>{abstract_preview}</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<a href="{url}" target="_blank" '
            f'style="display:inline-block;margin-top:.6rem;background:#eff6ff;'
            f'border:1px solid #3b82f6;border-radius:6px;padding:.4rem .9rem;'
            f'text-decoration:none;color:#1e40af;font-size:.8rem;font-weight:600;">'
            f'📄 Read full article on PubMed (PMID {pmid})</a>',
            unsafe_allow_html=True,
        )


# ════════════════════════════════════════════════════════════════════════════
#  PART 2 — SPECIALIST CHEST X-RAY ANALYSIS (TorchXRayVision)
# ════════════════════════════════════════════════════════════════════════════

# Module-level cache for the model — load once per session
_XRV_MODEL = None

# Modalities that should trigger specialist chest X-ray analysis
CHEST_XRAY_MODALITIES = {
    "chest x-ray", "chest xray", "cxr", "chest x-ray (pa)", "chest x-ray (ap)",
    "chest x-ray pa", "chest x-ray ap", "chest radiograph",
}

def is_chest_xray_modality(modality: str) -> bool:
    """Return True if modality string indicates a chest X-ray."""
    if not modality:
        return False
    return modality.strip().lower() in CHEST_XRAY_MODALITIES or "chest x" in modality.lower()


def _load_xrv_model():
    """Load TorchXRayVision DenseNet model (cached). Returns None if unavailable."""
    global _XRV_MODEL
    if not XRV_OK:
        return None
    if _XRV_MODEL is not None:
        return _XRV_MODEL
    try:
        # 'all' = trained on aggregate of NIH + CheXpert + MIMIC-CXR + PadChest + RSNA
        _XRV_MODEL = xrv.models.DenseNet(weights="densenet121-res224-all")
        _XRV_MODEL.eval()
        return _XRV_MODEL
    except Exception as e:
        print(f"TorchXRayVision model load failed: {e}")
        return None


def specialist_chest_xray_analysis(image_bytes: bytes) -> dict:
    """
    Run TorchXRayVision specialist model on a chest X-ray.

    Returns:
      {
        "ok": True/False,
        "available": True/False,    # whether xrv is installed at all
        "predictions": [             # sorted descending by probability
            {"pathology": "Pneumonia", "probability": 0.78},
            ...
        ],
        "model_name": "DenseNet121-NIH+CheXpert+MIMIC-CXR+PadChest",
        "error": "..."  # if ok==False
      }
    """
    if not XRV_OK:
        return {"ok": False, "available": False, "predictions": [],
                "model_name": "", "error": "torchxrayvision not installed"}

    model = _load_xrv_model()
    if model is None:
        return {"ok": False, "available": True, "predictions": [],
                "model_name": "", "error": "Could not load TorchXRayVision model"}

    try:
        # Load image to grayscale numpy array
        img = _PILImage.open(_io.BytesIO(image_bytes)).convert("L")
        arr = np.array(img).astype(np.float32)

        # Normalize to xrv's expected scale: [-1024, 1024]
        arr = xrv.datasets.normalize(arr, 255)

        # Add channel dim → (1, H, W)
        arr = arr[None, ...]

        # Resize/crop to 224x224 using xrv's transform
        transform = xrv.datasets.XRayResizer(224)
        arr = transform(arr)

        # Convert to tensor → (1, 1, 224, 224)
        tensor = torch.from_numpy(arr).unsqueeze(0)

        with torch.no_grad():
            preds = model(tensor)[0].cpu().numpy()

        # Pair pathology names with probabilities
        labels = model.pathologies
        pairs = [
            {"pathology": lbl, "probability": float(p)}
            for lbl, p in zip(labels, preds)
            if lbl and lbl.strip()  # filter blank labels
        ]
        pairs.sort(key=lambda x: x["probability"], reverse=True)

        return {
            "ok":         True,
            "available":  True,
            "predictions": pairs,
            "model_name": "DenseNet121 (NIH+CheXpert+MIMIC-CXR+PadChest+RSNA)",
            "error":      "",
        }
    except Exception as e:
        return {"ok": False, "available": True, "predictions": [],
                "model_name": "", "error": f"Inference failed: {e}"}


def render_specialist_panel(result: dict, gemini_findings: list = None) -> None:
    """Render the TorchXRayVision specialist results as a card with comparison."""
    if not result.get("available"):
        st.markdown(f"""
        <div class="alert-info" style="font-size:.82rem;">
          <b>📦 Specialist model not installed</b><br>
          Install with: <code>pip install torchxrayvision torch</code><br>
          This adds a second-opinion AI trained on 1M+ labelled chest X-rays
          (NIH, CheXpert, MIMIC-CXR) for verification of Gemini's findings.
        </div>
        """, unsafe_allow_html=True)
        return

    if not result.get("ok"):
        st.markdown(f"""
        <div class="alert-warn" style="font-size:.82rem;">
          ⚠️ Specialist model error: {result.get("error", "unknown")}
        </div>
        """, unsafe_allow_html=True)
        return

    preds = result.get("predictions", [])
    if not preds:
        return

    st.markdown("### 🔬 Specialist Second Opinion — TorchXRayVision")
    st.caption(f"Model: {result.get('model_name','')} · "
               f"Trained on >1M labelled chest X-rays from public medical datasets")

    # Top 5 most probable findings
    top5 = preds[:5]
    cols = st.columns(len(top5))
    for col, p in zip(cols, top5):
        prob_pct = int(p["probability"] * 100)
        # Color by probability: red >70%, orange >40%, gray below
        if prob_pct >= 70:
            color, bg = "#dc2626", "#fef2f2"
        elif prob_pct >= 40:
            color, bg = "#d97706", "#fffbeb"
        else:
            color, bg = "#6b7280", "#f8fafc"
        with col:
            st.markdown(f"""
            <div style="background:{bg};border:2px solid {color};border-radius:10px;
                        padding:.7rem .5rem;text-align:center;">
              <div style="font-size:.7rem;color:#374151;font-weight:600;
                          min-height:2.4rem;line-height:1.2;">
                {p["pathology"]}
              </div>
              <div style="font-size:1.4rem;font-weight:800;color:{color};
                          margin-top:.3rem;">{prob_pct}%</div>
            </div>
            """, unsafe_allow_html=True)

    # Agreement check with Gemini findings
    if gemini_findings:
        st.markdown("#### 🤝 Cross-Model Agreement")
        gemini_labels = " ".join(
            (f.get("label", "") + " " + f.get("description", "")).lower()
            for f in gemini_findings
        )
        agreements = []
        disagreements = []
        for p in preds[:8]:
            patho_lower = p["pathology"].lower().replace("_", " ")
            in_gemini = patho_lower in gemini_labels or any(
                w in gemini_labels for w in patho_lower.split() if len(w) > 4
            )
            high_prob = p["probability"] >= 0.5
            if in_gemini and high_prob:
                agreements.append(p["pathology"])
            elif not in_gemini and high_prob:
                disagreements.append(p["pathology"])

        if agreements:
            st.markdown(
                f'<div class="alert-good" style="font-size:.83rem;">'
                f'✅ <b>Both models agree on:</b> {", ".join(agreements)}'
                f'</div>', unsafe_allow_html=True)
        if disagreements:
            st.markdown(
                f'<div class="alert-warn" style="font-size:.83rem;">'
                f'⚠️ <b>Specialist model flags but Gemini did NOT:</b> '
                f'{", ".join(disagreements)} — worth a closer look.'
                f'</div>', unsafe_allow_html=True)
        if not agreements and not disagreements:
            st.markdown(
                f'<div class="alert-info" style="font-size:.83rem;">'
                f'ℹ️ Specialist model finds no high-probability pathologies '
                f'(>50%). Gemini\'s findings stand on their own.'
                f'</div>', unsafe_allow_html=True)

    # Full table in expander
    with st.expander("📊 Full pathology probability table (all 18 classes)"):
        import pandas as pd
        df = pd.DataFrame([{
            "Pathology": p["pathology"],
            "Probability": f"{int(p['probability']*100)}%",
            "Numeric": p["probability"],
        } for p in preds])
        st.dataframe(
            df[["Pathology", "Probability"]],
            use_container_width=True,
            hide_index=True,
        )


# ════════════════════════════════════════════════════════════════════════════
#  PART 3 — STUDENT FEEDBACK LOOP ON AI FINDINGS
# ════════════════════════════════════════════════════════════════════════════

def render_finding_feedback(finding_id: str, finding_label: str,
                             image_hash: str = "") -> None:
    """
    Render thumbs-up/down/uncertain widget for a single AI finding.
    Stores responses in session_state.imaging_feedback for later analysis/training.

    Args:
        finding_id:   unique key per finding within an image, e.g. "f0", "f1"
        finding_label: human label of the finding (for display)
        image_hash:   hash of the image (so feedback can be aggregated per-image)
    """
    feedback_store = st.session_state.setdefault("imaging_feedback", {})
    key_root = f"{image_hash}_{finding_id}"

    current = feedback_store.get(key_root, None)

    st.markdown(f"""
    <div style="margin:.4rem 0 .2rem;font-size:.78rem;color:#475569;">
      <b>Do you agree with this AI finding?</b>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])

    with c1:
        if st.button(
            "👍 Agree" + (" ✓" if current == "agree" else ""),
            key=f"fb_agree_{key_root}",
            use_container_width=True,
            type="primary" if current == "agree" else "secondary",
        ):
            feedback_store[key_root] = "agree"
            st.rerun()

    with c2:
        if st.button(
            "👎 Disagree" + (" ✓" if current == "disagree" else ""),
            key=f"fb_disagree_{key_root}",
            use_container_width=True,
            type="primary" if current == "disagree" else "secondary",
        ):
            feedback_store[key_root] = "disagree"
            st.rerun()

    with c3:
        if st.button(
            "🤔 Unsure" + (" ✓" if current == "unsure" else ""),
            key=f"fb_unsure_{key_root}",
            use_container_width=True,
            type="primary" if current == "unsure" else "secondary",
        ):
            feedback_store[key_root] = "unsure"
            st.rerun()

    with c4:
        if current == "disagree":
            note_key = f"fb_note_{key_root}"
            existing_note = feedback_store.get(f"{key_root}_note", "")
            note = st.text_input(
                "Why? (optional, helps improve AI)",
                value=existing_note,
                key=note_key,
                placeholder="e.g. wrong location, not a real finding...",
                label_visibility="collapsed",
            )
            if note != existing_note:
                feedback_store[f"{key_root}_note"] = note


def render_feedback_summary() -> None:
    """Render summary of student feedback collected this session."""
    feedback = st.session_state.get("imaging_feedback", {})
    if not feedback:
        return

    # Count by type (skip note entries)
    counts = {"agree": 0, "disagree": 0, "unsure": 0}
    for k, v in feedback.items():
        if k.endswith("_note"):
            continue
        if v in counts:
            counts[v] += 1

    total = sum(counts.values())
    if total == 0:
        return

    pct_agree = int(counts["agree"] / total * 100) if total else 0
    st.markdown("#### 📈 Your AI Verification Stats (this session)")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total reviewed", total)
    with col2:
        st.metric("Agreed", counts["agree"], f"{pct_agree}%")
    with col3:
        st.metric("Disagreed", counts["disagree"])
    with col4:
        st.metric("Unsure", counts["unsure"])


def export_feedback_for_training() -> str:
    """
    Export collected feedback as JSON string — useful for fine-tuning later.
    Each entry: {image_hash, finding_id, finding_label, verdict, note, timestamp}
    """
    import json
    feedback = st.session_state.get("imaging_feedback", {})
    if not feedback:
        return "[]"

    entries = []
    for key, verdict in feedback.items():
        if key.endswith("_note") or verdict not in ("agree", "disagree", "unsure"):
            continue
        # key format: {image_hash}_{finding_id}
        parts = key.rsplit("_", 1)
        img_hash = parts[0] if len(parts) > 1 else ""
        find_id  = parts[1] if len(parts) > 1 else key
        note     = feedback.get(f"{key}_note", "")

        entries.append({
            "image_hash":   img_hash,
            "finding_id":   find_id,
            "verdict":      verdict,
            "note":         note,
            "exported_at":  datetime.utcnow().isoformat(),
        })
    return json.dumps(entries, indent=2)
