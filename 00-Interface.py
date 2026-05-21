import streamlit as st
import pandas as pd
import numpy as np
import os
import importlib
import google.generativeai as genai
import fitz
from streamlit_option_menu import option_menu

# --- THIẾT LẬP TRANG CHUẨN KỸ THUẬT TOÀN MÀN HÌNH ---
st.set_page_config(page_title="Hệ thống Thiết kế Cầu AI - UTH", layout="wide", page_icon="🏗️")

# Khởi tạo bộ nhớ hội thoại chatbot
if 'messages' not in st.session_state:
    st.session_state.messages = []

# --- CẤU HÌNH AI GEMINI ASSISTANT ---
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel('gemini-2.5-flash')
    else:
        st.sidebar.error("❌ Không tìm thấy mã GEMINI_API_KEY trong Secrets!")
        gemini_model = None
except Exception as e:
    st.sidebar.error(f"Lỗi cấu hình AI: {e}")
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
            except:
                pass
    return knowledge_text

# Nạp hệ thống tài liệu vào bộ nhớ đệm
if 'bridge_library' not in st.session_state:
    with st.spinner("📚 Đang nạp hệ thống tiêu chuẩn cầu đường..."):
        st.session_state.bridge_library = load_all_standards()

# --- KẾT NỐI HỆ THỐNG MODULES THÀNH PHẦN ---
try:
    TK = importlib.import_module("01-Tinh_khong")
    YTHH = importlib.import_module("02-Yeuto_Hinhhoc")
    MCN = importlib.import_module("03-MatCatNgang")
    GRD = importlib.import_module("05-Main_Girder")
    PLOT = importlib.import_module("00-Drawing_Utils")
    importlib.reload(PLOT)
except Exception as e:
    st.error(f"Lỗi kết nối Module: {e}")

# --- KHỞI TẠO HOÀN CHỈNH BỘ NHỚ TRẠNG THÁI SESSION STATE ---
if 'design_data' not in st.session_state:
    st.session_state.design_data = {
        'day_dam': 0.0, 'khau_do_ngang': 0.0, 'bc': 12.0, 'loai_duong': "Do thi",
        'B': 20.0, 'H': 4.75, 'loai_doi_tuong_vuot': "Vượt sông", 'goc_giao': 90.0,
        'MNCN': 3.5, 'MNTT': 2.0, 'MNTC': 1.5, 'MNTN': 0.5, 'h_tn_tb': 0.0
    }

# =========================================================================
# ĐIỀU HƯỚNG CHÍNH: DẢI RIBBON NẰM NGANG PHÍA TRÊN CÙNG (CAD & EXCEL STYLE)
# =========================================================================
selected_ribbon = option_menu(
    menu_title=None, 
    options=["TAB TRANG CHỦ", "THÔNG SỐ TUYẾN & AI TƯ VẤN", "BẢN VẼ KỸ THUẬT TƯƠNG TÁC"],
    icons=["house", "sliders2", "layout-text-window-reverse"], 
    menu_icon="cast", 
    default_index=2, # Thiết lập mở mặc định tại không gian Bản vẽ tương tác theo hình ảnh của bạn
    orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "background-color": "#1e1e1e", "border-radius": "0px"},
        "icon": {"color": "#f39c12", "font-size": "14px"}, 
        "nav-link": {
            "font-size": "13px", "text-align": "center", "margin": "0px", "color": "white",
            "font-weight": "bold", "border-radius": "0px", "--hover-color": "#333333"
        },
        "nav-link-selected": {"background-color": "#007acc"}, # Màu xanh bản quyền đặc trưng AutoCAD
    }
)

# Thanh chỉ định ranh giới dải Ribbon
st.markdown("<hr style='margin-top: 0px; margin-bottom: 15px; border-color: #007acc;'>", unsafe_allow_html=True)

# =========================================================================
# THANH PANEL BÊN TRÁI (SIDEBAR): THÔNG TIN ĐỒ ÁN VÀ TRỢ LÝ CHATBOT PHỤ TRỢ
# =========================================================================
with st.sidebar:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(current_dir, "Images", "UTH.jpg")
    if os.path.exists(logo_path):
        st.image(logo_path, width=280)
    
    st.write("👤 **SVTH:** Chương DND")
    st.write("👨‍🏫 **GVHD:** T.S Nguyễn Văn Hiển")
    st.caption("🎓 *Đề tài:* Tích hợp AI và BIM tự động hóa thiết kế cầu đường bộ tại Việt Nam")
    
    st.markdown("---")
    st.subheader("🤖 Bridge AI Assistant")
    chat_container = st.container(height=220, border=True)
    with chat_container:
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Hỏi tôi về thiết kế...", key="sidebar_chat"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        try:
            design_info = st.session_state.get('design_data', "Chưa có dữ liệu.")
            system_msg = f"Bạn là chuyên gia thiết kế cầu UTH. Tri thức: {st.session_state.bridge_library}. Dữ liệu: {design_info}"
            response = gemini_model.generate_content(f"{system_msg}\n\nCâu hỏi: {prompt}")
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            st.rerun()
        except Exception as e:
            st.error(f"Lỗi AI: {e}")

# =========================================================================
# XỬ LÝ LOGIC HIỂN THỊ CHI TIẾT CỦA CÁC VÙNG LÀM VIỆC
# =========================================================================

# --- SECTION 1: TAB TRANG CHỦ ---
if selected_ribbon == "TAB TRANG CHỦ":
    st.title("🏗️ Hệ thống Tự động hóa Thiết kế và Tối ưu hóa Kết cấu Cầu")
    st.write("---")
    st.markdown("""
    ### Chào mừng bạn đến với ứng dụng tính toán kỹ thuật UTH
    Hệ thống hỗ trợ tự động hóa thiết kế trắc dọc, tính toán kích thước hình học thủy văn tĩnh không và ứng dụng công nghệ trí tuệ nhân tạo AI (Random Forest) nhằm đề xuất giải pháp kết cấu dầm chủ tối ưu chi phí.
    
    #### 🛠️ Hướng dẫn điều hướng:
    * **THÔNG SỐ TUYẾN & AI TƯ VẤN:** Vùng khai báo toàn diện các số liệu trắc dọc, cấp tuyến đường, số liệu thủy văn và kích hoạt robot tính toán AI.
    * **BẢN VẼ KỸ THUẬT TƯƠNG TÁC:** Không gian đồ họa chính hiển thị bản vẽ trắc dọc toàn cầu và mặt cắt ngang điển hình với tính năng Zoom/Pan thời gian thực.
    """)

# --- SECTION 2: THÔNG SỐ TUYẾN & AI TƯ VẤN ---
elif selected_ribbon == "THÔNG SỐ TUYẾN & AI TƯ VẤN":
    st.subheader("📥 Khai báo thông số đầu vào hệ thống")
    
    col_in1, col_in2 = st.columns(2)
    with col_in1:
        loai_c = st.radio("Chọn đối tượng vượt:", ["Vượt sông", "Vượt đường bộ"], horizontal=True, key="input_loai_c")
        st.session_state.design_data['loai_doi_tuong_vuot'] = loai_c
        
        goc_giao = st.number_input("Góc giao chéo (độ):", min_value=30.0, max_value=90.0, value=st.session_state.design_data['goc_giao'], step=1.0)
        st.session_state.design_data['goc_giao'] = goc_giao
        
        if loai_c == "Vượt sông":
            mien = st.selectbox("Khu vực:", ["1", "2"], format_func=lambda x: "Miền Bắc" if x=="1" else "Miền Nam")
            cap_s = st.selectbox("Cấp sông:", ["1", "2", "3", "4", "5", "6"], format_func=lambda x: f"Cấp {['I','II','III','IV','V','VI'][int(x)-1]}")
            loai_h = st.selectbox("Loại hình:", ["1", "2"], format_func=lambda x: "Kênh" if x=="1" else "Sông")
            b_khai_bao = 20.0
        else:
            loai_duong_v = st.selectbox("Cấp đường bị vượt:", ["Đường ô tô (Cấp I, II, III)", "Đường ô tô (Cấp còn lại)", "Đường cao tốc", "Đường cải tạo", "Đường xe thô sơ"])
            st.session_state.design_data['cap_duong_bi_vuot'] = loai_duong_v
            b_khai_bao = st.number_input("Bề rộng tĩnh không khai báo (B) - m:", value=st.session_state.design_data['B'], step=0.5)
            mien, cap_s, loai_h = "1", "1", "1"
            
    with col_in2:
        if loai_c == "Vượt sông":
            h_tn_tb = st.number_input("Cao độ tự nhiên trung bình (m):", value=st.session_state.design_data['h_tn_tb'], format="%.3f")
            h1 = st.number_input("MNCN (H1%):", value=st.session_state.design_data['MNCN'], format="%.3f")
            h5 = st.number_input("MNTT (H5%):", value=st.session_state.design_data['MNTT'], format="%.3f")
            h10 = st.number_input("MNTC (H10%):", value=st.session_state.design_data['MNTC'], format="%.3f")
            h98 = st.number_input("MNTN (H98%):", value=st.session_state.design_data['MNTN'], format="%.3f")
        else:
            h_tn_tb = st.number_input("Cao độ tự nhiên trung bình (m):", value=st.session_state.design_data['h_tn_tb'], format="%.3f", key="tn_db_tab2")
            h1 = st.number_input("Cao độ mặt đường bị vượt (m):", value=5.00, format="%.3f", key="overpass_height_tab2")
            h5, h10, h98 = h1, h1, h1

    st.subheader("📐 Yếu tố hình học trắc dọc tuyến")
    l_hinhhoc = st.selectbox("Chọn loại đường thiết kế:", ["Cao tốc", "O to", "Do thi"], key="main_type_tab2")

    if l_hinhhoc == "Cao tốc":
        d_hinhhoc = st.radio("Chọn địa hình:", options=["1", "2"], format_func=lambda x: "Đồng bằng" if x == "1" else "Địa hình khó khăn", key="ct_terrain_tab2")
        v_list = [120, 100] if d_hinhhoc == "1" else [80, 60]
        v_hinhhoc = st.selectbox("Vận tốc thiết kế Vtk (km/h):", options=v_list, key="ct_v_tab2")
        input_tra_cuu = v_hinhhoc
    elif l_hinhhoc == "O to":
        cap_duong_oto = st.selectbox("Chọn Cấp đường:", ["I", "II", "III", "IV", "V", "VI"], key="oto_cap_tab2")
        d_hinhhoc = st.radio("Chọn địa hình:", ["1", "2"], horizontal=True, format_func=lambda x: "Đồng bằng" if x == "1" else "Miền núi", key="oto_dh_tab2")
        input_tra_cuu = cap_duong_oto
    else:
        loai_dt = st.selectbox("Loại đường đô thị:", ["Trục chính đô thị", "Đường chính đô thị", "Đường khu vực", "Đường nội bộ"], key="dt_loai_tab2")
        cap_dt = st.selectbox("Cấp đường:", ["Đặc biệt", "Cấp I", "Cấp II"] if loai_dt == "Trục chính đô thị" else ["Cấp I", "Cấp II"], key="dt_cap_tab2")
        list_vtk = YTHH.get_vtk_goi_y_dothi(loai_dt, cap_dt)
        v_hinhhoc = st.radio("Chọn Vận tốc thiết kế Vtk (km/h) áp dụng:", options=list_vtk, horizontal=True, key="dt_v_tab2")
        d_hinhhoc = st.radio("Địa hình:", ["1", "2"], horizontal=True, format_func=lambda x: "Bằng phẳng" if x == "1" else "Đồi núi/Khó khăn", key="dt_dh_tab2")
        input_tra_cuu = v_hinhhoc

    res_geo = YTHH.tra_cuu_yeu_to_hinh_hoc(l_hinhhoc, input_tra_cuu, d_hinhhoc)
    if res_geo.get("status") == "success":
        chon_R = st.radio("Chọn bán kính đứng lồi áp dụng:", ["Tối thiểu thông thường", "Tối thiểu giới hạn"], horizontal=True, key="r_select_tab2")
        r_final = res_geo["R_loi_tt"] if chon_R == "Tối thiểu thông thường" else res_geo["R_loi_gh"]
        st.session_state.R_final = r_final

    st.divider()
    if st.button("🚀 Thực hiện Tính toán & Lưu thiết kế", use_container_width=True):
        res = TK.tra_cuu_tinh_khong_bridge(
            loai_cau=loai_c, mien=mien if loai_c=="Vượt sông" else None, cap_num=cap_s if loai_c=="Vượt sông" else None,
            loai_hinh=loai_h if loai_c=="Vượt sông" else None, loai_duong_vuot=loai_duong_v if loai_c=="Vượt đường bộ" else None,
            cap_oto=b_khai_bao if loai_c=="Vượt đường bộ" else None, h1=h1, h5=h5, h10=h10, h98=h98, h_tn_tb=h_tn_tb
        )
        alpha_rad = np.radians(goc_giao)
        res['B'] = round(res.get('B', 0) / np.sin(alpha_rad), 2) if goc_giao < 90 else res.get('B', 0)
        res['goc_giao'] = goc_giao
        res['h_tn_tb'] = h_tn_tb
        res['MNCN'], res['MNTT'], res['MNTC'], res['MNTN'] = h1, h5, h10, h98

        if res_geo.get("status") == "success":
            res['R_hinh_hoc'] = st.session_state.get('R_final', 5000)
            res['geo_logic'] = YTHH.tinh_toan_geo_logic(res, h_tn_tb if loai_c == "Vượt sông" else h1, res.get('day_dam', 0.0))
            imax_raw = res_geo.get('imax', '0')
            res['i_max_hinh_hoc'] = float(str(imax_raw).split('%')[0])
            res['bc'] = st.session_state.design_data.get('bc', 12.0)

            xlsx_path = os.path.join(os.path.dirname(__file__), "Girder.xlsx")
            models = GRD.train_bridge_ai_system(xlsx_path)
            if models:
                res['ai_result'] = GRD.predict_main_span(res['B'], goc_giao, res['bc'], "Đô thị" if loai_c == "Vượt đường bộ" else "Vượt sông", models, res['geo_logic']['L_cau'])
            st.session_state.design_data = res
            st.success("🎉 Đã đồng bộ dữ liệu hình học và dự báo AI thành công! Hãy chuyển sang Tab 'BẢN VẼ KỸ THUẬT TƯƠNG TÁC' để kiểm tra bản vẽ.")

# --- SECTION 3: BẢN VẼ KỸ THUẬT TƯƠNG TÁC (KHÔNG GIAN HIỂN THỊ CHÍNH) ---
elif selected_ribbon == "BẢN VẼ KỸ THUẬT TƯƠNG TÁC":
    st.subheader("🖼️ Hệ thống bản vẽ thiết kế công trình (Không gian hiển thị chính)")
    
    # THIẾT KẾ HỘP THOẠI KHAI BÁO NHANH (SECTION) NẰM GỌN GÀNG PHÍA TRÊN BẢN VẼ GIỐNG HÌNH CỦA BẠN
    with st.expander("🛠️ HỘP THOẠI KHAI BÁO & ĐIỀU CHỈNH NHANH THÔNG SỐ TRẮC DỌC", expanded=False):
        sec_col1, sec_col2, sec_col3 = st.columns(3)
        with sec_col1:
            st.markdown("**Thông số mặt cắt**")
            n_lan = st.number_input("Số làn xe:", min_value=2, value=2, key="sec_n_lan")
            w_le = st.number_input("Bề rộng dải an toàn (m):", value=0.5, key="sec_w_le")
            if st.button("🔄 Cập nhật kích thước Mặt cắt ngang", use_container_width=True):
                res_mcn_calc = MCN.thiet_ke_mcn_cau_web({"loai": st.session_state.design_data.get('loai_duong', 'Do thi'), "vtk": st.session_state.design_data.get('vtk', 60)})
                st.session_state.design_data['bc'] = res_mcn_calc['bc_cau']
                st.toast("Đã cập nhật bề rộng Bc mặt cắt ngang!")
        with sec_col2:
            st.markdown("**Bố trí nhịp từ AI**")
            if 'ai_result' in st.session_state.design_data:
                ai = st.session_state.design_data['ai_result']
                st.markdown(f"• Phương án: **Dầm {ai['loai_dam'].upper()}**")
                st.markdown(f"• Quy mô: **{ai['tong_so_nhip']} nhịp x {ai['chieu_dai']}m**")
                st.markdown(f"• Chiều cao kiến trúc: **{ai['chieu_cao']}m**")
            else:
                st.caption("Chưa có dữ liệu dự báo kết cấu AI.")
        with sec_col3:
            st.markdown("**Thông số kích thước mố trụ**")
            if 'geo_logic' in st.session_state.design_data:
                geo = st.session_state.design_data['geo_logic']
                st.markdown(f"• Khống chế mố trái: **{geo['x_mo_trai']:.2f} m**")
                st.markdown(f"• Khống chế mố phải: **{geo['x_mo_phai']:.2f} m**")
                st.markdown(f"• Tổng chiều dài L: **{geo['L_cau']:.2f} m**")
            else:
                st.caption("Chưa có dữ liệu hình học mố trụ.")

    # HỆ THỐNG TAB CON SONG SONG ĐỂ CHUYỂN ĐỔI BẢN VẼ VỚI VIEW RỘNG TỐI ĐA
    tab_trac_doc, tab_mcn_draw = st.tabs(["📊 Bản vẽ Trắc dọc toàn cầu", "📐 Bản vẽ Mặt cắt ngang điển hình"])
    
    with tab_trac_doc:
        try:
            # Nhúng đồ thị Plotly đối xứng phủ tràn toàn màn hình
            fig_plotly = PLOT.ve_trac_doc_cau(st.session_state.design_data)
            if fig_plotly is not None:
                st.plotly_chart(fig_plotly, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})
            else:
                st.warning("⚠️ Hệ thống bản vẽ trống. Vui lòng sang Tab 'THÔNG SỐ TUYẾN & AI TƯ VẤN' gõ nút Let's go trước!")
        except Exception as e:
            st.error(f"Lỗi khi dựng bản vẽ trắc dọc: {e}")
            
    with tab_mcn_draw:
        try:
            # Thiết lập thông số đầu vào cho cấu tạo mặt cắt ngang
            mcn_input_draw = {
                'bc_cau': float(st.session_state.design_data.get('bc', 12.0)),
                'w_lc': 0.5
            }
            fig_mn = PLOT.ve_mat_cat_ngang(mcn_input_draw)
            if fig_mn is not None:
                st.plotly_chart(fig_mn, use_container_width=True, config={'scrollZoom': True})
                
                # Hiển thị bảng kích thước kết cấu bổ trợ phía dưới bản vẽ hình học
                st.subheader("📋 Bảng tổng hợp kích thước mặt cắt ngang cầu")
                if 'design_data' in st.session_state:
                    res_mcn_show = MCN.thiet_ke_mcn_cau_web({"loai": st.session_state.design_data.get('loai_duong', 'Do thi'), "vtk": st.session_state.design_data.get('vtk', 60)})
                    st.code(res_mcn_show.get('mo_phong', 'Chưa có sơ đồ cấu tạo.'), language="text")
        except Exception as e:
            st.error(f"Lỗi khi dựng bản vẽ mặt cắt ngang: {e}")