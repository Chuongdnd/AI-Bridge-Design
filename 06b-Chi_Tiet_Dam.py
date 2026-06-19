"""
Module 06b — Giao diện Chi Tiết Dầm (Streamlit)
Cung cấp giao diện tinh chỉnh thông số hình học dầm với kiểm tra ràng buộc trực tiếp.

Hàm xuất công khai:
  render_beam_detail_panel(geo, loai_dam, key_prefix, cong_nghe) → None

Phụ thuộc:
  06b-Draw_Beam_Sections.py  — vẽ tiết diện Plotly
  06c-Beam_Validator.py      — kiểm tra ràng buộc
"""

from __future__ import annotations
import os
import copy
import importlib.util
from datetime import datetime
from typing import Any

import streamlit as st

_DIR = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────────────────────────────────────
# Lazy import — tên file có dấu gạch ngang, không dùng import thông thường
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "beam_validator", os.path.join(_DIR, "06c-Beam_Validator.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@st.cache_resource(show_spinner=False)
def _load_drawer():
    spec = importlib.util.spec_from_file_location(
        "draw_beam", os.path.join(_DIR, "06b-Draw_Beam_Sections.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─────────────────────────────────────────────────────────────────────────────
# Session State helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sk(prefix: str, name: str) -> str:
    return f"{prefix}_{name}"


def _init_state(key_prefix: str, geo_default: dict, loai_dam: str,
                cong_nghe: str) -> None:
    if _sk(key_prefix, "geo") not in st.session_state:
        st.session_state[_sk(key_prefix, "geo")]     = copy.deepcopy(geo_default)
    if _sk(key_prefix, "val") not in st.session_state:
        st.session_state[_sk(key_prefix, "val")]     = None
    if _sk(key_prefix, "history") not in st.session_state:
        st.session_state[_sk(key_prefix, "history")] = []
    if _sk(key_prefix, "loai") not in st.session_state:
        st.session_state[_sk(key_prefix, "loai")]    = loai_dam
    if _sk(key_prefix, "cn") not in st.session_state:
        st.session_state[_sk(key_prefix, "cn")]      = cong_nghe


def _get_nested(d: dict, key_path: str) -> Any:
    parts = key_path.split(".")
    for p in parts:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def _set_nested(d: dict, key_path: str, value: Any) -> None:
    parts = key_path.split(".")
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = value


def _run_validation(key_prefix: str) -> None:
    validator = _load_validator()
    geo   = st.session_state[_sk(key_prefix, "geo")]
    loai  = st.session_state[_sk(key_prefix, "loai")]
    cn    = st.session_state[_sk(key_prefix, "cn")]
    val   = validator.validate_beam_geometry(geo, loai, cn)
    st.session_state[_sk(key_prefix, "val")] = val


# ─────────────────────────────────────────────────────────────────────────────
# Danh sách thông số hiển thị theo loại dầm
# ─────────────────────────────────────────────────────────────────────────────

def _param_defs(loai_dam: str) -> list[dict]:
    """Trả về danh sách dict {label, key, min, max, step} cho form chỉnh sửa."""
    common_h = [
        {"label": "Chiều cao dầm H (mm)",         "key": "H",                      "min": 100, "max": 5000, "step": 10},
        {"label": "H cánh trên (mm)",              "key": "MC_AA.H_canh_tren",      "min": 50,  "max": 500,  "step": 5},
        {"label": "H vát cánh trên (mm)",          "key": "MC_AA.H_vat_canh_tren",  "min": 0,   "max": 200,  "step": 5},
        {"label": "H bụng (mm)",                   "key": "MC_AA.H_bung",           "min": 100, "max": 3000, "step": 10},
        {"label": "H vát cánh dưới (mm)",          "key": "MC_AA.H_vat_canh_duoi",  "min": 0,   "max": 200,  "step": 5},
        {"label": "H cánh dưới (mm)",              "key": "MC_AA.H_canh_duoi",      "min": 0,   "max": 500,  "step": 5},
    ]
    dul_common = [
        {"label": "Đường kính ống cáp ∅ (mm)",    "key": "cap_DUL.ong_PVC_D",      "min": 20,  "max": 120,  "step": 1},
        {"label": "Số ống cáp DUL",                "key": "cap_DUL.so_ong",          "min": 1,   "max": 30,   "step": 1},
    ]

    if loai_dam == "Super-T":
        return common_h + [
            {"label": "B bụng trên B_bung_top (mm)",  "key": "MC_AA.B_bung_top",    "min": 80,  "max": 300,  "step": 5},
            {"label": "B bụng dưới B_bung_bot (mm)",  "key": "MC_AA.B_bung_bot",    "min": 100, "max": 300,  "step": 5},
            {"label": "B khoang rỗng trên (mm)",       "key": "MC_AA.B_rong_tren",   "min": 100, "max": 2000, "step": 10},
            {"label": "B khoang rỗng dưới (mm)",       "key": "MC_AA.B_rong_duoi",   "min": 100, "max": 2000, "step": 10},
            {"label": "Đoạn đặc đầu dầm (mm)",        "key": "MC_BB.L_dau_dac",     "min": 0,   "max": 2000, "step": 50},
        ] + dul_common

    elif loai_dam in ("Dầm I", "T ngược", "Dầm T"):
        return common_h + [
            {"label": "B bụng dầm (mm)",               "key": "MC_AA.B_bung",        "min": 100, "max": 500,  "step": 5},
        ] + dul_common

    elif loai_dam == "Dầm bản rỗng":
        return common_h + [
            {"label": "Đường kính lỗ rỗng ∅ (mm)",    "key": "MC_AA.B_rong",        "min": 100, "max": 800,  "step": 10},
            {"label": "Số lỗ rỗng",                    "key": "MC_AA.so_rong",        "min": 1,   "max": 10,   "step": 1},
            {"label": "Khoảng cách tim lỗ (mm)",       "key": "MC_AA.kc_rong",        "min": 100, "max": 1000, "step": 10},
            {"label": "Tâm lỗ từ đáy y_rong (mm)",    "key": "MC_AA.y_rong",         "min": 50,  "max": 1000, "step": 10},
        ] + dul_common

    return common_h + dul_common


# ─────────────────────────────────────────────────────────────────────────────
# Render: Panel kiểm tra ràng buộc
# ─────────────────────────────────────────────────────────────────────────────

def _render_validation_panel(key_prefix: str) -> None:
    val = st.session_state.get(_sk(key_prefix, "val"))
    if val is None:
        st.info("Nhấn **Kiểm tra** để chạy kiểm tra ràng buộc hình học.")
        return

    errs  = val.get("errors", [])
    warns = val.get("warnings", [])
    infos = val.get("info_messages", [])
    ok    = not val["co_loi_nghiem_trong"]

    # Tóm tắt
    if ok and not warns:
        st.success(f"✅ Hình học hợp lệ — {len(infos)} kiểm tra đạt, 0 lỗi, 0 cảnh báo")
    elif ok:
        st.warning(f"🟡 {len(warns)} cảnh báo kỹ thuật — không có lỗi nghiêm trọng")
    else:
        st.error(f"🔴 {len(errs)} lỗi nghiêm trọng — cần sửa trước khi lưu")

    # Lỗi nghiêm trọng
    if errs:
        with st.expander(f"🔴 Lỗi nghiêm trọng ({len(errs)})", expanded=True):
            for e in errs:
                cols = st.columns([5, 2])
                cols[0].markdown(
                    f"**{e['ten_kiem_tra']}**  \n"
                    f"{e['mo_ta_loi']}  \n"
                    f"*Tham chiếu: {e['tham_chieu_tieu_chuan']}*"
                )
                if e.get("param_key") and e.get("gia_tri_de_xuat"):
                    if cols[1].button(
                        f"Sửa tự động", key=f"{key_prefix}_fix_{e['param_key']}",
                        help=f"Đặt {e['param_key']} = {e['gia_tri_de_xuat']}"
                    ):
                        _auto_fix(key_prefix, e["param_key"], e["gia_tri_de_xuat"])
                        _run_validation(key_prefix)
                        st.rerun()
                st.divider()

    # Cảnh báo
    if warns:
        with st.expander(f"🟡 Cảnh báo ({len(warns)})", expanded=len(errs) == 0):
            for w in warns:
                cols = st.columns([5, 2])
                cols[0].markdown(
                    f"**{w['ten_kiem_tra']}**  \n"
                    f"{w['mo_ta_loi']}  \n"
                    f"Hiện tại: `{w['gia_tri_hien_tai']}` → Đề xuất: `{w.get('gia_tri_de_xuat', 'N/A')}`"
                )
                if w.get("param_key") and w.get("gia_tri_de_xuat"):
                    if cols[1].button(
                        "Áp dụng", key=f"{key_prefix}_fix_{w['param_key']}",
                        help=f"Đặt {w['param_key']} = {w['gia_tri_de_xuat']}"
                    ):
                        _auto_fix(key_prefix, w["param_key"], w["gia_tri_de_xuat"])
                        _run_validation(key_prefix)
                        st.rerun()
                st.divider()

    # Thông tin đạt
    if infos:
        with st.expander(f"🔵 Thông tin xác nhận ({len(infos)})"):
            for inf in infos:
                st.markdown(f"✔ **{inf['ten_kiem_tra']}** — {inf['mo_ta_loi']}")


def _auto_fix(key_prefix: str, param_key: str, de_xuat_str: str) -> None:
    """Tách số nguyên từ chuỗi đề xuất và cập nhật vào geo."""
    import re
    nums = re.findall(r"-?\d+", str(de_xuat_str))
    if not nums:
        return
    value = int(nums[0])
    geo = st.session_state[_sk(key_prefix, "geo")]
    _set_nested(geo, param_key, value)


# ─────────────────────────────────────────────────────────────────────────────
# Render: Tabs bản vẽ
# ─────────────────────────────────────────────────────────────────────────────

def _render_drawing_tabs(key_prefix: str) -> None:
    drawer = _load_drawer()
    geo    = st.session_state[_sk(key_prefix, "geo")]
    loai   = st.session_state[_sk(key_prefix, "loai")]

    if loai == "Super-T":
        tab_labels = ["Mặt cắt A-A", "Mặt cắt B-B", "Mặt cắt C-C", "Mặt cắt dọc"]
        tabs = st.tabs(tab_labels)
        fns  = [
            drawer.draw_supert_AA,
            drawer.draw_supert_BB,
            drawer.draw_supert_CC,
            drawer.draw_supert_longitudinal,
        ]
        for tab, fn in zip(tabs, fns):
            with tab:
                try:
                    fig = fn(geo)
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as ex:
                    st.warning(f"Không thể vẽ: {ex}")
    else:
        with st.container():
            try:
                fig = drawer.draw_beam_section(loai, geo)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as ex:
                st.warning(f"Không thể vẽ tiết diện: {ex}")


# ─────────────────────────────────────────────────────────────────────────────
# Render: Form chỉnh sửa thông số
# ─────────────────────────────────────────────────────────────────────────────

def _render_param_editor(key_prefix: str) -> None:
    geo   = st.session_state[_sk(key_prefix, "geo")]
    loai  = st.session_state[_sk(key_prefix, "loai")]
    defs  = _param_defs(loai)

    st.markdown("#### Thông số hình học")
    changed = False

    for p in defs:
        pkey  = p["key"]
        cur   = _get_nested(geo, pkey)
        if cur is None:
            continue
        cur = int(cur) if isinstance(cur, float) and cur == int(cur) else cur

        wkey = f"{key_prefix}_input_{pkey.replace('.', '_')}"
        new_val = st.number_input(
            p["label"],
            min_value=p["min"], max_value=p["max"], step=p["step"],
            value=int(cur),
            key=wkey,
        )
        if new_val != cur:
            _set_nested(geo, pkey, new_val)
            changed = True

    if changed:
        _run_validation(key_prefix)

    st.markdown("---")
    if st.button("🔍 Kiểm tra ràng buộc", key=f"{key_prefix}_btn_check",
                 use_container_width=True):
        _run_validation(key_prefix)
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Render: Nút hành động (bị khóa khi có lỗi)
# ─────────────────────────────────────────────────────────────────────────────

def _render_action_buttons(key_prefix: str) -> None:
    val  = st.session_state.get(_sk(key_prefix, "val"), {}) or {}
    lock = val.get("co_loi_nghiem_trong", False)
    geo  = st.session_state[_sk(key_prefix, "geo")]
    loai = st.session_state[_sk(key_prefix, "loai")]

    if lock:
        st.warning("🔒 Các nút hành động bị khóa do có lỗi nghiêm trọng. Hãy sửa lỗi trước.")

    cols = st.columns(3)

    # Lưu cấu hình
    if cols[0].button("💾 Lưu cấu hình", key=f"{key_prefix}_btn_save",
                      disabled=lock, use_container_width=True):
        ten = datetime.now().strftime("%H:%M:%S")
        history: list = st.session_state[_sk(key_prefix, "history")]
        history.append({
            "timestamp"        : datetime.now().isoformat(),
            "ten_phien_ban"    : ten,
            "beam_params"      : copy.deepcopy(geo),
            "ket_qua_validation": copy.deepcopy(val),
            "ghi_chu"          : f"Lưu tự động — {loai}",
        })
        st.success(f"Đã lưu phiên bản lúc {ten}")
        st.rerun()

    # Áp dụng & đồng bộ toàn bộ hệ thống
    if cols[1].button("🔄 Áp dụng & Đồng bộ", key=f"{key_prefix}_btn_sync",
                      disabled=lock, use_container_width=True,
                      help="Cập nhật beam_params_final và đồng bộ 3D / DXF / IFC"):
        cn = st.session_state.get(_sk(key_prefix, "cn"), "DUL_sau")
        sync_all_modules(key_prefix, cn)
        st.rerun()

    # Xuất DXF (nhanh, không qua sync_all)
    if cols[2].button("📐 Xuất DXF", key=f"{key_prefix}_btn_dxf",
                      disabled=lock, use_container_width=True,
                      help="Xuất bản vẽ chi tiết dầm sang DXF"):
        cn = st.session_state.get(_sk(key_prefix, "cn"), "DUL_sau")
        sync_all_modules(key_prefix, cn, do_ifc=False)
        st.rerun()

    # Tải báo cáo kiểm tra
    if val:
        validator = _load_validator()
        L_m = geo.get("L", 0) / 1000.0
        report_md = validator.generate_validation_report(
            val, loai_dam=loai, L_m=L_m)
        st.download_button(
            "📄 Tải báo cáo kiểm tra (.md)",
            data=report_md.encode("utf-8"),
            file_name=f"kiem_tra_dam_{loai.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
            key=f"{key_prefix}_btn_report",
            use_container_width=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Render: Lịch sử phiên bản
# ─────────────────────────────────────────────────────────────────────────────

def _render_version_history(key_prefix: str) -> None:
    history: list = st.session_state.get(_sk(key_prefix, "history"), [])
    if not history:
        st.info("Chưa có phiên bản nào được lưu. Nhấn 'Lưu cấu hình' để bắt đầu.")
        return

    st.markdown(f"**{len(history)} phiên bản đã lưu**")
    for i, h in enumerate(reversed(history)):
        idx   = len(history) - 1 - i    # chỉ số thực trong list
        val_h = h.get("ket_qua_validation") or {}
        n_err = len(val_h.get("errors", []))
        n_wrn = len(val_h.get("warnings", []))
        status_icon = "✅" if n_err == 0 else "❌"

        cols = st.columns([3, 1, 1, 1, 1])
        cols[0].markdown(
            f"**{h['ten_phien_ban']}** — {h['ghi_chu']}  \n"
            f"{status_icon} {n_err} lỗi · {n_wrn} cảnh báo"
        )

        if cols[1].button("Khôi phục", key=f"{key_prefix}_hist_restore_{idx}"):
            st.session_state[_sk(key_prefix, "geo")] = copy.deepcopy(h["beam_params"])
            st.session_state[_sk(key_prefix, "val")] = copy.deepcopy(h["ket_qua_validation"])
            st.success(f"Đã khôi phục phiên bản {h['ten_phien_ban']}")
            st.rerun()

        if cols[2].button("So sánh", key=f"{key_prefix}_hist_compare_{idx}"):
            st.session_state[f"{key_prefix}_compare_idx"] = idx
            st.info(f"So sánh phiên bản {h['ten_phien_ban']} với cấu hình hiện tại:")
            _show_comparison(key_prefix, idx)

        if cols[3].button("Xóa", key=f"{key_prefix}_hist_delete_{idx}"):
            history.pop(idx)
            st.rerun()

        validator = _load_validator()
        L_m = h["beam_params"].get("L", 0) / 1000.0
        report_md = validator.generate_validation_report(
            h["ket_qua_validation"] or {}, loai_dam=h["ghi_chu"], L_m=L_m,
            ten_phien_ban=h["ten_phien_ban"])
        cols[4].download_button(
            "📄", data=report_md.encode("utf-8"),
            file_name=f"baocao_{h['ten_phien_ban'].replace(':','')}.md",
            mime="text/markdown",
            key=f"{key_prefix}_hist_dl_{idx}",
            help="Tải báo cáo phiên bản này",
        )
        st.divider()


def _show_comparison(key_prefix: str, hist_idx: int) -> None:
    history = st.session_state.get(_sk(key_prefix, "history"), [])
    if hist_idx >= len(history):
        return
    h     = history[hist_idx]
    cur   = st.session_state[_sk(key_prefix, "geo")]
    loai  = st.session_state[_sk(key_prefix, "loai")]
    defs  = _param_defs(loai)

    rows = []
    for p in defs:
        old_v = _get_nested(h["beam_params"], p["key"])
        new_v = _get_nested(cur, p["key"])
        if old_v != new_v:
            rows.append({"Thông số": p["label"],
                         "Phiên bản cũ": old_v, "Hiện tại": new_v})
    if rows:
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.info("Không có thay đổi nào.")


# ─────────────────────────────────────────────────────────────────────────────
# Hàm xuất chính
# ─────────────────────────────────────────────────────────────────────────────

def render_beam_detail_panel(geo: dict, loai_dam: str,
                             key_prefix: str = "beamdet",
                             cong_nghe: str = "DUL_sau") -> None:
    """
    Render giao diện chi tiết dầm: chỉnh sửa thông số, kiểm tra ràng buộc,
    bản vẽ tiết diện, lịch sử phiên bản.

    Parameters
    ----------
    geo        : dict  — từ get_beam_geometry_detail() (dữ liệu khởi đầu)
    loai_dam   : str   — "Super-T" | "Dầm I" | ... (chỉ đọc, không cho đổi tại đây)
    key_prefix : str   — namespace cho st.session_state (mặc định "beamdet")
    cong_nghe  : str   — "DUL_truoc" | "DUL_sau"
    """
    _init_state(key_prefix, geo, loai_dam, cong_nghe)

    # Nếu geo ngoài thay đổi (ví dụ user chọn nhịp khác), reset state
    stored_geo = st.session_state[_sk(key_prefix, "geo")]
    if stored_geo.get("L") != geo.get("L") or stored_geo.get("H") != geo.get("H"):
        st.session_state[_sk(key_prefix, "geo")] = copy.deepcopy(geo)
        st.session_state[_sk(key_prefix, "val")] = None

    L_m = geo.get("L", 0) / 1000.0
    st.markdown(f"### Chi tiết dầm **{loai_dam}** — L = {L_m:.1f}m")

    # ── Chạy kiểm tra lần đầu nếu chưa có ──
    if st.session_state[_sk(key_prefix, "val")] is None:
        _run_validation(key_prefix)

    # ── Layout chính: trái = editor, phải = kiểm tra + bản vẽ ──
    col_edit, col_right = st.columns([1, 2], gap="medium")

    with col_edit:
        _render_param_editor(key_prefix)
        st.markdown("---")
        _render_action_buttons(key_prefix)

    with col_right:
        _render_validation_panel(key_prefix)
        st.markdown("---")
        _render_drawing_tabs(key_prefix)

    # ── Lịch sử phiên bản (toàn chiều rộng phía dưới) ──
    with st.expander("📚 Lịch sử phiên bản", expanded=False):
        _render_version_history(key_prefix)


# =============================================================================
# PART 1 — Single source of truth: get_beam_params_final()
# =============================================================================

def get_beam_params_final(key_prefix: str = "beamdet") -> dict | None:
    """
    Trả về thông số dầm đã được xác nhận (beam_params_final) từ session state.

    Tất cả các module khác PHẢI gọi hàm này để lấy thông số dầm.
    Không được đọc trực tiếp từ catalog hay tự tính lại.

    Returns None nếu người dùng chưa nhấn "Áp dụng & Đồng bộ".
    """
    return st.session_state.get("beam_params_final")


# =============================================================================
# PART 6 — Orchestrator: sync_all_modules()
# =============================================================================

@st.cache_resource(show_spinner=False)
def _load_beam3d():
    spec = importlib.util.spec_from_file_location(
        "beam3d", os.path.join(_DIR, "04b-Beam3D.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@st.cache_resource(show_spinner=False)
def _load_export():
    spec = importlib.util.spec_from_file_location(
        "export_cad", os.path.join(_DIR, "09-Export_CAD_IFC.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _init_sync_status() -> None:
    if "sync_status" not in st.session_state:
        st.session_state["sync_status"] = {
            "module_04_3d"       : {"status": "not_generated", "last_sync": None, "hash": None},
            "module_09_dxf"      : {"status": "not_generated", "last_sync": None, "hash": None},
            "module_09_ifc"      : {"status": "not_generated", "last_sync": None, "hash": None},
            "module_11_drawings" : {"status": "not_generated", "last_sync": None, "hash": None},
        }


def _params_hash(geo: dict) -> str:
    import hashlib, json
    raw = json.dumps(geo, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()[:8]


def sync_all_modules(key_prefix: str = "beamdet",
                     cong_nghe: str = "DUL_sau",
                     do_dxf: bool = True,
                     do_ifc: bool = True) -> None:
    """
    Đồng bộ beam_params_final tới tất cả module phụ thuộc.

    Trình tự:
      1. Validate — dừng nếu có lỗi nghiêm trọng
      2. Lưu vào st.session_state["beam_params_final"]
      3. Dựng mô hình 3D (04b-Beam3D)
      4. Xuất DXF nếu do_dxf (09-Export_CAD_IFC)
      5. Xuất IFC nếu do_ifc (09-Export_CAD_IFC)
      6. Cập nhật sync_status + file_paths
      7. Hiển thị tóm tắt kết quả
    """
    _init_sync_status()
    geo  = st.session_state.get(_sk(key_prefix, "geo"))
    loai = st.session_state.get(_sk(key_prefix, "loai"), "Super-T")

    if geo is None:
        st.error("Không tìm thấy thông số dầm trong session state.")
        return

    # ── Bước 1: Validate ──
    _run_validation(key_prefix)
    val = st.session_state.get(_sk(key_prefix, "val"), {})
    if val.get("co_loi_nghiem_trong"):
        n_err = len(val.get("errors", []))
        st.error(f"🔴 Có {n_err} lỗi nghiêm trọng — không thể đồng bộ. Hãy sửa lỗi trước.")
        return

    # ── Bước 2: Lưu beam_params_final ──
    geo_final = copy.deepcopy(geo)
    geo_final["loai_dam"]  = loai
    geo_final["cong_nghe"] = cong_nghe
    st.session_state["beam_params_final"] = geo_final
    geo_hash = _params_hash(geo_final)
    now_iso  = datetime.now().isoformat()

    file_paths: dict[str, str] = {}
    status     = st.session_state["sync_status"]

    # ── Bước 3: Dựng mô hình 3D ──
    with st.spinner("🏗️ Đang dựng mô hình 3D..."):
        try:
            beam3d_mod = _load_beam3d()
            result3d   = beam3d_mod.rebuild_3D_model_from_params(geo_final, loai)
            st.session_state["beam3d_result"]  = result3d
            st.session_state["beam3d_plotly"]  = result3d["plotly"]
            status["module_04_3d"] = {
                "status": "synced", "last_sync": now_iso, "hash": geo_hash}
        except Exception as ex:
            st.warning(f"⚠️ Mô hình 3D: {ex}")
            status["module_04_3d"]["status"] = "error"

    # ── Bước 4: Xuất DXF ──
    if do_dxf:
        with st.spinner("📐 Đang xuất DXF..."):
            try:
                export_mod = _load_export()
                dxf_bytes  = export_mod.generate_dxf_from_beam_params(
                    geo_final, loai, cong_nghe)
                st.session_state["beam_dxf_bytes"] = dxf_bytes
                status["module_09_dxf"] = {
                    "status": "synced", "last_sync": now_iso, "hash": geo_hash}
            except Exception as ex:
                st.warning(f"⚠️ Xuất DXF: {ex}")
                status["module_09_dxf"]["status"] = "error"

    # ── Bước 5: Xuất IFC ──
    if do_ifc:
        with st.spinner("🏛️ Đang xuất IFC..."):
            try:
                export_mod = _load_export()
                ifc_bytes  = export_mod.generate_ifc_from_beam_params(
                    geo_final, loai, cong_nghe)
                st.session_state["beam_ifc_bytes"] = ifc_bytes
                status["module_09_ifc"] = {
                    "status": "synced", "last_sync": now_iso, "hash": geo_hash}
            except Exception as ex:
                st.warning(f"⚠️ Xuất IFC: {ex}")
                status["module_09_ifc"]["status"] = "error"

    # ── Bước 6: Cập nhật Module 11 ──
    status["module_11_drawings"] = {
        "status": "synced", "last_sync": now_iso, "hash": geo_hash}

    # ── Bước 7: Báo cáo ──
    stats = st.session_state.get("beam3d_result", {}).get("stats", {})
    n_ok  = sum(1 for m in status.values() if m["status"] == "synced")
    n_err = sum(1 for m in status.values() if m["status"] == "error")

    if n_err == 0:
        st.success(
            f"✅ Đồng bộ hoàn tất — {n_ok} module cập nhật  \n"
            f"Diện tích: {stats.get('dien_tich_m2', 0):.4f} m²  |  "
            f"Trọng lượng: {stats.get('trong_luong_tan', 0):.2f} tấn  |  "
            f"L/H = {stats.get('LH_ratio', 0):.2f}"
        )
    else:
        st.warning(f"⚠️ Đồng bộ một phần — {n_ok} thành công, {n_err} lỗi")

    # ── Nút tải file ──
    col_dl1, col_dl2, col_dl3 = st.columns(3)
    dxf_b = st.session_state.get("beam_dxf_bytes")
    ifc_b = st.session_state.get("beam_ifc_bytes")
    ts    = datetime.now().strftime("%Y%m%d_%H%M")
    loai_fn = loai.replace(" ", "_").replace("ầ", "a").replace("ỗ", "o")

    if dxf_b:
        col_dl1.download_button(
            "📐 Tải DXF", data=dxf_b,
            file_name=f"dam_{loai_fn}_{ts}.dxf",
            mime="application/octet-stream",
            key=f"{key_prefix}_dl_dxf",
            use_container_width=True,
        )
    if ifc_b:
        col_dl2.download_button(
            "🏛️ Tải IFC", data=ifc_b,
            file_name=f"dam_{loai_fn}_{ts}.ifc",
            mime="application/octet-stream",
            key=f"{key_prefix}_dl_ifc",
            use_container_width=True,
        )

    rpt_md = generate_sync_report(geo_final, val, status, file_paths)
    col_dl3.download_button(
        "📄 Báo cáo đồng bộ (.md)", data=rpt_md.encode("utf-8"),
        file_name=f"sync_report_{ts}.md",
        mime="text/markdown",
        key=f"{key_prefix}_dl_rpt",
        use_container_width=True,
    )


# =============================================================================
# PART 7 — Sync status widget
# =============================================================================

_STATUS_ICON = {
    "synced"       : "🟢",
    "out_of_sync"  : "🟡",
    "not_generated": "⚪",
    "error"        : "🔴",
}
_MODULE_LABEL = {
    "module_04_3d"       : "Mô hình 3D",
    "module_09_dxf"      : "DXF bản vẽ",
    "module_09_ifc"      : "IFC/BIM",
    "module_11_drawings" : "Bản vẽ KCN",
}


def render_sync_status_widget() -> None:
    """
    Hiển thị widget trạng thái đồng bộ (thường đặt trong sidebar).
    Gọi sau khi page render hoàn tất.
    """
    _init_sync_status()
    status = st.session_state.get("sync_status", {})

    with st.expander("🔄 Trạng thái đồng bộ", expanded=False):
        for mod_key, mod_status in status.items():
            icon  = _STATUS_ICON.get(mod_status["status"], "❓")
            label = _MODULE_LABEL.get(mod_key, mod_key)
            ts    = mod_status.get("last_sync")
            ts_str = ts[:16].replace("T", " ") if ts else "—"
            st.markdown(f"{icon} **{label}** — {ts_str}")

        bpf = st.session_state.get("beam_params_final")
        if bpf:
            L_m = bpf.get("L", 0) / 1000.0
            st.caption(
                f"beam_params_final: {bpf.get('loai_dam', '?')} "
                f"L={L_m:.1f}m H={bpf.get('H', 0)}mm"
            )
        else:
            st.caption("beam_params_final: chưa có — nhấn 'Áp dụng & Đồng bộ'")


def mark_params_changed(module_keys: list[str] | None = None) -> None:
    """
    Đánh dấu các module là out_of_sync khi beam_params thay đổi
    nhưng chưa đồng bộ.  Gọi khi người dùng chỉnh sửa thông số.
    """
    _init_sync_status()
    keys = module_keys or list(st.session_state["sync_status"].keys())
    for k in keys:
        if st.session_state["sync_status"][k]["status"] == "synced":
            st.session_state["sync_status"][k]["status"] = "out_of_sync"


# =============================================================================
# PART 8 — Sync report (markdown + download)
# =============================================================================

def generate_sync_report(beam_params: dict, val_result: dict,
                         sync_status: dict, file_paths: dict) -> str:
    """
    Tạo báo cáo đồng bộ đầy đủ (Markdown).

    Sections:
      1. Thông tin phiên bản + timestamp
      2. Bảng thông số đầy đủ
      3. Trạng thái đồng bộ từng module
      4. Thuộc tính tính toán (diện tích, trọng lượng, L/H)
      5. Kết quả validation
      6. Ghi chú tự do
    """
    loai    = beam_params.get("loai_dam", "?")
    L_m     = beam_params.get("L", 0) / 1000.0
    H_mm    = beam_params.get("H", 0)
    S_mm    = beam_params.get("S", 0)
    mc      = beam_params.get("MC_AA", {})
    cap     = beam_params.get("cap_DUL", {})
    cn      = beam_params.get("cong_nghe", "DUL_sau")
    ts      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    stats3d = st.session_state.get("beam3d_result", {}).get("stats", {})

    lines = [
        "# Báo cáo Đồng bộ Thông số Dầm",
        "",
        f"**Thời gian xuất:** {ts}  ",
        f"**Loại dầm:** {loai}  ",
        f"**Công nghệ:** {cn}  ",
        "",
        "---",
        "",
        "## 1. Thông số Hình học",
        "",
        "| Thông số | Giá trị |",
        "| --- | --- |",
        f"| Nhịp tính toán L | {L_m:.3f} m ({beam_params.get('L', 0)} mm) |",
        f"| Chiều cao dầm H | {H_mm} mm |",
        f"| Khoảng cách tim dầm S | {S_mm} mm |",
    ]

    if mc:
        lines += [
            f"| B cánh trên | {mc.get('B_canh_tren', '—')} mm |",
            f"| H cánh trên | {mc.get('H_canh_tren', '—')} mm |",
            f"| H bụng | {mc.get('H_bung', '—')} mm |",
            f"| B cánh dưới | {mc.get('B_canh_duoi', '—')} mm |",
            f"| H cánh dưới | {mc.get('H_canh_duoi', '—')} mm |",
        ]
        if loai == "Super-T":
            lines += [
                f"| B bụng trên (B_bung_top) | {mc.get('B_bung_top', '—')} mm |",
                f"| B bụng dưới (B_bung_bot) | {mc.get('B_bung_bot', '—')} mm |",
                f"| B khoang rỗng trên | {mc.get('B_rong_tren', '—')} mm |",
                f"| B khoang rỗng dưới | {mc.get('B_rong_duoi', '—')} mm |",
            ]
        else:
            lines.append(f"| B bụng | {mc.get('B_bung', '—')} mm |")

    if cap:
        lines += [
            f"| Số ống cáp DUL | {cap.get('so_ong', 0)} ống |",
            f"| Đường kính ống cáp | Ø{cap.get('ong_PVC_D', 49)} mm |",
            f"| Lực căng yêu cầu | {cap.get('luc_can_thiet', 0):.1f} kN |",
        ]

    lines += [
        "",
        "---",
        "",
        "## 2. Thuộc tính Tính toán",
        "",
        "| Thuộc tính | Giá trị |",
        "| --- | --- |",
        f"| Diện tích mặt cắt | {stats3d.get('dien_tich_m2', '—')} m² |",
        f"| Thể tích bê tông | {stats3d.get('the_tich_m3', '—')} m³ |",
        f"| Trọng lượng dầm | {stats3d.get('trong_luong_tan', '—')} tấn |",
        f"| Tải trọng bản thân | {stats3d.get('trong_luong_kN_m', '—')} kN/m |",
        f"| Tỉ số L/H | {stats3d.get('LH_ratio', round(L_m * 1000 / max(H_mm, 1), 2))} |",
        "",
        "---",
        "",
        "## 3. Trạng thái Đồng bộ Module",
        "",
        "| Module | Trạng thái | Lần cuối đồng bộ | Hash |",
        "| --- | --- | --- | --- |",
    ]

    for mod_key, mod_s in sync_status.items():
        icon   = _STATUS_ICON.get(mod_s["status"], "❓")
        label  = _MODULE_LABEL.get(mod_key, mod_key)
        ts_mod = (mod_s.get("last_sync") or "—")[:16].replace("T", " ")
        h      = mod_s.get("hash") or "—"
        lines.append(f"| {label} | {icon} {mod_s['status']} | {ts_mod} | `{h}` |")

    # Files generated
    if file_paths:
        lines += ["", "---", "", "## 4. File đã xuất", ""]
        for k, p in file_paths.items():
            lines.append(f"- **{k}**: `{p}`")

    # Validation results
    errs  = (val_result or {}).get("errors", [])
    warns = (val_result or {}).get("warnings", [])
    infos = (val_result or {}).get("info_messages", [])

    lines += [
        "",
        "---",
        "",
        "## 5. Kết quả Kiểm tra Ràng buộc",
        "",
        f"- 🔴 Lỗi nghiêm trọng: {len(errs)}",
        f"- 🟡 Cảnh báo: {len(warns)}",
        f"- 🔵 Thông tin đạt: {len(infos)}",
        "",
    ]
    for e in errs:
        lines.append(f"  - **[LỖI]** {e['ten_kiem_tra']}: {e['mo_ta_loi']}")
    for w in warns:
        lines.append(f"  - **[CẢNH BÁO]** {w['ten_kiem_tra']}: {w['mo_ta_loi']}")

    lines += [
        "",
        "---",
        "",
        "## 6. Ghi chú",
        "",
        "> *Báo cáo được tạo tự động bởi AI Bridge Design — UTH*  ",
        "> *Tiêu chuẩn áp dụng: TCVN 11823:2017*  ",
        f"> *Bê tông: C50 | Cáp DUL: {cn}*",
        "",
    ]

    return "\n".join(lines)
