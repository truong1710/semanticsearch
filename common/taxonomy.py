import re
import unicodedata
 
from .text import clean_text
 
TAXONOMY = {
    "ambiance": {"quiet": "Yên tĩnh", "lively": "Sôi động", "romantic": "Lãng mạn",
                 "cozy": "Ấm cúng"},
    "audience": {"family": "Gia đình có trẻ nhỏ", "couple": "Cặp đôi",
                 "solo": "Đi một mình", "business": "Công tác", "friends": "Nhóm bạn"},
    "feature": {"lake-view": "View hồ", "balcony": "Ban công", "pool": "Hồ bơi",
                "local-food": "Ẩm thực địa phương", "breakfast": "Bữa sáng", "spa": "Dịch vụ spa"},
    "style": {
        "classic": "Phong cách cổ điển",
        "neoclassical": "Phong cách tân cổ điển",
        "modern": "Phong cách hiện đại",
        "luxury": "Phong cách sang trọng",
        "minimalist": "Phong cách tối giản",
        "indochine": "Phong cách Đông Dương",
        
    },
    "space": {
        "spacious": "Không gian rộng rãi",
        "outdoor": "Không gian ngoài trời",
        "garden": "Sân vườn",
        "rooftop": "Sân thượng",
        "private-room": "Phòng riêng",
        "green": "Nhiều cây xanh",
    },
    # --- nhà hàng ---
    "cuisine": {
        "noodle": "Bún, phở, miến", "rice": "Cơm", "porridge": "Cháo",
        "grill": "Món nướng", "hotpot": "Lẩu", "seafood": "Ốc, hải sản",
        "snack": "Ăn vặt",
    },
    "service": {
        "late-night": "Ăn đêm", "street-food": "Quán vỉa hè",
        "air-conditioned": "Có máy lạnh",
    },
    "price": {"budget": "Bình dân", "mid": "Tầm trung", "high": "Cao cấp"},
    # --- chùa, bảo tàng, văn hóa ---
    "venue": {"temple": "Chùa", "shrine": "Đền, đình, miếu",
              "museum": "Bảo tàng", "heritage": "Di tích"},
    "theme": {"history": "Lịch sử", "art": "Nghệ thuật", "spiritual": "Tâm linh"},
    "visit": {"free-entry": "Miễn phí vé", "dress-code": "Cần ăn mặc kín đáo",
              "guided-tour": "Có thuyết minh", "interactive": "Trải nghiệm tương tác"},
    "amenity": {
        "wifi": "Wifi",
        "shuttle": "Xe đưa đón",
        "parking": "Bãi đỗ xe",
        "gym": "Phòng gym",
        "reception-24h": "Lễ tân 24/7",
        "laundry": "Giặt ủi",
        "pet-friendly": "Cho phép thú cưng",
    },
    
}
ALLOWED_TAGS = {tag for group in TAXONOMY.values() for tag in group}
TAG_GROUP = {
    tag: group
    for group, tags in TAXONOMY.items()
    for tag in tags
}
# Các cặp tag không được xuất hiện cùng nhau.
# Dùng chung cho luật, validate_tags và ai_tagger.
CONFLICTS = [
    frozenset({"quiet", "lively"}),
    frozenset({"budget", "mid"}),
    frozenset({"budget", "high"}),
    frozenset({"mid", "high"}),
]
 
# Tag hợp lệ theo loại địa điểm. Loại không có trong bảng được phép dùng mọi tag.
_HOTEL_ONLY = {"pool", "spa"} | set(TAXONOMY["amenity"])

_RESTAURANT_ONLY = (
    set(TAXONOMY["cuisine"]) | set(TAXONOMY["service"]) | set(TAXONOMY["price"])
)
_CULTURE_ONLY = (
    set(TAXONOMY["venue"]) | set(TAXONOMY["theme"]) | set(TAXONOMY["visit"])
)
CATEGORY_TAGS = {
    "cat-hotel": ALLOWED_TAGS - _RESTAURANT_ONLY - _CULTURE_ONLY,
    "cat-cafe": ALLOWED_TAGS - _HOTEL_ONLY - _RESTAURANT_ONLY - _CULTURE_ONLY,
        "cat-park": {
        "quiet", "lively", "romantic", "family", "couple", "solo", "lake-view",
        "spacious", "outdoor", "garden", "green",
    },
    "cat-culture": {
        "quiet", "lively", "family", "couple", "solo", "lake-view",
        "classic", "neoclassical", "modern", "minimalist", "indochine",
        "spacious", "outdoor", "garden", "green",
    } | _CULTURE_ONLY,
    "cat-restaurant": ALLOWED_TAGS - _HOTEL_ONLY - _CULTURE_ONLY,
}
 
 
def allowed_tags_for(category: str | None) -> set:
    """Trả về tập tag hợp lệ cho loại địa điểm; không rõ loại thì cho phép tất cả."""
    return CATEGORY_TAGS.get(category, ALLOWED_TAGS)
 
 
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
    "cozy": "ấm cúng", "friends": "phù hợp nhóm bạn",
    "noodle": "có bún, phở, miến", "rice": "có món cơm", "porridge": "có món cháo",
    "grill": "có món nướng", "hotpot": "có món lẩu", "seafood": "có ốc, hải sản",
    "snack": "có món ăn vặt",
    "late-night": "mở cửa đến khuya", "street-food": "là quán vỉa hè",
    "air-conditioned": "có máy lạnh",
    "budget": "giá bình dân", "mid": "giá tầm trung", "high": "giá cao cấp",
    "temple": "là chùa", "shrine": "là đền, đình hoặc miếu",
    "museum": "là bảo tàng", "heritage": "là di tích",
    "history": "mang giá trị lịch sử", "art": "mang giá trị nghệ thuật",
    "spiritual": "mang yếu tố tâm linh",
    "free-entry": "miễn phí vé", "dress-code": "cần ăn mặc kín đáo",
    "guided-tour": "có thuyết minh", "interactive": "có hoạt động trải nghiệm",
    "spacious": "có không gian rộng rãi",
    "outdoor": "có không gian ngoài trời",
    "garden": "có sân vườn",
    "rooftop": "có sân thượng",
    "private-room": "có phòng riêng",
    "green": "có nhiều cây xanh",
    "wifi": "có wifi", "shuttle": "có xe đưa đón", "parking": "có chỗ đỗ xe",
    "gym": "có phòng gym", "reception-24h": "có lễ tân 24/7",
    "laundry": "có dịch vụ giặt ủi", "pet-friendly": "cho phép mang thú cưng",
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
        r"ít ồn",
        r"tránh được sự ồn",
        r"không ồn",
        r"cách âm",
    ],
 
    "lively": [
        r"sôi động",
        r"náo nhiệt",
        r"vui nhộn",
        r"nhộn nhịp",
        r"đông vui",
        r"tấp nập",
    ],
    "romantic": [r"lãng mạn", r"bữa tối nến", r"hẹn hò"],
    # Loại "nhà hàng gia đình", "kinh doanh gia đình", "do gia đình" (chủ sở hữu).
    "family": [
        r"(?<!kinh doanh )(?<!do )gia đình",
        r"trẻ em", r"trẻ nhỏ", r"cho bé",
    ],
    "couple": [r"cặp đôi", r"trăng mật", r"massage đôi"],
    "solo": [r"đi một mình", r"ở một mình", r"du lịch bụi"],
    # "bàn làm việc", "khu làm việc" có ở gần như mọi phòng nên đã bỏ;
    # "công tác" đứng một mình khớp cả "công tác vệ sinh".
    "business": [
        r"doanh nhân", r"đi công tác", r"khách công tác", r"chuyến công tác",
        r"phòng họp",
    ],
    # "bên hồ", "mặt nước" chỉ vị trí, chưa chắc có view.
    "lake-view": [
        r"view hồ", r"view mặt hồ", r"nhìn ra hồ", r"nhìn ra mặt hồ",
        r"hướng hồ", r"hướng ra hồ",
    ],
    "balcony": [r"ban công"],
    "pool": [r"hồ bơi", r"bể bơi"],
    # "ẩm thực", "hải sản" đứng một mình quá chung nên đã bỏ.
    "local-food": [
        r"quán phở", r"đặc sản", r"món ăn truyền thống",
        r"ẩm thực (?:địa phương|truyền thống|việt|hà nội)",
        r"cà phê trứng", r"bún chả", r"bánh cuốn",
    ],
    "breakfast": [r"bữa sáng", r"ăn sáng", r"buffet sáng"],
    "spa": [r"\bspa\b", r"mát[\s-]?xa", r"massage", r"trị liệu", r"chăm sóc cơ thể"],
    "classic": [
        r"cổ kính",
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
 
    # Bỏ "cao cấp" (đồ dùng cao cấp), "grand", "resort" (thường nằm trong tên).
    "luxury": [
        r"sang trọng", r"đẳng cấp", r"xa hoa",
        r"thượng lưu", r"\b5 sao\b", r"năm sao",
        r"\bluxury\b",
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
 
    # --- nhà hàng ---
    "cozy": [r"ấm cúng"],
    "friends": [r"bạn bè", r"nhóm bạn", r"tụ tập"],
    "noodle": [r"\bbún\b", r"\bphở\b", r"\bmiến\b"],
    "rice": [r"\bcơm\b"],
    "porridge": [r"\bcháo\b"],
    "grill": [r"nướng"],
    "hotpot": [r"\blẩu\b"],
    "seafood": [r"\bốc\b", r"hải sản"],
    "snack": [r"ăn vặt", r"nem chua rán", r"bánh tráng trộn", r"\bnộm\b"],
    "street-food": [r"vỉa hè"],
    "air-conditioned": [r"máy lạnh", r"điều hòa"],
    # "price" và "late-night" không có luật: suy ra từ dữ liệu (price_tag, late_night_tag).
 
    # --- chùa, bảo tàng, văn hóa ---
    "temple": [r"\bchùa\b", r"thiền viện", r"tu viện"],
    # (?<!gia ) để "gia đình" không bị tính là "đình".
    "shrine": [r"\bđền\b", r"(?<!gia )\bđình\b", r"\bmiếu\b"],
    "museum": [r"bảo tàng"],
    "heritage": [r"di tích", r"di sản", r"thành cổ", r"hoàng thành"],
    "history": [r"lịch sử", r"hiện vật", r"cổ vật"],
    "art": [r"nghệ thuật", r"mỹ thuật", r"điêu khắc", r"phòng tranh"],
    "spiritual": [r"tâm linh", r"cầu an", r"thờ phật", r"thờ thần"],
    "free-entry": [r"miễn phí", r"không mất phí", r"không thu phí"],
    "dress-code": [
        r"trang phục (?:kín đáo|lịch sự|nghiêm túc)",
        r"ăn mặc (?:kín đáo|lịch sự)",
    ],
    "guided-tour": [r"hướng dẫn viên", r"thuyết minh"],
    "interactive": [r"tương tác", r"workshop", r"hoạt động trải nghiệm"],

        # --- không gian ---
    "spacious": [r"không gian rộng", r"rộng rãi", r"thoáng đãng", r"thoáng mát"],
    "outdoor": [r"ngoài trời", r"không gian mở"],
    "garden": [r"sân vườn", r"khu vườn", r"vườn cây"],
    "rooftop": [r"\brooftop\b", r"sân thượng", r"tầng thượng"],
    "private-room": [r"phòng riêng", r"phòng vip", r"phòng kín"],
    "green": [r"nhiều cây xanh", r"cây xanh", r"xanh mát", r"không gian xanh"],

    "wifi": [r"\bwi-?fi\b", r"internet (?:miễn phí|tốc độ cao)"],
    "shuttle": [
        r"xe đưa đón", r"đưa đón (?:sân bay|khách)", r"đón tiễn", r"xe đón",
        r"airport shuttle",
    ],
    "parking": [r"bãi đỗ xe", r"chỗ đậu xe", r"chỗ đỗ xe", r"bãi giữ xe", r"\bparking\b"],
    "gym": [r"phòng gym", r"phòng tập", r"\bgym\b", r"fitness"],
    "reception-24h": [r"lễ tân 24", r"lễ tân (?:hoạt động )?24/7", r"phục vụ 24/7", r"24/7"],
    "laundry": [r"giặt ủi", r"giặt là", r"dịch vụ giặt"],
    "pet-friendly": [r"thú cưng", r"vật nuôi", r"pet[\s-]?friendly"],
}
 
 
# Phát hiện từ phủ định đứng ngay trước bằng chứng (trong cùng mệnh đề).
# Loại trừ các cụm không mang nghĩa phủ định:
#   "không gian", "không khí", "không chỉ", "không những", "không thể thiếu", "chưa kể".
NEG_PREFIX = re.compile(
    r"\b(?:không(?!\s+(?:gian|khí|chỉ|những|thể\s+thiếu))|chưa(?!\s+kể)|chẳng)"
    r"(?:\s+hề)?(?:\s+\w+){0,2}\s*$"
)
 
# Dấu câu ngăn phủ định lan sang mệnh đề khác.
_CLAUSE_BREAK = re.compile(r"[.,;:!?\n]")

def rule_tags_with_evidence(text: str, category: str | None = None) -> dict:
    """
    Gán tag bằng luật regex.

    Args:
        text: Nội dung mô tả.
        category: Slug loại địa điểm (vd. "cat-park"); nếu có, chỉ gán tag hợp lệ
            với loại đó.

    Returns:
        dict {tag: đoạn văn bản làm bằng chứng}.
    """
    # NFC để regex không trượt khi dữ liệu crawl ở dạng NFD.
    text = unicodedata.normalize("NFC", clean_text(text)).lower()
    allowed = allowed_tags_for(category)
    found = {}

    for tag, patterns in TAG_RULES.items():
        if tag not in allowed:
            continue

        for pattern in patterns:
            for match in re.finditer(pattern, text):
                raw_prefix = text[max(0, match.start() - 25):match.start()]
                prefix = _CLAUSE_BREAK.split(raw_prefix)[-1]

                if NEG_PREFIX.search(prefix):
                    continue

                found[tag] = match.group(0)
                break

            if tag in found:
                break

    # Tag mâu thuẫn: bỏ cả hai vì luật không đủ thông tin để chọn bên nào đúng.
    for pair in CONFLICTS:
        if pair <= set(found):
            for tag in pair:
                found.pop(tag)

    return found


def validate_tags(tags: list, category: str | None = None) -> list:
    errors = []

    if len(tags) != len(set(tags)):
        errors.append("nhãn trùng")

    allowed = allowed_tags_for(category)

    for tag in tags:
        if tag not in ALLOWED_TAGS:
            errors.append(f"nhãn ngoài danh sách: {tag!r}")
        elif tag not in allowed:
            errors.append(f"nhãn không phù hợp loại {category!r}: {tag!r}")

    for pair in CONFLICTS:
        if pair <= set(tags):
            errors.append("xung đột: " + " + ".join(sorted(pair)))

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
