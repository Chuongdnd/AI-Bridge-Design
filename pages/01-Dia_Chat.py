"""
Trang 01 — Khai báo dữ liệu địa chất công trình
Cho phép người dùng tải template, upload file Excel địa chất,
xem kết quả phân tích và lưu vào Session State cho các module sau.
"""

import os
import io
import sys
import importlib

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Import loader ─────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    DC = importlib.import_module("00-DiaChat_Loader")
except Exception as _e:
    st.error(f"Không import được 00-DiaChat_Loader: {_e}")
    st.stop()

# ── Đường dẫn template ───────────────────────────────────────────────────────
_TEMPLATE_PATH = os.path.join(_ROOT, "Data", "Template_DiaChat.xlsx")

# ── Màu sắc lớp đất ──────────────────────────────────────────────────────────
_LAYER_COLORS = [
    "#8B6914", "#C8A96E", "#D4C9A0", "#A8C8A0",
    "#6B8E7A", "#5B7FA6", "#3A5F8A", "#2C4570",
    "#7B5EA7", "#4A7C59",
]


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _color_for_layer(ten_lop: str, idx: int) -> str:
    """Gán màu theo tên lớp hoặc index."""
    lop = str(ten_lop).upper().strip()
    color_map = {
        "K":  "#A0522D",  # đất đắp — nâu đỏ
        "1":  "#8B6914",
        "2":  "#C8A96E",
        "2A": "#D4B482",
        "2B": "#BCA06A",
        "3":  "#90A860",
        "4":  "#5B7FA6",
        "TK4":"#7FA0C8",
        "5":  "#C8D4A0",
    }
    return color_map.get(lop, _LAYER_COLORS[idx % len(_LAYER_COLORS)])


@st.cache_data(show_spinner=False)
def _load_cached(file_bytes: bytes, file_name: str):
    """Cache kết quả parse để không parse lại khi user tương tác UI."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        return DC.load_geology_excel(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# BIỂU ĐỒ
# ═══════════════════════════════════════════════════════════════════════════════
def _draw_plan_map(hk_list):
    """Bình đồ vị trí các hố khoan (scatter XY)."""
    xs = [hk["X"] for hk in hk_list if hk["X"] is not None]
    ys = [hk["Y"] for hk in hk_list if hk["Y"] is not None]
    names = [hk["ten"] for hk in hk_list if hk["X"] is not None]

    if not xs:
        return None

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text",
        marker=dict(size=14, color="#1F4E79", symbol="circle"),
        text=names,
        textposition="top center",
        textfont=dict(size=11),
        hovertemplate="<b>%{text}</b><br>X: %{x:.1f}<br>Y: %{y:.1f}<extra></extra>",
    ))
    fig.update_layout(
        title="Bình đồ vị trí hố khoan",
        xaxis_title="X (VN2000)",
        yaxis_title="Y (VN2000)",
        height=400,
        margin=dict(l=60, r=20, t=50, b=60),
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.35)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.35)", scaleanchor="x")
    return fig


def _draw_soil_columns(hk_list):
    """Hình trụ địa chất — mỗi hố khoan là một cột."""
    n = len(hk_list)
    if n == 0:
        return None

    fig = make_subplots(
        rows=1, cols=n,
        shared_yaxes=True,
        subplot_titles=[hk["ten"] for hk in hk_list],
        horizontal_spacing=0.04,
    )

    for col_idx, hk in enumerate(hk_list, start=1):
        lop_list = hk.get("lop_dat", [])
        Z_top = hk.get("Z", 0) or 0

        if not lop_list:
            continue

        # Tìm giới hạn sâu nhất
        z_bot = min(lp["cao_do_day"] for lp in lop_list if lp["cao_do_day"] is not None)

        for i, lp in enumerate(lop_list):
            color = _color_for_layer(lp["ten_lop"], i)
            dinh  = lp["cao_do_dinh"]
            day   = lp["cao_do_day"]
            if dinh is None or day is None:
                continue
            thick = dinh - day

            fig.add_trace(
                go.Bar(
                    x=[1],
                    y=[thick],
                    base=[day],
                    orientation="v",
                    marker_color=color,
                    marker_line=dict(color="white", width=0.5),
                    name=f"{hk['ten']}-{lp['ten_lop']}",
                    showlegend=False,
                    hovertemplate=(
                        f"<b>Lớp {lp['ten_lop']}</b><br>"
                        f"Đỉnh: {dinh:.2f} m<br>"
                        f"Đáy: {day:.2f} m<br>"
                        f"Dày: {thick:.2f} m<br>"
                        f"{lp['mo_ta'][:60]}...<extra></extra>"
                        if len(lp.get("mo_ta", "")) > 60
                        else (
                            f"<b>Lớp {lp['ten_lop']}</b><br>"
                            f"Đỉnh: {dinh:.2f} m<br>"
                            f"Đáy: {day:.2f} m<br>"
                            f"Dày: {thick:.2f} m<br>"
                            f"{lp.get('mo_ta', '')}<extra></extra>"
                        )
                    ),
                ),
                row=1, col=col_idx,
            )

            # Nhãn lớp
            mid = (dinh + day) / 2
            fig.add_annotation(
                x=0.5, y=mid,
                text=f"<b>{lp['ten_lop']}</b>",
                showarrow=False,
                font=dict(size=9, color="white"),
                xref=f"x{col_idx if col_idx > 1 else ''} domain",
                yref=f"y{col_idx if col_idx > 1 else ''}",
            )

    # Global y-axis phạm vi
    all_z = []
    for hk in hk_list:
        for lp in hk.get("lop_dat", []):
            if lp["cao_do_day"] is not None:
                all_z.append(lp["cao_do_day"])
            if lp["cao_do_dinh"] is not None:
                all_z.append(lp["cao_do_dinh"])

    y_min = min(all_z) - 2 if all_z else -50
    y_max = max(all_z) + 2 if all_z else 15

    fig.update_yaxes(range=[y_min, y_max], title_text="Cao độ (m)")
    fig.update_xaxes(showticklabels=False)
    fig.update_layout(
        height=max(500, int((y_max - y_min) * 7)),
        title="Hình trụ địa chất",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=60, r=20, t=80, b=40),
        barmode="stack",
    )
    return fig


def _draw_spt_profiles(hk_list):
    """Biểu đồ SPT-N theo độ sâu — nhiều hố khoan chồng nhau."""
    _COLORS = ["#1F4E79", "#C0392B", "#27AE60", "#F39C12", "#8E44AD", "#2980B9"]

    fig = go.Figure()
    has_data = False

    for i, hk in enumerate(hk_list):
        spt = hk.get("spt_data", [])
        if not spt:
            continue
        depths = [s for s, n in spt]
        ns     = [n for s, n in spt]
        has_data = True
        color = _COLORS[i % len(_COLORS)]

        fig.add_trace(go.Scatter(
            x=ns, y=depths,
            mode="lines+markers",
            name=hk["ten"],
            line=dict(color=color, width=2),
            marker=dict(size=6, color=color),
            hovertemplate="<b>%{fullData.name}</b><br>Độ sâu: %{y:.1f} m<br>N = %{x}<extra></extra>",
        ))

    if not has_data:
        return None

    # Đường tham chiếu
    max_depth = max(
        s for hk in hk_list for s, n in hk.get("spt_data", [])
    ) if any(hk.get("spt_data") for hk in hk_list) else 50

    for threshold, label, color, dash in [
        (10, "N=10 (đất yếu)", "orange", "dot"),
        (20, "N=20 (lớp chịu lực)", "green", "dash"),
    ]:
        fig.add_vline(
            x=threshold, line_dash=dash, line_color=color,
            annotation_text=label, annotation_position="top right",
            annotation_font_size=10,
        )

    fig.update_layout(
        title="Biểu đồ SPT-N theo độ sâu",
        xaxis_title="SPT-N (búa/30cm)",
        yaxis_title="Độ sâu (m)",
        yaxis=dict(autorange="reversed", range=[0, max_depth + 2]),
        xaxis=dict(range=[0, max(60, max(n for hk in hk_list for _, n in hk.get("spt_data", [])) + 5)]),
        height=600,
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(x=0.85, y=0.02),
        margin=dict(l=60, r=40, t=50, b=60),
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.35)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.35)")
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# GIAO DIỆN CHÍNH
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    st.title("🏗️ Khai báo dữ liệu địa chất công trình")
    st.markdown(
        """
        **Vai trò của bước này:**
        Nhập dữ liệu hố khoan (phân lớp địa chất + SPT-N) để hệ thống tự động
        tính các đặc trưng kỹ thuật làm đầu vào cho **Module 08 — Tư vấn móng cọc**.

        > Dữ liệu được đọc từ file Excel theo định dạng chuẩn. Tải template mẫu
        > để xem cấu trúc yêu cầu trước khi nhập liệu.
        """
    )

    # ── PHẦN 1: Tải template ─────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📥 Bước 1 — Tải template Excel mẫu")

    if os.path.exists(_TEMPLATE_PATH):
        with open(_TEMPLATE_PATH, "rb") as f:
            template_bytes = f.read()
        st.download_button(
            label="⬇️ Tải Template_DiaChat.xlsx",
            data=template_bytes,
            file_name="Template_DiaChat.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Template gồm 5 sheet: HUONG_DAN, Toado_HK, HK1, HK2, HK3, SPT",
        )
    else:
        st.warning("⚠️ Không tìm thấy file template. Kiểm tra Data/Template_DiaChat.xlsx")

    # ── PHẦN 2: Upload file ───────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📤 Bước 2 — Tải lên file Excel địa chất")

    uploaded = st.file_uploader(
        "Chọn file Excel địa chất (.xlsx / .xlsm)",
        type=["xlsx", "xlsm"],
        help="File phải có cấu trúc theo template hoặc tương thích (có sheet Toado_HK và SPT).",
    )

    if uploaded is None:
        st.info("👆 Tải lên file Excel để bắt đầu phân tích.")
        return

    # ── PHẦN 3: Đọc và xử lý ─────────────────────────────────────────────────
    with st.spinner("Đang đọc và phân tích dữ liệu địa chất…"):
        try:
            file_bytes = uploaded.read()
            data = _load_cached(file_bytes, uploaded.name)
        except Exception as exc:
            st.error(f"❌ Lỗi khi đọc file: {exc}")
            return

    hk_list = data.get("ho_khoan_list", [])
    errs    = data.get("validation_errors", [])
    dt_th   = data.get("dac_trung_tong_hop", {})

    if not hk_list:
        st.error("❌ Không đọc được hố khoan nào. Kiểm tra lại sheet Toado_HK.")
        return

    # ── PHẦN 4: Kết quả đọc ─────────────────────────────────────────────────
    st.markdown("---")
    st.subheader(f"📊 Bước 3 — Kết quả phân tích ({len(hk_list)} hố khoan)")

    # Validation badge
    if not errs:
        st.success(f"✅ Kiểm chứng đạt — {len(hk_list)} hố khoan, không có lỗi.")
    else:
        st.warning(f"⚠️ Đọc được {len(hk_list)} hố khoan, có **{len(errs)} cảnh báo/lỗi**.")
        with st.expander("Xem chi tiết cảnh báo / lỗi", expanded=True):
            df_err = pd.DataFrame(errs).rename(columns={
                "ten_sheet": "Sheet",
                "hang": "Hàng",
                "cot": "Cột",
                "mo_ta_loi": "Mô tả lỗi",
            })
            st.dataframe(df_err, use_container_width=True, hide_index=True)

    # Bảng tổng hợp hố khoan
    summary_rows = []
    for hk in hk_list:
        ten = hk["ten"]
        d   = dt_th.get(ten, {})
        summary_rows.append({
            "Hố khoan":        ten,
            "X":               f"{hk['X']:.1f}" if hk.get("X") else "—",
            "Y":               f"{hk['Y']:.1f}" if hk.get("Y") else "—",
            "Z (m)":           f"{hk['Z']:.2f}" if hk.get("Z") is not None else "—",
            "Số lớp":          len(hk.get("lop_dat", [])),
            "Khoan đến (m)":   d.get("do_sau_ket_thuc_khoan", "—"),
            "Chiều sâu lớp yếu (m)": d.get("chieu_sau_lop_yeu", "—"),
            "N TB lớp yếu":    d.get("spt_n_lop_yeu", "—"),
            "Chiều sâu lớp tốt (m)": d.get("chieu_sau_lop_tot", "—"),
            "N TB lớp tốt":    d.get("spt_n_lop_tot", "—"),
            "Đủ dữ liệu":      "✅" if d.get("dia_chat_du_lieu_co") else "⚠️",
        })

    df_sum = pd.DataFrame(summary_rows)
    st.dataframe(df_sum, use_container_width=True, hide_index=True)

    # Báo cáo text
    with st.expander("📋 Báo cáo kiểm chứng chi tiết (text)"):
        report = DC.validate_geology_data(data)
        st.code(report, language=None)

    # ── PHẦN 5: Trực quan hóa ────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📈 Bước 4 — Trực quan hóa địa chất")

    tab_map, tab_col, tab_spt = st.tabs([
        "🗺️ Bình đồ hố khoan",
        "🏛️ Hình trụ địa chất",
        "📉 Biểu đồ SPT-N",
    ])

    with tab_map:
        fig_map = _draw_plan_map(hk_list)
        if fig_map:
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.info("Không có tọa độ XY để vẽ bình đồ.")

    with tab_col:
        fig_col = _draw_soil_columns(hk_list)
        if fig_col:
            st.plotly_chart(fig_col, use_container_width=True)
            # Legend lớp đất
            all_lop = {}
            for hk in hk_list:
                for i, lp in enumerate(hk.get("lop_dat", [])):
                    key = lp["ten_lop"]
                    if key not in all_lop:
                        all_lop[key] = _color_for_layer(key, i)
            st.markdown("**Chú giải lớp đất:**")
            cols_leg = st.columns(min(len(all_lop), 6))
            for ci, (name, clr) in enumerate(all_lop.items()):
                with cols_leg[ci % len(cols_leg)]:
                    st.markdown(
                        f'<span style="background:{clr};padding:2px 8px;border-radius:3px;'
                        f'color:white;font-size:12px">Lớp {name}</span>',
                        unsafe_allow_html=True,
                    )
        else:
            st.info("Không có dữ liệu phân lớp để vẽ hình trụ.")

    with tab_spt:
        fig_spt = _draw_spt_profiles(hk_list)
        if fig_spt:
            st.plotly_chart(fig_spt, use_container_width=True)
        else:
            st.info("Không có dữ liệu SPT để vẽ biểu đồ.")

    # ── PHẦN 6: Xác nhận và lưu ──────────────────────────────────────────────
    st.markdown("---")
    st.subheader("💾 Bước 5 — Xác nhận và lưu dữ liệu")

    st.info(
        "Nhấn **Xác nhận & Lưu** để lưu dữ liệu địa chất vào Session State "
        "(`dia_chat_data`). Dữ liệu này sẽ được Module 08 (Tư vấn móng cọc) "
        "sử dụng tự động."
    )

    col_btn, col_status = st.columns([2, 5])
    with col_btn:
        if st.button("✅ Xác nhận & Lưu dữ liệu địa chất", type="primary"):
            st.session_state["dia_chat_data"] = data
            st.success(
                f"✅ Đã lưu dữ liệu **{len(hk_list)} hố khoan** vào Session State.\n\n"
                "Bạn có thể chuyển sang trang **Thiết kế cầu** để tiếp tục."
            )

    # Hiển thị trạng thái lưu hiện tại
    with col_status:
        existing = st.session_state.get("dia_chat_data")
        if existing:
            n_saved = len(existing.get("ho_khoan_list", []))
            st.info(f"📌 Session State hiện có: **{n_saved}** hố khoan đã lưu trước đó.")
        else:
            st.caption("Session State chưa có dữ liệu địa chất.")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__" or True:
    main()
