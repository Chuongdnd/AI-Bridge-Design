def tra_cuu_yeu_to_hinh_hoc(loai, vtk, dia_hinh="1"):
    """
    Hàm tra cứu các chỉ tiêu kỹ thuật dựa trên TCVN.
    loai: "O to", "Cao tốc", "Do thi"
    vtk: Tốc độ thiết kế
    dia_hinh: "1" (Đồng bằng), "2" (Miền núi)
    """
    # Dữ liệu tra cứu cho Đường Ô tô (TCVN 4054:2005)
    db_oto = {
        120: {"R": [11000, 17000], "imax": 4, "cap": "I"},
        100: {"R": [6000, 10000],  "imax": 5, "cap": "II"},
        80:  {"R": [4000, 5000],   "imax": 6, "cap": "III"},
        60:  {"R": [2500, 4000],   "imax": 7, "cap": "IV"},
        40:  {"R": [700, 1000],    "imax": 9, "cap": "V"},
        30:  {"R": [400, 600],     "imax": 10, "cap": "VI"}
    }
    
    # Dữ liệu tra cứu cho Cao tốc (TCVN 5729:2012)
    db_caotoc = {
        120: {"R": [12000, 17000, 20000], "imax": 4, "cap": "120"},
        100: {"R": [6000, 10000, 16000],  "imax": 5, "cap": "100"},
        80:  {"R": [3000, 4500, 12000],   "imax": 6, "cap": "80"},
        60:  {"R": [1500, 2000, 9000],    "imax": 6, "cap": "60"}
    }
    
    # Dữ liệu tra cứu cho Đường Đô thị (TCVN 13592:2022)
    db_dothi = {
        100: {"R": [6500, 10000], "imax": 4, "cap": "Cao tốc ĐT"},
        80:  {"R": [3000, 4500],  "imax": 5, "cap": "Trục chính"},
        60:  {"R": [1400, 2000],  "imax": 6, "cap": "Chính thứ yếu"},
        50:  {"R": [800, 1200],   "imax": 6, "cap": "Đường khu vực"},
        40:  {"R": [450, 700],    "imax": 7, "cap": "Đường phố gom"},
        30:  {"R": [250, 400],    "imax": 8, "cap": "Đường nội bộ"}
    }

    res = None
    if loai == "O to":
        res = db_oto.get(vtk)
    elif loai == "Cao tốc":
        res = db_caotoc.get(vtk)
    elif loai == "Do thi":
        res = db_dothi.get(vtk)

    if res:
        # Xử lý độ dốc dọc tối đa (i_max)
        imax_val = res['imax']
        if loai == "O to" and dia_hinh == "2":
            imax_val += 1 # Tăng 1% cho miền núi
            if imax_val > 11: imax_val = 11

        return {
            "status": "success",
            "cap_duong": res['cap'],
            "imax": imax_val,
            "R_loi_min": res['R'][0],
            "R_loi_tt": res['R'][1]
        }
    return {"status": "error", "message": "Không có dữ liệu cho vận tốc này"}

def tinh_toan_mcn_cau(n_lan, w_lan, w_le, w_at=0.5):
    """Tính toán bề rộng tổng cộng của cầu Bc"""
    # Bc = n*W_lan + 2*W_le + 2*W_an_toan + 2*Gờ lan can (0.5m mỗi bên)
    bc_thong_thuy = (n_lan * w_lan) + (2 * w_le) + (2 * w_at)
    bc_tong = bc_thong_thuy + 1.0 # 0.5m x 2 gờ lan can
    return round(bc_tong, 2)