"""
utils/component_library.py — Thư viện cấu kiện dùng chung (mố / trụ / dầm / móng).

Lưu/đọc bền vững ra JSON tại  Data/Library/components.json  để add/edit của
người dùng giữ được sau khi tắt app, dùng CHUNG cho cả 3 phương án.

Module thuần Python (không phụ thuộc Streamlit) — chỉ I/O + schema + seed.
Tên trường (field) cố tình đặt khớp schema app đang dùng (kcn_result / tru_result /
mong_result) để Phase 2 ghép cấu kiện vào 3D / bố trí chung được dễ dàng.
"""
import os
import re
import json
import base64
import unicodedata
import copy
import urllib.request
import urllib.error

# ── Đường dẫn lưu trữ ────────────────────────────────────────────────────────
_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
_ROOT        = os.path.dirname(_THIS_DIR)                       # gốc dự án
LIBRARY_DIR  = os.path.join(_ROOT, "Data", "Library")
LIBRARY_PATH = os.path.join(LIBRARY_DIR, "components.json")

VERSION = 1
COMPONENT_TYPES = ("dam", "tru", "mo", "mong")


# ══════════════════════════════════════════════════════════════════════════
# TỰ ĐỘNG LƯU LÊN GITHUB (tùy chọn) — cấu hình qua st.secrets hoặc biến môi
# trường: GITHUB_TOKEN, GITHUB_REPO ("owner/name"), GITHUB_BRANCH (mặc định
# "main"). Không cấu hình → chỉ lưu file cục bộ (hành vi cũ).
# ══════════════════════════════════════════════════════════════════════════
def _gh_config() -> dict:
    cfg = {}
    try:
        import streamlit as st          # ưu tiên Streamlit secrets
        for k in ("GITHUB_TOKEN", "GITHUB_REPO", "GITHUB_BRANCH"):
            try:
                if k in st.secrets:
                    cfg[k] = st.secrets[k]
            except Exception:
                pass
    except Exception:
        pass
    for k in ("GITHUB_TOKEN", "GITHUB_REPO", "GITHUB_BRANCH"):
        cfg.setdefault(k, os.environ.get(k))
    return cfg


def github_enabled() -> bool:
    c = _gh_config()
    return bool(c.get("GITHUB_TOKEN") and c.get("GITHUB_REPO"))


def commit_file_to_github(relpath: str, content_bytes: bytes,
                          message: str) -> tuple:
    """Commit/cập nhật 1 file lên GitHub qua Contents API.
    Trả về (ok: bool, thông điệp: str). Best-effort, không raise."""
    c = _gh_config()
    token  = c.get("GITHUB_TOKEN")
    repo   = c.get("GITHUB_REPO")
    branch = c.get("GITHUB_BRANCH") or "main"
    if not (token and repo):
        return (False, "Chưa cấu hình GITHUB_TOKEN/GITHUB_REPO")
    api = f"https://api.github.com/repos/{repo}/contents/{relpath}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-bridge-design",
    }
    sha = None                                   # SHA hiện tại (nếu file đã có)
    try:
        req = urllib.request.Request(api + f"?ref={branch}", headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read().decode()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return (False, f"GET lỗi {e.code}")
    except Exception as e:
        return (False, f"Mạng/khác: {e}")
    body = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "branch":  branch,
    }
    if sha:
        body["sha"] = sha
    try:
        req = urllib.request.Request(
            api, data=json.dumps(body).encode("utf-8"),
            headers={**headers, "Content-Type": "application/json"},
            method="PUT")
        with urllib.request.urlopen(req, timeout=20):
            return (True, "Đã đồng bộ lên GitHub")
    except urllib.error.HTTPError as e:
        return (False, f"PUT lỗi {e.code}: {e.read().decode()[:160]}")
    except Exception as e:
        return (False, f"Mạng/khác: {e}")


def _autocommit(relpath: str, content_bytes: bytes, label: str) -> None:
    """Tự commit nếu đã bật GitHub sync (best-effort, nuốt lỗi)."""
    if not github_enabled():
        return
    try:
        commit_file_to_github(relpath, content_bytes,
                              f"App tự lưu {label}")
    except Exception:
        pass

# Nhãn hiển thị cho từng loại
TYPE_LABEL = {
    "dam":  "Dầm",
    "tru":  "Trụ",
    "mo":   "Mố",
    "mong": "Móng",
}

# Schema từng loại — thứ tự trường = thứ tự cột trong bảng edit
SCHEMA = {
    "dam":  ["ten", "loai_dam", "chieu_dai", "chieu_cao",
             "khoang_cach_dam", "so_luong_dam", "be_rong_canh", "ghi_chu"],
    "tru":  ["ten", "loai_tru", "B_tru", "D_than", "H_than",
             "be_rong_xa_mu", "ghi_chu"],
    "mo":   ["ten", "loai_mo", "chieu_cao", "be_rong",
             "be_day_tuong", "ghi_chu"],
    "mong": ["ten", "loai_mong", "duong_kinh_coc", "so_coc",
             "chieu_dai_coc", "ghi_chu"],
}

# Trường số (numeric) — dùng để cấu hình cột & ép kiểu khi lưu
NUMERIC_FIELDS = {
    "dam":  ["chieu_dai", "chieu_cao", "khoang_cach_dam", "so_luong_dam", "be_rong_canh"],
    "tru":  ["B_tru", "D_than", "H_than", "be_rong_xa_mu"],
    "mo":   ["chieu_cao", "be_rong", "be_day_tuong"],
    "mong": ["duong_kinh_coc", "so_coc", "chieu_dai_coc"],
}

# Nhãn cột tiếng Việt (dùng cho st.column_config bên Interface)
FIELD_LABEL = {
    "ten":             "Tên cấu kiện",
    "loai_dam":        "Loại dầm",
    "loai_tru":        "Loại trụ",
    "loai_mo":         "Loại mố",
    "loai_mong":       "Loại móng",
    "chieu_dai":       "L nhịp (m)",
    "chieu_cao":       "Chiều cao (m)",
    "khoang_cach_dam": "K/c dầm (m)",
    "so_luong_dam":    "Số dầm",
    "be_rong_canh":    "B cánh (m)",
    "B_tru":           "B trụ (m)",
    "D_than":          "D thân (m)",
    "H_than":          "H thân (m)",
    "be_rong_xa_mu":   "B xà mũ (m)",
    "be_rong":         "Bề rộng (m)",
    "be_day_tuong":    "Bề dày tường (m)",
    "duong_kinh_coc":  "D cọc (m)",
    "so_coc":          "Số cọc",
    "chieu_dai_coc":   "L cọc (m)",
    "ghi_chu":         "Ghi chú",
}

# Tuỳ chọn cho cột "loại" (selectbox) — đồng bộ với DS.dam_color / mong_color
LOAI_OPTIONS = {
    "loai_dam":  ["Super-T", "Dầm I", "T ngược", "Bản rỗng", "Khác"],
    "loai_tru":  ["Trụ thân đặc", "Trụ thân cột", "Trụ thân hẹp", "Khác"],
    "loai_mo":   ["Mố chữ U", "Mố vùi", "Mố chữ nhật", "Khác"],
    "loai_mong": ["Cọc khoan nhồi", "Cọc ép", "Móng nông", "Khác"],
}


# ── Tiện ích ─────────────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    """Chuỗi → slug ASCII không dấu, dùng làm id ổn định."""
    text = str(text or "").strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("đ", "d").replace("Đ", "D")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "ck"


def _rec(ctype: str, ten: str, **fields) -> dict:
    """Tạo 1 bản ghi cấu kiện đầy đủ trường theo schema."""
    base = {k: "" for k in SCHEMA[ctype]}
    base["ten"] = ten
    base.update(fields)
    base["id"]    = slugify(ten)
    base["nguon"] = fields.get("nguon", "mặc định")
    return base


# ── Dữ liệu mẫu mặc định ─────────────────────────────────────────────────────
def default_library() -> dict:
    """Thư viện seed ban đầu — vài mẫu phổ biến cho mỗi loại."""
    dam = [
        _rec("dam", "Super-T 38m", loai_dam="Super-T", chieu_dai=38.2,
             chieu_cao=1.75, khoang_cach_dam=2.2, so_luong_dam=5,
             be_rong_canh=1.20, ghi_chu="Nhịp giản đơn phổ biến"),
        _rec("dam", "Super-T 24m", loai_dam="Super-T", chieu_dai=24.7,
             chieu_cao=1.20, khoang_cach_dam=2.0, so_luong_dam=6,
             be_rong_canh=1.00, ghi_chu=""),
        _rec("dam", "Dầm I 33m", loai_dam="Dầm I", chieu_dai=33.0,
             chieu_cao=1.65, khoang_cach_dam=2.4, so_luong_dam=5,
             be_rong_canh=0.65, ghi_chu=""),
        _rec("dam", "Bản rỗng 18m", loai_dam="Bản rỗng", chieu_dai=18.0,
             chieu_cao=0.90, khoang_cach_dam=0.0, so_luong_dam=1,
             be_rong_canh=0.0, ghi_chu="Bản rỗng đổ tại chỗ"),
    ]
    tru = [
        _rec("tru", "Trụ thân đặc", loai_tru="Trụ thân đặc", B_tru=1.6,
             D_than=1.2, H_than=8.0, be_rong_xa_mu=2.0, ghi_chu="H ≤ 10m"),
        _rec("tru", "Trụ 2 cột", loai_tru="Trụ thân cột", B_tru=1.2,
             D_than=1.0, H_than=9.0, be_rong_xa_mu=1.8,
             ghi_chu="Trụ thân cột tròn/đa giác"),
        _rec("tru", "Trụ thân hẹp", loai_tru="Trụ thân hẹp", B_tru=1.0,
             D_than=0.8, H_than=7.0, be_rong_xa_mu=1.6, ghi_chu=""),
    ]
    mo = [
        _rec("mo", "Mố chữ U", loai_mo="Mố chữ U", chieu_cao=6.0,
             be_rong=10.0, be_day_tuong=0.5, ghi_chu="Mố trọng lực chữ U"),
        _rec("mo", "Mố vùi", loai_mo="Mố vùi", chieu_cao=4.0,
             be_rong=9.0, be_day_tuong=0.4, ghi_chu=""),
    ]
    mong = [
        _rec("mong", "Cọc khoan nhồi D1.0", loai_mong="Cọc khoan nhồi",
             duong_kinh_coc=1.0, so_coc=6, chieu_dai_coc=30.0,
             ghi_chu="Đất yếu, tải lớn"),
        _rec("mong", "Cọc ép D0.4", loai_mong="Cọc ép",
             duong_kinh_coc=0.4, so_coc=12, chieu_dai_coc=20.0, ghi_chu=""),
        _rec("mong", "Móng nông", loai_mong="Móng nông",
             duong_kinh_coc=0.0, so_coc=0, chieu_dai_coc=0.0,
             ghi_chu="Nền đá / đất tốt"),
    ]
    return {"version": VERSION, "dam": dam, "tru": tru, "mo": mo, "mong": mong}


# ── Chuẩn hoá / validate ─────────────────────────────────────────────────────
def _coerce_record(ctype: str, rec: dict) -> dict:
    """Đảm bảo bản ghi có đủ trường schema + ép kiểu số."""
    out = {k: rec.get(k, "") for k in SCHEMA[ctype]}
    for f in NUMERIC_FIELDS[ctype]:
        v = out.get(f, "")
        try:
            out[f] = float(v) if v not in ("", None) else 0.0
        except (TypeError, ValueError):
            out[f] = 0.0
    out["ten"]   = str(out.get("ten", "") or "").strip()
    out["id"]    = slugify(rec.get("id") or out["ten"])
    out["nguon"] = rec.get("nguon", "người dùng")
    return out


def normalize(lib: dict) -> dict:
    """Bảo đảm dict thư viện đủ 4 loại, mỗi bản ghi đủ trường."""
    lib = dict(lib or {})
    out = {"version": VERSION}
    for ctype in COMPONENT_TYPES:
        rows = lib.get(ctype) or []
        out[ctype] = [_coerce_record(ctype, r) for r in rows if isinstance(r, dict)]
    return out


# ── I/O ──────────────────────────────────────────────────────────────────────
def _ensure_dir() -> None:
    os.makedirs(LIBRARY_DIR, exist_ok=True)


def load_library() -> dict:
    """Đọc thư viện từ JSON; nếu chưa có file → seed mặc định & ghi ra đĩa."""
    if os.path.exists(LIBRARY_PATH):
        try:
            with open(LIBRARY_PATH, "r", encoding="utf-8") as f:
                return normalize(json.load(f))
        except (OSError, json.JSONDecodeError):
            pass  # file hỏng → rơi xuống seed mặc định
    lib = default_library()
    try:
        save_library(lib)
    except OSError:
        pass
    return lib


def save_library(lib: dict) -> None:
    """Ghi thư viện ra JSON (UTF-8, giữ dấu tiếng Việt) + tự đồng bộ GitHub."""
    _ensure_dir()
    data = normalize(lib)
    _txt = json.dumps(data, ensure_ascii=False, indent=2)
    with open(LIBRARY_PATH, "w", encoding="utf-8") as f:
        f.write(_txt)
    _autocommit("Data/Library/components.json", _txt.encode("utf-8"),
                "thư viện cấu kiện")


def records_for(lib: dict, ctype: str) -> list:
    """Danh sách bản ghi của 1 loại (copy an toàn)."""
    return copy.deepcopy((lib or {}).get(ctype, []))


# ══════════════════════════════════════════════════════════════════════════
# KHO DẦM (BEAMS) — mỗi dầm là 1 định nghĩa đầy đủ (mặt cắt CAD + đoạn),
# tạo qua luồng "Chi tiết dầm". Lưu riêng vì cấu trúc khác bảng tham số.
# Mỗi bản ghi:
#   { id, ten, loai_dam, sections:{name:{outer,holes}}, segs:[...],
#     fill_sec, nguon, created_by, updated_at }
# ══════════════════════════════════════════════════════════════════════════
BEAMS_PATH = os.path.join(LIBRARY_DIR, "beams.json")


def load_beams() -> list:
    """Đọc danh sách dầm trong thư viện (list). Thiếu file → [] (chưa có dầm)."""
    if os.path.exists(BEAMS_PATH):
        try:
            with open(BEAMS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            beams = data.get("beams", []) if isinstance(data, dict) else data
            return [b for b in beams if isinstance(b, dict)]
        except (OSError, json.JSONDecodeError):
            pass
    return []


def save_beams(beams: list) -> None:
    """Ghi danh sách dầm ra JSON (UTF-8, giữ dấu) + tự đồng bộ GitHub."""
    _ensure_dir()
    _txt = json.dumps({"version": VERSION, "beams": list(beams or [])},
                      ensure_ascii=False, indent=2)
    with open(BEAMS_PATH, "w", encoding="utf-8") as f:
        f.write(_txt)
    _autocommit("Data/Library/beams.json", _txt.encode("utf-8"),
                "thư viện dầm")


def make_beam_id(ten: str, existing: list = None) -> str:
    """Sinh id duy nhất từ tên dầm (tránh trùng với danh sách hiện có)."""
    base = slugify(ten)
    existing_ids = {b.get("id") for b in (existing or [])}
    if base not in existing_ids:
        return base
    i = 2
    while f"{base}-{i}" in existing_ids:
        i += 1
    return f"{base}-{i}"


def upsert_beam(beams: list, beam: dict) -> list:
    """Thêm mới hoặc cập nhật 1 dầm theo id; trả về list mới."""
    out = [b for b in (beams or []) if b.get("id") != beam.get("id")]
    out.append(beam)
    return out


def delete_beam(beams: list, beam_id: str) -> list:
    return [b for b in (beams or []) if b.get("id") != beam_id]


def get_beam(beams: list, beam_id: str):
    return next((b for b in (beams or []) if b.get("id") == beam_id), None)
