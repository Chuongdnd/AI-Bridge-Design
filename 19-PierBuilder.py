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


def _poly_centroid_u(outer):
    """Hoành độ u (mm) trọng tâm 1 đa giác (đơn vị mặt cắt)."""
    pts = outer[:-1] if outer and outer[0] == outer[-1] else outer
    n = len(pts)
    if n < 3:
        return sum(p[0] for p in pts) / max(1, n) if pts else 0.0
    a2 = cu = 0.0
    for i in range(n):
        j = (i + 1) % n
        cr = pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
        a2 += cr; cu += (pts[i][0] + pts[j][0]) * cr
    if abs(a2) < 1e-9:
        return sum(p[0] for p in pts) / n
    return cu / (3.0 * a2)


def pier_stem_info(pier: dict):
    """Nhận diện THÂN trụ → ('2cot', khoảng_cách_2_cột_m) hoặc ('dac', bề_rộng_m)
    hoặc (None, 0). Dùng để hiện ô khai báo phù hợp + giá trị hiện tại."""
    p = migrate_pier(pier or {})
    lays = stem_layers_of(p.get("parts", {}).get("than", {}))
    if not lays:
        return None, 0.0
    solids = _section_solids(lays[0]["section"])
    if len(solids) >= 2:
        cs = sorted(solids, key=lambda s: _poly_centroid_u(s["outer"]))
        return "2cot", abs(_poly_centroid_u(cs[-1]["outer"])
                           - _poly_centroid_u(cs[0]["outer"])) * MM
    if len(solids) == 1:
        us = [u for (u, _v) in solids[0]["outer"]]
        return "dac", (max(us) - min(us)) * MM if us else 0.0
    return None, 0.0


def apply_stem_params(pier: dict, spacing_m: float = None,
                      width_m: float = None) -> dict:
    """Chỉnh THÂN trụ theo khai báo: spacing_m = khoảng cách 2 cột (trụ 2 thân);
    width_m = bề rộng thân (trụ đặc 1 thân). Trả pier MỚI (copy), không đổi gốc."""
    import copy
    p = copy.deepcopy(migrate_pier(pier or {}))
    than = p.get("parts", {}).get("than", {})
    lays = stem_layers_of(than)
    if not lays:
        return p
    new_lays = []
    for lay in lays:
        sec = dict(lay.get("section") or {})
        solids = _section_solids(sec)
        if len(solids) == 2 and spacing_m and spacing_m > 0:
            cs = sorted(solids, key=lambda s: _poly_centroid_u(s["outer"]))
            tc = spacing_m / 2.0 / MM            # tâm cột mục tiêu (mm)
            ns = []
            for k, s in enumerate(cs):
                c = _poly_centroid_u(s["outer"])
                shift = (-tc - c) if k == 0 else (tc - c)
                ns.append({"outer": [[u + shift, v] for (u, v) in s["outer"]],
                           "holes": [[[u + shift, v] for (u, v) in h]
                                     for h in s.get("holes", [])]})
            sec["solids"] = ns
            sec["outer"] = ns[0]["outer"]
            sec["holes"] = ns[0].get("holes", [])
        elif len(solids) == 1 and width_m and width_m > 0:
            s = solids[0]
            us = [u for (u, _v) in s["outer"]]
            cu = (min(us) + max(us)) / 2.0
            cur = (max(us) - min(us)) or 1.0
            f = (width_m / MM) / cur
            no = [[cu + (u - cu) * f, v] for (u, v) in s["outer"]]
            nh = [[[cu + (u - cu) * f, v] for (u, v) in h]
                  for h in s.get("holes", [])]
            sec["solids"] = [{"outer": no, "holes": nh}]
            sec["outer"] = no
            sec["holes"] = nh
        new_lays.append({**lay, "section": sec})
    than = dict(than); than["layers"] = new_lays
    p["parts"] = dict(p["parts"]); p["parts"]["than"] = than
    return p



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
        margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
        scene_camera=dict(eye=dict(x=1.6, y=-1.6, z=1.0)),
    )
    return fig


def build_pier_preview_fig(pier: dict, H_tru: float = None,
                           labels: dict = None, cap_width: float = None) -> go.Figure:
    """Figure 3D xem trước 1 trụ/mố (panel thư viện).
    cap_width: co bề rộng xà mũ theo bề rộng cầu (để KHỚP trụ trong 3D toàn cầu)."""
    return _part_scene_layout(
        go.Figure(build_pier_mesh_traces(pier, H_tru=H_tru, labels=labels,
                                         cap_width=cap_width)))


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
    # Chiều cao từng ĐOẠN xà mũ (dọc cầu) + chiều cao VAI KÊ = đoạn đầu/cuối
    # (chỗ dầm GỐI lên). Đoạn giữa (ụ chắn giữa 2 nhịp) thường cao hơn → nhô lên.
    _caps = _cap_layers(cap)
    _cap_h = []
    for _lay in _caps:
        _, _, _vmin, _vmax = _bbox_ab(_lay["section"].get("outer", [[0, 0]]))
        _cap_h.append((_vmax - _vmin) * MM)
    seat_h = min(_cap_h[0], _cap_h[-1]) if _cap_h else H_cap   # cao độ vai kê
    H_than = (stem_total_height(than_layers) if than_layers
              else float(than.get("H", 5.0)))
    if H_tru is not None:
        # Thân kéo lên tới VAI KÊ = đáy dầm; ụ giữa cao hơn sẽ nhô trên đáy dầm.
        H_than = max(0.3, float(H_tru) - H_be - seat_h)

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
    # Xà mũ: các đoạn xếp DỌC CẦU (cạnh nhau), CÙNG ĐÁY z. Vai kê (đầu/cuối) cao
    # bằng seat_h → đỉnh vai = đáy dầm; ụ giữa cao hơn → nhô lên giữa 2 đầu dầm.
    _total_D = sum(l["D"] for l in _caps) or 1.8
    _x = x_ctr - _total_D / 2.0
    for _lay, _h_lay in zip(_caps, _cap_h):
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


def pier_plan_polys(pier: dict, target_width: float = None) -> list:
    """Hình chiếu MẶT BẰNG (ngang u × dọc v) của trụ lắp ghép → list
    {name,color,xs(ngang m),ys(dọc m)}. Thân/bệ giữ footprint thật (kể cả
    nhiều khối); xà mũ = chữ nhật ngang(co theo cầu) × sâu tổng các đoạn."""
    p = migrate_pier(pier or {})
    parts = p.get("parts", {})
    be, than, cap = parts.get("be", {}), parts.get("than", {}), parts.get("xa_mu", {})
    out = []

    def _footprint(part, name, color):
        lays = stem_layers_of(part)
        sec = lays[0]["section"] if lays else part.get("section")
        for s in _section_solids(sec):
            _, _, vmin, vmax = _solids_bbox([s])
            cv = (vmin + vmax) / 2.0
            out.append({"name": name, "color": color,
                        "xs": [u * MM for (u, v) in s["outer"]],
                        "ys": [(v - cv) * MM for (u, v) in s["outer"]]})

    _footprint(be, "Bệ trụ", _COL["be"])
    _footprint(than, "Thân trụ", _COL["than"])
    cap_secs = _cap_layers(cap)
    if cap_secs:
        total_D = sum(float(l.get("D", 1.8) or 1.8) for l in cap_secs) or 1.8
        sec = max(cap_secs, key=lambda l: _sec_v_extent(l["section"]))["section"]
        if target_width:
            sec = _scale_section_u(sec, target_width)
        umin, umax, _, _ = _solids_bbox(_section_solids(sec))
        out.append({"name": "Xà mũ", "color": _COL["xa_mu"],
                    "xs": [umin * MM, umax * MM, umax * MM, umin * MM],
                    "ys": [-total_D / 2, -total_D / 2, total_D / 2, total_D / 2]})
    return out


def _sec_v_extent(section: dict) -> float:
    """Chiều cao (v-extent, m) của 1 mặt cắt."""
    sl = _section_solids(section)
    if not sl:
        return 0.0
    _, _, vmin, vmax = _solids_bbox(sl)
    return (vmax - vmin) * MM


def cap_mid_gap_m(pier: dict) -> float:
    """Bề rộng (dọc cầu, m) KHỐI GIỮA cao của xà mũ = KHE giữa 2 đầu dầm SPT.

    Xà mũ Super-T có ≥3 đoạn (vai kê thấp ở 2 đầu + ụ giữa cao): 2 đầu dầm kê lên
    2 đoạn vai kê THẤP, ụ giữa CAO nằm giữa 2 đầu dầm → khoảng cách gối = chiều
    dài dầm + bề rộng ụ giữa. Trả 0 nếu xà mũ 1 đoạn (dầm liền, không có ụ giữa)."""
    p = migrate_pier(pier or {})
    caps = _cap_layers(p.get("parts", {}).get("xa_mu", {}))
    if len(caps) < 3:
        return 0.0
    hs = [_sec_v_extent(l["section"]) for l in caps]
    hi = max(range(len(caps)), key=lambda i: hs[i])
    if hs[hi] <= min(hs[0], hs[-1]) + 1e-6:   # ụ giữa không cao hơn vai kê → bỏ
        return 0.0
    return float(caps[hi].get("D", 0.0) or 0.0)


def cap_seat_notch_depth_m(pier: dict) -> float:
    """Độ sâu KHẤC (vai kê) dưới ĐỈNH TƯỜNG TAI của xà mũ (m) — dầm SPT kê vào
    khấc, KHÔNG kê đỉnh tường tai. Lấy từ mặt cắt đoạn VAI KÊ (đoạn thấp nhất):
    đỉnh tường tai = v cao nhất; khấc = phần lõm GIỮA (|u| nhỏ) thấp hơn đỉnh.
    Trả 0 nếu mặt cắt không có khấc (đỉnh phẳng)."""
    p = migrate_pier(pier or {})
    caps = _cap_layers(p.get("parts", {}).get("xa_mu", {}))
    if not caps:
        return 0.0
    hs = [_sec_v_extent(l["section"]) for l in caps]
    seat = caps[min(range(len(caps)), key=lambda i: hs[i])]["section"]  # đoạn thấp = vai kê
    pts = [q for s in _section_solids(seat) for q in s.get("outer", [])]
    if not pts:
        return 0.0
    umax = max((abs(u) for (u, v) in pts), default=0.0) or 1.0
    v_top = max(v for (u, v) in pts)
    central = [v for (u, v) in pts if abs(u) < 0.4 * umax and v < v_top - 1.0]
    if not central:
        return 0.0                       # đỉnh phẳng giữa → không có khấc
    return max(0.0, (v_top - max(central)) * MM)


def pier_mcn_polys(pier: dict, z_top: float = 0.0, H_than: float = 5.0,
                   target_width: float = None, seat_view: bool = False) -> list:
    """Hình chiếu MẶT CẮT NGANG cầu (ngang u × cao z) của trụ lắp ghép.

    Trả list {name,color,xs(ngang m),ys(cao z m)}. z_top = cao độ ĐỈNH xà mũ
    (= đáy dầm); H_than = chiều cao thân (m). Xà mũ co bề rộng = target_width.
    Thân/bệ giữ tiết diện thật → mỗi khối là 1 chữ nhật theo bề rộng ngang.

    seat_view=True → MCN cắt tại ĐẦU DẦM: vẽ mặt cắt đoạn VAI KÊ (thấp) để thấy
    KHẤC kê dầm + tường tai (phần kê dầm). seat_view=False → vẽ đoạn ụ giữa (cao)."""
    p = migrate_pier(pier or {})
    parts = p.get("parts", {})
    be, than, cap = parts.get("be", {}), parts.get("than", {}), parts.get("xa_mu", {})
    be_layers, than_layers = stem_layers_of(be), stem_layers_of(than)
    H_be  = stem_total_height(be_layers) if be_layers else float(be.get("H", 1.5))
    H_cap = _part_height_m(cap, "xa_mu")
    out = []

    # 1) XÀ MŨ — mặt cắt (ngang u, cao v) đoạn CAO NHẤT; co bề rộng theo cầu.
    #    Dầm kê tại ĐỈNH các khối THẤP (đầu dầm khấc Super-T kê lên 2 bên), khối
    #    GIỮA cao nhất NHÔ LÊN đỡ bản mặt cầu. Giữ NGUYÊN chênh cao giữa các khối
    #    (neo theo mức kê dầm = z_top = đáy dầm), KHÔNG ép mọi khối cùng đỉnh.
    cap_secs = _cap_layers(cap)
    z_cap_b = z_top - H_cap
    _cap_outlines = []   # biên xà mũ (x,y) → thân trụ kéo lên sát đáy xà mũ
    if cap_secs:
        # Xà mũ Super-T = nhiều ĐOẠN (layer) dọc cầu: vai kê đầu/cuối THẤP (đầu dầm
        # khấc kê lên), ụ giữa CAO (đỡ bản). Neo sao cho VAI KÊ ở z_top (=đáy dầm)
        # → ụ giữa NHÔ LÊN (h_high − seat_h) trên đáy dầm. Đồng bộ với trắc dọc.
        cap_hs = [_sec_v_extent(l["section"]) for l in cap_secs]
        seat_h = min(cap_hs[0], cap_hs[-1]) if cap_hs else H_cap   # cao vai kê
        hi     = max(range(len(cap_secs)), key=lambda i: cap_hs[i])
        h_high = cap_hs[hi]
        if seat_view and len(cap_secs) >= 2:
            # MCN tại ĐẦU DẦM: mặt phẳng cắt qua VAI KÊ → vẽ mặt cắt đoạn THẤP
            # (có khấc kê dầm + tường tai). ụ giữa nằm giữa cầu (sau mặt cắt) →
            # không vẽ ở đây. Neo ĐỈNH tường tai vai kê = z_top.
            _si  = 0 if cap_hs[0] <= cap_hs[-1] else len(cap_secs) - 1
            sec  = cap_secs[_si]["section"]
            _z_cap_top = z_top                     # đỉnh tường tai vai kê = z_top
        else:
            sec  = cap_secs[hi]["section"]         # mặt cắt đoạn cao nhất (ụ giữa)
            _z_cap_top = z_top + (h_high - seat_h)  # đỉnh ụ giữa (trên đáy dầm)
        if target_width:
            sec = _scale_section_u(sec, target_width)
        _solids = _section_solids(sec)
        _, _, _, _v_sec_top = _solids_bbox(_solids) if _solids else (0, 0, 0, 0.0)
        _cap_ys = []
        for s in _solids:
            xs = [u * MM for (u, v) in s["outer"]]
            ys = [_z_cap_top + (v - _v_sec_top) * MM for (u, v) in s["outer"]]
            _cap_ys += ys
            _cap_outlines.append(list(zip(xs, ys)))
            out.append({"name": "Xà mũ", "color": _COL["xa_mu"], "xs": xs, "ys": ys})
        if _cap_ys:
            z_cap_b = min(_cap_ys)

    # Cao độ ĐÁY xà mũ tại hoành độ x (nội suy biên dưới) → thân trụ kéo lên sát.
    def _cap_bot_at(x):
        yy = []
        for poly in _cap_outlines:
            n = len(poly)
            for i in range(n):
                x0, y0 = poly[i]; x1, y1 = poly[(i + 1) % n]
                if min(x0, x1) - 1e-9 <= x <= max(x0, x1) + 1e-9 and abs(x1 - x0) > 1e-9:
                    yy.append(y0 + (x - x0) / (x1 - x0) * (y1 - y0))
        return min(yy) if yy else z_cap_b

    # 2) THÂN — đáy phẳng (= đỉnh bệ); ĐỈNH thân trụ KÉO LÊN bám đáy xà mũ (theo độ
    #    dốc) → hết khoảng hở giữa thân trụ và xà mũ khi xà mũ dốc/đáy không phẳng.
    z_be_t = z_cap_b - H_than
    than_sec = than_layers[0]["section"] if than_layers else than.get("section")
    for s in _section_solids(than_sec):
        umin, umax, _, _ = _solids_bbox([s])
        xL, xR = umin * MM, umax * MM
        # Đỉnh thân trụ BÁM ĐÁY xà mũ tại MỌI vị trí trong [xL, xR] (gồm cả các
        # điểm gãy của biên đáy xà mũ) → thân trụ không ngàm vào xà mũ, chỉ kéo
        # dài tới sát đáy xà mũ ở mọi điểm; hết khoảng hở khi đáy gãy/dốc.
        _midx = sorted(x for poly in _cap_outlines for (x, _y) in poly if xL < x < xR)
        _topx = [xL] + _midx + [xR]
        _top = [(x, _cap_bot_at(x)) for x in _topx]
        out.append({"name": "Thân trụ", "color": _COL["than"],
                    "xs": [xL, xR] + [x for (x, _y) in reversed(_top)],
                    "ys": [z_be_t, z_be_t] + [y for (_x, y) in reversed(_top)]})

    # 3) BỆ — footprint → chữ nhật ngang.
    be_sec = be_layers[0]["section"] if be_layers else be.get("section")
    for s in _section_solids(be_sec):
        umin, umax, _, _ = _solids_bbox([s])
        out.append({"name": "Bệ trụ", "color": _COL["be"],
                    "xs": [umin * MM, umax * MM, umax * MM, umin * MM],
                    "ys": [z_be_t - H_be, z_be_t - H_be, z_be_t, z_be_t]})
    return out


# ══════════════════════════════════════════════════════════════════════════
# MỐ BTCT (abutment) — 2 BỘ PHẬN, KẾT CẤU KHÁC TRỤ.
#   • Bệ mố    (be)  : mặt cắt MẶT BẰNG (ngang × dọc) → đùn ĐỨNG (cao H).
#   • Tường thân(than): mặt cắt DỌC cầu (hình bên: tường thân + vai kê gối)
#                       → đùn/LOFT theo NGANG cầu.
# Người dùng VẼ NHIỀU MẶT CẮT DỌC cầu, hệ thống LINK chúng theo phương NGANG
# cầu và LOFT (vuốt) giữa các mặt cắt kề nhau — cho phép tường thân thay đổi
# hình dạng dọc theo bề rộng (vd thân giữa cao, vuốt mỏng ra mép, tường cánh).
# Mỗi đoạn: {section, B, loft}; các đoạn xếp nối tiếp theo ngang cầu, đoạn có
# loft=True vuốt mượt sang mặt cắt đoạn kế (giống loft xà mũ nhưng theo trục y).
# Tương thích ngược: than định dạng cũ {section, B} = 1 đoạn không loft.
#
# Mố đặt ở đầu cầu: mặt trước (đỡ gối) quay vào nhịp, thân vươn ra phía đất
# đắp (out_dir). Mặt cắt dọc lưu [u, w] mm: u = dọc cầu (0 ở mặt trước, +u ra
# sau lưng), w = cao (0 ở mặt trên/đáy dầm, âm xuống).
# ══════════════════════════════════════════════════════════════════════════
_MO_LABEL = {"be": "Bệ mố", "than": "Tường thân"}


def _abut_long_mm(Wbody=1500.0, Lseat=900.0, Hbody=5000.0, Hseat=900.0) -> dict:
    """Mặt cắt dọc mố chữ L (mm): thân tường + vai kê gối nhô về phía nhịp."""
    return {"outer": [[-Lseat, 0.0], [Wbody, 0.0], [Wbody, -Hbody],
                      [0.0, -Hbody], [0.0, -Hseat], [-Lseat, -Hseat]],
            "holes": []}


def default_abutment(ten: str = "Mố mẫu") -> dict:
    # Mố = CHỈ tường thân (mặt cắt dọc đã GỒM cả bệ). Không tách bộ phận bệ.
    return {
        "id": "", "ten": ten, "loai": "mo", "H_ref": 6.5,
        "parts": {
            "than": {"section": _abut_long_mm(), "B": 8.0, "flex": True},
        },
    }


# ── Đoạn tường thân (xếp theo NGANG cầu) ─────────────────────────────────────
def _layer_seat_w(pts):
    """w của ledge NGANG cao nhất nằm dưới mép trên 1 mặt cắt = VAI KÊ của đoạn."""
    if not pts:
        return None
    w_top = max(w for (_u, w) in pts)
    n = len(pts); best = None
    for i in range(n):
        u0, w0 = pts[i]; u1, w1 = pts[(i + 1) % n]
        if (abs(w1 - w0) < 5.0 and abs(u1 - u0) > 300.0
                and w0 < w_top - 200.0 and (best is None or w0 > best)):
            best = w0
    return best


def _shift_section_w(sec, dw):
    """Dịch toàn bộ mặt cắt theo phương cao (w += dw); giữ nguyên nếu dw≈0."""
    if abs(dw) < 1e-6:
        return sec
    _sh = lambda poly: [[u, w + dw] for (u, w) in poly]
    ns = {"outer": _sh(sec.get("outer", [])),
          "holes": [_sh(h) for h in sec.get("holes", [])]}
    if sec.get("solids"):
        ns["solids"] = [{"outer": _sh(s.get("outer", [])),
                         "holes": [_sh(h) for h in s.get("holes", [])]}
                        for s in sec["solids"]]
    return ns


def _abut_align_layers(layers):
    """CĂN các đoạn (tường cánh/thân) theo VAI KÊ: dịch w mỗi đoạn để ledge vai kê
    của nó trùng vai kê đoạn THÂN CHÍNH (B lớn nhất). Thư viện thường vẽ tường
    cánh thấp hơn thân (~0.56m) → sau khi căn thì VAI KÊ và ĐÁY BỆ phẳng đều cho
    cả mố. Trả layers mới (không sửa bản gốc)."""
    if not layers or len(layers) < 2:
        return layers
    body = max(layers, key=lambda l: float(l.get("B", 0) or 0))
    ref = _layer_seat_w(body["section"]["outer"])
    if ref is None:
        return layers
    out = []
    for lay in layers:
        sw = _layer_seat_w(lay["section"]["outer"])
        dw = (ref - sw) if sw is not None else 0.0
        out.append({**lay, "section": _shift_section_w(lay["section"], dw)})
    return out


def abut_body_layers(than: dict) -> list:
    """Danh sách ĐOẠN tường thân [{section, B, loft}] xếp theo NGANG cầu —
    hỗ trợ cả định dạng cũ {section, B}=1 đoạn lẫn mới {layers:[...]}.
    loft=True → vuốt sang mặt cắt đoạn kế. Các đoạn được CĂN theo vai kê."""
    than = than or {}
    if than.get("layers"):
        out = []
        for lay in than["layers"]:
            if lay and (lay.get("section") or {}).get("outer"):
                out.append({"section": lay["section"],
                            "B": float(lay.get("B", 8.0) or 8.0),
                            "loft": bool(lay.get("loft"))})
        if out:
            return _abut_align_layers(out)
    if (than.get("section") or {}).get("outer"):
        return [{"section": than["section"],
                 "B": float(than.get("B", 8.0) or 8.0), "loft": False}]
    return []


def abut_body_total_B(than_or_layers) -> float:
    """Tổng bề rộng ngang cầu của tường thân = Σ bề rộng các đoạn."""
    lays = (than_or_layers if isinstance(than_or_layers, list)
            else abut_body_layers(than_or_layers))
    b = sum(float(l.get("B", 0) or 0) for l in lays)
    return b if b > 1e-6 else 8.0


def _abut_body_raw_h(layers: list) -> float:
    """Chiều cao tự nhiên (m) tường thân = w-extent của mặt cắt CAO NHẤT."""
    hs = []
    for lay in (layers or []):
        _, _, wmin, wmax = _bbox_ab(lay["section"].get("outer", [[0, 0]]))
        hs.append((wmax - wmin) * MM)
    return max(hs) if hs else 5.0


def _abut_body_u_range(layers: list):
    """Khoảng u (dọc cầu, mm) gộp mọi đoạn — để căn tâm bệ dưới thân."""
    us = []
    for lay in (layers or []):
        for s in _section_solids(lay["section"]):
            for (u, _w) in s["outer"]:
                us.append(u)
    if not us:
        return 0.0, 0.0
    return min(us), max(us)


def migrate_abutment(mo: dict) -> dict:
    """Đảm bảo bản ghi mố đúng schema (be plan + than longitudinal có loft).

    Giữ nguyên `than.layers` nếu đã có; nếu thiếu cả layers lẫn section đơn →
    seed mặt cắt mặc định."""
    if not isinstance(mo, dict):
        return default_abutment()
    out = dict(mo)
    parts = dict(out.get("parts") or {})
    base = default_abutment()["parts"]
    than = dict(parts.get("than") or {})
    has_layers = bool(than.get("layers")) and any(
        (l.get("section") or {}).get("outer") for l in than["layers"])
    has_single = len(than.get("section", {}).get("outer", [])) >= 3
    if not has_layers and not has_single:
        than["section"] = base["than"]["section"]
        than.setdefault("B", 8.0)
    than.setdefault("flex", True)
    out["parts"] = {"than": than}          # bỏ bệ — tường thân gồm cả bệ
    out["loai"] = "mo"
    return out


def _abut_body_height_m(than: dict, H_tru: float = None, H_be: float = 0.0) -> float:
    # Tường thân GỒM cả bệ → chiều cao đủ = H_tru (không trừ bệ riêng).
    layers = abut_body_layers(than)
    raw = _abut_body_raw_h(layers) if layers else 5.0
    if H_tru is not None:
        return max(0.5, float(H_tru))
    return raw


def abutment_total_height(mo: dict, H_tru: float = None) -> float:
    p = migrate_abutment(mo)
    if H_tru is not None:
        return round(float(H_tru), 3)
    return round(_abut_body_height_m(p["parts"]["than"], None), 3)


# ── Dựng khối tường thân: đùn thẳng hoặc loft theo NGANG cầu (y) ─────────────
def _abut_body_straight_mesh(sec, y0, B, x_face, out_dir, zmap,
                             color, name):
    """Đùn THẲNG 1 mặt cắt dọc (u,w) theo ngang cầu y0..y0+B (hằng dạng).
    Hỗ trợ nhiều khối rời + lỗ rỗng. (u,w) → (x = x_face+out_dir*u, z = zmap(w))."""
    solids = _section_solids(sec)
    if not solids:
        return None
    _, _, _wm, _ = _solids_bbox(solids)

    def _conv(pts):
        return [(x_face + out_dir * u * MM, zmap(w, _wm)) for (u, w) in pts]

    _mp = []
    for s in solids:
        outer = _conv(s["outer"])
        holes = [_conv(h) for h in s.get("holes", [])]
        _mp.append(_extrude(outer, holes, "xz", y0, B))
    return _mesh(_merge_parts(_mp), color, name)


def _abut_body_loft_mesh(secA, secB, y0, B, x_face, out_dir, zmap,
                         color, name, N=48, M=12):
    """Vuốt nối mặt cắt dọc A→B theo NGANG cầu y0..y0+B. Mỗi mặt cắt (u,w) →
    vòng (x,z); nội suy tuyến tính ring A→B dọc trục y, kèm nắp 2 đầu."""
    oA = (secA or {}).get("outer"); oB = (secB or {}).get("outer")
    if not oA or not oB or len(oA) < 3 or len(oB) < 3:
        return _abut_body_straight_mesh(secA, y0, B, x_face, out_dir,
                                        zmap, color, name)
    _, _, _wA, _ = _bbox_ab(oA); _, _, _wB, _ = _bbox_ab(oB)
    A = [[x_face + out_dir * u * MM, zmap(w, _wA)] for (u, w) in oA]
    Bp = [[x_face + out_dir * u * MM, zmap(w, _wB)] for (u, w) in oB]
    ra = _resample_ring(A, N)
    rb = _best_roll(ra, _resample_ring(Bp, N))
    vx, vy, vz = [], [], []
    for i in range(M + 1):
        t = i / M
        y = y0 + B * t
        ring = ra * (1 - t) + rb * t
        for (x, z) in ring:
            vx.append(x); vy.append(y); vz.append(z)
    I, J, K = [], [], []
    for i in range(M):                                   # thành bên
        for j in range(N):
            a = i * N + j;            b = i * N + (j + 1) % N
            c = (i + 1) * N + (j + 1) % N; e = (i + 1) * N + j
            I += [a, a]; J += [b, c]; K += [c, e]
    _, t0 = _triangulate([list(p) for p in ra], [])      # nắp đầu (y0, đảo chiều)
    for (p, q, r) in t0:
        I.append(p); J.append(r); K.append(q)
    base = M * N
    _, t1 = _triangulate([list(p) for p in rb], [])      # nắp cuối (y0+B)
    for (p, q, r) in t1:
        I.append(base + p); J.append(base + q); K.append(base + r)
    return go.Mesh3d(x=vx, y=vy, z=vz, i=I, j=J, k=K, color=color, opacity=0.96,
                     name=name, showlegend=bool(name), flatshading=True,
                     hovertemplate=f"{name}<extra></extra>")


def _clip_poly_w(poly, wc, keep_below):
    """Cắt đa giác (list [u,w]) tại đường ngang w=wc. keep_below=True → giữ phần
    w<=wc (BỆ); False → giữ phần w>=wc (TƯỜNG). Thêm điểm giao tại cạnh cắt qua."""
    if not poly:
        return []
    pts = poly[:-1] if poly[0] == poly[-1] else poly
    n = len(pts)
    inside = (lambda w: w <= wc + 1e-9) if keep_below else (lambda w: w >= wc - 1e-9)
    out = []
    for i in range(n):
        a = pts[i]; b = pts[(i + 1) % n]
        ai, bi = inside(a[1]), inside(b[1])
        if ai:
            out.append([a[0], a[1]])
        if ai != bi and abs(b[1] - a[1]) > 1e-9:
            t = (wc - a[1]) / (b[1] - a[1])
            out.append([a[0] + t * (b[0] - a[0]), wc])
    return out


def abut_body_traces(layers, zmap, x_face, out_dir, color,
                     name="Tường thân", target_width=None, ftop_w=None,
                     be_color=None, be_name="Bệ mố"):
    """Render tường thân: list đoạn [{section,B,loft}] xếp NGANG cầu (căn giữa
    tim cầu y=0), đoạn loft vuốt sang đoạn sau; còn lại đùn thẳng. zmap(w,wmin)→z.
    ftop_w (đỉnh bệ) cho → TÁCH mỗi đoạn thành BỆ (dưới) + TƯỜNG (trên) để nhận
    diện bệ mố. target_width: co/giãn tổng bề rộng ngang = bề rộng cầu."""
    layers = [l for l in (layers or []) if (l.get("section") or {}).get("outer")]
    if not layers:
        return []
    be_color = be_color or _COL["be"]
    total_B = abut_body_total_B(layers)
    _fB = (float(target_width) / total_B) if (target_width and total_B > 1e-6) else 1.0
    y = -total_B * _fB / 2.0
    multi = len(layers) > 1
    out = []
    for i, lay in enumerate(layers):
        _B = float(lay.get("B", 8.0) or 8.0) * _fB
        secA = lay["section"]
        nm = f"{name} #{i + 1}" if multi else name
        _is_loft = bool(lay.get("loft")) and i + 1 < len(layers)
        if ftop_w is not None and not _is_loft:
            # TÁCH bệ (dưới ftop) + tường (trên ftop) → nhận diện BỆ MỐ riêng.
            for s in _section_solids(secA):
                # BỆ = chữ nhật SẠCH (u-extent vùng bệ × đáy→đỉnh bệ) → đáy bệ 1
                # cấp, gờ bệ phẳng (bỏ bậc lẻ của tường cánh trong vùng bệ).
                _fp = [p for p in s["outer"] if p[1] <= ftop_w + 1e-6]
                if _fp:
                    # u-extent CHỈ theo vùng bệ (≤ đỉnh bệ) — KHÔNG lấy cả mặt vát
                    # tường cánh nhô về trước (gây "khối thừa" dưới chân bệ).
                    _fu = [p[0] for p in _fp]
                    _wm = min(p[1] for p in _fp)
                    fmin, fmax = min(_fu), max(_fu)
                    out.append(_abut_body_straight_mesh(
                        {"outer": [[fmin, _wm], [fmax, _wm],
                                   [fmax, ftop_w], [fmin, ftop_w]], "holes": []},
                        y, _B, x_face, out_dir, zmap, be_color, be_name))
                wall = _clip_poly_w(s["outer"], ftop_w, False)
                if len(wall) >= 3:
                    out.append(_abut_body_straight_mesh(
                        {"outer": wall, "holes": []}, y, _B, x_face, out_dir,
                        zmap, color, nm))
        elif _is_loft:
            secB = layers[i + 1]["section"]
            out.append(_abut_body_loft_mesh(secA, secB, y, _B, x_face, out_dir,
                                            zmap, color, nm))
        else:
            out.append(_abut_body_straight_mesh(secA, y, _B, x_face, out_dir,
                                                zmap, color, nm))
        y += _B
    return [t for t in out if t is not None]


def _abut_seat_w(layers):
    """(seat_w, w_bot) của VAI KÊ dầm — đơn vị mặt cắt: ledge NGANG cao nhất NẰM
    DƯỚI mép trên (tường đỉnh) của đoạn THÂN CHÍNH (B lớn nhất). Dầm kê tại seat_w;
    w_bot = đáy đoạn đó. (None,None) nếu không xác định được."""
    lays = [l for l in (layers or []) if (l.get("section") or {}).get("outer")]
    if not lays:
        return None, None
    body = max(lays, key=lambda l: float(l.get("B", 0) or 0))
    pts = body["section"]["outer"]
    ws = [w for (_u, w) in pts]
    w_top, w_bot = max(ws), min(ws)
    ledges = []
    n = len(pts)
    for i in range(n):
        u0, w0 = pts[i]; u1, w1 = pts[(i + 1) % n]
        if abs(w1 - w0) < 5.0 and abs(u1 - u0) > 300.0:    # đoạn ngang ≥ 300mm
            ledges.append(w0)
    below = [w for w in ledges if w < w_top - 200.0]       # ledge dưới tường đỉnh
    return (max(below) if below else w_top), w_bot


def abut_seat_u_m(mo: dict) -> float:
    """u (m) TÂM VAI KÊ dầm (ledge ngang cao nhất dưới tường đỉnh) của đoạn thân
    chính → để CĂN vai kê về đúng vị trí gối (đầu dầm). 0.0 nếu không xác định."""
    p = migrate_abutment(mo)
    lays = [l for l in abut_body_layers(p["parts"]["than"])
            if (l.get("section") or {}).get("outer")]
    if not lays:
        return 0.0
    body = max(lays, key=lambda l: float(l.get("B", 0) or 0))
    pts = body["section"]["outer"]
    w_top = max(w for (_u, w) in pts)
    best_w, best_us = None, None
    n = len(pts)
    for i in range(n):
        u0, w0 = pts[i]; u1, w1 = pts[(i + 1) % n]
        if (abs(w1 - w0) < 5.0 and abs(u1 - u0) > 300.0
                and w0 < w_top - 200.0 and (best_w is None or w0 > best_w)):
            best_w, best_us = w0, (min(u0, u1), max(u0, u1))
    if best_us is None:
        return 0.0
    return (best_us[0] + best_us[1]) / 2.0 * MM


def abut_backwall_u_m(mo: dict) -> float:
    """u (m) MẶT TRƯỚC TƯỜNG ĐỈNH (tường tai) = mép vai kê phía có tường DÂNG LÊN
    tới đỉnh — ĐẦU DẦM kê sát mặt này. Dùng để chừa KHOẢNG HỞ đầu dầm ↔ mố.
    0.0 nếu không xác định."""
    p = migrate_abutment(mo)
    lays = [l for l in abut_body_layers(p["parts"]["than"])
            if (l.get("section") or {}).get("outer")]
    if not lays:
        return 0.0
    body = max(lays, key=lambda l: float(l.get("B", 0) or 0))
    pts = body["section"]["outer"]
    w_top = max(w for (_u, w) in pts); n = len(pts)
    best_w, seg = None, None
    for i in range(n):
        u0, w0 = pts[i]; u1, w1 = pts[(i + 1) % n]
        if (abs(w1 - w0) < 5.0 and abs(u1 - u0) > 300.0
                and w0 < w_top - 200.0 and (best_w is None or w0 > best_w)):
            best_w, seg = w0, (i, (i + 1) % n)
    if seg is None:
        return 0.0
    # Endpoint nào có cạnh kề DÂNG LÊN cao hơn (về tường đỉnh) = back wall.
    _rise = lambda idx: max(pts[(idx - 1) % n][1], pts[(idx + 1) % n][1])
    ia, ib = seg
    return (pts[ia][0] if _rise(ia) >= _rise(ib) else pts[ib][0]) * MM


def _abut_footing_top_w(layers, seat_w, w_bot):
    """w (đơn vị mặt cắt) của ĐỈNH BỆ = ledge ngang cao nhất NẰM GIỮA đáy bệ và
    vai kê (nơi bệ bè rộng ra). None nếu thân thẳng (không có bệ riêng)."""
    lays = [l for l in (layers or []) if (l.get("section") or {}).get("outer")]
    if not lays:
        return None
    body = max(lays, key=lambda l: float(l.get("B", 0) or 0))
    pts = body["section"]["outer"]; n = len(pts)
    cand = []
    for i in range(n):
        u0, w0 = pts[i]; u1, w1 = pts[(i + 1) % n]
        if (abs(w1 - w0) < 5.0 and abs(u1 - u0) > 300.0
                and w_bot + 200.0 < w0 < seat_w - 200.0):
            cand.append(w0)
    return max(cand) if cand else None


def _abut_zmap(layers, z_betop, seat_z, H_tru, than):
    """Trả HÀM zmap(w, sec_wmin) → cao độ z. seat_z cho → NEO ĐỈNH BỆ = z_betop
    (=ĐTN−0.5, bệ CHÌM dưới đất) và VAI KÊ = seat_z (đáy dầm); BỆ giữ tỉ lệ thật
    (tụt xuống dưới đỉnh bệ), chỉ THÂN TƯỜNG co giãn, tường đỉnh giữ tỉ lệ thật →
    đúng hình thư viện + bệ dưới ĐTN. seat_z=None → tỉ lệ thật theo từng đoạn."""
    if seat_z is not None:
        seat_w, w_bot = _abut_seat_w(layers)
        ftop = _abut_footing_top_w(layers, seat_w, w_bot) if (seat_w and w_bot) else None
        if seat_w is not None and ftop is not None and (seat_w - ftop) > 1e-6:
            _wall = seat_w - ftop
            def zmap(w, _swm):
                if w >= seat_w:                      # TƯỜNG ĐỈNH: tỉ lệ thật
                    return seat_z + (w - seat_w) * MM
                if w >= ftop:                        # THÂN TƯỜNG: co giãn
                    return z_betop + (w - ftop) / _wall * (seat_z - z_betop)
                return z_betop + (w - ftop) * MM     # BỆ: tỉ lệ thật, CHÌM xuống dưới
            return zmap
        # Không tách được bệ → co giãn đều, neo vai kê=seat_z, đỉnh = z_betop.
        if seat_w is not None and w_bot is not None and (seat_w - w_bot) * MM > 1e-6:
            vsc = (seat_z - z_betop) / ((seat_w - w_bot) * MM)
            return lambda w, _swm: z_betop + (w - w_bot) * MM * vsc
    raw_h = _abut_body_raw_h(layers) if layers else 5.0
    body_h = _abut_body_height_m(than, H_tru)
    vsc = (body_h / raw_h) if raw_h > 1e-6 else 1.0
    return lambda w, sec_wmin: z_betop + (w - sec_wmin) * MM * vsc


def build_abutment_mesh_traces(mo: dict, H_tru: float = None, x_face: float = 0.0,
                               out_dir: float = 1.0, z_base: float = 0.0,
                               labels: dict = None, seat_z: float = None,
                               target_width: float = None) -> list:
    """list go.Mesh3d của 1 mố. x_face: lý trình tim (đường hồng); out_dir: ±1
    hướng MẶT TRƯỚC vào nhịp; z_base: đáy bệ. seat_z: cao độ VAI KÊ (=đáy dầm).
    target_width: co/giãn bề rộng NGANG mố = bề rộng cầu."""
    L = labels or _MO_LABEL
    p = migrate_abutment(mo)
    than = p["parts"]["than"]
    layers = abut_body_layers(than)
    zmap = _abut_zmap(layers, z_base, seat_z, H_tru, than)
    # Nhận diện ĐỈNH BỆ → tách khối BỆ MỐ riêng trong 3D (đáy mố là 1 bệ liền).
    _sw, _wb = _abut_seat_w(layers)
    _ftop = _abut_footing_top_w(layers, _sw, _wb) if (_sw and _wb) else None

    # TƯỜNG THÂN + BỆ: các đoạn mặt cắt dọc xếp theo NGANG cầu, loft vuốt mượt.
    traces = abut_body_traces(layers, zmap, x_face, out_dir,
                              _COL["than"], L["than"], target_width=target_width,
                              ftop_w=_ftop, be_color=_COL["be"], be_name=L["be"])
    traces = [t for t in traces if t is not None]
    _seen = set()                       # gộp chú giải trùng (Bệ mố / Tường thân)
    for t in traces:
        _n = getattr(t, "name", "") or ""
        try:
            t.showlegend = bool(_n) and (_n not in _seen)
        except Exception:
            pass
        _seen.add(_n)
    return traces


def abutment_elevation_polys(mo: dict, H_tru: float = None, x_face: float = 0.0,
                             out_dir: float = 1.0, z_base: float = 0.0,
                             labels: dict = None, seat_z: float = None) -> list:
    """Bóng MẶT ĐỨNG DỌC cầu (x-z) của mố → list {name,color,xs,zs}.
    seat_z: cao độ VAI KÊ (=đáy dầm) — neo vai kê tại seat_z, đáy bệ tại z_base."""
    L = labels or _MO_LABEL
    p = migrate_abutment(mo)
    than = p["parts"]["than"]
    layers = abut_body_layers(than)
    zmap = _abut_zmap(layers, z_base, seat_z, H_tru, than)

    # Đoạn THÂN CHÍNH (B lớn nhất) = NÉT THẤY (vết cắt tim cầu); tường cánh ở 2
    # biên ngang → NÉT KHUẤT (đứng sau/trước mặt phẳng cắt).
    _bi = (max(range(len(layers)), key=lambda i: float(layers[i].get("B", 0) or 0))
           if layers else -1)
    polys = []
    for i, lay in enumerate(layers):
        sec = lay["section"]
        _, _, _wm, _ = _bbox_ab(sec["outer"])
        polys.append({"name": L["than"], "color": _COL["than"],
                      "xs": [x_face + out_dir * u * MM for (u, w) in sec["outer"]],
                      "zs": [zmap(w, _wm) for (u, w) in sec["outer"]],
                      "hidden": (i != _bi)})
    return polys


def abutment_mcn_polys(mo: dict, z_seat: float, z_base: float,
                       labels: dict = None, target_width: float = None) -> list:
    """MẶT CẮT NGANG cầu của mố (ngang y × cao z) → list {name,color,ys,zs,hidden}.
    Mỗi đoạn (tường cánh/thân) tách 3 dải theo cao độ → thể hiện đầy đủ:
      • BỆ (đáy → đỉnh bệ) — khối bệ.
      • THÂN TRƯỚC vai kê (đỉnh bệ → vai kê=đáy dầm) — NÉT THẤY (mặt trước mố).
      • SAU vai kê (vai kê → đỉnh tường đỉnh) — NÉT KHUẤT (phần sau mố).
    target_width: co/giãn tổng bề rộng ngang = bề rộng cầu."""
    p = migrate_abutment(mo)
    than = p["parts"]["than"]
    layers = abut_body_layers(than)
    if not layers:
        return []
    zmap = _abut_zmap(layers, z_base, z_seat, None, than)
    seat_w, w_bot = _abut_seat_w(layers)
    ftop = _abut_footing_top_w(layers, seat_w, w_bot) if (seat_w and w_bot) else None
    z_betop = zmap(ftop, w_bot) if ftop is not None else (z_base + 0.8)
    total_B = abut_body_total_B(layers)
    _fB = (float(target_width) / total_B) if (target_width and total_B > 1e-6) else 1.0
    y = -total_B * _fB / 2.0
    out = []
    for lay in layers:
        B = float(lay.get("B", 8.0) or 8.0) * _fB
        ws = [w for (_u, w) in lay["section"]["outer"]]; _wm = min(ws)
        z_lo = zmap(min(ws), _wm); z_hi = zmap(max(ws), _wm); y1 = y + B
        def _rect(za, zb, name, color, hidden):
            if zb - za > 1e-6:
                out.append({"name": name, "color": color, "hidden": hidden,
                            "ys": [y, y1, y1, y], "zs": [za, za, zb, zb]})
        _rect(z_lo, min(z_betop, z_hi), "Bệ mố", _COL["be"], False)
        _rect(max(z_betop, z_lo), min(z_seat, z_hi), "Thân mố (trước)", _COL["than"], False)
        _rect(max(z_seat, z_lo), z_hi, "Sau mố (khuất)", _COL["than"], True)
        y = y1
    return out


def abutment_plan_polys(mo: dict, target_width: float = None,
                        labels: dict = None) -> list:
    """MẶT BẰNG (footprint) mố → list {name,color,xs(ngang),ys(dọc)}. Mỗi đoạn =
    1 chữ nhật: ngang = bề rộng B (đã co theo cầu), dọc = khoảng u mặt cắt. Tạo
    hình chữ U/T (thân rộng + 2 cánh dài về sau). Căn dọc theo VAI KÊ (gối)."""
    L = labels or _MO_LABEL
    p = migrate_abutment(mo)
    than = p["parts"]["than"]
    layers = abut_body_layers(than)
    if not layers:
        return []
    total_B = abut_body_total_B(layers)
    _fB = (float(target_width) / total_B) if (target_width and total_B > 1e-6) else 1.0
    su = abut_seat_u_m(mo)                      # dịch dọc → vai kê về 0
    y = -total_B * _fB / 2.0
    out = []
    for lay in layers:
        B = float(lay.get("B", 8.0) or 8.0) * _fB
        us = [u for (u, _w) in lay["section"]["outer"]]
        d0, d1 = min(us) * MM - su, max(us) * MM - su
        out.append({"name": L["than"], "color": _COL["than"],
                    "xs": [y, y + B, y + B, y],
                    "ys": [d0, d0, d1, d1]})
        y += B
    return out


def build_abutment_preview_fig(mo: dict, H_tru: float = None,
                               labels: dict = None, target_width: float = None,
                               seat_z: float = None, z_base: float = 0.0) -> go.Figure:
    """Figure 3D xem trước 1 mố (panel thư viện).
    target_width: co bề rộng mố theo bề rộng cầu (để KHỚP mố trong 3D toàn cầu).
    seat_z/z_base: nếu cho → NEO vai kê=seat_z, đỉnh bệ=z_base như mố trên CẦU
    (đồng bộ chiều cao 3D với mố thực tế của cầu)."""
    fig = go.Figure(build_abutment_mesh_traces(mo, H_tru=H_tru, labels=labels,
                                               target_width=target_width,
                                               seat_z=seat_z, z_base=z_base))
    fig.update_layout(
        scene=dict(xaxis_title="Dọc cầu (m)", yaxis_title="Ngang cầu (m)",
                   zaxis_title="Cao độ (m)", aspectmode="data"),
        template="plotly_dark", height=660,
        margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
        scene_camera=dict(eye=dict(x=1.7, y=-1.5, z=0.9)),
    )
    return fig
