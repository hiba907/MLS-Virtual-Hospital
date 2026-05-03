# DeepSeek Fallback — Setup Guide

DeepSeek is now wired into your app as a **fallback provider**. When all 20 Gemini keys × 3 models are exhausted (rate-limited), the app automatically tries DeepSeek before showing the error message.

---

## How it works

```
Student asks something
        ↓
Try Gemini key #1 → rate limited
Try Gemini key #2 → rate limited
... (all 20 keys × 3 models)
        ↓
ALL Gemini exhausted
        ↓
Try DeepSeek with same conversation
        ↓
   ✓ Success → response with "*[Backup AI: DeepSeek]*" tag
   ✗ Fail    → friendly error message
```

Students see normal AI responses with a small `[Backup AI: DeepSeek]` tag at the bottom when DeepSeek answered, so they know which provider was used.

---

## Setup steps

### Step 1 — Get a DeepSeek API key

1. Go to **https://platform.deepseek.com/**
2. Sign up (email + verification, no credit card needed for the free tier)
3. Click **"API keys"** in the left sidebar
4. Click **"Create new API key"**
5. Copy the key — it starts with `sk-` and looks like `sk-abc123...`

You'll get **5 million free tokens** automatically (no card required). That's roughly 250-500 student case interactions before you'd need to top up.

### Step 2 — Add to Streamlit Cloud secrets

1. Open https://share.streamlit.io/ → your app → ⋮ → Settings → Secrets
2. Add this line (anywhere at the top level, before `[epic]`):

```toml
DEEPSEEK_API_KEY = "sk-your-actual-deepseek-key-here"
```

3. Click **Save changes**
4. Streamlit auto-redeploys in ~60 seconds

### Step 3 — Upload the new app.py

Replace `app.py` on GitHub with the new version. Commit message: `Add DeepSeek fallback for AI rate limits`

---

## Testing it works

The cleanest test is to **deliberately trigger rate limits**, but that's hard. Instead:

1. Open the live app and use it normally
2. Watch the Streamlit Cloud logs (⋮ → Manage → Logs)
3. Eventually when Gemini hits a wall, you'll see in logs that DeepSeek was tried
4. Students will see normal responses with `*[Backup AI: DeepSeek]*` tag

If DeepSeek is configured wrong, the error message just falls back to the regular friendly error — no crash.

---

## Honest limitations

### 1. Vision/images partially supported

DeepSeek-Chat doesn't currently support image inputs. So when a student uploads an X-ray and Gemini is rate-limited:
- DeepSeek receives just the **text** part of the prompt
- It does its best reasoning without seeing the image
- A note tells the student: *"Image not directly analyzed — DeepSeek text fallback used because Gemini quota was exhausted."*

This is honest behavior. The student knows DeepSeek didn't actually see their image.

### 2. Quality differences

DeepSeek-Chat is good but not identical to Gemini for medical content. You may notice:
- Slightly different response style (more verbose at times)
- Occasional language switches if the question isn't fully in English
- Less polished medical terminology in some niche specialties

For most clinical reasoning, it performs well. For OSCE-style high-stakes grading, Gemini is still preferred.

### 3. Latency from China-based servers

DeepSeek's infrastructure is in China, so:
- Sometimes slower than Gemini (3-8 seconds vs 1-3 seconds)
- May have brief unavailability during peak hours
- Rare 503 errors when their servers are overloaded

Since DeepSeek is only the fallback, this isn't critical — students rarely hit it unless Gemini is completely exhausted.

### 4. Privacy consideration (worth mentioning)

DeepSeek processes requests on Chinese servers. For:
- General medical education content → fine, no real patient data
- Hypothetical case discussions → fine
- Real patient data → **never use through any AI, including DeepSeek**

Your existing system prompts already discourage real patient data sharing. If you have students in regions with strict data sovereignty rules (some EU/UAE), they may prefer to disable DeepSeek and just see the rate-limit error instead.

To disable DeepSeek for a specific user/situation, simply leave the `DEEPSEEK_API_KEY` secret unset — the code skips DeepSeek entirely if no key is configured.

---

## Cost reality check

**Free tier:** 5M tokens. Roughly 250-500 student case interactions.

**After free tier:**
- DeepSeek-Chat (V3.2): $0.14 per million input tokens, $0.28 per million output tokens
- Same 100 students/day pattern: ~$5-10/month

So even if students burn through the 5M free tokens, paying for DeepSeek as backup is very cheap. You can top up $5-10 at a time as needed.

---

## Comparison vs the "11 free Google accounts" idea

| Approach | Reliability | Code complexity | TOS risk | Cost |
|---|---|---|---|---|
| 11 free Google accounts | ❌ Low (gets banned) | High | High | $0 (until banned) |
| **DeepSeek fallback** | ✅ Decent | Low (already built) | None | $0-10/mo |
| Single paid Gemini | ✅ High | None | None | $20/mo |

DeepSeek is the **honest cheap option** — no TOS gray area, no risk of mass account ban, costs nothing for low volume.

---

## What changed in your code

1. **New module section** at lines ~830-940 in `app.py`:
   - `_deepseek_key()` — reads the secret
   - `_deepseek_available()` — checks if it's configured
   - `_gemini_history_to_openai()` — converts message format
   - `_call_deepseek()` — text fallback
   - `_call_deepseek_with_image()` — image fallback (text-only response)

2. **Two integration points:**
   - `call_ai()` — tries DeepSeek when Gemini fully exhausted
   - `call_ai_with_image()` — tries DeepSeek (text-only) when Gemini fully exhausted

3. **Visible to users:** Responses from DeepSeek end with `*[Backup AI: DeepSeek]*` so students see which provider was used.

That's it. No changes to UI, sidebar, or other modules.

---

## Quick troubleshooting

**Q: How do I confirm DeepSeek is being called?**
Check Streamlit Cloud logs. When Gemini fails, you should see successful `200` responses from `api.deepseek.com` in the logs.

**Q: My students still see the rate-limit error sometimes.**
That means BOTH Gemini AND DeepSeek failed. Possible causes:
- DeepSeek key missing or invalid (check the secret)
- DeepSeek servers temporarily down (rare but happens)
- Network issue on Streamlit's end

**Q: How do I disable DeepSeek?**
Just delete the `DEEPSEEK_API_KEY` line from your Streamlit secrets and save. The app silently goes back to Gemini-only.

**Q: Can I use a paid DeepSeek key?**
Yes — same setup. Once you top up, your free tier extends naturally. The code is identical.

---

That's it. Two changes: get a key + paste it as a secret. The code already knows what to do.
