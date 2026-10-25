import uuid
from itertools import islice

from qdrant_client import QdrantClient, models

from .config import BATCH, COLLECTION, EMBED_DIM, QDRANT_URL, TAG_VERSION
from .embeddings import embed_dense, embed_sparse_docs
from .taxonomy import CATEGORY_VI, TAG_VI, rule_tags_with_evidence, validate_tags
from .text_utils import clean_text
from .filters import parse_district, parse_price_range
client = QdrantClient(url=QDRANT_URL)
NAMESPACE = uuid.UUID("6f1c2f0e-3b7a-4c1e-9d55-2b8a1f7c9e10")

# Chỉ store.py được sửa hai dict này
PLACE_TAGS_BY_ID, TAG_SOURCE_BY_ID = {}, {}

import hashlib
from .config import EMBED_MODEL




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
    return {
        **p,
        "location": {"lat": p["latitude"], "lon": p["longitude"]},
        "tags": PLACE_TAGS_BY_ID[p["id"]],
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

def sync_places(place_list):
    if not place_list:
        raise RuntimeError("MySQL không trả về dòng nào hợp lệ, huỷ đồng bộ để tránh xoá hết Qdrant.")

    ensure_collection()

    PLACE_TAGS_BY_ID.clear()
    TAG_SOURCE_BY_ID.clear()
    for p in place_list:
        ev = rule_tags_with_evidence(clean_text(p["description"]))
        tags = sorted(ev)
        errs = validate_tags(tags)
        if errs:
            print("LỖI NHÃN", p["id"], errs)
        PLACE_TAGS_BY_ID[p["id"]] = tags
        TAG_SOURCE_BY_ID[p["id"]] = {t: "rule" for t in tags}

    n = ingest_places(place_list)

    # Xoá điểm không còn trong MySQL
    keep = {point_id(p["id"]) for p in place_list}
    existing, offset = set(), None
    while True:
        pts, offset = client.scroll(COLLECTION, limit=256, offset=offset, with_payload=False)
        existing |= {str(pt.id) for pt in pts}
        if offset is None:
            break
    stale = list(existing - keep)
    if stale:
        client.delete(COLLECTION, points_selector=models.PointIdsList(points=stale), wait=True)
    print(f"Đã upsert {n}, xoá {len(stale)} điểm cũ")