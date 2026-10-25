import hashlib

import numpy as np

from place_search.config import COLLECTION, EMBED_DIM, EMBED_MODEL, MODEL_CACHE_DIR
from place_search.embeddings import client as gemini, embed_dense, sparse_model
from place_search.store import client as qdrant, place_to_text

print("=" * 60)
print("1. CẤU HÌNH TRONG config.py")
print("=" * 60)
print("Dense model :", EMBED_MODEL)
print("Số chiều    :", EMBED_DIM)
print("Collection  :", COLLECTION)
print("Cache BM25  :", MODEL_CACHE_DIR)

print("\n" + "=" * 60)
print("2. MODEL DENSE (Gemini)")
print("=" * 60)
try:
    info = gemini.models.get(model=EMBED_MODEL)
    print("Tên đầy đủ     :", info.name)
    print("Hỗ trợ         :", info.supported_actions)
    print("Giới hạn input :", getattr(info, "input_token_limit", "?"), "token")
except Exception as e:
    print("Không lấy được thông tin model:", e)

vec = embed_dense(["thử"])[0]
print("Gọi thử embed  : OK, ra vector", len(vec), "chiều")

print("\nCác model embedding khác tài khoản này đang gọi được:")
try:
    for m in gemini.models.list():
        if "embedContent" in (m.supported_actions or []):
            print("  -", m.name)
except Exception as e:
    print("  (không liệt kê được:", e, ")")

print("\n" + "=" * 60)
print("3. MODEL SPARSE (BM25 / FastEmbed)")
print("=" * 60)
print("Model:", getattr(sparse_model, "model_name", "Qdrant/bm25"))
print("Loại :", type(sparse_model).__name__)

print("\n" + "=" * 60)
print("4. COLLECTION TRONG QDRANT")
print("=" * 60)
col = qdrant.get_collection(COLLECTION)
print("Số điểm        :", col.points_count)
for name, p in (col.config.params.vectors or {}).items():
    print(f"Vector {name!r:8}: {p.size} chiều, {p.distance}")
for name in (col.config.params.sparse_vectors or {}):
    print(f"Sparse {name!r:8}: có")

print("\n" + "=" * 60)
print("5. VECTOR ĐANG LƯU CÓ ĐÚNG MODEL HIỆN TẠI KHÔNG?")
print("=" * 60)
pts, _ = qdrant.scroll(COLLECTION, limit=1, with_payload=True, with_vectors=True)
payload = pts[0].payload
stored = np.asarray(pts[0].vector["dense"], dtype=np.float32)
text = place_to_text(payload, payload.get("tags") or [])

expected = hashlib.sha1(f"{EMBED_MODEL}|{EMBED_DIM}\n{text}".encode("utf-8")).hexdigest()
print("text_hash khớp model hiện tại:", expected == payload.get("text_hash"))

new = np.asarray(embed_dense([text])[0], dtype=np.float32)
cos = float(stored @ new / (np.linalg.norm(stored) * np.linalg.norm(new)))
print("cosine(vector lưu, vector embed lại):", round(cos, 4))
print("=> Đúng model" if cos > 0.99 else "=> LỆCH model, cần chạy lại sync_data.py")