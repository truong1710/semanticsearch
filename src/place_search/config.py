import os
from dotenv import load_dotenv

load_dotenv()

# ---------- Qdrant / model ----------
# COLLECTION = "places_demo"

COLLECTION = os.getenv("COLLECTION", "places_demo")
STOPOVER_TABLE = os.getenv("STOPOVER_TABLE", "stopover")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBED_DIM = 384
BATCH = 16
TAG_VERSION = "taxonomy-v2"

# ---------- Ngưỡng tìm kiếm ----------
CATEGORY_THR = 0.55
CATEGORY_MARGIN = 0.05
TAG_THR = 0.75
TAG_BOOST = 0.15
CANDIDATE_MULT = 4

# ---------- MySQL ----------
# Thông tin lấy từ file .env, không có giá trị mặc định cho mật khẩu
DB_CONFIG = dict(
    host=os.environ["DB_HOST"],
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    database=os.environ["DB_NAME"],
    charset="utf8mb4",
)
# cursorclass sẽ truyền trong db.py khi gọi pymysql.connect

# SQL_PLACES = """
# SELECT p.stopover_id,
#        p.stopover_name,
#        p.address,
#        p.description,
#        p.is_active + 0 AS is_active,
#        p.latitude,
#        p.longitude,
#        p.opening_hours,
#        p.price_range,
#        p.status,
#        p.user_id,
#        p.website,
#        p.category_id
# FROM stopover p
# WHERE p.category_id IS NOT NULL
#   AND p.category_id <> ''
# """


SQL_PLACES = f"""
SELECT p.stopover_id,
       p.stopover_name,
       p.address,
       p.description,
       p.is_active + 0 AS is_active,
       p.latitude,
       p.longitude,
       p.opening_hours,
       p.price_range,
       p.status,
       p.user_id,
       p.website,
       p.category_id
FROM {STOPOVER_TABLE} p
WHERE p.category_id IS NOT NULL
  AND p.category_id <> ''
"""
ALLOWED_STATUS = None   # ví dụ: {"APPROVED"}