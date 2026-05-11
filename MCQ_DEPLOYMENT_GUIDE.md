# Hybrid MCQ System — Deployment Guide

## What this delivers

After every case (post-diagnosis submission), students get **5 MCQs** to test their knowledge. The system:

1. **First checks** if you (admin) have ≥3 approved MCQs for this case → serves them (free, fast, vetted)
2. **Otherwise** generates 5 new MCQs with AI on the fly → saves as drafts for you to review
3. **Tracks** every student attempt for analytics
4. **Awards XP** for completion (5 base + 5 per correct answer)
5. **Lets students flag** problematic MCQs → you review flags in admin panel
6. **You approve/edit/reject** drafts in the Faculty Portal

The hybrid model gives you the best of both worlds: quality where it matters (curated bank), speed where needed (AI fallback).

---

## Files in this delivery

| File | Action |
|---|---|
| `app.py` | **Replace** existing on GitHub |
| `mcq_system.py` | **NEW** — upload to GitHub |

---

## STEP 1 — Run Supabase SQL (REQUIRED)

Open **Supabase Dashboard → SQL Editor → New query** and paste this entire block:

```sql
-- ─────────────────────────────────────────────────────────────────────
-- MCQ Hybrid System — schema
-- ─────────────────────────────────────────────────────────────────────

-- 1. The MCQ bank
create table if not exists public.case_mcqs (
    mcq_id          text primary key,
    case_id         text not null,
    case_title      text default '',
    question        text not null,
    choice_a        text not null,
    choice_b        text not null,
    choice_c        text not null,
    choice_d        text not null,
    correct_answer  text not null,
    explanation     text not null,
    category        text default 'general',
    status          text default 'draft',
    generated_by    text default 'ai',
    generator_model text default '',
    flag_count      integer default 0,
    flag_reasons    text default '',
    approved_at     timestamptz,
    approved_by     text default '',
    created_at      timestamptz default now()
);

create index if not exists idx_mcqs_case_status on public.case_mcqs(case_id, status);
create index if not exists idx_mcqs_status on public.case_mcqs(status, created_at);
create index if not exists idx_mcqs_flags on public.case_mcqs(flag_count) where flag_count > 0;

alter table public.case_mcqs enable row level security;
drop policy if exists "Allow all case_mcqs" on public.case_mcqs;
create policy "Allow all case_mcqs" on public.case_mcqs
    for all using (true) with check (true);

-- 2. Per-attempt tracking (analytics)
create table if not exists public.mcq_attempts (
    attempt_id    text primary key,
    user_id       text not null,
    user_name     text default '',
    mcq_id        text not null,
    case_id       text not null,
    was_correct   boolean default false,
    created_at    timestamptz default now()
);

create index if not exists idx_attempts_user on public.mcq_attempts(user_id, created_at);
create index if not exists idx_attempts_mcq  on public.mcq_attempts(mcq_id);

alter table public.mcq_attempts enable row level security;
drop policy if exists "Allow all mcq_attempts" on public.mcq_attempts;
create policy "Allow all mcq_attempts" on public.mcq_attempts
    for all using (true) with check (true);
```

Click **Run**. You should see "Success. No rows returned."

---

## STEP 2 — Upload 2 Python files to GitHub

Go to https://github.com/hiba907/MLS-Virtual-Hospital and upload:

1. **`app.py`** (replaces existing — has the MCQ hooks)
2. **`mcq_system.py`** (NEW file — the whole MCQ module)

Commit message: `Add Hybrid MCQ system (auto-MCQs after diagnosis)`

Streamlit auto-redeploys in ~60 seconds.

---

## STEP 3 — Test the full flow (~10 minutes)

### Test 1 — Student gets MCQs after diagnosis

1. Open the live app in incognito (Ctrl+Shift+N)
2. Log in as a student
3. Pick any case from the Case Library
4. Go through Patient Interview / Examination / Labs (or skip ahead)
5. Go to **Submit Diagnosis** → fill in diagnosis, treatment, reasoning → click **Submit for Evaluation**
6. After AI evaluation, **scroll down** — you should see a blue gradient banner:
   > 🧠 Test your knowledge — 5 quick questions
   > [📝 Start MCQ Session]
7. Click **Start MCQ Session**
8. Wait ~10-30 seconds (AI is generating MCQs for the first time)
9. Answer the 5 MCQs one at a time
10. After each answer, you see the explanation
11. End of session shows your score + XP earned

### Test 2 — As admin, review the drafts

1. In your normal browser (logged in as `hamdarhiba95@gmail.com`)
2. Sidebar → **👨‍🏫 FACULTY PORTAL** → **📝 MCQ Bank Manager**
3. Tab **⏳ Pending Review** — you should see 5 draft MCQs from the case you just tested
4. Click any draft to expand
5. Edit question/choices/answer/explanation if needed
6. Click **✓ Approve** → moves to approved bank

### Test 3 — Bank reuse (no AI call this time)

1. Approve at least 3 MCQs for the case
2. Switch to incognito, log in as a fresh student
3. Pick the SAME case → submit diagnosis → start MCQ session
4. This time the MCQs load instantly (served from approved bank, no AI call)
5. You see the curated MCQs you approved

### Test 4 — Flagging

1. As student, during an MCQ, expand **⚠️ Report this question**
2. Write a reason like "B is also correct"
3. Submit → success message
4. As admin → Faculty Portal → MCQ Bank Manager → tab **🚩 Flagged by Students**
5. You see the flagged MCQ with the student's reason
6. Options: Remove / Edit & re-approve / Clear flags

---

## What you'll see in the sidebar

After deployment, the sidebar gets ONE new entry for admins:

**👨‍🏫 FACULTY PORTAL**
- 📊 Analytics Dashboard
- 🏥 Case Creator
- 🛠️ Mentor Admin Panel
- **📝 MCQ Bank Manager** ← NEW

Students don't see a separate MCQ menu — they access MCQs automatically after submitting a diagnosis. This keeps the UX simple and tied to the case they just finished.

---

## How the AI generation works

When a student starts an MCQ session for a case without a bank:

1. Module sends Gemini a structured prompt with the case details
2. Asks for exactly 5 MCQs as a JSON array
3. Each MCQ must have: question, 4 choices (A-D), correct answer, explanation, category
4. Module validates the JSON, rejects malformed items
5. Saves valid MCQs as drafts in Supabase
6. Serves them to the student immediately (no wait for admin approval — that's why the hybrid works)

If Gemini is rate-limited and you have DeepSeek configured, it automatically falls back through your existing call_ai chain.

---

## Honest caveats

### 1. First time per case = AI call cost

The first student to do MCQs for a specific case triggers an AI generation. After that, all students with the same case (if you've approved ≥3 MCQs) get the bank — free and fast.

Cost per case (first time only): ~$0.005 to $0.02 on Gemini Flash, depending on case length.

### 2. AI MCQs are draft quality

Until you review and approve them, they ARE shown to the student who triggered the generation. This is by design (so they don't wait). But:
- The drafts go to your queue
- You can edit and approve them properly
- Next time anyone does that case, they get the curated version

For most cases this is fine — AI MCQs are usually decent. But occasionally one will have:
- A distractor that's actually correct
- Ambiguous wording
- A "trick" question students will dislike

That's why the **flag** mechanism exists. Students who notice issues report them, you review.

### 3. Category coverage isn't guaranteed

You asked for "5 MCQs covering diagnosis, management, complications, etc." but the AI may give you 3 diagnosis questions and 2 management. The prompt asks for variety but doesn't enforce it strictly.

You can manually rebalance in the admin panel if a case has too much of one category.

### 4. No images in MCQs (yet)

This version generates text-only MCQs. Image-based MCQs ("Identify this rash" with a picture) are out of scope for now.

### 5. Reset of MCQ session state

If a student starts an MCQ session, then navigates away mid-session, then comes back — the session resets. There's no "resume in progress" feature. For 5 short questions this is acceptable.

---

## XP rewards

When a student completes an MCQ session:
- **5 XP per question** completed (base)
- **5 XP bonus per correct answer**
- So 5/5 correct = **50 XP total**, 3/5 correct = **40 XP**, 0/5 = **25 XP**

This integrates with your existing Tier 1 gamification system (level progression, badges, leaderboard).

---

## What I did NOT change

- ❌ Existing case library, patient interview, examination, labs, imaging modules — all untouched
- ❌ Mentor directory and Jitsi calls — untouched
- ❌ Tier 1 (gamification, Ask Dr. Hiba) — untouched
- ❌ DeepSeek fallback — still works as before
- ❌ Audio sounds — still pending your U Mich upload
- ❌ Physical exam modality-honesty — still in place from Option A

---

## Summary checklist

- [ ] Run the Supabase SQL block (creates `case_mcqs` + `mcq_attempts` tables)
- [ ] Upload new `app.py` to GitHub
- [ ] Upload new `mcq_system.py` to GitHub (NEW file)
- [ ] Wait 60 seconds for Streamlit redeploy
- [ ] Test as student: pick case → submit diagnosis → see MCQ banner → take quiz
- [ ] Test as admin: Faculty Portal → MCQ Bank Manager → approve drafts

After that, you have a publishable feature: AI-generated assessment with admin curation loop. That's a genuine PhD methodology angle.

---

Hiba — this is the largest single feature build so far. Test thoroughly, especially the AI generation path (it relies on your existing Gemini keys + DeepSeek fallback). If you hit rate limits during testing, the friendly error will appear and you can retry.

Tell me how it goes. 👍
