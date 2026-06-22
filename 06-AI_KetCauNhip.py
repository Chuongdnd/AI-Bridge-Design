"""
Module 06 — AI Kết cấu nhịp (Span Structure AI)
Data  : Bridge_Train_Dataset_v3.xlsx — sheet 07_Kết cấu nhịp + 02 + 03
Features: B_tk, H_tk, Goc_xien, B_cau, Moi_truong
Labels  : Loai_dam (classifier) + L_dam, H_dam, Kc_dam, SL_dam (regressors)
Fallback: Rule-Based từ BEAM_CATALOG khi chưa có dữ liệu train

Phương án dự đoán:
  PA1 — Rule-Based tối ưu chi phí  (_predict_rb_chi_phi)
  PA2 — Rule-Based tối ưu mỹ quan  (_predict_rb_my_quan)
  PA3 — AI + tra catalog           (_predict_ai)
"""

import os
import sys
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score
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


def _n_nhip_from(L_cau, L_span):
    """Số nhịp khi chia cầu thành các nhịp ĐỀU = L_span (định hình catalog).
    Dùng làm tròn về số nhịp gần nhất (khớp cách bố trí của module vẽ 11)."""
    if not L_cau or L_cau <= 0 or not L_span or L_span <= 0:
        return 1
    return max(1, int(round(L_cau / L_span)))


# ---------------------------------------------------------------------------
# CATALOG DẦM BTCT THEO KINH NGHIỆM THỰC TẾ VN
# ---------------------------------------------------------------------------
BEAM_CATALOG = [
    # (loai_dam,         L,     B,    H,    S,    cong_nghe)
    ("Dầm bản",          9.00, 0.99, 0.40, 1.00, "DUL_truoc"),
    ("Dầm bản rỗng",    12.00, 0.99, 0.50, 1.00, "DUL_truoc"),
    ("Dầm bản rỗng",    18.00, 0.99, 0.65, 1.00, "DUL_truoc"),
    ("Dầm bản rỗng",    20.00, 0.99, 0.75, 1.00, "DUL_truoc"),
    ("Dầm bản rỗng",    21.00, 0.99, 0.80, 1.00, "DUL_truoc"),
    ("Dầm bản rỗng",    24.00, 0.99, 0.95, 1.00, "DUL_truoc"),
    ("Dầm I",            6.00, 0.16, 0.28, 1.50, "DUL_truoc"),
    ("Dầm I",            9.00, 0.20, 0.40, 1.50, "DUL_truoc"),
    ("Dầm I",           12.50, 0.32, 0.56, 1.50, "DUL_truoc"),
    ("Dầm I",           15.00, 0.22, 0.50, 1.50, "DUL_truoc"),
    ("Dầm I",           15.00, 0.45, 1.00, 2.25, "DUL_sau"),
    ("Dầm I",           18.60, 0.43, 0.70, 1.50, "DUL_truoc"),
    ("Dầm I",           20.70, 0.60, 1.20, 2.25, "DUL_sau"),
    ("Dầm I",           24.54, 0.56, 1.14, 1.75, "DUL_truoc"),
    ("Dầm I",           33.00, 0.50, 1.40, 2.40, "DUL_truoc"),
    ("Dầm I",           33.00, 0.65, 1.65, 2.25, "DUL_sau"),
    ("Dầm T",           12.00, 1.80, 0.90, 2.40, "DUL_truoc"),
    ("Dầm T",           15.00, 1.80, 1.00, 2.40, "DUL_truoc"),
    ("T ngược",         10.00, 0.98, 0.55, 1.00, "DUL_truoc"),
    ("T ngược",         12.00, 0.98, 0.55, 1.00, "DUL_truoc"),
    ("T ngược",         15.00, 0.98, 0.55, 1.00, "DUL_truoc"),
    ("T ngược",         18.00, 0.98, 0.75, 1.00, "DUL_truoc"),
    ("T ngược",         20.00, 0.98, 0.75, 1.00, "DUL_truoc"),
    ("T ngược",         25.00, 0.98, 0.90, 1.00, "DUL_truoc"),
    ("T ngược",         29.00, 0.98, 1.10, 1.00, "DUL_truoc"),
    ("Super-T",         28.20, 0.70, 1.75, 2.44, "DUL_sau"),
    ("Super-T",         35.70, 0.70, 1.75, 2.44, "DUL_sau"),
    ("Super-T",         38.20, 0.70, 1.75, 2.44, "DUL_sau"),
]


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
    tuple : (loai_dam, L, B, H, S, cong_nghe)
    """
    if loai_dam:
        filtered = [r for r in BEAM_CATALOG if r[0] == loai_dam]
        if filtered:
            return min(filtered, key=lambda r: abs(r[1] - L_target))
    return min(BEAM_CATALOG, key=lambda r: abs(r[1] - L_target))


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

    L_ai_raw  = float(models["reg_L"].predict(X_row)[0])
    L_min_geo = _L_nhip_min(B_tk, goc)
    L_ai_raw  = max(L_ai_raw, L_min_geo)
    L_ai_std  = _snap_length(L_ai_raw)
    # Chỉ xét nhịp định hình ≥ điều kiện tĩnh không (nhịp chính không vi phạm TK).
    # Toàn cầu dùng MỘT chiều dài định hình duy nhất → các nhịp đều nhau.
    possible_L = sorted({l for l in STD_LENGTHS if l >= L_min_geo - 1e-6} | {L_ai_std})
    possible_L = [l for l in possible_L if l >= L_min_geo - 1e-6] or [L_ai_std]

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
def _predict_rb_chi_phi(B_tk, goc, B_cau, L_cau_tong):
    """
    PA1 — Tối ưu chi phí xây dựng (Rule-Based từ BEAM_CATALOG).

    Chiến lược chấm điểm:
      - Ít trụ nhất (n_nhip nhỏ) → tiết kiệm chi phí phần dưới (trọng số cao nhất)
      - Nhịp dài hơn (L lớn) → ít dầm tổng thể hơn
      - Khoảng cách dầm S lớn → ít dầm trên mỗi mặt cắt ngang

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

    eligible = [r for r in BEAM_CATALOG if r[1] >= L_min_geo - 1e-6]
    if not eligible:
        eligible = BEAM_CATALOG

    best_score = -1e9
    best_record = None
    best_n_nhip = 1

    for record in eligible:
        loai, L, B, H, S, cong_nghe = record
        n_nhip = _n_nhip_from(L_cau, L) if L_cau else 1

        # Scoring: ít nhịp (ít trụ) → ưu tiên cao nhất; nhịp dài → thứ hai; S lớn → thứ ba
        score = (1.0 / n_nhip) * 100.0 + L * 1.0 + S * 5.0

        if score > best_score:
            best_score = score
            best_record = record
            best_n_nhip = n_nhip

    loai, L, B, H, S, cong_nghe = best_record

    n_dam = max(2, int(B_cau / S) + 1)
    oh = round((B_cau - (n_dam - 1) * S) / 2, 2)
    if oh < 0.15:
        n_dam = max(2, n_dam - 1)
        oh = round((B_cau - (n_dam - 1) * S) / 2, 2)
    if oh > max(1.2, 0.8 * S):
        n_dam += 1
        oh = round((B_cau - (n_dam - 1) * S) / 2, 2)

    return {
        "loai_dam":        loai,
        "chieu_dai":       L,
        "chieu_cao_dam":   H,
        "be_rong_dam":     B,
        "khoang_cach_dam": S,
        "tong_so_nhip":    best_n_nhip,
        "so_luong_dam":    n_dam,
        "overhang":        max(0.10, oh),
        "ti_le_L_H":       round(L / H, 1) if H > 0 else 0,
        "cong_nghe":       cong_nghe,
        "phuong_phap":     "Rule-Based (Chi phí)",
        "ghi_chu":         (f"Tối ưu ít trụ: {loai} L={L}m, "
                            f"{best_n_nhip} nhịp, S={S}m."),
    }


def _predict_rb_my_quan(B_tk, goc, B_cau, L_cau_tong):
    """
    PA2 — Tối ưu mỹ quan (Rule-Based từ BEAM_CATALOG).

    Chiến lược chấm điểm:
      - H nhỏ nhất → kết cấu nhịp thấp, thông thoáng (ưu tiên hàng đầu)
      - Ưu tiên loại dầm bản rỗng và T ngược (tỉ lệ H/L nhỏ)
      - Chấp nhận nhiều nhịp hơn nếu đổi lại được chiều cao thấp hơn
        (phạt số nhịp nhẹ hơn PA1)

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

    eligible = [r for r in BEAM_CATALOG if r[1] >= L_min_geo - 1e-6]
    if not eligible:
        eligible = BEAM_CATALOG

    best_score = -1e9
    best_record = None
    best_n_nhip = 1

    for record in eligible:
        loai, L, B, H, S, cong_nghe = record
        n_nhip = _n_nhip_from(L_cau, L) if L_cau else 1

        # Scoring: H nhỏ → điểm cao; bonus dầm bản rỗng và T ngược; phạt nhẹ số nhịp
        score = -H * 50.0
        if loai in ("Dầm bản rỗng", "T ngược"):
            score += 30.0
        score -= n_nhip * 3.0

        if score > best_score:
            best_score = score
            best_record = record
            best_n_nhip = n_nhip

    loai, L, B, H, S, cong_nghe = best_record

    n_dam = max(2, int(B_cau / S) + 1)
    oh = round((B_cau - (n_dam - 1) * S) / 2, 2)
    if oh < 0.15:
        n_dam = max(2, n_dam - 1)
        oh = round((B_cau - (n_dam - 1) * S) / 2, 2)
    if oh > max(1.2, 0.8 * S):
        n_dam += 1
        oh = round((B_cau - (n_dam - 1) * S) / 2, 2)

    return {
        "loai_dam":        loai,
        "chieu_dai":       L,
        "chieu_cao_dam":   H,
        "be_rong_dam":     B,
        "khoang_cach_dam": S,
        "tong_so_nhip":    best_n_nhip,
        "so_luong_dam":    n_dam,
        "overhang":        max(0.10, oh),
        "ti_le_L_H":       round(L / H, 1) if H > 0 else 0,
        "cong_nghe":       cong_nghe,
        "phuong_phap":     "Rule-Based (Mỹ quan)",
        "ghi_chu":         (f"Tối ưu chiều cao thấp: {loai} L={L}m, "
                            f"H={H}m, {best_n_nhip} nhịp."),
    }


def _predict_ai(B_tk, H_tk, goc, B_cau, moi_truong, L_cau_tong, models):
    """
    PA3 — AI dự đoán loại dầm + chiều dài, sau đó tra BEAM_CATALOG để lấy
    H, B, S thực tế thay vì dùng công thức.

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
        loai_cat, L_cat, B_cat, H_cat, S_cat, cong_nghe = best_record
        L_cau_actual = float(L_cau_tong) if L_cau_tong else L_cat
        n_nhip_cat = _n_nhip_from(L_cau_actual, L_cat)
        ghi_chu = (f"Chưa có mô hình AI — catalog L/H≈18: "
                   f"{loai_cat} L={L_cat}m, {n_nhip_cat} nhịp.")
        phuong_phap = "Catalog (chưa có AI)"
    else:
        loai_ai, L_ai, _, _ = _predict_optimize(
            B_tk, H_tk, goc, B_cau, moi_truong, L_cau_tong, models
        )
        # Nhịp chính không vi phạm tĩnh không → bảo đảm L tra catalog ≥ L_min_geo
        best_record = get_beam_from_catalog(max(L_ai, L_min_geo), loai_dam=loai_ai)
        loai_cat, L_cat, B_cat, H_cat, S_cat, cong_nghe = best_record
        if L_cat < L_min_geo - 1e-6:
            elig = [r for r in BEAM_CATALOG if r[1] >= L_min_geo - 1e-6]
            if elig:
                best_record = min(elig, key=lambda r: r[1])
                loai_cat, L_cat, B_cat, H_cat, S_cat, cong_nghe = best_record
        L_cau_actual = float(L_cau_tong) if L_cau_tong else L_cat
        n_nhip_cat = _n_nhip_from(L_cau_actual, L_cat)
        ghi_chu = (f"AI: {loai_ai} L≈{L_ai:.1f}m → "
                   f"Catalog: {loai_cat} L={L_cat}m, {n_nhip_cat} nhịp.")
        phuong_phap = "AI + Catalog"

    n_dam = max(2, int(B_cau / S_cat) + 1)
    oh = round((B_cau - (n_dam - 1) * S_cat) / 2, 2)
    if oh < 0.15:
        n_dam = max(2, n_dam - 1)
        oh = round((B_cau - (n_dam - 1) * S_cat) / 2, 2)
    if oh > max(1.2, 0.8 * S_cat):
        n_dam += 1
        oh = round((B_cau - (n_dam - 1) * S_cat) / 2, 2)

    return {
        "loai_dam":        loai_cat,
        "chieu_dai":       L_cat,
        "chieu_cao_dam":   H_cat,
        "be_rong_dam":     B_cat,
        "khoang_cach_dam": S_cat,
        "tong_so_nhip":    n_nhip_cat,
        "so_luong_dam":    n_dam,
        "overhang":        max(0.10, oh),
        "ti_le_L_H":       round(L_cat / H_cat, 1) if H_cat > 0 else 0,
        "cong_nghe":       cong_nghe,
        "phuong_phap":     phuong_phap,
        "ghi_chu":         ghi_chu,
    }


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
                         overhang, ti_le_L_H, cong_nghe, phuong_phap, ghi_chu },
        "pa2_my_quan": { ... },
        "pa3_ai":      { ... },
      }
    Tất cả giá trị H, B, S đều lấy từ BEAM_CATALOG, không tính bằng công thức.
    Chi tiết hình học dầm do người dùng dựng ở tab BeamBuilder (module 17).
    """
    return {
        "pa1_chi_phi": _predict_rb_chi_phi(B_tk, goc, B_cau, L_cau_tong),
        "pa2_my_quan": _predict_rb_my_quan(B_tk, goc, B_cau, L_cau_tong),
        "pa3_ai":      _predict_ai(B_tk, H_tk, goc, B_cau, moi_truong,
                                   L_cau_tong, models),
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
        'pa3_ai':      { ... },
    }
    """
    pa_keys = ["pa1_chi_phi", "pa2_my_quan", "pa3_ai"]
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
