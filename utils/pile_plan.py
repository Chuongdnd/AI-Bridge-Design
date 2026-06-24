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


def parse_pile_plan_bytes(
    dxf_bytes: bytes,
    *,
    swap_xy: bool = False,
    center: bool = True,
    default_L: float = DEFAULT_L,
    layers: list | None = None,
    unit: str = "auto",
    merge_concentric: bool = True,
) -> dict:
    """
    Đọc các CIRCLE trong DXF mặt bằng → danh sách cọc.

    Tham số:
      swap_xy   : True nếu bản vẽ đặt DỌC cầu theo trục X (xoay 90°).
      center    : True → căn tọa độ về trọng tâm nhóm cọc (gốc = tâm bệ).
      default_L : chiều dài cọc gán mặc định (mặt bằng không thể hiện L).
      layers    : nếu cho danh sách tên layer → chỉ lấy CIRCLE thuộc layer đó.
      unit      : 'auto' | 'mm' | 'cm' | 'dm' | 'm' — đơn vị bản vẽ (quy về mét).
      merge_concentric : gộp vòng tròn đồng tâm (cọc vẽ 2 vòng) thành 1.

    Trả về dict:
      {
        "piles": [...], "n": int, "warnings": [...],
        "bbox": (xmin,ymin,xmax,ymax),   # theo m, đã căn tâm
        "scale": float, "unit": str,     # hệ số quy đổi & mô tả đơn vị
      }
    """
    warnings: list[str] = []
    doc = _read_doc(dxf_bytes)
    msp = doc.modelspace()

    want_layers = {str(l).strip().lower() for l in layers} if layers else None

    raw_u = []  # (cx, cy, r) theo đơn vị bản vẽ
    for e in msp.query("CIRCLE"):
        if want_layers is not None:
            lname = str(getattr(e.dxf, "layer", "")).strip().lower()
            if lname not in want_layers:
                continue
        c = e.dxf.center
        r = float(e.dxf.radius)
        if r <= 0:
            continue
        raw_u.append((float(c.x), float(c.y), r))

    if not raw_u:
        warnings.append("Không tìm thấy đối tượng CIRCLE nào trong bản vẽ.")
        return {"piles": [], "n": 0, "warnings": warnings, "bbox": (0, 0, 0, 0),
                "scale": 1.0, "unit": "—"}

    # Quy đổi đơn vị → mét
    scale, unit_desc = _resolve_scale(doc, raw_u, unit)
    raw = [(x * scale, y * scale, r * scale) for (x, y, r) in raw_u]

    # Gộp vòng tròn đồng tâm (cọc vẽ bằng 2 vòng tròn)
    if merge_concentric:
        # dung sai = 1/4 bán kính nhỏ nhất, tối thiểu 5cm
        rmin = min(r for _, _, r in raw)
        tol = max(0.05, rmin * 0.25)
        raw, n_merged = _dedupe_concentric(raw, tol)
        if n_merged:
            warnings.append(f"Đã gộp {n_merged} vòng tròn đồng tâm (cọc vẽ 2 vòng).")

    # Xoay 90° nếu cần (DỌC cầu nằm trên trục X của bản vẽ)
    pts = []
    for cx, cy, r in raw:
        if swap_xy:
            x_ngang, y_doc = cy, cx
        else:
            x_ngang, y_doc = cx, cy
        pts.append((x_ngang, y_doc, r))

    # Căn tâm về trọng tâm
    if center and pts:
        mx = sum(p[0] for p in pts) / len(pts)
        my = sum(p[1] for p in pts) / len(pts)
        pts = [(x - mx, y - my, r) for (x, y, r) in pts]

    piles = [make_pile(x=x, y=y, D=2.0 * r, L=default_L) for (x, y, r) in pts]
    # Sắp xếp theo hàng (dọc) rồi cột (ngang) cho dễ nhìn ở bảng
    piles.sort(key=lambda p: (round(p["y"], 3), round(p["x"], 3)))

    xs = [p["x"] for p in piles]
    ys = [p["y"] for p in piles]
    bbox = (min(xs), min(ys), max(xs), max(ys))

    # Cảnh báo nếu đường kính cọc bất thường (có thể đọc nhầm vòng tròn khác)
    ds = sorted(p["D"] for p in piles)
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
            "scale": scale, "unit": unit_desc}


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
