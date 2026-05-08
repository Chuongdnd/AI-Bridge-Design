import streamlit as st
import pandas as pd
import os
import importlib
import sys

# Thiết lập giao diện rộng
st.set_page_config(page_title="AI Bridge Design", layout="wide")

# --- KẾT NỐI CÁC MODULE ---
try:
    TK = importlib.import_module("01-Tinh_khong")
    YTHH = importlib.import_module("02-Yeuto_Hinhhoc")
    MCN = importlib.import_module("03-MatCatNgang")
    GRD = importlib.import_module("05-Main_Girder")
except Exception as e:
    st.error(f"Lỗi kết nối Module: {e}. Hãy đảm bảo các file .py nằm cùng thư mục.")

st.title("🏗️ Hệ thống Tư vấn Thiết kế Cầu tự động")
st.markdown("---")

# Tạo các Tab cho từng giai đoạn thiết kế
tab1, tab2, tab3 = st.tabs(["🌊 Tĩnh không & Cấp đường", "🛣️ Mặt cắt ngang", "🤖 AI Dự báo Nhịp"])

# Biến lưu trữ kết quả giữa các Tab (Sử dụng session_state của Streamlit)
if 'design_data' not in st.session_state:
    st.session_state.design_data = {}

# --- TAB 1: TĨNH KHÔNG ---
with tab1:
    st.header("1. Thông số Tĩnh không & Cấp đường")
    col1, col2 = st.columns(2)
    
    with col1:
        loai_cau = st.radio("Loại cầu vượt:", ["Vượt sông", "Vượt đường bộ"])
        b_tk_input = st.number_input("Khẩu độ ngang yêu cầu (m):", value=20.0)
        h_tk_input = st.number_input("Tĩnh không đứng yêu cầu (m):", value=7.0)
        
    with col2:
        loai_duong = st.selectbox("Đối tượng đường trên cầu:", ["Cao tốc", "Đường ô tô", "Đường đô thị"])
        v_tk = st.select_slider("Vận tốc thiết kế (km/h):", options=[40, 60, 80, 100, 120])
        
    if st.button("Xác nhận thông số cơ bản"):
        st.session_state.design_data['b_tk'] = b_tk_input
        st.session_state.design_data['h_tk'] = h_tk_input
        st.session_state.design_data['vtk'] = v_tk
        st.session_state.design_data['loai_duong'] = loai_duong
        st.success("Đã lưu thông số cơ bản!")

# --- TAB 2: MẶT CẮT NGANG ---
with tab2:
    st.header("2. Thiết kế Mặt cắt ngang")
    if 'vtk' in st.session_state.design_data:
        n_lan = st.number_input("Số làn xe:", min_value=2, max_value=10, value=4)
        w_lan = st.number_input("Bề rộng 1 làn xe (m):", value=3.75)
        
        # Giả lập tính toán Bc nhanh
        bc_tinh_toan = (n_lan * w_lan) + 2.0 # (Cộng dải an toàn, lan can)
        st.info(f"Bề rộng cầu dự kiến (Bc): {bc_tinh_toan} m")
        
        if st.button("Chốt Mặt cắt ngang"):
            st.session_state.design_data['bc'] = bc_tinh_toan
            st.success("Đã xác định bề rộng cầu!")
    else:
        st.warning("Vui lòng hoàn thành Tab 1 trước.")

# --- TAB 3: DỰ BÁO AI ---
with tab3:
    st.header("3. AI Dự báo Kết cấu nhịp chính")
    if 'bc' in st.session_state.design_data:
        # Đường dẫn file Excel
        current_dir = os.path.dirname(os.path.abspath(__file__))
        xlsx_path = os.path.join(current_dir, 'Girder.xlsx')
        
        if st.button("Chạy mô hình AI Dự đoán"):
            with st.spinner('Đang học dữ liệu và tính toán...'):
                models = GRD.train_bridge_ai_system(xlsx_path)
                if models:
                    env = "Đô thị" if st.session_state.design_data['loai_duong'] == "Đường đô thị" else "Vượt sông"
                    res = GRD.predict_main_span(
                        st.session_state.design_data['b_tk'], 
                        90, 
                        st.session_state.design_data['bc'], 
                        env, 
                        models
                    )
                    
                    # Hiển thị kết quả trực quan
                    st.success("Dự báo hoàn tất!")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Loại dầm đề xuất", res['loai_dam'].upper())
                    c2.metric("Chiều dài nhịp", f"{res['chieu_dai']} m")
                    c3.metric("Số lượng dầm", f"{res['so_luong']} thanh")
                    
                    st.write("---")
                    st.subheader("Chi tiết cấu tạo dầm")
                    st.json(res) # Hiển thị full thông số dạng JSON cho chuyên gia
                else:
                    st.error("Không tìm thấy file Girder.xlsx!")
    else:
        st.warning("Vui lòng hoàn thành thiết kế Mặt cắt ngang ở Tab 2.")