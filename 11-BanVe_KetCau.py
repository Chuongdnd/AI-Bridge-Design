"""
Module 11 — Bản vẽ kết cấu cầu (2D + 3D)
Tất cả hình vẽ tạo từ design_data — không cần dữ liệu khảo sát.

Hàm xuất:
  ve_so_do_nhip_2d(d)      — Sơ đồ nhịp / trắc dọc sơ bộ
  ve_mat_cat_ngang_2d(d)   — MCN điển hình đầy đủ (dầm + bản + lớp phủ + lan can)
  ve_mat_dung_tru_2d(d)    — Mặt đứng trụ cầu 2D với kích thước
  ve_cau_3d(d)             — Mô hình 3D toàn cầu (piers + beams + deck)
"""

import numpy as np
import plotly.graph_objects as go

# ── Bảng màu ─────────────────────────────────────────────────────────────────
_C = {
    "btong":    "#c8d6c0",   # bê tông xám nhạt xanh
    "btong_dk": "#7f8c8d",   # bê tông viền
    "be":       "#aab7b8",   # bệ cọc
    "be_dk":    "#566573",
    "dam":      "#85929e",   # dầm
    "dam_dk":   "#2c3e50",
    "ban":      "#d5d8dc",   # bản mặt cầu
    "phu":      "#2c3e50",   # lớp phủ nhựa
    "lan_can":  "#7f8c8d",   # lan can
    "nuoc":     "rgba(52,152,219,0.35)",
    "dat":      "rgba(169,120,74,0.4)",
    "tk":       "rgba(231,76,60,0.12)",
    "tk_line":  "#e74c3c",
    "moc":      "#c0a06b",   # mố
    "dim":      "#5d6d7e",
}

# ── Helper: vẽ polygon ────────────────────────────────────────────────────────
def _poly(fig, xs, ys, fill, line_c, name="", opacity=1.0, showlegend=None, lw=1.5):
    sl = (name != "") if showlegend is None else showlegend
    xs = list(xs); ys = list(ys)
    fig.add_trace(go.Scatter(
        x=xs + [xs[0]], y=ys + [ys[0]],
        fill="toself", fillcolor=fill, opacity=opacity,
        line=dict(color=line_c, width=lw),
        mode="lines", name=name, showlegend=sl,
        hovertemplate=(f"<b>{name}</b><extra></extra>" if name else None),
    ))

def _hline(fig, y, x0, x1, label, color, dash="dot", lw=1.5):
    fig.add_shape(type="line", x0=x0, y0=y, x1=x1, y1=y,
                  line=dict(color=color, width=lw, dash=dash))
    if label:
        fig.add_annotation(x=(x0+x1)/2, y=y, text=f" {label}", showarrow=False,
                           font=dict(size=8, color=color), xanchor="left", yanchor="bottom")

def _dim_h(fig, y, x0, x1, text, color=_C["dim"], dy=0.4):
    """Dimension annotation ngang."""
    ya = y + dy
    fig.add_shape(type="line", x0=x0, y0=ya-0.15, x1=x0, y1=ya+0.15,
                  line=dict(color=color, width=1))
    fig.add_shape(type="line", x0=x1, y0=ya-0.15, x1=x1, y1=ya+0.15,
                  line=dict(color=color, width=1))
    fig.add_shape(type="line", x0=x0, y0=ya, x1=x1, y1=ya,
                  line=dict(color=color, width=1))
    fig.add_annotation(x=(x0+x1)/2, y=ya + 0.1, text=text, showarrow=False,
                       font=dict(size=8, color=color), yanchor="bottom",
                       bgcolor="rgba(255,255,255,0.8)")

def _dim_v(fig, x, y0, y1, text, color=_C["dim"], dx=0.6):
    xa = x + dx
    fig.add_shape(type="line", x0=xa-0.15, y0=y0, x1=xa+0.15, y1=y0,
                  line=dict(color=color, width=1))
    fig.add_shape(type="line", x0=xa-0.15, y0=y1, x1=xa+0.15, y1=y1,
                  line=dict(color=color, width=1))
    fig.add_shape(type="line", x0=xa, y0=y0, x1=xa, y1=y1,
                  line=dict(color=color, width=1))
    fig.add_annotation(x=xa+0.05, y=(y0+y1)/2, text=text, showarrow=False,
                       font=dict(size=8, color=color), xanchor="left",
                       bgcolor="rgba(255,255,255,0.8)")

# ── Box mesh 3D ───────────────────────────────────────────────────────────────
def _box3d(x0, y0, z0, x1, y1, z1, color="#bdc3c7", opacity=0.88, name="", sl=True):
    """Box từ góc (x0,y0,z0) đến (x1,y1,z1)."""
    vx = [x0,x1,x1,x0, x0,x1,x1,x0]
    vy = [y0,y0,y1,y1, y0,y0,y1,y1]
    vz = [z0,z0,z0,z0, z1,z1,z1,z1]
    # 12 tam giác (6 mặt)
    ii = [0,0, 4,4, 0,0, 3,3, 0,0, 1,1]
    jj = [1,2, 5,6, 1,5, 2,6, 3,7, 2,6]
    kk = [2,3, 6,7, 5,4, 6,7, 7,4, 6,5]
    return go.Mesh3d(
        x=vx, y=vy, z=vz, i=ii, j=jj, k=kk,
        color=color, opacity=opacity,
        name=name, showlegend=sl and bool(name),
        flatshading=True,
        lighting=dict(ambient=0.65, diffuse=0.85, specular=0.2),
        hovertemplate=f"<b>{name}</b><extra></extra>" if name else None,
    )


# ===========================================================================
# 1. SƠ ĐỒ BỐ TRÍ NHỊP (2D — mặt phẳng dọc cầu)
# ===========================================================================
def ve_so_do_nhip_2d(d):
    """
    Vẽ sơ đồ nhịp (profile view) từ design_data.
    Hiển thị: mố, trụ, dầm, bản, mực nước, tĩnh không, dimension.
    """
    kcn = d.get("kcn_result") or d.get("ai_result", {})
    geo = d.get("geo_logic", {})

    n_nhip  = int(kcn.get("tong_so_nhip", 3))
    L_nhip  = float(kcn.get("chieu_dai", 40))
    H_dam   = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    loai    = str(kcn.get("loai_dam", "Dầm I"))
    L_cau   = float(geo.get("L_cau", n_nhip * L_nhip))
    t_ban   = float(d.get("t_ban_mm", 200)) / 1000.0
    H_tru   = float(d.get("H_tru_est", 5.0))
    cao_dd  = float(d.get("cao_day_dam", H_tru + 5.0))
    h_tn    = float(d.get("h_tn_tb", 2.0))
    MNCN    = float(d.get("MNCN", 3.5))
    MNTT    = float(d.get("MNTT", 2.0))
    MNTN    = float(d.get("MNTN", 0.5))
    B_tk    = float(d.get("B", 20.0))
    H_tk    = float(d.get("H", 3.0))
    x_tim   = float(geo.get("x_tim_clearance", 0))

    x0 = -L_cau / 2

    # Cao độ tuyệt đối các cấu kiện
    z_deck   = cao_dd + H_dam + t_ban   # mặt đường xe chạy
    z_cap_t  = cao_dd                    # đỉnh xà mũ = đáy dầm
    z_cap_b  = cao_dd - 0.80            # đáy xà mũ
    z_sh_b   = z_cap_b - H_tru          # đáy thân trụ
    z_be_t   = z_sh_b                   # đỉnh bệ cọc
    z_be_b   = z_sh_b - 1.50           # đáy bệ cọc
    z_min    = min(z_be_b - 0.5, MNTN - 0.5, h_tn - 0.5)

    W_cap = max(2.0, L_nhip * 0.05 + 1.0)  # bán rộng xà mũ
    W_tru = 1.2    # bề rộng thân trụ
    W_be  = W_cap + 0.8
    W_mo  = 3.0    # bề rộng mố

    mg = max(15, L_nhip * 0.25)
    fig = go.Figure()

    # ── Nền đất ──────────────────────────────────────────────────────────
    _poly(fig,
        [x0-mg, x0+L_cau+mg, x0+L_cau+mg, x0-mg],
        [h_tn, h_tn, z_min-0.2, z_min-0.2],
        _C["dat"], "rgba(0,0,0,0)", "Nền đất", showlegend=False)
    _hline(fig, h_tn, x0-mg, x0+L_cau+mg, f"CĐTN trung bình = {h_tn:.2f}m",
           "#27ae60", dash="dash")

    # ── Mực nước ─────────────────────────────────────────────────────────
    _poly(fig,
        [x0+W_mo, x0+L_cau-W_mo, x0+L_cau-W_mo, x0+W_mo],
        [MNTN, MNTN, MNCN, MNCN],
        _C["nuoc"], "rgba(0,0,0,0)", "", showlegend=False)
    for y_w, lbl, clr in [
        (MNCN, f"MNCN = {MNCN:.3f}m", "#c0392b"),
        (MNTT, f"MNTT = {MNTT:.3f}m", "#2980b9"),
        (MNTN, f"MNTN = {MNTN:.3f}m", "#1abc9c"),
    ]:
        fig.add_trace(go.Scatter(
            x=[x0+W_mo+1, x0+L_cau-W_mo-1], y=[y_w, y_w],
            mode="lines+text", name=lbl,
            line=dict(color=clr, width=1.5, dash="dot"),
            text=[lbl, ""], textposition="top left",
            textfont=dict(size=8, color=clr)
        ))

    # ── Mố trái / phải ────────────────────────────────────────────────────
    for xm, side, sign in [(x0, "Trái", 1), (x0+L_cau, "Phải", -1)]:
        _poly(fig,
            [xm, xm+sign*W_mo, xm+sign*W_mo, xm],
            [z_be_b, z_be_b, z_deck, z_deck],
            _C["moc"], _C["be_dk"], f"Mố {side}")

    # ── Trụ giữa ─────────────────────────────────────────────────────────
    for i in range(1, n_nhip):
        xt = x0 + i * L_nhip
        sl = (i == 1)
        # Bệ cọc
        _poly(fig,
            [xt-W_be, xt+W_be, xt+W_be, xt-W_be],
            [z_be_b, z_be_b, z_be_t, z_be_t],
            _C["be"], _C["be_dk"], "Bệ cọc" if sl else "", showlegend=sl)
        # Thân trụ
        _poly(fig,
            [xt-W_tru/2, xt+W_tru/2, xt+W_tru/2, xt-W_tru/2],
            [z_sh_b, z_sh_b, z_cap_b, z_cap_b],
            _C["btong"], _C["btong_dk"], f"Thân trụ T{i}", showlegend=sl)
        # Xà mũ
        _poly(fig,
            [xt-W_cap, xt+W_cap, xt+W_cap, xt-W_cap],
            [z_cap_b, z_cap_b, z_cap_t, z_cap_t],
            _C["btong"], _C["dam_dk"], "Xà mũ" if sl else "", showlegend=sl)

    # ── Dầm + Bản mặt cầu ────────────────────────────────────────────────
    for i in range(n_nhip):
        xs = x0 + i * L_nhip
        xe = xs + L_nhip
        sl = (i == 0)
        _poly(fig, [xs, xe, xe, xs], [cao_dd, cao_dd, cao_dd+H_dam, cao_dd+H_dam],
              _C["dam"], _C["dam_dk"], f"Dầm {loai}" if sl else "", showlegend=sl)
        _poly(fig, [xs, xe, xe, xs],
              [cao_dd+H_dam, cao_dd+H_dam, z_deck, z_deck],
              _C["ban"], _C["dam_dk"], "Bản mặt cầu" if sl else "", showlegend=sl)

    # ── Khung tĩnh không ─────────────────────────────────────────────────
    y_tk_bot = MNCN   # tĩnh không tính từ MNCN
    fig.add_shape(type="rect",
        x0=x_tim-B_tk/2, x1=x_tim+B_tk/2,
        y0=y_tk_bot, y1=y_tk_bot+H_tk,
        line=dict(color=_C["tk_line"], width=2),
        fillcolor=_C["tk"])
    fig.add_annotation(x=x_tim, y=y_tk_bot+H_tk/2,
        text=f"<b>TĨNH KHÔNG</b><br>B={B_tk}m × H={H_tk}m",
        showarrow=False, font=dict(size=9, color=_C["tk_line"]),
        bgcolor="rgba(255,255,255,0.7)")

    # ── Dimensions ────────────────────────────────────────────────────────
    dy_dim = z_deck + 0.8
    for i in range(n_nhip):
        xs = x0 + i * L_nhip
        _dim_h(fig, dy_dim, xs, xs + L_nhip, f"L={L_nhip:.1f}m", dy=0)
    _dim_h(fig, dy_dim + 1.2, x0, x0+L_cau,
           f"<b>L_cầu = {L_cau:.1f}m</b>", color="#c0392b", dy=0)

    if n_nhip > 1:
        xt1 = x0 + L_nhip
        _dim_v(fig, xt1 + W_cap + 0.5, z_cap_b, z_cap_t,
               f"cap {0.8:.1f}m", dx=0.3)
        _dim_v(fig, xt1 + W_cap + 1.5, z_sh_b, z_cap_b,
               f"H={H_tru:.1f}m", dx=0.3)

    _dim_v(fig, x0 - W_mo - 1.5, cao_dd, cao_dd+H_dam,
           f"H_dầm={H_dam:.2f}m", dx=0.3)

    # ── Layout ────────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text=f"SƠ ĐỒ BỐ TRÍ NHỊP — {n_nhip} NHỊP × {L_nhip:.1f}m ({loai.upper()})",
            x=0.5, font=dict(size=13)
        ),
        xaxis=dict(title="Lý trình dọc cầu (m)", showgrid=True,
                   gridcolor="#ecf0f1", range=[x0-mg, x0+L_cau+mg]),
        yaxis=dict(title="Cao độ (m)", showgrid=True, gridcolor="#ecf0f1"),
        height=560, template="plotly_white",
        legend=dict(orientation="h", y=-0.18, font=dict(size=9)),
        margin=dict(l=70, r=30, t=70, b=100),
        hovermode="closest",
    )
    return fig


# ===========================================================================
# 2. MẶT CẮT NGANG ĐIỂN HÌNH ĐẦY ĐỦ
# ===========================================================================
def _beam_poly(fig, xc, H, loai, kc, t_ban):
    """Vẽ tiết diện dầm theo loại tại vị trí tim dầm xc."""
    z0 = -t_ban  # đáy bản mặt cầu = đỉnh dầm
    loai_l = loai.lower()

    if "bản" in loai_l:
        # Dầm bản — hình chữ nhật
        hw = kc * 0.48
        _poly(fig, [xc-hw, xc+hw, xc+hw, xc-hw],
              [z0, z0, z0-H, z0-H],
              _C["dam"], _C["dam_dk"], showlegend=False)

    elif "t ngược" in loai_l or "t-ngược" in loai_l:
        # T ngược — cánh rộng dưới, bụng hẹp trên
        fw = min(kc * 0.45, 0.55)   # nửa cánh trên (nhỏ)
        bw = 0.08                    # nửa bụng
        fh = min(H * 0.22, 0.30)    # chiều dày cánh trên
        xs = [xc-fw, xc+fw, xc+fw, xc+bw, xc+bw, xc-bw, xc-bw, xc-fw]
        ys = [z0, z0, z0-fh, z0-fh, z0-H, z0-H, z0-fh, z0-fh]
        _poly(fig, xs, ys, _C["dam"], _C["dam_dk"], showlegend=False)

    elif "super" in loai_l or "super-t" in loai_l:
        # Super-T — cánh dưới rộng, bụng hẹp, cánh trên hẹp
        bf  = min(kc * 0.50, 0.60)  # nửa cánh trên
        bw  = 0.10                   # nửa bụng
        btf = min(kc * 0.48, 0.58)  # nửa cánh dưới
        tf  = min(H * 0.08, 0.12)   # chiều dày cánh (trên & dưới)
        wh  = H - 2 * tf            # chiều cao bụng
        xs = [xc-bf, xc+bf, xc+bf, xc+bw, xc+btf, xc+btf, xc-btf, xc-btf, xc-bw, xc-bf]
        ys = [z0, z0,
              z0-tf, z0-tf,
              z0-tf-wh, z0-H,
              z0-H, z0-tf-wh,
              z0-tf, z0-tf]
        _poly(fig, xs, ys, _C["dam"], _C["dam_dk"], showlegend=False)

    else:
        # Dầm I — cánh trên, bụng, cánh dưới
        tw  = 0.08                   # nửa bụng
        fw  = 0.18                   # nửa cánh
        tf  = min(H * 0.08, 0.10)   # chiều dày cánh
        xs = [xc-fw, xc+fw, xc+fw, xc+tw, xc+fw, xc+fw, xc-fw, xc-fw, xc-tw, xc-fw]
        ys = [z0, z0, z0-tf, z0-tf, z0-H+tf, z0-H, z0-H, z0-H+tf, z0-tf, z0-tf]
        _poly(fig, xs, ys, _C["dam"], _C["dam_dk"], showlegend=False)


def ve_mat_cat_ngang_2d(d):
    """
    Vẽ MCN điển hình: bản mặt cầu, lớp phủ, dầm, lan can, kích thước.
    Trục Y = bề rộng, trục Z = chiều cao (0 = mặt đường).
    """
    kcn    = d.get("kcn_result") or d.get("ai_result", {})
    bc     = float(d.get("bc", 12.0))
    loai   = str(kcn.get("loai_dam", "Dầm I"))
    n_dam  = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
    kc     = float(kcn.get("khoang_cach_dam", 2.2))
    H_dam  = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    oh     = float(kcn.get("overhang", 0.5))
    t_ban  = float(d.get("t_ban_mm", 200)) / 1000.0
    t_phu  = 0.070   # lớp phủ nhựa đường 70mm
    H_lc   = 1.10    # chiều cao lan can
    W_lc   = 0.30    # bề rộng lan can
    W_le   = 0.50    # lề bộ hành

    fig = go.Figure()

    # ── Lớp phủ mặt cầu ──────────────────────────────────────────────────
    _poly(fig, [-bc/2, bc/2, bc/2, -bc/2],
          [t_phu, t_phu, 0, 0],
          _C["phu"], _C["dam_dk"], "Lớp phủ BTN", lw=1)

    # ── Bản mặt cầu ───────────────────────────────────────────────────────
    _poly(fig, [-bc/2, bc/2, bc/2, -bc/2],
          [0, 0, -t_ban, -t_ban],
          _C["ban"], _C["btong_dk"], "Bản mặt cầu")

    # ── Dầm chính ─────────────────────────────────────────────────────────
    x_first = -bc/2 + oh
    _beam_poly(fig, x_first, H_dam, loai, kc, t_ban)
    for i in range(1, n_dam):
        _beam_poly(fig, x_first + i * kc, H_dam, loai, kc, t_ban)
    # Legend dummy
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
        marker=dict(color=_C["dam"], size=10, symbol="square"),
        name=f"Dầm {loai} ({n_dam} dầm)"))

    # ── Lan can ───────────────────────────────────────────────────────────
    for side in [-1, 1]:
        xb = side * bc/2
        xi = xb - side * W_lc
        lc_xs = [xi, xb, xb, xi]
        lc_ys = [t_phu, t_phu, t_phu + H_lc, t_phu + H_lc]
        _poly(fig, lc_xs, lc_ys, _C["lan_can"], "#2c3e50",
              "Lan can" if side == -1 else "", showlegend=(side == -1))

    # ── Dimension annotations ─────────────────────────────────────────────
    z_bot = -t_ban - H_dam
    _dim_h(fig, z_bot - 0.3, -bc/2, bc/2, f"B_cầu = {bc}m", dy=0)
    if n_dam >= 2:
        _dim_h(fig, z_bot - 0.8, x_first, x_first+kc,
               f"@{kc}m (×{n_dam-1})", color="#8e44ad", dy=0)
    _dim_v(fig, bc/2 + 0.3, -t_ban, -t_ban-H_dam, f"H={H_dam}m", dx=0.2)
    _dim_v(fig, bc/2 + 1.0, -t_ban, 0, f"t_bản={int(t_ban*1000)}mm", dx=0.2)
    _dim_v(fig, bc/2 + 1.7, 0, t_phu, f"Lớp phủ {int(t_phu*1000)}mm",
           color="#c0392b", dx=0.2)

    # ── Tim đường ─────────────────────────────────────────────────────────
    for y in np.arange(-bc/2 + W_le + W_lc + 1.5, bc/2 - W_le - W_lc - 0.5, 3.75):
        fig.add_shape(type="line", x0=y, y0=t_phu+0.01, x1=y, y1=t_phu+0.01,
                      line=dict(color="white", width=1, dash="dash"))
    fig.add_shape(type="line", x0=0, y0=t_phu+0.01, x1=0, y1=t_phu+0.01,
                  line=dict(color="yellow", width=1.5, dash="solid"))

    fig.update_layout(
        title=dict(
            text=f"MẶT CẮT NGANG ĐIỂN HÌNH  —  B_cầu={bc}m  |  {n_dam}×{loai}  |  t_bản={int(t_ban*1000)}mm",
            x=0.5, font=dict(size=12)
        ),
        xaxis=dict(title="Bề rộng cầu (m)", showgrid=True, gridcolor="#ecf0f1",
                   range=[-bc/2 - 2.5, bc/2 + 2.5]),
        yaxis=dict(title="Chiều cao (m)", scaleanchor="x", scaleratio=1,
                   showgrid=True, gridcolor="#ecf0f1",
                   range=[-t_ban - H_dam - 1.2, t_phu + H_lc + 0.5]),
        height=520, template="plotly_white",
        legend=dict(orientation="h", y=-0.18, font=dict(size=9)),
        margin=dict(l=70, r=50, t=70, b=100),
    )
    return fig


# ===========================================================================
# 3. MẶT ĐỨNG TRỤ CẦU (2D)
# ===========================================================================
def ve_mat_dung_tru_2d(d):
    """
    Vẽ mặt đứng trụ cầu điển hình (nhìn dọc cầu).
    Hiển thị: bệ cọc, thân trụ (1 mặt), xà mũ, kích thước.
    """
    tru    = d.get("tru_result", {})
    kcn    = d.get("kcn_result") or d.get("ai_result", {})
    bc     = float(d.get("bc", 12.0))
    H_tru  = float(d.get("H_tru_est", 5.0))
    H_dam  = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    t_ban  = float(d.get("t_ban_mm", 200)) / 1000.0
    loai_t = str(tru.get("loai_tru", "Thân cột 2 trụ"))
    mong   = d.get("mong_result", {})
    D_coc  = float(mong.get("D_coc_mm", 600)) / 1000.0 if mong else 0.6

    cap_H  = 0.80  # chiều cao xà mũ
    cap_W  = max(2.0, bc * 0.18 + 1.0)  # nửa bề rộng xà mũ
    be_H   = 1.50  # chiều cao bệ cọc
    be_W   = cap_W + 0.8   # nửa bề rộng bệ cọc

    # Số thân cột
    n_cot = 3 if "3" in loai_t else (2 if ("cột" in loai_t.lower() or "2" in loai_t) else 1)
    W_cot = min(1.2, bc * 0.08 + 0.5)  # bề rộng thân cột

    # Hệ tọa độ: Z=0 tại đáy xà mũ = đỉnh thân
    # Xà mũ:   0..cap_H
    # Thân:    -H_tru..0
    # Bệ cọc: -(H_tru+be_H)..-(H_tru)

    fig = go.Figure()

    # ── Xà mũ ────────────────────────────────────────────────────────────
    _poly(fig, [-cap_W, cap_W, cap_W, -cap_W],
          [0, 0, cap_H, cap_H],
          _C["btong"], _C["dam_dk"], "Xà mũ (cap beam)")

    # ── Thân trụ ─────────────────────────────────────────────────────────
    if n_cot == 1:
        W_don = min(cap_W * 0.7, 1.2)
        _poly(fig, [-W_don, W_don, W_don, -W_don],
              [-H_tru, -H_tru, 0, 0],
              _C["btong"], _C["btong_dk"], "Thân trụ đặc")
    else:
        sp = cap_W * 0.60 / (n_cot - 1) * 2 if n_cot > 1 else 0
        starts = np.linspace(-cap_W * 0.6, cap_W * 0.6, n_cot)
        for i, xc in enumerate(starts):
            _poly(fig, [xc-W_cot/2, xc+W_cot/2, xc+W_cot/2, xc-W_cot/2],
                  [-H_tru, -H_tru, 0, 0],
                  _C["btong"], _C["btong_dk"],
                  f"Thân cột {i+1}" if i == 0 else "", showlegend=(i == 0))

    # ── Bệ cọc ───────────────────────────────────────────────────────────
    _poly(fig, [-be_W, be_W, be_W, -be_W],
          [-H_tru-be_H, -H_tru-be_H, -H_tru, -H_tru],
          _C["be"], _C["be_dk"], "Bệ cọc (pile cap)")

    # ── Cọc (ký hiệu) ─────────────────────────────────────────────────────
    L_coc_est = float(mong.get("L_coc_tu", 35)) if mong else 35
    n_coc_row = 3 if be_W >= 2.5 else 2
    coc_xs = np.linspace(-be_W * 0.7, be_W * 0.7, n_coc_row)
    for xc in coc_xs:
        fig.add_trace(go.Scatter(
            x=[xc, xc], y=[-H_tru-be_H, -H_tru-be_H-L_coc_est],
            mode="lines", line=dict(color=_C["pile"], width=3),
            name="Cọc (ký hiệu)" if xc == coc_xs[0] else "",
            showlegend=(xc == coc_xs[0]),
        ))

    # ── Dimensions ────────────────────────────────────────────────────────
    _dim_h(fig, cap_H + 0.4, -cap_W, cap_W, f"B_xà mũ = {cap_W*2:.1f}m", dy=0)
    _dim_h(fig, -H_tru - be_H - 0.4, -be_W, be_W, f"B_bệ cọc = {be_W*2:.1f}m", dy=0)
    _dim_v(fig, cap_W + 0.5, 0, cap_H, f"cap {cap_H}m", dx=0.2)
    _dim_v(fig, cap_W + 1.3, -H_tru, 0, f"H_trụ={H_tru:.1f}m", dx=0.2)
    _dim_v(fig, cap_W + 2.1, -H_tru-be_H, -H_tru, f"bệ {be_H:.1f}m", dx=0.2)

    # Cọc label
    fig.add_annotation(
        x=coc_xs[-1], y=-H_tru-be_H-L_coc_est/2,
        text=f"Cọc Ø{int(D_coc*1000)}mm<br>L≈{L_coc_est}m",
        showarrow=True, arrowhead=2, ax=30, ay=0,
        font=dict(size=8), bgcolor="white"
    )

    # ── Đường tim ─────────────────────────────────────────────────────────
    fig.add_shape(type="line", x0=0, y0=-H_tru-be_H-2, x1=0, y1=cap_H+0.5,
                  line=dict(color="#aab7b8", width=1, dash="dashdot"))
    fig.add_annotation(x=0, y=cap_H+0.5, text="CL", showarrow=False,
                       font=dict(size=9, color="#aab7b8"))

    # ── Title info ────────────────────────────────────────────────────────
    fig.add_annotation(
        x=0, y=-H_tru-be_H-L_coc_est-0.8,
        text=f"<b>{loai_t.upper()}</b>  |  {mong.get('loai_mong','Cọc') if mong else 'Cọc'}  Ø{int(D_coc*1000)}mm",
        showarrow=False, font=dict(size=9, color=_C["dam_dk"]),
        bgcolor="rgba(255,255,255,0.85)"
    )

    fig.update_layout(
        title=dict(
            text=f"MẶT ĐỨNG TRỤ CẦU — {loai_t.upper()}  |  H_trụ = {H_tru:.1f}m",
            x=0.5, font=dict(size=12)
        ),
        xaxis=dict(title="Bề rộng ngang (m)", showgrid=True, gridcolor="#ecf0f1",
                   range=[-be_W-2.5, be_W+2.5]),
        yaxis=dict(title="Chiều cao (m)", scaleanchor="x", scaleratio=1,
                   showgrid=True, gridcolor="#ecf0f1"),
        height=580, template="plotly_white",
        legend=dict(orientation="h", y=-0.15, font=dict(size=9)),
        margin=dict(l=70, r=50, t=70, b=100),
    )
    return fig


# ===========================================================================
# 4. MÔ HÌNH 3D TOÀN CẦU
# ===========================================================================
def ve_cau_3d(d):
    """
    Mô hình 3D cầu: mố, trụ (xà mũ + thân + bệ), dầm, bản mặt cầu.
    X = dọc cầu, Y = ngang cầu, Z = đứng.
    """
    kcn   = d.get("kcn_result") or d.get("ai_result", {})
    geo   = d.get("geo_logic", {})

    n_nhip = int(kcn.get("tong_so_nhip", 3))
    L_nhip = float(kcn.get("chieu_dai", 40))
    H_dam  = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    n_dam  = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
    kc_dam = float(kcn.get("khoang_cach_dam", 2.2))
    oh     = float(kcn.get("overhang", 0.5))
    L_cau  = float(geo.get("L_cau", n_nhip * L_nhip))
    bc     = float(d.get("bc", 12.0))
    t_ban  = float(d.get("t_ban_mm", 200)) / 1000.0
    H_tru  = float(d.get("H_tru_est", 5.0))
    cao_dd = float(d.get("cao_day_dam", H_tru + 5.0))

    cap_H  = 0.80
    cap_W  = max(2.0, bc * 0.18 + 1.0)
    be_H   = 1.50
    be_W   = cap_W + 0.8
    W_tru  = 1.2
    mo_W   = 3.5

    x0 = -L_cau / 2  # mố trái

    # Cao độ các cấu kiện
    z_deck = cao_dd + H_dam + t_ban
    z_cap_t = cao_dd
    z_cap_b = cao_dd - cap_H
    z_sh_b  = z_cap_b - H_tru
    z_be_t  = z_sh_b
    z_be_b  = z_sh_b - be_H

    traces = []

    # ── Mố trái / phải ────────────────────────────────────────────────────
    for xm, name in [(x0 - mo_W, "Mố trái"), (x0 + L_cau, "Mố phải")]:
        traces.append(_box3d(xm, -bc/2-0.5, z_be_b, xm+mo_W, bc/2+0.5, z_deck,
                             color="#c0a06b", opacity=0.85, name=name))

    # ── Trụ giữa ─────────────────────────────────────────────────────────
    for i in range(1, n_nhip):
        xt = x0 + i * L_nhip
        sl = (i == 1)
        traces.append(_box3d(xt-be_W, -be_W*0.6, z_be_b, xt+be_W, be_W*0.6, z_be_t,
                             color="#aab7b8", opacity=0.9,
                             name="Bệ cọc" if sl else "", sl=sl))
        traces.append(_box3d(xt-W_tru/2, -W_tru*0.8, z_sh_b, xt+W_tru/2, W_tru*0.8, z_cap_b,
                             color="#c8d6c0", opacity=0.9,
                             name="Thân trụ" if sl else "", sl=sl))
        traces.append(_box3d(xt-cap_W, -bc/2*0.9, z_cap_b, xt+cap_W, bc/2*0.9, z_cap_t,
                             color="#d5dbdb", opacity=0.9,
                             name="Xà mũ" if sl else "", sl=sl))

    # ── Dầm chính ─────────────────────────────────────────────────────────
    bf = 0.35  # bề rộng dầm
    y_first = -bc/2 + oh
    for i_nhip in range(n_nhip):
        xs = x0 + i_nhip * L_nhip
        sl = (i_nhip == 0)
        for i_dam in range(n_dam):
            yd = y_first + i_dam * kc_dam
            traces.append(_box3d(xs, yd-bf/2, cao_dd, xs+L_nhip, yd+bf/2, cao_dd+H_dam,
                                 color="#85929e", opacity=0.92,
                                 name=f"Dầm {kcn.get('loai_dam','')}" if (sl and i_dam==0) else "",
                                 sl=(sl and i_dam==0)))

    # ── Bản mặt cầu ───────────────────────────────────────────────────────
    for i_nhip in range(n_nhip):
        xs = x0 + i_nhip * L_nhip
        sl = (i_nhip == 0)
        traces.append(_box3d(xs, -bc/2, cao_dd+H_dam, xs+L_nhip, bc/2, z_deck,
                             color="#e8eaf0", opacity=0.7,
                             name="Bản mặt cầu" if sl else "", sl=sl))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=dict(
            text=f"MÔ HÌNH 3D CẦU — {n_nhip} NHỊP × {L_nhip:.1f}m  |  L_cầu={L_cau:.1f}m  |  B_cầu={bc}m",
            x=0.5, font=dict(size=13)
        ),
        scene=dict(
            xaxis_title="Dọc cầu X (m)",
            yaxis_title="Ngang cầu Y (m)",
            zaxis_title="Cao độ Z (m)",
            aspectmode="data",
            camera=dict(eye=dict(x=1.5, y=-1.8, z=0.8)),
            bgcolor="#f8f9fa",
        ),
        height=620,
        legend=dict(orientation="h", y=-0.05, font=dict(size=9)),
        margin=dict(l=0, r=0, t=60, b=50),
        paper_bgcolor="white",
    )
    return fig
