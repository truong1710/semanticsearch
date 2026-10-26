import json
import pymysql

from config import ALLOWED_STATUS, DB_CONFIG, SQL_PLACES
from common.taxonomy import CATEGORY_VI


CATEGORY_ID_MAP = {
    "cat-hotel": "cat-hotel",
    "cat-cafe": "cat-cafe",
    "cat-park": "cat-park",
    "cat-culture": "cat-culture",
    "cat-restaurant": "cat-restaurant",
}


def _s(v):
    if v is None:
        return ""
    return str(v)


def _bit_to_int(v):
    if v is None:
        return 0
    if isinstance(v, bytes):
        return int.from_bytes(v, byteorder="big")
    return int(v)


def _parse_image_urls(value):
    """Chuyển dữ liệu image_urls từ MySQL thành list URL."""
    if value is None:
        return []

    # Một số kiểu cursor có thể trả về bytes.
    if isinstance(value, bytes):
        value = value.decode("utf-8")

    # MySQL JSON thường được trả về dưới dạng chuỗi JSON.
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []

    # Chỉ chấp nhận danh sách URL.
    if not isinstance(value, list):
        return []

    # Loại bỏ giá trị rỗng, đồng thời giữ nguyên thứ tự.
    image_urls = []
    seen = set()

    for url in value:
        if not isinstance(url, str):
            continue

        url = url.strip()

        if url and url not in seen:
            image_urls.append(url)
            seen.add(url)

    return image_urls


def load_places(sql=SQL_PLACES):
    rows, skipped = [], []

    conn = pymysql.connect(
        **DB_CONFIG,
        cursorclass=pymysql.cursors.SSDictCursor
    )

    try:
        with conn.cursor() as cur:
            cur.execute(sql)

            for r in cur:
                pid = r["stopover_id"]

                # 1. Kiểm tra tọa độ
                try:
                    lat = float(r["latitude"])
                    lon = float(r["longitude"])
                except (TypeError, ValueError):
                    skipped.append((pid, "thiếu tọa độ"))
                    continue

                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    skipped.append((pid, "tọa độ ngoài phạm vi"))
                    continue

                # 2. Kiểm tra danh mục
                category_id = _s(r.get("category_id")).strip()
                cat = CATEGORY_ID_MAP.get(category_id)

                if category_id and cat is None:
                    skipped.append(
                        (pid, f"category_id chưa được ánh xạ: {category_id}")
                    )
                    continue

                if cat is not None and cat not in CATEGORY_VI:
                    skipped.append(
                        (pid, f"category không hợp lệ: {cat}")
                    )
                    continue

                # 3. Kiểm tra trạng thái
                if (
                    ALLOWED_STATUS is not None
                    and r.get("status") not in ALLOWED_STATUS
                ):
                    skipped.append((pid, f"status: {r.get('status')}"))
                    continue

                # 4. Đọc danh sách ảnh từ cột image_urls trong SQL_PLACES
                image_urls = _parse_image_urls(r.get("image_urls"))

                # 5. Đưa địa điểm và ảnh vào cùng một bản ghi
                rows.append({
                    "id": str(pid),
                    "name": _s(r["stopover_name"]),
                    "address": _s(r["address"]),
                    "description": _s(r["description"]),
                    "is_active": _bit_to_int(r["is_active"]),
                    "latitude": lat,
                    "longitude": lon,
                    "opening_hours": _s(r["opening_hours"]),
                    "price_range": _s(r["price_range"]),
                    "status": _s(r["status"]),
                    "created_by": _s(r["user_id"]),
                    "url": _s(r["website"]),
                    "category_id": category_id,
                    "category": cat,
                    "image_urls": image_urls,
                })

    finally:
        conn.close()

    print(
        f"Đọc {len(rows)} địa điểm, "
        f"bỏ qua {len(skipped)} địa điểm"
    )

    print(
        f"Tổng số ảnh: {sum(len(place['image_urls']) for place in rows)}"
    )

    print("Lý do bỏ qua:", skipped[:10])

    return rows


def main():
    """Demo SQL mặc định; ``--connect`` đọc dữ liệu trực tiếp từ MySQL."""
    import argparse

    parser = argparse.ArgumentParser(description="Place MySQL reader")
    parser.add_argument("--connect", action="store_true", help="load places from configured MySQL")
    args = parser.parse_args()
    if args.connect:
        print(f"Đọc được {len(load_places())} địa điểm")
    else:
        print("SQL source table:", SQL_PLACES.split("FROM", 1)[1].strip().split()[0])
        print("Ví dụ đọc thật: python -m database.mysql --connect")


if __name__ == "__main__":
    main()
