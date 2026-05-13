import streamlit as st
import pandas as pd
import os
import importlib
import google.generativeai as genai
import fitz
# --- THIẾT LẬP TRANG ---
if 'messages' not in st.session_state:
    st.session_state.messages = []
try:
    # Gọi chính xác tên biến bạn đã đặt trong mục Secrets
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        
        # Khởi tạo model - Nên dùng tên này để ổn định nhất
        gemini_model = genai.GenerativeModel('gemini-2.5-flash')
    else:
        st.error("❌ Không tìm thấy mã GEMINI_API_KEY trong cấu hình Secrets của Streamlit!")
        gemini_model = None
except Exception as e:
    st.error(f"Lỗi cấu hình AI: {e}")
    gemini_model = None

def load_all_standards(folder_name="Documents"):
    knowledge_text = ""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    folder_path = os.path.join(current_dir, folder_name)
    
    if not os.path.exists(folder_path):
        return "Thư mục tài liệu không tồn tại."

    for file_name in os.listdir(folder_path):
        if file_name.endswith(".pdf"):
            try:
                doc = fitz.open(os.path.join(folder_path, file_name))
                text = ""
                for page in doc:
                    text += page.get_text()
                knowledge_text += f"\n--- NGUỒN TÀI LIỆU: {file_name} ---\n{text}\n"
            except Exception as e:
                print(f"Lỗi đọc file {file_name}: {e}")
    return knowledge_text

# --- 3. NẠP TÀI LIỆU VÀO BỘ NHỚ (Chèn vào đây) ---
if 'bridge_library' not in st.session_state:
    with st.spinner("📚 Đang nạp hệ thống tiêu chuẩn cầu đường..."):
        st.session_state.bridge_library = load_all_standards()

st.set_page_config(page_title="Hệ thống Thiết kế Cầu AI", layout="wide", page_icon="🏗️")

current_dir = os.path.dirname(os.path.abspath(__file__)) # Lấy thư mục gốc của dự án
logo_path = os.path.join(current_dir, "Images", "UTH.jpg")

with st.sidebar:
    if os.path.exists(logo_path):
        st.image(logo_path, width=300)
    else:
        st.error("⚠️ Thiếu file logo!")

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
        
    st.subheader("📐 Yếu tố hình học thiết kế")
    l_hinhhoc = st.selectbox("Chọn loại đường thiết kế:", ["Cao tốc", "O to", "Do thi"], key="main_type")

# --- KỊCH BẢN 1: ĐỐI VỚI ĐƯỜNG CAO TỐC ---
    if l_hinhhoc == "Cao tốc":
        col1, col2 = st.columns(2)
        with col1:
            d_hinhhoc = st.radio("Chọn địa hình:", 
                                options=["1", "2"], 
                                format_func=lambda x: "Đồng bằng" if x == "1" else "Núi, đồi cao, địa hình khó khăn",
                                key="ct_terrain")
        with col2:
            # Ràng buộc vận tốc theo địa hình đúng yêu cầu
            v_list = [120, 100] if d_hinhhoc == "1" else [80, 60]
            v_hinhhoc = st.selectbox("Vận tốc thiết kế Vtk (km/h):", options=v_list, key="ct_v")

    # --- KỊCH BẢN 2: ĐỐI VỚI ĐƯỜNG Ô TÔ ---
    elif l_hinhhoc == "O to":
        st.markdown("### --- BẢNG 3: CẤP THIẾT KẾ VÀ LƯU LƯỢNG XE THIẾT KẾ (TCVN 4054:2005) ---")
        data_b3 = {
            "Cấp thiết kế": ["Cấp I", "Cấp II", "Cấp III", "Cấp IV", "Cấp V", "Cấp VI"],
            "Lưu lượng xe (xcqd/ngày đêm)": ["> 15.000", "6.000 - 15.000", "3.000 - 6.000", "500 - 3.000", "200 - 500", "<= 200"]
        }
        st.table(pd.DataFrame(data_b3))
        
        col_cap, col_dh = st.columns(2)
        with col_cap:
            cap_duong_oto = st.selectbox("Chọn Cấp đường:", ["I", "II", "III", "IV", "V", "VI"], key="oto_cap_auto")
        with col_dh:
            d_hinhhoc = st.radio("Chọn địa hình:", ["1", "2"], horizontal=True, 
                                 format_func=lambda x: "Đồng bằng" if x == "1" else "Miền núi", key="oto_dh_auto")
        
        # Xác định đầu vào tra cứu là Cấp đường
        input_tra_cuu = cap_duong_oto

    # --- KỊCH BẢN 3: ĐỐI VỚI ĐƯỜNG ĐÔ THỊ ---
    else:
        st.info("ℹ️ Tra cứu theo TCXDVN 104:2007")
        col_v_dt, col_dh_dt = st.columns(2)
        with col_v_dt:
            v_hinhhoc = st.selectbox("Vận tốc thiết kế Vtk (km/h):", options=[100, 80, 60, 50, 40, 30], key="dt_v")
        with col_dh_dt:
            d_hinhhoc = st.radio("Địa hình:", ["1", "2"], format_func=lambda x: "Bằng phẳng" if x == "1" else "Đồi núi", key="dt_dh")
        
        # Xác định đầu vào tra cứu là Vận tốc
        input_tra_cuu = v_hinhhoc

    # --- BƯỚC TRUNG GIAN: TRA CỨU YẾU TỐ HÌNH HỌC ---
    # Lệnh này nằm ngoài các khối if/else để luôn chạy trước khi bấm nút
    res_geo = YTHH.tra_cuu_yeu_to_hinh_hoc(l_hinhhoc, input_tra_cuu, d_hinhhoc)

    if res_geo.get("status") == "success":
        st.success(f"✅ Đã xác định Vtk = {res_geo['v_thiet_ke']} | imax = {res_geo['imax']}")
        
        # Cho phép người dùng chọn R đứng lồi để vẽ
        chon_R = st.radio("Chọn bán kính đứng lồi áp dụng:", 
                         ["Tối thiểu thông thường", "Tối thiểu giới hạn"], horizontal=True, key="r_selection")
        
        # Lưu giá trị R vào session_state để nút bấm bên dưới sử dụng
        r_final = res_geo["R_loi_tt"] if chon_R == "Tối thiểu thông thường" else res_geo["R_loi_gh"]
        st.session_state.R_final = r_final

    st.divider()

    # --- BƯỚC CUỐI: NÚT BẤM TÍNH TOÁN VÀ DỰNG HÌNH ---
    if st.button("🚀 Let's go!", use_container_width=True):
        # 1. Gọi hàm tính toán Tĩnh không & Thủy văn
        res = TK.tra_cuu_tinh_khong_bridge(
            loai_cau=loai_c, 
            mien=mien if loai_c=="Vượt sông" else None,
            cap_num=cap_s if loai_c=="Vượt sông" else None,
            loai_hinh=loai_h if loai_c=="Vượt sông" else None,
            loai_duong_vuot=loai_duong_v if loai_c=="Vượt đường bộ" else None,
            cap_oto=b_khai_bao if loai_c=="Vượt đường bộ" else None,
            h1=h1, h5=h5, h10=h10, h98=h98,
            h_tn_tb=h_tn_tb if loai_c=="Vượt sông" else h1
        )

        # 2. Bơm dữ liệu hình học vào res để phục vụ hàm vẽ
        if res_geo.get("status") == "success":
            res['R_hinh_hoc'] = st.session_state.get('R_final', 5000)
            
            # Ép kiểu imax về số (cắt bỏ dấu % nếu có)
            imax_raw = res_geo.get('imax', '0')
            res['i_max_hinh_hoc'] = float(str(imax_raw).split('%')[0])
            
            # Gán thêm biến 'bc' (bề rộng cầu) để tránh lỗi ở các tab khác
            res['bc'] = res.get('B', 0)

            # Lưu vào session_state để chatbot và các tab sau sử dụng
            st.session_state.design_data = res
            st.session_state.res_geo_current = res_geo

            # 3. HIỂN THỊ KẾT QUẢ VÀ BẢN VẼ
            st.subheader("🖼️ Sơ đồ trắc dọc cầu thiết kế")
            try:
                fig = PLOT.ve_trac_doc_cau(res)
                st.pyplot(fig)
                st.success(f"🎉 Đã vẽ trắc dọc với R = {res['R_hinh_hoc']}m")
            except Exception as e:
                st.error(f"Lỗi khi vẽ: {e}")

            # 4. HIỂN THỊ BẢNG TỔNG HỢP (Theo file txt của bạn)
            st.subheader("📊 Bảng thông số kỹ thuật")
            if loai_c == "Vượt đường bộ":
                df_data = {
                    "Thông số kỹ thuật": ["Loại đường bị vượt", "Bề rộng tĩnh không (B)", "Chiều cao tĩnh không (H)", "Cao độ mặt đường", "Cao độ đáy dầm thiết kế"],
                    "Giá trị": [res.get('label', "").split("-")[-1].strip(), f"{res.get('B', 0)} m", f"{res.get('H', 0)} m", f"{res.get('MNCN', 0):.3f} m", f"{res.get('day_dam', 0):.3f} m"]
                }
            else:
                df_data = {
                    "Thông số kỹ thuật": ["Khổ ngang (B)", "Tĩnh không đứng (H)", "Mực nước cao nhất (MNCN)", "Cao độ đáy dầm thiết kế"],
                    "Giá trị": [f"{res.get('B', 0)} m", f"{res.get('H', 0)} m", f"{res.get('MNCN', 0):.3f} m", f"{res.get('day_dam', 0):.3f} m"]
                }
            st.table(pd.DataFrame(df_data))
        else:
            st.error("❌ Không thể xác định yếu tố hình học. Vui lòng kiểm tra lại đầu vào.")
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
    col_a.write(f"📍 Tĩnh không B: **{st.session_state.design_data.get('B', 0)} m**")
    col_b.write(f"📍 Bề rộng Bc: **{st.session_state.design_data.get('bc', 0)} m**")
    moi_truong = st.session_state.design_data.get('loai_duong', st.session_state.get('main_type_select', 'Chưa chọn'))
    col_c.write(f"📍 Môi trường: **{moi_truong}**")

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

    st.markdown("---")
# --- SIDEBAR: THÔNG TIN VÀ CHATBOT (DÒNG 324 TRỞ ĐI) ---
with st.sidebar:
    st.markdown("---")
    st.write("👤 **SVTH:** Chương DND")
    st.write("👨‍🏫 **GVHD:** T.S Nguyễn Văn Hiển")
    st.write("🎓 **Đề tài:** Nghiên cứu giải pháp tích hợp trí tuệ nhân tạo (AI) và Mô hình thông tin công trình (BIM) tự động hóa thiết kế cầu đường bộ tại Việt Nam")

    # --- PHẦN CHATBOT (Tất cả phải thụt lề 4 khoảng trắng so với 'with') ---
    st.markdown("---")
    st.subheader("🤖 Bridge AI Assistant")
    
    # 1. Khung hiển thị hội thoại
    chat_container = st.container(height=250, border=True)
    
    with chat_container:
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])

    # 2. Ô nhập liệu chat (Cần thụt lề để nằm trong sidebar)
    if prompt := st.chat_input("Hỏi tôi về thiết kế cầu...", key="sidebar_chat"):
        # Lưu tin nhắn người dùng
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Xử lý AI Gemini
        try:
            design_info = st.session_state.get('design_data', "Chưa có dữ liệu.")
            system_msg = f"""
            Bạn là chuyên gia tư vấn thiết kế cầu của UTH. 
            Sử dụng tri thức sau: {st.session_state.bridge_library}
            Dữ liệu web hiện tại: {design_info}
            """
            
            # Gọi Gemini xử lý
            response = gemini_model.generate_content(f"{system_msg}\n\nCâu hỏi: {prompt}")
            
            # Lưu phản hồi của AI
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
            # Làm mới trang để tin nhắn hiện lên ngay lập tức
            st.rerun() 
            
        except Exception as e:
            st.error(f"Lỗi AI: {e}")