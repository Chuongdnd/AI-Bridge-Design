"""
Module 00-Validation — Quy tắc kiểm tra đầu vào thời gian thực
Được gọi từ 00-Interface.py (wizard steps)
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class FieldResult:
    """Kết quả kiểm tra một trường."""
    ok:      bool
    error:   Optional[str] = None   # Lỗi cứng — block tiếp tục
    warning: Optional[str] = None   # Cảnh báo mềm — vẫn cho tiếp
    hint:    Optional[str] = None   # Gợi ý giá trị hoặc hành động


# ── Bước 1: Thủy văn ─────────────────────────────────────────────────

def check_h1(h1: float, h5: float) -> FieldResult:
    """MNCN phải lớn hơn MNTT (cao độ có thể âm tuỳ vùng — không chặn cứng < 0)."""
    if h1 <= h5:
        return FieldResult(False,
            error=f"MNCN ({h1:.3f}m) phải LỚN HƠN MNTT ({h5:.3f}m)",
            hint=f"Thử đặt MNCN = {h5 + 0.5:.3f}m hoặc giảm MNTT")
    if h1 > 20:
        return FieldResult(True,
            warning=f"MNCN = {h1:.1f}m rất cao — kiểm tra lại đơn vị")
    return FieldResult(True)


def check_h5(h5: float, h1: float, h10: float) -> FieldResult:
    """MNTT phải nằm giữa MNCN và MNTC (không chặn cứng < 0)."""
    if h5 >= h1:
        return FieldResult(False,
            error=f"MNTT ({h5:.3f}m) phải NHỎ HƠN MNCN ({h1:.3f}m)",
            hint=f"Thử đặt MNTT = {h1 - 0.3:.3f}m")
    if h5 <= h10:
        return FieldResult(False,
            error=f"MNTT ({h5:.3f}m) phải LỚN HƠN MNTC ({h10:.3f}m)",
            hint=f"Thử đặt MNTT = {h10 + 0.3:.3f}m")
    return FieldResult(True)


def check_h10(h10: float, h5: float, h98: float) -> FieldResult:
    """MNTC phải nằm giữa MNTT và MNTN (không chặn cứng < 0)."""
    if h10 >= h5:
        return FieldResult(False,
            error=f"MNTC ({h10:.3f}m) phải NHỎ HƠN MNTT ({h5:.3f}m)",
            hint=f"Thử đặt MNTC = {h5 - 0.3:.3f}m")
    if h10 <= h98:
        return FieldResult(False,
            error=f"MNTC ({h10:.3f}m) phải LỚN HƠN MNTN ({h98:.3f}m)",
            hint=f"Thử đặt MNTC = {h98 + 0.3:.3f}m")
    return FieldResult(True)


def check_h98(h98: float, h10: float) -> FieldResult:
    """MNTN phải nhỏ hơn MNTC."""
    if h98 >= h10:
        return FieldResult(False,
            error=f"MNTN ({h98:.3f}m) phải NHỎ HƠN MNTC ({h10:.3f}m)",
            hint=f"Thử đặt MNTN = {h10 - 0.5:.3f}m")
    if h98 < -5:
        return FieldResult(True,
            warning=f"MNTN = {h98:.2f}m âm sâu — kiểm tra lại")
    return FieldResult(True)


def check_x_tim(x: float, lt_min=None, lt_max=None,
                allow_zero: bool = False) -> FieldResult:
    """Lý trình tim cầu phải trong phạm vi địa hình (nếu đã nạp).

    allow_zero=True (nguồn địa hình DXF bình đồ): lý trình 0 là HỢP LỆ — mốc
    0-0 đặt tại giao tim luồng × tim tuyến TK, không phải 'chưa nhập'."""
    if x == 0 and not allow_zero:
        return FieldResult(False,
            error="Chưa nhập lý trình tim cầu",
            hint="Nhập lý trình điểm cầu vượt sông/kênh (đơn vị: m)")
    if lt_min is not None and lt_max is not None:
        if not (lt_min <= x <= lt_max):
            return FieldResult(False,
                error=(f"Lý trình {x:.1f}m nằm ngoài phạm vi "
                       f"địa hình ({lt_min:.1f}–{lt_max:.1f}m)"),
                hint=f"Chọn giá trị trong khoảng {lt_min:.0f}–{lt_max:.0f}m")
    return FieldResult(True)


def check_goc_giao(goc: float) -> FieldResult:
    """Góc giao hợp lệ 30–90°, cảnh báo nếu < 75°."""
    if goc < 30 or goc > 90:
        return FieldResult(False, error="Góc giao phải từ 30° đến 90°")
    if goc < 75:
        return FieldResult(True,
            warning=(f"Góc giao {goc:.0f}° < 75° — cầu xiên, "
                     "cần kiểm tra thêm chiều dài nhịp hiệu dụng"))
    return FieldResult(True)


def check_t_ban(t_mm: float) -> FieldResult:
    """Chiều dày bản mặt cầu tối thiểu 175mm (TCVN 11823-2017)."""
    if t_mm < 175:
        return FieldResult(False,
            error=f"Chiều dày {int(t_mm)}mm vi phạm TCVN 11823-2017 Điều 9.7.1.1",
            hint="Tối thiểu 175mm — đề xuất dùng 200mm cho cầu đường bộ")
    if t_mm > 350:
        return FieldResult(True,
            warning=f"Chiều dày {int(t_mm)}mm rất lớn — kiểm tra lại có đúng không")
    return FieldResult(True)


# ── Bước 2: Hình học ─────────────────────────────────────────────────

def check_vtk(vtk: int, loai_duong: str) -> FieldResult:
    """Vtk phù hợp với loại đường."""
    _ranges = {
        "Cao toc":  (60, 120),
        "O to":     (20,  80),
        "Do thi":   (30,  80),
    }
    lo, hi = _ranges.get(loai_duong, (20, 120))
    if not (lo <= vtk <= hi):
        return FieldResult(False,
            error=f"Vtk {vtk} km/h không phù hợp với {loai_duong} "
                  f"(phạm vi: {lo}–{hi} km/h)")
    return FieldResult(True)


def check_bc(bc: float, n_lan: int, w_lan: float) -> FieldResult:
    """Chiều rộng cầu phải ≥ tổng chiều rộng làn × số làn."""
    bc_min = n_lan * w_lan + 2 * 0.5   # 0.5m lề tối thiểu mỗi bên
    if bc < bc_min:
        return FieldResult(False,
            error=(f"Bề rộng cầu {bc:.1f}m nhỏ hơn tổng làn + lề "
                   f"({bc_min:.1f}m)"),
            hint=f"Đề xuất tối thiểu {bc_min:.1f}m với {n_lan} làn × {w_lan}m")
    if bc > 30:
        return FieldResult(True,
            warning=f"Bề rộng {bc:.1f}m rất lớn — cầu nhiều làn, "
                    "kiểm tra lại MCN")
    return FieldResult(True)


# ── Kiểm tra tổng hợp toàn bộ bước 1 ────────────────────────────────

def validate_step1_full(h1, h5, h10, h98,
                         x_tim, goc, t_ban,
                         lt_min=None, lt_max=None) -> dict:
    """
    Chạy toàn bộ quy tắc bước 1.
    Trả về {'errors': {field: msg}, 'warnings': {field: msg},
            'hints': {field: msg}, 'all_ok': bool}
    """
    results = {
        'h1':    check_h1(h1, h5),
        'h5':    check_h5(h5, h1, h10),
        'h10':   check_h10(h10, h5, h98),
        'h98':   check_h98(h98, h10),
        'x_tim': check_x_tim(x_tim, lt_min, lt_max),
        'goc':   check_goc_giao(goc),
        't_ban': check_t_ban(t_ban),
    }
    errors   = {f: r.error   for f, r in results.items() if r.error}
    warnings = {f: r.warning for f, r in results.items() if r.warning}
    hints    = {f: r.hint    for f, r in results.items() if r.hint}
    return {
        'errors':   errors,
        'warnings': warnings,
        'hints':    hints,
        'all_ok':   len(errors) == 0,
    }
