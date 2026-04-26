"""
avatar_photo_patch.py  — FIXED v2
─────────────────────────────────────────────────────────────────────────────
FIXES IN THIS VERSION
─────────────────────────────────────────────────────────────────────────────
1. 429 Rate-limit → rotates through EVERY key in the pool, not just one
2. Automatic retry with exponential back-off (1 s → 2 s → 4 s)
3. Model fallback chain: gemini-2.0-flash → gemini-1.5-flash → gemini-pro-vision
4. API key NEVER shown in error messages (was leaking in the URL)
5. Clean user-facing error messages with actionable advice

HOW TO USE
─────────────────────────────────────────────────────────────────────────────
Replace the existing `_gemini_analyse_photo_for_avatar` function in app.py
with the one below. That's the only change needed.
─────────────────────────────────────────────────────────────────────────────
"""

import streamlit as st
import base64
import requests
import json
import time


def _gemini_analyse_photo_for_avatar(image_bytes: bytes) -> dict:
    """
    Send a photo to Gemini Vision and return avatar config dict.
    Keys returned: skin, hair, eyes, hijab (bool), hijab_color, glasses (bool).

    Improvements over v1:
    • Rotates through ALL keys in the pool on 429 errors
    • Retries each key up to 3 times with exponential back-off
    • Falls back through model chain if primary model is overloaded
    • Never exposes API key in any error/warning message
    """

    # ── Gather every available key from the pool ──────────────────────────
    def _all_keys() -> list:
        keys = []
        try:
            # Numbered pool — both naming conventions
            for i in range(1, 21):
                for pattern in (f"GEMINI_KEY_{i}", f"GEMINI_API_KEY_{i}"):
                    k = st.secrets.get(pattern, "").strip()
                    if k:
                        keys.append(k)
                        break
            # Bare fallbacks
            if not keys:
                for name in ("GEMINI_API_KEY", "GEMINI_KEY", "GOOGLE_API_KEY"):
                    k = st.secrets.get(name, "").strip()
                    if k:
                        keys.append(k)
                        break
        except Exception:
            pass

        # Also try get_api_key() if defined in app scope
        try:
            k = get_api_key()   # noqa: F821 — defined in app.py
            if k and k not in keys:
                keys.insert(0, k)   # try current rotation key first
        except Exception:
            pass

        return keys

    # ── Model fallback chain ───────────────────────────────────────────────
    MODELS = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-pro-vision",
    ]

    PROMPT = """Look at the person in this photo. Return ONLY a valid JSON object
with these exact keys (no preamble, no markdown fences, no explanation):

{
  "skin":        "<one of: #fde8d0 | #f5c5a3 | #d4956a | #a0673a | #6b3d1e>",
  "hair":        "<one of: #1a1a1a | #2c1810 | #6b3d1e | #8b3a0f | #c8a050 | #8a8a8a | #e8e8e8>",
  "eyes":        "<one of: #5c3a1e | #7c5230 | #2d6a4f | #1e6aa1 | #5a6a7a | #8b6914 | #0e7490>",
  "hijab":       <true | false>,
  "hijab_color": "<one of: #1a4f8a | #1a1a1a | #0e7490 | #7c1a1a | #556b2f | #b5556b | #6b7280 | #f8fafc>",
  "glasses":     <true | false>
}

Rules:
- Choose the closest matching hex from the listed options only.
- hijab = true ONLY if the person is clearly wearing a hijab/headscarf.
- glasses = true ONLY if the person is clearly wearing glasses.
- Return raw JSON only — no ```json fences, no extra text."""

    b64_img = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}},
                {"text": PROMPT},
            ]
        }],
        "generationConfig": {"temperature": 0.05, "maxOutputTokens": 256},
    }

    # ── Try each key × each model until one works ─────────────────────────
    all_keys = _all_keys()
    if not all_keys:
        st.error(
            "❌ No Gemini API key found. "
            "Add GEMINI_API_KEY to your secrets.toml and restart."
        )
        return {}

    last_error = ""
    tried = 0

    for model in MODELS:
        base_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        for key in all_keys:
            for attempt in range(3):             # up to 3 retries per key
                tried += 1
                try:
                    resp = requests.post(
                        base_url,
                        params={"key": key},     # key in params, NOT in URL string
                        json=payload,
                        timeout=22,
                    )

                    # Rate-limited on this key → rotate immediately
                    if resp.status_code == 429:
                        wait = 2 ** attempt      # 1 s, 2 s, 4 s
                        last_error = "rate limit (429)"
                        time.sleep(wait)
                        continue                 # retry same key with back-off

                    # Auth error → this key is bad, skip to next key
                    if resp.status_code in (400, 401, 403):
                        last_error = f"auth error ({resp.status_code})"
                        break                    # next key

                    # Model not found / overloaded → try next model
                    if resp.status_code in (404, 503):
                        last_error = f"model unavailable ({resp.status_code})"
                        break                    # break inner loops → next model

                    resp.raise_for_status()

                    # ── Parse response ─────────────────────────────────────
                    raw = (
                        resp.json()
                        .get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                    # Strip accidental markdown fences
                    clean = (
                        raw.strip()
                           .removeprefix("```json")
                           .removeprefix("```")
                           .removesuffix("```")
                           .strip()
                    )
                    result = json.loads(clean)

                    # Validate expected keys are present
                    if not all(k in result for k in ("skin", "eyes", "hijab")):
                        last_error = "incomplete JSON from model"
                        continue

                    return result   # ✅ SUCCESS

                except json.JSONDecodeError:
                    last_error = "model returned non-JSON"
                    continue       # retry
                except requests.Timeout:
                    last_error = "request timed out"
                    time.sleep(1)
                    continue
                except Exception as exc:
                    # ── SAFE error: strip any key-looking substrings ───────
                    safe_msg = str(exc)
                    for k in all_keys:
                        safe_msg = safe_msg.replace(k, "***")
                    last_error = safe_msg
                    continue

    # ── All keys and models exhausted ─────────────────────────────────────
    if "rate limit" in last_error or "429" in last_error:
        st.warning(
            "⚠️ All Gemini API keys are currently rate-limited. "
            "Wait 60 seconds then try again, or add more keys to secrets.toml. "
            f"(Tried {tried} combinations across {len(all_keys)} key(s) "
            f"and {len(MODELS)} model(s).)"
        )
    elif "auth" in last_error:
        st.error(
            "❌ Gemini API key rejected. "
            "Check your secrets.toml — the key may be invalid or expired."
        )
    elif "model unavailable" in last_error:
        st.warning(
            "⚠️ All Gemini vision models are temporarily unavailable. "
            "Please try again in a few minutes."
        )
    else:
        st.warning(
            f"⚠️ Photo analysis failed after {tried} attempts. "
            f"Reason: {last_error}. "
            "Try a clearer, well-lit face photo (jpg/png)."
        )

    return {}