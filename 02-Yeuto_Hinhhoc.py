import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# TCVN 4054:2005 — Mục 4.1.2 — Chiều rộng TỐI THIỂU các yếu tố trên MCN đường Ô TÔ
# ─────────────────────────────────────────────────────────────────────────────
# Bảng 6 — áp dụng cho địa hình ĐỒNG BẰNG và ĐỒI (cấp I–VI)
#   so_lan          : số làn xe tối thiểu dành cho xe cơ giới (làn) — TỔNG cả 2 hướng
#   w_lan           : chiều rộng 1 làn xe (m)
#   hai_chieu_rieng : True nếu phần xe chạy 2 hướng tách riêng bởi dải phân cách
#                     (cấp I, II — ghi "2 x ..." trong bảng); chỉ ảnh hưởng cách
#                     hiển thị/vẽ MCN, KHÔNG ảnh hưởng tổng chiều rộng xe chạy
#                     (= so_lan × w_lan trong mọi trường hợp).
#   w_dpc           : chiều rộng dải phân cách giữa (m), tối thiểu
#   w_le            : chiều rộng lề đường (m), tối thiểu (gồm cả phần gia cố)
#   w_le_gc         : chiều rộng lề GIA CỐ (m), tối thiểu — None nếu bảng không quy định
#   w_nen           : chiều rộng nền đường (m), tối thiểu — dùng để kiểm tra chéo
#                      (w_nen ≈ so_lan*w_lan + w_dpc + 2*w_le)
_B6_DONGBANG_DOI = {
    "I":   {"vtk": 120, "so_lan": 6, "w_lan": 3.75, "hai_chieu_rieng": True,
            "w_dpc": 3.00, "w_le": 3.50, "w_le_gc": 3.00, "w_nen": 32.5},
    "II":  {"vtk": 100, "so_lan": 4, "w_lan": 3.75, "hai_chieu_rieng": True,
            "w_dpc": 1.50, "w_le": 3.00, "w_le_gc": 2.50, "w_nen": 22.5},
    "III": {"vtk": 80,  "so_lan": 2, "w_lan": 3.50, "hai_chieu_rieng": False,
            "w_dpc": 0.00, "w_le": 2.50, "w_le_gc": 2.00, "w_nen": 12.0},
    "IV":  {"vtk": 60,  "so_lan": 2, "w_lan": 3.50, "hai_chieu_rieng": False,
            "w_dpc": 0.00, "w_le": 1.00, "w_le_gc": 0.50, "w_nen": 9.0},
    "V":   {"vtk": 40,  "so_lan": 2, "w_lan": 2.75, "hai_chieu_rieng": False,
            "w_dpc": 0.00, "w_le": 1.00, "w_le_gc": 0.50, "w_nen": 7.5},
    "VI":  {"vtk": 30,  "so_lan": 1, "w_lan": 3.50, "hai_chieu_rieng": False,
            "w_dpc": 0.00, "w_le": 1.50, "w_le_gc": None, "w_nen": 6.5},
}

# Bảng 7 — áp dụng cho địa hình VÙNG NÚI (chỉ cấp III–VI)
_B7_VUNGNUI = {
    "III": {"vtk": 60, "so_lan": 2, "w_lan": 3.00, "hai_chieu_rieng": False,
            "w_dpc": 0.00, "w_le": 1.50, "w_le_gc": 1.00, "w_nen": 9.0},
    "IV":  {"vtk": 40, "so_lan": 2, "w_lan": 2.75, "hai_chieu_rieng": False,
            "w_dpc": 0.00, "w_le": 1.00, "w_le_gc": 0.50, "w_nen": 7.5},
    "V":   {"vtk": 30, "so_lan": 1, "w_lan": 3.50, "hai_chieu_rieng": False,
            "w_dpc": 0.00, "w_le": 1.50, "w_le_gc": 1.00, "w_nen": 6.5},
    "VI":  {"vtk": 20, "so_lan": 1, "w_lan": 3.50, "hai_chieu_rieng": False,
            "w_dpc": 0.00, "w_le": 1.25, "w_le_gc": None, "w_nen": 6.0},
}

# ─────────────────────────────────────────────────────────────────────────────
# TCVN 5729:2012 — Bảng 1 — Chiều rộng tiêu chuẩn các yếu tố MCN đường CAO TỐC
# ─────────────────────────────────────────────────────────────────────────────
# Cấu trúc MCN (đối xứng): LềTrCỏ | LềGiaCố | XeChạy | DATdảiGiữa | DPC | DATdảiGiữa | XeChạy | LềGiaCố | LềTrCỏ
#   w_le_trong_co  : lề trồng cỏ (ngoài cùng), m
#   w_le_dat       : dải an toàn / lề gia cố (cạnh xe chạy), m
#   w_mat_duong    : mặt đường (phần xe chạy) MỖI CHIỀU cho 2 làn cơ bản, m
#                    (= n_lan_min_moi_chieu × w_lan; theo Điều 6.8 thêm 1 làn = +3.50m/3.75m)
#   w_dat_an_toan  : dải an toàn trong dải giữa MỖI BÊN, m
#   w_dpc_core     : dải phân cách lõi (không kể dải AT), m
#   w_nen          : chiều rộng nền đường toàn bộ (= 2×le_trong_co + 2×le_dat + 2×mat + 2×dat_AT + dpc_core)
#
# Độ dốc ngang (cố định theo Điều 6.3.4 & 6.4 — KHÔNG xét siêu cao):
#   Mặt đường & dải AT (lề gia cố): 2%   (dốc ra phía ngoài)
#   Lề trồng cỏ                  : 6%   (dốc ra phía ngoài)
#   Dải AT trong dải giữa         : 2%   (dốc ra phía ngoài — cùng chiều xe chạy)
# ─────────────────────────────────────────────────────────────────────────────
_B1_CAOTOC = {
    # 1) Có lớp phủ, KHÔNG bố trí trụ công trình
    "co_lop_phu_khong_tru": {
        "mo_ta": "Có lớp phủ, không bố trí trụ công trình",
        60:  {"w_le_trong_co": 0.75, "w_le_dat": 2.50, "w_mat_duong": 7.00,
               "w_dat_an_toan": 0.50, "w_dpc_core": 0.50, "w_nen": 22.00},
        80:  {"w_le_trong_co": 0.75, "w_le_dat": 2.50, "w_mat_duong": 7.00,
               "w_dat_an_toan": 0.50, "w_dpc_core": 0.50, "w_nen": 22.00},
        100: {"w_le_trong_co": 0.75, "w_le_dat": 3.00, "w_mat_duong": 7.50,
               "w_dat_an_toan": 0.75, "w_dpc_core": 0.75, "w_nen": 24.75},
        120: {"w_le_trong_co": 0.75, "w_le_dat": 3.00, "w_mat_duong": 7.50,
               "w_dat_an_toan": 0.75, "w_dpc_core": 0.75, "w_nen": 24.75},
    },
    # 2) Có lớp phủ, CÓ bố trí trụ công trình
    "co_lop_phu_co_tru": {
        "mo_ta": "Có lớp phủ, có bố trí trụ (cột) công trình",
        60:  {"w_le_trong_co": 0.75, "w_le_dat": 2.50, "w_mat_duong": 7.00,
               "w_dat_an_toan": 0.50, "w_dpc_core": 1.50, "w_nen": 23.00},
        80:  {"w_le_trong_co": 0.75, "w_le_dat": 2.50, "w_mat_duong": 7.00,
               "w_dat_an_toan": 0.50, "w_dpc_core": 1.50, "w_nen": 23.00},
        100: {"w_le_trong_co": 0.75, "w_le_dat": 3.00, "w_mat_duong": 7.50,
               "w_dat_an_toan": 0.75, "w_dpc_core": 1.50, "w_nen": 25.50},
        120: {"w_le_trong_co": 0.75, "w_le_dat": 3.00, "w_mat_duong": 7.50,
               "w_dat_an_toan": 0.75, "w_dpc_core": 1.50, "w_nen": 25.50},
    },
    # 3) Không có lớp phủ
    "khong_lop_phu": {
        "mo_ta": "Không có lớp phủ (trồng cỏ / hình chữ V)",
        60:  {"w_le_trong_co": 0.75, "w_le_dat": 2.50, "w_mat_duong": 7.00,
               "w_dat_an_toan": 0.50, "w_dpc_core": 3.00, "w_nen": 24.50},
        80:  {"w_le_trong_co": 0.75, "w_le_dat": 2.50, "w_mat_duong": 7.00,
               "w_dat_an_toan": 0.50, "w_dpc_core": 3.00, "w_nen": 24.50},
        100: {"w_le_trong_co": 0.75, "w_le_dat": 3.00, "w_mat_duong": 7.50,
               "w_dat_an_toan": 0.75, "w_dpc_core": 3.00, "w_nen": 27.00},
        120: {"w_le_trong_co": 0.75, "w_le_dat": 3.00, "w_mat_duong": 7.50,
               "w_dat_an_toan": 0.75, "w_dpc_core": 3.00, "w_nen": 27.00},
    },
}
# Thêm làn xe (Điều 6.8): mỗi làn thêm ngoài 2 làn cơ bản
_W_LAN_THEM_CT = {60: 3.50, 80: 3.50, 100: 3.75, 120: 3.75}
# Độ dốc ngang cố định TCVN 5729:2012
_I_MAT_CAOTOC       = 2.0   # % — mặt đường + dải AT
_I_LE_TRONG_CO_CT   = 6.0   # % — lề trồng cỏ


def tra_cuu_mcn_caotoc(vtk, loai_dpc="co_lop_phu_khong_tru"):
    """
    Tra cứu chiều rộng tiêu chuẩn MCN đường cao tốc theo Bảng 1 – TCVN 5729:2012.
    vtk     : 60 | 80 | 100 | 120 (km/h)
    loai_dpc: "co_lop_phu_khong_tru" | "co_lop_phu_co_tru" | "khong_lop_phu"
    Trả về dict chiều rộng TIÊU CHUẨN (không phải tối thiểu tuyệt đối) cho 2 làn/chiều.
    """
    loai = loai_dpc if loai_dpc in _B1_CAOTOC else "co_lop_phu_khong_tru"
    vtk_int = int(vtk)
    bang = _B1_CAOTOC[loai]
    if vtk_int not in bang:
        return {"status": "error",
                "message": f"TCVN 5729:2012 Bảng 1 không có Vtk={vtk}km/h "
                            f"(chỉ hỗ trợ 60, 80, 100, 120)."}
    d = bang[vtk_int]
    w_lan_min = d["w_mat_duong"] / 2   # 2 làn cơ bản mỗi chiều
    return {
        "status": "success",
        "tieu_chuan": "TCVN 5729:2012",
        "bang_ap_dung": "Bảng 1",
        "loai_dpc": loai,
        "mo_ta_dpc": bang["mo_ta"],
        "vtk": vtk_int,
        "n_lan_moi_chieu_min": 2,
        "w_lan_min": w_lan_min,
        "w_mat_duong_min": d["w_mat_duong"],
        "w_le_trong_co_min": d["w_le_trong_co"],
        "w_le_dat_min": d["w_le_dat"],
        "w_dat_an_toan_dg_min": d["w_dat_an_toan"],
        "w_dpc_core_min": d["w_dpc_core"],
        "w_nen_min": d["w_nen"],
        "w_lan_them": _W_LAN_THEM_CT[vtk_int],
        "i_mat_duong": _I_MAT_CAOTOC,
        "i_le_trong_co": _I_LE_TRONG_CO_CT,
    }


# ─────────────────────────────────────────────────────────────────────────────
# TCVN 4054:2005 — Bảng 8 — Cấu tạo tối thiểu DẢI PHÂN CÁCH GIỮA
# Áp dụng khi đường có ≥ 4 làn xe (Điều 4.4.1)
# ─────────────────────────────────────────────────────────────────────────────
_B8_DAI_PHAN_CACH = {
    "be_tong_duc_san": {
        "mo_ta": "Dải PC bê tông đúc sẵn, bó vỉa có lớp phủ, không bố trí trụ công trình",
        "w_phan_cach":      0.50,
        "w_an_toan_moi_ben": 0.50,
        "w_toi_thieu":      1.50,
    },
    "co_tru_cot": {
        "mo_ta": "Xây bó vỉa, có lớp phủ, có bố trí trụ (cột) công trình",
        "w_phan_cach":      1.50,
        "w_an_toan_moi_ben": 0.50,
        "w_toi_thieu":      2.50,
    },
    "khong_lop_phu": {
        "mo_ta": "Dải phân cách không có lớp phủ",
        "w_phan_cach":      3.00,
        "w_an_toan_moi_ben": 0.50,
        "w_toi_thieu":      4.00,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# TCVN 4054:2005 — Bảng 9 — Độ dốc ngang (%) các yếu tố trên MCN
# Phần lề không gia cố: 4.0 – 6.0% (không phụ thuộc loại mặt đường)
# ─────────────────────────────────────────────────────────────────────────────
_B9_DOC_NGANG = {
    "btxm_bthua": {
        "mo_ta": "Bê tông xi măng và bê tông nhựa",
        "i_min": 1.5, "i_max": 2.0,
    },
    "lat_da_tot": {
        "mo_ta": "Mặt đường lát đá tốt, phẳng",
        "i_min": 2.0, "i_max": 3.0,
    },
    "lat_da_tb": {
        "mo_ta": "Mặt đường lát đá chất lượng trung bình",
        "i_min": 3.0, "i_max": 3.5,
    },
    "da_dam_cap_phoi": {
        "mo_ta": "Đá dăm, cấp phối, mặt đường cấp thấp",
        "i_min": 3.0, "i_max": 3.5,
    },
}
_I_LE_KHONG_GC_MIN = 4.0   # % — phần lề không gia cố (Bảng 9, mục 2)
_I_LE_KHONG_GC_MAX = 6.0

# ─────────────────────────────────────────────────────────────────────────────
# TCVN 13592:2022 — Đường đô thị
# ─────────────────────────────────────────────────────────────────────────────
# Bảng 10: Chiều rộng 1 làn xe thông thường và số làn xe tối thiểu
_B10_DO_THI = {
    "cao_toc_do_thi": {
        "mo_ta": "Đường cao tốc đô thị",
        "w_lan": {100: 3.75, 80: 3.75, 60: 3.50},
        "so_lan_toi_thieu": 4,
        "so_lan_mong_muon": "6÷10",
    },
    "pho_chinh_chu_yeu": {
        "mo_ta": "Đường phố chính chủ yếu",
        "w_lan": {80: 3.75, 60: 3.50},
        "so_lan_toi_thieu": 4,
        "so_lan_mong_muon": "8÷12",
    },
    "pho_chinh_thu_yeu": {
        "mo_ta": "Đường phố chính thứ yếu",
        "w_lan": {60: 3.50},
        "so_lan_toi_thieu": 4,
        "so_lan_mong_muon": "6÷8",
    },
    "pho_gom": {
        "mo_ta": "Đường phố gom",
        "w_lan": {60: 3.50, 50: 3.25},
        "so_lan_toi_thieu": 2,
        "so_lan_mong_muon": "4÷6",
    },
    "pho_noi_bo": {
        "mo_ta": "Đường phố nội bộ",
        "w_lan": {50: 3.25, 40: 3.00, 30: 3.00},
        "so_lan_toi_thieu": 2,
        "so_lan_mong_muon": "2÷4",
    },
}

# Bảng 12: Độ dốc ngang phần xe chạy — đường đô thị (TCVN 13592:2022)
_B12_DOC_NGANG_DO_THI = {
    "btxm_bthua":      {"mo_ta": "Bê tông xi măng và bê tông nhựa", "i_min": 1.5, "i_max": 2.5},
    "nhua_khac":       {"mo_ta": "Các loại mặt đường nhựa khác",    "i_min": 2.0, "i_max": 3.0},
    "lat_da_tot":      {"mo_ta": "Mặt đường lát đá tốt, phẳng",     "i_min": 2.0, "i_max": 3.0},
    "da_dam_cap_phoi": {"mo_ta": "Mặt đường đá dăm, cấp phối",      "i_min": 2.5, "i_max": 3.5},
}

# Bảng 13: Chiều rộng tối thiểu lề đường và dải an toàn — đường đô thị
_B13_LE_DO_THI = {
    100: {"w_le_min": 2.50, "w_le_max": 3.00, "w_dat_at_loaiI": 1.00, "w_dat_at_loaiII_III": 0.75},
    80:  {"w_le_min": 2.50, "w_le_max": 3.00, "w_dat_at_loaiI": 0.75, "w_dat_at_loaiII_III": 0.50},
    60:  {"w_le_min": 1.50, "w_le_max": 2.50, "w_dat_at_loaiI": 0.50, "w_dat_at_loaiII_III": 0.25},
    50:  {"w_le_min": 0.75, "w_le_max": 1.00, "w_dat_at_loaiI": 0.25, "w_dat_at_loaiII_III": None},
    40:  {"w_le_min": 0.50, "w_le_max": 0.50, "w_dat_at_loaiI": None, "w_dat_at_loaiII_III": None},
    30:  {"w_le_min": 0.50, "w_le_max": 0.50, "w_dat_at_loaiI": None, "w_dat_at_loaiII_III": None},
    20:  {"w_le_min": 0.30, "w_le_max": 0.30, "w_dat_at_loaiI": None, "w_dat_at_loaiII_III": None},
}

# Bảng 14: Chiều rộng tối thiểu dải phân cách — đường đô thị (TCVN 13592:2022)
# Giá trị: tối thiểu tuyệt đối (m); (giá trị trong ngoặc = tối thiểu mong muốn về cảnh quan)
# cao_toc_do_thi: áp dụng theo TCVN 5729:2012 (None)
# pho_noi_bo   : không có dải phân cách (None)
_B14_DAI_PHAN_CACH_DO_THI = {
    "cao_toc_do_thi":    None,  # Áp dụng theo TCVN 5729:2012
    "pho_chinh_chu_yeu": {
        "I":   {"w_toi_thieu": 3.00, "w_mong_muon": 9.00},
        "II":  {"w_toi_thieu": 2.50, "w_mong_muon": 6.50},
        "III": {"w_toi_thieu": 2.00, "w_mong_muon": 4.00},
    },
    "pho_chinh_thu_yeu": {
        "I":   {"w_toi_thieu": 2.50, "w_mong_muon": 7.50},
        "II":  {"w_toi_thieu": 2.00, "w_mong_muon": 5.00},
        "III": {"w_toi_thieu": 1.50, "w_mong_muon": 3.00},
    },
    "pho_gom": {
        "I":   {"w_toi_thieu": 2.00, "w_mong_muon": 6.00},
        "II":  {"w_toi_thieu": 1.50, "w_mong_muon": 4.00},
        "III": {"w_toi_thieu": 1.00, "w_mong_muon": 2.00},
    },
    "pho_noi_bo":        None,  # Không có dải phân cách
}

# Bảng 15: Chiều rộng tối thiểu hè đường — đường đô thị (TCVN 13592:2022)
# cao_toc_do_thi: không áp dụng hè đường (None)
_B15_HE_DUONG = {
    "cao_toc_do_thi":    {"I": None, "II": None, "III": None},
    "pho_chinh_chu_yeu": {"I": 6.0,  "II": 5.0,  "III": 4.0},
    "pho_chinh_thu_yeu": {"I": 6.0,  "II": 5.0,  "III": 4.0},
    "pho_gom":           {"I": 4.5,  "II": 4.0,  "III": 3.0},
    "pho_noi_bo":        {"I": 3.0,  "II": 2.5,  "III": 2.0},
}

# Bảng 16: Kích thước tối thiểu dải trồng cây (tham khảo, không bắt buộc)
_B16_DAI_TRONG_CAY = {
    "cay_bong_mat_1_hang":     {"mo_ta": "Cây bóng mát trồng 1 hàng",     "w_min": 2.0},
    "cay_bong_mat_2_hang":     {"mo_ta": "Cây bóng mát trồng 2 hàng",     "w_min": 5.0},
    "dai_cay_bui_bai_co":      {"mo_ta": "Dải cây bụi, bãi cỏ",            "w_min": 1.0},
    "vuon_cay_nha_1_tang":     {"mo_ta": "Vườn cây trước nhà 1 tầng",     "w_min": 2.0},
    "vuon_cay_nha_nhieu_tang": {"mo_ta": "Vườn cây trước nhà nhiều tầng", "w_min": 6.0},
}


def tra_cuu_mcn_do_thi(vtk, loai_dt="pho_chinh_chu_yeu", dieu_kien_xd="II"):
    """
    Tra cứu TỐI THIỂU MCN đường đô thị theo TCVN 13592:2022 Bảng 10/13/14/15.
    vtk          : vận tốc thiết kế (km/h)
    loai_dt      : key trong _B10_DO_THI
    dieu_kien_xd : "I" | "II" | "III" (điều kiện xây dựng — ảnh hưởng Bảng 14, 15)
    """
    d = _B10_DO_THI.get(loai_dt)
    if d is None:
        return {"status": "error", "message": f"Không tìm thấy loại đường đô thị: {loai_dt}"}
    w_lan_dict = d["w_lan"]
    # Lấy w_lan theo VTK: khớp chính xác, không có thì lấy VTK hợp lệ lớn nhất ≤ vtk
    if vtk in w_lan_dict:
        w_lan_min = w_lan_dict[vtk]
    else:
        candidates = sorted([v for v in w_lan_dict if v <= vtk], reverse=True)
        if not candidates:
            candidates = sorted(w_lan_dict.keys())
        w_lan_min = w_lan_dict[candidates[0]]

    # Bảng 13: lề đường và dải an toàn (lấy VTK gần nhất)
    le_data = _B13_LE_DO_THI.get(vtk) or _B13_LE_DO_THI[
        min(_B13_LE_DO_THI.keys(), key=lambda x: abs(x - vtk))
    ]

    # Bảng 14: dải phân cách giữa
    b14 = _B14_DAI_PHAN_CACH_DO_THI.get(loai_dt)
    if b14 is None:
        dpc_min = None
        dpc_mong_muon = None
        co_dpc = False
        dpc_note = ("Áp dụng theo TCVN 5729:2012" if loai_dt == "cao_toc_do_thi"
                    else "Không có dải phân cách")
    else:
        dkx = b14.get(dieu_kien_xd, b14.get("II", {}))
        dpc_min = dkx.get("w_toi_thieu")
        dpc_mong_muon = dkx.get("w_mong_muon")
        co_dpc = True
        dpc_note = None

    # Bảng 15: hè đường
    b15 = _B15_HE_DUONG.get(loai_dt, {})
    he_min = b15.get(dieu_kien_xd)

    # Bảng 16 (tham khảo): dải trồng cây (không tra theo loại đường, chỉ lưu reference)
    trong_cay_ref = _B16_DAI_TRONG_CAY

    return {
        "status": "success",
        "tieu_chuan": "TCVN 13592:2022",
        "bang_ap_dung": "Bảng 10, 12, 13, 14, 15",
        "loai_dt": loai_dt,
        "mo_ta": d["mo_ta"],
        "vtk": vtk,
        "dieu_kien_xd": dieu_kien_xd,
        # Bảng 10
        "w_lan_min": w_lan_min,
        "so_lan_toi_thieu": d["so_lan_toi_thieu"],
        "so_lan_mong_muon": d["so_lan_mong_muon"],
        # Bảng 13
        "w_le_min": le_data["w_le_min"],
        "w_le_max": le_data["w_le_max"],
        "w_dat_at_loaiI": le_data["w_dat_at_loaiI"],
        "w_dat_at_loaiII_III": le_data["w_dat_at_loaiII_III"],
        # Bảng 14
        "co_dpc": co_dpc,
        "dpc_min": dpc_min,
        "dpc_mong_muon": dpc_mong_muon,
        "dpc_note": dpc_note,
        # Bảng 15
        "he_min": he_min,
        # Bảng 16 (tham khảo)
        "trong_cay_ref": {k: v["w_min"] for k, v in trong_cay_ref.items()},
    }


def tra_cuu_doc_ngang_do_thi(loai_mat="btxm_bthua"):
    """
    Tra cứu độ dốc ngang phần xe chạy theo Bảng 12 – TCVN 13592:2022.
    loai_mat: "btxm_bthua" | "nhua_khac" | "lat_da_tot" | "da_dam_cap_phoi"
    """
    d = _B12_DOC_NGANG_DO_THI.get(loai_mat, _B12_DOC_NGANG_DO_THI["btxm_bthua"])
    return {
        "loai_mat": loai_mat,
        "mo_ta": d["mo_ta"],
        "i_min": d["i_min"],
        "i_max": d["i_max"],
        "i_goi_y": round((d["i_min"] + d["i_max"]) / 2, 2),
    }


def tra_cuu_dai_phan_cach(loai_dpc="be_tong_duc_san"):
    """
    Tra cứu chiều rộng tối thiểu dải phân cách giữa theo Bảng 8 – TCVN 4054:2005.
    loai_dpc: "be_tong_duc_san" | "co_tru_cot" | "khong_lop_phu"
    """
    d = _B8_DAI_PHAN_CACH.get(loai_dpc)
    if d is None:
        d = _B8_DAI_PHAN_CACH["be_tong_duc_san"]
    return {"loai_dpc": loai_dpc, **d}


def tra_cuu_doc_ngang(loai_mat="btxm_bthua"):
    """
    Tra cứu độ dốc ngang mặt đường và lề gia cố theo Bảng 9 – TCVN 4054:2005.
    loai_mat: "btxm_bthua" | "lat_da_tot" | "lat_da_tb" | "da_dam_cap_phoi"
    Trả về dict gồm i_min, i_max (%), i_goi_y (trung bình), i_le_khong_gc_min/max.
    """
    d = _B9_DOC_NGANG.get(loai_mat, _B9_DOC_NGANG["btxm_bthua"])
    return {
        "loai_mat": loai_mat,
        "mo_ta": d["mo_ta"],
        "i_min": d["i_min"],
        "i_max": d["i_max"],
        "i_goi_y": round((d["i_min"] + d["i_max"]) / 2, 2),
        "i_le_khong_gc_min": _I_LE_KHONG_GC_MIN,
        "i_le_khong_gc_max": _I_LE_KHONG_GC_MAX,
    }


def tra_cuu_mcn_oto(cap_duong, dia_hinh="dong_bang"):
    """
    Tra cứu chiều rộng TỐI THIỂU các yếu tố trên MCN đường Ô TÔ theo TCVN 4054:2005.

    cap_duong : "I" | "II" | "III" | "IV" | "V" | "VI"
    dia_hinh  : "dong_bang" (Bảng 6 — đồng bằng và đồi) | "nui" (Bảng 7 — vùng núi)

    Trả về dict các giá trị TỐI THIỂU (m) — KHÔNG phải giá trị thiết kế cuối cùng.
    Người dùng phải tự nhập giá trị thiết kế (>= các giá trị tối thiểu này).
    """
    cap = str(cap_duong).upper().strip()
    if dia_hinh == "nui":
        bang, ten_bang = _B7_VUNGNUI, "Bảng 7 (vùng núi)"
    else:
        bang, ten_bang = _B6_DONGBANG_DOI, "Bảng 6 (đồng bằng và đồi)"

    if cap not in bang:
        return {
            "status": "error",
            "message": f"Cấp {cap} không có trong {ten_bang} của TCVN 4054:2005 "
                       f"(Bảng 7 chỉ áp dụng cấp III–VI)."
        }

    d = bang[cap]
    w_xe_chay_min = d["so_lan"] * d["w_lan"]
    return {
        "status": "success",
        "tieu_chuan": "TCVN 4054:2005",
        "bang_ap_dung": ten_bang,
        "cap_duong": cap,
        "v_thiet_ke": d["vtk"],
        "so_lan_min": d["so_lan"],
        "w_lan_min": d["w_lan"],
        "hai_chieu_rieng": d["hai_chieu_rieng"],
        "w_xe_chay_min": round(w_xe_chay_min, 2),
        "w_dpc_min": d["w_dpc"],
        "w_le_min": d["w_le"],
        "w_le_gc_min": d["w_le_gc"],
        "w_nen_duong_min": d["w_nen"],
    }


def thiet_ke_mcn_cau_web(data):
    """
    Hàm xử lý logic thiết kế mặt cắt ngang trả về Dictionary cho Web.
    (Gộp từ module 03-MatCatNgang.py)

    data:
      loai      : "O to" | "Cao tốc" | "Do thi"
      vtk       : vận tốc thiết kế (km/h) — dùng cho "Cao tốc" / "Do thi"
      cap_duong : cấp đường ("I".."VI") — dùng cho "O to" (TCVN 4054:2005)
      dia_hinh  : "dong_bang" | "nui" — dùng cho "O to"

      Các khóa GHI ĐÈ (override) do người dùng tự nhập — chỉ áp dụng cho "O to",
      nếu không truyền sẽ tự lấy giá trị tối thiểu theo tra_cuu_mcn_oto():
        so_lan, w_lan, w_le, w_dpc, w_le_gc   (đơn vị: làn / m)
        loai_dpc      : loại dải phân cách ("be_tong_duc_san"|"co_tru_cot"|"khong_lop_phu")
        loai_mat_duong: loại mặt đường ("btxm_bthua"|"lat_da_tot"|"lat_da_tb"|"da_dam_cap_phoi")
        i_doc_ngang   : độ dốc ngang mặt đường do người dùng nhập (%)
    """
    loai = data.get("loai")
    vtk  = data.get("vtk")

    # ── Giá trị mặc định ────────────────────────────────────────────────────
    w_lan = 3.5;  n_lan = 2;  w_le = 0.5;  w_le_gc = None;  w_dpc = 0.0
    w_lc  = 0.5;  tieu_chuan = "—";  w_xe_chay_min = w_nen_duong_min = None
    hai_chieu_rieng = False;  tra_loi = None
    # Cao tốc extras (0/False khi không phải cao tốc)
    is_caotoc        = False
    n_lan_moi_chieu  = 1
    w_mat_1chieu     = 0.0
    w_le_trong_co    = 0.0
    w_dat_an_toan_dg = 0.0
    w_dpc_core       = 0.0

    if loai == "O to":
        cap_duong = data.get("cap_duong", "IV")
        dia_hinh  = data.get("dia_hinh", "dong_bang")
        tra_loi = tra_cuu_mcn_oto(cap_duong, dia_hinh)
        if tra_loi.get("status") == "success":
            tieu_chuan      = f"{tra_loi['tieu_chuan']} – {tra_loi['bang_ap_dung']}"
            n_lan           = data.get("so_lan", tra_loi["so_lan_min"])
            w_lan           = data.get("w_lan",  tra_loi["w_lan_min"])
            w_le            = data.get("w_le",   tra_loi["w_le_min"])
            w_dpc           = data.get("w_dpc",  tra_loi["w_dpc_min"])
            w_le_gc         = data.get("w_le_gc", tra_loi["w_le_gc_min"])
            hai_chieu_rieng = tra_loi["hai_chieu_rieng"]
            w_xe_chay_min   = tra_loi["w_xe_chay_min"]
            w_nen_duong_min = tra_loi["w_nen_duong_min"]
            n_lan_moi_chieu = n_lan // 2

    elif loai == "Cao tốc":
        is_caotoc   = True
        loai_dpc_ct = data.get("loai_dpc_ct", "co_lop_phu_khong_tru")
        tra_loi     = tra_cuu_mcn_caotoc(vtk or 100, loai_dpc_ct)
        if tra_loi.get("status") == "success":
            tieu_chuan       = f"{tra_loi['tieu_chuan']} – {tra_loi['bang_ap_dung']}"
            n_lan_moi_chieu  = max(int(data.get("n_lan_moi_chieu", tra_loi["n_lan_moi_chieu_min"])),
                                   tra_loi["n_lan_moi_chieu_min"])
            n_lan            = n_lan_moi_chieu * 2
            w_lan            = float(data.get("w_lan", tra_loi["w_lan_min"]))
            w_mat_1chieu     = n_lan_moi_chieu * w_lan
            w_le_dat         = float(data.get("w_le_dat",        tra_loi["w_le_dat_min"]))
            w_le_trong_co    = float(data.get("w_le_trong_co",   tra_loi["w_le_trong_co_min"]))
            w_dat_an_toan_dg = float(data.get("w_dat_an_toan_dg",tra_loi["w_dat_an_toan_dg_min"]))
            w_dpc_core       = float(data.get("w_dpc_core",      tra_loi["w_dpc_core_min"]))
            w_le_gc          = w_le_dat
            w_le             = w_le_dat + w_le_trong_co
            w_dpc            = 2 * w_dat_an_toan_dg + w_dpc_core
            hai_chieu_rieng  = True
            w_xe_chay_min    = tra_loi["w_mat_duong_min"] * 2
            w_nen_duong_min  = tra_loi["w_nen_min"]
            tra_loi["n_lan_min"] = tra_loi["n_lan_moi_chieu_min"] * 2
        else:
            # fallback
            n_lan = 4; n_lan_moi_chieu = 2; w_lan = 3.75
            w_le_gc = 3.0; w_le_trong_co = 0.75; w_le = 3.75
            w_dat_an_toan_dg = 0.75; w_dpc_core = 0.75; w_dpc = 2.25
            w_mat_1chieu = 7.50; hai_chieu_rieng = True

    elif loai == "Do thi":
        loai_dt_key  = data.get("loai_dt", "pho_chinh_chu_yeu")
        dieu_kien_xd = data.get("dieu_kien_xd", "II")
        tra_loi = tra_cuu_mcn_do_thi(vtk or 60, loai_dt_key, dieu_kien_xd)
        if tra_loi.get("status") == "success":
            tieu_chuan      = f"{tra_loi['tieu_chuan']} – {tra_loi['bang_ap_dung']}"
            n_lan           = int(data.get("so_lan", tra_loi["so_lan_toi_thieu"]))
            w_lan           = float(data.get("w_lan", tra_loi["w_lan_min"]))
            w_le            = float(data.get("w_le",  tra_loi["w_le_min"]))
            _dpc_default    = tra_loi["dpc_min"] or 0.0
            w_dpc           = float(data.get("w_dpc", _dpc_default))
            w_le_gc         = float(data.get("w_le_gc") or 0.0)
            _he_default     = tra_loi["he_min"] or 0.0
            w_lc            = float(data.get("w_he", _he_default))   # hè đường → w_lc slot
            n_lan_moi_chieu = n_lan // 2
            hai_chieu_rieng = (n_lan >= 4 and w_dpc > 0)

    # ── Dải phân cách Bảng 8 (chỉ cho O to) / không áp dụng cho Cao tốc và Đô thị ──
    if loai == "O to":
        _loai_dpc_key = data.get("loai_dpc", "be_tong_duc_san")
        dpc_b8        = tra_cuu_dai_phan_cach(_loai_dpc_key)
        w_dpc_min_b8  = dpc_b8["w_toi_thieu"] if w_dpc > 0 else 0.0
    else:
        _loai_dpc_key = ""
        dpc_b8        = {}
        w_dpc_min_b8  = 0.0

    # ── Độ dốc ngang: Bảng 9 cho O to, cố định TCVN 5729 cho Cao tốc, Bảng 12 cho Đô thị ──
    if loai == "Cao tốc":
        loai_mat      = "btxm_bthua"
        doc_ngang     = {"mo_ta": "BT nhựa (TCVN 5729:2012 — cố định)",
                         "i_min": 2.0, "i_max": 2.0, "i_goi_y": 2.0,
                         "i_le_khong_gc_min": 6.0, "i_le_khong_gc_max": 6.0}
        i_doc_ngang   = _I_MAT_CAOTOC      # 2.0%
        i_le_trong_co = _I_LE_TRONG_CO_CT  # 6.0%
        i_trong_pham_vi = True
    elif loai == "Do thi":
        loai_mat    = data.get("loai_mat_duong", "btxm_bthua")
        doc_ngang   = tra_cuu_doc_ngang_do_thi(loai_mat)
        i_doc_ngang = float(data.get("i_doc_ngang", doc_ngang["i_goi_y"]))
        i_le_trong_co = 0.0
        i_trong_pham_vi = doc_ngang["i_min"] <= i_doc_ngang <= doc_ngang["i_max"]
    else:
        loai_mat    = data.get("loai_mat_duong", "btxm_bthua")
        doc_ngang   = tra_cuu_doc_ngang(loai_mat)
        i_doc_ngang = float(data.get("i_doc_ngang", doc_ngang["i_goi_y"]))
        i_le_trong_co = 0.0
        i_trong_pham_vi = doc_ngang["i_min"] <= i_doc_ngang <= doc_ngang["i_max"]

    # ── Tính toán tổng ───────────────────────────────────────────────────────
    w_mat_tong    = n_lan * w_lan
    bc_thong_thuy = w_mat_tong + (2 * w_le) + w_dpc
    bc_cau        = bc_thong_thuy + (2 * w_lc)

    if loai == "Cao tốc":
        mo_phong = (
            f"LềTC {w_le_trong_co}m | DAT {w_le_gc}m | "
            f"{n_lan_moi_chieu:g}LÀN×{w_lan}m | DAT {w_dat_an_toan_dg}m | "
            f"DPC {w_dpc_core}m | DAT {w_dat_an_toan_dg}m | "
            f"{n_lan_moi_chieu:g}LÀN×{w_lan}m | DAT {w_le_gc}m | LềTC {w_le_trong_co}m"
        )
    elif w_dpc > 0:
        _nlh = n_lan / 2
        mo_phong = (
            f"LC {w_lc}m | LỀ {w_le}m | {_nlh:g} LÀN x {w_lan}m | "
            f"DPC {w_dpc}m | {_nlh:g} LÀN x {w_lan}m | LỀ {w_le}m | LC {w_lc}m"
        )
    else:
        mo_phong = f"LC {w_lc}m | LỀ {w_le}m | {n_lan:g} LÀN x {w_lan}m | LỀ {w_le}m | LC {w_lc}m"

    return {
        "loai": loai,
        "tieu_chuan": tieu_chuan,
        "n_lan": n_lan,
        "w_lan": w_lan,
        "w_mat_tong": round(w_mat_tong, 2),
        "w_le": w_le,
        "w_le_gc": w_le_gc,
        "w_dpc": w_dpc,
        "w_lc": w_lc,
        "hai_chieu_rieng": hai_chieu_rieng,
        "w_xe_chay_min": w_xe_chay_min,
        "w_nen_duong_min": w_nen_duong_min,
        "tra_cuu_toi_thieu": tra_loi,
        # Cao tốc extras
        "is_caotoc": is_caotoc,
        "is_dothi":  (loai == "Do thi"),
        "w_he": w_lc if (loai == "Do thi") else 0.0,
        "n_lan_moi_chieu": n_lan_moi_chieu,
        "w_mat_1chieu": round(w_mat_1chieu, 2),
        "w_le_trong_co": w_le_trong_co,
        "w_dat_an_toan_dg": w_dat_an_toan_dg,
        "w_dpc_core": w_dpc_core,
        # Bảng 8 (O to)
        "loai_dpc": _loai_dpc_key,
        "dpc_b8": dpc_b8,
        "w_dpc_min_b8": w_dpc_min_b8,
        # Độ dốc ngang
        "loai_mat_duong": loai_mat,
        "doc_ngang_b9": doc_ngang,
        "i_doc_ngang": round(i_doc_ngang, 2),
        "i_le_trong_co": i_le_trong_co,
        "i_doc_ngang_trong_pham_vi": i_trong_pham_vi,
        "bc_cau": round(bc_cau, 2),
        "mo_phong": mo_phong,
    }


def get_vtk_goi_y_dothi(loai_dt, cap_dt):
    data_b6 = {
        "Trục chính đô thị": {"Đặc biệt": [100, 120], "Cấp I": [80, 100], "Cấp II": [60, 80]},
        "Đường chính đô thị": {"Cấp I": [60, 80], "Cấp II": [50, 60]},
        "Đường khu vực": {"Cấp I": [50, 60], "Cấp II": [40, 50]},
        "Đường nội bộ": {"Cấp I": [30, 40], "Cấp II": [20, 30]}
    }
    return data_b6.get(loai_dt, {}).get(cap_dt, [60])
def tra_cuu_yeu_to_hinh_hoc(loai, cap_duong, dia_hinh="1"):
    if loai == "O to":
        map_vtk = {
            "I": {"1": 120, "2": 80}, "II": {"1": 100, "2": 60}, "III": {"1": 80, "2": 60},
            "IV": {"1": 60, "2": 40}, "V": {"1": 40, "2": 30}, "VI": {"1": 30, "2": 20}
        }
        map_imax = {120: 4, 100: 5, 80: 6, 60: 7, 40: 9, 30: 10, 20: 12}
        map_R_loi = {
            120: [11000, 17000], 100: [6000, 10000], 80: [4000, 5000],
            60: [2500, 4000], 40: [700, 1000], 30: [400, 600], 20: [150, 250]
        }
        try:
            vtk = map_vtk[cap_duong][str(dia_hinh)]
            return {
                "status": "success", "loai_duong": "Đường Ô tô", "tieu_chuan": "TCVN 4054:2005",
                "v_thiet_ke": vtk, "imax": map_imax[vtk], "R_loi_gh": map_R_loi[vtk][0], "R_loi_tt": map_R_loi[vtk][1]
            }
        except: return {"status": "error", "message": "Lỗi tra cứu Đường Ô tô"}

    elif loai == "Cao tốc":
        try:
            vtk = int(cap_duong)
            data_ct = {
                120: {"imax": 4, "R": [15000, 25000]}, 100: {"imax": 5, "R": [10000, 15000]},
                80: {"imax": 6, "R": [4500, 7000]}, 60: {"imax": 7, "R": [2500, 4000]}
            }
            res = data_ct[vtk]
            return {
                "status": "success", "loai_duong": "Đường Cao tốc", "tieu_chuan": "TCVN 5729:2012",
                "v_thiet_ke": vtk, "imax": res["imax"], "R_loi_gh": res["R"][0], "R_loi_tt": res["R"][1]
            }
        except: return {"status": "error", "message": "Vtk Cao tốc phải là 120, 100, 80 hoặc 60"}

    elif loai == "Do thi":
        try:
            vtk = int(cap_duong)
            data_dt = {
                120: {"imax": 4, "R": [11000, 17000]}, 100: {"imax": 4, "R": [6500, 10000]},
                80: {"imax": 5, "R": [3000, 4500]}, 60: {"imax": 6, "R": [1400, 2000]},
                50: {"imax": 6, "R": [800, 1200]}, 40: {"imax": 7, "R": [450, 700]},
                30: {"imax": 8, "R": [250, 400]}, 20: {"imax": 9, "R": [120, 200]}
            }
            res = data_dt[vtk]
            return {
                "status": "success", "loai_duong": "Đường Đô thị", "tieu_chuan": "TCVN 13592:2022",
                "v_thiet_ke": vtk, "imax": res["imax"], "R_loi_gh": res["R"][0], "R_loi_tt": res["R"][1]
            }
        except: return {"status": "error", "message": "Vtk Đô thị không hợp lệ"}
    return {"status": "error", "message": "Loại đường không xác định"}
def tinh_toan_geo_logic(res, h_tn_tb, h_dam, h_dap_yc=6.0, x_tim_clearance=0.0,
                         lt_diahinh=None, z_diahinh=None):
    """
    Tính toán hình học trắc dọc với tim tĩnh không tại lý trình x_tim_clearance (m).
    Trả về các giá trị trong hệ tọa độ thực tế (lý trình).
    Phạm vi đề tài: cầu vượt sông/kênh → cao độ gốc lấy theo MNTT (H5%).

    lt_diahinh, z_diahinh : mảng lý trình / cao độ Z thực đo (tùy chọn). Khi được
        cung cấp, cao độ tự nhiên dùng để so sánh chiều cao đắp tại MỖI vị trí quét
        sẽ lấy theo NỘI SUY TỪ DỮ LIỆU THỰC ĐO tại đúng lý trình đó — không dùng
        cao độ trung bình h_tn_tb — để phản ánh đúng trường hợp lòng sông sâu hơn
        hai bên bờ (nếu dùng giá trị trung bình, vị trí điểm đầu/cuối — và do đó
        cao độ đặt mố/trụ — sẽ bị lệch). Nếu không có dữ liệu thực đo (hoặc lý
        trình quét nằm ngoài phạm vi khảo sát), tự động dùng h_tn_tb làm dự phòng.

    Lưu ý quan trọng: x_mo_trai / x_mo_phai trong dict trả về KHÔNG phải là vị trí
    mố thật, mà là điểm đầu / điểm cuối DỰ KIẾN của cầu — dùng để ước lượng chiều
    dài cầu (L_cau). Hai điểm này được quét ĐỘC LẬP (không lấy đối xứng qua tim
    tĩnh không), mỗi điểm phải thỏa đồng thời 2 điều kiện:
      - Điều kiện 1: quét địa hình 2000 điểm, tìm vị trí có chiều cao đắp
        (đường đỏ − cao độ địa hình THỰC tại điểm đó) gần với h_dap_yc nhất.
      - Điều kiện 2: tại vị trí đó, cao độ đường đỏ offset xuống 2.0m không được
        thấp hơn cao độ MNCN (H1%) + 0.25m (đảm bảo nền đường đầu cầu không ngập lũ).
    """
    R = res.get('R_hinh_hoc', 5000)
    i_val = res.get('i_max_hinh_hoc', 4.0) / 100

    y_base_goc = res.get('MNTT', 0)
    h1_mncn = res.get('MNCN', 0)

    y_dinh_tuyet_doi = h_dam + 2.0
    y_dinh = y_dinh_tuyet_doi - y_base_goc

    # Tính trong hệ tương đối (tim cầu tại 0)
    T = R * i_val
    x_t1_rel = -T
    x_t2_rel = T
    y_t_rel = y_dinh - (T**2) / (2 * R)

    # Ước lượng chiều dài cầu tối thiểu
    l_nhip_du_kien = res.get('ai_result', {}).get('chieu_dai', 33.0)
    l_cau_min = l_nhip_du_kien + 10.0

    # Quét địa hình 2000 điểm dọc tuyến (±500m quanh tim tĩnh không)
    x_scan_rel = np.linspace(-500, 500, 2000)
    x_scan_abs = x_scan_rel + x_tim_clearance  # lý trình thực tế của từng điểm quét

    co_diahinh_thuc = (
        lt_diahinh is not None and z_diahinh is not None and len(lt_diahinh) > 1
    )
    if co_diahinh_thuc:
        lt_arr = np.asarray(lt_diahinh, dtype=float)
        z_arr = np.asarray(z_diahinh, dtype=float)
        lt_min, lt_max = lt_arr.min(), lt_arr.max()
        # Nội suy cao độ THỰC tại từng điểm quét; điểm ngoài phạm vi khảo sát
        # (không có số liệu) mới dùng h_tn_tb làm dự phòng.
        z_thuc_abs = np.interp(x_scan_abs, lt_arr, z_arr)
        ngoai_pham_vi = (x_scan_abs < lt_min) | (x_scan_abs > lt_max)
        z_thuc_abs[ngoai_pham_vi] = h_tn_tb
        h_tn_tai_diem_tuong_doi = z_thuc_abs - y_base_goc
    else:
        # Không có dữ liệu khảo sát → dùng cao độ trung bình cho toàn tuyến (dự phòng)
        h_tn_tai_diem_tuong_doi = np.full_like(x_scan_rel, h_tn_tb - y_base_goc)

    y_scan_rel = []
    for xi in x_scan_rel:
        if xi < x_t1_rel:
            yi = y_t_rel - i_val * (x_t1_rel - xi)
        elif xi > x_t2_rel:
            yi = y_t_rel - i_val * (xi - x_t2_rel)
        else:
            yi = y_dinh - xi**2 / (2 * R)
        y_scan_rel.append(yi)
    y_scan_rel = np.array(y_scan_rel)

    # Điều kiện 1: chiều cao đắp (đường đỏ − địa hình THỰC tại điểm đó) so với h_dap_yc
    delta_y = y_scan_rel - h_tn_tai_diem_tuong_doi

    # Điều kiện 2 (quy về hệ tương đối): đường đỏ − 2.0m ≥ MNCN + 0.25m
    #   y_scan_rel + y_base_goc − 2.0 ≥ h1_mncn + 0.25
    #   ⇔ y_scan_rel ≥ h1_mncn + 0.25 + 2.0 − y_base_goc
    nguong_dk2_rel = h1_mncn + 0.25 + 2.0 - y_base_goc
    dat_dk2 = y_scan_rel >= nguong_dk2_rel

    def _tim_diem(mask_phia):
        """Tìm điểm (tương đối), trong phạm vi mask_phia, thỏa đồng thời ĐK2 (nếu có
        thể) và gần ĐK1 (chiều cao đắp ≈ h_dap_yc) nhất."""
        idx_phia = np.where(mask_phia)[0]
        idx_an_toan = idx_phia[dat_dk2[idx_phia]]
        idx_xet = idx_an_toan if len(idx_an_toan) > 0 else idx_phia
        idx_chon = idx_xet[np.argmin(np.abs(delta_y[idx_xet] - h_dap_yc))]
        return idx_chon

    # Điểm đầu (bên trái tim tĩnh không) và điểm cuối (bên phải) — quét độc lập
    idx_dau = _tim_diem(x_scan_rel < 0)
    idx_cuoi = _tim_diem(x_scan_rel > 0)
    x_dau_rel = x_scan_rel[idx_dau]
    x_cuoi_rel = x_scan_rel[idx_cuoi]
    # Cao độ địa hình thực (tương đối) ngay tại điểm đầu/cuối đã chọn
    y_dau_tuong_doi = h_tn_tai_diem_tuong_doi[idx_dau]
    y_cuoi_tuong_doi = h_tn_tai_diem_tuong_doi[idx_cuoi]

    # Khống chế chiều dài tối thiểu
    x_dau_rel = min(x_dau_rel, -l_cau_min / 2)
    x_cuoi_rel = max(x_cuoi_rel, l_cau_min / 2)

    # Chuyển sang hệ tọa độ thực tế bằng cách cộng với x_tim_clearance
    offset = x_tim_clearance
    x_t1 = x_t1_rel + offset
    x_t2 = x_t2_rel + offset
    x_diem_dau = x_dau_rel + offset
    x_diem_cuoi = x_cuoi_rel + offset
    l_cau_final = x_diem_cuoi - x_diem_dau

    return {
        "x_t1": x_t1,
        "x_t2": x_t2,
        "y_t": y_t_rel,
        "y_dinh": y_dinh,
        "R": R,
        "i_val": i_val,
        "x_mo_trai": x_diem_dau,        # điểm đầu dự kiến của cầu (không phải vị trí mố thật)
        "x_mo_phai": x_diem_cuoi,       # điểm cuối dự kiến của cầu (không phải vị trí mố thật)
        "y_mo": y_dau_tuong_doi,        # giữ để tương thích ngược (= cao độ tại điểm đầu)
        "y_mo_trai": y_dau_tuong_doi,   # cao độ địa hình THỰC tại điểm đầu
        "y_mo_phai": y_cuoi_tuong_doi,  # cao độ địa hình THỰC tại điểm cuối
        "L_cau": l_cau_final,
        "h_tn_tb": h_tn_tb,
        "co_diahinh_thuc": co_diahinh_thuc,
        "y_base_goc": y_base_goc,
        "x_tim_clearance": x_tim_clearance
    }