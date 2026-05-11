def tra_cuu_tinh_khong_bridge(loai_cau, mien=None, cap_num=None, loai_hinh=None, 
                               h1=0, h5=0, h10=0, h98=0, h_tn_tb=0, # THÊM BIẾN NÀY
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
                "H_TN_TB": h_tn_tb,
                "MNCN": h1,   # Mực nước cao nhất
                "MNTT": h5,   # Mực nước thông thuyền
                "MNTC": h10,  # Mực nước thi công
                "MNTN": h98,  # Mực nước thấp nhất
                "day_dam": round(cao_do_day_dam, 2),
                "label": f"Cầu vượt {('Kênh' if loai_hinh=='1' else 'Sông')} - Cấp {cap_num}"
            }
            
    elif loai_cau == "Vượt đường bộ":
        # 1. Chiều cao tĩnh không quy định theo hình ảnh bạn gửi
        # Cao tốc, Cấp I, Cấp II: 4.75m | Các loại khác: 4.5m
        if loai_duong_vuot == "Đường cao tốc":
            H = 5.0
        elif loai_duong_vuot == "Đường ô tô (Cấp I, II, III)":
            H = 4.75
        elif loai_duong_vuot == "Đường cải tạo":
            H = 4.3  # Theo yêu cầu H > 4.3m
        elif loai_duong_vuot == "Đường xe thô sơ":
            H = 2.5
        else:
            # Các cấp đường ô tô còn lại
            H = 4.5
        
        # 2. Bề rộng tĩnh không (B): Lấy theo khai báo của người dùng
        # Giả sử người dùng nhập B qua một tham số hoặc lấy mặc định nếu chưa nhập
        # Trong hàm này, ta sẽ ưu tiên lấy giá trị cap_oto (đang được dùng để truyền B từ Interface)
        # Nếu không có, mặc định là 0 để người dùng tự điền.
        B = cap_oto if cap_oto else 0 

        # 3. Tính toán cao độ đáy dầm
        # Với đường bộ, cao độ đáy dầm = Cao độ mặt đường vuot + H + 0.1 (phòng sai số)
        # Giả sử h1 ở đây đóng vai trò là cao độ mặt đường bên dưới
        cao_do_day_dam = h1 + H + 0.1
        
        return {
            "status": "success",
            "B": B,
            "H": H,
            "MNCN": h1,      # Cao độ mặt đường bị vượt dùng để vẽ nền
            "MNTT": h1,      # Đường bộ dùng h1 làm mốc bắt đầu khung tĩnh không
            "H_TN_TB": h1,   # Đường bộ coi mặt đường là cao độ tự nhiên trung bình
            "day_dam": round(cao_do_day_dam, 2),
            "label": f"Cầu vượt đường bộ - {loai_duong_vuot}"
        }