"""
mcda/scoring_formulas.py — Công thức chấm điểm thô (thang 0–10) theo file
Tieu_chi_cham_diem_3PA_AHP.xlsx. 2 loại: threshold (ngưỡng cố định) và
minmax (chuẩn hóa min-max giữa 3 phương án).
"""


def score_threshold_khau_do(L_max, L_min):
    """A1 — Phù hợp khẩu độ: dư % = (L_max − L_min)/L_min.
    L_max < L_min → 0; dư 0–20% → 10; 20–50% → 6; >50% → 3 (dư thừa lãng phí)."""
    try:
        L_max = float(L_max); L_min = float(L_min)
    except (TypeError, ValueError):
        return 0.0
    if L_min <= 0:
        return 0.0
    if L_max < L_min:
        return 0.0
    du = (L_max - L_min) / L_min
    if du <= 0.20:
        return 10.0
    if du <= 0.50:
        return 6.0
    return 3.0


def score_threshold_LH(L, H, co_ban_day):
    """A2 — Tỉ lệ L/H: CÓ bản đáy tối ưu 20–33 →10, chấp nhận 15–36 →6, ngoài →2;
    KHÔNG bản đáy tối ưu 15–22 →10, chấp nhận 12–25 →6, ngoài →2."""
    try:
        r = float(L) / float(H)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0
    if co_ban_day:
        if 20.0 <= r <= 33.0:
            return 10.0
        if 15.0 <= r <= 36.0:
            return 6.0
        return 2.0
    if 15.0 <= r <= 22.0:
        return 10.0
    if 12.0 <= r <= 25.0:
        return 6.0
    return 2.0


def score_minmax(value, all_values, direction="smaller_better"):
    """A3/B1/B2/C2/C3 — chuẩn hóa min-max giữa các phương án.
    smaller_better: 10·(X_max − X_i)/(X_max − X_min);
    larger_better : 10·(X_i − X_min)/(X_max − X_min).
    X_max = X_min → 10 cho mọi phương án (không phân biệt được)."""
    try:
        vals = [float(v) for v in all_values if v is not None]
        x = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not vals:
        return 0.0
    x_max, x_min = max(vals), min(vals)
    if abs(x_max - x_min) < 1e-12:
        return 10.0
    if direction == "larger_better":
        return round(10.0 * (x - x_min) / (x_max - x_min), 2)
    return round(10.0 * (x_max - x) / (x_max - x_min), 2)


def score_thiet_bi_lao_lap(loai_dam):
    """C1 — Thiết bị lao lắp: dầm hộp/đúc hẫng → 4 (thiết bị nặng, phức tạp);
    Super-T → 7 (lao dầm chuyên dụng); còn lại → 10 (cẩu thường)."""
    s = str(loai_dam or "").lower()
    if "hộp" in s or "hop" in s or "đúc hẫng" in s or "duc hang" in s:
        return 4.0
    if "super" in s or "spt" in s:
        return 7.0
    return 10.0


def score_chieu_cao(H):
    """D1 — Chiều cao dầm (thanh mảnh): <0.75m →10; ≤1.20 →7; ≤1.75 →4; >1.75 →2."""
    try:
        h = float(H)
    except (TypeError, ValueError):
        return 0.0
    if h < 0.75:
        return 10.0
    if h <= 1.20:
        return 7.0
    if h <= 1.75:
        return 4.0
    return 2.0


def score_ban_day(co_ban_day):
    """D2 — Bản đáy liền mạch (nhị phân): có → 10, không → 5."""
    return 10.0 if co_ban_day else 5.0


def _sc_khau_do(pa, all_pa, crit):
    return score_threshold_khau_do(pa.get("L_max_kha_nang"), pa.get("L_min_yeu_cau"))


def _sc_ty_le_LH(pa, all_pa, crit):
    return score_threshold_LH(pa.get("L_thuc_te"), pa.get("H_dam"),
                              pa.get("co_ban_day"))


def _sc_minmax(pa, all_pa, crit):
    src = crit.get("source")
    key = src or f"manual_{crit.get('ma')}"
    return score_minmax(pa.get(key),
                        [p.get(key) for p in all_pa],
                        crit.get("direction") or "smaller_better")


def _sc_thiet_bi(pa, all_pa, crit):
    return score_thiet_bi_lao_lap(pa.get("loai_dam"))


def _sc_chieu_cao(pa, all_pa, crit):
    return score_chieu_cao(pa.get("H_dam"))


def _sc_ban_day(pa, all_pa, crit):
    return score_ban_day(pa.get("co_ban_day"))


# Bảng điều phối: scorer key (criteria_config) → hàm (pa, all_pa, crit) → 0–10
SCORERS = {
    "khau_do":  _sc_khau_do,
    "ty_le_LH": _sc_ty_le_LH,
    "minmax":   _sc_minmax,
    "thiet_bi": _sc_thiet_bi,
    "chieu_cao": _sc_chieu_cao,
    "ban_day":  _sc_ban_day,
}
