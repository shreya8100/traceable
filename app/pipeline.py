"""
Orchestrates the full flow: search -> scrape -> extract -> merge.
This is the single entry point the API route calls.
"""
import asyncio
import logging
from app import config
from app.search import search_web
from app.scrape import scrape_pages
from app.extract import extract_entities_from_page
from app.merge import merge_entities, to_table_rows

log = logging.getLogger(__name__)


async def run_pipeline(topic: str) -> dict:
    # 1. Search
    log.info(f"[SEARCH] Querying for: '{topic}'")
    search_results = await search_web(topic)
    urls = [r.url for r in search_results][: config.MAX_PAGES_TO_SCRAPE]
    log.info(f"[SEARCH] Got {len(urls)} URLs: {urls}")

    if not urls:
        log.warning("[SEARCH] No URLs returned — check SERPER_API_KEY")
        return {"topic": topic, "rows": [], "stats": {"searched": 0, "scraped": 0, "scrape_failures": 0, "extracted_entities_raw": 0, "merged_entities": 0}}

    # 2. Scrape concurrently
    log.info(f"[SCRAPE] Fetching {len(urls)} pages...")
    scraped_pages = await scrape_pages(urls)
    successful_pages = [p for p in scraped_pages if p.success]
    failed_pages = [p for p in scraped_pages if not p.success]

    for p in failed_pages:
        log.warning(f"[SCRAPE] FAILED {p.url} — {p.error}")
    for p in successful_pages:
        log.info(f"[SCRAPE] OK {p.url} — {len(p.text)} chars")

    # 3. Extract concurrently
    semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_LLM_CALLS)

    async def bounded_extract(page):
        async with semaphore:
            try:
                log.info(f"[EXTRACT] Calling LLM for: {page.url}")
                entities = await extract_entities_from_page(topic, page)
                log.info(f"[EXTRACT] Got {len(entities)} entities from {page.url}")
                return entities
            except Exception as e:
                log.error(f"[EXTRACT] FAILED for {page.url} — {type(e).__name__}: {e}")
                return []

    extraction_results = await asyncio.gather(*[bounded_extract(p) for p in successful_pages])
    all_entities = [e for sublist in extraction_results for e in sublist]
    log.info(f"[EXTRACT] Total raw entities: {len(all_entities)}")

    # 4. Merge + format
    merged = merge_entities(all_entities)
    rows = to_table_rows(merged)
    rows.sort(key=lambda r: len(r["sources"]), reverse=True)
    log.info(f"[MERGE] {len(all_entities)} raw → {len(rows)} merged entities")

    stats = {
        "searched": len(urls),
        "scraped": len(successful_pages),
        "scrape_failures": len(failed_pages),
        "extracted_entities_raw": len(all_entities),
        "merged_entities": len(rows),
    }

    return {"topic": topic, "rows": rows, "stats": stats}