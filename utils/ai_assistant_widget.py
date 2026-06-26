# -*- coding: utf-8 -*-
"""
utils/ai_assistant_widget.py — Widget AI nhỏ nhúng vào các trang module khác

Sử dụng:
    from utils.ai_assistant_widget import ai_assistant_widget
    ai_assistant_widget(context_hint="Bước 3 — Kết cấu nhịp")
"""

from __future__ import annotations

import os
import importlib.util
from pathlib import Path
from typing import Optional, Dict

import streamlit as st

_ROOT = Path(__file__).parent.parent


@st.cache_resource(show_spinner=False)
def _load_ai_mod():
    path = _ROOT / "15-Bridge_AI_Assistant.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("bridge_ai", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ai_assistant_widget(
    context_hint: str = "",
    session_context: Optional[Dict] = None,
    key_suffix: str = "",
):
    """
    Widget chat thu gọn — nhúng cuối mỗi trang module.

    Parameters
    ----------
    context_hint : str
        Gợi ý ngữ cảnh hiển thị trên widget (ví dụ: "Bước 3 — KCN").
    session_context : dict, optional
        Dữ liệu thiết kế hiện tại. Nếu None, widget tự đọc từ session_state.
    key_suffix : str
        Suffix để tránh xung đột key khi nhúng nhiều widget trên cùng trang.
    """
    ai_mod = _load_ai_mod()
    if not ai_mod:
        return

    widget_key = f"ai_widget_{key_suffix}"

    with st.expander("🤖 Hỏi AI về bước này", expanded=False):
        if not os.environ.get("CLAUDE_API_KEY"):
            st.caption(
                "💡 Chưa có Claude API Key. Vào trang **15 — AI Assistant** "
                "để cấu hình."
            )
            return

        if context_hint:
            st.caption(f"Ngữ cảnh: **{context_hint}**")

        q = st.text_input(
            "Câu hỏi nhanh:",
            placeholder="Ví dụ: Tỉ lệ L/H tối ưu cho Super-T nhịp 38m?",
            key=f"{widget_key}_input",
        )

        if q and st.button("Hỏi AI", key=f"{widget_key}_btn"):
            # Lấy context nếu không truyền vào
            if session_context is None:
                ctx = {}
                ss = st.session_state
                bps = ss.get("beam_params_final") or ss.get("beam_params", {})
                if bps:
                    ctx["loai_dam"] = bps.get("loai_dam", "")
                    ctx["L_nhip"]   = bps.get("L", 0)
                    ctx["H_dam"]    = bps.get("H", 0)
                if context_hint:
                    ctx["context_hint"] = context_hint
            else:
                ctx = session_context

            with st.spinner("AI đang trả lời..."):
                try:
                    text, usage = ai_mod.ask_bridge_assistant(
                        question=q,
                        session_context=ctx,
                        stream=False,
                        use_rag=True,
                    )
                    st.markdown(text)
                    cost = usage.get("cost_usd", 0)
                    if cost > 0:
                        st.caption(f"Chi phí API: ${cost:.4f}")
                except Exception as e:
                    st.error(f"Lỗi: {e}")
