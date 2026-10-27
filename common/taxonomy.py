import re

from .text import clean_text

TAXONOMY = {
    "ambiance": {"quiet": "Yên tĩnh", "lively": "Sôi động", "romantic": "Lãng mạn"},
    "audience": {"family": "Gia đình có trẻ nhỏ", "couple": "Cặp đôi",
                 "solo": "Đi một mình", "business": "Công tác"},
    "feature": {"lake-view": "View hồ", "balcony": "Ban công", "pool": "Hồ bơi",
                "local-food": "Ẩm thực địa phương", "breakfast": "Bữa sáng", "spa": "Dịch vụ spa"},
    "style": {
        "classic": "Phong cách cổ điển",
        "neoclassical": "Phong cách tân cổ điển",
        "modern": "Phong cách hiện đại",
        "luxury": "Phong cách sang trọng",
        "minimalist": "Phong cách tối giản",
        "indochine": "Phong cách Đông Dương",
    },
}
ALLOWED_TAGS = {tag for group in TAXONOMY.values() for tag in group}

TAG_GROUP = {
    tag: group
    for group, tags in TAXONOMY.items()
    for tag in tags
}

TAG_VI = {
    "quiet": "yên tĩnh", "lively": "sôi động", "romantic": "lãng mạn",
    "family": "phù hợp gia đình", "couple": "phù hợp cặp đôi",
    "solo": "phù hợp người đi một mình", "business": "phù hợp công tác",
    "lake-view": "có view hồ", "balcony": "có ban công", "pool": "có hồ bơi",
    "local-food": "có ẩm thực địa phương", "breakfast": "có bữa sáng",
    "spa": "có dịch vụ spa",
    "classic": "có phong cách cổ điển",
    "neoclassical": "có phong cách tân cổ điển",
    "modern": "có phong cách hiện đại",
    "luxury": "có phong cách sang trọng",
    "minimalist": "có phong cách tối giản",
    "indochine": "có phong cách Đông Dương",
}

CATEGORY_VI = {
    "cat-hotel": "khách sạn",
    "cat-cafe": "quán cà phê hoặc phòng trà",
    "cat-park": "công viên",
    "cat-culture": "bảo tàng, chùa và địa điểm văn hóa",
    "cat-restaurant": "quán ăn và nhà hàng",
}

TAG_RULES = {
     "quiet": [
        r"yên tĩnh",
        r"yên bình",
        r"thanh tịnh",
        r"êm ái",
        r"ít ồn",
        r"tránh được sự ồn",
        r"không ồn",
        r"cách âm",
    ],

    "lively": [
        r"sôi động",
        r"náo nhiệt",
        r"vui nhộn",
        r"không khí nhộn nhịp",
        r"nhộn nhịp",
        r"đông vui",
        r"tấp nập",
    ],
    "romantic": [r"lãng mạn", r"bữa tối nến", r"hẹn hò"],
    "family": [r"gia đình", r"trẻ em", r"trẻ nhỏ", r"cho bé"],
    "couple": [r"cặp đôi", r"trăng mật", r"massage đôi"],
    "solo": [r"đi một mình", r"ở một mình", r"du lịch bụi"],
    "business": [r"doanh nhân", r"công tác", r"phòng họp", r"bàn làm việc", r"khu làm việc"],
    "lake-view": [r"view hồ", r"nhìn ra hồ", r"hướng hồ", r"bên hồ", r"mặt nước"],
    "balcony": [r"ban công"],
    "pool": [r"hồ bơi", r"bể bơi"],
    "local-food": [r"quán phở", r"hải sản", r"đặc sản", r"ẩm thực", r"món ăn truyền thống",
                   r"cà phê trứng", r"bún chả", r"bánh cuốn"],
    "breakfast": [r"bữa sáng", r"ăn sáng", r"buffet sáng"],
    "spa": [r"\bspa\b", r"mát[\s-]?xa", r"massage", r"trị liệu", r"chăm sóc cơ thể"],
    "classic": [
        r"cổ kính",
        r"phong cách cổ kính",
        r"kiến trúc cổ kính",
        r"cổ xưa",
        r"hoài cổ",
        r"phong cách cổ điển",
        r"kiến trúc cổ điển",
        r"thiết kế cổ điển",
        r"nội thất cổ điển",
        r"mang nét cổ điển",
        r"đậm chất cổ điển",
    ],

    "neoclassical": [
        r"tân cổ điển",
        r"phong cách neoclassical",
        r"kiến trúc neoclassical",
    ],

    "modern": [
        r"phong cách hiện đại",
        r"kiến trúc hiện đại",
        r"thiết kế hiện đại",
        r"nội thất hiện đại",
    ],

    "luxury": [
        r"sang trọng", r"đẳng cấp", r"xa hoa", r"cao cấp",
        r"thượng lưu", r"\b5 sao\b", r"năm sao",
        r"\bluxury\b", r"\bgrand\b", r"\bresort\b",
    ],

    "minimalist": [
        r"phong cách tối giản",
        r"thiết kế tối giản",
        r"kiến trúc tối giản",
    ],

    "indochine": [
        r"phong cách đông dương",
        r"phong cách indochine",
        r"kiến trúc đông dương",
        r"thiết kế đông dương",
    ],
    
}


NEG_SUFFIX = re.compile(
    r"^\s*(?:"
    r"không|chưa|chẳng|"
    r"không phải|"
    r"là không|"
    r"quá ồn|"
    r"ồn ào"
    r")\b"
)


# Phát hiện những từ phủ định gần bằng chứng.
NEG_PREFIX = re.compile(
    r"\b(?:không(?!\s+gian)|chưa|chẳng)(?:\s+hề)?(?:\s+\w+){0,2}\s*$"
)



def rule_tags_with_evidence(text: str) -> dict:
    text = clean_text(text).lower()
    found = {}

    for tag, patterns in TAG_RULES.items():
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                prefix = text[max(0, match.start() - 25):match.start()]
                if NEG_PREFIX.search(prefix):
                    continue
                found[tag] = match.group(0)
                break
            if tag in found:
                break

    if "quiet" in found and "lively" in found:
        found.pop("quiet")
        found.pop("lively")

    return found


def validate_tags(tags: list) -> list:
    errors = []
    if len(tags) != len(set(tags)):
        errors.append("nhãn trùng")
    for tag in tags:
        if tag not in ALLOWED_TAGS:
            errors.append(f"nhãn ngoài danh sách: {tag!r}")
    if "quiet" in tags and "lively" in tags:
        errors.append("xung đột: quiet + lively")
    return errors


def main():
    """Ví dụ chạy luật tag cục bộ: ``python -m common.taxonomy``."""
    sample = "Không gian yên tĩnh, có hồ bơi và phù hợp cho gia đình."
    tags = rule_tags_with_evidence(sample)
    print("Mô tả:", sample)
    print("Tag:", sorted(tags))
    print("Lỗi:", validate_tags(sorted(tags)))


if __name__ == "__main__":
    main()
