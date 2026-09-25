"""
ashm_case_combo.py
────────────────────────────────────────────────────────────────────────────
Admin/faculty-only: bundle several cases into a named "combo" (e.g. "Monday
AM Surge") and release them all onto the Multi-Patient board simultaneously
— this is the actual "five cases from different departments arriving
together" mechanic the proposal describes, which a one-at-a-time admission
dropdown doesn't provide.

Requires one new Supabase table:

    create table vh_case_combos (
      id           bigint generated always as identity primary key,
      combo_id       text unique not null,
      name             text not null,
      case_ids           jsonb not null,
      urgency_note         text,
      created_by             text,
      created_at              timestamp default now()
    );
"""

import time
import requests
import streamlit as st

TABLE = "vh_case_combos"


def _sb_creds():
    return st.secrets.get("SUPABASE_URL", ""), st.secrets.get("SUPABASE_KEY", "")


def _sb_available() -> bool:
    url, key = _sb_creds()
    return bool(url and key and not url.startswith("YOUR_"))


def _sb_headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation"}


def save_combo(row: dict) -> tuple:
    if not _sb_available():
        return False, "Supabase not configured."
    url, key = _sb_creds()
    try:
        r = requests.post(f"{url}/rest/v1/{TABLE}",
                           headers={**_sb_headers(key), "Prefer": "resolution=merge-duplicates,return=representation"},
                           json=row, timeout=10)
        return (True, "Saved.") if r.status_code in (200, 201) else (False, f"Failed: {r.text[:200]}")
    except Exception as e:
        return False, f"Failed: {e}"


def list_combos() -> list:
    if not _sb_available():
        return []
    url, key = _sb_creds()
    try:
        r = requests.get(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key),
                          params={"select": "*", "order": "created_at.desc"}, timeout=10)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def delete_combo(combo_id: str) -> bool:
    if not _sb_available():
        return False
    url, key = _sb_creds()
    try:
        r = requests.delete(f"{url}/rest/v1/{TABLE}", headers=_sb_headers(key),
                             params={"combo_id": f"eq.{combo_id}"}, timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False


def render_combo_builder(all_case_ids: list, fmt_fn):
    """Admin/faculty UI: build + save a combo. `all_case_ids` and `fmt_fn`
    come from the caller so this stays decoupled from where cases live."""
    st.markdown("#### ➕ Build a case combo")
    st.caption("Bundle several cases to arrive together, mirroring a real hospital shift.")
    with st.form("combo_builder_form"):
        name = st.text_input("Combo name", placeholder="e.g. Monday AM Surge")
        picked = st.multiselect("Cases in this combo", all_case_ids, format_func=fmt_fn)
        urgency_note = st.text_input("Urgency note for the pager (optional)",
                                      placeholder="e.g. 1 routine + 2 critical arrivals")
        go = st.form_submit_button("Save Combo", type="primary")
        if go:
            if not name.strip() or len(picked) < 2:
                st.error("Give the combo a name and pick at least 2 cases.")
            else:
                combo_id = f"combo_{int(time.time()*1000)}"
                ok, msg = save_combo({
                    "combo_id": combo_id, "name": name.strip(), "case_ids": picked,
                    "urgency_note": urgency_note.strip(),
                    "created_by": st.session_state.get("auth_user", {}).get("email", "unknown"),
                })
                st.success("✅ Combo saved.") if ok else st.error(msg)


def render_combo_list_with_release(on_release):
    """Lists saved combos with a Release button. `on_release(combo)` is
    called with the full combo row when clicked."""
    combos = list_combos()
    if not combos:
        st.info("No case combos saved yet.")
        return
    for c in combos:
        col1, col2, col3 = st.columns([3, 1, 1])
        col1.markdown(f"**{c['name']}** — {len(c['case_ids'])} cases"
                      + (f" · _{c['urgency_note']}_" if c.get("urgency_note") else ""))
        if col2.button("🚀 Release", key=f"release_{c['combo_id']}", type="primary"):
            on_release(c)
        if col3.button("🗑", key=f"del_combo_{c['combo_id']}"):
            delete_combo(c["combo_id"])
            st.rerun()
