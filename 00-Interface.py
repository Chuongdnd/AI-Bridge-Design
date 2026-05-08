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
    st.header("Xác định Tĩnh không & Cao độ đáy dầm")
    col1, col2 = st.columns(2)
    
    with col1:
        loai_c = st.radio("Loại cầu:", ["Vượt sông", "Vượt đường bộ"])
        if loai_c == "Vượt sông":
            mien = st.selectbox("Khu vực:", ["1", "2"], format_func=lambda x: "Miền Bắc" if x=="1" else "Miền Nam")
            cap_s = st.selectbox("Cấp sông:", ["1", "2", "3", "4", "5", "6"], index=2)
            hinh_thuc = st.selectbox("Hình thức:", ["1", "2"], format_func=lambda x: "Kênh" if x=="1" else "Sông")
    
    with col2:
        if loai_c == "Vượt sông":
            h1 = st.number_input("Mực nước thiết kế H1% (m):", value=2.0)
            h5 = st.number_input("Mực nước thông thuyền H5% (m):", value=1.5)
        else:
            loai_v = st.selectbox("Đường bị vượt là:", ["Cao tốc", "Đường ô tô"])
            cap_o = st.selectbox("Cấp đường bị vượt:", ["Cấp I, II, III", "Các cấp còn lại"])

    if st.button("Tra cứu Tĩnh không"):
        # Xử lý gọi hàm an toàn để tránh lỗi thiếu biến
        if loai_c == "Vượt sông":
            res = TK.tra_cuu_tinh_khong_bridge(loai_c, mien=mien, cap_song=cap_s, loai_hinh_thuy=hinh_thuc, h1=h1, h5=h5)
        else:
            res = TK.tra_cuu_tinh_khong_bridge(loai_c, loai_duong_vuot=loai_v, cap_oto=cap_o)
        
        if res.get('status') == "success":
            st.session_state.design_data['khau_do_ngang'] = res['khau_do_ngang']
            st.session_state.design_data['cao_do_day_dam'] = res['cao_do_day_dam']
            st.success(f"✅ {res['loai']}")
            st.metric("Khẩu độ ngang (m)", res['khau_do_ngang'])
        else:
            st.error(res.get('message', 'Lỗi không xác định'))

# ==========================================
# TAB 2: HÌNH HỌC & MẶT CẮT NGANG
# ==========================================
with tab2:
    st.header("🛣️ Thiết kế Hình học & Mặt cắt ngang Cầu")
    
    # --- PHẦN 1: NHẬP LIỆU ---
    col_in1, col_in2 = st.columns(2)
    
    with col_in1:
        st.subheader("📋 Thông số Tuyến")
        loai_d = st.selectbox("Loại đường thiết kế:", ["O to", "Cao tốc", "Do thi"], key="loai_duong_tab2")
        
        # Điều chỉnh dải vận tốc theo loại đường
        if loai_d == "Cao tốc":
            opts_v = [60, 80, 100, 120]
        elif loai_d == "O to":
            opts_v = [30, 40, 60, 80, 100, 120]
        else:
            opts_v = [30, 40, 50, 60, 80, 100]
            
        vtk = st.select_slider("Vận tốc thiết kế Vtk (km/h):", options=opts_v, value=opts_v[1] if len(opts_v)>1 else opts_v[0])
        dia_hinh = st.radio("Loại địa hình (Chỉ áp dụng cho Đường ô tô):", ["1", "2"], 
                            format_func=lambda x: "Đồng bằng / Đồi" if x=="1" else "Miền núi / Hiểm trở")

    with col_in2:
        st.subheader("📐 Quy mô Mặt cắt ngang")
        n_lan = st.number_input("Số làn xe tổng cộng (n):", min_value=2, max_value=12, value=2, step=2)
        w_le = st.number_input("Bề rộng dải an toàn / Lề (m):", min_value=0.25, max_value=3.0, value=0.5, step=0.25)
        # Bề rộng làn xe mặc định theo loại đường nhưng cho phép sửa
        w_lan_def = 3.5
        if loai_d == "Cao tốc" and vtk >= 100: w_lan_def = 3.75
        w_lan = st.number_input("Bề rộng 1 làn xe (m):", min_value=2.75, max_value=4.0, value=w_lan_def, step=0.25)

    # --- PHẦN 2: NÚT BẤM KÍCH HOẠT ---
    if st.button("🚀 Tra cứu Tiêu chuẩn & Vẽ sơ đồ MCN"):
        # 1. Gọi logic tra cứu hình học từ file 02 (YTHH)
        res_hh = YTHH.tra_cuu_yeu_to_hinh_hoc(loai_d, vtk, dia_hinh)
        
        # 2. Gọi logic tính toán chi tiết từ file 03 (MCN)
        # Chuẩn bị input cho hàm xử lý ở file 03
        data_mcn_input = {
            "loai": loai_d,
            "vtk": vtk,
            "n_lan": n_lan,
            "w_lan": w_lan,
            "w_le": w_le
        }
        res_mcn = MCN.thiet_ke_mcn_cau_web(data_mcn_input) # Đảm bảo file 03 có hàm này

        if res_hh["status"] == "success":
            st.divider()
            
            # --- HIỂN THỊ CHỈ SỐ KỸ THUẬT (METRICS) ---
            st.subheader("✅ Kết quả Tra cứu Tiêu chuẩn")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Cấp đường", res_hh['cap_duong'])
            m2.metric("i_max dọc", f"{res_hh['imax']}%")
            m3.metric("R lồi min (m)", res_hh['R_loi_min'])
            m4.metric("TỔNG BỀ RỘNG Bc", f"{res_mcn['bc_cau']} m")

            # --- HIỂN THỊ SƠ ĐỒ ĐỒ HỌA (MATPLOTLIB) ---
            st.subheader("🎨 Sơ đồ cấu tạo Mặt cắt ngang (Tỷ lệ thực)")
            # Gọi hàm vẽ từ file 03
            fig_mcn = MCN.ve_so_do_mcn_bridge(res_mcn) 
            st.pyplot(fig_mcn)

            # --- BẢNG CHI TIẾT THÀNH PHẦN ---
            st.subheader("📊 Bảng chi tiết thành phần kích thước")
            col_t1, col_t2 = st.columns([1.5, 1])
            
            with col_t1:
                df_out = pd.DataFrame({
                    "Thành phần": ["Phần xe chạy", "Dải an toàn (Lề)", "Dải phân cách", "Gờ lan can", "Tổng bề rộng Bc"],
                    "Chi tiết tính toán": [
                        f"{n_lan} làn x {w_lan}m = {res_mcn['w_mat_tong']}m",
                        f"2 bên x {w_le}m = {res_mcn['tong_w_le']}m",
                        f"{res_mcn['w_dpc']} m",
                        f"2 bên x {res_mcn['w_lc']}m = 1.0m",
                        f"{res_mcn['bc_cau']} m"
                    ]
                })
                st.table(df_out)
            
            with col_t2:
                st.info(f"**Ghi chú kỹ thuật:**\n- Tiêu chuẩn: {res_hh.get('tieuchuan', 'TCVN')}\n- Sơ đồ mô phỏng: `{res_mcn['mo_phong']}`")
                
            # Cập nhật Session State để Tab 3 (AI) lấy dữ liệu
            st.session_state.design_data['bc'] = res_mcn['bc_cau']
            st.session_state.design_data['vtk'] = vtk
            st.session_state.design_data['loai_duong'] = loai_d
            st.success("🎯 Đã lưu thông số Bc để dự báo AI tại Tab 3!")
        else:
            st.error(f"Lỗi: {res_hh.get('message')}")
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