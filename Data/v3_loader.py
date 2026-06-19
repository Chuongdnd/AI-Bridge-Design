"""
v3_loader.py — Bộ đọc dữ liệu Bridge_Train_Dataset_v3.xlsx
=============================================================
Cấu trúc mỗi sheet (0-indexed):
  Row 0 : "DATASET TRAIN — ..." (tieu de nhom)
  Row 1 : Mo ta nhom
  Row 2 : Ten cot tieng Viet
  Row 3 : Kieu du lieu (Text / Categorical / m / ...)
  Row 4 : Muc do bat buoc (LABEL / Bat buoc / ...)
  Row 5 : Gia tri hop le
  Row 6 : Python JSON key (snake_case)  <- HEADER
  Row 7 : Huong dan nhap ("← Nhap tu hang 9 ...")
  Row 8+: Du lieu thuc te (user dien sau)

Khoa noi giua cac sheet: "ten_cau".
"""

import os
import pandas as pd
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_V3 = os.path.join(_HERE, "Bridge_Train_Dataset_v3.xlsx")

# Ten sheet -> key noi bo
_SHEETS = {
    "tong_the":     "02_Tổng thể",
    "thuy_van":     "03_Thủy văn",
    "dia_chat":     "04_Địa chất",
    "mong":         "05_Móng",
    "mo_tru":       "06_Mố – Trụ",
    "ket_cau_nhip": "07_Kết cấu nhịp",
    "mat_cau":      "08_Mặt cầu",
}


def _read_sheet(xl_path: str, sheet_name: str) -> pd.DataFrame:
    """
    Doc 1 sheet v3 ve DataFrame chuan.
    - header=6  : dong Python snake_case keys lam ten cot
    - Drop row 0: dong huong dan ("← Nhap tu hang 9...")
    - Filter     : bo dong ten_cau rong
    Tra ve DataFrame rong neu chua co data thuc.
    """
    try:
        df = pd.read_excel(xl_path, sheet_name=sheet_name, header=6)
        if len(df) == 0:
            return pd.DataFrame()
        # Dong index 0 sau khi read = huong dan nhap -> bo
        df = df.iloc[1:].reset_index(drop=True)
        # Strip whitespace khoi ten cot
        df.columns = [str(c).strip() for c in df.columns]
        # Loc dong trang
        if "ten_cau" in df.columns:
            df = df.dropna(subset=["ten_cau"])
            df = df[df["ten_cau"].astype(str).str.strip().str.len() > 0]
        return df.reset_index(drop=True)
    except Exception as exc:
        print(f"[v3_loader] Loi doc sheet '{sheet_name}': {exc}")
        return pd.DataFrame()


def load_all_sheets(v3_file: str = None) -> dict:
    """
    Doc toan bo sheets v3.
    Tra ve dict {key: DataFrame}. DataFrame rong khi chua co data.
    """
    path = v3_file or _DEFAULT_V3
    if not os.path.exists(path):
        return {}
    result = {}
    for key, sh_name in _SHEETS.items():
        result[key] = _read_sheet(path, sh_name)
    return result


def _merge(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    """Gop 2 df theo ten_cau, tranh duplicate cols."""
    if left is None or left.empty:
        return right.copy() if right is not None and not right.empty else pd.DataFrame()
    if right is None or right.empty:
        return left.copy()
    new_cols = [c for c in right.columns if c not in left.columns or c == "ten_cau"]
    if "ten_cau" in right.columns and "ten_cau" in left.columns:
        return pd.merge(left, right[new_cols], on="ten_cau", how="outer")
    return left


# ─────────────────────────────────────────────────────────────────────────────
# Helpers cho tung module AI
# ─────────────────────────────────────────────────────────────────────────────

def get_kcn_df(v3_file: str = None) -> pd.DataFrame:
    """
    DataFrame cho Module 06-AI_KetCauNhip.
    Features : b_tinh_khong (B_tk), h_tinh_khong (H_tk), cap_song,
               vtk, goc_xien, b_cau/bc, l_cau, loai_vuot, loai_duong
    Targets  : loai_dam, l_tt, l_dam, h_dam, so_dam, kc_tim_dam, hang_dau_dam
    """
    sheets = load_all_sheets(v3_file)
    if not sheets:
        return pd.DataFrame()

    tv = sheets.get("thuy_van", pd.DataFrame())
    tt = sheets.get("tong_the", pd.DataFrame())
    kn = sheets.get("ket_cau_nhip", pd.DataFrame())

    tv_want = ["ten_cau","cap_song","b_tinh_khong","h_tinh_khong",
               "cao_do_mncn","cao_do_mntt","cao_do_mntc","cao_do_mntn"]
    tt_want = ["ten_cau","vtk","goc_xien","b_cau","bc","l_cau","tong_so_nhip",
               "loai_vuot","loai_duong","vung_dia_ly"]
    kn_want = ["ten_cau","loai_dam","l_tt","l_dam","h_dam","b_dam",
               "so_dam","kc_tim_dam","hang_dau_dam"]

    tv2 = tv[[c for c in tv_want if c in tv.columns]] if not tv.empty else pd.DataFrame()
    tt2 = tt[[c for c in tt_want if c in tt.columns]] if not tt.empty else pd.DataFrame()
    kn2 = kn[[c for c in kn_want if c in kn.columns]] if not kn.empty else pd.DataFrame()

    df = _merge(_merge(tv2, tt2), kn2)

    # Ep kieu so
    for c in ["b_tinh_khong","h_tinh_khong","vtk","goc_xien","b_cau","bc","l_cau",
              "l_tt","l_dam","h_dam","so_dam","kc_tim_dam","hang_dau_dam"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # bc lam b_cau neu b_cau trong
    if "bc" in df.columns:
        if "b_cau" in df.columns:
            df["b_cau"] = df["b_cau"].fillna(df["bc"])
        else:
            df["b_cau"] = df["bc"]

    # Loc dong co label
    if "loai_dam" in df.columns:
        df = df.dropna(subset=["loai_dam"])
        df = df[df["loai_dam"].astype(str).str.strip().str.len() > 0]

    return df.reset_index(drop=True)


def get_pier_df(v3_file: str = None) -> pd.DataFrame:
    """
    DataFrame cho Module 07-AI_MoTru.
    Features: vtk, b_cau (bc), h_tru, cap_song, loai_dam, loai_vuot, loai_duong
    Target  : loai_tru
    """
    sheets = load_all_sheets(v3_file)
    if not sheets:
        return pd.DataFrame()

    tt = sheets.get("tong_the", pd.DataFrame())
    tv = sheets.get("thuy_van", pd.DataFrame())
    mt = sheets.get("mo_tru", pd.DataFrame())
    kn = sheets.get("ket_cau_nhip", pd.DataFrame())

    tt_want = ["ten_cau","vtk","b_cau","bc","loai_vuot","loai_duong"]
    tv_want = ["ten_cau","cap_song"]
    mt_want = ["ten_cau","loai_tru","h_tru","so_cot","rong_tru","dai_tru"]
    kn_want = ["ten_cau","loai_dam"]

    tt2 = tt[[c for c in tt_want if c in tt.columns]] if not tt.empty else pd.DataFrame()
    tv2 = tv[[c for c in tv_want if c in tv.columns]] if not tv.empty else pd.DataFrame()
    mt2 = mt[[c for c in mt_want if c in mt.columns]] if not mt.empty else pd.DataFrame()
    kn2 = kn[[c for c in kn_want if c in kn.columns]] if not kn.empty else pd.DataFrame()

    df = _merge(_merge(_merge(tt2, tv2), mt2), kn2)

    for c in ["vtk","b_cau","bc","h_tru"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "bc" in df.columns:
        if "b_cau" in df.columns:
            df["b_cau"] = df["b_cau"].fillna(df["bc"])
        else:
            df["b_cau"] = df["bc"]

    # Is_Urban / Is_River tu loai_vuot / loai_duong
    if "loai_vuot" in df.columns:
        df["is_river"] = df["loai_vuot"].astype(str).str.lower().str.contains(
            "song|kenh", na=False).astype(int)
    if "loai_duong" in df.columns:
        df["is_urban"] = df["loai_duong"].astype(str).str.lower().str.contains(
            "do thi|urban", na=False).astype(int)

    if "loai_tru" in df.columns:
        df = df.dropna(subset=["loai_tru"])
        df = df[df["loai_tru"].astype(str).str.strip().str.len() > 0]
        df = df[~df["loai_tru"].astype(str).str.contains("Không có|Không trụ", na=False)]

    return df.reset_index(drop=True)


def get_foundation_df(v3_file: str = None) -> pd.DataFrame:
    """
    DataFrame cho Module 08-AI_Mong.
    Features: h_tru, loai_tru, cap_song, b_cau, vtk, is_river, is_urban
    Targets : loai_mong, chieu_dai_coc, duong_kinh_coc, so_coc, pp_tc_coc
    """
    sheets = load_all_sheets(v3_file)
    if not sheets:
        return pd.DataFrame()

    tt = sheets.get("tong_the", pd.DataFrame())
    tv = sheets.get("thuy_van", pd.DataFrame())
    mt = sheets.get("mo_tru", pd.DataFrame())
    mg = sheets.get("mong", pd.DataFrame())

    tt_want = ["ten_cau","vtk","b_cau","bc","loai_vuot","loai_duong"]
    tv_want = ["ten_cau","cap_song"]
    mt_want = ["ten_cau","h_tru","loai_tru"]
    mg_want = ["ten_cau","loai_mong","so_coc","chieu_dai_coc","duong_kinh_coc","pp_tc_coc"]

    tt2 = tt[[c for c in tt_want if c in tt.columns]] if not tt.empty else pd.DataFrame()
    tv2 = tv[[c for c in tv_want if c in tv.columns]] if not tv.empty else pd.DataFrame()
    mt2 = mt[[c for c in mt_want if c in mt.columns]] if not mt.empty else pd.DataFrame()
    mg2 = mg[[c for c in mg_want if c in mg.columns]] if not mg.empty else pd.DataFrame()

    df = _merge(_merge(_merge(tt2, tv2), mt2), mg2)

    for c in ["vtk","b_cau","bc","h_tru","chieu_dai_coc","duong_kinh_coc","so_coc"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "bc" in df.columns:
        if "b_cau" in df.columns:
            df["b_cau"] = df["b_cau"].fillna(df["bc"])
        else:
            df["b_cau"] = df["bc"]

    if "loai_vuot" in df.columns:
        df["is_river"] = df["loai_vuot"].astype(str).str.lower().str.contains(
            "song|kenh", na=False).astype(int)
    if "loai_duong" in df.columns:
        df["is_urban"] = df["loai_duong"].astype(str).str.lower().str.contains(
            "do thi", na=False).astype(int)

    if "loai_mong" in df.columns:
        df = df.dropna(subset=["loai_mong"])
        df = df[df["loai_mong"].astype(str).str.strip().str.len() > 0]

    return df.reset_index(drop=True)


def has_data(v3_file: str = None, min_rows: int = 5) -> bool:
    """Kiem tra nhanh xem v3 co du du lieu de train khong."""
    path = v3_file or _DEFAULT_V3
    if not os.path.exists(path):
        return False
    df = _read_sheet(path, "07_Kết cấu nhịp")
    if df.empty:
        return False
    if "loai_dam" in df.columns:
        valid = df.dropna(subset=["loai_dam"])
        valid = valid[valid["loai_dam"].astype(str).str.strip().str.len() > 0]
        return len(valid) >= min_rows
    return len(df) >= min_rows
