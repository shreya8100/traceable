"""
Central configuration. All secrets come from environment variables —
see .env.example for the full list.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Search ---
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SEARCH_RESULTS_PER_QUERY = int(os.getenv("SEARCH_RESULTS_PER_QUERY", "8"))

# --- LLM (OpenRouter by default; swap base_url/key for OpenAI, etc.) ---
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-3.5-haiku")

# --- Scraping ---
MAX_PAGES_TO_SCRAPE = int(os.getenv("MAX_PAGES_TO_SCRAPE", "8"))
SCRAPE_TIMEOUT_SECONDS = int(os.getenv("SCRAPE_TIMEOUT_SECONDS", "10"))
MAX_CHARS_PER_PAGE = int(os.getenv("MAX_CHARS_PER_PAGE", "8000"))  # cost/latency control

# --- Concurrency ---
MAX_CONCURRENT_SCRAPES = int(os.getenv("MAX_CONCURRENT_SCRAPES", "5"))
MAX_CONCURRENT_LLM_CALLS = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", "4"))

# --- Merge ---
ENTITY_NAME_SIMILARITY_THRESHOLD = float(os.getenv("ENTITY_NAME_SIMILARITY_THRESHOLD", "0.85"))
