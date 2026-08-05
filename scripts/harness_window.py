#!/usr/bin/env python3
"""Harness: verify RSS time-window filtering rejects stale items.

Usage:
    python scripts/harness_window.py
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.scanner import _apply_time_window, _extract_rss  # type: ignore


def rfc822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def build_feed(items: list[dict]) -> str:
    lines = ['<?xml version="1.0"?>', '<rss><channel>']
    for item in items:
        pub_date = f"<pubDate>{item['pub_date']}</pubDate>" if item.get("pub_date") else ""
        lines.append(
            f"<item><title>{item['title']}</title>"
            f"<link>{item['url']}</link>{pub_date}</item>"
        )
    lines.extend(["</channel></rss>"])
    return "\n".join(lines)


def main() -> int:
    failures = []
    now = datetime(2026, 8, 5, 9, 0, 0, tzinfo=timezone.utc)

    # Case 1: 36h window keeps 24h item, drops 72h item.
    items = [
        {
            "title": "Fresh story",
            "url": "https://example.com/fresh",
            "pub_date": rfc822(now - timedelta(hours=12)),
        },
        {
            "title": "Stale story",
            "url": "https://example.com/stale",
            "pub_date": rfc822(now - timedelta(hours=72)),
        },
    ]
    raw = build_feed(items)
    extracted = _extract_rss(raw, "https://example.com/feed")
    kept = _apply_time_window(extracted, 36, "exclude", now)
    kept_titles = {i["title"] for i in kept}
    if "Fresh story" not in kept_titles:
        failures.append("12-hour-old item should pass 36h window")
    if "Stale story" in kept_titles:
        failures.append("72-hour-old item should be rejected by 36h window")

    # Case 2: missing pubDate is excluded by default.
    items = [
        {"title": "No date", "url": "https://example.com/nodate"},
        {
            "title": "With date",
            "url": "https://example.com/withdate",
            "pub_date": rfc822(now - timedelta(hours=1)),
        },
    ]
    raw = build_feed(items)
    extracted = _extract_rss(raw, "https://example.com/feed")
    kept = _apply_time_window(extracted, 36, "exclude", now)
    kept_titles = {i["title"] for i in kept}
    if "No date" in kept_titles:
        failures.append("missing pubDate should be excluded by default")
    if "With date" not in kept_titles:
        failures.append("item with valid pubDate should be kept")

    # Case 3: missing pubDate included when policy is include.
    kept = _apply_time_window(extracted, 36, "include", now)
    kept_titles = {i["title"] for i in kept}
    if "No date" not in kept_titles or "With date" not in kept_titles:
        failures.append("missing pubDate should be includable via policy")

    if failures:
        print(f"FAIL: {len(failures)} harness check(s) failed")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PASS: time-window filter correctly rejects stale and dateless items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
