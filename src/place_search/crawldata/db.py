
import json
import os
import math
import uuid
import re
from pathlib import Path
from contextlib import closing

import pymysql
from dotenv import load_dotenv

load_dotenv()


# =====================================================
# 1. CẤU HÌNH MYSQL
# =====================================================

DB_HOST = os.getenv("DB_HOST", "localhost")

# Nếu MySQL Docker của bạn ánh xạ cổng 3312 -> 3306,
# dùng 3312. Có thể ghi đè bằng biến DB_PORT trong .env.
DB_PORT = int(os.getenv("DB_PORT", "3312"))

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "travel_app")
STOPOVER_TABLE = os.getenv("STOPOVER_TABLE", "stopover_test")

# Phải là user_id hợp lệ đã tồn tại trong hệ thống của bạn.
USER_ID = os.getenv("USER_ID", "").strip()

# File JSON nằm cùng thư mục với file Python này.
JSON_PATH = Path(__file__).resolve().with_name("places_new.json")


# Kiểm tra tên bảng để tránh chèn tên bảng không hợp lệ vào SQL.
if not re.fullmatch(r"[A-Za-z0-9_]+", STOPOVER_TABLE):
    raise ValueError("Tên bảng MySQL không hợp lệ.")


def get_connection():
    """Kết nối tới MySQL."""

    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


# =====================================================
# 2. CHUẨN HÓA DỮ LIỆU
# =====================================================

def _text(value):
    """Chuyển dữ liệu về chuỗi phù hợp để lưu vào MySQL."""

    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        return value if value else None

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    return str(value)


def _coordinate(value):
    """
    Chuyển tọa độ thành số thực.

    Trả về None nếu tọa độ thiếu hoặc không hợp lệ.
    """

    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def _to_row(place):
    """
    Chuyển một bản ghi JSON thành dữ liệu cho bảng stopover_test.

    name       -> stopover_name
    source_url -> website

    stopover_id được tạo ổn định từ tên và địa chỉ:
    cùng một khách sạn sẽ có cùng ID khi chạy lại.
    """

    name = _text(place.get("name"))
    address = _text(place.get("address"))

    # Tạo ID ổn định, tránh sinh ID mới mỗi lần chạy.
    identity = f"{name.casefold()}|{address.casefold()}"
    stopover_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, identity)
    )

    return {
        "stopover_id": stopover_id,
        "stopover_name": name,
        "description": _text(place.get("description")),
        "address": address,
        "latitude": _coordinate(place.get("latitude")),
        "longitude": _coordinate(place.get("longitude")),
        "opening_hours": _text(place.get("opening_hours")),
        "price_range": _text(place.get("price_range")),
        "website": _text(place.get("source_url")),
        "category_id": _text(place.get("category_id")),
        "user_id": USER_ID,
        "image_urls": place.get("image_urls") or []
    }


# =====================================================
# 3. ĐIỀU KIỆN LỌC KHÁCH SẠN
# =====================================================

def _is_valid_place(place):
    """
    Chỉ nhận khách sạn có:
    - Tên
    - Địa chỉ
    - Vĩ độ hợp lệ
    - Kinh độ hợp lệ

    Các bản ghi không đạt điều kiện sẽ bị bỏ qua.
    """

    name = _text(place.get("name"))
    address = _text(place.get("address"))

    latitude = _coordinate(place.get("latitude"))
    longitude = _coordinate(place.get("longitude"))

    if not name:
        return False, "Thiếu tên khách sạn"

    if not address:
        return False, "Thiếu địa chỉ"

    if latitude is None or longitude is None:
        return False, "Thiếu tọa độ hoặc tọa độ không hợp lệ"

    if not (-90 <= latitude <= 90):
        return False, "Vĩ độ nằm ngoài phạm vi hợp lệ"

    if not (-180 <= longitude <= 180):
        return False, "Kinh độ nằm ngoài phạm vi hợp lệ"

    # Giới hạn độ dài theo cấu trúc bảng MySQL.
    if len(name) > 255:
        return False, "Tên khách sạn dài hơn 255 ký tự"

    if len(address) > 500:
        return False, "Địa chỉ dài hơn 500 ký tự"

    if len(_text(place.get("opening_hours")) or "") > 255:
        return False, "Giờ mở cửa dài hơn 255 ký tự"

    if len(_text(place.get("price_range")) or "") > 100:
        return False, "Khoảng giá dài hơn 100 ký tự"

    if len(_text(place.get("source_url")) or "") > 255:
        return False, "URL nguồn dài hơn 255 ký tự"

    return True, None


# =====================================================
# 4. UPSERT MYSQL
# =====================================================

UPSERT = f"""
INSERT INTO `{STOPOVER_TABLE}` (
    stopover_id,
    stopover_name,
    description,
    address,
    latitude,
    longitude,
    opening_hours,
    price_range,
    website,
    category_id,
    user_id
)
VALUES (
    %(stopover_id)s,
    %(stopover_name)s,
    %(description)s,
    %(address)s,
    %(latitude)s,
    %(longitude)s,
    %(opening_hours)s,
    %(price_range)s,
    %(website)s,
    %(category_id)s,
    %(user_id)s
)
ON DUPLICATE KEY UPDATE
    stopover_name = VALUES(stopover_name),
    description = COALESCE(VALUES(description), description),
    address = COALESCE(VALUES(address), address),
    latitude = VALUES(latitude),
    longitude = VALUES(longitude),
    opening_hours = COALESCE(VALUES(opening_hours), opening_hours),
    price_range = COALESCE(VALUES(price_range), price_range),
    website = COALESCE(VALUES(website), website),
    category_id = COALESCE(VALUES(category_id), category_id)
"""

# SQL lưu từng ảnh của khách sạn
UPSERT_IMAGE = """
INSERT INTO stopover_image (
    stopover_id,
    image_url,
    is_primary,
    display_order
)
VALUES (%s, %s, %s, %s)
"""



def upsert_places(places, db_path=None):
    """
    Thêm/cập nhật khách sạn vào MySQL
    và lưu nhiều ảnh vào bảng stopover_image.
    """

    valid_rows = []
    skipped = 0

    # 1. Lọc dữ liệu hợp lệ
    for index, place in enumerate(places, start=1):
        is_valid, reason = _is_valid_place(place)

        if not is_valid:
            skipped += 1
            print(
                f"[BỎ QUA] Bản ghi {index}: "
                f"{place.get('name', 'Không có tên')} - {reason}"
            )
            continue

        valid_rows.append(_to_row(place))

    print(f"\nTổng bản ghi JSON: {len(places)}")
    print(f"Bản ghi không đạt điều kiện: {skipped}")
    print(f"Bản ghi đủ điều kiện: {len(valid_rows)}")

    if not valid_rows:
        print("Không có khách sạn hợp lệ để thêm.")
        return 0

    # 2. Kiểm tra USER_ID
    if not USER_ID:
        raise ValueError(
            "Bạn chưa cấu hình USER_ID. "
            "Hãy thêm USER_ID=<user_id hợp lệ> vào file .env."
        )

    # 3. Ghi khách sạn và ảnh vào MySQL
    with closing(get_connection()) as connection:
        try:
            with connection.cursor() as cursor:

                for row in valid_rows:

                    # Bước 3.1: Thêm hoặc cập nhật khách sạn
                    cursor.execute(UPSERT, row)

                    stopover_id = row["stopover_id"]

                    # Bước 3.2: Lấy danh sách ảnh từ JSON
                    image_urls = row.get("image_urls") or []

                    # Chỉ nhận URL dạng chuỗi, bỏ URL trống
                    image_urls = [
                        url.strip()
                        for url in image_urls
                        if isinstance(url, str) and url.strip()
                    ]

                    # Loại URL trùng nhau, giữ nguyên thứ tự
                    image_urls = list(dict.fromkeys(image_urls))

                    # Bước 3.3: Xóa ảnh cũ của khách sạn này
                    cursor.execute(
                        """
                        DELETE FROM stopover_image
                        WHERE stopover_id = %s
                        """,
                        (stopover_id,)
                    )

                    # Bước 3.4: Chuẩn bị danh sách ảnh mới
                    image_rows = [
                        (
                            stopover_id,
                            image_url,
                            index == 0,  # Ảnh đầu tiên làm ảnh đại diện
                            index + 1    # Thứ tự ảnh bắt đầu từ 1
                        )
                        for index, image_url in enumerate(image_urls)
                    ]

                    # Bước 3.5: Lưu nhiều ảnh cùng lúc
                    if image_rows:
                        cursor.executemany(
                            UPSERT_IMAGE,
                            image_rows
                        )

                    print(
                        f"[OK] {row['stopover_name']}: "
                        f"{len(image_rows)} ảnh"
                    )

            # Chỉ xác nhận khi tất cả thao tác thành công
            connection.commit()

        except Exception:
            # Có lỗi thì hoàn tác cả thông tin khách sạn và ảnh
            connection.rollback()
            raise

    print(f"\nĐã xử lý {len(valid_rows)} khách sạn.")
    print(f"Đã bỏ qua {skipped} bản ghi không hợp lệ.")
    print("Số khách sạn gồm cả bản ghi mới và bản ghi cập nhật.")

    return len(valid_rows)



# =====================================================
# 5. ĐỌC DỮ LIỆU JSON
# =====================================================

def load_places_json(json_path=JSON_PATH):
    """Đọc danh sách khách sạn từ file JSON."""

    json_path = Path(json_path)

    if not json_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file JSON: {json_path}"
        )

    with json_path.open("r", encoding="utf-8") as file:
        places = json.load(file)

    if not isinstance(places, list):
        raise ValueError("JSON phải chứa một danh sách các bản ghi.")

    return places


# =====================================================
# 6. ĐỌC DỮ LIỆU ĐỂ KIỂM TRA
# =====================================================

def list_places(limit=20, db_path=None):
    """Lấy danh sách địa điểm để kiểm tra."""

    limit = max(1, int(limit))

    sql = f"""
        SELECT *
        FROM `{STOPOVER_TABLE}`
        ORDER BY stopover_name
        LIMIT %s
    """

    with closing(get_connection()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (limit,))
            return cursor.fetchall()


# =====================================================
# 7. KIỂM TRA KẾT NỐI MYSQL
# =====================================================

def test_connection():
    """Kiểm tra kết nối và tên database."""

    with closing(get_connection()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS db_name")
            return cursor.fetchone()


# =====================================================
# 8. CHẠY CHƯƠNG TRÌNH
# =====================================================

if __name__ == "__main__":
    try:
        print("1. Kiểm tra kết nối MySQL...")
        print(test_connection())
        print("Kết nối MySQL thành công.\n")

        print("2. Đọc dữ liệu JSON...")
        places = load_places_json()
        print(f"Đọc được {len(places)} bản ghi.\n")

        print("3. Lọc và ghi dữ liệu vào MySQL...")
        upsert_places(places)

        print("\n4. Kiểm tra dữ liệu trong bảng...")
        saved_places = list_places(limit=10)

        for place in saved_places:
            print(
                place["stopover_name"],
                "|",
                place["latitude"],
                "|",
                place["longitude"],
            )

    except Exception as error:
        print(f"\nLỖI: {error}")
