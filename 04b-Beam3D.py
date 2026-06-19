"""
Module 04b — Dựng mô hình 3D dầm cầu từ thông số hình học chi tiết
Phụ thuộc: trimesh 4+, shapely 2+, plotly

Hàm xuất công khai:
  rebuild_3D_model_from_params(geo, loai_dam) → dict {mesh, plotly, stats}
  beam_section_polygon(geo, loai_dam)         → shapely.Polygon (mm)
"""

from __future__ import annotations
import math
import numpy as np
import plotly.graph_objects as go

try:
    from shapely.geometry import Polygon
    _HAS_SHAPELY = True
except ImportError:
    _HAS_SHAPELY = False

try:
    import trimesh
    _HAS_TRIMESH = True
except ImportError:
    _HAS_TRIMESH = False

_MM2M = 0.001      # mm → m (trimesh/IFC dùng đơn vị m)
_RHO_CONCRETE = 2.5  # t/m³


# ─────────────────────────────────────────────────────────────────────────────
# Polygon mặt cắt ngang (đơn vị mm, gốc tại đáy, x=0 tim dầm)
# ─────────────────────────────────────────────────────────────────────────────

def _supert_outer(mc: dict, H: int) -> list[tuple]:
    wo  = mc["web_out_hw"]
    haw = mc["B_vat_canh_tren"]
    hf  = mc["B_canh_tren"] / 2
    Hct = mc["H_canh_tren"]
    Hvct= mc["H_vat_canh_tren"]
    ywt = H - Hct - Hvct
    ytb = H - Hct
    return [
        (wo, 0), (wo, ywt), (wo + haw, ytb), (hf, ytb), (hf, H),
        (-hf, H), (-hf, ytb), (-(wo + haw), ytb), (-wo, ywt), (-wo, 0),
    ]


def _supert_void(mc: dict, H: int) -> list[tuple]:
    vit = mc["B_rong_tren"] / 2
    vib = mc["B_rong_duoi"] / 2
    Hcd = mc["H_canh_duoi"]
    Hvcd= mc["H_vat_canh_duoi"]
    Hct = mc["H_canh_tren"]
    Hvct= mc["H_vat_canh_tren"]
    yvb = Hcd + Hvcd
    yvt = H - Hct - Hvct
    return [(-vit, yvt), (vit, yvt), (vib, yvb), (-vib, yvb)]


def _dam_I_outer(mc: dict, H: int) -> list[tuple]:
    Bct = mc["B_canh_tren"] / 2
    Hct = mc["H_canh_tren"]
    Hvct= mc["H_vat_canh_tren"]
    bw  = mc["B_bung"] / 2
    Bcd = mc["B_canh_duoi"] / 2
    Hcd = mc["H_canh_duoi"]
    Hvcd= mc["H_vat_canh_duoi"]
    vat_bot = Hvcd * 2  # taper length
    vat_top = Hvct * 2
    return [
        (-Bcd, 0), (Bcd, 0),
        (Bcd, Hcd - Hvcd), (Bcd - vat_bot, Hcd),
        (bw, Hcd), (bw, H - Hct - Hvct),
        (Bct - vat_top, H - Hct), (Bct, H - Hct),
        (Bct, H), (-Bct, H),
        (-Bct, H - Hct), (-(Bct - vat_top), H - Hct),
        (-bw, H - Hct - Hvct), (-bw, Hcd),
        (-(Bcd - vat_bot), Hcd), (-Bcd, Hcd - Hvcd),
    ]


def _t_nguoc_outer(mc: dict, H: int) -> list[tuple]:
    Bcd = mc["B_canh_duoi"] / 2
    Hcd = mc["H_canh_duoi"]
    Hvcd= mc["H_vat_canh_duoi"]
    bw  = mc["B_bung"] / 2
    return [
        (-Bcd, 0), (Bcd, 0),
        (Bcd, Hcd - Hvcd), (bw, Hcd),
        (bw, H), (-bw, H),
        (-bw, Hcd), (-Bcd + Hvcd * 2, Hcd - Hvcd),
    ]


def _dam_T_outer(mc: dict, H: int) -> list[tuple]:
    Bct = mc["B_canh_tren"] / 2
    Hct = mc["H_canh_tren"]
    Hvct= mc["H_vat_canh_tren"]
    bw  = mc["B_bung"] / 2
    Hbung = mc["H_bung"]
    return [
        (-bw, 0), (bw, 0),
        (bw, Hbung), (bw + Hvct * 2, Hbung + Hvct),
        (Bct, Hbung + Hvct), (Bct, H),
        (-Bct, H), (-Bct, Hbung + Hvct),
        (-(bw + Hvct * 2), Hbung + Hvct), (-bw, Hbung),
    ]


def _ban_rong_outer(geo: dict) -> list[tuple]:
    mc = geo["MC_AA"]
    B  = geo.get("B", mc["B_canh_tren"])
    H  = geo["H"]
    return [(-B / 2, 0), (B / 2, 0), (B / 2, H), (-B / 2, H)]


def _ban_rong_holes(mc: dict) -> list[list[tuple]]:
    D   = mc.get("B_rong", 300)
    n   = mc.get("so_rong", 3)
    kc  = mc.get("kc_rong", 330)
    y0  = mc.get("y_rong", 250)
    r   = D / 2
    N   = 20
    x_start = -(n - 1) * kc / 2
    return [
        [(x_start + i * kc + r * math.cos(2 * math.pi * k / N),
          y0 + r * math.sin(2 * math.pi * k / N))
         for k in range(N)]
        for i in range(n)
    ]


def beam_section_polygon(geo: dict, loai_dam: str):
    """
    Trả về shapely.Polygon mặt cắt A-A (đơn vị mm).
    Trả None nếu thiếu shapely.
    """
    if not _HAS_SHAPELY:
        return None
    mc = geo.get("MC_AA", {})
    H  = geo.get("H", 0)

    if loai_dam == "Super-T":
        outer = _supert_outer(mc, H)
        void  = _supert_void(mc, H)
        return Polygon(outer, [void])
    elif loai_dam == "Dầm I":
        return Polygon(_dam_I_outer(mc, H))
    elif loai_dam == "T ngược":
        return Polygon(_t_nguoc_outer(mc, H))
    elif loai_dam == "Dầm T":
        return Polygon(_dam_T_outer(mc, H))
    elif loai_dam == "Dầm bản rỗng":
        return Polygon(_ban_rong_outer(geo), _ban_rong_holes(mc))
    else:
        outer = _ban_rong_outer(geo)
        return Polygon(outer)


# ─────────────────────────────────────────────────────────────────────────────
# Dựng mesh Trimesh
# ─────────────────────────────────────────────────────────────────────────────

def _scale_poly(poly, s: float):
    """Scale shapely Polygon by factor s (uniform)."""
    from shapely.affinity import scale
    return scale(poly, xfact=s, yfact=s, origin=(0, 0, 0))


def rebuild_3D_model_from_params(geo: dict, loai_dam: str) -> dict:
    """
    Dựng mô hình 3D dầm cầu từ beam_params chi tiết.

    Parameters
    ----------
    geo      : dict — thông số từ get_beam_geometry_detail() / beam_params_final
    loai_dam : str  — "Super-T" | "Dầm I" | "T ngược" | "Dầm T" | "Dầm bản rỗng"

    Returns
    -------
    dict:
        "mesh"   : trimesh.Trimesh hoặc None
        "plotly" : go.Figure — hiển thị 3D trong Streamlit
        "stats"  : dict — diện tích, trọng lượng, thể tích
    """
    mc      = geo.get("MC_AA", {})
    H_mm    = geo.get("H", 1750)
    L_mm    = geo.get("L", 38200)
    L_dau_mm = geo.get("MC_BB", {}).get("L_dau_dac", 750)
    s       = _MM2M

    # ── Section polygon (mm) ──
    section_mm = beam_section_polygon(geo, loai_dam)

    mesh = None
    vol_m3 = 0.0

    if _HAS_TRIMESH and _HAS_SHAPELY and section_mm is not None:
        try:
            section_m = _scale_poly(section_mm, s)
            solid_m   = _scale_poly(Polygon(list(section_mm.exterior.coords)), s) \
                        if loai_dam in ("Super-T", "Dầm bản rỗng") else section_m

            L_m   = L_mm * s
            Ld    = L_dau_mm * s
            L_mid = max(L_m - 2 * Ld, 1e-3)

            end1  = trimesh.creation.extrude_polygon(solid_m, Ld)
            body  = trimesh.creation.extrude_polygon(section_m, L_mid)
            end2  = trimesh.creation.extrude_polygon(solid_m, Ld)

            body.apply_translation([0, 0, Ld])
            end2.apply_translation([0, 0, L_m - Ld])

            mesh = trimesh.util.concatenate([end1, body, end2])
            vol_m3 = float(mesh.volume) if mesh.is_volume else 0.0
        except Exception:
            mesh = None

    # Diện tích và trọng lượng (tính từ Shapely nếu có)
    if _HAS_SHAPELY and section_mm is not None:
        area_m2 = section_mm.area * s * s
    else:
        # Ước lượng từ B × H × tỉ lệ rỗng
        B_m = geo.get("B", 2440) * s
        H_m = H_mm * s
        area_m2 = B_m * H_m * 0.55

    L_m = L_mm * s
    if vol_m3 == 0.0:
        vol_m3 = area_m2 * L_m

    stats = {
        "dien_tich_m2"       : round(area_m2, 4),
        "the_tich_m3"        : round(vol_m3, 3),
        "trong_luong_tan"    : round(vol_m3 * _RHO_CONCRETE, 2),
        "trong_luong_kN_m"   : round(area_m2 * _RHO_CONCRETE * 9.81, 2),
        "LH_ratio"           : round(L_mm / H_mm, 2),
    }

    # ── Plotly figure ──
    fig = _build_plotly_figure(mesh, geo, loai_dam, section_mm)

    return {"mesh": mesh, "plotly": fig, "stats": stats}


def _build_plotly_figure(mesh, geo: dict, loai_dam: str, section_mm) -> go.Figure:
    """Tạo go.Figure 3D từ Trimesh mesh và thêm cáp DUL."""
    mc  = geo.get("MC_AA", {})
    H_m = geo.get("H", 0) * _MM2M
    L_m = geo.get("L", 0) * _MM2M

    traces = []

    # ── Beam mesh ──
    if mesh is not None:
        v, f = mesh.vertices, mesh.faces
        traces.append(go.Mesh3d(
            x=v[:, 0], y=v[:, 1], z=v[:, 2],
            i=f[:, 0], j=f[:, 1], k=f[:, 2],
            color="#c8d6c0", opacity=0.88,
            name=loai_dam, showlegend=True,
            flatshading=True,
            lighting=dict(ambient=0.6, diffuse=0.85, specular=0.1, roughness=0.7),
            lightposition=dict(x=100, y=200, z=300),
        ))
    else:
        # Fallback: box placeholder
        B_m = geo.get("B", 2440) * _MM2M / 2
        traces.append(go.Mesh3d(
            x=[-B_m, B_m, B_m, -B_m, -B_m, B_m, B_m, -B_m],
            y=[0, 0, H_m, H_m, 0, 0, H_m, H_m],
            z=[0, 0, 0, 0, L_m, L_m, L_m, L_m],
            i=[0, 0, 4, 4, 0, 0, 3, 3, 0, 0, 1, 1],
            j=[1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 2, 6],
            k=[2, 3, 6, 7, 5, 4, 6, 7, 7, 4, 6, 5],
            color="#c8d6c0", opacity=0.75,
            name=f"{loai_dam} (xấp xỉ)", showlegend=True,
        ))

    # ── Cáp DUL ──
    cap    = geo.get("cap_DUL", {})
    so_ong = cap.get("so_ong", 0)
    ong_D  = cap.get("ong_PVC_D", 49) * _MM2M
    Hcd    = mc.get("H_canh_duoi", 0) * _MM2M
    Bcd    = mc.get("B_canh_duoi", mc.get("B_bung", 200)) * _MM2M / 2

    if so_ong > 0:
        cols = max(1, min(so_ong, 4))
        rows = math.ceil(so_ong / cols)
        z_arr = np.linspace(0.05 * L_m, 0.95 * L_m, 60)
        idx   = 0
        for r in range(rows):
            for c in range(cols):
                if idx >= so_ong:
                    break
                cx = (c - (cols - 1) / 2) * (Bcd * 1.4 / max(cols, 1))
                cy = Hcd + ong_D * (0.5 + r * 1.8)

                if cap.get("duong_di") == "parabol":
                    sag   = H_m * 0.22
                    y_arr = cy - sag * (4 * (z_arr / L_m) * (1 - z_arr / L_m))
                else:
                    y_arr = np.full_like(z_arr, cy)

                traces.append(go.Scatter3d(
                    x=np.full_like(z_arr, cx), y=y_arr, z=z_arr,
                    mode="lines", line=dict(color="#e74c3c", width=3),
                    name="Cáp DUL" if idx == 0 else None,
                    showlegend=(idx == 0),
                ))
                idx += 1

    L_m_disp = geo.get("L", 0) / 1000.0
    fig = go.Figure(data=traces)
    fig.update_layout(
        scene=dict(
            xaxis_title="Ngang (m)", yaxis_title="Đứng (m)", zaxis_title="Dọc (m)",
            aspectmode="data",
            bgcolor="#f0f4ef",
        ),
        title=dict(
            text=f"Mô hình 3D {loai_dam} — L = {L_m_disp:.1f}m, H = {geo.get('H',0)}mm",
            x=0.5, font=dict(size=13, color="#2c3e50"),
        ),
        margin=dict(l=0, r=0, t=50, b=0),
        paper_bgcolor="white",
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.85)"),
    )
    return fig
