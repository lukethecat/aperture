#!/usr/bin/env python3
"""agent_runner.py — Run Aperture as an LLM-agent-orchestrated skill.

The agent reads SKILL.md, maintains a small state machine, and decides which
stage to execute next. In production you can point it at a real LLM provider;
without one it falls back to a deterministic plan so the demo always works.

Usage:
    python agent_runner.py --dry --vertical tech --config config/example_vertical.toml
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine import tape
from engine.dedup import dedup_and_cluster
from engine.pipeline import ensure_profile, ensure_sources, get_sources, load_config
from engine.prescreen import prescreen_candidates
from engine.report import generate_report, save_report
from engine.scanner import scan_all
from engine.verifier import verify_candidates


def load_skill() -> str:
    """Load the skill specification that guides the agent."""
    skill_path = Path(__file__).resolve().parent / "SKILL.md"
    return skill_path.read_text(encoding="utf-8", errors="replace")


def agent_decide(
    state: Dict[str, Any],
    skill_text: str,
    provider: Optional[Any] = None,
) -> str:
    """Decide the next pipeline stage.

    With a provider, this is where the LLM reasons over the skill + state.
    Without a provider, we use the deterministic collect->edit->review->publish
    plan, but we still log the decision as an agent decision.
    """
    stages = ["collect", "edit", "review", "publish", "done"]
    current = state.get("stage", "start")

    if provider is not None:
        # LLM-driven decision (placeholder hook). In a full implementation the
        # provider would receive skill_text + state and return the next stage.
        # For now we fall through to the deterministic plan so the harness can
        # run without an API key.
        pass

    # Deterministic fallback: advance through the four stages.
    if current == "start":
        return "collect"
    if current in stages:
        idx = stages.index(current)
        if idx + 1 < len(stages):
            return stages[idx + 1]
    return "done"


def agent_reason(stage: str, state: Dict[str, Any]) -> str:
    """Return a short human-readable reason for the agent's decision."""
    reasons = {
        "collect": "SKILL.md section 3.1: fetch front pages and diff against yesterday's snapshot.",
        "edit": "SKILL.md section 3.2: prescreen candidates with the weighted profile.",
        "review": "SKILL.md section 3.3: verify prescreened items (stubbed in --dry mode).",
        "publish": "SKILL.md section 3.4: deduplicate, cluster, and generate the report.",
        "done": "Pipeline complete; no further stages.",
    }
    return reasons.get(stage, "Advancing to next stage.")


def run_agent(
    vertical: str,
    config_path: str,
    dry: bool = False,
    out_dir: str = ".",
) -> Dict[str, Any]:
    """Run the four-stage pipeline under agent orchestration."""
    skill_text = load_skill()
    cfg = load_config(config_path)
    ensure_profile(vertical, cfg)
    ensure_sources(vertical, cfg.get("sources", []))

    state: Dict[str, Any] = {"stage": "start", "vertical": vertical, "dry": dry}
    results: Dict[str, Any] = {}
    timings: Dict[str, float] = {}

    print("=" * 60)
    print("Aperture agent runner")
    print("=" * 60)
    print(f"[agent] loaded SKILL.md ({len(skill_text)} chars)")
    print(f"[agent] vertical={vertical}, dry={dry}")
    print()

    sources = get_sources(vertical)
    if not sources:
        print("[agent] no sources configured; pipeline complete.")
        state["stage"] = "done"
        report = generate_report(vertical, timings=timings, use_llm=False)
        return {"state": state, "report": report, "timings": timings}

    while True:
        next_stage = agent_decide(state, skill_text)
        state["stage"] = next_stage
        if next_stage == "done":
            print("[agent] decision: done — pipeline complete")
            break

        reason = agent_reason(next_stage, state)
        print(f"[agent] decision: {next_stage} — {reason}")

        if next_stage == "collect":
            t0 = time.time()
            scan_stats = scan_all(vertical, sources)
            timings["collect"] = time.time() - t0
            candidates = scan_stats.get("candidates", [])
            state["candidates"] = candidates
            print(f"[collect] {len(candidates)} candidates ({timings['collect']:.1f}s)")
            if not candidates:
                print("[agent] no candidates; skipping to publish")
                state["stage"] = "review"  # will advance to publish next loop

        elif next_stage == "edit":
            candidates = state.get("candidates", [])
            if not candidates:
                print("[edit] 0 passed / 0 rejected (no candidates)")
                state["prescreen"] = {"passed": 0, "rejected": 0, "passed_items": []}
            else:
                t1 = time.time()
                ps = prescreen_candidates(candidates, vertical)
                timings["edit"] = time.time() - t1
                state["prescreen"] = ps
                print(f"[edit] {ps['passed']} passed / {ps['rejected']} rejected ({timings['edit']:.1f}s)")

        elif next_stage == "review":
            ps = state.get("prescreen", {"passed_items": []})
            passed_items = ps.get("passed_items", [])
            if not passed_items or dry:
                # Dry mode: stub the review gate.
                verified_items = []
                for item in passed_items:
                    item["stage"] = "verified"
                    item["scores"]["verify"] = {"llm_called": False, "dry_mode": True}
                    tape.append(vertical, item)
                    verified_items.append(item)
                vf = {
                    "vertical": vertical,
                    "passed": len(verified_items),
                    "rejected": 0,
                    "passed_items": verified_items,
                    "rejected_items": [],
                    "provider_used": False,
                }
                reason_suffix = " (dry mode: LLM gate stubbed)"
            else:
                t2 = time.time()
                vf = verify_candidates(passed_items, vertical)
                timings["review"] = time.time() - t2
                reason_suffix = ""
            state["verify"] = vf
            print(f"[review] {vf['passed']} passed / {vf['rejected']} rejected{reason_suffix}")

        elif next_stage == "publish":
            vf = state.get("verify", {"passed_items": []})
            passed_items = vf.get("passed_items", [])
            t3 = time.time()
            dedup = dedup_and_cluster(passed_items, vertical)
            timings["publish_pool"] = time.time() - t3
            state["dedup"] = dedup
            print(f"[publish/pool] {dedup['pooled_count']} pooled ({timings['publish_pool']:.1f}s)")

            t4 = time.time()
            report = generate_report(vertical, timings=timings, use_llm=not dry)
            timings["publish_report"] = time.time() - t4
            state["report"] = report
            print(f"[publish/report] {report['stats'].get('formatted', 0)} items ({timings['publish_report']:.1f}s)")

        print()

    report = state.get("report") or generate_report(vertical, timings=timings, use_llm=False)
    print("=" * 60)
    print(report["body"])
    save_report(report, out_dir)
    print(f"\nReport saved to {out_dir}")

    return {"state": state, "report": report, "timings": timings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Aperture agent runner")
    parser.add_argument("--vertical", default="tech", help="Vertical name (default: tech)")
    parser.add_argument("--config", default="config/example_vertical.toml",
                        help="Path to vertical config")
    parser.add_argument("--dry", action="store_true",
                        help="Run without LLM provider (rule-only)")
    parser.add_argument("--out-dir", default=".", help="Directory to save report")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"Config not found: {args.config}", file=sys.stderr)
        return 1

    run_agent(
        vertical=args.vertical,
        config_path=args.config,
        dry=args.dry,
        out_dir=args.out_dir,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
