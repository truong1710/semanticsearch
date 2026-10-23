import re
import time
from urllib.parse import unquote

import requests

from . import config as cfg
from .extract import coords_from_ref
from .utils import in_bounds, is_specific_address, normalize, to_float


# ------------------------------------------------------------------ ảnh
def assign_images(page):
    # Trang một địa điểm: gán hết ảnh. Trang danh sách: theo tiêu đề mục chứa ảnh, rồi theo alt / tên file.
    places, images = page["places"], page["images"]
    single = len(places) == 1
    for p in places:
        key = normalize(p["name"])
        urls = []
        if single:
            urls = [i["url"] for i in images]
        elif key:
            for img in images:                       # (a) theo tiêu đề mục
                h = normalize(img["heading"])
                if h and (key in h or (len(h) >= 6 and h in key)):
                    urls.append(img["url"])
            if not urls:                             # (b) theo alt / tên file
                slug = key.replace(" ", "-")
                for img in images:
                    if (key in normalize(img["alt"]) or key in normalize(img["title"])
                            or slug in unquote(img["url"]).lower()):
                        urls.append(img["url"])
        cap = 20 if single else cfg.MAX_IMAGES_PER_PLACE
        p["image_urls"] = list(dict.fromkeys(urls))[:cap]
    return page


# ------------------------------------------------------------------ tọa độ
def match_ref(place, refs, single):
    if not refs:
        return None
    key = normalize(place.get("name"))
    addr = normalize(place.get("address"))
    for r in refs:                                   # chữ của link trùng địa chỉ
        t = normalize(r["text"])
        if addr and len(t) >= 6 and (addr in t or t in addr):
            return r
    for r in refs:                                   # link nằm dưới tiêu đề của chính địa điểm
        h = normalize(r["heading"])
        if h and key and (key in h or (len(h) >= 6 and h in key)):
            return r
    if single:
        embeds = [r for r in refs if r["kind"] == "embed"]
        return (embeds or refs)[0]
    return None


# Kết quả geocode là cả một khu vực/thành phố (không phải một điểm cụ thể) thì bỏ
GENERIC_GEO_TYPES = {"administrative", "city", "town", "village", "hamlet", "suburb", "quarter",
                     "neighbourhood", "city_block", "borough", "district", "municipality",
                     "county", "state", "province", "region", "country"}


# def geocode(query):
#     params = {"q": query, "format": "json", "limit": 1}
#     if cfg.COUNTRY_CODE:
#         params["countrycodes"] = cfg.COUNTRY_CODE
#     try:
#         r = requests.get(
#             "https://nominatim.openstreetmap.org/search",
#             params=params,
#             headers={"User-Agent": "place-crawler-demo"},
#             timeout=20,
#         )
#         data = r.json()
#         if data:
#             d = data[0]
#             if d.get("class") == "boundary" or d.get("type") in GENERIC_GEO_TYPES:
#                 return None, None
#             return float(d["lat"]), float(d["lon"])
#     except (requests.RequestException, ValueError, KeyError):
#         pass
#     return None, None



def geocode(query):
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "addressdetails": 1,
    }

    if cfg.COUNTRY_CODE:
        params["countrycodes"] = cfg.COUNTRY_CODE

    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers={
                "User-Agent": "HanoiPlaceCrawler/1.0 (educational project)"
            },
            timeout=20,
        )

        # In mã HTTP để biết server có phản hồi bình thường không.
        print(f"[GEOCODE HTTP] {r.status_code}")
        print(f"[GEOCODE URL] {r.url}")

        # Nếu HTTP 403, 429, 500... thì hiện lỗi thay vì bỏ qua.
        r.raise_for_status()

        data = r.json()

        # Không tìm thấy kết quả.
        if not data:
            print("[GEOCODE] Không tìm thấy kết quả.")
            return None, None

        d = data[0]
        print(
            f"[GEOCODE RESULT] "
            f"display_name={d.get('display_name')!r}, "
            f"class={d.get('class')!r}, "
            f"type={d.get('type')!r}"
        )

        if (
            d.get("class") == "boundary"
            or d.get("type") in GENERIC_GEO_TYPES
        ):
            print("[GEOCODE] Bị bộ lọc loại vì là khu vực chung.")
            return None, None

        return float(d["lat"]), float(d["lon"])

    except requests.RequestException as e:
        print(f"[GEOCODE NETWORK/HTTP ERROR] {e}")
    except (ValueError, KeyError) as e:
        print(f"[GEOCODE DATA ERROR] {e}")

    return None, None



def geocode_place(place):
    addr = re.sub(r"(?<=\D)\s*[-–]\s*(?=\D)", ", ", place.get("address") or "").strip(", ")
    name = (place.get("name") or "").strip()
    tries = []
    if addr and is_specific_address(addr):          # chỉ geocode riêng theo địa chỉ khi nó đủ cụ thể
        tries.append((addr + cfg.GEO_SUFFIX, "address"))
    if name and addr:
        tries.append((f"{name}, {addr}{cfg.GEO_SUFFIX}", "name_address"))
    if name:
        tries.append((name + cfg.GEO_SUFFIX, "name"))
    for query, tag in tries:
        lat, lng = geocode(query)

        print(f"[DEBUG] Loại truy vấn: {tag}")
        print(f"[DEBUG] Query: {query}")
        print(f"[DEBUG] Tọa độ nhận được: lat={lat}, lng={lng}")
        print(f"[DEBUG] Trong BBOX: {in_bounds(lat, lng)}")

        time.sleep(cfg.GEO_DELAY)

        if in_bounds(lat, lng):
            return lat, lng, "geocode_" + tag

    return None, None, None


def locate(place, refs, single):
    # Trả về (lat, lng, nguồn). Thứ tự: bài viết -> link/bản đồ Google Maps trong trang -> geocode
    lat, lng = to_float(place.get("latitude")), to_float(place.get("longitude"))
    if in_bounds(lat, lng):
        return lat, lng, "article"
    ref = match_ref(place, refs, single)
    if ref:
        lat, lng = coords_from_ref(ref)
        if in_bounds(lat, lng):
            return lat, lng, "maps_" + ref["kind"]
    return geocode_place(place)


def drop_shared_coords(pages):
    # Nhiều địa điểm cùng một toạ độ geocode gần như chắc chắn là điểm "tâm khu vực" chứ không phải vị trí thật -> bỏ
    same = {}
    for page in pages:
        for p in page["places"]:
            if (p.get("coord_source") or "").startswith("geocode"):
                same.setdefault((round(p["latitude"], 4), round(p["longitude"], 4)), []).append(p)
    for point, ps in same.items():
        if len(ps) >= 2:
            print(f"\nCẢNH BÁO: {len(ps)} địa điểm cùng toạ độ {point}, nghi là tâm khu vực nên đã bỏ toạ độ của chúng.")
            for p in ps:
                p["latitude"] = p["longitude"] = p["coord_source"] = None


def locate_all(pages, verbose=True):
    for page in pages:
        places = page["places"]
        if verbose:
            print("\nTrang:", page["url"])
        for p in places:
            lat, lng, src = locate(p, page.get("map_refs", []), len(places) == 1)
            p["latitude"], p["longitude"], p["coord_source"] = lat, lng, src
            if verbose:
                print("  ", p["name"], "|", lat, lng, "|", src)
    drop_shared_coords(pages)
    return pages
