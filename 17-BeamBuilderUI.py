"""
BeamBuilderUI — Streamlit render functions cho tab "Vẽ Chi Tiết Dầm".
Import module này từ 00-Interface.py rồi gọi render_tab().
Không có auto-execution — không gọi st.set_page_config hay st.title ở đây.
"""
from __future__ import annotations
import sys
import pathlib

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Lấy engine từ sys.modules (được load trước bởi caller) ──────────────────
def _get_bb():
    bb = sys.modules.get("BeamBuilder")
    if bb is None:
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "BeamBuilder",
            pathlib.Path(__file__).parent / "17-BeamBuilder.py",
        )
        bb = importlib.util.module_from_spec(_spec)
        sys.modules["BeamBuilder"] = bb
        _spec.loader.exec_module(bb)
    return bb


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

_SNAP_OPTIONS = {
    "Không snap": 0,
    "10 mm": 10,
    "25 mm": 25,
    "50 mm": 50,
    "100 mm": 100,
}
_SEC_COLORS = {
    "constant": "#4488cc",
    "loft": "#cc8844",
    "fill": "#448844",
}
_DARK = "#1a2330"


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════════════════════

def _init_state():
    bb = _get_bb()
    if "bb_model" not in st.session_state:
        st.session_state.bb_model = bb.preset_supert_model()
    if "bb_active_sec" not in st.session_state:
        names = list(st.session_state.bb_model.sections.keys())
        st.session_state.bb_active_sec = names[0] if names else ""
    if "bb_snap" not in st.session_state:
        st.session_state.bb_snap = 50
    if "bb_undo_stack" not in st.session_state:
        st.session_state.bb_undo_stack = []


def _model():
    return st.session_state.bb_model


def _push_undo():
    bb = _get_bb()
    stack = st.session_state.bb_undo_stack
    stack.append(bb.model_to_json(_model()))
    if len(stack) > 30:
        stack.pop(0)


def _undo():
    bb = _get_bb()
    if st.session_state.bb_undo_stack:
        st.session_state.bb_model = bb.model_from_json(
            st.session_state.bb_undo_stack.pop()
        )
        names = list(_model().sections.keys())
        if st.session_state.bb_active_sec not in names:
            st.session_state.bb_active_sec = names[0] if names else ""


def _snap(v: float) -> float:
    g = st.session_state.bb_snap
    return round(v / g) * g if g > 0 else v


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SECTION SKETCHER
# ═══════════════════════════════════════════════════════════════════════════════

def _render_sketcher():
    bb = _get_bb()
    m = _model()
    sec_names = list(m.sections.keys())

    col_list, col_main = st.columns([1, 4])

    with col_list:
        st.markdown("#### Thư viện MCN")
        if sec_names:
            cur_idx = sec_names.index(st.session_state.bb_active_sec) \
                      if st.session_state.bb_active_sec in sec_names else 0
            selected = st.radio("Chọn mặt cắt", options=sec_names,
                                index=cur_idx, key="sec_radio",
                                label_visibility="collapsed")
            st.session_state.bb_active_sec = selected
        else:
            selected = ""

        st.divider()
        new_name = st.text_input("Tên MCN mới", value="", placeholder="vd: D-D",
                                 key="new_sec_name")
        if st.button("➕ Thêm mặt cắt", use_container_width=True):
            n = new_name.strip()
            if not n:
                st.warning("Nhập tên MCN.")
            elif n in m.sections:
                st.warning(f"'{n}' đã tồn tại.")
            else:
                _push_undo()
                m.sections[n] = bb.CrossSection(name=n, outer=[], holes=[], open=False)
                st.session_state.bb_active_sec = n
                st.rerun()

        if len(sec_names) > 1 and selected:
            if st.button(f"🗑 Xoá '{selected}'", use_container_width=True, type="secondary"):
                _push_undo()
                del m.sections[selected]
                st.session_state.bb_active_sec = list(m.sections.keys())[0]
                st.rerun()

        st.divider()
        st.markdown("**Nạp preset**")
        pa, pb, pc = st.columns(3)
        with pa:
            if st.button("A-A", use_container_width=True, help="Preset Super-T A-A"):
                _push_undo()
                ps = bb.preset_supert_AA(); ps.name = selected or "A-A"
                m.sections[ps.name] = ps
                st.session_state.bb_active_sec = ps.name
                st.rerun()
        with pb:
            if st.button("B-B", use_container_width=True, help="Preset Super-T B-B"):
                _push_undo()
                ps = bb.preset_supert_BB(); ps.name = selected or "B-B"
                m.sections[ps.name] = ps
                st.session_state.bb_active_sec = ps.name
                st.rerun()
        with pc:
            if st.button("C-C", use_container_width=True, help="Preset Super-T C-C"):
                _push_undo()
                ps = bb.preset_supert_CC(); ps.name = selected or "C-C"
                m.sections[ps.name] = ps
                st.session_state.bb_active_sec = ps.name
                st.rerun()

        st.divider()
        if st.button("↩ Undo", use_container_width=True,
                     disabled=not st.session_state.bb_undo_stack):
            _undo(); st.rerun()

    with col_main:
        sec = m.sections.get(st.session_state.bb_active_sec)
        if sec is None:
            st.info("Chọn hoặc tạo một mặt cắt.")
            return

        h1, h2, h3 = st.columns([2, 1, 1])
        with h1:
            st.markdown(f"#### Mặt cắt: **{sec.name}**")
        with h2:
            sec.open = st.toggle("Máng hở", value=sec.open, key="sec_open_toggle")
        with h3:
            snap_label = st.selectbox(
                "Snap", options=list(_SNAP_OPTIONS.keys()),
                index=list(_SNAP_OPTIONS.values()).index(st.session_state.bb_snap),
                key="snap_sel", label_visibility="collapsed",
            )
            st.session_state.bb_snap = _SNAP_OPTIONS[snap_label]

        # Canvas
        fig = bb.make_section_fig(sec=sec, snap_grid=st.session_state.bb_snap,
                                   show_grid_pts=True)
        event = st.plotly_chart(fig, use_container_width=True, key="sketch_canvas",
                                on_select="rerun", selection_mode="points")
        if event and hasattr(event, "selection") and event.selection.points:
            pt = event.selection.points[0]
            _push_undo()
            sec.outer.append([_snap(float(pt.get("x", 0))), _snap(float(pt.get("y", 0)))])
            st.rerun()

        # Toolbar
        tc1, tc2, tc3, tc4, tc5, tc6 = st.columns(6)
        with tc1:
            if st.button("⟺ Mirror X", use_container_width=True):
                if sec.outer:
                    _push_undo()
                    mir = bb.poly_mirror_x(sec.outer)
                    sec.outer = bb.poly_close(
                        bb.poly_ensure_ccw(sec.outer + list(reversed(mir))))
                    st.rerun()
        with tc2:
            if st.button("↘ Offset void", use_container_width=True,
                         help="Offset vào 100mm → thêm lỗ void"):
                if len(sec.outer) >= 3:
                    _push_undo()
                    sec.holes.append(
                        bb.poly_close(bb.poly_ensure_cw(bb.poly_offset(sec.outer, 100.0))))
                    st.rerun()
        with tc3:
            if st.button("✂ Vát 20×20", use_container_width=True):
                if len(sec.outer) >= 3:
                    _push_undo()
                    sec.outer = bb.poly_apply_chamfer(sec.outer, 20, 20)
                    st.rerun()
        with tc4:
            if st.button("⊙ Snap all", use_container_width=True):
                if sec.outer and st.session_state.bb_snap > 0:
                    _push_undo()
                    sec.outer = bb.poly_apply_snap(sec.outer, st.session_state.bb_snap)
                    st.rerun()
        with tc5:
            if st.button("↺ Đảo chiều", use_container_width=True):
                if sec.outer:
                    _push_undo(); sec.outer = list(reversed(sec.outer)); st.rerun()
        with tc6:
            if st.button("🗑 Xoá tất cả", use_container_width=True, type="secondary"):
                _push_undo(); sec.outer = []; sec.holes = []; st.rerun()

        # Coordinate table
        st.markdown("**Tọa độ đỉnh** (chỉnh trực tiếp hoặc thêm dòng)")
        col_tbl, col_add = st.columns([3, 1])
        with col_tbl:
            df = pd.DataFrame(
                sec.outer if sec.outer else [[0.0, 0.0]],
                columns=["X (mm)", "Z (mm)"])
            edited = st.data_editor(
                df, num_rows="dynamic", use_container_width=True,
                key=f"ctbl_{sec.name}",
                column_config={
                    "X (mm)": st.column_config.NumberColumn(format="%.0f", step=10.0),
                    "Z (mm)": st.column_config.NumberColumn(format="%.0f", step=10.0),
                })
            if st.button("✔ Áp dụng bảng", type="primary", use_container_width=True):
                _push_undo()
                rows = edited.dropna().values.tolist()
                sec.outer = [[float(r[0]), float(r[1])] for r in rows]
                st.rerun()
        with col_add:
            st.markdown("**Thêm điểm**")
            with st.form("add_pt"):
                g = float(st.session_state.bb_snap or 50)
                ax = st.number_input("X (mm)", value=0.0, step=g)
                az = st.number_input("Z (mm)", value=0.0, step=g)
                if st.form_submit_button("➕ Thêm"):
                    _push_undo()
                    sec.outer.append([_snap(ax), _snap(az)])
                    st.rerun()
            if sec.holes:
                st.markdown("**Lỗ void**")
                for hi in range(len(sec.holes)):
                    if st.button(f"🗑 Lỗ #{hi}", key=f"dh_{hi}", use_container_width=True):
                        _push_undo(); sec.holes.pop(hi); st.rerun()

        # Validate
        result = bb.validate_section(sec)
        for e in result["errors"]:
            st.error(f"⛔ {e}")
        for w in result["warnings"]:
            st.warning(f"⚠ {w}")
        for info in result["infos"]:
            st.success(f"✔ {info}")
        if st.button("💾 Chuẩn hoá & Lưu MCN", type="primary",
                     disabled=bool(result["errors"])):
            _push_undo(); bb.normalize_section(sec)
            st.success(f"Đã lưu '{sec.name}'.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SEGMENT EDITOR
# ═══════════════════════════════════════════════════════════════════════════════

def _timeline_fig(m) -> go.Figure:
    bb = _get_bb()
    segs = m.segments
    if not segs:
        fig = go.Figure()
        fig.update_layout(height=160, template="plotly_dark",
                          paper_bgcolor=_DARK, plot_bgcolor=_DARK)
        return fig

    half = m.length / (2.0 if m.mirror else 1.0)
    fixed = sum(float(s.length) for s in segs if s.length != "fill")
    fills = sum(1 for s in segs if s.length == "fill")
    fill_len = max(0.0, (half - fixed) / fills) if fills else 0.0

    fig = go.Figure()
    y_off = 0.0
    for i, seg in enumerate(segs):
        L = fill_len if seg.length == "fill" else float(seg.length)
        label = (seg.section if seg.type == "constant"
                 else f"{seg.from_sec}→{seg.to_sec}")
        fill_flag = " (fill)" if seg.length == "fill" else ""
        color = _SEC_COLORS.get(seg.type, "#888888")
        y_label = f"Đoạn {i}: {label}{fill_flag}"
        fig.add_trace(go.Scatter(
            x=[y_off, y_off+L, y_off+L, y_off, y_off],
            y=[i-0.4, i-0.4, i+0.4, i+0.4, i-0.4],
            fill="toself", fillcolor=color,
            line=dict(color="white", width=1), mode="lines",
            name=y_label,
            hovertemplate=f"{y_label}<br>L = {L:.0f} mm<extra></extra>",
        ))
        fig.add_annotation(x=(y_off + y_off+L)/2, y=i,
                           text=f"{L:.0f} mm", showarrow=False,
                           font=dict(size=10, color="white"))
        y_off += L

    labels = [f"Đoạn {i}: " +
              (segs[i].section if segs[i].type=="constant"
               else f"{segs[i].from_sec}→{segs[i].to_sec}") +
              (" (fill)" if segs[i].length=="fill" else "")
              for i in range(len(segs))]
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=_DARK, plot_bgcolor=_DARK,
        height=max(200, 50 + len(segs)*50),
        margin=dict(l=200, r=20, t=30, b=40),
        xaxis=dict(title="Vị trí dọc (mm)", showgrid=True),
        yaxis=dict(tickvals=list(range(len(segs))), ticktext=labels, showgrid=False),
        showlegend=False,
    )
    return fig


def _render_segment_editor():
    bb = _get_bb()
    m = _model()
    sec_names = list(m.sections.keys())

    st.markdown("#### Bố trí đoạn dầm theo chiều dài")

    c_info, c_len = st.columns([3, 1])
    with c_info:
        st.caption("**Constant** (xanh): tiết diện không đổi.  "
                   "**Loft** (cam): vuốt giữa 2 MCN.  "
                   "**fill** tự co giãn.")
    with c_len:
        new_len = st.number_input("Chiều dài dầm (mm)", min_value=1000.0,
                                  max_value=100000.0, value=float(m.length),
                                  step=100.0, key="beam_len_input")
        if abs(new_len - m.length) > 0.5:
            m.length = new_len
    m.mirror = st.toggle("Mirror — dầm đối xứng", value=m.mirror, key="mirror_toggle")

    st.plotly_chart(_timeline_fig(m), use_container_width=True, key="timeline_chart")

    mv = bb.validate_model(m)
    for e in mv["errors"]: st.error(f"⛔ {e}")
    for w in mv["warnings"]: st.warning(f"⚠ {w}")

    st.divider()
    st.markdown("**Chỉnh sửa từng đoạn**")

    if not m.segments:
        st.info("Chưa có đoạn. Nhấn 'Thêm đoạn' bên dưới.")
    else:
        def _seg_label(i):
            s = m.segments[i]
            return (f"Đoạn {i}: constant [{s.section}]"
                    if s.type == "constant"
                    else f"Đoạn {i}: loft [{s.from_sec} → {s.to_sec}]")

        active = st.selectbox("Chọn đoạn", list(range(len(m.segments))),
                              format_func=_seg_label, key="seg_sel")
        seg = m.segments[active]

        ec1, ec2 = st.columns(2)
        with ec1:
            new_type = st.selectbox("Loại", ["constant", "loft"],
                                    index=0 if seg.type == "constant" else 1,
                                    key="seg_type")
            seg.type = new_type
            use_fill = st.checkbox("Dùng fill", value=(seg.length == "fill"),
                                   key="seg_fill_cb")
            if use_fill:
                seg.length = "fill"
            else:
                if seg.length == "fill":
                    seg.length = 1000.0
                seg.length = st.number_input("Chiều dài (mm)", min_value=0.0,
                                             max_value=float(m.length),
                                             value=float(seg.length), step=100.0,
                                             key="seg_len")
        with ec2:
            if seg.type == "constant":
                idx = sec_names.index(seg.section) if seg.section in sec_names else 0
                seg.section = st.selectbox("MCN", sec_names, index=idx, key="seg_sec")
            else:
                fi = sec_names.index(seg.from_sec) if seg.from_sec in sec_names else 0
                ti = sec_names.index(seg.to_sec)   if seg.to_sec   in sec_names else 0
                seg.from_sec = st.selectbox("Từ MCN", sec_names, index=fi, key="seg_from")
                seg.to_sec   = st.selectbox("Đến MCN", sec_names, index=ti, key="seg_to")

        ba, bb_, bc, bd = st.columns(4)
        with ba:
            if st.button("🔼 Lên", use_container_width=True, disabled=active == 0):
                _push_undo()
                m.segments.insert(active-1, m.segments.pop(active)); st.rerun()
        with bb_:
            if st.button("🔽 Xuống", use_container_width=True,
                         disabled=active == len(m.segments)-1):
                _push_undo()
                m.segments.insert(active+1, m.segments.pop(active)); st.rerun()
        with bc:
            if st.button("✂ Tách đoạn", use_container_width=True):
                if seg.type == "constant" and seg.length != "fill":
                    _push_undo()
                    L3 = float(seg.length) / 3.0
                    m.segments[active:active+1] = [
                        bb.Segment("constant", section=seg.section, length=L3),
                        bb.Segment("loft", from_sec=seg.section, to_sec=seg.section, length=L3),
                        bb.Segment("constant", section=seg.section, length=L3),
                    ]
                    st.rerun()
        with bd:
            if st.button("🗑 Xoá", use_container_width=True, type="secondary"):
                _push_undo(); m.segments.pop(active); st.rerun()

    st.divider()
    new_type_add = st.radio("Loại đoạn mới", ["constant", "loft"],
                            horizontal=True, key="new_seg_type")
    if st.button("➕ Thêm đoạn", type="primary", use_container_width=True):
        _push_undo()
        if new_type_add == "constant":
            m.segments.append(
                bb.Segment("constant", section=sec_names[0] if sec_names else None, length=1000.0))
        else:
            f = sec_names[0] if len(sec_names) >= 1 else None
            t = sec_names[1] if len(sec_names) >= 2 else f
            m.segments.append(bb.Segment("loft", from_sec=f, to_sec=t, length=900.0))
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — 3D VIEW
# ═══════════════════════════════════════════════════════════════════════════════

def _render_3d_view():
    bb = _get_bb()
    m = _model()

    st.markdown("#### Wireframe 3D + Bản vẽ khai triển")

    mv = bb.validate_model(m)
    for e in mv["errors"]: st.error(f"⛔ {e}")
    if mv["errors"]:
        st.warning("Sửa lỗi trước khi render 3D.")
        return

    with st.spinner("Đang tính loft …"):
        try:
            traces = bb.build_3d_wireframe(m)
        except Exception as ex:
            st.error(f"Lỗi loft: {ex}"); return

    fig3d = go.Figure(data=traces)
    fig3d.update_layout(
        template="plotly_dark", paper_bgcolor=_DARK, height=560,
        margin=dict(l=0, r=0, t=40, b=0),
        title=dict(text="Wireframe dầm — nét CAD", x=0.5,
                   font=dict(size=13, color="#dde3ea")),
        scene=dict(
            xaxis=dict(title="X (mm)", backgroundcolor=_DARK,
                       gridcolor="#2a3a4a", showbackground=True),
            yaxis=dict(title="Y dọc (mm)", backgroundcolor=_DARK,
                       gridcolor="#2a3a4a", showbackground=True),
            zaxis=dict(title="Z (mm)", backgroundcolor=_DARK,
                       gridcolor="#2a3a4a", showbackground=True),
            bgcolor=_DARK, aspectmode="data",
        ),
    )

    c3d, celev = st.columns([2, 1])
    with c3d:
        st.plotly_chart(fig3d, use_container_width=True, key="view3d")
    with celev:
        st.markdown("**Mặt cắt dọc**")
        try:
            st.plotly_chart(bb.make_elevation_fig(m), use_container_width=True,
                            key="elev_view")
        except Exception as ex:
            st.warning(f"Lỗi elevation: {ex}")

        active = st.session_state.get("bb_active_sec")
        if active and active in m.sections:
            st.markdown("**MCN đang chọn**")
            fsec = bb.make_section_fig(sec=m.sections[active], snap_grid=0,
                                       show_grid_pts=False)
            fsec.update_layout(height=260, margin=dict(l=30, r=10, t=20, b=30))
            st.plotly_chart(fsec, use_container_width=True, key="sec_prev")

    # JSON
    st.divider()
    st.markdown("#### Schema JSON")
    cexp, cimp = st.columns(2)
    with cexp:
        js = bb.model_to_json(m)
        st.download_button("⬇ Tải JSON", data=js, file_name="beam_model.json",
                           mime="application/json", use_container_width=True)
        with st.expander("Xem JSON"):
            st.code(js, language="json")
    with cimp:
        up = st.file_uploader("⬆ Nạp JSON", type=["json"], key="json_upload")
        if up is not None:
            try:
                loaded = bb.model_from_json(up.read().decode("utf-8"))
                _push_undo()
                st.session_state.bb_model = loaded
                names = list(loaded.sections.keys())
                st.session_state.bb_active_sec = names[0] if names else ""
                st.success("Đã nạp model từ JSON.")
                st.rerun()
            except Exception as ex:
                st.error(f"Lỗi parse JSON: {ex}")


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def render_tab():
    """Gọi hàm này từ 00-Interface.py hoặc pages/17-VeChiTiet_Dam.py."""
    _init_state()
    tab_mcn, tab_seg, tab_3d = st.tabs([
        "① Mặt Cắt Ngang (MCN)",
        "② Bố Trí Đoạn",
        "③ View 3D & Bản Vẽ",
    ])
    with tab_mcn:
        _render_sketcher()
    with tab_seg:
        _render_segment_editor()
    with tab_3d:
        _render_3d_view()


# ═══════════════════════════════════════════════════════════════════════════════
# CAD SECTION SKETCHER — tích hợp vào tab "Chi tiết dầm SPT"
# ═══════════════════════════════════════════════════════════════════════════════

_SEC_PRESETS = {
    "A-A": ("preset_supert_AA", True),
    "B-B": ("preset_supert_BB", False),
    "C-C": ("preset_supert_CC", False),
}

_QUICK_CMDS = [
    ("PL",       "Polyline",     "Bắt đầu vẽ polyline — click lưới để thêm điểm"),
    ("G",        "Grip/Dời",    "Chọn đỉnh rồi click điểm mới để dời"),
    ("E",        "Xoá đỉnh",   "Click đỉnh để xoá từng điểm"),
    ("C",        "Close",        "Đóng & lưu polyline hiện tại"),
    ("M",        "Mirror X",     "Gương qua X=0"),
    ("O 100",    "Offset void",  "Offset vào 100mm (tạo khoang rỗng)"),
    ("CHA 20,20","Vát 20×20",  "Chamfer góc 20×20mm"),
    ("CLEAR",    "Xoá tất cả", "Xoá mặt cắt hiện tại"),
]


def _cad_key(pfx: str, name: str) -> str:
    return f"cad_{pfx}_{name}"


def _cad_init(pfx: str, bb):
    """Khởi tạo session state CAD cho một prefix (A-A / B-B / C-C)."""
    sk = _cad_key(pfx, "sections")
    if sk not in st.session_state:
        secs = {}
        for sname, (fn, _) in _SEC_PRESETS.items():
            ps = getattr(bb, fn)()
            secs[sname] = ps
        st.session_state[sk] = secs
    if _cad_key(pfx, "active") not in st.session_state:
        st.session_state[_cad_key(pfx, "active")] = "A-A"
    if _cad_key(pfx, "state") not in st.session_state:
        st.session_state[_cad_key(pfx, "state")] = {
            "mode": None, "current_poly": [], "cursor": [0.0, 0.0],
            "snap": 50.0, "grip_selected": None,
        }
    if _cad_key(pfx, "hist") not in st.session_state:
        st.session_state[_cad_key(pfx, "hist")] = []
    if _cad_key(pfx, "undo") not in st.session_state:
        st.session_state[_cad_key(pfx, "undo")] = []


def _cad_push_undo(pfx: str, bb):
    secs = st.session_state[_cad_key(pfx, "sections")]
    import json
    snap = {k: {"outer": s.outer, "holes": s.holes, "open": s.open}
            for k, s in secs.items()}
    stack = st.session_state[_cad_key(pfx, "undo")]
    stack.append(json.dumps(snap))
    if len(stack) > 20:
        stack.pop(0)


def _cad_undo(pfx: str, bb):
    import json
    stack = st.session_state[_cad_key(pfx, "undo")]
    if not stack:
        return
    snap = json.loads(stack.pop())
    secs = st.session_state[_cad_key(pfx, "sections")]
    for k, v in snap.items():
        if k in secs:
            secs[k].outer = v["outer"]
            secs[k].holes = v["holes"]
            secs[k].open  = v["open"]
    cs = st.session_state[_cad_key(pfx, "state")]
    cs["current_poly"] = []; cs["mode"] = None


def _section_fig(sec, height: int = 220, title: str = "") -> "go.Figure":
    """Hiển thị mặt cắt ngang — đường viền sạch, không có điểm đánh dấu."""
    outer = sec.outer if sec.outer else []
    fig = go.Figure()

    if len(outer) >= 2:
        ox = [p[0] for p in outer] + [outer[0][0]]
        oz = [p[1] for p in outer] + [outer[0][1]]
        fig.add_trace(go.Scatter(
            x=ox, y=oz,
            fill="toself", fillcolor="rgba(90,145,190,0.22)",
            line=dict(color="#78b8de", width=2),
            mode="lines", showlegend=False,
            hovertemplate="(%{x:.1f}, %{y:.1f})<extra></extra>",
        ))

    for hole in (sec.holes or []):
        if len(hole) < 2:
            continue
        hx = [p[0] for p in hole] + [hole[0][0]]
        hz = [p[1] for p in hole] + [hole[0][1]]
        fig.add_trace(go.Scatter(
            x=hx, y=hz,
            fill="toself", fillcolor="rgba(15,22,35,0.95)",
            line=dict(color="#cc8866", width=1.5),
            mode="lines", showlegend=False, hoverinfo="none",
        ))

    if outer:
        xs_o = [p[0] for p in outer]; zs_o = [p[1] for p in outer]
        w = max(xs_o) - min(xs_o); h = abs(min(zs_o))
        mx = max(abs(min(xs_o)), abs(max(xs_o)))
        xr = [-mx * 1.18, mx * 1.18]
        zr = [-h * 1.15, h * 0.12]
        fig.add_annotation(
            x=0.5, y=0.04, xref="paper", yref="paper",
            text=f"B={w:.0f}  H={h:.0f} mm",
            showarrow=False, font=dict(size=9, color="#7ab8d9"),
            bgcolor="rgba(0,0,0,0.45)", borderpad=3,
            xanchor="center", yanchor="bottom",
        )
    else:
        xr, zr = [-1300, 1300], [-1900, 200]

    fig.update_layout(
        template="plotly_dark", paper_bgcolor="#1a2330", plot_bgcolor="#1a2330",
        height=height, margin=dict(l=30, r=10, t=28 if title else 12, b=28),
        title=dict(text=title, font=dict(size=12, color="#9ac8e8"), x=0.5) if title else {},
        xaxis=dict(range=xr, showgrid=True, gridcolor="#233040", dtick=200,
                   zeroline=True, zerolinecolor="#3a5a7a", zerolinewidth=1,
                   scaleanchor="y", scaleratio=1, showticklabels=False),
        yaxis=dict(range=zr, showgrid=True, gridcolor="#233040", dtick=200,
                   zeroline=True, zerolinecolor="#3a5a7a", zerolinewidth=1,
                   showticklabels=False),
        showlegend=False,
    )
    return fig


def _side_elevation_fig(m) -> "go.Figure":
    """Elevation figure nhỏ cho cột bên phải."""
    bb = _get_bb()
    try:
        fig = bb.make_elevation_fig(m)
        fig.update_layout(height=200, margin=dict(l=40, r=10, t=25, b=30),
                          title=dict(text="Mặt cắt dọc", font=dict(size=11)))
        return fig
    except Exception:
        fig = go.Figure()
        fig.update_layout(height=200, template="plotly_dark",
                          paper_bgcolor="#1a2330", plot_bgcolor="#1a2330",
                          title=dict(text="Mặt cắt dọc (chưa có dữ liệu)",
                                     font=dict(size=11)))
        return fig


def _side_3d_fig(m) -> "go.Figure":
    """3D wireframe nhỏ."""
    bb = _get_bb()
    try:
        traces = bb.build_3d_wireframe(m)
        fig = go.Figure(data=traces)
        fig.update_layout(
            template="plotly_dark", paper_bgcolor="#1a2330", height=270,
            margin=dict(l=0, r=0, t=25, b=0),
            title=dict(text="3D Wireframe", font=dict(size=11)),
            scene=dict(
                xaxis=dict(title="X", backgroundcolor="#1a2330",
                           gridcolor="#2a3a4a", showbackground=True, showticklabels=False),
                yaxis=dict(title="Y", backgroundcolor="#1a2330",
                           gridcolor="#2a3a4a", showbackground=True, showticklabels=False),
                zaxis=dict(title="Z", backgroundcolor="#1a2330",
                           gridcolor="#2a3a4a", showbackground=True, showticklabels=False),
                bgcolor="#1a2330", aspectmode="data",
            ),
        )
        return fig
    except Exception:
        fig = go.Figure()
        fig.update_layout(height=270, template="plotly_dark",
                          paper_bgcolor="#1a2330", plot_bgcolor="#1a2330",
                          title=dict(text="3D (cần đủ đoạn)", font=dict(size=11)))
        return fig


def _dxf_upload_card(pfx: str, bb, secs: dict, cad_state: dict,
                     hist: list, sec_name: str) -> None:
    """Upload card gọn cho một mặt cắt — không có nút chỉnh sửa."""
    sec = secs[sec_name]
    has_data = bool(sec.outer)
    dot = "●" if has_data else "○"
    dot_color = "#44dd88" if has_data else "#607080"
    st.markdown(
        f"<div style='text-align:center;font-size:13px;font-weight:bold;"
        f"color:{dot_color};margin-bottom:4px'>{dot} Mặt cắt {sec_name}</div>",
        unsafe_allow_html=True,
    )

    # Miniature section preview
    fig_mini = _section_fig(sec, height=170, title="")
    st.plotly_chart(fig_mini, use_container_width=True,
                    key=f"{pfx}_mini_{sec_name}",
                    config={"displayModeBar": False})

    # File uploader
    uploaded = st.file_uploader(
        f"DXF {sec_name}", type=["dxf", "dwg"],
        key=f"{pfx}_dxf_{sec_name}",
        label_visibility="collapsed",
        help="File → Save As → DXF trong AutoCAD (đơn vị mm). Vẽ ở bất kỳ vị trí nào.",
    )
    if uploaded is not None:
        _fp = f"{uploaded.name}_{uploaded.size}"
        _fp_key = f"_dxf_fp_{pfx}_{sec_name}"
        if cad_state.get(_fp_key) != _fp:
            _res = bb.parse_dxf_bytes(uploaded.read())
            if "error" in _res:
                st.error(_res["error"])
                _ents = _res.get("entities")
                if _ents:
                    st.caption(f"Entities: {', '.join(_ents)}")
            else:
                sec.outer = _res["outer"]
                sec.holes = _res["holes"]
                cad_state[_fp_key] = _fp
                _w = _res.get("width_mm", 0)
                _h = _res.get("height_mm", 0)
                hist.append((f"DXF {sec_name}: {uploaded.name}",
                             f"✓ {len(sec.outer)} đỉnh | {_w:.0f}×{_h:.0f}mm"))
                st.rerun()
        else:
            if has_data:
                _ox = [p[0] for p in sec.outer]; _oz = [p[1] for p in sec.outer]
                st.caption(
                    f"✔ {uploaded.name}  \n"
                    f"B={max(_ox)-min(_ox):.0f} H={abs(min(_oz)):.0f} mm | "
                    f"{len(sec.outer)} đỉnh"
                )
    else:
        if not has_data:
            st.caption("Chưa có DXF")


def render_cad_spt_tab(d: dict, pfx: str = "spt"):
    """
    Tab chi tiết dầm Super-T — import mặt cắt ngang từ DXF.
    Layout: 3 upload card (A-A / B-B / C-C) + [vị trí mặt cắt | 3D lớn].
    d   : design_data dict từ session_state
    pfx : prefix tránh collision session-state key
    """
    bb = _get_bb()
    _cad_init(pfx, bb)

    secs      = st.session_state[_cad_key(pfx, "sections")]
    cad_state = st.session_state[_cad_key(pfx, "state")]
    hist      = st.session_state[_cad_key(pfx, "hist")]

    kcn = d.get("kcn_result") or d.get("ai_result") or {}
    H   = float(kcn.get("chieu_cao_dam", 1.75)) * 1000
    L_m = float(kcn.get("chieu_dai", 38.0))
    kc  = float(kcn.get("khoang_cach_dam", 2.2)) * 1000
    L_half = L_m * 1000 / 2  # nửa dầm (mm), dùng mirror=True

    st.markdown(
        f"<div style='font-size:13px;color:#9ac8e8;margin-bottom:6px'>"
        f"Dầm Super-T — L={L_m:.1f}m | H={H:.0f}mm | S={kc:.0f}mm | "
        f"Upload DXF mặt cắt ngang từ AutoCAD (đơn vị mm)</div>",
        unsafe_allow_html=True,
    )

    # ═══ Hàng 1: 3 upload card ════════════════════════════════════════════════
    c_aa, c_bb, c_cc = st.columns(3)
    for col, sname in [(c_aa, "A-A"), (c_bb, "B-B"), (c_cc, "C-C")]:
        with col:
            _dxf_upload_card(pfx, bb, secs, cad_state, hist, sname)

    st.divider()

    # ═══ Hàng 2: Vị trí mặt cắt | 3D lớn ════════════════════════════════════
    col_pos, col_3d = st.columns([1, 3])

    # ── Cột trái: vị trí mặt cắt trên trắc dọc ──────────────────────────────
    with col_pos:
        st.markdown("**Vị trí mặt cắt trên trắc dọc**")
        st.caption(f"(Nhập chiều dài từng đoạn, đơn vị mm. L/2 = {L_half:.0f} mm)")

        # Defaults lần đầu
        cad_state.setdefault("seg_L1", min(300.0,  L_half * 0.02))
        cad_state.setdefault("seg_L2", min(900.0,  L_half * 0.12))
        cad_state.setdefault("seg_L3", 0.0)
        cad_state.setdefault("seg_L4", min(1200.0, L_half * 0.16))

        _seg_defs = [
            ("seg_L1", "L1 — C-C đầu dầm (mm)",   "Đoạn hộp đầu, mặt cắt C-C giữ nguyên"),
            ("seg_L2", "L2 — Vút C-C → A-A (mm)",  "Đoạn haunch, loft từ C-C sang A-A"),
            ("seg_L3", "L3 — A-A giữa (mm)",       "Đoạn A-A giữ nguyên (0 = bỏ qua)"),
            ("seg_L4", "L4 — Vút A-A → B-B (mm)",  "Đoạn haunch loft từ A-A sang B-B"),
        ]
        for _sk, _slabel, _shelp in _seg_defs:
            _val = st.number_input(
                _slabel, min_value=0, max_value=int(L_half),
                value=int(cad_state[_sk]), step=50,
                key=f"{pfx}_{_sk}", help=_shelp,
            )
            cad_state[_sk] = float(_val)

        L1 = cad_state["seg_L1"]; L2 = cad_state["seg_L2"]
        L3 = cad_state["seg_L3"]; L4 = cad_state["seg_L4"]
        L_fill = L_half - L1 - L2 - L3 - L4

        if L_fill < 0:
            st.error(f"Tổng L1+L2+L3+L4 = {L1+L2+L3+L4:.0f} mm > L/2 = {L_half:.0f} mm")
        else:
            st.caption(f"B-B nhịp giữa (fill): {L_fill:.0f} mm")

        # Sơ đồ trắc dọc
        _zones = [
            (L1,   "C-C",      "#4488cc"),
            (L2,   "→ A-A",   "#cc7733"),
            (L3,   "A-A",      "#44aa66"),
            (L4,   "→ B-B",   "#cc7733"),
            (max(L_fill, 0), "B-B",  "#8855cc"),
        ]
        _fig_sch = go.Figure()
        _x0 = 0.0
        for _zlen, _zlabel, _zcol in _zones:
            if _zlen <= 0:
                continue
            _fig_sch.add_shape(
                type="rect", x0=_x0, x1=_x0 + _zlen, y0=0, y1=1,
                fillcolor=f"rgba({int(_zcol[1:3],16)},{int(_zcol[3:5],16)},{int(_zcol[5:7],16)},0.55)",
                line=dict(color="#fff", width=0.5),
            )
            if _zlen > L_half * 0.04:
                _fig_sch.add_annotation(
                    x=_x0 + _zlen / 2, y=0.5, text=_zlabel,
                    showarrow=False, font=dict(size=9, color="#fff"),
                )
            _x0 += _zlen
        _fig_sch.update_layout(
            template="plotly_dark", paper_bgcolor="#1a2330", plot_bgcolor="#1a2330",
            height=65, margin=dict(l=10, r=10, t=4, b=22),
            xaxis=dict(range=[0, L_half], showgrid=False,
                       tickformat=".0f", tickfont=dict(size=8),
                       title=dict(text="mm từ đầu dầm", font=dict(size=8))),
            yaxis=dict(visible=False), showlegend=False,
        )
        st.plotly_chart(_fig_sch, use_container_width=True,
                        key=f"{pfx}_sch_fig",
                        config={"displayModeBar": False})

    # ── Cột phải: 3D wireframe lớn ────────────────────────────────────────────
    with col_3d:
        L1 = cad_state["seg_L1"]; L2 = cad_state["seg_L2"]
        L3 = cad_state["seg_L3"]; L4 = cad_state["seg_L4"]
        L_fill = L_half - L1 - L2 - L3 - L4
        _avail = {k: v for k, v in secs.items() if v.outer}

        try:
            if len(_avail) < 1:
                st.info("Upload ít nhất 1 mặt cắt để xem 3D preview.", icon="ℹ")
            elif L_fill < 0:
                st.warning("Điều chỉnh L1–L4 sao cho tổng ≤ L/2.")
            else:
                m3d = bb.BeamModel(length=L_m * 1000, mirror=True)
                m3d.sections = {k: v.clone() for k, v in _avail.items()}

                # Build segments theo L1–L4, chỉ thêm nếu section tồn tại
                _segs = []
                def _has(*names):
                    return all(n in m3d.sections for n in names)

                if L1 > 0 and _has("C-C"):
                    _segs.append(bb.Segment("constant", section="C-C", length=L1))
                elif L1 > 0 and _has("A-A"):
                    _segs.append(bb.Segment("constant", section="A-A", length=L1))

                if L2 > 0:
                    if _has("C-C", "A-A"):
                        _segs.append(bb.Segment("loft", from_sec="C-C", to_sec="A-A", length=L2))
                    elif _has("A-A"):
                        _segs.append(bb.Segment("constant", section="A-A", length=L2))

                if L3 > 0 and _has("A-A"):
                    _segs.append(bb.Segment("constant", section="A-A", length=L3))

                if L4 > 0:
                    if _has("A-A", "B-B"):
                        _segs.append(bb.Segment("loft", from_sec="A-A", to_sec="B-B", length=L4))
                    elif _has("B-B"):
                        _segs.append(bb.Segment("constant", section="B-B", length=L4))

                # Fill với section tốt nhất có
                _mid_sec = "B-B" if "B-B" in m3d.sections else (
                           "A-A" if "A-A" in m3d.sections else
                           next(iter(m3d.sections)))
                _segs.append(bb.Segment("constant", section=_mid_sec, length="fill"))
                m3d.segments = _segs

                _traces = bb.build_3d_wireframe(m3d)
                _fig3d = go.Figure(data=_traces)
                _fig3d.update_layout(
                    template="plotly_dark", paper_bgcolor="#1a2330",
                    height=600, margin=dict(l=0, r=0, t=35, b=0),
                    title=dict(
                        text="3D Wireframe — Dầm Super-T",
                        font=dict(size=13, color="#9ac8e8"), x=0.5,
                    ),
                    scene=dict(
                        xaxis=dict(title="X (mm)", backgroundcolor="#12202e",
                                   gridcolor="#2a3a4a", showbackground=True),
                        yaxis=dict(title="Y — dọc dầm (mm)", backgroundcolor="#12202e",
                                   gridcolor="#2a3a4a", showbackground=True),
                        zaxis=dict(title="Z (mm)", backgroundcolor="#12202e",
                                   gridcolor="#2a3a4a", showbackground=True),
                        bgcolor="#12202e", aspectmode="data",
                        camera=dict(eye=dict(x=1.4, y=-1.6, z=0.9)),
                    ),
                )
                st.plotly_chart(_fig3d, use_container_width=True,
                                key=f"{pfx}_3d_large",
                                config={"displayModeBar": True,
                                        "modeBarButtonsToRemove": ["toImage"]})

        except Exception as _e3d:
            st.error(f"Không tạo được 3D: {_e3d}")
