import pandas as pd

def tra_cuu_tieu_chuan_hinh_hoc(loai_duong, vtk):
    """
    Hàm tra cứu các chỉ tiêu kỹ thuật hình học dựa trên TCVN 4054:2005 và TCVN 9436:2012.
    """
    res = {
        "status": "error",
        "message": "",
        "data": {}
    }

    # 1. Cơ sở dữ liệu cho ĐƯỜNG Ô TÔ (TCVN 4054:2005)
    db_oto = {
        40: {"ten_cap": "Cấp IV", "imax": 7, "R_loi": [700, 450, 1200]}, # [R_loi_min, R_loi_tt, R_lom_min]
        60: {"ten_cap": "Cấp III", "imax": 6, "R_loi": [2500, 1500, 2000]},
        80: {"ten_cap": "Cấp II", "imax": 5, "R_loi": [5000, 3000, 3000]},
        100: {"ten_cap": "Cấp I", "imax": 4, "R_loi": [10000, 6000, 5000]}
    }

    # 2. Cơ sở dữ liệu cho ĐƯỜNG CAO TỐC (TCVN 5729:2012)
    db_caotoc = {
        60: {"ten_cap": "V60", "imax": 6, "R_loi": [2500, 1500, 2000]},
        80: {"ten_cap": "V80", "imax": 5, "R_loi": [5000, 3000, 3000]},
        100: {"ten_cap": "V100", "imax": 4, "R_loi": [10000, 6000, 5000]},
        120: {"ten_cap": "V120", "imax": 4, "R_loi": [15000, 9000, 8000]}
    }

    # 3. Cơ sở dữ liệu cho ĐƯỜNG ĐÔ THỊ (TCVN 13592:2022)
    db_dothi = {
        30: {"ten_cap": "Đường phố nội bộ", "imax": 9, "R_loi": [400, 250, 400]},
        40: {"ten_cap": "Đường thu gom", "imax": 8, "R_loi": [700, 450, 700]},
        50: {"ten_cap": "Đường chính khu vực", "imax": 7, "R_loi": [1200, 800, 1000]},
        60: {"ten_cap": "Đường trục chính đô thị", "imax": 6, "R_loi": [2500, 1500, 2000]}
    }

    try:
        data_match = None
        if loai_duong == "O to":
            data_match = db_oto.get(vtk)
        elif loai_duong == "Cao tốc":
            data_match = db_caotoc.get(vtk)
        elif loai_duong == "Do thi":
            data_match = db_dothi.get(vtk)

        if data_match:
            res["status"] = "success"
            res["data"] = {
                "loai": loai_duong,
                "cap_duong": data_match["ten_cap"],
                "imax": data_match["imax"],
                "R_loi_min": data_match["R_loi"][0],
                "R_loi_tt": data_match["R_loi"][1],
                "R_lom_min": data_match["R_loi"][2]
            }
        else:
            res["message"] = f"Không tìm thấy dữ liệu cho vận tốc {vtk} km/h của loại đường này."

    except Exception as e:
        res["message"] = f"Lỗi hệ thống: {str(e)}"

    return res

def tinh_toan_mat_cat_ngang(n_lan, w_lan, w_le, w_dai_an_toan=0.5):
    """
    Tính toán bề rộng cầu tổng thể (Bc)
    """
    # Công thức cơ bản: Bc = n*W_lan + 2*W_an_toan + 2*W_lan_can
    # Giả định bề rộng gờ lan can mỗi bên là 0.5m
    w_lan_can = 0.5 
    
    bc_thong_thuy = (n_lan * w_lan) + (2 * w_le) + (2 * w_dai_an_toan)
    bc_tong = bc_thong_thuy + (2 * w_lan_can)
    
    return round(bc_tong, 2)