import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import joblib

# ==========================================
# 1. HÀM ĐỌC VÀ LÀM SẠCH DỮ LIỆU
# ==========================================
def load_data(file_path):
    # Đọc file với bảng mã utf-8 để tránh lỗi font tiếng Việt
    df = pd.read_csv(file_path, encoding='utf-8')
    
    # Xóa khoảng trắng thừa ở tiêu đề cột (nếu có)
    df.columns = [c.strip() for c in df.columns]
    
    # In ra để kiểm tra
    print(f"-> Đã đọc {len(df)} dòng dữ liệu.")
    
    # Lọc bỏ các cầu 1 nhịp (vì không có trụ để học)
    df = df[~df['Loai_Tru'].str.contains("Không có", na=False)]
    
    # Xóa các dòng bị trống ở các cột quan trọng
    df = df.dropna(subset=['Vtk (km/h)', 'B_Cau (m)', 'H_Tru (m)', 'Loai_Dam', 'Loai_Tru'])
    
    # Mã hóa cột 'Loai_Dam' (Chữ -> Số)
    le_dam = LabelEncoder()
    df['Loai_Dam_Encoded'] = le_dam.fit_transform(df['Loai_Dam'].astype(str))
    
    # Các cột đầu vào (Features)
    X = df[['Vtk (km/h)', 'B_Cau (m)', 'H_Tru (m)', 'Is_Urban', 'Is_River', 'Loai_Dam_Encoded']]
    # Cột kết quả (Label)
    y = df['Loai_Tru']
    
    return X, y, le_dam

# ==========================================
# 2. HUẤN LUYỆN MÔ HÌNH
# ==========================================
def train_model(file_path):
    try:
        X, y, le_dam = load_data(file_path)
        
        # Sử dụng Random Forest - Rất phù hợp với dữ liệu bảng kỹ thuật cầu
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X, y)
        
        # Lưu mô hình và bộ mã hóa để dùng cho Tool
        joblib.dump(model, 'model_tru_cau.pkl')
        joblib.dump(le_dam, 'encoder_dam.pkl')
        
        print("=> Chúc mừng! Mô hình đã học xong và lưu vào file 'model_tru_cau.pkl'")
        
    except Exception as e:
        print(f"Lỗi khi huấn luyện: {e}")

# ==========================================
# 3. HÀM DỰ ĐOÁN (DÙNG TRONG TOOL)
# ==========================================
def predict_bridge_pier(vtk, b_cau, h_tru, is_urban, is_river, loai_dam_text):
    try:
        model = joblib.load('model_tru_cau.pkl')
        le_dam = joblib.load('encoder_dam.pkl')
        
        # Chuyển dầm từ chữ sang số AI đã học
        try:
            dam_encoded = le_dam.transform([loai_dam_text])[0]
        except:
            # Nếu dầm mới chưa có trong data, dùng giá trị phổ biến nhất (mặc định 0)
            dam_encoded = 0
            
        input_data = [[vtk, b_cau, h_tru, is_urban, is_river, dam_encoded]]
        res = model.predict(input_data)[0]
        prob = np.max(model.predict_proba(input_data)) * 100
        
        return res, prob
    except:
        return "Chưa có mô hình. Hãy chạy train trước!", 0

# ==========================================
# CHƯƠNG TRÌNH CHÍNH
# ==========================================
if __name__ == "__main__":
    # ĐƯỜNG DẪN FILE (Thay đổi nếu cần)
    FILE_CSV = r'C:\Users\admin\DC\ACCDocs\Chuongdnd\25-26-SauDaiHoc-ThS\Project Files\02-DATN-Master\07-VSC\Phan loai Tru.csv'
    
    # Bước 1: Huấn luyện
    train_model(FILE_CSV)
    
    # Bước 2: Dự đoán thử 1 trường hợp
    # Ví dụ: Vtk=80, B=12m, H=6.5m, Ngoại ô=0, Dưới sông=1, Dầm I
    loai_tru, do_tin_cay = predict_bridge_pier(80, 12, 6.5, 0, 1, 'Dầm I')
    
    print("-" * 30)
    print(f"KẾT QUẢ DỰ ĐOÁN AI:")
    print(f"Dạng trụ nên dùng: {loai_tru}")
    print(f"Độ tin cậy: {do_tin_cay:.2f}%")