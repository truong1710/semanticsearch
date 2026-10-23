import json
from pathlib import Path

from db import upsert_places

# Lấy thư mục gốc của dự án hanoi-search
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Đường dẫn tới file JSON
json_path = PROJECT_ROOT / "places_new.json"

# Đọc dữ liệu khách sạn
with open(json_path, "r", encoding="utf-8") as f:
    places = json.load(f)

print("Số bản ghi đọc từ JSON:", len(places))

# Ghi dữ liệu vào MySQL
count = upsert_places(places)

print("Số bản ghi đã xử lý:", count)