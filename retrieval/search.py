import numpy as np

from qdrant_client import models

from config import CANDIDATE_MULT, COLLECTION, TAG_BOOST
from embedding.vectors import embed_dense, embed_sparse_query
from .query import (
    _unit,
    tag_vectors,
    detect_landmark,
    infer_query_tags,
    parse_query,
    route_category,
    similarities,
)
from indexing.qdrant import client
from common.text import fold


def _flt(category=None, geo=None, price_max=None, district=None):
    """Tạo bộ lọc Qdrant từ danh mục, địa điểm, giá và quận."""
    must = []

    # Lọc theo danh mục, ví dụ cat-hotel.
    if category:
        must.append(
            models.FieldCondition(
                key="category",
                match=models.MatchValue(value=category),
            )
        )

    # Lọc theo bán kính địa lý quanh địa điểm.
    if geo:
        lat, lon, radius = geo

        must.append(
            models.FieldCondition(
                key="location",
                geo_radius=models.GeoRadius(
                    center=models.GeoPoint(lat=lat, lon=lon),
                    radius=radius,
                ),
            )
        )

    # "Dưới 3 triệu" nghĩa là giá nhỏ hơn 3.000.000 VND.
    if price_max is not None:
        must.append(
            models.FieldCondition(
                key="price_max",
                range=models.Range(lt=price_max),
            )
        )

    # Lọc theo quận.
    if district:
        must.append(
            models.FieldCondition(
                key="district",
                match=models.MatchValue(value=district),
            )
        )

    return models.Filter(must=must) if must else None


def search_dense(query, top_k=5, flt=None):
    """Tìm kiếm dense vector."""
    return client.query_points(
    collection_name=COLLECTION,
    query=embed_dense(
        [query],
        task_type="RETRIEVAL_QUERY",
    )[0],
    using="dense",
    query_filter=flt,
    limit=top_k,
    with_payload=True,
).points

    


def search_hybrid(query, top_k=5, flt=None, q_dense=None):
    """Tìm kiếm hybrid dense + sparse bằng RRF."""
    if q_dense is None:
        q_dense = embed_dense(
            [query],
            task_type="RETRIEVAL_QUERY",
        )[0]

    candidate_count = max(top_k * CANDIDATE_MULT, 20)

    return client.query_points(
        collection_name=COLLECTION,
        prefetch=[
            models.Prefetch(
                query=q_dense,
                using="dense",
                filter=flt,
                limit=candidate_count,
            ),
            models.Prefetch(
                query=embed_sparse_query(query),
                using="sparse",
                filter=flt,
                limit=candidate_count,
            ),
        ],
        query=models.FusionQuery(
            fusion=models.Fusion.RRF
        ),
        limit=candidate_count,
        with_payload=True,
    ).points


def smart_search(query, top_k=5, debug=False):
    """Tìm kiếm thông minh có kết hợp phân tích câu hỏi và bộ lọc."""

    # 1. Tách nội dung tìm kiếm và điều kiện.
    text, price_max, district = parse_query(query)

    # 2. Tạo embedding từ nội dung đã tách điều kiện.
    q_dense = embed_dense(
        [text],
        task_type="RETRIEVAL_QUERY",
    )[0]
    q_vec = _unit(q_dense)
    q_fold = fold(query)

    # 3. Phân tích danh mục và tag.
    category, cat_scores = route_category(q_vec, q_fold, text)
    wanted = set(infer_query_tags(q_vec, q_fold))

    # 4. Phát hiện địa danh có hỗ trợ tìm theo bán kính.
    landmark_name, geo = detect_landmark(q_fold)

    # 5. Tạo các lượt tìm kiếm.
    # Chỉ nới lỏng bán kính địa lý; không tự ý bỏ giá,
    # quận hoặc danh mục vì đó là điều kiện người dùng yêu cầu.
    attempts = [
        (category, geo, price_max, district),
    ]

    if geo:
        attempts.append(
            (category, None, price_max, district)
        )

    # 6. Tìm kiếm và loại các kết quả trùng ID.
    pool = {}
    tier = {}
    used = None

    for attempt_index, (cat, geo_filter, max_price, dist) in enumerate(attempts):
        qdrant_filter = _flt(
            category=cat,
            geo=geo_filter,
            price_max=max_price,
            district=dist,
        )

        found = search_hybrid(
            query=text,
            top_k=top_k,
            flt=qdrant_filter,
            q_dense=q_dense,
        )

        for hit in found:
            if hit.id not in pool:
                pool[hit.id] = hit
                tier[hit.id] = attempt_index

        if found and used is None:
            used = {
                "category": cat,
                "landmark": landmark_name if geo_filter else None,
                "price_max": max_price,
                "district": dist,
            }

        if len(pool) >= top_k:
            break

    hits = list(pool.values())

    # 7. Xếp hạng lại theo điểm hybrid và mức khớp tag.
    if hits:
        max_score = max(hit.score for hit in hits)

        if max_score == 0:
            max_score = 1.0

        for hit in hits:
            payload_tags = set(hit.payload.get("tags") or [])
            overlap = len(wanted & payload_tags)

            hit.score = (
                hit.score / max_score
                + TAG_BOOST * overlap
            )

        hits = sorted(
            hits,
            key=lambda hit: (
                tier[hit.id],
                -hit.score,
            ),
        )[:top_k]

    # 8. In thông tin debug.
    if debug:
        print(f"\nTruy vấn: {query!r}")
        print(f"  Nội dung tìm kiếm: {text!r}")
        print(f"  category={category}")
        print(f"  tags={sorted(wanted)}")
        print(f"  landmark={landmark_name}")
        print(f"  price_max={price_max}")
        print(f"  district={district}")
        print(f"  Bộ lọc được sử dụng={used}")

        top_similarities = sorted(
            similarities(q_vec, tag_vectors()).items(),
            key=lambda item: -item[1],
        )[:3]

        print(
            "  Độ giống tag cao nhất:",
            [(name, round(score, 2)) for name, score in top_similarities],
        )

        print(f"  Số kết quả: {len(hits)}")

    return hits


def show_smart(query, top_k=5, skip=("location",)):
    """In kết quả tìm kiếm."""
    hits = smart_search(query, top_k=top_k, debug=True)

    if not hits:
        print("  Không có kết quả phù hợp.")
        return

    for index, hit in enumerate(hits, 1):
        print(f"\nKết quả {index} (điểm {hit.score:.3f})")

        for key, value in (hit.payload or {}).items():
            if key in skip:
                continue

            print(f"  {key}: {value}")


# Điền ID thật từ MySQL; để trống thì bỏ qua bước đánh giá.
EVAL_SET = []


def evaluate(search_fn, k=5, name=""):
    recalls, reciprocal_ranks = [], []
    for query, relevant in EVAL_SET:
        ids = [hit.payload["id"] for hit in search_fn(query, k)]
        recalls.append(len(set(ids) & relevant) / len(relevant))
        rank = next((i for i, place_id in enumerate(ids, 1) if place_id in relevant), None)
        reciprocal_ranks.append(1 / rank if rank else 0.0)

    print(
        f"{name:18s} recall@{k} = {np.mean(recalls):.3f} "
        f"| MRR = {np.mean(reciprocal_ranks):.3f}"
    )


def run_evaluation():
    if not EVAL_SET:
        print("(EVAL_SET đang trống, bỏ qua đánh giá)")
        return

    print("\n=== ĐÁNH GIÁ ===")
    evaluate(search_dense, name="dense")
    evaluate(lambda query, k: search_hybrid(query, k)[:k], name="hybrid")
    evaluate(smart_search, name="smart (đầy đủ)")


def main():
    """Ví dụ an toàn mặc định; truyền câu hỏi để tìm trên dịch vụ thật."""
    import argparse

    parser = argparse.ArgumentParser(description="Place search demo")
    parser.add_argument("query", nargs="*", help="search text")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()
    if args.evaluate:
        run_evaluation()
    elif args.query:
        show_smart(" ".join(args.query), top_k=args.top_k)
    else:
        print("Ví dụ tìm thật: python -m retrieval.search quán cà phê yên tĩnh --top-k 5")


if __name__ == "__main__":
    main()
