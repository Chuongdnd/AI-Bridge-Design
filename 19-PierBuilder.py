"""
19-PierBuilder.py — Engine dựng TRỤ LẮP GHÉP (Phase 1 — MVP).

Trụ = assembly nhiều bộ phận, mỗi bộ phận là một KHỐI ĐÙN mặt cắt theo 1 trục:
  • Bệ móng (footing): hộp chữ nhật, đùn theo phương ĐỨNG (z).
  • Thân (stem)      : mặt cắt bằng (chữ nhật / tròn), đùn ĐỨNG (z); cao co giãn.
  • Xà mũ (cap)      : đùn theo phương DỌC cầu (x) của bóng mặt đứng NGANG (y-z),
                       có CÔNG XÔN (vát mỏng dần ra hai đầu).

Hệ trục dựng (đồng bộ 3D cầu): x = dọc cầu, y = ngang cầu, z = cao độ.
Khung cục bộ của trụ: z = 0 ở đáy bệ, tâm tại x = 0, y = 0.

Module thuần Python + Plotly (không phụ thuộc Streamlit) để dễ kiểm thử.
"""
import numpy as np
import plotly.graph_objects as go


# ── Màu các bộ phận ──────────────────────────────────────────────────────────
_COL = {
    "be":     "#7f8c9b",   # bệ móng
    "than":   "#5d8aa8",   # thân trụ
    "xa_mu":  "#6d9dc5",   # xà mũ
}


def default_pier(ten: str = "Trụ mẫu") -> dict:
    """Bản ghi trụ MVP: bệ + thân + mũ (kèm công xôn). Đơn vị mét."""
    return {
        "id": "", "ten": ten, "loai": "tru", "H_ref": 8.0,
        "footing": {"W": 4.0, "D": 3.0, "H": 1.5},
        "stem":    {"shape": "rect", "W": 1.6, "D": 1.2, "H": 5.0},
        "cap":     {"W": 8.0, "D": 1.8, "H": 1.2, "cant": 2.0, "H_tip": 0.6},
    }


# ── Hình học cơ bản: đùn một đa giác LỒI thành lăng trụ ───────────────────────
def _prism(poly_ab, plane: str, c0: float, clen: float):
    """Đùn đa giác lồi poly_ab (list (a,b), CCW) dọc trục thứ 3.

    plane='xy' → (a,b)=(x,y), đùn theo z (c0..c0+clen).
    plane='yz' → (a,b)=(y,z), đùn theo x.
    Trả về (X, Y, Z, I, J, K) cho go.Mesh3d (đa giác giả định LỒI → fan).
    """
    n = len(poly_ab)
    if n < 3 or abs(clen) < 1e-9:
        return None
    c1 = c0 + clen
    X, Y, Z = [], [], []

    def _xyz(a, b, c):
        if plane == "xy":
            return a, b, c          # (x, y, z)
        return c, a, b              # plane 'yz': (x=c, y=a, z=b)

    for (a, b) in poly_ab:          # ring đáy (0..n-1)
        x, y, z = _xyz(a, b, c0)
        X.append(x); Y.append(y); Z.append(z)
    for (a, b) in poly_ab:          # ring đỉnh (n..2n-1)
        x, y, z = _xyz(a, b, c1)
        X.append(x); Y.append(y); Z.append(z)

    I, J, K = [], [], []
    # Hai nắp (fan từ đỉnh 0)
    for i in range(1, n - 1):
        I += [0, n]; J += [i, n + i + 1]; K += [i + 1, n + i]
    # Thành bên: mỗi cạnh → 2 tam giác
    for i in range(n):
        i2 = (i + 1) % n
        b0, b1, t0, t1 = i, i2, n + i, n + i2
        I += [b0, b0]; J += [b1, t1]; K += [t1, t0]
    return X, Y, Z, I, J, K


def _rect(w_a: float, w_b: float):
    """Đa giác chữ nhật tâm gốc, kích thước w_a×w_b (CCW)."""
    a, b = w_a / 2.0, w_b / 2.0
    return [(-a, -b), (a, -b), (a, b), (-a, b)]


def _circle(d: float, n: int = 28):
    r = d / 2.0
    return [(r * np.cos(t), r * np.sin(t))
            for t in np.linspace(0, 2 * np.pi, n, endpoint=False)]


def _mesh(parts, color, name, legend=True, opacity=0.96):
    if parts is None:
        return None
    X, Y, Z, I, J, K = parts
    return go.Mesh3d(x=X, y=Y, z=Z, i=I, j=J, k=K, color=color,
                     opacity=opacity, name=name, showlegend=legend,
                     hovertemplate=f"{name}<extra></extra>")


def _cap_silhouette(Wc, Hc, cant, H_tip):
    """Danh sách đa giác LỒI (trong mặt phẳng y-z) của xà mũ có công xôn.
    z tham chiếu: đáy lõi = 0, đỉnh = Hc. Trả về list[poly_yz]."""
    Wcore = max(0.0, Wc - 2.0 * cant)
    z_top = Hc
    z_tip = Hc - max(0.0, min(H_tip, Hc))      # đáy tại mút công xôn
    polys = []
    # Lõi giữa (hộp)
    if Wcore > 1e-6:
        polys.append([(-Wcore / 2, 0.0), (Wcore / 2, 0.0),
                      (Wcore / 2, z_top), (-Wcore / 2, z_top)])
    # Công xôn phải (hình thang: đáy nghiêng từ lõi lên mút)
    if cant > 1e-6:
        polys.append([(Wcore / 2, 0.0), (Wc / 2, z_tip),
                      (Wc / 2, z_top), (Wcore / 2, z_top)])
        polys.append([(-Wc / 2, z_tip), (-Wcore / 2, 0.0),
                      (-Wcore / 2, z_top), (-Wc / 2, z_top)])
    return polys


def build_pier_mesh_traces(pier: dict, H_tru: float = None,
                           x_ctr: float = 0.0, z_base: float = 0.0) -> list:
    """Trả về list go.Mesh3d của 1 trụ.

    H_tru : nếu cho (m), chiều cao THÂN tự co để (đáy bệ→đỉnh mũ) = H_tru.
    x_ctr : lý trình tâm trụ (m).   z_base: cao độ đáy bệ (m).
    """
    p = pier or {}
    f = p.get("footing", {}); s = p.get("stem", {}); c = p.get("cap", {})
    Hf = float(f.get("H", 1.5))
    Hc = float(c.get("H", 1.2))
    Hs = float(s.get("H", 5.0))
    if H_tru is not None:                       # co thân theo chiều cao trụ
        Hs = max(0.3, float(H_tru) - Hf - Hc)

    traces = []
    z0 = z_base

    # 1) Bệ móng — hộp, đùn z
    fb = _prism(_rect(float(f.get("D", 3.0)), float(f.get("W", 4.0))),
                "xy", z0, Hf)
    traces.append(_mesh(_offset(fb, x_ctr, 0.0), _COL["be"], "Bệ móng"))

    # 2) Thân — mặt cắt bằng đùn z
    z_stem = z0 + Hf
    if str(s.get("shape", "rect")) == "circle":
        poly = _circle(float(s.get("W", 1.2)))
    else:
        poly = _rect(float(s.get("D", 1.2)), float(s.get("W", 1.6)))
    sb = _prism(poly, "xy", z_stem, Hs)
    traces.append(_mesh(_offset(sb, x_ctr, 0.0), _COL["than"], "Thân trụ"))

    # 3) Xà mũ — bóng y-z (công xôn) đùn theo x (dọc cầu)
    z_cap = z_stem + Hs
    Dc = float(c.get("D", 1.8))
    for _poly_yz in _cap_silhouette(float(c.get("W", 8.0)), Hc,
                                    float(c.get("cant", 0.0)),
                                    float(c.get("H_tip", 0.0))):
        # poly trong (y,z) với z bắt đầu từ 0 → cộng z_cap
        _poly = [(a, b + z_cap) for (a, b) in _poly_yz]
        cb = _prism(_poly, "yz", x_ctr - Dc / 2.0, Dc)
        traces.append(_mesh(cb, _COL["xa_mu"], "Xà mũ", legend=False))

    return [t for t in traces if t is not None]


def _offset(parts, dx: float, dy: float):
    """Dịch một mesh theo (dx, dy) trong mặt phẳng x-y."""
    if parts is None:
        return None
    X, Y, Z, I, J, K = parts
    return ([x + dx for x in X], [y + dy for y in Y], Z, I, J, K)


def build_pier_preview_fig(pier: dict, H_tru: float = None) -> go.Figure:
    """Figure 3D xem trước 1 trụ (panel thư viện)."""
    fig = go.Figure(build_pier_mesh_traces(pier, H_tru=H_tru))
    fig.update_layout(
        scene=dict(xaxis_title="Dọc cầu (m)", yaxis_title="Ngang cầu (m)",
                   zaxis_title="Cao độ (m)", aspectmode="data"),
        template="plotly_dark", height=520,
        margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="#0e1117",
        scene_camera=dict(eye=dict(x=1.6, y=-1.6, z=1.0)),
    )
    return fig


def pier_front_fig(pier: dict, H_tru: float = None) -> go.Figure:
    """Mặt đứng NGANG cầu (y-z) — kiểm tra nhanh công xôn xà mũ."""
    p = pier or {}
    f = p.get("footing", {}); s = p.get("stem", {}); c = p.get("cap", {})
    Hf = float(f.get("H", 1.5)); Hc = float(c.get("H", 1.2))
    Hs = float(s.get("H", 5.0))
    if H_tru is not None:
        Hs = max(0.3, float(H_tru) - Hf - Hc)
    fig = go.Figure()

    def _poly2d(xs, zs, color, name):
        fig.add_trace(go.Scatter(x=list(xs) + [xs[0]], y=list(zs) + [zs[0]],
                                 fill="toself", mode="lines",
                                 line=dict(color=color, width=2),
                                 fillcolor=color, opacity=0.55, name=name))

    Wf = float(f.get("W", 4.0))
    _poly2d([-Wf/2, Wf/2, Wf/2, -Wf/2], [0, 0, Hf, Hf], _COL["be"], "Bệ")
    z1 = Hf
    Ws = float(s.get("W", 1.6))
    _poly2d([-Ws/2, Ws/2, Ws/2, -Ws/2], [z1, z1, z1+Hs, z1+Hs],
            _COL["than"], "Thân")
    z2 = z1 + Hs
    for poly in _cap_silhouette(float(c.get("W", 8.0)), Hc,
                                float(c.get("cant", 0.0)),
                                float(c.get("H_tip", 0.0))):
        ys = [pt[0] for pt in poly]; zs = [pt[1] + z2 for pt in poly]
        _poly2d(ys, zs, _COL["xa_mu"], "Xà mũ")
    fig.update_layout(template="plotly_dark", height=360,
                      xaxis_title="Ngang cầu (m)", yaxis_title="Cao độ (m)",
                      yaxis_scaleanchor="x", yaxis_scaleratio=1.0,
                      showlegend=False, margin=dict(l=0, r=0, t=10, b=0),
                      paper_bgcolor="#0e1117")
    return fig


def pier_total_height(pier: dict, H_tru: float = None) -> float:
    p = pier or {}
    Hf = float(p.get("footing", {}).get("H", 1.5))
    Hc = float(p.get("cap", {}).get("H", 1.2))
    Hs = float(p.get("stem", {}).get("H", 5.0))
    if H_tru is not None:
        Hs = max(0.3, float(H_tru) - Hf - Hc)
    return Hf + Hs + Hc
