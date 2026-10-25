import os
import time
from functools import lru_cache

import numpy as np
from google import genai
from google.genai import types
from fastembed import SparseTextEmbedding
from qdrant_client import models

from common.text import fold
from config import BATCH, EMBED_DIM, EMBED_MODEL, MODEL_CACHE_DIR


@lru_cache(maxsize=1)
def _gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Thiếu GEMINI_API_KEY; hãy cấu hình trong .env.")
    return genai.Client(api_key=api_key)


@lru_cache(maxsize=1)
def _sparse_model():
    return SparseTextEmbedding(
        model_name="Qdrant/bm25",
        disable_stemmer=True,
        cache_dir=MODEL_CACHE_DIR,
    )


def embed_dense(
    texts,
    batch_size=BATCH,
    task_type="RETRIEVAL_DOCUMENT",
):
    """
    Chuyển văn bản thành dense vector bằng Gemini.

    RETRIEVAL_DOCUMENT: văn bản địa điểm/prototype.
    RETRIEVAL_QUERY: câu người dùng tìm kiếm.
    """
    if isinstance(texts, str):
        texts = [texts]

    if not texts:
        return []

    all_vectors = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]

        response = _gemini_client().models.embed_content(
            model=EMBED_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBED_DIM,
            ),
        )

        for item in response.embeddings:
            vector = np.asarray(item.values, dtype=np.float32)

            if len(vector) != EMBED_DIM:
                raise ValueError(
                    f"Sai số chiều: nhận {len(vector)}, "
                    f"mong đợi {EMBED_DIM}"
                )

            # Gemini Embedding 001 cần chuẩn hóa
            # khi dùng output_dimensionality=768.
            norm = np.linalg.norm(vector)

            if norm == 0:
                raise ValueError("Gemini trả về vector có norm bằng 0")

            vector = vector / norm
            all_vectors.append(vector.tolist())

        # Nghỉ ngắn giữa các batch.
        if start + batch_size < len(texts):
            time.sleep(0.2)

    return all_vectors


def to_sparse(emb):
    return models.SparseVector(
        indices=emb.indices.tolist(),
        values=emb.values.tolist(),
    )


def embed_sparse_docs(texts):
    return [
        to_sparse(e)
        for e in _sparse_model().embed([fold(t) for t in texts])
    ]


def embed_sparse_query(query):
    return to_sparse(
        next(iter(_sparse_model().query_embed(fold(query))))
    )


def main():
    """Demo cục bộ hoặc tạo vector thật với ``--embed``."""
    import argparse

    parser = argparse.ArgumentParser(description="Embedding example")
    parser.add_argument("--text", default="Quán cà phê yên tĩnh gần Hồ Tây")
    parser.add_argument("--embed", choices=("dense", "sparse"), help="run model/API")
    args = parser.parse_args()
    if args.embed == "dense":
        print(embed_dense(args.text, task_type="RETRIEVAL_QUERY"))
    elif args.embed == "sparse":
        print(embed_sparse_query(args.text))
    else:
        print("Input:", args.text)
        print("Folded:", fold(args.text))
        print("Ví dụ vector thật: python -m embedding.vectors --embed dense")


if __name__ == "__main__":
    main()
