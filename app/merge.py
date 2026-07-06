"""
Merges ExtractedEntity objects across multiple source pages into a single
deduplicated table. The same real-world entity ("Acme Inc.", "Acme, Inc",
"Acme") often appears across several pages with different attributes
extracted on each — we merge by fuzzy name match and union the attributes,
keeping every contributing source per attribute so we never lose traceability.
"""
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from app.extract import ExtractedEntity
from app import config


@dataclass
class SourcedValue:
    value: str
    evidence: str
    source_url: str


@dataclass
class MergedEntity:
    name: str
    attributes: dict[str, list[SourcedValue]] = field(default_factory=dict)
    source_urls: set[str] = field(default_factory=set)


_LEGAL_SUFFIXES = {
    "inc", "inc.", "llc", "llc.", "ltd", "ltd.", "corp", "corp.",
    "corporation", "co", "co.", "company", "the",
}


def _normalize(name: str) -> str:
    """Lowercase, strip punctuation, drop common legal suffixes/filler words.
    This handles the common case of 'Acme, Inc.' vs 'Acme Inc' vs 'The Acme Company'."""
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    tokens = [t for t in cleaned.split() if t not in _LEGAL_SUFFIXES]
    return " ".join(tokens)


def _similarity(a: str, b: str) -> float:
    """
    Combines two signals: character-level similarity (catches typos/minor
    variants) and token-set overlap (catches reordering and legal-suffix
    noise). We take the max of the two so either signal can trigger a merge.

    Known limitation: this is still a heuristic. "Acme AI" and "Acme Health"
    could be genuinely different companies that happen to share a word, or
    the same company referred to inconsistently — pure string similarity
    can't always tell. A more robust version would resolve entities via
    canonical identifiers (domain name, LinkedIn URL, etc.) when available
    in the source text, or use an LLM-based "are these the same entity?"
    check for borderline cases instead of a fixed threshold.
    """
    norm_a, norm_b = _normalize(a), _normalize(b)
    char_sim = SequenceMatcher(None, norm_a, norm_b).ratio()

    tokens_a, tokens_b = set(norm_a.split()), set(norm_b.split())
    if tokens_a and tokens_b:
        token_sim = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    else:
        token_sim = 0.0

    return max(char_sim, token_sim)


def merge_entities(all_entities: list[ExtractedEntity]) -> list[MergedEntity]:
    merged: list[MergedEntity] = []

    for entity in all_entities:
        match = None
        for existing in merged:
            if _similarity(entity.name, existing.name) >= config.ENTITY_NAME_SIMILARITY_THRESHOLD:
                match = existing
                break

        if match is None:
            match = MergedEntity(name=entity.name)
            merged.append(match)

        match.source_urls.add(entity.source_url)
        for attr_key, attr_val in entity.attributes.items():
            sourced = SourcedValue(
                value=attr_val.value,
                evidence=attr_val.evidence,
                source_url=entity.source_url,
            )
            match.attributes.setdefault(attr_key, []).append(sourced)

    return merged


def to_table_rows(merged_entities: list[MergedEntity]) -> list[dict]:
    """
    Flattens MergedEntity objects into a plain-dict row format that's easy
    to serialize to JSON and render in a table. Each cell keeps its full
    list of sourced values so the frontend can show "3 sources agree" or
    flag conflicting values, rather than silently picking one.
    """
    rows = []
    for entity in merged_entities:
        row = {
            "name": entity.name,
            "sources": sorted(entity.source_urls),
            "attributes": {},
        }
        for attr_key, sourced_values in entity.attributes.items():
            row["attributes"][attr_key] = [
                {"value": sv.value, "evidence": sv.evidence, "source_url": sv.source_url}
                for sv in sourced_values
            ]
        rows.append(row)
    return rows
