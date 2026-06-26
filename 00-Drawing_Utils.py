import numpy as np
import plotly.graph_objects as go
import streamlit as st


# =============================================================================
# QUY TẮC THỂ HIỆN BẢN VẼ (CAD standard) — nguồn dùng chung cho mọi bản vẽ 2D
# Bảng LAYER / TEXT / KÍCH THƯỚC theo bộ quy tắc thể hiện bản vẽ của dự án.
# Màu được CHUYỂN ĐỔI cho nền TRẮNG của webapp (CAD gốc nền đen) để vẫn đọc rõ.
# =============================================================================
# Màu theo LAYER (xấp xỉ màu AutoCAD, đã chỉnh cho nền sáng):
LAYER_COLORS = {
    "0":       "#2b2b2b",  # Trắng/đen 0.35 — đường bao cấu kiện KHÔNG cốt thép
    "1":       "#e74c3c",  # Đỏ 0.35     — nét thép chủ
    "2":       "#e1a100",  # Vàng 0.30   — nét thép đai
    "3":       "#1e8449",  # Xanh lá 0.25— đường bao cấu kiện CÓ cốt thép (BTCT)
    "4":       "#1f9ed1",  # Xanh nhạt   — kích thước, nét cấu kiện mảnh
    "4-dim":   "#1f9ed1",  # Xanh nhạt   — nét DIM
    "4-hidden":"#1f9ed1",  # Xanh nhạt   — nét khuất (dash)
    "5":       "#2e5cb8",  # Xanh dương  — nét mảnh (taluy, break line)
    "5-hatch": "#5b86d6",  # Xanh dương  — hatch
    "6-center":"#2e5cb8",  # Xanh dương  — nét center (chấm gạch)
    "6-text":  "#7d3c98",  # Tím         — text
    "8":       "#7f8c8d",  # Xám 0.09    — nét mảnh
}

# Chiều cao chữ (mm) → quy đổi xấp xỉ sang cỡ font Plotly (px) khi hiển thị:
TEXT_MM = {"note": 1.8, "title": 3.0, "drawing": 4.0}
def mm_to_px(mm):  # 1.8mm ≈ 11px là cỡ đọc tốt trên màn hình
    return max(7, round(float(mm) * 6.1))

# ── DIM STYLE (theo bảng KÍCH THƯỚC) ─────────────────────────────────────────
DIM_COLOR   = LAYER_COLORS["4-dim"]   # nét DIM = layer 4 (xanh nhạt)
DIM_LW      = 1.0                       # nét mảnh 0.15mm
DIM_TEXT    = mm_to_px(TEXT_MM["note"])# chữ kích thước 1.8mm
DIM_ARROW   = 1.4                       # mũi tên closed filled ~1.5mm


def add_dim_h(fig, x0, x1, y, text, color=None, fs=None, ext_from=None):
    """Đường KÍCH THƯỚC NGANG theo chuẩn: nét DIM xanh nhạt + 2 mũi tên closed
    filled (TCVN dim style). Nếu ext_from cho trước (y gốc của đối tượng) sẽ vẽ
    thêm nét gióng (extension line) từ đối tượng tới đường dim."""
    color = color or DIM_COLOR
    fs = fs or DIM_TEXT
    if ext_from is not None:
        for xi in (x0, x1):
            fig.add_shape(type="line", x0=xi, y0=ext_from, x1=xi, y1=y,
                          line=dict(color=color, width=0.8))
    # 2 annotation = đường dim vẽ 2 lần + mũi tên closed ở 2 đầu
    for xh, xt in ((x0, x1), (x1, x0)):
        fig.add_annotation(x=xh, y=y, ax=xt, ay=y, xref="x", yref="y",
                           axref="x", ayref="y", showarrow=True, arrowhead=3,
                           arrowsize=DIM_ARROW, arrowwidth=DIM_LW, arrowcolor=color)
    fig.add_annotation(x=(x0 + x1) / 2, y=y, text=text, showarrow=False,
                       font=dict(size=fs, color=color), yanchor="bottom",
                       bgcolor="rgba(255,255,255,0.85)")


def add_dim_v(fig, x, y0, y1, text, color=None, fs=None, ext_from=None):
    """Đường KÍCH THƯỚC ĐỨNG theo chuẩn (xem add_dim_h)."""
    color = color or DIM_COLOR
    fs = fs or DIM_TEXT
    if ext_from is not None:
        for yi in (y0, y1):
            fig.add_shape(type="line", x0=ext_from, y0=yi, x1=x, y1=yi,
                          line=dict(color=color, width=0.8))
    for yh, yt in ((y0, y1), (y1, y0)):
        fig.add_annotation(x=x, y=yh, ax=x, ay=yt, xref="x", yref="y",
                           axref="x", ayref="y", showarrow=True, arrowhead=3,
                           arrowsize=DIM_ARROW, arrowwidth=DIM_LW, arrowcolor=color)
    fig.add_annotation(x=x, y=(y0 + y1) / 2, text=text, showarrow=False,
                       font=dict(size=fs, color=color), xanchor="left",
                       textangle=-90, bgcolor="rgba(255,255,255,0.85)")


# ── Tùy chỉnh TỶ LỆ cho mặt cắt 2D (mặc định khóa 1:1) ──────────────────────
def apply_aspect(fig, mode="keep", ratio=1.0):
    """Đặt tỷ lệ trục cho 1 hình 2D.
    mode: 'keep' (giữ nguyên thiết kế gốc, KHÔNG sửa) | 'equal' (khóa 1:1) |
          'free' (giãn lấp khung) | 'custom' (cao:ngang = ratio)."""
    if mode == "keep":
        return fig
    try:
        fig.update_xaxes(scaleanchor=None)
        if mode == "free":
            fig.update_yaxes(scaleanchor=None)
        elif mode == "custom":
            fig.update_yaxes(scaleanchor="x", scaleratio=float(ratio))
        else:  # equal 1:1
            fig.update_yaxes(scaleanchor="x", scaleratio=1.0)
    except Exception:
        pass
    return fig


_ASPECT_OPTS = ["Mặc định", "Đúng tỷ lệ 1:1", "Giãn theo khung", "Tùy chỉnh…"]
_ASPECT_MODE = {"Mặc định": "keep", "Đúng tỷ lệ 1:1": "equal",
                "Giãn theo khung": "free", "Tùy chỉnh…": "custom"}


def aspect_control(fig, key, label="⚖️ Tỷ lệ", st_obj=None, default="equal"):
    """Hiện điều khiển chọn tỷ lệ cho 1 hình 2D rồi áp vào fig.
    Theo quy tắc thể hiện bản vẽ, MẶC ĐỊNH = 'Đúng tỷ lệ 1:1' (default='equal').
    Người dùng vẫn có thể đổi sang 'Giãn theo khung' / 'Tùy chỉnh' khi cần xem
    trắc dọc/mặt bằng cho dễ. Trả về fig (đã chỉnh).

    Dùng radio ngang (KHÔNG tạo cột) để an toàn khi gọi bên trong st.columns —
    tránh lỗi lồng cột quá 1 cấp của Streamlit."""
    _st = st_obj or st
    # Vị trí mặc định trên thanh radio theo tham số default (keep/equal/free/custom)
    _default_label = {v: k for k, v in _ASPECT_MODE.items()}.get(default, "Đúng tỷ lệ 1:1")
    _idx = _ASPECT_OPTS.index(_default_label) if _default_label in _ASPECT_OPTS else 1
    sel = _st.radio(label, _ASPECT_OPTS, horizontal=True, index=_idx, key=f"asp_{key}")
    mode = _ASPECT_MODE.get(sel, "keep")
    ratio = 1.0
    if mode == "custom":
        ratio = _st.slider("cao : ngang", 0.2, 5.0, 1.0, 0.1, key=f"aspr_{key}")
    return apply_aspect(fig, mode, ratio)


def ve_ky_hieu_muc_nuoc_plotly(fig, x_pos, y_val, label, color):
    """Vẽ ký hiệu mực nước tương tác bằng nét vẽ của Plotly"""
    fig.add_trace(go.Scatter(
        x=[x_pos - 6, x_pos + 6], y=[y_val, y_val],
        mode="lines", line=dict(color=color, width=1.5),
        showlegend=False, hoverinfo="skip"
    ))
    fig.add_trace(go.Scatter(
        x=[x_pos], y=[y_val + 0.3],
        mode="text", text=[f"{label}<br>{y_val:.3f}m"],
        textposition="top center", textfont=dict(color=color, size=9),
        showlegend=False, hoverinfo="skip"
    ))

def ve_trac_doc_cau(res, df_tim_line=None):
    geo = res.get('geo_logic')
    if not geo:
        return None
    
    if df_tim_line is None or df_tim_line.empty:
        st.warning("Không có dữ liệu tim tuyến")
        return None
    
    # Lấy thông tin từ geo
    x_tim = geo.get('x_tim_clearance', 0)
    x_mo_trai = geo['x_mo_trai']
    x_mo_phai = geo['x_mo_phai']
    x_t1 = geo['x_t1']
    x_t2 = geo['x_t2']
    y_dinh = geo['y_dinh']
    y_t = geo['y_t']
    R = geo['R']
    i_val = geo['i_val']
    y_base_goc = geo['y_base_goc']
    
    # Xác định phạm vi vẽ
    margin = 50
    x_start = x_mo_trai - margin
    x_end = x_mo_phai + margin
    df_view = df_tim_line[(df_tim_line['Lý trình'] >= x_start) & (df_tim_line['Lý trình'] <= x_end)].copy()
    
    if df_view.empty:
        st.warning("Không có dữ liệu tim tuyến trong phạm vi vẽ")
        return None
    
    fig = go.Figure()
    
    # 1. Đường địa hình tự nhiên
    fig.add_trace(go.Scatter(
        x=df_view['Lý trình'], y=df_view['Z'],
        mode='lines', name='Địa hình tự nhiên (tim tuyến)',
        line=dict(color='#27ae60', width=2)
    ))
    
    # 2. Đường đỏ thiết kế
    x_smooth = np.linspace(x_start, x_end, 500)
    y_red = []
    for x in x_smooth:
        if x < x_t1:
            y = y_t - i_val * (x_t1 - x)
        elif x > x_t2:
            y = y_t - i_val * (x - x_t2)
        else:
            y = y_dinh - (x - x_tim)**2 / (2 * R)
        y_red.append(y)
    fig.add_trace(go.Scatter(
        x=x_smooth, y=y_red, name='Đường đỏ thiết kế',
        line=dict(color='#e74c3c', width=3)
    ))
    
    # 3. Đáy dầm
    h_dam = res.get('ai_result', {}).get('chieu_cao', 1.65)
    h_ban = 0.18
    h_tong = h_ban + h_dam
    y_bottom = [y - h_tong for y in y_red]
    fig.add_trace(go.Scatter(
        x=x_smooth, y=y_bottom, name='Đáy dầm',
        line=dict(color='darkblue', width=2, dash='dashdot')
    ))
    
    # 4. Mố
    y_min = df_view['Z'].min()
    y_mo = geo.get('y_mo', y_min)
    fig.add_trace(go.Scatter(
        x=[x_mo_trai, x_mo_trai], y=[y_min, y_mo],
        mode='lines', name='Mố trái', line=dict(color='brown', width=3, dash='dash')
    ))
    fig.add_trace(go.Scatter(
        x=[x_mo_phai, x_mo_phai], y=[y_min, y_mo],
        mode='lines', name='Mố phải', line=dict(color='brown', width=3, dash='dash')
    ))
    
    # 5. Khung tĩnh không
    B = res.get('B', 0)
    H_tk = res.get('H', 0)
    if B > 0 and H_tk > 0:
        idx_tim = np.argmin(np.abs(x_smooth - x_tim))
        y_tim = y_red[idx_tim]
        fig.add_shape(type="rect",
                      x0=x_tim - B/2, x1=x_tim + B/2,
                      y0=y_tim - H_tk, y1=y_tim,
                      line=dict(color="magenta", width=2),
                      fillcolor="rgba(255,0,255,0.1)")
        fig.add_annotation(x=x_tim, y=y_tim - H_tk/2,
                           text=f"TĨNH KHÔNG<br>B={B}m, H={H_tk}m",
                           showarrow=False, font=dict(color="magenta", size=9))
    
    # 6. Mực nước (cầu vượt sông/kênh)
    h1 = res.get('MNCN', 0) - y_base_goc
    h5 = res.get('MNTT', 0) - y_base_goc
    h10 = res.get('MNTC', 0) - y_base_goc
    h98 = res.get('MNTN', 0) - y_base_goc
    ve_ky_hieu_muc_nuoc_plotly(fig, x_mo_trai + 20, h1, "MNCN H1%", "red")
    ve_ky_hieu_muc_nuoc_plotly(fig, x_mo_trai + 40, h5, "MNTT H5%", "blue")
    ve_ky_hieu_muc_nuoc_plotly(fig, x_mo_phai - 40, h10, "MNTC H10%", "green")
    ve_ky_hieu_muc_nuoc_plotly(fig, x_mo_phai - 20, h98, "MNTN H98%", "orange")
    
    # 7. Đường gióng T1, T2
    fig.add_shape(type="line", x0=x_t1, y0=y_min-5, x1=x_t1, y1=y_t,
                  line=dict(color="#95a5a6", width=1.5, dash="dot"))
    fig.add_annotation(x=x_t1, y=y_t-3, text=f"T1<br>{x_t1:.1f}m",
                       showarrow=False, font=dict(size=9))
    fig.add_shape(type="line", x0=x_t2, y0=y_min-5, x1=x_t2, y1=y_t,
                  line=dict(color="#95a5a6", width=1.5, dash="dot"))
    fig.add_annotation(x=x_t2, y=y_t-3, text=f"T2<br>{x_t2:.1f}m",
                       showarrow=False, font=dict(size=9))
    
    # Layout với tỷ lệ 1:1 (scaleratio=1)
    fig.update_layout(
        title=f"TRẮC DỌC THEO TIM TUYẾN - Tim tĩnh không tại LT = {x_tim:.2f}m",
        xaxis_title="Lý trình (m)",
        yaxis_title="Cao độ (m)",
        xaxis=dict(scaleanchor="y", scaleratio=1),
        height=550, template="plotly_white"
    )
    return fig

def ve_mat_cat_ngang(res_mcn, bridge_mode=False):
    """
    Vẽ mặt cắt ngang đường/cầu chi tiết.
    bridge_mode=True : vẽ MCN tại cầu — với cao tốc, lề trồng cỏ → lan can + dải phụ khai thác
                       (Điều 6.12.1 TCVN 5729:2012, Hình 4); chiều rộng cầu = chiều rộng nền đường.
    res_mcn: dict trả về từ YTHH.thiet_ke_mcn_cau_web().
    """
    n_lan        = float(res_mcn.get('n_lan', 2))
    w_lan        = float(res_mcn.get('w_lan', 3.5))
    w_le         = float(res_mcn.get('w_le', 0.5))
    w_le_gc      = float(res_mcn.get('w_le_gc') or 0.0)
    w_dpc        = float(res_mcn.get('w_dpc', 0.0))
    w_lc         = float(res_mcn.get('w_lc', 0.5))
    loai         = res_mcn.get('loai') or ''
    tieu_chuan   = res_mcn.get('tieu_chuan', '—')
    i_doc        = float(res_mcn.get('i_doc_ngang', 2.0))
    is_caotoc    = bool(res_mcn.get('is_caotoc', False))
    is_dothi     = bool(res_mcn.get('is_dothi', False))
    # Cao tốc extras
    w_dat_at_dg  = float(res_mcn.get('w_dat_an_toan_dg', 0.0))
    w_dpc_core   = float(res_mcn.get('w_dpc_core', w_dpc))
    w_le_trong_co= float(res_mcn.get('w_le_trong_co', 0.0))
    i_le_tc      = float(res_mcn.get('i_le_trong_co', 0.0))

    if is_caotoc:
        # Cao tốc: lề = dải AT (le_gc) + lề trồng cỏ (le_trong_co); không có gờ LC riêng
        w_le_gc_draw = w_le_gc
        w_dat_draw   = w_le_trong_co
        w_lc_draw    = 0.0
    else:
        w_le_gc_draw = min(w_le_gc, w_le)
        w_dat_draw   = max(0.0, w_le - w_le_gc_draw)
        w_lc_draw    = w_lc

    w_xechay_1ben = (n_lan * w_lan) / 2.0

    fig = go.Figure()

    def _band(x0, x1, y0, y1, color, name="", sl=False):
        fig.add_trace(go.Scatter(
            x=[x0, x1, x1, x0, x0], y=[y0, y0, y1, y1, y0],
            fill="toself", fillcolor=color, line=dict(color="black", width=1),
            mode="lines", name=name, showlegend=sl, hoverinfo="skip"
        ))

    def _dim(x0, x1, y, txt, color=None, fs=9):
        # Nét DIM theo chuẩn: mũi tên closed filled 2 đầu (giữ màu phân nhóm nếu có)
        color = color or DIM_COLOR
        for xh, xt in ((x0, x1), (x1, x0)):
            fig.add_annotation(x=xh, y=y, ax=xt, ay=y, xref="x", yref="y",
                               axref="x", ayref="y", showarrow=True, arrowhead=3,
                               arrowsize=1.2, arrowwidth=1, arrowcolor=color)
        fig.add_annotation(x=(x0+x1)/2, y=y+0.07, text=txt, showarrow=False,
                           font=dict(size=fs, color=color), yanchor="bottom",
                           bgcolor="rgba(255,255,255,0.85)")

    def _slope_arrow(x_from, x_to, y_ref, i_pct, color="#e74c3c"):
        h_vis = 0.08
        x_l, x_r = min(x_from, x_to), max(x_from, x_to)
        y_tim, y_le = y_ref + h_vis, y_ref
        fig.add_trace(go.Scatter(x=[x_l, x_r], y=[y_tim, y_le], mode="lines",
                                 line=dict(color=color, width=1.5, dash="dot"),
                                 showlegend=False, hoverinfo="skip"))
        fig.add_annotation(x=x_r, y=y_le, ax=x_l, ay=y_tim,
                           xref="x", yref="y", axref="x", ayref="y",
                           showarrow=True, arrowhead=2, arrowsize=1.0,
                           arrowwidth=1.5, arrowcolor=color)
        fig.add_annotation(x=(x_l+x_r)/2, y=(y_tim+y_le)/2+0.05,
                           text=f"i={i_pct:.1f}%", showarrow=False,
                           font=dict(size=8, color=color), bgcolor="rgba(255,255,255,0.8)")

    # bridge_mode: lề trồng cỏ → Lan can + dải phụ khai thác (Điều 6.12.1 TCVN 5729:2012)
    outer_color = "#95a5a6" if (is_caotoc and bridge_mode) else ("#85c88a" if is_caotoc else "#d2b48c")
    outer_label = ("Lan can + dải phụ khai thác" if bridge_mode
                   else ("Lề trồng cỏ" if is_caotoc else "Lề đất"))

    # ── Vùng trung tâm: DPC ──────────────────────────────────────────────────
    if is_caotoc:
        # Vẽ tách: DPC lõi (giữa) + dải an toàn DG (2 bên)
        # Trên cầu: dải phân cách lõi có khoảng trống cho khe hở 2 cầu tách + lan can AT
        _dpc_color = "#1e8449" if bridge_mode else "#27ae60"
        _dpc_label = "DPC (khoảng trống giữa 2 cầu)" if bridge_mode else "Dải phân cách lõi"
        _band(-w_dpc_core/2, w_dpc_core/2, 0, 0.15, _dpc_color, _dpc_label, sl=True)
        for s in (1, -1):
            _band(s*w_dpc_core/2, s*w_dpc/2, -0.02, 0.10, "#a9dfbf",
                  "Dải an toàn DG" if s==1 else "", sl=(s==1))
    elif w_dpc > 0:
        _band(-w_dpc/2, w_dpc/2, 0, 0.15, "#2ecc71", "Dải phân cách", sl=True)

    x_in   = w_dpc / 2
    x_xc   = x_in   + w_xechay_1ben
    x_legc = x_xc   + w_le_gc_draw
    x_le   = x_legc + w_dat_draw
    x_lc   = x_le   + w_lc_draw

    for s in (1, -1):
        _band(s*x_in, s*x_xc, 0, 0.10, "#7f8c8d", "Mặt đường" if s==1 else "", sl=(s==1))
        if w_le_gc_draw > 0:
            _band(s*x_xc, s*x_legc, -0.05, 0.05, "#aeb6bf",
                  ("Lề gia cố" if not is_caotoc else "Lề gia cố / DAT") if s==1 else "", sl=(s==1))
        if w_dat_draw > 0:
            _band(s*x_legc, s*x_le, -0.05, 0.0, outer_color,
                  outer_label if s==1 else "", sl=(s==1))
            # Lan can cầu: đường đứng ký hiệu lan can ở mép ngoài
            if is_caotoc and bridge_mode:
                fig.add_shape(type="line", x0=s*x_le, y0=0.0, x1=s*x_le, y1=0.35,
                              line=dict(color="#2c3e50", width=2))
                fig.add_shape(type="line", x0=s*(x_le-0.1), y0=0.30, x1=s*(x_le+0.1), y1=0.30,
                              line=dict(color="#2c3e50", width=2))
        if w_lc_draw > 0:
            if is_dothi:
                _he_color = "#f5cba7"   # màu hè đường (vỉa hè)
                _band(s*x_le, s*x_lc, -0.05, 0.08, _he_color,
                      "Hè đường" if s==1 else "", sl=(s==1))
                # Gờ đường (bó vỉa) tại mép tiếp giáp hè/lề
                fig.add_shape(type="line", x0=s*x_le, y0=-0.05, x1=s*x_le, y1=0.15,
                              line=dict(color="#7f8c8d", width=2))
            else:
                _band(s*x_le, s*x_lc, 0, 0.30, "#2c3e50",
                      "Gờ/lan can" if s==1 else "", sl=(s==1))

        # Mũi tên dốc ngang mặt đường
        _slope_arrow(s*x_in, s*x_xc, 0.10, i_doc, "#e74c3c")
        # Dải AT trong DG (cao tốc) — dốc ra ngoài
        if is_caotoc and w_dat_at_dg > 0:
            _slope_arrow(s*w_dpc_core/2, s*w_dpc/2, 0.10, i_doc, "#e74c3c")
        # Lề gia cố
        if w_le_gc_draw > 0:
            _slope_arrow(s*x_xc, s*x_legc, 0.05, i_doc, "#e74c3c")
        # Lề trồng cỏ (cao tốc đường) / lan can phụ (cầu) — dốc ngang 6% / phẳng
        if is_caotoc and w_dat_draw > 0 and not bridge_mode:
            _slope_arrow(s*x_legc, s*x_le, 0.0, i_le_tc, "#8e44ad")

    # ── Đường kích thước ────────────────────────────────────────────────────
    x_total = x_lc if w_lc_draw > 0 else x_le
    _dim(-x_total, x_total, 0.60, f"Tổng MCN = {2*x_total:.2f}m", color="#c0392b")
    if is_caotoc:
        _dim(-w_dpc_core/2, w_dpc_core/2, -0.25, f"DPC lõi {w_dpc_core:.2f}m", color="#27ae60")
        _dim(-w_dpc/2, w_dpc/2, -0.40, f"Dải giữa {w_dpc:.2f}m", color="#1e8449")
    elif w_dpc > 0:
        _dim(-w_dpc/2, w_dpc/2, -0.25, f"DPC {w_dpc:.2f}m", color="#27ae60")
    _dim(x_in, x_xc, -0.25, f"PXC {w_xechay_1ben:.2f}m", color="#34495e")
    _dim(x_xc, x_le if w_lc_draw == 0 else x_lc, -0.45,
         f"Lề {w_le:.2f}m", color="#8e44ad")

    if is_caotoc:
        _prefix = "MCN TẠI CẦU" if bridge_mode else "MCN ĐƯỜNG ĐẦU CẦU"
        _outer_txt = "Lan can+dải phụ" if bridge_mode else f"Lề TC {i_le_tc:.0f}%"
        subtitle = (f"{tieu_chuan} | {n_lan//2:g} làn/chiều × {w_lan:.2f}m | "
                    f"DG={w_dpc:.2f}m (lõi {w_dpc_core:.2f}m) | "
                    f"Lề={w_le:.2f}m | i={i_doc:.1f}% | {_outer_txt}")
    elif is_dothi:
        _prefix = "MCN"
        _he_txt  = f"Hè {w_lc:.1f}m | " if w_lc_draw > 0 else ""
        subtitle = (f"{tieu_chuan} | {n_lan:g} làn × {w_lan:.2f}m | "
                    f"DPC={w_dpc:.2f}m | Lề={w_le:.2f}m | {_he_txt}B_tổng={2*x_total:.2f}m | i={i_doc:.1f}%")
    else:
        _prefix = "MCN TẠI CẦU" if bridge_mode else "MCN"
        subtitle = (f"{tieu_chuan} | {n_lan:g} làn × {w_lan:.2f}m | DPC={w_dpc:.2f}m | "
                    f"Lề={w_le:.2f}m (gc {w_le_gc:.2f}m) | B_tổng={2*x_total:.2f}m | i={i_doc:.1f}%")

    fig.update_layout(
        title=dict(
            text=f"{_prefix} — {loai.upper()}<br>"
                 f"<span style='font-size:10px'>{subtitle}</span>",
            x=0.5, font=dict(size=13),
        ),
        xaxis=dict(title="Bề rộng (m)", showgrid=True, gridcolor="#ecf0f1",
                   range=[-x_total-1.5, x_total+1.5], scaleanchor="y", scaleratio=2.2),
        yaxis=dict(showgrid=False, zeroline=False, range=[-0.7, 0.90], showticklabels=False),
        height=360, template="plotly_white",
        legend=dict(orientation="h", y=-0.18, font=dict(size=9)),
        margin=dict(l=40, r=30, t=70, b=90),
    )
    return fig


def _box3d_simple(x0, x1, y0, y1, z0, z1, color, name="", sl=False, opacity=1.0):
    """Khối hộp 3D đơn giản (8 đỉnh, mặt phẳng) — dùng để extrude mặt cắt ngang."""
    xs = [x0, x1, x1, x0, x0, x1, x1, x0]
    ys = [y0, y0, y1, y1, y0, y0, y1, y1]
    zs = [z0, z0, z0, z0, z1, z1, z1, z1]
    ii = [0, 0, 4, 4, 0, 0, 3, 3, 0, 0, 1, 1]
    jj = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 2, 6]
    kk = [2, 3, 6, 7, 5, 4, 6, 7, 7, 4, 6, 5]
    return go.Mesh3d(
        x=xs, y=ys, z=zs, i=ii, j=jj, k=kk,
        color=color, opacity=opacity, flatshading=True,
        lighting=dict(ambient=0.55, diffuse=0.85, specular=0.25, roughness=0.65),
        name=name, showlegend=sl,
    )


def ve_mat_cat_ngang_3d(res_mcn, chieu_dai=20.0, bridge_mode=False):
    """
    Mô hình 3D một đoạn ngắn (mặc định 20m) của mặt cắt ngang đường — khối đặc,
    có đường viền rõ (kiểu Shaded trong Revit). Mặt đường thể hiện độ dốc ngang thực.
    res_mcn: dict trả về từ YTHH.thiet_ke_mcn_cau_web().
    bridge_mode=True: lề trồng cỏ (cao tốc) → lan can + dải phụ khai thác (Điều 6.12).
    """
    n_lan        = float(res_mcn.get('n_lan', 2))
    w_lan        = float(res_mcn.get('w_lan', 3.5))
    w_le         = float(res_mcn.get('w_le', 0.5))
    w_le_gc      = float(res_mcn.get('w_le_gc') or 0.0)
    w_dpc        = float(res_mcn.get('w_dpc', 0.0))
    w_lc         = float(res_mcn.get('w_lc', 0.5))
    loai         = res_mcn.get('loai') or ''
    i_doc        = float(res_mcn.get('i_doc_ngang', 2.0)) / 100.0
    is_caotoc    = bool(res_mcn.get('is_caotoc', False))
    is_dothi     = bool(res_mcn.get('is_dothi', False))
    w_dat_at_dg  = float(res_mcn.get('w_dat_an_toan_dg', 0.0))
    w_dpc_core   = float(res_mcn.get('w_dpc_core', w_dpc))
    w_le_trong_co= float(res_mcn.get('w_le_trong_co', 0.0))
    i_le_tc_r    = float(res_mcn.get('i_le_trong_co', 0.0)) / 100.0

    if is_caotoc:
        w_le_gc_draw = w_le_gc
        w_dat_draw   = w_le_trong_co
        w_lc_draw    = 0.0
    else:
        w_le_gc_draw = min(w_le_gc, w_le)
        w_dat_draw   = max(0.0, w_le - w_le_gc_draw)
        w_lc_draw    = w_lc

    w_xechay_1ben = (n_lan * w_lan) / 2.0
    x_in   = w_dpc / 2
    x_xc   = x_in   + w_xechay_1ben
    x_legc = x_xc   + w_le_gc_draw
    x_le   = x_legc + w_dat_draw
    x_lc   = x_le   + w_lc_draw

    def _z_road(abs_x):
        """Cao độ z mặt đường (dốc ngang i_doc từ mép trong ra ngoài)."""
        return 0.10 - abs(abs_x - x_in) * i_doc

    def _z_le_tc(abs_x):
        """Cao độ lề trồng cỏ (dốc 6% ra ngoài, tiếp nối với mép lề gia cố)."""
        z_at_legc = _z_road(x_legc) - 0.05   # z mặt lề gc tại mép
        return z_at_legc - (abs_x - x_legc) * i_le_tc_r

    L0, L1 = 0.0, float(chieu_dai)
    _ii = [0,0,4,4, 0,0,3,3, 0,0,1,1]
    _jj = [1,2,5,6, 1,5,2,6, 2,6,2,6]
    _kk = [2,3,6,7, 5,4,6,7, 6,5,6,5]
    traces = []

    def _slope_prism(y_in, y_out, z_in_top, z_out_top, z_bot, color, name="", sl=False):
        """Lăng trụ có mặt trên nghiêng (2 cao độ z khác nhau)."""
        xs = [L0, L1, L1, L0,  L0, L1, L1, L0]
        ys = [y_in, y_in, y_out, y_out,  y_in, y_in, y_out, y_out]
        zs = [z_in_top, z_in_top, z_out_top, z_out_top,  z_bot, z_bot, z_bot, z_bot]
        return go.Mesh3d(x=xs, y=ys, z=zs, i=_ii, j=_jj, k=_kk,
                         color=color, opacity=1.0, flatshading=True,
                         lighting=dict(ambient=0.55, diffuse=0.85, specular=0.25, roughness=0.65),
                         name=name, showlegend=sl)

    # ── DPC / dải giữa ──────────────────────────────────────────────────────
    if is_caotoc:
        traces.append(_box3d_simple(L0, L1, -w_dpc_core/2, w_dpc_core/2, 0, 0.15,
                                     "#27ae60", "Dải phân cách lõi", sl=True))
        for s in (1, -1):
            traces.append(_slope_prism(
                s*w_dpc_core/2, s*w_dpc/2,
                _z_road(w_dpc_core/2), _z_road(w_dpc/2),
                -0.02, "#a9dfbf",
                "Dải an toàn DG" if s==1 else "", sl=(s==1)
            ))
    elif w_dpc > 0:
        traces.append(_box3d_simple(L0, L1, -w_dpc/2, w_dpc/2, 0, 0.15, "#2ecc71",
                                     "Dải phân cách", sl=True))

    for s in (1, -1):
        # Mặt đường (dốc ngang)
        traces.append(_slope_prism(
            s*x_in, s*x_xc, _z_road(x_in), _z_road(x_xc), 0.0,
            "#7f8c8d", "Mặt đường" if s==1 else "", sl=(s==1)
        ))

        # Lề gia cố (cùng dốc ngang mặt đường)
        if w_le_gc_draw > 0:
            traces.append(_slope_prism(
                s*x_xc, s*x_legc, _z_road(x_xc)-0.05, _z_road(x_legc)-0.05, -0.05,
                "#aeb6bf",
                ("Lề gia cố" if not is_caotoc else "DAT / Lề gia cố") if s==1 else "",
                sl=(s==1)
            ))

        # Lề đất / lề trồng cỏ / lan can+dải phụ (bridge_mode)
        if w_dat_draw > 0:
            if is_caotoc and bridge_mode:
                # Điều 6.12.1: lề trồng cỏ → lan can + dải phụ khai thác (cùng chiều rộng)
                z_flat = _z_road(x_legc)
                traces.append(_box3d_simple(L0, L1, s*x_legc, s*x_le, -0.05, z_flat,
                                             "#95a5a6",
                                             "Lan can+dải phụ khai thác" if s==1 else "", sl=(s==1)))
                # Gờ lan can nhô lên
                traces.append(_box3d_simple(L0, L1, s*x_le-s*0.15, s*x_le, z_flat, z_flat+0.50,
                                             "#7f8c8d", "", sl=False))
            elif is_caotoc:
                traces.append(_slope_prism(
                    s*x_legc, s*x_le, _z_le_tc(x_legc), _z_le_tc(x_le), -0.05,
                    "#85c88a", "Lề trồng cỏ" if s==1 else "", sl=(s==1)
                ))
            else:
                traces.append(_box3d_simple(L0, L1, s*x_legc, s*x_le, -0.05, 0.0,
                                             "#d2b48c", "Lề đất" if s==1 else "", sl=(s==1)))

        # Gờ/lan can hoặc hè đường (không phải cao tốc)
        if w_lc_draw > 0:
            if is_dothi:
                traces.append(_box3d_simple(L0, L1, s*x_le, s*x_lc, -0.05, 0.08,
                                             "#f5cba7", "Hè đường" if s==1 else "", sl=(s==1)))
                # Bó vỉa nhỏ tại ranh giới hè/lề
                traces.append(_box3d_simple(L0, L1, s*(x_le-0.10), s*x_le, -0.05, 0.15,
                                             "#7f8c8d", "", sl=False))
            else:
                traces.append(_box3d_simple(L0, L1, s*x_le, s*x_lc, 0, 0.30,
                                             "#2c3e50", "Gờ/lan can" if s==1 else "", sl=(s==1)))

    fig = go.Figure(data=traces)
    _3d_prefix = ("MCN TẠI CẦU (Đ.6.12)" if bridge_mode else
                  ("MCN ĐƯỜNG ĐẦU CẦU" if is_caotoc else "MCN"))
    _slope_note = (f" / lan can+dải phụ" if (is_caotoc and bridge_mode) else
                   (f" / lề TC {i_le_tc_r*100:.0f}%" if is_caotoc else
                    (f" / hè {w_lc:.1f}m" if (is_dothi and w_lc_draw > 0) else "")))
    fig.update_layout(
        title=dict(
            text=(f"MÔ HÌNH 3D {_3d_prefix} — {loai.upper()} (đoạn {chieu_dai:.0f}m) | "
                  f"i={i_doc*100:.1f}%{_slope_note}"),
            x=0.5, font=dict(size=12)
        ),
        scene=dict(
            xaxis=dict(title="Chiều dài (m)", backgroundcolor="#f0f0f0",
                       gridcolor="#cccccc", showbackground=True),
            yaxis=dict(title="Bề rộng (m)", backgroundcolor="#e8e8e8",
                       gridcolor="#cccccc", showbackground=True),
            zaxis=dict(title="Cao độ (m)", backgroundcolor="#e0e0e0",
                       gridcolor="#cccccc", showbackground=True),
            aspectmode="data",
            camera=dict(eye=dict(x=-1.6, y=-2.0, z=1.1)),
            bgcolor="white",
        ),
        height=480, margin=dict(l=0, r=0, t=50, b=0),
        legend=dict(font=dict(size=9)),
        paper_bgcolor="white",
    )
    return fig