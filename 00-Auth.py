"""
Module 00-Auth — Xac thuc nguoi dung
=====================================
Luu tru: auth_users.json  (cung thu muc voi app)
Hash  : SHA-256 + salt ngau nhien 32 hex chars
Roles : admin (toan quyen) | user (chi xem/tinh)
"""

import json
import hashlib
import secrets
import os
import streamlit as st

_AUTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_users.json")

# Tạm ẩn đăng ký tự phục vụ (hệ thống chưa phổ biến rộng). Đặt True để bật lại.
ALLOW_SELF_REGISTER = False

# ─────────────────────────────────────────────────────────────────────────────
# Hash / verify
# ─────────────────────────────────────────────────────────────────────────────

def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def _verify(password: str, stored_hash: str, salt: str) -> bool:
    return _hash(password, salt) == stored_hash


# ─────────────────────────────────────────────────────────────────────────────
# Load / save
# ─────────────────────────────────────────────────────────────────────────────

def _default_db() -> dict:
    """Tao co so du lieu mac dinh voi tai khoan admin."""
    salt = secrets.token_hex(16)
    return {
        "users": {
            "admin": {
                "name":          "Administrator",
                "email":         "",
                "role":          "admin",
                "salt":          salt,
                "password_hash": _hash("admin123", salt),
            }
        }
    }


def _secrets_users() -> dict:
    """Tài khoản khai trong st.secrets[auth_users] — NGUỒN BỀN qua reboot trên
    Streamlit Cloud (file auth_users.json là TẠM, mất khi reboot). Định dạng:
        [auth_users.admin]
        password = "matkhau_moi"
        name = "Administrator"   # tùy chọn
        role = "admin"           # tùy chọn (mặc định: user)
        email = ""               # tùy chọn
    """
    out = {}
    try:
        su = dict(st.secrets.get("auth_users", {}) or {})
    except Exception:
        su = {}
    for uname, info in su.items():
        info = {"password": info} if isinstance(info, str) else dict(info)
        pw = str(info.get("password", "")).strip()
        if not pw:
            continue
        salt = secrets.token_hex(16)
        out[str(uname).strip()] = {
            "name":          info.get("name", uname),
            "email":         info.get("email", ""),
            "role":          info.get("role", "user"),
            "salt":          salt,
            "password_hash": _hash(pw, salt),
        }
    return out


# ── Kho BỀN ngoài: GitHub Gist riêng (đăng ký/đổi mật khẩu qua UI persist thật) ──
# Khai trong st.secrets:
#   [gist_auth]
#   token    = "ghp_xxx"        # PAT có quyền 'gist'
#   gist_id  = "xxxxxxxx"       # id của gist riêng
#   filename = "auth_users.json"  # (tùy chọn)
def _gist_cfg():
    try:
        g = st.secrets.get("gist_auth", None)
        if g and g.get("token") and g.get("gist_id"):
            return (g["token"], g["gist_id"], g.get("filename", "auth_users.json"))
    except Exception:
        pass
    return None


def _gist_fetch(cfg):
    import urllib.request
    token, gid, fname = cfg
    req = urllib.request.Request(
        f"https://api.github.com/gists/{gid}",
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "uth-bridge-app"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))
    f = (data.get("files") or {}).get(fname)
    if not f:
        return None
    content = (f.get("content") or "").strip()
    return json.loads(content) if content else None


def _gist_write(cfg, db):
    import urllib.request
    token, gid, fname = cfg
    body = json.dumps({"files": {fname: {"content":
            json.dumps(db, ensure_ascii=False, indent=2)}}}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.github.com/gists/{gid}", data=body, method="PATCH",
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json",
                 "User-Agent": "uth-bridge-app"})
    urllib.request.urlopen(req, timeout=10).read()


def _load() -> dict:
    cfg = _gist_cfg()
    if cfg:
        # Kho ngoài (Gist) — cache trong phiên để khỏi gọi API mỗi lần rerun
        db = st.session_state.get("_auth_db_cache")
        if db is None:
            try:
                db = _gist_fetch(cfg)
            except Exception:
                db = None
            if not (isinstance(db, dict) and db.get("users")):
                db = _default_db()
                try: _gist_write(cfg, db)
                except Exception: pass
            st.session_state["_auth_db_cache"] = db
    elif os.path.exists(_AUTH_FILE):
        try:
            with open(_AUTH_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
        except Exception:
            db = _default_db()
    else:
        db = _default_db()
    # Overlay tài khoản khai trong Secrets (admin cố định / khôi phục)
    _sec = _secrets_users()
    if _sec:
        db.setdefault("users", {})
        db["users"].update(_sec)
    return db


def _save(db: dict):
    cfg = _gist_cfg()
    if cfg:
        st.session_state["_auth_db_cache"] = db
        try:
            _gist_write(cfg, db)
        except Exception as _e:
            try: st.warning(f"Không ghi được kho tài khoản (Gist): {_e}")
            except Exception: pass
    else:
        try:
            with open(_AUTH_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────

def is_authenticated() -> bool:
    return bool(st.session_state.get("auth_ok"))


def current_user() -> dict:
    """Tra ve {'username':..., 'name':..., 'role':...} hoac {}."""
    return st.session_state.get("auth_user", {})


def is_admin() -> bool:
    return current_user().get("role") == "admin"


def logout():
    for k in ("auth_ok", "auth_user"):
        st.session_state.pop(k, None)


def reset_auth_db() -> tuple:
    """Đặt lại TOÀN BỘ kho tài khoản về mặc định (admin / admin123).

    - Xóa file auth_users.json cục bộ (nếu có) và ghi đè kho Gist (nếu cấu hình).
    - Xóa cache phiên để lần _load() sau đọc kho mới.
    - Tài khoản khai trong st.secrets[auth_users] không bị ảnh hưởng
      (luôn được overlay lại khi load).
    Trả về (ok: bool, msg: str).
    """
    db = _default_db()
    st.session_state.pop("_auth_db_cache", None)
    try:
        if os.path.exists(_AUTH_FILE):
            os.remove(_AUTH_FILE)
    except Exception:
        pass
    _save(db)
    return True, "Đã đặt lại kho tài khoản về mặc định: admin / admin123."


# ─────────────────────────────────────────────────────────────────────────────
# Dang ky tai khoan (tu phuc vu)
# ─────────────────────────────────────────────────────────────────────────────

def user_exists(username: str) -> bool:
    return username.strip() in _load().get("users", {})


def register_user(username: str, name: str, email: str, password: str,
                  role: str = "user") -> tuple:
    """Tao tai khoan moi (tu dang ky). Tra ve (ok: bool, msg: str)."""
    username = (username or "").strip()
    email    = (email or "").strip()
    if not username:
        return False, "Tên đăng nhập không được để trống."
    if not username.replace("_", "").replace("-", "").replace(".", "").isalnum():
        return False, "Tên đăng nhập chỉ gồm chữ, số, '_', '-', '.'."
    if "@" not in email or "." not in email.split("@")[-1]:
        return False, "Email không hợp lệ."
    if len(password) < 6:
        return False, "Mật khẩu phải có ít nhất 6 ký tự."
    db = _load()
    users = db.setdefault("users", {})
    if username in users:
        return False, f"Tên đăng nhập '{username}' đã tồn tại."
    # Email duy nhat (neu da co user khac dung)
    for un, ud in users.items():
        if email and ud.get("email", "").lower() == email.lower():
            return False, f"Email này đã được dùng cho tài khoản '{un}'."
    salt = secrets.token_hex(16)
    users[username] = {
        "name":          name.strip() or username,
        "email":         email,
        "role":          role,
        "salt":          salt,
        "password_hash": _hash(password, salt),
    }
    _save(db)
    return True, f"Đã tạo tài khoản '{username}'. Mời đăng nhập."


# ─────────────────────────────────────────────────────────────────────────────
# Trang dang nhap
# ─────────────────────────────────────────────────────────────────────────────

def show_login_page():
    """Hien thi trang dang nhap centred, co the nhan Enter de submit."""

    st.markdown("""
<style>
/* An toan bo sidebar va header o trang login */
[data-testid="stSidebar"]        { display: none !important; }
[data-testid="stHeader"]         { display: none !important; }
[data-testid="stToolbarActions"] { display: none !important; }
[data-testid="stDecoration"]     { display: none !important; }
[data-testid="stStatusWidget"]   { display: none !important; }
.stDeployButton                  { display: none !important; }
#MainMenu                        { display: none !important; }
footer                           { display: none !important; }

/* Nền login: KHÔNG ép → theo theme chọn trong ☰ Settings của Streamlit */

/* Bo form Streamlit */
[data-testid="stForm"] {
    background: #1e1e2e;
    border: 1px solid #3a3a5c;
    border-radius: 16px;
    padding: 32px 28px 24px !important;
    box-shadow: 0 8px 40px rgba(0,0,0,0.5);
}
</style>
""", unsafe_allow_html=True)

    # Khoang trong phia tren de can chinh doc
    st.markdown("<br><br><br>", unsafe_allow_html=True)

    _, mid, _ = st.columns([1.2, 1, 1.2])
    with mid:
        _sub = ("Đăng nhập hoặc đăng ký để tiếp tục" if ALLOW_SELF_REGISTER
                else "Vui lòng đăng nhập để tiếp tục")
        st.markdown(
            "<h2 style='text-align:center;color:#007acc;font-weight:700;margin-bottom:4px'>🏗️ Hệ thống thiết kế cầu</h2>"
            f"<p style='text-align:center;color:#6b7280;font-size:13px;margin-bottom:24px'>"
            f"UTH — {_sub}</p>",
            unsafe_allow_html=True,
        )

        # ── Đăng nhập ──────────────────────────────────────────────────────
        def _do_login():
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Tên đăng nhập", placeholder="username", key="lf_user")
                password = st.text_input("Mật khẩu", type="password", placeholder="••••••••", key="lf_pass")
                submitted = st.form_submit_button("🔐 Đăng nhập", use_container_width=True, type="primary")

            if submitted:
                db    = _load()
                udata = db["users"].get(username.strip())
                if udata and _verify(password, udata["password_hash"], udata["salt"]):
                    st.session_state["auth_ok"]   = True
                    st.session_state["auth_user"] = {
                        "username": username.strip(),
                        "name":     udata.get("name", username),
                        "role":     udata.get("role", "user"),
                    }
                    st.rerun()
                else:
                    st.error("❌ Tên đăng nhập hoặc mật khẩu không đúng.", icon=None)

        # ── Đăng ký (ẩn khi ALLOW_SELF_REGISTER = False) ───────────────────
        def _do_register():
            with st.form("register_form", clear_on_submit=False):
                r_user = st.text_input("Tên đăng nhập", placeholder="username", key="rf_user")
                r_name = st.text_input("Họ và tên", placeholder="Nguyễn Văn A", key="rf_name")
                r_mail = st.text_input("Email", placeholder="ban@example.com", key="rf_mail")
                r_p1   = st.text_input("Mật khẩu", type="password", placeholder="≥ 6 ký tự", key="rf_p1")
                r_p2   = st.text_input("Xác nhận mật khẩu", type="password", key="rf_p2")
                reg_submit = st.form_submit_button("📝 Tạo tài khoản", use_container_width=True, type="primary")

            if reg_submit:
                if r_p1 != r_p2:
                    st.error("Mật khẩu xác nhận không khớp.")
                else:
                    ok, msg = register_user(r_user, r_name, r_mail, r_p1)
                    if ok:
                        st.success("✅ " + msg + " Chuyển sang tab Đăng nhập.")
                    else:
                        st.error("❌ " + msg)

        if ALLOW_SELF_REGISTER:
            tab_login, tab_reg = st.tabs(["🔐 Đăng nhập", "📝 Đăng ký"])
            with tab_login:
                _do_login()
            with tab_reg:
                _do_register()
        else:
            _do_login()

    return is_authenticated()


# ─────────────────────────────────────────────────────────────────────────────
# Panel quan ly tai khoan (chi admin)
# ─────────────────────────────────────────────────────────────────────────────

def show_account_panel():
    """Render trong sidebar hoac main area tuy caller."""
    if not is_admin():
        st.warning("Chỉ admin mới có quyền quản lý tài khoản.")
        return

    db = _load()
    users = db["users"]

    st.markdown("### 👥 Quản lý tài khoản")

    # Danh sach tai khoan hien co
    st.markdown("#### Tài khoản hiện có")
    for uname, udata in users.items():
        cols = st.columns([3, 2, 1])
        cols[0].markdown(f"**{uname}** — {udata.get('name','')}")
        cols[1].markdown(f"Role: `{udata.get('role','user')}`")
        if uname != "admin":   # Khong cho xoa admin
            if cols[2].button("🗑️", key=f"del_{uname}", help=f"Xóa {uname}"):
                del db["users"][uname]
                _save(db)
                st.success(f"Đã xóa tài khoản **{uname}**.")
                st.rerun()

    st.markdown("---")

    # Them tai khoan moi
    with st.expander("➕ Thêm tài khoản mới", expanded=False):
        new_u = st.text_input("Tên đăng nhập mới", key="new_uname").strip()
        new_n = st.text_input("Họ tên hiển thị",   key="new_name").strip()
        new_e = st.text_input("Email (tuỳ chọn)",   key="new_email").strip()
        new_r = st.selectbox("Vai trò", ["user", "admin"], key="new_role")
        new_p = st.text_input("Mật khẩu", type="password", key="new_pass")
        new_p2= st.text_input("Xác nhận mật khẩu", type="password", key="new_pass2")

        if st.button("✅ Tạo tài khoản", key="btn_create"):
            if not new_u:
                st.error("Tên đăng nhập không được để trống.")
            elif new_u in users:
                st.error(f"Tên đăng nhập **{new_u}** đã tồn tại.")
            elif len(new_p) < 6:
                st.error("Mật khẩu phải có ít nhất 6 ký tự.")
            elif new_p != new_p2:
                st.error("Mật khẩu xác nhận không khớp.")
            else:
                salt = secrets.token_hex(16)
                users[new_u] = {
                    "name":          new_n or new_u,
                    "email":         new_e,
                    "role":          new_r,
                    "salt":          salt,
                    "password_hash": _hash(new_p, salt),
                }
                _save(db)
                st.success(f"Đã tạo tài khoản **{new_u}** ({new_r}).")
                st.rerun()

    st.markdown("---")

    # Doi mat khau
    with st.expander("🔑 Đổi mật khẩu", expanded=False):
        chg_u = st.selectbox("Chọn tài khoản", list(users.keys()), key="chg_u")
        chg_p = st.text_input("Mật khẩu mới", type="password", key="chg_p")
        chg_p2= st.text_input("Xác nhận", type="password", key="chg_p2")

        if st.button("💾 Lưu mật khẩu mới", key="btn_chg_pass"):
            if len(chg_p) < 6:
                st.error("Mật khẩu phải có ít nhất 6 ký tự.")
            elif chg_p != chg_p2:
                st.error("Mật khẩu xác nhận không khớp.")
            else:
                salt = secrets.token_hex(16)
                users[chg_u]["salt"]          = salt
                users[chg_u]["password_hash"] = _hash(chg_p, salt)
                _save(db)
                st.success(f"Đã cập nhật mật khẩu cho **{chg_u}**.")

    st.markdown("---")

    # Dat lai toan bo tai khoan ve mac dinh
    with st.expander("🔄 Đặt lại toàn bộ tài khoản (khôi phục mặc định)", expanded=False):
        st.warning(
            "Thao tác này **XÓA tất cả tài khoản** hiện có và khôi phục về "
            "mặc định `admin / admin123`. Tài khoản khai trong Secrets "
            "không bị ảnh hưởng. Không thể hoàn tác!"
        )
        rs_confirm = st.text_input(
            "Gõ `RESET` để xác nhận", key="rs_confirm", placeholder="RESET"
        )
        if st.button("⚠️ Đặt lại tài khoản", key="btn_reset_db", type="primary"):
            if rs_confirm.strip() != "RESET":
                st.error("Chưa xác nhận: hãy gõ đúng chữ RESET.")
            else:
                ok, msg = reset_auth_db()
                if ok:
                    logout()   # phien hien tai dang nhap lai bang mat khau moi
                    st.success("✅ " + msg + " Mời đăng nhập lại.")
                    st.rerun()
                else:
                    st.error("❌ " + msg)
