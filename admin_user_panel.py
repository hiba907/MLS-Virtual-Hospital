"""
═══════════════════════════════════════════════════════════════════════════
  MLS Virtual Hospital — Admin User Panel + Email Notifications
  ─────────────────────────────────────────────────────────────────────────
  Faculty-only tool for:
    • Viewing all registered users (name, email, role, registration date)
    • Filtering and searching the user list
    • Exporting user list as CSV
    • Sending broadcast email notifications (e.g., new case uploaded)
    • Tracking notification history

  WORKFLOW:
  ─────────
  Admin opens "User Management" → sees all users from vh_users table
   ↓
  Admin clicks "📧 Send Broadcast" → composes notification → sends to all
   ↓
  Email log saved to email_notifications table for audit trail

  AUTHOR: Hiba Hamdar — Academy of Medical Learning Skills
  COPYRIGHT (c) 2026 — All Rights Reserved
═══════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import streamlit as st
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import uuid
import smtplib
import ssl
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import io
import csv


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def _safe_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def _supabase_url() -> str:
    return _safe_secret("SUPABASE_URL", "").rstrip("/")


def _supabase_key() -> str:
    return _safe_secret("SUPABASE_KEY", "")


def _sb_headers() -> dict:
    key = _supabase_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _sb_available() -> bool:
    return bool(_supabase_url() and _supabase_key())


def _is_admin() -> bool:
    auth = st.session_state.get("auth_user", {}) or {}
    role = (auth.get("role") or "").lower()
    if role in ("admin", "faculty"):
        return True
    admin_email = _safe_secret("ADMIN_EMAIL", "hamdarhiba95@gmail.com").strip().lower()
    user_email = (auth.get("email") or "").strip().lower()
    return bool(user_email and admin_email and user_email == admin_email)


def _admin_name() -> str:
    auth = st.session_state.get("auth_user", {}) or {}
    return auth.get("name") or auth.get("email") or "admin"


# ═══════════════════════════════════════════════════════════════════════════
# USER LIST FETCH
# ═══════════════════════════════════════════════════════════════════════════
def fetch_all_users() -> List[Dict[str, Any]]:
    """Get all users from vh_users table."""
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/vh_users"
    params = {
        "select": "id,email,name,role,specialty,hospital,is_verified,created_at",
        "order":  "created_at.desc",
        "limit":  "1000",
    }
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=10)
        if r.status_code == 200:
            return r.json() or []
    except Exception as e:
        print(f"[user_panel] fetch error: {e}")
    return []


def filter_users(users: List[Dict[str, Any]],
                  search: str = "",
                  role_filter: str = "all",
                  verified_only: bool = False
                  ) -> List[Dict[str, Any]]:
    """Filter users by search term, role, and verified status."""
    out = users
    if search and search.strip():
        s = search.strip().lower()
        out = [u for u in out
                if s in (u.get("name", "") or "").lower()
                or s in (u.get("email", "") or "").lower()]
    if role_filter and role_filter != "all":
        out = [u for u in out
                if (u.get("role", "") or "").lower() == role_filter.lower()]
    if verified_only:
        out = [u for u in out if u.get("is_verified", True)]
    return out


# ═══════════════════════════════════════════════════════════════════════════
# EMAIL SENDING
# ═══════════════════════════════════════════════════════════════════════════
def _get_email_credentials() -> tuple:
    """Returns (from_email, app_password) tuple — or (None, None) if not configured."""
    from_email = _safe_secret("NOTIFY_EMAIL", "")
    password   = _safe_secret("NOTIFY_EMAIL_PASSWORD", "")
    if not from_email or not password:
        return None, None
    return from_email, password


def _send_one_email(to_email: str, subject: str, html_body: str,
                     text_body: str = "") -> bool:
    """Send a single email. Returns True if successful."""
    from_email, password = _get_email_credentials()
    if not from_email or not password:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"MLS Virtual Hospital <{from_email}>"
        msg["To"]   = to_email
        msg["Subject"] = subject

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=15) as server:
            server.login(from_email, password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[email] send error to {to_email}: {e}")
        return False


def _build_html_email(title: str, body: str, call_to_action_label: str = "",
                       call_to_action_url: str = "") -> str:
    """Build a nicely formatted HTML email."""
    cta_html = ""
    if call_to_action_label and call_to_action_url:
        cta_html = f"""
        <div style="text-align:center;margin:24px 0;">
          <a href="{call_to_action_url}"
             style="background:#0e7490;color:white;padding:12px 28px;
                    border-radius:8px;text-decoration:none;font-weight:700;
                    font-size:15px;display:inline-block;">
            {call_to_action_label}
          </a>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
          background:#f1f5f9;margin:0;padding:0; }}
  .container {{ max-width:600px;margin:0 auto;background:white;
                border-radius:12px;overflow:hidden;
                box-shadow:0 4px 14px rgba(0,0,0,.06); }}
  .header {{ background:linear-gradient(135deg,#0a2540,#0e7490);
             color:white;padding:24px 28px; }}
  .header h1 {{ margin:0;font-size:24px;font-weight:800; }}
  .header p {{ margin:6px 0 0 0;font-size:13px;opacity:.85; }}
  .body {{ padding:28px;color:#1e293b;line-height:1.6;font-size:15px; }}
  .footer {{ background:#f8fafc;padding:18px 28px;color:#64748b;
             font-size:12px;border-top:1px solid #e2e8f0; }}
  .footer a {{ color:#0e7490;text-decoration:none; }}
</style>
</head>
<body>
  <div style="padding:24px 12px;">
    <div class="container">
      <div class="header">
        <h1>🏥 MLS Virtual Hospital</h1>
        <p>An AI-augmented clinical training platform</p>
      </div>
      <div class="body">
        <h2 style="margin-top:0;color:#0a2540;">{title}</h2>
        {body}
        {cta_html}
      </div>
      <div class="footer">
        <p style="margin:0 0 6px 0;">
          You're receiving this because you have a registered account at
          MLS Virtual Hospital.
        </p>
        <p style="margin:0;">
          Built by Hiba Hamdar · Academy of Medical Learning Skills ·
          Educational use only. Not for clinical decision-making.
        </p>
      </div>
    </div>
  </div>
</body>
</html>"""


def send_broadcast_email(recipients: List[str], subject: str,
                          title: str, body_html: str,
                          cta_label: str = "", cta_url: str = "",
                          delay_per_email: float = 0.5
                          ) -> Dict[str, Any]:
    """
    Send an email to a list of recipients. Returns a summary dict.
    delay_per_email: seconds between sends to avoid Gmail throttling.
    """
    from_email, password = _get_email_credentials()
    if not from_email or not password:
        return {"success": 0, "failed": len(recipients),
                "error": "NOTIFY_EMAIL or NOTIFY_EMAIL_PASSWORD missing in secrets"}

    html_email = _build_html_email(title, body_html, cta_label, cta_url)

    success = 0
    failed = 0
    failed_emails = []

    for i, to_email in enumerate(recipients):
        if not to_email or "@" not in to_email:
            failed += 1
            continue
        if _send_one_email(to_email, subject, html_email):
            success += 1
        else:
            failed += 1
            failed_emails.append(to_email)
        # Throttle to avoid Gmail rate limits (~100 emails/day for free Gmail)
        if i < len(recipients) - 1:
            time.sleep(delay_per_email)

    return {
        "success":       success,
        "failed":        failed,
        "failed_emails": failed_emails,
        "total":         len(recipients),
    }


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATION LOG
# ═══════════════════════════════════════════════════════════════════════════
def log_notification(rec: Dict[str, Any]) -> bool:
    if not _sb_available():
        return False
    url = f"{_supabase_url()}/rest/v1/email_notifications"
    try:
        r = requests.post(url, headers=_sb_headers(), json=rec, timeout=10)
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[user_panel] log_notification error: {e}")
        return False


def list_notification_history() -> List[Dict[str, Any]]:
    if not _sb_available():
        return []
    url = f"{_supabase_url()}/rest/v1/email_notifications"
    params = {"select": "*", "order": "sent_at.desc", "limit": "50"}
    try:
        r = requests.get(url, headers=_sb_headers(), params=params, timeout=8)
        if r.status_code == 200:
            return r.json() or []
    except Exception:
        pass
    return []


# ═══════════════════════════════════════════════════════════════════════════
# UI: MAIN PANEL
# ═══════════════════════════════════════════════════════════════════════════
def render_user_management_panel() -> None:
    if not _is_admin():
        st.error("This page is for admins only.")
        return

    st.markdown(
        '<div class="section-header">👥 User Management</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div style="background:linear-gradient(135deg,#0a2540,#0e7490);color:white;
                border-radius:14px;padding:1.4rem 1.6rem;margin-bottom:1rem;">
      <div style="font-size:1.3rem;font-weight:800;margin-bottom:.4rem;">
        Manage Registered Users & Send Notifications
      </div>
      <div style="font-size:.92rem;opacity:.92;line-height:1.5;">
        View all registered users, export their list, and send broadcast
        emails (e.g., when you upload new cases). Includes notification history.
      </div>
    </div>
    """, unsafe_allow_html=True)

    users = fetch_all_users()
    history = list_notification_history()

    tabs = st.tabs([
        f"👥 All Users ({len(users)})",
        "📧 Send Broadcast",
        f"📋 Notification History ({len(history)})",
    ])

    with tabs[0]:
        _tab_user_list(users)
    with tabs[1]:
        _tab_send_broadcast(users)
    with tabs[2]:
        _tab_notification_history(history)


# ───────────────────────────────────────────────────────────────────────────
# TAB 1: User list
# ───────────────────────────────────────────────────────────────────────────
def _tab_user_list(users: List[Dict[str, Any]]) -> None:
    if not users:
        st.warning(
            "Could not fetch users. Either the database is unreachable or "
            "the `vh_users` table is empty."
        )
        return

    # Filters
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        search = st.text_input(
            "🔎 Search by name or email:",
            placeholder="e.g., 'ahmad' or 'gmail.com'",
            key="user_list_search",
        )
    with c2:
        roles_present = sorted(set(
            (u.get("role", "") or "student").lower() for u in users
        ))
        role_options = ["all"] + roles_present
        role_filter = st.selectbox("Role:", role_options, key="user_role_filter")
    with c3:
        st.write("")
        st.write("")
        verified_only = st.checkbox("Verified only", key="user_verified_only")

    filtered = filter_users(users, search, role_filter, verified_only)

    # Summary stats
    n_total = len(users)
    n_filtered = len(filtered)
    role_counts = {}
    for u in users:
        r = (u.get("role", "") or "student").lower()
        role_counts[r] = role_counts.get(r, 0) + 1

    cs1, cs2, cs3, cs4 = st.columns(4)
    with cs1:
        st.metric("Total users", n_total)
    with cs2:
        st.metric("Showing", n_filtered)
    with cs3:
        st.metric("Students", role_counts.get("student", 0))
    with cs4:
        n_others = sum(v for k, v in role_counts.items() if k != "student")
        st.metric("Others", n_others)

    # Export button
    if filtered:
        csv_data = _users_to_csv(filtered)
        st.download_button(
            label=f"📥 Export {len(filtered)} users as CSV",
            data=csv_data,
            file_name=f"mls_users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if not filtered:
        st.info("No users match these filters.")
        return

    # Display table
    st.markdown(f"**Showing {len(filtered)} user{'s' if len(filtered)!=1 else ''}**")

    # Use a clean table display
    table_data = []
    for u in filtered:
        created_at = (u.get("created_at") or "")[:10]
        verified = "✓" if u.get("is_verified", True) else "✗"
        table_data.append({
            "Name":         u.get("name", "—") or "—",
            "Email":        u.get("email", "—") or "—",
            "Role":         (u.get("role", "") or "student").capitalize(),
            "Specialty":    u.get("specialty", "") or "—",
            "Hospital":     u.get("hospital", "") or "—",
            "Verified":     verified,
            "Registered":   created_at or "—",
        })

    st.dataframe(table_data, use_container_width=True, hide_index=True)


def _users_to_csv(users: List[Dict[str, Any]]) -> str:
    """Convert user list to CSV string."""
    output = io.StringIO()
    fieldnames = ["name", "email", "role", "specialty", "hospital",
                   "is_verified", "created_at"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for u in users:
        writer.writerow({
            "name":        u.get("name", ""),
            "email":       u.get("email", ""),
            "role":        u.get("role", ""),
            "specialty":   u.get("specialty", ""),
            "hospital":    u.get("hospital", ""),
            "is_verified": u.get("is_verified", True),
            "created_at":  u.get("created_at", ""),
        })
    return output.getvalue()


# ───────────────────────────────────────────────────────────────────────────
# TAB 2: Send broadcast
# ───────────────────────────────────────────────────────────────────────────
def _tab_send_broadcast(users: List[Dict[str, Any]]) -> None:
    # Check email config
    from_email, password = _get_email_credentials()
    if not from_email or not password:
        st.error(
            "⚠️ Email is not configured. Add `NOTIFY_EMAIL` and "
            "`NOTIFY_EMAIL_PASSWORD` to your Streamlit Cloud secrets first."
        )
        st.info(
            "Setup: Use a Gmail account, enable 2FA, generate an App Password "
            "at https://myaccount.google.com/apppasswords, and paste both "
            "values into your Streamlit Cloud secrets."
        )
        return

    st.markdown("**Compose a broadcast email to send to all registered users.**")
    st.caption(
        "💡 Use this when you upload new cases, add new features, or have "
        "important announcements for your students."
    )

    # Filter who to send to
    st.markdown("### 🎯 Recipients")
    cf1, cf2 = st.columns(2)
    with cf1:
        role_select = st.multiselect(
            "Send to which roles:",
            options=["student", "resident", "senior", "faculty", "admin"],
            default=["student", "resident"],
            key="bc_roles",
        )
    with cf2:
        only_verified = st.checkbox("Only verified users", value=False, key="bc_verified")

    # Filter recipients
    recipients = []
    for u in users:
        role = (u.get("role", "") or "student").lower()
        if role not in role_select:
            continue
        if only_verified and not u.get("is_verified", True):
            continue
        email = u.get("email", "").strip()
        if email and "@" in email:
            recipients.append(email)

    st.info(f"📬 This will send to **{len(recipients)} user{'s' if len(recipients)!=1 else ''}**")

    if len(recipients) > 100:
        st.warning(
            f"⚠️ Sending to {len(recipients)} users will take ~{len(recipients)//2} seconds "
            f"due to Gmail rate limits. Free Gmail accounts can send ~100-500 "
            f"emails/day max."
        )

    st.markdown("---")
    st.markdown("### ✉️ Compose your message")

    # Quick template buttons
    cq1, cq2, cq3 = st.columns(3)
    with cq1:
        if st.button("📋 New Case template", use_container_width=True):
            st.session_state["bc_subject"] = "🆕 New clinical case available on MLS Virtual Hospital"
            st.session_state["bc_title"] = "A new case has been added!"
            st.session_state["bc_body"] = (
                "Hi {{name}},\n\n"
                "I just published a new clinical case on MLS Virtual Hospital. "
                "Come practice your clinical reasoning skills!\n\n"
                "Case topic: [describe the case briefly]\n\n"
                "Log in to your account and head to the Case Library to find it."
            )
            st.session_state["bc_cta_label"] = "Open MLS Virtual Hospital →"
            st.session_state["bc_cta_url"] = "https://mls-virtual-hospital.streamlit.app"
            st.rerun()
    with cq2:
        if st.button("🩻 New Image template", use_container_width=True):
            st.session_state["bc_subject"] = "🩻 New medical image added to practice library"
            st.session_state["bc_title"] = "Test your imaging interpretation skills"
            st.session_state["bc_body"] = (
                "Hi {{name}},\n\n"
                "A new medical image has been added to the Image Practice library. "
                "Open the platform to test your radiology skills.\n\n"
                "Topic: [describe briefly]"
            )
            st.session_state["bc_cta_label"] = "Practice Now →"
            st.session_state["bc_cta_url"] = "https://mls-virtual-hospital.streamlit.app"
            st.rerun()
    with cq3:
        if st.button("📣 Announcement template", use_container_width=True):
            st.session_state["bc_subject"] = "📣 Platform Update — MLS Virtual Hospital"
            st.session_state["bc_title"] = "We have updates for you"
            st.session_state["bc_body"] = (
                "Hi {{name}},\n\n"
                "Here's what's new on MLS Virtual Hospital:\n\n"
                "• [Feature 1]\n"
                "• [Feature 2]\n"
                "• [Feature 3]\n\n"
                "Log in to check it out."
            )
            st.session_state["bc_cta_label"] = "Visit Platform →"
            st.session_state["bc_cta_url"] = "https://mls-virtual-hospital.streamlit.app"
            st.rerun()

    with st.form("broadcast_form"):
        subject = st.text_input(
            "Email subject line:",
            value=st.session_state.get("bc_subject", ""),
            placeholder="e.g., 'New case available on MLS Virtual Hospital'",
        )
        title = st.text_input(
            "Email body heading:",
            value=st.session_state.get("bc_title", ""),
            placeholder="e.g., 'New case posted today'",
        )
        body = st.text_area(
            "Email body (plain text — paragraphs will be auto-formatted):",
            value=st.session_state.get("bc_body", ""),
            height=180,
            placeholder=(
                "Write your message here. Tip: use {{name}} as a placeholder "
                "if you want to personalize, but currently broadcasts use a "
                "generic 'Hi there!' greeting."
            ),
        )
        col_cta1, col_cta2 = st.columns(2)
        with col_cta1:
            cta_label = st.text_input(
                "Call-to-action button text (optional):",
                value=st.session_state.get("bc_cta_label", "Open MLS Virtual Hospital →"),
            )
        with col_cta2:
            cta_url = st.text_input(
                "Call-to-action URL (optional):",
                value=st.session_state.get("bc_cta_url", "https://mls-virtual-hospital.streamlit.app"),
            )

        confirm = st.checkbox(
            f"✅ I confirm I want to send this to {len(recipients)} users",
            key="bc_confirm",
        )

        send_btn = st.form_submit_button(
            "📤 Send Broadcast",
            type="primary",
            use_container_width=True,
            disabled=(len(recipients) == 0),
        )

        if send_btn:
            if not confirm:
                st.error("Please confirm by checking the box above.")
                return
            if not subject.strip() or not body.strip():
                st.error("Subject and body are required.")
                return

            # Format body as HTML
            body_html = body.strip().replace("\n\n", "</p><p style='margin:0 0 14px 0;'>")
            body_html = body_html.replace("\n", "<br>")
            # Replace {{name}} placeholder with generic greeting
            body_html = body_html.replace("{{name}}", "there")
            body_html = f"<p style='margin:0 0 14px 0;'>{body_html}</p>"

            with st.spinner(f"Sending {len(recipients)} emails... (~{len(recipients)//2} sec)"):
                result = send_broadcast_email(
                    recipients=recipients,
                    subject=subject.strip(),
                    title=title.strip() or subject.strip(),
                    body_html=body_html,
                    cta_label=cta_label.strip(),
                    cta_url=cta_url.strip(),
                )

            if result.get("error"):
                st.error(f"❌ {result['error']}")
                return

            # Log to history
            log_notification({
                "notification_id": "notif_" + uuid.uuid4().hex[:12],
                "subject":         subject.strip(),
                "body_preview":    body.strip()[:500],
                "sent_by":         _admin_name(),
                "n_recipients":    result["total"],
                "n_success":       result["success"],
                "n_failed":        result["failed"],
                "sent_at":         datetime.now(timezone.utc).isoformat(),
            })

            st.success(
                f"✅ Sent **{result['success']}** emails successfully. "
                f"{result['failed']} failed."
            )
            if result["failed"] > 0 and result.get("failed_emails"):
                with st.expander(f"Failed recipients ({result['failed']})", expanded=False):
                    for em in result["failed_emails"][:20]:
                        st.code(em)
                    if len(result["failed_emails"]) > 20:
                        st.caption(f"... and {len(result['failed_emails']) - 20} more")
            # Clear form state
            for key in ["bc_subject", "bc_title", "bc_body", "bc_cta_label",
                         "bc_cta_url", "bc_confirm"]:
                if key in st.session_state:
                    del st.session_state[key]


# ───────────────────────────────────────────────────────────────────────────
# TAB 3: Notification history
# ───────────────────────────────────────────────────────────────────────────
def _tab_notification_history(history: List[Dict[str, Any]]) -> None:
    if not history:
        st.info("No notifications sent yet. Use the **📧 Send Broadcast** tab to send your first.")
        return

    st.markdown(f"**{len(history)} broadcast{'s' if len(history)!=1 else ''} sent (showing latest 50)**")

    for notif in history:
        sent_at = (notif.get("sent_at") or "")[:16].replace("T", " ")
        subject = notif.get("subject", "(no subject)")
        n_success = notif.get("n_success", 0)
        n_failed = notif.get("n_failed", 0)
        sent_by = notif.get("sent_by", "?")

        with st.expander(
            f"📧 {sent_at} · {subject} ({n_success}/{n_success+n_failed} sent)",
            expanded=False
        ):
            st.markdown(f"**Sent by:** {sent_by}")
            st.markdown(f"**Total recipients:** {notif.get('n_recipients', 0)}")
            st.markdown(f"**Successful:** {n_success}")
            st.markdown(f"**Failed:** {n_failed}")
            st.markdown("**Preview of body:**")
            st.code(notif.get("body_preview", ""), language=None)


# ═══════════════════════════════════════════════════════════════════════════
# SUPABASE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════
USER_PANEL_SCHEMA = """
-- ─────────────────────────────────────────────────────────────────────
-- Email notification history — audit trail for broadcasts
-- ─────────────────────────────────────────────────────────────────────

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
"""


if __name__ == "__main__":
    print("MLS Virtual Hospital — Admin User Panel + Email Notifications")
    print("=" * 60)
    print(USER_PANEL_SCHEMA)
