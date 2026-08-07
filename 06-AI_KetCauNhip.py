"""
Module 06 — AI Kết cấu nhịp (Span Structure AI)
Data  : Bridge_Train_Dataset_v3.xlsx — sheet 07_Kết cấu nhịp + 02 + 03
Features: B_tk, H_tk, Goc_xien, B_cau, Moi_truong
Labels  : Loai_dam (classifier) + L_dam, H_dam, Kc_dam, SL_dam (regressors)
Fallback: Rule-Based từ BEAM_CATALOG khi chưa có dữ liệu train

Phương án dự đoán:
  PA1 — Rule-Based tối ưu chi phí  (_predict_rb_chi_phi)
        Chỉ chọn nhóm dầm KHÔNG có bản đáy liền mạch (Dầm I / Super-T / Dầm T)
        — cấu tạo đơn giản, chi phí thấp; ưu tiên nhịp dài để giảm số nhịp.
  PA2 — Rule-Based tối ưu mỹ quan  (_predict_rb_my_quan)
        Chỉ chọn nhóm dầm CÓ bản đáy liền mạch (T ngược / Dầm bản / Bản rỗng)
        — các dầm ghép sát tạo bề mặt phẳng dưới cầu, phù hợp đô thị/cầu vượt.
  PA3 — Machine Learning + tra catalog (_predict_ml)
        Random Forest học từ Bridge_Train_Dataset_v3 (công trình cầu VN thực
        tế), được chọn bất kỳ trong 6 loại dầm — GIỮ NGUYÊN làm cơ sở so sánh
        khách quan, KHÔNG cho người dùng ghi đè.
"""

import os
import sys
import numpy as np
import pandas as pd
# sklearn NẠP LƯỜI: ~1s + 82MB RAM lúc import, chỉ cần khi HUẤN LUYỆN
# (train_kcn_ai). Module này được import lúc khởi động app → nạp ở mức module
# là mọi phiên đều trả phí dù không train. Import đặt trong hàm train_*.
import warnings
warnings.filterwarnings("ignore")

_DIR = os.path.dirname(os.path.abspath(__file__))
_V3_DEFAULT = os.path.join(_DIR, "Data", "Bridge_Train_Dataset_v3.xlsx")

# ---------------------------------------------------------------------------
# Danh sách nhịp tiêu chuẩn (m) — theo thực tế VN
STD_LENGTHS = [12, 15, 18, 21, 24, 25, 27, 30, 33, 38.2, 40]

# Khoảng an toàn mép trụ cách biên tĩnh không (m) — ĐỒNG BỘ với _PIER_SAFETY
# trong 11-BanVe_KetCau.py. Nhịp chính căng giữa tĩnh không nên phải ≥
# B_tk + 2×_PIER_SAFETY thì hai trụ kề mới không lấn vào tĩnh không.
_PIER_SAFETY = 2.0


def _L_nhip_min(B_tk, goc):
    """
    Chiều dài nhịp TỐI THIỂU để nhịp chính KHÔNG vi phạm tĩnh không.

    Ràng buộc đồng thời:
      - Hình học vượt chéo: L ≥ B_tk / sin(goc) + 2.0
      - Tĩnh không (nhịp chính căng giữa, 2 trụ ngoài biên ± _PIER_SAFETY):
        L ≥ B_tk + 2×_PIER_SAFETY
    """
    L_geo   = B_tk / np.sin(np.radians(max(goc, 30))) + 2.0
    L_clear = B_tk + 2.0 * _PIER_SAFETY
    return max(L_geo, L_clear)


# ---------------------------------------------------------------------------
# BA KHOẢNG TĨNH KHÔNG THÔNG THUYỀN — phân theo B_tk (biến trực tiếp quyết
# định chiều dài nhịp tối thiểu)
# ---------------------------------------------------------------------------
KHOANG_TINH_KHONG = {
    "nho": {
        "pham_vi":  "B_tk < 30m",
        "ten":      "Khoảng nhỏ — Dầm giản đơn tiêu chuẩn",
        "mo_ta":    ("Dầm giản đơn tiêu chuẩn (BEAM_CATALOG 28 bản ghi, nhịp "
                     "≤ 38.2m): PA1 nhóm KHÔNG bản đáy liền mạch (Dầm I / "
                     "Super-T), PA2 nhóm CÓ bản đáy liền mạch (T ngược / "
                     "Dầm bản rỗng)."),
        "trong_pham_vi_de_tai": True,
    },
    "trung": {
        "pham_vi":  "30m ≤ B_tk < 60m",
        "ten":      "Khoảng trung — Cần bổ sung catalog dầm hộp",
        "mo_ta":    ("Vượt khả năng dầm giản đơn tiêu chuẩn: PA1 Super-T MỞ "
                     "RỘNG XÀ MŨ (nới ụ giữa — kỹ thuật _spt_widen_layout "
                     "Module 11); PA2 DẦM HỘP ĐÚC HẪNG CÂN BẰNG chiều cao "
                     "biến thiên (BEAM_CATALOG_TRUNG — catalog mở rộng)."),
        "trong_pham_vi_de_tai": True,
    },
    "lon": {
        "pham_vi":  "B_tk ≥ 60m",
        "ten":      "Khoảng lớn — Vượt phạm vi đề tài",
        "mo_ta":    ("Ngoài phạm vi đề tài: chỉ ghi nhận lý thuyết (cầu dây "
                     "văng / dầm hộp lớn / extradosed), không tự động tính "
                     "toán chi tiết."),
        "trong_pham_vi_de_tai": False,
    },
}


def _phan_loai_khoang_tinh_khong(B_tk, goc):
    """
    Phân loại BA KHOẢNG tĩnh không thông thuyền theo B_tk:
      • "nho"  : B_tk < 30m        — dầm giản đơn tiêu chuẩn (đầy đủ)
      • "trung": 30m ≤ B_tk < 60m  — Super-T mở rộng xà mũ / dầm hộp đúc hẫng
      • "lon"  : B_tk ≥ 60m        — ngoài phạm vi đề tài (chỉ ghi nhận)

    Returns
    -------
    dict: {khoang, L_nhip_min, trong_pham_vi_de_tai, ghi_chu}
    """
    B = float(B_tk or 0)
    L_nhip_min = float(_L_nhip_min(B, goc))
    if B < 30.0:
        khoang = "nho"
    elif B < 60.0:
        khoang = "trung"
    else:
        khoang = "lon"
    kg = KHOANG_TINH_KHONG[khoang]
    return {
        "khoang":               khoang,
        "L_nhip_min":           round(L_nhip_min, 2),
        "trong_pham_vi_de_tai": kg["trong_pham_vi_de_tai"],
        "ghi_chu": (f"{kg['ten']} ({kg['pham_vi']}; B_tk={B:g}m, góc={goc:g}° "
                    f"→ L_nhịp_min={L_nhip_min:.1f}m). {kg['mo_ta']}"),
    }


def _n_nhip_from(L_cau, L_span):
    """Số nhịp khi chia cầu thành các nhịp ĐỀU = L_span (định hình catalog).
    Dùng làm tròn về số nhịp gần nhất (khớp cách bố trí của module vẽ 11)."""
    if not L_cau or L_cau <= 0 or not L_span or L_span <= 0:
        return 1
    return max(1, int(round(L_cau / L_span)))


# ---------------------------------------------------------------------------
# CATALOG DẦM BTCT THEO KINH NGHIỆM THỰC TẾ VN
# ---------------------------------------------------------------------------
# Trường co_ban_day_lien_mach phân 2 nhóm theo cấu tạo bản đáy:
#   • False — KHÔNG bản đáy liền mạch (Dầm I 6–33m, Super-T 28.2–38.2m,
#     Dầm T 12–15m): nhìn từ dưới thấy các dầm riêng biệt, cấu tạo đơn giản,
#     chi phí thấp hơn → nhóm chọn của PA1 (tối ưu chi phí).
#   • True  — CÓ bản đáy liền mạch (T ngược 10–33m, Dầm bản đặc 9–24m,
#     Dầm bản rỗng 12–24m): các dầm ghép sát tạo bề mặt phẳng liền mạch dưới
#     cầu, mỹ quan cao → nhóm chọn của PA2 (tối ưu mỹ quan, đô thị/cầu vượt).
BEAM_CATALOG = [
    # (loai_dam,         L,     B,    H,    S,    cong_nghe,  co_ban_day_lien_mach)
    ("Dầm bản",          9.00, 0.99, 0.40, 1.00, "DUL_truoc", True),
    ("Dầm bản rỗng",    12.00, 0.99, 0.50, 1.00, "DUL_truoc", True),
    ("Dầm bản rỗng",    18.00, 0.99, 0.65, 1.00, "DUL_truoc", True),
    ("Dầm bản rỗng",    20.00, 0.99, 0.75, 1.00, "DUL_truoc", True),
    ("Dầm bản rỗng",    21.00, 0.99, 0.80, 1.00, "DUL_truoc", True),
    ("Dầm bản rỗng",    24.00, 0.99, 0.95, 1.00, "DUL_truoc", True),
    ("Dầm I",            6.00, 0.16, 0.28, 1.50, "DUL_truoc", False),
    ("Dầm I",            9.00, 0.20, 0.40, 1.50, "DUL_truoc", False),
    ("Dầm I",           12.50, 0.32, 0.56, 1.50, "DUL_truoc", False),
    ("Dầm I",           15.00, 0.22, 0.50, 1.50, "DUL_truoc", False),
    ("Dầm I",           15.00, 0.45, 1.00, 2.25, "DUL_sau",   False),
    ("Dầm I",           18.60, 0.43, 0.70, 1.50, "DUL_truoc", False),
    ("Dầm I",           20.70, 0.60, 1.20, 2.25, "DUL_sau",   False),
    ("Dầm I",           24.54, 0.56, 1.14, 1.75, "DUL_truoc", False),
    ("Dầm I",           33.00, 0.50, 1.40, 2.40, "DUL_truoc", False),
    ("Dầm I",           33.00, 0.65, 1.65, 2.25, "DUL_sau",   False),
    ("Dầm T",           12.00, 1.80, 0.90, 2.40, "DUL_truoc", False),
    ("Dầm T",           15.00, 1.80, 1.00, 2.40, "DUL_truoc", False),
    ("T ngược",         10.00, 0.98, 0.55, 1.00, "DUL_truoc", True),
    ("T ngược",         12.00, 0.98, 0.55, 1.00, "DUL_truoc", True),
    ("T ngược",         15.00, 0.98, 0.55, 1.00, "DUL_truoc", True),
    ("T ngược",         18.00, 0.98, 0.75, 1.00, "DUL_truoc", True),
    ("T ngược",         20.00, 0.98, 0.75, 1.00, "DUL_truoc", True),
    ("T ngược",         25.00, 0.98, 0.90, 1.00, "DUL_truoc", True),
    ("T ngược",         29.00, 0.98, 1.10, 1.00, "DUL_truoc", True),
    ("Super-T",         28.20, 0.70, 1.75, 2.44, "DUL_sau",   False),
    ("Super-T",         35.70, 0.70, 1.75, 2.44, "DUL_sau",   False),
    ("Super-T",         38.20, 0.70, 1.75, 2.44, "DUL_sau",   False),
]


def _rec_lien_mach(record):
    """Đọc trường co_ban_day_lien_mach của 1 bản ghi catalog (an toàn 6-tuple cũ)."""
    return bool(record[6]) if len(record) > 6 else False


def co_ban_day_lien_mach(loai_dam):
    """True nếu LOẠI dầm thuộc nhóm CÓ bản đáy liền mạch (tra theo catalog)."""
    for r in BEAM_CATALOG:
        if r[0] == loai_dam:
            return _rec_lien_mach(r)
    return False


def catalog_beam_types():
    """Danh sách loại dầm trong catalog (giữ thứ tự xuất hiện, không lặp)."""
    seen, out = set(), []
    for r in BEAM_CATALOG:
        if r[0] not in seen:
            seen.add(r[0])
            out.append(r[0])
    return out


def catalog_lengths(loai_dam):
    """Các chiều dài nhịp L (m) có sẵn trong catalog cho 1 loại dầm (tăng dần)."""
    return sorted({r[1] for r in BEAM_CATALOG if r[0] == loai_dam})


def get_beam_from_catalog(L_target, loai_dam=None):
    """
    Trả về bản ghi catalog gần nhất theo chiều dài nhịp.

    Parameters
    ----------
    L_target : float
        Chiều dài nhịp cần tìm (m).
    loai_dam : str, optional
        Nếu chỉ định, ưu tiên tìm trong loại dầm đó trước;
        nếu không có bản ghi phù hợp thì mở rộng toàn catalog.

    Returns
    -------
    tuple : (loai_dam, L, B, H, S, cong_nghe, co_ban_day_lien_mach)
    """
    if loai_dam:
        filtered = [r for r in BEAM_CATALOG if r[0] == loai_dam]
        if filtered:
            return min(filtered, key=lambda r: abs(r[1] - L_target))
    return min(BEAM_CATALOG, key=lambda r: abs(r[1] - L_target))


# ---------------------------------------------------------------------------
# THƯ VIỆN DẦM MẶC ĐỊNH + CHỌN DẦM TỪ THƯ VIỆN
# ---------------------------------------------------------------------------
# Ánh xạ tên loại dầm trong catalog → loại dầm theo SCHEMA thư viện
# (Super-T, Dầm I, T ngược, Bản rỗng, Khác). "Dầm bản" / "Dầm T" KHÔNG có trong
# thư viện nên quy về loại gần nhất để không bao giờ đề xuất loại thư viện thiếu.
_CATALOG_TO_LIB_TYPE = {
    "Dầm bản rỗng": "Bản rỗng",
    "Dầm bản":      "Bản rỗng",
    "T ngược":      "T ngược",
    "Dầm I":        "Dầm I",
    "Dầm T":        "Dầm I",
    "Super-T":      "Super-T",
}


def _build_default_library_beams():
    """Thư viện dầm MẶC ĐỊNH (dùng khi thư viện người dùng còn rỗng).

    Suy từ BEAM_CATALOG nhưng CHỈ giữ các loại biểu diễn được trong thư viện
    (Super-T, Dầm I, T ngược, Bản rỗng) — bỏ 'Dầm bản'/'Dầm T'. Nhờ đó hệ thống
    luôn chọn được dầm THỰC từ thư viện, không đề xuất loại thư viện chưa có.
    """
    seen = set()
    out = []
    for loai, L, B, H, S, cong_nghe, *_ in BEAM_CATALOG:
        if loai in ("Dầm bản", "Dầm T"):
            continue
        lib_type = _CATALOG_TO_LIB_TYPE.get(loai, "Khác")
        key = (lib_type, round(float(L), 1))
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "id":              f"default::{lib_type}::{L:g}",
            "ten":             f"{lib_type} {L:g}m (mặc định)",
            "loai_dam":        lib_type,
            "chieu_dai":       float(L),
            "chieu_cao":       float(H),
            "khoang_cach_dam": float(S),
            "cong_nghe":       cong_nghe,
            "_default":        True,
        })
    return out


DEFAULT_LIBRARY_BEAMS = _build_default_library_beams()


def select_library_beam(loai_dam_pred, L_target, user_beams=None):
    """
    Chọn dầm phù hợp TỪ THƯ VIỆN theo loại dầm dự đoán + chiều dài mục tiêu.

    Quy trình (theo yêu cầu): hệ thống tính sơ bộ chiều dài nhịp + dự đoán loại
    dầm, rồi LỰA CHỌN trong thư viện (người dùng hoặc mặc định) ra dầm phù hợp;
    sau đó người dùng tự rà soát/cập nhật.

    Parameters
    ----------
    loai_dam_pred : str   — loại dầm dự đoán (tên catalog hoặc schema thư viện)
    L_target      : float — chiều dài nhịp sơ bộ (m)
    user_beams    : list  — thư viện dầm người dùng (CLIB.load_beams()); rỗng →
                            dùng DEFAULT_LIBRARY_BEAMS.

    Returns
    -------
    (beam_dict, nguon) với nguon ∈ {'user','default'}; hoặc (None, None) nếu
    không có dầm nào (về lý thuyết không xảy ra vì luôn có thư viện mặc định).
    """
    pred_lib = _CATALOG_TO_LIB_TYPE.get(loai_dam_pred, loai_dam_pred)

    def _same_type(pool):
        return [b for b in pool
                if str(b.get("loai_dam", "")).strip() == pred_lib
                and float(b.get("chieu_dai") or 0) > 0]

    # CHỈ nhận dầm CÙNG LOẠI với dự đoán — KHÔNG đổi chéo loại (trước đây thư viện
    # chỉ có Super-T 19.4m → PA nhóm khác cũng bị ép thành Super-T 19.4m, sai cả
    # loại lẫn chiều dài định hình). Không có cùng loại trong thư viện người dùng
    # → dùng thư viện MẶC ĐỊNH (suy từ catalog định hình); vẫn không có → giữ
    # nguyên dự đoán (trả None để caller bỏ qua override).
    same = _same_type(user_beams or [])
    nguon = "user"
    if not same:
        same = _same_type(DEFAULT_LIBRARY_BEAMS)
        nguon = "default"
    if not same:
        return None, None
    best = min(same, key=lambda b: abs(float(b.get("chieu_dai") or 0) - float(L_target)))
    return best, nguon


# ---------------------------------------------------------------------------
# 1. NẠP & CHUẨN BỊ DỮ LIỆU
# ---------------------------------------------------------------------------
def load_training_data_v3(v3_path=None):
    """
    Đọc dữ liệu huấn luyện từ Bridge_Train_Dataset_v3.xlsx.
    Trả về DataFrame cùng cấu trúc cột với load_training_data(), hoặc rỗng nếu chưa có data.
    """
    path = v3_path or _V3_DEFAULT
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        data_dir = os.path.join(_DIR, "Data")
        if data_dir not in sys.path:
            sys.path.insert(0, data_dir)
        from v3_loader import get_kcn_df
        df = get_kcn_df(path)
    except Exception as e:
        print(f"[KCN-AI] Không nạp được v3_loader: {e}")
        return pd.DataFrame()

    if df.empty:
        return df

    # Anh xa ten cot v3 (snake_case) -> ten chuan noi bo module
    # v3 cols: b_tinh_khong, h_tinh_khong, goc_xien, b_cau/bc, l_tt, l_dam,
    #          h_dam, so_dam, kc_tim_dam, hang_dau_dam, loai_dam, loai_vuot, loai_duong
    rename = {
        "b_tinh_khong": "B_tk",
        "h_tinh_khong": "H_tk",
        "goc_xien":     "Goc_xien",
        "b_cau":        "B_cau",
        "bc":           "B_cau_alt",
        "l_dam":        "L_dam",
        "l_tt":         "L_tt",
        "h_dam":        "H_dam",
        "so_dam":       "SL_dam",
        "kc_tim_dam":   "Kc_dam",
        "hang_dau_dam": "Overhang",
        "loai_dam":     "Loai_dam",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    # B_cau tu bc neu thieu
    if "B_cau" not in df.columns and "B_cau_alt" in df.columns:
        df["B_cau"] = df["B_cau_alt"]
    elif "B_cau_alt" in df.columns:
        df["B_cau"] = df["B_cau"].fillna(df["B_cau_alt"])

    # L_dam tu L_tt neu thieu
    if "L_dam" not in df.columns and "L_tt" in df.columns:
        df["L_dam"] = pd.to_numeric(df["L_tt"], errors="coerce") + 0.5

    # Moi_truong tu loai_vuot / loai_duong
    if "Moi_truong" not in df.columns:
        src_col = "loai_vuot" if "loai_vuot" in df.columns else (
                   "loai_duong" if "loai_duong" in df.columns else None)
        if src_col:
            df["Moi_truong"] = df[src_col].astype(str).apply(
                lambda x: "Do thi" if "do thi" in x.lower() else "Vuot song"
            )
        else:
            df["Moi_truong"] = "Vuot song"

    # Ep kieu so
    for c in ["B_tk","H_tk","Goc_xien","B_cau","L_dam","H_dam","SL_dam","Kc_dam"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "Goc_xien" in df.columns:
        df["Goc_xien"] = df["Goc_xien"].fillna(90.0)
    else:
        df["Goc_xien"] = 90.0

    req = [c for c in ["B_tk","L_dam","Loai_dam","H_dam"] if c in df.columns]
    df = df.dropna(subset=req)
    if "L_dam" in df.columns:
        df = df[df["L_dam"] > 0]

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. HUẤN LUYỆN
# ---------------------------------------------------------------------------
def train_kcn_ai(v3_path=None, **_):
    """
    Huấn luyện bộ mô hình kết cấu nhịp từ Bridge_Train_Dataset_v3.xlsx.
    Trả về dict models khi v3 có >= 10 mẫu, ngược lại trả None
    (predict_kcn() sẽ dùng Rule-Based fallback tự động).
    """
    MIN_ROWS = 10
    v3p = v3_path or _V3_DEFAULT

    df = load_training_data_v3(v3p)
    n_v3 = len(df)
    if n_v3 < MIN_ROWS:
        print(f"[KCN-AI] Chua du du lieu (v3={n_v3}, can >={MIN_ROWS}). Dung Rule-Based.")
        return None
    print(f"[KCN-AI] Dung v3: {n_v3} mau")

    # Nạp sklearn TẠI ĐÂY — sau khi chắc chắn đủ dữ liệu để huấn luyện.
    from sklearn.ensemble import (RandomForestClassifier,
                                  RandomForestRegressor)
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import cross_val_score

    try:

        # Mã hóa môi trường
        le_env = LabelEncoder()
        df["Env_enc"] = le_env.fit_transform(df["Moi_truong"])

        # Mã hóa loại dầm
        le_type = LabelEncoder()
        df["Type_enc"] = le_type.fit_transform(df["Loai_dam"])

        # ─── Bộ đặc trưng đầu vào theo spec Sheet 03 ───
        feat_cols = []
        for c in ["B_tk", "H_tk", "Goc_xien", "B_cau", "Env_enc"]:
            if c in df.columns:
                feat_cols.append(c)

        X = df[feat_cols].copy()
        for c in feat_cols:
            X[c] = X[c].fillna(X[c].median())

        # Phân loại loại dầm
        clf_type = RandomForestClassifier(
            n_estimators=300, max_depth=8, min_samples_leaf=2,
            class_weight="balanced", random_state=42
        )
        clf_type.fit(X, df["Type_enc"])

        # Hồi quy chiều dài nhịp
        reg_L = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=42)
        reg_L.fit(X, df["L_dam"])

        # Hồi quy chiều cao dầm (phụ thuộc loại dầm + chiều dài)
        X_H = df[["Type_enc", "L_dam"]].fillna(0)
        reg_H = RandomForestRegressor(n_estimators=300, max_depth=6, random_state=42)
        reg_H.fit(X_H, df["H_dam"])

        models = {
            "clf_type": clf_type,
            "reg_L":    reg_L,
            "reg_H":    reg_H,
            "le_env":   le_env,
            "le_type":  le_type,
            "feat_cols": feat_cols,
            "n_samples": len(df),
            "version":  "v2_spec",
        }

        # Tùy chọn: khoảng cách dầm
        if "Kc_dam" in df.columns:
            Kc_clean = df["Kc_dam"].fillna(df["Kc_dam"].median())
            X_kc = df[["Type_enc", "B_cau"]].fillna(0) if "B_cau" in df.columns else df[["Type_enc"]].fillna(0)
            reg_kc = RandomForestRegressor(n_estimators=200, random_state=42)
            reg_kc.fit(X_kc, Kc_clean)
            models["reg_kc"] = reg_kc
            models["kc_has_Bcau"] = "B_cau" in df.columns

        # Tùy chọn: số lượng dầm
        if "SL_dam" in df.columns:
            SL_clean = df["SL_dam"].fillna(df["SL_dam"].median())
            X_sl = df[["Type_enc", "B_cau"]].fillna(0) if "B_cau" in df.columns else df[["Type_enc"]].fillna(0)
            reg_sl = RandomForestRegressor(n_estimators=200, random_state=42)
            reg_sl.fit(X_sl, SL_clean)
            models["reg_sl"] = reg_sl

        return models

    except Exception as e:
        print(f"[KCN-AI] Lỗi huấn luyện: {e}")
        return None


# ---------------------------------------------------------------------------
# 3. HÀM DỰ ĐOÁN NỘI BỘ (giữ nguyên cho PA3-AI)
# ---------------------------------------------------------------------------
def _build_x_row(B_tk, H_tk, goc, B_cau, moi_truong, models):
    le_env = models["le_env"]
    feat_cols = models["feat_cols"]
    env_str = moi_truong if moi_truong in le_env.classes_ else le_env.classes_[0]
    env_enc = le_env.transform([env_str])[0]
    mapping = {
        "B_tk":    B_tk,
        "H_tk":    H_tk if H_tk is not None else 3.5,
        "Goc_xien": goc,
        "B_cau":   B_cau,
        "Env_enc": env_enc,
    }
    return [[mapping.get(c, 0) for c in feat_cols]]


def _snap_length(L_raw):
    """Làm tròn chiều dài về nhịp tiêu chuẩn gần nhất."""
    return min(STD_LENGTHS, key=lambda x: abs(x - L_raw))


def _calc_girder_layout(dam_type, L_span, B_cau, models, S_catalog=None):
    """
    Tính khoảng cách và số lượng dầm trên mặt cắt ngang.

    Parameters
    ----------
    dam_type  : str   — loại dầm
    L_span    : float — chiều dài nhịp
    B_cau     : float — bề rộng cầu (m)
    models    : dict  — từ train_kcn_ai()
    S_catalog : float, optional
        Khoảng cách dầm lấy từ BEAM_CATALOG. Nếu có thì dùng ngay,
        không dự báo từ reg_kc.

    Returns
    -------
    (kc, n_dam, overhang)
    """
    if S_catalog is not None:
        kc = float(S_catalog)
        n_dam = max(2, int(B_cau / kc) + 1)
        oh = round((B_cau - (n_dam - 1) * kc) / 2, 2)
        # Overhang quá nhỏ → bớt 1 dầm
        if oh < 0.15:
            n_dam = max(2, n_dam - 1)
            oh = round((B_cau - (n_dam - 1) * kc) / 2, 2)
        # Overhang quá lớn → thêm 1 dầm
        if oh > max(1.2, 0.8 * kc):
            n_dam += 1
            oh = round((B_cau - (n_dam - 1) * kc) / 2, 2)
        return round(kc, 2), n_dam, max(0.10, oh)

    le_type = models["le_type"]
    t_enc = le_type.transform([dam_type])[0] if dam_type in le_type.classes_ else 0

    if "reg_kc" in models:
        X_kc = [[t_enc, B_cau]] if models.get("kc_has_Bcau") else [[t_enc]]
        kc = float(models["reg_kc"].predict(X_kc)[0])
        kc = max(0.8, min(kc, 3.0))
    else:
        defaults = {"Super-T": 2.2, "Dầm I": 2.0, "T ngược": 1.0, "Dầm bản": 0.7}
        kc = defaults.get(dam_type, 2.0)

    n_dam = max(3, int(round(B_cau / kc)) + 1)
    oh = round((B_cau - (n_dam - 1) * kc) / 2, 2)
    if oh > 0.8 * kc:
        n_dam += 1
        oh = round((B_cau - (n_dam - 1) * kc) / 2, 2)

    if "reg_sl" in models:
        X_sl = [[t_enc, B_cau]]
        n_dam = max(3, int(round(float(models["reg_sl"].predict(X_sl)[0]))))
        kc = round(B_cau / (n_dam - 1), 2) if n_dam > 1 else kc
        oh = round((B_cau - (n_dam - 1) * kc) / 2, 2)

    return round(kc, 2), n_dam, max(0.2, oh)


def _score_candidate(dam_type, L_span, n_nhip, h_dam, L_cau_tong, B_tk=None):
    """
    Hàm điểm cho tối ưu hóa tổ hợp (loại dầm × chiều dài nhịp) — dùng bởi _predict_optimize.

    Nguyên tắc chấm điểm:
    1. Ít trụ → tiết kiệm chi phí (tối đa 60 pt)
    2. Chiều dài nhịp phù hợp với bề rộng tĩnh không B_tk (tối đa 30 pt)
    3. Loại dầm phù hợp với chiều dài nhịp (tối đa 35 pt)
    4. Tỉ lệ L/H tối ưu kết cấu 17–22 (tối đa 15 pt)
    """
    score = 0.0

    if L_cau_tong and L_cau_tong > 0:
        score += 60.0 / max(n_nhip, 1)
    else:
        score += 50.0

    if B_tk is not None and B_tk <= 10:
        if 12 <= L_span <= 24:
            score += 30
        elif 24 < L_span <= 33:
            score += 12
    elif B_tk is not None and B_tk <= 22:
        if 24 <= L_span <= 38:
            score += 30
        elif 18 <= L_span < 24 or 38 < L_span <= 42:
            score += 15
    else:
        if 33 <= L_span <= 40:
            score += 30
        elif 25 <= L_span < 33 or 40 < L_span <= 45:
            score += 15

    if dam_type == "Dầm bản" and L_span <= 15:
        score += 35
    elif dam_type == "T ngược" and 12 <= L_span <= 22:
        score += 33
    elif dam_type == "Dầm I" and 18 <= L_span <= 33:
        score += 30
    elif dam_type == "Super-T" and 27 <= L_span <= 40:
        score += 35
    elif dam_type in {"Super-T", "Dầm I"}:
        score += 8

    if h_dam > 0:
        ratio = L_span / h_dam
        if 17 <= ratio <= 22:
            score += 15
        elif 15 <= ratio <= 25:
            score += 8

    return score


def _predict_single(B_tk, H_tk, goc, B_cau, moi_truong, models):
    """Dự đoán một cấu hình dầm đơn từ mô hình."""
    X_row = _build_x_row(B_tk, H_tk, goc, B_cau, moi_truong, models)
    le_type = models["le_type"]

    t_idx = models["clf_type"].predict(X_row)[0]
    loai_dam = str(le_type.inverse_transform([t_idx])[0]).strip()

    L_raw = float(models["reg_L"].predict(X_row)[0])
    L_min_geo = _L_nhip_min(B_tk, goc)
    L_raw = max(L_raw, L_min_geo)
    L_span = _snap_length(L_raw)
    # Bảo đảm nhịp định hình sau khi snap vẫn ≥ điều kiện tĩnh không
    if L_span < L_min_geo:
        ge = [l for l in STD_LENGTHS if l >= L_min_geo - 1e-6]
        L_span = min(ge) if ge else L_span

    t_enc_best = le_type.transform([loai_dam])[0] if loai_dam in le_type.classes_ else 0
    H_dam = float(models["reg_H"].predict([[t_enc_best, L_span]])[0])
    H_dam = max(0.5, min(H_dam, 3.5))

    return loai_dam, L_span, H_dam


def _predict_optimize(B_tk, H_tk, goc, B_cau, moi_truong, L_cau_tong, models):
    """Tối ưu hóa tổ hợp loại dầm × chiều dài — dùng bởi _predict_ai (PA3)."""
    le_type = models["le_type"]
    X_row = _build_x_row(B_tk, H_tk, goc, B_cau, moi_truong, models)

    ai_idx = models["clf_type"].predict(X_row)[0]
    ai_type = str(le_type.inverse_transform([ai_idx])[0]).strip()

    candidate_types = {ai_type}
    if "đô thị" in moi_truong.lower() or B_tk <= 20:
        candidate_types.update(["T ngược", "Dầm I"])
    else:
        candidate_types.update(["Super-T", "Dầm I"])
    candidate_types = {t for t in candidate_types if t in le_type.classes_}

    L_ml_raw  = float(models["reg_L"].predict(X_row)[0])
    L_min_geo = _L_nhip_min(B_tk, goc)
    L_ml_raw  = max(L_ml_raw, L_min_geo)
    L_ml_std  = _snap_length(L_ml_raw)
    # Chỉ xét nhịp định hình ≥ điều kiện tĩnh không (nhịp chính không vi phạm TK).
    # Toàn cầu dùng MỘT chiều dài định hình duy nhất → các nhịp đều nhau.
    possible_L = sorted({l for l in STD_LENGTHS if l >= L_min_geo - 1e-6} | {L_ml_std})
    possible_L = [l for l in possible_L if l >= L_min_geo - 1e-6] or [L_ml_std]

    best_score = -1
    best = None

    for dam_type in candidate_types:
        t_enc = le_type.transform([dam_type])[0]
        for L in possible_L:
            H_dam = float(models["reg_H"].predict([[t_enc, L]])[0])
            H_dam = max(0.5, min(H_dam, 3.5))

            n_nhip = _n_nhip_from(L_cau_tong, L) if (L_cau_tong and L_cau_tong > 0) else 1

            # Chấm điểm theo CHÍNH chiều dài định hình L (mọi nhịp đều = L)
            score = _score_candidate(dam_type, L, n_nhip, H_dam, L_cau_tong, B_tk=B_tk)
            if score > best_score:
                best_score = score
                best = (dam_type, L, n_nhip, H_dam)

    if best is None:
        loai_dam, L_span, H_dam = _predict_single(B_tk, H_tk, goc, B_cau, moi_truong, models)
        n_nhip = _n_nhip_from(L_cau_tong, L_span) if L_cau_tong else 1
        best = (loai_dam, L_span, n_nhip, H_dam)

    return best


# ---------------------------------------------------------------------------
# 4. BA PHƯƠNG ÁN DỰ ĐOÁN
# ---------------------------------------------------------------------------
def _girder_layout_from_S(B_cau, S):
    """Số dầm + overhang trên MCN từ khoảng cách dầm S catalog (dùng chung)."""
    n_dam = max(2, int(B_cau / S) + 1)
    oh = round((B_cau - (n_dam - 1) * S) / 2, 2)
    if oh < 0.15:
        n_dam = max(2, n_dam - 1)
        oh = round((B_cau - (n_dam - 1) * S) / 2, 2)
    if oh > max(1.2, 0.8 * S):
        n_dam += 1
        oh = round((B_cau - (n_dam - 1) * S) / 2, 2)
    return n_dam, max(0.10, oh)


def _plan_from_record(record, B_cau, n_nhip, phuong_phap, ghi_chu,
                      canh_bao=None, nguon_chon="tu_dong"):
    """Dựng dict phương án chuẩn (xem predict_kcn) từ 1 bản ghi catalog."""
    loai, L, B, H, S, cong_nghe = record[:6]
    n_dam, oh = _girder_layout_from_S(B_cau, S)
    plan = {
        "loai_dam":        loai,
        "chieu_dai":       L,
        "chieu_cao_dam":   H,
        "be_rong_dam":     B,
        "khoang_cach_dam": S,
        "tong_so_nhip":    n_nhip,
        "so_luong_dam":    n_dam,
        "overhang":        oh,
        "ti_le_L_H":       round(L / H, 1) if H > 0 else 0,
        "cong_nghe":       cong_nghe,
        "co_ban_day_lien_mach": _rec_lien_mach(record),
        "phuong_phap":     phuong_phap,
        "ghi_chu":         ghi_chu,
        "nguon_chon":      nguon_chon,
    }
    if canh_bao:
        plan["canh_bao"] = canh_bao
    return plan


def _filter_group(L_min_geo, lien_mach, L_cau=None):
    """Lọc catalog theo nhóm bản đáy + điều kiện tĩnh không (+ chiều dài cầu).

    Trả (records, canh_bao): đúng nhóm + thỏa L ≥ L_nhip_min; khi biết chiều
    dài toàn cầu thì loại dầm DÀI hơn cầu (L ≤ max(L_cau, L_min)×1.05 — không
    dùng dầm 38m cho cầu 15m). Nhóm rỗng → FALLBACK sang nhóm còn lại (kèm
    cảnh báo); cùng lắm trả cả catalog.
    """
    L_max = (max(float(L_cau), L_min_geo) * 1.05
             if (L_cau and float(L_cau) > 0) else None)

    def _pick(lm):
        grp = [r for r in BEAM_CATALOG
               if _rec_lien_mach(r) == lm and r[1] >= L_min_geo - 1e-6]
        if L_max is not None and grp:
            capped = [r for r in grp if r[1] <= L_max + 1e-6]
            if capped:
                return capped
            # Không dầm nào ngắn hơn cầu → lấy các dầm NGẮN NHẤT vượt nhịp
            # tối thiểu (không dùng dầm 38m cho cầu ~17m chỉ vì điểm cao).
            L_ngan = min(r[1] for r in grp)
            return [r for r in grp if r[1] <= L_ngan + 1e-6]
        return grp

    grp = _pick(lien_mach)
    if grp:
        return grp, None
    nhom = ("CÓ bản đáy liền mạch" if lien_mach else "KHÔNG bản đáy liền mạch")
    other = _pick(not lien_mach)
    canh_bao = (f"Không có dầm nhóm {nhom} thỏa nhịp tối thiểu "
                f"{L_min_geo:.1f}m (tĩnh không) — đã chuyển sang nhóm còn lại.")
    if other:
        return other, canh_bao
    return list(BEAM_CATALOG), (f"Không có dầm nào trong catalog thỏa nhịp tối "
                                f"thiểu {L_min_geo:.1f}m — dùng toàn bộ catalog.")


def _predict_rb_chi_phi(B_tk, goc, B_cau, L_cau_tong):
    """
    PA1 — Tối ưu chi phí xây dựng (Rule-Based từ BEAM_CATALOG).

    CHỈ chọn nhóm dầm KHÔNG có bản đáy liền mạch (Dầm I / Super-T / Dầm T —
    các dầm riêng biệt, cấu tạo đơn giản, chi phí thấp). Chấm điểm:
      - Ít trụ nhất (n_nhip nhỏ) → tiết kiệm chi phí phần dưới (trọng số cao nhất)
      - Nhịp dài hơn (L lớn) → ít dầm tổng thể hơn
      - Khoảng cách dầm S lớn → ít dầm trên mỗi mặt cắt ngang
    Cầu nhiều nhịp dùng CÙNG chiều dài nhịp cho cả nhịp chính và nhịp dẫn
    (không trộn dầm khác nhau) để đơn giản hóa thi công.

    Parameters
    ----------
    B_tk       : float — bề rộng tĩnh không (m)
    goc        : float — góc giao chéo (°)
    B_cau      : float — bề rộng mặt cầu (m)
    L_cau_tong : float or None — chiều dài toàn cầu (m)

    Returns
    -------
    dict với cấu trúc chuẩn (xem predict_kcn).
    """
    L_min_geo = _L_nhip_min(B_tk, goc)
    L_cau = float(L_cau_tong) if L_cau_tong else None

    eligible, canh_bao = _filter_group(L_min_geo, lien_mach=False, L_cau=L_cau)

    # KHOẢNG NHỎ — lọc chặt: nhấn mạnh Dầm I & Super-T (KHÔNG dùng Dầm T
    # thông thường ở đây vì tối ưu chi phí ưu tiên nhịp dài). Rỗng → giữ nhóm.
    _uu_tien = [r for r in eligible if r[0] in ("Dầm I", "Super-T")]
    if _uu_tien:
        eligible = _uu_tien

    best_score = -1e9
    best_record = None
    best_n_nhip = 1

    for record in eligible:
        loai, L, B, H, S, cong_nghe = record[:6]
        n_nhip = _n_nhip_from(L_cau, L) if L_cau else 1

        # Scoring: ít nhịp (ít trụ) → ưu tiên cao nhất; nhịp dài → thứ hai; S lớn → thứ ba
        score = (1.0 / n_nhip) * 100.0 + L * 1.0 + S * 5.0

        if score > best_score:
            best_score = score
            best_record = record
            best_n_nhip = n_nhip

    # CẦU 1 NHỊP (nhỏ): chọn NHỊP ĐỊNH HÌNH NHỎ NHẤT đủ tĩnh không (kinh tế, KHÔNG
    # dư khẩu độ) — thay vì nhịp dài nhất. Cầu nhiều nhịp giữ ưu tiên ít trụ ở trên.
    if best_n_nhip <= 1:
        _ge = [r for r in eligible if r[1] >= L_min_geo - 1e-6]
        if _ge:
            best_record = min(_ge, key=lambda r: r[1]); best_n_nhip = 1

    loai, L = best_record[0], best_record[1]
    S = best_record[4]
    ghi_chu = (f"Ưu tiên nhịp DÀI để giảm số nhịp → giảm chi phí thi công; "
               f"dầm KHÔNG bản đáy liền mạch (cấu tạo đơn giản, chi phí thấp): "
               f"{loai} L={L}m × {best_n_nhip} nhịp (cùng chiều dài cho nhịp "
               f"chính và nhịp dẫn), S={S}m.")
    return _plan_from_record(best_record, B_cau, best_n_nhip,
                             "Rule-Based (Chi phí — không bản đáy liền mạch)",
                             ghi_chu, canh_bao=canh_bao)


def _predict_rb_my_quan(B_tk, goc, B_cau, L_cau_tong):
    """
    PA2 — Tối ưu mỹ quan (Rule-Based từ BEAM_CATALOG).

    CHỈ chọn nhóm dầm CÓ bản đáy liền mạch (T ngược / Dầm bản / Bản rỗng —
    các dầm ghép sát tạo bề mặt phẳng liền mạch dưới cầu, phù hợp cầu đô thị
    và cầu vượt). Chấm điểm (nhấn cấu tạo bản đáy thay vì chỉ chiều cao):
      score = −H×30 + bonus_ban_day_lien_mach(50) + n_nhip×3
      - Hệ số H giảm 50 → 30: không quá nhấn chiều cao thấp
      - +50 điểm cho mọi dầm nhóm bản đáy liền mạch (0 khi phải fallback)
      - Ưu tiên chiều dài nhịp trung bình 10–33m phù hợp cầu đô thị
    Cầu nhiều nhịp dùng CÙNG chiều dài nhịp cho cả nhịp chính và nhịp dẫn
    (nguyên tắc như PA1).

    Parameters
    ----------
    B_tk       : float — bề rộng tĩnh không (m)
    goc        : float — góc giao chéo (°)
    B_cau      : float — bề rộng mặt cầu (m)
    L_cau_tong : float or None — chiều dài toàn cầu (m)

    Returns
    -------
    dict với cấu trúc chuẩn (xem predict_kcn).
    """
    L_min_geo = _L_nhip_min(B_tk, goc)
    L_cau = float(L_cau_tong) if L_cau_tong else None

    eligible, canh_bao = _filter_group(L_min_geo, lien_mach=True, L_cau=L_cau)

    # KHOẢNG NHỎ — lọc chặt: nhấn mạnh T ngược & Dầm bản rỗng (KHÔNG dùng
    # Dầm bản đặc — thường chỉ cho nhịp rất ngắn < 15m). Rỗng → giữ nhóm.
    _uu_tien = [r for r in eligible if r[0] in ("T ngược", "Dầm bản rỗng")]
    if _uu_tien:
        eligible = _uu_tien

    best_score = -1e9
    best_record = None
    best_n_nhip = 1

    for record in eligible:
        loai, L, B, H, S, cong_nghe = record[:6]
        n_nhip = _n_nhip_from(L_cau, L) if L_cau else 1

        # Scoring: −H×30 (nhấn vừa phải) + 50 điểm bản đáy liền mạch + n_nhip×3;
        # ưu tiên nhẹ nhịp trung bình 10–33m (phù hợp cầu đô thị).
        bonus_ban_day_lien_mach = 50.0 if _rec_lien_mach(record) else 0.0
        score = -H * 30.0 + bonus_ban_day_lien_mach + n_nhip * 3.0
        if 10.0 <= L <= 33.0:
            score += 5.0

        if score > best_score:
            best_score = score
            best_record = record
            best_n_nhip = n_nhip

    # CẦU 1 NHỊP (nhỏ): chọn NHỊP ĐỊNH HÌNH NHỎ NHẤT đủ tĩnh không (kinh tế) —
    # cùng nguyên tắc PA1, chỉ khác LOẠI dầm (nhóm bản đáy liền mạch).
    if best_n_nhip <= 1:
        _ge = [r for r in eligible if r[1] >= L_min_geo - 1e-6]
        if _ge:
            best_record = min(_ge, key=lambda r: r[1]); best_n_nhip = 1

    loai, L = best_record[0], best_record[1]
    H = best_record[3]
    ghi_chu = (f"Ưu tiên dầm CÓ bản đáy liền mạch — các dầm ghép sát tạo bề "
               f"mặt phẳng đẹp dưới cầu, phù hợp cầu đô thị/cầu vượt: {loai} "
               f"L={L}m × {best_n_nhip} nhịp (cùng chiều dài cho nhịp chính "
               f"và nhịp dẫn), H={H}m.")
    return _plan_from_record(best_record, B_cau, best_n_nhip,
                             "Rule-Based (Mỹ quan — bản đáy liền mạch)",
                             ghi_chu, canh_bao=canh_bao)


def make_plan_from_catalog(loai_dam, L, B_cau, L_cau_tong=None,
                           nguon_chon="nguoi_dung_khai_bao"):
    """
    Dựng phương án từ 1 dầm catalog do NGƯỜI DÙNG khai báo (loại + chiều dài).

    Dùng cho tính năng "khai báo lại loại dầm" của PA1/PA2: các thông số phụ
    thuộc (H, S, B, công nghệ DUL) tự lấy từ BEAM_CATALOG theo loại và chiều
    dài đã chọn; số nhịp chia đều theo chiều dài toàn cầu (cùng chiều dài
    nhịp cho nhịp chính và nhịp dẫn).

    Returns
    -------
    dict với cấu trúc chuẩn (xem predict_kcn), nguon_chon đánh dấu nguồn chọn.
    """
    record = get_beam_from_catalog(float(L), loai_dam=loai_dam)
    L_cat = record[1]
    n_nhip = (_n_nhip_from(float(L_cau_tong), L_cat)
              if (L_cau_tong and float(L_cau_tong) > 0) else 1)
    nhom = ("CÓ bản đáy liền mạch" if _rec_lien_mach(record)
            else "KHÔNG bản đáy liền mạch")
    ghi_chu = (f"Người dùng khai báo: {record[0]} L={L_cat}m × {n_nhip} nhịp "
               f"(nhóm {nhom}); H/S/công nghệ lấy theo catalog.")
    return _plan_from_record(record, B_cau, n_nhip,
                             "Người dùng khai báo (catalog)", ghi_chu,
                             nguon_chon=nguon_chon)


# ---------------------------------------------------------------------------
# KHOẢNG TRUNG (30m ≤ B_tk < 60m) — CATALOG MỞ RỘNG + 2 PHƯƠNG ÁN
# ---------------------------------------------------------------------------
# CATALOG MỞ RỘNG cho khoảng trung — ⚠️ dữ liệu MẪU ban đầu để chạy thử; cần
# BỔ SUNG bản ghi thực tế (định hình nhà máy / hồ sơ đúc hẫng đã duyệt) khi
# mở rộng đề tài.
BEAM_CATALOG_TRUNG = {
    # Super-T MỞ RỘNG XÀ MŨ (cơ sở PA1): (L_dam_m, H_m, S_m, mo_rong_kha_dung_m)
    # mo_rong_kha_dung = mức nới ụ giữa xà mũ đi kèm cỡ dầm (cap_mid_extra).
    "super_t_mo_rong": [
        (38.2, 1.75, 2.44, 0.0),
        (40.0, 1.75, 2.44, 1.2),
        (42.0, 1.75, 2.44, 2.4),
        (45.0, 1.75, 2.44, 4.0),
    ],
    # DẦM HỘP ĐÚC HẪNG CÂN BẰNG (cơ sở PA2): (L_nhip_m, H_min_m, H_max_m)
    # H_max tại trụ ≈ L/18–L/22; H_min giữa nhịp ≈ L/40–L/50 (TCVN 11823).
    "dam_hop_duc_hang": [
        (40.0, 1.0, 2.0),
        (50.0, 1.2, 2.5),
        (60.0, 1.4, 3.0),
    ],
}

# Dự trữ mép vai kê 2 phía khi nới ụ giữa (m) — khẩu độ thoát được của kỹ
# thuật mở rộng xà mũ ≈ L_dầm + mo_rong_xa_mu + _MEP_VAI_KE
_MEP_VAI_KE = 0.6


def _predict_pa1_khoang_trung(B_tk, goc, B_cau, L_cau_tong):
    """
    PA1 KHOẢNG TRUNG — Super-T MỞ RỘNG XÀ MŨ.

    Giữ dầm Super-T định hình, NỚI RỘNG Ụ GIỮA xà mũ tại trụ kẹp tĩnh không
    (kỹ thuật _spt_widen_layout của Module 11 — bề rộng nới ánh xạ vào
    cap_mid_extra khi dựng trụ 3D/2D): khẩu độ thoát ≈ L_dầm + mo_rong +
    dự trữ mép vai kê. Chọn cỡ Super-T NHỎ NHẤT trong BEAM_CATALOG_TRUNG
    có mức mở rộng khả dụng đủ vượt B_tk hiệu dụng.

    Returns dict cấu trúc chuẩn PA1 + mo_rong_xa_mu (m — bề rộng ụ giữa cần
    nới) + giai_phap = "Super-T mở rộng xà mũ".
    """
    B_hd = float(B_tk) / np.sin(np.radians(max(goc, 30)))   # B_tk hiệu dụng
    L_cau = float(L_cau_tong) if L_cau_tong else None
    canh_bao = None

    chon = None
    for (L, H, S, mo_max) in BEAM_CATALOG_TRUNG["super_t_mo_rong"]:
        mo_can = max(0.0, B_hd - L - _MEP_VAI_KE)
        if mo_can <= mo_max + 1e-6:
            chon = (L, H, S, round(mo_can, 1))
            break
    if chon is None:
        L, H, S, mo_max = BEAM_CATALOG_TRUNG["super_t_mo_rong"][-1]
        mo_can = round(max(0.0, B_hd - L - _MEP_VAI_KE), 1)
        chon = (L, H, S, mo_can)
        canh_bao = (f"Mức nới ụ giữa cần thiết {mo_can:g}m vượt khuyến nghị "
                    f"({mo_max:g}m cho Super-T {L:g}m) — kiểm tra kết cấu "
                    "xà mũ ở bước TKKT.")
    L, H, S, mo_rong = chon

    n_nhip = _n_nhip_from(L_cau, L) if L_cau else 1
    n_dam, oh = _girder_layout_from_S(B_cau, S)
    ghi_chu = (f"KHOẢNG TRUNG: giữ Super-T định hình L={L:g}m, NỚI Ụ GIỮA xà "
               f"mũ {mo_rong:g}m tại trụ kẹp tĩnh không (khẩu độ thoát ≈ "
               f"{L + mo_rong + _MEP_VAI_KE:.1f}m ≥ B_tk {B_tk:g}m) — kỹ "
               f"thuật _spt_widen_layout Module 11; {n_nhip} nhịp.")
    plan = {
        "loai_dam":        "Super-T",
        "chieu_dai":       L,
        "chieu_cao_dam":   H,
        "be_rong_dam":     0.70,
        "khoang_cach_dam": S,
        "tong_so_nhip":    n_nhip,
        "so_luong_dam":    n_dam,
        "overhang":        oh,
        "ti_le_L_H":       round(L / H, 1),
        "cong_nghe":       "DUL_sau",
        "co_ban_day_lien_mach": False,
        "mo_rong_xa_mu":   mo_rong,
        "giai_phap":       "Super-T mở rộng xà mũ",
        "phuong_phap":     "Rule-Based khoảng trung (Super-T mở rộng xà mũ)",
        "ghi_chu":         ghi_chu,
        "nguon_chon":      "tu_dong",
    }
    if canh_bao:
        plan["canh_bao"] = canh_bao
    return plan


def _predict_pa2_khoang_trung(B_tk, goc, B_cau, L_cau_tong):
    """
    PA2 KHOẢNG TRUNG — DẦM HỘP ĐÚC HẪNG CÂN BẰNG, chiều cao biến thiên.

    Chọn nhịp hộp NHỎ NHẤT ≥ L_nhịp_min từ BEAM_CATALOG_TRUNG; chiều cao
    biến thiên (TCVN 11823): H_max tại trụ ≈ L/18–L/22, H_min giữa nhịp ≈
    L/40–L/50, biên dạng đáy dầm parabol (thông số SƠ BỘ cho TKCS, không
    phải tính toán chi tiết TKKT).

    Returns dict cấu trúc chuẩn + H_dam_min/H_dam_max +
    phuong_phap_thi_cong = "Đúc hẫng cân bằng" + giai_phap = "Dầm hộp đúc hẫng".
    """
    L_min = _L_nhip_min(B_tk, goc)
    L_cau = float(L_cau_tong) if L_cau_tong else None
    canh_bao = None

    rows = BEAM_CATALOG_TRUNG["dam_hop_duc_hang"]
    du = [r for r in rows if r[0] >= L_min - 1e-6]
    if du:
        L, H_min, H_max = min(du, key=lambda r: r[0])
    else:
        L, H_min, H_max = max(rows, key=lambda r: r[0])
        canh_bao = (f"Nhịp hộp lớn nhất catalog ({L:g}m) < L_nhịp_min "
                    f"{L_min:.1f}m — cần bổ sung catalog dầm hộp dài hơn.")

    n_nhip = _n_nhip_from(L_cau, L) if L_cau else 1
    # MCN hộp: 1 hộp đơn cho cầu hẹp, 2 hộp cho cầu rộng
    so_hop = 1 if B_cau <= 13.0 else 2
    kc_hop = round(B_cau / so_hop, 2)
    oh = round(max(0.1, (B_cau - (so_hop - 1) * kc_hop) / 2 * 0.25), 2)
    ghi_chu = (f"KHOẢNG TRUNG: dầm hộp ĐÚC HẪNG CÂN BẰNG L={L:g}m × {n_nhip} "
               f"nhịp; chiều cao biến thiên H_max={H_max:g}m tại trụ "
               f"(≈L/{L/H_max:.0f}) → H_min={H_min:g}m giữa nhịp "
               f"(≈L/{L/H_min:.0f}), đáy dầm parabol (TCVN 11823).")
    plan = {
        "loai_dam":        "Dầm hộp",
        "chieu_dai":       L,
        "chieu_cao_dam":   H_max,          # đại diện (tại trụ) — code cũ dùng
        "H_dam_min":       H_min,
        "H_dam_max":       H_max,
        "be_rong_dam":     round(B_cau / so_hop, 2),
        "khoang_cach_dam": kc_hop,
        "tong_so_nhip":    n_nhip,
        "so_luong_dam":    so_hop,
        "overhang":        oh,
        "ti_le_L_H":       round(L / H_max, 1),
        "cong_nghe":       "DUL_sau",
        "co_ban_day_lien_mach": True,      # bản đáy hộp liền mạch
        "phuong_phap_thi_cong": "Đúc hẫng cân bằng",
        "giai_phap":       "Dầm hộp đúc hẫng",
        "phuong_phap":     "Rule-Based khoảng trung (dầm hộp đúc hẫng)",
        "ghi_chu":         ghi_chu,
        "nguon_chon":      "tu_dong",
    }
    if canh_bao:
        plan["canh_bao"] = canh_bao
    return plan


def _predict_khoang_lon(B_tk, goc, B_cau):
    """
    KHOẢNG LỚN (B_tk ≥ 60m) — NGOÀI PHẠM VI ĐỀ TÀI: chỉ đưa thông tin tham
    khảo, KHÔNG tự động tính số nhịp / chiều cao dầm / thông số chi tiết.
    """
    return {
        "khoang":               "lon",
        "trong_pham_vi_de_tai": False,
        "B_tk":                 float(B_tk),
        "L_nhip_min":           round(float(_L_nhip_min(B_tk, goc)), 1),
        "khuyen_nghi_pa1": (
            "Cầu dây văng với hệ dây văng và tháp cầu chịu lực chính, phù "
            "hợp vượt nhịp lớn không có trụ giữa"),
        "khuyen_nghi_pa2": (
            "Dầm hộp đúc hẫng cỡ lớn hoặc kết hợp dây văng hỗ trợ dạng "
            "extradosed"),
        "ly_do_ngoai_pham_vi": (
            "Vượt giới hạn thuật toán Rule-Based và catalog huấn luyện "
            "Random Forest hiện có, thuộc phạm vi TKKT cầu lớn cần khảo "
            "sát chi tiết và tham vấn chuyên gia"),
        "de_xuat": (
            "Đề xuất chuyển sang phần mềm chuyên dụng cầu lớn hoặc tham "
            "vấn viện nghiên cứu chuyên ngành"),
    }


def _predict_ml(B_tk, H_tk, goc, B_cau, moi_truong, L_cau_tong, models):
    """
    PA3 — Machine Learning (Random Forest học từ Bridge_Train_Dataset_v3 —
    dữ liệu công trình cầu Việt Nam) dự đoán loại dầm + chiều dài, sau đó tra
    BEAM_CATALOG để lấy H, B, S thực tế thay vì dùng công thức.

    PA3 được chọn BẤT KỲ trong 6 loại dầm của catalog (phản ánh kinh nghiệm
    tích lũy thực tế) và KHÔNG cho người dùng ghi đè — giữ nguyên kết quả học
    từ dữ liệu để làm cơ sở so sánh khách quan với PA1/PA2 Rule-Based.

    Nếu models là None (chưa huấn luyện), fallback về kết quả tra catalog
    theo tỉ lệ L/H mục tiêu ≈ 18 (giá trị kinh nghiệm trung bình).

    Parameters
    ----------
    B_tk       : float — bề rộng tĩnh không (m)
    H_tk       : float — chiều cao tĩnh không (m)
    goc        : float — góc giao chéo (°)
    B_cau      : float — bề rộng mặt cầu (m)
    moi_truong : str   — 'Vượt sông' | 'Đô thị' | ...
    L_cau_tong : float or None — chiều dài toàn cầu (m)
    models     : dict or None — từ train_kcn_ai()

    Returns
    -------
    dict với cấu trúc chuẩn (xem predict_kcn).
    """
    L_min_geo = _L_nhip_min(B_tk, goc)
    if models is None:
        # Fallback: chọn bản ghi catalog có L/H gần 18 nhất và L >= L_min_geo (tĩnh không)
        eligible = [r for r in BEAM_CATALOG if r[1] >= L_min_geo - 1e-6] or BEAM_CATALOG
        best_record = min(eligible, key=lambda r: abs(r[1] / r[3] - 18.0))
        loai_cat, L_cat = best_record[0], best_record[1]
        L_cau_actual = float(L_cau_tong) if L_cau_tong else L_cat
        n_nhip_cat = _n_nhip_from(L_cau_actual, L_cat)
        ghi_chu = (f"Chưa có mô hình Machine Learning — catalog L/H≈18: "
                   f"{loai_cat} L={L_cat}m, {n_nhip_cat} nhịp.")
        phuong_phap = "Catalog (chưa có mô hình ML)"
    else:
        loai_ml, L_ml, _, _ = _predict_optimize(
            B_tk, H_tk, goc, B_cau, moi_truong, L_cau_tong, models
        )
        # Nhịp chính không vi phạm tĩnh không → bảo đảm L tra catalog ≥ L_min_geo
        best_record = get_beam_from_catalog(max(L_ml, L_min_geo), loai_dam=loai_ml)
        if best_record[1] < L_min_geo - 1e-6:
            elig = [r for r in BEAM_CATALOG if r[1] >= L_min_geo - 1e-6]
            if elig:
                best_record = min(elig, key=lambda r: r[1])
        loai_cat, L_cat = best_record[0], best_record[1]
        L_cau_actual = float(L_cau_tong) if L_cau_tong else L_cat
        n_nhip_cat = _n_nhip_from(L_cau_actual, L_cat)
        ghi_chu = (f"Machine Learning (Random Forest, Bridge_Train_v3): "
                   f"{loai_ml} L≈{L_ml:.1f}m → "
                   f"Catalog: {loai_cat} L={L_cat}m, {n_nhip_cat} nhịp.")
        phuong_phap = "Machine Learning + Catalog"

    return _plan_from_record(best_record, B_cau, n_nhip_cat,
                             phuong_phap, ghi_chu)


# Alias tương thích ngược (tên cũ trước khi đổi PA3 → Machine Learning)
_predict_ai = _predict_ml


# ---------------------------------------------------------------------------
# 5. HÀM CHÍNH XUẤT KẾT QUẢ
# ---------------------------------------------------------------------------
def predict_kcn(B_tk, H_tk, goc, B_cau, moi_truong,
                L_cau_tong=None, models=None):
    """
    Dự đoán kết cấu nhịp — luôn trả về cả 3 phương án.

    Parameters
    ----------
    B_tk       : float — bề rộng tĩnh không (m)
    H_tk       : float — chiều cao tĩnh không (m)
    goc        : float — góc giao chéo (°)
    B_cau      : float — bề rộng mặt cắt cầu (m)
    moi_truong : str   — 'Vượt sông' | 'Đô thị' | ...
    L_cau_tong : float or None — chiều dài toàn cầu (m); None = chưa biết
    models     : dict or None — từ train_kcn_ai()

    Returns
    -------
    dict chứa 3 phương án:
      {
        "pa1_chi_phi": { loai_dam, chieu_dai, chieu_cao_dam, be_rong_dam,
                         khoang_cach_dam, tong_so_nhip, so_luong_dam,
                         overhang, ti_le_L_H, cong_nghe,
                         co_ban_day_lien_mach, phuong_phap, ghi_chu,
                         nguon_chon ('tu_dong' | 'nguoi_dung_khai_bao') },
        "pa2_my_quan": { ... },
        "pa3_ml":      { ... },   # Machine Learning — không cho ghi đè
        "khoang_tinh_khong": {khoang, L_nhip_min, trong_pham_vi_de_tai,
                              ghi_chu},   # phân loại 3 khoảng theo B_tk
      }
    Điều phối BA KHOẢNG tĩnh không (_phan_loai_khoang_tinh_khong):
      • "nho"  (B_tk < 30m)  : PA1/PA2 catalog dầm giản đơn + PA3 ML — như cũ.
      • "trung" (30–60m)     : PA1 Super-T mở rộng xà mũ, PA2 dầm hộp đúc
        hẫng; PA3 fallback Rule-Based (RF chưa huấn luyện cho khoảng trung).
      • "lon"  (B_tk ≥ 60m)  : trả dict CẢNH BÁO ngoài phạm vi đề tài
        (khuyen_nghi_pa1/pa2, ly_do_ngoai_pham_vi, de_xuat) — KHÔNG có các
        key pa1_chi_phi/pa2_my_quan/pa3_ml, không tính toán chi tiết.
    Khoảng nhỏ: H, B, S lấy từ BEAM_CATALOG, không tính bằng công thức.
    Chi tiết hình học dầm do người dùng dựng ở tab BeamBuilder (module 17).
    """
    khoang = _phan_loai_khoang_tinh_khong(B_tk, goc)

    # ── KHOẢNG LỚN: ngoài phạm vi đề tài — chỉ cảnh báo, KHÔNG sinh PA ──
    if khoang["khoang"] == "lon":
        canh_bao = _predict_khoang_lon(B_tk, goc, B_cau)
        canh_bao["khoang_tinh_khong"] = khoang
        return canh_bao

    # ── KHOẢNG TRUNG: Super-T mở rộng xà mũ / dầm hộp đúc hẫng ──────────
    if khoang["khoang"] == "trung":
        pa1 = _predict_pa1_khoang_trung(B_tk, goc, B_cau, L_cau_tong)
        pa2 = _predict_pa2_khoang_trung(B_tk, goc, B_cau, L_cau_tong)
        # PA3: Random Forest chưa huấn luyện cho khoảng trung → fallback RB
        pa3 = dict(pa2)
        pa3["phuong_phap"] = "Rule-Based (fallback ML — khoảng trung)"
        pa3["ghi_chu"] = ("Random Forest chưa huấn luyện cho khoảng trung, "
                          "dùng PA2 dầm hộp đúc hẫng làm khuyến nghị. "
                          + pa2["ghi_chu"])
        return {
            "pa1_chi_phi":        pa1,
            "pa2_my_quan":        pa2,
            "pa3_ml":             pa3,
            "khoang_tinh_khong":  khoang,
        }

    # ── KHOẢNG NHỎ: luồng hiện tại (catalog dầm giản đơn + ML) ──────────
    return {
        # PA1 = tối ưu CHI PHÍ: nhóm KHÔNG bản đáy liền mạch, nhịp dài ít trụ
        "pa1_chi_phi": _predict_rb_chi_phi(B_tk, goc, B_cau, L_cau_tong),
        # PA2 = tối ưu MỸ QUAN: nhóm CÓ bản đáy liền mạch (đô thị/cầu vượt)
        "pa2_my_quan": _predict_rb_my_quan(B_tk, goc, B_cau, L_cau_tong),
        # PA3 = Machine Learning (Random Forest, Bridge_Train_v3) + catalog
        "pa3_ml":      _predict_ml(B_tk, H_tk, goc, B_cau, moi_truong,
                                   L_cau_tong, models),
        "khoang_tinh_khong": khoang,
    }


def _predict_rb_nhip_ngan(B_tk, goc, B_cau, L_cau_tong=None):
    """
    PA1 — Nhịp NGẮN nhất, NHIỀU trụ.

    Chọn chiều dài định hình catalog nhỏ nhất thỏa điều kiện tĩnh không
    (_L_nhip_min) → bám tĩnh không, đổi tĩnh không thì nhịp đổi theo. Đây cũng là
    phương án mặc định của 'cầu tổng'. Dùng chung lõi với predict_kcn_default,
    chỉ khác nhãn hiển thị.
    """
    pa = predict_kcn_default(B_tk, goc, B_cau, L_cau_tong)
    pa["phuong_phap"] = "Rule-Based (Nhịp ngắn — nhiều trụ)"
    pa["ghi_chu"] = (f"Nhịp NGẮN nhất thỏa tĩnh không (nhiều trụ): "
                     f"{pa['loai_dam']} L={pa['chieu_dai']:g}m, "
                     f"{pa['tong_so_nhip']} nhịp.")
    return pa


def predict_kcn_default(B_tk, goc, B_cau, L_cau_tong=None):
    """
    Phương án MẶC ĐỊNH cho 'cầu tổng' — nhịp **bám tĩnh không**.

    Khác với predict_kcn (luôn trả PA1 tối ưu chi phí → chọn dầm DÀI NHẤT, vì
    vậy chiều dài nhịp luôn kẹt ở 38.2m bất kể tĩnh không), hàm này chọn chiều
    dài định hình catalog NHỎ NHẤT thỏa điều kiện tĩnh không (_L_nhip_min). Đổi
    tĩnh không (B_tk / góc) → chiều dài nhịp đổi theo ngay. Người dùng có thể
    tăng nhịp bằng cách gán dầm dài hơn từ thư viện (ghi đè qua span_layout).

    Trả về dict cùng cấu trúc với một phương án của predict_kcn.
    """
    L_min   = _L_nhip_min(B_tk, goc)
    elig    = [l for l in STD_LENGTHS if l >= L_min - 1e-6]
    L_def   = float(min(elig)) if elig else float(max(STD_LENGTHS))

    # Dầm catalog gần chiều dài định hình nhất (lấy H/B/S/công nghệ thực tế)
    loai, L_cat, B_cat, H_cat, S_cat, cong_nghe = get_beam_from_catalog(L_def)[:6]

    n_nhip = _n_nhip_from(L_cau_tong, L_def) if (L_cau_tong and L_cau_tong > 0) else 1

    n_dam = max(2, int(B_cau / S_cat) + 1)
    oh = round((B_cau - (n_dam - 1) * S_cat) / 2, 2)
    if oh < 0.15:
        n_dam = max(2, n_dam - 1)
        oh = round((B_cau - (n_dam - 1) * S_cat) / 2, 2)
    if oh > max(1.2, 0.8 * S_cat):
        n_dam += 1
        oh = round((B_cau - (n_dam - 1) * S_cat) / 2, 2)

    return {
        "loai_dam":        loai,
        "chieu_dai":       L_def,
        "chieu_cao_dam":   H_cat,
        "be_rong_dam":     B_cat,
        "khoang_cach_dam": S_cat,
        "tong_so_nhip":    n_nhip,
        "so_luong_dam":    n_dam,
        "overhang":        max(0.10, oh),
        "ti_le_L_H":       round(L_def / H_cat, 1) if H_cat > 0 else 0,
        "cong_nghe":       cong_nghe,
        "phuong_phap":     "Mặc định (bám tĩnh không)",
        "ghi_chu":         (f"Nhịp định hình nhỏ nhất thỏa tĩnh không: {loai} "
                            f"L={L_def:g}m, {n_nhip} nhịp."),
    }


# ---------------------------------------------------------------------------
# 6. CHẤM ĐIỂM PHƯƠNG ÁN (100 ĐIỂM)
# ---------------------------------------------------------------------------

# Hệ số suất đầu tư tương đối tham chiếu QĐ 409/QĐ-BXD 2025
_COST_COEFF = {
    "Dầm bản rỗng": 0.80,
    "T ngược":       0.90,
    "Dầm I":         1.00,   # DUL trước; DUL sau → 1.10 (kiểm tra qua cong_nghe)
    "Dầm T":         1.05,
    "Super-T":       1.20,
    "Dầm bản":       0.78,
}


def _classify_env(moi_truong, B_tk, L_min_geo):
    """
    Phân loại môi trường cầu để dùng trong tiêu chí A4.

    Returns
    -------
    str : 'urban' | 'rural' | 'large_river' | 'medium'
    """
    mt = moi_truong.lower()
    if any(k in mt for k in ("đô thị", "do thi", "nội thành", "urban")):
        return "urban"
    if any(k in mt for k in ("nông thôn", "nong thon",
                              "cấp iv", "cap iv", "cấp v", "cấp vi")):
        return "rural"
    if any(k in mt for k in ("sông lớn", "song lon",
                              "cấp i", "cap i", "cấp ii", "cấp iii")):
        return "large_river"
    # Suy ra từ hình học khi không có từ khoá rõ ràng
    if L_min_geo >= 28 or B_tk >= 30:
        return "large_river"
    if B_tk <= 12:
        return "rural"
    return "medium"


def _score_single_plan(pa, B_tk, goc, moi_truong):
    """
    Chấm điểm các tiêu chí độc lập cho một phương án
    (A1–A5, B3, C1, C2 — không cần so sánh với phương án khác).

    Parameters
    ----------
    pa         : dict  — một phương án từ predict_kcn()
    B_tk       : float — bề rộng tĩnh không (m)
    goc        : float — góc giao chéo (°)
    moi_truong : str   — môi trường

    Returns
    -------
    dict : { 'A1': int, 'A2': int, ..., 'C2': int }
    """
    loai      = pa["loai_dam"]
    L         = pa["chieu_dai"]
    H         = pa["chieu_cao_dam"]
    n_nhip    = pa["tong_so_nhip"]
    cong_nghe = pa["cong_nghe"]

    # ── A1: Khả năng vượt nhịp (15 điểm) ─────────────────────────────────
    L_min = B_tk / np.sin(np.radians(max(goc, 30))) + 2.0
    if L >= L_min:
        a1 = 15 if L <= L_min * 1.2 else 10   # dư >20% → trừ 5
    else:
        a1 = 0

    # ── A2: Tỉ lệ L/H theo TCVN 11823-2:2017 Bảng 2 (10 điểm) ──────────
    # Dầm giản đơn, Bê tông dự ứng lực.
    # H trong catalog là chiều cao dầm (chưa gồm bản mặt cầu ~0.18m),
    # nên ngưỡng giới hạn được nới thêm biên độ +10% so với lý thuyết.
    #   Nhóm Bản (H_min = 0.030L) → L/H_lý_thuyết ≤ 33.3 → cho phép ≤ 37
    #   Nhóm Dầm I đúc sẵn (H_min = 0.045L) → L/H_lý_thuyết ≤ 22.2 → cho phép ≤ 25
    #   T ngược: không có trong bảng, dùng tương tự Bản per TCVN
    _BAN = {"Dầm bản", "Dầm bản rỗng", "T ngược"}   # H_min = 0.030L
    ratio = L / H if H > 0 else 0
    if loai in _BAN:
        if 20 <= ratio <= 33:
            a2 = 10   # tối ưu — dầm bản hoạt động theo cơ chế bản, L/H cao là bình thường
        elif (15 <= ratio < 20) or (33 < ratio <= 37):
            a2 = 6    # chấp nhận (biên độ bù bản mặt cầu)
        elif (12 <= ratio < 15) or (37 < ratio <= 42):
            a2 = 3    # cần xem xét
        else:
            a2 = 0    # vi phạm TCVN hoặc quá dày
    else:             # Dầm I, Super-T, Dầm T — H_min = 0.045L
        if 15 <= ratio <= 22:
            a2 = 10   # tối ưu
        elif (12 <= ratio < 15) or (22 < ratio <= 25):
            a2 = 6    # chấp nhận
        elif (10 <= ratio < 12) or (25 < ratio <= 28):
            a2 = 3    # cần xem xét
        else:
            a2 = 0    # vi phạm TCVN hoặc quá dày

    # ── A3: Số trụ giữa sông (15 điểm) ───────────────────────────────────
    n_tru   = n_nhip - 1
    _a3_tbl = {0: 15, 1: 12, 2: 9, 3: 6, 4: 3}
    a3      = _a3_tbl.get(n_tru, 1)

    # ── A4: Phù hợp điều kiện môi trường (10 điểm) ───────────────────────
    env = _classify_env(moi_truong, B_tk, L_min)
    if env == "urban" and loai in ("Dầm bản rỗng", "T ngược"):
        a4 = 10
    elif env == "large_river" and loai in ("Super-T", "Dầm I"):
        a4 = 10
    elif env == "rural" and loai in ("Dầm I", "T ngược"):
        a4 = 8
    elif loai == "Super-T" and L < 20:
        a4 = 0   # Super-T dùng cho nhịp quá ngắn
    elif loai in ("Dầm bản rỗng", "Dầm bản", "T ngược") and env == "large_river":
        a4 = 2   # dầm thấp/mảnh cho sông lớn — không phù hợp
    else:
        a4 = 5   # trung tính

    # ── A5: Độ phức tạp thi công (10 điểm) ───────────────────────────────
    if loai in ("Dầm bản rỗng", "T ngược", "Dầm bản"):
        a5 = 10   # định hình phổ biến, sẵn có tại địa phương
    elif loai in ("Dầm I", "Dầm T"):
        a5 = 10 if cong_nghe == "DUL_truoc" else 7
    elif loai == "Super-T":
        a5 = 7    # cần đặt trước hoặc vận chuyển từ nhà máy lớn
    else:
        a5 = 4    # đặc biệt / đúc tại chỗ
    if goc < 60:
        a5 = max(0, a5 - 3)   # cầu xiên tăng độ phức tạp

    # ── B3: Chi phí bảo trì (5 điểm) ─────────────────────────────────────
    b3 = 5 if cong_nghe == "DUL_sau" else 3
    if n_nhip >= 4:
        b3 = max(0, b3 - 1)   # nhiều nhịp → nhiều gối & khe nối

    # ── C1: Chiều cao kết cấu nhịp (6 điểm) ──────────────────────────────
    if H < 0.75:
        c1 = 6
    elif H <= 1.20:
        c1 = 4
    elif H <= 1.75:
        c1 = 2
    else:
        c1 = 1

    # ── C2: Thống nhất kiểu dầm (4 điểm) ────────────────────────────────
    # Mỗi phương án dùng một loại dầm duy nhất → luôn đạt tối đa
    c2 = 4

    return {"A1": a1, "A2": a2, "A3": a3, "A4": a4, "A5": a5,
            "B3": b3, "C1": c1, "C2": c2}


def _score_b1_b2(pa_list, B_cau):
    """
    Chấm điểm tương đối B1 (chi phí kết cấu nhịp, 15 điểm) và
    B2 (chi phí phần dưới, 10 điểm) cho 3 phương án.

    Quy tắc: phương án rẻ nhất → điểm tối đa; đắt nhất → điểm tối thiểu;
    nội suy tuyến tính. Khi 3 phương án bằng nhau → tất cả nhận điểm tối đa
    (không có sự khác biệt để phân biệt).

    Parameters
    ----------
    pa_list : list[dict] — [pa1, pa2, pa3]
    B_cau   : float      — bề rộng mặt cầu (m)

    Returns
    -------
    (list[int], list[int]) : b1_scores, b2_scores tương ứng với pa_list
    """
    costs_nhip = []
    costs_tru  = []

    for pa in pa_list:
        loai      = pa["loai_dam"]
        L         = pa["chieu_dai"]
        n         = pa["tong_so_nhip"]
        cong_nghe = pa["cong_nghe"]

        coeff = _COST_COEFF.get(loai, 1.0)
        if loai == "Dầm I" and cong_nghe == "DUL_sau":
            coeff = 1.10
        costs_nhip.append(coeff * L * B_cau * n)
        costs_tru.append(float(n - 1))   # H_tru giống nhau → bỏ qua

    def _linear(vals, score_lo, score_hi):
        lo, hi = min(vals), max(vals)
        if hi == lo:
            return [score_hi] * len(vals)
        return [round(score_hi - (v - lo) / (hi - lo) * (score_hi - score_lo))
                for v in vals]

    return _linear(costs_nhip, 5, 15), _linear(costs_tru, 0, 10)


def score_kcn_plans(plans, B_tk, goc, B_cau, moi_truong):
    """
    Chấm điểm 3 phương án kết cấu nhịp theo bộ tiêu chí 100 điểm.

    Parameters
    ----------
    plans      : dict  — kết quả từ predict_kcn()
    B_tk       : float — bề rộng tĩnh không (m)
    goc        : float — góc giao chéo (°)
    B_cau      : float — bề rộng mặt cầu (m)
    moi_truong : str   — môi trường

    Returns
    -------
    dict : {
        'pa1_chi_phi': {
            'A1': int, 'A2': int, 'A3': int, 'A4': int, 'A5': int,
            'B1': int, 'B2': int, 'B3': int, 'C1': int, 'C2': int,
            'tong': int, 'xep_loai': str, 'khuyen_nghi': str,
        },
        'pa2_my_quan': { ... },
        'pa3_ml':      { ... },
    }
    """
    # pa3_ai = key cũ (dữ liệu đã lưu trước khi đổi tên PA3 → Machine Learning)
    pa_keys = [k for k in ("pa1_chi_phi", "pa2_my_quan", "pa3_ml", "pa3_ai")
               if k in plans]
    pa_list = [plans[k] for k in pa_keys]

    indep_scores      = [_score_single_plan(pa, B_tk, goc, moi_truong) for pa in pa_list]
    b1_list, b2_list  = _score_b1_b2(pa_list, B_cau)

    _rank = [
        (85, "Xuất sắc",   "Đề xuất chọn"),
        (70, "Tốt",        "Chấp nhận"),
        (55, "Trung bình", "Cân nhắc thêm"),
        ( 0, "Kém",        "Không khuyến nghị"),
    ]

    result = {}
    for i, key in enumerate(pa_keys):
        s = dict(indep_scores[i])
        s["B1"] = b1_list[i]
        s["B2"] = b2_list[i]
        s["tong"] = sum(s[k] for k in
                        ("A1", "A2", "A3", "A4", "A5",
                         "B1", "B2", "B3", "C1", "C2"))
        for threshold, xl, kn in _rank:
            if s["tong"] >= threshold:
                s["xep_loai"]    = xl
                s["khuyen_nghi"] = kn
                break
        result[key] = s

    return result


# ---------------------------------------------------------------------------
# CHẠY THỬ ĐỘC LẬP
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print("=== Huấn luyện mô hình Kết cấu nhịp (v3) ===")
    mdl = train_kcn_ai()
    if mdl is None:
        print("Chưa có dữ liệu train — PA3 dùng fallback catalog.")
    else:
        print(f"Đã học từ {mdl['n_samples']} mẫu | features: {mdl['feat_cols']}")
        print(f"Các loại dầm: {list(mdl['le_type'].classes_)}")

    B_tk, H_tk, goc = 15, 3.5, 90
    B_cau, L_cau_tong, moi_truong = 12, 80, "Vượt sông"

    print(f"\n=== Dự đoán: B_tk={B_tk}, H_tk={H_tk}, goc={goc}°, "
          f"B_cau={B_cau}, L_tong={L_cau_tong}m, MT={moi_truong} ===")
    res = predict_kcn(B_tk=B_tk, H_tk=H_tk, goc=goc, B_cau=B_cau,
                      moi_truong=moi_truong, L_cau_tong=L_cau_tong, models=mdl)

    for pa_name, pa in res.items():
        print(f"\n{'─'*52}")
        print(f"  {pa_name.upper()}")
        print(f"{'─'*52}")
        for k, v in pa.items():
            print(f"  {k:<22}: {v}")

    print(f"\n{'='*52}")
    print("  CHẤM ĐIỂM 3 PHƯƠNG ÁN (100 ĐIỂM)")
    print(f"{'='*52}")
    sc = score_kcn_plans(res, B_tk=B_tk, goc=goc, B_cau=B_cau,
                         moi_truong=moi_truong)

    _labels = {
        "A1": "A1 Vượt nhịp        /15",
        "A2": "A2 Tỉ lệ L/H        /10",
        "A3": "A3 Số trụ sông      /15",
        "A4": "A4 Môi trường       /10",
        "A5": "A5 Thi công         /10",
        "B1": "B1 Chi phí nhịp     /15",
        "B2": "B2 Chi phí phần dưới/10",
        "B3": "B3 Bảo trì           /5",
        "C1": "C1 Chiều cao dầm     /6",
        "C2": "C2 Thống nhất        /4",
    }
    pa_keys = list(sc.keys())
    print(f"  {'Tiêu chí':<30} {'PA1':>5} {'PA2':>5} {'PA3':>5}")
    print(f"  {'─'*30} {'─'*5} {'─'*5} {'─'*5}")
    for key, lbl in _labels.items():
        vals = [sc[p][key] for p in pa_keys]
        print(f"  {lbl:<30} {vals[0]:>5} {vals[1]:>5} {vals[2]:>5}")
    print(f"  {'─'*30} {'─'*5} {'─'*5} {'─'*5}")
    totals = [sc[p]["tong"] for p in pa_keys]
    print(f"  {'TỔNG ĐIỂM':<30} {totals[0]:>5} {totals[1]:>5} {totals[2]:>5}")
    print()
    for p in pa_keys:
        print(f"  {p}: {sc[p]['xep_loai']} — {sc[p]['khuyen_nghi']}")
