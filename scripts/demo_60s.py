#!/usr/bin/env python3
"""60-second demo: install-free, API-key-free run of Aperture.

This script runs the reference implementation in dry mode and prints the
generated daily report. It is the fastest way to see the tape-based pipeline
in action.

Usage:
    python scripts/demo_60s.py
"""

import glob
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=ROOT, check=True, text=True)


def main() -> int:
    print("Aperture — 60 second demo")
    print("=" * 60)
    print()

    start = time.time()

    # Step 1: confirm environment
    print("Step 1: Python version")
    run([sys.executable, "--version"])
    print()

    # Step 2: run the pipeline in dry mode (no API key needed)
    print("Step 2: Run the pipeline in --dry mode")
    print("        (prescreen + dedup are real; LLM review is stubbed)")
    run([
        sys.executable, "-m", "engine.pipeline",
        "--dry", "--vertical", "tech",
        "--config", "config/example_vertical.toml",
    ])
    print()

    # Step 3: show the report that was just written
    print("Step 3: Latest report")
    reports = sorted(ROOT.glob("report_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if reports:
        report = reports[0]
        print(f"        {report.name}")
        print()
        print(report.read_text(encoding="utf-8"))
    else:
        print("        No report found.")
        return 1

    elapsed = time.time() - start
    print(f"Done in {elapsed:.1f}s — no API key required.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
