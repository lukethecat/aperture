"""
report.py — Report generation (the "publish" stage).

Produces a plain-text daily report from pooled items. If an LLM provider is
configured, it may be used for formatting; otherwise a simple structured report
is emitted. The report is written to stdout/files and recorded on the tape.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List

from . import tape
from .verifier import call_llm, get_llm_provider


def _format_simple_report(vertical: str, today: str, items: List[Dict[str, Any]]) -> str:
    """Fallback formatter when no LLM provider is available."""
    lines = [f"# Daily Report {today} ({vertical})", ""]
    for idx, item in enumerate(items, 1):
        title = item.get("title", "")
        url = item.get("url", "")
        source = item.get("source_name", "")
        summary = item.get("summary", "")
        score = item.get("scores", {}).get("prescreen", 0)
        lines.append(f"{idx}. {title}")
        if summary:
            lines.append(f"   Summary: {summary}")
        if source:
            lines.append(f"   Source: {source}")
        if url:
            lines.append(f"   URL: {url}")
        lines.append(f"   Score: {score}")
        lines.append("")
    return "\n".join(lines)


def _format_llm_report(vertical: str, today: str, items: List[Dict[str, Any]]) -> str:
    """Use the configured LLM provider to format the report."""
    if not items:
        return f"# Daily Report {today} ({vertical})\n\nNo items today."

    prompt_items = []
    for item in items:
        prompt_items.append({
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "source": item.get("source_name", ""),
            "url": item.get("url", ""),
        })

    import json
    prompt = (
        "You are a news editor. Turn the following items into a concise daily report. "
        "Group related items. Output plain Markdown with sections.\n\n"
        f"Items:\n{json.dumps(prompt_items, ensure_ascii=False, indent=1)}"
    )
    result = call_llm(prompt)
    if result and isinstance(result, str):
        return result
    if result and isinstance(result, dict) and "report" in result:
        return result["report"]
    return _format_simple_report(vertical, today, items)


def generate_report(vertical: str,
                    timings: Dict[str, float] = None,
                    use_llm: bool = True) -> Dict[str, Any]:
    """
    Generate a daily report from today's pooled items.

    Parameters:
      vertical: the vertical name
      timings: optional stage timings for the status footer
      use_llm: whether to try LLM formatting when a provider is configured
    """
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    date_short = now.strftime("%y%m%d")

    all_items = tape.query(vertical, type="item")
    today_items = [
        i for i in all_items
        if i.get("stage") == "pooled" and i.get("ts", "").startswith(today)
    ]

    if not today_items:
        body = f"# Daily Report {date_short} ({vertical})\n\nNo pooled items today."
        return {
            "title": f"Daily Report {date_short} ({vertical})",
            "body": body,
            "stats": {"pooled": 0, "formatted": 0},
        }

    provider = get_llm_provider()
    if use_llm and provider:
        body = _format_llm_report(vertical, today, today_items)
    else:
        body = _format_simple_report(vertical, today, today_items)

    # Status footer
    lines = body.splitlines()
    lines.append("")
    lines.append("---")
    lines.append("Status for Nerds")

    frontpages = tape.query(vertical, type="frontpage")
    today_fp = [f for f in frontpages if f.get("date") == today]
    total_scanned = sum(f.get("count", 0) for f in today_fp)

    today_item_records = [
        i for i in all_items
        if i.get("ts", "").startswith(today)
        and i.get("stage") in ("prescreened", "verified", "pooled", "rejected")
    ]
    rejected_count = len([i for i in today_item_records if i.get("stage") == "rejected"])
    prescreened_count = len(today_item_records)

    sources = tape.query(vertical, type="source")
    source_map: Dict[str, Dict[str, Any]] = {}
    for s in sources:
        sid = s.get("id")
        if sid:
            source_map[sid] = s
    ok_sources = sum(
        1 for s in source_map.values()
        if s.get("health", {}).get("fail_count", 0) == 0
    )

    lines.append(f"- Sources: {len(source_map)} ({ok_sources} healthy) -> scanned: {total_scanned}")
    lines.append(
        f"- Prescreened: {prescreened_count - rejected_count} -> "
        f"pooled: {len(today_items)} -> report: {len(today_items)}"
    )

    if timings:
        for stage, t in timings.items():
            lines.append(f"- {stage}: {t:.1f}s")

    alerts = [
        f"{s['name']}({s['health']['fail_count']} fails)"
        for s in source_map.values()
        if s.get("health", {}).get("fail_count", 0) >= 3
    ]
    if alerts:
        lines.append(f"- Alerts: {', '.join(alerts)}")

    body = "\n".join(lines)

    tape.append(
        vertical,
        {
            "type": "report",
            "date": today,
            "vertical": vertical,
            "item_ids": [i.get("id", "") for i in today_items],
            "generated_at": now.isoformat(),
            "stats": {
                "scanned": total_scanned,
                "prescreened": prescreened_count,
                "rejected": rejected_count,
                "pooled": len(today_items),
                "formatted": len(today_items),
            },
        },
    )

    return {
        "title": f"Daily Report {date_short} ({vertical})",
        "body": body,
        "stats": {
            "scanned": total_scanned,
            "prescreened": prescreened_count,
            "rejected": rejected_count,
            "pooled": len(today_items),
            "formatted": len(today_items),
        },
    }


def save_report(report: Dict[str, Any], out_dir: str) -> None:
    """Save report body to a text file."""
    import os
    os.makedirs(out_dir, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%y%m%d")
    path = os.path.join(out_dir, f"report_{today}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report["body"])
