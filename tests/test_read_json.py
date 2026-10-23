
import json
from pathlib import Path

# Đường dẫn tới file JSON
file_path = Path("data/places.json")

# Đọc dữ liệu từ file
with open(file_path, "r", encoding="utf-8") as f:
    places = json.load(f)

# Kiểm tra kết quả
print("Tổng số địa điểm:", len(places))

valid_coords = [
    p for p in places
    if p.get("latitude") is not None
    and p.get("longitude") is not None
]

print("Số địa điểm có tọa độ:", len(valid_coords))
print("Số địa điểm chưa có tọa độ:", len(places) - len(valid_coords))

# In thử địa điểm đầu tiên
if places:
    print(json.dumps(places[0], ensure_ascii=False, indent=2))
