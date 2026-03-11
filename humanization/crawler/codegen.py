"""Claude API script generation and HTML sampling for extraction scripts."""

import json
import re
from typing import Optional, Tuple, Any

from .exceptions import ScriptGenerationError


SYSTEM_PROMPT = """You are a web scraping script generator. You write Python async functions that extract structured data from web pages using Playwright's Page API.

Rules:
1. Write a single async function named `extract(page)` that takes a Playwright Page object (already navigated to the target URL).
2. Use only these Page methods: page.query_selector_all(), page.query_selector(), page.evaluate(), page.inner_text(), page.get_attribute(), page.content(), page.wait_for_selector(), page.text_content(), page.inner_html().
3. Return a Python dict matching the provided JSON schema exactly.
4. Handle common edge cases: elements not found (return empty strings/lists as defaults), dynamic content (use wait_for_selector with a short timeout wrapped in try/except).
5. Do NOT import any modules. Do NOT use page.goto(). Do NOT launch browsers. Do NOT use 'import' statements.
6. Be as generic as possible -- use semantic HTML selectors (tag names, roles, aria labels, tag structure like 'table > tr > td') over brittle CSS class names when possible.
7. For wait_for_selector, always use a try/except with a short timeout (2000ms) so the script doesn't hang.
8. Output ONLY the Python async function definition. No markdown fences, no explanation, no comments outside the function."""


def build_generation_prompt(
    target: str,
    pattern: str,
    schema: dict,
    html_sample: str,
    previous_error: Optional[str] = None,
) -> str:
    """Construct the user message for script generation or healing."""
    parts = [
        f"Extract: {target}",
        f"Pattern category: {pattern}",
        "",
        "Expected output JSON schema:",
        json.dumps(schema, indent=2),
        "",
        "Page HTML (truncated):",
        html_sample,
    ]

    if previous_error:
        parts.extend([
            "",
            "The previous extraction script failed with this error:",
            previous_error,
            "",
            "Please fix the script to handle this case. Keep it generic.",
        ])

    parts.append("")
    parts.append("Write the `async def extract(page):` function.")
    return "\n".join(parts)


async def generate_script(
    client: Any,
    target: str,
    pattern: str,
    schema: dict,
    html_sample: str,
    previous_error: Optional[str] = None,
) -> Tuple[str, int]:
    """Call Claude API to generate or heal an extraction script.

    Args:
        client: An anthropic.AsyncAnthropic instance.
        target: What to extract.
        pattern: The classified pattern name.
        schema: The expected output JSON schema.
        html_sample: Truncated page HTML.
        previous_error: If healing, the error from the previous attempt.

    Returns:
        (script_code, total_tokens_used)

    Raises:
        ScriptGenerationError: If the API call fails or returns invalid output.
    """
    user_message = build_generation_prompt(
        target, pattern, schema, html_sample, previous_error
    )

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception as e:
        raise ScriptGenerationError(f"Claude API call failed: {e}") from e

    if not response.content:
        raise ScriptGenerationError("Claude API returned empty response")

    raw_code = response.content[0].text
    tokens = response.usage.input_tokens + response.usage.output_tokens
    code = _clean_code(raw_code)

    if "async def extract" not in code:
        raise ScriptGenerationError(
            "Generated code does not contain 'async def extract'"
        )

    return code, tokens


def _clean_code(raw: str) -> str:
    """Strip markdown fences and leading/trailing whitespace."""
    code = raw.strip()
    # Remove ```python ... ``` fences
    code = re.sub(r"^```(?:python)?\s*\n?", "", code)
    code = re.sub(r"\n?```\s*$", "", code)
    return code.strip()


async def sample_html(page: Any, max_chars: int = 15000) -> str:
    """Get a truncated HTML sample from the page for the generation prompt.

    Strategy:
    1. Get full page HTML via page.content()
    2. Strip <script> and <style> tags entirely
    3. If under max_chars, return as-is
    4. Otherwise: take <title> + meta description (up to 500 chars)
       + first (max_chars - 500) chars of cleaned body
    """
    try:
        html = await page.content()
    except Exception:
        return "<html><body>Failed to retrieve page content</body></html>"

    # Strip script and style tags
    cleaned = re.sub(
        r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
    )
    cleaned = re.sub(
        r"<style[^>]*>.*?</style>", "", cleaned, flags=re.DOTALL | re.IGNORECASE
    )
    # Collapse excessive whitespace
    cleaned = re.sub(r"\s{3,}", "\n", cleaned)

    if len(cleaned) <= max_chars:
        return cleaned

    # Extract title and meta for the header
    header_parts = []
    title_match = re.search(r"<title[^>]*>(.*?)</title>", cleaned, re.IGNORECASE | re.DOTALL)
    if title_match:
        header_parts.append(f"<title>{title_match.group(1)}</title>")
    meta_match = re.search(
        r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
        cleaned,
        re.IGNORECASE,
    )
    if meta_match:
        header_parts.append(f'<meta name="description" content="{meta_match.group(1)}">')

    header = "\n".join(header_parts)
    header_budget = min(len(header), 500)
    body_budget = max_chars - header_budget

    # Find body content
    body_match = re.search(r"<body[^>]*>(.*)", cleaned, re.IGNORECASE | re.DOTALL)
    body = body_match.group(1) if body_match else cleaned

    return header[:header_budget] + "\n...\n" + body[:body_budget]
