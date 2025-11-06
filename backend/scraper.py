# scraper.py
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse

# accept desktop and mobile subdomains (e.g., en.wikipedia.org, en.m.wikipedia.org)
WIKI_RE = re.compile(r"^https?://([a-z0-9-]+\.)*wikipedia\.org/wiki/", re.I)

class ScrapeError(Exception):
    pass

def validate_wikipedia_url(url: str) -> None:
    if not WIKI_RE.match(url):
        raise ScrapeError("Only Wikipedia article URLs are allowed (HTML scraping only).")

# Browser-like headers so Wikipedia doesn't block us
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

def _fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    if resp.status_code == 403:
        raise ScrapeError("Forbidden (403) from Wikipedia")
    if resp.status_code != 200:
        raise ScrapeError(f"Failed to fetch page: HTTP {resp.status_code}")
    return resp.text

def _to_mobile(url: str) -> str:
    """Convert desktop wiki URL to mobile if needed."""
    p = urlparse(url)
    host = p.netloc
    if host.endswith("wikipedia.org") and not host.endswith(".m.wikipedia.org"):
        if host.count(".") >= 2:
            host = host.replace(".wikipedia.org", ".m.wikipedia.org")
        else:
            host = "en.m.wikipedia.org"
    return urlunparse((p.scheme, host, p.path, p.params, p.query, p.fragment))

def scrape_wikipedia(url: str):
    """
    Returns (title, summary_text, text_blob, raw_html).
    """
    validate_wikipedia_url(url)

    try:
        html = _fetch(url)
    except ScrapeError:
        # Retry with mobile domain
        mobile_url = _to_mobile(url)
        html = _fetch(mobile_url)

    soup = BeautifulSoup(html, "html.parser")

    # Title
    title_tag = soup.find(id="firstHeading")
    title = title_tag.get_text(strip=True) if title_tag else (soup.title.get_text(strip=True) if soup.title else url)

    # Content (desktop & mobile-friendly)
    content = soup.find(id="mw-content-text") or soup.find("div", {"class": "content"}) or soup

    # Gather paragraphs + headings
    parts = []
    for el in content.select("p, h2, h3, h4"):
        text = el.get_text(" ", strip=True)
        if text:
            parts.append(text)
    text_blob = "\n".join(parts)

    # Summary = first 3 paragraphs
    summary = "\n".join([p.get_text(" ", strip=True) for p in content.select("p")][:3]) or title

    # Limit size for LLM cost
    MAX_CHARS = 12000
    if len(text_blob) > MAX_CHARS:
        text_blob = text_blob[:MAX_CHARS]

    return title, summary, text_blob, html
