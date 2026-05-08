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

def hien_thi_bang_5_dothi():
    print("\n--- BẢNG 5: PHÂN LOẠI ĐƯỜNG ĐÔ THỊ THEO CHỨC NĂNG (TCVN 13592:2022) ---")
    print("1. Hệ thống đường chính đô thị (Giao thông cơ động cao):")
    print("   - Cao tốc đô thị: Liên hệ đối ngoại, vành đai (Vtk: 80-100 km/h)")
    print("   - Phố chính chủ yếu: Trục chính toàn đô thị (Vtk: 60-80 km/h)")
    print("   - Phố chính thứ yếu: Liên hệ giữa các khu vực (Vtk: 50-60 km/h)")
    print("2. Hệ thống đường phố gom (Tiếp cận trung gian):")
    print("   - Phố gom chủ yếu/thứ yếu: Liên hệ đơn vị ở (Vtk: 40-60 km/h)")
    print("3. Hệ thống đường phố nội bộ (Tiếp cận cao):")
    print("   - Phố nội bộ: Liên hệ trong nhóm nhà ở (Vtk: 20-40 km/h)")
    print("-----------------------------------------------------------------------")

def chon_cap_duong():
    print("\n" + "="*60)
    print("      MODULE: KHAI BÁO CẤP ĐƯỜNG & TỐC ĐỘ THIẾT KẾ")
    print("="*60)
    print("CHỌN LOẠI ĐƯỜNG:")
    print("  1. Đường cao tốc (TCVN 5729:2012)")
    print("  2. Đường ô tô (TCVN 4054:2005)")
    print("  3. Đường đô thị (TCVN 13592:2022)")
    
    loai = input("=> Nhập lựa chọn (1/2/3): ").strip()

    if loai == "1":
        print("\n[GHI CHÚ ĐỊA HÌNH]:")
        print(" - Cấp 100, 120: Áp dụng cho vùng ĐỒNG BẰNG.")
        print(" - Cấp 60, 80: Áp dụng cho vùng NÚI, ĐỒI CAO, địa hình KHÓ KHĂN.")
        print("-" * 30)
        print("CHỌN CẤP TỐC ĐỘ:")
        print("  1. Cấp 120    2. Cấp 100    3. Cấp 80    4. Cấp 60")
        pick = input("=> Chọn (1-4): ").strip()
        vtk_map = {"1": 120, "2": 100, "3": 80, "4": 60}
        ten_cap_map = {"1": "120", "2": "100", "3": "80", "4": "60"}
        return {"loai": "Cao toc", "vtk": vtk_map.get(pick, 80), "ten_cap": ten_cap_map.get(pick)}

    elif loai == "2":
        hien_thi_bang_3_oto()
        print("\nCHỌN CẤP ĐƯỜNG VÀ ĐỊA HÌNH:")
        print("  1. Cấp I      2. Cấp II     3. Cấp III")
        print("  4. Cấp IV     5. Cấp V      6. Cấp VI")
        cap_input = input("=> Chọn cấp (1-6): ").strip()
        dh_input = input("=> Địa hình (1. Đồng bằng / 2. Núi): ").strip()
        
        vtk_map = {
            "1": {"1": 120, "2": 120}, "2": {"1": 100, "2": 100},
            "3": {"1": 80, "2": 60},  "4": {"1": 60, "2": 40},
            "5": {"1": 40, "2": 30},  "6": {"1": 30, "2": 20}
        }
        ten_cap_list = ["I", "II", "III", "IV", "V", "VI"]
        vtk = vtk_map.get(cap_input, {}).get(dh_input, 60)
        ten_cap = ten_cap_list[int(cap_input)-1] if cap_input.isdigit() and 1<=int(cap_input)<=6 else "N/A"
        return {"loai": "O to", "vtk": vtk, "ten_cap": ten_cap, "dia_hinh": dh_input}

    elif loai == "3":
        hien_thi_bang_5_dothi()
        print("\nCHỌN LOẠI ĐƯỜNG ĐÔ THỊ:")
        print("  1. Cao tốc đô thị      2. Phố chính chủ yếu")
        print("  3. Phố chính thứ yếu   4. Phố gom")
        print("  5. Phố nội bộ")
        pick = input("=> Chọn (1-5): ").strip()
        vtk_map = {"1": 100, "2": 80, "3": 60, "4": 50, "5": 30}
        ten_loai_map = {"1": "Cao tốc đô thị", "2": "Phố chính chủ yếu", "3": "Phố chính thứ yếu", "4": "Phố gom", "5": "Phố nội bộ"}
        return {"loai": "Do thi", "vtk": vtk_map.get(pick, 60), "ten_loai": ten_loai_map.get(pick)}

    return None

def tra_cuu_yeu_to_hinh_hoc(data):
    if not data: return
    vtk = data["vtk"]
    loai = data["loai"]

    # Dữ liệu tra cứu: R_loi [GH, TT, ThiGiac], i_max dọc
    db_caotoc = {
        120: {"R": [12000, 17000, 20000], "imax": 4},
        100: {"R": [6000, 10000, 16000],  "imax": 5},
        80:  {"R": [3000, 4500, 12000],   "imax": 6},
        60:  {"R": [1500, 2000, 9000],    "imax": 6}
    }
    db_oto = {
        120: {"R": [11000, 17000], "imax": 4},
        100: {"R": [6000, 10000],  "imax": 5},
        80:  {"R": [4000, 5000],   "imax": 6},
        60:  {"R": [2500, 4000],   "imax": 7},
        40:  {"R": [700, 1000],    "imax": 9},
        30:  {"R": [400, 600],     "imax": 10},
        20:  {"R": [200, 200],     "imax": 11}
    }
    db_dothi = {
        100: {"R": [6500, 10000], "imax": 4},
        80:  {"R": [3000, 4500],  "imax": 5},
        60:  {"R": [1400, 2000],  "imax": 6},
        50:  {"R": [800, 1200],   "imax": 6},
        40:  {"R": [450, 700],    "imax": 7},
        30:  {"R": [250, 400],    "imax": 8},
        20:  {"R": [100, 200],    "imax": 9}
    }

    print("\n" + "="*50)
    print("KẾT QUẢ TRA CỨU YẾU TỐ HÌNH HỌC")

    if loai == "Cao toc":
        res = db_caotoc.get(vtk)
        print("ĐỐI TƯỢNG: ĐƯỜNG CAO TỐC")
        print("Tiêu chuẩn: TCVN 5729:2012")
        print(f"Cấp đường: Cấp {data['ten_cap']}")
        print(f"Vận tốc thiết kế Vtk: {vtk} km/h")
        print(f"Độ dốc dọc tối đa i_max: {res['imax']}%")
        print(f"Độ dốc ngang mặt đường i_n: 2.0%")
        print("Bán kính đường cong đứng")
        print(f"  + R lồi tối thiểu giới hạn: {res['R'][0]} m")
        print(f"  + R lồi tối thiểu thông thường: {res['R'][1]} m")
        print(f"  + R lồi đạt yêu cầu thị giác: {res['R'][2]} m")

    elif loai == "O to":
        res = db_oto.get(vtk)
        print("ĐỐI TƯỢNG: ĐƯỜNG Ô TÔ")
        print("Tiêu chuẩn: TCVN 4054:2005")
        print(f"Cấp đường: Cấp {data['ten_cap']}")
        print(f"Vận tốc thiết kế Vtk: {vtk} km/h")
        print(f"Độ dốc dọc tối đa i_max: {res['imax']}%")
        if data.get("dia_hinh") == "2":
            print("  (*) Ghi chú: Khi khó khăn có thể +1% nhưng không quá 11%")
        
        print("Độ dốc ngang mặt đường (tham khảo):")
        print("  + Mặt BTXM, BT nhựa: 1.5% - 2.0%")
        print("  + Lề không gia cố: 4.0% - 6.0%")
        print("Bán kính đường cong đứng")
        print(f"  + R lồi tối thiểu giới hạn: {res['R'][0]} m")
        print(f"  + R lồi tối thiểu thông thường: {res['R'][1]} m")

    elif loai == "Do thi":
        res = db_dothi.get(vtk)
        print("ĐỐI TƯỢNG: ĐƯỜNG ĐÔ THỊ")
        print("Tiêu chuẩn: TCVN 13592:2022")
        print(f"Loại đường: {data['ten_loai']}")
        print(f"Vận tốc thiết kế Vtk: {vtk} km/h")
        print(f"Độ dốc dọc tối đa i_max: {res['imax']}%")
        print(f"Độ dốc ngang mặt đường i_n: 1.5% - 2.5%")
        print("Bán kính đường cong đứng")
        print(f"  + R lồi tiêu chuẩn: {res['R'][0]} m")
        print(f"  + R lồi mong muốn: {res['R'][1]} m")
    
    print("="*50)

if __name__ == "__main__":
    ket_qua = chon_cap_duong()
    tra_cuu_yeu_to_hinh_hoc(ket_qua)