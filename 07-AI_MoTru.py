"""
Module 07 — AI Mo - Tru (Pier Classification AI)
Data  : Bridge_Train_Dataset_v3.xlsx — sheet 06_Mo-Tru + 02 + 03 + 07
Features: Vtk, B_cau, H_tru, Is_Urban, Is_River, Cap_song, Loai_dam
Label   : Loai_tru (phan loai tru)
Fallback: Rule-Based 6 tang khi chua co du lieu train
"""

import os
import sys
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import StratifiedKFold, cross_val_score
import warnings
warnings.filterwarnings("ignore")

_DIR = os.path.dirname(os.path.abspath(__file__))
_V3_DEFAULT = os.path.join(_DIR, "Data", "Bridge_Train_Dataset_v3.xlsx")

# Thứ tự cấp sông (I = lớn nhất, VI = nhỏ nhất)
_CAP_SONG_ORDER = ["I", "II", "III", "IV", "V", "VI"]
# Ánh xạ chuỗi số → La Mã
_CAP_SONG_MAP = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI"}

# Danh sách loại trụ chuẩn
PIER_TYPES = [
    "Trụ đặc",            # Solid Wall — thân tường đặc, thấp
    "Trụ đặc thân hẹp",   # Solid Wall hẹp — sông lớn, chịu va tàu
    "Trụ cột đơn",        # Single-Column (chữ T / đầu búa) — đô thị
    "Thân cột 2 trụ",     # Bent Pier 2 cột — cầu vừa
    "Thân cột 3 trụ",     # Bent Pier 3 cột — cầu rộng
    "Thân rỗng",          # Hollow — trụ cao H > 10m
]

# Ghi chú kỹ thuật tra cứu ưu nhược điểm (dùng trong UI để hiển thị tooltip)
PIER_NOTES = {
    "Trụ đặc": (
        "Độ cứng cao, thi công đơn giản. "
        "Phù hợp trụ thấp ≤ 2.5m. Tốn vật liệu nếu trụ cao."
    ),
    "Trụ đặc thân hẹp": (
        "Tiết diện đặc chịu va tàu tốt. Mũi vát nhọn CD=0.7–0.8 "
        "giảm cản dòng chảy. Không cần ụ bảo vệ riêng. "
        "Chi phí ban đầu cao nhưng kinh tế dài hạn tại luồng nhộn nhịp."
    ),
    "Trụ cột đơn": (
        "Chiếm ít mặt bằng, thông thoáng không gian dưới cầu. "
        "Phù hợp cầu hẹp, cầu cong, cầu chéo đô thị. "
        "Yêu cầu móng tập trung vững chắc (cọc khoan nhồi đường kính lớn)."
    ),
    "Thân cột 2 trụ": (
        "Hệ khung ngang vững, phân tán lực tốt. "
        "Có thể kéo dài cọc lên làm cột, thi công nhanh. "
        "Chú ý xói lở và rác kẹt khi cọc lộ trước dòng chảy."
    ),
    "Thân cột 3 trụ": (
        "Phù hợp cầu rộng ≥ 16m, phân tán tải đều. "
        "Thi công phức tạp hơn thân cột 2 trụ. "
        "Chi phí bảo trì cao hơn do nhiều cấu kiện phơi lộ."
    ),
    "Thân rỗng": (
        "Tiết kiệm vật liệu cho trụ cao > 10m. "
        "Thi công yêu cầu kỹ thuật ván khuôn trượt hoặc leo. "
        "Khuyến nghị tham vấn chuyên gia tại giai đoạn TKKT."
    ),
}

# Danh sách loại mố chuẩn (phạm vi đề tài: 2 loại)
ABUTMENT_TYPES = [
    "Mố chân dê",   # Stub abutment — H_dap ≤ 4m
    "Mố chữ U",     # U-abutment   — H_dap > 4m
]

ABUTMENT_NOTES = {
    "Mố chân dê": (
        "Tiết kiệm vật liệu tối đa cho nền đắp thấp đến 4m, thi công nhanh, "
        "phù hợp cầu nhỏ và vừa. "
        "Khả năng chịu lực ngang phân bổ cho toàn hệ thống cầu, cần kiểm tra khi nhịp dài."
    ),
    "Mố chữ U": (
        "Phổ biến nhất cho nền đắp trên 4m, khả năng chống lật và chống trượt tốt, "
        "ổn định độc lập không phụ thuộc kết cấu nhịp. "
        "Chi phí vật liệu cao hơn mố chân dê nhưng độ tin cậy khai thác lâu dài tốt hơn."
    ),
}


def _encode_cap_song(val):
    """Chuyển cấp sông thành số nguyên 1–6 (I=1, VI=6)."""
    s = str(val).strip().upper()
    s = _CAP_SONG_MAP.get(s, s)
    try:
        return _CAP_SONG_ORDER.index(s) + 1
    except ValueError:
        return 4  # mặc định cấp IV


_CAP_DUONG_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}


def _encode_cap_duong(val):
    """Chuyển cấp đường thành số nguyên (0=Cao tốc, 1=I, ..., 6=VI)."""
    s = str(val).strip().upper()
    # Chuẩn hoá: bỏ tiền tố "CẤP", "CAP", dấu gạch dưới
    for prefix in ("CẤP", "CAP_", "CAP"):
        s = s.replace(prefix, "")
    s = s.replace("_", "").strip()
    if s in ("CT", "CAOTOC", "CAO TOC", "0", ""):
        return 0 if s in ("CT", "CAOTOC", "CAO TOC", "0") else 3
    if s in _CAP_DUONG_ROMAN:
        return _CAP_DUONG_ROMAN[s]
    try:
        return int(s)
    except (ValueError, TypeError):
        return 3  # mặc định cấp III


# ---------------------------------------------------------------------------
# 1. NẠP & CHUẨN BỊ DỮ LIỆU
# ---------------------------------------------------------------------------
def load_pier_data_v3(v3_path=None):
    """
    Đọc dữ liệu trụ cầu từ Bridge_Train_Dataset_v3.xlsx.
    Trả về (DataFrame, le_dam) hoặc (rỗng, None).
    """
    path = v3_path or _V3_DEFAULT
    if not os.path.exists(path):
        return pd.DataFrame(), None
    try:
        data_dir = os.path.join(_DIR, "Data")
        if data_dir not in sys.path:
            sys.path.insert(0, data_dir)
        from v3_loader import get_pier_df
        df = get_pier_df(path)
    except Exception as e:
        print(f"[Pier-AI] Không nạp v3_loader: {e}")
        return pd.DataFrame(), None

    if df.empty:
        return df, None

    rename = {
        "vtk":      "Vtk",
        "b_cau":    "B_cau",
        "bc":       "B_cau_alt",
        "h_tru":    "H_tru",
        "loai_tru": "Loai_tru",
        "loai_dam": "Loai_dam",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    if "B_cau" not in df.columns and "B_cau_alt" in df.columns:
        df["B_cau"] = df["B_cau_alt"]
    elif "B_cau_alt" in df.columns:
        df["B_cau"] = df["B_cau"].fillna(df["B_cau_alt"])

    for c in ["Vtk", "B_cau", "H_tru"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "cap_song" in df.columns:
        df["Cap_song"] = df["cap_song"].astype(str).str.strip().str.replace(
            r"(?i)cap\s*", "", regex=True).str.strip()
        df["Cap_song_enc"] = df["Cap_song"].apply(_encode_cap_song)
    else:
        df["Cap_song"]     = "VI"
        df["Cap_song_enc"] = 6

    if "Is_Urban" not in df.columns:
        if "loai_duong" in df.columns:
            df["Is_Urban"] = df["loai_duong"].astype(str).str.lower().str.contains(
                "do thi|urban", na=False).astype(int)
        else:
            df["Is_Urban"] = 0
    if "Is_River" not in df.columns:
        if "loai_vuot" in df.columns:
            df["Is_River"] = df["loai_vuot"].astype(str).str.lower().str.contains(
                "song|kenh", na=False).astype(int)
        else:
            df["Is_River"] = 1

    le_dam = None
    if "Loai_dam" in df.columns:
        le_dam = LabelEncoder()
        df["Loai_dam_enc"] = le_dam.fit_transform(df["Loai_dam"].astype(str).str.strip().fillna("Unknown"))
    else:
        df["Loai_dam_enc"] = 0

    if "Loai_tru" in df.columns:
        df = df[~df["Loai_tru"].astype(str).str.contains("Không có|Không trụ", na=False)]
        df = df.dropna(subset=["Loai_tru"])
        df = df[df["Loai_tru"].astype(str).str.strip().str.len() > 0]

    req = [c for c in ["Vtk", "B_cau", "H_tru", "Loai_tru"] if c in df.columns]
    df = df.dropna(subset=req)

    return df.reset_index(drop=True), le_dam


# ---------------------------------------------------------------------------
# 2. HUẤN LUYỆN
# ---------------------------------------------------------------------------
def train_pier_ai(v3_path=None, **_):
    """
    Huấn luyện mô hình phân loại trụ cầu từ Bridge_Train_Dataset_v3.xlsx.
    Trả về dict models khi v3 có >= 6 mẫu, ngược lại trả None
    (predict_pier() sẽ dùng Rule-Based fallback tự động).
    """
    MIN_ROWS = 6
    v3p = v3_path or _V3_DEFAULT

    df, le_dam = load_pier_data_v3(v3p)
    n_v3 = len(df)
    if n_v3 < MIN_ROWS:
        print(f"[Pier-AI] Chưa đủ dữ liệu (v3={n_v3}, cần >={MIN_ROWS}). Dùng Rule-Based.")
        return None
    print(f"[Pier-AI] Dùng v3: {n_v3} mẫu")

    try:
        if "Loai_dam" in df.columns:
            le_dam = LabelEncoder()
            df = df.copy()
            df["Loai_dam_enc"] = le_dam.fit_transform(df["Loai_dam"].astype(str).str.strip().fillna("Unknown"))
        elif le_dam is None:
            df = df.copy()
            df["Loai_dam_enc"] = 0

        if "Cap_song_enc" not in df.columns:
            df = df.copy()
            cap_src = df.get("Cap_song", df.get("cap_song", pd.Series(["VI"] * len(df))))
            df["Cap_song_enc"] = cap_src.astype(str).str.replace(
                r"[Cc]ấp\s*", "", regex=True).str.strip().apply(_encode_cap_song)

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
# 3. QUY TẮC KỸ THUẬT — MA TRẬN 6 TẦNG
# ---------------------------------------------------------------------------
def _rule_based_pier(vtk, B_cau, H_tru, is_urban, is_river,
                     cap_song="VI", loai_dam="", n_nhip=1, note=""):
    """
    Phân loại trụ cầu theo ma trận quyết định 6 tầng.

    Tầng 1 → chiều cao (tuyệt đối)
    Tầng 2 → cấp sông / va tàu
    Tầng 3 → bề rộng cầu (cấp V–VI)
    Tầng 4 → điều chỉnh đô thị
    Tầng 5 → tải trọng kết cấu nhịp
    Tầng 6 → trụ rất cao (H > 10m)
    """
    cap_int = _encode_cap_song(cap_song) if cap_song else 4
    can_than_rong = H_tru > 10
    notes = []
    tang = ""

    # ── Tầng 1 — Chiều cao trụ (ưu tiên tuyệt đối) ──────────────────────
    if H_tru <= 2.5:
        loai = "Trụ đặc"
        tang = "Tầng 1 — H_tru thấp"
        notes.append(f"H_tru={H_tru:.1f}m ≤ 2.5m — trụ đặc kinh tế nhất")
        ghi_chu = "; ".join(notes)
        if note:
            ghi_chu = (ghi_chu + ". " + note).strip()
        return {
            "loai_tru":        loai,
            "do_tin_cay":      100.0,
            "tang_quyet_dinh": tang,
            "ghi_chu":         ghi_chu,
            "phuong_phap":     "Rule-Based",
        }

    # ── Tầng 2 — Cấp sông xác định yêu cầu chịu va tàu ─────────────────
    # Bỏ qua Tầng 2 nếu không phải vượt sông (không có yêu cầu va tàu)
    if not is_river:
        cap_int = 6  # ép về cấp VI để rơi xuống Tầng 3 (width-based)

    if cap_int <= 2:
        # Cấp I–II: tải va tàu rất lớn, bắt buộc tiết diện đặc
        loai = "Trụ đặc thân hẹp"
        tang = "Tầng 2 — Cấp sông"
        notes.append(f"Cấp {cap_song} — tải va tàu rất lớn, bắt buộc tiết diện đặc")

    elif cap_int <= 4:
        # Cấp III–IV: va tàu vừa
        if not is_urban:
            loai = "Trụ đặc thân hẹp"
            tang = "Tầng 2 — Cấp sông"
            notes.append(
                f"Cấp {cap_song}, không đô thị — tiết diện đặc tối ưu thủy lực CD=0.7–0.8"
            )
        else:
            loai = "Thân cột 2 trụ"
            tang = "Tầng 2 — Cấp sông"
            notes.append(
                f"Cấp {cap_song}, đô thị — thân cột ưu tiên thông thoáng mỹ quan"
            )

    else:
        # Cấp V–VI → xét Tầng 3
        if B_cau < 10:
            loai = "Trụ cột đơn"
            tang = "Tầng 3 — Bề rộng cầu"
            notes.append(
                f"Cấp {cap_song}, B_cau={B_cau:.1f}m < 10m — cầu hẹp, trụ cột đơn tiết kiệm mặt bằng"
            )
        elif B_cau < 16:
            loai = "Thân cột 2 trụ"
            tang = "Tầng 3 — Bề rộng cầu"
            notes.append(f"Cấp {cap_song}, B_cau={B_cau:.1f}m — cầu vừa, thân cột 2 trụ")
        else:
            loai = "Thân cột 3 trụ"
            tang = "Tầng 3 — Bề rộng cầu"
            notes.append(
                f"Cấp {cap_song}, B_cau={B_cau:.1f}m ≥ 16m — cầu rộng, thân cột 3 trụ"
            )

    # ── Tầng 4 — Điều chỉnh theo môi trường đô thị ───────────────────────
    if is_urban:
        if loai == "Trụ đặc thân hẹp" and cap_int >= 4:
            # Va tàu không quá lớn (cấp IV trở đi) → ưu tiên thông thoáng
            loai = "Thân cột 2 trụ"
            tang = "Tầng 4 — Đô thị"
            notes.append(
                "Đô thị cấp ≥ IV: đổi sang thân cột — ưu tiên thông thoáng không gian và mỹ quan"
            )
        if B_cau < 10 and loai != "Trụ cột đơn":
            loai = "Trụ cột đơn"
            tang = "Tầng 4 — Đô thị"
            notes.append("Đô thị B_cau < 10m: trụ cột đơn — chiếm ít mặt bằng nút giao")

    # ── Tầng 5 — Điều chỉnh theo tải trọng kết cấu nhịp ─────────────────
    _HEAVY = ("Super-T", "Dầm I")
    loai_dam_str = str(loai_dam).strip()
    if loai_dam_str in _HEAVY:
        if n_nhip >= 4 and loai == "Trụ cột đơn":
            loai = "Thân cột 2 trụ"
            tang = "Tầng 5 — Tải trọng nhịp"
            notes.append(
                f"{loai_dam_str} × {n_nhip} nhịp — tải lớn, không dùng trụ cột đơn, nâng lên thân cột 2 trụ"
            )
        if cap_int >= 5:
            notes.append(
                f"Lưu ý: {loai_dam_str} trên sông cấp V–VI — khuyến nghị kiểm tra xói cục bộ chân cột"
            )

    # ── Tầng 6 — Chiều cao trụ rất cao ───────────────────────────────────
    if can_than_rong and loai not in ("Trụ đặc", "Trụ đặc thân hẹp"):
        loai = "Thân rỗng"
        tang = "Tầng 6 — H_tru rất cao"
        notes.append(
            f"H_tru={H_tru:.1f}m > 10m — trụ đặc quá nặng, khuyến nghị thân rỗng hoặc tham vấn chuyên gia"
        )

    ghi_chu = "; ".join(notes)
    if note:
        ghi_chu = (ghi_chu + ". " + note).strip()

    return {
        "loai_tru":        loai,
        "do_tin_cay":      100.0,
        "tang_quyet_dinh": tang,
        "ghi_chu":         ghi_chu,
        "phuong_phap":     "Rule-Based",
    }


# ---------------------------------------------------------------------------
# 4. HÀM DỰ ĐOÁN — TRẢ VỀ 2 PHƯƠNG ÁN
# ---------------------------------------------------------------------------
def predict_pier(vtk, B_cau, H_tru, is_urban, is_river, cap_song,
                 loai_dam, n_nhip, models,
                 # ── Tham số phân loại mố (tất cả có default, tương thích ngược) ──
                 H_dap=3.0, L_nhip=20.0, SPT_N=10,
                 MNCN=None, MNTN=None, Z_tu_nhien=None,
                 is_tidal=0, cap_duong=""):
    """
    Dự đoán loại trụ cầu (2 phương án RB + AI) và phân loại mố cầu (RB).

    Params — Trụ
    ------------
    vtk              : Vận tốc thiết kế (km/h)
    B_cau            : Bề rộng cầu (m)
    H_tru            : Chiều cao thân trụ ước tính (m)
    is_urban         : 1 nếu đô thị
    is_river         : 1 nếu vượt sông
    cap_song         : Cấp sông ('I'...'VI' hoặc '1'...'6')
    loai_dam         : Loại dầm (text, từ kết quả KCN)
    n_nhip           : Số nhịp
    models           : Dict từ train_pier_ai(), hoặc None

    Params — Mố (keyword-only, tất cả có default)
    ---------------------------------------------
    H_dap            : Chiều cao đất đắp tại mố (m)
    L_nhip           : Chiều dài nhịp biên (m)
    SPT_N            : Chỉ số SPT tại vị trí mố
    MNCN             : Mực nước cao nhất (m), None nếu không áp dụng
    MNTN             : Mực nước thấp nhất (m)
    Z_tu_nhien       : Cao độ tự nhiên tại vị trí mố (m)
    is_tidal         : 1 nếu vùng triều
    cap_duong        : Cấp đường ('Cao tốc'/'I'/'II'/...'VI')

    Returns
    -------
    dict: pa_rb, pa_ai, dong_thuan, canh_bao, ket_qua_mo
    """
    # Phương án Rule-Based (luôn tính)
    pa_rb = _rule_based_pier(
        vtk, B_cau, H_tru, is_urban, is_river,
        cap_song=cap_song, loai_dam=loai_dam, n_nhip=n_nhip,
    )

    # Phương án AI
    if models is None:
        # Chưa có mô hình → lặp lại RB
        pa_ai = {
            "loai_tru":    pa_rb["loai_tru"],
            "do_tin_cay":  100.0,
            "xep_hang":    [{"loai": pa_rb["loai_tru"], "xac_suat": 100.0}],
            "ghi_chu":     pa_rb["ghi_chu"],
            "phuong_phap": "Rule-Based (chưa có mô hình)",
        }
    else:
        try:
            le_dam    = models["le_dam"]
            feat_cols = models["feat_cols"]

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
            X_row   = [[mapping.get(c, 0) for c in feat_cols]]
            loai_ai = models["clf"].predict(X_row)[0]
            proba   = models["clf"].predict_proba(X_row)[0]
            classes = models["classes"]
            conf    = float(proba.max()) * 100

            top_idx  = np.argsort(proba)[::-1][:3]
            xep_hang = [
                {"loai": classes[i], "xac_suat": round(float(proba[i]) * 100, 1)}
                for i in top_idx if proba[i] > 0.01
            ]

            ghi_chu = (
                f"Mô hình RF ({models['n_samples']} mẫu): {loai_ai} "
                f"— độ tin cậy {conf:.1f}%"
            )
            if models.get("cv_acc") is not None:
                ghi_chu += f" | CV-acc: {models['cv_acc']}%"

            pa_ai = {
                "loai_tru":    loai_ai,
                "do_tin_cay":  round(conf, 1),
                "xep_hang":    xep_hang,
                "ghi_chu":     ghi_chu,
                "phuong_phap": "AI",
            }

        except Exception as e:
            # Fallback RB nếu AI lỗi
            rb_fb = _rule_based_pier(
                vtk, B_cau, H_tru, is_urban, is_river,
                cap_song=cap_song, loai_dam=loai_dam, n_nhip=n_nhip,
                note=f"[fallback AI lỗi: {e}]",
            )
            pa_ai = {
                "loai_tru":    rb_fb["loai_tru"],
                "do_tin_cay":  100.0,
                "xep_hang":    [{"loai": rb_fb["loai_tru"], "xac_suat": 100.0}],
                "ghi_chu":     rb_fb["ghi_chu"],
                "phuong_phap": "Rule-Based (chưa có mô hình)",
            }

    dong_thuan = pa_rb["loai_tru"] == pa_ai["loai_tru"]
    canh_bao = (
        ""
        if dong_thuan
        else (
            f"RB đề xuất '{pa_rb['loai_tru']}', AI đề xuất '{pa_ai['loai_tru']}' — cần xem xét"
        )
    )

    ket_qua_mo = _classify_abutment(
        H_dap=H_dap, L_nhip=L_nhip, is_urban=is_urban,
        SPT_N=SPT_N, MNCN=MNCN, MNTN=MNTN, Z_tu_nhien=Z_tu_nhien,
        is_tidal=is_tidal, cap_duong=cap_duong,
    )

    return {
        "pa_rb":      pa_rb,
        "pa_ai":      pa_ai,
        "dong_thuan": dong_thuan,
        "canh_bao":   canh_bao,
        "ket_qua_mo": ket_qua_mo,
    }


# ---------------------------------------------------------------------------
# 5. ƯỚC TÍNH CHIỀU CAO TRỤ — 3 TÌNH HUỐNG THỰC TẾ
# ---------------------------------------------------------------------------
def estimate_pier_height(
    MNCN, H_tinh_khong, H_dam, MNTN,
    Z_day_song=None,
    h_xoi_chung=0.0,
    vi_tri_tru="trong_nuoc_be_thap",
    Z_tu_nhien=None,
    h_xa_mu=1.2,
):
    """
    Ước tính chiều cao thân trụ theo ba tình huống thiết kế.

    Phân biệt H_than_tru (thân trụ nhìn thấy từ đỉnh bệ đến đáy xà mũ)
    và cao_dinh_tru (đỉnh trụ = đỉnh xà mũ = đáy dầm). Chỉ H_than_tru
    được đưa vào predict_pier() để phân loại loại trụ.

    Params
    ------
    MNCN          : Mực nước cao nhất thiết kế (m)
    H_tinh_khong  : Khổ tĩnh không thông thuyền (m)
    H_dam         : Chiều cao kết cấu nhịp (m)
    MNTN          : Mực nước thấp nhất thiết kế (m)
    Z_day_song    : Cao độ đáy sông tự nhiên (m) — bắt buộc cho bệ cao
    h_xoi_chung   : Chiều sâu xói chung tính toán (m), mặc định 0
    vi_tri_tru    : 'tren_can' | 'trong_nuoc_be_thap' | 'trong_nuoc_be_cao'
    Z_tu_nhien    : Cao độ mặt đất tự nhiên tại vị trí trụ (m) — dùng khi tren_can
    h_xa_mu       : Chiều cao xà mũ (m), mặc định 1.2

    Returns
    -------
    dict gồm: H_than_tru, cao_day_dam, cao_mat_cau, Z_dinh_be,
              cao_dinh_tru, can_than_rong, canh_bao, vi_tri_tru

    Tình huống 1 — tren_can
        Đỉnh bệ nhô lên mặt đất tự nhiên 0.25m để thoát nước và thi công.
        Z_dinh_be = Z_tu_nhien + 0.25

    Tình huống 2 — trong_nuoc_be_thap  (phổ biến nhất, cấp IV–VI)
        Đài cọc chìm dưới MNTN 0.4m, mỹ quan khi nước cạn, giảm cản dòng.
        Z_dinh_be = MNTN - 0.4

    Tình huống 3 — trong_nuoc_be_cao
        Đài cọc cao lộ trước dòng chảy, đỉnh bệ phải dưới đáy sông sau xói
        và dự phòng 0.5m theo TCVN 11823.
        Z_dinh_be = Z_day_song - h_xoi_chung - 0.5
        Phát sinh cảnh báo: xói cục bộ chân cọc lộ, lực đẩy nổi, va trôi.
    """
    cao_day_dam   = MNCN + H_tinh_khong          # cao độ đáy dầm
    cao_mat_cau   = cao_day_dam + H_dam + 0.25   # bản mặt cầu ~25 cm
    cao_dinh_tru  = cao_day_dam                  # đỉnh trụ = đỉnh xà mũ = đáy dầm
    cao_dinh_than = cao_day_dam - h_xa_mu        # đỉnh thân = đáy xà mũ

    canh_bao_list = []

    if vi_tri_tru == "tren_can":
        z0 = Z_tu_nhien if Z_tu_nhien is not None else MNTN
        Z_dinh_be = z0 + 0.25

    elif vi_tri_tru == "trong_nuoc_be_cao":
        if Z_day_song is None:
            canh_bao_list.append(
                "THIẾU Z_day_song — tạm dùng MNTN - 1.0m để ước tính"
            )
            Z_day_song = MNTN - 1.0
        Z_dinh_be = Z_day_song - h_xoi_chung - 0.5
        canh_bao_list.extend([
            "Bệ cao: cọc lộ trước dòng chảy sau xói — kiểm tra xói cục bộ chân cọc",
            "Kiểm tra lực đẩy nổi và lực va trôi theo TCVN 11823",
            "Khuyến nghị thiết kế ụ bảo vệ hoặc dầm chắn va trôi cho đoạn cọc lộ",
        ])

    else:
        # trong_nuoc_be_thap — mặc định, phổ biến nhất
        vi_tri_tru = "trong_nuoc_be_thap"
        Z_dinh_be  = MNTN - 0.4

    H_than_tru    = max(0.5, cao_dinh_than - Z_dinh_be)
    can_than_rong = H_than_tru > 10.0

    if can_than_rong:
        canh_bao_list.append(
            f"H_than_tru={H_than_tru:.2f}m > 10m — xem xét thân rỗng, tham vấn chuyên gia TKKT"
        )

    return {
        "H_than_tru":    round(H_than_tru, 2),
        "cao_day_dam":   round(cao_day_dam, 3),
        "cao_mat_cau":   round(cao_mat_cau, 3),
        "Z_dinh_be":     round(Z_dinh_be, 3),
        "cao_dinh_tru":  round(cao_dinh_tru, 3),
        "can_than_rong": can_than_rong,
        "canh_bao":      "; ".join(canh_bao_list),
        "vi_tri_tru":    vi_tri_tru,
    }


# ---------------------------------------------------------------------------
# 6. PHÂN LOẠI MỐ CẦU — RULE-BASED (PHẠM VI ĐỀ TÀI: MỐ CHÂN DÊ / MỐ CHỮ U)
# ---------------------------------------------------------------------------
def _classify_abutment(
    H_dap=3.0,
    L_nhip=20.0,
    is_urban=0,
    SPT_N=10,
    MNCN=None,
    MNTN=None,
    Z_tu_nhien=None,
    is_tidal=0,
    cap_duong="",
):
    """
    Phân loại mố cầu trong phạm vi đề tài (2 loại: Mố chân dê / Mố chữ U).

    Bước 1 — Chọn loại mố theo H_dap (quyết định cứng, không thay đổi):
        H_dap ≤ 4m  →  Mố chân dê   (nhóm dẻo)
        H_dap > 4m  →  Mố chữ U     (nhóm cứng)

    Bước 2 — Bản dẫn: bắt buộc cho mọi trường hợp trong đề tài.

    Bước 3 — Sinh cảnh báo kỹ thuật theo điều kiện phụ (không đổi loai_mo):
        • Z_tu_nhien < MNCN + 0.5m   → nguy cơ ngập lũ, kiểm tra mái taluy
        • SPT_N < 5                   → đất yếu, móng cọc bắt buộc, lún lệch
        • is_tidal = 1                → BTCT chống xâm thực, cọc ép thép lộ
        • H_dap > 4 và is_urban       → tường cánh song song thay vuông góc
        • L_nhip > 20m                → kiểm tra lực ngang, ổn định trượt/lật

    Bước 4 — Kích thước sơ bộ:
        L_tuong_canh = H_dap × 1.5 (taluy 1:1.5) hoặc × 2.0 (đất yếu)
        H_mo = cao_mat_cau_sb - Z_dinh_be_mo
             = (Z_tu_nhien + H_dap) - (Z_tu_nhien - 0.5)
             = H_dap + 0.5  (cả khi có lẫn không có Z_tu_nhien)

    Returns
    -------
    dict: loai_mo, nhom, can_ban_dan, H_mo, L_tuong_canh,
          warnings, ghi_chu, H_dap_vung
    """
    # ── Bước 1 — Chọn loại mố (quy tắc cứng) ────────────────────────────
    if H_dap <= 4.0:
        loai_mo    = "Mố chân dê"
        nhom       = "dẻo"
        H_dap_vung = "thấp (≤4m)"
    else:
        loai_mo    = "Mố chữ U"
        nhom       = "cứng"
        H_dap_vung = "cao (>4m)"

    # ── Bước 2 — Bản dẫn bắt buộc ───────────────────────────────────────
    can_ban_dan = True

    # ── Bước 3 — Cảnh báo kỹ thuật (không thay đổi loai_mo) ─────────────
    warnings_list = []

    if MNCN is not None and Z_tu_nhien is not None and Z_tu_nhien < MNCN + 0.5:
        warnings_list.append(
            f"Mố nguy cơ ngập lũ (Z_tu_nhien={Z_tu_nhien:.2f}m < MNCN+0.5={MNCN + 0.5:.2f}m)"
            " — kiểm tra ổn định mái taluy khi lũ rút, gia cố chân mố"
        )

    if MNTN is not None and Z_tu_nhien is not None and Z_tu_nhien < MNTN:
        warnings_list.append(
            f"NGUY HIỂM: Z_tu_nhien={Z_tu_nhien:.2f}m < MNTN={MNTN:.2f}m"
            " — vị trí mố luôn ngập, xem xét lại cao độ thiết kế"
        )

    if SPT_N < 5:
        warnings_list.append(
            f"SPT_N={SPT_N} < 5 — đất yếu: bắt buộc móng cọc,"
            " nguy cơ lún lệch đầu cầu — bản dẫn bắt buộc"
        )

    if is_tidal:
        warnings_list.append(
            "Vùng triều: BTCT chống xâm thực (W8, a/c ≤ 0.45, XM bền sulfate)"
            " — không dùng cọc ép thép lộ"
        )

    if H_dap > 4.0 and is_urban:
        warnings_list.append(
            "Mố chữ U đô thị: thiết kế tường cánh song song"
            " (thay vuông góc) để hạn chế chiếm dụng mặt bằng"
        )

    if L_nhip > 20.0:
        warnings_list.append(
            f"L_nhip={L_nhip:.0f}m > 20m: mố chịu lực ngang lớn hơn"
            " — kiểm tra ổn định trượt và lật theo TCVN 11823"
        )

    cap_int = _encode_cap_duong(cap_duong) if cap_duong else 3
    if cap_int <= 2:
        ten_cap = "Cao tốc" if cap_int == 0 else f"Cấp {cap_duong.strip()}"
        warnings_list.append(
            f"{ten_cap}: bắt buộc bản dẫn và tường cánh đủ dài che kín mái taluy (TCVN 11823:2017)"
        )

    # ── Bước 4 — Kích thước sơ bộ ───────────────────────────────────────
    taluy        = 2.0 if SPT_N < 5 else 1.5
    L_tuong_canh = round(H_dap * taluy, 2)

    # Đỉnh bệ mố luôn chôn ~0.5m dưới đường tự nhiên
    # H_mo = (Z_tu_nhien + H_dap) - (Z_tu_nhien - 0.5) = H_dap + 0.5
    H_mo = round(H_dap + 0.5, 2)

    return {
        "loai_mo":      loai_mo,
        "nhom":         nhom,
        "can_ban_dan":  can_ban_dan,
        "H_mo":         H_mo,
        "L_tuong_canh": L_tuong_canh,
        "warnings":     warnings_list,
        "ghi_chu":      ABUTMENT_NOTES.get(loai_mo, ""),
        "H_dap_vung":   H_dap_vung,
    }


# ---------------------------------------------------------------------------
# CHẠY THỬ ĐỘC LẬP
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    print("=== Huấn luyện mô hình Trụ cầu (v3) ===")
    mdl = train_pier_ai()
    if mdl is None:
        print("Chưa có dữ liệu train — dùng Rule-Based fallback")
    else:
        print(f"Học từ {mdl['n_samples']} mẫu | features: {mdl['feat_cols']}")
        print(f"Các loại trụ: {mdl['classes']}")

    examples = [
        dict(vtk=60,  B_cau=8,  H_tru=3.5, is_urban=0, is_river=1,
             cap_song="VI",  loai_dam="T ngược", n_nhip=1),
        dict(vtk=80,  B_cau=14, H_tru=5.0, is_urban=1, is_river=1,
             cap_song="IV",  loai_dam="Dầm I",   n_nhip=2),
        dict(vtk=100, B_cau=22, H_tru=7.5, is_urban=0, is_river=1,
             cap_song="III", loai_dam="Super-T",  n_nhip=4),
    ]

    for i, ex in enumerate(examples, 1):
        print(f"\n{'=' * 62}")
        print(f"  VD{i}: {ex}")
        res = predict_pier(models=mdl, **ex)

        rb = res["pa_rb"]
        ai = res["pa_ai"]
        print(f"  [RB] {rb['loai_tru']:20s} | {rb['tang_quyet_dinh']}")
        print(f"       {rb['ghi_chu']}")
        print(f"  [AI] {ai['loai_tru']:20s} | {ai['do_tin_cay']:.0f}% | {ai['phuong_phap']}")
        if res["dong_thuan"]:
            print("  => Dong thuan (hai phuong an trung nhau)")
        else:
            print(f"  => CANH BAO: {res['canh_bao']}")

    # ── Kiểm chứng estimate_pier_height() ────────────────────────────────
    print(f"\n{'=' * 62}")
    print("=== Kiem chung estimate_pier_height() — 3 tinh huong ===")

    pier_examples = [
        dict(
            label="VD1 — Tren can",
            MNCN=2.5, H_tinh_khong=3.0, H_dam=1.65, MNTN=0.1,
            vi_tri_tru="tren_can", Z_tu_nhien=1.8,
        ),
        dict(
            label="VD2 — Trong nuoc be thap",
            MNCN=3.2, H_tinh_khong=4.0, H_dam=1.65, MNTN=0.2,
            vi_tri_tru="trong_nuoc_be_thap",
        ),
        dict(
            label="VD3 — Trong nuoc be cao",
            MNCN=3.2, H_tinh_khong=4.0, H_dam=1.65, MNTN=0.2,
            Z_day_song=-1.5, h_xoi_chung=1.2,
            vi_tri_tru="trong_nuoc_be_cao",
        ),
    ]

    for ex in pier_examples:
        lbl = ex.pop("label")
        r   = estimate_pier_height(**ex)
        print(f"\n  {lbl}")
        print(f"    H_than_tru   = {r['H_than_tru']:.2f} m")
        print(f"    Z_dinh_be    = {r['Z_dinh_be']:.3f} m")
        print(f"    cao_day_dam  = {r['cao_day_dam']:.3f} m")
        print(f"    cao_dinh_tru = {r['cao_dinh_tru']:.3f} m")
        print(f"    cao_mat_cau  = {r['cao_mat_cau']:.3f} m")
        print(f"    can_than_rong= {r['can_than_rong']}")
        if r["canh_bao"]:
            for line in r["canh_bao"].split("; "):
                print(f"    [!] {line}")

    # ── Kiểm chứng _classify_abutment() + predict_pier (ket_qua_mo) ─────
    print(f"\n{'=' * 62}")
    print("=== Kiem chung _classify_abutment() — 3 vi du ===")

    ab_examples = [
        dict(
            label="VD1 — Cau nong thon nho",
            vtk=60, B_cau=8, H_tru=3.5, is_urban=0, is_river=1,
            cap_song="VI", loai_dam="T ngược", n_nhip=1,
            H_dap=2.5, L_nhip=12, SPT_N=8, MNCN=1.8, Z_tu_nhien=1.5,
        ),
        dict(
            label="VD2 — Cau do thi vua",
            vtk=80, B_cau=14, H_tru=5.0, is_urban=1, is_river=1,
            cap_song="IV", loai_dam="Dầm I", n_nhip=2,
            H_dap=5.0, L_nhip=25, SPT_N=4, MNCN=2.5, Z_tu_nhien=1.8,
        ),
        dict(
            label="VD3 — Cau song lon cap III",
            vtk=100, B_cau=22, H_tru=7.5, is_urban=0, is_river=1,
            cap_song="III", loai_dam="Super-T", n_nhip=4,
            H_dap=6.5, L_nhip=33, SPT_N=12, MNCN=3.5, Z_tu_nhien=2.8,
            cap_duong="III",
        ),
    ]

    for ex in ab_examples:
        lbl = ex.pop("label")
        res = predict_pier(models=mdl, **ex)
        mo  = res["ket_qua_mo"]
        rb  = res["pa_rb"]
        print(f"\n  {lbl}")
        print(f"  [Tru] {rb['loai_tru']:20s} | {rb['tang_quyet_dinh']}")
        print(f"  [Mo]  loai_mo      = {mo['loai_mo']}")
        print(f"        nhom         = {mo['nhom']}")
        print(f"        can_ban_dan  = {mo['can_ban_dan']}")
        print(f"        H_mo         = {mo['H_mo']:.2f} m")
        print(f"        L_tuong_canh = {mo['L_tuong_canh']:.2f} m")
        print(f"        H_dap_vung   = {mo['H_dap_vung']}")
        for w in mo["warnings"]:
            print(f"        [!] {w}")
