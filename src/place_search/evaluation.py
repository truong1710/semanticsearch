import numpy as np

from .search import search_dense, search_hybrid, smart_search

# Điền ID thật từ MySQL (dạng chuỗi). Để trống thì bỏ qua đánh giá.
EVAL_SET = [
    # ("quán cà phê trứng", {"12", "47"}),
]


def evaluate(search_fn, k=5, name=""):
    recalls, rrs = [], []
    for query, relevant in EVAL_SET:
        ids = [h.payload["id"] for h in search_fn(query, k)]
        recalls.append(len(set(ids) & relevant) / len(relevant))
        rank = next((i for i, x in enumerate(ids, 1) if x in relevant), None)
        rrs.append(1 / rank if rank else 0.0)
    print(f"{name:18s} recall@{k} = {np.mean(recalls):.3f} | MRR = {np.mean(rrs):.3f}")


def run_all():
    if not EVAL_SET:
        print("(EVAL_SET đang trống, bỏ qua đánh giá)")
        return
    print("\n=== ĐÁNH GIÁ ===")
    evaluate(lambda q, k: search_dense(q, k), name="dense")
    evaluate(lambda q, k: search_hybrid(q, k)[:k], name="hybrid")
    evaluate(lambda q, k: smart_search(q, k), name="smart (đầy đủ)")