def tra_cuu_tinh_khong_bridge(loai_cau, mien=None, cap_num=None, loai_hinh=None, 
                               h1=0, h5=0, h10=0, h98=0, 
                               loai_duong_vuot=None, cap_oto=None):
    # --- DỮ LIỆU GỐC TỪ FORM MẪU V5.0 ---
    data_thuy = {
        "1": { # Bắc
            "1": {"1": 70, "2": 85, "H": 11.0}, "2": {"1": 40, "2": 50, "H": 9.5},
            "3": {"1": 30, "2": 40, "H": 7.0},  "4": {"1": 25, "2": 30, "H": 6.0},
            "5": {"1": 15, "2": 20, "H": 4.0},  "6": {"1": 10, "2": 10, "H": 3.0},
        },
        "2": { # Nam
            "1": {"1": 75, "2": 120, "H": 11.0}, "2": {"1": 50, "2": 60, "H": 9.5},
            "3": {"1": 30, "2": 50, "H": 7.0},  "4": {"1": 25, "2": 30, "H": 6.0},
            "5": {"1": 15, "2": 25, "H": 4.0},  "6": {"1": 10, "2": 13, "H": 3.0},
        }
    }

    if loai_cau == "Vượt sông":
        if mien in data_thuy and cap_num in data_thuy[mien]:
            target = data_thuy[mien][cap_num]
            B = target.get(loai_hinh, "N/A")
            H = target["H"]
            
            # Tính toán cao độ đáy dầm tối thiểu
            cao_do_dat_goi = h1 + 0.5
            cao_do_day_dam = max(h5+H+0.1, cao_do_dat_goi)
            
            return {
                "status": "success",
                "B": B,
                "H": H,
                "MNCN": h1,   # Mực nước cao nhất
                "MNTT": h5,   # Mực nước thông thuyền
                "MNTC": h10,  # Mực nước thi công
                "MNTN": h98,  # Mực nước thấp nhất
                "day_dam": round(cao_do_day_dam, 2),
                "label": f"Cầu vượt {('Kênh' if loai_hinh=='1' else 'Sông')} - Cấp {cap_num}"
            }
            
    elif loai_cau == "Vượt đường bộ":
        H = 0
        ten = ""
        if loai_duong_vuot == "Cao tốc":
            H = 5.0
            ten = "Đường Cao tốc"
        else:
            H = 4.75 if cap_oto == "1" else 4.5
            ten = "Đường Ô tô"
            
        return {
            "status": "success",
            "B": "Theo quy mô mặt cắt ngang",
            "H": H,
            "day_dam": "Tính theo cao độ mặt đường bị vượt",
            "label": f"Cầu vượt {ten}"
        }
    
    return {"status": "error", "message": "Dữ liệu không hợp lệ"}