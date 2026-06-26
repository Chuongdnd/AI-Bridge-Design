"""
utils/khoi_luong.py — Thống kê KHỐI LƯỢNG cấu kiện cầu (sơ bộ).

Quy tắc: tính cho 1 cấu kiện chi tiết → tổng hợp toàn cầu → đưa vào dự toán.
Mỗi cấu kiện trả về: số lượng, bê tông (m³), ván khuôn (m²), cốt thép (kg).

Module thuần Python (không phụ thuộc Streamlit). Công thức kích thước bám theo
12-DuToan_SoBo.py để nhất quán; bổ sung VÁN KHUÔN (diện tích bề mặt bê tông).
Hệ số cốt thép (kg/m³) đặt ở RHO_THEP để dễ chỉnh.
"""
import math

_MM2M = 0.001

# Hàm lượng cốt thép sơ bộ (kg bê tông cốt thép trên 1 m³)
RHO_THEP = {
    "dam":     250.0,   # dầm BTCT DƯL (gồm cả thường, chưa tách DUL)
    "ban":     120.0,   # bản mặt cầu
    "than_tru":110.0,
    "xa_mu":   120.0,
    "mo":      110.0,
    "dai_coc": 100.0,   # bệ/đài cọc
    "coc":      85.0,
    "lan_can":  80.0,
}


def _f(x, dflt=0.0):
    try:
        if x in (None, ""):
            return float(dflt)
        return float(x)
    except (TypeError, ValueError):
        return float(dflt)


def _poly_area_mm2(outer):
    """Diện tích đa giác (shoelace) — outer=[[x,z],...] (mm). Trả mm²."""
    pts = [p for p in (outer or []) if len(p) >= 2]
    if len(pts) < 3:
        return 0.0
    s = 0.0
    for i in range(len(pts)):
        x1, z1 = pts[i][0], pts[i][1]
        x2, z2 = pts[(i + 1) % len(pts)][0], pts[(i + 1) % len(pts)][1]
        s += x1 * z2 - x2 * z1
    return abs(s) / 2.0


def _poly_perimeter_mm(outer):
    pts = [p for p in (outer or []) if len(p) >= 2]
    if len(pts) < 3:
        return 0.0
    per = 0.0
    for i in range(len(pts)):
        x1, z1 = pts[i][0], pts[i][1]
        x2, z2 = pts[(i + 1) % len(pts)][0], pts[(i + 1) % len(pts)][1]
        per += math.hypot(x2 - x1, z2 - z1)
    return per


# ── KHỐI LƯỢNG THEO MÔ HÌNH TRỤ LẮP GHÉP (xà mũ/thân/bệ thật) ───────────────
def _sec_solids(section):
    """List khối đặc [{outer,holes}] của 1 mặt cắt (hỗ trợ nhiều khối)."""
    section = section or {}
    sl = section.get("solids")
    if sl:
        return [s for s in sl if len(s.get("outer", [])) >= 3]
    o = section.get("outer", [])
    if len(o) < 3:
        return []
    return [{"outer": o, "holes": section.get("holes", [])}]


def _layers_of(part):
    """Tầng [{section,H,D}] của 1 bộ phận (hỗ trợ định dạng {section,H} cũ)."""
    part = part or {}
    if part.get("layers"):
        return [dict(l) for l in part["layers"]]
    if (part.get("section") or {}).get("outer"):
        return [{"section": part["section"],
                 "H": _f(part.get("H"), 1.5), "D": _f(part.get("D"), 1.8)}]
    return []


def _scaled_ngang(section, target_w_m):
    """Co/giãn mặt cắt theo phương NGANG (u) để bề rộng = target_w_m (cho xà mũ)."""
    sols = _sec_solids(section)
    if not sols or not target_w_m:
        return section
    us = [p[0] for s in sols for p in s["outer"]]
    w = (max(us) - min(us)) if us else 0.0
    if w < 1e-6:
        return section
    f = (float(target_w_m) * 1000.0) / w
    _sc = lambda pts: [[p[0] * f, p[1]] for p in pts]
    return {"solids": [{"outer": _sc(s["outer"]),
                        "holes": [_sc(h) for h in s.get("holes", [])]} for s in sols]}


def _net_area_perim_m(section):
    """(diện tích THỰC m² đã trừ lỗ, chu vi m) của 1 mặt cắt (mọi khối)."""
    A = P = 0.0
    for s in _sec_solids(section):
        a = _poly_area_mm2(s["outer"]) - sum(_poly_area_mm2(h) for h in (s.get("holes") or []))
        A += a * _MM2M * _MM2M
        P += _poly_perimeter_mm(s["outer"]) * _MM2M
        for h in (s.get("holes") or []):
            P += _poly_perimeter_mm(h) * _MM2M
    return A, P


def _vert_part_takeoff(part, H_total=None, width_m=None):
    """Bệ/thân: mỗi tầng đùn ĐỨNG theo H. → (bt m³, ván khuôn m²)."""
    lays = _layers_of(part)
    if not lays:
        return 0.0, 0.0
    if H_total is not None:                      # co chiều cao các tầng = H_total
        cur = sum(_f(l.get("H")) for l in lays) or 1.0
        fct = float(H_total) / cur
        lays = [{**l, "H": _f(l.get("H")) * fct} for l in lays]
    bt = vk_side = 0.0
    a_first = a_last = 0.0
    for i, l in enumerate(lays):
        sec = _scaled_ngang(l.get("section"), width_m) if width_m else l.get("section")
        A, P = _net_area_perim_m(sec)
        H = _f(l.get("H"))
        bt += A * H
        vk_side += P * H
        if i == 0:
            a_first = A
        a_last = A
    return bt, vk_side + a_first + a_last        # + nắp đáy & đỉnh


def _cap_takeoff(part, width_m=None):
    """Xà mũ: mỗi đoạn đùn DỌC cầu theo D. → (bt m³, ván khuôn m²)."""
    bt = vk = 0.0
    for l in _layers_of(part):
        sec = _scaled_ngang(l.get("section"), width_m) if width_m else l.get("section")
        A, P = _net_area_perim_m(sec)
        D = _f(l.get("D"), 1.8)
        bt += A * D
        vk += P * D + 2 * A                       # mặt bên + 2 đầu
    return bt, vk


def _part_height_m(part):
    """Chiều cao (m) của 1 bộ phận đùn đứng = Σ chiều cao tầng."""
    return sum(_f(l.get("H")) for l in _layers_of(part)) or 1.5


def _cap_height_m(part):
    """Chiều cao xà mũ (m) = đoạn cao nhất (v-extent lớn nhất)."""
    hs = []
    for l in _layers_of(part):
        for s in _sec_solids(l.get("section")):
            vs = [p[1] for p in s["outer"]]
            if vs:
                hs.append((max(vs) - min(vs)) * _MM2M)
    return max(hs) if hs else 1.2


def pier_model_takeoff(pier, H_than=None, cap_width=None):
    """Khối lượng trụ từ MÔ HÌNH lắp ghép → {be,than,xa_mu: (bt m³, vk m²)} | None.
    H_than: chiều cao THÂN mục tiêu (m) để co tầng cho khớp tĩnh không."""
    parts = (pier or {}).get("parts") or {}
    be, than, cap = parts.get("be"), parts.get("than"), parts.get("xa_mu")
    if not (be or than or cap):
        return None
    if H_than is not None:
        H_than = max(0.3, float(H_than))
    out = {}
    out["be"]    = _vert_part_takeoff(be) if be else (0.0, 0.0)
    out["than"]  = _vert_part_takeoff(than, H_total=H_than) if than else (0.0, 0.0)
    out["xa_mu"] = _cap_takeoff(cap, width_m=cap_width) if cap else (0.0, 0.0)
    return out


def _row(ten, so_luong, bt_m3, coppha_m2, thep_kg, ghi_chu=""):
    return {
        "ten":       ten,
        "so_luong":  so_luong,
        "bt_m3":     round(bt_m3, 2),
        "coppha_m2": round(coppha_m2, 1),
        "thep_kg":   round(thep_kg, 0),
        "ghi_chu":   ghi_chu,
    }


# ── Kích thước chung suy từ d ────────────────────────────────────────────────
def _dims(d):
    kcn  = d.get("kcn_result") or d.get("ai_result") or {}
    geo  = d.get("geo_logic") or {}
    tru  = d.get("tru_result") or {}
    mong = d.get("mong_result") or {}
    bc      = _f(d.get("bc"), 12.0)
    n_nhip  = int(_f(kcn.get("tong_so_nhip"), 1)) or 1
    n_tru   = max(0, n_nhip - 1)
    L_nhip  = _f(kcn.get("chieu_dai"), 38.0)
    L_cau   = _f(geo.get("L_cau"), n_nhip * L_nhip)
    H_tru   = _f(d.get("H_tru_est"), 6.0)
    t_ban   = _f(d.get("t_ban_mm"), 200.0) * _MM2M
    n_dam   = int(_f(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn"), 5)) or 5
    H_dam   = _f(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao"), 1.75)
    loai_tru = str(tru.get("loai_tru", "Thân đặc"))
    # Trụ
    W_tru = max(1.2, bc * 0.08)
    L_tru = max(2.5, bc * 0.25)
    cap_H = max(0.8, bc * 0.06)
    cap_L = min(bc * 0.9, L_tru + 1.2)
    # Móng cọc — chấp nhận mọi bộ tên khóa (AI / thư viện / khối lượng)
    _Dmm = mong.get("D_coc_mm") or mong.get("kich_thuoc_mm")
    if _Dmm:
        D_coc_mm = _f(_Dmm, 800)
    else:                                   # thư viện dùng duong_kinh_coc (m)
        D_coc_mm = (_f(mong.get("duong_kinh_coc"), 0) * 1000.0) or 800
    L_coc     = _f(mong.get("chieu_dai_coc") or mong.get("L_coc_tu"), 20) or 20
    so_coc_be = int(_f(mong.get("so_coc_be") or mong.get("So_coc_tu")
                       or mong.get("so_coc"), 5)) or 5
    loai_coc  = str(mong.get("loai_mong", "Cọc khoan nhồi"))
    D_m = D_coc_mm * _MM2M
    Be_ngang = _f(mong.get("Be_ngang"), max(3.0, D_m * 4))
    Be_doc   = _f(mong.get("Be_doc"),   max(3.0, D_m * 4))
    Be_cao   = _f(mong.get("Be_cao"),   max(1.0, D_m * 1.5))
    return dict(
        bc=bc, n_nhip=n_nhip, n_tru=n_tru, L_nhip=L_nhip, L_cau=L_cau,
        H_tru=H_tru, t_ban=t_ban, n_dam=n_dam, H_dam=H_dam, loai_tru=loai_tru,
        W_tru=W_tru, L_tru=L_tru, cap_H=cap_H, cap_L=cap_L,
        D_coc_mm=D_coc_mm, D_m=D_m, L_coc=L_coc, so_coc_be=so_coc_be,
        loai_coc=loai_coc, Be_ngang=Be_ngang, Be_doc=Be_doc, Be_cao=Be_cao,
    )


# ── Cấu kiện đơn (1 đơn vị) ──────────────────────────────────────────────────
def than_tru_1(dm):
    """Thân 1 trụ → (bt, coppha)."""
    W, L, H = dm["W_tru"], dm["L_tru"], dm["H_tru"]
    lt = dm["loai_tru"].lower()
    if "2 cột" in lt or "2cot" in lt or "cột" in lt:
        D = max(1.0, dm["bc"] * 0.07)
        bt = 2 * math.pi * (D / 2) ** 2 * H
        cop = 2 * math.pi * D * H
    elif "rỗng" in lt or "rong" in lt:
        tWall = max(0.3, W * 0.18)
        A = W * L - (W - 2 * tWall) * (L - 2 * tWall)
        bt = A * H
        cop = 2 * (W + L) * H * 1.6           # cả trong + ngoài
    else:
        bt = W * L * H
        cop = 2 * (W + L) * H
    return bt, cop


def xa_mu_1(dm):
    cap_L, cap_H, W = dm["cap_L"], dm["cap_H"], dm["W_tru"] + 0.5
    bt = cap_L * W * cap_H
    cop = 2 * (cap_L + W) * cap_H + cap_L * W   # mặt bên + đáy
    return bt, cop


def dai_coc_1(dm):
    """Bệ/đài cọc (1 bệ) → (bt, coppha)."""
    bt = dm["Be_ngang"] * dm["Be_doc"] * dm["Be_cao"]
    cop = 2 * (dm["Be_ngang"] + dm["Be_doc"]) * dm["Be_cao"]   # 4 mặt bên
    return bt, cop


def coc_nhom(dm, so_coc):
    """Nhóm cọc (so_coc cọc) → (bt, coppha, thep)."""
    D, L = dm["D_m"], dm["L_coc"]
    if "khoan nhồi" in dm["loai_coc"].lower():
        A = math.pi * (D / 2) ** 2
        cop_1 = 0.0                  # đổ tại chỗ trong lỗ khoan — không ván khuôn
    else:
        A = D * D                    # cọc vuông đúc sẵn
        cop_1 = 4 * D * L            # mặt bên đúc sẵn
    bt_1 = A * L
    bt = bt_1 * so_coc
    cop = cop_1 * so_coc
    thep = bt * RHO_THEP["coc"]
    return bt, cop, thep


def mo_1(dm):
    """Thân 1 mố (xà mũ + tường thân + tường cánh) → (bt, coppha)."""
    cap_L, cap_H, W = dm["cap_L"], dm["cap_H"], dm["W_tru"] + 0.5
    H_mo = max(dm["H_tru"] * 0.3, 2.0)
    xa_mu = cap_L * W * cap_H
    than  = cap_L * 0.8 * H_mo
    L_canh = max(2.0, H_mo * 1.2)
    canh  = 2 * (L_canh * 0.5 * H_mo)
    bt = xa_mu + than + canh
    cop = (2 * (cap_L + W) * cap_H +            # xà mũ
           2 * (cap_L + 0.8) * H_mo +          # tường thân
           4 * (L_canh + 0.5) * H_mo)          # 2 tường cánh (2 mặt)
    return bt, cop


def ban_mat_cau(dm):
    A = dm["bc"] * dm["L_cau"]
    bt = A * dm["t_ban"]
    cop = A + 2 * (dm["bc"] + dm["L_cau"]) * dm["t_ban"]
    thep = bt * RHO_THEP["ban"]
    return bt, cop, thep


# ── Lan can / giải phân cách ─────────────────────────────────────────────────
def _railing_specs(d):
    """Trả về list (ten, A_m2, chu_vi_m, tong_dai_m) cho lan can/GPC đã chọn."""
    dm = _dims(d)
    out = []
    rails = (d.get("railings") or {}) if isinstance(d.get("railings"), dict) else {}
    for key, n_dai, nhan in (("lan_can", 2.0, "Lan can"),
                             ("giai_phan_cach", 1.0, "Giải phân cách")):
        rec = rails.get(key)
        L_tong = dm["L_cau"] * n_dai
        if rec and rec.get("outer"):
            A = _poly_area_mm2(rec["outer"]) * _MM2M * _MM2M
            chu_vi = _poly_perimeter_mm(rec["outer"]) * _MM2M
            out.append((f"{nhan} ({rec.get('ten','')})", A, chu_vi, L_tong))
        elif key == "lan_can":
            out.append((nhan, 0.12, 1.6, L_tong))     # ước tính mặc định
    return out


def kl_lan_can_rows(d):
    rows = []
    for ten, A, chu_vi, L in _railing_specs(d):
        bt = A * L
        cop = chu_vi * L
        thep = bt * RHO_THEP["lan_can"]
        rows.append(_row(ten, f"{L:.0f} m", bt, cop, thep,
                         f"A={A:.3f}m² × {L:.0f}m"))
    return rows


# ── Dầm theo loại ────────────────────────────────────────────────────────────
def _beam_section_area_m2(beam_rec, dm):
    """Diện tích MCN dầm (m²): ưu tiên polygon thư viện, nếu không thì ước tính."""
    if beam_rec:
        secs = beam_rec.get("sections") or {}
        # ưu tiên mặt cắt giữa (B-B) rồi bất kỳ mặt cắt có outer
        for name in ("B-B", "C-C", "A-A"):
            s = secs.get(name)
            if s and s.get("outer"):
                a = _poly_area_mm2(s["outer"]) * _MM2M * _MM2M
                holes = sum(_poly_area_mm2(h) for h in (s.get("holes") or []))
                return max(a - holes * _MM2M * _MM2M, a * 0.6)
        for s in secs.values():
            if s and s.get("outer"):
                return _poly_area_mm2(s["outer"]) * _MM2M * _MM2M
    # Ước tính theo loại × chiều cao
    H = dm["H_dam"]
    factor = {"super-t": 0.36, "dầm i": 0.30, "t ngược": 0.30,
              "bản rỗng": 0.55}
    loai = str((beam_rec or {}).get("loai_dam", "")).lower()
    k = next((v for kk, v in factor.items() if kk in loai), 0.34)
    return k * H


def kl_dam_rows(d, roles):
    """roles = list (nhãn, beam_rec|None, L_m). Trả rows theo loại dầm (khử trùng)."""
    dm = _dims(d)
    rows = []
    seen = set()
    for lbl, brec, L in roles:
        loai = (brec.get("loai_dam") if brec else None) or \
               (d.get("kcn_result") or {}).get("loai_dam", "Super-T")
        L_m = _f(L or (brec or {}).get("chieu_dai"), dm["L_nhip"])
        n_dam = int(_f((brec or {}).get("so_luong_dam"), dm["n_dam"])) or dm["n_dam"]
        # số nhịp dùng loại này (ước tính): two_tier chia dẫn/chính; mặc định all
        sig = (str(loai).lower(), round(L_m, 1))
        if sig in seen:
            continue
        seen.add(sig)
        A = _beam_section_area_m2(brec, dm)
        H = _f((brec or {}).get("chieu_cao"), dm["H_dam"])
        B = _f((brec or {}).get("be_rong_canh"), 2.0) or 2.0
        n_total = n_dam   # mỗi nhịp; người dùng nhân số nhịp ở bảng tổng hợp
        bt = A * L_m * n_total
        cop = 2 * (B + H) * L_m * n_total
        thep = bt * RHO_THEP["dam"]
        rows.append(_row(f"Dầm {loai} ({lbl})", n_total, bt, cop, thep,
                         f"{n_total} dầm × L={L_m:.1f}m · A={A:.3f}m²"))
    return rows


# ── BẢNG KHỐI LƯỢNG THEO VỊ TRÍ (mố/trụ độc lập, gồm cọc) ───────────────────
def _coc_row(dm):
    bt_c, cop_c, th_c = coc_nhom(dm, dm["so_coc_be"])
    return _row(f"Cọc {dm['loai_coc']} Ø{dm['D_coc_mm']:.0f}",
                dm["so_coc_be"], bt_c, cop_c, th_c,
                f"{dm['so_coc_be']} cọc × {dm['L_coc']:.0f}m")


def khoi_luong_mo(d):
    """Khối lượng 1 MỐ (thân mố + đài cọc + cọc)."""
    dm = _dims(d)
    bt_m, cop_m = mo_1(dm)
    bt_b, cop_b = dai_coc_1(dm)
    return [
        _row("Thân mố", 1, bt_m, cop_m, bt_m * RHO_THEP["mo"]),
        _row("Đài cọc (bệ)", 1, bt_b, cop_b, bt_b * RHO_THEP["dai_coc"]),
        _coc_row(dm),
    ]


def _tru_bt_cop(d, dm):
    """Trả (than, xa_mu, be) = [(bt,cop),...] + ghi_chú nguồn. Ưu tiên MÔ HÌNH."""
    _tk = pier_model_takeoff((d or {}).get("_pier_model"),
                             H_than=dm.get("H_tru"), cap_width=dm.get("bc"))
    if _tk:
        return _tk["than"], _tk["xa_mu"], _tk["be"], "theo mô hình"
    return than_tru_1(dm), xa_mu_1(dm), dai_coc_1(dm), ""


def khoi_luong_tru(d):
    """Khối lượng 1 TRỤ (thân + xà mũ + đài cọc + cọc)."""
    dm = _dims(d)
    (bt_t, cop_t), (bt_x, cop_x), (bt_b, cop_b), _src = _tru_bt_cop(d, dm)
    return [
        _row("Thân trụ", 1, bt_t, cop_t, bt_t * RHO_THEP["than_tru"], _src),
        _row("Xà mũ", 1, bt_x, cop_x, bt_x * RHO_THEP["xa_mu"], _src),
        _row("Đài cọc (bệ)", 1, bt_b, cop_b, bt_b * RHO_THEP["dai_coc"], _src),
        _coc_row(dm),
    ]


def khoi_luong_vi_tri(d, vi_tri):
    """Khối lượng cho 1 vị trí theo key: 'mo_trai'/'mo_phai'/'tru_i'."""
    return khoi_luong_mo(d) if str(vi_tri).startswith("mo") else khoi_luong_tru(d)


def bang_theo_vi_tri(d):
    """Trả về list (ten_vi_tri, [rows]) cho Mố trái · Trụ 1..n · Mố phải."""
    dm = _dims(d)
    out = [("🧱 Mố trái", khoi_luong_mo(d))]
    for i in range(dm["n_tru"]):
        out.append((f"🏗️ Trụ {i + 1}", khoi_luong_tru(d)))
    out.append(("🧱 Mố phải", khoi_luong_mo(d)))
    return out


# ── BẢNG KHỐI LƯỢNG DẦM (toàn cầu) ──────────────────────────────────────────
def bang_dam(d, dam_roles=None):
    """Khối lượng dầm theo loại cho TOÀN CẦU (nhân số nhịp)."""
    dm = _dims(d)
    if not dam_roles:
        dam_roles = [("toàn cầu", None, dm["L_nhip"])]
    base = kl_dam_rows(d, dam_roles)
    # 1 loại → ×n_nhip; nhiều loại (2 tầng) → để nguyên (mỗi loại đại diện)
    mult = dm["n_nhip"] if len(base) <= 1 else 1
    out = []
    for r in base:
        out.append(_row(r["ten"], r["so_luong"],
                        r["bt_m3"] * mult, r["coppha_m2"] * mult,
                        r["thep_kg"] * mult,
                        r["ghi_chu"] + (f" × {dm['n_nhip']} nhịp" if mult > 1 else "")))
    return out


# ── BẢNG KHỐI LƯỢNG TOÀN CẦU ────────────────────────────────────────────────
def bang_toan_cau(d, dam_roles=None):
    """Tổng hợp khối lượng toàn cầu. dam_roles = list (nhãn, beam_rec, L) để
    tính dầm theo loại; nếu None → ước tính theo kcn."""
    dm = _dims(d)
    rows = list(bang_dam(d, dam_roles))

    # Bản mặt cầu
    bt_b, cop_b, th_b = ban_mat_cau(dm)
    rows.append(_row("Bản mặt cầu", 1, bt_b, cop_b, th_b,
                     f"{dm['bc']:.1f}×{dm['L_cau']:.0f}m, dày {dm['t_ban']*1000:.0f}mm"))

    # Trụ (×n_tru) — ưu tiên MÔ HÌNH lắp ghép
    (bt_t, cop_t), (bt_x, cop_x), (bt_be_m, cop_be_m), _src = _tru_bt_cop(d, dm)
    nt = dm["n_tru"]
    if nt > 0:
        rows.append(_row("Thân trụ", nt, bt_t * nt, cop_t * nt,
                         bt_t * nt * RHO_THEP["than_tru"], _src))
        rows.append(_row("Xà mũ trụ", nt, bt_x * nt, cop_x * nt,
                         bt_x * nt * RHO_THEP["xa_mu"], _src))

    # Mố (×2)
    bt_m, cop_m = mo_1(dm)
    rows.append(_row("Mố cầu", 2, bt_m * 2, cop_m * 2, bt_m * 2 * RHO_THEP["mo"]))

    # Đài cọc (bệ): trụ theo mô hình (nếu có), mố theo tham số
    n_be = nt + 2
    bt_dc, cop_dc = dai_coc_1(dm)
    if _src:
        bt_dc_tot  = bt_be_m * nt + bt_dc * 2
        cop_dc_tot = cop_be_m * nt + cop_dc * 2
    else:
        bt_dc_tot, cop_dc_tot = bt_dc * n_be, cop_dc * n_be
    rows.append(_row("Đài cọc (bệ móng)", n_be, bt_dc_tot, cop_dc_tot,
                     bt_dc_tot * RHO_THEP["dai_coc"], _src))

    # Cọc (tổng)
    n_coc = dm["so_coc_be"] * n_be
    bt_c, cop_c, th_c = coc_nhom(dm, n_coc)
    rows.append(_row(f"Cọc {dm['loai_coc']} Ø{dm['D_coc_mm']:.0f}", n_coc,
                     bt_c, cop_c, th_c,
                     f"{n_be} bệ × {dm['so_coc_be']} cọc × {dm['L_coc']:.0f}m"))

    # Lan can / GPC
    rows.extend(kl_lan_can_rows(d))
    return rows


def tong_hop(rows):
    """Tổng cộng bt/coppha/thep từ list rows."""
    return {
        "bt_m3":     round(sum(_f(r["bt_m3"]) for r in rows), 2),
        "coppha_m2": round(sum(_f(r["coppha_m2"]) for r in rows), 1),
        "thep_kg":   round(sum(_f(r["thep_kg"]) for r in rows), 0),
    }


# ── DỰ TOÁN: từ bảng khối lượng × đơn giá → thành tiền ───────────────────────
# Đơn giá tham khảo (đồng): bê tông đ/m³, ván khuôn đ/m², cốt thép đ/kg.
DON_GIA_MAC_DINH = {"bt": 1_800_000, "vk": 280_000, "thep": 22_000}


def du_toan(rows, dg_bt=None, dg_vk=None, dg_thep=None):
    """Từ list rows khối lượng → list rows dự toán (thêm thanh_tien) + tổng tiền.
    Trả về (rows_dt, tong_tien). Đơn giá None → dùng mặc định."""
    dg_bt   = DON_GIA_MAC_DINH["bt"]   if dg_bt   is None else dg_bt
    dg_vk   = DON_GIA_MAC_DINH["vk"]   if dg_vk   is None else dg_vk
    dg_thep = DON_GIA_MAC_DINH["thep"] if dg_thep is None else dg_thep
    out = []
    tong = 0.0
    for r in rows:
        tien = (_f(r["bt_m3"]) * dg_bt + _f(r["coppha_m2"]) * dg_vk
                + _f(r["thep_kg"]) * dg_thep)
        tong += tien
        out.append({**r, "thanh_tien": round(tien, 0)})
    return out, round(tong, 0)

