import joblib
import numpy as np

# ==========================================
# HÀM DỰ ĐOÁN (GIỮ NGUYÊN NHƯ CŨ)
# ==========================================
def predict_bridge_pier(vtk, b_cau, h_tru, is_urban, is_river, loai_dam_text):
    try:
        # Tải mô hình và bộ mã hóa đã huấn luyện trước đó
        model = joblib.load('model_tru_cau.pkl')
        le_dam = joblib.load('encoder_dam.pkl')
        
        # Chuyển loại dầm sang số
        try:
            dam_encoded = le_dam.transform([loai_dam_text])[0]
        except:
            dam_encoded = 0 # Mặc định nếu dầm lạ
            
        input_data = [[vtk, b_cau, h_tru, is_urban, is_river, dam_encoded]]
        res = model.predict(input_data)[0]
        prob = np.max(model.predict_proba(input_data)) * 100
        
        return res, prob
    except Exception as e:
        return f"Lỗi: {e}. Hãy đảm bảo bạn đã chạy file Train trước!", 0

# ==========================================
# GIAO DIỆN NHẬP LIỆU (USER INTERFACE)
# ==========================================
def main_interface():
    print("\n" + "="*50)
    print("   CÔNG CỤ HỖ TRỢ LỰA CHỌN TRỤ CẦU (AI ADVISOR)")
    print("="*50)
    print("Vui lòng nhập các thông số kỹ thuật bên dưới:")

    try:
        # 1. Nhập các thông số số thực
        vtk = float(input("1. Vận tốc thiết kế (km/h): "))
        b_cau = float(input("2. Bề rộng mặt cầu (m): "))
        h_tru = float(input("3. Chiều cao trụ dự kiến (m): "))
        
        # 2. Nhập các thông số lựa chọn Yes/No
        print("\n--- Điều kiện biên ---")
        urban_input = input("4. Cầu nằm trong đô thị? (y/n): ").lower()
        is_urban = 1 if urban_input == 'y' else 0
        
        river_input = input("5. Trụ nằm dưới nước/vượt sông? (y/n): ").lower()
        is_river = 1 if river_input == 'y' else 0
        
        # 3. Nhập loại dầm (phải khớp với các loại dầm trong Excel như: Dầm I, T ngược, I33...)
        print("\n--- Kết cấu nhịp ---")
        loai_dam = input("6. Nhập loại kết cấu dầm (VD: Dầm I, T ngược, Super-T): ")

        # Thực hiện dự đoán
        result, confidence = predict_bridge_pier(vtk, b_cau, h_tru, is_urban, is_river, loai_dam)

        # Hiển thị kết quả
        print("\n" + "*"*50)
        print(f"KẾT QUẢ TƯ VẤN TỪ AI:")
        print(f">> Dạng trụ đề xuất: {result.upper()}")
        print(f">> Độ tin cậy: {confidence:.2f}%")
        print("*"*50)
        
        if confidence < 70:
            print("Lưu ý: Độ tin cậy thấp, bạn nên tham khảo thêm ý kiến chuyên gia.")
            
    except ValueError:
        print("\n[LỖI] Vui lòng chỉ nhập số cho các thông số kỹ thuật!")

if __name__ == "__main__":
    main_interface()