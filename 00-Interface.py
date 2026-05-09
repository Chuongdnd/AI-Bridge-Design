import streamlit as st
import pandas as pd
import os
import importlib

# --- THIẾT LẬP TRANG ---
st.set_page_config(page_title="Hệ thống Thiết kế Cầu AI", layout="wide", page_icon="🏗️")
# --- 2. CHÈN NHẠC NỀN VÀO SIDEBAR  ---
with st.sidebar:
    st.title("🎵 Nhạc nền")
    # Đường dẫn file nhạc trên GitHub của bạn
    music_path = "Sounds/Trungtv.mp3" 
    
    if os.path.exists(music_path):
        # Sử dụng lệnh tiêu chuẩn, autoplay=True sẽ phát ngay khi có tương tác
        st.audio(music_path, loop=True, autoplay=True)
        st.caption("Đang phát: Trungtv.mp3")
    else:
        st.error(f"⚠️ Không tìm thấy file: {music_path}")
# --- KẾT NỐI MODULES ---
try:
    # Lưu ý: Đảm bảo các file này đã đổi tên trên GitHub, bỏ số đầu (vd: Tinh_khong.py)
    TK = importlib.import_module("01-Tinh_khong")
    YTHH = importlib.import_module("02-Yeuto_Hinhhoc")
    MCN = importlib.import_module("03-MatCatNgang")
    GRD = importlib.import_module("05-Main_Girder")
except Exception as e:
    st.error(f"⚠️ Lỗi kết nối Module: {e}. Kiểm tra lại tên file trên GitHub.")

# --- KHỞI TẠO SESSION STATE ---
if 'design_data' not in st.session_state:
    st.session_state.design_data = {
        'khau_do_ngang': 20.0,
        'cao_do_day_dam': 0.0,
        'bc': 12.0,
        'loai_duong': "O to",
        'vtk': 60
    }

st.title("🏗️ Hệ thống Tư vấn Thiết kế Cầu tự động (AI)")

# Kiểm tra file ảnh trước khi hiển thị để tránh lỗi Crash
if os.path.exists("Images/test1.jpg"):
    st.image("Images/test1.jpg", caption="Ảnh minh họa dự án")
else:
    st.warning("📸 Chưa tìm thấy file ảnh Images/test1.jpg trên GitHub.")

st.info("Quy trình: Tĩnh không ➔ Cấp đường ➔ Mặt cắt ngang ➔ Dự báo dầm bằng AI")

tab1, tab2, tab3 = st.tabs(["🌊 1. Tĩnh không", "🛣️ 2. Hình học & MCN", "🤖 3. AI Dự báo Nhịp"])

# ==========================================
# TAB 1: TĨNH KHÔNG
# ==========================================
with tab1:
    st.subheader("📋 Nhập thông số Tĩnh không")
    
    col_in1, col_in2 = st.columns(2)
    
    with col_in1:
        loai_c = st.radio("Chọn loại công trình:", ["Vượt sông", "Vượt đường bộ"])
        
        if loai_c == "Vượt sông":
            mien = st.selectbox("Chọn miền:", ["1", "2"], format_func=lambda x: "Miền Bắc" if x=="1" else "Miền Nam")
            cap_s = st.selectbox("Chọn cấp sông:", ["1", "2", "3", "4", "5", "6"], 
                                format_func=lambda x: f"Cấp {['I','II','III','IV','V','VI'][int(x)-1]}")
            loai_h = st.selectbox("Loại hình thủy đạo:", ["1", "2"], format_func=lambda x: "Kênh" if x=="1" else "Sông")
        else:
            loai_v = st.selectbox("Loại đường bị vượt:", ["Cao tốc", "Đường ô tô"])
            cap_o = "1"
            if loai_v == "Đường ô tô":
                cap_o = st.selectbox("Cấp đường bị vượt:", ["1", "2"], format_func=lambda x: "Cấp I, II, III" if x=="1" else "Các cấp còn lại")

    with col_in2:
        if loai_c == "Vượt sông":
            h1 = st.number_input("Cao độ mực nước H1% (m):", value=1.0, step=0.1)
            h5 = st.number_input("Cao độ mực nước H5% (m):", value=2.0, step=0.1)
        else:
            st.info("💡 Đối với cầu vượt đường bộ, cao độ đáy dầm phụ thuộc vào cao độ trắc dọc mặt đường bị vượt + H.")

    if st.button("🔍 Tra cứu kết quả V5.0"):
        res = TK.tra_cuu_tinh_khong_bridge(
            loai_cau=loai_c, mien=mien if loai_c=="Vượt sông" else None,
            cap_num=cap_s if loai_c=="Vượt sông" else None,
            loai_hinh=loai_h if loai_c=="Vượt sông" else None,
            h1=h1 if loai_c=="Vượt sông" else 0,
            h5=h5 if loai_c=="Vượt sông" else 0,
            loai_duong_vuot=loai_v if loai_c=="Vượt đường bộ" else None,
            cap_oto=cap_o if loai_c=="Vượt đường bộ" else None
        )
        
        if res["status"] == "success":
            st.divider()
            st.subheader(f"📊 Kết quả: {res['label']}")
            
            # Hiển thị Metrics (Các chỉ số quan trọng)
            m1, m2, m3 = st.columns(3)
            m1.metric("Khẩu độ ngang (B)", f"{res['B']} m")
            m2.metric("Chiều cao tĩnh không (H)", f"{res['H']} m")
            
            if loai_c == "Vượt sông":
                m3.metric("Đáy dầm tối thiểu", f"{res['day_dam']} m")
                
                # Bảng chi tiết
                df_res = pd.DataFrame({
                    "Hạng mục": ["Khẩu độ ngang thông thuyền (B)", "Chiều cao tĩnh không (H)", "Mực nước thông thuyền (MNTT)", "Cao độ đáy dầm tối thiểu"],
                    "Giá trị": [f"{res['B']} m", f"{res['H']} m", f"{res['MNTT']:.2f} m", f"{res['day_dam']} m"]
                })
                st.table(df_res)
            else:
                m3.metric("Yêu cầu H", f"H >= {res['H']} m")
            
            # Lưu vào session_state để các Tab sau sử dụng
            st.session_state.design_data['khau_do_ngang'] = res['B'] if isinstance(res['B'], (int, float)) else 20.0
            st.success("🎯 Dữ liệu đã được cập nhật cho hệ thống!")

# ==========================================
# TAB 2: HÌNH HỌC & MẶT CẮT NGANG
# ==========================================
with tab2:
    st.header("🛣️ Yếu tố hình học & Mặt cắt ngang")
    
    col1, col2 = st.columns(2)
    with col1:
        loai_d = st.selectbox("Loại đường thiết kế:", ["O to", "Cao tốc", "Do thi"])
        vtk = st.select_slider("Vận tốc thiết kế Vtk (km/h):", options=[30, 40, 50, 60, 80, 100, 120], value=60)
    
    with col2:
        n_lan_input = st.number_input("Số làn xe (n):", min_value=2, value=2)
        w_le_input = st.number_input("Bề rộng dải an toàn (m):", value=0.5)

    if st.button("🔍 Tra cứu & Tính toán MCN"):
        # 1. Tra cứu YTHH từ file 02
        res_hh = YTHH.tra_cuu_yeu_to_hinh_hoc(loai_d, vtk)
        
        # 2. Tính toán chi tiết MCN từ file 03
        input_data = {"loai": loai_d, "vtk": vtk}
        res_mcn = MCN.thiet_ke_mcn_cau_web(input_data)
        
        if res_hh["status"] == "success":
            st.divider()
            
            # --- HIỂN THỊ CHỈ SỐ KỸ THUẬT ---
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Cấp đường", res_hh['cap_duong'])
            m2.metric("i_max dọc", f"{res_hh['imax']}%")
            m3.metric("R lồi min", f"{res_hh['R_loi_min']}m")
            m4.metric("Tổng Bc", f"{res_mcn['bc_cau']}m")

            # --- HIỂN THỊ SƠ ĐỒ MÔ PHỎNG (Giống file 03 cũ) ---
            st.subheader("🖼️ Sơ đồ bố trí mặt cắt ngang cầu")
            st.code(res_mcn['mo_phong'], language="text")
            
            # --- BẢNG CHI TIẾT KÍCH THƯỚC ---
            df_mcn = pd.DataFrame({
                "Thành phần": ["Làn xe", "Dải an toàn", "Dải phân cách", "Gờ lan can", "TỔNG BỀ RỘNG (Bc)"],
                "Kích thước chi tiết": [
                    f"{n_lan_input} làn x {res_mcn['w_lan']}m",
                    f"2 bên x {w_le_input}m",
                    f"{res_mcn['w_dpc']} m",
                    f"2 bên x {res_mcn['w_lc']}m",
                    f"{res_mcn['bc_cau']} m"
                ]
            })
            st.table(df_mcn)

            # Lưu vào session_state để Robot AI ở Tab 3 sử dụng
            st.session_state.design_data['bc'] = res_mcn['bc_cau']
            st.session_state.design_data['vtk'] = vtk
            st.session_state.design_data['loai_duong'] = loai_d
# ==========================================
# TAB 3: DỰ BÁO AI
# ==========================================
with tab3:
    st.header("🤖 Robot AI dự báo Kết cấu nhịp chính")
    
    # Hiển thị tóm tắt đầu vào cho AI
    st.write("Dữ liệu đầu vào cho AI:")
    col_a, col_b, col_c = st.columns(3)
    col_a.write(f"📍 Tĩnh không B: **{st.session_state.design_data['khau_do_ngang']} m**")
    col_b.write(f"📍 Bề rộng Bc: **{st.session_state.design_data['bc']} m**")
    col_c.write(f"📍 Môi trường: **{st.session_state.design_data['loai_duong']}**")

    # Đường dẫn file Excel trên server
    base_path = os.path.dirname(__file__)
    xlsx_path = os.path.join(base_path, "Girder.xlsx")

    if st.button("🚀 Bắt đầu Dự báo AI"):
        if not os.path.exists(xlsx_path):
            st.error("Thiếu file Girder.xlsx trên GitHub!")
        else:
            with st.spinner('AI đang phân tích dữ liệu huấn luyện...'):
                # 1. Huấn luyện
                models = GRD.train_bridge_ai_system(xlsx_path)
                
                if models:
                    # 2. Dự báo
                    env = "Đô thị" if st.session_state.design_data['loai_duong'] == "Do thi" else "Vượt sông"
                    res_ai = GRD.predict_main_span(
                        st.session_state.design_data['khau_do_ngang'], 
                        90, # Góc giao
                        st.session_state.design_data['bc'], 
                        env, 
                        models
                    )
                    
                    # 3. Hiển thị kết quả
                                    
                    st.subheader("KẾT QUẢ ĐỀ XUẤT TỪ AI")
                    res_col1, res_col2, res_col3 = st.columns(3)
                    
                    res_col1.metric("Loại dầm", res_ai['loai_dam'].upper())
                    res_col2.metric("Chiều dài L", f"{res_ai['chieu_dai']} m")
                    res_col3.metric("Số lượng dầm", f"{res_ai['so_luong']} thanh")
                    
                    with st.expander("Xem chi tiết cấu tạo dầm"):
                        st.json(res_ai)
                else:
                    st.error("Lỗi trong quá trình huấn luyện AI.")

st.sidebar.markdown("---")
st.sidebar.write("👤 **Tác giả:** Chương DND")
st.sidebar.write("🎓 **Đề tài:** Ứng dụng AI trong thiết kế cầu")
st.sidebar.write("🎓 **Giám sát tác giả:** Quang BN")