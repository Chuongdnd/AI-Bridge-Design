"""
Module 06b — Vẽ mặt cắt chi tiết dầm cầu (Plotly)
Phụ thuộc: BEAM_GEOMETRY_DETAIL từ 06-AI_KetCauNhip.py

Hàm xuất công khai:
  draw_supert_AA(geo)           — Mặt cắt A-A giữa nhịp Super-T (rỗng)
  draw_supert_BB(geo)           — Mặt cắt B-B đầu dầm tại mố (đặc)
  draw_supert_CC(geo)           — Mặt cắt C-C đầu dầm tại trụ (chuyển tiếp)
  draw_supert_longitudinal(geo) — Mặt cắt dọc tổng thể Super-T
  draw_dam_I(geo)               — Mặt cắt dầm I
  draw_t_nguoc(geo)             — Mặt cắt T ngược
  draw_dam_ban_rong(geo)        — Mặt cắt dầm bản rỗng
  draw_dam_T(geo)               — Mặt cắt dầm T
  draw_beam_section(loai, geo)  — Dispatcher tự chọn hàm vẽ theo loại dầm

Quy ước hệ trục:
  x — ngang (mm), gốc tại tim dầm
  y — đứng (mm), gốc tại ĐÁY dầm (y=0 = mặt đáy)
  Đơn vị mm xuyên suốt; Plotly tự scale; yaxis=xaxis (tỉ lệ 1:1).
"""

import math
import plotly.graph_objects as go

# ── Bảng màu ─────────────────────────────────────────────────────────────────
_CLR = {
    "concrete"  : "#c8d6c0",
    "concrete_e": "#4a5d52",
    "solid_end" : "#a8bfab",
    "solid_e"   : "#3a4d42",
    "void_bg"   : "#f0f4ef",
    "void_e"    : "#8aab96",
    "cable"     : "#e74c3c",
    "cable_duct": "rgba(231,76,60,0.35)",
    "dim"       : "#5d6d7e",
    "dim_line"  : "#aab7b8",
    "annot_bg"  : "rgba(255,255,255,0.92)",
}

_LAYOUT_DEFAULTS = dict(
    paper_bgcolor="white",
    plot_bgcolor="#f8faf8",
    font=dict(family="Arial, sans-serif", size=10, color="#2c3e50"),
    showlegend=False,
    margin=dict(l=60, r=100, t=50, b=40),
)


# ─────────────────────────────────────────────────────────────────────────────
# Primitives
# ─────────────────────────────────────────────────────────────────────────────

def _poly(fig, xs, ys, fill, edge, name="", opacity=1.0, lw=1.5, dash="solid"):
    """Vẽ polygon đóng kín."""
    xs = list(xs); ys = list(ys)
    fig.add_trace(go.Scatter(
        x=xs + [xs[0]], y=ys + [ys[0]],
        fill="toself", fillcolor=fill, opacity=opacity,
        line=dict(color=edge, width=lw, dash=dash),
        mode="lines", name=name, showlegend=False,
        hovertemplate=(f"<b>{name}</b><extra></extra>" if name else None),
    ))


def _dim_h(fig, y_pos, x0, x1, label, color=None, offset=0):
    """Kích thước ngang với đường dóng và mũi tên."""
    c = color or _CLR["dim"]
    tick = abs(x1 - x0) * 0.03
    ya = y_pos + offset
    for xi in (x0, x1):
        fig.add_shape(type="line", x0=xi, y0=ya - tick, x1=xi, y1=ya + tick,
                      line=dict(color=c, width=1))
    fig.add_shape(type="line", x0=x0, y0=ya, x1=x1, y1=ya,
                  line=dict(color=c, width=1))
    fig.add_annotation(x=(x0 + x1) / 2, y=ya, text=f" {label} ",
                       showarrow=False, yanchor="bottom",
                       font=dict(size=8, color=c),
                       bgcolor=_CLR["annot_bg"])


def _dim_v(fig, x_pos, y0, y1, label, color=None, offset=0):
    """Kích thước đứng."""
    c = color or _CLR["dim"]
    xa = x_pos + offset
    tick = abs(y1 - y0) * 0.03
    for yi in (y0, y1):
        fig.add_shape(type="line", x0=xa - tick, y0=yi, x1=xa + tick, y1=yi,
                      line=dict(color=c, width=1))
    fig.add_shape(type="line", x0=xa, y0=y0, x1=xa, y1=y1,
                  line=dict(color=c, width=1))
    fig.add_annotation(x=xa, y=(y0 + y1) / 2, text=f" {label} ",
                       showarrow=False, xanchor="left",
                       font=dict(size=8, color=c),
                       bgcolor=_CLR["annot_bg"])


def _vline(fig, x, y0, y1, label="", color=None, dash="dot"):
    c = color or _CLR["dim_line"]
    fig.add_shape(type="line", x0=x, y0=y0, x1=x, y1=y1,
                  line=dict(color=c, width=1, dash=dash))
    if label:
        fig.add_annotation(x=x, y=y1, text=f"<b>{label}</b>",
                           showarrow=False, yanchor="bottom", xanchor="center",
                           font=dict(size=8, color=c))


def _hline(fig, y, x0, x1, label="", color=None, dash="dot"):
    c = color or _CLR["dim_line"]
    fig.add_shape(type="line", x0=x0, y0=y, x1=x1, y1=y,
                  line=dict(color=c, width=1, dash=dash))
    if label:
        fig.add_annotation(x=x0, y=y, text=f" {label}",
                           showarrow=False, xanchor="left", yanchor="bottom",
                           font=dict(size=8, color=c))


def _apply_equal_axis(fig, xs_all, ys_all, margin_pct=0.12):
    """Thiết lập tỉ lệ 1:1 với viền đều quanh bản vẽ."""
    xmin, xmax = min(xs_all), max(xs_all)
    ymin, ymax = min(ys_all), max(ys_all)
    span = max(xmax - xmin, ymax - ymin)
    mg = span * margin_pct
    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2
    half = span / 2 + mg
    fig.update_xaxes(range=[cx - half, cx + half], showgrid=True,
                     gridcolor="#e8ede8", zeroline=False,
                     title_text="mm", tickformat=",d")
    fig.update_yaxes(range=[cy - half, cy + half], showgrid=True,
                     gridcolor="#e8ede8", zeroline=False,
                     scaleanchor="x", scaleratio=1,
                     title_text="mm", tickformat=",d")


# ─────────────────────────────────────────────────────────────────────────────
# Super-T helpers — polygon builders
# ─────────────────────────────────────────────────────────────────────────────

def _supert_outer_polygon(mc):
    """
    Trả về (xs, ys) outer polygon Super-T A-A (đối xứng, 12 điểm).

    Gốc tọa độ: x=0 tim dầm, y=0 đáy dầm.
    Đi theo chiều kim đồng hồ từ góc dưới trái.
    """
    A   = mc                     # alias
    H   = A["H_canh_tren"] + A["H_vat_canh_tren"] + A["H_bung"] + A["H_canh_duoi"] + A["H_vat_canh_duoi"]
    wo  = A["web_out_hw"]        # half-width outer web edge ≈510
    haw = A["B_vat_canh_tren"]   # haunch width ≈100
    hah = A["H_vat_canh_tren"]   # haunch height ≈75
    ct  = A["H_canh_tren"]       # top flange height ≈150
    cd  = A["H_canh_duoi"]       # bottom flange height ≈225
    vd  = A["H_vat_canh_duoi"]   # bottom haunch height ≈50
    vdw = A["B_vat_canh_duoi"]   # bottom haunch width ≈50
    hf  = A["B_canh_tren"] // 2  # top flange half-width ≈1100

    # Derived y levels (from bottom = 0)
    y_cd_top  = cd + vd          # top of bottom flange (incl. vat)
    y_web_top = H - ct - hah     # base of top haunch = top of web
    y_tf_bot  = H - ct           # bottom of top flange

    xs = [
        -wo,         # 0: bottom-left outer
        -wo - vdw,   # 1: bottom flange left taper (outer)
         wo + vdw,   # 2: bottom flange right taper
         wo,         # 3: bottom-right outer web
         wo,         # 4: web right at haunch start
         wo + haw,   # 5: haunch inner-right (cantilever inner edge)
         hf,         # 6: top flange right outer
         hf,         # 7: top flange right top
        -hf,         # 8: top flange left top
        -hf,         # 9: top flange left outer
        -wo - haw,   # 10: haunch inner-left
        -wo,         # 11: web left at haunch base
    ]
    ys = [
        0,           # 0
        0,           # 1 (same height as bottom)
        0,           # 2
        0,           # 3
        y_web_top,   # 4
        y_tf_bot,    # 5
        y_tf_bot,    # 6
        H,           # 7
        H,           # 8
        y_tf_bot,    # 9
        y_tf_bot,    # 10
        y_web_top,   # 11 → close back to 0
    ]

    # Note: this simplified polygon omits the bottom vat and
    # the intermediate web bottom steps; see the full version below.
    return xs, ys


def _supert_outer_polygon_full(mc, H_total):
    """
    Outer polygon Super-T S=2200mm — 12 điểm theo polygon chuẩn.
    Gốc: x=0 tim dầm, y=0 đáy dầm (y tăng lên trên).

    Nửa phải: (490,0)→(510,20)→(510,250)→(610,1600)→(1100,1675)→(1100,1750)
    Sườn nghiêng: ±510 tại y=250 → ±610 tại y=1600.
    Cánh hẫng VUỐT: đáy từ y=1600 (gốc, dày 150mm) đến y=1675 (mép, dày 75mm).
    """
    k           = H_total / 1750
    hf          = mc["B_canh_tren"] // 2  # 1100mm: nửa bề rộng cánh
    CHAM        = round(20 * k)
    y_cham      = CHAM                    # y sau vát góc
    y_web_bot   = round(250 * k)          # 250mm: chân sườn / đỉnh bầu đáy
    y_web_top   = round(1600 * k)         # 1600mm: đỉnh sườn / gốc cánh (150mm từ đỉnh)
    y_tf_outer  = round(1675 * k)         # 1675mm: đáy mép cánh (75mm từ đỉnh, vuốt)
    wo          = round(510 * k)          # 510mm: sườn ngoài tại đáy
    wo_top      = round(610 * k)          # 610mm: sườn ngoài tại đỉnh
    p_cham      = wo - CHAM               # 490mm

    xs = [
         p_cham,    # P1 : chamfer đáy phải (490mm, y=0)
         wo,        # P2 : sau chamfer (510mm, y=20)
         wo,        # P3 : chân sườn ngoài (510mm, y=250)
         wo_top,    # P4 : đỉnh sườn ngoài (610mm, y=1600) ← slope P3→P4
         hf,        # P5 : mép cánh đáy (1100mm, y=1675) ← vuốt P4→P5
         hf,        # P6 : mép cánh đỉnh (1100mm, y=H)
        -hf,        # P7 : trái đỉnh
        -hf,        # P8 : trái mép cánh đáy
        -wo_top,    # P9 : trái đỉnh sườn
        -wo,        # P10: trái chân sườn
        -wo,        # P11: trái sau chamfer
        -p_cham,    # P12: trái chamfer
    ]
    ys = [
        0,             # P1
        y_cham,        # P2
        y_web_bot,     # P3
        y_web_top,     # P4
        y_tf_outer,    # P5
        H_total,       # P6
        H_total,       # P7
        y_tf_outer,    # P8
        y_web_top,     # P9
        y_web_bot,     # P10
        y_cham,        # P11
        0,             # P12
    ]
    return xs, ys


def _supert_void_polygon(mc, H_total):
    """
    Polygon khoang rỗng Super-T — hình thang 4 điểm.
    Đỉnh: ±510mm tại y=1600mm (đỉnh sườn / gốc cánh).
    Đáy : ±350mm tại y=250mm  (chân sườn / đỉnh bầu đáy).
    """
    k           = H_total / 1750
    vi_top      = round(510 * k)              # 510mm: mặt trong tại đỉnh
    vi_bot      = mc["B_rong_duoi"] // 2      # 350mm: mặt trong tại đáy (700/2)
    y_void_top  = round(1600 * k)             # 1600mm
    y_void_bot  = round(250 * k)              # 250mm

    xs = [-vi_top, vi_top,  vi_bot, -vi_bot]
    ys = [y_void_top, y_void_top, y_void_bot, y_void_bot]
    return xs, ys


# ─────────────────────────────────────────────────────────────────────────────
# draw_supert_AA
# ─────────────────────────────────────────────────────────────────────────────

def draw_supert_AA(geo, title=None):
    """
    Vẽ mặt cắt A-A giữa nhịp dầm Super-T (có khoang rỗng).

    Parameters
    ----------
    geo   : dict từ get_beam_geometry_detail() — BEAM_GEOMETRY_DETAIL entry
    title : str, optional

    Returns
    -------
    plotly.graph_objects.Figure
    """
    mc = geo["MC_AA"]
    H  = geo["H"]   # tổng chiều cao (mm)

    fig = go.Figure()
    fig.update_layout(**_LAYOUT_DEFAULTS,
                      title=dict(text=title or f"Mặt cắt A-A — Super-T H={H}mm",
                                 x=0.5, font=dict(size=13)))

    # ── 1. Outer polygon (concrete) ──────────────────────────────────────────
    ox, oy = _supert_outer_polygon_full(mc, H)
    _poly(fig, ox, oy, _CLR["concrete"], _CLR["concrete_e"],
          "Bê tông dầm Super-T", lw=2)

    # ── 2. Inner void (background color = "đục lỗ") ──────────────────────────
    vx, vy = _supert_void_polygon(mc, H)
    _poly(fig, vx, vy, _CLR["void_bg"], _CLR["void_e"],
          "Khoang rỗng", lw=1.2)

    # ── 3. Tim dầm (centerline) ───────────────────────────────────────────────
    _vline(fig, 0, -H * 0.06, H * 1.07, "TIM DẦM", dash="dashdot",
           color="#95a5a6")

    # ── 4. Kích thước ─────────────────────────────────────────────────────────
    hf   = mc["B_canh_tren"] // 2
    wo   = mc["web_out_hw"]
    cd   = mc["H_canh_duoi"]
    vdh  = mc["H_vat_canh_duoi"]
    ct   = mc["H_canh_tren"]
    hah  = mc["H_vat_canh_tren"]
    vi_t = wo - mc["B_bung_top"]
    vi_b = wo - mc["B_bung_bot"]

    dim_x_right = hf + hf * 0.08    # vị trí đặt kích thước đứng bên phải
    dim_x_left  = -hf - hf * 0.08

    # Chiều cao tổng
    _dim_v(fig, dim_x_right, 0, H, f"H={H}mm", offset=40)
    # Cánh trên
    _dim_v(fig, dim_x_right, H - ct, H, f"H_ct={ct}mm", offset=80)
    # Bụng
    y_web_bot = cd + vdh
    y_web_top = H - ct - hah
    _dim_v(fig, dim_x_right, y_web_bot, y_web_top,
           f"H_b={y_web_top - y_web_bot}mm", offset=80)
    # Cánh dưới
    _dim_v(fig, dim_x_right, 0, cd + vdh,
           f"H_cd={cd + vdh}mm", offset=80)

    # Bề rộng cánh trên
    _dim_h(fig, H + H * 0.05, -hf, hf, f"B={mc['B_canh_tren']}mm", offset=0)
    # Bề rộng cánh dưới
    _dim_h(fig, -H * 0.06, -wo, wo, f"B_cd={mc['B_canh_duoi']}mm", offset=0)
    # Bề rộng khoang rỗng (tại đỉnh)
    _dim_h(fig, y_web_top, -vi_t, vi_t,
           f"B_rỗng(trên)={mc['B_rong_tren']}mm", offset=0)
    # Bề rộng khoang rỗng (tại đáy)
    _dim_h(fig, y_web_bot, -vi_b, vi_b,
           f"B_rỗng(dưới)={mc['B_rong_duoi']}mm",
           color="#8e44ad", offset=0)

    # Chiều dày bụng (tại giữa)
    y_mid_web = (y_web_bot + y_web_top) / 2
    b_mid = (mc["B_bung_top"] + mc["B_bung_bot"]) // 2
    _dim_h(fig, y_mid_web, vi_t, wo, f"t={b_mid}mm",
           color="#27ae60", offset=0)

    # ── 5. Layout ─────────────────────────────────────────────────────────────
    all_x = ox + vx + [-hf - 200, hf + 200]
    all_y = oy + vy + [-H * 0.15, H * 1.15]
    _apply_equal_axis(fig, all_x, all_y, margin_pct=0.08)

    # Nhãn vật liệu
    fig.add_annotation(
        x=0, y=H / 2,
        text="<b>BTCT<br>DƯL</b>",
        showarrow=False, font=dict(size=9, color=_CLR["concrete_e"]),
        xanchor="center", yanchor="middle",
    )
    fig.add_annotation(
        x=0, y=(y_web_bot + y_web_top) / 2,
        text="<i>Khoang<br>rỗng</i>",
        showarrow=False, font=dict(size=8, color=_CLR["void_e"]),
        xanchor="center", yanchor="middle",
    )

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# draw_supert_BB
# ─────────────────────────────────────────────────────────────────────────────

def draw_supert_BB(geo, title=None):
    """
    Mặt cắt B-B đầu dầm tại mố — tiết diện đặc hoàn toàn, không khoang rỗng.
    """
    bb = geo["MC_BB"]
    H  = bb["H"]
    B  = geo["MC_AA"]["B_canh_tren"]   # same top flange width as A-A
    hf = B // 2
    # Bottom flange width same as A-A
    wo = geo["MC_AA"]["web_out_hw"]
    mc = geo["MC_AA"]

    fig = go.Figure()
    fig.update_layout(**_LAYOUT_DEFAULTS,
                      title=dict(text=title or
                                 f"Mặt cắt B-B — Đầu dầm tại mố (Đoạn đặc L={bb['L_dau_dac']}mm)",
                                 x=0.5, font=dict(size=13)))

    # Outer polygon = same shape as A-A but WITHOUT void
    ox, oy = _supert_outer_polygon_full(mc, H)
    _poly(fig, ox, oy, _CLR["solid_end"], _CLR["solid_e"],
          "Tiết diện đặc đầu dầm", lw=2)

    _vline(fig, 0, -H * 0.06, H * 1.07, "TIM DẦM", dash="dashdot",
           color="#95a5a6")

    # Kích thước
    _dim_v(fig, hf + 60, 0, H, f"H={H}mm", offset=40)
    _dim_h(fig, H + H * 0.05, -hf, hf, f"B={B}mm", offset=0)
    _dim_h(fig, -H * 0.06, -wo, wo, f"B_cd={mc['B_canh_duoi']}mm", offset=0)

    fig.add_annotation(
        x=0, y=H / 2,
        text="<b>BTCT ĐẶC<br>(Đầu dầm)</b>",
        showarrow=False, font=dict(size=9, color=_CLR["solid_e"]),
        xanchor="center", yanchor="middle",
    )
    fig.add_annotation(
        x=hf * 1.3, y=H * 0.3,
        text=f"⬅ Đoạn đặc<br>L_dầu = {bb['L_dau_dac']}mm",
        showarrow=True, arrowhead=2, ax=-40, ay=0,
        font=dict(size=8, color=_CLR["dim"]),
        bgcolor=_CLR["annot_bg"],
    )

    all_x = ox + [-hf - 200, hf + 200]
    all_y = oy + [-H * 0.15, H * 1.15]
    _apply_equal_axis(fig, all_x, all_y, margin_pct=0.08)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# draw_supert_CC
# ─────────────────────────────────────────────────────────────────────────────

def draw_supert_CC(geo, title=None):
    """
    Mặt cắt C-C đầu dầm tại trụ giữa — cánh trên thu hẹp, đáy đặc.
    """
    cc  = geo["MC_CC"]
    mc  = geo["MC_AA"]
    H   = cc["H"]
    B_t = cc["B_tren"]          # cánh trên thu hẹp ≈1020mm
    B_d = cc["B_duoi"]          # cánh dưới ≈1020mm (bằng B_canh_duoi A-A)
    H_ct_cc = cc["H_canh_tren_CC"]   # cánh trên dày hơn ≈300mm
    hf_top = B_t // 2
    hf_bot = B_d // 2

    fig = go.Figure()
    fig.update_layout(**_LAYOUT_DEFAULTS,
                      title=dict(text=title or
                                 f"Mặt cắt C-C — Đầu dầm tại trụ (B_trên={B_t}mm, H_ct={H_ct_cc}mm)",
                                 x=0.5, font=dict(size=13)))

    # Polygon hình thang cụt (trapezoidal cross-section, taper top to bottom)
    # C-C: cánh trên thu hẹp → trung gian giữa A-A (rỗng) và B-B (đặc)
    # Shape: cánh trên B_t rộng, phần thân/đáy B_d rộng
    vat = 50   # mm chamfer at corners
    xs = [
        -hf_top - vat,  hf_top + vat,   # top outer
         hf_top,         hf_top,         # ... (chamfer transition)
         hf_bot,         hf_bot,         # bottom right
        -hf_bot,        -hf_bot,         # bottom left
        -hf_top,        -hf_top - vat,   # back to top
    ]
    ys = [
        H - H_ct_cc,    H - H_ct_cc,    # base of top thick flange
        H - H_ct_cc,    0,              # right side going down (no taper shown simply as vertical)
        0,               0,
        0,               0,
        0,               H - H_ct_cc,
    ]

    # Simpler trapezoidal shape for C-C:
    # top flange: B_t wide, H_ct_cc tall at top
    # body: transitions to B_d at bottom (if B_d > B_t, it flares; if same, vertical)
    ht_top = H - H_ct_cc      # height of web portion below top flange
    xs = [
        -hf_top, hf_top, hf_top, hf_bot, hf_bot, -hf_bot, -hf_bot, -hf_top,
    ]
    ys = [
        H, H, H - H_ct_cc, H - H_ct_cc - 20, 0, 0, H - H_ct_cc - 20, H - H_ct_cc,
    ]

    _poly(fig, xs, ys, _CLR["solid_end"], _CLR["solid_e"],
          "Mặt cắt C-C", lw=2)

    _vline(fig, 0, -H * 0.06, H * 1.07, "TIM DẦM", dash="dashdot",
           color="#95a5a6")

    _dim_v(fig, hf_bot + 60, 0, H, f"H={H}mm", offset=40)
    _dim_h(fig, H + H * 0.05, -hf_top, hf_top, f"B_trên={B_t}mm")
    _dim_h(fig, -H * 0.06, -hf_bot, hf_bot, f"B_dưới={B_d}mm")
    _dim_v(fig, hf_bot + 60, H - H_ct_cc, H, f"H_ct={H_ct_cc}mm", offset=80)

    fig.add_annotation(
        x=0, y=H / 2,
        text="<b>Tiết diện C-C<br>(Đầu trụ)</b>",
        showarrow=False, font=dict(size=9, color=_CLR["solid_e"]),
        xanchor="center", yanchor="middle",
    )

    all_x = xs + [-hf_bot - 200, hf_bot + 200]
    all_y = ys + [-H * 0.15, H * 1.15]
    _apply_equal_axis(fig, all_x, all_y, margin_pct=0.10)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# draw_supert_longitudinal
# ─────────────────────────────────────────────────────────────────────────────

def draw_supert_longitudinal(geo, title=None):
    """
    Mặt cắt dọc tổng thể dầm Super-T.

    Thể hiện:
    - Đoạn đặc đầu dầm (B-B zone, 750mm mỗi đầu)
    - Phần rỗng giữa nhịp (A-A zone)
    - Đường cong cáp DUL parabol
    - Vị trí mặt cắt A-A, B-B chú thích đường dóng
    """
    L   = geo["L"]   # mm
    H   = geo["H"]   # mm
    bb  = geo["MC_BB"]
    mc  = geo["MC_AA"]
    cap = geo.get("cap_DUL", {})

    L_dau   = bb["L_dau_dac"]    # 750mm
    wo      = mc["web_out_hw"]   # ≈510 → half-width outer web
    cd      = mc["H_canh_duoi"]
    vdh     = mc["H_vat_canh_duoi"]
    ct      = mc["H_canh_tren"]
    hah     = mc["H_vat_canh_tren"]
    y_void_bot = cd + vdh
    y_void_top = H - ct - hah

    fig = go.Figure()
    fig.update_layout(
        **_LAYOUT_DEFAULTS,
        title=dict(text=title or
                   f"Mặt cắt dọc Super-T L={L/1000:.1f}m, H={H}mm",
                   x=0.5, font=dict(size=13)),
    )

    # ── Outer dầm (full length) ───────────────────────────────────────────────
    # Upper face: y = H (flat top)
    # Lower face: y = 0 (flat bottom)
    xs_outer = [0, L, L, 0]
    ys_outer = [0, 0, H, H]
    _poly(fig, xs_outer, ys_outer, _CLR["concrete"], _CLR["concrete_e"],
          "Dầm Super-T", lw=2)

    # ── Vùng rỗng giữa nhịp ──────────────────────────────────────────────────
    # Khoang rỗng đi từ x=L_dau đến x=L-L_dau, y=y_void_bot..y_void_top
    xs_void = [L_dau,      L - L_dau, L - L_dau, L_dau]
    ys_void = [y_void_bot, y_void_bot, y_void_top, y_void_top]
    _poly(fig, xs_void, ys_void, _CLR["void_bg"], _CLR["void_e"],
          "Khoang rỗng (nhịp giữa)", lw=1.5, dash="dot")

    # ── Đường cong cáp DUL (parabol) ─────────────────────────────────────────
    # Cáp thấp nhất tại gối (đầu dầm) và cao nhất tại giữa nhịp
    # e_goi = 50mm từ đáy ; e_giua = (cd + 50)mm từ đáy (trong cánh dưới và ra vùng rỗng)
    n_cap = cap.get("so_ong", 9)
    e_goi  = 80       # eccentricity at support (from bottom), mm
    e_giua = max(cd + 120, H * 0.40)   # at midspan (cable is high here)
    # Parabol: y = e_goi + (e_giua - e_goi) * 4*(x/L)*(1 - x/L)
    n_pts  = 60
    cap_xs = [L * i / (n_pts - 1) for i in range(n_pts)]
    cap_ys = [e_goi + (e_giua - e_goi) * 4 * (x / L) * (1 - x / L)
              for x in cap_xs]

    fig.add_trace(go.Scatter(
        x=cap_xs, y=cap_ys,
        mode="lines",
        line=dict(color=_CLR["cable"], width=2.5, dash="solid"),
        name=f"Cáp DUL ({n_cap} ống Ø{cap.get('ong_PVC_D', 49)}mm)",
        showlegend=True,
        hovertemplate="Cáp DUL: x=%{x:.0f}mm, y=%{y:.0f}mm<extra></extra>",
    ))

    # ── Đường gióng vị trí mặt cắt ───────────────────────────────────────────
    for x_sec, label in [
        (L_dau,         "B-B"),
        (L / 2,         "A-A"),
        (L - L_dau,     "B-B"),
    ]:
        _vline(fig, x_sec, -H * 0.12, H * 1.12, label,
               color="#c0392b", dash="dashdot")

    # ── Kích thước ─────────────────────────────────────────────────────────────
    _dim_h(fig, -H * 0.08, 0, L, f"L = {L/1000:.1f} m = {L} mm", offset=0)
    _dim_h(fig, -H * 0.16, 0, L_dau, f"L_đặc={L_dau}mm",
           color="#8e44ad", offset=0)
    _dim_h(fig, -H * 0.16, L - L_dau, L, f"L_đặc={L_dau}mm",
           color="#8e44ad", offset=0)
    _dim_v(fig, L + L * 0.04, 0, H, f"H={H}mm", offset=0)
    _dim_v(fig, L + L * 0.04, y_void_bot, y_void_top,
           f"H_rỗng={y_void_top - y_void_bot}mm",
           color="#27ae60", offset=40)

    # Chú thích eccentricity cáp
    fig.add_annotation(
        x=L / 2, y=e_giua,
        text=f"<b>Cáp giữa nhịp<br>e={e_giua:.0f}mm từ đáy</b>",
        showarrow=True, arrowhead=2, ax=60, ay=-30,
        font=dict(size=8, color=_CLR["cable"]),
        bgcolor=_CLR["annot_bg"],
    )
    fig.add_annotation(
        x=L_dau / 2, y=e_goi,
        text=f"Cáp tại gối<br>e={e_goi}mm",
        showarrow=True, arrowhead=2, ax=40, ay=-30,
        font=dict(size=8, color=_CLR["cable"]),
        bgcolor=_CLR["annot_bg"],
    )

    fig.update_xaxes(title_text="mm (dọc dầm)", showgrid=True,
                     gridcolor="#e8ede8", tickformat=",d")
    fig.update_yaxes(title_text="mm (đứng)", showgrid=True,
                     gridcolor="#e8ede8", tickformat=",d",
                     scaleanchor="x", scaleratio=1)
    fig.update_layout(showlegend=True,
                      legend=dict(x=0.01, y=0.99, bgcolor=_CLR["annot_bg"]))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# draw_dam_I
# ─────────────────────────────────────────────────────────────────────────────

def draw_dam_I(geo, title=None):
    """Mặt cắt dầm I tiêu chuẩn (cánh trên = cánh dưới, bụng hẹp giữa)."""
    mc = geo["MC_AA"]
    H  = geo["H"]
    ct  = mc["H_canh_tren"]
    cd  = mc["H_canh_duoi"]
    hf  = mc["B_canh_tren"] // 2   # top flange half-width
    bf  = mc["B_canh_duoi"] // 2   # bottom flange half-width
    bw  = mc["B_bung"] // 2        # web half-width
    vt  = mc["B_vat_canh_tren"]    # top chamfer
    vb  = mc["B_vat_canh_duoi"]    # bottom chamfer
    hvt = mc["H_vat_canh_tren"]
    hvb = mc["H_vat_canh_duoi"]

    # 12-point I-beam polygon (right half mirrored)
    y5 = H - ct           # bottom of top flange
    y4 = H - ct - hvt     # end of top chamfer
    y3 = cd + hvb         # start of bottom chamfer
    y2 = cd               # top of bottom flange body
    xs = [
        -hf,     hf,      # top flange top
         hf,     hf - vt, # top flange bottom-outer, chamfer start
         bw,     bw,      # web right (top, bottom)
         bw,     bf,      # chamfer to bottom flange
         bf,    -bf,      # bottom flange bottom
        -bf,    -bf,      # bottom flange left
        -bw,    -bw,      # web left (bottom, top)
        -(hf-vt), -hf,    # top chamfer left
    ]
    ys = [
        H, H,
        y5, y5,
        y4, y3,
        y2, y2,
        0, 0,
        y2, y3,
        y4, y5,
        y5, H,
    ]

    fig = go.Figure()
    fig.update_layout(**_LAYOUT_DEFAULTS,
                      title=dict(text=title or f"Mặt cắt Dầm I — H={H}mm",
                                 x=0.5, font=dict(size=13)))
    _poly(fig, xs, ys, _CLR["concrete"], _CLR["concrete_e"],
          "Dầm I BTCT DUL", lw=2)
    _vline(fig, 0, -H * 0.06, H * 1.07, "TIM", dash="dashdot",
           color="#95a5a6")

    _dim_v(fig, hf + 60, 0, H, f"H={H}mm", offset=40)
    _dim_v(fig, hf + 60, 0, cd, f"cd={cd}mm", offset=80)
    _dim_v(fig, hf + 60, H - ct, H, f"ct={ct}mm", offset=80)
    _dim_h(fig, H + H * 0.05, -hf, hf, f"B_ct={mc['B_canh_tren']}mm")
    _dim_h(fig, -H * 0.07, -bf, bf, f"B_cd={mc['B_canh_duoi']}mm",
           color="#8e44ad")
    _dim_h(fig, H / 2, -bw, bw, f"t_bụng={mc['B_bung']}mm",
           color="#27ae60")

    fig.add_annotation(x=0, y=H / 2, text="<b>BTCT<br>DƯL</b>",
                       showarrow=False, font=dict(size=9, color=_CLR["concrete_e"]),
                       xanchor="center", yanchor="middle")

    all_x = xs + [-hf - 150, hf + 150]
    all_y = ys + [-H * 0.15, H * 1.15]
    _apply_equal_axis(fig, all_x, all_y)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# draw_t_nguoc
# ─────────────────────────────────────────────────────────────────────────────

def draw_t_nguoc(geo, title=None):
    """
    Mặt cắt T ngược: bụng hẹp TRÊN, cánh rộng ĐÁY.
    Bê tông đổ tại chỗ giữa các dầm điền vào phần bụng.
    """
    mc  = geo["MC_AA"]
    H   = geo["H"]
    bw  = mc["B_bung"] // 2         # web half-width ≈100
    hb  = mc["H_bung"]              # web height
    bf  = mc["B_canh_duoi"] // 2    # bottom flange half-width ≈490
    cd  = mc["H_canh_duoi"]
    vb  = mc["B_vat_canh_duoi"]
    hvb = mc["H_vat_canh_duoi"]

    y_flange_top  = cd              # đỉnh cánh dưới phẳng
    y_vat_top     = cd + hvb        # sau vát chuyển tiếp lên bụng

    xs = [
        -bw,     bw,     bw,         bf,       bf,      -bf,    -bf,     -bw,
    ]
    ys = [
        H,       H,      y_vat_top,  y_flange_top, 0,   0,   y_flange_top, y_vat_top,
    ]

    fig = go.Figure()
    fig.update_layout(**_LAYOUT_DEFAULTS,
                      title=dict(text=title or f"Mặt cắt T ngược — H={H}mm",
                                 x=0.5, font=dict(size=13)))
    _poly(fig, xs, ys, _CLR["concrete"], _CLR["concrete_e"],
          "Dầm T ngược BTCT DUL", lw=2)
    _vline(fig, 0, -H * 0.06, H * 1.07, "TIM", dash="dashdot",
           color="#95a5a6")

    _dim_v(fig, bf + 50, 0, H, f"H={H}mm", offset=30)
    _dim_v(fig, bf + 50, 0, cd, f"H_cd={cd}mm", offset=70)
    _dim_h(fig, H + H * 0.05, -bf, bf, f"B={mc['B_canh_duoi']}mm")
    _dim_h(fig, H * 0.6, -bw, bw, f"B_bụng={mc['B_bung']}mm",
           color="#27ae60")

    all_x = xs + [-bf - 100, bf + 100]
    all_y = ys + [-H * 0.15, H * 1.15]
    _apply_equal_axis(fig, all_x, all_y)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# draw_dam_ban_rong
# ─────────────────────────────────────────────────────────────────────────────

def draw_dam_ban_rong(geo, title=None):
    """
    Mặt cắt dầm bản rỗng: hộp phẳng với các lỗ rỗng tròn bên trong.
    """
    mc  = geo["MC_AA"]
    H   = geo["H"]
    B   = mc["B_canh_tren"]          # full beam width
    D   = mc.get("B_rong", 300)      # hole diameter
    n   = mc.get("so_rong", 3)
    kc  = mc.get("kc_rong", 330)     # c-c spacing of holes
    y_c = mc.get("y_rong", H // 2)   # centroid y of holes from bottom

    fig = go.Figure()
    fig.update_layout(**_LAYOUT_DEFAULTS,
                      title=dict(text=title or
                                 f"Mặt cắt Dầm bản rỗng — H={H}mm, B={B}mm",
                                 x=0.5, font=dict(size=13)))

    # Outer rectangle
    hb = B // 2
    _poly(fig, [-hb, hb, hb, -hb], [0, 0, H, H],
          _CLR["concrete"], _CLR["concrete_e"], "Dầm bản rỗng", lw=2)

    # Circular holes (approximate with polygon)
    x_start = -(n - 1) * kc / 2
    for i in range(n):
        xc = x_start + i * kc
        theta = [math.radians(a) for a in range(0, 361, 10)]
        hxs = [xc + (D / 2) * math.cos(t) for t in theta]
        hys = [y_c + (D / 2) * math.sin(t) for t in theta]
        _poly(fig, hxs, hys, _CLR["void_bg"], _CLR["void_e"],
              "Lỗ rỗng" if i == 0 else "", lw=1)

    _vline(fig, 0, -H * 0.06, H * 1.07, "TIM", dash="dashdot",
           color="#95a5a6")
    _dim_v(fig, hb + 50, 0, H, f"H={H}mm", offset=30)
    _dim_h(fig, H + H * 0.05, -hb, hb, f"B={B}mm")
    _dim_h(fig, y_c, -D // 2, D // 2, f"Ø={D}mm", color="#8e44ad")

    all_x = [-hb - 100, hb + 100]
    all_y = [-H * 0.15, H * 1.15]
    _apply_equal_axis(fig, all_x, all_y)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# draw_dam_T
# ─────────────────────────────────────────────────────────────────────────────

def draw_dam_T(geo, title=None):
    """Mặt cắt Dầm T: cánh trên rộng, bụng đứng phía dưới."""
    mc  = geo["MC_AA"]
    H   = geo["H"]
    ct  = mc["H_canh_tren"]
    hf  = mc["B_canh_tren"] // 2
    bw  = mc["B_bung"] // 2
    vt  = mc["B_vat_canh_tren"]
    hvt = mc["H_vat_canh_tren"]

    y_bot_ct = H - ct     # base of top flange
    y_vat    = H - ct - hvt

    xs = [
        -hf,    hf,     hf,     hf - vt,
         bw,    bw,    -bw,    -bw,
        -(hf - vt), -hf,
    ]
    ys = [
        H,      H,      H - ct, y_vat,
        y_vat,  0,      0,      y_vat,
        y_vat,  H - ct,
    ]

    fig = go.Figure()
    fig.update_layout(**_LAYOUT_DEFAULTS,
                      title=dict(text=title or f"Mặt cắt Dầm T — H={H}mm",
                                 x=0.5, font=dict(size=13)))
    _poly(fig, xs, ys, _CLR["concrete"], _CLR["concrete_e"],
          "Dầm T BTCT DUL", lw=2)
    _vline(fig, 0, -H * 0.06, H * 1.07, "TIM", dash="dashdot",
           color="#95a5a6")

    _dim_v(fig, hf + 50, 0, H, f"H={H}mm", offset=30)
    _dim_v(fig, hf + 50, H - ct, H, f"H_ct={ct}mm", offset=70)
    _dim_h(fig, H + H * 0.05, -hf, hf, f"B={mc['B_canh_tren']}mm")
    _dim_h(fig, H * 0.3, -bw, bw, f"B_bụng={mc['B_bung']}mm",
           color="#27ae60")

    all_x = xs + [-hf - 100, hf + 100]
    all_y = ys + [-H * 0.15, H * 1.15]
    _apply_equal_axis(fig, all_x, all_y)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def draw_beam_section(loai_dam: str, geo: dict, section: str = "AA"):
    """
    Dispatcher: chọn đúng hàm vẽ theo loại dầm và ký hiệu mặt cắt.

    Parameters
    ----------
    loai_dam : str  — "Super-T", "Dầm I", "T ngược", "Dầm bản rỗng", "Dầm T"
    geo      : dict — từ get_beam_geometry_detail()
    section  : str  — "AA" | "BB" | "CC" | "doc" (chỉ dùng cho Super-T)

    Returns
    -------
    plotly.graph_objects.Figure or None
    """
    if geo is None:
        return None
    ll = loai_dam.lower()
    if "super" in ll:
        if section == "BB":
            return draw_supert_BB(geo)
        if section == "CC":
            return draw_supert_CC(geo)
        if section == "doc":
            return draw_supert_longitudinal(geo)
        return draw_supert_AA(geo)   # default AA
    if "dầm i" in ll or "dam i" in ll:
        return draw_dam_I(geo)
    if "t ngược" in ll or "t-ngược" in ll or "tngược" in ll:
        return draw_t_nguoc(geo)
    if "bản rỗng" in ll or "ban rong" in ll:
        return draw_dam_ban_rong(geo)
    if "dầm t" in ll or "dam t" in ll:
        return draw_dam_T(geo)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Quick test khi chạy trực tiếp
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, __file__.replace("06b-Draw_Beam_Sections.py", ""))
    sys.stdout.reconfigure(encoding="utf-8")

    # Lấy geometry từ Module 06
    try:
        from importlib import import_module
        m06 = import_module("06-AI_KetCauNhip".replace("-", "_"))
        get_detail = m06.get_beam_geometry_detail
    except Exception:
        import importlib.util, os
        spec = importlib.util.spec_from_file_location(
            "m06",
            os.path.join(os.path.dirname(__file__), "06-AI_KetCauNhip.py")
        )
        m06 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m06)
        get_detail = m06.get_beam_geometry_detail

    geo = get_detail("Super-T", 38.2)
    assert geo is not None, "Không tìm thấy geometry Super-T 38.2m"

    mc = geo["MC_AA"]
    print("=== Super-T 38.2m — MC_AA ===")
    for k, v in mc.items():
        print(f"  {k:<25}: {v}")

    print("\n=== Outer polygon A-A (mm) ===")
    ox, oy = _supert_outer_polygon_full(mc, geo["H"])
    for i, (x, y) in enumerate(zip(ox, oy)):
        print(f"  P{i+1:02d}: ({x:+7.0f}, {y:+7.0f})")

    print("\n=== Void polygon A-A (mm) ===")
    vx, vy = _supert_void_polygon(mc, geo["H"])
    for i, (x, y) in enumerate(zip(vx, vy)):
        print(f"  V{i+1}: ({x:+7.0f}, {y:+7.0f})")

    # Vẽ và lưu HTML
    fig_aa  = draw_supert_AA(geo)
    fig_bb  = draw_supert_BB(geo)
    fig_cc  = draw_supert_CC(geo)
    fig_doc = draw_supert_longitudinal(geo)
    fig_I   = draw_dam_I(get_detail("Dầm I", 33.0))
    fig_tn  = draw_t_nguoc(get_detail("T ngược", 15.0))
    fig_br  = draw_dam_ban_rong(get_detail("Dầm bản rỗng", 18.0))

    out = os.path.dirname(os.path.abspath(__file__))
    for name, fig in [
        ("test_AA.html",  fig_aa),
        ("test_BB.html",  fig_bb),
        ("test_CC.html",  fig_cc),
        ("test_doc.html", fig_doc),
        ("test_I.html",   fig_I),
        ("test_TN.html",  fig_tn),
        ("test_BR.html",  fig_br),
    ]:
        path = os.path.join(out, name)
        fig.write_html(path)
        print(f"Wrote {path}")

    print("\nDone — mở các file HTML để kiểm tra trực quan.")
