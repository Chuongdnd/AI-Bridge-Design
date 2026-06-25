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
        # earcut yêu cầu holes là LIST (gọi len(holes)); truyền None sẽ raise
        # TypeError → rơi xuống fan-fallback gây gấp nếp mặt cắt LÕM (xà mũ).
        tris = _earcut(ext, holes)
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


def _section_solids(section: dict) -> list:
    """Trả về list các KHỐI đặc [{outer, holes}] của mặt cắt.

    Mặt cắt nhiều khối rời (vd thân trụ 2 cột) lưu ở section['solids'].
    Tương thích ngược: mặt cắt cũ chỉ có outer/holes → 1 khối."""
    if not section:
        return []
    sl = section.get("solids")
    if sl:
        return [{"outer": s.get("outer", []), "holes": s.get("holes", [])}
                for s in sl if len(s.get("outer", [])) >= 3]
    o = section.get("outer", [])
    if len(o) < 3:
        return []
    return [{"outer": o, "holes": section.get("holes", [])}]


def _solids_bbox(solids: list):
    """Bbox (umin,umax,vmin,vmax) gộp mọi khối."""
    xs, ys = [], []
    for s in solids:
        for (u, v) in s["outer"]:
            xs.append(u); ys.append(v)
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), max(xs), min(ys), max(ys)


def _merge_parts(plist: list):
    """Gộp nhiều (X,Y,Z,I,J,K) thành 1 mesh (dời chỉ số đỉnh)."""
    plist = [p for p in plist if p]
    if not plist:
        return None
    X, Y, Z, I, J, K = [], [], [], [], [], []
    off = 0
    for (x, y, z, i, j, k) in plist:
        X += list(x); Y += list(y); Z += list(z)
        I += [v + off for v in i]; J += [v + off for v in j]; K += [v + off for v in k]
        off += len(x)
    return X, Y, Z, I, J, K



def _cap_layers(cap: dict) -> list:
    """Danh sách ĐOẠN xà mũ [{section, D, loft}] dọc cầu — hỗ trợ cả định dạng
    cũ ({section,D}=1 đoạn) lẫn mới ({layers:[...]}). loft=True → vuốt sang đoạn sau."""
    cap = cap or {}
    if cap.get("layers"):
        out = []
        for lay in cap["layers"]:
            if lay and (lay.get("section") or {}).get("outer"):
                out.append({"section": lay["section"],
                            "D": float(lay.get("D", 1.8) or 1.8),
                            "loft": bool(lay.get("loft"))})
        if out:
            return out
    if (cap.get("section") or {}).get("outer"):
        return [{"section": cap["section"],
                 "D": float(cap.get("D", 1.8) or 1.8), "loft": False}]
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
    solids = _section_solids(section)
    umin, umax, _, _ = _solids_bbox(solids)   # gộp mọi khối → giữ khoảng cách cột
    w = umax - umin
    if w < 1e-6:
        return section
    f = (target_w_m * 1000.0) / w           # target (m) → mm
    _sc = lambda pts: [[u * f, v] for (u, v) in pts]
    out = {"outer": _sc(section["outer"]),
           "holes": [_sc(h) for h in section.get("holes", [])]}
    if section.get("solids"):
        out["solids"] = [{"outer": _sc(s["outer"]),
                          "holes": [_sc(h) for h in s.get("holes", [])]}
                         for s in solids]
    return out


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

    be_layers   = stem_layers_of(be)        # [{section,H,loft}] hoặc []
    than_layers = stem_layers_of(than)
    H_be  = stem_total_height(be_layers) if be_layers else float(be.get("H", 1.5))
    H_cap = _part_height_m(cap, "xa_mu")
    H_than_nat = (stem_total_height(than_layers) if than_layers
                  else float(than.get("H", 5.0)))
    H_than = H_than_nat
    if H_tru is not None:                    # co chiều cao thân để khớp tổng H_tru
        H_than = max(0.3, float(H_tru) - H_be - H_cap)

    traces = []
    z = z_base
    # 1) BỆ — mặt bằng đùn đứng (nhiều tầng nếu có).
    if be_layers:
        traces += stem_traces(be_layers, z, x_ctr, color=_COL["be"], name=L["be"])
    else:
        traces.append(_plan_mesh(be.get("section"), z, H_be, x_ctr,
                                 _COL["be"], L["be"]))
    z += H_be
    # 2) THÂN — co chiều cao các tầng để tổng = H_than.
    if than_layers:
        _tl = _scale_layers_height(than_layers, H_than)
        traces += stem_traces(_tl, z, x_ctr, color=_COL["than"], name=L["than"])
    else:
        traces.append(_plan_mesh(than.get("section"), z, H_than, x_ctr,
                                 _COL["than"], L["than"]))
    z += H_than
    # 3) XÀ MŨ — các đoạn xếp theo DỌC CẦU, đoạn loft vuốt sang đoạn sau.
    traces += cap_traces(_cap_layers(cap), z, x_ctr, cap_width=cap_width,
                         color=_COL["xa_mu"], name=L["xa_mu"])
    return [t for t in traces if t is not None]


def _scale_layers_height(layers: list, target_total: float) -> list:
    """Co/giãn chiều cao các tầng để tổng = target_total (giữ tỉ lệ)."""
    cur = sum(float(l.get("H", 0) or 0) for l in (layers or [])) or 1.0
    f = float(target_total) / cur
    return [{**l, "H": float(l.get("H", 0) or 0) * f} for l in (layers or [])]


def build_pier_from_parts(cap: dict = None, stem: dict = None,
                          footing: dict = None, ten: str = "") -> dict:
    """Lắp 1 trụ HOÀN CHỈNH từ 3 bản ghi thư viện (xà mũ + thân + bệ).

    Trả về pier dict định dạng `parts` để build_pier_mesh_traces() vẽ. Mỗi bộ
    phận giữ nguyên hình dạng/tiết diện đã mô hình; khi gắn vào cầu, xà mũ tự
    co bề rộng theo cầu và thân tự co chiều cao theo tĩnh không (ở renderer)."""
    parts = {}
    if footing:
        parts["be"] = {"layers": stem_layers_of(footing),
                       "H": stem_total_height(footing)}
    if stem:
        parts["than"] = {"layers": stem_layers_of(stem),
                         "H": stem_total_height(stem)}
    if cap:
        parts["xa_mu"] = {"layers": _cap_layers(cap)}
    return {"ten": ten, "parts": parts, "loai": "tru"}



def _plan_mesh(section, z0, H, x_ctr, color, name):
    """Bệ/thân: section (u,v) mm → mặt bằng (x=v dọc, y=u ngang), đùn z.
    Hỗ trợ NHIỀU khối rời (vd thân trụ 2 cột) → gộp thành 1 mesh."""
    solids = _section_solids(section)
    if not solids:
        return None
    cu = 0.0  # u (ngang) đã căn tim tại 0 theo parser
    _, _, vmin, vmax = _solids_bbox(solids)
    cv = (vmin + vmax) / 2.0  # căn giữa theo dọc cầu

    def _conv(pts):
        return [((v - cv) * MM + x_ctr, (u - cu) * MM) for (u, v) in pts]

    parts = []
    for s in solids:
        outer = _conv(s["outer"])
        holes = [_conv(h) for h in s.get("holes", [])]
        parts.append(_extrude(outer, holes, "xy", z0, H))
    return _mesh(_merge_parts(parts), color, name)


def _cap_mesh(section, z0, x0, D, color, name):
    """Xà mũ: section (u,v) → (y=u ngang, z=v', cao), đùn dọc cầu x từ x0..x0+D.
    v' = v - vmin (lật dương lên), đặt đáy thấp nhất tại z0 (đỉnh thân)."""
    solids = _section_solids(section)
    if not solids:
        return None
    _, _, vmin, _ = _solids_bbox(solids)

    def _conv(pts):
        return [(u * MM, (v - vmin) * MM + z0) for (u, v) in pts]

    parts = []
    for s in solids:
        outer = _conv(s["outer"])
        holes = [_conv(h) for h in s.get("holes", [])]
        parts.append(_extrude(outer, holes, "yz", x0, D))
    return _mesh(_merge_parts(parts), color, name)


def _mesh(parts, color, name, opacity=0.96):
    if parts is None:
        return None
    X, Y, Z, I, J, K = parts
    return go.Mesh3d(x=X, y=Y, z=Z, i=I, j=J, k=K, color=color, opacity=opacity,
                     name=name, showlegend=True, flatshading=True,
                     hovertemplate=f"{name}<extra></extra>")


# ── LOFT xà mũ: vuốt nối giữa 2 mặt cắt dọc cầu (giống loft dầm) ─────────────
def _resample_ring(pts, n):
    arr = np.array([[p[0], p[1]] for p in pts], dtype=float)
    if len(arr) < 2:
        return arr
    loop = np.vstack([arr, arr[:1]])
    seg = np.sqrt((np.diff(loop, axis=0) ** 2).sum(1))
    cl = np.concatenate([[0.0], np.cumsum(seg)])
    total = cl[-1]
    if total < 1e-9:
        return arr[:n]
    t = np.linspace(0.0, total, n, endpoint=False)
    return np.column_stack([np.interp(t, cl, loop[:, 0]),
                            np.interp(t, cl, loop[:, 1])])


def _best_roll(ra, rb):
    """Căn rb khớp ra (thử cả chiều đảo + mọi offset) → loft không bắt chéo."""
    n = len(ra); best, bd = rb, float("inf")
    for cand in (rb, rb[::-1]):
        for off in range(n):
            r = np.roll(cand, off, axis=0)
            d = np.hypot(ra[:, 0] - r[:, 0], ra[:, 1] - r[:, 1]).sum()
            if d < bd:
                bd, best = d, r
    return best


def _cap_loft_mesh(secA, secB, z0, x0, D, color, name, N=44, M=12):
    """Vuốt nối mặt cắt A→B dọc cầu x0..x0+D. Mỗi mặt cắt (u,v)→(y=u, z=v'-vmin+z0)."""
    oA = (secA or {}).get("outer"); oB = (secB or {}).get("outer")
    if not oA or not oB or len(oA) < 3 or len(oB) < 3:
        return _cap_mesh(secA, z0, x0, D, color, name)
    _, _, vminA, _ = _bbox_ab(oA); _, _, vminB, _ = _bbox_ab(oB)
    A = [[u * MM, (v - vminA) * MM + z0] for (u, v) in oA]
    B = [[u * MM, (v - vminB) * MM + z0] for (u, v) in oB]
    ra = _resample_ring(A, N); rb = _best_roll(_resample_ring(A, N), _resample_ring(B, N))
    vx, vy, vz = [], [], []
    for i in range(M + 1):
        t = i / M
        x = x0 + D * t
        ring = ra * (1 - t) + rb * t
        for (y, z) in ring:
            vx.append(x); vy.append(y); vz.append(z)
    I, J, K = [], [], []
    for i in range(M):
        for j in range(N):
            a = i * N + j;            b = i * N + (j + 1) % N
            c = (i + 1) * N + (j + 1) % N; e = (i + 1) * N + j
            I += [a, a]; J += [b, c]; K += [c, e]
    return go.Mesh3d(x=vx, y=vy, z=vz, i=I, j=J, k=K, color=color, opacity=0.96,
                     name=name, showlegend=bool(name), flatshading=True,
                     hovertemplate=f"{name}<extra></extra>")


def cap_traces(layers, z0, x_ctr, cap_width=None, color=None, name="Xà mũ"):
    """Render xà mũ: list đoạn [{section,D,loft}] xếp dọc cầu, đoạn loft vuốt
    sang đoạn sau. Tổng bề dày căn giữa tại x_ctr; co bề rộng theo cap_width."""
    color = color or _COL["xa_mu"]
    layers = [l for l in (layers or []) if (l.get("section") or {}).get("outer")]
    if not layers:
        return []
    total_D = sum(float(l.get("D", 1.8) or 1.8) for l in layers) or 1.8
    x = x_ctr - total_D / 2.0
    multi = len(layers) > 1
    out = []
    for i, lay in enumerate(layers):
        _D = float(lay.get("D", 1.8) or 1.8)
        secA = _scale_section_u(lay["section"], cap_width) if cap_width else lay["section"]
        nm = f"{name} #{i + 1}" if multi else name
        if lay.get("loft") and i + 1 < len(layers):
            _nx = layers[i + 1]["section"]
            secB = _scale_section_u(_nx, cap_width) if cap_width else _nx
            out.append(_cap_loft_mesh(secA, secB, z0, x, _D, color, nm))
        else:
            out.append(_cap_mesh(secA, z0, x, _D, color, nm))
        x += _D
    return [t for t in out if t is not None]


# ── THÂN TRỤ nhiều tầng + loft theo PHƯƠNG ĐỨNG ─────────────────────────────
def stem_layers_of(part: dict) -> list:
    """Danh sách tầng thân trụ [{section,H,loft}] — tương thích {section,H} cũ."""
    part = part or {}
    if part.get("layers"):
        return [dict(l) for l in part["layers"]]
    if (part.get("section") or {}).get("outer"):
        return [{"section": part["section"], "H": float(part.get("H", 5.0) or 5.0)}]
    return []


def stem_total_height(part_or_layers) -> float:
    """Tổng chiều cao thân = Σ chiều cao các tầng."""
    lays = (part_or_layers if isinstance(part_or_layers, list)
            else stem_layers_of(part_or_layers))
    h = sum(float(l.get("H", 0) or 0) for l in lays)
    return h if h > 1e-6 else 5.0


def _centroid_y_m(solid_outer) -> float:
    """y (ngang, m) trọng tâm của 1 khối footprint — để ghép cặp khối khi loft."""
    pts = solid_outer
    n = len(pts); a2 = cy = 0.0
    for i in range(n):
        j = (i + 1) % n
        cr = pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
        a2 += cr; cy += (pts[i][0] + pts[j][0]) * cr      # u = ngang
    if abs(a2) < 1e-9:
        return sum(p[0] for p in pts) / max(n, 1) * MM
    return (cy / (3 * a2)) * MM


def _ring_xy_to_parts(ra, rb, z0, H, M, N):
    """Loft 2 vòng (x,y) theo PHƯƠNG ĐỨNG z0..z0+H → (X,Y,Z,I,J,K) kèn nắp."""
    vx, vy, vz = [], [], []
    for i in range(M + 1):
        t = i / M
        z = z0 + H * t
        ring = ra * (1 - t) + rb * t
        for (x, y) in ring:
            vx.append(x); vy.append(y); vz.append(z)
    I, J, K = [], [], []
    for i in range(M):                               # thành bên
        for j in range(N):
            a = i * N + j;             b = i * N + (j + 1) % N
            c = (i + 1) * N + (j + 1) % N; e = (i + 1) * N + j
            I += [a, a]; J += [b, c]; K += [c, e]
    _, t0 = _triangulate([list(p) for p in ra], [])  # nắp đáy (đảo chiều)
    for (p, q, r) in t0:
        I.append(p); J.append(r); K.append(q)
    base = M * N
    _, t1 = _triangulate([list(p) for p in rb], [])  # nắp đỉnh
    for (p, q, r) in t1:
        I.append(base + p); J.append(base + q); K.append(base + r)
    return vx, vy, vz, I, J, K


def _stem_loft_mesh(secA, secB, z0, H, x_ctr, color, name, N=56, M=14):
    """Vuốt nối footprint A→B theo PHƯƠNG ĐỨNG z0..z0+H. Footprint (u,v) →
    mặt bằng (x=(v-cv)+x_ctr, y=u). Ghép cặp từng khối (vd 2 cột)."""
    solA = _section_solids(secA); solB = _section_solids(secB)
    if not solA or not solB or len(solA) != len(solB):
        return _plan_mesh(secA, z0, H, x_ctr, color, name)
    _, _, vAmin, vAmax = _solids_bbox(solA); cvA = (vAmin + vAmax) / 2.0
    _, _, vBmin, vBmax = _solids_bbox(solB); cvB = (vBmin + vBmax) / 2.0

    def _ringA(s):
        return [[(v - cvA) * MM + x_ctr, u * MM] for (u, v) in s["outer"]]

    def _ringB(s):
        return [[(v - cvB) * MM + x_ctr, u * MM] for (u, v) in s["outer"]]

    ordA = sorted(range(len(solA)), key=lambda k: _centroid_y_m(solA[k]["outer"]))
    ordB = sorted(range(len(solB)), key=lambda k: _centroid_y_m(solB[k]["outer"]))
    parts = []
    for ia, ib in zip(ordA, ordB):
        ra = _resample_ring(_ringA(solA[ia]), N)
        rb = _best_roll(ra, _resample_ring(_ringB(solB[ib]), N))
        parts.append(_ring_xy_to_parts(ra, rb, z0, H, M, N))
    return _mesh(_merge_parts(parts), color, name)


def stem_traces(layers, z_base=0.0, x_ctr=0.0, color=None,
                name="Thân trụ", target_w_m=None):
    """Render thân trụ nhiều tầng xếp THEO PHƯƠNG ĐỨNG; tầng có loft vuốt mượt
    sang tầng trên. target_w_m: co bề rộng khớp cầu (giữ khoảng cách cột)."""
    color = color or _COL["than"]
    layers = [l for l in (layers or []) if (l.get("section") or {}).get("outer")]
    if not layers:
        return []
    z = z_base
    multi = len(layers) > 1
    out = []
    for i, lay in enumerate(layers):
        H = float(lay.get("H", 5.0) or 5.0)
        secA = _scale_section_u(lay["section"], target_w_m) if target_w_m else lay["section"]
        nm = f"{name} #{i + 1}" if multi else name
        if lay.get("loft") and i + 1 < len(layers):
            _nx = layers[i + 1]["section"]
            secB = _scale_section_u(_nx, target_w_m) if target_w_m else _nx
            out.append(_stem_loft_mesh(secA, secB, z, H, x_ctr, color, nm))
        else:
            out.append(_plan_mesh(secA, z, H, x_ctr, color, nm))
        z += H
    return [t for t in out if t is not None]


def build_stem_part_fig(layers: list, target_w_m: float = None,
                        color: str = None, name: str = "Thân trụ") -> go.Figure:
    """3D thân trụ độc lập (panel thư viện) — đặt đáy tại z=0."""
    return _part_scene_layout(
        go.Figure(stem_traces(layers, z_base=0.0, x_ctr=0.0,
                              color=color or _COL["than"],
                              name=name, target_w_m=target_w_m)))


def _part_scene_layout(fig):
    fig.update_layout(
        scene=dict(xaxis_title="Dọc cầu (m)", yaxis_title="Ngang cầu (m)",
                   zaxis_title="Cao độ (m)", aspectmode="data"),
        template="plotly_dark", height=660,
        margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="#0e1117",
        scene_camera=dict(eye=dict(x=1.6, y=-1.6, z=1.0)),
    )
    return fig


def build_pier_preview_fig(pier: dict, H_tru: float = None,
                           labels: dict = None) -> go.Figure:
    """Figure 3D xem trước 1 trụ/mố (panel thư viện)."""
    return _part_scene_layout(
        go.Figure(build_pier_mesh_traces(pier, H_tru=H_tru, labels=labels)))


def build_plan_part_fig(section: dict, H: float, color: str = "#5d8aa8",
                        name: str = "") -> go.Figure:
    """3D 1 bộ phận mặt-bằng (THÂN/BỆ): mặt cắt (u,v) đùn cao H — xem độc lập."""
    tr = _plan_mesh(section, 0.0, float(H or 1.0), 0.0, color, name)
    return _part_scene_layout(go.Figure([t for t in [tr] if t is not None]))


def build_cap_part_fig(cap_layers: list, cap_width: float = None) -> go.Figure:
    """3D xà mũ độc lập từ list đoạn [{section,D,loft}] — đặt đáy tại z=0."""
    return _part_scene_layout(
        go.Figure(cap_traces(cap_layers, z0=0.0, x_ctr=0.0,
                             cap_width=cap_width, color=_COL["xa_mu"],
                             name="Xà mũ")))


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
    be_layers, than_layers = stem_layers_of(be), stem_layers_of(than)
    H_be = stem_total_height(be_layers) if be_layers else float(be.get("H", 1.5))
    H_cap = _part_height_m(cap, "xa_mu")
    H_than = (stem_total_height(than_layers) if than_layers
              else float(than.get("H", 5.0)))
    if H_tru is not None:
        H_than = max(0.3, float(H_tru) - H_be - H_cap)

    def _sec0(part, layers):
        """Mặt cắt đại diện (tầng đáy) để lấy bề rộng dọc cầu."""
        if layers:
            return layers[0].get("section")
        return part.get("section")

    def _rect(name, color, w, z0, h):
        return {"name": name, "color": color,
                "xs": [x_ctr - w / 2, x_ctr + w / 2, x_ctr + w / 2, x_ctr - w / 2],
                "zs": [z0, z0, z0 + h, z0 + h]}

    z = z_base
    rects = [_rect(L["be"], _COL["be"],
                   _plan_doc_width_m(_sec0(be, be_layers)), z, H_be)]
    z += H_be
    rects.append(_rect(L["than"], _COL["than"],
                       _plan_doc_width_m(_sec0(than, than_layers)), z, H_than))
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

    _mp = []
    for s in _sec_solids:
        outer = _conv(s["outer"])
        holes = [_conv(h) for h in s.get("holes", [])]
        _mp.append(_extrude(outer, holes, "xz", -B / 2.0, B))
    traces.append(_mesh(_merge_parts(_mp), _COL["than"], L["than"]))
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
