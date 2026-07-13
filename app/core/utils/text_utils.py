"""
Shared location normalisation and district resolution utilities.
"""

from difflib import get_close_matches, SequenceMatcher


def normalize_location(location: str) -> str:
    return location.strip().lower()


def resolve_from_list(
    location: str,
    candidates: list[str],
    fuzzy_cutoff: float = 0.6,
    prefix_len: int = 3,
) -> dict:
    """
    Resolve a free-text location to one entry in *candidates*.

    Resolution order
    ----------------
    1. Exact match (case-insensitive)
    2. Prefix match
    3. Substring containment
    4. Prefix-anchored fuzzy match (difflib, constrained by prefix_len and length ratio)

    Returns dict: {matched: str|None, confidence: float, method: str}
    """
    loc_norm = normalize_location(location)
    lower_map: dict[str, str] = {c.strip().lower(): c for c in candidates}
    lower_keys = list(lower_map.keys())

    # 1. Exact
    if loc_norm in lower_map:
        return {"matched": lower_map[loc_norm], "confidence": 1.0, "method": "exact_match"}

    # 2. Prefix
    prefix_hits = [k for k in lower_keys if k.startswith(loc_norm)]
    if prefix_hits:
        best = max(prefix_hits, key=len)
        ratio = round(SequenceMatcher(None, loc_norm, best).ratio(), 3)
        return {"matched": lower_map[best], "confidence": ratio, "method": "prefix_match"}

    # 3. Substring containment
    sub_hits = [k for k in lower_keys if loc_norm in k]
    if sub_hits:
        best = max(sub_hits, key=lambda k: SequenceMatcher(None, loc_norm, k).ratio())
        ratio = round(SequenceMatcher(None, loc_norm, best).ratio(), 3)
        return {"matched": lower_map[best], "confidence": ratio, "method": "substring_match"}

    # 4. Prefix-anchored fuzzy
    prefix3 = loc_norm[:prefix_len]
    fuzzy_pool = [
        k for k in lower_keys
        if k.startswith(prefix3)
        and min(len(loc_norm), len(k)) / max(len(loc_norm), len(k)) >= 0.6
    ]
    if fuzzy_pool:
        close = get_close_matches(loc_norm, fuzzy_pool, n=1, cutoff=fuzzy_cutoff)
        if close:
            ratio = round(SequenceMatcher(None, loc_norm, close[0]).ratio(), 3)
            return {"matched": lower_map[close[0]], "confidence": ratio, "method": "fuzzy_match"}

    return {"matched": None, "confidence": 0.0, "method": "no_match"}
