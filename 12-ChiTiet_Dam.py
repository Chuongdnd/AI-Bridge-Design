"""
Module 12 — Chi tiết dầm cầu (Beam Details)
============================================
Vẽ chi tiết dầm theo loại: Super-T (SPT), T ngược, Dầm I

Kích thước tham chiếu từ bản vẽ SPT thực tế (L=38.2m):
  - H = 1750mm
  - Cánh trên trong: 225+770+225 = 1220mm
  - Đáy (stem): 160+700+160 = 1020mm
  - Cánh trên ngoài = kc (toàn khoảng cách tim dầm)

Hàm xuất:
  ve_chi_tiet_mcn(d, loai)           — MCN đầu dầm + MCN giữa dầm (2 panel)
  ve_chi_tiet_mat_cat_doc(d)         — Mặt cắt dọc (elevation)
  ve_chi_tiet_mat_bang(d)            — Mặt bằng dầm
  ve_chi_tiet_3d(d)                  — 3D một nhịp dầm
  render_chi_tiet_dam_tab(d, st)     — Render toàn bộ tab
"""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Bảng màu ─────────────────────────────────────────────────────────────────
_C = {
    "dam":      "#85929e",
    "dam_dk":   "#2c3e50",
    "ban":      "#d5d8dc",
    "btong_dk": "#566573",
    "dim":      "#5d6d7e",
    "phu":      "#2c3e50",
    "axis":     "#aab7b8",
    "steel":    "#c0392b",
    "hanh":     "rgba(200,214,192,0.6)",
}

# ─────────────────────────────────────────────────────────────────────────────
# HELPER POLYGONS / DIMENSIONS
# ─────────────────────────────────────────────────────────────────────────────

def _poly(fig, xs, ys, fill, lc, name="", op=1.0, sl=None, lw=1.5, row=None, col=None):
    show = (name != "") if sl is None else sl
    x = list(xs) + [xs[0]]; y = list(ys) + [ys[0]]
    kw = dict(x=x, y=y, fill="toself", fillcolor=fill, opacity=op,
              line=dict(color=lc, width=lw), mode="lines",
              name=name, showlegend=show,
              hovertemplate=f"<b>{name}</b><extra></extra>" if name else None)
    if row:
        fig.add_trace(go.Scatter(**kw), row=row, col=col)
    else:
        fig.add_trace(go.Scatter(**kw))


def _dim_h(fig, y, x0, x1, txt, color=None, row=None, col=None, fs=7):
    c = color or _C["dim"]
    for xi in [x0, x1]:
        s = dict(type="line", x0=xi, y0=y-0.04, x1=xi, y1=y+0.04,
                 line=dict(color=c, width=1))
        fig.add_shape(**s, **(dict(row=row, col=col) if row else {}))
    fig.add_shape(type="line", x0=x0, y0=y, x1=x1, y1=y,
                  line=dict(color=c, width=1),
                  **(dict(row=row, col=col) if row else {}))
    fig.add_annotation(x=(x0+x1)/2, y=y+0.03, text=txt, showarrow=False,
                       font=dict(size=fs, color=c), yanchor="bottom",
                       bgcolor="rgba(255,255,255,0.85)",
                       **(dict(row=row, col=col) if row else {}))


def _dim_v(fig, x, y0, y1, txt, color=None, dx=0.10, row=None, col=None, fs=7):
    c = color or _C["dim"]
    xa = x + dx
    for yi in [y0, y1]:
        fig.add_shape(type="line", x0=xa-0.04, y0=yi, x1=xa+0.04, y1=yi,
                      line=dict(color=c, width=1),
                      **(dict(row=row, col=col) if row else {}))
    fig.add_shape(type="line", x0=xa, y0=y0, x1=xa, y1=y1,
                  line=dict(color=c, width=1),
                  **(dict(row=row, col=col) if row else {}))
    fig.add_annotation(x=xa+0.04, y=(y0+y1)/2, text=txt, showarrow=False,
                       font=dict(size=fs, color=c), xanchor="left",
                       bgcolor="rgba(255,255,255,0.85)",
                       **(dict(row=row, col=col) if row else {}))


# ─────────────────────────────────────────────────────────────────────────────
# PROFILE GENERATORS — trả về (xs, ys) polygon theo khoảng cách từ xc
# ─────────────────────────────────────────────────────────────────────────────

def _spt_dims(H, kc):
    """
    Tính kích thước dầm SPT dựa trên H (m) và kc (m).
    Tham chiếu: SPT L=38.2m → H=1.750m, kc~2.4m.
    Kích thước chuẩn (mm): cánh trong=1220, đáy=1020, dày cánh=200, haunch=150.
    """
    k = H / 1.750   # hệ số tỷ lệ
    return {
        "H": H, "kc": kc,
        "tf_hw":  kc / 2,                             # nửa cánh trên NGOÀI = kc/2
        "tin_hw": min(kc/2 - 0.05, 0.610 * k),        # nửa cánh trên TRONG (610mm ref)
        "tf_h":   max(0.150, 0.200 * k),              # dày cánh trên (200mm ref)
        "hau_h":  max(0.080, 0.150 * k),              # cao haunch (150mm ref)
        "w_hw":   max(0.230, 0.350 * k),              # nửa rộng web song song (350mm ref)
        "bt_h":   max(0.030, 0.050 * k),              # cao vùng mở rộng web→cánh đáy
        "bf_hw":  max(0.380, 0.510 * k),              # nửa rộng cánh đáy (510mm ref)
        "bf_h":   max(0.100, 0.150 * k),              # dày cánh đáy (150mm ref)
    }


def _tngược_dims(H, kc):
    """Kích thước dầm T ngược (inverted T): web hẹp trên, cánh rộng dưới."""
    k = H / 1.20
    return {
        "H": H, "kc": kc,
        "w_hw":  max(0.065, 0.080 * k),    # nửa web (80mm ref for H=1.2)
        "bf_hw": min(kc * 0.44, 0.480),    # nửa cánh đáy
        "bf_h":  max(0.100, 0.220 * k),    # dày cánh đáy
    }


def _dami_dims(H, kc):
    """Kích thước dầm I: cánh trên = cánh dưới, web hẹp."""
    k = H / 1.60
    return {
        "H": H, "kc": kc,
        "fw":  max(0.160, 0.200 * k),   # nửa bề rộng cánh (200mm ref for H=1.6)
        "tw":  max(0.070, 0.090 * k),   # nửa bề rộng web (90mm ref)
        "tf":  max(0.120, 0.160 * k),   # dày cánh (trên & dưới)
    }


def _spt_profile(xc, z0, H, kc, at_end=False):
    """
    Profile 14 điểm dầm SPT (Super-T).
    z0 = cao độ đỉnh dầm (= đáy bản mặt cầu).
    at_end=True → web rộng hơn tại đầu dầm (vùng gối).
    """
    d = _spt_dims(H, kc)
    # Tại đầu dầm: web rộng hơn (thêm 30% để tạo vùng gối chắc)
    w = d["w_hw"] * (1.30 if at_end else 1.0)
    w = min(w, d["bf_hw"])

    xs = [
        xc - d["tf_hw"], xc + d["tf_hw"],    # 1,2: đỉnh cánh ngoài (=kc)
        xc + d["tf_hw"], xc + d["tin_hw"],   # 3,4: phải ngoài → haunch phải
        xc + w,                               # 5: cuối haunch phải (đỉnh web)
        xc + w,                               # 6: đáy web phải
        xc + d["bf_hw"], xc + d["bf_hw"],    # 7,8: cánh đáy phải
        xc - d["bf_hw"], xc - d["bf_hw"],    # 9,10: cánh đáy trái
        xc - w,                               # 11: đáy web trái
        xc - w,                               # 12: đỉnh web trái
        xc - d["tin_hw"], xc - d["tf_hw"],   # 13,14: haunch trái → ngoài trái
    ]
    ys = [
        z0, z0,                                           # 1,2
        z0 - d["tf_h"], z0 - d["tf_h"],                  # 3,4: đáy cánh trên
        z0 - d["tf_h"] - d["hau_h"],                     # 5: cuối haunch (đỉnh web)
        z0 - H + d["bf_h"] + d["bt_h"],                  # 6: đáy web
        z0 - H + d["bf_h"], z0 - H,                      # 7,8: cánh đáy phải
        z0 - H, z0 - H + d["bf_h"],                      # 9,10: cánh đáy trái
        z0 - H + d["bf_h"] + d["bt_h"],                  # 11: đáy web trái
        z0 - d["tf_h"] - d["hau_h"],                     # 12: đỉnh web trái
        z0 - d["tf_h"], z0 - d["tf_h"],                  # 13,14: đáy cánh trên trái
    ]
    return xs, ys


def _tngược_profile(xc, z0, H, kc):
    """Profile 8 điểm dầm T ngược (web hẹp trên, cánh rộng dưới)."""
    d = _tngược_dims(H, kc)
    xs = [
        xc - d["w_hw"], xc + d["w_hw"],          # 1,2: đỉnh web
        xc + d["w_hw"], xc + d["bf_hw"],          # 3,4: phải web → cánh đáy
        xc + d["bf_hw"], xc - d["bf_hw"],         # 5,6: đáy
        xc - d["bf_hw"], xc - d["w_hw"],          # 7,8: trái cánh → web
    ]
    ys = [
        z0, z0,                                    # 1,2: đỉnh web
        z0 - H + d["bf_h"], z0 - H + d["bf_h"],  # 3,4: giao web/cánh
        z0 - H, z0 - H,                           # 5,6: đáy cánh
        z0 - H + d["bf_h"], z0 - H + d["bf_h"],  # 7,8: giao cánh/web trái
    ]
    return xs, ys


def _dami_profile(xc, z0, H, kc):
    """Profile 12 điểm dầm I (cánh trên = cánh dưới, web hẹp giữa)."""
    d = _dami_dims(H, kc)
    xs = [
        xc - d["fw"], xc + d["fw"],   # 1,2: cánh trên ngoài
        xc + d["fw"], xc + d["tw"],   # 3,4: phải cánh → web
        xc + d["tw"], xc + d["fw"],   # 5,6: đáy web phải → cánh dưới
        xc + d["fw"], xc - d["fw"],   # 7,8: cánh dưới
        xc - d["fw"], xc - d["tw"],   # 9,10: trái cánh dưới → web
        xc - d["tw"], xc - d["fw"],   # 11,12: đỉnh web trái → cánh trên
    ]
    ys = [
        z0, z0,                              # 1,2: đỉnh cánh trên
        z0 - d["tf"], z0 - d["tf"],          # 3,4: đáy cánh trên
        z0 - H + d["tf"], z0 - H + d["tf"], # 5,6: đỉnh cánh dưới
        z0 - H, z0 - H,                      # 7,8: đáy cánh dưới
        z0 - H + d["tf"], z0 - H + d["tf"], # 9,10: đỉnh cánh dưới trái
        z0 - d["tf"], z0 - d["tf"],          # 11,12: đáy cánh trên trái
    ]
    return xs, ys


def _get_profile(loai_l, xc, z0, H, kc, at_end=False):
    """Dispatcher → trả về (xs, ys) theo loại dầm."""
    if "super" in loai_l:
        return _spt_profile(xc, z0, H, kc, at_end)
    elif "t ngược" in loai_l or "tngược" in loai_l or "t-ngược" in loai_l:
        return _tngược_profile(xc, z0, H, kc)
    else:
        return _dami_profile(xc, z0, H, kc)


# ─────────────────────────────────────────────────────────────────────────────
# 1. MẶT CẮT NGANG: ĐẦU DẦM + GIỮA DẦM (2 panel)
# ─────────────────────────────────────────────────────────────────────────────

def ve_chi_tiet_mcn(d):
    """
    Hai panel: MCN đầu dầm (A-A) và MCN giữa dầm (B-B).
    Theo tỷ lệ chuẩn 1:30 của bản vẽ SPT.
    """
    kcn  = d.get("kcn_result") or d.get("ai_result", {})
    loai = str(kcn.get("loai_dam", "Super-T"))
    ll   = loai.lower()
    H    = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    kc   = float(kcn.get("khoang_cach_dam", 2.2))
    t_ban = float(d.get("t_ban_mm", 200)) / 1000.0

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=[
            f"MẶT CẮT A-A — Đầu dầm (gối) TỶ LỆ 1:30",
            f"MẶT CẮT B-B — Giữa dầm (nhịp) TỶ LỆ 1:30",
        ],
        horizontal_spacing=0.10,
    )

    # Vẽ mỗi panel
    for col_idx, at_end in [(1, True), (2, False)]:
        z0 = 0.0  # đỉnh dầm

        # Bản mặt cầu (phía trên)
        hw = kc / 2
        _poly(fig, [-hw, hw, hw, -hw], [t_ban, t_ban, 0, 0],
              _C["ban"], _C["btong_dk"], "Bản mặt cầu" if col_idx == 1 else "",
              sl=(col_idx == 1), row=1, col=col_idx)

        # Profile dầm
        xs, ys = _get_profile(ll, 0.0, z0, H, kc, at_end)
        _poly(fig, xs, ys, _C["dam"], _C["dam_dk"],
              f"Dầm {loai}" if col_idx == 1 else "",
              sl=(col_idx == 1), row=1, col=col_idx, lw=2.0)

        # Đường tim
        fig.add_shape(type="line", x0=0, y0=-H - 0.15, x1=0, y1=t_ban + 0.10,
                      line=dict(color=_C["axis"], width=1, dash="dashdot"),
                      row=1, col=col_idx)
        fig.add_annotation(x=0, y=t_ban + 0.12, text="TIM DẦM",
                           showarrow=False, font=dict(size=7, color=_C["axis"]),
                           row=1, col=col_idx)

        # Dimensions
        d_info = _spt_dims(H, kc) if "super" in ll else (
            _tngược_dims(H, kc) if ("t ngược" in ll or "tngược" in ll) else _dami_dims(H, kc)
        )

        _dim_h(fig, -H - 0.25, -kc/2, kc/2, f"kc = {kc*1000:.0f}mm", row=1, col=col_idx)
        _dim_v(fig, kc/2 + 0.05, 0, -H, f"H={H*1000:.0f}mm", row=1, col=col_idx)
        _dim_v(fig, kc/2 + 0.05, 0, t_ban, f"t_bản={int(t_ban*1000)}mm",
               color="#c0392b", row=1, col=col_idx)

        if "super" in ll:
            tin = d_info["tin_hw"]
            w   = d_info["w_hw"] * (1.30 if at_end else 1.0)
            w   = min(w, d_info["bf_hw"])
            bf  = d_info["bf_hw"]
            _dim_h(fig, -H - 0.45, -tin, tin, f"{tin*2000:.0f}mm (cánh trong)",
                   color="#8e44ad", row=1, col=col_idx)
            _dim_h(fig, -H - 0.60, -bf, bf, f"{bf*2000:.0f}mm (đáy dầm)",
                   color="#27ae60", row=1, col=col_idx)
            _dim_h(fig, -H - 0.75, -w, w,
                   f"{w*2000:.0f}mm (web {'đầu' if at_end else 'giữa'})",
                   color="#e67e22", row=1, col=col_idx)
        elif "t ngược" in ll or "tngược" in ll:
            bf = d_info["bf_hw"]
            _dim_h(fig, -H - 0.45, -bf, bf, f"{bf*2000:.0f}mm (cánh đáy)",
                   color="#27ae60", row=1, col=col_idx)
        else:
            fw = d_info["fw"]
            _dim_h(fig, -H - 0.45, -fw, fw, f"{fw*2000:.0f}mm (cánh)",
                   color="#27ae60", row=1, col=col_idx)

    margin = H * 0.3
    fig.update_xaxes(
        showgrid=True, gridcolor="#ecf0f1",
        range=[-kc/2 - 0.35, kc/2 + 0.55],
        scaleanchor="y", scaleratio=1,
    )
    fig.update_yaxes(
        showgrid=True, gridcolor="#ecf0f1",
        range=[-H - margin, t_ban + 0.4],
    )
    fig.update_layout(
        height=520, template="plotly_white",
        legend=dict(orientation="h", y=-0.12, font=dict(size=9)),
        margin=dict(l=50, r=30, t=70, b=90),
        title=dict(
            text=(f"CHI TIẾT MẶT CẮT NGANG — DẦM {loai.upper()}<br>"
                  f"<span style='font-size:10px'>"
                  f"H={H*1000:.0f}mm | kc={kc*1000:.0f}mm | t_bản={int(t_ban*1000)}mm"
                  f"</span>"),
            x=0.5, font=dict(size=13),
        ),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 2. MẶT CẮT DỌC (Elevation / Longitudinal section)
# ─────────────────────────────────────────────────────────────────────────────

def ve_chi_tiet_mat_cat_doc(d):
    """
    Mặt cắt dọc dầm tại tim (x–z plane, nhìn từ bên cạnh).
    Hiển thị chiều cao dầm thay đổi theo chiều dài (Super-T: prismatic).
    Tỷ lệ 1:110 như bản vẽ tham chiếu.
    """
    kcn  = d.get("kcn_result") or d.get("ai_result", {})
    loai = str(kcn.get("loai_dam", "Super-T"))
    ll   = loai.lower()
    H    = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    L    = float(kcn.get("chieu_dai", 38.0))
    kc   = float(kcn.get("khoang_cach_dam", 2.2))
    t_ban = float(d.get("t_ban_mm", 200)) / 1000.0

    fig = go.Figure()

    # Chiều dài gối (bearing zone) = khoảng 750mm mỗi đầu cho SPT
    L_goi = min(0.75, L * 0.02)
    # Chiều dài vùng chuyển tiếp đầu dầm (haunch zone): ~2000mm cho SPT
    L_chuyentie = min(2.0, L * 0.05)

    d_mid = _spt_dims(H, kc) if "super" in ll else None
    d_end = _spt_dims(H, kc) if "super" in ll else None

    # ── Profil dọc dầm (mặt trên và mặt dưới) ──────────────────────────
    # Dầm Super-T (và các loại khác) — prismatic (chiều cao đều)
    # Phần cánh trên: từ x=0 đến x=L tại z=0 và z=-tf_h
    tf_h = _spt_dims(H, kc)["tf_h"] if "super" in ll else (
        0.0 if ("t ngược" in ll or "tngược" in ll) else _dami_dims(H, kc)["tf"]
    )
    bf_h = _spt_dims(H, kc)["bf_h"] if "super" in ll else (
        _tngược_dims(H, kc)["bf_h"] if ("t ngược" in ll or "tngược" in ll)
        else _dami_dims(H, kc)["tf"]
    )

    # Outline mặt ngoài dầm (hình chữ nhật đơn giản — phần nhìn từ bên):
    # Super-T nhìn ngang = hình chữ nhật, chiều cao H, chiều dài L

    # Cánh trên (top flange zone)
    _poly(fig,
          [0, L, L, 0],
          [0, 0, -tf_h, -tf_h],
          _C["hanh"], _C["dam_dk"], "Cánh trên (vùng)", lw=1.0, op=0.7)

    # Thân chính (web zone)
    _poly(fig,
          [0, L, L, 0],
          [-tf_h, -tf_h, -H + bf_h, -H + bf_h],
          _C["dam"], _C["dam_dk"], "Thân dầm (web)", lw=1.5)

    # Cánh đáy
    _poly(fig,
          [0, L, L, 0],
          [-H + bf_h, -H + bf_h, -H, -H],
          _C["hanh"], _C["dam_dk"], "Cánh đáy", lw=1.0, op=0.7)

    # Bản mặt cầu
    _poly(fig,
          [0, L, L, 0],
          [t_ban, t_ban, 0, 0],
          _C["ban"], _C["btong_dk"], "Bản mặt cầu BTCT", lw=1.0, op=0.8)

    # ── Vùng gối (bearing zone) ──────────────────────────────────────────
    for x_goi in [0, L - L_goi]:
        fig.add_shape(
            type="rect", x0=x_goi, y0=-H - 0.06, x1=x_goi + L_goi, y1=-H,
            fillcolor="rgba(192,160,107,0.5)", line=dict(color="#c0a06b", width=1.5)
        )
    fig.add_annotation(x=L_goi / 2, y=-H - 0.09,
                       text=f"Gối {L_goi*1000:.0f}mm", showarrow=False,
                       font=dict(size=7, color="#7f8c8d"))

    # ── Đường tim dầm ────────────────────────────────────────────────────
    fig.add_shape(type="line", x0=-0.5, y0=-H/2, x1=L+0.5, y1=-H/2,
                  line=dict(color=_C["axis"], width=1, dash="dashdot"))
    fig.add_annotation(x=L/2, y=-H/2 + 0.04, text="TIM DẦM",
                       showarrow=False, font=dict(size=7, color=_C["axis"]))

    # ── Ống thoát nước PVC (chỉ thị) ─────────────────────────────────────
    if "super" in ll:
        for x_pvc in np.linspace(L * 0.10, L * 0.90, max(2, int(L / 8.5))):
            fig.add_shape(
                type="circle", x0=x_pvc - 0.025, y0=-H * 0.92,
                x1=x_pvc + 0.025, y1=-H * 0.82,
                fillcolor="rgba(52,152,219,0.3)",
                line=dict(color="#2980b9", width=1)
            )
        fig.add_annotation(
            x=L * 0.55, y=-H * 0.87,
            text="Ống PVC D50", showarrow=True,
            arrowhead=2, ax=30, ay=0,
            font=dict(size=7, color="#2980b9")
        )

    # ── Dimensions ────────────────────────────────────────────────────────
    dy_top = t_ban + 0.3
    _dim_h(fig, dy_top, 0, L, f"L_nhịp = {L:.1f}m", color="#c0392b")
    _dim_h(fig, dy_top + 0.25, 0, L_goi, f"Lct={L_goi*1000:.0f}mm", color="#8e44ad")
    _dim_h(fig, dy_top + 0.25, L - L_goi, L, f"Lcp={L_goi*1000:.0f}mm", color="#8e44ad")
    _dim_v(fig, -0.3, 0, -H, f"H={H*1000:.0f}mm")
    _dim_v(fig, -0.3, 0, t_ban, f"t_bản={int(t_ban*1000)}mm", color="#c0392b")

    # Mặt cắt A-A và B-B trên hình
    for x_cut, lbl in [(L_goi + L_chuyentie * 0.3, "A-A"),
                        (L / 2, "B-B")]:
        fig.add_shape(type="line", x0=x_cut, y0=t_ban + 0.1, x1=x_cut, y1=-H - 0.15,
                      line=dict(color="#e74c3c", width=1.5, dash="dash"))
        fig.add_annotation(x=x_cut, y=t_ban + 0.12, text=lbl,
                           showarrow=False, font=dict(size=8, color="#e74c3c", family="Arial Black"),
                           yanchor="bottom")

    fig.update_layout(
        title=dict(
            text=(f"MẶT CẮT DỌC DẦM — {loai.upper()} | L={L:.1f}m | TỶ LỆ 1:110"),
            x=0.5, font=dict(size=12)
        ),
        xaxis=dict(title="Chiều dài dầm (m)", showgrid=True, gridcolor="#ecf0f1",
                   range=[-0.8, L + 1.0]),
        yaxis=dict(title="Chiều cao (m)", showgrid=True, gridcolor="#ecf0f1",
                   range=[-H - 0.4, t_ban + 0.6], scaleanchor="x", scaleratio=1),
        height=360, template="plotly_white",
        legend=dict(orientation="h", y=-0.22, font=dict(size=9)),
        margin=dict(l=70, r=30, t=60, b=100),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 3. MẶT BẰNG DẦM (Plan view — nhìn từ trên)
# ─────────────────────────────────────────────────────────────────────────────

def ve_chi_tiet_mat_bang(d):
    """
    Mặt bằng dầm: nhìn từ trên, thể hiện bề rộng cánh theo chiều dài.
    Tỷ lệ 1:110.
    """
    kcn  = d.get("kcn_result") or d.get("ai_result", {})
    loai = str(kcn.get("loai_dam", "Super-T"))
    ll   = loai.lower()
    H    = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    L    = float(kcn.get("chieu_dai", 38.0))
    kc   = float(kcn.get("khoang_cach_dam", 2.2))

    fig = go.Figure()

    if "super" in ll:
        dd = _spt_dims(H, kc)
        hw_outer = dd["tf_hw"]     # = kc/2
        hw_inner = dd["tin_hw"]    # cánh trong
        L_goi    = min(0.75, L * 0.02)
        L_ct     = min(2.0, L * 0.05)

        # Ngoại viền dầm (phần cánh trên)
        _poly(fig,
              [0, L, L, 0],
              [-hw_outer, -hw_outer, hw_outer, hw_outer],
              _C["hanh"], _C["dam_dk"], "Cánh trên (toàn rộng)", op=0.6)
        # Phần cánh trong (vùng sườn)
        _poly(fig,
              [0, L, L, 0],
              [-hw_inner, -hw_inner, hw_inner, hw_inner],
              _C["dam"], _C["dam_dk"], "Vùng sườn", op=0.8)

        # Đường tim ngang
        fig.add_shape(type="line", x0=-0.3, y0=0, x1=L+0.3, y1=0,
                      line=dict(color=_C["axis"], width=1, dash="dashdot"))

        # Thép móc cẩu (chỉ thị)
        for x_cau in [L_goi + 0.9, L - L_goi - 0.9]:
            fig.add_shape(type="circle",
                          x0=x_cau - 0.08, y0=-0.08, x1=x_cau + 0.08, y1=0.08,
                          fillcolor="rgba(192,57,43,0.4)",
                          line=dict(color="#c0392b", width=1.5))
        fig.add_annotation(x=L_goi + 0.9, y=hw_outer + 0.05,
                           text="Thép móc cẩu", showarrow=True,
                           arrowhead=2, ax=0, ay=-20,
                           font=dict(size=7, color="#c0392b"))

        # Dimensions
        _dim_h(fig, hw_outer + 0.3, 0, L, f"L = {L:.1f}m (= {L*1000:.0f}mm)", color="#c0392b")
        _dim_v(fig, L + 0.3, -hw_outer, hw_outer, f"kc = {kc*1000:.0f}mm")
        _dim_v(fig, L + 0.6, -hw_inner, hw_inner, f"{hw_inner*2000:.0f}mm", color="#8e44ad")

    elif "t ngược" in ll or "tngược" in ll:
        dd = _tngược_dims(H, kc)
        _poly(fig, [0, L, L, 0], [-dd["w_hw"], -dd["w_hw"], dd["w_hw"], dd["w_hw"]],
              _C["dam"], _C["dam_dk"], f"Web dầm {loai}", op=0.8)
        _poly(fig, [0, L, L, 0],
              [-dd["bf_hw"], -dd["bf_hw"], dd["bf_hw"], dd["bf_hw"]],
              _C["hanh"], _C["dam_dk"], "Cánh đáy", op=0.5)
        _dim_h(fig, dd["bf_hw"] + 0.2, 0, L, f"L = {L:.1f}m", color="#c0392b")
        _dim_v(fig, L + 0.2, -dd["bf_hw"], dd["bf_hw"], f"{dd['bf_hw']*2000:.0f}mm")

    else:  # Dầm I
        dd = _dami_dims(H, kc)
        _poly(fig, [0, L, L, 0], [-dd["fw"], -dd["fw"], dd["fw"], dd["fw"]],
              _C["hanh"], _C["dam_dk"], "Cánh dầm I", op=0.6)
        _poly(fig, [0, L, L, 0], [-dd["tw"], -dd["tw"], dd["tw"], dd["tw"]],
              _C["dam"], _C["dam_dk"], "Web dầm I", op=0.8)
        _dim_h(fig, dd["fw"] + 0.2, 0, L, f"L = {L:.1f}m", color="#c0392b")
        _dim_v(fig, L + 0.2, -dd["fw"], dd["fw"], f"{dd['fw']*2000:.0f}mm")

    fig.update_layout(
        title=dict(
            text=f"MẶT BẰNG DẦM — {loai.upper()} | L={L:.1f}m | TỶ LỆ 1:110",
            x=0.5, font=dict(size=12)
        ),
        xaxis=dict(title="Chiều dài dầm (m)", showgrid=True, gridcolor="#ecf0f1",
                   range=[-0.5, L + 1.2]),
        yaxis=dict(title="Bề rộng (m)", showgrid=True, gridcolor="#ecf0f1",
                   scaleanchor="x", scaleratio=1),
        height=280, template="plotly_white",
        legend=dict(orientation="h", y=-0.30, font=dict(size=9)),
        margin=dict(l=60, r=30, t=60, b=100),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 4. 3D MỘT NHỊP DẦM
# ─────────────────────────────────────────────────────────────────────────────

def _extrude_profile(xs_2d, ys_2d, x_start, x_end, color, name, opacity=1.0,
                     edge_color="#1a252f", edge_width=1.5):
    """
    Kéo dài profile 2D (ys_2d là y, xs_2d là z) theo trục x (chiều dài dầm).
    Trả về list [go.Mesh3d solid, go.Scatter3d edges] — Revit Shaded style.

    Hệ trục: x=chiều dài dầm, y=bề rộng ngang, z=chiều cao.
    xs_2d → y-axis (bề rộng)
    ys_2d → z-axis (chiều cao)
    """
    n = len(xs_2d)
    v_x0 = [x_start] * n;  v_y0 = list(xs_2d);  v_z0 = list(ys_2d)
    v_x1 = [x_end]   * n;  v_y1 = list(xs_2d);  v_z1 = list(ys_2d)
    verts_x = v_x0 + v_x1
    verts_y = v_y0 + v_y1
    verts_z = v_z0 + v_z1

    ii, jj, kk = [], [], []
    for i in range(n):
        i_next = (i + 1) % n
        a, b, c, e = i, i_next, i + n, i_next + n
        ii += [a, a]; jj += [b, c]; kk += [c, e]
    for i in range(1, n - 1):
        ii.append(0); jj.append(i); kk.append(i + 1)
    for i in range(1, n - 1):
        ii.append(n); jj.append(n + i + 1); kk.append(n + i)

    mesh = go.Mesh3d(
        x=verts_x, y=verts_y, z=verts_z,
        i=ii, j=jj, k=kk,
        color=color, opacity=opacity,
        name=name, showlegend=bool(name),
        flatshading=True,
        lighting=dict(ambient=0.55, diffuse=0.85, specular=0.30,
                      roughness=0.65, fresnel=0.05),
        lightposition=dict(x=500, y=300, z=1500),
        hovertemplate=f"<b>{name}</b><extra></extra>" if name else None,
    )

    # Đường viền nét (Revit shaded edges) — polygon đầu + cuối + cạnh dọc
    ex, ey, ez = [], [], []
    # Polygon đầu dầm
    for i in range(n):
        ex.append(x_start); ey.append(xs_2d[i]); ez.append(ys_2d[i])
    ex.append(x_start); ey.append(xs_2d[0]); ez.append(ys_2d[0])
    ex.append(None);    ey.append(None);     ez.append(None)
    # Polygon cuối dầm
    for i in range(n):
        ex.append(x_end); ey.append(xs_2d[i]); ez.append(ys_2d[i])
    ex.append(x_end); ey.append(xs_2d[0]); ez.append(ys_2d[0])
    ex.append(None);  ey.append(None);     ez.append(None)
    # Cạnh dọc mỗi đỉnh (nối đầu–cuối)
    for i in range(n):
        ex += [x_start, x_end, None]
        ey += [xs_2d[i], xs_2d[i], None]
        ez += [ys_2d[i], ys_2d[i], None]

    edges = go.Scatter3d(
        x=ex, y=ey, z=ez,
        mode="lines",
        line=dict(color=edge_color, width=edge_width),
        name="", showlegend=False, hoverinfo="skip",
    )
    return [mesh, edges]


def ve_chi_tiet_3d(d):
    """
    Mô hình 3D một nhịp dầm với profile chính xác theo loại dầm.
    x-axis = chiều dài dầm
    y-axis = bề rộng ngang
    z-axis = chiều cao
    """
    kcn  = d.get("kcn_result") or d.get("ai_result", {})
    loai = str(kcn.get("loai_dam", "Super-T"))
    ll   = loai.lower()
    H    = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    L    = float(kcn.get("chieu_dai", 38.0))
    kc   = float(kcn.get("khoang_cach_dam", 2.2))
    n_dam = int(kcn.get("so_luong_dam") or 5)
    oh   = float(kcn.get("overhang", 0.5))
    bc   = float(d.get("bc", 12.0))
    t_ban = float(d.get("t_ban_mm", 200)) / 1000.0

    traces = []

    # Vị trí tim các dầm
    x_first = -bc/2 + oh
    beam_positions = [x_first + i * kc for i in range(n_dam)]

    # Dầm — profile midspan (z0=0 = đỉnh dầm)
    for i, yc in enumerate(beam_positions):
        sl = (i == 0)
        xs_2d, zs_2d = _get_profile(ll, yc, 0.0, H, kc, at_end=False)
        traces += _extrude_profile(
            xs_2d, zs_2d,
            x_start=0.0, x_end=L,
            color=_C["dam"],
            name=f"Dầm {loai}" if sl else "",
            opacity=1.0,
        )

    # Bản mặt cầu (deck slab) — trong suốt vừa phải để thấy dầm
    deck_xs = [-bc/2, bc/2, bc/2, -bc/2]
    deck_zs = [0.0, 0.0, t_ban, t_ban]
    traces += _extrude_profile(
        deck_xs, deck_zs,
        x_start=0.0, x_end=L,
        color="#bdc3c7",
        name="Bản mặt cầu",
        opacity=0.55,
        edge_color="#5d6d7e",
    )

    # Gối dầm (bearing pads)
    L_goi = min(0.75, L * 0.02)
    for i, yc in enumerate(beam_positions):
        hw = max(0.20, H * 0.18)
        for xp in [0.0, L - L_goi]:
            sl_g = (i == 0 and xp == 0.0)
            goi_x = [xp, xp+L_goi, xp+L_goi, xp, xp, xp+L_goi, xp+L_goi, xp]
            goi_y = [yc-hw, yc-hw, yc+hw, yc+hw]*2
            goi_z = [-H-0.06]*4 + [-H]*4
            traces.append(go.Mesh3d(
                x=goi_x, y=goi_y, z=goi_z,
                i=[0,0,4,4,0,0,3,3,0,0,1,1],
                j=[1,2,5,6,1,5,2,6,3,7,2,6],
                k=[2,3,6,7,5,4,6,7,7,4,6,5],
                color="#b7950b", opacity=1.0,
                flatshading=True,
                lighting=dict(ambient=0.6, diffuse=0.85, specular=0.2),
                name="Gối dầm" if sl_g else "",
                showlegend=sl_g,
            ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=dict(
            text=f"MÔ HÌNH 3D — {n_dam} DẦM {loai.upper()} | L={L:.1f}m | B={bc:.1f}m",
            x=0.5, font=dict(size=12)
        ),
        scene=dict(
            xaxis=dict(title="Chiều dài (m)", backgroundcolor="#f0f0f0",
                       gridcolor="#cccccc", showbackground=True),
            yaxis=dict(title="Bề rộng ngang (m)", backgroundcolor="#e8e8e8",
                       gridcolor="#cccccc", showbackground=True),
            zaxis=dict(title="Chiều cao (m)", backgroundcolor="#e0e0e0",
                       gridcolor="#cccccc", showbackground=True),
            aspectmode="data",
            camera=dict(eye=dict(x=-1.8, y=-2.2, z=0.9)),
            bgcolor="white",
        ),
        height=580,
        margin=dict(l=0, r=0, t=55, b=0),
        legend=dict(font=dict(size=9), x=0.01, y=0.98),
        paper_bgcolor="white",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 5. CẬP NHẬT BEAM POLY TRONG MCN TỔNG (dùng profile chính xác)
# ─────────────────────────────────────────────────────────────────────────────

def beam_poly_accurate(fig, xc, z0, H, kc, loai, dam_color, dam_dk_color):
    """
    Vẽ dầm vào fig với profile chính xác. Thay thế _beam_poly trong module 11.
    """
    ll = loai.lower()
    xs, ys = _get_profile(ll, xc, z0, H, kc)
    from plotly.graph_objects import Scatter
    fig.add_trace(Scatter(
        x=xs + [xs[0]], y=ys + [ys[0]],
        fill="toself", fillcolor=dam_color, opacity=1.0,
        line=dict(color=dam_dk_color, width=1.5),
        mode="lines", name="", showlegend=False,
    ))


# ─────────────────────────────────────────────────────────────────────────────
# 6. HELPER — tạo dict d điển hình cho từng loại dầm
# ─────────────────────────────────────────────────────────────────────────────

# Thông số điển hình mỗi loại (từ thực tế VN)
_LOAI_DEFAULTS = {
    "super-t": dict(
        loai_dam="Super-T", chieu_cao_dam=1.750, khoang_cach_dam=2.200,
        chieu_dai=38.2,  so_luong_dam=4,  overhang=0.525,
        tong_so_nhip=1,
        label="SPT L38.2m  H=1750mm  kc=2200mm  4 dầm",
    ),
    "t nguoc": dict(
        loai_dam="T ngược", chieu_cao_dam=1.200, khoang_cach_dam=1.000,
        chieu_dai=24.0, so_luong_dam=16, overhang=0.500,
        tong_so_nhip=1,
        label="T ngược L24m  H=1200mm  kc=1000mm  16 dầm",
    ),
    "dam i": dict(
        loai_dam="Dầm I", chieu_cao_dam=1.600, khoang_cach_dam=1.750,
        chieu_dai=33.0, so_luong_dam=13, overhang=0.625,
        tong_so_nhip=1,
        label="Dầm I L33m  H=1600mm  kc=1750mm  13 dầm",
    ),
}


def _make_d_for_loai(loai, d_actual=None):
    """
    Tạo dict d với thông số điển hình của loai dầm cho tab chi tiết.
    Nếu d_actual cung cấp chiều cao / nhịp thực tế, dùng đó thay thế.
    """
    ll = loai.lower().replace("-", "").replace("_", "")
    if "super" in ll or "spt" in ll:
        key = "super-t"
    elif ("tng" in ll.replace(" ", "") or
          "t ng" in ll or
          "nguc" in ll or "ngược" in ll or "nguoc" in ll or
          "inverted" in ll):
        key = "t nguoc"
    else:
        key = "dam i"

    dd = dict(_LOAI_DEFAULTS[key])  # copy

    # Nếu thiết kế đã có giá trị thực tế → dùng
    if d_actual:
        kcn_a = d_actual.get("kcn_result") or d_actual.get("ai_result", {})
        if kcn_a.get("loai_dam", "").lower().replace("-", "").replace(" ", "") == \
           loai.lower().replace("-", "").replace(" ", ""):
            # Cùng loại → lấy kích thước thực
            for _k in ("chieu_cao_dam", "chieu_cao", "khoang_cach_dam", "chieu_dai", "so_luong_dam"):
                if kcn_a.get(_k):
                    dd[_k] = float(kcn_a[_k])

    bc_est = dd["khoang_cach_dam"] * dd["so_luong_dam"] + 2 * dd.get("overhang", 0.5)
    return {
        "kcn_result": dd,
        "ai_result":  dd,
        "t_ban_mm":   200,
        "bc":         bc_est,
        "chieu_day_mat_duong": 0.07,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. RENDER CHI TIẾT THEO LOẠI DẦM CỤ THỂ
# ─────────────────────────────────────────────────────────────────────────────

def _render_param_table(d_loai, st):
    """Bảng thông số hình học cho loai cụ thể."""
    kcn  = d_loai.get("kcn_result") or {}
    loai = str(kcn.get("loai_dam", ""))
    ll   = loai.lower()
    H    = float(kcn.get("chieu_cao_dam") or 1.75)
    kc   = float(kcn.get("khoang_cach_dam", 2.2))
    L    = float(kcn.get("chieu_dai", 38.0))

    with st.expander("📐 Thông số hình học", expanded=True):
        if "super" in ll:
            dd = _spt_dims(H, kc)
            rows = [
                ("Chiều dài nhịp L",       f"{L:.2f} m = {L*1000:.0f} mm"),
                ("Chiều cao dầm H",         f"{H:.3f} m = {H*1000:.0f} mm"),
                ("Cánh trên (tổng = kc)",   f"{kc:.3f} m = {kc*1000:.0f} mm"),
                ("Cánh trên trong",         f"{dd['tin_hw']*2000:.0f} mm"),
                ("Dày cánh trên",           f"{dd['tf_h']*1000:.0f} mm"),
                ("Haunch (chuyển tiếp)",    f"{dd['hau_h']*1000:.0f} mm"),
                ("Web song song (2×)",      f"{dd['w_hw']*2000:.0f} mm"),
                ("Cánh đáy (2×bf_hw)",      f"{dd['bf_hw']*2000:.0f} mm"),
                ("Dày cánh đáy",            f"{dd['bf_h']*1000:.0f} mm"),
                ("Tỷ lệ L/H",              f"{L/H:.1f}  (tối ưu 18–22)"),
            ]
        elif "t ngư" in ll or "tng" in ll:
            dd = _tngược_dims(H, kc)
            rows = [
                ("Chiều dài L",  f"{L:.2f} m"),
                ("Chiều cao H",  f"{H*1000:.0f} mm"),
                ("Web (thân trên)", f"{dd['w_hw']*2000:.0f} mm"),
                ("Cánh đáy (2×)", f"{dd['bf_hw']*2000:.0f} mm"),
                ("Dày cánh đáy", f"{dd['bf_h']*1000:.0f} mm"),
                ("Tỷ lệ L/H",    f"{L/H:.1f}"),
            ]
        else:
            dd = _dami_dims(H, kc)
            rows = [
                ("Chiều dài L",      f"{L:.2f} m"),
                ("Chiều cao H",      f"{H*1000:.0f} mm"),
                ("Cánh (2×fw)",      f"{dd['fw']*2000:.0f} mm"),
                ("Web (2×tw)",       f"{dd['tw']*2000:.0f} mm"),
                ("Dày cánh tf",      f"{dd['tf']*1000:.0f} mm"),
                ("Tỷ lệ L/H",        f"{L/H:.1f}"),
            ]
        st.table({"Thông số": [r[0] for r in rows],
                  "Giá trị":  [r[1] for r in rows]})


def render_chi_tiet_loai(d_actual, st, loai_fixed, key_prefix=""):
    """
    Render tab chi tiết cho một loại dầm cố định.
    Hiển thị MCN A-A/B-B, mặt cắt dọc, mặt bằng, 3D.
    """
    d_loai = _make_d_for_loai(loai_fixed, d_actual)
    kcn    = d_loai["kcn_result"]
    H  = float(kcn.get("chieu_cao_dam", 1.75))
    L  = float(kcn.get("chieu_dai", 38.0))
    kc = float(kcn.get("khoang_cach_dam", 2.2))
    nd = int(kcn.get("so_luong_dam", 5))

    st.markdown(
        f"**{loai_fixed.upper()}** — L={L:.1f}m | H={H*1000:.0f}mm | "
        f"kc={kc*1000:.0f}mm | {nd} dầm/MCN | tỷ lệ L/H={L/H:.1f}"
    )
    _render_param_table(d_loai, st)

    # ① MCN A-A + B-B
    st.markdown("**① Mặt cắt ngang — A-A (đầu dầm) và B-B (giữa dầm)**")
    try:
        fig_mcn = ve_chi_tiet_mcn(d_loai)
        st.plotly_chart(fig_mcn, use_container_width=True,
                        config={"scrollZoom": True, "displayModeBar": True},
                        key=f"{key_prefix}_mcn")
    except Exception as e:
        import traceback
        st.error(f"Lỗi MCN: {e}")
        with st.expander("Chi tiết"):
            st.code(traceback.format_exc())

    # ② Mặt cắt dọc
    st.markdown("**② Mặt cắt dọc — Tim dầm**")
    try:
        fig_doc = ve_chi_tiet_mat_cat_doc(d_loai)
        st.plotly_chart(fig_doc, use_container_width=True,
                        config={"scrollZoom": True, "displayModeBar": True},
                        key=f"{key_prefix}_doc")
    except Exception as e:
        st.error(f"Lỗi mặt cắt dọc: {e}")

    # ③ Mặt bằng
    st.markdown("**③ Mặt bằng dầm — Nhìn từ trên**")
    try:
        fig_mb = ve_chi_tiet_mat_bang(d_loai)
        st.plotly_chart(fig_mb, use_container_width=True,
                        config={"scrollZoom": True, "displayModeBar": True},
                        key=f"{key_prefix}_mb")
    except Exception as e:
        st.error(f"Lỗi mặt bằng: {e}")

    # ④ 3D dầm
    st.markdown("**④ Mô hình 3D — Shaded (xoay tự do)**")
    try:
        fig_3d = ve_chi_tiet_3d(d_loai)
        st.plotly_chart(fig_3d, use_container_width=True,
                        config={"scrollZoom": True, "displayModeBar": True},
                        key=f"{key_prefix}_3d")
        st.caption("Kéo để xoay · Scroll để zoom · Shift+drag để pan · Nháy đúp để reset")
    except Exception as e:
        import traceback
        st.error(f"Lỗi 3D: {e}")
        with st.expander("Chi tiết"):
            st.code(traceback.format_exc())


def render_chi_tiet_dam_tab(d, st):
    """Legacy wrapper — render chi tiết dầm theo loại đang thiết kế."""
    kcn  = d.get("kcn_result") or d.get("ai_result", {})
    loai = str(kcn.get("loai_dam", "Super-T"))
    render_chi_tiet_loai(d, st, loai, key_prefix="ctd_auto")
