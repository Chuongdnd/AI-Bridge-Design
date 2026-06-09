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


def _load() -> dict:
    if not os.path.exists(_AUTH_FILE):
        db = _default_db()
        _save(db)
        return db
    try:
        with open(_AUTH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _default_db()


def _save(db: dict):
    with open(_AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


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


# ─────────────────────────────────────────────────────────────────────────────
# Trang dang nhap
# ─────────────────────────────────────────────────────────────────────────────

def show_login_page():
    """Hien thi trang dang nhap. Tra ve True neu dang nhap thanh cong."""

    # CSS trang dang nhap
    st.markdown("""
<style>
.login-box {
    max-width: 420px;
    margin: 60px auto;
    padding: 40px 36px 32px;
    background: #1e1e2e;
    border-radius: 14px;
    border: 1px solid #3a3a5c;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.login-title {
    text-align: center;
    color: #f0f0f0;
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 6px;
}
.login-sub {
    text-align: center;
    color: #888;
    font-size: 13px;
    margin-bottom: 28px;
}
</style>
""", unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown('<div class="login-title">🏗️ Hệ thống Thiết kế Cầu AI</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">UTH — Vui lòng đăng nhập để tiếp tục</div>', unsafe_allow_html=True)

        username = st.text_input("Tên đăng nhập", key="login_user", placeholder="username")
        password = st.text_input("Mật khẩu", type="password", key="login_pass", placeholder="••••••••")

        if st.button("🔐 Đăng nhập", use_container_width=True, type="primary", key="login_btn"):
            db = _load()
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
                st.error("Tên đăng nhập hoặc mật khẩu không đúng.")

        st.markdown("</div>", unsafe_allow_html=True)

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
