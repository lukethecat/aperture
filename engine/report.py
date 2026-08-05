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


def _format_simple_report(vertical: str, today: str, items: List[Dict[str, Any]],
                          summary: str = "") -> str:
    """Fallback formatter when no LLM provider is available."""
    lines = [f"# Daily Report {today} ({vertical})", ""]
    if summary:
        lines.append(f"> **Editor's note**: {summary}")
        lines.append("")
    for idx, item in enumerate(items, 1):
        title = item.get("title", "")
        url = item.get("url", "")
        source = item.get("source_name", "")
        item_summary = item.get("summary", "")
        score = item.get("scores", {}).get("prescreen", 0)
        lines.append(f"{idx}. {title}")
        if item_summary:
            lines.append(f"   Summary: {item_summary}")
        if source:
            lines.append(f"   Source: {source}")
        if url:
            lines.append(f"   URL: {url}")
        lines.append(f"   Score: {score}")
        lines.append("")
    return "\n".join(lines)


def _format_llm_report(vertical: str, today: str, items: List[Dict[str, Any]],
                       summary: str = "") -> str:
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
        f"Editor's note (include at the top as a short paragraph): {summary}\n\n"
        f"Items:\n{json.dumps(prompt_items, ensure_ascii=False, indent=1)}"
    )
    result = call_llm(prompt)
    if result and isinstance(result, str):
        return result
    if result and isinstance(result, dict) and "report" in result:
        return result["report"]
    return _format_simple_report(vertical, today, items, summary)


def _generate_summary(items: List[Dict[str, Any]], use_llm: bool = False) -> str:
    """
    Generate a 100-300 character daily summary of the pooled items.
    Falls back to a rule-based summary when no LLM is available.
    """
    if not items:
        return "No frontier items made the cut today."

    if use_llm:
        provider = get_llm_provider()
        if provider:
            titles = [i.get("title", "") for i in items]
            prompt = (
                "Summarize the following AI-news headlines in one concise paragraph "
                "(100-300 characters) describing the day's main thread. Be plain, no hype.\n\n"
                "Headlines:\n" + "\n".join(f"- {t}" for t in titles)
            )
            result = call_llm(prompt)
            if result and isinstance(result, str):
                summary = result.strip().strip('"').strip("'")
                if 50 <= len(summary) <= 600:
                    return summary
            if result and isinstance(result, dict) and "summary" in result:
                summary = str(result["summary"]).strip()
                if 50 <= len(summary) <= 600:
                    return summary

    # Rule-based fallback: cluster by matched categories and keywords.
    category_counts: Dict[str, int] = {}
    keyword_weights: Dict[str, int] = {}
    for item in items:
        for cat in item.get("scores", {}).get("matched_categories", []):
            name = cat.get("category", "")
            if name:
                category_counts[name] = category_counts.get(name, 0) + 1
        for kw in item.get("scores", {}).get("matched_keywords", []):
            term = kw.get("term", "")
            weight = kw.get("weight", 0)
            if term:
                keyword_weights[term] = keyword_weights.get(term, 0) + weight

    top_cats = sorted(category_counts, key=lambda k: category_counts[k], reverse=True)[:3]
    top_kws = sorted(keyword_weights, key=lambda k: keyword_weights[k], reverse=True)[:3]

    themes = []
    if top_cats:
        themes.extend(top_cats)
    if len(top_kws) > len(top_cats):
        for kw in top_kws:
            if kw not in themes:
                themes.append(kw)
    themes = themes[:3]

    if not themes:
        return f"Today {len(items)} items made the cut across the frontier landscape."

    theme_text = ", ".join(themes)
    return (
        f"Today {len(items)} items made the cut, centered on {theme_text}. "
        f"The frontier continues to move on multiple fronts at once."
    )


def _format_timing_footer(timings: Dict[str, float]) -> str:
    """Render a compact timing footer."""
    if not timings:
        return ""
    total = sum(timings.values())
    parts = ", ".join(f"{stage}: {t:.1f}s" for stage, t in timings.items())
    return f"Total: {total:.1f}s ({parts})"


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
    summary = _generate_summary(today_items, use_llm=use_llm and provider is not None)
    if use_llm and provider:
        body = _format_llm_report(vertical, today, today_items, summary=summary)
    else:
        body = _format_simple_report(vertical, today, today_items, summary=summary)

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
        lines.append(f"- {_format_timing_footer(timings)}")

    alerts = [
        f"{s['name']}({s['health']['fail_count']} fails)"
        for s in source_map.values()
        if s.get("health", {}).get("fail_count", 0) >= 3
    ]
    if alerts:
        lines.append(f"- Alerts: {', '.join(alerts)}")

    # Source registry
    lines.append("")
    lines.append("## Source registry")
    for sid in sorted(source_map):
        s = source_map[sid]
        health = s.get("health", {})
        fails = health.get("fail_count", 0)
        status = "🟢" if fails == 0 else "🔴"
        lines.append(f"- {status} {s.get('name', sid)} — {s.get('list_url', '')}")

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
