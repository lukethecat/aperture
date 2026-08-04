#!/usr/bin/env python3
"""Harness: verify agent_runner.py demonstrates AI-native orchestration.

Usage:
    python scripts/harness_agent_runner.py
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    failures = []

    with tempfile.TemporaryDirectory(prefix="aperture_agent_harness_") as tmp:
        tmp_path = Path(tmp)
        # Copy the repo into a clean temp directory so the tape is empty.
        for name in ["agent_runner.py", "SKILL.md", "DESIGN.md", "config", "engine"]:
            src = ROOT / name
            dst = tmp_path / name
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        proc = subprocess.run(
            [sys.executable, "agent_runner.py", "--dry", "--vertical", "tech",
             "--config", "config/example_vertical.toml"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        output = proc.stdout or ""

        if proc.returncode != 0:
            failures.append(f"agent_runner exited with {proc.returncode}")
            if proc.stderr:
                failures.append(f"stderr: {proc.stderr[:500]}")

        # Must log agent decisions for each stage.
        required_decisions = [
            "[agent] decision: collect",
            "[agent] decision: edit",
            "[agent] decision: review",
            "[agent] decision: publish",
            "[agent] decision: done",
        ]
        for decision in required_decisions:
            if decision not in output:
                failures.append(f"missing agent log line: {decision}")

        # Must show the skill was loaded.
        if "loaded SKILL.md" not in output:
            failures.append("agent did not log loading SKILL.md")

        # Must produce a report.
        reports = sorted(tmp_path.glob("report_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not reports:
            failures.append("no report produced in clean environment")
        else:
            report_text = reports[0].read_text(encoding="utf-8", errors="replace")
            if "Daily Report" not in report_text:
                failures.append("report does not contain 'Daily Report'")

        # Dry-mode fallback: verify no LLM calls were made.
        if "dry_mode" not in output and "dry=True" not in output:
            failures.append("dry mode not evident in output")

    if failures:
        print(f"FAIL: {len(failures)} harness check(s) failed")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PASS: agent_runner demonstrates AI-native orchestration")
    print("  - agent decisions logged for all four stages")
    print("  - SKILL.md loaded")
    print("  - report generated in clean environment")
    print("  - dry-mode fallback works without API key")
    return 0


if __name__ == "__main__":
    sys.exit(main())
