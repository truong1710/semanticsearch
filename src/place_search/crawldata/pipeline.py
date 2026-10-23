import datetime
import json
from pathlib import Path

from . import config as cfg
from .ai_extract import extract_places
from .enrich import assign_images, locate_all
from .extract import prepare_page
from .fetch import follow_detail_links, load_pages
from .utils import make_place_id




def collect_places(pages):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    out = []
    for page in pages:
        for p in page["places"]:
            p["source_url"] = page["url"]
            p["place_id"] = make_place_id(p)
            p["crawled_at"] = now
            out.append(p)
    return out


def save_places(places, path=None):
    path = Path(path or cfg.OUTPUT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(places, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def print_summary(places):
    print("\nTổng số địa điểm:", len(places))

    if not places:
        print("Không có địa điểm nào.")
        return

    # In đầy đủ dữ liệu từng địa điểm giống Google Colab
    for i, p in enumerate(places, start=1):
        print(f"\n========== ĐỊA ĐIỂM {i} ==========")
        print(json.dumps(p, ensure_ascii=False, indent=2, default=str))

def run(urls, save=True, verbose=True):
    # Chạy toàn bộ: tải trang -> (vào trang chi tiết) -> lấy văn bản/ảnh/bản đồ -> AI -> gán ảnh -> tọa độ -> lưu
    pages = load_pages(urls)
    if cfg.FOLLOW_DETAIL_LINKS:
        pages = follow_detail_links(pages)
    for page in pages:
        prepare_page(page, verbose=verbose)
    extract_places(pages, verbose=verbose)
    for page in pages:
        assign_images(page)
    locate_all(pages, verbose=verbose)
    places = collect_places(pages)
    if save:
        path = save_places(places)
        print("\nĐã lưu:", path)
    if verbose:
        print_summary(places)
    return places
