def tra_cuu_yeu_to_hinh_hoc(loai, vtk, dia_hinh="1"):
    """
    Hàm tra cứu các chỉ tiêu kỹ thuật dựa trên TCVN.
    loai: "O to", "Cao tốc", "Do thi"
    vtk: Tốc độ thiết kế (số nguyên hoặc số thực)
    dia_hinh: "1" (Đồng bằng), "2" (Miền núi)
    """
    
    # 1. Dữ liệu tra cứu cho Đường Ô tô (TCVN 4054:2005)
    db_oto = {
        120: {"R": [11000, 17000], "imax": 4, "cap": "I"},
        100: {"R": [6000, 10000],  "imax": 5, "cap": "II"},
        80:  {"R": [4000, 5000],   "imax": 6, "cap": "III"},
        60:  {"R": [2500, 4000],   "imax": 7, "cap": "IV"},
        40:  {"R": [700, 1000],    "imax": 9, "cap": "V"},
        30:  {"R": [400, 600],     "imax": 10, "cap": "VI"}
    }
    
    # 2. Dữ liệu tra cứu cho Cao tốc (TCVN 5729:2012)
    db_caotoc = {
        120: {"R": [15000, 20000], "imax": 4, "cap": "120"},
        100: {"R": [10000, 15000], "imax": 5, "cap": "100"},
        80:  {"R": [4500, 7000],   "imax": 6, "cap": "80"},
        60:  {"R": [2500, 4000],   "imax": 7, "cap": "60"}
    }
    
    # 3. Dữ liệu tra cứu cho Đường đô thị (TCVN 13592:2022)
    db_dothi = {
        100: {"R": [6500, 10000], "imax": 4, "cap": "Cao tốc ĐT"},
        80:  {"R": [3000, 4500],  "imax": 5, "cap": "Trục chính"},
        60:  {"R": [1400, 2000],  "imax": 6, "cap": "Chính thứ yếu"},
        50:  {"R": [800, 1200],   "imax": 6, "cap": "Đường khu vực"},
        40:  {"R": [450, 700],    "imax": 7, "cap": "Đường phố gom"},
        30:  {"R": [250, 400],    "imax": 8, "cap": "Đường nội bộ"}
    }

    # Chọn bộ dữ liệu tương ứng
    res = None
    tc_name = ""
    if loai == "O to":
        res = db_oto.get(vtk)
        tc_name = "TCVN 4054:2005"
    elif loai == "Cao tốc":
        res = db_caotoc.get(vtk)
        tc_name = "TCVN 5729:2012"
    elif loai == "Do thi":
        res = db_dothi.get(vtk)
        tc_name = "TCVN 13592:2022"

    if res:
        # Xử lý độ dốc dọc tối đa (i_max)
        imax_val = res['imax']
        # Đối với đường ô tô miền núi (dia_hinh="2"), cho phép châm chước tăng dốc
        ghi_chu_imax = ""
        if loai == "O to" and str(dia_hinh) == "2":
            imax_val += 0 # Giữ nguyên i_max gốc nhưng thêm ghi chú
            ghi_chu_imax = " (Có thể +1% khi khó khăn nhưng không quá 11%)"

        # Trả về kết quả dạng Dictionary để file 00 hiển thị
        return {
            "status": "success",
            "tieu_chuan": tc_name,
            "cap_duong": res['cap'],
            "v_thiet_ke": f"{vtk} km/h",
            "imax": f"{imax_val}%{ghi_chu_imax}",
            "R_loi_min": res['R'][0],
            "R_loi_tt": res['R'][1],
            "dia_hinh": "Đồng bằng" if str(dia_hinh) == "1" else "Miền núi"
        }
    
    return {"status": "error", "message": "Không tìm thấy thông số vận tốc phù hợp."}

# Hàm hiển thị bảng 3 chỉ dùng để in ra Console nếu cần (vẫn giữ cho bạn)
def hien_thi_bang_3_oto():
    print("\n--- BẢNG 3: CẤP THIẾT KẾ VÀ LƯU LƯỢNG XE THIẾT KẾ (TCVN 4054:2005) ---")
    print("| Cấp thiết kế | Lưu lượng xe thiết kế (xcqd/ngày đêm)           |")
    print("|--------------|-------------------------------------------------|")
    print("|    Cấp I     |               xcqd > 15.000                     |")
    print("|    Cấp II    |          6.000 < xcqd <= 15.000                 |")
    print("|    Cấp III   |          3.000 < xcqd <= 6.000                  |")
    print("|    Cấp IV    |            500 < xcqd <= 3.000                  |")
    print("|    Cấp V     |            200 < xcqd <= 500                    |")
    print("|    Cấp VI    |               xcqd <= 200                       |")
    print("------------------------------------------------------------------")