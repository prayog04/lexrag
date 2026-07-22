"""Parse both PDFs, chunk them, embed, and upsert into Qdrant.

    python -m lexrag.ingestion.ingest              # full ingestion
    python -m lexrag.ingestion.ingest --dry-run     # parse + chunk only, print
                                                     # diagnostics, skip Qdrant

Re-run after any change to the PDFs or the parsers — it's idempotent
(point IDs are deterministic UUIDs derived from the chunk ID, so re-ingesting
overwrites rather than duplicates).
"""

from __future__ import annotations

import argparse
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from lexrag import config
from lexrag.ingestion.chunker import chunk_sections
from lexrag.ingestion.embed import embed_texts, embedding_dim
from lexrag.models import Chunk
from lexrag.parsing.bns_parser import parse_bns
from lexrag.parsing.ipc_parser import parse_ipc

_NAMESPACE = uuid.UUID("b8d1a9d0-6f3b-4b8a-9b1e-2f8f9a7c5e10")
_BATCH_SIZE = 64


def build_chunks() -> tuple[int, int, list[Chunk]]:
    ipc_sections = parse_ipc(config.IPC_PDF_PATH)
    bns_sections = parse_bns(config.BNS_PDF_PATH)
    chunks = chunk_sections(ipc_sections) + chunk_sections(bns_sections)
    return len(ipc_sections), len(bns_sections), chunks


def print_diagnostics(ipc_count: int, bns_count: int, chunks: list[Chunk]) -> None:
    section_chunks = sum(1 for c in chunks if c.chunk_type == "section")
    clause_chunks = sum(1 for c in chunks if c.chunk_type == "clause")
    print(f"IPC sections parsed: {ipc_count}")
    print(f"BNS sections parsed: {bns_count}")
    print(f"Total chunks: {len(chunks)} (section: {section_chunks}, clause: {clause_chunks})")


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, chunk_id))


def ingest(client: QdrantClient | None = None) -> None:
    ipc_count, bns_count, chunks = build_chunks()
    print_diagnostics(ipc_count, bns_count, chunks)

    client = client or QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY)
    dim = embedding_dim()

    if not client.collection_exists(config.QDRANT_COLLECTION):
        client.create_collection(
            collection_name=config.QDRANT_COLLECTION,
            vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
        )
        for field in ("act", "section_no", "chunk_type"):
            client.create_payload_index(
                collection_name=config.QDRANT_COLLECTION,
                field_name=field,
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )

    for i in range(0, len(chunks), _BATCH_SIZE):
        batch = chunks[i : i + _BATCH_SIZE]
        vectors = embed_texts([c.text for c in batch])
        points = [
            qmodels.PointStruct(
                id=_point_id(c.id),
                vector=vec,
                payload={
                    "chunk_id": c.id,
                    "act": c.act,
                    "section_no": c.section_no,
                    "section_title": c.section_title,
                    "chapter_no": c.chapter_no,
                    "chapter_title": c.chapter_title,
                    "chunk_type": c.chunk_type,
                    "parent_id": c.parent_id,
                    "text": c.text,
                    **c.metadata,
                },
            )
            for c, vec in zip(batch, vectors)
        ]
        client.upsert(collection_name=config.QDRANT_COLLECTION, points=points)
        print(f"Upserted {min(i + _BATCH_SIZE, len(chunks))}/{len(chunks)}")

    print("Ingestion complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and chunk only; skip embedding and Qdrant. Use this to sanity-check the parsers after a PDF or code change.",
    )
    args = parser.parse_args()

    if args.dry_run:
        ipc_count, bns_count, chunks = build_chunks()
        print_diagnostics(ipc_count, bns_count, chunks)
        return

    ingest()


if __name__ == "__main__":
    main()
