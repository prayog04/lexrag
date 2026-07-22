"""Thin wrapper around fastembed so the rest of the codebase doesn't care
which embedding model or library is behind it. fastembed runs ONNX models
on CPU, which is what makes this cheap to host — no GPU, no PyTorch."""

from __future__ import annotations

from functools import lru_cache

from fastembed import TextEmbedding

from lexrag import config


@lru_cache(maxsize=1)
def get_embedder() -> TextEmbedding:
    return TextEmbedding(model_name=config.EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    embedder = get_embedder()
    return [vec.tolist() for vec in embedder.embed(texts)]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def embedding_dim() -> int:
    return len(embed_query("dimension probe"))
