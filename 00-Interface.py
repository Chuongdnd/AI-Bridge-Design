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

# =========================================================================
# 🎨 🏙️ NHÚNG CSS NÂNG CAO: DIỆT SẠCH KHOẢNG ĐEN, CHỪA CHỖ CHO NÚT THANH BÊN (SIDEBAR)
# =========================================================================
# =========================================================================
# 🎨 🏙️ NHÚNG CSS NÂNG CAO: GIỮ NÚT SIDEBAR, ẨN SẠCH 3 KÝ HIỆU BÊN PHẢI VÀ THÊM TIÊU ĐỀ
# =========================================================================
st.markdown("""
    <style>
        /* 1. Thiết lập nền móng ứng dụng mượt mà */
        .stApp {
            background-color: #0e1117 !important;
        }

        /* 2. Cân chỉnh Header: Giữ chỗ cho nút Sidebar bên trái nhưng trong suốt */
        div[data-testid="stHeader"], header {
            background-color: transparent !important;
            box-shadow: none !important;
            height: 3.5rem !important;
            z-index: 99 !important;
        }

        /* 3. 🎯 TIÊU DIỆT SẠCH CỤM 3 KÝ HIỆU BÊN PHẢI (Deploy, GitHub, Menu 3 chấm) */
        div[data-testid="stActionButton"], 
        a[data-testid="stGitHubLink"], 
        #MainMenu {
            display: none !important;
        }

        /* 4. Thiết kế thanh Tiêu đề ghi đè (Top Custom Banner) sang trọng nằm dưới nút Sidebar */
        .custom-top-bar {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 3.5rem;
            background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%);
            border-bottom: 2px solid #007acc;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 98; /* Nằm dưới header để không đè lên nút Sidebar bên trái */
            box-shadow: 0px 4px 10px rgba(0,0,0,0.4);
        }
        
        .custom-top-title {
            color: #007acc !important;
            font-family: 'Arial', sans-serif;
            font-size: 1.3rem !important;
            font-weight: bold !important;
            letter-spacing: 1px;
            margin: 0 !important;
            padding: 0 !important;
            text-transform: uppercase;
            text-shadow: 0px 2px 4px rgba(0,0,0,0.5);
        }

        /* 5. Đẩy phân vùng nội dung chính xuống dưới thanh tiêu đề */
        .main .block-container {
            padding-top: 5rem !important;
            padding-bottom: 2rem !important;
            max-width: 98% !important;
        }

        /* 6. Định hình phân vùng hiển thị Tab bản vẽ */
        div[data-testid="stTabContent"] {
            background-color: #11151c !important;
            border: 1px solid #1e293b !important;
            border-radius: 6px !important;
            padding: 1.5rem !important;
            box-shadow: inset 0px 0px 15px rgba(0,0,0,0.5) !important;
        }
    </style>
    
    <div class="custom-top-bar">
        <h1 class="custom-top-title">🏗️ HỆ THỐNG THIẾT KẾ CẦU THÔNG MINH ỨNG DỤNG AI — UTH</h1>
    </div>
""", unsafe_allow_html=True)

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
    TV = importlib.import_module("00-Terrain_Viewer")
    importlib.reload(PLOT)
except Exception as e:
    st.error(f"Lỗi kết nối Module: {e}")

if 'design_data' not in st.session_state:
    st.session_state.design_data = {
        'day_dam': 0.0, 'khau_do_ngang': 0.0, 'bc': 12.0, 'loai_duong': "Do thi",
        'B': 20.0, 'H': 4.75, 'loai_doi_tuong_vuot': "Vượt sông", 'goc_giao': 90.0,
        'MNCN': 3.5, 'MNTT': 2.0, 'MNTC': 1.5, 'MNTN': 0.5, 'h_tn_tb': 0.0,
        'vtk': 60, 'i_max_hinh_hoc': 4.0, 'R_hinh_hoc': 5000,
        'geo_logic': {'L_cau': 120.0, 'x_mo_trai': -60.0, 'x_mo_phai': 60.0, 'y_mo': 1.5, 'h_tn_tb': 2.15, 'y_base_goc': 2.0},
        'ai_result': {'loai_dam': 'Super-T', 'tong_so_nhip': 3, 'chieu_dai': 40.0, 'chieu_cao': 1.75, 'so_luong_dam': 5, 'khoang_cach_dam': 2.2, 'ghi_chu': 'Phương án tối ưu từ AI.'}
    }

if 'chatbot_context' not in st.session_state:
    st.session_state.chatbot_context = "Chưa tiến hành chạy dự báo tính toán."

if 'current_tab' not in st.session_state:
    st.session_state.current_tab = "BẢN VẼ KỸ THUẬT TƯƠNG TÁC"

# =========================================================================
# ⚙️ ĐỊNH NGHĨA HỘP THOẠI KHAI BÁO SỐ LIỆU ĐỘC LẬP (OPTIONS WINDOW STYLE)
# =========================================================================
@st.dialog("⚙️ HỘP THOẠI KHAI BÁO THÔNG SỐ TUYẾN & THỦY VĂN", width="large")
def show_options_dialog():
    st.markdown("### 📥 Nhập các thông số hình học đầu vào công trình")
    sec_in1, sec_in2, sec_in3 = st.columns(3)
    
    with sec_in1:
        loai_c = st.radio("Chọn đối tượng vượt:", ["Vượt sông", "Vượt đường bộ"], horizontal=True)
        goc_giao = st.number_input("Góc giao chéo (độ):", min_value=30.0, max_value=90.0, value=st.session_state.design_data.get('goc_giao', 90.0), step=1.0)
        
        if loai_c == "Vượt sông":
            mien = st.selectbox("Khu vực miền:", ["1", "2"], format_func=lambda x: "Miền Bắc" if x=="1" else "Miền Nam")
            cap_s = st.selectbox("Cấp sông đường thủy:", ["1", "2", "3", "4", "5", "6"], format_func=lambda x: f"Cấp {['I','II','III','IV','V','VI'][int(x)-1]}")
            loai_h = st.selectbox("Loại hình thủy văn:", ["1", "2"], format_func=lambda x: "Kênh đào" if x=="1" else "Sông tự nhiên")
            b_khai_bao = 20.0
            loai_duong_v = None
        else:
            loai_duong_v = st.selectbox("Cấp đường bộ bị vượt:", ["Đường ô tô (Cấp I, II, III)", "Đường ô tô (Cấp còn lại)", "Đường cao tốc", "Đường cải tạo", "Đường xe thô sơ"])
            b_khai_bao = st.number_input("Bề rộng tĩnh không yêu cầu B (m):", value=st.session_state.design_data.get('B', 20.0), step=0.5)
            mien, cap_s, loai_h = "1", "1", "1"

    with sec_in2:
        st.markdown("**Số liệu cao độ hình học / Thủy văn (m)**")
        h_tn_tb = st.number_input("Cao độ tự nhiên trung bình:", value=st.session_state.design_data.get('h_tn_tb', 2.15), format="%.3f")
        if loai_c == "Vượt sông":
            h1 = st.number_input("Cao độ MNCN (H1%):", value=st.session_state.design_data.get('MNCN', 3.50), format="%.3f")
            h5 = st.number_input("Cao độ MNTT (H5%):", value=st.session_state.design_data.get('MNTT', 2.00), format="%.3f")
            h10 = st.number_input("Cao độ MNTC (H10%):", value=st.session_state.design_data.get('MNTC', 1.50), format="%.3f")
            h98 = st.number_input("Cao độ MNTN (H98%):", value=st.session_state.design_data.get('MNTN', 0.50), format="%.3f")
        else:
            h1 = st.number_input("Cao độ mặt đường bị vượt:", value=5.00, format="%.3f")
            h5, h10, h98 = h1, h1, h1

    with sec_in3:
        st.markdown("**Tiêu chuẩn hình học trắc dọc tuyến**")
        l_hinhhoc = st.selectbox("Loại đường thiết kế:", ["Cao tốc", "O to", "Do thi"])
        
        if l_hinhhoc == "Cao tốc":
            d_hinhhoc = st.radio("Địa hình:", options=["1", "2"], format_func=lambda x: "Đồng bằng" if x == "1" else "Khó khăn")
            v_list = [120, 100] if d_hinhhoc == "1" else [80, 60]
            v_hinhhoc = st.selectbox("Vận tốc thiết kế Vtk (km/h):", options=v_list)
            input_tra_cuu = v_hinhhoc
        elif l_hinhhoc == "O to":
            cap_duong_oto = st.selectbox("Cấp đường ô tô:", ["I", "II", "III", "IV", "V", "VI"])
            d_hinhhoc = st.radio("Địa hình vùng:", ["1", "2"], format_func=lambda x: "Đồng bằng" if x == "1" else "Miền núi")
            input_tra_cuu = cap_duong_oto
        else:
            loai_dt = st.selectbox("Phân loại đường đô thị:", ["Trục chính đô thị", "Đường chính đô thị", "Đường khu vực", "Đường nội bộ"])
            cap_dt = st.selectbox("Cấp kỹ thuật kỹ sư:", ["Đặc biệt", "Cấp I", "Cấp II"] if loai_dt == "Trục chính đô thị" else ["Cấp I", "Cấp II"])
            list_vtk = YTHH.get_vtk_goi_y_dothi(loai_dt, cap_dt)
            v_hinhhoc = st.radio("Vận tốc thiết kế Vtk:", options=list_vtk, horizontal=True)
            d_hinhhoc = st.radio("Địa hình đô thị:", ["1", "2"], format_func=lambda x: "Bằng phẳng" if x == "1" else "Khó khăn")
            input_tra_cuu = v_hinhhoc

        b_cau = st.number_input("Bề rộng Bc mặt cắt cầu (m):", min_value=6.0, value=st.session_state.design_data.get('bc', 12.0), step=0.5)

    res_geo = YTHH.tra_cuu_yeu_to_hinh_hoc(l_hinhhoc, input_tra_cuu, d_hinhhoc)
    r_final_calc = 5000
    if res_geo.get("status") == "success":
        r_final_calc = res_geo["R_loi_tt"]

    st.markdown("---")
    
    if st.button("💾 OK - Áp dụng cấu hình và Chạy dự báo AI", use_container_width=True, type="primary"):
        with st.spinner("⚡ Đang cập nhật dữ liệu..."):
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
                res['R_hinh_hoc'] = r_final_calc
                res['geo_logic'] = YTHH.tinh_toan_geo_logic(res, h_tn_tb if loai_c == "Vượt sông" else h1, res.get('day_dam', 0.0))
                imax_raw = res_geo.get('imax', '0')
                res['i_max_hinh_hoc'] = float(str(imax_raw).split('%')[0])
                res['bc'] = b_cau
                res['loai_duong'] = l_hinhhoc
                res['vtk'] = res_geo.get("v_thiet_ke", 60)

                xlsx_path = os.path.join(os.path.dirname(__file__), "Girder.xlsx")
                models = GRD.train_bridge_ai_system(xlsx_path)
                if models:
                    res['ai_result'] = GRD.predict_main_span(res['B'], goc_giao, res['bc'], "Đô thị" if loai_c == "Vượt đường bộ" else "Vượt sông", models, res['geo_logic']['L_cau'])
                
                st.session_state.design_data = res
                st.session_state.chatbot_context = f"Vtk={res['vtk']}km/h, LoaiDam={res['ai_result']['loai_dam']}, L_nhip={res['ai_result']['chieu_dai']}m, L_cau={res['geo_logic']['L_cau']:.2f}m"
                
                st.session_state.current_tab = "BẢN VẼ KỸ THUẬT TƯƠNG TÁC"
                st.rerun()

# =========================================================================
# 🏗️ BỌC VÙNG ĐIỀU KHIỂN VÀO KHUNG HTML MANG ID ĐỂ GHIM CỨNG (FREEZE PANEL)
# =========================================================================
st.markdown('<div id="custom-ribbon-container">', unsafe_allow_html=True)

ribbon_options = ["THUYẾT MINH", "BẢN VẼ KỸ THUẬT"]
default_idx = ribbon_options.index(st.session_state.current_tab) if st.session_state.current_tab in ribbon_options else 1

selected_ribbon = option_menu(
    menu_title=None, 
    options=ribbon_options,
    icons=["house", "layout-text-window-reverse"], 
    menu_icon="cast", 
    default_index=default_idx,
    orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "background-color": "#1e1e1e", "border-radius": "0px"},
        "icon": {"color": "#f39c12", "font-size": "14px"}, 
        "nav-link": {
            "font-size": "13px", "text-align": "center", "margin": "0px", "color": "white",
            "font-weight": "bold", "border-radius": "0px", "--hover-color": "#333333"
        },
        "nav-link-selected": {"background-color": "#007acc"},
    }
)
st.session_state.current_tab = selected_ribbon
st.markdown("<hr style='margin-top: 0px; margin-bottom: 10px; border-color: #007acc;'>", unsafe_allow_html=True)

# Bố trí hàng nút bấm Options và Dòng thông báo số liệu hiện hành nằm ngay trong khối đóng băng
if selected_ribbon == "BẢN VẼ KỸ THUẬT":
    ctrl_col1, ctrl_col2 = st.columns([1, 4])
    with ctrl_col1:
        if st.button("⚙️ OPTIONS - KHAI BÁO SỐ LIỆU", use_container_width=True, type="secondary"):
            show_options_dialog()
            
    with ctrl_col2:
        if 'ai_result' in st.session_state.design_data:
            ai_p = st.session_state.design_data['ai_result']
            geo_p = st.session_state.design_data['geo_logic']
            st.markdown(f"<div style='padding-top: 5px; font-size:13px;'>📊 <b>Thông số hiện hành:</b> Chiều dài L = <b>{geo_p['L_cau']:.2f}m</b> | Kết cấu nhịp: <b>{ai_p['tong_so_nhip']} nhịp x {ai_p['chieu_dai']}m (Dầm {ai_p['loai_dam'].upper()})</b> | Chiều cao H = <b>{ai_p['chieu_cao']}m</b></div>", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True) # ĐÓNG KHUNG CONTAINER GHIM CỨNG

# --- THANH SIDEBAR TRÁI (Đã khôi phục hoàn toàn nút thu phóng góc trên) ---
with st.sidebar:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(current_dir, "Images", "UTH.jpg")
    if os.path.exists(logo_path):
        st.image(logo_path, width=280)
    
    st.write("👤 **SVTH:** Chương DND")
    st.write("👨‍🏫 **GVHD:** T.S Nguyễn Văn Hiển")
    st.caption("🎓 *Đề tài:* Tích hợp AI và BIM tự động hóa thiết kế cầu đường bộ")
    
    st.markdown("---")
    st.subheader("🤖 Bridge AI Assistant")
    chat_container = st.container(height=220, border=True)
    with chat_container:
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Hỏi tôi về thiết kế...", key="sidebar_chat"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        try:
            design_info = st.session_state.chatbot_context
            system_msg = f"Bạn là chuyên gia thiết kế cầu UTH. Tri thức: {st.session_state.bridge_library}. Dữ liệu: {design_info}"
            response = gemini_model.generate_content(f"{system_msg}\n\nCâu hỏi: {prompt}")
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            st.rerun()
        except Exception as e:
            st.error(f"Lỗi AI: {e}")

# =========================================================================
# VÙNG KHÔNG GIAN ĐỒ HỌA BẢN VẼ TRẮC DỌC & MẶT CẮT NGANG
# =========================================================================
if selected_ribbon == "THUYẾT MINH":
    st.title("🏗️ Hệ thống Tự động hóa Thiết kế và Tối ưu hóa Kết cấu Cầu")
    st.write("---")
    st.markdown("""
    ### Ứng dụng tích toán kỹ thuật thông minh UTH
    * Bấm chọn tab **BẢN VẼ KỸ THUẬT** để vào không gian thiết kế chính.
    """)

elif selected_ribbon == "BẢN VẼ KỸ THUẬT":
    
    # 1. Chèn khung tải file .NTD lên đỉnh trang Workspace
    st.markdown("##### 📥 Nạp Cơ sở dữ liệu Khảo sát Địa hình Thực địa")
    file_khao_sat = st.file_uploader("Kéo và thả file .NTD trắc dọc trắc ngang tại đây", type=["ntd"])
    st.markdown("---")
    
    # 2. Kiểm tra trạng thái file để chia nhánh hiển thị Tab con độc lập
    if file_khao_sat is not None:
        df_geology = TV.parse_ntd_file(file_khao_sat)
        st.success(f"⚡ Hệ thống đã xử lý thành công {len(df_geology)} điểm mia địa hình thực tế!")
        
        # Nhóm 4 Tab con khi CÓ file khảo sát
        tab_dia_hinh_3d, tab_trac_doc, tab_mcn_draw = st.tabs([
            "🏔️ Mô hình Địa hình 3D",
            "📊 Bản vẽ Trắc dọc toàn cầu (Full View)", 
            "📐 Bản vẽ Mặt cắt ngang điển hình"
        ])
                   
        with tab_dia_hinh_3d:
            # Thanh slider và hàm vẽ được căn lề thẳng hàng tuyệt đối
            he_so_z = st.slider("📐 Phóng đại trục đứng (Nhìn rõ địa hình):", 0.01, 1.00, 0.25, step=0.01)
            fig_3d = TV.ve_dia_hinh_3d(df_geology, he_so_z=he_so_z)
            if fig_3d: st.plotly_chart(fig_3d, use_container_width=True)
            
        with tab_trac_doc:
            try:
                fig_plotly = PLOT.ve_trac_doc_cau(st.session_state.design_data)
                if fig_plotly is not None:
                    st.plotly_chart(fig_plotly, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})
            except Exception as e:
                st.error(f"Lỗi bản vẽ trắc dọc: {e}")
                
        with tab_mcn_draw:
            try:
                mcn_input_draw = {
                    'bc_cau': float(st.session_state.design_data.get('bc', 12.0)),
                    'w_lc': 0.5
                }
                fig_mn = PLOT.ve_mat_cat_ngang(mcn_input_draw)
                if fig_mn is not None:
                    st.plotly_chart(fig_mn, use_container_width=True, config={'scrollZoom': True})
                    
                    st.subheader("📋 Cấu tạo chi tiết các lớp mặt cắt")
                    res_mcn_show = MCN.thiet_ke_mcn_cau_web({"loai": st.session_state.design_data.get('loai_duong', 'Do thi'), "vtk": st.session_state.design_data.get('vtk', 60)})
                    st.code(res_mcn_show.get('mo_phong', 'Chưa có sơ đồ cấu tạo.'), language="text")
            except Exception as e:
                st.error(f"Lỗi bản vẽ mặt cắt ngang: {e}")
                
    else:
        # Nhóm 2 Tab mặc định khi CHƯA CÓ file khảo sát
        tab_trac_doc, tab_mcn_draw = st.tabs([
            "📊 Bản vẽ Trắc dọc toàn cầu (Full View)", 
            "📐 Bản vẽ Mặt cắt ngang điển hình"
        ])
        
        with tab_trac_doc:
            try:
                fig_plotly = PLOT.ve_trac_doc_cau(st.session_state.design_data)
                if fig_plotly is not None:
                    st.plotly_chart(fig_plotly, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})
            except Exception as e:
                st.error(f"Lỗi bản vẽ trắc dọc: {e}")
                
        with tab_mcn_draw:
            try:
                mcn_input_draw = {
                    'bc_cau': float(st.session_state.design_data.get('bc', 12.0)),
                    'w_lc': 0.5
                }
                fig_mn = PLOT.ve_mat_cat_ngang(mcn_input_draw)
                if fig_mn is not None:
                    st.plotly_chart(fig_mn, use_container_width=True, config={'scrollZoom': True})
                    
                    st.subheader("📋 Cấu tạo chi tiết các lớp mặt cắt")
                    res_mcn_show = MCN.thiet_ke_mcn_cau_web({"loai": st.session_state.design_data.get('loai_duong', 'Do thi'), "vtk": st.session_state.design_data.get('vtk', 60)})
                    st.code(res_mcn_show.get('mo_phong', 'Chưa có sơ đồ cấu tạo.'), language="text")
            except Exception as e:
                st.error(f"Lỗi bản vẽ mặt cắt ngang: {e}")