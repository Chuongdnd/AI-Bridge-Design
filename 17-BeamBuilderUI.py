"""
BeamBuilderUI — Streamlit render functions cho tab "Vẽ Chi Tiết Dầm".
Import module này từ 00-Interface.py rồi gọi render_tab().
Không có auto-execution — không gọi st.set_page_config hay st.title ở đây.
"""
from __future__ import annotations
import json
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


def _get_ifc_exporter():
    """Lazy-load 18-IFC_Exporter.py."""
    import importlib.util as _ifc_util
    _spec = _ifc_util.spec_from_file_location(
        "ifc_exporter18",
        pathlib.Path(__file__).parent / "18-IFC_Exporter.py",
    )
    if _spec is None:
        return None
    mod = _ifc_util.module_from_spec(_spec)
    try:
        _spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# PERSISTENCE — lưu/tải mặt cắt mặc định
# ═══════════════════════════════════════════════════════════════════════════════

_SAVE_FILE = pathlib.Path(__file__).parent / "spt_sections_saved.json"


def _save_defaults(secs: dict, cad_state: dict) -> str:
    """Ghi mặt cắt + cấu hình đoạn ra file JSON bên cạnh script.
    Trả về thông báo kết quả.
    """
    data: dict = {
        "sections": {
            name: {"outer": sec.outer, "holes": sec.holes}
            for name, sec in secs.items()
            if sec.outer          # chỉ lưu mặt cắt đã có dữ liệu
        },
        "segs":     cad_state.get("segs", []),
        "fill_sec": cad_state.get("fill_sec", "B-B"),
    }
    try:
        _SAVE_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        n = len(data["sections"])
        return f"✅ Đã lưu {n} mặt cắt vào {_SAVE_FILE.name}"
    except Exception as _e:
        return f"❌ Không lưu được: {_e}"


def _load_defaults(bb) -> dict | None:
    """Đọc file JSON đã lưu. Trả về dict hoặc None nếu không có / lỗi."""
    if not _SAVE_FILE.exists():
        return None
    try:
        raw = json.loads(_SAVE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    secs_out: dict = {}
    for name, v in raw.get("sections", {}).items():
        sec = bb.CrossSection(name=name, outer=[], holes=[], open=False)
        sec.outer = v.get("outer", [])
        sec.holes = v.get("holes", [])
        secs_out[name] = sec
    if not secs_out:
        return None
    return {
        "secs":     secs_out,
        "segs":     raw.get("segs", []),
        "fill_sec": raw.get("fill_sec", "B-B"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DRAG-RESIZE — inject CSS + JS để kéo thả thay đổi kích thước khung nhìn
# ═══════════════════════════════════════════════════════════════════════════════

def _inject_resize_js() -> None:
    """Chèn CSS resize handle và JS ResizeObserver vào trang.

    • CSS thêm tay cầm kéo (▼) ở góc dưới phải mỗi khung Plotly.
    • JS (qua parent.document) lắng nghe resize container và gọi
      Plotly.Plots.resize() để chart tự điều chỉnh.
    • MutationObserver giúp tự áp dụng lại sau mỗi Streamlit rerun.
    """
    # CSS — mỗi plotly chart có thể kéo dọc
    st.markdown("""
<style>
[data-testid="stPlotlyChart"] {
    resize: vertical !important;
    overflow: hidden !important;
    min-height: 80px !important;
    border-bottom: 2px solid rgba(68,136,204,0.18);
    transition: border-color 0.15s;
}
[data-testid="stPlotlyChart"]:hover {
    border-bottom-color: rgba(68,136,204,0.55);
}
[data-testid="stPlotlyChart"]::-webkit-resizer {
    background: linear-gradient(135deg,
        transparent 55%, rgba(68,136,204,0.7) 55%);
    border-radius: 0 0 2px 0;
}
</style>
""", unsafe_allow_html=True)

    # JS — theo dõi resize container → reflow Plotly chart
    st.components.v1.html("""
<script>
(function() {
  function setupCharts(pDoc, pWin) {
    function setupOne(el) {
      if (el.__resizeReady) return;
      el.__resizeReady = true;
      var ro = new pWin.ResizeObserver(function() {
        var p = el.querySelector('.js-plotly-plot');
        if (p && pWin.Plotly) pWin.Plotly.Plots.resize(p);
      });
      ro.observe(el);
    }

    // Áp dụng cho chart hiện tại
    pDoc.querySelectorAll('[data-testid="stPlotlyChart"]').forEach(setupOne);

    // Theo dõi chart mới (sau mỗi Streamlit rerun)
    if (!pDoc.__resizeMoInstalled) {
      pDoc.__resizeMoInstalled = true;
      var mo = new pWin.MutationObserver(function(muts) {
        muts.forEach(function(m) {
          m.addedNodes.forEach(function(n) {
            if (!n.querySelectorAll) return;
            n.querySelectorAll('[data-testid="stPlotlyChart"]').forEach(setupOne);
            if (n.matches && n.matches('[data-testid="stPlotlyChart"]')) setupOne(n);
          });
        });
      });
      mo.observe(pDoc.body, { childList: true, subtree: true });
    }
  }

  function trySetup(tries) {
    try {
      var pDoc = window.parent.document;
      var pWin = window.parent;
      if (!pDoc.body) throw new Error('body not ready');
      setupCharts(pDoc, pWin);
    } catch(e) {
      if (tries < 8) setTimeout(function(){ trySetup(tries+1); }, 600);
    }
  }
  trySetup(0);
})();
</script>
""", height=0, scrolling=False)


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
    """Khởi tạo session state CAD.
    Ưu tiên tải từ file JSON đã lưu; nếu không có thì dùng preset mặc định.
    """
    sk = _cad_key(pfx, "sections")
    if sk not in st.session_state:
        _saved = _load_defaults(bb)
        if _saved:
            secs = _saved["secs"]
            # Đảm bảo 3 mặt cắt gốc luôn tồn tại (dù rỗng)
            for sname, (fn, _) in _SEC_PRESETS.items():
                if sname not in secs:
                    secs[sname] = getattr(bb, fn)()
        else:
            secs = {sname: getattr(bb, fn)() for sname, (fn, _) in _SEC_PRESETS.items()}
        st.session_state[sk] = secs

    if _cad_key(pfx, "active") not in st.session_state:
        st.session_state[_cad_key(pfx, "active")] = "A-A"

    if _cad_key(pfx, "state") not in st.session_state:
        _saved = _load_defaults(bb)
        _init_cs: dict = {
            "mode": None, "current_poly": [], "cursor": [0.0, 0.0],
            "snap": 50.0, "grip_selected": None,
        }
        if _saved:
            _init_cs["segs"]     = _saved.get("segs", [])
            _init_cs["fill_sec"] = _saved.get("fill_sec", "B-B")
        st.session_state[_cad_key(pfx, "state")] = _init_cs

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
                # Auto-save sau mỗi lần import thành công
                _save_defaults(secs, cad_state)
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


def render_ifc_export_card(
    beam_model,
    design_data: dict,
    pfx: str = "spt",
):
    """
    Card xuất IFC — đặt ở cuối cột 3D trong render_cad_spt_tab().
    Hiển thị nút tải IFC mở được trực tiếp trong Revit.
    """
    IFC = _get_ifc_exporter()

    st.markdown(
        "<div style='background:#0d1a10;border:1px solid #1a4a22;"
        "border-radius:8px;padding:12px 14px;margin-top:12px'>"
        "<div style='font-size:10px;color:#2ecc71;text-transform:uppercase;"
        "letter-spacing:0.5px;margin-bottom:8px'>"
        "📦 Xuất mô hình IFC — mở trực tiếp trong Revit</div>",
        unsafe_allow_html=True,
    )

    if IFC is None:
        st.error(
            "Không load được module 18-IFC_Exporter.py. "
            "Kiểm tra file tồn tại trong cùng thư mục.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    ifc_ok, ifc_msg = IFC.check_ifcopenshell()

    if not ifc_ok:
        st.warning(f"⚠️ {ifc_msg}")
        st.code("pip install ifcopenshell", language="bash")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    _has_sections = any(
        s.outer for s in beam_model.sections.values()
    ) if beam_model.sections else False
    _has_segments = bool(beam_model.segments)

    if not _has_sections:
        st.info("Upload ít nhất 1 mặt cắt DXF để xuất IFC.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if not _has_segments:
        st.info("Khai báo ít nhất 1 đoạn dầm để xuất IFC.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    kcn    = design_data.get("kcn_result") or design_data.get("ai_result", {})
    n_nhip = int(kcn.get("tong_so_nhip", 3))
    n_dam  = int(kcn.get("so_luong_dam") or 5)
    L_nhip = float(kcn.get("chieu_dai", 38.0))

    st.markdown(
        f"<div style='font-size:11px;color:#aaa;margin-bottom:8px'>"
        f"Schema: <b style='color:#2ecc71'>IFC2X3</b> &nbsp;|&nbsp; "
        f"Phần tử: <b style='color:#2ecc71'>"
        f"{n_nhip * n_dam} IfcBeam</b> &nbsp;|&nbsp; "
        f"({n_nhip} nhịp × {n_dam} dầm)<br>"
        f"Mở bằng: <b style='color:#4fc3f7'>Revit → File → Open → IFC</b>"
        f"</div>",
        unsafe_allow_html=True,
    )

    _oa, _ob = st.columns(2)
    with _oa:
        _proj_name = st.text_input(
            "Tên dự án IFC",
            value=design_data.get("ten_du_an", "Cầu Super-T"),
            key=f"{pfx}_ifc_projname",
        )
    with _ob:
        _author = st.text_input(
            "Tác giả",
            value="UTH Bridge AI",
            key=f"{pfx}_ifc_author",
        )

    if f"{pfx}_ifc_bytes" not in st.session_state:
        st.session_state[f"{pfx}_ifc_bytes"] = None

    if st.button(
        "⚙️ Tạo file IFC",
        key=f"{pfx}_gen_ifc",
        use_container_width=True,
        type="secondary",
        help="Tạo IFC từ mô hình dầm hiện tại — thường mất 5-20 giây",
    ):
        with st.spinner("Đang xuất IFC…"):
            try:
                _ifc_bytes = IFC.export_beam_to_ifc(
                    beam_model   = beam_model,
                    design_data  = design_data,
                    project_name = _proj_name,
                    author       = _author,
                )
                st.session_state[f"{pfx}_ifc_bytes"] = _ifc_bytes
                st.success(
                    f"✅ IFC tạo thành công — "
                    f"{len(_ifc_bytes) / 1024:.0f} KB")
            except Exception as _ex:
                st.error(f"❌ Lỗi xuất IFC: {_ex}")
                import traceback
                with st.expander("Chi tiết lỗi"):
                    st.code(traceback.format_exc())

    _ifc_data = st.session_state.get(f"{pfx}_ifc_bytes")
    if _ifc_data:
        _fname = (
            f"dam_supert_{n_nhip}nhip_{int(L_nhip)}m.ifc"
        ).replace(" ", "_")

        st.download_button(
            label="⬇️ Tải IFC — Mở được trực tiếp trong Revit",
            data=_ifc_data,
            file_name=_fname,
            mime="application/x-step",
            use_container_width=True,
            type="primary",
            key=f"{pfx}_dl_ifc",
            help=(
                "Sau khi tải: Revit → File → Open → chọn file .ifc\n"
                "(Không dùng Insert → Link IFC)"
            ),
        )

        with st.expander("📖 Hướng dẫn mở trong Revit"):
            st.markdown("""
**Cách mở IFC trực tiếp trong Revit (không phải Link):**

1. Mở Revit → **File** → **Open** → **IFC**
2. Chọn file `.ifc` vừa tải về
3. Revit sẽ chuyển đổi IFC → RVT (mất 30-60 giây tùy kích thước)
4. Lưu file `.rvt` để làm việc tiếp

**Nếu muốn tùy chỉnh import:**
- Revit → **File** → **Open** → **IFC Options**
- Chọn schema mapping phù hợp

**Lưu ý:**
- Schema IFC2X3 — tương thích với mọi phiên bản Revit hỗ trợ Open IFC
- Geometry xuất dạng IfcFacetedBrep (solid mesh)
- Properties kỹ thuật nằm trong tab Properties của từng element trong Revit
""")

    st.markdown("</div>", unsafe_allow_html=True)


def render_cad_spt_tab(d: dict, pfx: str = "spt"):
    """
    Tab chi tiết dầm Super-T — import mặt cắt ngang từ DXF.
    Layout: 3 upload card (A-A / B-B / C-C) + [vị trí mặt cắt | 3D lớn].
    d   : design_data dict từ session_state
    pfx : prefix tránh collision session-state key
    """
    bb = _get_bb()
    _cad_init(pfx, bb)
    _inject_resize_js()   # CSS + JS cho kéo thả khung nhìn

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

    # ═══ Hàng 1: upload card (fragment — upload không rerun toàn app) ══════════
    _DEFAULTS = {"A-A", "B-B", "C-C"}

    @st.fragment
    def _upload_row():
        _sec_names = list(secs.keys())
        _del_sec   = None

        # Grid 3 cards/hàng, tất cả các mặt cắt hiện có
        for _r in range(0, len(_sec_names), 3):
            _row  = _sec_names[_r : _r + 3]
            _cols = st.columns(len(_row))
            for _col, _sn in zip(_cols, _row):
                with _col:
                    if _sn not in _DEFAULTS:
                        if st.button(f"🗑 Xóa {_sn}", key=f"{pfx}_del_sec_{_sn}",
                                     use_container_width=True):
                            _del_sec = _sn
                    _dxf_upload_card(pfx, bb, secs, cad_state, hist, _sn)

        if _del_sec and _del_sec not in _DEFAULTS and _del_sec in secs:
            del secs[_del_sec]
            st.rerun()

        # ── Thêm mặt cắt tùy chỉnh + lưu mặc định ──────────────────────
        st.markdown("---")
        _ac1, _ac2, _ac3 = st.columns([3, 1, 1])
        _nn = _ac1.text_input(
            "x", placeholder="Tên mặt cắt mới — VD: D-D, E-E, CC-2",
            key=f"{pfx}_new_sec_name", label_visibility="collapsed",
        )
        if _ac2.button("＋ Thêm mặt cắt", key=f"{pfx}_add_sec_btn",
                       use_container_width=True):
            _clean = _nn.strip().upper()
            if _clean and _clean not in secs:
                secs[_clean] = bb.CrossSection(name=_clean, outer=[], holes=[], open=False)
                st.rerun()
            elif not _clean:
                st.warning("Nhập tên mặt cắt trước.")
            else:
                st.info(f"'{_clean}' đã tồn tại.")

        if _ac3.button("💾 Lưu mặc định", key=f"{pfx}_save_def",
                       use_container_width=True,
                       help="Lưu tất cả mặt cắt + cấu hình đoạn. Lần sau mở app không cần upload lại."):
            _msg = _save_defaults(secs, cad_state)
            st.toast(_msg)

        # Trạng thái file đã lưu
        if _SAVE_FILE.exists():
            import os, time as _t
            _mtime = _SAVE_FILE.stat().st_mtime
            _dt    = _t.strftime("%d/%m/%Y %H:%M", _t.localtime(_mtime))
            _n_sec = len([k for k, v in secs.items() if v.outer])
            st.caption(
                f"💾 Đã lưu lúc {_dt} — {_n_sec} mặt cắt có dữ liệu  "
                f"| [Xóa file đã lưu]({'#'}) "
            )
            if st.button("🗑 Xóa dữ liệu đã lưu", key=f"{pfx}_del_save",
                         help="Xóa file lưu — lần sau app dùng preset mặc định"):
                _SAVE_FILE.unlink(missing_ok=True)
                st.toast("Đã xóa file lưu. Restart app để dùng preset mặc định.")
        else:
            st.caption("Chưa có dữ liệu lưu — bấm 💾 Lưu mặc định để lưu.")

    _upload_row()
    st.divider()

    # ═══ Hàng 2: Vị trí mặt cắt | 3D lớn ════════════════════════════════════
    # Thanh kéo tỷ lệ cột
    _cw = st.slider(
        "⟺  Cột đoạn mặt cắt  ◀▶  Cột 3D",
        min_value=10, max_value=55, step=5, format="%d%%",
        value=int(st.session_state.get(f"{pfx}_col_w", 25)),
        key=f"{pfx}_col_w_sl",
        help="Kéo để thay đổi tỷ lệ rộng cột trái (đoạn mặt cắt) / cột phải (3D)",
    )
    st.session_state[f"{pfx}_col_w"] = _cw
    col_pos, col_3d = st.columns([_cw, 100 - _cw])

    # ── Cột trái: vị trí + loại mặt cắt trên trắc dọc ──────────────────────
    with col_pos:
        st.markdown(f"**Đoạn mặt cắt — nửa dầm** (L/2 = {L_half:.0f} mm)")

        # ── Migration: L1-L4 cũ → danh sách đoạn mới ─────────────────────
        if "segs" not in cad_state:
            _l1 = cad_state.get("seg_L1", min(300.0,  L_half * 0.02))
            _l2 = cad_state.get("seg_L2", min(900.0,  L_half * 0.12))
            _l3 = cad_state.get("seg_L3", 0.0)
            _l4 = cad_state.get("seg_L4", min(1200.0, L_half * 0.16))
            _init = []
            if _l1 > 0: _init.append({"type": "constant", "sec": "C-C", "length": _l1})
            if _l2 > 0: _init.append({"type": "loft", "from_sec": "C-C", "to_sec": "A-A", "length": _l2})
            if _l3 > 0: _init.append({"type": "constant", "sec": "A-A", "length": _l3})
            if _l4 > 0: _init.append({"type": "loft", "from_sec": "A-A", "to_sec": "B-B", "length": _l4})
            cad_state["segs"] = _init
            cad_state.setdefault("fill_sec", "B-B")
            cad_state.setdefault("segs_ver", 0)

        _SD = cad_state["segs"]         # segment list (mutable reference)
        _v  = cad_state.get("segs_ver", 0)   # version suffix for stable keys
        _ALL  = list(secs.keys())        # tất cả tên mặt cắt đã đăng ký
        _PAL  = ["#44aa66","#8855cc","#4488cc","#cc8844","#dd5577","#4499bb","#99aa22","#cc5533"]
        _SCOL = {k: _PAL[i % len(_PAL)] for i, k in enumerate(_ALL)}
        _LCOL = "#cc8844"

        # ── Tiêu đề cột ──────────────────────────────────────────────────
        _h1, _h2, _h3, _h4 = st.columns([3, 4, 3, 1])
        _h1.caption("Loại"); _h2.caption("Mặt cắt"); _h3.caption("Dài (mm)"); _h4.caption("")

        _del_idx = None
        for _i, _sg in enumerate(_SD):
            _ka, _kb, _kc, _kd = (f"{pfx}_v{_v}_s{_i}_{x}" for x in ("t","sec","len","del"))
            _ca, _cb, _cc, _cd = st.columns([3, 4, 3, 1])

            # Loại
            _t_cur = 1 if _sg.get("type") == "loft" else 0
            _t_new = _ca.selectbox("t", ["Giữ nguyên", "Vuốt loft"],
                                   index=_t_cur, key=_ka,
                                   label_visibility="collapsed")
            _sg["type"] = "loft" if _t_new == "Vuốt loft" else "constant"

            # Mặt cắt
            if _sg["type"] == "constant":
                _si = _ALL.index(_sg.get("sec","A-A")) if _sg.get("sec") in _ALL else 0
                _sg["sec"] = _cb.selectbox("s", _ALL, index=_si, key=_kb,
                                           label_visibility="collapsed")
                _sg.pop("from_sec", None); _sg.pop("to_sec", None)
            else:
                _fi = _ALL.index(_sg.get("from_sec","C-C")) if _sg.get("from_sec") in _ALL else 2
                _ti = _ALL.index(_sg.get("to_sec","A-A"))   if _sg.get("to_sec")   in _ALL else 0
                _cf, _arrow, _ct = _cb.columns([5, 1, 5])
                _sg["from_sec"] = _cf.selectbox("f", _ALL, index=_fi,
                                                key=_kb + "f", label_visibility="collapsed")
                _arrow.markdown("<div style='text-align:center;padding-top:4px'>→</div>",
                                unsafe_allow_html=True)
                _sg["to_sec"]   = _ct.selectbox("t", _ALL, index=_ti,
                                                key=_kb + "t", label_visibility="collapsed")
                _sg.pop("sec", None)

            # Chiều dài
            _sg["length"] = float(_cc.number_input(
                "l", min_value=0, max_value=int(L_half),
                value=int(_sg.get("length", 500)), step=50,
                key=_kc, label_visibility="collapsed", format="%d",
            ))

            # Xóa
            if _cd.button("✕", key=_kd, use_container_width=True):
                _del_idx = _i

        # Xử lý xóa sau loop (tránh mutation trong loop)
        if _del_idx is not None:
            _SD.pop(_del_idx)
            cad_state["segs_ver"] = _v + 1
            st.rerun()

        if st.button("＋ Thêm đoạn", key=f"{pfx}_v{_v}_add", use_container_width=True):
            _SD.append({"type": "constant", "sec": "A-A", "length": 500.0})
            cad_state["segs_ver"] = _v + 1
            st.rerun()

        # ── Đoạn fill (tự động — còn lại) ───────────────────────────────
        _L_used = sum(float(s.get("length", 0)) for s in _SD)
        L_fill  = L_half - _L_used
        st.markdown("---")
        _fi2 = _ALL.index(cad_state.get("fill_sec","B-B")) if cad_state.get("fill_sec") in _ALL else 1
        cad_state["fill_sec"] = st.selectbox(
            f"Đoạn giữa nhịp (fill = {max(L_fill,0):.0f} mm)",
            _ALL, index=_fi2, key=f"{pfx}_fill_sec",
        )
        if L_fill < 0:
            st.error(f"Tổng {_L_used:.0f} mm > L/2 {L_half:.0f} mm — giảm chiều dài đoạn.")

        # ── Sơ đồ trắc dọc (có điều chỉnh chiều cao) ────────────────────
        _h_sch = st.slider(
            "↕ Cao sơ đồ", min_value=40, max_value=220, step=10,
            value=int(st.session_state.get(f"{pfx}_h_sch", 60)),
            key=f"{pfx}_h_sch_sl",
            help="Kéo để phóng to / thu nhỏ sơ đồ trắc dọc",
        )
        st.session_state[f"{pfx}_h_sch"] = _h_sch
        _zones_sch = []
        for _sg in _SD:
            _zl = float(_sg.get("length", 0))
            if _sg["type"] == "loft":
                _zlab = f"{_sg.get('from_sec','?')}→{_sg.get('to_sec','?')}"
                _zcl  = _LCOL
            else:
                _zlab = _sg.get("sec", "?")
                _zcl  = _SCOL.get(_zlab, "#668899")
            _zones_sch.append((_zl, _zlab, _zcl))
        _fsc = cad_state.get("fill_sec", "B-B")
        _zones_sch.append((max(L_fill, 0), _fsc, _SCOL.get(_fsc, "#668899")))

        _fig_sch = go.Figure()
        _x0_s = 0.0
        for _zl, _zlab, _zcl in _zones_sch:
            if _zl <= 0:
                continue
            _r, _g, _b = int(_zcl[1:3],16), int(_zcl[3:5],16), int(_zcl[5:7],16)
            _fig_sch.add_shape(type="rect", x0=_x0_s, x1=_x0_s+_zl, y0=0, y1=1,
                               fillcolor=f"rgba({_r},{_g},{_b},0.55)",
                               line=dict(color="#fff", width=0.5))
            if _zl > L_half * 0.04:
                _fig_sch.add_annotation(x=_x0_s+_zl/2, y=0.5, text=_zlab,
                                        showarrow=False, font=dict(size=8, color="#fff"))
            _x0_s += _zl
        _fig_sch.update_layout(
            template="plotly_dark", paper_bgcolor="#1a2330", plot_bgcolor="#1a2330",
            height=_h_sch, margin=dict(l=10, r=10, t=4, b=18),
            xaxis=dict(range=[0, L_half], showgrid=False, tickformat=".0f",
                       tickfont=dict(size=7),
                       title=dict(text="mm từ đầu dầm", font=dict(size=7))),
            yaxis=dict(visible=False), showlegend=False,
        )
        st.plotly_chart(_fig_sch, use_container_width=True,
                        key=f"{pfx}_sch_fig", config={"displayModeBar": False})

    # ── Cột phải: 3D wireframe lớn ────────────────────────────────────────────
    with col_3d:
        _avail  = {k: v for k, v in secs.items() if v.outer}
        _SD_3d  = cad_state.get("segs", [])
        _L_used = sum(float(s.get("length", 0)) for s in _SD_3d)
        L_fill  = L_half - _L_used

        try:
            if len(_avail) < 1:
                st.info("Upload ít nhất 1 mặt cắt để xem 3D preview.", icon="ℹ")
            elif L_fill < 0:
                st.warning(f"Tổng đoạn {_L_used:.0f} mm > L/2 {L_half:.0f} mm — giảm chiều dài.")
            else:
                m3d = bb.BeamModel(length=L_m * 1000, mirror=True)
                m3d.sections = {k: v.clone() for k, v in _avail.items()}

                def _has(*names):
                    return all(n in m3d.sections for n in names)

                _segs = []
                for _sg in _SD_3d:
                    _slen = float(_sg.get("length", 0))
                    if _slen <= 0:
                        continue
                    if _sg["type"] == "loft":
                        _fs = _sg.get("from_sec", "C-C")
                        _ts = _sg.get("to_sec",   "A-A")
                        if _has(_fs, _ts):
                            _segs.append(bb.Segment("loft", from_sec=_fs, to_sec=_ts, length=_slen))
                        elif _has(_ts):
                            _segs.append(bb.Segment("constant", section=_ts, length=_slen))
                        elif _has(_fs):
                            _segs.append(bb.Segment("constant", section=_fs, length=_slen))
                    else:
                        _ss = _sg.get("sec", next(iter(m3d.sections), "A-A"))
                        if _has(_ss):
                            _segs.append(bb.Segment("constant", section=_ss, length=_slen))
                        elif _avail:
                            _segs.append(bb.Segment("constant",
                                                    section=next(iter(_avail)), length=_slen))

                # Đoạn fill giữa nhịp
                _fill_sec = cad_state.get("fill_sec", "B-B")
                if not _has(_fill_sec):
                    _fill_sec = next(iter(m3d.sections), None)
                if _fill_sec:
                    _segs.append(bb.Segment("constant", section=_fill_sec, length="fill"))
                m3d.segments = _segs

                _traces = bb.build_3d_wireframe(m3d)
                _fig3d = go.Figure(data=_traces)

                # Thanh điều chỉnh chiều cao view 3D
                _h3d = st.slider(
                    "↕ Cao view 3D", min_value=300, max_value=1000, step=50,
                    value=int(st.session_state.get(f"{pfx}_h3d", 560)),
                    key=f"{pfx}_h3d_sl",
                    help="Kéo để phóng to / thu nhỏ khung nhìn 3D",
                )
                st.session_state[f"{pfx}_h3d"] = _h3d

                _fig3d.update_layout(
                    template="plotly_dark", paper_bgcolor="#1a2330",
                    height=_h3d, margin=dict(l=0, r=0, t=35, b=0),
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

                # Nút commit — chỉ update tab khác khi user bấm
                if st.button(
                    "🏗️ Cập nhật 3D toàn cầu & Bố trí chung",
                    type="primary", use_container_width=True,
                    key=f"{pfx}_commit_3d",
                    help="Ghi mô hình dầm này vào tab 3D Tổng hợp và Bố trí chung",
                ):
                    st.session_state["spt_beam_model"] = m3d
                    st.session_state["spt_L_m"] = L_m
                    st.session_state.pop("spt_beam_traces_cache", None)
                    # Lưu cấu hình đoạn vào file (bao gồm segs + fill_sec)
                    _save_defaults(secs, cad_state)
                    st.toast("✅ Đã cập nhật 3D & lưu cấu hình. Chuyển tab 🏗️ để xem.", icon="✅")

                # Xuất IFC mở được trong Revit
                render_ifc_export_card(m3d, d, pfx=pfx)

        except Exception as _e3d:
            st.error(f"Không tạo được 3D: {_e3d}")


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC — dùng từ 00-Interface.py
# ═══════════════════════════════════════════════════════════════════════════════

def render_btc_sections(pfx: str = "spt"):
    """Hiển thị mặt cắt dầm đã upload — gọi từ tab Bố trí chung."""
    secs = st.session_state.get(_cad_key(pfx, "sections"), {})
    if not secs:
        return
    avail = {k: v for k, v in secs.items() if v and v.outer}
    if not avail:
        return
    st.markdown("---")
    st.markdown("#### 📐 Chi tiết mặt cắt dầm chính (upload từ CAD)")
    _labels = {
        "A-A": "A-A — Giữa nhịp",
        "B-B": "B-B — Đầu dầm (mố)",
        "C-C": "C-C — Đầu dầm (trụ)",
    }
    _cols = st.columns(len(avail))
    for _i, (_k, _sec) in enumerate(avail.items()):
        _fig = _section_fig(_sec, height=280, title=_labels.get(_k, _k))
        _cols[_i].plotly_chart(_fig, use_container_width=True,
                               key=f"btc_sec_{pfx}_{_k}")


def get_beam_model_traces(d: dict, pfx: str = "spt") -> list:
    """Trả về list go.Scatter3d traces của BeamModel đã scale và định vị theo cầu.

    Dùng để chèn vào figure tab 3D Tổng hợp.  Trả về [] nếu chưa có model.
    Kết quả được cache vào session_state cho đến khi model được commit lại.
    """
    m3d = st.session_state.get("spt_beam_model")
    if m3d is None:
        return []

    # Cache — tránh tính lại khi rerun không liên quan
    _cache_key = "spt_beam_traces_cache"
    if _cache_key in st.session_state:
        return st.session_state[_cache_key]

    bb = _get_bb()
    try:
        _raw = bb.build_3d_wireframe(m3d)
    except Exception:
        return []
    if not _raw:
        return []

    kcn    = d.get("kcn_result") or d.get("ai_result", {})
    geo    = d.get("geo_logic", {})
    x0     = float(geo.get("x_mo_trai",     -60.0))
    L_nhip = float(kcn.get("chieu_dai",      38.0))
    n_nhip = int(kcn.get("tong_so_nhip",     3))
    n_dam  = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
    kc_dam = float(kcn.get("khoang_cach_dam", 2.2))
    bc     = float(d.get("bc",               12.0))
    oh     = float(kcn.get("overhang",        0.5))
    cao_dd = float(d.get("cao_day_dam",        8.0))
    H_dam  = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))

    x_first_dam  = -bc / 2 + oh        # vị trí Y dầm đầu tiên (m)
    z_beam_top   = cao_dd + H_dam       # cao độ đỉnh dầm = đáy bản mặt cầu (m)
    L_m          = float(st.session_state.get("spt_L_m", L_nhip))
    result  = []
    _legend = True   # legend only on the very first trace

    for i_dam in range(n_dam):
        beam_y = x_first_dam + i_dam * kc_dam
        for i_nhip in range(n_nhip):
            span_x0 = x0 + i_nhip * L_nhip
            for _t in _raw:
                if not (hasattr(_t, 'x') and _t.x is not None and len(_t.x) > 0):
                    continue
                _tx = np.array(_t.x, dtype=float)
                _ty = np.array(_t.y, dtype=float)
                _tz = np.array(_t.z, dtype=float)

                bx = span_x0 + _ty * (L_nhip / L_m) / 1000.0
                by = beam_y  + _tx / 1000.0
                bz = z_beam_top + _tz / 1000.0

                result.append(go.Scatter3d(
                    x=bx.tolist(), y=by.tolist(), z=bz.tolist(),
                    mode="lines",
                    line=_t.line,
                    name="Dầm Super-T (DXF)" if _legend else "",
                    showlegend=_legend,
                    hoverinfo="skip",
                ))
                _legend = False

    st.session_state[_cache_key] = result
    return result


def get_mcn_overlay_traces(d: dict, pfx: str = "spt") -> list:
    """Trả về go.Scatter traces (2D) overlay mặt cắt A-A thực tế lên MCN điển hình.

    Hệ trục MCN: x = ngang cầu (m), y = cao độ (0=mặt bê tông bản, âm=xuống dưới).
    Chỉ vẽ khi session_state có mặt cắt A-A với outer polygon đã upload.
    """
    secs_st = st.session_state.get(_cad_key(pfx, "sections"), {})
    sec_aa  = secs_st.get("A-A")
    if not sec_aa or not sec_aa.outer:
        return []

    kcn    = d.get("kcn_result") or d.get("ai_result", {})
    n_dam  = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
    kc_dam = float(kcn.get("khoang_cach_dam", 2.2))
    bc     = float(d.get("bc", 12.0))
    oh     = float(kcn.get("overhang", 0.5))
    t_ban  = float(d.get("t_ban_mm", 200)) / 1000.0

    x_first = -bc / 2 + oh
    outer   = sec_aa.outer   # [[x_mm, z_mm], ...]
    holes   = sec_aa.holes or []
    result  = []

    for i_dam in range(n_dam):
        x_center = x_first + i_dam * kc_dam
        xs = [x_center + p[0] / 1000.0 for p in outer]
        ys = [-t_ban   + p[1] / 1000.0 for p in outer]
        xs.append(xs[0]); ys.append(ys[0])
        result.append(go.Scatter(
            x=xs, y=ys,
            fill="toself",
            fillcolor="rgba(46,204,113,0.28)",
            line=dict(color="#27ae60", width=1.8),
            mode="lines",
            name="Mặt cắt A-A (DXF)" if i_dam == 0 else "",
            showlegend=(i_dam == 0),
            hovertemplate="Mặt cắt A-A thực tế<extra></extra>",
        ))
        for hole in holes:
            if not hole:
                continue
            hx = [x_center + p[0] / 1000.0 for p in hole]
            hy = [-t_ban   + p[1] / 1000.0 for p in hole]
            hx.append(hx[0]); hy.append(hy[0])
            result.append(go.Scatter(
                x=hx, y=hy,
                fill="toself", fillcolor="rgba(255,255,255,0.82)",
                line=dict(color="#27ae60", width=0.8),
                mode="lines", showlegend=False, hoverinfo="skip",
            ))

    return result


def get_elevation_profile_traces(d: dict, pfx: str = "spt") -> list:
    """Trả về go.Scatter traces overlay profil chiều cao dầm thực tế lên trắc dọc cầu.

    Hệ trục: x = lý trình (m), y = cao độ tuyệt đối (m).
    Hiển thị dạng haunch profile: cao ở hai đầu (C-C), thấp ở giữa nhịp (A-A).
    """
    secs_st   = st.session_state.get(_cad_key(pfx, "sections"), {})
    cad_state = st.session_state.get(_cad_key(pfx, "state"), {})
    segs_data = cad_state.get("segs", [])
    fill_sec  = cad_state.get("fill_sec", "A-A")

    if not segs_data:
        return []

    def _h_mm(name: str):
        s = secs_st.get(name)
        if not s or not s.outer:
            return None
        zvals = [p[1] for p in s.outer]
        return abs(min(zvals)) if zvals else None

    kcn    = d.get("kcn_result") or d.get("ai_result", {})
    geo    = d.get("geo_logic", {})
    x0     = float(geo.get("x_mo_trai",    -60.0))
    L_nhip = float(kcn.get("chieu_dai",     38.0))
    n_nhip = int(kcn.get("tong_so_nhip",    3))
    cao_dd = float(d.get("cao_day_dam",      8.0))
    H_nom  = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    _spt_L_raw = st.session_state.get("spt_L_m", None)
    if _spt_L_raw is not None:
        L_m = float(_spt_L_raw) * 1000.0   # spt_L_m stored in m → convert to mm
    else:
        L_m = L_nhip * 1000.0              # fallback: L_nhip metres → mm

    beam_top = cao_dd + H_nom   # cao độ đỉnh dầm (m) — cố định theo thiết kế

    # Xây dựng profile (x_mm, h_mm) từ đầu dầm → giữa nhịp
    pts = []
    _x  = 0.0
    for seg in segs_data:
        slen = float(seg.get("length", 0))
        if slen <= 0:
            continue
        if seg["type"] == "constant":
            h = _h_mm(seg.get("sec", "A-A")) or H_nom * 1000
            pts.append((_x, h))
            pts.append((_x + slen, h))
        else:
            h_from = _h_mm(seg.get("from_sec", "C-C")) or H_nom * 1000
            h_to   = _h_mm(seg.get("to_sec",   "A-A")) or H_nom * 1000
            pts.append((_x, h_from))
            pts.append((_x + slen, h_to))
        _x += slen

    h_fill = _h_mm(fill_sec) or H_nom * 1000
    L_half = L_m / 2.0
    if _x < L_half:
        pts.append((_x, h_fill))
        pts.append((L_half, h_fill))

    if not pts:
        return []

    # Mirror cho nửa phải
    full_pts = pts + [(L_m - p[0], p[1]) for p in reversed(pts[:-1])]

    result = []
    for i_nhip in range(n_nhip):
        span_x0 = x0 + i_nhip * L_nhip
        scale   = L_nhip / L_m

        bot_x = [span_x0 + s * scale for s, _ in full_pts]
        bot_y = [beam_top - h / 1000.0 for _, h in full_pts]

        # Polygon: top-left → bottom trace → top-right → close
        px = [bot_x[0]] + bot_x + [bot_x[-1], bot_x[0]]
        py = [beam_top]  + bot_y + [beam_top,  beam_top]

        result.append(go.Scatter(
            x=px, y=py,
            fill="toself",
            fillcolor="rgba(52,152,219,0.22)",
            line=dict(color="#2980b9", width=2),
            mode="lines",
            name="Profil dầm thực tế (DXF)" if i_nhip == 0 else "",
            showlegend=(i_nhip == 0),
            hovertemplate="Dầm SPT — profil thực tế<extra></extra>",
        ))

    return result
