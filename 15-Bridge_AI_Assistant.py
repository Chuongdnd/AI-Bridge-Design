# -*- coding: utf-8 -*-
"""
15-Bridge_AI_Assistant.py — AI Assistant cho thiết kế cầu
RAG pipeline + Claude API streaming + caching + cost tracking
"""

from __future__ import annotations

import os
import re
import json
import time
import hashlib
import logging
from pathlib import Path
from typing import Generator, List, Dict, Optional, Tuple

logger = logging.getLogger("Bridge_AI")

# ─────────────────────────────────────────────────────────────────────────────
# Load .env (CLAUDE_API_KEY)
# ─────────────────────────────────────────────────────────────────────────────

def _load_env():
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
DEFAULT_MODEL  = "claude-sonnet-4-6"

# ─────────────────────────────────────────────────────────────────────────────
# Giá token Claude (USD / 1M tokens — dùng để ước tính chi phí)
# ─────────────────────────────────────────────────────────────────────────────

PRICE_INPUT  = 3.0   # USD per 1M input tokens (Sonnet)
PRICE_OUTPUT = 15.0  # USD per 1M output tokens

# ─────────────────────────────────────────────────────────────────────────────
# System prompt chuyên gia thiết kế cầu
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Bạn là trợ lý AI chuyên gia về thiết kế cầu tại Việt Nam, tích hợp trong phần mềm AI-Bridge-Design.

NHIỆM VỤ CHÍNH:
1. Giải thích các tiêu chuẩn kỹ thuật cầu (TCVN 11823:2017, TCVN 10304:2014, v.v.)
2. Tư vấn lựa chọn kết cấu nhịp (Super-T, Dầm I, T ngược, Dầm bản rỗng)
3. Giải thích kết quả tính toán từ các module trong phần mềm
4. Đề xuất cải tiến thiết kế dựa trên kết quả đã có
5. Kiểm tra sự phù hợp với tiêu chuẩn và pháp quy

NGUYÊN TẮC TRẢ LỜI:
- Trả lời bằng tiếng Việt chuyên ngành cầu đường
- Trích dẫn cụ thể điều khoản tiêu chuẩn khi có thể (TCVN X:YYYY Điều Y.Z)
- Phân biệt rõ thông tin từ tài liệu tham chiếu vs. ý kiến chuyên gia
- Với câu hỏi định lượng: nêu công thức, thay số, kết quả rõ ràng
- Giới hạn 600 từ trừ khi cần phân tích chi tiết
- Kết thúc bằng câu hỏi gợi mở để người dùng có thể đào sâu thêm

GIỚI HẠN:
- Không đưa ra quyết định thiết kế cuối cùng thay kỹ sư
- Luôn khuyến nghị kiểm tra lại với kỹ sư có chứng chỉ hành nghề
- Không tạo ra số liệu không có trong tài liệu tham chiếu

NGỮ CẢNH TÀI LIỆU:
{context}

NGỮ CẢNH DỰ ÁN HIỆN TẠI (từ phần mềm):
{session_context}
"""

# ─────────────────────────────────────────────────────────────────────────────
# Phân loại câu hỏi
# ─────────────────────────────────────────────────────────────────────────────

_STANDARD_KEYWORDS = [
    "tcvn", "qcvn", "tiêu chuẩn", "điều khoản", "quy định", "bắt buộc",
    "nghị định", "thông tư", "quy chuẩn", "pháp lý", "thẩm định",
    "hl-93", "tải trọng", "tĩnh không", "xói lở",
]
_RESULT_KEYWORDS = [
    "kết quả", "tính toán", "module", "bước", "nhịp", "dầm", "cọc",
    "suất đầu tư", "dự toán", "chi phí", "điểm số", "phương án",
    "session", "màn hình", "nhập vào",
]
_IMPROVE_KEYWORDS = [
    "cải thiện", "tối ưu", "giảm chi phí", "tăng độ bền", "đề xuất",
    "thay đổi", "nên chọn", "hợp lý hơn", "phương án khác", "so sánh",
]


def classify_question(question: str) -> str:
    """
    Phân loại câu hỏi:
    - 'standard'      → hỏi về tiêu chuẩn, quy định
    - 'session_result'→ hỏi về kết quả tính toán hiện tại
    - 'improvement'   → đề xuất cải tiến thiết kế
    - 'general'       → câu hỏi chung về kỹ thuật cầu
    """
    q = question.lower()
    if any(kw in q for kw in _STANDARD_KEYWORDS):
        return "standard"
    if any(kw in q for kw in _RESULT_KEYWORDS):
        return "session_result"
    if any(kw in q for kw in _IMPROVE_KEYWORDS):
        return "improvement"
    return "general"


# ─────────────────────────────────────────────────────────────────────────────
# Cache đơn giản (in-memory, key = hash câu hỏi + context)
# ─────────────────────────────────────────────────────────────────────────────

_response_cache: Dict[str, Dict] = {}

def _cache_key(question: str, context: str) -> str:
    return hashlib.md5(f"{question}|||{context[:200]}".encode()).hexdigest()


def _get_cached(question: str, context: str) -> Optional[str]:
    key = _cache_key(question, context)
    entry = _response_cache.get(key)
    if entry and time.time() - entry["ts"] < 3600:  # TTL 1 giờ
        return entry["answer"]
    return None


def _set_cached(question: str, context: str, answer: str):
    key = _cache_key(question, context)
    _response_cache[key] = {"answer": answer, "ts": time.time()}


# ─────────────────────────────────────────────────────────────────────────────
# Định dạng ngữ cảnh RAG
# ─────────────────────────────────────────────────────────────────────────────

def _format_rag_context(chunks: List[Dict]) -> str:
    if not chunks:
        return "(Không tìm thấy tài liệu liên quan trong Knowledge Base)"
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(
            f"[Nguồn {i}] {c['filename']} ({c['source_type']}) — score={c['score']}\n"
            + c["text"]
        )
    return "\n\n---\n\n".join(parts)


def _format_session_context(session_data: Optional[Dict]) -> str:
    if not session_data:
        return "(Không có dữ liệu dự án từ phần mềm)"
    lines = []
    if "loai_cong_trinh" in session_data:
        lines.append(f"Loại công trình: {session_data['loai_cong_trinh']}")
    if "cap_duong" in session_data:
        lines.append(f"Cấp đường: {session_data['cap_duong']}")
    if "loai_dam" in session_data:
        lines.append(f"Loại dầm: {session_data['loai_dam']}")
    if "L_nhip" in session_data:
        lines.append(f"Nhịp thiết kế: {session_data['L_nhip']} m")
    if "n_nhip" in session_data:
        lines.append(f"Số nhịp: {session_data['n_nhip']}")
    if "n_dam" in session_data:
        lines.append(f"Số dầm/nhịp: {session_data['n_dam']}")
    if "suat_dau_tu" in session_data:
        lines.append(f"Suất đầu tư sơ bộ: {session_data['suat_dau_tu']:.2f} triệu/m²")
    if "tong_dau_tu" in session_data:
        lines.append(f"Tổng đầu tư sơ bộ: {session_data['tong_dau_tu']:.2f} triệu đồng")
    for k, v in session_data.items():
        if k not in ("loai_cong_trinh","cap_duong","loai_dam","L_nhip","n_nhip",
                     "n_dam","suat_dau_tu","tong_dau_tu"):
            lines.append(f"{k}: {v}")
    return "\n".join(lines) if lines else "(Không có dữ liệu)"


# ─────────────────────────────────────────────────────────────────────────────
# Gọi Claude API
# ─────────────────────────────────────────────────────────────────────────────

def _get_client():
    if not CLAUDE_API_KEY:
        raise ValueError(
            "Chưa cấu hình CLAUDE_API_KEY. "
            "Tạo file .env với dòng: CLAUDE_API_KEY=sk-ant-..."
        )
    try:
        import anthropic
    except ImportError as e:
        raise ImportError("Chưa cài anthropic. Chạy: pip install anthropic") from e
    return anthropic.Anthropic(api_key=CLAUDE_API_KEY)


def _call_claude_stream(
    system: str,
    user_message: str,
    history: List[Dict],
    model: str = DEFAULT_MODEL,
) -> Generator[str, None, Dict]:
    """
    Gọi Claude API ở chế độ streaming.
    Yields: các token text
    Returns (qua StopIteration.value): dict với usage stats
    """
    client = _get_client()

    messages = list(history[-10:])  # Giữ tối đa 10 lượt gần nhất
    messages.append({"role": "user", "content": user_message})

    usage_info: Dict = {}

    with client.messages.stream(
        model=model,
        max_tokens=1500,
        system=system,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
        # Sau khi stream xong
        final_msg = stream.get_final_message()
        usage = final_msg.usage
        usage_info = {
            "input_tokens":  usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_usd":      (
                usage.input_tokens / 1_000_000 * PRICE_INPUT
                + usage.output_tokens / 1_000_000 * PRICE_OUTPUT
            ),
        }
    return usage_info


def _call_claude_sync(
    system: str,
    user_message: str,
    history: List[Dict],
    model: str = DEFAULT_MODEL,
) -> Tuple[str, Dict]:
    """Gọi Claude API không streaming."""
    client = _get_client()

    messages = list(history[-10:])
    messages.append({"role": "user", "content": user_message})

    response = client.messages.create(
        model=model,
        max_tokens=1500,
        system=system,
        messages=messages,
    )

    text = response.content[0].text
    usage = response.usage
    usage_info = {
        "input_tokens":  usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost_usd":      (
            usage.input_tokens / 1_000_000 * PRICE_INPUT
            + usage.output_tokens / 1_000_000 * PRICE_OUTPUT
        ),
    }
    return text, usage_info


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def ask_bridge_assistant(
    question: str,
    session_context: Optional[Dict] = None,
    chat_history: Optional[List[Dict]] = None,
    stream: bool = True,
    model: str = DEFAULT_MODEL,
    use_rag: bool = True,
    k_rag: int = 5,
) -> Generator[str, None, None] | Tuple[str, Dict]:
    """
    Hỏi trợ lý AI thiết kế cầu.

    Parameters
    ----------
    question : str
        Câu hỏi của người dùng (tiếng Việt).
    session_context : dict, optional
        Dữ liệu thiết kế hiện tại từ st.session_state.
    chat_history : list of dict, optional
        Lịch sử hội thoại: [{"role": "user"|"assistant", "content": "..."}]
    stream : bool
        True → generator (dùng với st.write_stream); False → (text, usage)
    model : str
        Claude model ID.
    use_rag : bool
        True → tìm tài liệu liên quan trong Knowledge Base trước khi gọi API.
    k_rag : int
        Số chunk RAG trả về.

    Returns
    -------
    Nếu stream=True : generator yield từng token, kèm thuộc tính `.sources` và `.usage`
    Nếu stream=False: (full_text: str, usage: dict)
    """
    if chat_history is None:
        chat_history = []

    # 1. RAG — tìm tài liệu liên quan
    rag_chunks: List[Dict] = []
    if use_rag:
        try:
            from importlib.util import spec_from_file_location, module_from_spec
            _spec = spec_from_file_location(
                "rag_indexer",
                Path(__file__).parent / "14-RAG_Indexer.py",
            )
            _mod = module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            rag_chunks = _mod.query_similar(question, k=k_rag)
        except Exception as e:
            logger.warning("RAG không khả dụng: %s", e)

    # 2. Xây dựng system prompt
    rag_context     = _format_rag_context(rag_chunks)
    session_ctx_str = _format_session_context(session_context)
    system = SYSTEM_PROMPT.format(
        context=rag_context,
        session_context=session_ctx_str,
    )

    # 3. Kiểm tra cache (chỉ khi không stream)
    if not stream:
        cached = _get_cached(question, rag_context + session_ctx_str)
        if cached:
            return cached, {"cached": True, "cost_usd": 0}

    # 4. Gọi Claude API
    if stream:
        def _streaming_gen():
            full_text = ""
            usage_info = {}
            try:
                gen = _call_claude_stream(system, question, chat_history, model)
                for token in gen:
                    full_text += token
                    yield token
            except StopIteration as e:
                usage_info = e.value or {}
            except Exception as e:
                yield f"\n\n⚠️ Lỗi kết nối API: {e}"
            # Lưu sources và usage vào generator để caller đọc
            _streaming_gen.sources = rag_chunks
            _streaming_gen.usage   = usage_info
            _streaming_gen.full_text = full_text

        gen = _streaming_gen()
        gen.sources  = rag_chunks
        gen.usage    = {}
        gen.full_text = ""
        return gen

    else:
        text, usage = _call_claude_sync(system, question, chat_history, model)
        _set_cached(question, rag_context + session_ctx_str, text)
        usage["rag_sources"] = [
            {"filename": c["filename"], "score": c["score"]} for c in rag_chunks
        ]
        return text, usage


# ─────────────────────────────────────────────────────────────────────────────
# Kiểm tra sự tuân thủ tiêu chuẩn (compliance check)
# ─────────────────────────────────────────────────────────────────────────────

def check_compliance(design_params: Dict) -> Tuple[str, Dict]:
    """
    Kiểm tra nhanh các thông số thiết kế với tiêu chuẩn TCVN.

    Parameters
    ----------
    design_params : dict
        Ví dụ: {"loai_dam": "Super-T", "L_nhip": 38.2, "H_dam": 1750, ...}

    Returns
    -------
    (verdict: str, details: dict)
    """
    issues   = []
    warnings = []
    ok       = []

    loai = design_params.get("loai_dam", "")
    L    = float(design_params.get("L_nhip", 0))
    H    = float(design_params.get("H_dam", 0)) / 1000  # mm → m

    span_ranges = {
        "Super-T":       (25, 50),
        "Dầm I":         (15, 40),
        "T ngược":       (10, 25),
        "Dầm bản rỗng":  (6,  20),
    }

    lh_limits = {
        "Super-T": (18, 25),
        "Dầm I":   (16, 22),
        "T ngược": (10, 15),
    }

    if loai in span_ranges:
        lo, hi = span_ranges[loai]
        if L < lo:
            warnings.append(f"Nhịp L={L}m nhỏ hơn phạm vi tối ưu ({lo}–{hi}m) cho {loai}")
        elif L > hi:
            issues.append(f"Nhịp L={L}m vượt phạm vi khuyến nghị ({lo}–{hi}m) cho {loai}")
        else:
            ok.append(f"Nhịp L={L}m phù hợp với {loai} (TCVN 11823 Điều 5.5)")

    if H > 0 and L > 0:
        lh = L / H
        if loai in lh_limits:
            lo_lh, hi_lh = lh_limits[loai]
            if lh < lo_lh:
                warnings.append(f"L/H = {lh:.1f} < {lo_lh} — dầm quá nặng, lãng phí vật liệu")
            elif lh > hi_lh:
                issues.append(f"L/H = {lh:.1f} > {hi_lh} — dầm mảnh, cần kiểm tra độ võng (TCVN 11823 Điều 5.4.2)")
            else:
                ok.append(f"Tỉ lệ L/H = {lh:.1f} trong giới hạn ({lo_lh}–{hi_lh})")

    D_coc = float(design_params.get("D_coc", 0))
    if D_coc > 0 and D_coc < 600:
        warnings.append(f"D cọc = {D_coc}mm < 600mm — nhỏ hơn mức phổ biến (TCVN 10304 Điều 6.3.2)")

    verdict = "OK" if not issues else ("CẢNH BÁO" if not issues else "CẦN XEM XÉT")
    if issues:
        verdict = "CẦN XEM XÉT"
    elif warnings:
        verdict = "CẢNH BÁO"

    return verdict, {
        "issues":   issues,
        "warnings": warnings,
        "ok":       ok,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Test nhanh khi chạy trực tiếp
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test classify
    questions = [
        "TCVN 11823 quy định tỉ lệ L/H tối đa cho dầm Super-T là bao nhiêu?",
        "Đường kính tối thiểu của cọc khoan nhồi theo tiêu chuẩn là bao nhiêu?",
        "Kết quả suất đầu tư 11 triệu/m² có hợp lý không?",
        "Tôi nên cải thiện thiết kế như thế nào để giảm chi phí?",
    ]
    for q in questions:
        print(f"Q: {q}\n   → loại: {classify_question(q)}\n")

    # Test compliance check
    params = {"loai_dam": "Super-T", "L_nhip": 38.2, "H_dam": 1750, "D_coc": 800}
    verdict, details = check_compliance(params)
    print(f"\nCompliance check: {verdict}")
    for k, v in details.items():
        if v:
            print(f"  {k}: {v}")
