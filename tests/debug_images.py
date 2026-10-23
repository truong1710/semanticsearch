import json
import os
from contextlib import closing

import pymysql
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

STOPOVER_TABLE = os.getenv("STOPOVER_TABLE", "stopover_test")
COLLECTION = "places_test"          # đổi đúng tên collection bạn đang dùng

SQL_PLACES = f"""
SELECT p.stopover_id,
       p.stopover_name,
       COALESCE(
           (SELECT JSON_ARRAYAGG(i.image_url)
            FROM stopover_image i
            WHERE i.stopover_id = p.stopover_id),
           JSON_ARRAY()
       ) AS image_urls
FROM {STOPOVER_TABLE} p
LIMIT 10
"""


def get_conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3312")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "travel_app"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


print("=== 1. TRONG MYSQL ===")
with closing(get_conn()) as conn, conn.cursor() as cur:
    cur.execute(SQL_PLACES)
    rows = cur.fetchall()

mysql_imgs = {}
for r in rows:
    raw = r["image_urls"]
    n = len(json.loads(raw)) if isinstance(raw, str) else len(raw or [])
    mysql_imgs[r["stopover_id"]] = n
    print(r["stopover_name"], "|", type(raw).__name__, "|", n, "ảnh")


print("\n=== 2. TRONG QDRANT ===")
client = QdrantClient(url="http://localhost:6333")
print("Các collection:", [c.name for c in client.get_collections().collections])
print("Tổng point:", client.count(COLLECTION).count)

points, _ = client.scroll(COLLECTION, limit=10, with_payload=True, with_vectors=False)
for p in points:
    imgs = p.payload.get("image_urls")
    print(p.payload.get("name"), "|", type(imgs).__name__, "|",
          len(imgs) if isinstance(imgs, list) else imgs)