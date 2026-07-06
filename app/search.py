"""
Thin wrapper around Serper (Google Search API).

Why Serper: 2,500 free queries/month, no credit card required,
simple REST API. Sign up at https://serper.dev to get a key.
Swap this module out for any other provider if you prefer —
the rest of the pipeline only depends on the SearchResult shape below.
"""
import httpx
from dataclasses import dataclass
from app import config


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


async def search_web(query: str, count: int = None) -> list[SearchResult]:
    count = count or config.SEARCH_RESULTS_PER_QUERY

    if not config.SERPER_API_KEY:
        raise RuntimeError(
            "SERPER_API_KEY is not set. Get a free key (2,500 queries/month) at https://serper.dev"
        )

    headers = {
        "X-API-KEY": config.SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": count}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://google.serper.dev/search",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("organic", []):
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
            )
        )
    return results
