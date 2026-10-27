
import os

from dotenv import load_dotenv
from google import genai

from crawldata import config as crawl_cfg


# Đọc API key từ file .env ở thư mục gốc.
PROJECT_ROOT = crawl_cfg.BASE_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")

_client = None


def get_client():
    """Tạo Gemini client một lần, sau đó tái sử dụng."""
    global _client

    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError("Chưa cấu hình GEMINI_API_KEY trong .env")

        _client = genai.Client(api_key=api_key)

    return _client


def generate_text(prompt: str) -> str:
    """Gọi model sinh văn bản đã cấu hình trong crawler."""
    response = get_client().models.generate_content(
        model=crawl_cfg.EXTRACT_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json"},
    )

    return response.text or ""
