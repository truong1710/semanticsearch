
import hashlib
import json
import re
from pathlib import Path

from common.gemini_client import generate_text
from crawldata import config as crawl_cfg


# Dùng model sinh văn bản đã cấu hình trong crawler.
# Không cần thêm GEMINI_TAG_MODEL vào file .env.
MODEL = crawl_cfg.EXTRACT_MODEL


# Cache kết quả AI để tránh gọi API lại với dữ liệu đã xử lý.
CACHE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "cache"
    / "ai_tags.json"
)


def _load_cache() -> dict:
    """Đọc cache từ ổ đĩa."""
    if not CACHE_PATH.exists():
        return {}

    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

        # Chỉ chấp nhận cache có cấu trúc dictionary.
        return data if isinstance(data, dict) else {}

    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict) -> None:
    """Lưu cache; tự tạo thư mục nếu chưa tồn tại."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _cache_key(text: str, candidates: list[str]) -> str:
    """Tạo khóa cache theo model, nội dung và tag được phép đề xuất."""
    content = json.dumps(
        {
            "model": MODEL,
            "text": text,
            "candidates": sorted(candidates),
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def suggest_tags(
    text: str,
    existing_tags: list[str],
    allowed_tags: list[str],
) -> list[str]:
    """
    Dùng Gemini đề xuất các tag bổ sung cho địa điểm.

    Args:
        text: Nội dung mô tả địa điểm.
        existing_tags: Các tag đã được luật nhận diện.
        allowed_tags: Toàn bộ tag hợp lệ trong taxonomy.

    Returns:
        Danh sách tag bổ sung hợp lệ.
        Nếu AI gặp lỗi, trả về [] để hệ thống tiếp tục dùng tag luật.
    """
    text = (text or "").strip()

    if not text:
        return []

    # Loại bỏ tag trùng lặp và chuẩn hóa danh sách.
    existing_tags = sorted(set(existing_tags))
    allowed_tags = sorted(set(allowed_tags))

    # Chỉ cho AI đề xuất những tag chưa được luật nhận diện.
    candidates = sorted(set(allowed_tags) - set(existing_tags))

    if not candidates:
        return []

    # Tạo khóa dựa trên đúng nội dung và danh sách tag được phép đề xuất.
    key = _cache_key(text, candidates)

    cache = _load_cache()

    if key in cache:
        cached_tags = cache[key]

        # Kiểm tra lại dữ liệu cache trước khi sử dụng.
        if isinstance(cached_tags, list):
            return sorted({
                tag
                for tag in cached_tags
                if isinstance(tag, str) and tag in candidates
            })

    prompt = f"""
Bạn là hệ thống phân loại đặc điểm của địa điểm du lịch tại Việt Nam.

NỘI DUNG ĐỊA ĐIỂM:
{text}

CÁC TAG ĐÃ ĐƯỢC LUẬT NHẬN DIỆN:
{json.dumps(existing_tags, ensure_ascii=False)}

CÁC TAG ĐƯỢC PHÉP ĐỀ XUẤT:
{json.dumps(candidates, ensure_ascii=False)}

NHIỆM VỤ:
- Chỉ chọn tag có bằng chứng rõ ràng từ nội dung.
- Chỉ sử dụng chính xác tag trong danh sách được phép đề xuất.
- Không tự tạo tag mới.
- Không suy diễn từ vị trí địa lý.
  Ví dụ: ở gần hồ không đồng nghĩa với có view hồ.
- Không gán tag chỉ vì đó là đặc điểm thường thấy ở khách sạn.
- Không chọn lại tag đã được luật nhận diện.
- Chỉ trả về JSON array, ví dụ: ["modern", "breakfast"].
- Nếu không có tag nào phù hợp, trả về [].
- Không trả về giải thích hay Markdown.
"""

    try:
        # Gọi module Gemini dùng chung.
        raw = generate_text(prompt).strip()

        # Dự phòng trường hợp model trả JSON trong Markdown.
        raw = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            raw,
            flags=re.IGNORECASE,
        ).strip()

        result = json.loads(raw)

        if not isinstance(result, list):
            raise ValueError("Phản hồi AI không phải JSON array.")

        # Chỉ chấp nhận tag thuộc candidates.
        valid_tags = sorted({
            tag
            for tag in result
            if isinstance(tag, str) and tag in candidates
        })

        # Chỉ lưu kết quả hợp lệ vào cache.
        cache[key] = valid_tags
        _save_cache(cache)

        return valid_tags

    except Exception as exc:
        print(f"AI tagging thất bại, dùng tag luật: {exc}")
        return []
