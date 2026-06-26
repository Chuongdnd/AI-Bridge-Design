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
import importlib as _il
try:                                    # helper tỷ lệ mặt cắt 2D dùng chung
    _PLOT = _il.import_module("00-Drawing_Utils")
except Exception:
    _PLOT = None


def _aspect(fig, key):
    if _PLOT is not None:
        try:
            return _PLOT.aspect_control(fig, key, st_obj=st)
        except Exception:
            pass
    return fig

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


def _get_banve():
    """Lazy-load 11-BanVe_KetCau.py để dùng chung bố trí nhịp (calc_span_layout)."""
    bv = sys.modules.get("BanVeKetCau11")
    if bv is None:
        import importlib.util as _bv_util
        _spec = _bv_util.spec_from_file_location(
            "BanVeKetCau11",
            pathlib.Path(__file__).parent / "11-BanVe_KetCau.py",
        )
        if _spec is None:
            return None
        bv = _bv_util.module_from_spec(_spec)
        sys.modules["BanVeKetCau11"] = bv
        try:
            _spec.loader.exec_module(bv)
        except Exception:
            return None
    return bv


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


# ── Export / Import state một dầm theo pfx (dùng cho Thư viện cấu kiện) ──────
def export_beam_state(pfx: str) -> dict:
    """Chụp (snapshot) state CAD của một dầm (theo pfx) → dict serializable.
    Định dạng đồng bộ với _save_defaults để tái dùng dễ."""
    secs = st.session_state.get(_cad_key(pfx, "sections")) or {}
    cs   = st.session_state.get(_cad_key(pfx, "state")) or {}
    return {
        "sections": {
            name: {"outer": sec.outer, "holes": sec.holes}
            for name, sec in secs.items() if getattr(sec, "outer", None)
        },
        "segs":     cs.get("segs", []),
        "fill_sec": cs.get("fill_sec", "B-B"),
    }


def import_beam_state(pfx: str, data: dict, bb=None) -> None:
    """Nạp dict (từ export_beam_state) vào state CAD của một pfx —
    ghi đè sections + state. Bảo đảm các mặt cắt preset luôn tồn tại."""
    bb = bb or _get_bb()
    data = data or {}
    secs: dict = {}
    for name, v in (data.get("sections") or {}).items():
        sec = bb.CrossSection(name=name, outer=[], holes=[], open=False)
        sec.outer = v.get("outer", [])
        sec.holes = v.get("holes", [])
        secs[name] = sec
    # Chỉ đảm bảo các mặt cắt TỐI THIỂU (A-A, B-B) — không ép tạo lại C-C.
    for sname, (fn, _) in _SEC_PRESETS.items():
        if sname in _MIN_SECS and sname not in secs:
            secs[sname] = getattr(bb, fn)()
    st.session_state[_cad_key(pfx, "sections")] = secs
    st.session_state[_cad_key(pfx, "state")] = {
        "mode": None, "current_poly": [], "cursor": [0.0, 0.0],
        "snap": 50.0, "grip_selected": None,
        "segs":     data.get("segs", []),
        "fill_sec": data.get("fill_sec", "B-B"),
    }
    st.session_state[_cad_key(pfx, "active")] = "A-A"
    st.session_state[_cad_key(pfx, "hist")] = []
    st.session_state[_cad_key(pfx, "undo")] = []


# Suffix pfx theo loại dầm — PHẢI đồng bộ với _BTYPES trong render_cad_spt_tab
BTYPE_SUFFIX = {
    "Super-T":     "",
    "Dầm T ngược": "tinv",
    "Dầm I":       "ibeam",
}


def effective_pfx(base_pfx: str, beam_type: str = None) -> str:
    """pfx thực tế nơi sections của 1 dầm được lưu (gồm suffix theo loại dầm).
    Bỏ qua biến thể vai trò (dầm biên/nhịp biên) — Thư viện chỉ dùng vai trò gốc."""
    bt = beam_type or st.session_state.get(f"{base_pfx}_beam_type", "Super-T")
    suffix = BTYPE_SUFFIX.get(bt, "")
    return f"{base_pfx}_{suffix}" if suffix else base_pfx


def _resolve_storage_pfx(base_pfx: str) -> str:
    """pfx THỰC nơi mặt cắt đang được lưu. Builder lưu kèm hậu tố theo loại dầm
    (effective_pfx) nên khi ĐỌC ta phải dò: loại đang chọn → base → các hậu tố
    loại khác, chọn pfx đầu tiên có mặt cắt. Khắc phục lỗi 3D toàn cầu không cập
    nhật dầm mới với Dầm I / Dầm T ngược (sections nằm ở base_ibeam/base_tinv)."""
    def _has_secs(p):
        s = st.session_state.get(_cad_key(p, "sections")) or {}
        return any(getattr(v, "outer", None) for v in s.values())
    cands = [effective_pfx(base_pfx), base_pfx]
    cands += [f"{base_pfx}_{s}" for s in BTYPE_SUFFIX.values() if s]
    seen = set()
    for p in cands:
        if p in seen:
            continue
        seen.add(p)
        if _has_secs(p):
            return p
    return base_pfx


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
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
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
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
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
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", height=560,
        margin=dict(l=0, r=0, t=40, b=0),
        title=dict(text="Wireframe dầm — nét CAD", x=0.5,
                   font=dict(size=13, color="#dde3ea")),
        scene=dict(
            xaxis=dict(title="X (mm)", backgroundcolor="rgba(0,0,0,0)",
                       gridcolor="rgba(128,128,128,0.35)", showbackground=True),
            yaxis=dict(title="Y dọc (mm)", backgroundcolor="rgba(0,0,0,0)",
                       gridcolor="rgba(128,128,128,0.35)", showbackground=True),
            zaxis=dict(title="Z (mm)", backgroundcolor="rgba(0,0,0,0)",
                       gridcolor="rgba(128,128,128,0.35)", showbackground=True),
            bgcolor="rgba(0,0,0,0)", aspectmode="data",
        ),
    )

    c3d, celev = st.columns([2, 1])
    with c3d:
        if _PLOT is not None:
            _PLOT.to_concrete_3d(fig3d)   # khối đặc màu bê tông (quy tắc thể hiện)
        st.plotly_chart(fig3d, use_container_width=True, key="view3d")
    with celev:
        st.markdown("**Mặt cắt dọc**")
        try:
            _felev = bb.make_elevation_fig(m)
            _aspect(_felev, "bb_elev_view")
            st.plotly_chart(_felev, use_container_width=True,
                            key="elev_view")
        except Exception as ex:
            st.warning(f"Lỗi elevation: {ex}")

        active = st.session_state.get("bb_active_sec")
        if active and active in m.sections:
            st.markdown("**MCN đang chọn**")
            fsec = bb.make_section_fig(sec=m.sections[active], snap_grid=0,
                                       show_grid_pts=False)
            fsec.update_layout(height=260, margin=dict(l=30, r=10, t=20, b=30))
            _aspect(fsec, "bb_sec_prev")
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

# Mặt cắt TỐI THIỂU bắt buộc (không cho xoá) — chỉ 2 mặt cắt.
# C-C là preset gợi ý nhưng người dùng được phép xoá để còn 2 mặt cắt.
_MIN_SECS = {"A-A", "B-B"}

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
            # Đảm bảo các mặt cắt TỐI THIỂU (A-A, B-B) luôn tồn tại (dù rỗng)
            for sname, (fn, _) in _SEC_PRESETS.items():
                if sname in _MIN_SECS and sname not in secs:
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
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=height, margin=dict(l=30, r=10, t=28 if title else 12, b=28),
        title=dict(text=title, font=dict(size=12, color="#9ac8e8"), x=0.5) if title else {},
        xaxis=dict(range=xr, showgrid=True, gridcolor="rgba(128,128,128,0.35)", dtick=200,
                   zeroline=True, zerolinecolor="rgba(128,128,128,0.35)", zerolinewidth=1,
                   scaleanchor="y", scaleratio=1, showticklabels=False),
        yaxis=dict(range=zr, showgrid=True, gridcolor="rgba(128,128,128,0.35)", dtick=200,
                   zeroline=True, zerolinecolor="rgba(128,128,128,0.35)", zerolinewidth=1,
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
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
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
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", height=270,
            margin=dict(l=0, r=0, t=25, b=0),
            title=dict(text="3D Wireframe", font=dict(size=11)),
            scene=dict(
                xaxis=dict(title="X", backgroundcolor="rgba(0,0,0,0)",
                           gridcolor="rgba(128,128,128,0.35)", showbackground=True, showticklabels=False),
                yaxis=dict(title="Y", backgroundcolor="rgba(0,0,0,0)",
                           gridcolor="rgba(128,128,128,0.35)", showbackground=True, showticklabels=False),
                zaxis=dict(title="Z", backgroundcolor="rgba(0,0,0,0)",
                           gridcolor="rgba(128,128,128,0.35)", showbackground=True, showticklabels=False),
                bgcolor="#1a2330", aspectmode="data",
            ),
        )
        return fig
    except Exception:
        fig = go.Figure()
        fig.update_layout(height=270, template="plotly_dark",
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
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
                _tim = ("tim CAD" if _res.get("tim_source") == "cad_line"
                        else "trọng tâm")
                hist.append((f"DXF {sec_name}: {uploaded.name}",
                             f"✓ {len(sec.outer)} đỉnh | {_w:.0f}×{_h:.0f}mm | "
                             f"căn theo {_tim}"))
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
        f"Phần tử: <b style='color:#2ecc71'>1 IfcBeam</b> &nbsp;|&nbsp; "
        f"L={L_nhip:.0f}m — 1 dầm đơn để kiểm tra trong Revit<br>"
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


def _render_seg_rows(seg_list, _ALL, max_len, kp, ver_key, cad_state):
    """Render bảng khai báo đoạn mặt cắt cho MỘT nửa dầm (đầu → giữa nhịp).
    kp = key prefix duy nhất; ver_key = khóa version trong cad_state (rerun khi sửa)."""
    _v = cad_state.get(ver_key, 0)
    _h1, _h2, _h3, _h4 = st.columns([3, 4, 3, 1])
    _h1.caption("Loại"); _h2.caption("Mặt cắt"); _h3.caption("Dài (mm)"); _h4.caption("")
    _del = None
    for _i, _sg in enumerate(seg_list):
        _ka, _kb, _kc, _kd = (f"{kp}_v{_v}_s{_i}_{x}" for x in ("t", "sec", "len", "del"))
        _ca, _cb, _cc, _cd = st.columns([3, 4, 3, 1])
        _t_new = _ca.selectbox("t", ["Giữ nguyên", "Vuốt loft"],
                               index=1 if _sg.get("type") == "loft" else 0,
                               key=_ka, label_visibility="collapsed")
        _sg["type"] = "loft" if _t_new == "Vuốt loft" else "constant"
        if _sg["type"] == "constant":
            _si = _ALL.index(_sg.get("sec", "A-A")) if _sg.get("sec") in _ALL else 0
            _sg["sec"] = _cb.selectbox("s", _ALL, index=_si, key=_kb,
                                       label_visibility="collapsed")
            _sg.pop("from_sec", None); _sg.pop("to_sec", None)
        else:
            _fi = _ALL.index(_sg.get("from_sec", "C-C")) if _sg.get("from_sec") in _ALL \
                  else (2 if len(_ALL) > 2 else 0)
            _ti = _ALL.index(_sg.get("to_sec", "A-A")) if _sg.get("to_sec") in _ALL else 0
            _cf, _ar, _ct = _cb.columns([5, 1, 5])
            _sg["from_sec"] = _cf.selectbox("f", _ALL, index=_fi, key=_kb + "f",
                                            label_visibility="collapsed")
            _ar.markdown("<div style='text-align:center;padding-top:4px'>→</div>",
                         unsafe_allow_html=True)
            _sg["to_sec"] = _ct.selectbox("t", _ALL, index=_ti, key=_kb + "t",
                                          label_visibility="collapsed")
            _sg.pop("sec", None)
        _sg["length"] = float(_cc.number_input(
            "l", min_value=0, max_value=int(max_len),
            value=int(_sg.get("length", 500)), step=50,
            key=_kc, label_visibility="collapsed", format="%d"))
        if _cd.button("✕", key=_kd, use_container_width=True):
            _del = _i
    if _del is not None:
        seg_list.pop(_del); cad_state[ver_key] = _v + 1; st.rerun()
    if st.button("＋ Thêm đoạn", key=f"{kp}_v{_v}_add", use_container_width=True):
        seg_list.append({"type": "constant", "sec": "A-A", "length": 500.0})
        cad_state[ver_key] = _v + 1; st.rerun()


def _segdicts_to_segments(bb, seg_dicts, has_fn, avail, reverse=False):
    """Đổi list dict đoạn → list bb.Segment. reverse=True (nửa phải): đảo thứ tự
    và đảo chiều loft (đang khai đầu→giữa, cần chuyển thành giữa→đầu)."""
    out = []
    src = list(reversed(seg_dicts)) if reverse else list(seg_dicts)
    for sg in src:
        slen = float(sg.get("length", 0))
        if slen <= 0:
            continue
        if sg.get("type") == "loft":
            fs = sg.get("from_sec", "C-C"); ts = sg.get("to_sec", "A-A")
            if reverse:
                fs, ts = ts, fs
            if has_fn(fs, ts):
                out.append(bb.Segment("loft", from_sec=fs, to_sec=ts, length=slen))
            elif has_fn(ts):
                out.append(bb.Segment("constant", section=ts, length=slen))
            elif has_fn(fs):
                out.append(bb.Segment("constant", section=fs, length=slen))
        else:
            ss = sg.get("sec") or (next(iter(avail)) if avail else None)
            if ss and has_fn(ss):
                out.append(bb.Segment("constant", section=ss, length=slen))
            elif avail:
                out.append(bb.Segment("constant", section=next(iter(avail)), length=slen))
    return out


def render_cad_spt_tab(d: dict, pfx: str = "spt", show_type: bool = True):
    """
    Tab chi tiết dầm — hỗ trợ Super-T, T ngược, I-Beam.
    Layout: dropdown loại dầm → upload cards → khai báo đoạn + sơ đồ → 3D toàn rộng.
    d         : design_data dict từ session_state
    pfx       : prefix tránh collision session-state key
    show_type : False → ẩn ô chọn loại dầm (Thư viện dầm — dầm định nghĩa bằng
                DXF, không cần chọn loại). Vẫn giữ loại trong session để tương thích.
    """
    _orig_pfx_arg = pfx     # giữ pfx gốc để cache pfx hiệu dụng (cho Thư viện)
    # ── Loại dầm ─────────────────────────────────────────────────────────────
    # (suffix, label_hiện_thị, fill_sec_mặc_định)
    _BTYPES: dict[str, tuple[str, str, str]] = {
        "Super-T":     ("",      "Dầm Super-T",    "B-B"),
        "Dầm T ngược": ("tinv",  "Dầm T ngược",    "A-A"),
        "Dầm I":       ("ibeam", "Dầm I (I-Beam)", "A-A"),
    }
    _bt_names = list(_BTYPES.keys())
    _bt_key   = f"{pfx}_beam_type"
    if show_type:
        _bt_sel = st.selectbox(
            "🏗️ Loại dầm",
            _bt_names,
            index=_bt_names.index(st.session_state.get(_bt_key, "Super-T")),
            key=_bt_key,
            help="Mỗi loại dầm có bộ mặt cắt và cấu hình riêng biệt",
        )
    else:
        _bt_sel = st.session_state.get(_bt_key, "Super-T")
        if _bt_sel not in _BTYPES:
            _bt_sel = "Super-T"
    _bt_suffix, _bt_label, _bt_fill_default = _BTYPES[_bt_sel]
    # Super-T giữ pfx="spt" để tương thích dữ liệu đã lưu; loại khác thêm suffix
    if _bt_suffix:
        pfx = f"{pfx}_{_bt_suffix}"

    bb = _get_bb()
    # Bảo đảm dầm gốc (default) đã init trước khi clone biến thể từ nó
    _cad_init(pfx, bb)

    # ═══ DẦM BIẾN THỂ THEO VAI TRÒ (kế thừa từ dầm gốc) ═══════════════════════
    # Ẩn trong Thư viện (show_type=False) — dầm thư viện chỉ là 1 cây, không cần
    # khai biến thể dầm biên / nhịp biên.
    _base_pfx = pfx
    if show_type:
        with st.container():
            _vc1, _vc2 = st.columns(2)
            _tg_dam  = _vc1.toggle("Dầm biên khác dầm giữa",
                                   key=f"{_base_pfx}_tg_dambien",
                                   help="Bật để dựng riêng cây dầm BIÊN (cây ngoài cùng)")
            _tg_nhip = _vc2.toggle("Nhịp biên khác nhịp giữa",
                                   key=f"{_base_pfx}_tg_nhipbien",
                                   help="Bật để dựng riêng dầm ở NHỊP BIÊN (nhịp mố–trụ)")
    else:
        _tg_dam = _tg_nhip = False

    # Tập biến thể đang bật → để hàm đặt dầm định tuyến (đọc qua _active_variants)
    _active = set()
    if _tg_dam:  _active.add("TB")
    if _tg_nhip: _active.add("LB")
    if _tg_dam and _tg_nhip: _active.add("LB_TB")
    st.session_state[_variant_active_key(_base_pfx)] = _active

    _role_opts = [("default", "Mặc định (nhịp giữa · dầm giữa)")]
    if _tg_dam:  _role_opts.append(("TB", "Dầm biên"))
    if _tg_nhip: _role_opts.append(("LB", "Nhịp biên"))
    if _tg_dam and _tg_nhip: _role_opts.append(("LB_TB", "Nhịp biên · Dầm biên"))

    _role_sel = "default"
    if len(_role_opts) > 1:
        _role_sel = st.radio(
            "🧩 Đang dựng dầm cho vai trò:",
            [k for k, _ in _role_opts],
            format_func=lambda k: dict(_role_opts)[k],
            horizontal=True, key=f"{_base_pfx}_role_sel",
        )

    if _role_sel != "default":
        _role_pfx = f"{_base_pfx}__{_role_sel}"
        # KẾ THỪA: lần đầu chọn vai trò → clone mặt cắt + đoạn từ dầm gốc
        if _cad_key(_role_pfx, "sections") not in st.session_state:
            _src_secs = st.session_state.get(_cad_key(_base_pfx, "sections")) or {}
            st.session_state[_cad_key(_role_pfx, "sections")] = {
                k: v.clone() for k, v in _src_secs.items()
            }
            _src_state = st.session_state.get(_cad_key(_base_pfx, "state"), {}) or {}
            st.session_state[_cad_key(_role_pfx, "state")] = {
                **{k: v for k, v in _src_state.items() if k != "segs"},
                "segs": [dict(s) for s in _src_state.get("segs", [])],
            }
            st.session_state.setdefault(_cad_key(_role_pfx, "hist"), [])
            st.session_state.setdefault(_cad_key(_role_pfx, "undo"), [])
        pfx = _role_pfx
        st.info(f"✏️ Đang chỉnh **{dict(_role_opts)[_role_sel]}** — kế thừa từ dầm "
                f"gốc, chỉ sửa phần khác. Vai trò không khai sẽ tự dùng dầm gốc.")

    _cad_init(pfx, bb)
    _inject_resize_js()
    # Cache pfx hiệu dụng (đã gồm suffix loại dầm) để Thư viện export đúng chỗ
    st.session_state[f"_effpfx_{_orig_pfx_arg}"] = pfx

    secs      = st.session_state[_cad_key(pfx, "sections")]
    cad_state = st.session_state[_cad_key(pfx, "state")]
    hist      = st.session_state[_cad_key(pfx, "hist")]
    cad_state.setdefault("fill_sec", _bt_fill_default)

    kcn = d.get("kcn_result") or d.get("ai_result") or {}
    H   = float(kcn.get("chieu_cao_dam", 1.75)) * 1000
    L_m = float(kcn.get("chieu_dai", 38.0))
    kc  = float(kcn.get("khoang_cach_dam", 2.2)) * 1000
    L_half = L_m * 1000 / 2

    st.markdown(
        f"<div style='font-size:13px;color:#9ac8e8;margin-bottom:6px'>"
        f"{_bt_label} — L={L_m:.1f}m | H={H:.0f}mm | S={kc:.0f}mm | "
        f"Upload DXF mặt cắt ngang từ AutoCAD (đơn vị mm)</div>",
        unsafe_allow_html=True,
    )

    # ═══ Hàng 1: upload card (fragment — upload không rerun toàn app) ══════════
    _DEFAULTS = set(_MIN_SECS)   # tối thiểu 2 mặt cắt (A-A, B-B) — không cho xoá

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
            st.caption(f"💾 Đã lưu lúc {_dt} — {_n_sec} mặt cắt có dữ liệu.")
            # ── Xóa AN TOÀN: 2 bước xác nhận (tránh lỡ tay) ───────────────────
            _confirm_key = f"{pfx}_del_save_confirm"
            if not st.session_state.get(_confirm_key):
                if st.button("🗑 Xóa mặt cắt mặc định đã lưu…",
                             key=f"{pfx}_del_save",
                             help="Chỉ xóa BỘ MẶT CẮT MẶC ĐỊNH của trình dựng dầm. "
                                  "KHÔNG ảnh hưởng các dầm đã lưu trong Thư viện."):
                    st.session_state[_confirm_key] = True
                    st.rerun()
            else:
                st.warning(
                    "⚠️ Chỉ xóa **bộ mặt cắt mặc định** của trình dựng dầm "
                    "(file `spt_sections_saved.json`). Các **dầm trong Thư viện "
                    "KHÔNG bị ảnh hưởng**. Bạn chắc chắn?")
                _dc1, _dc2 = st.columns(2)
                if _dc1.button("✓ Xóa mặc định", key=f"{pfx}_del_save_yes",
                               type="primary", use_container_width=True):
                    _SAVE_FILE.unlink(missing_ok=True)
                    st.session_state.pop(_confirm_key, None)
                    st.toast("Đã xóa mặt cắt mặc định. Dầm trong Thư viện vẫn còn.")
                    st.rerun()
                if _dc2.button("Hủy", key=f"{pfx}_del_save_no",
                               use_container_width=True):
                    st.session_state.pop(_confirm_key, None)
                    st.rerun()
        else:
            st.caption("Chưa có dữ liệu lưu — bấm 💾 Lưu mặc định để lưu.")

    _upload_row()
    st.divider()

    # ═══ Hàng 2: Khai báo đoạn mặt cắt ════════════════════════════════════════
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
        cad_state.setdefault("fill_sec", _bt_fill_default)
        cad_state.setdefault("segs_ver", 0)

    _ALL  = list(secs.keys())
    _PAL  = ["#44aa66","#8855cc","#4488cc","#cc8844","#dd5577","#4499bb","#99aa22","#cc5533"]
    _SCOL = {k: _PAL[i % len(_PAL)] for i, k in enumerate(_ALL)}
    _LCOL = "#cc8844"

    # Tùy chọn HAI ĐẦU DẦM KHÁC NHAU (không đối xứng)
    _asym = st.toggle(
        "🔀 Hai đầu dầm khác nhau (không đối xứng)",
        value=bool(cad_state.get("asym", False)), key=f"{pfx}_asym",
        help="Bật nếu đầu dầm phía này khác đầu kia (vd đầu mố ≠ đầu trụ). "
             "Tắt = hai đầu đối xứng (mirror nửa dầm).",
    )
    cad_state["asym"] = _asym
    _SD    = cad_state["segs"]
    _full  = L_m * 1000.0

    if _asym:
        # Lần đầu bật: clone nửa phải từ nửa trái để kế thừa, người dùng sửa sau
        cad_state.setdefault("segs_right", [dict(s) for s in _SD])
        cad_state.setdefault("segs_right_ver", 0)
        _SDR = cad_state["segs_right"]
        st.markdown(f"**① Đoạn đầu TRÁI → giữa** (toàn dầm L = {_full:.0f} mm)")
        _render_seg_rows(_SD,  _ALL, _full, f"{pfx}_L", "segs_ver",       cad_state)
        st.markdown("**② Đoạn đầu PHẢI → giữa**")
        _render_seg_rows(_SDR, _ALL, _full, f"{pfx}_R", "segs_right_ver", cad_state)
        _L_used  = (sum(float(s.get("length", 0)) for s in _SD)
                    + sum(float(s.get("length", 0)) for s in _SDR))
        L_fill   = _full - _L_used
        _cap_txt = f"toàn dầm {_full:.0f} mm"
    else:
        st.markdown(f"**Đoạn mặt cắt — nửa dầm** (L/2 = {L_half:.0f} mm)")
        _render_seg_rows(_SD, _ALL, L_half, f"{pfx}_L", "segs_ver", cad_state)
        _L_used  = sum(float(s.get("length", 0)) for s in _SD)
        L_fill   = L_half - _L_used
        _cap_txt = f"L/2 {L_half:.0f} mm"

    st.markdown("---")
    _cur_fill = cad_state.get("fill_sec", _bt_fill_default)
    _fi2 = _ALL.index(_cur_fill) if _cur_fill in _ALL else 0
    cad_state["fill_sec"] = st.selectbox(
        f"Đoạn giữa nhịp (fill = {max(L_fill, 0):.0f} mm)",
        _ALL, index=_fi2, key=f"{pfx}_fill_sec",
    )
    if L_fill < 0:
        st.error(f"Tổng đoạn {_L_used:.0f} mm > {_cap_txt} — giảm chiều dài đoạn.")

    # ═══ Hàng 2b: Sơ đồ dầm (toàn bộ chiều rộng) ════════════════════════════
    st.divider()
    _sch_ctrl_l, _sch_ctrl_r = st.columns([1, 1])
    _sch_mode = _sch_ctrl_l.radio(
        "Chế độ sơ đồ",
        ["Nửa dầm", "Toàn dầm"],
        index=int(st.session_state.get(f"{pfx}_sch_mode", 0)),
        horizontal=True,
        key=f"{pfx}_sch_mode_rb",
    )
    st.session_state[f"{pfx}_sch_mode"] = 0 if _sch_mode == "Nửa dầm" else 1
    _h_sch = _sch_ctrl_r.slider(
        "↕ Cao sơ đồ", min_value=60, max_value=300, step=10,
        value=int(st.session_state.get(f"{pfx}_h_sch", 100)),
        key=f"{pfx}_h_sch_sl",
        help="Kéo để phóng to / thu nhỏ sơ đồ trắc dọc",
    )
    st.session_state[f"{pfx}_h_sch"] = _h_sch

    # Xây vùng màu từ list đoạn (đầu → giữa nhịp)
    _fsc = cad_state.get("fill_sec", _bt_fill_default)
    def _zones_of(_seglist):
        _zz = []
        for _sg in _seglist:
            _zl = float(_sg.get("length", 0))
            if _sg["type"] == "loft":
                _zlab = f"{_sg.get('from_sec','?')}→{_sg.get('to_sec','?')}"
                _zcl  = _LCOL
            else:
                _zlab = _sg.get("sec", "?")
                _zcl  = _SCOL.get(_zlab, "#668899")
            _zz.append((_zl, _zlab, _zcl))
        return _zz

    _fill_zone = (max(L_fill, 0), _fsc, _SCOL.get(_fsc, "#668899"))

    if _asym:
        # Toàn dầm BẤT ĐỐI XỨNG: trái(đầu→giữa) + fill + phải đảo(giữa→đầu)
        _zr = list(reversed(_zones_of(_SDR)))
        _zr = [(_zl, ("→".join(reversed(_lab.split("→"))) if "→" in _lab else _lab), _cl)
               for (_zl, _lab, _cl) in _zr]
        _zones_sch = _zones_of(_SD) + [_fill_zone] + _zr
        _x_total = _full; _x_mid = None
        _x_label = "mm từ đầu dầm (toàn dầm — 2 đầu khác nhau)"
    else:
        _zones_half = _zones_of(_SD) + [_fill_zone]
        if _sch_mode == "Toàn dầm":
            _zones_sch = list(_zones_half) + list(reversed(_zones_half))
            _x_total = L_m * 1000
            _x_mid   = L_half
            _x_label = "mm từ đầu dầm (toàn nhịp)"
        else:
            _zones_sch = _zones_half
            _x_total = L_half
            _x_mid   = None
            _x_label = "mm từ đầu dầm (nửa nhịp)"

    _fig_sch = go.Figure()
    _x0_s = 0.0
    for _zl, _zlab, _zcl in _zones_sch:
        if _zl <= 0:
            continue
        _r, _g, _b = int(_zcl[1:3],16), int(_zcl[3:5],16), int(_zcl[5:7],16)
        _fig_sch.add_shape(type="rect", x0=_x0_s, x1=_x0_s+_zl, y0=0, y1=1,
                           fillcolor=f"rgba({_r},{_g},{_b},0.55)",
                           line=dict(color="#fff", width=0.5))
        if _zl > _x_total * 0.04:
            _fig_sch.add_annotation(x=_x0_s+_zl/2, y=0.5, text=_zlab,
                                    showarrow=False, font=dict(size=9, color="#fff"))
        _x0_s += _zl

    # Đường tim (chỉ ở chế độ toàn dầm)
    if _x_mid is not None:
        _fig_sch.add_shape(type="line", x0=_x_mid, x1=_x_mid, y0=0, y1=1,
                           line=dict(color="#ffffff", width=1.5, dash="dot"))
        _fig_sch.add_annotation(x=_x_mid, y=1.05, text="CL", showarrow=False,
                                font=dict(size=8, color="#ffffff"), yref="paper")

    _fig_sch.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=_h_sch, margin=dict(l=10, r=10, t=12, b=22),
        xaxis=dict(range=[0, _x_total], showgrid=False, tickformat=".0f",
                   tickfont=dict(size=8),
                   title=dict(text=_x_label, font=dict(size=8))),
        yaxis=dict(visible=False), showlegend=False,
    )
    st.plotly_chart(_fig_sch, use_container_width=True,
                    key=f"{pfx}_sch_fig", config={"displayModeBar": False})

    # ═══ Hàng 3: 3D Wireframe — toàn bộ chiều rộng ════════════════════════════
    st.divider()
    _avail = {k: v for k, v in secs.items() if v.outer}
    _SD_3d  = cad_state.get("segs", [])
    _SDR_3d = cad_state.get("segs_right", []) if _asym else []
    _L_used_3d = (sum(float(s.get("length", 0)) for s in _SD_3d)
                  + (sum(float(s.get("length", 0)) for s in _SDR_3d) if _asym else 0))
    _cap_total = _full if _asym else L_half
    L_fill_3d  = _cap_total - _L_used_3d

    try:
        if len(_avail) < 1:
            st.info("Upload ít nhất 1 mặt cắt để xem 3D preview.", icon="ℹ")
        elif L_fill_3d < 0:
            st.warning(f"Tổng đoạn {_L_used_3d:.0f} mm > {_cap_total:.0f} mm — giảm chiều dài.")
        else:
            # Bất đối xứng → mirror=False, khai báo NGUYÊN dầm; đối xứng → mirror=True (nửa dầm)
            m3d = bb.BeamModel(length=L_m * 1000, mirror=not _asym)
            m3d.sections = {k: v.clone() for k, v in _avail.items()}

            def _has(*names):
                return all(n in m3d.sections for n in names)

            _fill_sec = cad_state.get("fill_sec", _bt_fill_default)
            if not _has(_fill_sec):
                _fill_sec = next(iter(m3d.sections), None)

            if _asym:
                # trái(đầu→giữa) + fill(giữa) + phải đảo(giữa→đầu)
                _segs  = _segdicts_to_segments(bb, _SD_3d,  _has, _avail, reverse=False)
                if _fill_sec:
                    _segs.append(bb.Segment("constant", section=_fill_sec, length="fill"))
                _segs += _segdicts_to_segments(bb, _SDR_3d, _has, _avail, reverse=True)
            else:
                _segs = _segdicts_to_segments(bb, _SD_3d, _has, _avail, reverse=False)
                if _fill_sec:
                    _segs.append(bb.Segment("constant", section=_fill_sec, length="fill"))
            m3d.segments = _segs

            _traces = bb.build_3d_wireframe(m3d)
            _fig3d  = go.Figure(data=_traces)

            _h3d = st.slider(
                "↕ Cao view 3D", min_value=400, max_value=1200, step=50,
                value=int(st.session_state.get(f"{pfx}_h3d", 700)),
                key=f"{pfx}_h3d_sl",
                help="Kéo để phóng to / thu nhỏ khung nhìn 3D",
            )
            st.session_state[f"{pfx}_h3d"] = _h3d

            _fig3d.update_layout(
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                height=_h3d, margin=dict(l=0, r=0, t=40, b=0),
                title=dict(
                    text=f"3D Wireframe — {_bt_label}",
                    font=dict(size=14, color="#9ac8e8"), x=0.5,
                ),
                scene=dict(
                    xaxis=dict(title="X (mm)", backgroundcolor="rgba(0,0,0,0)",
                               gridcolor="rgba(128,128,128,0.35)", showbackground=True),
                    yaxis=dict(title="Y — dọc dầm (mm)", backgroundcolor="rgba(0,0,0,0)",
                               gridcolor="rgba(128,128,128,0.35)", showbackground=True),
                    zaxis=dict(title="Z (mm)", backgroundcolor="rgba(0,0,0,0)",
                               gridcolor="rgba(128,128,128,0.35)", showbackground=True),
                    bgcolor="#12202e", aspectmode="data",
                    camera=dict(eye=dict(x=1.4, y=-1.6, z=0.9)),
                ),
            )
            if _PLOT is not None:
                _PLOT.to_concrete_3d(_fig3d)   # khối đặc màu bê tông (quy tắc thể hiện)
            st.plotly_chart(_fig3d, use_container_width=True,
                            key=f"{pfx}_3d_large",
                            config={"displayModeBar": True,
                                    "modeBarButtonsToRemove": ["toImage"]})

            if st.button(
                "🏗️ Cập nhật 3D toàn cầu & Bố trí chung",
                type="primary", use_container_width=True,
                key=f"{pfx}_commit_3d",
                help="Ghi mô hình dầm này vào tab 3D Tổng hợp và Bố trí chung",
            ):
                st.session_state["spt_beam_model"] = m3d
                st.session_state["spt_L_m"] = L_m
                st.session_state.pop("spt_beam_traces_cache", None)
                # Chỉ lưu file mặc định cho DẦM GỐC (biến thể chỉ giữ trong phiên,
                # tránh ghi đè spt_sections_saved.json bằng mặt cắt biến thể).
                if _role_sel == "default":
                    _save_defaults(secs, cad_state)
                    _msg_extra = "& lưu cấu hình"
                else:
                    _msg_extra = f"(vai trò: {dict(_role_opts)[_role_sel]})"
                st.toast(f"✅ Đã cập nhật 3D toàn cầu {_msg_extra}. Chuyển tab 🏗️ để xem.",
                         icon="✅")

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


def _beam_span_list(d: dict) -> list:
    """Danh sách (x_start, x_end) từng nhịp — ĐỒNG BỘ với bản vẽ cầu qua
    11-BanVe_KetCau.calc_span_layout (nhịp chính căng giữa tĩnh không, nhịp đều).
    Fallback về chia đều từ x_mo_trai nếu không nạp được module bản vẽ."""
    geo    = d.get("geo_logic", {})
    kcn    = d.get("kcn_result") or d.get("ai_result", {})
    x0     = float(geo.get("x_mo_trai", -60.0))
    L_nhip = float(kcn.get("chieu_dai", 38.0))
    n_nhip = int(kcn.get("tong_so_nhip", 3))
    x_end  = float(geo.get("x_mo_phai", x0 + max(1, n_nhip) * L_nhip))
    x_tim  = float(geo.get("x_tim_clearance", (x0 + x_end) / 2))
    B_tk   = float(d.get("B", 20.0))
    bv = _get_banve()
    if bv is not None and hasattr(bv, "resolve_supports"):
        try:                              # ĐỒNG BỘ bố trí 2 tầng (nhịp chính/dẫn)
            supports, _ = bv.resolve_supports(d, x0, x_end, x_tim, B_tk, L_nhip)
            return list(zip(supports[:-1], supports[1:]))
        except Exception:
            pass
    if bv is not None and hasattr(bv, "calc_span_layout"):
        try:
            supports, _ = bv.calc_span_layout(x0, x_end, x_tim, B_tk, L_nhip)
            return list(zip(supports[:-1], supports[1:]))
        except Exception:
            pass
    return [(x0 + i * L_nhip, x0 + (i + 1) * L_nhip) for i in range(n_nhip)]


def _main_span_idx(d: dict, spans: list) -> int:
    """Chỉ số nhịp CHÍNH (chứa tim tĩnh không) trong danh sách spans."""
    if not spans:
        return -1
    geo   = d.get("geo_logic", {})
    x0    = float(geo.get("x_mo_trai", spans[0][0]))
    x_end = float(geo.get("x_mo_phai", spans[-1][1]))
    x_tim = float(geo.get("x_tim_clearance", (x0 + x_end) / 2))
    for i, (a, b) in enumerate(spans):
        if a - 1e-6 <= x_tim <= b + 1e-6:
            return i
    return len(spans) // 2


def _span_pfx(d: dict, base_pfx: str, i_span: int, main_idx: int) -> str:
    """pfx dầm cho nhịp i_span: nhịp chính → '{base}_main' nếu có dầm chính
    riêng (đã nạp), ngược lại dùng base_pfx (dầm nhịp dẫn)."""
    sl = (d or {}).get("span_layout") or {}
    if (sl.get("mode") == "two_tier" and sl.get("beam_main")
            and i_span == main_idx):
        main_pfx = f"{base_pfx}_main"
        if st.session_state.get(_cad_key(main_pfx, "sections")):
            return main_pfx
    return base_pfx


def _resolve_beam_sections(pfx: str = "spt"):
    """Bộ mặt cắt dầm + tên mặt cắt giữa nhịp (fill_sec), theo thứ tự ưu tiên:
    1) mặt cắt người dùng đang khai báo trong session,
    2) dầm mặc định đã lưu (spt_sections_saved.json),
    3) preset built-in (Super-T A-A/B-B/C-C).
    Đảm bảo mọi view luôn có dầm để vẽ kể cả khi chưa mở tab Chi tiết dầm."""
    bb = _get_bb()
    pfx = _resolve_storage_pfx(pfx)   # dò pfx thực (kèm hậu tố loại dầm)
    secs      = st.session_state.get(_cad_key(pfx, "sections"))
    cad_state = st.session_state.get(_cad_key(pfx, "state"), {}) or {}
    fill_sec  = cad_state.get("fill_sec")
    _has_outer = bool(secs) and any(getattr(s, "outer", None) for s in secs.values())
    if not _has_outer:
        saved = _load_defaults(bb)
        if saved:
            secs     = saved["secs"]
            fill_sec = fill_sec or saved.get("fill_sec")
        else:
            secs     = {sn: getattr(bb, fn)() for sn, (fn, _) in _SEC_PRESETS.items()}
            fill_sec = fill_sec or "B-B"
    return secs, (fill_sec or "B-B")


def _pick_beam_section(secs: dict, fill_sec: str):
    """Mặt cắt đại diện (ưu tiên fill_sec, sau đó mặt cắt đầu tiên có outer)."""
    sec = secs.get(fill_sec) if secs else None
    if sec and getattr(sec, "outer", None):
        return sec
    for _s in (secs or {}).values():
        if _s and getattr(_s, "outer", None):
            return _s
    return None


# ── DẦM BIẾN THỂ THEO VAI TRÒ (kế thừa đầy đủ — clone cây dầm theo từng vai trò) ──
# Vai trò = (vị trí DỌC cầu) × (vị trí NGANG cầu):
#   L = "B" nhịp biên (nhịp đầu/cuối, mố–trụ) | "G" nhịp giữa (trụ–trụ)
#   T = "B" dầm biên  (cây ngoài cùng)        | "G" dầm giữa
# Mỗi biến thể là 1 cây dầm RIÊNG, lưu state dưới pfx riêng: f"{base}__{key}".
#   key ∈ {"TB"(dầm biên), "LB"(nhịp biên), "LB_TB"(nhịp biên & dầm biên)}.
#   Mặc định (G,G) = base pfx. Vai trò chưa khai → fallback về cây gần nhất → base.
def _variant_active_key(base_pfx: str) -> str:
    return f"{base_pfx}__active_variants"


def _active_variants(base_pfx: str) -> set:
    """Tập key biến thể đã commit (vd {'TB','LB'})."""
    return set(st.session_state.get(_variant_active_key(base_pfx), set()))


def _variant_pfx(base_pfx: str, L: str, T: str, active: set) -> str:
    """pfx của cây dầm áp cho vai trò (L,T) theo fallback: khớp đúng → 1 trục → base."""
    if L == "B" and T == "B":
        cands = ["LB_TB", "LB", "TB"]
    elif L == "B":
        cands = ["LB"]
    elif T == "B":
        cands = ["TB"]
    else:
        cands = []
    for c in cands:
        if c in active:
            return f"{base_pfx}__{c}"
    return base_pfx


def _build_role_sections(base_pfx: str):
    """Tính trước mặt cắt đại diện cho base + từng biến thể (tránh đọc lặp).
    Trả về (active:set, secmap:{pfx: section})."""
    active = _active_variants(base_pfx)
    pfxs = {base_pfx} | {f"{base_pfx}__{v}" for v in active}
    secmap = {}
    for p in pfxs:
        secs, fill = _resolve_beam_sections(p)
        secmap[p] = _pick_beam_section(secs, fill)
    return active, secmap


def _cell_section(base_pfx, active, secmap, i_span, n_span, i_dam, n_dam):
    """Mặt cắt + cờ mirror cho 1 cây dầm tại (nhịp i_span, vị trí ngang i_dam).
    mirror=True cho dầm biên phía phải (cây ngoài cùng bên +y) để đối xứng."""
    L = "B" if (i_span == 0 or i_span == n_span - 1) else "G"
    T = "B" if (i_dam == 0 or i_dam == n_dam - 1) else "G"
    pfx = _variant_pfx(base_pfx, L, T, active)
    sec = secmap.get(pfx) or secmap.get(base_pfx)
    mirror = (T == "B" and i_dam == n_dam - 1)
    return sec, mirror


def _prism_tri(n: int):
    """Chỉ số tam giác (i,j,k) cho lăng trụ extrude từ đa giác n đỉnh
    (đỉnh 0..n-1 = mặt trước, n..2n-1 = mặt sau)."""
    ii, jj, kk = [], [], []
    for k in range(n):
        k1 = (k + 1) % n
        a, b, c, e = k, k1, k + n, k1 + n
        ii += [a, a]; jj += [b, c]; kk += [c, e]
    for k in range(1, n - 1):
        ii.append(0);  jj.append(k);     kk.append(k + 1)
    for k in range(1, n - 1):
        ii.append(n);  jj.append(n+k+1); kk.append(n + k)
    return ii, jj, kk


# ── QUÉT MẶT CẮT BIẾN THIÊN DỌC NHỊP (3D toàn cầu thể hiện 2 đầu/haunch khác nhau) ──
def _beam_model_from_pfx(pfx: str, L_mm: float):
    """Dựng bb.BeamModel từ state của 1 vai trò (pfx): mặt cắt + đoạn (segs/segs_right)
    + fill + cờ asym. Trả None nếu không có mặt cắt."""
    bb = _get_bb()
    pfx = _resolve_storage_pfx(pfx)   # dò pfx thực (kèm hậu tố loại dầm)
    secs_st   = st.session_state.get(_cad_key(pfx, "sections")) or {}
    cad_state = st.session_state.get(_cad_key(pfx, "state"), {}) or {}
    avail = {k: v for k, v in secs_st.items() if getattr(v, "outer", None)}
    if not avail:
        # Fallback: file lưu / preset (không có đoạn → dầm 1 mặt cắt)
        rs, fill = _resolve_beam_sections(pfx)
        avail = {k: v for k, v in (rs or {}).items() if getattr(v, "outer", None)}
        cad_state = {"fill_sec": fill}
    if not avail:
        return None
    asym   = bool(cad_state.get("asym", False))
    segs   = cad_state.get("segs", [])
    segs_r = cad_state.get("segs_right", []) if asym else []
    m = bb.BeamModel(length=float(L_mm), mirror=not asym)
    m.sections = {k: v.clone() for k, v in avail.items()}
    _has = lambda *n: all(x in m.sections for x in n)
    fs = cad_state.get("fill_sec")
    if not fs or not _has(fs):
        fs = next(iter(m.sections), None)
    seglist = _segdicts_to_segments(bb, segs, _has, avail, reverse=False)
    if fs:
        seglist.append(bb.Segment("constant", section=fs, length="fill"))
    if asym:
        seglist += _segdicts_to_segments(bb, segs_r, _has, avail, reverse=True)
    m.segments = seglist
    return m


def _beam_rings(m, N: int = 28):
    """List (frac∈[0,1], ring Nx2 mm[ngang,cao]) lấy mẫu mặt cắt dọc dầm.
    constant → 2 ring giống nhau; loft → nội suy (đã xoay khớp)."""
    bb = _get_bb()
    try:
        segs = bb._resolve_segments(m)
    except Exception:
        return []
    total = sum(s["length"] for s in segs) or 1.0
    def _ring(name):
        sec = m.sections.get(name)
        if not sec or not getattr(sec, "outer", None):
            return None
        try:
            return bb.resample_polygon(sec.outer, N, closed=True)
        except Exception:
            return None
    out = []; y = 0.0
    for seg in segs:
        L = seg["length"]; y1 = y + L
        if seg["type"] == "constant":
            ra = _ring(seg.get("section"))
            if ra is not None:
                out.append((y / total, ra)); out.append((y1 / total, ra))
        else:
            ra = _ring(seg.get("from_sec")); rb = _ring(seg.get("to_sec"))
            if ra is not None and rb is not None:
                try:
                    rb = bb._best_rotation(ra, rb)
                except Exception:
                    pass
                _NS = 4
                for i in range(_NS + 1):
                    t = i / _NS
                    out.append(((y + L * t) / total, ra * (1 - t) + rb * t))
            elif ra is not None:
                out.append((y / total, ra)); out.append((y1 / total, ra))
        y = y1
    return out


def _build_role_rings(base_pfx: str, L_mm: float, N: int = 28):
    """Ring dọc dầm cho base + từng biến thể (precompute). (active, ringmap{pfx:rings})."""
    active = _active_variants(base_pfx)
    pfxs = {base_pfx} | {f"{base_pfx}__{v}" for v in active}
    ringmap = {}
    for p in pfxs:
        m = _beam_model_from_pfx(p, L_mm)
        ringmap[p] = _beam_rings(m, N) if m is not None else []
    return active, ringmap


def _cell_rings(base_pfx, active, ringmap, i_span, n_span, i_dam, n_dam):
    """Ring + cờ mirror cho 1 cây dầm tại (nhịp, vị trí ngang) theo vai trò."""
    L = "B" if (i_span == 0 or i_span == n_span - 1) else "G"
    T = "B" if (i_dam == 0 or i_dam == n_dam - 1) else "G"
    pfx = _variant_pfx(base_pfx, L, T, active)
    rings = ringmap.get(pfx) or ringmap.get(base_pfx) or []
    mirror = (T == "B" and i_dam == n_dam - 1)
    return rings, mirror


def _tube_faces(M: int, N: int):
    """Tam giác hoá ống: M vòng × N điểm + 2 nắp đầu (FAN — chỉ đúng cho mặt
    cắt LỒI). Giữ lại cho tương thích; mesh dầm dùng _beam_solid_faces."""
    ii, jj, kk = [], [], []
    for r in range(M - 1):
        b0, b1 = r * N, (r + 1) * N
        for i in range(N):
            i1 = (i + 1) % N
            a, b, c, e = b0 + i, b0 + i1, b1 + i, b1 + i1
            ii += [a, a]; jj += [b, e]; kk += [e, c]
    for i in range(1, N - 1):           # nắp đầu
        ii.append(0); jj.append(i); kk.append(i + 1)
    _last = (M - 1) * N
    for i in range(1, N - 1):           # nắp cuối
        ii.append(_last); jj.append(_last + i + 1); kk.append(_last + i)
    return ii, jj, kk


def _ring_cap_faces(R, base: int, ydir: float):
    """Tam giác hoá NẮP của 1 vòng R (Nx2: [ngang x, cao z]) → list (i,j,k) tham
    chiếu đỉnh base..base+N-1. earcut (đúng cho mặt cắt LÕM như máng Super-T);
    fan dự phòng cho mặt cắt lồi.

    Mỗi tam giác được ĐỊNH HƯỚNG để thành phần pháp tuyến theo trục DỌC Y cùng
    dấu với ydir (+1/−1) → nắp được tô sáng ĐỀU như thành ống (hết loang màu/tối
    ở vách ngăn & đầu dầm do chiều quay earcut không nhất quán)."""
    R = np.asarray(R, dtype=float)
    n = len(R)
    tris = None
    try:
        from ezdxf.math import Vec2
        from ezdxf.math._mapbox_earcut import earcut as _earcut
        pts = [Vec2(float(p[0]), float(p[1])) for p in R]
        raw = _earcut(pts, [])
        idx = {}
        for m, p in enumerate(R):
            idx[(round(float(p[0]), 3), round(float(p[1]), 3))] = m
        out = []
        ok = True
        for tri in raw:
            try:
                out.append(tuple(idx[(round(v.x, 3), round(v.y, 3))] for v in tri))
            except KeyError:
                ok = False; break
        tris = out if (ok and out) else None
    except Exception:
        tris = None
    if not tris:                                  # fan dự phòng (mặt cắt lồi)
        tris = [(0, i, i + 1) for i in range(1, n - 1)]
    faces = []
    for (a, b, c) in tris:
        ax, az = R[b, 0] - R[a, 0], R[b, 1] - R[a, 1]
        bx, bz = R[c, 0] - R[a, 0], R[c, 1] - R[a, 1]
        ny = az * bx - ax * bz                     # thành phần Y pháp tuyến (Y=const)
        if ny != 0.0 and (ny < 0.0) != (ydir < 0.0):
            b, c = c, b                            # sai chiều → đảo để khớp ydir
        faces.append((base + a, base + b, base + c))
    return faces


def _same_ring_shape(Ra, Rb, tol: float = 1.0) -> bool:
    """2 vòng có CÙNG hình không (bất biến theo điểm bắt đầu / chiều xoay)?
    So khớp tập điểm đã sắp xếp — tránh bịt nắp thừa ở mối nối liên tục mà
    _best_rotation đã xoay lệch index (vd loft→fill cùng mặt cắt)."""
    if getattr(Ra, "shape", None) != getattr(Rb, "shape", None):
        return False
    a = Ra[np.lexsort((Ra[:, 1], Ra[:, 0]))]
    b = Rb[np.lexsort((Rb[:, 1], Rb[:, 0]))]
    return bool(np.max(np.hypot(a[:, 0] - b[:, 0], a[:, 1] - b[:, 1])) < tol)


def _beam_solid_faces(rings, N: int, eps: float = 1e-4):
    """Tam giác hoá khối dầm từ list (frac, R) — XỬ LÝ ĐÚNG vách ngăn/đổi mặt cắt.

    • Hai vòng cách nhau (Δfrac>eps) → THÀNH ống (band) như cũ.
    • Mối nối dài-0 (Δfrac≈0) ĐỔI mặt cắt (vd thân↔vách ngăn) → KHÔNG nối band
      xoắn nữa, mà BỊT NẮP phẳng 2 mặt (mặt cuối đoạn trước + mặt đầu đoạn sau).
      Silhouette ngoài trùng nhau → thành ngoài liền mạch (xuyên suốt); máng được
      lấp bằng mặt đặc của vách ngăn — hết lỗi mặt xoắn ở vách ngăn.
    • Mối nối dài-0 nhưng CÙNG hình → liền mạch (bỏ qua, không nắp).
    • 2 đầu dầm luôn bịt nắp.
    """
    M = len(rings)
    ii, jj, kk = [], [], []

    def _band(r):
        b0, b1 = r * N, (r + 1) * N
        for i in range(N):
            i1 = (i + 1) % N
            a, b, c, e = b0 + i, b0 + i1, b1 + i, b1 + i1
            ii.extend([a, a]); jj.extend([b, e]); kk.extend([e, c])

    def _cap(r, ydir):
        for (p, q, s) in _ring_cap_faces(rings[r][1], r * N, ydir):
            ii.append(p); jj.append(q); kk.append(s)

    if M >= 1:
        _cap(0, ydir=-1.0)                        # nắp đầu dầm (mặt −Y)
    for r in range(M - 1):
        if abs(rings[r + 1][0] - rings[r][0]) > eps:
            _band(r)                              # thành ống
        else:
            Ra, Rb = rings[r][1], rings[r + 1][1]
            same = _same_ring_shape(Ra, Rb)       # bất biến theo điểm bắt đầu/xoay
            if not same:                          # đổi mặt cắt → bịt 2 nắp
                _cap(r, ydir=+1.0)                # mặt cuối đoạn trước (+Y)
                _cap(r + 1, ydir=-1.0)            # mặt đầu đoạn sau (−Y)
    if M >= 1:
        _cap(M - 1, ydir=+1.0)                    # nắp cuối dầm (mặt +Y)
    return ii, jj, kk


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
    _spans  = _beam_span_list(d)
    result  = []
    _legend = True   # legend only on the very first trace

    for i_dam in range(n_dam):
        beam_y = x_first_dam + i_dam * kc_dam
        for span_x0, span_x1 in _spans:
            _scale = (span_x1 - span_x0) / L_m
            for _t in _raw:
                if not (hasattr(_t, 'x') and _t.x is not None and len(_t.x) > 0):
                    continue
                _tx = np.array(_t.x, dtype=float)
                _ty = np.array(_t.y, dtype=float)
                _tz = np.array(_t.z, dtype=float)

                bx = span_x0 + _ty * _scale / 1000.0
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


def _beam_end_section_name(vpfx: str):
    """Tên mặt cắt tại ĐẦU DẦM (đoạn đầu tiên dọc nửa dầm). None nếu không có segs."""
    cad_state = st.session_state.get(_cad_key(vpfx, "state"), {}) or {}
    segs = cad_state.get("segs") or []
    if segs:
        s0 = segs[0]
        return s0.get("sec") or s0.get("from_sec")
    return None


def get_mcn_overlay_traces(d: dict, pfx: str = "spt", which: str = "mid") -> list:
    """Trả về go.Scatter traces (2D) overlay mặt cắt dầm thực tế lên MCN điển hình.

    which="mid" → mặt cắt GIỮA dầm (fill_sec, mặc định);
    which="end" → mặt cắt tại ĐẦU dầm (đoạn segment đầu — thường đặc/vách dày).

    Hệ trục MCN: x = ngang cầu (m), y = cao độ (0=mặt bê tông bản, âm=xuống dưới).
    """
    active, secmap = _build_role_sections(pfx)
    if not any(s and getattr(s, "outer", None) for s in secmap.values()):
        return []

    kcn    = d.get("kcn_result") or d.get("ai_result", {})
    n_dam  = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
    kc_dam = float(kcn.get("khoang_cach_dam", 2.2))
    bc     = float(d.get("bc", 12.0))
    oh     = float(kcn.get("overhang", 0.5))
    t_ban  = float(d.get("t_ban_mm", 200)) / 1000.0

    x_first = -bc / 2 + oh
    result  = []
    # MCN điển hình = nhịp GIỮA (L="G"); chỉ khác theo vai trò NGANG (dầm biên/giữa).
    # Dùng span giả ở giữa (n_span=3, i_span=1) để _cell_section cho L="G".
    _leg = True
    for i_dam in range(n_dam):
        sec, mir = _cell_section(pfx, active, secmap, 1, 3, i_dam, n_dam)
        _drop_holes = False
        if which == "end":
            # Mặt cắt tại đầu dầm của đúng cây dầm (variant) ở vị trí ngang này.
            _T = "B" if (i_dam == 0 or i_dam == n_dam - 1) else "G"
            _vpfx = _variant_pfx(pfx, "G", _T, active)
            _secs_v, _fill_v = _resolve_beam_sections(_vpfx)
            _en = _beam_end_section_name(_vpfx)
            _sec_end = (_secs_v or {}).get(_en) if _en else None
            if _sec_end is not None and getattr(_sec_end, "outer", None):
                sec = _sec_end
            else:
                # Không có mặt cắt đầu dầm riêng → đầu dầm là khối ĐẶC (bịt khoang
                # rỗng), bỏ lỗ để phân biệt rõ với mặt cắt giữa nhịp (có khoang rỗng).
                _drop_holes = True
        if sec is None or not getattr(sec, "outer", None):
            continue
        _sgn = -1.0 if mir else 1.0
        x_center = x_first + i_dam * kc_dam
        xs = [x_center + _sgn * p[0] / 1000.0 for p in sec.outer]
        ys = [-t_ban   + p[1] / 1000.0 for p in sec.outer]
        xs.append(xs[0]); ys.append(ys[0])
        result.append(go.Scatter(
            x=xs, y=ys,
            fill="toself",
            fillcolor="rgba(46,204,113,0.28)",
            line=dict(color="#27ae60", width=1.8),
            mode="lines",
            name=("Mặt cắt đầu dầm" if which == "end" else "Mặt cắt giữa dầm") if _leg else "",
            showlegend=_leg,
            hovertemplate="Mặt cắt dầm thực tế<extra></extra>",
        ))
        _leg = False
        for hole in ([] if _drop_holes else (sec.holes or [])):
            if not hole:
                continue
            hx = [x_center + _sgn * p[0] / 1000.0 for p in hole]
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
    L_half = L_m / 2.0

    def _full_pts_for(_pfx: str):
        """Profil dầm (full_pts mm) cho 1 pfx; None nếu không dựng được."""
        cad_state = st.session_state.get(_cad_key(_pfx, "state"), {}) or {}
        segs_data = cad_state.get("segs", [])
        secs_st, fill_sec = _resolve_beam_sections(_pfx)
        if not segs_data:
            _saved = _load_defaults(_get_bb())
            if _saved:
                segs_data = _saved.get("segs", []) or []

        def _h_mm(name: str):
            s = secs_st.get(name)
            if not s or not s.outer:
                return None
            zvals = [p[1] for p in s.outer]
            return abs(min(zvals)) if zvals else None

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
        if _x < L_half:
            pts.append((_x, h_fill))
            pts.append((L_half, h_fill))
        if not pts:
            return None
        return pts + [(L_m - p[0], p[1]) for p in reversed(pts[:-1])]

    base_pts = _full_pts_for(pfx)
    if base_pts is None:
        return []

    # Dầm RIÊNG cho nhịp chính (nếu khai báo dầm chính khác nhịp dẫn)
    sl       = (d or {}).get("span_layout") or {}
    main_pfx = f"{pfx}_main"
    main_pts = None
    if (sl.get("mode") == "two_tier" and sl.get("beam_main")
            and st.session_state.get(_cad_key(main_pfx, "sections"))):
        main_pts = _full_pts_for(main_pfx) or base_pts

    # ── Bố trí nhịp ĐỒNG BỘ với bản vẽ trắc dọc (resolve_supports — 2 tầng). ──
    _bv       = _get_banve()
    B_tk      = float(d.get("B", 20.0))
    x_end_geo = float(geo.get("x_mo_phai", x0 + max(1, n_nhip) * L_nhip))
    x_tim     = float(geo.get("x_tim_clearance", (x0 + x_end_geo) / 2))
    if _bv is not None and hasattr(_bv, "resolve_supports"):
        supports, _ = _bv.resolve_supports(d, x0, x_end_geo, x_tim, B_tk, L_nhip)
    elif _bv is not None and hasattr(_bv, "calc_span_layout"):
        supports, _ = _bv.calc_span_layout(x0, x_end_geo, x_tim, B_tk, L_nhip)
    else:
        supports = [x0 + i * L_nhip for i in range(n_nhip + 1)]
    spans    = list(zip(supports[:-1], supports[1:]))
    main_idx = _main_span_idx(d, spans)

    result = []
    for i_nhip, (span_x0, span_x1) in enumerate(spans):
        full_pts = (main_pts if (main_pts is not None and i_nhip == main_idx)
                    else base_pts)
        scale   = (span_x1 - span_x0) / L_m

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


def get_plan_beam_traces(d: dict, pfx: str = "spt") -> list:
    """Trả về go.Scatter traces overlay đường tim dầm lên mặt bằng cầu (bình đồ).

    Hệ trục bình đồ: x = lý trình (m), y = ngang cầu (m).
    """
    secs_st = st.session_state.get(_cad_key(pfx, "sections"), {})
    if not any(s and s.outer for s in secs_st.values()):
        return []

    kcn    = d.get("kcn_result") or d.get("ai_result", {})
    geo    = d.get("geo_logic", {})
    x0     = float(geo.get("x_mo_trai", -60.0))
    x_end  = float(geo.get("x_mo_phai", x0 + float(geo.get("L_cau", 120))))
    n_dam  = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
    kc_dam = float(kcn.get("khoang_cach_dam", 2.2))
    bc     = float(d.get("bc", 12.0))
    oh     = float(kcn.get("overhang", 0.5))

    x_first = -bc / 2 + oh
    result  = []
    for i in range(n_dam):
        y_beam = x_first + i * kc_dam
        result.append(go.Scatter(
            x=[x0, x_end], y=[y_beam, y_beam],
            mode="lines",
            line=dict(color="#27ae60", width=1.5, dash="dot"),
            name="Tim dầm (DXF)" if i == 0 else "",
            showlegend=(i == 0),
            hovertemplate=f"Tim dầm {i+1} | offset={y_beam:.2f}m<extra></extra>",
        ))
    return result


def _beam_corner_idx(vx, vy, vz, Np, ang_deg=18.0):
    """Chỉ số điểm là GÓC THẬT trên mặt cắt (vòng 0): nơi tiết diện ĐỔI HƯỚNG
    > ang_deg. Bỏ qua điểm trên đoạn thẳng/đường cong mịn (do resample N điểm)."""
    import math
    out = []
    for i in range(Np):
        a = (vx[(i - 1) % Np], vy[(i - 1) % Np], vz[(i - 1) % Np])
        b = (vx[i], vy[i], vz[i])
        c = (vx[(i + 1) % Np], vy[(i + 1) % Np], vz[(i + 1) % Np])
        v1 = (b[0]-a[0], b[1]-a[1], b[2]-a[2])
        v2 = (c[0]-b[0], c[1]-b[1], c[2]-b[2])
        n1 = math.sqrt(sum(t*t for t in v1)); n2 = math.sqrt(sum(t*t for t in v2))
        if n1 < 1e-9 or n2 < 1e-9:
            out.append(i); continue
        cs = max(-1.0, min(1.0, sum(v1[k]*v2[k] for k in range(3)) / (n1*n2)))
        if math.degrees(math.acos(cs)) > ang_deg:   # đổi hướng > ngưỡng → góc
            out.append(i)
    return out or list(range(Np))


def _beam_edge_trace(vx, vy, vz, M, Np, name="", color="#3a3a3a", width=1.4):
    """Chỉ vẽ NÉT ĐƯỜNG BAO khối dầm (Scatter3d): cạnh DỌC tại các GÓC THẬT của
    tiết diện (nét kết nối giữa 2 mặt phẳng) + viền mặt cắt 2 ĐẦU. KHÔNG vẽ cạnh
    dọc tại mọi điểm resample, KHÔNG viền từng vòng → đường bao gọn.
    vx/vy/vz là lưới M vòng × Np điểm (ring-major)."""
    ex, ey, ez = [], [], []
    for i in _beam_corner_idx(vx, vy, vz, Np):   # cạnh DỌC chỉ tại GÓC tiết diện
        for r in range(M):
            k = r * Np + i
            ex.append(vx[k]); ey.append(vy[k]); ez.append(vz[k])
        ex.append(None); ey.append(None); ez.append(None)
    for r in (0, M - 1):                      # viền mặt cắt CHỈ ở 2 đầu dầm
        b = r * Np
        for i in range(Np):
            ex.append(vx[b + i]); ey.append(vy[b + i]); ez.append(vz[b + i])
        ex.append(vx[b]); ey.append(vy[b]); ez.append(vz[b])
        ex.append(None); ey.append(None); ez.append(None)
    return go.Scatter3d(x=ex, y=ey, z=ez, mode="lines",
                        line=dict(color=color, width=width),
                        name=name, showlegend=bool(name), hoverinfo="skip")


def get_beam_model_mesh_traces(d: dict, pfx: str = "spt") -> list:
    """go.Mesh3d (solid) dầm cho 3D toàn cầu — QUÉT mặt cắt biến thiên dọc nhịp
    (thể hiện 2 đầu/haunch khác nhau), theo VAI TRÒ từng cây (biên/giữa × nhịp biên/giữa)."""
    kcn    = d.get("kcn_result") or d.get("ai_result", {})
    n_dam  = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
    kc_dam = float(kcn.get("khoang_cach_dam", 2.2))
    bc     = float(d.get("bc",                12.0))
    oh     = float(kcn.get("overhang",         0.5))
    cao_dd = float(d.get("cao_day_dam",         8.0))
    H_dam  = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    L_mm   = float(st.session_state.get("spt_L_m", kcn.get("chieu_dai", 38.0))) * 1000.0

    active, ringmap = _build_role_rings(pfx, L_mm)
    if not any(ringmap.values()):
        return []

    z_top   = cao_dd + H_dam
    x_first = -bc / 2 + oh
    _spans  = _beam_span_list(d)
    n_span  = len(_spans)
    main_idx = _main_span_idx(d, _spans)

    # Dầm RIÊNG cho nhịp chính (nếu có) → precompute rings của pfx chính
    sl       = (d or {}).get("span_layout") or {}
    main_pfx = f"{pfx}_main"
    main_rt  = None
    if (sl.get("mode") == "two_tier" and sl.get("beam_main")
            and st.session_state.get(_cad_key(main_pfx, "sections"))):
        _am, _rm = _build_role_rings(main_pfx, L_mm)
        if any(_rm.values()):
            main_rt = (main_pfx, _am, _rm)

    result  = []
    _legend = True
    for i_dam in range(n_dam):
        beam_y = x_first + i_dam * kc_dam
        for i_span, (sx0, sx1) in enumerate(_spans):
            if main_rt is not None and i_span == main_idx:
                _p, _a, _r = main_rt
                rings, mir = _cell_rings(_p, _a, _r,
                                         i_span, n_span, i_dam, n_dam)
            else:
                rings, mir = _cell_rings(pfx, active, ringmap,
                                         i_span, n_span, i_dam, n_dam)
            if not rings or len(rings) < 2:
                continue
            _sgn = -1.0 if mir else 1.0
            Np   = len(rings[0][1]); M = len(rings)
            vx, vy, vz = [], [], []
            for frac, R in rings:
                ch = sx0 + frac * (sx1 - sx0)
                for i in range(Np):
                    vx.append(ch)
                    vy.append(beam_y + _sgn * R[i, 0] / 1000.0)
                    vz.append(z_top + R[i, 1] / 1000.0)
            _ii, _jj, _kk = _beam_solid_faces(rings, Np)
            result.append(go.Mesh3d(
                x=vx, y=vy, z=vz,
                i=_ii, j=_jj, k=_kk,
                color="#5d8aa8", opacity=0.95,
                name="Dầm DXF thực tế" if _legend else "",
                showlegend=_legend,
                flatshading=True,
                lighting=dict(ambient=0.82, diffuse=0.40, specular=0.08,
                              roughness=0.75, fresnel=0.03),
                lightposition=dict(x=500, y=300, z=1500),
                hovertemplate="<b>Dầm DXF</b><extra></extra>" if _legend else None,
            ))
            result.append(_beam_edge_trace(vx, vy, vz, M, Np))  # đường bao/cạnh dầm
            _legend = False
    return result


def _model_from_record(rec: dict):
    """Dựng bb.BeamModel từ bản ghi dầm thư viện. Trả (m, L_mm, bb) hoặc (None,...)."""
    bb = _get_bb()
    rec = rec or {}
    secs = rec.get("sections") or {}
    if not any((v or {}).get("outer") for v in secs.values()):
        return None, 0.0, bb
    L_mm = float(rec.get("chieu_dai", 38.2) or 38.2) * 1000.0
    m = bb.BeamModel(length=L_mm, mirror=True)
    m.sections = {
        k: bb.CrossSection(name=k, outer=list(v.get("outer", [])),
                           holes=[list(h) for h in v.get("holes", [])], open=False)
        for k, v in secs.items() if (v or {}).get("outer")
    }
    _has = lambda *n: all(x in m.sections for x in n)
    seglist = _segdicts_to_segments(bb, rec.get("segs", []), _has, m.sections)
    fs = rec.get("fill_sec")
    if not fs or not _has(fs):
        fs = next(iter(m.sections), None)
    if fs:
        seglist.append(bb.Segment("constant", section=fs, length="fill"))
    m.segments = seglist
    return m, L_mm, bb


def _beam_record_solid_traces(m, L_mm, N=40):
    rings = _beam_rings(m, N)
    if len(rings) < 2:
        return None
    vx, vy, vz = [], [], []
    for frac, R in rings:
        yy = frac * L_mm / 1000.0
        for i in range(N):
            vx.append(R[i, 0] / 1000.0)
            vy.append(yy)
            vz.append(R[i, 1] / 1000.0)
    ii, jj, kk = _beam_solid_faces(rings, N)
    M = len(rings)
    mesh = go.Mesh3d(
        x=vx, y=vy, z=vz, i=ii, j=jj, k=kk,
        color="#5d8aa8", opacity=0.96, flatshading=True,
        lighting=dict(ambient=0.82, diffuse=0.40, specular=0.08,
                      roughness=0.75, fresnel=0.03),
        lightposition=dict(x=500, y=300, z=1500),
        name="Dầm (mô hình thư viện)", showlegend=True,
        hovertemplate="<b>Dầm thư viện</b><extra></extra>")
    # Mesh + đường bao/cạnh để nhìn rõ nét trên 3D
    return [mesh, _beam_edge_trace(vx, vy, vz, M, N)]


def beam_record_solid_fig(rec: dict, N: int = 40):
    """3D SOLID (Shaded) của 1 DẦM từ bản ghi thư viện. Trả go.Figure | None."""
    m, L_mm, _ = _model_from_record(rec)
    if m is None:
        return None
    traces = _beam_record_solid_traces(m, L_mm, N)
    if not traces:
        return None
    fig = go.Figure(traces)
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", height=460,
        margin=dict(l=0, r=0, t=30, b=0),
        scene=dict(xaxis_title="Ngang dầm (m)", yaxis_title="Dọc dầm (m)",
                   zaxis_title="Cao (m)", aspectmode="data",
                   camera=dict(eye=dict(x=1.7, y=-1.9, z=0.8))),
    )
    return fig


def _order_sec_names(names):
    """Sắp mặt cắt theo A-A, B-B, C-C, … (chữ cái), phần khác xếp sau."""
    def _key(n):
        s = str(n).strip().upper()
        return (0, s) if s and s[0].isalpha() else (1, s)
    return sorted(names, key=_key)


def _add_mcn_dims(fig, x_ctr, w, vmin, vmax, color="#c0392b"):
    """Đường kích thước (dim) bề rộng + chiều cao cho 1 mặt cắt, toạ độ dữ liệu mm."""
    xL, xR = x_ctr - w / 2.0, x_ctr + w / 2.0
    H = vmax - vmin
    off = max(90.0, 0.06 * max(w, H))        # khoảng đẩy đường dim ra ngoài
    tk  = max(45.0, off * 0.5)               # chiều dài nét nối/gờ
    # ── Dim BỀ RỘNG (nằm dưới mặt cắt) ─────────────────────────────────────
    y_d = vmin - off
    fig.add_trace(go.Scatter(
        x=[xL, xR], y=[y_d, y_d], mode="lines",
        line=dict(color=color, width=1.1), showlegend=False, hoverinfo="skip"))
    for xe in (xL, xR):                        # nét nối + gờ mũi tên
        fig.add_trace(go.Scatter(
            x=[xe, xe], y=[vmin, y_d - tk * 0.3], mode="lines",
            line=dict(color=color, width=0.8), showlegend=False, hoverinfo="skip"))
    fig.add_annotation(x=x_ctr, y=y_d, text=f"{w:.0f}", showarrow=False,
                       yshift=-9, font=dict(size=9, color=color),
                       bgcolor="rgba(255,255,255,0.85)")
    # ── Dim CHIỀU CAO (bên trái mặt cắt) ──────────────────────────────────
    x_d = xL - off
    fig.add_trace(go.Scatter(
        x=[x_d, x_d], y=[vmin, vmax], mode="lines",
        line=dict(color=color, width=1.1), showlegend=False, hoverinfo="skip"))
    for ye in (vmin, vmax):
        fig.add_trace(go.Scatter(
            x=[xL, x_d - tk * 0.3], y=[ye, ye], mode="lines",
            line=dict(color=color, width=0.8), showlegend=False, hoverinfo="skip"))
    fig.add_annotation(x=x_d, y=(vmin + vmax) / 2.0, text=f"{H:.0f}",
                       showarrow=False, xshift=-10, textangle=-90,
                       font=dict(size=9, color=color),
                       bgcolor="rgba(255,255,255,0.85)")


def beam_record_mcn_fig(rec: dict):
    """Các MẶT CẮT NGANG đã khai báo của dầm (A-A, B-B, …) xếp cạnh nhau."""
    m, _L, _bb = _model_from_record(rec)
    if m is None:
        return None
    names = [n for n in _order_sec_names(m.sections.keys())
             if m.sections[n].outer]
    if not names:
        return None
    # Pre-tính bề rộng từng mặt cắt để đặt cách nhau theo BAO (không đè nhau khi
    # mặt cắt rộng đứng cạnh mặt cắt hẹp).
    geo = {}
    for nm in names:
        sec = m.sections[nm]
        us = [p[0] for p in sec.outer]; vs = [p[1] for p in sec.outer]
        geo[nm] = dict(cx=(min(us) + max(us)) / 2.0,
                       w=(max(us) - min(us)) or 600.0,
                       vmin=min(vs), vmax=max(vs))
    fig = go.Figure()
    gap = 700.0                               # khe hở BAO giữa 2 mặt cắt (mm)
    ticks, tickt = [], []
    x_off = geo[names[0]]["w"] / 2.0
    prev_w = None
    for nm in names:
        sec = m.sections[nm]
        cx = geo[nm]["cx"]; w = geo[nm]["w"]
        if prev_w is not None:                # tâm cách tâm = nửa+khe+nửa
            x_off += prev_w / 2.0 + gap + w / 2.0
        xs = [(p[0] - cx) + x_off for p in sec.outer] + [(sec.outer[0][0] - cx) + x_off]
        ys = [p[1] for p in sec.outer] + [sec.outer[0][1]]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, fill="toself", fillcolor="rgba(100,160,200,0.35)",
            line=dict(color="#34607a", width=1.7), mode="lines",
            name=nm, hoverinfo="skip"))
        for h in sec.holes:
            if len(h) < 3:
                continue
            hx = [(p[0] - cx) + x_off for p in h] + [(h[0][0] - cx) + x_off]
            hy = [p[1] for p in h] + [h[0][1]]
            fig.add_trace(go.Scatter(
                x=hx, y=hy, fill="toself", fillcolor="white",
                line=dict(color="#34607a", width=1), mode="lines",
                showlegend=False, hoverinfo="skip"))
        _add_mcn_dims(fig, x_off, w, geo[nm]["vmin"], geo[nm]["vmax"])
        ticks.append(x_off); tickt.append(nm)
        prev_w = w
    fig.update_layout(
        template="plotly_white", height=400,
        title=dict(text="① Mặt cắt ngang các vị trí (mm)", x=0.5, font=dict(size=12)),
        xaxis=dict(tickvals=ticks, ticktext=tickt, showgrid=False, zeroline=False),
        yaxis=dict(title="Cao (mm)", scaleanchor="x", scaleratio=1,
                   showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5, zeroline=False),
        margin=dict(l=70, r=20, t=50, b=50), showlegend=True,
        legend=dict(orientation="h", y=-0.14, font=dict(size=9)))
    return fig


def _beam_envelopes(rec: dict, N=64):
    m, L_mm, _ = _model_from_record(rec)
    if m is None:
        return None
    rings = _beam_rings(m, N)
    if len(rings) < 2:
        return None
    xs, ztop, zbot, yl, yr = [], [], [], [], []
    for frac, R in rings:
        xs.append(frac * L_mm / 1000.0)
        ztop.append(float(R[:, 1].max()) / 1000.0)
        zbot.append(float(R[:, 1].min()) / 1000.0)
        yl.append(float(R[:, 0].min()) / 1000.0)
        yr.append(float(R[:, 0].max()) / 1000.0)
    return xs, ztop, zbot, yl, yr, L_mm / 1000.0


def beam_record_elev_fig(rec: dict):
    """MẶT CẮT DỌC tim dầm — bao hình chiều cao theo chiều dài."""
    e = _beam_envelopes(rec)
    if not e:
        return None
    xs, zt, zb, yl, yr, L = e
    fig = go.Figure(go.Scatter(
        x=xs + xs[::-1], y=zt + zb[::-1], fill="toself",
        fillcolor="rgba(100,160,200,0.35)", line=dict(color="#34607a", width=1.7),
        mode="lines", name="Mặt cắt dọc", hoverinfo="skip"))
    fig.update_layout(
        template="plotly_white", height=300,
        title=dict(text=f"② Mặt cắt dọc tim dầm · L={L:.1f}m", x=0.5, font=dict(size=12)),
        xaxis=dict(title="Dọc dầm (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5),
        yaxis=dict(title="Cao (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5),
        margin=dict(l=55, r=20, t=50, b=45))
    return fig


def beam_record_plan_fig(rec: dict):
    """MẶT BẰNG dầm (nhìn từ trên) — bao hình bề rộng theo chiều dài."""
    e = _beam_envelopes(rec)
    if not e:
        return None
    xs, zt, zb, yl, yr, L = e
    fig = go.Figure(go.Scatter(
        x=xs + xs[::-1], y=yr + yl[::-1], fill="toself",
        fillcolor="rgba(120,170,140,0.35)", line=dict(color="#3a6a4a", width=1.7),
        mode="lines", name="Mặt bằng", hoverinfo="skip"))
    fig.update_layout(
        template="plotly_white", height=280,
        title=dict(text=f"③ Mặt bằng dầm (nhìn từ trên) · L={L:.1f}m",
                   x=0.5, font=dict(size=12)),
        xaxis=dict(title="Dọc dầm (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5),
        yaxis=dict(title="Ngang (m)", showgrid=True, gridcolor="rgba(128,128,128,0.35)", gridwidth=0.5),
        margin=dict(l=55, r=20, t=50, b=45))
    return fig


def beam_record_figs(rec: dict):
    """Gói 4 hình (mcn/elev/plan/solid) của 1 dầm thư viện. {} nếu không dựng được."""
    if not (rec and rec.get("sections")):
        return {}
    out = {}
    for key, fn in (("mcn", beam_record_mcn_fig), ("elev", beam_record_elev_fig),
                    ("plan", beam_record_plan_fig), ("solid", beam_record_solid_fig)):
        try:
            out[key] = fn(rec)
        except Exception:
            out[key] = None
    return out


def get_beam_model_mesh_traces_vn2000(d: dict, df_geology, he_so_z: float = 1.0,
                                      pfx: str = "spt") -> list:
    """Như get_beam_model_mesh_traces nhưng đặt dầm trong hệ toạ độ VN-2000 ĐÃ
    TRỪ ORIGIN (trùng hệ với địa hình của ve_dia_hinh_3d) — dùng cho view
    '3D Tổng hợp' (terrain). Ánh xạ (lý trình, offset ngang) → (X,Y) theo tim
    tuyến rồi trừ origin = tim tuyến tại lý trình nhỏ nhất. z × he_so_z.

    Phải dùng hàm này (KHÔNG dùng bản chainage) khi chèn dầm lên figure địa
    hình, nếu không dầm sẽ lệch hệ → auto-range nổ tung, không zoom được.
    """
    if df_geology is None or getattr(df_geology, "empty", True):
        return []
    need = {"Lý trình", "X_VN2000", "Y_VN2000", "Góc_Tuyến", "Offset"}
    if need - set(df_geology.columns):
        return []

    kcn    = d.get("kcn_result") or d.get("ai_result", {})
    n_dam  = int(kcn.get("so_luong_dam") or kcn.get("so_luong_dam_mcn", 5))
    kc_dam = float(kcn.get("khoang_cach_dam", 2.2))
    bc     = float(d.get("bc", 12.0))
    oh     = float(kcn.get("overhang", 0.5))
    cao_dd = float(d.get("cao_day_dam", 8.0))
    H_dam  = float(kcn.get("chieu_cao_dam") or kcn.get("chieu_cao", 1.75))
    L_mm   = float(st.session_state.get("spt_L_m", kcn.get("chieu_dai", 38.0))) * 1000.0

    active, ringmap = _build_role_rings(pfx, L_mm)
    if not any(ringmap.values()):
        return []

    df_cl = (df_geology[df_geology["Offset"] == 0]
             [["Lý trình", "X_VN2000", "Y_VN2000", "Góc_Tuyến"]]
             .drop_duplicates("Lý trình").sort_values("Lý trình"))
    if df_cl.empty:
        return []
    lt_v = df_cl["Lý trình"].values
    vx_v = df_cl["X_VN2000"].values
    vy_v = df_cl["Y_VN2000"].values
    gc_v = df_cl["Góc_Tuyến"].values
    _i0  = int(np.argmin(lt_v))
    x_org = float(vx_v[_i0]); y_org = float(vy_v[_i0])

    def _vn(s, off):
        xc = float(np.interp(s, lt_v, vx_v))
        yc = float(np.interp(s, lt_v, vy_v))
        g  = float(np.interp(s, lt_v, gc_v))
        p  = g + np.pi / 2
        return (xc + off * np.cos(p) - x_org, yc + off * np.sin(p) - y_org)

    z_top   = cao_dd + H_dam
    x_first = -bc / 2 + oh
    spans   = _beam_span_list(d)
    n_span  = len(spans)
    main_idx = _main_span_idx(d, spans)

    # Dầm RIÊNG cho nhịp chính (nếu có)
    sl       = (d or {}).get("span_layout") or {}
    main_pfx = f"{pfx}_main"
    main_rt  = None
    if (sl.get("mode") == "two_tier" and sl.get("beam_main")
            and st.session_state.get(_cad_key(main_pfx, "sections"))):
        _am, _rm = _build_role_rings(main_pfx, L_mm)
        if any(_rm.values()):
            main_rt = (main_pfx, _am, _rm)

    result = []
    _legend = True
    for i_dam in range(n_dam):
        beam_y = x_first + i_dam * kc_dam
        for i_span, (sx0, sx1) in enumerate(spans):
            if main_rt is not None and i_span == main_idx:
                _p, _a, _r = main_rt
                rings, mir = _cell_rings(_p, _a, _r,
                                         i_span, n_span, i_dam, n_dam)
            else:
                rings, mir = _cell_rings(pfx, active, ringmap,
                                         i_span, n_span, i_dam, n_dam)
            if not rings or len(rings) < 2:
                continue
            _sgn = -1.0 if mir else 1.0
            Np   = len(rings[0][1]); M = len(rings)
            vX, vY, vZ = [], [], []
            for frac, R in rings:
                ch = sx0 + frac * (sx1 - sx0)
                for i in range(Np):
                    X, Y = _vn(ch, beam_y + _sgn * R[i, 0] / 1000.0)
                    vX.append(X); vY.append(Y); vZ.append((z_top + R[i, 1] / 1000.0) * he_so_z)
            _ii, _jj, _kk = _beam_solid_faces(rings, Np)
            result.append(go.Mesh3d(
                x=vX, y=vY, z=vZ,
                i=_ii, j=_jj, k=_kk,
                color="#5d8aa8", opacity=0.95,
                name="Dầm DXF thực tế" if _legend else "",
                showlegend=_legend,
                flatshading=True,
                lighting=dict(ambient=0.82, diffuse=0.40, specular=0.08,
                              roughness=0.75, fresnel=0.03),
                lightposition=dict(x=500, y=300, z=1500),
                hovertemplate="<b>Dầm DXF</b><extra></extra>" if _legend else None,
            ))
            result.append(_beam_edge_trace(vX, vY, vZ, M, Np))  # đường bao/cạnh dầm
            _legend = False
    return result
