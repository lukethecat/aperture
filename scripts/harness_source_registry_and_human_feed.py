#!/usr/bin/env python3
"""Harness: source registry rendering + human-feed ECHO source proposals.

Usage:
    python scripts/harness_source_registry_and_human_feed.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import tape
from engine.echo import apply_answer, prepare
from engine.profile import init_profile
from engine.report import generate_report

VERTICAL = "harness-registry-hf"
TAPE_PATH = ROOT / "tape" / f"{VERTICAL}.jsonl"


def _cleanup() -> None:
    if TAPE_PATH.exists():
        TAPE_PATH.unlink()


def _seed_sources_and_items() -> None:
    init_profile(
        VERTICAL,
        keywords=[{"term": "AI", "weight": 3}],
        categories=[],
        negatives=[],
        reason="harness seed",
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc).isoformat()

    # pull source (rss)
    tape.append(
        VERTICAL,
        {
            "type": "source",
            "id": "hn",
            "name": "Hacker News",
            "vertical": VERTICAL,
            "list_url": "https://news.ycombinator.com/rss",
            "extract_profile": {"method": "rss"},
            "health": {"last_ok": now, "fail_count": 0},
        },
    )
    # scan source (generic_links)
    tape.append(
        VERTICAL,
        {
            "type": "source",
            "id": "tc",
            "name": "TechCrunch",
            "vertical": VERTICAL,
            "list_url": "https://techcrunch.com",
            "extract_profile": {"method": "generic_links"},
            "health": {"last_ok": now, "fail_count": 0},
        },
    )
    # human-feed source
    tape.append(
        VERTICAL,
        {
            "type": "source",
            "id": "hf_tip",
            "name": "Weixin Tip",
            "vertical": VERTICAL,
            "list_url": "",
            "extract_profile": {"method": "human_feed"},
            "health": {"last_ok": now, "fail_count": 0},
        },
    )

    # frontpage snapshot so report scanning math works
    tape.append(
        VERTICAL,
        {
            "type": "frontpage",
            "source_id": "hn",
            "date": today,
            "items": [],
            "count": 0,
        },
    )

    base_items = [
        {
            "title": "OpenAI releases new reasoning model",
            "url": "https://example.com/openai",
            "source_id": "hn",
            "source_name": "Hacker News",
        },
        {
            "title": "Startup raises series A for edge AI",
            "url": "https://mp.weixin.qq.com/s/abc123",
            "source_id": "hf_tip",
            "source_name": "Weixin Tip",
        },
    ]
    for idx, raw in enumerate(base_items):
        tape.append(
            VERTICAL,
            {
                "type": "item",
                "vertical": VERTICAL,
                "source_id": raw["source_id"],
                "source_name": raw["source_name"],
                "title": raw["title"],
                "url": raw["url"],
                "url_norm": raw["url"],
                "stage": "pooled",
                "scores": {
                    "prescreen": 5,
                    "matched_keywords": [],
                    "matched_categories": [],
                    "matched_negatives": [],
                },
                "ts": now,
                "id": f"item-{idx}",
                "cluster_id": f"cluster-{idx}",
                "simhash": idx,
            },
        )


def _check_registry(report_body: str) -> list:
    failures = []
    if "[Hacker News](https://news.ycombinator.com/rss) · pull" not in report_body:
        failures.append("registry missing pull source link+badge")
    if "[TechCrunch](https://techcrunch.com) · scan" not in report_body:
        failures.append("registry missing scan source link+badge")
    if "Weixin Tip · human-feed" not in report_body:
        failures.append("registry missing human-feed badge")
    return failures


def _check_human_feed_question() -> list:
    failures = []
    questions = prepare(VERTICAL)
    source_questions = [q for q in questions if q.get("kind") == "source_proposal"]
    if not source_questions:
        failures.append("human-feed items did not trigger a source-proposal question")
        return failures

    q = source_questions[0]
    if "Weixin Tip" not in q["question"]:
        failures.append("source-proposal question missing source name")
    if "closed platform" not in q["question"]:
        failures.append("Weixin URL did not add closed-platform note")
    if not q.get("proposed_source", {}).get("weixin"):
        failures.append("proposed_source.weixin flag not set")

    # Yes answer should record a source_proposal, not a keyword.
    res = apply_answer(q["id"], VERTICAL, "yes")
    if res.get("status") != "source_proposal":
        failures.append(f"apply_answer yes returned {res.get('status')} instead of source_proposal")
    if not res.get("notify_channel"):
        failures.append("Weixin source proposal should request channel notification")
    if "@Cindy" not in res.get("message", ""):
        failures.append("Weixin proposal message missing @Cindy")
    if not tape.query(VERTICAL, type="source_proposal"):
        failures.append("source_proposal tape record missing")

    # Profile should not have been modified by the source-proposal answer.
    from engine.profile import get_profile

    profile = get_profile(VERTICAL)
    keywords = {kw["term"].lower() for kw in profile.get("keywords", [])}
    if "weixin tip" in keywords:
        failures.append("source-proposal yes incorrectly added source name as keyword")

    return failures


def main() -> int:
    failures = []
    _cleanup()
    _seed_sources_and_items()

    report = generate_report(VERTICAL, use_llm=False)
    failures.extend(_check_registry(report.get("body", "")))
    failures.extend(_check_human_feed_question())

    _cleanup()

    if failures:
        print(f"FAIL: {len(failures)} harness check(s) failed")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PASS: registry renders links+badges and human-feed triggers source proposals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
