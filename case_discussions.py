"""
case_discussions.py - Case Discussion Rooms for the MLS Virtual Hospital (additive, standalone).

Students open discussions around cases, reply with reasoning, mark helpful replies, follow threads and
get notified (in-app bell + email) when others reply. Faculty can pin, close, comment and hide posts.

Safety built in:
  - every post with images needs a de-identification confirmation
  - images are re-encoded (EXIF/GPS/camera metadata stripped), resized, max 3 per post
  - notification emails never contain case content (title + link only)
  - one email per follower per thread per hour; instant/off preference per user

Storage: Supabase (tables in case_discussions.sql). Without Supabase: labelled DEMO mode (session only).
Email: reuses admin_user_panel._send_one_email (Gmail credentials already configured for the app).

Hook-up in app.py:  from case_discussions import render_case_discussions ; render_case_discussions()
"""
import base64
import io
import datetime as _dt
import requests
import streamlit as st

DEPTS = ["General", "Critical Care", "Medical Laboratory / Pathology", "Endoscopy", "Cardiology",
         "Infectious Disease", "Endocrinology", "Oncology", "Surgery", "Radiology", "Medical Education", "Other"]
T = {"threads": "vh_disc_threads", "posts": "vh_disc_posts", "follows": "vh_disc_follows", "prefs": "vh_disc_prefs"}
MAX_IMG = 3
EMAIL_GAP_MIN = 60
DEIDENT = ("I confirm every image and all text here is de-identified: no faces, names, ID or record numbers, "
           "hospital labels, dates of birth, tattoos or other identifying marks, and any required patient consent "
           "has been obtained.")


# ─────────────── storage (Supabase or demo) ───────────────
def _secret(k, d=""):
    try:
        return st.secrets.get(k, d)
    except Exception:
        return d


def _sb():
    u, k = _secret("SUPABASE_URL"), _secret("SUPABASE_KEY")
    return (u.rstrip("/"), k) if u and k and not str(u).startswith("YOUR_") else None


def _h(k):
    return {"apikey": k, "Authorization": f"Bearer {k}", "Content-Type": "application/json",
            "Prefer": "return=representation"}


def _demo():
    return st.session_state.setdefault("cd_demo", {t: [] for t in T})


def _now():
    return _dt.datetime.utcnow().isoformat(timespec="seconds")


def sel(t, eq=None, order=None):
    cfg = _sb()
    if cfg:
        u, k = cfg
        p = {"select": "*"}
        for c, v in (eq or {}).items():
            p[c] = f"eq.{v}"
        if order:
            p["order"] = order
        try:
            r = requests.get(f"{u}/rest/v1/{T[t]}", headers=_h(k), params=p, timeout=10)
            return r.json() if r.status_code == 200 else []
        except Exception:
            return []
    rows = [r for r in _demo()[t] if all(str(r.get(c)) == str(v) for c, v in (eq or {}).items())]
    if order:
        col, _, d = order.partition(".")
        rows = sorted(rows, key=lambda r: str(r.get(col, "")), reverse=(d == "desc"))
    return rows


def ins(t, row):
    cfg = _sb()
    if cfg:
        u, k = cfg
        try:
            r = requests.post(f"{u}/rest/v1/{T[t]}", headers=_h(k), json=row, timeout=15)
            if r.status_code in (200, 201):
                j = r.json()
                return j[0] if j else row
        except Exception:
            pass
        st.error("Could not save. Check that case_discussions.sql has been run in Supabase.")
        return None
    d = _demo()
    row = dict(row)
    row["id"] = len(d[t]) + 1
    row.setdefault("created_at", _now())
    d[t].append(row)
    return row


def upd(t, rid, patch):
    cfg = _sb()
    if cfg:
        u, k = cfg
        try:
            r = requests.patch(f"{u}/rest/v1/{T[t]}", headers=_h(k), params={"id": f"eq.{rid}"}, json=patch, timeout=10)
            return r.status_code in (200, 204)
        except Exception:
            return False
    for r in _demo()[t]:
        if str(r["id"]) == str(rid):
            r.update(patch)
    return True


# ─────────────── helpers ───────────────
def _user():
    a = st.session_state.get("auth_user") or {}
    return {"id": str(a.get("id") or a.get("email") or ""), "name": a.get("name") or a.get("email") or "Guest",
            "email": (a.get("email") or "").strip(), "role": (a.get("role") or "student").lower(),
            "signed_in": bool(a)}


def _mod(u):
    return u["role"] in ("admin", "faculty")


def clean_image(data: bytes):
    """Re-encode: strips EXIF/GPS/camera metadata, fixes rotation, max 1200px, JPEG q80. Returns b64 str or None."""
    try:
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((1200, 1200))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=80, optimize=True)  # no exif passed => metadata dropped
        return base64.b64encode(out.getvalue()).decode()
    except Exception:
        return None


def _images_from(files):
    out = []
    for f in (files or [])[:MAX_IMG]:
        if f.size > 8 * 1024 * 1024:
            st.warning(f"{f.name} is larger than 8 MB and was skipped.")
            continue
        b = clean_image(f.getvalue())
        if b:
            out.append(b)
        else:
            st.warning(f"{f.name} could not be read as an image and was skipped.")
    return out


def _show_images(imgs):
    imgs = imgs or []
    if imgs:
        cols = st.columns(len(imgs))
        for c, b in zip(cols, imgs):
            c.image(base64.b64decode(b), use_container_width=True)


def _prefs(u):
    rows = sel("prefs", eq={"user_id": u["id"]})
    if rows:
        return rows[0]
    return ins("prefs", {"user_id": u["id"], "email": u["email"], "email_mode": "instant", "last_seen": _now()}) or \
        {"user_id": u["id"], "email_mode": "instant", "last_seen": _now(), "id": None}


def _follow(u, tid):
    if not [f for f in sel("follows", eq={"thread_id": tid}) if f["user_id"] == u["id"]]:
        ins("follows", {"thread_id": tid, "user_id": u["id"], "email": u["email"], "last_emailed": ""})


def _following(u, tid):
    return any(f["user_id"] == u["id"] for f in sel("follows", eq={"thread_id": tid}))


def _unfollow(u, tid):
    cfg = _sb()
    if cfg:
        url, k = cfg
        try:
            requests.delete(f"{url}/rest/v1/{T['follows']}", headers=_h(k),
                            params={"thread_id": f"eq.{tid}", "user_id": f"eq.{u['id']}"}, timeout=10)
        except Exception:
            pass
    else:
        d = _demo()
        d["follows"] = [f for f in d["follows"] if not (str(f["thread_id"]) == str(tid) and f["user_id"] == u["id"])]


def _notify(thread, author, ptype):
    """Email followers (not the author) - title + link only, max 1 email/hour/thread/follower, max 40 per call."""
    try:
        from admin_user_panel import _send_one_email, _build_html_email
    except Exception:
        return 0
    app_url = _secret("APP_URL", "https://mls-virtual-hospital.streamlit.app")
    sent = 0
    now = _dt.datetime.utcnow()
    for f in sel("follows", eq={"thread_id": thread["id"]}):
        if sent >= 40 or f.get("user_id") == author["id"] or not f.get("email"):
            continue
        pr = sel("prefs", eq={"user_id": f["user_id"]})
        if pr and pr[0].get("email_mode") == "off":
            continue
        le = f.get("last_emailed") or ""
        try:
            if le and (now - _dt.datetime.fromisoformat(le)).total_seconds() < EMAIL_GAP_MIN * 60:
                continue
        except Exception:
            pass
        title = thread.get("title", "a discussion")
        html = _build_html_email(
            "New reply in a discussion you follow",
            f"<b>{author['name']}</b> replied in <b>{title}</b>.<br><br>Open the app and go to "
            f"<b>Case Discussions</b> to read it. You can switch emails off there at any time.",
            "Open MLS Virtual Hospital", app_url)
        if _send_one_email(f["email"], f"New reply: {title}", html, f"New reply in: {title}. Open {app_url}"):
            upd("follows", f["id"], {"last_emailed": _now()})
            sent += 1
    return sent


# ─────────────── pages ───────────────
def _list(u):
    c = st.columns([2, 2, 1])
    dept = c[0].selectbox("Department", ["All"] + DEPTS, key="cd_dept")
    q = c[1].text_input("Search titles", key="cd_q")
    unans = c[2].checkbox("Unanswered", key="cd_un")
    threads = [t for t in sel("threads") if not t.get("hidden")]
    posts = sel("posts")
    cnt = {}
    for p in posts:
        if not p.get("hidden"):
            cnt[str(p["thread_id"])] = cnt.get(str(p["thread_id"]), 0) + 1
    threads.sort(key=lambda t: (not t.get("pinned"), str(t.get("last_activity", "")),), reverse=False)
    threads.sort(key=lambda t: str(t.get("last_activity", "")), reverse=True)
    threads.sort(key=lambda t: not t.get("pinned"))
    shown = 0
    for t in threads:
        n = cnt.get(str(t["id"]), 0)
        if dept != "All" and t.get("department") != dept:
            continue
        if q and q.lower() not in (t.get("title") or "").lower():
            continue
        if unans and n:
            continue
        shown += 1
        with st.container(border=True):
            tag = ("📌 " if t.get("pinned") else "") + ("🔒 " if t.get("status") == "closed" else "")
            st.markdown(f"**{tag}{t['title']}**  \n{t.get('department', '')} · by {t.get('author_name', '')} · "
                        f"{n} repl{'y' if n == 1 else 'ies'}")
            if st.button("Open discussion", key=f"cd_o_{t['id']}"):
                st.session_state["cd_open"] = t["id"]
                st.rerun()
    if not shown:
        st.info("No discussions yet. Start the first one in the next tab.")


def _new(u):
    if not u["signed_in"]:
        st.warning("Sign in to start a discussion.")
        return
    nf = st.session_state.get("cd_nf", 0)
    if st.session_state.pop("cd_posted", False):
        st.success("Posted. You will be notified when someone replies.")
    with st.form(f"cd_new_{nf}", clear_on_submit=False):
        title = st.text_input("Title (a clear question or case headline)")
        c = st.columns(2)
        dept = c[0].selectbox("Department", DEPTS)
        ref = c[1].text_input("Related case (optional)")
        body = st.text_area("Describe the case or question. What do you think, and why?", height=150)
        files = st.file_uploader(f"Images (optional, up to {MAX_IMG})", type=["jpg", "jpeg", "png"],
                                 accept_multiple_files=True)
        ok = st.checkbox(DEIDENT)
        if st.form_submit_button("Post discussion", type="primary"):
            if not (title.strip() and body.strip()):
                st.error("Title and description are required.")
            elif files and not ok:
                st.error("Please confirm the images are de-identified.")
            elif not ok:
                st.error("Please confirm the content is de-identified.")
            else:
                imgs = _images_from(files)
                t = ins("threads", {"title": title.strip(), "body": body.strip(), "department": dept,
                                    "case_ref": ref.strip(), "author_id": u["id"], "author_name": u["name"],
                                    "status": "open", "pinned": False, "hidden": False, "images": imgs,
                                    "last_activity": _now()})
                if t:
                    _follow(u, t["id"])
                    st.session_state["cd_nf"] = nf + 1
                    st.session_state["cd_posted"] = True
                    st.rerun()


def _thread(u, tid):
    rows = sel("threads", eq={"id": tid})
    if not rows or rows[0].get("hidden"):
        st.error("Discussion not found.")
        st.session_state.pop("cd_open", None)
        return
    t = rows[0]
    if st.button("← All discussions"):
        st.session_state.pop("cd_open", None)
        st.rerun()
    st.markdown(f"## {'📌 ' if t.get('pinned') else ''}{t['title']}")
    st.caption(f"{t.get('department')} · by {t.get('author_name')} · {str(t.get('created_at', ''))[:16]}"
               + (f" · case: {t['case_ref']}" if t.get("case_ref") else "")
               + (" · 🔒 closed" if t.get("status") == "closed" else ""))
    st.write(t.get("body"))
    _show_images(t.get("images"))

    c = st.columns(4)
    if u["signed_in"]:
        if _following(u, tid):
            if c[0].button("🔕 Unfollow", key="cd_unf"):
                _unfollow(u, tid)
                st.rerun()
        elif c[0].button("🔔 Follow", key="cd_fol"):
            _follow(u, tid)
            st.rerun()
    if _mod(u):
        if c[1].button("Unpin" if t.get("pinned") else "📌 Pin", key="cd_pin"):
            upd("threads", tid, {"pinned": not t.get("pinned")})
            st.rerun()
        if c[2].button("Reopen" if t.get("status") == "closed" else "🔒 Close", key="cd_cl"):
            upd("threads", tid, {"status": "open" if t.get("status") == "closed" else "closed"})
            st.rerun()
        if c[3].button("🗑 Remove", key="cd_rm"):
            upd("threads", tid, {"hidden": True})
            st.session_state.pop("cd_open", None)
            st.rerun()
    st.divider()

    posts = [p for p in sel("posts", eq={"thread_id": tid}, order="created_at.asc") if not p.get("hidden")]
    posts.sort(key=lambda p: (not p.get("best"),))
    for p in posts:
        with st.container(border=True):
            badge = " · 🎓 Faculty" if p.get("is_faculty") else ""
            best = "✅ **Best answer**  \n" if p.get("best") else ""
            st.markdown(f"{best}**{p.get('author_name')}**{badge} · {str(p.get('created_at', ''))[:16]}")
            st.write(p.get("body"))
            _show_images(p.get("images"))
            hb = p.get("helpful_by") or []
            cc = st.columns([1, 1, 1, 3])
            if u["signed_in"] and u["id"] not in hb and p.get("author_id") != u["id"]:
                if cc[0].button(f"👍 Helpful ({len(hb)})", key=f"cd_h_{p['id']}"):
                    upd("posts", p["id"], {"helpful_by": hb + [u["id"]]})
                    st.rerun()
            else:
                cc[0].caption(f"👍 {len(hb)}")
            if u["id"] == t.get("author_id") or _mod(u):
                if cc[1].button("Unmark best" if p.get("best") else "Mark best", key=f"cd_b_{p['id']}"):
                    upd("posts", p["id"], {"best": not p.get("best")})
                    st.rerun()
            if _mod(u) and cc[2].button("Remove", key=f"cd_pr_{p['id']}"):
                upd("posts", p["id"], {"hidden": True})
                st.rerun()
    if not posts:
        st.caption("No replies yet. Be the first to share your reasoning.")

    if t.get("status") == "closed":
        st.info("This discussion is closed.")
    elif not u["signed_in"]:
        st.warning("Sign in to reply.")
    else:
        rf = st.session_state.get("cd_rf_n", 0)
        if st.session_state.pop("cd_replied", None):
            st.success(st.session_state.pop("cd_replied_msg", "Reply posted."))
        with st.form(f"cd_reply_{rf}", clear_on_submit=False):
            body = st.text_area("Your reply (give your reasoning, not just an answer)", height=110)
            files = st.file_uploader(f"Images (optional, up to {MAX_IMG})", type=["jpg", "jpeg", "png"],
                                     accept_multiple_files=True, key=f"cd_rf_{rf}")
            ok = st.checkbox(DEIDENT, key=f"cd_rok_{rf}")
            if st.form_submit_button("Post reply", type="primary"):
                if not body.strip():
                    st.error("Write a reply first.")
                elif not ok:
                    st.error("Please confirm the content is de-identified.")
                else:
                    imgs = _images_from(files)
                    p = ins("posts", {"thread_id": tid, "author_id": u["id"], "author_name": u["name"],
                                      "body": body.strip(), "images": imgs, "is_faculty": _mod(u),
                                      "helpful_by": [], "best": False, "hidden": False})
                    if p:
                        upd("threads", tid, {"last_activity": _now()})
                        _follow(u, tid)
                        n = _notify(t, u, "reply")
                        st.session_state["cd_rf_n"] = rf + 1
                        st.session_state["cd_replied"] = True
                        st.session_state["cd_replied_msg"] = "Reply posted." + (
                            f" {n} follower(s) notified by email." if n else "")
                        st.rerun()


def _bell(u):
    """New replies by others, in threads the user follows, since last_seen."""
    pr = _prefs(u)
    seen = str(pr.get("last_seen") or "")
    mine = {str(f["thread_id"]) for f in sel("follows") if f["user_id"] == u["id"]}
    new = []
    threads = {str(t["id"]): t for t in sel("threads") if not t.get("hidden")}
    for p in sel("posts"):
        if (str(p["thread_id"]) in mine and p.get("author_id") != u["id"] and not p.get("hidden")
                and str(p.get("created_at", "")) > seen and str(p["thread_id"]) in threads):
            new.append(p)
    return pr, new, threads


def _notifications(u):
    if not u["signed_in"]:
        st.warning("Sign in to see notifications.")
        return
    pr, new, threads = _bell(u)
    st.markdown("**Email notifications**")
    mode = st.radio("Email me when someone replies to a discussion I follow",
                    ["instant", "off"], index=0 if pr.get("email_mode") != "off" else 1, horizontal=True,
                    format_func=lambda x: "Yes (max 1 email per discussion per hour)" if x == "instant" else "No emails",
                    key="cd_mode")
    if mode != pr.get("email_mode") and pr.get("id") is not None:
        upd("prefs", pr["id"], {"email_mode": mode, "email": u["email"]})
        st.success("Saved.")
    st.markdown(f"**New replies ({len(new)})**")
    by = {}
    for p in new:
        by.setdefault(str(p["thread_id"]), []).append(p)
    for tid, ps in by.items():
        t = threads[tid]
        with st.container(border=True):
            st.write(f"**{t['title']}** - {len(ps)} new, latest by {ps[-1].get('author_name')}")
            if st.button("Open", key=f"cd_nt_{tid}"):
                st.session_state["cd_open"] = t["id"]
                st.rerun()
    if new and pr.get("id") is not None and st.button("Mark all as read"):
        upd("prefs", pr["id"], {"last_seen": _now()})
        st.rerun()
    if not new:
        st.caption("You are up to date.")


def render_case_discussions():
    u = _user()
    st.markdown("### 💬 Case Discussions")
    st.caption("Discuss cases, share your reasoning, ask questions. Always de-identify patients. "
               "Teaching discussion only - not medical advice.")
    if not _sb():
        st.warning("DEMO MODE: Supabase is not configured, so nothing is saved after this session.")
    if st.session_state.get("cd_open"):
        _thread(u, st.session_state["cd_open"])
        return
    n = 0
    if u["signed_in"]:
        try:
            n = len(_bell(u)[1])
        except Exception:
            n = 0
    t = st.tabs(["Discussions", "Start a discussion", f"🔔 Notifications ({n})"])
    with t[0]:
        _list(u)
    with t[1]:
        _new(u)
    with t[2]:
        _notifications(u)
