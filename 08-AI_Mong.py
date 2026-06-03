"""
Module 08 — Móng cầu (Foundation Advisor)
Spec: Bridge_Features_Dataset.xlsx → Sheet 05_Móng
Data: Chưa có bộ dữ liệu huấn luyện riêng — dùng quy tắc kỹ thuật theo TCVN.

Logic dựa trên:
  - TCVN 10304:2014  Móng cọc — tiêu chuẩn thiết kế
  - TCVN 11823-2017  Thiết kế cầu đường bộ — phần chung
  - Kinh nghiệm thực tế các dự án cầu VN
"""

# ---------------------------------------------------------------------------
# BẢNG TRA CỨU ĐƯỜNG KÍNH CỌC GỢI Ý
# ---------------------------------------------------------------------------
#  Dựa trên chiều cao trụ + cấp sông (tải trọng lớn → cọc lớn hơn)

_D_COC_TABLE = {
    # (H_tru <= 4, H_tru <= 8, H_tru > 8) → đường kính (mm)
    "sông_lớn":  (800,  1000, 1200),   # Cấp I, II
    "sông_vừa":  (600,  800,  1000),   # Cấp III, IV
    "sông_nhỏ":  (500,  600,  800),    # Cấp V, VI
    "đường_bộ":  (400,  600,  800),    # Vượt đường bộ / đô thị
}

_L_COC_TABLE = {
    # D_coc (mm) → chiều dài cọc gợi ý (m)  — căn cứ địa chất TB vùng ĐBSCL/Đông Nam Bộ
    400:  (25, 30),
    500:  (30, 40),
    600:  (35, 45),
    800:  (40, 55),
    1000: (45, 60),
    1200: (50, 65),
    1500: (55, 70),
}

_SO_COC_TABLE = {
    # D_coc (mm) → số cọc gợi ý (từ, đến)
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


def _chon_loai_song(cap_song_int, is_river):
    if not is_river:
        return "đường_bộ"
    if cap_song_int <= 2:
        return "sông_lớn"
    elif cap_song_int <= 4:
        return "sông_vừa"
    return "sông_nhỏ"


def _chon_D_coc(loai_song, H_tru):
    row = _D_COC_TABLE[loai_song]
    if H_tru <= 4:
        return row[0]
    elif H_tru <= 8:
        return row[1]
    return row[2]


# ---------------------------------------------------------------------------
# HÀM CHÍNH
# ---------------------------------------------------------------------------
def predict_foundation(H_tru, loai_tru, is_river, cap_song,
                       B_cau=None, vtk=None, L_nhip=None):
    """
    Gợi ý loại móng và thông số cọc.

    Params
    ------
    H_tru     : Chiều cao thân trụ (m)
    loai_tru  : Loại trụ đã xác định ('Khung 2 cột', 'Trụ đặc', ...)
    is_river  : 1 nếu vượt sông
    cap_song  : Cấp sông ('I'–'VI' hoặc '1'–'6')
    B_cau     : Bề rộng cầu (m)  — dùng để ước tính tải
    vtk       : Vận tốc thiết kế (km/h)
    L_nhip    : Chiều dài nhịp (m)

    Returns
    -------
    dict với các trường:
        loai_mong, D_coc_mm, D_coc_chon_txt,
        L_coc_tu, L_coc_den, So_coc_tu, So_coc_den,
        phuong_phap_thi_cong, ghi_chu_mong, khuyen_nghi
    """
    cap_int  = _cap_song_to_int(cap_song) if cap_song else 4
    loai_song = _chon_loai_song(cap_int, bool(is_river))

    H = float(H_tru) if H_tru else 5.0
    D_coc = _chon_D_coc(loai_song, H)

    # Quyết định loại móng
    if D_coc >= 800:
        loai_mong = "Cọc khoan nhồi"
        pp_thi_cong = "Khoan nhồi bùn khoan (bentonite) hoặc vách chống ống vách"
    elif D_coc >= 500:
        if is_river and cap_int <= 3:
            loai_mong = "Cọc khoan nhồi"
            pp_thi_cong = "Khoan nhồi bùn khoan"
        else:
            loai_mong = "Cọc đóng BTCT DƯL"
            pp_thi_cong = "Đóng búa diesel hoặc búa rung"
    else:
        loai_mong = "Cọc ép BTCT"
        pp_thi_cong = "Ép tĩnh (ép neo hoặc ép robot)"

    # Chiều dài và số cọc
    L_range = _L_COC_TABLE.get(D_coc, (40, 55))
    N_range = _SO_COC_TABLE.get(D_coc, (4, 9))

    # Điều chỉnh theo H_tru cao
    if H > 10:
        L_range = (L_range[1], L_range[1] + 10)
        N_range = (N_range[0] + 2, N_range[1] + 2)

    # Gợi ý kích thước bệ cọc
    D_m = D_coc / 1000.0
    if N_range[0] <= 4:
        be_goi_y = f"{round(D_m*2+0.5+2*0.5,1)} × {round(D_m*2+0.5+2*0.5,1)} × {round(1.5+D_m,1)} m"
    else:
        be_goi_y = f"≥ {round((D_coc/1000)*3+1.0, 1)} m (dài) × B_cầu theo dọc cầu"

    # Kiểm tra điều kiện đặc biệt
    khuyen_nghi = []
    if is_river and cap_int <= 2:
        khuyen_nghi.append("Kiểm tra xói lở theo TCVN 9845:2013; bảo vệ cọc bằng thảm đá/kè đá.")
    if H > 8:
        khuyen_nghi.append("Trụ cao — cần phân tích ổn định ngang (moment lật, áp lực nước).")
    if not khuyen_nghi:
        khuyen_nghi.append("Kiểm tra sức chịu tải cọc theo TCVN 10304:2014 trước khi quyết định.")

    ghi_chu = (
        f"Quy tắc kỹ thuật dựa TCVN 10304:2014 & kinh nghiệm VN. "
        f"Cấp sông {['I','II','III','IV','V','VI'][cap_int-1] if 1<=cap_int<=6 else cap_int}, "
        f"H_trụ={H:.1f}m, loại sông={loai_song}."
    )

    return {
        "loai_mong":          loai_mong,
        "D_coc_mm":           D_coc,
        "D_coc_chon_txt":     f"Ø{D_coc} mm",
        "L_coc_tu":           L_range[0],
        "L_coc_den":          L_range[1],
        "So_coc_tu":          N_range[0],
        "So_coc_den":         N_range[1],
        "kich_thuoc_be_goi_y": be_goi_y,
        "phuong_phap_thi_cong": pp_thi_cong,
        "ghi_chu_mong":       ghi_chu,
        "khuyen_nghi":        khuyen_nghi,
    }


# ---------------------------------------------------------------------------
# TIỆN ÍCH: format kết quả thành text thuyết minh
# ---------------------------------------------------------------------------
def format_mong_report(res_mong):
    """Trả về chuỗi text tóm tắt kết quả móng."""
    lines = [
        f"  Loại móng     : {res_mong['loai_mong']}",
        f"  Đường kính cọc: {res_mong['D_coc_chon_txt']}",
        f"  Chiều dài cọc : {res_mong['L_coc_tu']} – {res_mong['L_coc_den']} m (gợi ý)",
        f"  Số cọc/bệ     : {res_mong['So_coc_tu']} – {res_mong['So_coc_den']} cọc",
        f"  Bệ cọc (gợi ý): {res_mong['kich_thuoc_be_goi_y']}",
        f"  Thi công      : {res_mong['phuong_phap_thi_cong']}",
    ]
    for kn in res_mong["khuyen_nghi"]:
        lines.append(f"  ⚠ {kn}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CHẠY THỬ ĐỘC LẬP
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    test_cases = [
        {"H_tru": 5.08, "loai_tru": "Khung 2 cột", "is_river": 1, "cap_song": "VI", "B_cau": 17.5},
        {"H_tru": 8.5,  "loai_tru": "Thân rỗng",   "is_river": 1, "cap_song": "II", "B_cau": 20.0},
        {"H_tru": 3.0,  "loai_tru": "Trụ đặc",     "is_river": 0, "cap_song": "",   "B_cau": 12.0},
    ]

    for tc in test_cases:
        res = predict_foundation(**tc)
        print(f"\n=== H_tru={tc['H_tru']}m | Cấp sông={tc['cap_song']} ===")
        print(format_mong_report(res))
