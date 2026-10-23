import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from urllib.parse import parse_qsl, urljoin, urlparse

import requests

from . import config as cfg
from .extract import get_content_root, root_text
from .utils import clean_url

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
LOAD_MORE_RE = re.compile(r"xem thêm|tải thêm|hiển thị thêm|load more|show more", re.I)
FILE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".pdf", ".zip", ".mp4", ".doc", ".docx", ".xls", ".xlsx")

_session = None


def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(cfg.HEADERS)
    return _session


def fetch_static(url):
    r = _get_session().get(url, timeout=25)
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding or "utf-8"
    return r.status_code, r.text


def assess(html_text):
    # Trả về (selector tìm được, số ký tự văn bản trong vùng nội dung)
    root, used, title = get_content_root(html_text)
    return used, len(root_text(root, title))


def is_good(used, n):
    # "body" nghĩa là không selector nào khớp -> nhiều khả năng nội dung chưa được dựng
    return used != "body" and n >= cfg.MIN_CONTENT_CHARS


# ------------------------------------------------------------------ trình duyệt (Playwright)
_pw_ready = False


def ensure_playwright():
    global _pw_ready
    if _pw_ready:
        return
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  Đang cài playwright...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "playwright"], check=True)
    print("  Đang cài trình duyệt Chromium (lần đầu mất khoảng 1 phút)...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"],
                   check=True, capture_output=True)
    _pw_ready = True


def click_load_more(page):
    # Chỉ bấm các nút KHÔNG chuyển trang (button, role=button, link # hoặc javascript:) có chữ "Xem thêm"...
    for _ in range(cfg.LOAD_MORE_CLICKS):
        cands = page.locator("button, [role=button], a[href^='#'], a[href^='javascript']").filter(has_text=LOAD_MORE_RE)
        clicked = False
        for i in range(min(cands.count(), 5)):
            el = cands.nth(i)
            try:
                if not el.is_visible():
                    continue
                el.scroll_into_view_if_needed(timeout=2000)
                el.click(timeout=3000)
                page.wait_for_timeout(1000)
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            break


def render_html(url, scrolls=None):
    scrolls = cfg.BROWSER_SCROLLS if scrolls is None else scrolls
    ensure_playwright()

    def _run():
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=BROWSER_UA, locale="vi-VN")
                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                except Exception:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                for _ in range(scrolls):                  # cuộn để tải thêm danh sách
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(1000)
                click_load_more(page)                     # bấm "Xem thêm" nếu có
                return page.content()
            finally:
                browser.close()

    # chạy trong luồng riêng để không xung đột với vòng lặp sự kiện (Jupyter/Colab)
    with ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(_run).result()


# ------------------------------------------------------------------ tải nhiều trang
def load_pages(urls, delay=0.0):
    # Tải thường trước; nếu nội dung nghèo / lỗi thì thử trình duyệt; giữ bản có nhiều nội dung hơn
    out = []
    for i, raw_url in enumerate(urls):
        if i and delay:
            time.sleep(delay)
        url = clean_url(raw_url)
        print("\nURL:", url)
        html_text, how, used, n = None, None, None, 0

        if cfg.RENDER_MODE in ("auto", "static"):
            try:
                status, body = fetch_static(url)
                print("  Tải thường: HTTP", status, "| HTML", len(body), "ký tự")
                if status == 200:
                    html_text, how = body, "static"
                    used, n = assess(body)
                    print(f"  Vùng nội dung: {used} | văn bản: {n} ký tự")
                elif status == 403:
                    print("  -> 403: trang có thể chặn bot.")
            except requests.RequestException as e:
                print("  Lỗi khi tải thường:", e)

        static_ok = html_text is not None and is_good(used, n)
        if cfg.RENDER_MODE == "browser" or (cfg.RENDER_MODE == "auto" and not static_ok):
            print("  -> Dùng trình duyệt (RENDER_MODE = browser)..." if cfg.RENDER_MODE == "browser"
                  else "  -> Nội dung nghèo hoặc không tải được, thử dùng trình duyệt...")
            try:
                rendered = render_html(url)
                r_used, r_n = assess(rendered)
                print(f"  Trình duyệt: vùng nội dung: {r_used} | văn bản: {r_n} ký tự")
                if html_text is None or is_good(r_used, r_n) or r_n > 1.3 * n:
                    html_text, how = rendered, "browser"
            except Exception as e:
                print("  Không dùng được trình duyệt:", e)

        if html_text is None:
            print("  -> Bỏ qua trang này.")
            continue
        print("  HTML dùng để xử lý:", "từ trình duyệt" if how == "browser" else "tải thường")
        out.append({"url": url, "html": html_text, "fetched_by": how})

    print("\nĐã tải thành công:", len(out), "/", len(urls), "trang")
    return out


# ------------------------------------------------------------------ từ trang danh sách vào trang chi tiết
def link_template(url):
    # Dạng đường dẫn của link, ví dụ /hotels/a25-hotel và /hotels/nesta-hotel cùng là /hotels/{}
    p = urlparse(url)
    segs = [x for x in p.path.split("/") if x]
    head = segs[:-1] if segs else []
    keys = ",".join(sorted(k for k, _ in parse_qsl(p.query)))
    return "/" + "/".join(head + ["{}"]) + (f"?{keys}" if keys else "")


def collect_detail_links(page):
    root, used, _ = get_content_root(page["html"])
    base = page["url"]
    base_p = urlparse(base)
    found = {}
    for a in root.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        url = clean_url(urljoin(base, unescape(href)).split("#")[0])
        p = urlparse(url)
        if p.scheme not in ("http", "https") or p.netloc != base_p.netloc:
            continue
        if p.path.lower().endswith(FILE_EXTS):
            continue
        if p.path.rstrip("/") == base_p.path.rstrip("/"):     # chính trang này / liên kết phân trang
            continue
        found.setdefault(url, a.get_text(" ", strip=True))

    print(f"  Link nội bộ trong vùng nội dung: {len(found)}")
    if cfg.DETAIL_LINK_PATTERN:
        links = [u for u in found if re.search(cfg.DETAIL_LINK_PATTERN, u)]
        print(f"  Lọc theo DETAIL_LINK_PATTERN: {len(links)} link")
        return links

    groups = {}
    for u in found:
        groups.setdefault(link_template(u), []).append(u)
    ranked = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    for tpl, us in ranked[:5]:
        print(f"    {len(us):3d} link | {tpl:35} | vd: {us[0]}")
    if ranked and len(ranked[0][1]) >= 3:
        print("  -> Chọn nhóm:", ranked[0][0], "(nếu sai, đặt cfg.DETAIL_LINK_PATTERN)")
        return ranked[0][1]
    print("  -> Không có nhóm nào đủ 3 link, có thể trang mở chi tiết bằng JavaScript (không có link).")
    return []


def follow_detail_links(pages):
    # Nhận các trang danh sách, trả về các trang chi tiết (hoặc chính `pages` nếu không tìm được link)
    detail_urls = []
    for lp in pages:
        print("\nTrang danh sách:", lp["url"])
        detail_urls += collect_detail_links(lp)
    detail_urls = list(dict.fromkeys(detail_urls))
    print(f"\nTổng số link chi tiết tìm được: {len(detail_urls)} (sẽ lấy tối đa {cfg.MAX_DETAIL_PAGES})")
    detail_urls = detail_urls[:cfg.MAX_DETAIL_PAGES]
    if not detail_urls:
        print("Không có link chi tiết, giữ nguyên các trang đã tải.")
        return pages
    return load_pages(detail_urls, delay=cfg.DETAIL_DELAY)
