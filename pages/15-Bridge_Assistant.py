# -*- coding: utf-8 -*-
"""
pages/15-Bridge_Assistant.py — AI Assistant thiết kế cầu
Chat UI với RAG + Claude API streaming
"""

import os
import time
import json
import importlib.util
from pathlib import Path

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Tải module helper (tên có dấu gạch ngang → dùng importlib)
# ─────────────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent


def _load_module(name: str, filename: str):
    path = ROOT / filename
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@st.cache_resource(show_spinner=False)
def _get_ai_module():
    return _load_module("bridge_ai", "15-Bridge_AI_Assistant.py")


@st.cache_resource(show_spinner=False)
def _get_rag_module():
    return _load_module("rag_indexer", "14-RAG_Indexer.py")


# ─────────────────────────────────────────────────────────────────────────────
# Session state khởi tạo
# ─────────────────────────────────────────────────────────────────────────────

def _init_state():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []          # [{"role": ..., "content": ...}]
    if "conversations" not in st.session_state:
        st.session_state.conversations = {}         # {name: [messages]}
    if "current_conv" not in st.session_state:
        st.session_state.current_conv = "Cuộc hội thoại 1"
    if "usage_stats" not in st.session_state:
        st.session_state.usage_stats = {
            "total_cost_usd": 0.0,
            "total_in_tokens": 0,
            "total_out_tokens": 0,
            "n_calls": 0,
        }
    if "rag_ready" not in st.session_state:
        st.session_state.rag_ready = False
    if "feedback_store" not in st.session_state:
        st.session_state.feedback_store = {}


# ─────────────────────────────────────────────────────────────────────────────
# Lấy session_context từ các module đã chạy
# ─────────────────────────────────────────────────────────────────────────────

def _collect_session_context() -> dict:
    ctx = {}
    ss  = st.session_state

    for key in ("loai_cong_trinh", "cap_duong", "cap_ky_thuat"):
        if key in ss:
            ctx[key] = ss[key]

    bps = ss.get("beam_params_final") or ss.get("beam_params", {})
    if bps:
        ctx["loai_dam"] = bps.get("loai_dam", "")
        ctx["L_nhip"]   = bps.get("L", 0)
        ctx["H_dam"]    = bps.get("H", 0)
        ctx["n_dam"]    = bps.get("n_dam", 0)

    kcn = ss.get("kcn_result", {})
    if kcn:
        ctx["n_nhip"] = kcn.get("tong_so_nhip", 0)
        ctx["bc"]     = kcn.get("be_rong_cau", 0)

    du_toan = ss.get("du_toan_result", {})
    if du_toan:
        ph = du_toan.get("phan_tich", {})
        th = du_toan.get("tong_hop", {})
        ctx["suat_dau_tu"] = ph.get("suat_dau_tu_trieu_m2", 0)
        ctx["tong_dau_tu"] = th.get("tong_dau_tu", 0)

    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# Hiển thị tin nhắn trong chat
# ─────────────────────────────────────────────────────────────────────────────

def _render_message(role: str, content: str, msg_idx: int, sources=None):
    with st.chat_message(role):
        st.markdown(content)

        if role == "assistant":
            col1, col2, col3, col4 = st.columns([1, 1, 1, 6])
            fb_key = f"fb_{msg_idx}"
            current_fb = st.session_state.feedback_store.get(fb_key)

            with col1:
                if st.button("👍", key=f"up_{msg_idx}", help="Hữu ích",
                             type="primary" if current_fb == "up" else "secondary"):
                    st.session_state.feedback_store[fb_key] = "up"
            with col2:
                if st.button("👎", key=f"dn_{msg_idx}", help="Chưa hữu ích",
                             type="primary" if current_fb == "dn" else "secondary"):
                    st.session_state.feedback_store[fb_key] = "dn"
            with col3:
                if st.button("📋", key=f"cp_{msg_idx}", help="Sao chép"):
                    st.toast("Nội dung đã được sao chép!", icon="✅")

            if sources:
                with st.expander(f"📚 Nguồn tham chiếu ({len(sources)} tài liệu)", expanded=False):
                    for i, src in enumerate(sources, 1):
                        score_pct = int(src.get("score", 0) * 100)
                        st.markdown(
                            f"**[{i}]** `{src['filename']}` "
                            f"({src.get('source_type','')}) — "
                            f"độ liên quan: **{score_pct}%**"
                        )
                        st.caption(src.get("text", "")[:200] + "...")


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

def _render_sidebar():
    ai_mod  = _get_ai_module()
    rag_mod = _get_rag_module()

    with st.sidebar:
        st.markdown("## 🤖 AI Bridge Assistant")

        # Cảnh báo bảo mật
        st.info(
            "⚠️ **Lưu ý bảo mật**\n\n"
            "Các câu hỏi được xử lý bởi **Claude API** (Anthropic) — "
            "một dịch vụ bên ngoài. Không nhập thông tin nhạy cảm "
            "(tên dự án, địa danh cụ thể, số hợp đồng, thông tin chủ đầu tư).",
            icon="🔒",
        )

        # API key
        st.markdown("### ⚙️ Cấu hình API")
        api_key = st.text_input(
            "Claude API Key",
            value=os.environ.get("CLAUDE_API_KEY", ""),
            type="password",
            help="Lấy API key tại console.anthropic.com",
        )
        if api_key:
            os.environ["CLAUDE_API_KEY"] = api_key
            if ai_mod:
                ai_mod.CLAUDE_API_KEY = api_key

        # Model
        model = st.selectbox(
            "Model",
            ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-8"],
            index=0,
        )

        # RAG
        st.markdown("### 📚 Knowledge Base")
        if rag_mod:
            stats = rag_mod.get_index_stats()
            if stats.get("status") == "ready":
                st.success(
                    f"Index sẵn sàng: **{stats['n_chunks']}** chunks "
                    f"từ **{stats['n_files']}** tài liệu"
                )
                st.session_state.rag_ready = True
            elif stats.get("status") == "empty":
                st.warning("Index chưa được xây dựng.")
                if st.button("🔧 Xây dựng Index", type="primary"):
                    with st.spinner("Đang indexing tài liệu..."):
                        try:
                            result = rag_mod.rebuild_index(force=True)
                            st.success(
                                f"Hoàn tất: {result['new_chunks']} chunks mới từ "
                                f"{result['n_docs']} tài liệu"
                            )
                            st.session_state.rag_ready = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi: {e}")
            else:
                st.error(f"Lỗi index: {stats.get('error','')}")
                if st.button("🔄 Thử lại"):
                    st.rerun()
        else:
            st.error("Không tìm thấy 14-RAG_Indexer.py")

        if st.button("♻️ Rebuild Index"):
            with st.spinner("Đang xây dựng lại index..."):
                try:
                    result = rag_mod.rebuild_index(force=True)
                    st.success(f"Xong: {result.get('n_chunks',0)} chunks")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        # Quản lý hội thoại
        st.markdown("### 💬 Hội thoại")
        conv_name = st.text_input(
            "Tên hội thoại",
            value=st.session_state.current_conv,
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Lưu"):
                st.session_state.conversations[conv_name] = list(
                    st.session_state.chat_history
                )
                st.toast(f"Đã lưu '{conv_name}'")
        with col2:
            if st.button("🗑️ Xóa"):
                st.session_state.chat_history = []
                st.toast("Đã xóa hội thoại hiện tại")
                st.rerun()

        saved = list(st.session_state.conversations.keys())
        if saved:
            selected = st.selectbox("📂 Hội thoại đã lưu", [""] + saved)
            if selected and st.button("📂 Mở"):
                st.session_state.chat_history = list(
                    st.session_state.conversations[selected]
                )
                st.session_state.current_conv = selected
                st.rerun()

        # Thống kê chi phí
        st.markdown("### 📊 Sử dụng API")
        us = st.session_state.usage_stats
        st.metric("Tổng chi phí", f"${us['total_cost_usd']:.4f}")
        st.metric("Số lần gọi",   str(us["n_calls"]))
        st.metric("Tokens vào",   f"{us['total_in_tokens']:,}")
        st.metric("Tokens ra",    f"{us['total_out_tokens']:,}")

        # Export
        st.markdown("### 📤 Xuất dữ liệu")
        if st.button("📥 Xuất JSON"):
            export = {
                "conversation": st.session_state.chat_history,
                "usage":        st.session_state.usage_stats,
            }
            st.download_button(
                "Tải file JSON",
                data=json.dumps(export, ensure_ascii=False, indent=2),
                file_name="bridge_ai_chat.json",
                mime="application/json",
            )

    return model


# ─────────────────────────────────────────────────────────────────────────────
# Câu hỏi gợi ý
# ─────────────────────────────────────────────────────────────────────────────

SUGGESTED_QUESTIONS = [
    "TCVN 11823 quy định tỉ lệ L/H tối đa cho dầm Super-T là bao nhiêu?",
    "Đường kính tối thiểu cọc khoan nhồi trong cầu đường là bao nhiêu?",
    "Suất đầu tư hiện tại của tôi có hợp lý không so với cầu cấp III?",
    "Làm thế nào để giảm chi phí kết cấu nhịp xuống thêm 15%?",
    "Tĩnh không thông thuyền tối thiểu theo TCVN là bao nhiêu?",
    "Hướng dẫn kiểm tra ổn định ngang cho dầm Super-T nhịp dài.",
]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="AI Bridge Assistant",
        page_icon="🌉",
        layout="wide",
    )

    _init_state()
    model = _render_sidebar()

    st.title("🌉 AI Bridge Assistant")
    st.caption(
        "Trợ lý AI chuyên gia thiết kế cầu · "
        "Powered by Claude API + RAG (Knowledge Base TCVN)"
    )

    ai_mod = _get_ai_module()
    if not ai_mod:
        st.error("❌ Không tìm thấy `15-Bridge_AI_Assistant.py`")
        st.stop()

    # ── Tab: Chat | Compliance Check | Ngữ cảnh dự án ──
    tab_chat, tab_compliance, tab_context = st.tabs([
        "💬 Hội thoại", "✅ Kiểm tra tiêu chuẩn", "📋 Ngữ cảnh dự án"
    ])

    # ─── TAB 1: CHAT ────────────────────────────────────────────────────────
    with tab_chat:
        # Hiển thị câu hỏi gợi ý nếu chưa có lịch sử
        if not st.session_state.chat_history:
            st.markdown("#### 💡 Câu hỏi gợi ý")
            cols = st.columns(3)
            for i, q in enumerate(SUGGESTED_QUESTIONS):
                with cols[i % 3]:
                    if st.button(q, key=f"sug_{i}", use_container_width=True):
                        st.session_state._pending_question = q

        # Hiển thị lịch sử chat
        sources_store = st.session_state.get("_sources_store", {})
        for idx, msg in enumerate(st.session_state.chat_history):
            sources = sources_store.get(idx)
            _render_message(msg["role"], msg["content"], idx, sources)

        # Chat input
        user_input = st.chat_input("Đặt câu hỏi về thiết kế cầu...")

        # Xử lý pending question (từ nút gợi ý)
        if hasattr(st.session_state, "_pending_question"):
            user_input = st.session_state._pending_question
            del st.session_state._pending_question

        if user_input:
            if not os.environ.get("CLAUDE_API_KEY"):
                st.error("⚠️ Chưa nhập Claude API Key trong sidebar.")
                st.stop()

            # Phân loại câu hỏi
            q_type = ai_mod.classify_question(user_input)
            type_labels = {
                "standard":       "📖 Tiêu chuẩn",
                "session_result": "📊 Kết quả tính toán",
                "improvement":    "💡 Đề xuất cải tiến",
                "general":        "💬 Chung",
            }
            st.caption(f"Phân loại: {type_labels.get(q_type, q_type)}")

            # Lưu user message
            st.session_state.chat_history.append({
                "role": "user", "content": user_input
            })

            user_idx = len(st.session_state.chat_history) - 1
            _render_message("user", user_input, user_idx)

            # Gọi AI
            session_ctx = _collect_session_context()
            history_for_api = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.chat_history[:-1]  # Bỏ câu vừa thêm
            ]

            with st.chat_message("assistant"):
                placeholder = st.empty()
                full_response = ""
                sources_received = []

                try:
                    gen = ai_mod.ask_bridge_assistant(
                        question=user_input,
                        session_context=session_ctx,
                        chat_history=history_for_api,
                        stream=True,
                        model=model,
                        use_rag=st.session_state.rag_ready,
                    )

                    # Stream text
                    for token in gen:
                        full_response += token
                        placeholder.markdown(full_response + "▌")
                    placeholder.markdown(full_response)

                    # Lấy sources sau khi stream xong
                    sources_received = getattr(gen, "sources", [])
                    usage = getattr(gen, "usage", {})

                except Exception as e:
                    full_response = f"❌ Lỗi: {e}\n\nVui lòng kiểm tra API key và kết nối mạng."
                    placeholder.markdown(full_response)
                    usage = {}

            # Lưu assistant message
            st.session_state.chat_history.append({
                "role": "assistant", "content": full_response
            })
            asst_idx = len(st.session_state.chat_history) - 1

            # Lưu sources
            if "_sources_store" not in st.session_state:
                st.session_state._sources_store = {}
            st.session_state._sources_store[asst_idx] = sources_received

            # Cập nhật usage stats
            us = st.session_state.usage_stats
            us["n_calls"]          += 1
            us["total_cost_usd"]   += usage.get("cost_usd", 0)
            us["total_in_tokens"]  += usage.get("input_tokens", 0)
            us["total_out_tokens"] += usage.get("output_tokens", 0)

            # Hiển thị sources dưới tin nhắn vừa xong
            if sources_received:
                with st.expander(f"📚 Nguồn tham chiếu ({len(sources_received)} tài liệu)"):
                    for i, src in enumerate(sources_received, 1):
                        score_pct = int(src.get("score", 0) * 100)
                        st.markdown(
                            f"**[{i}]** `{src['filename']}` "
                            f"({src.get('source_type','')}) — "
                            f"độ liên quan: **{score_pct}%**"
                        )
                        st.caption(src.get("text", "")[:200] + "...")

            st.rerun()

    # ─── TAB 2: COMPLIANCE CHECK ────────────────────────────────────────────
    with tab_compliance:
        st.subheader("✅ Kiểm tra sự phù hợp với tiêu chuẩn TCVN")

        col1, col2 = st.columns(2)
        with col1:
            loai_dam = st.selectbox(
                "Loại dầm",
                ["Super-T", "Dầm I", "T ngược", "Dầm bản rỗng"],
            )
            L_nhip = st.number_input("Nhịp L (m)", 5.0, 100.0, 38.2, 0.5)
            H_dam  = st.number_input("Chiều cao dầm H (mm)", 500, 5000, 1750, 50)
        with col2:
            D_coc  = st.number_input("Đường kính cọc D (mm, 0=bỏ qua)", 0, 3000, 800, 100)
            n_nhip = st.number_input("Số nhịp", 1, 20, 1)
            bc     = st.number_input("Bề rộng cầu (m)", 4.0, 30.0, 12.0, 0.5)

        if st.button("🔍 Kiểm tra", type="primary"):
            params = {
                "loai_dam": loai_dam,
                "L_nhip":   L_nhip,
                "H_dam":    H_dam,
                "D_coc":    D_coc,
                "n_nhip":   n_nhip,
                "bc":       bc,
            }
            verdict, details = ai_mod.check_compliance(params)

            color = {"OK": "success", "CẢNH BÁO": "warning", "CẦN XEM XÉT": "error"}.get(verdict, "info")
            getattr(st, color)(f"**Kết quả: {verdict}**")

            if details["ok"]:
                st.success("✅ Đạt yêu cầu:\n" + "\n".join(f"- {x}" for x in details["ok"]))
            if details["warnings"]:
                st.warning("⚠️ Cảnh báo:\n" + "\n".join(f"- {x}" for x in details["warnings"]))
            if details["issues"]:
                st.error("❌ Vấn đề cần xem xét:\n" + "\n".join(f"- {x}" for x in details["issues"]))

            # Hỏi AI thêm nếu có vấn đề
            if (details["issues"] or details["warnings"]) and os.environ.get("CLAUDE_API_KEY"):
                if st.button("💡 Nhận tư vấn cải tiến từ AI"):
                    prompt = (
                        f"Tôi đang thiết kế cầu với {loai_dam}, L={L_nhip}m, H={H_dam}mm. "
                        f"Kiểm tra tiêu chuẩn cho thấy: {details}. "
                        f"Hãy đề xuất cách cải thiện thiết kế."
                    )
                    text, usage = ai_mod.ask_bridge_assistant(
                        question=prompt,
                        session_context=_collect_session_context(),
                        stream=False,
                        model=model,
                    )
                    st.markdown("### 💡 Tư vấn AI")
                    st.markdown(text)

    # ─── TAB 3: NGỮ CẢNH DỰ ÁN ─────────────────────────────────────────────
    with tab_context:
        st.subheader("📋 Ngữ cảnh dự án được truyền vào AI")
        ctx = _collect_session_context()
        if ctx:
            st.json(ctx)
            st.caption("Dữ liệu này được tự động lấy từ các bước thiết kế đã hoàn thành.")
        else:
            st.info(
                "Chưa có dữ liệu từ các bước thiết kế trước. "
                "Hoàn thiện Bước 1–5 để AI có thêm ngữ cảnh về dự án của bạn."
            )

        st.markdown("---")
        st.markdown("#### 📌 Widget AI nhanh")
        st.caption("Đặt câu hỏi nhanh mà không cần chuyển tab hội thoại:")
        quick_q = st.text_input("Câu hỏi nhanh:")
        if quick_q and st.button("Hỏi", key="quick_ask"):
            if not os.environ.get("CLAUDE_API_KEY"):
                st.error("Chưa có API key")
            else:
                with st.spinner("Đang hỏi AI..."):
                    text, _ = ai_mod.ask_bridge_assistant(
                        question=quick_q,
                        session_context=ctx,
                        stream=False,
                        model=model,
                    )
                st.markdown(text)


if __name__ == "__main__":
    main()
