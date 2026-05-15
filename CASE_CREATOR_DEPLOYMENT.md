# AI Case Creator — Deployment Guide

## What this delivers

A Faculty Portal tool to grow your case library 10x faster, using AI assistance with admin curation.

**Three modes:**
1. **✨ Create from Scratch** — Type 1-2 sentences → AI generates a complete teaching case
2. **🔧 Expand Existing** — Pick from your 319 xlsx cases → AI fills in missing teaching fields (learning objectives, differential, reasoning, etc.) WITHOUT changing your clinical data
3. **📦 Bulk Enrichment** — Process up to 20 cases at once, each becomes a draft for your review

**Workflow:** AI generates → saves as DRAFT → you review/edit in Faculty Portal → approve → goes live for students.

**Key feature:** Approved AI cases appear in the student Case Library alongside your original 319 xlsx cases — students don't see any separation.

---

## Files in this delivery

| File | Action |
|---|---|
| `app.py` | **Replace** existing on GitHub |
| `case_creator.py` | **NEW** — upload to GitHub |

---

## STEP 1 — Run Supabase SQL (REQUIRED)

Open **Supabase Dashboard → SQL Editor → New query** and paste this:

```sql
CREATE TABLE IF NOT EXISTS public.cases_extended (
    case_id              text PRIMARY KEY,
    title                text DEFAULT '',
    system               text DEFAULT 'general',
    difficulty           text DEFAULT 'basic',
    age_sex              text DEFAULT '',
    occupation           text DEFAULT '',
    chief_complaint      text DEFAULT '',
    duration             text DEFAULT '',
    context              text DEFAULT '',
    hpi                  text DEFAULT '',
    pmh                  text DEFAULT '',
    family_hx            text DEFAULT '',
    social_hx            text DEFAULT '',
    medications          text DEFAULT '',
    vitals               text DEFAULT '',
    appearance           text DEFAULT '',
    physical_findings    text DEFAULT '',
    labs                 text DEFAULT '',
    urine                text DEFAULT '',
    imaging_tests        text DEFAULT '',
    xray_report          text DEFAULT '',
    ct_report            text DEFAULT '',
    final_diagnosis      text DEFAULT '',
    learning_objectives  text DEFAULT '',
    differential         text DEFAULT '',
    diagnostic_reasoning text DEFAULT '',
    teaching_points      text DEFAULT '',
    treatment            text DEFAULT '',
    tags                 text DEFAULT '',
    status               text DEFAULT 'draft',
    source_brief         text DEFAULT '',
    source_mode          text DEFAULT '',
    source_case_ref      text DEFAULT '',
    created_by           text DEFAULT '',
    approved_by          text DEFAULT '',
    approved_at          timestamptz,
    created_at           timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cases_ext_status
    ON public.cases_extended(status, created_at);
CREATE INDEX IF NOT EXISTS idx_cases_ext_system
    ON public.cases_extended(system, difficulty);

ALTER TABLE public.cases_extended ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all cases_extended" ON public.cases_extended;
CREATE POLICY "Allow all cases_extended" ON public.cases_extended
    FOR ALL USING (true) WITH CHECK (true);
```

Click **Run**. Expected: "Success. No rows returned."

---

## STEP 2 — Upload 2 Python files to GitHub

1. `app.py` (replaces existing)
2. `case_creator.py` (NEW file)

Commit message: `Add AI Case Creator with approval workflow`

Streamlit auto-redeploys in ~60 seconds.

---

## STEP 3 — Test the full flow

### Test 1 — Sidebar visibility

1. Log in as admin (`hamdarhiba95@gmail.com`)
2. Look at sidebar → **👨‍🏫 FACULTY PORTAL** section
3. You should now see:
   - 📊 Analytics Dashboard
   - 🏥 Case Creator (existing — manual + MIMIC)
   - **✨ AI Case Creator** (NEW)
   - 🛠️ Mentor Admin Panel
   - 📝 MCQ Bank Manager

### Test 2 — Create from scratch

1. Click **✨ AI Case Creator**
2. Tab: **✨ Create from Scratch**
3. Type a brief: `"55yo male with 2 weeks of progressive shortness of breath, leg swelling, and orthopnea. Hypertensive, ex-smoker."`
4. System: respiratory or cardio
5. Difficulty: intermediate
6. Click **🤖 Generate full case with AI**
7. Wait ~20 seconds
8. Should see green ✅ message: *"Case generated and saved as draft! Case ID: AICASE-XXXX"*
9. Expand the preview — you'll see the complete case

### Test 3 — Approve the draft

1. Go to **⏳ Pending Drafts** tab
2. You should see the case you just generated
3. Expand it → all 27 fields are visible and editable
4. Make any edits you want
5. Click **✓ Approve & publish**
6. Green message: *"Case approved — now live for students"*
7. Move to **✓ Approved Bank** tab → see it listed

### Test 4 — Verify students see it

1. Log out, log in as a student account (or open incognito)
2. Go to **Case Library**
3. The new AI case should appear alongside your 319 xlsx cases
4. Click into it → all fields populated correctly

### Test 5 — Expand existing case

1. Back as admin, click **✨ AI Case Creator**
2. Tab: **🔧 Expand Existing**
3. Search box: type "pneumonia" or any condition you have
4. Pick a case from dropdown
5. Click **🤖 Expand this case with AI**
6. AI keeps your clinical data, adds teaching fields
7. Saved as draft for review

### Test 6 — Bulk enrichment (start small)

1. Tab: **📦 Bulk Enrichment**
2. How many cases: 2 or 3 (start small for first test)
3. Click **🤖 Bulk-enrich N cases**
4. Watch progress bar
5. Check Pending Drafts — should see new drafts

---

## How the case creator handles your existing xlsx

Important detail: **the AI Case Creator never touches `case_studies.xlsx`.**

- Your 319 original cases stay in xlsx, unchanged
- New AI cases live in Supabase `cases_extended` table
- The student Case Library reads from BOTH and combines them
- This protects your original data from accidental corruption

When you "expand existing", the AI READS your xlsx case, but stores the expanded version as a NEW entry in Supabase. Your xlsx is read-only from the AI's perspective.

---

## Cost & rate-limit reality check

Each AI call costs ~$0.005 to $0.02 on Gemini Flash (depending on case complexity).

**For your free Gemini tier:**
- Per-minute: 15 requests max
- Per-day: 1,500 requests max
- For bulk enrichment of 319 cases, plan 30+ batches over a few days

**To enrich all 319 cases:**
- 5 cases × ~$0.01 = $0.05 per batch
- 64 batches total = ~$3.20 total if paid
- Or spread across many days with free tier

**Honest recommendation:** Do 5 cases per day for a few weeks. That gives you time to actually review each draft properly instead of batch-approving without checking.

---

## Honest caveats

### 1. AI-generated cases will sometimes have errors

AI is good at generating plausible-sounding clinical content, but it can:
- Use slightly wrong reference ranges
- Suggest off-label treatments
- Mix up region-specific guidelines
- Generate inconsistent vitals/labs vs. the diagnosis

**That's why the approval workflow exists.** Always read drafts critically before approving.

### 2. The first case in a system will be the trickiest

AI is much better at common conditions (pneumonia, MI, appendicitis) than rare ones (specific genetic disorders, unusual presentations). For rare cases, the "Expand Existing" mode is safer because your clinical data anchors it.

### 3. Expanded cases preserve YOUR clinical data exactly

If your existing case has typos or shorthand ("ptp", "neg.") — those stay as-is. AI only adds new teaching fields. If you want to clean up the clinical data, do that manually in the edit form.

### 4. Bulk enrichment skips already-processed cases

The system uses `source_case_ref` to track which xlsx cases have already been processed. So if you run bulk enrichment twice with no other changes, the second run will find fewer cases (because the first batch's are skipped).

### 5. Approved cases appear immediately for students

There's no "publish later" feature. Once you click Approve, students can see it. Reject first if you're unsure.

### 6. Cache may delay visibility

Streamlit caches the case library. After approving a new case, students may not see it for up to a few minutes until the cache expires. To force immediate visibility, you can ask students to refresh the page.

---

## What this enables for your PhD

This feature gives you a publishable methodology:

> **"AI-Assisted Curation of Clinical Teaching Cases: A Hybrid Approach"**
>
> *We deployed an AI-assisted case generation tool integrated into our virtual hospital platform. Faculty provided brief case descriptions or existing case fragments; an AI model (Gemini Flash) generated complete teaching cases with learning objectives, differential diagnoses, diagnostic reasoning, and teaching points. Faculty reviewed and approved drafts before publication. Over X months, Y AI-generated cases were curated across Z specialties.*

You can also collect data on:
- Approval rates (% of drafts approved without major edits)
- Time-to-curate (vs. fully manual case writing)
- Student engagement with AI vs. manual cases

That's strong PhD methodology.

---

## What I did NOT change

- ❌ Existing manual Case Creator page (still works)
- ❌ MIMIC-IV integration (still works)
- ❌ Original 319 xlsx cases (never touched)
- ❌ MCQ system, Mentor Directory, Tier 1 features (untouched)
- ❌ Audio sounds, Option A modality-honesty (untouched)

---

## Deployment checklist

- [ ] Run the Supabase SQL block (creates `cases_extended` table)
- [ ] Upload new `app.py` to GitHub
- [ ] Upload new `case_creator.py` to GitHub (NEW file)
- [ ] Wait 60 seconds for Streamlit redeploy
- [ ] Log in as admin → see "✨ AI Case Creator" in sidebar
- [ ] Create one test case from scratch → approve → verify it appears in student Case Library

---

## What's next after this works

Once you've used the Case Creator for a week or two and have your bank growing, the next two priorities from your earlier plan are:

1. **Image library expansion** — link CC-licensed images from Radiopaedia to specific cases
2. **RAG with medical references** — let AI tutor cite real guidelines

Reply when you're ready to build either of those.

---

Hiba — test thoroughly. Start with **Create from Scratch** on a topic you know well, so you can validate the AI output quality before trusting it for less familiar cases.

Tell me how it goes. 👍
