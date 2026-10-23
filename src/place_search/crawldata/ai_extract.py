import copy
import hashlib
import json
import os
import re
import time
from pathlib import Path

from . import config as cfg
from .utils import clean_place, normalize
from dotenv import load_dotenv
from google import genai

load_dotenv()

FIELDS = ["name", "description", "address", "latitude", "longitude",
          "opening_hours", "price_range", "image_urls", "category_id"]

_client = None


def get_client():
    global _client

    if _client is None:
        key = os.getenv("GEMINI_API_KEY")

        if not key:
            raise RuntimeError("Chưa có GEMINI_API_KEY trong file .env")

        _client = genai.Client(api_key=key)

    return _client


def build_prompt(text):
    cats = "\n".join(f'- "{k}": {v}' for k, v in cfg.CATEGORIES.items())
    target = cfg.TARGET
    return f"""
Bạn là hệ thống trích xuất dữ liệu địa điểm từ trang web tiếng Việt.

NHIỆM VỤ:
Đọc toàn bộ nội dung trang và trích xuất các {target} được giới thiệu trực tiếp trong nội dung chính.
Mỗi {target} là một đối tượng JSON riêng.

PHẠM VI TRÍCH XUẤT:
- Nếu trang là danh sách (top, gợi ý...), chỉ lấy các {target} được giới thiệu thành từng mục riêng.
- Nếu trang chỉ giới thiệu MỘT {target} (tên ở tiêu đề chính), trả về mảng đúng một phần tử.
- Không lấy {target} khác chỉ xuất hiện trong menu, chân trang, liên kết, mục bài viết liên quan hoặc phần so sánh.
- Không lấy hạng mục con (hạng phòng, món ăn, dịch vụ), tour, công ty đăng bài hay địa điểm lân cận thành đối tượng riêng; có thể nhắc chúng trong description.
- Tên phải xuất hiện trong văn bản nguồn. Không tạo tên không có trong văn bản.
- Không dùng kiến thức bên ngoài để bổ sung thông tin còn thiếu.

CÁC TRƯỜNG CẦN TRÍCH XUẤT:
- name: Tên chính thức hoặc tên được bài viết dùng để gọi địa điểm.
- description: Tóm tắt thông tin quan trọng: loại hình, đặc điểm, tiện ích, dịch vụ, hoạt động được đề cập.
- address: Nếu nguồn có nhãn như "Địa chỉ:" thì sao chép nguyên văn phần sau nhãn. Nếu không có nhãn, lấy địa chỉ hiển thị ngay cạnh phần giới thiệu của chính địa điểm đó. Không có thì null.
- review: đánh giá của từng khách sạn.
- latitude: Vĩ độ nếu nguồn ghi.
- longitude: Kinh độ nếu nguồn ghi.
- opening_hours: Giờ mở cửa nếu nguồn ghi.
- price_range: Nếu nguồn có nhãn giá như "Giá phòng:", "Giá tham khảo:", "Giá vé:", "Giá:" thì sao chép nguyên văn mức giá. Không có thì null.
- image_urls: luôn trả về [].
- category_id: Một giá trị trong danh sách bên dưới.

DANH SÁCH category_id HỢP LỆ:
{cats}
Chọn đúng một giá trị theo loại hình chính của địa điểm. Không đủ căn cứ thì null. Không tự tạo danh mục mới.

QUY TẮC ĐẦU RA:
- Chỉ trả về một mảng JSON hợp lệ, mỗi phần tử là một đối tượng địa điểm có đủ các trường trên.
- Giá trị chưa xác định dùng null.
- Không thêm giải thích hay Markdown.

NỘI DUNG TRANG:
{text}
"""


def call_gemini(prompt, retries_per_model=4):
    # Gọi model chính; lỗi server (5xx) thì thử lại; hết hạn mức (429) hoặc vẫn lỗi thì chuyển model dự phòng
    from google.genai import errors

    models = [cfg.EXTRACT_MODEL] + [m for m in cfg.MODEL_FALLBACKS if m != cfg.EXTRACT_MODEL]
    last_error = None
    for model in models:
        for attempt in range(retries_per_model):
            try:
                resp = get_client().models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"response_mime_type": "application/json"},
                )
                return resp.text
            except errors.ServerError as e:
                last_error = e
                wait = 5 * 2 ** attempt
                print(f"  {model}: lỗi server ({getattr(e, 'code', '?')}), thử lại sau {wait}s ({attempt + 1}/{retries_per_model})")
                time.sleep(wait)
            except errors.ClientError as e:
                if getattr(e, "code", None) == 429:
                    last_error = e
                    print(f"  {model}: hết hạn mức (429)")
                    break
                raise
        print(f"  {model} chưa dùng được, chuyển model khác (nếu có)...")
    raise RuntimeError("Tất cả model đều lỗi hoặc hết hạn mức. Chờ rồi chạy lại, hoặc thêm cfg.MODEL_FALLBACKS.") from last_error


def parse_places(raw, source_text):
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("Kết quả AI phải là một mảng JSON")

    ntext = normalize(source_text)
    out, seen = [], set()
    for p in data:
        if not isinstance(p, dict) or not p.get("name"):
            continue
        key = normalize(p["name"])
        if key in seen:
            continue
        seen.add(key)
        for f in FIELDS:
            p.setdefault(f, None)
        if p["category_id"] not in cfg.CATEGORIES:
            p["category_id"] = None
        p["image_urls"] = []
        p["verified_in_source"] = key in ntext      # tên có thật sự xuất hiện trong văn bản không
        out.append(p)
    return out


# ------------------------------------------------------------------ cache
def cache_key(prompt):
    # Khóa cache gồm model + toàn bộ prompt (văn bản, TARGET, danh mục...) nên đổi bất cứ thứ gì là tự gọi lại AI
    return hashlib.sha1((cfg.EXTRACT_MODEL + "\n" + prompt).encode("utf-8")).hexdigest()


def load_cache():
    path = Path(cfg.CACHE_FILE)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_cache(cache):
    path = Path(cfg.CACHE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_places(pages, verbose=True):
    # Với mỗi trang: gọi AI (hoặc dùng cache) rồi lưu danh sách địa điểm vào page["places"]
    cache = load_cache() if cfg.USE_CACHE else {}
    for page in pages:
        url = page["url"]
        page["places"] = []
        if verbose:
            print("\nTrang:", url)

        text = page.get("text", "")
        if len(text) < 200:
            print(f"  BỎ QUA: văn bản chỉ có {len(text)} ký tự, quá ngắn để gửi AI.")
            print("  -> Trang có thể dựng bằng JavaScript (xem cfg.RENDER_MODE) hoặc cfg.CONTENT_SELECTORS chưa khớp.")
            continue

        prompt = build_prompt(text)
        key = cache_key(prompt)
        if key in cache:
            print("  [cache] dùng lại kết quả AI đã lưu")
            places = copy.deepcopy(cache[key]["places"])
        else:
            print("  [gọi AI]")
            raw = call_gemini(prompt)
            places = parse_places(raw, text)
            if places:                                   # không lưu kết quả rỗng vào cache
                if cfg.USE_CACHE:
                    cache[key] = {"url": url, "places": copy.deepcopy(places)}
                    save_cache(cache)
            else:
                print("  CẢNH BÁO: AI không trả về địa điểm nào (không lưu cache).")
                print("  Phản hồi thô của AI:", (raw or "")[:300])
                print("  800 ký tự đầu văn bản đã gửi cho AI:")
                print(text[:800])

        for p in places:
            clean_place(p)
        page["places"] = places
        if verbose:
            print(f"  -> {len(places)} địa điểm")
            for p in places:
                flag = "" if p["verified_in_source"] else "   <-- tên không thấy trong văn bản, kiểm tra lại"
                print("   -", p["name"], "|", p["address"], "|", p["price_range"], flag)
    return pages
