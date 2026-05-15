"""
═══════════════════════════════════════════════════════════════════════════
  MLS Virtual Hospital — RAG System (Phase 3 of Knowledge Expansion)
  ─────────────────────────────────────────────────────────────────────────
  Retrieval-Augmented Generation: AI tutor searches your custom medical
  reference library (WHO guidelines, CDC documents, etc.) before answering
  student questions. Responses cite real sources.

  HOW IT WORKS:
  ─────────────
  Admin uploads a PDF / text → system extracts text → chunks into passages
   ↓
  Each chunk gets embedded (Gemini embedding API, free tier)
   ↓
  Stored in Supabase with embedding vector
   ↓
  Student asks question → embed question → similarity search → top 3-5 chunks
   ↓
  AI tutor reads relevant chunks + answers with citations

  LEGAL CONSTRAINTS:
  ──────────────────
  Only upload LEGALLY shareable documents:
   ✅ WHO publications (open access)
   ✅ CDC documents (US gov, public domain)
   ✅ NIH / NICE / Cochrane (mostly open)
   ✅ Your own teaching materials
   ❌ UpToDate, Harrison's, BMJ Best Practice (copyrighted)

  AUTHOR: Hiba Hamdar — Academy of Medical Learning Skills
  COPYRIGHT (c) 2026 — All Rights Reserved
═══════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import streamlit as st
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
import uuid
import re
import io
import math
import requests


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
CHUNK_SIZE_CHARS    = 1200   # chars per chunk (~300 tokens, good for embeddings)
CHUNK_OVERLAP_CHARS = 200    # overlap between chunks (preserves context)
TOP_K_RESULTS       = 4      # how many chunks to retrieve per query
MIN_SIMILARITY      = 0.55   # threshold for relevance

EMBEDDING_MODEL = "models/text-embedding-004"
EMBEDDING_DIM   = 768

DOCUMENT_CATEGORIES = [
    "WHO Guidelines",
    "CDC Documents",
    "NICE Guidelines",
    "Cochrane Reviews",
    "Open Access Journal",
    "Teaching Materials",
    "Other",
]


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


def _is_admin() -> bool:
    auth = st.session_state.get("auth_user", {}) or {}
    role = (auth.get("role") or "").lower()
    if role in ("admin", "faculty"):
        return True
    admin_email = _safe_secret("ADMIN_EMAIL", "hamdarhiba95@gmail.com").strip().lower()
    user_email = (auth.get("email") or "").strip().lower()
    return bool(user_email and admin_email and user_email == admin_email)


# ═══════════════════════════════════════════════════════════════════════════
# EMBEDDING — uses Gemini's free embedding API
# ═══════════════════════════════════════════════════════════════════════════
def _gemini_keys() -> List[str]:
    keys = []
    for i in range(1, 21):
        k = _safe_secret(f"GEMINI_API_KEY_{i}", "")
        if k:
            keys.append(k)
    primary = _safe_secret("GEMINI_API_KEY", "")
    if primary and primary not in keys:
        keys.append(primary)
    return keys


def get_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> Optional[List[float]]:
    """
    Get an embedding vector for text using Gemini's free embedding API.
    task_type: 'RETRIEVAL_DOCUMENT' for stored chunks, 'RETRIEVAL_QUERY' for searches.
    """
    if not text or not text.strip():
        return None
    text = text.strip()[:9000]  # API limit safety

    for key in _gemini_keys():
        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/"
                f"{EMBEDDING_MODEL}:embedContent?key={key}"
            )
            payload = {
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
            }
            r = requests.post(url, json=payload, timeout=20)
            if r.status_code == 200:
                data = r.json()
                emb = data.get("embedding", {}).get("values", [])
                if emb:
                    return emb
        except Exception as e:
            print(f"[rag] embedding error with key: {e}")
            continue
    return None


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ═══════════════════════════════════════════════════════════════════════════
# TEXT EXTRACTION & CHUNKING
# ═══════════════════════════════════════════════════════════════════════════
def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes. Returns plain text or '' on failure."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []
        for page in reader.pages:
            try:
                text_parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n\n".join(text_parts)
    except ImportError:
        # Try pdfplumber as fallback
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                return "\n\n".join((p.extract_text() or "") for p in pdf.pages)
        except Exception as e:
            print(f"[rag] PDF extraction error: {e}")
            return ""
    except Exception as e:
        print(f"[rag] PDF extraction error: {e}")
        return ""


def chunk_text(text: str,
                chunk_size: int = CHUNK_SIZE_CHARS,
                overlap: int = CHUNK_OVERLAP_CHARS) -> List[str]:
    """
    Split text into overlapping chunks. Tries to break at paragraph boundaries
    when possible to preserve semantic units.
    """
    if not text:
        return []
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence end within last 200 chars of chunk
            search_start = max(end - 200, start)
            best_break = text.rfind(". ", search_start, end)
            if best_break == -1:
                best_break = text.rfind("\n", search_start, end)
            if best_break != -1 and best_break > start + chunk_size // 2:
                end = best_break + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
        if start >= len(text):
            break
    return chunks


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════════
def list_documents() -> List[Dict[str, Any]]:
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/rag_documents"
    params = {"select": "*", "order": "created_at.desc"}
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return r.json() or []
    except Exception as e:
        print(f"[rag] list_documents error: {e}")
    return []


def insert_document(rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _sb_available():
        return None
    url = f"{_supabase_url()}/rest/v1/rag_documents"
    try:
        r = requests.post(url, headers=_sb_headers(), json=rec, timeout=10)
        if r.status_code in (200, 201):
            return rec
    except Exception as e:
        print(f"[rag] insert_document error: {e}")
    return None


def insert_chunks_batch(chunks_data: List[Dict[str, Any]]) -> int:
    """Insert chunks in a batch. Returns number successfully inserted."""
    if not _sb_available() or not chunks_data:
        return 0
    url = f"{_supabase_url()}/rest/v1/rag_chunks"
    succeeded = 0
    # Insert in batches of 50 to avoid payload size limits
    for i in range(0, len(chunks_data), 50):
        batch = chunks_data[i:i+50]
        try:
            r = requests.post(url, headers=_sb_headers(), json=batch, timeout=15)
            if r.status_code in (200, 201):
                succeeded += len(batch)
        except Exception as e:
            print(f"[rag] batch insert error: {e}")
            continue
    return succeeded


def list_chunks_for_document(doc_id: str) -> List[Dict[str, Any]]:
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/rag_chunks"
    params = {
        "doc_id": f"eq.{doc_id}",
        "select": "chunk_id,doc_id,chunk_index,chunk_text,embedding",
        "order":  "chunk_index.asc",
    }
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=10)
        if r.status_code == 200:
            return r.json() or []
    except Exception:
        pass
    return []


def list_all_chunks() -> List[Dict[str, Any]]:
    """Fetch all chunks for similarity search. Cached per session."""
    cache_key = "_rag_chunks_cache"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/rag_chunks"
    all_chunks = []
    offset = 0
    page_size = 500
    while True:
        params = {
            "select": "chunk_id,doc_id,doc_title,doc_category,chunk_index,chunk_text,embedding",
            "limit":  str(page_size),
            "offset": str(offset),
            "order":  "doc_id.asc",
        }
        try:
            r = requests.get(url, headers=_sb_headers(), params=params, timeout=15)
            if r.status_code != 200:
                break
            page = r.json() or []
            if not page:
                break
            all_chunks.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        except Exception:
            break
    st.session_state[cache_key] = all_chunks
    return all_chunks


def invalidate_chunks_cache() -> None:
    if "_rag_chunks_cache" in st.session_state:
        del st.session_state["_rag_chunks_cache"]


def delete_document(doc_id: str) -> bool:
    """Delete a document and all its chunks."""
    if not _sb_available():
        return False
    # Delete chunks first
    chunks_url = f"{_supabase_url()}/rest/v1/rag_chunks"
    try:
        requests.delete(chunks_url, headers=_sb_headers(),
                         params={"doc_id": f"eq.{doc_id}"}, timeout=15)
    except Exception:
        pass
    # Delete document
    doc_url = f"{_supabase_url()}/rest/v1/rag_documents"
    try:
        r = requests.delete(doc_url, headers=_sb_headers(),
                             params={"doc_id": f"eq.{doc_id}"}, timeout=10)
        invalidate_chunks_cache()
        return r.status_code in (200, 204)
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════
# CORE RETRIEVAL — used by the main app to find relevant content
# ═══════════════════════════════════════════════════════════════════════════
def search_relevant_chunks(query: str, top_k: int = TOP_K_RESULTS,
                            min_similarity: float = MIN_SIMILARITY
                            ) -> List[Dict[str, Any]]:
    """
    Search the document library for chunks relevant to the query.
    Returns up to top_k chunks ordered by similarity, each with a 'similarity' field.
    Returns [] if no chunks meet the threshold.
    """
    if not query or not query.strip():
        return []
    query_emb = get_embedding(query, task_type="RETRIEVAL_QUERY")
    if not query_emb:
        return []

    chunks = list_all_chunks()
    if not chunks:
        return []

    scored = []
    for chunk in chunks:
        chunk_emb = chunk.get("embedding")
        if not chunk_emb or not isinstance(chunk_emb, list):
            continue
        sim = cosine_similarity(query_emb, chunk_emb)
        if sim >= min_similarity:
            chunk["similarity"] = sim
            scored.append(chunk)

    scored.sort(key=lambda c: c.get("similarity", 0), reverse=True)
    return scored[:top_k]


def get_rag_context_for_query(query: str, top_k: int = TOP_K_RESULTS) -> str:
    """
    Get formatted context string ready to inject into an AI prompt.
    Returns empty string if no relevant content found.
    """
    relevant = search_relevant_chunks(query, top_k=top_k)
    if not relevant:
        return ""

    parts = ["─── RELEVANT MEDICAL REFERENCES ───"]
    for i, chunk in enumerate(relevant, 1):
        title = chunk.get("doc_title", "Unknown source")
        cat = chunk.get("doc_category", "")
        text = chunk.get("chunk_text", "")
        sim_pct = round(chunk.get("similarity", 0) * 100)
        parts.append(
            f"\n[Source {i}: {title} ({cat}) — relevance {sim_pct}%]\n{text}"
        )
    parts.append("\n─── END REFERENCES ───")
    parts.append(
        "\nWhen answering, cite sources by name (e.g., 'According to "
        "[Source Name]...'). If the references don't contain relevant info, "
        "say so and answer from general medical knowledge."
    )
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# UI: ADMIN PANEL
# ═══════════════════════════════════════════════════════════════════════════
def render_rag_admin_panel() -> None:
    if not _is_admin():
        st.error("This page is for admins only.")
        return

    st.markdown(
        '<div class="section-header">📖 Medical Reference Library (RAG)</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div style="background:linear-gradient(135deg,#0a2540,#0e7490);color:white;
                border-radius:14px;padding:1.4rem 1.6rem;margin-bottom:1rem;">
      <div style="font-size:1.3rem;font-weight:800;margin-bottom:.4rem;">
        Reference Library — Let AI Cite Real Sources
      </div>
      <div style="font-size:.92rem;opacity:.92;line-height:1.5;">
        Upload medical guidelines, protocols, and reference documents. The AI
        tutor will search them when answering student questions and cite real
        sources in its responses.
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.warning(
        "⚠️ **Copyright reminder:** Only upload documents you have the legal "
        "right to use. Safe sources: WHO publications, CDC documents, NIH/NICE/"
        "Cochrane open content, your own teaching materials. **Never upload "
        "UpToDate, Harrison's, BMJ Best Practice, or textbook PDFs.**"
    )

    documents = list_documents()

    tabs = st.tabs([
        "➕ Upload Document",
        f"📚 Library ({len(documents)})",
        "🔎 Test Search",
        "📊 Stats",
    ])

    with tabs[0]:
        _admin_upload_tab()
    with tabs[1]:
        _admin_library_tab(documents)
    with tabs[2]:
        _admin_test_search_tab()
    with tabs[3]:
        _admin_stats_tab(documents)


def _admin_upload_tab() -> None:
    st.markdown("**Upload a PDF or paste text directly. The system will chunk it and create searchable embeddings.**")

    method = st.radio(
        "Upload method:",
        ["📤 Upload PDF file", "📝 Paste text directly"],
        horizontal=True,
        key="rag_upload_method",
    )

    with st.form("upload_doc_form"):
        title = st.text_input(
            "Document title (descriptive):",
            placeholder="e.g., 'WHO Guidelines for the Treatment of TB (2024)'",
        )
        category = st.selectbox("Category:", DOCUMENT_CATEGORIES)
        source_url = st.text_input(
            "Source URL (where you got it):",
            placeholder="https://www.who.int/publications/...",
        )

        pdf_file = None
        pasted_text = ""

        if method == "📤 Upload PDF file":
            pdf_file = st.file_uploader(
                "Choose a PDF file:",
                type=["pdf"],
                key="rag_pdf_upload",
            )
        else:
            pasted_text = st.text_area(
                "Paste document text here:",
                height=300,
                placeholder="Paste the full text of the guideline or document...",
            )

        license_confirm = st.checkbox(
            "✓ I confirm this document is legally permitted for use "
            "(public domain, CC-licensed, or my own work).",
            value=False,
        )

        submitted = st.form_submit_button(
            "🚀 Process & index document",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if not title.strip():
                st.error("Please provide a document title.")
                return
            if not license_confirm:
                st.error(
                    "You must confirm the document is legally permitted for use."
                )
                return

            # Get the text
            text = ""
            if pdf_file:
                with st.spinner("Extracting text from PDF..."):
                    pdf_bytes = pdf_file.read()
                    text = extract_text_from_pdf(pdf_bytes)
                    if not text:
                        st.error(
                            "Could not extract text from PDF. The file may be "
                            "image-only (scanned). Try pasting text directly."
                        )
                        return
            elif pasted_text.strip():
                text = pasted_text.strip()
            else:
                st.error("Please upload a PDF or paste text.")
                return

            # Chunk it
            chunks = chunk_text(text)
            if not chunks:
                st.error("Document is empty after chunking.")
                return

            doc_id = "doc_" + uuid.uuid4().hex[:12]

            # Show progress
            st.info(
                f"📊 Document has {len(text):,} characters, will be split into "
                f"**{len(chunks)} chunks**. Generating embeddings now..."
            )
            progress_bar = st.progress(0.0)
            status_text = st.empty()

            # Insert document record first
            doc_record = {
                "doc_id":         doc_id,
                "title":          title.strip(),
                "category":       category,
                "source_url":     source_url.strip(),
                "n_chunks":       len(chunks),
                "n_chars":        len(text),
                "added_by":       (st.session_state.get("auth_user") or {}).get("name", "admin"),
                "created_at":     datetime.now(timezone.utc).isoformat(),
            }
            if not insert_document(doc_record):
                st.error("Could not save document record.")
                return

            # Embed each chunk and prepare for batch insert
            chunk_records = []
            failed_chunks = 0
            for i, chunk_text_val in enumerate(chunks):
                status_text.markdown(f"Embedding chunk **{i+1}/{len(chunks)}**...")
                emb = get_embedding(chunk_text_val, task_type="RETRIEVAL_DOCUMENT")
                if not emb:
                    failed_chunks += 1
                    continue
                chunk_records.append({
                    "chunk_id":     f"ch_{uuid.uuid4().hex[:14]}",
                    "doc_id":       doc_id,
                    "doc_title":    title.strip()[:200],
                    "doc_category": category,
                    "chunk_index":  i,
                    "chunk_text":   chunk_text_val,
                    "embedding":    emb,
                    "created_at":   datetime.now(timezone.utc).isoformat(),
                })
                progress_bar.progress((i + 1) / len(chunks))

            # Batch insert
            status_text.markdown("💾 Saving to database...")
            n_saved = insert_chunks_batch(chunk_records)

            status_text.empty()
            progress_bar.empty()
            invalidate_chunks_cache()

            if n_saved > 0:
                msg = f"✅ Indexed {n_saved}/{len(chunks)} chunks for **{title}**"
                if failed_chunks > 0:
                    msg += f" ({failed_chunks} chunks failed embedding — likely Gemini rate limit)"
                st.success(msg)
                st.info(
                    "Document is now searchable. The AI tutor will use it when "
                    "answering relevant student questions."
                )
            else:
                st.error("Could not save chunks to database.")


def _admin_library_tab(documents: List[Dict[str, Any]]) -> None:
    if not documents:
        st.info("📚 Library is empty. Upload your first document in the **➕ Upload Document** tab.")
        st.markdown("---")
        st.markdown("### 🎯 Suggested first documents (all free & legally shareable)")
        st.markdown("""
        - **WHO TB Treatment Guidelines** → https://www.who.int/publications/i/item/9789240063129
        - **WHO Antibiotic Stewardship Manual** → https://www.who.int/publications/i/item/9789240050912
        - **CDC Adult Immunization Schedule** → https://www.cdc.gov/vaccines/schedules/
        - **NICE Pneumonia Guidelines (CG191)** → https://www.nice.org.uk/guidance/cg191
        - **Your own teaching notes** → paste text directly
        """)
        return

    st.markdown(f"**{len(documents)} document{'s' if len(documents)!=1 else ''} in library**")
    for doc in documents:
        doc_id = doc.get("doc_id", "")
        title = doc.get("title", "(no title)")
        cat = doc.get("category", "")
        n_chunks = doc.get("n_chunks", 0)
        with st.expander(
            f"📘 {title} ({cat}) · {n_chunks} chunks",
            expanded=False
        ):
            st.markdown(f"**Category:** {cat}")
            st.markdown(f"**Source:** {doc.get('source_url', '—')}")
            st.markdown(f"**Total chunks:** {n_chunks}")
            st.markdown(f"**Total chars:** {doc.get('n_chars', 0):,}")
            st.caption(f"Added: {doc.get('created_at', '')[:10]}")

            if st.button(f"🗑️ Delete this document",
                          key=f"del_doc_{doc_id}",
                          use_container_width=True):
                if delete_document(doc_id):
                    st.warning(f"Deleted '{title}' and all its chunks.")
                    st.rerun()


def _admin_test_search_tab() -> None:
    st.markdown(
        "**Test the retrieval system.** Type a medical question and see what "
        "chunks the system finds. This is what gets injected into the AI tutor's prompt."
    )

    query = st.text_input(
        "Test query:",
        placeholder="e.g., 'What is the first-line treatment for community-acquired pneumonia?'",
        key="rag_test_query",
    )
    if st.button("🔎 Search", type="primary"):
        if not query.strip():
            st.warning("Enter a query first.")
            return
        with st.spinner("Searching..."):
            results = search_relevant_chunks(query.strip(), top_k=5)
        if not results:
            st.info(
                "No relevant content found. Either the library is empty, or no "
                "documents discuss this topic with high enough similarity."
            )
            return

        st.success(f"Found {len(results)} relevant chunks:")
        for i, chunk in enumerate(results, 1):
            sim = chunk.get("similarity", 0)
            st.markdown(f"""
            <div style="background:#f0f9ff;border-left:4px solid #0ea5e9;
                        border-radius:8px;padding:.9rem 1.1rem;margin:.6rem 0;">
              <div style="font-weight:700;color:#0369a1;font-size:.85rem;">
                #{i} · {chunk.get('doc_title', '?')} · {chunk.get('doc_category', '')}
              </div>
              <div style="font-size:.7rem;color:#64748b;margin-bottom:.4rem;">
                Relevance: {round(sim*100)}% · Chunk index: {chunk.get('chunk_index', '?')}
              </div>
              <div style="font-size:.82rem;color:#0f172a;line-height:1.5;
                          background:white;padding:.6rem .8rem;border-radius:6px;">
                {chunk.get('chunk_text', '')[:600]}{'...' if len(chunk.get('chunk_text', '')) > 600 else ''}
              </div>
            </div>
            """, unsafe_allow_html=True)


def _admin_stats_tab(documents: List[Dict[str, Any]]) -> None:
    n_docs = len(documents)
    n_chunks_total = sum(d.get("n_chunks", 0) for d in documents)
    n_chars_total = sum(d.get("n_chars", 0) for d in documents)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("📘 Documents", n_docs)
    with c2:
        st.metric("📄 Total chunks", n_chunks_total)
    with c3:
        st.metric("📝 Total chars", f"{n_chars_total:,}")

    # Breakdown by category
    by_cat = {}
    for d in documents:
        cat = d.get("category", "Other")
        by_cat[cat] = by_cat.get(cat, 0) + 1

    if by_cat:
        st.markdown("---")
        st.markdown("**By category:**")
        for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
            st.markdown(f"- {cat}: **{count}**")


# ═══════════════════════════════════════════════════════════════════════════
# SUPABASE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════
RAG_SCHEMA = """
-- ─────────────────────────────────────────────────────────────────────
-- RAG System — Medical Reference Library schema
-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.rag_documents (
    doc_id       text PRIMARY KEY,
    title        text NOT NULL,
    category     text DEFAULT '',
    source_url   text DEFAULT '',
    n_chunks     integer DEFAULT 0,
    n_chars      integer DEFAULT 0,
    added_by     text DEFAULT '',
    created_at   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rag_docs_cat ON public.rag_documents(category, created_at);

ALTER TABLE public.rag_documents ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow all rag_documents" ON public.rag_documents;
CREATE POLICY "Allow all rag_documents" ON public.rag_documents
    FOR ALL USING (true) WITH CHECK (true);

CREATE TABLE IF NOT EXISTS public.rag_chunks (
    chunk_id     text PRIMARY KEY,
    doc_id       text NOT NULL,
    doc_title    text DEFAULT '',
    doc_category text DEFAULT '',
    chunk_index  integer DEFAULT 0,
    chunk_text   text NOT NULL,
    embedding    jsonb,
    created_at   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc ON public.rag_chunks(doc_id, chunk_index);

ALTER TABLE public.rag_chunks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow all rag_chunks" ON public.rag_chunks;
CREATE POLICY "Allow all rag_chunks" ON public.rag_chunks
    FOR ALL USING (true) WITH CHECK (true);
"""


if __name__ == "__main__":
    print("MLS Virtual Hospital — RAG System (Phase 3)")
    print("=" * 60)
    print(RAG_SCHEMA)
