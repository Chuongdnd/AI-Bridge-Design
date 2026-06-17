"""
Module 06 — AI Kết cấu nhịp (Span Structure AI)
Data  : Bridge_Train_Dataset_v3.xlsx — sheet 07_Kết cấu nhịp + 02 + 03
Features: B_tk, H_tk, Goc_xien, B_cau, Moi_truong
Labels  : Loai_dam (classifier) + L_dam, H_dam, Kc_dam, SL_dam (regressors)
Fallback: Rule-Based khi chưa có dữ liệu train
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
# 3. HÀM DỰ ĐOÁN NỘI BỘ
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


def _calc_girder_layout(dam_type, L_span, B_cau, models):
    """Tính khoảng cách và số lượng dầm."""
    le_type = models["le_type"]
    t_enc = le_type.transform([dam_type])[0] if dam_type in le_type.classes_ else 0

    if "reg_kc" in models:
        X_kc = [[t_enc, B_cau]] if models.get("kc_has_Bcau") else [[t_enc]]
        kc = float(models["reg_kc"].predict(X_kc)[0])
        kc = max(0.8, min(kc, 3.0))
    else:
        # Quy tắc kinh nghiệm
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
    Hàm điểm cho tối ưu hóa tổ hợp (loại dầm × chiều dài nhịp).

    Nguyên tắc chấm điểm:
    1. Ít trụ → tiết kiệm chi phí (tối đa 60 pt)
    2. Chiều dài nhịp phù hợp với bề rộng tĩnh không B_tk (tối đa 30 pt)
       - B_tk nhỏ (cầu nhỏ): nhịp ngắn 12–24m tối ưu kinh tế
       - B_tk trung bình:     nhịp 24–38m
       - B_tk lớn:            nhịp 33–40m
    3. Loại dầm phù hợp với chiều dài nhịp (tối đa 35 pt)
       - Dầm bản:  L ≤ 15m
       - T ngược:  12 ≤ L ≤ 22m
       - Dầm I:    18 ≤ L ≤ 33m
       - Super-T:  27 ≤ L ≤ 40m
    4. Tỉ lệ L/H tối ưu kết cấu 17–22 (tối đa 15 pt)
    """
    score = 0.0

    # ── 1. Ít trụ ──────────────────────────────────────────────────────────
    if L_cau_tong and L_cau_tong > 0:
        score += 60.0 / max(n_nhip, 1)
    else:
        score += 50.0

    # ── 2. Dải nhịp tối ưu theo B_tk ──────────────────────────────────────
    if B_tk is not None and B_tk <= 10:
        # Cầu nhỏ (kênh, sông nhỏ cấp V–VI): nhịp ngắn tối ưu
        if 12 <= L_span <= 24:
            score += 30
        elif 24 < L_span <= 33:
            score += 12
        # nhịp > 33m với cầu nhỏ: lãng phí → không thưởng
    elif B_tk is not None and B_tk <= 22:
        # Cầu trung bình (cấp IV–V)
        if 24 <= L_span <= 38:
            score += 30
        elif 18 <= L_span < 24 or 38 < L_span <= 42:
            score += 15
    else:
        # Cầu lớn (cấp I–III) hoặc B_tk không biết
        if 33 <= L_span <= 40:
            score += 30
        elif 25 <= L_span < 33 or 40 < L_span <= 45:
            score += 15

    # ── 3. Phù hợp loại dầm ↔ chiều dài nhịp ──────────────────────────────
    if dam_type == "Dầm bản" and L_span <= 15:
        score += 35
    elif dam_type == "T ngược" and 12 <= L_span <= 22:
        score += 33
    elif dam_type == "Dầm I" and 18 <= L_span <= 33:
        score += 30
    elif dam_type == "Super-T" and 27 <= L_span <= 40:
        score += 35
    elif dam_type in {"Super-T", "Dầm I"}:
        score += 8   # phổ biến nhưng nhịp không tối ưu

    # ── 4. Tỉ lệ L/H ───────────────────────────────────────────────────────
    if h_dam > 0:
        ratio = L_span / h_dam
        if 17 <= ratio <= 22:
            score += 15
        elif 15 <= ratio <= 25:
            score += 8

    return score


# ---------------------------------------------------------------------------
# 4. PHƯƠNG THỨC DỰ ĐOÁN
# ---------------------------------------------------------------------------
def _predict_single(B_tk, H_tk, goc, B_cau, moi_truong, models):
    """Dự đoán một cấu hình dầm đơn từ mô hình."""
    X_row = _build_x_row(B_tk, H_tk, goc, B_cau, moi_truong, models)
    le_type = models["le_type"]

    t_idx = models["clf_type"].predict(X_row)[0]
    loai_dam = str(le_type.inverse_transform([t_idx])[0]).strip()

    L_raw = float(models["reg_L"].predict(X_row)[0])
    # Đảm bảo nhịp đủ vuợt tĩnh không
    L_min_geo = (B_tk / np.sin(np.radians(max(goc, 30)))) + 2.0
    L_raw = max(L_raw, L_min_geo)
    L_span = _snap_length(L_raw)

    t_enc_best = le_type.transform([loai_dam])[0] if loai_dam in le_type.classes_ else 0
    H_dam = float(models["reg_H"].predict([[t_enc_best, L_span]])[0])
    H_dam = max(0.5, min(H_dam, 3.5))

    return loai_dam, L_span, H_dam


def _predict_optimize(B_tk, H_tk, goc, B_cau, moi_truong, L_cau_tong, models):
    """Tối ưu hóa tổ hợp loại dầm × chiều dài."""
    le_type = models["le_type"]
    X_row = _build_x_row(B_tk, H_tk, goc, B_cau, moi_truong, models)

    # Tập ứng viên loại dầm
    ai_idx = models["clf_type"].predict(X_row)[0]
    ai_type = str(le_type.inverse_transform([ai_idx])[0]).strip()

    candidate_types = {ai_type}
    # Thêm loại dầm phổ biến theo môi trường
    if "đô thị" in moi_truong.lower() or B_tk <= 20:
        candidate_types.update(["T ngược", "Dầm I"])
    else:
        candidate_types.update(["Super-T", "Dầm I"])
    candidate_types = {t for t in candidate_types if t in le_type.classes_}

    L_ai_raw  = float(models["reg_L"].predict(X_row)[0])
    L_min_geo = (B_tk / np.sin(np.radians(max(goc, 30)))) + 2.0
    L_ai_raw  = max(L_ai_raw, L_min_geo)
    L_ai_std  = _snap_length(L_ai_raw)
    possible_L = sorted({L_ai_std} | {l for l in STD_LENGTHS if l >= L_min_geo * 0.9})

    best_score = -1
    best = None

    for dam_type in candidate_types:
        t_enc = le_type.transform([dam_type])[0]
        for L in possible_L:
            H_dam = float(models["reg_H"].predict([[t_enc, L]])[0])
            H_dam = max(0.5, min(H_dam, 3.5))

            if L_cau_tong and L_cau_tong > 0:
                n_nhip = max(1, int(np.ceil(L_cau_tong / L)))
                L_thuc = L_cau_tong / n_nhip
                if L_thuc > 45:
                    continue
            else:
                n_nhip = 1
                L_thuc = L

            score = _score_candidate(dam_type, L_thuc, n_nhip, H_dam, L_cau_tong, B_tk=B_tk)
            if score > best_score:
                best_score = score
                best = (dam_type, round(L_thuc, 2), n_nhip, H_dam)

    if best is None:
        loai_dam, L_span, H_dam = _predict_single(B_tk, H_tk, goc, B_cau, moi_truong, models)
        n_nhip = max(1, int(np.ceil(L_cau_tong / L_span))) if L_cau_tong else 1
        best = (loai_dam, L_span, n_nhip, H_dam)

    return best


def _predict_rb(B_tk, goc, B_cau, L_cau_tong):
    """Quy tắc kinh nghiệm (rule-based) — dự phòng."""
    L_min = (B_tk / np.sin(np.radians(max(goc, 30)))) + 2.0
    L_rb   = max(15, min(40, L_min))
    L_span = _snap_length(L_rb)
    n_nhip = max(1, int(np.ceil(L_cau_tong / L_span))) if L_cau_tong else 1
    L_thuc = L_cau_tong / n_nhip if L_cau_tong else L_span
    loai_dam = "Super-T" if n_nhip >= 4 else ("Dầm I" if n_nhip >= 2 else "T ngược")
    H_dam    = round(L_thuc / 18, 2)
    kc       = 2.2 if loai_dam == "Super-T" else 2.0
    n_dam    = int(B_cau / kc) + 1
    oh       = round((B_cau - (n_dam - 1) * kc) / 2, 2)
    return {
        "loai_dam": loai_dam, "chieu_dai": round(L_thuc, 2), "tong_so_nhip": n_nhip,
        "chieu_cao_dam": H_dam, "so_luong_dam": n_dam, "khoang_cach_dam": kc,
        "overhang": oh, "do_tin_cay": 0.0, "phuong_phap": "Rule-Based",
        "ghi_chu": "Dựa trên quy tắc kinh nghiệm (thiếu mô hình AI).",
    }


# ---------------------------------------------------------------------------
# 5. HÀM CHÍNH XUẤT KẾT QUẢ
# ---------------------------------------------------------------------------
def predict_kcn(B_tk, H_tk, goc, B_cau, moi_truong, L_cau_tong=None,
                models=None, method="auto"):
    """
    Dự đoán kết cấu nhịp (loại dầm + thông số hình học).

    Params
    ------
    B_tk        : Bề rộng tĩnh không (m)
    H_tk        : Chiều cao tĩnh không (m)
    goc         : Góc giao chéo (°)
    B_cau       : Bề rộng mặt cắt cầu (m)
    moi_truong  : 'Vượt sông' | 'Đô thị' | ...
    L_cau_tong  : Chiều dài toàn cầu (m), None = chưa biết
    models      : Dict từ train_kcn_ai()
    method      : 'auto' | 'ai' | 'rb'

    Returns
    -------
    dict với các trường:
        loai_dam, chieu_dai, tong_so_nhip,
        chieu_cao_dam, so_luong_dam, khoang_cach_dam, overhang,
        ti_le_L_H, do_tin_cay, phuong_phap, ghi_chu
    """
    if models is None or method == "rb":
        return _predict_rb(B_tk, goc, B_cau, L_cau_tong)

    if method == "ai":
        loai_dam, L_span, H_dam = _predict_single(B_tk, H_tk, goc, B_cau, moi_truong, models)
        n_nhip = max(1, int(np.ceil(L_cau_tong / L_span))) if L_cau_tong else 1
        L_thuc = L_cau_tong / n_nhip if L_cau_tong else L_span
        ghi_chu = f"Dự báo thuần AI: {loai_dam} — {n_nhip} nhịp x {L_thuc:.1f}m"
    else:  # auto
        loai_dam, L_thuc, n_nhip, H_dam = _predict_optimize(
            B_tk, H_tk, goc, B_cau, moi_truong, L_cau_tong, models
        )
        ghi_chu = f"Tối ưu hóa tổ hợp: {loai_dam} — {n_nhip} nhịp x {L_thuc:.1f}m"

    # Tính layout dầm ngang
    kc, n_dam, oh = _calc_girder_layout(loai_dam, L_thuc, B_cau, models)

    # Độ tin cậy (xác suất class tốt nhất)
    le_type = models["le_type"]
    X_row   = _build_x_row(B_tk, H_tk, goc, B_cau, moi_truong, models)
    proba   = models["clf_type"].predict_proba(X_row)[0]
    try:
        conf = float(proba[le_type.transform([loai_dam])[0]]) * 100
    except Exception:
        conf = float(proba.max()) * 100

    return {
        "loai_dam":        loai_dam,
        "chieu_dai":       round(L_thuc, 2),
        "tong_so_nhip":    n_nhip,
        "chieu_cao_dam":   round(H_dam, 2),
        "so_luong_dam":    n_dam,
        "khoang_cach_dam": kc,
        "overhang":        oh,
        "ti_le_L_H":       round(L_thuc / H_dam, 1) if H_dam > 0 else 0,
        "do_tin_cay":      round(conf, 1),
        "phuong_phap":     method.upper(),
        "ghi_chu":         ghi_chu,
    }


# ---------------------------------------------------------------------------
# CHẠY THỬ ĐỘC LẬP
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print("=== Huan luyen mo hinh Ket cau nhip (v3) ===")
    mdl = train_kcn_ai()
    if mdl is None:
        print("Chua co du lieu train — dung Rule-Based fallback")
    else:
        print(f"Da hoc tu {mdl['n_samples']} mau | features: {mdl['feat_cols']}")
        print(f"Cac loai dam: {list(mdl['le_type'].classes_)}")

    print("\n=== Vi du du doan ===")
    res = predict_kcn(
        B_tk=15, H_tk=3.5, goc=90, B_cau=14, moi_truong="Vuot song",
        L_cau_tong=100, models=mdl, method="auto"
    )
    for k, v in res.items():
        print(f"  {k}: {v}")
