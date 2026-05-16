# Admin User Panel + Email Notifications — Deployment Guide

## What this delivers

A new Faculty Portal entry **👥 User Management** with three tabs:

### Tab 1 — 👥 All Users
- See every registered user (old + new) with name, email, role, specialty, hospital, verified status, registration date
- Search by name or email
- Filter by role (student/resident/senior/faculty)
- Filter to verified only
- **Export to CSV** for backups or external analysis

### Tab 2 — 📧 Send Broadcast
- Compose an email to all registered users
- Filter by role (e.g., only students)
- 3 quick templates: New Case, New Image, General Announcement
- Optional call-to-action button + URL
- Confirmation checkbox before sending (prevents accidents)
- Sends one-by-one with throttling to respect Gmail rate limits

### Tab 3 — 📋 Notification History
- Audit log of every broadcast you've sent
- Date, subject, success/fail counts, body preview
- Useful for tracking what students have been informed about

---

## ✅ Important reassurances

### Old users: **NO need to re-register!**

Your existing users' accounts work fine. All updates we've made added NEW tables and features — we never touched `vh_users`. They keep:
- Their email + password
- Their XP and progress
- Access to all new features

Old users may have empty values for new fields (role, specialty, hospital) — but the platform still works for them. Only if they want to register as a Senior would they need profile editing (a feature we can add later if needed).

---

## Files in this delivery

| File | Action |
|---|---|
| `app.py` | **Replace** existing on GitHub |
| `admin_user_panel.py` | **NEW** — upload to GitHub |

---

## STEP 1 — Run Supabase SQL

Open **Supabase → SQL Editor → New query**, paste this, click **Run**:

```sql
-- Email notification history — audit trail
CREATE TABLE IF NOT EXISTS public.email_notifications (
    notification_id  text PRIMARY KEY,
    subject          text NOT NULL,
    body_preview     text DEFAULT '',
    sent_by          text DEFAULT '',
    n_recipients     integer DEFAULT 0,
    n_success        integer DEFAULT 0,
    n_failed         integer DEFAULT 0,
    sent_at          timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_email_notif_sent ON public.email_notifications(sent_at DESC);

ALTER TABLE public.email_notifications ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow all email_notifications" ON public.email_notifications;
CREATE POLICY "Allow all email_notifications" ON public.email_notifications
    FOR ALL USING (true) WITH CHECK (true);
```

Expected: "Success. No rows returned."

---

## STEP 2 — Verify email credentials in Streamlit secrets

The system uses your **existing** email infrastructure (the one you set up for mentor verification emails). Verify these are in your Streamlit Cloud → Settings → Secrets:

```toml
NOTIFY_EMAIL = "your-gmail-address@gmail.com"
NOTIFY_EMAIL_PASSWORD = "your-16-char-gmail-app-password"
```

**If they're already there from earlier setup, you're good.** If not:

1. Go to https://myaccount.google.com/apppasswords
2. Create an app password (16 characters, no spaces)
3. Add both secrets to Streamlit Cloud

---

## STEP 3 — Upload to GitHub

1. Upload `app.py` (replaces existing)
2. Upload `admin_user_panel.py` (NEW file)

Commit message: `Add admin user management + email broadcasts`

Wait ~60 seconds for Streamlit to redeploy.

---

## STEP 4 — Test the workflow

### Test 1 — View user list

1. Log in as admin (`hamdarhiba95@gmail.com`)
2. Sidebar → 👨‍🏫 Faculty Portal → **👥 User Management**
3. Tab **👥 All Users** — you should see every registered user
4. Try the search box → type any name or email
5. Try filtering by role
6. Click **📥 Export as CSV** → downloads a CSV file you can open in Excel

### Test 2 — Send a test broadcast (start small!)

**IMPORTANT:** Test with yourself first before sending to all users.

1. Tab **📧 Send Broadcast**
2. **Recipients:** Uncheck all roles except one that ONLY YOU are in
   - Or, easier: temporarily change your own user role in Supabase to `test_only` to isolate yourself
3. Click the **📋 New Case template** button
4. Edit the subject + body to your liking
5. Check the confirmation box
6. Click **📤 Send Broadcast**
7. Wait ~5 seconds
8. **Check your inbox** — you should receive a nicely formatted email

### Test 3 — Real broadcast after upload a case

1. Upload a new case via Case Creator
2. Approve it
3. Go to User Management → 📧 Send Broadcast
4. Click **📋 New Case template**
5. Customize: add the case title in the body
6. Send to all students

### Test 4 — Notification history

1. Tab **📋 Notification History**
2. See all broadcasts you've sent
3. Click any entry to see details

---

## ⚠️ Honest caveats about email sending

### 1. Gmail free tier limit: ~500 emails/day

Free Gmail accounts can send **~500 emails per 24 hours**. If you have:
- 50 users → no problem, you can broadcast multiple times daily
- 100 users → still fine
- 500+ users → space out broadcasts across multiple days
- 1000+ users → you'll need a paid email service (SendGrid, Resend, Mailgun)

### 2. Sending speed: ~0.5 seconds per email

A broadcast to 100 users takes ~50 seconds. To 500 users → ~4 minutes. Don't close the browser tab during sending.

### 3. Some emails will fail

Common reasons:
- Recipient's spam filter
- Old/invalid email addresses
- Gmail blocking burst-send patterns

The system shows which failed. You can resend just to the failed ones later.

### 4. Email may land in spam initially

First few broadcasts may go to students' spam folders. Tell them once:
> "Check your spam folder — emails from MLS Virtual Hospital may land there initially. Mark as 'Not spam' to fix this."

### 5. Privacy: be honest about email usage

Best practice when promoting your platform:
- Mention in registration that they'll receive occasional update emails
- Add an unsubscribe note (or just say "reply with UNSUBSCRIBE to stop")
- Don't send more than 1-2 emails per week max

### 6. Don't spam!

Sending too many emails leads to:
- Students unsubscribing / blocking
- Gmail flagging your account
- Damaged reputation

**Honest rule of thumb:** Email students when there's REAL value. Maybe 2-4 broadcasts per month max. Treat their inbox with respect.

---

## How to use this in practice

### Workflow for "new case" notifications

1. You generate a case via AI Case Creator
2. You review and approve it
3. You navigate to User Management → Send Broadcast
4. Click "📋 New Case template"
5. Customize:
   - Subject: `🆕 New case: Atrial fibrillation in the ED`
   - Body: "Hi there, I just published a new case on managing atrial fibrillation in an ED setting. Come practice your clinical reasoning!"
   - CTA: "Open Platform →"
6. Send to students

### Workflow for monthly digest

End of each month, send a summary:
- Subject: "📅 MLS Virtual Hospital — November update"
- Body: bulletted list of new cases, features, MCQs added
- CTA: "Explore the platform →"

### Workflow for re-engagement

Inactive users haven't logged in for 30 days:
- Personalized email mentioning what's new
- "We miss you! Here's what's been added since you last visited..."

---

## What I did NOT change

- ❌ Existing user registration flow (works as before)
- ❌ Existing `vh_users` table structure (NO changes)
- ❌ Existing mentor email notification system (still works)
- ❌ Any other features (MCQ, Case Creator, RAG, etc.)

This module is purely additive — nothing breaks.

---

## Privacy & legal considerations

I want to flag a few things honestly:

### 1. Get consent during registration

Your current registration may not explicitly say "we may email you with updates." This is generally fine for transactional/educational emails to people who voluntarily signed up for an educational platform, but to be safe:

**Suggested update to registration:** Add a small disclaimer above the Sign Up button:
> "By creating an account, you agree to receive occasional educational emails from MLS Virtual Hospital. You can unsubscribe anytime by replying to any email."

I can add this in a future update if you want.

### 2. GDPR / privacy compliance

If you have EU users (or your platform spreads to Europe), you technically need:
- A privacy policy
- A way to delete user data on request
- Clear consent for marketing emails

For now, with mostly Lebanese users and an educational tool, this is low-risk. But if you grow internationally, plan for this.

### 3. Unsubscribe mechanism

Currently no built-in unsubscribe link. If a user replies "STOP" you'd manually remove them. For larger scale, we'd need to add an unsubscribe flow. Tell me if/when this becomes important.

---

## Deployment checklist

- [ ] Run the Supabase SQL block (creates `email_notifications` table)
- [ ] Verify `NOTIFY_EMAIL` + `NOTIFY_EMAIL_PASSWORD` are in Streamlit secrets
- [ ] Upload new `app.py` to GitHub
- [ ] Upload new `admin_user_panel.py` to GitHub (NEW file)
- [ ] Wait 60 seconds for Streamlit redeploy
- [ ] Log in as admin → see "👥 User Management" in Faculty Portal sidebar
- [ ] Test with a small recipient list first (just yourself)
- [ ] When confident, do a real broadcast

---

## Summary

You now have:
- **User list** with search, filter, CSV export
- **Email broadcasts** with role filtering, templates, confirmation
- **Notification history** for audit and tracking

Plus the answer you needed: **old users do not need to re-register.**

This is genuinely useful for engagement and retention. Use it wisely — don't spam, but do keep students informed when there's real value.

---

**Deploy this, test with a small group first, then scale up. Let me know if anything fails during deployment.** 👍
