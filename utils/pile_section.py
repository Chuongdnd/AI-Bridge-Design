"""
utils/pile_section.py — Chi tiết MẶT CẮT NGANG cọc (parametric).

Người dùng tạo chi tiết cọc trong Thư viện móng bằng cách chọn dạng mặt cắt và
nhập kích thước; module sinh biên dạng polygon (mm) + đường kính tương đương để:
  - hiển thị xem trước mặt cắt,
  - cấp đường kính (m) cho sơ đồ cọc / các hình mố–trụ.

Thuần Python (không phụ thuộc Streamlit/Plotly) để dễ kiểm thử & tái dùng.
Đơn vị toạ độ polygon: mm; gốc tại tâm mặt cắt.
"""
from __future__ import annotations

import math

SHAPES = ["Tròn", "Vuông", "Chữ nhật", "Đa giác đều"]
DEFAULT_SHAPE = "Tròn"


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(d)


def section_polygon(shape, b_mm, h_mm=None, n_sides=8, n_arc=48):
    """Sinh biên dạng ngoài mặt cắt cọc (list [x, z] mm, tâm ở gốc).

    - Tròn      : b = đường kính.
    - Vuông     : b = cạnh.
    - Chữ nhật  : b = bề rộng (ngang), h = chiều cao (dọc).
    - Đa giác đều: b = đường kính vòng tròn ngoại tiếp, n_sides = số cạnh.
    """
    b = max(1.0, _f(b_mm, 1.0))
    shape = str(shape or DEFAULT_SHAPE)
    if shape == "Tròn":
        r = b / 2.0
        return [[r * math.cos(t), r * math.sin(t)]
                for t in [2 * math.pi * k / n_arc for k in range(n_arc)]]
    if shape == "Vuông":
        a = b / 2.0
        return [[-a, -a], [a, -a], [a, a], [-a, a]]
    if shape == "Chữ nhật":
        bw = b / 2.0
        hh = max(1.0, _f(h_mm, b)) / 2.0
        return [[-bw, -hh], [bw, -hh], [bw, hh], [-bw, hh]]
    if shape == "Đa giác đều":
        n = max(3, int(_f(n_sides, 8)))
        r = b / 2.0
        # đỉnh đầu hướng lên, mặt cắt cân đối
        off = math.pi / 2.0
        return [[r * math.cos(off + 2 * math.pi * k / n),
                 r * math.sin(off + 2 * math.pi * k / n)] for k in range(n)]
    # fallback: tròn
    r = b / 2.0
    return [[r * math.cos(t), r * math.sin(t)]
            for t in [2 * math.pi * k / n_arc for k in range(n_arc)]]


def equivalent_D_m(shape, b_mm, h_mm=None, n_sides=8):
    """Đường kính tương đương (m) — dùng cho sơ đồ cọc & ký hiệu.

    Tròn → Ø; Vuông → cạnh; Chữ nhật → cạnh lớn; Đa giác đều → đường kính
    vòng ngoại tiếp. (Quy ước đơn giản, đủ cho bố trí & vẽ ký hiệu.)"""
    b = max(0.0, _f(b_mm, 0.0))
    shape = str(shape or DEFAULT_SHAPE)
    if shape == "Chữ nhật":
        return max(b, _f(h_mm, b)) / 1000.0
    return b / 1000.0


def section_area_mm2(shape, b_mm, h_mm=None, n_sides=8):
    """Diện tích mặt cắt (mm²)."""
    b = max(0.0, _f(b_mm, 0.0))
    shape = str(shape or DEFAULT_SHAPE)
    if shape == "Tròn":
        return math.pi * (b / 2.0) ** 2
    if shape == "Vuông":
        return b * b
    if shape == "Chữ nhật":
        return b * _f(h_mm, b)
    if shape == "Đa giác đều":
        n = max(3, int(_f(n_sides, 8)))
        r = b / 2.0
        return 0.5 * n * r * r * math.sin(2 * math.pi / n)
    return math.pi * (b / 2.0) ** 2


def describe(shape, b_mm, h_mm=None, n_sides=8):
    """Mô tả ngắn gọn mặt cắt cọc cho nhãn hiển thị."""
    shape = str(shape or DEFAULT_SHAPE)
    b = _f(b_mm, 0.0)
    if shape == "Tròn":
        return f"Tròn Ø{b:.0f}"
    if shape == "Vuông":
        return f"Vuông {b:.0f}×{b:.0f}"
    if shape == "Chữ nhật":
        return f"CN {b:.0f}×{_f(h_mm, b):.0f}"
    if shape == "Đa giác đều":
        return f"{int(_f(n_sides, 8))} cạnh Ø{b:.0f}"
    return f"{shape} {b:.0f}"


def section_fields(shape, b_mm, h_mm=None, n_sides=8):
    """Trả về dict các trường mặt cắt + đường kính tương đương (m) để ghi vào
    bản ghi móng trong thư viện."""
    return {
        "tiet_dien": str(shape or DEFAULT_SHAPE),
        "canh_b": round(_f(b_mm, 0.0), 1),
        "canh_h": round(_f(h_mm, 0.0), 1),
        "so_canh": int(_f(n_sides, 0)),
        "duong_kinh_coc": round(equivalent_D_m(shape, b_mm, h_mm, n_sides), 3),
    }
