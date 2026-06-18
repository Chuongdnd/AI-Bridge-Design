"""
Module 08 — Tư vấn Móng Cọc
Logic Rule-Based theo TCVN 11823:2017 (Thiết kế cầu đường bộ)
và TCVN 10304:2014 (Móng cọc — tiêu chuẩn thiết kế).

Phạm vi: chỉ xem xét hai loại cọc phù hợp công trình cầu vừa–lớn tại Việt Nam:
  1. Cọc ép BTCT   — tiết diện vuông 200–450 mm
  2. Cọc khoan nhồi — đường kính 600–1500 mm

Logic phân loại thực hiện qua 4 tầng:
  Tầng 0 — điều kiện loại trừ cứng (TCVN 10304 khoản 7)
  Tầng 1 — chiều sâu đến lớp tựa mũi
  Tầng 2 — môi trường thi công và điều kiện địa tầng
  Tầng 3 — tải trọng đầu cọc
  Tầng 4 — ràng buộc đường kính (CKN ≥ đường kính trụ)
"""

import math

# ═══════════════════════════════════════════════════════════════════════════════
# BẢNG THAM CHIẾU
# ═══════════════════════════════════════════════════════════════════════════════
PILE_TYPES = {
    "Cọc ép BTCT": {
        "mo_ta":      "Cọc BTCT tiết diện vuông, thi công bằng ép tĩnh",
        "tieu_chuan": "TCVN 10304:2014, TCVN 7570:2006",
        "pp_tc":      "Ép tĩnh (ép neo hoặc ép robot)",
        "uu_diem":    "Chi phí thấp; kiểm soát chất lượng tốt qua lực ép; thi công nhanh",
        "nhuoc_diem": "Không tựa mũi vào cát/đá; chiều dài tối đa ~40m; không qua đá mồ côi",
    },
    "Cọc khoan nhồi": {
        "mo_ta":      "Cọc BTCT đổ tại chỗ, thi công bằng khoan tạo lỗ",
        "tieu_chuan": "TCVN 10304:2014",
        "pp_tc":      "Khoan bùn bentonite hoặc vách ống chống thép",
        "uu_diem":    "Chiều sâu lớn; không rung động; đường kính linh hoạt; khoan qua đá",
        "nhuoc_diem": "Chi phí cao; cần thiết bị chuyên dụng; kiểm tra chất lượng phức tạp",
    },
}

# Kích thước chuẩn — (cạnh_mm hoặc D_mm) → thông số
PILE_SIZES = {
    "Cọc ép BTCT": {
        # cạnh_mm: {chieu_rong_mm, tai_trong_tk_kN, chieu_dai_max_m}
        200: {"chieu_rong_mm": 200, "tai_trong_tk_kN": 250,  "chieu_dai_max_m": 20},
        250: {"chieu_rong_mm": 250, "tai_trong_tk_kN": 400,  "chieu_dai_max_m": 28},
        300: {"chieu_rong_mm": 300, "tai_trong_tk_kN": 600,  "chieu_dai_max_m": 32},
        350: {"chieu_rong_mm": 350, "tai_trong_tk_kN": 900,  "chieu_dai_max_m": 36},
        400: {"chieu_rong_mm": 400, "tai_trong_tk_kN": 1200, "chieu_dai_max_m": 40},
        450: {"chieu_rong_mm": 450, "tai_trong_tk_kN": 1500, "chieu_dai_max_m": 40},
    },
    "Cọc khoan nhồi": {
        # D_mm: {duong_kinh_mm, tai_trong_tk_kN, chieu_dai_max_m}
        600:  {"duong_kinh_mm": 600,  "tai_trong_tk_kN": 800,  "chieu_dai_max_m": 60},
        800:  {"duong_kinh_mm": 800,  "tai_trong_tk_kN": 1500, "chieu_dai_max_m": 70},
        1000: {"duong_kinh_mm": 1000, "tai_trong_tk_kN": 2500, "chieu_dai_max_m": 80},
        1200: {"duong_kinh_mm": 1200, "tai_trong_tk_kN": 4000, "chieu_dai_max_m": 90},
        1500: {"duong_kinh_mm": 1500, "tai_trong_tk_kN": 6000, "chieu_dai_max_m": 100},
    },
}

# Nhóm loại đất
_DAT_DINH = {"Sét", "Sét pha"}
_DAT_ROI  = {"Cát", "Cát pha", "Cát lẫn sỏi", "Sỏi cuội"}


# ═══════════════════════════════════════════════════════════════════════════════
# HÀM LOGIC PHÂN LOẠI CỌC
# ═══════════════════════════════════════════════════════════════════════════════
def _select_pile_type(dac_trung, tai_trong, is_urban):
    """
    Phân loại loại cọc qua 4 tầng logic.

    Returns
    -------
    (loai_coc: str, reasons: list[str], warnings: list[str])
    """
    warnings = []
    reasons  = []
    force_ckn = False

    lop_tua       = dac_trung.get("lop_tua_mui_de_xuat") or {}
    co_lop_tua    = dac_trung.get("co_lop_tua_mui_du_kien", False)
    loai_dat      = lop_tua.get("loai_dat", "")
    IL            = lop_tua.get("IL")
    do_sau        = lop_tua.get("do_sau_dinh") or 30.0
    co_set_chay   = dac_trung.get("co_set_chay", False)
    co_da_moi     = dac_trung.get("co_da_moi_co_giua", False)

    # ── Tầng 0: Điều kiện loại trừ cứng ─────────────────────────────────────
    if not co_lop_tua:
        warnings.append(
            "⚠️ Không tìm được lớp tựa mũi phù hợp trong phạm vi hố khoan. "
            "Đề nghị khoan sâu thêm hoặc xem xét cọc ma sát toàn thân. "
            "Kết quả tính toán dưới đây mang tính sơ bộ."
        )

    if loai_dat in _DAT_ROI:
        force_ckn = True
        warnings.append(
            f"❌ [Tầng 0] Lớp tựa mũi là đất rời ({loai_dat}). "
            "Theo TCVN 10304:2014 khoản 7.2.3, cọc ép không được tựa mũi vào cát/sỏi "
            "(hiện tượng từ chối giả làm cọc không đạt chiều sâu thiết kế). "
            "Bắt buộc dùng cọc khoan nhồi."
        )
        reasons.append(f"[Tầng 0] Tựa mũi vào đất rời ({loai_dat}) → bắt buộc CKN")

    elif loai_dat in _DAT_DINH and IL is not None and IL > 0.6:
        force_ckn = True
        warnings.append(
            f"❌ [Tầng 0] Lớp tựa mũi là {loai_dat} có IL={IL:.2f} > 0.6 "
            "(sét dẻo mềm đến dẻo chảy). "
            "Không phù hợp cho cọc ép tựa mũi theo TCVN 10304:2014. "
            "Bắt buộc dùng cọc khoan nhồi."
        )
        reasons.append(f"[Tầng 0] Sét tựa mũi IL={IL:.2f} > 0.6 → bắt buộc CKN")

    if co_da_moi:
        force_ckn = True
        warnings.append(
            "❌ [Tầng 0] Phát hiện lớp đá phong hóa hoặc đá mồ côi nằm giữa hố khoan. "
            "Cọc ép không thể hạ qua lớp đá cứng xen kẹp (TCVN 10304:2014 khoản 7.2.5). "
            "Bắt buộc dùng cọc khoan nhồi để khoan xuyên."
        )
        reasons.append("[Tầng 0] Đá mồ côi/phong hóa giữa hố → bắt buộc CKN")

    if co_set_chay:
        warnings.append(
            "⚠️ [Thông tin] Có lớp sét với IL > 0.6 trong hố khoan. "
            "Cần kiểm tra ảnh hưởng đến ma sát thành cọc và ổn định thân cọc "
            "khi cọc đi qua lớp này (TCVN 10304:2014 khoản 8.2)."
        )

    if force_ckn:
        return "Cọc khoan nhồi", reasons, warnings

    # ── Tầng 1: Chiều sâu đến lớp tựa mũi ─────────────────────────────────
    do_sau_val = float(do_sau)
    if do_sau_val > 35:
        force_ckn = True
        warnings.append(
            f"⚠️ [Tầng 1] Chiều sâu đến lớp tựa mũi = {do_sau_val:.1f}m > 35m. "
            "Cọc ép không đủ khả năng thi công tại chiều sâu này. "
            "Bắt buộc dùng cọc khoan nhồi (TCVN 10304:2014 khoản 6.1)."
        )
        reasons.append(f"[Tầng 1] Chiều sâu {do_sau_val:.1f}m > 35m → bắt buộc CKN")
        return "Cọc khoan nhồi", reasons, warnings

    # ── Chấm điểm tầng 1–3 ─────────────────────────────────────────────────
    score_ep  = 0
    score_ckn = 0

    if do_sau_val < 25:
        score_ep += 2
        reasons.append(f"[Tầng 1] Chiều sâu lớp tốt {do_sau_val:.1f}m < 25m → ưu tiên cọc ép")
    else:
        score_ep  += 1
        score_ckn += 1
        reasons.append(f"[Tầng 1] Chiều sâu lớp tốt {do_sau_val:.1f}m = 25–35m → cân nhắc cả hai")

    # Tầng 2: Môi trường thi công
    if is_urban:
        score_ckn += 2
        reasons.append("[Tầng 2] Khu đô thị → ưu tiên CKN (giảm tiếng ồn/rung động TCVN 11823)")

    if dac_trung.get("co_da_phong_hoa") and not dac_trung.get("co_da_moi_co_giua"):
        score_ckn += 1
        reasons.append("[Tầng 2] Có đá phong hóa → CKN ngàm vào đá khả thi hơn")

    # Tầng 3: Tải trọng
    if tai_trong <= 1200:
        score_ep += 1
        reasons.append(f"[Tầng 3] Tải trọng {tai_trong:.0f}kN ≤ 1.200kN → cọc ép đủ khả năng")
    else:
        score_ckn += 2
        reasons.append(f"[Tầng 3] Tải trọng {tai_trong:.0f}kN > 1.200kN → ưu tiên CKN để giảm số cọc")

    loai = "Cọc ép BTCT" if score_ep > score_ckn else "Cọc khoan nhồi"
    return loai, reasons, warnings


def _select_pile_size(pile_type, tai_trong, duong_kinh_tru=None):
    """
    Chọn kích thước cọc nhỏ nhất thỏa mãn tải trọng và ràng buộc đường kính.

    Giả định tối thiểu 4 cọc/bệ để tính tải 1 cọc.
    Tăng dần số cọc giả định (4→6→8→9→12) cho đến khi tìm được kích thước phù hợp.

    Returns
    -------
    (size_key: int, spec: dict)
    """
    sizes = PILE_SIZES[pile_type]

    for n_est in [4, 6, 8, 9, 12]:
        tai_1coc = tai_trong / n_est
        tai_tk   = tai_1coc / 0.7   # chia hệ số làm việc nhóm
        for size_key in sorted(sizes.keys()):
            spec = sizes[size_key]
            if spec["tai_trong_tk_kN"] < tai_tk:
                continue
            # Tầng 4: D_coc >= D_tru cho CKN
            if pile_type == "Cọc khoan nhồi" and duong_kinh_tru:
                if size_key / 1000 < duong_kinh_tru:
                    continue
            return size_key, spec

    # Fallback: kích thước lớn nhất có thể (ưu tiên thỏa D_tru)
    all_keys = sorted(sizes.keys(), reverse=True)
    if pile_type == "Cọc khoan nhồi" and duong_kinh_tru:
        filtered = [k for k in all_keys if k / 1000 >= duong_kinh_tru]
        key = filtered[0] if filtered else all_keys[0]
    else:
        key = all_keys[0]
    return key, sizes[key]


# ═══════════════════════════════════════════════════════════════════════════════
# HÀM CHÍNH
# ═══════════════════════════════════════════════════════════════════════════════
def predict_foundation(dac_trung_dia_chat, tai_trong_dau_coc,
                       loai_tru=None, duong_kinh_tru=None,
                       is_urban=False, is_river=False,
                       cao_do_dau_coc=None):
    """
    Tư vấn móng cọc theo Rule-Based — TCVN 11823:2017 + TCVN 10304:2014.

    Parameters
    ----------
    dac_trung_dia_chat : dict — từ 00-DiaChat_Loader.dac_trung_tong_hop[hk_name]
                                (hoặc dict tổng hợp từ nhiều hố khoan)
    tai_trong_dau_coc  : float — tổng tải trọng tính toán tác dụng lên một bệ cọc (kN)
    loai_tru           : str   — loại trụ từ Module 07 (thông tin tham khảo)
    duong_kinh_tru     : float — đường kính / bề rộng trụ (m), dùng cho ràng buộc CKN
    is_urban           : bool  — khu vực đô thị (hạn chế tiếng ồn/rung)
    is_river           : bool  — công trình vượt sông
    cao_do_dau_coc     : float — cao độ đầu cọc (m); mặc định = Z mặt đất - 0.5m

    Returns
    -------
    dict đầy đủ thông số tư vấn móng cọc
    """
    # ── Xử lý đầu vào ─────────────────────────────────────────────────────────
    dac_trung = dac_trung_dia_chat or {}
    P_be      = float(tai_trong_dau_coc) if tai_trong_dau_coc else 800.0
    D_tru     = float(duong_kinh_tru) if duong_kinh_tru else None

    lop_tua          = dac_trung.get("lop_tua_mui_de_xuat") or {}
    cao_do_dinh_tua  = lop_tua.get("cao_do_dinh")
    do_sau_dinh      = lop_tua.get("do_sau_dinh") or 25.0
    loai_dat_tua     = lop_tua.get("loai_dat", "")
    RQD_tua          = lop_tua.get("RQD")

    # ── Chọn loại cọc (tầng 0–3) ──────────────────────────────────────────────
    loai_coc, reasons, warnings = _select_pile_type(
        dac_trung, P_be, bool(is_urban)
    )

    # ── Chọn kích thước cọc (tầng 4 tích hợp) ─────────────────────────────────
    size_key, spec = _select_pile_size(loai_coc, P_be, D_tru)

    if loai_coc == "Cọc ép BTCT":
        D_m           = size_key / 1000        # cạnh cọc (m)
        kich_thuoc_str = f"{size_key}×{size_key} mm"
    else:
        D_m           = size_key / 1000        # đường kính (m)
        kich_thuoc_str = f"Ø{size_key} mm"
        # Ghi nhận nếu cần điều chỉnh đường kính vì ràng buộc Tầng 4
        if D_tru and D_m < D_tru:
            warnings.append(
                f"⚠️ [Tầng 4] Đường kính CKN phải ≥ đường kính trụ "
                f"({D_tru*1000:.0f}mm). Đã chọn D={size_key}mm."
            )
        reasons.append(
            f"[Tầng 4] D_coc={size_key}mm"
            + (f" ≥ D_trụ={D_tru*1000:.0f}mm ✓" if D_tru else "")
        )

    # ── Tính chiều dài cắm vào lớp tốt ───────────────────────────────────────
    if loai_dat_tua == "Đá tươi":
        # TCVN 10304:2014 khoản 8.3: ngàm vào đá tươi tối thiểu 0.5m
        cam_vao = 0.5 if (RQD_tua or 0) > 75 else 1.0
    elif loai_dat_tua == "Đá phong hóa":
        cam_vao = max(1.5, 2.0 * D_m)
    else:
        # Đất: max(4m, 4D) — TCVN 10304:2014
        cam_vao = max(4.0, 4.0 * D_m)

    # ── Cao độ đầu cọc và mũi cọc ─────────────────────────────────────────────
    Z_surface = dac_trung.get("Z") or 0.0
    if cao_do_dau_coc is not None:
        cao_do_dc = float(cao_do_dau_coc)
    else:
        cao_do_dc = float(Z_surface) - 0.5  # mặc định: 0.5m dưới mặt đất

    if cao_do_dinh_tua is not None:
        cao_do_mc = float(cao_do_dinh_tua) - cam_vao
        L_coc     = round(cao_do_dc - cao_do_mc, 1)
        L_coc     = max(L_coc, 8.0)  # chiều dài tối thiểu kỹ thuật
    else:
        # Ước tính từ chiều sâu lớp tốt khi không có cao độ tuyệt đối
        L_coc     = round(float(do_sau_dinh) + cam_vao + abs(cao_do_dc - Z_surface), 1)
        L_coc     = max(L_coc, 8.0)
        cao_do_mc = cao_do_dc - L_coc

    # Kiểm tra chiều dài tối đa theo kích thước cọc
    L_max = spec.get("chieu_dai_max_m", 999)
    if L_coc > L_max:
        warnings.append(
            f"⚠️ Chiều dài cọc tính được ({L_coc}m) vượt giới hạn kỹ thuật "
            f"của {kich_thuoc_str} (L_max={L_max}m). "
            "Cân nhắc tăng kích thước cọc hoặc thay đổi độ sâu tựa mũi."
        )

    # ── Số cọc trên bệ ────────────────────────────────────────────────────────
    Q_1coc = spec["tai_trong_tk_kN"]
    # TCVN 10304: so_coc = ceil(P_be / (Q_tk * η_nhóm))
    so_coc = max(4, math.ceil(P_be / (Q_1coc * 0.7)))

    # ── Khoảng cách tim cọc và kích thước bệ ──────────────────────────────────
    kt_tim  = round(3.0 * D_m, 2)   # min 3D (TCVN 10304:2014 khoản 9.3)
    kt_mep  = round(1.5 * D_m, 2)   # từ tim cọc ngoài đến mép bệ

    n_cols  = math.ceil(math.sqrt(so_coc))
    n_rows  = math.ceil(so_coc / n_cols)
    Be_ngang = round((n_cols - 1) * kt_tim + 2 * kt_mep, 2)
    Be_doc   = round((n_rows - 1) * kt_tim + 2 * kt_mep, 2)
    Be_cao   = round(max(1.0, 1.5 * D_m), 2)

    # Cảnh báo xói lở cho cầu vượt sông
    if is_river:
        warnings.append(
            "ℹ️ Công trình vượt sông — kiểm tra xói lở đáy sông theo TCVN 9845:2013; "
            "bảo vệ bệ cọc bằng thảm đá hoặc kè đá hộc."
        )

    # ── Ghi chú và cơ sở lựa chọn ─────────────────────────────────────────────
    tru_info = f"Trụ: {loai_tru}. " if loai_tru else ""
    ghi_chu = (
        f"{tru_info}Chọn {loai_coc} ({kich_thuoc_str}), L={L_coc}m, "
        f"n={so_coc} cọc/bệ. "
        f"Cơ sở: {'; '.join(reasons[:2]) if reasons else 'Rule-Based'}."
    )

    return {
        # Kết quả chính
        "loai_coc":               loai_coc,
        "kich_thuoc_coc":         kich_thuoc_str,
        "kich_thuoc_mm":          size_key,
        "chieu_dai_coc":          L_coc,
        "so_coc_be":              so_coc,
        # Bố trí cọc
        "khoang_cach_tim_coc":    kt_tim,
        "khoang_cach_mep_be":     kt_mep,
        "n_cols_be":              n_cols,
        "n_rows_be":              n_rows,
        # Kích thước bệ cọc
        "kich_thuoc_be":          f"{Be_ngang:.2f}m × {Be_doc:.2f}m × {Be_cao:.2f}m",
        "Be_ngang":               Be_ngang,
        "Be_doc":                 Be_doc,
        "Be_cao":                 Be_cao,
        # Cao độ
        "cao_do_dau_coc":         round(cao_do_dc, 2),
        "cao_do_mui_coc":         round(cao_do_mc, 2),
        "chieu_dai_cam_lop_tot":  cam_vao,
        # Thông tin lớp tựa mũi
        "lop_tua_mui":            lop_tua.get("ten_lop", "Chưa xác định"),
        "loai_dat_tua_mui":       loai_dat_tua,
        "do_sau_tua_mui":         round(float(do_sau_dinh), 1),
        # Thông số tải trọng
        "Q_1coc_tk_kN":           Q_1coc,
        "tai_trong_be_kN":        P_be,
        # Kết quả phân tích
        "warnings":               warnings,
        "ly_do_chon":             reasons,
        "ghi_chu":                ghi_chu,
        "phuong_phap":            "Rule-Based theo TCVN 11823:2017 và TCVN 10304:2014",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TIỆN ÍCH
# ═══════════════════════════════════════════════════════════════════════════════
def format_mong_report(res):
    """Định dạng kết quả thành chuỗi báo cáo ngắn."""
    lines = [
        f"  Loại cọc        : {res['loai_coc']}",
        f"  Kích thước      : {res['kich_thuoc_coc']}",
        f"  Chiều dài cọc   : {res['chieu_dai_coc']} m",
        f"  Số cọc / bệ     : {res['so_coc_be']} cọc",
        f"  Kích thước bệ   : {res['kich_thuoc_be']}",
        f"  Khoảng cách tim : {res['khoang_cach_tim_coc']} m",
        f"  Cao độ đầu cọc  : {res['cao_do_dau_coc']} m",
        f"  Cao độ mũi cọc  : {res['cao_do_mui_coc']} m",
        f"  Lớp tựa mũi     : {res['lop_tua_mui']} ({res['loai_dat_tua_mui']})",
        f"  Phương pháp     : {res['phuong_phap']}",
    ]
    if res["warnings"]:
        lines.append("  --- Cảnh báo kỹ thuật ---")
        for w in res["warnings"]:
            lines.append(f"  {w}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# CHẠY THỬ ĐỘC LẬP
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    # ── Ví dụ 1: Cầu nông thôn nhỏ ──────────────────────────────────────────
    # Tải đầu cọc 600kN, chiều sâu lớp tốt 18m, đất dính, không đô thị
    dac_trung_1 = {
        "lop_tua_mui_de_xuat": {
            "ten_lop":    "Sét cứng",
            "loai_dat":   "Sét",
            "IL":         0.10,
            "RQD":        None,
            "cao_do_dinh": -18.0,
            "cao_do_day":  -26.0,
            "chieu_day":    8.0,
            "do_sau_dinh": 18.0,
            "spt_n_tb":    35.0,
        },
        "co_lop_tua_mui_du_kien": True,
        "co_set_chay":    False,
        "co_da_moi_co_giua": False,
        "co_da_phong_hoa": False,
        "co_da_tuoi":     False,
        "Z":               0.5,
    }

    print("=" * 60)
    print("VÍ DỤ 1 — Cầu nông thôn nhỏ")
    print("  Tải: 600 kN  |  Sâu lớp tốt: 18m  |  Không đô thị")
    print("=" * 60)
    res1 = predict_foundation(
        dac_trung_1,
        tai_trong_dau_coc=600,
        duong_kinh_tru=0.5,
        is_urban=False,
        is_river=True,
    )
    print(format_mong_report(res1))

    # ── Ví dụ 2: Cầu vượt sông cấp IV đô thị ────────────────────────────────
    # Tải 1800kN, sâu 35m, có sét chảy IL=0.7, đô thị
    dac_trung_2 = {
        "lop_tua_mui_de_xuat": {
            "ten_lop":    "Cát chặt vừa",
            "loai_dat":   "Cát",          # cát → tier 0: force CKN
            "IL":         None,
            "RQD":        None,
            "cao_do_dinh": -35.0,
            "cao_do_day":  -42.0,
            "chieu_day":    7.0,
            "do_sau_dinh": 35.0,
            "spt_n_tb":    45.0,
        },
        "co_lop_tua_mui_du_kien": True,
        "co_set_chay":    True,          # có sét IL=0.7 tại độ sâu ~15m
        "co_da_moi_co_giua": False,
        "co_da_phong_hoa": False,
        "co_da_tuoi":     False,
        "Z":               2.0,
    }

    print("\n" + "=" * 60)
    print("VÍ DỤ 2 — Cầu vượt sông cấp IV trong đô thị")
    print("  Tải: 1800 kN  |  Sâu 35m  |  Sét chảy IL=0.7  |  Đô thị")
    print("=" * 60)
    res2 = predict_foundation(
        dac_trung_2,
        tai_trong_dau_coc=1800,
        duong_kinh_tru=1.2,
        is_urban=True,
        is_river=True,
    )
    print(format_mong_report(res2))

    print(f"\nVí dụ 1 → {res1['loai_coc']}  ({res1['kich_thuoc_coc']})  "
          f"L={res1['chieu_dai_coc']}m  n={res1['so_coc_be']}cọc")
    print(f"Ví dụ 2 → {res2['loai_coc']}  ({res2['kich_thuoc_coc']})  "
          f"L={res2['chieu_dai_coc']}m  n={res2['so_coc_be']}cọc")
