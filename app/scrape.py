"""
Fetches pages and extracts the main readable text, stripping nav/ads/boilerplate.
"""
import asyncio
import httpx
import trafilatura
from bs4 import BeautifulSoup
from dataclasses import dataclass
from app import config


@dataclass
class ScrapedPage:
    url: str
    title: str
    text: str
    success: bool
    error: str | None = None


# Realistic browser User-Agent — custom bot strings get blocked by many sites
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _extract_with_beautifulsoup(html: str) -> str:
    """Fallback extractor when trafilatura returns nothing."""
    soup = BeautifulSoup(html, "html.parser")
    # Remove noise tags
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


async def _fetch_one(client: httpx.AsyncClient, url: str) -> ScrapedPage:
    try:
        resp = await client.get(
            url,
            headers=_HEADERS,
            timeout=config.SCRAPE_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            return ScrapedPage(url=url, title="", text="", success=False, error=f"non-html content-type: {content_type}")

        html = resp.text

        # Try trafilatura first
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
            no_fallback=False,
        )

        # Fall back to BeautifulSoup if trafilatura got nothing
        if not extracted:
            extracted = _extract_with_beautifulsoup(html)

        if not extracted or len(extracted.strip()) < 100:
            return ScrapedPage(url=url, title="", text="", success=False, error="no extractable content")

        metadata = trafilatura.extract_metadata(html)
        title = metadata.title if metadata else ""

        return ScrapedPage(
            url=url,
            title=title or "",
            text=extracted[: config.MAX_CHARS_PER_PAGE],
            success=True,
        )

    except Exception as e:
        return ScrapedPage(url=url, title="", text="", success=False, error=str(e))


async def scrape_pages(urls: list[str]) -> list[ScrapedPage]:
    semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_SCRAPES)

    async def bounded_fetch(client, url):
        async with semaphore:
            return await _fetch_one(client, url)

    async with httpx.AsyncClient() as client:
        tasks = [bounded_fetch(client, url) for url in urls]
        return await asyncio.gather(*tasks)