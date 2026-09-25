"""
medsim_pager.py
────────────────────────────────────────────────────────────────────────────
The "virtual pager" — Tier 1 (simple): browser Notification API alerts that
fire while the fellow has the tab open. Free, no external service, no
service worker.

(Tier 2 — alerts that reach a closed browser/phone screen — needs a service
worker + VAPID keys + a small push-subscription table in Supabase. That's a
bigger, separate build; this file is deliberately scoped to Tier 1 so it
ships today. See the bottom of this file for what Tier 2 would add.)

Usage from medsim_multipatient.py (or any page):

    from medsim_pager import request_pager_permission, fire_pager_alert

    request_pager_permission()          # call once near the top of the page
    ...
    if new_patient_arrived:
        fire_pager_alert(
            title="🔴 New Critical Patient",
            body="Bed 3 — chest pain, STEMI protocol",
            urgency="critical",
        )
"""

import streamlit.components.v1 as components


def request_pager_permission(height: int = 60):
    """Ask the browser for notification permission. Safe to call every
    rerun — the browser only prompts once per site until permission
    changes. Shows a small status line."""
    html = """
    <div id="pager-status" style="font-family:'Segoe UI',sans-serif;font-size:12px;
         color:#9091a4;padding:4px 0;"></div>
    <script>
      const statusEl = document.getElementById('pager-status');
      function updateStatus() {
        const p = Notification.permission;
        statusEl.textContent = p === 'granted' ? '🔔 Pager alerts enabled'
                              : p === 'denied'  ? '🔕 Pager alerts blocked in browser settings'
                              : '🔔 Enable pager alerts for this tab';
      }
      if (!('Notification' in window)) {
        statusEl.textContent = 'Notifications not supported in this browser.';
      } else if (Notification.permission === 'default') {
        Notification.requestPermission().then(updateStatus);
      } else {
        updateStatus();
      }
    </script>
    """
    components.html(html, height=height)


def fire_pager_alert(title: str, body: str, urgency: str = "routine", height: int = 1):
    """Fire one browser notification immediately. urgency: 'routine' |
    'urgent' | 'critical' — only affects the icon/tag, not delivery.
    Call this once per new event (e.g. right after a new patient is added
    to the board) — calling it every rerun will re-fire it every rerun, so
    gate it with a session_state flag at the call site."""
    icon = {"routine": "🟢", "urgent": "🟠", "critical": "🔴"}.get(urgency, "🔔")
    safe_title = title.replace("`", "'").replace("\\", "")
    safe_body = body.replace("`", "'").replace("\\", "")
    html = f"""
    <script>
      if ('Notification' in window && Notification.permission === 'granted') {{
        try {{
          new Notification(`{icon} {safe_title}`, {{
            body: `{safe_body}`,
            tag: 'medsim-pager-' + Date.now(),
          }});
        }} catch(e) {{ console.warn('Pager notification failed:', e); }}
      }}
      // Audible chime, independent of notification permission
      try {{
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.type = 'sine'; o.frequency.value = {800 if urgency == "critical" else 600};
        o.connect(g); g.connect(ctx.destination);
        g.gain.setValueAtTime(0.001, ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + 0.02);
        g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
        o.start(); o.stop(ctx.currentTime + 0.4);
      }} catch(e) {{}}
    </script>
    """
    components.html(html, height=height)


# ── Tier 2 scope note (not built here) ──────────────────────────────────────
# To reach a fellow with the tab/browser fully closed, you'd add:
#   1. A service worker (sw.js) registered on the page, handling 'push' events
#      and showing a notification even when no tab is open.
#   2. VAPID keys (free, self-generated with `pywebpush` or `web-push` CLI —
#      no paid service required) identifying your server to push providers.
#   3. A `vh_push_subscriptions` Supabase table storing each fellow's
#      PushSubscription object (created client-side via
#      `registration.pushManager.subscribe()`).
#   4. A small server-side sender (Python `pywebpush` library) that reads
#      subscriptions from Supabase and POSTs the push payload whenever a
#      new patient event fires — this needs to run as a background process
#      or scheduled job, since Streamlit itself only executes while a page
#      is being viewed, it can't independently push in the background.
# Still $0 in service fees either way — the added cost is entirely your own
# build time, plus needing *something* (a small cron job / server) running
# independently of Streamlit to dispatch pushes when fellows aren't on the page.
