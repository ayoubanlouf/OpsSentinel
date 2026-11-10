"""Runbook Ingestion Engine: parses technical runbooks, chunks with semantic overlap,
computes vector embeddings via Google Gemini API, and stores them in PostgreSQL pgvector.
"""

import argparse
import glob
import logging
import os
import re
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from opssentinel.config import settings
from opssentinel.db import clear_runbooks, get_db_connection, insert_runbook_chunk

logger = logging.getLogger("opssentinel.ingestion")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def get_gemini_client() -> genai.Client:
    """Initialize the Google GenAI Client with configured API key."""
    if not settings.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY is not configured in environment or .env file. "
            "Please set GEMINI_API_KEY before running ingestion."
        )
    return genai.Client(api_key=settings.gemini_api_key)


def compute_embedding(
    client: genai.Client,
    text: str,
    model: str | None = None,
    dimensions: int = 768,
) -> list[float]:
    """Compute vector embedding for a text chunk using the Google Gemini API."""
    model_name = model or settings.gemini_embedding_model
    response = client.models.embed_content(
        model=model_name,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=dimensions),
    )
    # Support both single embedding or list response
    if hasattr(response, "embeddings") and response.embeddings:
        return list(response.embeddings[0].values)
    elif hasattr(response, "embedding") and response.embedding:
        return list(response.embedding.values)
    else:
        raise ValueError(f"Unexpected response structure from embed_content: {response}")


def parse_runbook_metadata(content: str, filename: str) -> tuple[str, str, dict[str, Any]]:
    """Extract title, category, and metadata from markdown content."""
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else Path(filename).stem.replace("_", " ").title()

    category = "General SRE"
    cat_match = re.search(r"\*\*Category\*\*:\s*([^\n]+)", content)
    if cat_match:
        category = cat_match.group(1).strip()

    severity = "P2"
    sev_match = re.search(r"\*\*Severity\*\*:\s*([^\n]+)", content)
    if sev_match:
        severity = sev_match.group(1).strip()

    service = "Core Infrastructure"
    svc_match = re.search(r"\*\*Service Name\*\*:\s*([^\n]+)", content)
    if svc_match:
        service = svc_match.group(1).strip()

    metadata = {
        "title": title,
        "filename": os.path.basename(filename),
        "category": category,
        "severity": severity,
        "service": service,
    }
    return title, category, metadata


def chunk_text_semantically(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[str]:
    """Split markdown text into semantic chunks respecting section boundaries and paragraphs."""
    # Split by markdown headers (## ) to preserve contextual semantic blocks
    sections = re.split(r"(?=(?:\n|^)##\s+)", text)
    chunks: list[str] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        if len(section) <= chunk_size:
            chunks.append(section)
        else:
            # Split section by paragraphs or double newlines
            paragraphs = section.split("\n\n")
            current_chunk: list[str] = []
            current_len = 0

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                para_len = len(para)

                if current_len + para_len + 2 > chunk_size and current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append(chunk_text)
                    # Create semantic overlap from tail of previous chunk
                    overlap_chars = 0
                    overlap_paras: list[str] = []
                    for p in reversed(current_chunk):
                        if overlap_chars + len(p) <= chunk_overlap:
                            overlap_paras.insert(0, p)
                            overlap_chars += len(p)
                        else:
                            break
                    current_chunk = overlap_paras + [para]
                    current_len = sum(len(p) for p in current_chunk) + len(current_chunk) * 2
                else:
                    current_chunk.append(para)
                    current_len += para_len + 2

            if current_chunk:
                chunks.append("\n\n".join(current_chunk))

    return chunks if chunks else [text]


def ingest_file(
    file_path: str,
    client: genai.Client,
    conn: Any,
) -> int:
    """Ingest a single markdown runbook into pgvector."""
    path = Path(file_path)
    if not path.is_file():
        logger.warning("Skipping missing file: %s", file_path)
        return 0

    content = path.read_text(encoding="utf-8")
    title, category, metadata = parse_runbook_metadata(content, path.name)
    chunks = chunk_text_semantically(content)

    logger.info(
        "Ingesting '%s' (%s chunks) - Category: %s",
        title,
        len(chunks),
        category,
    )

    ingested_count = 0
    for idx, chunk in enumerate(chunks):
        # Prepend title and category context to each chunk embedding for high retrieval relevance
        embedding_input = f"Runbook: {title}\nCategory: {category}\nContent:\n{chunk}"
        embedding = compute_embedding(client, embedding_input)

        chunk_meta = {**metadata, "chunk_index": idx, "total_chunks": len(chunks)}
        insert_runbook_chunk(
            conn=conn,
            title=title,
            filename=path.name,
            category=category,
            content=chunk,
            chunk_index=idx,
            embedding=embedding,
            metadata=chunk_meta,
        )
        ingested_count += 1

    return ingested_count


def ingest_all_runbooks(
    docs_dir: str = "docs",
    reset: bool = True,
) -> int:
    """Ingest all markdown runbooks found inside docs_dir recursively."""
    client = get_gemini_client()
    pattern = os.path.join(docs_dir, "**", "*.md")
    files = glob.glob(pattern, recursive=True)

    if not files:
        logger.warning("No markdown files found matching pattern: %s", pattern)
        return 0

    total_chunks = 0
    with get_db_connection() as conn:
        if reset:
            logger.info("Resetting existing runbooks table...")
            clear_runbooks(conn)

        for file_path in sorted(files):
            total_chunks += ingest_file(file_path, client, conn)

    logger.info("Successfully ingested %d total chunks from %d files.", total_chunks, len(files))
    return total_chunks


def main():
    """CLI entrypoint for ingestion."""
    parser = argparse.ArgumentParser(description="OpsSentinel Runbook Vector Ingestion Engine")
    parser.add_argument(
        "--docs-dir",
        default="docs",
        help="Root directory containing markdown runbooks (default: docs)",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not clear existing runbooks table before ingestion",
    )
    args = parser.parse_args()

    try:
        count = ingest_all_runbooks(docs_dir=args.docs_dir, reset=not args.no_reset)
        print(f"Ingestion complete: {count} chunks indexed.")
    except Exception as e:
        logger.error("Ingestion failed: %s", e, exc_info=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()

