# -*- coding: utf-8 -*-
"""
Module 06d — Beam Dimension Editor
===================================
Widget chỉnh sửa kích thước chi tiết mặt cắt dầm, tích hợp vào THUYẾT MINH
tab của 00-Interface.py.

Hàm xuất:
  render_beam_dim_editor(d, st)   — Render toàn bộ editor (gọi từ Interface)
"""

import importlib.util
import math
from pathlib import Path

import plotly.graph_objects as go

_ROOT = Path(__file__).parent

# ── Lazy-load 06b vẽ mặt cắt ─────────────────────────────────────────────────

_DRAW_MOD = None


def _draw_mod():
    global _DRAW_MOD
    if _DRAW_MOD is None:
        spec = importlib.util.spec_from_file_location(
            "draw_beam", _ROOT / "06b-Draw_Beam_Sections.py"
        )
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _DRAW_MOD = m
    return _DRAW_MOD


# ── Constants ─────────────────────────────────────────────────────────────────

_PA_KEYS   = ["pa1_chi_phi", "pa2_my_quan", "pa3_ai"]
_PA_LABELS = {
    "pa1_chi_phi": "PA1 — Tối ưu chi phí",
    "pa2_my_quan": "PA2 — Tối ưu mỹ quan",
    "pa3_ai":      "PA3 — AI khuyến nghị",
}
_PA_COLORS = {
    "pa1_chi_phi": "#3b82f6",
    "pa2_my_quan": "#8b5cf6",
    "pa3_ai":      "#10b981",
}

_LH_RANGE = {
    "Super-T":       (18, 25),
    "Dầm I":         (16, 22),
    "T ngược":       (10, 15),
    "Dầm bản rỗng":  (12, 18),
    "Dầm T":         (14, 20),
    "Dầm bản":       (12, 18),
}

_SPAN_RANGE = {
    "Super-T":       (25, 50),
    "Dầm I":         (15, 40),
    "T ngược":       (10, 30),
    "Dầm bản rỗng":  (6,  25),
    "Dầm T":         (12, 25),
    "Dầm bản":       (6,  15),
}


# ── Session-state keys (prefix để không xung đột với Interface) ───────────────
_SS_SEL = "_bde_selected_pa"
_SS_ED  = "_bde_edited"


# ── Khởi tạo session state ────────────────────────────────────────────────────

def _init(st):
    st.session_state.setdefault(_SS_SEL, "pa1_chi_phi")
    st.session_state.setdefault(_SS_ED,  {})


# ── Render 3-PA cards ─────────────────────────────────────────────────────────

def _pa_cards(kcn_3_pa: dict, selected_key: str, st):
    cols = st.columns(3)
    for col, pk in zip(cols, _PA_KEYS):
        pa     = kcn_3_pa.get(pk) or {}
        loai   = pa.get("loai_dam",        "—")
        L      = pa.get("chieu_dai",        0)
        H_m    = pa.get("chieu_cao_dam",    0)
        S_m    = pa.get("khoang_cach_dam",  0)
        n_dam  = pa.get("so_luong_dam",     0)
        n_nhip = pa.get("tong_so_nhip",     1)
        lh     = pa.get("ti_le_L_H",        0)
        color  = _PA_COLORS[pk]
        is_sel = (pk == selected_key)
        border = f"3px solid {color}" if is_sel else f"1px solid {color}55"
        bg     = f"{color}14"         if is_sel else "white"
        with col:
            st.markdown(
                f"<div style='border:{border};border-radius:8px;"
                f"padding:10px 14px;background:{bg};min-height:130px'>"
                f"<b style='color:{color};font-size:12px'>{_PA_LABELS[pk]}</b><br>"
                f"<span style='font-size:16px;font-weight:700'>{loai}</span><br>"
                f"L=<b>{L:.1f}m</b> · H=<b>{int(H_m*1000)}mm</b><br>"
                f"S={int(S_m*1000)}mm · n_dầm={n_dam}<br>"
                f"n_nhịp={n_nhip} · L/H={lh:.1f}"
                f"</div>",
                unsafe_allow_html=True,
            )


# ── Dimension editor (number_input cho từng loại dầm) ────────────────────────

def _dim_inputs(st, loai_dam: str, mc: dict, pfx: str):
    """Render number_input fields, return updated mc dict."""
    mc_ed = dict(mc)
    c1, c2, c3 = st.columns(3)

    if loai_dam == "Super-T":
        with c1:
            st.markdown("**Cánh trên**")
            mc_ed["B_canh_tren"]     = st.number_input("B_cánh_trên (mm)",    1000, 3500,
                int(mc.get("B_canh_tren",     2200)), 50, key=f"{pfx}B_ct")
            mc_ed["H_canh_tren"]     = st.number_input("H_cánh_trên (mm)",    100,  400,
                int(mc.get("H_canh_tren",      150)),  5, key=f"{pfx}H_ct")
            mc_ed["B_vat_canh_tren"] = st.number_input("B_vát_trên (mm)",     0,    300,
                int(mc.get("B_vat_canh_tren",  100)),  5, key=f"{pfx}B_vct")
            mc_ed["H_vat_canh_tren"] = st.number_input("H_vát_trên (mm)",     0,    200,
                int(mc.get("H_vat_canh_tren",   75)),  5, key=f"{pfx}H_vct")
        with c2:
            st.markdown("**Bụng + Khoang rỗng**")
            mc_ed["B_bung_top"]  = st.number_input("B_bụng_trên (mm)",  60, 400,
                int(mc.get("B_bung_top",  110)), 5, key=f"{pfx}B_bt")
            mc_ed["B_bung_bot"]  = st.number_input("B_bụng_dưới (mm)", 80, 400,
                int(mc.get("B_bung_bot",  160)), 5, key=f"{pfx}B_bb")
            mc_ed["H_bung"]      = st.number_input("H_bụng (mm)",      300, 3000,
                int(mc.get("H_bung",     1100)), 25, key=f"{pfx}H_bg")
            mc_ed["B_rong_tren"] = st.number_input("B_rỗng_trên (mm)", 100, 1500,
                int(mc.get("B_rong_tren", 800)), 25, key=f"{pfx}B_rt")
            mc_ed["B_rong_duoi"] = st.number_input("B_rỗng_dưới (mm)", 100, 1500,
                int(mc.get("B_rong_duoi", 700)), 25, key=f"{pfx}B_rd")
            mc_ed["H_rong"] = mc_ed["H_bung"]
        with c3:
            st.markdown("**Cánh dưới**")
            mc_ed["B_canh_duoi"]     = st.number_input("B_cánh_dưới (mm)",  400, 2000,
                int(mc.get("B_canh_duoi",   1020)), 25, key=f"{pfx}B_cd")
            mc_ed["H_canh_duoi"]     = st.number_input("H_cánh_dưới (mm)",  100,  500,
                int(mc.get("H_canh_duoi",    225)),  5, key=f"{pfx}H_cd")
            mc_ed["B_vat_canh_duoi"] = st.number_input("B_vát_dưới (mm)",    0,   200,
                int(mc.get("B_vat_canh_duoi", 50)),  5, key=f"{pfx}B_vcd")
            mc_ed["H_vat_canh_duoi"] = st.number_input("H_vát_dưới (mm)",    0,   200,
                int(mc.get("H_vat_canh_duoi", 50)),  5, key=f"{pfx}H_vcd")

    elif loai_dam in ("Dầm I", "Dầm T"):
        with c1:
            st.markdown("**Cánh trên**")
            mc_ed["B_canh_tren"]     = st.number_input("B_cánh_trên (mm)",  150, 1500,
                int(mc.get("B_canh_tren",    650)), 25, key=f"{pfx}B_ct")
            mc_ed["H_canh_tren"]     = st.number_input("H_cánh_trên (mm)",   80,  400,
                int(mc.get("H_canh_tren",    150)),  5, key=f"{pfx}H_ct")
            mc_ed["B_vat_canh_tren"] = st.number_input("B_vát_trên (mm)",     0,  150,
                int(mc.get("B_vat_canh_tren", 50)),  5, key=f"{pfx}B_vct")
            mc_ed["H_vat_canh_tren"] = st.number_input("H_vát_trên (mm)",     0,  150,
                int(mc.get("H_vat_canh_tren", 50)),  5, key=f"{pfx}H_vct")
        with c2:
            st.markdown("**Bụng**")
            mc_ed["B_bung"]  = st.number_input("B_bụng (mm)",  80, 600,
                int(mc.get("B_bung", mc.get("B_bung_top", 200))), 5, key=f"{pfx}B_bg")
            mc_ed["H_bung"]  = st.number_input("H_bụng (mm)", 200, 3000,
                int(mc.get("H_bung", 900)), 25, key=f"{pfx}H_bg")
            mc_ed["B_bung_top"] = mc_ed["B_bung"]
            mc_ed["B_bung_bot"] = mc_ed["B_bung"]
        with c3:
            st.markdown("**Cánh dưới**")
            mc_ed["B_canh_duoi"]     = st.number_input("B_cánh_dưới (mm)",   80, 1500,
                int(mc.get("B_canh_duoi",    650)), 25, key=f"{pfx}B_cd")
            mc_ed["H_canh_duoi"]     = st.number_input("H_cánh_dưới (mm)",   80,  400,
                int(mc.get("H_canh_duoi",    150)),  5, key=f"{pfx}H_cd")
            mc_ed["B_vat_canh_duoi"] = st.number_input("B_vát_dưới (mm)",     0,  150,
                int(mc.get("B_vat_canh_duoi", 50)),  5, key=f"{pfx}B_vcd")
            mc_ed["H_vat_canh_duoi"] = st.number_input("H_vát_dưới (mm)",     0,  150,
                int(mc.get("H_vat_canh_duoi", 50)),  5, key=f"{pfx}H_vcd")

    elif loai_dam == "T ngược":
        with c1:
            st.markdown("**Bụng (phần trên)**")
            mc_ed["B_canh_tren"] = st.number_input("B_bụng (mm)", 100, 500,
                int(mc.get("B_canh_tren", mc.get("B_bung", 200))), 10, key=f"{pfx}B_ct")
            mc_ed["H_canh_tren"] = st.number_input("H_bụng (mm)", 100, 2500,
                int(mc.get("H_canh_tren", mc.get("H_bung", 350))), 25, key=f"{pfx}H_ct")
            mc_ed["B_bung"] = mc_ed["B_canh_tren"]
            mc_ed["H_bung"] = mc_ed["H_canh_tren"]
        with c2:
            st.markdown("**Cánh dưới (rộng)**")
            mc_ed["B_canh_duoi"]     = st.number_input("B_cánh_dưới (mm)", 500, 2000,
                int(mc.get("B_canh_duoi", 980)), 25, key=f"{pfx}B_cd")
            mc_ed["H_canh_duoi"]     = st.number_input("H_cánh_dưới (mm)",  80,  400,
                int(mc.get("H_canh_duoi", 200)),  5, key=f"{pfx}H_cd")
            mc_ed["B_vat_canh_duoi"] = st.number_input("B_vát_dưới (mm)",    0,  100,
                int(mc.get("B_vat_canh_duoi", 30)), 5, key=f"{pfx}B_vcd")
            mc_ed["H_vat_canh_duoi"] = st.number_input("H_vát_dưới (mm)",    0,  100,
                int(mc.get("H_vat_canh_duoi", 30)), 5, key=f"{pfx}H_vcd")

    elif loai_dam in ("Dầm bản rỗng", "Dầm bản"):
        with c1:
            mc_ed["B_canh_tren"] = st.number_input("Bề rộng bản B (mm)", 500, 2000,
                int(mc.get("B_canh_tren", 1000)), 25, key=f"{pfx}B_ct")
        with c2:
            mc_ed["so_rong"] = int(st.number_input("Số lỗ rỗng", 1, 10,
                int(mc.get("so_rong", mc.get("n_rong", 3))), 1, key=f"{pfx}n_rong"))
            mc_ed["B_rong"]  = st.number_input("Đường kính lỗ (mm)", 100, 600,
                int(mc.get("B_rong", mc.get("duong_kinh_rong", 300))), 25, key=f"{pfx}D_rong")

    return mc_ed


# ── Thông số tổng quát (L, H, S, n_dam) ──────────────────────────────────────

def _general_inputs(st, H_cur: int, L_cur: int, S_cur: int, n_dam_cur: int,
                    loai_dam: str, pfx: str):
    st.markdown("---")
    st.markdown("**📐 Thông số tổng quát nhịp (mm)**")
    g1, g2, g3, g4 = st.columns(4)
    with g1:
        H_new = st.number_input("Chiều cao H", 200, 5000, H_cur, 25, key=f"{pfx}H_tot")
    with g2:
        L_new = st.number_input("Chiều dài L", 5000, 60000, L_cur, 200, key=f"{pfx}L_tot")
    with g3:
        S_new = st.number_input("Khoảng cách S", 500, 4000, S_cur, 50, key=f"{pfx}S_tot")
    with g4:
        n_new = int(st.number_input("Số dầm/MCN", 2, 20, n_dam_cur, 1, key=f"{pfx}n_dam"))

    LH = L_new / H_new if H_new else 0
    lo, hi = _LH_RANGE.get(loai_dam, (12, 22))
    if lo <= LH <= hi:
        st.success(f"✅ L/H = {LH:.1f} — Đạt [{lo}–{hi}] TCVN 11823")
    elif LH < lo:
        st.info(f"ℹ️ L/H = {LH:.1f} < {lo} — Dầm hơi nặng, có thể giảm H")
    else:
        st.warning(f"⚠️ L/H = {LH:.1f} > {hi} — Kiểm tra độ võng")

    return int(H_new), int(L_new), int(S_new), n_new


# ── Ước tính diện tích tiết diện ─────────────────────────────────────────────

def _area(loai_dam: str, mc: dict, H_mm: float) -> float:
    if loai_dam == "Super-T":
        B_ct = mc.get("B_canh_tren",  2200); H_ct = mc.get("H_canh_tren",   150)
        bw   = (mc.get("B_bung_top", 110) + mc.get("B_bung_bot", 160)) / 2
        H_b  = mc.get("H_bung",      1100)
        B_cd = mc.get("B_canh_duoi", 1020); H_cd = mc.get("H_canh_duoi",   225)
        void = (mc.get("B_rong_tren", 800) + mc.get("B_rong_duoi", 700)) / 2 * H_b
        return max(0, B_ct*H_ct + bw*H_b + B_cd*H_cd - void) / 1e6
    elif loai_dam in ("Dầm I", "Dầm T"):
        B_ct = mc.get("B_canh_tren", 650); H_ct = mc.get("H_canh_tren", 150)
        bw   = mc.get("B_bung",      200); H_b  = mc.get("H_bung",      900)
        B_cd = mc.get("B_canh_duoi", 650); H_cd = mc.get("H_canh_duoi", 150)
        return (B_ct*H_ct + bw*H_b + B_cd*H_cd) / 1e6
    elif loai_dam == "T ngược":
        B_w  = mc.get("B_canh_tren", 200); H_w  = mc.get("H_canh_tren", 350)
        B_cd = mc.get("B_canh_duoi", 980); H_cd = mc.get("H_canh_duoi", 200)
        return (B_w*H_w + B_cd*H_cd) / 1e6
    else:
        B = mc.get("B_canh_tren", H_mm / 2)
        n = int(mc.get("so_rong", 3)); D = mc.get("B_rong", 300)
        return max(0, B*H_mm - n * math.pi * (D/2)**2) / 1e6


# ── Xây dựng geo dict để truyền cho 06b ──────────────────────────────────────

def _build_geo(geo_base: dict, mc_ed: dict, H_new: int, L_new: int, S_new: int) -> dict:
    """Trả về geo dict cập nhật để vẽ mặt cắt."""
    geo = dict(geo_base)
    geo["H"]    = H_new
    geo["L"]    = L_new
    geo["S"]    = S_new
    geo["MC_AA"] = mc_ed
    return geo


# ── Hàm chính xuất ra ngoài ───────────────────────────────────────────────────

def render_beam_dim_editor(d: dict, st) -> None:
    """
    Render widget chỉnh sửa kích thước chi tiết dầm.

    Parameters
    ----------
    d  : dict — st.session_state.design_data
    st : module streamlit
    """
    _init(st)

    kcn_3_pa = d.get("kcn_3_pa")
    kcn_flat = d.get("kcn_result")  # flat dict (PA1 hoặc cũ)

    # ── Nếu chưa chạy AI ──────────────────────────────────────────────────────
    if not kcn_3_pa and not kcn_flat:
        st.info("⏳ Chạy pipeline AI trước để có kết quả kết cấu nhịp.")
        return

    # ── Xây dựng 3 PA fake nếu chỉ có flat result ────────────────────────────
    if not kcn_3_pa:
        # Tạo 3-PA wrapper từ kcn_flat (backward compat)
        kcn_3_pa = {
            "pa1_chi_phi": dict(kcn_flat),
            "pa2_my_quan": dict(kcn_flat),
            "pa3_ai":      dict(kcn_flat),
        }

    # ── Selector PA ───────────────────────────────────────────────────────────
    _pa_cards(kcn_3_pa, st.session_state[_SS_SEL], st)

    sel = st.radio(
        "Chọn phương án:",
        options=_PA_KEYS,
        format_func=lambda k: _PA_LABELS[k],
        horizontal=True,
        index=_PA_KEYS.index(st.session_state[_SS_SEL]),
        key="_bde_pa_radio",
    )
    if sel != st.session_state[_SS_SEL]:
        st.session_state[_SS_SEL] = sel
        st.session_state[_SS_ED]  = {}
        st.rerun()

    pa       = kcn_3_pa[st.session_state[_SS_SEL]]
    loai_dam = pa.get("loai_dam", "Super-T")

    # Lấy geometry_detail từ PA (đã có nếu chạy với predict_kcn v2)
    geo_base = pa.get("geometry_detail") or {}
    mc_base  = geo_base.get("MC_AA") or {}
    H_base   = int(geo_base.get("H") or pa.get("chieu_cao_dam", 1.75) * 1000)
    L_base   = int(geo_base.get("L") or pa.get("chieu_dai",     38.2) * 1000)
    S_base   = int(geo_base.get("S") or pa.get("khoang_cach_dam", 2.2) * 1000)
    ndam_base = int(pa.get("so_luong_dam", 6))

    ep = st.session_state.get(_SS_ED) or {}
    mc_cur    = ep.get("MC_AA",  mc_base)
    H_cur     = ep.get("H",      H_base)
    L_cur     = ep.get("L",      L_base)
    S_cur     = ep.get("S",      S_base)
    ndam_cur  = ep.get("n_dam",  ndam_base)

    # Kiểm tra span range
    L_m = L_cur / 1000
    lo_sp, hi_sp = _SPAN_RANGE.get(loai_dam, (5, 100))
    if L_m > hi_sp:
        st.error(f"❌ L = {L_m:.1f}m > {hi_sp}m — Vượt phạm vi của {loai_dam}")
    elif L_m < lo_sp:
        st.warning(f"⚠️ L = {L_m:.1f}m < {lo_sp}m — Nhịp ngắn hơn khuyến nghị của {loai_dam}")

    # ── Editor + Preview ───────────────────────────────────────────────────────
    st.markdown(f"**Loại dầm: {loai_dam}**")
    pfx = "_bde_"
    ed_col, draw_col = st.columns([5, 4], gap="large")

    with ed_col:
        st.markdown("#### ✏️ Kích thước mặt cắt A-A (mm)")
        mc_ed = _dim_inputs(st, loai_dam, mc_cur, pfx)
        H_new, L_new, S_new, ndam_new = _general_inputs(
            st, H_cur, L_cur, S_cur, ndam_cur, loai_dam, pfx
        )

    with draw_col:
        st.markdown("#### 📐 Bản vẽ mặt cắt A-A (live)")
        try:
            draw = _draw_mod()
            geo_upd = _build_geo(geo_base, mc_ed, H_new, L_new, S_new)
            fig = draw.draw_beam_section(loai_dam, geo_upd, "AA")
            if fig:
                fig.update_layout(height=420, margin=dict(l=40, r=40, t=45, b=30))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"Chưa có bản vẽ cho {loai_dam}")
        except Exception as exc:
            st.warning(f"Lỗi vẽ mặt cắt: {exc}")

        A  = _area(loai_dam, mc_ed, H_new)
        m1, m2, m3 = st.columns(3)
        m1.metric("A tiết diện", f"{A:.4f} m²")
        m2.metric("I sơ bộ", f"{A*(H_new/1000)**2/12:.5f} m⁴")
        m3.metric("Khối lượng/m", f"{A*2500:.0f} kg/m")

    # ── Nút Lưu ───────────────────────────────────────────────────────────────
    st.markdown("---")
    b1, b2, b3 = st.columns([3, 3, 4])

    with b1:
        if st.button("✅ Xác nhận & Lưu thông số dầm", type="primary",
                     use_container_width=True, key="_bde_save"):
            beam_final = {
                "loai_dam":     loai_dam,
                "L":            L_new,
                "H":            H_new,
                "B":            int(mc_ed.get("B_canh_tren", H_new // 2)),
                "S":            S_new,
                "n_dam":        ndam_new,
                "overhang":     pa.get("overhang", 0.5),
                "tong_so_nhip": int(pa.get("tong_so_nhip", 1)),
                "cong_nghe":    pa.get("cong_nghe", "DUL_sau"),
                "phuong_phap":  pa.get("phuong_phap", ""),
                "MC_AA":        mc_ed,
                "cap_DUL":      geo_base.get("cap_DUL", {}),
            }
            d["beam_params_final"] = beam_final
            # Cập nhật kcn_result flat để các module khác không bị lỗi
            d["kcn_result"] = {
                "loai_dam":        loai_dam,
                "chieu_dai":       round(L_new / 1000, 2),
                "chieu_cao_dam":   round(H_new / 1000, 3),
                "be_rong_dam":     round(mc_ed.get("B_canh_tren", H_new/2) / 1000, 3),
                "khoang_cach_dam": round(S_new / 1000, 3),
                "so_luong_dam":    ndam_new,
                "tong_so_nhip":    int(pa.get("tong_so_nhip", 1)),
                "overhang":        pa.get("overhang", 0.5),
                "ti_le_L_H":       round(L_new / H_new, 2) if H_new else 0,
                "cong_nghe":       pa.get("cong_nghe", "DUL_sau"),
                "phuong_phap":     pa.get("phuong_phap", ""),
                "ghi_chu":         f"Đã chỉnh sửa thủ công từ {_PA_LABELS[st.session_state[_SS_SEL]]}",
                "do_tin_cay":      d.get("kcn_result", {}).get("do_tin_cay", 80),
            }
            st.session_state[_SS_ED] = {
                "MC_AA": mc_ed, "H": H_new, "L": L_new,
                "S": S_new, "n_dam": ndam_new,
            }
            st.success(
                f"✅ Đã lưu **{loai_dam}** — "
                f"L={L_new/1000:.2f}m, H={H_new}mm, "
                f"S={S_new}mm, n_dam={ndam_new}"
            )
            st.balloons()

    with b2:
        if st.button("↩️ Reset về AI gợi ý", use_container_width=True, key="_bde_reset"):
            st.session_state[_SS_ED] = {}
            st.rerun()

    with b3:
        saved = d.get("beam_params_final")
        if saved:
            st.info(
                f"**Đã lưu:** {saved.get('loai_dam','?')} "
                f"L={saved.get('L',0)/1000:.1f}m "
                f"H={saved.get('H',0)}mm "
                f"n={saved.get('n_dam','?')}"
            )
        else:
            st.caption("Chưa lưu kích thước chi tiết.")
