"""
Module 09 — So sanh 3 Phuong An
==========================================
Khi Module 06 da sinh kcn_3_pa (truyen qua tham so kcn_3_pa), dashboard so
sanh dung DUNG 3 phuong an cua he thong:
  PA1 — Toi uu chi phi   (nhom dam KHONG ban day lien mach)
  PA2 — Toi uu my quan   (nhom dam CO ban day lien mach)
  PA3 — Machine Learning (Random Forest hoc tu Bridge_Train_v3 — ket qua goc,
        khong bi nguoi dung ghi de, lam co so so sanh khach quan)
Fallback (chua co kcn_3_pa): 3 loai dam dai dien Dam I / T nguoc / Super-T.

Tung PA lay so do nhip, sau do tinh:
  - Loai tru / chieu cao tru
  - Loai mong / coc
  - Chi phi tuong doi, thoi gian thi cong
"""

import numpy as np
import os
import importlib.util

_DIR = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────────────────────
# Dải nhịp và tỉ lệ H/L theo loại dầm
# ─────────────────────────────────────────────────────────────────────────────
_DAM_SPEC = {
    "Dầm I":   {"L_min": 18, "L_max": 33, "L_opt": 24, "hL_lo": 15, "hL_hi": 18},
    "T ngược": {"L_min": 12, "L_max": 22, "L_opt": 18, "hL_lo": 12, "hL_hi": 15},
    "Super-T": {"L_min": 27, "L_max": 40, "L_opt": 33, "hL_lo": 18, "hL_hi": 20},
}

_STD_LENGTHS = [12, 15, 18, 21, 24, 25, 27, 30, 33, 38.2, 40]

# Chi so don gia tuong doi (so sanh giua PA)
_DAM_COST  = {"Super-T": 1.35, "Dầm I": 1.10, "T ngược": 0.95, "Dầm bản": 0.80}
_TRU_COST  = {
    "Thân cột 2 trụ": 0.90, "Thân cột 3 trụ": 1.00,
    "Trụ đặc": 0.85,        "Trụ đặc thân hẹp": 1.05,
    "Thân rỗng (2 cột)": 1.20, "Khung 2 cột": 1.10,
}
_MONG_COST  = {
    "Cọc đóng BTCT DƯL": 1.00, "Cọc ép BTCT DƯL": 1.15,
    "Cọc khoan nhồi": 1.80,    "Cọc ly tâm D600": 1.25,
}
_MONG_TGIAN = {
    "Cọc đóng BTCT DƯL": 0.8, "Cọc ép BTCT DƯL": 1.0,
    "Cọc khoan nhồi": 1.5,    "Cọc ly tâm D600": 1.0,
}


def _snap(L, choices=_STD_LENGTHS):
    return min(choices, key=lambda x: abs(x - L))


def _girder_rb(loai_dam, B_cau):
    """Khoang cach, so luong dam, overhang theo quy tac kinh nghiem."""
    defaults = {"Super-T": 2.2, "Dầm I": 2.0, "T ngược": 1.0, "Dầm bản": 0.7}
    kc = defaults.get(loai_dam, 2.0)
    n  = max(3, int(round(B_cau / kc)) + 1)
    oh = round((B_cau - (n - 1) * kc) / 2, 2)
    if oh > 0.8 * kc:
        n += 1
        oh = round((B_cau - (n - 1) * kc) / 2, 2)
    return round(kc, 2), n, max(0.2, oh)


# ─────────────────────────────────────────────────────────────────────────────
# SINH KCN CHO MOT LOAI DAM CU THE
# ─────────────────────────────────────────────────────────────────────────────

def _kcn_for_beam(loai_dam, B_tk, goc, B_cau, L_cau, kcn_models=None):
    """
    Tinh so do nhip toi uu cho mot loai dam cho truoc.
    Chon nhip trong dai [L_min, L_max] cua loai dam, snap ve chuan.
    """
    spec  = _DAM_SPEC.get(loai_dam, _DAM_SPEC["Dầm I"])
    L_min_geo = (B_tk / np.sin(np.radians(max(goc, 30)))) + 2.0

    # Chon candidates trong dai cho phep cua loai dam
    candidates = [
        L for L in _STD_LENGTHS
        if spec["L_min"] <= L <= spec["L_max"] and L >= L_min_geo * 0.95
    ]
    if not candidates:
        # Neu khong co ung vien, lay gan nhat voi L_opt
        candidates = [_snap(max(spec["L_opt"], L_min_geo))]

    # Chon n_nhip it nhat (it tru) trong pham vi hop le
    best_L, best_n = None, None
    for L in sorted(candidates, reverse=True):  # nhip dai -> it tru
        n = max(1, int(np.ceil(L_cau / L)))
        L_thuc = L_cau / n
        if L_thuc >= spec["L_min"] * 0.9:
            best_L, best_n = round(L_thuc, 2), n
            break

    if best_L is None:
        best_n = max(1, int(np.ceil(L_cau / spec["L_opt"])))
        best_L = round(L_cau / best_n, 2)

    # Chieu cao dam theo ti le H/L toi uu
    hL_mid = (spec["hL_lo"] + spec["hL_hi"]) / 2
    H_dam  = round(best_L / hL_mid, 2)

    # Bo tri dam ngang
    if kcn_models:
        try:
            s = importlib.util.spec_from_file_location(
                "kcn06", os.path.join(_DIR, "06-AI_KetCauNhip.py"))
            m = importlib.util.module_from_spec(s)
            s.loader.exec_module(m)
            kc, n_dam, oh = m._calc_girder_layout(loai_dam, best_L, B_cau, kcn_models)
        except Exception:
            kc, n_dam, oh = _girder_rb(loai_dam, B_cau)
    else:
        kc, n_dam, oh = _girder_rb(loai_dam, B_cau)

    lh = round(best_L / H_dam, 1) if H_dam > 0 else 0
    return {
        "loai_dam":        loai_dam,
        "chieu_dai":       best_L,
        "tong_so_nhip":    best_n,
        "chieu_cao_dam":   H_dam,
        "so_luong_dam":    n_dam,
        "khoang_cach_dam": kc,
        "overhang":        oh,
        "ti_le_L_H":       lh,
        "do_tin_cay":      0.0,
        "phuong_phap":     f"PA-{loai_dam}",
        "ghi_chu":         (
            f"{loai_dam}: {best_n} nhip x {best_L:.1f}m"
            f" | H={H_dam:.2f}m | L/H={lh:.1f}"
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CHI SO CHI PHI TUONG DOI
# ─────────────────────────────────────────────────────────────────────────────

def _cost_index(kcn, H_tru, B_cau, loai_tru, mong):
    n_nhip, L, H_dam = kcn["tong_so_nhip"], kcn["chieu_dai"], kcn["chieu_cao_dam"]
    n_dam, loai_dam  = kcn["so_luong_dam"], kcn["loai_dam"]
    n_tru = max(n_nhip - 1, 1)

    if "bản" in loai_dam.lower():
        v_dam = L * B_cau * H_dam
    elif "hộp" in loai_dam.lower():
        v_dam = L * B_cau * H_dam * 0.4
    else:
        v_dam = n_dam * L * H_dam * 0.25
    c_dam = n_nhip * v_dam * _DAM_COST.get(loai_dam, 1.2)

    h = max(H_tru, 1.0)
    if "cột" in loai_tru.lower():
        D = 0.8 + B_cau * 0.02
        nc = 3 if "3" in loai_tru else 2
        v_tru = nc * (np.pi * (D / 2) ** 2) * h
    elif "rỗng" in loai_tru.lower():
        v_tru = (B_cau * 0.4 - 0.3) * 0.35 * h
    else:
        b = max(1.2, B_cau * 0.08)
        v_tru = b * 1.5 * h
    c_tru = n_tru * v_tru * _TRU_COST.get(loai_tru, 1.0) * 2.5

    loai_mong = mong.get("loai_mong", "Cọc đóng BTCT DƯL")
    D_m   = mong.get("D_coc_mm", 600) / 1000
    L_c   = (mong.get("L_coc_tu", 30) + mong.get("L_coc_den", 45)) / 2
    n_coc = (mong.get("So_coc_tu", 4) + mong.get("So_coc_den", 8)) / 2
    c_mong = n_tru * n_coc * (D_m ** 2) * L_c * _MONG_COST.get(loai_mong, 1.0) * 10

    return c_dam + c_tru + c_mong


def _thoi_gian(n_tru, loai_mong, n_nhip, loai_dam):
    t_mong = n_tru * _MONG_TGIAN.get(loai_mong, 1.0) * 1.5
    t_tru  = n_tru * 0.8
    duc_san = loai_dam in ("Super-T", "Dầm I", "T ngược")
    t_dam  = n_nhip * (1.2 if duc_san else 2.0)
    return round(t_mong + t_tru + t_dam, 1)


# ─────────────────────────────────────────────────────────────────────────────
# HAM CHINH: SINH 3 PHUONG AN
# ─────────────────────────────────────────────────────────────────────────────

def generate_3_alternatives(
    B_tk, H_tk, goc, B_cau, moi_truong, L_cau,
    kcn_models=None, pier_models=None, fnd_models=None,
    MNCN=0.0, H_tk_nhip=3.5, h98=0.0,
    cap_song="VI", is_urban=0, is_river=1, vtk=80,
    # Tham so nay khong dung nua (giu lai de khong loi Interface.py)
    pa1_kcn=None, pa1_tru=None, pa1_mong=None,
    kcn_3_pa=None,
):
    """
    Sinh 3 phuong an thiet ke cau.

    Co kcn_3_pa (tu Module 06 predict_kcn) → dung DUNG 3 phuong an he thong:
      PA1 — Toi uu chi phi (khong ban day lien mach)
      PA2 — Toi uu my quan (ban day lien mach)
      PA3 — Machine Learning (ket qua goc lam co so so sanh)
    Khong co → fallback 3 loai dam dai dien (Dam I / T nguoc / Super-T).

    Returns: list[dict] gom 3 phuong an, moi dict co:
        label, color, mo_ta, loai_dam_key,
        kcn, tru, mong,
        H_tru_est, cao_day_dam, n_tru,
        cost_raw, cost_pct, thoi_gian, score_ky_thuat
    """
    spec7 = importlib.util.spec_from_file_location("mot07", os.path.join(_DIR, "07-AI_MoTru.py"))
    mod7  = importlib.util.module_from_spec(spec7)
    spec7.loader.exec_module(mod7)

    spec8 = importlib.util.spec_from_file_location("mong08", os.path.join(_DIR, "08-AI_Mong.py"))
    mod8  = importlib.util.module_from_spec(spec8)
    spec8.loader.exec_module(mod8)

    _PA_DEF = [
        {
            "loai_dam": "Dầm I",
            "pa_key":   "pa1_chi_phi",
            "label":    "PA1 — Tối ưu chi phí",
            "color":    "#3498db",
            "mo_ta":    "Nhịp dài — ít nhịp, dầm KHÔNG bản đáy liền mạch (cấu tạo đơn giản, chi phí thấp).",
        },
        {
            "loai_dam": "T ngược",
            "pa_key":   "pa2_my_quan",
            "label":    "PA2 — Tối ưu mỹ quan",
            "color":    "#2ecc71",
            "mo_ta":    "Dầm CÓ bản đáy liền mạch — bề mặt phẳng dưới cầu, phù hợp đô thị/cầu vượt.",
        },
        {
            "loai_dam": "Super-T",
            "pa_key":   "pa3_ml",
            "label":    "PA3 — Machine Learning",
            "color":    "#e67e22",
            "mo_ta":    "Random Forest học từ dữ liệu cầu VN (Bridge_Train_v3) — kết quả gốc tham chiếu.",
        },
    ]

    # 'pa3_ai' = key cu (du lieu luu truoc khi doi ten PA3 → Machine Learning)
    _3pa = dict(kcn_3_pa or {})
    if "pa3_ml" not in _3pa and "pa3_ai" in _3pa:
        _3pa["pa3_ml"] = _3pa["pa3_ai"]

    results = []
    for pa in _PA_DEF:
        _plan = _3pa.get(pa["pa_key"]) if _3pa else None

        # ── 1. KCN: dung dung phuong an Module 06 neu co ───────────────────
        if isinstance(_plan, dict) and _plan.get("loai_dam"):
            kcn = dict(_plan)
            loai_dam = kcn["loai_dam"]
            pa = dict(pa)
            pa["label"] = f"{pa['label']} ({loai_dam})"
            if _plan.get("ghi_chu"):
                pa["mo_ta"] = _plan["ghi_chu"]
        else:
            loai_dam = pa["loai_dam"]
            kcn = _kcn_for_beam(loai_dam, B_tk, goc, B_cau, L_cau, kcn_models)

        # ── 2. Chieu cao tru ─────────────────────────────────────────────
        _ph = mod7.estimate_pier_height(
            MNCN=MNCN, H_tinh_khong=H_tk_nhip,
            H_dam=kcn["chieu_cao_dam"], MNTN=h98,
        )
        H_tru_est   = _ph['H_than_tru']
        cao_day_dam = _ph['cao_day_dam']

        # ── 3. Tru — dung AI/RB chung (loai tru phu thuoc H_tru, B_cau, ...) ──
        tru = mod7.predict_pier(
            vtk=vtk, B_cau=B_cau, H_tru=H_tru_est,
            is_urban=is_urban, is_river=is_river,
            cap_song=cap_song, loai_dam=loai_dam,
            n_nhip=kcn["tong_so_nhip"], models=pier_models,
        )

        # ── 4. Mong ────────────────────────────────────────────────────
        mong = mod8.predict_foundation(
            H_tru=H_tru_est, loai_tru=tru["loai_tru"],
            is_river=is_river, cap_song=cap_song,
            B_cau=B_cau, vtk=vtk,
            L_nhip=kcn["chieu_dai"],
            is_urban=is_urban,
            foundation_models=fnd_models,
        )

        n_tru = max(kcn["tong_so_nhip"] - 1, 1)

        # ── 5. Chi phi va thoi gian ─────────────────────────────────────
        ci = _cost_index(kcn, H_tru_est, B_cau, tru["loai_tru"], mong)
        tg = _thoi_gian(n_tru, mong["loai_mong"], kcn["tong_so_nhip"], loai_dam)

        # Score ky thuat (L/H trong dai toi uu + it tru)
        lh = kcn.get("ti_le_L_H", 0) or 0
        spec = _DAM_SPEC.get(loai_dam, {})
        lo, hi = spec.get("hL_lo", 15), spec.get("hL_hi", 20)
        lh_score  = 100 if lo <= lh <= hi else (70 if lo * 0.9 <= lh <= hi * 1.1 else 40)
        tru_score = max(0, 100 - n_tru * 5)
        score_kt  = round((lh_score + tru_score) / 2, 0)

        results.append({
            "label":          pa["label"],
            "pa_key":         pa.get("pa_key"),
            "color":          pa["color"],
            "mo_ta":          pa["mo_ta"],
            "loai_dam_key":   loai_dam,
            "kcn":            kcn,
            "tru":            tru,
            "mong":           mong,
            "H_tru_est":      round(H_tru_est, 2),
            "cao_day_dam":    round(cao_day_dam, 3),
            "n_tru":          n_tru,
            "cost_raw":       ci,
            "cost_pct":       100.0,
            "thoi_gian":      tg,
            "score_ky_thuat": score_kt,
        })

    # Chuan hoa chi phi ve % so voi PA1 (Dam I)
    base = results[0]["cost_raw"] if results[0]["cost_raw"] > 0 else 1.0
    for r in results:
        r["cost_pct"] = round(r["cost_raw"] / base * 100, 1)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# CAP NHAT 1 PHUONG AN SAU KHI NGUOI DUNG KHAI BAO LAI (PA1/PA2)
# ─────────────────────────────────────────────────────────────────────────────

def refresh_alternative_kcn(alternatives, pa_key, kcn_plan, B_cau):
    """Cap nhat KCN cua 1 phuong an trong list alternatives (sau khi nguoi dung
    khai bao lai dam PA1/PA2 hoac huy khai bao) va tinh lai chi phi/thoi gian.
    Giu nguyen tru/mong hien co (xap xi chap nhan duoc cho so sanh so bo)."""
    if not alternatives or not isinstance(kcn_plan, dict):
        return alternatives
    for alt in alternatives:
        if alt.get("pa_key") != pa_key:
            continue
        kcn = dict(kcn_plan)
        alt["kcn"] = kcn
        alt["loai_dam_key"] = kcn.get("loai_dam", alt.get("loai_dam_key"))
        alt["n_tru"] = max(int(kcn.get("tong_so_nhip", 1)) - 1, 1)
        base_lbl = str(alt.get("label", "")).split(" (")[0]
        alt["label"] = f"{base_lbl} ({kcn.get('loai_dam','?')})"
        if kcn.get("ghi_chu"):
            alt["mo_ta"] = kcn["ghi_chu"]
        try:
            alt["cost_raw"] = _cost_index(
                kcn, alt.get("H_tru_est", 6.0), B_cau,
                (alt.get("tru") or {}).get("loai_tru", "Trụ đặc"),
                alt.get("mong") or {})
            alt["thoi_gian"] = _thoi_gian(
                alt["n_tru"], (alt.get("mong") or {}).get("loai_mong", ""),
                kcn.get("tong_so_nhip", 1), alt["loai_dam_key"])
        except Exception:
            pass
        break
    # Chuan hoa lai % chi phi theo PA1
    try:
        base = alternatives[0].get("cost_raw") or 1.0
        for r in alternatives:
            if r.get("cost_raw"):
                r["cost_pct"] = round(r["cost_raw"] / base * 100, 1)
    except Exception:
        pass
    return alternatives


def _nguon_chon_badges(alternatives, st):
    """Badge nguon chon cho tung cot PA: nguoi dung ghi de → VANG
    'Người dùng khai báo'; PA3 Machine Learning → XANH DUONG 'Kết quả ML gốc'
    (nhan manh vai tro co so so sanh khach quan, khong bi can thiep)."""
    _3pa = ((st.session_state.get("design_data") or {}).get("kcn_3_pa")
            if hasattr(st, "session_state") else None) or {}
    out = []
    for alt in alternatives:
        pk = alt.get("pa_key")
        if pk == "pa3_ml":
            out.append("<span style='background:#1d4ed8;color:#fff;padding:2px 8px;"
                       "border-radius:10px;font-size:11px'>Kết quả ML gốc</span>")
            continue
        plan = _3pa.get(pk) or {}
        if plan.get("nguon_chon") == "nguoi_dung_khai_bao" or \
                (alt.get("kcn") or {}).get("nguon_chon") == "nguoi_dung_khai_bao":
            out.append("<span style='background:#f59e0b;color:#1a1000;padding:2px 8px;"
                       "border-radius:10px;font-size:11px'>Người dùng khai báo</span>")
        else:
            out.append("")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# RENDER TAB SO SANH (Streamlit)
# ─────────────────────────────────────────────────────────────────────────────

def render_comparison_tab(alternatives, st):
    """Render tab so sanh 3 phuong an."""
    import plotly.graph_objects as go
    import pandas as pd

    if not alternatives:
        st.warning("Chua co du lieu phuong an. Hay chay tinh toan truoc.")
        return

    pa_labels = [a["label"] for a in alternatives]
    pa_colors = [a["color"] for a in alternatives]

    st.markdown("## So sanh 3 Phuong An")
    st.caption("PA1 chi phí · PA2 mỹ quan · PA3 Machine Learning — so sanh ky thuat, kinh te va thi cong")

    # Badge BA KHOẢNG TĨNH KHÔNG (module 06) — cách so sánh khác nhau theo khoảng
    _kg = (((st.session_state.get("design_data") or {}).get("kcn_3_pa") or {})
           .get("khoang_tinh_khong")
           if hasattr(st, "session_state") else None) or {}
    _kg_id = _kg.get("khoang")
    if _kg_id == "nho":
        st.markdown("<span style='background:#0d3d1f;color:#2ecc71;padding:2px 10px;"
                    "border-radius:12px;font-size:12px'>🟢 Khoảng nhỏ — so sánh "
                    "3 PA dầm giản đơn tiêu chuẩn</span>", unsafe_allow_html=True)
    elif _kg_id == "trung":
        st.markdown("<span style='background:#3a2c00;color:#f39c12;padding:2px 10px;"
                    "border-radius:12px;font-size:12px'>🟡 Khoảng trung — so sánh "
                    "Super-T mở rộng xà mũ ↔ dầm hộp đúc hẫng (PA3 = fallback "
                    "PA2, chi phí dầm hộp là ước tính sơ bộ)</span>",
                    unsafe_allow_html=True)
    elif _kg_id == "lon":
        st.markdown("<span style='background:#4a2410;color:coral;padding:2px 10px;"
                    "border-radius:12px;font-size:12px'>🟠 Khoảng lớn — ngoài "
                    "phạm vi đề tài: không so sánh định lượng, chỉ ghi nhận "
                    "khuyến nghị lý thuyết (dây văng / dầm hộp lớn)</span>",
                    unsafe_allow_html=True)

    # Mo ta ngan + badge nguon chon (nguoi dung khai bao / ket qua ML goc)
    _badges = _nguon_chon_badges(alternatives, st)
    cols = st.columns(3)
    for alt, col, bdg in zip(alternatives, cols, _badges):
        with col:
            st.markdown(
                f"<div style='background:{alt['color']}22;border-left:4px solid {alt['color']};"
                f"padding:12px;border-radius:8px;margin-bottom:8px'>"
                f"<b>{alt['label']}</b> {bdg}<br><small>{alt['mo_ta']}</small></div>",
                unsafe_allow_html=True,
            )
    st.markdown("---")

    # ── Bang chi tieu ─────────────────────────────────────────────────────
    st.markdown("### Chi tieu ky thuat — Ket cau nhip, Tru & Mong")

    # Highlight: bien hien thi "tot nhat" trong moi hang
    _raw = {
        "n_nhip": [a["kcn"]["tong_so_nhip"] for a in alternatives],
        "L":      [a["kcn"]["chieu_dai"]     for a in alternatives],
        "H_dam":  [a["kcn"]["chieu_cao_dam"] for a in alternatives],
        "lh":     [a["kcn"].get("ti_le_L_H",0) or 0 for a in alternatives],
        "n_tru":  [a["n_tru"]                for a in alternatives],
        "H_tru":  [a["H_tru_est"]            for a in alternatives],
        "cost":   [a["cost_pct"]             for a in alternatives],
        "tgian":  [a["thoi_gian"]            for a in alternatives],
    }
    # Dam I c huẩn L/H toi uu: 15-18; T nguoc: 12-15; Super-T: 18-20
    _LH_RANGE = {
        "Dầm I":   (15, 18),
        "T ngược": (12, 15),
        "Super-T": (18, 20),
    }

    rows = [
        ("Loai dam",          [a["loai_dam_key"]                                   for a in alternatives], None),
        ("So do nhip",        [f"{a['kcn']['tong_so_nhip']} nhip x {a['kcn']['chieu_dai']:.1f} m" for a in alternatives], None),
        ("Chieu cao dam H (m)",[f"{a['kcn']['chieu_cao_dam']:.2f}"                 for a in alternatives], None),
        ("Ti le L/H",         [f"{a['kcn'].get('ti_le_L_H',0) or 0:.1f}"          for a in alternatives], "lh_check"),
        ("So dam / MCN",      [str(a["kcn"]["so_luong_dam"])                       for a in alternatives], None),
        ("Loai tru",          [a["tru"]["loai_tru"]                                for a in alternatives], None),
        ("So tru giua",       [str(a["n_tru"])                                     for a in alternatives], "min_best"),
        ("H tru uoc tinh (m)",[f"{a['H_tru_est']:.2f}"                            for a in alternatives], None),
        ("Loai mong",         [a["mong"]["loai_mong"]                              for a in alternatives], None),
        ("Duong kinh coc",    [a["mong"]["D_coc_chon_txt"]                         for a in alternatives], None),
        ("Chieu dai coc (m)", [f"{a['mong']['L_coc_tu']}–{a['mong']['L_coc_den']}" for a in alternatives], None),
        ("So coc / be",       [f"{a['mong']['So_coc_tu']}–{a['mong']['So_coc_den']}" for a in alternatives], None),
    ]

    hdr = "".join(
        f"<th style='background:{c}22;color:{c};padding:8px;text-align:center'>{lb}"
        f"{('<br>' + b) if b else ''}</th>"
        for c, lb, b in zip(pa_colors, pa_labels, _badges)
    )
    # Mau BAM THEME: dung rgba() BAN TRONG SUOT thay vi ma mau dac.
    # Truoc day bang ep cung mau SANG (#f0f0f0 / #f8f9fa / #ffffff) trong khi than
    # bang KHONG dat mau chu -> chu thua huong theme. O nen TOI: chu trang tren o
    # trang = khong doc duoc. rgba phu len nen trang nen tu hop voi ca sang lan toi.
    # (Co y dung rgba chu khong phai rgb: bo lat mau trong 00-Interface.py chi khop
    #  'rgb(' — rgba duoc bo qua, tranh bi lat nguoc lai.)
    _BG_HEAD = "rgba(128,128,128,0.18)"     # header
    _BG_ODD  = "rgba(128,128,128,0.07)"     # soc xen ke
    _BG_EVEN = "transparent"
    _LINE    = "rgba(128,128,128,0.40)"
    _OK      = "rgba(46,204,113,0.28)"      # xanh: tot nhat / trong dai
    _BAD     = "rgba(231,76,60,0.22)"       # do: ngoai pham vi
    html = (
        "<table style='width:100%;border-collapse:collapse;font-size:14px'>"
        f"<tr><th style='text-align:left;padding:8px;background:{_BG_HEAD}'>Tieu chi</th>{hdr}</tr>"
    )
    separators = {5, 8}
    for idx, (label, vals, hint) in enumerate(rows):
        bg = _BG_ODD if idx % 2 == 0 else _BG_EVEN
        border = f"border-top:2px solid {_LINE};" if idx in separators else ""
        cells = ""
        for vi, (v, alt) in enumerate(zip(vals, alternatives)):
            # Danh dau o "tot nhat" bang mau xanh nhat
            mark = ""
            if hint == "min_best":
                raw_vals = [a["n_tru"] for a in alternatives]
                if int(v) == min(raw_vals):
                    mark = f" background:{_OK}!important;font-weight:bold;"
            elif hint == "lh_check":
                lo, hi = _LH_RANGE.get(alt["loai_dam_key"], (15, 20))
                lh_val = alt["kcn"].get("ti_le_L_H", 0) or 0
                if lo <= lh_val <= hi:
                    mark = f" background:{_OK}!important;font-weight:bold;"
                elif lh_val < lo * 0.9 or lh_val > hi * 1.1:
                    mark = f" background:{_BAD}!important;"
            cells += f"<td style='text-align:center;padding:6px;background:{bg};{border}{mark}'>{v}</td>"
        html += (
            f"<tr><td style='padding:6px;background:{bg};font-weight:500;{border}'>{label}</td>"
            f"{cells}</tr>"
        )
    html += "</table>"
    html += "<p style='font-size:11px;color:#888;margin-top:4px'>🟢 Xanh = gia tri tot nhat / trong dai toi uu &nbsp;|&nbsp; 🔴 Do = ngoai pham vi khuyen nghi</p>"
    st.markdown(html, unsafe_allow_html=True)

    st.markdown("---")

    # ── Bieu do so sanh ────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### Chi phi tuong doi (Dam I = 100%)")
        costs = [a["cost_pct"] for a in alternatives]
        fig_cost = go.Figure(go.Bar(
            x=pa_labels, y=costs, marker_color=pa_colors,
            text=[f"{c:.0f}%" for c in costs], textposition="outside",
        ))
        fig_cost.add_hline(y=100, line_dash="dot", line_color="#888",
                           annotation_text="Dam I = 100%", annotation_position="bottom right")
        fig_cost.update_layout(
            yaxis_title="% so voi Dam I",
            yaxis=dict(range=[0, max(costs) * 1.25]),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            height=300, margin=dict(t=20, b=10),
        )
        st.plotly_chart(fig_cost, use_container_width=True, key="chart_cost_pa")

    with col_b:
        st.markdown("### Thoi gian thi cong uoc tinh (thang)")
        tgt = [a["thoi_gian"] for a in alternatives]
        fig_tgt = go.Figure(go.Bar(
            x=pa_labels, y=tgt, marker_color=pa_colors,
            text=[f"{t:.1f}" for t in tgt], textposition="outside",
        ))
        fig_tgt.update_layout(
            yaxis_title="Thang",
            yaxis=dict(range=[0, max(tgt) * 1.3]),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            height=300, margin=dict(t=20, b=10),
        )
        st.plotly_chart(fig_tgt, use_container_width=True, key="chart_tgt_pa")

    # ── Bieu do so do nhip ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### So sánh sơ đồ nhịp")

    fig_span = go.Figure()
    for alt in alternatives:
        kcn = alt["kcn"]
        n   = kcn["tong_so_nhip"]
        L   = kcn["chieu_dai"]
        # Ve cac nhip nhu cac thanh ngang
        x_vals, y_vals = [], []
        for i in range(n):
            x_start = i * L
            x_end   = (i + 1) * L
            x_vals += [x_start, x_end, None]
            y_vals += [0, 0, None]
        fig_span.add_trace(go.Scatter(
            x=x_vals, y=y_vals,
            mode="lines",
            line=dict(color=alt["color"], width=10),
            name=f"{alt['label']} ({n}x{L:.1f}m)",
        ))
        # Ve tru
        for i in range(1, n):
            fig_span.add_shape(
                type="line",
                x0=i * L, y0=-0.5, x1=i * L, y1=0,
                line=dict(color=alt["color"], width=3),
            )

    fig_span.update_layout(
        xaxis_title="Chieu dai (m)", yaxis=dict(visible=False),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=220, margin=dict(t=10, b=30, l=10, r=10),
        showlegend=True,
        legend=dict(orientation="h", y=-0.3),
    )
    st.plotly_chart(fig_span, use_container_width=True, key="chart_span_pa")

    # ── Radar chart ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Bieu do Radar — Danh gia Da tieu chi")
    categories = ["Chi phi thap", "L/H toi uu", "It tru", "Thi cong nhanh", "Nhan hieu dia phuong"]

    max_cost = max(a["cost_pct"] for a in alternatives)
    max_tgt  = max(a["thoi_gian"] for a in alternatives)
    min_tgt  = min(a["thoi_gian"] for a in alternatives)

    # "Pho bien dia phuong": Dam I va T nguoc rat pho bien o VN
    _local_score = {"Dầm I": 90, "T ngược": 80, "Super-T": 70}

    fig_radar = go.Figure()
    for alt in alternatives:
        cost_score = round(max(10, min(100, (max_cost - alt["cost_pct"]) / max(max_cost - min(a["cost_pct"] for a in alternatives), 1) * 90 + 10)), 0)
        lh_score   = float(alt["score_ky_thuat"])
        tru_score  = max(10, 100 - alt["n_tru"] * 8)
        tgt_range  = max(max_tgt - min_tgt, 0.1)
        tgt_score  = round(max(10, min(100, (max_tgt - alt["thoi_gian"]) / tgt_range * 90 + 10)), 0)
        local_score = _local_score.get(alt["loai_dam_key"], 60)

        vals = [cost_score, lh_score, tru_score, tgt_score, local_score, cost_score]
        _h = alt["color"].lstrip("#")
        _fill = f"rgba({int(_h[0:2],16)},{int(_h[2:4],16)},{int(_h[4:6],16)},0.20)"
        fig_radar.add_trace(go.Scatterpolar(
            r=vals,
            theta=categories + [categories[0]],
            fill="toself",
            name=alt["label"],
            line_color=alt["color"],
            fillcolor=_fill,
        ))

    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True, height=420,
        margin=dict(t=20, b=20),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_radar, use_container_width=True, key="chart_radar_pa")

    # ── Nhan xet khuyen nghi ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Nhan xet & Khuyen nghi")

    min_cost_idx = min(range(3), key=lambda i: alternatives[i]["cost_pct"])
    min_tru_idx  = min(range(3), key=lambda i: alternatives[i]["n_tru"])
    best_lh_idx  = max(range(3), key=lambda i: alternatives[i]["score_ky_thuat"])
    min_tgt_idx  = min(range(3), key=lambda i: alternatives[i]["thoi_gian"])

    for note in [
        f"**Chi phi thap nhat**: {alternatives[min_cost_idx]['label']} — {alternatives[min_cost_idx]['cost_pct']:.0f}% so voi Dam I",
        f"**It tru nhat**: {alternatives[min_tru_idx]['label']} — {alternatives[min_tru_idx]['n_tru']} tru giua",
        f"**Ti le L/H tot nhat**: {alternatives[best_lh_idx]['label']} — L/H = {alternatives[best_lh_idx]['kcn'].get('ti_le_L_H',0) or 0:.1f}",
        f"**Thi cong nhanh nhat**: {alternatives[min_tgt_idx]['label']} — {alternatives[min_tgt_idx]['thoi_gian']:.1f} thang",
    ]:
        st.markdown(f"- {note}")

    # ── Bang so sanh loai tru ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### So sanh phuong an tru theo loai dam:")
    tru_rows = [
        {
            "Loai dam":    alt["loai_dam_key"],
            "So do nhip":  f"{alt['kcn']['tong_so_nhip']}x{alt['kcn']['chieu_dai']:.1f}m",
            "Loai tru":    alt["tru"]["loai_tru"],
            "So tru":      alt["n_tru"],
            "H tru (m)":   f"{alt['H_tru_est']:.2f}",
            "Loai mong":   alt["mong"]["loai_mong"],
            "D coc":       alt["mong"]["D_coc_chon_txt"],
            "Chi phi (%)": f"{alt['cost_pct']:.0f}%",
            "Thoi gian (thang)": f"{alt['thoi_gian']:.1f}",
        }
        for alt in alternatives
    ]
    st.dataframe(pd.DataFrame(tru_rows), use_container_width=True, hide_index=True)
