import streamlit as st
import pandas as pd
import os
import importlib
import google.generativeai as genai
# --- THIẾT LẬP TRANG ---
API_KEY = "AIzaSyC9Mpgrd-_b5xTzTfIHruDKQy9YIak52Oo"
try:
    genai.configure(api_key=API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Lỗi cấu hình AI: {e}")

st.set_page_config(page_title="Hệ thống Thiết kế Cầu AI", layout="wide", page_icon="🏗️")

current_dir = os.path.dirname(os.path.abspath(__file__)) # Lấy thư mục gốc của dự án
logo_path = os.path.join(current_dir, "Images", "UTH.jpg")

with st.sidebar:
    if os.path.exists(logo_path):
        st.image(logo_path, width=300)
    else:
        st.error("⚠️ Thiếu file logo!")

# --- 2. CHÈN NHẠC NỀN VÀO SIDEBAR ---
with st.sidebar:
    st.title("🎵 Sound")
    music_path = os.path.join(current_dir, "Sounds", "S1.mp3")
    if os.path.exists(music_path):
        st.audio(music_path, loop=True, autoplay=True)
    else:
        st.error(f"⚠️ Không tìm thấy file: {music_path}")

# --- KẾT NỐI MODULES ---
try:
    TK = importlib.import_module("01-Tinh_khong")
    YTHH = importlib.import_module("02-Yeuto_Hinhhoc")
    MCN = importlib.import_module("03-MatCatNgang")
    GRD = importlib.import_module("05-Main_Girder")
    PLOT = importlib.import_module("00-Drawing_Utils")
    importlib.reload(PLOT)
except Exception as e:
    st.error(f"Lỗi kết nối Module: {e}")

# --- KHỞI TẠO SESSION STATE ---
if 'design_data' not in st.session_state:
    st.session_state.design_data = {
        'day_dam': 0.0,
        'khau_do_ngang': 0.0,
        'bc': 0.0,
        'loai_duong': "Do thi"
    }
if 'messages' not in st.session_state:
    st.session_state.messages = []
# --- GIAO DIỆN CHÍNH ---
tab1, tab2, tab3 = st.tabs(["🌊 Tĩnh không & Thủy văn", "📐 Hình học & MCN", "🤖 Dự báo AI"])

# ==========================================
# TAB 1: TĨNH KHÔNG & THỦY VĂN
# ==========================================
with tab1:
    st.header("🌊 Thông số Tĩnh không & Thủy văn thiết kế")
    col_in1, col_in2 = st.columns(2)
    with col_in1:
        loai_c = st.radio("Chọn đối tượng vượt:", ["Vượt sông", "Vượt đường bộ"], horizontal=True)
        if loai_c == "Vượt sông":
            mien = st.selectbox("Khu vực:", ["1", "2"], format_func=lambda x: "Miền Bắc" if x=="1" else "Miền Nam")
            cap_s = st.selectbox("Cấp sông:", ["1", "2", "3", "4", "5", "6"], format_func=lambda x: f"Cấp {['I','II','III','IV','V','VI'][int(x)-1]}")
            loai_h = st.selectbox("Loại hình:", ["1", "2"], format_func=lambda x: "Kênh" if x=="1" else "Sông")
        else: # Trường hợp Vượt đường bộ
            loai_duong_v = st.selectbox("Cấp đường bị vượt:", [
        "Đường ô tô (Cấp I, II, III)", 
        "Đường ô tô (Cấp còn lại)", 
        "Đường cao tốc", 
        "Đường cải tạo", 
        "Đường xe thô sơ"
    ])
            # Ô NHẬP BỀ RỘNG B THEO KHAI BÁO NGƯỜI DÙNG
            b_khai_bao = st.number_input("Bề rộng tĩnh không khai báo (B) - m:", value=20.0, step=0.5)
        st.markdown("---")
        l_hinhhoc = st.selectbox("Cấp thiết kế đường trên cầu:", ["O to", "Cao tốc", "Do thi"], key="geo_l")
    with col_in2:
        if loai_c == "Vượt sông":
            h_tn_tb = st.number_input("Cao độ tự nhiên trung bình (m):", value=0.00, format="%.3f")
            h1 = st.number_input("MNCN (H1%):", value=3.50, format="%.3f")
            h5 = st.number_input("MNTT (H5%):", value=2.00, format="%.3f")
            h10 = st.number_input("MNTC (H10%):", value=1.50, format="%.3f")
            h98 = st.number_input("MNTN (H98%):", value=0.50, format="%.3f")
        else:
            # Đối với đường bộ, h1 đóng vai trò là cao độ mặt đường bị vượt
            h1 = st.number_input("Cao độ mặt đường bị vượt (m):", value=5.00, format="%.3f")
            # Các giá trị khác ẩn hoặc để mặc định để tránh lỗi hàm
            h5, h10, h98 = h1, h1, h1
        st.markdown("---")
        v_list = [120, 100, 80, 60, 40, 30] if l_hinhhoc != "Do thi" else [100, 80, 60, 50, 40, 30]
        v_hinhhoc = st.selectbox("Vận tốc thiết kế Vtk (km/h):", v_list, key="geo_v")
        d_hinhhoc = st.radio("Địa hình:", [("1", "Đồng bằng"), ("2", "Miền núi")], 
                                 format_func=lambda x: x[1], horizontal=True, key="geo_d")[0]
    # QUAN TRỌNG: Mọi hiển thị kết quả phải nằm TRONG khối lệnh button này
    if st.button("🚀 Let's go"):
        res = TK.tra_cuu_tinh_khong_bridge(
            loai_cau=loai_c, 
            mien=mien if loai_c=="Vượt sông" else None,
            cap_num=cap_s if loai_c=="Vượt sông" else None,
            loai_hinh=loai_h if loai_c=="Vượt sông" else None,
            loai_duong_vuot=loai_duong_v if loai_c=="Vượt đường bộ" else None,
            cap_oto=b_khai_bao if loai_c=="Vượt đường bộ" else None,
            h1=h1, 
            h5=h5, 
            h10=h10, 
            h98=h98,
            h_tn_tb=h_tn_tb if loai_c=="Vượt sông" else h1 # TRUYỀN THÊM BIẾN NÀY
        )
    
        if res["status"] == "success":
            # LƯU KẾT QUẢ VÀO SESSION STATE
            st.session_state.tinh_khong_res = res
            st.session_state.design_data.update({'day_dam': res['day_dam'], 'khau_do_ngang': res['B']})

    # HIỂN THỊ KẾT QUẢ (Nằm ngoài nút bấm nhưng kiểm tra session_state)
    if 'tinh_khong_res' in st.session_state:
        res = st.session_state.tinh_khong_res
        st.divider()

        # --- BƯỚC A: CHUẨN BỊ DỮ LIỆU BẢNG TRƯỚC (Để tránh lỗi NameError) ---
        if "vượt đường bộ" in res.get('label', "").lower():
            df_data = {
                "Thông số kỹ thuật": ["Loại đường bị vượt", "Bề rộng (B)", "Tĩnh không (H)", "Cao độ mặt đường", "Cao độ đáy dầm"],
                "Giá trị": [res.get('label', "").split("-")[-1].strip(), f"{res.get('B', 0)} m", f"{res.get('H', 0)} m", f"{res.get('MNCN', 0):.3f} m", f"{res.get('day_dam', 0):.3f} m"]
            }
        else:
            df_data = {
                "Thông số kỹ thuật": ["Khổ thông thuyền (B)", "Tĩnh không (H)", "Cao độ đáy dầm thiết kế", "MNCN (H1%)", "MNTT (H5%)", "MNTC (H10%)", "MNTN (H98%)"],
                "Giá trị": [f"{res.get('B', 0)} m", f"{res.get('H', 0)} m", f"{res.get('day_dam', 0):.3f} m", f"{res.get('MNCN', 0):.3f} m", f"{res.get('MNTT', 0):.3f} m", f"{res.get('MNTC', 0):.3f} m", f"{res.get('MNTN', 0):.3f} m"]
            }

        # --- BƯỚC B: TRA CỨU HÌNH HỌC VÀ VẼ HÌNH ---
        res_geo = YTHH.tra_cuu_yeu_to_hinh_hoc(l_hinhhoc, v_hinhhoc, d_hinhhoc)
        
        if res_geo and res_geo.get("status") == "success":
            # Gán dữ liệu bán kính vào res để PLOT vẽ đường cong
            res['R_hinh_hoc'] = res_geo['R_loi_min']
            res['i_max_hinh_hoc'] = res_geo['imax']
            
            st.subheader("🖼️ Sơ đồ bố trí chung mặt cắt dọc cầu")
            st.pyplot(PLOT.ve_trac_doc_cau(res))
    
            # Hiển thị bảng hình học
            st.divider()
            st.subheader("🛣️ Kết quả Yếu tố Hình học (TCVN)")
            g1, g2, g3 = st.columns(3)
            g1.metric("Cấp đường", res_geo['cap_duong'])
            g2.metric("Độ dốc dọc max", f"{res_geo['imax']}%")
            g3.metric("Bán kính Rmin", f"{res_geo['R_loi_min']} m")
        else:
            st.error("Không tìm thấy dữ liệu hình học phù hợp.")

        st.divider()
        # 2. Hiển thị bảng thông số
        st.subheader("📊 Chi tiết thông số kỹ thuật")
        
        # Kiểm tra loại cầu dựa trên label kết quả
        if "vượt đường bộ" in res.get('label', "").lower():
            # NỘI DUNG CHO VƯỢT ĐƯỜNG BỘ
            df_data = {
                "Thông số kỹ thuật": [
                    "Loại đường bị vượt", 
                    "Bề rộng tĩnh không (B)", 
                    "Chiều cao tĩnh không (H)", 
                    "Cao độ mặt đường", 
                    "Cao độ đáy dầm thiết kế"
                ],
                "Giá trị": [
                    res.get('label', "").split("-")[-1].strip(), # Lấy tên loại đường từ label
                    f"{res.get('B', 0)} m", 
                    f"{res.get('H', 0)} m", 
                    f"{res.get('MNCN', 0):.3f} m", 
                    f"{res.get('day_dam', 0):.3f} m"
                ]
            }
        else:
            # GIỮ NGUYÊN NỘI DUNG VƯỢT SÔNG CỦA BẠN
            df_data = {
                "Thông số kỹ thuật": [
                    "Khổ thông thuyền ngang (B)", "Chiều cao tĩnh không đứng (H)", "Cao độ đáy dầm thiết kế",
                    "Mực nước cao nhất (MNCN)", "Mực nước thông thuyền (MNTT)", "Mực nước thi công (MNTC)",
                    "Mực nước thấp nhất (MNTN)"
                ],
                "Giá trị": [
                    f"{res.get('B', 0)} m", 
                    f"{res.get('H', 0)} m", 
                    f"{res.get('day_dam', 0):.3f} m", 
                    f"{res.get('MNCN', 0):.3f} m", 
                    f"{res.get('MNTT', 0):.3f} m", 
                    f"{res.get('MNTC', 0):.3f} m", 
                    f"{res.get('MNTN', 0):.3f} m"
                ]
            }
            
        st.table(pd.DataFrame(df_data))
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
st.sidebar.write("👤 **SVTH:** Chương DND")
st.sidebar.write("👨‍🏫 **GVHD:** T.S Nguyễn Văn Hiển")
st.sidebar.write("🎓 **Đề tài:** Nghiên cứu giải pháp tích hợp trí tuệ nhân tạo (AI) và Mô hình thông tin công trình (BIM) tự động hóa thiết kế cầu đường bộ tại Việt Nam")


# --- 2. CSS ĐỂ NÚT CHAT NẰM CỐ ĐỊNH GÓC PHẢI ---
st.markdown("""
    <style>
    div[data-testid="stPopover"] {
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 1000;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. KHUNG CHAT (Phiên bản đã sửa lỗi kết nối) ---
with st.popover("💬 Trợ lý Kỹ thuật"):
    st.markdown("### 🤖 Bridge AI Assistant")
    
    # Khởi tạo messages nếu chưa có để tránh lỗi AttributeError
    if "messages" not in st.session_state:
        st.session_state.messages = []

    chat_box = st.container(height=350)
    
    # Hiển thị lịch sử chat
    for msg in st.session_state.messages:
        chat_box.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Hỏi tôi về thiết kế cầu..."):
        # Hiển thị tin nhắn người dùng
        st.session_state.messages.append({"role": "user", "content": prompt})
        chat_box.chat_message("user").write(prompt)
        
        try:
            # Gửi câu hỏi cho Gemini
            full_prompt = f"Bạn là kỹ sư cầu đường VN chuyên nghiệp. Trả lời ngắn gọn câu hỏi: {prompt}"
            # Sử dụng đúng biến gemini_model đã khai báo ở đầu file
            response = gemini_model.generate_content(full_prompt)
            
            # Hiển thị câu trả lời của AI
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            chat_box.chat_message("assistant").write(response.text)
        except Exception as e:
            st.error(f"Lỗi: {str(e)}") # Hiện lỗi chi tiết nếu Key bị khóa hoặc sai