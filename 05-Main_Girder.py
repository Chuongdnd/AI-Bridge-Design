import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

# =========================================================
# MODULE 1: HUẤN LUYỆN AI (Học từ dữ liệu thực tế)
# =========================================================
# =========================================================
# MODULE 1: HUẤN LUYỆN AI (Đã cập nhật đồng bộ biến)
# =========================================================
def train_bridge_ai_system(file_path):
    if not os.path.exists(file_path):
        print(f"Lỗi: Không tìm thấy file tại {file_path}")
        return None
    try:
        # Đọc dữ liệu từ file Excel
        df = pd.read_excel(file_path, sheet_name='MainSpan')
        # Xóa khoảng trắng thừa trong tên cột để tránh lỗi KeyError
        df.columns = [str(c).strip() for c in df.columns]
        
        # Nhận diện các cột quan trọng
        col_tk = next((c for c in df.columns if 'tĩnh không B' in c), None)
        col_len = next((c for c in df.columns if 'Chiều dài dầm' in c), None)
        col_type = next((c for c in df.columns if 'Loại dầm' in c), None)
        col_bcau = next((c for c in df.columns if 'B_cầu' in c), None)
        col_dist = next((c for c in df.columns if 'K/c dầm' in c), None)
        col_h = next((c for c in df.columns if 'H_dầm' in c), None)

        # Chuyển đổi dữ liệu sang dạng số an toàn
        for col in [col_tk, col_len, col_dist, col_bcau, col_h]:
            if col: df[col] = pd.to_numeric(df[col], errors='coerce')

        # Làm sạch dữ liệu: Loại bỏ dòng trống ở các cột quyết định
        df_clean = df.dropna(subset=[col_tk, col_len, col_type, col_h]).copy()
        
        # Mã hóa nhãn (Label Encoding) - Giữ nguyên logic logic
        le_env = LabelEncoder()
        # Tạo cột môi trường giả định nếu dữ liệu thực tế bị thiếu để tránh lỗi fit
        env_data = df_clean['Môi trường'].astype(str) if 'Môi trường' in df_clean.columns else pd.Series(['Vượt sông']*len(df_clean))
        df_clean['Env_Enc'] = le_env.fit_transform(env_data)
        
        le_type = LabelEncoder()
        df_clean['Type_Enc'] = le_type.fit_transform(df_clean[col_type])

        # Huấn luyện các mô hình Random Forest (Giữ nguyên tham số n=100, rs=42)
        X = df_clean[[col_tk, 'Env_Enc']]
        
        # 1. Dự đoán loại dầm
        m_type = RandomForestClassifier(n_estimators=100, random_state=42).fit(X, df_clean['Type_Enc'])
        # 2. Dự đoán chiều dài dầm
        m_len = RandomForestRegressor(n_estimators=100, random_state=42).fit(X, df_clean[col_len])
        # 3. Dự đoán chiều cao dầm (Key trả về là 'h' để đồng bộ hàm predict)
        m_height = RandomForestRegressor(n_estimators=100, random_state=42).fit(df_clean[['Type_Enc', col_len]], df_clean[col_h])
        # 4. Dự đoán khoảng cách dầm
        m_dist = RandomForestRegressor(n_estimators=100, random_state=42).fit(df_clean[['Type_Enc', col_bcau]], df_clean[col_dist].fillna(1.0))

        # Trả về Dictionary với tên Key đã được chuẩn hóa cho file 05
        return {
            'type': m_type, 
            'len': m_len, 
            'h': m_height,    # Đã đổi từ 'height' thành 'h' để khớp với logic predict_main_span
            'dist': m_dist, 
            'le_env': le_env, 
            'le_type': le_type, 
            'count': len(df_clean)
        }
    except Exception as e:
        print(f"Lỗi Module Huấn luyện: {e}")
        return None

# =========================================================
# MODULE 2: LOGIC XÁC ĐỊNH THÔNG SỐ NHỊP VÀ PHÂN CHIA NHỊP
# =========================================================
def predict_main_span(b_tk, goc, b_cau, env, models, L_cau_tong=None):
    """
    Cập nhật đồng bộ:
    - Lấy L_cau_tong từ kết quả trắc dọc (File 02)
    - So sánh PA kinh tế Super-T 38.2m
    - Sử dụng models['h'] thay cho models['height'] theo hàm train mới
    """
    # 1. Mã hóa môi trường đầu vào
    try:
        env_enc = models['le_env'].transform([env])[0]
    except:
        env_enc = 0

    # 2. Dự đoán Loại dầm và Chiều dài AI ban đầu
    t_idx = models['type'].predict([[b_tk, env_enc]])[0]
    t_f = models['le_type'].inverse_transform([t_idx])[0]
    
    # Logic nghiệp vụ: Đô thị tĩnh không hẹp ưu tiên T ngược
    if env == "Đô thị" and b_tk <= 20:
        t_f = "T ngược"

    # 3. Dự đoán Chiều dài dầm vừa khít tĩnh không (L)
    l_ai = models['len'].predict([[b_tk, env_enc]])[0]
    l_min = (b_tk / np.sin(np.radians(goc))) + 2.0 # Khống chế hình học tối thiểu
    
    # Quy đổi về chiều dài định hình phổ biến cho nhịp chính
    std_lengths = [15, 18, 21, 24, 25, 30, 33, 38.2, 40]
    l_f_ai = max(l_ai, l_min)
    l_f_ai = min(std_lengths, key=lambda x: abs(x - l_f_ai))

    # --- BỔ SUNG LOGIC PHÂN CHIA NHỊP VÀ SO SÁNH KINH TẾ ---
    analysis_note = ""
    n_nhip_final = 1
    
    if L_cau_tong and L_cau_tong > 0:
        # 1. Phương án A: Theo dầm AI đề xuất (Dầm I, T...)
        n_ai = int(np.ceil(L_cau_tong / l_f_ai))
        l_thuc_ai = round(L_cau_tong / n_ai, 2)
        
        # 2. Phương án B: Theo dầm Super-T (Ưu tiên giảm số hàng trụ)
        l_spt_dinh_hinh = 38.2
        # Sử dụng floor để tìm số nhịp ít nhất có thể
        n_spt = int(np.floor(L_cau_tong / l_spt_dinh_hinh))
        if n_spt < 1: n_spt = 1
        
        l_thuc_spt = round(L_cau_tong / n_spt, 2)
        
        # KIỂM TRA ĐIỀU KIỆN KINH TẾ:
        # Nếu dùng Super-T mà giảm được số nhịp (n_spt < n_ai) 
        # và chiều dài dầm thực tế không vượt quá giới hạn cho phép (40m)
        if n_spt < n_ai and l_thuc_spt <= 40.0:
            analysis_note = (f"Tối ưu kinh tế: Giảm từ {n_ai} nhịp xuống {n_spt} nhịp nhờ dùng dầm Super-T "
                             f"(L thực tế = {l_thuc_spt}m). Tiết kiệm {n_ai - n_spt} hàng trụ.")
            l_f = l_thuc_spt
            t_f = "Super-T"
            n_nhip_final = n_spt
        else:
            # Nếu không giảm được trụ hoặc dầm vượt quá 40m, giữ nguyên PA ban đầu
            analysis_note = f"Phương án tối ưu: Chia cầu thành {n_ai} nhịp dầm {t_f}."
            l_f = l_thuc_ai
            n_nhip_final = n_ai
    else:
        l_f = l_f_ai
        analysis_note = "Dự báo thông số cho 1 nhịp đơn."

    # 4. Dự đoán Chiều cao dầm (H) - Sử dụng 'h' thay cho 'height'
    t_enc = models['le_type'].transform([t_f])[0]
    h_ai = models['h'].predict([[t_enc, l_f]])[0] # models['h'] đã được khớp với hàm train
    
    # Khống chế cấu tạo H >= 1/18 - 1/20 L (ngoại trừ T ngược)
    h_f = h_ai if "t ngược" in t_f.lower() else max(h_ai, round(l_f/20, 2))

    # 5. Dự đoán Số lượng dầm và Khoảng cách (S) trên Mặt cắt ngang
    s_f = models['dist'].predict([[t_enc, b_cau]])[0]
    n_dam = int(np.floor(b_cau / s_f)) + 1
    oh = round((b_cau - (n_dam - 1) * s_f) / 2, 2)
    
    if oh >= 0.8 * s_f:
        n_dam += 1
        oh = round((b_cau - (n_dam - 1) * s_f) / 2, 2)

    return {
        "loai_dam": t_f,
        "chieu_dai": l_f,
        "tong_so_nhip": n_nhip_final,
        "chieu_cao": round(h_f, 2),
        "so_luong_dam_mcn": n_dam,
        "khoang_cach_dam": round(s_f, 2),
        "overhang": oh,
        "ghi_chu_ai": analysis_note
    }

# =========================================================
# CHƯƠNG TRÌNH CHÍNH (Đã cập nhật tính năng chia nhịp)
# =========================================================
def run_bridge_advisor_v2():
    print("="*65)
    print("   HỆ THỐNG AI TƯ VẤN THIẾT KẾ KẾT CẤU & PHÂN CHIA NHỊP")
    print("="*65)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    xlsx_path = os.path.join(current_dir, 'Girder.xlsx')
    
    # 1. Huấn luyện hệ thống
    models = train_bridge_ai_system(xlsx_path)
    if not models: 
        print(f"Lỗi: Không tìm thấy file {xlsx_path} hoặc dữ liệu không hợp lệ.")
        return

    print(f"[*] Đã huấn luyện xong từ {models['count']} dự án mẫu.")

    try:
        # 2. Nhập thông số đầu vào (Mô phỏng dữ liệu từ Tab 1 & Tab 2)
        b_tk = float(input("\n1. Nhập tĩnh không nhịp chính B (m): "))
        l_cau_tong = input("2. Nhập tổng chiều dài cầu (m) [Bỏ trống nếu chỉ tính 1 nhịp]: ")
        l_cau_tong = float(l_cau_tong) if l_cau_tong else None
        
        goc = float(input("3. Nhập góc giao chéo (độ) [Mặc định 90]: ") or 90)
        b_cau = float(input("4. Nhập bề rộng mặt cắt ngang cầu Bc (m): "))
        
        print("5. Chọn môi trường xây dựng:")
        print("   1. Vượt sông / Ngoài đô thị")
        print("   2. Trong đô thị / Cầu vượt nút giao")
        env_choice = input("=> Chọn (1/2): ")
        env = "Đô thị" if env_choice == "2" else "Vượt sông"

        # 3. Gọi hàm dự báo AI đã được tích hợp logic chia nhịp
        res = predict_main_span(b_tk, goc, b_cau, env, models, L_cau_tong=l_cau_tong)

        # 4. Xuất kết quả đề xuất
        print("\n" + "*"*25 + " KẾT QUẢ TƯ VẤN TỐI ƯU " + "*"*25)
        print(f"  + Loại dầm kiến nghị:     {res['loai_dam'].upper()}")
        print(f"  + Số lượng nhịp:          {res['tong_so_nhip']} nhịp")
        print(f"  + Chiều dài mỗi nhịp (L): {res['chieu_dai']} m")
        print(f"  + Chiều cao dầm (H):      {res['chieu_cao']} m")
        
        print(f"\n  --- Thông số mặt cắt ngang ---")
        print(f"  + Số lượng dầm trên MCN:  {res['so_luong_dam_mcn']} dầm")
        print(f"  + Khoảng cách dầm (S):    {res['khoang_cach_dam']} m")
        print(f"  + Khoảng nhô (Overhang):  {res['overhang']} m")
        
        print(f"\n  => ĐÁNH GIÁ AI: {res['ghi_chu_ai']}")
        print("*"*73)

    except ValueError:
        print("Lỗi: Vui lòng nhập thông số dạng số chính xác.")
    except Exception as e:
        print(f"Đã xảy ra lỗi hệ thống: {e}")

if __name__ == "__main__":
    run_bridge_advisor_v2()