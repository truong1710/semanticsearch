# Cấu hình của place_crawler.
# Các module đọc giá trị bằng `from . import config as cfg` rồi dùng `cfg.TEN_BIEN` MỖI LẦN cần,
# nên có thể đổi lúc chạy (ví dụ cfg.BBOX = (...)) mà không phải sửa file này.
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "place_crawler"      # thư mục riêng, không đè dữ liệu khác của dự án

TARGET = "khách sạn"                 # loại địa điểm cần lấy: "khách sạn", "quán cà phê", "nhà hàng"...
EXTRACT_MODEL = "gemini-3.5-flash-lite"
MODEL_FALLBACKS = []                 # ví dụ ["gemini-3.5-flash"]: tự chuyển model khi model chính quá tải / hết hạn mức

# Danh mục hợp lệ cho category_id (nếu DB đã có bảng danh mục thì nên lấy từ đó thay vì viết trùng ở đây)
CATEGORIES = {
    "cat-hotel": "Khách sạn, resort hoặc cơ sở lưu trú thuộc loại khách sạn.",
    "cat-cafe": "Quán cà phê, tiệm cà phê.",
    "cat-park": "Công viên, vườn hoa hoặc khu công viên công cộng.",
    "cat-culture": "Chùa, đền, di tích lịch sử, bảo tàng và địa điểm văn hóa.",
    "cat-restaurant": "Nhà hàng, quán ăn, quán phở, quán bún và các cơ sở kinh doanh đồ ăn.",
}

# Khung tọa độ hợp lệ (lat_min, lat_max, lng_min, lng_max). Đặt None để không kiểm tra.
BBOX = (20.8, 21.4, 105.6, 106.1)    # Hà Nội
GEO_SUFFIX = ", Hà Nội, Việt Nam"    # thêm vào câu truy vấn geocode
COUNTRY_CODE = "vn"                  # None để bỏ giới hạn quốc gia

# Vùng nội dung chính của bài, thử lần lượt từ trên xuống. Thêm selector của site mới vào đây.
CONTENT_SELECTORS = [".cmp-vna-rte", ".entry-content", ".post-content", ".article-content", "article", "main"]
MIN_CONTENT_CHARS = 500

MAX_IMAGES = 100                     # số ảnh tối đa lấy từ một trang
MAX_IMAGES_PER_PLACE = 8             # ảnh tối đa cho mỗi địa điểm (trang danh sách)
GEO_DELAY = 1.1                      # Nominatim: tối đa 1 request/giây

# Cách tải trang:
#   "auto"    : tải thường trước; nếu nội dung nghèo (trang dựng bằng JavaScript) thì tự bật trình duyệt
#   "static"  : chỉ tải thường (nhanh, không cần cài trình duyệt)
#   "browser" : luôn dùng trình duyệt
RENDER_MODE = "auto"
BROWSER_SCROLLS = 6                  # số lần cuộn trang khi dùng trình duyệt
LOAD_MORE_CLICKS = 10                # số lần tối đa tự bấm nút "Xem thêm" / "Tải thêm"

# Trang danh sách -> trang chi tiết
FOLLOW_DETAIL_LINKS = False          # True: coi URL đưa vào là TRANG DANH SÁCH, tự đi vào từng trang chi tiết
DETAIL_LINK_PATTERN = None           # regex lọc link chi tiết, ví dụ r"/hotels/[^/]+$"; None = tự đoán
MAX_DETAIL_PAGES = 5                 # mỗi trang chi tiết tốn 1 request AI (gói miễn phí chỉ ~20/ngày)
DETAIL_DELAY = 1.0                   # nghỉ giữa các trang (giây)

USE_CACHE = True                     # True: dùng lại kết quả AI đã lưu, không tốn request
CACHE_FILE = DATA_DIR / "ai_cache.json"
OUTPUT_FILE = DATA_DIR / "places.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}
