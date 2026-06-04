"""
Module 08 — Móng cầu (Foundation Advisor)
Căn cứ:
  - TCVN 10304:2014   Móng cọc — tiêu chuẩn thiết kế
  - TCVN 11823-2017   Thiết kế cầu đường bộ
  - Kinh nghiệm thực tế các dự án cầu VN

Gồm 2 lớp:
  1. Rule-Based nâng cao — dùng ngay, không cần dữ liệu
  2. AI model (Random Forest trên dataset tổng hợp) — khung cho tương lai:
     khi có dữ liệu dự án thực, thay thế bằng dữ liệu đó để cải thiện độ chính xác.

Ba loại cọc và tiêu chí lựa chọn
─────────────────────────────────
• Cọc khoan nhồi (CKN):
    - Chiều dài cọc ước tính > 50m (lớp đất tốt quá sâu)
    - Đường kính cần ≥ 800mm (tải trọng lớn)
    - Sông lớn (cấp I–II) + H_trụ > 5m
• Cọc ép BTCT DƯL:
    - Khu vực đông dân cư (hạn chế tiếng ồn/rung)
    - Đường kính ≤ 500mm (có thể ép được)
• Cọc đóng BTCT DƯL:
    - Không phải khu đông dân, chiều dài ≤ 50m, D < 800mm
    - Kinh tế, thi công nhanh
"""

import numpy as np
import pandas as pd

# ── Bảng tra đường kính cọc ──────────────────────────────────────────────────
# loai_song → (D tại H≤4m, D tại 4<H≤8m, D tại H>8m) [mm]
_D_COC_TABLE = {
    "sông_lớn":  (800,  1000, 1200),   # Cấp I, II
    "sông_vừa":  (600,  800,  1000),   # Cấp III, IV
    "sông_nhỏ":  (500,  600,  800),    # Cấp V, VI
}

# Đường kính → (L_min, L_max) chiều dài cọc gợi ý [m] (ĐBSCL/Đông Nam Bộ)
_L_COC_TABLE = {
    400:  (20, 30),
    500:  (28, 38),
    600:  (32, 45),
    800:  (38, 52),
    1000: (45, 60),
    1200: (50, 65),
    1500: (55, 70),
}

# Đường kính → (N_min, N_max) số cọc/bệ gợi ý
_SO_COC_TABLE = {
    400:  (4, 6),
    500:  (4, 8),
    600:  (4, 8),
    800:  (4, 9),
    1000: (4, 9),
    1200: (4, 6),
    1500: (2, 4),
}


def _cap_song_to_int(cap_song):
    """'VI' → 6, 'I' → 1, '6' → 6 v.v."""
    cap_map = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
    s = str(cap_song).strip().upper()
    if s.isdigit():
        return int(s)
    return cap_map.get(s, 4)


def _chon_loai_song(cap_int, is_river):
    if not is_river:
        return "sông_vừa"   # mặc định (đề tài chỉ vượt sông)
    if cap_int <= 2:
        return "sông_lớn"
    elif cap_int <= 4:
        return "sông_vừa"
    return "sông_nhỏ"


def _chon_D_coc(loai_song, H_tru):
    row = _D_COC_TABLE[loai_song]
    if H_tru <= 4:
        return row[0]
    elif H_tru <= 8:
        return row[1]
    return row[2]


def _chon_loai_coc(D_coc_mm, loai_song, H_tru, L_coc_max, is_urban):
    """
    Quyết định loại cọc dựa trên 3 tiêu chí:

    1. L_coc_max > 50m → CKN (lớp đất tốt quá sâu, cọc đóng/ép không hiệu quả)
    2. is_urban → cọc ép (hạn chế tiếng ồn/rung trong khu đông dân cư)
                  ngoại lệ: D > 500mm không ép được → CKN thay thế
    3. Còn lại  → cọc đóng (kinh tế, tốc độ thi công nhanh)
                  ngoại lệ: D ≥ 800mm hoặc sông lớn + H_tru > 5m → CKN
    """
    if L_coc_max > 50:
        return (
            "Cọc khoan nhồi",
            "Khoan nhồi bùn khoan (bentonite) hoặc vách ống chống thép"
        )
    if is_urban:
        if D_coc_mm <= 500:
            return (
                "Cọc ép BTCT DƯL",
                "Ép tĩnh (ép neo hoặc ép robot) — hạn chế tiếng ồn/rung"
            )
        else:
            return (
                "Cọc khoan nhồi",
                "Khoan nhồi (thay thế cọc ép vì D > 500mm)"
            )
    if D_coc_mm >= 800 or (loai_song == "sông_lớn" and H_tru > 5):
        return (
            "Cọc khoan nhồi",
            "Khoan nhồi bùn khoan (bentonite) hoặc vách ống chống thép"
        )
    return (
        "Cọc đóng BTCT DƯL",
        "Đóng búa diesel hoặc búa rung — kinh tế, thi công nhanh"
    )


# ===========================================================================
# AI MODEL — Khung Random Forest trên dữ liệu tổng hợp
# ===========================================================================
def _generate_synthetic_data(n=600, seed=42):
    """
    Tạo dataset tổng hợp để huấn luyện AI chọn loại cọc.
    Label được gán theo quy tắc kỹ thuật (_chon_loai_coc).
    Khi có dữ liệu dự án thực, thay thế hàm này.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        H_tru     = float(rng.uniform(2, 16))
        cap_int   = int(rng.integers(1, 7))
        is_river  = int(rng.integers(0, 2))
        is_urban  = int(rng.integers(0, 2))
        loai_song = _chon_loai_song(cap_int, bool(is_river))
        D_mm      = _chon_D_coc(loai_song, H_tru)
        L_est     = float(rng.uniform(20, 70))   # chiều dài cọc ước tính

        loai, _ = _chon_loai_coc(D_mm, loai_song, H_tru, L_est, bool(is_urban))
        rows.append({
            "H_tru": H_tru, "D_coc_mm": D_mm, "is_urban": is_urban,
            "cap_int": cap_int, "is_river": is_river, "L_coc_est": L_est,
            "Loai_coc": loai,
        })
    return pd.DataFrame(rows)


def train_foundation_ai():
    """
    Huấn luyện Random Forest phân loại loại cọc.
    Dùng dataset tổng hợp từ quy tắc kỹ thuật.
    Trả về dict models (dùng với predict_foundation_ai).
    """
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import LabelEncoder
    except ImportError:
        return None

    df = _generate_synthetic_data()
    feat_cols = ["H_tru", "D_coc_mm", "is_urban", "cap_int", "is_river", "L_coc_est"]
    X = df[feat_cols]
    y = df["Loai_coc"]

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    clf = RandomForestClassifier(
        n_estimators=300, max_depth=8, min_samples_leaf=2,
        class_weight="balanced", random_state=42
    )
    clf.fit(X, y_enc)

    return {
        "clf":       clf,
        "le":        le,
        "feat_cols": feat_cols,
        "classes":   list(le.classes_),
        "note":      "Học từ dữ liệu tổng hợp theo TCVN 10304. Thay bằng dữ liệu thực khi có.",
    }


def predict_foundation_ai(models, H_tru, D_coc_mm, is_urban, cap_int, is_river, L_coc_est):
    """Dự đoán loại cọc bằng AI model, trả về (loai, xac_suat%)."""
    if models is None:
        return None, 0.0
    try:
        X_row = [[H_tru, D_coc_mm, is_urban, cap_int, is_river, L_coc_est]]
        idx   = models["clf"].predict(X_row)[0]
        proba = models["clf"].predict_proba(X_row)[0]
        loai  = models["le"].inverse_transform([idx])[0]
        conf  = float(proba.max()) * 100
        return loai, conf
    except Exception:
        return None, 0.0


# ===========================================================================
# HÀM CHÍNH
# ===========================================================================
def predict_foundation(H_tru, loai_tru, is_river, cap_song,
                       B_cau=None, vtk=None, L_nhip=None,
                       is_urban=0, foundation_models=None):
    """
    Gợi ý loại móng và thông số cọc.

    Params
    ------
    H_tru            : Chiều cao thân trụ (m)
    loai_tru         : Loại trụ đã xác định ('Khung 2 cột', 'Trụ đặc', ...)
    is_river         : 1 nếu vượt sông
    cap_song         : Cấp sông ('I'–'VI' hoặc '1'–'6')
    B_cau            : Bề rộng cầu (m)
    vtk              : Vận tốc thiết kế (km/h)
    L_nhip           : Chiều dài nhịp (m)
    is_urban         : 1 nếu khu vực đông dân cư (hạn chế tiếng ồn/rung)
    foundation_models: Dict từ train_foundation_ai() (tùy chọn)

    Returns
    -------
    dict đầy đủ thông số móng cọc
    """
    cap_int   = _cap_song_to_int(cap_song) if cap_song else 4
    loai_song = _chon_loai_song(cap_int, bool(is_river))

    H = float(H_tru) if H_tru else 5.0
    D_coc = _chon_D_coc(loai_song, H)

    # Tra bảng chiều dài và số cọc
    L_range = _L_COC_TABLE.get(D_coc, (38, 52))
    N_range = _SO_COC_TABLE.get(D_coc, (4, 9))

    # Điều chỉnh khi trụ rất cao
    if H > 10:
        L_range = (L_range[1], L_range[1] + 10)
        N_range = (N_range[0] + 2, N_range[1] + 2)

    L_coc_est = L_range[1]   # dùng giá trị max để quyết định loại cọc

    # ── Chọn loại cọc ──────────────────────────────────────────────────────
    loai_mong_rb, pp_rb = _chon_loai_coc(D_coc, loai_song, H, L_coc_est, bool(is_urban))

    # Thử dùng AI (nếu có model)
    loai_mong_ai, conf_ai = predict_foundation_ai(
        foundation_models, H, D_coc, is_urban, cap_int, int(bool(is_river)), L_coc_est
    )

    if loai_mong_ai is not None and conf_ai >= 60:
        loai_mong  = loai_mong_ai
        phuong_phap = pp_rb   # giữ mô tả thi công từ RB (phù hợp loại)
        # Điều chỉnh mô tả theo AI nếu loại khác
        if loai_mong_ai != loai_mong_rb:
            _, phuong_phap = _chon_loai_coc(D_coc, loai_song, H, L_coc_est, bool(is_urban))
        do_tin_cay_txt = f"AI {conf_ai:.0f}%"
    else:
        loai_mong   = loai_mong_rb
        phuong_phap = pp_rb
        do_tin_cay_txt = "Quy tắc kỹ thuật"

    # ── Gợi ý kích thước bệ cọc ────────────────────────────────────────────
    D_m = D_coc / 1000.0
    if N_range[0] <= 4:
        be_goi_y = (
            f"{round(D_m*2 + 1.0, 1)} × {round(D_m*2 + 1.0, 1)} × "
            f"{round(1.2 + D_m, 1)} m (bệ 4 cọc)"
        )
    else:
        be_goi_y = (
            f"≥ {round(D_m*3 + 1.0, 1)} m (dọc cầu) × "
            f"B_cầu ÷ {N_range[1]} m (ngang cầu)"
        )

    # ── Khuyến nghị kỹ thuật ───────────────────────────────────────────────
    khuyen_nghi = []
    if is_river and cap_int <= 2:
        khuyen_nghi.append(
            "Kiểm tra xói lở theo TCVN 9845:2013; bảo vệ bệ cọc bằng thảm đá / kè đá."
        )
    if H > 8:
        khuyen_nghi.append(
            "Trụ cao — cần phân tích ổn định ngang (moment lật, áp lực ngang dòng chảy)."
        )
    if is_urban and loai_mong in ("Cọc ép BTCT DƯL", "Cọc khoan nhồi"):
        khuyen_nghi.append(
            "Khu đông dân cư — ưu tiên cọc ép/khoan nhồi để hạn chế tiếng ồn và rung động."
        )
    if loai_mong == "Cọc khoan nhồi" and L_coc_est > 50:
        khuyen_nghi.append(
            f"Chiều dài cọc ước tính {L_coc_est}m — lớp đất tốt sâu, bắt buộc cọc khoan nhồi."
        )
    if not khuyen_nghi:
        khuyen_nghi.append(
            "Xác định sức chịu tải cọc theo TCVN 10304:2014 sau khi có kết quả khảo sát địa chất."
        )

    cap_lbl = ["I","II","III","IV","V","VI"]
    cap_str = cap_lbl[cap_int - 1] if 1 <= cap_int <= 6 else str(cap_int)
    ghi_chu = (
        f"[{do_tin_cay_txt}] Căn cứ TCVN 10304:2014 — "
        f"Cấp sông {cap_str}, H_trụ={H:.1f}m, loại sông={loai_song}, "
        f"{'Khu đông dân cư' if is_urban else 'Khu thông thoáng'}."
    )

    return {
        "loai_mong":            loai_mong,
        "D_coc_mm":             D_coc,
        "D_coc_chon_txt":       f"Ø{D_coc} mm",
        "L_coc_tu":             L_range[0],
        "L_coc_den":            L_range[1],
        "So_coc_tu":            N_range[0],
        "So_coc_den":           N_range[1],
        "kich_thuoc_be_goi_y":  be_goi_y,
        "phuong_phap_thi_cong": phuong_phap,
        "ghi_chu_mong":         ghi_chu,
        "khuyen_nghi":          khuyen_nghi,
    }


# ===========================================================================
# TIỆN ÍCH
# ===========================================================================
def format_mong_report(res):
    lines = [
        f"  Loại móng      : {res['loai_mong']}",
        f"  Đường kính cọc : {res['D_coc_chon_txt']}",
        f"  Chiều dài cọc  : {res['L_coc_tu']} – {res['L_coc_den']} m (gợi ý)",
        f"  Số cọc/bệ      : {res['So_coc_tu']} – {res['So_coc_den']} cọc",
        f"  Bệ cọc (gợi ý) : {res['kich_thuoc_be_goi_y']}",
        f"  Thi công       : {res['phuong_phap_thi_cong']}",
    ]
    for kn in res["khuyen_nghi"]:
        lines.append(f"  ⚠ {kn}")
    return "\n".join(lines)


# ===========================================================================
# CHẠY THỬ ĐỘC LẬP
# ===========================================================================
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print("=== Huấn luyện AI Móng cọc ===")
    mdl = train_foundation_ai()
    print(f"Model sẵn sàng: {mdl is not None}")

    test_cases = [
        {"H_tru": 5.0,  "loai_tru": "Thân cột 2 trụ", "is_river": 1, "cap_song": "VI",
         "B_cau": 12.0, "is_urban": 0},
        {"H_tru": 8.5,  "loai_tru": "Trụ đặc thân hẹp", "is_river": 1, "cap_song": "IV",
         "B_cau": 17.5, "is_urban": 0},
        {"H_tru": 4.0,  "loai_tru": "Thân cột 2 trụ", "is_river": 1, "cap_song": "VI",
         "B_cau": 12.0, "is_urban": 1},   # khu đông dân → cọc ép
        {"H_tru": 12.0, "loai_tru": "Trụ đặc thân hẹp", "is_river": 1, "cap_song": "II",
         "B_cau": 20.0, "is_urban": 0},   # sông lớn + trụ cao → CKN
    ]

    for tc in test_cases:
        res = predict_foundation(**tc, foundation_models=mdl)
        print(f"\n── H={tc['H_tru']}m | Cấp {tc['cap_song']} | urban={tc['is_urban']} ──")
        print(format_mong_report(res))
