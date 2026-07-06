"""
FastAPI app exposing the agentic search pipeline.

Run with: uvicorn app.main:app --reload
"""
import logging
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.pipeline import run_pipeline

# Enable logging so pipeline steps print to terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(title="Traceable — Agentic Search")


class SearchRequest(BaseModel):
    topic: str


@app.post("/api/search")
async def search(req: SearchRequest):
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic must not be empty")
    try:
        result = await run_pipeline(topic)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Pipeline error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")
    return result


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/api/debug")
async def debug(topic: str = "coffee shops in NYC"):
    """
    Call this in your browser: http://localhost:8000/api/debug?topic=your+topic
    Tests each pipeline stage and returns exactly what each step produces.
    """
    from app.search import search_web
    from app.scrape import scrape_pages
    from app.extract import extract_entities_from_page

    result = {"topic": topic, "stages": {}}

    # Stage 1: Search
    try:
        search_results = await search_web(topic)
        urls = [r.url for r in search_results]
        result["stages"]["search"] = {
            "ok": True,
            "count": len(urls),
            "urls": urls[:5],
        }
    except Exception as e:
        result["stages"]["search"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return result

    # Stage 2: Scrape first URL only
    try:
        pages = await scrape_pages(urls[:1])
        p = pages[0]
        result["stages"]["scrape"] = {
            "ok": p.success,
            "url": p.url,
            "title": p.title,
            "chars": len(p.text),
            "preview": p.text[:300] if p.text else None,
            "error": p.error,
        }
    except Exception as e:
        result["stages"]["scrape"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return result

    # Stage 3: LLM extract
    try:
        successful = [p for p in pages if p.success]
        if successful:
            entities = await extract_entities_from_page(topic, successful[0])
            result["stages"]["extract"] = {
                "ok": True,
                "entity_count": len(entities),
                "entities": [
                    {"name": e.name, "attributes": list(e.attributes.keys())}
                    for e in entities[:5]
                ],
            }
        else:
            result["stages"]["extract"] = {"ok": False, "error": "no successfully scraped pages"}
    except Exception as e:
        result["stages"]["extract"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return result