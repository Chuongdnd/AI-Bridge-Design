"""
Module 11 — Bản vẽ kết cấu cầu (2D + 3D)
Tất cả hình vẽ tạo từ design_data — không cần dữ liệu khảo sát.
Khi có df_tim_line (địa hình) → tự động overlay vào sơ đồ nhịp.

Hàm xuất:
  ve_so_do_nhip_2d(d, df_tim_line=None) — Sơ đồ nhịp với trụ đặt ngoài tĩnh không
  ve_mat_cat_ngang_2d(d)               — MCN điển hình đầy đủ
  ve_cau_3d(d, df_tim_line=None)       — Mô hình 3D kết cấu + địa hình nếu có
"""

import numpy as np
import plotly.graph_objects as go

# ── Sơ đồ cọc khai báo từ DXF (utils/pile_plan.py) ───────────────────────────
try:
    import utils.pile_plan as PP
except Exception:  # pragma: no cover - giữ chạy được nếu thiếu module
    PP = None

# ── Engine trụ lắp ghép (nạp trễ, dùng chung) ────────────────────────────────
_PB_ENGINE = None


def _get_PB():
    """Nạp 19-PierBuilder.py một lần (tránh phụ thuộc vòng)."""
    global _PB_ENGINE
    if _PB_ENGINE is None:
        import importlib.util as _iu
        import os as _os
        _d = _os.path.dirname(_os.path.abspath(__file__))
        _s = _iu.spec_from_file_location("PierBuilder",
                                         _os.path.join(_d, "19-PierBuilder.py"))
        _m = _iu.module_from_spec(_s)
        _s.loader.exec_module(_m)
        _PB_ENGINE = _m
    return _PB_ENGINE

# ── Bảng màu ─────────────────────────────────────────────────────────────────
# Quy tắc thể hiện bản vẽ — LAYER áp cho bản vẽ 2D:
#   layer 3 (xanh lá)  = đường bao cấu kiện CÓ cốt thép (BTCT)
#   layer 4 (xanh nhạt)= kích thước (DIM) + nét cấu kiện mảnh
#   layer 5 (xanh dương)= nét mảnh (taluy, break line)
_LAYER3 = "#1e8449"   # xanh lá — đường bao BTCT
_LAYER5 = "#2e5cb8"   # xanh dương — nét mảnh / taluy / break line
_C = {
    "btong":    "#c8d6c0",
    "btong_dk": _LAYER3,   # đường bao BTCT = layer 3 (xanh lá)
    "bao":      _LAYER3,   # alias đường bao cấu kiện BTCT
    "be":       "#aab7b8",
    "be_dk":    "#566573",
    "dam":      "#85929e",
    "dam_dk":   _LAYER3,   # đường bao xà mũ/dầm BTCT = layer 3
    "ban":      "#d5d8dc",
    "phu":      "#2c3e50",
    "lan_can":  "#7f8c8d",
    "nuoc":     "rgba(52,152,219,0.35)",
    "dat":      "rgba(169,120,74,0.35)",
    "tk":       "rgba(231,76,60,0.12)",
    "tk_line":  "#e74c3c",
    "moc":      "#c0a06b",
    "dim":      "#1f9ed1",   # nét DIM = layer 4 "xanh nhạt" (quy tắc thể hiện bản vẽ)
    "dia_hinh": "#27ae60",
}

# Cỡ chữ kích thước theo chuẩn (1.8mm) — quy đổi xấp xỉ sang px màn hình
_DIM_TXT = 9
_DIM_ARROW = 1.2  # mũi tên closed filled (~1.5mm)
KHO_HO_DAM_MO = 0.10  # m — khoảng hở (khe co giãn) đầu dầm ↔ mặt trước tường đỉnh mố


def _snap_be_tops(be_tops, thresh=1.0):
    """ĐỒNG BỘ cao độ ĐỈNH BỆ giữa các trụ: nếu chênh lệch (max−min) ≤ thresh (m,
    ~1m) → gộp về 1 cao độ LÀM TRÒN NGUYÊN (không thập phân). Ngược lại giữ nguyên
    từng trụ (địa hình chênh nhiều). Trả list cùng độ dài."""
    vals = [v for v in be_tops if v is not None]
    if len(vals) < 2 or (max(vals) - min(vals)) > thresh + 1e-9:
        return list(be_tops)
    _common = float(round(sum(vals) / len(vals)))     # 1 cao độ chẵn dùng chung
    return [_common if v is not None else None for v in be_tops]


def _pier_be_top(xt, terrain_fn, z_cap_b):
    """Đỉnh bệ 1 trụ (thô, chưa đồng bộ): chôn 0.5m dưới ĐTN, chừa ≥0.5m thân."""
    return min(float(terrain_fn(xt)) - 0.5, float(z_cap_b) - 0.5)


def _hex_rgba(col, op=1.0):
    """'#rrggbb' → 'rgba(r,g,b,op)'. Nếu đã là rgb/rgba thì giữ nguyên."""
    c = str(col or "#888888")
    if c.startswith("#") and len(c) >= 7:
        try:
            r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
            return f"rgba({r},{g},{b},{op})"
        except ValueError:
            return c
    return c


def _stitch_loops(segs, q=1e-3):
    """Nối các ĐOẠN giao (mesh × mặt phẳng) thành các VÒNG KÍN → list [(a,b)].
    Lượng tử hoá điểm về lưới q(m) để khớp đầu mút. Tham lam, hợp mặt cắt lồi/hộp."""
    def _k(p):
        return (round(p[0] / q), round(p[1] / q))
    adj = {}; pos = {}
    for a, b in segs:
        ka, kb = _k(a), _k(b)
        if ka == kb:
            continue
        pos[ka] = a; pos[kb] = b
        adj.setdefault(ka, set()).add(kb)
        adj.setdefault(kb, set()).add(ka)
    loops = []; used = set()
    for start in list(adj):
        if start in used or len(adj[start]) == 0:
            continue
        loop = [start]; used.add(start); cur = start; prev = None
        while True:
            nxt = next((n for n in adj[cur] if n != prev and n not in used), None)
            if nxt is None:
                break
            loop.append(nxt); used.add(nxt); prev, cur = cur, nxt
            if start in adj[cur] and len(loop) >= 3:
                break
        if len(loop) >= 3:
            loops.append([pos[k] for k in loop])
    return loops


def _convex_hull(pts):
    """Bao lồi 2D (Andrew monotone chain) → list điểm CCW. pts: [(a,b)]."""
    pts = sorted(set((round(p[0], 4), round(p[1], 4)) for p in pts))
    if len(pts) <= 2:
        return pts
    def _cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lo = []
    for p in pts:
        while len(lo) >= 2 and _cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    hi = []
    for p in reversed(pts):
        while len(hi) >= 2 and _cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def project_mesh_traces(traces, axis="y"):
    """CHIẾU list go.Mesh3d lên mặt phẳng vuông góc trục `axis` → list
    {name,color,xs,zs} là BAO LỒI (silhouette) từng bộ phận. Dùng cho HÌNH CHIẾU
    ĐỨNG (trắc dọc): axis 'y' giữ (x=dọc, z=cao) → trụ 2 thân chiếu chồng thành 1
    cột (đúng elevation), khác với lát cắt mỏng tại tim làm MẤT cột."""
    m0, m1 = [i for i in (0, 1, 2) if i != {"x": 0, "y": 1, "z": 2}[axis]]
    groups = {}
    for t in traces:
        if getattr(t, "type", "") != "mesh3d":
            continue
        X, Y, Z = list(t.x or []), list(t.y or []), list(t.z or [])
        if not X:
            continue
        V = list(zip(X, Y, Z))
        nm = getattr(t, "name", "") or ""
        g = groups.setdefault(nm, {"pts": [], "color": getattr(t, "color", None)})
        g["pts"].extend((v[m0], v[m1]) for v in V)
    out = []
    for nm, g in groups.items():
        hull = _convex_hull(g["pts"])
        if len(hull) >= 3:
            out.append({"name": nm, "color": g["color"],
                        "xs": [p[0] for p in hull], "zs": [p[1] for p in hull]})
    return out


def cut_mesh_traces(traces, axis="y", value=0.0, q=1e-3):
    """CẮT list go.Mesh3d bằng mặt phẳng axis=value → list {name,color,xs,zs} là
    ĐƯỜNG BAO tiết diện thật, chiếu lên 2 trục còn lại. axis 'y' = cắt DỌC tim cầu
    (giữ x=dọc, z=cao) cho trắc dọc; 'x' = cắt NGANG tại lý trình (giữ y=ngang, z).
    Gom theo tên bộ phận rồi nối vòng kín (fill được)."""
    ax = {"x": 0, "y": 1, "z": 2}[axis]
    m0, m1 = [i for i in (0, 1, 2) if i != ax]
    groups = {}
    for t in traces:
        if getattr(t, "type", "") != "mesh3d":
            continue
        X, Y, Z = list(t.x or []), list(t.y or []), list(t.z or [])
        I, J, K = list(t.i or []), list(t.j or []), list(t.k or [])
        if not (X and I):
            continue
        V = list(zip(X, Y, Z))
        nm = getattr(t, "name", "") or ""
        g = groups.setdefault(nm, {"segs": [], "color": getattr(t, "color", None)})
        for a, b, c in zip(I, J, K):
            pts = []
            for p, r in ((a, b), (b, c), (c, a)):
                dp, dr = V[p][ax] - value, V[r][ax] - value
                if (dp < 0 <= dr) or (dr < 0 <= dp):
                    tt = dp / (dp - dr)
                    pts.append((V[p][m0] + tt * (V[r][m0] - V[p][m0]),
                                V[p][m1] + tt * (V[r][m1] - V[p][m1])))
            if len(pts) >= 2:
                g["segs"].append((pts[0], pts[1]))
    out = []
    for nm, g in groups.items():
        for loop in _stitch_loops(g["segs"], q):
            out.append({"name": nm, "color": g["color"],
                        "xs": [p[0] for p in loop], "zs": [p[1] for p in loop]})
    return out


def _abut_seat_z(cao_dd, pier_assembly):
    """Cao độ VAI KÊ (đáy dầm) PHÍA MỐ. Dầm SPT lên mố là ĐẦU TRƠN (không khấc)
    nên đáy dầm phía mố HẠ THẤP so với phía trụ đúng bằng ĐỘ SÂU KHẤC xà mũ →
    tường thân phần kê dầm thấp lại (đúng cấu tạo, không bị cao như phía trụ).
    pier_assembly=None (không có khấc) → giữ nguyên = cao_dd."""
    try:
        nd = (_get_PB().cap_seat_notch_depth_m(pier_assembly)
              if pier_assembly else 0.0)
    except Exception:
        nd = 0.0
    return float(cao_dd) - float(nd or 0.0)


def _terrain_z_at(d, df_geology, x, df_tim_line=None):
    """Cao độ ĐỊA HÌNH TỰ NHIÊN tại lý trình x — DÙNG CHUNG với 3D
    (add_all_to_terrain_fig, tim Offset==0 của df_geology) VÀ trắc dọc
    (df_tim_line). Ưu tiên df_geology; thiếu → df_tim_line; thiếu nữa → h_tn_tb.
    Nhờ vậy cao độ MÓNG ở các mặt cắt chi tiết BÁM địa hình y hệt 3D & trắc dọc."""
    h_tn = float((d or {}).get("h_tn_tb", 2.0))
    # (1) df_geology — nguồn của mô hình 3D
    if df_geology is not None and not getattr(df_geology, "empty", True):
        try:
            if {"Offset", "Lý trình", "Z"} <= set(df_geology.columns):
                _cl = df_geology[df_geology["Offset"] == 0]
                _lt = _cl["Lý trình"].values.astype(float)
                _z  = _cl["Z"].values.astype(float)
                if len(_lt) >= 2 and _lt.min() <= x <= _lt.max():
                    return float(np.interp(x, _lt, _z))
        except Exception:
            pass
    # (2) df_tim_line — nguồn của trắc dọc (nếu không có df_geology)
    if df_tim_line is not None and not getattr(df_tim_line, "empty", True):
        try:
            _lc = next((c for c in df_tim_line.columns
                        if 'ý trình' in c or c.lower() in ['ly_trinh', 'chainage']), None)
            _zc = next((c for c in df_tim_line.columns
                        if c.upper() in ['Z', 'CAO_DO', 'H', 'ELEVATION']), None)
            if _lc and _zc:
                _lt = df_tim_line[_lc].values.astype(float)
                _z  = df_tim_line[_zc].values.astype(float)
                if len(_lt) >= 2 and _lt.min() <= x <= _lt.max():
                    return float(np.interp(x, _lt, _z))
        except Exception:
            pass
    return h_tn


def _pier_be_tops_synced(piers, terrain_fn, soffit_fn):
    """Đỉnh bệ CHUẨN cho MỌI trụ — DÙNG CHUNG 3D · trắc dọc · mặt cắt chi tiết:
    min(ĐTN−0.5, đáy_dầm−1.0) rồi ĐỒNG BỘ cao độ chẵn (_snap_be_tops). Trả
    {round(xt,3): đỉnh_bệ}. Bảo đảm 3 view vẽ CÙNG cao độ móng từng trụ."""
    raw = [min(float(terrain_fn(xt)) - 0.5, float(soffit_fn(xt)) - 1.0)
           for xt in piers]
    return {round(xt, 3): v for xt, v in zip(piers, _snap_be_tops(raw))}

# ── Helpers ───────────────────────────────────────────────────────────────────
def _poly(fig, xs, ys, fill, line_c, name="", opacity=1.0, showlegend=None,
          lw=1.5, dash=None):
    sl = (name != "") if showlegend is None else showlegend
    xs = list(xs); ys = list(ys)
    # dash → NÉT KHUẤT (đường đứt), không tô nền (chỉ vẽ biên).
    fig.add_trace(go.Scatter(
        x=xs + [xs[0]], y=ys + [ys[0]],
        fill=(None if dash else "toself"), fillcolor=fill, opacity=opacity,
        line=dict(color=line_c, width=lw, dash=dash),
        mode="lines", name=name, showlegend=sl,
        hovertemplate=(f"<b>{name}</b><extra></extra>" if name else None),
    ))

def _clip_poly_above(xs, zs, z_min):
    """Cắt đa giác GIỮ phần z ≥ z_min (Sutherland–Hodgman 1 cạnh ngang). Dùng thể
    hiện ĐẦU DẦM KHẤC: bỏ phần dưới đáy khấc, GIỮ NGUYÊN hình (không bóp dẹt)."""
    n = len(xs)
    ox, oz = [], []
    for i in range(n):
        x1, z1 = xs[i], zs[i]
        x2, z2 = xs[(i + 1) % n], zs[(i + 1) % n]
        in1 = z1 >= z_min - 1e-9
        in2 = z2 >= z_min - 1e-9
        if in1:
            ox.append(x1); oz.append(z1)
        if in1 != in2 and abs(z2 - z1) > 1e-9:
            t = (z_min - z1) / (z2 - z1)
            ox.append(x1 + t * (x2 - x1)); oz.append(z_min)
    return ox, oz


def _skew_alpha_rad(d):
    """Góc giao (radian) đã clamp 30°–90°. 90° = không xiên."""
    try:
        g = float((d or {}).get("goc_giao", 90.0))
    except Exception:
        g = 90.0
    return np.radians(max(30.0, min(90.0, g)))


def _skew_widen(d) -> float:
    """Hệ số NỚI bề rộng phần dưới theo góc xiên: chiều dài THẬT của mố/trụ dọc
    trục xiên = bc/sin(α). Trả 1.0 khi cầu vuông góc (α≈90°)."""
    a = _skew_alpha_rad(d)
    s = np.sin(a)
    return 1.0 / s if s > 1e-6 else 1.0


def _skew_cot(d) -> float:
    """cot(α) — hệ số TRƯỢT mặt bằng theo góc xiên (dọc += ngang·cot). 0 khi α≈90°."""
    try:
        g = float((d or {}).get("goc_giao", 90.0))
    except Exception:
        g = 90.0
    if g >= 89.9 or g <= 0:
        return 0.0
    return 1.0 / np.tan(_skew_alpha_rad(d))


def _h_goi(d) -> float:
    """Chiều cao GỐI cầu (m): khoảng hở đáy dầm ↔ đỉnh xà mũ. Khai báo qua
    d['h_goi_m'] (mặc định 0.15m). Dầm SPT kê trên gối nên đỉnh xà mũ THẤP HƠN
    đáy dầm đúng bằng chiều cao gối."""
    try:
        return max(0.0, float(d.get("h_goi_m", 0.15)))
    except (TypeError, ValueError):
        return 0.15


# Khe hở đầu bản mặt cầu ↔ mố: 100mm (cầu lớn L≥100m) / 50mm (cầu nhỏ L<100m)
GAP_BAN_MO_LON  = 0.10
GAP_BAN_MO_NHO  = 0.05
L_CAU_NHO_MAX   = 100.0     # L < 100m = cầu nhỏ
KHO_HO_DAY_DAM  = 0.10      # 100mm khe hở đáy dầm ↔ đỉnh tĩnh không
H_DA_KE_GOI     = 0.15      # 150mm đá kê gối + gối (đáy dầm ↔ đỉnh xà mũ)


def _gap_ban_mo(L_cau: float) -> float:
    """Khe hở mỗi đầu bản mặt cầu tới mố (m)."""
    return GAP_BAN_MO_NHO if float(L_cau) < L_CAU_NHO_MAX else GAP_BAN_MO_LON


def make_red_line(d):
    """Trắc dọc thiết kế (ĐƯỜNG ĐỎ) — DÙNG CHUNG cho trắc dọc / dầm / 3D.

    - Đỉnh đường cong đứng lồi đặt tại TIM TĨNH KHÔNG (x_tim_clearance).
    - Cao độ đỉnh = đỉnh tĩnh không THÔNG THUYỀN (MNTT + H) + 100mm khe hở đáy
      dầm (xét đáy dầm biên xếp theo dốc ngang → cộng (Bc/2)·i_ngang)
      + chiều cao dầm + chiều dày bản mặt cầu.
    - Cong theo bán kính R_hinh_hoc; ngoài cung / khi R≤0 → 2 nhánh dốc thẳng
      theo dốc dọc i_max_hinh_hoc; i=0 & R≤0 → phẳng.

    Trả (z_red_fn, x_apex, z_crown, t_ban, H_dam).
    """
    kcn   = d.get("kcn_result") or d.get("ai_result", {})
    geo   = d.get("geo_logic", {})
    MNTT  = float(d.get("MNTT", 2.0))
    H_tk  = float(d.get("H", 3.0))
    H_dam = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    t_ban = float(d.get("t_ban_mm", 200)) / 1000.0
    bc    = float(d.get("bc", 12.0))
    i_ng  = abs(float(d.get("i_doc_ngang", 2.0))) / 100.0
    x0    = float(geo.get("x_mo_trai", -60.0))
    x_end = float(geo.get("x_mo_phai", 60.0))
    x_tim = float(geo.get("x_tim_clearance", (x0 + x_end) / 2))
    R     = float(d.get("R_hinh_hoc", 0) or 0)
    i_gr  = abs(float(d.get("i_max_hinh_hoc", 0) or 0)) / 100.0

    # ĐƯỜNG ĐỎ = TRẮC DỌC THIẾT KẾ theo KHAI BÁO (đường cong đứng lồi bán kính R
    # + độ dốc dọc i người dùng khai báo/tính). ĐỈNH đặt tại TIM TĨNH KHÔNG; cao độ
    # đỉnh đặt sao cho ĐÁY DẦM BIÊN tại nhịp chính vừa đủ hở TĨNH KHÔNG CAO NHẤT
    # (max lũ & thông thuyền = cao_day_dam hệ thống). Vẫn KIỂM SOÁT không cho vi
    # phạm ĐK1 an-toàn-lũ ở mọi điểm (nâng đường đỏ nếu cần).
    MNCN = float(d.get("MNCN", 3.5))
    _cao_dd_sys = float(d.get("cao_day_dam", 0) or 0)   # đáy dầm biên nhịp chính
    if _cao_dd_sys <= 0:                                 # suy dự phòng nếu thiếu
        _cao_dd_sys = max(MNCN + 0.50, MNTT + H_tk + KHO_HO_DAY_DAM)
    _extra   = (bc / 2.0) * i_ng + H_dam + t_ban        # đáy dầm biên → đỉnh bản tại tim
    z_crown  = _cao_dd_sys + _extra                     # đỉnh đường đỏ (tại tim TK)
    z_floor  = (MNCN + 0.50) + _extra                   # đỉnh bản tối thiểu (ĐK1 lũ)
    # Nâng đỉnh thêm độ VÕNG của đường cong đứng trong bề rộng khổ tĩnh không, để
    # đáy dầm tại MÉP khổ (x_tim ± B_tk/2) vẫn KHÔNG PHẠM tĩnh không thông thuyền.
    B_tk = float(d.get("B", 20.0))
    if R > 0:
        z_crown += (B_tk / 2.0) ** 2 / (2.0 * R)

    def _raw(x):
        # Đường cong đứng lồi theo KHAI BÁO: parabol bán kính R quanh đỉnh, ngoài
        # cung nối dốc thẳng i. R≤0 → chỉ dốc i; i=0 & R≤0 → phẳng.
        dx = abs(x - x_tim)
        if R > 0:
            x_tan = R * i_gr if i_gr > 0 else float("inf")
            if dx <= x_tan:
                return z_crown - dx * dx / (2.0 * R)
            z_tan = z_crown - x_tan * x_tan / (2.0 * R)
            return z_tan - (dx - x_tan) * i_gr
        if i_gr > 0:
            return z_crown - dx * i_gr
        return z_crown

    def _z_red(x):
        # Theo trắc dọc khai báo, NHƯNG không thấp hơn mức ĐK1 lũ (nâng nếu vi phạm).
        return max(_raw(x), z_floor)

    return _z_red, x_tim, z_crown, t_ban, H_dam


def _goi_block_2d(fig, xc, z_cap_t, h_goi, w=0.45, color="#34495e",
                  name="", sl=False):
    """Khối GỐI (mặt đứng/MCN 2D): hộp nhỏ từ đỉnh xà mũ lên đáy dầm tại 1 gối."""
    if h_goi <= 0:
        return
    _poly(fig, [xc - w/2, xc + w/2, xc + w/2, xc - w/2],
          [z_cap_t, z_cap_t, z_cap_t + h_goi, z_cap_t + h_goi],
          color, "#1c2833", name, opacity=0.95, showlegend=sl, lw=1.0)


def _hline(fig, y, x0, x1, label, color, dash="dot", lw=1.5):
    fig.add_shape(type="line", x0=x0, y0=y, x1=x1, y1=y,
                  line=dict(color=color, width=lw, dash=dash))
    if label:
        fig.add_annotation(x=x0 + (x1-x0)*0.05, y=y, text=f" {label}", showarrow=False,
                           font=dict(size=8, color=color), yanchor="bottom", xanchor="left")

def _rec_dim(fig, kind, a, b, off, text):
    """Ghi dữ liệu KÍCH THƯỚC lên fig.layout.meta để xuất DIM thật ra DXF
    (kind 'h'/'v', a,b = 2 mép, off = vị trí đường dim, text = nhãn)."""
    try:
        _m = fig.layout.meta
        _m = dict(_m) if isinstance(_m, dict) else {}
        _m["cau_dims"] = list(_m.get("cau_dims", [])) + \
            [[kind, float(a), float(b), float(off), str(text)]]
        fig.layout.meta = _m
    except Exception:
        pass


def _dim_h(fig, y, x0, x1, text, color=None, dy=0):
    """Đường kích thước NGANG — nét DIM xanh nhạt + 2 mũi tên closed filled
    (theo bảng KÍCH THƯỚC trong quy tắc thể hiện bản vẽ)."""
    color = color or _C["dim"]
    ya = y + dy
    _rec_dim(fig, "h", x0, x1, ya, text)
    # đường dim + mũi tên 2 đầu (head ở x0 và x1, hướng ra ngoài)
    # name="DIM" → nút "Ẩn DIM" lọc được (an_dim_text).
    for xh, xt in ((x0, x1), (x1, x0)):
        fig.add_annotation(x=xh, y=ya, ax=xt, ay=ya, xref="x", yref="y",
                           axref="x", ayref="y", showarrow=True, arrowhead=3,
                           arrowsize=_DIM_ARROW, arrowwidth=1, arrowcolor=color,
                           name="DIM")
    fig.add_annotation(x=(x0+x1)/2, y=ya+0.05, text=text, showarrow=False,
                       font=dict(size=_DIM_TXT, color=color), yanchor="bottom",
                       bgcolor="rgba(255,255,255,0.85)", name="DIM")

def _dim_v(fig, x, y0, y1, text, color=None, dx=0.4):
    """Đường kích thước ĐỨNG — nét DIM xanh nhạt + 2 mũi tên closed filled."""
    color = color or _C["dim"]
    xa = x + dx
    _rec_dim(fig, "v", y0, y1, xa, text)
    for yh, yt in ((y0, y1), (y1, y0)):
        fig.add_annotation(x=xa, y=yh, ax=xa, ay=yt, xref="x", yref="y",
                           axref="x", ayref="y", showarrow=True, arrowhead=3,
                           arrowsize=_DIM_ARROW, arrowwidth=1, arrowcolor=color,
                           name="DIM")
    fig.add_annotation(x=xa+0.08, y=(y0+y1)/2, text=text, showarrow=False,
                       font=dict(size=_DIM_TXT, color=color), xanchor="left",
                       textangle=-90, bgcolor="rgba(255,255,255,0.85)", name="DIM")


def an_dim_text(fig, an_dim=False, an_text=False):
    """Ẩn KÍCH THƯỚC (DIM) và/hoặc CHỮ ghi chú trên bản vẽ 2D theo tùy chọn.
    - an_dim : bỏ mọi annotation name="DIM" (đường dim + mũi tên + nhãn số).
    - an_text: bỏ mọi annotation chữ còn lại (nhãn Z=, tên cấu kiện, ghi chú…).
    Trả về fig (sửa tại chỗ) — gọi SAU khi hình đã dựng xong."""
    try:
        keep = []
        for a in (fig.layout.annotations or ()):
            is_dim = (str(getattr(a, "name", "") or "") == "DIM")
            if an_dim and is_dim:
                continue
            if an_text and not is_dim:
                continue
            keep.append(a)
        fig.layout.annotations = tuple(keep)
    except Exception:
        pass
    return fig

# ── Áp LAYER cho bản vẽ 2D (quy tắc thể hiện bản vẽ) ─────────────────────────
def _apply_layers_2d(fig):
    """Đường bao cấu kiện BTCT → layer 3 (xanh lá).
    Phần kết cấu trên (thân trụ/bản/xà mũ/dầm) đã xanh lá sẵn nhờ btong_dk/dam_dk.
    Hàm này quét thêm các polygon CÓ TÔ mà đường bao đang là màu bê tông sậm
    (be_dk: bệ cọc, mố, cọc tròn) → đổi sang xanh lá. KHÔNG đụng nét nước/đất/
    địa chất (màu khác) hay cọc vẽ dạng line (không tô) hay nét DIM (đã xanh nhạt)."""
    _be_dk = str(_C["be_dk"]).lower()
    for tr in fig.data:
        if not isinstance(tr, go.Scatter):
            continue
        if "toself" not in str(getattr(tr, "fill", "") or ""):
            continue
        try:
            if tr.line is not None and str(tr.line.color).lower() == _be_dk:
                tr.line.color = _LAYER3
        except Exception:
            pass
    return fig


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


# Nhóm cấu kiện ĐƯỢC vẽ đường bao (KHÔNG gồm mặt nước, tĩnh không, địa hình,
# đường đầu cầu, lớp phủ). Khớp theo legendgroup/name của trace.
_OUTLINE_GROUPS = ("Lan can", "Giải phân cách", "Mố", "Trụ", "Xà mũ",
                   "Thân", "Bệ", "Cọc", "Dầm", "Mặt cầu", "Bản")


def _add_box_outlines(fig, color="#1b2631", width=2.0, name="Đường bao cấu kiện",
                      groups=_OUTLINE_GROUPS):
    """Gộp ĐƯỜNG BAO của các cấu kiện (lan can, mố, trụ, cọc, dầm, bản mặt cầu)
    vào 1 trace Scatter3d → thấy rõ ranh giới trên 3D tổng.

    Dùng CẠNH ĐẶC TRƯNG (feature edge): cạnh biên (1 tam giác) hoặc cạnh gấp khúc
    (2 mặt lệch > ~25°). Nhờ vậy hộp, tấm quét (bản), khối extrude (lan can) đều
    ra viền sạch, KHÔNG vẽ đường chéo trên mặt phẳng. Mặt nước/tĩnh không/địa hình
    bị loại theo nhóm."""
    def _want(tr):
        g = str(getattr(tr, "legendgroup", "") or "") + "|" + \
            str(getattr(tr, "name", "") or "")
        return any(k in g for k in groups)

    xs, ys, zs = [], [], []
    for tr in list(fig.data):
        if getattr(tr, "type", "") != "mesh3d" or not _want(tr):
            continue
        vx, vy, vz = tr.x, tr.y, tr.z
        ii, jj, kk = tr.i, tr.j, tr.k
        if vx is None or ii is None:
            continue
        try:
            V = np.column_stack([np.asarray(vx, float),
                                 np.asarray(vy, float),
                                 np.asarray(vz, float)])
            tris = list(zip(ii, jj, kk))
        except Exception:
            continue
        edge_norms = {}
        for (a, b, c) in tris:
            a, b, c = int(a), int(b), int(c)
            nrm = np.cross(V[b] - V[a], V[c] - V[a])
            _ln = float(np.linalg.norm(nrm))
            if _ln < 1e-12:
                continue
            nrm = nrm / _ln
            for p, q in ((a, b), (b, c), (c, a)):
                key = (p, q) if p < q else (q, p)
                edge_norms.setdefault(key, []).append(nrm)
        for (p, q), ns in edge_norms.items():
            feat = (len(ns) == 1) or (abs(float(np.dot(ns[0], ns[1]))) < 0.90)
            if not feat:
                continue
            xs += [V[p, 0], V[q, 0], None]
            ys += [V[p, 1], V[q, 1], None]
            zs += [V[p, 2], V[q, 2], None]
    if not xs:
        return
    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=zs, mode="lines",
        line=dict(color=color, width=width),
        name=name, showlegend=True, legendgroup="_outline",
        hoverinfo="skip"))


def _hover3d(fig):
    """Hover mọi cấu kiện 3D → TÊN (legendgroup/name) + CAO ĐỘ z tại điểm di chuột."""
    for tr in fig.data:
        if getattr(tr, "type", "") not in ("mesh3d", "scatter3d"):
            continue
        lbl = str(getattr(tr, "legendgroup", "") or getattr(tr, "name", "") or "")
        if lbl == "_outline":
            try: tr.hoverinfo = "skip"
            except Exception: pass
            continue
        if not lbl:
            lbl = "Cấu kiện"
        try:
            tr.hovertemplate = f"<b>{lbl}</b><br>Cao độ: %{{z:.3f}} m<extra></extra>"
            tr.hoverinfo = None
        except Exception:
            pass


def _hover2d(fig):
    """Hover mọi cấu kiện trắc dọc 2D → TÊN + LÝ TRÌNH + CAO ĐỘ (y) tại điểm."""
    for tr in fig.data:
        if getattr(tr, "type", "") not in ("scatter", "scattergl"):
            continue
        lbl = str(getattr(tr, "name", "") or getattr(tr, "legendgroup", "") or "")
        if lbl == "_outline":
            continue
        head = f"<b>{lbl}</b><br>" if lbl else ""
        try:
            tr.hovertemplate = (head + "Lý trình %{x:.1f} m · Cao độ %{y:.3f} m"
                                "<extra></extra>")
            tr.hoverinfo = None
        except Exception:
            pass


def _approach_road_traces(xa, xb, bc, z_road, z_g, taluy=1.5, sl=True):
    """Đường đầu cầu 3D: nền đắp (lăng trụ hình thang, mái taluy) + mặt đường.
    xa = tại lưng mố, xb = đầu xa (cách xb−xa theo phương dọc)."""
    s = max(0.0, (z_road - z_g)) * taluy          # bề rộng mái taluy mỗi bên
    cs = [(-bc / 2, z_road), (bc / 2, z_road),     # đỉnh nền (mặt đường)
          (bc / 2 + s, z_g), (-bc / 2 - s, z_g)]   # chân taluy (mặt đất)
    X, Y, Z = [], [], []
    for x in (xa, xb):
        for (y, z) in cs:
            X.append(x); Y.append(y); Z.append(z)
    quads = [(0, 1, 5, 4), (3, 2, 6, 7), (0, 3, 7, 4),
             (1, 2, 6, 5), (0, 1, 2, 3), (4, 5, 6, 7)]
    I, J, K = [], [], []
    for a, b, c, e in quads:
        I += [a, a]; J += [b, c]; K += [c, e]
    embankment = go.Mesh3d(
        x=X, y=Y, z=Z, i=I, j=J, k=K, color="#c9a86b", opacity=0.55,
        flatshading=True, name="Nền đắp đầu cầu" if sl else "", showlegend=sl,
        lighting=dict(ambient=0.65, diffuse=0.85, specular=0.15),
        hovertemplate="Nền đắp đầu cầu<extra></extra>")
    road = _box3d(min(xa, xb), -bc / 2, z_road - 0.25, max(xa, xb), bc / 2, z_road,
                  color="#34495e", opacity=0.92,
                  name="Mặt đường đầu cầu" if sl else "", sl=sl)
    return [embankment, road]


# ===========================================================================
# LAN CAN / GIẢI PHÂN CÁCH — kéo (extrude) MCN khai báo CHẠY DỌC TOÀN CẦU
# ===========================================================================
def _sweep_profile_mesh(profile_yz, y_off, mirror, x_start, x_end, z_base,
                        color, name="", sl=False, opacity=0.95):
    """Kéo 1 mặt cắt ngang kín (list [y_m, z_m], gốc z=0 tại đáy) dọc trục x
    từ x_start→x_end thành 1 khối Mesh3d (chỉ dựng mặt bao quanh — đủ kín nhìn
    như khối đặc; 2 đầu giấu trong mố)."""
    pts = [(float(p[0]), float(p[1])) for p in (profile_yz or []) if len(p) >= 2]
    if len(pts) < 3:
        return None
    sgn = -1.0 if mirror else 1.0
    vx, vy, vz = [], [], []
    for (yy, zz) in pts:                       # 2 đỉnh / điểm: đầu x_start & x_end
        y = sgn * yy + y_off
        z = z_base + zz
        vx += [x_start, x_end]; vy += [y, y]; vz += [z, z]
    n = len(pts)
    ii, jj, kk = [], [], []
    for i in range(n):                          # nối vòng kín (i → i+1 mod n)
        a0 = 2 * i;            a1 = 2 * i + 1
        b0 = 2 * ((i + 1) % n); b1 = 2 * ((i + 1) % n) + 1
        ii += [a0, a0];  jj += [b0, b1];  kk += [b1, a1]
    return go.Mesh3d(
        x=vx, y=vy, z=vz, i=ii, j=jj, k=kk,
        color=color, opacity=opacity, name=name, showlegend=sl and bool(name),
        flatshading=True, lighting=dict(ambient=0.65, diffuse=0.85, specular=0.2),
        hovertemplate=f"<b>{name}</b><extra></extra>" if name else None,
    )


def _sweep_profile_curve_mesh(profile_yz, y_off, mirror, vn_func, s0, s1,
                              z_base, color, name="", sl=False, step=5.0,
                              opacity=0.95, dz_fn=None):
    """Như _sweep_profile_mesh nhưng BÁM ĐƯỜNG CONG tim tuyến (VN-2000): tại mỗi
    lý trình s, mỗi điểm MCN đặt theo offset ngang qua vn_func(s, offset).
    dz_fn(s): độ lệch cao độ theo lý trình (bám TRẮC DỌC / đường đỏ)."""
    pts = [(float(p[0]), float(p[1])) for p in (profile_yz or []) if len(p) >= 2]
    n = len(pts)
    if n < 3:
        return None
    sgn = -1.0 if mirror else 1.0
    import numpy as _np
    m  = max(2, int(abs(s1 - s0) / max(step, 0.5)))
    ss = _np.linspace(s0, s1, m + 1)
    vx, vy, vz = [], [], []
    for s in ss:
        _ds = dz_fn(s) if dz_fn else 0.0
        for (yy, zz) in pts:
            xx, yc = vn_func(s, sgn * yy + y_off)
            vx.append(xx); vy.append(yc); vz.append(z_base + zz + _ds)
    ii, jj, kk = [], [], []
    for i in range(m):
        for j in range(n):
            a = i * n + j;            b = i * n + (j + 1) % n
            c = (i + 1) * n + (j + 1) % n; dd = (i + 1) * n + j
            ii += [a, a]; jj += [b, c]; kk += [c, dd]
    return go.Mesh3d(
        x=vx, y=vy, z=vz, i=ii, j=jj, k=kk,
        color=color, opacity=opacity, name=name, showlegend=sl and bool(name),
        flatshading=True, lighting=dict(ambient=0.65, diffuse=0.85, specular=0.2),
        hovertemplate=f"<b>{name}</b><extra></extra>" if name else None,
    )


def _median_required(d):
    """Tiêu chuẩn CÓ yêu cầu dải phân cách giữa? True khi w_dpc>0 trong cấu hình
    mặt cắt ngang đường (mcn_oto_override) — do hệ thống tra theo TCVN."""
    mcn = (d or {}).get("mcn_oto_override") or {}
    try:
        return float(mcn.get("w_dpc", 0) or 0) > 0
    except Exception:
        return False


def _resolve_railings(d):
    """{'lan_can':rec, 'giai_phan_cach':rec|None}: ưu tiên lựa chọn d['railings'];
    thiếu → lấy MẶC ĐỊNH từ thư viện. Giải phân cách CHỈ thêm khi tiêu chuẩn yêu
    cầu (w_dpc>0) hoặc người dùng đã chọn sẵn."""
    rails = dict((d or {}).get("railings") or {}) if isinstance((d or {}).get("railings"), dict) else {}
    need_med = _median_required(d)
    if rails.get("lan_can") and (rails.get("giai_phan_cach") or not need_med):
        return rails
    try:
        import utils.component_library as _CL
        lib = _CL.load_railings()
    except Exception:
        lib = []
    if not rails.get("lan_can"):
        lc = next((r for r in lib if r.get("loai") == "lan_can"), None)
        if lc:
            rails["lan_can"] = lc
    if not rails.get("giai_phan_cach") and need_med:
        gpc = next((r for r in lib if r.get("loai") == "giai_phan_cach"), None)
        if gpc:
            rails["giai_phan_cach"] = gpc
    return rails


def _profile_outer_at_z(prof, zc):
    """Mép NGOÀI (y lớn nhất) của biên dạng tại cao độ zc — nội suy giao điểm."""
    ys = []
    n = len(prof)
    for i in range(n):
        a = prof[i]; b = prof[(i + 1) % n]
        if a[1] != b[1] and (a[1] - zc) * (b[1] - zc) <= 0:
            t = (zc - a[1]) / (b[1] - a[1])
            ys.append(a[0] + t * (b[0] - a[0]))
    return max(ys) if ys else max((p[0] for p in prof), default=0.0)


def _rail_geom(prof, bc):
    """Đặt lan can theo CHÂN THẬT (mép trong cùng = phía đường), MOVE CẢ KHỐI:
      • base_z: cao độ chân (điểm y NHỎ NHẤT) → đặt ngang ĐỈNH BẢN; cả khối dịch
        xuống nguyên khối (giữ hình), phần dưới base_z (mũi) rủ xuống mép bản.
      • y_edge: offset để mép NGOÀI tại cao độ base_z trùng mép cầu ±bc/2.
      • y_in  : mép TRONG (phía đường) — vị trí lớp phủ ngừng.
    prof = [[y_m, z_m]]."""
    if not prof:
        return bc / 2.0, bc / 2.0, 0.0
    y_min = min(p[0] for p in prof)
    inner = [p for p in prof if abs(p[0] - y_min) < 0.05] or prof
    base_z = min(p[1] for p in inner)               # cao độ chân thật
    y_out = _profile_outer_at_z(prof, base_z)        # mép ngoài tại cao độ chân
    return bc / 2.0 - y_out, bc / 2.0 - (y_out - y_min), base_z


def _rail_place(prof, bc):
    """Trả (prof, y_edge, base_z): KÉO CẢ KHỐI (giữ nguyên hình) ra ngoài sao cho
    cạnh đứng PHÍA TRONG của phần THÒ XUỐNG (z<base_z) trùng MÉP BẢN ±bc/2 — phần
    thò xuống ốp đúng mép bản, cả khối dịch theo (không kéo riêng cạnh nào)."""
    y_edge, _, base_z = _rail_geom(prof, bc)
    drape_inner = min((p[0] for p in prof if p[1] < base_z - 1e-6), default=None)
    if drape_inner is None:
        return prof, y_edge, base_z
    return prof, bc / 2.0 - drape_inner, base_z       # neo cạnh trong drape tại mép


def _railing_inner_y(d, bc):
    """Mép TRONG lan can (m, +) + NỬA bề rộng dải phân cách (m) để cắt lớp phủ.
    Lớp phủ ngừng tại mặt trong chân (phía đường) SAU khi kéo cả khối ra mép."""
    rails = _resolve_railings(d)
    lc = rails.get("lan_can"); gpc = rails.get("giai_phan_cach")
    prof = [[p[0] / 1000.0, p[1] / 1000.0] for p in ((lc or {}).get("outer") or [])]
    if prof:
        _, y_edge, _ = _rail_place(prof, bc)
        y_in = min(p[0] for p in prof) + y_edge       # mặt trong chân sau khi neo
    else:
        y_in = bc / 2.0
    w_gpc = float((gpc or {}).get("rong_mm", 0) or 0) / 1000.0 if gpc else 0.0
    return y_in, w_gpc / 2.0


def _abut_long_depth_m(abut):
    """Chiều dài DỌC (theo lý trình) của mố/TƯỜNG CÁNH (m) — để kéo dài lan can ra
    hết tường cánh mố. Lấy từ khẩu độ dọc mặt cắt thân mố; fallback 3.5m."""
    if not abut:
        return 3.5
    try:
        PB = _get_PB()
        p = PB.migrate_abutment(abut)
        us = [u for l in PB.abut_body_layers(p["parts"]["than"])
              if (l.get("section") or {}).get("outer")
              for (u, _w) in l["section"]["outer"]]
        if us:
            return max((max(us) - min(us)) / 1000.0, 1.0)
    except Exception:
        pass
    return 3.5


def _railing_curve_traces(d, vn_func, s0, s1, bc, z_base, dz_fn=None):
    """Lan can (2 mép) + giải phân cách (tim) BÁM đường cong tim tuyến VN-2000.
    dz_fn(s): độ lệch cao độ theo lý trình → lan can BÁM ĐƯỜNG ĐỎ (trắc dọc)."""
    out = []
    rails = _resolve_railings(d)
    if not isinstance(rails, dict):
        return out

    def _prof_m(rec):
        return [[p[0] / 1000.0, p[1] / 1000.0] for p in (rec.get("outer") or [])]

    lc = rails.get("lan_can")
    if lc and lc.get("outer"):
        prof, y_edge, base_z = _rail_place(_prof_m(lc), bc)
        # MOVE CẢ KHỐI: chân ngồi đỉnh bản; phần thò xuống dịch ra mép bản.
        for _side, _mir, _sl in ((1.0, False, True), (-1.0, True, False)):
            _m = _sweep_profile_curve_mesh(
                prof, y_off=_side * y_edge, mirror=_mir, vn_func=vn_func,
                s0=s0, s1=s1, z_base=z_base - base_z, color="#bfc4c9",
                name=f"Lan can ({lc.get('ten','')})" if _sl else "", sl=_sl,
                dz_fn=dz_fn)
            if _m is not None:
                out.append(_m)
    gpc = rails.get("giai_phan_cach")
    if gpc and gpc.get("outer"):
        _m = _sweep_profile_curve_mesh(
            _prof_m(gpc), y_off=0.0, mirror=False, vn_func=vn_func,
            s0=s0, s1=s1, z_base=z_base, color="#aeb6bd",
            name=f"Giải phân cách ({gpc.get('ten','')})", sl=True, dz_fn=dz_fn)
        if _m is not None:
            out.append(_m)
    return out


def _railing_traces_3d(d, x_start, x_end, bc, z_deck):
    """Trả về list Mesh3d lan can (2 mép cầu) + giải phân cách (tim) đã chọn
    cho phương án — d['railings'] (thiếu → mặc định thư viện, dải PC theo tiêu chuẩn)."""
    out = []
    rails = _resolve_railings(d)
    if not isinstance(rails, dict):
        return out

    def _prof_m(rec):
        return [[p[0] / 1000.0, p[1] / 1000.0] for p in (rec.get("outer") or [])]

    # ── Lan can: đặt ở 2 mép cầu, MẶT NGOÀI tại ±bc/2 ──────────────────────
    lc = rails.get("lan_can")
    if lc and lc.get("outer"):
        prof, y_edge, base_z = _rail_place(_prof_m(lc), bc)  # move khối + drape ra mép
        for _side, _mir, _sl in ((1.0, False, True), (-1.0, True, False)):
            _m = _sweep_profile_mesh(
                prof, y_off=_side * y_edge, mirror=_mir,
                x_start=x_start, x_end=x_end, z_base=z_deck - base_z, color="#bfc4c9",
                name=f"Lan can ({lc.get('ten','')})" if _sl else "", sl=_sl)
            if _m is not None:
                out.append(_m)

    # ── Giải phân cách: đặt ở tim cầu (y=0) ──────────────────────────────
    gpc = rails.get("giai_phan_cach")
    if gpc and gpc.get("outer"):
        _m = _sweep_profile_mesh(
            _prof_m(gpc), y_off=0.0, mirror=False,
            x_start=x_start, x_end=x_end, z_base=z_deck, color="#aeb6bd",
            name=f"Giải phân cách ({gpc.get('ten','')})", sl=True)
        if _m is not None:
            out.append(_m)
    return out


# ===========================================================================
# SƠ ĐỒ CỌC khai báo từ DXF (utils/pile_plan.py) — vẽ theo tọa độ thật + cọc xiên
# ===========================================================================
def _layout_piles(d, pos_key):
    """Trả về list cọc đã khai cho 1 vị trí (mố/trụ) hoặc None nếu chưa khai."""
    if PP is None or not isinstance(d, dict):
        return None
    try:
        lay = PP.get_layout(d, pos_key)
        return lay["piles"] if lay else None
    except Exception:
        return None


def _pile_w(D_m):
    """Bề rộng nét vẽ cọc 2D theo đường kính (m) — đồng bộ cách cũ."""
    return max(2, int(float(D_m) * 12))


def _draw_piles_elevation(fig, piles, x_center, z_top, color, legend_name=None):
    """
    Vẽ cọc lên TRẮC DỌC (trục ngang figure = DỌC cầu).
      đỉnh cọc tại x_center + y(dọc); đáy lệch thêm ix*L (cọc xiên trong mp dọc).
    """
    if not piles:
        return
    tip_x, tip_z = [], []
    for j, p in enumerate(piles):
        L = float(p["L"])
        xt = x_center + float(p["y"])
        xb = xt + float(p.get("ix", 0.0)) * L
        zb = z_top - L
        fig.add_trace(go.Scatter(
            x=[xt, xb], y=[z_top, zb], mode="lines",
            line=dict(color=color, width=_pile_w(p["D"])),
            name=(legend_name if (legend_name and j == 0) else ""),
            showlegend=(bool(legend_name) and j == 0),
            hoverinfo="skip"))
        tip_x.append(xb); tip_z.append(zb)
    fig.add_trace(go.Scatter(
        x=tip_x, y=tip_z, mode="markers",
        marker=dict(symbol="triangle-down", size=5, color=color),
        showlegend=False, hoverinfo="skip"))


def _draw_piles_section(fig, piles, x_center, z_top, color, legend_name=None):
    """
    Vẽ cọc lên MẶT CẮT NGANG (trục ngang figure = NGANG cầu).
      đỉnh cọc tại x_center + x(ngang); đáy lệch thêm iy*L (cọc xiên trong mp ngang).
    """
    if not piles:
        return
    tip_x, tip_z = [], []
    for j, p in enumerate(piles):
        L = float(p["L"])
        xt = x_center + float(p["x"])
        xb = xt + float(p.get("iy", 0.0)) * L
        zb = z_top - L
        fig.add_trace(go.Scatter(
            x=[xt, xb], y=[z_top, zb], mode="lines",
            line=dict(color=color, width=_pile_w(p["D"])),
            name=(legend_name if (legend_name and j == 0) else ""),
            showlegend=(bool(legend_name) and j == 0),
            hoverinfo="skip"))
        tip_x.append(xb); tip_z.append(zb)
    fig.add_trace(go.Scatter(
        x=tip_x, y=tip_z, mode="markers",
        marker=dict(symbol="triangle-down", size=5, color=color),
        showlegend=False, hoverinfo="skip"))


def _pile_traces_3d(piles, x_center, y_center, z_top, color, legend_name=None):
    """
    Trả về list Scatter3d các cọc trong mô hình 3D.
    Trục: X = DỌC cầu (chainage), Y = NGANG cầu, Z = cao độ.
      đỉnh = (x_center + y_dọc, y_center + x_ngang, z_top)
      đáy  = đỉnh + (ix*L theo X, iy*L theo Y, -L theo Z)
    """
    out = []
    for j, p in enumerate(piles or []):
        L = float(p["L"])
        x0 = x_center + float(p["y"])
        y0 = y_center + float(p["x"])
        x1 = x0 + float(p.get("ix", 0.0)) * L
        y1 = y0 + float(p.get("iy", 0.0)) * L
        out.append(go.Scatter3d(
            x=[x0, x1], y=[y0, y1], z=[z_top, z_top - L],
            mode="lines",
            line=dict(color=color, width=max(3, int(float(p["D"]) * 6))),
            name=(legend_name if (legend_name and j == 0) else ""),
            showlegend=(bool(legend_name) and j == 0),
            hoverinfo="skip"))
    return out


def _draw_piles_3d(fig, piles, x_center, y_center, z_top, color, legend_name=None):
    """Thêm cọc 3D trực tiếp vào fig (bọc _pile_traces_3d)."""
    for t in _pile_traces_3d(piles, x_center, y_center, z_top, color, legend_name):
        fig.add_trace(t)


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


# Danh sách nhịp định hình catalog (m) — đồng bộ STD_LENGTHS của 06-AI_KetCauNhip.py
STD_LENGTHS = [12, 15, 18, 21, 24, 25, 27, 30, 33, 38.2, 40]


def _snap_up_std(L_min):
    """Chiều dài nhịp định hình catalog NHỎ NHẤT ≥ L_min (m).
    Nếu L_min vượt danh mục thì làm tròn lên bội số 5m."""
    ge = [l for l in STD_LENGTHS if l >= L_min - 1e-6]
    if ge:
        return float(min(ge))
    return float(int(np.ceil(L_min / 5.0)) * 5)


def _calc_span_layout(x0, x_end, x_tim, B_tk, L_nhip=None):
    """
    Bố trí nhịp ĐỀU — tất cả nhịp = một chiều dài định hình catalog L_std.

    Nguyên tắc (theo yêu cầu thiết kế):
      1. Nhịp chính (nhịp chứa tim tĩnh không) căng GIỮA x_tim → hai trụ kề
         nhịp chính cách biên tĩnh không ≥ _PIER_SAFETY ⇒ KHÔNG vi phạm tĩnh không.
      2. Mọi nhịp (kể cả nhịp dẫn) đều bằng nhau và bằng chiều dài định hình
         catalog L_std — không còn mỗi nhịp một chiều dài lẻ khác nhau.

    L_nhip : chiều dài nhịp định hình do module 06 chọn (kcn['chieu_dai']).
             Nếu thiếu hoặc < điều kiện tĩnh không (B_tk + 2×_PIER_SAFETY) thì
             tự nâng lên định hình nhỏ nhất thỏa điều kiện này.

    Returns
    -------
    (supports, L_std)
        supports : list[float] — tọa độ MỐ–TRỤ–MỐ tăng dần (gồm cả 2 mố).
        L_std    : float       — chiều dài mỗi nhịp (m).
    """
    L_clear = B_tk + 2.0 * _PIER_SAFETY
    if L_nhip and float(L_nhip) + 1e-6 >= L_clear:
        L_std = float(L_nhip)
    else:
        L_std = _snap_up_std(L_clear)

    # Nhịp chính căng giữa tim tĩnh không
    main_L = x_tim - L_std / 2.0
    main_R = x_tim + L_std / 2.0

    # Số nhịp dẫn mỗi phía = LÀM TRÒN (gần nhất) quãng từ nhịp chính tới điểm ngắt
    # cầu (vị trí đắp ≈ 6m). Dùng round (không phải ceil) để mố chỉ DỜI 1 CHÚT về
    # đúng bội số chiều dài nhịp — không lố hẳn ra thêm gần cả một nhịp.
    n_left  = max(0, int(round((main_L - x0)   / L_std)))
    n_right = max(0, int(round((x_end - main_R) / L_std)))

    left  = [main_L - i * L_std for i in range(n_left, 0, -1)]
    right = [main_R + i * L_std for i in range(1, n_right + 1)]
    supports = left + [main_L, main_R] + right
    return supports, L_std


# Public alias
calc_span_layout = _calc_span_layout


def resolve_supports(d, x0, x_end, x_tim, B_tk, L_nhip=None):
    """Bố trí mố–trụ theo cấu hình ``d['span_layout']``.

    mode 'two_tier' : nhịp CHÍNH (căng giữa tĩnh không) dài L_main, các nhịp
                      DẪN dài L_dan rải đều hai phía. Nếu thiếu L_main hoặc
                      L_main < điều kiện tĩnh không → tự nâng (snap-up).
    mode khác/thiếu : trả về bố trí ĐỀU như ``_calc_span_layout`` (giữ nguyên
                      hành vi cũ — tương thích ngược).

    Returns (supports, L_dan) — đồng bộ chữ ký (supports, L_std) cũ.
    """
    sl  = (d or {}).get("span_layout") or {}
    kcn = (d or {}).get("kcn_result") or (d or {}).get("ai_result", {}) or {}
    if L_nhip is None:
        L_nhip = float(kcn.get("chieu_dai", 33.0) or 33.0)

    # Khe ụ giữa xà mũ (Super-T): KHOẢNG CÁCH GỐI = chiều dài dầm + bề rộng ụ giữa
    # (2 đầu dầm kê 2 vai kê thấp, ụ giữa cao nằm GIỮA 2 đầu dầm). 0 nếu xà mũ 1
    # đoạn (dầm liền) → giữ nguyên hành vi cũ.
    _cap_gap = float((d or {}).get("cap_gap_m", 0.0) or 0.0)

    # ── DẦM SPT (~38.2m): GIỮ 1 loại dầm, NỚI RỘNG ụ giữa xà mũ khi nhịp vượt
    # tĩnh không (như bản vẽ KM4/KM7: 45→42.5→40→39.1). spacing = 38.2 + 2×0.1 +
    # ụ giữa; nhịp thường 40m, nhịp vượt nới ụ giữa. Ghi d["_pier_cap_widen"] để
    # xà mũ trụ tương ứng vẽ RỘNG ra (trắc dọc + 3D + MCN).
    _kcn = (d or {}).get("kcn_result") or (d or {}).get("ai_result", {}) or {}
    _loai = str(_kcn.get("loai_dam", "") or "").lower()
    _Lb = float(_kcn.get("chieu_dai", 0) or 0)
    # KHOẢNG TRUNG (module 06): giai_phap 'Super-T mở rộng xà mũ' → cùng kỹ
    # thuật nới ụ giữa cho cả các cỡ Super-T dài 40/42/45m (kèm mo_rong_xa_mu).
    _gp_widen = (str(_kcn.get("giai_phap") or "") == "Super-T mở rộng xà mũ")
    if ("super" in _loai or "spt" in _loai) and (
            37.5 <= _Lb <= 39.0 or (_gp_widen and _Lb > 0)):
        try:
            _W0 = _get_PB().cap_mid_width_m(d.get("_pier_model")) or 1.6
        except Exception:
            _W0 = 1.6
        _clr = [(x_tim, float(B_tk))]
        for _c in (d.get("extra_clearances") or []):
            try:
                _b = float(_c.get("B", 0) or 0)
                if _b > 0:
                    _clr.append((float(_c["x"]), _b))
            except (TypeError, ValueError, KeyError):
                pass
        _sup, _widen = _spt_widen_layout(x0, x_end, x_tim, _clr, _W0, L_beam=_Lb)
        if isinstance(d, dict):
            d["_pier_cap_widen"] = _widen      # {round(x,3): bề rộng ụ giữa (m)}
            d["_pier_cap_W0"] = _W0
        return _sup, _Lb

    # ── Có TĨNH KHÔNG PHỤ + phương án bật quy tắc né (PA1 'fewest' / PA2
    # 'straddle') → CHIA LẠI nhịp từ tim tĩnh không chính ra 2 mố, trộn chiều dài
    # dầm catalog để KHÔNG trụ nào phạm tĩnh không (thay vì chỉ bỏ trụ). PA3/khác
    # hoặc không có tĩnh không phụ → giữ luồng cũ bên dưới.
    _clr_mode = (d or {}).get("_clearance_mode")
    if _clr_mode in ("fewest", "straddle") and ((d or {}).get("extra_clearances")):
        _L_base = float(sl.get("L_dan") or sl.get("L_main") or L_nhip)
        return _clearance_layout(x0, x_end, x_tim, B_tk, _L_base,
                                 d.get("extra_clearances"), _clr_mode)

    if sl.get("mode") != "two_tier":
        # Bố trí ĐỀU. Ưu tiên chiều dài người dùng đặt/áp dầm thư viện
        # (span_layout['L_dan']/['L_main']); nếu chưa có thì dùng L_nhip mặc định.
        L_user = sl.get("L_dan") or sl.get("L_main")
        if L_user and float(L_user) > 0:
            L_nhip = float(L_user)
        _sp, _Ls = _calc_span_layout(x0, x_end, x_tim, B_tk, L_nhip + _cap_gap)
        return _avoid_extra_clearances(_sp, d), _Ls

    L_clear = B_tk + 2.0 * _PIER_SAFETY
    L_dan   = float(sl.get("L_dan") or L_nhip)
    if L_dan <= 0:
        L_dan = L_nhip
    L_main  = sl.get("L_main")
    L_main  = float(L_main) if L_main else _snap_up_std(L_clear)
    if L_main + 1e-6 < L_clear:               # không đủ tĩnh không → tự nâng
        L_main = _snap_up_std(L_clear)
    L_dan  += _cap_gap        # khoảng cách gối = chiều dài dầm + ụ giữa xà mũ
    L_main += _cap_gap

    main_L = x_tim - L_main / 2.0
    main_R = x_tim + L_main / 2.0
    # LÀM TRÒN (gần nhất) số nhịp dẫn → mố dời 1 chút về bội số chiều dài nhịp dẫn.
    n_left  = max(0, int(round((main_L - x0)   / L_dan)))
    n_right = max(0, int(round((x_end - main_R) / L_dan)))
    left  = [main_L - i * L_dan for i in range(n_left, 0, -1)]
    right = [main_R + i * L_dan for i in range(1, n_right + 1)]
    supports = left + [main_L, main_R] + right
    return _avoid_extra_clearances(supports, d), L_dan


def extra_clearance_intervals(d):
    """Vùng CẤM đặt trụ [a,b] (lý trình m) của các TĨNH KHÔNG PHỤ khai báo trong
    hộp thoại thủy văn. Mỗi tĩnh không: {x: lý trình, B: bề rộng, H, z}. Vùng cấm
    = [x − B/2 − an toàn, x + B/2 + an toàn]. [] nếu không khai báo."""
    out = []
    for c in ((d or {}).get("extra_clearances") or []):
        try:
            x = float(c.get("x"))
            B = float(c.get("B", 0) or 0)
        except (TypeError, ValueError):
            continue
        half = B / 2.0 + _PIER_SAFETY
        out.append((x - half, x + half))
    return out


def _avoid_extra_clearances(supports, d):
    """Bỏ các TRỤ rơi vào vùng cấm của tĩnh không phụ → trụ KHÔNG phạm tĩnh không
    (nhịp bắc qua tĩnh không tự nối dài = hệ thống chọn nhịp lớn hơn). Luôn giữ 2
    MỐ đầu–cuối. No-op khi chưa khai báo tĩnh không phụ (không đổi hành vi cũ)."""
    forb = extra_clearance_intervals(d)
    if not forb or len(supports) < 3:
        return supports
    x0, x_end = supports[0], supports[-1]
    kept = [p for p in supports[1:-1]
            if not any(a - 1e-6 <= p <= b + 1e-6 for (a, b) in forb)]
    return [x0] + kept + [x_end]


def _in_any_zone(p, zones):
    return any(a - 1e-6 <= p <= b + 1e-6 for (a, b, *_ ) in zones)


def _snap_ge(v):
    """Chiều dài catalog nhỏ nhất ≥ v (m)."""
    return next((L for L in sorted(STD_LENGTHS) if L + 1e-6 >= v), _snap_up_std(v))


def _place_dir(P0, sgn, target, zones, L0, mode, Lc_common):
    """Rải trụ từ P0 theo hướng sgn (±1) tới target — ƯU TIÊN CHIỀU DÀI CHUNG L0
    (đồng bộ dầm, ít loại dầm). Chỉ nơi trụ L0 rơi vào vùng cấm mới đổi = nhịp
    BẮC QUA khoang: PA1 dùng CHUNG Lc_common (theo khoang rộng nhất); PA2 dùng
    nhịp vừa đủ cho khoang đó. Trụ trước khoang có thể lệch để nhịp bắc qua khớp.
    Nhịp biên = L0 (mố chạy tới lưới, không sinh nhịp lẻ). zones=(a,b,need)."""
    piers = []
    P = P0
    guard = 0
    while sgn * (target - P) > 1e-6 and guard < 500:
        guard += 1
        Pn = P + sgn * L0
        zb = next(((a, b, nd) for (a, b, nd) in zones
                   if a - 1e-6 <= Pn <= b + 1e-6), None)
        if zb is None:                       # nhịp L0 bình thường (đồng bộ)
            P = Pn; piers.append(P)
            continue
        a, b, nd = zb                        # trụ L0 sẽ phạm khoang → bắc qua
        far = (b if sgn > 0 else a) + sgn * 0.01   # đáp QUA hẳn mép xa khoang
        Lc = Lc_common if mode == "fewest" else max(L0, _snap_ge(nd))
        pp = far - sgn * Lc                        # trụ trước → nhịp bắc qua = Lc
        approach = sgn * (pp - P)
        if approach >= 12.0 - 1e-6 and not _in_any_zone(pp, zones):
            # đủ chỗ đặt TRỤ TRƯỚC (nhịp dẫn ≥ 12m) → nhịp bắc qua = Lc (đồng bộ)
            P = pp; piers.append(P)
            P = far; piers.append(P)
        else:
            # P đã sát khoang → BẮC THẲNG từ P (tránh nhịp dẫn lẻ quá ngắn)
            L = _snap_ge(sgn * (far - P))
            P = P + sgn * L; piers.append(P)
    return piers


def _clearance_layout(x0, x_end, x_tim, B_tk, L_base, extras, mode):
    """Bố trí MỐ–TRỤ né MỌI tĩnh không (chính + phụ), rải TỪ TIM TĨNH KHÔNG CHÍNH
    ra 2 mố. ƯU TIÊN dùng CHUNG 1 chiều dài dầm L0 = L_base (đồng bộ, ít loại
    dầm); chỉ nhịp bắc qua khoang mới khác. Trả (supports, L0)."""
    L0 = float(L_base) if L_base and float(L_base) > 0 else 33.0
    clearances = [(float(x_tim), float(B_tk))]
    for c in (extras or []):
        try:
            _b = float(c.get("B", 0) or 0)
            if _b > 0:
                clearances.append((float(c["x"]), _b))
        except (TypeError, ValueError, KeyError):
            pass
    needs = [b + 2.0 * _PIER_SAFETY for (_x, b) in clearances]
    zones = [(x - b / 2.0 - _PIER_SAFETY, x + b / 2.0 + _PIER_SAFETY,
              b + 2.0 * _PIER_SAFETY) for (x, b) in clearances if b and b > 0]
    # PA1: 1 loại nhịp bắc qua CHUNG (đủ cho khoang RỘNG NHẤT); PA2: theo từng khoang.
    Lc_common = max(L0, _snap_ge(max(needs)))
    # Nhịp CHÍNH căng giữa tim TK chính = L0 nếu đủ dài bắc qua, không thì Lc.
    need_main = float(B_tk) + 2.0 * _PIER_SAFETY
    L_main = L0 if L0 + 1e-6 >= need_main else (
        Lc_common if mode == "fewest" else max(L0, _snap_ge(need_main)))
    P_L = x_tim - L_main / 2.0
    P_R = x_tim + L_main / 2.0
    left  = _place_dir(P_L, -1.0, x0,    zones, L0, mode, Lc_common)
    right = _place_dir(P_R, +1.0, x_end, zones, L0, mode, Lc_common)
    return sorted(left + [P_L, P_R] + right), L0


def _clearance_zones(clearances):
    """[(a,b)] vùng cấm đặt trụ từ list (x, B): [x−B/2−an toàn, x+B/2+an toàn]."""
    return [(x - b / 2.0 - _PIER_SAFETY, x + b / 2.0 + _PIER_SAFETY)
            for (x, b) in clearances if b and b > 0]


def _spt_widen_layout(x0, x_end, x_tim, clearances, W0, L_beam=38.2, gap=0.1):
    """Bố trí trụ cho dầm SPT (VD 38.2m) GIỮ 1 loại dầm, NỚI RỘNG ụ giữa xà mũ tại
    nhịp vượt tĩnh không (thay vì đổi loại dầm). Trả (supports, widen) với
    widen[round(x,3)] = bề rộng ụ giữa (m) của trụ.

    spacing = L_beam + 2·gap + (W_trái + W_phải)/2. Nhịp thường W=W0. Nhịp vượt: 2
    trụ kẹp W = need−(L_beam+2gap) → nhịp kế TỰ thu dần (dùng chung trụ nới). Nhịp
    biên (mố, đầu trơn) = L_beam + 2gap + W/2."""
    two = 2.0 * gap
    need_main = float(clearances[0][1]) + 2.0 * _PIER_SAFETY   # B_tk + 4
    W_main = max(W0, need_main - L_beam - two)
    span_main = L_beam + two + W_main
    P_L = x_tim - span_main / 2.0
    P_R = x_tim + span_main / 2.0
    widen = {round(P_L, 3): W_main, round(P_R, 3): W_main}
    zones = [(cx - B / 2.0 - _PIER_SAFETY, cx + B / 2.0 + _PIER_SAFETY,
              B + 2.0 * _PIER_SAFETY) for (cx, B) in clearances[1:] if B > 0]

    def _side(P0, Wp, sgn, target):
        piers = []; cur, Wc = P0, Wp; zs = list(zones); guard = 0
        while guard < 300:
            guard += 1
            end_span = L_beam + two + Wc / 2.0            # trụ → mố (mố đầu trơn)
            if sgn * (target - cur) <= end_span + 1e-6:   # sát mố → đặt MỐ, dừng
                piers.append(cur + sgn * end_span)
                break
            sp = L_beam + two + (Wc + W0) / 2.0           # → trụ thường
            nxt = cur + sgn * sp; Wn = W0
            zc = next(((a, b, nd) for (a, b, nd) in zs
                       if min(cur, nxt) < b - 1e-6 and max(cur, nxt) > a + 1e-6), None)
            if zc:                                         # nhịp cắt tĩnh không phụ
                _a, _b, nd = zc
                Wn = max(W0, 2.0 * (nd - L_beam - two) - Wc)
                nxt = cur + sgn * (L_beam + two + (Wc + Wn) / 2.0)
                zs = [z for z in zs if z != zc]
            piers.append(nxt); widen[round(nxt, 3)] = Wn
            cur, Wc = nxt, Wn
        return piers

    left = _side(P_L, W_main, -1.0, x0)
    right = _side(P_R, W_main, +1.0, x_end)
    return sorted(left + [P_L, P_R] + right), widen


def main_span_index(supports, x_tim):
    """Chỉ số nhịp CHÍNH (nhịp chứa tim tĩnh không). -1 nếu rỗng."""
    spans = list(zip(supports[:-1], supports[1:]))
    for i, (a, b) in enumerate(spans):
        if a - 1e-6 <= x_tim <= b + 1e-6:
            return i
    return (len(spans) // 2) if spans else -1


def _add_elevation_table(fig, d, loc="tl"):
    """Bảng CAO ĐỘ THIẾT KẾ tham chiếu (neo theo khung giấy) cho bản vẽ."""
    def _g(k):
        v = (d or {}).get(k)
        try:
            return float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None
    rows = []
    for lbl, key in (("MNCN", "MNCN"), ("MNTT", "MNTT"), ("MNTN", "MNTN")):
        v = _g(key)
        if v is not None:
            rows.append(f"{lbl} = {v:6.2f}")
    mc, dd = _g("cao_mat_cau"), _g("cao_day_dam")
    if mc is not None:
        rows.append(f"Mặt cầu = {mc:6.2f}")
    if dd is not None:
        rows.append(f"Đáy dầm = {dd:6.2f}")
    if not rows:
        return
    txt = "<b>CAO ĐỘ (m)</b><br>" + "<br>".join(rows)
    x, xa = (0.005, "left") if loc.endswith("l") else (0.995, "right")
    y, ya = (0.99, "top") if loc.startswith("t") else (0.02, "bottom")
    fig.add_annotation(
        xref="paper", yref="paper", x=x, y=y, xanchor=xa, yanchor=ya,
        text=txt, showarrow=False, align="left",
        font=dict(size=8, color="#2c3e50", family="Courier New, monospace"),
        bgcolor="rgba(255,255,255,0.92)", bordercolor="#7f8c8d",
        borderwidth=1, borderpad=4)


_MAT_NOTES = (
    "<b>GHI CHÚ VẬT LIỆU</b><br>"
    "• Dầm BTCT DƯL · f'c = 40 MPa<br>"
    "• Mố/trụ/bệ BT · f'c = 30 MPa<br>"
    "• Cốt thép CB400-V · fy = 400 MPa<br>"
    "• Lớp phủ BTN dày 70mm + lớp phòng nước"
)


def _add_material_notes(fig, loc="bl"):
    """Ghi chú vật liệu & tiêu chuẩn (neo theo khung giấy)."""
    x, xa = (0.005, "left") if loc.endswith("l") else (0.995, "right")
    y, ya = (0.99, "top") if loc.startswith("t") else (0.02, "bottom")
    fig.add_annotation(
        xref="paper", yref="paper", x=x, y=y, xanchor=xa, yanchor=ya,
        text=_MAT_NOTES, showarrow=False, align="left",
        font=dict(size=8, color="#34495e"),
        bgcolor="rgba(255,255,255,0.92)", bordercolor="#95a5a6",
        borderwidth=1, borderpad=4)


def mong_dims(mong):
    """Chuẩn hoá kích thước cọc từ mong_result (AI) HOẶC bản ghi thư viện móng.

    Trả (D_coc_m, L_coc_m, n_coc). Hỗ trợ mọi bộ tên khóa đang dùng:
      • AI:       D_coc_mm (mm), L_coc_tu (m), So_coc_tu
      • Thư viện: duong_kinh_coc (m), chieu_dai_coc (m), so_coc
      • Khối lượng: kich_thuoc_mm (mm), so_coc_be
    """
    m = mong or {}
    if m.get("D_coc_mm") or m.get("kich_thuoc_mm"):
        D = float(m.get("D_coc_mm") or m.get("kich_thuoc_mm") or 600) / 1000.0
    else:
        D = float(m.get("duong_kinh_coc", 0) or 0) or 0.6
    L = float(m.get("L_coc_tu") or m.get("chieu_dai_coc") or 30) or 30.0
    n = int(float(m.get("So_coc_tu") or m.get("so_coc_be") or m.get("so_coc") or 4) or 4)
    return D, L, max(1, n)


def pile_grid_fit(be_ngang, be_doc, D, la_ckn):
    """Lưới cọc LẤP ĐẦY BỆ HIỆN TẠI với tim-tim ≥ tối thiểu TCVN 10304:2025:
      • Khoan nhồi: S_min = max(3.0D, D+1.0m thông thủy); tim cọc ngoài cách
        mép bệ ≥ D/2 + 300mm.
      • Đóng/ép:    S_min = max(750mm, 2.5D); mép ≥ D/2 + 225mm.
    Số cọc mỗi phương = số lớn nhất đặt vừa (bệ rộng → nhiều cọc, bệ hẹp → ít)
    → mật độ luôn KHỚP kích thước bệ. Trả (xs_ngang, ys_doc, S_ngang, S_doc)."""
    D = max(float(D or 0.6), 0.2)
    S_min = max(3.0 * D, D + 1.0) if la_ckn else max(0.75, 2.5 * D)
    edge = D / 2.0 + (0.30 if la_ckn else 0.225)

    def _axis(B):
        avail = max(0.0, float(B or 0) - 2.0 * edge)
        n = max(1, int(np.floor(avail / S_min + 1e-9)) + 1)
        if n == 1:
            return [0.0], S_min
        S = avail / (n - 1)
        return [(i - (n - 1) / 2.0) * S for i in range(n)], S

    xs, S_ng = _axis(be_ngang)
    ys, S_dc = _axis(be_doc)
    return xs, ys, S_ng, S_dc


def mong_pile_grid(mong, be_ngang=None, be_doc=None):
    """LƯỚI CỌC CHUẨN — MỘT NGUỒN cho mọi bản vẽ (trắc dọc, MCN, mặt bằng, 3D)
    khi chưa khai sơ đồ cọc DXF.

    be_ngang/be_doc cho → lưới LẤP ĐẦY BỆ THẬT đó (pile_grid_fit, gốc = bệ của
    mô hình 3D); không cho → dùng layout Module 08 (n_cols_be, n_rows_be,
    khoang_cach_tim). Trả (xs_ngang, ys_doc, D_m, L_m, S_m)."""
    m = mong or {}
    D, L, n = mong_dims(m)
    la_ckn = (D >= 0.8 or "khoan" in str(m.get("loai_coc")
                                         or m.get("loai_mong") or "").lower())
    if be_ngang and be_doc and float(be_ngang) > 0 and float(be_doc) > 0:
        xs, ys, S_ng, S_dc = pile_grid_fit(be_ngang, be_doc, D, la_ckn)
        return xs, ys, D, L, round(min(S_ng, S_dc), 2)
    nc = int(float(m.get("n_cols_be") or 0) or 0)
    nr = int(float(m.get("n_rows_be") or 0) or 0)
    if nc <= 0:
        nc = max(2, int(np.ceil(np.sqrt(n))))
    if nr <= 0:
        nr = max(1, int(np.ceil(n / nc)))
    S = float(m.get("khoang_cach_tim") or m.get("khoang_cach_tim_coc") or 0)
    if S <= 0:
        S = max(0.75, (3.0 if D >= 0.8 else 2.5) * D)
    xs = [(i - (nc - 1) / 2.0) * S for i in range(nc)]
    ys = [(j - (nr - 1) / 2.0) * S for j in range(nr)]
    return xs, ys, D, L, S


def validate_span_layout(d, x0, x_end, x_tim, B_tk):
    """Kiểm tra bố trí NHỊP / DẦM / BỀ RỘNG → list cảnh báo (rỗng nếu hợp lệ)."""
    d = d or {}
    sl  = d.get("span_layout") or {}
    kcn = d.get("kcn_result") or d.get("ai_result") or {}
    warns = []

    # 1) Dầm có lấp đủ BỀ RỘNG cầu? (n−1)·@ + 2·hẫng ≈ bc
    bc    = float(d.get("bc", 0) or 0)
    n_dam = int(float(kcn.get("so_luong_dam", 0) or 0))
    kc    = float(kcn.get("khoang_cach_dam", 0) or 0)
    oh    = float(d.get("overhang", 0.5) or 0.5)
    if bc > 0 and n_dam >= 2 and kc > 0:
        used = (n_dam - 1) * kc + 2 * oh
        if abs(used - bc) > 0.30:
            warns.append(
                f"Bố trí {n_dam} dầm @ {kc:.2f}m + 2×hẫng {oh:.2f}m = {used:.2f}m, "
                f"lệch bề rộng cầu {bc:.2f}m ({used - bc:+.2f}m) — chỉnh số dầm / "
                f"khoảng cách dầm / bề rộng cầu cho khớp.")

    # 2) Chiều dài DẦM có đủ vượt NHỊP bố trí?
    supports, L_std = resolve_supports(d, x0, x_end, x_tim, B_tk)
    L_dam = float(kcn.get("chieu_dai", 0) or 0)
    if L_dam > 0 and L_std and L_dam + 0.5 < float(L_std):
        warns.append(
            f"Chiều dài dầm {L_dam:.1f}m < nhịp bố trí {float(L_std):.1f}m — "
            f"dầm không đủ vượt nhịp; tăng chiều dài dầm hoặc giảm nhịp.")

    # 3) Bố trí 2 tầng: tĩnh không & khoảng hở đầu/cuối
    if sl.get("mode") == "two_tier":
        L_clear = B_tk + 2.0 * _PIER_SAFETY
        L_main  = sl.get("L_main")
        if L_main and float(L_main) + 1e-6 < L_clear:
            warns.append(
                f"Nhịp chính L={float(L_main):.1f}m < tĩnh không yêu cầu "
                f"{L_clear:.1f}m → đã tự nâng lên {_snap_up_std(L_clear):.1f}m.")
        if supports:
            if supports[0] > x0 + 1e-6:
                warns.append(
                    f"Bố trí bắt đầu tại {supports[0]:.1f}m > mố trái {x0:.1f}m "
                    f"— có khoảng hở đầu cầu.")
            if supports[-1] < x_end - 1e-6:
                warns.append(
                    f"Bố trí kết thúc tại {supports[-1]:.1f}m < mố phải "
                    f"{x_end:.1f}m — có khoảng hở cuối cầu.")
    return warns


# ===========================================================================
# 0b. OVERLAY ĐỊA CHẤT — Trắc dọc
# ===========================================================================
_GEO_FILL = [
    "rgba(190,155, 95,0.28)",
    "rgba(215,195,135,0.28)",
    "rgba(185,170,115,0.28)",
    "rgba(165,155,100,0.28)",
    "rgba(155,185,140,0.28)",
    "rgba(120,165,200,0.28)",
    "rgba( 95,130,180,0.28)",
    "rgba( 75,105,155,0.28)",
]
_GEO_LINE = [
    "rgba(190,155, 95,0.80)",
    "rgba(215,195,135,0.80)",
    "rgba(185,170,115,0.80)",
    "rgba(165,155,100,0.80)",
    "rgba(155,185,140,0.80)",
    "rgba(120,165,200,0.80)",
    "rgba( 95,130,180,0.80)",
    "rgba( 75,105,155,0.80)",
]


def _draw_dia_chat_trac_doc(fig, dia_chat_data, x0, x_end, h_tn, z_min, mg=20):
    """Overlay địa chất lên trắc dọc: tầng lớp màu + hình trụ HK + SPT."""
    if not dia_chat_data:
        return
    hk_list = dia_chat_data.get("ho_khoan_list", [])
    if not hk_list:
        return

    x_span = x_end - x0

    def _chainage(hk, idx):
        lt = hk.get("ly_trinh")
        if lt is not None:
            try:
                return float(lt)
            except (TypeError, ValueError):
                pass
        xc = hk.get("X")
        if xc is not None:
            try:
                xf = float(xc)
                if x0 - x_span * 0.6 <= xf <= x_end + x_span * 0.6:
                    return xf
            except (TypeError, ValueError):
                pass
        return x0 + (idx + 0.5) / len(hk_list) * x_span

    hk_ch = sorted(
        [(i, _chainage(hk, i), hk) for i, hk in enumerate(hk_list)],
        key=lambda t: t[1],
    )

    # Thu thập tên lớp theo thứ tự
    lop_order, seen = [], set()
    for _, _, hk in hk_ch:
        for lop in hk.get("lop_dat", []):
            nm = str(lop.get("ten_lop", "")).strip()
            if nm and nm not in seen:
                lop_order.append(nm)
                seen.add(nm)
    if not lop_order:
        return

    x_left  = x0  - mg * 0.20
    x_right = x_end + mg * 0.20
    N_WAVE  = 80

    def _wave_boundary(pts_sorted, xl, xr):
        """Nội suy + thêm gợn sóng nhỏ cho đường ranh giới."""
        ext = [(xl, pts_sorted[0][1])] + pts_sorted + [(xr, pts_sorted[-1][1])]
        xw = np.linspace(xl, xr, N_WAVE)
        zw = np.interp(xw, [p[0] for p in ext], [p[1] for p in ext])
        amp = max(0.04, (max(p[1] for p in ext) - min(p[1] for p in ext)) * 0.025)
        zw += amp * np.sin(np.linspace(0, 5 * np.pi, N_WAVE))
        return xw, zw

    # ── Vẽ tầng lớp địa chất ─────────────────────────────────────────────
    for li, lop_name in enumerate(lop_order):
        fill_c = _GEO_FILL[li % len(_GEO_FILL)]
        line_c = _GEO_LINE[li % len(_GEO_LINE)]

        bot_pts, top_pts = [], []
        for _, ch, hk in hk_ch:
            z_m = float(hk.get("Z", h_tn) or h_tn)
            for lop in hk.get("lop_dat", []):
                if str(lop.get("ten_lop", "")).strip() == lop_name:
                    bot_pts.append((ch, float(lop["cao_do_day"])))
                    if li == 0:
                        top_pts.append((ch, z_m))
                    else:
                        prev = lop_order[li - 1]
                        for lp2 in hk.get("lop_dat", []):
                            if str(lp2.get("ten_lop", "")).strip() == prev:
                                top_pts.append((ch, float(lp2["cao_do_day"])))
                                break
                        else:
                            top_pts.append((ch, z_m))
                    break

        if not bot_pts:
            continue

        xb, zb = _wave_boundary(sorted(bot_pts, key=lambda p: p[0]), x_left, x_right)
        if top_pts:
            xt2, zt = _wave_boundary(sorted(top_pts, key=lambda p: p[0]), x_left, x_right)
        else:
            xt2 = np.linspace(x_left, x_right, N_WAVE)
            zt  = np.full(N_WAVE, h_tn)

        # Clip tại z_min
        zb = np.maximum(zb, z_min)
        zt = np.maximum(zt, z_min)

        fig.add_trace(go.Scatter(
            x=list(xb) + list(xb[::-1]),
            y=list(zt) + list(zb[::-1]),
            fill="toself", fillcolor=fill_c,
            line=dict(color="rgba(0,0,0,0)", width=0),
            mode="lines", name=f"Lớp địa chất {lop_name}", showlegend=True,
            hovertemplate=f"<b>Lớp {lop_name}</b><extra></extra>",
        ))
        # Đường ranh giới đáy lớp
        fig.add_trace(go.Scatter(
            x=list(xb), y=list(zb),
            mode="lines", line=dict(color=line_c, width=1.2),
            showlegend=False, hoverinfo="skip",
        ))
        # Nhãn tên lớp tại giữa
        x_mid = (x_left + x_right) / 2
        z_bot_mid = float(np.interp(x_mid, xb, zb))
        z_top_mid = float(np.interp(x_mid, xt2, zt))
        z_label   = (z_top_mid + z_bot_mid) / 2
        if z_label > z_min + 0.8:
            fig.add_annotation(
                x=x_mid, y=z_label,
                text=f"<b>{lop_name}</b>",
                showarrow=False, font=dict(size=9, color="#333333"),
                bgcolor="rgba(255,255,255,0.78)",
                bordercolor=line_c, borderwidth=1, borderpad=3,
            )

    # ── Hình trụ HK ──────────────────────────────────────────────────────
    bh_w = max(0.35, x_span * 0.004)
    for _, ch, hk in hk_ch:
        z_m = float(hk.get("Z", h_tn) or h_tn)
        lop_dat = hk.get("lop_dat", [])
        z_bot_hk = float(lop_dat[-1]["cao_do_day"]) if lop_dat else z_min
        z_bot_hk = max(z_bot_hk, z_min)

        # Màu từng lớp trong cột HK
        for lop in lop_dat:
            zd = float(lop["cao_do_day"])
            zdi= float(lop["cao_do_dinh"])
            if zd >= z_m or zdi <= z_min:
                continue
            top_lop = min(zdi, z_m)
            bot_lop = max(zd,  z_min)
            nm = str(lop.get("ten_lop", "")).strip()
            ci = lop_order.index(nm) if nm in lop_order else 0
            fig.add_trace(go.Scatter(
                x=[ch-bh_w, ch+bh_w, ch+bh_w, ch-bh_w, ch-bh_w],
                y=[bot_lop, bot_lop, top_lop, top_lop, bot_lop],
                fill="toself", fillcolor=_GEO_FILL[ci % len(_GEO_FILL)],
                line=dict(color="#444", width=0.6),
                mode="lines", showlegend=False, hoverinfo="skip",
            ))
            # Đường kẻ ngang ranh giới lớp + cao độ
            fig.add_shape(type="line",
                x0=ch - bh_w, y0=zd, x1=ch + bh_w * 2.2, y1=zd,
                line=dict(color="#555", width=0.7))
            fig.add_annotation(
                x=ch + bh_w * 2.5, y=zd,
                text=f"{zd:.1f}",
                showarrow=False, font=dict(size=7, color="#333"),
                xanchor="left", yanchor="middle",
            )

        # Viền ngoài cột HK
        fig.add_trace(go.Scatter(
            x=[ch-bh_w, ch+bh_w, ch+bh_w, ch-bh_w, ch-bh_w],
            y=[z_bot_hk, z_bot_hk, z_m, z_m, z_bot_hk],
            fill="none",
            line=dict(color="#111", width=1.4),
            mode="lines", showlegend=False, hoverinfo="skip",
        ))

        # SPT bên trái (N values)
        for s_start, s_end, n_val in hk.get("spt", []):
            if n_val is None:
                continue
            z_spt = z_m - (float(s_start) + float(s_end)) / 2.0
            if z_spt < z_min or z_spt > z_m + 0.5:
                continue
            fig.add_annotation(
                x=ch - bh_w * 2.5, y=z_spt,
                text=f"<span style='color:#8B0000'>{int(n_val)}</span>",
                showarrow=False, font=dict(size=7),
                xanchor="right", yanchor="middle",
            )

        # Tên HK + cao độ miệng
        fig.add_annotation(
            x=ch, y=z_m + 0.6,
            text=f"<b>{hk['ten']}</b>",
            showarrow=False, font=dict(size=9, color="#1F4E79"),
            yanchor="bottom", bgcolor="rgba(255,255,255,0.85)",
        )
        fig.add_annotation(
            x=ch, y=z_m,
            text=f"+{z_m:.2f}",
            showarrow=False, font=dict(size=7, color="#1F4E79"),
            yanchor="top", xanchor="center",
        )


# ===========================================================================
# 1. SƠ ĐỒ BỐ TRÍ NHỊP (2D) — Trụ đặt NGOÀI tĩnh không
# ===========================================================================
def ve_so_do_nhip_2d(d, df_tim_line=None, dia_chat_data=None,
                     pier_assembly=None, abutment_assembly=None, beam_params=None):
    """
    Sơ đồ nhịp 2D từ design_data.
    - Trụ được đặt tại biên tĩnh không, KHÔNG vi phạm vùng thông thuyền.
    - Nếu có df_tim_line (Lý trình, Z): overlay đường địa hình thực đo.
    - Tọa độ X theo Lý trình thực địa (cùng hệ với df_tim_line).
    - beam_params: thông tin dầm THỰC đang áp dụng (vd loai_dam) để tiêu đề/ghi
      chú hiển thị đúng loại dầm thư viện thay vì loại dầm AI mặc định.
    """
    kcn = d.get("kcn_result") or d.get("ai_result", {})
    geo = d.get("geo_logic", {})

    n_nhip  = int(kcn.get("tong_so_nhip", 3))
    L_nhip  = float(kcn.get("chieu_dai", 40))
    H_dam   = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    # Loại dầm: ưu tiên dầm THỰC đang áp dụng (thư viện) → sau đó mới tới AI
    loai    = str((beam_params or {}).get("loai_dam") or kcn.get("loai_dam", "Dầm I"))
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
    mong    = d.get("mong_result") or {}
    D_coc_m, L_coc, _n_coc = mong_dims(mong)
    # Lưới cọc CHUẨN Module 08 — trắc dọc (x = DỌC cầu) thấy n_rows cọc tim-tim S.
    _pg_xs, _pg_ys, _, _, _pg_S = mong_pile_grid(mong)
    n_coc_row = max(2, min(4, _n_coc))     # (giữ cho code cũ còn tham chiếu)

    # TRỤ / MỐ lấy từ MÔ HÌNH 3D (d['_pier_model'] / d['_mo_model']) nếu người gọi
    # không truyền assembly → trắc dọc hiển thị ĐÚNG trụ/mố như 3D cầu, KHÔNG dùng
    # khối tự vẽ độc lập.
    if pier_assembly is None:
        pier_assembly = d.get("_pier_model")
    if abutment_assembly is None:
        abutment_assembly = d.get("_mo_model")

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

    # ── Bố trí nhịp ĐỀU theo chiều dài định hình catalog, nhịp chính căng
    #    giữa tĩnh không (xem _calc_span_layout) ────────────────────────────
    L_nhip   = float(kcn.get("chieu_dai", 33.0) or 33.0)
    supports, L_std = resolve_supports(d, x0, x_end, x_tim, B_tk, L_nhip)
    x0, x_end = supports[0], supports[-1]
    piers    = supports[1:-1]
    n_nhip   = len(supports) - 1
    L_cau    = x_end - x0
    spans    = [(supports[i], supports[i+1]) for i in range(len(supports)-1)]

    # ── ĐƯỜNG ĐỎ (trắc dọc thiết kế) — datum của toàn kết cấu ───────────────
    # Đỉnh đường cong tại TIM TĨNH KHÔNG; cao độ đỉnh tính từ đỉnh tĩnh không +
    # 100mm khe hở đáy dầm (xét dốc ngang dầm biên) + H_dầm + bề dày bản.
    # Bản mặt cầu, dầm, xà mũ đều BÁM đường đỏ (top-down).
    _z_red, _x_apex, _z_crown, _t_ban_rl, _H_dam_rl = make_red_line(d)

    def _z_deck_bot(x):   # đáy bản mặt cầu = đường đỏ − bề dày bản
        return _z_red(x) - t_ban

    def _z_beam_soffit(x):  # đáy dầm = đáy bản − chiều cao dầm
        return _z_red(x) - t_ban - H_dam

    def _z_cap_top(x):    # đỉnh xà mũ = đáy dầm − (đá kê gối + gối) 150mm
        return _z_beam_soffit(x) - H_DA_KE_GOI

    # ── Cao độ kết cấu ĐẠI DIỆN (tại tim TK — cho dim & khối hạ bộ) ─────────
    h_goi    = _h_goi(d)
    z_deck   = _z_crown                     # đỉnh bản tại đỉnh đường cong
    cao_dd   = _z_beam_soffit(_x_apex)      # đáy dầm đại diện (bám đường đỏ)
    z_dam_b  = cao_dd
    z_cap_t  = _z_cap_top(_x_apex)          # đỉnh xà mũ đại diện
    z_cap_b  = z_cap_t - 0.80
    z_sh_b   = z_cap_b - H_tru
    z_be_t   = z_sh_b
    z_be_b   = z_sh_b - 1.50
    _z_terr_piers = [_tz(p) for p in piers] if piers else [h_tn]
    _z_be_b_min   = min((zt - 0.5 - 1.50) for zt in _z_terr_piers)
    z_min    = min(_z_be_b_min - L_coc - 2.0, z_be_b - L_coc - 2.0, MNTN - 0.5)

    W_cap = max(2.0, L_cau / n_nhip * 0.05 + 1.0)
    W_tru = 1.2
    W_be  = W_cap + 0.8
    W_mo  = 3.0

    _gap_bm = _gap_ban_mo(L_cau)            # khe hở bản ↔ mố mỗi đầu
    mg = max(20, L_cau * 0.15)
    fig = go.Figure()

    # ── Đường địa hình từ khảo sát (nếu có) ─────────────────────────────
    # Khi có dữ liệu địa chất, fill đất mờ hơn để địa chất hiện rõ
    _terr_fill_alpha = "0.12" if dia_chat_data else "0.35"
    _dat_fill = f"rgba(169,120,74,{_terr_fill_alpha})"
    if df_tim_line is not None and not df_tim_line.empty:
        lt_col = next((c for c in df_tim_line.columns if 'ý trình' in c or 'ly_trinh' in c.lower() or c.lower() == 'x'), None)
        z_col  = next((c for c in df_tim_line.columns if c.upper() in ['Z', 'CAO_DO', 'H', 'ELEVATION']), None)
        if lt_col and z_col:
            df_v = df_tim_line[
                (df_tim_line[lt_col] >= x0 - mg) &
                (df_tim_line[lt_col] <= x_end + mg)
            ].sort_values(lt_col)
            if not df_v.empty:
                # Fill trước (nền), đường địa hình vẽ lại sau overlay địa chất
                fig.add_trace(go.Scatter(
                    x=list(df_v[lt_col]) + list(df_v[lt_col])[::-1],
                    y=list(df_v[z_col]) + [z_min]*len(df_v),
                    fill="toself", fillcolor=_dat_fill,
                    line=dict(color="rgba(0,0,0,0)"),
                    mode="lines", showlegend=False, hoverinfo="skip"
                ))
    else:
        _poly(fig,
            [x0-mg, x_end+mg, x_end+mg, x0-mg],
            [h_tn, h_tn, z_min-0.2, z_min-0.2],
            _dat_fill, "rgba(0,0,0,0)", "", showlegend=False)

    # ── Overlay địa chất (vẽ SAU fill đất để hiện lên trên) ─────────────
    _draw_dia_chat_trac_doc(fig, dia_chat_data, x0, x_end, h_tn, z_min, mg=mg)

    # ── Đường địa hình (vẽ lại lên trên cùng để rõ nét) ─────────────────
    if df_tim_line is not None and not df_tim_line.empty and lt_col and z_col and not df_v.empty:
        fig.add_trace(go.Scatter(
            x=df_v[lt_col], y=df_v[z_col],
            mode="lines", name="Địa hình TN (khảo sát)",
            line=dict(color=_C["dia_hinh"], width=2.5),
            hovertemplate="Lý trình: %{x:.1f}m<br>Cao độ: %{y:.3f}m<extra>Địa hình</extra>"
        ))
    else:
        _hline(fig, h_tn, x0-mg, x_end+mg,
               f"CĐTN trung bình ≈ {h_tn:.2f}m", "#27ae60", dash="dash")

    # ── Mực nước — CHỈ hiển thị trong phạm vi TĨNH KHÔNG ─────────────────────
    _wx0 = x_tim - B_tk / 2
    _wx1 = x_tim + B_tk / 2
    _poly(fig,
        [_wx0, _wx1, _wx1, _wx0],
        [MNTN, MNTN, MNCN, MNCN],
        _C["nuoc"], "rgba(0,0,0,0)", "Mực nước sông", showlegend=True)
    for y_w, lbl, clr in [
        (MNCN, f"MNCN={MNCN:.3f}m", "#c0392b"),
        (MNTT, f"MNTT={MNTT:.3f}m", "#2980b9"),
        (MNTN, f"MNTN={MNTN:.3f}m", "#1abc9c"),
    ]:
        fig.add_trace(go.Scatter(
            x=[_wx0, _wx1], y=[y_w, y_w],
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

        # Phần ngầm (bệ cọc generic) — CHỈ vẽ khi KHÔNG có mố thư viện. Mố thư
        # viện đã GỒM bệ (đùn xuống ĐTN−0.5) → bỏ hẳn khối bệ cũ.
        if not abutment_assembly:
            _poly(fig,
                [xm, xm+sign*W_mo, xm+sign*W_mo, xm],
                [z_mo_bot, z_mo_bot, z_terr_mo, z_terr_mo],
                "rgba(192,160,107,0.3)", _C["be_dk"],
                "", showlegend=False, lw=1)

        # Phần nổi trên mặt đất (thân mố từ terrain → deck)
        _pile_ztop = z_mo_bot          # đỉnh cọc (mặc định generic)
        _pile_xc   = xm                # tâm nhóm cọc
        _pile_span = abs(W_mo)         # bề rộng bố trí cọc
        if abutment_assembly:
            _PB = _get_PB()
            # Đỉnh mố (vai kê gối) = ĐÁY DẦM (z_cap_t). ĐÁY mố (bệ) chôn 0.5m
            # dưới ĐƯỜNG TỰ NHIÊN tại mố (giống quy ước bệ trụ). out_dir=sign:
            # MẶT TRƯỚC mố (phía nhịp, u>0) quay VÀO NHỊP, lưng (u<0) ra mái dốc.
            _z_base_mo = z_terr_mo - 0.5
            # CĂN theo KHOẢNG HỞ đầu dầm ↔ mố = 100mm: mặt trước tường đỉnh đặt
            # lùi 0.10m sau đầu dầm (đầu dầm tại xm) → khe co giãn 100mm.
            _u_bw = _PB.abut_backwall_u_m(abutment_assembly)
            _xf_mo = xm - sign * (KHO_HO_DAM_MO + _u_bw)
            # Đáy dầm PHÍA MỐ bám ĐƯỜNG ĐỎ tại mố (đầu dầm lên mố là đầu trơn).
            _seat_mo = _abut_seat_z(_z_beam_soffit(xm), pier_assembly)
            _mo_allx = []; _mo_allz = []
            for _pl in _PB.abutment_elevation_polys(
                    abutment_assembly, H_tru=(_seat_mo - _z_base_mo),
                    x_face=_xf_mo, out_dir=sign, z_base=_z_base_mo,
                    seat_z=_seat_mo):      # vai kê = đáy dầm MỐ; ĐỈNH bệ = ĐTN−0.5
                _poly(fig, _pl["xs"], _pl["zs"], _pl["color"], _C["be_dk"],
                      (_pl["name"] if side == "Trái" else ""),
                      showlegend=(side == "Trái"))
                _mo_allx += list(_pl["xs"]); _mo_allz += list(_pl["zs"])
            if _mo_allx:                  # cọc ĐI THEO BỆ mố mới
                _pile_xc   = (min(_mo_allx) + max(_mo_allx)) / 2.0
                _pile_span = max(_mo_allx) - min(_mo_allx)
            # Cọc bắt đầu từ ĐÁY BỆ thực (đáy mố sâu nhất, dưới ĐTN).
            _pile_ztop = min(_mo_allz) if _mo_allz else _z_base_mo
        else:
            _z_top_mo = _z_red(xm)          # đỉnh mố = đường đỏ tại mố
            _poly(fig,
                [xm, xm+sign*W_mo, xm+sign*W_mo, xm],
                [z_terr_mo, z_terr_mo, _z_top_mo, _z_top_mo],
                _C["moc"], _C["be_dk"], f"Mố {side}")

        # Đường địa hình tại mố (chỉ thị)
        fig.add_annotation(
            x=xm + sign*W_mo*0.5, y=z_terr_mo,
            text=f"Z={z_terr_mo:.2f}m",
            showarrow=False, font=dict(size=7, color="#27ae60"),
            yanchor="bottom", bgcolor="rgba(255,255,255,0.7)"
        )

        # ── Cọc tại mố ──────────────────────────────────────────────────────
        _mo_key = "mo_trai" if side == "Trái" else "mo_phai"
        _piles_mo = _layout_piles(d, _mo_key)
        if _piles_mo:
            # Sơ đồ cọc khai báo từ DXF → vẽ theo tọa độ thật (đỉnh cọc = đáy bệ mố)
            _draw_piles_elevation(
                fig, _piles_mo, x_center=_pile_xc, z_top=_pile_ztop,
                color="rgba(120,90,50,0.75)",
                legend_name=(f"Cọc mố ({len(_piles_mo)} cọc)" if side == "Trái" else None))
        else:
            # Lưới cọc LẤP ĐẦY BỆ MỐ THẬT (gốc 3D): trắc dọc thấy n_rows cọc
            # theo DỌC, tim-tim ≥ tối thiểu TCVN.
            _ys_mo = _pg_ys
            if abutment_assembly:
                try:
                    _bnm, _bdm = _get_PB().abut_footing_dims_m(
                        abutment_assembly, target_width=bc)
                    if _bdm > 0.3:
                        _, _ys_mo, _, _, _ = mong_pile_grid(
                            mong, be_ngang=_bnm, be_doc=_bdm)
                except Exception:
                    pass
            coc_xs_mo = [_pile_xc + _yy for _yy in _ys_mo]
            for j, xc in enumerate(coc_xs_mo):
                fig.add_trace(go.Scatter(
                    x=[xc, xc], y=[_pile_ztop, _pile_ztop - L_coc],
                    mode="lines",
                    line=dict(color="rgba(120,90,50,0.65)", width=max(2, int(D_coc_m * 12))),
                    name=f"Cọc mố Ø{int(D_coc_m*1000)}mm, L≈{L_coc:.0f}m"
                         if (side == "Trái" and j == 0) else "",
                    showlegend=(side == "Trái" and j == 0),
                ))
            fig.add_trace(go.Scatter(
                x=list(coc_xs_mo), y=[_pile_ztop - L_coc] * len(coc_xs_mo),
                mode="markers",
                marker=dict(symbol="triangle-down", size=5, color="rgba(120,90,50,0.8)"),
                showlegend=False, hoverinfo="skip",
            ))

    # ── Trụ giữa (đặt NGOÀI tĩnh không + 2m an toàn) ─────────────────────
    # ĐỈNH BỆ DÙNG CHUNG với 3D & mặt cắt chi tiết (_pier_be_tops_synced):
    # min(ĐTN−0.5, đáy_dầm−1.0) + đồng bộ cao độ chẵn → 3 view khớp tuyệt đối.
    _be_top_map = _pier_be_tops_synced(piers, _tz, _z_beam_soffit)
    for i, xt in enumerate(piers):
        sl = (i == 0)
        z_terr_tru = _tz(xt)   # cao độ địa hình (đường tự nhiên) tại vị trí trụ

        # ĐỈNH Ụ GIỮA xà mũ = ĐÁY BẢN MẶT CẦU (đỡ bản); 2 VAI KÊ 2 bên thấp hơn
        # (đỡ phần KHẤC của dầm). Neo xà mũ lắp ghép tại đỉnh ụ = đáy bản.
        z_ugiua_i = _z_deck_bot(xt)               # đỉnh ụ giữa = đáy bản mặt cầu
        z_vaike_i = _z_beam_soffit(xt)            # vai kê = đáy dầm (đỡ khấc dầm)
        z_cap_t_i = z_ugiua_i                     # neo đỉnh xà mũ (ụ giữa)
        z_cap_b_i = z_vaike_i - 0.80              # đáy xà mũ (dưới vai kê)
        # Đỉnh bệ CHÔN 0.5m DƯỚI ĐTN, đã ĐỒNG BỘ về cao độ chẵn (nếu chênh ≤ 1m).
        z_be_t_i = _be_top_map.get(round(xt, 3),
                                   min(z_terr_tru - 0.5, z_cap_b_i - 0.5))
        z_be_t_i = min(z_be_t_i, z_cap_b_i - 0.5)       # vẫn phải chừa ≥0.5m thân
        z_sh_b_i = z_be_t_i                              # đáy thân trụ = đỉnh bệ
        z_be_b_i = z_be_t_i - 1.50                       # đáy bệ cọc

        # Trụ LẮP GHÉP từ thư viện: vẽ bóng mặt đứng dọc theo mặt cắt thật
        if pier_assembly:
            _PB = _get_PB()
            # TRẮC DỌC = HÌNH CHIẾU ĐỨNG thật của LƯỚI 3D trụ (chiếu lên x–z tại
            # tim) — cùng nguồn với 3D toàn cầu → trụ 2 thân hiện đúng, xà mũ bậc
            # (ụ giữa) đúng, thay khối hộp tham số cũ (pier_elevation_rects).
            # Xà mũ NỚI RỘNG cho nhịp SPT vượt tĩnh không (ụ giữa to hơn W0).
            _wmap = (d or {}).get("_pier_cap_widen") or {}
            _w0td = float((d or {}).get("_pier_cap_W0", 0) or 0)
            _mid_extra_td = max(0.0, _wmap.get(round(xt, 3), _w0td) - _w0td)
            _ptr_td = _PB.build_pier_mesh_traces(
                pier_assembly, H_tru=(z_cap_t_i - z_be_b_i),
                x_ctr=xt, z_base=z_be_b_i, cap_width=None,
                cap_mid_extra=_mid_extra_td)
            _seen_td = set()
            for _rc in project_mesh_traces(_ptr_td, axis="y"):
                _nm = _rc["name"].split(" #")[0]
                _sl = sl and _nm not in _seen_td; _seen_td.add(_nm)
                _poly(fig, _rc["xs"], _rc["zs"], _rc["color"], _C["dam_dk"],
                      (_nm if _sl else ""), showlegend=_sl)
            fig.add_annotation(
                x=xt, y=z_terr_tru, text=f"Z={z_terr_tru:.2f}m",
                showarrow=True, arrowhead=2, arrowcolor="#27ae60",
                ax=25, ay=-15, font=dict(size=7, color="#27ae60"),
                bgcolor="rgba(255,255,255,0.7)")
            _piles_tru = _layout_piles(d, f"tru_{i+1}")
            if _piles_tru:
                _draw_piles_elevation(
                    fig, _piles_tru, x_center=xt, z_top=z_be_b_i, color=_C["be_dk"],
                    legend_name=(f"Cọc trụ ({len(_piles_tru)} cọc)" if sl else None))
            else:
                # Lưới cọc Module 08: n_rows cọc theo DỌC cầu, tim-tim đúng S.
                coc_xs_tru = [xt + _yy for _yy in _pg_ys]
                for j, xc in enumerate(coc_xs_tru):
                    fig.add_trace(go.Scatter(
                        x=[xc, xc], y=[z_be_b_i, z_be_b_i - L_coc], mode="lines",
                        line=dict(color=_C["be_dk"], width=max(2, int(D_coc_m * 12))),
                        name=(f"Cọc trụ Ø{int(D_coc_m*1000)}mm, L≈{L_coc:.0f}m"
                              if (sl and j == 0) else ""),
                        showlegend=(sl and j == 0)))
                fig.add_trace(go.Scatter(
                    x=list(coc_xs_tru), y=[z_be_b_i - L_coc] * len(coc_xs_tru),
                    mode="markers",
                    marker=dict(symbol="triangle-down", size=5, color=_C["be_dk"]),
                    showlegend=False, hoverinfo="skip"))
            continue

        # Phần NGẦM: bệ cọc + thân trụ dưới mặt đất → nét đứt mờ
        if z_be_b_i < z_terr_tru:
            # Bệ cọc ngầm
            _poly(fig,
                [xt-W_be, xt+W_be, xt+W_be, xt-W_be],
                [z_be_b_i, z_be_b_i, min(z_be_t_i, z_terr_tru), min(z_be_t_i, z_terr_tru)],
                "rgba(170,183,184,0.3)", _C["be_dk"],
                "Bệ cọc (ngầm)" if sl else "", showlegend=sl, lw=1)
            # Thân trụ ngầm (nếu có)
            if z_sh_b_i < z_terr_tru:
                _poly(fig,
                    [xt-W_tru/2, xt+W_tru/2, xt+W_tru/2, xt-W_tru/2],
                    [z_sh_b_i, z_sh_b_i, z_terr_tru, z_terr_tru],
                    "rgba(200,214,192,0.3)", _C["btong_dk"],
                    "", showlegend=False, lw=1)
        else:
            # Đáy sông thấp hơn đáy bệ → bệ + thân nổi trên đáy sông: vẽ bệ ĐẶC
            _poly(fig,
                [xt-W_be, xt+W_be, xt+W_be, xt-W_be],
                [z_be_b_i, z_be_b_i, z_be_t_i, z_be_t_i],
                _C["btong"], _C["be_dk"],
                "Bệ cọc" if sl else "", showlegend=sl)

        # Phần NỔI: thân trụ nhìn thấy từ mặt đất (hoặc đỉnh bệ nếu bệ nổi) → đáy xà mũ
        z_shaft_visible_bot = max(z_sh_b_i, z_terr_tru)
        if z_shaft_visible_bot < z_cap_b_i:
            _poly(fig,
                [xt-W_tru/2, xt+W_tru/2, xt+W_tru/2, xt-W_tru/2],
                [z_shaft_visible_bot, z_shaft_visible_bot, z_cap_b_i, z_cap_b_i],
                _C["btong"], _C["btong_dk"], f"Thân trụ T{i+1}", showlegend=sl)

        # Xà mũ dạng BẬC: VAI KÊ 2 bên (đến đáy dầm — đỡ khấc dầm) + Ụ GIỮA cao hơn
        # (đến đáy bản — đỡ bản mặt cầu). Bám đường đỏ tại trụ.
        _poly(fig,
            [xt-W_cap, xt+W_cap, xt+W_cap, xt-W_cap],
            [z_cap_b_i, z_cap_b_i, z_vaike_i, z_vaike_i],
            _C["btong"], _C["dam_dk"], "Xà mũ (vai kê)" if sl else "", showlegend=sl)
        _w_ug = max(0.6, W_cap * 0.35)     # nửa bề rộng ụ giữa
        _poly(fig,
            [xt-_w_ug, xt+_w_ug, xt+_w_ug, xt-_w_ug],
            [z_vaike_i, z_vaike_i, z_ugiua_i, z_ugiua_i],
            _C["btong"], _C["dam_dk"], "Ụ giữa (đỡ bản)" if sl else "", showlegend=sl)

        # Cao độ địa hình tại trụ
        fig.add_annotation(
            x=xt, y=z_terr_tru,
            text=f"Z={z_terr_tru:.2f}m",
            showarrow=True, arrowhead=2, arrowcolor="#27ae60",
            ax=25, ay=-15,
            font=dict(size=7, color="#27ae60"),
            bgcolor="rgba(255,255,255,0.7)"
        )

        # ── Cọc tại trụ (bên dưới bệ cọc) ──────────────────────────────────
        _piles_tru = _layout_piles(d, f"tru_{i+1}")
        if _piles_tru:
            _draw_piles_elevation(
                fig, _piles_tru, x_center=xt, z_top=z_be_b_i, color=_C["be_dk"],
                legend_name=(f"Cọc trụ ({len(_piles_tru)} cọc)" if sl else None))
        else:
            # Lưới cọc Module 08: n_rows cọc theo DỌC cầu, tim-tim đúng S.
            coc_xs_tru = [xt + _yy for _yy in _pg_ys]
            for j, xc in enumerate(coc_xs_tru):
                fig.add_trace(go.Scatter(
                    x=[xc, xc], y=[z_be_b_i, z_be_b_i - L_coc],
                    mode="lines",
                    line=dict(color=_C["be_dk"], width=max(2, int(D_coc_m * 12))),
                    name=f"Cọc trụ Ø{int(D_coc_m*1000)}mm, L≈{L_coc:.0f}m"
                         if (sl and j == 0) else "",
                    showlegend=(sl and j == 0),
                ))
            fig.add_trace(go.Scatter(
                x=list(coc_xs_tru), y=[z_be_b_i - L_coc] * len(coc_xs_tru),
                mode="markers",
                marker=dict(symbol="triangle-down", size=5, color=_C["be_dk"]),
                showlegend=False, hoverinfo="skip",
            ))

    # ── DẦM HỘP ĐÚC HẪNG (khoảng trung): thân hộp chiều cao BIẾN THIÊN ──
    # kcn.giai_phap == 'Dầm hộp đúc hẫng' → vẽ đáy dầm parabol mỗi nhịp:
    # H_max tại trụ → H_min giữa nhịp (TCVN 11823), thay cho dầm thư viện.
    if str(kcn.get("giai_phap") or "") == "Dầm hộp đúc hẫng":
        _H_mx = float(kcn.get("H_dam_max") or kcn.get("chieu_cao_dam") or 2.5)
        _H_mn = float(kcn.get("H_dam_min") or max(0.8, _H_mx * 0.5))
        for _ib, (_xs_b, _xe_b) in enumerate(spans):
            _Lsp = max(_xe_b - _xs_b, 1e-6)
            _xx = np.linspace(_xs_b, _xe_b, 40)
            _hh = _H_mn + (_H_mx - _H_mn) * (2 * (_xx - _xs_b) / _Lsp - 1) ** 2
            _top = [_z_deck_bot(_x) for _x in _xx]           # đáy bản = đỉnh hộp
            _bot = [t - h for t, h in zip(_top, _hh)]
            fig.add_trace(go.Scatter(
                x=list(_xx) + list(_xx[::-1]),
                y=_top + _bot[::-1],
                fill="toself", fillcolor=_C["ban"],
                line=dict(color=_C["dam_dk"], width=1.4),
                mode="lines",
                name=(f"Dầm hộp đúc hẫng H={_H_mn:g}–{_H_mx:g}m"
                      if _ib == 0 else ""),
                showlegend=(_ib == 0),
                hovertemplate=("<b>Dầm hộp đúc hẫng cân bằng</b><br>"
                               f"H_max={_H_mx:g}m tại trụ · H_min={_H_mn:g}m "
                               "giữa nhịp<extra></extra>"),
            ))

    # ── Bản mặt cầu theo từng nhịp + nhãn chiều dài ──────────────────────
    # Biên dạng DẦM do người dùng dựng (tab Chi tiết dầm) chèn ở 00-Interface
    # qua get_elevation_profile_traces — KHÔNG vẽ dầm AI tại đây nữa.
    for i, (xs, xe) in enumerate(spans):
        sl = (i == 0)
        L_span = xe - xs
        # Bản mặt cầu chừa KHE HỞ với mố (100mm cầu lớn / 50mm cầu nhỏ) ở 2 đầu
        xs_b = xs + _gap_bm if i == 0 else xs
        xe_b = xe - _gap_bm if i == len(spans) - 1 else xe
        # Mặt TRÊN = đường đỏ; mặt DƯỚI = đáy bản (đường đỏ − bề dày bản), cùng cong
        _poly(fig, [xs_b, xe_b, xe_b, xs_b],
              [_z_deck_bot(xs_b), _z_deck_bot(xe_b), _z_red(xe_b), _z_red(xs_b)],
              _C["ban"], _C["dam_dk"],
              "Bản mặt cầu" if sl else "", showlegend=sl)
        # Dimension mỗi nhịp
        fig.add_annotation(x=(xs+xe)/2, y=_z_red((xs+xe)/2)+0.4, text=f"L={L_span:.1f}m",
                           showarrow=False, font=dict(size=8, color=_C["dam_dk"]),
                           bgcolor="rgba(255,255,255,0.8)")

    # ── ĐƯỜNG ĐỎ (nét thiết kế) — vẽ nổi trên mặt cầu + kéo qua đường đầu cầu ──
    _L_app_red = max(12.0, mg * 0.85)
    _red_xs = list(np.linspace(x0 - _L_app_red, x_end + _L_app_red, 120))
    fig.add_trace(go.Scatter(
        x=_red_xs, y=[_z_red(x) for x in _red_xs],
        mode="lines", name="Đường đỏ (trắc dọc TK)",
        line=dict(color="#e4002b", width=2.6),
        hovertemplate="Lý trình: %{x:.1f}m<br>Đường đỏ: %{y:.3f}m<extra></extra>",
    ))
    _R_show = float(d.get("R_hinh_hoc", 0) or 0)
    _i_show = abs(float(d.get("i_max_hinh_hoc", 0) or 0))
    if _R_show > 0:
        fig.add_annotation(
            x=_x_apex, y=_z_red(_x_apex) + 0.9,
            text=f"ĐƯỜNG ĐỎ — đỉnh tại tim TK | R={_R_show:,.0f}m, i={_i_show:.1f}%",
            showarrow=False, font=dict(size=8, color="#e4002b"),
            bgcolor="rgba(255,255,255,0.8)")

    # ── ĐƯỜNG ĐẦU CẦU (nền đắp + mặt đường sau mố) ──────────────────────────
    L_app  = max(12.0, mg * 0.85)          # chiều dài đoạn đường đầu cầu hiển thị
    taluy  = 1.5                           # mái dốc taluy 1:1.5
    for xm, od in [(x0, -1.0), (x_end, 1.0)]:
        x_far = xm + od * L_app
        z_road_m = _z_red(xm)              # cao độ mặt đường tại mố = đường đỏ
        z_road_f = _z_red(x_far)           # cao độ mặt đường đầu xa (theo đường đỏ)
        z_g   = _tz(xm)                     # cao độ địa hình gần mố
        toe_x = x_far + od * max(0.0, (z_road_f - z_g)) * taluy   # chân taluy
        # Nền đắp đầu cầu (đất đắp sau mố)
        _poly(fig, [xm, x_far, toe_x, xm], [z_road_m, z_road_f, z_g, z_g],
              "rgba(196,164,107,0.32)", "#8a6d3b",
              "Nền đắp đầu cầu" if od < 0 else "", showlegend=(od < 0))
        # Mái taluy (đường dốc) + mặt đường (lớp phủ)
        fig.add_trace(go.Scatter(
            x=[x_far, toe_x], y=[z_road_f, z_g], mode="lines",
            line=dict(color="#8a6d3b", width=1.4, dash="dot"),
            showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(
            x=[xm, x_far], y=[z_road_m, z_road_f], mode="lines",
            line=dict(color="#2c3e50", width=3),
            name="Mặt đường đầu cầu" if od < 0 else "", showlegend=(od < 0),
            hoverinfo="skip"))
        fig.add_annotation(
            x=(xm + x_far) / 2, y=(z_road_m + z_road_f) / 2 + 0.45, text="ĐƯỜNG ĐẦU CẦU",
            showarrow=False, font=dict(size=8, color="#2c3e50"),
            bgcolor="rgba(255,255,255,0.75)")
        # Chiều cao đắp sau mố (từ mặt đất TN tới mặt đường)
        _h_dap = z_road_m - z_g
        if _h_dap > 0.3:
            _dim_v(fig, xm + od * (L_app * 0.5), z_g, z_road_m,
                   f"H_đắp={_h_dap:.2f}m", color="#8a6d3b", dx=od * 0.4)

    # ── Khung tĩnh không THÔNG THUYỀN — đáy tại MNTT (mực nước thông thuyền) ──
    y_tk_bot = MNTT
    fig.add_shape(type="rect",
        x0=x_tim-B_tk/2, x1=x_tim+B_tk/2,
        y0=y_tk_bot, y1=y_tk_bot+H_tk,
        line=dict(color=_C["tk_line"], width=2.5),
        fillcolor=_C["tk"])
    fig.add_annotation(x=x_tim, y=y_tk_bot+H_tk/2,
        text=f"<b>TĨNH KHÔNG</b><br>B={B_tk:.1f}m × H={H_tk:.1f}m",
        showarrow=False, font=dict(size=9, color=_C["tk_line"]),
        bgcolor="rgba(255,255,255,0.8)")

    # ── Tĩnh không PHỤ (khai báo thêm ở hộp thoại thủy văn) ───────────────
    # Mỗi tĩnh không: x=lý trình, z=cao độ đáy, B×H. Trụ đã được rải TRÁNH các
    # vùng này (resolve_supports → _avoid_extra_clearances).
    for _ic, _cx in enumerate((d.get("extra_clearances") or [])):
        try:
            _xk = float(_cx.get("x")); _Bk = float(_cx.get("B", 0) or 0)
            _Hk = float(_cx.get("H", 0) or 0); _zk = float(_cx.get("z", MNCN))
        except (TypeError, ValueError):
            continue
        if _Bk <= 0 or _Hk <= 0:
            continue
        _nm = str(_cx.get("ten") or f"TK phụ {_ic+1}")
        fig.add_shape(type="rect",
            x0=_xk-_Bk/2, x1=_xk+_Bk/2, y0=_zk, y1=_zk+_Hk,
            line=dict(color="#e67e22", width=2.0, dash="dash"),
            fillcolor="rgba(230,126,34,0.10)")
        fig.add_annotation(x=_xk, y=_zk+_Hk/2,
            text=f"<b>{_nm}</b><br>B={_Bk:.1f}m × H={_Hk:.1f}m",
            showarrow=False, font=dict(size=8, color="#e67e22"),
            bgcolor="rgba(255,255,255,0.8)")

    # Gióng thẳng vị trí biên tĩnh không → trụ (từ đáy bệ thực của trụ → mặt cầu)
    # kèm DIM cao độ ĐƯỜNG ĐỎ tại từng vị trí trụ.
    for xp in piers:
        _y0_gp = min(_tz(xp) - 0.5 - 1.50, z_be_b)
        _z_red_p = _z_red(xp)
        fig.add_shape(type="line",
            x0=xp, y0=_y0_gp, x1=xp, y1=_z_red_p,
            line=dict(color="#aab7b8", width=0.8, dash="dashdot"))
        # Cao độ đường đỏ tại trụ (dim)
        fig.add_annotation(
            x=xp, y=_z_red_p + 0.15,
            text=f"▽ ĐĐ={_z_red_p:.3f}m",
            showarrow=False, font=dict(size=8, color="#e4002b"),
            yanchor="bottom", bgcolor="rgba(255,255,255,0.85)")
    # Cao độ đường đỏ tại 2 mố
    for _xm in (x0, x_end):
        _zr = _z_red(_xm)
        fig.add_annotation(
            x=_xm, y=_zr + 0.15, text=f"▽ ĐĐ={_zr:.3f}m",
            showarrow=False, font=dict(size=8, color="#e4002b"),
            yanchor="bottom", bgcolor="rgba(255,255,255,0.85)")

    # ── Dimension tổng ────────────────────────────────────────────────────
    dy_dim = z_deck + 0.7
    _dim_h(fig, dy_dim+1.2, x0, x_end,
           f"<b>L_cầu = {L_cau:.1f}m ({n_nhip} nhịp — {loai})</b>",
           color="#c0392b", dy=0)
    # Nhịp chính = nhịp chứa tim tĩnh không (đã căng giữa x_tim, tất cả nhịp = L_std)
    main_a, main_b = next(((a, b) for (a, b) in spans
                           if a - 1e-6 <= x_tim <= b + 1e-6), (spans[0] if spans else (x0, x_end)))
    span_main = main_b - main_a
    ok_str = "✓" if span_main >= B_tk + 2*_PIER_SAFETY else "⚠"
    _dim_h(fig, dy_dim, main_a, main_b,
           f"Nhịp chính {span_main:.1f}m (≥ B_tk {B_tk:.1f}m + 2×{_PIER_SAFETY:.0f}m) {ok_str}",
           color="#e74c3c", dy=0)
    _dim_v(fig, x_end+W_mo+0.3, z_sh_b, z_cap_b, f"H_trụ={H_tru:.1f}m", dx=0.2)
    _dim_v(fig, x0-W_mo-0.3, cao_dd, cao_dd+H_dam, f"H_dầm={H_dam:.2f}m", dx=0.2)
    if piers:
        _z_be_b0 = min(_tz(piers[0]) - 0.5 - 1.50, z_be_b)  # đáy bệ thực của trụ đầu
        _dim_v(fig, piers[0] + W_be + 0.6, _z_be_b0 - L_coc, _z_be_b0,
               f"L_cọc≈{L_coc:.0f}m", color="#8e44ad", dx=0.2)
        fig.add_annotation(
            x=piers[0] + W_be + 1.6, y=_z_be_b0 - L_coc * 0.5,
            text=f"Cọc Ø{int(D_coc_m*1000)}mm<br>L≈{L_coc:.0f}m",
            showarrow=True, arrowhead=2, arrowcolor=_C["be_dk"],
            ax=30, ay=0,
            font=dict(size=8, color=_C["be_dk"]),
            bgcolor="rgba(255,255,255,0.85)",
        )

    fig.update_layout(
        title=dict(
            text=(f"SƠ ĐỒ BỐ TRÍ NHỊP — {n_nhip} NHỊP ({loai.upper()})"
                  f" | L_cầu={L_cau:.1f}m | B_tk={B_tk:.1f}m"),
            x=0.5, font=dict(size=13)
        ),
        xaxis=dict(title="Lý trình (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5),
        yaxis=dict(title="Cao độ (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5),
        height=680 if dia_chat_data else 580,
        template="plotly_white",
        legend=dict(orientation="h", y=-0.20, font=dict(size=9)),
        margin=dict(l=70, r=30, t=70, b=130),
        hovermode="closest",
    )
    # Dầm kê THẲNG vào khấc xà mũ (tường tai nhô 2 bên) → KHÔNG vẽ khối gối riêng
    # (trước đây khối gối tối ở đỉnh xà mũ trông như 'lỗ chữ nhật').

    _add_elevation_table(fig, d, loc="tl")
    _apply_layers_2d(fig)
    _hover2d(fig)   # hover: tên cấu kiện + lý trình + cao độ
    return fig


# ===========================================================================
# 2. MẶT CẮT NGANG ĐIỂN HÌNH ĐẦY ĐỦ
# ===========================================================================


def ve_mat_cat_ngang_2d(d, beam_params=None, pier_assembly=None, cap_top_y=None,
                        show_substructure=True, beam_centers=None):
    """MCN điển hình: bản, lớp phủ, dầm, lan can, kích thước, chú thích lớp.

    beam_params : dict | None — nếu có, ưu tiên dùng giá trị từ beam_params_final
                                thay cho kcn_result (từ AI/catalog).
    pier_assembly : dict | None — nếu có, vẽ TRỤ LẮP GHÉP thật thay trụ 2 cột cũ.
    cap_top_y : float | None — cao độ ĐỈNH XÀ MŨ (m, hệ MCN). Với dầm Super‑T,
                truyền ĐÁY DẦM TẠI ĐẦU DẦM (mặt cắt đầu) để xà mũ kê đúng đầu dầm.
                None → mặc định −t_bản − H_dầm.
    """
    kcn   = d.get("kcn_result") or d.get("ai_result", {})
    bc    = float(d.get("bc", 12.0))
    # Override từ beam_params nếu người dùng đã tinh chỉnh
    if beam_params is not None:
        loai  = str(beam_params.get("loai_dam", kcn.get("loai_dam", "Dầm I")))
        H_dam = float(beam_params.get("H", kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))) / 1000.0
        kc    = float(beam_params.get("S", kcn.get("khoang_cach_dam", 2.2) * 1000)) / 1000.0
    else:
        loai  = str(kcn.get("loai_dam", "Dầm I"))
        H_dam = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
        kc    = float(kcn.get("khoang_cach_dam", 2.2))
    n_dam = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
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

    # TIM DẦM — dùng CHUNG bố trí với dầm thực & 3D (beam_centers từ mcn_beam_centers
    # đã co mép dầm biên vào trong bản). Thiếu → căn đối xứng theo kc.
    if beam_centers and len(beam_centers) == n_dam:
        _cx = list(beam_centers)
    else:
        _cx = [-(n_dam - 1) * kc / 2.0 + i * kc for i in range(n_dam)]
    x_first = _cx[0]

    # ── Bê tông đổ tại chỗ giữa các dầm (cho T ngược và Dầm I) ──────────
    is_tngược = "t ngược" in loai_l or "t-ngược" in loai_l or "tngược" in loai_l
    is_damiI  = not ("bản" in loai_l or "super" in loai_l or is_tngược)
    if is_tngược or is_damiI:
        # Vùng BT đổ tại chỗ giữa các dầm (từ đáy bản → đỉnh cánh dầm)
        # (màu nhạt hơn để phân biệt với dầm precast)
        for i in range(n_dam - 1):
            x_left  = _cx[i]
            x_right = _cx[i + 1]
            _poly(fig,
                  [x_left, x_right, x_right, x_left],
                  [-t_ban, -t_ban, -t_ban - H_dam * 0.5, -t_ban - H_dam * 0.5],
                  "rgba(200,210,200,0.45)", "rgba(127,140,141,0.3)",
                  "BT đổ tại chỗ" if i == 0 else "", showlegend=(i == 0), lw=0.5)

    # ── Độ dốc ngang mặt cầu (crown tại tim) — bản & lớp phủ dốc; ĐÁY bản cũng
    # dốc song song (bề dày bản KHÔNG đổi) → DẦM đặt thấp dần theo độ dốc.
    _i_ng = float(d.get("i_doc_ngang", 2.0)) / 100.0
    _xe   = bc / 2
    def _off(x):          # độ hạ cao độ mặt theo dốc ngang (đỉnh tại tim x=0)
        return -abs(x) * _i_ng

    # ── Lớp phủ mặt cầu — CHỈ phủ trong mép TRONG lan can; tách 2 dải nếu có dải
    #    phân cách giữa (lan can & dải PC đặt TRỰC TIẾP trên bản mặt cầu, lớp phủ
    #    ngừng tại đó). y_in = mép trong lan can; y_med = nửa bề rộng dải PC. ──
    _rails2d = _resolve_railings(d)
    _y_in, _y_med = _railing_inner_y(d, bc)
    t_btn = min(t_phu * 0.7, 0.07)

    def _phu_strip(a, b, sl):
        if b - a <= 1e-3:
            return
        xt = [a] + ([0.0] if a < 0 < b else []) + [b]   # thêm điểm tim (crown)
        _poly(fig, xt + xt[::-1],
              [t_phu + _off(x) for x in xt] +
              [t_phu - t_btn + _off(x) for x in xt[::-1]],
              "#2c3e50", "#1a252f", "BTN mặt đường" if sl else "", lw=1,
              showlegend=sl)
        _poly(fig, xt + xt[::-1],
              [t_phu - t_btn + _off(x) for x in xt] + [_off(x) for x in xt[::-1]],
              "#7f8c8d", "#566573",
              "Lớp dính bám + phòng nước" if sl else "", lw=0.8, opacity=0.7,
              showlegend=sl)

    if _y_med > 0:                       # có dải phân cách giữa → 2 dải lớp phủ
        _phu_strip(-_y_in, -_y_med, True)
        _phu_strip(_y_med, _y_in, False)
    else:
        _phu_strip(-_y_in, _y_in, True)

    # ── Bản mặt cầu BTCT ── mặt TRÊN và ĐÁY cùng dốc ngang 2% → BỀ DÀY KHÔNG ĐỔI
    #    (≥ t_ban mọi vùng). Đáy bản dốc nên dầm đặt thấp dần ra mép theo độ dốc.
    _poly(fig, [-_xe, 0, _xe, _xe, 0, -_xe],
          [_off(-_xe), 0.0, _off(_xe),
           _off(_xe) - t_ban, -t_ban, _off(-_xe) - t_ban],
          _C["ban"], _C["btong_dk"], "Bản mặt cầu BTCT")
    # Ghi chú độ dốc ngang
    fig.add_annotation(x=_xe * 0.5, y=t_phu + _off(_xe * 0.5) + 0.12,
                       text=f"i = {_i_ng*100:.1f}%", showarrow=False,
                       font=dict(size=8, color="#c0392b"))

    # ── Dầm chính: biên dạng do người dùng dựng (tab Chi tiết dầm) được chèn
    #    ở 00-Interface qua get_mcn_overlay_traces — KHÔNG vẽ dầm AI tại đây nữa.

    # ── Lan can (mặt cắt thư viện) — ĐẶT TRÊN BẢN MẶT CẦU, mặt ngoài tại ±bc/2 ──
    _lc2 = (_rails2d or {}).get("lan_can")
    if _lc2 and _lc2.get("outer"):
        _profm0 = [[p[0] / 1000.0, p[1] / 1000.0] for p in _lc2["outer"]]
        _profm, _yedge_l, _basez_l = _rail_place(_profm0, bc)  # move khối + drape ra mép
        for side in (-1, 1):
            xb = side * _xe
            _zb = _off(xb)               # đỉnh bản tại mép (chân lan can ngồi đây)
            xs = [side * (yy + _yedge_l) for yy, _ in _profm]
            zs = [_zb + zz - _basez_l for _, zz in _profm]
            _poly(fig, xs, zs, _C["lan_can"], "#2c3e50",
                  "Lan can" if side == -1 else "", showlegend=(side == -1))
    else:
        for side in [-1, 1]:            # fallback: hộp tham số cũ
            xb = side * _xe; xi = xb - side * W_lc; _e = _off(xb)
            _poly(fig, [xi, xb, xb, xi],
                  [_e, _e, _e + H_lc, _e + H_lc], _C["lan_can"], "#2c3e50",
                  "Lan can" if side == -1 else "", showlegend=(side == -1))

    # ── Giải phân cách giữa (nếu tiêu chuẩn yêu cầu) — đặt tim, trên bản mặt cầu ─
    _gpc2 = (_rails2d or {}).get("giai_phan_cach")
    if _gpc2 and _gpc2.get("outer"):
        _pg = [[p[0] / 1000.0, p[1] / 1000.0] for p in _gpc2["outer"]]
        _poly(fig, [yy for yy, _ in _pg], [zz for _, zz in _pg],
              _C["lan_can"], "#2c3e50", "Giải phân cách", showlegend=True)

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

    # ── Kết cấu bên dưới dầm: Xà mũ → Thân trụ → Bệ cọc → Cọc (MCN) ──────
    # CHỈ vẽ tại mặt cắt CÓ TRỤ (đầu dầm). MCN giữa nhịp không có trụ → bỏ toàn
    # bộ kết cấu phần dưới + các dim phần dưới (tránh "kết cấu dưới + dim thừa").
    if not show_substructure:
        z_substructure_bot = -t_ban - H_dam - 0.5
    else:
        H_tru_sub  = float(d.get("H_tru_est", 5.0))
        mong_sub   = d.get("mong_result") or {}
        D_coc_sub, L_coc_sub, _n_coc_sub = mong_dims(mong_sub)
        n_coc_sub  = max(3, _n_coc_sub)

        cap_H_sub  = 0.80
        cap_W_sub  = min(bc * 0.46, bc / 2 - 0.10)
        W_shaft_sub = max(0.80, bc * 0.065)
        be_H_sub   = 1.50
        be_W_sub   = min(cap_W_sub * 1.12, bc / 2 - 0.05)
        H_show     = min(H_tru_sub, 3.5)   # trụ cao > 3.5m → dùng ký hiệu cắt

        # MCN điển hình (đầu dầm): dầm kê vào KHẤC xà mũ → ĐỈNH xà mũ (tường tai)
        # nhô CAO HƠN đáy dầm = độ sâu khấc (theo mặt cắt xà mũ thư viện).
        h_goi_s    = _h_goi(d)
        z_dam_b_s  = float(cap_top_y) if cap_top_y is not None else (-t_ban - H_dam)
        _notch_dep_s = (_get_PB().cap_seat_notch_depth_m(pier_assembly)
                        if pier_assembly else 0.0)
        z_cap_t_s  = z_dam_b_s + _notch_dep_s      # đỉnh tường tai = đáy dầm + khấc
        r_coc_sub  = D_coc_sub / 2
        _stem_centers = []   # tâm ngang từng thân → vẽ ký hiệu cắt

        if pier_assembly:
            # TRỤ LẮP GHÉP thật (xà mũ co bề rộng cầu, thân/bệ giữ tiết diện).
            _PB = _get_PB()
            _lab = {"Xà mũ": "Xà mũ trụ", "Thân trụ": "Thân trụ (MCN)", "Bệ trụ": "Bệ cọc"}
            _polys = _PB.pier_mcn_polys(pier_assembly, z_top=z_cap_t_s,
                                        H_than=H_show, target_width=bc,
                                        seat_view=True)   # MCN đầu dầm: vẽ vai kê
            _seen = set()
            for _pl in _polys:
                _nm = _pl["name"]; _sl = _nm not in _seen; _seen.add(_nm)
                _poly(fig, _pl["xs"], _pl["ys"], _pl["color"], _C["btong_dk"],
                      _lab.get(_nm, _nm) if _sl else "", opacity=0.88, showlegend=_sl)
            _than = [pl for pl in _polys if pl["name"] == "Thân trụ"]
            _be   = [pl for pl in _polys if pl["name"] == "Bệ trụ"]
            _cap  = [pl for pl in _polys if pl["name"] == "Xà mũ"]
            z_cap_b_s = min((y for pl in _cap for y in pl["ys"]),
                            default=z_cap_t_s - cap_H_sub)
            z_sh_b_s = min((y for pl in _than for y in pl["ys"]),
                           default=z_cap_b_s - H_show)
            z_be_b_s = min((y for pl in _be for y in pl["ys"]), default=z_sh_b_s - be_H_sub)
            z_be_t_s = z_sh_b_s
            _stem_centers = [sum(pl["xs"]) / len(pl["xs"]) for pl in _than]
            _allx = [x for pl in _polys for x in pl["xs"]]
            if _allx:
                be_W_sub = max(abs(min(_allx)), abs(max(_allx)))
        else:
            z_cap_b_s = z_cap_t_s - cap_H_sub
            z_sh_b_s   = z_cap_b_s - H_show
            z_be_t_s   = z_sh_b_s
            z_be_b_s   = z_sh_b_s - be_H_sub

            # Xà mũ
            _poly(fig, [-cap_W_sub, cap_W_sub, cap_W_sub, -cap_W_sub],
                  [z_cap_b_s, z_cap_b_s, z_cap_t_s, z_cap_t_s],
                  _C["btong"], _C["dam_dk"], "Xà mũ trụ", opacity=0.85)

            # Thân trụ (2 cột)
            for xc_sh in [-cap_W_sub * 0.48, cap_W_sub * 0.48]:
                _poly(fig, [xc_sh - W_shaft_sub/2, xc_sh + W_shaft_sub/2,
                            xc_sh + W_shaft_sub/2, xc_sh - W_shaft_sub/2],
                      [z_sh_b_s, z_sh_b_s, z_cap_b_s, z_cap_b_s],
                      _C["btong"], _C["btong_dk"],
                      "Thân trụ (MCN)" if xc_sh < 0 else "", showlegend=(xc_sh < 0))
                _stem_centers.append(xc_sh)

            # Bệ cọc
            _poly(fig, [-be_W_sub, be_W_sub, be_W_sub, -be_W_sub],
                  [z_be_b_s, z_be_b_s, z_be_t_s, z_be_t_s],
                  _C["be"], _C["be_dk"], "Bệ cọc")

        # Ký hiệu cắt ngang nếu trụ cao > 3.5m (vẽ tại tâm từng thân)
        if H_tru_sub > 3.5 and _stem_centers:
            for xc_sh in _stem_centers:
                for dy_break in [0.14, 0.28]:
                    fig.add_shape(type="line",
                        x0=xc_sh - W_shaft_sub * 0.75, y0=z_sh_b_s - dy_break,
                        x1=xc_sh + W_shaft_sub * 0.75, y1=z_sh_b_s - dy_break,
                        line=dict(color=_C["btong_dk"], width=1.5))
            fig.add_annotation(x=0, y=z_sh_b_s - 0.21,
                text=f"// (H_trụ={H_tru_sub:.1f}m)",
                showarrow=False, font=dict(size=7, color=_C["dim"]),
                bgcolor="rgba(255,255,255,0.8)")

        # Cọc — MẶT ĐỨNG: lưới Module 08 (MCN = ngang cầu → n_cols cọc, tim-tim S)
        _mg_xs, _, _, _, _ = mong_pile_grid(d.get("mong_result"))
        coc_ys = list(_mg_xs)
        _z_pile_top = z_be_b_s
        _z_pile_bot = z_be_b_s - L_coc_sub
        _pile_lw    = max(3, int(D_coc_sub * 12))
        for j, yc in enumerate(coc_ys):
            fig.add_trace(go.Scatter(
                x=[yc, yc], y=[_z_pile_top, _z_pile_bot], mode="lines",
                line=dict(color=_C["be_dk"], width=_pile_lw),
                name=f"Cọc Ø{int(D_coc_sub*1000)}mm (MCN)" if j == 0 else "",
                showlegend=(j == 0), hoverinfo="skip",
            ))
        fig.add_trace(go.Scatter(
            x=list(coc_ys), y=[_z_pile_bot] * len(coc_ys), mode="markers",
            marker=dict(symbol="triangle-down", size=6, color=_C["be_dk"]),
            showlegend=False, hoverinfo="skip"))

        # Kích thước bệ cọc và khoảng cách cọc (đặt ngay dưới đáy bệ)
        _dim_h(fig, z_be_b_s - 0.35,
               -be_W_sub, be_W_sub, f"B_bệ = {be_W_sub*2:.1f}m", dy=0)
        if len(coc_ys) >= 2:
            kc_coc_show = abs(coc_ys[1] - coc_ys[0])
            _dim_h(fig, z_be_b_s - 0.90,
                   coc_ys[0], coc_ys[1], f"a_cọc={kc_coc_show:.2f}m",
                   color="#8e44ad", dy=0)
        fig.add_annotation(
            x=be_W_sub + 0.6, y=(_z_pile_top + _z_pile_bot) / 2,
            text=f"Cọc Ø{int(D_coc_sub*1000)}mm<br>L≈{L_coc_sub:.0f}m",
            showarrow=True, arrowhead=2, arrowcolor=_C["be_dk"],
            ax=40, ay=0,
            font=dict(size=7, color=_C["be_dk"]),
            bgcolor="rgba(255,255,255,0.9)",
        )
        _dim_v(fig, be_W_sub + 1.8, z_cap_b_s, z_cap_t_s,
               f"xà mũ {cap_H_sub:.2f}m", dx=0.2)
        _dim_v(fig, be_W_sub + 1.8, z_be_b_s, z_be_t_s,
               f"bệ {be_H_sub:.2f}m", dx=0.2)

        z_substructure_bot = _z_pile_bot - 1.0

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
        xaxis=dict(title="Bề rộng (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5,
                   range=[-bc/2 - 3.5, bc/2 + 5.5]),
        yaxis=dict(title="Cao độ (m)", scaleanchor="x", scaleratio=1,
                   showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5,
                   range=[z_substructure_bot, t_phu + H_lc + 0.6]),
        height=700, template="plotly_white",
        legend=dict(orientation="h", y=-0.15, font=dict(size=9)),
        margin=dict(l=70, r=80, t=90, b=100),
    )
    _add_material_notes(fig, loc="bl")
    _apply_layers_2d(fig)
    return fig



# ===========================================================================
# 3b. HELPER — Extrude profile dầm thành Mesh3D
# ===========================================================================


# ===========================================================================
# 4. MÔ HÌNH 3D — Kết cấu + địa hình (nếu có df_tim_line)
# ===========================================================================
def ve_cau_3d(d, df_tim_line=None, beam_params=None,
              pier_assembly=None, abutment_assembly=None):
    """
    Mô hình 3D kết cấu cầu với trụ đặt đúng ngoài tĩnh không.
    Nếu có df_tim_line: thêm surface địa hình dọc cầu.

    beam_params : dict | None — nếu có, ưu tiên dùng giá trị từ beam_params_final.
    """
    kcn    = d.get("kcn_result") or d.get("ai_result", {})
    geo    = d.get("geo_logic", {})

    n_nhip = int(kcn.get("tong_so_nhip", 3))
    L_nhip = float(kcn.get("chieu_dai", 40))
    n_dam  = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
    # Override từ beam_params nếu người dùng đã tinh chỉnh
    if beam_params is not None:
        H_dam  = float(beam_params.get("H", kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))) / 1000.0
        kc_dam = float(beam_params.get("S", kcn.get("khoang_cach_dam", 2.2) * 1000)) / 1000.0
    else:
        H_dam  = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
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

    # Bố trí nhịp đều theo chiều dài định hình catalog, nhịp chính căng giữa tĩnh không
    supports, L_std = resolve_supports(d, x0, x_end, x_tim, B_tk, L_nhip)
    x0, x_end = supports[0], supports[-1]
    piers    = supports[1:-1]
    n_nhip   = len(supports) - 1
    L_cau    = x_end - x0
    spans    = [(supports[i], supports[i+1]) for i in range(len(supports)-1)]

    cap_H = 0.80
    cap_W = max(2.0, bc * 0.18 + 1.0)
    be_H  = 1.50
    be_W  = cap_W + 0.8
    W_tru = 1.2
    mo_W  = 3.5

    h_goi    = _h_goi(d)                 # chiều cao gối (đáy dầm → đỉnh xà mũ)
    z_deck   = cao_dd + H_dam + t_ban
    z_dam_b  = cao_dd                     # đáy dầm (kê trên gối)
    z_cap_t  = cao_dd - h_goi             # đỉnh xà mũ = đáy dầm − gối
    z_cap_b  = z_cap_t - cap_H
    z_sh_b   = z_cap_b - H_tru
    z_be_t   = z_sh_b
    z_be_b   = z_sh_b - be_H

    traces = []

    # Gán NHÓM (legendgroup) để bật/tắt theo cụm trong 3D (click chú giải ẩn cả
    # cụm — groupclick='togglegroup'). Trả về trace/list đã gắn.
    def _g(tr, grp):
        items = tr if isinstance(tr, (list, tuple)) else [tr]
        for _t in items:
            try:
                _t.legendgroup = grp
            except Exception:
                pass
        return tr

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

                traces.append(_g(go.Surface(
                    x=x_surf, y=y_surf, z=z_surf,
                    colorscale="earth", opacity=0.70,
                    showscale=False, name="Địa hình (khảo sát)",
                    hovertemplate="Lý trình: %{x:.1f}m<br>Cao độ: %{z:.3f}m<extra>Địa hình</extra>"
                ), "Địa hình"))
    else:
        # Không có khảo sát: hiển thị mực nước phẳng
        mg_3d = 20
        x_rng = [x0-mg_3d, x_end+mg_3d]
        y_rng = [-bc*1.5, bc*1.5]
        traces.append(_g(go.Surface(
            x=[[x_rng[0], x_rng[1]],[x_rng[0], x_rng[1]]],
            y=[[y_rng[0], y_rng[0]],[y_rng[1], y_rng[1]]],
            z=[[MNCN, MNCN],[MNCN, MNCN]],
            colorscale=[[0, "rgba(52,152,219,0.45)"], [1, "rgba(52,152,219,0.45)"]],
            showscale=False, opacity=0.45, name="Mặt nước (MNCN)",
        ), "Mặt nước"))

    # ── Mố ────────────────────────────────────────────────────────────────
    #   x_face = lý trình mặt trước (đỡ gối); out_dir = hướng RA sau lưng.
    for _im, (x_face, out_dir, nm, xm) in enumerate(
            [(x0, -1.0, "Mố trái", x0-mo_W), (x_end, 1.0, "Mố phải", x_end)]):
        # Cọc khai báo từ DXF (nếu có) — đặt tại tâm bệ mố
        _piles_mo3d = _layout_piles(d, "mo_trai" if _im == 0 else "mo_phai")
        if _piles_mo3d:
            traces.extend(_g(_pile_traces_3d(
                _piles_mo3d, x_center=xm + mo_W/2, y_center=0.0,
                z_top=z_be_b, color="#7d5a32",
                legend_name=(f"Cọc mố ({len(_piles_mo3d)})" if _im == 0 else None)),
                "Cọc"))
        if abutment_assembly:
            _PB = _get_PB()
            # Đỉnh mố (vai kê gối) = ĐÁY DẦM (z_cap_t = cao_dd).
            for _at in _PB.build_abutment_mesh_traces(
                    abutment_assembly, H_tru=(z_cap_t - z_be_b),
                    x_face=x_face, out_dir=out_dir, z_base=z_be_b):
                _at.showlegend = bool(_im == 0)
                traces.append(_g(_at, "Mố"))
            continue
        traces.append(_g(_box3d(xm, -bc/2-0.5, z_be_b, xm+mo_W, bc/2+0.5, z_deck,
                             color="#c0a06b", name=nm), "Mố"))

    # ── Đường đầu cầu: nền đắp + mặt đường vươn 50m mỗi bên ──────────────────
    _L_app3d = 50.0
    for _xm, _od in [(x0, -1.0), (x_end, 1.0)]:
        for _at in _approach_road_traces(
                _xm, _xm + _od * _L_app3d, bc, z_deck, h_tn, taluy=1.5,
                sl=(_od < 0)):
            traces.append(_g(_at, "Đường đầu cầu"))

    # ── Trụ (đặt NGOÀI tĩnh không) ────────────────────────────────────────
    for i, xt in enumerate(piers):
        sl = (i == 0)
        # Cọc khai báo từ DXF (nếu có) — đặt tại tâm bệ trụ
        _piles_tru3d = _layout_piles(d, f"tru_{i+1}")
        if _piles_tru3d:
            traces.extend(_g(_pile_traces_3d(
                _piles_tru3d, x_center=xt, y_center=0.0,
                z_top=z_be_b, color="#566573",
                legend_name=(f"Cọc trụ ({len(_piles_tru3d)})" if sl else None)),
                "Cọc"))
        # TRỤ: CHỈ dùng mô hình lắp ghép (xà mũ/thân/bệ) người dùng đã tạo.
        _ptr = []
        if pier_assembly:
            _PB = _get_PB()
            _ptr = _PB.build_pier_mesh_traces(
                pier_assembly, H_tru=(z_cap_t - z_be_b),
                x_ctr=xt, z_base=z_be_b, cap_width=bc)
        if _ptr:
            for _pt in _ptr:
                _pt.showlegend = bool(sl)   # chỉ chú giải ở trụ đầu
                traces.append(_g(_pt, "Trụ"))
        else:
            # Chưa gắn mô hình trụ → khối MỜ TẠM (không phải trụ tham số "giả").
            traces.append(_g(_box3d(
                xt - 1.0, -1.0, z_be_b, xt + 1.0, 1.0, z_cap_t,
                color="#7f8c8d", opacity=0.22,
                name="Trụ (chưa gắn mô hình)" if sl else "", sl=sl), "Trụ"))

    # ── Dầm chính: mô hình 3D do người dùng dựng (tab Chi tiết dầm) được chèn
    #    ở 00-Interface qua get_beam_model_mesh_traces — KHÔNG vẽ dầm AI tại đây.

    # ── Bản mặt cầu ───────────────────────────────────────────────────────
    for i_nhip, (xs, xe) in enumerate(spans):
        sl = (i_nhip == 0)
        traces.append(_g(_box3d(xs, -bc/2, cao_dd+H_dam, xe, bc/2, z_deck,
                             color="#e8eaf0", opacity=0.55,
                             name="Bản mặt cầu" if sl else "", sl=sl), "Bản mặt cầu"))

    # ── Lan can / Giải phân cách — kéo MCN chạy dọc toàn cầu + ra hết tường cánh mố ─
    try:
        _wd = _abut_long_depth_m(abutment_assembly)
        traces.extend(_g(_railing_traces_3d(d, x0 - _wd, x_end + _wd, bc, z_deck), "Lan can"))
    except Exception as _e:
        print(f"[ve_cau_3d] lan can lỗi: {_e}")

    # ── GỐI cầu tại mỗi vị trí đỡ (đáy dầm kê trên gối, trên đỉnh xà mũ) ───
    if h_goi > 0:
        for _is, _xs in enumerate(supports):
            traces.append(_g(_box3d(
                _xs - 0.30, -bc/2 + 0.4, z_cap_t, _xs + 0.30, bc/2 - 0.4, z_dam_b,
                color="#2c3e50", opacity=1.0,
                name="Gối cầu" if _is == 0 else "", sl=(_is == 0)), "Gối"))

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
            legendgroup="Tĩnh không",
        ))

    # Tĩnh không PHỤ (khung cam) — khai báo ở hộp thoại thủy văn
    _tkp_sl3 = True
    for _cx in (d.get("extra_clearances") or []):
        try:
            _xk = float(_cx.get("x")); _Bk = float(_cx.get("B", 0) or 0)
            _Hk = float(_cx.get("H", 0) or 0); _zk = float(_cx.get("z", MNCN))
        except (TypeError, ValueError):
            continue
        if _Bk <= 0 or _Hk <= 0:
            continue
        _gk = float(_cx.get("goc", 90) or 90)
        _cotk = (0.0 if _gk >= 89.9 or _gk <= 0
                 else 1.0 / np.tan(np.radians(max(10.0, min(89.9, _gk)))))
        _xkL = _xk - _Bk/2; _xkR = _xk + _Bk/2
        for _y in y_tk:
            _dx = _y * _cotk        # xiên theo góc giao với tim tuyến
            fig.add_trace(go.Scatter3d(
                x=[_xkL+_dx, _xkR+_dx, _xkR+_dx, _xkL+_dx, _xkL+_dx], y=[_y]*5,
                z=[_zk, _zk, _zk+_Hk, _zk+_Hk, _zk],
                mode="lines", line=dict(color="#e67e22", width=3),
                name="Tĩnh không phụ" if (_tkp_sl3 and _y == y_tk[0]) else "",
                showlegend=(_tkp_sl3 and _y == y_tk[0]),
                legendgroup="Tĩnh không phụ",
            ))
        _tkp_sl3 = False

    # Đường bao cấu kiện (viền tối các hộp) → dễ nhìn ranh giới
    _add_box_outlines(fig)
    _hover3d(fig)   # hover: tên cấu kiện + cao độ

    fig.update_layout(
        title=dict(
            text=f"MÔ HÌNH 3D CẦU — {n_nhip} NHỊP | L={L_cau:.1f}m | B={bc}m",
            x=0.5, font=dict(size=13)
        ),
        scene=dict(
            xaxis=dict(title="Lý trình (m)", backgroundcolor="rgba(0,0,0,0)",
                       gridcolor="rgba(128,128,128,0.35)", showbackground=True),
            yaxis=dict(title="Ngang cầu (m)", backgroundcolor="rgba(0,0,0,0)",
                       gridcolor="rgba(128,128,128,0.35)", showbackground=True),
            zaxis=dict(title="Cao độ (m)", backgroundcolor="rgba(0,0,0,0)",
                       gridcolor="rgba(128,128,128,0.35)", showbackground=True),
            aspectmode="data",
            camera=dict(eye=dict(x=1.4, y=-1.8, z=0.8)),
            bgcolor="white",
        ),
        height=640,
        # Click nhóm trong chú giải → ẩn/hiện CẢ CỤM cấu kiện (groupclick).
        legend=dict(orientation="h", y=-0.06, font=dict(size=9),
                    groupclick="togglegroup",
                    title=dict(text="Bấm để ẩn/hiện cấu kiện ▾", font=dict(size=9))),
        margin=dict(l=0, r=0, t=60, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
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

        L_nhip = float(kcn.get("chieu_dai", 33.0) or 33.0)
        supports, L_std = resolve_supports(d, x0, x_end, x_tim, B_tk, L_nhip)
        x0, x_end = supports[0], supports[-1]
        piers = supports[1:-1]
        n_nhip = len(supports) - 1

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
        D_coc, L_coc, _ = mong_dims(mong_r)

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

        # Origin = tim tuyến VN-2000 tại lý trình NHỎ NHẤT — TRÙNG với origin mà
        # ve_dia_hinh_3d đã trừ (terrain_x_origin/y_origin). Bắt buộc trừ origin
        # để kết cấu cầu nằm CÙNG hệ toạ độ gần-0 với địa hình (nếu để VN-2000
        # thô ~600.000m thì auto-range nổ tung, không zoom vào được).
        _i0   = int(np.argmin(lt_v))
        x_org = float(vx_v[_i0]); y_org = float(vy_v[_i0])

        # ── Góc xiên (góc giao) → hệ số trượt theo lý trình ────────────────
        # Cắt xiên = TRƯỢT dọc tim tuyến: điểm ở offset `off` dịch lý trình một
        # lượng off·cot(α) (α=góc giao). Tim cầu (off=0) GIỮ NGUYÊN trên tuyến →
        # cầu không văng ra ngoài; mố/trụ/đầu bản nghiêng đúng phương xiên.
        try:
            _goc_sk = float(d.get("goc_giao", 90.0))
        except Exception:
            _goc_sk = 90.0
        _cot = (0.0 if _goc_sk >= 89.9 or _goc_sk <= 0
                else 1.0 / np.tan(np.radians(max(30.0, min(89.9, _goc_sk)))))

        def _at(s):
            return (float(np.interp(s, lt_v, vx_v)),
                    float(np.interp(s, lt_v, vy_v)),
                    float(np.interp(s, lt_v, goc_v)),
                    float(np.interp(s, lt_v, vz_v)))

        def _vn(s, off=0.0, skew=True):
            s_eff = (s + off * _cot) if skew else s     # trượt lý trình theo góc xiên
            xc, yc, goc, _ = _at(s_eff)
            perp = goc + np.pi / 2
            return (xc + off * np.cos(perp) - x_org,
                    yc + off * np.sin(perp) - y_org)

        hz = he_so_z

        # ── ĐƯỜNG ĐỎ DÙNG CHUNG với trắc dọc 2D (make_red_line) → 3D & trắc dọc
        #    CÙNG một biên dạng cao độ; trắc dọc 2D là "lát cắt" đúng của 3D. ────
        _zred_fn, _, _zcrown, _tban_rl, _Hdam_rl = make_red_line(d)
        cao_dd = _zcrown - t_ban - H_dam          # đáy dầm tại đỉnh (bám đường đỏ)

        def _prof(s):
            """Độ lệch cao độ đường đỏ so với đỉnh (×hz) — quét bản/dầm theo trắc dọc."""
            return (_zred_fn(s) - _zcrown) * hz

        _be3d_snap = {}   # {round(xt,3): đỉnh bệ ĐỒNG BỘ} — nạp sau khi có piers
        def _pier_found(xt):
            """Cao độ móng trụ THEO ĐỊA HÌNH TỪNG TRỤ (khớp trắc dọc) — real units.
            Trả (đáy_dầm, đỉnh_bệ, đáy_bệ). Đỉnh bệ chôn 0.5m dưới ĐTN tại trụ, ĐÃ
            đồng bộ về cao độ chẵn nếu các trụ chênh ≤ 1m (_be3d_snap)."""
            _soffit = _zred_fn(xt) - t_ban - H_dam       # đáy dầm (vai kê) tại trụ
            _zt     = float(np.interp(xt, lt_v, vz_v))   # cao độ ĐTN tại trụ
            _be_top = min(_zt - 0.5, _soffit - 1.0)      # đỉnh bệ (chừa tối thiểu thân)
            _be_top = min(_be3d_snap.get(round(xt, 3), _be_top), _soffit - 1.0)
            return _soffit, _be_top, _be_top - 1.50      # đáy bệ = đỉnh bệ − 1.5m

        # ── Cao độ × he_so_z (mốc tại ĐỈNH đường cong; theo trạm cộng _prof) ────
        z_phu  = (cao_dd + H_dam + t_ban + t_phu) * hz
        z_deck = (cao_dd + H_dam + t_ban) * hz    # = _zcrown*hz
        z_bant = (cao_dd + H_dam) * hz
        z_beamb = cao_dd * hz
        z_capt = (cao_dd - H_DA_KE_GOI) * hz      # đỉnh xà mũ = đáy dầm − 150mm
        z_capb = (cao_dd - H_DA_KE_GOI - 0.80) * hz
        z_sht  = z_capb
        z_shb  = (cao_dd - H_DA_KE_GOI - 0.80 - H_tru) * hz
        z_bet  = z_shb
        z_beb  = (cao_dd - H_DA_KE_GOI - 0.80 - H_tru - 1.50) * hz
        z_pileb = z_beb - L_coc * hz

        cap_W     = max(2.0, bc * 0.18 + 1.0)
        be_W      = cap_W + 0.8
        W_tru     = 1.2
        W_cot     = min(1.0, bc * 0.06 + 0.4)
        cap_thick = 0.4
        be_long   = be_W * 0.7
        mo_L      = 3.5
        # KÍCH THƯỚC BỆ THẬT từ Module 08 (Be_ngang × Be_doc, TCVN 10304:2025)
        # — ưu tiên hơn heuristic theo bề rộng cầu (be_W dùng nửa-bề-rộng).
        if float(mong_r.get("Be_ngang") or 0) > 0:
            be_W = max(be_W, float(mong_r["Be_ngang"]) / 2.0)
        if float(mong_r.get("Be_doc") or 0) > 0:
            be_long = float(mong_r["Be_doc"]) / 2.0

        supports, L_std = resolve_supports(d, x0, x_end, x_tim, B_tk, L_nhip)
        x0, x_end = supports[0], supports[-1]
        piers    = supports[1:-1]
        n_nhip   = len(supports) - 1
        # ĐỈNH BỆ DÙNG CHUNG với trắc dọc & mặt cắt chi tiết (_pier_be_tops_synced).
        _be3d_snap.update(_pier_be_tops_synced(
            piers,
            lambda xt: float(np.interp(xt, lt_v, vz_v)),
            lambda xt: _zred_fn(xt) - t_ban - H_dam))
        L_cau    = x_end - x0
        spans    = [(supports[i], supports[i+1]) for i in range(len(supports)-1)]

        # ── Helper: HỘP 3D căn theo tim tuyến VN-2000 ────────────────────
        # Cùng logic _box3d nhưng XY lấy từ _vn(lý_trình, offset_ngang)
        def _abox(s0, s1, oL, oR, zb, zt, color, opacity=0.88, name="", sl=True,
                  skew=True):
            c = [_vn(s0, oL, skew), _vn(s0, oR, skew),
                 _vn(s1, oR, skew), _vn(s1, oL, skew)]
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

        def _aswept(s0, s1, oL, oR, zb, zt, color, opacity=0.88,
                    name="", sl=True, step=5.0, skew=True, zbR=None, ztR=None,
                    dz_fn=None):
            """Tấm 3D (lớp phủ / bản mặt cầu) QUÉT dọc tim tuyến — chia nhỏ theo
            lý trình để bám đúng đường cong, thay cho hộp thẳng nối đầu–cuối.
            zbR/ztR: cao độ đáy/đỉnh tại mép PHẢI (oR) — khác mép trái để tạo DỐC
            NGANG (crown); mặc định None = phẳng (= zb/zt).
            dz_fn(s): độ lệch cao độ theo lý trình (bám TRẮC DỌC / đường đỏ)."""
            _zbR = zb if zbR is None else zbR
            _ztR = zt if ztR is None else ztR
            m  = max(2, int(abs(s1 - s0) / step))
            ss = np.linspace(s0, s1, m + 1)
            vx, vy, vz = [], [], []
            for s in ss:
                xL, yL = _vn(s, oL, skew)
                xR, yR = _vn(s, oR, skew)
                _ds = dz_fn(s) if dz_fn else 0.0
                vx += [xL, xR, xL, xR]
                vy += [yL, yR, yL, yR]
                vz += [zb+_ds, _zbR+_ds, zt+_ds, _ztR+_ds]  # 0=Lđáy 1=Rđáy 2=Lđỉnh 3=Rđỉnh
            ii, jj, kk = [], [], []
            def _q(a, b, c, dd):
                ii.append(a); jj.append(b); kk.append(c)
                ii.append(a); jj.append(c); kk.append(dd)
            for i in range(m):
                b0, b1 = 4 * i, 4 * (i + 1)
                _q(b0+2, b0+3, b1+3, b1+2)   # mặt trên
                _q(b0+0, b1+0, b1+1, b0+1)   # mặt dưới
                _q(b0+0, b0+2, b1+2, b1+0)   # vách trái
                _q(b0+1, b1+1, b1+3, b0+3)   # vách phải
            _q(0, 1, 3, 2)                    # bịt đầu
            _last = 4 * m
            _q(_last, _last+2, _last+3, _last+1)  # bịt cuối
            return go.Mesh3d(
                x=vx, y=vy, z=vz, i=ii, j=jj, k=kk,
                color=color, opacity=opacity, flatshading=True,
                name=name, showlegend=sl and bool(name),
                lighting=dict(ambient=0.65, diffuse=0.85, specular=0.2),
                hovertemplate=f"<b>{name}</b><extra></extra>" if name else None,
            )

        # Gán nhóm + thêm trace; click chú giải ẩn/hiện cả cụm (groupclick).
        _grp_state = {"g": None}
        def _ag(tr):
            if _grp_state["g"]:
                try:
                    tr.legendgroup = _grp_state["g"]
                except Exception:
                    pass
            fig.add_trace(tr)

        # =========================================================
        # LỚP 1 — THỦY VĂN & TĨNH KHÔNG
        # =========================================================
        # Mực nước chỉ hiển thị cục bộ tại vị trí khung tĩnh không
        yw_local = B_tk * 1.2          # độ rộng ngang (vuông góc tim)
        xL_water = x_tim - B_tk / 2   # giới hạn dọc = chiều rộng TK
        xR_water = x_tim + B_tk / 2
        _grp_state["g"] = "Mặt nước"
        for z_w, lbl, clr, op in [
            (MNCN * hz, f"MNCN = {MNCN:.3f}m", "#2980b9", 0.50),
            (MNTT * hz, f"MNTT = {MNTT:.3f}m", "#3498db", 0.35),
            (MNTN * hz, f"MNTN = {MNTN:.3f}m", "#1abc9c", 0.25),
        ]:
            _ag(_abox(xL_water, xR_water, -yw_local, yw_local,
                                z_w - 0.05 * hz, z_w, clr, op, lbl, skew=False))

        # Khung tĩnh không B×H (dây đỏ) — bề rộng B_tk VUÔNG GÓC SÔNG; sông cắt
        # tuyến theo GÓC GIAO nên khung XIÊN theo góc như mố/trụ/mặt cầu (góc=90°
        # → dọc tuyến như cũ). Hướng sông = hướng trụ xiên (_vn tại tim, off 0→1).
        _grp_state["g"] = "Tĩnh không"
        _ck0 = _vn(x_tim, 0.0); _ck1 = _vn(x_tim, 1.0)
        _rvx = _ck1[0] - _ck0[0]; _rvy = _ck1[1] - _ck0[1]
        _rvn = (_rvx * _rvx + _rvy * _rvy) ** 0.5 or 1.0
        _pux = -_rvy / _rvn; _puy = _rvx / _rvn      # vuông góc sông = hướng B_tk
        xrL = _ck0[0] - _pux * (B_tk / 2); yrL = _ck0[1] - _puy * (B_tk / 2)
        xrR = _ck0[0] + _pux * (B_tk / 2); yrR = _ck0[1] + _puy * (B_tk / 2)
        z_tkb = MNCN * hz; z_tkt = (MNCN + H_tk) * hz
        for xs, ys, xe, ye, z0, z1, nm in [
            (xrL,yrL, xrR,yrR, z_tkb,z_tkb, "Đáy TK"),
            (xrL,yrL, xrR,yrR, z_tkt,z_tkt, "Đỉnh TK"),
            (xrL,yrL, xrL,yrL, z_tkb,z_tkt, "Cột trái TK"),
            (xrR,yrR, xrR,yrR, z_tkb,z_tkt, "Cột phải TK"),
        ]:
            _ag(go.Scatter3d(
                x=[xs,xe], y=[ys,ye], z=[z0,z1],
                mode="lines+markers",
                line=dict(color="#e74c3c", width=6),
                marker=dict(size=5, color="#e74c3c"),
                name=nm, showlegend=(nm == "Đáy TK"),
            ))
        _ag(go.Scatter3d(
            x=[(xrL+xrR)/2], y=[(yrL+yrR)/2], z=[(z_tkb+z_tkt)/2],
            mode="text", text=[f"B={B_tk}m × H={H_tk}m"],
            textfont=dict(color="#e74c3c", size=11), showlegend=False,
        ))

        # Tĩnh không PHỤ (khai báo trong hộp thoại thủy văn) — khung cam
        _tkp_sl = True
        for _cx in (d.get("extra_clearances") or []):
            try:
                _xk = float(_cx.get("x")); _Bk = float(_cx.get("B", 0) or 0)
                _Hk = float(_cx.get("H", 0) or 0); _zk = float(_cx.get("z", MNCN))
            except (TypeError, ValueError):
                continue
            if _Bk <= 0 or _Hk <= 0:
                continue
            _nmk = str(_cx.get("ten") or "TK phụ")
            _pxL, _pyL = _vn(_xk - _Bk/2, 0); _pxR, _pyR = _vn(_xk + _Bk/2, 0)
            _zkb = _zk * hz; _zkt = (_zk + _Hk) * hz
            for xs, ys, xe, ye, z0, z1 in [
                (_pxL,_pyL, _pxR,_pyR, _zkb,_zkb), (_pxL,_pyL, _pxR,_pyR, _zkt,_zkt),
                (_pxL,_pyL, _pxL,_pyL, _zkb,_zkt), (_pxR,_pyR, _pxR,_pyR, _zkb,_zkt),
            ]:
                _ag(go.Scatter3d(
                    x=[xs,xe], y=[ys,ye], z=[z0,z1], mode="lines",
                    line=dict(color="#e67e22", width=5),
                    name="Tĩnh không phụ" if _tkp_sl else "", showlegend=_tkp_sl))
                _tkp_sl = False
            _ag(go.Scatter3d(
                x=[(_pxL+_pxR)/2], y=[(_pyL+_pyR)/2], z=[(_zkb+_zkt)/2],
                mode="text", text=[f"{_nmk}<br>B={_Bk:.1f}×H={_Hk:.1f}m"],
                textfont=dict(color="#e67e22", size=9), showlegend=False))

        # =========================================================
        # LỚP 2 — TRẮC DỌC (đường line — đúng cho profile)
        # =========================================================
        s_range = np.linspace(lt_v[0], lt_v[-1], 100)
        XP, YP, ZP = [], [], []
        for s in s_range:
            xc, yc = _vn(s, 0)
            XP.append(xc); YP.append(yc)
            ZP.append(float(np.interp(s, lt_v, vz_v)) * hz)
        _grp_state["g"] = "Trắc dọc"
        _ag(go.Scatter3d(x=XP, y=YP, z=ZP, mode="lines",
                                   line=dict(color="#27ae60", width=4),
                                   name="Địa hình TN tim tuyến"))

        # Đường đỏ thiết kế = make_red_line (CÙNG với trắc dọc 2D) — kéo hết
        # đường đầu cầu 2 đầu.
        _L_app3d_red = max(12.0, L_cau * 0.15)
        XRD, YRD, ZRD = [], [], []
        for s in np.linspace(x0 - _L_app3d_red, x_end + _L_app3d_red, 90):
            xc, yc = _vn(s, 0)
            XRD.append(xc); YRD.append(yc); ZRD.append(_zred_fn(s) * hz)
        _ag(go.Scatter3d(x=XRD, y=YRD, z=ZRD, mode="lines",
                                   line=dict(color="#e74c3c", width=5),
                                   name="Đường đỏ thiết kế"))

        # =========================================================
        # LỚP 3 — KẾT CẤU NHỊP (Mesh3d KHỐI 3D)
        # =========================================================

        # Bản mặt cầu (full bề rộng) + Lớp phủ BTN. Lớp phủ CHỈ phủ trong khoảng
        # mép TRONG lan can; nếu có dải phân cách giữa thì tách 2 dải (lan can &
        # dải PC đặt TRỰC TIẾP trên bản mặt cầu, lớp phủ ngừng tại đó).
        _grp_state["g"] = "Mặt cầu"
        # ĐỘ DỐC NGANG (đồng bộ MCN): crown tại tim, hạ ra mép. _dz = độ hạ cao độ
        # (đã ×hz) theo offset ngang. Bản & lớp phủ tách tại tim để tạo mái crown.
        _i_ng3d = float(d.get("i_doc_ngang", 2.0)) / 100.0
        def _dz(o):
            return -abs(o) * _i_ng3d * hz
        # Bản mặt cầu — 2 mái dốc từ tim ra 2 mép (crown), QUÉT bám ĐƯỜNG ĐỎ (_prof).
        _ag(_aswept(x0, x_end, -bc/2, 0.0,
                    z_bant + _dz(-bc/2), z_deck + _dz(-bc/2), "#d5d8dc", 0.82,
                    "Bản mặt cầu", zbR=z_bant, ztR=z_deck, dz_fn=_prof))
        _ag(_aswept(x0, x_end, 0.0, bc/2,
                    z_bant, z_deck, "#d5d8dc", 0.82, "", sl=False,
                    zbR=z_bant + _dz(bc/2), ztR=z_deck + _dz(bc/2), dz_fn=_prof))
        _y_in, _y_med = _railing_inner_y(d, bc)
        if _y_med > 0:                     # có dải phân cách giữa → lớp phủ 2 bên
            _ag(_aswept(x0, x_end, -_y_in, -_y_med,
                        z_deck + _dz(-_y_in), z_phu + _dz(-_y_in), "#2c3e50", 0.92,
                        "Lớp phủ BTN", zbR=z_deck + _dz(-_y_med),
                        ztR=z_phu + _dz(-_y_med), dz_fn=_prof))
            _ag(_aswept(x0, x_end, _y_med, _y_in,
                        z_deck + _dz(_y_med), z_phu + _dz(_y_med), "#2c3e50", 0.92,
                        "", sl=False, zbR=z_deck + _dz(_y_in),
                        ztR=z_phu + _dz(_y_in), dz_fn=_prof))
        else:                              # phủ suốt → tách tại tim tạo crown
            _ag(_aswept(x0, x_end, -_y_in, 0.0,
                        z_deck + _dz(-_y_in), z_phu + _dz(-_y_in), "#2c3e50", 0.92,
                        "Lớp phủ BTN", zbR=z_deck, ztR=z_phu, dz_fn=_prof))
            _ag(_aswept(x0, x_end, 0.0, _y_in,
                        z_deck, z_phu, "#2c3e50", 0.92, "", sl=False,
                        zbR=z_deck + _dz(_y_in), ztR=z_phu + _dz(_y_in), dz_fn=_prof))

        # Lan can / Giải phân cách — ĐẶT TRÊN BẢN MẶT CẦU (z_deck), không trên lớp
        # phủ. KÉO DÀI ra hết tường cánh mố 2 đầu (theo chiều dọc mố).
        _grp_state["g"] = "Lan can"
        _wd = _abut_long_depth_m(d.get("_mo_model"))
        _z_edge = z_deck + _dz(bc/2)          # mép bản đã hạ theo dốc ngang
        try:
            # dz_fn=_prof → lan can BÁM ĐƯỜNG ĐỎ (trắc dọc) theo từng lý trình.
            for _rt in _railing_curve_traces(d, _vn, x0 - _wd, x_end + _wd, bc,
                                             _z_edge, dz_fn=_prof):
                _ag(_rt)
        except Exception as _e:
            print(f"[add_all] lan can lỗi: {_e}")

        # Dầm chính: mô hình 3D do người dùng dựng (tab Chi tiết dầm) được chèn
        # ở 00-Interface qua get_beam_model_mesh_traces — KHÔNG vẽ dầm AI tại đây.

        # =========================================================
        # LỚP 4 — TRỤ CẦU (Mesh3d KHỐI 3D)
        # =========================================================

        # TRỤ LẮP GHÉP thật (mặc định 2 thân SPT, từ d["_pier_model"]) — thay
        # KHỐI TRỤ CŨ. Dựng mesh trong hệ cục bộ (x=dọc, y=ngang, z=cao) rồi NẮN
        # về hệ địa hình VN-2000 qua _vn (bám cong tuyến) + nhân hz cho trục cao.
        _pier_model = d.get("_pier_model")
        _PBp = _get_PB()
        if _pier_model:
            # Dầm vẽ ĐẦY ĐỦ, đáy dầm = VAI KÊ; build_pier neo ĐỈNH ụ giữa =
            # z_base+H_total, vai kê = đỉnh ụ − khấc → để VAI KÊ = đáy dầm thì đỉnh
            # ụ giữa = đáy dầm + khấc (ụ nhô lên đỡ bản).
            try:
                _notch3d = _PBp.cap_seat_notch_depth_m(_pier_model) or 0.0
            except Exception:
                _notch3d = 0.0
            _wmap3d = (d or {}).get("_pier_cap_widen") or {}
            _w03d = float((d or {}).get("_pier_cap_W0", 0) or 0)
            for i_p, xt in enumerate(piers):
                sl = (i_p == 0)
                # THÂN TRỤ KÉO GIÃN theo ĐỊA HÌNH TỪNG TRỤ (khớp trắc dọc):
                #  • ĐỈNH Ụ GIỮA xà mũ = ĐÁY BẢN (đỡ bản mặt cầu); vai kê 2 bên thấp
                #    hơn (đỡ khấc dầm) do khấc trong model.
                #  • Đỉnh bệ chôn 0.5m dưới ĐTN tại trụ; đáy bệ = đỉnh bệ − 1.5m.
                #  • Chiều cao thân trụ tự co để nối đáy bệ ↔ đỉnh ụ (build_pier).
                _soffit_i, _z_be_top_i, _z_be_bot_i = _pier_found(xt)
                _anchor_top  = _soffit_i + H_dam                  # đỉnh ụ giữa = đáy bản
                _H_total_i   = _anchor_top - _z_be_bot_i          # đáy bệ → đỉnh ụ
                # Xà mũ NỚI RỘNG cho nhịp SPT vượt tĩnh không (ụ giữa to hơn W0).
                _mid_extra_3d = max(0.0, _wmap3d.get(round(xt, 3), _w03d) - _w03d)
                try:
                    _ptr = _PBp.build_pier_mesh_traces(
                        _pier_model, H_tru=_H_total_i, x_ctr=xt,
                        z_base=_z_be_bot_i, cap_width=bc,
                        cap_mid_extra=_mid_extra_3d)
                except Exception as _pe:
                    print(f"[add_all] trụ lắp ghép lỗi: {_pe}")
                    _ptr = []
                for _tr in _ptr:
                    _nm = str(getattr(_tr, "name", "") or "")
                    try:
                        _nx, _ny = [], []
                        for _vx, _vy in zip(list(_tr.x), list(_tr.y)):
                            _gx, _gy = _vn(_vx, _vy)
                            _nx.append(_gx); _ny.append(_gy)
                        _tr.x = _nx; _tr.y = _ny
                        _tr.z = [_vz * hz for _vz in list(_tr.z)]
                        # Nhóm chú giải: bệ → "Bệ cọc", còn lại → "Trụ"
                        _tr.legendgroup = "Bệ cọc" if "Bệ" in _nm else "Trụ"
                        _tr.showlegend = bool(sl and _nm)
                    except Exception:
                        pass
                    fig.add_trace(_tr)
        else:
            # Fallback: KHỐI TRỤ CŨ (chỉ khi chưa resolve được trụ lắp ghép).
            _grp_state["g"] = "Trụ"
            for i_p, xt in enumerate(piers):
                sl = (i_p == 0)
                _ag(_abox(xt-cap_thick, xt+cap_thick, -cap_W, cap_W,
                                    z_capb, z_capt, "#d5dbdb", 0.90,
                                    "Xà mũ" if sl else "", sl=sl))
                col_offs = np.linspace(-cap_W*0.6, cap_W*0.6, n_cot)
                for i_c, off_c in enumerate(col_offs):
                    _ag(_abox(
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

            # Bệ cọc (hộp) — CHỈ vẽ khi KHÔNG dùng trụ lắp ghép (trụ lắp ghép đã
            # gồm bệ thật) → tránh vẽ trùng bệ.
            if not _pier_model:
                _grp_state["g"] = "Bệ cọc"
                _ag(_abox(xt-be_long, xt+be_long, -be_W, be_W,
                                    z_beb, z_bet, "#aab7b8", 0.90,
                                    "Bệ cọc" if sl else "", sl=sl))

            # Cọc (line) — ĐỈNH CỌC bám ĐÁY BỆ theo địa hình từng trụ (khớp trắc dọc)
            _grp_state["g"] = "Cọc"
            if _pier_model:
                _, _, _z_be_bot_p = _pier_found(xt)
                _z_coc_top = _z_be_bot_p * hz
            else:
                _z_coc_top = z_bet
            _z_coc_bot = _z_coc_top - L_coc * hz
            # Bố trí cọc CHÍNH XÁC theo Module 08 (TCVN 10304:2025): lưới
            # n_cols × n_rows với tim-tim khoang_cach_tim, căn tâm bệ. Thiếu
            # thông số (dữ liệu cũ) → heuristic trải đều theo bề bệ như trước.
            _S_coc = float(mong_r.get("khoang_cach_tim")
                           or mong_r.get("khoang_cach_tim_coc") or 0)
            _nc_be = int(mong_r.get("n_cols_be") or 0)
            _nr_be = int(mong_r.get("n_rows_be") or 0)
            if _S_coc > 0 and _nc_be >= 1 and _nr_be >= 1:
                c_ds = [(_c - (_nc_be - 1) / 2.0) * _S_coc
                        for _c in range(_nc_be)]           # ngang cầu
                c_ls = [(_r - (_nr_be - 1) / 2.0) * _S_coc
                        for _r in range(_nr_be)]           # dọc cầu
            else:
                c_ds = np.linspace(-be_W*0.65, be_W*0.65, n_coc_row)
                c_ls = np.linspace(-be_long*0.65, be_long*0.65, n_coc_row)
            for dl in c_ls:
                for dt in c_ds:
                    xp, yp = _vn(xt + dl, dt)
                    lbl_coc = (f"Cọc Ø{int(D_coc*1000)}mm L={L_coc:.0f}m"
                               if (sl and dl == c_ls[0] and dt == c_ds[0]) else "")
                    _ag(go.Scatter3d(
                        x=[xp, xp], y=[yp, yp], z=[_z_coc_top, _z_coc_bot],
                        mode="lines",
                        line=dict(color="#4a4a4a", width=5),
                        name=lbl_coc,
                        showlegend=bool(lbl_coc),
                    ))

        # =========================================================
        # LỚP 6 — MỐ HAI ĐẦU (Mesh3d KHỐI 3D)
        # =========================================================

        # MỐ LẮP GHÉP thật (mặc định "Mố chữ U" từ d["_mo_model"]) — thay khối mố
        # hộp cũ. Đáy mố chôn 0.5m dưới ĐTN tại mố; đỉnh = đáy dầm; out_dir=±1
        # để mặt trước quay vào nhịp. Nắn về hệ địa hình qua _vn + nhân hz.
        _grp_state["g"] = "Mố"
        _mo_model = d.get("_mo_model")
        _PBm2 = _get_PB()
        for xm, nm, sgn in [(x0, "Mố trái", 1), (x_end, "Mố phải", -1)]:
            sl = (nm == "Mố trái")
            if _mo_model:
                _zt_mo    = float(np.interp(xm, lt_v, vz_v))   # ĐTN tại mố
                _zbase_mo = _zt_mo - 0.5
                # Đáy dầm PHÍA MỐ = đáy dầm − độ sâu khấc (đầu dầm lên mố đầu trơn).
                # Bám ĐƯỜNG ĐỎ TẠI MỐ (xm), KHÔNG dùng cao_dd đỉnh → khớp trắc dọc/MCN.
                _soffit_mo3d = _zred_fn(xm) - t_ban - H_dam
                _seat_mo3d = _abut_seat_z(_soffit_mo3d, d.get("_pier_model"))
                _Htru_mo  = max(0.5, _seat_mo3d - _zbase_mo)    # đỉnh mố = đáy dầm mố
                _xf_mo3d  = xm - sgn * (KHO_HO_DAM_MO
                                        + _PBm2.abut_backwall_u_m(_mo_model))  # hở 100mm
                try:
                    _mtr = _PBm2.build_abutment_mesh_traces(
                        _mo_model, H_tru=_Htru_mo, x_face=_xf_mo3d,
                        out_dir=sgn, z_base=_zbase_mo, seat_z=_seat_mo3d,
                        target_width=bc)       # co bề rộng mố theo bề rộng cầu
                except Exception as _me:
                    print(f"[add_all] mố lỗi: {_me}"); _mtr = []
                for _tr in _mtr:
                    try:
                        _nx, _ny = [], []
                        for _vx, _vy in zip(list(_tr.x), list(_tr.y)):
                            _gx, _gy = _vn(_vx, _vy); _nx.append(_gx); _ny.append(_gy)
                        _tr.x = _nx; _tr.y = _ny
                        _tr.z = [_vz * hz for _vz in list(_tr.z)]
                        _tr.legendgroup = "Mố"
                        _tr.name = nm if sl else ""
                        _tr.showlegend = bool(sl)
                    except Exception:
                        pass
                    fig.add_trace(_tr)
            else:
                _ag(_abox(xm, xm + sgn*mo_L, -bc/2-0.5, bc/2+0.5,
                                    z_beb, z_deck, "#c0a06b", 0.85, nm, sl=sl))

        # ── ĐƯỜNG ĐẦU CẦU: nền đắp + mặt đường vươn 50m mỗi bên ──────────────
        # Extrapolate tim tuyến beyond survey range (np.interp would clamp).
        def _vn_ext(s, off=0.0):
            # Đường đầu cầu XIÊN theo góc giao (khớp mố xiên) → skew=True: điểm ở
            # offset off trượt lý trình off·cot(α), nối liền với bản mặt cầu xiên.
            if s < lt_v[0]:
                xc, yc = _vn(float(lt_v[0]), off, True); g = float(goc_v[0]); dd = s - lt_v[0]
                return (xc + dd*np.cos(g), yc + dd*np.sin(g))
            if s > lt_v[-1]:
                xc, yc = _vn(float(lt_v[-1]), off, True); g = float(goc_v[-1]); dd = s - lt_v[-1]
                return (xc + dd*np.cos(g), yc + dd*np.sin(g))
            return _vn(s, off, True)

        def _approach_emb(s0, s1, z_top_fn, taluy=1.5, name="", sl=True, step=5.0):
            """Nền đắp đầu cầu QUÉT dọc tim tuyến: mặt cắt hình thang (đỉnh = mặt
            đường KHỚP cao độ mặt cầu, đáy mở theo mái taluy tới mặt đất TN)."""
            m  = max(2, int(abs(s1 - s0) / step))
            ss = np.linspace(s0, s1, m + 1)
            vx, vy, vz = [], [], []
            for s in ss:
                z_road = z_top_fn(s)
                z_g    = float(np.interp(s, lt_v, vz_v)) * hz
                h_real = max(0.0, (z_road - z_g) / max(hz, 1e-6))
                sft    = h_real * taluy
                xtL, ytL = _vn_ext(s, -bc/2)
                xtR, ytR = _vn_ext(s,  bc/2)
                xbL, ybL = _vn_ext(s, -(bc/2 + sft))
                xbR, ybR = _vn_ext(s,  (bc/2 + sft))
                vx += [xtL, xtR, xbR, xbL]
                vy += [ytL, ytR, ybR, ybL]
                vz += [z_road, z_road, z_g, z_g]   # 0=đỉnhL 1=đỉnhR 2=đáyR 3=đáyL
            ii, jj, kk = [], [], []
            def _q(a, b, c, dd):
                ii.append(a); jj.append(b); kk.append(c)
                ii.append(a); jj.append(c); kk.append(dd)
            for i in range(m):
                b0, b1 = 4*i, 4*(i+1)
                _q(b0+0, b0+1, b1+1, b1+0)   # mặt đỉnh (mặt đường)
                _q(b0+3, b0+2, b1+2, b1+3)   # mặt đáy
                _q(b0+1, b0+2, b1+2, b1+1)   # mái taluy phải
                _q(b0+0, b1+0, b1+3, b0+3)   # mái taluy trái
            _q(0, 1, 2, 3)                    # bịt đầu (lưng mố)
            _last = 4*m
            _q(_last, _last+3, _last+2, _last+1)  # bịt cuối
            return go.Mesh3d(
                x=vx, y=vy, z=vz, i=ii, j=jj, k=kk,
                color="#c9a86b", opacity=0.55, flatshading=True,
                name=name, showlegend=sl and bool(name),
                lighting=dict(ambient=0.65, diffuse=0.85, specular=0.15),
                hovertemplate=f"<b>{name}</b><extra></extra>" if name else None,
            )

        def _approach_road(s0, s1, z_top_fn, name="", sl=True, step=5.0):
            """Mặt đường đầu cầu (tấm mỏng) KHỚP cao độ mặt cầu, hạ dần theo dốc dọc."""
            m  = max(2, int(abs(s1 - s0) / step))
            ss = np.linspace(s0, s1, m + 1)
            vx, vy, vz = [], [], []
            for s in ss:
                zt = z_top_fn(s); zb = zt - 0.25 * hz
                xL, yL = _vn_ext(s, -bc/2)
                xR, yR = _vn_ext(s,  bc/2)
                vx += [xL, xR, xL, xR]
                vy += [yL, yR, yL, yR]
                vz += [zb, zb, zt, zt]            # 0=Lđáy 1=Rđáy 2=Lđỉnh 3=Rđỉnh
            ii, jj, kk = [], [], []
            def _q(a, b, c, dd):
                ii.append(a); jj.append(b); kk.append(c)
                ii.append(a); jj.append(c); kk.append(dd)
            for i in range(m):
                b0, b1 = 4*i, 4*(i+1)
                _q(b0+2, b0+3, b1+3, b1+2)        # mặt trên
                _q(b0+0, b1+0, b1+1, b0+1)        # mặt dưới
            return go.Mesh3d(
                x=vx, y=vy, z=vz, i=ii, j=jj, k=kk,
                color="#34495e", opacity=0.95, flatshading=True,
                name=name, showlegend=sl and bool(name),
                lighting=dict(ambient=0.65, diffuse=0.85, specular=0.2),
                hovertemplate=f"<b>{name}</b><extra></extra>" if name else None,
            )

        # Cao độ mặt đường đầu cầu BÁM ĐƯỜNG ĐỎ (make_red_line) + lớp phủ → liền
        # mạch với mặt cầu, không chênh bậc tại khe nối.
        _grp_state["g"] = "Đường đầu cầu"
        _L_app_t = 50.0
        for _xm, _od in [(x0, -1.0), (x_end, 1.0)]:
            _s1 = _xm + _od * _L_app_t
            def _z_app(s, _xm=_xm):
                return (_zred_fn(s) + t_phu) * hz
            _ag(_approach_emb(
                _xm, _s1, _z_app, taluy=1.5,
                name="Nền đắp đầu cầu" if _od < 0 else "", sl=(_od < 0)))
            _ag(_approach_road(
                _xm, _s1, _z_app,
                name="Mặt đường đầu cầu" if _od < 0 else "", sl=(_od < 0)))

        # ── BẢN QUÁ ĐỘ (cấu kiện BẮT BUỘC sau mỗi mố — Module 07) ───────────
        # Đọc tru_result.ket_qua_mo.ban_qua_do: tấm BTCT nằm giữa tường đỉnh
        # mố và dầm kê trong nền đường, mặt bản dưới mặt đường ≥ 0.7m, dốc
        # dọc 10–15% hạ dần về phía nền đường.
        _grp_state["g"] = "Bản quá độ"
        _bqd = ((d.get("tru_result") or {}).get("ket_qua_mo") or {}
                ).get("ban_qua_do") or {}
        _L_bqd   = float(_bqd.get("L_bqd", 5.0) or 5.0)
        _t_bqd   = float(_bqd.get("day_bqd", 0.30) or 0.30)
        _doc_bqd = float(_bqd.get("doc_bqd_val", 0.10) or 0.10)
        _cover   = float(_bqd.get("chieu_sau_dat_dap_toi_thieu", 0.70) or 0.70)

        def _bqd_slab(s0, s1, z_top0, z_top1, t_slab, color, nm, sl):
            """Tấm nghiêng quét theo tim tuyến (2 mặt cắt × 4 đỉnh)."""
            vx, vy, vz = [], [], []
            for _s, _zt in [(s0, z_top0), (s1, z_top1)]:
                _xL, _yL = _vn_ext(_s, -bc / 2)
                _xR, _yR = _vn_ext(_s,  bc / 2)
                vx += [_xL, _xR, _xR, _xL]
                vy += [_yL, _yR, _yR, _yL]
                vz += [_zt * hz, _zt * hz,
                       (_zt - t_slab) * hz, (_zt - t_slab) * hz]
            ii, jj, kk = [], [], []
            def _q(a, b, c, dd):
                ii.append(a); jj.append(b); kk.append(c)
                ii.append(a); jj.append(c); kk.append(dd)
            _q(0, 1, 5, 4)   # mặt trên
            _q(3, 2, 6, 7)   # mặt dưới
            _q(0, 4, 7, 3)   # bên trái
            _q(1, 2, 6, 5)   # bên phải
            _q(0, 1, 2, 3)   # bịt đầu phía mố
            _q(4, 5, 6, 7)   # bịt đầu phía nền đường
            return go.Mesh3d(
                x=vx, y=vy, z=vz, i=ii, j=jj, k=kk,
                color=color, opacity=0.95, flatshading=True,
                name=nm, showlegend=sl and bool(nm),
                lighting=dict(ambient=0.6, diffuse=0.9, specular=0.15),
                hovertemplate=(f"<b>{nm or 'Bản quá độ'}</b><br>L={_L_bqd:g}m"
                               f" · dày {_t_bqd*100:.0f}cm · dốc "
                               f"{_doc_bqd*100:.0f}% · đắp ≥{_cover*100:.0f}cm"
                               "<extra></extra>"))

        for _xm, _od in [(x0, -1.0), (x_end, 1.0)]:
            # Một đầu kê TƯỜNG ĐỈNH MỐ (tại mố), đầu kia trên DẦM KÊ trong nền
            # đường (cách mố L_bqd); mặt bản dưới mặt đường ≥ _cover, hạ dần
            # theo dốc _doc_bqd về phía nền đường.
            _s_far = _xm + _od * _L_bqd
            _z_near = _zred_fn(_xm) + t_phu - _cover
            _z_far  = _z_near - _doc_bqd * _L_bqd
            _ag(_bqd_slab(_xm, _s_far, _z_near, _z_far, _t_bqd, "#8d99a6",
                          "Bản quá độ" if _od < 0 else "", sl=(_od < 0)))
            # Dầm kê đỡ đầu bản trong nền đường
            _ag(_bqd_slab(_s_far, _s_far + _od * 0.4,
                          _z_far - _t_bqd, _z_far - _t_bqd, 0.4,
                          "#6d7a87", "", sl=False))

        # Đường bao cấu kiện (viền tối các hộp trụ/mố/xà mũ/bệ…) → dễ nhìn
        _add_box_outlines(fig)
        _hover3d(fig)   # hover: tên cấu kiện + cao độ

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
            showlegend=True,
            legend=dict(
                orientation="v", x=1.01, y=0.5,
                font=dict(size=8),
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor="#ccc", borderwidth=1,
                groupclick="togglegroup",   # click nhóm → ẩn/hiện cả cụm
                title=dict(text="Ẩn/hiện cấu kiện ▾", font=dict(size=9)),
            ),
        )

    except Exception as exc:
        import traceback
        print(f"[add_all_to_terrain_fig] Lỗi: {exc}\n{traceback.format_exc()}")


# ===========================================================================
# 7. BÌNH ĐỒ CẦU (MẶT BẰNG — nhìn từ trên xuống)
# ===========================================================================
def _ve_binh_do_cong(d, df_geology):
    """Mặt bằng cầu CONG theo tim tuyến khảo sát — khớp với 3D tổng
    (add_all_to_terrain_fig): dùng cùng phép chiếu _vn(lý_trình, offset) sang
    tọa độ VN-2000 (đã trừ gốc). Vẽ: mặt cầu + lan can + tim + đường đầu cầu +
    mố + trụ + khung tĩnh không, đều bám đúng đường cong & góc xiên như 3D."""
    kcn = d.get("kcn_result") or d.get("ai_result", {})
    geo = d.get("geo_logic", {})
    bc     = float(d.get("bc", 12.0))
    B_tk   = float(d.get("B", 20.0))
    L_nhip = float(kcn.get("chieu_dai", 33.0) or 33.0)
    L_cau0 = float(geo.get("L_cau", 120))
    x0    = float(geo.get("x_mo_trai", -L_cau0 / 2))
    x_end = float(geo.get("x_mo_phai", x0 + L_cau0))
    x_tim = float(geo.get("x_tim_clearance", (x0 + x_end) / 2))
    supports, L_std = resolve_supports(d, x0, x_end, x_tim, B_tk, L_nhip)
    x0, x_end = supports[0], supports[-1]
    piers  = supports[1:-1]
    n_nhip = len(supports) - 1
    L_cau  = x_end - x0
    goc    = float(d.get("goc_giao", 90.0))

    # ── Tim tuyến VN-2000 (Offset==0) — giống add_all_to_terrain_fig ─────────
    df_cl = (df_geology[df_geology["Offset"] == 0]
             [["Lý trình", "X_VN2000", "Y_VN2000", "Góc_Tuyến"]]
             .drop_duplicates("Lý trình").sort_values("Lý trình"))
    lt_v  = df_cl["Lý trình"].values
    vx_v  = df_cl["X_VN2000"].values
    vy_v  = df_cl["Y_VN2000"].values
    goc_v = df_cl["Góc_Tuyến"].values
    _i0   = int(np.argmin(lt_v))
    x_org = float(vx_v[_i0]); y_org = float(vy_v[_i0])
    _cot  = (0.0 if goc >= 89.9 or goc <= 0
             else 1.0 / np.tan(np.radians(max(30.0, min(89.9, goc)))))

    def _at(s):
        return (float(np.interp(s, lt_v, vx_v)),
                float(np.interp(s, lt_v, vy_v)),
                float(np.interp(s, lt_v, goc_v)))

    def _vn(s, off=0.0, skew=True):
        s_eff = (s + off * _cot) if skew else s
        xc, yc, g = _at(s_eff)
        perp = g + np.pi / 2
        return (xc + off * np.cos(perp) - x_org,
                yc + off * np.sin(perp) - y_org)

    cap_W = max(2.0, bc * 0.18 + 1.0)   # nửa bề rộng xà mũ (ngang) — như 3D tổng
    tru_L = 0.8                          # nửa bề dày xà mũ (dọc)
    mo_L  = 3.5                          # chiều dài mố (dọc)
    mg    = max(12.0, L_cau * 0.15)      # chiều dài đường đầu cầu hiển thị

    def _xy(pts):
        return [p[0] for p in pts], [p[1] for p in pts]

    fig = go.Figure()
    _ns = max(24, int(L_cau / 2))
    ss  = np.linspace(x0, x_end, _ns)

    # ── Khung tĩnh không (sông) — BÁM GÓC XIÊN (sông cắt tuyến theo góc giao) ──
    ss_tk = np.linspace(x_tim - B_tk/2, x_tim + B_tk/2, 8)
    _la = [_vn(s, -B_tk*0.7) for s in ss_tk]     # skew=True → sông xiên theo góc
    _ra = [_vn(s, +B_tk*0.7) for s in ss_tk]
    _px, _py = _xy(_la + _ra[::-1] + [_la[0]])
    fig.add_trace(go.Scatter(x=_px, y=_py, fill="toself",
        fillcolor="rgba(52,152,219,0.15)", mode="lines",
        line=dict(color="#2980b9", width=1.5, dash="dot"),
        name=f"Sông/Kênh (B_tk={B_tk:.0f}m)"))

    # ── Tĩnh không PHỤ (dải cam vuông góc tuyến tại từng lý trình khai báo) ──
    _tkp_first = True
    for _cx in (d.get("extra_clearances") or []):
        try:
            _xk = float(_cx.get("x")); _Bk = float(_cx.get("B", 0) or 0)
        except (TypeError, ValueError):
            continue
        if _Bk <= 0:
            continue
        _nmk = str(_cx.get("ten") or "Tĩnh không phụ")
        _gk = float(_cx.get("goc", 90) or 90)
        _cotk = (0.0 if _gk >= 89.9 or _gk <= 0
                 else 1.0 / np.tan(np.radians(max(10.0, min(89.9, _gk)))))
        _yh = B_tk*0.7
        _ssk = np.linspace(_xk - _Bk/2, _xk + _Bk/2, 8)
        # Xiên theo góc giao: mép transverse dịch dọc tuyến 1 lượng off·cotk
        _lak = [_vn(s + (-_yh)*_cotk, -_yh, skew=False) for s in _ssk]
        _rak = [_vn(s + (+_yh)*_cotk, +_yh, skew=False) for s in _ssk]
        _px, _py = _xy(_lak + _rak[::-1] + [_lak[0]])
        fig.add_trace(go.Scatter(x=_px, y=_py, fill="toself",
            fillcolor="rgba(230,126,34,0.12)", mode="lines",
            line=dict(color="#e67e22", width=1.8, dash="dash"),
            name=(_nmk if _tkp_first else ""), showlegend=_tkp_first))
        _tkp_first = False

    # ── Đường đầu cầu (2 đầu, kéo dài ngoài mố) — BÁM góc xiên như MẶT CẦU & 3D
    #    (add_all_to_terrain_fig dùng _vn_ext skew=True) + mái TALUY ──────────
    _h_dap_tb = max(1.5, float(d.get("H_tru_est", 5.0)) * 0.4)   # chiều cao đắp ước tính
    _taluy_w  = 1.5 * _h_dap_tb                                   # bề rộng chân taluy 1:1.5
    for s_m, od, lbl in [(x0, -1.0, "Đường đầu cầu"), (x_end, 1.0, None)]:
        ss_a = np.linspace(s_m, s_m + od*mg, 14)
        _la = [_vn(s, -bc/2) for s in ss_a]      # skew=True → xiên theo góc giao
        _ra = [_vn(s, +bc/2) for s in ss_a]
        _px, _py = _xy(_la + _ra[::-1] + [_la[0]])
        fig.add_trace(go.Scatter(x=_px, y=_py, fill="toself",
            fillcolor="rgba(196,164,107,0.28)", mode="lines",
            line=dict(color="#8a6d3b", width=1.4),
            name=lbl or "", showlegend=bool(lbl)))
        # Mái taluy: chân taluy = mép đường + bề rộng taluy (nét đứt 2 bên)
        for _sgn in (-1, 1):
            _toe = [_vn(s, _sgn*(bc/2 + _taluy_w)) for s in ss_a]
            _px, _py = _xy(_toe)
            fig.add_trace(go.Scatter(x=_px, y=_py, mode="lines",
                line=dict(color="#a5866b", width=1.0, dash="dot"),
                name=("Chân taluy" if (lbl and _sgn == -1) else ""),
                showlegend=bool(lbl and _sgn == -1)))
            # gạch mái taluy (đường xiên từ mép đường ra chân taluy)
            for _st in np.linspace(ss_a[0], ss_a[-1], 6):
                _e0 = _vn(_st, _sgn*bc/2)
                _e1 = _vn(_st, _sgn*(bc/2 + _taluy_w))
                fig.add_trace(go.Scatter(x=[_e0[0], _e1[0]], y=[_e0[1], _e1[1]],
                    mode="lines", line=dict(color="#c4a76b", width=0.6),
                    showlegend=False, hoverinfo="skip"))

    # ── Mặt cầu (dải cong theo tim) ─────────────────────────────────────────
    _left  = [_vn(s, -bc/2) for s in ss]
    _right = [_vn(s, +bc/2) for s in ss]
    _px, _py = _xy(_left + _right[::-1] + [_left[0]])
    fig.add_trace(go.Scatter(x=_px, y=_py, fill="toself",
        fillcolor="rgba(213,216,220,0.60)", mode="lines",
        line=dict(color="#2c3e50", width=2), name="Mặt cầu",
        hovertemplate=f"Mặt cầu B={bc:.1f}m, Góc={goc:.0f}°<extra></extra>"))

    # ── Lan can 2 bên (nét đậm) ─────────────────────────────────────────────
    for _sy, _nm in [(-1, "Lan can"), (1, None)]:
        _edge = [_vn(s, _sy*bc/2) for s in ss]
        _px, _py = _xy(_edge)
        fig.add_trace(go.Scatter(x=_px, y=_py, mode="lines",
            line=dict(color="#2c3e50", width=3),
            name=_nm or "", showlegend=bool(_nm)))

    # ── Tim cầu ─────────────────────────────────────────────────────────────
    _ctr = [_vn(s, 0.0) for s in np.linspace(x0 - 6, x_end + 6, _ns)]
    _px, _py = _xy(_ctr)
    fig.add_trace(go.Scatter(x=_px, y=_py, mode="lines",
        line=dict(color="#e74c3c", width=1, dash="dashdot"),
        name="Tim cầu", showlegend=False))

    # ── Mố (2 đầu) — MẶT BẰNG = CHIẾU lưới 3D mố thực (build_abutment_mesh_traces)
    # xuống mặt bằng, CÙNG NGUỒN + CÙNG neo (x_face, out_dir) với 3D toàn cầu →
    # khớp tuyệt đối (giữ hình chữ U: thân + 2 cánh). Cọc theo sơ đồ khai báo.
    _PBa = _get_PB()
    _mo_asm = d.get("_mo_model")
    _cao_dd_bd = float(d.get("cao_day_dam", 8.0))
    for s_m, sgn, lbl, _mk in [(x0, 1.0, "Mố M1", "mo_trai"),
                               (x_end, -1.0, "Mố M2", "mo_phai")]:
        if _mo_asm:
            _mseen = set()
            _xf_m = s_m - sgn * (KHO_HO_DAM_MO + _PBa.abut_backwall_u_m(_mo_asm))
            _seat = _abut_seat_z(_cao_dd_bd, d.get("_pier_model"))
            _mtr = _PBa.build_abutment_mesh_traces(
                _mo_asm, H_tru=5.0, x_face=_xf_m, out_dir=sgn,
                z_base=0.0, seat_z=_seat, target_width=bc)
            _piles_m = _layout_piles(d, _mk)
            if _piles_m:
                _mcx, _mcy = [], []
                for _p in _piles_m:
                    _gx, _gy = _vn(s_m + sgn * float(_p.get("y", 0.0)),
                                   float(_p.get("x", 0.0)))
                    _mcx.append(_gx); _mcy.append(_gy)
                fig.add_trace(go.Scatter(x=_mcx, y=_mcy, mode="markers",
                    marker=dict(symbol="circle-open", size=7, color="#8e6e53",
                                line=dict(width=1.2)), showlegend=False))
            for _pl in project_mesh_traces(_mtr, axis="z"):
                _nm = _pl["name"].split(" #")[0]
                _sl2 = (lbl == "Mố M1") and (_nm not in _mseen); _mseen.add(_nm)
                # xs = dọc (chainage), zs = ngang → chiếu lên tim cong _vn.
                _pts = [_vn(_ch, _ng) for _ch, _ng in zip(_pl["xs"], _pl["zs"])]
                _px, _py = _xy(_pts + [_pts[0]])
                fig.add_trace(go.Scatter(x=_px, y=_py, fill="toself",
                    fillcolor=_hex_rgba(_pl.get("color", "#c0a06b"), 0.6),
                    mode="lines", line=dict(color="#7d6608", width=1.5),
                    name=(_nm if _sl2 else ""), showlegend=_sl2))
        else:
            bm = bc/2 + 0.6
            _c = [_vn(s_m, -bm), _vn(s_m, +bm),
                  _vn(s_m - sgn*mo_L, +bm), _vn(s_m - sgn*mo_L, -bm)]
            _px, _py = _xy(_c + [_c[0]])
            fig.add_trace(go.Scatter(x=_px, y=_py, fill="toself",
                fillcolor="rgba(192,160,107,0.65)", mode="lines",
                line=dict(color="#7d6608", width=2), name=lbl))

    # ── Trụ — MẶT BẰNG THẬT từ hệ trụ lắp ghép (khớp 3D): footprint bệ/thân/xà mũ
    # + cọc theo sơ đồ khai báo (thay khối hộp tham số cũ). Chiếu lên tim cong _vn.
    _PBm = _get_PB()
    _pier_asm = d.get("_pier_model")
    _wmap = (d or {}).get("_pier_cap_widen") or {}
    _w0cap = float((d or {}).get("_pier_cap_W0", 0) or 0)
    mong  = d.get("mong_result") or {}
    D_coc, _Lc, _ncoc = mong_dims(mong)

    def _draw_plan_polys(polys, xc_s, seen, dash=None, fill_op=0.78, first=False):
        for _pl in polys:
            _nm = _pl["name"]; _sl = first and (_nm not in seen); seen.add(_nm)
            _pts = [_vn(xc_s + _yy, _xx) for _xx, _yy in zip(_pl["xs"], _pl["ys"])]
            _px, _py = _xy(_pts + [_pts[0]])
            _col = _pl.get("color", "#566573")
            fig.add_trace(go.Scatter(x=_px, y=_py, fill="toself",
                fillcolor=_hex_rgba(_col, fill_op), mode="lines",
                line=dict(color=_C["be_dk"], width=1.4, dash=dash),
                name=(_nm if _sl else ""), showlegend=_sl))

    def _draw_plan_piles(pos_key, xc_s, first=False):
        _piles = _layout_piles(d, pos_key)
        if not _piles:
            return
        _cx, _cy = [], []
        for _p in _piles:
            _gx, _gy = _vn(xc_s + float(_p.get("y", 0.0)), float(_p.get("x", 0.0)))
            _cx.append(_gx); _cy.append(_gy)
        fig.add_trace(go.Scatter(x=_cx, y=_cy, mode="markers",
            marker=dict(symbol="circle-open", size=7, color="#8e6e53",
                        line=dict(width=1.2)),
            name=(f"Cọc ({len(_piles)} cọc)" if first else ""), showlegend=first))

    for i, xt in enumerate(piers):
        _sl = (i == 0)
        _seen = set()
        if _pier_asm:
            _mid_extra = max(0.0, _wmap.get(round(xt, 3), _w0cap) - _w0cap)
            _polys = _PBm.pier_plan_polys(_pier_asm, target_width=bc,
                                          cap_mid_extra=_mid_extra)
            _draw_plan_piles(f"tru_{i+1}", xt, first=_sl)
            _draw_plan_polys(_polys, xt, _seen, first=_sl)   # bệ→thân→xà mũ (trên)
        else:
            _c = [_vn(xt + s, o) for s, o in
                  [(-tru_L, -cap_W), (-tru_L, cap_W), (tru_L, cap_W), (tru_L, -cap_W)]]
            _px, _py = _xy(_c + [_c[0]])
            fig.add_trace(go.Scatter(x=_px, y=_py, fill="toself",
                fillcolor="rgba(133,146,158,0.78)", mode="lines",
                line=dict(color="#566573", width=1.5),
                name="Xà mũ" if _sl else "", showlegend=_sl))
        _cx, _cy = _vn(xt, 0.0)
        fig.add_annotation(x=_cx, y=_cy, text=f"T{i+1}", showarrow=False,
            font=dict(size=8, color="white"), bgcolor="rgba(86,101,115,0.85)")

    fig.update_layout(
        title=dict(text=(f"BÌNH ĐỒ CẦU (theo tim khảo sát) — {n_nhip} nhịp | "
                         f"L={L_cau:.1f}m | B_c={bc:.1f}m"
                         + (f" | Góc xiên α={goc:.0f}°" if goc < 89.0 else "")),
                   x=0.5, font=dict(size=12)),
        xaxis=dict(title="X (m, VN-2000 tương đối)", showgrid=True,
                   gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5),
        yaxis=dict(title="Y (m)", showgrid=True, scaleanchor="x", scaleratio=1,
                   gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5),
        height=460, template="plotly_white",
        legend=dict(orientation="h", y=-0.22, font=dict(size=9)),
        margin=dict(l=60, r=40, t=60, b=90), hovermode="closest",
    )
    _apply_layers_2d(fig)
    return fig


def ve_binh_do_2d(d, df_tim_line=None, df_geology=None):
    """Bình đồ cầu: mặt bằng nhìn từ trên, bao gồm dầm, mố, trụ, TK, góc xiên.

    Nếu có df_geology (VN-2000: X_VN2000, Y_VN2000, Góc_Tuyến, Offset) → vẽ
    bình đồ CONG theo tim khảo sát (khớp 3D tổng). Ngược lại vẽ bình đồ THẲNG
    có xét góc xiên (fallback khi chưa nạp khảo sát)."""
    _align = df_geology if df_geology is not None else df_tim_line
    _need = {"X_VN2000", "Y_VN2000", "Góc_Tuyến", "Offset", "Lý trình"}
    if (_align is not None and hasattr(_align, "columns")
            and not _align.empty and _need <= set(_align.columns)):
        try:
            return _ve_binh_do_cong(d, _align)
        except Exception as _e:
            print(f"[ve_binh_do_2d] fallback thẳng do lỗi bình đồ cong: {_e}")

    kcn  = d.get("kcn_result") or d.get("ai_result", {})
    geo  = d.get("geo_logic", {})
    L_cau  = float(geo.get("L_cau", 120))
    bc     = float(d.get("bc", 12.0))
    B_tk   = float(d.get("B", 20.0))
    n_nhip = int(kcn.get("tong_so_nhip", 3))
    x0     = float(geo.get("x_mo_trai", -L_cau / 2))
    x_end  = float(geo.get("x_mo_phai", x0 + L_cau))
    x_tim  = float(geo.get("x_tim_clearance", (x0 + x_end) / 2))
    L_nhip = float(kcn.get("chieu_dai", 33.0) or 33.0)
    supports, L_std = resolve_supports(d, x0, x_end, x_tim, B_tk, L_nhip)
    x0, x_end = supports[0], supports[-1]
    piers  = supports[1:-1]
    n_nhip = len(supports) - 1
    L_cau  = x_end - x0
    cap_W  = max(2.0, bc * 0.18 + 1.0)
    mo_W   = 3.5

    # ── Góc xiên ─────────────────────────────────────────────────────────
    goc = float(d.get("goc_giao", 90.0))
    alpha  = np.radians(max(30.0, min(89.9, goc)))  # clamp 30°–89.9°
    # Độ lệch ngang (theo x) tại y = ±(bc/2): dương ở y=+bc/2
    # Mố & cầu xiên khi goc < 90°
    skew_dx = (bc / 2) / np.tan(alpha)          # tại mép bc/2
    mo_dx   = (bc / 2 + 0.6) / np.tan(alpha)    # tại mép mố (rộng hơn bc 0.6m)

    def _sx(y):
        """x-offset cho điểm có tọa độ ngang y (do góc xiên)."""
        return y / np.tan(alpha)

    fig = go.Figure()

    # Vùng sông (tĩnh không) — không bị ảnh hưởng góc xiên
    fig.add_shape(type="rect",
        x0=x_tim - B_tk / 2, x1=x_tim + B_tk / 2,
        y0=-B_tk * 0.7, y1=B_tk * 0.7,
        fillcolor="rgba(52,152,219,0.18)", line=dict(color="#2980b9", width=1.5, dash="dot"))
    fig.add_annotation(x=x_tim, y=0,
        text=f"Sông/Kênh<br>B={B_tk:.1f}m", showarrow=False,
        font=dict(size=9, color="#2980b9"), bgcolor="rgba(255,255,255,0.7)")

    # ── Mặt cầu — hình bình hành theo góc xiên ───────────────────────────
    # Các góc: (x0+sx(-bc/2), -bc/2) → (x_end+sx(-bc/2), -bc/2)
    #          → (x_end+sx(+bc/2), +bc/2) → (x0+sx(+bc/2), +bc/2)
    _x_deck = [
        x0  + _sx(-bc/2), x_end + _sx(-bc/2),
        x_end + _sx(+bc/2), x0  + _sx(+bc/2),
        x0  + _sx(-bc/2),
    ]
    _y_deck = [-bc/2, -bc/2, bc/2, bc/2, -bc/2]
    fig.add_trace(go.Scatter(
        x=_x_deck, y=_y_deck,
        fill="toself", fillcolor="rgba(213,216,220,0.55)",
        line=dict(color="#2c3e50", width=2),
        name="Mặt cầu", mode="lines",
        hovertemplate=f"Mặt cầu B={bc:.1f}m, Góc={goc:.0f}°<extra></extra>"
    ))

    # Lan can (đường đậm 2 bên dọc cầu)
    for sy in [-1, 1]:
        fig.add_trace(go.Scatter(
            x=[x0 + _sx(sy*bc/2), x_end + _sx(sy*bc/2)],
            y=[sy * bc/2, sy * bc/2],
            mode="lines", line=dict(color="#2c3e50", width=3), showlegend=False,
        ))

    # Tim cầu (dashdot dọc)
    fig.add_shape(type="line",
        x0=x0 - 8, y0=0, x1=x_end + 8, y1=0,
        line=dict(color="#e74c3c", width=1, dash="dashdot"))

    # ── Mố — xiên theo góc giao ───────────────────────────────────────────
    for xm, lbl in [(x0, "Mố trái"), (x_end, "Mố phải")]:
        sign = 1 if xm == x0 else -1
        bm   = bc / 2 + 0.6   # bán chiều rộng mố (rộng hơn lan can 0.6m)
        # Mặt trước mố (tiếp xúc nhịp): từ (xm+sx(-bm), -bm) → (xm+sx(+bm), +bm)
        # Mặt sau mố (back wall): cộng thêm sign*mo_W
        xf_bot = xm + _sx(-bm)
        xf_top = xm + _sx(+bm)
        xb_bot = xf_bot + sign * mo_W
        xb_top = xf_top + sign * mo_W
        fig.add_trace(go.Scatter(
            x=[xf_bot, xb_bot, xb_top, xf_top, xf_bot],
            y=[-bm, -bm, bm, bm, -bm],
            fill="toself", fillcolor="rgba(192,160,107,0.65)",
            line=dict(color="#7d6608", width=2),
            name=lbl, mode="lines",
        ))
        # Tường cánh (xiên theo mố)
        for sy in [-1, 1]:
            wing_y = sy * (bm + mo_W * 0.8)
            fig.add_trace(go.Scatter(
                x=[xf_bot if sy < 0 else xf_top,
                   (xf_bot if sy < 0 else xf_top) + sign * mo_W * 1.4 + _sx(sy * mo_W * 0.8)],
                y=[sy * bm, wing_y],
                mode="lines", line=dict(color="#7d6608", width=1.5), showlegend=False,
            ))

    # ── Trụ — xà mũ xiên theo góc ────────────────────────────────────────
    tru_L_half = 0.8
    for i, xt in enumerate(piers):
        # Xà mũ xiên: từ (xt-L+sx(-cap_W), -cap_W) → (xt+L+sx(-cap_W), -cap_W)
        #             → (xt+L+sx(+cap_W), +cap_W) → (xt-L+sx(+cap_W), +cap_W)
        _xt_x = [
            xt - tru_L_half + _sx(-cap_W),
            xt + tru_L_half + _sx(-cap_W),
            xt + tru_L_half + _sx(+cap_W),
            xt - tru_L_half + _sx(+cap_W),
            xt - tru_L_half + _sx(-cap_W),
        ]
        fig.add_trace(go.Scatter(
            x=_xt_x, y=[-cap_W, -cap_W, cap_W, cap_W, -cap_W],
            fill="toself", fillcolor="rgba(133,146,158,0.75)",
            line=dict(color="#566573", width=1.5),
            name=f"Trụ T{i+1}", mode="lines",
        ))
        fig.add_annotation(x=xt, y=0, text=f"T{i+1}",
            showarrow=False, font=dict(size=8, color="white"),
            bgcolor="rgba(86,101,115,0.85)")

    # Khung tĩnh không (mặt bằng — vuông góc với dòng chảy)
    fig.add_shape(type="rect",
        x0=x_tim - B_tk/2, x1=x_tim + B_tk/2,
        y0=-B_tk/2 - 0.3, y1=B_tk/2 + 0.3,
        line=dict(color="#e74c3c", width=2.5, dash="dash"),
        fillcolor="rgba(231,76,60,0.04)")

    # ── Tĩnh không PHỤ (khung cam tại từng lý trình khai báo) ────────────────
    for _cx in (d.get("extra_clearances") or []):
        try:
            _xk = float(_cx.get("x")); _Bk = float(_cx.get("B", 0) or 0)
        except (TypeError, ValueError):
            continue
        if _Bk <= 0:
            continue
        _nmk = str(_cx.get("ten") or "TK phụ")
        _gk = float(_cx.get("goc", 90) or 90)
        _cotk = (0.0 if _gk >= 89.9 or _gk <= 0
                 else 1.0 / np.tan(np.radians(max(10.0, min(89.9, _gk)))))
        _yh = B_tk/2 + 0.3
        _shk = lambda _y: _y * _cotk        # xiên theo góc giao với tim tuyến
        fig.add_trace(go.Scatter(
            x=[_xk-_Bk/2+_shk(-_yh), _xk+_Bk/2+_shk(-_yh),
               _xk+_Bk/2+_shk(+_yh), _xk-_Bk/2+_shk(+_yh), _xk-_Bk/2+_shk(-_yh)],
            y=[-_yh, -_yh, _yh, _yh, -_yh],
            fill="toself", fillcolor="rgba(230,126,34,0.06)", mode="lines",
            line=dict(color="#e67e22", width=2.0, dash="dash"),
            name="Tĩnh không phụ", showlegend=False,
            hovertemplate=f"{_nmk} B={_Bk:.1f}m, góc={_gk:.0f}°<extra></extra>"))
        fig.add_annotation(x=_xk + _shk(_yh), y=B_tk/2 + 0.6,
            text=(f"<b>{_nmk}</b> B={_Bk:.1f}m"
                  + (f" · {_gk:.0f}°" if _gk < 89.0 else "")),
            showarrow=False, font=dict(size=8, color="#e67e22"),
            bgcolor="rgba(255,255,255,0.8)")

    # ── Chú thích góc xiên ────────────────────────────────────────────────
    if goc < 89.0:
        fig.add_annotation(
            x=x0 + _sx(bc/2) + 2, y=bc/2 + 0.5,
            text=f"<b>Góc giao chéo α = {goc:.0f}°</b>",
            showarrow=True, arrowhead=2, arrowcolor="#e67e22",
            ax=-40, ay=-20,
            font=dict(size=10, color="#e67e22"),
            bgcolor="rgba(255,255,255,0.85)",
        )

    # Dimensions
    _dim_h(fig, bc/2 + 2.5, x0, x_end, f"L_cầu = {L_cau:.1f} m (dọc cầu)", dy=0)
    if piers:
        _dim_h(fig, -bc/2 - 2.5, piers[0], piers[-1] if len(piers) > 1 else x_end,
               f"Khoảng TT = {(piers[-1] if len(piers)>1 else x_end) - piers[0]:.1f} m", dy=0)
    _dim_v(fig, x_end + _sx(bc/2) + mo_W + 1.5, -bc/2, bc/2, f"B_c = {bc:.1f} m", dx=0.5)
    _dim_v(fig, x_tim + B_tk/2 + 1.2, -B_tk/2, B_tk/2, f"B_tk = {B_tk:.1f} m",
           color="#e74c3c", dx=0.5)

    fig.update_layout(
        title=dict(
            text=(f"BÌNH ĐỒ CẦU — {n_nhip} nhịp | L={L_cau:.1f}m | B_c={bc:.1f}m"
                  + (f" | Góc xiên α={goc:.0f}°" if goc < 89.0 else "")),
            x=0.5, font=dict(size=12)
        ),
        xaxis=dict(title="Lý trình (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5,
                   scaleanchor="y", scaleratio=1),
        yaxis=dict(title="Ngang (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5),
        height=420, template="plotly_white",
        legend=dict(orientation="h", y=-0.22, font=dict(size=9)),
        margin=dict(l=60, r=40, t=60, b=90),
        hovermode="closest",
    )
    _apply_layers_2d(fig)
    return fig


# ===========================================================================
# 8. MẶT CẮT NGANG TẠI VỊ TRÍ MỐ / TRỤ
# ===========================================================================
def ve_mcn_vi_tri(d, vi_tri='mo_trai', df_geology=None, pier_assembly=None,
                  x_half=None, abutment_assembly=None, mo_view='truoc',
                  beam_mcn_outer=None, df_tim_line=None,
                  beam_centers=None, draw_own_beams=True):
    """
    MCN cắt vuông góc tim cầu tại vị trí mố hoặc trụ cụ thể.
    vi_tri: 'mo_trai' | 'mo_phai' | 'tru_1' | 'tru_2' | ...
    df_geology: DataFrame với cột Lý trình, Offset, Z (từ file .NTD)
    abutment_assembly: mố lắp ghép thư viện → cắt MCN theo mố mới (thay mố cũ).
    mo_view: 'truoc' = MCN TRƯỚC mố (nhìn từ sông) | 'sau' = MCN SAU mố (nhìn từ
             tuyến về sông) — đổi nét thấy/khuất + tiêu đề tương ứng.
    """
    kcn   = d.get("kcn_result") or d.get("ai_result", {})
    geo   = d.get("geo_logic", {})
    tru_r = d.get("tru_result", {}) or {}
    mong  = d.get("mong_result", {}) or {}

    bc_raw = float(d.get("bc", 12.0))
    # Góc xiên: mặt cắt ngang mố/trụ vẽ theo bề rộng THẬT dọc trục xiên = bc/sin(α)
    _wsk   = _skew_widen(d)
    bc     = bc_raw * _wsk
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
    L_nhip = float(kcn.get("chieu_dai", 33.0) or 33.0)
    supports, L_std = resolve_supports(d, x0, x_end, x_tim, B_tk, L_nhip)
    x0, x_end = supports[0], supports[-1]
    piers  = supports[1:-1]
    n_nhip = len(supports) - 1
    cap_W  = max(2.0, bc * 0.18 + 1.0)
    be_W   = cap_W + 0.8

    _mo_suffix = (" — SAU MỐ (nhìn từ tuyến)" if mo_view == 'sau'
                  else " — TRƯỚC MỐ (nhìn từ sông)")
    if vi_tri == 'mo_trai':
        x_cut = x0;   title_vt = "MỐ M1" + _mo_suffix
    elif vi_tri == 'mo_phai':
        x_cut = x_end; title_vt = "MỐ M2" + _mo_suffix
    else:
        idx = int(vi_tri.replace('tru_', '')) - 1
        x_cut = piers[idx] if idx < len(piers) else x_tim
        title_vt = f"TRỤ T{idx + 1}"

    # CAO ĐỘ ĐẶT DẦM DÙNG CHUNG với trắc dọc & 3D: đáy dầm theo ĐƯỜNG ĐỎ
    # (make_red_line) tại ĐÚNG lý trình cắt → MCN · trắc dọc · 3D KHÔNG lệch nhau.
    try:
        _zred_mcn, _, _, _tb_mcn, _hd_mcn = make_red_line(d)
        cao_dd = _zred_mcn(x_cut) - t_ban - H_dam
    except Exception:
        pass
    # ĐTN tại lý trình cắt (DÙNG CHUNG 3D & trắc dọc) → móng bám địa hình.
    z_ground = _terrain_z_at(d, df_geology, x_cut, df_tim_line)
    # Đỉnh bệ TRỤ đồng bộ 3 view: min(ĐTN−0.5, đáy dầm−1.0) + snap toàn cầu.
    _be_top_sync = None
    if not vi_tri.startswith('mo'):
        try:
            _tfn_m = lambda _x: _terrain_z_at(d, df_geology, _x, df_tim_line)
            _sfn_m = lambda _x: _zred_mcn(_x) - t_ban - H_dam
            _be_top_sync = _pier_be_tops_synced(piers, _tfn_m, _sfn_m).get(
                round(x_cut, 3))
        except Exception:
            _be_top_sync = None

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
    # THỨ TỰ CAO ĐỘ TỪ ĐƯỜNG ĐỎ XUỐNG: đường đỏ = đỉnh bản mặt cầu → bản mặt cầu
    # (dày t_ban) → dầm (H_dam) → đá kê gối (h_goi) → tường thân mố/xà mũ.
    z_deck = cao_dd + H_dam + t_ban    # đỉnh bản mặt cầu = ĐƯỜNG ĐỎ (tại TIM)
    z_ban_b = cao_dd + H_dam           # đáy bản = ĐỈNH dầm (tại TIM)
    h_goi_v = max(0.12, _h_goi(d))     # chiều cao đá kê gối (gối + đá kê)
    # ĐÁY dầm = cao_dd (THIẾT KẾ) — ĐỒNG BỘ với TRẮC DỌC & 3D (không lấy chiều cao
    # mặt cắt thư viện làm mốc, tránh lệch cao độ). Mặt cắt dầm co về chiều cao
    # H_dam (từ đáy dầm cao_dd tới đáy bản) để nằm gọn dưới bản, không trồi lên.
    _bm_all = (beam_mcn_outer or {}).get("outer") if beam_mcn_outer else None
    if _bm_all:
        _bz_h = [p[1] for p in _bm_all]
        _H_sec = (max(_bz_h) - min(_bz_h)) / 1000.0
    else:
        _H_sec = H_dam
    # ĐÁY dầm = đỉnh dầm (đáy bản) − chiều cao mặt cắt THẬT → dầm vẽ ĐẦY ĐỦ hình
    # (KHÔNG bóp dẹt, KHÔNG cắt). Xà mũ tự có VAI KÊ (kê dầm) + Ụ GIỮA (nhô, đỡ
    # bản) do model dựng khi neo vai kê = đáy dầm này.
    _z_beam_soffit = z_ban_b - _H_sec        # đáy dầm = mức VAI KÊ (dầm đầy đủ)
    # ĐỘ DỐC NGANG mặt cầu (đồng bộ MCN điển hình & 3D): crown tại tim (x=0), hạ
    # dần ra mép. Bản/dầm/đá kê gối/lan can bám dốc; xà mũ/thân mố giữ ĐỈNH PHẲNG
    # (đá kê gối cao thấp khác nhau để tạo dốc — đúng cấu tạo).
    _i_ng = float(d.get("i_doc_ngang", 2.0)) / 100.0
    def _off(x):
        return -abs(x) * _i_ng

    # Bố trí dầm (ngang) — DÙNG CHUNG bố trí với MCN điển hình & 3D: ưu tiên
    # beam_centers (từ mcn_beam_centers = _fit_beam_centers, đã chia đều + hở lan
    # can). Thiếu → căn đối xứng theo kc (×_wsk theo góc xiên).
    _ndam_g = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5) or 5)
    _kcd_g  = float(kcn.get("khoang_cach_dam", 2.2) or 2.2) * _wsk
    if beam_centers and len(beam_centers) >= 1:
        _beam_cx = [float(c) * _wsk for c in beam_centers]   # nới theo góc xiên
        _ndam_g  = len(_beam_cx)
    else:
        _oh_g   = float(kcn.get("overhang", 0.5) or 0.5) * _wsk
        _xf_g   = -bc/2 + _oh_g
        if _ndam_g >= 2 and (_xf_g + (_ndam_g - 1) * _kcd_g) > bc/2:
            _xf_g = -(_ndam_g - 1) * _kcd_g / 2.0
        _beam_cx = [_xf_g + i * _kcd_g for i in range(_ndam_g)]

    def _draw_da_ke_goi(z_seat_top, yr, hidden=False):
        """Đá kê gối tại từng vị trí dầm: ĐÁY tại đỉnh xà mũ/thân mố (PHẲNG =
        z_seat_top−h_goi_v), ĐỈNH bám đáy dầm dốc = z_seat_top+_off(x). z_seat_top
        = đáy dầm tại TIM; chỉ vẽ trong bề rộng đỡ dầm yr=(y0,y1)."""
        _wg = 0.50; _sh = False
        _z_bot = z_seat_top - h_goi_v          # đỉnh xà mũ/thân mố (phẳng)
        for _xc in _beam_cx:
            if not (yr[0] + 0.05 <= _xc <= yr[1] - 0.05):
                continue
            _z_top = z_seat_top + _off(_xc)     # đáy dầm (bám dốc ngang)
            _poly(fig, [_xc - _wg/2, _xc + _wg/2, _xc + _wg/2, _xc - _wg/2],
                  [_z_bot, _z_bot, _z_top, _z_top],
                  ("rgba(0,0,0,0)" if hidden else "#7f8c8d"),
                  ("#1f9ed1" if hidden else "#2c3e50"),
                  "Đá kê gối" if not _sh else "", showlegend=(not _sh),
                  dash=("dash" if hidden else None), lw=1.2)
            _sh = True

    if is_mo:
        if abutment_assembly:
            # MCN cắt theo MỐ THƯ VIỆN: vai kê = đáy dầm, đáy bệ = ĐTN−0.5.
            _PBa = _get_PB()
            _z_base_mo = z_ground - 0.5      # ĐTN tại lý trình (đồng bộ 3D)
            _is_back = (mo_view == 'sau')
            # ĐÁY dầm = đáy bản − chiều cao dầm THẬT (dầm nằm HẲN dưới bản). Đỉnh
            # tường thân mố HẠ xuống dưới đáy dầm đúng chiều cao đá kê gối → chừa
            # chỗ đặt gối; vai kê mố thấp lại (theo yêu cầu).
            _seat_mo = _z_beam_soffit                     # đáy dầm tại mố
            _z_body_top = _z_beam_soffit - h_goi_v        # ĐỈNH tường thân mố
            # MỐ = 1 KHỐI THỐNG NHẤT: vẽ mọi đoạn (thân + cánh); nét thấy/khuất
            # đảo theo hướng nhìn (trước = từ sông, sau = từ tuyến về sông).
            _mcn_pl = _PBa.abutment_mcn_polys(
                abutment_assembly, z_seat=_z_body_top, z_base=_z_base_mo,
                target_width=bc, back=_is_back)  # co bề rộng mố theo bề rộng cầu
            # Vẽ SAU mố (nét khuất) trước → THÂN/BỆ (nét thấy) đè lên trên.
            _mcn_pl.sort(key=lambda p: 0 if p.get("hidden") else 1)
            _seen_mo = set()
            for _pl in _mcn_pl:
                _hid = _pl.get("hidden"); _nm = _pl["name"]
                _sl = _nm not in _seen_mo; _seen_mo.add(_nm)
                _poly(fig, _pl["ys"], _pl["zs"],
                      ("rgba(0,0,0,0)" if _hid else _pl["color"]),
                      ("#1f9ed1" if _hid else _C["be_dk"]),
                      _nm if _sl else "", showlegend=_sl,
                      dash=("dash" if _hid else None))
            # ── NÉT VAI KÊ DẦM: bệ đỡ đáy dầm tại đỉnh thân mố + đá kê gối từng
            # dầm. Trước mố = NÉT THẤY (mặt kê quay ra sông); sau mố = NÉT KHUẤT.
            _mw = bc / 2.0
            # Bề rộng thân mố (đoạn rộng nhất) = vùng kê dầm (giữa 2 tường cánh).
            _body_yr = max(((min(p["ys"]), max(p["ys"])) for p in _mcn_pl),
                           key=lambda r: r[1] - r[0], default=(-_mw, _mw))
            _seat_dash = "dash" if _is_back else None
            _seat_col  = "#e67e22"
            # Đường vai kê (đáy dầm MỐ = đỉnh đá kê gối) chạy suốt bề rộng kê
            fig.add_trace(go.Scatter(
                x=[_body_yr[0], _body_yr[1]], y=[_seat_mo, _seat_mo], mode="lines",
                line=dict(color=_seat_col, width=2.2, dash=_seat_dash),
                name="Vai kê dầm (đáy dầm)", showlegend=True))
            # Đá kê gối tại từng vị trí dầm: NẰM DƯỚI đáy dầm, TRÊN đỉnh thân mố.
            _draw_da_ke_goi(_seat_mo, _body_yr, hidden=_is_back)
            # Vai kê bản quá độ (mặt sau mố) — nét chỉ dẫn
            fig.add_trace(go.Scatter(
                x=[-_mw, _mw], y=[cao_dd + 1.0, cao_dd + 1.0], mode="lines",
                line=dict(color="#9b59b6", width=1.2, dash="dot"),
                name="Vai kê bản quá độ", showlegend=True))
            _zbe_bot = min((z for p in _mcn_pl for z in p["zs"]), default=_z_base_mo)
            _piles_mo_vt = _layout_piles(d, vi_tri)
            if _piles_mo_vt:
                _draw_piles_section(
                    fig, _piles_mo_vt, x_center=0.0, z_top=_zbe_bot,
                    color="#7d5a32", legend_name=f"Cọc ({len(_piles_mo_vt)} cọc)")
        else:
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
            # Cọc khai báo từ DXF (nếu có) — đỉnh cọc tại đáy thân mố
            _piles_mo_vt = _layout_piles(d, vi_tri)
            if _piles_mo_vt:
                _draw_piles_section(
                    fig, _piles_mo_vt, x_center=0.0, z_top=h_tn,
                    color="#7d5a32", legend_name=f"Cọc ({len(_piles_mo_vt)} cọc)")
    else:
        # TRỤ: xà mũ Super-T có VAI KÊ (khối THẤP 2 bên) kê đầu dầm khấc + Ụ GIỮA
        # (khối CAO NHẤT) đỡ bản mặt cầu. pier_mcn_polys tự dựng chênh cao này khi
        # neo z_top = ĐÁY DẦM (mức VAI KÊ) → dầm ngồi trên vai kê, ụ giữa nhô lên.
        cap_H  = 0.80; be_H = 1.50
        z_cap_t = _z_beam_soffit              # mức VAI KÊ = đáy dầm (ụ giữa do model nhô)
        z_capb = z_cap_t - cap_H
        # THÂN TRỤ KÉO GIÃN theo ĐTN tại lý trình (đồng bộ 3D & trắc dọc qua
        # _pier_be_tops_synced): đỉnh bệ có SNAP toàn cầu, luôn dưới đáy xà mũ ≥0.5m.
        z_shb  = _be_top_sync if _be_top_sync is not None else (z_ground - 0.5)
        z_shb  = min(z_shb, z_capb - 0.5)
        H_tru  = max(0.5, z_capb - z_shb)
        z_beb  = z_shb - be_H

        if pier_assembly:
            # TRỤ LẮP GHÉP: MCN = LÁT CẮT NGANG THẬT của LƯỚI 3D (cùng
            # build_pier_mesh_traces với 3D & trắc dọc), cắt tại tim trụ
            # (cut_mesh_traces axis="x") → xà mũ (ụ giữa đỡ bản) + 2 thân + bệ hiện
            # ĐÚNG như 3D. Cap co bề rộng = bc; ĐỈNH ụ giữa neo ĐÁY BẢN (z_ban_b).
            _PBm = _get_PB()
            _wmap = (d or {}).get("_pier_cap_widen") or {}
            _w0   = float((d or {}).get("_pier_cap_W0", 0) or 0)
            _mid_extra = max(0.0, _wmap.get(round(x_cut, 3), _w0) - _w0)
            _ptr = _PBm.build_pier_mesh_traces(
                pier_assembly, H_tru=(z_ban_b - z_beb), x_ctr=0.0, z_base=z_beb,
                cap_width=bc, cap_mid_extra=_mid_extra)
            _polys = cut_mesh_traces(_ptr, axis="x", value=0.0)  # ngang: (y,z)
            _seen = set()
            for _pl in _polys:
                _nm = _pl["name"].split(" #")[0]
                _sl = _nm not in _seen; _seen.add(_nm)
                _poly(fig, _pl["xs"], _pl["zs"], _pl["color"], _C["btong_dk"],
                      _nm if _sl else "", showlegend=_sl)
            # KHỐI GÁC DẦM (vai kê): cắt lưới tại đoạn VAI KÊ (thấp hơn ụ giữa, lệch
            # tim theo dọc cầu) → thấy mức kê đầu dầm khấc. Vẽ NÉT LIỀN BÊ TÔNG (đầu
            # dầm khấc kê lên). CÙNG lưới 3D nên khớp tuyệt đối.
            try:
                _seat_leg = True
                for _sx in _PBm.cap_seat_x_centers(
                        pier_assembly, x_ctr=0.0, cap_mid_extra=_mid_extra):
                    for _rc in cut_mesh_traces(_ptr, axis="x", value=_sx):
                        if _rc["name"].split(" #")[0] != "Xà mũ":
                            continue
                        _poly(fig, _rc["xs"], _rc["zs"], _C["btong"],
                              _C["btong_dk"],
                              "Vai kê gác dầm" if _seat_leg else "",
                              showlegend=_seat_leg, lw=1.3)
                        _seat_leg = False
            except Exception:
                pass
            _allx = [x for pl in _polys for x in pl["xs"]]
            if _allx:
                be_W = max(be_W, abs(min(_allx)), abs(max(_allx)))
            _capx = [x for pl in _polys if pl["name"].split(" #")[0] in ("Xà mũ",)
                     for x in pl["xs"]]
            _capy = [y for pl in _polys if pl["name"].split(" #")[0] in ("Xà mũ",)
                     for y in pl["zs"]]
            _bex  = [x for pl in _polys if pl["name"].split(" #")[0] == "Bệ trụ"
                     for x in pl["xs"]]
            _bey  = [y for pl in _polys if pl["name"].split(" #")[0] == "Bệ trụ"
                     for y in pl["zs"]]
            _thy  = [y for pl in _polys if pl["name"].split(" #")[0] == "Thân trụ"
                     for y in pl["zs"]]
            if _capx:
                cap_W = max(abs(min(_capx)), abs(max(_capx)))
            _ally = [y for pl in _polys for y in pl["zs"]]
            if _ally:
                z_beb = min(z_beb, min(_ally))
            # (Dầm ĐẦU KHẤC lọt thẳng vào khấc xà mũ — KHÔNG vẽ đá kê gối riêng.)
            # KÍCH THƯỚC trụ lắp ghép: bề rộng & chiều cao từng bộ phận
            _xd = (max(_capx) if _capx else cap_W) + 0.9
            if _capx and _capy:
                _dim_h(fig, max(_capy) + 0.55, min(_capx), max(_capx),
                       f"B_xà mũ={max(_capx)-min(_capx):.2f}m", color="#8e44ad")
                _dim_v(fig, _xd, min(_capy), max(_capy),
                       f"xà mũ {max(_capy)-min(_capy):.2f}m", dx=0.15)
            if _thy:
                _dim_v(fig, _xd, min(_thy), max(_thy),
                       f"thân {max(_thy)-min(_thy):.2f}m", dx=0.15)
            if _bex and _bey:
                _dim_v(fig, _xd, min(_bey), max(_bey),
                       f"bệ {max(_bey)-min(_bey):.2f}m", dx=0.15)
                _dim_h(fig, min(_bey) - 0.55, min(_bex), max(_bex),
                       f"B_bệ={max(_bex)-min(_bex):.2f}m")
        else:
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

            # Xà mũ (đỉnh = z_cap_t = đáy dầm; dầm kê trên vai kê)
            _poly(fig, [-cap_W, cap_W, cap_W, -cap_W],
                  [z_capb, z_capb, z_cap_t, z_cap_t],
                  _C["btong"], _C["dam_dk"], "Xà mũ")


        # Cọc — ưu tiên sơ đồ cọc khai báo từ DXF (mặt cắt ngang: chiếu trục ngang)
        _piles_vt = _layout_piles(d, vi_tri)
        if _piles_vt:
            _draw_piles_section(
                fig, _piles_vt, x_center=0.0, z_top=z_beb, color=_C["be_dk"],
                legend_name=f"Cọc ({len(_piles_vt)} cọc)")
        else:
            # Lưới cọc Module 08: MCN (ngang cầu) thấy n_cols cọc, tim-tim S.
            _mg_xs, _, D_coc, L_coc, _ = mong_pile_grid(mong)
            for i_coc, xc in enumerate(_mg_xs):
                fig.add_trace(go.Scatter(
                    x=[xc, xc], y=[z_beb, z_beb - L_coc],
                    mode="lines",
                    line=dict(color=_C["be_dk"], width=max(3, int(D_coc * 6))),
                    name=f"Cọc Ø{int(D_coc*1000)}mm" if i_coc == 0 else "",
                    showlegend=(i_coc == 0)
                ))

        # Dimensions trụ (parametric) — chỉ khi CHƯA gắn trụ lắp ghép
        if not pier_assembly:
            _dim_v(fig, cap_W + 0.6, z_shb, z_capb, f"H_trụ={H_tru:.1f}m", dx=0.2)
            _dim_h(fig, z_beb - 0.5, -be_W, be_W, f"B_bệ={be_W*2:.1f}m", dy=0)

    # ── Dầm chủ (mặt cắt ngang) — MẶT CẮT DẦM THỰC từ thư viện (beam_mcn_outer);
    # ĐỈNH dầm sát ĐÁY BẢN (dầm nằm HẲN dưới bản, không trồi lên), đáy dầm =
    # _z_beam_soffit. Vị trí dùng chung _beam_cx (đã ×_wsk) để dầm ⟷ đá kê gối
    # trùng khớp. KHÔNG vẽ 'hộp' cũ.
    # draw_own_beams=False → dầm được OVERLAY từ get_mcn_overlay_traces(which="end")
    # ở nơi gọi (đúng MẶT CẮT ĐẦU DẦM KHẤC + cắt cánh, LÁT CẮT thật của 3D).
    _bm_out = (beam_mcn_outer or {}).get("outer") if (beam_mcn_outer and draw_own_beams) else None
    if not draw_own_beams:
        pass                                  # dầm do nơi gọi overlay (lát cắt 3D)
    elif _bm_out:
        # Mặt cắt thư viện: z 0 ở đỉnh, âm xuống đáy. Vẽ ĐẦY ĐỦ hình (KHÔNG co,
        # KHÔNG cắt): neo ĐỈNH dầm sát đáy bản → đáy dầm = _z_beam_soffit (= vai kê).
        _bx   = [p[0] for p in _bm_out]; _bz = [p[1] for p in _bm_out]
        _bxc  = (min(_bx) + max(_bx)) / 2.0        # căn tim ngang
        _bzmax = max(_bz)                          # đỉnh dầm (z lớn nhất, ~0)
        _holes = (beam_mcn_outer or {}).get("holes") or []
        for _id, _xc in enumerate(_beam_cx):
            _dz = _off(_xc)                        # dầm bám dốc ngang mặt cầu
            _xs = [_xc + (px - _bxc) / 1000.0 for px in _bx]
            _zs = [z_ban_b + _dz + (pz - _bzmax) / 1000.0 for pz in _bz]  # đỉnh=đáy bản
            _poly(fig, _xs, _zs, _C["dam"], _C["dam_dk"],
                  "Dầm chủ (thư viện)" if _id == 0 else "", showlegend=(_id == 0))
            for _h in _holes:                      # lỗ rỗng (dầm hộp/Super-T)
                _hx = [_xc + (q[0] - _bxc) / 1000.0 for q in _h]
                _hz = [z_ban_b + _dz + (q[1] - _bzmax) / 1000.0 for q in _h]
                _poly(fig, _hx, _hz, "rgba(0,0,0,0)", _C["dam_dk"], "",
                      showlegend=False, lw=0.8)
    else:
        # Chưa có dầm thư viện → CHỈ vẽ ký hiệu tim dầm (không dựng dầm cũ).
        for _id, _xc in enumerate(_beam_cx):
            _dz = _off(_xc)
            fig.add_trace(go.Scatter(
                x=[_xc, _xc], y=[_z_beam_soffit + _dz, z_ban_b + _dz],
                mode="lines", line=dict(color=_C["dam_dk"], width=1, dash="dot"),
                name="Tim dầm" if _id == 0 else "", showlegend=(_id == 0)))

    # Bản mặt cầu — theo ĐƯỜNG ĐỎ, dày t_ban, BÁM ĐỘ DỐC NGANG (crown tại tim).
    _poly(fig, [-bc/2, 0, bc/2, bc/2, 0, -bc/2],
          [z_ban_b + _off(-bc/2), z_ban_b, z_ban_b + _off(bc/2),
           z_deck + _off(bc/2), z_deck, z_deck + _off(-bc/2)],
          _C["ban"], _C["btong_dk"], "Bản mặt cầu")

    # ── Lan can (mặt cắt thư viện) — ĐẶT TRÊN BẢN MẶT CẦU, mặt ngoài tại ±bc/2 ──
    _rails_vt = _resolve_railings(d)
    _lc_vt = (_rails_vt or {}).get("lan_can")
    if _lc_vt and _lc_vt.get("outer"):
        _pm0 = [[p[0] / 1000.0, p[1] / 1000.0] for p in _lc_vt["outer"]]
        _pm, _ye_vt, _bz_vt = _rail_place(_pm0, bc)   # move khối + drape ra mép
        for sy in (-1, 1):
            _zed = z_deck + _off(sy * bc/2)           # đỉnh bản tại mép (dốc)
            xs = [sy * (yy + _ye_vt) for yy, _ in _pm]
            zs = [_zed + zz - _bz_vt for _, zz in _pm]
            _poly(fig, xs, zs, _C["lan_can"], "#2c3e50",
                  "Lan can" if sy == -1 else "", showlegend=(sy == -1))
    else:
        for sy in [-1, 1]:            # fallback: ký hiệu hộp tham số cũ
            _zed = z_deck + _off(sy * bc/2)
            _poly(fig,
                  [sy * bc/2 - sy*0.3, sy * bc/2, sy * bc/2, sy * bc/2 - sy*0.3],
                  [_zed, _zed, _zed + 1.1, _zed + 1.1],
                  _C["lan_can"], "#2c3e50",
                  "Lan can" if sy == -1 else "", showlegend=(sy == -1))

    # ── Giải phân cách giữa (nếu tiêu chuẩn yêu cầu) — đặt tim, trên bản mặt cầu ─
    _gpc_vt = (_rails_vt or {}).get("giai_phan_cach")
    if _gpc_vt and _gpc_vt.get("outer"):
        _pg_vt = [[p[0] / 1000.0, p[1] / 1000.0] for p in _gpc_vt["outer"]]
        _zg = min(z for _, z in _pg_vt)
        _poly(fig, [yy for yy, _ in _pg_vt], [z_deck + zz - _zg for _, zz in _pg_vt],
              _C["lan_can"], "#2c3e50", "Giải phân cách", showlegend=True)

    # Dimensions chung — khi xiên: ghi bề rộng THẬT dọc trục xiên = bc/sin(α)
    _blbl = (f"B_xiên = {bc:.2f} m (Bc {bc_raw:.1f}/sin{float(d.get('goc_giao',90)):.0f}°)"
             if _wsk > 1.001 else f"B_cầu = {bc:.1f} m")
    _dim_h(fig, z_deck + 1.5, -bc/2, bc/2, _blbl, dy=0)
    if not is_mo:
        _dim_h(fig, z_deck + 2.2, -cap_W, cap_W, f"B_xà mũ = {cap_W*2:.1f} m",
               color="#8e44ad", dy=0)

    # Khung nhìn: bám theo kết cấu (không để địa hình rộng kéo dãn khung).
    # x_half: nếu cho → ép tầm nhìn ngang chung (thẳng trục với mặt bằng kết cấu).
    _Xv = float(x_half) if x_half else (max(bc / 2, B_tk / 2, be_W, cap_W) + 4.0)
    fig.update_layout(
        title=dict(
            text=f"MẶT CẮT NGANG — {title_vt} | Lý trình ≈ {x_cut:.1f} m",
            x=0.5, font=dict(size=12)
        ),
        xaxis=dict(title="Ngang cầu (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5,
                   range=[-_Xv, _Xv]),
        # MCN là mặt cắt true-shape → khóa tỉ lệ 1:1 cho khỏi méo hình trụ.
        yaxis=dict(title="Cao độ (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5,
                   scaleanchor="x", scaleratio=1),
        height=480, template="plotly_white",
        legend=dict(orientation="h", y=-0.20, font=dict(size=9)),
        margin=dict(l=60, r=40, t=60, b=100),
    )
    _add_elevation_table(fig, d, loc="tr")
    _apply_layers_2d(fig)
    return fig


# ===========================================================================
# 8b. BỐ HÌNH MỐ – TRỤ THEO VỊ TRÍ — 4 hình: mặt bằng KC, mặt bằng cọc,
#     mặt cắt ngang (ở trên), mặt cắt dọc. Dùng chung 1 bộ hình học _pos_geometry.
# ===========================================================================
def _pos_geometry(d, vi_tri, pier_assembly=None, df_geology=None, df_tim_line=None):
    """Tập hợp toàn bộ kích thước/hình học cho 1 vị trí (mố/trụ) — dùng chung
    cho cả 4 hình để đảm bảo nhất quán. Kích thước theo DỌC cầu suy từ sơ đồ
    cọc khai báo (nếu có), nếu không dùng mặc định.
    pier_assembly: nếu có → lấy chiều cao xà mũ/bệ THẬT (thay 0.80/1.50 cũ).
    df_geology: khảo sát → cao độ dầm bám ĐƯỜNG ĐỎ tại lý trình + móng bám ĐỊA
    HÌNH tại vị trí (ĐỒNG BỘ mô hình 3D thực, không tự vẽ cao độ độc lập)."""
    kcn   = d.get("kcn_result") or d.get("ai_result", {})
    geo   = d.get("geo_logic", {})
    tru_r = d.get("tru_result", {}) or {}
    mong  = d.get("mong_result", {}) or {}

    bc     = float(d.get("bc", 12.0))
    B_tk   = float(d.get("B", 20.0))
    H_tru  = float(d.get("H_tru_est", 5.0))
    cao_dd = float(d.get("cao_day_dam", H_tru + 5.0))
    H_dam  = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    t_ban  = float(d.get("t_ban_mm", 200)) / 1000.0
    h_tn   = float(d.get("h_tn_tb", 2.0))
    L_cau  = float(geo.get("L_cau", 120))
    x0     = float(geo.get("x_mo_trai", -L_cau / 2))
    x_end  = float(geo.get("x_mo_phai", x0 + L_cau))
    x_tim  = float(geo.get("x_tim_clearance", (x0 + x_end) / 2))
    L_nhip = float(kcn.get("chieu_dai", 33.0) or 33.0)
    supports, _ = resolve_supports(d, x0, x_end, x_tim, B_tk, L_nhip)
    x0, x_end = supports[0], supports[-1]
    piers = supports[1:-1]

    cap_W = max(2.0, bc * 0.18 + 1.0)   # nửa BỀ RỘNG xà mũ (ngang)
    be_W  = cap_W + 0.8                  # nửa BỀ RỘNG bệ cọc (ngang)
    cap_H = 0.80; be_H = 1.50            # mặc định khi chưa lắp trụ thật
    if pier_assembly:                    # lấy chiều cao xà mũ/bệ THẬT
        _PB = _get_PB()
        _pp = _PB.migrate_pier(pier_assembly).get("parts", {})
        cap_H = _PB._part_height_m(_pp.get("xa_mu", {}), "xa_mu") or cap_H
        _bl = _PB.stem_layers_of(_pp.get("be", {}))
        be_H = (_PB.stem_total_height(_bl) if _bl
                else float(_pp.get("be", {}).get("H", be_H))) or be_H

    is_mo = str(vi_tri).startswith("mo")
    if vi_tri == "mo_trai":
        x_cut = x0;   title_vt = "MỐ M1"
    elif vi_tri == "mo_phai":
        x_cut = x_end; title_vt = "MỐ M2"
    else:
        idx = int(str(vi_tri).replace("tru_", "")) - 1
        x_cut = piers[idx] if idx < len(piers) else x_tim
        title_vt = f"TRỤ T{idx + 1}"

    # ── CAO ĐỘ DẦM DÙNG CHUNG với trắc dọc & 3D: đáy dầm theo ĐƯỜNG ĐỎ
    #    (make_red_line) tại ĐÚNG lý trình cắt → mặt cắt chi tiết = "lát cắt" thật
    #    của 3D, KHÔNG lấy cao_dd đỉnh (phẳng) làm mốc. ──
    try:
        _zred_pg, _, _, _tb_pg, _hd_pg = make_red_line(d)
        cao_dd = _zred_pg(x_cut) - t_ban - H_dam
    except Exception:
        pass

    h_goi  = _h_goi(d)               # chiều cao gối/đá kê gối
    z_deck = cao_dd + H_dam + t_ban
    z_dam_b = cao_dd                 # đáy dầm
    # ĐỒNG BỘ với TRẮC DỌC & 3D (ve_so_do_nhip_2d): TRỤ dầm ĐẦU KHẤC lọt vào khấc
    # → ĐỈNH xà mũ = đáy dầm + độ sâu khấc; MỐ đầu trơn kê đá kê gối → đỉnh thân
    # mố = đáy dầm − đá kê gối. (Trước đây detail lấy cao_dd−h_goi cho cả hai nên
    # LỆCH cao độ so với bố trí chung/3D.)
    try:
        _notch_pg = (_get_PB().cap_seat_notch_depth_m(pier_assembly)
                     if pier_assembly else 0.0) or 0.0
    except Exception:
        _notch_pg = 0.0
    z_cap_t = (cao_dd - h_goi) if is_mo else (cao_dd + _notch_pg)
    z_capb = z_cap_t - cap_H
    # ── MÓNG BÁM ĐỊA HÌNH TẠI VỊ TRÍ (đồng bộ 3D & trắc dọc): đỉnh bệ TRỤ dùng
    #    CHUNG _pier_be_tops_synced (min(ĐTN−0.5, đáy dầm−1.0) + snap); MỐ = ĐTN−0.5.
    #    Thân KÉO GIÃN theo địa hình (không dùng H_tru phẳng). ──
    z_ground = _terrain_z_at(d, df_geology, x_cut, df_tim_line)
    if is_mo:
        z_shb = min(z_ground - 0.5, z_capb - 0.5)
    else:
        try:
            _tfn = lambda _x: _terrain_z_at(d, df_geology, _x, df_tim_line)
            _sfn = lambda _x: _zred_pg(_x) - t_ban - H_dam
            _bmap = _pier_be_tops_synced(piers, _tfn, _sfn)
            z_shb = _bmap.get(round(x_cut, 3), min(z_ground - 0.5, cao_dd - 1.0))
        except Exception:
            z_shb = min(z_ground - 0.5, cao_dd - 1.0)
        z_shb = min(z_shb, z_capb - 0.5)      # luôn dưới đáy xà mũ ≥0.5m
    z_beb  = z_shb - be_H
    H_tru  = max(0.5, z_capb - z_shb)         # chiều cao thân THẬT (kéo theo ĐTN)

    # Thân cột (trụ)
    loai_t = str(tru_r.get("loai_tru", "Thân cột 2 trụ"))
    n_cot  = 3 if "3" in loai_t else (2 if "cột" in loai_t.lower() else 1)
    W_cot  = min(1.0, bc * 0.06 + 0.4)
    col_offs = list(np.linspace(-cap_W * 0.6, cap_W * 0.6, n_cot))

    # Cọc khai báo + kích thước theo DỌC cầu
    piles = _layout_piles(d, vi_tri)
    D_coc = mong_dims(mong)[0]
    L_coc = mong_dims(mong)[1]
    if piles:
        Dmax = max(p["D"] for p in piles)
        ys = [p["y"] for p in piles]; xs = [p["x"] for p in piles]
        be_half_doc   = max(abs(min(ys)), abs(max(ys))) + 0.75 * Dmax
        be_half_ngang = max(be_W, max(abs(min(xs)), abs(max(xs))) + 0.75 * Dmax)
    else:
        # BỆ THẬT làm GỐC (đồng bộ 3D): mố → bệ mố thư viện (co theo bc);
        # trụ → bệ hệ trụ (mong đã sync theo footing_dims_m ở Interface).
        _bn = float(mong.get("Be_ngang") or 0)
        _bd = float(mong.get("Be_doc") or 0)
        if is_mo and d.get("_mo_model"):
            try:
                _bnm, _bdm = _get_PB().abut_footing_dims_m(
                    d["_mo_model"], target_width=bc)
                if _bnm > 0.5 and _bdm > 0.3:
                    _bn, _bd = _bnm, _bdm
            except Exception:
                pass
        be_half_doc   = (_bd / 2.0) if _bd > 0 else max(1.6, be_W * 0.5)
        be_half_ngang = max(be_W, _bn / 2.0) if _bn > 0 else be_W
    cap_half_doc = max(0.8, min(be_half_doc * 0.85, H_dam * 0.55 + 0.45))

    return dict(
        bc=bc, B_tk=B_tk, H_tru=H_tru, H_dam=H_dam, t_ban=t_ban, h_tn=h_tn,
        z_ground=z_ground,
        cao_dd=cao_dd, z_deck=z_deck, z_capb=z_capb, z_shb=z_shb, z_beb=z_beb,
        z_cap_t=z_cap_t, z_dam_b=z_dam_b, h_goi=h_goi,
        cap_W=cap_W, be_W=be_W, cap_H=cap_H, be_H=be_H,
        is_mo=is_mo, x_cut=x_cut, title_vt=title_vt,
        n_cot=n_cot, W_cot=W_cot, col_offs=col_offs, loai_t=loai_t,
        piles=piles, D_coc=D_coc, L_coc=L_coc, mong=mong,
        be_half_doc=be_half_doc, be_half_ngang=be_half_ngang,
        cap_half_doc=cap_half_doc,
    )


def _circle(fig, xc, yc, r, line_c, fill, name="", showlegend=False):
    fig.add_shape(type="circle", xref="x", yref="y",
                  x0=xc - r, y0=yc - r, x1=xc + r, y1=yc + r,
                  line=dict(color=line_c, width=1.5), fillcolor=fill, layer="above")
    if name:
        fig.add_trace(go.Scatter(
            x=[xc], y=[yc], mode="markers",
            marker=dict(size=0.1, color=fill),
            name=name, showlegend=showlegend, hoverinfo="skip"))


def _auto_pile_grid(g):
    """Lưới cọc khi chưa khai DXF — LẤP ĐẦY BỆ THẬT của vị trí (gốc 3D:
    be_half_ngang/doc từ hệ trụ/mố lắp ghép) với tim-tim ≥ tối thiểu TCVN;
    D/L từ Module 08. Bệ rộng → nhiều cọc, bệ hẹp → ít — luôn khớp bệ."""
    xs, ys, D, L, _S = mong_pile_grid(
        g.get("mong"),
        be_ngang=2.0 * float(g.get("be_half_ngang") or 0),
        be_doc=2.0 * float(g.get("be_half_doc") or 0))
    out = []
    for yy in ys:
        for xx in xs:
            out.append({"x": float(xx), "y": float(yy), "D": D,
                        "L": L, "ix": 0.0, "iy": 0.0})
    return out


def ve_mat_bang_coc(d, vi_tri='mo_trai'):
    """MẶT BẰNG CỌC — nhìn từ trên xuống: x = ngang cầu, y = dọc cầu.
    Vẽ vòng tròn từng cọc theo tọa độ thật (ưu tiên sơ đồ DXF), kèm bệ & kích thước."""
    g = _pos_geometry(d, vi_tri)
    fig = go.Figure()

    piles = g["piles"]
    declared = bool(piles)
    # Góc xiên: bệ HÌNH BÌNH HÀNH (dọc += ngang·cot). Cọc DXF khai báo giữ tọa độ
    # thật; lưới cọc TỰ ĐỘNG trượt theo bệ cho khớp.
    _cotp = _skew_cot(d)
    if not piles:
        piles = _auto_pile_grid(g)
        if _cotp:
            for _p in piles:
                _p["y"] = _p["y"] + _p["x"] * _cotp

    bhn, bhd = g["be_half_ngang"], g["be_half_doc"]
    # Bệ cọc (hình chiếu bằng — bình hành theo góc xiên)
    _bx = [-bhn, bhn, bhn, -bhn]; _by = [-bhd, -bhd, bhd, bhd]
    _poly(fig, _bx, [y + x * _cotp for x, y in zip(_bx, _by)],
          "rgba(170,183,184,0.25)", _C["be_dk"], "Bệ cọc", lw=1.8)

    # Vòng tròn cọc
    for j, p in enumerate(piles):
        _circle(fig, p["x"], p["y"], p["D"] / 2.0, _C["be_dk"],
                "rgba(86,101,115,0.30)",
                name=(f"Cọc Ø{int(round(p['D']*1000))}mm" if j == 0 else ""),
                showlegend=(j == 0))
        fig.add_trace(go.Scatter(
            x=[p["x"]], y=[p["y"]], mode="markers+text",
            marker=dict(size=4, color=_C["be_dk"]),
            text=[str(j + 1)], textposition="middle center",
            textfont=dict(size=8, color="#2c3e50"),
            showlegend=False, hoverinfo="text",
            hovertext=[f"Cọc {j+1}: x={p['x']:.2f} y={p['y']:.2f} "
                       f"Ø{p['D']:.2f}m L={p['L']:.1f}m"]))

    # Trục tim
    fig.add_shape(type="line", x0=0, y0=-bhd - 0.6, x1=0, y1=bhd + 0.6,
                  line=dict(color="#aab7b8", width=1, dash="dashdot"))
    fig.add_shape(type="line", x0=-bhn - 0.6, y0=0, x1=bhn + 0.6, y1=0,
                  line=dict(color="#aab7b8", width=1, dash="dashdot"))

    # Khoảng cách cọc (nếu lưới đều)
    xs_u = sorted({round(p["x"], 2) for p in piles})
    ys_u = sorted({round(p["y"], 2) for p in piles})
    if len(xs_u) >= 2:
        _dim_h(fig, -bhd - 0.5, xs_u[0], xs_u[1],
               f"a={abs(xs_u[1]-xs_u[0]):.2f}m", dy=0)
    if len(ys_u) >= 2:
        _dim_v(fig, bhn + 0.5, ys_u[0], ys_u[1],
               f"b={abs(ys_u[1]-ys_u[0]):.2f}m", dx=0.2)
    _dim_h(fig, bhd + 0.5, -bhn, bhn, f"B_bệ={2*bhn:.2f}m", dy=0)
    _dim_v(fig, -bhn - 0.5, -bhd, bhd, f"L_bệ={2*bhd:.2f}m", dx=-0.2)

    _src = "sơ đồ DXF" if declared else "tự động (chưa khai DXF)"
    _R = max(bhn, bhd, *( [abs(p["x"]) for p in piles] or [0] ),
             *( [abs(p["y"]) for p in piles] or [0] )) + 1.5
    fig.update_layout(
        title=dict(text=f"MẶT BẰNG CỌC — {g['title_vt']} | {len(piles)} cọc · {_src}",
                   x=0.5, font=dict(size=12)),
        xaxis=dict(title="Ngang cầu (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5,
                   range=[-_R, _R]),
        yaxis=dict(title="Dọc cầu (m)", scaleanchor="x", scaleratio=1,
                   showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5),
        height=400, template="plotly_white",
        legend=dict(orientation="h", y=-0.18, font=dict(size=9)),
        margin=dict(l=55, r=30, t=60, b=80),
    )
    _apply_layers_2d(fig)
    return fig


def ve_mat_bang_mo_tru(d, vi_tri='mo_trai', pier_assembly=None, x_half=None,
                       abutment_assembly=None):
    """MẶT BẰNG KẾT CẤU MỐ/TRỤ — nhìn từ trên: x = ngang cầu, y = dọc cầu.
    abutment_assembly: mố lắp ghép → vẽ footprint mố thực (thân + 2 cánh)."""
    g = _pos_geometry(d, vi_tri, pier_assembly)
    fig = go.Figure()
    bhn, bhd = g["be_half_ngang"], g["be_half_doc"]
    bc = g["bc"]
    # Góc xiên: mặt bằng mố/trụ vẽ HÌNH BÌNH HÀNH — trượt dọc theo ngang·cot(α).
    _cotp = _skew_cot(d)
    def _polyS(xs, ys, *a, **k):
        _poly(fig, list(xs),
              [y + x * _cotp for x, y in zip(list(xs), list(ys))], *a, **k)
    def _circS(xc, yc, r, *a, **k):
        _circle(fig, xc, yc + xc * _cotp, r, *a, **k)
    _use_asm = bool(pier_assembly) and not g["is_mo"]
    _use_mo  = bool(abutment_assembly) and g["is_mo"]

    if _use_asm:
        # TRỤ LẮP GHÉP: vẽ footprint thật (bệ/thân/xà mũ) + NÉT khối giữa (ụ giữa)
        # và tường tai (detail=True) → mặt bằng xà mũ thể hiện đủ các khối.
        _PBm = _get_PB()
        _polys = _PBm.pier_plan_polys(pier_assembly, target_width=bc, detail=True)
        _seen = set()
        for _pl in _polys:
            _nm = _pl["name"]; _sl = _nm not in _seen; _seen.add(_nm)
            _polyS(_pl["xs"], _pl["ys"], _pl["color"], _C["be_dk"],
                   _nm if _sl else "", showlegend=_sl, lw=1.6)
        _allx = [x for pl in _polys for x in pl["xs"]]
        _ally = [y for pl in _polys for y in pl["ys"]]
        if _allx:
            bhn = max(bhn, abs(min(_allx)), abs(max(_allx)))
        if _ally:
            bhd = max(bhd, abs(min(_ally)), abs(max(_ally)))
    elif _use_mo:
        # MỐ THƯ VIỆN: footprint thật (thân + 2 cánh), co bề rộng theo cầu.
        _PBa = _get_PB()
        _mpolys = _PBa.abutment_plan_polys(abutment_assembly, target_width=bc)
        _seen = set()
        for _pl in _mpolys:
            _nm = _pl["name"]; _sl = _nm not in _seen; _seen.add(_nm)
            _polyS(_pl["xs"], _pl["ys"], _pl["color"], _C["be_dk"],
                   _nm if _sl else "", showlegend=_sl, lw=1.6)
        _allx = [x for pl in _mpolys for x in pl["xs"]]
        _ally = [y for pl in _mpolys for y in pl["ys"]]
        if _allx:
            bhn = max(bhn, abs(min(_allx)), abs(max(_allx)))
        if _ally:
            bhd = max(bhd, abs(min(_ally)), abs(max(_ally)))
    else:
        # Bệ cọc (chung)
        _polyS([-bhn, bhn, bhn, -bhn], [-bhd, -bhd, bhd, bhd],
               "rgba(170,183,184,0.30)", _C["be_dk"], "Bệ cọc", lw=1.8)

    if _use_asm or _use_mo:
        pass  # đã vẽ footprint trụ/mố ở trên
    elif g["is_mo"]:
        # Thân mố (tường thân) + tường cánh kéo về phía sau (dọc cầu)
        body_ng = bc / 2 + 0.5
        body_dc = max(0.8, bhd * 0.35)
        _polyS([-body_ng, body_ng, body_ng, -body_ng],
               [-body_dc, -body_dc, body_dc, body_dc],
               _C["moc"], _C["be_dk"], "Thân mố")
        wing_len = bhd  # tường cánh trải theo dọc
        for sy in (-1, 1):
            xw = sy * body_ng
            _polyS([xw - sy*0.4, xw, xw, xw - sy*0.4],
                   [-wing_len, -wing_len, wing_len, wing_len],
                   "rgba(192,160,107,0.45)", _C["be_dk"],
                   "Tường cánh" if sy == -1 else "", showlegend=(sy == -1))
    else:
        # Xà mũ (chạy ngang) + thân cột
        _polyS([-g["cap_W"], g["cap_W"], g["cap_W"], -g["cap_W"]],
               [-g["cap_half_doc"], -g["cap_half_doc"], g["cap_half_doc"], g["cap_half_doc"]],
               "rgba(133,146,158,0.45)", _C["dam_dk"], "Xà mũ", lw=1.5)
        r_col = g["W_cot"] / 2.0
        for ic, off_c in enumerate(g["col_offs"]):
            _circS(off_c, 0.0, r_col, _C["btong_dk"], "rgba(200,214,192,0.85)",
                   name=("Thân cột" if ic == 0 else ""), showlegend=(ic == 0))

    # Cọc (chấm tròn mờ để định vị)
    _piles = g["piles"] or _auto_pile_grid(g)
    for j, p in enumerate(_piles):
        _circS(p["x"], p["y"], p["D"] / 2.0, "rgba(86,101,115,0.55)",
               "rgba(86,101,115,0.12)",
               name=("Cọc" if j == 0 else ""), showlegend=(j == 0))

    fig.add_shape(type="line", x0=0, y0=-bhd - 0.6, x1=0, y1=bhd + 0.6,
                  line=dict(color="#aab7b8", width=1, dash="dashdot"))
    _dim_h(fig, bhd + 0.5, -bhn, bhn, f"B_bệ={2*bhn:.2f}m", dy=0)
    _dim_v(fig, -bhn - 0.5, -bhd, bhd, f"L_bệ={2*bhd:.2f}m", dx=-0.2)

    _struct_x = max(bhn, g["cap_W"], (bc / 2 + 0.5) if g["is_mo"] else 0)
    _struct_y = max(bhd, g.get("cap_half_doc", 0))
    _R = max(_struct_x, _struct_y) + 1.5
    # x_half: ép tầm nhìn ngang CHUNG để thẳng trục với mặt cắt ngang bên dưới.
    _xr = float(x_half) if x_half else _R
    fig.update_layout(
        title=dict(text=f"MẶT BẰNG KẾT CẤU — {g['title_vt']}", x=0.5, font=dict(size=12)),
        xaxis=dict(title="Ngang cầu (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5,
                   range=[-_xr, _xr]),
        yaxis=dict(title="Dọc cầu (m)", scaleanchor="x", scaleratio=1,
                   showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5),
        height=400, template="plotly_white",
        legend=dict(orientation="h", y=-0.18, font=dict(size=9)),
        margin=dict(l=60, r=40, t=60, b=80),
    )
    _apply_layers_2d(fig)
    return fig


def ve_mat_cat_doc_vi_tri(d, vi_tri='mo_trai', pier_assembly=None,
                          abutment_assembly=None, df_geology=None,
                          df_tim_line=None, draw_own_beams=True):
    """MẶT CẮT DỌC tại vị trí — cắt dọc tim cầu qua mố/trụ: x = dọc cầu, y = cao độ.
    abutment_assembly: mố lắp ghép → vẽ mặt cắt dọc theo mố thực (nét thấy/khuất).
    df_geology/df_tim_line: khảo sát → dầm bám đường đỏ + móng bám địa hình (đồng
    bộ 3D & trắc dọc).
    draw_own_beams=False → nơi gọi OVERLAY profil dầm THẬT (get_elevation_profile_
    traces dời về tim trụ) = ĐÚNG như trắc dọc; hàm KHÔNG vẽ dầm hộp tham số."""
    g = _pos_geometry(d, vi_tri, pier_assembly, df_geology=df_geology,
                      df_tim_line=df_tim_line)
    fig = go.Figure()
    bhd = g["be_half_doc"]
    h_tn = g["z_ground"]        # ĐTN tại lý trình cắt (đồng bộ 3D), thay h_tn phẳng

    # Địa hình (phẳng) + đất nền
    x_span = max(bhd + 3.0, 5.0)
    z_min = min(g["z_beb"], h_tn) - 3.0
    fig.add_trace(go.Scatter(
        x=[-x_span, x_span, x_span, -x_span],
        y=[h_tn, h_tn, z_min, z_min],
        fill="toself", fillcolor=_C["dat"],
        line=dict(color="#6d4c41", width=1.5), mode="lines",
        name="Địa hình"))

    if pier_assembly and not g["is_mo"]:
        # TRỤ: HÌNH CHIẾU ĐỨNG thật của LƯỚI 3D (project axis='y') — CÙNG NGUỒN &
        # CÙNG cách neo với 3D và trắc dọc (bố trí chung): ĐỈNH ụ giữa = ĐÁY BẢN,
        # đáy bệ = g["z_beb"], nới ụ giữa theo _pier_cap_widen. Nhờ vậy xà mũ bậc
        # (ụ giữa/vai kê) + trụ 2 thân hiện ĐÚNG như trắc dọc, thay pier_elevation_rects.
        _PBm = _get_PB()
        _z_ugiua = g["cao_dd"] + g["H_dam"]      # đỉnh ụ giữa = đáy bản mặt cầu
        _z_beb   = g["z_beb"]
        _wmap = (d or {}).get("_pier_cap_widen") or {}
        _w0   = float((d or {}).get("_pier_cap_W0", 0) or 0)
        _mid_extra = max(0.0, _wmap.get(round(g["x_cut"], 3), _w0) - _w0)
        _ptr = _PBm.build_pier_mesh_traces(
            pier_assembly, H_tru=(_z_ugiua - _z_beb),
            x_ctr=0.0, z_base=_z_beb, cap_width=None, cap_mid_extra=_mid_extra)
        _seen = set()
        for _rc in project_mesh_traces(_ptr, axis="y"):
            _nm = _rc["name"].split(" #")[0]
            _sl = _nm not in _seen; _seen.add(_nm)
            _poly(fig, _rc["xs"], _rc["zs"], _rc["color"], _C["dam_dk"],
                  _nm if _sl else "", showlegend=_sl)
        z_top_pile = _z_beb
    elif g["is_mo"] and abutment_assembly:
        # MỐ THƯ VIỆN: mặt cắt DỌC thật (vai kê = đáy dầm, đáy bệ = ĐTN−0.5).
        _PBa = _get_PB()
        _zb_mo = h_tn - 0.5
        # Đáy dầm PHÍA MỐ = đáy dầm − độ sâu khấc (đầu dầm lên mố là đầu trơn).
        _seat_mo = _abut_seat_z(g["cao_dd"], pier_assembly)
        # MỐ = 1 KHỐI THỐNG NHẤT: vẽ mọi đoạn cùng nét THẤY, 1 chú giải "Mố"
        # (cánh trước, thân sau → thân nổi trên, dầm kê đúng vai kê thân).
        _el_pl = _PBa.abutment_elevation_polys(
            abutment_assembly, H_tru=(_seat_mo - _zb_mo),
            x_face=0.0, out_dir=1.0, z_base=_zb_mo, seat_z=_seat_mo)
        _el_pl.sort(key=lambda p: 0 if p.get("hidden") else 1)
        _seen = False
        for _pl in _el_pl:
            _poly(fig, _pl["xs"], _pl["zs"], _pl["color"], _C["be_dk"],
                  ("Mố" if not _seen else ""), showlegend=(not _seen))
            _seen = True
        z_top_pile = min((z for p in _el_pl for z in p["zs"]), default=_zb_mo)
    elif g["is_mo"]:
        # Thân mố + tường cánh (mặt cắt dọc) — generic (chưa có mố thư viện)
        body_dc = max(0.8, bhd * 0.35)
        _poly(fig, [-body_dc, body_dc, body_dc, -body_dc],
              [h_tn, h_tn, g["z_deck"], g["z_deck"]],
              _C["moc"], _C["be_dk"], "Thân mố")
        _poly(fig, [-bhd, bhd, bhd, -bhd],
              [g["z_beb"], g["z_beb"], h_tn, h_tn],
              "rgba(170,183,184,0.30)", _C["be_dk"], "Bệ cọc")
        z_top_pile = g["z_beb"]
    else:
        # Bệ + thân trụ + xà mũ (mặt cắt dọc)
        _poly(fig, [-bhd, bhd, bhd, -bhd],
              [g["z_beb"], g["z_beb"], g["z_shb"], g["z_shb"]],
              _C["be"], _C["be_dk"], "Bệ cọc")
        col_dc = max(g["W_cot"], g["cap_half_doc"] * 0.8)
        _poly(fig, [-col_dc, col_dc, col_dc, -col_dc],
              [g["z_shb"], g["z_shb"], g["z_capb"], g["z_capb"]],
              _C["btong"], _C["btong_dk"], "Thân trụ")
        _poly(fig, [-g["cap_half_doc"], g["cap_half_doc"],
                    g["cap_half_doc"], -g["cap_half_doc"]],
              [g["z_capb"], g["z_capb"], g["z_cap_t"], g["z_cap_t"]],
              _C["btong"], _C["dam_dk"], "Xà mũ")
        z_top_pile = g["z_beb"]

    # ── ĐÁ KÊ GỐI: CHỈ ở MỐ (đầu dầm trơn kê gối). TRỤ: dầm đầu khấc lọt vào khấc
    #    xà mũ (không gối riêng) — đồng bộ trắc dọc/3D. ──
    if g["is_mo"] and g.get("h_goi", 0) > 0:
        _goi_block_2d(fig, 0.0, g["z_cap_t"], g["h_goi"],
                      w=max(0.4, g["cap_half_doc"] * 0.5), name="Đá kê gối", sl=True)

    # ── DẦM chủ (mặt cắt DỌC — hình chiếu cạnh) kê trên gối, vươn vào nhịp; ứng
    #    với bố trí chung toàn cầu. TRỤ: 2 đầu dầm 2 nhịp; MỐ: 1 đầu dầm vào nhịp.
    #    TRỤ có khấc → ụ giữa (tường tai) nhô cao hơn đáy dầm đúng độ sâu khấc.
    #    draw_own_beams=False → nơi gọi overlay profil dầm THẬT (đầu khấc) khớp trắc dọc.
    if draw_own_beams:
        _z_sof = g["cao_dd"]                       # đáy dầm (kê trên gối)
        _z_topd = g["cao_dd"] + g["H_dam"]         # đỉnh dầm = đáy bản
        try:
            _notch_d = (_get_PB().cap_seat_notch_depth_m(pier_assembly)
                        if (pier_assembly and not g["is_mo"]) else 0.0) or 0.0
        except Exception:
            _notch_d = 0.0
        _gap_d = max(0.12, _notch_d * 0.6)         # khe co giãn giữa 2 đầu dầm
        _sides = ([-1, 1] if not g["is_mo"] else [1])   # mố: dầm vào nhịp (+x)
        _leg_d = True
        for _sg in _sides:
            _xn = _sg * _gap_d
            _xf = _sg * (x_span - 0.05)
            _poly(fig, [_xn, _xf, _xf, _xn],
                  [_z_sof, _z_sof, _z_topd, _z_topd],
                  _C["dam"], _C["dam_dk"],
                  "Dầm chủ" if _leg_d else "", showlegend=_leg_d)
            _leg_d = False
        # Ụ giữa / tường tai (khấc) giữa 2 đầu dầm ở TRỤ có khấc.
        if not g["is_mo"] and _notch_d > 1e-3:
            _poly(fig, [-_gap_d, _gap_d, _gap_d, -_gap_d],
                  [_z_sof, _z_sof, _z_sof + _notch_d, _z_sof + _notch_d],
                  _C["btong"], _C["dam_dk"], "Ụ giữa (khấc)", showlegend=True)

    # Cọc (chiếu lên mặt phẳng dọc, có độ xiên ix)
    _piles = g["piles"] or _auto_pile_grid(g)
    _draw_piles_elevation(fig, _piles, x_center=0.0, z_top=z_top_pile,
                          color=_C["be_dk"], legend_name=f"Cọc ({len(_piles)})")

    # Bản mặt cầu (ký hiệu)
    _poly(fig, [-x_span, x_span, x_span, -x_span],
          [g["cao_dd"] + g["H_dam"], g["cao_dd"] + g["H_dam"],
           g["z_deck"], g["z_deck"]],
          _C["ban"], _C["btong_dk"], "Bản mặt cầu")

    _dim_h(fig, g["z_beb"] - 0.6, -bhd, bhd, f"L_bệ={2*bhd:.2f}m", dy=0)
    fig.add_shape(type="line", x0=0, y0=z_min, x1=0, y1=g["z_deck"] + 0.5,
                  line=dict(color="#aab7b8", width=1, dash="dashdot"))

    fig.update_layout(
        title=dict(text=f"MẶT CẮT DỌC — {g['title_vt']} | Lý trình ≈ {g['x_cut']:.1f} m",
                   x=0.5, font=dict(size=12)),
        xaxis=dict(title="Dọc cầu (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5,
                   range=[-x_span, x_span]),
        yaxis=dict(title="Cao độ (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5),
        height=480, template="plotly_white",
        legend=dict(orientation="h", y=-0.18, font=dict(size=9)),
        margin=dict(l=55, r=30, t=60, b=100),
    )
    _apply_layers_2d(fig)
    return fig


# ===========================================================================
# 9. CHẾ ĐỘ HIỂN THỊ 3D (tương tự Revit: Shaded / Wireframe / X-Ray / Realistic)
# ===========================================================================
# Các khối GIỮ trong suốt kể cả chế độ đặc (mặt nước, tĩnh không, khối mờ tạm…)
_TRANSLUCENT_KEYS = ("nước", "Mặt nước", "MNCN", "MNTT", "MNTN", "MNTC",
                     "Tĩnh không", "chưa gắn", "tạm")

# ── HỆ THỐNG MÃ MÀU CÁC HẠNG MỤC cho mô hình 3D (theo bảng quy định) ──────────
# Cấu kiện BTXM = xám #d6d6d6; bê tông nhựa/lớp phủ = xám đậm #4a484b.
# EXCLUSION: đổi MỌI khối đặc sang màu hạng mục tương ứng, TRỪ nền đắp/địa hình
# và khối trong suốt → bắt được cả dầm thư viện / trụ chèn từ module khác.
CONCRETE_3D = "#d6d6d6"        # Các cấu kiện BTXM (214,214,214)
ASPHALT_3D  = "#4a484b"        # Bê tông nhựa (74,72,75)
_ASPHALT_SRC_3D = {"#2c3e50", "#34495e"}   # lớp phủ BTN / mặt đường đầu cầu
_NON_CONCRETE_3D = {
    "#c9a86b",              # nền đắp / địa hình → giữ
    "#e8eaf0",              # khối bao dầm (mờ) → giữ
}


def _is_translucent(trace) -> bool:
    nm = str(getattr(trace, "name", "") or "")
    return any(k in nm for k in _TRANSLUCENT_KEYS)


def _to_concrete(trace) -> None:
    """Quy 1 khối về màu hạng mục chuẩn (BTXM xám / bê tông nhựa xám đậm);
    giữ nền đắp/địa hình/khối trong suốt."""
    if _is_translucent(trace):
        return
    try:
        if trace.opacity is not None and float(trace.opacity) < 0.5:
            return
    except Exception:
        pass
    col = str(getattr(trace, "color", "") or "").strip().lower()
    if col in _NON_CONCRETE_3D:
        return
    trace.color = ASPHALT_3D if col in _ASPHALT_SRC_3D else CONCRETE_3D


# Cụm KHÔNG biến dạng theo góc xiên (địa hình thực, mặt nước, khung tĩnh không,
# nền/mặt đường đầu cầu chạy thẳng theo lý trình) — chỉ KẾT CẤU CẦU mới xiên.
_SKEW_SKIP_KW = ("địa hình", "dia hinh", "terrain", "mặt nước", "mat nuoc",
                 "nước", "nuoc", "tĩnh không", "tinh khong")
# (Đường đầu cầu KHÔNG còn trong skip → xiên theo góc giao, khớp mố xiên.)


def apply_skew_3d(fig, d, start_index=0):
    """Biến dạng XIÊN mô hình 3D theo GÓC GIAO (goc_giao) — đồng bộ với bình đồ 2D.

    Cắt xiên = phép TRƯỢT (shear) trong mặt phẳng lý trình–ngang cầu: điểm có
    toạ độ ngang y bị dịch theo lý trình x một lượng y·cot(α) (α = góc giao).
    Dầm vẫn song song tim cầu (mỗi dầm ở y cố định chỉ tịnh tiến theo x); mố/trụ
    nghiêng đúng theo phương cắt xiên — giống mặt cầu hình bình hành ở bình đồ.

    • start_index: chỉ biến dạng các trace từ vị trí này trở đi (bỏ qua nền địa
      hình đã vẽ trước khi overlay kết cấu).
    • Luôn BỎ QUA địa hình/mặt nước/tĩnh không/đường đầu cầu theo tên & nhóm.
    """
    try:
        goc = float((d or {}).get("goc_giao", 90.0))
    except Exception:
        goc = 90.0
    if goc >= 89.9 or goc <= 0:
        return fig                                   # không xiên → giữ nguyên
    alpha = np.radians(max(30.0, min(89.9, goc)))
    cot = 1.0 / np.tan(alpha)
    for _i, tr in enumerate(fig.data):
        if _i < start_index:
            continue
        _key = (str(getattr(tr, "legendgroup", "") or "") + " " +
                str(getattr(tr, "name", "") or "")).lower()
        if any(k in _key for k in _SKEW_SKIP_KW):
            continue
        x = getattr(tr, "x", None); y = getattr(tr, "y", None)
        if x is None or y is None:
            continue
        try:
            xa = np.asarray(x, dtype=float); ya = np.asarray(y, dtype=float)
            if xa.shape != ya.shape:
                continue
            tr.x = (xa + ya * cot)
        except Exception:
            continue
    return fig


def apply_render_mode(fig, mode="Shaded"):
    """
    Áp dụng chế độ hiển thị lên figure 3D sau khi đã tạo.
    mode: 'Shaded' | 'Wireframe' | 'X-Ray' | 'Realistic'

    'Shaded'/'Realistic' = ĐẶC (opacity 1.0) cho cấu kiện kết cấu → không nhìn
    xuyên, đỡ rối mắt khi zoom (mặt nước & tĩnh không vẫn trong suốt).
    """
    for trace in fig.data:
        if isinstance(trace, go.Mesh3d):
            # Quy mọi khối BTCT về 1 màu bê tông đặc trước khi áp chế độ hiển thị
            _to_concrete(trace)
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
                if not _is_translucent(trace):
                    trace.opacity = 1.0
            else:  # Shaded (mặc định) — ĐẶC
                trace.flatshading = True
                trace.lighting = dict(ambient=0.55, diffuse=0.9, specular=0.25)
                if not _is_translucent(trace):
                    trace.opacity = 1.0

    if mode == "Wireframe":
        # Thêm contour lines cho tất cả Mesh3d
        for trace in fig.data:
            if isinstance(trace, go.Mesh3d):
                trace.contour = go.mesh3d.Contour(show=True, color="#2c3e50", width=2)
    return fig
