"""
Module 07 — AI Mo - Tru (Pier Classification AI)
Data  : Bridge_Train_Dataset_v3.xlsx — sheet 06_Mo-Tru + 02 + 03 + 07
Features: Vtk, B_cau, H_tru, Is_Urban, Is_River, Cap_song, Loai_dam
Label   : Loai_tru (phan loai tru)
Fallback: Rule-Based khi chua co du lieu train

Phân loại TRỤ theo 3 NHÓM cấu tạo chính (PIER_TYPES):
  1. Trụ DẺO (Trụ cọc)      — nhịp ngắn ≤12m, trụ thấp ≤4m, không thông thuyền
  2. Trụ CỘT (thân cột BTCT) — cầu cạn/cầu vượt/sông cấp IV–VI; 1 cột (đô thị)
                               hoặc nhiều cột (2–4) theo bề rộng cầu
  3. Trụ ĐẶC THÂN HẸP        — sông lớn cấp I–III, va tàu; H>10m → biến thể rỗng
Kết quả trả đồng thời nhom_tru (dẻo/cột/đặc thân hẹp) + loai_tru chi tiết.

MỐ: mọi mố BẮT BUỘC có BẢN QUÁ ĐỘ (ban_qua_do trong ket_qua_mo) — kích thước
theo quy mô cầu (BAN_QUA_DO_CONFIG), dày ≥30cm, dốc 10–15%, đất đắp ≥70cm.
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

# ---------------------------------------------------------------------------
# PHÂN LOẠI TRỤ THEO 3 NHÓM CẤU TẠO CHÍNH
# ---------------------------------------------------------------------------
# Mỗi nhóm có đặc điểm cấu tạo + điều kiện áp dụng riêng; loại con trong nhóm
# xác định sau khi đã chọn nhóm (xem _rule_based_pier).
PIER_TYPES = {
    "dẻo": {
        "ten_nhom": "Trụ dẻo (Trụ cọc)",
        "dac_diem": (
            "1 hoặc 2 hàng cọc tiết diện nhỏ 30×30 đến 40×40 cm liên kết "
            "TRỰC TIẾP với xà mũ, KHÔNG có bệ trụ riêng."
        ),
        "dieu_kien": (
            "Cầu nhiều nhịp ngắn L_nhịp ≤ 12m; trụ thấp H_trụ ≤ 4m; lòng "
            "sông không sâu, không thông thuyền (không vượt sông hoặc sông "
            "cấp V–VI). Thường kết hợp với Mố dẻo (Mố chân dê)."
        ),
        "loai": ["Trụ cọc"],
    },
    "cột": {
        "ten_nhom": "Trụ cột (Trụ thân cột BTCT)",
        "dac_diem": (
            "Thanh mảnh: 1 hoặc nhiều cột tròn/chữ nhật liên kết với xà mũ "
            "chịu uốn, CÓ bệ móng riêng. Đường kính cột phổ biến 0.8–2m, "
            "cá biệt 3m."
        ),
        "dieu_kien": (
            "Cầu cạn, cầu vượt, cầu vượt sông cấp IV–VI ít cây trôi, nhịp "
            "trung bình. Trụ 1 cột cho cầu vượt đô thị (giải phóng tối đa "
            "không gian gầm cầu); trụ nhiều cột (2–4) cho cầu vừa và rộng."
        ),
        "loai": ["Trụ cột đơn", "Thân cột 2 trụ", "Thân cột 3 trụ",
                 "Thân cột 4 trụ"],
    },
    "đặc thân hẹp": {
        "ten_nhom": "Trụ đặc thân hẹp",
        "dac_diem": (
            "Phần thân dưới THU HẸP so với bề rộng kết cấu nhịp (ngược với "
            "2 nhóm trên). Mũi vát nhọn, hệ số cản dòng chảy CD = 0.7–0.8."
        ),
        "dieu_kien": (
            "Cầu vượt sông lớn cấp I–III, chịu va tàu lớn, nhiều cây trôi. "
            "Khi H_trụ > 10m chuyển sang biến thể Trụ đặc thân hẹp RỖNG để "
            "giảm khối lượng vật liệu."
        ),
        "loai": ["Trụ đặc thân hẹp", "Trụ đặc thân hẹp rỗng"],
    },
}

# Danh sách phẳng tương thích ngược (code cũ duyệt PIER_TYPES như list)
PIER_TYPES_FLAT = [lt for g in PIER_TYPES.values() for lt in g["loai"]]


def nhom_tru_of(loai_tru: str) -> str:
    """Tra NHÓM cấu tạo ('dẻo'/'cột'/'đặc thân hẹp') từ tên loại trụ chi tiết.
    Nhận cả tên cũ ('Trụ đặc', 'Thân rỗng'…) để tương thích dữ liệu đã lưu."""
    s = str(loai_tru or "").strip().lower()
    for nhom, g in PIER_TYPES.items():
        if any(s == lt.lower() for lt in g["loai"]):
            return nhom
    if "cọc" in s:
        return "dẻo"
    if "đặc" in s or "rỗng" in s:
        return "đặc thân hẹp"
    if "cột" in s:
        return "cột"
    return "cột"


# Ghi chú kỹ thuật tra cứu ưu nhược điểm (dùng trong UI để hiển thị tooltip)
PIER_NOTES = {
    # ── Nhóm 1 — Trụ dẻo ────────────────────────────────────────────────
    "Trụ cọc": (
        "Nhóm TRỤ DẺO: 1–2 hàng cọc 30×30 đến 40×40 cm liên kết trực tiếp "
        "xà mũ, KHÔNG bệ trụ riêng — cấu tạo đơn giản, kinh tế nhất cho cầu "
        "nhiều nhịp ngắn ≤ 12m, trụ thấp ≤ 4m, lòng sông nông không thông "
        "thuyền. Thường đi cùng Mố dẻo (chân dê). Không dùng nơi va xô lớn."
    ),
    # ── Nhóm 2 — Trụ cột ────────────────────────────────────────────────
    "Trụ cột đơn": (
        "Nhóm TRỤ CỘT: 1 cột (tròn/chữ nhật, D phổ biến 0.8–2m, cá biệt 3m) "
        "+ bệ móng riêng. Giải phóng tối đa không gian dưới gầm — chuẩn cho "
        "cầu vượt đô thị, cầu cong/chéo. Yêu cầu móng tập trung vững chắc "
        "(cọc khoan nhồi đường kính lớn)."
    ),
    "Thân cột 2 trụ": (
        "Nhóm TRỤ CỘT: khung ngang 2 cột + xà mũ chịu uốn, có bệ móng riêng. "
        "Phân tán lực tốt, thi công nhanh, phù hợp cầu vừa B<16m; cầu cạn / "
        "sông cấp IV–VI ít cây trôi. Chú ý xói lở và rác kẹt chân cột."
    ),
    "Thân cột 3 trụ": (
        "Nhóm TRỤ CỘT: 3 cột cho cầu rộng 16–24m, phân tán tải đều. "
        "Thi công phức tạp hơn 2 cột; nhiều cấu kiện phơi lộ hơn."
    ),
    "Thân cột 4 trụ": (
        "Nhóm TRỤ CỘT: 4 cột cho cầu rất rộng ≥ 24m. "
        "Kiểm tra phân bố tải xà mũ và độ cứng ngang tổng thể."
    ),
    # ── Nhóm 3 — Trụ đặc thân hẹp ───────────────────────────────────────
    "Trụ đặc thân hẹp": (
        "Nhóm TRỤ ĐẶC THÂN HẸP: thân dưới thu hẹp so với bề rộng nhịp, mũi "
        "vát nhọn CD=0.7–0.8 giảm cản dòng. Chịu va tàu lớn, chống cây trôi "
        "— chuẩn cho sông cấp I–III. Không cần ụ bảo vệ riêng; chi phí ban "
        "đầu cao nhưng kinh tế dài hạn tại luồng nhộn nhịp."
    ),
    "Trụ đặc thân hẹp rỗng": (
        "Biến thể RỖNG của trụ đặc thân hẹp khi H_trụ > 10m — giảm khối "
        "lượng vật liệu, giữ khả năng chịu va tàu. Thi công yêu cầu ván "
        "khuôn trượt/leo; tham vấn chuyên gia tại giai đoạn TKKT."
    ),
    # ── Tên cũ (tương thích dữ liệu đã lưu) ─────────────────────────────
    "Trụ đặc": (
        "Tên cũ (≤ v2). Độ cứng cao, thi công đơn giản, phù hợp trụ thấp; "
        "phân loại mới xếp theo nhóm TRỤ ĐẶC THÂN HẸP."
    ),
    "Thân rỗng": (
        "Tên cũ (≤ v2) cho trụ cao > 10m; phân loại mới dùng "
        "'Trụ đặc thân hẹp rỗng' trong nhóm TRỤ ĐẶC THÂN HẸP."
    ),
}

# ---------------------------------------------------------------------------
# BẢN QUÁ ĐỘ — CẤU KIỆN BẮT BUỘC CHO MỌI MỐ CẦU
# ---------------------------------------------------------------------------
# 4 chức năng thiết yếu: (1) khắc phục điểm xóc đầu cầu do đất đắp trong lòng
# mố khó đạt độ chặt tuyệt đối; (2) chuyển tiếp độ cứng dần dần giữa nền đường
# mềm và mố cầu cứng; (3) xử lý bù trừ lún chênh lệch khi độ chênh < 5cm;
# (4) phân phối lại tải trọng (đất đắp + hoạt tải xe) lên mố theo hướng tích
# cực cho ổn định.
BAN_QUA_DO_CONFIG = {
    # Chiều dài bản theo QUY MÔ CẦU (L_cau = chiều dài toàn cầu, m)
    "chieu_dai_theo_quy_mo": [
        {"quy_mo": "Cầu nhỏ (L ≤ 25m)",        "L_max_cau": 25.0,
         "L_bqd_min": 5.0,  "L_bqd_max": 5.0},
        {"quy_mo": "Cầu trung (25 < L ≤ 100m)", "L_max_cau": 100.0,
         "L_bqd_min": 6.0,  "L_bqd_max": 8.0},
        {"quy_mo": "Cầu lớn (L > 100m)",        "L_max_cau": None,
         "L_bqd_min": 8.0,  "L_bqd_max": 12.0},
    ],
    # Thông số cấu tạo CỐ ĐỊNH
    "day_bqd_min_m":       0.30,   # chiều dày bản ≥ 30cm
    "doc_bqd_min":         0.10,   # độ dốc dọc 10–15% về phía nền đường
    "doc_bqd_max":         0.15,
    "chieu_sau_dat_dap_m": 0.70,   # đất đắp mặt đường → mặt bản ≥ 70cm
    "vat_lieu":            "BTCT M300 đổ tại chỗ hoặc đúc sẵn",
    "vi_tri_lap_dat": (
        "Một đầu bản kê lên tường đỉnh mố, đầu còn lại đặt trên dầm kê "
        "nằm trong nền đường."
    ),
    "chuc_nang": [
        "Khắc phục hiện tượng điểm xóc đầu cầu (đất đắp trong lòng mố khó "
        "đạt độ chặt tuyệt đối)",
        "Chuyển tiếp độ cứng dần dần giữa nền đường mềm và mố cầu cứng",
        "Xử lý lún chênh lệch — bù trừ khi độ chênh < 5cm",
        "Phân phối lại tải trọng đất đắp + hoạt tải xe lên mố theo hướng "
        "tích cực cho ổn định",
    ],
}


def _calc_ban_qua_do(L_cau=None):
    """
    Tính thông số BẢN QUÁ ĐỘ (cấu kiện BẮT BUỘC cho mọi mố) theo quy mô cầu.

    Parameters
    ----------
    L_cau : float or None — chiều dài toàn cầu (m), từ geo_logic["L_cau"]
            (Module 02). None → fallback 25m (cầu nhỏ) kèm cảnh báo.

    Returns
    -------
    dict: L_bqd (m, giá trị chọn), L_bqd_range (chuỗi khoảng quy định),
          quy_mo_cau, day_bqd, doc_bqd (chuỗi), doc_bqd_val (số),
          chieu_sau_dat_dap_toi_thieu, vat_lieu, vi_tri_lap_dat,
          chuc_nang (list), canh_bao ('' nếu đủ dữ liệu).
    """
    cfg = BAN_QUA_DO_CONFIG
    canh_bao = ""
    if not L_cau or float(L_cau) <= 0:
        L_cau = 25.0
        canh_bao = ("Chưa có L_cau từ Module 02 (geo_logic) — tạm dùng 25m "
                    "(cầu nhỏ) để tính bản quá độ; chạy pipeline đầy đủ để "
                    "cập nhật.")
    L_cau = float(L_cau)

    for band in cfg["chieu_dai_theo_quy_mo"]:
        if band["L_max_cau"] is None or L_cau <= band["L_max_cau"]:
            break
    lo, hi = band["L_bqd_min"], band["L_bqd_max"]
    # Giá trị chọn: nội suy tuyến tính trong khoảng quy định theo L_cau
    if hi > lo:
        if band["L_max_cau"] is not None:            # cầu trung 25→100m
            t = (L_cau - 25.0) / (band["L_max_cau"] - 25.0)
        else:                                        # cầu lớn 100m→300m (chặn)
            t = min(1.0, (L_cau - 100.0) / 200.0)
        L_bqd = round((lo + max(0.0, min(1.0, t)) * (hi - lo)) * 2) / 2.0
    else:
        L_bqd = lo

    return {
        "L_bqd":       L_bqd,
        "L_bqd_range": (f"{lo:g}m" if hi == lo else f"{lo:g}–{hi:g}m"),
        "quy_mo_cau":  band["quy_mo"],
        "day_bqd":     cfg["day_bqd_min_m"],
        "doc_bqd":     (f"{cfg['doc_bqd_min']*100:.0f}–"
                        f"{cfg['doc_bqd_max']*100:.0f}% về phía nền đường"),
        "doc_bqd_val": cfg["doc_bqd_min"],
        "chieu_sau_dat_dap_toi_thieu": cfg["chieu_sau_dat_dap_m"],
        "vat_lieu":       cfg["vat_lieu"],
        "vi_tri_lap_dat": cfg["vi_tri_lap_dat"],
        "chuc_nang":      list(cfg["chuc_nang"]),
        "canh_bao":       canh_bao,
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
# 3. QUY TẮC KỸ THUẬT — PHÂN NHÓM TRƯỚC, LOẠI CON SAU
# ---------------------------------------------------------------------------
def _rule_based_pier(vtk, B_cau, H_tru, is_urban, is_river,
                     cap_song="VI", loai_dam="", n_nhip=1, note="",
                     L_nhip=None):
    """
    Phân loại trụ theo 3 NHÓM cấu tạo chính (PIER_TYPES), sau đó xác định
    LOẠI CON trong nhóm.

    Bước 1 — PHÂN NHÓM theo điều kiện chính:
      • Nhóm DẺO (Trụ cọc): L_nhịp ≤ 12m, H_trụ ≤ 4m, không thông thuyền
        (không vượt sông hoặc sông cấp V–VI). Cọc nhỏ 30×30–40×40cm nối
        thẳng xà mũ, không bệ riêng; thường đi cùng Mố chân dê.
      • Nhóm ĐẶC THÂN HẸP: vượt sông LỚN cấp I–III (va tàu lớn, cây trôi).
        Thân dưới thu hẹp, mũi vát CD=0.7–0.8.
      • Nhóm CỘT (còn lại): cầu cạn/cầu vượt/sông cấp IV–VI ít cây trôi.

    Bước 2 — LOẠI CON trong nhóm:
      • Dẻo         → "Trụ cọc".
      • Cột         → đô thị hoặc B<10m: "Trụ cột đơn" (giải phóng gầm cầu);
                      B<16m: 2 cột; B<24m: 3 cột; còn lại: 4 cột.
      • Đặc thân hẹp→ H ≤ 10m: "Trụ đặc thân hẹp";
                      H > 10m: "Trụ đặc thân hẹp rỗng" (giảm vật liệu).

    Returns dict có ĐỒNG THỜI nhom_tru (dẻo/cột/đặc thân hẹp — giao diện và
    Module 11 dùng) và loai_tru chi tiết (tương thích ngược code cũ).
    """
    cap_int = _encode_cap_song(cap_song) if cap_song else 4
    _L_nhip = float(L_nhip) if L_nhip else 20.0
    notes = []

    # ── Bước 1 — PHÂN NHÓM ──────────────────────────────────────────────
    khong_thong_thuyen = (not is_river) or cap_int >= 5
    if _L_nhip <= 12.0 and H_tru <= 4.0 and khong_thong_thuyen:
        nhom = "dẻo"
        tang = "Nhóm 1 — Trụ dẻo (Trụ cọc)"
        notes.append(
            f"L_nhịp={_L_nhip:.0f}m ≤ 12m, H_trụ={H_tru:.1f}m ≤ 4m, "
            + ("không vượt sông" if not is_river else f"sông cấp {cap_song} không thông thuyền")
            + " — trụ dẻo: cọc 30×30–40×40cm nối trực tiếp xà mũ, không bệ "
              "riêng; kết hợp Mố dẻo (chân dê)")
    elif is_river and cap_int <= 3:
        nhom = "đặc thân hẹp"
        tang = "Nhóm 3 — Trụ đặc thân hẹp"
        notes.append(
            f"Sông lớn cấp {cap_song} — va tàu lớn, nhiều cây trôi: thân "
            "dưới thu hẹp, mũi vát nhọn CD=0.7–0.8")
    else:
        nhom = "cột"
        tang = "Nhóm 2 — Trụ cột"
        notes.append(
            ("Cầu cạn/cầu vượt" if not is_river else f"Sông cấp {cap_song} ít cây trôi")
            + " — trụ thân cột BTCT (cột D 0.8–2m, có bệ móng riêng)")

    # ── Bước 2 — LOẠI CON trong nhóm ────────────────────────────────────
    if nhom == "dẻo":
        loai = "Trụ cọc"

    elif nhom == "đặc thân hẹp":
        if H_tru > 10.0:
            loai = "Trụ đặc thân hẹp rỗng"
            notes.append(
                f"H_trụ={H_tru:.1f}m > 10m — biến thể thân RỖNG giảm khối "
                "lượng vật liệu")
        else:
            loai = "Trụ đặc thân hẹp"

    else:  # nhóm cột
        if is_urban:
            loai = "Trụ cột đơn"
            notes.append(
                "Đô thị — trụ 1 cột giải phóng tối đa không gian dưới gầm cầu")
        elif B_cau < 10:
            loai = "Trụ cột đơn"
            notes.append(f"B_cau={B_cau:.1f}m < 10m — cầu hẹp, 1 cột đủ")
        elif B_cau < 16:
            loai = "Thân cột 2 trụ"
            notes.append(f"B_cau={B_cau:.1f}m — cầu vừa, 2 cột")
        elif B_cau < 24:
            loai = "Thân cột 3 trụ"
            notes.append(f"B_cau={B_cau:.1f}m — cầu rộng, 3 cột")
        else:
            loai = "Thân cột 4 trụ"
            notes.append(f"B_cau={B_cau:.1f}m ≥ 24m — cầu rất rộng, 4 cột")

        # Điều chỉnh tải trọng nặng: nhiều nhịp dầm nặng KHÔNG đô thị → ≥2 cột
        _HEAVY = ("Super-T", "Dầm I")
        loai_dam_str = str(loai_dam).strip()
        if (loai_dam_str in _HEAVY and n_nhip >= 4
                and loai == "Trụ cột đơn" and not is_urban):
            loai = "Thân cột 2 trụ"
            notes.append(
                f"{loai_dam_str} × {n_nhip} nhịp — tải lớn, nâng lên 2 cột")
        if loai_dam_str in _HEAVY and cap_int >= 5 and is_river:
            notes.append(
                f"Lưu ý: {loai_dam_str} trên sông cấp V–VI — kiểm tra xói "
                "cục bộ chân cột")
        if H_tru > 10.0:
            notes.append(
                f"H_trụ={H_tru:.1f}m > 10m — cột mảnh, kiểm tra ổn định "
                "uốn dọc; cân nhắc tiết diện rỗng ở TKKT")

    ghi_chu = "; ".join(notes)
    if note:
        ghi_chu = (ghi_chu + ". " + note).strip()

    return {
        "loai_tru":        loai,          # chi tiết (tương thích ngược)
        "nhom_tru":        nhom,          # dẻo / cột / đặc thân hẹp
        "ten_nhom":        PIER_TYPES[nhom]["ten_nhom"],
        "do_tin_cay":      100.0,
        "tang_quyet_dinh": tang,
        "ghi_chu":         ghi_chu,
        "phuong_phap":     "Rule-Based",
    }


# ---------------------------------------------------------------------------
# 4. HÀM DỰ ĐOÁN — TRẢ VỀ 2 PHƯƠNG ÁN
# ---------------------------------------------------------------------------
def predict_pier(vtk, B_cau, H_tru, is_urban, is_river, cap_song,
                 loai_dam, n_nhip=1, models=None,
                 # ── Tham số phân loại mố (tất cả có default, tương thích ngược) ──
                 H_dap=3.0, L_nhip=20.0, SPT_N=10,
                 MNCN=None, MNTN=None, Z_tu_nhien=None,
                 is_tidal=0, cap_duong="", L_cau=None):
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
    L_nhip           : Chiều dài nhịp biên (m) — cũng dùng phân nhóm trụ dẻo
    SPT_N            : Chỉ số SPT tại vị trí mố
    MNCN             : Mực nước cao nhất (m), None nếu không áp dụng
    MNTN             : Mực nước thấp nhất (m)
    Z_tu_nhien       : Cao độ tự nhiên tại vị trí mố (m)
    is_tidal         : 1 nếu vùng triều
    cap_duong        : Cấp đường ('Cao tốc'/'I'/'II'/...'VI')
    L_cau            : Chiều dài toàn cầu (m) — tính BẢN QUÁ ĐỘ (bắt buộc);
                       None → fallback 25m kèm cảnh báo trong ban_qua_do.

    Returns
    -------
    dict: loai_tru, nhom_tru, pa_rb, pa_ai, dong_thuan, canh_bao, ket_qua_mo
          (ket_qua_mo LUÔN có key ban_qua_do — cấu kiện bắt buộc).
    """
    # Phương án Rule-Based (luôn tính) — phân NHÓM trước, loại con sau
    pa_rb = _rule_based_pier(
        vtk, B_cau, H_tru, is_urban, is_river,
        cap_song=cap_song, loai_dam=loai_dam, n_nhip=n_nhip,
        L_nhip=L_nhip,
    )

    # Phương án AI
    if models is None:
        # Chưa có mô hình → lặp lại RB
        pa_ai = {
            "loai_tru":    pa_rb["loai_tru"],
            "nhom_tru":    pa_rb["nhom_tru"],
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
                "nhom_tru":    nhom_tru_of(loai_ai),
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
                L_nhip=L_nhip, note=f"[fallback AI lỗi: {e}]",
            )
            pa_ai = {
                "loai_tru":    rb_fb["loai_tru"],
                "nhom_tru":    rb_fb["nhom_tru"],
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
        is_tidal=is_tidal, cap_duong=cap_duong, L_cau=L_cau,
    )

    return {
        # ── Convenience keys (tương thích ngược với các module cũ) ──
        "loai_tru":   pa_rb["loai_tru"],
        "nhom_tru":   pa_rb["nhom_tru"],
        "ten_nhom":   pa_rb.get("ten_nhom", ""),
        "do_tin_cay": pa_rb["do_tin_cay"],
        # ── Hai phương án đầy đủ ──
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
    t_ban=0.20,
    t_phu=0.05,
    MNTT=None,
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
    Z_tu_nhien    : Cao độ ĐƯỜNG TỰ NHIÊN tại vị trí trụ (m) — cơ sở tính đỉnh bệ
                    (đỉnh bệ = Z_tu_nhien − 0.5m). Là đáy sông nếu trụ trong nước,
                    mặt đất nếu trụ trên cạn. Nên truyền theo từng vị trí trụ.
    h_xa_mu       : Chiều cao xà mũ (m), mặc định 1.2

    Returns
    -------
    dict gồm: H_than_tru, cao_day_dam, cao_mat_cau, Z_dinh_be,
              cao_dinh_tru, can_than_rong, canh_bao, vi_tri_tru

    Quy tắc đỉnh bệ (Z_dinh_be):

    • Bệ thấp / trên cạn (mặc định) — đỉnh bệ CHÔN ~0.5m DƯỚI ĐƯỜNG TỰ NHIÊN
        tại vị trí trụ; KHÔNG lấy theo MNTN cho toàn tuyến. "Đường tự nhiên" tại
        trụ là cao độ đáy sông (trụ trong nước) hoặc mặt đất (trụ trên cạn) → mỗi
        trụ một cao độ riêng nên chiều cao thân trụ cũng khác nhau.
        Z_dinh_be = Z_tu_nhien − 0.5
        (đồng bộ quy ước đỉnh bệ MỐ trong _classify_abutment: chôn 0.5m dưới ĐTN).

    • trong_nuoc_be_cao — trường hợp đặc biệt, đài cọc cao lộ trước dòng chảy:
        đỉnh bệ khống chế theo đáy sông sau xói + dự phòng 0.5m (TCVN 11823).
        Z_dinh_be = Z_day_song − h_xoi_chung − 0.5
        Phát sinh cảnh báo: xói cục bộ chân cọc lộ, lực đẩy nổi, va trôi.
    """
    # Cao độ đáy dầm (đáy dầm BIÊN — điểm THẤP NHẤT) tối thiểu theo TCVN 8818
    # điều 4.3, lấy GIÁ TRỊ LỚN HƠN của 2 điều kiện (tĩnh không nào cao nhất):
    #   ĐK1 — an toàn lũ:      đáy dầm ≥ MNCN + 0.50m
    #   ĐK2 — thông thuyền:    đáy dầm ≥ MNTT + H_tĩnh_không + 0.10m
    # (KHÔNG lấy MNCN + H_tĩnh_không — đó là ghép sai mực nước lũ với khổ thông
    #  thuyền → tĩnh không "phụ" không đúng chuẩn.)
    _mntt = float(MNTT) if MNTT is not None else float(MNCN)
    cao_do_an_toan      = float(MNCN) + 0.50
    cao_do_thong_thuyen = _mntt + float(H_tinh_khong) + 0.10
    cao_day_dam   = max(cao_do_an_toan, cao_do_thong_thuyen)
    # Mặt cầu hoàn thiện = đáy dầm + chiều cao dầm + bản BTCT + lớp phủ
    # (đồng bộ với bản vẽ: z_deck = đáy dầm + H_dam + t_ban; mặt phủ trên đó).
    cao_mat_cau   = cao_day_dam + H_dam + float(t_ban) + float(t_phu)
    cao_dinh_tru  = cao_day_dam                  # đỉnh trụ = đỉnh xà mũ = đáy dầm
    cao_dinh_than = cao_day_dam - h_xa_mu        # đỉnh thân = đáy xà mũ

    canh_bao_list = []

    if vi_tri_tru == "trong_nuoc_be_cao":
        # Trường hợp đặc biệt: bệ cao, cọc lộ trước dòng chảy → đỉnh bệ khống chế
        # theo đáy sông sau xói (KHÔNG theo đường tự nhiên).
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
        # Quy tắc chung (bệ thấp / trên cạn): đỉnh bệ CHÔN ~0.5m DƯỚI ĐƯỜNG TỰ
        # NHIÊN tại vị trí trụ — KHÔNG lấy theo MNTN cho toàn tuyến.
        if Z_tu_nhien is not None:
            z_tn = float(Z_tu_nhien)
        elif Z_day_song is not None:
            z_tn = float(Z_day_song)
        else:
            # Dự phòng cuối: thiếu địa hình → xấp xỉ đáy sông ≈ MNTN (chỉ để hàm
            # vẫn chạy; nên truyền Z_tu_nhien theo từng trụ để chính xác).
            z_tn = MNTN
            canh_bao_list.append(
                "THIẾU cao độ tự nhiên tại trụ — tạm lấy ≈ MNTN; khai báo địa hình "
                "để đỉnh bệ bám đúng đường tự nhiên (đỉnh bệ = ĐTN − 0.5m)"
            )
        Z_dinh_be = z_tn - 0.5
        if vi_tri_tru not in ("tren_can", "trong_nuoc_be_thap"):
            vi_tri_tru = "trong_nuoc_be_thap"

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
    L_cau=None,
):
    """
    Phân loại mố cầu trong phạm vi đề tài (2 loại: Mố chân dê / Mố chữ U).

    Bước 1 — Chọn loại mố theo H_dap (quyết định cứng, không thay đổi):
        H_dap ≤ 4m  →  Mố chân dê   (nhóm dẻo)
        H_dap > 4m  →  Mố chữ U     (nhóm cứng)

    Bước 2 — BẢN QUÁ ĐỘ: cấu kiện BẮT BUỘC cho MỌI mố (không còn tùy chọn).
        Kích thước theo quy mô cầu (BAN_QUA_DO_CONFIG / _calc_ban_qua_do):
        L_cau ≤ 25m → L_bqd ≥ 5m; 25–100m → 6–8m; > 100m → 8–12m.
        Dày ≥ 30cm; dốc dọc 10–15% về phía nền đường; đất đắp mặt đường →
        mặt bản ≥ 70cm; BTCT đổ tại chỗ hoặc đúc sẵn. Một đầu kê tường đỉnh
        mố, đầu kia đặt trên dầm kê trong nền đường. (Bản dẫn/can_ban_dan cũ
        giữ nguyên để tương thích — nay đồng nghĩa bản quá độ bắt buộc.)

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
    dict: loai_mo, nhom, can_ban_dan, ban_qua_do (BẮT BUỘC), H_mo,
          L_tuong_canh, warnings, ghi_chu, H_dap_vung
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

    # ── Bước 2 — BẢN QUÁ ĐỘ bắt buộc cho mọi mố ─────────────────────────
    can_ban_dan = True                       # giữ key cũ (tương thích ngược)
    ban_qua_do = _calc_ban_qua_do(L_cau)

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

    if ban_qua_do.get("canh_bao"):
        warnings_list.append(ban_qua_do["canh_bao"])

    return {
        "loai_mo":      loai_mo,
        "nhom":         nhom,
        "can_ban_dan":  can_ban_dan,
        "ban_qua_do":   ban_qua_do,          # BẮT BUỘC cho mọi mố
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
        print(f"  [RB] {rb['loai_tru']:20s} | nhóm: {rb['nhom_tru']:14s} | {rb['tang_quyet_dinh']}")
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
        bqd = mo["ban_qua_do"]
        print(f"  [BQD] L={bqd['L_bqd']:g}m ({bqd['L_bqd_range']}, {bqd['quy_mo_cau']}) | "
              f"dày={bqd['day_bqd']:g}m | dốc {bqd['doc_bqd']} | đắp ≥{bqd['chieu_sau_dat_dap_toi_thieu']:g}m")
        for w in mo["warnings"]:
            print(f"        [!] {w}")
