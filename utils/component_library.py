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
import unicodedata
import copy

# ── Đường dẫn lưu trữ ────────────────────────────────────────────────────────
_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
_ROOT        = os.path.dirname(_THIS_DIR)                       # gốc dự án
LIBRARY_DIR  = os.path.join(_ROOT, "Data", "Library")
LIBRARY_PATH = os.path.join(LIBRARY_DIR, "components.json")

VERSION = 1
COMPONENT_TYPES = ("dam", "tru", "mo", "mong")

# Lưu trữ HOÀN TOÀN CỤC BỘ. Người dùng tự tải thư viện về (.zip) để giữ và tự
# upload lại để dùng khi làm — không còn tự đồng bộ GitHub.

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
    "mong": ["ten", "loai_mong", "tiet_dien", "canh_b", "canh_h", "so_canh",
             "duong_kinh_coc", "so_coc", "chieu_dai_coc", "ghi_chu"],
}

# Trường số (numeric) — dùng để cấu hình cột & ép kiểu khi lưu
NUMERIC_FIELDS = {
    "dam":  ["chieu_dai", "chieu_cao", "khoang_cach_dam", "so_luong_dam", "be_rong_canh"],
    "tru":  ["B_tru", "D_than", "H_than", "be_rong_xa_mu"],
    "mo":   ["chieu_cao", "be_rong", "be_day_tuong"],
    "mong": ["canh_b", "canh_h", "so_canh", "duong_kinh_coc", "so_coc", "chieu_dai_coc"],
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
    "tiet_dien":       "Dạng mặt cắt",
    "canh_b":          "Cạnh/Ø b (mm)",
    "canh_h":          "Cạnh h (mm)",
    "so_canh":         "Số cạnh",
    "ghi_chu":         "Ghi chú",
}

# Tuỳ chọn cho cột "loại" (selectbox) — đồng bộ với DS.dam_color / mong_color
LOAI_OPTIONS = {
    "loai_dam":  ["Super-T", "Dầm I", "T ngược", "Bản rỗng", "Khác"],
    "loai_tru":  ["Trụ thân đặc", "Trụ thân cột", "Trụ thân hẹp", "Khác"],
    "loai_mo":   ["Mố chữ U", "Mố vùi", "Mố chữ nhật", "Khác"],
    "loai_mong": ["Cọc khoan nhồi", "Cọc ép", "Móng nông", "Khác"],
    "tiet_dien": ["Tròn", "Vuông", "Chữ nhật", "Đa giác đều"],
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
             tiet_dien="Tròn", canh_b=1000.0, canh_h=0.0, so_canh=0,
             duong_kinh_coc=1.0, so_coc=6, chieu_dai_coc=30.0,
             ghi_chu="Đất yếu, tải lớn"),
        _rec("mong", "Cọc ép D0.4", loai_mong="Cọc ép",
             tiet_dien="Vuông", canh_b=400.0, canh_h=0.0, so_canh=0,
             duong_kinh_coc=0.4, so_coc=12, chieu_dai_coc=20.0, ghi_chu=""),
        _rec("mong", "Móng nông", loai_mong="Móng nông",
             tiet_dien="", canh_b=0.0, canh_h=0.0, so_canh=0,
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
    """Ghi thư viện ra JSON (UTF-8, giữ dấu tiếng Việt) — chỉ lưu cục bộ."""
    _ensure_dir()
    data = normalize(lib)
    _txt = json.dumps(data, ensure_ascii=False, indent=2)
    with open(LIBRARY_PATH, "w", encoding="utf-8") as f:
        f.write(_txt)


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


# ══════════════════════════════════════════════════════════════════════════
# KHO TRỤ LẮP GHÉP (PIERS) — mỗi trụ là 1 ASSEMBLY nhiều bộ phận
# (bệ / thân / xà mũ…), mỗi bộ phận có mặt cắt + trục đùn riêng.
#   { id, ten, loai:"tru", H_ref, components:[ {ten, role, kind, ...} ],
#     created_by, updated_at }
# Lưu riêng (piers.json) vì cấu trúc khác bảng tham số components.json.
# ══════════════════════════════════════════════════════════════════════════
PIERS_PATH = os.path.join(LIBRARY_DIR, "piers.json")


def load_piers() -> list:
    """Đọc danh sách trụ lắp ghép. Thiếu file → []."""
    if os.path.exists(PIERS_PATH):
        try:
            with open(PIERS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            piers = data.get("piers", []) if isinstance(data, dict) else data
            return [p for p in piers if isinstance(p, dict)]
        except (OSError, json.JSONDecodeError):
            pass
    return []


def save_piers(piers: list) -> None:
    """Ghi danh sách trụ ra JSON + tự đồng bộ GitHub (nếu bật)."""
    _ensure_dir()
    _txt = json.dumps({"version": VERSION, "piers": list(piers or [])},
                      ensure_ascii=False, indent=2)
    with open(PIERS_PATH, "w", encoding="utf-8") as f:
        f.write(_txt)


def make_pier_id(ten: str, existing: list = None) -> str:
    base = slugify(ten) or "tru"
    existing_ids = {p.get("id") for p in (existing or [])}
    if base not in existing_ids:
        return base
    i = 2
    while f"{base}-{i}" in existing_ids:
        i += 1
    return f"{base}-{i}"


def upsert_pier(piers: list, pier: dict) -> list:
    out = [p for p in (piers or []) if p.get("id") != pier.get("id")]
    out.append(pier)
    return out


def delete_pier(piers: list, pier_id: str) -> list:
    return [p for p in (piers or []) if p.get("id") != pier_id]


def get_pier(piers: list, pier_id: str):
    return next((p for p in (piers or []) if p.get("id") == pier_id), None)


# ══════════════════════════════════════════════════════════════════════════
# KHO MỐ LẮP GHÉP (ABUTMENTS) — cùng mô hình assembly như trụ (parts:
# mũ mố / tường thân / bệ mố), lưu riêng mos.json.
# ══════════════════════════════════════════════════════════════════════════
MOS_PATH = os.path.join(LIBRARY_DIR, "mos.json")


def load_mos() -> list:
    if os.path.exists(MOS_PATH):
        try:
            with open(MOS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            mos = data.get("mos", []) if isinstance(data, dict) else data
            return [m for m in mos if isinstance(m, dict)]
        except (OSError, json.JSONDecodeError):
            pass
    return []


def save_mos(mos: list) -> None:
    _ensure_dir()
    _txt = json.dumps({"version": VERSION, "mos": list(mos or [])},
                      ensure_ascii=False, indent=2)
    with open(MOS_PATH, "w", encoding="utf-8") as f:
        f.write(_txt)


def make_mo_id(ten: str, existing: list = None) -> str:
    base = slugify(ten) or "mo"
    existing_ids = {m.get("id") for m in (existing or [])}
    if base not in existing_ids:
        return base
    i = 2
    while f"{base}-{i}" in existing_ids:
        i += 1
    return f"{base}-{i}"


def upsert_mo(mos: list, mo: dict) -> list:
    out = [m for m in (mos or []) if m.get("id") != mo.get("id")]
    out.append(mo)
    return out


def delete_mo(mos: list, mo_id: str) -> list:
    return [m for m in (mos or []) if m.get("id") != mo_id]


def get_mo(mos: list, mo_id: str):
    return next((m for m in (mos or []) if m.get("id") == mo_id), None)


# ══════════════════════════════════════════════════════════════════════════
# KHO LAN CAN / GIẢI PHÂN CÁCH (RAILINGS) — mỗi bản ghi là 1 MẶT CẮT NGANG
# (upload từ DXF) sẽ được kéo (extrude) chạy DỌC TOÀN CẦU.
#   { id, ten, loai:"lan_can"|"giai_phan_cach",
#     outer:[[y_mm,z_mm],...], holes:[[[y,z],...],...],
#     rong_mm, cao_mm, created_by }
# Hệ toạ độ mặt cắt: trục y = ngang cầu (mm), trục z = cao độ từ mặt cầu (mm).
# Lưu riêng railings.json.
# ══════════════════════════════════════════════════════════════════════════
RAILINGS_PATH = os.path.join(LIBRARY_DIR, "railings.json")

RAILING_TYPES = ("lan_can", "giai_phan_cach")
RAILING_LABEL = {"lan_can": "Lan can", "giai_phan_cach": "Giải phân cách"}


def load_railings() -> list:
    """Đọc danh sách lan can/giải phân cách. Thiếu file → []."""
    if os.path.exists(RAILINGS_PATH):
        try:
            with open(RAILINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            rows = data.get("railings", []) if isinstance(data, dict) else data
            return [r for r in rows if isinstance(r, dict)]
        except (OSError, json.JSONDecodeError):
            pass
    return []


def save_railings(railings: list) -> None:
    """Ghi danh sách lan can/giải phân cách ra JSON (chỉ lưu cục bộ)."""
    _ensure_dir()
    _txt = json.dumps({"version": VERSION, "railings": list(railings or [])},
                      ensure_ascii=False, indent=2)
    with open(RAILINGS_PATH, "w", encoding="utf-8") as f:
        f.write(_txt)


def make_railing_id(ten: str, existing: list = None) -> str:
    base = slugify(ten) or "lan-can"
    existing_ids = {r.get("id") for r in (existing or [])}
    if base not in existing_ids:
        return base
    i = 2
    while f"{base}-{i}" in existing_ids:
        i += 1
    return f"{base}-{i}"


def upsert_railing(railings: list, rail: dict) -> list:
    out = [r for r in (railings or []) if r.get("id") != rail.get("id")]
    out.append(rail)
    return out


def delete_railing(railings: list, rail_id: str) -> list:
    return [r for r in (railings or []) if r.get("id") != rail_id]


def get_railing(railings: list, rail_id: str):
    return next((r for r in (railings or []) if r.get("id") == rail_id), None)


# ══════════════════════════════════════════════════════════════════════════
# 3 THƯ VIỆN BỘ PHẬN TRỤ ĐỘC LẬP — lắp ghép khi gắn cầu:
#   caps    (xà mũ)   — schema giống DẦM: {sections, segs, fill_sec} + loft
#   stems   (thân trụ) — {section, H, flex}
#   footings(bệ trụ)  — {section, H}
# Lưu riêng caps.json / stems.json / footings.json. CRUD chung qua factory.
# ══════════════════════════════════════════════════════════════════════════
def _make_part_store(filename: str, json_key: str):
    """Tạo bộ hàm (load, save, mkid, upsert, delete, get) cho 1 kho list[dict]."""
    path = os.path.join(LIBRARY_DIR, filename)

    def _load() -> list:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                rows = data.get(json_key, []) if isinstance(data, dict) else data
                return [r for r in rows if isinstance(r, dict)]
            except (OSError, json.JSONDecodeError):
                pass
        return []

    def _save(rows: list) -> None:
        _ensure_dir()
        _txt = json.dumps({"version": VERSION, json_key: list(rows or [])},
                          ensure_ascii=False, indent=2)
        with open(path, "w", encoding="utf-8") as f:
            f.write(_txt)

    def _mkid(ten: str, existing: list = None) -> str:
        base = slugify(ten) or json_key[:3]
        ids = {r.get("id") for r in (existing or [])}
        if base not in ids:
            return base
        i = 2
        while f"{base}-{i}" in ids:
            i += 1
        return f"{base}-{i}"

    def _upsert(rows: list, rec: dict) -> list:
        out = [r for r in (rows or []) if r.get("id") != rec.get("id")]
        out.append(rec)
        return out

    def _delete(rows: list, rid: str) -> list:
        return [r for r in (rows or []) if r.get("id") != rid]

    def _get(rows: list, rid: str):
        return next((r for r in (rows or []) if r.get("id") == rid), None)

    return path, _load, _save, _mkid, _upsert, _delete, _get


(CAPS_PATH, load_caps, save_caps, make_cap_id, upsert_cap, delete_cap, get_cap
 ) = _make_part_store("caps.json", "caps")
(STEMS_PATH, load_stems, save_stems, make_stem_id, upsert_stem, delete_stem, get_stem
 ) = _make_part_store("stems.json", "stems")
(FOOTINGS_PATH, load_footings, save_footings, make_footing_id, upsert_footing,
 delete_footing, get_footing) = _make_part_store("footings.json", "footings")


# ══════════════════════════════════════════════════════════════════════════
# XUẤT / NHẬP TOÀN BỘ THƯ VIỆN — gộp các kho thành 1 bundle JSON để người dùng
# tự tải về và tự upload lại.
# ══════════════════════════════════════════════════════════════════════════
def export_bundle() -> dict:
    """Gộp toàn bộ thư viện thành 1 dict (để ghi ra 1 file JSON)."""
    return {
        "version":    VERSION,
        "kind":       "ai-bridge-library",
        "components": normalize(load_library()),
        "beams":      load_beams(),
        "piers":      load_piers(),
        "mos":        load_mos(),
        "railings":   load_railings(),
        "caps":       load_caps(),
        "stems":      load_stems(),
        "footings":   load_footings(),
    }


def import_bundle(bundle: dict) -> dict:
    """Ghi đè toàn bộ thư viện từ 1 bundle đã tải lên.
    Trả về dict {kho: số_bản_ghi} đã nạp. Bỏ qua kho thiếu trong file."""
    bundle = dict(bundle or {})
    counts = {}
    if "components" in bundle:
        lib = normalize(bundle.get("components") or {})
        save_library(lib)
        counts["components"] = sum(len(lib.get(c, [])) for c in COMPONENT_TYPES)
    for key, saver in (
        ("beams",    save_beams),
        ("piers",    save_piers),
        ("mos",      save_mos),
        ("railings", save_railings),
        ("caps",     save_caps),
        ("stems",    save_stems),
        ("footings", save_footings),
    ):
        if key in bundle:
            rows = [x for x in (bundle.get(key) or []) if isinstance(x, dict)]
            saver(rows)
            counts[key] = len(rows)
    return counts
