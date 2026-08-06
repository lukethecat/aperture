#!/usr/bin/env python3
"""Agent-facilitated discovery source: bookkeep a curated candidate into the tape.

This script does **deterministic bookkeeping only** — it writes a curated item
to the tape as a human-feed entry with `facilitated_by: agent`. The judgment
(search, read, and selection) is the agent's job, performed with whatever
WebSearch/tools the agent has available.

Aperture's "never stop at the message" rule: an X/Twitter post is a signal,
never the final citation. The URL injected must be the original English news
article URL. If only an X post URL is available, the script attempts a
best-effort DuckDuckGo resolution from the headline; if that fails, it drops
the candidate and logs the reason on the tape.

Usage:
    # Inject an item the agent has already resolved to the original article URL.
    python scripts/x_hunt.py --vertical ai-frontier --source-id ainativef_zh \
        --title "OpenAI announces GPT-5" \
        --url "https://openai.com/blog/introducing-gpt-5" \
        --inject

    # Best-effort automated search fallback (many engines block automated
    # queries, so prefer the --title/--url path in daily operation).
    python scripts/x_hunt.py --vertical ai-frontier \
        --query "AI artificial intelligence site:x.com" \
        --inject

The injected item is written to the vertical's tape as a human-feed item with
`facilitated_by: agent`. It then goes through the normal prescreen/review/dedup
stages like any other candidate.
"""
import argparse
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import tape
from engine.scanner import normalize_url

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_HUMAN_FEED_SOURCE = "owner_tips"

# X/Twitter status URLs are signals, not final sources. Aperture's "never stop at
# the message" rule requires the original article URL before injection.
_X_STATUS_RE = re.compile(r"https?://(x\.com|twitter\.com)/[^/]+/status/")


def _is_x_post_url(url: str) -> bool:
    return bool(_X_STATUS_RE.search(url or ""))


def _resolve_original_url(title: str) -> Optional[str]:
    """
    Best-effort resolution of an original article URL from a headline.
    Searches DuckDuckGo and returns the first result that is not an X/Twitter
    post. Returns None if no non-X result is found.
    """
    if not title:
        return None
    results = _duckduckgo_html_search(title)
    for r in results:
        url = r.get("url", "")
        if not url or _is_x_post_url(url):
            continue
        return url
    return None


def _fetch_url(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            charset = resp.headers.get_content_charset()
            if charset:
                return data.decode(charset, errors="replace")
            try:
                return data.decode("utf-8", errors="replace")
            except UnicodeDecodeError:
                return data.decode("latin-1", errors="replace")
    except urllib.error.URLError:
        return ""
    except Exception:
        return ""


def _duckduckgo_html_search(query: str) -> List[Dict[str, str]]:
    """Best-effort DuckDuckGo HTML search; often blocked or returns no results."""
    encoded = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    raw = _fetch_url(url)
    if not raw:
        return []

    results = []
    for block in re.findall(
        r'<a[^>]*class="result__a"[^>]*>(.*?)</a>.*?(?:<a[^>]*class="result__url"[^>]*href="([^"]*)"[^>]*>[^<]*</a>)?',
        raw,
        re.DOTALL | re.IGNORECASE,
    ):
        title_html, href = block
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        if not title or not href:
            continue
        # DuckDuckGo redirects through //duckduckgo.com/l/?uddg=...
        if href.startswith("//duckduckgo.com") or href.startswith("https://duckduckgo.com"):
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            real_urls = parsed.get("uddg", [])
            if real_urls:
                href = urllib.parse.unquote(real_urls[0])
        results.append({"title": title, "url": href})
    return results


def _filter_x_ai_results(results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Keep results that look like X/Twitter posts and have an AI-ish title."""
    ai_terms = {
        "ai", "artificial intelligence", "llm", "model", "gpt", "claude", "gemini",
        "openai", "anthropic", "mistral", "qwen", "benchmark", "agent", "safety",
        "multimodal", "reasoning", "open source", "open weights", "frontier",
    }
    filtered = []
    for r in results:
        url = r.get("url", "")
        title = r.get("title", "")
        if not re.search(r"https?://(x\.com|twitter\.com)/[^/]+/status/", url):
            continue
        lower = (title + " " + url).lower()
        if any(term in lower for term in ai_terms):
            filtered.append(r)
    return filtered


def _resolve_source_name(vertical: str, source_id: str) -> str:
    """Return the registered source name for source_id, or source_id itself."""
    for s in tape.query(vertical, type="source"):
        if s.get("id") == source_id:
            return s.get("name") or source_id
    return source_id


def inject_item(
    vertical: str,
    title: str,
    url: str,
    source_id: str = DEFAULT_HUMAN_FEED_SOURCE,
    facilitated_by: str = "agent",
) -> Dict[str, Any]:
    """Write a human-feed item to the tape and return the record."""
    now = datetime.now(timezone.utc).isoformat()
    url_norm = normalize_url(url)
    item_id = f"{source_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    record = {
        "type": "item",
        "id": item_id,
        "vertical": vertical,
        "source_id": source_id,
        "source_name": _resolve_source_name(vertical, source_id),
        "title": title,
        "url": url,
        "url_norm": url_norm,
        "stage": "scanned",  # enters the pipeline at prescreen
        "scores": {},
        "ts": now,
        "facilitated_by": facilitated_by,
    }
    tape.append(vertical, record)
    return record


def drop_item(
    vertical: str,
    title: str,
    url: str,
    source_id: str = DEFAULT_HUMAN_FEED_SOURCE,
    reason: str = "unresolved_origin",
) -> Dict[str, Any]:
    """Log an X-hunt candidate that could not be resolved to an original URL."""
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "type": "item",
        "id": f"{source_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-drop",
        "vertical": vertical,
        "source_id": source_id,
        "source_name": _resolve_source_name(vertical, source_id),
        "title": title,
        "url": url,
        "stage": "dropped",
        "drop_reason": reason,
        "ts": now,
        "facilitated_by": "agent",
    }
    tape.append(vertical, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Agent-facilitated human-feed: bookkeep a curated X/AI candidate into the tape."
    )
    parser.add_argument("--vertical", default="ai-frontier", help="Vertical name")
    parser.add_argument("--source-id", default=DEFAULT_HUMAN_FEED_SOURCE, help="Human-feed source id")
    parser.add_argument(
        "--query",
        default="AI artificial intelligence site:x.com",
        help="Best-effort automated search fallback (many engines block automated search)",
    )
    parser.add_argument("--title", help="Title of the agent-curated post")
    parser.add_argument("--url", help="URL of the agent-curated post")
    parser.add_argument("--inject", action="store_true", help="Write the candidate to the tape")
    parser.add_argument("--max-results", type=int, default=5, help="Max candidates to display")
    parser.add_argument(
        "--resolve",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Try to resolve X post URLs to original article URLs (default: True)",
    )
    parser.add_argument(
        "--allow-x-url",
        action="store_true",
        help="Allow injecting an X post URL as the final source (requires explicit opt-in)",
    )
    args = parser.parse_args()

    if args.title and args.url:
        candidates = [{"title": args.title, "url": args.url}]
    else:
        print(
            "[search] Best-effort automated search fallback. "
            "Daily workflow should use agent WebSearch + --title/--url."
        )
        print(f"[search] {args.query}")
        candidates = _duckduckgo_html_search(args.query)
        candidates = _filter_x_ai_results(candidates)
        if not candidates:
            print(
                "No X candidates found via automated search. "
                "Use --title and --url to inject an agent-curated post."
            )
            return 1

    print(f"[candidates] top {min(args.max_results, len(candidates))}:")
    for idx, c in enumerate(candidates[: args.max_results], 1):
        print(f"  {idx}. {c['title']}\n     {c['url']}")

    if not args.inject:
        print("\nUse --inject to write the top candidate to the tape.")
        return 0

    top = candidates[0]
    title = top["title"]
    url = top["url"]

    # Enforce "never stop at the message": X post URLs must be resolved to the
    # original article URL unless the operator explicitly opts out.
    if _is_x_post_url(url):
        if args.allow_x_url:
            print("[warning] Injecting an X post URL as the final source (--allow-x-url).")
        elif args.resolve:
            print("[resolve] X post URL detected; attempting to resolve original article URL...")
            resolved = _resolve_original_url(title)
            if resolved:
                print(f"[resolve] OK: {resolved}")
                url = resolved
            else:
                print("[resolve] Failed: could not locate original article URL; dropping candidate.")
                drop_item(
                    vertical=args.vertical,
                    title=title,
                    url=top["url"],
                    source_id=args.source_id,
                    reason="unresolved_x_origin",
                )
                return 0
        else:
            print("[error] X post URLs are not allowed as final sources. "
                  "Use --resolve to find the original article or --allow-x-url to override.")
            return 1

    record = inject_item(
        vertical=args.vertical,
        title=title,
        url=url,
        source_id=args.source_id,
        facilitated_by="agent",
    )
    print(f"\n[injected] {record['id']}: {record['title']}")
    print(f"           {record['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
