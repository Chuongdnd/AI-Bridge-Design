"""
utils/workspace.py — Không gian làm việc theo TỪNG tài khoản (multi-user).

Bố cục đĩa (ổ cố định trên server):
    users/<username>/
        library/              ← thư viện riêng của user (8 file .json)
        projects/
            <project_id>/
                design.json   ← inputs + 3 phương án (PA1/PA2/PA3)
                meta.json     ← {id, name, created, modified}

Module thuần Python (không phụ thuộc Streamlit). Việc seed thư viện cho user mới
= COPY bộ mặc định ở Data/Library/ sang users/<u>/library/ (chỉ khi chưa có).
"""
import os
import re
import json
import time
import shutil
import unicodedata

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT     = os.path.dirname(_THIS_DIR)

USERS_ROOT      = os.path.join(_ROOT, "users")
DEFAULT_LIB_DIR = os.path.join(_ROOT, "Data", "Library")

# Các file kho thư viện (đồng bộ với component_library.STORE_FILES)
STORE_FILES = ("components.json", "beams.json", "piers.json", "mos.json",
               "railings.json", "caps.json", "stems.json", "footings.json")


# ── Tiện ích ─────────────────────────────────────────────────────────────────
def _slug(text: str) -> str:
    text = str(text or "").strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("đ", "d").replace("Đ", "D")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "du-an"


def _safe_user(username: str) -> str:
    """Chuẩn hoá tên user thành tên thư mục an toàn (chống path traversal)."""
    u = _slug(username)
    return u or "user"


# ── Thư mục user & thư viện ──────────────────────────────────────────────────
def user_dir(username: str) -> str:
    return os.path.join(USERS_ROOT, _safe_user(username))


def user_library_dir(username: str) -> str:
    return os.path.join(user_dir(username), "library")


def projects_root(username: str) -> str:
    return os.path.join(user_dir(username), "projects")


def seed_user_library(username: str) -> bool:
    """COPY bộ thư viện mặc định sang thư viện riêng của user nếu CHƯA có.
    Trả về True nếu vừa seed (tạo mới), False nếu đã tồn tại."""
    dst = user_library_dir(username)
    if os.path.isdir(dst) and any(
            os.path.exists(os.path.join(dst, f)) for f in STORE_FILES):
        return False
    os.makedirs(dst, exist_ok=True)
    for f in STORE_FILES:
        src = os.path.join(DEFAULT_LIB_DIR, f)
        if os.path.exists(src):
            try:
                shutil.copy2(src, os.path.join(dst, f))
            except OSError:
                pass
    return True


def ensure_user(username: str) -> str:
    """Bảo đảm cây thư mục + thư viện cho user. Trả về user_dir."""
    os.makedirs(projects_root(username), exist_ok=True)
    seed_user_library(username)
    return user_dir(username)


# ── Dự án (nhiều dự án / user) ───────────────────────────────────────────────
def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _new_pid(name: str, existing: set) -> str:
    base = _slug(name)
    pid  = base
    i = 2
    while pid in existing:
        pid = f"{base}-{i}"
        i += 1
    return pid


def project_dir(username: str, pid: str) -> str:
    return os.path.join(projects_root(username), _slug(pid))


def _meta_path(username: str, pid: str) -> str:
    return os.path.join(project_dir(username, pid), "meta.json")


def _design_path(username: str, pid: str) -> str:
    return os.path.join(project_dir(username, pid), "design.json")


def list_projects(username: str) -> list:
    """Danh sách dự án [{id, name, created, modified}] — mới sửa lên đầu."""
    root = projects_root(username)
    out = []
    if os.path.isdir(root):
        for pid in os.listdir(root):
            mp = _meta_path(username, pid)
            if os.path.exists(mp):
                try:
                    with open(mp, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    meta.setdefault("id", pid)
                    out.append(meta)
                except (OSError, json.JSONDecodeError):
                    out.append({"id": pid, "name": pid,
                                "created": "", "modified": ""})
    out.sort(key=lambda m: m.get("modified", ""), reverse=True)
    return out


def create_project(username: str, name: str, design: dict = None) -> str:
    """Tạo dự án mới, trả về project_id."""
    ensure_user(username)
    existing = {p["id"] for p in list_projects(username)}
    pid = _new_pid(name, existing)
    os.makedirs(project_dir(username, pid), exist_ok=True)
    now = _now()
    meta = {"id": pid, "name": (name or pid).strip() or pid,
            "created": now, "modified": now}
    with open(_meta_path(username, pid), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    save_project_design(username, pid, design or {})
    return pid


def project_meta(username: str, pid: str) -> dict:
    mp = _meta_path(username, pid)
    if os.path.exists(mp):
        try:
            with open(mp, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {"id": pid, "name": pid, "created": "", "modified": ""}


def rename_project(username: str, pid: str, new_name: str) -> None:
    meta = project_meta(username, pid)
    meta["name"] = (new_name or pid).strip() or pid
    meta["modified"] = _now()
    os.makedirs(project_dir(username, pid), exist_ok=True)
    with open(_meta_path(username, pid), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def delete_project(username: str, pid: str) -> None:
    d = project_dir(username, pid)
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)


def load_project_design(username: str, pid: str) -> dict:
    dp = _design_path(username, pid)
    if os.path.exists(dp):
        try:
            with open(dp, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_project_design(username: str, pid: str, design: dict) -> None:
    os.makedirs(project_dir(username, pid), exist_ok=True)
    with open(_design_path(username, pid), "w", encoding="utf-8") as f:
        json.dump(design or {}, f, ensure_ascii=False, indent=2)
    # cập nhật mốc sửa
    meta = project_meta(username, pid)
    meta["modified"] = _now()
    with open(_meta_path(username, pid), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def duplicate_project(username: str, pid: str, new_name: str = None) -> str:
    """Nhân bản dự án (kèm design). Trả về project_id mới."""
    src_meta = project_meta(username, pid)
    name = (new_name or (src_meta.get("name", pid) + " (bản sao)"))
    design = load_project_design(username, pid)
    return create_project(username, name, design)
