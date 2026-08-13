"""
search_scorer.py — shared candidate re-ranking utility for product name search.

File: app/utils/search_scorer.py

Used by:
    app/scraper_v2/affiliate/flipkart.py  — re-ranks Flipkart Affiliate results
    app/services/web_search.py            — re-ranks Tavily results (Amazon/Myntra)

Adding a new scoring signal:
    1. Add it inside score_candidate() below.
    2. No other files need changes — all callers import this function.

Scoring signals (combined into a float, higher = better match):

    Model number match  (+0.5)
        Exact substring match of a model-like token (uppercase alphanumeric,
        6+ chars) from the query found in the candidate title.
        e.g. "MGM8842MIN" in title → +0.5
        Highest weight — a model number match is an exact product match.

    Brand match  (+0.2)
        Candidate brand field appears in the query (case-insensitive).
        e.g. query contains "bosch", candidate.brand = "Bosch" → +0.2

    Token overlap  (0.0–0.3)
        Fraction of meaningful query tokens (3+ chars, non-stopword) that
        appear in the candidate title. Scaled to 0–0.3.
        e.g. 4 of 5 query tokens found in title → +0.24

Total max score ≈ 1.0 for a perfect match.
Never raises — returns 0.0 on any error (safe to call from scrapers).
"""

from __future__ import annotations

import re
from typing import Optional

# Stopwords excluded from token overlap scoring — too common to be meaningful
_STOPWORDS: frozenset[str] = frozenset({
    "the", "and", "for", "with", "from", "this", "that",
    "are", "was", "has", "have", "its", "new", "best",
    "buy", "price", "india", "online", "offer", "deal",
    "get", "shop", "latest", "top", "review", "reviews",
})


def query_title_similarity(query: str, title: str) -> float:
    """
    Token overlap similarity between a search query and a result title.
    Returns 0.0–1.0.

    Used to validate search results — if top result similarity is below
    a threshold, the results are likely wrong category/product.

    Strips common prefixes like "Buy " from portal titles before scoring.
    Ignores stopwords and short tokens (< 2 chars).

    Args:
        query: Raw user search query (e.g. "Boat Wanderer Smart Kids Watch").
        title: Result title (e.g. "Buy boAt Wanderer Smart Kids Watch GPS").

    Returns:
        Float 0.0–1.0. Higher = better match.
        0.0 when either string is empty.

    Examples:
        >>> query_title_similarity("Boat Wanderer Smart", "Buy boAt Wanderer Smart Kids Watch")
        0.6
        >>> query_title_similarity("Samsung TV", "boAt Speaker 200")
        0.0
    """
    if not query or not title:
        return 0.0

    _STOPWORDS = frozenset({
        "the", "and", "for", "with", "from", "this", "that",
        "buy", "a", "an", "in", "of", "to", "is", "are", "at",
        "by", "on", "it", "be", "as", "or", "get",
    })

    def _tokenize(text: str) -> set:
        import re
        tokens = re.split(r"[\s,()\[\]|&]+", text.lower().strip())
        return {t for t in tokens if len(t) >= 2 and t not in _STOPWORDS}

    # Strip common portal prefixes
    clean_title = title.lower().replace("buy ", "").strip()

    q_tokens = _tokenize(query)
    t_tokens = _tokenize(clean_title)

    if not q_tokens or not t_tokens:
        return 0.0

    intersection = q_tokens & t_tokens
    return round(len(intersection) / max(len(q_tokens), len(t_tokens)), 4)


def score_candidate(candidate: dict, query: str) -> float:
    """
    Score a product search candidate against the user's query.

    Args:
        candidate: Dict with at least 'name' (str) and optionally 'brand' (str).
                   Both Flipkart Affiliate and Tavily result dicts are accepted.
        query:     Raw user search query (e.g. "BOSCH TrueMixx Pro mixer grinder").

    Returns:
        Float score in range 0.0–1.0+. Higher = better match.
        Returns 0.0 on any error.
    """
    try:
        title = (candidate.get("name") or candidate.get("title") or "").lower()
        brand = (candidate.get("brand") or "").lower()
        q     = query.lower()

        score = 0.0

        # ── Signal 1: model number match (+0.5) ──────────────────────────────
        # Extract uppercase alphanumeric tokens of 6+ chars from the original
        # (non-lowercased) query — model numbers are typically uppercase.
        # e.g. "MGM8842MIN", "SMS6HMI00I", "BCHDAH9Q"
        model_tokens = re.findall(r'[A-Z0-9]{6,}', query)
        for token in model_tokens:
            if token.lower() in title:
                score += 0.5
                break  # one model match is sufficient

        # ── Signal 2: brand match (+0.2) ──────────────────────────────────────
        # Check if the candidate's brand field appears anywhere in the query.
        # Works for both "BOSCH TrueMixx..." (brand at start) and
        # "TrueMixx Pro by Bosch" (brand elsewhere).
        if brand and brand in q:
            score += 0.2

        # ── Signal 3: token overlap (0.0–0.3) ────────────────────────────────
        # Split query into tokens, strip stopwords and short tokens,
        # count how many appear in the title.
        q_tokens = [
            t for t in re.split(r'[\s|,()[\]]+', q)
            if len(t) >= 3 and t not in _STOPWORDS
        ]
        if q_tokens:
            matches = sum(1 for t in q_tokens if t in title)
            overlap = matches / len(q_tokens)
            score  += overlap * 0.3

        return round(score, 4)

    except Exception:
        return 0.0


def rank_candidates(
    candidates: list[dict],
    query: str,
    limit: int,
) -> list[dict]:
    """
    Score, sort, and trim a list of product candidates.

    Adds a temporary '_score' key for sorting, then removes it before
    returning so callers receive clean dicts.

    Args:
        candidates: List of candidate dicts (Flipkart or Tavily shape).
        query:      Raw user search query.
        limit:      Max candidates to return after ranking.

    Returns:
        Top `limit` candidates sorted by score descending.
        Returns candidates unchanged (order preserved) if list is empty.
    """
    if not candidates:
        return candidates

    for c in candidates:
        c["_score"] = score_candidate(c, query)

    candidates.sort(key=lambda c: c["_score"], reverse=True)

    # Clean up internal key before returning
    for c in candidates:
        c.pop("_score", None)

    return candidates[:limit]
