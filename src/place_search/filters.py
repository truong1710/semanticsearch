
import re
import unicodedata

from .text_utils import fold


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
_UNIT = r"(triệu|tr|m|k|nghìn|ngàn|đồng|vnd|đ)?"

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
    )

    match = re.search(price_pattern, text, re.I)

    if match:
        number = match.group(1)
        unit = match.group(2)

        price_max = _to_vnd(number, unit)

        # Chỉ xóa điều kiện nếu phân tích được số tiền.
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
