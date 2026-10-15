from qdrant_client import models

from .config import CANDIDATE_MULT, COLLECTION, TAG_BOOST
from .embeddings import embed_dense, embed_sparse_query
from .query_analysis import (TAG_VECS, _unit, detect_landmark, infer_query_tags,
                             route_category, similarities)
from .store import client
from .text_utils import fold


def _flt(category=None, geo=None):
    must = []
    if category:
        must.append(models.FieldCondition(key="category", match=models.MatchValue(value=category)))
    if geo:
        lat, lon, r = geo
        must.append(models.FieldCondition(
            key="location",
            geo_radius=models.GeoRadius(center=models.GeoPoint(lat=lat, lon=lon), radius=r)))
    return models.Filter(must=must) if must else None


def search_dense(query, top_k=5, flt=None):
    return client.query_points(
        COLLECTION, query=embed_dense([query])[0], using="dense",
        query_filter=flt, limit=top_k, with_payload=True).points


def search_hybrid(query, top_k=5, flt=None, q_dense=None):
    if q_dense is None:
        q_dense = embed_dense([query])[0]
    n = max(top_k * CANDIDATE_MULT, 20)
    return client.query_points(
        COLLECTION,
        prefetch=[
            models.Prefetch(query=q_dense, using="dense", filter=flt, limit=n),
            models.Prefetch(query=embed_sparse_query(query), using="sparse", filter=flt, limit=n),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=n, with_payload=True).points


def smart_search(query, top_k=5, debug=False):
    q_dense = embed_dense([query])[0]
    q_vec = _unit(q_dense)
    q_fold = fold(query)

    category, cat_scores = route_category(q_vec, q_fold, query)
    wanted = set(infer_query_tags(q_vec, q_fold))
    lm_name, geo = detect_landmark(q_fold)

    if category:
        attempts = [(category, geo), (category, None)] if geo else [(category, None)]
    else:
        attempts = [(None, geo), (None, None)] if geo else [(None, None)]

    pool, tier, used = {}, {}, None
    for t, (cat, g) in enumerate(attempts):
        found = search_hybrid(query, top_k, _flt(cat, g), q_dense)
        for h in found:
            if h.id not in pool:
                pool[h.id], tier[h.id] = h, t
        if found and used is None:
            used = {"category": cat, "landmark": lm_name if g else None}
        if len(pool) >= top_k:
            break
    hits = list(pool.values())

    if hits:
        top = max(h.score for h in hits) or 1.0
        for h in hits:
            overlap = len(wanted & set(h.payload.get("tags", [])))
            h.score = h.score / top + TAG_BOOST * overlap
        hits = sorted(hits, key=lambda h: (tier[h.id], -h.score))[:top_k]

    if debug:
        print(f"\nTruy vấn: {query!r}")
        print(f"  category={category} | tags={sorted(wanted)} | landmark={lm_name} | bộ lọc dùng={used}")
        top_sims = sorted(similarities(q_vec, TAG_VECS).items(), key=lambda x: -x[1])[:3]
        print("  độ giống tag cao nhất:", [(k, round(v, 2)) for k, v in top_sims])
    return hits


def show_smart(query, top_k=5, skip=("location",)):
    hits = smart_search(query, top_k, debug=True)
    if not hits:
        print("  Không có kết quả.")
    for i, h in enumerate(hits, 1):
        print(f"\nKết quả {i}  (điểm {h.score:.3f})")
        for k, v in h.payload.items():
            if k in skip:
                continue
            print(f"  {k}: {v}")