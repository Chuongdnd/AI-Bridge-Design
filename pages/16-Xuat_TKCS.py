# -*- coding: utf-8 -*-
"""
pages/16-Xuat_TKCS.py — Giao diện xuất thuyết minh thiết kế cơ sở (TKCS)
Sinh file DOCX chuẩn ngành theo Nghị định 175/2024/NĐ-CP
"""

import io
import os
import json
import datetime
import importlib.util
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent


# ── Tải TKCSGenerator ────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _load_gen_module():
    path = ROOT / "16-TKCS_Generator.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("tkcs_gen", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Session state ─────────────────────────────────────────────────────────────

def _init():
    if "tkcs_versions" not in st.session_state:
        st.session_state.tkcs_versions = []
    if "tkcs_qc_result" not in st.session_state:
        st.session_state.tkcs_qc_result = None


# ── Kiểm tra dữ liệu đầu vào ─────────────────────────────────────────────────

PREREQS = [
    ("beam_params_final",  "Bước 3–4 — Thông số dầm (beam_params_final)",    True),
    ("kcn_result",         "Bước 5 — Kết cấu nhịp (kcn_result)",             True),
    ("pier_result",        "Bước 6 — Mố trụ (pier_result)",                  False),
    ("mong_coc_result",    "Bước 7 — Móng cọc (mong_coc_result)",            False),
]


def _check_prereqs() -> dict:
    result = {}
    for key, label, required in PREREQS:
        has = bool(st.session_state.get(key))
        result[key] = {"label": label, "has": has, "required": required}
    return result


def _render_prereqs(checks: dict) -> bool:
    """Hiển thị checklist điều kiện tiên quyết. Trả về True nếu đủ điều kiện bắt buộc."""
    st.subheader("📋 Kiểm tra dữ liệu đầu vào")
    all_required_ok = True

    for key, info in checks.items():
        icon = "✅" if info["has"] else ("❌" if info["required"] else "⚠️")
        suffix = " *(bắt buộc)*" if info["required"] else " *(tùy chọn)*"
        col1, col2 = st.columns([1, 8])
        with col1:
            st.markdown(icon)
        with col2:
            st.markdown(f"{info['label']}{suffix}")

        if info["required"] and not info["has"]:
            all_required_ok = False

    if not all_required_ok:
        st.warning(
            "⚠️ Chưa đủ dữ liệu bắt buộc. Vui lòng hoàn thành các bước thiết kế "
            "trước khi xuất thuyết minh. Bạn có thể dùng dữ liệu demo để kiểm tra."
        )

    return all_required_ok


# ── Dữ liệu demo ─────────────────────────────────────────────────────────────

def _load_demo_data():
    """Nạp dữ liệu mẫu vào session_state để test."""
    import datetime as dt
    st.session_state["beam_params_final"] = {
        "loai_dam": "Super-T", "L": 38_200, "H": 1_750, "B": 2_440,
        "S": 2_200, "n_dam": 6, "cong_nghe": "DUL căng trước",
        "mac_bt": "B50 (f'c = 50 MPa)",
    }
    st.session_state["kcn_result"] = {
        "tong_so_nhip": 1, "be_rong_cau": 12.0,
        "so_lan_xe": 2, "so_dam_tren_mat_cat": 6,
    }
    st.session_state["pier_result"] = {
        "loai_tru": "Trụ thân đặc BTCT", "H_tru": 6.5,
        "loai_mo": "Mố chữ U BTCT", "H_dap": 2.0,
        "vat_lieu_tru": "BTCT B30",
    }
    st.session_state["mong_coc_result"] = {
        "loai_coc": "Cọc khoan nhồi BTCT",
        "D_coc": 800, "L_coc": 35, "n_coc_be": 4, "Q_cho_phep": 1_800,
        "lop_tua_mui": "Lớp cát chặt N≥30",
    }
    # Chi phí: tính theo SUẤT ĐẦU TƯ từ design_data (bỏ du_toan_result demo).
    st.session_state["design_data"] = {
        "bc": 12.0, "geo_logic": {"L_cau": 38.2},
        "kcn_result": {"loai_dam": "Super-T", "chieu_dai": 38.2},
        "mong_result": {"loai_mong": "Cọc khoan nhồi"},
    }
    st.session_state["terrain_data"] = {
        "dia_hinh": "đồng bằng, tương đối bằng phẳng",
        "MNCN": "+1.80", "MNTN": "-0.50", "MNTT": "+1.20",
    }
    st.session_state["cap_cong_trinh"] = "III"
    st.success("✅ Đã nạp dữ liệu demo")
    st.rerun()


# ── Xuất file ────────────────────────────────────────────────────────────────

def _do_export(gen_mod, project_info: dict, cfg: dict) -> tuple:
    """
    Chạy TKCSGenerator và trả về (docx_bytes, zip_bytes, stats, qc).
    """
    gen = gen_mod.TKCSGenerator(
        session_data=dict(st.session_state),
        config=cfg,
        project_info=project_info,
    )

    progress_bar = st.progress(0, text="Đang khởi tạo...")

    def _cb(step, total, msg):
        pct = int(100 * step / max(total, 1))
        progress_bar.progress(pct, text=msg)

    docx_bytes = gen.generate(progress_callback=_cb)
    progress_bar.progress(100, text="Hoàn tất!")

    zip_bytes = None
    try:
        zip_bytes = gen.generate_zip()
    except Exception:
        pass

    stats = {
        "n_tables":  len(gen.num.tables),
        "n_figures": len(gen.num.figures),
        "size_kb":   len(docx_bytes) // 1024,
        "toc_items": len(gen.num.toc),
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    qc = gen.quality_check()
    return docx_bytes, zip_bytes, stats, qc


# ── Lịch sử phiên bản ────────────────────────────────────────────────────────

def _render_version_history():
    versions = st.session_state.get("tkcs_versions", [])
    if not versions:
        st.info("Chưa có phiên bản nào được xuất trong phiên làm việc này.")
        return

    st.subheader(f"📜 Lịch sử phiên bản ({len(versions)} bản)")

    for i, v in enumerate(reversed(versions)):
        with st.expander(
            f"v{v['version']}  —  {v['timestamp'][:16]}  —  "
            f"{v['project_name']}  |  {v['size_kb']} KB  —  "
            f"Chất lượng: {v['quality_score']}/100",
            expanded=(i == 0),
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"📊 Bảng: {v['n_tables']} | Hình: {v['n_figures']}")
                st.write(f"📝 Mục lục: {v['toc_items']} mục")
                if v.get("note"):
                    st.write(f"📌 Ghi chú: {v['note']}")
            with col2:
                if v.get("docx_bytes"):
                    st.download_button(
                        f"📥 Tải DOCX (v{v['version']})",
                        data=v["docx_bytes"],
                        file_name=f"TKCS_v{v['version']}_{v['timestamp'][:10]}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_v{v['version']}_{i}",
                    )


# ── Đánh giá chất lượng ──────────────────────────────────────────────────────

def _render_quality(qc: dict):
    total = qc.get("total", 0)
    grade = qc.get("grade", "—")
    scores = qc.get("scores", {})

    color = "#22c55e" if total >= 90 else "#f59e0b" if total >= 75 else "#ef4444"
    st.markdown(
        f"<div style='background:{color}22;border-left:4px solid {color};"
        f"padding:10px;border-radius:6px'>"
        f"<b>Điểm chất lượng thuyết minh: {total}/100 — {grade}</b></div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    labels = {
        "day_du":       ("Tính đầy đủ", 40),
        "nhat_quan":    ("Nhất quán", 25),
        "trich_dan":    ("Trích dẫn TC", 20),
        "thong_tin_da": ("Thông tin DA", 15),
    }
    for col, (key, (label, max_score)) in zip(
        [col1, col2, col3, col4], labels.items()
    ):
        with col:
            sc = scores.get(key, 0)
            st.metric(f"{label} (/{max_score})", sc)

    issues = [x for x in qc.get("issues", []) if x]
    if issues:
        st.warning("⚠️ Cần cải thiện:\n" + "\n".join(f"- {x}" for x in issues))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Xuất thuyết minh TKCS",
        page_icon="📄",
        layout="wide",
    )

    _init()
    gen_mod = _load_gen_module()

    st.title("📄 Xuất thuyết minh thiết kế cơ sở (TKCS)")
    st.caption(
        "Sinh file DOCX chuẩn ngành xây dựng Việt Nam · "
        "Tuân thủ Nghị định 175/2024/NĐ-CP · 12 chương đầy đủ"
    )

    if not gen_mod:
        st.error("❌ Không tìm thấy `16-TKCS_Generator.py`")
        st.stop()

    # ── Tabs chính ────────────────────────────────────────────────────────────
    tab_xuat, tab_lich_su, tab_huong_dan = st.tabs([
        "📝 Xuất thuyết minh", "📜 Lịch sử phiên bản", "ℹ️ Hướng dẫn"
    ])

    # ════════════════════════════════════════════════════════════════════════
    # TAB 1: XUẤT
    # ════════════════════════════════════════════════════════════════════════
    with tab_xuat:

        # ── Kiểm tra điều kiện ────────────────────────────────────────────
        checks = _check_prereqs()
        all_ok = _render_prereqs(checks)

        if not all_ok:
            col_demo, _ = st.columns([2, 6])
            with col_demo:
                if st.button("🔧 Nạp dữ liệu demo", type="primary"):
                    _load_demo_data()
            st.divider()

        # ── Cấu hình xuất ─────────────────────────────────────────────────
        with st.expander("⚙️ Cấu hình xuất", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Chọn chương cần xuất:**")
                chapter_labels = {
                    1:  "Chương 1: Thông tin chung",
                    2:  "Chương 2: Cơ sở pháp lý",
                    3:  "Chương 3: Điều kiện tự nhiên",
                    4:  "Chương 4: Quy mô và tải trọng",
                    5:  "Chương 5: Kết cấu nhịp",
                    6:  "Chương 6: Mố và trụ",
                    7:  "Chương 7: Móng cọc",
                    8:  "Chương 8: Mặt cầu và phụ trợ",
                    9:  "Chương 9: Dự toán sơ bộ",
                    10: "Chương 10: Tác động môi trường",
                    11: "Chương 11: Tổ chức thi công",
                    12: "Chương 12: Kết luận và kiến nghị",
                }
                selected_chs = []
                col_a, col_b = st.columns(2)
                for i, (ch, label) in enumerate(chapter_labels.items()):
                    with (col_a if i < 6 else col_b):
                        if st.checkbox(label, value=True, key=f"ch_{ch}"):
                            selected_chs.append(ch)

            with col2:
                detail_level = st.radio(
                    "Mức độ chi tiết:",
                    ["Sơ bộ", "Trung bình (khuyến nghị)", "Đầy đủ"],
                    index=1,
                )
                include_figures = st.checkbox("Chèn biểu đồ (kaleido)", value=True)
                include_appendix = st.checkbox("Xuất thêm file ZIP (kèm phụ lục)", value=True)
                version_note = st.text_input(
                    "Ghi chú phiên bản:",
                    placeholder="Ví dụ: Bản trình chủ đầu tư lần 1",
                )

        # ── Thông tin dự án ───────────────────────────────────────────────
        with st.expander("🏗️ Thông tin dự án (trang bìa)", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                ten_du_an = st.text_input(
                    "Tên đầy đủ dự án / cầu *",
                    value=st.session_state.get("_pi_ten_du_an",
                          "Cầu Kênh Xáng Thị Xã ABC"),
                    key="pi_ten_du_an",
                )
                dia_diem = st.text_input(
                    "Địa điểm xây dựng *",
                    value=st.session_state.get("_pi_dia_diem", ""),
                    key="pi_dia_diem",
                )
                chu_dau_tu = st.text_input(
                    "Chủ đầu tư",
                    value=st.session_state.get("_pi_chu_dau_tu", "UBND huyện / tỉnh"),
                    key="pi_chu_dau_tu",
                )
                tu_van = st.text_input(
                    "Đơn vị tư vấn",
                    value="AI-Bridge-Design System — Trường ĐH Giao thông VT TP.HCM",
                    key="pi_tu_van",
                )
            with col2:
                hoc_vien = st.text_input(
                    "Học viên / Người lập",
                    value=st.session_state.get("_pi_hoc_vien", ""),
                    key="pi_hoc_vien",
                )
                gv = st.text_input(
                    "Giảng viên hướng dẫn",
                    value=st.session_state.get("_pi_gv", "TS. Nguyễn Văn Hiển"),
                    key="pi_gv",
                )
                ngay_lap = st.date_input(
                    "Ngày lập thuyết minh",
                    value=__import__("datetime").date.today(),
                    key="pi_ngay_lap",
                )
                diem_dau = st.text_input("Điểm đầu tuyến", key="pi_diem_dau")
                diem_cuoi = st.text_input("Điểm cuối tuyến", key="pi_diem_cuoi")

        # ── Nút xuất ─────────────────────────────────────────────────────
        st.divider()
        col_btn, col_info = st.columns([2, 6])
        with col_btn:
            export_btn = st.button(
                "🚀 Xuất thuyết minh TKCS",
                type="primary",
                use_container_width=True,
                disabled=(not selected_chs),
            )

        if not selected_chs:
            st.warning("Hãy chọn ít nhất một chương để xuất.")

        if export_btn:
            project_info = {
                "ten_du_an":    ten_du_an,
                "dia_diem":     dia_diem,
                "chu_dau_tu":   chu_dau_tu,
                "tu_van":       tu_van,
                "hoc_vien":     hoc_vien,
                "gv_huong_dan": gv,
                "ngay_lap":     str(ngay_lap),
                "diem_dau":     diem_dau,
                "diem_cuoi":    diem_cuoi,
            }
            cfg = {
                "selected_chapters": selected_chs,
                "detail_level":      detail_level,
                "include_figures":   include_figures,
            }

            with st.spinner("Đang sinh thuyết minh..."):
                try:
                    docx_bytes, zip_bytes, stats, qc = _do_export(
                        gen_mod, project_info, cfg
                    )
                    st.session_state["_last_docx"]    = docx_bytes
                    st.session_state["_last_zip"]     = zip_bytes
                    st.session_state["_last_stats"]   = stats
                    st.session_state["tkcs_qc_result"] = qc

                    # Lưu vào lịch sử
                    versions = st.session_state.setdefault("tkcs_versions", [])
                    v_num    = len(versions) + 1
                    versions.append({
                        "version":       v_num,
                        "timestamp":     stats["timestamp"],
                        "project_name":  ten_du_an[:40],
                        "size_kb":       stats["size_kb"],
                        "n_tables":      stats["n_tables"],
                        "n_figures":     stats["n_figures"],
                        "toc_items":     stats["toc_items"],
                        "quality_score": qc.get("total", 0),
                        "note":          version_note,
                        "docx_bytes":    docx_bytes,
                    })
                    st.success(
                        f"✅ Thuyết minh xuất thành công! "
                        f"{stats['size_kb']} KB · {stats['n_tables']} bảng · "
                        f"{stats['n_figures']} hình · {stats['toc_items']} mục"
                    )
                except Exception as e:
                    st.error(f"❌ Lỗi khi xuất: {e}")
                    import traceback
                    st.code(traceback.format_exc(), language="python")

        # ── Kết quả ──────────────────────────────────────────────────────
        docx_bytes = st.session_state.get("_last_docx")
        if docx_bytes:
            st.divider()
            st.subheader("📥 Tải xuống")

            stats = st.session_state.get("_last_stats", {})
            qc    = st.session_state.get("tkcs_qc_result", {})

            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1: st.metric("Kích thước", f"{stats.get('size_kb',0)} KB")
            with col_m2: st.metric("Số bảng",    stats.get("n_tables", 0))
            with col_m3: st.metric("Số hình",    stats.get("n_figures", 0))
            with col_m4: st.metric("Chất lượng", f"{qc.get('total',0)}/100")

            # Đánh giá chất lượng
            if qc:
                _render_quality(qc)

            st.divider()
            col_dl1, col_dl2, col_dl3 = st.columns(3)

            ts_str = stats.get("timestamp","")[:10].replace("-","")
            name   = (ten_du_an if "ten_du_an" in dir() else "TKCS").replace(" ","_")[:30]

            with col_dl1:
                st.download_button(
                    "📄 Tải DOCX",
                    data=docx_bytes,
                    file_name=f"TM_TKCS_{name}_{ts_str}.docx",
                    mime="application/vnd.openxmlformats-officedocument"
                         ".wordprocessingml.document",
                    use_container_width=True,
                    type="primary",
                )

            zip_bytes = st.session_state.get("_last_zip")
            if zip_bytes:
                with col_dl2:
                    st.download_button(
                        "📦 Tải ZIP (kèm phụ lục)",
                        data=zip_bytes,
                        file_name=f"HoSo_TKCS_{name}_{ts_str}.zip",
                        mime="application/zip",
                        use_container_width=True,
                    )

            with col_dl3:
                if st.button("👁️ Xem cấu trúc", use_container_width=True):
                    st.session_state["_show_toc"] = not st.session_state.get("_show_toc", False)

            # Xem trước cấu trúc mục lục
            if st.session_state.get("_show_toc"):
                st.markdown("### 📋 Cấu trúc thuyết minh")
                st.caption("Ghi chú: Mở file Word và nhấn Ctrl+A → F9 để cập nhật mục lục tự động.")

                ch_titles = [
                    "Thông tin chung về dự án",
                    "Cơ sở pháp lý và tiêu chuẩn thiết kế",
                    "Điều kiện tự nhiên khu vực xây dựng",
                    "Quy mô và tải trọng thiết kế",
                    "Giải pháp thiết kế kết cấu nhịp",
                    "Giải pháp thiết kế mố và trụ cầu",
                    "Giải pháp thiết kế móng",
                    "Mặt cầu và các bộ phận phụ trợ",
                    "Dự toán sơ bộ tổng mức đầu tư",
                    "Đánh giá tác động môi trường sơ bộ",
                    "Phương án tổ chức thi công sơ bộ",
                    "Kết luận và kiến nghị",
                ]
                for i, title in enumerate(ch_titles, 1):
                    if i in selected_chs:
                        st.markdown(f"**Chương {i}: {title}** ✓")
                    else:
                        st.markdown(f"~~Chương {i}: {title}~~ *(bỏ qua)*")

    # ════════════════════════════════════════════════════════════════════════
    # TAB 2: LỊCH SỬ
    # ════════════════════════════════════════════════════════════════════════
    with tab_lich_su:
        _render_version_history()

        if st.session_state.get("tkcs_versions"):
            st.divider()
            if st.button("🗑️ Xóa toàn bộ lịch sử"):
                st.session_state.tkcs_versions = []
                st.rerun()

    # ════════════════════════════════════════════════════════════════════════
    # TAB 3: HƯỚNG DẪN
    # ════════════════════════════════════════════════════════════════════════
    with tab_huong_dan:
        st.markdown("""
### 📖 Hướng dẫn sử dụng

#### Quy trình xuất thuyết minh

1. **Hoàn thành các bước thiết kế** (Bước 3–9) hoặc nạp dữ liệu demo để thử
2. **Nhập thông tin dự án** — tên cầu, địa điểm, chủ đầu tư, học viên...
3. **Chọn chương** cần xuất (mặc định tất cả 12 chương)
4. **Nhấn "Xuất thuyết minh TKCS"** — quá trình mất 5–30 giây tùy dữ liệu
5. **Tải xuống** file DOCX hoặc ZIP (kèm phụ lục)

---

#### Sau khi tải về

Mở file trong Microsoft Word:
- **Ctrl+A** → **F9** để cập nhật mục lục và danh mục bảng/hình tự động
- Kiểm tra và chỉnh sửa nội dung theo thực tế dự án
- In ấn với khổ A4, lề trái 3cm, lề phải 2cm để đóng quyển

---

#### Cấu trúc thuyết minh (Nghị định 175/2024/NĐ-CP, Điều 20)

| Chương | Nội dung | Yêu cầu |
|--------|----------|---------|
| 1 | Thông tin chung dự án | Bắt buộc |
| 2 | Cơ sở pháp lý và tiêu chuẩn | Bắt buộc |
| 3 | Điều kiện tự nhiên | Bắt buộc |
| 4 | Quy mô và tải trọng | Bắt buộc |
| 5 | Kết cấu nhịp | Bắt buộc |
| 6 | Mố và trụ cầu | Bắt buộc |
| 7 | Móng cọc | Bắt buộc |
| 8 | Mặt cầu và phụ trợ | Bắt buộc |
| 9 | Dự toán sơ bộ | Bắt buộc |
| 10 | Tác động môi trường | Sơ bộ |
| 11 | Tổ chức thi công | Sơ bộ |
| 12 | Kết luận và kiến nghị | Bắt buộc |

---

#### Lưu ý kỹ thuật

- File DOCX sử dụng font **Times New Roman** (cỡ 13pt nội dung, 14pt tiêu đề chương)
- Khổ giấy A4, lề trái 3cm (đóng quyển), lề phải 2cm, lề trên/dưới 2.5cm
- Biểu đồ được chuyển sang PNG thông qua **kaleido** — cần cài: `pip install kaleido`
- Mỗi lần xuất được lưu tự động vào **Lịch sử phiên bản** trong tab bên cạnh

---

#### Hạn chế hiện tại

- Không hỗ trợ xuất bản vẽ DXF (cần chuyển sang PDF riêng bằng AutoCAD)
- Kiểm tra chính tả tiếng Việt: cần kiểm tra thủ công trong Word
- File ZIP chỉ bao gồm DOCX chính + danh mục tiêu chuẩn (phụ lục bản vẽ thêm sau)
        """)


if __name__ == "__main__":
    main()
