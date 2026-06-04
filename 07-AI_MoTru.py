"""
Module 07 — AI Mố – Trụ (Pier Classification AI)
Spec: Bridge_Features_Dataset.xlsx → Sheet 04_Mố – Trụ
Data: Phan loai Tru.csv
Features: Vtk, B_cau, H_tru, Is_Urban, Is_River, Cap_song, Loai_dam
Label   : Loai_tru (phân loại trụ)
"""

import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder
from sklearn.model_selection import StratifiedKFold, cross_val_score
import warnings
warnings.filterwarnings("ignore")

# Thứ tự cấp sông (I = lớn nhất, VI = nhỏ nhất)
_CAP_SONG_ORDER = ["I", "II", "III", "IV", "V", "VI"]
# Ánh xạ chuỗi số → La Mã
_CAP_SONG_MAP = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI"}


def _encode_cap_song(val):
    """Chuyển cấp sông thành số nguyên 1–6 (I=1, VI=6)."""
    s = str(val).strip().upper()
    s = _CAP_SONG_MAP.get(s, s)
    try:
        return _CAP_SONG_ORDER.index(s) + 1
    except ValueError:
        return 4  # mặc định cấp IV


# ---------------------------------------------------------------------------
# 1. NẠP & CHUẨN BỊ DỮ LIỆU
# ---------------------------------------------------------------------------
def load_pier_data(file_path):
    """
    Đọc Phan loai Tru.csv.
    Lọc bỏ cầu 1 nhịp (không có trụ), chuẩn hóa cột.
    """
    df = pd.read_csv(file_path, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]

    # Chuẩn hóa tên cột
    rename = {}
    for c in df.columns:
        lc = c.lower()
        if "vtk" in lc:
            rename[c] = "Vtk"
        elif "b_cau" in lc or "b cau" in lc:
            rename[c] = "B_cau"
        elif "h_tru" in lc or "h tru" in lc:
            rename[c] = "H_tru"
        elif "is_urban" in lc:
            rename[c] = "Is_Urban"
        elif "is_river" in lc:
            rename[c] = "Is_River"
        elif "cap_song" in lc or "cap song" in lc:
            rename[c] = "Cap_song"
        elif "loai_dam" in lc or "loai dam" in lc:
            rename[c] = "Loai_dam"
        elif "loai_tru" in lc or "loai tru" in lc:
            rename[c] = "Loai_tru"
    df = df.rename(columns=rename)

    # Loại bỏ cầu 1 nhịp (không có trụ)
    if "Loai_tru" in df.columns:
        df = df[~df["Loai_tru"].astype(str).str.contains("Không có", na=False)]

    # Ép kiểu số
    for c in ["Vtk", "B_cau", "H_tru", "Is_Urban", "Is_River"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Mã hóa cấp sông
    if "Cap_song" in df.columns:
        df["Cap_song_enc"] = df["Cap_song"].apply(_encode_cap_song)
    else:
        df["Cap_song_enc"] = 4

    # Mã hóa loại dầm
    if "Loai_dam" in df.columns:
        le_dam = LabelEncoder()
        df["Loai_dam_enc"] = le_dam.fit_transform(df["Loai_dam"].astype(str).str.strip())
    else:
        le_dam = None
        df["Loai_dam_enc"] = 0

    # Loại bỏ dòng thiếu
    req = [c for c in ["Vtk", "B_cau", "H_tru", "Loai_tru"] if c in df.columns]
    df = df.dropna(subset=req)

    return df, le_dam


# ---------------------------------------------------------------------------
# 2. HUẤN LUYỆN
# ---------------------------------------------------------------------------
def train_pier_ai(file_path):
    """
    Huấn luyện mô hình phân loại trụ cầu.
    Trả về dict models hoặc None.
    """
    if not os.path.exists(file_path):
        return None
    try:
        df, le_dam = load_pier_data(file_path)
        if len(df) < 6:
            return None

        # ─── Bộ đặc trưng theo spec Sheet 04 ───
        feat_cols = []
        for c in ["Vtk", "B_cau", "H_tru", "Is_Urban", "Is_River",
                  "Cap_song_enc", "Loai_dam_enc"]:
            if c in df.columns:
                feat_cols.append(c)

        X = df[feat_cols].fillna(df[feat_cols].median())
        y = df["Loai_tru"].astype(str).str.strip()

        clf = RandomForestClassifier(
            n_estimators=300, max_depth=6, min_samples_leaf=1,
            class_weight="balanced", random_state=42
        )
        clf.fit(X, y)

        # Cross-validation (chỉ khi đủ mẫu)
        cv_score = None
        if len(df) >= 15:
            try:
                cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
                scores = cross_val_score(clf, X, y, cv=cv, scoring="accuracy")
                cv_score = round(float(scores.mean()) * 100, 1)
            except Exception:
                pass

        return {
            "clf":       clf,
            "le_dam":    le_dam,
            "feat_cols": feat_cols,
            "classes":   list(clf.classes_),
            "n_samples": len(df),
            "cv_acc":    cv_score,
            "version":   "v2_spec",
        }

    except Exception as e:
        print(f"[Pier-AI] Lỗi huấn luyện: {e}")
        return None


# ---------------------------------------------------------------------------
# 3. HÀM DỰ ĐOÁN
# ---------------------------------------------------------------------------
def predict_pier(vtk, B_cau, H_tru, is_urban, is_river, cap_song,
                 loai_dam, models):
    """
    Dự đoán loại trụ cầu.

    Params
    ------
    vtk       : Vận tốc thiết kế (km/h)
    B_cau     : Bề rộng cầu (m)
    H_tru     : Chiều cao thân trụ ước tính (m)
    is_urban  : 1 nếu đô thị, 0 nếu không
    is_river  : 1 nếu vượt sông, 0 nếu không
    cap_song  : Cấp sông ('I'...'VI' hoặc '1'...'6'), '' nếu không áp dụng
    loai_dam  : Loại dầm (text, từ kết quả KCN)
    models    : Dict từ train_pier_ai()

    Returns
    -------
    dict với: loai_tru, do_tin_cay, xep_hang (top-3), ghi_chu
    """
    if models is None:
        return _rule_based_pier(vtk, B_cau, H_tru, is_urban, is_river, cap_song=cap_song)

    try:
        le_dam = models["le_dam"]
        feat_cols = models["feat_cols"]

        # Mã hóa đầu vào
        cap_song_enc = _encode_cap_song(cap_song) if cap_song else 4
        try:
            dam_enc = le_dam.transform([str(loai_dam).strip()])[0] if le_dam else 0
        except Exception:
            dam_enc = 0

        mapping = {
            "Vtk": vtk, "B_cau": B_cau, "H_tru": H_tru,
            "Is_Urban": is_urban, "Is_River": is_river,
            "Cap_song_enc": cap_song_enc, "Loai_dam_enc": dam_enc,
        }
        X_row = [[mapping.get(c, 0) for c in feat_cols]]

        loai_tru = models["clf"].predict(X_row)[0]
        proba    = models["clf"].predict_proba(X_row)[0]
        classes  = models["classes"]
        conf     = float(proba.max()) * 100

        # Top-3 phương án
        top_idx = np.argsort(proba)[::-1][:3]
        xep_hang = [
            {"loai": classes[i], "xac_suat": round(float(proba[i]) * 100, 1)}
            for i in top_idx if proba[i] > 0.01
        ]

        ghi_chu = (
            f"Mô hình RF ({models['n_samples']} mẫu) dự báo: {loai_tru} "
            f"— độ tin cậy {conf:.1f}%"
        )
        if models.get("cv_acc") is not None:
            ghi_chu += f" | CV-acc: {models['cv_acc']}%"

        return {
            "loai_tru":   loai_tru,
            "do_tin_cay": round(conf, 1),
            "xep_hang":   xep_hang,
            "ghi_chu":    ghi_chu,
        }

    except Exception as e:
        return _rule_based_pier(vtk, B_cau, H_tru, is_urban, is_river,
                                cap_song=cap_song, note=f"[fallback] {e}")


# ---------------------------------------------------------------------------
# 4. QUY TẮC KỸ THUẬT — CẦU VƯỢT SÔNG (DỰ PHÒNG)
# ---------------------------------------------------------------------------
def _rule_based_pier(vtk, B_cau, H_tru, is_urban, is_river, cap_song="VI", note=""):
    """
    Phân loại trụ cầu vượt sông theo quy tắc kỹ thuật.

    Nguyên tắc chọn trụ (cầu vượt sông cấp III–VI):
    ─────────────────────────────────────────────────
    • Cấp V–VI (sông nhỏ, tải va tàu nhỏ):
        → Trụ thân cột (2 hoặc 3 thân tùy B_cầu).
          Cột thanh mảnh phù hợp dòng chảy nhỏ,
          có thể bố trí thêm cốt thép để chịu va tàu.
    • Cấp III–IV (sông vừa, tải va tàu lớn hơn):
        → Trụ đặc thân hẹp.
          Tiết diện đặc đảm bảo chịu va tàu tốt hơn.
    • Trụ rất thấp (H ≤ 2.5m): luôn chọn trụ đặc (kinh tế).
    """
    cap_int = _encode_cap_song(cap_song) if cap_song else 4

    if is_river:
        if H_tru <= 2.5:
            # Trụ thấp → trụ đặc bất kể cấp sông
            loai = "Trụ đặc"
        elif cap_int >= 5:
            # Cấp V, VI: thân cột (2 hoặc 3 thân tuỳ bề rộng)
            if B_cau >= 16:
                loai = "Thân cột 3 trụ"
            else:
                loai = "Thân cột 2 trụ"
        elif cap_int >= 3:
            # Cấp III, IV: trụ đặc thân hẹp chịu va tàu tốt hơn
            loai = "Trụ đặc thân hẹp"
        else:
            # Cấp I, II: trụ đặc thân hẹp (tải va tàu lớn)
            loai = "Trụ đặc thân hẹp"
    else:
        # Không phải vượt sông (hiện đề tài không dùng nhánh này)
        if H_tru <= 3.0:
            loai = "Trụ đặc"
        elif B_cau >= 20:
            loai = "Khung 2 cột"
        elif H_tru >= 8.0:
            loai = "Thân rỗng"
        else:
            loai = "Khung 2 cột"

    ghi_chu = (
        f"Quy tắc kỹ thuật: Cấp sông {cap_song}, "
        f"H_trụ={H_tru:.1f}m, B_cầu={B_cau:.1f}m. {note}"
    ).strip()
    return {
        "loai_tru":   loai,
        "do_tin_cay": 0.0,
        "xep_hang":   [{"loai": loai, "xac_suat": 100.0}],
        "ghi_chu":    ghi_chu,
    }


# ---------------------------------------------------------------------------
# 5. ƯỚC TÍNH CHIỀU CAO TRỤ
# ---------------------------------------------------------------------------
def estimate_pier_height(MNCN, H_tinh_khong, H_dam, MNTN):
    """
    Ước tính chiều cao thân trụ dựa trên cao độ.
    H_tru = (MNCN + H_tinh_khong + H_dam) - MNTN - 0.5
    """
    cao_day_dam = MNCN + H_tinh_khong
    cao_mat_cau = cao_day_dam + H_dam + 0.25   # bản mặt cầu ~25cm
    H_tru = max(0.5, cao_day_dam - MNTN - 0.5)
    return round(H_tru, 2), round(cao_day_dam, 3), round(cao_mat_cau, 3)


# ---------------------------------------------------------------------------
# CHẠY THỬ ĐỘC LẬP
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(current_dir, "Phan loai Tru.csv")

    print("=== Huấn luyện mô hình Trụ cầu ===")
    mdl = train_pier_ai(csv_path)
    if mdl is None:
        print("THẤT BẠI — kiểm tra Phan loai Tru.csv")
    else:
        print(f"Học từ {mdl['n_samples']} mẫu | features: {mdl['feat_cols']}")
        print(f"Các loại trụ: {mdl['classes']}")
        if mdl["cv_acc"]:
            print(f"Cross-val accuracy: {mdl['cv_acc']}%")

        print("\n=== Ví dụ dự đoán ===")
        res = predict_pier(
            vtk=100, B_cau=17.5, H_tru=5.08,
            is_urban=0, is_river=1, cap_song="VI",
            loai_dam="T ngược", models=mdl
        )
        for k, v in res.items():
            print(f"  {k}: {v}")
