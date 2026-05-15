# Phase 3 — RAG System + Strategic Plan + Marketing

This document covers three topics:
1. **Phase 3 deployment** — the RAG system you just got
2. **Additional features** to strengthen the platform
3. **Marketing & promotion** — video scripts, ad copy, launch strategy

Each section has honest caveats about what's realistic.

---

# PART 1: PHASE 3 — RAG SYSTEM DEPLOYMENT

## What this delivers

When students ask the **AI Tutor** a question:
- System searches your custom medical reference library
- If relevant content is found, AI cites it in the answer
- Sources visible to students: *"According to the WHO TB Guidelines (2024)..."*

## Files in this delivery

| File | Action |
|---|---|
| `app.py` | **Replace** existing on GitHub |
| `rag_system.py` | **NEW** — upload to GitHub |

## STEP 1 — Required pip packages

The RAG system needs PDF text extraction. Add to your `requirements.txt`:

```
pypdf>=4.0.0
```

If you don't have a requirements.txt, create one at the repo root.

## STEP 2 — Run Supabase SQL

```sql
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
```

## STEP 3 — Deploy

1. Upload `app.py` + `rag_system.py` + `requirements.txt` to GitHub
2. Wait 60 sec for Streamlit redeploy
3. Sidebar → Faculty Portal → **📖 Reference Library (RAG)**

## STEP 4 — Add your first document

### Easiest: Test with pasted text first

1. Faculty Portal → 📖 Reference Library (RAG) → **➕ Upload Document** tab
2. Pick "📝 Paste text directly"
3. Title: *"Test — Sepsis Management"*
4. Paste any short paragraph about sepsis from a CC-licensed source
5. Click "🚀 Process & index document"

Watch the progress bar embed each chunk (this is the actual AI work).

### Then test the search

1. Tab: **🔎 Test Search**
2. Type: *"How do I treat sepsis?"*
3. Click Search → should find your document chunk

### Then test in the live tutor

1. Open a case → AI Tutor
2. Ask: *"What is the management approach for this patient?"*
3. AI should respond with content informed by your uploaded reference
4. Small caption appears: "📖 Last response referenced your custom medical library"

## Recommended starter documents (all legally shareable)

| Document | Source | Direct link |
|---|---|---|
| WHO TB Guidelines 2024 | WHO | https://www.who.int/publications/i/item/9789240063129 |
| WHO Antibiotic Stewardship | WHO | https://www.who.int/publications/i/item/9789240050912 |
| WHO Sepsis Recommendations | WHO | https://www.who.int/news-room/fact-sheets/detail/sepsis |
| CDC Infection Control | CDC | https://www.cdc.gov/infectioncontrol/ |
| CDC Adult Immunization | CDC | https://www.cdc.gov/vaccines/schedules/ |
| NICE Pneumonia (CG191) | NICE | https://www.nice.org.uk/guidance/cg191 |
| Your teaching notes | Yours | Paste directly |

**Don't try to upload 50 documents at once.** Start with 3-5. See how it works. Add more later.

## Honest caveats

### 1. Embedding API has rate limits

Gemini's free embedding API allows ~1500 requests/day. A 50-page document = ~100 chunks = 100 API calls. So you can index ~15 documents per day on free tier.

### 2. Search uses JSON storage, not pgvector

I'm using JSONB storage + in-Python cosine similarity, not Supabase's pgvector extension. Why? It works on free tier without setup. Tradeoff: slower for large libraries (>5,000 chunks). Fine for your use case.

### 3. Cited sources might be incomplete

The AI sometimes paraphrases without citing. Improving this requires prompt engineering. The system shows a "📖 Last response referenced your library" caption to indicate when RAG was used.

### 4. PDF extraction can fail on scanned PDFs

If a PDF is image-based (scanned), text extraction returns empty. You'd need OCR (Tesseract) for that — not built in. Use text-based PDFs or paste content directly.

### 5. Documents are not chunked semantically

Chunks are split by character count (~1200 chars) with overlap. A more sophisticated system would chunk by section/paragraph. The current approach works fine but is not optimal.

---

# PART 2: ADDITIONAL FEATURES TO STRENGTHEN THE PLATFORM

This is my honest strategic advice — what would actually move the needle vs. what would be busywork.

## High-impact additions (worth building)

### 🟢 1. Student feedback loop
After each AI interaction, ask: "Was this answer helpful?" 👍 👎
- Failed answers → faculty review queue
- Build a "common mistakes" dataset over time
- **Effort:** ~200 lines, half a day
- **Value:** Real data for paper, quality improvement

### 🟢 2. Spaced repetition for wrong MCQs
Wrong MCQ answers automatically get added to a daily review deck.
- You already have the Spaced Repetition module built (just not deployed)
- **Effort:** Deploy + test ~half a day
- **Value:** Huge — active recall is the most evidence-based learning method

### 🟢 3. Student progress dashboard
Show each student:
- Cases completed
- Average MCQ score
- Weak areas (lowest score categories)
- Recommended next cases
- **Effort:** ~400 lines, 1 day
- **Value:** Engagement + retention + paper data

### 🟢 4. Email digest / notifications
Weekly email: "You completed 5 cases. Your weakest area is cardiology. Recommended cases: ..."
- Use Resend free tier (3,000 emails/month free)
- **Effort:** ~300 lines, 1 day
- **Value:** Re-engagement, retention metrics

### 🟢 5. Mobile-friendly review
Streamlit is desktop-optimized. Add a mobile-friendly "review mode":
- Compact case display
- Swipe through MCQs
- **Effort:** ~500 lines, 1-2 days
- **Value:** Doubles potential user base

## Medium-impact additions (consider later)

### 🟡 6. Group/class cohorts
Faculty creates a "class," students join with a code, sees their cohort's leaderboard.
- **Effort:** ~600 lines
- **Value:** Useful when you have real classes using the platform

### 🟡 7. Specialty-specific OSCE stations
Currently OSCE simulator is generic. Add cardiology-specific, surgery-specific OSCEs.
- **Effort:** Content curation > coding
- **Value:** Higher exam relevance

### 🟡 8. Lebanese/Arabic localization
Translate UI + key content to Arabic.
- **Effort:** ~800 lines (UI strings) + significant translation work
- **Value:** Expands accessibility in MENA region

## Low-impact (be honest with yourself)

### 🔴 9. "Train your own AI model"
You asked about this earlier. **Don't do this.** Costs $1,000+, takes weeks, gives worse results than what you have. RAG (Phase 3) solves the same problem better.

### 🔴 10. More visual flash
3D anatomy, more animations, AR/VR.
- **Effort:** Massive
- **Value:** Looks impressive in demos, doesn't improve learning outcomes

### 🔴 11. Building everything yourself
You've already built A LOT. The next phase should be **content + users + data**, not more features.

## My honest recommendation for next 3 months

**Stop building. Start using.**

You have:
- ✅ Full multi-modal platform
- ✅ AI assistance, mentor system, real audio, real images, RAG
- ✅ MCQs, case creator, gamification

What you DON'T have:
- ❌ Real users at scale
- ❌ Performance data
- ❌ Published paper
- ❌ Iteration based on student feedback

**Spend the next 3 months on:**
1. **Recruit 20-50 real medical students** to use the platform
2. **Collect data on usage** — what features they use most, where they drop off
3. **Iterate based on feedback** — fix what's broken, not build new things
4. **Write the platform description paper** (JOSS or JMIR Med Ed)

Building more features without users is a trap many solo developers fall into.

---

# PART 3: MARKETING & PROMOTION

## ⚠️ First — important caveats

Before promoting, I need to be honest:

1. **Add visible disclaimers** before public launch (see Part 4)
2. **Don't promise clinical accuracy** — promise educational value
3. **Start small** — pilot with one class, not "everyone"
4. **Respect medical advertising laws** in Lebanon and your target regions
5. **Don't compete claims with established platforms** without evidence

## A. Video Promotion Script (90 seconds)

This is a script you (or someone) would record. I CAN'T make a video, but here's a tight 90-second script:

### Video Script: "Introducing MLS Virtual Hospital"

**[0:00–0:08] Hook (close-up of student looking stressed)**
> "Medical school case-based learning is broken. You read about pneumonia in a textbook. You memorize symptoms. But you've never actually managed a patient."

**[0:08–0:20] Problem (split screen: textbook vs. real patient encounter)**
> "When you finally see your first patient, you freeze. The gap between studying medicine and practicing medicine is huge — and it's costing students their confidence."

**[0:20–0:35] Solution intro (your platform screen recording)**
> "MLS Virtual Hospital is a free AI-powered teaching platform built by a researcher who lived this gap. Hundreds of real-style cases. Talk to AI patients. Order labs. Read X-rays. Submit your diagnosis and get instant expert feedback."

**[0:35–0:55] Feature montage (screen recordings, 2-3 sec each)**
> "Practice clinical reasoning with cases across every specialty. Listen to real heart and lung sounds. Interpret real X-rays. Test your knowledge with auto-generated MCQs. Connect with senior doctors for video mentorship — all inside the app, all free."

**[0:55–1:15] Differentiator (your face, talking to camera)**
> "Built by Hiba Hamdar, an independent researcher at the Academy of Medical Learning Skills. This isn't built by a company — it's built by a medic who knows what students actually need. And it's completely free for medical students worldwide."

**[1:15–1:30] Call to action**
> "Start practicing medicine the way you'll actually practice it. Visit MLS Virtual Hospital today. Link in description. No subscription. No credit card. Just real clinical training."

**[End screen]**
- Platform URL
- Free for medical students
- Visual disclaimer: "Educational use only. Not for clinical decision-making."

### Production notes (realistic & cheap)

- **Equipment:** Smartphone camera, free background (white wall)
- **Audio:** Phone mic is fine, but record in a quiet room
- **Screen recordings:** Free tools — OBS Studio or built-in macOS/Windows
- **Editing:** CapCut (free), iMovie, or DaVinci Resolve (free)
- **Music:** YouTube Audio Library (free, license-cleared)
- **Total time:** 4-8 hours including filming + editing
- **Cost:** $0

### Alternative — animated explainer (if you don't want to be on camera)

Use **Canva's video templates** (free tier) + your voice-over. Animate platform features as screen recordings overlaid on text. Same script, no face needed.

## B. Ad Copy Templates

### Short ad (Twitter/X / LinkedIn)
> 🏥 Medical students — I built a free AI-powered virtual hospital for clinical training.
>
> Practice with hundreds of cases. Talk to AI patients. Listen to real heart sounds. Get auto-generated MCQs.
>
> Built by a researcher for medical students. No subscription. No credit card.
>
> [Link]
>
> #MedEd #MedicalStudents #MedicalEducation #AI

### Long ad (LinkedIn / blog post intro)
> **I built a free virtual hospital for medical students — here's why**
>
> Two years ago I watched medical students struggle with the same thing I struggled with: the chasm between memorizing textbook cases and managing real patients.
>
> So I built MLS Virtual Hospital. Free. AI-powered. Hundreds of cases. Real clinical sounds. Auto-generated MCQs. Image practice. Mentor video calls. All in one platform, all free for students worldwide.
>
> It works in the browser. No installation. Sign up takes 30 seconds.
>
> If you're a medical student, try it: [link]
>
> If you're a medical educator, I'd love your feedback.
>
> Built solo by Hiba Hamdar at the Academy of Medical Learning Skills.

### Instagram caption (with video/carousel)
> Free AI clinical training for medical students 🏥
>
> Swipe to see what's inside →
>
> ✅ Hundreds of patient cases
> ✅ AI tutor with real sources
> ✅ Real auscultation sounds
> ✅ Image practice library
> ✅ Mentor video calls
> ✅ MCQs after every case
>
> All free. Link in bio.
>
> #medicaleducation #medicalstudent #medstudent #usmle #mededchat

## C. Launch Strategy (Honest)

### Phase 1 (Week 1-2): Soft launch
- Show to **5-10 students you personally know**
- Watch them use it
- Fix obvious bugs
- Collect testimonials

### Phase 2 (Week 3-4): Community launch
- Post on **r/medicalschool** (Reddit) — be transparent it's your project, follow community rules
- Post on **r/medstudents**, **r/medicine**
- Share in Lebanese medical student WhatsApp/Telegram groups (if you have access)
- LinkedIn post (English + Arabic if possible)

### Phase 3 (Month 2-3): Expansion
- Reach out to **medical school student associations** in MENA region
- Email medical educators offering free institutional access
- Submit to medical education conferences (poster or short talk)
- Start writing the platform description paper (JOSS or JMIR Med Ed)

### Phase 4 (Month 4-6): Validation
- Run a small pilot study with one class (after getting ethics approval somehow)
- Collect pre/post outcome data
- Write the outcomes paper

### Don't do these things (honest warning)
- ❌ Don't pay for ads in month 1 — get organic feedback first
- ❌ Don't promise things the platform doesn't do
- ❌ Don't compete head-on with UpToDate / Osmosis — they have $$$
- ❌ Don't market to non-medical-students yet
- ❌ Don't market in places that violate medical advertising laws

## D. Landing page content

Your Streamlit app IS the landing page in a way, but you might want a simple separate one. Free options:

### Quick landing page (Carrd.co or similar — free)

**Headline:** "MLS Virtual Hospital — Free AI clinical training for medical students"

**Sub-headline:** "Hundreds of cases. Real sounds. Real images. AI tutor. All free."

**3-section layout:**
1. **What it does** — bullet list of features
2. **Who it's for** — medical students, residents, educators
3. **How to start** — button → your Streamlit app URL

**Footer:**
- Built by Hiba Hamdar
- Educational use only — see disclaimers
- Contact email

---

# PART 4: CRITICAL DISCLAIMERS TO ADD

Before promoting widely, add these to your platform. I genuinely recommend this for your protection.

### Add to your Streamlit app footer / About page:

```
⚠️ EDUCATIONAL USE DISCLAIMER

This platform is provided for medical education purposes only.

• All cases, AI responses, and content are for learning, not clinical decision-making
• Never use this platform's output to make decisions about real patients
• AI may produce inaccurate or outdated information
• Always verify clinical content against current authoritative sources
• Real patients require real clinical evaluation by licensed physicians

By using this platform, you acknowledge:
- You are using it for educational purposes
- You will not rely on AI output for patient care
- The creators bear no responsibility for clinical outcomes related to platform use

Built by Hiba Hamdar at the Academy of Medical Learning Skills.
This platform is not affiliated with any medical board, university, or
clinical service. Not reviewed by any regulatory body.

Copyright © 2026 Hiba Hamdar. All rights reserved.
Software made available for educational use.
```

### Add to your registration page (must-accept checkbox):

```
☐ I understand that MLS Virtual Hospital is for educational use only.
   I will not use its content for real clinical decisions.
   I understand AI-generated content may be inaccurate.
```

### Add to AI tutor responses (automatic footer):

When the AI tutor answers, append:
> *"⚠️ This response is for educational purposes only. Verify against authoritative clinical sources before applying to real patients."*

---

# SUMMARY: WHAT TO DO NEXT

Here's my honest recommendation, in priority order:

### This week:
1. ⭐ **Deploy Phase 1, 2, 2.5, 3** (if not already done)
2. ⭐ **Add disclaimers** (Part 4 above) — protect yourself before promoting
3. ⭐ **Upload 3-5 RAG documents** (WHO, CDC) — test the system

### This month:
4. ✋ **STOP building new features**
5. ⭐ **Add 20-30 cases via AI Case Creator** — grow content
6. ⭐ **Add 10-20 images** to image library
7. ⭐ **Show platform to 5-10 students** for feedback
8. ⭐ **Fix what they say is broken**

### Months 2-3:
9. ⭐ **Record promotional video** using script in Part 3
10. ⭐ **Soft launch** on social media
11. ⭐ **Submit conference abstract** (AMEE 2026 or similar)
12. ⭐ **Start drafting platform description paper**

### Months 4-6:
13. ⭐ **Try to find one academic collaborator** (huge unlock)
14. ⭐ **Submit paper to JOSS or JMIR Medical Education**
15. ⭐ **Pilot study with one class** (if ethics access obtained)

---

**Honest closing thought:**

You've built something genuinely impressive. The biggest risk now isn't that you lack features — it's that you spend so much time building that you never publish, never get real users, never validate the work academically.

The platform is ready. **The next move is users, not code.**

I'm here when you need help with any of the above. 👍
