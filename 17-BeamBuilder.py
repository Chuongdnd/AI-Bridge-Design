"""
BeamBuilder — lõi tính toán cho Section Sketcher + Parametric Beam Builder.

Cấu trúc dữ liệu : CrossSection, Segment, Feature, BeamModel  (JSON-serialisable)
Tiện ích polygon  : area, winding, close, mirror, offset, chamfer, resample
Loft engine       : linear morph 2 polyline → danh sách điểm 3D
Đầu ra Plotly     : build_3d_wireframe, make_section_fig, make_elevation_fig
Đơn vị nội bộ     : mm (trục X = ngang, Z = đứng, Y = dọc dầm)
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from typing import Literal

import numpy as np
import plotly.graph_objects as go


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  DATA MODEL
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CrossSection:
    name: str
    outer: list                        # list of [x, z] in mm
    holes: list = field(default_factory=list)   # list of [[x,z],…]
    open: bool = False                 # True → máng hở (không có đỉnh nối ngang)
    origin: list = field(default_factory=lambda: [0.0, 0.0])

    def clone(self) -> "CrossSection":
        import copy
        return copy.deepcopy(self)


@dataclass
class Segment:
    type: str = "constant"             # "constant" | "loft"
    section: str | None = None
    from_sec: str | None = None
    to_sec: str | None = None
    length: object = 0.0              # float (mm) hoặc "fill"
    rule: str = "linear"


@dataclass
class Feature:
    kind: str = "pvc_hole"            # "pvc_hole" | "chamfer"
    anchor: str = "absolute"
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    d: float = 49.0
    size: list = field(default_factory=list)
    edges: str = ""


@dataclass
class BeamModel:
    length: float = 38200.0
    datum: dict = field(default_factory=lambda: {"y0": "tim_dam", "z0": "day_dam"})
    sections: dict = field(default_factory=dict)   # name → CrossSection
    segments: list = field(default_factory=list)
    mirror: bool = True
    features: list = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  JSON  I/O
# ═══════════════════════════════════════════════════════════════════════════════

def _sec_to_dict(s: CrossSection) -> dict:
    return dict(name=s.name, outer=s.outer, holes=s.holes,
                open=s.open, origin=s.origin)

def _sec_from_dict(d: dict) -> CrossSection:
    return CrossSection(
        name=d["name"],
        outer=[list(p) for p in d["outer"]],
        holes=[[list(p) for p in h] for h in d.get("holes", [])],
        open=d.get("open", False),
        origin=list(d.get("origin", [0.0, 0.0])),
    )

def model_to_json(m: BeamModel, indent: int = 2) -> str:
    d = dict(
        length=m.length,
        datum=m.datum,
        sections={k: _sec_to_dict(v) for k, v in m.sections.items()},
        segments=[asdict(s) for s in m.segments],
        mirror=m.mirror,
        features=[asdict(f) for f in m.features],
    )
    return json.dumps(d, ensure_ascii=False, indent=indent)

def model_from_json(s: str) -> BeamModel:
    d = json.loads(s)
    m = BeamModel(length=d.get("length", 38200.0), datum=d.get("datum", {}),
                  mirror=d.get("mirror", True))
    for k, v in d.get("sections", {}).items():
        m.sections[k] = _sec_from_dict(v)
    for sv in d.get("segments", []):
        m.segments.append(Segment(**sv))
    for fv in d.get("features", []):
        m.features.append(Feature(**fv))
    return m


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  POLYGON UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def poly_area_signed(pts: list) -> float:
    """Shoelace — dương = CCW."""
    n = len(pts)
    return sum(pts[i][0] * pts[(i+1) % n][1] - pts[(i+1) % n][0] * pts[i][1]
               for i in range(n)) / 2.0

def poly_is_ccw(pts: list) -> bool:
    return poly_area_signed(pts) > 0

def poly_ensure_ccw(pts: list) -> list:
    return list(pts) if poly_is_ccw(pts) else list(reversed(pts))

def poly_ensure_cw(pts: list) -> list:
    return list(pts) if not poly_is_ccw(pts) else list(reversed(pts))

def poly_close(pts: list, tol: float = 1e-6) -> list:
    """Xoá điểm cuối trùng với điểm đầu."""
    pts = list(pts)
    while len(pts) > 1:
        dx = abs(pts[0][0] - pts[-1][0])
        dz = abs(pts[0][1] - pts[-1][1])
        if dx < tol and dz < tol:
            pts.pop()
        else:
            break
    return pts

def poly_mirror_x(pts: list) -> list:
    return [[-p[0], p[1]] for p in pts]

def poly_offset(pts: list, d: float) -> list:
    """
    Offset polygon vào trong (d>0 = thu nhỏ, d<0 = mở rộng).
    Dùng average vertex normal — đủ cho mặt cắt dầm, không phức tạp.
    """
    n = len(pts)
    result = []
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]

        def unit_inward(a, b):
            ex, ez = b[0] - a[0], b[1] - a[1]
            L = math.hypot(ex, ez)
            if L < 1e-12:
                return (0.0, 0.0)
            return (ez / L, -ex / L)   # rotate 90° CW (inward for CCW polygon)

        n1 = unit_inward(p0, p1)
        n2 = unit_inward(p1, p2)
        bx, bz = n1[0] + n2[0], n1[1] + n2[1]
        blen = math.hypot(bx, bz)
        if blen < 1e-12:
            result.append([p1[0] + d * n1[0], p1[1] + d * n1[1]])
        else:
            dot = n1[0] * bx / blen + n1[1] * bz / blen
            scale = 1.0 / max(abs(dot), 0.2)   # clamp to avoid spikes
            result.append([p1[0] + d * bx / blen * scale,
                           p1[1] + d * bz / blen * scale])
    return result

def poly_apply_snap(pts: list, grid: float) -> list:
    if grid <= 0:
        return pts
    return [[round(p[0] / grid) * grid, round(p[1] / grid) * grid] for p in pts]

def poly_apply_chamfer(pts: list, cx: float, cz: float) -> list:
    """Cắt vát tất cả góc nhọn < 120°, kích thước (cx, cz) mm."""
    if cx <= 0 or cz <= 0:
        return pts
    result = []
    n = len(pts)
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        e1x, e1z = p1[0] - p0[0], p1[1] - p0[1]
        e2x, e2z = p2[0] - p1[0], p2[1] - p1[1]
        L1 = math.hypot(e1x, e1z)
        L2 = math.hypot(e2x, e2z)
        if L1 < 1e-9 or L2 < 1e-9:
            result.append(list(p1))
            continue
        cos_a = (e1x * e2x + e1z * e2z) / (L1 * L2)
        cos_a = max(-1.0, min(1.0, cos_a))
        angle = math.degrees(math.acos(cos_a))
        if angle > 30:   # chamfer góc nhọn (< 150° ở phía trong)
            f1 = min(cx / L1, 0.45)
            f2 = min(cz / L2, 0.45)
            result.append([p1[0] - f1 * e1x, p1[1] - f1 * e1z])
            result.append([p1[0] + f2 * e2x, p1[1] + f2 * e2z])
        else:
            result.append(list(p1))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def _pt_in_poly(pt, poly) -> bool:
    x, z = pt[0], pt[1]
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, zi = poly[i]
        xj, zj = poly[j]
        if ((zi > z) != (zj > z)) and (x < (xj - xi) * (z - zi) / (zj - zi + 1e-15) + xi):
            inside = not inside
        j = i
    return inside

def _segs_intersect(p1, p2, p3, p4) -> bool:
    def cross2d(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1 = cross2d(p3, p4, p1)
    d2 = cross2d(p3, p4, p2)
    d3 = cross2d(p1, p2, p3)
    d4 = cross2d(p1, p2, p4)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False

def validate_section(sec: CrossSection) -> dict:
    errors, warnings, infos = [], [], []
    outer = sec.outer
    if len(outer) < 3:
        errors.append("Biên ngoài cần ≥ 3 đỉnh.")
        return {"errors": errors, "warnings": warnings, "infos": infos}

    n = len(outer)
    for i in range(n):
        for j in range(i + 2, n):
            if j == n - 1 and i == 0:
                continue
            if _segs_intersect(outer[i], outer[(i+1)%n], outer[j], outer[(j+1)%n]):
                errors.append(f"Biên ngoài tự cắt: cạnh {i}–{i+1} × cạnh {j}–{j+1}.")

    for hi, hole in enumerate(sec.holes):
        if len(hole) < 3:
            errors.append(f"Lỗ #{hi}: cần ≥ 3 đỉnh.")
            continue
        for pt in hole:
            if not _pt_in_poly(pt, outer):
                errors.append(f"Lỗ #{hi} có đỉnh nằm ngoài biên ngoài.")
                break

    area = abs(poly_area_signed(outer))
    if area < 1.0:
        warnings.append(f"Diện tích rất nhỏ ({area:.1f} mm²).")
    else:
        infos.append(f"Diện tích A = {area/1e6:.4f} m²  ({area:.0f} mm²)")

    if sec.open:
        infos.append("Mặt cắt máng hở (open = True).")

    return {"errors": errors, "warnings": warnings, "infos": infos}

def normalize_section(sec: CrossSection) -> CrossSection:
    sec.outer = poly_close(poly_ensure_ccw(sec.outer))
    sec.holes = [poly_close(poly_ensure_cw(h)) for h in sec.holes]
    return sec

def validate_model(m: BeamModel) -> dict:
    errors, warnings = [], []
    if not m.sections:
        errors.append("Chưa định nghĩa mặt cắt ngang nào.")

    seg_names = {k for k in m.sections}
    for i, seg in enumerate(m.segments):
        if seg.type == "constant" and seg.section not in seg_names:
            errors.append(f"Đoạn {i}: mặt cắt '{seg.section}' chưa định nghĩa.")
        if seg.type == "loft":
            for attr in ("from_sec", "to_sec"):
                nm = getattr(seg, attr)
                if nm not in seg_names:
                    errors.append(f"Đoạn {i} loft: mặt cắt '{nm}' chưa định nghĩa.")
            if seg.from_sec == seg.to_sec:
                warnings.append(f"Đoạn {i} loft: from = to ({seg.from_sec}), nên dùng constant.")

    fixed = sum(float(s.length) for s in m.segments if s.length != "fill")
    fills = sum(1 for s in m.segments if s.length == "fill")
    half = m.length / 2.0 if m.mirror else m.length
    if fills == 0 and abs(fixed - half) > 1.0:
        warnings.append(
            f"Tổng đoạn ({fixed:.0f} mm) ≠ chiều dài nửa dầm ({half:.0f} mm). "
            "Nên thêm đoạn 'fill'."
        )
    return {"errors": errors, "warnings": warnings}


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  RESAMPLE
# ═══════════════════════════════════════════════════════════════════════════════

def _cumlen(pts_arr: np.ndarray, closed: bool = True) -> np.ndarray:
    loop = np.vstack([pts_arr, pts_arr[[0]]]) if closed else pts_arr
    diffs = np.diff(loop, axis=0)
    dists = np.hypot(diffs[:, 0], diffs[:, 1])
    return np.concatenate([[0.0], np.cumsum(dists)])

def resample_polygon(pts: list, n: int, closed: bool = True) -> np.ndarray:
    """Resample về n điểm theo arc-length đều nhau."""
    arr = np.array(pts, dtype=float)
    cl = _cumlen(arr, closed=closed)
    total = cl[-1]
    if total < 1e-9 or n < 2:
        return arr[:n] if len(arr) >= n else arr
    target = np.linspace(0.0, total, n, endpoint=not closed)
    loop = np.vstack([arr, arr[[0]]]) if closed else arr
    rx = np.interp(target, cl, loop[:, 0])
    rz = np.interp(target, cl, loop[:, 1])
    return np.column_stack([rx, rz])


# ═══════════════════════════════════════════════════════════════════════════════
# 6.  LOFT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

N_RESAMP = 64    # điểm trên mỗi vòng
N_STAT   = 10   # trạm dọc trên mỗi đoạn loft


def _best_rotation(ra: np.ndarray, rb: np.ndarray) -> np.ndarray:
    """Tìm offset vòng cho rb sao cho tổng khoảng cách tới ra nhỏ nhất."""
    n = len(ra)
    best_off, best_d = 0, float("inf")
    for off in range(n):
        rb_rot = np.roll(rb, off, axis=0)
        d = np.sum(np.hypot(ra[:, 0] - rb_rot[:, 0], ra[:, 1] - rb_rot[:, 1]))
        if d < best_d:
            best_d, best_off = d, off
    return np.roll(rb, best_off, axis=0)


def _loft_wireframe_traces(ra: np.ndarray, rb: np.ndarray,
                            y0: float, y1: float,
                            n_stat: int = N_STAT,
                            color_ring: str = "#88bbdd",
                            color_long: str = "#557799") -> list:
    """
    Trả về list tuple (xs, ys, zs, is_ring) để vẽ Plotly 3D.
    Y = dọc dầm (mm), X = ngang, Z = đứng.
    """
    rb = _best_rotation(ra, rb)
    t_vals = np.linspace(0.0, 1.0, n_stat)
    stations = [(1.0 - t) * ra + t * rb for t in t_vals]
    traces = []

    # Vòng tròn tại mỗi trạm
    for ti, (t, ring) in enumerate(zip(t_vals, stations)):
        y = y0 + t * (y1 - y0)
        n = len(ring)
        xs = list(ring[:, 0]) + [ring[0, 0]]
        zs = list(ring[:, 1]) + [ring[0, 1]]
        ys = [y] * (n + 1)
        is_key = ti == 0 or ti == n_stat - 1
        traces.append((xs, ys, zs, is_key))

    # Đường loft dọc (ít hơn để không rậm rạp)
    stride = max(1, N_RESAMP // 16)
    for vi in range(0, N_RESAMP, stride):
        xs = [stations[ti][vi, 0] for ti in range(n_stat)]
        zs = [stations[ti][vi, 1] for ti in range(n_stat)]
        ys = [y0 + t * (y1 - y0) for t in t_vals]
        traces.append((xs, ys, zs, False))

    return traces


def _resolve_segments(m: BeamModel) -> list[dict]:
    """Trả về list dict đã giải quyết 'fill' và mirror."""
    segs = list(m.segments)

    # Giải quyết fill
    half = m.length / (2.0 if m.mirror else 1.0)
    fixed = sum(float(s.length) for s in segs if s.length != "fill")
    fills = sum(1 for s in segs if s.length == "fill")
    fill_len = max(0.0, (half - fixed) / fills) if fills else 0.0

    resolved = []
    for s in segs:
        L = fill_len if s.length == "fill" else float(s.length)
        resolved.append(dict(type=s.type, section=s.section,
                             from_sec=s.from_sec, to_sec=s.to_sec,
                             length=L, rule=s.rule))

    # Mirror
    if m.mirror:
        mirrored = []
        for s in reversed(resolved):
            mirrored.append(dict(type=s["type"],
                                 section=s["section"],
                                 from_sec=s["to_sec"],
                                 to_sec=s["from_sec"],
                                 length=s["length"],
                                 rule=s["rule"]))
        resolved = resolved + mirrored

    return resolved


def _get_resampled(m: BeamModel, name: str) -> np.ndarray:
    sec = m.sections.get(name)
    if sec is None:
        raise ValueError(f"Mặt cắt '{name}' chưa định nghĩa trong model.")
    pts = list(sec.outer)
    # Gộp lỗ vào polyline nếu có (dùng cho wireframe đơn giản)
    for h in sec.holes:
        pts += h + [h[0]]
    return resample_polygon(pts, N_RESAMP, closed=not sec.open)


def build_3d_wireframe(m: BeamModel) -> list:
    """Trả về list go.Scatter3d traces cho Plotly."""
    segs = _resolve_segments(m)
    traces = []
    y_off = 0.0

    CRG = "#88bbdd"    # màu vòng
    CLG = "#557799"    # màu đường dọc

    for seg in segs:
        L = seg["length"]
        y1 = y_off + L

        if seg["type"] == "constant":
            ra = _get_resampled(m, seg["section"])
            for y in (y_off, y1):
                xs = list(ra[:, 0]) + [ra[0, 0]]
                zs = list(ra[:, 1]) + [ra[0, 1]]
                traces.append(go.Scatter3d(
                    x=xs, y=[y]*len(xs), z=zs,
                    mode="lines", line=dict(color=CRG, width=2),
                    showlegend=False, hoverinfo="skip"))
            stride = max(1, N_RESAMP // 12)
            for vi in range(0, N_RESAMP, stride):
                traces.append(go.Scatter3d(
                    x=[ra[vi,0]]*2, y=[y_off, y1], z=[ra[vi,1]]*2,
                    mode="lines", line=dict(color=CLG, width=1),
                    showlegend=False, hoverinfo="skip"))

        elif seg["type"] == "loft":
            ra = _get_resampled(m, seg["from_sec"])
            rb = _get_resampled(m, seg["to_sec"])
            for xs, ys, zs, is_key in _loft_wireframe_traces(
                    ra, rb, y_off, y1, N_STAT, CRG, CLG):
                traces.append(go.Scatter3d(
                    x=xs, y=ys, z=zs,
                    mode="lines",
                    line=dict(color=CRG if is_key else CLG,
                              width=2 if is_key else 1),
                    showlegend=False, hoverinfo="skip"))

        y_off = y1

    return traces


# ═══════════════════════════════════════════════════════════════════════════════
# 7.  2D SECTION CANVAS FIGURE
# ═══════════════════════════════════════════════════════════════════════════════

_DARK = "#1a2330"
_GRID = "#2a3a4a"
_OUTER = "#88bbdd"
_HOLE  = "#e08080"
_AXIS  = "#5dade2"
_DIM   = "#e0c060"
_VERT  = "#66ff99"


def make_section_fig(sec: CrossSection | None = None,
                     snap_grid: float = 50.0,
                     show_grid_pts: bool = True,
                     x_range: tuple = (-1300, 1300),
                     z_range: tuple = (-1850, 200)) -> go.Figure:
    """
    Canvas 2D cho Section Sketcher.
    • Vẽ polygon hiện tại (outer + holes).
    • Hiển thị lưới điểm click (nếu show_grid_pts=True).
    • Trả về figure đã config với drawclosedpath cho Plotly toolbar.
    """
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_DARK, plot_bgcolor=_DARK,
        height=560,
        margin=dict(l=50, r=20, t=40, b=50),
        xaxis=dict(range=list(x_range), title="X (mm)", dtick=100,
                   showgrid=True, gridcolor=_GRID, zeroline=True,
                   zerolinecolor=_AXIS, zerolinewidth=1.5,
                   scaleanchor="y", scaleratio=1),
        yaxis=dict(range=list(z_range), title="Z (mm)", dtick=100,
                   showgrid=True, gridcolor=_GRID, zeroline=True,
                   zerolinecolor=_AXIS, zerolinewidth=1.5),
        showlegend=False,
    )

    # Grid điểm click (nhỏ, trong suốt)
    if show_grid_pts and snap_grid > 0:
        gx = np.arange(
            (x_range[0] // snap_grid) * snap_grid,
            x_range[1] + snap_grid, snap_grid)
        gz = np.arange(
            (z_range[0] // snap_grid) * snap_grid,
            z_range[1] + snap_grid, snap_grid)
        GX, GZ = np.meshgrid(gx, gz)
        fig.add_trace(go.Scatter(
            x=GX.flatten().tolist(), y=GZ.flatten().tolist(),
            mode="markers",
            marker=dict(size=3, color="rgba(100,150,200,0.15)", symbol="circle"),
            name="_grid", hoverinfo="x+y",
            hovertemplate="X=%{x:.0f}  Z=%{y:.0f}<extra></extra>",
        ))

    if sec is None:
        return fig

    # Biên ngoài
    outer = sec.outer
    if len(outer) >= 2:
        ox = [p[0] for p in outer] + [outer[0][0]]
        oz = [p[1] for p in outer] + [outer[0][1]]
        fig.add_trace(go.Scatter(
            x=ox, y=oz,
            fill="toself", fillcolor="rgba(100,160,200,0.20)",
            line=dict(color=_OUTER, width=2),
            mode="lines+markers",
            marker=dict(size=7, color=_VERT, symbol="circle"),
            name="Biên ngoài",
            hovertemplate="X=%{x:.0f}  Z=%{y:.0f}<extra>outer</extra>",
        ))
        # Đánh số đỉnh
        for i, (px, pz) in enumerate(outer):
            fig.add_annotation(x=px, y=pz, text=str(i),
                               showarrow=False,
                               font=dict(size=8, color=_VERT),
                               bgcolor="rgba(0,0,0,0.5)",
                               xanchor="center", yanchor="bottom",
                               yshift=8)

    # Lỗ
    for hi, hole in enumerate(sec.holes):
        if len(hole) < 2:
            continue
        hx = [p[0] for p in hole] + [hole[0][0]]
        hz = [p[1] for p in hole] + [hole[0][1]]
        fig.add_trace(go.Scatter(
            x=hx, y=hz,
            fill="toself", fillcolor="rgba(200,80,80,0.25)",
            line=dict(color=_HOLE, width=1.5),
            mode="lines+markers",
            marker=dict(size=5, color=_HOLE, symbol="x"),
            name=f"Lỗ #{hi}",
            hovertemplate=f"Lỗ #{hi} X=%{{x:.0f}}  Z=%{{y:.0f}}<extra></extra>",
        ))

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 8.  ELEVATION & PLAN FIGURES
# ═══════════════════════════════════════════════════════════════════════════════

def make_elevation_fig(m: BeamModel) -> go.Figure:
    """Mặt cắt dọc — đường bao trên/dưới + ký hiệu mặt cắt."""
    segs = _resolve_segments(m)
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_DARK, plot_bgcolor=_DARK,
        height=300, margin=dict(l=60, r=20, t=30, b=50),
        xaxis=dict(title="Dọc dầm Y (mm)", showgrid=True, gridcolor=_GRID,
                   zeroline=False),
        yaxis=dict(title="Z (mm)", showgrid=True, gridcolor=_GRID,
                   zeroline=True, zerolinecolor=_AXIS),
        showlegend=False,
    )

    y_off = 0.0
    sec_markers = []

    for si, seg in enumerate(segs):
        L = seg["length"]
        y1 = y_off + L

        # Lấy outline trên/dưới từ mặt cắt
        def _zrange(name):
            sec = m.sections.get(name)
            if sec is None:
                return 0.0, 1750.0
            zs = [p[1] for p in sec.outer]
            return min(zs), max(zs)

        if seg["type"] == "constant":
            z_lo, z_hi = _zrange(seg["section"])
            fig.add_shape(type="rect",
                          x0=y_off, y0=z_lo, x1=y1, y1=z_hi,
                          line=dict(color=_OUTER, width=1.5),
                          fillcolor="rgba(100,160,200,0.12)")
        elif seg["type"] == "loft":
            z_lo_a, z_hi_a = _zrange(seg["from_sec"])
            z_lo_b, z_hi_b = _zrange(seg["to_sec"])
            fig.add_shape(type="line",
                          x0=y_off, y0=z_hi_a, x1=y1, y1=z_hi_b,
                          line=dict(color=_OUTER, width=1.5))
            fig.add_shape(type="line",
                          x0=y_off, y0=z_lo_a, x1=y1, y1=z_lo_b,
                          line=dict(color=_OUTER, width=1.5))

        # Ký hiệu mặt cắt tại ranh giới đoạn
        if si == 0:
            sec_markers.append((y_off, seg.get("section") or seg.get("from_sec")))
        sec_markers.append((y1, seg.get("section") or seg.get("to_sec")))
        y_off = y1

    # Vẽ ký hiệu cắt
    seen = set()
    for y, nm in sec_markers:
        if nm is None or nm in seen:
            continue
        seen.add(nm)
        fig.add_vline(x=y, line_dict=dict(color=_DIM, dash="dash", width=1.5))
        fig.add_annotation(x=y, y=0, yref="paper",
                           text=f"<b>{nm}</b>",
                           showarrow=False,
                           font=dict(size=10, color=_DIM),
                           bgcolor="rgba(0,0,0,0.6)",
                           yanchor="bottom")

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 9.  PRESET SECTIONS (Super-T S=2200, H=1750)
# ═══════════════════════════════════════════════════════════════════════════════

def preset_supert_AA() -> CrossSection:
    """Mặt cắt A-A — máng hở 18 điểm (mm, z=0 tại đỉnh, z=-1750 đáy)."""
    outer = [
        [-1100,    0], [-510,    0], [-510, -275], [-295, -1175],
        [ 295, -1175], [ 510, -275], [ 510,    0], [1100,    0],
        [1100,  -75], [ 610, -150], [ 510, -1175], [ 510, -1730],
        [ 490, -1750], [-490, -1750], [-510, -1730], [-510, -1175],
        [-610, -150], [-1100,  -75],
    ]
    return CrossSection(name="A-A", outer=outer, open=True, origin=[0.0, 0.0])


def preset_supert_BB() -> CrossSection:
    """Mặt cắt B-B — đầu dầm đặc."""
    outer = [
        [-1100,    0], [1100,    0], [1100, -1750], [-1100, -1750],
    ]
    return CrossSection(name="B-B", outer=outer, open=False, origin=[0.0, 0.0])


def preset_supert_CC() -> CrossSection:
    """Mặt cắt C-C — gần gối (sườn hẹp ±610mm, không có cánh)."""
    outer = [
        [-610,    0], [610,    0],
        [ 510,  -20], [ 510, -250], [ 610, -1600],
        [1100, -1675], [1100, -1750],
        [-1100, -1750], [-1100, -1675], [-610, -1600],
        [-510, -250], [-510, -20],
    ]
    return CrossSection(name="C-C", outer=outer, open=False, origin=[0.0, 0.0])


def preset_supert_model() -> BeamModel:
    """BeamModel mẫu cho Super-T L=38200, S=2200, H=1750."""
    m = BeamModel(length=38200.0, mirror=True)
    m.sections["C-C"] = preset_supert_CC()
    m.sections["A-A"] = preset_supert_AA()
    m.sections["B-B"] = preset_supert_BB()
    m.segments = [
        Segment(type="constant", section="C-C", length=300.0),
        Segment(type="loft", from_sec="C-C", to_sec="A-A", length=900.0),
        Segment(type="loft", from_sec="A-A", to_sec="B-B", length=1200.0),
        Segment(type="constant", section="B-B", length="fill"),
    ]
    return m


# ═══════════════════════════════════════════════════════════════════════════════
# 10. CAD COMMAND INTERPRETER
# ═══════════════════════════════════════════════════════════════════════════════

CAD_HELP = (
    "── Vẽ ──────────────────────────────────────────\n"
    "PL / POLYLINE       — bắt đầu vẽ polyline (click lưới hoặc gõ toạ độ)\n"
    "L  / LINE           — bắt đầu vẽ line\n"
    "x,z                 — tọa độ tuyệt đối (mm) — gõ tay không snap\n"
    "@dx,dz              — tọa độ tương đối\n"
    "C  / CLOSE          — đóng & lưu polyline → outer boundary\n"
    "── Chỉnh sửa trực tiếp trên bản vẽ ─────────────\n"
    "G  / GRIP           — chọn đỉnh (click vàng) rồi click điểm mới để dời\n"
    "E  / ERASE          — click đỉnh (đỏ) để xoá từng điểm\n"
    "DEL i               — xoá đỉnh thứ i theo số (vd: DEL 3)\n"
    "ESC                 — thoát chế độ vẽ / grip / erase\n"
    "── Biến đổi ────────────────────────────────────\n"
    "M  / MIRROR         — gương qua X=0 rồi nối thành biên kín\n"
    "O  d / OFFSET d     — offset vào d mm → tạo lỗ void (mặc định 100)\n"
    "CHA cx,cz           — vát góc (mặc định 20,20)\n"
    "── Cài đặt ─────────────────────────────────────\n"
    "OPEN / CLOSED       — đặt cờ máng hở / kín\n"
    "SNAP g              — đặt snap grid (mm, 0=tắt) — ảnh hưởng lưới click\n"
    "── Khác ────────────────────────────────────────\n"
    "EH i / ERASEH i     — xoá lỗ void thứ i\n"
    "CLEAR               — xoá toàn bộ mặt cắt\n"
    "PRESET AA/BB/CC     — nạp preset Super-T\n"
    "U  / UNDO           — hoàn tác bước vừa rồi\n"
    "?  / HELP           — hiển thị trợ giúp này"
)


def _apply_snap(v: float, g: float) -> float:
    return round(v / g) * g if g > 0 else v


def process_cad_command(cmd_raw: str, sec: "CrossSection",
                         cad_state: dict) -> str:
    """
    Xử lý một dòng lệnh CAD.  Thay đổi sec và cad_state tại chỗ.
    Trả về chuỗi kết quả để hiển thị trong history.
    cad_state keys: mode, current_poly, cursor, snap
    """
    cmd_raw = cmd_raw.strip()
    if not cmd_raw:
        return ""

    parts  = cmd_raw.split()
    verb   = parts[0].upper()
    snap   = float(cad_state.get("snap", 0))

    # ── HELP ──────────────────────────────────────────────────────────────
    if verb in ("?", "H", "HELP"):
        return CAD_HELP

    # ── START MODES ───────────────────────────────────────────────────────
    if verb in ("PL", "POLYLINE"):
        cad_state["mode"] = "polyline"
        cad_state["current_poly"] = []
        return "POLYLINE — nhập tọa độ điểm đầu (vd: 0,0)"

    if verb in ("L", "LINE"):
        cad_state["mode"] = "line"
        cad_state["current_poly"] = []
        return "LINE — nhập điểm đầu"

    # ── GRIP MODE (click to select then move a vertex) ────────────────────
    if verb in ("G", "GRIP"):
        cad_state["mode"] = "grip"
        cad_state["grip_selected"] = None
        return "GRIP — click đỉnh (cam) để chọn, click điểm mới để dời"

    # ── ERASE MODE (click a vertex to delete it) ───────────────────────────
    if verb in ("E", "ERASE"):
        cad_state["mode"] = "erase"
        cad_state["grip_selected"] = None
        return "ERASE — click đỉnh (đỏ) để xoá"

    # ── DELETE VERTEX BY INDEX ─────────────────────────────────────────────
    if verb in ("DEL", "DELETE"):
        try:
            idx = int(parts[1])
            if 0 <= idx < len(sec.outer):
                removed = sec.outer.pop(idx)
                return f"✓ Xoá đỉnh #{idx} ({removed[0]:.0f},{removed[1]:.0f})"
            return f"⚠ #{idx} ngoài phạm vi (có {len(sec.outer)} điểm)"
        except (ValueError, IndexError):
            return "Cú pháp: DEL <số_đỉnh>  (vd: DEL 3)"

    # ── ESCAPE / NONE (exit any mode without committing) ──────────────────
    if verb in ("ESC", "ESCAPE", "NONE"):
        cad_state["mode"] = None
        cad_state["grip_selected"] = None
        cad_state["current_poly"] = []
        return "Thoát chế độ vẽ"

    # ── CLOSE ─────────────────────────────────────────────────────────────
    if verb in ("C", "CLOSE"):
        poly = cad_state.get("current_poly", [])
        if len(poly) >= 3:
            sec.outer = [list(p) for p in poly]
            cad_state["current_poly"] = []
            cad_state["mode"] = None
            return f"✓ Đóng polyline — {len(sec.outer)} điểm → outer"
        return f"⚠ Cần ≥ 3 điểm (hiện có {len(poly)})"

    # ── COORDINATE INPUT: x,z hoặc @dx,dz ────────────────────────────────
    coord = parts[0]
    if coord.startswith("@") and "," in coord:
        try:
            dx, dz = map(float, coord[1:].split(",", 1))
            last = cad_state.get("cursor", [0.0, 0.0])
            x = last[0] + dx   # tọa độ gõ tay → KHÔNG snap
            z = last[1] + dz
            cad_state["cursor"] = [x, z]
            if cad_state.get("mode") in ("polyline", "line"):
                cad_state.setdefault("current_poly", []).append([x, z])
                n = len(cad_state["current_poly"])
                return f"+ ({x:.0f}, {z:.0f})  #{n}"
            return f"Cursor → ({x:.0f}, {z:.0f})"
        except ValueError:
            pass

    if "," in coord and not coord.startswith("@"):
        try:
            x, z = map(float, coord.split(",", 1))
            # tọa độ gõ tay → KHÔNG snap (snap chỉ cho click chuột)
            cad_state["cursor"] = [x, z]
            if cad_state.get("mode") in ("polyline", "line"):
                cad_state.setdefault("current_poly", []).append([x, z])
                n = len(cad_state["current_poly"])
                return f"+ ({x:.0f}, {z:.0f})  #{n}"
            return f"Cursor → ({x:.0f}, {z:.0f})"
        except ValueError:
            pass

    # ── MIRROR ────────────────────────────────────────────────────────────
    if verb in ("M", "MIRROR"):
        if sec.outer:
            mir = poly_mirror_x(sec.outer)
            sec.outer = poly_close(poly_ensure_ccw(
                sec.outer + list(reversed(mir))))
            return f"✓ Mirror X=0 — tổng {len(sec.outer)} điểm"
        return "⚠ Chưa có outer boundary"

    # ── OFFSET ────────────────────────────────────────────────────────────
    if verb in ("O", "OFFSET"):
        try:
            d = float(parts[1]) if len(parts) >= 2 else 100.0
            if len(sec.outer) >= 3:
                hole = poly_close(poly_ensure_cw(poly_offset(sec.outer, d)))
                sec.holes.append(hole)
                return f"✓ Offset {d:.0f}mm → lỗ #{len(sec.holes)-1}"
            return "⚠ Chưa có outer để offset"
        except (ValueError, IndexError):
            return "Cú pháp: O 100"

    # ── CHAMFER ───────────────────────────────────────────────────────────
    if verb in ("CHA", "CHAMFER"):
        try:
            if len(parts) >= 2 and "," in parts[1]:
                cx, cz_v = map(float, parts[1].split(","))
            else:
                cx, cz_v = 20.0, 20.0
            if sec.outer:
                sec.outer = poly_apply_chamfer(sec.outer, cx, cz_v)
                return f"✓ Chamfer {cx:.0f}×{cz_v:.0f}mm — {len(sec.outer)} điểm"
            return "⚠ Chưa có outer"
        except Exception:
            return "Cú pháp: CHA 20,20"

    # ── SNAP ──────────────────────────────────────────────────────────────
    if verb in ("SNAP", "SN"):
        try:
            g = float(parts[1]) if len(parts) >= 2 else 50.0
            cad_state["snap"] = g
            return f"Snap grid = {g:.0f} mm"
        except Exception:
            return "Cú pháp: SNAP 50"

    # ── OPEN / CLOSED ─────────────────────────────────────────────────────
    if verb == "OPEN":
        sec.open = True;  return "✓ Máng hở (open = True)"
    if verb == "CLOSED":
        sec.open = False; return "✓ Mặt cắt kín (open = False)"

    # ── CLEAR ─────────────────────────────────────────────────────────────
    if verb == "CLEAR":
        sec.outer = []; sec.holes = []
        cad_state["mode"] = None; cad_state["current_poly"] = []
        return "✓ Đã xoá toàn bộ"

    # ── ERASE HOLE ────────────────────────────────────────────────────────
    if verb in ("EH", "ERASEH"):
        try:
            idx = int(parts[1]) if len(parts) >= 2 else -1
            if sec.holes:
                sec.holes.pop(idx)
                return f"✓ Xoá lỗ #{idx} — còn {len(sec.holes)} lỗ"
            return "⚠ Không có lỗ nào"
        except Exception:
            return "Cú pháp: EH 0"

    # ── NORMALIZE ─────────────────────────────────────────────────────────
    if verb in ("NORM", "NORMALIZE"):
        if sec.outer:
            normalize_section(sec)
            return "✓ Chuẩn hoá chiều quay"
        return "⚠ Chưa có outer"

    # ── PRESET ────────────────────────────────────────────────────────────
    if verb == "PRESET":
        name = (parts[1].upper() if len(parts) >= 2 else "AA").replace("-", "")
        if name == "AA":
            ps = preset_supert_AA()
        elif name == "BB":
            ps = preset_supert_BB()
        elif name == "CC":
            ps = preset_supert_CC()
        else:
            return f"⚠ Preset '{name}' không có. Dùng: PRESET AA | BB | CC"
        sec.outer = ps.outer; sec.holes = ps.holes; sec.open = ps.open
        cad_state["mode"] = None; cad_state["current_poly"] = []
        return f"✓ Nạp preset {name}"

    return f"❓ '{cmd_raw}' không nhận diện. Gõ ? để xem lệnh."


# ═══════════════════════════════════════════════════════════════════════════════
# 11. DXF IMPORT
# ═══════════════════════════════════════════════════════════════════════════════

def _chain_lines_to_polys(
    lines: list[tuple[tuple[float, float], tuple[float, float]]],
    tol: float = 0.5,
) -> list[list[tuple[float, float]]]:
    """
    Ghép các đoạn LINE thành danh sách vòng kín.
    lines: list of ((x1,y1),(x2,y2))
    tol  : khoảng cách tối đa để coi hai endpoint là trùng nhau (mm)
    """
    if not lines:
        return []

    # Map endpoint → list of (line_idx, other_endpoint)
    from collections import defaultdict
    adj: dict[int, list[tuple[int, int]]] = defaultdict(list)
    nodes: list[tuple[float, float]] = []
    node_map: dict[tuple[int, int], int] = {}

    def _node(pt: tuple[float, float]) -> int:
        key = (round(pt[0] / tol), round(pt[1] / tol))
        if key not in node_map:
            node_map[key] = len(nodes)
            nodes.append(pt)
        return node_map[key]

    for li, (p1, p2) in enumerate(lines):
        n1, n2 = _node(p1), _node(p2)
        if n1 != n2:
            adj[n1].append((n2, li))
            adj[n2].append((n1, li))

    used_edges: set[int] = set()
    loops: list[list[tuple[float, float]]] = []

    for start in list(adj.keys()):
        for nbr, eid in list(adj[start]):
            if eid in used_edges:
                continue
            path = [start]
            used_edges.add(eid)
            cur = nbr
            # Follow the chain
            while cur != start and len(path) < len(nodes) + 1:
                path.append(cur)
                found = False
                for nxt, neid in adj[cur]:
                    if neid not in used_edges:
                        used_edges.add(neid)
                        cur = nxt
                        found = True
                        break
                if not found:
                    break
            if cur == start and len(path) >= 3:
                pts = [nodes[n] for n in path]
                pts.append(pts[0])
                loops.append(pts)
    return loops


def parse_dxf_bytes(dxf_bytes: bytes) -> dict:
    """
    Đọc file DXF (bytes), trả về dict:
      outer      — list [[x,z], ...] đường biên ngoài (lớn nhất theo diện tích)
      holes      — list of list [[x,z], ...] khoang rỗng
      raw_count  — số polyline/loop đọc được
      width_mm, height_mm — kích thước bounding box (mm)
      entities   — list các loại entity đã tìm thấy (debug)
      error      — chuỗi lỗi nếu thất bại

    Hỗ trợ: LWPOLYLINE, POLYLINE, LINE (tự ghép thành vòng kín).
    Toạ độ: CAD X→MCN X, CAD Y→MCN Z.
    Sau đó dịch chuyển: X=0 tại tâm ngang, Z=0 tại mặt trên (y_max→0).
    Đơn vị giữ nguyên (mặc định mm trong CAD).
    """
    try:
        import ezdxf
    except ImportError:
        return {"error": "Thư viện ezdxf chưa được cài đặt.\nChạy: pip install ezdxf"}

    import io
    import os
    import tempfile

    # Phát hiện DWG (binary) — magic bytes AC10xx
    if dxf_bytes[:4] in (b"AC10", b"AC12", b"AC14"):
        ver = dxf_bytes[:6].decode("ascii", "replace")
        return {
            "error": (
                f"File là DWG ({ver}), không phải DXF.\n"
                "Để upload được, hãy lưu lại dưới dạng DXF trong AutoCAD:\n"
                "  File → Save As → Files of type: AutoCAD 2000/2004/2007 DXF (*.dxf)"
            )
        }

    # Ghi ra file tạm → dùng ezdxf.readfile() để tránh vấn đề encoding/stream
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False, mode="wb") as tmp:
            tmp.write(dxf_bytes)
            tmp_path = tmp.name
        doc = ezdxf.readfile(tmp_path)
    except Exception as exc:
        # Fallback: thử decode text rồi StringIO
        try:
            try:
                _txt = dxf_bytes.decode("utf-8")
            except UnicodeDecodeError:
                _txt = dxf_bytes.decode("cp1252", errors="replace")
            doc = ezdxf.read(io.StringIO(_txt))
        except Exception as exc2:
            return {"error": f"Không đọc được file DXF: {exc2}"}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    msp = doc.modelspace()
    polys: list[list[tuple[float, float]]] = []
    raw_lines: list[tuple[tuple[float, float], tuple[float, float]]] = []
    entity_types: set[str] = set()

    for entity in msp:
        etype = entity.dxftype()
        entity_types.add(etype)
        pts: list[tuple[float, float]] = []
        closed = False

        if etype == "LWPOLYLINE":
            pts = [(float(p[0]), float(p[1])) for p in entity.get_points()]
            closed = bool(entity.is_closed)

        elif etype == "POLYLINE":
            try:
                if entity.get_mode() in ("AnyPolygonMesh", "PolyFaceMesh"):
                    continue
            except Exception:
                pass
            pts = [(float(v.dxf.location.x), float(v.dxf.location.y))
                   for v in entity.vertices]
            closed = bool(entity.is_closed)

        elif etype == "LINE":
            try:
                raw_lines.append((
                    (float(entity.dxf.start.x), float(entity.dxf.start.y)),
                    (float(entity.dxf.end.x),   float(entity.dxf.end.y)),
                ))
            except Exception:
                pass
            continue

        elif etype == "INSERT":
            # Block reference — bỏ qua (không expand block)
            continue

        if not pts or len(pts) < 2:
            continue

        # Force-close nếu flag closed hoặc đầu/cuối gần nhau (< 0.5 mm)
        if pts[0] != pts[-1]:
            gap = ((pts[0][0] - pts[-1][0]) ** 2 +
                   (pts[0][1] - pts[-1][1]) ** 2) ** 0.5
            if closed or gap < 0.5:
                pts = pts + [pts[0]]

        if len(pts) >= 3:
            polys.append(pts)

    # Nếu không có LWPOLYLINE/POLYLINE → thử ghép LINE thành vòng kín
    if not polys and raw_lines:
        polys = _chain_lines_to_polys(raw_lines)

    if not polys:
        found = ", ".join(sorted(entity_types)) or "(trống)"
        return {
            "error": (
                f"Không tìm thấy đường biên khép kín trong file.\n"
                f"Entity đọc được: {found}\n"
                f"Vui lòng vẽ mặt cắt bằng lệnh PLINE (Polyline) trong AutoCAD "
                f"và lưu dưới dạng DXF (không phải DWG)."
            )
        }

    # Tính diện tích → outer = lớn nhất
    def _area(pts: list[tuple[float, float]]) -> float:
        n = len(pts) - 1 if pts[0] == pts[-1] else len(pts)
        a = 0.0
        for i in range(n):
            j = (i + 1) % n
            a += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
        return abs(a) / 2.0

    areas = [_area(p) for p in polys]
    idx_outer = areas.index(max(areas))
    outer_raw = polys[idx_outer]
    holes_raw = [p for i, p in enumerate(polys) if i != idx_outer]

    # Bounding box của outer
    xs = [p[0] for p in outer_raw]
    ys = [p[1] for p in outer_raw]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    x_mid  = (xmin + xmax) / 2.0
    y_top  = ymax   # mặt trên → Z = 0

    def _center(pts: list[tuple[float, float]]) -> list[list[float]]:
        return [[round(p[0] - x_mid, 3), round(p[1] - y_top, 3)] for p in pts]

    return {
        "outer":     _center(outer_raw),
        "holes":     [_center(h) for h in holes_raw],
        "raw_count": len(polys),
        "bbox_raw":  [xmin, xmax, ymin, ymax],
        "width_mm":  round(xmax - xmin, 1),
        "height_mm": round(ymax - ymin, 1),
        "entities":  sorted(entity_types),
    }
