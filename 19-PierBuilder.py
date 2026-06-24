"""
19-PierBuilder.py — Engine dựng TRỤ LẮP GHÉP (Phase 1).

Trụ = 3 BỘ PHẬN, mỗi bộ phận có MẶT CẮT riêng (upload DXF như dầm) rồi ĐÙN
thành khối đặc (hỗ trợ lỗ rỗng qua tam giác hóa earcut của ezdxf):

  • Bệ trụ  (be)   : mặt cắt = MẶT BẰNG (ngang × dọc) → đùn ĐỨNG theo cao H.
  • Thân trụ(than) : mặt cắt = MẶT BẰNG (ngang × dọc) → đùn ĐỨNG theo cao H
                     (cao co giãn theo chiều cao trụ thực tế khi gắn cầu).
  • Xà mũ   (xa_mu): mặt cắt = MẶT ĐỨNG NGANG cầu (đã gồm công xôn) → đùn
                     theo DỌC cầu theo chiều sâu D.

Mặt cắt lưu theo quy ước của BeamBuilder: list [x, z] đơn vị mm, x ngang,
z = 0 ở mép trên & âm dần xuống. Engine quy đổi mm→m khi dựng 3D.

Hệ trục dựng (đồng bộ 3D cầu): x = dọc cầu, y = ngang cầu, z = cao độ.
Khung cục bộ trụ: z = 0 ở đáy bệ, tâm tại x = 0 (lý trình) & y = 0 (tim cầu).

Thuần Python + Plotly + ezdxf (không phụ thuộc Streamlit) để dễ kiểm thử.
"""
import numpy as np
import plotly.graph_objects as go
from ezdxf.math import Vec2
from ezdxf.math._mapbox_earcut import earcut as _earcut

MM = 0.001  # mm → m

_COL = {"be": "#7f8c9b", "than": "#5d8aa8", "xa_mu": "#6d9dc5"}
_ROLE_LABEL = {"be": "Bệ trụ", "than": "Thân trụ", "xa_mu": "Xà mũ"}


# ── Mặt cắt mặc định (mm) ────────────────────────────────────────────────────
def _rect_mm(w: float, h: float) -> dict:
    """Chữ nhật rộng w × cao h (mm), tâm ngang = 0, mép trên z = 0."""
    return {"outer": [[-w / 2, 0.0], [w / 2, 0.0],
                      [w / 2, -h], [-w / 2, -h]], "holes": []}


def _cantilever_cap_mm(W=8000.0, Hc=1200.0, cant=2000.0, Htip=600.0) -> dict:
    """Bóng mặt đứng ngang của xà mũ công xôn (mm): đỉnh phẳng, đáy vát ra mút."""
    core = max(0.0, W / 2 - cant)
    return {"outer": [[-W / 2, 0.0], [W / 2, 0.0],
                      [W / 2, -(Hc - Htip)], [core, -Hc],
                      [-core, -Hc], [-W / 2, -(Hc - Htip)]], "holes": []}


def default_pier(ten: str = "Trụ mẫu") -> dict:
    """Bản ghi trụ MVP với mặt cắt mặc định cho 3 bộ phận."""
    return {
        "id": "", "ten": ten, "loai": "tru", "H_ref": 8.0,
        "parts": {
            "be":    {"section": _rect_mm(4000, 3000), "H": 1.5},
            "than":  {"section": _rect_mm(1600, 1200), "H": 5.0, "flex": True},
            "xa_mu": {"section": _cantilever_cap_mm(), "D": 1.8},
        },
    }


def migrate_pier(p: dict) -> dict:
    """Nâng cấp bản ghi cũ (footing/stem/cap tham số) → mô hình parts."""
    if not isinstance(p, dict):
        return default_pier()
    if "parts" in p:
        return p
    f = p.get("footing", {}); s = p.get("stem", {}); c = p.get("cap", {})
    if str(s.get("shape")) == "circle":
        sec_than = _circle_section_mm(float(s.get("W", 1200)) * 1000)
    else:
        sec_than = _rect_mm(float(s.get("W", 1.6)) * 1000, float(s.get("D", 1.2)) * 1000)
    out = dict(p)
    out["parts"] = {
        "be":    {"section": _rect_mm(float(f.get("W", 4.0)) * 1000,
                                      float(f.get("D", 3.0)) * 1000),
                  "H": float(f.get("H", 1.5))},
        "than":  {"section": sec_than, "H": float(s.get("H", 5.0)), "flex": True},
        "xa_mu": {"section": _cantilever_cap_mm(float(c.get("W", 8.0)) * 1000,
                                                float(c.get("H", 1.2)) * 1000,
                                                float(c.get("cant", 2.0)) * 1000,
                                                float(c.get("H_tip", 0.6)) * 1000),
                  "D": float(c.get("D", 1.8))},
    }
    for k in ("footing", "stem", "cap"):
        out.pop(k, None)
    return out


def _circle_section_mm(d: float, n: int = 28) -> dict:
    r = d / 2.0
    pts = [[r * np.cos(t), r * np.sin(t)]
           for t in np.linspace(0, 2 * np.pi, n, endpoint=False)]
    return {"outer": pts, "holes": []}


# ── Tam giác hóa & đùn mặt cắt thành khối đặc ────────────────────────────────
def _clean_ring(pts):
    """Bỏ điểm trùng liên tiếp & điểm đóng vòng lặp lại (DXF hay thêm)."""
    out = []
    for p in pts:
        if out and abs(p[0] - out[-1][0]) < 1e-6 and abs(p[1] - out[-1][1]) < 1e-6:
            continue
        out.append((p[0], p[1]))
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < 1e-6 \
            and abs(out[0][1] - out[-1][1]) < 1e-6:
        out.pop()
    return out


def _triangulate(outer_ab, holes_ab):
    """Tam giác hóa đa giác (có lỗ) → list (a,b) index-triples theo thứ tự
    vertex gộp [outer..., hole0..., hole1...]. Earcut KHÔNG thêm điểm Steiner
    nên mọi đỉnh tam giác đều là đỉnh đầu vào → tra ngược ra chỉ số được."""
    rings = [list(outer_ab)] + [list(h) for h in (holes_ab or []) if len(h) >= 3]
    idx = {}
    flat = []
    for ring in rings:
        for p in ring:
            flat.append(p)
    for i, p in enumerate(flat):
        idx[(round(p[0], 3), round(p[1], 3))] = i
    ext = [Vec2(p[0], p[1]) for p in outer_ab]
    holes = [[Vec2(q[0], q[1]) for q in h] for h in (holes_ab or []) if len(h) >= 3]
    try:
        tris = _earcut(ext, holes if holes else None)
    except Exception:
        tris = []
    out = []
    for tri in tris:
        try:
            out.append(tuple(idx[(round(v.x, 3), round(v.y, 3))] for v in tri))
        except KeyError:
            continue
    if not out and len(outer_ab) >= 3:           # fallback: fan (đa giác lồi)
        out = [(0, i, i + 1) for i in range(1, len(outer_ab) - 1)]
    return flat, out


def _extrude(outer_ab, holes_ab, plane: str, c0: float, clen: float):
    """Đùn mặt cắt (a,b) dọc trục thứ 3 c0..c0+clen → (X,Y,Z,I,J,K).

    plane='xy' → (a,b)=(x,y) đùn theo z (bệ/thân, đứng).
    plane='yz' → (a,b)=(y,z) đùn theo x (xà mũ, dọc cầu).
    """
    outer_ab = _clean_ring(outer_ab)
    holes_ab = [_clean_ring(h) for h in (holes_ab or [])]
    holes_ab = [h for h in holes_ab if len(h) >= 3]
    if len(outer_ab) < 3 or abs(clen) < 1e-9:
        return None
    flat, tris = _triangulate(outer_ab, holes_ab)
    n = len(flat)
    c1 = c0 + clen
    X, Y, Z = [], [], []

    def _xyz(a, b, c):
        return (a, b, c) if plane == "xy" else (c, a, b)

    for (a, b) in flat:                          # ring đáy 0..n-1
        x, y, z = _xyz(a, b, c0); X.append(x); Y.append(y); Z.append(z)
    for (a, b) in flat:                          # ring đỉnh n..2n-1
        x, y, z = _xyz(a, b, c1); X.append(x); Y.append(y); Z.append(z)

    I, J, K = [], [], []
    for (t0, t1, t2) in tris:                    # nắp đáy
        I.append(t0); J.append(t1); K.append(t2)
    for (t0, t1, t2) in tris:                    # nắp đỉnh (đảo chiều)
        I.append(n + t0); J.append(n + t2); K.append(n + t1)

    # Thành bên: mỗi vòng (outer + holes) nối đáy↔đỉnh
    rings = [list(outer_ab)] + [list(h) for h in (holes_ab or []) if len(h) >= 3]
    base = 0
    for ring in rings:
        m = len(ring)
        for i in range(m):
            i2 = (i + 1) % m
            b0, b1 = base + i, base + i2
            t0, t1 = n + base + i, n + base + i2
            I += [b0, b0]; J += [b1, t1]; K += [t1, t0]
        base += m
    return X, Y, Z, I, J, K


def _bbox_ab(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), max(xs), min(ys), max(ys)


def _part_height_m(part: dict, role: str) -> float:
    """Chiều cao (m) một bộ phận theo trục z."""
    if role == "xa_mu":
        _, _, vmin, vmax = _bbox_ab(part.get("section", {}).get("outer", [[0, 0]]))
        return (vmax - vmin) * MM
    return float(part.get("H", 1.5))


def build_pier_mesh_traces(pier: dict, H_tru: float = None,
                           x_ctr: float = 0.0, z_base: float = 0.0) -> list:
    """Trả về list go.Mesh3d của 1 trụ (3 bộ phận).

    H_tru : nếu cho (m), chiều cao THÂN tự co để (đáy bệ→đỉnh mũ) = H_tru.
    x_ctr : lý trình tâm trụ (m).   z_base: cao độ đáy bệ (m).
    """
    p = migrate_pier(pier or {})
    parts = p.get("parts", {})
    be, than, cap = parts.get("be", {}), parts.get("than", {}), parts.get("xa_mu", {})
    H_be = float(be.get("H", 1.5))
    H_cap = _part_height_m(cap, "xa_mu")
    H_than = float(than.get("H", 5.0))
    if H_tru is not None:
        H_than = max(0.3, float(H_tru) - H_be - H_cap)

    traces = []
    z = z_base

    # 1) BỆ — mặt bằng đùn đứng. section(u,v): u→ngang(y), v→dọc(x).
    traces.append(_plan_mesh(be.get("section"), z, H_be, x_ctr, _COL["be"], "Bệ trụ"))
    z += H_be
    # 2) THÂN
    traces.append(_plan_mesh(than.get("section"), z, H_than, x_ctr,
                             _COL["than"], "Thân trụ"))
    z += H_than
    # 3) XÀ MŨ — mặt đứng ngang (u→ngang y, v→cao z) đùn dọc cầu (x) sâu D.
    traces.append(_cap_mesh(cap.get("section"), z, float(cap.get("D", 1.8)),
                            x_ctr, _COL["xa_mu"], "Xà mũ"))
    return [t for t in traces if t is not None]


def _plan_mesh(section, z0, H, x_ctr, color, name):
    """Bệ/thân: section (u,v) mm → mặt bằng (x=v dọc, y=u ngang), đùn z."""
    if not section or len(section.get("outer", [])) < 3:
        return None
    cu = 0.0  # u (ngang) đã căn tim tại 0 theo parser
    umin, umax, vmin, vmax = _bbox_ab(section["outer"])
    cv = (vmin + vmax) / 2.0  # căn giữa theo dọc cầu

    def _conv(pts):
        return [((v - cv) * MM + x_ctr, (u - cu) * MM) for (u, v) in pts]

    outer = _conv(section["outer"])
    holes = [_conv(h) for h in section.get("holes", [])]
    parts = _extrude(outer, holes, "xy", z0, H)
    return _mesh(parts, color, name)


def _cap_mesh(section, z0, D, x_ctr, color, name):
    """Xà mũ: section (u,v) → (y=u ngang, z=v', cao), đùn dọc cầu x sâu D.
    v' = v - vmin (lật dương lên), đặt đáy thấp nhất tại z0 (đỉnh thân)."""
    if not section or len(section.get("outer", [])) < 3:
        return None
    umin, umax, vmin, vmax = _bbox_ab(section["outer"])

    def _conv(pts):
        return [(u * MM, (v - vmin) * MM + z0) for (u, v) in pts]

    outer = _conv(section["outer"])
    holes = [_conv(h) for h in section.get("holes", [])]
    parts = _extrude(outer, holes, "yz", x_ctr - D / 2.0, D)
    return _mesh(parts, color, name)


def _mesh(parts, color, name, opacity=0.96):
    if parts is None:
        return None
    X, Y, Z, I, J, K = parts
    return go.Mesh3d(x=X, y=Y, z=Z, i=I, j=J, k=K, color=color, opacity=opacity,
                     name=name, showlegend=True, flatshading=True,
                     hovertemplate=f"{name}<extra></extra>")


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


def pier_total_height(pier: dict, H_tru: float = None) -> float:
    p = migrate_pier(pier or {})
    parts = p.get("parts", {})
    H_be = float(parts.get("be", {}).get("H", 1.5))
    H_cap = _part_height_m(parts.get("xa_mu", {}), "xa_mu")
    H_than = float(parts.get("than", {}).get("H", 5.0))
    if H_tru is not None:
        H_than = max(0.3, float(H_tru) - H_be - H_cap)
    return round(H_be + H_than + H_cap, 3)
