"""
Module 08 — Tư vấn Móng Cọc
Logic Rule-Based theo TCVN 11823:2017 (Thiết kế cầu đường bộ)
và TCVN 10304:2025 (Móng cọc — tiêu chuẩn thiết kế).

Cấu trúc 4 NHÓM LOGIC (A → D) tương ứng 4 khía cạnh bài toán móng cọc:
  A — Lựa chọn LOẠI CỌC theo ĐƯỜNG KÍNH (_select_pile_category):
      • "small" D ≤ 0.6m — cọc đóng/ép vuông 200–450mm, cọc tròn ly tâm
        D300–D600; Q_tk 250–1800 kN. Cầu nhịp nhỏ, tải đầu cọc thấp, nền
        không quá rắn, không đá tảng/đá mồ côi trong phạm vi cắm cọc.
      • "large" D = 0.8–2m — cọc khoan nhồi D800–D2000; Q_tk 1500–6000 kN.
        Tải trọng lớn, yêu cầu chịu tải + chống uốn cao, đô thị hạn chế
        rung động, có đá phong hóa/đá mồ côi cần khoan xuyên.
        RÀNG BUỘC BẮT BUỘC: D_coc ≥ D_tru.
  B — CHIỀU DÀI CỌC + TẦNG TỰA MŨI (_check_bearing_layer, _calc_pile_length):
      • Lớp tựa mũi đạt: đất dính SPT-N ≥ 30; đất rời SPT-N ≥ 40; đá RQD > 60%.
      • Chiều sâu cắm: đất chặt/dính cứng ≥ 3.0m; đất yếu/rời ≥ 6.0m;
        đá tươi RQD > 75% (hoặc đạt độ chối) ngàm ≥ 0.5m.
      • Kiểm tra L/D ≤ 37 khi nền yếu (SPT tb < 15 trong 10m đầu);
        kiểm tra kinh tế Q_vật_liệu so Q_đất_nền (chênh > 40% → cảnh báo).
  C — SỐ LƯỢNG CỌC (_calc_pile_number):
      n = max(4, ⌈P_bệ / (Q_1cọc × η_g)⌉ × dự phòng 1.05–1.10)
      η_g: đất dính → Converse-Labarre; đất rời → 0.9–1.0.
  D — KHOẢNG CÁCH BỐ TRÍ (_calc_pile_layout):
      • Đóng/ép: tim-tim ≥ max(750mm, 2.5D); mũi ma sát ≥ 3D;
        mặt ngoài cọc → mép bệ ≥ 225mm.
      • Khoan nhồi: tim-tim > 3.0D; thông thủy thân cọc ≥ 1.0m; mặt bên
        cọc → mép bệ ≥ 300mm; tim-tim < 4D (không ống vách) và < 6D →
        cảnh báo tương tác / trình tự thi công.
"""

import math

# ═══════════════════════════════════════════════════════════════════════════════
# BẢNG THAM CHIẾU
# ═══════════════════════════════════════════════════════════════════════════════

# ── A. PHÂN LOẠI CỌC THEO ĐƯỜNG KÍNH (TCVN 10304:2025) ────────────────────────
PILE_CATEGORY = {
    "small": {
        "ten":       "Cọc đường kính nhỏ (D ≤ 0.6m)",
        "gom":       ("Cọc đóng / cọc ép tiết diện vuông 200–450mm; "
                      "cọc tròn ly tâm D300–D600mm"),
        "Q_tk_kN":   (250, 1800),
        "dieu_kien": ("Cầu nhịp nhỏ, tải trọng đầu cọc thấp, nền đất không "
                      "quá rắn, KHÔNG có đá tảng / đá mồ côi trong phạm vi "
                      "cắm cọc."),
    },
    "large": {
        "ten":       "Cọc đường kính lớn (D = 0.8–2m)",
        "gom":       "Cọc khoan nhồi D800, D1000, D1200, D1500, D2000",
        "Q_tk_kN":   (1500, 6000),
        "dieu_kien": ("Công trình tải trọng lớn, yêu cầu sức chịu tải và "
                      "chống uốn cao, cầu đô thị hạn chế rung động, có đá "
                      "phong hóa / đá mồ côi cần khoan xuyên. RÀNG BUỘC: "
                      "D_cọc ≥ D_trụ."),
    },
}

PILE_TYPES = {
    "Cọc ép BTCT": {
        "mo_ta":      "Cọc BTCT tiết diện vuông, thi công bằng ép tĩnh",
        "tieu_chuan": "TCVN 10304:2025, TCVN 7570:2006",
        "pp_tc":      "Ép tĩnh (ép neo hoặc ép robot)",
        "uu_diem":    "Chi phí thấp; kiểm soát chất lượng tốt qua lực ép; thi công nhanh",
        "nhuoc_diem": "Không tựa mũi vào cát/đá; chiều dài tối đa ~40m; không qua đá mồ côi",
    },
    "Cọc ly tâm PHC": {
        "mo_ta":      "Cọc tròn ly tâm BTCT DƯL, thi công bằng ép/đóng",
        "tieu_chuan": "TCVN 7888:2014, TCVN 10304:2025",
        "pp_tc":      "Ép tĩnh hoặc đóng búa",
        "uu_diem":    "Chịu tải cao hơn cọc vuông cùng cỡ; chất lượng nhà máy ổn định",
        "nhuoc_diem": "Giòn khi va đập; không qua đá mồ côi; cần thiết bị nối cọc",
    },
    "Cọc khoan nhồi": {
        "mo_ta":      "Cọc BTCT đổ tại chỗ, thi công bằng khoan tạo lỗ",
        "tieu_chuan": "TCVN 10304:2025",
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
    "Cọc ly tâm PHC": {
        # D_mm: {duong_kinh_mm, tai_trong_tk_kN, chieu_dai_max_m}
        300: {"duong_kinh_mm": 300, "tai_trong_tk_kN": 400,  "chieu_dai_max_m": 24},
        350: {"duong_kinh_mm": 350, "tai_trong_tk_kN": 550,  "chieu_dai_max_m": 28},
        400: {"duong_kinh_mm": 400, "tai_trong_tk_kN": 700,  "chieu_dai_max_m": 32},
        500: {"duong_kinh_mm": 500, "tai_trong_tk_kN": 1100, "chieu_dai_max_m": 36},
        600: {"duong_kinh_mm": 600, "tai_trong_tk_kN": 1800, "chieu_dai_max_m": 40},
    },
    "Cọc khoan nhồi": {
        # D_mm: {duong_kinh_mm, tai_trong_tk_kN, chieu_dai_max_m}
        600:  {"duong_kinh_mm": 600,  "tai_trong_tk_kN": 800,  "chieu_dai_max_m": 60},
        800:  {"duong_kinh_mm": 800,  "tai_trong_tk_kN": 1500, "chieu_dai_max_m": 70},
        1000: {"duong_kinh_mm": 1000, "tai_trong_tk_kN": 2500, "chieu_dai_max_m": 80},
        1200: {"duong_kinh_mm": 1200, "tai_trong_tk_kN": 4000, "chieu_dai_max_m": 90},
        1500: {"duong_kinh_mm": 1500, "tai_trong_tk_kN": 6000, "chieu_dai_max_m": 100},
        2000: {"duong_kinh_mm": 2000, "tai_trong_tk_kN": 6000, "chieu_dai_max_m": 100},
    },
}

# Nhóm loại đất
_DAT_DINH = {"Sét", "Sét pha"}
_DAT_ROI  = {"Cát", "Cát pha", "Cát lẫn sỏi", "Sỏi cuội"}
_DA       = {"Đá tươi", "Đá phong hóa"}


# ═══════════════════════════════════════════════════════════════════════════════
# A — LỰA CHỌN LOẠI CỌC THEO ĐƯỜNG KÍNH
# ═══════════════════════════════════════════════════════════════════════════════
def _select_pile_category(dac_trung_dia_chat, tai_trong, D_tru=None,
                          is_urban=False):
    """
    Phân loại cọc theo ĐƯỜNG KÍNH và điều kiện áp dụng (PILE_CATEGORY).

    Parameters
    ----------
    dac_trung_dia_chat : dict  — đặc trưng địa chất (00-DiaChat_Loader)
    tai_trong          : float — tải trọng tính toán lên một bệ cọc (kN)
    D_tru              : float — đường kính/bề rộng trụ (m); ràng buộc D_cọc ≥ D_trụ
    is_urban           : bool  — đô thị (hạn chế rung động)

    Returns
    -------
    (category: 'small'|'large', reasons: list[str], warnings: list[str])
    """
    dac_trung = dac_trung_dia_chat or {}
    reasons, warnings = [], []

    lop_tua   = dac_trung.get("lop_tua_mui_de_xuat") or {}
    loai_dat  = lop_tua.get("loai_dat", "")
    IL        = lop_tua.get("IL")
    do_sau    = float(lop_tua.get("do_sau_dinh") or 30.0)
    co_da_moi = dac_trung.get("co_da_moi_co_giua", False)
    co_da_ph  = dac_trung.get("co_da_phong_hoa", False)

    # ── Các điều kiện BẮT BUỘC nhóm LỚN (khoan nhồi) ────────────────────
    if co_da_moi or co_da_ph:
        reasons.append(
            "Có đá phong hóa / đá mồ côi trong phạm vi cắm cọc — cọc nhỏ "
            "(đóng/ép/ly tâm) không hạ qua được, cần KHOAN XUYÊN → nhóm LỚN")
        return "large", reasons, warnings

    if is_urban:
        reasons.append(
            "Cầu đô thị — hạn chế rung động/tiếng ồn khi hạ cọc → nhóm LỚN "
            "(khoan nhồi)")
        return "large", reasons, warnings

    if D_tru and float(D_tru) > 0.6:
        reasons.append(
            f"Ràng buộc D_cọc ≥ D_trụ = {float(D_tru)*1000:.0f}mm > 600mm — "
            "vượt phạm vi cọc nhỏ → nhóm LỚN")
        return "large", reasons, warnings

    # Tải đầu cọc yêu cầu (giả định tối thiểu 4 cọc/bệ) vượt Q_tk max nhóm nhỏ
    q_max_small = PILE_CATEGORY["small"]["Q_tk_kN"][1]
    if float(tai_trong or 0) / 4.0 > q_max_small:
        reasons.append(
            f"Tải đầu cọc ≈ {float(tai_trong)/4.0:.0f}kN/cọc (4 cọc/bệ) > "
            f"{q_max_small}kN (Q_tk max nhóm nhỏ) → nhóm LỚN")
        return "large", reasons, warnings

    if loai_dat in _DAT_ROI:
        reasons.append(
            f"Lớp tựa mũi là đất rời ({loai_dat}) — cọc ép dễ từ chối giả, "
            "không đạt chiều sâu thiết kế (TCVN 10304:2025) → nhóm LỚN")
        return "large", reasons, warnings

    if loai_dat in _DAT_DINH and IL is not None and IL > 0.6:
        reasons.append(
            f"Sét tựa mũi IL={IL:.2f} > 0.6 (dẻo mềm–dẻo chảy) — không phù "
            "hợp cọc nhỏ tựa mũi → nhóm LỚN")
        return "large", reasons, warnings

    if do_sau > 35:
        reasons.append(
            f"Chiều sâu lớp tựa mũi {do_sau:.1f}m > 35m — vượt khả năng thi "
            "công cọc đóng/ép → nhóm LỚN")
        return "large", reasons, warnings

    # ── Còn lại → nhóm NHỎ ──────────────────────────────────────────────
    reasons.append(
        f"Tải bệ {float(tai_trong or 0):.0f}kN vừa phải, lớp tựa mũi sâu "
        f"{do_sau:.1f}m ≤ 35m, không đá tảng/đá mồ côi, không ràng buộc "
        "đô thị/D_trụ → nhóm NHỎ (đóng/ép vuông 200–450mm hoặc ly tâm "
        "D300–D600)")
    return "small", reasons, warnings


def _select_pile_size(pile_type, tai_trong, duong_kinh_tru=None):
    """
    Chọn kích thước cọc NHỎ NHẤT có Q_tk ≥ tải trọng thiết kế đại diện,
    thỏa ràng buộc đường kính (nhóm lớn: D_cọc ≥ D_trụ).

    tai_trong ở đây là tải trọng tính toán ĐẠI DIỆN dùng để định cỡ cọc
    (Q_tk của cỡ chọn phải phủ được); số lượng cọc chính thức tính riêng
    ở bước C với hệ số nhóm η_g.

    Returns
    -------
    (size_key: int, spec: dict)
    """
    sizes = PILE_SIZES[pile_type]
    # Nhóm lớn: chỉ xét D ≥ 800 (D600 giữ trong bảng để tương thích cũ)
    keys = sorted(k for k in sizes
                  if pile_type != "Cọc khoan nhồi" or k >= 800)

    for size_key in keys:
        spec = sizes[size_key]
        if spec["tai_trong_tk_kN"] < float(tai_trong or 0):
            continue
        # Ràng buộc nhóm lớn: D_coc >= D_tru
        if pile_type == "Cọc khoan nhồi" and duong_kinh_tru:
            if size_key / 1000 < duong_kinh_tru:
                continue
        return size_key, spec

    # Fallback: kích thước lớn nhất có thể (ưu tiên thỏa D_tru)
    all_keys = sorted(keys, reverse=True)
    if pile_type == "Cọc khoan nhồi" and duong_kinh_tru:
        filtered = [k for k in all_keys if k / 1000 >= duong_kinh_tru]
        key = filtered[0] if filtered else all_keys[0]
    else:
        key = all_keys[0]
    return key, sizes[key]


# ═══════════════════════════════════════════════════════════════════════════════
# B — TẦNG TỰA MŨI + CHIỀU DÀI CỌC (TCVN 10304:2025)
# ═══════════════════════════════════════════════════════════════════════════════
def _check_bearing_layer(dac_trung_dia_chat):
    """
    Kiểm tra LỚP TỰA MŨI theo 3 tiêu chuẩn định lượng TCVN 10304:2025:
      • Đất DÍNH: SPT-N ≥ 30      • Đất RỜI: SPT-N ≥ 40      • ĐÁ: RQD > 60%

    Returns
    -------
    dict: {dat, loai_nhom ('dinh'|'roi'|'da'), spt_n, RQD, force_ckn,
           warnings, mo_ta}
    """
    dac_trung = dac_trung_dia_chat or {}
    lop_tua   = dac_trung.get("lop_tua_mui_de_xuat") or {}
    co_lop    = dac_trung.get("co_lop_tua_mui_du_kien", False)
    loai_dat  = str(lop_tua.get("loai_dat", "") or "")
    spt_n     = lop_tua.get("spt_n_tb")
    RQD       = lop_tua.get("RQD")
    warnings  = []

    # Phân nhóm đất dính / rời / đá từ dữ liệu địa chất Module 00
    if loai_dat in _DA:
        loai_nhom = "da"
    elif loai_dat in _DAT_ROI:
        loai_nhom = "roi"
    elif loai_dat in _DAT_DINH:
        loai_nhom = "dinh"
    else:
        loai_nhom = "dinh"
        if loai_dat:
            warnings.append(
                f"⚠️ Loại đất lớp tựa mũi '{loai_dat}' chưa phân biệt rõ "
                "dính/rời — mặc định coi là ĐẤT DÍNH, cần xác nhận lại với "
                "hồ sơ địa chất.")

    dat = False
    if co_lop:
        if loai_nhom == "da":
            dat = (RQD or 0) > 60
            mo_ta = f"Đá RQD={RQD if RQD is not None else '—'}% (yêu cầu > 60%)"
        elif loai_nhom == "roi":
            dat = (spt_n or 0) >= 40
            mo_ta = f"Đất rời SPT-N={spt_n if spt_n is not None else '—'} (yêu cầu ≥ 40)"
        else:
            dat = (spt_n or 0) >= 30
            mo_ta = f"Đất dính SPT-N={spt_n if spt_n is not None else '—'} (yêu cầu ≥ 30)"
    else:
        mo_ta = "Chưa có lớp tựa mũi dự kiến trong phạm vi hố khoan"

    force_ckn = False
    if not dat:
        force_ckn = True
        warnings.append(
            "⚠️ Không tìm được lớp tựa mũi phù hợp (đất dính SPT-N ≥ 30 / "
            "đất rời SPT-N ≥ 40 / đá RQD > 60%) trong phạm vi hợp lý — đề "
            "xuất chuyển sang CỌC KHOAN NHỒI có thể xuyên sâu hơn.")

    return {"dat": dat, "loai_nhom": loai_nhom, "spt_n": spt_n, "RQD": RQD,
            "force_ckn": force_ckn, "warnings": warnings, "mo_ta": mo_ta}


def _calc_pile_length(dac_trung_dia_chat, D_m, spec, loai_coc,
                      cao_do_dau_coc=None, bearing=None):
    """
    Chiều dài cọc + chiều sâu cắm vào lớp tốt theo TCVN 10304:2025.

    Chiều sâu cắm L_cam (3 trường hợp):
      • Đất chặt / đất dính cứng      : L_cam ≥ 3.0m
      • Đất yếu / đất rời             : L_cam ≥ 6.0m
      • Đá tươi RQD > 75% (độ chối)   : ngàm L_cam ≥ 0.5m

    Kiểm tra bổ sung:
      • Nền yếu (SPT tb < 15 trong 10m đầu) → L/D ≤ 37, vượt → đề xuất tăng D.
      • Kinh tế: |Q_vật_liệu − Q_đất| > 40% → cảnh báo lãng phí vật liệu.

    Returns
    -------
    dict: {L_coc, cam_vao, cao_do_dau_coc, cao_do_mui_coc, ty_le_LD,
           Q_vl_kN, warnings}
    """
    dac_trung = dac_trung_dia_chat or {}
    lop_tua   = dac_trung.get("lop_tua_mui_de_xuat") or {}
    bearing   = bearing or _check_bearing_layer(dac_trung)
    warnings  = []

    loai_dat  = str(lop_tua.get("loai_dat", "") or "")
    RQD       = lop_tua.get("RQD")
    spt_n     = lop_tua.get("spt_n_tb")
    do_sau    = float(lop_tua.get("do_sau_dinh") or 25.0)
    cao_dinh  = lop_tua.get("cao_do_dinh")

    # ── Chiều sâu cắm vào lớp tốt (TCVN 10304:2025) ─────────────────────
    if loai_dat == "Đá tươi" and (RQD or 0) > 75:
        cam_vao = 0.5          # đá tươi / đạt độ chối → ngàm ≥ 0.5m
        cs_cam  = "Đá tươi RQD > 75% → ngàm ≥ 0.5m"
    elif loai_dat in _DA:
        cam_vao = max(1.5, 2.0 * D_m)
        cs_cam  = "Đá phong hóa → cắm ≥ max(1.5m, 2D)"
    elif ((bearing["loai_nhom"] == "dinh" and (spt_n or 0) >= 30)
          or (bearing["loai_nhom"] == "roi" and (spt_n or 0) >= 40)):
        cam_vao = 3.0          # đất chặt / đất dính cứng
        cs_cam  = "Đất chặt / dính cứng → cắm ≥ 3.0m"
    else:
        cam_vao = 6.0          # đất yếu / đất rời
        cs_cam  = "Đất yếu / đất rời → cắm ≥ 6.0m"

    # ── Cao độ đầu cọc / mũi cọc → chiều dài ────────────────────────────
    Z_surface = dac_trung.get("Z") or 0.0
    cao_do_dc = (float(cao_do_dau_coc) if cao_do_dau_coc is not None
                 else float(Z_surface) - 0.5)
    if cao_dinh is not None:
        cao_do_mc = float(cao_dinh) - cam_vao
        L_coc = max(round(cao_do_dc - cao_do_mc, 1), 8.0)
    else:
        L_coc = max(round(do_sau + cam_vao + abs(cao_do_dc - Z_surface), 1), 8.0)
        cao_do_mc = cao_do_dc - L_coc

    L_max = spec.get("chieu_dai_max_m", 999)
    if L_coc > L_max:
        warnings.append(
            f"⚠️ Chiều dài cọc tính được ({L_coc}m) vượt giới hạn kỹ thuật "
            f"(L_max={L_max}m). Cân nhắc tăng kích thước cọc hoặc thay đổi "
            "độ sâu tựa mũi.")

    # ── Ổn định: L/D ≤ 37 khi nền yếu (SPT tb < 15 trong 10m đầu) ───────
    ty_le_LD = round(L_coc / D_m, 1) if D_m > 0 else 0.0
    spt_10m = dac_trung.get("spt_n_tb_10m") or dac_trung.get("spt_tb_10m")
    if spt_10m is not None and float(spt_10m) < 15 and ty_le_LD > 37:
        warnings.append(
            f"⚠️ Nền yếu (SPT tb 10m đầu = {float(spt_10m):.0f} < 15) và "
            f"L/D = {ty_le_LD} > 37 — nguy cơ mất ổn định thân cọc; đề xuất "
            f"TĂNG đường kính lên cỡ tiếp theo (TCVN 10304:2025).")

    # ── Kinh tế: Q_vật_liệu so Q_đất_nền ────────────────────────────────
    if loai_coc == "Cọc khoan nhồi":
        A = math.pi * (D_m / 2) ** 2
        sigma_vl = 6000.0      # kN/m² — BT đổ tại chỗ
    elif loai_coc == "Cọc ly tâm PHC":
        A = math.pi * (D_m / 2) ** 2 * 0.55   # rỗng lòng
        sigma_vl = 12000.0     # BTCT DƯL ly tâm
    else:
        A = D_m ** 2
        sigma_vl = 9000.0      # BTCT DƯL vuông
    Q_vl = round(A * sigma_vl)
    Q_dat = float(spec.get("tai_trong_tk_kN", 0) or 0)
    if Q_dat > 0 and Q_vl > Q_dat * 1.4:
        warnings.append(
            f"ℹ️ Kinh tế: Q_vật_liệu ≈ {Q_vl:.0f}kN > 140% Q_đất_nền "
            f"({Q_dat:.0f}kN) — vật liệu cọc chưa khai thác hết, cân nhắc "
            "giảm kích thước hoặc tăng chiều sâu để tận dụng (lãng phí "
            "vật liệu).")

    return {"L_coc": L_coc, "cam_vao": cam_vao, "co_so_cam": cs_cam,
            "cao_do_dau_coc": round(cao_do_dc, 2),
            "cao_do_mui_coc": round(cao_do_mc, 2),
            "ty_le_LD": ty_le_LD, "Q_vl_kN": Q_vl, "warnings": warnings}


# ═══════════════════════════════════════════════════════════════════════════════
# C — SỐ LƯỢNG CỌC (HỆ SỐ NHÓM η_g + DỰ PHÒNG THI CÔNG)
# ═══════════════════════════════════════════════════════════════════════════════
def _eta_converse_labarre(m, n, D_m, S_m):
    """Hệ số hiệu quả nhóm Converse-Labarre (đất dính, bệ không tiếp xúc đất):
    η = 1 − θ/90 × [(n−1)·m + (m−1)·n] / (m·n),  θ = arctan(D/S) (độ)."""
    m = max(1, int(m)); n = max(1, int(n))
    if m * n <= 1:
        return 1.0
    theta = math.degrees(math.atan(D_m / max(S_m, 1e-6)))
    eta = 1.0 - theta / 90.0 * ((n - 1) * m + (m - 1) * n) / (m * n)
    return max(0.5, min(1.0, eta))


def _calc_pile_number(P_be, Q_1coc, D_m, S_m, dat_roi=False, dat_yeu=False,
                      be_tiep_xuc_dat=False):
    """
    Số cọc trên bệ theo TCVN 10304:2025 với hệ số hiệu quả nhóm η_g:
        n = max(4, ⌈P_bệ / (Q_1cọc × η_g) × dự_phòng⌉)

    η_g:
      • Đất DÍNH, bệ không tiếp xúc đất / đất bề mặt yếu → Converse-Labarre
        (tim-tim = 2.5D → η ≈ 0.7–0.8 tùy số cọc).
      • Đất RỜI → η ≈ 0.9–1.0 (tổng sức kháng các cọc đơn).
    Dự phòng sai số thi công 1.05–1.10 (cọc đóng lệch 75–150mm).

    Returns
    -------
    dict: {so_coc, eta_g, n_cols, n_rows, du_phong, chi_tiet}
    """
    P = max(float(P_be or 0), 1.0)
    Q = max(float(Q_1coc or 1), 1.0)
    du_phong = 1.10 if dat_yeu else 1.05

    # Lặp: n → lưới m×k → η_g → n mới (hội tụ nhanh, ≤ 6 vòng)
    n = max(4, math.ceil(P / Q))
    eta = 1.0
    for _ in range(6):
        n_cols = math.ceil(math.sqrt(n))
        n_rows = math.ceil(n / n_cols)
        if dat_roi and not be_tiep_xuc_dat:
            eta = 0.95           # đất rời: η ≈ 0.9–1.0
        elif dat_roi:
            eta = 1.0
        else:
            eta = round(_eta_converse_labarre(n_rows, n_cols, D_m, S_m), 3)
        n_new = max(4, math.ceil(P / (Q * eta) * du_phong))
        if n_new == n:
            break
        n = n_new

    n_cols = math.ceil(math.sqrt(n))
    n_rows = math.ceil(n / n_cols)
    chi_tiet = (
        f"n = max(4, ⌈{P:.0f} / ({Q:.0f} × η_g={eta:.2f}) × "
        f"{du_phong:.2f}⌉) = {n} cọc (lưới {n_rows}×{n_cols}). "
        f"Đã dự phòng sai số thi công 75-150 mm (hệ số {du_phong:.2f}).")
    return {"so_coc": n, "eta_g": eta, "n_cols": n_cols, "n_rows": n_rows,
            "du_phong": du_phong, "chi_tiet": chi_tiet}


# ═══════════════════════════════════════════════════════════════════════════════
# D — KHOẢNG CÁCH BỐ TRÍ CỌC (TCVN 10304:2025)
# ═══════════════════════════════════════════════════════════════════════════════
def _calc_pile_layout(loai_coc, D_m, so_coc, coc_ma_sat=False,
                      co_ong_vach=False):
    """
    Khoảng cách bố trí cọc theo TCVN 10304:2025 — phân biệt 2 loại:

    Cọc ĐÓNG / ÉP (kể cả ly tâm):
      • Tim-tim ≥ max(750mm, 2.5D)
      • Cọc MA SÁT: tại mặt phẳng mũi cọc tim-tim ≥ 3D
      • Mặt ngoài cọc → mép bệ ≥ 225mm
    Cọc KHOAN NHỒI:
      • Tim-tim thiết kế > 3.0D
      • Tim-tim < 4D + thi công KHÔNG ống vách → cảnh báo tương tác
      • Tim-tim < 6D → cảnh báo trình tự thi công
      • Thông thủy giữa thân cọc ≥ 1.0m
      • Mặt bên cọc → mép bệ ≥ 300mm

    Returns
    -------
    dict: {khoang_cach_tim, khoang_cach_mep, khoang_cach_thong_thuy,
           kt_mep_tim, n_cols, n_rows, Be_ngang, Be_doc, Be_cao, warnings,
           quy_tac}
    """
    warnings, quy_tac = [], []
    la_ckn = (loai_coc == "Cọc khoan nhồi")

    if la_ckn:
        # Tim-tim > 3.0D và bảo đảm thông thủy ≥ 1.0m
        S = max(3.0 * D_m, D_m + 1.0)
        quy_tac.append(f"Tim-tim > 3.0D = {3.0*D_m:.2f}m; thông thủy ≥ 1.0m "
                       f"→ chọn S = {S:.2f}m")
        if S < 4.0 * D_m and not co_ong_vach:
            warnings.append(
                f"⚠️ Tim-tim {S:.2f}m < 4D = {4*D_m:.2f}m, thi công không "
                "ống vách — Cần đánh giá ảnh hưởng tương tác giữa các cọc.")
        if S < 6.0 * D_m:
            warnings.append(
                f"⚠️ Tim-tim {S:.2f}m < 6D = {6*D_m:.2f}m — Trình tự thi "
                "công khoan cọc phải được quy định rõ trong hồ sơ thiết kế.")
        thong_thuy = round(S - D_m, 2)
        mep_min = 0.300         # mặt bên cọc → mép bệ ≥ 300mm
        quy_tac.append("Mặt bên cọc → mép bệ ≥ 300mm")
    else:
        S = max(0.750, 2.5 * D_m)
        quy_tac.append(f"Tim-tim ≥ max(750mm, 2.5D={2.5*D_m:.2f}m) "
                       f"→ chọn S = {S:.2f}m")
        if coc_ma_sat:
            S = max(S, 3.0 * D_m)
            quy_tac.append(f"Cọc MA SÁT: tại mặt phẳng mũi tim-tim ≥ 3D "
                           f"→ S = {S:.2f}m")
        thong_thuy = round(S - D_m, 2)
        mep_min = 0.225         # mặt ngoài cọc → mép bệ ≥ 225mm
        quy_tac.append("Mặt ngoài cọc → mép bệ ≥ 225mm")

    S = round(S, 2)
    kt_mep_tim = round(D_m / 2.0 + mep_min, 2)   # TIM cọc ngoài → mép bệ

    n_cols = math.ceil(math.sqrt(so_coc))
    n_rows = math.ceil(so_coc / n_cols)
    Be_ngang = round((n_cols - 1) * S + 2 * kt_mep_tim, 2)
    Be_doc   = round((n_rows - 1) * S + 2 * kt_mep_tim, 2)
    Be_cao   = round(max(1.0, 1.5 * D_m), 2)

    return {"khoang_cach_tim": S,
            "khoang_cach_mep": mep_min,
            "khoang_cach_thong_thuy": (thong_thuy if la_ckn else None),
            "kt_mep_tim": kt_mep_tim,
            "n_cols": n_cols, "n_rows": n_rows,
            "Be_ngang": Be_ngang, "Be_doc": Be_doc, "Be_cao": Be_cao,
            "warnings": warnings, "quy_tac": quy_tac}


# ═══════════════════════════════════════════════════════════════════════════════
# HÀM CHÍNH
# ═══════════════════════════════════════════════════════════════════════════════
def predict_foundation_geo(dac_trung_dia_chat, tai_trong_dau_coc,
                           loai_tru=None, duong_kinh_tru=None,
                           is_urban=False, is_river=False,
                           cao_do_dau_coc=None):
    """
    Tư vấn móng cọc theo Rule-Based — TCVN 11823:2017 + TCVN 10304:2025.
    Cấu trúc 4 nhóm logic A (loại cọc) → B (chiều dài) → C (số cọc) →
    D (bố trí) — xem docstring module.

    Parameters
    ----------
    dac_trung_dia_chat : dict — từ 00-DiaChat_Loader.dac_trung_tong_hop[hk_name]
    tai_trong_dau_coc  : float — tổng tải trọng tính toán lên một bệ cọc (kN)
    loai_tru           : str   — loại trụ từ Module 07 (thông tin tham khảo)
    duong_kinh_tru     : float — đường kính / bề rộng trụ (m) — ràng buộc D_cọc ≥ D_trụ
    is_urban           : bool  — khu vực đô thị (hạn chế tiếng ồn/rung)
    is_river           : bool  — công trình vượt sông
    cao_do_dau_coc     : float — cao độ đầu cọc (m); mặc định = Z mặt đất − 0.5m

    Returns
    -------
    dict đầy đủ thông số 4 phần A/B/C/D (kèm key cũ để tương thích ngược).
    """
    dac_trung = dac_trung_dia_chat or {}
    P_be      = float(tai_trong_dau_coc) if tai_trong_dau_coc else 800.0
    D_tru     = float(duong_kinh_tru) if duong_kinh_tru else None

    lop_tua      = dac_trung.get("lop_tua_mui_de_xuat") or {}
    loai_dat_tua = lop_tua.get("loai_dat", "")
    warnings, reasons = [], []

    # ── A. Lựa chọn loại cọc theo đường kính ────────────────────────────
    category, rs_a, ws_a = _select_pile_category(
        dac_trung, P_be, D_tru=D_tru, is_urban=bool(is_urban))
    reasons.extend(f"[A] {r}" for r in rs_a)
    warnings.extend(ws_a)

    # ── B1. Kiểm tra lớp tựa mũi (có thể ép chuyển nhóm lớn) ────────────
    bearing = _check_bearing_layer(dac_trung)
    warnings.extend(bearing["warnings"])
    if bearing["force_ckn"] and category == "small":
        category = "large"
        reasons.append("[B] Lớp tựa mũi không đạt tiêu chuẩn → chuyển CỌC "
                       "KHOAN NHỒI xuyên sâu hơn (nhóm LỚN)")

    loai_coc = "Cọc khoan nhồi" if category == "large" else "Cọc ép BTCT"

    # Kích thước cọc (nhóm lớn ràng buộc D ≥ D_trụ)
    size_key, spec = _select_pile_size(loai_coc, P_be, D_tru)
    D_m = size_key / 1000.0
    if loai_coc == "Cọc ép BTCT":
        kich_thuoc_str = f"{size_key}×{size_key} mm"
        # Cỡ ly tâm tương đương (cùng nhóm nhỏ — phương án thay thế)
        _lt = next((k for k in sorted(PILE_SIZES["Cọc ly tâm PHC"])
                    if PILE_SIZES["Cọc ly tâm PHC"][k]["tai_trong_tk_kN"]
                    >= spec["tai_trong_tk_kN"]), None)
        ly_tam_td = f"D{_lt} ly tâm PHC" if _lt else None
    else:
        kich_thuoc_str = f"Ø{size_key} mm"
        ly_tam_td = None
        if D_tru:
            reasons.append(
                f"[A] Ràng buộc D_cọc = {size_key}mm ≥ D_trụ = "
                f"{D_tru*1000:.0f}mm {'✓' if D_m >= D_tru else '✗'}")

    # ── B2. Chiều dài cọc + chiều sâu cắm ───────────────────────────────
    lb = _calc_pile_length(dac_trung, D_m, spec, loai_coc,
                           cao_do_dau_coc=cao_do_dau_coc, bearing=bearing)
    warnings.extend(lb["warnings"])
    reasons.append(f"[B] Lớp tựa mũi: {bearing['mo_ta']}; {lb['co_so_cam']} "
                   f"→ L = {lb['L_coc']}m")

    # ── D1. Khoảng cách tim-tim (cần trước để tính η_g) ─────────────────
    layout0 = _calc_pile_layout(loai_coc, D_m, 4,
                                coc_ma_sat=not bearing["dat"])
    S_m = layout0["khoang_cach_tim"]

    # ── C. Số lượng cọc với hệ số nhóm η_g + dự phòng thi công ──────────
    dat_roi = bearing["loai_nhom"] == "roi"
    spt_10m = dac_trung.get("spt_n_tb_10m") or dac_trung.get("spt_tb_10m")
    dat_yeu = spt_10m is not None and float(spt_10m) < 15
    Q_1coc = spec["tai_trong_tk_kN"]
    num = _calc_pile_number(P_be, Q_1coc, D_m, S_m,
                            dat_roi=dat_roi, dat_yeu=dat_yeu)
    so_coc = num["so_coc"]
    reasons.append(f"[C] {num['chi_tiet']}")

    # ── D2. Bố trí cọc chính thức theo số cọc đã chốt ───────────────────
    layout = _calc_pile_layout(loai_coc, D_m, so_coc,
                               coc_ma_sat=not bearing["dat"])
    warnings.extend(layout["warnings"])
    reasons.append(f"[D] {'; '.join(layout['quy_tac'])}")

    if is_river:
        warnings.append(
            "ℹ️ Công trình vượt sông — kiểm tra xói lở đáy sông theo TCVN "
            "9845:2013; bảo vệ bệ cọc bằng thảm đá hoặc kè đá hộc.")

    tru_info = f"Trụ: {loai_tru}. " if loai_tru else ""
    ghi_chu = (
        f"{tru_info}Nhóm {PILE_CATEGORY[category]['ten']} → {loai_coc} "
        f"({kich_thuoc_str}), L={lb['L_coc']}m, n={so_coc} cọc/bệ "
        f"(η_g={num['eta_g']:.2f}). "
        f"Cơ sở: {'; '.join(reasons[:2]) if reasons else 'Rule-Based'}.")

    return {
        # ── A. Loại cọc ──────────────────────────────────────────────────
        "category":               category,          # 'small' | 'large'
        "ten_nhom_coc":           PILE_CATEGORY[category]["ten"],
        "loai_coc":               loai_coc,          # tương thích ngược
        "kich_thuoc_coc":         kich_thuoc_str,
        "kich_thuoc_mm":          size_key,
        "ly_tam_tuong_duong":     ly_tam_td,
        "Q_1coc_tk_kN":           Q_1coc,
        # ── B. Chiều dài + tầng tựa mũi ─────────────────────────────────
        "chieu_dai_coc":          lb["L_coc"],
        "chieu_dai_cam_lop_tot":  lb["cam_vao"],
        "co_so_cam":              lb["co_so_cam"],
        "cao_do_dau_coc":         lb["cao_do_dau_coc"],
        "cao_do_mui_coc":         lb["cao_do_mui_coc"],
        "ty_le_LD":               lb["ty_le_LD"],
        "Q_vl_kN":                lb["Q_vl_kN"],
        "lop_tua_mui":            lop_tua.get("ten_lop", "Chưa xác định"),
        "loai_dat_tua_mui":       loai_dat_tua,
        "do_sau_tua_mui":         round(float(lop_tua.get("do_sau_dinh") or 25.0), 1),
        "lop_tua_dat":            bearing["dat"],
        "lop_tua_mo_ta":          bearing["mo_ta"],
        # ── C. Số lượng cọc ─────────────────────────────────────────────
        "so_coc_be":              so_coc,
        "he_so_nhom":             num["eta_g"],
        "he_so_du_phong":         num["du_phong"],
        "cong_thuc_so_coc":       num["chi_tiet"],
        # ── D. Bố trí cọc ───────────────────────────────────────────────
        "khoang_cach_tim":        layout["khoang_cach_tim"],
        "khoang_cach_mep":        layout["khoang_cach_mep"],
        "khoang_cach_thong_thuy": layout["khoang_cach_thong_thuy"],
        "khoang_cach_tim_coc":    layout["khoang_cach_tim"],   # key cũ
        "khoang_cach_mep_be":     layout["kt_mep_tim"],        # key cũ (tim→mép)
        "n_cols_be":              layout["n_cols"],
        "n_rows_be":              layout["n_rows"],
        "kich_thuoc_be":          (f"{layout['Be_ngang']:.2f}m × "
                                   f"{layout['Be_doc']:.2f}m × "
                                   f"{layout['Be_cao']:.2f}m"),
        "Be_ngang":               layout["Be_ngang"],
        "Be_doc":                 layout["Be_doc"],
        "Be_cao":                 layout["Be_cao"],
        # ── Tổng hợp ────────────────────────────────────────────────────
        "tai_trong_be_kN":        P_be,
        "warnings":               warnings,
        "ly_do_chon":             reasons,
        "ghi_chu":                ghi_chu,
        "phuong_phap":            ("Rule-Based theo TCVN 11823:2017 và "
                                   "TCVN 10304:2025 (4 nhóm logic A–D)"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TIỆN ÍCH
# ═══════════════════════════════════════════════════════════════════════════════
def format_mong_report(res):
    """Định dạng kết quả thành chuỗi báo cáo ngắn."""
    lines = [
        f"  Nhóm cọc        : {res.get('ten_nhom_coc', res.get('category', '—'))}",
        f"  Loại cọc        : {res['loai_coc']}",
        f"  Kích thước      : {res['kich_thuoc_coc']}",
        f"  Chiều dài cọc   : {res['chieu_dai_coc']} m "
        f"(cắm {res.get('chieu_dai_cam_lop_tot', '—')}m vào lớp tốt)",
        f"  Số cọc / bệ     : {res['so_coc_be']} cọc "
        f"(η_g = {res.get('he_so_nhom', '—')})",
        f"  Kích thước bệ   : {res['kich_thuoc_be']}",
        f"  Khoảng cách tim : {res.get('khoang_cach_tim', res.get('khoang_cach_tim_coc'))} m",
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
# API TƯƠNG THÍCH — cho 00-Interface.py và 09-So_Sanh_PA.py
# ═══════════════════════════════════════════════════════════════════════════════

# Bảng tra đường kính cọc theo cấp sông
_CAP_SONG_D_MM = {
    "I": 1200, "II": 1000, "III": 1000, "IV": 800, "V": 800, "VI": 600,
    1: 1200, 2: 1000, 3: 1000, 4: 800, 5: 800, 6: 600,
}
# Bảng tra tải trọng trục / m lane theo vtk
_VTK_KN_M = {
    "HL93": 14.0, "HS20": 12.0, "HS25": 14.5, "H30": 14.0,
    "XB80": 8.0, "13.5T": 6.0, "30T": 14.0,
    80: 14.0, 30: 14.0, 13.5: 6.0,
}
# Sức chịu tải thiết kế 1 cọc theo D(mm)
_Q_TK_KN = {200: 250, 250: 400, 300: 600, 350: 900, 400: 1200, 450: 1500,
             600: 800, 800: 1500, 1000: 2500, 1200: 4000, 1500: 6000,
             2000: 6000}


def train_foundation_ai(v3_path=None):
    """Stub — module dùng rule-based, không cần file train."""
    return None


def predict_foundation(H_tru=None, loai_tru=None, is_river=False, cap_song="VI",
                       B_cau=12.0, vtk=None, L_nhip=40.0, is_urban=False,
                       foundation_models=None,
                       dac_trung_dia_chat=None, tai_trong_dau_coc=None,
                       duong_kinh_tru=None, cao_do_dau_coc=None):
    """
    Tư vấn móng cọc — Rule-Based (TCVN 11823:2017 / TCVN 10304:2025).

    Hỗ trợ 2 chế độ gọi:
    • Bridge-params (từ Interface + So_Sanh_PA):
        predict_foundation(H_tru=…, B_cau=…, cap_song=…, vtk=…, L_nhip=…, …)
    • Geo-data (từ Module 08 trực tiếp):
        predict_foundation(dac_trung_dia_chat=…, tai_trong_dau_coc=…, …)
    """
    # ── Chế độ geo-data: ủy thác cho hàm chi tiết ────────────────────────────
    if dac_trung_dia_chat is not None:
        return predict_foundation_geo(
            dac_trung_dia_chat, tai_trong_dau_coc or 800.0,
            loai_tru=loai_tru, duong_kinh_tru=duong_kinh_tru,
            is_urban=bool(is_urban), is_river=bool(is_river),
            cao_do_dau_coc=cao_do_dau_coc,
        )

    # ── Chế độ bridge-params: ước tính từ thông số cầu ───────────────────────
    H   = float(H_tru  or 5.0)
    L   = float(L_nhip or 40.0)
    B   = float(B_cau  or 12.0)
    cap = str(cap_song).upper() if not isinstance(cap_song, (int, float)) else cap_song

    # Đường kính cọc
    D_mm = _CAP_SONG_D_MM.get(cap, 800)
    if H > 12:  D_mm = max(D_mm, 1000)
    if L > 60:  D_mm = max(D_mm, 1200)

    # Loại cọc
    _river = bool(is_river)
    _urban = bool(is_urban)
    if _river and cap in ("I", "II", 1, 2):
        loai_coc = "Cọc khoan nhồi BTCT"
        D_txt    = f"D{D_mm}mm"
        pp_tc    = "Khoan nhồi"
    elif _urban:
        loai_coc = "Cọc ép BTCT DƯL"
        D_txt    = f"Ø{D_mm}mm"
        pp_tc    = "Ép thuỷ lực"
    else:
        loai_coc = "Cọc đóng BTCT DƯL"
        D_txt    = f"Ø{D_mm}mm"
        pp_tc    = "Đóng búa diesel"

    # Phân nhóm theo đường kính (A) — đồng bộ với PILE_CATEGORY
    category = "large" if D_mm >= 800 else "small"

    # Chiều dài cọc (ước tính từ H_tru + cấp sông)
    _depth_extra = {
        "I": 20, "II": 16, "III": 12, "IV": 10, "V": 8, "VI": 6,
        1: 20, 2: 16, 3: 12, 4: 10, 5: 8, 6: 6,
    }.get(cap, 8)
    L_est = max(20.0, H * 3.2 + _depth_extra)
    L_tu  = int(L_est * 0.85)
    L_den = int(L_est * 1.20)

    # Bố trí (D) trước để có S cho hệ số nhóm (C)
    D_m = D_mm / 1000.0
    _loai_norm = ("Cọc khoan nhồi" if "khoan nhồi" in loai_coc.lower()
                  else "Cọc ép BTCT")
    layout0 = _calc_pile_layout(_loai_norm, D_m, 4)
    kt_tim = layout0["khoang_cach_tim"]

    # Tải trọng bệ → số cọc (C: η_g + dự phòng thi công)
    _q   = _VTK_KN_M.get(vtk, 12.0)
    P_be = max(500.0, L * B * _q * 0.35)
    Q_tk = _Q_TK_KN.get(D_mm, 800)
    num = _calc_pile_number(P_be, Q_tk, D_m, kt_tim, dat_roi=False)
    So_coc  = num["so_coc"]
    So_tu   = max(4, (round(So_coc * 0.80 / 2) * 2))
    So_den  = max(So_tu + 2, (round(So_coc * 1.25 / 2) * 2))

    layout = _calc_pile_layout(_loai_norm, D_m, So_coc)
    n_cols = layout["n_cols"]
    Be_W   = layout["Be_ngang"]
    Be_H   = layout["Be_cao"]
    be_txt = f"{Be_W}m × {layout['Be_doc']}m × {Be_H}m"

    return {
        # ── Keys tương thích cũ (00-Interface, 09-So_Sanh_PA) ────────────────
        "loai_mong":            loai_coc,
        "D_coc_chon_txt":       D_txt,
        "D_coc_mm":             D_mm,
        "L_coc_tu":             L_tu,
        "L_coc_den":            L_den,
        "So_coc_tu":            So_tu,
        "So_coc_den":           So_den,
        "kich_thuoc_be_goi_y":  be_txt,
        "phuong_phap_thi_cong": pp_tc,
        # ── Keys mới (11-BanVe_KetCau + UI 4 phần A–D) ────────────────────────
        "category":             category,
        "ten_nhom_coc":         PILE_CATEGORY[category]["ten"],
        "chieu_dai_coc":        L_tu,
        "so_coc_be":            So_coc,
        "he_so_nhom":           num["eta_g"],
        "he_so_du_phong":       num["du_phong"],
        "cong_thuc_so_coc":     num["chi_tiet"],
        "kich_thuoc_mm":        D_mm,
        "Be_ngang":             Be_W,
        "Be_doc":               layout["Be_doc"],
        "Be_cao":               Be_H,
        "kich_thuoc_be":        be_txt,
        "khoang_cach_tim":      layout["khoang_cach_tim"],
        "khoang_cach_mep":      layout["khoang_cach_mep"],
        "khoang_cach_thong_thuy": layout["khoang_cach_thong_thuy"],
        "khoang_cach_tim_coc":  layout["khoang_cach_tim"],
        "khoang_cach_mep_be":   layout["kt_mep_tim"],
        "n_cols_be":            n_cols,
        "n_rows_be":            layout["n_rows"],
        "Q_1coc_tk_kN":         Q_tk,
        "tai_trong_be_kN":      round(P_be),
        "phuong_phap":          "Rule-Based — ước tính từ thông số cầu (TCVN 10304:2025)",
        "warnings": [
            "📌 Chưa có dữ liệu địa chất thực tế — thông số cọc là ước tính "
            "theo kinh nghiệm từ cap_song, H_tru, L_nhip. "
            "Khai báo địa chất tại trang 01-Địa Chất để có kết quả chính xác hơn."
        ] + layout["warnings"],
        "ly_do_chon": [
            f"cap_song={cap_song}, H_tru={H:.1f}m, B_cau={B:.1f}m, L_nhip={L:.1f}m",
            num["chi_tiet"],
        ],
        "ghi_chu": (
            f"{loai_coc} {D_txt}, L≈{L_tu}–{L_den}m, "
            f"{So_tu}–{So_den}cọc/bệ (ước tính từ thông số cầu)."
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CHẠY THỬ ĐỘC LẬP
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    # ── Ví dụ 1: Cầu nông thôn nhỏ ──────────────────────────────────────────
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
        dac_trung_dia_chat=dac_trung_1,
        tai_trong_dau_coc=600,
        duong_kinh_tru=0.5,
        is_urban=False,
        is_river=True,
    )
    print(format_mong_report(res1))

    # ── Ví dụ 2: Cầu vượt sông cấp IV đô thị ────────────────────────────────
    dac_trung_2 = {
        "lop_tua_mui_de_xuat": {
            "ten_lop":    "Cát chặt vừa",
            "loai_dat":   "Cát",
            "IL":         None,
            "RQD":        None,
            "cao_do_dinh": -35.0,
            "cao_do_day":  -42.0,
            "chieu_day":    7.0,
            "do_sau_dinh": 35.0,
            "spt_n_tb":    45.0,
        },
        "co_lop_tua_mui_du_kien": True,
        "co_set_chay":    True,
        "co_da_moi_co_giua": False,
        "co_da_phong_hoa": False,
        "co_da_tuoi":     False,
        "Z":               2.0,
    }

    print("\n" + "=" * 60)
    print("VÍ DỤ 2 — Cầu vượt sông cấp IV trong đô thị")
    print("  Tải: 1800 kN  |  Sâu 35m  |  Đô thị")
    print("=" * 60)
    res2 = predict_foundation(
        dac_trung_dia_chat=dac_trung_2,
        tai_trong_dau_coc=1800,
        duong_kinh_tru=1.2,
        is_urban=True,
        is_river=True,
    )
    print(format_mong_report(res2))

    print(f"\nVí dụ 1 → [{res1['category']}] {res1['loai_coc']} "
          f"({res1['kich_thuoc_coc']})  L={res1['chieu_dai_coc']}m  "
          f"n={res1['so_coc_be']}cọc  η={res1['he_so_nhom']}")
    print(f"Ví dụ 2 → [{res2['category']}] {res2['loai_coc']} "
          f"({res2['kich_thuoc_coc']})  L={res2['chieu_dai_coc']}m  "
          f"n={res2['so_coc_be']}cọc  η={res2['he_so_nhom']}")
