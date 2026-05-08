def tra_cuu_tinh_khong_bridge(loai_cau, mien=None, cap_song=None, loai_hinh_thuy=None, h1=0.0, h5=0.0, loai_duong_vuot=None, cap_oto=None):
    """
    Hàm tra cứu tĩnh không cầu.
    Dữ liệu được trích xuất từ các quy chuẩn TCVN hiện hành.
    """
    
    # --- DỮ LIỆU QUY CHUẨN ĐƯỜNG THỦY ---
    # 1: Miền Bắc, 2: Miền Nam
    # loai_hinh_thuy: "1": Kênh, "2": Sông
    data_thuy = {
        "1": { # Bắc
            "1": {"1": 70, "2": 85, "H": 11.0}, # Cấp I
            "2": {"1": 40, "2": 50, "H": 9.5},  # Cấp II
            "3": {"1": 30, "2": 40, "H": 7.0},  # Cấp III
            "4": {"1": 25, "2": 30, "H": 6.0},  # Cấp IV
            "5": {"1": 15, "2": 20, "H": 4.0},  # Cấp V
            "6": {"1": 10, "2": 10, "H": 3.0},  # Cấp VI
        },
        "2": { # Nam
            "1": {"1": 75, "2": 120, "H": 11.0},
            "2": {"1": 50, "2": 60, "H": 9.5},
            "3": {"1": 30, "2": 50, "H": 7.0},
            "4": {"1": 25, "2": 30, "H": 6.0},
            "5": {"1": 20, "2": 25, "H": 4.0},
            "6": {"1": 15, "2": 15, "H": 3.0},
        }
    }

    # --- TRƯỜNG HỢP 1: CẦU VƯỢT SÔNG ---
    if loai_cau == "Vượt sông":
        try:
            target = data_thuy[mien][cap_song]
            khau_do_ngang = target[loai_hinh_thuy]
            h_thong_thuyen = target["H"]
            
            # Tính cao độ đáy dầm tối thiểu
            # Thường lấy max của (H5% + H thông thuyền) và (H1% + 0.5m an toàn)
            cao_do_day_dam = max(h5 + h_thong_thuyen, h1 + 0.5)
            
            return {
                "status": "success",
                "loai": "CẦU VƯỢT SÔNG",
                "khau_do_ngang": khau_do_ngang,
                "h_tinh_khong": h_thong_thuyen,
                "cao_do_day_dam": round(cao_do_day_dam, 3),
                "ghi_chu": f"Dựa trên cấp sông {cap_song} - { 'Miền Bắc' if mien=='1' else 'Miền Nam'}"
            }
        except KeyError:
            return {"status": "error", "message": "Dữ liệu cấp sông hoặc miền không hợp lệ."}

    # --- TRƯỜNG HỢP 2: CẦU VƯỢT ĐƯỜNG BỘ ---
    elif loai_cau == "Vượt đường bộ":
        h_tinh_khong = 0.0
        ten_duong = ""
        
        if loai_duong_vuot == "Cao tốc":
            h_tinh_khong = 5.0
            ten_duong = "ĐƯỜNG CAO TỐC"
        else: # Đường ô tô
            if cap_oto == "Cấp I, II, III":
                h_tinh_khong = 4.75
                ten_duong = "ĐƯỜNG Ô TÔ CẤP I-III"
            else:
                h_tinh_khong = 4.5
                ten_duong = "ĐƯỜNG Ô TÔ CÁC CẤP CÒN LẠI"
        
        return {
            "status": "success",
            "loai": "CẦU VƯỢT ĐƯỜNG",
            "khau_do_ngang": "Theo mặt cắt ngang đường bị vượt",
            "h_tinh_khong": h_tinh_khong,
            "cao_do_day_dam": "Tùy thuộc cao độ mặt đường bị vượt",
            "ghi_chu": f"Tĩnh không đứng yêu cầu: {h_tinh_khong}m ({ten_duong})"
        }
    
    return {"status": "error", "message": "Loại cầu không xác định."}