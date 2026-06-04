"""
Module 10 — Tư vấn lớp phủ mặt cầu (Bridge Deck Pavement Advisor)
Căn cứ:
  - TCVN 8819:2011   Mặt đường bê tông nhựa nóng — yêu cầu thiết kế
  - 22TCN 211-2006   Áo đường mềm — các yêu cầu và chỉ dẫn thiết kế
  - TCVN 11823-2017  Thiết kế cầu đường bộ (phần mặt cầu)
  - Hướng dẫn kỹ thuật phòng OGFC, SBS-modified asphalt (cầu dài)

Ghi chú: Module này mang tính tư vấn sơ bộ.
         Người dùng cần cập nhật theo tiêu chuẩn hiện hành và điều kiện thực tế.
"""

# ── Cấu trúc lớp phủ tiêu biểu ───────────────────────────────────────────────
# Mỗi phương án gồm list các lớp từ trên xuống:
# {"ten": str, "vat_lieu": str, "day_min": float, "day_tt": float, "don_vi": "mm"}

_PAV_SCHEMES = {
    # Phương án A: BTN thông thường (cầu ô tô Vtk ≤ 80 km/h)
    "BTN_thuong": {
        "mo_ta": "Mặt cầu BTN thông thường (Vtk ≤ 80 km/h)",
        "tieu_chuan": "TCVN 8819:2011 + 22TCN 211-2006",
        "lop": [
            {"ten": "Lớp BTN hạt nhỏ (Surface)",
             "vat_lieu": "BTN hạt nhỏ 9.5 hoặc 12.5",
             "day_min": 30, "day_tt": 40, "don_vi": "mm"},
            {"ten": "Lớp BTN hạt trung (Binder)",
             "vat_lieu": "BTN hạt trung 19",
             "day_min": 40, "day_tt": 50, "don_vi": "mm"},
            {"ten": "Lớp dính bám",
             "vat_lieu": "Nhũ tương bitum CSS-1 hoặc PC-70",
             "day_min": 0, "day_tt": 0, "don_vi": "kg/m²", "lieu_luong": "0.3–0.5 kg/m²"},
            {"ten": "Lớp phòng nước",
             "vat_lieu": "Màng chống thấm bitum cải tiến SBS (dạng tấm)",
             "day_min": 3, "day_tt": 4, "don_vi": "mm"},
        ],
        "tong_day_min": 73, "tong_day_tt": 94,
    },
    # Phương án B: BTN cao cấp (cầu cao tốc / Vtk > 80 km/h)
    "BTN_cao_cap": {
        "mo_ta": "Mặt cầu BTN cao cấp (Vtk > 80 km/h hoặc cầu quan trọng)",
        "tieu_chuan": "TCVN 8819:2011 + AASHTO M320 (nhựa SBS)",
        "lop": [
            {"ten": "Lớp BTN hạt nhỏ cải tiến (Surface)",
             "vat_lieu": "BTN hạt nhỏ 9.5 — nhựa SBS (PG 76-22 hoặc tương đương)",
             "day_min": 35, "day_tt": 40, "don_vi": "mm"},
            {"ten": "Lớp BTN hạt trung cải tiến (Binder)",
             "vat_lieu": "BTN hạt trung 19 — nhựa SBS",
             "day_min": 45, "day_tt": 55, "don_vi": "mm"},
            {"ten": "Lớp dính bám",
             "vat_lieu": "Nhũ tương nhựa cải tiến polymer",
             "day_min": 0, "day_tt": 0, "don_vi": "kg/m²", "lieu_luong": "0.4–0.6 kg/m²"},
            {"ten": "Lớp phòng nước cao cấp",
             "vat_lieu": "Màng SBS dán nóng 2 lớp (dày ≥ 4mm) hoặc hệ Eliminator",
             "day_min": 4, "day_tt": 5, "don_vi": "mm"},
        ],
        "tong_day_min": 84, "tong_day_tt": 100,
    },
    # Phương án C: Mặt cầu BTXM (cầu hạng nặng, tải xe đặc biệt)
    "BTXM": {
        "mo_ta": "Mặt cầu bê tông xi măng (tải trọng đặc biệt hoặc cầu cảng)",
        "tieu_chuan": "TCVN 11823-2017 + AASHTO LRFD",
        "lop": [
            {"ten": "Lớp bê tông xi măng mặt cầu",
             "vat_lieu": "BTXM M40 hoặc cao hơn, cốt sợi thép hoặc sợi tổng hợp",
             "day_min": 120, "day_tt": 150, "don_vi": "mm"},
            {"ten": "Lớp chống thấm",
             "vat_lieu": "Vật liệu chống thấm PU hoặc epoxy gốc nước",
             "day_min": 1, "day_tt": 2, "don_vi": "mm"},
        ],
        "tong_day_min": 121, "tong_day_tt": 152,
    },
}


def tu_van_lop_phu(vtk, loai_duong="Do thi", L_nhip=40, moi_truong="Vượt sông"):
    """
    Tư vấn sơ bộ cấu tạo lớp phủ mặt cầu.

    Params
    ------
    vtk         : Vận tốc thiết kế (km/h)
    loai_duong  : 'Cao toc' | 'O to' | 'Do thi'
    L_nhip      : Chiều dài nhịp (m) — cầu dài → yêu cầu cao hơn
    moi_truong  : 'Vượt sông' | ...

    Returns
    -------
    dict: phuong_an, cac_lop (list), tong_day, ghi_chu, khuyen_nghi
    """
    # Chọn phương án
    if loai_duong == "Cao toc" or vtk > 80:
        scheme_key = "BTN_cao_cap"
    else:
        scheme_key = "BTN_thuong"

    scheme = _PAV_SCHEMES[scheme_key]

    # Bổ sung ghi chú môi trường
    khuyen_nghi = []
    if "sông" in moi_truong.lower():
        khuyen_nghi.append(
            "Cầu qua sông: tăng cường chống thấm — dùng màng SBS dán nóng 2 lớp "
            "hoặc hệ epoxy coating dưới lớp phòng nước."
        )
    if L_nhip >= 40:
        khuyen_nghi.append(
            f"Nhịp dài {L_nhip}m: kiểm tra độ võng và biến dạng bản mặt cầu; "
            "cân nhắc dùng BTN nhựa cải tiến polymer (SBS) để giảm vết nứt mỏi."
        )
    if vtk >= 80:
        khuyen_nghi.append(
            "Vtk cao — thiết kế hệ số nhám IRI ≤ 2.0 m/km; "
            "kiểm tra kháng vệt bánh xe theo TCVN 8819:2011."
        )
    khuyen_nghi.append(
        "Chiều dày thiết kế tối thiểu bản mặt cầu BTCT: 175 mm (TCVN 11823-2017 Điều 9.7.1.1)."
    )

    return {
        "phuong_an":   scheme["mo_ta"],
        "tieu_chuan":  scheme["tieu_chuan"],
        "cac_lop":     scheme["lop"],
        "tong_day_min": scheme["tong_day_min"],
        "tong_day_tt":  scheme["tong_day_tt"],
        "khuyen_nghi": khuyen_nghi,
        "ghi_chu": (
            "Kết quả mang tính tư vấn sơ bộ. "
            "Cập nhật theo tiêu chuẩn TCVN hiện hành và kết quả thí nghiệm vật liệu thực tế."
        ),
    }


def format_lop_phu_report(res):
    """Trả về chuỗi text tóm tắt cấu tạo lớp phủ."""
    lines = [f"  Phương án: {res['phuong_an']}",
             f"  Tiêu chuẩn: {res['tieu_chuan']}",
             f"  Tổng chiều dày: {res['tong_day_min']}–{res['tong_day_tt']} mm",
             "  Cấu tạo lớp (trên → dưới):"]
    for i, lop in enumerate(res["cac_lop"], 1):
        if "lieu_luong" in lop:
            lines.append(f"    {i}. {lop['ten']}: {lop['lieu_luong']} ({lop['vat_lieu']})")
        elif lop["day_tt"] > 0:
            lines.append(
                f"    {i}. {lop['ten']}: "
                f"{lop['day_min']}–{lop['day_tt']} mm ({lop['vat_lieu']})"
            )
    for kn in res["khuyen_nghi"]:
        lines.append(f"  ⚠ {kn}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    res = tu_van_lop_phu(vtk=80, loai_duong="Do thi", L_nhip=40, moi_truong="Vượt sông")
    print(format_lop_phu_report(res))
