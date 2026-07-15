"""
mcda/ahp_interface.py — Giao diện MCDA-AHP cho tab SO SÁNH PHƯƠNG ÁN:
  • Khai báo so sánh cặp 2 CẤP (nhóm chính ↔ tiêu chí con) theo thang Saaty 1–9,
    chỉ khai nửa trên ma trận (nửa dưới = nghịch đảo tự động).
  • Hiển thị ma trận đầy đủ + ma trận chuẩn hóa + trọng số W_i + chỉ số CR
    (CR ≤ 0.10 xanh "nhất quán"; CR > 0.10 đỏ + gợi ý cặp mâu thuẫn).
  • Nút "Dùng trọng số mặc định" (35/35/20/10 + phân bổ con chuẩn).
  • Kết quả: bảng điểm chi tiết (màu theo mức), radar 4 nhóm, tổng điểm +
    xếp loại + phương án khuyến nghị.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import criteria_config as CC
from . import ahp_calculator as AHP
from . import data_adapter as DA
from . import scoring_engine as SE
from . import criteria_manager as CM

# Thang Saaty cho 1 CẶP (trái ⟵ quan trọng hơn | 1 = ngang nhau | ⟶ phải)
_SAATY_OPTS = ["9 ⟵", "7 ⟵", "5 ⟵", "3 ⟵", "1 =", "3 ⟶", "5 ⟶", "7 ⟶", "9 ⟶"]
_SAATY_VAL = {"9 ⟵": 9.0, "7 ⟵": 7.0, "5 ⟵": 5.0, "3 ⟵": 3.0, "1 =": 1.0,
              "3 ⟶": 1/3, "5 ⟶": 1/5, "7 ⟶": 1/7, "9 ⟶": 1/9}
_SAATY_HELP = ("Thang Saaty: 1 = quan trọng NGANG NHAU · 3 = hơn ÍT · "
               "5 = hơn RÕ RỆT · 7 = hơn RẤT NHIỀU · 9 = TUYỆT ĐỐI hơn. "
               "Mũi tên chỉ phía quan trọng hơn.")


def _pairwise_matrix_ui(st, labels, key_prefix, ten_muc):
    """UI khai báo NỬA TRÊN ma trận so sánh cặp → trả kết quả AHP đầy đủ."""
    n = len(labels)
    A = np.ones((n, n))
    if n >= 2:
        st.caption(_SAATY_HELP)
        for i in range(n):
            for j in range(i + 1, n):
                _sel = st.select_slider(
                    f"**{labels[i]}** ⟵ · ⟶ **{labels[j]}**",
                    options=_SAATY_OPTS, value=st.session_state.get(
                        f"{key_prefix}_{i}_{j}", "1 ="),
                    key=f"{key_prefix}_{i}_{j}")
                A[i, j] = _SAATY_VAL[_sel]
                A[j, i] = 1.0 / A[i, j]        # nửa dưới = nghịch đảo
    res = AHP.tinh_trong_so_ahp(A)
    with st.expander(f"Ma trận & trọng số — {ten_muc} "
                     f"(CR = {res['CR']:.3f})", expanded=False):
        st.markdown("**Ma trận so sánh cặp** (nửa dưới tự nghịch đảo):")
        st.dataframe(pd.DataFrame(np.round(A, 3), index=labels,
                                  columns=labels), use_container_width=True)
        st.markdown("**Ma trận chuẩn hóa** (chia tổng cột):")
        st.dataframe(pd.DataFrame(res["ma_tran_chuan_hoa"], index=labels,
                                  columns=labels), use_container_width=True)
        st.markdown("**Vector trọng số W_i:** " + " · ".join(
            f"{l} = {w:.3f}" for l, w in zip(labels, res["trong_so"])))
        st.caption(f"λ_max = {res['lambda_max']} · CI = {res['CI']} · "
                   f"CR = {res['CR']}")
    if res["chap_nhan"]:
        st.success(f"✅ {ten_muc}: CR = {res['CR']:.3f} ≤ 0.10 — "
                   "ma trận NHẤT QUÁN, chấp nhận.")
    else:
        _hint = AHP.goi_y_cap_mau_thuan(A, res["trong_so"], labels)
        _txt = ""
        if _hint:
            _txt = (f" Gợi ý: cặp **{_hint[0]} ↔ {_hint[1]}** đang mâu thuẫn "
                    f"nhất (khai {_hint[2]} nhưng tỉ số trọng số ≈ {_hint[3]}).")
        st.error(f"❌ {ten_muc}: CR = {res['CR']:.3f} > 0.10 — ma trận KHÔNG "
                 f"nhất quán, vui lòng xem lại các giá trị so sánh cặp.{_txt}")
    return res


def _default_weights(criteria):
    """Bộ trọng số mặc định 35/35/20/10 + phân bổ con chuẩn (chuẩn hóa theo
    tiêu chí đang active)."""
    by_group = CC.active_by_group(criteria)
    g_active = {g: cs for g, cs in by_group.items() if cs}
    tot_g = sum(CC.DEFAULT_GROUP_WEIGHTS.get(g, 0) for g in g_active) or 1.0
    w_nhom = {g: CC.DEFAULT_GROUP_WEIGHTS.get(g, 0) / tot_g for g in g_active}
    w_con = {}
    for g, cs in g_active.items():
        raw = {c["ma"]: CC.DEFAULT_SUB_WEIGHTS.get(c["ma"], 1.0) for c in cs}
        tot = sum(raw.values()) or 1.0
        w_con[g] = {ma: v / tot for ma, v in raw.items()}
    return w_nhom, w_con


def render_ahp_section(st, criteria):
    """Khai báo trọng số 2 cấp → trả (trong_so_tuyet_doi {ma:%}, ok: bool)."""
    by_group = CC.active_by_group(criteria)
    g_keys = [g for g in CC.GROUPS if by_group.get(g)]

    _c1, _c2 = st.columns([1, 2])
    with _c1:
        _use_default = st.toggle(
            "Dùng trọng số mặc định",
            value=bool(st.session_state.get("mcda_use_default", True)),
            key="mcda_use_default",
            help="Nhóm 35/35/20/10 (Kỹ thuật/Kinh tế/Thi công/Mỹ quan) + "
                 "phân bổ con chuẩn — bỏ qua khai báo AHP.")
    if _use_default:
        w_nhom, w_con = _default_weights(criteria)
        weights, warn = AHP.tinh_trong_so_tuyet_doi(w_nhom, w_con)
        with _c2:
            st.info("Đang dùng bộ trọng số MẶC ĐỊNH "
                    "(Kỹ thuật 35 · Kinh tế 35 · Thi công 20 · Mỹ quan 10).")
        if warn:
            st.warning(warn)
        return weights, True

    ok = True
    # ── CẤP 1: so sánh cặp 4 nhóm chính ─────────────────────────────────────
    st.markdown("#### CẤP 1 — So sánh cặp giữa các NHÓM tiêu chí")
    g_labels = [CC.GROUPS[g] for g in g_keys]
    res_g = _pairwise_matrix_ui(st, g_labels, "mcda_pw_grp", "Nhóm chính")
    ok = ok and res_g["chap_nhan"]
    w_nhom = {g: w for g, w in zip(g_keys, res_g["trong_so"])}

    # ── CẤP 2: so sánh cặp tiêu chí con trong từng nhóm ─────────────────────
    st.markdown("#### CẤP 2 — So sánh cặp TIÊU CHÍ CON trong từng nhóm")
    w_con = {}
    for g in g_keys:
        cs = by_group[g]
        st.markdown(f"##### Nhóm {CC.GROUPS[g]} ({len(cs)} tiêu chí)")
        labels = [f"{c['ma']} {c['ten']}" for c in cs]
        # key theo MÃ tiêu chí → thêm/bớt tiêu chí tự sinh cặp mới
        key_pfx = "mcda_pw_" + g + "_" + "_".join(c["ma"] for c in cs)
        res_s = _pairwise_matrix_ui(st, labels, key_pfx, f"Nhóm {CC.GROUPS[g]}")
        ok = ok and res_s["chap_nhan"]
        w_con[g] = {c["ma"]: w for c, w in zip(cs, res_s["trong_so"])}

    weights, warn = AHP.tinh_trong_so_tuyet_doi(w_nhom, w_con)
    if warn:
        st.warning(warn)
    st.markdown("**Trọng số tuyệt đối (thang 100):** " + " · ".join(
        f"{ma} = {w:.1f}%" for ma, w in sorted(weights.items())))
    return weights, ok


def _render_results(st, du_lieu, weights, criteria):
    """Bảng chi tiết (màu theo mức) + radar 4 nhóm + tổng điểm/xếp loại."""
    kq = SE.cham_diem_mcda(du_lieu, weights, criteria)
    if kq["bo_qua"]:
        for c, ly_do in kq["bo_qua"]:
            st.warning(f"⏭️ Bỏ qua **{c['ma']} {c['ten']}** — {ly_do}.")
    if not kq["rows"]:
        st.error("Không có tiêu chí nào chấm được — kiểm tra dữ liệu/tiêu chí.")
        return

    pa_keys = list(du_lieu.keys())
    labels = {k: du_lieu[k].get("label", k) for k in pa_keys}

    # 1) Bảng chi tiết điểm từng tiêu chí (điểm thô / điểm có trọng số)
    st.markdown("#### 📋 Bảng điểm chi tiết")
    df = pd.DataFrame([{
        "Mã": r["ma"], "Tiêu chí": r["ten"], "Nhóm": CC.GROUPS[r["nhom"]],
        "Trọng số (%)": r["trong_so"],
        **{f"{labels[k]}": f"{r['tho'][k]:.1f} → {r['ts'][k]:.2f}"
           for k in pa_keys},
    } for r in kq["rows"]])
    _sty = df.style
    try:                                    # màu nền theo mức điểm thô
        def _bg(v):
            try:
                tho = float(str(v).split("→")[0])
            except (ValueError, IndexError):
                return ""
            if tho >= 8:
                return "background-color: rgba(46,204,113,0.25)"
            if tho >= 5:
                return "background-color: rgba(241,196,15,0.22)"
            return "background-color: rgba(231,76,60,0.22)"
        _sty = _sty.map(_bg, subset=[labels[k] for k in pa_keys])
    except Exception:
        pass
    st.dataframe(_sty, use_container_width=True, hide_index=True)
    st.caption("Mỗi ô: **điểm thô (0–10) → điểm có trọng số**. "
               "Xanh ≥8 · vàng 5–8 · đỏ <5.")

    # 2) Radar chart 4 nhóm (điểm nhóm chuẩn hóa 0–10)
    st.markdown("#### 🕸️ Radar 4 nhóm tiêu chí")
    _gs = [g for g in CC.GROUPS if kq["nhom_max"].get(g)]
    fig = go.Figure()
    for k in pa_keys:
        vals = [round(kq["nhom_diem"][k].get(g, 0)
                      / max(kq["nhom_max"].get(g, 1), 1e-9) * 10, 2)
                for g in _gs]
        fig.add_trace(go.Scatterpolar(
            r=vals + vals[:1],
            theta=[CC.GROUPS[g] for g in _gs] + [CC.GROUPS[_gs[0]]],
            fill="toself", name=labels[k]))
    fig.update_layout(
        polar=dict(radialaxis=dict(range=[0, 10], showticklabels=True)),
        height=420, margin=dict(l=60, r=60, t=30, b=30),
        legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(fig, use_container_width=True)

    # 3) Tổng điểm + xếp loại + khuyến nghị
    st.markdown("#### 🏆 Tổng điểm & xếp loại")
    kn = kq["khuyen_nghi"] or {}
    cols = st.columns(len(pa_keys))
    for col, k in zip(cols, pa_keys):
        _is_best = (k == kn.get("pa"))
        col.metric(("⭐ " if _is_best else "") + labels[k],
                   f"{kq['tong'][k]:.1f} / 100", kq["xep_loai"][k])
    if kn:
        if kn.get("tuong_duong"):
            st.info(f"⚖️ **{labels[kn['pa']]}** và "
                    f"**{labels[kn['tuong_duong']]}** TƯƠNG ĐƯƠNG "
                    f"(chênh {kn['chenh']:.1f} < 5 điểm) — cân nhắc thêm yếu tố "
                    "ngoài mô hình (địa phương, thẩm mỹ, kinh nghiệm thi công).")
        else:
            st.success(f"🏆 Khuyến nghị chọn **{labels[kn['pa']]}** "
                       f"({kq['tong'][kn['pa']]:.1f} điểm — "
                       f"{kq['xep_loai'][kn['pa']]})"
                       + (f", hơn PA kế {kn['chenh']:.1f} điểm."
                          if kn.get("chenh") is not None else "."))


def render_mcda_tab(st):
    """Entry point — gọi từ tab SO SÁNH PHƯƠNG ÁN của 00-Interface."""
    st.markdown("## 🎯 Chấm điểm so sánh phương án — MCDA / AHP-Saaty")
    st.caption("Dữ liệu 3 phương án lấy TỰ ĐỘNG từ kết quả hệ thống (Module "
               "06 + 12); trọng số do NGƯỜI DÙNG khai báo qua so sánh cặp AHP "
               "hoặc dùng bộ mặc định 35/35/20/10.")

    criteria = CM.get_criteria(st)
    du_lieu, warns = DA.lay_du_lieu_3_pa(st.session_state)

    t_data, t_crit, t_ahp, t_kq = st.tabs(
        ["📥 Dữ liệu 3 PA", "🧩 Tiêu chí", "⚖️ Trọng số AHP", "🏆 Kết quả"])

    with t_data:
        for w in warns:
            st.warning(f"⚠️ {w}")
        if du_lieu:
            st.dataframe(pd.DataFrame([
                {"Thông số": lbl, **{du_lieu[k]["label"]:
                                     du_lieu[k].get(fld) for k in du_lieu}}
                for fld, lbl in [
                    ("loai_dam", "Loại dầm"),
                    ("L_max_kha_nang", "L_max khả năng (m)"),
                    ("L_min_yeu_cau", "L_min yêu cầu (m)"),
                    ("L_thuc_te", "L thực tế (m)"),
                    ("H_dam", "H dầm (m)"),
                    ("so_nhip", "Số nhịp"),
                    ("khoang_cach_dam", "Khoảng cách dầm (m)"),
                    ("so_dam_mc", "Số dầm/mặt cắt"),
                    ("co_ban_day", "Bản đáy liền mạch"),
                    ("suat_dau_tu", "Suất đầu tư (tr/m²)"),
                    ("ngay_thi_cong_nhip", "Ngày thi công/nhịp"),
                    ("dien_tich_bai_duc", "Bãi đúc (m²)"),
                ]]), use_container_width=True, hide_index=True)
            CM.render_manual_inputs(st, du_lieu)
        else:
            st.error("Chưa có dữ liệu 3 phương án — chạy ⚙️ OPTIONS → "
                     "Tính toán trước.")

    with t_crit:
        criteria = CM.render_criteria_manager(st, criteria)

    with t_ahp:
        weights, ok = render_ahp_section(st, criteria)

    with t_kq:
        if not du_lieu:
            st.error("Chưa có dữ liệu 3 phương án.")
        elif not ok:
            st.error("Ma trận AHP chưa nhất quán (CR > 0.10) — sửa ở tab "
                     "**⚖️ Trọng số AHP** trước khi xem kết quả.")
        else:
            # nạp lại dữ liệu (nhập thủ công có thể vừa đổi)
            du_lieu, _ = DA.lay_du_lieu_3_pa(st.session_state)
            _render_results(st, du_lieu, weights, criteria)
