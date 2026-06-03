import streamlit as st
import pandas as pd
import numpy as np
import os
import importlib
import google.generativeai as genai
import fitz
from streamlit_option_menu import option_menu
import plotly.graph_objects as go

# --- THIẾT LẬP TRANG (CHỈ MỘT LẦN) ---
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

if 'bridge_library' not in st.session_state:
    with st.spinner("📚 Đang nạp hệ thống tiêu chuẩn cầu đường..."):
        st.session_state.bridge_library = load_all_standards()

# --- KẾT NỐI HỆ THỐNG MODULES THÀNH PHẦN ---
try:
    TK   = importlib.import_module("01-Tinh_khong")
    YTHH = importlib.import_module("02-Yeuto_Hinhhoc")
    MCN  = importlib.import_module("03-MatCatNgang")
    GRD  = importlib.import_module("05-Main_Girder")    # Legacy girder (dùng cho bản vẽ)
    KCN  = importlib.import_module("06-AI_KetCauNhip")  # AI Kết cấu nhịp v2
    MOT  = importlib.import_module("07-AI_MoTru")       # AI Mố – Trụ v2
    MONG = importlib.import_module("08-AI_Mong")        # Móng (rule-based)
    PLOT = importlib.import_module("00-Drawing_Utils")
    TV   = importlib.import_module("00-Terrain_Viewer")
    TC   = importlib.import_module("04-Pier-test")
    importlib.reload(PLOT)
except Exception as e:
    st.error(f"Lỗi kết nối Module: {e}")
    st.stop()

if 'design_data' not in st.session_state:
    st.session_state.design_data = {
        'day_dam': 0.0, 'khau_do_ngang': 0.0, 'bc': 12.0, 'loai_duong': "Do thi",
        'B': 20.0, 'H': 4.75, 'loai_doi_tuong_vuot': "Vượt sông", 'goc_giao': 90.0,
        'MNCN': 3.5, 'MNTT': 2.0, 'MNTC': 1.5, 'MNTN': 0.5, 'h_tn_tb': 0.0,
        'cap_song': 'VI', 'vtk': 60, 'i_max_hinh_hoc': 4.0, 'R_hinh_hoc': 5000,
        'geo_logic': {'L_cau': 120.0, 'x_mo_trai': -60.0, 'x_mo_phai': 60.0, 'y_mo': 1.5, 'h_tn_tb': 2.15, 'y_base_goc': 2.0},
        'ai_result': {'loai_dam': 'Super-T', 'tong_so_nhip': 3, 'chieu_dai': 40.0, 'chieu_cao': 1.75, 'so_luong_dam': 5, 'khoang_cach_dam': 2.2, 'ghi_chu': 'Phương án tối ưu từ AI.'},
        'kcn_result': None,
        'tru_result': None,
        'mong_result': None,
    }

if 'chatbot_context' not in st.session_state:
    st.session_state.chatbot_context = "Chưa tiến hành chạy dự báo tính toán."

if 'current_tab' not in st.session_state:
    st.session_state.current_tab = "BẢN VẼ KỸ THUẬT TƯƠNG TÁC"

# =========================================================================
# ⚙️ HỘP THOẠI KHAI BÁO SỐ LIỆU
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
            x_tim_clearance = st.number_input("📍 Lý trình tim tĩnh không (m)", value=0.0, step=1.0, format="%.2f", key="x_tim_clearance")
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
        with st.spinner("⚡ Đang chạy toàn bộ AI pipeline..."):
            # ── Bước 1: Tĩnh không ───────────────────────────────────────────
            res = TK.tra_cuu_tinh_khong_bridge(
                loai_cau=loai_c, mien=mien if loai_c=="Vượt sông" else None,
                cap_num=cap_s if loai_c=="Vượt sông" else None,
                loai_hinh=loai_h if loai_c=="Vượt sông" else None,
                loai_duong_vuot=loai_duong_v if loai_c=="Vượt đường bộ" else None,
                cap_oto=b_khai_bao if loai_c=="Vượt đường bộ" else None,
                h1=h1, h5=h5, h10=h10, h98=h98, h_tn_tb=h_tn_tb
            )
            alpha_rad = np.radians(goc_giao)
            res['B'] = round(res.get('B', 0) / np.sin(alpha_rad), 2) if goc_giao < 90 else res.get('B', 0)
            res['goc_giao'] = goc_giao
            res['h_tn_tb'] = h_tn_tb
            res['MNCN'], res['MNTT'], res['MNTC'], res['MNTN'] = h1, h5, h10, h98
            res['cap_song'] = cap_s if loai_c == "Vượt sông" else ""
            res['loai_doi_tuong_vuot'] = loai_c

            if res_geo.get("status") == "success":
                # ── Bước 2: Hình học ─────────────────────────────────────────
                res['R_hinh_hoc'] = r_final_calc
                res['geo_logic']  = YTHH.tinh_toan_geo_logic(
                    res, h_tn_tb if loai_c == "Vượt sông" else h1,
                    res.get('day_dam', 0.0), x_tim_clearance=x_tim_clearance
                )
                imax_raw = res_geo.get('imax', '0')
                res['i_max_hinh_hoc'] = float(str(imax_raw).split('%')[0])
                res['bc']         = b_cau
                res['loai_duong'] = l_hinhhoc
                res['vtk']        = res_geo.get("v_thiet_ke", 60)

                L_cau    = res['geo_logic'].get('L_cau', None)
                moi_tr   = "Đô thị" if loai_c == "Vượt đường bộ" else "Vượt sông"
                xlsx_path = os.path.join(os.path.dirname(__file__), "Girder.xlsx")
                csv_path  = os.path.join(os.path.dirname(__file__), "Phan loai Tru.csv")

                # ── Bước 3 (legacy): Dầm — dùng cho bản vẽ kỹ thuật ─────────
                grd_models = GRD.train_bridge_ai_system(xlsx_path)
                if grd_models:
                    res['ai_result'] = GRD.predict_main_span(
                        b_tk=res['B'], goc=goc_giao, b_cau=res['bc'],
                        env=moi_tr, models=grd_models,
                        L_cau_tong=L_cau, method='auto'
                    )

                # ── Bước 4: AI Kết cấu nhịp (v2, đầy đủ đặc trưng) ──────────
                kcn_models = KCN.train_kcn_ai(xlsx_path)
                if kcn_models:
                    res['kcn_result'] = KCN.predict_kcn(
                        B_tk=res['B'], H_tk=res.get('H', 3.5),
                        goc=goc_giao, B_cau=res['bc'],
                        moi_truong=moi_tr, L_cau_tong=L_cau,
                        models=kcn_models, method='auto'
                    )
                else:
                    res['kcn_result'] = None

                # ── Bước 5: AI Mố – Trụ ──────────────────────────────────────
                pier_models = MOT.train_pier_ai(csv_path)
                loai_dam_cho_tru = (
                    res['kcn_result']['loai_dam'] if res.get('kcn_result')
                    else res.get('ai_result', {}).get('loai_dam', 'Super-T')
                )
                H_dam_est = (
                    res['kcn_result']['chieu_cao_dam'] if res.get('kcn_result')
                    else res.get('ai_result', {}).get('chieu_cao', 1.75)
                )
                # Ước tính chiều cao trụ từ cao độ
                H_tru_est, cao_day_dam, cao_mat_cau = MOT.estimate_pier_height(
                    MNCN=h1, H_tinh_khong=res.get('H', 3.5),
                    H_dam=H_dam_est, MNTN=h98
                )
                res['H_tru_est']  = H_tru_est
                res['cao_day_dam'] = cao_day_dam
                res['cao_mat_cau'] = cao_mat_cau

                is_urban  = 1 if loai_c == "Vượt đường bộ" else 0
                is_river  = 1 if loai_c == "Vượt sông"    else 0
                res['tru_result'] = MOT.predict_pier(
                    vtk=res['vtk'], B_cau=res['bc'],
                    H_tru=H_tru_est, is_urban=is_urban,
                    is_river=is_river, cap_song=res['cap_song'],
                    loai_dam=loai_dam_cho_tru, models=pier_models
                )

                # ── Bước 6: Móng cầu (rule-based) ────────────────────────────
                loai_tru_str = (
                    res['tru_result']['loai_tru'] if res.get('tru_result')
                    else 'Khung 2 cột'
                )
                res['mong_result'] = MONG.predict_foundation(
                    H_tru=H_tru_est, loai_tru=loai_tru_str,
                    is_river=is_river, cap_song=res['cap_song'],
                    B_cau=res['bc'], vtk=res['vtk'],
                    L_nhip=res.get('kcn_result', {}).get('chieu_dai') if res.get('kcn_result') else None
                )

                st.session_state.design_data = res
                kcn = res.get('kcn_result') or res.get('ai_result', {})
                st.session_state.chatbot_context = (
                    f"Vtk={res['vtk']}km/h | "
                    f"LoaiDam={kcn.get('loai_dam','?')} | "
                    f"L_nhip={kcn.get('chieu_dai','?')}m | "
                    f"L_cau={res['geo_logic']['L_cau']:.1f}m | "
                    f"LoaiTru={res.get('tru_result',{}).get('loai_tru','?')} | "
                    f"LoaiMong={res.get('mong_result',{}).get('loai_mong','?')}"
                )
                st.session_state.current_tab = "THUYẾT MINH"
                st.rerun()

# =========================================================================
# BỌC VÙNG ĐIỀU KHIỂN VÀO KHUNG HTML GHIM CỨNG
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

# Hàng nút bấm và thông số hiện hành
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

st.markdown('</div>', unsafe_allow_html=True)

# --- THANH SIDEBAR TRÁI ---
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
# VÙNG HIỂN THỊ CHÍNH
# =========================================================================
if selected_ribbon == "THUYẾT MINH":
    d = st.session_state.design_data
    kcn  = d.get('kcn_result')
    tru  = d.get('tru_result')
    mong = d.get('mong_result')

    # Nếu chưa chạy AI, hiển thị hướng dẫn
    if kcn is None and tru is None:
        st.title("🏗️ Hệ thống Tự động hóa Thiết kế và Tối ưu hóa Kết cấu Cầu")
        st.info("👆 Nhấn **BẢN VẼ KỸ THUẬT** → **⚙️ OPTIONS** → điền thông số và nhấn **OK** để chạy toàn bộ AI pipeline.")
        st.markdown("""
**Luồng tính toán:**
1. 📐 **Tĩnh không** — tra cứu theo cấp sông / loại đường bị vượt (TCVN 8818)
2. 📏 **Hình học trắc dọc** — độ dốc, bán kính đường cong (TCVN 4054 / 5729 / 13592)
3. 🛣️ **Mặt cắt ngang** — bề rộng, số làn, lề bộ hành
4. 🤖 **AI Kết cấu nhịp** — loại dầm, nhịp, chiều cao dầm, bố trí dầm ngang
5. 🤖 **AI Trụ cầu** — phân loại trụ theo Vtk, B_cầu, H_trụ, môi trường
6. 📋 **Móng cầu** — gợi ý loại cọc, đường kính, chiều dài theo TCVN 10304
        """)
        st.stop()

    st.title("📄 Thuyết minh Tính toán Thiết kế Cầu")
    st.caption(f"Xuất bởi Hệ thống AI UTH — {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}")
    st.markdown("---")

    # ── I. THÔNG SỐ ĐẦU VÀO ──────────────────────────────────────────────
    with st.expander("**I. THÔNG SỐ ĐẦU VÀO CÔNG TRÌNH**", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Loại công trình**")
            st.write(f"Đối tượng vượt : **{d.get('loai_doi_tuong_vuot','—')}**")
            st.write(f"Loại đường     : {d.get('loai_duong','—')}")
            st.write(f"Vtk            : **{d.get('vtk',0)} km/h**")
            st.write(f"Góc giao chéo  : {d.get('goc_giao',90)}°")
            if d.get('cap_song'):
                st.write(f"Cấp sông ĐTNĐ  : Cấp {d['cap_song']}")
        with c2:
            st.markdown("**Cao độ thủy văn (m)**")
            st.write(f"MNCN (H1%)  : {d.get('MNCN',0):.3f} m")
            st.write(f"MNTT (H5%)  : {d.get('MNTT',0):.3f} m")
            st.write(f"MNTC (H10%) : {d.get('MNTC',0):.3f} m")
            st.write(f"MNTN (H98%) : {d.get('MNTN',0):.3f} m")
            st.write(f"CĐTN trung bình: {d.get('h_tn_tb',0):.3f} m")
        with c3:
            st.markdown("**Bề rộng mặt cắt**")
            st.write(f"Tĩnh không B : **{d.get('B',0):.2f} m**")
            st.write(f"Tĩnh không H : **{d.get('H',0):.2f} m**")
            st.write(f"Bề rộng Bc   : {d.get('bc',0):.1f} m")
            geo = d.get('geo_logic', {})
            st.write(f"Chiều dài cầu: **{geo.get('L_cau',0):.1f} m**")

    # ── II. KẾT CẤU NHỊP (AI) ────────────────────────────────────────────
    with st.expander("**II. KẾT CẤU NHỊP — Dầm chính (AI v2)**", expanded=True):
        if kcn:
            kc1, kc2 = st.columns([3, 2])
            with kc1:
                st.markdown(f"### Loại dầm: **{kcn['loai_dam'].upper()}**")
                st.markdown(f"Sơ đồ nhịp: **{kcn['tong_so_nhip']} nhịp × {kcn['chieu_dai']} m**")
                st.table(pd.DataFrame({
                    "Thông số": [
                        "Chiều dài nhịp",
                        "Chiều cao dầm",
                        "Tỉ lệ L/H",
                        "Số lượng dầm / MCN",
                        "Khoảng cách tim dầm",
                        "Phần hẫng (overhang)",
                        "Tổng số nhịp",
                    ],
                    "Giá trị": [
                        f"{kcn['chieu_dai']} m",
                        f"{kcn['chieu_cao_dam']} m",
                        f"{kcn['ti_le_L_H']} (tối ưu 17–22)",
                        f"{kcn['so_luong_dam']} dầm",
                        f"{kcn['khoang_cach_dam']} m",
                        f"{kcn['overhang']} m",
                        f"{kcn['tong_so_nhip']} nhịp",
                    ],
                }))
            with kc2:
                conf = kcn.get('do_tin_cay', 0)
                color = "#27ae60" if conf >= 70 else ("#f39c12" if conf >= 50 else "#e74c3c")
                st.markdown(f"""
<div style='background:{color};padding:16px;border-radius:8px;text-align:center'>
<span style='color:white;font-size:36px;font-weight:bold'>{conf:.0f}%</span><br>
<span style='color:white'>Độ tin cậy AI</span>
</div>
                """, unsafe_allow_html=True)
                st.caption(f"Phương pháp: {kcn.get('phuong_phap','AUTO')}")
                st.info(kcn.get('ghi_chu', ''))
        else:
            st.warning("Chưa có kết quả AI kết cấu nhịp.")

    # ── III. TRỤ CẦU (AI) ────────────────────────────────────────────────
    with st.expander("**III. TRỤ CẦU — Phân loại & kích thước (AI v2)**", expanded=True):
        if tru:
            tc1, tc2 = st.columns([3, 2])
            with tc1:
                st.markdown(f"### Loại trụ: **{tru['loai_tru']}**")
                H_tru = d.get('H_tru_est', 0)
                cao_dd = d.get('cao_day_dam', 0)
                cao_mc = d.get('cao_mat_cau', 0)
                st.table(pd.DataFrame({
                    "Thông số": [
                        "Chiều cao trụ (ước tính)",
                        "Cao độ đáy dầm (ước tính)",
                        "Cao độ mặt cầu (ước tính)",
                        "Số trụ giữa",
                    ],
                    "Giá trị": [
                        f"{H_tru:.2f} m",
                        f"{cao_dd:.3f} m",
                        f"{cao_mc:.3f} m",
                        f"{max(0, kcn['tong_so_nhip'] - 1) if kcn else '—'} trụ",
                    ],
                }))
                if tru.get('xep_hang'):
                    st.markdown("**Top phương án dự báo:**")
                    for r in tru['xep_hang']:
                        bar = "█" * int(r['xac_suat'] / 5)
                        st.text(f"  {r['loai']:25s} {bar}  {r['xac_suat']:.0f}%")
            with tc2:
                conf_tru = tru.get('do_tin_cay', 0)
                color_tru = "#27ae60" if conf_tru >= 70 else ("#f39c12" if conf_tru >= 50 else "#e74c3c")
                if conf_tru > 0:
                    st.markdown(f"""
<div style='background:{color_tru};padding:16px;border-radius:8px;text-align:center'>
<span style='color:white;font-size:36px;font-weight:bold'>{conf_tru:.0f}%</span><br>
<span style='color:white'>Độ tin cậy AI</span>
</div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
<div style='background:#95a5a6;padding:16px;border-radius:8px;text-align:center'>
<span style='color:white;font-size:18px'>Quy tắc kinh nghiệm</span>
</div>
                    """, unsafe_allow_html=True)
                st.caption(tru.get('ghi_chu', ''))
        else:
            st.warning("Chưa có kết quả AI trụ cầu.")

    # ── IV. MÓNG CẦU ─────────────────────────────────────────────────────
    with st.expander("**IV. MÓNG CẦU — Gợi ý loại cọc (TCVN 10304)**", expanded=True):
        if mong:
            mc1, mc2 = st.columns(2)
            with mc1:
                st.markdown(f"### Loại móng: **{mong['loai_mong']}**")
                st.table(pd.DataFrame({
                    "Thông số": [
                        "Đường kính cọc",
                        "Chiều dài cọc",
                        "Số cọc / bệ",
                        "Kích thước bệ cọc",
                        "Thi công",
                    ],
                    "Giá trị": [
                        mong["D_coc_chon_txt"],
                        f"{mong['L_coc_tu']} – {mong['L_coc_den']} m",
                        f"{mong['So_coc_tu']} – {mong['So_coc_den']} cọc",
                        mong["kich_thuoc_be_goi_y"],
                        mong["phuong_phap_thi_cong"],
                    ],
                }))
            with mc2:
                st.markdown("**Khuyến nghị kỹ thuật:**")
                for kn in mong.get("khuyen_nghi", []):
                    st.warning(kn)
                st.caption(mong.get("ghi_chu_mong", ""))
        else:
            st.warning("Chưa có kết quả gợi ý móng.")

    # ── V. MẶT CẮT NGANG ────────────────────────────────────────────────
    with st.expander("**V. MẶT CẮT NGANG CẦU**", expanded=False):
        try:
            res_mcn = MCN.thiet_ke_mcn_cau_web({
                "loai": d.get('loai_duong', 'Do thi'),
                "vtk":  d.get('vtk', 60)
            })
            st.code(res_mcn.get('mo_phong', 'Chưa có sơ đồ.'), language="text")
        except Exception as ex:
            st.error(f"Lỗi mặt cắt ngang: {ex}")

    st.markdown("---")
    st.caption("Kết quả mang tính tham khảo sơ bộ. Cần kiểm tra và điều chỉnh theo tiêu chuẩn TCVN hiện hành.")

elif selected_ribbon == "BẢN VẼ KỸ THUẬT":
    
    st.markdown("##### 📥 Nạp Cơ sở dữ liệu Khảo sát Địa hình Thực địa")
    file_khao_sat = st.file_uploader("📂 1. Kéo và thả file .NTD trắc dọc trắc ngang tại đây", type=["ntd"])
    file_toa_do = st.file_uploader("📍 2. Kéo và thả bảng tọa độ tim thực tế (.CSV hoặc .XLSX) tại đây", type=["csv", "xlsx"])
    st.markdown("---")
    
    if file_khao_sat is not None and file_toa_do is not None:
        df_ntd = TV.parse_ntd_file(file_khao_sat)
        df_coord = TV.parse_coordinate_file(file_toa_do)
        
        if df_coord is not None and not df_ntd.empty:
            df_geology = TV.convert_to_vn2000(df_ntd, df_coord)
            
            if not df_geology.empty:
                st.success(f"⚡ Hệ thống đã đồng bộ thành công {len(df_geology)} điểm mia không gian theo tọa độ tim thực tế VN-2000!")
                st.session_state.df_geology = df_geology 

                tab_dia_hinh_3d, tab_trac_doc, tab_tru_3d, tab_mcn_draw = st.tabs([
                    "🏔️ Mô hình Địa hình 3D",
                    "📊 Bản vẽ Trắc dọc toàn cầu (Full View)", 
                    "🏗️ Mô hình Trụ cầu 3D",
                    "📐 Bản vẽ Mặt cắt ngang điển hình"
                ])
                
                with tab_dia_hinh_3d:
                    col_opt1, col_opt2, col_opt3 = st.columns(3)
                    with col_opt1:
                        che_do_view = st.selectbox(
                            "🎨 Chế độ hiển thị địa hình:", 
                            ["Bề mặt mịn", "Đường đồng mức", "Lưới tam giác"]
                        )
                    with col_opt2:
                        he_so_z = st.slider("📐 Phóng đại trục đứng (Nhìn rõ lòng sông):", 0.05, 3.00, 0.50, step=0.05)
                    with col_opt3:
                        do_min_view = st.select_slider(
                            "✨ Bộ lọc mịn khử gồ ghề (Rolling Smooth):", 
                            options=[1, 3, 5, 7], 
                            value=3
                        )

                    st.markdown("---")
                    st.subheader("📊 Tích hợp Bản mô phỏng Địa chất Công trình chuyên sâu")
                    file_excel_dc = st.file_uploader("Tải lên file Excel số liệu địa chất trọn gói ba sheet:", type=['xlsx'])

                    df_hk, df_layers, df_spt = None, None, None
                    hien_mat_lop, hien_khoi_lop, do_trong_dh = True, False, 1.0

                    if file_excel_dc is not None:
                        with st.spinner("🔍 Đang phân tích dữ liệu địa chất..."):
                            df_hk, df_layers, df_spt = TV.doc_excel_dia_chat_3_sheet(file_excel_dc)
                        if df_hk is not None and not df_hk.empty:
                            st.success(f"🎉 Hệ thống định vị thành công {len(df_hk)} hố khảo sát!")
                            col_dc1, col_dc2, col_dc3 = st.columns(3)
                            with col_dc1:
                                hien_mat_lop = st.checkbox("🪨 Hiển thị mặt phẳng lớp đất", value=True)
                            with col_dc2:
                                hien_khoi_lop = st.checkbox("📦 Hiển thị khối lớp đất", value=False)
                            with col_dc3:
                                do_trong_dh = st.slider("Độ trong suốt địa hình:", 0.35, 1.0, 0.72, step=0.05)
                        else:
                            st.warning("⚠️ Dữ liệu địa chất không hợp lệ hoặc không tìm thấy cột tọa độ. Mô hình sẽ chỉ hiển thị địa hình.")

                    fig_3d, mx, my, mz = TV.ve_dia_hinh_3d(
                        df_geology, he_so_z=he_so_z, che_do=che_do_view, do_min=do_min_view
                    )

                    if fig_3d is None:
                        st.error("❌ Không thể tạo mô hình 3D từ dữ liệu khảo sát. Hãy kiểm tra lại file NTD và bảng tọa độ.")
                    else:
                        if df_hk is not None and not df_hk.empty:
                            fig_3d = TV.dap_them_ket_cau_dia_chat_3d(
                                fig_3d, df_hk, df_layers, df_spt, mx, my, mz, he_so_z=he_so_z,
                                hien_mat_phang_lop=hien_mat_lop, hien_khoi_lop=hien_khoi_lop,
                                do_trong_dia_hinh=do_trong_dh if (hien_mat_lop or hien_khoi_lop) else 1.0
                            )
                        st.plotly_chart(fig_3d, use_container_width=True, config={'renderWorldCopies': False, 'displayModeBar': True})
                                # Sau khi vẽ xong mô hình
                if fig_3d is not None:
                    col_exp1, col_exp2 = st.columns([1, 3])
                    with col_exp1:
                        if st.button("📤 Xuất địa hình ra IFC", key="export_ifc_terrain"):
                            with st.spinner("Đang xuất file IFC..."):
                                ifc_path = "terrain_output.ifc"
                                success = TV.export_terrain_to_ifc(mx, my, mz, ifc_path, name="DiaHinh_KhaoSat")
                                if success:
                                    with open(ifc_path, "rb") as f:
                                        st.download_button("⬇️ Tải file IFC", f, file_name="terrain.ifc", mime="application/octet-stream")
                                    st.success("Xuất IFC thành công!")
                                else:
                                    st.error("Xuất IFC thất bại. Kiểm tra lại cài đặt ifcopenshell.")
                with tab_trac_doc:
                    design = st.session_state.design_data
                    tim_line = None
                    if 'df_geology' in st.session_state:
                        df_geo = st.session_state.df_geology
                        # Lấy các điểm tim tuyến (offset=0)
                        tim_line = df_geo[df_geo['Offset'] == 0][['Lý trình', 'Z']].drop_duplicates(subset=['Lý trình']).sort_values('Lý trình')
                    if tim_line is not None and not tim_line.empty and 'geo_logic' in design:
                        try:
                            fig_td = PLOT.ve_trac_doc_cau(design, tim_line)
                            if fig_td:
                                st.plotly_chart(fig_td, use_container_width=True)
                            else:
                                st.info("Không thể tạo bản vẽ trắc dọc.")
                        except Exception as e:
                            st.error(f"Lỗi khi vẽ trắc dọc: {e}")
                    else:
                        st.warning("⚠️ Chưa có dữ liệu tim tuyến hoặc chưa chạy OPTIONS. Vui lòng tải file khảo sát và cập nhật số liệu.")
                
                with tab_tru_3d:
                    st.subheader("🏗️ Cấu hình Kích thước Hình học Trụ cầu Tham số hóa")
                    # Nhập thông số theo đúng tên biến của hàm create_pier
                    c1, c2 = st.columns(2)
                    with c1:
                        H = st.number_input("Chiều cao thân trụ (m)", value=5.0, step=0.5, key="h_than")
                        W = st.number_input("Chiều rộng thân trụ - dọc cầu (m)", value=1.5, step=0.1, key="w_than")
                        L = st.number_input("Chiều dài thân trụ - ngang cầu (m)", value=3.0, step=0.1, key="l_than")
                        top_H = st.number_input("Chiều cao đỉnh trụ (m)", value=0.5, step=0.1, key="top_h")
                        top_W = st.number_input("Chiều rộng đỉnh trụ (m)", value=2.0, step=0.1, key="top_w")
                    with c2:
                        base_H = st.number_input("Chiều cao bệ trụ (m)", value=1.0, step=0.1, key="base_h")
                        base_W = st.number_input("Chiều rộng bệ trụ (m)", value=2.5, step=0.1, key="base_w")
                        base_L = st.number_input("Chiều dài bệ trụ (m)", value=4.0, step=0.1, key="base_l")
                    
                    if st.button("🚀 Tạo mô hình trụ 3D", use_container_width=True):
                        with st.spinner("Đang tạo mô hình trụ từ trimesh..."):
                            pier = TC.create_pier(H, W, L, top_W, top_H, base_W, base_H, base_L)
                            vertices, faces = TC.trimesh_to_plotly_mesh(pier)
                            fig_pier = go.Figure(data=[go.Mesh3d(
                                x=vertices[:,0], y=vertices[:,1], z=vertices[:,2],
                                i=faces[:,0], j=faces[:,1], k=faces[:,2],
                                color='lightgray', opacity=0.9, flatshading=True,
                                lighting=dict(ambient=0.5, diffuse=0.8, specular=0.5)
                            )])
                            fig_pier.update_layout(
                                scene=dict(
                                    xaxis_title="X (m)", yaxis_title="Y (m)", zaxis_title="Z (m)",
                                    aspectmode='data'
                                ),
                                margin=dict(l=0, r=0, b=0, t=0),
                                height=600,
                                title="Mô hình trụ cầu 3D (trimesh)"
                            )
                            st.plotly_chart(fig_pier, use_container_width=True)
                
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
        st.info("⏳ Vui lòng tải lên cả file .NTD và bảng tọa độ để hiển thị mô hình 3D và bản vẽ.")