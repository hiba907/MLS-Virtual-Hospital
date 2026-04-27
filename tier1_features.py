"""
═══════════════════════════════════════════════════════════════════════════
  MLS Virtual Hospital — Tier 1 Features Module
  ─────────────────────────────────────────────────────────────────────────
  Two major features combined into one deployable file:

  1. GAMIFICATION SYSTEM
     • XP (experience points) for every action
     • Level progression (10 levels: Novice → Master Clinician)
     • 15 achievement badges across 5 categories
     • Daily streak tracking
     • Weekly leaderboard (anonymous, opt-in)
     • Personal stats dashboard

  2. ASK MENTOR SYSTEM
     • Direct WhatsApp + Email contact with mentor
     • Smart message pre-filling with full case context
     • Floating "Ask Dr. Hiba" help button on every page (app-wide)
     • Multiple entry points across the app
     • Daily limit: 3 questions per student per day (configurable)

  Author: Hiba Hamdar — Academy of Medical Learning Skills
  Copyright (c) 2026 — All Rights Reserved
═══════════════════════════════════════════════════════════════════════════

USAGE
-----
1. Save this file as `tier1_features.py` in the same folder as `app.py`
2. Add to top of app.py:
       try:
           from tier1_features import (
               award_xp, get_user_stats, render_xp_bar, render_stats_dashboard,
               check_and_award_badges, render_ask_mentor_button,
               render_ask_mentor_page, render_leaderboard,
               MENTOR_WHATSAPP, MENTOR_EMAIL,
           )
           TIER1_AVAILABLE = True
       except Exception as e:
           TIER1_AVAILABLE = False
           print(f"Tier 1 features not loaded: {e}")
3. Configure mentor contact in secrets.toml:
       MENTOR_WHATSAPP = "+961XXXXXXXX"   # Your WhatsApp (with country code, no spaces)
       MENTOR_EMAIL    = "you@example.com"
       MENTOR_NAME     = "Hiba"
4. Add to Supabase (SQL editor):
       (See SQL block at the bottom of this file)
5. Add a sidebar entry pointing to render_stats_dashboard().

═══════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from typing import Optional, Dict, List, Tuple, Any
import json
import hashlib

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

# ── Mentor contact info — read from secrets.toml ──────────────────────────
def _safe_secret(key: str, default: str = "") -> str:
    """Get a secret safely, fall back to default if missing."""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

MENTOR_WHATSAPP = _safe_secret("MENTOR_WHATSAPP", "")
MENTOR_EMAIL    = _safe_secret("MENTOR_EMAIL", "hamdarhiba95@gmail.com")
MENTOR_NAME     = _safe_secret("MENTOR_NAME", "Dr. Hiba")

# How many questions a student can ask per DAY.
# Set to None for unlimited.
DAILY_MENTOR_LIMIT = 3

# ── XP rewards table — what each action is worth ──────────────────────────
XP_REWARDS = {
    # Core clinical actions
    "patient_interview_question": 2,
    "physical_exam_performed":     5,
    "lab_panel_ordered":           5,
    "imaging_analyzed":             8,
    "diagnosis_submitted":         15,
    "diagnosis_correct":           25,    # bonus on top of submitted
    # Advanced
    "osce_station_completed":      30,
    "osce_high_score":             20,    # bonus if score >= 80%
    "progress_note_written":       15,
    "flashcard_session":            8,
    # Engagement
    "case_completed":              30,
    "peer_session_completed":      40,
    "doccollab_search":             5,
    "ai_tutor_session":            10,
    # Daily login
    "daily_login":                  5,
    "streak_bonus_3_days":         15,
    "streak_bonus_7_days":         50,
    "streak_bonus_30_days":       200,
}

# ── Level system — XP thresholds and titles ───────────────────────────────
LEVELS = [
    # (min_xp, title, emoji, color_hex)
    (0,      "Novice Student",      "Lv1",  "#94a3b8"),
    (100,    "Junior Student",      "Lv2",  "#60a5fa"),
    (300,    "Clinical Student",    "Lv3",  "#3b82f6"),
    (700,    "Senior Student",      "Lv4",  "#8b5cf6"),
    (1500,   "Foundation Doctor",   "Lv5",  "#a855f7"),
    (3000,   "Resident",            "Lv6",  "#06b6d4"),
    (5000,   "Senior Resident",     "Lv7",  "#10b981"),
    (8000,   "Registrar",           "Lv8",  "#f59e0b"),
    (12000,  "Specialist",          "Lv9",  "#ef4444"),
    (20000,  "Master Clinician",    "Lv10", "#ec4899"),
]

# ── Achievement badges — 15 across 5 categories ───────────────────────────
BADGES = [
    # Format: (id, title, description, icon, category, criteria_func_name)
    # Diagnostic
    ("first_diagnosis", "First Diagnosis", "Submitted your first diagnosis",
     "1st", "diagnostic", "submit_count_>=_1"),
    ("ten_diagnoses", "Ten Diagnoses", "Submitted 10 diagnoses",
     "10x", "diagnostic", "submit_count_>=_10"),
    ("fifty_diagnoses", "Fifty Diagnoses", "Submitted 50 diagnoses",
     "50x", "diagnostic", "submit_count_>=_50"),
    ("perfect_score", "Perfect Score", "Got a 100% on a diagnosis",
     "100", "diagnostic", "perfect_score_>=_1"),
    # Engagement
    ("streak_3", "Three Day Streak", "Logged in 3 days in a row",
     "3d", "engagement", "streak_>=_3"),
    ("streak_7", "Week Streak", "Logged in 7 days in a row",
     "7d", "engagement", "streak_>=_7"),
    ("streak_30", "Month Streak", "Logged in 30 days in a row",
     "30d", "engagement", "streak_>=_30"),
    # Specialty mastery
    ("cardio_apprentice", "Cardio Apprentice",
     "Completed 5 cardiology cases",
     "CV5", "specialty", "specialty_cardiology_>=_5"),
    ("respiratory_apprentice", "Respiratory Apprentice",
     "Completed 5 respiratory cases",
     "RS5", "specialty", "specialty_respiratory_>=_5"),
    ("emergency_apprentice", "Emergency Apprentice",
     "Completed 5 emergency cases",
     "ER5", "specialty", "specialty_emergency_>=_5"),
    # Skills
    ("osce_master", "OSCE Master", "Scored 80%+ on 3 OSCE stations",
     "OSC", "skills", "osce_high_>=_3"),
    ("note_writer", "Note Writer", "Wrote 10 progress notes",
     "PN", "skills", "notes_count_>=_10"),
    ("flashcard_warrior", "Flashcard Warrior",
     "Reviewed 100 flashcards",
     "FC", "skills", "flashcards_>=_100"),
    # Social
    ("peer_pioneer", "Peer Pioneer", "Completed your first peer simulation",
     "P1", "social", "peer_count_>=_1"),
    ("peer_legend", "Peer Legend", "Completed 10 peer simulations",
     "P10", "social", "peer_count_>=_10"),
]

# ═══════════════════════════════════════════════════════════════════════════
# SUPABASE HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def _get_supabase_client():
    """Try to get the Supabase client used by the rest of the app."""
    # Reuse existing helper if available
    for fn_name in ("get_supabase_client", "_get_sb_client"):
        fn = st.session_state.get(fn_name)
        if fn:
            try:
                return fn()
            except Exception:
                pass
    # Fall back: try to build directly from secrets
    try:
        from supabase import create_client
        url = _safe_secret("SUPABASE_URL", "")
        key = _safe_secret("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


def _get_user_id() -> str:
    """Get a stable user id for the current session."""
    # Try common patterns from existing code
    for k in ("user_id", "user_email", "username"):
        v = st.session_state.get(k)
        if v:
            return str(v)
    # Build a fallback based on session
    fallback = st.session_state.get("_anon_uid")
    if not fallback:
        import uuid
        fallback = "anon_" + uuid.uuid4().hex[:12]
        st.session_state["_anon_uid"] = fallback
    return fallback


# ═══════════════════════════════════════════════════════════════════════════
# CORE GAMIFICATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════
def get_user_stats(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Return the full stats record for a user. Creates one if missing."""
    user_id = user_id or _get_user_id()
    client = _get_supabase_client()
    if not client:
        # Fall back to session-only stats
        cache_key = f"_local_stats_{user_id}"
        if cache_key not in st.session_state:
            st.session_state[cache_key] = _empty_stats(user_id)
        return st.session_state[cache_key]
    try:
        r = client.table("user_stats").select("*").eq("user_id", user_id).execute()
        if r.data:
            return r.data[0]
        # Create new record
        new_rec = _empty_stats(user_id)
        client.table("user_stats").insert(new_rec).execute()
        return new_rec
    except Exception as e:
        # Database table missing or other error — fall back to session
        cache_key = f"_local_stats_{user_id}"
        if cache_key not in st.session_state:
            st.session_state[cache_key] = _empty_stats(user_id)
        return st.session_state[cache_key]


def _empty_stats(user_id: str) -> Dict[str, Any]:
    return {
        "user_id":        user_id,
        "total_xp":       0,
        "current_streak": 0,
        "longest_streak": 0,
        "last_login":     None,
        "diagnoses_submitted": 0,
        "diagnoses_correct":   0,
        "osce_high_count":     0,
        "notes_count":         0,
        "flashcards_reviewed": 0,
        "peer_sessions":       0,
        "specialty_counts":    {},   # {"cardiology": 5, ...}
        "earned_badges":       [],   # [badge_id, ...]
        "show_on_leaderboard": True,
        "display_name":        "",
    }


def _save_user_stats(stats: Dict[str, Any]) -> None:
    """Persist stats record to Supabase if available."""
    client = _get_supabase_client()
    if not client:
        cache_key = f"_local_stats_{stats['user_id']}"
        st.session_state[cache_key] = stats
        return
    try:
        # Convert dict fields to JSON for Postgres
        record = dict(stats)
        if isinstance(record.get("specialty_counts"), dict):
            record["specialty_counts"] = json.dumps(record["specialty_counts"])
        if isinstance(record.get("earned_badges"), list):
            record["earned_badges"] = json.dumps(record["earned_badges"])
        client.table("user_stats").upsert(record).execute()
    except Exception:
        # Save locally as fallback
        cache_key = f"_local_stats_{stats['user_id']}"
        st.session_state[cache_key] = stats


def _normalize_stats(stats: Dict[str, Any]) -> Dict[str, Any]:
    """Convert JSON strings back to native objects after Supabase reads."""
    s = dict(stats)
    if isinstance(s.get("specialty_counts"), str):
        try:
            s["specialty_counts"] = json.loads(s["specialty_counts"])
        except Exception:
            s["specialty_counts"] = {}
    if isinstance(s.get("earned_badges"), str):
        try:
            s["earned_badges"] = json.loads(s["earned_badges"])
        except Exception:
            s["earned_badges"] = []
    return s


# ═══════════════════════════════════════════════════════════════════════════
# AWARD XP — THE MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
def award_xp(action: str, *, amount: Optional[int] = None,
             metadata: Optional[Dict[str, Any]] = None,
             toast: bool = True) -> int:
    """Award XP for an action. Returns total XP after award.

    Usage:
        award_xp("patient_interview_question")
        award_xp("diagnosis_correct", metadata={"specialty": "cardiology"})
        award_xp("custom_action", amount=10)
    """
    if amount is None:
        amount = XP_REWARDS.get(action, 0)
    if amount <= 0:
        return get_user_stats().get("total_xp", 0)

    user_id = _get_user_id()
    stats = _normalize_stats(get_user_stats(user_id))

    # Update XP
    old_xp = stats.get("total_xp", 0)
    stats["total_xp"] = old_xp + amount

    # Update domain counters
    if action == "diagnosis_submitted":
        stats["diagnoses_submitted"] = stats.get("diagnoses_submitted", 0) + 1
    elif action == "diagnosis_correct":
        stats["diagnoses_correct"] = stats.get("diagnoses_correct", 0) + 1
    elif action == "osce_high_score":
        stats["osce_high_count"] = stats.get("osce_high_count", 0) + 1
    elif action == "progress_note_written":
        stats["notes_count"] = stats.get("notes_count", 0) + 1
    elif action == "flashcard_session":
        # Each session counts as ~10 cards reviewed
        stats["flashcards_reviewed"] = stats.get("flashcards_reviewed", 0) + 10
    elif action == "peer_session_completed":
        stats["peer_sessions"] = stats.get("peer_sessions", 0) + 1
    elif action == "case_completed" and metadata and metadata.get("specialty"):
        spec = metadata["specialty"].lower()
        sc = stats.get("specialty_counts", {}) or {}
        sc[spec] = sc.get(spec, 0) + 1
        stats["specialty_counts"] = sc

    # Save
    _save_user_stats(stats)

    # Check for level-up & new badges
    old_level = _level_for_xp(old_xp)
    new_level = _level_for_xp(stats["total_xp"])
    leveled_up = (new_level[0] != old_level[0])

    new_badges = check_and_award_badges(silent=True)

    # Show toast if requested
    if toast:
        msg = f"+{amount} XP"
        if leveled_up:
            msg += f" • Level Up! {new_level[1]}"
        try:
            st.toast(msg, icon="*")
        except Exception:
            pass  # Older Streamlit versions
        for b in new_badges:
            try:
                st.toast(f"Badge unlocked: {b['title']}", icon="*")
            except Exception:
                pass

    return stats["total_xp"]


def update_login_streak() -> Tuple[int, int]:
    """Call once per session at login. Returns (current_streak, xp_awarded)."""
    user_id = _get_user_id()
    stats = _normalize_stats(get_user_stats(user_id))

    today = datetime.now(timezone.utc).date()
    last_login_str = stats.get("last_login")
    last_login = None
    if last_login_str:
        try:
            last_login = datetime.fromisoformat(str(last_login_str).split("T")[0]).date()
        except Exception:
            last_login = None

    # Already logged in today — no change
    if last_login == today:
        return stats.get("current_streak", 0), 0

    # Calculate new streak
    if last_login == today - timedelta(days=1):
        # Consecutive day
        new_streak = stats.get("current_streak", 0) + 1
    else:
        # Streak broken (or first ever)
        new_streak = 1

    stats["current_streak"] = new_streak
    stats["longest_streak"] = max(stats.get("longest_streak", 0), new_streak)
    stats["last_login"] = today.isoformat()

    # Award daily login XP
    xp_gained = XP_REWARDS["daily_login"]
    stats["total_xp"] = stats.get("total_xp", 0) + xp_gained

    # Bonus XP for milestone streaks
    bonus = 0
    if new_streak == 3:
        bonus = XP_REWARDS["streak_bonus_3_days"]
    elif new_streak == 7:
        bonus = XP_REWARDS["streak_bonus_7_days"]
    elif new_streak == 30:
        bonus = XP_REWARDS["streak_bonus_30_days"]
    if bonus:
        stats["total_xp"] += bonus
        xp_gained += bonus

    _save_user_stats(stats)
    return new_streak, xp_gained


# ═══════════════════════════════════════════════════════════════════════════
# BADGE LOGIC
# ═══════════════════════════════════════════════════════════════════════════
def check_and_award_badges(silent: bool = False) -> List[Dict[str, Any]]:
    """Check all badges and return any newly earned ones."""
    user_id = _get_user_id()
    stats = _normalize_stats(get_user_stats(user_id))
    earned = set(stats.get("earned_badges", []) or [])
    new_badges = []

    for badge_id, title, desc, icon, category, criteria in BADGES:
        if badge_id in earned:
            continue
        if _check_criteria(criteria, stats):
            earned.add(badge_id)
            new_badges.append({
                "id": badge_id, "title": title, "description": desc,
                "icon": icon, "category": category,
            })

    if new_badges:
        stats["earned_badges"] = sorted(list(earned))
        _save_user_stats(stats)

    return new_badges


def _check_criteria(criteria: str, stats: Dict[str, Any]) -> bool:
    """Evaluate a badge criteria string like 'submit_count_>=_10'."""
    try:
        parts = criteria.rsplit("_", 2)  # ['submit_count', '>=', '10']
        if len(parts) != 3:
            return False
        field, op, value = parts
        value = int(value)

        # Map fields to actual stat values
        actual = 0
        if field == "submit_count":
            actual = stats.get("diagnoses_submitted", 0)
        elif field == "perfect_score":
            actual = stats.get("diagnoses_correct", 0)
        elif field == "streak":
            actual = stats.get("longest_streak", 0)
        elif field == "osce_high":
            actual = stats.get("osce_high_count", 0)
        elif field == "notes_count":
            actual = stats.get("notes_count", 0)
        elif field == "flashcards":
            actual = stats.get("flashcards_reviewed", 0)
        elif field == "peer_count":
            actual = stats.get("peer_sessions", 0)
        elif field.startswith("specialty_"):
            spec = field.replace("specialty_", "")
            sc = stats.get("specialty_counts", {}) or {}
            actual = sc.get(spec, 0)
        else:
            return False

        if op == ">=":
            return actual >= value
        elif op == ">":
            return actual > value
        elif op == "==":
            return actual == value
        return False
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════
# LEVEL CALCULATION
# ═══════════════════════════════════════════════════════════════════════════
def _level_for_xp(xp: int) -> Tuple[int, str, str, str]:
    """Return (level_number, title, emoji, color) for given XP."""
    for i in range(len(LEVELS) - 1, -1, -1):
        threshold, title, emoji, color = LEVELS[i]
        if xp >= threshold:
            return (i + 1, title, emoji, color)
    return (1, *LEVELS[0][1:])


def _xp_to_next_level(xp: int) -> Tuple[int, int, float]:
    """Return (xp_in_current_level, xp_needed_to_next, percent_progress)."""
    current_level_idx = _level_for_xp(xp)[0] - 1
    current_threshold = LEVELS[current_level_idx][0]
    if current_level_idx < len(LEVELS) - 1:
        next_threshold = LEVELS[current_level_idx + 1][0]
        in_level = xp - current_threshold
        needed = next_threshold - current_threshold
        pct = min(100.0, max(0.0, in_level / needed * 100))
        return (in_level, needed, pct)
    # Max level
    return (xp - current_threshold, 0, 100.0)


# ═══════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════
def render_xp_bar(compact: bool = True) -> None:
    """Compact XP/level bar suitable for sidebar."""
    stats = _normalize_stats(get_user_stats())
    xp = stats.get("total_xp", 0)
    level, title, emoji, color = _level_for_xp(xp)
    in_level, needed, pct = _xp_to_next_level(xp)
    streak = stats.get("current_streak", 0)

    if compact:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,{color}22,{color}08);
                    border:1.5px solid {color}66;border-radius:10px;
                    padding:.7rem .85rem;margin:.4rem 0;">
            <div style="display:flex;justify-content:space-between;align-items:center;
                        font-size:.8rem;color:#0f172a;font-weight:600;">
                <span>{emoji} {title}</span>
                <span style="color:{color};">Lv {level}</span>
            </div>
            <div style="background:#e2e8f0;border-radius:6px;height:6px;margin:.5rem 0 .35rem;
                        overflow:hidden;">
                <div style="background:linear-gradient(90deg,{color},{color}cc);
                            width:{pct:.1f}%;height:100%;border-radius:6px;"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:.7rem;color:#64748b;">
                <span>{xp:,} XP</span>
                <span>{f"+{needed - in_level} to next" if needed > 0 else "MAX"}</span>
            </div>
            <div style="margin-top:.4rem;font-size:.72rem;color:#64748b;">
                Streak: <b style="color:{color};">{streak} days</b>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,{color},{color}aa);
                    color:white;border-radius:14px;padding:1.5rem;text-align:center;">
            <div style="font-size:.85rem;letter-spacing:.1em;opacity:.9;">{emoji} LEVEL {level}</div>
            <div style="font-size:1.6rem;font-weight:800;margin:.4rem 0;">{title}</div>
            <div style="font-size:2.4rem;font-weight:900;margin:.5rem 0;">{xp:,} XP</div>
            <div style="background:rgba(255,255,255,.25);border-radius:6px;height:8px;
                        overflow:hidden;margin:.6rem 0;">
                <div style="background:white;width:{pct:.1f}%;height:100%;border-radius:6px;"></div>
            </div>
            <div style="font-size:.85rem;opacity:.9;">
                {in_level:,} / {needed:,} XP to next level
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_stats_dashboard() -> None:
    """Full stats / achievements / leaderboard dashboard page."""
    st.markdown('<div class="section-header">Your Progress Dashboard</div>',
                unsafe_allow_html=True)

    stats = _normalize_stats(get_user_stats())
    xp = stats.get("total_xp", 0)
    level, title, emoji, color = _level_for_xp(xp)

    # Big level card
    render_xp_bar(compact=False)
    st.markdown("<br/>", unsafe_allow_html=True)

    # Quick stats row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        _stat_card("Diagnoses", stats.get("diagnoses_submitted", 0), "#3b82f6")
    with col2:
        _stat_card("Correct", stats.get("diagnoses_correct", 0), "#10b981")
    with col3:
        _stat_card("Streak", f'{stats.get("current_streak", 0)} d', "#f59e0b")
    with col4:
        _stat_card("Badges", len(stats.get("earned_badges", [])), "#ec4899")

    st.markdown("---")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["Achievements", "Specialty Mastery", "Leaderboard"])

    with tab1:
        _render_badges_section(stats)
    with tab2:
        _render_specialty_section(stats)
    with tab3:
        _render_leaderboard_section()


def _stat_card(label: str, value: Any, color: str) -> None:
    st.markdown(f"""
    <div style="background:white;border:1.5px solid {color}33;border-radius:12px;
                padding:1rem .8rem;text-align:center;">
        <div style="color:{color};font-size:1.7rem;font-weight:800;">{value}</div>
        <div style="color:#64748b;font-size:.78rem;letter-spacing:.05em;
                    text-transform:uppercase;margin-top:.2rem;">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_badges_section(stats: Dict[str, Any]) -> None:
    earned_ids = set(stats.get("earned_badges", []) or [])

    # Group by category
    cats = {}
    for badge_id, title, desc, icon, cat, _ in BADGES:
        cats.setdefault(cat, []).append((badge_id, title, desc, icon))

    cat_titles = {
        "diagnostic":  "Diagnostic Badges",
        "engagement":  "Engagement Badges",
        "specialty":   "Specialty Badges",
        "skills":      "Clinical Skills Badges",
        "social":      "Collaboration Badges",
    }

    for cat_key, badges in cats.items():
        st.markdown(f"### {cat_titles.get(cat_key, cat_key.title())}")
        cols = st.columns(min(5, len(badges)))
        for i, (bid, btitle, bdesc, bicon) in enumerate(badges):
            earned = bid in earned_ids
            with cols[i % len(cols)]:
                opacity = "1.0" if earned else "0.32"
                bg     = "#fef3c7" if earned else "#f1f5f9"
                border = "#f59e0b" if earned else "#cbd5e1"
                txt_c  = "#92400e" if earned else "#94a3b8"
                check  = "<div style='color:#10b981;font-size:.75rem;font-weight:700;margin-top:.2rem;'>UNLOCKED</div>" if earned else ""
                st.markdown(f"""
                <div style="background:{bg};border:2px solid {border};border-radius:10px;
                            padding:.8rem .5rem;text-align:center;opacity:{opacity};
                            min-height:115px;">
                    <div style="font-size:1.1rem;font-weight:900;color:{txt_c};margin-bottom:.3rem;">
                        {bicon}
                    </div>
                    <div style="font-size:.75rem;font-weight:700;color:{txt_c};line-height:1.2;">
                        {btitle}
                    </div>
                    <div style="font-size:.65rem;color:{txt_c};opacity:.8;margin-top:.25rem;line-height:1.2;">
                        {bdesc}
                    </div>
                    {check}
                </div>
                """, unsafe_allow_html=True)
        st.markdown("<br/>", unsafe_allow_html=True)


def _render_specialty_section(stats: Dict[str, Any]) -> None:
    sc = stats.get("specialty_counts", {}) or {}
    if not sc:
        st.info("Complete cases across different specialties to build mastery.")
        return

    # Sort by count
    sorted_specs = sorted(sc.items(), key=lambda x: -x[1])
    for spec, count in sorted_specs:
        # Specialty rank
        if count >= 20:
            rank = "Specialist"; rank_color = "#dc2626"
        elif count >= 10:
            rank = "Senior"; rank_color = "#f59e0b"
        elif count >= 5:
            rank = "Apprentice"; rank_color = "#3b82f6"
        else:
            rank = "Beginner"; rank_color = "#94a3b8"
        next_th = 5 if count < 5 else (10 if count < 10 else (20 if count < 20 else None))
        bar_w = 100 if next_th is None else min(100, int(count / next_th * 100))
        st.markdown(f"""
        <div style="background:white;border:1.5px solid #e2e8f0;border-radius:10px;
                    padding:.8rem 1rem;margin-bottom:.6rem;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-weight:700;color:#0f172a;text-transform:capitalize;">{spec}</span>
            <span style="color:{rank_color};font-weight:700;font-size:.85rem;">
                {rank} ({count})</span>
          </div>
          <div style="background:#f1f5f9;border-radius:5px;height:6px;margin-top:.5rem;overflow:hidden;">
              <div style="background:{rank_color};width:{bar_w}%;height:100%;"></div>
          </div>
          <div style="font-size:.7rem;color:#64748b;margin-top:.3rem;">
            {f"{count} of {next_th} cases to next rank" if next_th else "Mastered"}
          </div>
        </div>
        """, unsafe_allow_html=True)


def _render_leaderboard_section() -> None:
    """Show anonymous weekly leaderboard."""
    client = _get_supabase_client()
    if not client:
        st.info("Leaderboard requires database connection.")
        return

    try:
        r = (client.table("user_stats")
             .select("display_name,total_xp,current_streak,show_on_leaderboard")
             .eq("show_on_leaderboard", True)
             .order("total_xp", desc=True)
             .limit(20)
             .execute())
        rows = r.data or []
    except Exception:
        rows = []

    if not rows:
        st.info("No leaderboard data yet. Be the first to make the top!")
        return

    me_id = _get_user_id()
    me_stats = _normalize_stats(get_user_stats(me_id))
    me_xp = me_stats.get("total_xp", 0)

    medals = ["#1", "#2", "#3"]
    for i, row in enumerate(rows[:20]):
        name = row.get("display_name") or f"Student #{i+1:03d}"
        xp_v = row.get("total_xp", 0)
        streak = row.get("current_streak", 0)
        is_me = (xp_v == me_xp and i == 0) or False  # rough heuristic
        bg = "#fef3c7" if is_me else "white"
        rank_disp = medals[i] if i < 3 else f"#{i+1}"
        st.markdown(f"""
        <div style="background:{bg};border:1.5px solid #e2e8f0;border-radius:8px;
                    padding:.6rem .9rem;margin-bottom:.4rem;display:flex;
                    justify-content:space-between;align-items:center;">
            <div style="display:flex;gap:.6rem;align-items:center;">
                <span style="font-size:1rem;font-weight:700;color:#3b82f6;">{rank_disp}</span>
                <span style="font-weight:600;color:#0f172a;">{name}</span>
            </div>
            <div style="display:flex;gap:1rem;align-items:center;font-size:.85rem;">
                <span style="color:#3b82f6;font-weight:700;">{xp_v:,} XP</span>
                <span style="color:#f59e0b;">{streak}d streak</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Opt-out toggle
    st.markdown("---")
    show_me = st.checkbox(
        "Show me on the leaderboard",
        value=me_stats.get("show_on_leaderboard", True),
        key="lb_opt_in",
    )
    if show_me != me_stats.get("show_on_leaderboard", True):
        me_stats["show_on_leaderboard"] = show_me
        _save_user_stats(me_stats)
        st.success("Leaderboard preference updated.")


def render_leaderboard() -> None:
    """Standalone leaderboard view (alias for use elsewhere)."""
    _render_leaderboard_section()


# ═══════════════════════════════════════════════════════════════════════════
# ASK MENTOR SYSTEM
# ═══════════════════════════════════════════════════════════════════════════
def _today_str() -> str:
    """Return today's date as YYYY-MM-DD (UTC)."""
    return datetime.now(timezone.utc).date().isoformat()


def get_mentor_questions_remaining() -> Optional[int]:
    """How many more mentor questions can the user ask today?

    Returns None if there is no limit (unlimited mode).
    """
    if DAILY_MENTOR_LIMIT is None:
        return None  # Unlimited

    user_id = _get_user_id()
    today = _today_str()
    # Try DB
    client = _get_supabase_client()
    if client:
        try:
            r = (client.table("mentor_questions")
                 .select("id")
                 .eq("user_id", user_id)
                 .eq("day", today)
                 .execute())
            used = len(r.data or [])
            return max(0, DAILY_MENTOR_LIMIT - used)
        except Exception:
            pass
    # Fall back to session
    cache_key = f"_mentor_q_{user_id}_{today}"
    used = st.session_state.get(cache_key, 0)
    return max(0, DAILY_MENTOR_LIMIT - used)


def _record_mentor_question(question_text: str, case_context: str) -> None:
    user_id = _get_user_id()
    today = _today_str()
    client = _get_supabase_client()
    if client:
        try:
            client.table("mentor_questions").insert({
                "user_id":       user_id,
                "day":           today,
                "question":      question_text[:2000],
                "case_context":  case_context[:2000],
                "created_at":    datetime.now(timezone.utc).isoformat(),
            }).execute()
            return
        except Exception:
            pass
    # Fall back to session counter
    cache_key = f"_mentor_q_{user_id}_{today}"
    st.session_state[cache_key] = st.session_state.get(cache_key, 0) + 1


def _build_mentor_message(question: str,
                           case_title: str = "",
                           student_name: str = "",
                           module: str = "") -> str:
    """Build a structured message that includes case context."""
    lines = [f"Hello {MENTOR_NAME},"]
    if student_name:
        lines.append(f"\nI'm {student_name}, a student using MLS Virtual Hospital.")
    else:
        lines.append("\nI'm a student using MLS Virtual Hospital.")
    if case_title or module:
        lines.append("")
        if case_title:
            lines.append(f"Case: {case_title}")
        if module:
            lines.append(f"Module: {module}")
    lines.append("")
    lines.append("My question:")
    lines.append(question)
    lines.append("")
    lines.append("Thank you for your time.")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# FLOATING HELP BUTTON — appears on every page
# ═══════════════════════════════════════════════════════════════════════════
def render_floating_help_button() -> None:
    """A floating "Ask Hiba" button that appears on every page.

    Call this once per page render (e.g., at the top of every page function,
    or in your main routing code right after the page is rendered).

    The button floats in the bottom-right corner. Clicking it opens WhatsApp
    in a new tab with a friendly pre-filled message.
    """
    if not MENTOR_WHATSAPP and not MENTOR_EMAIL:
        return  # No contact configured

    # Build a generic pre-filled message
    student_name = (st.session_state.get("user_name", "")
                    or st.session_state.get("display_name", "")
                    or "")

    # Try to get current page/module context
    current_page = st.session_state.get("page", "the platform")
    current_case = st.session_state.get("current_case_title", "")

    msg_lines = [f"Hello {MENTOR_NAME},"]
    if student_name:
        msg_lines.append(f"\nI'm {student_name}, using MLS Virtual Hospital.")
    else:
        msg_lines.append("\nI'm using MLS Virtual Hospital.")
    msg_lines.append(f"\nI was on the '{current_page}' page")
    if current_case:
        msg_lines.append(f" working on the case: {current_case}")
    msg_lines.append(" and I have a question:")
    msg_lines.append("\n[type your question here]")
    msg_lines.append("\nThank you for your time.")

    msg = "\n".join(msg_lines)
    encoded = quote(msg)

    # WhatsApp link (preferred) or email fallback
    if MENTOR_WHATSAPP:
        wa_num = MENTOR_WHATSAPP.lstrip("+").replace(" ", "").replace("-", "")
        link = f"https://wa.me/{wa_num}?text={encoded}"
        icon_color = "#25d366"
        tooltip = f"Ask {MENTOR_NAME} on WhatsApp"
    else:
        subject = quote(f"MLS Hospital question from a student")
        link = f"mailto:{MENTOR_EMAIL}?subject={subject}&body={encoded}"
        icon_color = "#3b82f6"
        tooltip = f"Email {MENTOR_NAME}"

    # Render floating button using a Streamlit components.html block
    # This stays anchored regardless of page scroll
    components.html(f"""
    <div id="mls-help-fab" style="
        position: fixed;
        bottom: 1.5rem;
        right: 1.5rem;
        z-index: 99999;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif;
    ">
      <a href="{link}" target="_blank" style="text-decoration:none;">
        <div style="
            background: {icon_color};
            color: white;
            padding: .85rem 1.2rem;
            border-radius: 999px;
            box-shadow: 0 6px 18px rgba(0,0,0,.25);
            display: flex;
            align-items: center;
            gap: .55rem;
            font-weight: 700;
            font-size: .92rem;
            cursor: pointer;
            transition: transform .15s ease, box-shadow .15s ease;
            white-space: nowrap;
        "
        onmouseover="this.style.transform='scale(1.05)';this.style.boxShadow='0 10px 24px rgba(0,0,0,.3)';"
        onmouseout="this.style.transform='scale(1)';this.style.boxShadow='0 6px 18px rgba(0,0,0,.25)';"
        title="{tooltip}">
            <span style="font-size:1.1rem;">?</span>
            <span>Ask {MENTOR_NAME}</span>
        </div>
      </a>
    </div>
    """, height=80)


def render_ask_mentor_button(*,
                              context_label: str = "this case",
                              case_title: str = "",
                              module: str = "",
                              variant: str = "compact") -> None:
    """Render an "Ask Mentor" button with proper limits and pre-fill.

    variant: 'compact' (small button) | 'card' (big card with explanation)
    """
    if not MENTOR_WHATSAPP and not MENTOR_EMAIL:
        return  # No contact configured

    remaining = get_mentor_questions_remaining()  # None = unlimited
    is_unlimited = (remaining is None)

    if variant == "card":
        if is_unlimited:
            limit_text = "Ask anytime — there's no limit on questions."
        else:
            limit_text = (f"Limited to {DAILY_MENTOR_LIMIT} questions per day — "
                          f"you have <b>{remaining}</b> remaining today.")
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#fef3c7,#fde68a);
                    border:2px solid #f59e0b;border-radius:14px;
                    padding:1.2rem 1.4rem;margin:1rem 0;">
          <div style="font-size:1.1rem;font-weight:800;color:#78350f;margin-bottom:.4rem;">
            Stuck on {context_label}?
          </div>
          <div style="font-size:.88rem;color:#78350f;line-height:1.5;">
            Ask {MENTOR_NAME} directly for help. Your message will include the case
            context automatically. {limit_text}
          </div>
        </div>
        """, unsafe_allow_html=True)

    if not is_unlimited and remaining <= 0:
        st.warning(
            f"You've used all {DAILY_MENTOR_LIMIT} mentor questions for today. "
            "Your limit resets at midnight (UTC). In the meantime, try the AI "
            "Tutor or DocCollab."
        )
        return

    # Toggle to expand
    expand_key = f"mentor_expand_{module}_{case_title}"
    if st.button(f"Ask {MENTOR_NAME} a question",
                 key=f"ask_mentor_btn_{module}_{case_title}",
                 use_container_width=True):
        st.session_state[expand_key] = not st.session_state.get(expand_key, False)

    if not st.session_state.get(expand_key, False):
        return

    with st.container():
        st.markdown(f"""
        <div style="background:#fff;border:1.5px solid #e2e8f0;border-radius:10px;
                    padding:1rem;margin-top:.6rem;">
        """, unsafe_allow_html=True)

        student_name = st.text_input(
            "Your name (so I can reply properly):",
            value=st.session_state.get("user_name", "") or
                  st.session_state.get("display_name", ""),
            key=f"mq_name_{module}",
        )

        question = st.text_area(
            "Your question:",
            placeholder="Be specific. What concept is unclear? What did you try?",
            height=120,
            key=f"mq_text_{module}",
        )

        char_count = len(question)
        if char_count < 30 and question:
            st.caption(f"Your question is {char_count} characters — try to be more specific (~30+).")

        # Build the message preview
        preview_msg = _build_mentor_message(
            question or "[your question here]",
            case_title=case_title,
            student_name=student_name or "",
            module=module,
        )

        with st.expander("Preview the message that will be sent"):
            st.code(preview_msg, language=None)

        col1, col2 = st.columns(2)
        ready = bool(question and len(question) >= 20 and student_name)

        with col1:
            if MENTOR_WHATSAPP:
                if ready:
                    wa_link = f"https://wa.me/{MENTOR_WHATSAPP.lstrip('+').replace(' ', '')}?text={quote(preview_msg)}"
                    st.markdown(f"""
                    <a href="{wa_link}" target="_blank" style="text-decoration:none;">
                      <div style="background:#25d366;color:white;padding:.7rem;
                                  border-radius:8px;text-align:center;font-weight:700;
                                  font-size:.95rem;cursor:pointer;">
                        Send via WhatsApp
                      </div>
                    </a>
                    """, unsafe_allow_html=True)
                else:
                    st.button("Send via WhatsApp", disabled=True,
                             use_container_width=True, key=f"wa_dis_{module}")

        with col2:
            if MENTOR_EMAIL:
                if ready:
                    subject = f"MLS Hospital question: {case_title or module or 'help'}"
                    em_link = f"mailto:{MENTOR_EMAIL}?subject={quote(subject)}&body={quote(preview_msg)}"
                    st.markdown(f"""
                    <a href="{em_link}" target="_blank" style="text-decoration:none;">
                      <div style="background:#3b82f6;color:white;padding:.7rem;
                                  border-radius:8px;text-align:center;font-weight:700;
                                  font-size:.95rem;cursor:pointer;">
                        Send via Email
                      </div>
                    </a>
                    """, unsafe_allow_html=True)
                else:
                    st.button("Send via Email", disabled=True,
                             use_container_width=True, key=f"em_dis_{module}")

        # Mark as sent button
        if ready:
            st.markdown(
                "<div style='font-size:.78rem;color:#64748b;margin-top:.6rem;'>"
                "After sending, please mark below to count this against your "
                "weekly limit:</div>", unsafe_allow_html=True)
            if st.button("I sent the question",
                         key=f"mq_sent_{module}",
                         use_container_width=True,
                         type="primary"):
                _record_mentor_question(question, f"{case_title} | {module}")
                if is_unlimited:
                    st.success(f"Recorded. Thanks for reaching out — {MENTOR_NAME} will reply soon.")
                else:
                    st.success(f"Recorded. You have {remaining - 1} questions remaining today.")
                st.session_state[expand_key] = False
                # Award some XP for asking thoughtful questions
                award_xp("ai_tutor_session", amount=10, toast=False)
                try:
                    st.rerun()
                except Exception:
                    pass

        st.markdown("</div>", unsafe_allow_html=True)


def render_ask_mentor_page() -> None:
    """Standalone Ask Mentor page for the sidebar."""
    st.markdown('<div class="section-header">Ask the Mentor</div>',
                unsafe_allow_html=True)

    if not MENTOR_WHATSAPP and not MENTOR_EMAIL:
        st.error(
            "Mentor contact has not been configured. Add `MENTOR_WHATSAPP` "
            "and/or `MENTOR_EMAIL` to your secrets.toml."
        )
        return

    remaining = get_mentor_questions_remaining()
    is_unlimited = (remaining is None)

    if is_unlimited:
        limit_block = """
        <div style="margin-top:1rem;background:rgba(255,255,255,.15);
                    padding:.6rem .9rem;border-radius:8px;display:inline-block;">
            <span style="font-size:.85rem;">Free for everyone — </span>
            <b style="font-size:1rem;color:#fbbf24;">No limit on questions</b>
        </div>
        """
    else:
        limit_block = f"""
        <div style="margin-top:1rem;background:rgba(255,255,255,.15);
                    padding:.6rem .9rem;border-radius:8px;display:inline-block;">
            <span style="font-size:.85rem;">Questions remaining today:</span>
            <b style="font-size:1.2rem;margin-left:.4rem;color:#fbbf24;">
                {remaining} / {DAILY_MENTOR_LIMIT}
            </b>
        </div>
        """

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0a2540,#1a4f8a);color:white;
                border-radius:14px;padding:1.5rem 1.8rem;margin-bottom:1.2rem;">
        <div style="font-size:1.4rem;font-weight:800;margin-bottom:.4rem;">
            Direct Access to Your Mentor
        </div>
        <div style="font-size:.95rem;opacity:.9;line-height:1.5;">
            If you're stuck on a concept after trying the AI Tutor and DocCollab,
            you can reach {MENTOR_NAME} directly. Your message will include the
            current case context automatically.
        </div>
        {limit_block}
    </div>
    """, unsafe_allow_html=True)

    # Tips before asking
    st.markdown("### Before you ask...")
    tips = [
        "**Try the AI Tutor first** — it can often help with concept questions.",
        "**Search DocCollab** — real PubMed cases may answer your question.",
        "**Be specific** — 'I'm confused about cardiac vs respiratory dyspnea' is "
        "much better than 'help me with breathing'.",
        "**Show your reasoning** — what do you currently think the answer is, "
        "and why? This helps me see where you're getting stuck.",
    ]
    for t in tips:
        st.markdown(f"- {t}")

    st.markdown("---")
    st.markdown("### Ask your question")

    # Reuse the button logic
    render_ask_mentor_button(
        context_label="a clinical concept",
        case_title=st.session_state.get("current_case_title", ""),
        module="general",
        variant="card",
    )


# ═══════════════════════════════════════════════════════════════════════════
# DAILY-LOGIN HOOK — call this once at the start of every session
# ═══════════════════════════════════════════════════════════════════════════
def init_session() -> None:
    """Run at app start. Updates daily streak and awards login XP."""
    if st.session_state.get("_tier1_initialized"):
        return
    try:
        streak, xp = update_login_streak()
        if xp > 0:
            try:
                msg = f"Daily login bonus: +{xp} XP"
                if streak in (3, 7, 30):
                    msg += f" (Day {streak} streak!)"
                st.toast(msg, icon="*")
            except Exception:
                pass
    except Exception:
        pass
    st.session_state["_tier1_initialized"] = True


# ═══════════════════════════════════════════════════════════════════════════
# REQUIRED SUPABASE TABLES (run once in SQL editor)
# ═══════════════════════════════════════════════════════════════════════════
SUPABASE_SCHEMA = """
-- Tier 1 Features Tables
-- Run this once in your Supabase SQL editor

create table if not exists user_stats (
    user_id              text primary key,
    total_xp             integer default 0,
    current_streak       integer default 0,
    longest_streak       integer default 0,
    last_login           date,
    diagnoses_submitted  integer default 0,
    diagnoses_correct    integer default 0,
    osce_high_count      integer default 0,
    notes_count          integer default 0,
    flashcards_reviewed  integer default 0,
    peer_sessions        integer default 0,
    specialty_counts     text default '{}',
    earned_badges        text default '[]',
    show_on_leaderboard  boolean default true,
    display_name         text default '',
    updated_at           timestamptz default now()
);

create table if not exists mentor_questions (
    id           bigserial primary key,
    user_id      text not null,
    day          text not null,
    question     text,
    case_context text,
    created_at   timestamptz default now()
);

create index if not exists idx_user_stats_xp on user_stats(total_xp desc);
create index if not exists idx_mentor_questions_user_day
    on mentor_questions(user_id, day);

alter table user_stats enable row level security;
alter table mentor_questions enable row level security;

create policy "Allow all user_stats" on user_stats for all using (true) with check (true);
create policy "Allow all mentor_questions" on mentor_questions for all using (true) with check (true);
"""

# Print schema if run directly
if __name__ == "__main__":
    print("MLS Virtual Hospital — Tier 1 Features Module")
    print("=" * 60)
    print("\nThis is a library module. Import functions from it in app.py.\n")
    print("REQUIRED SUPABASE SCHEMA:")
    print(SUPABASE_SCHEMA)
