import re
import time
from html import unescape
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import config as cfg

# ------------------------------------------------------------------ vùng nội dung chính + văn bản
NOISE_TAGS = ["script", "style", "noscript", "svg", "nav", "header", "footer", "aside"]
# So khớp theo TỪNG tên class (không so chuỗi con) để "has-sidebar", "right-sidebar" của khối bọc cả bài không bị xóa nhầm
NOISE_TOKEN_RE = re.compile(
    r"^(comments?|comment[-_].*|respond|related.*|sidebar.*|share.*|social.*|cookie.*|popup.*|breadcrumbs?.*)$",
    re.I,
)


def drop_noise_blocks(root):
    for el in root.find_all(True):
        if el.attrs is None:
            continue
        tokens = list(el.get("class", [])) + [el.get("id") or ""]
        if any(NOISE_TOKEN_RE.match(t) for t in tokens if t) and len(el.get_text(strip=True)) < 2500:
            el.extract()


def get_content_root(html_text):
    # Trả về (khối nội dung, selector đã dùng, tiêu đề trang)
    soup = BeautifulSoup(html_text, "html.parser")

    title_el = soup.find("h1") or soup.title
    title = title_el.get_text(" ", strip=True) if title_el else ""

    for el in soup.find_all(NOISE_TAGS):
        el.extract()

    root, used = None, None
    for sel in cfg.CONTENT_SELECTORS:                   # xác định vùng nội dung TRƯỚC
        els = soup.select(sel)
        ids = {id(e) for e in els}
        els = [e for e in els if not any(id(p) in ids for p in e.parents)]
        if els and sum(len(e.get_text(strip=True)) for e in els) >= cfg.MIN_CONTENT_CHARS:
            root = BeautifulSoup("<div></div>", "html.parser").div
            for e in els:
                root.append(e.extract())
            used = sel
            break
    if root is None:
        root, used = (soup.body or soup), "body"

    drop_noise_blocks(root)                             # rồi mới dọn bình luận/bài liên quan BÊN TRONG vùng đó
    return root, used, title


def root_text(root, title):
    text = root.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return (f"TIÊU ĐỀ TRANG: {title}\n" if title else "") + text


# ------------------------------------------------------------------ ảnh
UI_WORDS = ("logo", "icon", "sprite", "avatar", "gravatar", "payment", "flag", "placeholder",
            "spinner", "loading", "emoji", "pixel", "blank", "button", "arrow",
            "facebook", "instagram", "youtube", "tiktok", "twitter", "zalo")
THUMB_RE = re.compile(r"-(\d{2,4})x(\d{2,4})(?=\.\w{3,5}$)")


def img_src(img):
    for attr in ("data-src", "data-original", "data-lazy-src", "data-lazy", "src"):
        v = img.get(attr)
        if v and not v.strip().startswith("data:"):
            return v.strip()
    srcset = img.get("data-srcset") or img.get("srcset")
    if srcset:
        parts = [p.strip().split()[0] for p in srcset.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return None


def extract_images(root, page_url, max_images=None):
    max_images = max_images or cfg.MAX_IMAGES
    images, seen = [], set()
    heading = ""
    for el in root.find_all(["h1", "h2", "h3", "h4", "img"]):
        if el.name != "img":
            heading = el.get_text(" ", strip=True)
            continue

        src = img_src(el)
        if not src:
            continue
        url = urljoin(page_url, src)
        p = urlparse(url)
        path = unquote(p.path).lower()
        if p.scheme not in ("http", "https") or path.endswith((".svg", ".ico", ".gif")):
            continue
        if any(w in path for w in UI_WORDS):
            continue

        alt = (el.get("alt") or "").strip()
        title = (el.get("title") or "").strip()
        meta = " ".join([alt, title, " ".join(el.get("class", []))]).lower()
        if any(w in meta for w in ("logo", "icon", "sprite")):
            continue

        try:
            w, h = int(el.get("width", 0)), int(el.get("height", 0))
            if (w and w < 100) or (h and h < 80):
                continue
        except (TypeError, ValueError):
            pass

        m = THUMB_RE.search(path)
        if m and int(m.group(1)) < 200 and int(m.group(2)) < 200:
            continue

        key = (p.netloc, THUMB_RE.sub("", path))   # bỏ hậu tố -300x200 để loại ảnh trùng
        if key in seen:
            continue
        seen.add(key)

        images.append({"url": url, "alt": alt, "title": title, "heading": heading})
        if len(images) >= max_images:
            break
    return images


# ------------------------------------------------------------------ link / bản đồ Google Maps
MAP_HOSTS = ("maps.app.goo.gl", "goo.gl/maps", "google.com/maps", "google.com.vn/maps", "maps.google.")
SHORT_HOSTS = ("maps.app.goo.gl", "goo.gl/maps")

PIN_RE = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")                       # vị trí ghim: (lat, lng)
EMBED_RE = re.compile(r"!2d(-?\d+\.\d+)!3d(-?\d+\.\d+)")                      # bản đồ nhúng: (lng, lat)
AT_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")                             # tâm bản đồ: (lat, lng)
QLL_RE = re.compile(r"[?&](?:q|ll|query|destination)=(-?\d+\.\d+),(-?\d+\.\d+)")
EMBED_URL_RE = re.compile(r"https://www\.google\.com/maps/embed\?pb=[^\"'\s<>\\]+")


def parse_coords(text):
    # Trả về (lat, lng) từ URL/văn bản Google Maps, ưu tiên vị trí ghim
    if not text:
        return None, None
    text = unquote(text)
    m = PIN_RE.search(text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = EMBED_RE.search(text)
    if m:
        return float(m.group(2)), float(m.group(1))
    m = AT_RE.search(text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = QLL_RE.search(text)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


_coord_cache = {}


def coords_from_ref(ref):
    url = ref["url"]
    if url in _coord_cache:
        return _coord_cache[url]
    lat, lng = parse_coords(url)
    if lat is None and any(h in url for h in SHORT_HOSTS):
        try:
            r = requests.get(url, headers=cfg.HEADERS, allow_redirects=True, timeout=20)
            lat, lng = parse_coords(r.url)
            if lat is None:
                lat, lng = parse_coords(r.text)
            time.sleep(1)
        except requests.RequestException:
            pass
    _coord_cache[url] = (lat, lng)
    return lat, lng


def get_map_refs(root, raw_html, page_url):
    refs, seen = [], set()
    heading = ""
    for el in root.find_all(["h1", "h2", "h3", "h4", "a", "iframe"]):
        if el.name in ("h1", "h2", "h3", "h4"):
            heading = el.get_text(" ", strip=True)
            continue
        if el.name == "a":
            raw = el.get("href")
        else:
            raw = el.get("src") or el.get("data-src") or el.get("data-lazy-src")
        if not raw:
            continue
        url = urljoin(page_url, unescape(raw.strip()))
        if not any(h in url for h in MAP_HOSTS) or url in seen:
            continue
        seen.add(url)
        refs.append({
            "url": url,
            "text": el.get_text(" ", strip=True) if el.name == "a" else "",
            "heading": heading,
            "kind": "embed" if el.name == "iframe" else "link",
        })
    # Dự phòng: bản đồ nhúng nằm trong script / thuộc tính lazy-load
    for m in EMBED_URL_RE.finditer(unescape(raw_html)):
        url = m.group(0)
        if url not in seen:
            seen.add(url)
            refs.append({"url": url, "text": "", "heading": "", "kind": "embed"})
    return refs


# ------------------------------------------------------------------ gộp các bước cho một trang
def prepare_page(page, verbose=True):
    # Thêm vào page: root, selector, title, text, images, map_refs
    root, used, title = get_content_root(page["html"])
    page.update(root=root, selector=used, title=title, text=root_text(root, title))
    page["images"] = extract_images(root, page["url"])
    page["map_refs"] = get_map_refs(root, page["html"], page["url"])

    if verbose:
        heads = [h.get_text(" ", strip=True) for h in root.find_all(["h2", "h3"])]
        kinds = [r["kind"] for r in page["map_refs"]]
        print("\nTrang:", page["url"])
        print("Selector dùng:", used, "| Độ dài văn bản:", len(page["text"]))
        print("Số tiêu đề h2/h3:", len(heads))
        for h in heads[:15]:
            print("  -", h)
        print("Số ảnh sau lọc:", len(page["images"]))
        print("Link bản đồ:", kinds.count("link"), "| Bản đồ nhúng:", kinds.count("embed"))
        if len(page["text"]) < cfg.MIN_CONTENT_CHARS:
            print("CẢNH BÁO: văn bản quá ngắn, kiểm tra lại CONTENT_SELECTORS.")
        print("--- 500 ký tự đầu ---")
        print(page["text"][:500])
    return page
