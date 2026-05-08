import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

# =========================================================
# MODULE 1: HUẤN LUYỆN AI (Học từ dữ liệu thực tế)
# =========================================================
def train_bridge_ai_system(file_path):
    try:
        # Đọc dữ liệu từ file Excel
        df = pd.read_excel(file_path, sheet_name='MainSpan')
        df.columns = [str(c).strip() for c in df.columns]
        
        # Nhận diện các cột quan trọng
        col_tk = next((c for c in df.columns if 'tĩnh không B' in c), None)
        col_len = next((c for c in df.columns if 'Chiều dài dầm' in c), None)
        col_type = next((c for c in df.columns if 'Loại dầm' in c), None)
        col_bcau = next((c for c in df.columns if 'B_cầu' in c), None)
        col_dist = next((c for c in df.columns if 'K/c dầm' in c), None)
        col_h = next((c for c in df.columns if 'H_dầm' in c), None)

        # Chuyển đổi dữ liệu sang dạng số
        for col in [col_tk, col_len, col_dist, col_bcau, col_h]:
            if col: df[col] = pd.to_numeric(df[col], errors='coerce')

        # Làm sạch dữ liệu
        df_clean = df.dropna(subset=[col_tk, col_len, col_type, col_h]).copy()
        
        # Mã hóa nhãn (Label Encoding) cho Môi trường và Loại dầm
        le_env = LabelEncoder()
        df_clean['Env_Enc'] = le_env.fit_transform(df_clean['Môi trường'].astype(str))
        le_type = LabelEncoder()
        df_clean['Type_Enc'] = le_type.fit_transform(df_clean[col_type])

        # Huấn luyện các mô hình Random Forest
        X = df_clean[[col_tk, 'Env_Enc']]
        # 1. Dự đoán loại dầm (Phân loại)
        m_type = RandomForestClassifier(n_estimators=100, random_state=42).fit(X, df_clean['Type_Enc'])
        # 2. Dự đoán chiều dài dầm (Hồi quy)
        m_len = RandomForestRegressor(n_estimators=100, random_state=42).fit(X, df_clean[col_len])
        # 3. Dự đoán chiều cao dầm dựa trên loại và chiều dài
        m_height = RandomForestRegressor(n_estimators=100, random_state=42).fit(df_clean[['Type_Enc', col_len]], df_clean[col_h])
        # 4. Dự đoán khoảng cách dầm dựa trên loại và bề rộng cầu
        m_dist = RandomForestRegressor(n_estimators=100, random_state=42).fit(df_clean[['Type_Enc', col_bcau]], df_clean[col_dist].fillna(1.0))

        return {
            'type': m_type, 'len': m_len, 'height': m_height, 'dist': m_dist, 
            'le_env': le_env, 'le_type': le_type, 'count': len(df_clean)
        }
    except Exception as e:
        print(f"Lỗi Module Huấn luyện: {e}")
        return None

# =========================================================
# MODULE 2: LOGIC XÁC ĐỊNH THÔNG SỐ NHỊP CHÍNH
# =========================================================
def predict_main_span(b_tk, goc, b_cau, env, models):
    # 1. Mã hóa môi trường đầu vào
    try:
        env_enc = models['le_env'].transform([env])[0]
    except:
        env_enc = 0

    # 2. Dự đoán Loại dầm
    t_idx = models['type'].predict([[b_tk, env_enc]])[0]
    t_f = models['le_type'].inverse_transform([t_idx])[0]
    
    # Ưu tiên logic nghiệp vụ: Đô thị tĩnh không hẹp dùng T ngược
    if env == "Đô thị" and b_tk <= 20:
        t_f = "T ngược"

    # 3. Dự đoán Chiều dài dầm (L)
    l_ai = models['len'].predict([[b_tk, env_enc]])[0]
    l_min = (b_tk / np.sin(np.radians(goc))) + 2.0 # Khống chế hình học tối thiểu
    
    # Quy đổi về chiều dài định hình phổ biến
    std_lengths = [15, 18, 21, 24, 25, 30, 33, 38.2, 40]
    l_f = max(l_ai, l_min)
    l_f = min(std_lengths, key=lambda x: abs(x - l_f)) if l_f <= 40 else round(l_f, 1)

    # 4. Dự đoán Chiều cao dầm (H)
    t_enc = models['le_type'].transform([t_f])[0]
    h_ai = models['height'].predict([[t_enc, l_f]])[0]
    # Khống chế cấu tạo H >= 1/18 - 1/20 L (ngoại trừ T ngược)
    h_f = h_ai if "t ngược" in t_f.lower() else max(h_ai, round(l_f/20, 2))

    # 5. Dự đoán Số lượng dầm và Khoảng cách (S)
    s_f = models['dist'].predict([[t_enc, b_cau]])[0]
    n_dam = int(np.floor(b_cau / s_f)) + 1
    # Tính toán khoảng nhô cánh dầm (overhang)
    oh = round((b_cau - (n_dam - 1) * s_f) / 2, 2)
    
    # Nếu oh quá lớn, tăng thêm 1 dầm để phân bổ lại
    if oh >= 0.8 * s_f:
        n_dam += 1
        oh = round((b_cau - (n_dam - 1) * s_f) / 2, 2)

    return {
        "loai_dam": t_f,
        "chieu_dai": l_f,
        "chieu_cao": round(h_f, 2),
        "so_luong": n_dam,
        "khoang_cach": round(s_f, 2),
        "overhang": oh
    }

# =========================================================
# CHƯƠNG TRÌNH CHÍNH
# =========================================================
def run_bridge_advisor_v2():
    print("="*60)
    print("   HỆ THỐNG AI TƯ VẤN THIẾT KẾ KẾT CẤU NHỊP CHÍNH")
    print("="*60)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    xlsx_path = os.path.join(current_dir, 'Girder.xlsx')
    
    # Kiểm tra file dữ liệu
    if not os.path.exists(xlsx_path):
        print(f"Lỗi: Không tìm thấy file dữ liệu tại {xlsx_path}")
        return

    models = train_bridge_ai_system(xlsx_path)
    if not models: return

    print(f"[*] Đã huấn luyện xong từ {models['count']} dự án mẫu.")

    try:
        # Nhập thông số đầu vào
        b_tk = float(input("\n1. Nhập tĩnh không nhịp chính B (m): "))
        goc = float(input("2. Nhập góc giao chéo (độ) [Mặc định 90]: ") or 90)
        b_cau = float(input("3. Nhập bề rộng mặt cắt ngang cầu Bc (m): "))
        print("4. Chọn môi trường xây dựng:")
        print("   1. Vượt sông / Ngoài đô thị")
        print("   2. Trong đô thị / Cầu vượt nút giao")
        env_choice = input("=> Chọn (1/2): ")
        env = "Đô thị" if env_choice == "2" else "Vượt sông"

        # Dự đoán
        res = predict_main_span(b_tk, goc, b_cau, env, models)

        # Xuất kết quả
        print("\n" + "*"*25 + " KẾT QUẢ ĐỀ XUẤT " + "*"*25)
        print(f"  + Loại dầm kiến nghị:    {res['loai_dam'].upper()}")
        print(f"  + Chiều dài dầm (L):     {res['chieu_dai']} m")
        print(f"  + Chiều cao dầm (H):     {res['chieu_cao']} m")
        print(f"  + Số lượng dầm trên MCN: {res['so_luong']} dầm")
        print(f"  + Khoảng cách dầm (S):   {res['khoang_cach']} m")
        print(f"  + Khoảng nhô (Overhang): {res['overhang']} m")
        print("*"*67)

    except ValueError:
        print("Lỗi: Vui lòng nhập thông số dạng số chính xác.")
    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")

if __name__ == "__main__":
    run_bridge_advisor_v2()