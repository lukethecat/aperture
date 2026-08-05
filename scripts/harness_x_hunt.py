#!/usr/bin/env python3
"""Harness: agent-facilitated human-feed injection (scripts/x_hunt.py).

Usage:
    python scripts/harness_x_hunt.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import tape
from engine.echo import prepare
from engine.pipeline import run_pipeline
from engine.profile import init_profile

VERTICAL = "harness-x-hunt"
TAPE_PATH = ROOT / "tape" / f"{VERTICAL}.jsonl"


def _cleanup() -> None:
    if TAPE_PATH.exists():
        TAPE_PATH.unlink()


def _seed() -> None:
    init_profile(
        VERTICAL,
        keywords=[{"term": "AI", "weight": 3}],
        categories=[],
        negatives=[{"term": "crypto", "weight": 3}],
        reason="harness seed",
    )
    now = datetime.now(timezone.utc).isoformat()
    tape.append(
        VERTICAL,
        {
            "type": "source",
            "id": "owner_tips",
            "name": "Owner Tips",
            "vertical": VERTICAL,
            "list_url": "",
            "extract_profile": {"method": "human_feed"},
            "health": {"last_ok": now, "fail_count": 0},
        },
    )


def main() -> int:
    failures = []
    _cleanup()
    _seed()

    # Inject a manually chosen X-style URL as agent-facilitated human-feed.
    from scripts.x_hunt import inject_item

    record = inject_item(
        vertical=VERTICAL,
        title="New open-weights model shows strong reasoning benchmarks",
        url="https://x.com/example_ai/status/1234567890",
        source_id="owner_tips",
        facilitated_by="agent",
    )

    if record.get("facilitated_by") != "agent":
        failures.append("injected item missing facilitated_by=agent")

    items = tape.query(VERTICAL, type="item")
    hf_items = [i for i in items if i.get("source_id") == "owner_tips" and i.get("stage") == "scanned"]
    if len(hf_items) != 1:
        failures.append(f"expected 1 scanned human-feed item, found {len(hf_items)}")

    # Run the pipeline dry; the human-feed item should enter the funnel.
    result = run_pipeline(VERTICAL, dry=True, use_llm_report=False)
    if result["prescreen"]["total_candidates"] < 1:
        failures.append("human-feed item was not picked up by the pipeline")

    # ECHO should generate a source-proposal question from the human-feed item.
    questions = prepare(VERTICAL)
    source_questions = [q for q in questions if q.get("kind") == "source_proposal"]
    if not source_questions:
        failures.append("human-feed item did not trigger ECHO source-proposal question")

    _cleanup()

    if failures:
        print(f"FAIL: {len(failures)} harness check(s) failed")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PASS: agent-facilitated human-feed injection flows through pipeline and ECHO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
