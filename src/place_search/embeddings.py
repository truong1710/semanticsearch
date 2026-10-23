import time

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import models


from .text_utils import fold
from .config import BATCH, EMBED_DIM, EMBED_MODEL, MODEL_CACHE_DIR


t0 = time.perf_counter()
dense_model = TextEmbedding(model_name=EMBED_MODEL, cache_dir=MODEL_CACHE_DIR)
sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25", disable_stemmer=True, cache_dir=MODEL_CACHE_DIR)
print(f"Đã nạp model trong {time.perf_counter() - t0:.1f}s")


def embed_dense(texts, batch_size=BATCH):
    return [v.tolist() for v in dense_model.embed(texts, batch_size=batch_size)]


def to_sparse(emb):
    return models.SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())


def embed_sparse_docs(texts):
    return [to_sparse(e) for e in sparse_model.embed([fold(t) for t in texts])]


def embed_sparse_query(query):
    return to_sparse(next(iter(sparse_model.query_embed(fold(query)))))


assert len(embed_dense(["thử"])[0]) == EMBED_DIM