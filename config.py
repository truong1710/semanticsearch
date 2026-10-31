import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

# ---------- Qdrant / model ----------
# COLLECTION = "places_demo"

COLLECTION = os.getenv("COLLECTION", "places_demo")
STOPOVER_TABLE = os.getenv("STOPOVER_TABLE", "stopover")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768

_model_cache_path = Path(os.getenv("MODEL_CACHE_DIR", "models"))
if not _model_cache_path.is_absolute():
    _model_cache_path = PROJECT_ROOT / _model_cache_path
MODEL_CACHE_DIR = str(_model_cache_path)
BATCH = 98
EMBED_BATCH_DELAY_SECONDS = 70
TAG_VERSION = "taxonomy-v2"
_search_eval_path = Path(os.getenv("SEARCH_EVAL_FILE", "data/search_eval.json"))
SEARCH_EVAL_FILE = (
    _search_eval_path
    if _search_eval_path.is_absolute()
    else PROJECT_ROOT / _search_eval_path
)

# ---------- Ngưỡng tìm kiếm ----------
CATEGORY_THR = 0.55
CATEGORY_MARGIN = 0.05
TAG_THR = 0.75
TAG_BOOST = 0.45
CANDIDATE_MULT = 4
# Provisional cosine cutoff for search results; tune with labeled queries.
MIN_RELEVANCE_SCORE = float(os.getenv("MIN_RELEVANCE_SCORE", "0.45"))
if not -1.0 <= MIN_RELEVANCE_SCORE <= 1.0:
    raise ValueError("MIN_RELEVANCE_SCORE must be between -1 and 1.")

# ---------- MySQL ----------
# Không cần cấu hình MySQL để import package; kết nối chỉ mở khi load_places() chạy.
DB_CONFIG = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "travel_app"),
    charset="utf8mb4",
)
# cursorclass sẽ truyền trong db.py khi gọi pymysql.connect

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
       p.category_id,
       COALESCE(
           (
               SELECT JSON_ARRAYAGG(i.image_url)
               FROM stopover_image i
               WHERE i.stopover_id = p.stopover_id
           ),
           JSON_ARRAY()
       ) AS image_urls
FROM {STOPOVER_TABLE} p
WHERE p.category_id IS NOT NULL
  AND p.category_id <> ''
"""
ALLOWED_STATUS = None   # ví dụ: {"APPROVED"}


def main():
    """In cấu hình không chứa bí mật: ``python -m config``."""
    print("Project root:", PROJECT_ROOT)
    print("Qdrant:", QDRANT_URL)
    print("Collection:", COLLECTION)
    print("Embedding:", EMBED_MODEL, EMBED_DIM)
    print("Model cache:", MODEL_CACHE_DIR)


if __name__ == "__main__":
    main()
