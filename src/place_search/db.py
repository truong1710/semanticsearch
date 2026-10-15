import pymysql

from .config import ALLOWED_STATUS, DB_CONFIG, SQL_PLACES
from .taxonomy import CATEGORY_VI

CATEGORY_ID_MAP = {
    "cat-hotel": "cat-hotel",
    "cat-cafe": "cat-cafe",
    "cat-park": "cat-park",
    "cat-culture": "cat-culture",
    "cat-restaurant": "cat-restaurant",
}


def _s(v):
    return "" if v is None else str(v)


def _bit_to_int(v):
    if v is None:
        return 0
    if isinstance(v, bytes):
        return int.from_bytes(v, byteorder="big")
    return int(v)


def load_places(sql=SQL_PLACES):
    rows, skipped = [], []
    conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.SSDictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            for r in cur:
                pid = r["stopover_id"]

                try:
                    lat = float(r["latitude"])
                    lon = float(r["longitude"])
                except (TypeError, ValueError):
                    skipped.append((pid, "thiếu tọa độ"))
                    continue

                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    skipped.append((pid, "tọa độ ngoài phạm vi"))
                    continue

                category_id = _s(r.get("category_id")).strip()
                cat = CATEGORY_ID_MAP.get(category_id)

                if category_id and cat is None:
                    skipped.append((pid, f"category_id chưa được ánh xạ: {category_id}"))
                    continue

                if cat is not None and cat not in CATEGORY_VI:
                    skipped.append((pid, f"category không hợp lệ: {cat}"))
                    continue

                if ALLOWED_STATUS is not None and r.get("status") not in ALLOWED_STATUS:
                    skipped.append((pid, f"status: {r.get('status')}"))
                    continue

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
                })
    finally:
        conn.close()

    print(f"Đọc {len(rows)} địa điểm, bỏ qua {len(skipped)}", skipped[:10])
    return rows