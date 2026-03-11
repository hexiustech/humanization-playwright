"""Pattern classification using keyword heuristics."""

from typing import Dict, List


PATTERN_KEYWORDS: Dict[str, List[str]] = {
    "table_data": ["table", "rows", "columns", "grid", "spreadsheet", "csv", "thead", "tbody"],
    "product_listing": [
        "product", "price", "listing", "catalog", "shop", "item", "buy",
        "cart", "merchandise", "goods",
    ],
    "article_content": [
        "article", "post", "blog", "story", "news", "author",
        "paragraph", "headline", "byline",
    ],
    "link_list": ["link", "url", "href", "navigation", "menu", "sitemap", "anchor"],
}


def classify_target(target: str) -> str:
    """Classify a target description into a pattern category.

    Counts keyword hits per pattern in the lowercased target string.
    Returns the best-matching pattern (minimum 1 hit), or 'generic' if none match.
    """
    target_lower = target.lower()
    scores: Dict[str, int] = {}

    for pattern, keywords in PATTERN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in target_lower)
        if score > 0:
            scores[pattern] = score

    if not scores:
        return "generic"

    return max(scores, key=scores.get)  # type: ignore[arg-type]
