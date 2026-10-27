import uuid
from itertools import islice

from qdrant_client import QdrantClient, models
from indexing.ai_tagger import suggest_tags
from config import BATCH, COLLECTION, EMBED_DIM, QDRANT_URL, TAG_VERSION
from embedding.vectors import embed_dense, embed_sparse_docs
from common.taxonomy import (
    TAXONOMY,
    ALLOWED_TAGS,
    CATEGORY_VI,
    TAG_VI,
    TAG_GROUP,
    rule_tags_with_evidence,
    validate_tags,
)
from common.text import clean_text
from retrieval.query import parse_district, parse_price_range
client = QdrantClient(url=QDRANT_URL)
NAMESPACE = uuid.UUID("6f1c2f0e-3b7a-4c1e-9d55-2b8a1f7c9e10")

# Chỉ store.py được sửa hai dict này
PLACE_TAGS_BY_ID, TAG_SOURCE_BY_ID = {}, {}

import hashlib
from config import EMBED_MODEL




def point_id(place_id: str) -> str:
    return str(uuid.uuid5(NAMESPACE, str(place_id)))


def batched(iterable, n):
    it = iter(iterable)
    while batch := list(islice(it, n)):
        yield batch


def text_hash(text):
    key = f"{EMBED_MODEL}|{EMBED_DIM}\n{text}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()

def existing_hashes(ids):
    pts = client.retrieve(COLLECTION, ids=ids, with_payload=["text_hash"], with_vectors=False)
    return {str(p.id): (p.payload or {}).get("text_hash") for p in pts}


def build_payload(p, h):
    pmin, pmax = parse_price_range(p.get("price_range"))
    tags = PLACE_TAGS_BY_ID[p["id"]]

    # Tự động gom tag theo nhóm Taxonomy.
    tags_by_group = {}

    for tag in tags:
        group = TAG_GROUP.get(tag)

        if group is not None:
            tags_by_group.setdefault(group, []).append(tag)

    # Tự động tạo payload cho mọi nhóm Taxonomy.
    # Ví dụ: ambiance, audience, feature, style...
    taxonomy_payload = {
        group: tags_by_group.get(group, [])
        for group in TAXONOMY
    }

    return {
        **p,
        "location": {
            "lat": p["latitude"],
            "lon": p["longitude"],
        },

        # Các nhóm tag được sinh tự động từ TAXONOMY.
        **taxonomy_payload,

        # Giữ trường cũ để không ảnh hưởng code tìm kiếm.
        "tags": tags,
       
        "tag_source": TAG_SOURCE_BY_ID[p["id"]],
        "tag_version": TAG_VERSION,

        "price_min": pmin,
        "price_max": pmax,
        "district": parse_district(p.get("address")),
        "text_hash": h,
    }


def ensure_collection():
    if client.collection_exists(COLLECTION):
        print("Dùng lại collection có sẵn:", client.count(COLLECTION, exact=True).count, "điểm")
        return
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={"dense": models.VectorParams(size=EMBED_DIM, distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )
    client.create_payload_index(COLLECTION, "category", models.PayloadSchemaType.KEYWORD)
    client.create_payload_index(COLLECTION, "tags", models.PayloadSchemaType.KEYWORD)
    client.create_payload_index(COLLECTION, "location", models.PayloadSchemaType.GEO)
    client.create_payload_index(COLLECTION, "price_min", models.PayloadSchemaType.INTEGER)
    client.create_payload_index(COLLECTION, "price_max", models.PayloadSchemaType.INTEGER)
    client.create_payload_index(COLLECTION, "district", models.PayloadSchemaType.KEYWORD)
    print("Đã tạo collection mới")


def place_to_text(place: dict, tags=()) -> str:
    parts = [
        f"{clean_text(place.get('name'))} là {CATEGORY_VI.get(place.get('category'), 'địa điểm')}",
        f"Địa chỉ: {clean_text(place.get('address'))}",
        f"Mô tả: {clean_text(place.get('description'))}",
    ]
    # if clean_text(place.get("opening_hours")):
    #     parts.append(f"Giờ mở cửa: {clean_text(place['opening_hours'])}")
    # if clean_text(place.get("price_range")):
    #     parts.append(f"Mức giá: {clean_text(place['price_range'])}")
    if tags:
        parts.append("Đặc điểm phù hợp: " + ", ".join(TAG_VI[t] for t in tags if t in TAG_VI))
    return ". ".join(parts) + "."


def ingest_places(place_list):
    embedded = skipped = 0
    for batch in batched(place_list, BATCH):
        texts = {p["id"]: place_to_text(p, PLACE_TAGS_BY_ID[p["id"]]) for p in batch}
        hashes = {pid: text_hash(t) for pid, t in texts.items()}
        old = existing_hashes([point_id(p["id"]) for p in batch])

        changed = [p for p in batch if old.get(point_id(p["id"])) != hashes[p["id"]]]
        same = [p for p in batch if old.get(point_id(p["id"])) == hashes[p["id"]]]

        # văn bản không đổi: giữ vector, chỉ cập nhật payload (ảnh, tọa độ, giá...)
        for p in same:
            client.overwrite_payload(
                COLLECTION,
                payload=build_payload(p, hashes[p["id"]]),
                points=[point_id(p["id"])],
                wait=True,
            )

        # văn bản đổi hoặc điểm mới: embed lại rồi upsert
        if changed:
            ts = [texts[p["id"]] for p in changed]
            dense = embed_dense(
                ts,
                batch_size=BATCH,
                task_type="RETRIEVAL_DOCUMENT",
            )
            sparse = embed_sparse_docs(ts)
            points = [
                models.PointStruct(
                    id=point_id(p["id"]),
                    vector={"dense": dv, "sparse": sv},
                    payload=build_payload(p, hashes[p["id"]]),
                )
                for p, dv, sv in zip(changed, dense, sparse)
            ]
            client.upsert(COLLECTION, points=points, wait=True)

        embedded += len(changed)
        skipped += len(same)

    print(f"  embed mới/đổi: {embedded} | không đổi (bỏ qua embed): {skipped}")
    return embedded + skipped

# def sync_places(place_list):
#     if not place_list:
#         raise RuntimeError("MySQL không trả về dòng nào hợp lệ, huỷ đồng bộ để tránh xoá hết Qdrant.")

#     ensure_collection()

#     PLACE_TAGS_BY_ID.clear()
#     TAG_SOURCE_BY_ID.clear()
#     for p in place_list:
#         ev = rule_tags_with_evidence(clean_text(p["description"]))
#         tags = sorted(ev)
#         errs = validate_tags(tags)
#         if errs:
#             print("LỖI NHÃN", p["id"], errs)
#         PLACE_TAGS_BY_ID[p["id"]] = tags
#         TAG_SOURCE_BY_ID[p["id"]] = {t: "rule" for t in tags}

#     n = ingest_places(place_list)

#     # Xoá điểm không còn trong MySQL
#     keep = {point_id(p["id"]) for p in place_list}
#     existing, offset = set(), None
#     while True:
#         pts, offset = client.scroll(COLLECTION, limit=256, offset=offset, with_payload=False)
#         existing |= {str(pt.id) for pt in pts}
#         if offset is None:
#             break
#     stale = list(existing - keep)
#     if stale:
#         client.delete(COLLECTION, points_selector=models.PointIdsList(points=stale), wait=True)
#     print(f"Đã upsert {n}, xoá {len(stale)} điểm cũ")


def sync_places(place_list):
    if not place_list:
        raise RuntimeError(
            "MySQL không trả về dòng nào hợp lệ, "
            "huỷ đồng bộ để tránh xoá hết Qdrant."
        )

    ensure_collection()

    PLACE_TAGS_BY_ID.clear()
    TAG_SOURCE_BY_ID.clear()

    for p in place_list:
        description = clean_text(p.get("description"))

        # BƯỚC 1: Dùng regex nhận diện tag trước.
        rule_evidence = rule_tags_with_evidence(description)
        rule_tags = set(rule_evidence.keys())

        # BƯỚC 2: Gemini đề xuất tag bổ sung.
        # Chỉ chọn tag thuộc taxonomy và phù hợp category.
        ai_tags = suggest_tags(
            text=description,
            existing_tags=sorted(rule_tags),
            allowed_tags=sorted(ALLOWED_TAGS),
            category=p.get("category"),
        )

        # BƯỚC 3: Gộp tag regex và AI, loại trùng.
        tags = sorted(rule_tags | set(ai_tags))

        # BƯỚC 4: Kiểm tra tính hợp lệ của tag.
        errs = validate_tags(tags)
        if errs:
            print("LỖI NHÃN", p["id"], errs)

        # Lưu tag để build_payload() và place_to_text() sử dụng.
        PLACE_TAGS_BY_ID[p["id"]] = tags

        # Ghi rõ nguồn tạo ra từng tag.
        tag_sources = {
            tag: "rule"
            for tag in rule_tags
        }

        for tag in ai_tags:
            # Ưu tiên nguồn rule nếu tag đã được rule nhận diện.
            tag_sources.setdefault(tag, "ai")

        TAG_SOURCE_BY_ID[p["id"]] = tag_sources

        print(
            f"[TAG] {p.get('name', p['id'])}: "
            f"rule={len(rule_tags)}, "
            f"ai={len(set(ai_tags) - rule_tags)}, "
            f"total={len(tags)}"
        )

    # BƯỚC 5: Embedding và cập nhật payload lên Qdrant.
    n = ingest_places(place_list)

    # BƯỚC 6: Xoá các điểm không còn trong MySQL.
    keep = {point_id(p["id"]) for p in place_list}
    existing, offset = set(), None

    while True:
        pts, offset = client.scroll(
            COLLECTION,
            limit=256,
            offset=offset,
            with_payload=False,
        )
        existing.update(str(pt.id) for pt in pts)

        if offset is None:
            break

    stale = list(existing - keep)

    if stale:
        client.delete(
            COLLECTION,
            points_selector=models.PointIdsList(points=stale),
            wait=True,
        )

    print(f"Đã upsert {n}, xoá {len(stale)} điểm cũ")


def main():
    """Demo văn bản hoặc chạy trạng thái/đồng bộ Qdrant bằng cờ tường minh."""
    import argparse

    parser = argparse.ArgumentParser(description="Qdrant indexing example")
    parser.add_argument("--status", action="store_true", help="show collection count")
    parser.add_argument("--sync", action="store_true", help="read MySQL and sync all points")
    args = parser.parse_args()
    if args.status:
        print("Collection:", COLLECTION, "points:", client.count(COLLECTION, exact=True).count)
    elif args.sync:
        from database.mysql import load_places

        sync_places(load_places())
    else:
        sample = {"name": "Khách sạn mẫu", "category": "cat-hotel", "address": "Tây Hồ, Hà Nội", "description": "Yên tĩnh"}
        print(place_to_text(sample, tags=["quiet"]))
        print("Ví dụ kiểm tra Qdrant: python -m indexing.qdrant --status")


if __name__ == "__main__":
    main()
