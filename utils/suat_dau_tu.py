"""
utils/suat_dau_tu.py — Suất vốn đầu tư xây dựng công trình cầu (Bảng 76,
QĐ 409/… về suất vốn đầu tư công trình giao thông).

Dùng để ƯỚC giá trị công trình cầu = suất vốn đầu tư × diện tích mặt cầu.

Đơn vị gốc bảng: "1.000 đ/m²"; giá trị in trong bảng (vd 21.597) dùng dấu "."
là phân cách hàng nghìn → 21.597 (nghìn đ/m²) = 21,597,000 đ/m² = 21.597 TRIỆU
đ/m². Vì vậy ở đây lưu trực tiếp theo **triệu đồng/m²** (số khớp y hệt bảng):
    giá trị (triệu đ) = suat_trieu_m2 × diện_tích_mặt_cầu (m²)

Module thuần Python (không phụ thuộc Streamlit) — dễ kiểm thử & tái dùng.
"""

# ── Bảng 76: mỗi dòng 1 loại kết cấu cầu ─────────────────────────────────────
# nhom    : nhãn nhóm chiều dài nhịp (hiển thị)
# suat    : suất vốn đầu tư (triệu đ/m²)  ·  cp_xd: chi phí xây dựng (triệu đ/m²)
# cp_tb   : chi phí thiết bị (triệu đ/m², 0 nếu bảng để trống)
# match   : tiêu chí tự khớp {bo_hanh, dam, mong, L_min, L_max} (m)
#   dam  ∈ {ban_mo_nhe, dam_t_thuong, dam_ban_dul, i_t_supert, dam_hop, dan_thep}
#   mong ∈ {nong, coc, khoan_nhoi}  (None = không xét)
SUAT_DAU_TU = [
    {"code": "14210.01", "nhom": "< 15m",
     "ten": "Cầu bản mố nhẹ, móng nông, HL93, L= 9m",
     "suat": 21.597, "cp_xd": 20.238, "cp_tb": 0.0,
     "match": {"bo_hanh": False, "dam": "ban_mo_nhe", "mong": "nong",
               "L_min": 0.0, "L_max": 12.0}},
    {"code": "14210.02", "nhom": "< 15m",
     "ten": "Cầu dầm T BTCT thường, móng nông, HL93, 9m < L ≤ 15m",
     "suat": 20.923, "cp_xd": 19.610, "cp_tb": 0.0,
     "match": {"bo_hanh": False, "dam": "dam_t_thuong", "mong": "nong",
               "L_min": 9.0, "L_max": 15.0}},
    {"code": "14210.03", "nhom": "< 15m",
     "ten": "Cầu dầm bản BTCT DƯL, móng nông, HL93, 12m < L ≤ 15m",
     "suat": 25.238, "cp_xd": 23.663, "cp_tb": 0.0,
     "match": {"bo_hanh": False, "dam": "dam_ban_dul", "mong": "nong",
               "L_min": 12.0, "L_max": 15.0}},
    {"code": "14210.04", "nhom": "< 15m",
     "ten": "Cầu dầm T BTCT thường, móng cọc BTCT, HL93, 9m < L ≤ 15m",
     "suat": 26.482, "cp_xd": 24.816, "cp_tb": 0.0,
     "match": {"bo_hanh": False, "dam": "dam_t_thuong", "mong": "coc",
               "L_min": 9.0, "L_max": 15.0}},
    {"code": "14210.05", "nhom": "< 15m",
     "ten": "Cầu dầm bản BTCT DƯL, móng cọc BTCT, HL93, 12m < L ≤ 15m",
     "suat": 31.813, "cp_xd": 29.815, "cp_tb": 0.0,
     "match": {"bo_hanh": False, "dam": "dam_ban_dul", "mong": "coc",
               "L_min": 12.0, "L_max": 15.0}},
    {"code": "14210.06", "nhom": "15 ÷ 25m",
     "ten": "Cầu dầm bản BTCT DƯL, móng nông, HL93, 15m < L < 24m",
     "suat": 28.354, "cp_xd": 26.573, "cp_tb": 0.0,
     "match": {"bo_hanh": False, "dam": "dam_ban_dul", "mong": "nong",
               "L_min": 15.0, "L_max": 24.0}},
    {"code": "14210.07", "nhom": "15 ÷ 25m",
     "ten": "Cầu dầm bản BTCT DƯL, móng cọc BTCT, HL93, 15m < L < 24m",
     "suat": 30.169, "cp_xd": 28.263, "cp_tb": 0.0,
     "match": {"bo_hanh": False, "dam": "dam_ban_dul", "mong": "coc",
               "L_min": 15.0, "L_max": 24.0}},
    {"code": "14210.08", "nhom": "25 ÷ 50m",
     "ten": "Cầu dầm I, T, Super-T BTCT DƯL, móng nông, HL93, L < 40m",
     "suat": 35.009, "cp_xd": 32.806, "cp_tb": 0.0,
     "match": {"bo_hanh": False, "dam": "i_t_supert", "mong": "nong",
               "L_min": 24.0, "L_max": 40.0}},
    {"code": "14210.09", "nhom": "25 ÷ 50m",
     "ten": "Cầu dầm I, T, Super-T BTCT DƯL, móng cọc BTCT, HL93, L < 40m",
     "suat": 39.883, "cp_xd": 37.372, "cp_tb": 0.0,
     "match": {"bo_hanh": False, "dam": "i_t_supert", "mong": "coc",
               "L_min": 24.0, "L_max": 50.0}},
    {"code": "14210.10", "nhom": "50 ÷ 100m",
     "ten": "Cầu dầm hộp BTCT DƯL đúc hẫng, móng cọc khoan nhồi, HL93, L < 100m",
     "suat": 46.424, "cp_xd": 43.501, "cp_tb": 0.0,
     "match": {"bo_hanh": False, "dam": "dam_hop", "mong": "khoan_nhoi",
               "L_min": 50.0, "L_max": 100.0}},
    {"code": "14210.11", "nhom": "Bộ hành 25 ÷ 50m",
     "ten": "Cầu bộ hành vượt đường, dầm dàn thép, rộng 3m, 30m < L < 50m",
     "suat": 84.640, "cp_xd": 68.876, "cp_tb": 0.0,
     "match": {"bo_hanh": True, "dam": "dan_thep", "mong": None,
               "L_min": 30.0, "L_max": 50.0}},
]

CODE_INDEX = {r["code"]: r for r in SUAT_DAU_TU}


def get_row(code: str):
    """Trả bản ghi suất theo mã (None nếu không có)."""
    return CODE_INDEX.get(code)


# ── Phân loại đầu vào ────────────────────────────────────────────────────────
def classify_dam(loai_dam: str) -> str:
    """Quy loại dầm thực tế → nhóm trong bảng suất."""
    s = str(loai_dam or "").lower()
    if "hộp" in s or "hop" in s:
        return "dam_hop"
    if "dàn" in s or "dan thep" in s or "thép" in s and "dàn" in s:
        return "dan_thep"
    if "bản" in s or "ban rong" in s or "bản rỗng" in s:
        return "dam_ban_dul"
    if "super" in s or "super-t" in s or "dầm i" in s or "dam i" in s \
            or s.strip() in ("i", "t") or "dầm t" in s or "dam t" in s:
        return "i_t_supert"
    return "i_t_supert"          # mặc định cho dầm BTCT DƯL phổ biến


def classify_mong(loai_mong: str) -> str:
    """Quy loại móng thực tế → {nong, coc, khoan_nhoi}."""
    s = str(loai_mong or "").lower()
    if "nông" in s or "nong" in s:
        return "nong"
    if "khoan nhồi" in s or "khoan nhoi" in s:
        return "khoan_nhoi"
    if "cọc" in s or "coc" in s or "ép" in s or "ep" in s:
        return "coc"
    return "coc"                 # mặc định: móng cọc (phổ biến)


# ── Tự khớp dòng suất phù hợp ────────────────────────────────────────────────
def suggest(loai_dam: str = "", loai_mong: str = "", L_nhip: float = 0.0,
            bo_hanh: bool = False) -> str:
    """Chọn MÃ suất phù hợp nhất theo loại dầm/móng + chiều dài nhịp L (m).

    Trả mã (str). Khớp theo điểm: ưu tiên đúng nhóm L, rồi loại dầm, rồi móng.
    """
    if bo_hanh:
        return "14210.11"
    dam = classify_dam(loai_dam)
    mong = classify_mong(loai_mong)
    L = float(L_nhip or 0.0)

    # Cầu lớn nhịp >50m → dầm hộp đúc hẫng (móng khoan nhồi)
    if L >= 50.0 or dam == "dam_hop":
        return "14210.10"

    # Với nhịp < 50m, cọc khoan nhồi vẫn xếp nhóm "móng cọc" (bảng chỉ tách
    # nông/cọc; khoan_nhoi riêng chỉ dùng cho dầm hộp ở 14210.10).
    if mong == "khoan_nhoi":
        mong = "coc"

    best, best_score = None, -1
    for r in SUAT_DAU_TU:
        m = r["match"]
        if m["bo_hanh"]:
            continue
        score = 0
        # 1) Trong dải chiều dài nhịp → +3
        if m["L_min"] <= L <= m["L_max"]:
            score += 3
        else:                                   # gần dải → +1 (khoảng đệm 3m)
            if (m["L_min"] - 3.0) <= L <= (m["L_max"] + 3.0):
                score += 1
        # 2) Đúng nhóm dầm → +2 (i_t_supert ~ dam_ban_dul cùng họ DƯL → +1)
        if m["dam"] == dam:
            score += 2
        elif {m["dam"], dam} <= {"i_t_supert", "dam_ban_dul"}:
            score += 1
        # 3) Đúng loại móng → +2
        if m["mong"] == mong:
            score += 2
        if score > best_score:
            best_score, best = score, r["code"]
    return best or "14210.09"


# ── Tính giá trị công trình ──────────────────────────────────────────────────
def deck_area(length_m: float, width_m: float) -> float:
    """Diện tích mặt cầu (m²) = chiều dài cầu × bề rộng cầu."""
    return max(0.0, float(length_m or 0.0)) * max(0.0, float(width_m or 0.0))


def compute(area_m2: float, code: str) -> dict:
    """Giá trị công trình theo suất đầu tư.

    Trả dict (triệu đồng): {suat, cp_xd, cp_tb, area, gia_tri, gia_tri_xd,
    gia_tri_tb}. gia_tri = suat × diện tích.
    """
    r = get_row(code) or {}
    a = max(0.0, float(area_m2 or 0.0))
    suat = float(r.get("suat", 0.0))
    cp_xd = float(r.get("cp_xd", 0.0))
    cp_tb = float(r.get("cp_tb", 0.0))
    return {
        "code": code, "ten": r.get("ten", ""), "nhom": r.get("nhom", ""),
        "area": a, "suat": suat, "cp_xd": cp_xd, "cp_tb": cp_tb,
        "gia_tri":    round(suat * a, 1),       # triệu đồng
        "gia_tri_xd": round(cp_xd * a, 1),
        "gia_tri_tb": round(cp_tb * a, 1),
    }
