"""Entry point that coordinates crawl, review, import, and embedding stages.

Run ``python -m core.pipeline --help`` for the available stages. Review and
import remain separate commands so duplicate records are not inserted before
the generated files have been checked. Example: ``python -m core.pipeline parse-query "hotel under 3 million"``.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def sync_embeddings() -> int:
    """Read places from MySQL and synchronize their vectors to Qdrant."""
    from database.mysql import load_places
    from indexing.qdrant import sync_places

    return sync_places(load_places())


def check_duplicates() -> None:
    """Compare crawl results with MySQL and write review files."""
    script = PROJECT_ROOT / "scripts" / "check_duplicates.py"
    subprocess.run([sys.executable, str(script), "--run"], cwd=PROJECT_ROOT, check=True)


def inspect_crawled_data() -> None:
    path = PROJECT_ROOT / "data" / "craw" / "places.json"
    places = json.loads(path.read_text(encoding="utf-8"))
    valid = [p for p in places if p.get("latitude") is not None and p.get("longitude") is not None]
    print(f"Địa điểm: {len(places)}")
    print(f"Có tọa độ: {len(valid)}")
    print(f"Thiếu tọa độ: {len(places) - len(valid)}")
    if places:
        print(json.dumps(places[0], ensure_ascii=False, indent=2))


def main(argv: Sequence[str] | None = None) -> None:
    """CLI example: ``python -m core.pipeline search quán cà phê yên tĩnh``."""
    parser = argparse.ArgumentParser(description="Place search data pipeline")
    stages = parser.add_subparsers(dest="stage")

    crawl_parser = stages.add_parser("crawl", help="crawl the provided URLs")
    crawl_parser.add_argument("urls", nargs="*", help="URLs to crawl")
    stages.add_parser("check", help="check crawl output for duplicates")
    stages.add_parser("import", help="import checked new places into MySQL")
    stages.add_parser("embed", help="sync MySQL places to Qdrant")
    search_parser = stages.add_parser("search", help="search places")
    search_parser.add_argument("query", nargs="+", help="search phrase")
    search_parser.add_argument("--top-k", type=int, default=5)
    stages.add_parser("evaluate", aliases=["eval"], help="evaluate search quality")
    parse_parser = stages.add_parser("parse-query", help="inspect extracted search filters")
    parse_parser.add_argument("query", nargs="+")
    stages.add_parser("inspect-crawl", help="summarize the latest crawl JSON")
    stages.add_parser("qdrant", help="list Qdrant collections")

    args = parser.parse_args(argv)
    if args.stage is None:
        parser.print_help()
        print('\nVí dụ: python -m core.pipeline parse-query "khách sạn dưới 3 triệu ở Tây Hồ"')
        return

    if args.stage == "crawl":
        from crawldata.pipeline import run as crawl

        crawl(args.urls or ["https://mia.vn/cam-nang-du-lich/khach-san-5-sao-ha-noi-19881"])
    elif args.stage == "check":
        check_duplicates()
    elif args.stage == "import":
        from crawldata.db import import_places

        import_places()
    elif args.stage == "embed":
        sync_embeddings()
    elif args.stage == "search":
        from retrieval.search import show_smart

        show_smart(" ".join(args.query), top_k=args.top_k)
    elif args.stage in {"evaluate", "eval"}:
        from retrieval.search import run_evaluation

        run_evaluation()
    elif args.stage == "parse-query":
        from retrieval.query import parse_query

        print(parse_query(" ".join(args.query)))
    elif args.stage == "inspect-crawl":
        inspect_crawled_data()
    elif args.stage == "qdrant":
        from qdrant_client import QdrantClient

        from config import QDRANT_URL

        collections = QdrantClient(url=QDRANT_URL).get_collections()
        print("Qdrant collections:", [item.name for item in collections.collections])


if __name__ == "__main__":
    main()
