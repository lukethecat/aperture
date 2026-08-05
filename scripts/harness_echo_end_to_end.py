#!/usr/bin/env python3
"""Harness: end-to-end ECHO flow — prepare → deliver → ingest → distill.

Usage:
    python scripts/harness_echo_end_to_end.py
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import tape
from engine.echo import (
    apply_answer,
    distill,
    enable,
    prepare,
    record_delivery,
    record_raw_answer,
)
from engine.profile import get_profile, init_profile

VERTICAL = "harness-echo"
TAPE_PATH = ROOT / "tape" / f"{VERTICAL}.jsonl"


def _cleanup() -> None:
    if TAPE_PATH.exists():
        TAPE_PATH.unlink()


def _seed_tape(date: str) -> None:
    """Seed the tape with a profile, source, frontpage, and pooled items."""
    init_profile(
        VERTICAL,
        keywords=[{"term": "AI", "weight": 3}],
        categories=[{"name": "models", "keywords": ["model"], "bonus": 2}],
        negatives=[{"term": "sponsored", "weight": 3}],
        reason="harness seed",
    )
    now = datetime.fromisoformat(f"{date}T12:00:00+00:00").isoformat()

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
    tape.append(
        VERTICAL,
        {
            "type": "frontpage",
            "source_id": "hn",
            "date": date,
            "items": [],
            "count": 0,
        },
    )

    base_items = [
        {
            "title": "Quantum breakthrough claims new speed record",
            "url": "https://example.com/quantum-1",
            "source_name": "Hacker News",
        },
        {
            "title": "Quantum networking reaches 100 km milestone",
            "url": "https://example.com/quantum-2",
            "source_name": "Hacker News",
        },
        {
            "title": "OpenAI releases new reasoning model",
            "url": "https://example.com/openai",
            "source_name": "Hacker News",
        },
    ]
    for idx, raw in enumerate(base_items):
        tape.append(
            VERTICAL,
            {
                "type": "item",
                "vertical": VERTICAL,
                "source_id": "hn",
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


def _write_question_with_date(date: str) -> Dict:
    """Directly write a pending question for a specific date."""
    qid = f"echo-{date}-quantum-test"
    tape.append(
        VERTICAL,
        {
            "id": qid,
            "type": "echo_question",
            "vertical": VERTICAL,
            "date": date,
            "topic": "Quantum",
            "question": "Add 'Quantum' to the profile?",
            "evidence": {"count": 2, "urls": []},
            "answerable_in_one_word": True,
            "status": "pending",
        },
    )
    return {"id": qid, "date": date}


def main() -> int:
    failures = []
    _cleanup()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    # ==== Path A: prepare → deliver → ingest → distill (today) ====
    _seed_tape(today)
    questions = prepare(VERTICAL)
    print(f"[prepare] generated {len(questions)} question(s)")
    if not questions:
        failures.append("ECHO did not generate a question for repeated topic 'Quantum'")

    if not failures:
        q = questions[0]
        qid = q["id"]

        # deliver
        record_delivery(VERTICAL, [qid], "#harness", "msg-123")
        if not tape.query(VERTICAL, type="echo_delivery"):
            failures.append("echo_delivery record missing")

        # ingest
        record_raw_answer(VERTICAL, qid, "yes")
        if not tape.query(VERTICAL, type="echo_raw_answer"):
            failures.append("echo_raw_answer record missing")

        # distill (applied directly because raw_answer is today)
        old_profile = get_profile(VERTICAL)
        old_version = old_profile.get("version", 0)
        res = apply_answer(qid, VERTICAL, "yes")
        if res.get("status") != "applied":
            failures.append(f"apply_answer returned status={res.get('status')}")

        new_profile = get_profile(VERTICAL)
        new_version = new_profile.get("version", 0)
        terms = {kw["term"].lower() for kw in new_profile.get("keywords", [])}
        if new_version <= old_version:
            failures.append(f"profile version did not bump ({old_version} -> {new_version})")
        if "quantum" not in terms:
            failures.append("topic 'quantum' not found in profile keywords")

        all_q = [r for r in tape.query(VERTICAL, type="echo_question") if r.get("id") == qid]
        answered_q = [r for r in all_q if r.get("status") == "answered"]
        if not answered_q:
            failures.append("question not marked answered")

    # ==== Path B: expiry of yesterday's unanswered delivered question ====
    _cleanup()
    _seed_tape(yesterday)
    q_yesterday = _write_question_with_date(yesterday)
    record_delivery(VERTICAL, [q_yesterday["id"]], "#harness", "msg-456")

    # Move state forward: prepare today should expire yesterday's question.
    _seed_tape(today)
    prepare(VERTICAL)
    expired = [r for r in tape.query(VERTICAL, type="echo_question") if r.get("status") == "expired"]
    if not expired:
        failures.append("unanswered delivered question from yesterday was not expired")

    # ==== Path C: silence and enable ====
    silence_q = [r for r in tape.query(VERTICAL, type="echo_question") if r.get("status") == "pending"]
    if silence_q:
        res = apply_answer(silence_q[0]["id"], VERTICAL, "silence")
        if res.get("status") != "silenced":
            failures.append("silence answer did not silence ECHO")
        enable(VERTICAL)

    _cleanup()

    if failures:
        print(f"FAIL: {len(failures)} harness check(s) failed")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PASS: end-to-end ECHO flow works (prepare → deliver → ingest → distill)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
