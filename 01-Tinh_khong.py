def tra_cuu_thiet_ke_cau_v5():
    # --- DỮ LIỆU QUY CHUẨN ---
    # Chuyển đổi key của cấp sông thành số "1", "2", "3"...
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
            "5": {"1": 15, "2": 25, "H": 4.0},
            "6": {"1": 10, "2": 13, "H": 3.0},
        }
    }

    print("="*50)
    print("      CHƯƠNG TRÌNH TRA CỨU THIẾT KẾ CẦU V5.0")
    print("="*50)
    print("CHỌN LOẠI CÔNG TRÌNH:")
    print("  1. Cầu vượt đường thủy")
    print("  2. Cầu vượt đường bộ")
    
    loai_cau = input("=> Nhập lựa chọn (1/2): ").strip()

    # --- TRƯỜNG HỢP 1: CẦU VƯỢT SÔNG ---
    if loai_cau == "1":
        print("\n[1. THÔNG TIN MIỀN]")
        print("  1. Miền Bắc")
        print("  2. Miền Nam")
        mien = input("=> Chọn miền (1/2): ").strip()

        print("\n[2. CẤP SÔNG]")
        print("  1. Cấp I    2. Cấp II   3. Cấp III")
        print("  4. Cấp IV   5. Cấp V    6. Cấp VI")
        cap_num = input("=> Chọn số tương ứng (1-6): ").strip()

        print("\n[3. LOẠI HÌNH THỦY ĐẠO]")
        print("  1. Kênh")
        print("  2. Sông")
        loai_hinh = input("=> Chọn loại (1/2): ").strip()

        print("\n[4. NHẬP CAO ĐỘ MỰC NƯỚC]")
        try:
            h1 = float(input(" - Nhập cao độ mực nước H1% (m): "))
            h5 = float(input(" - Nhập cao độ mực nước H5% (m): "))
        except ValueError:
            print("!! Lỗi: Vui lòng nhập số thập phân.")
            return

        # Xử lý kết quả vượt sông
        if mien in data_thuy and cap_num in data_thuy[mien]:
            target = data_thuy[mien][cap_num]
            khau_do = target.get(loai_hinh, "N/A")
            tinh_khong = target["H"]
            
            # Chuyển đổi số sang tên hiển thị
            ten_mien = "BẮC" if mien == "1" else "NAM"
            ten_loai = "KÊNH" if loai_hinh == "1" else "SÔNG"
            list_cap = ["I", "II", "III", "IV", "V", "VI"]
            ten_cap = list_cap[int(cap_num)-1]
            
            cao_do_day_kho = h5
            cao_do_dat_goi = h1 + 0.5
            cao_do_dam = max(h5 + tinh_khong, cao_do_dat_goi)

            print("\n" + "*"*50)
            print(f"KẾT QUẢ: CẦU VƯỢT {ten_loai} - CẤP {ten_cap} - MIỀN {ten_mien}")
            print("-" * 50)
            print(f"  + Khẩu độ ngang thông thuyền (B): {khau_do} m")
            print(f"  + Chiều cao tĩnh không (H):      {tinh_khong} m")
            print(f"  + Mực nước thông thuyền (MNTT):  {cao_do_day_kho:.2f} m")
            print(f"  + CAO ĐỘ ĐÁY DẦM TỐI THIỂU:     {cao_do_dam:.2f} m")
            print("*"*50)
        else:
            print("!! Lỗi: Lựa chọn cấp sông hoặc miền không hợp lệ.")

    # --- TRƯỜNG HỢP 2: CẦU VƯỢT ĐƯỜNG ---
    elif loai_cau == "2":
        print("\n[LOẠI ĐƯỜNG BỊ VƯỢT]")
        print("  1. Đường cao tốc")
        print("  2. Đường ô tô")
        loai_duong = input("=> Chọn loại đường (1/2): ").strip()

        h_tinh_khong = 0
        ten_duong = ""

        if loai_duong == "1":
            h_tinh_khong = 5.0
            ten_duong = "ĐƯỜNG CAO TỐC"
        elif loai_duong == "2":
            print("\n[CẤP ĐƯỜNG Ô TÔ]")
            print("  1. Cấp I, II, III")
            print("  2. Các cấp còn lại")
            cap_oto = input("=> Chọn cấp đường (1/2): ").strip()
            
            if cap_oto == "1":
                h_tinh_khong = 4.75
                ten_duong = "ĐƯỜNG Ô TÔ CẤP I/II/III"
            else:
                h_tinh_khong = 4.5
                ten_duong = "ĐƯỜNG Ô TÔ CẤP THẤP"

        if h_tinh_khong > 0:
            print("\n" + "*"*50)
            print(f"KẾT QUẢ: CẦU VƯỢT {ten_duong}")
            print("-" * 50)
            print(f"  + Chiều cao tĩnh không (H): {h_tinh_khong} m")
            print("*"*50)
        else:
            print("!! Lỗi: Lựa chọn không hợp lệ.")

    else:
        print("!! Lỗi: Chỉ nhập 1 hoặc 2.")

if __name__ == "__main__":
    tra_cuu_thiet_ke_cau_v5()