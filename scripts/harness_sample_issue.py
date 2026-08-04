"""Harness: verify docs/sample-issue.md is faithful to tape/sample-tech.jsonl.

Run with: python scripts/harness_sample_issue.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAPE_PATH = ROOT / "tape" / "sample-tech.jsonl"
MD_PATH = ROOT / "docs" / "sample-issue.md"


def load_tape(path: Path):
    records = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            records.append(json.loads(line))
    return records


def main() -> int:
    if not TAPE_PATH.exists():
        print(f"FAIL: sample tape not found: {TAPE_PATH}")
        return 1
    if not MD_PATH.exists():
        print(f"FAIL: sample issue not found: {MD_PATH}")
        return 1

    tape = load_tape(TAPE_PATH)
    md = MD_PATH.read_text(encoding="utf-8")

    reports = [r for r in tape if r["type"] == "report"]
    if not reports:
        print("FAIL: no report record in sample tape")
        return 1
    report = reports[-1]

    items_by_id = {r["id"]: r for r in tape if r["type"] == "item" and "id" in r}
    pooled_items = [r for r in tape if r["type"] == "item" and r.get("stage") == "pooled"]
    rejected_items = [r for r in tape if r["type"] == "item" and r.get("stage") == "rejected"]
    pooled_ids = {r["id"] for r in pooled_items}
    rejected_titles = {r["title"] for r in rejected_items}

    failures = []

    # 1. Stats in markdown match the report.
    stats = report["stats"]
    expected_stats_phrases = [
        f"{stats['scanned']} items scanned",
        f"{stats['prescreened']} prescreened",
        f"{stats['rejected']} rejected",
        f"{stats['pooled']} pooled",
        f"{stats['formatted']} formatted",
    ]
    for phrase in expected_stats_phrases:
        if phrase not in md:
            failures.append(f"stats phrase not found: {phrase!r}")

    # 2. Every item ID mentioned in markdown exists in the sample tape.
    mentioned_ids = set(re.findall(r"`([a-f0-9]{12})`", md))
    for iid in sorted(mentioned_ids):
        if iid not in items_by_id:
            failures.append(f"mentioned item id not in tape: {iid}")
        elif iid not in pooled_ids:
            failures.append(f"mentioned item id is not a pooled item: {iid}")

    # 3. Every quoted title in the rejected table exists in the sample tape rejections.
    # The rejected table starts after "| Title | Stage | Reason |".
    in_rejected_table = False
    for line in md.splitlines():
        if line.startswith("| Title | Stage | Reason |"):
            in_rejected_table = True
            continue
        if in_rejected_table:
            if not line.startswith("|"):
                break
            if line.startswith("|---------"):
                continue
            # Extract the title from the first cell (between quotes).
            m = re.search(r'"([^"]+)"', line)
            if m:
                title = m.group(1)
                if title not in rejected_titles:
                    failures.append(f"rejected table title not in tape rejections: {title!r}")

    # 4. Pooled item claims match tape (score and keywords).
    # Items with a full "### N. Title" subsection get detailed checks.
    # Items only listed in the "remaining" summary line get existence checks.
    for item in pooled_items:
        iid = item["id"]
        if iid not in mentioned_ids:
            continue
        score = item["scores"]["prescreen"]
        keywords = [k["term"] for k in item["scores"]["matched_keywords"]]
        section_match = re.search(
            rf"### \d+\. {re.escape(item['title'])}.*?(?=---|\n## |\Z)",
            md,
            re.DOTALL,
        )
        if section_match:
            section = section_match.group(0)
            if f"score **{score}**" not in section:
                failures.append(
                    f"score mismatch for {iid}: expected score {score} in subsection"
                )
            for kw in keywords:
                if f"`{kw}`" not in section:
                    failures.append(f"keyword {kw!r} not mentioned for {iid}")
        else:
            # Listed in the "remaining" summary: confirm summary line claims are consistent.
            summary_match = re.search(
                rf"The remaining \d+ pooled items \(`([^`]+)`\).*?followed the same chain: (.*?)(?:\n|$)",
                md,
                re.DOTALL,
            )
            if summary_match:
                summary_ids, summary_claims = summary_match.group(1), summary_match.group(2)
                if iid in summary_ids:
                    if f"score {score}" not in summary_claims and "score 5" not in summary_claims:
                        failures.append(f"summary line does not claim score {score} for {iid}")
                    for kw in keywords:
                        if f"`{kw}`" not in summary_claims and kw not in summary_claims:
                            failures.append(f"summary line does not mention keyword {kw!r} for {iid}")

    if failures:
        print(f"FAIL: {len(failures)} harness check(s) failed")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PASS: sample issue matches sample tape")
    print(f"  - report stats: {stats}")
    print(f"  - pooled items checked: {len([i for i in pooled_items if i['id'] in mentioned_ids])}")
    checked_rejected_titles = {
        m.group(1)
        for line in md.splitlines()
        if line.startswith("|") and (m := re.search(r'"([^"]+)"', line))
    }
    print(f"  - rejected table titles checked: {len(rejected_titles & checked_rejected_titles)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
