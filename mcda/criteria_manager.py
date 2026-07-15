"""
mcda/criteria_manager.py — Quản lý bộ tiêu chí dạng BẢNG EXCEL (st.data_editor):
  • SỬA trực tiếp mọi tiêu chí (kể cả tiêu chí sẵn có): tên, nhóm, công thức,
    hướng tối ưu, bật/tắt.
  • THÊM dòng mới ngay trên bảng (num_rows="dynamic") → tiêu chí custom, mã tự
    sinh theo nhóm; XÓA dòng bất kỳ (bộ mặc định khôi phục bằng nút Reset).
  • Mọi thay đổi PERSIST vào session 'mcda_criteria_config' NGAY trong lượt
    chạy → tab Trọng số AHP + Kết quả cập nhật tức thì. Thêm/bớt tiêu chí →
    key ma trận AHP nhóm đổi theo bộ mã → tự yêu cầu khai lại (cặp mới '1 =').
  • Nhập DỮ LIỆU THỦ CÔNG từng PA (C2/C3 + tiêu chí custom/threshold thiếu
    nguồn) → session 'mcda_manual_values'.
"""
import pandas as pd

from . import criteria_config as CC

_DIR_LBL = {"smaller_better": "Nhỏ hơn tốt", "larger_better": "Lớn hơn tốt",
            None: "—", "": "—"}
_DIR_VAL = {"Nhỏ hơn tốt": "smaller_better", "Lớn hơn tốt": "larger_better",
            "—": None}
_GRP_VAL = {v: k for k, v in CC.GROUPS.items()}

# Scorer threshold GỐC của tiêu chí mặc định (khôi phục khi đổi lại công thức)
_DEFAULT_SCORER = {c["ma"]: c["scorer"] for c in CC.default_criteria()}
_DEFAULT_SOURCE = {c["ma"]: c["source"] for c in CC.default_criteria()}


def get_criteria(st):
    """Bộ tiêu chí hiện hành từ session (khởi tạo mặc định lần đầu)."""
    if "mcda_criteria_config" not in st.session_state:
        st.session_state["mcda_criteria_config"] = CC.default_criteria()
    return st.session_state["mcda_criteria_config"]


def _to_df(criteria):
    return pd.DataFrame([{
        "Mã":        c["ma"],
        "Tiêu chí":  c["ten"],
        "Nhóm":      CC.GROUPS.get(c["nhom"], c["nhom"]),
        "Công thức": c.get("formula", "minmax"),
        "Hướng":     _DIR_LBL.get(c.get("direction"), "—"),
        "Bật":       bool(c.get("active")),
        "Tự thêm":   bool(c.get("custom")),
    } for c in criteria])


def _rebuild(criteria, edited_df):
    """Dựng lại bộ tiêu chí từ bảng đã sửa. Trả (criteria_mới, có_thêm_bớt)."""
    by_ma = {c["ma"]: c for c in criteria}
    new_list, structural = [], False
    for _, row in edited_df.iterrows():
        ma = str(row.get("Mã") or "").strip()
        ten = str(row.get("Tiêu chí") or "").strip()
        nhom = _GRP_VAL.get(str(row.get("Nhóm") or ""), None)
        formula = str(row.get("Công thức") or "minmax")
        direction = _DIR_VAL.get(str(row.get("Hướng") or "—"))
        active = bool(row.get("Bật"))
        if not ten and not ma:                      # dòng trống → bỏ
            continue
        if ma and ma in by_ma:                      # SỬA tiêu chí có sẵn
            c = dict(by_ma[ma])
            c["ten"] = ten or c["ten"]
            if nhom and nhom != c["nhom"]:
                c["nhom"] = nhom; structural = True   # đổi nhóm → AHP nhóm đổi
            if formula != c.get("formula"):
                c["formula"] = formula
                # threshold gốc (A1, C1…) khôi phục scorer riêng; còn lại minmax
                c["scorer"] = (_DEFAULT_SCORER.get(ma, "minmax")
                               if formula == "threshold" else "minmax")
            if formula == "minmax":
                c["direction"] = direction or "smaller_better"
            else:
                c["direction"] = direction
            if active != bool(c.get("active")):
                c["active"] = active; structural = True
            new_list.append(c)
        else:                                       # THÊM dòng mới → custom
            if not ten or not nhom:
                continue                            # thiếu tên/nhóm → chờ nhập đủ
            new_ma = CC.next_custom_ma(list(by_ma.values()) + new_list, nhom)
            new_list.append(dict(
                ma=new_ma, ten=ten, nhom=nhom, formula=formula,
                scorer="minmax", direction=direction or "smaller_better",
                source=None, active=active if row.get("Bật") is not None else True,
                custom=True))
            structural = True
    # XÓA: mã cũ không còn trong bảng
    kept = {c["ma"] for c in new_list}
    if any(ma not in kept for ma in by_ma):
        structural = True
    return new_list, structural


def render_criteria_manager(st, criteria):
    """BẢNG tiêu chí kiểu Excel — sửa/thêm/xóa trực tiếp trên bảng."""
    st.markdown("#### 🧩 Bộ tiêu chí — bảng thao tác trực tiếp")
    st.caption("Sửa Ô để đổi tên/nhóm/công thức/hướng/bật-tắt; **➕ dòng cuối** "
               "để thêm tiêu chí (mã tự sinh theo nhóm); chọn dòng rồi 🗑 để "
               "xóa. ⚠️ Thêm/bớt/đổi nhóm → cần KHAI LẠI so sánh cặp AHP của "
               "nhóm đó (trọng số mặc định không ảnh hưởng). Tiêu chí tự thêm "
               "nhập giá trị từng PA ở '✍️ Dữ liệu thủ công' (tab 📥).")

    edited = st.data_editor(
        _to_df(criteria), num_rows="dynamic", hide_index=True,
        use_container_width=True, key="mcda_crit_editor",
        column_config={
            "Mã": st.column_config.TextColumn(
                "Mã", disabled=True, help="Tự sinh theo nhóm (A/B/C/D + số)"),
            "Tiêu chí": st.column_config.TextColumn("Tiêu chí", required=False),
            "Nhóm": st.column_config.SelectboxColumn(
                "Nhóm", options=list(CC.GROUPS.values()), required=False),
            "Công thức": st.column_config.SelectboxColumn(
                "Công thức", options=["threshold", "minmax"],
                help="threshold = ngưỡng cố định (chỉ tiêu chí gốc có công "
                     "thức riêng); minmax = chuẩn hóa giữa 3 PA"),
            "Hướng": st.column_config.SelectboxColumn(
                "Hướng", options=["Nhỏ hơn tốt", "Lớn hơn tốt", "—"],
                help="Chỉ dùng cho công thức minmax"),
            "Bật": st.column_config.CheckboxColumn("Bật"),
            "Tự thêm": st.column_config.CheckboxColumn("Tự thêm", disabled=True),
        })

    new_criteria, structural = _rebuild(criteria, edited)
    if new_criteria != criteria:
        st.session_state["mcda_criteria_config"] = new_criteria
        if structural:
            # Bảng cần vẽ lại với MÃ vừa sinh / dòng đã xóa → reset state editor
            st.session_state.pop("mcda_crit_editor", None)
            st.info("Đã cập nhật bộ tiêu chí — ma trận AHP nhóm liên quan đổi "
                    "theo (cặp mới mặc định '1 ='); dùng AHP tự khai thì kiểm "
                    "tra lại tab ⚖️.")
            st.rerun()
        criteria = new_criteria

    if st.button("🔄 Khôi phục bộ tiêu chí mặc định (10 tiêu chí gốc)",
                 key="mcda_crit_reset"):
        st.session_state["mcda_criteria_config"] = CC.default_criteria()
        st.session_state.pop("mcda_crit_editor", None)
        st.rerun()
    return criteria


def render_manual_inputs(st, du_lieu):
    """Nhập DỮ LIỆU THỦ CÔNG từng PA (C2/C3 + tiêu chí custom) →
    session['mcda_manual_values'][pa_key][field]."""
    criteria = get_criteria(st)
    _manual_fields = []
    for c in criteria:
        if not c.get("active"):
            continue
        if c["ma"] == "C2":
            _manual_fields.append(("ngay_thi_cong_nhip",
                                   "Ngày thi công / nhịp (C2)"))
        elif c["ma"] == "C3":
            _manual_fields.append(("dien_tich_bai_duc",
                                   "Diện tích bãi đúc m² (C3)"))
        elif c.get("custom"):
            _manual_fields.append((f"manual_{c['ma']}",
                                   f"{c['ma']} — {c['ten']}"))
    if not _manual_fields:
        return
    mv = dict(st.session_state.get("mcda_manual_values") or {})
    with st.expander("✍️ Dữ liệu thủ công (hệ thống không tự có — "
                     "C2, C3, tiêu chí tự thêm)", expanded=False):
        st.caption("Không nhập (=0) → tiêu chí tương ứng BỊ BỎ QUA khi chấm "
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
