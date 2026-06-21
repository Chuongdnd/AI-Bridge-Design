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
    ("PL",       "Polyline",     "Bắt đầu vẽ polyline"),
    ("C",        "Close",        "Đóng & lưu polyline"),
    ("M",        "Mirror X",     "Gương qua X=0"),
    ("O 100",    "Offset void",  "Offset vào 100mm (tạo khoang rỗng)"),
    ("CHA 20,20","Vát 20×20",   "Chamfer góc 20×20mm"),
    ("CLEAR",    "Xoá tất cả",  "Xoá mặt cắt hiện tại"),
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
            "snap": 50.0,
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


def _canvas_fig(sec, cad_state: dict) -> "go.Figure":
    """Canvas MCN: outer + in-progress polyline + cursor marker."""
    bb = _get_bb()

    outer = sec.outer if sec.outer else []
    snap  = float(cad_state.get("snap", 0))

    # Axis ranges — auto-fit to section with margin
    all_pts = list(outer) + cad_state.get("current_poly", [])
    if all_pts:
        xs_all = [p[0] for p in all_pts]
        zs_all = [p[1] for p in all_pts]
        margin_x = max(200, (max(xs_all)-min(xs_all))*0.25)
        margin_z = max(200, (max(zs_all)-min(zs_all))*0.25)
        xr = [min(xs_all)-margin_x, max(xs_all)+margin_x]
        zr = [min(zs_all)-margin_z, max(zs_all)+margin_z]
    else:
        xr, zr = [-1400, 1400], [-1900, 300]

    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="#1a2330", plot_bgcolor="#1a2330",
        height=520, margin=dict(l=50, r=10, t=30, b=45),
        xaxis=dict(range=xr, title="X (mm)", showgrid=True, gridcolor="#233040",
                   dtick=100, zeroline=True, zerolinecolor="#4da6d9", zerolinewidth=1.5,
                   scaleanchor="y", scaleratio=1),
        yaxis=dict(range=zr, title="Z (mm)", showgrid=True, gridcolor="#233040",
                   dtick=100, zeroline=True, zerolinecolor="#4da6d9", zerolinewidth=1.5),
        showlegend=False,
    )

    # Committed outer
    if len(outer) >= 2:
        ox = [p[0] for p in outer] + [outer[0][0]]
        oz = [p[1] for p in outer] + [outer[0][1]]
        fig.add_trace(go.Scatter(
            x=ox, y=oz,
            fill="toself", fillcolor="rgba(90,145,190,0.18)",
            line=dict(color="#78b8de", width=2), mode="lines+markers",
            marker=dict(size=6, color="#66ee99", symbol="circle"),
            hovertemplate="P%{pointNumber}: (%{x:.0f}, %{y:.0f})<extra></extra>",
        ))
        # Đánh số đỉnh
        for i, (px, pz) in enumerate(outer):
            fig.add_annotation(x=px, y=pz, text=str(i), showarrow=False,
                               font=dict(size=8, color="#66ee99"),
                               bgcolor="rgba(0,0,0,0.6)", yshift=9,
                               xanchor="center", yanchor="bottom")

    # Holes
    for hi, hole in enumerate(sec.holes or []):
        if len(hole) < 2:
            continue
        hx = [p[0] for p in hole] + [hole[0][0]]
        hz = [p[1] for p in hole] + [hole[0][1]]
        fig.add_trace(go.Scatter(
            x=hx, y=hz,
            fill="toself", fillcolor="rgba(180,60,60,0.22)",
            line=dict(color="#cc6666", width=1.5, dash="dot"),
            mode="lines", name=f"Lỗ #{hi}",
            hovertemplate=f"Lỗ #{hi} (%{{x:.0f}}, %{{y:.0f}})<extra></extra>",
        ))

    # In-progress polyline (dashed, lighter)
    wip = cad_state.get("current_poly", [])
    if len(wip) >= 2:
        fig.add_trace(go.Scatter(
            x=[p[0] for p in wip], y=[p[1] for p in wip],
            mode="lines+markers",
            line=dict(color="#ffcc44", width=1.5, dash="dash"),
            marker=dict(size=5, color="#ffcc44"),
            hovertemplate="WIP (%{x:.0f}, %{y:.0f})<extra></extra>",
        ))
    # Cursor marker
    cur = cad_state.get("cursor", [0.0, 0.0])
    fig.add_trace(go.Scatter(
        x=[cur[0]], y=[cur[1]], mode="markers",
        marker=dict(size=10, color="#ff6644", symbol="cross"),
        hovertemplate=f"Cursor ({cur[0]:.0f}, {cur[1]:.0f})<extra></extra>",
    ))

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


def render_cad_spt_tab(d: dict, pfx: str = "spt"):
    """
    Tab chi tiết dầm Super-T với CAD command-line section sketcher.
    Thay thế các bản vẽ tĩnh bằng giao diện vẽ tương tác.
    d : design_data dict từ session_state
    pfx: prefix để tránh collision session-state key
    """
    bb  = _get_bb()
    _cad_init(pfx, bb)

    secs       = st.session_state[_cad_key(pfx, "sections")]
    active_sec = st.session_state[_cad_key(pfx, "active")]
    cad_state  = st.session_state[_cad_key(pfx, "state")]
    hist       = st.session_state[_cad_key(pfx, "hist")]
    sec        = secs.get(active_sec)

    # Lấy thông số dầm từ design_data để hiển thị
    kcn = d.get("kcn_result") or d.get("ai_result") or {}
    H   = float(kcn.get("chieu_cao_dam", 1.75)) * 1000   # mm
    L   = float(kcn.get("chieu_dai", 38.0))
    kc  = float(kcn.get("khoang_cach_dam", 2.2)) * 1000

    # ── Header bar ──────────────────────────────────────────────────────────
    hc1, hc2, hc3, hc4 = st.columns([3, 2, 1, 1])
    with hc1:
        st.markdown(
            f"**Super-T** — L={L:.1f}m | H={H:.0f}mm | S={kc:.0f}mm"
        )
    with hc2:
        new_active = st.radio(
            "Mặt cắt", list(secs.keys()),
            index=list(secs.keys()).index(active_sec),
            horizontal=True, key=f"{pfx}_sec_radio",
            label_visibility="collapsed",
        )
        if new_active != active_sec:
            st.session_state[_cad_key(pfx, "active")] = new_active
            cad_state["mode"] = None; cad_state["current_poly"] = []
            st.rerun()
    with hc3:
        open_toggle = st.toggle("Máng hở", value=sec.open,
                                key=f"{pfx}_open_toggle")
        if open_toggle != sec.open:
            _cad_push_undo(pfx, bb); sec.open = open_toggle
    with hc4:
        if st.button("↩ Undo", key=f"{pfx}_undo_btn",
                     disabled=not st.session_state[_cad_key(pfx, "undo")]):
            _cad_undo(pfx, bb); st.rerun()

    # ── 3 cột chính ─────────────────────────────────────────────────────────
    col_cmd, col_canvas, col_views = st.columns([1, 3, 1])

    # ── Cột trái: CAD command line ──────────────────────────────────────────
    with col_cmd:
        # Mode indicator
        mode = cad_state.get("mode")
        cur  = cad_state.get("cursor", [0.0, 0.0])
        snap = cad_state.get("snap", 50.0)
        n_wip = len(cad_state.get("current_poly", []))

        mode_text  = f"**{mode.upper()}**" if mode else "—"
        snap_text  = f"{snap:.0f} mm" if snap > 0 else "Tắt"
        st.markdown(
            f"<div style='background:#111820;border:1px solid #2a4060;"
            f"border-radius:6px;padding:8px;font-size:12px;font-family:monospace'>"
            f"<span style='color:#4da6d9'>Lệnh:</span> {mode_text}<br>"
            f"<span style='color:#4da6d9'>Cursor:</span> ({cur[0]:.0f}, {cur[1]:.0f})<br>"
            f"<span style='color:#4da6d9'>WIP pts:</span> {n_wip}<br>"
            f"<span style='color:#4da6d9'>Snap:</span> {snap_text}"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Command history (last 15 lines)
        hist_text = "\n".join(
            f"{'>' if i % 2 == 0 else ' '} {line}"
            for i, line in enumerate(
                [item for pair in hist[-8:] for item in pair]
            )
        ) if hist else "(Chưa có lệnh)"
        st.markdown(
            f"<div style='background:#0d141c;border:1px solid #1e3050;"
            f"border-radius:4px;padding:6px 8px;font-size:11px;"
            f"font-family:monospace;height:220px;overflow-y:auto;"
            f"white-space:pre;color:#b0c8dc'>{hist_text}</div>",
            unsafe_allow_html=True,
        )

        # Command input
        def _submit():
            cmd = st.session_state.get(f"{pfx}_cmd_input", "").strip()
            if not cmd:
                return
            if cmd.upper() in ("U", "UNDO"):
                _cad_undo(pfx, bb)
                hist.append((cmd, "↩ Undo"))
            else:
                _cad_push_undo(pfx, bb)
                result = bb.process_cad_command(cmd, sec, cad_state)
                hist.append((cmd, result))
            st.session_state[f"{pfx}_cmd_input"] = ""

        st.text_input(
            "Lệnh CAD:",
            key=f"{pfx}_cmd_input",
            on_change=_submit,
            placeholder="PL  /  0,0  /  @490,0  /  C  /  ?",
            label_visibility="visible",
        )

        # Quick command buttons
        st.markdown("<div style='font-size:11px;color:#7090a0;margin-top:4px'>Nhanh:</div>",
                    unsafe_allow_html=True)
        for qcmd, qlabel, qtip in _QUICK_CMDS:
            if st.button(qlabel, key=f"{pfx}_q_{qcmd.replace(' ','_')}",
                         help=f"{qcmd} — {qtip}", use_container_width=True):
                _cad_push_undo(pfx, bb)
                result = bb.process_cad_command(qcmd, sec, cad_state)
                hist.append((qcmd, result))
                st.rerun()

        # Validate
        vr = bb.validate_section(sec)
        for e in vr["errors"]:
            st.error(e, icon="⛔")
        for info in vr["infos"]:
            st.caption(f"✔ {info}")

    # ── Cột giữa: Canvas MCN ────────────────────────────────────────────────
    with col_canvas:
        st.markdown(f"**Mặt cắt {active_sec}** — Dầm Super-T S=2200mm")
        fig_canvas = _canvas_fig(sec, cad_state)
        st.plotly_chart(fig_canvas, use_container_width=True,
                        key=f"{pfx}_canvas_{active_sec}",
                        config={"scrollZoom": True, "displayModeBar": True,
                                "modeBarButtonsToRemove": ["select2d", "lasso2d"]})

        # Bảng tọa độ (nhỏ, collapsible)
        with st.expander(f"Bảng tọa độ ({len(sec.outer)} đỉnh)", expanded=False):
            if sec.outer:
                df_coord = pd.DataFrame(sec.outer, columns=["X (mm)", "Z (mm)"])
                edited = st.data_editor(
                    df_coord, num_rows="dynamic", use_container_width=True,
                    key=f"{pfx}_coord_tbl_{active_sec}",
                    column_config={
                        "X (mm)": st.column_config.NumberColumn(format="%.0f", step=10.0),
                        "Z (mm)": st.column_config.NumberColumn(format="%.0f", step=10.0),
                    },
                )
                if st.button("✔ Áp dụng bảng", key=f"{pfx}_apply_tbl",
                             type="primary"):
                    _cad_push_undo(pfx, bb)
                    rows = edited.dropna().values.tolist()
                    sec.outer = [[float(r[0]), float(r[1])] for r in rows]
                    st.rerun()
            else:
                st.info("Chưa có đỉnh. Dùng lệnh PL để vẽ.")

    # ── Cột phải: Elevation + 3D ────────────────────────────────────────────
    with col_views:
        # Xây BeamModel từ các section hiện tại để preview
        try:
            m_preview = bb.BeamModel(length=L * 1000, mirror=True)
            m_preview.sections = {k: v.clone() for k, v in secs.items()
                                   if v.outer}
            m_preview.segments = [
                bb.Segment("constant", section="C-C", length=300.0),
                bb.Segment("loft", from_sec="C-C", to_sec="A-A", length=900.0),
                bb.Segment("loft", from_sec="A-A", to_sec="B-B", length=1200.0),
                bb.Segment("constant", section="B-B", length="fill"),
            ]
        except Exception:
            m_preview = None

        st.markdown("**Mặt cắt dọc**")
        if m_preview and len(m_preview.sections) >= 2:
            st.plotly_chart(_side_elevation_fig(m_preview),
                            use_container_width=True,
                            key=f"{pfx}_elev_view",
                            config={"displayModeBar": False})
        else:
            st.caption("(Cần ≥ 2 mặt cắt)")

        st.markdown("**Wireframe 3D**")
        if m_preview and len(m_preview.sections) >= 2:
            st.plotly_chart(_side_3d_fig(m_preview),
                            use_container_width=True,
                            key=f"{pfx}_3d_view",
                            config={"displayModeBar": False})
        else:
            st.caption("(Cần ≥ 2 mặt cắt)")
