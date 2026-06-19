"""
Module 06c — Kiểm tra ràng buộc hình học dầm cầu
Nhận dict geo từ get_beam_geometry_detail() hoặc phiên bản user chỉnh sửa,
trả về danh sách lỗi / cảnh báo / thông tin theo 3 mức độ.

Hàm xuất công khai:
  validate_beam_geometry(geo, loai_dam, cong_nghe)  → dict kết quả
  generate_validation_report(val_result, ...)        → markdown string
"""

from __future__ import annotations
from datetime import datetime
from typing import Any

# ── Ngưỡng tham số — điều chỉnh tại đây, không cần sửa logic ───────────────
VALIDATION_THRESHOLDS: dict[str, Any] = {
    "h_tolerance"          : 5,     # mm — sai lệch tổng chiều cao cho phép
    "web_min"              : 150,   # mm — chiều dày bụng tối thiểu (TCVN 11823)
    "web_recommended"      : 200,   # mm — chiều dày bụng khuyến nghị
    "flange_top_min"       : 100,   # mm — chiều dày cánh trên tối thiểu
    "cover_top_bot"        : 30,    # mm — lớp bảo vệ trên / dưới
    "cover_side"           : 25,    # mm — lớp bảo vệ mặt bên
    "void_supert_tolerance": 10,    # mm — sai lệch B_rong vs giá trị tính từ web
    "void_vert_margin"     : 30,    # mm — khe hở trên/dưới void (chỉ cho hollow slab)
    "solid_end_min"        : 600,   # mm — đoạn đặc đầu dầm tối thiểu
    "solid_end_max"        : 1000,  # mm — đoạn đặc đầu dầm tối đa
    "haunch_max_ratio"     : 0.60,  # — H_vat / H_canh tối đa (Super-T chuẩn ~50%)
    "duct_dia_pre_max"     : 70,    # mm — đường kính ống DUL trước tối đa
    "duct_dia_post_max"    : 100,   # mm — đường kính ống DUL sau tối đa
    "cc_top_ratio_max"     : 0.60,  # — B_tren_CC / B_total tối đa
    # Tỉ lệ L/H theo kinh nghiệm
    "LH_ranges": {
        "Super-T"      : {"optimal": (18, 22), "accept": (15, 25), "limit": (12, 28)},
        "Dầm I"        : {"optimal": (15, 20), "accept": (13, 23), "limit": (10, 26)},
        "T ngược"      : {"optimal": (12, 16), "accept": (10, 18), "limit": (8,  20)},
        "Dầm T"        : {"optimal": (13, 18), "accept": (11, 20), "limit": (9,  22)},
        "Dầm bản rỗng" : {"optimal": (22, 30), "accept": (18, 35), "limit": (14, 40)},
        "Dầm bản"      : {"optimal": (20, 28), "accept": (16, 33), "limit": (12, 38)},
        "_default"     : {"optimal": (15, 22), "accept": (12, 25), "limit": (10, 28)},
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper builder
# ─────────────────────────────────────────────────────────────────────────────

def _item(ten: str, mo_ta: str, thong_so: str,
          hien_tai: Any, de_xuat: Any = None,
          tieu_chuan: str = "TCVN 11823:2017",
          param_key: str | None = None) -> dict:
    """Tạo một mục kết quả kiểm tra chuẩn hoá."""
    return {
        "ten_kiem_tra"        : ten,
        "mo_ta_loi"           : mo_ta,
        "thong_so_lien_quan"  : thong_so,
        "gia_tri_hien_tai"    : hien_tai,
        "gia_tri_de_xuat"     : de_xuat,
        "tham_chieu_tieu_chuan": tieu_chuan,
        "param_key"           : param_key,   # đường dẫn dấu chấm, ví dụ "MC_AA.H_bung"
    }


# ─────────────────────────────────────────────────────────────────────────────
# Nhóm 1 — Nhất quán kích thước tổng thể
# ─────────────────────────────────────────────────────────────────────────────

def _check_geometric_consistency(geo: dict, loai: str, mc: dict, H: int) -> dict:
    errors, warnings, info = [], [], []
    T = VALIDATION_THRESHOLDS

    H_ct   = mc.get("H_canh_tren", 0)
    H_vct  = mc.get("H_vat_canh_tren", 0)
    H_bung = mc.get("H_bung", 0)
    H_cd   = mc.get("H_canh_duoi", 0)
    H_vcd  = mc.get("H_vat_canh_duoi", 0)
    B_ct   = mc.get("B_canh_tren", 0)
    B_cd   = mc.get("B_canh_duoi", 0)

    # ── Tổng chiều cao ──
    H_sum = H_ct + H_vct + H_bung + H_cd + H_vcd
    if H > 0 and abs(H_sum - H) > T["h_tolerance"]:
        de_xuat_bung = H - H_ct - H_vct - H_cd - H_vcd
        errors.append(_item(
            "Tổng chiều cao không khớp H",
            (f"H_ct({H_ct}) + H_vct({H_vct}) + H_bung({H_bung}) + "
             f"H_vcd({H_vcd}) + H_cd({H_cd}) = {H_sum}mm ≠ H = {H}mm "
             f"(sai lệch {abs(H_sum - H)}mm)"),
            "H_ct, H_vct, H_bung, H_vcd, H_cd",
            f"{H_sum} mm", f"H_bung = {de_xuat_bung} mm",
            param_key="MC_AA.H_bung",
        ))
    else:
        info.append(_item(
            "Tổng chiều cao khớp", f"Σ thành phần chiều cao = {H_sum}mm = H",
            "H_ct+H_vct+H_bung+H_vcd+H_cd", f"{H_sum} mm",
        ))

    # ── Kích thước bằng 0 hoặc âm ──
    must_positive = [
        ("H_canh_tren", H_ct), ("H_bung", H_bung),
        ("B_canh_tren", B_ct),
    ]
    if loai not in ("Dầm T",):          # Dầm T không có cánh dưới riêng
        must_positive.append(("B_canh_duoi", B_cd))
    for name, val in must_positive:
        if val <= 0:
            errors.append(_item(
                f"{name} không hợp lệ",
                f"Kích thước {name} = {val}mm — phải > 0",
                name, f"{val} mm", None,
                param_key=f"MC_AA.{name}",
            ))

    # ── Super-T: nhất quán web_out_hw ──
    if loai == "Super-T":
        wo = mc.get("web_out_hw", 0)
        if wo > 0 and abs(B_cd - 2 * wo) > T["h_tolerance"]:
            errors.append(_item(
                "B_canh_duoi không khớp 2×web_out_hw",
                f"B_canh_duoi = {B_cd}mm ≠ 2 × web_out_hw({wo}) = {2*wo}mm",
                "B_canh_duoi, web_out_hw",
                f"{B_cd} mm", f"{2*wo} mm",
                param_key="MC_AA.B_canh_duoi",
            ))

    # ── Tỉ lệ vát ──
    if H_ct > 0 and H_vct > H_ct * T["haunch_max_ratio"]:
        warnings.append(_item(
            "Vát cánh trên quá lớn",
            f"H_vat_canh_tren / H_canh_tren = {H_vct}/{H_ct} = {H_vct/H_ct:.0%} > {T['haunch_max_ratio']:.0%}",
            "H_vat_canh_tren, H_canh_tren",
            f"{H_vct} mm", f"≤ {int(H_ct * T['haunch_max_ratio'])} mm",
            param_key="MC_AA.H_vat_canh_tren",
        ))
    if H_cd > 0 and H_vcd > H_cd * T["haunch_max_ratio"]:
        warnings.append(_item(
            "Vát cánh dưới quá lớn",
            f"H_vat_canh_duoi / H_canh_duoi = {H_vcd}/{H_cd} = {H_vcd/H_cd:.0%} > {T['haunch_max_ratio']:.0%}",
            "H_vat_canh_duoi, H_canh_duoi",
            f"{H_vcd} mm", f"≤ {int(H_cd * T['haunch_max_ratio'])} mm",
            param_key="MC_AA.H_vat_canh_duoi",
        ))

    info.append(_item(
        "Hình học mặt cắt A-A",
        f"B_ct = {B_ct}mm | B_cd = {B_cd}mm | H_bung = {H_bung}mm",
        "B_canh_tren, B_canh_duoi, H_bung", f"H = {H} mm",
    ))
    return {"errors": errors, "warnings": warnings, "info": info}


# ─────────────────────────────────────────────────────────────────────────────
# Nhóm 2 — Ràng buộc khoang rỗng
# ─────────────────────────────────────────────────────────────────────────────

def _check_void_constraints(geo: dict, loai: str, mc: dict, H: int) -> dict:
    errors, warnings, info = [], [], []
    T = VALIDATION_THRESHOLDS

    if loai == "Super-T":
        B_bt   = mc.get("B_bung_top", 110)
        B_bb   = mc.get("B_bung_bot", 160)
        B_cd   = mc.get("B_canh_duoi", 1020)
        B_rt   = mc.get("B_rong_tren", 0)
        B_rb   = mc.get("B_rong_duoi", 0)
        H_bung = mc.get("H_bung", 0)
        H_rong = mc.get("H_rong", 0)
        tol    = T["void_supert_tolerance"]

        # B_rong là giá trị phái sinh — phải nhất quán với B_bung và B_canh_duoi
        exp_rt = B_cd - 2 * B_bt
        exp_rb = B_cd - 2 * B_bb
        if B_rt > 0 and abs(B_rt - exp_rt) > tol:
            errors.append(_item(
                "B_rong_tren không nhất quán với bụng dầm",
                f"B_rong_tren = {B_rt}mm ≠ B_cd - 2×B_bung_top = {exp_rt}mm "
                f"(sai lệch {abs(B_rt - exp_rt)}mm > {tol}mm)",
                "B_rong_tren, B_bung_top, B_canh_duoi",
                f"{B_rt} mm", f"{exp_rt} mm",
                param_key="MC_AA.B_rong_tren",
            ))
        if B_rb > 0 and abs(B_rb - exp_rb) > tol:
            errors.append(_item(
                "B_rong_duoi không nhất quán với bụng dầm",
                f"B_rong_duoi = {B_rb}mm ≠ B_cd - 2×B_bung_bot = {exp_rb}mm "
                f"(sai lệch {abs(B_rb - exp_rb)}mm > {tol}mm)",
                "B_rong_duoi, B_bung_bot, B_canh_duoi",
                f"{B_rb} mm", f"{exp_rb} mm",
                param_key="MC_AA.B_rong_duoi",
            ))

        # Hình dạng hình thang — rộng ở trên là đúng Super-T
        if B_rt < B_rb:
            warnings.append(_item(
                "Khoang rỗng hẹp hơn ở trên (ngược thực tế Super-T)",
                f"B_rong_tren ({B_rt}mm) < B_rong_duoi ({B_rb}mm). "
                "Cấu tạo chuẩn: khoang rỗng rộng hơn ở trên.",
                "B_rong_tren, B_rong_duoi",
                f"trên={B_rt}mm, dưới={B_rb}mm", f"trên ≥ {B_rb}mm",
                param_key="MC_AA.B_rong_tren",
            ))

        # Chiều cao khoang rỗng <= chiều cao bụng
        if H_rong > H_bung:
            errors.append(_item(
                "Khoang rỗng cao hơn chiều cao bụng",
                f"H_rong = {H_rong}mm > H_bung = {H_bung}mm — void xuyên vào cánh",
                "H_rong, H_bung",
                f"{H_rong} mm", f"= {H_bung} mm",
                param_key="MC_AA.H_rong",
            ))
        else:
            info.append(_item(
                "Khoang rỗng Super-T",
                f"Hình thang: trên={B_rt}mm / dưới={B_rb}mm / cao={H_rong}mm",
                "B_rong_tren, B_rong_duoi, H_rong", f"{B_rt}×{H_rong}mm",
            ))

    elif loai == "Dầm bản rỗng":
        D       = mc.get("B_rong", 300)     # đường kính lỗ tròn
        so_rong = mc.get("so_rong", 3)
        kc_rong = mc.get("kc_rong", 330)    # khoảng cách tim
        y_rong  = mc.get("y_rong", 0)       # tâm lỗ tính từ đáy
        H_ct    = mc.get("H_canh_tren", 0)
        H_cd    = mc.get("H_canh_duoi", 0)
        B_total = geo.get("B", 990)
        vm      = T["void_vert_margin"]

        # Lỗ rỗng phải nằm trong bản
        top_edge = H - H_ct - vm
        bot_edge = H_cd + vm
        if y_rong + D / 2 > top_edge:
            errors.append(_item(
                "Lỗ rỗng phạm vào cánh trên",
                f"Tâm lỗ y={y_rong}mm + R={D//2}mm = {y_rong + D//2}mm > {top_edge}mm (giới hạn trên)",
                "y_rong, B_rong, H_canh_tren",
                f"{y_rong + D//2} mm", f"≤ {int(top_edge)} mm",
                param_key="MC_AA.y_rong",
            ))
        if y_rong - D / 2 < bot_edge:
            errors.append(_item(
                "Lỗ rỗng phạm vào cánh dưới",
                f"Tâm lỗ y={y_rong}mm - R={D//2}mm = {y_rong - D//2}mm < {bot_edge}mm (giới hạn dưới)",
                "y_rong, B_rong, H_canh_duoi",
                f"{y_rong - D//2} mm", f"≥ {int(bot_edge)} mm",
                param_key="MC_AA.y_rong",
            ))

        # Các lỗ phải vừa trong chiều rộng bản
        if so_rong > 0 and kc_rong > 0:
            total_w = (so_rong - 1) * kc_rong + D
            avail_w = B_total - 2 * T["cover_side"]
            if total_w > avail_w:
                errors.append(_item(
                    "Các lỗ rỗng không vừa chiều rộng dầm",
                    f"Chiều rộng cần = (n-1)×kc + D = {total_w}mm > B - 2×25 = {avail_w}mm",
                    "so_rong, kc_rong, B_rong, B",
                    f"{total_w} mm", f"Giảm kc_rong hoặc so_rong",
                    param_key="MC_AA.kc_rong",
                ))
            else:
                info.append(_item(
                    "Lỗ rỗng dầm bản",
                    f"{so_rong} lỗ ∅{D}mm, kc_tim={kc_rong}mm, tổng rộng={total_w}mm/{avail_w}mm",
                    "so_rong, B_rong, kc_rong", f"{so_rong}×∅{D}mm",
                ))

    else:
        info.append(_item(
            "Tiết diện đặc", "Không có khoang rỗng — bỏ qua kiểm tra.",
            "-", "-",
        ))

    return {"errors": errors, "warnings": warnings, "info": info}


# ─────────────────────────────────────────────────────────────────────────────
# Nhóm 3 — Tỉ lệ kích thước theo kinh nghiệm
# ─────────────────────────────────────────────────────────────────────────────

def _check_dimension_ratios(geo: dict, loai: str, mc: dict, H: int) -> dict:
    errors, warnings, info = [], [], []
    T = VALIDATION_THRESHOLDS
    L_mm = geo.get("L", 0)
    if L_mm <= 0 or H <= 0:
        return {"errors": errors, "warnings": warnings, "info": info}

    L_m = L_mm / 1000.0
    lh  = (L_m * 1000) / H       # L(mm)/H(mm) = L(m)/H(m)
    rng = T["LH_ranges"].get(loai, T["LH_ranges"]["_default"])
    opt_lo, opt_hi = rng["optimal"]
    acc_lo, acc_hi = rng["accept"]
    lim_lo, lim_hi = rng["limit"]

    if lh < lim_lo or lh > lim_hi:
        errors.append(_item(
            "Tỉ lệ L/H ngoài giới hạn kỹ thuật",
            f"L/H = {L_m:.1f}m / {H/1000:.3f}m = {lh:.1f} — giới hạn [{lim_lo}, {lim_hi}] cho {loai}",
            "L, H", f"{lh:.1f}",
            f"L/H trong [{opt_lo}, {opt_hi}] (tối ưu)",
            tieu_chuan="Kinh nghiệm thiết kế VN + Eurocode 2",
        ))
    elif lh < acc_lo or lh > acc_hi:
        warnings.append(_item(
            "Tỉ lệ L/H ngoài vùng khuyến nghị",
            f"L/H = {lh:.1f} — khuyến nghị [{opt_lo}, {opt_hi}], chấp nhận được [{acc_lo}, {acc_hi}]",
            "L, H", f"{lh:.1f}",
            f"[{opt_lo} – {opt_hi}]",
            tieu_chuan="Kinh nghiệm thiết kế VN",
        ))
    else:
        info.append(_item(
            "Tỉ lệ L/H tốt",
            f"L/H = {lh:.1f} nằm trong vùng tối ưu [{opt_lo}, {opt_hi}] cho {loai}",
            "L, H", f"{lh:.1f}",
        ))

    return {"errors": errors, "warnings": warnings, "info": info}


# ─────────────────────────────────────────────────────────────────────────────
# Nhóm 4 — Tuân thủ TCVN 11823
# ─────────────────────────────────────────────────────────────────────────────

def _check_tcvn_compliance(geo: dict, loai: str, mc: dict) -> dict:
    errors, warnings, info = [], [], []
    T = VALIDATION_THRESHOLDS

    # Chiều dày bụng
    # Super-T: B_bung_bot là thành bụng chịu lực chính (gần trục trung hoà),
    #          B_bung_top là thành vỏ trên khoang rỗng — không áp dụng 150mm ở đây
    if loai == "Super-T":
        bung_min = mc.get("B_bung_bot", 0)   # thành bụng dưới, tiêu biểu cho TCVN
        pk       = "MC_AA.B_bung_bot"
    else:
        bung_min = mc.get("B_bung", 0)
        pk       = "MC_AA.B_bung"

    if bung_min > 0:
        if bung_min < T["web_min"]:
            errors.append(_item(
                "Bụng dầm quá mỏng — vi phạm TCVN 11823",
                f"Chiều dày bụng = {bung_min}mm < {T['web_min']}mm (Điều 5.7.3.2)",
                "B_bung", f"{bung_min} mm", f"{T['web_min']} mm",
                tieu_chuan="TCVN 11823:2017 Điều 5.7.3.2",
                param_key=pk,
            ))
        elif bung_min < T["web_recommended"] and loai != "Super-T":
            # Super-T chuẩn có B_bung_bot=160mm < 200mm — không cảnh báo, đây là giá trị tiêu chuẩn
            warnings.append(_item(
                "Bụng dầm mỏng hơn khuyến nghị",
                f"Chiều dày bụng = {bung_min}mm < {T['web_recommended']}mm (khuyến nghị cho DUL)",
                "B_bung", f"{bung_min} mm", f"{T['web_recommended']} mm",
                param_key=pk,
            ))
        else:
            info.append(_item(
                "Chiều dày bụng đạt yêu cầu",
                f"B_bung = {bung_min}mm ≥ {T['web_min']}mm (TCVN)",
                "B_bung", f"{bung_min} mm",
            ))

    # Chiều dày cánh trên
    H_ct = mc.get("H_canh_tren", 0)
    if 0 < H_ct < T["flange_top_min"]:
        warnings.append(_item(
            "Cánh trên mỏng hơn khuyến nghị TCVN",
            f"H_canh_tren = {H_ct}mm < {T['flange_top_min']}mm (TCVN 11823 khuyến nghị tối thiểu)",
            "H_canh_tren", f"{H_ct} mm", f"{T['flange_top_min']} mm",
            param_key="MC_AA.H_canh_tren",
        ))
    elif H_ct >= T["flange_top_min"]:
        info.append(_item(
            "Cánh trên đạt chiều dày tối thiểu",
            f"H_canh_tren = {H_ct}mm ≥ {T['flange_top_min']}mm",
            "H_canh_tren", f"{H_ct} mm",
        ))

    return {"errors": errors, "warnings": warnings, "info": info}


# ─────────────────────────────────────────────────────────────────────────────
# Nhóm 5 — Tương thích công nghệ DUL
# ─────────────────────────────────────────────────────────────────────────────

def _check_dul_compatibility(geo: dict, loai: str, cap: dict,
                              cong_nghe: str) -> dict:
    errors, warnings, info = [], [], []
    T = VALIDATION_THRESHOLDS
    ong_D    = cap.get("ong_PVC_D", 0)
    so_ong   = cap.get("so_ong", 0)
    L_m      = geo.get("L", 0) / 1000.0

    # Đường kính ống
    if ong_D > 0:
        max_D = T["duct_dia_pre_max"] if cong_nghe == "DUL_truoc" else T["duct_dia_post_max"]
        cn_vn = "DUL trước" if cong_nghe == "DUL_truoc" else "DUL sau"
        if ong_D > max_D:
            errors.append(_item(
                f"Đường kính ống cáp vượt giới hạn {cn_vn}",
                f"ong_PVC_D = {ong_D}mm > {max_D}mm (giới hạn cho {cn_vn})",
                "ong_PVC_D", f"{ong_D} mm", f"≤ {max_D} mm",
                tieu_chuan="TCVN 11823:2017 Điều 5.10.3",
                param_key="cap_DUL.ong_PVC_D",
            ))
        else:
            info.append(_item(
                "Đường kính ống cáp phù hợp",
                f"∅{ong_D}mm ≤ {max_D}mm ({cn_vn})",
                "ong_PVC_D", f"∅{ong_D} mm",
            ))

    # Số ống cáp — kinh nghiệm Super-T
    if loai == "Super-T" and so_ong > 0 and L_m > 0:
        if L_m < 30:
            rmin, rmax = 4, 10
        elif L_m < 37:
            rmin, rmax = 8, 14
        else:
            rmin, rmax = 9, 16

        if so_ong < rmin:
            warnings.append(_item(
                "Số ống cáp có thể chưa đủ",
                f"Super-T L={L_m:.1f}m: {so_ong} ống < {rmin} (khuyến nghị {rmin}–{rmax})",
                "so_ong, L", f"{so_ong}", f"{rmin}–{rmax}",
                tieu_chuan="Kinh nghiệm thiết kế VN",
                param_key="cap_DUL.so_ong",
            ))
        elif so_ong > rmax:
            warnings.append(_item(
                "Số ống cáp có thể quá nhiều",
                f"Super-T L={L_m:.1f}m: {so_ong} ống > {rmax} (khuyến nghị {rmin}–{rmax})",
                "so_ong, L", f"{so_ong}", f"{rmin}–{rmax}",
                tieu_chuan="Kinh nghiệm thiết kế VN",
                param_key="cap_DUL.so_ong",
            ))
        else:
            info.append(_item(
                "Số ống cáp phù hợp",
                f"{so_ong} ống trong vùng khuyến nghị {rmin}–{rmax} cho L={L_m:.1f}m",
                "so_ong", f"{so_ong}",
            ))

    return {"errors": errors, "warnings": warnings, "info": info}


# ─────────────────────────────────────────────────────────────────────────────
# Nhóm 6 — Tính khả thi thi công
# ─────────────────────────────────────────────────────────────────────────────

def _check_construction_compatibility(geo: dict, loai: str) -> dict:
    errors, warnings, info = [], [], []
    T  = VALIDATION_THRESHOLDS
    bb = geo.get("MC_BB", {})
    cc = geo.get("MC_CC", {})
    B_total = geo.get("B", 0)

    if loai == "Super-T":
        L_dau = bb.get("L_dau_dac", 0)
        if L_dau > 0:
            if L_dau < T["solid_end_min"]:
                warnings.append(_item(
                    "Đoạn đặc đầu dầm ngắn — nguy cơ mất neo cáp",
                    f"L_dau_dac = {L_dau}mm < {T['solid_end_min']}mm (tối thiểu cho neo cáp DUL sau)",
                    "MC_BB.L_dau_dac", f"{L_dau} mm", f"{T['solid_end_min']} mm",
                    param_key="MC_BB.L_dau_dac",
                ))
            elif L_dau > T["solid_end_max"]:
                warnings.append(_item(
                    "Đoạn đặc đầu dầm dài hơn cần thiết",
                    f"L_dau_dac = {L_dau}mm > {T['solid_end_max']}mm — lãng phí vật liệu",
                    "MC_BB.L_dau_dac", f"{L_dau} mm", f"600–1000 mm",
                    param_key="MC_BB.L_dau_dac",
                ))
            else:
                info.append(_item(
                    "Đoạn đặc đầu dầm đạt yêu cầu",
                    f"L_dau_dac = {L_dau}mm trong [{T['solid_end_min']}, {T['solid_end_max']}]mm",
                    "MC_BB.L_dau_dac", f"{L_dau} mm",
                ))

        # Mặt cắt C-C: chiều rộng cánh trên
        B_tren_cc = cc.get("B_tren", 0)
        if B_tren_cc > 0 and B_total > 0:
            ratio = B_tren_cc / B_total
            if ratio > T["cc_top_ratio_max"]:
                warnings.append(_item(
                    "Cánh trên mặt cắt C-C khá rộng",
                    f"B_tren_CC / B = {B_tren_cc}/{B_total} = {ratio:.0%} > {T['cc_top_ratio_max']:.0%}",
                    "MC_CC.B_tren, B", f"{ratio:.0%}", f"≤ {T['cc_top_ratio_max']:.0%}",
                    param_key="MC_CC.B_tren",
                ))
            else:
                info.append(_item(
                    "Tỉ lệ cánh trên C-C hợp lý",
                    f"B_tren_CC/B = {ratio:.0%} ≤ {T['cc_top_ratio_max']:.0%}",
                    "MC_CC.B_tren", f"{ratio:.0%}",
                ))

    return {"errors": errors, "warnings": warnings, "info": info}


# ─────────────────────────────────────────────────────────────────────────────
# Hàm chính
# ─────────────────────────────────────────────────────────────────────────────

def validate_beam_geometry(geo: dict, loai_dam: str,
                           cong_nghe: str = "DUL_sau") -> dict:
    """
    Kiểm tra toàn bộ ràng buộc hình học cho một loại dầm cầu.

    Parameters
    ----------
    geo       : dict  — từ get_beam_geometry_detail() hoặc user chỉnh sửa
    loai_dam  : str   — "Super-T" | "Dầm I" | "T ngược" | "Dầm T" | "Dầm bản rỗng"
    cong_nghe : str   — "DUL_truoc" hoặc "DUL_sau" (mặc định "DUL_sau")

    Returns
    -------
    dict:
        info_messages       : list[dict]  — thông tin xác nhận (xanh dương)
        warnings            : list[dict]  — cảnh báo kỹ thuật (vàng)
        errors              : list[dict]  — lỗi nghiêm trọng (đỏ)
        co_loi_nghiem_trong : bool
    """
    mc   = geo.get("MC_AA", {})
    H    = geo.get("H", 0)
    cap  = geo.get("cap_DUL", {})

    all_errors, all_warnings, all_info = [], [], []

    groups = [
        _check_geometric_consistency(geo, loai_dam, mc, H),
        _check_void_constraints     (geo, loai_dam, mc, H),
        _check_dimension_ratios     (geo, loai_dam, mc, H),
        _check_tcvn_compliance      (geo, loai_dam, mc),
        _check_dul_compatibility    (geo, loai_dam, cap, cong_nghe),
        _check_construction_compatibility(geo, loai_dam),
    ]
    for r in groups:
        all_errors   .extend(r["errors"])
        all_warnings .extend(r["warnings"])
        all_info     .extend(r["info"])

    return {
        "info_messages"        : all_info,
        "warnings"             : all_warnings,
        "errors"               : all_errors,
        "co_loi_nghiem_trong"  : len(all_errors) > 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Xuất báo cáo Markdown
# ─────────────────────────────────────────────────────────────────────────────

def generate_validation_report(val_result: dict, loai_dam: str = "",
                                L_m: float = 0, ten_phien_ban: str = "",
                                **meta) -> str:
    """
    Sinh báo cáo kiểm tra hình học dạng Markdown.

    Returns
    -------
    str — có thể hiển thị qua st.markdown() hoặc tải về dưới dạng .md
    """
    ts    = datetime.now().strftime("%Y-%m-%d %H:%M")
    errs  = val_result.get("errors", [])
    warns = val_result.get("warnings", [])
    infos = val_result.get("info_messages", [])
    ok    = len(errs) == 0

    def _icon_row(n, label, icon):
        return f"| {icon} {label} | **{n}** |"

    lines = [
        "# Báo cáo kiểm tra hình học dầm cầu",
        "",
        f"- **Loại dầm:** {loai_dam or 'N/A'}",
    ]
    if L_m:
        lines.append(f"- **Chiều dài:** {L_m:.1f} m")
    if ten_phien_ban:
        lines.append(f"- **Phiên bản:** {ten_phien_ban}")
    lines += [
        f"- **Thời gian kiểm tra:** {ts}",
        "",
        "## Tóm tắt kết quả",
        "",
        "| Mục | Kết quả |",
        "|-----|---------|",
        _icon_row(len(errs),  "Lỗi nghiêm trọng", "🔴"),
        _icon_row(len(warns), "Cảnh báo",          "🟡"),
        _icon_row(len(infos), "Thông tin đạt",     "🔵"),
        f"| **Kết luận tổng thể** | **{'✅ ĐẠT' if ok else '❌ KHÔNG ĐẠT'}** |",
        "",
    ]

    if errs:
        lines += [f"## 🔴 Lỗi nghiêm trọng ({len(errs)})", ""]
        for i, e in enumerate(errs, 1):
            lines += [
                f"### {i}. {e['ten_kiem_tra']}",
                f"- **Mô tả:** {e['mo_ta_loi']}",
                f"- **Thông số:** `{e['thong_so_lien_quan']}`",
                f"- **Hiện tại:** {e['gia_tri_hien_tai']}",
                f"- **Đề xuất sửa:** {e['gia_tri_de_xuat'] or 'Xem lại thiết kế'}",
                f"- **Tham chiếu:** {e['tham_chieu_tieu_chuan']}",
                "",
            ]

    if warns:
        lines += [f"## 🟡 Cảnh báo ({len(warns)})", ""]
        for i, w in enumerate(warns, 1):
            lines += [
                f"### {i}. {w['ten_kiem_tra']}",
                f"- **Mô tả:** {w['mo_ta_loi']}",
                f"- **Hiện tại:** {w['gia_tri_hien_tai']}",
                f"- **Đề xuất:** {w['gia_tri_de_xuat'] or 'Xem xét điều chỉnh'}",
                "",
            ]

    if infos:
        lines += [f"## 🔵 Thông tin xác nhận ({len(infos)})", ""]
        for inf in infos:
            lines.append(f"- **{inf['ten_kiem_tra']}:** {inf['mo_ta_loi']}")
        lines.append("")

    lines += [
        "---",
        "*Được tạo tự động bởi Hệ thống Thiết kế Cầu AI — Module 06c-Beam_Validator*",
    ]
    return "\n".join(l for l in lines if l is not None)


# ─────────────────────────────────────────────────────────────────────────────
# 5 Test scenarios
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import copy

    # ── Dữ liệu tham chiếu Super-T 38.2m (lấy từ _supert_section(2200,1750,38200)) ──
    GEO_SUPERT_38 = {
        "L": 38200, "B": 2440, "H": 1750, "S": 2200,
        "MC_AA": {
            "B_canh_tren": 2200, "H_canh_tren": 150,
            "B_vat_canh_tren": 100, "H_vat_canh_tren": 75,
            "B_bung_top": 110, "B_bung_bot": 160,
            "H_bung": 1250,
            "B_canh_duoi": 1020, "H_canh_duoi": 225,
            "B_vat_canh_duoi": 50, "H_vat_canh_duoi": 50,
            "web_out_hw": 510,
            "B_rong_tren": 800, "B_rong_duoi": 700, "H_rong": 1250,
        },
        "MC_BB": {"L_dau_dac": 750, "B": 2440, "H": 1750, "dac": True},
        "MC_CC": {"L_dau_dac": 750, "B_tren": 1020, "B_duoi": 1020,
                  "H": 1750, "H_canh_tren_CC": 300},
        "cap_DUL": {"ong_PVC_D": 49, "so_ong": 12, "duong_di": "parabol"},
    }

    def _run(label, geo, loai, cn="DUL_sau"):
        r = validate_beam_geometry(geo, loai, cn)
        print(f"\n{'='*60}")
        print(f"Kịch bản: {label}")
        print(f"  Lỗi: {len(r['errors'])}  |  Cảnh báo: {len(r['warnings'])}  |  "
              f"Info: {len(r['info_messages'])}  |  co_loi_nghiem_trong: {r['co_loi_nghiem_trong']}")
        for e in r["errors"]:
            print(f"  🔴 {e['ten_kiem_tra']}: {e['mo_ta_loi'][:80]}")
        for w in r["warnings"]:
            print(f"  🟡 {w['ten_kiem_tra']}: {w['mo_ta_loi'][:80]}")
        return r

    # 1. Super-T 38.2m tiêu chuẩn → 0 lỗi / 0 cảnh báo
    _run("Super-T 38.2m chuẩn (kỳ vọng 0 lỗi)", GEO_SUPERT_38, "Super-T")

    # 2. B_canh_duoi > B_canh_tren → lỗi đỏ, nút bị khóa
    geo2 = copy.deepcopy(GEO_SUPERT_38)
    geo2["MC_AA"]["B_canh_duoi"] = 2500     # > B_canh_tren=2200 (phi lý)
    geo2["MC_AA"]["web_out_hw"]  = 1250     # khiến B_cd=2500 nhưng void 800 → vi phạm
    _run("B_canh_duoi > B_canh_tren (kỳ vọng lỗi đỏ)", geo2, "Super-T")

    # 3. L/H ngoài vùng accept (25,28] → cảnh báo vàng
    # Super-T accept=[15,25], limit=[12,28]
    # L=38.2m, H=1450mm → L/H = 38200/1450 = 26.3 → ngoài accept (>25) nhưng trong limit (<28) → warning
    geo3 = copy.deepcopy(GEO_SUPERT_38)
    geo3["H"] = 1450
    geo3["MC_AA"]["H_bung"] = 1450 - 150 - 75 - 225 - 50   # = 950
    geo3["MC_AA"]["H_rong"] = 950
    _run("L/H = 26.3 (kỳ vọng cảnh báo vàng, 0 lỗi)", geo3, "Super-T")

    # 4. Khoang rỗng vượt ra ngoài bụng → lỗi đỏ
    geo4 = copy.deepcopy(GEO_SUPERT_38)
    geo4["MC_AA"]["B_rong_tren"] = 950      # > B_cd - 2×B_bt = 1020 - 220 = 800
    _run("Khoang rỗng quá rộng (kỳ vọng lỗi đỏ)", geo4, "Super-T")

    # 5. Auto-fix: xem gia_tri_de_xuat cho lỗi tổng chiều cao
    geo5 = copy.deepcopy(GEO_SUPERT_38)
    geo5["MC_AA"]["H_bung"] = 1000          # tổng = 150+75+1000+50+225 = 1500 ≠ 1750
    r5 = _run("H_bung sai → auto-fix đề xuất (kỳ vọng H_bung=1250)", geo5, "Super-T")
    if r5["errors"]:
        e = r5["errors"][0]
        print(f"\n  → Auto-fix: param_key={e['param_key']}, de_xuat={e['gia_tri_de_xuat']}")
