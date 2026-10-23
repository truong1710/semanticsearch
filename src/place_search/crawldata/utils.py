import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from . import config as cfg


def normalize(s):
    # chữ thường, bỏ dấu tiếng Việt, bỏ ký tự lạ: "Meliá Hà Nội" -> "melia ha noi"
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def in_bounds(lat, lng):
    if lat is None or lng is None:
        return False
    if cfg.BBOX is None:
        return True
    b = cfg.BBOX
    return b[0] <= lat <= b[1] and b[2] <= lng <= b[3]


TRACKING_PREFIXES = ("utm_", "gclid", "gad_", "gbraid", "wbraid", "fbclid", "msclkid")


def clean_url(url):
    # bỏ tham số quảng cáo (gclid, utm_...)
    p = urlparse(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if not k.lower().startswith(TRACKING_PREFIXES)]
    return urlunparse(p._replace(query=urlencode(q)))


# --- Địa chỉ có đủ cụ thể để geocode không? ---
ADMIN_WORDS = {"quan", "huyen", "phuong", "xa", "thi", "tran", "tinh", "q", "p"}
STREET_MARKERS = {"pho", "duong", "ngo", "ngach", "hem", "street", "road", "lane", "avenue", "st", "rd", "ave"}


def address_core(addr):
    # Phần còn lại của địa chỉ sau khi bỏ tên thành phố/quốc gia và các từ hành chính (quận, phường...)
    s = normalize(addr)
    s = re.sub(r"\b(thanh pho|tp)\b", " ", s)
    drop = set(normalize(cfg.GEO_SUFFIX).split()) | {"hanoi", "vietnam", "vn"} | ADMIN_WORDS
    return [t for t in s.split() if t not in drop]


def is_specific_address(addr):
    # Cụ thể = có số nhà, hoặc có "phố/đường/ngõ...", hoặc còn từ 3 từ trở lên (tên đường)
    core = address_core(addr or "")
    has_digit = any(ch.isdigit() for t in core for ch in t)
    return bool(core) and (has_digit or any(t in STREET_MARKERS for t in core) or len(core) >= 3)


def clean_place(p):
    # Địa chỉ chỉ là tên thành phố (ví dụ "Hà Nội") không phải địa chỉ thật -> null
    if p.get("address") and not address_core(p["address"]):
        p["address"] = None


def make_place_id(p):
    # Mã ổn định theo tên chuẩn hóa, để cập nhật lại (upsert) khi crawl lần sau mà không nhân đôi.
    # Lưu ý: hai địa điểm khác nhau nhưng trùng tên sẽ trùng mã; nếu cần phân biệt, thêm địa chỉ/tọa độ vào khóa.
    return hashlib.sha1(normalize(p.get("name")).encode("utf-8")).hexdigest()[:12]
