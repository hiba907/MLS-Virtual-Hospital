# Phase 2: Image Practice Library — Deployment Guide

## What this delivers

A new student-facing module **"🩻 Image Practice"** where students browse curated medical images and practice interpretation. Plus a Faculty Portal admin panel to add/manage images with an approval workflow.

**Student experience:**
1. Sidebar → **🩻 Image Practice**
2. Filter by Modality / System / Difficulty
3. See image cards with clinical context visible
4. Click **"👁️ Reveal key findings"** → see what to notice
5. Click **"💡 Reveal diagnosis"** → see the answer + teaching points + earn 10 XP

**Admin experience:**
1. Faculty Portal → **🩻 Image Library Manager**
2. **➕ Add New Image** tab → paste URL + metadata → saves as draft
3. **⏳ Drafts** tab → preview, edit, then publish
4. **✓ Published** tab → manage live library
5. **📊 Stats** tab → drafts/published/view counts

---

## Files in this delivery

| File | Action |
|---|---|
| `app.py` | **Replace** existing on GitHub |
| `image_library.py` | **NEW** — upload to GitHub |

---

## STEP 1 — Run Supabase SQL

Open **Supabase → SQL Editor → New query**, paste this, click **Run**:

```sql
CREATE TABLE IF NOT EXISTS public.image_library (
    image_id          text PRIMARY KEY,
    title             text NOT NULL,
    image_url         text NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_img_status
    ON public.image_library(status, created_at);
CREATE INDEX IF NOT EXISTS idx_img_filters
    ON public.image_library(modality, system, difficulty);

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
```

Expected: "Success. No rows returned."

---

## STEP 2 — Upload files to GitHub

1. `app.py` (replaces existing)
2. `image_library.py` (NEW file)

Commit message: `Add Image Practice Library (Phase 2)`

Streamlit redeploys in ~60 seconds.

---

## STEP 3 — Where to find legal images to start

I need to be honest with you about a few things:

### ⚠️ Important honest reality about image URLs

I cannot give you 30 guaranteed-working direct image URLs from Radiopaedia. Here's why:

1. **Radiopaedia uses dynamic image hosting** with URLs that look like:
   ```
   https://prod-images-static.radiopaedia.org/images/1371230/186f8496f0dd2fdb0f98467d2b32dbce9c4abc6579dd5b8167c09a298c23ec91_thumb.jpeg
   ```
   These specific URLs may work today but could change.

2. **Many image hosts block hotlinking** for bandwidth/copyright reasons — even if the URL exists, embedding may fail.

3. **The safest path: download → host yourself** (like we did for audio).

### ✅ The reliable workflow for images

**Mirror what you did for audio:**

1. **Browse Radiopaedia** at https://radiopaedia.org/cases
2. Find a case you like (e.g., search for "pneumonia", "pneumothorax", "appendicitis")
3. Right-click the main image → **"Save image as..."** 
4. Save with a descriptive filename: `pneumonia-right-lower-lobe.jpg`
5. Upload to `static/images/` in your GitHub repo (just like `static/sounds/`)
6. Reference URL: `https://raw.githubusercontent.com/hiba907/MLS-Virtual-Hospital/main/static/images/pneumonia-right-lower-lobe.jpg`
7. In the Faculty Portal, paste this URL + write the clinical context, findings, diagnosis

### 📚 Recommended starting cases from Radiopaedia (verified topics)

I've verified these case topics exist on Radiopaedia. Browse each, pick the version that has CC license + best clarity:

**Chest X-Ray (start here — most common)**
1. **Lobar pneumonia** — https://radiopaedia.org/cases/lobar-pneumonia
2. **Pneumothorax** — search: `radiopaedia pneumothorax case`
3. **Tension pneumothorax** — search: `radiopaedia tension pneumothorax`
4. **Pleural effusion** — search: `radiopaedia pleural effusion`
5. **Pulmonary edema (CHF)** — search: `radiopaedia pulmonary edema`
6. **Lobar collapse** — search: `radiopaedia lobar collapse`
7. **Cardiomegaly** — search: `radiopaedia cardiomegaly`
8. **TB cavitary lesion** — search: `radiopaedia tuberculosis cavity`

**Abdominal X-Ray / CT**
9. **Bowel obstruction** — search: `radiopaedia small bowel obstruction`
10. **Pneumoperitoneum** — search: `radiopaedia pneumoperitoneum free air`
11. **Appendicitis CT** — search: `radiopaedia acute appendicitis CT`
12. **Sigmoid volvulus** — search: `radiopaedia sigmoid volvulus`

**Musculoskeletal**
13. **Colles fracture** — search: `radiopaedia colles fracture`
14. **Scaphoid fracture** — search: `radiopaedia scaphoid fracture`
15. **Hip fracture** — search: `radiopaedia femoral neck fracture`
16. **Boxer's fracture** — search: `radiopaedia boxer fracture`

**Neuro**
17. **Acute hemorrhagic stroke (CT)** — search: `radiopaedia acute intracerebral hemorrhage`
18. **Ischemic stroke (CT/MRI)** — search: `radiopaedia MCA stroke`
19. **Subdural hematoma** — search: `radiopaedia acute subdural hematoma`
20. **Epidural hematoma** — search: `radiopaedia epidural hematoma`

**ECG**
21. **STEMI inferior** — search: `radiopaedia inferior STEMI`
22. **Atrial fibrillation** — search: `radiopaedia atrial fibrillation ECG`
23. **Complete heart block** — search: `radiopaedia third degree heart block`

For ECG specifically, **LITFL ECG Library** is a goldmine: https://litfl.com/ecg-library/ — has CC-licensed ECGs for nearly every condition.

### 🎯 My honest recommendation: start with 10 images

Don't try to populate 100 images in a weekend. Start with **10 high-quality ones**:

- 3 chest X-rays (pneumonia, pneumothorax, pulmonary edema)
- 2 abdominal (bowel obstruction, appendicitis)  
- 2 MSK (Colles fracture, scaphoid)
- 2 neuro (ICH on CT, MCA stroke)
- 1 ECG (STEMI)

Spending 10-15 minutes per image = 2-3 hours to launch a working library. Then add more over time as you see student usage.

---

## STEP 4 — Test the workflow

### Test 1 — Add an image as admin

1. Log in as `hamdarhiba95@gmail.com`
2. Sidebar → Faculty Portal → **🩻 Image Library Manager**
3. Tab: **➕ Add New Image**
4. Fill in:
   - **Title:** `Right Lower Lobe Pneumonia`
   - **Image URL:** (paste a verified working URL from your GitHub or Radiopaedia)
   - **Modality:** X-ray (CXR)
   - **System:** respiratory
   - **Difficulty:** intermediate
   - **Clinical context:** *"45-year-old male with 3 days of fever, productive cough, and right-sided pleuritic chest pain."*
   - **Key findings:** *"Right lower lobe consolidation with air bronchograms. No pleural effusion. Cardiac silhouette normal."*
   - **Diagnosis:** *"Community-acquired pneumonia (right lower lobe)"*
   - **Teaching points:** *"Air bronchograms indicate air-filled airways in consolidated lung tissue. Lobar pneumonia respects anatomical boundaries."*
   - **Source:** `Radiopaedia case 12345 (CC BY-NC-SA)` *(or your own attribution)*
5. Click **💾 Save as draft**

### Test 2 — Publish it

1. Go to **⏳ Drafts** tab
2. Expand your draft → verify the image preview shows
3. Make any edits if needed
4. Click **✓ Publish**

### Test 3 — View as student

1. Log out, log in as a student (or incognito)
2. Sidebar → Tools → **🩻 Image Practice**
3. You should see the published image
4. Click **👁️ Reveal key findings** → see findings
5. Click **💡 Reveal diagnosis** → see answer + 10 XP awarded

---

## Honest caveats

### 1. Image URL stability

Just like with our audio files, external image URLs can break. The safest path:
- Download images to your local machine
- Rename them descriptively
- Upload to `static/images/` in your GitHub repo
- Reference the GitHub raw URL

This protects you from external sites changing their structure.

### 2. Copyright attribution is critical

Radiopaedia uses **CC BY-NC-SA 4.0** — non-commercial use OK if you attribute the original author.

**Always include source attribution** in the "Source" field. Example format:
```
"Case courtesy of Dr [Author Name], Radiopaedia.org, rID: 12345 (CC BY-NC-SA 4.0)"
```

For your PhD platform, **non-commercial use is generally fine** — but you need to attribute every image. The "Source" field exists for this reason.

### 3. Patient identification

⚠️ **Never use:**
- Real patient images from your hospital without consent + IRB approval
- Screenshots from textbooks (copyright)
- Random Google Images results (unknown license)

### 4. Image quality

Some Radiopaedia thumbnails are low-resolution. For teaching, students need to see findings clearly. When downloading:
- Use the highest-resolution version available
- Verify findings are visible in the image
- Re-encode if needed (the file should be <2MB for fast loading)

### 5. The reveal mechanism uses session state

If a student reveals findings, navigates away, and comes back — the reveals reset. This is intentional (so they can practice again) but worth knowing.

### 6. No AI vision yet

This is v1 — text-only descriptions. In Phase 2B (later), we can add AI vision analysis that automatically generates findings/diagnoses from the image. For now, you write the descriptions manually.

---

## Summary checklist

- [ ] Run the Supabase SQL block (creates `image_library` + `image_views` tables)
- [ ] Upload new `app.py` to GitHub
- [ ] Upload new `image_library.py` to GitHub (NEW file)
- [ ] Wait 60 seconds for Streamlit redeploy
- [ ] Verify sidebar: **🩻 Image Practice** appears in Tools (everyone) and **🩻 Image Library Manager** in Faculty Portal (admin)
- [ ] Add 1 test image → publish → verify students see it
- [ ] Plan 1-2 hour curation sessions to add 10-20 starter images

---

## What's next (Phase 3)

After this is stable and you have ~20 images in the library:

**Phase 3: RAG with Medical Guidelines** — Upload PDFs of CDC/WHO/NIH guidelines. AI tutor searches them and cites sources in answers.

**Optional Phase 2B (later):** Add AI vision analysis to auto-generate findings for each image.

Tell me when Phase 2 is deployed and you're ready for Phase 3. 👍
