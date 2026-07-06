"""
utils/pile_plan.py — Đọc SƠ ĐỒ CỌC từ bản vẽ mặt bằng (DXF) + schema bố trí cọc.

Quy ước:
  - Người dùng vẽ mặt bằng bệ cọc, mỗi cọc là một ĐƯỜNG TRÒN (CIRCLE):
        tâm circle  → vị trí cọc
        bán kính    → bán kính cọc (D = 2*r)
  - Trục bản vẽ:  X (ngang màn hình) = NGANG cầu,  Y = DỌC cầu.
        (có thể xoay 90° khi import nếu bản vẽ đặt ngược)
  - Tọa độ cọc được CĂN TÂM về trọng tâm nhóm cọc (gốc = tâm bệ).

Mỗi cọc lưu dạng dict:
    {
      "x":  float,   # ngang cầu (m), gốc = tâm bệ
      "y":  float,   # dọc  cầu (m)
      "D":  float,   # đường kính cọc (m)
      "L":  float,   # chiều dài cọc (m)            — nhập ở bảng (mặt bằng không có)
      "ix": float,   # độ xiên theo trục DỌC  (tan góc, 0 = thẳng đứng)
      "iy": float,   # độ xiên theo trục NGANG (tan góc, 0 = thẳng đứng)
    }

Bố trí cọc cho 1 vị trí (mố/trụ):
    {"piles": [ {pile}, ... ], "note": str}

Module thuần Python (không phụ thuộc Streamlit) để dễ kiểm thử.
"""
from __future__ import annotations

import io
import math

try:
    import ezdxf
    from ezdxf import recover as _ezdxf_recover
except Exception:  # pragma: no cover - ezdxf luôn có trong project
    ezdxf = None
    _ezdxf_recover = None


# ── Mặc định ──────────────────────────────────────────────────────────────────
DEFAULT_D = 1.0     # m — đường kính cọc mặc định khi bản vẽ không có thông tin
DEFAULT_L = 30.0    # m — chiều dài cọc mặc định
PILE_KEYS = ("x", "y", "D", "L", "ix", "iy")

# Hệ số quy đổi đơn vị bản vẽ → MÉT
UNIT_TO_M = {"mm": 0.001, "cm": 0.01, "dm": 0.1, "m": 1.0}
# Mã $INSUNITS (DXF) → tên đơn vị
_INSUNITS_NAME = {1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m", 14: "dm"}
_INSUNITS_TO_M = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0, 14: 0.1}


def _resolve_scale(doc, raw_pts, unit):
    """Xác định hệ số quy đổi bản vẽ → mét và mô tả nguồn gốc.

    unit: 'auto' | 'mm' | 'cm' | 'dm' | 'm'. 'auto' → đọc $INSUNITS, nếu không
    có thì đoán theo độ lớn kích thước (bệ cọc thực tế chỉ vài… vài chục mét)."""
    u = str(unit or "auto").strip().lower()
    if u in UNIT_TO_M:
        return UNIT_TO_M[u], u
    # auto: thử $INSUNITS
    try:
        ins = int(getattr(doc, "units", 0) or 0)
    except Exception:
        ins = 0
    if ins in _INSUNITS_TO_M:
        return _INSUNITS_TO_M[ins], f"auto·$INSUNITS={_INSUNITS_NAME.get(ins, ins)}"
    # heuristic theo độ lớn extent
    if raw_pts:
        xs = [p[0] for p in raw_pts]; ys = [p[1] for p in raw_pts]
        extent = max(max(xs) - min(xs), max(ys) - min(ys), 2.0 * max(p[2] for p in raw_pts))
    else:
        extent = 0.0
    if extent > 1000:      # >1000 đơn vị → chắc chắn mm
        return 0.001, "auto·đoán mm"
    if extent > 100:       # 100…1000 → cm
        return 0.01, "auto·đoán cm"
    return 1.0, "auto·đoán m"


def make_pile(x=0.0, y=0.0, D=DEFAULT_D, L=DEFAULT_L, ix=0.0, iy=0.0) -> dict:
    """Tạo 1 cọc với đầy đủ trường, ép kiểu float an toàn."""
    def _f(v, d):
        try:
            return float(v)
        except (TypeError, ValueError):
            return float(d)
    return {
        "x": _f(x, 0.0), "y": _f(y, 0.0),
        "D": max(0.1, _f(D, DEFAULT_D)),
        "L": max(0.0, _f(L, DEFAULT_L)),
        "ix": _f(ix, 0.0), "iy": _f(iy, 0.0),
    }


def normalize_pile(p: dict) -> dict:
    """Chuẩn hóa 1 dict cọc bất kỳ về schema đầy đủ."""
    p = p or {}
    return make_pile(
        x=p.get("x", 0.0), y=p.get("y", 0.0),
        D=p.get("D", DEFAULT_D), L=p.get("L", DEFAULT_L),
        ix=p.get("ix", 0.0), iy=p.get("iy", 0.0),
    )


def _read_doc(dxf_bytes: bytes):
    """Đọc DXF từ bytes, có fallback recover cho file lỗi nhẹ."""
    if ezdxf is None:
        raise RuntimeError("Thiếu thư viện ezdxf để đọc DXF.")
    text = dxf_bytes.decode("utf-8", errors="ignore") if isinstance(dxf_bytes, (bytes, bytearray)) else dxf_bytes
    try:
        doc = ezdxf.read(io.StringIO(text))
    except Exception:
        if _ezdxf_recover is None:
            raise
        doc, _auditor = _ezdxf_recover.read(io.StringIO(text))
    return doc


def _dedupe_concentric(raw, tol_m):
    """Gộp các vòng tròn ĐỒNG TÂM (cùng tâm trong dung sai tol_m) thành 1 cọc —
    giữ bán kính LỚN NHẤT (vòng ngoài = chu vi cọc). raw: [(x,y,r)] đã quy về m."""
    used = [False] * len(raw)
    out = []
    for i, (xi, yi, ri) in enumerate(raw):
        if used[i]:
            continue
        group = [(xi, yi, ri)]
        used[i] = True
        for j in range(i + 1, len(raw)):
            if used[j]:
                continue
            xj, yj, rj = raw[j]
            if abs(xj - xi) <= tol_m and abs(yj - yi) <= tol_m:
                group.append((xj, yj, rj))
                used[j] = True
        # tâm trung bình, bán kính lớn nhất
        gx = sum(g[0] for g in group) / len(group)
        gy = sum(g[1] for g in group) / len(group)
        gr = max(g[2] for g in group)
        out.append((gx, gy, gr))
    return out, (len(raw) - len(out))


def _median(vals):
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def _collect_circles(msp, want_layers):
    out = []
    for e in msp.query("CIRCLE"):
        if want_layers is not None:
            if str(getattr(e.dxf, "layer", "")).strip().lower() not in want_layers:
                continue
        c = e.dxf.center
        r = float(e.dxf.radius)
        if r > 0:
            out.append((float(c.x), float(c.y), r))
    return out


def _detect_cross_centers(msp, want_layers):
    """Phát hiện TIM CỌC từ dấu '+' (2 đoạn thẳng vuông góc cắt nhau).

    - Lấy các LINE ngắn (loại bỏ đường tim cầu dài) → tách nhóm gần NGANG và
      gần ĐỨNG; mỗi cặp H×V cắt nhau cho 1 tâm.
    - Bổ sung POINT và INSERT (block) làm tâm cọc nếu có.
    Trả về list (x, y) theo đơn vị bản vẽ.
    """
    H = []  # (x0, x1, y, L)  đoạn gần ngang
    V = []  # (y0, y1, x, L)  đoạn gần đứng
    lens = []
    for e in msp.query("LINE"):
        if want_layers is not None:
            if str(getattr(e.dxf, "layer", "")).strip().lower() not in want_layers:
                continue
        a = e.dxf.start; b = e.dxf.end
        dx = float(b.x) - float(a.x); dy = float(b.y) - float(a.y)
        L = math.hypot(dx, dy)
        if L <= 1e-9:
            continue
        ang = math.degrees(math.atan2(abs(dy), abs(dx)))
        if ang <= 15.0:
            H.append((min(a.x, b.x), max(a.x, b.x), 0.5 * (a.y + b.y), L)); lens.append(L)
        elif ang >= 75.0:
            V.append((min(a.y, b.y), max(a.y, b.y), 0.5 * (a.x + b.x), L)); lens.append(L)

    centers = []
    if H and V:
        # Ngưỡng độ dài cánh dấu '+': loại đường tim cầu (dài hơn nhiều)
        med = _median(lens)
        max_arm = max(med * 3.0, 1e-6)
        Hs = [h for h in H if h[3] <= max_arm]
        Vs = [v for v in V if v[3] <= max_arm]
        tol = max(med * 0.15, 1e-9)
        for (hx0, hx1, hy, hL) in Hs:
            for (vy0, vy1, vx, vL) in Vs:
                # H và V có cắt nhau? (giao tại (vx, hy))
                if (hx0 - tol) <= vx <= (hx1 + tol) and (vy0 - tol) <= hy <= (vy1 + tol):
                    centers.append((vx, hy))

    # POINT / INSERT làm tâm cọc (nếu bản vẽ dùng kiểu này)
    for e in msp.query("POINT"):
        if want_layers is not None:
            if str(getattr(e.dxf, "layer", "")).strip().lower() not in want_layers:
                continue
        p = e.dxf.location
        centers.append((float(p.x), float(p.y)))
    for e in msp.query("INSERT"):
        if want_layers is not None:
            if str(getattr(e.dxf, "layer", "")).strip().lower() not in want_layers:
                continue
        p = e.dxf.insert
        centers.append((float(p.x), float(p.y)))

    # Gộp các tâm trùng/sát nhau
    if not centers:
        return []
    span = max(max(c[0] for c in centers) - min(c[0] for c in centers),
               max(c[1] for c in centers) - min(c[1] for c in centers), 1.0)
    ctol = span * 0.01  # 1% kích thước cụm
    uniq = []
    for (x, y) in centers:
        if all(abs(x - ux) > ctol or abs(y - uy) > ctol for (ux, uy) in uniq):
            uniq.append((x, y))
    return uniq


def parse_pile_plan_bytes(
    dxf_bytes: bytes,
    *,
    swap_xy: bool = False,
    center: bool = True,
    default_L: float = DEFAULT_L,
    layers: list | None = None,
    unit: str = "mm",
    merge_concentric: bool = True,
    source: str = "cross",
    pile_D: float = DEFAULT_D,
    pile_L: float | None = None,
) -> dict:
    """
    Đọc DXF mặt bằng → danh sách TIM CỌC.

    Tham số:
      swap_xy   : True nếu bản vẽ đặt DỌC cầu theo trục X (xoay 90°).
      center    : True → căn tọa độ về trọng tâm nhóm cọc (gốc = tâm bệ).
      default_L : chiều dài cọc mặc định (dùng khi không truyền pile_L).
      layers    : nếu cho danh sách tên layer → chỉ lấy đối tượng thuộc layer đó.
      unit      : 'mm' (mặc định) | 'cm' | 'dm' | 'm' | 'auto'.
      source    : 'cross' (mặc định) nhận TIM CỌC qua dấu '+'; 'circle' qua
                  vòng tròn; 'auto' thử dấu '+' trước, không có thì dùng vòng tròn.
      pile_D    : đường kính cọc (m) lấy từ THƯ VIỆN CHI TIẾT CỌC — gán cho mọi
                  cọc khi nhận theo dấu '+' (mặt bằng không quyết định hình dáng).
      pile_L    : chiều dài cọc (m) từ thư viện; None → dùng default_L.

    Trả về dict: piles, n, warnings, bbox(m), scale, unit, source.
    """
    warnings: list[str] = []
    pile_L = float(pile_L) if pile_L is not None else float(default_L)
    doc = _read_doc(dxf_bytes)
    msp = doc.modelspace()
    want_layers = {str(l).strip().lower() for l in layers} if layers else None

    used = source
    # raw_u: danh sách (x, y, r|None) theo đơn vị bản vẽ; r=None → lấy D từ thư viện
    raw_u = []
    if source in ("cross", "auto"):
        centers = _detect_cross_centers(msp, want_layers)
        if centers:
            raw_u = [(x, y, None) for (x, y) in centers]
            used = "cross"
        elif source == "cross":
            warnings.append("Không thấy dấu '+' (tim cọc) nào — thử chọn nhận theo "
                            "Vòng tròn, hoặc kiểm tra layer.")
            return {"piles": [], "n": 0, "warnings": warnings, "bbox": (0, 0, 0, 0),
                    "scale": 1.0, "unit": "—", "source": used}
    if not raw_u:  # circle hoặc auto-fallback
        circles = _collect_circles(msp, want_layers)
        if not circles:
            warnings.append("Không tìm thấy tim cọc (dấu '+') hay vòng tròn nào.")
            return {"piles": [], "n": 0, "warnings": warnings, "bbox": (0, 0, 0, 0),
                    "scale": 1.0, "unit": "—", "source": used}
        raw_u = [(x, y, r) for (x, y, r) in circles]
        used = "circle"

    # Quy đổi đơn vị → mét
    scale, unit_desc = _resolve_scale(doc, raw_u, unit)
    raw = [(x * scale, y * scale, (r * scale if r is not None else None))
           for (x, y, r) in raw_u]

    # Gộp vòng tròn đồng tâm (chỉ khi nhận theo vòng tròn)
    if used == "circle" and merge_concentric:
        rr = [r for _, _, r in raw if r]
        if rr:
            tol = max(0.05, min(rr) * 0.25)
            raw3 = [(x, y, r) for (x, y, r) in raw]
            raw3, n_merged = _dedupe_concentric(raw3, tol)
            raw = [(x, y, r) for (x, y, r) in raw3]
            if n_merged:
                warnings.append(f"Đã gộp {n_merged} vòng tròn đồng tâm.")

    # Xoay 90° nếu cần
    pts = []
    for cx, cy, r in raw:
        x_ngang, y_doc = (cy, cx) if swap_xy else (cx, cy)
        pts.append((x_ngang, y_doc, r))

    # Căn tâm về trọng tâm
    if center and pts:
        mx = sum(p[0] for p in pts) / len(pts)
        my = sum(p[1] for p in pts) / len(pts)
        pts = [(x - mx, y - my, r) for (x, y, r) in pts]

    piles = [make_pile(x=x, y=y,
                       D=(2.0 * r if r is not None else pile_D),
                       L=pile_L)
             for (x, y, r) in pts]
    piles.sort(key=lambda p: (round(p["y"], 3), round(p["x"], 3)))

    xs = [p["x"] for p in piles]
    ys = [p["y"] for p in piles]
    bbox = (min(xs), min(ys), max(xs), max(ys))

    ds = sorted(p["D"] for p in piles)
    # Cảnh báo đường kính bất thường chỉ áp dụng khi đọc từ vòng tròn
    if used == "circle":
        if ds and ds[-1] > 2.5 * ds[0]:
            warnings.append(
                f"Đường kính cọc chênh lệch lớn (Ø{ds[0]:.2f}…{ds[-1]:.2f}m) — "
                "kiểm tra vòng tròn không phải cọc bị đọc nhầm không."
            )
        if ds and (ds[0] < 0.2 or ds[-1] > 4.0):
            warnings.append(
                f"Đường kính cọc = Ø{ds[0]:.2f}…{ds[-1]:.2f}m sau quy đổi ({unit_desc}). "
                "Nếu sai, chọn lại đơn vị bản vẽ."
            )
    return {"piles": piles, "n": len(piles), "warnings": warnings, "bbox": bbox,
            "scale": scale, "unit": unit_desc, "source": used}


# ── Truy cập / lưu bố trí cọc trong design_data ──────────────────────────────
def get_layouts(d: dict) -> dict:
    """Trả về dict pile_layouts (tạo nếu chưa có)."""
    if not isinstance(d, dict):
        return {}
    return d.get("pile_layouts") or {}


def get_layout(d: dict, pos_key: str) -> dict | None:
    """Lấy bố trí cọc đã khai cho 1 vị trí; None nếu chưa khai."""
    lay = get_layouts(d).get(pos_key)
    if not lay:
        return None
    piles = [normalize_pile(p) for p in (lay.get("piles") or [])]
    if not piles:
        return None
    return {"piles": piles, "note": lay.get("note", "")}


def set_layout(d: dict, pos_key: str, piles: list, note: str = "") -> None:
    """Ghi bố trí cọc cho 1 vị trí vào design_data (chuẩn hóa schema)."""
    if "pile_layouts" not in d or not isinstance(d.get("pile_layouts"), dict):
        d["pile_layouts"] = {}
    d["pile_layouts"][pos_key] = {
        "piles": [normalize_pile(p) for p in (piles or [])],
        "note": note,
    }


def pile_position_keys(n_nhip: int) -> list[tuple[str, str]]:
    """
    Sinh danh sách (key, nhãn) các vị trí theo số nhịp:
      n_nhip nhịp → (n_nhip - 1) trụ giữa + 2 mố.
    Key trụ dùng dạng 'tru_1', 'tru_2'… ĐỒNG BỘ với ve_mcn_vi_tri().
    """
    out = [("mo_trai", "Mố trái")]
    n_tru = max(0, int(n_nhip) - 1)
    for i in range(n_tru):
        out.append((f"tru_{i+1}", f"Trụ T{i+1}"))
    out.append(("mo_phai", "Mố phải"))
    return out


# ── Hình học cọc xiên (dùng chung cho 2D/3D render) ──────────────────────────
def pile_bottom(p: dict, z_top: float):
    """
    Tính tọa độ ĐÁY cọc từ ĐỈNH cọc (x, y, z_top) và độ xiên.
      Δngang = iy * L , Δdọc = ix * L , Δz = -L  (xấp xỉ: L đo theo phương đứng)
    Trả về (x_bot, y_bot, z_bot).
    """
    L = float(p.get("L", 0.0))
    return (
        float(p["x"]) + float(p.get("iy", 0.0)) * L,
        float(p["y"]) + float(p.get("ix", 0.0)) * L,
        z_top - L,
    )


def slope_ratio_to_tan(n: float) -> float:
    """Đổi 'độ xiên 1:n' → tan góc nghiêng (1/n). n<=0 → 0 (thẳng đứng)."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if abs(n) < 1e-9 else 1.0 / n


def tan_to_slope_ratio(t: float) -> float:
    """Đổi tan góc → 'n' của 1:n (0 nếu thẳng đứng)."""
    try:
        t = float(t)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if abs(t) < 1e-9 else 1.0 / t


# ═══════════════════════════════════════════════════════════════════════════════
# LƯỚI CỌC MẶC ĐỊNH TỪ mong_result (Module 08 — TCVN 10304:2025)
# ═══════════════════════════════════════════════════════════════════════════════
def default_grid(mong: dict) -> dict:
    """Sinh LƯỚI CỌC MẶC ĐỊNH từ mong_result Module 08 (khi người dùng chưa
    upload DXF sơ đồ cọc): n_cols × n_rows cọc, tim-tim = khoang_cach_tim,
    căn tâm về (0,0) = tâm bệ.

    Trả: {"piles": [pile...], "Be_ngang", "Be_doc", "S", "D", "note"}
    (schema pile như make_pile — dùng được cho mọi hàm vẽ hiện có)."""
    m = mong or {}
    D = float(m.get("D_coc_mm") or m.get("kich_thuoc_mm") or 800) / 1000.0
    L = float(m.get("chieu_dai_coc") or m.get("L_coc_tu") or DEFAULT_L)
    n = int(m.get("so_coc_be") or m.get("So_coc_tu") or 4)
    S = float(m.get("khoang_cach_tim") or m.get("khoang_cach_tim_coc")
              or 3.0 * D)
    n_cols = int(m.get("n_cols_be") or math.ceil(math.sqrt(n)))
    n_rows = int(m.get("n_rows_be") or math.ceil(n / max(1, n_cols)))
    kt_mep = float(m.get("khoang_cach_mep_be") or (D / 2 + 0.3))

    piles = []
    k = 0
    for r in range(n_rows):
        for c in range(n_cols):
            if k >= n:
                break
            piles.append(make_pile(
                x=(c - (n_cols - 1) / 2.0) * S,
                y=(r - (n_rows - 1) / 2.0) * S,
                D=D, L=L))
            k += 1
    Be_ngang = float(m.get("Be_ngang") or ((n_cols - 1) * S + 2 * kt_mep))
    Be_doc   = float(m.get("Be_doc")   or ((n_rows - 1) * S + 2 * kt_mep))
    return {"piles": piles, "Be_ngang": round(Be_ngang, 2),
            "Be_doc": round(Be_doc, 2), "S": S, "D": D,
            "note": (f"Lưới mặc định {n_rows}×{n_cols}, tim-tim {S:g}m "
                     f"(TCVN 10304:2025)")}


def grid_figure(mong: dict):
    """Vẽ MẶT BẰNG BỆ CỌC (plotly) từ mong_result: bệ + cọc + kích thước
    tim-tim / mép bệ theo TCVN 10304:2025. Trả go.Figure."""
    import plotly.graph_objects as go
    g = default_grid(mong)
    piles, D, S = g["piles"], g["D"], g["S"]
    W, Hd = g["Be_ngang"], g["Be_doc"]
    m = mong or {}
    la_ckn = "khoan nhồi" in str(m.get("loai_coc") or m.get("loai_mong") or "").lower()

    fig = go.Figure()
    # Bệ cọc
    fig.add_shape(type="rect", x0=-W/2, x1=W/2, y0=-Hd/2, y1=Hd/2,
                  line=dict(color="#7f8c8d", width=2),
                  fillcolor="rgba(127,140,141,0.10)")
    # Cọc
    for p in piles:
        fig.add_shape(type="circle",
                      x0=p["x"]-D/2, x1=p["x"]+D/2,
                      y0=p["y"]-D/2, y1=p["y"]+D/2,
                      line=dict(color="#2c3e50", width=2),
                      fillcolor="rgba(52,73,94,0.25)")
    # Kích thước tim-tim (2 cọc đầu hàng dưới, nếu có ≥ 2 cột)
    xs = sorted({round(p["x"], 3) for p in piles})
    ys = sorted({round(p["y"], 3) for p in piles})
    if len(xs) >= 2:
        y_dim = min(ys) - max(0.5, D)
        fig.add_annotation(x=(xs[0]+xs[1])/2, y=y_dim,
                           text=f"tim-tim S={S:g}m", showarrow=False,
                           font=dict(size=11, color="#c0392b"))
        fig.add_shape(type="line", x0=xs[0], x1=xs[1], y0=y_dim+0.2,
                      y1=y_dim+0.2, line=dict(color="#c0392b", width=1))
    # Mép bệ
    mep = float(m.get("khoang_cach_mep") or (0.3 if la_ckn else 0.225))
    fig.add_annotation(x=W/2, y=max(ys) if ys else 0,
                       text=f"mặt cọc→mép bệ ≥{mep*1000:.0f}mm",
                       showarrow=False, xanchor="left",
                       font=dict(size=10, color="#2980b9"))
    tt = m.get("khoang_cach_thong_thuy")
    title = (f"MẶT BẰNG BỆ CỌC — {len(piles)} cọc D{D*1000:.0f} · "
             f"bệ {W:g}×{Hd:g}m"
             + (f" · thông thủy {tt:g}m" if tt else ""))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13)),
        xaxis=dict(scaleanchor="y", scaleratio=1, title="Ngang cầu (m)",
                   zeroline=False),
        yaxis=dict(title="Dọc cầu (m)", zeroline=False),
        height=420, margin=dict(t=50, b=40, l=40, r=20),
        plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
    return fig
