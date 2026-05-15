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
        st.session_state.design_data['loai_doi_tuong_vuot'] = loai_c
        goc_giao = st.number_input("Góc giao chéo (độ):", min_value=30.0, max_value=90.0, value=90.0, step=1.0, 
                                    help="Góc giữa tim tuyến cầu và tim dòng chảy/đường bị vượt. 90 độ là vuông góc.")
        st.session_state.design_data['goc_giao'] = goc_giao
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
            st.session_state.design_data['cap_duong_bi_vuot'] = loai_duong_v
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
            h_tn_tb = st.number_input("Cao độ tự nhiên trung bình (m):", value=0.00, format="%.3f", key="tn_db")
            h1 = st.number_input("Cao độ mặt đường bị vượt (m):", value=5.00, format="%.3f", key="overpass_height")
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
        input_tra_cuu = v_hinhhoc
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
        col_loai, col_cap_dt = st.columns(2)
        with col_loai:
            loai_dt = st.selectbox("Loại đường đô thị:", 
                                   ["Trục chính đô thị", "Đường chính đô thị", "Đường khu vực", "Đường nội bộ"], 
                                   key="dt_loai")
        with col_cap_dt:
            # Xác định danh sách cấp tương ứng để người dùng chọn
            options_cap = ["Đặc biệt", "Cấp I", "Cấp II"] if loai_dt == "Trục chính đô thị" else ["Cấp I", "Cấp II"]
            cap_dt = st.selectbox("Cấp đường:", options_cap, key="dt_cap")

        # GỌI HÀM TỪ FILE 02 ĐỂ LẤY VẬN TỐC (Không cần viết bảng data ở đây nữa)
        list_vtk = YTHH.get_vtk_goi_y_dothi(loai_dt, cap_dt)
        
        v_hinhhoc = st.radio("Chọn Vận tốc thiết kế Vtk (km/h) áp dụng:", 
                             options=list_vtk, horizontal=True, key="dt_v_final")
        
        d_hinhhoc = st.radio("Địa hình:", ["1", "2"], horizontal=True,
                             format_func=lambda x: "Bằng phẳng" if x == "1" else "Đồi núi/Khó khăn", key="dt_dh")
        
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

    # --- BƯỚC CUỐI: NÚT BẤM TÍNH TOÁN, DỰNG HÌNH & DỰ BÁO AI ---
    if st.button("🚀 Let's go!", use_container_width=True):
        # 1. Gọi hàm tính toán Tĩnh không & Thủy văn (Lấy dữ liệu thô từ File 01)
        res = TK.tra_cuu_tinh_khong_bridge(
            loai_cau=loai_c, 
            mien=mien if loai_c=="Vượt sông" else None,
            cap_num=cap_s if loai_c=="Vượt sông" else None,
            loai_hinh=loai_h if loai_c=="Vượt sông" else None,
            loai_duong_vuot=loai_duong_v if loai_c=="Vượt đường bộ" else None,
            cap_oto=b_khai_bao if loai_c=="Vượt đường bộ" else None,
            h1=h1, h5=h5, h10=h10, h98=h98,
            h_tn_tb=h_tn_tb
        )
        
        # --- CẬP NHẬT 1: TÍNH TOÁN BỀ RỘNG THEO GÓC XIÊN ---
        alpha_deg = goc_giao  # Biến này lấy từ input st.number_input bạn vừa thêm
        alpha_rad = np.radians(alpha_deg)
        B_goc = res.get('B', 0)
        
        # Nếu xiên (góc < 90), quy đổi B_tk = B / sin(alpha)
        if alpha_deg < 90:
            B_thiet_ke = round(B_goc / np.sin(alpha_rad), 2)
        else:
            B_thiet_ke = B_goc
            
        res['B'] = B_thiet_ke # Cập nhật lại B để các hàm sau sử dụng
        res['goc_giao'] = alpha_deg
        res['h_tn_tb'] = h_tn_tb

        # 2. Bơm dữ liệu hình học và tính toán trắc dọc
        if res_geo.get("status") == "success":
            res['R_hinh_hoc'] = st.session_state.get('R_final', 5000)
            h_tham_chieu = h_tn_tb if loai_c == "Vượt sông" else h1
            h_dam_thuc_te = res.get('day_dam', 0.0)

            # Gọi hàm tính toán logic từ file 02 (Xác định L_cau, x_mo_trai,...)
            res['geo_logic'] = YTHH.tinh_toan_geo_logic(res, h_tham_chieu, h_dam_thuc_te)
            
            imax_raw = res_geo.get('imax', '0')
            res['i_max_hinh_hoc'] = float(str(imax_raw).split('%')[0])
            res['bc'] = 12.0  # Mặc định bề rộng mặt cầu, có thể thay bằng input người dùng

            # --- CẬP NHẬT 2: GỌI ROBOT AI DỰ BÁO KẾT CẤU (File 05) ---
            with st.spinner('🤖 Robot AI đang dự báo nhịp & dầm tối ưu...'):
                xlsx_path = os.path.join(os.path.dirname(__file__), "Girder.xlsx")
                models = GRD.train_bridge_ai_system(xlsx_path)
                
                if models:
                    env_ai = "Đô thị" if loai_c == "Vượt đường bộ" else "Vượt sông"
                    # Dự báo dầm, số nhịp dựa trên B xiên và L_cau thực tế
                    res_ai = GRD.predict_main_span(
                        b_tk=res['B'], 
                        goc=alpha_deg, 
                        b_cau=res['bc'], 
                        env=env_ai, 
                        models=models,
                        L_cau_tong=res['geo_logic']['L_cau']
                    )
                    res['ai_result'] = res_ai
                else:
                    st.warning("⚠️ Không nạp được mô hình AI, chỉ hiển thị trắc dọc hình học.")

            # Lưu vào session_state
            st.session_state.design_data = res
            st.session_state.res_geo_current = res_geo

            # 3. HIỂN THỊ KẾT QUẢ TỔNG HỢP
            st.divider()
            col_res1, col_res2 = st.columns([2, 1])
            
            with col_res1:
                st.subheader("🖼️ Sơ đồ trắc dọc cầu thiết kế")
                try:
                    fig = PLOT.ve_trac_doc_cau(res)
                    st.pyplot(fig)
                except Exception as e:
                    st.error(f"Lỗi khi vẽ: {e}")
            
            with col_res2:
                st.subheader("🤖 Đề xuất của AI")
                if 'ai_result' in res:
                    ai = res['ai_result']
                    st.info(f"**{ai['loai_dam'].upper()}**")
                    st.write(f"🔹 Tổng số nhịp: **{ai['tong_so_nhip']} nhịp**")
                    st.write(f"🔹 Chiều dài nhịp: **{ai['chieu_dai']} m**")
                    st.write(f"🔹 Chiều cao dầm: **{ai['chieu_cao']} m**")
                    st.success(f"💡 {ai['ghi_chu_ai']}")
                
                st.subheader("📐 Thông số mố trụ")
                geo = res['geo_logic']
                st.write(f"📍 Vị trí mố trái: **{geo['x_mo_trai']:.2f} m**")
                st.write(f"📍 Vị trí mố phải: **{geo['x_mo_phai']:.2f} m**")
                st.write(f"📏 Tổng chiều dài L: **{geo['L_cau']:.2f} m**")
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
    
    # 1. TRUY XUẤT DỮ LIỆU AN TOÀN TỪ TAB 1 & TAB 2
    data = st.session_state.design_data
    
    # Xác định môi trường trực tiếp từ lựa chọn đối tượng vượt ở Tab 1
    # Nếu chưa chọn, mặc định là "Vượt sông"
    loai_vuot_tab1 = data.get('loai_doi_tuong_vuot', 'Vượt sông')
    env = "Đô thị" if loai_vuot_tab1 == "Vượt đường bộ" else "Vượt sông"
    
    # Hiển thị tóm tắt đầu vào để người dùng kiểm tra
    st.write("Dữ liệu đầu vào cho AI (Lấy từ Tab 1 & Tab 2):")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("📍 Tĩnh không B", f"{data.get('B', 0)} m")
    col_b.metric("📍 Bề rộng Bc", f"{data.get('bc', 0)} m")
    col_c.metric("📍 Môi trường", env)

    # Đường dẫn file Excel huấn luyện
    xlsx_path = os.path.join(os.path.dirname(__file__), "Girder.xlsx")

    if st.button("🚀 Bắt đầu Dự báo AI", use_container_width=True):
        if not os.path.exists(xlsx_path):
            st.error("❌ Thiếu file Girder.xlsx để huấn luyện Robot AI!")
        elif 'geo_logic' not in data:
            st.warning("⚠️ Bạn cần nhấn 'Let's go!' ở Tab 1 để có dữ liệu tổng chiều dài cầu trước.")
        else:
            with st.spinner('AI đang phân tích và tính toán phương án tối ưu...'):
                # Gọi Module huấn luyện (File 05)
                models = GRD.train_bridge_ai_system(xlsx_path)
                
                if models:
                    # GỌI DỰ BÁO: Tận dụng B (File 01), Bc (Tab 2) và L_cau (File 02)
                    res_ai = GRD.predict_main_span(
                        b_tk = data.get('B', 20.0), 
                        goc = 90, 
                        b_cau = data.get('bc', 12.0), 
                        env = env, 
                        models = models,
                        L_cau_tong = data['geo_logic'].get('L_cau') # Lấy tổng chiều dài cầu để chia nhịp
                    )
                    
                    # 3. HIỂN THỊ KẾT QUẢ ĐỀ XUẤT
                    st.divider()
                    st.subheader("📋 KẾT QUẢ ĐỀ XUẤT TỪ ROBOT AI")
                    
                    # Hiển thị các chỉ số chính
                    r1, r2, r3 = st.columns(3)
                    r1.metric("Loại dầm", res_ai['loai_dam'].upper())
                    r2.metric("Tổng số nhịp", f"{res_ai.get('tong_so_nhip', 1)} nhịp")
                    r3.metric("Chiều dài nhịp (L)", f"{res_ai['chieu_dai']} m")
                    
                    # Thông báo đánh giá của AI về tính kinh tế
                    st.info(f"💡 **Đánh giá AI:** {res_ai.get('ghi_chu_ai', 'Đã tính toán xong phương án nhịp.')}")
                    
                    with st.expander("🔍 Xem chi tiết cấu tạo và mặt cắt ngang"):
                        st.json(res_ai)
                else:
                    st.error("❌ Lỗi trong quá trình huấn luyện hệ thống AI.")

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