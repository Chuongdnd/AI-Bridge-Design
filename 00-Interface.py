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

# --- THIáº¾T Láº¬P TRANG (CHá»ˆ Má»˜T Láº¦N) ---
st.set_page_config(page_title="Há»‡ thá»‘ng Thiáº¿t káº¿ Cáº§u AI - UTH", layout="wide", page_icon="ðŸ—ï¸")

# â”€â”€ Global CSS: áº©n toolbar + Engineering layout â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
st.markdown("""
<style>
/* â”€â”€ áº¨n Streamlit toolbar/menu/footer â”€â”€ */
[data-testid="stToolbarActions"]  { display: none !important; }
[data-testid="stDecoration"]      { display: none !important; }
[data-testid="stStatusWidget"]    { display: none !important; }
.stDeployButton                   { display: none !important; }
#MainMenu                         { display: none !important; }
footer                            { display: none !important; }

/* â”€â”€ Metrics â”€â”€ */
[data-testid="stMetric"] {
    background: #1a1a2a; border: 1px solid #333355;
    border-radius: 8px; padding: 8px 12px;
}
[data-testid="stMetricValue"] { font-size: 16px !important; color: #4fc3f7 !important; }

/* â”€â”€ Sidebar â”€â”€ */
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

/* â”€â”€ Number input validation feedback â”€â”€ */
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

/* â”€â”€ Topbar: Ä‘áº©y main content xuá»‘ng 52px â”€â”€ */
section[data-testid="stMain"] .block-container {
    padding-top: 52px !important;
    padding-bottom: 32px !important;
    max-width: 100% !important;
}

/* â”€â”€ Nav buttons phá»§ lÃªn topbar â”€â”€ */
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

# â”€â”€ XÃC THá»°C NGÆ¯á»œI DÃ™NG â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
import importlib.util as _iutil
_auth_spec = _iutil.spec_from_file_location("auth00", os.path.join(os.path.dirname(os.path.abspath(__file__)), "00-Auth.py"))
AUTH = _iutil.module_from_spec(_auth_spec)
_auth_spec.loader.exec_module(AUTH)

if not AUTH.is_authenticated():
    AUTH.show_login_page()
    st.stop()

# Khá»Ÿi táº¡o bá»™ nhá»› há»™i thoáº¡i chatbot
if 'messages' not in st.session_state:
    st.session_state.messages = []

# --- Cáº¤U HÃŒNH AI GEMINI ASSISTANT ---
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel('gemini-2.5-flash')
    else:
        st.sidebar.error("âŒ KhÃ´ng tÃ¬m tháº¥y mÃ£ GEMINI_API_KEY trong Secrets!")
        gemini_model = None
except Exception as e:
    st.sidebar.error(f"Lá»—i cáº¥u hÃ¬nh AI: {e}")
    gemini_model = None

def load_all_standards(folder_name="Documents"):
    knowledge_text = ""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    folder_path = os.path.join(current_dir, folder_name)
    if not os.path.exists(folder_path):
        return "ThÆ° má»¥c tÃ i liá»‡u khÃ´ng tá»“n táº¡i."
    for file_name in os.listdir(folder_path):
        if file_name.endswith(".pdf"):
            try:
                doc = fitz.open(os.path.join(folder_path, file_name))
                text = ""
                for page in doc:
                    text += page.get_text()
                knowledge_text += f"\n--- NGUá»’N TÃ€I LIá»†U: {file_name} ---\n{text}\n"
            except:
                pass
    return knowledge_text

if 'bridge_library' not in st.session_state:
    with st.spinner("ðŸ“š Äang náº¡p há»‡ thá»‘ng tiÃªu chuáº©n cáº§u Ä‘Æ°á»ng..."):
        st.session_state.bridge_library = load_all_standards()

# --- Káº¾T Ná»I Há»† THá»NG MODULES THÃ€NH PHáº¦N ---
try:
    TK   = importlib.import_module("01-Tinh_khong")
    YTHH = importlib.import_module("02-Yeuto_Hinhhoc")  # Yáº¿u tá»‘ hÃ¬nh há»c + MCN
    KCN  = importlib.import_module("06-AI_KetCauNhip")  # AI Káº¿t cáº¥u nhá»‹p v2
    MOT  = importlib.import_module("07-AI_MoTru")       # AI Má»‘ â€“ Trá»¥ v2
    MONG = importlib.import_module("08-AI_Mong")        # MÃ³ng (rule-based)
    EXP  = importlib.import_module("09-Export_CAD_IFC") # Export DXF / IFC
    PLOT = importlib.import_module("00-Drawing_Utils")
    TV   = importlib.import_module("00-Terrain_Viewer")
    TC   = importlib.import_module("04-Pier-test")
    LPC  = importlib.import_module("10-LopPhu_MatCau")  # Lá»›p phá»§ máº·t cáº§u
    BVK  = importlib.import_module("11-BanVe_KetCau")   # Báº£n váº½ káº¿t cáº¥u 2D/3D
    SSP  = importlib.import_module("09-So_Sanh_PA")     # So sÃ¡nh 3 phÆ°Æ¡ng Ã¡n
    CTD  = importlib.import_module("12-ChiTiet_Dam")    # Chi tiáº¿t dáº§m
    importlib.reload(PLOT)
    importlib.reload(BVK)
    importlib.reload(CTD)
except Exception as e:
    st.error(f"Lá»—i káº¿t ná»‘i Module: {e}")
    st.stop()

if 'design_data' not in st.session_state:
    st.session_state.design_data = {
        'day_dam': 0.0, 'khau_do_ngang': 0.0, 'bc': 12.0, 'loai_duong': "Do thi",
        'B': 20.0, 'H': 4.75, 'loai_doi_tuong_vuot': "VÆ°á»£t sÃ´ng", 'goc_giao': 90.0,
        'MNCN': 3.5, 'MNTT': 2.0, 'MNTC': 1.5, 'MNTN': 0.5, 'h_tn_tb': 0.0,
        'x_tim_clearance': 0.0,
        'cap_song': 'VI', 'vtk': 60, 'i_max_hinh_hoc': 4.0, 'R_hinh_hoc': 5000,
        't_ban_mm': 200,       # chiá»u dÃ y báº£n máº·t cáº§u (mm), min 175mm theo TCVN 11823
        'is_urban': 0,         # 1 = khu Ä‘Ã´ng dÃ¢n cÆ° (áº£nh hÆ°á»Ÿng chá»n loáº¡i cá»c)
        'geo_logic': {'L_cau': 120.0, 'x_mo_trai': -60.0, 'x_mo_phai': 60.0, 'y_mo': 1.5, 'h_tn_tb': 2.15, 'y_base_goc': 2.0},
        'ai_result': {'loai_dam': 'Super-T', 'tong_so_nhip': 3, 'chieu_dai': 40.0, 'chieu_cao': 1.75, 'so_luong_dam': 5, 'khoang_cach_dam': 2.2, 'ghi_chu': 'PhÆ°Æ¡ng Ã¡n tá»‘i Æ°u tá»« AI.'},
        'kcn_result': None,
        'tru_result': None,
        'mong_result': None,
        'lop_phu_result': None,
    }

if 'chatbot_context' not in st.session_state:
    st.session_state.chatbot_context = "ChÆ°a tiáº¿n hÃ nh cháº¡y dá»± bÃ¡o tÃ­nh toÃ¡n."

if 'alternatives' not in st.session_state:
    st.session_state.alternatives = None

if 'current_tab' not in st.session_state:
    st.session_state.current_tab = "THUYáº¾T MINH"

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

# â”€â”€ Metadata 8 bÆ°á»›c pipeline AI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
PIPELINE_STEPS = [
    {"id": "TK",   "label": "TÄ©nh khÃ´ng ÄTNÄ",    "desc": "Tra cá»©u tÄ©nh khÃ´ng thÃ´ng thuyá»n theo TCVN 8818:2022",         "icon": "ðŸŒŠ", "weight": 5},
    {"id": "YTHH", "label": "Yáº¿u tá»‘ hÃ¬nh há»c",     "desc": "TÃ­nh MCN, chiá»u rá»™ng cáº§u, Ä‘á»™ dá»‘c dá»c ngang",                  "icon": "ðŸ“", "weight": 10},
    {"id": "KCN",  "label": "AI káº¿t cáº¥u nhá»‹p",     "desc": "Dá»± bÃ¡o loáº¡i dáº§m, sá»‘ nhá»‹p, chiá»u dÃ i, chiá»u cao",              "icon": "ðŸ¤–", "weight": 20},
    {"id": "MOT",  "label": "AI má»‘ â€“ trá»¥",         "desc": "Dá»± bÃ¡o loáº¡i trá»¥, kÃ­ch thÆ°á»›c thÃ¢n trá»¥, loáº¡i má»‘",               "icon": "ðŸ›ï¸", "weight": 20},
    {"id": "MONG", "label": "AI mÃ³ng cáº§u",          "desc": "Dá»± bÃ¡o loáº¡i mÃ³ng, Ä‘Æ°á»ng kÃ­nh cá»c, chiá»u sÃ¢u",                 "icon": "âš™ï¸", "weight": 20},
    {"id": "LPC",  "label": "Lá»›p phá»§ máº·t cáº§u",     "desc": "TÆ° váº¥n cáº¥u táº¡o lá»›p phá»§ theo TCVN 8819:2011",                 "icon": "ðŸ›£ï¸", "weight": 5},
    {"id": "BVK",  "label": "Báº£n váº½ káº¿t cáº¥u",      "desc": "Sinh báº£n váº½ tráº¯c dá»c, máº·t cáº¯t ngang, má»‘ trá»¥",                "icon": "ðŸ“‹", "weight": 10},
    {"id": "SSP",  "label": "So sÃ¡nh phÆ°Æ¡ng Ã¡n",   "desc": "Sinh vÃ  Ä‘Ã¡nh giÃ¡ 3 phÆ°Æ¡ng Ã¡n loáº¡i dáº§m",                       "icon": "ðŸ“Š", "weight": 10},
]
assert sum(s["weight"] for s in PIPELINE_STEPS) == 100


class PipelineTracker:
    """Quáº£n lÃ½ tráº¡ng thÃ¡i vÃ  hiá»ƒn thá»‹ tiáº¿n trÃ¬nh pipeline AI."""

    STATUS_WAIT    = "wait"
    STATUS_RUNNING = "running"
    STATUS_DONE    = "done"
    STATUS_ERROR   = "error"
    STATUS_SKIP    = "skip"

    _COLORS = {
        "wait":    ("#333355", "#888899", "â—‹"),
        "running": ("#1a2d45", "#4fc3f7", "âŸ³"),
        "done":    ("#0d3d1f", "#2ecc71", "âœ“"),
        "error":   ("#2d0a0a", "#e74c3c", "âœ—"),
        "skip":    ("#1a1a1a", "#555555", "â€”"),
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
            "margin:0 0 8px'>ðŸ¤– Pipeline AI Ä‘ang cháº¡y...</p>",
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
        self.messages[step_id] = "Bá» qua do bÆ°á»›c trÆ°á»›c tháº¥t báº¡i"
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
                f"<summary style='font-size:11px;color:#666;cursor:pointer'>â± Thá»i gian chi tiáº¿t</summary>"
                f"<table style='width:100%;font-size:11px;border-collapse:collapse;margin-top:6px'>"
                f"{''.join(rows)}"
                f"<tr style='border-top:1px solid #333'>"
                f"<td style='padding:4px 8px;color:#fff;font-weight:600'>Tá»•ng cá»™ng</td>"
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
                f" â€” {meta['desc']}</p>",
                unsafe_allow_html=True,
            )
        elif self._pct >= 100:
            self._ph_label.markdown(
                "<p style='font-size:12px;color:#2ecc71;margin:0 0 4px'>"
                "âœ… HoÃ n táº¥t táº¥t cáº£ cÃ¡c bÆ°á»›c</p>",
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


# â”€â”€ Design System â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
import importlib.util as _dsutil
_dsspec = _dsutil.spec_from_file_location(
    "ds00",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "00-DesignSystem.py")
)
DS = _dsutil.module_from_spec(_dsspec)
_dsspec.loader.exec_module(DS)
st.markdown(DS.GLOBAL_CSS, unsafe_allow_html=True)

# â”€â”€ Import module validation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    """number_input bá»c thÃªm icon tráº¡ng thÃ¡i vÃ  feedback dÆ°á»›i Ã´."""
    touched  = key in st.session_state.field_touched
    prev_err = st.session_state.field_errors.get(key)
    label_display = (
        f"ðŸ”´ {label}" if (touched and prev_err)
        else f"âœ… {label}" if touched
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
                f"color:#ff8a80'>âŒ {result.error}</div>",
                unsafe_allow_html=True,
            )
            if result.hint:
                st.markdown(
                    f"<div style='margin-top:-4px;margin-bottom:8px;"
                    f"padding:4px 10px;background:#1a2000;"
                    f"border-left:3px solid #f39c12;"
                    f"border-radius:0 6px 6px 0;font-size:11px;"
                    f"color:#ffc947'>ðŸ’¡ {result.hint}</div>",
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
                f"color:#ffc947'>âš ï¸ {result.warning}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.session_state.field_errors.pop(key, None)
            st.session_state.field_warnings.pop(key, None)
            st.markdown(
                f"<div style='margin-top:-12px;margin-bottom:8px;"
                f"padding:4px 10px;font-size:11px;"
                f"color:#2ecc71'>âœ… Há»£p lá»‡</div>",
                unsafe_allow_html=True,
            )

    return new_val


def _render_step_status_banner(errors: dict, warnings: dict,
                                n_fields_total: int):
    """Banner tá»•ng há»£p tráº¡ng thÃ¡i bÆ°á»›c hiá»‡n táº¡i â€” hiá»‡n á»Ÿ Ä‘áº§u form."""
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
        msg_icon  = "âŒ"
        msg_text  = (f"{n_err} lá»—i cáº§n sá»­a trÆ°á»›c khi tiáº¿p tá»¥c"
                     + (f" Â· {n_warn} cáº£nh bÃ¡o" if n_warn else ""))
    elif n_warn > 0:
        msg_color = "#ffc947"
        msg_bg    = "#1f1600"
        msg_icon  = "âš ï¸"
        msg_text  = f"{n_warn} cáº£nh bÃ¡o â€” cÃ³ thá»ƒ tiáº¿p tá»¥c nhÆ°ng nÃªn kiá»ƒm tra láº¡i"
    else:
        msg_color = "#2ecc71"
        msg_bg    = "#0d1f0d"
        msg_icon  = "âœ…"
        msg_text  = "Táº¥t cáº£ trÆ°á»ng há»£p lá»‡ â€” cÃ³ thá»ƒ tiáº¿p tá»¥c"

    st.markdown(
        f"{bar_html}"
        f"<div style='padding:8px 12px;background:{msg_bg};"
        f"border-radius:6px;font-size:12px;color:{msg_color};"
        f"margin-bottom:12px'>{msg_icon} {msg_text}</div>",
        unsafe_allow_html=True,
    )


# =========================================================================
# âš™ï¸ WIZARD KHAI BÃO Sá» LIá»†U â€” 3 BÆ¯á»šC
# =========================================================================
def _render_wizard_progress(current: int, steps: list):
    cols = st.columns(len(steps))
    for i, (col, label) in enumerate(zip(cols, steps), 1):
        with col:
            if i < current:
                st.markdown(
                    f"<div style='text-align:center;padding:8px 4px;"
                    f"background:#0d3d1f;border:1px solid #2ecc71;border-radius:8px'>"
                    f"<div style='font-size:16px'>âœ…</div>"
                    f"<div style='font-size:11px;color:#2ecc71;font-weight:600'>BÆ°á»›c {i}</div>"
                    f"<div style='font-size:10px;color:#aaa'>{label}</div></div>",
                    unsafe_allow_html=True,
                )
            elif i == current:
                st.markdown(
                    f"<div style='text-align:center;padding:8px 4px;"
                    f"background:#1a2d45;border:2px solid #007acc;border-radius:8px'>"
                    f"<div style='font-size:16px'>â–¶ï¸</div>"
                    f"<div style='font-size:11px;color:#4fc3f7;font-weight:700'>BÆ°á»›c {i} â€” Hiá»‡n táº¡i</div>"
                    f"<div style='font-size:10px;color:#ccc'>{label}</div></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='text-align:center;padding:8px 4px;"
                    f"background:#1a1a2a;border:1px solid #333355;border-radius:8px;opacity:0.6'>"
                    f"<div style='font-size:16px'>â—‹</div>"
                    f"<div style='font-size:11px;color:#888'>BÆ°á»›c {i}</div>"
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
        errs['h1']  = f"MNCN ({h1}) pháº£i Lá»šN HÆ N MNTT ({h5})"
    if h5 <= h10:
        errs['h5']  = f"MNTT ({h5}) pháº£i Lá»šN HÆ N MNTC ({h10})"
    if h10 <= h98:
        errs['h10'] = f"MNTC ({h10}) pháº£i Lá»šN HÆ N MNTN ({h98})"
    if draft.get('x_tim_clearance', 0) == 0:
        errs['x_tim'] = "LÃ½ trÃ¬nh tim cáº§u chÆ°a Ä‘Æ°á»£c nháº­p"
    return errs


def _validate_step2(draft: dict) -> dict:
    errs = {}
    vtk = draft.get('vtk', 0)
    if vtk <= 0:
        errs['vtk'] = "Váº­n tá»‘c thiáº¿t káº¿ pháº£i lá»›n hÆ¡n 0"
    bc = draft.get('bc', 0.0)
    if bc < 3.5:
        errs['bc'] = f"Chiá»u rá»™ng cáº§u {bc}m cÃ³ váº» quÃ¡ nhá» (thÃ´ng thÆ°á»ng â‰¥ 7m)"
    return errs


@st.dialog("âš™ï¸ KHAI BÃO THÃ”NG Sá» THIáº¾T Káº¾", width="large")
def show_options_dialog():
    STEP_LABELS = ["Thá»§y vÄƒn & Vá»‹ trÃ­", "HÃ¬nh há»c tuyáº¿n", "Xem láº¡i & Cháº¡y AI"]
    step  = st.session_state.wizard_step
    draft = st.session_state.wizard_draft

    _render_wizard_progress(step, STEP_LABELS)

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # BÆ¯á»šC 1 â€” THá»¦Y VÄ‚N & Vá»Š TRÃ
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    if step == 1:
        st.markdown(
            DS.section_header(
                title = "ThÃ´ng sá»‘ thá»§y vÄƒn & vá»‹ trÃ­ cáº§u",
                icon  = "ðŸŒŠ",
                sub   = "Pháº¡m vi Ä‘á» tÃ i: Cáº§u vÆ°á»£t sÃ´ng/kÃªnh cáº¥p IVâ€“VI (TCVN 8818:2022)",
            ),
            unsafe_allow_html=True,
        )

        # Banner tá»•ng há»£p (chá»‰ hiá»‡n sau láº§n touched Ä‘áº§u tiÃªn)
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
            st.markdown("**ðŸ“ Vá»‹ trÃ­ & phÃ¢n loáº¡i**")
            mien = st.selectbox(
                "Khu vá»±c miá»n:",
                ["1", "2"],
                index=0 if draft.get('mien', '2') == '1' else 1,
                format_func=lambda x: "Miá»n Báº¯c" if x == "1" else "Miá»n Nam",
                key="wz_mien",
            )
            cap_s = st.selectbox(
                "Cáº¥p sÃ´ng ÄTNÄ:",
                ["4", "5", "6", "3", "2", "1"],
                index=["4","5","6","3","2","1"].index(str(draft.get('cap_s', '4'))),
                format_func=lambda x: f"Cáº¥p {['I','II','III','IV','V','VI'][int(x)-1]}",
                key="wz_caps",
            )
            loai_h = st.selectbox(
                "Loáº¡i hÃ¬nh thá»§y vÄƒn:",
                ["1", "2"],
                index=0 if draft.get('loai_h', '2') == '1' else 1,
                format_func=lambda x: "KÃªnh Ä‘Ã o" if x == "1" else "SÃ´ng tá»± nhiÃªn",
                key="wz_loaih",
            )
            goc_giao = _field_with_feedback(
                label     = "GÃ³c giao chÃ©o (Ä‘á»™)",
                value     = float(draft.get('goc_giao', st.session_state.design_data.get('goc_giao', 90.0))),
                key       = "wz_goc",
                check_fn  = VAL.check_goc_giao,
                check_args= (),
                fmt       = "%.1f",
                min_val   = 30.0,
                max_val   = 90.0,
                step      = 1.0,
                help_txt  = "90Â° = vuÃ´ng gÃ³c. Cáº§u xiÃªn < 75Â° cáº§n kiá»ƒm tra thÃªm.",
            )

        with col_b:
            st.markdown("**ðŸ“ Cao Ä‘á»™ thá»§y vÄƒn (m)**")
            st.caption("Thá»© tá»± báº¯t buá»™c: MNCN > MNTT > MNTC > MNTN")

            _lt_min = _lt_max = None
            if 'df_tim_line' in st.session_state and st.session_state.df_tim_line is not None:
                _tl = st.session_state.df_tim_line
                _lt_col = next((c for c in _tl.columns if 'Ã½ trÃ¬nh' in c or c.lower() == 'ly_trinh'), None)
                if _lt_col:
                    _lt_min = float(_tl[_lt_col].min())
                    _lt_max = float(_tl[_lt_col].max())
                    st.info(f"ðŸ—ºï¸ Äá»‹a hÃ¬nh: LÃ½ trÃ¬nh {_lt_min:.1f} â†’ {_lt_max:.1f}m  |  Gá»£i Ã½ tim cáº§u â‰ˆ **{(_lt_min+_lt_max)/2:.1f}m**")

            x_tim_clearance = _field_with_feedback(
                label     = "ðŸ“ LÃ½ trÃ¬nh tim tÄ©nh khÃ´ng (m)",
                value     = float(draft.get('x_tim_clearance', st.session_state.design_data.get('x_tim_clearance', 0.0))),
                key       = "wz_xtim",
                check_fn  = VAL.check_x_tim,
                check_args= (_lt_min, _lt_max),
                fmt       = "%.2f",
                step      = 1.0,
                help_txt  = "LÃ½ trÃ¬nh Ä‘iá»ƒm tim cáº§u vÆ°á»£t qua sÃ´ng/kÃªnh.",
            )

            _d = st.session_state.design_data
            h1 = _field_with_feedback(
                label     = "MNCN â€” Má»±c nÆ°á»›c cao nháº¥t H1% (m)",
                value     = float(draft.get('h1', _d.get('MNCN', 3.50))),
                key       = "wz_h1",
                check_fn  = VAL.check_h1,
                check_args= (float(draft.get('h5', _d.get('MNTT', 2.00))),),
                help_txt  = "Má»±c nÆ°á»›c cao nháº¥t táº§n suáº¥t 1% â€” dÃ¹ng tÃ­nh an toÃ n va tÃ u",
            )
            h5 = _field_with_feedback(
                label     = "MNTT â€” Má»±c nÆ°á»›c thÃ´ng thuyá»n H5% (m)",
                value     = float(draft.get('h5', _d.get('MNTT', 2.00))),
                key       = "wz_h5",
                check_fn  = VAL.check_h5,
                check_args= (h1, float(draft.get('h10', _d.get('MNTC', 1.50)))),
                help_txt  = "Má»±c nÆ°á»›c thÃ´ng thuyá»n â€” dÃ¹ng tÃ­nh chiá»u cao tÄ©nh khÃ´ng H",
            )
            h10 = _field_with_feedback(
                label     = "MNTC â€” Má»±c nÆ°á»›c thi cÃ´ng H10% (m)",
                value     = float(draft.get('h10', _d.get('MNTC', 1.50))),
                key       = "wz_h10",
                check_fn  = VAL.check_h10,
                check_args= (h5, float(draft.get('h98', _d.get('MNTN', 0.50)))),
                help_txt  = "Má»±c nÆ°á»›c thi cÃ´ng táº§n suáº¥t 10%",
            )
            h98 = _field_with_feedback(
                label     = "MNTN â€” Má»±c nÆ°á»›c tháº¥p nháº¥t H98% (m)",
                value     = float(draft.get('h98', _d.get('MNTN', 0.50))),
                key       = "wz_h98",
                check_fn  = VAL.check_h98,
                check_args= (h10,),
                help_txt  = "Má»±c nÆ°á»›c kiá»‡t táº§n suáº¥t 98% â€” dÃ¹ng Æ°á»›c tÃ­nh chiá»u cao trá»¥",
            )

            st.markdown("**ðŸ—ï¸ Báº£n máº·t cáº§u**")
            t_ban_mm = _field_with_feedback(
                label     = "Chiá»u dÃ y báº£n máº·t cáº§u (mm)",
                value     = float(draft.get('t_ban_mm', _d.get('t_ban_mm', 200))),
                key       = "wz_tban",
                check_fn  = VAL.check_t_ban,
                check_args= (),
                fmt       = "%.0f",
                min_val   = 150.0,
                max_val   = 400.0,
                step      = 5.0,
                help_txt  = "Tá»‘i thiá»ƒu 175mm â€” TCVN 11823-2017 Äiá»u 9.7.1.1",
                unit      = "mm",
            )

        # Disable nÃºt Tiáº¿p náº¿u cÃ²n lá»—i cá»©ng
        _has_hard_errors = any(
            k in st.session_state.field_errors
            for k in ['wz_h1', 'wz_h5', 'wz_h10', 'wz_h98', 'wz_xtim', 'wz_goc', 'wz_tban']
        )

        st.markdown("<br>", unsafe_allow_html=True)
        _, btn_col = st.columns([3, 1])
        with btn_col:
            if st.button(
                "Tiáº¿p theo â–¶",
                use_container_width=True,
                type="primary",
                disabled=_has_hard_errors,
                key="wz_next1",
                help="Sá»­a háº¿t lá»—i Ä‘á» trÆ°á»›c khi sang bÆ°á»›c tiáº¿p theo" if _has_hard_errors else "",
            ):
                st.session_state.wizard_draft.update({
                    'mien': mien, 'cap_s': cap_s, 'loai_h': loai_h,
                    'goc_giao': goc_giao, 'x_tim_clearance': x_tim_clearance,
                    'h1': h1, 'h5': h5, 'h10': h10, 'h98': h98,
                    't_ban_mm': int(t_ban_mm),
                })
                st.session_state.wizard_step = 2
                st.rerun()

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # BÆ¯á»šC 2 â€” HÃŒNH Há»ŒC TUYáº¾N
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    elif step == 2:
        st.markdown(
            DS.section_header(
                title = "TiÃªu chuáº©n hÃ¬nh há»c tuyáº¿n Ä‘Æ°á»ng",
                icon  = "ðŸ›£ï¸",
                sub   = "Chá»n loáº¡i Ä‘Æ°á»ng, váº­n tá»‘c thiáº¿t káº¿ vÃ  nháº­p bá» rá»™ng cáº§u",
            ),
            unsafe_allow_html=True,
        )

        # Khá»Ÿi táº¡o defaults â€” sáº½ Ä‘Æ°á»£c ghi Ä‘Ã¨ trong tá»«ng nhÃ¡nh
        v_hinhhoc     = draft.get('v_hinhhoc', 60)
        d_hinhhoc     = draft.get('d_hinhhoc', '1')
        input_tra_cuu = draft.get('input_tra_cuu', 60)
        mcn_oto_override = {}
        r_final_calc  = draft.get('r_final_calc', 5000)
        i_final_calc  = draft.get('i_final_calc', 4.0)
        res_geo       = {}

        _lh_opts = ["Cao tá»‘c", "O to", "Do thi"]
        l_hinhhoc = st.selectbox(
            "Loáº¡i Ä‘Æ°á»ng thiáº¿t káº¿:",
            _lh_opts,
            index=_lh_opts.index(draft.get('l_hinhhoc', 'Do thi')),
        )

        if l_hinhhoc == "Cao tá»‘c":
            d_hinhhoc = st.radio("Äá»‹a hÃ¬nh:", options=["1", "2"], format_func=lambda x: "Äá»“ng báº±ng" if x == "1" else "KhÃ³ khÄƒn")
            v_list = [120, 100] if d_hinhhoc == "1" else [80, 60]
            v_hinhhoc = st.selectbox("Váº­n tá»‘c thiáº¿t káº¿ Vtk (km/h):", options=v_list)
            input_tra_cuu = v_hinhhoc

            _dpc_ct_labels = {
                "co_lop_phu_khong_tru": "CÃ³ lá»›p phá»§, khÃ´ng bá»‘ trÃ­ trá»¥ cÃ´ng trÃ¬nh",
                "co_lop_phu_co_tru":    "CÃ³ lá»›p phá»§, cÃ³ bá»‘ trÃ­ trá»¥ cÃ´ng trÃ¬nh",
                "khong_lop_phu":        "KhÃ´ng cÃ³ lá»›p phá»§ (trá»“ng cá» / hÃ¬nh chá»¯ V)",
            }
            st.markdown("**Máº·t cáº¯t ngang Ä‘Æ°á»ng (TCVN 5729:2012 Báº£ng 1)**")
            loai_dpc_ct = st.selectbox(
                "Cáº¥u táº¡o dáº£i giá»¯a:",
                options=list(_dpc_ct_labels.keys()),
                format_func=lambda k: _dpc_ct_labels[k],
                help="Theo Äiá»u 6.5 â€” xÃ¡c Ä‘á»‹nh chiá»u rá»™ng dáº£i phÃ¢n cÃ¡ch lÃµi."
            )
            tra_ct = YTHH.tra_cuu_mcn_caotoc(v_hinhhoc, loai_dpc_ct)
            if tra_ct.get("status") == "success":
                st.caption(
                    f"{tra_ct['bang_ap_dung']} â€” Vtk={v_hinhhoc}km/h: "
                    f"Máº·t Ä‘Æ°á»ng â‰¥ **{tra_ct['w_mat_duong_min']:g}m** (2 lÃ n/chiá»u Ã— {tra_ct['w_lan_min']:g}m) | "
                    f"Lá» gia cá»‘ â‰¥ **{tra_ct['w_le_dat_min']:g}m** | "
                    f"DAT dáº£i giá»¯a â‰¥ **{tra_ct['w_dat_an_toan_dg_min']:g}m** | "
                    f"DPC lÃµi â‰¥ **{tra_ct['w_dpc_core_min']:g}m** | "
                    f"Ná»n â‰¥ **{tra_ct['w_nen_min']:g}m**"
                )
                st.caption(
                    "Äá»™ dá»‘c ngang (cá»‘ Ä‘á»‹nh TCVN 5729:2012): "
                    f"Máº·t Ä‘Æ°á»ng & dáº£i AT = **{tra_ct['i_mat_duong']:g}%** | "
                    f"Lá» trá»“ng cá» = **{tra_ct['i_le_trong_co']:g}%**"
                )
                c_ct1, c_ct2 = st.columns(2)
                with c_ct1:
                    n_lan_ct = st.number_input(
                        "Sá»‘ lÃ n xe má»—i chiá»u:",
                        min_value=int(tra_ct["n_lan_moi_chieu_min"]),
                        value=int(tra_ct["n_lan_moi_chieu_min"]),
                        step=1,
                        help=f"Tá»‘i thiá»ƒu {tra_ct['n_lan_moi_chieu_min']} lÃ n/chiá»u (Báº£ng 1). "
                             f"ThÃªm 1 lÃ n = +{tra_ct['w_lan_them']:g}m máº·t Ä‘Æ°á»ng (Äiá»u 6.8)."
                    )
                    w_le_dat_ct = st.number_input(
                        "Chiá»u rá»™ng lá» gia cá»‘ / dáº£i AT (m):",
                        min_value=float(tra_ct["w_le_dat_min"]),
                        value=float(tra_ct["w_le_dat_min"]),
                        step=0.25, format="%.2f",
                        help=f"Tá»‘i thiá»ƒu {tra_ct['w_le_dat_min']:g}m theo Báº£ng 1."
                    )
                with c_ct2:
                    w_dat_at_dg_ct = st.number_input(
                        "Dáº£i an toÃ n trong dáº£i giá»¯a (m):",
                        min_value=float(tra_ct["w_dat_an_toan_dg_min"]),
                        value=float(tra_ct["w_dat_an_toan_dg_min"]),
                        step=0.25, format="%.2f",
                        help=f"Tá»‘i thiá»ƒu {tra_ct['w_dat_an_toan_dg_min']:g}m má»—i bÃªn (Báº£ng 1)."
                    )
                    w_dpc_core_ct = st.number_input(
                        "Chiá»u rá»™ng dáº£i phÃ¢n cÃ¡ch lÃµi (m):",
                        min_value=float(tra_ct["w_dpc_core_min"]),
                        value=float(tra_ct["w_dpc_core_min"]),
                        step=0.25, format="%.2f",
                        help=f"Tá»‘i thiá»ƒu {tra_ct['w_dpc_core_min']:g}m theo Báº£ng 1 (loáº¡i Ä‘Ã£ chá»n)."
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
                st.warning(f"âš ï¸ {tra_ct.get('message','KhÃ´ng tra Ä‘Æ°á»£c MCN cao tá»‘c.')}")
                mcn_oto_override = {"loai_dpc_ct": loai_dpc_ct}
        elif l_hinhhoc == "O to":
            cap_duong_oto = st.selectbox("Cáº¥p Ä‘Æ°á»ng Ã´ tÃ´:", ["I", "II", "III", "IV", "V", "VI"])
            d_hinhhoc = st.radio("Äá»‹a hÃ¬nh vÃ¹ng:", ["1", "2"], format_func=lambda x: "Äá»“ng báº±ng" if x == "1" else "Miá»n nÃºi")
            input_tra_cuu = cap_duong_oto

            dia_hinh_mcn = "dong_bang" if d_hinhhoc == "1" else "nui"
            tra_mcn = YTHH.tra_cuu_mcn_oto(cap_duong_oto, dia_hinh_mcn)
            if tra_mcn.get("status") == "success":
                st.markdown("**Máº·t cáº¯t ngang Ä‘Æ°á»ng (TCVN 4054:2005)**")
                st.caption(
                    f"{tra_mcn['bang_ap_dung']} â€” Cáº¥p {cap_duong_oto}: tá»‘i thiá»ƒu "
                    f"**{tra_mcn['so_lan_min']:g} lÃ n Ã— {tra_mcn['w_lan_min']:g}m** | "
                    f"Dáº£i PC â‰¥ **{tra_mcn['w_dpc_min']:g}m** | "
                    f"Lá» â‰¥ **{tra_mcn['w_le_min']:g}m**"
                    + (f" (gia cá»‘ â‰¥ {tra_mcn['w_le_gc_min']:g}m)" if tra_mcn['w_le_gc_min'] else "")
                    + f" | Ná»n Ä‘Æ°á»ng â‰¥ **{tra_mcn['w_nen_duong_min']:g}m**"
                )
                c_mcn1, c_mcn2 = st.columns(2)
                with c_mcn1:
                    so_lan_oto = st.number_input(
                        "Sá»‘ lÃ n xe thiáº¿t káº¿:",
                        min_value=int(tra_mcn["so_lan_min"]), value=int(tra_mcn["so_lan_min"]), step=1,
                        help=f"Tá»‘i thiá»ƒu {tra_mcn['so_lan_min']:g} lÃ n theo TCVN 4054:2005."
                    )
                    w_lan_oto = st.number_input(
                        "Chiá»u rá»™ng 1 lÃ n xe (m):",
                        min_value=float(tra_mcn["w_lan_min"]), value=float(tra_mcn["w_lan_min"]),
                        step=0.25, format="%.2f",
                        help=f"Tá»‘i thiá»ƒu {tra_mcn['w_lan_min']:g}m theo TCVN 4054:2005."
                    )
                with c_mcn2:
                    w_le_oto = st.number_input(
                        "Chiá»u rá»™ng lá» Ä‘Æ°á»ng (m):",
                        min_value=float(tra_mcn["w_le_min"]), value=float(tra_mcn["w_le_min"]),
                        step=0.25, format="%.2f",
                        help=f"Tá»‘i thiá»ƒu {tra_mcn['w_le_min']:g}m theo TCVN 4054:2005."
                    )
                    w_dpc_oto = st.number_input(
                        "Chiá»u rá»™ng dáº£i phÃ¢n cÃ¡ch giá»¯a (m):",
                        min_value=float(tra_mcn["w_dpc_min"]), value=float(tra_mcn["w_dpc_min"]),
                        step=0.25, format="%.2f",
                        help=f"Tá»‘i thiá»ƒu {tra_mcn['w_dpc_min']:g}m theo TCVN 4054:2005"
                             + (" (cáº¥p nÃ y khÃ´ng báº¯t buá»™c cÃ³ dáº£i phÃ¢n cÃ¡ch)." if tra_mcn['w_dpc_min'] == 0 else ".")
                    )
                _dpc_labels = {
                    "be_tong_duc_san": "BT Ä‘Ãºc sáºµn, bÃ³ vá»‰a cÃ³ lá»›p phá»§ (khÃ´ng cÃ³ trá»¥)",
                    "co_tru_cot":      "XÃ¢y bÃ³ vá»‰a, cÃ³ lá»›p phá»§, cÃ³ bá»‘ trÃ­ trá»¥ cÃ´ng trÃ¬nh",
                    "khong_lop_phu":   "KhÃ´ng cÃ³ lá»›p phá»§",
                }
                _dpc_keys = list(_dpc_labels.keys())
                if w_dpc_oto > 0:
                    st.markdown("**Dáº£i phÃ¢n cÃ¡ch giá»¯a (Báº£ng 8 â€“ TCVN 4054:2005)**")
                    loai_dpc_oto = st.selectbox(
                        "Loáº¡i cáº¥u táº¡o dáº£i phÃ¢n cÃ¡ch:",
                        options=_dpc_keys,
                        format_func=lambda k: _dpc_labels[k],
                        help="Theo Äiá»u 4.4.1 â€“ chá»‰ bá»‘ trÃ­ khi Ä‘Æ°á»ng cÃ³ â‰¥ 4 lÃ n xe."
                    )
                    _b8 = YTHH.tra_cuu_dai_phan_cach(loai_dpc_oto)
                    st.caption(
                        f"Tá»‘i thiá»ƒu theo Báº£ng 8: pháº§n phÃ¢n cÃ¡ch â‰¥ **{_b8['w_phan_cach']:g}m** | "
                        f"pháº§n an toÃ n 2Ã—{_b8['w_an_toan_moi_ben']:g}m | "
                        f"Tá»•ng dáº£i PC â‰¥ **{_b8['w_toi_thieu']:g}m**"
                    )
                    if w_dpc_oto < _b8["w_toi_thieu"]:
                        st.warning(
                            f"âš ï¸ Dáº£i phÃ¢n cÃ¡ch nháº­p ({w_dpc_oto:.2f}m) nhá» hÆ¡n tá»‘i thiá»ƒu "
                            f"Báº£ng 8 ({_b8['w_toi_thieu']:g}m) cho loáº¡i '{_dpc_labels[loai_dpc_oto]}'."
                        )
                else:
                    loai_dpc_oto = "be_tong_duc_san"

                _mat_labels = {
                    "btxm_bthua":    "BÃª tÃ´ng xi mÄƒng / bÃª tÃ´ng nhá»±a (1.5â€“2.0%)",
                    "lat_da_tot":    "Máº·t Ä‘Æ°á»ng lÃ¡t Ä‘Ã¡ tá»‘t, pháº³ng (2.0â€“3.0%)",
                    "lat_da_tb":     "Máº·t Ä‘Æ°á»ng lÃ¡t Ä‘Ã¡ cháº¥t lÆ°á»£ng TB (3.0â€“3.5%)",
                    "da_dam_cap_phoi": "ÄÃ¡ dÄƒm, cáº¥p phá»‘i, máº·t Ä‘Æ°á»ng cáº¥p tháº¥p (3.0â€“3.5%)",
                }
                st.markdown("**Äá»™ dá»‘c ngang máº·t Ä‘Æ°á»ng (Báº£ng 9 â€“ TCVN 4054:2005)**")
                loai_mat_duong_oto = st.selectbox(
                    "Loáº¡i máº·t Ä‘Æ°á»ng (áº£nh hÆ°á»Ÿng Ä‘á»™ dá»‘c ngang):",
                    options=list(_mat_labels.keys()),
                    format_func=lambda k: _mat_labels[k],
                )
                _b9 = YTHH.tra_cuu_doc_ngang(loai_mat_duong_oto)
                st.caption(
                    f"Báº£ng 9: Ä‘á»™ dá»‘c ngang máº·t Ä‘Æ°á»ng & lá» gia cá»‘: "
                    f"**{_b9['i_min']:g}% â€“ {_b9['i_max']:g}%** | "
                    f"Lá» khÃ´ng gia cá»‘: **{_b9['i_le_khong_gc_min']:g}% â€“ {_b9['i_le_khong_gc_max']:g}%**"
                )
                i_doc_ngang_oto = st.number_input(
                    "Äá»™ dá»‘c ngang thiáº¿t káº¿ i (%):",
                    min_value=float(_b9["i_min"]),
                    max_value=float(_b9["i_max"]),
                    value=float(_b9["i_goi_y"]),
                    step=0.5, format="%.1f",
                    help=f"TCVN 4054:2005 Báº£ng 9: {_b9['i_min']:g}% â€“ {_b9['i_max']:g}% cho loáº¡i máº·t Ä‘Æ°á»ng nÃ y."
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
                st.warning(f"âš ï¸ {tra_mcn.get('message','KhÃ´ng tra Ä‘Æ°á»£c MCN tá»‘i thiá»ƒu.')}")
                mcn_oto_override = {"cap_duong": cap_duong_oto, "dia_hinh": dia_hinh_mcn}
        else:  # Do thi
            loai_dt = st.selectbox("PhÃ¢n loáº¡i Ä‘Æ°á»ng Ä‘Ã´ thá»‹:", ["Trá»¥c chÃ­nh Ä‘Ã´ thá»‹", "ÄÆ°á»ng chÃ­nh Ä‘Ã´ thá»‹", "ÄÆ°á»ng khu vá»±c", "ÄÆ°á»ng ná»™i bá»™"])
            cap_dt = st.selectbox("Cáº¥p ká»¹ thuáº­t ká»¹ sÆ°:", ["Äáº·c biá»‡t", "Cáº¥p I", "Cáº¥p II"] if loai_dt == "Trá»¥c chÃ­nh Ä‘Ã´ thá»‹" else ["Cáº¥p I", "Cáº¥p II"])
            list_vtk = YTHH.get_vtk_goi_y_dothi(loai_dt, cap_dt)
            v_hinhhoc = st.radio("Váº­n tá»‘c thiáº¿t káº¿ Vtk:", options=list_vtk, horizontal=True)
            d_hinhhoc = st.radio("Äá»‹a hÃ¬nh Ä‘Ã´ thá»‹:", ["1", "2"], format_func=lambda x: "Báº±ng pháº³ng" if x == "1" else "KhÃ³ khÄƒn")
            input_tra_cuu = v_hinhhoc

            _dt_labels = {
                "cao_toc_do_thi":   "ÄÆ°á»ng cao tá»‘c Ä‘Ã´ thá»‹",
                "pho_chinh_chu_yeu":"ÄÆ°á»ng phá»‘ chÃ­nh chá»§ yáº¿u",
                "pho_chinh_thu_yeu":"ÄÆ°á»ng phá»‘ chÃ­nh thá»© yáº¿u",
                "pho_gom":          "ÄÆ°á»ng phá»‘ gom",
                "pho_noi_bo":       "ÄÆ°á»ng phá»‘ ná»™i bá»™",
            }
            _col_dtA, _col_dtB = st.columns(2)
            with _col_dtA:
                loai_dt_mcn = st.selectbox(
                    "Loáº¡i Ä‘Æ°á»ng phá»‘ (MCN â€” Báº£ng 10):",
                    options=list(_dt_labels.keys()),
                    format_func=lambda k: _dt_labels[k],
                    key="loai_dt_mcn",
                )
            with _col_dtB:
                dieu_kien_xd = st.radio(
                    "Äiá»u kiá»‡n xÃ¢y dá»±ng (áº£nh hÆ°á»Ÿng Báº£ng 14, 15):",
                    options=["I", "II", "III"],
                    horizontal=True,
                    key="dieu_kien_xd",
                    help="I: Thuáº­n lá»£i | II: BÃ¬nh thÆ°á»ng | III: KhÃ³ khÄƒn",
                )
            tra_dt = YTHH.tra_cuu_mcn_do_thi(v_hinhhoc, loai_dt_mcn, dieu_kien_xd)

            if tra_dt.get("status") == "success":
                st.caption(
                    f"ðŸ“ **Báº£ng 10** â€” {tra_dt['mo_ta']} | VTK {v_hinhhoc} km/h | "
                    f"LÃ n tá»‘i thiá»ƒu: **{tra_dt['w_lan_min']:.2f}m** | "
                    f"Sá»‘ lÃ n: **{tra_dt['so_lan_toi_thieu']}** (mong muá»‘n {tra_dt['so_lan_mong_muon']})"
                )
                _dat_at_cap = (tra_dt['w_dat_at_loaiI'] if dieu_kien_xd == "I"
                               else tra_dt['w_dat_at_loaiII_III'])
                st.caption(
                    f"ðŸ“ **Báº£ng 13** â€” Lá»: **{tra_dt['w_le_min']:.2f}Ã·{tra_dt['w_le_max']:.2f}m** | "
                    + (f"Dáº£i AT (Ä‘k {dieu_kien_xd}): **{_dat_at_cap:.2f}m**"
                       if _dat_at_cap else "Dáº£i AT: khÃ´ng báº¯t buá»™c á»Ÿ VTK nÃ y")
                )
                if tra_dt["co_dpc"] and tra_dt["dpc_min"] is not None:
                    st.caption(
                        f"ðŸ“ **Báº£ng 14** â€” Dáº£i phÃ¢n cÃ¡ch tá»‘i thiá»ƒu (Ä‘k {dieu_kien_xd}): "
                        f"**{tra_dt['dpc_min']:.2f}m** (mong muá»‘n {tra_dt['dpc_mong_muon']:.2f}m)"
                    )
                elif tra_dt.get("dpc_note"):
                    st.caption(f"ðŸ“ **Báº£ng 14** â€” {tra_dt['dpc_note']}")
                if tra_dt["he_min"] is not None:
                    st.caption(
                        f"ðŸ“ **Báº£ng 15** â€” HÃ¨ Ä‘Æ°á»ng tá»‘i thiá»ƒu (Ä‘k {dieu_kien_xd}): "
                        f"**{tra_dt['he_min']:.1f}m**"
                    )

                st.markdown("**Pháº§n xe cháº¡y (Báº£ng 10):**")
                _c1, _c2 = st.columns(2)
                with _c1:
                    n_lan_dt = st.number_input(
                        "Sá»‘ lÃ n xe:",
                        min_value=tra_dt["so_lan_toi_thieu"], value=tra_dt["so_lan_toi_thieu"],
                        step=2, key="n_lan_dt",
                    )
                    w_lan_dt = st.number_input(
                        "Chiá»u rá»™ng 1 lÃ n xe (m):",
                        min_value=tra_dt["w_lan_min"], value=tra_dt["w_lan_min"],
                        step=0.25, format="%.2f", key="w_lan_dt",
                    )
                with _c2:
                    w_le_dt = st.number_input(
                        f"Lá» Ä‘Æ°á»ng (m) â€” tá»‘i thiá»ƒu {tra_dt['w_le_min']:.2f}m:",
                        min_value=tra_dt["w_le_min"],
                        max_value=max(tra_dt["w_le_max"], tra_dt["w_le_min"] + 3.0),
                        value=tra_dt["w_le_min"],
                        step=0.25, format="%.2f", key="w_le_dt",
                    )

                st.markdown("**Dáº£i phÃ¢n cÃ¡ch giá»¯a (Báº£ng 14):**")
                if tra_dt["co_dpc"] and tra_dt["dpc_min"] is not None:
                    w_dpc_dt = st.number_input(
                        f"Chiá»u rá»™ng DPC (m) â€” tá»‘i thiá»ƒu {tra_dt['dpc_min']:.2f}m "
                        f"(mong muá»‘n {tra_dt['dpc_mong_muon']:.2f}m):",
                        min_value=tra_dt["dpc_min"],
                        value=tra_dt["dpc_min"],
                        step=0.50, format="%.2f", key="w_dpc_dt",
                    )
                elif tra_dt.get("dpc_note"):
                    st.info(f"â„¹ï¸ {tra_dt['dpc_note']}")
                    w_dpc_dt = 0.0
                else:
                    w_dpc_dt = st.number_input(
                        "Chiá»u rá»™ng DPC (m, 0 náº¿u khÃ´ng cÃ³):",
                        min_value=0.0, value=0.0, step=0.5, format="%.2f", key="w_dpc_dt",
                    )

                st.markdown("**HÃ¨ Ä‘Æ°á»ng / Dáº£i bÃªn Ä‘Æ°á»ng (Báº£ng 15):**")
                _he_min_val = tra_dt["he_min"] if tra_dt["he_min"] is not None else 0.0
                if _he_min_val > 0:
                    w_he_dt = st.number_input(
                        f"Chiá»u rá»™ng hÃ¨ Ä‘Æ°á»ng (m) â€” tá»‘i thiá»ƒu {_he_min_val:.1f}m:",
                        min_value=_he_min_val, value=_he_min_val,
                        step=0.5, format="%.1f", key="w_he_dt",
                    )
                else:
                    st.info("â„¹ï¸ Loáº¡i Ä‘Æ°á»ng nÃ y khÃ´ng quy Ä‘á»‹nh hÃ¨ Ä‘Æ°á»ng báº¯t buá»™c.")
                    w_he_dt = st.number_input(
                        "Chiá»u rá»™ng hÃ¨ Ä‘Æ°á»ng (m, 0 náº¿u khÃ´ng cÃ³):",
                        min_value=0.0, value=0.0, step=0.5, format="%.1f", key="w_he_dt",
                    )

                with st.expander("ðŸ“‹ Báº£ng 16 â€” KÃ­ch thÆ°á»›c tá»‘i thiá»ƒu dáº£i trá»“ng cÃ¢y (tham kháº£o)"):
                    _tc_ref = tra_dt.get("trong_cay_ref", {})
                    _tc_labels = {
                        "cay_bong_mat_1_hang":     "CÃ¢y bÃ³ng mÃ¡t trá»“ng 1 hÃ ng",
                        "cay_bong_mat_2_hang":     "CÃ¢y bÃ³ng mÃ¡t trá»“ng 2 hÃ ng",
                        "dai_cay_bui_bai_co":      "Dáº£i cÃ¢y bá»¥i, bÃ£i cá»",
                        "vuon_cay_nha_1_tang":     "VÆ°á»n cÃ¢y trÆ°á»›c nhÃ  1 táº§ng",
                        "vuon_cay_nha_nhieu_tang": "VÆ°á»n cÃ¢y trÆ°á»›c nhÃ  nhiá»u táº§ng",
                    }
                    st.table(pd.DataFrame({
                        "HÃ¬nh thá»©c trá»“ng cÃ¢y": [_tc_labels.get(k, k) for k in _tc_ref],
                        "Chiá»u rá»™ng tá»‘i thiá»ƒu (m)": list(_tc_ref.values()),
                    }))

                st.markdown("**Äá»™ dá»‘c ngang (Báº£ng 12):**")
                _loai_mat_dt_labels = {
                    "btxm_bthua":      "BÃª tÃ´ng xi mÄƒng / bÃª tÃ´ng nhá»±a",
                    "nhua_khac":       "Máº·t Ä‘Æ°á»ng nhá»±a khÃ¡c",
                    "lat_da_tot":      "LÃ¡t Ä‘Ã¡ tá»‘t, pháº³ng",
                    "da_dam_cap_phoi": "ÄÃ¡ dÄƒm, cáº¥p phá»‘i",
                }
                loai_mat_dt = st.selectbox(
                    "Loáº¡i máº·t Ä‘Æ°á»ng:",
                    options=list(_loai_mat_dt_labels.keys()),
                    format_func=lambda k: _loai_mat_dt_labels[k],
                    key="loai_mat_dt",
                )
                tra_doc_dt = YTHH.tra_cuu_doc_ngang_do_thi(loai_mat_dt)
                i_doc_ngang_dt = st.number_input(
                    f"Äá»™ dá»‘c ngang i (%) â€” Báº£ng 12: {tra_doc_dt['i_min']:g}Ã·{tra_doc_dt['i_max']:g}%:",
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
                st.warning(f"âš ï¸ {tra_dt.get('message','KhÃ´ng tra Ä‘Æ°á»£c MCN Ä‘Ã´ thá»‹.')}")
                mcn_oto_override = {"loai_dt": loai_dt_mcn, "dieu_kien_xd": dieu_kien_xd}

        b_cau = st.number_input(
            "Bá» rá»™ng Bc máº·t cáº¯t cáº§u (m):",
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

            st.markdown("**BÃ¡n kÃ­nh Ä‘Æ°á»ng cong Ä‘á»©ng lá»“i**")
            st.caption(
                f"Theo {res_geo['tieu_chuan']}: R giá»›i háº¡n (tá»‘i thiá»ƒu) = **{r_gh:,.0f} m** | "
                f"R thÃ´ng thÆ°á»ng (khuyáº¿n nghá»‹) = **{r_tt:,.0f} m**"
            )
            r_final_calc = st.number_input(
                "BÃ¡n kÃ­nh Ä‘Æ°á»ng cong Ä‘á»©ng lá»“i R thiáº¿t káº¿ (m):",
                min_value=r_gh, value=max(r_tt, r_gh), step=100.0, format="%.0f",
                help=f"KhÃ´ng Ä‘Æ°á»£c nhá» hÆ¡n giÃ¡ trá»‹ giá»›i háº¡n tá»‘i thiá»ƒu {r_gh:,.0f} m theo {res_geo['tieu_chuan']}."
            )

            st.markdown("**Äá»™ dá»‘c dá»c**")
            st.caption(f"Äá»™ dá»‘c dá»c lá»›n nháº¥t cho phÃ©p theo tiÃªu chuáº©n: **imax = {imax_calc:.1f} %**")
            i_final_calc = st.number_input(
                "Äá»™ dá»‘c dá»c thiáº¿t káº¿ i (%):",
                min_value=0.0, max_value=imax_calc, value=imax_calc, step=0.1, format="%.1f",
                help=f"KhÃ´ng Ä‘Æ°á»£c vÆ°á»£t quÃ¡ Ä‘á»™ dá»‘c dá»c lá»›n nháº¥t cho phÃ©p {imax_calc:.1f}% theo {res_geo['tieu_chuan']}."
            )
        else:
            st.error(
                f"âŒ KhÃ´ng tra Ä‘Æ°á»£c yáº¿u tá»‘ hÃ¬nh há»c cho loáº¡i Ä‘Æ°á»ng **{l_hinhhoc}**: "
                f"{res_geo.get('message', 'Lá»—i khÃ´ng xÃ¡c Ä‘á»‹nh')}. "
                "Khi nháº¥n **Tiáº¿p theo**, há»‡ thá»‘ng sáº½ **khÃ´ng** cháº¡y Ä‘Æ°á»£c AI pipeline."
            )

        # LÆ°u draft trÃªn má»—i rerun cá»§a bÆ°á»›c 2
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
            if st.button("â—€ Quay láº¡i", use_container_width=True, key="wz_back2"):
                st.session_state.wizard_step = 1
                st.rerun()
        with btn_f:
            if st.button("Tiáº¿p theo â–¶", use_container_width=True, type="primary", key="wz_next2"):
                errs = _validate_step2(st.session_state.wizard_draft)
                st.session_state.wizard_errors['step2'] = errs
                if not errs:
                    st.session_state.wizard_step = 3
                    st.rerun()
                else:
                    for msg in errs.values():
                        st.error(f"âš ï¸ {msg}")

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # BÆ¯á»šC 3 â€” XEM Láº I & CHáº Y AI
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    elif step == 3:
        st.markdown(
            DS.section_header(
                title = "Xem láº¡i thÃ´ng sá»‘ & Cháº¡y tÃ­nh toÃ¡n",
                icon  = "âœ…",
                sub   = "Kiá»ƒm tra láº¡i toÃ n bá»™ trÆ°á»›c khi cháº¡y pipeline AI",
            ),
            unsafe_allow_html=True,
        )

        draft = st.session_state.wizard_draft

        with st.expander("ðŸŒŠ Thá»§y vÄƒn & Vá»‹ trÃ­", expanded=True):
            s1a, s1b, s1c = st.columns(3)
            s1a.metric("Khu vá»±c", "Miá»n Báº¯c" if draft.get('mien') == '1' else "Miá»n Nam")
            s1b.metric("Cáº¥p sÃ´ng", f"Cáº¥p {['I','II','III','IV','V','VI'][int(draft.get('cap_s',4))-1]}")
            s1c.metric("Loáº¡i hÃ¬nh", "KÃªnh Ä‘Ã o" if draft.get('loai_h') == '1' else "SÃ´ng tá»± nhiÃªn")
            s2a, s2b, s2c, s2d = st.columns(4)
            s2a.metric("MNCN (H1%)", f"{draft.get('h1', 0):.3f} m")
            s2b.metric("MNTT (H5%)", f"{draft.get('h5', 0):.3f} m")
            s2c.metric("MNTC (H10%)", f"{draft.get('h10', 0):.3f} m")
            s2d.metric("MNTN (H98%)", f"{draft.get('h98', 0):.3f} m")
            st.caption(
                f"ðŸ“ Tim cáº§u: **{draft.get('x_tim_clearance', 0):.2f} m** | "
                f"GÃ³c giao: **{draft.get('goc_giao', 90):.0f}Â°** | "
                f"Báº£n máº·t cáº§u: **{draft.get('t_ban_mm', 200)} mm**"
            )

        with st.expander("ðŸ›£ï¸ HÃ¬nh há»c tuyáº¿n", expanded=True):
            _loai_map = {"Cao tá»‘c": "ðŸ›£ï¸ Cao tá»‘c", "O to": "ðŸš— Ã” tÃ´", "Do thi": "ðŸ™ï¸ ÄÃ´ thá»‹"}
            st.markdown(
                f"Loáº¡i Ä‘Æ°á»ng: **{_loai_map.get(draft.get('l_hinhhoc',''), 'â€”')}** | "
                f"Vtk: **{draft.get('vtk', 'â€”')} km/h** | "
                f"Äá»‹a hÃ¬nh: **{'Äá»“ng báº±ng' if draft.get('d_hinhhoc')=='1' else 'NÃºi/KhÃ³ khÄƒn'}**"
            )
            _mcn = draft.get('mcn_oto_override', {})
            if _mcn:
                st.caption(
                    f"Sá»‘ lÃ n: {_mcn.get('so_lan', _mcn.get('n_lan_moi_chieu', 'â€”'))} | "
                    f"Rá»™ng lÃ n: {_mcn.get('w_lan', 'â€”')} m | "
                    f"Lá»: {_mcn.get('w_le', _mcn.get('w_le_dat', 'â€”'))} m"
                )
            st.caption(
                f"Bc = **{draft.get('b_cau', 0):.1f} m** | "
                f"R = **{draft.get('r_final_calc', 0):.0f} m** | "
                f"i = **{draft.get('i_final_calc', 0):.1f} %**"
            )

        ed1, ed2, _ = st.columns([1, 1, 2])
        with ed1:
            if st.button("âœï¸ Sá»­a thá»§y vÄƒn", key="wz_edit1", use_container_width=True):
                st.session_state.wizard_step = 1
                st.rerun()
        with ed2:
            if st.button("âœï¸ Sá»­a hÃ¬nh há»c", key="wz_edit2", use_container_width=True):
                st.session_state.wizard_step = 2
                st.rerun()

        st.markdown("---")
        st.markdown("**ðŸ˜ï¸ Äiá»u kiá»‡n Ä‘á»‹a phÆ°Æ¡ng**")
        is_urban_chk = st.checkbox(
            "Khu vá»±c Ä‘Ã´ng dÃ¢n cÆ° (háº¡n cháº¿ tiáº¿ng á»“n/rung)",
            value=bool(draft.get('is_urban', st.session_state.design_data.get('is_urban', 0))),
            help="áº¢nh hÆ°á»Ÿng Ä‘áº¿n lá»±a chá»n loáº¡i cá»c: khu Ä‘Ã´ng dÃ¢n â†’ Æ°u tiÃªn cá»c Ã©p",
            key="wz_urban",
        )
        st.session_state.wizard_draft['is_urban'] = int(is_urban_chk)

        st.markdown("<br>", unsafe_allow_html=True)
        back_col, run_col = st.columns([1, 2])
        with back_col:
            if st.button("â—€ Quay láº¡i", use_container_width=True, key="wz_back3"):
                st.session_state.wizard_step = 2
                st.rerun()
        with run_col:
            st.markdown(
                "<p style='font-size:11px;color:#888;margin-bottom:4px'>"
                "ðŸ¤– Pipeline AI: TK â†’ HÃ¬nh há»c â†’ KCN â†’ Trá»¥ â†’ MÃ³ng â†’ Lá»›p phá»§ â†’ Báº£n váº½ â†’ So sÃ¡nh PA</p>",
                unsafe_allow_html=True,
            )
            submitted = st.button(
                "ðŸš€ CHáº Y TÃNH TOÃN AI",
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

            # Re-compute terrain data tá»« session state
            _df_tl = st.session_state.get('df_tim_line', None)
            lt_diahinh_arr = None
            z_diahinh_arr  = None
            h_tn_tb = st.session_state.design_data.get('h_tn_tb', 0.0)
            if _df_tl is not None and not _df_tl.empty:
                _lt_col_t = next((c for c in _df_tl.columns if 'Ã½ trÃ¬nh' in c or c.lower()=='ly_trinh'), None)
                _z_col_t  = next((c for c in _df_tl.columns if c.upper() == 'Z'), None)
                if _lt_col_t and _z_col_t:
                    _mask_t = ((_df_tl[_lt_col_t] >= x_tim_clearance - 80) &
                               (_df_tl[_lt_col_t] <= x_tim_clearance + 80))
                    _sub_t = _df_tl[_mask_t]
                    h_tn_tb = float(_sub_t[_z_col_t].mean()) if not _sub_t.empty else float(_df_tl[_z_col_t].mean())
                    lt_diahinh_arr = _df_tl[_lt_col_t].to_numpy()
                    z_diahinh_arr  = _df_tl[_z_col_t].to_numpy()

            # â”€â”€ Khá»Ÿi táº¡o tracker â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            tracker = PipelineTracker(PIPELINE_STEPS)
            tracker.setup()
            pipeline_ok = True
            kcn_models  = None
            pier_models = None
            fnd_models  = None

            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            # BÆ¯á»šC 1 â€” TÄ¨NH KHÃ”NG
            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
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
                res['loai_doi_tuong_vuot'] = "VÆ°á»£t sÃ´ng"
                res['t_ban_mm'] = t_ban_mm
                res['is_urban'] = is_urban_val
                res['x_tim_clearance'] = x_tim_clearance
                res['mcn_oto_input'] = mcn_oto_override
                tracker.done("TK", f"B={res.get('B',0)}m  H={res.get('H',0)}m  ÄÃ¡y dáº§mâ‰¥{res.get('day_dam',0):.3f}m")
            except Exception as _e:
                tracker.error("TK", str(_e))
                pipeline_ok = False
                res = {}

            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            # BÆ¯á»šC 2 â€” Yáº¾U Tá» HÃŒNH Há»ŒC  (critical)
            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            if pipeline_ok:
                tracker.start("YTHH")
                try:
                    res_geo = YTHH.tra_cuu_yeu_to_hinh_hoc(l_hinhhoc, input_tra_cuu, d_hinhhoc)
                    if res_geo.get("status") != "success":
                        raise ValueError(
                            f"KhÃ´ng tÃ­nh Ä‘Æ°á»£c yáº¿u tá»‘ hÃ¬nh há»c tuyáº¿n: "
                            f"{res_geo.get('message', 'Lá»—i khÃ´ng xÃ¡c Ä‘á»‹nh')}. "
                            "Kiá»ƒm tra láº¡i Loáº¡i Ä‘Æ°á»ng, Váº­n tá»‘c thiáº¿t káº¿ vÃ  Äá»‹a hÃ¬nh."
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
                    moi_tr = "VÆ°á»£t sÃ´ng"
                    v3_path = os.path.join(os.path.dirname(__file__), "Data", "Bridge_Train_Dataset_v3.xlsx")
                    res['ai_result'] = None
                    tracker.done("YTHH",
                        f"L_cáº§u={L_cau:.1f}m  Bc={b_cau:.1f}m  Vtk={res['vtk']}km/h")
                except Exception as _e:
                    tracker.error("YTHH", str(_e))
                    pipeline_ok = False
            else:
                tracker.skip("YTHH")

            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            # BÆ¯á»šC 3 â€” AI Káº¾T Cáº¤U NHá»ŠP
            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
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
                        f"{_kr.get('tong_so_nhip','?')} nhá»‹p Ã— "
                        f"{_kr.get('chieu_dai','?')}m ({_kr.get('loai_dam','?')})")
                except Exception as _e:
                    tracker.error("KCN", str(_e))
                    res['kcn_result'] = None
            else:
                tracker.skip("KCN")

            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            # BÆ¯á»šC 4 â€” AI Má» â€“ TRá»¤
            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
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
                        f"{_tr.get('loai_tru','?')}  H_trá»¥â‰ˆ{H_tru_est:.1f}m")
                except Exception as _e:
                    tracker.error("MOT", str(_e))
                    res['tru_result'] = None
                    H_tru_est = 8.0
                    is_river  = 1
            else:
                tracker.skip("MOT")

            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            # BÆ¯á»šC 5 â€” AI MÃ“NG Cáº¦U
            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            if pipeline_ok:
                tracker.start("MONG")
                try:
                    loai_tru_str = (
                        res['tru_result']['loai_tru'] if res.get('tru_result')
                        else 'ThÃ¢n cá»™t 2 trá»¥'
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

            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            # BÆ¯á»šC 6 â€” Lá»šP PHá»¦ Máº¶T Cáº¦U
            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            tracker.start("LPC")
            try:
                res['lop_phu_result'] = LPC.tu_van_lop_phu(
                    vtk=res.get('vtk', 60),
                    loai_duong=res.get('loai_duong', 'Do thi'),
                    L_nhip=(res.get('kcn_result', {}).get('chieu_dai', 40)
                            if res.get('kcn_result') else 40),
                    moi_truong="VÆ°á»£t sÃ´ng",
                )
                _lp = res.get('lop_phu_result') or {}
                _lp_pa = str(_lp.get('phuong_an', '?'))
                tracker.done("LPC", (_lp_pa[:40] + "...") if len(_lp_pa) > 40 else _lp_pa)
            except Exception as _e:
                tracker.error("LPC", str(_e))
                res['lop_phu_result'] = None

            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            # BÆ¯á»šC 7 â€” Báº¢N Váº¼ Káº¾T Cáº¤U
            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            tracker.start("BVK")
            try:
                importlib.reload(BVK)
                importlib.reload(CTD)
                tracker.done("BVK", "Báº£n váº½ 2D/3D Ä‘Ã£ sáºµn sÃ ng")
            except Exception as _e:
                tracker.error("BVK", str(_e))

            # LÆ°u design_data trÆ°á»›c khi cháº¡y SSP
            if pipeline_ok:
                st.session_state.design_data = res

            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            # BÆ¯á»šC 8 â€” SO SÃNH 3 PHÆ¯Æ NG ÃN
            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            tracker.start("SSP")
            try:
                st.session_state.alternatives = SSP.generate_3_alternatives(
                    B_tk=res.get('B', 20), H_tk=res.get('H', 3.5), goc=goc_giao,
                    B_cau=res.get('bc', 12), moi_truong=moi_tr if pipeline_ok else "VÆ°á»£t sÃ´ng",
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
                tracker.done("SSP", "3 phÆ°Æ¡ng Ã¡n Ä‘Ã£ Ä‘Æ°á»£c sinh vÃ  Ä‘Ã¡nh giÃ¡")
            except Exception as _e:
                tracker.error("SSP", str(_e))
                st.session_state.alternatives = None

            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            # Káº¾T THÃšC PIPELINE
            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
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
                    st.success("âœ… Pipeline hoÃ n táº¥t â€” chuyá»ƒn sang Báº£n váº½ ká»¹ thuáº­t")
                else:
                    st.warning(
                        f"âš ï¸ Pipeline hoÃ n táº¥t vá»›i {n_errors} bÆ°á»›c cÃ³ cáº£nh bÃ¡o. "
                        "Káº¿t quáº£ váº«n Ä‘Æ°á»£c lÆ°u â€” xem chi tiáº¿t á»Ÿ trÃªn."
                    )
                time.sleep(0.8)
                st.session_state.current_tab = "Báº¢N Váº¼ Ká»¸ THUáº¬T"
                st.rerun()
            elif n_critical_errors > 0:
                st.error(
                    f"âŒ {n_critical_errors} bÆ°á»›c quan trá»ng tháº¥t báº¡i. "
                    "Kiá»ƒm tra láº¡i sá»‘ liá»‡u Ä‘áº§u vÃ o vÃ  thá»­ láº¡i."
                )

    # â”€â”€ Fallback: step ngoÃ i pháº¡m vi â†’ reset â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    else:
        st.session_state.wizard_step = 1
        st.rerun()


# TRáº NG THÃI TAB & RIBBON TÃ™Y CHá»ˆNH
# =========================================================================

# Map tÃªn tab cÅ© vá» má»›i
if st.session_state.current_tab == "Báº¢N Váº¼ Káº¾T Cáº¤U":
    st.session_state.current_tab = "Báº¢N Váº¼ Ká»¸ THUáº¬T"


def _get_tab_states(d: dict) -> dict:
    """Tráº£ vá» dict tráº¡ng thÃ¡i 'done' | 'partial' | 'locked' cho 3 tab."""
    has_kcn  = bool(d.get('kcn_result'))
    has_tru  = bool(d.get('tru_result'))
    has_mong = bool(d.get('mong_result'))
    has_basic = bool(d.get('day_dam')) or bool(d.get('bc'))

    # Tab 0 â€” THUYáº¾T MINH
    if has_kcn and has_tru and has_mong:
        tab0 = 'done'
    elif has_basic:
        tab0 = 'partial'
    else:
        tab0 = 'locked'

    # Tab 1 â€” Báº¢N Váº¼ Ká»¸ THUáº¬T
    if has_kcn and has_tru:
        tab1 = 'done'
    elif has_kcn:
        tab1 = 'partial'
    else:
        tab1 = 'locked'

    # Tab 2 â€” SO SÃNH PHÆ¯Æ NG ÃN
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
                'badge_text': '#0d3d1f', 'text': '#e0ffe8', 'icon': 'âœ“'},
    'partial': {'bg': '#3a2c00', 'border': '#f39c12', 'badge_bg': '#f39c12',
                'badge_text': '#1a1000', 'text': '#fff3cc', 'icon': 'â³'},
    'locked':  {'bg': '#1a1a2a', 'border': '#444466', 'badge_bg': '#333355',
                'badge_text': '#9999bb', 'text': '#888899', 'icon': 'â—‹'},
}
_STATE_LABEL = {
    'done':    'HoÃ n táº¥t',
    'partial': 'Äang tÃ­nh',
    'locked':  'ChÆ°a cÃ³ dá»¯ liá»‡u',
}
_TAB_META = [
    {
        'key':      'THUYáº¾T MINH',
        'icon':     'ðŸ“‹',
        'state':    tab_states['tab0'],
        'tip':      'Káº¿t quáº£ tÃ­nh toÃ¡n tá»•ng há»£p',
        'lock_msg': 'Nháº¥n OPTIONS â†’ OK Ä‘á»ƒ cháº¡y tÃ­nh toÃ¡n',
    },
    {
        'key':      'Báº¢N Váº¼ Ká»¸ THUáº¬T',
        'icon':     'ðŸ“',
        'state':    tab_states['tab1'],
        'tip':      'Báº£n váº½ 2D/3D káº¿t cáº¥u cáº§u',
        'lock_msg': 'Cáº§n cháº¡y tÃ­nh toÃ¡n káº¿t cáº¥u nhá»‹p trÆ°á»›c',
    },
    {
        'key':      'SO SÃNH PHÆ¯Æ NG ÃN',
        'icon':     'ðŸ“Š',
        'state':    tab_states['tab2'],
        'tip':      'So sÃ¡nh 3 phÆ°Æ¡ng Ã¡n loáº¡i dáº§m',
        'lock_msg': 'Cáº§n cháº¡y tÃ­nh toÃ¡n nhá»‹p trÆ°á»›c',
    },
]

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# LAYOUT HELPERS â€” Topbar / Right panel / Status bar
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _render_topbar(d: dict, cur_tab: str) -> None:
    """Fixed 44px topbar: logo + tab nav + quick info + user."""
    _kcn   = d.get('kcn_result') or {}
    _geo   = d.get('geo_logic') or {}
    _L     = _geo.get('L_cau', 0)
    _dam   = _kcn.get('loai_dam', '')
    _nhip  = _kcn.get('tong_so_nhip', '')
    _cdai  = _kcn.get('chieu_dai', '')
    _info  = (
        f"L={_L:.1f}m Â· {_nhip}Ã—{_cdai}m Â· {_dam}"
        if _L else "ChÆ°a cÃ³ dá»¯ liá»‡u â€” nháº¥n OPTIONS"
    )
    _u     = AUTH.current_user()
    _uname = _u.get('name', _u.get('username', ''))
    _crown = 'ðŸ‘‘' if AUTH.is_admin() else 'ðŸ‘¤'

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
        f"height:44px;display:flex;align-items:center'>ðŸ—ï¸ UTH</div>"
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
    """HTML cho má»™t result card trong right panel."""
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
        "letter-spacing:0.4px;margin:0 0 8px'>Káº¿t quáº£ AI</div>",
        unsafe_allow_html=True,
    )

    # Card 1 â€” Káº¿t cáº¥u nhá»‹p
    if _kcn:
        _dam     = _kcn.get('loai_dam', 'â€”')
        _col_dam = DS.dam_color(_dam)
        _c1 = (
            f"<div style='font-size:13px;font-weight:600;color:{_col_dam}'>{_dam}</div>"
            f"<div style='font-size:10px;color:#888;margin-top:3px'>"
            f"{_kcn.get('tong_so_nhip','?')} nhá»‹p Ã— {_kcn.get('chieu_dai','?')}m"
            f" Â· H={_kcn.get('chieu_cao_dam') or _kcn.get('chieu_cao','?')}m</div>"
        )
    else:
        _c1 = "<div style='font-size:11px;color:#444;text-align:center;padding:6px'>ChÆ°a tÃ­nh toÃ¡n</div>"
    st.markdown(_rcard("Káº¿t cáº¥u nhá»‹p", "ðŸŒ‰", _c1, "#007acc"), unsafe_allow_html=True)

    # Card 2 â€” Má»‘ â€“ Trá»¥
    if _tru:
        _lt = _tru.get('loai_tru', 'â€”')
        _ht = d.get('H_tru_est', 'â€”')
        _lmo = _tru.get('loai_mo', 'â€”')
        _c2 = (
            f"<div style='font-size:13px;font-weight:600;color:#c39bd3'>{_lt}</div>"
            f"<div style='font-size:10px;color:#888;margin-top:3px'>"
            f"Hâ‰ˆ{_ht}m Â· Má»‘: {str(_lmo)[:18]}</div>"
        )
    else:
        _c2 = "<div style='font-size:11px;color:#444;text-align:center;padding:6px'>ChÆ°a tÃ­nh toÃ¡n</div>"
    st.markdown(_rcard("Má»‘ â€“ Trá»¥", "ðŸ›ï¸", _c2, "#9b59b6"), unsafe_allow_html=True)

    # Card 3 â€” MÃ³ng
    if _mong:
        _lm      = _mong.get('loai_mong', 'â€”')
        _col_mng = DS.mong_color(_lm)
        _dc      = _mong.get('duong_kinh_coc', 'â€”')
        _c3 = (
            f"<div style='font-size:13px;font-weight:600;color:{_col_mng}'>{_lm}</div>"
            f"<div style='font-size:10px;color:#888;margin-top:3px'>D = {_dc}m</div>"
        )
    else:
        _c3 = "<div style='font-size:11px;color:#444;text-align:center;padding:6px'>ChÆ°a tÃ­nh toÃ¡n</div>"
    st.markdown(_rcard("MÃ³ng cáº§u", "âš™ï¸", _c3, "#e67e22"), unsafe_allow_html=True)

    # Card 4 â€” HÃ¬nh há»c tá»•ng quÃ¡t
    _L   = _geo.get('L_cau', 0)
    _bc  = d.get('bc', 0)
    _vtk = d.get('vtk', 0)
    if _L:
        _c4 = (
            f"<div style='font-size:13px;font-weight:600;color:#2ecc71'>{_L:.2f} m</div>"
            f"<div style='font-size:10px;color:#888;margin-top:3px'>"
            f"Bc={_bc:.1f}m Â· Vtk={_vtk} km/h</div>"
        )
    else:
        _c4 = "<div style='font-size:11px;color:#444;text-align:center;padding:6px'>ChÆ°a cÃ³ dá»¯ liá»‡u</div>"
    st.markdown(_rcard("HÃ¬nh há»c tá»•ng quÃ¡t", "ðŸ“", _c4, "#2ecc71"), unsafe_allow_html=True)


def _render_statusbar(d: dict) -> None:
    """Fixed 22px status bar á»Ÿ dÆ°á»›i cÃ¹ng: pipeline progress."""
    _steps = [
        ("KCN",      bool(d.get('kcn_result'))),
        ("Má»‘-trá»¥",   bool(d.get('tru_result'))),
        ("MÃ³ng",     bool(d.get('mong_result'))),
        ("Lá»›p phá»§",  bool(d.get('lop_phu_result'))),
        ("So sÃ¡nh",  bool(st.session_state.get('alternatives'))),
    ]
    _done  = sum(1 for _, ok in _steps if ok)
    _items = " &nbsp;Â·&nbsp; ".join(
        (
            f"<span style='color:#2ecc71'>âœ“ {name}</span>"
            if ok else
            f"<span style='color:#333355'>â—‹ {name}</span>"
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
        f"{_done}/5 bÆ°á»›c</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


# â”€â”€ Topbar + nav buttons (phá»§ lÃªn topbar) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_cur_tab = st.session_state.get('current_tab', 'THUYáº¾T MINH')
_render_topbar(st.session_state.design_data, _cur_tab)

_col_tabs = st.columns(3)
for _ci, (_col, _m) in enumerate(zip(_col_tabs, _TAB_META)):
    with _col:
        if _m['state'] == 'locked':
            st.button(
                f"{_m['icon']} {_m['key']}",
                disabled=True,
                use_container_width=True,
                help=f"ðŸ”’ {_m['lock_msg']}",
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

# â”€â”€ HÃ ng nÃºt OPTIONS + thÃ´ng sá»‘ hiá»‡n hÃ nh â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ctrl_col1, ctrl_col2 = st.columns([1, 4])
with ctrl_col1:
    _has_result = bool(st.session_state.design_data.get('kcn_result'))
    _btn_label  = "âš™ï¸ CHá»ˆNH Sá»¬A Sá» LIá»†U" if _has_result else "âš™ï¸ OPTIONS â€” KHAI BÃO Sá» LIá»†U"
    if st.button(
        _btn_label,
        use_container_width=True,
        type="secondary" if _has_result else "primary",
        help="Nháº¥n Ä‘á»ƒ má»Ÿ há»™p thoáº¡i nháº­p thÃ´ng sá»‘ â€” báº¯t buá»™c trÆ°á»›c khi tÃ­nh toÃ¡n",
        key="btn_options_main",
    ):
        # Reset validation state Ä‘á»ƒ trÃ¡nh lá»—i cÅ© hiá»‡n láº¡i
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
            f"ðŸ“Š <b>ThÃ´ng sá»‘ hiá»‡n hÃ nh:</b> "
            f"L = <b>{_geo_p.get('L_cau',0):.2f}m</b> | "
            f"Káº¿t cáº¥u nhá»‹p: <b>{_ai_p.get('tong_so_nhip','?')} nhá»‹p Ã— {_ai_p.get('chieu_dai','?')}m "
            f"(Dáº§m {_ai_p.get('loai_dam','').upper()})</b> | "
            f"H = <b>{_ai_p.get('chieu_cao_dam') or _ai_p.get('chieu_cao','â€”')}m</b>"
            f"</div>",
            unsafe_allow_html=True
        )

# --- THANH SIDEBAR TRÃI ---
with st.sidebar:

    # â”€â”€ VÃ™NG A: ThÃ´ng tin dá»± Ã¡n â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path   = os.path.join(current_dir, "Images", "UTH.jpg")
    if os.path.exists(logo_path):
        st.image(logo_path, width=260)

    st.markdown(
        "<div style='background:#1e1e2e;border:1px solid #2a2a3a;"
        "border-radius:8px;padding:10px 12px;margin:6px 0'>"
        "<div style='font-size:11px;color:#555;margin-bottom:6px;"
        "text-transform:uppercase;letter-spacing:0.4px'>Äá» tÃ i</div>"
        "<div style='font-size:12px;color:#ccc;line-height:1.5'>"
        "TÃ­ch há»£p AI vÃ  BIM tá»± Ä‘á»™ng hÃ³a<br>thiáº¿t káº¿ cáº§u Ä‘Æ°á»ng bá»™</div>"
        "<hr style='border-color:#2a2a3a;margin:8px 0'>"
        "<div style='font-size:11px;color:#888'>"
        "ðŸ‘¤ <b style='color:#aaa'>SVTH:</b> ChÆ°Æ¡ng DND<br>"
        "ðŸ‘¨â€ðŸ« <b style='color:#aaa'>GVHD:</b> T.S Nguyá»…n VÄƒn Hiá»ƒn"
        "</div></div>",
        unsafe_allow_html=True,
    )

    _u = AUTH.current_user()
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:8px;padding:6px 0'>"
        f"<span style='font-size:18px'>{'ðŸ‘‘' if AUTH.is_admin() else 'ðŸ‘¤'}</span>"
        f"<div>"
        f"<div style='font-size:12px;color:#ddd;font-weight:600'>"
        f"{_u.get('name', _u.get('username',''))}</div>"
        f"<div style='font-size:10px;color:#666'>{_u.get('role','').upper()}</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    _col_lo, _col_acc = st.columns(2)
    with _col_lo:
        if st.button("ðŸšª ÄÄƒng xuáº¥t", use_container_width=True, key="btn_logout"):
            AUTH.logout()
            st.rerun()
    with _col_acc:
        if AUTH.is_admin():
            if st.button("ðŸ‘¥ TÃ i khoáº£n", use_container_width=True, key="btn_account"):
                st.session_state['show_account'] = not st.session_state.get('show_account', False)

    if st.session_state.get('show_account') and AUTH.is_admin():
        with st.expander("ðŸ‘¥ Quáº£n lÃ½ tÃ i khoáº£n", expanded=True):
            AUTH.show_account_panel()
            if st.button("âœ• ÄÃ³ng", key="btn_close_acc"):
                st.session_state['show_account'] = False
                st.rerun()

    # â”€â”€ VÃ™NG B: ThÃ´ng sá»‘ hiá»‡n hÃ nh â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    st.markdown(
        "<hr style='border-color:#2a2a3a;margin:10px 0'>"
        "<p style='font-size:10px;color:#555;margin:0 0 6px;"
        "text-transform:uppercase;letter-spacing:0.4px'>"
        "ðŸ“Š ThÃ´ng sá»‘ hiá»‡n hÃ nh</p>",
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
            "<div style='font-size:20px;margin-bottom:4px'>â—‹</div>"
            "<div style='font-size:11px;color:#555'>"
            "ChÆ°a cÃ³ káº¿t quáº£<br>Nháº¥n OPTIONS Ä‘á»ƒ báº¯t Ä‘áº§u</div>"
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
        _loai_dam = _kcn.get('loai_dam', 'â€”')
        _t_nhip   = _kcn.get('tong_so_nhip', 'â€”')
        _L_nhip   = _kcn.get('chieu_dai', 'â€”')
        _bc       = _sd.get('bc', 0)
        _vtk      = _sd.get('vtk', 0)
        _loai_tru = _tru.get('loai_tru', 'â€”')
        _loai_mng = _mng.get('loai_mong', 'â€”')
        _d_coc    = _mng.get('duong_kinh_coc', 'â€”')
        _H_tru    = _sd.get('H_tru_est', 'â€”')
        _cap_song = _sd.get('cap_song', 'â€”')

        _dam_colors = {"Super-T": "#4fc3f7", "Dáº§m I": "#2ecc71", "T ngÆ°á»£c": "#f39c12"}
        _dc = _dam_colors.get(_loai_dam, "#9b59b6")

        _rows_html = "".join([
            _sb_row("Dáº§m",      _loai_dam, _dc),
            _sb_row("SÆ¡ Ä‘á»“",    f"{_t_nhip}Ã—{_L_nhip}m"),
            _sb_row("L cáº§u",    f"{_L_cau:.1f}m"),
            _sb_row("Bc",       f"{_bc:.1f}m"),
            _sb_row("Vtk",      f"{_vtk} km/h"),
            _sb_row("Trá»¥",      str(_loai_tru)[:20], "#c39bd3"),
            _sb_row("H trá»¥",    f"{_H_tru:.1f}m" if isinstance(_H_tru, float) else str(_H_tru)),
            _sb_row("MÃ³ng",     str(_loai_mng)[:18], "#f0a500"),
            _sb_row("D cá»c",    f"{_d_coc}m"),
            _sb_row("Cáº¥p sÃ´ng", f"Cáº¥p {_cap_song}"),
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
            f"<span>HoÃ n thÃ nh pipeline</span>"
            f"<span style='color:#4fc3f7'>{_pct_sb}%</span></div>"
            f"<div style='background:#1e1e2e;border-radius:4px;"
            f"height:5px;overflow:hidden'>"
            f"<div style='width:{_pct_sb}%;height:100%;"
            f"background:linear-gradient(90deg,#007acc,#2ecc71)'>"
            f"</div></div></div>",
            unsafe_allow_html=True,
        )

    # â”€â”€ VÃ™NG C: Trung tÃ¢m xuáº¥t file â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    st.markdown(
        "<hr style='border-color:#2a2a3a;margin:10px 0'>"
        "<p style='font-size:10px;color:#555;margin:0 0 8px;"
        "text-transform:uppercase;letter-spacing:0.4px'>"
        "â¬‡ï¸ Xuáº¥t file</p>",
        unsafe_allow_html=True,
    )

    _export_ready = bool(_sd.get('kcn_result'))

    if not _export_ready:
        st.markdown(
            "<p style='font-size:11px;color:#444;text-align:center;"
            "padding:8px'>Cháº¡y tÃ­nh toÃ¡n Ä‘á»ƒ má»Ÿ khÃ³a xuáº¥t file</p>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<p style='font-size:10px;color:#888;margin:0 0 4px'>"
            "ðŸ“ Báº£n váº½ CAD (DXF)</p>",
            unsafe_allow_html=True,
        )
        _ecol1, _ecol2 = st.columns(2)
        with _ecol1:
            if st.button("Tráº¯c dá»c", use_container_width=True, key="sb_dxf_td"):
                try:
                    _b = EXP.export_trac_doc_dxf(_sd)
                    st.download_button(
                        "ðŸ’¾ Táº£i DXF", _b, "trac_doc.dxf",
                        mime="application/octet-stream",
                        key="sb_dl_td", use_container_width=True,
                    )
                except Exception as _ex:
                    st.error(f"Lá»—i: {_ex}")
        with _ecol2:
            if st.button("Máº·t cáº¯t", use_container_width=True, key="sb_dxf_mc"):
                try:
                    _b = EXP.export_mcn_dxf(_sd)
                    st.download_button(
                        "ðŸ’¾ Táº£i DXF", _b, "mat_cat_ngang.dxf",
                        mime="application/octet-stream",
                        key="sb_dl_mc", use_container_width=True,
                    )
                except Exception as _ex:
                    st.error(f"Lá»—i: {_ex}")

        st.markdown(
            "<p style='font-size:10px;color:#888;margin:8px 0 4px'>"
            "ðŸ—ï¸ MÃ´ hÃ¬nh BIM (IFC)</p>",
            unsafe_allow_html=True,
        )
        if st.button("Xuáº¥t IFC káº¿t cáº¥u cáº§u", use_container_width=True, key="sb_ifc_bridge"):
            try:
                _b = EXP.export_bridge_ifc(_sd)
                st.download_button(
                    "ðŸ’¾ Táº£i IFC", _b, "bridge.ifc",
                    mime="application/octet-stream",
                    key="sb_dl_ifc", use_container_width=True,
                )
            except Exception as _ex:
                st.error(f"Lá»—i: {_ex}")

        _df_geo_sb = st.session_state.get('gdf_terrain') or st.session_state.get('df_geo')
        if _df_geo_sb is not None:
            if st.button("Xuáº¥t IFC Ä‘á»‹a hÃ¬nh", use_container_width=True, key="sb_ifc_terrain"):
                with st.spinner("Äang xuáº¥t..."):
                    try:
                        _, mx, my, mz = TV.ve_dia_hinh_3d(
                            _df_geo_sb, he_so_z=1.0, che_do="Bá» máº·t má»‹n", do_min=3)
                        _ifc_path = "terrain_output.ifc"
                        _ok = TV.export_terrain_to_ifc(mx, my, mz, _ifc_path, "DiaHinh_KhaoSat")
                        if _ok:
                            with open(_ifc_path, "rb") as _fh:
                                st.download_button(
                                    "ðŸ’¾ Táº£i IFC Ä‘á»‹a hÃ¬nh", _fh, "terrain.ifc",
                                    mime="application/octet-stream",
                                    key="sb_dl_terrifc", use_container_width=True,
                                )
                    except Exception as _ex:
                        st.error(f"Lá»—i: {_ex}")

        st.markdown(
            "<p style='font-size:10px;color:#888;margin:8px 0 4px'>"
            "ðŸ“„ BÃ¡o cÃ¡o (PDF)</p>",
            unsafe_allow_html=True,
        )
        if st.button("Xuáº¥t thuyáº¿t minh PDF", use_container_width=True, key="sb_pdf"):
            st.info(
                "ðŸ’¡ TÃ­nh nÄƒng xuáº¥t PDF Ä‘ang phÃ¡t triá»ƒn. "
                "DÃ¹ng Ctrl+P Ä‘á»ƒ in tá»« trÃ¬nh duyá»‡t táº¡m thá»i."
            )

    # â”€â”€ VÃ™NG D: Chatbot AI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    st.markdown(
        "<hr style='border-color:#2a2a3a;margin:10px 0'>"
        "<p style='font-size:10px;color:#555;margin:0 0 8px;"
        "text-transform:uppercase;letter-spacing:0.4px'>"
        "ðŸ¤– Há»i AI vá» káº¿t quáº£</p>",
        unsafe_allow_html=True,
    )

    chat_container = st.container(height=220, border=True)
    with chat_container:
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Há»i tÃ´i vá» thiáº¿t káº¿...", key="sidebar_chat"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        try:
            design_info = st.session_state.chatbot_context
            system_msg = f"Báº¡n lÃ  chuyÃªn gia thiáº¿t káº¿ cáº§u UTH. Tri thá»©c: {st.session_state.bridge_library}. Dá»¯ liá»‡u: {design_info}"
            response = gemini_model.generate_content(f"{system_msg}\n\nCÃ¢u há»i: {prompt}")
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            st.rerun()
        except Exception as e:
            st.error(f"Lá»—i AI: {e}")

# =========================================================================
# VÃ™NG HIá»‚N THá»Š CHÃNH
# =========================================================================
selected_ribbon = st.session_state.get('current_tab', 'THUYáº¾T MINH')

# ── Layout: Main canvas (5 col) + Right panel (2 col) ──────────────────────────
_col_main, _col_right = st.columns([5, 2], gap="small")

with _col_right:
    _render_right_panel(st.session_state.design_data)

with _col_main:
    if selected_ribbon == "THUYáº¾T MINH":
        d = st.session_state.design_data
        kcn  = d.get('kcn_result')
        tru  = d.get('tru_result')
        mong = d.get('mong_result')
    
        # Náº¿u chÆ°a cháº¡y AI â†’ Welcome / Onboarding screen
        if kcn is None:
            st.markdown("""
    <div style='text-align:center; padding: 32px 0 16px'>
      <div style='font-size:48px'>ðŸ—ï¸</div>
      <h2 style='color:#f0f0f0; margin:8px 0 4px'>ChÃ o má»«ng Ä‘áº¿n Há»‡ thá»‘ng Thiáº¿t káº¿ Cáº§u AI</h2>
      <p style='color:#888; font-size:14px'>UTH â€” TÃ­ch há»£p AI vÃ  BIM tá»± Ä‘á»™ng hÃ³a thiáº¿t káº¿ cáº§u Ä‘Æ°á»ng bá»™</p>
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
                    "âš™ï¸", "BÆ°á»›c 1 â€” Khai bÃ¡o sá»‘ liá»‡u",
                    "Nháº­p thÃ´ng sá»‘ thá»§y vÄƒn, hÃ¬nh há»c tuyáº¿n vÃ  Ä‘iá»u kiá»‡n Ä‘á»‹a phÆ°Æ¡ng qua há»™p thoáº¡i OPTIONS",
                    "#007acc",
                ), unsafe_allow_html=True)
            with wc2:
                st.markdown(_step_card(
                    "ðŸ¤–", "BÆ°á»›c 2 â€” Cháº¡y AI tÃ­nh toÃ¡n",
                    "AI tá»± Ä‘á»™ng tÃ­nh toÃ¡n káº¿t cáº¥u nhá»‹p, má»‘ trá»¥, mÃ³ng cá»c vÃ  lá»›p phá»§ máº·t cáº§u theo TCVN",
                    "#f39c12",
                ), unsafe_allow_html=True)
            with wc3:
                st.markdown(_step_card(
                    "ðŸ“", "BÆ°á»›c 3 â€” Xem káº¿t quáº£ & xuáº¥t file",
                    "Äá»c thuyáº¿t minh, xem báº£n váº½ ká»¹ thuáº­t 2D/3D, so sÃ¡nh phÆ°Æ¡ng Ã¡n vÃ  xuáº¥t DXF/IFC",
                    "#2ecc71",
                ), unsafe_allow_html=True)
    
            st.markdown("<br>", unsafe_allow_html=True)
            _, _mid, _ = st.columns([1.5, 1, 1.5])
            with _mid:
                if st.button(
                    "âš™ï¸ Báº®T Äáº¦U â€” Khai bÃ¡o sá»‘ liá»‡u",
                    use_container_width=True,
                    type="primary",
                    key="welcome_start_btn",
                ):
                    show_options_dialog()
            st.caption("ðŸ’¡ Sau khi Ä‘iá»n Ä‘áº§y Ä‘á»§ thÃ´ng sá»‘ vÃ  nháº¥n OK, há»‡ thá»‘ng sáº½ tá»± Ä‘á»™ng cháº¡y toÃ n bá»™ pipeline AI.")
            st.stop()
    
        st.title("ðŸ“„ Thuyáº¿t minh TÃ­nh toÃ¡n Thiáº¿t káº¿ Cáº§u")
        st.caption(f"Xuáº¥t bá»Ÿi Há»‡ thá»‘ng AI UTH â€” {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}")
        st.markdown("---")
    
        # â”€â”€ I. THÃ”NG Sá» Äáº¦U VÃ€O â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        with st.expander("**I. THÃ”NG Sá» Äáº¦U VÃ€O CÃ”NG TRÃŒNH**", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Loáº¡i cÃ´ng trÃ¬nh**")
                st.write(f"Äá»‘i tÆ°á»£ng vÆ°á»£t : **{d.get('loai_doi_tuong_vuot','â€”')}**")
                st.write(f"Loáº¡i Ä‘Æ°á»ng     : {d.get('loai_duong','â€”')}")
                st.write(f"Vtk            : **{d.get('vtk',0)} km/h**")
                st.write(f"GÃ³c giao chÃ©o  : {d.get('goc_giao',90)}Â°")
                if d.get('cap_song'):
                    st.write(f"Cáº¥p sÃ´ng ÄTNÄ  : Cáº¥p {d['cap_song']}")
            with c2:
                st.markdown("**Cao Ä‘á»™ thá»§y vÄƒn (m)**")
                st.write(f"MNCN (H1%)  : {d.get('MNCN',0):.3f} m")
                st.write(f"MNTT (H5%)  : {d.get('MNTT',0):.3f} m")
                st.write(f"MNTC (H10%) : {d.get('MNTC',0):.3f} m")
                st.write(f"MNTN (H98%) : {d.get('MNTN',0):.3f} m")
                st.write(f"CÄTN (tá»« Ä‘á»‹a hÃ¬nh): {d.get('h_tn_tb',0):.3f} m")
            with c3:
                st.markdown("**Bá» rá»™ng máº·t cáº¯t**")
                st.write(f"TÄ©nh khÃ´ng B : **{d.get('B',0):.2f} m**")
                st.write(f"TÄ©nh khÃ´ng H : **{d.get('H',0):.2f} m**")
                st.write(f"Bá» rá»™ng Bc   : {d.get('bc',0):.1f} m")
                geo = d.get('geo_logic', {})
                st.write(f"Chiá»u dÃ i cáº§u: **{geo.get('L_cau',0):.1f} m**")
    
        # â”€â”€ II. Káº¾T Cáº¤U NHá»ŠP (AI) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        with st.expander("**II. Káº¾T Cáº¤U NHá»ŠP â€” Dáº§m chÃ­nh (AI v2)**", expanded=True):
            if kcn:
                kc1, kc2 = st.columns([3, 2])
                with kc1:
                    st.markdown(f"### Loáº¡i dáº§m: **{kcn['loai_dam'].upper()}**")
                    st.markdown(f"SÆ¡ Ä‘á»“ nhá»‹p: **{kcn['tong_so_nhip']} nhá»‹p Ã— {kcn['chieu_dai']} m**")
                    st.table(pd.DataFrame({
                        "ThÃ´ng sá»‘": [
                            "Chiá»u dÃ i nhá»‹p",
                            "Chiá»u cao dáº§m",
                            "Tá»‰ lá»‡ L/H",
                            "Sá»‘ lÆ°á»£ng dáº§m / MCN",
                            "Khoáº£ng cÃ¡ch tim dáº§m",
                            "Pháº§n háº«ng (overhang)",
                            "Tá»•ng sá»‘ nhá»‹p",
                        ],
                        "GiÃ¡ trá»‹": [
                            f"{kcn['chieu_dai']} m",
                            f"{kcn['chieu_cao_dam']} m",
                            f"{kcn['ti_le_L_H']} (tá»‘i Æ°u 17â€“22)",
                            f"{kcn['so_luong_dam']} dáº§m",
                            f"{kcn['khoang_cach_dam']} m",
                            f"{kcn['overhang']} m",
                            f"{kcn['tong_so_nhip']} nhá»‹p",
                        ],
                    }))
                with kc2:
                    conf = kcn.get('do_tin_cay', 0)
                    color = "#27ae60" if conf >= 70 else ("#f39c12" if conf >= 50 else "#e74c3c")
                    st.markdown(f"""
    <div style='background:{color};padding:16px;border-radius:8px;text-align:center'>
    <span style='color:white;font-size:36px;font-weight:bold'>{conf:.0f}%</span><br>
    <span style='color:white'>Äá»™ tin cáº­y AI</span>
    </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"PhÆ°Æ¡ng phÃ¡p: {kcn.get('phuong_phap','AUTO')}")
                    st.info(kcn.get('ghi_chu', ''))
            else:
                st.warning("ChÆ°a cÃ³ káº¿t quáº£ AI káº¿t cáº¥u nhá»‹p.")
    
        # â”€â”€ III. TRá»¤ Cáº¦U (AI) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        with st.expander("**III. TRá»¤ Cáº¦U â€” PhÃ¢n loáº¡i & kÃ­ch thÆ°á»›c (AI v2)**", expanded=True):
            if tru:
                tc1, tc2 = st.columns([3, 2])
                with tc1:
                    st.markdown(f"### Loáº¡i trá»¥: **{tru['loai_tru']}**")
                    H_tru = d.get('H_tru_est', 0)
                    cao_dd = d.get('cao_day_dam', 0)
                    cao_mc = d.get('cao_mat_cau', 0)
                    st.table(pd.DataFrame({
                        "ThÃ´ng sá»‘": [
                            "Chiá»u cao trá»¥ (Æ°á»›c tÃ­nh)",
                            "Cao Ä‘á»™ Ä‘Ã¡y dáº§m (Æ°á»›c tÃ­nh)",
                            "Cao Ä‘á»™ máº·t cáº§u (Æ°á»›c tÃ­nh)",
                            "Sá»‘ trá»¥ giá»¯a",
                        ],
                        "GiÃ¡ trá»‹": [
                            f"{H_tru:.2f} m",
                            f"{cao_dd:.3f} m",
                            f"{cao_mc:.3f} m",
                            f"{max(0, kcn['tong_so_nhip'] - 1) if kcn else 'â€”'} trá»¥",
                        ],
                    }))
                    if tru.get('xep_hang'):
                        st.markdown("**Top phÆ°Æ¡ng Ã¡n dá»± bÃ¡o:**")
                        for r in tru['xep_hang']:
                            bar = "â–ˆ" * int(r['xac_suat'] / 5)
                            st.text(f"  {r['loai']:25s} {bar}  {r['xac_suat']:.0f}%")
                with tc2:
                    conf_tru = tru.get('do_tin_cay', 0)
                    color_tru = "#27ae60" if conf_tru >= 70 else ("#f39c12" if conf_tru >= 50 else "#e74c3c")
                    if conf_tru > 0:
                        st.markdown(f"""
    <div style='background:{color_tru};padding:16px;border-radius:8px;text-align:center'>
    <span style='color:white;font-size:36px;font-weight:bold'>{conf_tru:.0f}%</span><br>
    <span style='color:white'>Äá»™ tin cáº­y AI</span>
    </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
    <div style='background:#95a5a6;padding:16px;border-radius:8px;text-align:center'>
    <span style='color:white;font-size:18px'>Quy táº¯c kinh nghiá»‡m</span>
    </div>
                        """, unsafe_allow_html=True)
                    st.caption(tru.get('ghi_chu', ''))
            else:
                st.warning("ChÆ°a cÃ³ káº¿t quáº£ AI trá»¥ cáº§u.")
    
        # â”€â”€ IV. MÃ“NG Cáº¦U â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        with st.expander("**IV. MÃ“NG Cáº¦U â€” Gá»£i Ã½ loáº¡i cá»c (TCVN 10304)**", expanded=True):
            if mong:
                mc1, mc2 = st.columns(2)
                with mc1:
                    st.markdown(f"### Loáº¡i mÃ³ng: **{mong['loai_mong']}**")
                    st.table(pd.DataFrame({
                        "ThÃ´ng sá»‘": [
                            "ÄÆ°á»ng kÃ­nh cá»c",
                            "Chiá»u dÃ i cá»c",
                            "Sá»‘ cá»c / bá»‡",
                            "KÃ­ch thÆ°á»›c bá»‡ cá»c",
                            "Thi cÃ´ng",
                        ],
                        "GiÃ¡ trá»‹": [
                            mong["D_coc_chon_txt"],
                            f"{mong['L_coc_tu']} â€“ {mong['L_coc_den']} m",
                            f"{mong['So_coc_tu']} â€“ {mong['So_coc_den']} cá»c",
                            mong["kich_thuoc_be_goi_y"],
                            mong["phuong_phap_thi_cong"],
                        ],
                    }))
                with mc2:
                    st.markdown("**Khuyáº¿n nghá»‹ ká»¹ thuáº­t:**")
                    for kn in mong.get("khuyen_nghi", []):
                        st.warning(kn)
                    st.caption(mong.get("ghi_chu_mong", ""))
            else:
                st.warning("ChÆ°a cÃ³ káº¿t quáº£ gá»£i Ã½ mÃ³ng.")
    
        # â”€â”€ V. Báº¢N Máº¶T Cáº¦U & Lá»šP PHá»¦ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        lop_phu = d.get('lop_phu_result')
        with st.expander("**V. Báº¢N Máº¶T Cáº¦U & Lá»šP PHá»¦ Máº¶T Cáº¦U**", expanded=False):
            t_ban_mm_val = d.get('t_ban_mm', 200)
            st.markdown(f"**Chiá»u dÃ y báº£n máº·t cáº§u BTCT:** `{t_ban_mm_val} mm` "
                        f"{'âœ…' if t_ban_mm_val >= 175 else 'âš ï¸ DÆ°á»›i tá»‘i thiá»ƒu 175mm'}")
            st.caption("Tá»‘i thiá»ƒu 175 mm theo TCVN 11823-2017 Äiá»u 9.7.1.1")
            if lop_phu:
                st.markdown(f"**PhÆ°Æ¡ng Ã¡n lá»›p phá»§:** {lop_phu['phuong_an']}")
                st.caption(f"TiÃªu chuáº©n: {lop_phu['tieu_chuan']}")
                lp_data = []
                for i, lop in enumerate(lop_phu['cac_lop'], 1):
                    if "lieu_luong" in lop:
                        day_txt = lop["lieu_luong"]
                    elif lop["day_tt"] > 0:
                        day_txt = f"{lop['day_min']}â€“{lop['day_tt']} mm"
                    else:
                        day_txt = "â€”"
                    lp_data.append({"STT": i, "Lá»›p cáº¥u táº¡o": lop["ten"],
                                     "Chiá»u dÃ y": day_txt, "Váº­t liá»‡u": lop["vat_lieu"]})
                st.table(pd.DataFrame(lp_data))
                st.info(f"Tá»•ng chiá»u dÃ y lá»›p phá»§: **{lop_phu['tong_day_min']}â€“{lop_phu['tong_day_tt']} mm**")
                for kn in lop_phu.get('khuyen_nghi', []):
                    st.warning(kn)
                st.caption(lop_phu.get('ghi_chu', ''))
    
        # â”€â”€ VI. Máº¶T Cáº®T NGANG â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        with st.expander("**VI. Máº¶T Cáº®T NGANG Cáº¦U**", expanded=False):
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
                    # â”€â”€ So sÃ¡nh Báº£ng 1 TCVN 5729:2012 â”€â”€
                    st.caption(f"ðŸ“ {res_mcn['tieu_chuan']} â€” Vtk={tra_tt.get('vtk','')}km/h â€” {tra_tt.get('mo_ta_dpc','')}")
                    df_so_sanh = pd.DataFrame({
                        "Yáº¿u tá»‘": [
                            "Sá»‘ lÃ n/chiá»u", "Chiá»u rá»™ng 1 lÃ n (m)", "Máº·t Ä‘Æ°á»ng/chiá»u (m)",
                            "Lá» gia cá»‘/DAT (m)", "DAT dáº£i giá»¯a (m)", "DPC lÃµi (m)", "Ná»n Ä‘Æ°á»ng (m)"
                        ],
                        "TiÃªu chuáº©n (TCVN 5729:2012)": [
                            tra_tt["n_lan_moi_chieu_min"], tra_tt["w_lan_min"],
                            tra_tt["w_mat_duong_min"], tra_tt["w_le_dat_min"],
                            tra_tt["w_dat_an_toan_dg_min"], tra_tt["w_dpc_core_min"],
                            tra_tt["w_nen_min"],
                        ],
                        "Thiáº¿t káº¿ (ngÆ°á»i dÃ¹ng nháº­p)": [
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
                        st.error("âš ï¸ Má»™t sá»‘ giÃ¡ trá»‹ thiáº¿t káº¿ NHá»Ž HÆ N má»©c tiÃªu chuáº©n TCVN 5729:2012!")
                    else:
                        st.success("âœ… GiÃ¡ trá»‹ thiáº¿t káº¿ thá»a mÃ£n tiÃªu chuáº©n TCVN 5729:2012.")
                    st.caption(
                        f"Äá»™ dá»‘c ngang (cá»‘ Ä‘á»‹nh TCVN 5729:2012): "
                        f"Máº·t Ä‘Æ°á»ng & DAT = **{res_mcn['i_doc_ngang']:g}%** | "
                        f"Lá» trá»“ng cá» = **{res_mcn['i_le_trong_co']:g}%**"
                    )
    
                elif is_dothi and tra_tt and tra_tt.get("status") == "success":
                    # â”€â”€ So sÃ¡nh Báº£ng 10/13/14/15 TCVN 13592:2022 â”€â”€
                    _dkx = tra_tt.get("dieu_kien_xd", "II")
                    st.caption(
                        f"ðŸ“ {res_mcn['tieu_chuan']} â€” {tra_tt.get('mo_ta','')} | "
                        f"VTK {tra_tt.get('vtk','')} km/h | Äiá»u kiá»‡n xÃ¢y dá»±ng: {_dkx}"
                    )
                    # Báº£ng 10/13
                    _dat_at_cap = (tra_tt.get('w_dat_at_loaiI') if _dkx == "I"
                                   else tra_tt.get('w_dat_at_loaiII_III'))
                    df_10_13 = pd.DataFrame({
                        "Yáº¿u tá»‘": [
                            "Sá»‘ lÃ n xe (tá»‘i thiá»ƒu)", "Chiá»u rá»™ng 1 lÃ n (m)",
                            "Lá» Ä‘Æ°á»ng tá»‘i thiá»ƒu (m)", "Lá» Ä‘Æ°á»ng tá»‘i Ä‘a (m)",
                        ],
                        f"TiÃªu chuáº©n Báº£ng 10/13": [
                            f"{tra_tt['so_lan_toi_thieu']} (mong {tra_tt['so_lan_mong_muon']})",
                            tra_tt["w_lan_min"], tra_tt["w_le_min"], tra_tt["w_le_max"],
                        ],
                        "Thiáº¿t káº¿ (nháº­p)": [
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
                        st.error("âš ï¸ Má»™t sá»‘ giÃ¡ trá»‹ NHá»Ž HÆ N má»©c tá»‘i thiá»ƒu TCVN 13592:2022!")
                    else:
                        st.success("âœ… Pháº§n xe cháº¡y vÃ  lá» thá»a mÃ£n TCVN 13592:2022.")
                    if _dat_at_cap:
                        st.caption(
                            f"Dáº£i an toÃ n (Báº£ng 13, Ä‘k {_dkx}): **{_dat_at_cap:.2f}m** "
                            f"(báº¯t buá»™c khi VTK â‰¥ 50 km/h â€” Äiá»u 9.4.3)"
                        )
                    # Báº£ng 14 â€” DPC
                    _dpc_min = tra_tt.get("dpc_min")
                    _dpc_mm  = tra_tt.get("dpc_mong_muon")
                    _dpc_note= tra_tt.get("dpc_note")
                    if tra_tt.get("co_dpc") and _dpc_min is not None:
                        _w_dpc_tk = res_mcn.get("w_dpc", 0)
                        _ok_dpc   = _w_dpc_tk >= _dpc_min
                        st.caption(
                            f"Dáº£i phÃ¢n cÃ¡ch (Báº£ng 14, Ä‘k {_dkx}): "
                            f"tá»‘i thiá»ƒu **{_dpc_min:.2f}m** (mong muá»‘n {_dpc_mm:.2f}m) | "
                            f"Thiáº¿t káº¿: **{_w_dpc_tk:.2f}m** â€” "
                            + ("âœ… Äáº¡t" if _ok_dpc else "âš ï¸ ChÆ°a Ä‘áº¡t tá»‘i thiá»ƒu")
                        )
                    elif _dpc_note:
                        st.caption(f"Dáº£i phÃ¢n cÃ¡ch (Báº£ng 14): {_dpc_note}")
                    # Báº£ng 15 â€” HÃ¨ Ä‘Æ°á»ng
                    _he_min = tra_tt.get("he_min")
                    _w_he_tk = res_mcn.get("w_he", res_mcn.get("w_lc", 0))
                    if _he_min is not None:
                        _ok_he = _w_he_tk >= _he_min
                        st.caption(
                            f"HÃ¨ Ä‘Æ°á»ng (Báº£ng 15, Ä‘k {_dkx}): "
                            f"tá»‘i thiá»ƒu **{_he_min:.1f}m** | "
                            f"Thiáº¿t káº¿: **{_w_he_tk:.1f}m** â€” "
                            + ("âœ… Äáº¡t" if _ok_he else "âš ï¸ ChÆ°a Ä‘áº¡t tá»‘i thiá»ƒu")
                        )
                    # Báº£ng 12 â€” Ä‘á»™ dá»‘c ngang
                    _b12 = res_mcn.get("doc_ngang_b9", {})
                    if _b12:
                        _i    = res_mcn.get("i_doc_ngang", _b12.get("i_goi_y", 2.0))
                        _ok_i = res_mcn.get("i_doc_ngang_trong_pham_vi", True)
                        st.caption(
                            f"Äá»™ dá»‘c ngang â€” {_b12.get('mo_ta','')} | "
                            f"Pháº¡m vi Báº£ng 12: **{_b12['i_min']:g}%â€“{_b12['i_max']:g}%** | "
                            f"Thiáº¿t káº¿: **{_i:.1f}%** â€” "
                            + ("âœ… Trong pháº¡m vi" if _ok_i else "âš ï¸ NgoÃ i pháº¡m vi TCVN")
                        )
    
                elif not is_caotoc and not is_dothi and tra_tt and tra_tt.get("status") == "success":
                    # â”€â”€ So sÃ¡nh Báº£ng 6/7 TCVN 4054:2005 â”€â”€
                    st.caption(f"ðŸ“ {res_mcn['tieu_chuan']} â€” Cáº¥p {tra_tt['cap_duong']}")
                    df_so_sanh = pd.DataFrame({
                        "Yáº¿u tá»‘": ["Sá»‘ lÃ n xe", "Chiá»u rá»™ng 1 lÃ n (m)", "Dáº£i phÃ¢n cÃ¡ch (m)",
                                   "Lá» Ä‘Æ°á»ng (m)", "Lá» gia cá»‘ (m)"],
                        "Tá»‘i thiá»ƒu (TCVN 4054:2005)": [
                            tra_tt["so_lan_min"], tra_tt["w_lan_min"], tra_tt["w_dpc_min"],
                            tra_tt["w_le_min"], tra_tt["w_le_gc_min"] or "â€”",
                        ],
                        "Thiáº¿t káº¿ (ngÆ°á»i dÃ¹ng nháº­p)": [
                            res_mcn["n_lan"], res_mcn["w_lan"], res_mcn["w_dpc"],
                            res_mcn["w_le"], res_mcn["w_le_gc"] or "â€”",
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
                        st.error("âš ï¸ Má»™t sá»‘ giÃ¡ trá»‹ thiáº¿t káº¿ NHá»Ž HÆ N má»©c tá»‘i thiá»ƒu theo tiÃªu chuáº©n!")
                    else:
                        st.success("âœ… GiÃ¡ trá»‹ thiáº¿t káº¿ thá»a mÃ£n chiá»u rá»™ng tá»‘i thiá»ƒu theo tiÃªu chuáº©n.")
    
                    # â”€â”€ Báº£ng 8 â”€â”€
                    _dpc_b8 = res_mcn.get("dpc_b8", {})
                    if res_mcn.get("w_dpc", 0) > 0 and _dpc_b8:
                        _w_dpc_min_b8 = res_mcn.get("w_dpc_min_b8", 0)
                        _ok_dpc = res_mcn["w_dpc"] >= _w_dpc_min_b8
                        st.caption(
                            f"Dáº£i phÃ¢n cÃ¡ch â€” {_dpc_b8.get('mo_ta','')} | "
                            f"Tá»‘i thiá»ƒu Báº£ng 8: **{_w_dpc_min_b8:g}m** | "
                            f"Thiáº¿t káº¿: **{res_mcn['w_dpc']:.2f}m** â€” "
                            + ("âœ… Äáº¡t" if _ok_dpc else "âš ï¸ ChÆ°a Ä‘áº¡t")
                        )
                    # â”€â”€ Báº£ng 9 â”€â”€
                    _b9 = res_mcn.get("doc_ngang_b9", {})
                    if _b9:
                        _i = res_mcn.get("i_doc_ngang", _b9.get("i_goi_y", 2.0))
                        _ok_i = res_mcn.get("i_doc_ngang_trong_pham_vi", True)
                        st.caption(
                            f"Äá»™ dá»‘c ngang â€” {_b9.get('mo_ta','')} | "
                            f"Pháº¡m vi Báº£ng 9: **{_b9['i_min']:g}% â€“ {_b9['i_max']:g}%** | "
                            f"Thiáº¿t káº¿: **{_i:.1f}%** â€” "
                            + ("âœ… Trong pháº¡m vi" if _ok_i else "âš ï¸ NgoÃ i pháº¡m vi TCVN")
                        )
    
                elif tra_tt and tra_tt.get("status") == "error":
                    st.warning(f"âš ï¸ {tra_tt.get('message')}")
    
                st.code(res_mcn.get('mo_phong', 'ChÆ°a cÃ³ sÆ¡ Ä‘á»“.'), language="text")
    
                if is_caotoc:
                    st.markdown("#### MCN Ä‘Æ°á»ng Ä‘áº§u cáº§u")
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
                    st.markdown("#### MCN táº¡i cáº§u â€” Äiá»u 6.12 TCVN 5729:2012")
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
                        "Theo Äiá»u 6.12.1 TCVN 5729:2012: chiá»u rá»™ng cáº§u báº±ng chiá»u rá»™ng ná»n Ä‘Æ°á»ng (Báº£ng 1). "
                        "Lá» trá»“ng cá» Ä‘Æ°á»£c thay báº±ng lan can cáº§u + dáº£i phá»¥ khai thÃ¡c cÃ¹ng chiá»u rá»™ng. "
                        "Theo Äiá»u 6.12.4: hai chiá»u xe cháº¡y thÆ°á»ng Ä‘Æ°á»£c bá»‘ trÃ­ thÃ nh 2 cáº§u tÃ¡ch biá»‡t."
                    )
            except Exception as ex:
                import traceback
                st.error(f"Lá»—i máº·t cáº¯t ngang: {ex}")
                with st.expander("Chi tiáº¿t lá»—i"):
                    st.code(traceback.format_exc())
    
        # â”€â”€ VII. SO SÃNH 3 PHÆ¯Æ NG ÃN LOáº I Dáº¦M â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _alts = st.session_state.get("alternatives")
        with st.expander("**VII. SO SÃNH 3 PHÆ¯Æ NG ÃN LOáº I Dáº¦M**", expanded=bool(_alts)):
            if not _alts:
                st.info("Cháº¡y pipeline Ä‘á»ƒ tá»± Ä‘á»™ng sinh 3 phÆ°Æ¡ng Ã¡n so sÃ¡nh.")
            else:
                _pa_colors = [a["color"] for a in _alts]
                _pa_labels = [a["label"] for a in _alts]
    
                # Tháº» tÃ³m táº¯t nhanh má»—i PA
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
                            f"<tr><td style='color:#888'>SÆ¡ Ä‘á»“ nhá»‹p</td>"
                            f"<td style='text-align:right;font-weight:600'>{_k['tong_so_nhip']} Ã— {_k['chieu_dai']:.1f} m</td></tr>"
                            f"<tr><td style='color:#888'>Chiá»u cao H</td>"
                            f"<td style='text-align:right;font-weight:600'>{_k['chieu_cao_dam']:.2f} m</td></tr>"
                            f"<tr><td style='color:#888'>L/H</td>"
                            f"<td style='text-align:right;font-weight:600'>{_k.get('ti_le_L_H',0) or 0:.1f}</td></tr>"
                            f"<tr><td style='color:#888'>Loáº¡i trá»¥</td>"
                            f"<td style='text-align:right;font-weight:600'>{_t['loai_tru']}</td></tr>"
                            f"<tr><td style='color:#888'>Sá»‘ trá»¥</td>"
                            f"<td style='text-align:right;font-weight:600'>{_alt['n_tru']} trá»¥</td></tr>"
                            f"<tr><td style='color:#888'>Loáº¡i mÃ³ng</td>"
                            f"<td style='text-align:right;font-weight:600'>{_m['loai_mong']}</td></tr>"
                            f"<tr><td style='color:#888'>ÄÆ°á»ng kÃ­nh cá»c</td>"
                            f"<td style='text-align:right;font-weight:600'>{_m['D_coc_chon_txt']}</td></tr>"
                            f"<tr style='border-top:1px solid #444'><td style='color:#888;padding-top:6px'>Chi phÃ­ tÆ°Æ¡ng Ä‘á»‘i</td>"
                            f"<td style='text-align:right;font-weight:700;color:{_alt['color']};padding-top:6px'>{_alt['cost_pct']:.0f}%</td></tr>"
                            f"<tr><td style='color:#888'>Thá»i gian TC</td>"
                            f"<td style='text-align:right;font-weight:600'>{_alt['thoi_gian']:.1f} thÃ¡ng</td></tr>"
                            f"</table></div>",
                            unsafe_allow_html=True,
                        )
    
                st.markdown("")
                # Bieu do nhanh chi phi + so tru
                _fig2 = go.Figure()
                _fig2.add_trace(go.Bar(
                    name="Chi phÃ­ (%)",
                    x=_pa_labels,
                    y=[a["cost_pct"] for a in _alts],
                    marker_color=_pa_colors,
                    text=[f"{a['cost_pct']:.0f}%" for a in _alts],
                    textposition="outside",
                    yaxis="y",
                ))
                _fig2.add_trace(go.Scatter(
                    name="Sá»‘ trá»¥ giá»¯a",
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
                    yaxis=dict(title="Chi phÃ­ (%, Dáº§m I=100%)", side="left"),
                    yaxis2=dict(title="Sá»‘ trá»¥ giá»¯a", side="right", overlaying="y",
                                rangemode="tozero"),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    height=280, margin=dict(t=10, b=10, l=10, r=10),
                    legend=dict(orientation="h", y=-0.25),
                    barmode="group",
                )
                st.plotly_chart(_fig2, use_container_width=True, key="pa_quick_chart")
                st.caption("Xem Ä‘áº§y Ä‘á»§ biá»ƒu Ä‘á»“ radar & báº£ng chi tiáº¿t á»Ÿ tab **SO SÃNH PHÆ¯Æ NG ÃN**.")
    
        st.markdown("---")
        st.caption("Káº¿t quáº£ mang tÃ­nh tham kháº£o sÆ¡ bá»™. Cáº§n kiá»ƒm tra vÃ  Ä‘iá»u chá»‰nh theo tiÃªu chuáº©n TCVN hiá»‡n hÃ nh.")
    
    elif selected_ribbon == "Báº¢N Váº¼ Ká»¸ THUáº¬T":
        _s1 = tab_states['tab1']
        if _s1 == 'done':
            st.markdown(
                DS.banner("success", "Dá»¯ liá»‡u Ä‘áº§y Ä‘á»§ â€” báº£n váº½ hiá»ƒn thá»‹ káº¿t quáº£ tÃ­nh toÃ¡n má»›i nháº¥t."),
                unsafe_allow_html=True,
            )
        elif _s1 == 'partial':
            st.markdown(
                DS.banner("warning",
                          "Káº¿t cáº¥u nhá»‹p Ä‘Ã£ cÃ³ nhÆ°ng chÆ°a tÃ­nh xong trá»¥",
                          "Má»™t sá»‘ báº£n váº½ cÃ³ thá»ƒ chÆ°a Ä‘áº§y Ä‘á»§"),
                unsafe_allow_html=True,
            )
        elif _s1 == 'locked':
            _es = DS.empty_state(
                icon      = "ðŸ“",
                title     = "Báº£n váº½ chÆ°a sáºµn sÃ ng",
                desc      = ("Pipeline AI cáº§n cháº¡y thÃ nh cÃ´ng Ä‘á»ƒ sinh "
                             "báº£n váº½ tráº¯c dá»c, máº·t cáº¯t ngang vÃ  má»‘ trá»¥."),
                cta_label = "âš™ï¸ Má»Ÿ OPTIONS",
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
    
        # â”€â”€ Khai bÃ¡o Ä‘á»‹a hÃ¬nh (luÃ´n hiá»ƒn thá»‹) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        with st.expander(
            "ðŸ“¥ Khai bÃ¡o dá»¯ liá»‡u Ä‘á»‹a hÃ¬nh (file .NTD + báº£ng tá»a Ä‘á»™ VN-2000)",
            expanded=(not has_ai or "df_geology" not in st.session_state),
        ):
            st.caption("Náº¡p file kháº£o sÃ¡t Ä‘á»ƒ báº£n váº½ káº¿t cáº¥u tÃ­ch há»£p Ä‘á»‹a hÃ¬nh thá»±c Ä‘o.")
            _c1, _c2 = st.columns(2)
            with _c1:
                file_khao_sat = st.file_uploader(
                    "ðŸ“‚ File .NTD (tráº¯c dá»c â€“ tráº¯c ngang)", type=["ntd"], key="ntd_up"
                )
            with _c2:
                file_toa_do = st.file_uploader(
                    "ðŸ“ Tá»a Ä‘á»™ tim tuyáº¿n (.CSV / .XLSX)", type=["csv","xlsx"], key="coord_up"
                )
            if file_khao_sat and file_toa_do:
                with st.spinner("âš¡ Äang Ä‘á»“ng bá»™ tá»a Ä‘á»™ VN-2000..."):
                    df_ntd   = TV.parse_ntd_file(file_khao_sat)
                    df_coord = TV.parse_coordinate_file(file_toa_do)
                if df_coord is not None and not df_ntd.empty:
                    _dg = TV.convert_to_vn2000(df_ntd, df_coord)
                    if not _dg.empty:
                        st.session_state.df_geology = _dg
                        _tl = (_dg[_dg["Offset"] == 0][["LÃ½ trÃ¬nh","Z"]]
                               .drop_duplicates("LÃ½ trÃ¬nh").sort_values("LÃ½ trÃ¬nh"))
                        st.session_state.df_tim_line = _tl
                        st.success(f"âœ… ÄÃ£ Ä‘á»“ng bá»™ {len(_dg)} Ä‘iá»ƒm Ä‘á»‹a hÃ¬nh theo VN-2000!")
    
        st.markdown("---")
    
        if not has_ai:
            _kcn_err  = d.get('_kcn_error')
            _ran      = 'H_tru_est' in d
            if _ran:
                st.warning(
                    "âš ï¸ Pipeline Ä‘Ã£ cháº¡y nhÆ°ng **AI Káº¿t cáº¥u nhá»‹p khÃ´ng cho káº¿t quáº£**. "
                    + (f"\n\nChi tiáº¿t lá»—i: `{_kcn_err}`" if _kcn_err else "")
                    + "\n\nCÃ³ thá»ƒ thiáº¿u file `Data/Bridge_Train_Dataset_v3.xlsx` hoáº·c lá»—i tÃ­nh toÃ¡n. "
                    "Má»Ÿ **âš™ï¸ OPTIONS** Ä‘á»ƒ cháº¡y láº¡i."
                )
            else:
                st.info(
                    "âš™ï¸ Nháº¥n nÃºt **âš™ï¸ OPTIONS - KHAI BÃO Sá» LIá»†U** á»Ÿ gÃ³c trÃªn trÃ¡i, "
                    "Ä‘iá»n Ä‘áº§y Ä‘á»§ thÃ´ng sá»‘, sau Ä‘Ã³ nháº¥n **ðŸ’¾ OK - Ãp dá»¥ng cáº¥u hÃ¬nh vÃ  Cháº¡y dá»± bÃ¡o AI** "
                    "bÃªn trong há»™p thoáº¡i Ä‘á»ƒ há»‡ thá»‘ng cháº¡y AI pipeline vÃ  hiá»ƒn thá»‹ káº¿t quáº£ táº¡i Ä‘Ã¢y."
                )
        else:
            _df_geo  = st.session_state.get("df_geology", None)
            _df_tim  = st.session_state.get("df_tim_line", None)
            has_terr = _df_geo is not None and not _df_geo.empty
    
            # ThÃ´ng tin brief
            _geo_d = d.get("geo_logic", {})
            st.caption(
                f"ðŸ“Š L_cáº§u=**{_geo_d.get('L_cau',0):.1f}m** | "
                f"{kcn.get('tong_so_nhip','?')}Ã—{kcn.get('chieu_dai','?')}m "
                f"**{kcn.get('loai_dam','').upper()}** | "
                f"B_tk={d.get('B',0):.1f}m Ã— H_tk={d.get('H',0):.2f}m | "
                + ("ðŸ—ºï¸ Äá»‹a hÃ¬nh: Ä‘Ã£ náº¡p" if has_terr else "ðŸ—ºï¸ Äá»‹a hÃ¬nh: chÆ°a náº¡p (táº£i á»Ÿ trÃªn)")
            )
    
            # â”€â”€ Sub-tabs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            (tab_3d, tab_btc, tab_mcn_vt,
             tab_spt, tab_tng, tab_dami,
             tab_dia_chat, tab_export) = st.tabs([
                "ðŸŒ 3D Tá»•ng há»£p"  + (" ðŸ—ºï¸" if has_terr else " (sÆ¡ Ä‘á»“)"),
                "ðŸ“‹ Bá»‘ trÃ­ chung",
                "âœ‚ï¸ MCN Má»‘/Trá»¥",
                "ðŸ”© Chi tiáº¿t SPT",
                "ðŸ”© T ngÆ°á»£c",
                "ðŸ”© Dáº§m I",
                "ðŸª¨ Äá»‹a cháº¥t",
                "ðŸ“¤ Xuáº¥t báº£n váº½",
            ])
    
            # â”€â”€ TAB 1: 3D Tá»•ng há»£p â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            with tab_3d:
                if has_terr:
                    # â”€â”€ Kiá»ƒm tra alignment lÃ½ trÃ¬nh cáº§u vs Ä‘á»‹a hÃ¬nh â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                    _geo_d2 = d.get("geo_logic", {})
                    _xmo_t  = float(_geo_d2.get("x_mo_trai", -60))
                    _xmo_p  = float(_geo_d2.get("x_mo_phai",  60))
                    _xtim   = float(_geo_d2.get("x_tim_clearance", (_xmo_t+_xmo_p)/2))
                    _lt_col2= next((c for c in _df_geo.columns if 'Ã½ trÃ¬nh' in c or c.lower()=='ly_trinh'), 'LÃ½ trÃ¬nh')
                    _lt_min2= float(_df_geo[_lt_col2].min()) if _lt_col2 in _df_geo.columns else 0
                    _lt_max2= float(_df_geo[_lt_col2].max()) if _lt_col2 in _df_geo.columns else 999
                    _overlap = max(_lt_min2, _xmo_t) < min(_lt_max2, _xmo_p)
    
                    _c1, _c2, _c3 = st.columns(3)
                    _c1.metric("ðŸ—ºï¸ LÃ½ trÃ¬nh Ä‘á»‹a hÃ¬nh", f"{_lt_min2:.1f} â†’ {_lt_max2:.1f} m")
                    _c2.metric("ðŸŒ‰ LÃ½ trÃ¬nh cáº§u", f"{_xmo_t:.1f} â†’ {_xmo_p:.1f} m")
                    _c3.metric("â­• Tim tÄ©nh khÃ´ng", f"{_xtim:.1f} m")
    
                    if not _overlap:
                        _suggest_tim = (_lt_min2 + _lt_max2) / 2
                        st.error(
                            f"âŒ **Cáº§u khÃ´ng náº±m trong pháº¡m vi Ä‘á»‹a hÃ¬nh!** "
                            f"Äá»‹a hÃ¬nh: {_lt_min2:.1f}â†’{_lt_max2:.1f}m | Cáº§u: {_xmo_t:.1f}â†’{_xmo_p:.1f}m. "
                            f"ðŸ‘‰ Má»Ÿ **OPTIONS** vÃ  Ä‘áº·t **LÃ½ trÃ¬nh tim tÄ©nh khÃ´ng â‰ˆ {_suggest_tim:.1f}m** "
                            f"Ä‘á»ƒ cáº§u khá»›p vá»›i Ä‘á»‹a hÃ¬nh."
                        )
                    else:
                        _pct_ok = 100*(min(_lt_max2,_xmo_p)-max(_lt_min2,_xmo_t))/max(1,_xmo_p-_xmo_t)
                        st.success(f"âœ… Cáº§u khá»›p Ä‘á»‹a hÃ¬nh ({_pct_ok:.0f}% chiá»u dÃ i cáº§u náº±m trong pháº¡m vi Ä‘á»‹a hÃ¬nh)")
    
                    col_o1, col_o2, col_o3, col_o4 = st.columns(4)
                    with col_o1:
                        che_do_view = st.selectbox("ðŸŽ¨ Äá»‹a hÃ¬nh:",
                            ["Bá» máº·t má»‹n","ÄÆ°á»ng Ä‘á»“ng má»©c","LÆ°á»›i tam giÃ¡c"], key="cd3d")
                    with col_o2:
                        he_so_z = st.slider("ðŸ“ PhÃ³ng Ä‘áº¡i Z:", 0.05, 3.00, 0.50, 0.05, key="hsz3d")
                    with col_o3:
                        do_min_view = st.select_slider("âœ¨ Má»‹n hoÃ¡:",
                            options=[1,3,5,7], value=3, key="dm3d")
                    with col_o4:
                        render_mode_3d = st.selectbox(
                            "ðŸ–¥ï¸ Cháº¿ Ä‘á»™ hiá»ƒn thá»‹:",
                            ["Shaded", "Realistic", "X-Ray", "Wireframe"],
                            key="rm3d",
                            help="Shaded: máº·c Ä‘á»‹nh â€¢ Realistic: Ä‘á»• bÃ³ng cao â€¢ X-Ray: xuyÃªn tháº¥u â€¢ Wireframe: khung lÆ°á»›i"
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
                                f"Äá»‹a hÃ¬nh: {_n_before} trace | Káº¿t cáº¥u cáº§u: +{_n_after - _n_before} trace. "
                                "KÃ©o chuá»™t xoay â€¢ Scroll zoom â€¢ Shift+drag pan."
                            )
                            if _err_overlay:
                                st.error(f"Lá»—i overlay káº¿t cáº¥u: {_err_overlay}")
                            elif _n_after == _n_before:
                                st.warning("âš ï¸ KhÃ´ng thÃªm Ä‘Æ°á»£c trace káº¿t cáº¥u â€” kiá»ƒm tra cá»™t df_geology bÃªn dÆ°á»›i")
                                with st.expander("Debug df_geology"):
                                    st.write("Columns:", list(_df_geo.columns))
                                    st.write("Offset values:", sorted(_df_geo['Offset'].unique()[:10].tolist()) if 'Offset' in _df_geo.columns else "N/A")
                                    st.write("x_mo_trai:", d.get('geo_logic',{}).get('x_mo_trai'))
                                    st.write("LÃ½ trÃ¬nh range:", float(_df_geo['LÃ½ trÃ¬nh'].min()), "â†’", float(_df_geo['LÃ½ trÃ¬nh'].max()) if 'LÃ½ trÃ¬nh' in _df_geo.columns else "N/A")
                        else:
                            st.error("KhÃ´ng táº¡o Ä‘Æ°á»£c mÃ´ hÃ¬nh Ä‘á»‹a hÃ¬nh.")
                    except Exception as _e:
                        st.error(f"Lá»—i 3D tá»•ng há»£p: {_e}")
                else:
                    st.info("ðŸ“Œ Náº¡p file Ä‘á»‹a hÃ¬nh á»Ÿ trÃªn Ä‘á»ƒ xem káº¿t cáº¥u tÃ­ch há»£p Ä‘á»‹a hÃ¬nh thá»±c Ä‘o. "
                            "Hiá»‡n Ä‘ang hiá»ƒn thá»‹ mÃ´ hÃ¬nh sÆ¡ Ä‘á»“ cáº§u.")
                    _rm_no_terr = st.selectbox(
                        "ðŸ–¥ï¸ Cháº¿ Ä‘á»™ hiá»ƒn thá»‹:", ["Shaded","Realistic","X-Ray","Wireframe"],
                        key="rm3d_noterr"
                    )
                    try:
                        fig_3d = BVK.ve_cau_3d(d, df_tim_line=None)
                        BVK.apply_render_mode(fig_3d, _rm_no_terr)
                        st.plotly_chart(fig_3d, use_container_width=True,
                                        config={"scrollZoom": True, "displayModeBar": True})
                    except Exception as _e:
                        st.error(f"Lá»—i váº½ 3D: {_e}")
    
            # â”€â”€ TAB 2: Bá»‘ trÃ­ chung â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            with tab_btc:
                st.markdown("##### Bá»‘ trÃ­ chung â€” BÃ¬nh Ä‘á»“ + Tráº¯c dá»c + MCN Ä‘iá»ƒn hÃ¬nh")
                try:
                    _btc1, _btc2 = st.columns([3, 2])
                    with _btc1:
                        st.markdown("**BÃ¬nh Ä‘á»“ cáº§u** (nhÃ¬n tá»« trÃªn)")
                        fig_bd = BVK.ve_binh_do_2d(d, df_tim_line=_df_tim)
                        st.plotly_chart(fig_bd, use_container_width=True,
                                        config={"scrollZoom": True, "displayModeBar": True})
                    with _btc2:
                        st.markdown("**MCN Ä‘iá»ƒn hÃ¬nh**")
                        fig_mcn_btc = BVK.ve_mat_cat_ngang_2d(d)
                        st.plotly_chart(fig_mcn_btc, use_container_width=True,
                                        config={"scrollZoom": True, "displayModeBar": True})
                    st.markdown("**Tráº¯c dá»c cáº§u**")
                    _dc_data = st.session_state.get("dia_chat_data")
                    fig_td_btc = BVK.ve_so_do_nhip_2d(d, df_tim_line=_df_tim,
                                                       dia_chat_data=_dc_data)
                    st.plotly_chart(fig_td_btc, use_container_width=True,
                                    config={"scrollZoom": True, "displayModeBar": True})
                except Exception as _e:
                    st.error(f"Lá»—i tab Bá»‘ trÃ­ chung: {_e}")
    
            # â”€â”€ TAB 3: MCN táº¡i vá»‹ trÃ­ má»‘ / trá»¥ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            with tab_mcn_vt:
                st.markdown("##### Máº·t cáº¯t ngang táº¡i tá»«ng vá»‹ trÃ­ Má»‘ â€“ Trá»¥")
                _kcn_vt = d.get("kcn_result") or d.get("ai_result", {})
                _n_nhip_vt = int(_kcn_vt.get("tong_so_nhip", 3))
                _n_tru_vt  = max(0, _n_nhip_vt - 1)
                _vi_tri_options = ["mo_trai"] + [f"tru_{i+1}" for i in range(_n_tru_vt)] + ["mo_phai"]
                _vi_tri_labels  = (
                    ["Má»‘ trÃ¡i"] +
                    [f"Trá»¥ T{i+1}" for i in range(_n_tru_vt)] +
                    ["Má»‘ pháº£i"]
                )
                _sel_col1, _sel_col2 = st.columns([2, 3])
                with _sel_col1:
                    _vt_idx = st.radio(
                        "Chá»n vá»‹ trÃ­:",
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
                    st.metric("LÃ½ trÃ¬nh vá»‹ trÃ­ cáº¯t", f"{_x_cut_show:.2f} m")
                    st.metric("Cao Ä‘á»™ Ä‘Ã¡y dáº§m", f"{d.get('cao_day_dam', 0):.3f} m")
                    st.metric("H trá»¥ Æ°á»›c tÃ­nh", f"{d.get('H_tru_est', 0):.2f} m")
                try:
                    fig_mcn_vt = BVK.ve_mcn_vi_tri(d, vi_tri=_selected_vt, df_geology=_df_geo)
                    st.plotly_chart(fig_mcn_vt, use_container_width=True,
                                    config={"scrollZoom": True, "displayModeBar": True})
                except Exception as _e:
                    st.error(f"Lá»—i váº½ MCN vá»‹ trÃ­: {_e}")
    
            # â”€â”€ TAB: Chi tiáº¿t dáº§m SPT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            with tab_spt:
                try:
                    CTD.render_chi_tiet_loai(d, st, "Super-T", key_prefix="spt")
                except Exception as _e:
                    import traceback
                    st.error(f"Lá»—i tab SPT: {_e}")
                    with st.expander("Chi tiáº¿t lá»—i"):
                        st.code(traceback.format_exc())
    
            # â”€â”€ TAB: Chi tiáº¿t dáº§m T ngÆ°á»£c â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            with tab_tng:
                try:
                    CTD.render_chi_tiet_loai(d, st, "T ngÆ°á»£c", key_prefix="tng")
                except Exception as _e:
                    import traceback
                    st.error(f"Lá»—i tab T ngÆ°á»£c: {_e}")
                    with st.expander("Chi tiáº¿t lá»—i"):
                        st.code(traceback.format_exc())
    
            # â”€â”€ TAB: Chi tiáº¿t dáº§m I â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            with tab_dami:
                try:
                    CTD.render_chi_tiet_loai(d, st, "Dáº§m I", key_prefix="dami")
                except Exception as _e:
                    import traceback
                    st.error(f"Lá»—i tab Dáº§m I: {_e}")
                    with st.expander("Chi tiáº¿t lá»—i"):
                        st.code(traceback.format_exc())
    
            # â”€â”€ TAB: Äá»‹a cháº¥t & Äá»‹a hÃ¬nh chi tiáº¿t â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            with tab_dia_chat:
                # â”€â”€ Quy trÃ¬nh 3 bÆ°á»›c â€” luÃ´n hiá»ƒn thá»‹ dÃ¹ cÃ³ hay chÆ°a cÃ³ Ä‘á»‹a hÃ¬nh â”€â”€
                _dc_tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "Data", "Template_DiaChat.xlsx")
                st.markdown("##### ðŸª¨ Quy trÃ¬nh khai bÃ¡o dá»¯ liá»‡u Ä‘á»‹a cháº¥t")
                _cs1, _cs2, _cs3 = st.columns(3)
                with _cs1:
                    st.markdown(
                        "<div style='background:#1e3a5f;border-radius:8px;padding:14px'>"
                        "<div style='color:#f39c12;font-weight:700;font-size:14px'>1ï¸âƒ£ Táº£i file template máº«u</div>"
                        "<div style='color:#ccc;font-size:12px;margin-top:6px'>"
                        "Má»Ÿ file, Ä‘á»c hÆ°á»›ng dáº«n á»Ÿ sheet <b>HUONG_DAN</b>.</div></div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown("")
                    if os.path.exists(_dc_tpl):
                        with open(_dc_tpl, "rb") as _fh_tpl:
                            st.download_button(
                                "â¬‡ï¸ Táº£i Template_DiaChat.xlsx",
                                data=_fh_tpl.read(),
                                file_name="Template_DiaChat.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True, key="dl_tpl_dc",
                                help="Gá»“m 5 sheet: HUONG_DAN Â· Toado_HK Â· HK1 Â· HK2 Â· HK3 Â· SPT",
                            )
                        st.caption("Sheet: HUONG_DAN | Toado_HK | HKx | SPT")
                    else:
                        st.error("âš ï¸ KhÃ´ng tÃ¬m tháº¥y Data/Template_DiaChat.xlsx")
                with _cs2:
                    st.markdown(
                        "<div style='background:#1a3d1a;border-radius:8px;padding:14px'>"
                        "<div style='color:#2ecc71;font-weight:700;font-size:14px'>2ï¸âƒ£ Äiá»n sá»‘ liá»‡u vÃ o template</div>"
                        "<div style='color:#ccc;font-size:12px;margin-top:6px'>"
                        "â€¢ Sheet <b>Toado_HK</b>: tá»a Ä‘á»™ X, Y (VN-2000) + Z miá»‡ng há»‘<br>"
                        "â€¢ Sheet <b>HK01, HK02â€¦</b>: tÃªn lá»›p, cao Ä‘á»™ Ä‘Ã¡y lá»›p, mÃ´ táº£<br>"
                        "â€¢ Sheet <b>SPT</b>: Ä‘á»™ sÃ¢u + giÃ¡ trá»‹ N (náº¿u cÃ³)</div></div>",
                        unsafe_allow_html=True,
                    )
                with _cs3:
                    st.markdown(
                        "<div style='background:#3d1a1a;border-radius:8px;padding:14px'>"
                        "<div style='color:#e74c3c;font-weight:700;font-size:14px'>3ï¸âƒ£ Upload & phÃ¢n tÃ­ch</div>"
                        "<div style='color:#ccc;font-size:12px;margin-top:6px'>"
                        "Táº£i file Ä‘Ã£ Ä‘iá»n lÃªn Ã´ bÃªn dÆ°á»›i. Há»‡ thá»‘ng tá»± Ä‘á»c vÃ  tÃ­ch há»£p "
                        "vÃ o mÃ´ hÃ¬nh 3D Ä‘á»‹a hÃ¬nh (náº¿u Ä‘Ã£ náº¡p file .NTD).</div></div>",
                        unsafe_allow_html=True,
                    )
    
                st.markdown("---")
    
                # â”€â”€ Upload file Ä‘á»‹a cháº¥t (luÃ´n hiá»ƒn thá»‹) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                st.markdown("#### ðŸ“¤ Táº£i lÃªn file Excel Ä‘á»‹a cháº¥t Ä‘Ã£ Ä‘iá»n")
                file_excel_dc = st.file_uploader(
                    "Chá»n file .xlsx (cáº¥u trÃºc theo template):",
                    type=["xlsx"], key="dc_ex",
                    help="File cáº§n cÃ³: sheet Toado_HK (tá»a Ä‘á»™ há»‘ khoan) + sheet HKxx (phÃ¢n lá»›p Ä‘á»‹a cháº¥t tá»«ng há»‘).",
                )
                df_hk, df_layers, df_spt = None, None, None
                hien_mat_lop, hien_khoi_lop, do_trong_dh = True, False, 1.0
    
                if file_excel_dc:
                    with st.spinner("Äang phÃ¢n tÃ­ch Ä‘á»‹a cháº¥t..."):
                        df_hk, df_layers, df_spt = TV.doc_excel_dia_chat_3_sheet(file_excel_dc)
                    if df_hk is not None and not df_hk.empty:
                        st.success(f"âœ… Äá»c Ä‘Æ°á»£c **{len(df_hk)} há»‘ khoan** tá»« file.")
                        _df_hk_show = df_hk.rename(columns={
                            "Ho_Khoan": "Há»‘ khoan",
                            "X_VN2000": "X (VN-2000)",
                            "Y_VN2000": "Y (VN-2000)",
                            "Z_Mieng":  "Z miá»‡ng (m)",
                        })
                        st.dataframe(_df_hk_show, use_container_width=True, hide_index=True)
                        _cap_parts = []
                        if df_layers is not None and not df_layers.empty:
                            _n_lop = (df_layers["Ten_Lop"].nunique()
                                      if "Ten_Lop" in df_layers.columns else len(df_layers))
                            _cap_parts.append(f"ðŸ“ {_n_lop} loáº¡i lá»›p | {len(df_layers)} báº£n ghi phÃ¢n lá»›p")
                        if df_spt is not None and not df_spt.empty:
                            _cap_parts.append(f"ðŸ”© SPT: {len(df_spt)} dÃ²ng")
                        if _cap_parts:
                            st.caption(" Â· ".join(_cap_parts))
                        # â”€â”€ LÆ°u vÃ o session_state Ä‘á»ƒ tráº¯c dá»c dÃ¹ng Ä‘Æ°á»£c â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                            st.caption(f"ðŸ’¾ ÄÃ£ lÆ°u {len(_hk_list_ss)} há»‘ khoan vÃ o bá»™ nhá»› phiÃªn â€” tráº¯c dá»c sáº½ hiá»ƒn thá»‹ Ä‘á»‹a cháº¥t.")
                        except Exception as _e_ss:
                            st.caption(f"âš ï¸ LÆ°u session_state tháº¥t báº¡i: {_e_ss}")
                        if has_terr:
                            cdc1, cdc2, cdc3 = st.columns(3)
                            with cdc1:
                                hien_mat_lop  = st.checkbox("Máº·t pháº³ng lá»›p Ä‘áº¥t", True)
                            with cdc2:
                                hien_khoi_lop = st.checkbox("Khá»‘i lá»›p Ä‘áº¥t", False)
                            with cdc3:
                                do_trong_dh = st.slider("Äá»™ trong suá»‘t:", 0.35, 1.0, 0.72, 0.05)
                    else:
                        st.error("âŒ KhÃ´ng Ä‘á»c Ä‘Æ°á»£c dá»¯ liá»‡u. Kiá»ƒm tra cáº¥u trÃºc file theo template.")
    
                # â”€â”€ MÃ´ hÃ¬nh 3D Ä‘á»‹a hÃ¬nh + overlay Ä‘á»‹a cháº¥t â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                if not has_terr:
                    st.info("ðŸ“Œ Náº¡p file Ä‘á»‹a hÃ¬nh (.NTD + tá»a Ä‘á»™ VN-2000) á»Ÿ **Ä‘áº§u tab Báº¢N Váº¼ Ká»¸ THUáº¬T** Ä‘á»ƒ xem mÃ´ hÃ¬nh 3D Ä‘á»‹a hÃ¬nh tÃ­ch há»£p Ä‘á»‹a cháº¥t.")
                else:
                    try:
                        st.markdown("---")
                        st.subheader("ðŸ“Š MÃ´ hÃ¬nh Äá»‹a hÃ¬nh 3D chi tiáº¿t")
                        col_d1, col_d2, col_d3 = st.columns(3)
                        with col_d1:
                            _che = st.selectbox("Cháº¿ Ä‘á»™:", ["Bá» máº·t má»‹n","ÄÆ°á»ng Ä‘á»“ng má»©c","LÆ°á»›i tam giÃ¡c"], key="dccd")
                        with col_d2:
                            _hz  = st.slider("PhÃ³ng Ä‘áº¡i Z:", 0.05, 3.0, 0.5, 0.05, key="dchz")
                        with col_d3:
                            _dm  = st.select_slider("Má»‹n hoÃ¡:", [1,3,5,7], 3, key="dcdm")
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
                        st.error(f"Lá»—i Ä‘á»‹a cháº¥t: {_e}")
    
            # â”€â”€ TAB: Xuáº¥t báº£n váº½ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            with tab_export:
                st.subheader("ðŸ“¤ Xuáº¥t báº£n váº½ ká»¹ thuáº­t")
                st.markdown(
                    "<div style='background:#141420;border:1px solid #2a2a3a;"
                    "border-radius:8px;padding:12px 14px;"
                    "display:flex;align-items:center;gap:10px'>"
                    "<span style='font-size:20px'>â¬‡ï¸</span>"
                    "<div>"
                    "<div style='font-size:12px;color:#ccc;font-weight:600'>"
                    "Xuáº¥t DXF / IFC / PDF</div>"
                    "<div style='font-size:11px;color:#666;margin-top:2px'>"
                    "Táº¥t cáº£ tÃ¹y chá»n xuáº¥t file náº±m trong "
                    "<b style='color:#4fc3f7'>thanh bÃªn trÃ¡i â†–</b></div>"
                    "</div></div>",
                    unsafe_allow_html=True,
                )
    
    # =========================================================================
    # SO SÃNH PHÆ¯Æ NG ÃN
    # =========================================================================
    elif selected_ribbon == "SO SÃNH PHÆ¯Æ NG ÃN":
        _s2 = tab_states['tab2']
        if _s2 == 'done':
            st.markdown(
                DS.banner("success", "ÄÃ£ cÃ³ 3 phÆ°Æ¡ng Ã¡n â€” Ä‘ang hiá»ƒn thá»‹ káº¿t quáº£ so sÃ¡nh."),
                unsafe_allow_html=True,
            )
        elif _s2 == 'partial':
            st.markdown(
                DS.banner("warning",
                          "ÄÃ£ cÃ³ káº¿t quáº£ káº¿t cáº¥u nhá»‹p",
                          "Cháº¡y láº¡i pipeline Ä‘áº§y Ä‘á»§ Ä‘á»ƒ sinh so sÃ¡nh 3 phÆ°Æ¡ng Ã¡n"),
                unsafe_allow_html=True,
            )
    
        alts = st.session_state.get("alternatives", None)
        if alts is None:
            st.markdown(
                DS.section_header(
                    title = "So sÃ¡nh 3 PhÆ°Æ¡ng Ã¡n Loáº¡i Dáº§m",
                    icon  = "ðŸ“Š",
                    sub   = "Há»‡ thá»‘ng sáº½ tÃ­nh toÃ¡n cÃ¹ng má»™t cáº§u vá»›i 3 loáº¡i dáº§m, so sÃ¡nh ká»¹ thuáº­t + kinh táº¿",
                ),
                unsafe_allow_html=True,
            )
            _es = DS.empty_state(
                icon      = "ðŸ“Š",
                title     = "ChÆ°a cÃ³ dá»¯ liá»‡u so sÃ¡nh",
                desc      = ("Nháº¥n <b>âš™ï¸ OPTIONS</b> â†’ Ä‘iá»n thÃ´ng sá»‘ â†’ "
                             "<b>ðŸš€ Cháº¡y AI</b> Ä‘á»ƒ sinh 3 phÆ°Æ¡ng Ã¡n tá»± Ä‘á»™ng."),
                cta_label = "âš™ï¸ Má»Ÿ OPTIONS",
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
                    title = "Giá»›i thiá»‡u 3 phÆ°Æ¡ng Ã¡n so sÃ¡nh",
                    icon  = "â„¹ï¸",
                ),
                unsafe_allow_html=True,
            )
            st.caption("Sau khi pipeline cháº¡y xong, há»‡ thá»‘ng hiá»ƒn thá»‹ báº£ng so sÃ¡nh ká»¹ thuáº­t, radar chart vÃ  phÃ¢n tÃ­ch chi phÃ­.")
    
            # Tháº» thÃ´ng tin 3 loai dam
            _c1, _c2, _c3 = st.columns(3)
            _dam_cards = [
                {
                    "color": "#3498db",
                    "title": "PA1 â€” Dáº§m I",
                    "subtitle": "BTCT dá»± á»©ng lá»±c â€” Ä‘Ãºc sáºµn",
                    "specs": [
                        ("Chiá»u dÃ i nhá»‹p", "18 â€“ 33 m"),
                        ("Tá»‰ lá»‡ H/L tá»‘i Æ°u", "1/15 â€“ 1/18"),
                        ("Sá»‘ dáº§m / MCN", "5 â€“ 9 dáº§m"),
                        ("Khoáº£ng cÃ¡ch tim", "1.8 â€“ 2.2 m"),
                    ],
                    "tru": "ThÃ¢n cá»™t 2â€“3 trá»¥ (táº£i trá»ng trung bÃ¬nh)",
                    "pros": "Phá»• biáº¿n nháº¥t táº¡i VN, nhÃ  cung cáº¥p nhiá»u, thi cÃ´ng nhanh",
                    "cons": "Chiá»u cao dáº§m lá»›n hÆ¡n Super-T, cáº§n cáº©u láº¯p chuyÃªn dá»¥ng",
                    "use": "Cáº§u nÃ´ng thÃ´n, Ä‘Æ°á»ng tá»‰nh, cáº¥p IVâ€“VI",
                },
                {
                    "color": "#2ecc71",
                    "title": "PA2 â€” T ngÆ°á»£c",
                    "subtitle": "BTCT thÆ°á»ng / DÆ¯L â€” Ä‘á»• táº¡i chá»— hoáº·c Ä‘Ãºc sáºµn",
                    "specs": [
                        ("Chiá»u dÃ i nhá»‹p", "12 â€“ 22 m"),
                        ("Tá»‰ lá»‡ H/L tá»‘i Æ°u", "1/12 â€“ 1/15"),
                        ("Sá»‘ dáº§m / MCN", "5 â€“ 11 dáº§m"),
                        ("Khoáº£ng cÃ¡ch tim", "0.9 â€“ 1.2 m"),
                    ],
                    "tru": "ThÃ¢n cá»™t Ä‘Æ¡n hoáº·c 2 trá»¥ (táº£i nhá», nhá»‹p ngáº¯n)",
                    "pros": "Chi phÃ­ dáº§m Ä‘Æ¡n chiáº¿c tháº¥p nháº¥t, Ä‘Æ¡n giáº£n thi cÃ´ng",
                    "cons": "Nhiá»u trá»¥ hÆ¡n â†’ cáº£n dÃ²ng, tÄƒng chi phÃ­ mÃ³ng",
                    "use": "Cáº§u kÃªnh nhá», Ä‘Æ°á»ng nÃ´ng thÃ´n cáº¥p Vâ€“VI",
                },
                {
                    "color": "#e67e22",
                    "title": "PA3 â€” Super-T",
                    "subtitle": "BTCT dá»± á»©ng lá»±c â€” Ä‘Ãºc sáºµn tiáº¿t diá»‡n T rá»—ng",
                    "specs": [
                        ("Chiá»u dÃ i nhá»‹p", "27 â€“ 40 m"),
                        ("Tá»‰ lá»‡ H/L tá»‘i Æ°u", "1/18 â€“ 1/20"),
                        ("Sá»‘ dáº§m / MCN", "4 â€“ 7 dáº§m"),
                        ("Khoáº£ng cÃ¡ch tim", "2.0 â€“ 2.5 m"),
                    ],
                    "tru": "Trá»¥ Ä‘áº·c / Ä‘áº·c thÃ¢n háº¹p (táº£i lá»›n tá»« nhá»‹p dÃ i)",
                    "pros": "Ãt trá»¥, Ã­t cáº£n dÃ²ng, káº¿t cáº¥u thanh máº£nh hiá»‡n Ä‘áº¡i",
                    "cons": "Trá»ng lÆ°á»£ng dáº§m lá»›n â†’ cáº§n thiáº¿t bá»‹ cáº©u láº¯p máº¡nh hÆ¡n",
                    "use": "Cáº§u sÃ´ng lá»›n, quá»‘c lá»™, cáº¥p IIIâ€“IV",
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
                        f"<div style='font-size:12px;color:#aaa'><b style='color:{_card['color']}'>Loáº¡i trá»¥:</b> {_card['tru']}</div>"
                        f"<div style='font-size:12px;color:#aaa;margin-top:6px'><b style='color:#2ecc71'>âœ”</b> {_card['pros']}</div>"
                        f"<div style='font-size:12px;color:#aaa;margin-top:4px'><b style='color:#e74c3c'>âœ˜</b> {_card['cons']}</div>"
                        f"<div style='font-size:11px;background:{_card['color']}22;border-radius:6px;"
                        f"padding:6px 8px;margin-top:10px;color:{_card['color']}'>"
                        f"ðŸ“Œ {_card['use']}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
    
            st.markdown("---")
            st.markdown("### Ná»™i dung so sÃ¡nh sau khi cháº¡y pipeline")
            _info_cols = st.columns(4)
            for _ic, (_icon, _txt) in zip(_info_cols, [
                ("ðŸ“", "Báº£ng Ä‘a tiÃªu chÃ­\nKCN Â· Trá»¥ Â· MÃ³ng"),
                ("ðŸ’°", "Chi phÃ­ tÆ°Æ¡ng Ä‘á»‘i\n(Dáº§m I = 100%)"),
                ("ðŸ“Š", "Biá»ƒu Ä‘á»“ radar\n5 tiÃªu chÃ­ Ä‘Ã¡nh giÃ¡"),
                ("ðŸ›ï¸", "So sÃ¡nh loáº¡i trá»¥\nvÃ  phÆ°Æ¡ng Ã¡n mÃ³ng"),
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
                st.error(f"Lá»—i render so sÃ¡nh phÆ°Æ¡ng Ã¡n: {_ssp_err}")
                import traceback
                st.code(traceback.format_exc())

_render_statusbar(st.session_state.design_data)


# â”€â”€ Debug Design System panel (bá» checkbox trÆ°á»›c khi deploy) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if st.sidebar.checkbox("ðŸ”§ Debug DS", value=False, key="ds_debug_toggle"):
    import inspect
    with st.expander("ðŸŽ¨ Design System Token Preview", expanded=True):
        st.caption("Táº¥t cáº£ token mÃ u sáº¯c trong DS.Color â€” dÃ¹ng Ä‘á»ƒ kiá»ƒm tra visual consistency.")
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
