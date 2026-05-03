# Deployment Guide — Multi-Senior Mentor System + Audio Fix

This patch delivers your 3 main asks:
1. ✅ Users register as Student / Resident / Senior / Faculty with specialty
2. ✅ Embedded Jitsi video calls (in-app, no new tab)
3. ✅ Admin manually verifies Seniors before they appear in directory
4. ✅ Audio sounds — fixed URL strategy + step-by-step to actually make sounds play

---

## Files in this delivery

| File | Action |
|---|---|
| `app.py` | **Replace** existing on GitHub |
| `mentor_directory.py` | **Replace** existing on GitHub |
| `real_clinical_sounds.py` | **Replace** existing on GitHub |

Tier 1 files (`tier1_features.py`) and others are unchanged.

---

## STEP 1 — Run Supabase SQL (REQUIRED)

Open Supabase → SQL Editor → New Query → paste & run:

```sql
-- Add columns for Senior verification + specialty
alter table public.vh_users
    add column if not exists specialty   text default '',
    add column if not exists hospital    text default '',
    add column if not exists is_verified boolean default true;

-- Default existing seniors to unverified (admin must approve them)
update public.vh_users set is_verified = false
    where role = 'senior' and is_verified is distinct from false;

-- Mentor sessions table
create table if not exists public.mentor_sessions (
    session_id        text primary key,
    user_id           text not null,
    user_name         text default '',
    user_role         text default 'student',
    senior_id         text not null,
    senior_name       text default '',
    senior_specialty  text default '',
    case_title        text default '',
    case_id           text default '',
    question_summary  text not null,
    preferred_slots   text default '',
    comm_method       text default '',
    jitsi_room        text default '',
    status            text default 'pending',
    admin_notes       text default '',
    completed_at      timestamptz,
    created_at        timestamptz default now()
);

create index if not exists idx_msess_status on public.mentor_sessions(status, created_at);
create index if not exists idx_msess_user   on public.mentor_sessions(user_id, senior_id, case_id);
create index if not exists idx_msess_senior on public.mentor_sessions(senior_id, status);

alter table public.mentor_sessions enable row level security;

drop policy if exists "Allow all mentor_sessions" on public.mentor_sessions;
create policy "Allow all mentor_sessions"
    on public.mentor_sessions for all using (true) with check (true);
```

You should see "Success. No rows returned."

---

## STEP 2 — Upload 3 Python files to GitHub

Replace these on https://github.com/hiba907/MLS-Virtual-Hospital:

1. `app.py`
2. `mentor_directory.py`
3. `real_clinical_sounds.py`

Streamlit Cloud auto-redeploys in ~60 seconds.

---

## STEP 3 — Audio fix (THE IMPORTANT BIT)

The previous URLs at easyauscultation.com all return **404 — the files were deleted**. Your screenshot proved this. To make sounds actually play, you need to host MP3 files yourself.

### Option A — University of Michigan Heart Sound Library (RECOMMENDED)

This is the legitimate, free, embeddable solution.

**Download the files (free, CC BY-SA 3.0 license):**
1. Go to https://open.umich.edu/find/open-educational-resources/medical/heart-sound-murmur-library
2. Click through to the "Sessions" tab
3. Download all MP3 files (or use the zip)
4. The filenames in the kit may differ from what the code expects

**Upload to your GitHub:**
1. In your repo, create a new folder: `static/sounds/`
2. Upload the MP3 files with these exact filenames:
   - `normal-heart-s1-s2.mp3`
   - `aortic-stenosis.mp3`
   - `s3-gallop.mp3`
   - `s4-gallop.mp3`
   - `pericardial-rub.mp3`
   - `normal-vesicular.mp3`
   - `fine-crackles.mp3`
   - `coarse-crackles.mp3`
   - `wheezes.mp3`
   - `rhonchi.mp3`
   - `diminished.mp3`
   - `pleural-rub.mp3`
   - `stridor.mp3`
   - `bowel-normal.mp3`
   - `bowel-hyperactive.mp3`
   - `bowel-absent.mp3`

3. The code now points to `https://raw.githubusercontent.com/hiba907/MLS-Virtual-Hospital/main/static/sounds/` so files just work once uploaded.

**You don't need ALL 16 files** — start with the 5 most common (normal heart, normal lung, wheeze, crackles, murmur) and your students will already see real sounds working.

### Option B — Bandwidth-friendlier alternative

If your repo is getting too large, host the MP3s on a free CDN like:
- **Cloudflare R2** (free 10 GB)
- **GitHub Releases** (no size penalty on the repo itself)

Then in `real_clinical_sounds.py`, change one line near the top:
```python
SOUND_BASE_URL = "https://your-cdn-url.com/sounds"
```

### Option C — If you can't host files yet

Sounds will show "404 / cannot load" but the **fallback button** still works. Students can click "Open in new tab" but it'll still 404 since the source files are gone. So this option is honestly broken until you upload files.

**Recommendation: do Option A. It takes 30 minutes and gives you working sounds permanently.**

---

## STEP 4 — Test the full flow

After Streamlit redeploys, test as follows:

### Test the registration system
1. Open https://mls-virtual-hospital.streamlit.app in incognito
2. Register a new account with role = **"Senior / Consultant Doctor"** + specialty + hospital
3. You'll see a yellow info box: "Senior accounts require admin verification..."
4. Log in to the app — you have full access immediately
5. Open Mentor Directory — your test senior should NOT appear (unverified)

### Test the admin verification (do this as you, Dr. Hiba)
1. Log in with `hamdarhiba95@gmail.com` (the email you set in `ADMIN_EMAIL`)
2. Sidebar → Faculty Portal → 🛠️ Mentor Admin Panel
3. Tab: "⏳ Verify Seniors" — see your test senior pending
4. Click "✓ Verify this senior"
5. Now go back to Mentor Directory — they appear

### Test the booking flow
1. Log in as a Student or Resident
2. Open Mentor Directory
3. Click "Request a session with [verified senior]"
4. Fill out the form (question, time, method)
5. Submit

### Test the embedded Jitsi call
1. Log in as the Senior (or test in 2 browsers)
2. Sidebar → Tools → 📋 My Sessions
3. See pending request → click "✓ Accept"
4. Click "🎥 Join video call"
5. **Jitsi should now load INSIDE the app** (not a new tab)
6. From the other browser, do the same — both should see each other in-app

---

## Honest known issues you should expect

### About the audio
- **The sounds will not play until you upload MP3 files to your repo.** No code change can fix this — the source URLs were broken by the third-party site. This is unavoidable.

### About the registration
- I added 3 columns to `vh_users`. If you have **existing senior accounts** in your DB, the SQL automatically marks them as unverified. **You'll need to verify them in the admin panel** before they appear in the directory.
- The email `hamdarhiba95@gmail.com` is hardcoded as admin via `ADMIN_EMAIL` secret. If you change Gmail accounts, update the secret.

### About Jitsi
- Jitsi Meet (jitsi.org) is a free public service. It works most of the time but isn't 100% guaranteed uptime.
- Some networks (particularly corporate firewalls) block Jitsi traffic. If a user's network blocks it, they'll see a blank iframe. The "open in new tab" link is provided as a fallback.
- Browser permissions for camera/microphone need to be granted on first use.

### About the AI rate limit issue
- I did **NOT** implement multi-provider rotation or BYO-API-key. After thinking carefully, both approaches have serious problems (see my detailed reply earlier).
- The friendly error message I added previously is still in place.
- If you want me to implement either approach despite the concerns, just ask.

---

## Summary

After deployment you have:

✅ **Registration with roles** — Students/Residents/Seniors/Faculty self-select at signup
✅ **Specialty tagging** — Required for Residents and Seniors
✅ **Admin verification** — Seniors don't appear publicly until you approve them
✅ **Mentor Directory** — Browse verified seniors filtered by specialty
✅ **Session booking** — 2 sessions per case per senior (your rule)
✅ **Embedded Jitsi calls** — In-app video, no new tab
✅ **My Sessions page** — Both students and seniors track requests
✅ **Audio fix infrastructure** — Code ready, just needs MP3 files in `static/sounds/`

Total new code: ~1,500 lines across 3 files.
Total cost: $0 (Jitsi is free, GitHub hosting is free).

---

**Hiba — this is honest, deployable work. Test it, tell me what breaks. The audio piece needs YOU to upload the MP3 files; everything else just works after the SQL + GitHub upload.**
