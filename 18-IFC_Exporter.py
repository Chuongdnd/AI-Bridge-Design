"""
18-IFC_Exporter.py
Xuất BeamModel → IFC2X3 có thể mở trực tiếp trong Revit
(File → Open → IFC → chọn file .ifc)
Dùng IFC2X3 vì Revit chỉ hỗ trợ Open IFC đầy đủ với schema này;
IFC4 chỉ hỗ trợ qua Link IFC.

Yêu cầu: pip install ifcopenshell
"""
from __future__ import annotations
import math
import uuid
import time
import numpy as np
from typing import List, Tuple

try:
    import ifcopenshell
    import ifcopenshell.api
    import ifcopenshell.api.root
    import ifcopenshell.api.unit
    import ifcopenshell.api.context
    import ifcopenshell.api.geometry
    import ifcopenshell.api.spatial
    import ifcopenshell.api.aggregate
    HAS_IFC = True
except ImportError:
    HAS_IFC = False


# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════

def _new_guid() -> str:
    return ifcopenshell.guid.compress(uuid.uuid4().hex)


def _clean_ring2d(pts, tol: float = 0.05) -> list:
    """
    Làm sạch vòng 2D [x,z] trước khi triangulate:
    - Loại bỏ điểm trùng liên tiếp
    - Loại bỏ điểm cuối trùng với điểm đầu (closed polygon)
    """
    if not pts:
        return pts
    result = [list(pts[0])]
    for p in pts[1:]:
        if abs(p[0] - result[-1][0]) > tol or abs(p[1] - result[-1][1]) > tol:
            result.append(list(p))
    # Remove closing duplicate
    while (len(result) > 1
           and abs(result[-1][0] - result[0][0]) < tol
           and abs(result[-1][1] - result[0][1]) < tol):
        result.pop()
    return result


def _face_degenerate(verts: list, face: list, tol: float = 0.05) -> bool:
    """True nếu mặt tam giác có 2 đỉnh trùng vị trí (zero-area face)."""
    pts = [verts[i] for i in face]
    for a in range(len(pts)):
        for b in range(a + 1, len(pts)):
            pa, pb = pts[a], pts[b]
            if (abs(pa[0]-pb[0]) < tol
                    and abs(pa[1]-pb[1]) < tol
                    and abs(pa[2]-pb[2]) < tol):
                return True
    return False


def _loft_cross_sections(
    sec_from: list,   # [[x,z], ...] mm
    sec_to:   list,   # [[x,z], ...] mm
    length:   float,  # mm, dọc theo Y
    n_steps:  int = 6,
) -> Tuple[List, List]:
    """
    Nội suy tuyến tính giữa 2 mặt cắt theo chiều dài.
    Trả về (vertices, faces) để tạo IfcFacetedBrep.
    vertices: list of (x, y, z) mm
    faces:    list of [i0, i1, i2] (triangles, index vào vertices)
    """
    # Deduplicate both rings before use
    from_pts = _clean_ring2d(sec_from)
    to_pts   = _clean_ring2d(sec_to)
    n = min(len(from_pts), len(to_pts))
    if n < 3:
        return [], []

    verts: List = []
    faces: List = []

    rings = []
    for step in range(n_steps + 1):
        t = step / n_steps
        y = t * length
        ring = []
        for i in range(n):
            x = from_pts[i][0] * (1 - t) + to_pts[i][0] * t
            z = from_pts[i][1] * (1 - t) + to_pts[i][1] * t
            ring.append(len(verts))
            verts.append((x, y, z))
        rings.append(ring)

    # Side faces (quads split into 2 triangles)
    for s in range(n_steps):
        r0 = rings[s]
        r1 = rings[s + 1]
        for i in range(n):
            j = (i + 1) % n
            faces.append([r0[i], r0[j], r1[j]])
            faces.append([r0[i], r1[j], r1[i]])

    # Start cap — centroid fan, normal points toward -Y
    r_start = rings[0]
    cx_s = sum(verts[i][0] for i in r_start) / n
    cz_s = sum(verts[i][2] for i in r_start) / n
    verts.append((cx_s, 0.0, cz_s))
    ci_s = len(verts) - 1
    for i in range(n):
        j = (i + 1) % n
        faces.append([ci_s, r_start[j], r_start[i]])

    # End cap — centroid fan, normal points toward +Y
    r_end = rings[-1]
    cx_e = sum(verts[i][0] for i in r_end) / n
    cz_e = sum(verts[i][2] for i in r_end) / n
    verts.append((cx_e, length, cz_e))
    ci_e = len(verts) - 1
    for i in range(n):
        j = (i + 1) % n
        faces.append([ci_e, r_end[i], r_end[j]])

    # Remove any zero-area (degenerate) triangles
    faces = [f for f in faces if not _face_degenerate(verts, f)]

    return verts, faces


def _extrude_section(
    outer: list,   # [[x,z], ...] mm
    holes: list,   # [[[x,z],...], ...]
    length: float, # mm, theo Y
) -> Tuple[List, List]:
    """Constant section: extrude theo Y."""
    return _loft_cross_sections(outer, outer, length, n_steps=1)


def _make_faceted_brep(ifc_file, verts, faces, context):
    """
    Tạo IfcFacetedBrep từ danh sách đỉnh và mặt.
    Geometry format Revit hiểu khi mở trực tiếp.
    """
    ifc_verts = [
        ifc_file.createIfcCartesianPoint([float(v[0]), float(v[1]), float(v[2])])
        for v in verts
    ]

    ifc_faces = []
    for f in faces:
        if len(f) < 3:
            continue
        pts = [ifc_verts[i] for i in f]
        loop = ifc_file.createIfcPolyLoop(pts)
        bound = ifc_file.createIfcFaceOuterBound(loop, True)
        ifc_faces.append(ifc_file.createIfcFace([bound]))

    if not ifc_faces:
        return None

    shell = ifc_file.createIfcClosedShell(ifc_faces)
    return ifc_file.createIfcFacetedBrep(shell)


def _placement(ifc_file, x=0.0, y=0.0, z=0.0,
               axis=(0, 0, 1), ref_dir=(1, 0, 0)):
    """Tạo IfcLocalPlacement."""
    origin = ifc_file.createIfcCartesianPoint([float(x), float(y), float(z)])
    ax     = ifc_file.createIfcDirection([float(v) for v in axis])
    ref    = ifc_file.createIfcDirection([float(v) for v in ref_dir])
    ax2    = ifc_file.createIfcAxis2Placement3D(origin, ax, ref)
    return ifc_file.createIfcLocalPlacement(None, ax2)


# ══════════════════════════════════════════════════════════
# MAIN EXPORT FUNCTION
# ══════════════════════════════════════════════════════════

def export_beam_to_ifc(
    beam_model,
    design_data: dict,
    filename: str = "dam_supert.ifc",
    author:   str = "UTH Bridge AI",
    project_name: str = "Cầu Super-T",
) -> bytes:
    """
    Xuất BeamModel → IFC2X3 bytes có thể mở trực tiếp trong Revit.

    Params
    ------
    beam_model  : BeamBuilder.BeamModel (đã có sections + segments)
    design_data : design_data dict từ session_state
    filename    : tên file (chỉ dùng cho metadata)
    author      : tên tác giả
    project_name: tên dự án

    Returns
    -------
    bytes: nội dung file IFC (UTF-8 encoded)
    """
    if not HAS_IFC:
        raise ImportError(
            "ifcopenshell chưa được cài. "
            "Chạy: pip install ifcopenshell"
        )

    import sys
    bb = sys.modules.get("BeamBuilder")
    if bb is None:
        raise RuntimeError("BeamBuilder module chưa được load.")

    # ── 1. Tạo file IFC2X3 (Revit hỗ trợ Open IFC đầy đủ với IFC2X3) ──
    ifc_file = ifcopenshell.file(schema="IFC2X3")

    # ── 2. IfcOwnerHistory ───────────────────────────────────────────
    person  = ifc_file.createIfcPerson(
        None, "UTH", "Bridge AI", None, None, None, None, None)
    org     = ifc_file.createIfcOrganization(
        None, "UTH", "University of Transport and Communications",
        None, None)
    p_and_o = ifc_file.createIfcPersonAndOrganization(person, org, None)
    app     = ifc_file.createIfcApplication(
        org, "1.0", "UTH Bridge AI System", "UTH-AI")
    ts      = int(time.time())
    owner_hist = ifc_file.createIfcOwnerHistory(
        p_and_o, app, "READWRITE", "ADDED", None, None, None, ts)

    # ── 3. Units (mm) ────────────────────────────────────────────────
    mm_unit  = ifc_file.createIfcSIUnit(None, "LENGTHUNIT", "MILLI", "METRE")
    deg_unit = ifc_file.createIfcSIUnit(None, "PLANEANGLEUNIT", None, "RADIAN")
    unit_assign = ifc_file.createIfcUnitAssignment([mm_unit, deg_unit])

    # ── 4. Geometric context ─────────────────────────────────────────
    world_origin = ifc_file.createIfcCartesianPoint([0.0, 0.0, 0.0])
    world_ax     = ifc_file.createIfcAxis2Placement3D(
        world_origin,
        ifc_file.createIfcDirection([0.0, 0.0, 1.0]),
        ifc_file.createIfcDirection([1.0, 0.0, 0.0]),
    )
    ctx = ifc_file.createIfcGeometricRepresentationContext(
        "Model", "Model", 3, 1.0e-5, world_ax, None)
    body_ctx = ifc_file.createIfcGeometricRepresentationSubContext(
        "Body", "Model", None, None, None, None, ctx,
        None, "MODEL_VIEW", None)

    # ── 5. IfcProject ────────────────────────────────────────────────
    project = ifc_file.createIfcProject(
        _new_guid(), owner_hist, project_name,
        None, None, None, None, [ctx], unit_assign)

    # ── 6. IfcSite ───────────────────────────────────────────────────
    site_plc = _placement(ifc_file)
    site = ifc_file.createIfcSite(
        _new_guid(), owner_hist, "Site", None, None,
        site_plc, None, None, "ELEMENT", None, None, None, None, None)
    ifc_file.createIfcRelAggregates(
        _new_guid(), owner_hist, None, None, project, [site])

    # ── 7. IfcBuilding ───────────────────────────────────────────────
    bldg_plc = _placement(ifc_file)
    bldg = ifc_file.createIfcBuilding(
        _new_guid(), owner_hist, project_name, None, None,
        bldg_plc, None, None, "ELEMENT", None, None, None)
    ifc_file.createIfcRelAggregates(
        _new_guid(), owner_hist, None, None, site, [bldg])

    # ── 8. IfcBuildingStorey (cao độ đáy dầm) ────────────────────────
    cao_dd     = float(design_data.get("cao_day_dam", 0.0)) * 1000  # m→mm
    storey_plc = _placement(ifc_file, z=cao_dd)
    storey = ifc_file.createIfcBuildingStorey(
        _new_guid(), owner_hist, "Cao độ đáy dầm",
        None, None, storey_plc, None, None, "ELEMENT", cao_dd)
    ifc_file.createIfcRelAggregates(
        _new_guid(), owner_hist, None, None, bldg, [storey])

    # ── 9. Lấy thông số kỹ thuật (chỉ dùng cho PropertySet) ─────────
    kcn    = design_data.get("kcn_result") or design_data.get("ai_result", {})
    n_nhip = int(kcn.get("tong_so_nhip", 3))
    L_nhip = float(kcn.get("chieu_dai",   38.0))   # m (metadata)
    n_dam  = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
    kc_dam = float(kcn.get("khoang_cach_dam", 2.2)) * 1000  # m→mm (metadata)

    # ── 10. Tính segments geometry ───────────────────────────────────
    secs   = beam_model.sections
    segs   = beam_model.segments
    mirror = beam_model.mirror
    L_full = float(beam_model.length)   # mm (full beam)

    fixed  = sum(
        float(s.length) for s in segs if s.length != "fill")
    fills  = sum(1 for s in segs if s.length == "fill")
    half   = L_full / (2.0 if mirror else 1.0)
    fill_l = max(0.0, (half - fixed) / fills) if fills else 0.0

    # ── 11. Tạo 1 IfcBeam đơn tại gốc tọa độ ───────────────────────
    # Tab Chi tiết SPT chỉ cần 1 dầm để kiểm tra geometry trong Revit.

    def _get_outer(sec_name):
        s = secs.get(sec_name)
        return s.outer if s and s.outer else []

    # Expand mirror
    seg_list = list(segs)
    if mirror:
        seg_list = seg_list + [
            type('_S', (), {
                'type':     sg.type,
                'section':  getattr(sg, 'section',  None),
                'from_sec': getattr(sg, 'to_sec',   None),
                'to_sec':   getattr(sg, 'from_sec', None),
                'length':   sg.length,
            })()
            for sg in reversed(segs)
        ]

    all_verts: List = []
    all_faces: List = []
    y_cursor = 0.0

    for seg in seg_list:
        slen = fill_l if seg.length == "fill" else float(seg.length)
        if slen <= 0:
            continue

        if seg.type == "constant":
            outer = _get_outer(seg.section)
            if not outer:
                y_cursor += slen
                continue
            v, f = _extrude_section(outer, [], slen)
        else:
            outer_f = _get_outer(seg.from_sec)
            outer_t = _get_outer(seg.to_sec)
            if not outer_f and not outer_t:
                y_cursor += slen
                continue
            outer_f = outer_f or outer_t
            outer_t = outer_t or outer_f
            v, f = _loft_cross_sections(outer_f, outer_t, slen)

        offset_v = [(vx, vy + y_cursor, vz) for vx, vy, vz in v]
        offset_f = [[fi + len(all_verts) for fi in face] for face in f]
        all_verts.extend(offset_v)
        all_faces.extend(offset_f)
        y_cursor += slen

    beam_elements = []

    if all_verts and all_faces:
        brep = _make_faceted_brep(ifc_file, all_verts, all_faces, body_ctx)
        if brep is not None:
            shape_rep = ifc_file.createIfcShapeRepresentation(
                body_ctx, "Body", "Brep", [brep])
            prod_def = ifc_file.createIfcProductDefinitionShape(
                None, None, [shape_rep])

            # Đặt dầm tại gốc tọa độ (0, 0, 0) tương đối với storey
            _plc_ax2 = ifc_file.createIfcAxis2Placement3D(
                ifc_file.createIfcCartesianPoint([0.0, 0.0, 0.0]),
                ifc_file.createIfcDirection([0.0, 0.0, 1.0]),
                ifc_file.createIfcDirection([1.0, 0.0, 0.0]),
            )
            beam_plc = ifc_file.createIfcLocalPlacement(storey_plc, _plc_ax2)

            beam_el = ifc_file.createIfcBeam(
                _new_guid(), owner_hist,
                "Dam_Super_T",
                f"Super-T L={L_nhip:.1f}m H={kcn.get('chieu_cao_dam',1.75)*1000:.0f}mm",
                None, beam_plc, prod_def, None,
            )
            beam_elements.append(beam_el)

            beam_type = ifc_file.createIfcBeamType(
                _new_guid(), owner_hist,
                "Super-T",
                f"H={kcn.get('chieu_cao_dam', 1.75)*1000:.0f}mm",
                None, None, None, None, None, "BEAM",
            )
            ifc_file.createIfcRelDefinesByType(
                _new_guid(), owner_hist, None, None,
                [beam_el], beam_type)

    # ── 12. Gán tất cả dầm vào storey ───────────────────────────────
    if beam_elements:
        ifc_file.createIfcRelContainedInSpatialStructure(
            _new_guid(), owner_hist,
            "Dam Super-T", None,
            beam_elements, storey,
        )

    # ── 13. IfcPropertySet — thông số kỹ thuật ───────────────────────
    if beam_elements:
        props = [
            ifc_file.createIfcPropertySingleValue(
                "L_nhip_mm", None,
                ifc_file.createIfcReal(L_nhip * 1000), None),   # m→mm
            ifc_file.createIfcPropertySingleValue(
                "H_dam_mm", None,
                ifc_file.createIfcReal(
                    float(kcn.get("chieu_cao_dam", 1.75)) * 1000), None),
            ifc_file.createIfcPropertySingleValue(
                "Loai_dam", None,
                ifc_file.createIfcText(
                    str(kcn.get("loai_dam", "Super-T"))), None),
            ifc_file.createIfcPropertySingleValue(
                "So_nhip_thiet_ke", None,
                ifc_file.createIfcInteger(n_nhip), None),
            ifc_file.createIfcPropertySingleValue(
                "So_dam_tren_MCN", None,
                ifc_file.createIfcInteger(n_dam), None),
            ifc_file.createIfcPropertySingleValue(
                "Khoang_cach_dam_mm", None,
                ifc_file.createIfcReal(kc_dam), None),
            ifc_file.createIfcPropertySingleValue(
                "Cao_do_day_dam_m", None,
                ifc_file.createIfcReal(
                    float(design_data.get("cao_day_dam", 0))), None),
        ]
        pset = ifc_file.createIfcPropertySet(
            _new_guid(), owner_hist,
            "UTH_BridgeBeamProperties", None, props)
        ifc_file.createIfcRelDefinesByProperties(
            _new_guid(), owner_hist, None, None,
            beam_elements, pset)

    # ── 14. Xuất ra bytes ────────────────────────────────────────────
    # ifcopenshell.write() chỉ nhận file path, không nhận StringIO
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as _tmp:
        _tmp_path = _tmp.name
    try:
        ifc_file.write(_tmp_path)
        with open(_tmp_path, "rb") as _f:
            return _f.read()
    finally:
        try:
            os.unlink(_tmp_path)
        except OSError:
            pass


def check_ifcopenshell() -> tuple[bool, str]:
    """Kiểm tra ifcopenshell có sẵn không. Trả về (ok, message)."""
    if not HAS_IFC:
        return False, (
            "ifcopenshell chua duoc cai.\n"
            "Chay lenh: pip install ifcopenshell\n"
            "Sau do restart app."
        )
    try:
        v = ifcopenshell.version
        return True, f"ifcopenshell {v} — san sang"
    except Exception as e:
        return False, f"ifcopenshell loi: {e}"
