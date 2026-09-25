"""
medsim_shared_state.py
────────────────────────────────────────────────────────────────────────────
Shared, cross-device room state for the Multi-Patient Caseload / pager
system. Fixes the architecture gap where DeteriorationEngine state lived
only in each browser's private st.session_state, so one user's admitted
patients were invisible to everyone else.

Design: DeteriorationEngine.tick() is stateful (random jitter + one-time
phase deltas accumulate per call, not a pure function of elapsed time), so
it is NOT safe to have every viewer's browser independently call tick() on
the same room — they'd each compute a different, drifting result. Instead:

  - Exactly ONE session (the admin/instructor running the board) actually
    calls engine.tick() and pushes the resulting state dict here after
    every tick — that's the single source of truth.
  - Every other viewer (students) never runs the engine at all for shared
    rooms. They just poll pull_active_rooms() and render what they get.
  - Each viewer keeps its own small local cache (in st.session_state) of
    "what did I last see" purely to detect *new* patients or *worsened*
    status, so it knows when to fire its own local pager notification.
    That comparison is local and harmless to keep per-session; the patient
    data itself is not.

Requires one new Supabase table:

    create table vh_active_patients (
      id            bigint generated always as identity primary key,
      room_id         text unique not null,
      bed_label         text,
      case_name           text,
      status                text,
      rhythm                  text,
      vitals                    jsonb,
      current_message             text,
      elapsed_seconds               integer,
      admitted_by                     text,
      active                             boolean default true,
      updated_at                          timestamp default now()
    );
"""

import requests
import streamlit as st

TABLE = "vh_active_patients"


def _sb_creds():
    return st.secrets.get("SUPABASE_URL", ""), st.secrets.get("SUPABASE_KEY", "")


def _sb_available() -> bool:
    url, key = _sb_creds()
    return bool(url and key and not url.startswith("YOUR_"))


def _sb_headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation"}


def push_room_state(room_id: str, bed_label: str, case_name: str, state: dict, admitted_by: str) -> bool:
    """Called ONLY by the authoritative ticking session, after each tick()."""
    if not _sb_available():
        return False
    url, key = _sb_creds()
    row = {
        "room_id": room_id, "bed_label": bed_label, "case_name": case_name,
        "status": state.get("status", "stable"), "rhythm": state.get("rhythm", ""),
        "vitals": state.get("vitals", {}), "current_message": state.get("current_message", ""),
        "elapsed_seconds": state.get("elapsed", 0), "admitted_by": admitted_by, "active": True,
    }
    try:
        r = requests.post(f"{url}/rest/v1/{TABLE}",
                           headers={**_sb_headers(key), "Prefer": "resolution=merge-duplicates,return=representation"},
                           json=row, timeout=8)
        return r.status_code in (200, 201)
    except Exception:
        return False


def pull_active_rooms() -> list:
    """Called by every viewer (admin and students alike) to render the board."""
    if not _sb_available():
        return []
    url, key = _sb_creds()
    try:
        r = requests.get(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key),
                          params={"select": "*", "active": "eq.true", "order": "updated_at.desc"}, timeout=8)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def discharge_room(room_id: str) -> bool:
    if not _sb_available():
        return False
    url, key = _sb_creds()
    try:
        r = requests.patch(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key),
                            params={"room_id": f"eq.{room_id}"}, json={"active": False}, timeout=8)
        return r.status_code in (200, 204)
    except Exception:
        return False
