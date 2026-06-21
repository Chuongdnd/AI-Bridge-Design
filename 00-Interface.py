import streamlit as st
import pandas as pd
import numpy as np
import os
import importlib
import time
import google.generativeai as genai
import fitz
try:
    from streamlit_option_menu import option_menu
    _HAS_OPTION_MENU = True
except ImportError:
    _HAS_OPTION_MENU = False
import plotly.graph_objects as go

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

/* ── Sidebar ── */
[data-testid="stSidebar"] { min-width: 300px !important; max-width: 300px !important; }
[data-testid="stSidebar"] > div:first-child { padding: 56px 14px 32px !important; }
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
    left: 300px !important;
    right: 0 !important;
    z-index: 501 !important;
    height: 44px !important;
    margin: 0 !important;
    padding: 0 !important;
    gap: 0 !important;
    background: transparent !important;
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
    TC   = importlib.import_module("04-Pier-test")
    LPC  = importlib.import_module("10-LopPhu_MatCau")  # Lớp phủ mặt cầu
    BVK  = importlib.import_module("11-BanVe_KetCau")   # Bản vẽ kết cấu 2D/3D
    SSP  = importlib.import_module("09-So_Sanh_PA")     # So sánh 3 phương án
    CTD  = importlib.import_module("12-ChiTiet_Dam")    # Chi tiết dầm
    BDE  = importlib.import_module("06d-BeamDimEditor") # Chỉnh sửa kích thước dầm
    importlib.reload(PLOT)
    importlib.reload(BVK)
    importlib.reload(CTD)
    importlib.reload(BDE)

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

if 'wizard_step' not in st.session_state:
    st.session_state.wizard_step = 1

if 'wizard_draft' not in st.session_state:
    st.session_state.wizard_draft = {}

if 'wizard_errors' not in st.session_state:
    st.session_state.wizard_errors = {}

if 'field_touched' not in st.session_state:
    st.session_state.field_touched = set()

if 'field_errors' not in st.session_state:
    st.session_state.field_errors = {}

if 'field_warnings' not in st.session_state:
    st.session_state.field_warnings = {}

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
# ⚙️ WIZARD KHAI BÁO SỐ LIỆU — 3 BƯỚC
# =========================================================================
def _render_wizard_progress(current: int, steps: list):
    cols = st.columns(len(steps))
    for i, (col, label) in enumerate(zip(cols, steps), 1):
        with col:
            if i < current:
                st.markdown(
                    f"<div style='text-align:center;padding:8px 4px;"
                    f"background:#0d3d1f;border:1px solid #2ecc71;border-radius:8px'>"
                    f"<div style='font-size:16px'>✅</div>"
                    f"<div style='font-size:11px;color:#2ecc71;font-weight:600'>Bước {i}</div>"
                    f"<div style='font-size:10px;color:#aaa'>{label}</div></div>",
                    unsafe_allow_html=True,
                )
            elif i == current:
                st.markdown(
                    f"<div style='text-align:center;padding:8px 4px;"
                    f"background:#1a2d45;border:2px solid #007acc;border-radius:8px'>"
                    f"<div style='font-size:16px'>▶️</div>"
                    f"<div style='font-size:11px;color:#4fc3f7;font-weight:700'>Bước {i} — Hiện tại</div>"
                    f"<div style='font-size:10px;color:#ccc'>{label}</div></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='text-align:center;padding:8px 4px;"
                    f"background:#1a1a2a;border:1px solid #333355;border-radius:8px;opacity:0.6'>"
                    f"<div style='font-size:16px'>○</div>"
                    f"<div style='font-size:11px;color:#888'>Bước {i}</div>"
                    f"<div style='font-size:10px;color:#666'>{label}</div></div>",
                    unsafe_allow_html=True,
                )
    st.markdown("<hr style='margin:12px 0 16px;border-color:#333'>", unsafe_allow_html=True)


def _validate_step1(draft: dict) -> dict:
    errs = {}
    h1  = draft.get('h1',  0.0)
    h5  = draft.get('h5',  0.0)
    h10 = draft.get('h10', 0.0)
    h98 = draft.get('h98', 0.0)
    if h1 <= h5:
        errs['h1']  = f"MNCN ({h1}) phải LỚN HƠN MNTT ({h5})"
    if h5 <= h10:
        errs['h5']  = f"MNTT ({h5}) phải LỚN HƠN MNTC ({h10})"
    if h10 <= h98:
        errs['h10'] = f"MNTC ({h10}) phải LỚN HƠN MNTN ({h98})"
    if draft.get('x_tim_clearance', 0) == 0:
        errs['x_tim'] = "Lý trình tim cầu chưa được nhập"
    return errs


def _validate_step2(draft: dict) -> dict:
    errs = {}
    vtk = draft.get('vtk', 0)
    if vtk <= 0:
        errs['vtk'] = "Vận tốc thiết kế phải lớn hơn 0"
    bc = draft.get('bc', 0.0)
    if bc < 3.5:
        errs['bc'] = f"Chiều rộng cầu {bc}m có vẻ quá nhỏ (thông thường ≥ 7m)"
    return errs


@st.dialog("⚙️ KHAI BÁO THÔNG SỐ THIẾT KẾ", width="large")
def show_options_dialog():
    STEP_LABELS = ["Thủy văn & Vị trí", "Hình học tuyến", "Xem lại & Chạy AI"]
    step  = st.session_state.wizard_step
    draft = st.session_state.wizard_draft

    _render_wizard_progress(step, STEP_LABELS)

    # ═══════════════════════════════════════════════════════════════════
    # BƯỚC 1 — THỦY VĂN & VỊ TRÍ
    # ═══════════════════════════════════════════════════════════════════
    if step == 1:
        st.markdown(
            DS.section_header(
                title = "Thông số thủy văn & vị trí cầu",
                icon  = "🌊",
                sub   = "Phạm vi đề tài: Cầu vượt sông/kênh cấp IV–VI (TCVN 8818:2022)",
            ),
            unsafe_allow_html=True,
        )

        # Banner tổng hợp (chỉ hiện sau lần touched đầu tiên)
        _touched_step1 = st.session_state.field_touched & {
            'wz_h1', 'wz_h5', 'wz_h10', 'wz_h98', 'wz_xtim', 'wz_goc', 'wz_tban'
        }
        if _touched_step1:
            _render_step_status_banner(
                errors={k: v for k, v in st.session_state.field_errors.items()
                        if k.startswith('wz_')},
                warnings={k: v for k, v in st.session_state.field_warnings.items()
                          if k.startswith('wz_')},
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
                key="wz_mien",
            )
            cap_s = st.selectbox(
                "Cấp sông ỐTN:",
                ["4", "5", "6", "3", "2", "1"],
                index=["4","5","6","3","2","1"].index(str(draft.get('cap_s', '4'))),
                format_func=lambda x: f"Cấp {['I','II','III','IV','V','VI'][int(x)-1]}",
                key="wz_caps",
            )
            loai_h = st.selectbox(
                "Loại hình thủy văn:",
                ["1", "2"],
                index=0 if draft.get('loai_h', '2') == '1' else 1,
                format_func=lambda x: "Kênh đào" if x == "1" else "Sông tự nhiên",
                key="wz_loaih",
            )
            goc_giao = _field_with_feedback(
                label     = "Góc giao chéo (độ)",
                value     = float(draft.get('goc_giao', st.session_state.design_data.get('goc_giao', 90.0))),
                key       = "wz_goc",
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
                key       = "wz_xtim",
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
                key       = "wz_h1",
                check_fn  = VAL.check_h1,
                check_args= (float(draft.get('h5', _d.get('MNTT', 2.00))),),
                help_txt  = "Mực nước cao nhất tần suất 1% — dùng tính an toàn va tàu",
            )
            h5 = _field_with_feedback(
                label     = "MNTT — Mực nước thông thuyền H5% (m)",
                value     = float(draft.get('h5', _d.get('MNTT', 2.00))),
                key       = "wz_h5",
                check_fn  = VAL.check_h5,
                check_args= (h1, float(draft.get('h10', _d.get('MNTC', 1.50)))),
                help_txt  = "Mực nước thông thuyền — dùng tính chiều cao tĩnh không H",
            )
            h10 = _field_with_feedback(
                label     = "MNTC — Mực nước thi công H10% (m)",
                value     = float(draft.get('h10', _d.get('MNTC', 1.50))),
                key       = "wz_h10",
                check_fn  = VAL.check_h10,
                check_args= (h5, float(draft.get('h98', _d.get('MNTN', 0.50)))),
                help_txt  = "Mực nước thi công tần suất 10%",
            )
            h98 = _field_with_feedback(
                label     = "MNTN — Mực nước thấp nhất H98% (m)",
                value     = float(draft.get('h98', _d.get('MNTN', 0.50))),
                key       = "wz_h98",
                check_fn  = VAL.check_h98,
                check_args= (h10,),
                help_txt  = "Mực nước kiệt tần suất 98% — dùng ước tính chiều cao trụ",
            )

            st.markdown("**🛣️ Bản mặt cầu**")
            t_ban_mm = _field_with_feedback(
                label     = "Chiều dày bản mặt cầu (mm)",
                value     = float(draft.get('t_ban_mm', _d.get('t_ban_mm', 200))),
                key       = "wz_tban",
                check_fn  = VAL.check_t_ban,
                check_args= (),
                fmt       = "%.0f",
                min_val   = 150.0,
                max_val   = 400.0,
                step      = 5.0,
                help_txt  = "Tối thiểu 175mm — TCVN 11823-2017 Điều 9.7.1.1",
                unit      = "mm",
            )

        # Disable nút Tiếp nếu còn lỗi cứng
        _has_hard_errors = any(
            k in st.session_state.field_errors
            for k in ['wz_h1', 'wz_h5', 'wz_h10', 'wz_h98', 'wz_xtim', 'wz_goc', 'wz_tban']
        )

        st.markdown("<br>", unsafe_allow_html=True)
        _, btn_col = st.columns([3, 1])
        with btn_col:
            if st.button(
                "Tiếp theo ▶",
                use_container_width=True,
                type="primary",
                disabled=_has_hard_errors,
                key="wz_next1",
                help="Sửa hết lỗi đỏ trước khi sang bước tiếp theo" if _has_hard_errors else "",
            ):
                st.session_state.wizard_draft.update({
                    'mien': mien, 'cap_s': cap_s, 'loai_h': loai_h,
                    'goc_giao': goc_giao, 'x_tim_clearance': x_tim_clearance,
                    'h1': h1, 'h5': h5, 'h10': h10, 'h98': h98,
                    't_ban_mm': int(t_ban_mm),
                })
                st.session_state.wizard_step = 2
                st.rerun()

    # ═══════════════════════════════════════════════════════════════════
    # BƯỚC 2 — HÌNH HỌC TUYẾN
    # ═══════════════════════════════════════════════════════════════════
    elif step == 2:
        st.markdown(
            DS.section_header(
                title = "Tiêu chuẩn hình học tuyến đường",
                icon  = "🛣️",
                sub   = "Chọn loại đường, vận tốc thiết kế và nhập bề rộng cầu",
            ),
            unsafe_allow_html=True,
        )

        # Khởi tạo defaults — sẽ được ghi đè trong từng nhánh
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

        # Lưu draft trên mỗi rerun của bước 2
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
            if st.button("◀ Quay lại", use_container_width=True, key="wz_back2"):
                st.session_state.wizard_step = 1
                st.rerun()
        with btn_f:
            if st.button("Tiếp theo ▶", use_container_width=True, type="primary", key="wz_next2"):
                errs = _validate_step2(st.session_state.wizard_draft)
                st.session_state.wizard_errors['step2'] = errs
                if not errs:
                    st.session_state.wizard_step = 3
                    st.rerun()
                else:
                    for msg in errs.values():
                        st.error(f"⚠️ {msg}")

    # ═══════════════════════════════════════════════════════════════════
    # BƯỚC 3 — XEM LẠI & CHẠY AI
    # ═══════════════════════════════════════════════════════════════════
    elif step == 3:
        st.markdown(
            DS.section_header(
                title = "Xem lại thông số & Chạy tính toán",
                icon  = "✅",
                sub   = "Kiểm tra lại toàn bộ trước khi chạy pipeline AI",
            ),
            unsafe_allow_html=True,
        )

        draft = st.session_state.wizard_draft

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
            if st.button("✏️ Sửa thủy văn", key="wz_edit1", use_container_width=True):
                st.session_state.wizard_step = 1
                st.rerun()
        with ed2:
            if st.button("✏️ Sửa hình học", key="wz_edit2", use_container_width=True):
                st.session_state.wizard_step = 2
                st.rerun()

        st.markdown("---")
        st.markdown("**📋 Điều kiện địa phương**")
        is_urban_chk = st.checkbox(
            "Khu vực đông dân cư (hạn chế tiếng ồn/rung)",
            value=bool(draft.get('is_urban', st.session_state.design_data.get('is_urban', 0))),
            help="Ảnh hưởng đến lựa chọn loại cọc: khu đông dân → ưu tiên cọc ép",
            key="wz_urban",
        )
        st.session_state.wizard_draft['is_urban'] = int(is_urban_chk)

        st.markdown("<br>", unsafe_allow_html=True)
        back_col, run_col = st.columns([1, 2])
        with back_col:
            if st.button("◀ Quay lại", use_container_width=True, key="wz_back3"):
                st.session_state.wizard_step = 2
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
                key="wz_submit",
            )

        if submitted:
            st.session_state.wizard_step   = 1
            st.session_state.wizard_errors = {}

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

            # Re-compute terrain data từ session state
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

            # ── Khởi tạo tracker ─────────────────────────────────────────────────
            tracker = PipelineTracker(PIPELINE_STEPS)
            tracker.setup()
            pipeline_ok = True
            kcn_models  = None
            pier_models = None
            fnd_models  = None

            # ══════════════════════════════════════════════════════════════════
            # BƯỚC 1 — TĨNH KHÔNG
            # ══════════════════════════════════════════════════════════════════
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

            # ══════════════════════════════════════════════════════════════════
            # BƯỚC 2 — YẾU TỐ HÌNH HỌC  (critical)
            # ══════════════════════════════════════════════════════════════════
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

            # ══════════════════════════════════════════════════════════════════
            # BƯỚC 3 — AI KẾT CẤU NHỊP
            # ══════════════════════════════════════════════════════════════════
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

            # ══════════════════════════════════════════════════════════════════
            # BƯỚC 4 — AI MỐ – TRỤ
            # ══════════════════════════════════════════════════════════════════
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

            # ══════════════════════════════════════════════════════════════════
            # BƯỚC 5 — AI MÓNG CẦU
            # ══════════════════════════════════════════════════════════════════
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

            # ══════════════════════════════════════════════════════════════════
            # BƯỚC 6 — LỚP PHỦ MẶT CẦU
            # ══════════════════════════════════════════════════════════════════
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

            # ══════════════════════════════════════════════════════════════════
            # BƯỚC 7 — BẢN VẼ KẾT CẤU
            # ══════════════════════════════════════════════════════════════════
            tracker.start("BVK")
            try:
                importlib.reload(BVK)
                importlib.reload(CTD)
                tracker.done("BVK", "Bản vẽ 2D/3D đã sẵn sàng")
            except Exception as _e:
                tracker.error("BVK", str(_e))

            # Lưu design_data trước khi chạy SSP
            if pipeline_ok:
                st.session_state.design_data = res

            # ══════════════════════════════════════════════════════════════════
            # BƯỚC 8 — SO SÁNH 3 PHƯƠNG ÁN
            # ══════════════════════════════════════════════════════════════════
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

            # ══════════════════════════════════════════════════════════════════
            # KẾT THÚC PIPELINE
            # ══════════════════════════════════════════════════════════════════
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
                st.session_state.current_tab = "BẢN VẼ KỸ THUẬT"
                st.rerun()
            elif n_critical_errors > 0:
                st.error(
                    f"❌ {n_critical_errors} bước quan trọng thất bại. "
                    "Kiểm tra lại số liệu đầu vào và thử lại."
                )

    # ── Fallback: step ngoài phạm vi → reset ───────────────────────────────
    else:
        st.session_state.wizard_step = 1
        st.rerun()


# TRẠNG THỜI TAB & RIBBON TÙY CHỈNH
# =========================================================================

# Map tên tab cũ về mới
if st.session_state.current_tab == "BẢN VẼ KẾT CẤU":
    st.session_state.current_tab = "BẢN VẼ KỸ THUẬT"


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

    return {'tab0': tab0, 'tab1': tab1, 'tab2': tab2, 'tab3': 'done'}


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
        'key':      'BẢN VẼ KỸ THUẬT',
        'icon':     '🖼️',
        'state':    tab_states['tab1'],
        'tip':      'Bản vẽ 2D/3D kết cấu cầu',
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
        'key':      'VẼ CHI TIẾT DẦM',
        'icon':     '📐',
        'state':    tab_states['tab3'],
        'tip':      'Section Sketcher + Beam Builder 3D',
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
        f"<div style='position:fixed;top:0;left:300px;right:0;z-index:500;"
        f"height:44px;background:#0d0d1a;border-bottom:2px solid #007acc;"
        f"display:flex;align-items:center;overflow:hidden'>"
        f"<div style='padding:0 14px;font-size:14px;font-weight:700;"
        f"color:#007acc;white-space:nowrap;border-right:1px solid #1e1e2e;"
        f"height:44px;display:flex;align-items:center'>🏗️ UTH</div>"
        f"<div style='display:flex;height:100%;flex:1'>{_tabs_h}</div>"
        f"<div style='border-left:1px solid #1e1e2e;padding:0 12px;"
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


def _render_right_panel(d: dict) -> None:
    """4 result cards trong right panel (col_right)."""
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

_col_tabs = st.columns(4)
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

# ── Hàng nút OPTIONS + thông số hiện hành ───────────────────────────────────
ctrl_col1, ctrl_col2 = st.columns([1, 4])
with ctrl_col1:
    _has_result = bool(st.session_state.design_data.get('kcn_result'))
    _btn_label  = "⚙️ CHỈNH SỬA SỐ LIỆU" if _has_result else "⚙️ OPTIONS — KHAI BÁO SỐ LIỆU"
    if st.button(
        _btn_label,
        use_container_width=True,
        type="secondary" if _has_result else "primary",
        help="Nhấn để mở hộp thoại nhập thông số — bắt buộc trước khi tính toán",
        key="btn_options_main",
    ):
        # Reset validation state để tránh lỗi cũ hiện lại
        st.session_state.field_touched  = set()
        st.session_state.field_errors   = {}
        st.session_state.field_warnings = {}
        if not st.session_state.wizard_draft:
            st.session_state.wizard_step = 1
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

# --- THANH SIDEBAR TRÍI ---
with st.sidebar:

    # ── VÙNG A: Thông tin dự án ──────────────────────────────────────────
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path   = os.path.join(current_dir, "Images", "UTH.jpg")
    if os.path.exists(logo_path):
        st.image(logo_path, width=260)

    st.markdown(
        "<div style='background:#1e1e2e;border:1px solid #2a2a3a;"
        "border-radius:8px;padding:10px 12px;margin:6px 0'>"
        "<div style='font-size:11px;color:#555;margin-bottom:6px;"
        "text-transform:uppercase;letter-spacing:0.4px'>Đề tài</div>"
        "<div style='font-size:12px;color:#ccc;line-height:1.5'>"
        "Tích hợp AI và BIM tự động hóa<br>thiết kế cầu đường bộ</div>"
        "<hr style='border-color:#2a2a3a;margin:8px 0'>"
        "<div style='font-size:11px;color:#888'>"
        "👤 <b style='color:#aaa'>SVTH:</b> Chương DND<br>"
        "👨‍🏫 <b style='color:#aaa'>GVHD:</b> T.S Nguyễn Văn Hiển"
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

    # ── VÙNG C: Trung tâm xuất file ──────────────────────────────────────
    st.markdown(
        "<hr style='border-color:#2a2a3a;margin:10px 0'>"
        "<p style='font-size:10px;color:#555;margin:0 0 8px;"
        "text-transform:uppercase;letter-spacing:0.4px'>"
        "⬇️ Xuất file</p>",
        unsafe_allow_html=True,
    )

    _export_ready = bool(_sd.get('kcn_result'))

    if not _export_ready:
        st.markdown(
            "<p style='font-size:11px;color:#444;text-align:center;"
            "padding:8px'>Chạy tính toán để mở khóa xuất file</p>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<p style='font-size:10px;color:#888;margin:0 0 4px'>"
            "📄 Bản vẽ CAD (DXF)</p>",
            unsafe_allow_html=True,
        )
        _ecol1, _ecol2 = st.columns(2)
        with _ecol1:
            if st.button("Trắc dọc", use_container_width=True, key="sb_dxf_td"):
                try:
                    _b = EXP.export_trac_doc_dxf(_sd)
                    st.download_button(
                        "💾 Tải DXF", _b, "trac_doc.dxf",
                        mime="application/octet-stream",
                        key="sb_dl_td", use_container_width=True,
                    )
                except Exception as _ex:
                    st.error(f"Lỗi: {_ex}")
        with _ecol2:
            if st.button("Mặt cắt", use_container_width=True, key="sb_dxf_mc"):
                try:
                    _b = EXP.export_mcn_dxf(_sd)
                    st.download_button(
                        "💾 Tải DXF", _b, "mat_cat_ngang.dxf",
                        mime="application/octet-stream",
                        key="sb_dl_mc", use_container_width=True,
                    )
                except Exception as _ex:
                    st.error(f"Lỗi: {_ex}")

        st.markdown(
            "<p style='font-size:10px;color:#888;margin:8px 0 4px'>"
            "🏗️ Mô hình BIM (IFC)</p>",
            unsafe_allow_html=True,
        )
        if st.button("Xuất IFC kết cấu cầu", use_container_width=True, key="sb_ifc_bridge"):
            try:
                _b = EXP.export_bridge_ifc(_sd)
                st.download_button(
                    "💾 Tải IFC", _b, "bridge.ifc",
                    mime="application/octet-stream",
                    key="sb_dl_ifc", use_container_width=True,
                )
            except Exception as _ex:
                st.error(f"Lỗi: {_ex}")

        _df_geo_sb = st.session_state.get('gdf_terrain') or st.session_state.get('df_geo')
        if _df_geo_sb is not None:
            if st.button("Xuất IFC địa hình", use_container_width=True, key="sb_ifc_terrain"):
                with st.spinner("Đang xuất..."):
                    try:
                        _, mx, my, mz = TV.ve_dia_hinh_3d(
                            _df_geo_sb, he_so_z=1.0, che_do="Bề mặt mịn", do_min=3)
                        _ifc_path = "terrain_output.ifc"
                        _ok = TV.export_terrain_to_ifc(mx, my, mz, _ifc_path, "DiaHinh_KhaoSat")
                        if _ok:
                            with open(_ifc_path, "rb") as _fh:
                                st.download_button(
                                    "💾 Tải IFC địa hình", _fh, "terrain.ifc",
                                    mime="application/octet-stream",
                                    key="sb_dl_terrifc", use_container_width=True,
                                )
                    except Exception as _ex:
                        st.error(f"Lỗi: {_ex}")

        st.markdown(
            "<p style='font-size:10px;color:#888;margin:8px 0 4px'>"
            "📄 Báo cáo (PDF)</p>",
            unsafe_allow_html=True,
        )
        if st.button("Xuất thuyết minh PDF", use_container_width=True, key="sb_pdf"):
            st.info(
                "💡 Tính năng xuất PDF đang phát triển. "
                "Dùng Ctrl+P để in từ trình duyệt tạm thời."
            )

    # ── VÙNG D: Chatbot AI ───────────────────────────────────────────────
    st.markdown(
        "<hr style='border-color:#2a2a3a;margin:10px 0'>"
        "<p style='font-size:10px;color:#555;margin:0 0 8px;"
        "text-transform:uppercase;letter-spacing:0.4px'>"
        "🤖 Hỏi AI về kết quả</p>",
        unsafe_allow_html=True,
    )

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
selected_ribbon = st.session_state.get('current_tab', 'THUYẾT MINH')

#  Layout: Main canvas (5 col) + Right panel (2 col) 
_col_main, _col_right = st.columns([5, 2], gap="small")

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
                    show_options_dialog()
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
    
        # ── II.b CHỈNH SỬA KÍCH THƯỚC CHI TIẾT DẦM ──────────────────────────
        with st.expander("**✏️ II.b CHỈNH SỬA KÍCH THƯỚC CHI TIẾT DẦM**", expanded=False):
            try:
                BDE.render_beam_dim_editor(d, st)
            except Exception as _bde_err:
                st.error(f"Lỗi module chỉnh sửa dầm: {_bde_err}")
                import traceback as _tb
                st.code(_tb.format_exc())

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
                        show_options_dialog()
            st.stop()
    
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
                "🏗️ 3D Tổng hợp"  + (" 🗺️" if has_terr else " (sơ đồ)"),
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
                            f"⚠️ **Cầu không nằm trong phạm vi địa hình!** "
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
                        he_so_z = st.slider("↕️ Phóng đại Z:", 0.05, 3.00, 0.50, 0.05, key="hsz3d")
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
                    _dc_data = st.session_state.get("dia_chat_data")
                    fig_td_btc = BVK.ve_so_do_nhip_2d(d, df_tim_line=_df_tim,
                                                       dia_chat_data=_dc_data)
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
                # ── Quy trình 3 bước — luôn hiển thị dù có hay chưa có địa hình ──
                _dc_tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "Data", "Template_DiaChat.xlsx")
                st.markdown("##### 🪨 Quy trình khai báo dữ liệu địa chất")
                _cs1, _cs2, _cs3 = st.columns(3)
                with _cs1:
                    st.markdown(
                        "<div style='background:#1e3a5f;border-radius:8px;padding:14px'>"
                        "<div style='color:#f39c12;font-weight:700;font-size:14px'>1️⃣ Tải file template mẫu</div>"
                        "<div style='color:#ccc;font-size:12px;margin-top:6px'>"
                        "Mở file, đọc hướng dẫn ở sheet <b>HUONG_DAN</b>.</div></div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown("")
                    if os.path.exists(_dc_tpl):
                        with open(_dc_tpl, "rb") as _fh_tpl:
                            st.download_button(
                                "⬇️ Tải Template_DiaChat.xlsx",
                                data=_fh_tpl.read(),
                                file_name="Template_DiaChat.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True, key="dl_tpl_dc",
                                help="Gồm 5 sheet: HUONG_DAN · Toado_HK · HK1 · HK2 · HK3 · SPT",
                            )
                        st.caption("Sheet: HUONG_DAN | Toado_HK | HKx | SPT")
                    else:
                        st.error("⚠️ Không tìm thấy Data/Template_DiaChat.xlsx")
                with _cs2:
                    st.markdown(
                        "<div style='background:#1a3d1a;border-radius:8px;padding:14px'>"
                        "<div style='color:#2ecc71;font-weight:700;font-size:14px'>2️⃣ Điền số liệu vào template</div>"
                        "<div style='color:#ccc;font-size:12px;margin-top:6px'>"
                        "• Sheet <b>Toado_HK</b>: tọa độ X, Y (VN-2000) + Z miệng hố<br>"
                        "• Sheet <b>HK01, HK02…</b>: tên lớp, cao độ đáy lớp, mô tả<br>"
                        "• Sheet <b>SPT</b>: độ sâu + giá trị N (nếu có)</div></div>",
                        unsafe_allow_html=True,
                    )
                with _cs3:
                    st.markdown(
                        "<div style='background:#3d1a1a;border-radius:8px;padding:14px'>"
                        "<div style='color:#e74c3c;font-weight:700;font-size:14px'>3️⃣ Upload & phân tích</div>"
                        "<div style='color:#ccc;font-size:12px;margin-top:6px'>"
                        "Tải file đã điền lên ô bên dưới. Hệ thống tự đọc và tích hợp "
                        "vào mô hình 3D địa hình (nếu đã nạp file .NTD).</div></div>",
                        unsafe_allow_html=True,
                    )
    
                st.markdown("---")
    
                # ── Upload file địa chất (luôn hiển thị) ─────────────────────────
                st.markdown("#### 📤 Tải lên file Excel địa chất đã điền")
                file_excel_dc = st.file_uploader(
                    "Chọn file .xlsx (cấu trúc theo template):",
                    type=["xlsx"], key="dc_ex",
                    help="File cần có: sheet Toado_HK (tọa độ hố khoan) + sheet HKxx (phân lớp địa chất từng hố).",
                )
                df_hk, df_layers, df_spt = None, None, None
                hien_mat_lop, hien_khoi_lop, do_trong_dh = True, False, 1.0
    
                if file_excel_dc:
                    with st.spinner("Đang phân tích địa chất..."):
                        df_hk, df_layers, df_spt = TV.doc_excel_dia_chat_3_sheet(file_excel_dc)
                    if df_hk is not None and not df_hk.empty:
                        st.success(f"✅ Đọc được **{len(df_hk)} hố khoan** từ file.")
                        _df_hk_show = df_hk.rename(columns={
                            "Ho_Khoan": "Hố khoan",
                            "X_VN2000": "X (VN-2000)",
                            "Y_VN2000": "Y (VN-2000)",
                            "Z_Mieng":  "Z miệng (m)",
                        })
                        st.dataframe(_df_hk_show, use_container_width=True, hide_index=True)
                        _cap_parts = []
                        if df_layers is not None and not df_layers.empty:
                            _n_lop = (df_layers["Ten_Lop"].nunique()
                                      if "Ten_Lop" in df_layers.columns else len(df_layers))
                            _cap_parts.append(f"📊 {_n_lop} loại lớp | {len(df_layers)} bản ghi phân lớp")
                        if df_spt is not None and not df_spt.empty:
                            _cap_parts.append(f"🔩 SPT: {len(df_spt)} dòng")
                        if _cap_parts:
                            st.caption(" · ".join(_cap_parts))
                        # ── Lưu vào session_state để trắc dọc dùng được ──────────
                        try:
                            _hk_list_ss = []
                            for _, _hkr in df_hk.iterrows():
                                _ten_hk = str(_hkr.get("Ho_Khoan", f"HK{_}")).strip().upper()
                                _z_m    = float(_hkr.get("Z_Mieng", 0) or 0)
                                _lop_dat_ss = []
                                _prev_z = _z_m
                                if df_layers is not None and not df_layers.empty:
                                    _hk_lops = df_layers[df_layers["Ho_Khoan"] == _ten_hk]
                                    for _, _lr in _hk_lops.iterrows():
                                        _z_day = float(_lr.get("Cao_Do_Day", _prev_z - 2) or _prev_z - 2)
                                        _lop_dat_ss.append({
                                            "ten_lop":    str(_lr.get("Ten_Lop", "?")).strip(),
                                            "cao_do_dinh": round(_prev_z, 3),
                                            "cao_do_day":  round(_z_day, 3),
                                            "chieu_day":   round(_prev_z - _z_day, 2),
                                            "mo_ta": "", "loai_dat": "",
                                        })
                                        _prev_z = _z_day
                                _hk_list_ss.append({
                                    "ten": _ten_hk,
                                    "X": float(_hkr.get("X_VN2000", 0) or 0),
                                    "Y": float(_hkr.get("Y_VN2000", 0) or 0),
                                    "Z": _z_m,
                                    "ly_trinh": None,
                                    "lop_dat":  _lop_dat_ss,
                                    "spt":      [],
                                })
                            st.session_state["dia_chat_data"] = {
                                "ho_khoan_list":      _hk_list_ss,
                                "validation_errors":  [],
                                "dac_trung_tong_hop": {},
                            }
                            st.caption(f"💾 Đã lưu {len(_hk_list_ss)} hố khoan vào bộ nhớ phiên — trắc dọc sẽ hiển thị địa chất.")
                        except Exception as _e_ss:
                            st.caption(f"⚠️ Lưu session_state thất bại: {_e_ss}")
                        if has_terr:
                            cdc1, cdc2, cdc3 = st.columns(3)
                            with cdc1:
                                hien_mat_lop  = st.checkbox("Mặt phẳng lớp đất", True)
                            with cdc2:
                                hien_khoi_lop = st.checkbox("Khối lớp đất", False)
                            with cdc3:
                                do_trong_dh = st.slider("Độ trong suốt:", 0.35, 1.0, 0.72, 0.05)
                    else:
                        st.error("❌ Không đọc được dữ liệu. Kiểm tra cấu trúc file theo template.")
    
                # ── Mô hình 3D địa hình + overlay địa chất ───────────────────────
                if not has_terr:
                    st.info("📌 Nạp file địa hình (.NTD + tọa độ VN-2000) ở **đầu tab BẢN VẼ KỸ THUẬT** để xem mô hình 3D địa hình tích hợp địa chất.")
                else:
                    try:
                        st.markdown("---")
                        st.subheader("📊 Mô hình Địa hình 3D chi tiết")
                        col_d1, col_d2, col_d3 = st.columns(3)
                        with col_d1:
                            _che = st.selectbox("Chế độ:", ["Bề mặt mịn","Đường đồng mức","Lưới tam giác"], key="dccd")
                        with col_d2:
                            _hz  = st.slider("Phóng đại Z:", 0.05, 3.0, 0.5, 0.05, key="dchz")
                        with col_d3:
                            _dm  = st.select_slider("Mịn hoá:", [1,3,5,7], 3, key="dcdm")
                        _ftmp, _, _, _ = TV.ve_dia_hinh_3d(_df_geo, he_so_z=_hz, che_do=_che, do_min=_dm)
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
                st.markdown(
                    "<div style='background:#141420;border:1px solid #2a2a3a;"
                    "border-radius:8px;padding:12px 14px;"
                    "display:flex;align-items:center;gap:10px'>"
                    "<span style='font-size:20px'>⬇️</span>"
                    "<div>"
                    "<div style='font-size:12px;color:#ccc;font-weight:600'>"
                    "Xuất DXF / IFC / PDF</div>"
                    "<div style='font-size:11px;color:#666;margin-top:2px'>"
                    "Tất cả tùy chọn xuất file nằm trong "
                    "<b style='color:#4fc3f7'>thanh bên trái ↖</b></div>"
                    "</div></div>",
                    unsafe_allow_html=True,
                )
    
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
                        show_options_dialog()
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

    elif selected_ribbon == "VẼ CHI TIẾT DẦM":
        try:
            BBUI.render_tab()
        except Exception as _bb_err:
            st.error(f"Lỗi Section Sketcher: {_bb_err}")
            import traceback
            st.code(traceback.format_exc())

_render_statusbar(st.session_state.design_data)


# ── Debug Design System panel (bề checkbox trước khi deploy) ─────────────────
if st.sidebar.checkbox("🔧 Debug DS", value=False, key="ds_debug_toggle"):
    import inspect
    with st.expander("🎨 Design System Token Preview", expanded=True):
        st.caption("Tất cả token màu sắc trong DS.Color — dùng để kiểm tra visual consistency.")
        _dc_cols = st.columns(2)
        _dc_items = [(n, v) for n, v in inspect.getmembers(DS.Color)
                     if not n.startswith('_') and isinstance(v, str) and v.startswith('#')]
        for i, (name, val) in enumerate(_dc_items):
            with _dc_cols[i % 2]:
                st.markdown(
                    f"<div style='display:flex;gap:8px;align-items:center;padding:3px 0'>"
                    f"<div style='width:20px;height:20px;background:{val};"
                    f"border-radius:4px;border:1px solid #333;flex-shrink:0'></div>"
                    f"<code style='font-size:11px'>Color.{name} = {val}</code>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
