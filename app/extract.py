"""
Uses an LLM to pull structured entities + attributes out of raw page text,
given the user's topic query. This is the core "agentic search" step.

Key design choice: we ask the model to return, for every attribute value,
a short verbatim supporting snippet from the page. That snippet is what
lets the frontend show "traceable to source" — clicking a cell can show
the exact quote + link it came from, not just a bare LLM claim.

We use JSON mode / strict prompting rather than function-calling tool use,
since this needs to run against arbitrary OpenAI-compatible endpoints
(OpenRouter, local models, etc.) where tool-calling support is inconsistent.
"""
import json
import re
import httpx
from dataclasses import dataclass, field
from app import config
from app.scrape import ScrapedPage


@dataclass
class ExtractedAttribute:
    value: str
    evidence: str  # short verbatim quote supporting this value


@dataclass
class ExtractedEntity:
    name: str
    attributes: dict[str, ExtractedAttribute]
    source_url: str


EXTRACTION_SYSTEM_PROMPT = """You are a precise information extraction engine.

You will be given:
1. A topic/query describing what kind of entities the user is looking for.
2. The text content of one web page.

Your job: identify any distinct entities in the page text that are clearly
relevant to the topic (e.g. companies, restaurants, tools, people, products —
whatever kind of entity the topic implies). For each entity, extract a small
set of useful attributes.

Rules:
- Only extract entities that are explicitly mentioned in the provided text. Never invent or guess.
- Every attribute value MUST be accompanied by a short, verbatim quote ("evidence") from the text that supports it. Keep quotes under 25 words.
- If a useful attribute isn't supported by the text, omit it rather than guessing.
- If the page contains no relevant entities, return an empty list.
- Return STRICT JSON only. No markdown, no commentary, no code fences.

Output schema:
{
  "entities": [
    {
      "name": "Entity Name",
      "attributes": {
        "attribute_key": {"value": "...", "evidence": "..."},
        ...
      }
    }
  ]
}
"""


def _build_user_prompt(topic: str, page: ScrapedPage) -> str:
    return (
        f"TOPIC: {topic}\n\n"
        f"PAGE URL: {page.url}\n"
        f"PAGE TITLE: {page.title}\n\n"
        f"PAGE TEXT:\n{page.text}\n\n"
        "Extract relevant entities as JSON per the schema."
    )


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def extract_entities_from_page(topic: str, page: ScrapedPage) -> list[ExtractedEntity]:
    if not page.success or not page.text:
        return []

    payload = {
        "model": config.LLM_MODEL,
        "max_tokens": 2000,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(topic, page)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Traceable Search",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{config.LLM_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    raw_text = data["choices"][0]["message"]["content"]
    raw_text = _strip_code_fences(raw_text)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # Model occasionally wraps JSON in stray text despite instructions.
        # Try to salvage by grabbing the outermost {...} block.
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

    entities = []
    for raw_entity in parsed.get("entities", []):
        name = raw_entity.get("name", "").strip()
        if not name:
            continue
        attrs = {}
        for key, val in raw_entity.get("attributes", {}).items():
            if isinstance(val, dict) and "value" in val:
                attrs[key] = ExtractedAttribute(
                    value=str(val.get("value", "")).strip(),
                    evidence=str(val.get("evidence", "")).strip(),
                )
        entities.append(ExtractedEntity(name=name, attributes=attrs, source_url=page.url))

    return entities
