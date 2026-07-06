# Traceable — Agentic Web Search

Type a topic, get a structured table of entities extracted from the web — every cell linked back to the exact quote it came from.

**Live demo:** https://traceable-search.fly.dev

## What it does

1. Takes any topic query (e.g. "AI startups in healthcare", "best ramen in Tokyo")
2. Searches the web via Serper (Google Search API)
3. Scrapes and cleans the top results with `trafilatura`
4. Sends each page to an LLM (via OpenRouter) to extract entities and attributes, with a verbatim supporting quote per value
5. Merges entities found across multiple pages, keeping all source citations
6. Returns a table where hovering any cell shows the exact quote + source link

## Stack

- **Backend:** Python, FastAPI, httpx
- **Search:** Serper (Google Search API)
- **Scraping:** trafilatura
- **LLM:** OpenRouter (default: `anthropic/claude-3.5-haiku`, swappable)
- **Deploy:** Fly.io (Docker)

## Local setup

```bash
git clone https://github.com/yourusername/traceable
cd traceable
python3 -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add SERPER_API_KEY and LLM_API_KEY
uvicorn app.main:app --reload
```

Open http://localhost:8000

**Get API keys (both free):**
- Serper: https://serper.dev — 2,500 free queries/month, no credit card
- OpenRouter: https://openrouter.ai/keys — pay-per-token, claude-3.5-haiku costs ~$0.01-0.05 per query

## Deploy to Render (free, no credit card)

1. Push your code to a public GitHub repo
2. Go to https://render.com and sign up with GitHub
3. Click **New → Blueprint** and select your repo — Render picks up `render.yaml` automatically
4. In the dashboard, open your service → **Environment** and add:
   - `SERPER_API_KEY` = your key from serper.dev
   - `LLM_API_KEY` = your key from openrouter.ai
5. Click **Deploy**

Your app will be live at `https://traceable-search.onrender.com` (or whatever name you pick).

To update: just `git push` — Render auto-deploys on every push to main.

> **Note:** The free tier sleeps after 15 minutes of inactivity. The first request after idle takes ~30 seconds to wake up. This is fine for a portfolio link — just warn visitors or add a note on the page.

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `SERPER_API_KEY` | — | Required. From serper.dev |
| `LLM_API_KEY` | — | Required. From openrouter.ai |
| `LLM_MODEL` | `anthropic/claude-3.5-haiku` | Any OpenRouter model string |
| `LLM_BASE_URL` | OpenRouter | Swap for OpenAI, local Ollama, etc. |
| `SEARCH_RESULTS_PER_QUERY` | `8` | More = better coverage, slower |
| `MAX_PAGES_TO_SCRAPE` | `8` | Cap on pages fetched |
| `MAX_CHARS_PER_PAGE` | `8000` | Truncation limit per page (cost control) |
| `MAX_CONCURRENT_SCRAPES` | `5` | Parallel scrape workers |
| `MAX_CONCURRENT_LLM_CALLS` | `4` | Parallel LLM requests |

## Design decisions

**One LLM call per page, not one call for the whole batch.** Keeps each call's context small (cheaper, faster, less chance of hallucination) and isolates failures — one bad page doesn't abort the run.

**Evidence quotes are required per attribute.** Every cell value is backed by a verbatim snippet from the source text. This is the core traceability mechanism — not just "the LLM said so."

**Fuzzy name deduplication.** The same entity appears across sources under different names ("OpenAI Inc.", "OpenAI"). Dedup uses normalized token-set overlap + character similarity, so legal suffixes and minor formatting differences don't prevent merging.

**trafilatura over raw HTML parsing.** Purpose-built for extracting article body text from arbitrary HTML. Handles a much wider range of real-world sites than hand-written selectors would.

## Known limitations

- No JavaScript rendering — pages that require JS to display content (heavy SPAs) will scrape as empty
- Entity dedup is heuristic, not semantic — "Facebook" and "Meta" won't merge; genuinely ambiguous names may over- or under-merge
- No retry logic on transient scrape/LLM failures
- Latency is ~15-30s per query (dominated by LLM calls) — not suitable for real-time autocomplete
