# -*- coding: utf-8 -*-
"""
14-RAG_Indexer.py — Vector index cho Knowledge Base thiết kế cầu
Sử dụng sentence-transformers (multilingual) + ChromaDB
"""

from __future__ import annotations

import os
import re
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger("RAG_Indexer")

# ─────────────────────────────────────────────────────────────────────────────
# Cấu hình
# ─────────────────────────────────────────────────────────────────────────────

KB_DIR     = Path(__file__).parent / "Data" / "Knowledge_Base"
CHROMA_DIR = Path(__file__).parent / "Data" / "chroma_db"

EMBED_MODEL   = "paraphrase-multilingual-mpnet-base-v2"
CHUNK_SIZE    = 600     # ký tự mỗi chunk
CHUNK_OVERLAP = 80      # ký tự overlap giữa chunk liên tiếp
COLLECTION    = "bridge_knowledge"
TOP_K_DEFAULT = 5

# Map thư mục KB → loại nguồn tài liệu
SOURCE_TYPES: Dict[str, str] = {
    "TCVN":        "Tiêu chuẩn kỹ thuật",
    "QCVN":        "Quy chuẩn",
    "Catalog":     "Catalog sản phẩm",
    "Phap_Ly":     "Văn bản pháp lý",
    "Kinh_Nghiem": "Kinh nghiệm thiết kế",
    "Tieu_Chuan_AI": "Tiêu chuẩn AI",
}

# ─────────────────────────────────────────────────────────────────────────────
# Chunking
# ─────────────────────────────────────────────────────────────────────────────

def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Tách văn bản thành các đoạn có overlap."""
    # Ưu tiên tách tại dòng trống (ranh giới đoạn) để giữ ngữ nghĩa
    paragraphs: List[str] = re.split(r"\n{2,}", text.strip())
    chunks: List[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 <= size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
                # Overlap: giữ phần cuối của chunk hiện tại
                tail = current[-overlap:] if overlap else ""
                current = (tail + "\n\n" + para).strip()
            else:
                # Đoạn đơn quá dài → cắt cứng
                for i in range(0, len(para), size - overlap):
                    chunks.append(para[i : i + size])
                current = ""

    if current:
        chunks.append(current)

    return [c for c in chunks if len(c.strip()) > 30]


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()[:12]


# ─────────────────────────────────────────────────────────────────────────────
# Đọc tài liệu
# ─────────────────────────────────────────────────────────────────────────────

def _load_txt(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1258", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _load_docx(path: Path) -> str:
    try:
        import docx
        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        logger.warning("python-docx chưa cài — bỏ qua %s", path.name)
        return ""


def _load_pdf(path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
    except ImportError:
        logger.warning("pdfplumber chưa cài — bỏ qua %s", path.name)
        return ""


def load_document(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".txt":
        return _load_txt(path)
    if ext == ".docx":
        return _load_docx(path)
    if ext == ".pdf":
        return _load_pdf(path)
    logger.warning("Định dạng không hỗ trợ: %s", path.suffix)
    return ""


def _source_type_from_path(path: Path) -> str:
    for part in path.parts:
        if part in SOURCE_TYPES:
            return SOURCE_TYPES[part]
    return "Tài liệu tham khảo"


def collect_documents() -> List[Dict]:
    """Duyệt KB_DIR, trả về list dict {path, text, source_type, filename}."""
    docs = []
    for ext in ("*.txt", "*.pdf", "*.docx"):
        for fp in KB_DIR.rglob(ext):
            text = load_document(fp)
            if len(text.strip()) < 50:
                continue
            docs.append({
                "path":        fp,
                "text":        text,
                "source_type": _source_type_from_path(fp),
                "filename":    fp.name,
                "rel_path":    str(fp.relative_to(KB_DIR)),
            })
    logger.info("Tìm thấy %d tài liệu trong Knowledge Base", len(docs))
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# ChromaDB helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_chroma():
    """Trả về (client, collection) ChromaDB — lazy import."""
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError as e:
        raise ImportError(
            "Chưa cài chromadb. Chạy: pip install chromadb"
        ) from e

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    col = client.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    return client, col


def _get_embedder():
    """Trả về SentenceTransformer model — lazy import."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise ImportError(
            "Chưa cài sentence-transformers. Chạy: pip install sentence-transformers"
        ) from e
    logger.info("Đang tải embedding model: %s", EMBED_MODEL)
    return SentenceTransformer(EMBED_MODEL)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def rebuild_index(force: bool = False) -> Dict:
    """
    Xây dựng lại toàn bộ vector index từ Knowledge Base.

    Parameters
    ----------
    force : bool
        True → xóa index cũ trước khi xây lại.

    Returns
    -------
    dict với keys: n_docs, n_chunks, embed_model, collection
    """
    _, col = _get_chroma()
    embedder = _get_embedder()

    if force:
        logger.info("Xóa index cũ...")
        col.delete(where={"source_type": {"$ne": "_placeholder_"}})

    docs = collect_documents()
    if not docs:
        logger.warning("Không tìm thấy tài liệu nào trong %s", KB_DIR)
        return {"n_docs": 0, "n_chunks": 0}

    # Kiểm tra những file đã index (dựa trên file_hash trong metadata)
    existing_ids: set = set(col.get(include=[])["ids"])

    all_ids, all_texts, all_embeds, all_metas = [], [], [], []
    total_chunks = 0

    for doc in docs:
        file_hash = _file_hash(doc["path"])
        chunks = _chunk_text(doc["text"])
        for i, chunk in enumerate(chunks):
            chunk_id = f"{file_hash}_{i:04d}"
            if chunk_id in existing_ids and not force:
                continue  # Skip: đã có trong index
            all_ids.append(chunk_id)
            all_texts.append(chunk)
            all_metas.append({
                "filename":    doc["filename"],
                "rel_path":    doc["rel_path"],
                "source_type": doc["source_type"],
                "chunk_idx":   i,
                "file_hash":   file_hash,
            })
        total_chunks += len(chunks)

    if not all_texts:
        logger.info("Index đã cập nhật — không có chunk mới.")
        return {"n_docs": len(docs), "n_chunks": total_chunks, "new_chunks": 0}

    logger.info("Đang embedding %d chunk mới...", len(all_texts))
    embeds = embedder.encode(all_texts, show_progress_bar=True, normalize_embeddings=True)
    all_embeds = embeds.tolist()

    # Upsert theo batch 500
    batch = 500
    for i in range(0, len(all_ids), batch):
        col.upsert(
            ids=all_ids[i : i + batch],
            embeddings=all_embeds[i : i + batch],
            documents=all_texts[i : i + batch],
            metadatas=all_metas[i : i + batch],
        )

    logger.info(
        "Index hoàn tất: %d tài liệu, %d chunk (%d mới)",
        len(docs), total_chunks, len(all_ids),
    )
    return {
        "n_docs":       len(docs),
        "n_chunks":     total_chunks,
        "new_chunks":   len(all_ids),
        "embed_model":  EMBED_MODEL,
        "collection":   COLLECTION,
        "chroma_dir":   str(CHROMA_DIR),
    }


def query_similar(
    question: str,
    k: int = TOP_K_DEFAULT,
    source_filter: Optional[str] = None,
) -> List[Dict]:
    """
    Tìm k chunk gần nhất với câu hỏi.

    Parameters
    ----------
    question : str
        Câu hỏi (tiếng Việt hoặc tiếng Anh).
    k : int
        Số kết quả trả về.
    source_filter : str, optional
        Lọc theo source_type, ví dụ "Tiêu chuẩn kỹ thuật".

    Returns
    -------
    List[Dict] với keys: text, filename, rel_path, source_type, score
    """
    _, col = _get_chroma()
    embedder = _get_embedder()

    n_docs = col.count()
    if n_docs == 0:
        logger.warning("Index rỗng. Hãy chạy rebuild_index() trước.")
        return []

    q_embed = embedder.encode([question], normalize_embeddings=True).tolist()

    where = None
    if source_filter:
        where = {"source_type": source_filter}

    results = col.query(
        query_embeddings=q_embed,
        n_results=min(k, n_docs),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append({
            "text":        doc,
            "filename":    meta.get("filename", ""),
            "rel_path":    meta.get("rel_path", ""),
            "source_type": meta.get("source_type", ""),
            "score":       round(1.0 - dist, 4),  # cosine similarity
        })

    return output


def get_index_stats() -> Dict:
    """Trả về thống kê về vector index hiện tại."""
    try:
        _, col = _get_chroma()
        n = col.count()
        if n == 0:
            return {"status": "empty", "n_chunks": 0}
        # Lấy mẫu metadata để đếm số tài liệu
        sample = col.get(limit=min(n, 10000), include=["metadatas"])
        files = {m["filename"] for m in sample["metadatas"]}
        return {
            "status":   "ready",
            "n_chunks": n,
            "n_files":  len(files),
            "collection": COLLECTION,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# CLI helper
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "rebuild"

    if cmd == "rebuild":
        result = rebuild_index(force="--force" in sys.argv)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "query":
        q = " ".join(sys.argv[2:]) or "Chiều cao dầm Super-T cho nhịp 38m"
        results = query_similar(q, k=3)
        for i, r in enumerate(results, 1):
            print(f"\n[{i}] {r['filename']} (score={r['score']})")
            print(r["text"][:300])

    elif cmd == "stats":
        print(json.dumps(get_index_stats(), ensure_ascii=False, indent=2))

    else:
        print("Usage: python 14-RAG_Indexer.py [rebuild|query <text>|stats] [--force]")
