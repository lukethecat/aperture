"""
pipeline.py — Four-stage pipeline entry point.

Stages (collect -> edit -> review -> publish):
  1. collect: scan configured sources and produce candidates
  2. edit: prescreen candidates using the profile
  3. review: verify prescreened items with an optional LLM provider
  4. publish: deduplicate, cluster, and generate the report

Usage:
  python -m engine.pipeline --dry --vertical tech
  python -m engine.pipeline --vertical tech --config config/my_vertical.toml
"""
import argparse
import os
import sys
import time
from typing import Any, Dict, List

# Windows consoles may default to a legacy code page that cannot render
# registry/status emoji used in reports. Force UTF-8 for stdout/stderr.
if sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from . import tape
from .dedup import dedup_and_cluster, print_dedup_stats
from .prescreen import prescreen_candidates, print_prescreen_stats
from .profile import init_profile
from .report import generate_report, save_report
from .scanner import scan_all
from .verifier import verify_candidates, print_verify_stats


def _load_toml_config(path: str) -> Dict[str, Any]:
    """Load a TOML config using stdlib tomllib (Python 3.11+)."""
    try:
        import tomllib  # type: ignore
    except ImportError:
        raise RuntimeError(
            "TOML config requires Python 3.11+ (tomllib). "
            "Pass a JSON file or initialize profile manually."
        )
    with open(path, "rb") as f:
        return tomllib.load(f)


def _load_json_config(path: str) -> Dict[str, Any]:
    import json
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(path: str) -> Dict[str, Any]:
    """Load a vertical configuration from TOML or JSON."""
    if path.endswith(".json"):
        return _load_json_config(path)
    return _load_toml_config(path)


def ensure_profile(vertical: str, cfg: Dict[str, Any]) -> None:
    """Initialize or sync the profile from the vertical config."""
    from .profile import get_profile, sync_profile_from_config
    existing = get_profile(vertical)
    if not existing:
        init_profile(
            vertical,
            keywords=cfg.get("keywords", []),
            categories=cfg.get("categories", []),
            negatives=cfg.get("negatives", []),
            reason="loaded from config",
            threshold=cfg.get("threshold", 2),
            language=cfg.get("language", "en"),
            editorial_review_scores=cfg.get("editorial_review_scores", []),
        )
        return

    # Sync config drift (threshold, language, editorial_review_scores).
    sync_profile_from_config(
        vertical,
        threshold=cfg.get("threshold"),
        language=cfg.get("language"),
        editorial_review_scores=cfg.get("editorial_review_scores"),
    )


def ensure_sources(vertical: str, sources: List[Dict[str, Any]]) -> None:
    """Register sources on the tape if not already present."""
    existing = {s["id"]: s for s in tape.query(vertical, type="source")}
    for src in sources:
        sid = src.get("id")
        if not sid or sid in existing:
            continue
        record = {
            "type": "source",
            "id": sid,
            "name": src.get("name", sid),
            "vertical": vertical,
            "list_url": src.get("list_url", ""),
            "extract_profile": src.get("extract_profile", {}),
            "health": {"last_ok": None, "fail_count": 0},
        }
        tape.append(vertical, record)


def _human_feed_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return sources configured as human-feed."""
    result = []
    for src in sources:
        profile = src.get("extract_profile", {})
        method = profile.get("method", "") if isinstance(profile, dict) else ""
        if method == "human_feed":
            result.append(src)
    return result


def _collect_human_feed_items(vertical: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Collect human-feed items injected since the last run.

    Human-feed items are written to the tape with `stage: scanned` by the
    delivery agent (e.g. scripts/x_hunt.py). This function picks up any such
    items that have not yet been prescreened and prepends them to the
    candidate list so they go through the same funnel as pull/scan items.
    """
    from datetime import datetime, timezone

    hf_source_ids = {s["id"] for s in _human_feed_sources(sources)}
    if not hf_source_ids:
        return []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    items = tape.query(vertical, type="item")
    candidates: List[Dict[str, Any]] = []
    for item in items:
        if item.get("source_id") not in hf_source_ids:
            continue
        if item.get("stage") != "scanned":
            continue
        if not item.get("ts", "").startswith(today):
            continue
        candidate = dict(item)
        candidate.setdefault("source_name", item.get("source_id"))
        candidates.append(candidate)
    return candidates


def get_sources(vertical: str) -> List[Dict[str, Any]]:
    """Return the latest source records for a vertical."""
    all_records = tape.query(vertical, type="source")
    seen: Dict[str, Dict[str, Any]] = {}
    for r in all_records:
        sid = r.get("id")
        if sid:
            seen[sid] = r
    return list(seen.values())


def run_pipeline(vertical: str,
                 dry: bool = False,
                 max_verify: int = 20,
                 use_llm_report: bool = True) -> Dict[str, Any]:
    """Run the full collect->edit->review->publish pipeline."""
    timings: Dict[str, float] = {}

    sources = get_sources(vertical)
    if not sources:
        report = generate_report(vertical, timings=timings, use_llm=False)
        return {
            "scan": {"vertical": vertical, "sources_total": 0, "candidates": []},
            "prescreen": {"total_candidates": 0, "passed": 0, "rejected": 0},
            "verify": {"passed": 0, "rejected": 0},
            "dedup": {"pooled_count": 0},
            "report": report,
            "timings": timings,
        }

    # Collect
    t0 = time.time()
    scan_stats = scan_all(vertical, sources)
    candidates = scan_stats.get("candidates", [])
    hf_candidates = _collect_human_feed_items(vertical, sources)
    candidates.extend(hf_candidates)
    timings["collect"] = time.time() - t0
    print(f"[collect] {len(candidates)} candidates ({len(hf_candidates)} from human-feed) "
          f"({timings['collect']:.1f}s)", flush=True)

    if not candidates:
        report = generate_report(vertical, timings=timings, use_llm=not dry and use_llm_report)
        return {
            "scan": scan_stats,
            "prescreen": {"total_candidates": 0, "passed": 0, "rejected": 0},
            "verify": {"passed": 0, "rejected": 0},
            "dedup": {"pooled_count": 0},
            "report": report,
            "timings": timings,
        }

    # Edit
    t1 = time.time()
    ps = prescreen_candidates(candidates, vertical)
    timings["edit"] = time.time() - t1
    print(
        f"[edit] {ps['passed']} passed / {ps.get('borderline', 0)} borderline / "
        f"{ps['rejected']} rejected ({timings['edit']:.1f}s)",
        flush=True,
    )

    # Review
    t2 = time.time()
    if dry:
        # In dry mode, promote prescreened items without LLM review.
        verified_items = ps["passed_items"]
        for item in verified_items:
            item["stage"] = "verified"
            item["scores"]["verify"] = {"llm_called": False, "dry_mode": True}
            tape.append(vertical, item)
        vf = {
            "vertical": vertical,
            "passed": len(verified_items),
            "rejected": 0,
            "passed_items": verified_items,
            "rejected_items": [],
            "provider_used": False,
        }
    else:
        vf = verify_candidates(ps["passed_items"], vertical, max_items=max_verify)
    timings["review"] = time.time() - t2
    print(f"[review] {vf['passed']} passed / {vf['rejected']} rejected ({timings['review']:.1f}s)",
          flush=True)

    # Publish
    t3 = time.time()
    dedup = dedup_and_cluster(vf["passed_items"], vertical)
    timings["publish_pool"] = time.time() - t3
    print(f"[publish/pool] {dedup['pooled_count']} pooled ({timings['publish_pool']:.1f}s)",
          flush=True)

    t4 = time.time()
    report = generate_report(vertical, timings=timings, use_llm=not dry and use_llm_report)
    timings["publish_report"] = time.time() - t4
    print(f"[publish/report] {report['stats'].get('formatted', 0)} items ({timings['publish_report']:.1f}s)",
          flush=True)

    return {
        "scan": scan_stats,
        "prescreen": ps,
        "verify": vf,
        "dedup": dedup,
        "report": report,
        "timings": timings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Self-evolving news engine pipeline")
    parser.add_argument("--vertical", default="tech", help="Vertical name (default: tech)")
    parser.add_argument("--config", default="config/example_vertical.toml",
                        help="Path to vertical config")
    parser.add_argument("--dry", action="store_true",
                        help="Run without LLM provider (rule-only)")
    parser.add_argument("--max-verify", type=int, default=20,
                        help="Max items to verify per run")
    parser.add_argument("--no-llm-report", action="store_true",
                        help="Disable LLM report formatting even if provider is set")
    parser.add_argument("--out-dir", default=".", help="Directory to save report")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"Config not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    cfg = load_config(args.config)
    ensure_profile(args.vertical, cfg)
    ensure_sources(args.vertical, cfg.get("sources", []))

    result = run_pipeline(
        vertical=args.vertical,
        dry=args.dry,
        max_verify=args.max_verify,
        use_llm_report=not args.no_llm_report,
    )

    if "error" in result:
        print(result["error"], file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 60)
    print(result["report"]["body"])

    save_report(result["report"], args.out_dir)
    print(f"\nReport saved to {args.out_dir}")


if __name__ == "__main__":
    main()
