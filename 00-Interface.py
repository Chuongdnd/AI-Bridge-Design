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

# ── Ẩn toolbar GitHub / Deploy / MainMenu (áp dụng cho CẢ trang login) ──────
st.markdown("""
<style>
[data-testid="stToolbarActions"]  { display: none !important; }
[data-testid="stDecoration"]      { display: none !important; }
[data-testid="stStatusWidget"]    { display: none !important; }
.stDeployButton                   { display: none !important; }
#MainMenu                         { display: none !important; }
footer                            { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── XÁC THỰC NGƯỜI DÙNG ─────────────────────────────────────────────────────
import importlib.util as _iutil
_auth_spec = _iutil.spec_from_file_location("auth00", os.path.join(os.path.dirname(os.path.abspath(__file__)), "00-Auth.py"))
AUTH = _iutil.module_from_spec(_auth_spec)
_auth_spec.loader.exec_module(AUTH)

if not AUTH.is_authenticated():
    AUTH.show_login_page()
    st.stop()

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
    YTHH = importlib.import_module("02-Yeuto_Hinhhoc")  # Yếu tố hình học + MCN
    GRD  = importlib.import_module("05-Main_Girder")    # Legacy girder (dùng cho bản vẽ)
    KCN  = importlib.import_module("06-AI_KetCauNhip")  # AI Kết cấu nhịp v2
    MOT  = importlib.import_module("07-AI_MoTru")       # AI Mố – Trụ v2
    MONG = importlib.import_module("08-AI_Mong")        # Móng (rule-based)
    EXP  = importlib.import_module("09-Export_CAD_IFC") # Export DXF / IFC
    PLOT = importlib.import_module("00-Drawing_Utils")
    TV   = importlib.import_module("00-Terrain_Viewer")
    TC   = importlib.import_module("04-Pier-test")
    LPC  = importlib.import_module("10-LopPhu_MatCau")  # Lớp phủ mặt cầu
    BVK  = importlib.import_module("11-BanVe_KetCau")   # Bản vẽ kết cấu 2D/3D
    SSP  = importlib.import_module("09-So_Sanh_PA")     # So sánh 3 phương án
    CTD  = importlib.import_module("12-ChiTiet_Dam")    # Chi tiết dầm
    importlib.reload(PLOT)
    importlib.reload(BVK)
    importlib.reload(CTD)
except Exception as e:
    st.error(f"Lỗi kết nối Module: {e}")
    st.stop()

if 'design_data' not in st.session_state:
    st.session_state.design_data = {
        'day_dam': 0.0, 'khau_do_ngang': 0.0, 'bc': 12.0, 'loai_duong': "Do thi",
        'B': 20.0, 'H': 4.75, 'loai_doi_tuong_vuot': "Vượt sông", 'goc_giao': 90.0,
        'MNCN': 3.5, 'MNTT': 2.0, 'MNTC': 1.5, 'MNTN': 0.5, 'h_tn_tb': 0.0,
        'x_tim_clearance': 0.0,
        'cap_song': 'VI', 'vtk': 60, 'i_max_hinh_hoc': 4.0, 'R_hinh_hoc': 5000,
        't_ban_mm': 200,       # chiều dày bản mặt cầu (mm), min 175mm theo TCVN 11823
        'is_urban': 0,         # 1 = khu đông dân cư (ảnh hưởng chọn loại cọc)
        'geo_logic': {'L_cau': 120.0, 'x_mo_trai': -60.0, 'x_mo_phai': 60.0, 'y_mo': 1.5, 'h_tn_tb': 2.15, 'y_base_goc': 2.0},
        'ai_result': {'loai_dam': 'Super-T', 'tong_so_nhip': 3, 'chieu_dai': 40.0, 'chieu_cao': 1.75, 'so_luong_dam': 5, 'khoang_cach_dam': 2.2, 'ghi_chu': 'Phương án tối ưu từ AI.'},
        'kcn_result': None,
        'tru_result': None,
        'mong_result': None,
        'lop_phu_result': None,
    }

if 'chatbot_context' not in st.session_state:
    st.session_state.chatbot_context = "Chưa tiến hành chạy dự báo tính toán."

if 'alternatives' not in st.session_state:
    st.session_state.alternatives = None

if 'current_tab' not in st.session_state:
    st.session_state.current_tab = "THUYẾT MINH"

# =========================================================================
# ⚙️ HỘP THOẠI KHAI BÁO SỐ LIỆU
# =========================================================================
@st.dialog("⚙️ HỘP THOẠI KHAI BÁO THÔNG SỐ TUYẾN & THỦY VĂN", width="large")
def show_options_dialog():
    st.markdown("### 📥 Nhập các thông số hình học đầu vào công trình")
    sec_in1, sec_in2, sec_in3 = st.columns(3)
    
    with sec_in1:
        st.info("🌊 Phạm vi đề tài: Cầu vượt sông/kênh cấp IV–VI (TCVN 8818)")
        goc_giao = st.number_input("Góc giao chéo (độ):", min_value=30.0, max_value=90.0, value=st.session_state.design_data.get('goc_giao', 90.0), step=1.0)
        mien  = st.selectbox("Khu vực miền:", ["1", "2"], format_func=lambda x: "Miền Bắc" if x=="1" else "Miền Nam")
        cap_s = st.selectbox("Cấp sông ĐTNĐ:", ["4", "5", "6", "3", "2", "1"],
                             format_func=lambda x: f"Cấp {['I','II','III','IV','V','VI'][int(x)-1]}")
        loai_h = st.selectbox("Loại hình thủy văn:", ["1", "2"], format_func=lambda x: "Kênh đào" if x=="1" else "Sông tự nhiên")
        st.markdown("**Điều kiện khu vực**")
        is_urban_chk = st.checkbox("Khu vực đông dân cư (hạn chế tiếng ồn/rung)",
                                   value=bool(st.session_state.design_data.get('is_urban', 0)),
                                   help="Ảnh hưởng đến lựa chọn loại cọc: khu đông dân → ưu tiên cọc ép")

    with sec_in2:
        st.markdown("**Số liệu cao độ thủy văn (m)**")
        # Gợi ý từ terrain đã nạp (nếu có)
        _lt_min = _lt_max = None
        if 'df_tim_line' in st.session_state and st.session_state.df_tim_line is not None:
            _tl = st.session_state.df_tim_line
            _lt_col = next((c for c in _tl.columns if 'ý trình' in c or c.lower()=='ly_trinh'), None)
            if _lt_col:
                _lt_min = float(_tl[_lt_col].min())
                _lt_max = float(_tl[_lt_col].max())
                _suggest = (_lt_min + _lt_max) / 2
                st.info(f"🗺️ Địa hình: Lý trình {_lt_min:.1f} → {_lt_max:.1f}m  |  Gợi ý tim cầu ≈ **{_suggest:.1f}m**")
        x_tim_clearance = st.number_input(
            "📍 Lý trình tim tĩnh không (m)",
            value=float(st.session_state.design_data.get('x_tim_clearance', 0.0)),
            step=1.0, format="%.2f", key="x_tim_clearance",
            help="Lý trình điểm tim cầu vượt qua sông/kênh. Phải nằm trong phạm vi lý trình file khảo sát."
        )
        # Cao độ tự nhiên: lấy THỰC theo từng điểm từ dữ liệu địa hình đã nạp
        # (h_tn_tb chỉ còn dùng làm giá trị trung bình hiển thị / dự phòng khi
        #  ngoài phạm vi khảo sát hoặc chưa nạp địa hình).
        _df_tl = st.session_state.get('df_tim_line', None)
        lt_diahinh_arr = None
        z_diahinh_arr = None
        if _df_tl is not None and not _df_tl.empty:
            _lt_col_t = next((c for c in _df_tl.columns if 'ý trình' in c or c.lower()=='ly_trinh'), None)
            _z_col_t  = next((c for c in _df_tl.columns if c.upper() == 'Z'), None)
            if _lt_col_t and _z_col_t:
                _mask_t = (
                    (_df_tl[_lt_col_t] >= x_tim_clearance - 80) &
                    (_df_tl[_lt_col_t] <= x_tim_clearance + 80)
                )
                _sub_t = _df_tl[_mask_t]
                h_tn_tb = float(_sub_t[_z_col_t].mean()) if not _sub_t.empty else float(_df_tl[_z_col_t].mean())
                lt_diahinh_arr = _df_tl[_lt_col_t].to_numpy()
                z_diahinh_arr  = _df_tl[_z_col_t].to_numpy()
                st.success(
                    f"📐 Cao độ tự nhiên TB (từ địa hình ±80m): **{h_tn_tb:.3f} m** — "
                    f"tính toán vị trí điểm đầu/cuối cầu sẽ dùng cao độ THỰC theo từng điểm."
                )
            else:
                h_tn_tb = st.session_state.design_data.get('h_tn_tb', 0.0)
                st.warning("⚠️ Không tìm thấy cột cao độ Z trong dữ liệu địa hình.")
        else:
            h_tn_tb = st.session_state.design_data.get('h_tn_tb', 0.0)
            st.warning("⚠️ Chưa nạp file địa hình (.NTD). Nạp file để tính cao độ tự nhiên chính xác.")
        h1  = st.number_input("Cao độ MNCN (H1%):",  value=st.session_state.design_data.get('MNCN', 3.50), format="%.3f")
        h5  = st.number_input("Cao độ MNTT (H5%):",  value=st.session_state.design_data.get('MNTT', 2.00), format="%.3f")
        h10 = st.number_input("Cao độ MNTC (H10%):", value=st.session_state.design_data.get('MNTC', 1.50), format="%.3f")
        h98 = st.number_input("Cao độ MNTN (H98%):", value=st.session_state.design_data.get('MNTN', 0.50), format="%.3f")
        st.markdown("**Bản mặt cầu**")
        t_ban_mm = st.number_input(
            "Chiều dày bản mặt cầu (mm):",
            min_value=175, max_value=350,
            value=int(st.session_state.design_data.get('t_ban_mm', 200)),
            step=5,
            help="Tối thiểu 175 mm theo TCVN 11823-2017 Điều 9.7.1.1"
        )

    with sec_in3:
        st.markdown("**Tiêu chuẩn hình học trắc dọc tuyến**")
        l_hinhhoc = st.selectbox("Loại đường thiết kế:", ["Cao tốc", "O to", "Do thi"])

        mcn_oto_override = {}   # chỉ có nội dung khi l_hinhhoc == "O to"

        if l_hinhhoc == "Cao tốc":
            d_hinhhoc = st.radio("Địa hình:", options=["1", "2"], format_func=lambda x: "Đồng bằng" if x == "1" else "Khó khăn")
            v_list = [120, 100] if d_hinhhoc == "1" else [80, 60]
            v_hinhhoc = st.selectbox("Vận tốc thiết kế Vtk (km/h):", options=v_list)
            input_tra_cuu = v_hinhhoc

            # ── MCN cao tốc theo TCVN 5729:2012 Bảng 1 ──────────────────────
            _dpc_ct_labels = {
                "co_lop_phu_khong_tru": "Có lớp phủ, không bố trí trụ công trình",
                "co_lop_phu_co_tru":    "Có lớp phủ, có bố trí trụ công trình",
                "khong_lop_phu":        "Không có lớp phủ (trồng cỏ / hình chữ V)",
            }
            st.markdown("**Mặt cắt ngang đường (TCVN 5729:2012 Bảng 1)**")
            loai_dpc_ct = st.selectbox(
                "Cấu tạo dải giữa:",
                options=list(_dpc_ct_labels.keys()),
                format_func=lambda k: _dpc_ct_labels[k],
                help="Theo Điều 6.5 — xác định chiều rộng dải phân cách lõi."
            )
            tra_ct = YTHH.tra_cuu_mcn_caotoc(v_hinhhoc, loai_dpc_ct)
            if tra_ct.get("status") == "success":
                st.caption(
                    f"{tra_ct['bang_ap_dung']} — Vtk={v_hinhhoc}km/h: "
                    f"Mặt đường ≥ **{tra_ct['w_mat_duong_min']:g}m** (2 làn/chiều × {tra_ct['w_lan_min']:g}m) | "
                    f"Lề gia cố ≥ **{tra_ct['w_le_dat_min']:g}m** | "
                    f"DAT dải giữa ≥ **{tra_ct['w_dat_an_toan_dg_min']:g}m** | "
                    f"DPC lõi ≥ **{tra_ct['w_dpc_core_min']:g}m** | "
                    f"Nền ≥ **{tra_ct['w_nen_min']:g}m**"
                )
                st.caption(
                    "Độ dốc ngang (cố định TCVN 5729:2012): "
                    f"Mặt đường & dải AT = **{tra_ct['i_mat_duong']:g}%** | "
                    f"Lề trồng cỏ = **{tra_ct['i_le_trong_co']:g}%**"
                )
                c_ct1, c_ct2 = st.columns(2)
                with c_ct1:
                    n_lan_ct = st.number_input(
                        "Số làn xe mỗi chiều:",
                        min_value=int(tra_ct["n_lan_moi_chieu_min"]),
                        value=int(tra_ct["n_lan_moi_chieu_min"]),
                        step=1,
                        help=f"Tối thiểu {tra_ct['n_lan_moi_chieu_min']} làn/chiều (Bảng 1). "
                             f"Thêm 1 làn = +{tra_ct['w_lan_them']:g}m mặt đường (Điều 6.8)."
                    )
                    w_le_dat_ct = st.number_input(
                        "Chiều rộng lề gia cố / dải AT (m):",
                        min_value=float(tra_ct["w_le_dat_min"]),
                        value=float(tra_ct["w_le_dat_min"]),
                        step=0.25, format="%.2f",
                        help=f"Tối thiểu {tra_ct['w_le_dat_min']:g}m theo Bảng 1."
                    )
                with c_ct2:
                    w_dat_at_dg_ct = st.number_input(
                        "Dải an toàn trong dải giữa (m):",
                        min_value=float(tra_ct["w_dat_an_toan_dg_min"]),
                        value=float(tra_ct["w_dat_an_toan_dg_min"]),
                        step=0.25, format="%.2f",
                        help=f"Tối thiểu {tra_ct['w_dat_an_toan_dg_min']:g}m mỗi bên (Bảng 1)."
                    )
                    w_dpc_core_ct = st.number_input(
                        "Chiều rộng dải phân cách lõi (m):",
                        min_value=float(tra_ct["w_dpc_core_min"]),
                        value=float(tra_ct["w_dpc_core_min"]),
                        step=0.25, format="%.2f",
                        help=f"Tối thiểu {tra_ct['w_dpc_core_min']:g}m theo Bảng 1 (loại đã chọn)."
                    )
                mcn_oto_override = {
                    "loai_dpc_ct": loai_dpc_ct,
                    "n_lan_moi_chieu": n_lan_ct,
                    "w_lan": tra_ct["w_lan_min"],
                    "w_le_dat": w_le_dat_ct,
                    "w_le_trong_co": tra_ct["w_le_trong_co_min"],
                    "w_dat_an_toan_dg": w_dat_at_dg_ct,
                    "w_dpc_core": w_dpc_core_ct,
                }
            else:
                st.warning(f"⚠️ {tra_ct.get('message','Không tra được MCN cao tốc.')}")
                mcn_oto_override = {"loai_dpc_ct": loai_dpc_ct}
        elif l_hinhhoc == "O to":
            cap_duong_oto = st.selectbox("Cấp đường ô tô:", ["I", "II", "III", "IV", "V", "VI"])
            d_hinhhoc = st.radio("Địa hình vùng:", ["1", "2"], format_func=lambda x: "Đồng bằng" if x == "1" else "Miền núi")
            input_tra_cuu = cap_duong_oto

            # ── MCN tối thiểu theo TCVN 4054:2005 (Bảng 6/7) + khai báo tùy chỉnh ──
            dia_hinh_mcn = "dong_bang" if d_hinhhoc == "1" else "nui"
            tra_mcn = YTHH.tra_cuu_mcn_oto(cap_duong_oto, dia_hinh_mcn)
            if tra_mcn.get("status") == "success":
                st.markdown("**Mặt cắt ngang đường (TCVN 4054:2005)**")
                st.caption(
                    f"{tra_mcn['bang_ap_dung']} — Cấp {cap_duong_oto}: tối thiểu "
                    f"**{tra_mcn['so_lan_min']:g} làn × {tra_mcn['w_lan_min']:g}m** | "
                    f"Dải PC ≥ **{tra_mcn['w_dpc_min']:g}m** | "
                    f"Lề ≥ **{tra_mcn['w_le_min']:g}m**"
                    + (f" (gia cố ≥ {tra_mcn['w_le_gc_min']:g}m)" if tra_mcn['w_le_gc_min'] else "")
                    + f" | Nền đường ≥ **{tra_mcn['w_nen_duong_min']:g}m**"
                )
                c_mcn1, c_mcn2 = st.columns(2)
                with c_mcn1:
                    so_lan_oto = st.number_input(
                        "Số làn xe thiết kế:",
                        min_value=int(tra_mcn["so_lan_min"]), value=int(tra_mcn["so_lan_min"]), step=1,
                        help=f"Tối thiểu {tra_mcn['so_lan_min']:g} làn theo TCVN 4054:2005."
                    )
                    w_lan_oto = st.number_input(
                        "Chiều rộng 1 làn xe (m):",
                        min_value=float(tra_mcn["w_lan_min"]), value=float(tra_mcn["w_lan_min"]),
                        step=0.25, format="%.2f",
                        help=f"Tối thiểu {tra_mcn['w_lan_min']:g}m theo TCVN 4054:2005."
                    )
                with c_mcn2:
                    w_le_oto = st.number_input(
                        "Chiều rộng lề đường (m):",
                        min_value=float(tra_mcn["w_le_min"]), value=float(tra_mcn["w_le_min"]),
                        step=0.25, format="%.2f",
                        help=f"Tối thiểu {tra_mcn['w_le_min']:g}m theo TCVN 4054:2005."
                    )
                    w_dpc_oto = st.number_input(
                        "Chiều rộng dải phân cách giữa (m):",
                        min_value=float(tra_mcn["w_dpc_min"]), value=float(tra_mcn["w_dpc_min"]),
                        step=0.25, format="%.2f",
                        help=f"Tối thiểu {tra_mcn['w_dpc_min']:g}m theo TCVN 4054:2005"
                             + (" (cấp này không bắt buộc có dải phân cách)." if tra_mcn['w_dpc_min'] == 0 else ".")
                    )
                # ── Dải phân cách giữa (Bảng 8) — chỉ hiện khi có DPC ──
                _dpc_labels = {
                    "be_tong_duc_san": "BT đúc sẵn, bó vỉa có lớp phủ (không có trụ)",
                    "co_tru_cot":      "Xây bó vỉa, có lớp phủ, có bố trí trụ công trình",
                    "khong_lop_phu":   "Không có lớp phủ",
                }
                _dpc_keys = list(_dpc_labels.keys())
                if w_dpc_oto > 0:
                    st.markdown("**Dải phân cách giữa (Bảng 8 – TCVN 4054:2005)**")
                    loai_dpc_oto = st.selectbox(
                        "Loại cấu tạo dải phân cách:",
                        options=_dpc_keys,
                        format_func=lambda k: _dpc_labels[k],
                        help="Theo Điều 4.4.1 – chỉ bố trí khi đường có ≥ 4 làn xe."
                    )
                    _b8 = YTHH.tra_cuu_dai_phan_cach(loai_dpc_oto)
                    st.caption(
                        f"Tối thiểu theo Bảng 8: phần phân cách ≥ **{_b8['w_phan_cach']:g}m** | "
                        f"phần an toàn 2×{_b8['w_an_toan_moi_ben']:g}m | "
                        f"Tổng dải PC ≥ **{_b8['w_toi_thieu']:g}m**"
                    )
                    if w_dpc_oto < _b8["w_toi_thieu"]:
                        st.warning(
                            f"⚠️ Dải phân cách nhập ({w_dpc_oto:.2f}m) nhỏ hơn tối thiểu "
                            f"Bảng 8 ({_b8['w_toi_thieu']:g}m) cho loại '{_dpc_labels[loai_dpc_oto]}'."
                        )
                else:
                    loai_dpc_oto = "be_tong_duc_san"  # mặc định, không hiển thị

                # ── Độ dốc ngang mặt đường (Bảng 9) ──
                _mat_labels = {
                    "btxm_bthua":    "Bê tông xi măng / bê tông nhựa (1.5–2.0%)",
                    "lat_da_tot":    "Mặt đường lát đá tốt, phẳng (2.0–3.0%)",
                    "lat_da_tb":     "Mặt đường lát đá chất lượng TB (3.0–3.5%)",
                    "da_dam_cap_phoi": "Đá dăm, cấp phối, mặt đường cấp thấp (3.0–3.5%)",
                }
                st.markdown("**Độ dốc ngang mặt đường (Bảng 9 – TCVN 4054:2005)**")
                loai_mat_duong_oto = st.selectbox(
                    "Loại mặt đường (ảnh hưởng độ dốc ngang):",
                    options=list(_mat_labels.keys()),
                    format_func=lambda k: _mat_labels[k],
                )
                _b9 = YTHH.tra_cuu_doc_ngang(loai_mat_duong_oto)
                st.caption(
                    f"Bảng 9: độ dốc ngang mặt đường & lề gia cố: "
                    f"**{_b9['i_min']:g}% – {_b9['i_max']:g}%** | "
                    f"Lề không gia cố: **{_b9['i_le_khong_gc_min']:g}% – {_b9['i_le_khong_gc_max']:g}%**"
                )
                i_doc_ngang_oto = st.number_input(
                    "Độ dốc ngang thiết kế i (%):",
                    min_value=float(_b9["i_min"]),
                    max_value=float(_b9["i_max"]),
                    value=float(_b9["i_goi_y"]),
                    step=0.5, format="%.1f",
                    help=f"TCVN 4054:2005 Bảng 9: {_b9['i_min']:g}% – {_b9['i_max']:g}% cho loại mặt đường này."
                )

                mcn_oto_override = {
                    "cap_duong": cap_duong_oto, "dia_hinh": dia_hinh_mcn,
                    "so_lan": so_lan_oto, "w_lan": w_lan_oto,
                    "w_le": w_le_oto, "w_dpc": w_dpc_oto,
                    "w_le_gc": tra_mcn.get("w_le_gc_min"),
                    "loai_dpc": loai_dpc_oto,
                    "loai_mat_duong": loai_mat_duong_oto,
                    "i_doc_ngang": i_doc_ngang_oto,
                }
            else:
                st.warning(f"⚠️ {tra_mcn.get('message','Không tra được MCN tối thiểu.')}")
                mcn_oto_override = {"cap_duong": cap_duong_oto, "dia_hinh": dia_hinh_mcn}
        else:
            loai_dt = st.selectbox("Phân loại đường đô thị:", ["Trục chính đô thị", "Đường chính đô thị", "Đường khu vực", "Đường nội bộ"])
            cap_dt = st.selectbox("Cấp kỹ thuật kỹ sư:", ["Đặc biệt", "Cấp I", "Cấp II"] if loai_dt == "Trục chính đô thị" else ["Cấp I", "Cấp II"])
            list_vtk = YTHH.get_vtk_goi_y_dothi(loai_dt, cap_dt)
            v_hinhhoc = st.radio("Vận tốc thiết kế Vtk:", options=list_vtk, horizontal=True)
            d_hinhhoc = st.radio("Địa hình đô thị:", ["1", "2"], format_func=lambda x: "Bằng phẳng" if x == "1" else "Khó khăn")
            input_tra_cuu = v_hinhhoc

            # ── MCN đường đô thị — Bảng 10, 12, 13 TCVN 13592:2022 ────────────
            _dt_labels = {
                "cao_toc_do_thi":   "Đường cao tốc đô thị",
                "pho_chinh_chu_yeu":"Đường phố chính chủ yếu",
                "pho_chinh_thu_yeu":"Đường phố chính thứ yếu",
                "pho_gom":          "Đường phố gom",
                "pho_noi_bo":       "Đường phố nội bộ",
            }
            _col_dtA, _col_dtB = st.columns(2)
            with _col_dtA:
                loai_dt_mcn = st.selectbox(
                    "Loại đường phố (MCN — Bảng 10):",
                    options=list(_dt_labels.keys()),
                    format_func=lambda k: _dt_labels[k],
                    key="loai_dt_mcn",
                )
            with _col_dtB:
                dieu_kien_xd = st.radio(
                    "Điều kiện xây dựng (ảnh hưởng Bảng 14, 15):",
                    options=["I", "II", "III"],
                    horizontal=True,
                    key="dieu_kien_xd",
                    help="I: Thuận lợi | II: Bình thường | III: Khó khăn",
                )
            tra_dt = YTHH.tra_cuu_mcn_do_thi(v_hinhhoc, loai_dt_mcn, dieu_kien_xd)

            if tra_dt.get("status") == "success":
                # ── Hiển thị tra cứu ─────────────────────────────────────────
                st.caption(
                    f"📐 **Bảng 10** — {tra_dt['mo_ta']} | VTK {v_hinhhoc} km/h | "
                    f"Làn tối thiểu: **{tra_dt['w_lan_min']:.2f}m** | "
                    f"Số làn: **{tra_dt['so_lan_toi_thieu']}** (mong muốn {tra_dt['so_lan_mong_muon']})"
                )
                _dat_at_cap = (tra_dt['w_dat_at_loaiI'] if dieu_kien_xd == "I"
                               else tra_dt['w_dat_at_loaiII_III'])
                st.caption(
                    f"📐 **Bảng 13** — Lề: **{tra_dt['w_le_min']:.2f}÷{tra_dt['w_le_max']:.2f}m** | "
                    + (f"Dải AT (đk {dieu_kien_xd}): **{_dat_at_cap:.2f}m**"
                       if _dat_at_cap else "Dải AT: không bắt buộc ở VTK này")
                )
                if tra_dt["co_dpc"] and tra_dt["dpc_min"] is not None:
                    st.caption(
                        f"📐 **Bảng 14** — Dải phân cách tối thiểu (đk {dieu_kien_xd}): "
                        f"**{tra_dt['dpc_min']:.2f}m** (mong muốn {tra_dt['dpc_mong_muon']:.2f}m)"
                    )
                elif tra_dt.get("dpc_note"):
                    st.caption(f"📐 **Bảng 14** — {tra_dt['dpc_note']}")
                if tra_dt["he_min"] is not None:
                    st.caption(
                        f"📐 **Bảng 15** — Hè đường tối thiểu (đk {dieu_kien_xd}): "
                        f"**{tra_dt['he_min']:.1f}m**"
                    )

                # ── Phần xe chạy ──────────────────────────────────────────────
                st.markdown("**Phần xe chạy (Bảng 10):**")
                _c1, _c2 = st.columns(2)
                with _c1:
                    n_lan_dt = st.number_input(
                        "Số làn xe:",
                        min_value=tra_dt["so_lan_toi_thieu"], value=tra_dt["so_lan_toi_thieu"],
                        step=2, key="n_lan_dt",
                    )
                    w_lan_dt = st.number_input(
                        "Chiều rộng 1 làn xe (m):",
                        min_value=tra_dt["w_lan_min"], value=tra_dt["w_lan_min"],
                        step=0.25, format="%.2f", key="w_lan_dt",
                    )
                with _c2:
                    w_le_dt = st.number_input(
                        f"Lề đường (m) — tối thiểu {tra_dt['w_le_min']:.2f}m:",
                        min_value=tra_dt["w_le_min"],
                        max_value=max(tra_dt["w_le_max"], tra_dt["w_le_min"] + 3.0),
                        value=tra_dt["w_le_min"],
                        step=0.25, format="%.2f", key="w_le_dt",
                    )

                # ── Dải phân cách (Bảng 14) ───────────────────────────────────
                st.markdown("**Dải phân cách giữa (Bảng 14):**")
                if tra_dt["co_dpc"] and tra_dt["dpc_min"] is not None:
                    w_dpc_dt = st.number_input(
                        f"Chiều rộng DPC (m) — tối thiểu {tra_dt['dpc_min']:.2f}m "
                        f"(mong muốn {tra_dt['dpc_mong_muon']:.2f}m):",
                        min_value=tra_dt["dpc_min"],
                        value=tra_dt["dpc_min"],
                        step=0.50, format="%.2f", key="w_dpc_dt",
                    )
                elif tra_dt.get("dpc_note"):
                    st.info(f"ℹ️ {tra_dt['dpc_note']}")
                    w_dpc_dt = 0.0
                else:
                    w_dpc_dt = st.number_input(
                        "Chiều rộng DPC (m, 0 nếu không có):",
                        min_value=0.0, value=0.0, step=0.5, format="%.2f", key="w_dpc_dt",
                    )

                # ── Hè đường (Bảng 15) ────────────────────────────────────────
                st.markdown("**Hè đường / Dải bên đường (Bảng 15):**")
                _he_min_val = tra_dt["he_min"] if tra_dt["he_min"] is not None else 0.0
                if _he_min_val > 0:
                    w_he_dt = st.number_input(
                        f"Chiều rộng hè đường (m) — tối thiểu {_he_min_val:.1f}m:",
                        min_value=_he_min_val, value=_he_min_val,
                        step=0.5, format="%.1f", key="w_he_dt",
                    )
                else:
                    st.info("ℹ️ Loại đường này không quy định hè đường bắt buộc.")
                    w_he_dt = st.number_input(
                        "Chiều rộng hè đường (m, 0 nếu không có):",
                        min_value=0.0, value=0.0, step=0.5, format="%.1f", key="w_he_dt",
                    )

                # ── Dải trồng cây (Bảng 16 — tham khảo) ─────────────────────
                with st.expander("📋 Bảng 16 — Kích thước tối thiểu dải trồng cây (tham khảo)"):
                    _tc_ref = tra_dt.get("trong_cay_ref", {})
                    _tc_labels = {
                        "cay_bong_mat_1_hang":     "Cây bóng mát trồng 1 hàng",
                        "cay_bong_mat_2_hang":     "Cây bóng mát trồng 2 hàng",
                        "dai_cay_bui_bai_co":      "Dải cây bụi, bãi cỏ",
                        "vuon_cay_nha_1_tang":     "Vườn cây trước nhà 1 tầng",
                        "vuon_cay_nha_nhieu_tang": "Vườn cây trước nhà nhiều tầng",
                    }
                    st.table(pd.DataFrame({
                        "Hình thức trồng cây": [_tc_labels.get(k, k) for k in _tc_ref],
                        "Chiều rộng tối thiểu (m)": list(_tc_ref.values()),
                    }))

                # ── Mặt đường và độ dốc ngang (Bảng 12) ─────────────────────
                st.markdown("**Độ dốc ngang (Bảng 12):**")
                _loai_mat_dt_labels = {
                    "btxm_bthua":      "Bê tông xi măng / bê tông nhựa",
                    "nhua_khac":       "Mặt đường nhựa khác",
                    "lat_da_tot":      "Lát đá tốt, phẳng",
                    "da_dam_cap_phoi": "Đá dăm, cấp phối",
                }
                loai_mat_dt = st.selectbox(
                    "Loại mặt đường:",
                    options=list(_loai_mat_dt_labels.keys()),
                    format_func=lambda k: _loai_mat_dt_labels[k],
                    key="loai_mat_dt",
                )
                tra_doc_dt = YTHH.tra_cuu_doc_ngang_do_thi(loai_mat_dt)
                i_doc_ngang_dt = st.number_input(
                    f"Độ dốc ngang i (%) — Bảng 12: {tra_doc_dt['i_min']:g}÷{tra_doc_dt['i_max']:g}%:",
                    min_value=float(tra_doc_dt["i_min"]),
                    max_value=float(tra_doc_dt["i_max"]),
                    value=float(tra_doc_dt["i_goi_y"]),
                    step=0.5, format="%.1f", key="i_doc_ngang_dt",
                )
                mcn_oto_override = {
                    "loai_dt":        loai_dt_mcn,
                    "dieu_kien_xd":   dieu_kien_xd,
                    "so_lan":         n_lan_dt,
                    "w_lan":          w_lan_dt,
                    "w_le":           w_le_dt,
                    "w_dpc":          w_dpc_dt,
                    "w_he":           w_he_dt,
                    "loai_mat_duong": loai_mat_dt,
                    "i_doc_ngang":    i_doc_ngang_dt,
                }
            else:
                st.warning(f"⚠️ {tra_dt.get('message','Không tra được MCN đô thị.')}")
                mcn_oto_override = {"loai_dt": loai_dt_mcn, "dieu_kien_xd": dieu_kien_xd}

        b_cau = st.number_input("Bề rộng Bc mặt cắt cầu (m):", min_value=6.0, value=st.session_state.design_data.get('bc', 12.0), step=0.5)

        res_geo = YTHH.tra_cuu_yeu_to_hinh_hoc(l_hinhhoc, input_tra_cuu, d_hinhhoc)
        r_final_calc = 5000
        i_final_calc = 4.0
        if res_geo.get("status") == "success":
            r_gh = float(res_geo["R_loi_gh"])
            r_tt = float(res_geo["R_loi_tt"])
            imax_calc = float(str(res_geo.get('imax', 4)).split('%')[0])

            st.markdown("**Bán kính đường cong đứng lồi**")
            st.caption(
                f"Theo {res_geo['tieu_chuan']}: R giới hạn (tối thiểu) = **{r_gh:,.0f} m** | "
                f"R thông thường (khuyến nghị) = **{r_tt:,.0f} m**"
            )
            r_final_calc = st.number_input(
                "Bán kính đường cong đứng lồi R thiết kế (m):",
                min_value=r_gh, value=max(r_tt, r_gh), step=100.0, format="%.0f",
                help=f"Có thể chọn lớn hơn giá trị khuyến nghị, nhưng không được nhỏ hơn "
                     f"giá trị giới hạn tối thiểu {r_gh:,.0f} m theo {res_geo['tieu_chuan']}."
            )

            st.markdown("**Độ dốc dọc**")
            st.caption(f"Độ dốc dọc lớn nhất cho phép theo tiêu chuẩn: **imax = {imax_calc:.1f} %**")
            i_final_calc = st.number_input(
                "Độ dốc dọc thiết kế i (%):",
                min_value=0.0, max_value=imax_calc, value=imax_calc, step=0.1, format="%.1f",
                help=f"Không được vượt quá độ dốc dọc lớn nhất cho phép {imax_calc:.1f}% theo {res_geo['tieu_chuan']}."
            )

    st.markdown("---")
    
    if st.button("💾 OK - Áp dụng cấu hình và Chạy dự báo AI", use_container_width=True, type="primary"):
        with st.spinner("⚡ Đang chạy toàn bộ AI pipeline..."):
            is_urban_val = 1 if is_urban_chk else 0
            # ── Bước 1: Tĩnh không ───────────────────────────────────────────
            res = TK.tra_cuu_tinh_khong_bridge(
                mien=mien, cap_num=cap_s, loai_hinh=loai_h,
                h1=h1, h5=h5, h10=h10, h98=h98, h_tn_tb=h_tn_tb
            )
            alpha_rad = np.radians(goc_giao)
            res['B'] = round(res.get('B', 0) / np.sin(alpha_rad), 2) if goc_giao < 90 else res.get('B', 0)
            res['goc_giao'] = goc_giao
            res['h_tn_tb'] = h_tn_tb
            res['MNCN'], res['MNTT'], res['MNTC'], res['MNTN'] = h1, h5, h10, h98
            res['cap_song'] = cap_s
            res['loai_doi_tuong_vuot'] = "Vượt sông"
            res['t_ban_mm'] = t_ban_mm
            res['is_urban'] = is_urban_val
            res['x_tim_clearance'] = x_tim_clearance  # lưu để hiển thị lại lần sau
            res['mcn_oto_input'] = mcn_oto_override   # khai báo MCN đường ô tô (nếu có)

            if res_geo.get("status") == "success":
                # ── Bước 2: Hình học ─────────────────────────────────────────
                res['R_hinh_hoc'] = r_final_calc
                res['i_max_hinh_hoc'] = i_final_calc
                res['geo_logic']  = YTHH.tinh_toan_geo_logic(
                    res, h_tn_tb,
                    res.get('day_dam', 0.0), x_tim_clearance=x_tim_clearance,
                    lt_diahinh=lt_diahinh_arr, z_diahinh=z_diahinh_arr
                )
                res['bc']         = b_cau
                res['loai_duong'] = l_hinhhoc
                res['vtk']        = res_geo.get("v_thiet_ke", 60)

                L_cau    = res['geo_logic'].get('L_cau', None)
                moi_tr   = "Vượt sông"
                v3_path  = os.path.join(os.path.dirname(__file__), "Data", "Bridge_Train_Dataset_v3.xlsx")

                # ── Bước 3 (legacy GRD module — bo qua neu khong co file) ────
                res['ai_result'] = None

                # ── Bước 4: AI Kết cấu nhịp ──────────────────────────────────
                try:
                    kcn_models = KCN.train_kcn_ai(v3_path=v3_path)
                except TypeError:
                    kcn_models = KCN.train_kcn_ai()   # fallback: phiên bản cũ không có v3_path
                except Exception:
                    kcn_models = None
                try:
                    res['kcn_result'] = KCN.predict_kcn(
                        B_tk=res['B'], H_tk=res.get('H', 3.5),
                        goc=goc_giao, B_cau=res['bc'],
                        moi_truong=moi_tr, L_cau_tong=L_cau,
                        models=kcn_models,
                        method='auto' if kcn_models else 'rb'
                    )
                except Exception:
                    res['kcn_result'] = None

                # ── Bước 5: AI Mố – Trụ ──────────────────────────────────────
                try:
                    pier_models = MOT.train_pier_ai(v3_path=v3_path)
                except TypeError:
                    pier_models = MOT.train_pier_ai()
                except Exception:
                    pier_models = None
                loai_dam_cho_tru = (
                    res['kcn_result']['loai_dam'] if res.get('kcn_result')
                    else (res.get('ai_result') or {}).get('loai_dam', 'Super-T')
                )
                H_dam_est = (
                    res['kcn_result']['chieu_cao_dam'] if res.get('kcn_result')
                    else (res.get('ai_result') or {}).get('chieu_cao', 1.75)
                )
                # Ước tính chiều cao trụ từ cao độ
                H_tru_est, cao_day_dam, cao_mat_cau = MOT.estimate_pier_height(
                    MNCN=h1, H_tinh_khong=res.get('H', 3.5),
                    H_dam=H_dam_est, MNTN=h98
                )
                res['H_tru_est']  = H_tru_est
                res['cao_day_dam'] = cao_day_dam
                res['cao_mat_cau'] = cao_mat_cau

                is_urban  = is_urban_val
                is_river  = 1   # đề tài chỉ vượt sông
                res['tru_result'] = MOT.predict_pier(
                    vtk=res['vtk'], B_cau=res['bc'],
                    H_tru=H_tru_est, is_urban=is_urban,
                    is_river=is_river, cap_song=res['cap_song'],
                    loai_dam=loai_dam_cho_tru, models=pier_models
                )

                # ── Bước 6: Móng cầu (AI + RB) ───────────────────────────────
                loai_tru_str = (
                    res['tru_result']['loai_tru'] if res.get('tru_result')
                    else 'Thân cột 2 trụ'
                )
                fnd_models = MONG.train_foundation_ai(v3_path=v3_path)
                res['mong_result'] = MONG.predict_foundation(
                    H_tru=H_tru_est, loai_tru=loai_tru_str,
                    is_river=is_river, cap_song=res['cap_song'],
                    B_cau=res['bc'], vtk=res['vtk'],
                    L_nhip=res.get('kcn_result', {}).get('chieu_dai') if res.get('kcn_result') else None,
                    is_urban=is_urban_val,
                    foundation_models=fnd_models
                )

                # ── Bước 7: Lớp phủ mặt cầu ──────────────────────────────────
                res['lop_phu_result'] = LPC.tu_van_lop_phu(
                    vtk=res['vtk'],
                    loai_duong=res.get('loai_duong', 'Do thi'),
                    L_nhip=res.get('kcn_result', {}).get('chieu_dai', 40) if res.get('kcn_result') else 40,
                    moi_truong="Vượt sông"
                )

                st.session_state.design_data = res

                # ── Bước 8: Sinh 3 phương án so sánh ──────────────────────
                try:
                    st.session_state.alternatives = SSP.generate_3_alternatives(
                        B_tk=res['B'], H_tk=res.get('H', 3.5), goc=goc_giao,
                        B_cau=res['bc'], moi_truong=moi_tr, L_cau=L_cau,
                        kcn_models=kcn_models, pier_models=pier_models,
                        fnd_models=fnd_models,
                        MNCN=h1, H_tk_nhip=res.get('H', 3.5), h98=h98,
                        cap_song=res['cap_song'], is_urban=is_urban_val,
                        is_river=1, vtk=res['vtk'],
                        pa1_kcn=res.get('kcn_result'),
                        pa1_tru=res.get('tru_result'),
                        pa1_mong=res.get('mong_result'),
                    )
                except Exception as _alt_err:
                    st.session_state.alternatives = None
                    st.warning(f"Không sinh được phương án so sánh: {_alt_err}")

                kcn = res.get('kcn_result') or (res.get('ai_result') or {})
                st.session_state.chatbot_context = (
                    f"Vtk={res['vtk']}km/h | "
                    f"LoaiDam={kcn.get('loai_dam','?')} | "
                    f"L_nhip={kcn.get('chieu_dai','?')}m | "
                    f"L_cau={res['geo_logic']['L_cau']:.1f}m | "
                    f"LoaiTru={res.get('tru_result',{}).get('loai_tru','?')} | "
                    f"LoaiMong={res.get('mong_result',{}).get('loai_mong','?')}"
                )
                st.session_state.current_tab = "BẢN VẼ KỸ THUẬT"
                st.rerun()

# =========================================================================
# BỌC VÙNG ĐIỀU KHIỂN VÀO KHUNG HTML GHIM CỨNG
# =========================================================================
st.markdown('<div id="custom-ribbon-container">', unsafe_allow_html=True)

ribbon_options = ["THUYẾT MINH", "BẢN VẼ KỸ THUẬT", "SO SÁNH PHƯƠNG ÁN"]
# Map old tab names về mới
if st.session_state.current_tab == "BẢN VẼ KẾT CẤU":
    st.session_state.current_tab = "BẢN VẼ KỸ THUẬT"
default_idx = ribbon_options.index(st.session_state.current_tab) if st.session_state.current_tab in ribbon_options else 1

selected_ribbon = option_menu(
    menu_title=None,
    options=ribbon_options,
    icons=["house", "rulers", "bar-chart-line"],
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

# Hàng nút bấm OPTIONS + thông số hiện hành
ctrl_col1, ctrl_col2 = st.columns([1, 4])
with ctrl_col1:
    if st.button("⚙️ OPTIONS - KHAI BÁO SỐ LIỆU", use_container_width=True, type="secondary"):
        show_options_dialog()
with ctrl_col2:
    if st.session_state.design_data.get('kcn_result') or (st.session_state.design_data.get('ai_result') or {}).get('loai_dam'):
        _ai_p  = st.session_state.design_data.get('kcn_result') or (st.session_state.design_data.get('ai_result') or {})
        _geo_p = st.session_state.design_data.get('geo_logic', {})
        st.markdown(
            f"<div style='padding-top:5px; font-size:13px;'>"
            f"📊 <b>Thông số hiện hành:</b> "
            f"L = <b>{_geo_p.get('L_cau',0):.2f}m</b> | "
            f"Kết cấu nhịp: <b>{_ai_p.get('tong_so_nhip','?')} nhịp × {_ai_p.get('chieu_dai','?')}m "
            f"(Dầm {_ai_p.get('loai_dam','').upper()})</b> | "
            f"H = <b>{_ai_p.get('chieu_cao_dam') or _ai_p.get('chieu_cao','—')}m</b>"
            f"</div>",
            unsafe_allow_html=True
        )

st.markdown('</div>', unsafe_allow_html=True)

# --- THANH SIDEBAR TRÁI (giữ nguyên như ban đầu) ---
with st.sidebar:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(current_dir, "Images", "UTH.jpg")
    if os.path.exists(logo_path):
        st.image(logo_path, width=280)

    st.write("👤 **SVTH:** Chương DND")
    st.write("👨‍🏫 **GVHD:** T.S Nguyễn Văn Hiển")
    st.caption("🎓 *Đề tài:* Tích hợp AI và BIM tự động hóa thiết kế cầu đường bộ")

    st.markdown("---")

    # ── Thông tin tài khoản & đăng xuất ─────────────────────────────────
    _u = AUTH.current_user()
    st.caption(f"🔑 Đăng nhập: **{_u.get('name', _u.get('username',''))}** ({_u.get('role','')})")
    _col1, _col2 = st.columns(2)
    with _col1:
        if st.button("🚪 Đăng xuất", use_container_width=True, key="btn_logout"):
            AUTH.logout()
            st.rerun()
    with _col2:
        _show_acct = st.button("👥 Tài khoản", use_container_width=True, key="btn_acct",
                               disabled=not AUTH.is_admin(),
                               help="Quản lý tài khoản (chỉ admin)")
    if _show_acct and AUTH.is_admin():
        with st.expander("👥 Quản lý tài khoản", expanded=True):
            AUTH.show_account_panel()

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
            st.write(f"CĐTN (từ địa hình): {d.get('h_tn_tb',0):.3f} m")
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

    # ── V. BẢN MẶT CẦU & LỚP PHỦ ────────────────────────────────────────
    lop_phu = d.get('lop_phu_result')
    with st.expander("**V. BẢN MẶT CẦU & LỚP PHỦ MẶT CẦU**", expanded=False):
        t_ban_mm_val = d.get('t_ban_mm', 200)
        st.markdown(f"**Chiều dày bản mặt cầu BTCT:** `{t_ban_mm_val} mm` "
                    f"{'✅' if t_ban_mm_val >= 175 else '⚠️ Dưới tối thiểu 175mm'}")
        st.caption("Tối thiểu 175 mm theo TCVN 11823-2017 Điều 9.7.1.1")
        if lop_phu:
            st.markdown(f"**Phương án lớp phủ:** {lop_phu['phuong_an']}")
            st.caption(f"Tiêu chuẩn: {lop_phu['tieu_chuan']}")
            lp_data = []
            for i, lop in enumerate(lop_phu['cac_lop'], 1):
                if "lieu_luong" in lop:
                    day_txt = lop["lieu_luong"]
                elif lop["day_tt"] > 0:
                    day_txt = f"{lop['day_min']}–{lop['day_tt']} mm"
                else:
                    day_txt = "—"
                lp_data.append({"STT": i, "Lớp cấu tạo": lop["ten"],
                                 "Chiều dày": day_txt, "Vật liệu": lop["vat_lieu"]})
            st.table(pd.DataFrame(lp_data))
            st.info(f"Tổng chiều dày lớp phủ: **{lop_phu['tong_day_min']}–{lop_phu['tong_day_tt']} mm**")
            for kn in lop_phu.get('khuyen_nghi', []):
                st.warning(kn)
            st.caption(lop_phu.get('ghi_chu', ''))

    # ── VI. MẶT CẮT NGANG ────────────────────────────────────────────────
    with st.expander("**VI. MẶT CẮT NGANG CẦU**", expanded=False):
        try:
            _mcn_in = dict(d.get('mcn_oto_input') or {})
            res_mcn = YTHH.thiet_ke_mcn_cau_web({
                "loai": d.get('loai_duong', 'Do thi'),
                "vtk":  d.get('vtk', 60),
                **_mcn_in,
            })

            tra_tt     = res_mcn.get("tra_cuu_toi_thieu")
            is_caotoc  = res_mcn.get("is_caotoc", False)
            is_dothi   = res_mcn.get("is_dothi", False)

            if is_caotoc and tra_tt and tra_tt.get("status") == "success":
                # ── So sánh Bảng 1 TCVN 5729:2012 ──
                st.caption(f"📐 {res_mcn['tieu_chuan']} — Vtk={tra_tt.get('vtk','')}km/h — {tra_tt.get('mo_ta_dpc','')}")
                df_so_sanh = pd.DataFrame({
                    "Yếu tố": [
                        "Số làn/chiều", "Chiều rộng 1 làn (m)", "Mặt đường/chiều (m)",
                        "Lề gia cố/DAT (m)", "DAT dải giữa (m)", "DPC lõi (m)", "Nền đường (m)"
                    ],
                    "Tiêu chuẩn (TCVN 5729:2012)": [
                        tra_tt["n_lan_moi_chieu_min"], tra_tt["w_lan_min"],
                        tra_tt["w_mat_duong_min"], tra_tt["w_le_dat_min"],
                        tra_tt["w_dat_an_toan_dg_min"], tra_tt["w_dpc_core_min"],
                        tra_tt["w_nen_min"],
                    ],
                    "Thiết kế (người dùng nhập)": [
                        res_mcn["n_lan_moi_chieu"], res_mcn["w_lan"],
                        res_mcn["w_mat_1chieu"], res_mcn["w_le_gc"],
                        res_mcn["w_dat_an_toan_dg"], res_mcn["w_dpc_core"],
                        round(res_mcn.get("w_nen_duong_min") or
                              2*(res_mcn["w_le_trong_co"]+res_mcn["w_le_gc"]+res_mcn["w_mat_1chieu"])
                              +res_mcn["w_dpc"], 2),
                    ],
                })
                st.table(df_so_sanh)
                _khong_dat = (
                    res_mcn["n_lan_moi_chieu"] < tra_tt["n_lan_moi_chieu_min"] or
                    res_mcn["w_lan"]           < tra_tt["w_lan_min"] or
                    res_mcn["w_le_gc"]         < tra_tt["w_le_dat_min"] or
                    res_mcn["w_dat_an_toan_dg"]< tra_tt["w_dat_an_toan_dg_min"] or
                    res_mcn["w_dpc_core"]      < tra_tt["w_dpc_core_min"]
                )
                if _khong_dat:
                    st.error("⚠️ Một số giá trị thiết kế NHỎ HƠN mức tiêu chuẩn TCVN 5729:2012!")
                else:
                    st.success("✅ Giá trị thiết kế thỏa mãn tiêu chuẩn TCVN 5729:2012.")
                st.caption(
                    f"Độ dốc ngang (cố định TCVN 5729:2012): "
                    f"Mặt đường & DAT = **{res_mcn['i_doc_ngang']:g}%** | "
                    f"Lề trồng cỏ = **{res_mcn['i_le_trong_co']:g}%**"
                )

            elif is_dothi and tra_tt and tra_tt.get("status") == "success":
                # ── So sánh Bảng 10/13/14/15 TCVN 13592:2022 ──
                _dkx = tra_tt.get("dieu_kien_xd", "II")
                st.caption(
                    f"📐 {res_mcn['tieu_chuan']} — {tra_tt.get('mo_ta','')} | "
                    f"VTK {tra_tt.get('vtk','')} km/h | Điều kiện xây dựng: {_dkx}"
                )
                # Bảng 10/13
                _dat_at_cap = (tra_tt.get('w_dat_at_loaiI') if _dkx == "I"
                               else tra_tt.get('w_dat_at_loaiII_III'))
                df_10_13 = pd.DataFrame({
                    "Yếu tố": [
                        "Số làn xe (tối thiểu)", "Chiều rộng 1 làn (m)",
                        "Lề đường tối thiểu (m)", "Lề đường tối đa (m)",
                    ],
                    f"Tiêu chuẩn Bảng 10/13": [
                        f"{tra_tt['so_lan_toi_thieu']} (mong {tra_tt['so_lan_mong_muon']})",
                        tra_tt["w_lan_min"], tra_tt["w_le_min"], tra_tt["w_le_max"],
                    ],
                    "Thiết kế (nhập)": [
                        res_mcn["n_lan"], res_mcn["w_lan"],
                        res_mcn["w_le"], res_mcn["w_le"],
                    ],
                })
                st.table(df_10_13)
                _khong_dat_dt = (
                    res_mcn["n_lan"] < tra_tt["so_lan_toi_thieu"] or
                    res_mcn["w_lan"] < tra_tt["w_lan_min"] or
                    res_mcn["w_le"]  < tra_tt["w_le_min"]
                )
                if _khong_dat_dt:
                    st.error("⚠️ Một số giá trị NHỎ HƠN mức tối thiểu TCVN 13592:2022!")
                else:
                    st.success("✅ Phần xe chạy và lề thỏa mãn TCVN 13592:2022.")
                if _dat_at_cap:
                    st.caption(
                        f"Dải an toàn (Bảng 13, đk {_dkx}): **{_dat_at_cap:.2f}m** "
                        f"(bắt buộc khi VTK ≥ 50 km/h — Điều 9.4.3)"
                    )
                # Bảng 14 — DPC
                _dpc_min = tra_tt.get("dpc_min")
                _dpc_mm  = tra_tt.get("dpc_mong_muon")
                _dpc_note= tra_tt.get("dpc_note")
                if tra_tt.get("co_dpc") and _dpc_min is not None:
                    _w_dpc_tk = res_mcn.get("w_dpc", 0)
                    _ok_dpc   = _w_dpc_tk >= _dpc_min
                    st.caption(
                        f"Dải phân cách (Bảng 14, đk {_dkx}): "
                        f"tối thiểu **{_dpc_min:.2f}m** (mong muốn {_dpc_mm:.2f}m) | "
                        f"Thiết kế: **{_w_dpc_tk:.2f}m** — "
                        + ("✅ Đạt" if _ok_dpc else "⚠️ Chưa đạt tối thiểu")
                    )
                elif _dpc_note:
                    st.caption(f"Dải phân cách (Bảng 14): {_dpc_note}")
                # Bảng 15 — Hè đường
                _he_min = tra_tt.get("he_min")
                _w_he_tk = res_mcn.get("w_he", res_mcn.get("w_lc", 0))
                if _he_min is not None:
                    _ok_he = _w_he_tk >= _he_min
                    st.caption(
                        f"Hè đường (Bảng 15, đk {_dkx}): "
                        f"tối thiểu **{_he_min:.1f}m** | "
                        f"Thiết kế: **{_w_he_tk:.1f}m** — "
                        + ("✅ Đạt" if _ok_he else "⚠️ Chưa đạt tối thiểu")
                    )
                # Bảng 12 — độ dốc ngang
                _b12 = res_mcn.get("doc_ngang_b9", {})
                if _b12:
                    _i    = res_mcn.get("i_doc_ngang", _b12.get("i_goi_y", 2.0))
                    _ok_i = res_mcn.get("i_doc_ngang_trong_pham_vi", True)
                    st.caption(
                        f"Độ dốc ngang — {_b12.get('mo_ta','')} | "
                        f"Phạm vi Bảng 12: **{_b12['i_min']:g}%–{_b12['i_max']:g}%** | "
                        f"Thiết kế: **{_i:.1f}%** — "
                        + ("✅ Trong phạm vi" if _ok_i else "⚠️ Ngoài phạm vi TCVN")
                    )

            elif not is_caotoc and not is_dothi and tra_tt and tra_tt.get("status") == "success":
                # ── So sánh Bảng 6/7 TCVN 4054:2005 ──
                st.caption(f"📐 {res_mcn['tieu_chuan']} — Cấp {tra_tt['cap_duong']}")
                df_so_sanh = pd.DataFrame({
                    "Yếu tố": ["Số làn xe", "Chiều rộng 1 làn (m)", "Dải phân cách (m)",
                               "Lề đường (m)", "Lề gia cố (m)"],
                    "Tối thiểu (TCVN 4054:2005)": [
                        tra_tt["so_lan_min"], tra_tt["w_lan_min"], tra_tt["w_dpc_min"],
                        tra_tt["w_le_min"], tra_tt["w_le_gc_min"] or "—",
                    ],
                    "Thiết kế (người dùng nhập)": [
                        res_mcn["n_lan"], res_mcn["w_lan"], res_mcn["w_dpc"],
                        res_mcn["w_le"], res_mcn["w_le_gc"] or "—",
                    ],
                })
                st.table(df_so_sanh)
                _khong_dat = (
                    res_mcn["n_lan"] < tra_tt["so_lan_min"] or
                    res_mcn["w_lan"] < tra_tt["w_lan_min"] or
                    res_mcn["w_dpc"] < tra_tt["w_dpc_min"] or
                    res_mcn["w_le"]  < tra_tt["w_le_min"]
                )
                if _khong_dat:
                    st.error("⚠️ Một số giá trị thiết kế NHỎ HƠN mức tối thiểu theo tiêu chuẩn!")
                else:
                    st.success("✅ Giá trị thiết kế thỏa mãn chiều rộng tối thiểu theo tiêu chuẩn.")

                # ── Bảng 8 ──
                _dpc_b8 = res_mcn.get("dpc_b8", {})
                if res_mcn.get("w_dpc", 0) > 0 and _dpc_b8:
                    _w_dpc_min_b8 = res_mcn.get("w_dpc_min_b8", 0)
                    _ok_dpc = res_mcn["w_dpc"] >= _w_dpc_min_b8
                    st.caption(
                        f"Dải phân cách — {_dpc_b8.get('mo_ta','')} | "
                        f"Tối thiểu Bảng 8: **{_w_dpc_min_b8:g}m** | "
                        f"Thiết kế: **{res_mcn['w_dpc']:.2f}m** — "
                        + ("✅ Đạt" if _ok_dpc else "⚠️ Chưa đạt")
                    )
                # ── Bảng 9 ──
                _b9 = res_mcn.get("doc_ngang_b9", {})
                if _b9:
                    _i = res_mcn.get("i_doc_ngang", _b9.get("i_goi_y", 2.0))
                    _ok_i = res_mcn.get("i_doc_ngang_trong_pham_vi", True)
                    st.caption(
                        f"Độ dốc ngang — {_b9.get('mo_ta','')} | "
                        f"Phạm vi Bảng 9: **{_b9['i_min']:g}% – {_b9['i_max']:g}%** | "
                        f"Thiết kế: **{_i:.1f}%** — "
                        + ("✅ Trong phạm vi" if _ok_i else "⚠️ Ngoài phạm vi TCVN")
                    )

            elif tra_tt and tra_tt.get("status") == "error":
                st.warning(f"⚠️ {tra_tt.get('message')}")

            st.code(res_mcn.get('mo_phong', 'Chưa có sơ đồ.'), language="text")

            if is_caotoc:
                st.markdown("#### MCN đường đầu cầu")
            _c2d, _c3d = st.columns(2)
            with _c2d:
                fig_mcn_2d = PLOT.ve_mat_cat_ngang(res_mcn, bridge_mode=False)
                st.plotly_chart(fig_mcn_2d, use_container_width=True,
                                config={"scrollZoom": True, "displayModeBar": True},
                                key="mcn_oto_2d")
            with _c3d:
                fig_mcn_3d = PLOT.ve_mat_cat_ngang_3d(res_mcn, chieu_dai=20.0, bridge_mode=False)
                st.plotly_chart(fig_mcn_3d, use_container_width=True,
                                config={"scrollZoom": True, "displayModeBar": True},
                                key="mcn_oto_3d")

            if is_caotoc:
                st.markdown("#### MCN tại cầu — Điều 6.12 TCVN 5729:2012")
                _c2d_cau, _c3d_cau = st.columns(2)
                with _c2d_cau:
                    fig_cau_2d = PLOT.ve_mat_cat_ngang(res_mcn, bridge_mode=True)
                    st.plotly_chart(fig_cau_2d, use_container_width=True,
                                    config={"scrollZoom": True, "displayModeBar": True},
                                    key="mcn_cau_2d")
                with _c3d_cau:
                    fig_cau_3d = PLOT.ve_mat_cat_ngang_3d(res_mcn, chieu_dai=20.0, bridge_mode=True)
                    st.plotly_chart(fig_cau_3d, use_container_width=True,
                                    config={"scrollZoom": True, "displayModeBar": True},
                                    key="mcn_cau_3d")
                st.caption(
                    "Theo Điều 6.12.1 TCVN 5729:2012: chiều rộng cầu bằng chiều rộng nền đường (Bảng 1). "
                    "Lề trồng cỏ được thay bằng lan can cầu + dải phụ khai thác cùng chiều rộng. "
                    "Theo Điều 6.12.4: hai chiều xe chạy thường được bố trí thành 2 cầu tách biệt."
                )
        except Exception as ex:
            import traceback
            st.error(f"Lỗi mặt cắt ngang: {ex}")
            with st.expander("Chi tiết lỗi"):
                st.code(traceback.format_exc())

    # ── VII. SO SÁNH 3 PHƯƠNG ÁN LOẠI DẦM ───────────────────────────────
    _alts = st.session_state.get("alternatives")
    with st.expander("**VII. SO SÁNH 3 PHƯƠNG ÁN LOẠI DẦM**", expanded=bool(_alts)):
        if not _alts:
            st.info("Chạy pipeline để tự động sinh 3 phương án so sánh.")
        else:
            _pa_colors = [a["color"] for a in _alts]
            _pa_labels = [a["label"] for a in _alts]

            # Thẻ tóm tắt nhanh mỗi PA
            _c1, _c2, _c3 = st.columns(3)
            for _col, _alt in zip([_c1, _c2, _c3], _alts):
                _k  = _alt["kcn"]
                _t  = _alt["tru"]
                _m  = _alt["mong"]
                with _col:
                    st.markdown(
                        f"<div style='background:{_alt['color']}18;border:1px solid {_alt['color']}55;"
                        f"border-radius:10px;padding:14px'>"
                        f"<div style='font-weight:700;color:{_alt['color']};font-size:15px'>{_alt['label']}</div>"
                        f"<div style='font-size:12px;color:#aaa;margin-bottom:10px'>{_alt['mo_ta']}</div>"
                        f"<table style='width:100%;font-size:13px'>"
                        f"<tr><td style='color:#888'>Sơ đồ nhịp</td>"
                        f"<td style='text-align:right;font-weight:600'>{_k['tong_so_nhip']} × {_k['chieu_dai']:.1f} m</td></tr>"
                        f"<tr><td style='color:#888'>Chiều cao H</td>"
                        f"<td style='text-align:right;font-weight:600'>{_k['chieu_cao_dam']:.2f} m</td></tr>"
                        f"<tr><td style='color:#888'>L/H</td>"
                        f"<td style='text-align:right;font-weight:600'>{_k.get('ti_le_L_H',0) or 0:.1f}</td></tr>"
                        f"<tr><td style='color:#888'>Loại trụ</td>"
                        f"<td style='text-align:right;font-weight:600'>{_t['loai_tru']}</td></tr>"
                        f"<tr><td style='color:#888'>Số trụ</td>"
                        f"<td style='text-align:right;font-weight:600'>{_alt['n_tru']} trụ</td></tr>"
                        f"<tr><td style='color:#888'>Loại móng</td>"
                        f"<td style='text-align:right;font-weight:600'>{_m['loai_mong']}</td></tr>"
                        f"<tr><td style='color:#888'>Đường kính cọc</td>"
                        f"<td style='text-align:right;font-weight:600'>{_m['D_coc_chon_txt']}</td></tr>"
                        f"<tr style='border-top:1px solid #444'><td style='color:#888;padding-top:6px'>Chi phí tương đối</td>"
                        f"<td style='text-align:right;font-weight:700;color:{_alt['color']};padding-top:6px'>{_alt['cost_pct']:.0f}%</td></tr>"
                        f"<tr><td style='color:#888'>Thời gian TC</td>"
                        f"<td style='text-align:right;font-weight:600'>{_alt['thoi_gian']:.1f} tháng</td></tr>"
                        f"</table></div>",
                        unsafe_allow_html=True,
                    )

            st.markdown("")
            # Bieu do nhanh chi phi + so tru
            _fig2 = go.Figure()
            _fig2.add_trace(go.Bar(
                name="Chi phí (%)",
                x=_pa_labels,
                y=[a["cost_pct"] for a in _alts],
                marker_color=_pa_colors,
                text=[f"{a['cost_pct']:.0f}%" for a in _alts],
                textposition="outside",
                yaxis="y",
            ))
            _fig2.add_trace(go.Scatter(
                name="Số trụ giữa",
                x=_pa_labels,
                y=[a["n_tru"] for a in _alts],
                mode="lines+markers+text",
                text=[str(a["n_tru"]) for a in _alts],
                textposition="top center",
                line=dict(color="#e74c3c", width=2, dash="dot"),
                marker=dict(size=10, color="#e74c3c"),
                yaxis="y2",
            ))
            _fig2.update_layout(
                yaxis=dict(title="Chi phí (%, Dầm I=100%)", side="left"),
                yaxis2=dict(title="Số trụ giữa", side="right", overlaying="y",
                            rangemode="tozero"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                height=280, margin=dict(t=10, b=10, l=10, r=10),
                legend=dict(orientation="h", y=-0.25),
                barmode="group",
            )
            st.plotly_chart(_fig2, use_container_width=True, key="pa_quick_chart")
            st.caption("Xem đầy đủ biểu đồ radar & bảng chi tiết ở tab **SO SÁNH PHƯƠNG ÁN**.")

    st.markdown("---")
    st.caption("Kết quả mang tính tham khảo sơ bộ. Cần kiểm tra và điều chỉnh theo tiêu chuẩn TCVN hiện hành.")

elif selected_ribbon == "BẢN VẼ KỸ THUẬT":
    d   = st.session_state.design_data
    kcn = d.get("kcn_result") or d.get("ai_result")
    tru = d.get("tru_result")
    has_ai = kcn is not None

    # ── Khai báo địa hình (luôn hiển thị) ──────────────────────────────
    with st.expander(
        "📥 Khai báo dữ liệu địa hình (file .NTD + bảng tọa độ VN-2000)",
        expanded=(not has_ai or "df_geology" not in st.session_state),
    ):
        st.caption("Nạp file khảo sát để bản vẽ kết cấu tích hợp địa hình thực đo.")
        _c1, _c2 = st.columns(2)
        with _c1:
            file_khao_sat = st.file_uploader(
                "📂 File .NTD (trắc dọc – trắc ngang)", type=["ntd"], key="ntd_up"
            )
        with _c2:
            file_toa_do = st.file_uploader(
                "📍 Tọa độ tim tuyến (.CSV / .XLSX)", type=["csv","xlsx"], key="coord_up"
            )
        if file_khao_sat and file_toa_do:
            with st.spinner("⚡ Đang đồng bộ tọa độ VN-2000..."):
                df_ntd   = TV.parse_ntd_file(file_khao_sat)
                df_coord = TV.parse_coordinate_file(file_toa_do)
            if df_coord is not None and not df_ntd.empty:
                _dg = TV.convert_to_vn2000(df_ntd, df_coord)
                if not _dg.empty:
                    st.session_state.df_geology = _dg
                    _tl = (_dg[_dg["Offset"] == 0][["Lý trình","Z"]]
                           .drop_duplicates("Lý trình").sort_values("Lý trình"))
                    st.session_state.df_tim_line = _tl
                    st.success(f"✅ Đã đồng bộ {len(_dg)} điểm địa hình theo VN-2000!")

    st.markdown("---")

    if not has_ai:
        st.info("⚙️ Nhấn **KHAI BÁO SỐ LIỆU** trong thanh bên trái để nhập thông số và chạy AI.")
    else:
        _df_geo  = st.session_state.get("df_geology", None)
        _df_tim  = st.session_state.get("df_tim_line", None)
        has_terr = _df_geo is not None and not _df_geo.empty

        # Thông tin brief
        _geo_d = d.get("geo_logic", {})
        st.caption(
            f"📊 L_cầu=**{_geo_d.get('L_cau',0):.1f}m** | "
            f"{kcn.get('tong_so_nhip','?')}×{kcn.get('chieu_dai','?')}m "
            f"**{kcn.get('loai_dam','').upper()}** | "
            f"B_tk={d.get('B',0):.1f}m × H_tk={d.get('H',0):.2f}m | "
            + ("🗺️ Địa hình: đã nạp" if has_terr else "🗺️ Địa hình: chưa nạp (tải ở trên)")
        )

        # ── Sub-tabs ────────────────────────────────────────────────────
        (tab_3d, tab_btc, tab_mcn_vt,
         tab_spt, tab_tng, tab_dami,
         tab_dia_chat, tab_export) = st.tabs([
            "🌐 3D Tổng hợp"  + (" 🗺️" if has_terr else " (sơ đồ)"),
            "📋 Bố trí chung",
            "✂️ MCN Mố/Trụ",
            "🔩 Chi tiết SPT",
            "🔩 T ngược",
            "🔩 Dầm I",
            "🪨 Địa chất",
            "📤 Xuất bản vẽ",
        ])

        # ── TAB 1: 3D Tổng hợp ─────────────────────────────────────────
        with tab_3d:
            if has_terr:
                # ── Kiểm tra alignment lý trình cầu vs địa hình ──────────────
                _geo_d2 = d.get("geo_logic", {})
                _xmo_t  = float(_geo_d2.get("x_mo_trai", -60))
                _xmo_p  = float(_geo_d2.get("x_mo_phai",  60))
                _xtim   = float(_geo_d2.get("x_tim_clearance", (_xmo_t+_xmo_p)/2))
                _lt_col2= next((c for c in _df_geo.columns if 'ý trình' in c or c.lower()=='ly_trinh'), 'Lý trình')
                _lt_min2= float(_df_geo[_lt_col2].min()) if _lt_col2 in _df_geo.columns else 0
                _lt_max2= float(_df_geo[_lt_col2].max()) if _lt_col2 in _df_geo.columns else 999
                _overlap = max(_lt_min2, _xmo_t) < min(_lt_max2, _xmo_p)

                _c1, _c2, _c3 = st.columns(3)
                _c1.metric("🗺️ Lý trình địa hình", f"{_lt_min2:.1f} → {_lt_max2:.1f} m")
                _c2.metric("🌉 Lý trình cầu", f"{_xmo_t:.1f} → {_xmo_p:.1f} m")
                _c3.metric("⭕ Tim tĩnh không", f"{_xtim:.1f} m")

                if not _overlap:
                    _suggest_tim = (_lt_min2 + _lt_max2) / 2
                    st.error(
                        f"❌ **Cầu không nằm trong phạm vi địa hình!** "
                        f"Địa hình: {_lt_min2:.1f}→{_lt_max2:.1f}m | Cầu: {_xmo_t:.1f}→{_xmo_p:.1f}m. "
                        f"👉 Mở **OPTIONS** và đặt **Lý trình tim tĩnh không ≈ {_suggest_tim:.1f}m** "
                        f"để cầu khớp với địa hình."
                    )
                else:
                    _pct_ok = 100*(min(_lt_max2,_xmo_p)-max(_lt_min2,_xmo_t))/max(1,_xmo_p-_xmo_t)
                    st.success(f"✅ Cầu khớp địa hình ({_pct_ok:.0f}% chiều dài cầu nằm trong phạm vi địa hình)")

                col_o1, col_o2, col_o3, col_o4 = st.columns(4)
                with col_o1:
                    che_do_view = st.selectbox("🎨 Địa hình:",
                        ["Bề mặt mịn","Đường đồng mức","Lưới tam giác"], key="cd3d")
                with col_o2:
                    he_so_z = st.slider("📐 Phóng đại Z:", 0.05, 3.00, 0.50, 0.05, key="hsz3d")
                with col_o3:
                    do_min_view = st.select_slider("✨ Mịn hoá:",
                        options=[1,3,5,7], value=3, key="dm3d")
                with col_o4:
                    render_mode_3d = st.selectbox(
                        "🖥️ Chế độ hiển thị:",
                        ["Shaded", "Realistic", "X-Ray", "Wireframe"],
                        key="rm3d",
                        help="Shaded: mặc định • Realistic: đổ bóng cao • X-Ray: xuyên thấu • Wireframe: khung lưới"
                    )
                try:
                    _fig_t, mx, my, mz = TV.ve_dia_hinh_3d(
                        _df_geo, he_so_z=he_so_z, che_do=che_do_view, do_min=do_min_view
                    )
                    if _fig_t:
                        _n_before = len(_fig_t.data)
                        _err_overlay = None
                        try:
                            BVK.add_all_to_terrain_fig(_fig_t, d, _df_geo, he_so_z)
                            BVK.apply_render_mode(_fig_t, render_mode_3d)
                        except Exception as _oe:
                            _err_overlay = str(_oe)
                        _n_after = len(_fig_t.data)

                        st.plotly_chart(_fig_t, use_container_width=True,
                                        config={"displayModeBar": True})
                        st.caption(
                            f"Địa hình: {_n_before} trace | Kết cấu cầu: +{_n_after - _n_before} trace. "
                            "Kéo chuột xoay • Scroll zoom • Shift+drag pan."
                        )
                        if _err_overlay:
                            st.error(f"Lỗi overlay kết cấu: {_err_overlay}")
                        elif _n_after == _n_before:
                            st.warning("⚠️ Không thêm được trace kết cấu — kiểm tra cột df_geology bên dưới")
                            with st.expander("Debug df_geology"):
                                st.write("Columns:", list(_df_geo.columns))
                                st.write("Offset values:", sorted(_df_geo['Offset'].unique()[:10].tolist()) if 'Offset' in _df_geo.columns else "N/A")
                                st.write("x_mo_trai:", d.get('geo_logic',{}).get('x_mo_trai'))
                                st.write("Lý trình range:", float(_df_geo['Lý trình'].min()), "→", float(_df_geo['Lý trình'].max()) if 'Lý trình' in _df_geo.columns else "N/A")
                    else:
                        st.error("Không tạo được mô hình địa hình.")
                except Exception as _e:
                    st.error(f"Lỗi 3D tổng hợp: {_e}")
            else:
                st.info("📌 Nạp file địa hình ở trên để xem kết cấu tích hợp địa hình thực đo. "
                        "Hiện đang hiển thị mô hình sơ đồ cầu.")
                _rm_no_terr = st.selectbox(
                    "🖥️ Chế độ hiển thị:", ["Shaded","Realistic","X-Ray","Wireframe"],
                    key="rm3d_noterr"
                )
                try:
                    fig_3d = BVK.ve_cau_3d(d, df_tim_line=None)
                    BVK.apply_render_mode(fig_3d, _rm_no_terr)
                    st.plotly_chart(fig_3d, use_container_width=True,
                                    config={"scrollZoom": True, "displayModeBar": True})
                except Exception as _e:
                    st.error(f"Lỗi vẽ 3D: {_e}")

        # ── TAB 2: Bố trí chung ────────────────────────────────────────
        with tab_btc:
            st.markdown("##### Bố trí chung — Bình đồ + Trắc dọc + MCN điển hình")
            try:
                _btc1, _btc2 = st.columns([3, 2])
                with _btc1:
                    st.markdown("**Bình đồ cầu** (nhìn từ trên)")
                    fig_bd = BVK.ve_binh_do_2d(d, df_tim_line=_df_tim)
                    st.plotly_chart(fig_bd, use_container_width=True,
                                    config={"scrollZoom": True, "displayModeBar": True})
                with _btc2:
                    st.markdown("**MCN điển hình**")
                    fig_mcn_btc = BVK.ve_mat_cat_ngang_2d(d)
                    st.plotly_chart(fig_mcn_btc, use_container_width=True,
                                    config={"scrollZoom": True, "displayModeBar": True})
                st.markdown("**Trắc dọc cầu**")
                fig_td_btc = BVK.ve_so_do_nhip_2d(d, df_tim_line=_df_tim)
                st.plotly_chart(fig_td_btc, use_container_width=True,
                                config={"scrollZoom": True, "displayModeBar": True})
            except Exception as _e:
                st.error(f"Lỗi tab Bố trí chung: {_e}")

        # ── TAB 3: MCN tại vị trí mố / trụ ───────────────────────────
        with tab_mcn_vt:
            st.markdown("##### Mặt cắt ngang tại từng vị trí Mố – Trụ")
            _kcn_vt = d.get("kcn_result") or d.get("ai_result", {})
            _n_nhip_vt = int(_kcn_vt.get("tong_so_nhip", 3))
            _n_tru_vt  = max(0, _n_nhip_vt - 1)
            _vi_tri_options = ["mo_trai"] + [f"tru_{i+1}" for i in range(_n_tru_vt)] + ["mo_phai"]
            _vi_tri_labels  = (
                ["Mố trái"] +
                [f"Trụ T{i+1}" for i in range(_n_tru_vt)] +
                ["Mố phải"]
            )
            _sel_col1, _sel_col2 = st.columns([2, 3])
            with _sel_col1:
                _vt_idx = st.radio(
                    "Chọn vị trí:",
                    options=range(len(_vi_tri_options)),
                    format_func=lambda i: _vi_tri_labels[i],
                    horizontal=False, key="mcn_vt_radio"
                )
            _selected_vt = _vi_tri_options[_vt_idx]
            with _sel_col2:
                _geo_vt = d.get("geo_logic", {})
                _piers_vt = BVK.calc_pier_positions(
                    float(_geo_vt.get("x_mo_trai", -60)),
                    float(_geo_vt.get("x_mo_phai",  60)),
                    _n_nhip_vt,
                    float(_geo_vt.get("x_tim_clearance", 0)),
                    float(d.get("B", 20))
                )
                _pos_map = {
                    "mo_trai": float(_geo_vt.get("x_mo_trai", -60)),
                    "mo_phai": float(_geo_vt.get("x_mo_phai",  60)),
                    **{f"tru_{i+1}": _piers_vt[i] for i in range(len(_piers_vt))}
                }
                _x_cut_show = _pos_map.get(_selected_vt, 0)
                st.metric("Lý trình vị trí cắt", f"{_x_cut_show:.2f} m")
                st.metric("Cao độ đáy dầm", f"{d.get('cao_day_dam', 0):.3f} m")
                st.metric("H trụ ước tính", f"{d.get('H_tru_est', 0):.2f} m")
            try:
                fig_mcn_vt = BVK.ve_mcn_vi_tri(d, vi_tri=_selected_vt, df_geology=_df_geo)
                st.plotly_chart(fig_mcn_vt, use_container_width=True,
                                config={"scrollZoom": True, "displayModeBar": True})
            except Exception as _e:
                st.error(f"Lỗi vẽ MCN vị trí: {_e}")

        # ── TAB: Chi tiết dầm SPT ─────────────────────────────────────
        with tab_spt:
            try:
                CTD.render_chi_tiet_loai(d, st, "Super-T", key_prefix="spt")
            except Exception as _e:
                import traceback
                st.error(f"Lỗi tab SPT: {_e}")
                with st.expander("Chi tiết lỗi"):
                    st.code(traceback.format_exc())

        # ── TAB: Chi tiết dầm T ngược ─────────────────────────────────
        with tab_tng:
            try:
                CTD.render_chi_tiet_loai(d, st, "T ngược", key_prefix="tng")
            except Exception as _e:
                import traceback
                st.error(f"Lỗi tab T ngược: {_e}")
                with st.expander("Chi tiết lỗi"):
                    st.code(traceback.format_exc())

        # ── TAB: Chi tiết dầm I ────────────────────────────────────────
        with tab_dami:
            try:
                CTD.render_chi_tiet_loai(d, st, "Dầm I", key_prefix="dami")
            except Exception as _e:
                import traceback
                st.error(f"Lỗi tab Dầm I: {_e}")
                with st.expander("Chi tiết lỗi"):
                    st.code(traceback.format_exc())

        # ── TAB: Địa chất & Địa hình chi tiết ─────────────────────────
        with tab_dia_chat:
            if not has_terr:
                st.info("Nạp file địa hình ở trên để xem mô hình địa chất.")
            else:
                try:
                    st.subheader("📊 Mô hình Địa hình 3D chi tiết")
                    col_d1, col_d2, col_d3 = st.columns(3)
                    with col_d1:
                        _che = st.selectbox("Chế độ:", ["Bề mặt mịn","Đường đồng mức","Lưới tam giác"], key="dccd")
                    with col_d2:
                        _hz  = st.slider("Phóng đại Z:", 0.05, 3.0, 0.5, 0.05, key="dchz")
                    with col_d3:
                        _dm  = st.select_slider("Mịn hoá:", [1,3,5,7], 3, key="dcdm")
                    _ftmp, _, _, _ = TV.ve_dia_hinh_3d(_df_geo, he_so_z=_hz, che_do=_che, do_min=_dm)

                    st.markdown("---")
                    st.subheader("📊 Tích hợp Địa chất Công trình")
                    file_excel_dc = st.file_uploader("Tải file Excel địa chất (3 sheet):", type=["xlsx"], key="dc_ex")
                    df_hk, df_layers, df_spt = None, None, None
                    hien_mat_lop, hien_khoi_lop, do_trong_dh = True, False, 1.0
                    if file_excel_dc:
                        with st.spinner("Đang phân tích địa chất..."):
                            df_hk, df_layers, df_spt = TV.doc_excel_dia_chat_3_sheet(file_excel_dc)
                        if df_hk is not None and not df_hk.empty:
                            st.success(f"✅ Định vị {len(df_hk)} hố khảo sát!")
                            cdc1, cdc2, cdc3 = st.columns(3)
                            with cdc1:
                                hien_mat_lop = st.checkbox("Mặt phẳng lớp đất", True)
                            with cdc2:
                                hien_khoi_lop = st.checkbox("Khối lớp đất", False)
                            with cdc3:
                                do_trong_dh = st.slider("Độ trong suốt:", 0.35, 1.0, 0.72, 0.05)
                    if _ftmp:
                        if df_hk is not None and not df_hk.empty:
                            _ftmp = TV.dap_them_ket_cau_dia_chat_3d(
                                _ftmp, df_hk, df_layers, df_spt,
                                _, _, _,
                                he_so_z=_hz,
                                hien_mat_phang_lop=hien_mat_lop,
                                hien_khoi_lop=hien_khoi_lop,
                                do_trong_dia_hinh=do_trong_dh if (hien_mat_lop or hien_khoi_lop) else 1.0
                            )
                        st.plotly_chart(_ftmp, use_container_width=True,
                                        config={"displayModeBar": True})
                except Exception as _e:
                    st.error(f"Lỗi địa chất: {_e}")

        # ── TAB: Xuất bản vẽ ───────────────────────────────────────────
        with tab_export:
            st.subheader("📤 Xuất bản vẽ kỹ thuật")
            exp_cols = st.columns(3)
            with exp_cols[0]:
                if st.button("⬇️ DXF Trắc dọc", use_container_width=True, key="xdxftd"):
                    try:
                        _b = EXP.export_trac_doc_dxf(d)
                        st.download_button("💾 DXF", _b, "trac_doc.dxf",
                                           mime="application/octet-stream", key="dl_td2")
                    except Exception as _ex:
                        st.error(f"Lỗi: {_ex}")
            with exp_cols[1]:
                if st.button("⬇️ DXF Mặt cắt ngang", use_container_width=True, key="xdxfmcn"):
                    try:
                        _b = EXP.export_mcn_dxf(d)
                        st.download_button("💾 DXF", _b, "mat_cat_ngang.dxf",
                                           mime="application/octet-stream", key="dl_mcn2")
                    except Exception as _ex:
                        st.error(f"Lỗi: {_ex}")
            with exp_cols[2]:
                if st.button("⬇️ IFC kết cấu cầu", use_container_width=True, key="xifcbr"):
                    try:
                        _b = EXP.export_bridge_ifc(d)
                        st.download_button("💾 IFC", _b, "bridge.ifc",
                                           mime="application/octet-stream", key="dl_brifc2")
                    except Exception as _ex:
                        st.error(f"Lỗi: {_ex}")
            if has_terr:
                st.markdown("---")
                if st.button("📤 Xuất địa hình IFC", key="xifcter"):
                    with st.spinner("Đang xuất..."):
                        try:
                            _fig_ex, mx, my, mz = TV.ve_dia_hinh_3d(
                                _df_geo, he_so_z=1.0, che_do="Bề mặt mịn", do_min=3)
                            ifc_path = "terrain_output.ifc"
                            ok = TV.export_terrain_to_ifc(mx, my, mz, ifc_path, "DiaHinh_KhaoSat")
                            if ok:
                                with open(ifc_path, "rb") as _fh:
                                    st.download_button("⬇️ Tải IFC địa hình", _fh,
                                                       "terrain.ifc", mime="application/octet-stream",
                                                       key="dl_terrifc2")
                                st.success("Xuất IFC địa hình thành công!")
                            else:
                                st.error("Xuất thất bại.")
                        except Exception as _ex:
                            st.error(f"Lỗi: {_ex}")

# =========================================================================
# SO SÁNH PHƯƠNG ÁN
# =========================================================================
elif selected_ribbon == "SO SÁNH PHƯƠNG ÁN":
    alts = st.session_state.get("alternatives", None)
    if alts is None:
        st.title("📊 So sánh 3 Phương án Loại Dầm")
        st.info("👆 Nhấn **⚙️ OPTIONS** → điền thông số → **OK** để AI tự sinh 3 phương án cho công trình cụ thể của bạn.")
        st.markdown("---")
        st.markdown("### Giới thiệu 3 phương án so sánh")
        st.caption("Hệ thống sẽ tính toán cùng một cầu với 3 loại dầm khác nhau, sau đó so sánh kỹ thuật + kinh tế để hỗ trợ chọn phương án tối ưu.")

        # Thẻ thông tin 3 loai dam
        _c1, _c2, _c3 = st.columns(3)
        _dam_cards = [
            {
                "color": "#3498db",
                "title": "PA1 — Dầm I",
                "subtitle": "BTCT dự ứng lực — đúc sẵn",
                "specs": [
                    ("Chiều dài nhịp", "18 – 33 m"),
                    ("Tỉ lệ H/L tối ưu", "1/15 – 1/18"),
                    ("Số dầm / MCN", "5 – 9 dầm"),
                    ("Khoảng cách tim", "1.8 – 2.2 m"),
                ],
                "tru": "Thân cột 2–3 trụ (tải trọng trung bình)",
                "pros": "Phổ biến nhất tại VN, nhà cung cấp nhiều, thi công nhanh",
                "cons": "Chiều cao dầm lớn hơn Super-T, cần cẩu lắp chuyên dụng",
                "use": "Cầu nông thôn, đường tỉnh, cấp IV–VI",
            },
            {
                "color": "#2ecc71",
                "title": "PA2 — T ngược",
                "subtitle": "BTCT thường / DƯL — đổ tại chỗ hoặc đúc sẵn",
                "specs": [
                    ("Chiều dài nhịp", "12 – 22 m"),
                    ("Tỉ lệ H/L tối ưu", "1/12 – 1/15"),
                    ("Số dầm / MCN", "5 – 11 dầm"),
                    ("Khoảng cách tim", "0.9 – 1.2 m"),
                ],
                "tru": "Thân cột đơn hoặc 2 trụ (tải nhỏ, nhịp ngắn)",
                "pros": "Chi phí dầm đơn chiếc thấp nhất, đơn giản thi công",
                "cons": "Nhiều trụ hơn → cản dòng, tăng chi phí móng",
                "use": "Cầu kênh nhỏ, đường nông thôn cấp V–VI",
            },
            {
                "color": "#e67e22",
                "title": "PA3 — Super-T",
                "subtitle": "BTCT dự ứng lực — đúc sẵn tiết diện T rỗng",
                "specs": [
                    ("Chiều dài nhịp", "27 – 40 m"),
                    ("Tỉ lệ H/L tối ưu", "1/18 – 1/20"),
                    ("Số dầm / MCN", "4 – 7 dầm"),
                    ("Khoảng cách tim", "2.0 – 2.5 m"),
                ],
                "tru": "Trụ đặc / đặc thân hẹp (tải lớn từ nhịp dài)",
                "pros": "Ít trụ, ít cản dòng, kết cấu thanh mảnh hiện đại",
                "cons": "Trọng lượng dầm lớn → cần thiết bị cẩu lắp mạnh hơn",
                "use": "Cầu sông lớn, quốc lộ, cấp III–IV",
            },
        ]
        for _col, _card in zip([_c1, _c2, _c3], _dam_cards):
            with _col:
                _spec_rows = "".join(
                    f"<tr><td style='color:#aaa;padding:3px 0'>{k}</td>"
                    f"<td style='text-align:right;font-weight:600;padding:3px 0'>{v}</td></tr>"
                    for k, v in _card["specs"]
                )
                st.markdown(
                    f"<div style='background:{_card['color']}15;border:1px solid {_card['color']}50;"
                    f"border-radius:12px;padding:16px;height:100%'>"
                    f"<div style='font-size:16px;font-weight:700;color:{_card['color']}'>{_card['title']}</div>"
                    f"<div style='font-size:12px;color:#999;margin-bottom:12px'>{_card['subtitle']}</div>"
                    f"<table style='width:100%;font-size:13px;border-collapse:collapse'>{_spec_rows}</table>"
                    f"<hr style='border-color:#444;margin:10px 0'>"
                    f"<div style='font-size:12px;color:#aaa'><b style='color:{_card['color']}'>Loại trụ:</b> {_card['tru']}</div>"
                    f"<div style='font-size:12px;color:#aaa;margin-top:6px'><b style='color:#2ecc71'>✔</b> {_card['pros']}</div>"
                    f"<div style='font-size:12px;color:#aaa;margin-top:4px'><b style='color:#e74c3c'>✘</b> {_card['cons']}</div>"
                    f"<div style='font-size:11px;background:{_card['color']}22;border-radius:6px;"
                    f"padding:6px 8px;margin-top:10px;color:{_card['color']}'>"
                    f"📌 {_card['use']}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("---")
        st.markdown("### Nội dung so sánh sau khi chạy pipeline")
        _info_cols = st.columns(4)
        for _ic, (_icon, _txt) in zip(_info_cols, [
            ("📐", "Bảng đa tiêu chí\nKCN · Trụ · Móng"),
            ("💰", "Chi phí tương đối\n(Dầm I = 100%)"),
            ("📊", "Biểu đồ radar\n5 tiêu chí đánh giá"),
            ("🏛️", "So sánh loại trụ\nvà phương án móng"),
        ]):
            with _ic:
                st.markdown(
                    f"<div style='text-align:center;padding:14px;background:#1e1e2e;"
                    f"border-radius:10px;border:1px solid #333'>"
                    f"<div style='font-size:26px'>{_icon}</div>"
                    f"<div style='font-size:12px;color:#aaa;white-space:pre-line;margin-top:6px'>{_txt}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
    else:
        try:
            SSP.render_comparison_tab(alts, st)
        except Exception as _ssp_err:
            st.error(f"Lỗi render so sánh phương án: {_ssp_err}")
            import traceback
            st.code(traceback.format_exc())
