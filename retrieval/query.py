
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache

import numpy as np

from config import CATEGORY_MARGIN, CATEGORY_THR, TAG_THR
from embedding.vectors import embed_dense
from common.text import fold


DISTRICTS = [
    # 12 quận
    "Ba Đình", "Hoàn Kiếm", "Tây Hồ", "Long Biên", "Cầu Giấy", "Đống Đa",
    "Hai Bà Trưng", "Hoàng Mai", "Thanh Xuân", "Nam Từ Liêm", "Bắc Từ Liêm", "Hà Đông",
    # 1 thị xã
    "Sơn Tây",
    # 17 huyện
    "Ba Vì", "Chương Mỹ", "Đan Phượng", "Đông Anh", "Gia Lâm", "Hoài Đức",
    "Mê Linh", "Mỹ Đức", "Phú Xuyên", "Phúc Thọ", "Quốc Oai", "Sóc Sơn",
    "Thạch Thất", "Thanh Oai", "Thanh Trì", "Thường Tín", "Ứng Hòa",
]

# Ví dụ số:
# 3
# 3.5
# 3,5
# 3.000.000
_NUM = r"(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)"

# Các đơn vị tiền thường gặp.
_UNIT = r"(triệu|tr|m|k|nghìn|ngàn|đồng|vnd|đ)?\b"

_PRICE_PATTERN = _NUM + r"\s*" + _UNIT


def normalize_text(text):
    """Chuẩn hóa Unicode và khoảng trắng."""
    text = unicodedata.normalize("NFC", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _to_vnd(num, unit=None):
    """
    Chuyển số tiền về VND.

    3 triệu      -> 3000000
    500k          -> 500000
    3.000.000 VND -> 3000000
    """
    if not num:
        return None

    num = num.strip()
    unit = (unit or "").lower().strip()

    if unit in ("triệu", "tr", "m"):
        try:
            return int(float(num.replace(",", ".")) * 1_000_000)
        except ValueError:
            return None

    if unit in ("k", "nghìn", "ngàn"):
        try:
            return int(float(num.replace(",", ".")) * 1_000)
        except ValueError:
            return None

    # Với số không có đơn vị hoặc dùng đơn vị đồng/VND,
    # bỏ dấu phân cách hàng nghìn.
    digits = re.sub(r"[.,]", "", num)

    if digits.isdigit():
        return int(digits)

    return None


def parse_price_range(text):
    """
    Phân tích giá trong dữ liệu khách sạn.

    Ví dụ:
        '3.000.000 - 5.000.000 VND/phòng'
        -> (3000000, 5000000)

        'Từ 3.000.000 VND'
        -> (3000000, 3000000)

        'Liên hệ'
        -> (None, None)
    """
    text = normalize_text(text)

    if not text:
        return None, None

    values = []

    for match in re.finditer(_PRICE_PATTERN, text, re.I):
        number = match.group(1)
        unit = match.group(2)

        value = _to_vnd(number, unit)

        # Loại các số nhỏ có khả năng không phải giá VND.
        if value is not None and value >= 10_000:
            values.append(value)

    if not values:
        return None, None

    return min(values), max(values)


def parse_district(address):
    """Tìm tên quận trong địa chỉ, kể cả khi khác dấu Unicode."""
    address_folded = fold(normalize_text(address))

    for district in DISTRICTS:
        if fold(district) in address_folded:
            return district

    return None


def parse_query(query):
    """
    Tách câu truy vấn thành:
        (text, price_max, district)

    Ví dụ:
        'Tìm khách sạn dưới 3 triệu ở Tây Hồ'

    Kết quả:
        ('Tìm khách sạn ở', 3000000, 'Tây Hồ')
    """
    original_query = normalize_text(query)

    if not original_query:
        return "", None, None

    text = original_query
    price_max = None
    district = None

    # Các điều kiện giá tối đa.
    price_pattern = (
        r"(?:dưới|ít hơn|thấp hơn|không quá|tối đa|<=|<)\s*"
        + _PRICE_PATTERN
        + r"(?!\s*sao)"
    )

    match = re.search(price_pattern, text, re.I)

    if match:
        number = match.group(1)
        unit = match.group(2)

        price_max = _to_vnd(number, unit)

        # Số trần không đơn vị mà quá nhỏ (vd "dưới 5") thì không phải giá VND.
        if price_max is not None and not unit and price_max < 10_000:
            price_max = None

        # Chỉ xóa điều kiện khỏi câu khi thật sự là giá.
        if price_max is not None:
            text = text[:match.start()] + " " + text[match.end():]
    text = normalize_text(text)

    # Tìm quận bằng chuỗi đã bỏ dấu.
    text_folded = fold(text)

    for name in DISTRICTS:
        folded_name = fold(name)

        # Tìm vị trí theo từng ký tự gốc để xóa đúng
        # cả khi chuỗi đầu vào dùng Unicode tổ hợp dấu.
        found = None
        for start in range(len(text) + 1):
            for end in range(start + 1, len(text) + 1):
                if fold(text[start:end]) == folded_name:
                    found = (start, end)
                    break
            if found:
                break

        if found:
            start, end = found
            district = name
            text = text[:start] + " " + text[end:]
            text = normalize_text(text)
            break

    # Không để câu tìm kiếm rỗng.
    if not text:
        text = original_query

    return text, price_max, district
def _unit(m):
    m = np.asarray(m, dtype=float)
    return m / np.linalg.norm(m, axis=-1, keepdims=True)


CATEGORY_PROTOTYPES = {
    "cat-park": ["công viên", "vườn hoa", "chỗ đi dạo nhiều cây xanh", "nơi chạy bộ tập thể dục"],
    "cat-hotel": ["khách sạn", "chỗ ở qua đêm", "resort nghỉ dưỡng", "nơi nghỉ"],
    "cat-cafe": ["quán cà phê", "quán cafe", "chỗ ngồi làm việc uống cà phê", "phòng trà"],
    "cat-culture": ["bảo tàng", "chùa", "di tích lịch sử", "địa điểm văn hóa"],
    "cat-restaurant": ["quán ăn", "nhà hàng", "món ăn đặc sản", "quán phở bún"],
}
TAG_PROTOTYPES = {
    "romantic": ["lãng mạn", "hẹn hò", "đi với người yêu", "kỷ niệm ngày cưới"],
    "couple": ["cặp đôi", "đi với người yêu", "vợ chồng", "trăng mật"],
    "family": ["gia đình", "đi chơi với con nhỏ", "trẻ em", "cho bé"],
    "quiet": ["yên tĩnh", "thư giãn", "tránh ồn ào", "yên bình"],
    "lively": ["sôi động", "náo nhiệt", "vui nhộn"],
    "business": ["đi công tác", "họp hành", "làm việc"],
    "solo": ["đi một mình", "du lịch bụi"],
    "pool": ["hồ bơi", "bể bơi"],
    "lake-view": ["view hồ", "nhìn ra hồ", "bên hồ"],
    "local-food": ["đặc sản", "món ăn truyền thống", "ẩm thực Hà Nội"],
    "breakfast": ["ăn sáng", "bữa sáng"],
    "classic": [ "khách sạn cổ điển", "khách sạn mang phong cách cổ kính", "khách sạn có nét kiến trúc cổ xưa", "khách sạn phong cách hoài cổ",],
}


def _build_protos(protos):
    result = {}

    for k, v in protos.items():
        vectors = embed_dense(v)
        normalized_vectors = _unit(vectors)
        result[k] = normalized_vectors

    return result

@lru_cache(maxsize=1)
def category_vectors():
    return _build_protos(CATEGORY_PROTOTYPES)


@lru_cache(maxsize=1)
def tag_vectors():
    return _build_protos(TAG_PROTOTYPES)


def similarities(q_vec, vecs):
    result = {}

    for k, m in vecs.items():
        scores = m @ q_vec
        best_score = scores.max()
        result[k] = float(best_score)

    return result

CATEGORY_KEYWORDS = {
    "cat-hotel": ["khach san", "hotel", "resort", "noi nghi", "cho nghi"],
    "cat-cafe": ["ca phe", "cafe", "coffee", "phong tra"],
    "cat-park": ["cong vien", "vuon hoa", "tap the duc", "chay bo", "di dao", "tap yoga"],
    "cat-culture": ["bao tang", "di tich", "dia diem van hoa"],
    "cat-restaurant": ["quan an", "nha hang", "quan pho", "quan bun", "an uong", "mon an"],
}


def keyword_category(q_fold, q_raw):
    matched = {c for c, kws in CATEGORY_KEYWORDS.items() if any(k in q_fold for k in kws)}
    if "chùa" in q_raw.lower():
        matched.add("cat-culture")
    return matched.pop() if len(matched) == 1 else None


def route_category(q_vec, q_fold, q_raw=""):
    scores = similarities(q_vec, category_vectors())
    kw = keyword_category(q_fold, q_raw)
    if kw:
        return kw, scores
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    (c1, s1), (_, s2) = ranked[0], ranked[1]
    if s1 >= CATEGORY_THR and s1 - s2 >= CATEGORY_MARGIN:
        return c1, scores
    return None, scores

# Luật cho truy vấn: cụm chữ thường không dấu, KHÔNG dùng regex
QUERY_TAG_RULES = {
    
    "lively": ["soi dong", "nao nhiet", "vui nhon", "nhon nhip", "dong vui"],
    "romantic": ["lang man", "hen ho", "nguoi yeu", "ky niem"],
    "family": ["gia dinh", "tre em", "tre nho", "cho be"],
    "couple": ["cap doi", "trang mat", "nguoi yeu", "vo chong"],
    "solo": ["di mot minh", "o mot minh", "du lich bui"],
    "business": ["doanh nhan", "cong tac", "phong hop"],
    "lake-view": ["view ho", "nhin ra ho", "huong ho", "ben ho"],
    "balcony": ["ban cong"],
    "pool": ["ho boi", "be boi"],
    "local-food": ["dac san", "am thuc", "mon an truyen thong", "bun cha"],
    "breakfast": ["bua sang", "an sang", "buffet sang"],
    "spa": ["spa", "mat xa", "matxa", "massage", "tri lieu"],
    "neoclassical": ["tan co dien"],
    "modern": ["hien dai"],
    "luxury": ["sang trong", "dang cap", "xa hoa", "cao cap", "thuong luu", "5 sao", "nam sao"],
    "minimalist": ["toi gian"],
    "indochine": ["dong duong", "indochine"],
    "classic": ["co dien","co kinh","mang net co xua","phong cach co xua",],

    "quiet": [
        "yen tinh", "yen binh", "thanh tinh", "thanh binh",
        "it on", "thu gian", "tranh on", "tranh tieng on",
        "khong gian yen tinh",
    ],
    "shuttle": [
        "dua don", "don san bay", "xe don", "shuttle", "airport transfer",
    ],
    "wifi": ["wifi", "internet", "mang mien phi"],
    "cozy": ["am cung", "gan gui", "de chiu"],
}


def _has_phrase(p, text):
    # khớp nguyên từ: "an sang" không còn khớp trong "san sang"
    return re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", text) is not None


def fuzzy_contains(phrase, text, cutoff=0.88):
    n = len(phrase.split())
    words = text.split()
    return any(
        SequenceMatcher(None, phrase, " ".join(words[i:i + n])).ratio() >= cutoff
        for i in range(len(words) - n + 1)
    )


def infer_query_tags(q_vec, q_fold):
    tags = set()
    for tag, pats in QUERY_TAG_RULES.items():
        for p in pats:
            # fuzzy chỉ cho cụm dài (chịu lỗi gõ), cụm ngắn phải khớp đúng
            if _has_phrase(p, q_fold) or (len(p) >= 10 and fuzzy_contains(p, q_fold, 0.9)):
                tags.add(tag)
                break
    for tag, s in similarities(q_vec, tag_vectors()).items():
        if s >= TAG_THR:
            tags.add(tag)
    if "quiet" in tags and "lively" in tags:
        tags -= {"quiet", "lively"}
    return sorted(tags)

# (lat, lon, bán kính mét)
LANDMARKS = {
    "ho hoan kiem": (21.0285, 105.8522, 2000),
    "pho co": (21.0340, 105.8500, 1500),
    "ho tay": (21.0600, 105.8200, 3000),
    "van mieu": (21.0270, 105.8350, 2000),
}


def detect_landmark(q_fold):
    for name, (lat, lon, r) in LANDMARKS.items():
        if name in q_fold:
            return name, (lat, lon, r)
    return None, None


def main():
    """Demo tách điều kiện tìm kiếm, không gọi API: ``python -m retrieval.query``."""
    sample = "Khách sạn yên tĩnh dưới 3 triệu ở Tây Hồ"
    print("Query:", sample)
    print("Parsed:", parse_query(sample))
    print("District:", parse_district("Quận Tây Hồ, Hà Nội"))


if __name__ == "__main__":
    main()
