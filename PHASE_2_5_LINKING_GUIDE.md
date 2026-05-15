# Phase 2.5 — Image-to-Case Linking

## What this adds on top of Phase 2

You can now **optionally link any image to a specific case**. Linked images:
- ✅ Still appear in the standalone **🩻 Image Practice** library (everyone sees them)
- ✅ **PLUS** appear inline when students view that specific case's imaging report
- ✅ Have a "Reveal findings" mechanism so students can interpret before seeing the answer

Unlinked images just appear in the standalone library as before. **Linking is optional.**

---

## Files in this delivery

| File | Action |
|---|---|
| `app.py` | **Replace** existing on GitHub (adds 1 import + 1 hook in case viewer) |
| `image_library.py` | **Replace** existing on GitHub (adds linking field, helpers, render fn) |

---

## STEP 1 — Run Supabase SQL (REQUIRED migration)

This adds the new `case_id` column to your existing `image_library` table. Safe to run even if you already have the Phase 2 table.

Open **Supabase → SQL Editor → New query** and paste this:

```sql
-- Phase 2.5 migration — adds case_id column to image_library
ALTER TABLE public.image_library ADD COLUMN IF NOT EXISTS case_id text DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_img_case_link
    ON public.image_library(case_id, status) WHERE case_id != '';
```

Click **Run**. Expected: "Success. No rows returned."

---

## STEP 2 — Upload files to GitHub

1. `app.py` (replaces existing)
2. `image_library.py` (replaces existing)

Commit message: `Add Phase 2.5 image-to-case linking`

Streamlit redeploys in ~60 seconds.

---

## STEP 3 — How to use it

### When adding a new image (admin):

1. Sidebar → Faculty Portal → **🩻 Image Library Manager**
2. Tab: **➕ Add New Image**
3. You'll see a new dropdown: **🔗 Link to case (optional)**
4. Either:
   - Leave as **"— No case (standalone image) —"** → image only appears in Image Practice library
   - Pick a specific case → image appears in Image Practice library AND inline when students view that case

### When student views a case:

1. Student opens a case → goes through history, exam, labs
2. Reaches **Imaging** room
3. Clicks "Request Imaging"
4. They see:
   - The original text-based "Reported Findings" (from your xlsx)
   - **PLUS** a new "🩻 Imaging Studies" section below showing all linked real images
   - Each image has its own "👁️ Reveal findings" button so they can interpret first

### When student browses Image Practice library:

1. Sidebar → Tools → **🩻 Image Practice**
2. They see ALL published images (linked + unlinked)
3. Works exactly as before — filtering, reveal mechanism, XP

---

## Testing the workflow

### Test 1 — Link an image to a case

1. Go to **🩻 Image Library Manager → ➕ Add New Image**
2. Pick a case from the new "Link to case" dropdown (e.g., the first case in your library)
3. Fill in image URL + metadata
4. Save as draft → go to Drafts tab → Publish

### Test 2 — Verify it appears in the case

1. Log in as a student (or use incognito)
2. Go to **Case Library** → open the case you linked the image to
3. Go through the flow → reach **Imaging**
4. Click "Request Imaging"
5. You should see:
   - Text findings (from xlsx)
   - Below it: **🩻 Imaging Studies (1)** header with your linked image
   - "👁️ Reveal findings" button

### Test 3 — Verify it still appears standalone

1. Sidebar → Tools → **🩻 Image Practice**
2. The image should also appear here in the gallery
3. Linked and unlinked images coexist

---

## Strategic suggestion for using this

**Don't try to link images to all 319 cases.** Instead:

1. **Phase 2.5a — Top 10 most-used cases:** Link images to the 10 cases students access most. Maximum impact for minimum effort.

2. **Phase 2.5b — High-yield imaging cases:** Link to cases where imaging is THE main learning point (e.g., pneumonia, pneumothorax, fractures, stroke).

3. **Phase 2.5c — Build over time:** Add 1-2 linked images per week as you build the case library.

Realistic plan: **20-30 linked images covers the highest-impact cases.** That's a weekend of careful work, not weeks of grinding.

---

## Honest caveats

### 1. Case ID matching is exact

The `case_id` in the image must EXACTLY match the `Case_ID` in your xlsx (or AI-generated case). If your xlsx has `Case_ID = 5`, the image's `case_id` must be `"5"` (string).

The dropdown handles this for you, so you don't have to type case IDs manually.

### 2. Multiple images per case work fine

You can link 2, 3, or 10 images to the same case. They all display in order.

### 3. Drafts don't show until published

Linked images only appear in the case viewer once they're **published**. Drafts only show in the admin panel.

### 4. Existing images aren't auto-linked

This feature only applies to images you link going forward. If you have unlinked images from Phase 2 and want to link them now:
- Go to Drafts tab (or move from Published back to Draft)
- Edit each one → set the link → republish

### 5. Page caching may delay updates

Streamlit caches the case library. After publishing a newly-linked image, the case may need a hard refresh (Ctrl+Shift+R) to show the new image.

---

## What I did NOT change

- ❌ Existing case viewer flow (still works exactly as before)
- ❌ Image Practice page (still works, shows all images)
- ❌ Faculty Portal layout
- ❌ Any other modules (MCQ, Mentor Directory, Case Creator, etc.)

The case-linking is **additive** — nothing breaks, everything just gets the option to be linked.

---

## Deployment checklist

- [ ] Run the migration SQL (adds `case_id` column)
- [ ] Upload new `app.py` to GitHub
- [ ] Upload new `image_library.py` to GitHub
- [ ] Wait 60 seconds for Streamlit redeploy
- [ ] Test: add 1 image linked to a specific case → verify it appears in that case's imaging tab
- [ ] Verify the standalone Image Practice library still works

---

## Summary

Phase 2.5 makes images **smart**: they can be standalone (appear in library) or linked (also appear inline with their case). All optional, all opt-in.

After deployment, you have everything you need to build a polished, integrated, multi-modal teaching platform. 👍

---

**Tell me when it's deployed and what you see.**
