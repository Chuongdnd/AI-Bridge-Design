"""
mcda/criteria_manager.py — Quản lý bộ tiêu chí qua giao diện:
  • Bật/tắt tiêu chí có sẵn (checkbox active).
  • Thêm tiêu chí mới (tên, nhóm, loại công thức, hướng tối ưu, giá trị từng
    PA nếu thủ công) — đánh dấu custom=True; xóa được tiêu chí custom.
  • Thêm/bớt tiêu chí → ma trận AHP của nhóm đó ĐỔI KEY (theo bộ mã tiêu chí)
    → tự yêu cầu khai báo lại so sánh cặp; cảnh báo rõ cho người dùng.
  • Cấu hình lưu Session State key 'mcda_criteria_config' (giữ khi rerender).
  • Nhập DỮ LIỆU THỦ CÔNG từng PA (C2 ngày/nhịp, C3 bãi đúc, tiêu chí custom)
    → session 'mcda_manual_values'.
"""
from . import criteria_config as CC
from . import data_adapter as DA


def get_criteria(st):
    """Bộ tiêu chí hiện hành từ session (khởi tạo mặc định lần đầu)."""
    if "mcda_criteria_config" not in st.session_state:
        st.session_state["mcda_criteria_config"] = CC.default_criteria()
    return st.session_state["mcda_criteria_config"]


def render_criteria_manager(st, criteria):
    """UI bật/tắt + thêm/xóa tiêu chí. Trả bộ tiêu chí sau chỉnh sửa."""
    st.markdown("#### 🧩 Bộ tiêu chí (bật/tắt · thêm · xóa)")
    st.caption("⚠️ Thay đổi tiêu chí (bật/tắt/thêm/xóa) làm ĐỔI ma trận AHP "
               "của nhóm tương ứng — cần KHAI BÁO LẠI so sánh cặp cho nhóm đó "
               "(trọng số mặc định không bị ảnh hưởng).")

    _changed = False
    for g, ten_nhom in CC.GROUPS.items():
        cs = [c for c in criteria if c["nhom"] == g]
        if not cs:
            continue
        st.markdown(f"**Nhóm {ten_nhom}**")
        for c in cs:
            _c1, _c2 = st.columns([5, 1])
            _lbl = (f"{c['ma']} — {c['ten']}"
                    + (" 🧷(tự thêm)" if c.get("custom") else ""))
            _new = _c1.checkbox(_lbl, value=bool(c.get("active")),
                                key=f"mcda_act_{c['ma']}")
            if _new != bool(c.get("active")):
                c["active"] = _new
                _changed = True
            if c.get("custom"):
                if _c2.button("🗑", key=f"mcda_del_{c['ma']}",
                              help="Xóa tiêu chí tự thêm"):
                    criteria.remove(c)
                    st.session_state["mcda_criteria_config"] = criteria
                    st.rerun()

    with st.expander("➕ Thêm tiêu chí mới", expanded=False):
        _ten = st.text_input("Tên tiêu chí", key="mcda_new_ten",
                             placeholder="VD: Kinh nghiệm nhà thầu địa phương")
        _c1, _c2, _c3 = st.columns(3)
        _nhom = _c1.selectbox("Nhóm", list(CC.GROUPS),
                              format_func=lambda g: CC.GROUPS[g],
                              key="mcda_new_nhom")
        _ct = _c2.selectbox("Loại công thức", ["minmax", "threshold"],
                            key="mcda_new_formula",
                            help="Tiêu chí tự thêm loại threshold chấm như "
                                 "minmax trên giá trị nhập tay (0–10).")
        _dir = _c3.selectbox("Hướng tối ưu",
                             ["smaller_better", "larger_better"],
                             format_func=lambda v: ("Nhỏ hơn tốt"
                                                    if v == "smaller_better"
                                                    else "Lớn hơn tốt"),
                             key="mcda_new_dir")
        st.caption("Tiêu chí tự thêm là THỦ CÔNG — nhập giá trị từng phương án "
                   "ở mục 'Dữ liệu thủ công' (tab 📥 Dữ liệu 3 PA).")
        if st.button("➕ Thêm", key="mcda_new_add", type="primary"):
            if not (_ten or "").strip():
                st.warning("Nhập tên tiêu chí trước.")
            else:
                _ma = CC.next_custom_ma(criteria, _nhom)
                criteria.append(dict(
                    ma=_ma, ten=_ten.strip(), nhom=_nhom,
                    formula=_ct, scorer="minmax", direction=_dir,
                    source=None, active=True, custom=True))
                st.session_state["mcda_criteria_config"] = criteria
                st.success(f"Đã thêm {_ma} — {_ten.strip()}. Nhập giá trị "
                           "từng PA ở tab 📥, khai lại AHP nhóm "
                           f"{CC.GROUPS[_nhom]} nếu dùng trọng số tự khai.")
                st.rerun()

    if _changed:
        st.session_state["mcda_criteria_config"] = criteria
        st.info("Đã cập nhật tiêu chí — nếu dùng AHP tự khai, kiểm tra lại "
                "ma trận nhóm liên quan (cặp mới mặc định '1 =').")
    return criteria


def render_manual_inputs(st, du_lieu):
    """Nhập DỮ LIỆU THỦ CÔNG từng PA (C2/C3 + tiêu chí custom) →
    session['mcda_manual_values'][pa_key][field]."""
    criteria = get_criteria(st)
    _manual_fields = [("ngay_thi_cong_nhip", "Ngày thi công / nhịp (C2)"),
                      ("dien_tich_bai_duc", "Diện tích bãi đúc m² (C3)")]
    _manual_fields += [(f"manual_{c['ma']}", f"{c['ma']} — {c['ten']}")
                       for c in criteria if c.get("custom") and c.get("active")]
    if not _manual_fields:
        return
    mv = dict(st.session_state.get("mcda_manual_values") or {})
    with st.expander("✍️ Dữ liệu thủ công (hệ thống không tự có — "
                     "C2, C3, tiêu chí tự thêm)", expanded=False):
        st.caption("Không nhập → tiêu chí tương ứng BỊ BỎ QUA khi chấm "
                   "(không tự điền mặc định gây sai lệch).")
        for fld, lbl in _manual_fields:
            st.markdown(f"**{lbl}**")
            cols = st.columns(max(len(du_lieu), 1))
            for col, k in zip(cols, du_lieu):
                cur = (mv.get(k) or {}).get(fld)
                v = col.number_input(
                    du_lieu[k]["label"], min_value=0.0,
                    value=float(cur) if cur not in (None, "") else 0.0,
                    step=1.0, key=f"mcda_mv_{k}_{fld}",
                    help="0 = chưa nhập (bỏ qua tiêu chí)")
                mv.setdefault(k, {})[fld] = (v if v > 0 else None)
    st.session_state["mcda_manual_values"] = mv
