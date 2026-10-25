
import json
import os
import re
import unicodedata
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv


# ==================================================
# 1. CẤU HÌNH
# ==================================================
PROJECT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_DIR / ".env")

JSON_PATH = PROJECT_DIR / "data" / "places.json"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3312")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME", "travel_app"),
}

TABLE_NAME = os.getenv("STOPOVER_TABLE", "stopover_test")

# Chỉ cho phép tên bảng hợp lệ để tránh SQL injection
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", TABLE_NAME):
    raise ValueError("Tên bảng trong .env không hợp lệ!")

if not DB_CONFIG["password"]:
    raise ValueError("Không tìm thấy DB_PASSWORD trong file .env!")

if not JSON_PATH.exists():
    raise FileNotFoundError(f"Không tìm thấy file: {JSON_PATH}")


# ==================================================
# 2. CHUẨN HÓA TÊN VÀ ĐỊA CHỈ
# ==================================================

def normalize_text(value):
    """
    Chuẩn hóa văn bản để so sánh:
    - Chữ thường
    - Bỏ dấu tiếng Việt
    - Bỏ dấu câu
    - Gộp khoảng trắng
    """

    if value is None:
        return ""

    value = unicodedata.normalize("NFC", str(value))
    value = value.lower().strip()

    # Tách dấu khỏi ký tự, sau đó loại bỏ dấu
    value = unicodedata.normalize("NFD", value)
    value = "".join(
        char
        for char in value
        if unicodedata.category(char) != "Mn"
    )

    # Chuẩn hóa dấu câu và khoảng trắng
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value


# ==================================================
# 3. ĐỌC DỮ LIỆU CRAWL TỪ JSON
# ==================================================

with open(JSON_PATH, "r", encoding="utf-8") as file:
    crawled_places = json.load(file)

if not isinstance(crawled_places, list):
    raise ValueError("Dữ liệu JSON phải là một danh sách!")

print("=" * 50)
print("KIỂM TRA DỮ LIỆU CRAWL")
print("=" * 50)
print(f"File JSON: {JSON_PATH}")
print(f"Số bản ghi crawl: {len(crawled_places)}")


# ==================================================
# 4. LẤY DỮ LIỆU TỪ MYSQL MỘT LẦN
# ==================================================

conn = None
cursor = None

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Lấy tên và địa chỉ từ bảng được cấu hình trong .env
    sql = f"""
        SELECT stopover_name, address
        FROM `{TABLE_NAME}`
    """

    cursor.execute(sql)
    db_places = cursor.fetchall()

finally:
    if cursor is not None:
        cursor.close()

    if conn is not None and conn.is_connected():
        conn.close()


print(f"Database: {DB_CONFIG['database']}")
print(f"Bảng kiểm tra: {TABLE_NAME}")
print(f"Số bản ghi trong DB: {len(db_places)}")


# ==================================================
# 5. TẠO TẬP HỢP ĐỂ TRA CỨU NHANH
# ==================================================

db_keys = set()
db_names = set()

for name, address in db_places:
    normalized_name = normalize_text(name)
    normalized_address = normalize_text(address)

    if normalized_name:
        db_names.add(normalized_name)

    # Chỉ tạo khóa đầy đủ khi có cả tên và địa chỉ
    if normalized_name and normalized_address:
        db_keys.add((normalized_name, normalized_address))


# ==================================================
# 6. KIỂM TRA TRÙNG
# ==================================================

new_places = []
duplicate_places = []
needs_review = []

# Các khóa đã gặp trong file JSON
seen_json_keys = set()

# Các tên đã gặp trong file JSON
seen_json_names = set()

for place in crawled_places:

    # Bỏ qua bản ghi không phải object JSON
    if not isinstance(place, dict):
        needs_review.append(place)
        continue

    name = normalize_text(place.get("name"))
    address = normalize_text(place.get("address"))

    # Không đủ tên hoặc địa chỉ để đối chiếu
    if not name or not address:
        needs_review.append(place)
        continue

    key = (name, address)

    # Trường hợp 1: Trùng tên + địa chỉ với DB
    # hoặc trùng với bản ghi JSON đã xuất hiện trước đó
    if key in db_keys or key in seen_json_keys:
        duplicate_places.append(place)

    # Trường hợp 2: Tên đã có trong DB hoặc JSON
    # nhưng địa chỉ khác nhau, cần kiểm tra thủ công
    elif name in db_names or name in seen_json_names:
        needs_review.append(place)

    # Trường hợp 3: Chưa tìm thấy dấu hiệu trùng
    else:
        new_places.append(place)

    # Ghi nhận để kiểm tra các bản ghi tiếp theo
    seen_json_keys.add(key)
    seen_json_names.add(name)


# ==================================================
# 7. LƯU KẾT QUẢ
# ==================================================

def save_json(filename, data):
    output_path = PROJECT_DIR / filename

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(f"Đã lưu {filename}: {len(data)} bản ghi")


save_json("places_new.json", new_places)
save_json("places_duplicates.json", duplicate_places)
save_json("places_needs_review.json", needs_review)


# ==================================================
# 8. TỔNG KẾT
# ==================================================

print("\n" + "=" * 50)
print("KẾT QUẢ KIỂM TRA")
print("=" * 50)

print(f"Tổng bản ghi crawl:          {len(crawled_places)}")
print(f"Tổng bản ghi trong DB:       {len(db_places)}")
print(f"Có khả năng thêm mới:        {len(new_places)}")
print(f"Trùng tên và địa chỉ:        {len(duplicate_places)}")
print(f"Cần kiểm tra thêm:           {len(needs_review)}")

print("\nCác file kết quả:")
print("1. places_new.json")
print("2. places_duplicates.json")
print("3. places_needs_review.json")

print("\nHoàn tất! Chương trình chỉ đọc DB, không INSERT hoặc UPDATE.")
