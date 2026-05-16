import pandas as pd
import numpy as np
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
def tinh_toan_geo_logic(res, h_tn_tb, h_dam, h_dap_yc=6.0):
    """Tính toán hình học trắc dọc - Đã dời gốc tọa độ (0,0) về TIM TĨNH KHÔNG"""
    R = res.get('R_hinh_hoc', 5000)
    i_val = res.get('i_max_hinh_hoc', 4.0) / 100
    
    # 1. Xác định mốc cao độ gốc Y=0 dựa trên loại cầu
    label_res = res.get('label', "")
    is_duong_bo = "vượt đường bộ" in label_res.lower()
    h1 = res.get('MNCN', 0)
    h5 = res.get('MNTT', 0)
    y_base_goc = h1 if is_duong_bo else h5

    # Đưa cao độ đỉnh đường đỏ tuyệt đối về hệ tọa độ tương đối
    y_dinh_tuyet_doi = h_dam + 2.0 
    y_dinh = y_dinh_tuyet_doi - y_base_goc

    # 2. Ép tim cầu về X = 0 (Đối xứng hoàn hảo)
    x_dinh = 0  
    T = R * i_val
    x_t1, x_t2 = -T, T
    y_t = y_dinh - (T**2) / (2 * R)

    # Chiều dài cầu tối thiểu
    l_nhip_du_kien = res.get('ai_result', {}).get('chieu_dai', 33.0) 
    l_cau_min = l_nhip_du_kien + 10.0 

    # 3. Quét địa hình tương đối tìm mố (Quét từ -500 đến 500 thay vì 0 đến 1000)
    x_scan = np.linspace(-500, 500, 2000)
    y_scan = []
    for xi in x_scan:
        if xi < x_t1: yi = y_t - i_val * (x_t1 - xi)
        elif xi > x_t2: yi = y_t - i_val * (xi - x_t2)
        else: yi = y_dinh - xi**2 / (2 * R)
        y_scan.append(yi)
    y_scan = np.array(y_scan)

    # 4. Tìm mố trái đối xứng (Quét nửa âm bên trái xi < 0)
    h_tn_tb_tuong_doi = h_tn_tb - y_base_goc
    delta_y = y_scan - h_tn_tb_tuong_doi
    
    # Chỉ tìm trong khoảng x_scan < 0 (tương ứng 1000 phần tử đầu tiên)
    idx_mo = np.argmin(np.abs(delta_y[:1000] - h_dap_yc))
    x_mo_trai_tinh_toan = x_scan[idx_mo]
    
    # Khống chế chiều dài tối thiểu đối xứng
    x_mo_trai_min = - (l_cau_min / 2)
    x_mo_trai = min(x_mo_trai_tinh_toan, x_mo_trai_min)
    
    l_cau_final = abs(x_mo_trai) * 2

    return {
        "x_t1": x_t1, 
        "x_t2": x_t2, 
        "y_t": y_t, 
        "y_dinh": y_dinh, 
        "R": R, 
        "i_val": i_val,
        "x_mo_trai": x_mo_trai,
        "x_mo_phai": abs(x_mo_trai),
        "y_mo": y_scan[idx_mo] if x_mo_trai == x_mo_trai_tinh_toan else y_scan[np.argmin(np.abs(x_scan - x_mo_trai))],
        "L_cau": l_cau_final,
        "h_tn_tb": h_tn_tb,
        "y_base_goc": y_base_goc # Lưu lại mốc dời trục để đồng bộ các phần tử thủy văn
    }