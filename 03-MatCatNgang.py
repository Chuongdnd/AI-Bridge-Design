import importlib
import sys

# Bước 1: Kết nối với file 02-Yeuto_Hinhhoc.py
try:
    # Thử import nếu bạn đã đổi tên thành Yeuto_Hinhhoc.py
    import Yeuto_Hinhhoc as YTHH
except ImportError:
    try:
        # Sử dụng importlib cho tên file có dấu gạch ngang
        YTHH = importlib.import_module("02-Yeuto_Hinhhoc")
    except ModuleNotFoundError:
        print("Lỗi: Không tìm thấy file 02-Yeuto_Hinhhoc.py trong cùng thư mục!")
        sys.exit()

def thiet_ke_mcn_cau(data):
    if not data:
        return
    
    loai = data.get("loai")
    vtk = data.get("vtk")
    cap = data.get("ten_cap")
    
    if loai == "Cao toc":
        # --- DỮ LIỆU TRA CỨU BẢNG 1 - TCVN 5729:2012 ---
        db_dpc = {
            "1": {120: [0.75, 0.75], 100: [0.75, 0.75], 80: [0.50, 0.50], 60: [0.50, 0.50]},
            "2": {120: [3.00, 0.75], 100: [3.00, 0.75], 80: [2.00, 0.50], 60: [2.00, 0.50]},
            "3": {120: [3.00, 0.75], 100: [3.00, 0.75], 80: [3.00, 0.50], 60: [3.00, 0.50]}
        }
        
        db_ngoai = {
            120: {"at_ngoai": 3.0, "le_co": 0.75, "mat_chuan": 7.5},
            100: {"at_ngoai": 3.0, "le_co": 0.75, "mat_chuan": 7.5},
            80:  {"at_ngoai": 2.5, "le_co": 0.75, "mat_chuan": 7.0},
            60:  {"at_ngoai": 2.5, "le_co": 0.75, "mat_chuan": 7.0}
        }

        # 1. Khai báo cấu tạo dải phân cách
        print("\n" + "-" * 30 + " THIẾT LẬP CẤU TẠO CAO TỐC " + "-" * 30)
        print("CHỌN CẤU TẠO DẢI PHÂN CÁCH GIỮA (Bảng 1 - TCVN 5729):")
        print("  1. Loại 1: Có lớp phủ, không trụ cầu")
        print("  2. Loại 2: Không lớp phủ (trồng cỏ...)")
        print("  3. Loại 3: Có bố trí trụ cầu/công trình")
        pick_dpc = input("=> Nhập lựa chọn (1-3) [Mặc định 1]: ").strip() or "1"
        
        dpc_names = {"1": "Loại 1 (Có lớp phủ)", "2": "Loại 2 (Trồng cỏ)", "3": "Loại 3 (Có trụ cầu)"}
        ten_dpc = dpc_names.get(pick_dpc, dpc_names["1"])

        # 2. Khai báo số làn xe và lan can
        user_lan = input(f"=> Nhập số làn xe mỗi chiều (Mặc định tối thiểu 2): ").strip()
        so_lan = int(user_lan) if user_lan and int(user_lan) >= 2 else 2
        
        w_lc_def = 0.5
        user_lc = input(f"=> Nhập bề rộng lan can mỗi bên [Mặc định {w_lc_def}m]: ").strip()
        w_lc = float(user_lc) if user_lc else w_lc_def

        # 3. Tra cứu và tính toán bề rộng
        w_dpc_thong_thuy, w_at_trong = db_dpc.get(pick_dpc, db_dpc["1"])[vtk]
        cfg_ngoai = db_ngoai[vtk]
        
        # Dải giữa (W_g)
        w_g = w_dpc_thong_thuy + (2 * w_at_trong)
        
        # Tính toán mặt đường
        w_mat_1_ben = cfg_ngoai["mat_chuan"]
        if so_lan > 2:
            delta = 3.75 if vtk >= 100 else 3.5
            w_mat_1_ben += delta * (so_lan - 2)
            
        # Tổng bề rộng cầu (Bc) và Nền đường (Bn)
        w_duong = (w_mat_1_ben * 2) + (cfg_ngoai["at_ngoai"] * 2) + w_g + (cfg_ngoai["le_co"] * 2)
        
        is_don_nguyen_tach = w_dpc_thong_thuy >= 1.5
        if is_don_nguyen_tach:
            w_1_don_nguyen = w_lc + cfg_ngoai["at_ngoai"] + w_mat_1_ben + w_at_trong + w_lc
            w_khoang_ho = w_dpc_thong_thuy - (2 * w_lc)
            w_cau = (2 * w_1_don_nguyen) + w_khoang_ho
        else:
            w_cau = (w_mat_1_ben * 2) + (cfg_ngoai["at_ngoai"] * 2) + w_g + (2 * w_lc)

        # 4. HIỂN THỊ KẾT QUẢ
        print("\n" + "="*95)
        print(f"{'KẾT QUẢ BỐ TRÍ MẶT CẮT NGANG CẦU CAO TỐC':^95}")
        print("="*95)
        print(f"TIÊU CHUẨN: TCVN 5729:2012")
        print(f"+ Cấu tạo dải giữa: {ten_dpc}")
        print(f"+ Số làn xe: {so_lan} làn/chiều")
        print(f"+ Vận tốc thiết kế (Vtk): {vtk} km/h")
        print("-" * 95)
        
        header_str = "BẢNG TỔNG HỢP MẶT CẮT NGANG"
        print(f"{header_str:^95}")
        print("-" * 95)

        # Sơ đồ Đường
        le_duong = f"--LỀ CỎ {cfg_ngoai['le_co']}m--AT NGOÀI {cfg_ngoai['at_ngoai']}m--"
        phan_xe = f"--MD ({so_lan}L) {w_mat_1_ben:.2f}m--"
        dpc_duong = f"|AT {w_at_trong}m|DPC {w_dpc_thong_thuy}m|AT {w_at_trong}m|"
        
        print(f" [ĐƯỜNG]: {le_duong}{phan_xe}{dpc_duong}{phan_xe}{le_duong}")
        print(f" ==> TỔNG BỀ RỘNG NỀN ĐƯỜNG (Bn): {w_duong:.2f} m")
        print("-" * 95)

        # Sơ đồ Cầu
        if is_don_nguyen_tach:
            dn_trai = f"|LC {w_lc}|AT NG {cfg_ngoai['at_ngoai']}|{phan_xe}|AT TR {w_at_trong}|LC {w_lc}|"
            dn_phai = f"|LC {w_lc}|AT TR {w_at_trong}|{phan_xe}|AT NG {cfg_ngoai['at_ngoai']}|LC {w_lc}|"
            print(f" [CẦU ]: {dn_trai} < Hở {w_khoang_ho:.2f}m > {dn_phai}")
            print(f" ==> BỀ RỘNG 1 ĐƠN NGUYÊN: {w_1_don_nguyen:.2f} m")
        else:
            le_cau = f"|LC {w_lc}|AT NG {cfg_ngoai['at_ngoai']}m--"
            print(f" [CẦU ]: {le_cau}{phan_xe}{dpc_duong}{phan_xe}{le_cau[::-1]}")
        
        print(f" ==> TỔNG BỀ RỘNG TOÀN CẦU (Bc): {w_cau:.2f} m")
        print("="*95)

    elif loai == "O to":
        dia_hinh = data.get("dia_hinh", "Dong bang") 
        is_nui = "Nui" in dia_hinh or "MN" in dia_hinh
        dia_hinh_input = data.get("dia_hinh", "1")
        if dia_hinh_input == "1" or "Dong bang" in str(dia_hinh_input):
            dia_hinh_display = "Đồng bằng"
            is_nui = False
        else:
            dia_hinh_display = "Núi"
            is_nui = True
        # --- DỮ LIỆU GỐC TỪ TIÊU CHUẨN ---
        db_6 = {
            "I":   {"lan": 6, "w_1_lan": 3.75, "w_mat": 22.5, "le_gc": 3.00, "nen": 32.5, "dpc_mac_dinh": 3.0},
            "II":  {"lan": 4, "w_1_lan": 3.75, "w_mat": 15.0, "le_gc": 2.50, "nen": 22.5, "dpc_mac_dinh": 1.5},
            "III": {"lan": 2, "w_1_lan": 3.50, "w_mat": 7.0,  "le_gc": 2.00, "nen": 12.0, "dpc_mac_dinh": 0.0},
            "IV":  {"lan": 2, "w_1_lan": 3.50, "w_mat": 7.0,  "le_gc": 0.50, "nen": 9.0,  "dpc_mac_dinh": 0.0},
            "V":   {"lan": 2, "w_1_lan": 2.75, "w_mat": 5.5,  "le_gc": 0.50, "nen": 7.5,  "dpc_mac_dinh": 0.0},
            "VI":  {"lan": 1, "w_1_lan": 3.50, "w_mat": 3.5,  "le_gc": 0.00, "nen": 6.5,  "dpc_mac_dinh": 0.0}
        }
        db_7 = {
            "III": {"lan": 2, "w_1_lan": 3.00, "w_mat": 6.0,  "le_gc": 1.00, "nen": 9.0,  "dpc_mac_dinh": 0.0},
            "IV":  {"lan": 2, "w_1_lan": 2.75, "w_mat": 5.5,  "le_gc": 0.50, "nen": 7.5,  "dpc_mac_dinh": 0.0},
            "V":   {"lan": 1, "w_1_lan": 3.50, "w_mat": 3.5,  "le_gc": 1.00, "nen": 6.5,  "dpc_mac_dinh": 0.0},
            "VI":  {"lan": 1, "w_1_lan": 3.50, "w_mat": 3.5,  "le_gc": 0.00, "nen": 6.0,  "dpc_mac_dinh": 0.0}
        }

        data_bang = db_7 if is_nui else db_6
        cfg = data_bang.get(cap)

        if cfg:
             
            w_dpc = 0.0
            if not is_nui and cap in ["I", "II"]:
                print("CHỌN CẤU TẠO DẢI PHÂN CÁCH GIỮA:")
                print("  1. Bê tông đúc sẵn (1.5m) | 2. Có trụ CT (2.5m) | 3. Trồng cỏ (4.0m)")
                pick_dpc = input(f"=> Chọn (1-3) [Mặc định {cfg['dpc_mac_dinh']}m]: ").strip()
                db_8 = {"1": 1.50, "2": 2.50, "3": 4.00}
                w_dpc = db_8.get(pick_dpc, cfg['dpc_mac_dinh'])
            
            w_lc_def = 0.5
            user_lc = input(f"=> Nhập bề rộng lan can mỗi bên [Mặc định {w_lc_def}m]: ").strip()
            w_lc = float(user_lc) if user_lc else w_lc_def

            # --- 2. TÍNH TOÁN LOGIC ---
            w_le_dat = 0.5
            w_duong = cfg['w_mat'] + w_dpc + 2 * (cfg['le_gc'] + w_le_dat)
            
            is_don_nguyen_tach = w_dpc >= 1.5
            if is_don_nguyen_tach:
                w_at_trong = 0.5 
                w_1_don_nguyen = (cfg['w_mat'] / 2) + cfg['le_gc'] + (2 * w_lc) + w_at_trong
                w_khoang_ho = w_dpc - (2 * w_lc)
                w_cau = (2 * w_1_don_nguyen) + w_khoang_ho
            else:
                w_cau = cfg['w_mat'] + w_dpc + 2 * (cfg['le_gc'] + w_lc)

            # --- 3. HIỂN THỊ KẾT QUẢ  ---
            print("\n" + "="*95)
            print(f"{'KẾT QUẢ BỐ TRÍ MẶT CẮT NGANG CẦU THEO TIÊU CHUẨN':^95}")
            print("="*95)
            print(f"TIÊU CHUẨN: TCVN 4054:2005 | Cấp thiết kế: {cap} | Vận tốc: {vtk} km/h")
            print("-" * 95)
            
            # Tiêu đề con cho bảng tổng hợp
            header_str = "BẢNG TỔNG HỢP MẶT CẮT NGANG ĐƯỜNG Ô TÔ"
           
            print(f"{header_str:^95}")
            print(f"+ Địa hình: {dia_hinh_display}")
            print(f"+ Cấp thiết kế: {cap}")
            print(f"+ Vtk: {vtk} km/h")
            print("-" * 95)

            # Sơ đồ Đường
            le_duong = f"--LỀ ĐẤT {w_le_dat}m--LGC {cfg['le_gc']}m--"
            phan_xe = f"--MD ({cfg['lan']//2}L) {cfg['w_mat']/2:.2f}m--"
            tim_duong = f"|DPC {w_dpc}m|" if w_dpc > 0 else "|TIM|"
            
            print(f" [ĐƯỜNG]: {le_duong}{phan_xe}{tim_duong}{phan_xe}{le_duong}")
            print(f" ==> TỔNG BỀ RỘNG NỀN ĐƯỜNG (Bn): {w_duong:.2f} m")
            print("-" * 95)

            # Sơ đồ Cầu
            if is_don_nguyen_tach:
                dn_trai = f"|LC {w_lc}|--LGC {cfg['le_gc']}m--{phan_xe}|AT {w_at_trong}|LC {w_lc}|"
                dn_phai = f"|LC {w_lc}|AT {w_at_trong}|{phan_xe}--LGC {cfg['le_gc']}m--|LC {w_lc}|"
                print(f" [CẦU ]: {dn_trai} < Hở {w_khoang_ho:.2f}m > {dn_phai}")
                print(f" ==> BỀ RỘNG 1 ĐƠN NGUYÊN: {w_1_don_nguyen:.2f} m")
                print(f" ==> KHOẢNG HỞ GIỮA 2 CẦU: {w_khoang_ho:.2f} m")
            else:
                le_cau = f"|LC {w_lc}|--LGC {cfg['le_gc']}m--"
                print(f" [CẦU ]: {le_cau}{phan_xe}{tim_duong}{phan_xe}{le_cau[::-1]}")
            
            print(f" ==> TỔNG BỀ RỘNG CẦU (Bc): {w_cau:.2f} m")
            print("="*95)
            # --- GHI CHÚ ---
            print(f"GHI CHÚ THIẾT KẾ (CẤP {cap}):")
            if cap in ["I", "II"]:
                print(" - Bố trí dải phân cách cứng để phân làn xe chạy tốc độ cao.")
                print(" - Cầu tách đơn nguyên giúp giảm nội lực nhiệt độ và dễ thi công lắp ghép.")
            else:
                print(" - Xe thô sơ và xe máy đi hỗn hợp trên phần lề gia cố (LGC).")
    elif loai == "Do thi":
        # --- 1. XÁC ĐỊNH LOẠI ĐƯỜNG ---
        ten_loai_duong = data.get("ten_loai")
        if not ten_loai_duong:
            cap_nguoi_dung = str(data.get("ten_cap", ""))
            cap_map = {"1": "Cao tốc đô thị", "2": "Phố chính chủ yếu", "3": "Phố chính thứ yếu", "4": "Phố gom", "5": "Phố nội bộ"}
            ten_loai_duong = cap_map.get(cap_nguoi_dung, "Đường đô thị")

        vtk = data.get("vtk", 60)
        print(f"\nĐỐI TƯỢNG: {ten_loai_duong.upper()} | Vtk = {vtk} km/h")
        
        # --- 2. CHỌN ĐIỀU KIỆN XÂY DỰNG ---
        dk_xd_label = "II"
        if ten_loai_duong != "Cao tốc đô thị":
            print("\nCHỌN ĐIỀU KIỆN XÂY DỰNG (TCVN 13592):")
            print("   1. Loại I: Thuận lợi | 2. Loại II: Trung bình | 3. Loại III: Khó khăn")
            sel_dk = input("=> Chọn (1-3) [Mặc định 2]: ").strip() or "2"
            dk_xd_label = {"1": "I", "2": "II", "3": "III"}.get(sel_dk, "II")

        # --- 3. TRA CỨU SỐ LÀN XE (BẢNG 10) ---
        db_bang_10 = {
            "Cao tốc đô thị":    {100: 3.75, 80: 3.75, 60: 3.50, "min": 4, "max": 10, "default": 6},
            "Phố chính chủ yếu": {80: 3.75, 60: 3.50, "min": 4, "max": 12, "default": 4},
            "Phố chính thứ yếu": {60: 3.50, "min": 4, "max": 8, "default": 4},
            "Phố gom":           {60: 3.50, 50: 3.25, "min": 2, "max": 6, "default": 2},
            "Phố nội bộ":        {50: 3.25, 40: 3.25, 30: 3.00, 20: 2.75, "min": 2, "max": 4, "default": 2}
        }
        row10 = db_bang_10.get(ten_loai_duong, {})
        w_1_lan = row10.get(vtk, 3.50)
        n_min, n_max = row10.get("min", 2), row10.get("max", 4)
        n_def = row10.get("default", n_min)
        
        while True:
            try:
                user_lan = input(f"\n=> Số làn xe thiết kế ({n_min}-{n_max}) [Mặc định {n_def}]: ").strip()
                n_lan = int(user_lan) if user_lan else n_def
                if n_min <= n_lan <= n_max: break
                print(f" [!] LỖI: Số làn phải từ {n_min} đến {n_max}.")
            except ValueError: print(" [!] LỖI: Vui lòng nhập số nguyên.")

        # --- 4. TRA CỨU DẢI PHÂN CÁCH (W_dpc) ---
        w_dpc = 0.0
        if ten_loai_duong == "Cao tốc đô thị":
            print("\nCHỌN CẤU TẠO DẢI PHÂN CÁCH (Bảng 1 - TCVN 5729):")
            print("   1. Có lớp phủ, không trụ | 2. Có lớp phủ, có trụ | 3. Không lớp phủ")
            sel_ct = input("=> Chọn (1-3) [Mặc định 1]: ").strip() or "1"
            db_bang_1_5729 = {
                "1": {120: 0.75, 100: 0.75, 80: 0.50, 60: 0.50},
                "2": {120: 1.50, 100: 1.50, 80: 1.50, 60: 1.50},
                "3": {120: 3.00, 100: 3.00, 80: 3.00, 60: 3.00}
            }
            w_dpc = db_bang_1_5729.get(sel_ct, {}).get(vtk, 0.50)
        else:
            db_bang_14 = {
                "Phố chính chủ yếu": {"I": 3.0, "II": 2.5, "III": 2.0},
                "Phố chính thứ yếu": {"I": 2.5, "II": 2.0, "III": 1.5},
                "Phố gom":           {"I": 2.0, "II": 1.5, "III": 1.0},
                "Phố nội bộ":        {"I": 0.0, "II": 0.0, "III": 0.0}
            }
            w_dpc_min = db_bang_14.get(ten_loai_duong, {}).get(dk_xd_label, 0.0)
            if w_dpc_min > 0:
                while True:
                    try:
                        user_dpc = input(f"\n=> Chiều rộng dải phân cách thiết kế [Mặc định tối thiểu {w_dpc_min}m]: ").strip()
                        w_dpc = float(user_dpc) if user_dpc else w_dpc_min
                        if w_dpc >= w_dpc_min: break
                        print(f" [!] LỖI: Tối thiểu {w_dpc_min}m.")
                    except ValueError: print(" [!] LỖI: Nhập số.")

        # --- 5. TRA CỨU HÈ ĐƯỜNG (BẢNG 15) ---
        w_he = 0.0
        if ten_loai_duong != "Cao tốc đô thị":
            db_bang_15 = {
                "Phố chính chủ yếu": {"I": 6.0, "II": 5.0, "III": 4.0},
                "Phố chính thứ yếu": {"I": 6.0, "II": 5.0, "III": 4.0},
                "Phố gom":           {"I": 4.5, "II": 4.0, "III": 3.0},
                "Phố nội bộ":        {"I": 3.0, "II": 2.5, "III": 2.0}
            }
            w_he_min = db_bang_15.get(ten_loai_duong, {}).get(dk_xd_label, 2.0)
            while True:
                try:
                    user_he = input(f"\n=> Chiều rộng hè đường thiết kế [Mặc định tối thiểu {w_he_min}m]: ").strip()
                    w_he = float(user_he) if user_he else w_he_min
                    if w_he >= w_he_min: break
                    print(f" [!] LỖI: Tối thiểu {w_he_min}m.")
                except ValueError: print(" [!] LỖI: Nhập số.")

        # --- 6. TRA CỨU DẢI TRỒNG CÂY (BẢNG 16) ---
        w_dtc = 0.0
        print("\nCHỌN HÌNH THỨC TRỒNG CÂY (Bảng 16):")
        print("   1. Thảm cỏ (1m) | 2. Cây 1 hàng (2m) | 3. Cây 2 hàng (5m)")
        sel_tc = input("=> Chọn (0-3) [Mặc định 1]: ").strip() or "1"
        w_dtc_min = { "1": 1.0, "2": 2.0, "3": 5.0, "0": 0.0}.get(sel_tc, 1.0)
        
        if w_dtc_min >= 0:
            while True:
                try:
                    user_dtc = input(f"=> Chiều rộng dải trồng cây [Mặc định {w_dtc_min}m]: ").strip()
                    w_dtc = float(user_dtc) if user_dtc else w_dtc_min
                    if w_dtc >= w_dtc_min: break
                    print(f" [!] LỖI: Tối thiểu {w_dtc_min}m.")
                except ValueError: print(" [!] LỖI: Nhập số.")

        # --- 7. TÍNH TOÁN & HIỂN THỊ ---
        w_lc_def = 0.5
        user_lc = input(f"\n=> Bề rộng lan can cầu mỗi bên [Mặc định {w_lc_def}m]: ").strip()
        w_lc = float(user_lc) if user_lc else w_lc_def
        
        w_mat_tong = n_lan * w_1_lan
        is_don_nguyen_tach = w_dpc > 1.5
        
        # Bn (Đường) - Cầu (Bc) logic
        w_duong = w_mat_tong + w_dpc + 2 * (w_he + w_dtc)
        if is_don_nguyen_tach:
            w_1_don_nguyen = (w_mat_tong / 2) + w_he + (2 * w_lc)
            w_khoang_ho = w_dpc - (2 * w_lc)
            w_cau = (2 * w_1_don_nguyen) + w_khoang_ho
        else:
            w_cau = w_mat_tong + w_dpc + 2 * (w_he + w_lc)

        # Hiển thị bảng tổng hợp
        print("\n" + "="*95)
        print(f"{'BẢNG TỔNG HỢP MẶT CẮT NGANG':^95}")
        print("="*95)

        le_duong = f"--HÈ {w_he}m--CÂY {w_dtc}m--"
        phan_xe_1_2 = f"--MD ({n_lan//2}L) {w_mat_tong/2:.2f}m--"
        tim_duong = f"|DPC {w_dpc}m|" if w_dpc > 0 else "|TIM|"
        
        print(f" [ĐƯỜNG]: {le_duong}{phan_xe_1_2}{tim_duong}{phan_xe_1_2}{le_duong}")
        print(f" ==> TỔNG BỀ RỘNG NỀN ĐƯỜNG (Bn): {w_duong:.2f} m")
        print("-" * 95)

        le_cau_bien = f"--HÈ {w_he}m--" 
        if is_don_nguyen_tach:
            dn_trai = f"|LC {w_lc}|{le_cau_bien}{phan_xe_1_2}|LC {w_lc}|"
            dn_phai = f"|LC {w_lc}|{phan_xe_1_2}{le_cau_bien}|LC {w_lc}|"
            print(f" [CẦU ]: {dn_trai} < Hở {w_khoang_ho:.2f}m > {dn_phai}")
            print(f" ==> BỀ RỘNG 1 ĐƠN NGUYÊN: {w_1_don_nguyen:.2f} m")
        else:
            lc_trai = f"|LC {w_lc}|{le_cau_bien}"
            lc_phai = f"{le_cau_bien}|LC {w_lc}|"
            print(f" [CẦU ]: {lc_trai}{phan_xe_1_2}{tim_duong}{phan_xe_1_2}{lc_phai}")
            
        print(f" ==> TỔNG BỀ RỘNG CHIẾM DỤNG CẦU (Bc): {w_cau:.2f} m")
        print("="*95)

if __name__ == "__main__":
    # Nhận dữ liệu đầu vào từ file 02
    try:
        data_input = YTHH.chon_cap_duong()
        thiet_ke_mcn_cau(data_input)
    except Exception as e:
        print(f"Đã xảy ra lỗi khi thực thi: {e}")