"""
Trang 12 — Dự toán Sơ bộ Tự động (TKCS)
Căn cứ: Nghị định 175/2024/NĐ-CP; QĐ 409/2025/QĐ-BXD.
"""

import importlib.util
import os
import copy
import hashlib
import json
from datetime import datetime

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="Dự toán Sơ bộ", page_icon="💰", layout="wide")

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ─────────────────────────────────────────────────────────────────────────────
# LOAD ENGINE
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _load_engine():
    spec = importlib.util.spec_from_file_location(
        "du_toan_engine", os.path.join(_DIR, "12-DuToan_SoBo.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

DT = _load_engine()


# ─────────────────────────────────────────────────────────────────────────────
# TIỆN ÍCH
# ─────────────────────────────────────────────────────────────────────────────

def _fmt(so_nghin: float, unit="ty") -> str:
    return DT.format_vnd(so_nghin, unit)


def _res() -> dict:
    return st.session_state.get("res") or {}


def _has_kcn() -> bool:
    r = _res()
    return bool(r.get("kcn_result") or r.get("ai_result"))


def _params_hash(d: dict) -> str:
    raw = json.dumps(d, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()[:8]


def _init_history():
    if "du_toan_history" not in st.session_state:
        st.session_state["du_toan_history"] = []


# ─────────────────────────────────────────────────────────────────────────────
# KIỂM TRA ĐIỀU KIỆN
# ─────────────────────────────────────────────────────────────────────────────

st.title("💰 Dự toán Sơ bộ — TKCS")
st.caption("Tự động sinh dự toán từ thông số đã tinh chỉnh | Nghị định 175/2024 | QĐ 409/2025")

if not _has_kcn():
    st.error("❌ Chưa có kết quả thiết kế kết cấu nhịp.")
    st.info(
        "Vui lòng hoàn thành các bước trước:  \n"
        "1. **Bước 1–3**: Nhập thông tin cầu và điều kiện địa hình  \n"
        "2. **Bước 4–6**: Chạy AI thiết kế kết cấu nhịp (Module 06)  \n"
        "3. *(Khuyến nghị)* Bước 7–8: AI mố trụ + móng cọc để có dự toán chính xác hơn"
    )
    st.stop()

_init_history()
res = _res()

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — CÀI ĐẶT THAM SỐ
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Tham số Dự toán")

    vung_mien = st.selectbox(
        "Vùng miền (hệ số địa phương)",
        list(DT.HE_SO_DIA_PHUONG.keys()),
        index=2,   # Đồng bằng Nam Bộ
    )
    st.caption(f"k_đp = {DT.HE_SO_DIA_PHUONG[vung_mien]:.2f}")

    cap_duong = st.selectbox(
        "Cấp đường công trình",
        list(DT.HE_SO_CAP_DUONG.keys()),
        index=3,   # Cấp III
    )
    st.caption(f"k_cap = {DT.HE_SO_CAP_DUONG[cap_duong]:.2f}")

    st.divider()
    st.subheader("Chi phí phụ trợ (%)")
    he_dt  = st.slider("Dự phòng",          5.0, 15.0, 10.0, 0.5)
    he_tk  = st.slider("Thiết kế + QLDA",   3.0, 8.0,   5.0, 0.5)
    he_ks  = st.slider("Khảo sát",          1.0, 4.0,   2.0, 0.5)
    he_tn  = st.slider("Thử nghiệm VL",     0.5, 2.0,   1.0, 0.5)
    he_bh  = st.slider("Bảo hiểm CT",       0.2, 1.5,   0.5, 0.1)
    vat_pct = st.number_input("VAT (%)", 0.0, 15.0, 10.0, 1.0)

    st.divider()
    beam_params_ok = bool(res.get("beam_params_final"))
    if beam_params_ok:
        st.success("✅ Sử dụng beam_params_final đã tinh chỉnh")
    else:
        st.info("ℹ️ Sử dụng thông số từ AI/catalog (chưa tinh chỉnh)")

# ─────────────────────────────────────────────────────────────────────────────
# NÚT TÍNH TOÁN
# ─────────────────────────────────────────────────────────────────────────────

col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 4])

with col_btn1:
    btn_calc = st.button("🔢 Tính toán Dự toán", type="primary",
                         use_container_width=True)

with col_btn2:
    btn_3pa  = st.button("📊 So sánh 3 Phương án",
                         use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# XỬ LÝ TÍNH TOÁN
# ─────────────────────────────────────────────────────────────────────────────

if btn_calc:
    with st.spinner("⏳ Đang tính toán dự toán sơ bộ..."):
        try:
            dt_result = DT.tinh_du_toan_so_bo(
                res, vung_mien, cap_duong,
                he_so_dt_pct = he_dt,
                he_so_tk_ql  = he_tk,
                he_so_ks     = he_ks,
                he_so_tn     = he_tn,
                he_so_bh     = he_bh,
                vat_pct      = vat_pct,
            )
            st.session_state["du_toan_result"] = dt_result

            # Lưu lịch sử
            ghi_chu = st.session_state.pop("du_toan_ghi_chu", "")
            history: list = st.session_state["du_toan_history"]
            history.append({
                "timestamp"        : datetime.now().isoformat(),
                "beam_params_hash" : _params_hash(res.get("beam_params_final") or {}),
                "vung_mien"        : vung_mien,
                "cap_duong"        : cap_duong,
                "tong_dau_tu"      : dt_result["tong_hop"]["tong_dau_tu"],
                "suat_dau_tu"      : dt_result["phan_tich"]["suat_dau_tu_trieu_m2"],
                "du_toan"          : copy.deepcopy(dt_result),
                "ghi_chu"          : ghi_chu or f"Phiên #{len(history)+1}",
            })
        except Exception as ex:
            st.error(f"Lỗi khi tính dự toán: {ex}")
            st.exception(ex)

if btn_3pa:
    with st.spinner("📊 Đang so sánh 3 phương án..."):
        try:
            ss_result = DT.so_sanh_du_toan_3_pa(res, vung_mien, cap_duong)
            st.session_state["du_toan_ss_result"] = ss_result
        except Exception as ex:
            st.error(f"Lỗi so sánh phương án: {ex}")

# ─────────────────────────────────────────────────────────────────────────────
# HIỂN THỊ KẾT QUẢ
# ─────────────────────────────────────────────────────────────────────────────

dt_result = st.session_state.get("du_toan_result")

if dt_result is None:
    st.info("Nhấn **Tính toán Dự toán** để bắt đầu. Hoặc chọn **So sánh 3 Phương án** để xem song song.")
    st.stop()

th = dt_result["tong_hop"]
ph = dt_result["phan_tich"]
ts = dt_result["thong_so"]
kl = dt_result["khoi_luong"]

# ── KPI cards ──
st.subheader("📋 Tóm tắt Dự toán")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Tổng đầu tư",
           f"{th['tong_dau_tu']/1e6:.3f} tỷ",
           f"XL: {th['tong_xay_lap']/1e6:.3f} tỷ")
c2.metric("Suất đầu tư",
           f"{ph['suat_dau_tu_trieu_m2']:.1f} tr/m²",
           f"Mặt cầu {ph['A_cau_m2']:.0f} m²")
c3.metric("KCN / Tổng XL",
           f"{ph['ty_le_KCN_pct']:.0f}%",
           f"{th['hm1_KCN']/1e6:.3f} tỷ")
c4.metric("Mố trụ / Tổng XL",
           f"{ph['ty_le_MTM_pct']:.0f}%",
           f"{th['hm2_MTM']/1e6:.3f} tỷ")
c5.metric("Móng cọc / Tổng XL",
           f"{ph['ty_le_MON_pct']:.0f}%",
           f"{th['hm3_MON']/1e6:.3f} tỷ")

# Cảnh báo suất đầu tư
canh_bao = ph.get("canh_bao", "")
if "✅" in canh_bao:
    st.success(canh_bao)
else:
    st.warning(canh_bao)

st.divider()

# ── Tabs chính ──
tab_tong, tab_ct, tab_bieu_do, tab_ss, tab_ls = st.tabs([
    "📊 Tổng hợp", "📋 Chi tiết hạng mục",
    "📈 Biểu đồ phân tích", "⚖️ So sánh 3 PA", "📚 Lịch sử"
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — TỔNG HỢP
# ════════════════════════════════════════════════════════════════════════════

with tab_tong:
    st.markdown(
        f"**Thông số công trình:** {ts['n_nhip']} nhịp × "
        f"{kl['dam']['L_dam_m']:.1f}m | {ts['loai_dam']} | "
        f"Bc = {ts['bc']}m | {ts['n_dam']} dầm/nhịp"
    )

    import pandas as pd

    rows_tong = [
        {"Hạng mục": "I. Kết cấu nhịp (KCN)",    "Thành tiền (nghìn đ)": th["hm1_KCN"],   "% / Xây lắp": f"{ph['ty_le_KCN_pct']:.1f}%"},
        {"Hạng mục": "II. Mố trụ cầu (MTM)",      "Thành tiền (nghìn đ)": th["hm2_MTM"],   "% / Xây lắp": f"{ph['ty_le_MTM_pct']:.1f}%"},
        {"Hạng mục": "III. Móng cọc",              "Thành tiền (nghìn đ)": th["hm3_MON"],   "% / Xây lắp": f"{ph['ty_le_MON_pct']:.1f}%"},
        {"Hạng mục": "IV. Bản mặt cầu + lớp phủ", "Thành tiền (nghìn đ)": th["hm4_BMC"],   "% / Xây lắp": f"{round(th['hm4_BMC']/th['tong_xay_lap']*100,1):.1f}%"},
        {"Hạng mục": "V. Phụ trợ",                 "Thành tiền (nghìn đ)": th["hm5_PHU"],   "% / Xây lắp": f"{round(th['hm5_PHU']/th['tong_xay_lap']*100,1):.1f}%"},
        {"Hạng mục": "▸ TỔNG CHI PHÍ XÂY LẮP",   "Thành tiền (nghìn đ)": th["tong_xay_lap"], "% / Xây lắp": "100%"},
        {"Hạng mục": "Dự phòng",                   "Thành tiền (nghìn đ)": th["du_phong"],  "% / Xây lắp": ""},
        {"Hạng mục": "Thiết kế + QLDA",            "Thành tiền (nghìn đ)": th["thiet_ke_QLDA"], "% / Xây lắp": ""},
        {"Hạng mục": "Khảo sát",                   "Thành tiền (nghìn đ)": th["khao_sat"],  "% / Xây lắp": ""},
        {"Hạng mục": "Thử nghiệm VL",              "Thành tiền (nghìn đ)": th["thu_nghiem"], "% / Xây lắp": ""},
        {"Hạng mục": "Bảo hiểm CT",                "Thành tiền (nghìn đ)": th["bao_hiem"],  "% / Xây lắp": ""},
        {"Hạng mục": "▸ TỔNG TRƯỚC THUẾ",         "Thành tiền (nghìn đ)": th["tong_truoc_VAT"], "% / Xây lắp": ""},
        {"Hạng mục": "VAT 10%",                    "Thành tiền (nghìn đ)": th["VAT"],        "% / Xây lắp": ""},
        {"Hạng mục": "★ TỔNG VỐN ĐẦU TƯ",        "Thành tiền (nghìn đ)": th["tong_dau_tu"], "% / Xây lắp": ""},
    ]

    def _fmt_cell(v):
        if isinstance(v, (int, float)):
            trieu = v / 1000
            return f"{trieu:,.1f} triệu"
        return v

    df_tong = pd.DataFrame(rows_tong)
    df_tong["Triệu VND"] = df_tong["Thành tiền (nghìn đ)"].apply(
        lambda x: f"{x/1000:,.1f}" if isinstance(x, (int, float)) else "")
    df_tong["Tỷ VND"]    = df_tong["Thành tiền (nghìn đ)"].apply(
        lambda x: f"{x/1e6:.3f}" if isinstance(x, (int, float)) else "")

    st.dataframe(
        df_tong[["Hạng mục", "Tỷ VND", "Triệu VND", "% / Xây lắp"]],
        hide_index=True, use_container_width=True,
        column_config={
            "Hạng mục" : st.column_config.TextColumn("Hạng mục", width="large"),
            "Tỷ VND"   : st.column_config.TextColumn("Tỷ VND",   width="small"),
            "Triệu VND": st.column_config.TextColumn("Triệu VND", width="medium"),
            "% / Xây lắp":st.column_config.TextColumn("% XL",    width="small"),
        }
    )

    # Khối lượng chính
    with st.expander("📦 Khối lượng vật liệu chính"):
        c_kl1, c_kl2, c_kl3 = st.columns(3)
        with c_kl1:
            st.markdown("**Kết cấu nhịp**")
            st.write(f"Bê tông M50: {kl['dam']['bt_m3']:.1f} m³")
            st.write(f"Cốt thép thường: {kl['dam']['thep_thuong_tan']:.2f} t")
            st.write(f"Cáp DUL: {kl['dam']['thep_DUL_tan']:.2f} t")
            st.write(f"Cốp pha: {kl['dam']['coppha_m2']:.0f} m²")
        with c_kl2:
            st.markdown("**Mố trụ cầu**")
            st.write(f"Bê tông M35: {kl['tru']['vol_BT_M35_m3']:.1f} m³")
            st.write(f"Cốt thép: {kl['tru']['thep_mo_tru_tan']:.2f} t")
            st.write(f"({kl['tru']['n_tru']} trụ + 2 mố)")
        with c_kl3:
            st.markdown("**Móng cọc**")
            st.write(f"{kl['coc']['loai_coc']}")
            st.write(f"Ø{kl['coc']['D_coc_mm']:.0f}mm × {kl['coc']['L_coc_m']}m")
            st.write(f"Tổng dài: {kl['coc']['L_coc_tong_m']:.0f} m")
            st.write(f"Bệ móng: {kl['coc']['vol_be_m3']:.1f} m³")

    # Download buttons
    c_dl1, c_dl2 = st.columns(2)
    xlsx_bytes = DT.xuat_excel(dt_result)
    if xlsx_bytes:
        ts_str = datetime.now().strftime("%Y%m%d_%H%M")
        c_dl1.download_button(
            "📥 Tải bảng dự toán Excel",
            data=xlsx_bytes,
            file_name=f"du_toan_so_bo_{ts_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    # Markdown report
    md_report = _build_md_report(dt_result)
    c_dl2.download_button(
        "📄 Tải báo cáo Markdown",
        data=md_report.encode("utf-8"),
        file_name=f"du_toan_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
        mime="text/markdown",
        use_container_width=True,
    )


def _build_md_report(dt: dict) -> str:
    th = dt["tong_hop"]
    ph = dt["phan_tich"]
    ts = dt["thong_so"]
    lines = [
        "# BÁO CÁO DỰ TOÁN SƠ BỘ — TKCS",
        f"**Thời gian xuất:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        f"**Loại dầm:** {ts['loai_dam']}  |  **Bc:** {ts['bc']}m  |  "
        f"**Cấp đường:** {ts['cap_duong']}  |  **Vùng:** {ts['vung_mien']}",
        "", "---", "",
        "## Tổng hợp Chi phí",
        "",
        "| Hạng mục | Tỷ VND |",
        "| --- | --- |",
        f"| I. Kết cấu nhịp | {th['hm1_KCN']/1e6:.3f} |",
        f"| II. Mố trụ cầu | {th['hm2_MTM']/1e6:.3f} |",
        f"| III. Móng cọc | {th['hm3_MON']/1e6:.3f} |",
        f"| IV. Bản mặt cầu + lớp phủ | {th['hm4_BMC']/1e6:.3f} |",
        f"| V. Phụ trợ | {th['hm5_PHU']/1e6:.3f} |",
        f"| **Tổng xây lắp** | **{th['tong_xay_lap']/1e6:.3f}** |",
        f"| Tổng trước thuế | {th['tong_truoc_VAT']/1e6:.3f} |",
        f"| **Tổng đầu tư (có VAT)** | **{th['tong_dau_tu']/1e6:.3f}** |",
        "", "---", "",
        "## Phân tích",
        "",
        f"- **Mặt cầu:** {ph['A_cau_m2']:.0f} m²  (L={ph['L_cau_m']:.1f}m)",
        f"- **Suất đầu tư:** {ph['suat_dau_tu_trieu_m2']:.1f} triệu VND/m²",
        f"- **Tỉ lệ KCN:** {ph['ty_le_KCN_pct']:.0f}% | MTM: {ph['ty_le_MTM_pct']:.0f}% | Móng: {ph['ty_le_MON_pct']:.0f}%",
        f"- {ph['canh_bao']}",
        "", "---",
        "> *AI Bridge Design — UTH | TCVN 11823:2017 | QĐ 409/2025/QĐ-BXD*",
    ]
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — CHI TIẾT HẠNG MỤC
# ════════════════════════════════════════════════════════════════════════════

with tab_ct:
    def _show_hm(label: str, hm_list: list, color: str):
        with st.expander(f"**{label}**", expanded=True):
            rows = []
            for hm in hm_list:
                rows.append({
                    "Tên hạng mục": hm["ten"],
                    "ĐV"          : hm["don_vi"],
                    "Khối lượng"  : hm["khoi_luong"],
                    "Đơn giá (K)" : f"{hm['don_gia']:,.0f}",
                    "Thành tiền (K)" : f"{hm['thanh_tien']:,.0f}",
                    "Triệu VND"   : f"{hm['thanh_tien']/1000:.1f}",
                    "Ghi chú"     : hm.get("ghi_chu", ""),
                })
            import pandas as pd
            df = pd.DataFrame(rows)
            st.dataframe(df, hide_index=True, use_container_width=True)
            tong_hm = sum(h["thanh_tien"] for h in hm_list)
            st.markdown(f"**Tổng: {tong_hm/1e6:.3f} tỷ VND**")

    _show_hm("I. Kết cấu nhịp — Dầm BTDƯL", dt_result["hang_muc_1"], "#BDD7E8")
    _show_hm("II. Mố trụ cầu",               dt_result["hang_muc_2"], "#E2EFDA")
    _show_hm("III. Móng cọc",                 dt_result["hang_muc_3"], "#FFF2CC")
    _show_hm("IV. Bản mặt cầu + lớp phủ",    dt_result["hang_muc_4"], "#FCE4D6")
    _show_hm("V. Phụ trợ",                    dt_result["hang_muc_5"], "#F2F2F2")


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — BIỂU ĐỒ PHÂN TÍCH
# ════════════════════════════════════════════════════════════════════════════

with tab_bieu_do:
    col_p1, col_p2 = st.columns(2)

    # ── Pie chart phân bổ chi phí ──
    labels = ["KCN", "Mố trụ", "Móng cọc", "Bản mặt cầu", "Phụ trợ"]
    values = [
        th["hm1_KCN"], th["hm2_MTM"], th["hm3_MON"],
        th["hm4_BMC"], th["hm5_PHU"],
    ]
    colors = ["#2196F3", "#4CAF50", "#FF9800", "#E91E63", "#9C27B0"]

    fig_pie = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.4,
        marker=dict(colors=colors),
        textinfo="label+percent",
        hovertemplate="%{label}: %{value:,.0f} nghìn đ (%{percent})<extra></extra>",
    ))
    fig_pie.update_layout(
        title="Phân bổ Chi phí Xây lắp",
        showlegend=True,
        margin=dict(t=50, b=20, l=0, r=0),
        height=380,
    )
    col_p1.plotly_chart(fig_pie, use_container_width=True)

    # ── Bar chart KCN vs MTM vs Móng ──
    fig_bar = go.Figure()
    cats  = ["Kết cấu nhịp", "Mố trụ", "Móng cọc", "Bản mặt cầu", "Phụ trợ"]
    vals  = [th["hm1_KCN"]/1e6, th["hm2_MTM"]/1e6, th["hm3_MON"]/1e6,
             th["hm4_BMC"]/1e6, th["hm5_PHU"]/1e6]
    fig_bar.add_trace(go.Bar(
        x=cats, y=vals, marker_color=colors,
        text=[f"{v:.3f} tỷ" for v in vals],
        textposition="outside",
    ))
    fig_bar.update_layout(
        title="Chi phí theo Hạng mục (tỷ VND)",
        yaxis_title="Tỷ VND",
        margin=dict(t=50, b=20, l=0, r=0),
        height=380,
    )
    col_p2.plotly_chart(fig_bar, use_container_width=True)

    # ── Biểu đồ cấu thành chi phí dầm ──
    st.subheader("Cấu thành chi phí Kết cấu nhịp")
    hm1 = dt_result["hang_muc_1"]
    fig_dam = go.Figure(go.Bar(
        x=[h["ten"][:40] for h in hm1],
        y=[h["thanh_tien"] / 1e6 for h in hm1],
        marker_color="#2196F3",
        text=[f"{h['thanh_tien']/1e6:.3f} tỷ" for h in hm1],
        textposition="outside",
    ))
    fig_dam.update_layout(
        yaxis_title="Tỷ VND",
        xaxis_tickangle=-20,
        height=350,
        margin=dict(t=20, b=60, l=0, r=0),
    )
    st.plotly_chart(fig_dam, use_container_width=True)

    # ── Tham chiếu suất đầu tư ──
    st.subheader("So sánh Suất đầu tư tham chiếu")
    suat_tt = ph["suat_dau_tu_trieu_m2"]
    khoang = {
        "Cao tốc": (14, 22), "Cấp I": (12, 18), "Cấp II": (10, 16),
        "Cấp III": (8, 13),  "Cấp IV": (6, 11),
    }
    fig_ref = go.Figure()
    for cd, (lo, hi) in khoang.items():
        fig_ref.add_trace(go.Bar(
            name=cd, x=[cd], y=[hi - lo],
            base=[lo],
            marker_color=("rgba(33,150,243,0.5)"
                          if cd == ts["cap_duong"] else "rgba(200,200,200,0.4)"),
            showlegend=False,
        ))
    fig_ref.add_hline(y=suat_tt, line_dash="dash", line_color="red",
                      annotation_text=f"Dự toán: {suat_tt:.1f} tr/m²")
    fig_ref.update_layout(
        barmode="overlay",
        yaxis_title="Triệu VND/m²",
        title="Suất đầu tư vs Dải tham chiếu QĐ 409/2025",
        height=350,
        margin=dict(t=50, b=20, l=0, r=0),
    )
    st.plotly_chart(fig_ref, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — SO SÁNH 3 PHƯƠNG ÁN
# ════════════════════════════════════════════════════════════════════════════

with tab_ss:
    ss_result = st.session_state.get("du_toan_ss_result")

    if ss_result is None:
        st.info("Nhấn **So sánh 3 Phương án** ở trên để tính toán và so sánh.")
    else:
        ss = ss_result["so_sanh"]
        import pandas as pd

        st.subheader("Bảng so sánh chi phí 3 phương án")
        pa_keys = ["pa1", "pa2", "pa3"]
        rows_ss = []
        metrics = [
            ("Loại dầm", "loai_dam"),
            ("Chi phí KCN (tỷ)", "chi_phi_KCN_ty"),
            ("Chi phí mố trụ (tỷ)", "chi_phi_MTM_ty"),
            ("Chi phí móng (tỷ)", "chi_phi_MON_ty"),
            ("Tổng xây lắp (tỷ)", "tong_xay_lap_ty"),
            ("Tổng đầu tư (tỷ)", "tong_dau_tu_ty"),
            ("Suất đt (tr/m²)", "suat_dau_tu_trieu_m2"),
            ("Chênh lệch so min (tỷ)", "chenh_so_min_ty"),
            ("Chênh lệch (%)", "chenh_so_min_pct"),
            ("Điểm kinh tế (30đ)", "diem_kinh_te"),
        ]
        for (label, key) in metrics:
            row = {"Chỉ tiêu": label}
            for pa_k in pa_keys:
                m = ss.get(pa_k, {})
                v = m.get(key, "—")
                if isinstance(v, float) and key not in ("loai_dam",):
                    row[f"PA {pa_k[-1]}"] = f"{v:.3f}" if v < 100 else f"{v:.1f}"
                else:
                    row[f"PA {pa_k[-1]}"] = str(v)
            rows_ss.append(row)

        df_ss = pd.DataFrame(rows_ss)
        # Highlight best (min cost) PA
        min_ty = min(ss[k].get("tong_dau_tu_ty", 999) for k in pa_keys)

        st.dataframe(df_ss, hide_index=True, use_container_width=True)

        # Highlight PA tốt nhất
        best_pa = min(pa_keys, key=lambda k: ss[k].get("tong_dau_tu_ty", 999))
        best_loai = ss[best_pa].get("loai_dam", "?")
        st.success(f"🏆 Phương án kinh tế nhất: **{best_loai}** (PA{best_pa[-1]}) — Tổng đầu tư thấp nhất")

        # Bar chart so sánh
        fig_ss = go.Figure()
        cats_ss = ["KCN", "Mố trụ", "Móng", "Bản+LP", "Phụ trợ"]
        colors_ss = ["#2196F3", "#4CAF50", "#FF9800"]
        for idx, pa_k in enumerate(pa_keys):
            pa_dt = ss_result[pa_k]["tong_hop"]
            fig_ss.add_trace(go.Bar(
                name=ss[pa_k]["loai_dam"],
                x=cats_ss,
                y=[pa_dt["hm1_KCN"]/1e6, pa_dt["hm2_MTM"]/1e6,
                   pa_dt["hm3_MON"]/1e6, pa_dt["hm4_BMC"]/1e6,
                   pa_dt["hm5_PHU"]/1e6],
                marker_color=colors_ss[idx],
            ))
        fig_ss.update_layout(
            barmode="group", title="So sánh chi phí theo hạng mục (tỷ VND)",
            yaxis_title="Tỷ VND", height=420,
        )
        st.plotly_chart(fig_ss, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — LỊCH SỬ DỰ TOÁN
# ════════════════════════════════════════════════════════════════════════════

with tab_ls:
    history: list = st.session_state.get("du_toan_history", [])

    if not history:
        st.info("Chưa có phiên tính dự toán nào. Nhấn **Tính toán Dự toán** để bắt đầu.")
    else:
        st.markdown(f"**{len(history)} phiên tính dự toán đã lưu**")
        st.text_input("Ghi chú cho phiên tiếp theo:", key="du_toan_ghi_chu",
                      placeholder="VD: Tăng H_tru lên 8m...")

        import pandas as pd
        rows_ls = []
        for i, h in enumerate(reversed(history)):
            rows_ls.append({
                "Phiên": h.get("ghi_chu", f"#{len(history)-i}"),
                "Thời gian": h["timestamp"][:16].replace("T", " "),
                "Vùng miền": h.get("vung_mien", "—"),
                "Cấp đường": h.get("cap_duong", "—"),
                "Tổng đầu tư (tỷ)": f"{h['tong_dau_tu']/1e6:.3f}",
                "Suất đt (tr/m²)": f"{h['suat_dau_tu']:.1f}",
                "Hash params": h.get("beam_params_hash", "—"),
                "_idx": len(history) - 1 - i,
            })

        df_ls = pd.DataFrame(rows_ls).drop(columns=["_idx"])
        st.dataframe(df_ls, hide_index=True, use_container_width=True)

        # So sánh phiên
        if len(history) >= 2:
            st.subheader("So sánh giữa các phiên")
            col_ls1, col_ls2 = st.columns(2)
            idx_a = col_ls1.selectbox("Phiên A", range(len(history)),
                                       format_func=lambda i: history[i].get("ghi_chu", f"#{i+1}"))
            idx_b = col_ls2.selectbox("Phiên B", range(len(history)),
                                       format_func=lambda i: history[i].get("ghi_chu", f"#{i+1}"),
                                       index=min(1, len(history)-1))
            ha = history[idx_a]
            hb = history[idx_b]
            diff_ty = (ha["tong_dau_tu"] - hb["tong_dau_tu"]) / 1e6
            diff_suat = ha["suat_dau_tu"] - hb["suat_dau_tu"]
            st.markdown(
                f"| | **{ha.get('ghi_chu','A')}** | **{hb.get('ghi_chu','B')}** | Chênh lệch |\n"
                f"| --- | --- | --- | --- |\n"
                f"| Tổng ĐT (tỷ) | {ha['tong_dau_tu']/1e6:.3f} | {hb['tong_dau_tu']/1e6:.3f} | {diff_ty:+.3f} |\n"
                f"| Suất ĐT (tr/m²) | {ha['suat_dau_tu']:.1f} | {hb['suat_dau_tu']:.1f} | {diff_suat:+.1f} |"
            )

        # Nút khôi phục
        cols_ls = st.columns(len(history))
        for i, h in enumerate(history):
            if cols_ls[i % len(cols_ls)].button(
                f"Xem phiên {i+1}", key=f"ls_view_{i}"
            ):
                st.session_state["du_toan_result"] = h["du_toan"]
                st.rerun()
