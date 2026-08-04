#!/usr/bin/env python3
"""Harness: verify scripts/demo_60s.py runs end-to-end without an API key.

Usage:
    python scripts/harness_demo.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    # Run the demo script. It must complete without any API key.
    env = {"PATH": str(Path(sys.executable).parent)}
    proc = subprocess.run(
        [sys.executable, "scripts/demo_60s.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )

    failures = []
    if proc.returncode != 0:
        failures.append(f"demo script exited with {proc.returncode}")
        if proc.stderr:
            failures.append(f"stderr: {proc.stderr[:500]}")

    output = proc.stdout or ""

    # The demo must claim it ran in --dry mode.
    if "--dry" not in output:
        failures.append("demo output does not mention --dry mode")

    # A report must have been produced.
    reports = sorted(ROOT.glob("report_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        failures.append("no report_*.txt file was produced")
    else:
        report_text = reports[0].read_text(encoding="utf-8", errors="replace")
        if "Daily Report" not in report_text:
            failures.append("report does not contain 'Daily Report'")
        if "Source:" not in report_text:
            failures.append("report contains no items")

    if failures:
        print(f"FAIL: {len(failures)} harness check(s) failed")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PASS: 60s demo runs end-to-end without an API key")
    print(f"  - latest report: {reports[0].name}")
    print(f"  - report items: {report_text.count('Source:')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
