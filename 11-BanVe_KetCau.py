"""
Module 11 — Bản vẽ kết cấu cầu (2D + 3D)
Tất cả hình vẽ tạo từ design_data — không cần dữ liệu khảo sát.
Khi có df_tim_line (địa hình) → tự động overlay vào sơ đồ nhịp.

Hàm xuất:
  ve_so_do_nhip_2d(d, df_tim_line=None) — Sơ đồ nhịp với trụ đặt ngoài tĩnh không
  ve_mat_cat_ngang_2d(d)               — MCN điển hình đầy đủ
  ve_mat_dung_tru_2d(d)               — Mặt đứng trụ cầu 2D
  ve_cau_3d(d, df_tim_line=None)       — Mô hình 3D kết cấu + địa hình nếu có
"""

import numpy as np
import plotly.graph_objects as go

# ── Bảng màu ─────────────────────────────────────────────────────────────────
_C = {
    "btong":    "#c8d6c0",
    "btong_dk": "#7f8c8d",
    "be":       "#aab7b8",
    "be_dk":    "#566573",
    "dam":      "#85929e",
    "dam_dk":   "#2c3e50",
    "ban":      "#d5d8dc",
    "phu":      "#2c3e50",
    "lan_can":  "#7f8c8d",
    "nuoc":     "rgba(52,152,219,0.35)",
    "dat":      "rgba(169,120,74,0.35)",
    "tk":       "rgba(231,76,60,0.12)",
    "tk_line":  "#e74c3c",
    "moc":      "#c0a06b",
    "dim":      "#5d6d7e",
    "dia_hinh": "#27ae60",
}

# ── Helpers ───────────────────────────────────────────────────────────────────
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
        fig.add_annotation(x=x0 + (x1-x0)*0.05, y=y, text=f" {label}", showarrow=False,
                           font=dict(size=8, color=color), yanchor="bottom", xanchor="left")

def _dim_h(fig, y, x0, x1, text, color=None, dy=0):
    color = color or _C["dim"]
    ya = y + dy
    for xi in [x0, x1]:
        fig.add_shape(type="line", x0=xi, y0=ya-0.12, x1=xi, y1=ya+0.12,
                      line=dict(color=color, width=1))
    fig.add_shape(type="line", x0=x0, y0=ya, x1=x1, y1=ya,
                  line=dict(color=color, width=1))
    fig.add_annotation(x=(x0+x1)/2, y=ya+0.05, text=text, showarrow=False,
                       font=dict(size=8, color=color), yanchor="bottom",
                       bgcolor="rgba(255,255,255,0.85)")

def _dim_v(fig, x, y0, y1, text, color=None, dx=0.4):
    color = color or _C["dim"]
    xa = x + dx
    for yi in [y0, y1]:
        fig.add_shape(type="line", x0=xa-0.2, y0=yi, x1=xa+0.2, y1=yi,
                      line=dict(color=color, width=1))
    fig.add_shape(type="line", x0=xa, y0=y0, x1=xa, y1=y1,
                  line=dict(color=color, width=1))
    fig.add_annotation(x=xa+0.08, y=(y0+y1)/2, text=text, showarrow=False,
                       font=dict(size=8, color=color), xanchor="left",
                       bgcolor="rgba(255,255,255,0.85)")

# ── Box mesh 3D ───────────────────────────────────────────────────────────────
def _box3d(x0, y0, z0, x1, y1, z1, color="#bdc3c7", opacity=0.88, name="", sl=True):
    vx = [x0,x1,x1,x0, x0,x1,x1,x0]
    vy = [y0,y0,y1,y1, y0,y0,y1,y1]
    vz = [z0,z0,z0,z0, z1,z1,z1,z1]
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
# TÍNH VỊ TRÍ TRỤ — Đặt NGOÀI tĩnh không với khoảng cách an toàn
# ===========================================================================

# Khoảng cách an toàn tối thiểu từ MÉP TRỤ đến BIÊN tĩnh không (TCVN 8818)
_PIER_SAFETY = 2.0   # m  (mép trụ cách biên thông thuyền ≥ 2m)

def _calc_pier_positions(x0, x_end, n_nhip, x_tim, B_tk):
    """
    Tính vị trí các trụ đảm bảo NGOÀI vùng tĩnh không + khoảng an toàn 2m.

    Quy tắc:
    - n_nhip = 1 : không có trụ
    - n_nhip = 2 : 1 trụ ngoài biên TK + _PIER_SAFETY
    - n_nhip = 3 : 2 trụ tại x_tim ± (B/2 + _PIER_SAFETY)
    - n_nhip ≥ 4 : 2 trụ tại biên + thêm trụ trong đoạn tiếp cận

    Returns: list[float] — x-positions của các trụ, đã sắp xếp tăng dần
    """
    if n_nhip <= 1:
        return []

    # Biên tĩnh không + khoảng an toàn → vị trí TIM trụ tối thiểu
    xL = x_tim - B_tk / 2 - _PIER_SAFETY   # trụ trái: ngoài biên trái 2m
    xR = x_tim + B_tk / 2 + _PIER_SAFETY   # trụ phải: ngoài biên phải 2m
    L_cau = x_end - x0

    # Không để trụ quá sát mố (giữ ≥ 6% L_cau để có nhịp tiếp cận tối thiểu)
    xL = max(xL, x0 + L_cau * 0.06)
    xR = min(xR, x_end - L_cau * 0.06)

    if n_nhip == 2:
        # 1 trụ: chọn vị trí nào cho nhịp cân bằng hơn
        opts = [xL, xR]
        best = min(opts, key=lambda xp: abs((xp - x0) - (x_end - xp)))
        return [best]

    if n_nhip == 3:
        return [xL, xR]

    # n_nhip >= 4: thêm trụ trong đoạn tiếp cận
    n_extra = n_nhip - 3
    L_left  = xL - x0
    L_right = x_end - xR

    if L_left + L_right < 1e-3:
        # Degenerate: spread evenly
        return sorted([x0 + i * L_cau / n_nhip for i in range(1, n_nhip)])

    n_extra_L = round(n_extra * L_left / (L_left + L_right))
    n_extra_R = n_extra - n_extra_L

    piers = []
    for i in range(1, n_extra_L + 1):
        piers.append(x0 + i * L_left / (n_extra_L + 1))
    piers.append(xL)
    piers.append(xR)
    for i in range(1, n_extra_R + 1):
        piers.append(xR + i * L_right / (n_extra_R + 1))

    return sorted(piers)

# Public alias
calc_pier_positions = _calc_pier_positions

# ===========================================================================
# 1. SƠ ĐỒ BỐ TRÍ NHỊP (2D) — Trụ đặt NGOÀI tĩnh không
# ===========================================================================
def ve_so_do_nhip_2d(d, df_tim_line=None):
    """
    Sơ đồ nhịp 2D từ design_data.
    - Trụ được đặt tại biên tĩnh không, KHÔNG vi phạm vùng thông thuyền.
    - Nếu có df_tim_line (Lý trình, Z): overlay đường địa hình thực đo.
    - Tọa độ X theo Lý trình thực địa (cùng hệ với df_tim_line).
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

    # Tọa độ Lý trình thực địa
    x0    = float(geo.get("x_mo_trai", -L_cau / 2))
    x_end = float(geo.get("x_mo_phai", x0 + L_cau))
    x_tim = float(geo.get("x_tim_clearance", (x0 + x_end) / 2))

    # ── Helper: lấy cao độ địa hình TN tại lý trình x ────────────────────
    _lt_col = _z_col = None
    _lt_arr = _z_arr = None
    if df_tim_line is not None and not df_tim_line.empty:
        _lt_col = next((c for c in df_tim_line.columns
                        if 'ý trình' in c or c.lower() in ['ly_trinh', 'chainage']), None)
        _z_col  = next((c for c in df_tim_line.columns
                        if c.upper() in ['Z', 'CAO_DO', 'H', 'ELEVATION']), None)
        if _lt_col and _z_col:
            _lt_arr = df_tim_line[_lt_col].values
            _z_arr  = df_tim_line[_z_col].values

    def _tz(x):
        """Cao độ địa hình thực tế tại lý trình x. Fallback về h_tn_tb nếu không có data."""
        if _lt_arr is None:
            return h_tn
        if x < _lt_arr.min() or x > _lt_arr.max():
            return h_tn
        return float(np.interp(x, _lt_arr, _z_arr))

    # ── Vị trí trụ đặt ngoài tĩnh không + safety ─────────────────────────
    piers    = _calc_pier_positions(x0, x_end, n_nhip, x_tim, B_tk)
    supports = [x0] + piers + [x_end]
    spans    = [(supports[i], supports[i+1]) for i in range(len(supports)-1)]

    # ── Cao độ kết cấu (tuyệt đối) ───────────────────────────────────────
    z_deck   = cao_dd + H_dam + t_ban
    z_cap_t  = cao_dd
    z_cap_b  = cao_dd - 0.80
    z_sh_b   = z_cap_b - H_tru       # đáy thân trụ (= đỉnh bệ cọc)
    z_be_t   = z_sh_b
    z_be_b   = z_sh_b - 1.50         # đáy bệ cọc
    z_min    = min(z_be_b - 1.0, MNTN - 0.5)

    W_cap = max(2.0, L_cau / n_nhip * 0.05 + 1.0)
    W_tru = 1.2
    W_be  = W_cap + 0.8
    W_mo  = 3.0

    mg = max(20, L_cau * 0.15)
    fig = go.Figure()

    # ── Đường địa hình từ khảo sát (nếu có) ─────────────────────────────
    if df_tim_line is not None and not df_tim_line.empty:
        lt_col = next((c for c in df_tim_line.columns if 'ý trình' in c or 'ly_trinh' in c.lower() or c.lower() == 'x'), None)
        z_col  = next((c for c in df_tim_line.columns if c.upper() in ['Z', 'CAO_DO', 'H', 'ELEVATION']), None)
        if lt_col and z_col:
            df_v = df_tim_line[
                (df_tim_line[lt_col] >= x0 - mg) &
                (df_tim_line[lt_col] <= x_end + mg)
            ].sort_values(lt_col)
            if not df_v.empty:
                fig.add_trace(go.Scatter(
                    x=df_v[lt_col], y=df_v[z_col],
                    mode="lines", name="Địa hình TN (khảo sát)",
                    line=dict(color=_C["dia_hinh"], width=2.5),
                    hovertemplate="Lý trình: %{x:.1f}m<br>Cao độ: %{y:.3f}m<extra>Địa hình</extra>"
                ))
                # Fill dưới đường địa hình
                fig.add_trace(go.Scatter(
                    x=list(df_v[lt_col]) + list(df_v[lt_col])[::-1],
                    y=list(df_v[z_col]) + [z_min]*len(df_v),
                    fill="toself", fillcolor=_C["dat"],
                    line=dict(color="rgba(0,0,0,0)"),
                    mode="lines", showlegend=False, hoverinfo="skip"
                ))
    else:
        # Không có khảo sát → hiển thị đường địa hình ước tính (h_tn_tb)
        _hline(fig, h_tn, x0-mg, x_end+mg,
               f"CĐTN trung bình ≈ {h_tn:.2f}m", "#27ae60", dash="dash")
        _poly(fig,
            [x0-mg, x_end+mg, x_end+mg, x0-mg],
            [h_tn, h_tn, z_min-0.2, z_min-0.2],
            _C["dat"], "rgba(0,0,0,0)", "", showlegend=False)

    # ── Mực nước ─────────────────────────────────────────────────────────
    _poly(fig,
        [x0+W_mo, x_end-W_mo, x_end-W_mo, x0+W_mo],
        [MNTN, MNTN, MNCN, MNCN],
        _C["nuoc"], "rgba(0,0,0,0)", "Mực nước sông", showlegend=True)
    for y_w, lbl, clr in [
        (MNCN, f"MNCN={MNCN:.3f}m", "#c0392b"),
        (MNTT, f"MNTT={MNTT:.3f}m", "#2980b9"),
        (MNTN, f"MNTN={MNTN:.3f}m", "#1abc9c"),
    ]:
        fig.add_trace(go.Scatter(
            x=[x0+W_mo+1, x_end-W_mo-1], y=[y_w, y_w],
            mode="lines+text", name=lbl,
            line=dict(color=clr, width=1.5, dash="dot"),
            text=[lbl, ""], textposition="top left",
            textfont=dict(size=8, color=clr)
        ))

    # ── Mố trái / phải ────────────────────────────────────────────────────
    # Cao độ đất nền tại vị trí mố lấy từ địa hình thực tế
    for xm, side, sign in [(x0, "Trái", 1), (x_end, "Phải", -1)]:
        z_terr_mo = _tz(xm)                      # cao độ địa hình tại mố
        z_mo_bot  = min(z_be_b, z_terr_mo - 1.5) # bệ cọc ngầm dưới đất

        # Phần ngầm (bệ cọc, cọc) — nét đứt, mờ
        _poly(fig,
            [xm, xm+sign*W_mo, xm+sign*W_mo, xm],
            [z_mo_bot, z_mo_bot, z_terr_mo, z_terr_mo],
            "rgba(192,160,107,0.3)", _C["be_dk"],
            "", showlegend=False, lw=1)

        # Phần nổi trên mặt đất (thân mố từ terrain → deck)
        _poly(fig,
            [xm, xm+sign*W_mo, xm+sign*W_mo, xm],
            [z_terr_mo, z_terr_mo, z_deck, z_deck],
            _C["moc"], _C["be_dk"], f"Mố {side}")

        # Đường địa hình tại mố (chỉ thị)
        fig.add_annotation(
            x=xm + sign*W_mo*0.5, y=z_terr_mo,
            text=f"Z={z_terr_mo:.2f}m",
            showarrow=False, font=dict(size=7, color="#27ae60"),
            yanchor="bottom", bgcolor="rgba(255,255,255,0.7)"
        )

    # ── Trụ giữa (đặt NGOÀI tĩnh không + 2m an toàn) ─────────────────────
    for i, xt in enumerate(piers):
        sl = (i == 0)
        z_terr_tru = _tz(xt)   # cao độ địa hình tại vị trí trụ (thực tế)

        # Phần NGẦM: bệ cọc + thân trụ dưới mặt đất → nét đứt mờ
        z_underground_top = min(z_sh_b, z_terr_tru)  # thân trụ ngập đến terrain
        if z_be_b < z_terr_tru:
            # Bệ cọc ngầm
            _poly(fig,
                [xt-W_be, xt+W_be, xt+W_be, xt-W_be],
                [z_be_b, z_be_b, min(z_be_t, z_terr_tru), min(z_be_t, z_terr_tru)],
                "rgba(170,183,184,0.3)", _C["be_dk"],
                "Bệ cọc (ngầm)" if sl else "", showlegend=sl, lw=1)
            # Thân trụ ngầm (nếu có)
            if z_sh_b < z_terr_tru:
                _poly(fig,
                    [xt-W_tru/2, xt+W_tru/2, xt+W_tru/2, xt-W_tru/2],
                    [z_sh_b, z_sh_b, z_terr_tru, z_terr_tru],
                    "rgba(200,214,192,0.3)", _C["btong_dk"],
                    "", showlegend=False, lw=1)

        # Phần NỔI: thân trụ từ terrain → đáy xà mũ
        z_shaft_visible_bot = max(z_sh_b, z_terr_tru)
        if z_shaft_visible_bot < z_cap_b:
            _poly(fig,
                [xt-W_tru/2, xt+W_tru/2, xt+W_tru/2, xt-W_tru/2],
                [z_shaft_visible_bot, z_shaft_visible_bot, z_cap_b, z_cap_b],
                _C["btong"], _C["btong_dk"], f"Thân trụ T{i+1}", showlegend=sl)

        # Xà mũ (luôn nổi)
        _poly(fig,
            [xt-W_cap, xt+W_cap, xt+W_cap, xt-W_cap],
            [z_cap_b, z_cap_b, z_cap_t, z_cap_t],
            _C["btong"], _C["dam_dk"], "Xà mũ" if sl else "", showlegend=sl)

        # Cao độ địa hình tại trụ
        fig.add_annotation(
            x=xt, y=z_terr_tru,
            text=f"Z={z_terr_tru:.2f}m",
            showarrow=True, arrowhead=2, arrowcolor="#27ae60",
            ax=25, ay=-15,
            font=dict(size=7, color="#27ae60"),
            bgcolor="rgba(255,255,255,0.7)"
        )

    # ── Dầm theo từng nhịp (chiều dài thực) ──────────────────────────────
    for i, (xs, xe) in enumerate(spans):
        sl = (i == 0)
        L_span = xe - xs
        _poly(fig, [xs, xe, xe, xs], [cao_dd, cao_dd, cao_dd+H_dam, cao_dd+H_dam],
              _C["dam"], _C["dam_dk"],
              f"Dầm {loai}" if sl else "", showlegend=sl)
        _poly(fig, [xs, xe, xe, xs],
              [cao_dd+H_dam, cao_dd+H_dam, z_deck, z_deck],
              _C["ban"], _C["dam_dk"],
              "Bản mặt cầu" if sl else "", showlegend=sl)
        # Dimension mỗi nhịp
        fig.add_annotation(x=(xs+xe)/2, y=z_deck+0.4, text=f"L={L_span:.1f}m",
                           showarrow=False, font=dict(size=8, color=_C["dam_dk"]),
                           bgcolor="rgba(255,255,255,0.8)")

    # ── Khung tĩnh không ─────────────────────────────────────────────────
    y_tk_bot = MNCN
    fig.add_shape(type="rect",
        x0=x_tim-B_tk/2, x1=x_tim+B_tk/2,
        y0=y_tk_bot, y1=y_tk_bot+H_tk,
        line=dict(color=_C["tk_line"], width=2.5),
        fillcolor=_C["tk"])
    fig.add_annotation(x=x_tim, y=y_tk_bot+H_tk/2,
        text=f"<b>TĨNH KHÔNG</b><br>B={B_tk:.1f}m × H={H_tk:.1f}m",
        showarrow=False, font=dict(size=9, color=_C["tk_line"]),
        bgcolor="rgba(255,255,255,0.8)")

    # Gióng thẳng vị trí biên tĩnh không → trụ
    for xp in piers:
        fig.add_shape(type="line",
            x0=xp, y0=z_be_b, x1=xp, y1=z_deck,
            line=dict(color="#aab7b8", width=0.8, dash="dashdot"))

    # ── Dimension tổng ────────────────────────────────────────────────────
    dy_dim = z_deck + 0.7
    _dim_h(fig, dy_dim+1.2, x0, x_end,
           f"<b>L_cầu = {L_cau:.1f}m ({n_nhip} nhịp — {loai})</b>",
           color="#c0392b", dy=0)
    if len(piers) >= 2:
        khoang_thong = piers[-1] - piers[0]
        ok_str = "✓" if khoang_thong >= B_tk + 2*_PIER_SAFETY else "⚠"
        _dim_h(fig, dy_dim, piers[0], piers[-1],
               f"Khoảng thông thuyền {khoang_thong:.1f}m (TK={B_tk:.1f}m+2×{_PIER_SAFETY:.0f}m safety) {ok_str}",
               color="#e74c3c", dy=0)
    elif len(piers) == 1:
        # n_nhip=2: nhịp chính phải ≥ B_tk + 2×safety
        xs_main = min(piers[0], x_end - (piers[0]-x0))
        xe_main = max(piers[0], x_end - (piers[0]-x0))
        span_main = spans[1][1] - spans[1][0] if piers[0] < x_tim else spans[0][1] - spans[0][0]
        ok_str = "✓" if span_main >= B_tk + 2*_PIER_SAFETY else "⚠"
        _dim_h(fig, dy_dim, x_tim-B_tk/2, x_tim+B_tk/2,
               f"Nhịp chính {span_main:.1f}m ≥ B_tk={B_tk:.1f}m {ok_str}",
               color="#e74c3c", dy=0)
    _dim_v(fig, x_end+W_mo+0.3, z_sh_b, z_cap_b, f"H_trụ={H_tru:.1f}m", dx=0.2)
    _dim_v(fig, x0-W_mo-0.3, cao_dd, cao_dd+H_dam, f"H_dầm={H_dam:.2f}m", dx=0.2)

    fig.update_layout(
        title=dict(
            text=(f"SƠ ĐỒ BỐ TRÍ NHỊP — {n_nhip} NHỊP ({loai.upper()})"
                  f" | L_cầu={L_cau:.1f}m | B_tk={B_tk:.1f}m"),
            x=0.5, font=dict(size=13)
        ),
        xaxis=dict(title="Lý trình (m)", showgrid=True, gridcolor="#ecf0f1"),
        yaxis=dict(title="Cao độ (m)", showgrid=True, gridcolor="#ecf0f1"),
        height=580, template="plotly_white",
        legend=dict(orientation="h", y=-0.20, font=dict(size=9)),
        margin=dict(l=70, r=30, t=70, b=110),
        hovermode="closest",
    )
    return fig


# ===========================================================================
# 2. MẶT CẮT NGANG ĐIỂN HÌNH ĐẦY ĐỦ
# ===========================================================================
def _beam_poly(fig, xc, H, loai, kc, t_ban):
    """
    Vẽ mặt cắt ngang dầm tại tim xc.
    z=0 tại mặt dưới bản mặt cầu; dầm nằm trong [z0, z0-H].

    Hình dạng chuẩn theo ảnh tham chiếu:
    - Super-T  : cánh trên rộng (≈ kc), haunch thon, cánh đáy nhỏ
    - T ngược  : web hẹp ở TRÊN, cánh rộng ở ĐÁY (T lộn ngược)
    - Dầm I    : cánh trên = cánh dưới, web hẹp ở giữa (12 điểm)
    """
    z0 = -t_ban
    loai_l = loai.lower()

    if "bản" in loai_l:
        # Dầm bản: hình chữ nhật
        hw = kc * 0.48
        _poly(fig, [xc-hw, xc+hw, xc+hw, xc-hw],
              [z0, z0, z0-H, z0-H],
              _C["dam"], _C["dam_dk"], showlegend=False)

    elif "t ngược" in loai_l or "t-ngược" in loai_l or "tngược" in loai_l:
        # Dầm T ngược (inverted-T):
        # - Web (sườn) HẸP ở TRÊN, nhúng vào bản BT đổ tại chỗ
        # - Bản cánh (flange) RỘNG ở ĐÁY
        #              ██   ← web hẹp (tw)
        #              ██
        #    ███████████████ ← cánh đáy rộng (fw)
        tw  = max(0.07, min(0.13, kc * 0.10))   # nửa bề rộng web
        fw  = min(kc * 0.44, 0.50)               # nửa bề rộng cánh đáy
        fh  = min(H * 0.24, 0.30)               # chiều cao cánh đáy
        xs = [xc-tw, xc+tw, xc+tw, xc+fw, xc+fw, xc-fw, xc-fw, xc-tw]
        ys = [z0,    z0,    z0-H+fh, z0-H+fh, z0-H, z0-H, z0-H+fh, z0-H+fh]
        _poly(fig, xs, ys, _C["dam"], _C["dam_dk"], showlegend=False)

    elif "super" in loai_l:
        # Dầm Super-T (SPT):
        # - Cánh trên RỘNG (≈ toàn khoảng cách tim), các cánh sát nhau
        # - Haunch (vát) chuyển từ cánh sang web
        # - Web thon, cánh đáy nhỏ
        # ████████████████ ← cánh trên rộng (tf_hw ≈ 0.46·kc)
        # ████         ████← haunch
        #    █████████    ← web + cánh đáy nhỏ
        tf_hw  = min(kc * 0.46, 1.10)   # nửa bề rộng cánh trên
        tf_h   = min(H * 0.12, 0.20)    # chiều cao cánh trên
        haunch = min(H * 0.10, 0.14)    # chiều cao haunch (chuyển cánh→web)
        w_top  = min(kc * 0.15, 0.26)   # nửa rộng web tại đỉnh
        w_bot  = min(kc * 0.11, 0.18)   # nửa rộng web tại đáy (thon nhẹ)
        bf_hw  = min(kc * 0.22, 0.34)   # nửa bề rộng cánh đáy
        bf_h   = min(H * 0.12, 0.18)    # chiều cao cánh đáy
        # 12 điểm: clockwise từ góc trên-trái
        xs = [
            xc-tf_hw, xc+tf_hw,          # 1,2 : đỉnh cánh trên (rộng)
            xc+tf_hw, xc+w_top,          # 3,4 : cạnh phải cánh → haunch phải
            xc+w_bot, xc+bf_hw,          # 5,6 : cuối haunch → cánh đáy phải trên
            xc+bf_hw, xc-bf_hw,          # 7,8 : đáy cánh đáy
            xc-bf_hw, xc-w_bot,          # 9,10: cánh đáy trái → cuối haunch
            xc-w_top, xc-tf_hw,          # 11,12: haunch trái → cạnh cánh trái
        ]
        ys = [
            z0,    z0,                   # 1,2
            z0-tf_h, z0-tf_h-haunch,    # 3,4
            z0-H+bf_h, z0-H+bf_h,       # 5,6
            z0-H, z0-H,                 # 7,8
            z0-H+bf_h, z0-H+bf_h,      # 9,10
            z0-tf_h-haunch, z0-tf_h,    # 11,12
        ]
        _poly(fig, xs, ys, _C["dam"], _C["dam_dk"], showlegend=False)

    else:  # Dầm I (mặc định)
        # I-beam: cánh trên = cánh dưới, web hẹp
        #  ████████  ← cánh trên (fw)
        #     ██     ← web (tw)
        #  ████████  ← cánh dưới (fw)
        tw = max(0.07, min(0.11, kc * 0.07))   # nửa bề rộng web
        fw = max(0.16, min(0.30, kc * 0.20))   # nửa bề rộng cánh
        tf = min(H * 0.13, 0.18)               # chiều cao cánh (trên & dưới)
        # 12 điểm chuẩn I-beam
        xs = [xc-fw, xc+fw, xc+fw, xc+tw,   xc+tw,   xc+fw,
              xc+fw, xc-fw, xc-fw, xc-tw,   xc-tw,   xc-fw]
        ys = [z0,    z0,    z0-tf, z0-tf,   z0-H+tf, z0-H+tf,
              z0-H,  z0-H,  z0-H+tf, z0-H+tf, z0-tf, z0-tf]
        _poly(fig, xs, ys, _C["dam"], _C["dam_dk"], showlegend=False)


def ve_mat_cat_ngang_2d(d):
    """MCN điển hình: bản, lớp phủ, dầm, lan can, kích thước, chú thích lớp."""
    kcn   = d.get("kcn_result") or d.get("ai_result", {})
    bc    = float(d.get("bc", 12.0))
    loai  = str(kcn.get("loai_dam", "Dầm I"))
    n_dam = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
    kc    = float(kcn.get("khoang_cach_dam", 2.2))
    H_dam = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    oh    = float(kcn.get("overhang", 0.5))
    t_ban = float(d.get("t_ban_mm", 200)) / 1000.0
    loai_l = loai.lower()

    # Chiều dày lớp phủ theo loại đường
    lop_phu = d.get("lop_phu_result", {})
    t_phu   = float(lop_phu.get("tong_day_tt", 70)) / 1000.0 if lop_phu else 0.070
    t_phu   = max(0.050, min(t_phu, 0.120))

    H_lc = 1.10   # chiều cao lan can
    W_lc = 0.30   # bề rộng lan can

    fig = go.Figure()

    x_first = -bc/2 + oh   # tim dầm đầu tiên

    # ── Bê tông đổ tại chỗ giữa các dầm (cho T ngược và Dầm I) ──────────
    is_tngược = "t ngược" in loai_l or "t-ngược" in loai_l or "tngược" in loai_l
    is_damiI  = not ("bản" in loai_l or "super" in loai_l or is_tngược)
    if is_tngược or is_damiI:
        # Vùng BT đổ tại chỗ giữa các dầm (từ đáy bản → đỉnh cánh dầm)
        # (màu nhạt hơn để phân biệt với dầm precast)
        for i in range(n_dam - 1):
            x_left  = x_first + i * kc
            x_right = x_first + (i + 1) * kc
            _poly(fig,
                  [x_left, x_right, x_right, x_left],
                  [-t_ban, -t_ban, -t_ban - H_dam * 0.5, -t_ban - H_dam * 0.5],
                  "rgba(200,210,200,0.45)", "rgba(127,140,141,0.3)",
                  "BT đổ tại chỗ" if i == 0 else "", showlegend=(i == 0), lw=0.5)

    # ── Lớp phủ mặt cầu ──────────────────────────────────────────────────
    # Lớp BTN (bê tông nhựa chặt)
    t_btn = min(t_phu * 0.7, 0.07)
    _poly(fig, [-bc/2, bc/2, bc/2, -bc/2],
          [t_phu, t_phu, t_phu - t_btn, t_phu - t_btn],
          "#2c3e50", "#1a252f", "BTN mặt đường", lw=1)
    # Lớp dính bám + phòng nước
    _poly(fig, [-bc/2, bc/2, bc/2, -bc/2],
          [t_phu - t_btn, t_phu - t_btn, 0, 0],
          "#7f8c8d", "#566573", "Lớp dính bám + phòng nước", lw=0.8, opacity=0.7)

    # ── Bản mặt cầu BTCT ─────────────────────────────────────────────────
    _poly(fig, [-bc/2, bc/2, bc/2, -bc/2], [0, 0, -t_ban, -t_ban],
          _C["ban"], _C["btong_dk"], "Bản mặt cầu BTCT")

    # ── Dầm chính ────────────────────────────────────────────────────────
    _beam_poly(fig, x_first, H_dam, loai, kc, t_ban)
    for i in range(1, n_dam):
        _beam_poly(fig, x_first + i * kc, H_dam, loai, kc, t_ban)
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
        marker=dict(color=_C["dam"], size=10, symbol="square"),
        name=f"Dầm {loai} BTCT DƯL ({n_dam} dầm)"))

    # ── Lan can ───────────────────────────────────────────────────────────
    for side in [-1, 1]:
        xb = side * bc / 2
        xi = xb - side * W_lc
        _poly(fig, [xi, xb, xb, xi],
              [t_phu, t_phu, t_phu + H_lc, t_phu + H_lc],
              _C["lan_can"], "#2c3e50",
              "Lan can / dải an toàn" if side == -1 else "",
              showlegend=(side == -1))
        # Chân lan can
        _poly(fig, [xi, xb, xb, xi],
              [0, 0, t_phu, t_phu],
              "#95a5a6", "#7f8c8d", "", showlegend=False, lw=0.5)

    # ── Đường tim cầu ────────────────────────────────────────────────────
    fig.add_shape(type="line", x0=0, y0=-t_ban - H_dam - 0.3, x1=0, y1=t_phu + H_lc + 0.1,
                  line=dict(color="#aab7b8", width=1, dash="dashdot"))
    fig.add_annotation(x=0, y=t_phu + H_lc + 0.12, text="TIM CẦU",
                       showarrow=False, font=dict(size=8, color="#7f8c8d"),
                       xanchor="center")

    # ── Chú thích lớp cấu tạo (góc phải) ────────────────────────────────
    ann_x = bc / 2 + 0.2
    ann_y = t_phu + 0.05
    layer_notes = [
        (f"BTN {int(t_btn*1000)}mm (C16 chặt)",        t_phu - t_btn / 2),
        ("Nhựa dính bám TC 0.5 kg/m²",                 t_phu * 0.15),
        ("Lớp phòng nước dạng phun",                   -t_ban * 0.1),
        (f"BMC BTCT tối thiểu {int(t_ban*1000)}mm",    -t_ban * 0.6),
    ]
    for note, y_pos in layer_notes:
        fig.add_annotation(
            x=ann_x, y=y_pos,
            text=f"<b>←</b> {note}",
            showarrow=False,
            xanchor="left",
            font=dict(size=7, color="#2c3e50"),
            bgcolor="rgba(255,255,255,0.85)",
        )

    # ── Kích thước ────────────────────────────────────────────────────────
    z_bot = -t_ban - H_dam
    _dim_h(fig, z_bot - 0.35, -bc/2, bc/2, f"Bc = {bc} m", dy=0)
    if n_dam >= 2:
        _dim_h(fig, z_bot - 0.85, x_first, x_first + kc,
               f"@{kc:.2f}m (×{n_dam-1} khoảng)", color="#8e44ad", dy=0)
        # Khoảng cách từ tim dầm ngoài cùng đến mép cầu (overhang)
        _dim_h(fig, z_bot - 0.85, -bc/2, x_first,
               f"oh={oh:.2f}m", color="#27ae60", dy=0)
    _dim_v(fig, bc/2 + 1.8, -t_ban, -t_ban - H_dam,
           f"H_dầm={H_dam:.2f}m", dx=0.2)
    _dim_v(fig, bc/2 + 2.6, -t_ban, 0,
           f"t_bản={int(t_ban*1000)}mm", dx=0.2)
    _dim_v(fig, bc/2 + 2.6, 0, t_phu,
           f"LP={int(t_phu*1000)}mm", color="#c0392b", dx=0.2)

    # ── Ký hiệu vật liệu (đường gạch chéo cho BTCT) ──────────────────────
    # Tim dầm đầu tiên — ghi nhãn loại dầm
    fig.add_annotation(
        x=x_first, y=-t_ban - H_dam * 0.5,
        text=f"<b>DẦM {loai.upper()}<br>BTCT DƯL</b>",
        showarrow=True, arrowhead=2, arrowcolor=_C["dim"],
        ax=-40, ay=20,
        font=dict(size=7, color="#2c3e50"),
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor=_C["dim"], borderwidth=0.5,
    )

    # Tỷ lệ ước tính (dựa vào bề rộng)
    ty_le = max(50, int(bc * 8))
    ty_le = min(200, (ty_le // 25) * 25)

    fig.update_layout(
        title=dict(
            text=(f"MẶT CẮT NGANG ĐIỂN HÌNH — TỶ LỆ 1:{ty_le}<br>"
                  f"<span style='font-size:11px'>"
                  f"B={bc}m | {n_dam} dầm {loai.upper()} BTCT DƯL | "
                  f"@{kc:.2f}m | t_bản={int(t_ban*1000)}mm"
                  f"</span>"),
            x=0.5, font=dict(size=13)
        ),
        xaxis=dict(title="Bề rộng (m)", showgrid=True, gridcolor="#ecf0f1",
                   range=[-bc/2 - 3.5, bc/2 + 4.5]),
        yaxis=dict(title="Cao độ (m)", scaleanchor="x", scaleratio=1,
                   showgrid=True, gridcolor="#ecf0f1",
                   range=[-t_ban - H_dam - 1.4, t_phu + H_lc + 0.6]),
        height=560, template="plotly_white",
        legend=dict(orientation="h", y=-0.18, font=dict(size=9)),
        margin=dict(l=70, r=80, t=90, b=100),
    )
    return fig


# ===========================================================================
# 3. MẶT ĐỨNG TRỤ CẦU (2D)
# ===========================================================================
def ve_mat_dung_tru_2d(d):
    """Mặt đứng trụ cầu điển hình với bệ cọc, thân, xà mũ và kích thước."""
    tru   = d.get("tru_result", {})
    kcn   = d.get("kcn_result") or d.get("ai_result", {})
    bc    = float(d.get("bc", 12.0))
    H_tru = float(d.get("H_tru_est", 5.0))
    H_dam = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    t_ban = float(d.get("t_ban_mm", 200)) / 1000.0
    loai_t= str(tru.get("loai_tru", "Thân cột 2 trụ"))
    mong  = d.get("mong_result", {})
    D_coc = float(mong.get("D_coc_mm", 600)) / 1000.0 if mong else 0.6

    cap_H = 0.80
    cap_W = max(2.0, bc * 0.18 + 1.0)
    be_H  = 1.50
    be_W  = cap_W + 0.8
    n_cot = 3 if "3" in loai_t else (2 if "cột" in loai_t.lower() else 1)
    W_cot = min(1.2, bc * 0.08 + 0.5)

    fig = go.Figure()

    # Xà mũ
    _poly(fig, [-cap_W, cap_W, cap_W, -cap_W], [0, 0, cap_H, cap_H],
          _C["btong"], _C["dam_dk"], "Xà mũ (cap beam)")
    # Thân trụ
    if n_cot == 1:
        W_don = min(cap_W * 0.7, 1.2)
        _poly(fig, [-W_don, W_don, W_don, -W_don], [-H_tru, -H_tru, 0, 0],
              _C["btong"], _C["btong_dk"], "Thân trụ đặc")
    else:
        starts = np.linspace(-cap_W * 0.6, cap_W * 0.6, n_cot)
        for i, xc in enumerate(starts):
            _poly(fig, [xc-W_cot/2, xc+W_cot/2, xc+W_cot/2, xc-W_cot/2],
                  [-H_tru, -H_tru, 0, 0], _C["btong"], _C["btong_dk"],
                  f"Thân cột {i+1}" if i == 0 else "", showlegend=(i == 0))
    # Bệ cọc
    _poly(fig, [-be_W, be_W, be_W, -be_W], [-H_tru-be_H, -H_tru-be_H, -H_tru, -H_tru],
          _C["be"], _C["be_dk"], "Bệ cọc")

    # Cọc
    L_coc = float(mong.get("L_coc_tu", 35)) if mong else 35
    n_coc_row = 3 if be_W >= 2.5 else 2
    coc_xs = np.linspace(-be_W * 0.7, be_W * 0.7, n_coc_row)
    for i, xc in enumerate(coc_xs):
        fig.add_trace(go.Scatter(
            x=[xc, xc], y=[-H_tru-be_H, -H_tru-be_H-L_coc],
            mode="lines", line=dict(color=_C["be_dk"], width=4),
            name="Cọc (ký hiệu)" if i == 0 else "", showlegend=(i == 0),
        ))

    # Dimensions
    _dim_h(fig, cap_H + 0.4, -cap_W, cap_W, f"B_xà mũ = {cap_W*2:.1f}m", dy=0)
    _dim_h(fig, -H_tru-be_H-0.4, -be_W, be_W, f"B_bệ cọc = {be_W*2:.1f}m", dy=0)
    _dim_v(fig, cap_W+0.5, 0, cap_H, f"cap {cap_H}m", dx=0.2)
    _dim_v(fig, cap_W+1.3, -H_tru, 0, f"H_trụ={H_tru:.1f}m", dx=0.2)
    _dim_v(fig, cap_W+2.1, -H_tru-be_H, -H_tru, f"bệ {be_H:.1f}m", dx=0.2)

    fig.add_annotation(x=coc_xs[-1], y=-H_tru-be_H-L_coc/2,
        text=f"Cọc Ø{int(D_coc*1000)}mm<br>L≈{L_coc:.0f}m",
        showarrow=True, arrowhead=2, ax=35, ay=0,
        font=dict(size=8), bgcolor="rgba(255,255,255,0.85)")

    fig.add_shape(type="line", x0=0, y0=-H_tru-be_H-2, x1=0, y1=cap_H+0.5,
                  line=dict(color="#aab7b8", width=1, dash="dashdot"))
    fig.add_annotation(x=0, y=cap_H+0.5, text="CL", showarrow=False,
                       font=dict(size=9, color="#aab7b8"))

    fig.update_layout(
        title=dict(text=f"MẶT ĐỨNG TRỤ — {loai_t.upper()} | H_trụ={H_tru:.1f}m",
                   x=0.5, font=dict(size=12)),
        xaxis=dict(title="Bề rộng ngang (m)", showgrid=True, gridcolor="#ecf0f1",
                   range=[-be_W-2.8, be_W+2.8]),
        yaxis=dict(title="Chiều cao (m)", scaleanchor="x", scaleratio=1,
                   showgrid=True, gridcolor="#ecf0f1"),
        height=580, template="plotly_white",
        legend=dict(orientation="h", y=-0.15, font=dict(size=9)),
        margin=dict(l=70, r=55, t=70, b=100),
    )
    return fig


# ===========================================================================
# 4. MÔ HÌNH 3D — Kết cấu + địa hình (nếu có df_tim_line)
# ===========================================================================
def ve_cau_3d(d, df_tim_line=None):
    """
    Mô hình 3D kết cấu cầu với trụ đặt đúng ngoài tĩnh không.
    Nếu có df_tim_line: thêm surface địa hình dọc cầu.
    """
    kcn    = d.get("kcn_result") or d.get("ai_result", {})
    geo    = d.get("geo_logic", {})

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
    B_tk   = float(d.get("B", 20.0))
    h_tn   = float(d.get("h_tn_tb", 2.0))
    MNCN   = float(d.get("MNCN", 3.5))
    MNTN   = float(d.get("MNTN", 0.5))

    x0    = float(geo.get("x_mo_trai", -L_cau / 2))
    x_end = float(geo.get("x_mo_phai", x0 + L_cau))
    x_tim = float(geo.get("x_tim_clearance", (x0 + x_end) / 2))

    # Pier positions
    piers    = _calc_pier_positions(x0, x_end, n_nhip, x_tim, B_tk)
    supports = [x0] + piers + [x_end]
    spans    = [(supports[i], supports[i+1]) for i in range(len(supports)-1)]

    cap_H = 0.80
    cap_W = max(2.0, bc * 0.18 + 1.0)
    be_H  = 1.50
    be_W  = cap_W + 0.8
    W_tru = 1.2
    mo_W  = 3.5

    z_deck   = cao_dd + H_dam + t_ban
    z_cap_t  = cao_dd
    z_cap_b  = cao_dd - cap_H
    z_sh_b   = z_cap_b - H_tru
    z_be_t   = z_sh_b
    z_be_b   = z_sh_b - be_H

    traces = []

    # ── Địa hình 3D (từ df_tim_line) ─────────────────────────────────────
    if df_tim_line is not None and not df_tim_line.empty:
        lt_col = next((c for c in df_tim_line.columns
                       if 'ý trình' in c or c.lower() in ['ly_trinh','x','chainage']), None)
        z_col  = next((c for c in df_tim_line.columns
                       if c.upper() in ['Z', 'CAO_DO', 'H', 'ELEVATION']), None)
        if lt_col and z_col:
            df_v = df_tim_line[
                (df_tim_line[lt_col] >= x0 - 30) &
                (df_tim_line[lt_col] <= x_end + 30)
            ].sort_values(lt_col)
            if len(df_v) >= 2:
                xvals = df_v[lt_col].values
                zvals = df_v[z_col].values
                W_belt = bc * 2  # bề rộng địa hình hiển thị

                # Tạo surface địa hình dạng dải dọc cầu
                x_surf = np.vstack([xvals, xvals])
                y_surf = np.vstack([np.full_like(xvals, -W_belt),
                                     np.full_like(xvals,  W_belt)])
                z_surf = np.vstack([zvals, zvals])

                traces.append(go.Surface(
                    x=x_surf, y=y_surf, z=z_surf,
                    colorscale="earth", opacity=0.70,
                    showscale=False, name="Địa hình (khảo sát)",
                    hovertemplate="Lý trình: %{x:.1f}m<br>Cao độ: %{z:.3f}m<extra>Địa hình</extra>"
                ))
    else:
        # Không có khảo sát: hiển thị mực nước phẳng
        mg_3d = 20
        x_rng = [x0-mg_3d, x_end+mg_3d]
        y_rng = [-bc*1.5, bc*1.5]
        traces.append(go.Surface(
            x=[[x_rng[0], x_rng[1]],[x_rng[0], x_rng[1]]],
            y=[[y_rng[0], y_rng[0]],[y_rng[1], y_rng[1]]],
            z=[[MNCN, MNCN],[MNCN, MNCN]],
            colorscale=[[0, "rgba(52,152,219,0.45)"], [1, "rgba(52,152,219,0.45)"]],
            showscale=False, opacity=0.45, name="Mặt nước (MNCN)",
        ))

    # ── Mố ────────────────────────────────────────────────────────────────
    for xm, nm in [(x0-mo_W, "Mố trái"), (x_end, "Mố phải")]:
        traces.append(_box3d(xm, -bc/2-0.5, z_be_b, xm+mo_W, bc/2+0.5, z_deck,
                             color="#c0a06b", name=nm))

    # ── Trụ (đặt NGOÀI tĩnh không) ────────────────────────────────────────
    for i, xt in enumerate(piers):
        sl = (i == 0)
        traces.append(_box3d(xt-be_W, -be_W*0.6, z_be_b, xt+be_W, be_W*0.6, z_be_t,
                             color="#aab7b8", name="Bệ cọc" if sl else "", sl=sl))
        traces.append(_box3d(xt-W_tru/2, -W_tru*0.8, z_sh_b,
                             xt+W_tru/2,  W_tru*0.8, z_cap_b,
                             color="#c8d6c0", name="Thân trụ" if sl else "", sl=sl))
        traces.append(_box3d(xt-cap_W, -bc/2*0.9, z_cap_b, xt+cap_W, bc/2*0.9, z_cap_t,
                             color="#d5dbdb", name="Xà mũ" if sl else "", sl=sl))

    # ── Dầm chính theo từng nhịp ──────────────────────────────────────────
    bf      = 0.35
    y_first = -bc/2 + oh
    for i_nhip, (xs, xe) in enumerate(spans):
        sl = (i_nhip == 0)
        for i_dam in range(n_dam):
            yd = y_first + i_dam * kc_dam
            traces.append(_box3d(xs, yd-bf/2, cao_dd, xe, yd+bf/2, cao_dd+H_dam,
                                 color="#85929e", opacity=0.92,
                                 name=f"Dầm {kcn.get('loai_dam','')}" if (sl and i_dam==0) else "",
                                 sl=(sl and i_dam==0)))

    # ── Bản mặt cầu ───────────────────────────────────────────────────────
    for i_nhip, (xs, xe) in enumerate(spans):
        sl = (i_nhip == 0)
        traces.append(_box3d(xs, -bc/2, cao_dd+H_dam, xe, bc/2, z_deck,
                             color="#e8eaf0", opacity=0.72,
                             name="Bản mặt cầu" if sl else "", sl=sl))

    fig = go.Figure(data=traces)

    # Vẽ khung tĩnh không trong 3D
    xL = x_tim - B_tk/2; xR = x_tim + B_tk/2
    y_tk = [-(B_tk/2+1), B_tk/2+1]
    for y in y_tk:
        fig.add_trace(go.Scatter3d(
            x=[xL, xR, xR, xL, xL], y=[y]*5,
            z=[MNCN, MNCN, MNCN+float(d.get('H',3.0)),
               MNCN+float(d.get('H',3.0)), MNCN],
            mode="lines", line=dict(color="#e74c3c", width=3),
            name="Tĩnh không" if y == y_tk[0] else "", showlegend=(y == y_tk[0]),
        ))

    fig.update_layout(
        title=dict(
            text=f"MÔ HÌNH 3D CẦU — {n_nhip} NHỊP | L={L_cau:.1f}m | B={bc}m",
            x=0.5, font=dict(size=13)
        ),
        scene=dict(
            xaxis_title="Lý trình (m)",
            yaxis_title="Ngang cầu (m)",
            zaxis_title="Cao độ (m)",
            aspectmode="data",
            camera=dict(eye=dict(x=1.4, y=-1.8, z=0.8)),
            bgcolor="#f5f6fa",
        ),
        height=640,
        legend=dict(orientation="h", y=-0.06, font=dict(size=9)),
        margin=dict(l=0, r=0, t=60, b=50),
        paper_bgcolor="white",
    )
    return fig


# ===========================================================================
# 5. OVERLAY KẾT CẤU CẦU LÊN HÌNH ĐỊA HÌNH 3D THỰC ĐO (VN-2000)
# ===========================================================================
def add_bridge_to_terrain_fig(fig, d, df_geology, he_so_z=1.0):
    """
    Thêm kết cấu cầu vào hình địa hình 3D thực đo VN-2000.

    Nguyên tắc khớp tọa độ:
    - Terrain dùng X_Real, Y_Real (VN-2000 sau offset vuông góc) và Z*he_so_z
    - Tim cầu = tim tuyến khảo sát (Offset=0) → X_VN2000, Y_VN2000
    - Lý trình tim tĩnh không là điểm neo chung giữa 2 mô hình
    - Phương ngang cầu = vuông góc với Góc_Tuyến tại mỗi cọc

    Columns df_geology: Lý trình, Offset, Z, X_VN2000, Y_VN2000, Góc_Tuyến, X_Real, Y_Real
    """
    try:
        kcn    = d.get("kcn_result") or d.get("ai_result", {})
        geo    = d.get("geo_logic", {})
        n_nhip = int(kcn.get("tong_so_nhip", 3))
        H_tru  = float(d.get("H_tru_est", 5.0))
        cao_dd = float(d.get("cao_day_dam", H_tru + 5.0))
        H_dam  = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
        t_ban  = float(d.get("t_ban_mm", 200)) / 1000.0
        B_tk   = float(d.get("B", 20.0))
        bc     = float(d.get("bc", 12.0))
        L_cau  = float(geo.get("L_cau", n_nhip * float(kcn.get("chieu_dai", 40))))
        x0     = float(geo.get("x_mo_trai", -L_cau / 2))
        x_end  = float(geo.get("x_mo_phai", x0 + L_cau))
        x_tim  = float(geo.get("x_tim_clearance", (x0 + x_end) / 2))

        # ── Lấy tim tuyến VN-2000 từ df_geology ─────────────────────────
        # Columns: Lý trình, X_VN2000, Y_VN2000, Góc_Tuyến (từ convert_to_vn2000)
        req_cols = {'Lý trình', 'X_VN2000', 'Y_VN2000', 'Góc_Tuyến', 'Offset', 'Z'}
        missing = req_cols - set(df_geology.columns)
        if missing:
            print(f"[add_bridge] Thiếu cột: {missing}. Có: {list(df_geology.columns)}")
            return

        df_cl = (df_geology[df_geology['Offset'] == 0]
                 [['Lý trình', 'X_VN2000', 'Y_VN2000', 'Góc_Tuyến', 'Z']]
                 .drop_duplicates('Lý trình')
                 .sort_values('Lý trình'))
        if df_cl.empty:
            print("[add_bridge] Tim tuyến rỗng (Offset==0 không có dữ liệu)")
            return

        lt_v   = df_cl['Lý trình'].values
        vx_v   = df_cl['X_VN2000'].values   # X VN-2000 tim tuyến
        vy_v   = df_cl['Y_VN2000'].values   # Y VN-2000 tim tuyến
        goc_v  = df_cl['Góc_Tuyến'].values  # hướng tuyến (radian)
        vz_v   = df_cl['Z'].values           # cao độ địa hình tim tuyến

        def _at(s):
            """Trả về (X_VN2000, Y_VN2000, Góc_Tuyến, Z) tại lý trình s."""
            return (float(np.interp(s, lt_v, vx_v)),
                    float(np.interp(s, lt_v, vy_v)),
                    float(np.interp(s, lt_v, goc_v)),
                    float(np.interp(s, lt_v, vz_v)))

        def _vn2000(s, offset_ngang=0.0):
            """
            Chuyển (Lý trình s, offset ngang) → (X_Real, Y_Real) VN-2000.
            offset_ngang > 0 = phía trái (theo quy ước), < 0 = phải.
            Công thức giống convert_to_vn2000: vuông góc với Góc_Tuyến.
            """
            xc, yc, goc, _ = _at(s)
            perp = goc + np.pi / 2           # hướng vuông góc với tim tuyến
            xr = xc + offset_ngang * np.cos(perp)
            yr = yc + offset_ngang * np.sin(perp)
            return xr, yr

        # ── Cao độ kết cấu (× he_so_z để khớp terrain) ──────────────────
        hz = he_so_z
        z_deck = (cao_dd + H_dam + t_ban) * hz
        z_cap  =  cao_dd * hz
        z_sh_b = (cao_dd - 0.80 - H_tru) * hz
        z_be_b = (cao_dd - 0.80 - H_tru - 1.50) * hz
        MNCN   =  float(d.get("MNCN", 3.5)) * hz
        H_tk   =  float(d.get("H", 3.0)) * hz

        piers = _calc_pier_positions(x0, x_end, n_nhip, x_tim, B_tk)

        # ── Bề mặt bản mặt cầu — go.Mesh3d (dải tam giác dọc tim tuyến) ──
        # go.Surface với z=const không render được vì colorscale min==max → dùng Mesh3d
        n_pts = min(40, max(len(lt_v), 4))
        s_pts = np.linspace(x0, x_end, n_pts)

        X_L, Y_L, X_R, Y_R = [], [], [], []
        for s in s_pts:
            xl, yl = _vn2000(s, -bc / 2)
            xr, yr = _vn2000(s,  bc / 2)
            X_L.append(xl); Y_L.append(yl)
            X_R.append(xr); Y_R.append(yr)

        # Vertices: [left edge points] + [right edge points]
        mesh_x = X_L + X_R
        mesh_y = Y_L + Y_R
        mesh_z = [z_deck] * n_pts + [z_deck] * n_pts
        # Triangulation: 2 triangles per quad
        ii_m, jj_m, kk_m = [], [], []
        for k in range(n_pts - 1):
            # Quad: L[k], L[k+1], R[k], R[k+1]
            ii_m += [k,       k + 1       ]
            jj_m += [k + 1,   n_pts + k + 1]
            kk_m += [n_pts + k, n_pts + k  ]
        fig.add_trace(go.Mesh3d(
            x=mesh_x, y=mesh_y, z=mesh_z,
            i=ii_m, j=jj_m, k=kk_m,
            color="#c8d0d8", opacity=0.92,
            flatshading=True,
            lighting=dict(ambient=0.8, diffuse=0.6),
            name="Bản mặt cầu",
            showlegend=True,
            hovertemplate="Bản mặt cầu<br>Z=%.2fm<extra></extra>" % (z_deck / hz),
        ))

        # ── Trụ — Mesh3d hộp + đường dọc có marker ─────────────────────
        cap_W_half = max(2.0, bc * 0.18)   # nửa bề rộng xà mũ (thực tế ~2-3m)
        for i, xt in enumerate(piers):
            sl = (i == 0)

            # Đường tim trụ (có marker để nhìn thấy ở mọi góc)
            xc, yc = _vn2000(xt, 0)
            zz = np.linspace(max(z_be_b, -1.0), z_deck, 8).tolist()
            fig.add_trace(go.Scatter3d(
                x=[xc] * 8, y=[yc] * 8, z=zz,
                mode="lines+markers",
                line=dict(color="#566573", width=8),
                marker=dict(size=4, color="#566573", symbol="circle"),
                name="Trụ cầu" if sl else "",
                showlegend=sl,
            ))

            # Xà mũ: đường ngang rộng cap_W_half mỗi bên — có marker ở đầu
            xrL, yrL = _vn2000(xt, -cap_W_half)
            xrR, yrR = _vn2000(xt,  cap_W_half)
            fig.add_trace(go.Scatter3d(
                x=[xrL, xc, xrR], y=[yrL, yc, yrR],
                z=[z_cap, z_cap, z_cap],
                mode="lines+markers",
                line=dict(color="#aab7b8", width=10),
                marker=dict(size=6, color="#aab7b8", symbol="square"),
                name="Xà mũ" if sl else "",
                showlegend=sl,
            ))

        # ── Mố trái / phải — đường đứng + ngang, có marker ──────────────
        for xm, nm in [(x0, "Mố trái"), (x_end, "Mố phải")]:
            sl = (nm == "Mố trái")
            # Tim mố
            xc, yc = _vn2000(xm, 0)
            fig.add_trace(go.Scatter3d(
                x=[xc, xc], y=[yc, yc],
                z=[z_be_b, z_deck],
                mode="lines+markers",
                line=dict(color="#c0a06b", width=10),
                marker=dict(size=6, color="#c0a06b", symbol="square"),
                name=nm, showlegend=sl,
            ))
            # Thanh ngang mố (rộng bc)
            xrL, yrL = _vn2000(xm, -bc / 2)
            xrR, yrR = _vn2000(xm,  bc / 2)
            for z_level in [z_be_b, z_deck]:
                fig.add_trace(go.Scatter3d(
                    x=[xrL, xc, xrR], y=[yrL, yc, yrR],
                    z=[z_level] * 3,
                    mode="lines",
                    line=dict(color="#c0a06b", width=6),
                    showlegend=False,
                ))

        # ── Tĩnh không — khung đỏ (biên thông thuyền) ────────────────────
        xL_tk = x_tim - B_tk / 2
        xR_tk = x_tim + B_tk / 2
        xrL, yrL = _vn2000(xL_tk, 0)
        xrR, yrR = _vn2000(xR_tk, 0)

        # Cột đứng ở 2 biên
        for xr_v, yr_v, side in [(xrL, yrL, "Biên trái TK"), (xrR, yrR, "Biên phải TK")]:
            fig.add_trace(go.Scatter3d(
                x=[xr_v, xr_v], y=[yr_v, yr_v],
                z=[MNCN, MNCN + H_tk],
                mode="lines+markers",
                line=dict(color="#e74c3c", width=5),
                marker=dict(size=6, color="#e74c3c", symbol="circle"),
                name=side, showlegend=True,
            ))
        # Thanh ngang đáy và đỉnh tĩnh không
        for z_tk_level in [MNCN, MNCN + H_tk]:
            fig.add_trace(go.Scatter3d(
                x=[xrL, xrR], y=[yrL, yrR],
                z=[z_tk_level, z_tk_level],
                mode="lines",
                line=dict(color="#e74c3c", width=4, dash="dot"),
                showlegend=False,
            ))

    except Exception as exc:
        import traceback
        print(f"[add_bridge_to_terrain_fig] Lỗi: {exc}\n{traceback.format_exc()}")


# ===========================================================================
# 6. MÔI TRƯỜNG 3D TỔNG HỢP — Digital Twin (Mesh3d khối thực sự)
# ===========================================================================
def add_all_to_terrain_fig(fig, d, df_geology, he_so_z=1.0):
    """
    Phối hợp TẤT CẢ kết quả tính toán vào 1 môi trường 3D thống nhất.
    Tất cả cấu kiện dùng _abox() → Mesh3d 8 đỉnh 12 tam giác (KHỐI 3D thực),
    giống hệt ve_cau_3d nhưng tọa độ VN-2000 căn theo tim tuyến khảo sát.

    Lớp 1 — Thủy văn (01-Tinh_khong): mặt phẳng mực nước + khung TK
    Lớp 2 — Trắc dọc (02-Yeuto_Hinhhoc): đường đỏ + đường địa hình TN
    Lớp 3 — Kết cấu nhịp (06-AI_KetCauNhip): lớp phủ + bản + dầm (khối)
    Lớp 4 — Trụ cầu (07-AI_MoTru): xà mũ + thân trụ (khối)
    Lớp 5 — Móng (08-AI_Mong): bệ cọc (khối) + cọc (lines)
    Lớp 6 — Mố hai đầu (khối)
    """
    try:
        # ── Thông số ──────────────────────────────────────────────────────
        kcn    = d.get("kcn_result") or d.get("ai_result", {})
        geo    = d.get("geo_logic", {})
        tru_r  = d.get("tru_result", {}) or {}
        mong_r = d.get("mong_result", {}) or {}

        n_nhip = int(kcn.get("tong_so_nhip", 3))
        L_nhip = float(kcn.get("chieu_dai", 40))
        H_dam  = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
        n_dam  = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
        kc_dam = float(kcn.get("khoang_cach_dam", 2.2))
        oh_dam = float(kcn.get("overhang", 0.5))
        loai_t = str(tru_r.get("loai_tru", "Than cot 2 tru"))
        n_cot  = 3 if "3" in loai_t else (2 if "cot" in loai_t.lower() or "cột" in loai_t.lower() else 1)

        bc     = float(d.get("bc", 12.0))
        t_ban  = float(d.get("t_ban_mm", 200)) / 1000.0
        t_phu  = 0.07
        B_tk   = float(d.get("B", 20.0))
        H_tk   = float(d.get("H", 3.0))
        MNCN   = float(d.get("MNCN", 3.5))
        MNTT   = float(d.get("MNTT", 2.0))
        MNTN   = float(d.get("MNTN", 0.5))
        H_tru  = float(d.get("H_tru_est", 5.0))
        cao_dd = float(d.get("cao_day_dam", H_tru + 5.0))
        D_coc  = float(mong_r.get("D_coc_mm", 600)) / 1000.0 if mong_r else 0.6
        L_coc  = float(mong_r.get("L_coc_tu", 35)) if mong_r else 35.0

        L_cau = float(geo.get("L_cau", n_nhip * L_nhip))
        x0    = float(geo.get("x_mo_trai", -L_cau / 2))
        x_end = float(geo.get("x_mo_phai", x0 + L_cau))
        x_tim = float(geo.get("x_tim_clearance", (x0 + x_end) / 2))

        # ── Kiểm tra cột ──────────────────────────────────────────────────
        req = {"Lý trình", "X_VN2000", "Y_VN2000", "Góc_Tuyến", "Offset", "Z"}
        if req - set(df_geology.columns):
            print(f"[add_all] Thiếu cột: {req - set(df_geology.columns)}")
            return

        df_cl = (df_geology[df_geology["Offset"] == 0]
                 [["Lý trình", "X_VN2000", "Y_VN2000", "Góc_Tuyến", "Z"]]
                 .drop_duplicates("Lý trình").sort_values("Lý trình"))
        if df_cl.empty:
            return

        lt_v  = df_cl["Lý trình"].values
        vx_v  = df_cl["X_VN2000"].values
        vy_v  = df_cl["Y_VN2000"].values
        goc_v = df_cl["Góc_Tuyến"].values
        vz_v  = df_cl["Z"].values

        def _at(s):
            return (float(np.interp(s, lt_v, vx_v)),
                    float(np.interp(s, lt_v, vy_v)),
                    float(np.interp(s, lt_v, goc_v)),
                    float(np.interp(s, lt_v, vz_v)))

        def _vn(s, off=0.0):
            xc, yc, goc, _ = _at(s)
            perp = goc + np.pi / 2
            return xc + off * np.cos(perp), yc + off * np.sin(perp)

        hz = he_so_z

        # ── Cao độ × he_so_z ──────────────────────────────────────────────
        z_phu  = (cao_dd + H_dam + t_ban + t_phu) * hz
        z_deck = (cao_dd + H_dam + t_ban) * hz
        z_bant = (cao_dd + H_dam) * hz
        z_beamb = cao_dd * hz
        z_capt = cao_dd * hz
        z_capb = (cao_dd - 0.80) * hz
        z_sht  = z_capb
        z_shb  = (cao_dd - 0.80 - H_tru) * hz
        z_bet  = z_shb
        z_beb  = (cao_dd - 0.80 - H_tru - 1.50) * hz
        z_pileb = z_beb - L_coc * hz

        cap_W     = max(2.0, bc * 0.18 + 1.0)
        be_W      = cap_W + 0.8
        W_tru     = 1.2
        W_cot     = min(1.0, bc * 0.06 + 0.4)
        cap_thick = 0.4
        be_long   = be_W * 0.7
        mo_L      = 3.5

        piers    = _calc_pier_positions(x0, x_end, n_nhip, x_tim, B_tk)
        supports = [x0] + piers + [x_end]
        spans    = [(supports[i], supports[i+1]) for i in range(len(supports)-1)]

        # ── Helper: HỘP 3D căn theo tim tuyến VN-2000 ────────────────────
        # Cùng logic _box3d nhưng XY lấy từ _vn(lý_trình, offset_ngang)
        def _abox(s0, s1, oL, oR, zb, zt, color, opacity=0.88, name="", sl=True):
            c = [_vn(s0, oL), _vn(s0, oR), _vn(s1, oR), _vn(s1, oL)]
            vx = [p[0] for p in c] + [p[0] for p in c]
            vy = [p[1] for p in c] + [p[1] for p in c]
            vz = [zb]*4 + [zt]*4
            ii = [0,0, 4,4, 0,0, 3,3, 0,0, 1,1]
            jj = [1,2, 5,6, 1,5, 2,6, 3,7, 2,6]
            kk = [2,3, 6,7, 5,4, 6,7, 7,4, 6,5]
            return go.Mesh3d(
                x=vx, y=vy, z=vz, i=ii, j=jj, k=kk,
                color=color, opacity=opacity, flatshading=True,
                name=name, showlegend=sl and bool(name),
                lighting=dict(ambient=0.65, diffuse=0.85, specular=0.2),
                hovertemplate=f"<b>{name}</b><extra></extra>" if name else None,
            )

        # =========================================================
        # LỚP 1 — THỦY VĂN & TĨNH KHÔNG
        # =========================================================
        # Mực nước chỉ hiển thị cục bộ tại vị trí khung tĩnh không
        yw_local = B_tk * 1.2          # độ rộng ngang (vuông góc tim)
        xL_water = x_tim - B_tk / 2   # giới hạn dọc = chiều rộng TK
        xR_water = x_tim + B_tk / 2
        for z_w, lbl, clr, op in [
            (MNCN * hz, f"MNCN = {MNCN:.3f}m", "#2980b9", 0.50),
            (MNTT * hz, f"MNTT = {MNTT:.3f}m", "#3498db", 0.35),
            (MNTN * hz, f"MNTN = {MNTN:.3f}m", "#1abc9c", 0.25),
        ]:
            fig.add_trace(_abox(xL_water, xR_water, -yw_local, yw_local,
                                z_w - 0.05 * hz, z_w, clr, op, lbl))

        # Khung tĩnh không B×H (dây đỏ)
        xL_tk = x_tim - B_tk/2; xR_tk = x_tim + B_tk/2
        xrL, yrL = _vn(xL_tk, 0); xrR, yrR = _vn(xR_tk, 0)
        z_tkb = MNCN * hz; z_tkt = (MNCN + H_tk) * hz
        for xs, ys, xe, ye, z0, z1, nm in [
            (xrL,yrL, xrR,yrR, z_tkb,z_tkb, "Đáy TK"),
            (xrL,yrL, xrR,yrR, z_tkt,z_tkt, "Đỉnh TK"),
            (xrL,yrL, xrL,yrL, z_tkb,z_tkt, "Cột trái TK"),
            (xrR,yrR, xrR,yrR, z_tkb,z_tkt, "Cột phải TK"),
        ]:
            fig.add_trace(go.Scatter3d(
                x=[xs,xe], y=[ys,ye], z=[z0,z1],
                mode="lines+markers",
                line=dict(color="#e74c3c", width=6),
                marker=dict(size=5, color="#e74c3c"),
                name=nm, showlegend=True,
            ))
        fig.add_trace(go.Scatter3d(
            x=[(xrL+xrR)/2], y=[(yrL+yrR)/2], z=[(z_tkb+z_tkt)/2],
            mode="text", text=[f"B={B_tk}m × H={H_tk}m"],
            textfont=dict(color="#e74c3c", size=11), showlegend=False,
        ))

        # =========================================================
        # LỚP 2 — TRẮC DỌC (đường line — đúng cho profile)
        # =========================================================
        s_range = np.linspace(lt_v[0], lt_v[-1], 100)
        XP, YP, ZP = [], [], []
        for s in s_range:
            xc, yc = _vn(s, 0)
            XP.append(xc); YP.append(yc)
            ZP.append(float(np.interp(s, lt_v, vz_v)) * hz)
        fig.add_trace(go.Scatter3d(x=XP, y=YP, z=ZP, mode="lines",
                                   line=dict(color="#27ae60", width=4),
                                   name="Địa hình TN tim tuyến"))

        x_t1  = geo.get("x_t1", x0); x_t2 = geo.get("x_t2", x_end)
        y_t   = geo.get("y_t", 4.0); y_dn  = geo.get("y_dinh", 4.5)
        R_geo = geo.get("R", 5000);  i_geo  = geo.get("i_val", 0.04)
        y_base = geo.get("y_base_goc", MNTT)
        def _rdz(s):
            if   s < x_t1: yr = y_t  - i_geo*(x_t1 - s)
            elif s > x_t2: yr = y_t  - i_geo*(s  - x_t2)
            else:           yr = y_dn - (s - x_tim)**2 / (2*R_geo)
            return (yr + y_base) * hz
        XRD, YRD, ZRD = [], [], []
        for s in np.linspace(x0-5, x_end+5, 80):
            xc, yc = _vn(s, 0)
            XRD.append(xc); YRD.append(yc); ZRD.append(_rdz(s))
        fig.add_trace(go.Scatter3d(x=XRD, y=YRD, z=ZRD, mode="lines",
                                   line=dict(color="#e74c3c", width=5),
                                   name="Đường đỏ thiết kế"))

        # =========================================================
        # LỚP 3 — KẾT CẤU NHỊP (Mesh3d KHỐI 3D)
        # =========================================================

        # Lớp phủ BTN
        fig.add_trace(_abox(x0, x_end, -bc/2, bc/2,
                            z_deck, z_phu, "#2c3e50", 0.92, "Lớp phủ BTN"))

        # Bản mặt cầu
        fig.add_trace(_abox(x0, x_end, -bc/2, bc/2,
                            z_bant, z_deck, "#d5d8dc", 0.82, "Bản mặt cầu"))

        # Dầm chính — mỗi dầm 1 hộp
        bf_half = 0.20
        y_first = -bc/2 + oh_dam
        for i_sp, (xs, xe) in enumerate(spans):
            sl_sp = (i_sp == 0)
            for i_d in range(n_dam):
                yd = y_first + i_d * kc_dam
                fig.add_trace(_abox(
                    xs, xe, yd - bf_half, yd + bf_half,
                    z_beamb, z_bant, "#85929e", 0.92,
                    f"Dầm {kcn.get('loai_dam','')}" if (sl_sp and i_d == 0) else "",
                    sl=sl_sp and i_d == 0,
                ))

        # =========================================================
        # LỚP 4 — TRỤ CẦU (Mesh3d KHỐI 3D)
        # =========================================================

        for i_p, xt in enumerate(piers):
            sl = (i_p == 0)

            # Xà mũ
            fig.add_trace(_abox(xt-cap_thick, xt+cap_thick, -cap_W, cap_W,
                                z_capb, z_capt, "#d5dbdb", 0.90,
                                "Xà mũ" if sl else "", sl=sl))

            # Thân trụ (n_cot cột)
            col_offs = np.linspace(-cap_W*0.6, cap_W*0.6, n_cot)
            for i_c, off_c in enumerate(col_offs):
                fig.add_trace(_abox(
                    xt - W_tru/2, xt + W_tru/2,
                    off_c - W_cot/2, off_c + W_cot/2,
                    z_shb, z_sht, "#c8d6c0", 0.92,
                    f"Thân trụ T{i_p+1}" if (sl and i_c == 0) else "",
                    sl=sl and i_c == 0,
                ))

        # =========================================================
        # LỚP 5 — MÓNG (Mesh3d KHỐI + cọc lines)
        # =========================================================

        n_coc_row = 3 if be_W >= 2.5 else 2
        for i_p, xt in enumerate(piers):
            sl = (i_p == 0)

            # Bệ cọc (hộp)
            fig.add_trace(_abox(xt-be_long, xt+be_long, -be_W, be_W,
                                z_beb, z_bet, "#aab7b8", 0.90,
                                "Bệ cọc" if sl else "", sl=sl))

            # Cọc (line - OK vì cọc thực tế cũng tròn/mảnh)
            c_ds = np.linspace(-be_W*0.65, be_W*0.65, n_coc_row)
            c_ls = np.linspace(-be_long*0.65, be_long*0.65, n_coc_row)
            for dl in c_ls:
                for dt in c_ds:
                    xp, yp = _vn(xt + dl, dt)
                    lbl_coc = (f"Cọc Ø{int(D_coc*1000)}mm L={L_coc:.0f}m"
                               if (sl and dl == c_ls[0] and dt == c_ds[0]) else "")
                    fig.add_trace(go.Scatter3d(
                        x=[xp, xp], y=[yp, yp], z=[z_bet, z_pileb],
                        mode="lines",
                        line=dict(color="#4a4a4a", width=5),
                        name=lbl_coc,
                        showlegend=bool(lbl_coc),
                    ))

        # =========================================================
        # LỚP 6 — MỐ HAI ĐẦU (Mesh3d KHỐI 3D)
        # =========================================================

        for xm, nm in [(x0, "Mố trái"), (x_end, "Mố phải")]:
            sl = (nm == "Mố trái")
            sign = 1 if xm == x0 else -1
            fig.add_trace(_abox(xm, xm + sign*mo_L, -bc/2-0.5, bc/2+0.5,
                                z_beb, z_deck, "#c0a06b", 0.85, nm, sl=sl))

        # ── Title ─────────────────────────────────────────────────────────
        fig.update_layout(
            title=dict(
                text=(f"<b>MÔI TRƯỜNG 3D TỔNG HỢP</b><br>"
                      f"<sup>{n_nhip}×{L_nhip}m {kcn.get('loai_dam','').upper()} | "
                      f"B={bc}m | H_trụ={H_tru:.1f}m | "
                      f"Cọc Ø{int(D_coc*1000)}mm L={L_coc:.0f}m | "
                      f"Tĩnh không B={B_tk}m×H={H_tk}m</sup>"),
                x=0.5, font=dict(size=12),
            ),
            legend=dict(
                orientation="v", x=1.01, y=0.5,
                font=dict(size=8),
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor="#ccc", borderwidth=1,
            ),
        )

    except Exception as exc:
        import traceback
        print(f"[add_all_to_terrain_fig] Lỗi: {exc}\n{traceback.format_exc()}")


# ===========================================================================
# 7. BÌNH ĐỒ CẦU (MẶT BẰNG — nhìn từ trên xuống)
# ===========================================================================
def ve_binh_do_2d(d, df_tim_line=None):
    """Bình đồ cầu: mặt bằng nhìn từ trên, bao gồm dầm, mố, trụ, TK."""
    kcn  = d.get("kcn_result") or d.get("ai_result", {})
    geo  = d.get("geo_logic", {})
    L_cau  = float(geo.get("L_cau", 120))
    bc     = float(d.get("bc", 12.0))
    B_tk   = float(d.get("B", 20.0))
    n_nhip = int(kcn.get("tong_so_nhip", 3))
    x0     = float(geo.get("x_mo_trai", -L_cau / 2))
    x_end  = float(geo.get("x_mo_phai", x0 + L_cau))
    x_tim  = float(geo.get("x_tim_clearance", (x0 + x_end) / 2))
    piers  = _calc_pier_positions(x0, x_end, n_nhip, x_tim, B_tk)
    cap_W  = max(2.0, bc * 0.18 + 1.0)
    mo_W   = 3.5

    fig = go.Figure()

    # Lớp đất / sông nền
    _lt_col = _z_col = None
    if df_tim_line is not None and not df_tim_line.empty:
        _lt_col = next((c for c in df_tim_line.columns if 'ý trình' in c or c.lower()=='ly_trinh'), None)
        _z_col  = next((c for c in df_tim_line.columns if c.upper()=='Z'), None)

    # Vùng sông (tĩnh không)
    fig.add_shape(type="rect",
        x0=x_tim - B_tk / 2, x1=x_tim + B_tk / 2,
        y0=-B_tk * 0.7, y1=B_tk * 0.7,
        fillcolor="rgba(52,152,219,0.18)", line=dict(color="#2980b9", width=1.5, dash="dot"))
    fig.add_annotation(x=x_tim, y=0,
        text=f"Sông/Kênh<br>B={B_tk:.1f}m", showarrow=False,
        font=dict(size=9, color="#2980b9"), bgcolor="rgba(255,255,255,0.7)")

    # Mặt cầu (fill nhạt)
    fig.add_trace(go.Scatter(
        x=[x0, x_end, x_end, x0, x0],
        y=[-bc/2, -bc/2, bc/2, bc/2, -bc/2],
        fill="toself", fillcolor="rgba(213,216,220,0.55)",
        line=dict(color="#2c3e50", width=2),
        name="Mặt cầu", mode="lines",
        hovertemplate=f"Mặt cầu B={bc:.1f}m<extra></extra>"
    ))

    # Lan can (đường đậm 2 bên)
    for sy in [-1, 1]:
        fig.add_shape(type="line",
            x0=x0, y0=sy * bc/2, x1=x_end, y1=sy * bc/2,
            line=dict(color="#2c3e50", width=3))

    # Tim cầu (dashdot)
    fig.add_shape(type="line",
        x0=x0 - 8, y0=0, x1=x_end + 8, y1=0,
        line=dict(color="#e74c3c", width=1, dash="dashdot"))

    # Mố
    for xm, lbl in [(x0, "Mố trái"), (x_end, "Mố phải")]:
        sign = 1 if xm == x0 else -1
        fig.add_trace(go.Scatter(
            x=[xm, xm + sign * mo_W, xm + sign * mo_W, xm, xm],
            y=[-bc/2 - 0.6, -bc/2 - 0.6, bc/2 + 0.6, bc/2 + 0.6, -bc/2 - 0.6],
            fill="toself", fillcolor="rgba(192,160,107,0.65)",
            line=dict(color="#7d6608", width=2),
            name=lbl, mode="lines",
        ))
        # Tường cánh
        for sy in [-1, 1]:
            yw_end = sy * (bc/2 + 0.6 + mo_W * 0.8)
            fig.add_trace(go.Scatter(
                x=[xm + sign * 0.3, xm + sign * mo_W * 1.6],
                y=[sy * (bc/2 + 0.6), yw_end],
                mode="lines", line=dict(color="#7d6608", width=1.5),
                showlegend=False
            ))

    # Trụ
    tru_L_half = 0.8
    for i, xt in enumerate(piers):
        fig.add_trace(go.Scatter(
            x=[xt - tru_L_half, xt + tru_L_half, xt + tru_L_half,
               xt - tru_L_half, xt - tru_L_half],
            y=[-cap_W, -cap_W, cap_W, cap_W, -cap_W],
            fill="toself", fillcolor="rgba(133,146,158,0.75)",
            line=dict(color="#566573", width=1.5),
            name=f"Trụ T{i+1}", mode="lines",
        ))
        fig.add_annotation(x=xt, y=0, text=f"T{i+1}",
            showarrow=False, font=dict(size=8, color="white"),
            bgcolor="rgba(86,101,115,0.85)")

    # Khung tĩnh không (mặt bằng)
    fig.add_shape(type="rect",
        x0=x_tim - B_tk/2, x1=x_tim + B_tk/2,
        y0=-B_tk/2 - 0.3, y1=B_tk/2 + 0.3,
        line=dict(color="#e74c3c", width=2.5, dash="dash"),
        fillcolor="rgba(231,76,60,0.04)")

    # Dimensions
    _dim_h(fig, bc/2 + 2.5, x0, x_end, f"L_cầu = {L_cau:.1f} m", dy=0)
    if piers:
        _dim_h(fig, -bc/2 - 2.5, piers[0], piers[-1] if len(piers) > 1 else x_end,
               f"Khoảng TT = {(piers[-1] if len(piers)>1 else x_end) - piers[0]:.1f} m", dy=0)
    _dim_v(fig, x_end + mo_W + 1.5, -bc/2, bc/2, f"B_c = {bc:.1f} m", dx=0.5)
    _dim_v(fig, x_tim + B_tk/2 + 1.2, -B_tk/2, B_tk/2, f"B_tk = {B_tk:.1f} m",
           color="#e74c3c", dx=0.5)

    fig.update_layout(
        title=dict(
            text=f"BÌNH ĐỒ CẦU — {n_nhip} nhịp | L={L_cau:.1f}m | B_c={bc:.1f}m",
            x=0.5, font=dict(size=12)
        ),
        xaxis=dict(title="Lý trình (m)", showgrid=True, gridcolor="#ecf0f1",
                   scaleanchor="y", scaleratio=1),
        yaxis=dict(title="Ngang (m)", showgrid=True, gridcolor="#ecf0f1"),
        height=420, template="plotly_white",
        legend=dict(orientation="h", y=-0.22, font=dict(size=9)),
        margin=dict(l=60, r=40, t=60, b=90),
        hovermode="closest",
    )
    return fig


# ===========================================================================
# 8. MẶT CẮT NGANG TẠI VỊ TRÍ MỐ / TRỤ
# ===========================================================================
def ve_mcn_vi_tri(d, vi_tri='mo_trai', df_geology=None):
    """
    MCN cắt vuông góc tim cầu tại vị trí mố hoặc trụ cụ thể.
    vi_tri: 'mo_trai' | 'mo_phai' | 'tru_1' | 'tru_2' | ...
    df_geology: DataFrame với cột Lý trình, Offset, Z (từ file .NTD)
    """
    kcn   = d.get("kcn_result") or d.get("ai_result", {})
    geo   = d.get("geo_logic", {})
    tru_r = d.get("tru_result", {}) or {}
    mong  = d.get("mong_result", {}) or {}

    bc     = float(d.get("bc", 12.0))
    B_tk   = float(d.get("B", 20.0))
    H_tk   = float(d.get("H", 3.0))
    H_tru  = float(d.get("H_tru_est", 5.0))
    cao_dd = float(d.get("cao_day_dam", H_tru + 5.0))
    H_dam  = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    t_ban  = float(d.get("t_ban_mm", 200)) / 1000.0
    n_nhip = int(kcn.get("tong_so_nhip", 3))
    MNCN   = float(d.get("MNCN", 3.5))
    MNTT   = float(d.get("MNTT", 2.0))
    MNTN   = float(d.get("MNTN", 0.5))
    h_tn   = float(d.get("h_tn_tb", 2.0))
    L_cau  = float(geo.get("L_cau", 120))
    x0     = float(geo.get("x_mo_trai", -L_cau / 2))
    x_end  = float(geo.get("x_mo_phai", x0 + L_cau))
    x_tim  = float(geo.get("x_tim_clearance", (x0 + x_end) / 2))
    piers  = _calc_pier_positions(x0, x_end, n_nhip, x_tim, B_tk)
    cap_W  = max(2.0, bc * 0.18 + 1.0)
    be_W   = cap_W + 0.8

    if vi_tri == 'mo_trai':
        x_cut = x0;   title_vt = "MỐ TRÁI"
    elif vi_tri == 'mo_phai':
        x_cut = x_end; title_vt = "MỐ PHẢI"
    else:
        idx = int(vi_tri.replace('tru_', '')) - 1
        x_cut = piers[idx] if idx < len(piers) else x_tim
        title_vt = f"TRỤ T{idx + 1}"

    is_mo = vi_tri.startswith('mo')
    fig = go.Figure()

    # ── Địa hình cắt ngang ──────────────────────────────────────────────
    y_terr = z_terr = None
    if df_geology is not None and not df_geology.empty:
        need = {'Lý trình', 'Offset', 'Z'}
        if need <= set(df_geology.columns):
            df_cut = df_geology[abs(df_geology['Lý trình'] - x_cut) <= 5.0].copy()
            if not df_cut.empty:
                df_cut = df_cut.sort_values('Offset')
                y_terr = df_cut['Offset'].values.astype(float)
                z_terr = df_cut['Z'].values.astype(float)

    if y_terr is None:
        spread = max(bc * 2.5, B_tk + 5)
        y_terr = np.array([-spread, -bc, bc, spread])
        z_terr = np.array([h_tn, h_tn, h_tn, h_tn])

    z_min = float(z_terr.min()) - 3.0

    # Fill đất
    fig.add_trace(go.Scatter(
        x=np.concatenate([y_terr, y_terr[::-1]]),
        y=np.concatenate([z_terr, np.full_like(z_terr, z_min)]),
        fill="toself", fillcolor=_C["dat"],
        line=dict(color="#6d4c41", width=2),
        name="Địa hình", mode="lines"
    ))

    # ── Mực nước (chỉ ở trụ và tại tim) ────────────────────────────────
    y_nw_range = [y_terr[0], y_terr[-1]]
    if not is_mo:
        for z_w, lbl, clr in [
            (MNCN, f"MNCN={MNCN:.3f}m", "#c0392b"),
            (MNTT, f"MNTT={MNTT:.3f}m", "#2980b9"),
            (MNTN, f"MNTN={MNTN:.3f}m", "#1abc9c"),
        ]:
            fig.add_trace(go.Scatter(
                x=y_nw_range, y=[z_w, z_w], mode="lines+text",
                line=dict(color=clr, width=1.5, dash="dot"),
                text=[lbl, ""], textposition="top left",
                textfont=dict(size=8, color=clr), name=lbl,
            ))
        # Fill vùng nước
        fig.add_trace(go.Scatter(
            x=[y_nw_range[0], y_nw_range[1], y_nw_range[1], y_nw_range[0]],
            y=[MNTN, MNTN, MNCN, MNCN],
            fill="toself", fillcolor=_C["nuoc"],
            line=dict(color="rgba(0,0,0,0)"),
            mode="lines", showlegend=False, hoverinfo="skip"
        ))

    # ── Kết cấu ─────────────────────────────────────────────────────────
    z_deck = cao_dd + H_dam + t_ban

    if is_mo:
        mo_dep = 3.5
        _poly(fig, [-bc/2 - 0.5, bc/2 + 0.5, bc/2 + 0.5, -bc/2 - 0.5],
              [h_tn, h_tn, z_deck, z_deck],
              _C["moc"], _C["be_dk"], "Thân mố")
        for sy in [-1, 1]:
            xw0 = sy * (bc/2 + 0.5)
            xw1 = sy * (bc/2 + 0.5 + mo_dep)
            _poly(fig, [xw0, xw1, xw1, xw0],
                  [z_min, z_min, h_tn, h_tn],
                  "rgba(192,160,107,0.35)", _C["be_dk"],
                  "Tường cánh" if sy == -1 else "", showlegend=(sy == -1))
    else:
        # Bệ cọc
        cap_H  = 0.80; be_H = 1.50
        z_capb = cao_dd - cap_H
        z_shb  = z_capb - H_tru
        z_beb  = z_shb - be_H

        _poly(fig, [-be_W, be_W, be_W, -be_W],
              [z_beb, z_beb, z_shb, z_shb],
              _C["be"], _C["be_dk"], "Bệ cọc")

        # Thân cột
        loai_t = str(tru_r.get("loai_tru", "Thân cột 2 trụ"))
        n_cot  = 3 if "3" in loai_t else (2 if "cột" in loai_t.lower() else 1)
        W_cot  = min(1.0, bc * 0.06 + 0.4)
        col_offs = np.linspace(-cap_W * 0.6, cap_W * 0.6, n_cot)
        for ic, off_c in enumerate(col_offs):
            _poly(fig, [off_c - W_cot/2, off_c + W_cot/2,
                        off_c + W_cot/2, off_c - W_cot/2],
                  [z_shb, z_shb, z_capb, z_capb],
                  _C["btong"], _C["btong_dk"],
                  "Thân cột" if ic == 0 else "", showlegend=(ic == 0))

        # Xà mũ
        _poly(fig, [-cap_W, cap_W, cap_W, -cap_W],
              [z_capb, z_capb, cao_dd, cao_dd],
              _C["btong"], _C["dam_dk"], "Xà mũ")

        # Cọc
        D_coc = float(mong.get("D_coc_mm", 600)) / 1000.0 if mong else 0.6
        L_coc = float(mong.get("L_coc_tu", 35)) if mong else 35
        n_coc = 3 if be_W >= 2.5 else 2
        for i_coc, xc in enumerate(np.linspace(-be_W * 0.7, be_W * 0.7, n_coc)):
            fig.add_trace(go.Scatter(
                x=[xc, xc], y=[z_beb, z_beb - L_coc],
                mode="lines",
                line=dict(color=_C["be_dk"], width=max(3, int(D_coc * 6))),
                name=f"Cọc Ø{int(D_coc*1000)}mm" if i_coc == 0 else "",
                showlegend=(i_coc == 0)
            ))

        # Dimensions trụ
        _dim_v(fig, cap_W + 0.6, z_shb, z_capb, f"H_trụ={H_tru:.1f}m", dx=0.2)
        _dim_h(fig, z_beb - 0.5, -be_W, be_W, f"B_bệ={be_W*2:.1f}m", dy=0)

    # Bản mặt cầu
    _poly(fig, [-bc/2, bc/2, bc/2, -bc/2],
          [cao_dd + H_dam, cao_dd + H_dam, z_deck, z_deck],
          _C["ban"], _C["btong_dk"], "Bản mặt cầu")

    # Lan can (ký hiệu)
    for sy in [-1, 1]:
        _poly(fig,
              [sy * bc/2 - sy*0.3, sy * bc/2, sy * bc/2, sy * bc/2 - sy*0.3],
              [z_deck, z_deck, z_deck + 1.1, z_deck + 1.1],
              _C["lan_can"], "#2c3e50",
              "Lan can" if sy == -1 else "", showlegend=(sy == -1))

    # Dimensions chung
    _dim_h(fig, z_deck + 1.5, -bc/2, bc/2, f"B_cầu = {bc:.1f} m", dy=0)
    if not is_mo:
        _dim_h(fig, z_deck + 2.2, -cap_W, cap_W, f"B_xà mũ = {cap_W*2:.1f} m",
               color="#8e44ad", dy=0)

    fig.update_layout(
        title=dict(
            text=f"MẶT CẮT NGANG — {title_vt} | Lý trình ≈ {x_cut:.1f} m",
            x=0.5, font=dict(size=12)
        ),
        xaxis=dict(title="Ngang cầu (m)", showgrid=True, gridcolor="#ecf0f1"),
        yaxis=dict(title="Cao độ (m)", showgrid=True, gridcolor="#ecf0f1",
                   scaleanchor="x", scaleratio=1),
        height=540, template="plotly_white",
        legend=dict(orientation="h", y=-0.20, font=dict(size=9)),
        margin=dict(l=65, r=40, t=60, b=100),
    )
    return fig


# ===========================================================================
# 9. CHẾ ĐỘ HIỂN THỊ 3D (tương tự Revit: Shaded / Wireframe / X-Ray / Realistic)
# ===========================================================================
def apply_render_mode(fig, mode="Shaded"):
    """
    Áp dụng chế độ hiển thị lên figure 3D sau khi đã tạo.
    mode: 'Shaded' | 'Wireframe' | 'X-Ray' | 'Realistic'
    """
    for trace in fig.data:
        if isinstance(trace, go.Mesh3d):
            if mode == "Wireframe":
                trace.opacity = 0.0
                # Bật hiển thị wireframe overlay qua intensity
                trace.flatshading = False
            elif mode == "X-Ray":
                trace.opacity = min(float(trace.opacity or 0.5), 0.18)
                trace.flatshading = False
            elif mode == "Realistic":
                trace.flatshading = False
                trace.lighting = dict(
                    ambient=0.35, diffuse=0.90, specular=0.70,
                    roughness=0.25, fresnel=0.50
                )
                trace.lightposition = dict(x=200, y=200, z=500)
            else:  # Shaded (mặc định)
                trace.flatshading = True
                trace.lighting = dict(ambient=0.65, diffuse=0.85, specular=0.2)

    if mode == "Wireframe":
        # Thêm contour lines cho tất cả Mesh3d
        for trace in fig.data:
            if isinstance(trace, go.Mesh3d):
                trace.contour = go.mesh3d.Contour(show=True, color="#2c3e50", width=2)
    return fig
