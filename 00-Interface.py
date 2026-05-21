import streamlit as st
import pandas as pd
import numpy as np
import os
import importlib
import google.generativeai as genai
import fitz
from streamlit_option_menu import option_menu

# --- THIẾT LẬP LAYOUT GIAO DIỆN PHONG CÁCH CAD/EXCEL ---
st.set_page_config(layout="wide", page_title="Hệ thống Thiết kế Cầu tối ưu - UTH")

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
        st.sidebar.error("❌ Thiếu cấu hình GEMINI_API_KEY trong Secrets!")
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
                for page in doc:
                    knowledge_text += page.get_text()
            except:
                pass
    return knowledge_text if knowledge_text else "Không có tài liệu tiêu chuẩn nào được nạp."

if 'bridge_library' not in st.session_state:
    with st.spinner("📚 Đang nạp hệ thống tiêu chuẩn kỹ thuật Việt Nam..."):
        st.session_state.bridge_library = load_all_standards()

# --- DYNAMIC IMPORTS CÁC MODULE CHỨC NĂNG BÊN NGOÀI ---
try:
    DrawingUtils = importlib.import_module("00-Drawing_Utils")
    Geometry = importlib.import_module("02-Yeuto_Hinhhoc")
    GirderAI = importlib.import_module("05-Main_Girder")
except Exception as e:
    st.error(f"❌ Lỗi nạp File thành phần hệ thống: {e}")

# =========================================================================
# THIẾT KẾ THANH SIDEBAR TRÁI: DÀNH CHO PANEL TRỢ LÝ ẢO & THƯ VIỆN TIỆN ÍCH
# =========================================================================
with st.sidebar:
    st.markdown("### 🏛️ Đại học Giao thông vận tải TP.HCM")
    st.markdown("---")
    st.subheader("🤖 Bridge AI Assistant")
    
    # Khung hiển thị nội dung chat phụ trợ độc lập bên trái
    chat_container = st.container(height=350, border=True)
    with chat_container:
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Hỏi tôi về tiêu chuẩn hoặc kết cấu... ", key="sidebar_chat"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        chat_container.chat_message("user").write(prompt)
        
        try:
            design_info = st.session_state.get('design_data', "Chưa tiến hành chạy dự báo.")
            system_msg = f"""
            Bạn là chuyên gia tư vấn thiết kế cầu của UTH. 
            Sử dụng tri thức tiêu chuẩn sau: {st.session_state.bridge_library}
            Dữ liệu tính toán hiện tại: {design_info}
            """
            response = gemini_model.generate_content(f"{system_msg}\n\nCâu hỏi: {prompt}")
            ai_reply = response.text
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            chat_container.chat_message("assistant").write(ai_reply)
        except Exception as chat_err:
            st.error(f"Lỗi phản hồi AI: {chat_err}")

# =========================================================================
# 🏠 TẠO DẢI MENU RIBBON NẰM NGANG PHÍA TRÊN CÙNG CHUYÊN NGHIỆP (PHONG CÁCH CAD/EXCEL)
# =========================================================================
selected_ribbon = option_menu(
    menu_title=None, 
    options=["TAB TRANG CHỦ", "THÔNG SỐ TUYẾN & AI TƯ VẤN", "BẢN VẼ KỸ THUẬT TƯƠNG TÁC"],
    icons=["house", "cpu", "layout-text-window-reverse"], 
    menu_icon="cast", 
    default_index=1, # Mặc định mở luôn tab nhập liệu để thuận tiện thao tác
    orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "background-color": "#2c3e50", "border-radius": "0px"},
        "icon": {"color": "#f39c12", "font-size": "15px"}, 
        "nav-link": {
            "font-size": "13px", 
            "text-align": "center", 
            "margin": "0px", 
            "color": "white",
            "font-weight": "bold",
            "border-radius": "0px",
            "--hover-color": "#34495e"
        },
        "nav-link-selected": {"background-color": "#007acc"}, # Màu xanh bản quyền đặc trưng AutoCAD
    }
)

# Đường kẻ phân tách dải Ribbon và vùng làm việc
st.markdown("<hr style='margin-top: 0px; margin-bottom: 20px; border-color: #007acc;'>", unsafe_allow_html=True)

# Khởi tạo mô hình AI dầm cầu từ file Excel nền tảng
excel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Girder.xlsx")
bridge_models = GirderAI.train_bridge_ai_system(excel_path)

# =========================================================================
# LOGIC ĐIỀU HƯỚNG THEO CÁC LỰA CHỌN TRÊN RIBBON MENU
# =========================================================================

# --- TAB 1: TRANG CHỦ ---
if selected_ribbon == "TAB TRANG CHỦ":
    st.title("🚀 Hệ Thống Tối Ưu Hóa Thiết Kế Trắc Dọc & Kết Cấu Nhịp Cầu Bản Đường")
    st.write("---")
    st.markdown("""
    #### 📌 Giới thiệu phần mềm:
    Hệ thống tích hợp quy trình tính toán tự động các yếu tố hình học đường cong đứng theo Tiêu chuẩn thiết kế đường ô tô hiện hành, kết hợp thuật toán **Học máy Random Forest (AI)** để đưa ra giải pháp bố trí kết cấu nhịp tối ưu chi phí.
    
    #### ⚙️ Hướng dẫn thao tác nhanh:
    1. Click chọn tab **THÔNG SỐ TUYẾN & AI TƯ VẤN** trên thanh Ribbon để khai báo thông số công trình.
    2. Kiểm tra các bảng kết quả tính toán cao độ hình học và đề xuất kết cấu nhịp từ AI.
    3. Chuyển sang tab **BẢN VẼ KỸ THUẬT TƯƠNG TÁC** để xem bản vẽ trắc dọc toàn cầu trực quan hóa bằng đồ thị Plotly.
    """)

# --- TAB 2: THÔNG SỐ TUYẾN & AI TƯ VẤN ---
elif selected_ribbon == "THÔNG SỐ TUYẾN & AI TƯ VẤN":
    st.subheader("📥 Khai báo thông số đầu vào & Chạy xử lý")
    
    # Sử dụng bố cục 3 cột đều nhau để nhập liệu chuyên nghiệp
    in1, in2, in3 = st.columns(3)
    with in1:
        loai_tuyen = st.selectbox("Chọn Loại đường thiết kế:", ["O to", "Cao tốc", "Do thi"])
        if loai_tuyen == "O to":
            cap_duong = st.selectbox("Cấp đường nông thôn (TCVN 4054):", ["I", "II", "III", "IV", "V", "VI"])
            dia_hinh = st.radio("Dạng Địa hình:", [("1", "Đồng bằng / Bình nguyên"), ("2", "Vùng núi / Khó khăn")], format_func=lambda x: x[1])[0]
            vtk_final = None
        elif loai_tuyen == "Cao tốc":
            cap_duong = st.selectbox("Vận tốc thiết kế yêu cầu (km/h):", ["120", "100", "80", "60"])
            dia_hinh = "1"
            vtk_final = int(cap_duong)
        else:
            loai_dt = st.selectbox("Phân cấp đường đô thị (TCVN 13592):", ["Trục chính đô thị", "Đường chính đô thị", "Đường khu vực", "Đường nội bộ"])
            cap_dt = st.selectbox("Cấp kỹ thuật đô thị:", ["Đặc biệt", "Cấp I", "Cấp II"])
            vtks = Geometry.get_vtk_goi_y_dothi(loai_dt, cap_dt)
            vtk_final = st.selectbox("Vận tốc thiết kế gợi ý (km/h):", vtks)
            cap_duong = str(vtk_final)
            dia_hinh = "1"

    with in2:
        moitruong = st.selectbox("Môi trường xây dựng hạ tầng:", ["Vượt sông / Ngoài đô thị", "Trong đô thị / Cầu vượt nút giao"])
        env_label = "Đô thị" if "Trong đô thị" in moitruong else "Vượt sông"
        b_thong_thuy = st.number_input("Bề rộng thông thủy yêu cầu B (m):", min_value=4.0, value=15.0, step=0.5)
        h_tinh_khong = st.number_input("Chiều cao tĩnh không kỹ thuật H (m):", min_value=2.0, value=4.75, step=0.25)

    with in3:
        b_cau = st.number_input("Bề rộng toàn mặt cắt ngang cầu Bc (m):", min_value=6.0, value=12.0, step=0.5)
        goc_giao = st.slider("Góc giao chéo tuyến (Độ):", min_value=30, max_value=90, value=90)
        h_tn_tb = st.number_input("Cao độ tự nhiên trung bình sông/đường tuyệt đối (m):", value=2.15)

    st.markdown("---")
    
    # Thực hiện tra cứu nhanh từ tiêu chuẩn hình học thiết kế
    std_res = Geometry.tra_cuu_yeu_to_hinh_hoc(loai_tuyen, cap_duong, dia_hinh)
    
    if std_res["status"] == "success":
        v_calc = std_res["v_thiet_ke"]
        i_max_tcvn = std_res["imax"]
        
        # Gọi mô hình AI tính toán kết cấu nhịp
        ai_res = GirderAI.predict_main_span(h_tinh_khong, goc_giao, b_cau, env_label, bridge_models, L_cau_tong=120.0)
        
        # Ghép nối sang module phân tích cao độ hình học đối xứng của file 02
        geo_input = {
            'label': moitruong,
            'MNCN': 4.5, 'MNTT': 1.0, 'MNTC': 3.5, 'MNTN': 0.2,
            'B': b_thong_thuy, 'H': h_tinh_khong,
            'R_hinh_hoc': std_res["R_loi_tt"],
            'i_max_hinh_hoc': i_max_tcvn,
            'ai_result': ai_res
        }
        geo_output = Geometry.tinh_toan_geo_logic(geo_input, h_tn_tb, h_dam=ai_res['chieu_cao'], h_dap_yc=5.5)
        
        # Đóng gói dữ liệu vào Session State để chuyển tiếp dữ liệu sang Tab bản vẽ Plotly
        st.session_state.app_design_results = {
            'MNCN': 4.5, 'MNTT': 1.0, 'MNTC': 3.5, 'MNTN': 0.2, 'B': b_thong_thuy, 'H': h_tinh_khong, 'label': moitruong,
            'ai_result': ai_res, 'geo_logic': geo_output
        }
        st.session_state.design_data = f"Vtk={v_calc}km/h, LoaiDam={ai_res['loai_dam']}, L_nhip={ai_res['chieu_dai']}m, L_cau={geo_output['L_cau']:.2f}m"

        # HIỂN THỊ KẾT QUẢ TÍNH TOÁN RA MÀN HÌNH CHÍNH (Giao diện 2 cột cân xứng)
        out_col1, out_col2 = st.columns(2)
        with out_col1:
            st.success("📘 KẾT QUẢ TRA CỨU HÌNH HỌC TUYẾN (TCVN)")
            st.write(f"• **Tiêu chuẩn áp dụng:** {std_res['tieu_chuan']}")
            st.write(f"• **Vận tốc thiết kế Vtk:** {v_calc} km/h")
            st.write(f"• **Độ dốc dọc lớn nhất cho phép $i_{{max}}$:** {i_max_tcvn} %")
            st.write(f"• **Bán kính đường cong đứng lồi tối thiểu:** {std_res['R_loi_tt']} m")
            st.write(f"• **Chiều dài toàn cầu thiết kế lý tưởng:** {geo_output['L_cau']:.2f} m")

        with out_col2:
            st.info("🤖 GIẢI PHÁP KẾT CẤU NHỊP ĐỀ XUẤT TỪ AI")
            st.write(f"• **Kiểu kết cấu dầm chủ kiến nghị:** Dầm {ai_res['loai_dam'].upper()}")
            st.write(f"• **Sơ đồ chia nhịp toàn cầu:** {ai_res['tong_so_nhip']} nhịp × {ai_res['chieu_dai']} m")
            st.write(f"• **Chiều cao kiến trúc dầm H:** {ai_res['chieu_cao']} m")
            st.write(f"• **Bố trí số lượng dầm trên MCN:** {ai_res['so_luong_dam']} thanh dầm (Khoảng cách S = {ai_res['khoang_cach_dam']:.2f}m)")
            st.caption(f"📝 *Nhận xét chiến lược của AI:* {ai_res['ghi_chu']}")
    else:
        st.error(f"Lỗi hệ thống tra cứu: {std_res['message']}")

# --- TAB 3: BẢN VẼ KỸ THUẬT TƯƠNG TÁC ---
elif selected_ribbon == "BẢN VẼ KỸ THUẬT TƯƠNG TÁC":
    if 'app_design_results' not in st.session_state:
        st.warning("⚠️ Vui lòng chuyển qua Tab 'THÔNG SỐ TUYẾN & AI TƯ VẤN' nhập liệu và chạy tính toán trước!")
    else:
        st.subheader("🖼️ Hệ thống bản vẽ thiết kế công trình")
        
        # --- ĐÂY LÀ ĐOẠN PHÂN CHIA HỆ TAB CON GIỐNG LAYOUT CAD ---
        tab_trac_doc, tab_mcn = st.tabs(["📊 Bản vẽ Trắc dọc toàn cầu", "📐 Bản vẽ Mặt cắt ngang điển hình"])
        
        res_data = st.session_state.app_design_results
        
        with tab_trac_doc:
            st.markdown("**Sơ đồ trắc dọc cầu đối xứng hoàn hảo qua tim (0,0)**")
            fig_td = DrawingUtils.ve_trac_doc_cau(res_data)
            if fig_td:
                st.plotly_chart(fig_td, use_container_width=True, config={'scrollZoom': True, 'displaymodeBar': True})
            else:
                st.error("Không thể khởi tạo bản vẽ trắc dọc.")
                
        with tab_mcn:
            st.markdown("**Mặt cắt ngang kết cấu dầm và bố trí làn xe trên cầu**")
            mcn_input = {
                'bc_cau': res_data['geo_logic']['h_tn_tb'] * 0 + res_data['ai_result'].get('so_luong_dam', 5) * 0 + res_data['geo_logic'].get('y_base_goc', 0)*0 + 12.0, 
                'w_lc': 0.5
            }
            # Cập nhật thông số mặt cắt từ kết quả AI thực tế
            mcn_input['bc_cau'] = float(res_data['ai_result'].get('B_cầu_thực', 12.0))
            fig_mn = DrawingUtils.ve_mat_cat_ngang(mcn_input)
            if fig_mn:
                st.plotly_chart(fig_mn, use_container_width=True)