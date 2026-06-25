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
    plane='yz' → (a,b)=(y,z) đùn theo x (xà mũ trụ, dọc cầu).
    plane='xz' → (a,b)=(x,z) đùn theo y (thân+mũ mố, ngang cầu).
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
        if plane == "xy":
            return (a, b, c)
        if plane == "yz":
            return (c, a, b)
        return (a, c, b)        # 'xz': đùn theo y

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


def _cap_layers(cap: dict) -> list:
    """Danh sách TẦNG xà mũ [{section, D}] — hỗ trợ cả định dạng cũ ({section,D}
    = 1 tầng) lẫn mới ({layers:[...]}). Tầng xếp chồng từ dưới lên."""
    cap = cap or {}
    if cap.get("layers"):
        out = []
        for lay in cap["layers"]:
            if lay and lay.get("section", {}).get("outer"):
                out.append({"section": lay["section"],
                            "D": float(lay.get("D", 1.8) or 1.8)})
        if out:
            return out
    if cap.get("section", {}).get("outer"):
        return [{"section": cap["section"], "D": float(cap.get("D", 1.8) or 1.8)}]
    return []


def _part_height_m(part: dict, role: str) -> float:
    """Chiều cao (m) một bộ phận theo trục z."""
    if role == "xa_mu":
        # Các đoạn xếp DỌC CẦU (cạnh nhau), cùng đáy → chiều cao mũ = đoạn CAO NHẤT.
        hs = []
        for lay in _cap_layers(part):
            _, _, vmin, vmax = _bbox_ab(lay["section"].get("outer", [[0, 0]]))
            hs.append((vmax - vmin) * MM)
        return max(hs) if hs else 1.2
    return float(part.get("H", 1.5))


def _scale_section_u(section: dict, target_w_m: float) -> dict:
    """Co/giãn mặt cắt theo phương NGANG (u) để bề rộng = target_w_m (giữ tâm
    u=0, giữ nguyên chiều cao). Dùng để xà mũ khớp BỀ RỘNG CẦU khi gắn vào cầu."""
    if not section or not section.get("outer") or not target_w_m:
        return section
    umin, umax, _, _ = _bbox_ab(section["outer"])
    w = umax - umin
    if w < 1e-6:
        return section
    f = (target_w_m * 1000.0) / w           # target (m) → mm
    _sc = lambda pts: [[u * f, v] for (u, v) in pts]
    return {"outer": _sc(section["outer"]),
            "holes": [_sc(h) for h in section.get("holes", [])]}


def build_pier_mesh_traces(pier: dict, H_tru: float = None,
                           x_ctr: float = 0.0, z_base: float = 0.0,
                           labels: dict = None, cap_width: float = None) -> list:
    """Trả về list go.Mesh3d của 1 trụ/mố (3 bộ phận).

    H_tru     : nếu cho (m), chiều cao THÂN tự co để (đáy bệ→đỉnh mũ) = H_tru.
    x_ctr     : lý trình tâm (m).   z_base: cao độ đáy bệ (m).
    labels    : ghi đè tên bộ phận {be,than,xa_mu} (mặc định: nhãn trụ).
    cap_width : nếu cho (m), co/giãn BỀ RỘNG xà mũ = cap_width (khớp bề rộng cầu),
                giữ nguyên hình dạng & chiều cao.
    """
    L = labels or _ROLE_LABEL
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
    traces.append(_plan_mesh(be.get("section"), z, H_be, x_ctr, _COL["be"], L["be"]))
    z += H_be
    # 2) THÂN
    traces.append(_plan_mesh(than.get("section"), z, H_than, x_ctr,
                             _COL["than"], L["than"]))
    z += H_than
    # 3) XÀ MŨ — 1..3 ĐOẠN xếp theo phương DỌC CẦU (x), cùng đáy tại đỉnh thân.
    #    Mỗi đoạn 1 mặt cắt ngang + chiều sâu dọc cầu D; tổng D căn giữa tại x_ctr.
    _caps = _cap_layers(cap)
    _multi = len(_caps) > 1
    _total_D = sum(l["D"] for l in _caps) or 1.8
    _x = x_ctr - _total_D / 2.0
    for _li, _lay in enumerate(_caps):
        _sec = _scale_section_u(_lay["section"], cap_width) if cap_width else _lay["section"]
        _nm = (f"{L['xa_mu']} #{_li + 1}" if _multi else L["xa_mu"])
        traces.append(_cap_mesh(_sec, z, _x, _lay["D"], _COL["xa_mu"], _nm))
        _x += _lay["D"]
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


def _cap_mesh(section, z0, x0, D, color, name):
    """Xà mũ: section (u,v) → (y=u ngang, z=v', cao), đùn dọc cầu x từ x0..x0+D.
    v' = v - vmin (lật dương lên), đặt đáy thấp nhất tại z0 (đỉnh thân)."""
    if not section or len(section.get("outer", [])) < 3:
        return None
    umin, umax, vmin, vmax = _bbox_ab(section["outer"])

    def _conv(pts):
        return [(u * MM, (v - vmin) * MM + z0) for (u, v) in pts]

    outer = _conv(section["outer"])
    holes = [_conv(h) for h in section.get("holes", [])]
    parts = _extrude(outer, holes, "yz", x0, D)
    return _mesh(parts, color, name)


def _mesh(parts, color, name, opacity=0.96):
    if parts is None:
        return None
    X, Y, Z, I, J, K = parts
    return go.Mesh3d(x=X, y=Y, z=Z, i=I, j=J, k=K, color=color, opacity=opacity,
                     name=name, showlegend=True, flatshading=True,
                     hovertemplate=f"{name}<extra></extra>")


def build_pier_preview_fig(pier: dict, H_tru: float = None,
                           labels: dict = None) -> go.Figure:
    """Figure 3D xem trước 1 trụ/mố (panel thư viện)."""
    fig = go.Figure(build_pier_mesh_traces(pier, H_tru=H_tru, labels=labels))
    fig.update_layout(
        scene=dict(xaxis_title="Dọc cầu (m)", yaxis_title="Ngang cầu (m)",
                   zaxis_title="Cao độ (m)", aspectmode="data"),
        template="plotly_dark", height=660,
        margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="#0e1117",
        scene_camera=dict(eye=dict(x=1.6, y=-1.6, z=1.0)),
    )
    return fig


def _plan_doc_width_m(section: dict) -> float:
    """Bề rộng theo phương DỌC cầu (m) của mặt cắt mặt bằng (= v-extent)."""
    _, _, vmin, vmax = _bbox_ab((section or {}).get("outer", [[0, 0]]))
    return max(0.05, (vmax - vmin) * MM)


def pier_elevation_rects(pier: dict, H_tru: float = None,
                         x_ctr: float = 0.0, z_base: float = 0.0,
                         labels: dict = None) -> list:
    """Bóng MẶT ĐỨNG DỌC cầu (x-z) của trụ/mố → list {name,color,xs,zs}.
    Dùng để vẽ trong trắc dọc 2D. Mỗi bộ phận là 1 chữ nhật:
      bệ/thân rộng = bề rộng dọc cầu mặt cắt; xà mũ rộng = chiều sâu D.
    """
    L = labels or _ROLE_LABEL
    p = migrate_pier(pier or {})
    parts = p.get("parts", {})
    be, than, cap = parts.get("be", {}), parts.get("than", {}), parts.get("xa_mu", {})
    H_be = float(be.get("H", 1.5))
    H_cap = _part_height_m(cap, "xa_mu")
    H_than = float(than.get("H", 5.0))
    if H_tru is not None:
        H_than = max(0.3, float(H_tru) - H_be - H_cap)

    def _rect(name, color, w, z0, h):
        return {"name": name, "color": color,
                "xs": [x_ctr - w / 2, x_ctr + w / 2, x_ctr + w / 2, x_ctr - w / 2],
                "zs": [z0, z0, z0 + h, z0 + h]}

    z = z_base
    rects = [_rect(L["be"], _COL["be"], _plan_doc_width_m(be.get("section")), z, H_be)]
    z += H_be
    rects.append(_rect(L["than"], _COL["than"],
                       _plan_doc_width_m(than.get("section")), z, H_than))
    z += H_than
    # Xà mũ: các đoạn xếp DỌC CẦU (cạnh nhau), cùng đáy z; mỗi đoạn cao riêng.
    _caps = _cap_layers(cap)
    _total_D = sum(l["D"] for l in _caps) or 1.8
    _x = x_ctr - _total_D / 2.0
    for _lay in _caps:
        _, _, _vmin, _vmax = _bbox_ab(_lay["section"].get("outer", [[0, 0]]))
        _h_lay = (_vmax - _vmin) * MM
        rects.append({"name": L["xa_mu"], "color": _COL["xa_mu"],
                      "xs": [_x, _x + _lay["D"], _x + _lay["D"], _x],
                      "zs": [z, z, z + _h_lay, z + _h_lay]})
        _x += _lay["D"]
    return rects


def pier_total_height(pier: dict, H_tru: float = None) -> float:
    p = migrate_pier(pier or {})
    parts = p.get("parts", {})
    H_be = float(parts.get("be", {}).get("H", 1.5))
    H_cap = _part_height_m(parts.get("xa_mu", {}), "xa_mu")
    H_than = float(parts.get("than", {}).get("H", 5.0))
    if H_tru is not None:
        H_than = max(0.3, float(H_tru) - H_be - H_cap)
    return round(H_be + H_than + H_cap, 3)


# ══════════════════════════════════════════════════════════════════════════
# MỐ CHỮ U BTCT (abutment) — KẾT CẤU KHÁC TRỤ.
#   • Bệ mố (be)        : mặt cắt MẶT BẰNG (ngang × dọc) → đùn ĐỨNG (cao H).
#   • Thân + mũ mố(than): mặt cắt DỌC cầu (hình L: tường thân + vai kê gối)
#                         → đùn NGANG cầu theo bề rộng B.
# Mố đặt ở đầu cầu: mặt trước (đỡ gối) quay vào nhịp, thân vươn ra phía đất
# đắp (out_dir). Mặt cắt dọc lưu [u, w] mm: u = dọc cầu (0 ở mặt trước, +u ra
# sau lưng), w = cao (0 ở mặt trên/đáy dầm, âm xuống).
# ══════════════════════════════════════════════════════════════════════════
_MO_LABEL = {"be": "Bệ mố", "than": "Thân + mũ mố"}


def _abut_long_mm(Wbody=1500.0, Lseat=900.0, Hbody=5000.0, Hseat=900.0) -> dict:
    """Mặt cắt dọc mố chữ L (mm): thân tường + vai kê gối nhô về phía nhịp."""
    return {"outer": [[-Lseat, 0.0], [Wbody, 0.0], [Wbody, -Hbody],
                      [0.0, -Hbody], [0.0, -Hseat], [-Lseat, -Hseat]],
            "holes": []}


def default_abutment(ten: str = "Mố mẫu") -> dict:
    return {
        "id": "", "ten": ten, "loai": "mo", "H_ref": 6.5,
        "parts": {
            "be":   {"section": _rect_mm(6000, 4000), "H": 1.5},
            "than": {"section": _abut_long_mm(), "B": 8.0, "flex": True},
        },
    }


def migrate_abutment(mo: dict) -> dict:
    """Đảm bảo bản ghi mố đúng schema (be plan + than longitudinal có B)."""
    if not isinstance(mo, dict):
        return default_abutment()
    out = dict(mo)
    parts = dict(out.get("parts") or {})
    base = default_abutment()["parts"]
    be = dict(parts.get("be") or {})
    if len(be.get("section", {}).get("outer", [])) < 3:
        be["section"] = base["be"]["section"]
    be.setdefault("H", 1.5)
    than = dict(parts.get("than") or {})
    if len(than.get("section", {}).get("outer", [])) < 3:
        than["section"] = base["than"]["section"]
    than.setdefault("B", 8.0)
    than.setdefault("flex", True)
    out["parts"] = {"be": be, "than": than}
    out["loai"] = "mo"
    return out


def _abut_body_height_m(than: dict, H_tru: float = None, H_be: float = 1.5) -> float:
    sec = than.get("section") or _abut_long_mm()
    _, _, wmin, wmax = _bbox_ab(sec["outer"])
    raw = (wmax - wmin) * MM
    if H_tru is not None:
        return max(0.5, float(H_tru) - H_be)
    return raw


def abutment_total_height(mo: dict, H_tru: float = None) -> float:
    p = migrate_abutment(mo)
    H_be = float(p["parts"]["be"].get("H", 1.5))
    if H_tru is not None:
        return round(float(H_tru), 3)
    return round(H_be + _abut_body_height_m(p["parts"]["than"], None, H_be), 3)


def build_abutment_mesh_traces(mo: dict, H_tru: float = None, x_face: float = 0.0,
                               out_dir: float = 1.0, z_base: float = 0.0,
                               labels: dict = None) -> list:
    """list go.Mesh3d của 1 mố. x_face: lý trình mặt trước (đỡ gối);
    out_dir: +1/−1 hướng RA sau lưng (xa nhịp); z_base: cao độ đáy bệ."""
    L = labels or _MO_LABEL
    p = migrate_abutment(mo)
    be, than = p["parts"]["be"], p["parts"]["than"]
    H_be = float(be.get("H", 1.5))
    B = float(than.get("B", 8.0))
    sec = than.get("section") or _abut_long_mm()
    umin, umax, wmin, wmax = _bbox_ab(sec["outer"])
    raw_h = (wmax - wmin) * MM
    body_h = _abut_body_height_m(than, H_tru, H_be)
    vsc = body_h / raw_h if raw_h > 1e-6 else 1.0
    z_body0 = z_base + H_be

    traces = []
    # BỆ: mặt bằng đùn đứng, căn tâm dưới thân
    u_ctr = (umin + umax) / 2.0
    x_be = x_face + out_dir * u_ctr * MM
    traces.append(_plan_mesh(be.get("section"), z_base, H_be, x_be, _COL["be"], L["be"]))

    # THÂN+MŨ: mặt cắt dọc (u,w) → (x = x_face+out_dir*u, z = z_body0+(w-wmin)*vsc),
    # đùn theo ngang cầu y trong [-B/2, B/2].
    def _conv(pts):
        return [(x_face + out_dir * u * MM, z_body0 + (w - wmin) * MM * vsc)
                for (u, w) in pts]

    outer = _conv(sec["outer"])
    holes = [_conv(h) for h in sec.get("holes", [])]
    mesh = _extrude(outer, holes, "xz", -B / 2.0, B)
    traces.append(_mesh(mesh, _COL["than"], L["than"]))
    return [t for t in traces if t is not None]


def abutment_elevation_polys(mo: dict, H_tru: float = None, x_face: float = 0.0,
                             out_dir: float = 1.0, z_base: float = 0.0,
                             labels: dict = None) -> list:
    """Bóng MẶT ĐỨNG DỌC cầu (x-z) của mố → list {name,color,xs,zs}.
    Thân+mũ là ĐÚNG mặt cắt dọc (vì mặt phẳng trắc dọc trùng mặt cắt dọc mố)."""
    L = labels or _MO_LABEL
    p = migrate_abutment(mo)
    be, than = p["parts"]["be"], p["parts"]["than"]
    H_be = float(be.get("H", 1.5))
    sec = than.get("section") or _abut_long_mm()
    umin, umax, wmin, wmax = _bbox_ab(sec["outer"])
    raw_h = (wmax - wmin) * MM
    body_h = _abut_body_height_m(than, H_tru, H_be)
    vsc = body_h / raw_h if raw_h > 1e-6 else 1.0
    z_body0 = z_base + H_be

    polys = []
    # Bệ: chữ nhật rộng theo dọc cầu (v-extent mặt bằng), căn tâm dưới thân
    u_ctr = (umin + umax) / 2.0
    x_be = x_face + out_dir * u_ctr * MM
    w_be = _plan_doc_width_m(be.get("section"))
    polys.append({"name": L["be"], "color": _COL["be"],
                  "xs": [x_be - w_be/2, x_be + w_be/2, x_be + w_be/2, x_be - w_be/2],
                  "zs": [z_base, z_base, z_base + H_be, z_base + H_be]})
    # Thân+mũ: đúng đa giác mặt cắt dọc
    polys.append({"name": L["than"], "color": _COL["than"],
                  "xs": [x_face + out_dir * u * MM for (u, w) in sec["outer"]],
                  "zs": [z_body0 + (w - wmin) * MM * vsc for (u, w) in sec["outer"]]})
    return polys


def build_abutment_preview_fig(mo: dict, H_tru: float = None,
                               labels: dict = None) -> go.Figure:
    """Figure 3D xem trước 1 mố (panel thư viện)."""
    fig = go.Figure(build_abutment_mesh_traces(mo, H_tru=H_tru, labels=labels))
    fig.update_layout(
        scene=dict(xaxis_title="Dọc cầu (m)", yaxis_title="Ngang cầu (m)",
                   zaxis_title="Cao độ (m)", aspectmode="data"),
        template="plotly_dark", height=660,
        margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="#0e1117",
        scene_camera=dict(eye=dict(x=1.7, y=-1.5, z=0.9)),
    )
    return fig
