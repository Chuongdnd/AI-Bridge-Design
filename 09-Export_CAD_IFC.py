"""
Module 09 — Export CAD (DXF) & BIM (IFC)
-----------------------------------------
2D → DXF (ezdxf):
    export_mcn_dxf()        : Mặt cắt ngang điển hình
    export_trac_doc_dxf()   : Trắc dọc cầu (đơn giản hóa)
    export_tru_dxf()        : Bản vẽ trụ cầu (2 hình chiếu)

3D → IFC (ifcopenshell):
    export_pier_ifc()       : Model trụ cầu
    export_bridge_ifc()     : Model kết cấu toàn cầu (trụ + dầm + bản)

Trả về bytes để Streamlit download_button dùng trực tiếp.
"""

import io
import math
import numpy as np

# ─── DXF ────────────────────────────────────────────────────────────────────
try:
    import ezdxf
    from ezdxf import colors
    from ezdxf.enums import TextEntityAlignment
    _HAS_EZDXF = True
except ImportError:
    _HAS_EZDXF = False

# ─── IFC ────────────────────────────────────────────────────────────────────
try:
    import ifcopenshell
    import ifcopenshell.api
    _HAS_IFC = True
except ImportError:
    _HAS_IFC = False


# ===========================================================================
# TIỆN ÍCH DXF
# ===========================================================================
_LAYER_CFG = {
    "TERRAIN":      {"color": 3,   "linetype": "CONTINUOUS"},   # xanh lá
    "DESIGN_LINE":  {"color": 1,   "linetype": "CONTINUOUS"},   # đỏ
    "GIRDER_BOT":   {"color": 5,   "linetype": "DASHED"},       # xanh dương
    "CLEARANCE":    {"color": 6,   "linetype": "CONTINUOUS"},   # magenta
    "WATER":        {"color": 4,   "linetype": "DASHED"},       # cyan
    "ABUTMENT":     {"color": 30,  "linetype": "CONTINUOUS"},   # cam
    "PIER":         {"color": 8,   "linetype": "CONTINUOUS"},   # xám
    "DECK":         {"color": 253, "linetype": "CONTINUOUS"},   # xám nhạt
    "GIRDER":       {"color": 5,   "linetype": "CONTINUOUS"},
    "RAILING":      {"color": 7,   "linetype": "CONTINUOUS"},   # trắng
    "DIMS":         {"color": 2,   "linetype": "CONTINUOUS"},   # vàng
    "TEXT":         {"color": 7,   "linetype": "CONTINUOUS"},
    "CENTERLINE":   {"color": 1,   "linetype": "CENTER"},
    "HATCH":        {"color": 8,   "linetype": "CONTINUOUS"},
}

def _setup_doc(title="BRIDGE DRAWING"):
    """Tạo DXF document mới với các layer chuẩn."""
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6      # meters
    doc.header["$MEASUREMENT"] = 1   # metric

    for name, cfg in _LAYER_CFG.items():
        if name not in doc.layers:
            layer = doc.layers.new(name=name)
            layer.color = cfg["color"]
            try:
                layer.linetype = cfg["linetype"]
            except Exception:
                pass
    return doc


def _add_dim_linear(msp, p1, p2, dist, text="", layer="DIMS", dimscale=1.0):
    """Thêm dimension tuyến tính."""
    try:
        msp.add_linear_dim(
            base=(p1[0], p1[1] + dist),
            p1=p1, p2=p2,
            dimstyle="EZDXF",
            override={"dimtxt": 0.25 * dimscale, "dimscale": dimscale},
        ).render()
    except Exception:
        # Fallback: vẽ thủ công
        msp.add_line(p1, (p1[0], p1[1] + dist), dxfattribs={"layer": layer})
        msp.add_line(p2, (p2[0], p2[1] + dist), dxfattribs={"layer": layer})
        mx = (p1[0] + p2[0]) / 2
        msp.add_line((p1[0], p1[1]+dist), (p2[0], p2[1]+dist), dxfattribs={"layer": layer})
        label = text or f"{abs(p2[0]-p1[0]):.2f}"
        msp.add_text(label, dxfattribs={"layer": "TEXT", "height": 0.25 * dimscale}).set_placement(
            (mx, p1[1] + dist + 0.1)
        )


def _title_block(msp, title, subtitle, scale, x0=0, y0=0):
    h = 0.35
    msp.add_text(title,    dxfattribs={"layer": "TEXT", "height": h * 1.4}).set_placement((x0, y0))
    msp.add_text(subtitle, dxfattribs={"layer": "TEXT", "height": h}).set_placement((x0, y0 - 0.6))
    msp.add_text(f"TỶ LỆ: {scale}", dxfattribs={"layer": "TEXT", "height": h}).set_placement((x0, y0 - 1.1))
    msp.add_text("ĐẠI HỌC GIAO THÔNG VẬN TẢI TP.HCM (UTH) — AI BRIDGE DESIGN",
                 dxfattribs={"layer": "TEXT", "height": h * 0.8}).set_placement((x0, y0 - 1.6))


# ===========================================================================
# 1. DXF — MẶT CẮT NGANG
# ===========================================================================
def export_mcn_dxf(design_data) -> bytes:
    """
    Xuất bản vẽ Mặt cắt ngang điển hình ra file DXF.
    design_data cần có: bc, kcn_result (hoặc ai_result).
    """
    if not _HAS_EZDXF:
        raise RuntimeError("Thiếu thư viện ezdxf")

    kcn  = design_data.get("kcn_result") or design_data.get("ai_result", {})
    bc   = float(design_data.get("bc", 12.0))
    H_dam = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.65))
    kc    = float(kcn.get("khoang_cach_dam", 2.0))
    n_dam = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 6))
    oh    = float(kcn.get("overhang", 0.5))
    loai  = str(kcn.get("loai_dam", "Dầm I"))

    doc = _setup_doc("MẶT CẮT NGANG")
    msp = doc.modelspace()

    # --- Bản mặt cầu (deck slab) ---
    t_ban = 0.20   # chiều dày bản mặt cầu
    w_lc  = 0.5    # lan can
    x_left  = -bc / 2
    x_right =  bc / 2

    # Bản mặt cầu
    deck_pts = [(x_left, 0), (x_right, 0), (x_right, -t_ban), (x_left, -t_ban)]
    msp.add_lwpolyline(deck_pts + [deck_pts[0]], close=True,
                       dxfattribs={"layer": "DECK", "lineweight": 50})

    # Gạch nền bản mặt cầu
    hatch = msp.add_hatch(color=253, dxfattribs={"layer": "HATCH"})
    hatch.paths.add_polyline_path([(p[0], p[1]) for p in deck_pts])
    hatch.set_pattern_fill("ANSI31", scale=0.05)

    # --- Dầm chính ---
    # Tính vị trí tim từng dầm
    x_first = x_left + oh
    dam_xs = [x_first + i * kc for i in range(n_dam)]

    def _draw_I_beam(x_tim, h, bw=0.15, bf=0.35, tf=0.08):
        """Vẽ tiết diện dầm I/Super-T đơn giản."""
        y0 = -t_ban         # đỉnh dầm ngang bản
        y1 = y0 - h         # đáy dầm
        # Bụng
        pts_web = [(x_tim - bw/2, y0), (x_tim + bw/2, y0),
                   (x_tim + bw/2, y1), (x_tim - bw/2, y1)]
        msp.add_lwpolyline(pts_web + [pts_web[0]], close=True,
                           dxfattribs={"layer": "GIRDER", "lineweight": 40})
        # Cánh dưới
        pts_bot = [(x_tim - bf/2, y1 + tf), (x_tim + bf/2, y1 + tf),
                   (x_tim + bf/2, y1),       (x_tim - bf/2, y1)]
        msp.add_lwpolyline(pts_bot + [pts_bot[0]], close=True,
                           dxfattribs={"layer": "GIRDER", "lineweight": 40})

    def _draw_T_beam(x_tim, h, bw=0.14, bt=1.0, tf=0.14):
        """Vẽ tiết diện dầm T ngược."""
        y0 = -t_ban
        y1 = y0 - h
        pts_web = [(x_tim - bw/2, y0), (x_tim + bw/2, y0),
                   (x_tim + bw/2, y1), (x_tim - bw/2, y1)]
        msp.add_lwpolyline(pts_web + [pts_web[0]], close=True,
                           dxfattribs={"layer": "GIRDER", "lineweight": 40})
        pts_top = [(x_tim - bt/2, y0), (x_tim + bt/2, y0),
                   (x_tim + bt/2, y0 - tf), (x_tim - bt/2, y0 - tf)]
        msp.add_lwpolyline(pts_top + [pts_top[0]], close=True,
                           dxfattribs={"layer": "GIRDER", "lineweight": 40})

    for xd in dam_xs:
        if "T ngược" in loai:
            _draw_T_beam(xd, H_dam)
        else:
            _draw_I_beam(xd, H_dam)

    # --- Lan can ---
    for side in [x_left, x_right]:
        sign = 1 if side == x_left else -1
        railing_pts = [
            (side, 0), (side + sign * w_lc, 0),
            (side + sign * w_lc, 1.1), (side, 1.1)
        ]
        msp.add_lwpolyline(railing_pts + [railing_pts[0]], close=True,
                           dxfattribs={"layer": "RAILING", "lineweight": 30})

    # --- Đường tim ---
    msp.add_line((0, -H_dam - t_ban - 0.5), (0, 0.5),
                 dxfattribs={"layer": "CENTERLINE", "lineweight": 13})
    msp.add_text("CL", dxfattribs={"layer": "TEXT", "height": 0.2}).set_placement((0.1, 0.3))

    # --- Dimensions ---
    _add_dim_linear(msp, (x_left, -H_dam - t_ban - 0.5),
                    (x_right, -H_dam - t_ban - 0.5),
                    dist=-0.8, text=f"B_cầu = {bc}m")
    # Chiều cao dầm
    _add_dim_linear(msp, (x_right + 0.8, -t_ban),
                    (x_right + 0.8, -t_ban - H_dam),
                    dist=0.6, text=f"H = {H_dam}m")

    # --- Khoảng cách dầm annotation ---
    if n_dam >= 2:
        y_arr = -H_dam - t_ban - 0.3
        for i in range(n_dam - 1):
            xm = (dam_xs[i] + dam_xs[i+1]) / 2
            msp.add_text(f"@{kc:.2f}", dxfattribs={"layer": "DIMS", "height": 0.18}).set_placement((xm, y_arr))

    # --- Title block ---
    vtk  = design_data.get("vtk", "—")
    loai_duong = design_data.get("loai_duong", "")
    _title_block(msp,
                 title=f"MẶT CẮT NGANG CẦU ĐIỂN HÌNH",
                 subtitle=f"Bc={bc}m  |  {n_dam}×{loai}  |  Vtk={vtk}km/h  |  {loai_duong}",
                 scale="1:50",
                 x0=x_left, y0=-H_dam - t_ban - 2.5)

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


# ===========================================================================
# 2. DXF — TRẮC DỌC
# ===========================================================================
def export_trac_doc_dxf(design_data) -> bytes:
    """Xuất bản vẽ Trắc dọc cầu ra DXF."""
    if not _HAS_EZDXF:
        raise RuntimeError("Thiếu thư viện ezdxf")

    geo   = design_data.get("geo_logic", {})
    kcn   = design_data.get("kcn_result") or design_data.get("ai_result", {})
    B_tk  = float(design_data.get("B", 20))
    H_tk  = float(design_data.get("H", 3.5))
    MNCN  = float(data := design_data.get("MNCN", 3.5))
    MNTT  = float(design_data.get("MNTT", 2.0))
    MNTN  = float(design_data.get("MNTN", 0.5))

    x_mo_trai = float(geo.get("x_mo_trai", -60))
    x_mo_phai = float(geo.get("x_mo_phai",  60))
    x_tim     = float(geo.get("x_tim_clearance", 0))
    y_dinh    = float(geo.get("y_dinh", 6.0))
    y_t       = float(geo.get("y_t", 5.8))
    x_t1      = float(geo.get("x_t1", -40))
    x_t2      = float(geo.get("x_t2",  40))
    R_val     = float(geo.get("R", 5000))
    i_val     = float(geo.get("i_val", 0.02))
    y_base    = float(geo.get("y_base_goc", 2.0))
    L_cau     = float(geo.get("L_cau", 120))
    h_tn_tb   = float(design_data.get("h_tn_tb", y_base))

    H_dam     = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.65))
    n_nhip    = int(kcn.get("tong_so_nhip", 3))
    L_nhip    = float(kcn.get("chieu_dai", 40))
    loai_dam  = str(kcn.get("loai_dam", "Dầm I"))

    doc = _setup_doc("TRẮC DỌC")
    msp = doc.modelspace()

    margin = 30
    x_start = x_mo_trai - margin
    x_end   = x_mo_phai + margin

    # --- Đường thiết kế (đường đỏ) ---
    xs = np.linspace(x_start, x_end, 300)
    design_pts = []
    for x in xs:
        if x < x_t1:
            y = y_t - i_val * (x_t1 - x)
        elif x > x_t2:
            y = y_t - i_val * (x - x_t2)
        else:
            y = y_dinh - (x - x_tim)**2 / (2 * R_val)
        design_pts.append((float(x), float(y)))
    msp.add_lwpolyline(design_pts, dxfattribs={"layer": "DESIGN_LINE", "lineweight": 50})

    # Đáy dầm
    h_tong = H_dam + 0.20
    bot_pts = [(p[0], p[1] - h_tong) for p in design_pts]
    msp.add_lwpolyline(bot_pts, dxfattribs={"layer": "GIRDER_BOT", "lineweight": 30})

    # --- Đường địa hình (flat approximation nếu không có survey) ---
    terrain_y = h_tn_tb
    msp.add_line((x_start, terrain_y), (x_end, terrain_y),
                 dxfattribs={"layer": "TERRAIN", "lineweight": 40})
    msp.add_text("Đường đất tự nhiên (trung bình)",
                 dxfattribs={"layer": "TERRAIN", "height": 0.3}).set_placement((x_start + 2, terrain_y + 0.15))

    # --- Mực nước ---
    for (yn, label, col) in [
        (MNCN, f"MNCN H1% = {MNCN:.3f}m", 1),
        (MNTT, f"MNTT H5% = {MNTT:.3f}m", 4),
        (MNTN, f"MNTN H98% = {MNTN:.3f}m", 3),
    ]:
        msp.add_line((x_mo_trai + 5, yn), (x_mo_phai - 5, yn),
                     dxfattribs={"layer": "WATER", "lineweight": 25})
        msp.add_text(label, dxfattribs={"layer": "WATER", "height": 0.25}).set_placement(
            (x_mo_trai + 6, yn + 0.1))

    # --- Mố ---
    y_mo  = float(geo.get("y_mo", y_base))
    y_bot_mo = terrain_y - 2.0
    for xm in [x_mo_trai, x_mo_phai]:
        idx = int(np.argmin(np.abs(np.array([p[0] for p in design_pts]) - xm)))
        y_top_mo = design_pts[idx][1]
        mo_w = 3.0
        pts_mo = [
            (xm - mo_w/2, y_bot_mo), (xm + mo_w/2, y_bot_mo),
            (xm + mo_w/2, y_top_mo), (xm - mo_w/2, y_top_mo)
        ]
        msp.add_lwpolyline(pts_mo + [pts_mo[0]], close=True,
                           dxfattribs={"layer": "ABUTMENT", "lineweight": 50})
        hatch = msp.add_hatch(dxfattribs={"layer": "HATCH"})
        hatch.paths.add_polyline_path([(p[0], p[1]) for p in pts_mo])
        hatch.set_pattern_fill("ANSI31", scale=0.2)

    # --- Trụ ---
    x_trus = []
    if n_nhip > 1:
        for i in range(1, n_nhip):
            x_trus.append(x_mo_trai + i * L_nhip)
    tru_w = 1.5
    H_tru = float(design_data.get("H_tru_est", 5.0))
    for xt in x_trus:
        if x_mo_trai < xt < x_mo_phai:
            idx = int(np.argmin(np.abs(np.array([p[0] for p in design_pts]) - xt)))
            y_top_tru = design_pts[idx][1] - h_tong
            y_bot_tru = y_top_tru - H_tru
            pts_tru = [
                (xt - tru_w/2, y_bot_tru), (xt + tru_w/2, y_bot_tru),
                (xt + tru_w/2, y_top_tru), (xt - tru_w/2, y_top_tru)
            ]
            msp.add_lwpolyline(pts_tru + [pts_tru[0]], close=True,
                               dxfattribs={"layer": "PIER", "lineweight": 50})

    # --- Khung tĩnh không ---
    idx_tim = int(np.argmin(np.abs(np.array([p[0] for p in design_pts]) - x_tim)))
    y_tim_tk = design_pts[idx_tim][1]
    pts_tk = [
        (x_tim - B_tk/2, y_tim_tk - H_tk), (x_tim + B_tk/2, y_tim_tk - H_tk),
        (x_tim + B_tk/2, y_tim_tk),         (x_tim - B_tk/2, y_tim_tk)
    ]
    msp.add_lwpolyline(pts_tk + [pts_tk[0]], close=True,
                       dxfattribs={"layer": "CLEARANCE", "lineweight": 35})
    msp.add_text(f"TĨNH KHÔNG  B={B_tk}m × H={H_tk}m",
                 dxfattribs={"layer": "CLEARANCE", "height": 0.28}).set_placement(
        (x_tim - B_tk/2, y_tim_tk - H_tk - 0.3))

    # --- Chú thích sơ đồ nhịp ---
    y_annot = terrain_y - 3.5
    msp.add_text(f"SƠ ĐỒ NHỊP: {n_nhip} × {L_nhip:.1f}m ({loai_dam})  |  L_cầu = {L_cau:.1f}m",
                 dxfattribs={"layer": "TEXT", "height": 0.35}).set_placement((x_mo_trai, y_annot))

    # Đường gióng T1, T2
    for (xv, lbl) in [(x_t1, "T1"), (x_t2, "T2")]:
        msp.add_line((xv, y_annot - 0.5), (xv, y_t + 0.5),
                     dxfattribs={"layer": "DIMS", "lineweight": 13})
        msp.add_text(lbl, dxfattribs={"layer": "DIMS", "height": 0.25}).set_placement((xv + 0.3, y_t + 0.3))

    # --- Title ---
    _title_block(msp,
                 title="TRẮC DỌC THEO TIM TUYẾN",
                 subtitle=f"L_cầu={L_cau:.1f}m  |  {n_nhip}×{L_nhip:.1f}m {loai_dam}  |  MNCN={MNCN:.3f}m",
                 scale="H: 1:500  V: 1:100",
                 x0=x_start, y0=y_annot - 2.0)

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


# ===========================================================================
# 3. DXF — BẢN VẼ TRỤ CẦU (2 hình chiếu)
# ===========================================================================
def export_tru_dxf(design_data) -> bytes:
    """
    Xuất bản vẽ trụ cầu 2 hình chiếu (chính diện + cạnh).
    Lấy thông số từ design_data và session state.
    """
    if not _HAS_EZDXF:
        raise RuntimeError("Thiếu thư viện ezdxf")

    H     = float(design_data.get("H_tru_est", 5.0))      # chiều cao thân trụ
    W     = 1.5                                             # chiều rộng dọc cầu
    L_tru = max(2.5, float(design_data.get("bc", 12)) * 0.3)  # chiều dài ngang cầu
    cap_H = 0.8                                             # chiều cao xà mũ
    cap_W = W + 1.0
    cap_L = L_tru + 0.5
    base_H = 1.5                                           # chiều cao bệ trụ
    base_W = W + 1.5
    base_L = L_tru + 1.0
    loai_tru = str((design_data.get("tru_result") or {}).get("loai_tru", "Trụ đặc"))

    doc = _setup_doc("BẢN VẼ TRỤ CẦU")
    msp = doc.modelspace()

    GAP = L_tru + 8   # khoảng cách 2 hình chiếu

    # ── Hình chiếu CHÍNH DIỆN (nhìn dọc cầu → thấy mặt rộng) ──
    def draw_elevation(x_off, label, shaft_w, cap_w, base_w):
        # Bệ trụ
        msp.add_lwpolyline([
            (x_off - base_w/2, -base_H), (x_off + base_w/2, -base_H),
            (x_off + base_w/2, 0),       (x_off - base_w/2, 0)
        ] + [(x_off - base_w/2, -base_H)], close=True,
            dxfattribs={"layer": "PIER", "lineweight": 50})

        if "2 cột" in loai_tru.lower():
            # Khung 2 cột: vẽ 2 cột riêng
            col_w  = shaft_w * 0.6
            col_sp = shaft_w * 1.8
            for cx in [x_off - col_sp/2, x_off + col_sp/2]:
                msp.add_lwpolyline([
                    (cx - col_w/2, 0), (cx + col_w/2, 0),
                    (cx + col_w/2, H), (cx - col_w/2, H)
                ] + [(cx - col_w/2, 0)], close=True,
                    dxfattribs={"layer": "PIER", "lineweight": 50})
        else:
            # Thân đặc
            msp.add_lwpolyline([
                (x_off - shaft_w/2, 0), (x_off + shaft_w/2, 0),
                (x_off + shaft_w/2, H), (x_off - shaft_w/2, H)
            ] + [(x_off - shaft_w/2, 0)], close=True,
                dxfattribs={"layer": "PIER", "lineweight": 50})

        # Xà mũ (cap)
        msp.add_lwpolyline([
            (x_off - cap_w/2, H), (x_off + cap_w/2, H),
            (x_off + cap_w/2, H + cap_H), (x_off - cap_w/2, H + cap_H)
        ] + [(x_off - cap_w/2, H)], close=True,
            dxfattribs={"layer": "PIER", "lineweight": 60})

        # Gạch
        for elem_pts in [
            [(x_off - base_w/2, -base_H), (x_off + base_w/2, -base_H),
             (x_off + base_w/2, 0),       (x_off - base_w/2, 0)],
        ]:
            hatch = msp.add_hatch(dxfattribs={"layer": "HATCH"})
            hatch.paths.add_polyline_path([(p[0], p[1]) for p in elem_pts])
            hatch.set_pattern_fill("ANSI37", scale=0.15)

        # Đường tim
        msp.add_line((x_off, -base_H - 0.5), (x_off, H + cap_H + 0.5),
                     dxfattribs={"layer": "CENTERLINE", "lineweight": 13})

        # Dimensions
        _add_dim_linear(msp, (x_off - cap_w/2, H + cap_H + 0.5),
                        (x_off + cap_w/2, H + cap_H + 0.5), dist=0.6,
                        text=f"Xà mũ = {cap_w:.2f}m")
        _add_dim_linear(msp, (x_off - base_w/2, -base_H - 0.5),
                        (x_off + base_w/2, -base_H - 0.5), dist=-0.6,
                        text=f"Bệ = {base_w:.2f}m")
        _add_dim_linear(msp, (x_off + cap_w/2 + 0.6, 0),
                        (x_off + cap_w/2 + 0.6, H), dist=0.6,
                        text=f"H_trụ = {H:.2f}m")
        _add_dim_linear(msp, (x_off + cap_w/2 + 0.6, -base_H),
                        (x_off + cap_w/2 + 0.6, 0), dist=0.6,
                        text=f"Bệ H = {base_H:.2f}m")

        # Label
        msp.add_text(label, dxfattribs={"layer": "TEXT", "height": 0.35}).set_placement(
            (x_off - cap_w/2, -base_H - 1.8))

    # Hình chiếu 1: nhìn dọc cầu (shaft = W, cap = cap_W, base = base_W)
    draw_elevation(0, "HÌNH CHIẾU ĐỨNG (Nhìn dọc cầu)", W, cap_W, base_W)
    # Hình chiếu 2: nhìn ngang cầu (shaft = L_tru, cap = cap_L, base = base_L)
    draw_elevation(GAP, "HÌNH CHIẾU CẠNH (Nhìn ngang cầu)", L_tru, cap_L, base_L)

    # Title block
    bc_val = design_data.get("bc", "—")
    _title_block(msp,
                 title=f"BẢN VẼ TRỤ CẦU — {loai_tru.upper()}",
                 subtitle=f"H_trụ={H:.2f}m  |  B_cầu={bc_val}m  |  Xà mũ={cap_W:.2f}×{cap_L:.2f}m  |  Bệ={base_W:.2f}×{base_L:.2f}×{base_H:.1f}m",
                 scale="1:50",
                 x0=-base_W / 2, y0=-base_H - 3.0)

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


# ===========================================================================
# 4 & 5. IFC — LOW-LEVEL API (version-stable, IFC4)
# ===========================================================================
def _new_ifc():
    """Tạo IFC4 file với header, units và context chuẩn."""
    ifc = ifcopenshell.file(schema="IFC4")
    try:
        ifc.wrapped_data.header.file_name.name = "bridge.ifc"
        ifc.wrapped_data.header.file_name.author = ["UTH-AI Bridge Design"]
    except Exception:
        pass

    # Units: meter + radian
    unit_assignment = ifc.createIfcUnitAssignment([
        ifc.createIfcSIUnit(None, "LENGTHUNIT",  None, "METRE"),
        ifc.createIfcSIUnit(None, "AREAUNIT",    None, "SQUARE_METRE"),
        ifc.createIfcSIUnit(None, "VOLUMEUNIT",  None, "CUBIC_METRE"),
        ifc.createIfcSIUnit(None, "PLANEANGLEUNIT", None, "RADIAN"),
    ])
    project = ifc.createIfcProject(
        ifcopenshell.guid.new(), None, "Bridge Project", None,
        None, None, None, (unit_assignment,), None
    )

    # Geometric context
    origin_2d   = ifc.createIfcCartesianPoint([0.0, 0.0])
    ax_2d       = ifc.createIfcAxis2Placement2D(origin_2d, None)
    origin_3d   = ifc.createIfcCartesianPoint([0.0, 0.0, 0.0])
    z_dir       = ifc.createIfcDirection([0.0, 0.0, 1.0])
    x_dir       = ifc.createIfcDirection([1.0, 0.0, 0.0])
    ax_3d       = ifc.createIfcAxis2Placement3D(origin_3d, z_dir, x_dir)
    geo_ctx     = ifc.createIfcGeometricRepresentationContext(
        None, "Model", 3, 1.0e-5, ax_3d, ax_2d
    )
    body_ctx    = ifc.createIfcGeometricRepresentationSubContext(
        "Body", "Model", None, None, None, None, geo_ctx, None, "MODEL_VIEW", None
    )

    # Site → Building → Storey hierarchy
    site_placement = ifc.createIfcLocalPlacement(
        None, ifc.createIfcAxis2Placement3D(origin_3d, z_dir, x_dir)
    )
    site     = ifc.createIfcSite(ifcopenshell.guid.new(), None, "Site", None, None,
                                  site_placement, None, None, "ELEMENT", None, None, None, None, None)
    building = ifc.createIfcBuilding(ifcopenshell.guid.new(), None, "Bridge", None, None,
                                      site_placement, None, None, "ELEMENT", None, None, None)
    storey   = ifc.createIfcBuildingStorey(ifcopenshell.guid.new(), None, "Level 0",
                                            None, None, site_placement, None, None, "ELEMENT", 0.0)

    ifc.createIfcRelAggregates(ifcopenshell.guid.new(), None, None, None, project, [site])
    ifc.createIfcRelAggregates(ifcopenshell.guid.new(), None, None, None, site,    [building])
    ifc.createIfcRelAggregates(ifcopenshell.guid.new(), None, None, None, building,[storey])

    return ifc, storey, body_ctx


def _ifc_box(ifc, storey, body_ctx,
             cx, cy, cz, dx, dy, dz,
             ifc_class="IfcColumn", name="Element",
             material_name="Concrete C35"):
    """
    Thêm 1 phần tử IFC dạng hộp chữ nhật vào storey.
    (cx,cy,cz) = tâm đáy hộp, (dx,dy,dz) = kích thước.
    """
    # Profile: hình chữ nhật trong mặt phẳng XY
    origin_2d = ifc.createIfcCartesianPoint([0.0, 0.0])
    ax_2d     = ifc.createIfcAxis2Placement2D(origin_2d, None)
    profile   = ifc.createIfcRectangleProfileDef("AREA", None, ax_2d, float(dx), float(dy))

    # Extrude theo Z
    z_dir  = ifc.createIfcDirection([0.0, 0.0, 1.0])
    solid  = ifc.createIfcExtrudedAreaSolid(profile, None, z_dir, float(dz))
    shape  = ifc.createIfcShapeRepresentation(body_ctx, "Body", "SweptSolid", [solid])
    prod_rep = ifc.createIfcProductDefinitionShape(None, None, [shape])

    # Placement: dịch chuyển tâm hộp đến (cx, cy, cz)
    loc    = ifc.createIfcCartesianPoint([float(cx), float(cy), float(cz)])
    z3     = ifc.createIfcDirection([0.0, 0.0, 1.0])
    x3     = ifc.createIfcDirection([1.0, 0.0, 0.0])
    ax_3d  = ifc.createIfcAxis2Placement3D(loc, z3, x3)
    placement = ifc.createIfcLocalPlacement(None, ax_3d)

    # Tạo entity
    guid = ifcopenshell.guid.new()
    kwargs = dict(
        GlobalId=guid, OwnerHistory=None, Name=name,
        Description=None, ObjectType=None,
        ObjectPlacement=placement, Representation=prod_rep,
    )
    if ifc_class == "IfcSlab":
        kwargs["PredefinedType"] = "FLOOR"
    elif ifc_class == "IfcFooting":
        kwargs["PredefinedType"] = "PAD_FOOTING"
    elif ifc_class == "IfcColumn":
        kwargs["PredefinedType"] = "COLUMN"
    elif ifc_class == "IfcBeam":
        kwargs["PredefinedType"] = "BEAM"

    element = ifc.create_entity(ifc_class, **kwargs)

    # Gán vào storey
    ifc.createIfcRelContainedInSpatialStructure(
        ifcopenshell.guid.new(), None, None, None, [element], storey
    )

    # Vật liệu
    mat    = ifc.createIfcMaterial(material_name)
    mat_set = ifc.createIfcMaterialLayerSet([], material_name)
    ifc.createIfcRelAssociatesMaterial(
        ifcopenshell.guid.new(), None, None, None, [element], mat
    )
    return element


def export_pier_ifc(design_data) -> bytes:
    """Xuất model trụ cầu (1 trụ điển hình) ra IFC."""
    if not _HAS_IFC:
        raise RuntimeError("Thiếu thư viện ifcopenshell")

    H_tru  = float(design_data.get("H_tru_est", 5.0))
    bc     = float(design_data.get("bc", 12.0))
    W      = 1.5
    L_tru  = max(2.5, bc * 0.3)
    cap_H  = 0.8
    cap_W  = W + 1.0
    cap_L  = L_tru + 0.5
    base_H = 1.5
    base_W = W + 1.5
    base_L = L_tru + 1.0
    loai_tru = str((design_data.get("tru_result") or {}).get("loai_tru", "Tru dac"))

    ifc, storey, ctx = _new_ifc()

    # Bệ trụ
    _ifc_box(ifc, storey, ctx, -base_L/2, -base_W/2, -base_H,
             base_L, base_W, base_H, "IfcFooting", "Be tru")

    if "2 cot" in loai_tru.lower() or "2 cột" in loai_tru.lower():
        col_sp = L_tru * 0.6
        for i, cx in enumerate([-col_sp/2, col_sp/2]):
            _ifc_box(ifc, storey, ctx, cx - W*0.3, -W/2, 0,
                     W*0.6, W, H_tru, "IfcColumn", f"Cot tru {i+1}")
    else:
        _ifc_box(ifc, storey, ctx, -L_tru/2, -W/2, 0,
                 L_tru, W, H_tru, "IfcColumn", "Than tru")

    # Xà mũ
    _ifc_box(ifc, storey, ctx, -cap_L/2, -cap_W/2, H_tru,
             cap_L, cap_W, cap_H, "IfcBeam", "Xa mu tru")

    import tempfile, os as _os
    with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tf:
        tmp_path = tf.name
    ifc.write(tmp_path)
    data = open(tmp_path, "rb").read()
    _os.unlink(tmp_path)
    return data


# ===========================================================================
# 5. IFC — MODEL KẾT CẤU TOÀN CẦU
# ===========================================================================
def export_bridge_ifc(design_data) -> bytes:
    """
    Xuất model kết cấu toàn cầu (trụ + dầm + bản mặt cầu) ra IFC.
    X = tim cầu (dọc), Y = ngang cầu, Z = thẳng đứng.
    """
    if not _HAS_IFC:
        raise RuntimeError("Thiếu thư viện ifcopenshell")

    geo    = design_data.get("geo_logic", {})
    kcn    = design_data.get("kcn_result") or design_data.get("ai_result", {})
    bc     = float(design_data.get("bc", 12.0))
    H_tru  = float(design_data.get("H_tru_est", 5.0))

    n_nhip   = int(kcn.get("tong_so_nhip", 3))
    L_nhip   = float(kcn.get("chieu_dai", 40))
    H_dam    = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.65))
    kc_dam   = float(kcn.get("khoang_cach_dam", 2.0))
    n_dam    = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
    oh       = float(kcn.get("overhang", 0.5))
    loai_dam = str(kcn.get("loai_dam", "Dam I"))
    L_cau    = float(geo.get("L_cau", n_nhip * L_nhip))
    z_dd     = float(design_data.get("cao_day_dam", H_tru + 5.0))

    W_tru   = 1.5
    L_tru_d = max(2.5, bc * 0.3)
    cap_H   = 0.8;  cap_W = W_tru + 1.0;  cap_L = L_tru_d + 0.5
    base_H  = 1.5;  base_W = W_tru + 1.5; base_L = L_tru_d + 1.0
    t_ban   = 0.20

    ifc, storey, ctx = _new_ifc()

    x0 = -L_cau / 2   # tim mố trái

    # ── Trụ giữa ──
    for i in range(1, n_nhip):
        xt = x0 + i * L_nhip
        z0_tru = z_dd - H_dam - H_tru - cap_H
        _ifc_box(ifc, storey, ctx, xt - base_L/2, -base_W/2, z0_tru - base_H,
                 base_L, base_W, base_H, "IfcFooting", f"Be tru T{i}")
        _ifc_box(ifc, storey, ctx, xt - L_tru_d/2, -W_tru/2, z0_tru,
                 L_tru_d, W_tru, H_tru, "IfcColumn", f"Than tru T{i}")
        _ifc_box(ifc, storey, ctx, xt - cap_L/2, -cap_W/2, z0_tru + H_tru,
                 cap_L, cap_W, cap_H, "IfcBeam", f"Xa mu T{i}")

    # ── Dầm chính ──
    bf = 0.35
    for i_nhip in range(n_nhip):
        xs_nhip = x0 + i_nhip * L_nhip
        y_first = -(bc / 2) + oh
        for i_dam in range(n_dam):
            yd = y_first + i_dam * kc_dam
            _ifc_box(ifc, storey, ctx,
                     xs_nhip, yd - bf/2, z_dd - H_dam,
                     L_nhip, bf, H_dam,
                     "IfcBeam", f"Dam N{i_nhip+1}-D{i_dam+1}",
                     material_name="BTCT DUL")

    # ── Bản mặt cầu ──
    for i_nhip in range(n_nhip):
        xs_nhip = x0 + i_nhip * L_nhip
        _ifc_box(ifc, storey, ctx,
                 xs_nhip, -bc/2, z_dd,
                 L_nhip, bc, t_ban,
                 "IfcSlab", f"Ban mat cau N{i_nhip+1}",
                 material_name="Concrete C40")

    import tempfile, os as _os
    with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tf:
        tmp_path = tf.name
    ifc.write(tmp_path)
    data = open(tmp_path, "rb").read()
    _os.unlink(tmp_path)
    return data


# ===========================================================================
# KIỂM TRA TRẠNG THÁI THƯ VIỆN
# ===========================================================================
def check_libs():
    """Trả về dict trạng thái các thư viện export."""
    return {
        "ezdxf":       _HAS_EZDXF,
        "ifcopenshell": _HAS_IFC,
    }


# ===========================================================================
# CHẠY THỬ ĐỘC LẬP
# ===========================================================================
if __name__ == "__main__":
    import sys, os
    sys.stdout.reconfigure(encoding="utf-8")

    # Dữ liệu mẫu
    sample = {
        "bc": 17.5, "vtk": 100, "loai_duong": "Vượt sông",
        "B": 15.0,  "H": 3.5,
        "MNCN": 3.5, "MNTT": 2.0, "MNTN": 0.5,
        "h_tn_tb": 2.15,
        "H_tru_est": 5.08, "cao_day_dam": 7.5, "cao_mat_cau": 9.5,
        "geo_logic": {
            "L_cau": 120, "x_mo_trai": -60, "x_mo_phai": 60,
            "x_tim_clearance": 0, "y_dinh": 7.5, "y_t": 7.2,
            "x_t1": -40, "x_t2": 40, "R": 5000, "i_val": 0.015,
            "y_mo": 2.5, "y_base_goc": 2.0,
        },
        "kcn_result": {
            "loai_dam": "Dầm I", "chieu_dai": 40.0, "tong_so_nhip": 3,
            "chieu_cao_dam": 1.75, "so_luong_dam": 8, "khoang_cach_dam": 2.0, "overhang": 0.75,
        },
        "tru_result": {"loai_tru": "Khung 2 cột"},
    }

    out = os.path.dirname(os.path.abspath(__file__))

    libs = check_libs()
    print("Thư viện:", libs)

    if libs["ezdxf"]:
        with open(os.path.join(out, "_test_mcn.dxf"), "wb") as f:
            f.write(export_mcn_dxf(sample))
        print("✓ Xuất MCN DXF")

        with open(os.path.join(out, "_test_trac_doc.dxf"), "wb") as f:
            f.write(export_trac_doc_dxf(sample))
        print("✓ Xuất Trắc dọc DXF")

        with open(os.path.join(out, "_test_tru.dxf"), "wb") as f:
            f.write(export_tru_dxf(sample))
        print("✓ Xuất Trụ DXF")

    if libs["ifcopenshell"]:
        with open(os.path.join(out, "_test_pier.ifc"), "wb") as f:
            f.write(export_pier_ifc(sample))
        print("✓ Xuất Pier IFC")

        with open(os.path.join(out, "_test_bridge.ifc"), "wb") as f:
            f.write(export_bridge_ifc(sample))
        print("✓ Xuất Bridge Full IFC")
