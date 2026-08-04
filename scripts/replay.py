#!/usr/bin/env python3
"""replay.py — Replay the decision chain for any item in the tape.

The tape is append-only, so every stage of an item's life (scan, prescreen,
review, dedup) can be reconstructed by reading its records.

Usage:
    python scripts/replay.py --item d02fcce3d996
    python scripts/replay.py --why https://epoch.ai/MirrorCode
    python scripts/replay.py --why https://epoch.ai/mirrorcode --vertical tech
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parent.parent


def load_tape(vertical: str) -> List[Dict[str, Any]]:
    """Load all records for a vertical from the append-only tape."""
    tape_path = ROOT / "tape" / f"{vertical}.jsonl"
    if not tape_path.exists():
        # Fall back to the committed sample tape for demos.
        tape_path = ROOT / "tape" / "sample-tech.jsonl"
    if not tape_path.exists():
        raise FileNotFoundError(f"No tape found for vertical: {vertical}")

    records = []
    for line in tape_path.read_text(encoding="utf-8").split("\n"):
        if line.strip():
            records.append(json.loads(line))
    return records


def find_item_by_id(records: List[Dict[str, Any]], item_id: str) -> Optional[Dict[str, Any]]:
    """Return the most recent item record with the given id."""
    for r in reversed(records):
        if r.get("type") == "item" and r.get("id") == item_id:
            return r
    return None


def find_item_by_url(records: List[Dict[str, Any]], url: str) -> Optional[Dict[str, Any]]:
    """Return the most recent item record whose URL or url_norm matches."""
    url = url.rstrip("/").lower()
    for r in reversed(records):
        if r.get("type") == "item":
            record_url = (r.get("url") or "").rstrip("/").lower()
            norm_url = (r.get("url_norm") or "").rstrip("/").lower()
            if url in (record_url, norm_url) or record_url in url or norm_url in url:
                return r
    return None


def find_frontpage_for_item(
    records: List[Dict[str, Any]], source_id: str, before_ts: str
) -> Optional[Dict[str, Any]]:
    """Return the latest frontpage snapshot for a source before the item timestamp."""
    candidates = [
        r for r in records
        if r.get("type") == "frontpage" and r.get("source_id") == source_id
        and r.get("ts", "") <= before_ts
    ]
    return candidates[-1] if candidates else None


def find_profile_at_time(
    records: List[Dict[str, Any]], before_ts: str
) -> Optional[Dict[str, Any]]:
    """Return the latest profile version before the item timestamp."""
    candidates = [
        r for r in records
        if r.get("type") == "profile" and r.get("ts", "") <= before_ts
    ]
    return candidates[-1] if candidates else None


def format_timestamp(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return ts


def print_decision_chain(item: Dict[str, Any], records: List[Dict[str, Any]]) -> None:
    """Print a human-readable decision chain for an item record."""
    title = item.get("title", "Untitled")
    url = item.get("url", "")
    url_norm = item.get("url_norm", "")
    source = item.get("source_name", item.get("source_id", "unknown"))
    stage = item.get("stage", "unknown")
    item_id = item.get("id", "N/A")
    ts = item.get("ts", "")

    print(f"Decision replay for: {title}")
    if item_id and item_id != "N/A":
        print(f"  Item ID: {item_id}")
    print(f"  Source:  {source}")
    print(f"  URL:     {url}")
    if url_norm and url_norm != url.rstrip("/"):
        print(f"  Normalized URL: {url_norm}")
    print(f"  Stage:   {stage}")
    print()

    # 1. Scan
    frontpage = find_frontpage_for_item(records, item.get("source_id", ""), ts)
    print("1. Scan")
    if frontpage:
        print(f"   Front page fetched at {format_timestamp(frontpage.get('ts', ''))}")
        # Confirm the item appeared in that frontpage.
        urls = {it.get("url_norm", it.get("url", "")) for it in frontpage.get("items", [])}
        if url_norm in urls:
            print("   Item URL was new on the front page in this snapshot.")
        else:
            print("   Item URL does not appear in the matching frontpage snapshot (may be from an earlier diff).")
    else:
        print("   No matching frontpage snapshot found.")
    print()

    # 2. Prescreen
    scores = item.get("scores", {})
    prescreen_score = scores.get("prescreen", 0)
    matched_keywords = scores.get("matched_keywords", [])
    matched_categories = scores.get("matched_categories", [])
    matched_negatives = scores.get("matched_negatives", [])

    print("2. Prescreen")
    print(f"   Score: {prescreen_score}")
    if matched_keywords:
        terms = ", ".join(f"{k['term']}({k['weight']})" for k in matched_keywords)
        print(f"   Matched keywords: {terms}")
    if matched_categories:
        cats = ", ".join(f"{c['name']}(+{c['bonus']})" for c in matched_categories)
        print(f"   Matched categories: {cats}")
    if matched_negatives:
        negs = ", ".join(f"{n['term']}(-{n['weight']})" for n in matched_negatives)
        print(f"   Matched negatives: {negs}")
    if not any([matched_keywords, matched_categories, matched_negatives]):
        print("   No keyword, category, or negative matches.")
    print()

    # 3. Review
    print("3. Review")
    verify = scores.get("verify", {})
    if verify.get("dry_mode"):
        print("   Dry mode - LLM review gate was stubbed; item carried through.")
    elif verify.get("llm_called"):
        print("   LLM review was called.")
        for key in ["is_news", "is_ad", "vertical_fit"]:
            if key in verify:
                print(f"   {key}: {verify[key]}")
    else:
        print("   No review record found.")
    print()

    # 4. Dedup / outcome
    print("4. Outcome")
    if stage == "pooled":
        cluster_id = item.get("cluster_id", item_id)
        print(f"   Pooled. Cluster ID: {cluster_id}")
        if cluster_id == item_id:
            print("   This item is the main entry for its cluster (no duplicates merged).")
        else:
            print("   This item was merged into an existing cluster.")
    elif stage == "rejected":
        reason = item.get("reject_reason", "unknown")
        print(f"   Rejected. Reason: {reason}")
        if reason == "low_score":
            print("   The prescreen score was below the threshold.")
    elif stage == "verified":
        print("   Verified but not yet pooled (check later records for dedup outcome).")
    else:
        print(f"   Final stage: {stage}")
    print()

    # 5. Profile context
    profile = find_profile_at_time(records, ts)
    if profile:
        print("Profile context at scan time")
        print(f"   Version: {profile.get('version', 'unknown')}")
        print(f"   Reason:  {profile.get('reason', 'unknown')}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay an item's decision chain from the tape")
    parser.add_argument("--vertical", default="tech", help="Vertical name (default: tech)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--item", help="Item ID (12-char hex)")
    group.add_argument("--why", help="URL to look up")
    args = parser.parse_args()

    records = load_tape(args.vertical)

    if args.item:
        item = find_item_by_id(records, args.item)
        if not item:
            print(f"Item not found in tape: {args.item}", file=sys.stderr)
            return 1
    else:
        item = find_item_by_url(records, args.why)
        if not item:
            print(f"No item matching URL found in tape: {args.why}", file=sys.stderr)
            return 1

    print_decision_chain(item, records)
    return 0


if __name__ == "__main__":
    sys.exit(main())
