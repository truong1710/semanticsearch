
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.place_search.crawldata.pipeline import run

from src.place_search.crawldata.pipeline import run
URLS = [
   
    "https://mia.vn/cam-nang-du-lich/khach-san-5-sao-ha-noi-19881",
    
]

if __name__ == "__main__":
    run(sys.argv[1:] or URLS)
