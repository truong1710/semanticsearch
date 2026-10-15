import html
import re
import unicodedata

from bs4 import BeautifulSoup

URL_RE = re.compile(r"https?://\S+|www\.\S+")
INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2B06\u2194-\u21AA]+")


def clean_text(text) -> str:
    if text is None or (isinstance(text, float) and text != text):
        return ""
    text = html.unescape(str(text))
    text = BeautifulSoup(text, "html.parser").get_text(" ")
    text = unicodedata.normalize("NFC", text)
    text = INVISIBLE_RE.sub("", text)
    text = URL_RE.sub(" ", text)
    text = EMOJI_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def fold(text: str) -> str:
    """Hạ chữ thường và bỏ dấu tiếng Việt: 'Công viên' -> 'cong vien'."""
    text = clean_text(text).lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip()