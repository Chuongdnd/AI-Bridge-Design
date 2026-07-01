"""
Module 00-DesignSystem — Hệ thống ngôn ngữ thiết kế
Dùng trong toàn bộ app — import 1 lần từ 00-Interface.py
Thay đổi token ở đây sẽ cập nhật toàn bộ giao diện.
"""


# ══════════════════════════════════════════════════════════
# TOKEN MÀU SẮC
# ══════════════════════════════════════════════════════════

class Color:
    # Nền
    BG_BASE      = "#0f0f1a"
    BG_SURFACE   = "#1e1e2e"
    BG_ELEVATED  = "#141420"
    BG_INSET     = "#12121e"

    # Viền
    BORDER_SUBTLE  = "#2a2a3a"
    BORDER_DEFAULT = "#333355"
    BORDER_FOCUS   = "#007acc"

    # Accent chính
    PRIMARY        = "#007acc"
    PRIMARY_DARK   = "#005fa3"
    PRIMARY_BG     = "#0a1f35"

    # Semantic
    SUCCESS        = "#2ecc71"
    SUCCESS_BG     = "#0d3d1f"
    WARNING        = "#f39c12"
    WARNING_BG     = "#1f1600"
    ERROR          = "#e74c3c"
    ERROR_BG       = "#2d0a0a"
    INFO           = "#4fc3f7"
    INFO_BG        = "#0a1f35"

    # Loại kết cấu — dùng nhất quán toàn app
    DAM_SUPER_T    = "#007acc"
    DAM_I          = "#2ecc71"
    DAM_T_NGUOC    = "#f39c12"
    DAM_OTHER      = "#9b59b6"

    TRU_COT        = "#9b59b6"
    TRU_DAC        = "#6c3483"
    MONG_CKN       = "#e67e22"
    MONG_EP        = "#d35400"
    MONG_NONG      = "#e74c3c"

    # Text
    TEXT_PRIMARY   = "#f0f0f0"
    TEXT_SECONDARY = "#aaaaaa"
    TEXT_MUTED     = "#666666"
    TEXT_DISABLED  = "#444455"


# ══════════════════════════════════════════════════════════
# TOKEN SPACING & SHAPE
# ══════════════════════════════════════════════════════════

class Space:
    XS  = "4px"
    SM  = "8px"
    MD  = "12px"
    LG  = "16px"
    XL  = "24px"
    XXL = "32px"


class Radius:
    SM   = "6px"
    MD   = "8px"
    LG   = "12px"
    XL   = "16px"
    PILL = "999px"


class Font:
    SIZE_XS   = "10px"
    SIZE_SM   = "11px"
    SIZE_BASE = "13px"
    SIZE_MD   = "14px"
    SIZE_LG   = "16px"
    SIZE_XL   = "20px"
    SIZE_2XL  = "24px"

    WEIGHT_NORMAL = "400"
    WEIGHT_MEDIUM = "500"
    WEIGHT_BOLD   = "600"

    LABEL_STYLE = (
        f"font-size:10px;color:{Color.TEXT_MUTED};"
        "text-transform:uppercase;letter-spacing:0.5px;margin:0 0 6px"
    )


# ══════════════════════════════════════════════════════════
# COMPONENT: EMPTY STATE
# ══════════════════════════════════════════════════════════

def empty_state(
    icon:      str,
    title:     str,
    desc:      str,
    cta_label: str = "",
    cta_key:   str = "",
    variant:   str = "default",   # 'default' | 'locked' | 'error'
) -> dict:
    """
    Trả về dict {'html': str, 'show_cta': bool, 'cta_key': str}
    Caller dùng st.markdown(result['html']) rồi
    if result['show_cta']: st.button(cta_label, key=cta_key)
    """
    _border_colors = {
        "default": Color.BORDER_DEFAULT,
        "locked":  Color.BORDER_SUBTLE,
        "error":   Color.ERROR,
    }
    _icon_colors = {
        "default": Color.TEXT_MUTED,
        "locked":  Color.TEXT_DISABLED,
        "error":   Color.ERROR,
    }
    border = _border_colors.get(variant, Color.BORDER_DEFAULT)
    ic     = _icon_colors.get(variant,   Color.TEXT_MUTED)

    html = (
        f"<div style='text-align:center;padding:32px 24px;"
        f"background:{Color.BG_SURFACE};"
        f"border:1px dashed {border};"
        f"border-radius:{Radius.LG};margin:8px 0'>"
        f"<div style='font-size:36px;margin-bottom:10px;"
        f"color:{ic}'>{icon}</div>"
        f"<div style='font-size:{Font.SIZE_MD};"
        f"font-weight:{Font.WEIGHT_MEDIUM};"
        f"color:{Color.TEXT_PRIMARY};margin-bottom:6px'>"
        f"{title}</div>"
        f"<div style='font-size:{Font.SIZE_SM};"
        f"color:{Color.TEXT_SECONDARY};line-height:1.6;"
        f"max-width:320px;margin:0 auto'>"
        f"{desc}</div>"
        f"</div>"
    )
    return {
        "html":      html,
        "show_cta":  bool(cta_label),
        "cta_label": cta_label,
        "cta_key":   cta_key,
    }


# ══════════════════════════════════════════════════════════
# COMPONENT: THÔNG BÁO CHUẨN
# ══════════════════════════════════════════════════════════

def banner(
    level:   str,   # 'info' | 'success' | 'warning' | 'error'
    message: str,
    detail:  str = "",
    icon:    str = "",
) -> str:
    """Trả về HTML string banner thông báo nhất quán."""
    _cfg = {
        "info":    (Color.INFO_BG,    Color.INFO,    icon or "ℹ️"),
        "success": (Color.SUCCESS_BG, Color.SUCCESS, icon or "✅"),
        "warning": (Color.WARNING_BG, Color.WARNING, icon or "⚠️"),
        "error":   (Color.ERROR_BG,   Color.ERROR,   icon or "❌"),
    }
    bg, color, ic = _cfg.get(level, _cfg["info"])
    detail_html = (
        f"<div style='font-size:{Font.SIZE_XS};"
        f"color:{Color.TEXT_MUTED};margin-top:3px'>{detail}</div>"
        if detail else ""
    )
    return (
        f"<div style='padding:{Space.SM} {Space.MD};"
        f"background:{bg};"
        f"border-left:3px solid {color};"
        f"border-radius:0 {Radius.SM} {Radius.SM} 0;"
        f"margin:{Space.XS} 0'>"
        f"<span style='color:{color}'>{ic}</span> "
        f"<span style='font-size:{Font.SIZE_SM};"
        f"color:{Color.TEXT_PRIMARY}'>{message}</span>"
        f"{detail_html}"
        f"</div>"
    )


# ══════════════════════════════════════════════════════════
# COMPONENT: SECTION HEADER
# ══════════════════════════════════════════════════════════

def section_header(
    title:  str,
    icon:   str = "",
    sub:    str = "",
    action: str = "",
) -> str:
    """Header chuẩn cho mỗi section trong tab."""
    sub_html = (
        f"<div style='font-size:{Font.SIZE_SM};"
        f"color:{Color.TEXT_MUTED};margin-top:2px'>{sub}</div>"
        if sub else ""
    )
    action_html = (
        f"<div style='font-size:{Font.SIZE_XS};"
        f"color:{Color.PRIMARY}'>{action}</div>"
        if action else ""
    )
    return (
        f"<div style='display:flex;justify-content:space-between;"
        f"align-items:flex-start;margin:{Space.LG} 0 {Space.SM}'>"
        f"<div>"
        f"<div style='font-size:{Font.SIZE_LG};"
        f"font-weight:{Font.WEIGHT_MEDIUM};"
        f"color:{Color.TEXT_PRIMARY}'>"
        f"{icon} {title}</div>"
        f"{sub_html}"
        f"</div>"
        f"{action_html}"
        f"</div>"
        f"<hr style='border-color:{Color.BORDER_SUBTLE};"
        f"margin:0 0 {Space.MD}'>"
    )


# ══════════════════════════════════════════════════════════
# COMPONENT: TAG / BADGE
# ══════════════════════════════════════════════════════════

def badge(
    label: str,
    color: str = Color.PRIMARY,
    bg:    str = Color.PRIMARY_BG,
) -> str:
    return (
        f"<span style='display:inline-block;"
        f"font-size:{Font.SIZE_XS};font-weight:{Font.WEIGHT_BOLD};"
        f"color:{color};background:{bg};"
        f"padding:2px 8px;border-radius:{Radius.PILL};"
        f"border:1px solid {color}40'>"
        f"{label}</span>"
    )


# ══════════════════════════════════════════════════════════
# HELPERS TIỆN ÍCH
# ══════════════════════════════════════════════════════════

def dam_color(loai_dam: str) -> str:
    """Màu accent chuẩn theo loại dầm."""
    return {
        "Super-T": Color.DAM_SUPER_T,
        "Dầm I":   Color.DAM_I,
        "T ngược": Color.DAM_T_NGUOC,
    }.get(loai_dam, Color.DAM_OTHER)


def mong_color(loai_mong: str) -> str:
    """Màu accent chuẩn theo loại móng."""
    _map = {
        "Cọc khoan nhồi": Color.MONG_CKN,
        "Cọc ép":         Color.MONG_EP,
        "Móng nông":      Color.MONG_NONG,
    }
    return next(
        (v for k, v in _map.items() if k in str(loai_mong)),
        Color.MONG_CKN,
    )


# ══════════════════════════════════════════════════════════
# CSS TOÀN CỤC — inject 1 lần duy nhất
# ══════════════════════════════════════════════════════════

GLOBAL_CSS = f"""
<style>
/* ── Base ── KHÔNG ép nền/chữ .stApp → để Streamlit tự nhuộm theo THEME (☰ →
   Settings → Theme: Light/Dark/System). Nền canvas + widget gốc + biểu đồ (nền
   trong suốt) sẽ bám theme. */

/* ── Utility cards ── */
.ds-card {{
    background:    {Color.BG_SURFACE};
    border:        1px solid {Color.BORDER_DEFAULT};
    border-radius: {Radius.LG};
    padding:       {Space.LG};
    margin:        {Space.SM} 0;
}}
.ds-card-accent {{
    border-top: 3px solid {Color.PRIMARY};
}}

/* ── Labels ── */
.ds-label {{
    font-size:      {Font.SIZE_XS};
    color:          {Color.TEXT_MUTED};
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin:         0 0 {Space.SM};
}}

/* ── Divider ── */
.ds-divider {{
    border:     none;
    border-top: 1px solid {Color.BORDER_SUBTLE};
    margin:     {Space.LG} 0;
}}

/* ── Streamlit overrides ── */
[data-testid="stForm"] {{
    background:    {Color.BG_SURFACE} !important;
    border:        1px solid {Color.BORDER_DEFAULT} !important;
    border-radius: {Radius.LG} !important;
}}

div[data-testid="stExpander"] > details {{
    background:    {Color.BG_SURFACE};
    border:        1px solid {Color.BORDER_SUBTLE} !important;
    border-radius: {Radius.MD} !important;
}}

/* ── Scrollbar ── */
::-webkit-scrollbar       {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {Color.BG_BASE}; }}
::-webkit-scrollbar-thumb {{
    background:    {Color.BORDER_DEFAULT};
    border-radius: {Radius.PILL};
}}
</style>
"""
