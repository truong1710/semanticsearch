import re
from difflib import SequenceMatcher

import numpy as np

from .config import CATEGORY_MARGIN, CATEGORY_THR, TAG_THR
from .embeddings import embed_dense
from .taxonomy import TAG_RULES
from .text_utils import fold


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
}


def _build_protos(protos):
    return {k: _unit(embed_dense(v)) for k, v in protos.items()}


CAT_VECS = _build_protos(CATEGORY_PROTOTYPES)
TAG_VECS = _build_protos(TAG_PROTOTYPES)


def similarities(q_vec, vecs):
    return {k: float((m @ q_vec).max()) for k, m in vecs.items()}


CATEGORY_KEYWORDS = {
    "cat-hotel": ["khach san", "hotel", "resort", "noi nghi", "cho nghi"],
    "cat-cafe": ["ca phe", "cafe", "coffee", "phong tra"],
    "cat-park": ["cong vien", "vuon hoa"],
    "cat-culture": ["bao tang", "di tich", "dia diem van hoa"],
    "cat-restaurant": ["quan an", "nha hang", "quan pho", "quan bun", "an uong", "mon an"],
}


def keyword_category(q_fold, q_raw):
    matched = {c for c, kws in CATEGORY_KEYWORDS.items() if any(k in q_fold for k in kws)}
    if "chùa" in q_raw.lower():
        matched.add("cat-culture")
    return matched.pop() if len(matched) == 1 else None


def route_category(q_vec, q_fold, q_raw=""):
    scores = similarities(q_vec, CAT_VECS)
    kw = keyword_category(q_fold, q_raw)
    if kw:
        return kw, scores
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    (c1, s1), (_, s2) = ranked[0], ranked[1]
    if s1 >= CATEGORY_THR and s1 - s2 >= CATEGORY_MARGIN:
        return c1, scores
    return None, scores


QUERY_TAG_RULES = {tag: [fold(p) for p in pats] for tag, pats in TAG_RULES.items()}
QUERY_TAG_RULES["romantic"] += ["nguoi yeu", "ky niem"]
QUERY_TAG_RULES["couple"] += ["nguoi yeu", "vo chong"]
QUERY_TAG_RULES["quiet"] += ["thu gian", "tranh on"]


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
            plain = re.fullmatch(r"[a-z ]{6,}", p) is not None
            if re.search(p, q_fold) or (plain and fuzzy_contains(p, q_fold)):
                tags.add(tag)
                break
    for tag, s in similarities(q_vec, TAG_VECS).items():
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