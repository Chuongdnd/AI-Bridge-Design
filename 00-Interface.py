import streamlit as st
import pandas as pd
import numpy as np
import os
import io
import zipfile
import importlib
import time
import json
import pathlib
import google.generativeai as genai
import fitz
try:
    from streamlit_option_menu import option_menu
    _HAS_OPTION_MENU = True
except ImportError:
    _HAS_OPTION_MENU = False
import plotly.graph_objects as go
import plotly.io as _pio

# Mặc định thao tác bản vẽ 2D = PAN (kéo để di chuyển) thay vì zoom — dễ thao
# tác hơn cho bản vẽ kỹ thuật. Áp cho mọi template dùng trong app. Zoom vẫn
# dùng được bằng con lăn chuột (scrollZoom=True trong config).
for _tpl_name in ("plotly_white", "plotly_dark", "plotly", "none"):
    try:
        _pio.templates[_tpl_name].layout.dragmode = "pan"
    except Exception:
        pass

# --- THIẾT LẬP TRANG (CHỈ MỘT LẦN) ---
st.set_page_config(page_title="Hệ thống Thiết kế Cầu AI - UTH", layout="wide", page_icon="🏗️")

# ── Global CSS: ẩn toolbar + Engineering layout ──────────────────────────────
st.markdown("""
<style>
/* ── Ẩn Streamlit toolbar/menu/footer ── */
[data-testid="stToolbarActions"]  { display: none !important; }
[data-testid="stDecoration"]      { display: none !important; }
[data-testid="stStatusWidget"]    { display: none !important; }
.stDeployButton                   { display: none !important; }
#MainMenu                         { display: none !important; }
footer                            { display: none !important; }

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: #1a1a2a; border: 1px solid #333355;
    border-radius: 8px; padding: 8px 12px;
}
[data-testid="stMetricValue"] { font-size: 16px !important; color: #4fc3f7 !important; }

/* ── Sidebar — kích thước do JS điều khiển qua CSS var ──
   Chỉ khóa width khi sidebar ĐANG MỞ. Khi người dùng bấm nút thu gọn (collapse)
   của Streamlit, JS gắn class .cau-sb-collapsed lên <html> → bỏ khóa để Streamlit
   tự thu sidebar về 0 và nội dung/topbar dồn sát mép trái. */
html:not(.cau-sb-collapsed) [data-testid="stSidebar"] {
    min-width: var(--sidebar-width, 300px) !important;
    max-width: var(--sidebar-width, 300px) !important;
}
[data-testid="stSidebar"] {
    transition: min-width 0.05s, max-width 0.05s, transform 0.15s;
    will-change: min-width, max-width, transform;
}
[data-testid="stSidebar"] > div:first-child { padding: 56px 14px 32px !important; }

/* Main content tự co giãn theo sidebar */
section[data-testid="stMain"] {
    transition: margin-left 0.05s;
    will-change: margin-left;
}

/* Right panel — kích thước do JS điều khiển */
[data-testid="stHorizontalBlock"] > div:last-child {
    min-width: var(--right-panel-width, 220px) !important;
    max-width: var(--right-panel-width, 220px) !important;
    flex: 0 0 var(--right-panel-width, 220px) !important;
}

/* ── Topbar cố định (vị trí điều khiển qua CSS var để responsive) ── */
.uth-topbar {
    position: fixed; top: 0; right: 0;
    left: var(--sidebar-edge, var(--sidebar-width, 300px));
    transition: left 0.15s;
    z-index: 500; height: 44px;
    background: #0d0d1a; border-bottom: 2px solid #007acc;
    display: flex; align-items: center; overflow: hidden;
}
.uth-topbar .uth-tabs { display: flex; height: 100%; flex: 1; overflow-x: auto; }

/* ── Mobile: gỡ lệch 300px, xếp dọc, chống tràn ngang ── */
@media (max-width: 768px) {
    .panel-drag-handle { display: none !important; }
    [data-testid="stSidebar"] {
        min-width: 100% !important;
        max-width: 100% !important;
    }
    /* Topbar + overlay nút ribbon bám mép trái */
    .uth-topbar { left: 0 !important; }
    div[data-testid="stHorizontalBlock"]:has(button[data-testid^="ribbonbtn"]) {
        left: 0 !important;
    }
    /* Right panel xuống full-width thay vì cố định 220px */
    [data-testid="stHorizontalBlock"] > div:last-child {
        min-width: 100% !important;
        max-width: 100% !important;
        flex: 1 1 100% !important;
    }
    /* Giảm padding ngang để không tràn */
    section[data-testid="stMain"] .block-container {
        padding-left: 8px !important;
        padding-right: 8px !important;
    }
    /* Ẩn phần info dài trong topbar cho gọn */
    .uth-topbar .uth-info { display: none !important; }
}
[data-testid="stSidebar"] button {
    font-size: 12px !important; padding: 4px 8px !important;
    height: auto !important; min-height: 32px !important;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 4px !important; }
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button {
    background: #0d3d1f !important; border-color: #2ecc71 !important;
    color: #2ecc71 !important; font-size: 11px !important;
}

/* ── Number input validation feedback ── */
[data-testid="stNumberInput"]:has(+ div div[style*="e74c3c"]) input {
    border-color: #e74c3c !important;
    box-shadow: 0 0 0 1px #e74c3c !important;
}
[data-testid="stNumberInput"]:has(+ div div[style*="2ecc71"]) input {
    border-color: #2ecc71 !important;
}
[data-testid="stNumberInput"]:has(+ div div[style*="ffc947"]) input {
    border-color: #f39c12 !important;
}

/* ── Topbar: đẩy main content xuống 52px ── */
section[data-testid="stMain"] .block-container {
    padding-top: 52px !important;
    padding-bottom: 32px !important;
    max-width: 100% !important;
}

/* ── Nav buttons phủ lên topbar ── */
div[data-testid="stHorizontalBlock"]:has(button[data-testid^="ribbonbtn"]) {
    position: fixed !important;
    top: 0 !important;
    left: var(--sidebar-edge, var(--sidebar-width, 300px)) !important;
    right: 0 !important;
    z-index: 501 !important;
    height: 44px !important;
    margin: 0 !important;
    padding: 0 !important;
    gap: 0 !important;
    background: transparent !important;
    transition: left 0.15s !important;
}
div[data-testid="stHorizontalBlock"]:has(button[data-testid^="ribbonbtn"]) > div {
    padding: 0 !important;
    margin: 0 !important;
    min-width: 0 !important;
}
div[data-testid="stHorizontalBlock"]:has(button[data-testid^="ribbonbtn"]) button {
    opacity: 0 !important;
    height: 44px !important;
    min-height: 44px !important;
    width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
    border-radius: 0 !important;
    border: none !important;
    pointer-events: auto !important;
}
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
        st.sidebar.error("🚨 Không tìm thấy mã GEMINI_API_KEY trong Secrets!")
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
    KCN  = importlib.import_module("06-AI_KetCauNhip")  # AI Kết cấu nhịp v2
    MOT  = importlib.import_module("07-AI_MoTru")       # AI Mố – Trụ v2
    MONG = importlib.import_module("08-AI_Mong")        # Móng (rule-based)
    EXP  = importlib.import_module("09-Export_CAD_IFC") # Export DXF / IFC
    PLOT = importlib.import_module("00-Drawing_Utils")
    TV   = importlib.import_module("00-Terrain_Viewer")
    LPC  = importlib.import_module("10-LopPhu_MatCau")  # Lớp phủ mặt cầu
    BVK  = importlib.import_module("11-BanVe_KetCau")   # Bản vẽ kết cấu 2D/3D
    SSP  = importlib.import_module("09-So_Sanh_PA")     # So sánh 3 phương án
    CTD  = importlib.import_module("12-ChiTiet_Dam")    # Chi tiết dầm
    importlib.reload(PLOT)
    importlib.reload(BVK)
    importlib.reload(CTD)

    # ── Section Sketcher + Beam Builder (module nạp bằng spec vì tên có số) ──
    _bb_dir  = os.path.dirname(os.path.abspath(__file__))
    _bb_espec = _iutil.spec_from_file_location(
        "BeamBuilder", os.path.join(_bb_dir, "17-BeamBuilder.py"))
    _BB_ENGINE = _iutil.module_from_spec(_bb_espec)
    import sys as _sys
    _sys.modules["BeamBuilder"] = _BB_ENGINE
    _bb_espec.loader.exec_module(_BB_ENGINE)

    _bb_uspec = _iutil.spec_from_file_location(
        "BeamBuilderUI", os.path.join(_bb_dir, "17-BeamBuilderUI.py"))
    BBUI = _iutil.module_from_spec(_bb_uspec)
    _bb_uspec.loader.exec_module(BBUI)

    # ── Pier Builder (trụ lắp ghép — Phase 1) ───────────────────────────────
    _pb_spec = _iutil.spec_from_file_location(
        "PierBuilder", os.path.join(_bb_dir, "19-PierBuilder.py"))
    PB = _iutil.module_from_spec(_pb_spec)
    _pb_spec.loader.exec_module(PB)

    # ── Thư viện cấu kiện dùng chung (mố/trụ/dầm/móng) ──────────────────────
    _cl_spec = _iutil.spec_from_file_location(
        "component_library", os.path.join(_bb_dir, "utils", "component_library.py"))
    CLIB = _iutil.module_from_spec(_cl_spec)
    _cl_spec.loader.exec_module(CLIB)

    # ── Không gian làm việc đa người dùng (thư viện + dự án theo tài khoản) ──
    _ws_spec = _iutil.spec_from_file_location(
        "workspace", os.path.join(_bb_dir, "utils", "workspace.py"))
    WS = _iutil.module_from_spec(_ws_spec)
    _ws_spec.loader.exec_module(WS)
    # Resolver đọc st.session_state (thread-local theo phiên) → mỗi user 1 thư viện
    CLIB.set_lib_dir_resolver(lambda: st.session_state.get("user_lib_dir"))

    # ── Sơ đồ cọc: đọc DXF mặt bằng + schema bố trí cọc ─────────────────────
    _pp_spec = _iutil.spec_from_file_location(
        "pile_plan", os.path.join(_bb_dir, "utils", "pile_plan.py"))
    PP = _iutil.module_from_spec(_pp_spec)
    _pp_spec.loader.exec_module(PP)

    # ── Chi tiết mặt cắt cọc (parametric) ───────────────────────────────────
    _ps_spec = _iutil.spec_from_file_location(
        "pile_section", os.path.join(_bb_dir, "utils", "pile_section.py"))
    PS = _iutil.module_from_spec(_ps_spec)
    _ps_spec.loader.exec_module(PS)

    # ── Thống kê khối lượng cấu kiện (sơ bộ) ────────────────────────────────
    _kl_spec = _iutil.spec_from_file_location(
        "khoi_luong", os.path.join(_bb_dir, "utils", "khoi_luong.py"))
    KL = _iutil.module_from_spec(_kl_spec)
    _kl_spec.loader.exec_module(KL)

except Exception as e:
    st.error(f"Lỗi kết nối Module: {e}")
    st.stop()

# ── Bối cảnh người dùng: thư viện + dự án theo tài khoản ────────────────────
# Chạy mỗi lần rerun; khởi tạo (seed thư viện, chọn dự án) khi user vừa đổi.
_cur_uname = (AUTH.current_user() or {}).get("username", "")
if _cur_uname and st.session_state.get("_ws_user") != _cur_uname:
    WS.ensure_user(_cur_uname)                      # tạo cây thư mục + seed thư viện
    st.session_state["user_lib_dir"] = WS.user_library_dir(_cur_uname)
    # Đổi user trong cùng trình duyệt → xoá state của user cũ để nạp lại
    for _k in ("design_data", "dam_beams", "dam_piers", "dam_mos", "lib_railings",
               "lib_caps", "lib_stems", "lib_footings", "bridge_library_comp"):
        st.session_state.pop(_k, None)
    _projs = WS.list_projects(_cur_uname)
    st.session_state["current_pid"] = (
        _projs[0]["id"] if _projs else WS.create_project(_cur_uname, "Dự án 1"))
    st.session_state["_ws_user"] = _cur_uname

# ── Persistence: lưu / tải thông số khai báo vào JSON ──────────────────────
_DESIGN_SAVE_FILE = pathlib.Path(__file__).parent / "design_data_saved.json"
_DESIGN_SAVE_KEYS = [
    'MNCN','MNTT','MNTC','MNTN','h_tn_tb','x_tim_clearance','goc_giao',
    'B','H','day_dam','khau_do_ngang','cap_song','loai_doi_tuong_vuot',
    'vtk','bc','loai_duong','t_ban_mm','i_max_hinh_hoc','R_hinh_hoc',
    'is_urban','geo_logic','ai_result','kcn_result','tru_result',
    'mong_result','lop_phu_result', 'cao_day_dam', 'H_tru_est',
    'lib_dam_applied', 'pile_layouts', 'railing_by_pa', 'span_layout_by_pa',
]

def _cur_user_pid():
    """(username, project_id) của phiên hiện tại — None nếu chưa sẵn sàng."""
    _u = (AUTH.current_user() or {}).get("username")
    _pid = st.session_state.get("current_pid")
    return (_u, _pid) if (_u and _pid and 'WS' in globals()) else (None, None)

def _save_design_inputs(d: dict) -> None:
    data = {k: d[k] for k in _DESIGN_SAVE_KEYS if k in d}
    # Sạch hoá về JSON-safe (numpy/np.float… → str/số) trước khi ghi
    try:
        data = json.loads(json.dumps(data, ensure_ascii=False, default=str))
    except Exception:
        pass
    _u, _pid = _cur_user_pid()
    try:
        if _u and _pid:
            WS.save_project_design(_u, _pid, data)        # → dự án của user
        else:
            _DESIGN_SAVE_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding='utf-8')
    except Exception:
        pass

def _load_design_inputs() -> dict | None:
    _u, _pid = _cur_user_pid()
    if _u and _pid:
        try:
            data = WS.load_project_design(_u, _pid)
            return data or None
        except Exception:
            return None
    # Fallback: file toàn cục cũ (khi chưa có bối cảnh user)
    if not _DESIGN_SAVE_FILE.exists():
        return None
    try:
        return json.loads(_DESIGN_SAVE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return None


# ── Sơ đồ cọc: UI khai báo theo từng vị trí (upload DXF mặt bằng + cọc xiên) ──
_COC_COLS = ["x (ngang, m)", "y (dọc, m)", "D (m)", "L (m)",
             "Xiên dọc (n:1)", "Xiên ngang (n:1)"]


def _coc_piles_to_df(piles):
    rows = [{
        _COC_COLS[0]: round(float(p["x"]), 3),  _COC_COLS[1]: round(float(p["y"]), 3),
        _COC_COLS[2]: round(float(p["D"]), 3),  _COC_COLS[3]: round(float(p["L"]), 2),
        # ix/iy (tan) → n của 'n:1' (0 = thẳng đứng)
        _COC_COLS[4]: round(PP.tan_to_slope_ratio(p.get("ix", 0.0)), 2),
        _COC_COLS[5]: round(PP.tan_to_slope_ratio(p.get("iy", 0.0)), 2),
    } for p in piles]
    return pd.DataFrame(rows, columns=_COC_COLS)


def _coc_df_to_piles(df):
    out = []
    for _, r in df.iterrows():
        if pd.isna(r[_COC_COLS[0]]) or pd.isna(r[_COC_COLS[1]]):
            continue  # bỏ hàng trống (data_editor thêm hàng NaN)
        try:
            x = float(r[_COC_COLS[0]]); y = float(r[_COC_COLS[1]])
        except (TypeError, ValueError):
            continue  # bỏ hàng lỗi
        # 'n:1' → tan (n=0/để trống = thẳng đứng)
        _nx = 0.0 if pd.isna(r[_COC_COLS[4]]) else r[_COC_COLS[4]]
        _ny = 0.0 if pd.isna(r[_COC_COLS[5]]) else r[_COC_COLS[5]]
        out.append(PP.make_pile(
            x=x, y=y, D=r[_COC_COLS[2]], L=r[_COC_COLS[3]],
            ix=PP.slope_ratio_to_tan(_nx), iy=PP.slope_ratio_to_tan(_ny)))
    return out


def _coc_lib_options():
    """Danh sách chi tiết cọc từ thư viện móng (CLIB) → [(nhãn, D_m, L_m)]."""
    try:
        mongs = CLIB.load_library().get("mong", [])
    except Exception:
        mongs = []
    opts = []
    for m in mongs:
        D = float(m.get("duong_kinh_coc", 0) or 0)
        L = float(m.get("chieu_dai_coc", 0) or 0)
        if D > 0:
            _shp = m.get("tiet_dien", "")
            _mc = (PS.describe(_shp, m.get("canh_b", 0), m.get("canh_h", 0),
                               m.get("so_canh", 0)) if _shp else f"Ø{D*1000:.0f}")
            opts.append((f"{m.get('ten','(cọc)')} — {_mc}, L={L:.0f}m", D, L))
    return opts


def _render_so_do_coc_ui(d, pos_key, pos_label):
    """Khai báo Sơ đồ cọc cho 1 vị trí: upload DXF mặt bằng → nhận TIM CỌC (dấu '+'),
    đường kính/chiều dài lấy từ THƯ VIỆN CHI TIẾT CỌC → bảng cọc (chỉnh L & độ
    xiên 'n:1') → lưu vào d['pile_layouts'][pos_key]."""
    with st.expander(f"🔵 Sơ đồ cọc — {pos_label} (upload DXF mặt bằng)", expanded=False):
        _lay  = PP.get_layout(d, pos_key)
        _ncur = len(_lay["piles"]) if _lay else 0
        st.caption(
            "Upload **DXF mặt bằng bệ cọc**. Hệ nhận **TIM CỌC** qua **dấu '+'** "
            "(hình dáng/đường kính cọc lấy từ **Thư viện chi tiết cọc**, không phụ "
            "thuộc vòng tròn trên bản vẽ). Tự **căn tâm** về trọng tâm nhóm cọc. "
            "Cột **Xiên dọc/ngang (n:1)** = độ xiên dạng n:1 (n phần đứng / 1 phần "
            "ngang; **0 = thẳng đứng**; n=10 ≈ 1 ngang trên 10 sâu)."
        )
        if _ncur:
            st.success(f"Đang dùng sơ đồ cọc đã khai: **{_ncur} cọc** cho {pos_label}.")
        else:
            st.info("Chưa khai sơ đồ cọc — bản vẽ đang rải cọc tự động (mặc định).")

        _sk = f"coc_tbl_{pos_key}"
        _c1, _c2 = st.columns([3, 2])
        with _c1:
            _up = st.file_uploader(
                f"DXF mặt bằng cọc — {pos_label}", type=["dxf"],
                key=f"coc_dxf_{pos_key}")
            # Chi tiết cọc (D, L) từ thư viện móng + giá trị từ móng đã thiết kế
            _mong = d.get("mong_result", {}) or {}
            _D_def = float(_mong.get("D_coc_mm", 1000) or 1000) / 1000.0
            _L_def = float(_mong.get("L_coc_tu", 30) or 30)
            _lib = _coc_lib_options()
            _lib_lbls = ["— nhập tay —"] + [o[0] for o in _lib]
            _lib_sel = st.selectbox(
                "Chi tiết cọc (thư viện)", _lib_lbls, index=0,
                key=f"coc_lib_{pos_key}",
                help="Đường kính & chiều dài cọc lấy từ Thư viện chi tiết cọc "
                     "(tab Thư viện cấu kiện → Móng).")
            if _lib_sel != _lib_lbls[0]:
                _o = _lib[_lib_lbls.index(_lib_sel) - 1]
                _D_def, _L_def = _o[1], _o[2]
            _cd1, _cd2 = st.columns(2)
            _pileD = _cd1.number_input("Ø cọc (m)", 0.2, 4.0, float(_D_def), 0.1,
                                       key=f"coc_D_{pos_key}")
            _pileL = _cd2.number_input("L cọc (m)", 5.0, 120.0, float(_L_def), 1.0,
                                       key=f"coc_L_{pos_key}")
        with _c2:
            _mode_lbl = st.radio(
                "Nhận diện cọc theo:", ["Tim cọc (dấu +)", "Vòng tròn"],
                index=0, key=f"coc_mode_{pos_key}",
                help="Mặc định lấy TIM CỌC từ dấu '+'. Hình dáng cọc lấy từ thư viện.")
            _source = "cross" if _mode_lbl.startswith("Tim") else "circle"
            _swap = st.checkbox("Xoay 90° (dọc cầu nằm trục X)", key=f"coc_swap_{pos_key}")
            _unit_lbl = st.selectbox(
                "Đơn vị bản vẽ", ["mm", "cm", "m", "Tự động"], index=0,
                key=f"coc_unit_{pos_key}",
                help="Bản vẽ CAD cầu thường vẽ bằng mm.")
        _unit = {"Tự động": "auto"}.get(_unit_lbl, _unit_lbl)

        if _up is not None and st.button("📥 Đọc cọc từ DXF", key=f"coc_read_{pos_key}"):
            try:
                _res = PP.parse_pile_plan_bytes(
                    _up.getvalue(), swap_xy=_swap, unit=_unit, source=_source,
                    pile_D=float(_pileD), pile_L=float(_pileL))
                for _w in _res["warnings"]:
                    st.warning(_w)
                if _res["n"]:
                    st.session_state[_sk] = _coc_piles_to_df(_res["piles"])
                    _kind = "tim cọc (dấu +)" if _res["source"] == "cross" else "vòng tròn"
                    st.success(
                        f"Đọc được **{_res['n']} cọc** từ {_kind} · "
                        f"Ø{float(_pileD):.2f}m, L={float(_pileL):.0f}m · "
                        f"đơn vị: {_res['unit']} (×{_res['scale']:g}). "
                        "Chỉnh L & độ xiên ở bảng dưới rồi bấm Lưu.")
                    st.caption("⚠️ Nếu khoảng cách cọc sai → chọn lại **Đơn vị bản vẽ** "
                               "rồi đọc lại. Cọc xiên: nhập **n** của n:1 (0 = thẳng).")
                else:
                    st.error("Không nhận được tim cọc nào — thử đổi cách nhận diện "
                             "hoặc kiểm tra layer/đơn vị.")
            except Exception as _e:
                st.error(f"Lỗi đọc DXF: {_e}")

        # Khởi tạo bảng: session (đang sửa) → layout đã lưu → rỗng
        if _sk in st.session_state:
            _df0 = st.session_state[_sk]
        elif _lay:
            _df0 = _coc_piles_to_df(_lay["piles"])
        else:
            _df0 = pd.DataFrame(columns=_COC_COLS)

        _edited = st.data_editor(
            _df0, num_rows="dynamic", use_container_width=True,
            key=f"coc_editor_{pos_key}",
            column_config={
                _COC_COLS[2]: st.column_config.NumberColumn(format="%.3f", min_value=0.1),
                _COC_COLS[3]: st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                _COC_COLS[4]: st.column_config.NumberColumn(
                    format="%.2f", min_value=0.0,
                    help="Cọc xiên theo phương DỌC cầu, dạng n:1 (n phần ĐỨNG ứng 1 "
                         "phần NGANG; n càng lớn càng đứng). 0 = thẳng đứng. VD n=10 "
                         "→ 1 ngang trên 10 sâu."),
                _COC_COLS[5]: st.column_config.NumberColumn(
                    format="%.2f", min_value=0.0,
                    help="Cọc xiên theo phương NGANG cầu, dạng n:1. 0 = thẳng đứng."),
            },
        )

        _b1, _b2, _b3 = st.columns(3)
        if _b1.button("💾 Lưu vào vị trí này", type="primary", key=f"coc_save_{pos_key}"):
            _piles = _coc_df_to_piles(_edited)
            if _piles:
                PP.set_layout(d, pos_key, _piles)
                _save_design_inputs(d)
                st.session_state[_sk] = _coc_piles_to_df(_piles)
                st.success(f"Đã lưu **{len(_piles)} cọc** cho {pos_label}.")
                st.rerun()
            else:
                st.error("Bảng cọc rỗng — chưa có gì để lưu.")
        if _b2.button("🧹 Bỏ chỉnh sửa", key=f"coc_reset_{pos_key}"):
            st.session_state.pop(_sk, None)
            st.rerun()
        if _b3.button("🗑 Xóa khai báo", key=f"coc_del_{pos_key}"):
            if isinstance(d.get("pile_layouts"), dict):
                if d["pile_layouts"].pop(pos_key, None) is not None:
                    _save_design_inputs(d)
            st.session_state.pop(_sk, None)
            st.rerun()

if 'design_data' not in st.session_state:
    _saved_design = _load_design_inputs()
    _default_design = {
        'day_dam': 0.0, 'khau_do_ngang': 0.0, 'bc': 12.0, 'loai_duong': "Do thi",
        'B': 20.0, 'H': 4.75, 'loai_doi_tuong_vuot': "Vượt sông", 'goc_giao': 90.0,
        'MNCN': 3.5, 'MNTT': 2.0, 'MNTC': 1.5, 'MNTN': 0.5, 'h_tn_tb': 0.0,
        'x_tim_clearance': 0.0,
        'cap_song': 'VI', 'vtk': 60, 'i_max_hinh_hoc': 4.0, 'R_hinh_hoc': 5000,
        't_ban_mm': 200,
        'is_urban': 0,
        'geo_logic': {'L_cau': 120.0, 'x_mo_trai': -60.0, 'x_mo_phai': 60.0, 'y_mo': 1.5, 'h_tn_tb': 2.15, 'y_base_goc': 2.0},
        'ai_result': {'loai_dam': 'Super-T', 'tong_so_nhip': 3, 'chieu_dai': 40.0, 'chieu_cao': 1.75, 'so_luong_dam': 5, 'khoang_cach_dam': 2.2, 'ghi_chu': 'Phương án tối ưu từ AI.'},
        'kcn_result': None,
        'tru_result': None,
        'mong_result': None,
        'lop_phu_result': None,
    }
    if _saved_design:
        _default_design.update(_saved_design)
    st.session_state.design_data = _default_design

if 'chatbot_context' not in st.session_state:
    st.session_state.chatbot_context = "Chưa tiến hành chạy dự báo tính toán."

if 'alternatives' not in st.session_state:
    st.session_state.alternatives = None

if 'current_tab' not in st.session_state:
    st.session_state.current_tab = "THUYẾT MINH"

if 'wizard_draft' not in st.session_state:
    st.session_state.wizard_draft = {}

if 'open_dialog' not in st.session_state:
    st.session_state.open_dialog = None

if 'dialog_origin' not in st.session_state:
    st.session_state.dialog_origin = "sidebar"

if 'field_touched' not in st.session_state:
    st.session_state.field_touched = set()

if 'field_errors' not in st.session_state:
    st.session_state.field_errors = {}

if 'field_warnings' not in st.session_state:
    st.session_state.field_warnings = {}

if 'panel_widths' not in st.session_state:
    st.session_state.panel_widths = {'left': 300, 'right': 220}

# ── Metadata 8 bước pipeline AI ──────────────────────────────────────────────
PIPELINE_STEPS = [
    {"id": "TK",   "label": "Tĩnh không ỐTN",    "desc": "Tra cứu tĩnh không thông thuyền theo TCVN 8818:2022",         "icon": "🌊", "weight": 5},
    {"id": "YTHH", "label": "Yếu tố hình học",     "desc": "Tính MCN, chiều rộng cầu, độ dốc dọc ngang",                  "icon": "📐", "weight": 10},
    {"id": "KCN",  "label": "AI kết cấu nhịp",     "desc": "Dự báo loại dầm, số nhịp, chiều dài, chiều cao",              "icon": "🤖", "weight": 20},
    {"id": "MOT",  "label": "AI mố – trụ",         "desc": "Dự báo loại trụ, kích thước thân trụ, loại mố",               "icon": "🏗️", "weight": 20},
    {"id": "MONG", "label": "AI móng cầu",          "desc": "Dự báo loại móng, đường kính cọc, chiều sâu",                 "icon": "⚙️", "weight": 20},
    {"id": "LPC",  "label": "Lớp phủ mặt cầu",     "desc": "Tư vấn cấu tạo lớp phủ theo TCVN 8819:2011",                 "icon": "🛣️", "weight": 5},
    {"id": "BVK",  "label": "Bản vẽ kết cấu",      "desc": "Sinh bản vẽ trắc dọc, mặt cắt ngang, mố trụ",                "icon": "📋", "weight": 10},
    {"id": "SSP",  "label": "So sánh phương án",   "desc": "Sinh và đánh giá 3 phương án loại dầm",                       "icon": "📊", "weight": 10},
]
assert sum(s["weight"] for s in PIPELINE_STEPS) == 100


class PipelineTracker:
    """Quản lý trạng thái và hiển thị tiến trình pipeline AI."""

    STATUS_WAIT    = "wait"
    STATUS_RUNNING = "running"
    STATUS_DONE    = "done"
    STATUS_ERROR   = "error"
    STATUS_SKIP    = "skip"

    _COLORS = {
        "wait":    ("#333355", "#888899", "○"),
        "running": ("#1a2d45", "#4fc3f7", "⟳"),
        "done":    ("#0d3d1f", "#2ecc71", "✓"),
        "error":   ("#2d0a0a", "#e74c3c", "✗"),
        "skip":    ("#1a1a1a", "#555555", "—"),
    }

    def __init__(self, steps: list):
        self.steps    = steps
        self.statuses = {s["id"]: self.STATUS_WAIT for s in steps}
        self.messages = {s["id"]: "" for s in steps}
        self.timings  = {s["id"]: 0.0 for s in steps}
        self._starts  = {}
        self._pct     = 0.0
        self._ph_bar  = None
        self._ph_label = None
        self._ph_grid  = None

    def setup(self):
        st.markdown(
            "<div style='background:#141420;border:1px solid #333366;"
            "border-radius:12px;padding:16px;margin:8px 0'>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='font-size:13px;font-weight:600;color:#4fc3f7;"
            "margin:0 0 8px'>🤖 Pipeline AI đang chạy...</p>",
            unsafe_allow_html=True,
        )
        self._ph_label = st.empty()
        self._ph_bar   = st.empty()
        self._ph_grid  = st.empty()
        st.markdown("</div>", unsafe_allow_html=True)
        self._render()

    def start(self, step_id: str):
        self.statuses[step_id] = self.STATUS_RUNNING
        self._starts[step_id]  = time.time()
        self._render()

    def done(self, step_id: str, msg: str = ""):
        elapsed = time.time() - self._starts.get(step_id, time.time())
        self.statuses[step_id] = self.STATUS_DONE
        self.messages[step_id] = msg
        self.timings[step_id]  = elapsed
        step = next(s for s in self.steps if s["id"] == step_id)
        self._pct = min(100.0, self._pct + step["weight"])
        self._render()

    def error(self, step_id: str, err_msg: str):
        elapsed = time.time() - self._starts.get(step_id, time.time())
        self.statuses[step_id] = self.STATUS_ERROR
        self.messages[step_id] = err_msg
        self.timings[step_id]  = elapsed
        self._render()

    def skip(self, step_id: str):
        self.statuses[step_id] = self.STATUS_SKIP
        self.messages[step_id] = "Bề qua do bước trước thất bại"
        self._render()

    def finish(self, success: bool):
        self._pct = 100.0 if success else self._pct
        self._render()

    def render_timing_summary(self):
        total = sum(self.timings.values())
        rows  = []
        for s in self.steps:
            sid = s["id"]
            t   = self.timings[sid]
            if t > 0:
                pct_time = t / total * 100 if total > 0 else 0
                rows.append(
                    f"<tr>"
                    f"<td style='padding:3px 8px;color:#aaa'>{s['icon']} {s['label']}</td>"
                    f"<td style='padding:3px 8px;color:#4fc3f7;text-align:right'>{t:.2f}s</td>"
                    f"<td style='padding:3px 8px;color:#888;text-align:right'>{pct_time:.0f}%</td>"
                    f"</tr>"
                )
        if rows:
            st.markdown(
                f"<details style='margin-top:8px'>"
                f"<summary style='font-size:11px;color:#666;cursor:pointer'>⏱ Thời gian chi tiết</summary>"
                f"<table style='width:100%;font-size:11px;border-collapse:collapse;margin-top:6px'>"
                f"{''.join(rows)}"
                f"<tr style='border-top:1px solid #333'>"
                f"<td style='padding:4px 8px;color:#fff;font-weight:600'>Tổng cộng</td>"
                f"<td style='padding:4px 8px;color:#2ecc71;text-align:right;font-weight:600'>{total:.2f}s</td>"
                f"<td></td></tr>"
                f"</table></details>",
                unsafe_allow_html=True,
            )

    def _render(self):
        running_id = next(
            (sid for sid, st_ in self.statuses.items() if st_ == self.STATUS_RUNNING), None
        )
        if running_id:
            meta = next(s for s in self.steps if s["id"] == running_id)
            self._ph_label.markdown(
                f"<p style='font-size:12px;color:#aaa;margin:0 0 4px'>"
                f"{meta['icon']} <b style='color:#fff'>{meta['label']}</b>"
                f" — {meta['desc']}</p>",
                unsafe_allow_html=True,
            )
        elif self._pct >= 100:
            self._ph_label.markdown(
                "<p style='font-size:12px;color:#2ecc71;margin:0 0 4px'>"
                "✅ Hoàn tất tất cả các bước</p>",
                unsafe_allow_html=True,
            )

        pct = int(self._pct)
        self._ph_bar.markdown(
            f"<div style='background:#1e1e2e;border-radius:6px;height:10px;"
            f"overflow:hidden;margin-bottom:12px'>"
            f"<div style='width:{pct}%;height:100%;"
            f"background:linear-gradient(90deg,#007acc,#2ecc71);"
            f"border-radius:6px;transition:width 0.3s'></div></div>"
            f"<p style='font-size:11px;color:#888;margin:-8px 0 8px;"
            f"text-align:right'>{pct}%</p>",
            unsafe_allow_html=True,
        )

        rows_html = ""
        for s in self.steps:
            sid    = s["id"]
            status = self.statuses[sid]
            bg, color, badge = self._COLORS[status]
            msg    = self.messages[sid]
            timing = self.timings[sid]

            timing_str = (
                f"<span style='color:#555;font-size:10px'> {timing:.1f}s</span>"
                if timing > 0 else ""
            )
            msg_html = ""
            if status == self.STATUS_ERROR and msg:
                msg_html = (
                    f"<div style='font-size:10px;color:#ff8a80;margin-top:2px;"
                    f"padding-left:4px;border-left:2px solid #e74c3c'>{msg}</div>"
                )
            elif status == self.STATUS_DONE and msg:
                msg_html = (
                    f"<div style='font-size:10px;color:#555;margin-top:2px'>{msg}</div>"
                )

            rows_html += (
                f"<div style='display:flex;align-items:flex-start;gap:8px;"
                f"padding:6px 10px;background:{bg};border-radius:6px;margin-bottom:4px'>"
                f"<span style='font-size:13px;min-width:20px;color:{color};"
                f"font-weight:700;line-height:1.4'>{badge}</span>"
                f"<div style='flex:1'>"
                f"<span style='font-size:12px;color:#ddd'>{s['icon']} {s['label']}</span>"
                f"{timing_str}{msg_html}"
                f"</div></div>"
            )

        self._ph_grid.markdown(
            f"<div style='margin-top:4px'>{rows_html}</div>",
            unsafe_allow_html=True,
        )


# ── Design System ────────────────────────────────────────────────────────────
import importlib.util as _dsutil
_dsspec = _dsutil.spec_from_file_location(
    "ds00",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "00-DesignSystem.py")
)
DS = _dsutil.module_from_spec(_dsspec)
_dsspec.loader.exec_module(DS)
st.markdown(DS.GLOBAL_CSS, unsafe_allow_html=True)

# ── Import module validation ──────────────────────────────────────────────────
import importlib.util as _vutil
_vspec = _vutil.spec_from_file_location(
    "val00",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "00-Validation.py")
)
VAL = _vutil.module_from_spec(_vspec)
_vspec.loader.exec_module(VAL)


def _field_with_feedback(
    label: str,
    value: float,
    key: str,
    check_fn,
    check_args: tuple,
    fmt: str = "%.3f",
    min_val: float = None,
    max_val: float = None,
    step: float = 0.001,
    help_txt: str = "",
    unit: str = "m",
) -> float:
    """number_input bọc thêm icon trạng thái và feedback dưới ô."""
    touched  = key in st.session_state.field_touched
    prev_err = st.session_state.field_errors.get(key)
    label_display = (
        f"🔴 {label}" if (touched and prev_err)
        else f"✅ {label}" if touched
        else label
    )

    kwargs = dict(
        label=label_display,
        value=value,
        format=fmt,
        step=step,
        key=key,
        help=help_txt,
    )
    if min_val is not None:
        kwargs['min_value'] = min_val
    if max_val is not None:
        kwargs['max_value'] = max_val

    new_val = st.number_input(**kwargs)

    if new_val != value:
        st.session_state.field_touched.add(key)

    if key in st.session_state.field_touched:
        result = check_fn(new_val, *check_args)

        if result.error:
            st.session_state.field_errors[key] = result.error
            st.markdown(
                f"<div style='margin-top:-12px;margin-bottom:8px;"
                f"padding:6px 10px;background:#2d0a0a;"
                f"border-left:3px solid #e74c3c;"
                f"border-radius:0 6px 6px 0;font-size:12px;"
                f"color:#ff8a80'>❌ {result.error}</div>",
                unsafe_allow_html=True,
            )
            if result.hint:
                st.markdown(
                    f"<div style='margin-top:-4px;margin-bottom:8px;"
                    f"padding:4px 10px;background:#1a2000;"
                    f"border-left:3px solid #f39c12;"
                    f"border-radius:0 6px 6px 0;font-size:11px;"
                    f"color:#ffc947'>💡 {result.hint}</div>",
                    unsafe_allow_html=True,
                )
        elif result.warning:
            st.session_state.field_errors.pop(key, None)
            st.session_state.field_warnings[key] = result.warning
            st.markdown(
                f"<div style='margin-top:-12px;margin-bottom:8px;"
                f"padding:6px 10px;background:#1f1600;"
                f"border-left:3px solid #f39c12;"
                f"border-radius:0 6px 6px 0;font-size:12px;"
                f"color:#ffc947'>⚠️ {result.warning}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.session_state.field_errors.pop(key, None)
            st.session_state.field_warnings.pop(key, None)
            st.markdown(
                f"<div style='margin-top:-12px;margin-bottom:8px;"
                f"padding:4px 10px;font-size:11px;"
                f"color:#2ecc71'>✅ Hợp lệ</div>",
                unsafe_allow_html=True,
            )

    return new_val


def _render_step_status_banner(errors: dict, warnings: dict,
                                n_fields_total: int):
    """Banner tổng hợp trạng thái bước hiện tại — hiện ở đầu form."""
    n_err  = len(errors)
    n_warn = len(warnings)
    n_ok   = n_fields_total - n_err - n_warn

    if n_err == 0 and n_warn == 0 and n_ok == 0:
        return

    err_pct  = n_err  / n_fields_total * 100
    warn_pct = n_warn / n_fields_total * 100
    ok_pct   = n_ok   / n_fields_total * 100

    bar_html = (
        f"<div style='display:flex;height:6px;border-radius:3px;"
        f"overflow:hidden;margin-bottom:8px'>"
        f"<div style='width:{ok_pct:.0f}%;background:#2ecc71'></div>"
        f"<div style='width:{warn_pct:.0f}%;background:#f39c12'></div>"
        f"<div style='width:{err_pct:.0f}%;background:#e74c3c'></div>"
        f"</div>"
    )

    if n_err > 0:
        msg_color = "#ff8a80"
        msg_bg    = "#2d0a0a"
        msg_icon  = "❌"
        msg_text  = (f"{n_err} lỗi cần sửa trước khi tiếp tục"
                     + (f" · {n_warn} cảnh báo" if n_warn else ""))
    elif n_warn > 0:
        msg_color = "#ffc947"
        msg_bg    = "#1f1600"
        msg_icon  = "⚠️"
        msg_text  = f"{n_warn} cảnh báo — có thể tiếp tục nhưng nên kiểm tra lại"
    else:
        msg_color = "#2ecc71"
        msg_bg    = "#0d1f0d"
        msg_icon  = "✅"
        msg_text  = "Tất cả trường hợp lệ — có thể tiếp tục"

    st.markdown(
        f"{bar_html}"
        f"<div style='padding:8px 12px;background:{msg_bg};"
        f"border-radius:6px;font-size:12px;color:{msg_color};"
        f"margin-bottom:12px'>{msg_icon} {msg_text}</div>",
        unsafe_allow_html=True,
    )



# =========================================================================
# ↔ RESIZABLE PANELS — inject CSS + JS drag handles
# =========================================================================
def _inject_resizable_panels() -> None:
    """Kéo CẠNH PHẢI của sidebar trái để chỉnh độ rộng.
    Chỉ thay đổi WIDTH của sidebar — KHÔNG đụng vùng nội dung chính (Streamlit
    tự dồn theo flex). JS chạy trong components.html, thao tác
    window.parent.document (st.markdown loại bỏ <script>)."""
    st.markdown(
        """
<style>
#cau-sb-drag {
    position: fixed; top: 0; bottom: 0; width: 7px; z-index: 99990;
    cursor: col-resize; background: transparent; transition: background .15s;
}
#cau-sb-drag:hover, #cau-sb-drag.dragging { background: rgba(0,122,204,0.55); }
body.cau-resizing, body.cau-resizing * {
    cursor: col-resize !important; user-select: none !important;
}
@media (max-width: 768px) { #cau-sb-drag { display: none !important; } }
</style>
<div id="cau-sb-drag" title="Kéo để chỉnh rộng sidebar · nháy đúp để đặt lại"></div>
""",
        unsafe_allow_html=True,
    )
    st.components.v1.html(
        """
<script>
(function(){
  var D = window.parent.document, W = window.parent;
  var MINW = 180, MAXW = 560, KEY = 'cau_ai_left_w';
  function sb(){ return D.querySelector('[data-testid="stSidebar"]'); }
  function handle(){ return D.getElementById('cau-sb-drag'); }
  var curW = parseInt(W.localStorage.getItem(KEY) || '') || 0;
  var _lastEdge = -1, _lastCollapsed = null;  // tránh ghi lại DOM gây vòng lặp observer

  // Đồng bộ MÉP PHẢI THỰC của sidebar → biến --sidebar-edge để topbar/ribbon bám
  // theo, đồng thời nhận biết trạng thái THU GỌN (collapse) để gắn class lên <html>.
  // Chỉ ghi DOM khi giá trị THỰC SỰ đổi — nếu không MutationObserver sẽ tự kích lại.
  function sync(){
    var s = sb(), h = handle();
    if (!s) return;
    var r = s.getBoundingClientRect();
    // Nhận biết THU GỌN: ưu tiên cờ aria-expanded của Streamlit (đáng tin nhất,
    // không bị CSS khóa width che mất), kèm fallback theo kích thước thực tế.
    var aria = s.getAttribute('aria-expanded');
    var cc = D.querySelector('[data-testid="stSidebarCollapsedControl"]');
    var hasCollapsedCtrl = !!(cc && cc.getBoundingClientRect().width > 0);  // chỉ tính khi HIỆN
    var collapsed = (aria === 'false') || hasCollapsedCtrl
                    || (r.width < 60) || (r.right < 60);
    var edge = collapsed ? 0 : Math.max(0, r.right);
    if (collapsed !== _lastCollapsed){
      _lastCollapsed = collapsed;
      D.documentElement.classList.toggle('cau-sb-collapsed', collapsed);
      if (h) h.style.display = collapsed ? 'none' : 'block';
    }
    if (Math.abs(edge - _lastEdge) > 0.5){
      _lastEdge = edge;
      D.documentElement.style.setProperty('--sidebar-edge', edge + 'px');
      if (h && !collapsed) h.style.left = (edge - 3) + 'px';
    }
  }
  function applyW(w){
    // Khóa width khi sidebar đang mở (xem global CSS), rồi đồng bộ lại edge.
    D.documentElement.style.setProperty('--sidebar-width', w + 'px');
    sync();
  }
  function refresh(){ if (curW >= MINW) applyW(curW); else sync(); }

  function setup(){
    var h = handle(), s = sb();
    if (!h || !s) return false;
    refresh();
    if (h.__bound) return true;
    h.__bound = true;
    var dragging = false, startX = 0, startW = 0;
    h.addEventListener('mousedown', function(e){
      e.preventDefault(); dragging = true; startX = e.clientX;
      startW = sb().getBoundingClientRect().width;
      h.classList.add('dragging'); D.body.classList.add('cau-resizing');
    });
    D.addEventListener('mousemove', function(e){
      if (!dragging) return;
      var w = Math.min(MAXW, Math.max(MINW, startW + (e.clientX - startX)));
      curW = w; applyW(w);
    });
    D.addEventListener('mouseup', function(){
      if (!dragging) return;
      dragging = false; h.classList.remove('dragging');
      D.body.classList.remove('cau-resizing');
      W.localStorage.setItem(KEY, curW);
    });
    h.addEventListener('dblclick', function(){
      curW = 0; W.localStorage.removeItem(KEY);
      D.documentElement.style.removeProperty('--sidebar-width');  // về 300px mặc định
      sync();
    });
    return true;
  }

  var tries = 0;
  (function tryInit(){
    if (setup()){
      // Theo dõi cả thay đổi cấu trúc (childList) lẫn style/aria của sidebar
      // (Streamlit đổi transform/width khi thu gọn) để dồn layout kịp thời.
      // Gom nhiều mutation vào 1 nhịp rAF để tránh đo layout liên tục.
      var _raf = 0;
      var mo = new W.MutationObserver(function(){
        if (_raf) return;
        _raf = W.requestAnimationFrame(function(){ _raf = 0; refresh(); });
      });
      mo.observe(D.body, {childList: true, subtree: true, attributes: true,
                          attributeFilter: ['style', 'class', 'aria-expanded']});
      W.addEventListener('resize', sync);
      // Đồng bộ thêm vài nhịp để bắt kịp animation thu gọn/mở của Streamlit.
      [120, 250, 450].forEach(function(t){ setTimeout(sync, t); });
    } else if (tries < 40){ tries++; setTimeout(tryInit, 200); }
  })();
})();
</script>
""",
        height=0, scrolling=False,
    )


# Gọi ngay sau định nghĩa — trước khi sidebar và columns được render
_inject_resizable_panels()


# =========================================================================
# ⚙️ KHAI BÁO SỐ LIỆU — 3 DIALOGS ĐỘC LẬP
# =========================================================================

@st.dialog("🌊 BƯỚC 1 / 3 — Thủy văn & Vị trí cầu", width="large")
def dialog_step1():
    draft = st.session_state.wizard_draft

    st.markdown(
        DS.section_header(
            title = "Thông số thủy văn & vị trí cầu",
            icon  = "🌊",
            sub   = "Phạm vi đề tài: Cầu vượt sông/kênh cấp IV–VI (TCVN 8818:2022)",
        ),
        unsafe_allow_html=True,
    )

    _touched = st.session_state.field_touched & {
        'd1_h1', 'd1_h5', 'd1_h10', 'd1_h98', 'd1_xtim', 'd1_goc', 'd1_tban'
    }
    if _touched:
        _render_step_status_banner(
            errors={k: v for k, v in st.session_state.field_errors.items()
                    if k.startswith('d1_')},
            warnings={k: v for k, v in st.session_state.field_warnings.items()
                      if k.startswith('d1_')},
            n_fields_total=7,
        )

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**📍 Vị trí & phân loại**")
        mien = st.selectbox(
            "Khu vực miền:",
            ["1", "2"],
            index=0 if draft.get('mien', '2') == '1' else 1,
            format_func=lambda x: "Miền Bắc" if x == "1" else "Miền Nam",
            key="d1_mien",
        )
        cap_s = st.selectbox(
            "Cấp sông ỐTN:",
            ["4", "5", "6", "3", "2", "1"],
            index=["4","5","6","3","2","1"].index(str(draft.get('cap_s', '4'))),
            format_func=lambda x: f"Cấp {['I','II','III','IV','V','VI'][int(x)-1]}",
            key="d1_caps",
        )
        loai_h = st.selectbox(
            "Loại hình thủy văn:",
            ["1", "2"],
            index=0 if draft.get('loai_h', '2') == '1' else 1,
            format_func=lambda x: "Kênh đào" if x == "1" else "Sông tự nhiên",
            key="d1_loaih",
        )
        goc_giao = _field_with_feedback(
            label     = "Góc giao chéo (độ)",
            value     = float(draft.get('goc_giao', st.session_state.design_data.get('goc_giao', 90.0))),
            key       = "d1_goc",
            check_fn  = VAL.check_goc_giao,
            check_args= (),
            fmt       = "%.1f",
            min_val   = 30.0,
            max_val   = 90.0,
            step      = 1.0,
            help_txt  = "90° = vuông góc. Cầu xiên < 75° cần kiểm tra thêm.",
        )

    with col_b:
        st.markdown("**📏 Cao độ thủy văn (m)**")
        st.caption("Thứ tự bắt buộc: MNCN > MNTT > MNTC > MNTN")

        _lt_min = _lt_max = None
        if 'df_tim_line' in st.session_state and st.session_state.df_tim_line is not None:
            _tl = st.session_state.df_tim_line
            _lt_col = next((c for c in _tl.columns if 'ý trình' in c or c.lower() == 'ly_trinh'), None)
            if _lt_col:
                _lt_min = float(_tl[_lt_col].min())
                _lt_max = float(_tl[_lt_col].max())
                st.info(f"🗺️ Địa hình: Lý trình {_lt_min:.1f} → {_lt_max:.1f}m  |  Gợi ý tim cầu ≈ **{(_lt_min+_lt_max)/2:.1f}m**")

        x_tim_clearance = _field_with_feedback(
            label     = "📍 Lý trình tim tĩnh không (m)",
            value     = float(draft.get('x_tim_clearance', st.session_state.design_data.get('x_tim_clearance', 0.0))),
            key       = "d1_xtim",
            check_fn  = VAL.check_x_tim,
            check_args= (_lt_min, _lt_max),
            fmt       = "%.2f",
            step      = 1.0,
            help_txt  = "Lý trình điểm tim cầu vượt qua sông/kênh.",
        )

        _d = st.session_state.design_data
        h1 = _field_with_feedback(
            label     = "MNCN — Mực nước cao nhất H1% (m)",
            value     = float(draft.get('h1', _d.get('MNCN', 3.50))),
            key       = "d1_h1",
            check_fn  = VAL.check_h1,
            check_args= (float(draft.get('h5', _d.get('MNTT', 2.00))),),
            help_txt  = "Mực nước cao nhất tần suất 1% — dùng tính an toàn va tàu",
        )
        h5 = _field_with_feedback(
            label     = "MNTT — Mực nước thông thuyền H5% (m)",
            value     = float(draft.get('h5', _d.get('MNTT', 2.00))),
            key       = "d1_h5",
            check_fn  = VAL.check_h5,
            check_args= (h1, float(draft.get('h10', _d.get('MNTC', 1.50)))),
            help_txt  = "Mực nước thông thuyền — dùng tính chiều cao tĩnh không H",
        )
        h10 = _field_with_feedback(
            label     = "MNTC — Mực nước thi công H10% (m)",
            value     = float(draft.get('h10', _d.get('MNTC', 1.50))),
            key       = "d1_h10",
            check_fn  = VAL.check_h10,
            check_args= (h5, float(draft.get('h98', _d.get('MNTN', 0.50)))),
            help_txt  = "Mực nước thi công tần suất 10%",
        )
        h98 = _field_with_feedback(
            label     = "MNTN — Mực nước thấp nhất H98% (m)",
            value     = float(draft.get('h98', _d.get('MNTN', 0.50))),
            key       = "d1_h98",
            check_fn  = VAL.check_h98,
            check_args= (h10,),
            help_txt  = "Mực nước kiệt tần suất 98% — dùng ước tính chiều cao trụ",
        )

        st.markdown("**🛣️ Bản mặt cầu**")
        t_ban_mm = _field_with_feedback(
            label     = "Chiều dày bản mặt cầu (mm)",
            value     = float(draft.get('t_ban_mm', _d.get('t_ban_mm', 200))),
            key       = "d1_tban",
            check_fn  = VAL.check_t_ban,
            check_args= (),
            fmt       = "%.0f",
            min_val   = 150.0,
            max_val   = 400.0,
            step      = 5.0,
            help_txt  = "Tối thiểu 175mm — TCVN 11823-2017 Điều 9.7.1.1",
            unit      = "mm",
        )

    _has_hard_errors = any(
        k in st.session_state.field_errors
        for k in ['d1_h1', 'd1_h5', 'd1_h10', 'd1_h98', 'd1_xtim', 'd1_goc', 'd1_tban']
    )

    st.markdown("<br>", unsafe_allow_html=True)
    _, btn_col = st.columns([3, 1])
    with btn_col:
        if st.button(
            "Bước 2 ▶",
            use_container_width=True,
            type="primary",
            disabled=_has_hard_errors,
            key="d1_next",
            help="Sửa hết lỗi đỏ trước khi sang bước tiếp theo" if _has_hard_errors else "",
        ):
            st.session_state.wizard_draft.update({
                'mien': mien, 'cap_s': cap_s, 'loai_h': loai_h,
                'goc_giao': goc_giao, 'x_tim_clearance': x_tim_clearance,
                'h1': h1, 'h5': h5, 'h10': h10, 'h98': h98,
                't_ban_mm': int(t_ban_mm),
            })
            st.session_state.open_dialog = "step2"
            st.rerun()


@st.dialog("🛣️ BƯỚC 2 / 3 — Tiêu chuẩn hình học tuyến", width="large")
def dialog_step2():
    draft = st.session_state.wizard_draft

    st.markdown(
        DS.section_header(
            title = "Tiêu chuẩn hình học tuyến đường",
            icon  = "🛣️",
            sub   = "Chọn loại đường, vận tốc thiết kế và nhập bề rộng cầu",
        ),
        unsafe_allow_html=True,
    )

    with st.expander("🌊 Tóm tắt Bước 1 — Thủy văn", expanded=False):
        _s1a, _s1b, _s1c = st.columns(3)
        _s1a.metric("Khu vực", "Miền Bắc" if draft.get('mien') == '1' else "Miền Nam")
        _s1b.metric("Cấp sông", f"Cấp {['I','II','III','IV','V','VI'][int(draft.get('cap_s','4'))-1]}")
        _s1c.metric("Loại hình", "Kênh đào" if draft.get('loai_h') == '1' else "Sông tự nhiên")
        st.caption(
            f"MNCN={draft.get('h1',0):.3f}m | MNTT={draft.get('h5',0):.3f}m | "
            f"MNTC={draft.get('h10',0):.3f}m | MNTN={draft.get('h98',0):.3f}m | "
            f"Tim cầu={draft.get('x_tim_clearance',0):.2f}m | Góc={draft.get('goc_giao',90):.0f}°"
        )

    v_hinhhoc     = draft.get('v_hinhhoc', 60)
    d_hinhhoc     = draft.get('d_hinhhoc', '1')
    input_tra_cuu = draft.get('input_tra_cuu', 60)
    mcn_oto_override = {}
    r_final_calc  = draft.get('r_final_calc', 5000)
    i_final_calc  = draft.get('i_final_calc', 4.0)
    res_geo       = {}

    _lh_opts = ["Cao tốc", "O to", "Do thi"]
    l_hinhhoc = st.selectbox(
        "Loại đường thiết kế:",
        _lh_opts,
        index=_lh_opts.index(draft.get('l_hinhhoc', 'Do thi')),
    )

    if l_hinhhoc == "Cao tốc":
        d_hinhhoc = st.radio("Địa hình:", options=["1", "2"], format_func=lambda x: "Đồng bằng" if x == "1" else "Khó khăn")
        v_list = [120, 100] if d_hinhhoc == "1" else [80, 60]
        v_hinhhoc = st.selectbox("Vận tốc thiết kế Vtk (km/h):", options=v_list)
        input_tra_cuu = v_hinhhoc

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
                loai_dpc_oto = "be_tong_duc_san"

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
    else:  # Do thi
        loai_dt = st.selectbox("Phân loại đường đô thị:", ["Trục chính đô thị", "Đường chính đô thị", "Đường khu vực", "Đường nội bộ"])
        cap_dt = st.selectbox("Cấp kỹ thuật kỹ sư:", ["Đặc biệt", "Cấp I", "Cấp II"] if loai_dt == "Trục chính đô thị" else ["Cấp I", "Cấp II"])
        list_vtk = YTHH.get_vtk_goi_y_dothi(loai_dt, cap_dt)
        v_hinhhoc = st.radio("Vận tốc thiết kế Vtk:", options=list_vtk, horizontal=True)
        d_hinhhoc = st.radio("Địa hình đô thị:", ["1", "2"], format_func=lambda x: "Bằng phẳng" if x == "1" else "Khó khăn")
        input_tra_cuu = v_hinhhoc

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
                key="d2_loai_dt_mcn",
            )
        with _col_dtB:
            dieu_kien_xd = st.radio(
                "Điều kiện xây dựng (ảnh hưởng Bảng 14, 15):",
                options=["I", "II", "III"],
                horizontal=True,
                key="d2_dieu_kien_xd",
                help="I: Thuận lợi | II: Bình thường | III: Khó khăn",
            )
        tra_dt = YTHH.tra_cuu_mcn_do_thi(v_hinhhoc, loai_dt_mcn, dieu_kien_xd)

        if tra_dt.get("status") == "success":
            st.caption(
                f"ℹ️ **Bảng 10** — {tra_dt['mo_ta']} | VTK {v_hinhhoc} km/h | "
                f"Làn tối thiểu: **{tra_dt['w_lan_min']:.2f}m** | "
                f"Số làn: **{tra_dt['so_lan_toi_thieu']}** (mong muốn {tra_dt['so_lan_mong_muon']})"
            )
            _dat_at_cap = (tra_dt['w_dat_at_loaiI'] if dieu_kien_xd == "I"
                           else tra_dt['w_dat_at_loaiII_III'])
            st.caption(
                f"ℹ️ **Bảng 13** — Lề: **{tra_dt['w_le_min']:.2f}÷{tra_dt['w_le_max']:.2f}m** | "
                + (f"Dải AT (đk {dieu_kien_xd}): **{_dat_at_cap:.2f}m**"
                   if _dat_at_cap else "Dải AT: không bắt buộc ở VTK này")
            )
            if tra_dt["co_dpc"] and tra_dt["dpc_min"] is not None:
                st.caption(
                    f"ℹ️ **Bảng 14** — Dải phân cách tối thiểu (đk {dieu_kien_xd}): "
                    f"**{tra_dt['dpc_min']:.2f}m** (mong muốn {tra_dt['dpc_mong_muon']:.2f}m)"
                )
            elif tra_dt.get("dpc_note"):
                st.caption(f"ℹ️ **Bảng 14** — {tra_dt['dpc_note']}")
            if tra_dt["he_min"] is not None:
                st.caption(
                    f"ℹ️ **Bảng 15** — Hè đường tối thiểu (đk {dieu_kien_xd}): "
                    f"**{tra_dt['he_min']:.1f}m**"
                )

            st.markdown("**Phần xe chạy (Bảng 10):**")
            _c1, _c2 = st.columns(2)
            with _c1:
                n_lan_dt = st.number_input(
                    "Số làn xe:",
                    min_value=tra_dt["so_lan_toi_thieu"], value=tra_dt["so_lan_toi_thieu"],
                    step=2, key="d2_n_lan_dt",
                )
                w_lan_dt = st.number_input(
                    "Chiều rộng 1 làn xe (m):",
                    min_value=tra_dt["w_lan_min"], value=tra_dt["w_lan_min"],
                    step=0.25, format="%.2f", key="d2_w_lan_dt",
                )
            with _c2:
                w_le_dt = st.number_input(
                    f"Lề đường (m) — tối thiểu {tra_dt['w_le_min']:.2f}m:",
                    min_value=tra_dt["w_le_min"],
                    max_value=max(tra_dt["w_le_max"], tra_dt["w_le_min"] + 3.0),
                    value=tra_dt["w_le_min"],
                    step=0.25, format="%.2f", key="d2_w_le_dt",
                )

            st.markdown("**Dải phân cách giữa (Bảng 14):**")
            if tra_dt["co_dpc"] and tra_dt["dpc_min"] is not None:
                w_dpc_dt = st.number_input(
                    f"Chiều rộng DPC (m) — tối thiểu {tra_dt['dpc_min']:.2f}m "
                    f"(mong muốn {tra_dt['dpc_mong_muon']:.2f}m):",
                    min_value=tra_dt["dpc_min"],
                    value=tra_dt["dpc_min"],
                    step=0.50, format="%.2f", key="d2_w_dpc_dt",
                )
            elif tra_dt.get("dpc_note"):
                st.info(f"ℹ️ {tra_dt['dpc_note']}")
                w_dpc_dt = 0.0
            else:
                w_dpc_dt = st.number_input(
                    "Chiều rộng DPC (m, 0 nếu không có):",
                    min_value=0.0, value=0.0, step=0.5, format="%.2f", key="d2_w_dpc_dt",
                )

            st.markdown("**Hè đường / Dải bên đường (Bảng 15):**")
            _he_min_val = tra_dt["he_min"] if tra_dt["he_min"] is not None else 0.0
            if _he_min_val > 0:
                w_he_dt = st.number_input(
                    f"Chiều rộng hè đường (m) — tối thiểu {_he_min_val:.1f}m:",
                    min_value=_he_min_val, value=_he_min_val,
                    step=0.5, format="%.1f", key="d2_w_he_dt",
                )
            else:
                st.info("ℹ️ Loại đường này không quy định hè đường bắt buộc.")
                w_he_dt = st.number_input(
                    "Chiều rộng hè đường (m, 0 nếu không có):",
                    min_value=0.0, value=0.0, step=0.5, format="%.1f", key="d2_w_he_dt",
                )

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
                key="d2_loai_mat_dt",
            )
            tra_doc_dt = YTHH.tra_cuu_doc_ngang_do_thi(loai_mat_dt)
            i_doc_ngang_dt = st.number_input(
                f"Độ dốc ngang i (%) — Bảng 12: {tra_doc_dt['i_min']:g}÷{tra_doc_dt['i_max']:g}%:",
                min_value=float(tra_doc_dt["i_min"]),
                max_value=float(tra_doc_dt["i_max"]),
                value=float(tra_doc_dt["i_goi_y"]),
                step=0.5, format="%.1f", key="d2_i_doc_ngang_dt",
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

    b_cau = st.number_input(
        "Bề rộng Bc mặt cắt cầu (m):",
        min_value=6.0,
        value=float(draft.get('b_cau', st.session_state.design_data.get('bc', 12.0))),
        step=0.5,
    )

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
            help=f"Không được nhỏ hơn giá trị giới hạn tối thiểu {r_gh:,.0f} m theo {res_geo['tieu_chuan']}."
        )

        st.markdown("**Độ dốc dọc**")
        st.caption(f"Độ dốc dọc lớn nhất cho phép theo tiêu chuẩn: **imax = {imax_calc:.1f} %**")
        i_final_calc = st.number_input(
            "Độ dốc dọc thiết kế i (%):",
            min_value=0.0, max_value=imax_calc, value=imax_calc, step=0.1, format="%.1f",
            help=f"Không được vượt quá độ dốc dọc lớn nhất cho phép {imax_calc:.1f}% theo {res_geo['tieu_chuan']}."
        )
    else:
        st.error(
            f"⚠️ Không tra được yếu tố hình học cho loại đường **{l_hinhhoc}**: "
            f"{res_geo.get('message', 'Lỗi không xác định')}. "
            "Khi nhấn **Tiếp theo**, hệ thống sẽ **không** chạy được AI pipeline."
        )

    _vtk_from_geo = (res_geo.get('v_thiet_ke', 60)
                     if res_geo.get('status') == 'success'
                     else draft.get('vtk', 60))
    st.session_state.wizard_draft.update({
        'l_hinhhoc': l_hinhhoc, 'v_hinhhoc': v_hinhhoc,
        'd_hinhhoc': d_hinhhoc, 'input_tra_cuu': input_tra_cuu,
        'mcn_oto_override': mcn_oto_override,
        'b_cau': b_cau, 'bc': b_cau,
        'r_final_calc': r_final_calc, 'i_final_calc': i_final_calc,
        'vtk': _vtk_from_geo,
        'res_geo_ok': res_geo.get('status') == 'success',
    })

    st.markdown("<br>", unsafe_allow_html=True)
    btn_b, btn_f = st.columns([1, 1])
    with btn_b:
        if st.button("◀ Bước 1", use_container_width=True, key="d2_back"):
            st.session_state.open_dialog = "step1"
            st.rerun()
    with btn_f:
        if st.button("Bước 3 ▶", use_container_width=True, type="primary", key="d2_next"):
            _errs2 = {}
            _vtk2 = st.session_state.wizard_draft.get('vtk', 0)
            if _vtk2 <= 0:
                _errs2['vtk'] = "Vận tốc thiết kế phải lớn hơn 0"
            _bc2 = st.session_state.wizard_draft.get('bc', 0.0)
            if _bc2 < 3.5:
                _errs2['bc'] = f"Chiều rộng cầu {_bc2}m có vẻ quá nhỏ (thông thường ≥ 7m)"
            if _errs2:
                for _msg in _errs2.values():
                    st.error(f"⚠️ {_msg}")
            else:
                st.session_state.open_dialog = "step3"
                st.rerun()


@st.dialog("🚀 BƯỚC 3 / 3 — Xem lại & Chạy tính toán AI", width="large")
def dialog_step3():
    draft = st.session_state.wizard_draft

    st.markdown(
        DS.section_header(
            title = "Xem lại thông số & Chạy tính toán",
            icon  = "✅",
            sub   = "Kiểm tra lại toàn bộ trước khi chạy pipeline AI",
        ),
        unsafe_allow_html=True,
    )

    with st.expander("🌊 Thủy văn & Vị trí", expanded=True):
        s1a, s1b, s1c = st.columns(3)
        s1a.metric("Khu vực", "Miền Bắc" if draft.get('mien') == '1' else "Miền Nam")
        s1b.metric("Cấp sông", f"Cấp {['I','II','III','IV','V','VI'][int(draft.get('cap_s',4))-1]}")
        s1c.metric("Loại hình", "Kênh đào" if draft.get('loai_h') == '1' else "Sông tự nhiên")
        s2a, s2b, s2c, s2d = st.columns(4)
        s2a.metric("MNCN (H1%)", f"{draft.get('h1', 0):.3f} m")
        s2b.metric("MNTT (H5%)", f"{draft.get('h5', 0):.3f} m")
        s2c.metric("MNTC (H10%)", f"{draft.get('h10', 0):.3f} m")
        s2d.metric("MNTN (H98%)", f"{draft.get('h98', 0):.3f} m")
        st.caption(
            f"📍 Tim cầu: **{draft.get('x_tim_clearance', 0):.2f} m** | "
            f"Góc giao: **{draft.get('goc_giao', 90):.0f}°** | "
            f"Bản mặt cầu: **{draft.get('t_ban_mm', 200)} mm**"
        )

    with st.expander("🛣️ Hình học tuyến", expanded=True):
        _loai_map = {"Cao tốc": "🛣️ Cao tốc", "O to": "🚗 Ô tô", "Do thi": "🏙️ Đô thị"}
        st.markdown(
            f"Loại đường: **{_loai_map.get(draft.get('l_hinhhoc',''), '—')}** | "
            f"Vtk: **{draft.get('vtk', '—')} km/h** | "
            f"Địa hình: **{'Đồng bằng' if draft.get('d_hinhhoc')=='1' else 'Núi/Khó khăn'}**"
        )
        _mcn = draft.get('mcn_oto_override', {})
        if _mcn:
            st.caption(
                f"Số làn: {_mcn.get('so_lan', _mcn.get('n_lan_moi_chieu', '—'))} | "
                f"Rộng làn: {_mcn.get('w_lan', '—')} m | "
                f"Lề: {_mcn.get('w_le', _mcn.get('w_le_dat', '—'))} m"
            )
        st.caption(
            f"Bc = **{draft.get('b_cau', 0):.1f} m** | "
            f"R = **{draft.get('r_final_calc', 0):.0f} m** | "
            f"i = **{draft.get('i_final_calc', 0):.1f} %**"
        )

    ed1, ed2, _ = st.columns([1, 1, 2])
    with ed1:
        if st.button("✏️ Sửa thủy văn", key="d3_edit1", use_container_width=True):
            st.session_state.open_dialog = "step1"
            st.rerun()
    with ed2:
        if st.button("✏️ Sửa hình học", key="d3_edit2", use_container_width=True):
            st.session_state.open_dialog = "step2"
            st.rerun()

    st.markdown("---")
    st.markdown("**📋 Điều kiện địa phương**")
    is_urban_chk = st.checkbox(
        "Khu vực đông dân cư (hạn chế tiếng ồn/rung)",
        value=bool(draft.get('is_urban', st.session_state.design_data.get('is_urban', 0))),
        help="Ảnh hưởng đến lựa chọn loại cọc: khu đông dân → ưu tiên cọc ép",
        key="d3_urban",
    )
    st.session_state.wizard_draft['is_urban'] = int(is_urban_chk)

    st.markdown("<br>", unsafe_allow_html=True)
    back_col, run_col = st.columns([1, 2])
    with back_col:
        if st.button("◀ Bước 2", use_container_width=True, key="d3_back"):
            st.session_state.open_dialog = "step2"
            st.rerun()
    with run_col:
        st.markdown(
            "<p style='font-size:11px;color:#888;margin-bottom:4px'>"
            "🤖 Pipeline AI: TK → Hình học → KCN → Trụ → Móng → Lớp phủ → Bản vẽ → So sánh PA</p>",
            unsafe_allow_html=True,
        )
        submitted = st.button(
            "🚀 CHẠY TÍNH TOÁN AI",
            use_container_width=True,
            type="primary",
            key="d3_submit",
        )

    if submitted:
        d = st.session_state.wizard_draft
        mien             = d['mien']
        cap_s            = d['cap_s']
        loai_h           = d['loai_h']
        goc_giao         = d['goc_giao']
        h1               = d['h1']
        h5               = d['h5']
        h10              = d['h10']
        h98              = d['h98']
        t_ban_mm         = d['t_ban_mm']
        x_tim_clearance  = d['x_tim_clearance']
        l_hinhhoc        = d['l_hinhhoc']
        v_hinhhoc        = d.get('v_hinhhoc', 60)
        d_hinhhoc        = d.get('d_hinhhoc', '1')
        input_tra_cuu    = d.get('input_tra_cuu', v_hinhhoc)
        mcn_oto_override = d.get('mcn_oto_override', {})
        b_cau            = d.get('b_cau', 12.0)
        r_final_calc     = d.get('r_final_calc', 5000)
        i_final_calc     = d.get('i_final_calc', 4.0)
        is_urban_val     = d.get('is_urban', 0)

        _df_tl = st.session_state.get('df_tim_line', None)
        lt_diahinh_arr = None
        z_diahinh_arr  = None
        h_tn_tb = st.session_state.design_data.get('h_tn_tb', 0.0)
        if _df_tl is not None and not _df_tl.empty:
            _lt_col_t = next((c for c in _df_tl.columns if 'ý trình' in c or c.lower()=='ly_trinh'), None)
            _z_col_t  = next((c for c in _df_tl.columns if c.upper() == 'Z'), None)
            if _lt_col_t and _z_col_t:
                _mask_t = ((_df_tl[_lt_col_t] >= x_tim_clearance - 80) &
                           (_df_tl[_lt_col_t] <= x_tim_clearance + 80))
                _sub_t = _df_tl[_mask_t]
                h_tn_tb = float(_sub_t[_z_col_t].mean()) if not _sub_t.empty else float(_df_tl[_z_col_t].mean())
                lt_diahinh_arr = _df_tl[_lt_col_t].to_numpy()
                z_diahinh_arr  = _df_tl[_z_col_t].to_numpy()

        tracker = PipelineTracker(PIPELINE_STEPS)
        tracker.setup()
        pipeline_ok = True
        kcn_models  = None
        pier_models = None
        fnd_models  = None

        # ── TK ──────────────────────────────────────────────────────────
        tracker.start("TK")
        try:
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
            res['x_tim_clearance'] = x_tim_clearance
            res['mcn_oto_input'] = mcn_oto_override
            tracker.done("TK", f"B={res.get('B',0)}m  H={res.get('H',0)}m  Đáy dầm≥{res.get('day_dam',0):.3f}m")
        except Exception as _e:
            tracker.error("TK", str(_e))
            pipeline_ok = False
            res = {}

        # ── YTHH ────────────────────────────────────────────────────────
        if pipeline_ok:
            tracker.start("YTHH")
            try:
                res_geo = YTHH.tra_cuu_yeu_to_hinh_hoc(l_hinhhoc, input_tra_cuu, d_hinhhoc)
                if res_geo.get("status") != "success":
                    raise ValueError(
                        f"Không tính được yếu tố hình học tuyến: "
                        f"{res_geo.get('message', 'Lỗi không xác định')}. "
                        "Kiểm tra lại Loại đường, Vận tốc thiết kế và Địa hình."
                    )
                res['R_hinh_hoc']    = r_final_calc
                res['i_max_hinh_hoc'] = i_final_calc
                res['geo_logic'] = YTHH.tinh_toan_geo_logic(
                    res, h_tn_tb, res.get('day_dam', 0.0),
                    x_tim_clearance=x_tim_clearance,
                    lt_diahinh=lt_diahinh_arr, z_diahinh=z_diahinh_arr,
                )
                res['bc']         = b_cau
                res['loai_duong'] = l_hinhhoc
                res['vtk']        = res_geo.get("v_thiet_ke", 60)
                L_cau  = res['geo_logic'].get('L_cau', None)
                moi_tr = "Vượt sông"
                v3_path = os.path.join(os.path.dirname(__file__), "Data", "Bridge_Train_Dataset_v3.xlsx")
                res['ai_result'] = None
                tracker.done("YTHH",
                    f"L_cầu={L_cau:.1f}m  Bc={b_cau:.1f}m  Vtk={res['vtk']}km/h")
            except Exception as _e:
                tracker.error("YTHH", str(_e))
                pipeline_ok = False
        else:
            tracker.skip("YTHH")

        # ── KCN ─────────────────────────────────────────────────────────
        if pipeline_ok:
            tracker.start("KCN")
            try:
                try:
                    kcn_models = KCN.train_kcn_ai(v3_path=v3_path)
                except TypeError:
                    kcn_models = KCN.train_kcn_ai()
                except Exception as _e_train:
                    kcn_models = None
                    res['_kcn_error'] = f"train: {_e_train}"
                _kcn_raw = KCN.predict_kcn(
                    B_tk=res['B'], H_tk=res.get('H', 3.5),
                    goc=goc_giao, B_cau=res['bc'],
                    moi_truong=moi_tr, L_cau_tong=L_cau,
                    models=kcn_models,
                )
                if isinstance(_kcn_raw, dict) and "pa1_chi_phi" in _kcn_raw:
                    _pa = dict(_kcn_raw["pa1_chi_phi"])
                    _pa["do_tin_cay"] = 85 if kcn_models else 60
                    res['kcn_result'] = _pa
                    res['kcn_3_pa']   = _kcn_raw
                else:
                    res['kcn_result'] = _kcn_raw
                _kr = res.get('kcn_result') or {}
                tracker.done("KCN",
                    f"{_kr.get('tong_so_nhip','?')} nhịp × "
                    f"{_kr.get('chieu_dai','?')}m ({_kr.get('loai_dam','?')})")
            except Exception as _e:
                tracker.error("KCN", str(_e))
                res['kcn_result'] = None
        else:
            tracker.skip("KCN")

        # ── MOT ─────────────────────────────────────────────────────────
        if pipeline_ok:
            tracker.start("MOT")
            try:
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
                _ph = MOT.estimate_pier_height(
                    MNCN=h1, H_tinh_khong=res.get('H', 3.5),
                    H_dam=H_dam_est, MNTN=h98,
                    t_ban=float(res.get('t_ban_mm', 200)) / 1000.0,
                )
                H_tru_est   = _ph['H_than_tru']
                cao_day_dam = _ph['cao_day_dam']
                cao_mat_cau = _ph['cao_mat_cau']
                res['H_tru_est']   = H_tru_est
                res['cao_day_dam'] = cao_day_dam
                res['cao_mat_cau'] = cao_mat_cau
                is_urban = is_urban_val
                is_river = 1
                _n_nhip = (res.get('kcn_result', {}).get('tong_so_nhip', 1)
                           if res.get('kcn_result') else 1)
                res['tru_result'] = MOT.predict_pier(
                    vtk=res['vtk'], B_cau=res['bc'],
                    H_tru=H_tru_est, is_urban=is_urban,
                    is_river=is_river, cap_song=res['cap_song'],
                    loai_dam=loai_dam_cho_tru, n_nhip=_n_nhip,
                    models=pier_models,
                )
                _tr = res.get('tru_result') or {}
                tracker.done("MOT",
                    f"{_tr.get('loai_tru','?')}  H_trụ≈{H_tru_est:.1f}m")
            except Exception as _e:
                tracker.error("MOT", str(_e))
                res['tru_result'] = None
                H_tru_est = 8.0
                is_river  = 1
        else:
            tracker.skip("MOT")

        # ── MONG ────────────────────────────────────────────────────────
        if pipeline_ok:
            tracker.start("MONG")
            try:
                loai_tru_str = (
                    res['tru_result']['loai_tru'] if res.get('tru_result')
                    else 'Thân cột 2 trụ'
                )
                fnd_models = MONG.train_foundation_ai(v3_path=v3_path)
                res['mong_result'] = MONG.predict_foundation(
                    H_tru=res.get('H_tru_est', 8.0),
                    loai_tru=loai_tru_str,
                    is_river=is_river, cap_song=res['cap_song'],
                    B_cau=res['bc'], vtk=res['vtk'],
                    L_nhip=(res.get('kcn_result', {}).get('chieu_dai')
                            if res.get('kcn_result') else None),
                    is_urban=is_urban_val,
                    foundation_models=fnd_models,
                )
                _mg = res.get('mong_result') or {}
                tracker.done("MONG",
                    f"{_mg.get('loai_mong','?')}  "
                    f"D={_mg.get('duong_kinh_coc','?')}m  "
                    f"L={_mg.get('chieu_dai_coc','?')}m")
            except Exception as _e:
                tracker.error("MONG", str(_e))
                res['mong_result'] = None
        else:
            tracker.skip("MONG")

        # ── LPC ─────────────────────────────────────────────────────────
        tracker.start("LPC")
        try:
            res['lop_phu_result'] = LPC.tu_van_lop_phu(
                vtk=res.get('vtk', 60),
                loai_duong=res.get('loai_duong', 'Do thi'),
                L_nhip=(res.get('kcn_result', {}).get('chieu_dai', 40)
                        if res.get('kcn_result') else 40),
                moi_truong="Vượt sông",
            )
            _lp = res.get('lop_phu_result') or {}
            _lp_pa = str(_lp.get('phuong_an', '?'))
            tracker.done("LPC", (_lp_pa[:40] + "...") if len(_lp_pa) > 40 else _lp_pa)
        except Exception as _e:
            tracker.error("LPC", str(_e))
            res['lop_phu_result'] = None

        # ── BVK ─────────────────────────────────────────────────────────
        tracker.start("BVK")
        try:
            importlib.reload(BVK)
            importlib.reload(CTD)
            tracker.done("BVK", "Bản vẽ 2D/3D đã sẵn sàng")
        except Exception as _e:
            tracker.error("BVK", str(_e))

        if pipeline_ok:
            st.session_state.design_data = res
            _save_design_inputs(res)

        # ── SSP ─────────────────────────────────────────────────────────
        tracker.start("SSP")
        try:
            st.session_state.alternatives = SSP.generate_3_alternatives(
                B_tk=res.get('B', 20), H_tk=res.get('H', 3.5), goc=goc_giao,
                B_cau=res.get('bc', 12), moi_truong=moi_tr if pipeline_ok else "Vượt sông",
                L_cau=L_cau if pipeline_ok else None,
                kcn_models=kcn_models, pier_models=pier_models,
                fnd_models=fnd_models,
                MNCN=h1, H_tk_nhip=res.get('H', 3.5), h98=h98,
                cap_song=res.get('cap_song', cap_s), is_urban=is_urban_val,
                is_river=1, vtk=res.get('vtk', 60),
                pa1_kcn=res.get('kcn_result'),
                pa1_tru=res.get('tru_result'),
                pa1_mong=res.get('mong_result'),
            )
            tracker.done("SSP", "3 phương án đã được sinh và đánh giá")
        except Exception as _e:
            tracker.error("SSP", str(_e))
            st.session_state.alternatives = None

        n_errors = sum(
            1 for s in PIPELINE_STEPS
            if tracker.statuses[s["id"]] == PipelineTracker.STATUS_ERROR
        )
        n_critical_errors = sum(
            1 for sid in ["TK", "YTHH"]
            if tracker.statuses[sid] == PipelineTracker.STATUS_ERROR
        )
        tracker.finish(success=(n_critical_errors == 0))
        tracker.render_timing_summary()

        if pipeline_ok and res.get('kcn_result'):
            kcn = res.get('kcn_result') or (res.get('ai_result') or {})
            st.session_state.chatbot_context = (
                f"Vtk={res['vtk']}km/h | "
                f"LoaiDam={kcn.get('loai_dam','?')} | "
                f"L_nhip={kcn.get('chieu_dai','?')}m | "
                f"L_cau={res['geo_logic']['L_cau']:.1f}m | "
                f"LoaiTru={res.get('tru_result',{}).get('loai_tru','?')} | "
                f"LoaiMong={res.get('mong_result',{}).get('loai_mong','?')}"
            )
            time.sleep(1.2)
            if n_errors == 0:
                st.success("✅ Pipeline hoàn tất — chuyển sang Bản vẽ kỹ thuật")
            else:
                st.warning(
                    f"⚠️ Pipeline hoàn tất với {n_errors} bước có cảnh báo. "
                    "Kết quả vẫn được lưu — xem chi tiết ở trên."
                )
            time.sleep(0.8)
            st.session_state.open_dialog = None
            st.session_state.wizard_draft = {}
            st.session_state.current_tab = "Phương án 1"
            st.rerun()
        elif n_critical_errors > 0:
            st.error(
                f"❌ {n_critical_errors} bước quan trọng thất bại. "
                "Kiểm tra lại số liệu đầu vào và thử lại."
            )



# TRẠNG THỜI TAB & RIBBON TÙY CHỈNH
# =========================================================================

# Map tên tab cũ về mới
if st.session_state.current_tab in ("BẢN VẼ KẾT CẤU", "BẢN VẼ KỸ THUẬT"):
    st.session_state.current_tab = "Phương án 1"


def _get_tab_states(d: dict) -> dict:
    """Trả về dict trạng thái 'done' | 'partial' | 'locked' cho 3 tab."""
    has_kcn  = bool(d.get('kcn_result'))
    has_tru  = bool(d.get('tru_result'))
    has_mong = bool(d.get('mong_result'))
    has_basic = bool(d.get('day_dam')) or bool(d.get('bc'))

    # Tab 0 — THUYẾT MINH
    if has_kcn and has_tru and has_mong:
        tab0 = 'done'
    elif has_basic:
        tab0 = 'partial'
    else:
        tab0 = 'locked'

    # Tab 1 — BẢN VẼ KỸ THUẬT
    if has_kcn and has_tru:
        tab1 = 'done'
    elif has_kcn:
        tab1 = 'partial'
    else:
        tab1 = 'locked'

    # Tab 2 — SO SÁNH PHƯƠNG ÁN
    alts = st.session_state.get('alternatives')
    if alts is not None:
        tab2 = 'done'
    elif has_kcn:
        tab2 = 'partial'
    else:
        tab2 = 'locked'

    return {'tab0': tab0, 'tab1': tab1, 'tab2': tab2}


tab_states = _get_tab_states(st.session_state.design_data)

_STATE_STYLE = {
    'done':    {'bg': '#0d3d1f', 'border': '#2ecc71', 'badge_bg': '#2ecc71',
                'badge_text': '#0d3d1f', 'text': '#e0ffe8', 'icon': '✓'},
    'partial': {'bg': '#3a2c00', 'border': '#f39c12', 'badge_bg': '#f39c12',
                'badge_text': '#1a1000', 'text': '#fff3cc', 'icon': '📍'},
    'locked':  {'bg': '#1a1a2a', 'border': '#444466', 'badge_bg': '#333355',
                'badge_text': '#9999bb', 'text': '#888899', 'icon': '○'},
}
_STATE_LABEL = {
    'done':    'Hoàn tất',
    'partial': 'Đang tính',
    'locked':  'Chưa có dữ liệu',
}
_TAB_META = [
    {
        'key':      'THUYẾT MINH',
        'icon':     '📋',
        'state':    tab_states['tab0'],
        'tip':      'Kết quả tính toán tổng hợp',
        'lock_msg': 'Nhấn OPTIONS → OK để chạy tính toán',
    },
    {
        'key':      'Phương án 1',
        'icon':     '🖼️',
        'state':    tab_states['tab1'],
        'tip':      'Bản vẽ 2D/3D — Phương án 1 (tối ưu chi phí)',
        'lock_msg': 'Cần chạy tính toán kết cấu nhịp trước',
    },
    {
        'key':      'Phương án 2',
        'icon':     '🖼️',
        'state':    tab_states['tab1'],
        'tip':      'Bản vẽ 2D/3D — Phương án 2 (tối ưu mỹ quan)',
        'lock_msg': 'Cần chạy tính toán kết cấu nhịp trước',
    },
    {
        'key':      'Phương án 3',
        'icon':     '🖼️',
        'state':    tab_states['tab1'],
        'tip':      'Bản vẽ 2D/3D — Phương án 3 (AI đề xuất)',
        'lock_msg': 'Cần chạy tính toán kết cấu nhịp trước',
    },
    {
        'key':      'SO SÁNH PHƯƠNG ÁN',
        'icon':     '📊',
        'state':    tab_states['tab2'],
        'tip':      'So sánh 3 phương án loại dầm',
        'lock_msg': 'Cần chạy tính toán nhịp trước',
    },
    {
        'key':      'THƯ VIỆN',
        'icon':     '📚',
        'state':    'done',
        'tip':      'Thư viện cấu kiện dùng chung (mố/trụ/dầm/móng)',
        'lock_msg': '',
    },
]

# ══════════════════════════════════════════════════════════
# LAYOUT HELPERS — Topbar / Right panel / Status bar
# ══════════════════════════════════════════════════════════

def _render_topbar(d: dict, cur_tab: str) -> None:
    """Fixed 44px topbar: logo + tab nav + quick info + user."""
    _kcn   = d.get('kcn_result') or {}
    _geo   = d.get('geo_logic') or {}
    _L     = _geo.get('L_cau', 0)
    _dam   = _kcn.get('loai_dam', '')
    _nhip  = _kcn.get('tong_so_nhip', '')
    _cdai  = _kcn.get('chieu_dai', '')
    _info  = (
        f"L={_L:.1f}m · {_nhip}×{_cdai}m · {_dam}"
        if _L else "Chưa có dữ liệu — nhấn OPTIONS"
    )
    _u     = AUTH.current_user()
    _uname = _u.get('name', _u.get('username', ''))
    _crown = '👑' if AUTH.is_admin() else '👤'

    _tabs_h = ""
    for _m in _TAB_META:
        _sc      = _STATE_STYLE[_m['state']]
        _is_act  = (cur_tab == _m['key'])
        _sc_text = _sc['text']
        _sc_bbg  = _sc['badge_bg']
        _sc_btxt = _sc['badge_text']
        _sc_icon = _sc['icon']
        _bb      = f"border-bottom:3px solid {_sc['border']}" if _is_act else "border-bottom:3px solid transparent"
        _bg      = f"background:{_sc['bg']}" if _is_act else "background:transparent"
        _tabs_h += (
            f"<div style='padding:0 14px;height:44px;display:flex;align-items:center;"
            f"gap:5px;cursor:pointer;{_bg};{_bb};flex-shrink:0'>"
            f"<span style='font-size:13px'>{_m['icon']}</span>"
            f"<span style='font-size:11px;font-weight:600;color:{_sc_text}'>{_m['key']}</span>"
            f"<span style='font-size:9px;background:{_sc_bbg};"
            f"color:{_sc_btxt};padding:1px 6px;border-radius:9px'>"
            f"{_sc_icon}</span>"
            f"</div>"
        )

    st.markdown(
        f"<div class='uth-topbar'>"
        f"<div style='padding:0 14px;font-size:14px;font-weight:700;"
        f"color:#007acc;white-space:nowrap;border-right:1px solid #1e1e2e;"
        f"height:44px;display:flex;align-items:center'>🏗️ UTH</div>"
        f"<div class='uth-tabs'>{_tabs_h}</div>"
        f"<div class='uth-info' style='border-left:1px solid #1e1e2e;padding:0 12px;"
        f"font-size:10px;color:#666;white-space:nowrap;"
        f"max-width:260px;overflow:hidden;text-overflow:ellipsis'>{_info}</div>"
        f"<div style='border-left:1px solid #1e1e2e;padding:0 12px;"
        f"font-size:11px;color:#aaa;white-space:nowrap'>"
        f"{_crown} {_uname}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _rcard(title: str, icon: str, content_html: str, accent: str = "#007acc") -> str:
    """HTML cho một result card trong right panel."""
    return (
        f"<div style='background:#141420;border:1px solid #2a2a3a;"
        f"border-top:2px solid {accent};border-radius:8px;"
        f"padding:10px 12px;margin-bottom:8px'>"
        f"<div style='font-size:9px;color:#555;text-transform:uppercase;"
        f"letter-spacing:0.5px;margin-bottom:6px'>{icon} {title}</div>"
        f"{content_html}"
        f"</div>"
    )


def _render_right_panel_kl(base_d: dict, ribbon: str) -> None:
    """Panel phải khi đang ở 1 phương án: tóm tắt KHỐI LƯỢNG cấu kiện toàn cầu
    (thay cho các thẻ thông số AISummary)."""
    st.markdown(
        "<div style='font-size:10px;color:#555;text-transform:uppercase;"
        "letter-spacing:0.4px;margin:0 0 8px'>Khối lượng — " + ribbon + "</div>",
        unsafe_allow_html=True,
    )
    d = _build_pa_d(base_d, ribbon)
    if not (d.get('kcn_result') or d.get('ai_result')):
        st.markdown("<div style='font-size:11px;color:#444;text-align:center;"
                    "padding:10px'>Chưa tính toán — mở OPTIONS</div>",
                    unsafe_allow_html=True)
        return
    try:
        _rows = KL.bang_toan_cau(d, dam_roles=_pa_dam_roles(d, ribbon))
        _t = KL.tong_hop(_rows)
    except Exception as _e:
        st.caption(f"Lỗi khối lượng: {_e}")
        return

    for _icon, _lbl, _val, _col in (
        ("🧱", "Bê tông",  f"{_t['bt_m3']:.1f} m³",        "#4fc3f7"),
        ("🪵", "Ván khuôn", f"{_t['coppha_m2']:.0f} m²",   "#e67e22"),
        ("⛓️", "Cốt thép", f"{_t['thep_kg']/1000:.2f} tấn", "#2ecc71"),
    ):
        st.markdown(
            f"<div style='background:#141420;border:1px solid #2a2a3a;"
            f"border-left:3px solid {_col};border-radius:8px;padding:8px 12px;"
            f"margin-bottom:6px'>"
            f"<div style='font-size:10px;color:#888'>{_icon} {_lbl}</div>"
            f"<div style='font-size:18px;font-weight:700;color:{_col}'>{_val}</div>"
            f"</div>", unsafe_allow_html=True)

    # Top cấu kiện theo bê tông
    st.markdown("<div style='font-size:10px;color:#555;margin:8px 0 4px'>"
                "Theo cấu kiện (BT m³)</div>", unsafe_allow_html=True)
    for _r in sorted(_rows, key=lambda x: -x["bt_m3"])[:7]:
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;"
            f"font-size:11px;padding:2px 0;border-bottom:1px solid #1e1e2e'>"
            f"<span style='color:#aaa'>{_r['ten'][:22]}</span>"
            f"<span style='color:#4fc3f7;font-weight:600'>{_r['bt_m3']:.1f}</span>"
            f"</div>", unsafe_allow_html=True)
    st.caption("Khối lượng sơ bộ · chi tiết ở tab **Bố trí chung**.")


def _render_right_panel(d: dict) -> None:
    """Panel phải (col_right). Ở các tab phương án → tóm tắt khối lượng;
    nơi khác → 4 thẻ kết quả AI."""
    _ribbon = st.session_state.get('current_tab', '')
    if _ribbon in _PA_KEY_MAP:
        _render_right_panel_kl(d, _ribbon)
        return

    _kcn  = d.get('kcn_result') or {}
    _geo  = d.get('geo_logic') or {}
    _tru  = d.get('tru_result') or {}
    _mong = d.get('mong_result') or {}

    st.markdown(
        "<div style='font-size:10px;color:#555;text-transform:uppercase;"
        "letter-spacing:0.4px;margin:0 0 8px'>Kết quả AI</div>",
        unsafe_allow_html=True,
    )

    # Card 1 — Kết cấu nhịp
    if _kcn:
        _dam     = _kcn.get('loai_dam', '—')
        _col_dam = DS.dam_color(_dam)
        _c1 = (
            f"<div style='font-size:13px;font-weight:600;color:{_col_dam}'>{_dam}</div>"
            f"<div style='font-size:10px;color:#888;margin-top:3px'>"
            f"{_kcn.get('tong_so_nhip','?')} nhịp × {_kcn.get('chieu_dai','?')}m"
            f" · H={_kcn.get('chieu_cao_dam') or _kcn.get('chieu_cao','?')}m</div>"
        )
    else:
        _c1 = "<div style='font-size:11px;color:#444;text-align:center;padding:6px'>Chưa tính toán</div>"
    st.markdown(_rcard("Kết cấu nhịp", "🌉", _c1, "#007acc"), unsafe_allow_html=True)

    # Card 2 — Mố – Trụ
    if _tru:
        _lt = _tru.get('loai_tru', '—')
        _ht = d.get('H_tru_est', '—')
        _lmo = _tru.get('loai_mo', '—')
        _c2 = (
            f"<div style='font-size:13px;font-weight:600;color:#c39bd3'>{_lt}</div>"
            f"<div style='font-size:10px;color:#888;margin-top:3px'>"
            f"H≈{_ht}m · Mố: {str(_lmo)[:18]}</div>"
        )
    else:
        _c2 = "<div style='font-size:11px;color:#444;text-align:center;padding:6px'>Chưa tính toán</div>"
    st.markdown(_rcard("Mố – Trụ", "🏛️", _c2, "#9b59b6"), unsafe_allow_html=True)

    # Card 3 — Móng
    if _mong:
        _lm      = _mong.get('loai_mong', '—')
        _col_mng = DS.mong_color(_lm)
        _dc      = _mong.get('duong_kinh_coc', '—')
        _c3 = (
            f"<div style='font-size:13px;font-weight:600;color:{_col_mng}'>{_lm}</div>"
            f"<div style='font-size:10px;color:#888;margin-top:3px'>D = {_dc}m</div>"
        )
    else:
        _c3 = "<div style='font-size:11px;color:#444;text-align:center;padding:6px'>Chưa tính toán</div>"
    st.markdown(_rcard("Móng cầu", "⚙️", _c3, "#e67e22"), unsafe_allow_html=True)

    # Card 4 — Hình học tổng quát
    _L   = _geo.get('L_cau', 0)
    _bc  = d.get('bc', 0)
    _vtk = d.get('vtk', 0)
    if _L:
        _c4 = (
            f"<div style='font-size:13px;font-weight:600;color:#2ecc71'>{_L:.2f} m</div>"
            f"<div style='font-size:10px;color:#888;margin-top:3px'>"
            f"Bc={_bc:.1f}m · Vtk={_vtk} km/h</div>"
        )
    else:
        _c4 = "<div style='font-size:11px;color:#444;text-align:center;padding:6px'>Chưa có dữ liệu</div>"
    st.markdown(_rcard("Hình học tổng quát", "📐", _c4, "#2ecc71"), unsafe_allow_html=True)


def _render_statusbar(d: dict) -> None:
    """Fixed 22px status bar ở dưới cùng: pipeline progress."""
    _steps = [
        ("KCN",      bool(d.get('kcn_result'))),
        ("Mố-trụ",   bool(d.get('tru_result'))),
        ("Móng",     bool(d.get('mong_result'))),
        ("Lớp phủ",  bool(d.get('lop_phu_result'))),
        ("So sánh",  bool(st.session_state.get('alternatives'))),
    ]
    _done  = sum(1 for _, ok in _steps if ok)
    _items = " &nbsp;·&nbsp; ".join(
        (
            f"<span style='color:#2ecc71'>✓ {name}</span>"
            if ok else
            f"<span style='color:#333355'>○ {name}</span>"
        )
        for name, ok in _steps
    )
    _pct_c = "#2ecc71" if _done == 5 else "#007acc" if _done > 0 else "#333355"
    st.markdown(
        f"<div style='position:fixed;bottom:0;left:300px;right:0;z-index:500;"
        f"height:22px;background:#0a0a14;border-top:1px solid #1a1a2a;"
        f"display:flex;align-items:center;padding:0 16px;gap:12px;"
        f"font-size:10px;color:#444'>"
        f"<span style='color:#555;font-weight:600'>Pipeline:</span>"
        f"{_items}"
        f"<span style='margin-left:auto;color:{_pct_c};font-weight:600'>"
        f"{_done}/5 bước</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ── Topbar + nav buttons (phủ lên topbar) ────────────────────────────────────
_cur_tab = st.session_state.get('current_tab', 'THUYẾT MINH')
_render_topbar(st.session_state.design_data, _cur_tab)

# ── 3 HỘP KHAI BÁO ĐỘC LẬP — đặt TRÊN ribbon, mỗi nút mở 1 hộp thoại riêng
#    (không gôm chung thành 1 wizard tuần tự) ──────────────────────────────────
_has_kq_decl = bool(st.session_state.design_data.get('kcn_result'))
_dk1, _dk2, _dk4, _dk3 = st.columns(4)
with _dk1:
    if st.button("🌊 Thông số thủy văn & vị trí cầu",
                 use_container_width=True, key="declbtn_step1",
                 help="Khai báo thủy văn, mực nước, vị trí & tĩnh không"):
        st.session_state.field_touched = set()
        st.session_state.field_errors = {}
        st.session_state.field_warnings = {}
        st.session_state.open_dialog = "step1"
        st.rerun()
with _dk2:
    if st.button("🛣️ Tiêu chuẩn hình học tuyến đường",
                 use_container_width=True, key="declbtn_step2",
                 help="Loại đường, vận tốc, bề rộng, bán kính, độ dốc"):
        st.session_state.open_dialog = "step2"
        st.rerun()
with _dk4:
    _has_geo = bool(st.session_state.get("df_geology") is not None
                    or st.session_state.get("dia_chat_frames"))
    if st.button("🪨 Địa hình & Địa chất" + (" ✓" if _has_geo else ""),
                 use_container_width=True, key="declbtn_geodata",
                 help="Nạp .NTD/VN-2000 + Excel địa chất — DÙNG CHUNG cho cả 3 phương án"):
        st.session_state.open_dialog = "geodata"
        st.rerun()
with _dk3:
    if st.button("✅ Xem lại thông số & Chạy tính toán",
                 use_container_width=True, key="declbtn_step3",
                 type="primary" if not _has_kq_decl else "secondary",
                 help="Xem lại toàn bộ rồi chạy pipeline AI"):
        st.session_state.open_dialog = "step3"
        st.rerun()

_col_tabs = st.columns(len(_TAB_META))
for _ci, (_col, _m) in enumerate(zip(_col_tabs, _TAB_META)):
    with _col:
        if _m['state'] == 'locked':
            st.button(
                f"{_m['icon']} {_m['key']}",
                disabled=True,
                use_container_width=True,
                help=f"🔒 {_m['lock_msg']}",
                key=f"ribbonbtn_{_ci}",
            )
        else:
            if st.button(
                f"{_m['icon']} {_m['key']}",
                use_container_width=True,
                type="primary" if (_cur_tab == _m['key']) else "secondary",
                key=f"ribbonbtn_{_ci}",
            ):
                st.session_state.current_tab = _m['key']
                st.rerun()

# ── Hộp khai báo độc lập — mỗi box là @st.fragment để tránh rerun toàn bộ ──

@st.fragment
def _decl_box_thuy_van():
    _sd = st.session_state.design_data
    _has_tv = bool(_sd.get('MNCN') and _sd.get('MNCN') != 3.5 or _sd.get('x_tim_clearance'))
    with st.expander("🌊 Thủy văn & Vị trí", expanded=not _has_tv):
        _tc1, _tc2 = st.columns(2)
        with _tc1:
            _mn1 = st.number_input("MNCN (m)", value=float(_sd.get('MNCN', 3.5)),
                                    step=0.1, format="%.2f", key="dinp_MNCN")
            _mn3 = st.number_input("MNTC (m)", value=float(_sd.get('MNTC', 1.5)),
                                    step=0.1, format="%.2f", key="dinp_MNTC")
            _B_tk = st.number_input("Rộng tĩnh không (m)", value=float(_sd.get('B', 20.0)),
                                     step=0.5, key="dinp_B")
            _day_dam = st.number_input("Cao trình đáy cầu (m)", value=float(_sd.get('day_dam', 0.0)),
                                        step=0.1, key="dinp_day_dam")
            _xtim = st.number_input("Lý trình tim TK (m)", value=float(_sd.get('x_tim_clearance', 0.0)),
                                     step=1.0, key="dinp_xtim")
        with _tc2:
            _mn2 = st.number_input("MNTT (m)", value=float(_sd.get('MNTT', 2.0)),
                                    step=0.1, format="%.2f", key="dinp_MNTT")
            _mn4 = st.number_input("MNTN (m)", value=float(_sd.get('MNTN', 0.5)),
                                    step=0.1, format="%.2f", key="dinp_MNTN")
            _H_tk = st.number_input("Cao tĩnh không (m)", value=float(_sd.get('H', 4.75)),
                                     step=0.25, key="dinp_H")
            _cap_s_opts = ["IV","V","VI","III","II","I"]
            _cap_idx = _cap_s_opts.index(str(_sd.get('cap_song','VI'))) if str(_sd.get('cap_song','VI')) in _cap_s_opts else 2
            _cap_song = st.selectbox("Cấp sông", _cap_s_opts, index=_cap_idx, key="dinp_cap_song",
                                      format_func=lambda x: f"Cấp {x}")
            _goc_giao = st.number_input("Góc giao (°)", value=float(_sd.get('goc_giao', 90.0)),
                                         step=5.0, key="dinp_goc_giao")
        if st.button("✅ Áp dụng & Lưu", use_container_width=True, key="btn_apply_tv"):
            st.session_state.design_data.update({
                'MNCN': _mn1, 'MNTT': _mn2, 'MNTC': _mn3, 'MNTN': _mn4,
                'B': _B_tk, 'H': _H_tk, 'day_dam': _day_dam,
                'x_tim_clearance': _xtim, 'cap_song': _cap_song, 'goc_giao': _goc_giao,
            })
            _save_design_inputs(st.session_state.design_data)
            st.toast("✅ Đã lưu — Thủy văn & Vị trí", icon="✅")

@st.fragment
def _decl_box_hinh_hoc():
    _sd = st.session_state.design_data
    _has_hh = bool(_sd.get('vtk') and _sd.get('vtk') != 60 or _sd.get('bc') != 12.0)
    with st.expander("🛣️ Hình học & Giao thông", expanded=not _has_hh):
        _hc1, _hc2 = st.columns(2)
        with _hc1:
            _vtk = st.number_input("Vận tốc TK (km/h)", value=int(_sd.get('vtk', 60)),
                                    step=10, key="dinp_vtk")
            _bc = st.number_input("Chiều rộng cầu (m)", value=float(_sd.get('bc', 12.0)),
                                   step=0.5, key="dinp_bc")
            _t_ban = st.number_input("Chiều dày bản (mm)", value=int(_sd.get('t_ban_mm', 200)),
                                      step=25, key="dinp_tban")
        with _hc2:
            _ld_opts = ["Do thi", "Ngoai o"]
            _loai_duong = st.selectbox("Loại đường", _ld_opts, key="dinp_loai_duong",
                                        index=0 if _sd.get('loai_duong', 'Do thi') == 'Do thi' else 1)
            _i_max = st.number_input("Dốc dọc max (%)", value=float(_sd.get('i_max_hinh_hoc', 4.0)),
                                      step=0.5, key="dinp_imax")
            _R_hh = st.number_input("Bán kính bình đồ (m)", value=float(_sd.get('R_hinh_hoc', 5000.0)),
                                     step=100.0, key="dinp_Rhh")
        if st.button("✅ Áp dụng & Lưu", use_container_width=True, key="btn_apply_hh"):
            st.session_state.design_data.update({
                'vtk': _vtk, 'bc': _bc, 't_ban_mm': _t_ban,
                'loai_duong': _loai_duong, 'i_max_hinh_hoc': _i_max, 'R_hinh_hoc': _R_hh,
            })
            _save_design_inputs(st.session_state.design_data)
            st.toast("✅ Đã lưu — Hình học & Giao thông", icon="✅")

# ── Lưu/nạp địa hình mặc định (giống spt_sections_saved.json cho mặt cắt) ────
#   File tải lên lần đầu được lưu cạnh script → tự nạp cho lần dùng tiếp theo.
_TERRAIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "terrain_saved")
_TERRAIN_NTD = os.path.join(_TERRAIN_DIR, "terrain.ntd")
_DIA_CHAT_SAVED = os.path.join(_TERRAIN_DIR, "dia_chat.xlsx")  # địa chất mặc định


def _terrain_coord_path():
    """Đường dẫn file tọa độ đã lưu (ưu tiên .xlsx, sau đó .csv)."""
    for _ext in (".xlsx", ".csv"):
        _p = os.path.join(_TERRAIN_DIR, "terrain_coord" + _ext)
        if os.path.exists(_p):
            return _p
    return None


def _save_terrain_defaults(ntd_bytes: bytes, coord_bytes: bytes,
                           coord_name: str) -> None:
    """Auto-save file địa hình vừa tải để tái dùng cho lần sau."""
    try:
        os.makedirs(_TERRAIN_DIR, exist_ok=True)
        with open(_TERRAIN_NTD, "wb") as _f:
            _f.write(ntd_bytes)
        _ext = ".csv" if str(coord_name).lower().endswith(".csv") else ".xlsx"
        _coord_path = os.path.join(_TERRAIN_DIR, "terrain_coord" + _ext)
        # Dọn file tọa độ cũ khác đuôi để tránh nhập nhằng.
        _other = os.path.join(_TERRAIN_DIR,
                              "terrain_coord" + (".xlsx" if _ext == ".csv" else ".csv"))
        if os.path.exists(_other):
            try:
                os.remove(_other)
            except OSError:
                pass
        with open(_coord_path, "wb") as _f:
            _f.write(coord_bytes)
    except Exception:
        pass


def _load_terrain_defaults():
    """Đọc dữ liệu địa hình đã lưu → df_geology. None nếu chưa có / lỗi."""
    _coord_path = _terrain_coord_path()
    if not (os.path.exists(_TERRAIN_NTD) and _coord_path):
        return None
    try:
        with open(_TERRAIN_NTD, "rb") as _f:
            _ntd_buf = io.BytesIO(_f.read())
            _ntd_buf.name = os.path.basename(_TERRAIN_NTD)
        with open(_coord_path, "rb") as _f:
            _co_buf = io.BytesIO(_f.read())
            _co_buf.name = os.path.basename(_coord_path)
        df_ntd   = TV.parse_ntd_file(_ntd_buf)
        df_coord = TV.parse_coordinate_file(_co_buf)
        if df_coord is None or df_ntd.empty:
            return None
        _dg = TV.convert_to_vn2000(df_ntd, df_coord)
        return _dg if not _dg.empty else None
    except Exception:
        return None


@st.fragment
def _decl_box_dia_hinh():
    """Hộp khai báo 3 — Dữ liệu địa hình (.NTD + tọa độ VN-2000)."""
    with st.expander("📥 Địa hình (.NTD + tọa độ VN-2000)",
                     expanded=("df_geology" not in st.session_state)):
        st.caption("Nạp file khảo sát để bản vẽ tích hợp địa hình thực đo.")
        _c1, _c2 = st.columns(2)
        with _c1:
            file_khao_sat = st.file_uploader(
                "📂 File .NTD (trắc dọc – ngang)", type=["ntd"], key="ntd_up")
        with _c2:
            file_toa_do = st.file_uploader(
                "📍 Tọa độ tim tuyến (.CSV/.XLSX)", type=["csv", "xlsx"], key="coord_up")
        if file_khao_sat and file_toa_do:
            with st.spinner("⚡ Đang đồng bộ tọa độ VN-2000..."):
                df_ntd   = TV.parse_ntd_file(file_khao_sat)
                df_coord = TV.parse_coordinate_file(file_toa_do)
            if df_coord is not None and not df_ntd.empty:
                _dg = TV.convert_to_vn2000(df_ntd, df_coord)
                if not _dg.empty:
                    st.session_state.df_geology = _dg
                    _tl = (_dg[_dg["Offset"] == 0][["Lý trình", "Z"]]
                           .drop_duplicates("Lý trình").sort_values("Lý trình"))
                    st.session_state.df_tim_line = _tl
                    _save_terrain_defaults(file_khao_sat.getvalue(),
                                           file_toa_do.getvalue(),
                                           file_toa_do.name)
                    st.success(f"✅ Đã đồng bộ {len(_dg)} điểm địa hình theo "
                               "VN-2000! (đã lưu làm mặc định cho lần sau)")
        elif "df_geology" not in st.session_state:
            # Chưa tải file → tự nạp dữ liệu địa hình mặc định đã lưu.
            _dg = _load_terrain_defaults()
            if _dg is not None and not _dg.empty:
                st.session_state.df_geology = _dg
                _tl = (_dg[_dg["Offset"] == 0][["Lý trình", "Z"]]
                       .drop_duplicates("Lý trình").sort_values("Lý trình"))
                st.session_state.df_tim_line = _tl
                st.info(f"🗺️ Đã tự nạp địa hình mặc định ({len(_dg)} điểm). "
                        "Tải file mới ở trên để thay thế.")


def _process_geology_excel(file, persist=True):
    """Đọc file Excel địa chất 3 sheet → lưu session (dùng chung 3 phương án).
    Lưu cả dia_chat_data (cho trắc dọc) và dia_chat_frames (df thô cho 3D).
    persist=True → ghi file ra terrain_saved/dia_chat.xlsx làm MẶC ĐỊNH cho
    lần sau (tự nạp lúc khởi động, không cần mở hộp khai báo)."""
    df_hk, df_layers, df_spt = TV.doc_excel_dia_chat_3_sheet(file)
    if df_hk is None or df_hk.empty:
        return None
    _hk_list_ss = []
    for _i, _hkr in df_hk.iterrows():
        _ten_hk = str(_hkr.get("Ho_Khoan", f"HK{_i}")).strip().upper()
        _z_m    = float(_hkr.get("Z_Mieng", 0) or 0)
        _lop_dat_ss, _prev_z = [], _z_m
        if df_layers is not None and not df_layers.empty:
            _hk_lops = df_layers[df_layers["Ho_Khoan"] == _ten_hk]
            for _, _lr in _hk_lops.iterrows():
                _z_day = float(_lr.get("Cao_Do_Day", _prev_z - 2) or _prev_z - 2)
                _lop_dat_ss.append({
                    "ten_lop": str(_lr.get("Ten_Lop", "?")).strip(),
                    "cao_do_dinh": round(_prev_z, 3),
                    "cao_do_day":  round(_z_day, 3),
                    "chieu_day":   round(_prev_z - _z_day, 2),
                    "mo_ta": "", "loai_dat": "",
                })
                _prev_z = _z_day
        _hk_list_ss.append({
            "ten": _ten_hk, "X": float(_hkr.get("X_VN2000", 0) or 0),
            "Y": float(_hkr.get("Y_VN2000", 0) or 0), "Z": _z_m,
            "ly_trinh": None, "lop_dat": _lop_dat_ss, "spt": [],
        })
    st.session_state["dia_chat_data"] = {
        "ho_khoan_list": _hk_list_ss, "validation_errors": [],
        "dac_trung_tong_hop": {},
    }
    st.session_state["dia_chat_frames"] = (df_hk, df_layers, df_spt)
    if persist:
        try:
            os.makedirs(_TERRAIN_DIR, exist_ok=True)
            _b = file.getvalue() if hasattr(file, "getvalue") else None
            if _b:
                with open(_DIA_CHAT_SAVED, "wb") as _fp:
                    _fp.write(_b)
        except Exception:
            pass
    return df_hk, df_layers, df_spt


def _autoload_geo_defaults() -> None:
    """Tự nạp địa hình + địa chất MẶC ĐỊNH (đã lưu) vào phiên NGAY khi khởi động
    — để tab 3D có dữ liệu mà KHÔNG cần mở hộp khai báo địa chất trước.
    Chỉ chạy 1 lần/phiên (đã có trong session thì bỏ qua)."""
    if "df_geology" not in st.session_state:
        try:
            _dg = _load_terrain_defaults()
            if _dg is not None and not _dg.empty:
                st.session_state.df_geology = _dg
                _tl = (_dg[_dg["Offset"] == 0][["Lý trình", "Z"]]
                       .drop_duplicates("Lý trình").sort_values("Lý trình"))
                st.session_state.df_tim_line = _tl
        except Exception:
            pass
    if "dia_chat_frames" not in st.session_state and os.path.exists(_DIA_CHAT_SAVED):
        try:
            with open(_DIA_CHAT_SAVED, "rb") as _fp:
                _buf = io.BytesIO(_fp.read())
            _buf.name = "dia_chat.xlsx"
            _process_geology_excel(_buf, persist=False)
        except Exception:
            pass


_autoload_geo_defaults()


@st.dialog("🪨 Địa hình & Địa chất (dùng chung 3 phương án)", width="large")
def dialog_geo_data():
    st.caption("Dữ liệu địa hình & địa chất dùng CHUNG cho cả 3 phương án.")
    st.markdown("#### 🗺️ Địa hình (.NTD + tọa độ VN-2000)")
    _decl_box_dia_hinh()
    st.markdown("---")
    st.markdown("#### 🪨 Địa chất (Excel 3 sheet: Toado_HK · HKxx · SPT)")
    _dc_tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "Data", "Template_DiaChat.xlsx")
    if os.path.exists(_dc_tpl):
        with open(_dc_tpl, "rb") as _fh_tpl:
            st.download_button(
                "⬇️ Tải Template_DiaChat.xlsx", data=_fh_tpl.read(),
                file_name="Template_DiaChat.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True, key="dl_tpl_dc")
    _f = st.file_uploader("File .xlsx địa chất (theo template):",
                          type=["xlsx"], key="dc_ex")
    if _f:
        with st.spinner("Đang phân tích địa chất..."):
            _r = _process_geology_excel(_f)
        if _r is not None:
            st.success(f"✅ Đã nạp {len(_r[0])} hố khoan — dùng chung cho cả 3 phương án.")
        else:
            st.error("❌ Không đọc được dữ liệu. Kiểm tra cấu trúc file theo template.")
    elif st.session_state.get("dia_chat_frames"):
        _fhk = st.session_state["dia_chat_frames"][0]
        st.caption(f"✅ Đang có dữ liệu địa chất: {len(_fhk)} hố khoan trong phiên.")


# ── Dialog dispatcher ────────────────────────────────────────────────────────
# TIÊU THỤ cờ NGAY trước khi mở: st.dialog là fragment (tự rerun nội bộ) nên chỉ
# cần gọi 1 lần để mở; Streamlit tự giữ mở. Nếu KHÔNG xoá cờ, khi người dùng bấm
# X đóng lại → full-rerun thấy cờ vẫn còn → mở lại liên tục (gây khó chịu, nhất
# là trên điện thoại). Xoá cờ trước khi gọi để đóng là đóng hẳn.
_od = st.session_state.get('open_dialog')
if _od:
    st.session_state.open_dialog = None
    if _od == "step1":
        dialog_step1()
    elif _od == "step2":
        dialog_step2()
    elif _od == "step3":
        dialog_step3()
    elif _od == "geodata":
        dialog_geo_data()

# (3 hộp khai báo đã chuyển LÊN TRÊN ribbon — xem khối "3 HỘP KHAI BÁO ĐỘC LẬP".
#  Hộp khai báo địa hình nằm trong tab BẢN VẼ KỸ THUẬT.)

# --- THANH SIDEBAR TRÍI ---
def _data_file_registry() -> dict:
    """Mọi file dữ liệu NGƯỜI DÙNG cần lưu bền (arcname → đường dẫn)."""
    _root = pathlib.Path(__file__).parent
    return {
        "auth_users.json":              _root / "auth_users.json",
        "design_data_saved.json":       _DESIGN_SAVE_FILE,
        "spt_sections_saved.json":      _root / "spt_sections_saved.json",
        "Data/Library/beams.json":      pathlib.Path(CLIB.beams_path()),
        "Data/Library/piers.json":      pathlib.Path(CLIB.piers_path()),
        "Data/Library/mos.json":        pathlib.Path(CLIB.mos_path()),
        "Data/Library/railings.json":   pathlib.Path(CLIB.railings_path()),
        "Data/Library/components.json": pathlib.Path(CLIB.library_path()),
        "terrain_saved/terrain.ntd":        _root / "terrain_saved" / "terrain.ntd",
        "terrain_saved/terrain_coord.xlsx": _root / "terrain_saved" / "terrain_coord.xlsx",
    }


def _render_data_backup() -> None:
    """Sao lưu/khôi phục TOÀN BỘ dữ liệu người dùng dưới dạng 1 file .zip."""
    reg = _data_file_registry()
    with st.expander("💾 Sao lưu / Khôi phục dữ liệu", expanded=False):
        st.caption(
            "Sao lưu TOÀN BỘ dữ liệu người dùng (tài khoản, thư viện dầm & cấu "
            "kiện, thông số dự án, mặt cắt mặc định, địa hình). Tải về để commit/"
            "giữ; nạp lại để khôi phục sau khi server reset.")
        _buf = io.BytesIO()
        _present = []
        with zipfile.ZipFile(_buf, "w", zipfile.ZIP_DEFLATED) as _zf:
            for _arc, _p in reg.items():
                try:
                    if _p and pathlib.Path(_p).exists():
                        _zf.write(str(_p), arcname=_arc)
                        _present.append(_arc)
                except Exception:
                    pass
        st.download_button(
            f"⬇️ Tải về sao lưu ({len(_present)} mục)", data=_buf.getvalue(),
            file_name="aibridge_backup.zip", mime="application/zip",
            use_container_width=True, key="data_backup_dl",
            disabled=(not _present))
        _upz = st.file_uploader("⬆️ Khôi phục từ .zip", type=["zip"],
                                key="data_restore_zip")
        if _upz is not None and st.button(
                "✅ Khôi phục dữ liệu", key="data_restore_apply",
                type="primary", use_container_width=True):
            try:
                _n = 0
                with zipfile.ZipFile(io.BytesIO(_upz.read())) as _zf:
                    _names = set(_zf.namelist())
                    for _arc, _p in reg.items():       # chỉ nhận file hợp lệ
                        if _arc in _names:
                            _bytes = _zf.read(_arc)
                            pathlib.Path(_p).parent.mkdir(parents=True, exist_ok=True)
                            pathlib.Path(_p).write_bytes(_bytes)
                            _n += 1
                st.session_state.pop("dam_beams", None)   # nạp lại từ file
                st.success(f"Đã khôi phục {_n} mục. Tải lại trang để áp dụng.")
                st.rerun()
            except Exception as _e:
                st.error(f"File sao lưu không hợp lệ: {_e}")


# ── DỰ ÁN: đóng gói / khôi phục .zip (design + thư viện cá nhân) ────────────
def _project_zip_bytes() -> bytes:
    """Gói dự án hiện tại thành .zip: manifest + design.json + library/*.json."""
    _u, _pid = _cur_user_pid()
    design = {k: st.session_state.design_data[k]
              for k in _DESIGN_SAVE_KEYS if k in st.session_state.design_data}
    try:
        design = json.loads(json.dumps(design, ensure_ascii=False, default=str))
    except Exception:
        pass
    meta = WS.project_meta(_u, _pid) if _u else {}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps({
            "kind": "ai-bridge-project", "version": 1, "app": "AI-Bridge-Design",
            "user": _u, "project": meta,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, ensure_ascii=False, indent=2))
        z.writestr("design.json", json.dumps(design, ensure_ascii=False, indent=2))
        _libdir = st.session_state.get("user_lib_dir") or CLIB.active_lib_dir()
        for _fn in CLIB.STORE_FILES:
            _p = os.path.join(_libdir, _fn)
            if os.path.exists(_p):
                z.write(_p, arcname=f"library/{_fn}")
    return buf.getvalue()


def _import_project_zip(username: str, data: bytes, replace_lib: bool = True) -> str:
    """Khôi phục từ .zip → TẠO dự án mới (không đè dự án hiện tại). Trả về pid mới.
    replace_lib=True → ghi đè thư viện cá nhân (dùng chung mọi dự án) bằng file."""
    z = zipfile.ZipFile(io.BytesIO(data))
    names = set(z.namelist())
    design = {}
    if "design.json" in names:
        design = json.loads(z.read("design.json").decode("utf-8"))
    pname = "Dự án nhập"
    if "manifest.json" in names:
        try:
            mani = json.loads(z.read("manifest.json").decode("utf-8"))
            pname = (mani.get("project") or {}).get("name") or pname
        except Exception:
            pass
    pid = WS.create_project(username, pname, design)
    if replace_lib:
        _libdir = WS.user_library_dir(username)
        os.makedirs(_libdir, exist_ok=True)
        for _fn in CLIB.STORE_FILES:
            _arc = f"library/{_fn}"
            if _arc in names:
                with open(os.path.join(_libdir, _fn), "wb") as f:
                    f.write(z.read(_arc))
    return pid


def _switch_project(new_pid: str) -> None:
    """Lưu dự án hiện tại rồi chuyển sang dự án khác (nạp lại design)."""
    _save_design_inputs(st.session_state.design_data)
    st.session_state["current_pid"] = new_pid
    st.session_state.pop("design_data", None)
    st.rerun()


def _render_project_panel() -> None:
    """Bảng quản lý nhiều dự án + Lưu/Mở .zip — render trong sidebar."""
    _u = (AUTH.current_user() or {}).get("username")
    if not _u:
        return
    projs = WS.list_projects(_u)
    if not projs:
        st.session_state["current_pid"] = WS.create_project(_u, "Dự án 1")
        projs = WS.list_projects(_u)
    ids   = [p["id"] for p in projs]
    names = {p["id"]: p.get("name", p["id"]) for p in projs}
    cur   = st.session_state.get("current_pid") or ids[0]
    if cur not in ids:
        cur = ids[0]; st.session_state["current_pid"] = cur

    st.markdown(
        "<hr style='border-color:#2a2a3a;margin:10px 0'>"
        "<p style='font-size:10px;color:#555;margin:0 0 6px;"
        "text-transform:uppercase;letter-spacing:0.4px'>📁 Dự án</p>",
        unsafe_allow_html=True)

    sel = st.selectbox("Dự án hiện tại", ids, index=ids.index(cur),
                       format_func=lambda i: names.get(i, i), key="proj_select")
    if sel != cur:
        _switch_project(sel)

    with st.expander("⚙️ Quản lý dự án", expanded=False):
        _nn = st.text_input("Tên dự án mới", key="proj_new_name",
                            placeholder="VD: Cầu Sông Hàn")
        _c1, _c2 = st.columns(2)
        if _c1.button("➕ Tạo mới", key="proj_create", use_container_width=True):
            if _nn.strip():
                _save_design_inputs(st.session_state.design_data)
                st.session_state["current_pid"] = WS.create_project(_u, _nn.strip())
                st.session_state.pop("design_data", None)
                st.rerun()
            else:
                st.warning("Nhập tên dự án mới.")
        if _c2.button("📑 Nhân bản", key="proj_dup", use_container_width=True):
            _save_design_inputs(st.session_state.design_data)
            st.session_state["current_pid"] = WS.duplicate_project(_u, cur)
            st.session_state.pop("design_data", None)
            st.rerun()
        _rn = st.text_input("Đổi tên dự án hiện tại", value=names.get(cur, ""),
                            key="proj_rename")
        if st.button("✏️ Lưu tên", key="proj_rename_btn", use_container_width=True):
            WS.rename_project(_u, cur, _rn.strip() or cur)
            st.rerun()
        if len(ids) > 1:
            if st.button("🗑️ Xoá dự án này", key="proj_del",
                         use_container_width=True):
                WS.delete_project(_u, cur)
                st.session_state["current_pid"] = None
                st.session_state.pop("design_data", None)
                st.rerun()
        else:
            st.caption("Không thể xoá dự án cuối cùng.")

    _safe = WS._slug(names.get(cur, "duan"))
    st.download_button(
        "💾 Lưu dự án (.zip)", data=_project_zip_bytes(),
        file_name=f"duan_{_safe}_{time.strftime('%Y%m%d')}.zip",
        mime="application/zip", use_container_width=True, key="proj_dl")

    _up = st.file_uploader("📂 Mở dự án (.zip)", type=["zip"], key="proj_up")
    if _up is not None:
        _rl = st.checkbox("Ghi đè thư viện cá nhân từ file", value=True,
                          key="proj_up_lib",
                          help="Thư viện dùng chung cho mọi dự án của bạn.")
        if st.button("⬆️ Khôi phục từ file", key="proj_up_btn",
                     use_container_width=True):
            try:
                _pid = _import_project_zip(_u, _up.getvalue(), replace_lib=_rl)
                st.session_state["current_pid"] = _pid
                st.session_state.pop("design_data", None)
                for _k in ("dam_beams", "dam_piers", "dam_mos", "lib_railings",
                           "lib_caps", "lib_stems", "lib_footings"):
                    st.session_state.pop(_k, None)
                st.success("✅ Đã khôi phục dự án từ file.")
                st.rerun()
            except Exception as _e:
                st.error(f"File dự án không hợp lệ: {_e}")


with st.sidebar:

    # ── VÙNG A: Thông tin dự án ──────────────────────────────────────────
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path   = os.path.join(current_dir, "Images", "UTH.jpg")
    if os.path.exists(logo_path):
        st.image(logo_path, width=260)

    st.markdown(
        "<div style='background:#1e1e2e;border:1px solid #2a2a3a;"
        "border-radius:8px;padding:14px 14px;margin:6px 0'>"
        "<div style='font-size:12px;color:#777;margin-bottom:8px;"
        "text-transform:uppercase;letter-spacing:0.6px'>Đề tài</div>"
        "<div style='font-size:17px;font-weight:700;color:#f0f0f0;line-height:1.45'>"
        "Tích hợp AI và BIM tự động hóa<br>thiết kế cầu đường bộ</div>"
        "<hr style='border-color:#2a2a3a;margin:11px 0'>"
        "<div style='font-size:14px;color:#cfcfcf;line-height:1.7'>"
        "👤 <b style='color:#fff'>SVTH:</b> Chương DND<br>"
        "👨‍🏫 <b style='color:#fff'>GVHD:</b> T.S Nguyễn Văn Hiển"
        "</div></div>",
        unsafe_allow_html=True,
    )

    _u = AUTH.current_user()
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:8px;padding:6px 0'>"
        f"<span style='font-size:18px'>{'👑' if AUTH.is_admin() else '👤'}</span>"
        f"<div>"
        f"<div style='font-size:12px;color:#ddd;font-weight:600'>"
        f"{_u.get('name', _u.get('username',''))}</div>"
        f"<div style='font-size:10px;color:#666'>{_u.get('role','').upper()}</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    _col_lo, _col_acc = st.columns(2)
    with _col_lo:
        if st.button("🚪 Đăng xuất", use_container_width=True, key="btn_logout"):
            AUTH.logout()
            st.rerun()
    with _col_acc:
        if AUTH.is_admin():
            if st.button("👥 Tài khoản", use_container_width=True, key="btn_account"):
                st.session_state['show_account'] = not st.session_state.get('show_account', False)

    if st.session_state.get('show_account') and AUTH.is_admin():
        with st.expander("👥 Quản lý tài khoản", expanded=True):
            AUTH.show_account_panel()
            if st.button("✕ Đóng", key="btn_close_acc"):
                st.session_state['show_account'] = False
                st.rerun()

    # ── Quản lý nhiều dự án + Lưu/Mở .zip ────────────────────────────────
    _render_project_panel()

    # ── VÙNG B: Thông số hiện hành ───────────────────────────────────────
    st.markdown(
        "<hr style='border-color:#2a2a3a;margin:10px 0'>"
        "<p style='font-size:10px;color:#555;margin:0 0 6px;"
        "text-transform:uppercase;letter-spacing:0.4px'>"
        "📊 Thông số hiện hành</p>",
        unsafe_allow_html=True,
    )

    _sd  = st.session_state.design_data
    _kcn = _sd.get('kcn_result') or _sd.get('ai_result') or {}
    _geo = _sd.get('geo_logic')  or {}
    _tru = _sd.get('tru_result') or {}
    _mng = _sd.get('mong_result') or {}
    _has_data = bool(_kcn.get('loai_dam'))

    if not _has_data:
        st.markdown(
            "<div style='padding:10px;background:#141420;"
            "border:1px dashed #333355;border-radius:8px;text-align:center'>"
            "<div style='font-size:20px;margin-bottom:4px'>○</div>"
            "<div style='font-size:11px;color:#555'>"
            "Chưa có kết quả<br>Nhấn OPTIONS để bắt đầu</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        def _sb_row(label: str, value: str, color: str = "#4fc3f7") -> str:
            return (
                f"<div style='display:flex;justify-content:space-between;"
                f"align-items:center;padding:4px 0;"
                f"border-bottom:1px solid #1e1e2e'>"
                f"<span style='font-size:10px;color:#666'>{label}</span>"
                f"<span style='font-size:11px;font-weight:600;"
                f"color:{color}'>{value}</span></div>"
            )

        _L_cau    = _geo.get('L_cau', 0)
        _loai_dam = _kcn.get('loai_dam', '—')
        _t_nhip   = _kcn.get('tong_so_nhip', '—')
        _L_nhip   = _kcn.get('chieu_dai', '—')
        _bc       = _sd.get('bc', 0)
        _vtk      = _sd.get('vtk', 0)
        _loai_tru = _tru.get('loai_tru', '—')
        _loai_mng = _mng.get('loai_mong', '—')
        _d_coc    = _mng.get('duong_kinh_coc', '—')
        _H_tru    = _sd.get('H_tru_est', '—')
        _cap_song = _sd.get('cap_song', '—')

        _dam_colors = {"Super-T": "#4fc3f7", "Dầm I": "#2ecc71", "T ngược": "#f39c12"}
        _dc = _dam_colors.get(_loai_dam, "#9b59b6")

        _rows_html = "".join([
            _sb_row("Dầm",      _loai_dam, _dc),
            _sb_row("Sơ đồ",    f"{_t_nhip}×{_L_nhip}m"),
            _sb_row("L cầu",    f"{_L_cau:.1f}m"),
            _sb_row("Bc",       f"{_bc:.1f}m"),
            _sb_row("Vtk",      f"{_vtk} km/h"),
            _sb_row("Trụ",      str(_loai_tru)[:20], "#c39bd3"),
            _sb_row("H trụ",    f"{_H_tru:.1f}m" if isinstance(_H_tru, float) else str(_H_tru)),
            _sb_row("Móng",     str(_loai_mng)[:18], "#f0a500"),
            _sb_row("D cọc",    f"{_d_coc}m"),
            _sb_row("Cấp sông", f"Cấp {_cap_song}"),
        ])

        st.markdown(
            f"<div style='background:#141420;border:1px solid #2a2a3a;"
            f"border-radius:8px;padding:8px 10px'>{_rows_html}</div>",
            unsafe_allow_html=True,
        )

        _steps_done = sum([
            bool(_sd.get('kcn_result')),
            bool(_sd.get('tru_result')),
            bool(_sd.get('mong_result')),
            bool(_sd.get('lop_phu_result')),
            bool(st.session_state.get('alternatives')),
        ])
        _pct_sb = int(_steps_done / 5 * 100)
        st.markdown(
            f"<div style='margin-top:6px'>"
            f"<div style='display:flex;justify-content:space-between;"
            f"font-size:10px;color:#555;margin-bottom:3px'>"
            f"<span>Hoàn thành pipeline</span>"
            f"<span style='color:#4fc3f7'>{_pct_sb}%</span></div>"
            f"<div style='background:#1e1e2e;border-radius:4px;"
            f"height:5px;overflow:hidden'>"
            f"<div style='width:{_pct_sb}%;height:100%;"
            f"background:linear-gradient(90deg,#007acc,#2ecc71)'>"
            f"</div></div></div>",
            unsafe_allow_html=True,
        )


# =========================================================================
# CHATBOT AI — WIDGET NỔI góc dưới phải (thu/phóng kiểu Messenger)
# Render TRƯỚC vùng chính (trước mọi st.stop) để luôn hiện ở mọi tab.
# =========================================================================
def _chat_resize_js():
    """Tay nắm góc TRÊN-TRÁI để kéo phóng to/thu nhỏ khung chat (cả 2 chiều).
    Khung neo dưới-phải → kéo lên-trái thì to ra. Lưu kích thước vào localStorage,
    tự áp lại sau mỗi rerun (MutationObserver). Chạy trong iframe → parent.document."""
    st.components.v1.html("""
<script>
(function(){
  var KW='cau_chat_w', KH='cau_chat_h';
  function msgTargets(wrap){
    // Phần tử CUỘN thực sự (mang height/overflow) + phần tử .st-key-chat_msgs
    var c = wrap.querySelector('.st-key-chat_msgs');
    if(!c) return [];
    var set = [c];
    c.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"]').forEach(function(x){ set.push(x); });
    if(c.matches && c.matches('[data-testid="stVerticalBlockBorderWrapper"]')) set.push(c);
    return set;
  }
  function applyH(wrap, h){
    msgTargets(wrap).forEach(function(el){
      el.style.height = h + 'px';
      el.style.maxHeight = 'none';
      el.style.overflow = 'auto';
    });
  }
  function curH(wrap){
    var t = msgTargets(wrap);
    var best = 320;
    t.forEach(function(el){ var r = el.getBoundingClientRect().height; if(r > 40) best = r; });
    return best;
  }
  function setup(pDoc, pWin){
    var wrap = pDoc.querySelector('.st-key-floatchat_wrap');
    if(!wrap) return;
    var sw0 = localStorage.getItem(KW), sh0 = localStorage.getItem(KH);
    if(sw0) wrap.style.width = sw0 + 'px';
    if(sh0) applyH(wrap, parseFloat(sh0));
    if(wrap.__chatGrip) return;
    wrap.__chatGrip = true;
    if(getComputedStyle(wrap).position === 'static') wrap.style.position = 'fixed';
    var g = pDoc.createElement('div');
    g.title = 'Kéo để phóng to / thu nhỏ';
    g.style.cssText = 'position:absolute;top:-4px;left:-4px;width:22px;height:22px;'
      + 'cursor:nwse-resize;z-index:100003;border-top:3px solid #4a9eff;'
      + 'border-left:3px solid #4a9eff;border-radius:9px 0 0 0;'
      + 'background:rgba(74,158,255,0.12);';
    wrap.appendChild(g);
    var drag=false, sx, sy, sw, sh;
    g.addEventListener('mousedown', function(e){
      drag=true; sx=e.clientX; sy=e.clientY;
      sw=wrap.getBoundingClientRect().width;
      sh=curH(wrap);
      e.preventDefault(); e.stopPropagation();
    });
    pDoc.addEventListener('mousemove', function(e){
      if(!drag) return;
      var nw=Math.min(Math.max(sw+(sx-e.clientX),320), pWin.innerWidth*0.9);
      var nh=Math.min(Math.max(sh+(sy-e.clientY),160), pWin.innerHeight*0.78);
      wrap.style.width=nw+'px';
      applyH(wrap, nh);
    });
    pDoc.addEventListener('mouseup', function(){
      if(!drag) return; drag=false;
      localStorage.setItem(KW, Math.round(parseFloat(wrap.style.width)||380));
      localStorage.setItem(KH, Math.round(curH(wrap)));
    });
  }
  function start(tries){
    try{
      var pDoc=window.parent.document, pWin=window.parent;
      if(!pDoc.body) throw 0;
      setup(pDoc, pWin);
      if(!pDoc.__chatMO){
        pDoc.__chatMO=true;
        new pWin.MutationObserver(function(){ setup(pDoc, pWin); })
          .observe(pDoc.body, {childList:true, subtree:true});
      }
    }catch(e){ if(tries<12) setTimeout(function(){ start(tries+1); }, 500); }
  }
  start(0);
})();
</script>
""", height=0)


def _render_floating_chat():
    st.session_state.setdefault('chat_open', False)
    st.markdown("""
    <style>
    /* Bong bóng mở chat (khi thu nhỏ) */
    .st-key-floatbtn_wrap { position: fixed; bottom: 20px; right: 20px; z-index: 100000; width: 150px; }
    .st-key-floatbtn_wrap button {
        border-radius: 28px !important; height: 50px; font-weight: 700;
        box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
    /* Khung chat (khi mở) — kéo tay nắm góc TRÊN-TRÁI để phóng to/thu nhỏ
       (neo dưới-phải nên nở lên-trái). Kích thước do JS điều khiển. */
    .st-key-floatchat_wrap {
        position: fixed; bottom: 20px; right: 20px; z-index: 100000;
        width: 380px; max-width: 92vw;
        background: #12121c; border: 1px solid #2a3550; border-radius: 14px;
        box-shadow: 0 12px 44px rgba(0,0,0,0.6); padding: 14px 12px 4px; }
    .st-key-floatchat_wrap [data-testid="stChatInput"] { background: transparent; }
    .st-key-chat_msgs { overflow: auto !important; }
    </style>
    """, unsafe_allow_html=True)

    if not st.session_state.chat_open:
        with st.container(key="floatbtn_wrap"):
            if st.button("💬 Hỏi AI", key="chat_open_btn", type="primary",
                         use_container_width=True):
                st.session_state.chat_open = True
                st.rerun()
        return

    with st.container(key="floatchat_wrap"):
        _h1, _h2 = st.columns([5, 1])
        _h1.markdown(
            "<div style='font-weight:700;color:#9ac8e8;padding-top:6px'>"
            "🤖 Trợ lý AI cầu</div>", unsafe_allow_html=True)
        if _h2.button("–", key="chat_min_btn", help="Thu nhỏ"):
            st.session_state.chat_open = False
            st.rerun()

        _box = st.container(height=320, key="chat_msgs")
        with _box:
            if not st.session_state.get("messages"):
                st.caption("Hỏi tôi về thông số, kết quả thiết kế, tiêu chuẩn… "
                           "(kéo tay nắm ◤ góc trên-trái để phóng to/thu nhỏ)")
            for _msg in st.session_state.get("messages", []):
                st.chat_message(_msg["role"]).write(_msg["content"])

        if _prompt := st.chat_input("Hỏi tôi về thiết kế…", key="float_chat_input"):
            st.session_state.messages.append({"role": "user", "content": _prompt})
            try:
                _design_info = st.session_state.chatbot_context
                _system_msg = (f"Bạn là chuyên gia thiết kế cầu UTH. "
                               f"Tri thức: {st.session_state.bridge_library}. "
                               f"Dữ liệu: {_design_info}")
                _resp = gemini_model.generate_content(
                    f"{_system_msg}\n\nCâu hỏi: {_prompt}")
                st.session_state.messages.append(
                    {"role": "assistant", "content": _resp.text})
                st.rerun()
            except Exception as _e:
                st.error(f"Lỗi AI: {_e}")

    # Tay nắm kéo góc trên-trái (phóng to/thu nhỏ cả 2 chiều)
    _chat_resize_js()

_render_floating_chat()

# =========================================================================
# VÙNG HIỂN THỊ CHÍNH
# =========================================================================
# ══════════════════════════════════════════════════════════════════════════
# THƯ VIỆN CẤU KIỆN
#   • Dầm  : danh sách thẻ + panel tạo/sửa (tái dùng luồng Chi tiết dầm CAD)
#   • Trụ/Mố/Móng : bảng tham số (st.data_editor)
# ══════════════════════════════════════════════════════════════════════════
_DAM_EDIT_PFX = "lib_dam_edit"
_PA_SPT_PFX   = {"Phương án 1": "spt_pa1",
                 "Phương án 2": "spt_pa2",
                 "Phương án 3": "spt_pa3"}


def _reset_dam_edit_state() -> None:
    """Xóa state CAD của pfx soạn thảo → bắt đầu một dầm trắng."""
    for _suf in ("", "tinv", "ibeam"):
        _p = f"{_DAM_EDIT_PFX}_{_suf}" if _suf else _DAM_EDIT_PFX
        for _k in ("sections", "state", "active", "hist", "undo"):
            st.session_state.pop(f"cad_{_p}_{_k}", None)
    st.session_state.pop(f"{_DAM_EDIT_PFX}_beam_type", None)
    st.session_state.pop(f"_effpfx_{_DAM_EDIT_PFX}", None)


def _pa_span_layout(pa_key: str) -> dict:
    """Cấu hình bố trí nhịp (span_layout) của 1 PA — lưu theo PA trong design_data."""
    _all = st.session_state.design_data.get("span_layout_by_pa") or {}
    return dict(_all.get(pa_key) or {})


def _save_pa_span_layout(pa_key: str, sl: dict) -> None:
    _all = dict(st.session_state.design_data.get("span_layout_by_pa") or {})
    _all[pa_key] = dict(sl or {})
    st.session_state.design_data["span_layout_by_pa"] = _all


def _pa_railing(pa_key: str) -> dict:
    """Lựa chọn lan can/giải phân cách của 1 PA → {'lan_can': id, 'giai_phan_cach': id}."""
    _all = st.session_state.design_data.get("railing_by_pa") or {}
    return dict(_all.get(pa_key) or {})


def _save_pa_railing(pa_key: str, sel: dict) -> None:
    _all = dict(st.session_state.design_data.get("railing_by_pa") or {})
    _all[pa_key] = {k: v for k, v in (sel or {}).items() if v}
    st.session_state.design_data["railing_by_pa"] = _all


def _resolve_railings_for_pa(pa_key: str) -> dict:
    """Trả về {'lan_can': rec|None, 'giai_phan_cach': rec|None} đã giải từ thư viện."""
    rails = st.session_state.get("lib_railings")
    if rails is None:
        rails = CLIB.load_railings()
    sel = _pa_railing(pa_key)
    out = {}
    for _t in CLIB.RAILING_TYPES:
        out[_t] = CLIB.get_railing(rails, sel.get(_t)) if sel.get(_t) else None
    return out


def _pa_dam_roles(d: dict, pa_key: str) -> list:
    """Danh sách vai trò dầm (nhãn, beam_rec|None, L) của 1 PA để thống kê/khối lượng."""
    sl = _pa_span_layout(pa_key)
    beams = st.session_state.get("dam_beams") or CLIB.load_beams()
    roles = []
    if sl.get("mode") == "two_tier":
        roles.append(("nhịp dẫn",  CLIB.get_beam(beams, sl.get("beam_dan")),  sl.get("L_dan")))
        roles.append(("nhịp chính", CLIB.get_beam(beams, sl.get("beam_main")), sl.get("L_main")))
    else:
        _bid = sl.get("beam_dan") or (d.get("lib_dam_applied") or {}).get(pa_key)
        roles.append(("toàn cầu", CLIB.get_beam(beams, _bid) if _bid else None,
                      sl.get("L_dan")))
    return roles


_PA_KEY_MAP = {"Phương án 1": "pa1_chi_phi",
               "Phương án 2": "pa2_my_quan",
               "Phương án 3": "pa3_ai"}


def _build_pa_d(base_d: dict, ribbon: str) -> dict:
    """Dựng design_data riêng cho 1 phương án: đổi kcn_result theo PA + nạp
    span_layout & lan can (dùng chung cho mọi nơi cần d của PA, kể cả panel phải)."""
    pa_key = _PA_KEY_MAP.get(ribbon)
    if not pa_key:
        return base_d
    d = dict(base_d)
    _3pa = base_d.get("kcn_3_pa") or {}
    if _3pa.get(pa_key):
        d["kcn_result"] = dict(_3pa[pa_key])
    d["span_layout"] = _pa_span_layout(ribbon)
    d["railings"] = _resolve_railings_for_pa(ribbon)
    return d


def _maybe_fragment(fn):
    """Bọc hàm bằng st.fragment nếu phiên bản Streamlit hỗ trợ — để thao tác
    bên trong (tích chọn ô) chỉ rerun cục bộ, KHÔNG reload cả trang."""
    _f = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None)
    return _f(fn) if _f else fn


def _render_kl_table(rows: list, title: str = None, key: str = None) -> None:
    """Hiển thị 1 bảng khối lượng: Cấu kiện · Số lượng · BT(m³) · Ván khuôn(m²) · Cốt thép(kg)."""
    if title:
        st.markdown(title)
    if not rows:
        st.caption("Chưa đủ dữ liệu để thống kê khối lượng.")
        return
    _df = pd.DataFrame([{
        "Cấu kiện":       r["ten"],
        "Số lượng":       r["so_luong"],
        "Bê tông (m³)":   r["bt_m3"],
        "Ván khuôn (m²)": r["coppha_m2"],
        "Cốt thép (kg)":  r["thep_kg"],
        "Ghi chú":        r.get("ghi_chu", ""),
    } for r in rows])
    st.dataframe(_df, use_container_width=True, hide_index=True, key=key)
    _t = KL.tong_hop(rows)
    st.caption(f"**Σ Tổng:** Bê tông **{_t['bt_m3']:.1f} m³** · "
               f"Ván khuôn **{_t['coppha_m2']:.0f} m²** · "
               f"Cốt thép **{_t['thep_kg']:.0f} kg** ({_t['thep_kg']/1000:.2f} tấn)")


def _apply_beam_to_pa(d: dict, pa_key: str, beam: dict, tier: str = "dan") -> None:
    """Gán dầm thư viện cho 1 PA + nạp sections vào pfx Chi tiết dầm của PA.

    tier='dan'  → dầm nhịp DẪN (pfx PA, overlay dùng cho nhịp dẫn).
    tier='main' → dầm nhịp CHÍNH (pfx '{PA}_main', overlay dùng cho nhịp chính).
    """
    base0 = _PA_SPT_PFX.get(pa_key, "spt")
    base  = base0 if tier == "dan" else f"{base0}_main"
    eff   = BBUI.effective_pfx(base, beam.get("loai_dam"))
    st.session_state[f"{base}_beam_type"] = beam.get("loai_dam", "Super-T")
    BBUI.import_beam_state(eff, beam)
    st.session_state[f"_loaded_beam_{base}"] = beam["id"]
    if tier == "dan":
        _ap = dict(d.get("lib_dam_applied") or {})
        _ap[pa_key] = beam["id"]
        d["lib_dam_applied"] = _ap
        st.session_state.design_data["lib_dam_applied"] = _ap
    # Cập nhật span_layout theo PA (kèm chiều dài dầm nếu đã khai báo)
    _sl  = _pa_span_layout(pa_key)
    _len = float(beam.get("chieu_dai", 0) or 0)
    if tier == "main":
        _sl["beam_main"] = beam["id"]
        _sl.setdefault("mode", "two_tier")
        if _len > 0:
            _sl["L_main"] = _len
    else:
        _sl["beam_dan"] = beam["id"]
        if _len > 0:
            _sl["L_dan"] = _len
    _save_pa_span_layout(pa_key, _sl)
    _lbl = "nhịp chính" if tier == "main" else "nhịp dẫn"
    st.toast(f"Đã áp dụng dầm “{beam.get('ten','')}” ({_lbl}) cho {pa_key}.", icon="✅")
    st.rerun()


def _render_dam_edit_panel(d: dict) -> None:
    """Panel tạo/sửa dầm (bung ra khi bấm + / Sửa, thu gọn sau khi Lưu)."""
    base       = _DAM_EDIT_PFX
    editing_id = st.session_state.get("_lib_dam_editing_id")
    _title     = "✏️ Sửa dầm" if editing_id else "➕ Tạo dầm mới"

    st.markdown(
        f"<div style='background:#0a1f35;border:1px solid #007acc;"
        f"border-radius:8px;padding:8px 12px;margin:6px 0'>"
        f"<b style='color:#4fc3f7'>{_title}</b> — chọn loại dầm, upload DXF mặt cắt "
        f"và khai báo đoạn (giống tab Chi tiết dầm), đặt tên rồi 💾 Lưu.</div>",
        unsafe_allow_html=True,
    )
    _nc1, _nc2 = st.columns([3, 1])
    with _nc1:
        st.text_input("Tên dầm", key="_lib_dam_name_in",
                      placeholder="VD: Super-T 38m TEDIS",
                      help="Tên hiển thị của loại dầm trong thư viện.")
    with _nc2:
        st.session_state.setdefault("_lib_dam_len_in", 33.0)
        st.number_input("Chiều dài dầm (m)", min_value=1.0, max_value=300.0,
                        step=0.1, key="_lib_dam_len_in",
                        help="Chiều dài định hình của dầm — dùng làm chiều dài "
                             "nhịp gợi ý khi áp dụng vào phương án.")

    try:
        # Dùng CHIỀU DÀI KHAI BÁO để dựng/đo dầm trong thư viện (độc lập với
        # chiều dài nhịp toàn cục) → mặt cắt dọc/3D & bố trí đoạn khớp số đã khai.
        _decl_L = float(st.session_state.get("_lib_dam_len_in", 0) or 0) or 33.0
        _kcn_panel = {**(d.get("kcn_result") or d.get("ai_result") or {}),
                      "chieu_dai": _decl_L}
        _d_panel = {**d, "kcn_result": _kcn_panel, "ai_result": _kcn_panel}
        BBUI.render_cad_spt_tab(_d_panel, pfx=base, show_type=False)
    except Exception as _e:
        import traceback
        st.error(f"Lỗi dựng dầm: {_e}")
        with st.expander("Chi tiết lỗi"):
            st.code(traceback.format_exc())

    st.markdown("---")
    _s1, _s2, _ = st.columns([1, 1, 3])
    if _s1.button("💾 Lưu dầm", type="primary", use_container_width=True,
                  key="_lib_dam_save_btn"):
        _nm = (st.session_state.get("_lib_dam_name_in") or "").strip()
        eff  = st.session_state.get(f"_effpfx_{base}", base)
        data = BBUI.export_beam_state(eff)
        if not _nm:
            st.warning("⚠️ Nhập **tên dầm** trước khi lưu.")
        elif not data.get("sections"):
            st.warning("⚠️ Chưa có mặt cắt nào — hãy upload ít nhất 1 file DXF.")
        else:
            beams = st.session_state.get("dam_beams", CLIB.load_beams())
            loai  = st.session_state.get(f"{base}_beam_type", "Super-T")
            bid   = editing_id or CLIB.make_beam_id(_nm, beams)
            rec = {
                "id": bid, "ten": _nm, "loai_dam": loai,
                "chieu_dai": float(st.session_state.get("_lib_dam_len_in", 0) or 0),
                "sections": data["sections"], "segs": data["segs"],
                "fill_sec": data["fill_sec"], "nguon": "người dùng",
                "created_by": (AUTH.current_user() or {}).get("name", ""),
                "updated_at": time.strftime("%Y-%m-%d %H:%M"),
            }
            st.session_state.dam_beams = CLIB.upsert_beam(beams, rec)
            CLIB.save_beams(st.session_state.dam_beams)
            st.session_state["_lib_dam_panel"] = None
            st.session_state.pop("_lib_dam_editing_id", None)
            st.toast(f"Đã lưu dầm “{_nm}”.", icon="✅")
            st.rerun()
    if _s2.button("Hủy", use_container_width=True, key="_lib_dam_cancel_btn"):
        st.session_state["_lib_dam_panel"] = None
        st.session_state.pop("_lib_dam_editing_id", None)
        st.rerun()


def _render_part_io(part_key: str, label: str, rows: list,
                    save_fn, ss_key: str | None = None) -> None:
    """Sao lưu / khôi phục thư viện CỤC BỘ cho 1 bộ phận.

    rows     : danh sách bản ghi hiện có của bộ phận đó.
    save_fn  : callback(list) lưu xuống đĩa (vd CLIB.save_beams).
    ss_key   : nếu có → cập nhật st.session_state[ss_key] = danh sách mới.
    File tải về theo định dạng {kind, part, rows}; khi upload chấp nhận cả
    file part lẫn danh sách thuần."""
    with st.expander(f"💾 Sao lưu / khôi phục thư viện {label}", expanded=False):
        st.caption(
            f"Tải về để giữ bản sao thư viện **{label}** (commit vào repo hoặc "
            "lưu sang máy khác); upload lại để khôi phục. Có thể **gộp** thêm "
            "hoặc **thay thế toàn bộ**.")
        _c1, _c2 = st.columns(2)
        with _c1:
            _payload = json.dumps(
                {"kind": "ai-bridge-part", "part": part_key, "version": 1,
                 "rows": rows}, ensure_ascii=False, indent=2)
            st.download_button(
                f"⬇️ Tải thư viện {label}", data=_payload.encode("utf-8"),
                file_name=f"thu_vien_{part_key}.json", mime="application/json",
                use_container_width=True, key=f"partio_dl_{part_key}")
        with _c2:
            _up = st.file_uploader(
                "⬆️ Nạp lại từ file (.json)", type=["json"],
                key=f"partio_ul_{part_key}")
        if _up is not None:
            try:
                _doc = json.loads(_up.read().decode("utf-8"))
                if isinstance(_doc, dict):
                    _imp = _doc.get("rows")
                    if _imp is None:
                        _imp = _doc.get(part_key, [])
                else:
                    _imp = _doc
                _imp = [r for r in (_imp or []) if isinstance(r, dict)]
            except Exception as _e:
                _imp = None
                st.error(f"File không hợp lệ: {_e}")
            if _imp is not None:
                _mode = st.radio(
                    "Cách nạp:", ["Gộp (giữ mục hiện có)", "Thay thế toàn bộ"],
                    horizontal=True, key=f"partio_mode_{part_key}")
                if st.button(f"✅ Xác nhận nạp {len(_imp)} mục",
                             type="primary", key=f"partio_apply_{part_key}"):
                    if _mode.startswith("Thay"):
                        _new = _imp
                    else:
                        _byid = {r.get("id"): r for r in rows if r.get("id")}
                        _extra = []
                        for _r in _imp:
                            if _r.get("id"):
                                _byid[_r["id"]] = _r
                            else:
                                _extra.append(_r)
                        _new = list(_byid.values()) + _extra
                    if ss_key:
                        st.session_state[ss_key] = _new
                    save_fn(_new)
                    st.success(f"Đã nạp {len(_imp)} mục vào thư viện {label}.")
                    st.rerun()


def _render_tru_io() -> None:
    """Sao lưu / khôi phục CHUNG cho cả 3 kho bộ phận trụ: xà mũ · thân · bệ.

    Đặt ở cấp tổng (trên hàng chọn Xà mũ/Thân/Bệ) — 1 file mang theo cả 3."""
    caps = st.session_state.get("lib_caps")
    if caps is None:
        caps = st.session_state.lib_caps = CLIB.load_caps()
    stems = st.session_state.get("lib_stems")
    if stems is None:
        stems = st.session_state.lib_stems = CLIB.load_stems()
    foots = st.session_state.get("lib_footings")
    if foots is None:
        foots = st.session_state.lib_footings = CLIB.load_footings()
    with st.expander("💾 Sao lưu / khôi phục thư viện trụ (xà mũ · thân · bệ)",
                     expanded=False):
        st.caption("Tải về / nạp lại **CHUNG** cho cả 3 bộ phận trụ trong 1 file. "
                   "Có thể **gộp** thêm hoặc **thay thế toàn bộ**.")
        _c1, _c2 = st.columns(2)
        with _c1:
            _payload = json.dumps(
                {"kind": "ai-bridge-pier", "version": 1,
                 "caps": caps, "stems": stems, "footings": foots},
                ensure_ascii=False, indent=2)
            st.download_button(
                "⬇️ Tải thư viện trụ", data=_payload.encode("utf-8"),
                file_name="thu_vien_tru.json", mime="application/json",
                use_container_width=True, key="partio_dl_tru")
        with _c2:
            _up = st.file_uploader("⬆️ Nạp lại từ file (.json)", type=["json"],
                                   key="partio_ul_tru")
        if _up is not None:
            try:
                _doc = json.loads(_up.read().decode("utf-8"))
                if not isinstance(_doc, dict):
                    raise ValueError("File trụ phải gồm caps/stems/footings")
                _ic = [r for r in (_doc.get("caps") or []) if isinstance(r, dict)]
                _is = [r for r in (_doc.get("stems") or []) if isinstance(r, dict)]
                _if = [r for r in (_doc.get("footings") or []) if isinstance(r, dict)]
            except Exception as _e:
                st.error(f"File không hợp lệ: {_e}")
            else:
                _mode = st.radio(
                    "Cách nạp:", ["Gộp (giữ mục hiện có)", "Thay thế toàn bộ"],
                    horizontal=True, key="partio_mode_tru")

                def _merge(cur, imp):
                    if _mode.startswith("Thay"):
                        return imp
                    _byid = {r.get("id"): r for r in cur if r.get("id")}
                    _ex = []
                    for r in imp:
                        if r.get("id"):
                            _byid[r["id"]] = r
                        else:
                            _ex.append(r)
                    return list(_byid.values()) + _ex

                if st.button(
                        f"✅ Xác nhận nạp {len(_ic)} xà mũ · {len(_is)} thân · "
                        f"{len(_if)} bệ", type="primary", key="partio_apply_tru"):
                    _nc, _ns, _nf = (_merge(caps, _ic), _merge(stems, _is),
                                     _merge(foots, _if))
                    st.session_state.lib_caps = _nc;     CLIB.save_caps(_nc)
                    st.session_state.lib_stems = _ns;    CLIB.save_stems(_ns)
                    st.session_state.lib_footings = _nf; CLIB.save_footings(_nf)
                    st.success("Đã nạp thư viện trụ (xà mũ · thân · bệ).")
                    st.rerun()


def render_dam_library(d: dict) -> None:
    """Tab Dầm: panel tạo/sửa (nếu đang mở) hoặc danh sách thẻ dầm."""
    if "dam_beams" not in st.session_state:
        st.session_state.dam_beams = CLIB.load_beams()

    # Đang mở panel tạo/sửa → ưu tiên hiển thị panel, ẩn danh sách
    if st.session_state.get("_lib_dam_panel"):
        _render_dam_edit_panel(d)
        return

    beams   = st.session_state.dam_beams
    applied = (d.get("lib_dam_applied") or {})

    _h1, _h2 = st.columns([3, 1])
    with _h1:
        st.markdown("##### 🌉 Thư viện dầm")
        st.caption("Mỗi dầm tạo qua panel như tab Chi tiết dầm. "
                   "Chọn & áp dụng dầm vào phương án ở tab **Bố trí chung**.")
    with _h2:
        if st.button("➕ Tạo dầm mới", type="primary", use_container_width=True,
                     key="lib_dam_new"):
            _reset_dam_edit_state()
            st.session_state.pop("_lib_dam_editing_id", None)
            st.session_state["_lib_dam_name_in"] = ""
            st.session_state["_lib_dam_len_in"] = 33.0
            st.session_state["_lib_dam_panel"] = "new"
            st.rerun()

    # ── Sao lưu / khôi phục thư viện dầm (cục bộ) ────────────────────────────
    _render_part_io("dam", "dầm", beams, CLIB.save_beams, ss_key="dam_beams")

    if not beams:
        st.info("Chưa có dầm nào. Bấm **➕ Tạo dầm mới** để bắt đầu.")
        return

    # Mỗi dầm một HÀNG, sắp xếp theo TÊN (như folder desktop) — người dùng
    # tự đặt tiền tố tên để điều khiển thứ tự. Áp dụng dầm làm ở tab Bố trí chung.
    st.caption("Danh sách sắp theo tên (A→Z) — đặt tên có tiền tố để xếp theo ý. "
               "Áp dụng dầm vào phương án ở tab **Bố trí chung**.")
    _beams_sorted = sorted(
        beams, key=lambda b: str(b.get("ten", "")).strip().lower())
    for b in _beams_sorted:
        _n_sec = len(b.get("sections", {}))
        _used  = [pa for pa, bid in applied.items() if bid == b.get("id")]
        _badge = (" · ".join(_used)) if _used else "chưa áp dụng"
        _info, _a3, _a4 = st.columns([8, 1, 1])
        with _info:
            st.markdown(
                f"<div style='background:#141420;border:1px solid #2a2a3a;"
                f"border-left:4px solid {DS.dam_color(b.get('loai_dam',''))};"
                f"border-radius:8px;padding:8px 12px'>"
                f"<span style='font-size:14px;font-weight:600;color:#f0f0f0'>"
                f"🌉 {b.get('ten','(không tên)')}</span>"
                f"<span style='font-size:11px;color:#888;margin-left:10px'>"
                f"{b.get('loai_dam','')} · "
                f"L={b.get('chieu_dai','—')}m · {_n_sec} mặt cắt · "
                f"{b.get('created_by','') or '—'}</span>"
                f"<span style='font-size:10px;color:#4fc3f7;margin-left:10px'>"
                f"📌 {_badge}</span></div>",
                unsafe_allow_html=True,
            )
        if _a3.button("✏️", key=f"lib_edit_{b['id']}",
                      use_container_width=True, help="Sửa dầm"):
            _reset_dam_edit_state()
            eff = BBUI.effective_pfx(_DAM_EDIT_PFX, b.get("loai_dam"))
            st.session_state[f"{_DAM_EDIT_PFX}_beam_type"] = b.get("loai_dam", "Super-T")
            BBUI.import_beam_state(eff, b)
            st.session_state["_lib_dam_editing_id"] = b["id"]
            st.session_state["_lib_dam_name_in"] = b.get("ten", "")
            st.session_state["_lib_dam_len_in"] = float(b.get("chieu_dai", 0) or 33.0)
            st.session_state["_lib_dam_panel"] = b["id"]
            st.rerun()
        if _a4.button("🗑️", key=f"lib_del_{b['id']}",
                      use_container_width=True, help="Xóa dầm"):
            st.session_state.dam_beams = CLIB.delete_beam(beams, b["id"])
            CLIB.save_beams(st.session_state.dam_beams)
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# THƯ VIỆN CẤU KIỆN LẮP GHÉP (assembly) — dùng chung cho TRỤ & MỐ.
# Mỗi loại 3 bộ phận (mũ / thân / bệ), mỗi phần upload mặt cắt DXF riêng.
# ══════════════════════════════════════════════════════════════════════════
def _asm_cfg(kind: str) -> dict:
    if kind == "mo":
        return {
            "kind": "mo", "label": "Mố", "icon": "🧱", "ss": "dam_mos",
            "color": "#c0a06b", "id_key": "abutment_assembly_id",
            "name_ph": "VD: Mố chữ U M1",
            "load": CLIB.load_mos, "save": CLIB.save_mos, "upsert": CLIB.upsert_mo,
            "delete": CLIB.delete_mo, "get": CLIB.get_mo, "mkid": CLIB.make_mo_id,
            "default": PB.default_abutment, "migrate": PB.migrate_abutment,
            "preview": PB.build_abutment_preview_fig, "total_h": PB.abutment_total_height,
            "parts": [
                {"role": "than", "label": "Tường thân",
                 "hint": "Vẽ NHIỀU mặt cắt DỌC cầu (hình bên: tường thân + vai "
                         "kê gối); hệ thống xếp nối tiếp theo NGANG cầu và LOFT "
                         "(vuốt) giữa các mặt cắt kề nhau.",
                 "param": "B", "plabel": "Bề rộng ngang cầu B (m)",
                 "pmin": 1.0, "pmax": 40.0, "pdef": 8.0, "flex": True},
                {"role": "be", "label": "Bệ mố",
                 "hint": "Mặt cắt = MẶT BẰNG (ngang × dọc) — đùn theo chiều cao.",
                 "param": "H", "plabel": "Chiều cao H (m)",
                 "pmin": 0.3, "pmax": 10.0, "pdef": 1.5, "flex": False},
            ],
        }
    return {
        "kind": "tru", "label": "Trụ", "icon": "🏗️", "ss": "dam_piers",
        "color": "#6d9dc5", "id_key": "pier_assembly_id",
        "name_ph": "VD: Trụ thân đặc T1",
        "load": CLIB.load_piers, "save": CLIB.save_piers, "upsert": CLIB.upsert_pier,
        "delete": CLIB.delete_pier, "get": CLIB.get_pier, "mkid": CLIB.make_pier_id,
        "default": PB.default_pier, "migrate": PB.migrate_pier,
        "preview": PB.build_pier_preview_fig, "total_h": PB.pier_total_height,
        "parts": [
            {"role": "xa_mu", "label": "Xà mũ",
             "hint": "Mặt cắt = MẶT ĐỨNG NGANG cầu (gồm công xôn) — đùn dọc cầu.",
             "param": "D", "plabel": "Chiều sâu dọc cầu D (m)",
             "pmin": 0.3, "pmax": 10.0, "pdef": 1.8, "flex": False},
            {"role": "than", "label": "Thân trụ",
             "hint": "Mặt cắt = MẶT BẰNG (ngang × dọc) — đùn theo chiều cao.",
             "param": "H", "plabel": "Chiều cao H (m)",
             "pmin": 0.3, "pmax": 60.0, "pdef": 5.0, "flex": True},
            {"role": "be", "label": "Bệ trụ",
             "hint": "Mặt cắt = MẶT BẰNG (ngang × dọc) — đùn theo chiều cao.",
             "param": "H", "plabel": "Chiều cao H (m)",
             "pmin": 0.3, "pmax": 10.0, "pdef": 1.5, "flex": False},
        ],
    }


def _asm_labels(cfg: dict) -> dict:
    return {pt["role"]: pt["label"] for pt in cfg["parts"]}


def _clear_asm_widgets(kind: str) -> None:
    """Xóa giá trị widget cũ khi mở panel tạo/sửa (tránh dính dữ liệu trước)."""
    _keys = [f"_lib_{kind}_name", f"pp_{kind}_than_flex", f"nlay_{kind}_xamu"]
    for role in ("be", "than", "xa_mu"):
        _keys += [f"{kind}_dxf_{role}", f"_{kind}_sig_{role}"]
        for pp in ("H", "B", "D"):
            _keys.append(f"pp_{kind}_{role}_{pp}")
    for i in range(3):      # tầng xà mũ
        _keys += [f"{kind}_dxf_xamu_L{i}", f"_{kind}_sig_xamu_L{i}",
                  f"pp_{kind}_xamu_D_L{i}"]
    for i in range(16):     # đoạn tường thân mố (mặt cắt dọc + loft ngang)
        _keys += [f"{kind}_dxf_than_L{i}", f"_{kind}_sig_than_L{i}",
                  f"pp_{kind}_than_B_L{i}", f"pp_{kind}_than_loft_L{i}"]
    _keys.append(f"_than_secs_{kind}")    # store mặt cắt theo đoạn tường thân
    for _k in _keys:
        st.session_state.pop(_k, None)


def _asm_section_fig(section: dict):
    """Xem trước 2D 1 mặt cắt (tái dùng make_section_fig của BeamBuilder).
    Hỗ trợ nhiều khối rời (vd thân trụ 2 cột) → vẽ thêm các khối phụ."""
    outer = (section or {}).get("outer", [])
    if len(outer) < 3:
        return None
    solids = (section or {}).get("solids") or [
        {"outer": outer, "holes": section.get("holes", [])}]
    # Khung bao mọi khối để cả 2 cột đều lọt khung
    _ax = [p[0] for s in solids for p in s["outer"]]
    _az = [p[1] for s in solids for p in s["outer"]]
    xs, zs = _ax, _az
    mx = max(200.0, (max(xs) - min(xs)) * 0.08)
    mz = max(200.0, (max(zs) - min(zs)) * 0.08)
    sec = _BB_ENGINE.CrossSection("MC", list(outer),
                                  [list(h) for h in section.get("holes", [])])
    fig = _BB_ENGINE.make_section_fig(
        sec, show_grid_pts=False,
        x_range=(min(xs) - mx, max(xs) + mx),
        z_range=(min(zs) - mz, max(zs) + mz))
    # Vẽ thêm các KHỐI PHỤ (khối thứ 2 trở đi) cùng kiểu màu
    import plotly.graph_objects as _go
    for s in solids[1:]:
        _o = s.get("outer", [])
        if len(_o) < 3:
            continue
        fig.add_trace(_go.Scatter(
            x=[p[0] for p in _o] + [_o[0][0]], y=[p[1] for p in _o] + [_o[0][1]],
            fill="toself", fillcolor="rgba(100,160,200,0.20)",
            line=dict(color="#6db1d6", width=2), mode="lines",
            hoverinfo="skip", showlegend=False))
        for _h in s.get("holes", []):
            if len(_h) < 3:
                continue
            fig.add_trace(_go.Scatter(
                x=[p[0] for p in _h] + [_h[0][0]], y=[p[1] for p in _h] + [_h[0][1]],
                fill="toself", fillcolor="#0e1117",
                line=dict(color="#6db1d6", width=1), mode="lines",
                hoverinfo="skip", showlegend=False))
    # constrain="domain": giữ tỷ lệ thật của mặt cắt NHƯNG khung luôn cao 210px,
    # letterbox phần thừa → mọi ô xem trước có CÙNG KÍCH THƯỚC (lưới cân đối).
    fig.update_xaxes(constrain="domain")
    fig.update_yaxes(constrain="domain")
    fig.update_layout(height=210, margin=dict(l=40, r=10, t=10, b=30),
                      autosize=True)
    return fig


def _xamu_layers_of(part) -> list:
    """Lấy danh sách tầng xà mũ từ part (hỗ trợ định dạng cũ {section,D})."""
    part = part or {}
    if part.get("layers"):
        return [dict(l) for l in part["layers"]]
    if (part.get("section") or {}).get("outer"):
        return [{"section": part["section"], "D": float(part.get("D", 1.8) or 1.8)}]
    return []


def _render_xamu_layers(kind, part) -> dict:
    """Editor XÀ MŨ dạng LƯỚI: mỗi đoạn = [bản vẽ mặt cắt | Upload · Chiều dài ·
    Loft], 2 đoạn/hàng. Thêm đoạn tuỳ ý. Mặt cắt giữ trong store session."""
    _init = _xamu_layers_of(part)
    _store = f"_xamu_secs_{kind}"
    if _store not in st.session_state:
        st.session_state[_store] = [dict(l.get("section") or {}) for l in _init] or [{}]
    secs = st.session_state[_store]
    _n = len(secs)
    st.caption("Các đoạn nối tiếp nhau theo dọc cầu (tổng bề dày căn giữa tim trụ). "
               "Bấm **➕ Thêm đoạn** để khai bao nhiêu đoạn tuỳ ý.")

    new_layers = []
    for i in range(_n):
        cur = _init[i] if i < len(_init) else {}
        sec = dict(secs[i] or {})
        st.markdown(f"**Đoạn {i+1}**" + (" → loft" if cur.get("loft") else ""))
        _pv, _ct = st.columns([3, 2])
        with _ct:
            _up = st.file_uploader(
                "Upload mặt cắt (DXF/DWG)", type=["dxf", "dwg"],
                key=f"{kind}_dxf_xamu_L{i}")
            if _up is not None:
                _sig = f"{_up.name}:{_up.size}"
                if st.session_state.get(f"_{kind}_sig_xamu_L{i}") != _sig:
                    try:
                        _res = _BB_ENGINE.parse_dxf_bytes(_up.read())
                        if _res.get("error"):
                            st.error(f"DXF: {_res['error']}")
                        elif len(_res.get("outer", [])) >= 3:
                            sec = {"outer": _res["outer"],
                                   "holes": _res.get("holes", []),
                                   "solids": _res.get("solids")}
                            secs[i] = sec
                            st.session_state[f"_{kind}_sig_xamu_L{i}"] = _sig
                            st.success(f"✅ {len(sec['outer'])} đỉnh")
                        else:
                            st.warning("Không có biên kín.")
                    except Exception as _e:
                        st.error(f"Lỗi DXF: {_e}")
            _D = st.number_input(
                "Chiều dài (m)", 0.3, 10.0,
                float(cur.get("D", 1.8) or 1.8), 0.1,
                key=f"pp_{kind}_xamu_D_L{i}")
            _loft = False
            if i < _n - 1:
                _loft = st.checkbox(
                    "Loft (vuốt sang đoạn sau)",
                    value=bool(cur.get("loft", False)),
                    key=f"pp_{kind}_xamu_loft_L{i}",
                    help="Vuốt mượt sang mặt cắt đoạn kế.")
        with _pv:
            _f = _asm_section_fig(sec)
            if _f is not None:
                PLOT.aspect_control(_f, f"{kind}_secfig_xamu_L{i}")
                st.plotly_chart(_f, use_container_width=True,
                                key=f"{kind}_secfig_xamu_L{i}")
            else:
                st.info("Chưa có mặt cắt — upload DXF cho đoạn này.")
        new_layers.append({"section": sec, "D": float(_D), "loft": bool(_loft)})

    _a1, _a2, _ = st.columns([1, 1, 3])
    if _a1.button("➕ Thêm đoạn", key=f"addseg_{kind}_xamu",
                  use_container_width=True):
        secs.append({})
        st.rerun()
    if _n > 1 and _a2.button("🗑 Bớt đoạn cuối", key=f"rmseg_{kind}_xamu",
                             use_container_width=True):
        secs.pop()
        _j = _n - 1
        for _k in (f"{kind}_dxf_xamu_L{_j}", f"_{kind}_sig_xamu_L{_j}",
                   f"pp_{kind}_xamu_D_L{_j}", f"pp_{kind}_xamu_loft_L{_j}"):
            st.session_state.pop(_k, None)
        st.rerun()
    return {"layers": [l for l in new_layers if l is not None]}


def _render_than_layers(kind, part) -> dict:
    """Editor TƯỜNG THÂN MỐ dạng LƯỚI: mỗi đoạn = 1 MẶT CẮT DỌC cầu, xếp nối
    tiếp theo NGANG cầu; đoạn loft vuốt mượt sang mặt cắt đoạn sau. Mirror
    _render_xamu_layers nhưng đùn/loft theo trục y (ngang cầu) + có 'flex'."""
    _init = PB.abut_body_layers(part)
    _store = f"_than_secs_{kind}"
    if _store not in st.session_state:
        st.session_state[_store] = [dict(l.get("section") or {}) for l in _init] or [{}]
    secs = st.session_state[_store]
    _n = len(secs)
    st.caption("Mỗi đoạn là 1 MẶT CẮT DỌC cầu, xếp nối tiếp theo NGANG cầu "
               "(tổng bề rộng căn giữa tim cầu). Bật **Loft** để vuốt mượt sang "
               "mặt cắt đoạn kế. Bấm **➕ Thêm đoạn** để khai nhiều mặt cắt.")

    new_layers = []
    for i in range(_n):
        cur = _init[i] if i < len(_init) else {}
        sec = dict(secs[i] or {})
        st.markdown(f"**Đoạn {i+1}**" + (" → loft" if cur.get("loft") else ""))
        _pv, _ct = st.columns([3, 2])
        with _ct:
            _up = st.file_uploader(
                "Upload mặt cắt dọc (DXF/DWG)", type=["dxf", "dwg"],
                key=f"{kind}_dxf_than_L{i}")
            if _up is not None:
                _sig = f"{_up.name}:{_up.size}"
                if st.session_state.get(f"_{kind}_sig_than_L{i}") != _sig:
                    try:
                        _res = _BB_ENGINE.parse_dxf_bytes(_up.read())
                        if _res.get("error"):
                            st.error(f"DXF: {_res['error']}")
                        elif len(_res.get("outer", [])) >= 3:
                            sec = {"outer": _res["outer"],
                                   "holes": _res.get("holes", []),
                                   "solids": _res.get("solids")}
                            secs[i] = sec
                            st.session_state[f"_{kind}_sig_than_L{i}"] = _sig
                            st.success(f"✅ {len(sec['outer'])} đỉnh")
                        else:
                            st.warning("Không có biên kín.")
                    except Exception as _e:
                        st.error(f"Lỗi DXF: {_e}")
            _B = st.number_input(
                "Bề rộng ngang cầu (m)", 0.3, 40.0,
                float(cur.get("B", 8.0) or 8.0), 0.1,
                key=f"pp_{kind}_than_B_L{i}")
            _loft = False
            if i < _n - 1:
                _loft = st.checkbox(
                    "Loft (vuốt sang đoạn sau)",
                    value=bool(cur.get("loft", False)),
                    key=f"pp_{kind}_than_loft_L{i}",
                    help="Vuốt mượt sang mặt cắt đoạn kế.")
        with _pv:
            _f = _asm_section_fig(sec)
            if _f is not None:
                PLOT.aspect_control(_f, f"{kind}_secfig_than_L{i}")
                st.plotly_chart(_f, use_container_width=True,
                                key=f"{kind}_secfig_than_L{i}")
            else:
                st.info("Chưa có mặt cắt — upload DXF cho đoạn này.")
        new_layers.append({"section": sec, "B": float(_B), "loft": bool(_loft)})

    _a1, _a2, _ = st.columns([1, 1, 3])
    if _a1.button("➕ Thêm đoạn", key=f"addseg_{kind}_than",
                  use_container_width=True):
        secs.append({})
        st.rerun()
    if _n > 1 and _a2.button("🗑 Bớt đoạn cuối", key=f"rmseg_{kind}_than",
                             use_container_width=True):
        secs.pop()
        _j = _n - 1
        for _k in (f"{kind}_dxf_than_L{_j}", f"_{kind}_sig_than_L{_j}",
                   f"pp_{kind}_than_B_L{_j}", f"pp_{kind}_than_loft_L{_j}"):
            st.session_state.pop(_k, None)
        st.rerun()
    _flex = st.checkbox("Co theo chiều cao (khi gắn cầu)",
                        value=bool(part.get("flex", True)),
                        key=f"pp_{kind}_than_flex")
    return {"layers": [l for l in new_layers if l is not None], "flex": bool(_flex)}


def _render_asm_part_editor(kind, spec, part) -> dict:
    """Khối UI 1 bộ phận: upload DXF + xem trước 2D + tham số đùn. Trả part mới."""
    role = spec["role"]; label = spec["label"]
    st.caption(spec["hint"])
    if role == "xa_mu":
        return _render_xamu_layers(kind, part)
    if kind == "mo" and role == "than":
        return _render_than_layers(kind, part)
    part = dict(part or {})
    sec = dict(part.get("section") or {})

    _up = st.file_uploader(f"⬆ Upload mặt cắt {label} (DXF/DWG)",
                           type=["dxf", "dwg"], key=f"{kind}_dxf_{role}")
    if _up is not None:
        _sig = f"{_up.name}:{_up.size}"
        if st.session_state.get(f"_{kind}_sig_{role}") != _sig:
            try:
                _res = _BB_ENGINE.parse_dxf_bytes(_up.read())
                if _res.get("error"):
                    st.error(f"Lỗi đọc DXF: {_res['error']}")
                elif len(_res.get("outer", [])) >= 3:
                    sec = {"outer": _res["outer"], "holes": _res.get("holes", []),
                           "solids": _res.get("solids")}
                    st.session_state[f"_{kind}_sig_{role}"] = _sig
                    st.success(f"✅ Đã nạp mặt cắt {label}: {len(sec['outer'])} đỉnh"
                               f"{', ' + str(len(sec['holes'])) + ' lỗ' if sec['holes'] else ''}.")
                else:
                    st.warning("Không tìm thấy biên kín trong DXF.")
            except Exception as _e:
                st.error(f"Lỗi xử lý DXF: {_e}")
    part["section"] = sec

    _pv, _pp = st.columns([3, 2])
    with _pv:
        _f = _asm_section_fig(sec)
        if _f is not None:
            PLOT.aspect_control(_f, f"{kind}_secfig_{role}")
            st.plotly_chart(_f, use_container_width=True, key=f"{kind}_secfig_{role}")
        else:
            st.info("Chưa có mặt cắt — upload DXF để bắt đầu.")
    with _pp:
        _pm = spec["param"]
        part[_pm] = st.number_input(
            spec["plabel"], spec["pmin"], spec["pmax"],
            float(part.get(_pm, spec["pdef"])), 0.1,
            key=f"pp_{kind}_{role}_{_pm}")
        if spec.get("flex"):
            part["flex"] = st.checkbox(
                "Co theo chiều cao (khi gắn cầu)",
                value=bool(part.get("flex", True)), key=f"pp_{kind}_than_flex")
    return part


def _render_asm_edit_panel(cfg: dict) -> None:
    """Panel tạo/sửa 1 cấu kiện lắp ghép (trụ hoặc mố)."""
    kind = cfg["kind"]; lab = cfg["label"]; labels = _asm_labels(cfg)
    editing_id = st.session_state.get(f"_lib_{kind}_editing_id")
    cur = cfg["migrate"](st.session_state.get(f"_lib_{kind}_draft") or cfg["default"]())
    parts = dict(cur.get("parts", {}))

    st.markdown(
        f"<div style='background:#0a1f35;border:1px solid #007acc;border-radius:8px;"
        f"padding:8px 12px;margin:6px 0'><b style='color:#4fc3f7'>"
        f"{'✏️ Sửa ' + lab.lower() if editing_id else '➕ Tạo ' + lab.lower() + ' mới'}"
        f"</b> — mỗi bộ phận upload MẶT CẮT riêng để dựng khối, rồi 💾 Lưu.</div>",
        unsafe_allow_html=True)

    _nm = st.text_input(f"Tên {lab.lower()}", value=cur.get("ten", ""),
                        placeholder=cfg["name_ph"], key=f"_lib_{kind}_name")

    # Khai báo mặt cắt từng bộ phận (full-width, hình mặt cắt nhỏ gọn)
    _ptabs = st.tabs([f"🧱 {pt['label']}" for pt in cfg["parts"]])
    for _tab, spec in zip(_ptabs, cfg["parts"]):
        with _tab:
            parts[spec["role"]] = _render_asm_part_editor(
                kind, spec, parts.get(spec["role"], {}))

    rec = {"id": editing_id or "", "ten": _nm, "loai": kind, "parts": parts}
    rec["H_ref"] = cfg["total_h"](rec)
    st.session_state[f"_lib_{kind}_draft"] = rec

    # Xem trước 3D — HÀNG RIÊNG DƯỚI CÙNG, full-width cho to & dễ xoay
    st.markdown("---")
    st.markdown(f"**🧊 Xem trước 3D** — kéo xoay · cao ≈ {rec['H_ref']} m")
    try:
        st.plotly_chart(PLOT.to_concrete_3d(cfg["preview"](rec, labels=labels)),
                        use_container_width=True, key=f"{kind}_prev3d")
    except Exception as _e:
        st.error(f"Lỗi xem trước 3D: {_e}")

    st.markdown("---")
    _p1, _p2, _ = st.columns([1, 1, 3])
    if _p1.button(f"💾 Lưu {lab.lower()}", type="primary",
                  use_container_width=True, key=f"_lib_{kind}_save"):
        if not _nm.strip():
            st.warning(f"⚠️ Nhập **tên {lab.lower()}** trước khi lưu.")
        else:
            items = st.session_state.get(cfg["ss"], cfg["load"]())
            rid = editing_id or cfg["mkid"](_nm, items)
            rec["id"] = rid
            rec["created_by"] = (AUTH.current_user() or {}).get("name", "")
            rec["updated_at"] = time.strftime("%Y-%m-%d %H:%M")
            st.session_state[cfg["ss"]] = cfg["upsert"](items, rec)
            cfg["save"](st.session_state[cfg["ss"]])
            for _s in ("panel", "editing_id", "draft"):
                st.session_state.pop(f"_lib_{kind}_{_s}", None)
            st.toast(f"Đã lưu {lab.lower()} “{_nm}”.", icon="✅")
            st.rerun()
    if _p2.button("Hủy", use_container_width=True, key=f"_lib_{kind}_cancel"):
        for _s in ("panel", "editing_id", "draft"):
            st.session_state.pop(f"_lib_{kind}_{_s}", None)
        st.rerun()


# Một số TRỤ ĐIỂN HÌNH mặc định — ghép sẵn từ 3 bộ phận trong thư viện.
_PIER_PRESETS = [
    {"ten": "Trụ thân đặc tròn", "cap_id": "xm-i-tng",
     "stem_id": "than-dac-tron", "footing_id": "be-vuong"},
    {"ten": "Trụ 2 cột lục giác", "cap_id": "xm-2-phia-spt",
     "stem_id": "than-2-lucgiac", "footing_id": "be-vuong"},
    {"ten": "Trụ thân vuông đổi tiết diện",
     "cap_id": "xm-cung-dam-i-i-tng-tng-cao-1-5",
     "stem_id": "than-dac-vuong-thay-doi-tiet-dien", "footing_id": "be-vuong"},
]


def _pier_part_libs():
    """Nạp & cache 3 thư viện bộ phận trụ (caps/stems/footings)."""
    if st.session_state.get("lib_caps") is None:
        st.session_state["lib_caps"] = CLIB.load_caps()
    if st.session_state.get("lib_stems") is None:
        st.session_state["lib_stems"] = CLIB.load_stems()
    if st.session_state.get("lib_footings") is None:
        st.session_state["lib_footings"] = CLIB.load_footings()
    return (st.session_state["lib_caps"], st.session_state["lib_stems"],
            st.session_state["lib_footings"])


def _current_pier_parts():
    """Lựa chọn trụ HIỆN TẠI — đọc TRỰC TIẾP từ session_state của widget picker.

    Nhờ vậy mọi bản vẽ (kể cả vẽ TRƯỚC picker trong cùng 1 lần chạy) đều thấy
    lựa chọn mới ngay → KHÔNG cần st.rerun() (tránh vòng lặp cập nhật / lag)."""
    caps, stems, foots = _pier_part_libs()
    if not (caps or stems or foots):
        return None
    _custom = "🔧 Tùy chỉnh bộ phận…"
    sel = st.session_state.get("tru_preset_sel")
    if sel and sel != _custom:
        for p in _PIER_PRESETS:
            if p["ten"] == sel:
                return {"ten": p["ten"], "cap_id": p["cap_id"],
                        "stem_id": p["stem_id"], "footing_id": p["footing_id"]}
    if sel == _custom:
        def _id(key, items):
            v = st.session_state.get(key)
            if not v or v == "(không)":
                return None
            return next((it.get("id") for it in items if it.get("ten") == v), None)
        return {"ten": "Trụ tùy chỉnh", "cap_id": _id("tru_cap_sel", caps),
                "stem_id": _id("tru_stem_sel", stems),
                "footing_id": _id("tru_footing_sel", foots)}
    p = _PIER_PRESETS[0]                       # chưa render picker → preset đầu
    return {"ten": p["ten"], "cap_id": p["cap_id"],
            "stem_id": p["stem_id"], "footing_id": p["footing_id"]}


def _resolve_assembly(d, kind: str) -> dict:
    """Bản ghi trụ/mố lắp ghép đang gán cho cầu (None nếu dùng mặc định)."""
    cfg = _asm_cfg(kind)
    if kind == "tru":
        pp = _current_pier_parts()
        if pp and (pp.get("cap_id") or pp.get("stem_id") or pp.get("footing_id")):
            caps, stems, foots = _pier_part_libs()
            cap  = CLIB.get_cap(caps, pp.get("cap_id"))
            stem = CLIB.get_stem(stems, pp.get("stem_id"))
            foot = CLIB.get_footing(foots, pp.get("footing_id"))
            if cap or stem or foot:
                return PB.build_pier_from_parts(cap, stem, foot,
                                                ten=pp.get("ten", "Trụ lắp ghép"))
    rid = (d or {}).get(cfg["id_key"])
    if not rid:
        return None
    items = st.session_state.get(cfg["ss"]) or cfg["load"]()
    return cfg["get"](items, rid)


def _pier_parts_label(pp, caps, stems, foots) -> str:
    """Tóm tắt tên 3 bộ phận của 1 cấu hình trụ lắp ghép."""
    _c = CLIB.get_cap(caps, pp.get("cap_id")) if pp else None
    _s = CLIB.get_stem(stems, pp.get("stem_id")) if pp else None
    _f = CLIB.get_footing(foots, pp.get("footing_id")) if pp else None
    return (f"🧢 {(_c or {}).get('ten','—')} · "
            f"🏛️ {(_s or {}).get('ten','—')} · "
            f"🟫 {(_f or {}).get('ten','—')}")


def _pier_assembler(d) -> None:
    """Chọn 1 TRỤ điển hình có sẵn, hoặc tự ghép từ 3 bộ phận (xà mũ/thân/bệ).
    Khi gắn vào cầu: xà mũ tự co bề rộng theo cầu, thân tự co chiều cao tĩnh không."""
    caps, stems, foots = _pier_part_libs()
    if not (caps or stems or foots):
        st.caption("🏗️ Chưa có bộ phận trụ — dựng **Xà mũ / Thân / Bệ** ở "
                   "**THƯ VIỆN → Trụ** rồi quay lại đây để lắp vào cầu.")
        d["pier_parts"] = None
        return
    _opts = [p["ten"] for p in _PIER_PRESETS] + ["🔧 Tùy chỉnh bộ phận…"]
    cur = d.get("pier_parts") or {}
    _idx = 0
    for i, p in enumerate(_PIER_PRESETS):
        if (cur.get("cap_id") == p["cap_id"] and cur.get("stem_id") == p["stem_id"]
                and cur.get("footing_id") == p["footing_id"]):
            _idx = i
            break
    else:
        _idx = len(_PIER_PRESETS) if cur else 0
    _sel = st.selectbox(
        "🏗️ Trụ áp dụng cho cầu", _opts, index=_idx, key="tru_preset_sel",
        help="Chọn 1 trụ điển hình có sẵn, hoặc 'Tùy chỉnh' để ghép từng bộ phận. "
             "Khi gắn vào cầu, xà mũ tự co bề rộng theo cầu, thân tự co chiều cao.")
    if _sel != _opts[-1]:
        p = _PIER_PRESETS[_opts.index(_sel)]
        st.caption(_pier_parts_label(
            {"cap_id": p["cap_id"], "stem_id": p["stem_id"],
             "footing_id": p["footing_id"]}, caps, stems, foots))
    else:
        def _pick(label, items, key, cur_id):
            _o = ["(không)"] + [it.get("ten", "(?)") for it in items]
            _i = next((k + 1 for k, it in enumerate(items)
                       if it.get("id") == cur_id), 0)
            st.selectbox(label, _o, index=_i, key=key)
        _c1, _c2, _c3 = st.columns(3)
        with _c1:
            _pick("🧢 Xà mũ", caps, "tru_cap_sel", cur.get("cap_id"))
        with _c2:
            _pick("🏛️ Thân trụ", stems, "tru_stem_sel", cur.get("stem_id"))
        with _c3:
            _pick("🟫 Bệ trụ", foots, "tru_footing_sel", cur.get("footing_id"))
    # Nguồn sự thật là widget state (đọc qua _current_pier_parts) → KHÔNG rerun.
    d["pier_parts"] = _current_pier_parts()



def _assembly_picker(d, kind: str) -> None:
    """Selectbox chọn trụ/mố lắp ghép áp dụng cho cầu (lưu d[id_key])."""
    if kind == "tru":
        _pier_assembler(d)
        return
    cfg = _asm_cfg(kind); lab = cfg["label"]
    items = st.session_state.get(cfg["ss"])
    if items is None:
        items = st.session_state[cfg["ss"]] = cfg["load"]()
    if not items:
        st.caption(f"{cfg['icon']} Chưa có {lab.lower()} trong Thư viện — tạo ở "
                   f"**THƯ VIỆN → {lab}** rồi quay lại đây để gắn vào cầu.")
        d[cfg["id_key"]] = None
        return
    _opts = [f"({lab} mặc định)"] + [p.get("ten", "(không tên)") for p in items]
    _cur = d.get(cfg["id_key"])
    _idx = next((k + 1 for k, p in enumerate(items) if p.get("id") == _cur), 0)
    _sel = st.selectbox(
        f"{cfg['icon']} {lab} lắp ghép áp dụng cho cầu", _opts, index=_idx,
        key=f"{kind}_assembly_sel",
        help=f"Thay hình {lab.lower()} mặc định trong trắc dọc & 3D bằng {lab.lower()} "
             f"đã dựng trong Thư viện (tự co chiều cao theo cao độ đáy dầm).")
    d[cfg["id_key"]] = (None if _sel == _opts[0]
                        else items[_opts.index(_sel) - 1].get("id"))


# ══════════════════════════════════════════════════════════════════════════
# 3 THƯ VIỆN BỘ PHẬN TRỤ ĐỘC LẬP: Xà mũ (loft) · Thân trụ · Bệ trụ
# ══════════════════════════════════════════════════════════════════════════
_SIMPLE_PART_CFG = {
    "stem": {"ss": "lib_stems", "icon": "🏛️", "label": "Thân trụ", "color": "#5d8aa8",
             "load": "load_stems", "save": "save_stems", "upsert": "upsert_stem",
             "delete": "delete_stem", "get": "get_stem", "mkid": "make_stem_id",
             "layered": True,
             "hint": "Mặt cắt = MẶT BẰNG (ngang × dọc cầu). Thêm nhiều tầng xếp "
                     "THEO PHƯƠNG ĐỨNG, có thể loft vuốt giữa các tầng."},
    "footing": {"ss": "lib_footings", "icon": "🟫", "label": "Bệ trụ", "color": "#7f8c9b",
                "load": "load_footings", "save": "save_footings", "upsert": "upsert_footing",
                "delete": "delete_footing", "get": "get_footing", "mkid": "make_footing_id",
                "layered": True,
                "hint": "Mặt cắt = MẶT BẰNG (ngang × dọc cầu). Thêm nhiều tầng xếp "
                        "THEO PHƯƠNG ĐỨNG (bệ giật cấp), có thể loft giữa các tầng."},
}


def _clear_cap_widgets():
    for i in range(16):
        for k in (f"cap_dxf_xamu_L{i}", f"_cap_sig_xamu_L{i}",
                  f"pp_cap_xamu_D_L{i}", f"pp_cap_xamu_loft_L{i}"):
            st.session_state.pop(k, None)
    st.session_state.pop("_xamu_secs_cap", None)   # store mặt cắt theo đoạn
    st.session_state.pop("_cap_name", None)


def render_cap_library():
    """Thư viện XÀ MŨ — nhiều đoạn mặt cắt xếp dọc cầu, có loft (giống tạo dầm)."""
    if "lib_caps" not in st.session_state:
        st.session_state.lib_caps = CLIB.load_caps()
    caps = st.session_state.lib_caps
    if st.session_state.get("_cap_panel"):
        _render_cap_edit_panel()
        return
    _h1, _h2 = st.columns([3, 1])
    with _h1:
        st.markdown("##### 🧢 Xà mũ (đùn dọc cầu · có loft)")
        st.caption("Mỗi xà mũ = 1–3 đoạn mặt cắt ngang xếp **dọc cầu**; đoạn loft "
                   "vuốt mượt sang đoạn sau. Lắp vào cầu ở **Bố trí chung**.")
    with _h2:
        if st.button("➕ Tạo xà mũ mới", type="primary", use_container_width=True,
                     key="cap_new"):
            _clear_cap_widgets()
            st.session_state["_cap_draft"] = {"ten": "", "layers": []}
            st.session_state.pop("_cap_edit_id", None)
            st.session_state["_cap_panel"] = "new"
            st.rerun()
    if not caps:
        st.info("Chưa có xà mũ nào. Bấm **➕ Tạo xà mũ mới**.")
        return
    for c in sorted(caps, key=lambda x: str(x.get("ten", "")).lower()):
        _lays = c.get("layers", [])
        _info, _e, _del = st.columns([8, 1, 1])
        _info.markdown(
            f"<div style='background:#141420;border:1px solid #2a2a3a;"
            f"border-left:4px solid #6d9dc5;border-radius:8px;padding:8px 12px'>"
            f"<span style='font-size:14px;font-weight:600;color:#f0f0f0'>🧢 "
            f"{c.get('ten','(không tên)')}</span>"
            f"<span style='font-size:11px;color:#888;margin-left:10px'>"
            f"{len(_lays)} đoạn · dày "
            f"{'/'.join(str(l.get('D','?')) for l in _lays)}m</span></div>",
            unsafe_allow_html=True)
        if _e.button("✏️", key=f"cap_edit_{c['id']}", use_container_width=True):
            _clear_cap_widgets()
            st.session_state["_cap_draft"] = dict(c)
            st.session_state["_cap_edit_id"] = c["id"]
            st.session_state["_cap_panel"] = c["id"]
            st.rerun()
        if _del.button("🗑️", key=f"cap_del_{c['id']}", use_container_width=True):
            st.session_state.lib_caps = CLIB.delete_cap(caps, c["id"])
            CLIB.save_caps(st.session_state.lib_caps)
            st.rerun()


def _render_cap_edit_panel():
    eid = st.session_state.get("_cap_edit_id")
    draft = st.session_state.get("_cap_draft") or {"ten": "", "layers": []}
    st.markdown(
        f"<div style='background:#0a1f35;border:1px solid #007acc;border-radius:8px;"
        f"padding:8px 12px;margin:6px 0'><b style='color:#4fc3f7'>"
        f"{'✏️ Sửa xà mũ' if eid else '➕ Tạo xà mũ mới'}</b> — khai báo đoạn mặt cắt "
        f"dọc cầu (có loft), rồi 💾 Lưu.</div>", unsafe_allow_html=True)
    _ten = st.text_input("Tên xà mũ", value=draft.get("ten", ""), key="_cap_name",
                         placeholder="VD: Xà mũ trụ T 2 đoạn")
    _part = _render_xamu_layers("cap", {"layers": draft.get("layers", [])})
    _layers = _part["layers"]
    st.session_state["_cap_draft"] = {"ten": _ten, "layers": _layers}

    st.markdown("---")
    st.markdown("**🧊 Xem trước 3D xà mũ** (độc lập · kéo xoay)")
    try:
        st.plotly_chart(PLOT.to_concrete_3d(PB.build_cap_part_fig(_layers)),
                        use_container_width=True, key="cap_prev3d")
    except Exception as _e:
        st.error(f"Lỗi xem trước 3D: {_e}")

    _s1, _s2, _ = st.columns([1, 1, 3])
    if _s1.button("💾 Lưu xà mũ", type="primary", use_container_width=True,
                  key="cap_save"):
        if not _ten.strip():
            st.warning("⚠️ Nhập **tên xà mũ**.")
        elif not any((l.get("section") or {}).get("outer") for l in _layers):
            st.warning("⚠️ Cần ít nhất 1 đoạn có mặt cắt (upload DXF).")
        else:
            caps = st.session_state.get("lib_caps", CLIB.load_caps())
            rid = eid or CLIB.make_cap_id(_ten, caps)
            rec = {"id": rid, "ten": _ten.strip(), "layers": _layers,
                   "created_by": (AUTH.current_user() or {}).get("name", ""),
                   "updated_at": time.strftime("%Y-%m-%d %H:%M")}
            st.session_state.lib_caps = CLIB.upsert_cap(caps, rec)
            CLIB.save_caps(st.session_state.lib_caps)
            for _k in ("_cap_panel", "_cap_edit_id", "_cap_draft"):
                st.session_state.pop(_k, None)
            st.toast(f"Đã lưu xà mũ “{_ten}”.", icon="✅")
            st.rerun()
    if _s2.button("Hủy", use_container_width=True, key="cap_cancel"):
        for _k in ("_cap_panel", "_cap_edit_id", "_cap_draft"):
            st.session_state.pop(_k, None)
        st.rerun()


def _clear_part_widgets(kind: str) -> None:
    """Xoá widget state + store mặt cắt của panel thân/bệ trước khi mở mới/sửa."""
    for _k in (f"{kind}_dxf_part", f"_{kind}_sig_part",
               f"pp_{kind}_H", f"_{kind}_name", f"_stem_secs_{kind}"):
        st.session_state.pop(_k, None)
    for i in range(24):                 # các tầng thân trụ (layered)
        for _k in (f"{kind}_dxf_stem_L{i}", f"_{kind}_sig_stem_L{i}",
                   f"pp_{kind}_stem_H_L{i}", f"pp_{kind}_stem_loft_L{i}"):
            st.session_state.pop(_k, None)


def render_simple_part_library(kind: str):
    """Thư viện THÂN TRỤ (nhiều tầng + loft) / BỆ TRỤ (1 mặt cắt), 3D độc lập."""
    cfg = _SIMPLE_PART_CFG[kind]
    ss = cfg["ss"]
    _load = getattr(CLIB, cfg["load"])
    if ss not in st.session_state:
        st.session_state[ss] = _load()
    items = st.session_state[ss]
    if st.session_state.get(f"_{kind}_panel"):
        _render_simple_part_panel(kind, cfg)
        return
    _h1, _h2 = st.columns([3, 1])
    with _h1:
        st.markdown(f"##### {cfg['icon']} {cfg['label']}")
        st.caption(cfg["hint"] + " Lắp vào cầu ở **Bố trí chung**.")
    with _h2:
        if st.button(f"➕ Tạo {cfg['label'].lower()} mới", type="primary",
                     use_container_width=True, key=f"{kind}_new"):
            st.session_state[f"_{kind}_draft"] = {"ten": "", "section": {}, "H": 5.0}
            st.session_state.pop(f"_{kind}_edit_id", None)
            _clear_part_widgets(kind)
            st.session_state[f"_{kind}_panel"] = "new"
            st.rerun()
    if not items:
        st.info(f"Chưa có {cfg['label'].lower()} nào.")
        return
    for it in sorted(items, key=lambda x: str(x.get("ten", "")).lower()):
        _info, _e, _del = st.columns([8, 1, 1])
        if cfg.get("layered"):
            _nl = len(PB.stem_layers_of(it))
            _meta = (f"{_nl} tầng · cao {PB.stem_total_height(it):.2f}m"
                     if _nl else "chưa có mặt cắt")
        else:
            _meta = f"H={it.get('H','?')}m"
        _info.markdown(
            f"<div style='background:#141420;border:1px solid #2a2a3a;"
            f"border-left:4px solid {cfg['color']};border-radius:8px;padding:8px 12px'>"
            f"<span style='font-size:14px;font-weight:600;color:#f0f0f0'>"
            f"{cfg['icon']} {it.get('ten','(không tên)')}</span>"
            f"<span style='font-size:11px;color:#888;margin-left:10px'>"
            f"{_meta}</span></div>", unsafe_allow_html=True)
        if _e.button("✏️", key=f"{kind}_edit_{it['id']}", use_container_width=True):
            st.session_state[f"_{kind}_draft"] = dict(it)
            st.session_state[f"_{kind}_edit_id"] = it["id"]
            _clear_part_widgets(kind)
            st.session_state[f"_{kind}_panel"] = it["id"]
            st.rerun()
        if _del.button("🗑️", key=f"{kind}_del_{it['id']}", use_container_width=True):
            st.session_state[ss] = getattr(CLIB, cfg["delete"])(items, it["id"])
            getattr(CLIB, cfg["save"])(st.session_state[ss])
            st.rerun()


def _render_stem_layers(kind: str, draft: dict) -> list:
    """Editor THÂN TRỤ nhiều tầng theo PHƯƠNG ĐỨNG: mỗi tầng = [bản vẽ mặt cắt |
    Upload · Chiều cao · Loft]. Mỗi tầng 1 hàng. Trả về list layers."""
    _init = PB.stem_layers_of(draft)
    _store = f"_stem_secs_{kind}"
    if _store not in st.session_state:
        st.session_state[_store] = [dict(l.get("section") or {}) for l in _init] or [{}]
    secs = st.session_state[_store]
    _n = len(secs)
    st.caption("Các tầng xếp chồng **theo phương đứng** (từ đáy lên đỉnh). "
               "Bấm **➕ Thêm tầng** để khai báo bao nhiêu tầng tuỳ ý; bật **Loft** "
               "để vuốt mượt từ tầng dưới lên tầng trên.")
    new_layers = []
    for i in range(_n):
        cur = _init[i] if i < len(_init) else {}
        sec = dict(secs[i] or {})
        st.markdown(f"**Tầng {i+1}** (từ đáy)" + (" → loft" if cur.get("loft") else ""))
        _pv, _ct = st.columns([3, 2])
        with _ct:
            _up = st.file_uploader(
                "Upload mặt cắt mặt bằng (DXF/DWG)", type=["dxf", "dwg"],
                key=f"{kind}_dxf_stem_L{i}")
            if _up is not None:
                _sig = f"{_up.name}:{_up.size}"
                if st.session_state.get(f"_{kind}_sig_stem_L{i}") != _sig:
                    try:
                        _res = _BB_ENGINE.parse_dxf_bytes(_up.read())
                        if _res.get("error"):
                            st.error(f"DXF: {_res['error']}")
                        elif len(_res.get("outer", [])) >= 3:
                            sec = {"outer": _res["outer"],
                                   "holes": _res.get("holes", []),
                                   "solids": _res.get("solids")}
                            secs[i] = sec
                            st.session_state[f"_{kind}_sig_stem_L{i}"] = _sig
                            _ns = _res.get("n_solids", 1)
                            st.success(f"✅ {len(sec['outer'])} đỉnh"
                                       + (f" · {_ns} khối" if _ns > 1 else ""))
                        else:
                            st.warning("Không có biên kín.")
                    except Exception as _e:
                        st.error(f"Lỗi DXF: {_e}")
            _H = st.number_input(
                "Chiều cao tầng (m)", 0.2, 40.0,
                float(cur.get("H", 3.0) or 3.0), 0.1,
                key=f"pp_{kind}_stem_H_L{i}")
            _loft = False
            if i < _n - 1:
                _loft = st.checkbox(
                    "Loft (vuốt lên tầng trên)",
                    value=bool(cur.get("loft", False)),
                    key=f"pp_{kind}_stem_loft_L{i}",
                    help="Vuốt mượt từ mặt cắt tầng này lên mặt cắt tầng kế trên.")
        with _pv:
            _f = _asm_section_fig(sec)
            if _f is not None:
                PLOT.aspect_control(_f, f"{kind}_secfig_stem_L{i}")
                st.plotly_chart(_f, use_container_width=True,
                                key=f"{kind}_secfig_stem_L{i}")
            else:
                st.info("Chưa có mặt cắt — upload DXF cho tầng này.")
        new_layers.append({"section": sec, "H": float(_H), "loft": bool(_loft)})

    _a1, _a2, _ = st.columns([1, 1, 3])
    if _a1.button("➕ Thêm tầng", key=f"addseg_{kind}_stem",
                  use_container_width=True):
        secs.append({})
        st.rerun()
    if _n > 1 and _a2.button("🗑 Bớt tầng trên", key=f"rmseg_{kind}_stem",
                             use_container_width=True):
        secs.pop()
        _j = _n - 1
        for _k in (f"{kind}_dxf_stem_L{_j}", f"_{kind}_sig_stem_L{_j}",
                   f"pp_{kind}_stem_H_L{_j}", f"pp_{kind}_stem_loft_L{_j}"):
            st.session_state.pop(_k, None)
        st.rerun()
    return [l for l in new_layers if (l.get("section") or {}).get("outer")]


def _render_stem_panel(kind: str, cfg: dict):
    """Panel THÂN TRỤ nhiều tầng đứng + loft (3D độc lập)."""
    eid = st.session_state.get(f"_{kind}_edit_id")
    draft = st.session_state.get(f"_{kind}_draft") or {}
    st.markdown(
        f"<div style='background:#0a1f35;border:1px solid #007acc;border-radius:8px;"
        f"padding:8px 12px;margin:6px 0'><b style='color:#4fc3f7'>"
        f"{'✏️ Sửa ' if eid else '➕ Tạo '}{cfg['label'].lower()}</b> — nhiều tầng "
        f"mặt cắt xếp đứng, có loft, rồi 💾 Lưu.</div>", unsafe_allow_html=True)
    _ten = st.text_input(f"Tên {cfg['label'].lower()}", value=draft.get("ten", ""),
                         key=f"_{kind}_name")
    st.caption(cfg["hint"])

    layers = _render_stem_layers(kind, draft)
    # Giữ qua rerun (bấm Lưu là rerun mới)
    _dr = dict(draft); _dr["layers"] = layers
    _dr.pop("section", None); _dr.pop("H", None)
    st.session_state[f"_{kind}_draft"] = _dr

    st.markdown("---")
    _Htot = PB.stem_total_height(layers)
    st.markdown(f"**🧊 Xem trước 3D {cfg['label'].lower()}** (độc lập · cao ≈ "
                f"{_Htot:.2f} m)")
    try:
        st.plotly_chart(
            PLOT.to_concrete_3d(
                PB.build_stem_part_fig(layers, color=cfg["color"], name=cfg["label"])),
            use_container_width=True, key=f"{kind}_prev3d")
    except Exception as _e:
        st.error(f"Lỗi 3D: {_e}")

    _s1, _s2, _ = st.columns([1, 1, 3])
    if _s1.button(f"💾 Lưu {cfg['label'].lower()}", type="primary",
                  use_container_width=True, key=f"{kind}_save"):
        if not _ten.strip():
            st.warning(f"⚠️ Nhập **tên {cfg['label'].lower()}**.")
        elif not layers:
            st.warning("⚠️ Cần ít nhất 1 tầng có mặt cắt.")
        else:
            items = st.session_state.get(cfg["ss"], getattr(CLIB, cfg["load"])())
            rid = eid or getattr(CLIB, cfg["mkid"])(_ten, items)
            rec = {"id": rid, "ten": _ten.strip(), "layers": layers,
                   "H": float(_Htot),
                   "created_by": (AUTH.current_user() or {}).get("name", ""),
                   "updated_at": time.strftime("%Y-%m-%d %H:%M")}
            st.session_state[cfg["ss"]] = getattr(CLIB, cfg["upsert"])(items, rec)
            getattr(CLIB, cfg["save"])(st.session_state[cfg["ss"]])
            for _k in (f"_{kind}_panel", f"_{kind}_edit_id", f"_{kind}_draft",
                       f"_stem_secs_{kind}"):
                st.session_state.pop(_k, None)
            st.toast(f"Đã lưu {cfg['label'].lower()} “{_ten}”.", icon="✅")
            st.rerun()
    if _s2.button("Hủy", use_container_width=True, key=f"{kind}_cancel"):
        for _k in (f"_{kind}_panel", f"_{kind}_edit_id", f"_{kind}_draft",
                   f"_stem_secs_{kind}"):
            st.session_state.pop(_k, None)
        st.rerun()


def _render_simple_part_panel(kind: str, cfg: dict):
    if cfg.get("layered"):
        _render_stem_panel(kind, cfg)
        return
    eid = st.session_state.get(f"_{kind}_edit_id")
    draft = st.session_state.get(f"_{kind}_draft") or {}
    st.markdown(
        f"<div style='background:#0a1f35;border:1px solid #007acc;border-radius:8px;"
        f"padding:8px 12px;margin:6px 0'><b style='color:#4fc3f7'>"
        f"{'✏️ Sửa ' if eid else '➕ Tạo '}{cfg['label'].lower()}</b> — upload mặt cắt "
        f"mặt bằng + chiều cao, rồi 💾 Lưu.</div>", unsafe_allow_html=True)
    _ten = st.text_input(f"Tên {cfg['label'].lower()}", value=draft.get("ten", ""),
                         key=f"_{kind}_name")
    st.caption(cfg["hint"])
    sec = dict(draft.get("section") or {})
    _up = st.file_uploader(f"⬆ Upload mặt cắt {cfg['label'].lower()} (DXF/DWG)",
                           type=["dxf", "dwg"], key=f"{kind}_dxf_part")
    if _up is not None:
        _sig = f"{_up.name}:{_up.size}"
        if st.session_state.get(f"_{kind}_sig_part") != _sig:
            try:
                _res = _BB_ENGINE.parse_dxf_bytes(_up.read())
                if _res.get("error"):
                    st.error(f"Lỗi đọc DXF: {_res['error']}")
                elif len(_res.get("outer", [])) >= 3:
                    sec = {"outer": _res["outer"], "holes": _res.get("holes", []),
                           "solids": _res.get("solids")}
                    st.session_state[f"_{kind}_sig_part"] = _sig
                    # GIỮ qua rerun: bấm Lưu là 1 rerun mới, uploader giữ file
                    # nhưng sig không đổi → khối parse bị bỏ qua. Lưu vào draft.
                    _dr = dict(st.session_state.get(f"_{kind}_draft") or {})
                    _dr["section"] = sec
                    st.session_state[f"_{kind}_draft"] = _dr
                    _ns = _res.get("n_solids", 1)
                    st.success(f"✅ Đã nạp: {len(sec['outer'])} đỉnh"
                               + (f" · {_ns} khối." if _ns > 1 else "."))
                else:
                    st.warning("Không tìm thấy biên kín trong DXF.")
            except Exception as _e:
                st.error(f"Lỗi xử lý DXF: {_e}")
    _c1, _c2 = st.columns([3, 2])
    with _c1:
        _f = _asm_section_fig(sec)
        if _f is not None:
            PLOT.aspect_control(_f, f"{kind}_secfig_part")
            st.plotly_chart(_f, use_container_width=True, key=f"{kind}_secfig_part")
        else:
            st.info("Chưa có mặt cắt — upload DXF.")
    with _c2:
        _H = st.number_input("Chiều cao H (m)", 0.3, 60.0,
                             float(draft.get("H", 5.0) or 5.0), 0.1,
                             key=f"pp_{kind}_H")

    st.markdown("---")
    st.markdown(f"**🧊 Xem trước 3D {cfg['label'].lower()}** (độc lập)")
    try:
        st.plotly_chart(
            PLOT.to_concrete_3d(PB.build_plan_part_fig(sec, _H, cfg["color"], cfg["label"])),
            use_container_width=True, key=f"{kind}_prev3d")
    except Exception as _e:
        st.error(f"Lỗi 3D: {_e}")

    _s1, _s2, _ = st.columns([1, 1, 3])
    if _s1.button(f"💾 Lưu {cfg['label'].lower()}", type="primary",
                  use_container_width=True, key=f"{kind}_save"):
        if not _ten.strip():
            st.warning(f"⚠️ Nhập **tên {cfg['label'].lower()}**.")
        elif not sec.get("outer"):
            st.warning("⚠️ Cần upload mặt cắt.")
        else:
            items = st.session_state.get(cfg["ss"], getattr(CLIB, cfg["load"])())
            rid = eid or getattr(CLIB, cfg["mkid"])(_ten, items)
            rec = {"id": rid, "ten": _ten.strip(), "section": sec, "H": float(_H),
                   "created_by": (AUTH.current_user() or {}).get("name", ""),
                   "updated_at": time.strftime("%Y-%m-%d %H:%M")}
            st.session_state[cfg["ss"]] = getattr(CLIB, cfg["upsert"])(items, rec)
            getattr(CLIB, cfg["save"])(st.session_state[cfg["ss"]])
            for _k in (f"_{kind}_panel", f"_{kind}_edit_id", f"_{kind}_draft"):
                st.session_state.pop(_k, None)
            st.toast(f"Đã lưu {cfg['label'].lower()} “{_ten}”.", icon="✅")
            st.rerun()
    if _s2.button("Hủy", use_container_width=True, key=f"{kind}_cancel"):
        for _k in (f"_{kind}_panel", f"_{kind}_edit_id", f"_{kind}_draft"):
            st.session_state.pop(_k, None)
        st.rerun()


def render_assembly_library(kind: str) -> None:
    """Thư viện cấu kiện lắp ghép (trụ hoặc mố)."""
    cfg = _asm_cfg(kind); lab = cfg["label"]; ss = cfg["ss"]
    labels = _asm_labels(cfg)
    if ss not in st.session_state:
        st.session_state[ss] = cfg["load"]()

    if st.session_state.get(f"_lib_{kind}_panel"):
        _render_asm_edit_panel(cfg)
        return

    items = st.session_state[ss]
    _h1, _h2 = st.columns([3, 1])
    _part_txt = ("bệ + thân + xà mũ (công xôn)" if kind == "tru"
                 else "bệ + thân + mũ kê gối (mố chữ U)")
    with _h1:
        st.markdown(f"##### {cfg['icon']} {lab} lắp ghép")
        st.caption(f"{lab} = {_part_txt}. Mỗi bộ phận upload mặt cắt riêng. "
                   f"Gắn vào cầu ở tab **Bố trí chung**.")
    with _h2:
        if st.button(f"➕ Tạo {lab.lower()} mới", type="primary",
                     use_container_width=True, key=f"lib_{kind}_new"):
            _clear_asm_widgets(kind)
            st.session_state[f"_lib_{kind}_draft"] = cfg["default"]()
            st.session_state.pop(f"_lib_{kind}_editing_id", None)
            st.session_state[f"_lib_{kind}_panel"] = "new"
            st.rerun()

    _render_part_io(kind, lab.lower(), items, cfg["save"], ss_key=ss)
    if not items:
        st.info(f"Chưa có {lab.lower()} nào. Bấm **➕ Tạo {lab.lower()} mới** để bắt đầu.")
        return

    for p in sorted(items, key=lambda x: str(x.get("ten", "")).strip().lower()):
        _info, _e3, _e4 = st.columns([8, 1, 1])
        with _info:
            _pp = cfg["migrate"](p).get("parts", {})
            if kind == "tru":
                _xml = _xamu_layers_of(_pp.get('xa_mu', {}))
                _mu_txt = ("/".join(f"{l.get('D','?')}" for l in _xml) + "m"
                           if _xml else "?")
                _sub = (f"bệ H={_pp.get('be',{}).get('H','?')}m · "
                        f"thân H={_pp.get('than',{}).get('H','?')}m · "
                        f"mũ {len(_xml)} đoạn (dày {_mu_txt})")
            else:
                _sub = (f"bệ H={_pp.get('be',{}).get('H','?')}m · "
                        f"thân+mũ rộng B={_pp.get('than',{}).get('B','?')}m")
            st.markdown(
                f"<div style='background:#141420;border:1px solid #2a2a3a;"
                f"border-left:4px solid {cfg['color']};border-radius:8px;padding:8px 12px'>"
                f"<span style='font-size:14px;font-weight:600;color:#f0f0f0'>"
                f"{cfg['icon']} {p.get('ten','(không tên)')}</span>"
                f"<span style='font-size:11px;color:#888;margin-left:10px'>"
                f"{_sub} · cao ≈ {cfg['total_h'](p)}m · "
                f"{p.get('created_by','') or '—'}</span></div>",
                unsafe_allow_html=True)
        if _e3.button("✏️", key=f"lib_{kind}_edit_{p['id']}",
                      use_container_width=True, help=f"Sửa {lab.lower()}"):
            _clear_asm_widgets(kind)
            st.session_state[f"_lib_{kind}_draft"] = dict(p)
            st.session_state[f"_lib_{kind}_editing_id"] = p["id"]
            st.session_state[f"_lib_{kind}_panel"] = p["id"]
            st.rerun()
        if _e4.button("🗑️", key=f"lib_{kind}_del_{p['id']}",
                      use_container_width=True, help=f"Xóa {lab.lower()}"):
            st.session_state[ss] = cfg["delete"](items, p["id"])
            cfg["save"](st.session_state[ss])
            st.rerun()


def _pile_section_fig(shape, b_mm, h_mm, n_sides, height=260, title=""):
    """Vẽ xem trước MẶT CẮT NGANG cọc từ tham số (mm)."""
    import plotly.graph_objects as _go
    poly = PS.section_polygon(shape, b_mm, h_mm, n_sides)
    xs = [p[0] for p in poly] + [poly[0][0]]
    zs = [p[1] for p in poly] + [poly[0][1]]
    fig = _go.Figure()
    fig.add_trace(_go.Scatter(
        x=xs, y=zs, fill="toself", mode="lines",
        fillcolor="rgba(170,183,184,0.45)", line=dict(color="#566573", width=2),
        hoverinfo="skip", showlegend=False))
    # tâm + ký hiệu trục
    _r = max(abs(min(xs)), abs(max(xs)), abs(min(zs)), abs(max(zs)), 1.0)
    fig.add_shape(type="line", x0=-_r*1.15, y0=0, x1=_r*1.15, y1=0,
                  line=dict(color="#aab7b8", width=1, dash="dashdot"))
    fig.add_shape(type="line", x0=0, y0=-_r*1.15, x1=0, y1=_r*1.15,
                  line=dict(color="#aab7b8", width=1, dash="dashdot"))
    _Deq = PS.equivalent_D_m(shape, b_mm, h_mm, n_sides)
    fig.update_layout(
        title=dict(text=title or f"{PS.describe(shape, b_mm, h_mm, n_sides)} · "
                                 f"Ø_tđ={_Deq:.2f}m", x=0.5, font=dict(size=12)),
        xaxis=dict(title="x (mm)", scaleanchor="y", scaleratio=1,
                   showgrid=True, gridcolor="#eef2f3", zeroline=False),
        yaxis=dict(title="z (mm)", showgrid=True, gridcolor="#eef2f3", zeroline=False),
        height=height, template="plotly_white",
        margin=dict(l=50, r=20, t=44, b=40),
    )
    return fig


def render_mong_library(lib: dict) -> None:
    """Thư viện MÓNG: tạo CHI TIẾT CỌC qua mặt cắt ngang (parametric)."""
    st.markdown("##### 🦵 Chi tiết cọc (mặt cắt ngang)")
    st.caption("Tạo chi tiết cọc bằng cách chọn **dạng mặt cắt** và nhập kích thước "
               "(mm). Đường kính tương đương (m) tự suy ra để dùng cho **Sơ đồ cọc** "
               "và các hình mố–trụ.")
    recs = list(CLIB.records_for(lib, "mong"))

    def _save_mong(_new):
        _nl = dict(lib); _nl["mong"] = _new
        CLIB.save_library(_nl)
        st.session_state.component_library = CLIB.normalize(_nl)
    _render_part_io("mong", "móng", recs, _save_mong)

    # ── Danh sách thẻ chi tiết cọc (giống Dầm/Trụ/Mố) — ✏️ sửa · 🗑️ xóa ──
    if recs:
        st.markdown("**Đã có trong thư viện:**")
        for _r in sorted(recs, key=lambda x: str(x.get("ten", "")).strip().lower()):
            _shp = _r.get("tiet_dien", "") or "—"
            _b = _r.get("canh_b", 0); _h = _r.get("canh_h", 0); _n = _r.get("so_canh", 0)
            _desc = (PS.describe(_shp, _b, _h, _n) if _shp not in ("", "—") else "MC chưa khai")
            _nm = _r.get("ten", "(cọc)")
            _info, _e3, _e4 = st.columns([8, 1, 1])
            with _info:
                st.markdown(
                    f"<div style='background:#141420;border:1px solid #2a2a3a;"
                    f"border-left:4px solid #7d5a32;border-radius:8px;padding:8px 12px'>"
                    f"<span style='font-size:14px;font-weight:600;color:#f0f0f0'>"
                    f"🦵 {_nm}</span>"
                    f"<span style='font-size:11px;color:#888;margin-left:10px'>"
                    f"{_r.get('loai_mong','—')} · {_desc} · "
                    f"Ø_tđ={float(_r.get('duong_kinh_coc',0) or 0):.2f}m · "
                    f"L={float(_r.get('chieu_dai_coc',0) or 0):.0f}m</span></div>",
                    unsafe_allow_html=True)
            if _e3.button("✏️", key=f"mong_edit_{_r.get('id', _nm)}",
                          use_container_width=True, help="Sửa chi tiết cọc"):
                st.session_state["mong_pick"] = _nm
                st.rerun()
            if _e4.button("🗑️", key=f"mong_delcard_{_r.get('id', _nm)}",
                          use_container_width=True, help="Xóa chi tiết cọc"):
                _keep = [r for r in recs if r.get("ten") != _nm]
                _newlib = dict(lib); _newlib["mong"] = _keep
                try:
                    CLIB.save_library(_newlib)
                    st.session_state.component_library = CLIB.normalize(_newlib)
                    if st.session_state.get("mong_pick") == _nm:
                        st.session_state["mong_pick"] = "— Tạo mới —"
                    st.rerun()
                except Exception as _e:
                    st.error(f"Lỗi xóa: {_e}")

    st.markdown("---")
    st.markdown("**➕ Thêm / sửa chi tiết cọc**")
    _names = ["— Tạo mới —"] + [r.get("ten", "") for r in recs]
    # mong_pick có thể trỏ tới record vừa bị xóa → ép về hợp lệ trước khi render
    if st.session_state.get("mong_pick") not in _names:
        st.session_state["mong_pick"] = _names[0]
    _pick = st.selectbox("Chọn để sửa", _names, index=0, key="mong_pick")
    _cur = {}
    if _pick != _names[0]:
        _cur = next((r for r in recs if r.get("ten") == _pick), {})
    # Hậu tố key theo record đang chọn → đổi record thì widget lấy lại default mới
    _pk = str(_names.index(_pick))

    _c1, _c2 = st.columns([3, 2])
    with _c1:
        _ten = st.text_input("Tên chi tiết cọc", value=_cur.get("ten", ""),
                             key=f"mong_ten_{_pk}")
        _loai = st.selectbox(
            "Loại móng", CLIB.LOAI_OPTIONS["loai_mong"],
            index=(CLIB.LOAI_OPTIONS["loai_mong"].index(_cur["loai_mong"])
                   if _cur.get("loai_mong") in CLIB.LOAI_OPTIONS["loai_mong"] else 0),
            key=f"mong_loai_{_pk}")
        _shapes = PS.SHAPES
        _shape = st.selectbox(
            "Dạng mặt cắt", _shapes,
            index=(_shapes.index(_cur["tiet_dien"])
                   if _cur.get("tiet_dien") in _shapes else 0),
            key=f"mong_shape_{_pk}")
        # record cũ chưa khai mặt cắt → suy cạnh b từ đường kính tương đương
        _b_def = float(_cur.get("canh_b", 0) or 0)
        if _b_def <= 0:
            _b_def = float(_cur.get("duong_kinh_coc", 0) or 0) * 1000 or 1000.0
        _cc1, _cc2, _cc3 = st.columns(3)
        _b = _cc1.number_input(
            "Cạnh/Ø b (mm)", 50.0, 5000.0, _b_def, 50.0, key=f"mong_b_{_pk}")
        _h = _cc2.number_input(
            "Cạnh h (mm)", 0.0, 5000.0,
            float(_cur.get("canh_h", 0) or 0), 50.0, key=f"mong_h_{_pk}",
            help="Chỉ dùng cho Chữ nhật (chiều cao).",
            disabled=(_shape != "Chữ nhật"))
        _n = _cc3.number_input(
            "Số cạnh", 3, 16, int(_cur.get("so_canh", 8) or 8), 1, key=f"mong_n_{_pk}",
            help="Chỉ dùng cho Đa giác đều.",
            disabled=(_shape != "Đa giác đều"))
        _cd1, _cd2 = st.columns(2)
        _sococ = _cd1.number_input("Số cọc (gợi ý)", 0, 200,
                                   int(_cur.get("so_coc", 0) or 0), 1,
                                   key=f"mong_sococ_{_pk}")
        _Lcoc = _cd2.number_input("L cọc (m)", 0.0, 120.0,
                                  float(_cur.get("chieu_dai_coc", 30) or 30), 1.0,
                                  key=f"mong_Lcoc_{_pk}")
        _ghi = st.text_input("Ghi chú", value=_cur.get("ghi_chu", ""),
                             key=f"mong_ghi_{_pk}")
    with _c2:
        try:
            _f_ps = _pile_section_fig(_shape, _b, _h, _n)
            PLOT.aspect_control(_f_ps, f"pile_sec_{_pk}")
            st.plotly_chart(_f_ps,
                            use_container_width=True, config={"displayModeBar": False})
        except Exception as _e:
            st.error(f"Lỗi vẽ mặt cắt: {_e}")
        st.metric("Ø tương đương", f"{PS.equivalent_D_m(_shape, _b, _h, _n):.3f} m")

    _b1, _b2 = st.columns([1, 1])
    if _b1.button("💾 Lưu chi tiết cọc", type="primary", key="mong_save"):
        if not str(_ten).strip():
            st.error("Cần nhập **Tên chi tiết cọc**.")
        else:
            _flds = PS.section_fields(_shape, _b, _h, _n)
            _new = {
                "ten": _ten.strip(), "loai_mong": _loai,
                "so_coc": int(_sococ), "chieu_dai_coc": float(_Lcoc),
                "ghi_chu": _ghi, **_flds,
            }
            _byname = {r.get("ten"): r for r in recs}
            _byname[_new["ten"]] = _new           # upsert theo tên
            _newlib = dict(lib); _newlib["mong"] = list(_byname.values())
            try:
                CLIB.save_library(_newlib)
                st.session_state.component_library = CLIB.normalize(_newlib)
                st.success(f"✅ Đã lưu chi tiết cọc **{_new['ten']}**.")
                st.rerun()
            except Exception as _e:
                st.error(f"Lỗi lưu: {_e}")
    if _pick != _names[0] and _b2.button("🗑 Xóa chi tiết này", key="mong_del"):
        _keep = [r for r in recs if r.get("ten") != _pick]
        _newlib = dict(lib); _newlib["mong"] = _keep
        try:
            CLIB.save_library(_newlib)
            st.session_state.component_library = CLIB.normalize(_newlib)
            st.success(f"Đã xóa **{_pick}**.")
            st.rerun()
        except Exception as _e:
            st.error(f"Lỗi xóa: {_e}")


def _normalize_railing_section(outer, holes):
    """Chuẩn hoá MCN lan can: y giữ nguyên (ngang), z dời sao cho ĐÁY z=0
    (chân lan can đặt trên mặt cầu, vươn lên trên). Trả (outer, holes, rộng, cao)."""
    if not outer or len(outer) < 3:
        return [], [], 0.0, 0.0
    zs = [p[1] for p in outer]
    z_min = min(zs)
    def _shift(pts):
        return [[float(p[0]), float(p[1]) - z_min] for p in pts]
    o2 = _shift(outer)
    h2 = [_shift(h) for h in (holes or []) if len(h) >= 3]
    ys = [p[0] for p in o2]; zz = [p[1] for p in o2]
    return o2, h2, (max(ys) - min(ys)), (max(zz) - min(zz))


def render_railing_library() -> None:
    """Thư viện LAN CAN / GIẢI PHÂN CÁCH — upload MCN (DXF) chạy dọc toàn cầu."""
    rails = st.session_state.lib_railings
    st.markdown("##### 🚧 Lan can / Giải phân cách")
    st.caption("Upload **mặt cắt ngang** chi tiết (DXF). Khi khai báo ở phương án "
               "(tab **Bố trí chung**), chọn loại MCN này — mô hình 3D sẽ kéo MCN "
               "đó **chạy dọc toàn cầu**.")

    _render_part_io("railings", "lan can/GPC", rails, CLIB.save_railings,
                    ss_key="lib_railings")

    # ── Danh sách đã có ──────────────────────────────────────────────────
    if rails:
        st.markdown("**Đã có trong thư viện:**")
        for _r in sorted(rails, key=lambda x: str(x.get("ten", "")).lower()):
            _info, _ed, _del = st.columns([8, 1, 1])
            with _info:
                _lab = CLIB.RAILING_LABEL.get(_r.get("loai"), "—")
                st.markdown(
                    f"<div style='background:#141420;border:1px solid #2a2a3a;"
                    f"border-left:4px solid #e67e22;border-radius:8px;padding:8px 12px'>"
                    f"<span style='font-size:14px;font-weight:600;color:#f0f0f0'>"
                    f"🚧 {_r.get('ten','(không tên)')}</span>"
                    f"<span style='font-size:11px;color:#888;margin-left:10px'>"
                    f"{_lab} · rộng {float(_r.get('rong_mm',0) or 0):.0f}mm · "
                    f"cao {float(_r.get('cao_mm',0) or 0):.0f}mm · "
                    f"{len(_r.get('outer',[]))} đỉnh</span></div>",
                    unsafe_allow_html=True)
            if _ed.button("✏️", key=f"rail_edit_{_r['id']}",
                          use_container_width=True, help="Sửa"):
                st.session_state["_rail_draft"] = {
                    "outer": _r.get("outer", []), "holes": _r.get("holes", []),
                    "rong_mm": _r.get("rong_mm", 0), "cao_mm": _r.get("cao_mm", 0)}
                st.session_state["rail_ten"] = _r.get("ten", "")
                st.session_state["rail_loai"] = _r.get("loai", "lan_can")
                st.session_state["rail_ghi"] = _r.get("ghi_chu", "")
                st.session_state["_rail_edit_id"] = _r["id"]
                st.session_state.pop("_rail_sig", None)
                st.rerun()
            if _del.button("🗑️", key=f"rail_del_{_r['id']}",
                           use_container_width=True, help="Xóa"):
                st.session_state.lib_railings = CLIB.delete_railing(rails, _r["id"])
                CLIB.save_railings(st.session_state.lib_railings)
                st.rerun()
        st.markdown("---")

    # ── Thêm mới ─────────────────────────────────────────────────────────
    st.markdown("**➕ Thêm lan can / giải phân cách mới**")
    _up = st.file_uploader("⬆ Upload mặt cắt ngang (DXF)", type=["dxf", "dwg"],
                           key="rail_dxf")
    if _up is not None:
        _sig = f"{_up.name}:{_up.size}"
        if st.session_state.get("_rail_sig") != _sig:
            try:
                _res = _BB_ENGINE.parse_dxf_bytes(_up.read())
                if _res.get("error"):
                    st.error(f"Lỗi đọc DXF: {_res['error']}")
                elif len(_res.get("outer", [])) >= 3:
                    _o, _h, _w, _ht = _normalize_railing_section(
                        _res["outer"], _res.get("holes", []))
                    st.session_state["_rail_draft"] = {
                        "outer": _o, "holes": _h, "rong_mm": _w, "cao_mm": _ht}
                    st.session_state["_rail_sig"] = _sig
                    st.session_state.pop("_rail_edit_id", None)  # upload mới = bản ghi mới
                    st.success(f"✅ Đã nạp MCN: {len(_o)} đỉnh · rộng {_w:.0f}mm · "
                               f"cao {_ht:.0f}mm.")
                else:
                    st.warning("Không tìm thấy biên kín trong DXF.")
            except Exception as _e:
                st.error(f"Lỗi xử lý DXF: {_e}")

    _draft = st.session_state.get("_rail_draft") or {}
    _pv, _pp = st.columns([3, 2])
    with _pv:
        _f = _asm_section_fig(_draft) if _draft.get("outer") else None
        if _f is not None:
            PLOT.aspect_control(_f, "rail_secfig")
            st.plotly_chart(_f, use_container_width=True, key="rail_secfig")
        else:
            st.info("Chưa có mặt cắt — upload DXF để bắt đầu.")
    with _pp:
        _ten = st.text_input("Tên", key="rail_ten",
                             placeholder="VD: Lan can BT cốt thép H1.1m")
        _loai = st.selectbox(
            "Loại", list(CLIB.RAILING_TYPES),
            format_func=lambda k: CLIB.RAILING_LABEL.get(k, k), key="rail_loai")
        _ghi = st.text_input("Ghi chú", key="rail_ghi")

    if st.button("💾 Lưu vào thư viện", type="primary", key="rail_save",
                 disabled=(not _draft.get("outer"))):
        if not str(_ten).strip():
            st.error("Cần nhập **Tên**.")
        else:
            _eid = st.session_state.get("_rail_edit_id")
            _rec = {
                "id":  _eid or CLIB.make_railing_id(_ten, rails),
                "ten": _ten.strip(), "loai": _loai,
                "outer": _draft["outer"], "holes": _draft.get("holes", []),
                "rong_mm": float(_draft.get("rong_mm", 0) or 0),
                "cao_mm":  float(_draft.get("cao_mm", 0) or 0),
                "ghi_chu": _ghi, "created_by": AUTH.current_user().get("username", ""),
            }
            st.session_state.lib_railings = CLIB.upsert_railing(rails, _rec)
            CLIB.save_railings(st.session_state.lib_railings)
            for _k in ("_rail_draft", "_rail_sig", "_rail_edit_id",
                       "rail_ten", "rail_ghi"):
                st.session_state.pop(_k, None)
            st.success(f"✅ Đã lưu **{_rec['ten']}**.")
            st.rerun()


def _render_library_io() -> None:
    """Nút TẢI TOÀN BỘ thư viện về (.json) + UPLOAD thư viện đã tạo để dùng.
    Người dùng tự tạo → tải về giữ → upload lại khi làm (không tự lưu GitHub)."""
    _io1, _io2 = st.columns(2)
    with _io1:
        try:
            _bundle = CLIB.export_bundle()
            _data = json.dumps(_bundle, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button(
                "⬇️ Tải toàn bộ thư viện", data=_data,
                file_name="thu_vien_cau_kien.json", mime="application/json",
                use_container_width=True, key="lib_export_all")
        except Exception as _e:
            st.error(f"Lỗi xuất thư viện: {_e}")
    with _io2:
        _up = st.file_uploader(
            "⬆️ Upload thư viện (.json)", type=["json"],
            key="lib_import_all", label_visibility="collapsed")
        if _up is not None and st.button(
                "✅ Nạp thư viện đã upload", type="primary",
                use_container_width=True, key="lib_import_apply"):
            try:
                _bundle = json.loads(_up.read().decode("utf-8"))
                _counts = CLIB.import_bundle(_bundle)
                # Xóa cache session để nạp lại từ file vừa ghi
                for _k in ("component_library", "dam_beams", "dam_piers",
                           "dam_mos", "lib_railings", "lib_caps", "lib_stems",
                           "lib_footings"):
                    st.session_state.pop(_k, None)
                st.success("Đã nạp thư viện: " + ", ".join(
                    f"{k}={v}" for k, v in _counts.items()) + ".")
                st.rerun()
            except Exception as _e:
                st.error(f"File thư viện không hợp lệ: {_e}")


def render_thu_vien() -> None:
    """Tab Thư viện cấu kiện dùng chung.
    Dầm: tạo qua panel CAD. Trụ/Mố/Móng: bảng tham số. Luôn truy cập được."""
    st.markdown("---")
    _render_library_io()
    st.markdown(
        DS.section_header(
            "Thư viện cấu kiện dùng chung",
            icon="📚",
            sub=("Dùng chung cho cả 3 phương án. Dầm tạo qua panel như tab "
                 "Chi tiết dầm; Trụ/Mố/Móng khai báo bằng bảng tham số."),
        ),
        unsafe_allow_html=True,
    )

    d = st.session_state.design_data
    if "component_library" not in st.session_state:
        st.session_state.component_library = CLIB.load_library()
    lib = st.session_state.component_library
    if "dam_beams" not in st.session_state:
        st.session_state.dam_beams = CLIB.load_beams()

    if "dam_piers" not in st.session_state:
        st.session_state.dam_piers = CLIB.load_piers()
    if "dam_mos" not in st.session_state:
        st.session_state.dam_mos = CLIB.load_mos()
    if "lib_railings" not in st.session_state:
        st.session_state.lib_railings = CLIB.load_railings()

    # Trụ & Mố: thư viện LẮP GHÉP (upload mặt cắt). Móng: vẫn bảng tham số.
    # Dùng option_menu giữ NGUYÊN tab đang chọn sau khi Lưu (st.tabs sẽ reset
    # về tab đầu mỗi lần rerun — gây nhảy về "Dầm" rất khó chịu).
    # KEY ỔN ĐỊNH (không kèm số đếm) → st.radio lưu được lựa chọn qua mọi rerun;
    # số đếm hiển thị qua format_func nên không phá vỡ persistence khi thêm/xóa.
    _lib_keys  = ["dam", "tru", "mo", "mong", "rail"]
    _lib_disp  = {"dam": "🌉 Dầm", "tru": "🏗️ Trụ", "mo": "🧱 Mố",
                  "mong": "🦵 Móng", "rail": "🚧 Lan can/GPC"}
    _lib_count = {
        "dam":  len(st.session_state.dam_beams),
        "tru":  (len(st.session_state.get("lib_caps") or CLIB.load_caps())
                 + len(st.session_state.get("lib_stems") or CLIB.load_stems())
                 + len(st.session_state.get("lib_footings") or CLIB.load_footings())),
        "mo":   len(st.session_state.dam_mos),
        "mong": len(lib.get("mong", [])),
        "rail": len(st.session_state.lib_railings),
    }
    _sel = st.radio(
        "Nhóm cấu kiện", _lib_keys, horizontal=True, key="_lib_subtab",
        format_func=lambda k: f"{_lib_disp[k]} ({_lib_count[k]})",
        label_visibility="collapsed")

    if _sel == "dam":
        render_dam_library(d)
    elif _sel == "tru":
        # 3 thư viện bộ phận trụ độc lập (lắp ghép khi gắn cầu).
        # Sao lưu/khôi phục đặt ở CẤP TỔNG — chung cho cả 3 bộ phận con.
        _render_tru_io()
        _tru_sub = st.radio(
            "Bộ phận trụ", ["🧢 Xà mũ", "🏛️ Thân trụ", "🟫 Bệ trụ"],
            horizontal=True, key="_tru_part_sub", label_visibility="collapsed")
        st.markdown("")
        if _tru_sub.startswith("🧢"):
            render_cap_library()
        elif _tru_sub.startswith("🏛️"):
            render_simple_part_library("stem")
        else:
            render_simple_part_library("footing")
    elif _sel == "mo":
        render_assembly_library("mo")
    elif _sel == "mong":
        render_mong_library(lib)
    else:
        render_railing_library()


selected_ribbon = st.session_state.get('current_tab', 'THUYẾT MINH')

#  Layout: Main canvas + Right panel (tỷ lệ cố định 7:3)
_col_main, _col_right = st.columns([7, 3], gap="small")

with _col_right:
    _render_right_panel(st.session_state.design_data)

with _col_main:
    if selected_ribbon == "THUYẾT MINH":
        d = st.session_state.design_data
        kcn  = d.get('kcn_result')
        tru  = d.get('tru_result')
        mong = d.get('mong_result')
    
        # Nếu chưa chạy AI → Welcome / Onboarding screen
        if kcn is None:
            st.markdown("""
    <div style='text-align:center; padding: 32px 0 16px'>
      <div style='font-size:48px'>🏗️</div>
      <h2 style='color:#f0f0f0; margin:8px 0 4px'>Chào mừng đến Hệ thống Thiết kế Cầu AI</h2>
      <p style='color:#888; font-size:14px'>UTH — Tích hợp AI và BIM tự động hóa thiết kế cầu đường bộ</p>
    </div>
    """, unsafe_allow_html=True)
    
            def _step_card(icon, title, desc, color):
                return (
                    f"<div style='background:#1e1e2e; border:1px solid {color}; "
                    f"border-top:3px solid {color}; border-radius:12px; padding:20px; "
                    f"height:100%; text-align:center;'>"
                    f"<div style='font-size:36px; margin-bottom:12px'>{icon}</div>"
                    f"<h4 style='color:{color}; margin:0 0 10px'>{title}</h4>"
                    f"<p style='color:#aaa; font-size:13px; line-height:1.6; margin:0'>{desc}</p>"
                    f"</div>"
                )
    
            wc1, wc2, wc3 = st.columns(3)
            with wc1:
                st.markdown(_step_card(
                    "⚙️", "Bước 1 — Khai báo số liệu",
                    "Nhập thông số thủy văn, hình học tuyến và điều kiện địa phương qua hộp thoại OPTIONS",
                    "#007acc",
                ), unsafe_allow_html=True)
            with wc2:
                st.markdown(_step_card(
                    "🤖", "Bước 2 — Chạy AI tính toán",
                    "AI tự động tính toán kết cấu nhịp, mố trụ, móng cọc và lớp phủ mặt cầu theo TCVN",
                    "#f39c12",
                ), unsafe_allow_html=True)
            with wc3:
                st.markdown(_step_card(
                    "📋", "Bước 3 — Xem kết quả & xuất file",
                    "📄 thuyết minh, xem bản vẽ kỹ thuật 2D/3D, so sánh phương án và xuất DXF/IFC",
                    "#2ecc71",
                ), unsafe_allow_html=True)
    
            st.markdown("<br>", unsafe_allow_html=True)
            _, _mid, _ = st.columns([1.5, 1, 1.5])
            with _mid:
                if st.button(
                    "⚙️ BẮT ĐẦU — Khai báo số liệu",
                    use_container_width=True,
                    type="primary",
                    key="welcome_start_btn",
                ):
                    st.session_state.open_dialog = "step1"
                    st.session_state.field_touched = set()
                    st.session_state.field_errors = {}
                    st.session_state.field_warnings = {}
                    st.rerun()
            st.caption("💡 Sau khi điền đầy đủ thông số và nhấn OK, hệ thống sẽ tự động chạy toàn bộ pipeline AI.")
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
                    st.write(f"Cấp sông ỐTN  : Cấp {d['cap_song']}")
            with c2:
                st.markdown("**Cao độ thủy văn (m)**")
                st.write(f"MNCN (H1%)  : {d.get('MNCN',0):.3f} m")
                st.write(f"MNTT (H5%)  : {d.get('MNTT',0):.3f} m")
                st.write(f"MNTC (H10%) : {d.get('MNTC',0):.3f} m")
                st.write(f"MNTN (H98%) : {d.get('MNTN',0):.3f} m")
                st.write(f"CỐTN (từ địa hình): {d.get('h_tn_tb',0):.3f} m")
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
    
        # (Đã bỏ "II.b CHỈNH SỬA KÍCH THƯỚC CHI TIẾT DẦM" — thay bằng tab
        #  BeamBuilder mới; chi tiết dầm do người dùng dựng ở đó.)

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
                    st.caption(f"📋 {res_mcn['tieu_chuan']} — Vtk={tra_tt.get('vtk','')}km/h — {tra_tt.get('mo_ta_dpc','')}")
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
                        f"📋 {res_mcn['tieu_chuan']} — {tra_tt.get('mo_ta','')} | "
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
                    st.caption(f"📋 {res_mcn['tieu_chuan']} — Cấp {tra_tt['cap_duong']}")
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
                    # Sơ đồ MCN đường: cao độ mang tính biểu trưng → giữ tỷ lệ thiết kế
                    PLOT.aspect_control(fig_mcn_2d, "mcn_oto_2d", default="keep")
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
                        # Sơ đồ MCN tại cầu: cao độ biểu trưng → giữ tỷ lệ thiết kế
                        PLOT.aspect_control(fig_cau_2d, "mcn_cau_2d", default="keep")
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
    
    elif selected_ribbon in ("Phương án 1", "Phương án 2", "Phương án 3"):
        _s1 = tab_states['tab1']
        if _s1 == 'done':
            st.markdown(
                DS.banner("success", "Dữ liệu đầy đủ — bản vẽ hiển thị kết quả tính toán mới nhất."),
                unsafe_allow_html=True,
            )
        elif _s1 == 'partial':
            st.markdown(
                DS.banner("warning",
                          "Kết cấu nhịp đã có nhưng chưa tính xong trụ",
                          "Một số bản vẽ có thể chưa đầy đủ"),
                unsafe_allow_html=True,
            )
        elif _s1 == 'locked':
            _es = DS.empty_state(
                icon      = "🔒",
                title     = "Bản vẽ chưa sẵn sàng",
                desc      = ("Pipeline AI cần chạy thành công để sinh "
                             "bản vẽ trắc dọc, mặt cắt ngang và mố trụ."),
                cta_label = "⚙️ Mở OPTIONS",
                cta_key   = "es_open_opts_bv",
                variant   = "locked",
            )
            st.markdown(_es["html"], unsafe_allow_html=True)
            if _es["show_cta"]:
                _, _mc, _ = st.columns([1.5, 1, 1.5])
                with _mc:
                    if st.button(_es["cta_label"], key=_es["cta_key"],
                                 use_container_width=True, type="secondary"):
                        st.session_state.open_dialog = "step1"
                        st.session_state.field_touched = set()
                        st.session_state.field_errors = {}
                        st.session_state.field_warnings = {}
                        st.rerun()
            st.stop()

        d   = st.session_state.design_data
        # Chọn phương án theo tab → đổi kcn_result sang PA tương ứng.
        # Trụ/móng/địa hình/địa chất DÙNG CHUNG cho cả 3 phương án.
        _pa_map = {"Phương án 1": "pa1_chi_phi",
                   "Phương án 2": "pa2_my_quan",
                   "Phương án 3": "pa3_ai"}
        _pa_key = _pa_map.get(selected_ribbon, "pa1_chi_phi")
        _3pa = d.get("kcn_3_pa") or {}
        if _3pa.get(_pa_key):
            d = {**d, "kcn_result": dict(_3pa[_pa_key])}
        kcn = d.get("kcn_result") or d.get("ai_result")
        tru = d.get("tru_result")
        has_ai = kcn is not None
        # Mô hình trụ/mố lắp ghép → để KHỐI LƯỢNG tính theo mô hình mới (nếu có)
        try:
            d["_pier_model"] = _resolve_assembly(d, "tru")
            d["_mo_model"]   = _resolve_assembly(d, "mo")
        except Exception:
            d["_pier_model"] = d["_mo_model"] = None

        st.markdown("---")
    
        if not has_ai:
            _kcn_err  = d.get('_kcn_error')
            _ran      = 'H_tru_est' in d
            if _ran:
                st.warning(
                    "⚠️ Pipeline đã chạy nhưng **AI Kết cấu nhịp không cho kết quả**. "
                    + (f"\n\nChi tiết lỗi: `{_kcn_err}`" if _kcn_err else "")
                    + "\n\nCó thể thiếu file `Data/Bridge_Train_Dataset_v3.xlsx` hoặc lỗi tính toán. "
                    "Mở **⚙️ OPTIONS** để chạy lại."
                )
            else:
                st.info(
                    "⚙️ Nhấn nút **⚙️ OPTIONS - KHAI BÁO SỐ LIỆU** ở góc trên trái, "
                    "điền đầy đủ thông số, sau đó nhấn **💾 OK - Áp dụng cấu hình và Chạy dự báo AI** "
                    "bên trong hộp thoại để hệ thống chạy AI pipeline và hiển thị kết quả tại đây."
                )
        else:
            _df_geo  = st.session_state.get("df_geology", None)
            _df_tim  = st.session_state.get("df_tim_line", None)
            has_terr = _df_geo is not None and not _df_geo.empty
            # pfx dầm theo phương án — dùng CHUNG cho mọi sub-tab (overlay theo PA)
            _spt_pfx = _PA_SPT_PFX.get(selected_ribbon, "spt")
            # Nạp bố trí nhịp (2 tầng) của PA vào d → mọi bản vẽ đồng bộ
            d = {**d, "span_layout": _pa_span_layout(selected_ribbon),
                 "railings": _resolve_railings_for_pa(selected_ribbon)}

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
             tab_spt, tab_thkl, tab_dutoan,
             tab_export) = st.tabs([
                "🏗️ 3D Tổng hợp"  + (" 🗺️" if has_terr else " (sơ đồ)"),
                "📋 Bố trí chung",
                "✂️ MCN Mố/Trụ",
                "🔩 Chi tiết dầm",
                "📊 THKL",
                "💰 Dự toán",
                "📤 Xuất hồ sơ",
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
                            f"⚠️ **Cầu không nằm trong phạm vi địa hình!** "
                            f"Địa hình: {_lt_min2:.1f}→{_lt_max2:.1f}m | Cầu: {_xmo_t:.1f}→{_xmo_p:.1f}m. "
                            f"👉 Mở **OPTIONS** và đặt **Lý trình tim tĩnh không ≈ {_suggest_tim:.1f}m** "
                            f"để cầu khớp với địa hình."
                        )
                    else:
                        _pct_ok = 100*(min(_lt_max2,_xmo_p)-max(_lt_min2,_xmo_t))/max(1,_xmo_p-_xmo_t)
                        st.success(f"✅ Cầu khớp địa hình ({_pct_ok:.0f}% chiều dài cầu nằm trong phạm vi địa hình)")
    
                    with st.expander("⚙️ Tùy chỉnh hiển thị 3D", expanded=False):
                        _o1, _o2 = st.columns(2)
                        with _o1:
                            che_do_view = st.selectbox("🎨 Địa hình:",
                                ["Bề mặt mịn", "Đường đồng mức", "Lưới tam giác"], key="cd3d")
                            do_min_view = st.select_slider("✨ Mịn hoá:",
                                options=[1, 3, 5, 7], value=3, key="dm3d")
                        with _o2:
                            he_so_z = st.slider("↕️ Phóng đại Z:", 0.05, 3.00, 0.50, 0.05,
                                                key="hsz3d")
                            render_mode_3d = st.selectbox(
                                "🖥️ Chế độ hiển thị:",
                                ["Shaded", "Realistic", "X-Ray", "Wireframe"],
                                key="rm3d",
                                help="Shaded: mặc định • Realistic: đổ bóng cao • "
                                     "X-Ray: xuyên thấu • Wireframe: khung lưới")
                    # Compute VN-2000 origin from min-lý-trình centre-line point
                    _x_origin_vn2000 = 0.0
                    _y_origin_vn2000 = 0.0
                    if 'X_Real' in _df_geo.columns and 'Lý trình' in _df_geo.columns:
                        _df_geo_cl = _df_geo[_df_geo['Offset'] == 0] if 'Offset' in _df_geo.columns else _df_geo
                        if not _df_geo_cl.empty:
                            _idx_min_lt = _df_geo_cl['Lý trình'].idxmin()
                            _x_origin_vn2000 = float(_df_geo_cl.loc[_idx_min_lt, 'X_Real'])
                    if 'Y_Real' in _df_geo.columns and 'Lý trình' in _df_geo.columns:
                        _df_geo_cl2 = _df_geo[_df_geo['Offset'] == 0] if 'Offset' in _df_geo.columns else _df_geo
                        if not _df_geo_cl2.empty:
                            _idx_min_lt2 = _df_geo_cl2['Lý trình'].idxmin()
                            _y_origin_vn2000 = float(_df_geo_cl2.loc[_idx_min_lt2, 'Y_Real'])
                    st.session_state['terrain_x_origin'] = _x_origin_vn2000
                    st.session_state['terrain_y_origin'] = _y_origin_vn2000
                    try:
                        _fig_t, mx, my, mz = TV.ve_dia_hinh_3d(
                            _df_geo, he_so_z=he_so_z, che_do=che_do_view, do_min=do_min_view,
                            x_origin=_x_origin_vn2000, y_origin=_y_origin_vn2000,
                        )
                        if _fig_t:
                            _n_before = len(_fig_t.data)
                            _err_overlay = None
                            try:
                                BVK.add_all_to_terrain_fig(_fig_t, d, _df_geo, he_so_z)
                                # Chèn dầm thực tế từ thư viện (hệ VN-2000 trừ origin,
                                # khớp địa hình). add_all_to_terrain_fig KHÔNG vẽ dầm.
                                try:
                                    _spt_t_traces = BBUI.get_beam_model_mesh_traces_vn2000(
                                        d, _df_geo, he_so_z, pfx=_spt_pfx)
                                    for _i_b, _spt_t in enumerate(_spt_t_traces or []):
                                        _spt_t.legendgroup = "Dầm"
                                        try: _spt_t.showlegend = (_i_b == 0)
                                        except Exception: pass
                                        _fig_t.add_trace(_spt_t)
                                except Exception:
                                    pass
                                BVK.apply_render_mode(_fig_t, render_mode_3d)
                            except Exception as _oe:
                                _err_overlay = str(_oe)
                            _n_after = len(_fig_t.data)

                            # Focus camera on bridge span (lý trình relative coords)
                            _geo_cam = d.get("geo_logic", {})
                            _x_cam_mid = (
                                float(_geo_cam.get("x_mo_trai", 0)) +
                                float(_geo_cam.get("x_mo_phai", 0))
                            ) / 2.0
                            _z_cam_ref = float(d.get("cao_mat_cau") or d.get("cao_day_dam", 8.0))
                            _z_cam_sc  = _z_cam_ref * he_so_z
                            _fig_t.update_layout(
                                # Hiện chú giải để bấm ẩn/hiện cấu kiện (đặt trên
                                # cùng, ngang — tránh đè thanh cao độ bên phải).
                                showlegend=True,
                                legend=dict(orientation="h", x=0, y=1.0,
                                            yanchor="bottom", font=dict(size=9),
                                            groupclick="togglegroup",
                                            bgcolor="rgba(255,255,255,0.75)"),
                                scene_camera=dict(
                                    eye=dict(x=0.0, y=-2.5, z=1.2),
                                    center=dict(x=0.0, y=0.0, z=0.0),
                                ),
                                scene=dict(
                                    xaxis=dict(title="Lý trình (m)"),
                                    yaxis=dict(title="Ngang cầu (m)"),
                                    zaxis=dict(title="Cao độ (m)"),
                                ),
                            )

                            st.plotly_chart(_fig_t, use_container_width=True,
                                            config={"displayModeBar": True})
                            st.caption(
                                f"Địa hình: {_n_before} trace | Kết cấu cầu: +{_n_after - _n_before} trace. "
                                "Kéo chuột xoay • Scroll zoom • Shift+drag pan."
                            )
                            if _err_overlay:
                                st.error(f"Lỗi overlay kết cấu: {_err_overlay}")
                            elif _n_after == _n_before:
                                st.warning("⚠️ Không thêm được trace kết cấu — kiểm tra dữ liệu địa chất.")
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
                        fig_3d = BVK.ve_cau_3d(
                            d, df_tim_line=None,
                            pier_assembly=_resolve_assembly(d, "tru"),
                            abutment_assembly=_resolve_assembly(d, "mo"))
                        # Chèn dầm thực tế từ thư viện (ve_cau_3d KHÔNG vẽ dầm)
                        try:
                            _spt_tr = BBUI.get_beam_model_mesh_traces(d, pfx=_spt_pfx)
                            if _spt_tr:
                                for _i_b, _tr in enumerate(_spt_tr):
                                    _tr.legendgroup = "Dầm"
                                    try: _tr.showlegend = (_i_b == 0)
                                    except Exception: pass
                                    fig_3d.add_trace(_tr)
                                st.caption("🔩 Dầm thực tế từ mô hình thư viện")
                        except Exception:
                            pass
                        BVK.apply_render_mode(fig_3d, _rm_no_terr)
                        st.plotly_chart(fig_3d, use_container_width=True,
                                        config={"scrollZoom": True, "displayModeBar": True})
                    except Exception as _e:
                        st.error(f"Lỗi vẽ 3D: {_e}")
    
            # ── TAB 2: Bố trí chung ────────────────────────────────────────
            with tab_btc:
                st.markdown("##### Bố trí chung")

                _pa3 = (selected_ribbon == "Phương án 3")
                if _pa3:
                    st.info(
                        "🤖 **Phương án 3** — cấu kiện do **AI dự báo kết luận** "
                        "(đang phát triển, làm sau). Tạm thời vẽ theo cấu kiện mặc "
                        "định; chưa cho khai báo thủ công lan can / dầm / mố trụ.")

                if not _pa3:
                    # ── 0a. Lan can / Giải phân cách (theo phương án) ────────────
                    with st.expander(f"🚧 Lan can / Giải phân cách — {selected_ribbon}",
                                     expanded=False):
                        _rails_lib = st.session_state.get("lib_railings")
                        if _rails_lib is None:
                            _rails_lib = CLIB.load_railings()
                            st.session_state.lib_railings = _rails_lib
                        if not _rails_lib:
                            st.info("Chưa có MCN lan can/giải phân cách nào. Vào tab "
                                    "**📚 Thư viện → 🚧 Lan can/Giải phân cách** để upload "
                                    "mặt cắt ngang (DXF).")
                        else:
                            _sel_cur = _pa_railing(selected_ribbon)
                            _rc1, _rc2 = st.columns(2)
                            _new_sel = {}
                            for _col, _t in ((_rc1, "lan_can"),
                                             (_rc2, "giai_phan_cach")):
                                _opts = [r for r in _rails_lib if r.get("loai") == _t]
                                _ids  = ["— Không dùng —"] + [r["id"] for r in _opts]
                                _names = {r["id"]: r.get("ten", r["id"]) for r in _opts}
                                _cur = _sel_cur.get(_t)
                                _idx = _ids.index(_cur) if _cur in _ids else 0
                                with _col:
                                    _pick = st.selectbox(
                                        CLIB.RAILING_LABEL[_t], _ids, index=_idx,
                                        format_func=lambda k: ("— Không dùng —"
                                                               if k.startswith("—")
                                                               else _names.get(k, k)),
                                        key=f"rail_sel_{_t}_{selected_ribbon}")
                                if not _pick.startswith("—"):
                                    _new_sel[_t] = _pick
                            if st.button("💾 Áp dụng lan can cho phương án",
                                         key=f"rail_apply_{selected_ribbon}",
                                         use_container_width=True):
                                _save_pa_railing(selected_ribbon, _new_sel)
                                st.success("Đã áp dụng. Mô hình 3D sẽ kéo MCN dọc toàn cầu.")
                                st.rerun()
                            st.caption("MCN đã chọn sẽ được **kéo chạy dọc toàn cầu** trong "
                                       "mô hình 3D (lan can ở 2 mép cầu, giải phân cách ở tim).")

                    # ── 0. Dầm thư viện & bố trí nhịp (theo phương án) ────────────
                    with st.expander(f"🌉 Dầm & bố trí nhịp — {selected_ribbon}",
                                     expanded=False):
                        _beams_btc = st.session_state.get("dam_beams") or CLIB.load_beams()
                        _sl_cur    = _pa_span_layout(selected_ribbon)
                        _names_btc = [b.get("ten", "(không tên)") for b in _beams_btc]
                        _Ls_btc    = [float(x) for x in BVK.STD_LENGTHS]

                        def _beam_idx(_bid):
                            for _k, _b in enumerate(_beams_btc):
                                if _b.get("id") == _bid:
                                    return _k + 1
                            return 0

                        def _L_idx(_v, _dflt=33.0):
                            if _v in _Ls_btc:
                                return _Ls_btc.index(_v)
                            return _Ls_btc.index(_dflt) if _dflt in _Ls_btc else 0

                        if not _beams_btc:
                            st.caption("Chưa có dầm trong **THƯ VIỆN**. Hãy tạo dầm trước "
                                       "rồi quay lại đây để gán theo nhịp.")
                        _opts_btc = ["— chọn dầm —"] + _names_btc

                        _mode_lbl = st.radio(
                            "Kiểu bố trí nhịp:",
                            ["Đều (1 loại dầm)", "2 tầng (nhịp chính + nhịp dẫn)"],
                            index=(1 if _sl_cur.get("mode") == "two_tier" else 0),
                            horizontal=True, key=f"btc_mode_{selected_ribbon}")
                        _two = _mode_lbl.startswith("2 tầng")

                        if not _two:
                            _cu1, _cu2 = st.columns([2, 1])
                            with _cu1:
                                _seld = st.selectbox(
                                    "Dầm áp dụng (cả cầu):", _opts_btc,
                                    index=_beam_idx(_sl_cur.get("beam_dan")),
                                    key=f"btc_beamu_{selected_ribbon}")
                            with _cu2:
                                _Ldu = st.selectbox(
                                    "Chiều dài nhịp (m):", _Ls_btc,
                                    index=_L_idx(_sl_cur.get("L_dan")),
                                    key=f"btc_Lu_{selected_ribbon}")
                            _ca, _cb = st.columns(2)
                            if _ca.button("💾 Lưu bố trí đều", use_container_width=True,
                                          key=f"btc_saveu_{selected_ribbon}"):
                                _new = dict(_sl_cur)
                                _new.update({"mode": "uniform", "L_dan": float(_Ldu),
                                             "L_main": float(_Ldu)})
                                _save_pa_span_layout(selected_ribbon, _new)
                                st.rerun()
                            if _cb.button("✅ Áp dụng dầm", use_container_width=True,
                                          type="primary", disabled=(_seld == _opts_btc[0]),
                                          key=f"btc_applyu_{selected_ribbon}"):
                                _apply_beam_to_pa(
                                    d, selected_ribbon,
                                    _beams_btc[_opts_btc.index(_seld) - 1], "dan")
                        else:
                            st.markdown("**Nhịp dẫn** — đồng bộ mọi nhịp dẫn")
                            _cd1, _cd2 = st.columns([2, 1])
                            with _cd1:
                                _seld = st.selectbox(
                                    "Dầm nhịp dẫn:", _opts_btc,
                                    index=_beam_idx(_sl_cur.get("beam_dan")),
                                    key=f"btc_beamd_{selected_ribbon}")
                            with _cd2:
                                _Ld = st.selectbox(
                                    "Chiều dài nhịp dẫn (m):", _Ls_btc,
                                    index=_L_idx(_sl_cur.get("L_dan")),
                                    key=f"btc_Ld_{selected_ribbon}")
                            if st.button("✅ Áp dụng dầm nhịp dẫn", use_container_width=True,
                                         disabled=(_seld == _opts_btc[0]),
                                         key=f"btc_applyd_{selected_ribbon}"):
                                _apply_beam_to_pa(
                                    d, selected_ribbon,
                                    _beams_btc[_opts_btc.index(_seld) - 1], "dan")

                            st.markdown("**Nhịp chính** — căng giữa tĩnh không")
                            _auto_m = st.checkbox(
                                "Tự chọn chiều dài theo tĩnh không",
                                value=(not _sl_cur.get("L_main")),
                                key=f"btc_autom_{selected_ribbon}")
                            _cm1, _cm2 = st.columns([2, 1])
                            with _cm1:
                                _selm = st.selectbox(
                                    "Dầm nhịp chính:", _opts_btc,
                                    index=_beam_idx(_sl_cur.get("beam_main")),
                                    key=f"btc_beamm_{selected_ribbon}")
                            with _cm2:
                                _Lm = st.selectbox(
                                    "Chiều dài nhịp chính (m):", _Ls_btc,
                                    index=_L_idx(_sl_cur.get("L_main"), 38.2),
                                    disabled=_auto_m, key=f"btc_Lm_{selected_ribbon}")
                            _cs, _cap = st.columns(2)
                            if _cs.button("💾 Lưu bố trí 2 tầng", use_container_width=True,
                                          key=f"btc_save2_{selected_ribbon}"):
                                _new = dict(_sl_cur)
                                _new.update({"mode": "two_tier", "L_dan": float(_Ld),
                                             "L_main": (None if _auto_m else float(_Lm))})
                                _save_pa_span_layout(selected_ribbon, _new)
                                st.rerun()
                            if _cap.button("✅ Áp dụng dầm nhịp chính", use_container_width=True,
                                           type="primary", disabled=(_selm == _opts_btc[0]),
                                           key=f"btc_applym_{selected_ribbon}"):
                                _apply_beam_to_pa(
                                    d, selected_ribbon,
                                    _beams_btc[_opts_btc.index(_selm) - 1], "main")

                        # Tóm tắt + cảnh báo tĩnh không
                        try:
                            _geo_btc = d.get("geo_logic", {})
                            _x0b  = float(_geo_btc.get("x_mo_trai", -60))
                            _xeb  = float(_geo_btc.get("x_mo_phai", 60))
                            _xtb  = float(_geo_btc.get("x_tim_clearance", (_x0b + _xeb) / 2))
                            _Btk  = float(d.get("B", 20.0))
                            _sup, _Ldn = BVK.resolve_supports(d, _x0b, _xeb, _xtb, _Btk)
                            _nsp = max(0, len(_sup) - 1)
                            _mid = BVK.main_span_index(_sup, _xtb)
                            if _nsp:
                                _Lmn = _sup[_mid + 1] - _sup[_mid]
                                st.caption(
                                    f"Bố trí: **{_nsp} nhịp** · nhịp dẫn L=**{_Ldn:.1f}m** · "
                                    f"nhịp chính (#{_mid + 1}) L=**{_Lmn:.1f}m**.")
                            for _w in BVK.validate_span_layout(d, _x0b, _xeb, _xtb, _Btk):
                                st.warning("⚠️ " + _w)
                        except Exception:
                            pass

                try:
                    # ── 1. Trắc dọc cầu ──────────────────────────────────────
                    st.markdown("**Trắc dọc cầu**")
                    if not _pa3:        # PA3: cấu kiện do AI dự báo, không cho chọn
                        _pck1, _pck2 = st.columns(2)
                        with _pck1:
                            _assembly_picker(d, "tru")
                        with _pck2:
                            _assembly_picker(d, "mo")
                    _pa_obj = _resolve_assembly(d, "tru")
                    _ab_obj = _resolve_assembly(d, "mo")
                    _dc_data = st.session_state.get("dia_chat_data")
                    fig_td_btc = BVK.ve_so_do_nhip_2d(d, df_tim_line=_df_tim,
                                                       dia_chat_data=_dc_data,
                                                       pier_assembly=_pa_obj,
                                                       abutment_assembly=_ab_obj)
                    try:
                        # ve_so_do_nhip_2d KHÔNG vẽ dầm tham số → chỉ chèn dầm thư viện
                        for _td_tr in (BBUI.get_elevation_profile_traces(d, pfx=_spt_pfx) or []):
                            fig_td_btc.add_trace(_td_tr)
                    except Exception:
                        pass
                    PLOT.aspect_control(fig_td_btc, "td_btc")
                    st.plotly_chart(fig_td_btc, use_container_width=True,
                                    config={"scrollZoom": True, "displayModeBar": True})

                    # ── 2. Mặt bằng cầu ──────────────────────────────────────
                    st.markdown("**Mặt bằng cầu** (nhìn từ trên)")
                    fig_bd = BVK.ve_binh_do_2d(d, df_tim_line=_df_tim)
                    try:
                        for _bd_tr in BBUI.get_plan_beam_traces(d, pfx=_spt_pfx):
                            fig_bd.add_trace(_bd_tr)
                    except Exception:
                        pass
                    PLOT.aspect_control(fig_bd, "binh_do_btc")
                    st.plotly_chart(fig_bd, use_container_width=True,
                                    config={"scrollZoom": True, "displayModeBar": True})

                    # ── 3. MCN điển hình tại ĐẦU DẦM & GIỮA DẦM ─────────────────
                    st.markdown("**Mặt cắt ngang cầu** (kết cấu nhịp) — tại "
                                "**đầu dầm** và **giữa dầm**")
                    # Thông số clip trục y (dùng chung cho 2 hình)
                    _kcn_btc = d.get("kcn_result") or d.get("ai_result", {})
                    _H_dam_btc = float(_kcn_btc.get("chieu_cao_dam") or _kcn_btc.get("chieu_cao", 1.75))
                    _t_ban_btc = float(d.get("t_ban_mm", 200)) / 1000.0
                    _t_phu_btc = float((d.get("lop_phu_result") or {}).get("tong_day_tt", 70)) / 1000.0
                    _y_bot_btc = -(_H_dam_btc + _t_ban_btc + 0.15)   # ngay dưới đáy dầm
                    _y_top_btc = _t_phu_btc + 1.40                    # trên đỉnh lan can

                    _pa_tru_mcn = _resolve_assembly(d, "tru")

                    def _build_mcn_fig(_which):
                        _fig = BVK.ve_mat_cat_ngang_2d(d, pier_assembly=_pa_tru_mcn)
                        try:
                            # ve_mat_cat_ngang_2d KHÔNG vẽ dầm tham số (chỉ có nhãn).
                            # Chèn dầm thư viện + bỏ NHÃN "BTCT DƯL" trùng.
                            _trs = BBUI.get_mcn_overlay_traces(d, pfx=_spt_pfx, which=_which)
                            if _trs:
                                _fig.layout.annotations = tuple(
                                    a for a in (_fig.layout.annotations or [])
                                    if 'BTCT DƯL' not in str(getattr(a, 'text', ''))
                                )
                                for _tr in _trs:
                                    _fig.add_trace(_tr)
                        except Exception:
                            pass
                        _fig.update_layout(
                            yaxis=dict(range=[_y_bot_btc, _y_top_btc], autorange=False),
                            height=420,
                        )
                        return _fig

                    _mc1, _mc2 = st.columns(2)
                    with _mc1:
                        st.caption("📍 MCN tại **đầu dầm** (trên gối)")
                        _fe = _build_mcn_fig("end")
                        PLOT.aspect_control(_fe, "mcn_btc_end")
                        st.plotly_chart(_fe, use_container_width=True,
                                        config={"scrollZoom": True, "displayModeBar": True},
                                        key="mcn_btc_end")
                    with _mc2:
                        st.caption("📍 MCN tại **giữa dầm** (giữa nhịp)")
                        _fm = _build_mcn_fig("mid")
                        PLOT.aspect_control(_fm, "mcn_btc_mid")
                        st.plotly_chart(_fm, use_container_width=True,
                                        config={"scrollZoom": True, "displayModeBar": True},
                                        key="mcn_btc_mid")

                    # ── 4. Bảng KHỐI LƯỢNG cấu kiện TOÀN CẦU ─────────────────
                    st.markdown("---")
                    st.markdown("### 📊 Khối lượng cấu kiện — Toàn cầu")
                    try:
                        _kl_rows = KL.bang_toan_cau(d, dam_roles=_pa_dam_roles(d, selected_ribbon))
                        _render_kl_table(_kl_rows, key=f"kl_toancau_{selected_ribbon}")
                        st.caption("Khối lượng **sơ bộ** — cơ sở lập **dự toán** "
                                   "(xem tab **💰 Dự toán**). Hệ số cốt thép (kg/m³) theo "
                                   "cấu kiện; cọc khoan nhồi không tính ván khuôn.")
                    except Exception as _ekl:
                        st.error(f"Lỗi bảng khối lượng: {_ekl}")

                except Exception as _e:
                    st.error(f"Lỗi tab Bố trí chung: {_e}")
    
            # ── TAB 3: MCN tại vị trí mố / trụ ───────────────────────────
            with tab_mcn_vt:
                st.markdown("##### Bố hình Mố – Trụ tại từng vị trí "
                            "(mặt bằng kết cấu · mặt bằng cọc · mặt cắt ngang · mặt cắt dọc)")
                _kcn_vt = d.get("kcn_result") or d.get("ai_result", {})
                _geo_vt = d.get("geo_logic", {})
                # Bố trí nhịp ĐỀU theo catalog (đồng bộ với bản vẽ) → suy ra số trụ thực tế
                _x0_vt   = float(_geo_vt.get("x_mo_trai", -60))
                _xe_vt   = float(_geo_vt.get("x_mo_phai",  60))
                _xtim_vt = float(_geo_vt.get("x_tim_clearance", (_x0_vt + _xe_vt) / 2))
                _Lnhip_vt = float(_kcn_vt.get("chieu_dai", 33) or 33)
                _supports_vt, _ = BVK.calc_span_layout(
                    _x0_vt, _xe_vt, _xtim_vt, float(d.get("B", 20)), _Lnhip_vt
                )
                _x0_vt, _xe_vt = _supports_vt[0], _supports_vt[-1]
                _piers_vt  = _supports_vt[1:-1]
                _n_nhip_vt = len(_supports_vt) - 1
                _n_tru_vt  = len(_piers_vt)
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
                    _pos_map = {
                        "mo_trai": _x0_vt,
                        "mo_phai": _xe_vt,
                        **{f"tru_{i+1}": _piers_vt[i] for i in range(len(_piers_vt))}
                    }
                    _x_cut_show = _pos_map.get(_selected_vt, 0)
                    st.metric("Lý trình vị trí cắt", f"{_x_cut_show:.2f} m")
                    st.metric("Cao độ đáy dầm", f"{d.get('cao_day_dam', 0):.3f} m")
                    st.metric("H trụ ước tính", f"{d.get('H_tru_est', 0):.2f} m")

                # ── 🔵 Sơ đồ cọc tại vị trí — upload DXF mặt bằng + cọc xiên ──
                _vt_label_cur = _vi_tri_labels[_vt_idx]
                _render_so_do_coc_ui(d, _selected_vt, _vt_label_cur)

                st.markdown(
                    f"**Bố trí {_vt_label_cur}** — TRÁI: mặt bằng kết cấu · mặt cắt "
                    "ngang (thẳng trục Ngang cầu) | PHẢI: mặt bằng cọc · mặt cắt dọc")
                _pa_tru = _resolve_assembly(d, "tru")   # dựng 1 lần, dùng lại
                # Tầm nhìn ngang CHUNG cho 2 hình cột TRÁI → thẳng trục Ngang cầu
                _xh = max(float(d.get("bc", 12.0)) / 2.0 + 4.0, 11.0)
                # Cột TRÁI rộng (~67%): mặt bằng kết cấu trên · mặt cắt ngang dưới.
                # Cột PHẢI hẹp (~33%): mặt bằng cọc trên · mặt cắt dọc dưới.
                _colL, _colR = st.columns([2, 1], gap="medium")
                with _colL:
                    try:
                        _f_mbmt = BVK.ve_mat_bang_mo_tru(
                            d, vi_tri=_selected_vt,
                            pier_assembly=_pa_tru, x_half=_xh)
                        PLOT.aspect_control(_f_mbmt, "mb_motru")
                        st.plotly_chart(_f_mbmt,
                                        use_container_width=True,
                                        config={"scrollZoom": True, "displayModeBar": True})
                    except Exception as _e:
                        st.error(f"Lỗi vẽ mặt bằng kết cấu: {_e}")
                    try:
                        _f_mcnvt = BVK.ve_mcn_vi_tri(
                            d, vi_tri=_selected_vt, df_geology=_df_geo,
                            pier_assembly=_pa_tru, x_half=_xh)
                        PLOT.aspect_control(_f_mcnvt, "mcn_vitri")
                        st.plotly_chart(_f_mcnvt,
                                        use_container_width=True,
                                        config={"scrollZoom": True, "displayModeBar": True})
                    except Exception as _e:
                        st.error(f"Lỗi vẽ mặt cắt ngang: {_e}")
                with _colR:
                    try:
                        _f_mbc = BVK.ve_mat_bang_coc(d, vi_tri=_selected_vt)
                        PLOT.aspect_control(_f_mbc, "mb_coc")
                        st.plotly_chart(_f_mbc,
                                        use_container_width=True,
                                        config={"scrollZoom": True, "displayModeBar": True})
                    except Exception as _e:
                        st.error(f"Lỗi vẽ mặt bằng cọc: {_e}")
                    try:
                        _f_mcd = BVK.ve_mat_cat_doc_vi_tri(
                            d, vi_tri=_selected_vt, pier_assembly=_pa_tru)
                        PLOT.aspect_control(_f_mcd, "mc_doc_vitri")
                        st.plotly_chart(_f_mcd,
                                        use_container_width=True,
                                        config={"scrollZoom": True, "displayModeBar": True})
                    except Exception as _e:
                        st.error(f"Lỗi vẽ mặt cắt dọc: {_e}")

                # ── Khối lượng ĐỘC LẬP cho vị trí đang chọn (gồm cọc) ────────
                st.markdown("---")
                st.markdown(f"### 📊 Khối lượng — {_vt_label_cur} (gồm cọc)")
                try:
                    _kl_vt = KL.khoi_luong_vi_tri(d, _selected_vt)
                    _render_kl_table(_kl_vt, key=f"kl_vt_{selected_ribbon}_{_selected_vt}")
                    st.caption("Khối lượng **sơ bộ** của riêng vị trí này (thân + xà mũ/"
                               "thân mố + đài cọc + cọc).")
                except Exception as _ekl:
                    st.error(f"Lỗi bảng khối lượng vị trí: {_ekl}")

            # ── TAB: Chi tiết dầm — HIỂN THỊ KẾT QUẢ (không khai báo) ────
            with tab_spt:
                try:
                    # Nạp dầm thư viện đã áp dụng cho PA (để mặt bằng/overlay đúng)
                    _applied_id = (d.get("lib_dam_applied") or {}).get(selected_ribbon)
                    if _applied_id and st.session_state.get(f"_loaded_beam_{_spt_pfx}") != _applied_id:
                        _bm = CLIB.get_beam(st.session_state.get("dam_beams")
                                            or CLIB.load_beams(), _applied_id)
                        if _bm:
                            st.session_state[f"{_spt_pfx}_beam_type"] = _bm.get("loai_dam", "Super-T")
                            BBUI.import_beam_state(
                                BBUI.effective_pfx(_spt_pfx, _bm.get("loai_dam")), _bm)
                            st.session_state[f"_loaded_beam_{_spt_pfx}"] = _applied_id

                    st.markdown("##### 🔩 Chi tiết dầm — Kết quả")
                    st.caption("Tab này HIỂN THỊ kết quả chi tiết dầm của phương án "
                               "(việc dựng/khai báo dầm làm ở **📚 Thư viện → Dầm**).")

                    # ① Mặt bằng bố trí dầm theo từng nhịp
                    st.markdown("**① Mặt bằng bố trí dầm theo nhịp**")
                    try:
                        _fig_plan = BVK.ve_binh_do_2d(d, df_tim_line=_df_tim)
                        try:
                            for _ptr in BBUI.get_plan_beam_traces(d, pfx=_spt_pfx):
                                _fig_plan.add_trace(_ptr)
                        except Exception:
                            pass
                        PLOT.aspect_control(_fig_plan, f"ctd_plan_{selected_ribbon}")
                        st.plotly_chart(_fig_plan, use_container_width=True,
                                        config={"scrollZoom": True, "displayModeBar": True},
                                        key=f"ctd_plan_{selected_ribbon}")
                    except Exception as _ep:
                        st.error(f"Lỗi mặt bằng bố trí dầm: {_ep}")

                    # ② Khối lượng dầm theo loại (toàn cầu)
                    st.markdown("**② Khối lượng dầm theo loại** (toàn cầu)")
                    try:
                        _render_kl_table(
                            KL.bang_dam(d, dam_roles=_pa_dam_roles(d, selected_ribbon)),
                            key=f"kl_dam_{selected_ribbon}")
                    except Exception as _ekl:
                        st.error(f"Lỗi bảng khối lượng dầm: {_ekl}")

                    # ③ Chi tiết MCN · mặt cắt dọc · mặt bằng theo từng loại dầm
                    st.markdown("---")
                    st.markdown("**③ Mặt cắt ngang · mặt cắt dọc · mặt bằng — theo từng loại dầm**")
                    _sl_ctd    = _pa_span_layout(selected_ribbon)
                    _beams_ctd = st.session_state.get("dam_beams") or CLIB.load_beams()
                    _kcn_ctd   = dict(d.get("kcn_result") or d.get("ai_result") or {})

                    # Thu thập vai trò dầm (nhịp dẫn / nhịp chính) + bản ghi thư viện
                    _roles = []
                    if _sl_ctd.get("mode") == "two_tier":
                        _roles.append(("Nhịp dẫn",
                                       CLIB.get_beam(_beams_ctd, _sl_ctd.get("beam_dan")),
                                       _sl_ctd.get("L_dan")))
                        _roles.append(("Nhịp chính",
                                       CLIB.get_beam(_beams_ctd, _sl_ctd.get("beam_main")),
                                       _sl_ctd.get("L_main")))
                    else:
                        _bid = _sl_ctd.get("beam_dan") or _applied_id
                        _roles.append(("Dầm",
                                       CLIB.get_beam(_beams_ctd, _bid) if _bid else None,
                                       _sl_ctd.get("L_dan")))

                    # Khử trùng theo (loại, chiều dài) để không vẽ lặp
                    def _pick_lib_beam(_beams, _loai, _L):
                        """Tự khớp dầm thư viện theo loại + chiều dài gần nhất."""
                        _cs = [b for b in (_beams or []) if b.get("sections")
                               and str(b.get("loai_dam", "")).lower() == str(_loai).lower()]
                        if not _cs:
                            _cs = [b for b in (_beams or []) if b.get("sections")]
                        if not _cs:
                            return None
                        return min(_cs, key=lambda b: abs(
                            float(b.get("chieu_dai", 0) or 0) - float(_L or 0)))

                    _seen = set(); _shown = 0
                    for _ri, (_lbl, _brec, _Lr) in enumerate(_roles):
                        _loai_r = ((_brec.get("loai_dam") if _brec else None)
                                   or _kcn_ctd.get("loai_dam") or "Super-T")
                        _Lval = float(_Lr or (_brec or {}).get("chieu_dai")
                                      or _kcn_ctd.get("chieu_dai", 38.0) or 38.0)
                        # Chưa áp dụng dầm cụ thể → tự khớp dầm thư viện (để 3D đúng)
                        if not (_brec and _brec.get("sections")):
                            _auto = _pick_lib_beam(_beams_ctd, _loai_r, _Lval)
                            if _auto:
                                _brec = _auto
                                _loai_r = _auto.get("loai_dam") or _loai_r
                        _sig = (str(_loai_r).lower(), round(_Lval, 1))
                        if _sig in _seen:
                            continue
                        _seen.add(_sig)
                        _ten_r = (_brec or {}).get("ten", "")
                        st.markdown(f"#### 🌉 {_lbl}"
                                    + (f" — {_ten_r}" if _ten_r else "")
                                    + f"  ·  *{_loai_r}* · L={_Lval:.1f}m")
                        _kcn_r = dict(_kcn_ctd)
                        _kcn_r["loai_dam"]  = _loai_r
                        _kcn_r["chieu_dai"] = _Lval
                        if _brec:
                            if _brec.get("chieu_cao"):
                                _kcn_r["chieu_cao_dam"] = float(_brec["chieu_cao"])
                            if _brec.get("khoang_cach_dam"):
                                _kcn_r["khoang_cach_dam"] = float(_brec["khoang_cach_dam"])
                            if _brec.get("so_luong_dam"):
                                _kcn_r["so_luong_dam"] = int(_brec["so_luong_dam"])
                        _d_role = {**d, "kcn_result": _kcn_r, "ai_result": _kcn_r}
                        # 2D + 3D từ MÔ HÌNH DẦM THƯ VIỆN (thay hình tham số cũ)
                        _bfigs = {}
                        if _brec and (_brec.get("sections")):
                            try:
                                _bfigs = BBUI.beam_record_figs(_brec)
                            except Exception:
                                _bfigs = {}
                        try:
                            CTD.render_chi_tiet_loai(
                                _d_role, st, _loai_r,
                                key_prefix=f"ctd_{selected_ribbon}_{_ri}",
                                beam_figs=_bfigs)
                            _shown += 1
                        except Exception as _er:
                            st.error(f"Lỗi chi tiết {_lbl}: {_er}")
                    if _shown == 0:
                        st.info("Chưa xác định được loại dầm. Áp dụng dầm cho phương án "
                                "ở tab **📋 Bố trí chung**, hoặc tạo dầm trong **📚 Thư viện**.")
                except Exception as _e:
                    import traceback
                    st.error(f"Lỗi tab Chi tiết dầm: {_e}")
                    with st.expander("Chi tiết lỗi"):
                        st.code(traceback.format_exc())

            # ── TAB: THKL — Thống kê khối lượng toàn cầu (dạng bảng Excel) ──
            with tab_thkl:
                st.markdown("##### 📊 Thống kê khối lượng toàn cầu — " + selected_ribbon)
                st.caption("Tổng hợp khối lượng các hạng mục cho **toàn cầu** "
                           "(số lượng · bê tông · ván khuôn · cốt thép). Tải về **.xlsx** để dùng tiếp.")
                try:
                    _thkl_rows = KL.bang_toan_cau(d, dam_roles=_pa_dam_roles(d, selected_ribbon))
                    _tt = KL.tong_hop(_thkl_rows)
                    _df_thkl = pd.DataFrame([{
                        "TT":             i + 1,
                        "Hạng mục":       r["ten"],
                        "Số lượng":       str(r["so_luong"]),
                        "Bê tông (m³)":   r["bt_m3"],
                        "Ván khuôn (m²)": r["coppha_m2"],
                        "Cốt thép (kg)":  r["thep_kg"],
                        "Ghi chú":        r.get("ghi_chu", ""),
                    } for i, r in enumerate(_thkl_rows)])
                    # Dòng TỔNG CỘNG
                    _df_thkl.loc[len(_df_thkl)] = {
                        "TT": "", "Hạng mục": "TỔNG CỘNG", "Số lượng": "",
                        "Bê tông (m³)": _tt["bt_m3"], "Ván khuôn (m²)": _tt["coppha_m2"],
                        "Cốt thép (kg)": _tt["thep_kg"], "Ghi chú": "",
                    }
                    st.dataframe(_df_thkl, use_container_width=True, hide_index=True,
                                 key=f"thkl_table_{selected_ribbon}")
                    _c1, _c2, _c3 = st.columns(3)
                    _c1.metric("Σ Bê tông",  f"{_tt['bt_m3']:.1f} m³")
                    _c2.metric("Σ Ván khuôn", f"{_tt['coppha_m2']:.0f} m²")
                    _c3.metric("Σ Cốt thép",  f"{_tt['thep_kg']/1000:.2f} tấn")
                    # Xuất .xlsx
                    try:
                        _xbuf = io.BytesIO()
                        with pd.ExcelWriter(_xbuf, engine="openpyxl") as _xw:
                            _df_thkl.to_excel(_xw, index=False, sheet_name="THKL_toan_cau")
                        st.download_button(
                            "⬇️ Tải bảng THKL (.xlsx)", data=_xbuf.getvalue(),
                            file_name=f"THKL_{selected_ribbon.replace(' ', '_')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"thkl_xlsx_{selected_ribbon}")
                    except Exception as _ex:
                        st.caption(f"(Không xuất được .xlsx: {_ex})")
                except Exception as _e:
                    st.error(f"Lỗi THKL: {_e}")

            # ── TAB: Xuất bản vẽ ───────────────────────────────────────────
            with tab_export:
                @_maybe_fragment
                def _export_frag():
                    st.subheader("📤 Xuất hồ sơ — chọn theo cây thư mục")
                    st.caption("Tích chọn các phần cần lấy theo **thư mục**, rồi "
                               "**📦 Đóng gói (.zip)** — cấu trúc thư mục được giữ "
                               "nguyên trong gói tải về. Tệp nặng (IFC/địa hình) chỉ "
                               "được tạo khi bấm đóng gói.")
                    _PA_TAG = selected_ribbon.replace(" ", "_")

                    def _terrain_ifc_bytes():
                        if _df_geo is None or getattr(_df_geo, "empty", True):
                            return None
                        import tempfile as _tmp
                        _, _mx, _my, _mz = TV.ve_dia_hinh_3d(
                            _df_geo, he_so_z=1.0, che_do="Bề mặt mịn", do_min=3)
                        _p = os.path.join(_tmp.gettempdir(), "terrain_export.ifc")
                        if TV.export_terrain_to_ifc(_mx, _my, _mz, _p, "DiaHinh_KhaoSat"):
                            with open(_p, "rb") as _fh:
                                return _fh.read()
                        return None

                    # Cây xuất 3 cấp: (thư mục, dir, [ (cấu kiện, sub_dir,
                    #   [ (id, định dạng, tệp, producer) ]) ]). Quy ước: 2D→DXF, 3D→IFC.
                    _exp_tree = [
                        ("🌉 Kết cấu cầu", "KetCauCau", [
                            ("Mặt cắt ngang", "MatCatNgang", [
                                ("mcn2d", "2D — DXF",            "mat_cat_ngang.dxf",
                                 lambda: EXP.export_mcn_dxf(d)),
                                ("mcn3d", "3D — IFC (kéo dọc cầu)", "mat_cat_ngang_3d.ifc",
                                 lambda: EXP.export_bridge_ifc(d)),
                            ]),
                            ("Trắc dọc", "TracDoc", [
                                ("td2d", "2D — DXF", "trac_doc.dxf",
                                 lambda: EXP.export_trac_doc_dxf(d)),
                            ]),
                            ("Trụ cầu", "Tru", [
                                ("tru2d", "2D — DXF", "tru.dxf",
                                 lambda: EXP.export_tru_dxf(d)),
                                ("tru3d", "3D — IFC", "tru.ifc",
                                 lambda: EXP.export_pier_ifc(d)),
                            ]),
                            ("Kết cấu toàn cầu", "ToanCau", [
                                ("cau3d", "3D — IFC", "ket_cau_cau.ifc",
                                 lambda: EXP.export_bridge_ifc(d)),
                            ]),
                        ]),
                        ("🗺️ Địa hình", "DiaHinh", [
                            ("Địa hình khảo sát", "KhaoSat", [
                                ("dh3d", "3D — IFC", "dia_hinh.ifc", _terrain_ifc_bytes),
                            ]),
                        ]),
                        ("📚 Dữ liệu / Thư viện", "DuLieu", [
                            ("Thư viện cấu kiện", "ThuVien", [
                                ("lib", "Toàn bộ (JSON)", "thu_vien.json",
                                 lambda: json.dumps(CLIB.export_bundle(), ensure_ascii=False,
                                                    indent=2).encode("utf-8")),
                            ]),
                            ("Phương án", "PhuongAn", [
                                ("par", "Thông số & kết quả (JSON)", "thong_so_phuong_an.json",
                                 lambda: json.dumps(
                                     {k: d.get(k) for k in
                                      ("bc", "B", "H", "vtk", "kcn_result", "tru_result",
                                       "mong_result", "lop_phu_result", "geo_logic", "span_layout")},
                                     ensure_ascii=False, indent=2, default=str).encode("utf-8")),
                            ]),
                        ]),
                    ]

                    # Tất cả key (3 cấp) — phục vụ nút chọn/bỏ chọn tất cả
                    _all_keys = [f"exp_{_PA_TAG}_{_id}"
                                 for _, _, _subs in _exp_tree
                                 for _, _, _fmts in _subs
                                 for _id, *_ in _fmts]
                    _bt1, _bt2, _ = st.columns([1, 1, 3])
                    if _bt1.button("✅ Chọn tất cả", key=f"exp_selall_{_PA_TAG}",
                                   use_container_width=True):
                        for _k in _all_keys:
                            st.session_state[_k] = True
                        st.rerun()
                    if _bt2.button("⬜ Bỏ chọn", key=f"exp_selnone_{_PA_TAG}",
                                   use_container_width=True):
                        for _k in _all_keys:
                            st.session_state[_k] = False
                        st.rerun()

                    _sel_items = []     # (dir_đầy_đủ, fname, producer, label)
                    for _flabel, _fdir, _subs in _exp_tree:
                        _ids_in = [f"exp_{_PA_TAG}_{_id}"
                                   for _, _, _fmts in _subs for _id, *_ in _fmts]
                        _n_on = sum(1 for _k in _ids_in if st.session_state.get(_k))
                        with st.expander(f"{_flabel}  ({_n_on}/{len(_ids_in)})", expanded=True):
                            for _slabel, _sdir, _fmts in _subs:
                                st.markdown(f"**↳ {_slabel}**")
                                for _id, _fmtlbl, _fn, _mk in _fmts:
                                    if st.checkbox(
                                            f"　{_fmtlbl}  ·  `{_fdir}/{_sdir}/{_fn}`",
                                            key=f"exp_{_PA_TAG}_{_id}"):
                                        _sel_items.append(
                                            (f"{_fdir}/{_sdir}", _fn, _mk,
                                             f"{_slabel} · {_fmtlbl}"))

                    st.markdown("---")
                    _cz1, _cz2 = st.columns([1, 1])
                    if _cz1.button(f"📦 Đóng gói {len(_sel_items)} mục đã chọn (.zip)",
                                   type="primary", use_container_width=True,
                                   disabled=(not _sel_items), key=f"exp_zip_{_PA_TAG}"):
                        _buf = io.BytesIO(); _ok = []; _err = []
                        with zipfile.ZipFile(_buf, "w", zipfile.ZIP_DEFLATED) as _zf:
                            for _fdir, _fn, _mk, _lbl in _sel_items:
                                try:
                                    _b = _mk()
                                    if _b:
                                        _zf.writestr(f"{_fdir}/{_fn}", _b); _ok.append(_lbl)
                                    else:
                                        _err.append(f"{_lbl} (không có dữ liệu)")
                                except Exception as _ex:
                                    _err.append(f"{_lbl}: {_ex}")
                        st.session_state[f"_exp_zip_{_PA_TAG}"] = _buf.getvalue()
                        st.session_state[f"_exp_zip_sum_{_PA_TAG}"] = (_ok, _err)
                        st.rerun()

                    _zbytes = st.session_state.get(f"_exp_zip_{_PA_TAG}")
                    if _zbytes:
                        _ok, _err = st.session_state.get(f"_exp_zip_sum_{_PA_TAG}", ([], []))
                        if _ok:
                            st.success("✅ Đã đóng gói: " + ", ".join(_ok))
                        if _err:
                            st.warning("⚠️ Bỏ qua: " + "; ".join(_err))
                        _cz2.download_button(
                            "⬇️ Tải gói .zip", data=_zbytes,
                            file_name=f"ho_so_{_PA_TAG}.zip", mime="application/zip",
                            use_container_width=True, key=f"exp_dl_{_PA_TAG}")
                _export_frag()

            # ── TAB CUỐI: Dự toán (từ bảng khối lượng toàn cầu) ──────────
            with tab_dutoan:
                st.markdown("##### 💰 Dự toán sơ bộ — " + selected_ribbon)
                st.caption("Lấy **bảng khối lượng toàn cầu** (tab Bố trí chung) × "
                           "**đơn giá** → thành tiền từng cấu kiện và tổng công trình.")
                try:
                    _kl_dt = KL.bang_toan_cau(d, dam_roles=_pa_dam_roles(d, selected_ribbon))
                    _dgc1, _dgc2, _dgc3 = st.columns(3)
                    _dg_bt = _dgc1.number_input(
                        "Đơn giá bê tông (đ/m³)", 0, 20_000_000,
                        KL.DON_GIA_MAC_DINH["bt"], 50_000, key=f"dg_bt_{selected_ribbon}")
                    _dg_vk = _dgc2.number_input(
                        "Đơn giá ván khuôn (đ/m²)", 0, 5_000_000,
                        KL.DON_GIA_MAC_DINH["vk"], 10_000, key=f"dg_vk_{selected_ribbon}")
                    _dg_th = _dgc3.number_input(
                        "Đơn giá cốt thép (đ/kg)", 0, 200_000,
                        KL.DON_GIA_MAC_DINH["thep"], 500, key=f"dg_th_{selected_ribbon}")
                    _dt_rows, _tong_tien = KL.du_toan(_kl_dt, _dg_bt, _dg_vk, _dg_th)
                    _df_dt = pd.DataFrame([{
                        "Cấu kiện":       r["ten"],
                        "Số lượng":       r["so_luong"],
                        "Bê tông (m³)":   r["bt_m3"],
                        "Ván khuôn (m²)": r["coppha_m2"],
                        "Cốt thép (kg)":  r["thep_kg"],
                        "Thành tiền (đ)": f"{r['thanh_tien']:,.0f}",
                    } for r in _dt_rows])
                    st.dataframe(_df_dt, use_container_width=True, hide_index=True,
                                 key=f"dt_table_{selected_ribbon}")
                    st.success(f"**Σ Tổng dự toán sơ bộ: {_tong_tien:,.0f} đ "
                               f"≈ {_tong_tien/1e9:.3f} tỷ đồng** "
                               f"(chưa gồm phụ trợ, thiết bị, các hệ số chi phí).")
                except Exception as _edt:
                    st.error(f"Lỗi dự toán: {_edt}")

    # =========================================================================
    # SO SÁNH PHƯƠNG ÁN
    # =========================================================================
    elif selected_ribbon == "SO SÁNH PHƯƠNG ÁN":
        _s2 = tab_states['tab2']
        if _s2 == 'done':
            st.markdown(
                DS.banner("success", "Đã có 3 phương án — đang hiển thị kết quả so sánh."),
                unsafe_allow_html=True,
            )
        elif _s2 == 'partial':
            st.markdown(
                DS.banner("warning",
                          "Đã có kết quả kết cấu nhịp",
                          "Chạy lại pipeline đầy đủ để sinh so sánh 3 phương án"),
                unsafe_allow_html=True,
            )
    
        alts = st.session_state.get("alternatives", None)
        if alts is None:
            st.markdown(
                DS.section_header(
                    title = "So sánh 3 Phương án Loại Dầm",
                    icon  = "📊",
                    sub   = "Hệ thống sẽ tính toán cùng một cầu với 3 loại dầm, so sánh kỹ thuật + kinh tế",
                ),
                unsafe_allow_html=True,
            )
            _es = DS.empty_state(
                icon      = "📊",
                title     = "Chưa có dữ liệu so sánh",
                desc      = ("Nhấn <b>⚙️ OPTIONS</b> → điền thông số → "
                             "<b>🚀 Chạy AI</b> để sinh 3 phương án tự động."),
                cta_label = "⚙️ Mở OPTIONS",
                cta_key   = "es_open_opts_ss",
                variant   = "locked",
            )
            st.markdown(_es["html"], unsafe_allow_html=True)
            if _es["show_cta"]:
                _, _mc, _ = st.columns([1.5, 1, 1.5])
                with _mc:
                    if st.button(_es["cta_label"], key=_es["cta_key"],
                                 use_container_width=True, type="secondary"):
                        st.session_state.open_dialog = "step1"
                        st.session_state.field_touched = set()
                        st.session_state.field_errors = {}
                        st.session_state.field_warnings = {}
                        st.rerun()
            st.markdown(
                DS.section_header(
                    title = "Giới thiệu 3 phương án so sánh",
                    icon  = "ℹ️",
                ),
                unsafe_allow_html=True,
            )
            st.caption("Sau khi pipeline chạy xong, hệ thống hiển thị bảng so sánh kỹ thuật, radar chart và phân tích chi phí.")
    
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
                ("📊", "Bảng đa tiêu chí\nKCN · Trụ · Móng"),
                ("💰", "Chi phí tương đối\n(Dầm I = 100%)"),
                ("📊", "Biểu đồ radar\n5 tiêu chí đánh giá"),
                ("⚖️", "So sánh loại trụ\nvà phương án móng"),
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

    elif selected_ribbon == "THƯ VIỆN":
        try:
            render_thu_vien()
        except Exception as _cl_err:
            st.error(f"Lỗi Thư viện cấu kiện: {_cl_err}")
            import traceback
            st.code(traceback.format_exc())

_render_statusbar(st.session_state.design_data)
