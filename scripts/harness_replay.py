#!/usr/bin/env python3
"""Harness: verify scripts/replay.py reconstructs decision chains correctly.

Usage:
    python scripts/harness_replay.py
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_replay(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "scripts/replay.py"] + args,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout or ""


def main() -> int:
    failures = []

    # 1. Replay a known pooled item by ID.
    code, out = run_replay(["--item", "d02fcce3d996", "--vertical", "tech"])
    if code != 0:
        failures.append("--item d02fcce3d996 exited non-zero")
    else:
        required = [
            "Decision replay for:",
            "Stage:   pooled",
            "Front page fetched at",
            "Score: 5",
            "Matched keywords: AI(5)",
            "Pooled. Cluster ID:",
        ]
        for phrase in required:
            if phrase not in out:
                failures.append(f"pooled item replay missing: {phrase!r}")

    # 2. Replay the same item by URL.
    code, out = run_replay(["--why", "https://epoch.ai/MirrorCode", "--vertical", "tech"])
    if code != 0:
        failures.append("--why https://epoch.ai/MirrorCode exited non-zero")
    else:
        if "Stage:   pooled" not in out:
            failures.append("URL replay did not identify pooled stage")
        if "Score: 5" not in out:
            failures.append("URL replay did not show prescreen score")

    # 3. Replay a rejected item by URL.
    code, out = run_replay(["--why", "https://news.ycombinator.com/item?id=49156683", "--vertical", "tech"])
    if code != 0:
        failures.append("--why rejected URL exited non-zero")
    else:
        if "Stage:   rejected" not in out:
            failures.append("rejected URL replay did not show rejected stage")
        if "low_score" not in out:
            failures.append("rejected URL replay did not show low_score reason")

    if failures:
        print(f"FAIL: {len(failures)} harness check(s) failed")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PASS: replay.py reconstructs decision chains for pooled and rejected items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
