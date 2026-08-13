"""
report.py — Report generation (the "publish" stage).

Produces a plain-text daily report from pooled items. If an LLM provider is
configured, it may be used for formatting; otherwise a simple structured report
is emitted. The report is written to stdout/files and recorded on the tape.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from . import tape
from .profile import get_profile
from .verifier import call_llm, get_llm_provider


def _local_today() -> str:
    """Return today's date in the system's local timezone."""
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def _utc_ts_to_local_date(ts: str) -> str:
    """Convert an ISO UTC timestamp string to the local date."""
    if not ts:
        return ""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%Y-%m-%d")


def _vertical_display_name(vertical: str, language: str = "en") -> str:
    """Map a vertical slug to a human-readable report title."""
    mapping = {
        "ai-frontier": {"en": "AI Frontier Daily", "zh": "AI 前沿日报"},
        "tech": {"en": "Tech Daily", "zh": "科技日报"},
    }
    names = mapping.get(vertical, {
        "en": f"{vertical.replace('-', ' ').title()} Daily",
        "zh": f"{vertical.replace('-', ' ')} 日报",
    })
    return names.get(language, names["en"])


def _is_human_feed_source(source: Dict[str, Any]) -> bool:
    """Return True if the source is configured as human-feed."""
    profile = source.get("extract_profile", {})
    if not isinstance(profile, dict):
        return False
    return profile.get("method", "") == "human_feed"


def _human_feed_sources_with_items_today(vertical: str, today: str) -> Set[str]:
    """Return human-feed source ids that have at least one item today."""
    active: Set[str] = set()
    for item in tape.query(vertical, type="item"):
        if _utc_ts_to_local_date(item.get("ts", "")) == today:
            active.add(item.get("source_id", ""))
    return active


def _format_simple_report(vertical: str, today: str, items: List[Dict[str, Any]],
                          summary: str = "", language: str = "en") -> str:
    """Fallback formatter when no LLM provider is available."""
    title = _vertical_display_name(vertical, language)
    editor_label = "编辑手记" if language == "zh" else "Editor's note"
    summary_label = "摘要" if language == "zh" else "Summary"
    source_label = "来源" if language == "zh" else "Source"
    url_label = "链接" if language == "zh" else "URL"
    score_label = "评分" if language == "zh" else "Score"
    lines = [f"# {title} · {today}", ""]
    if summary:
        lines.append(f"> **{editor_label}**：{summary}")
        lines.append("")
    for idx, item in enumerate(items, 1):
        title = item.get("title", "")
        url = item.get("url", "")
        source = item.get("source_name", "")
        item_summary = item.get("summary", "")
        score = item.get("scores", {}).get("prescreen", 0)
        lines.append(f"{idx}. {title}")
        if item_summary:
            lines.append(f"   {summary_label}：{item_summary}")
        if source:
            lines.append(f"   {source_label}：{source}")
        if url:
            lines.append(f"   {url_label}：{url}")
        lines.append(f"   {score_label}：{score}")
        lines.append("")
    return "\n".join(lines)


def _format_llm_report(vertical: str, today: str, items: List[Dict[str, Any]],
                       summary: str = "", language: str = "en") -> str:
    """Use the configured LLM provider to format the report."""
    if not items:
        title = _vertical_display_name(vertical, language)
        no_items = "今日无条目。" if language == "zh" else "No items today."
        return f"# {title} · {today}\n\n{no_items}"

    prompt_items = []
    for item in items:
        prompt_items.append({
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "source": item.get("source_name", ""),
            "url": item.get("url", ""),
        })

    import json
    if language == "zh":
        prompt = (
            "你是一位中文科技新闻编辑。请将以下英文一手 AI 前沿资讯整理成一份简洁的中文日报。"
            "标题和逐条点评用中文，保留原始英文来源和 URL。"
            "将相关条目分组。输出纯 Markdown，顶部包含一段简短的编辑手记。\n\n"
            f"编辑手记（置于顶部作为简短段落）：{summary}\n\n"
            f"条目：\n{json.dumps(prompt_items, ensure_ascii=False, indent=1)}"
        )
    else:
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
    return _format_simple_report(vertical, today, items, summary, language=language)


def _generate_summary(items: List[Dict[str, Any]], use_llm: bool = False,
                      language: str = "en") -> str:
    """
    Generate a 100-300 character daily summary of the pooled items.
    Falls back to a rule-based summary when no LLM is available.
    """
    if not items:
        return "今日无条目入选。" if language == "zh" else "No frontier items made the cut today."

    if use_llm:
        provider = get_llm_provider()
        if provider:
            titles = [i.get("title", "") for i in items]
            if language == "zh":
                prompt = (
                    "请将以下 AI 前沿新闻标题总结成一段 100-300 字的中文编辑手记，"
                    "概括今日主线。平实、不夸张。\n\n"
                    "标题：\n" + "\n".join(f"- {t}" for t in titles)
                )
            else:
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
        if language == "zh":
            return f"今日共 {len(items)} 条入选，覆盖前沿多个方向。"
        return f"Today {len(items)} items made the cut across the frontier landscape."

    theme_text = "、".join(themes) if language == "zh" else ", ".join(themes)
    if language == "zh":
        return (
            f"今日共 {len(items)} 条入选，主线围绕 {theme_text}。"
            f"AI 前沿仍在多线并进。"
        )
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


def _format_editorial_review_pool(items: List[Dict[str, Any]], language: str = "en") -> str:
    """Render the editorial review pool section for borderline items."""
    if not items:
        return ""
    er_label = "编辑复审池" if language == "zh" else "Editorial review pool"
    er_hint = (
        "以下条目 score=5，未进入主报告，请 frontier-editor 每日审稿时 yes/no/skip："
        if language == "zh"
        else "The following score=5 items are held for daily editorial review:"
    )
    lines = ["", "---", er_label, er_hint]
    for idx, item in enumerate(items, 1):
        lines.append(f"{idx}. {item.get('title', '')}")
        lines.append(f"   来源：{item.get('source_name', '')} — {item.get('url', '')}")
        lines.append(f"   评分：{item.get('scores', {}).get('prescreen', 0)}")
    return "\n".join(lines)


def _source_acquisition_badge(extract_profile: Dict[str, Any], list_url: str) -> str:
    """
    Map extraction method to acquisition taxonomy badge.

    Mapping:
      - rss / json_api      -> pull
      - generic_links / regex -> scan
      - human_feed or no list_url -> human-feed
    """
    method = (extract_profile or {}).get("method", "")
    if method in ("rss", "json_api"):
        return "pull"
    if method in ("generic_links", "regex"):
        return "scan"
    if method == "human_feed" or not list_url:
        return "human-feed"
    return "scan"


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
    now = datetime.now().astimezone()
    today = now.strftime("%Y-%m-%d")
    date_short = now.strftime("%y%m%d")

    all_items = tape.query(vertical, type="item")
    today_pooled = [
        i for i in all_items
        if i.get("stage") == "pooled"
        and _utc_ts_to_local_date(i.get("ts", "")) == today
    ]
    today_borderline = [
        i for i in all_items
        if i.get("stage") == "borderline"
        and _utc_ts_to_local_date(i.get("ts", "")) == today
    ]
    # Deduplication may cluster same-event items from different sources.
    # Keep only the highest-scoring item from each cluster for the report.
    cluster_groups: Dict[str, List[Dict[str, Any]]] = {}
    for i in today_pooled:
        cid = i.get("cluster_id") or i.get("id")
        cluster_groups.setdefault(cid, []).append(i)
    today_items = [
        sorted(items, key=lambda x: x.get("scores", {}).get("prescreen", 0), reverse=True)[0]
        for items in cluster_groups.values()
    ]

    profile = get_profile(vertical) or {}
    language = profile.get("language", "en")

    if not today_items:
        title = _vertical_display_name(vertical, language)
        no_pooled = "今日无入选条目。" if language == "zh" else "No pooled items today."
        body = f"# {title} · {today}\n\n{no_pooled}"
        body += _format_editorial_review_pool(today_borderline, language=language)
        return {
            "title": f"{title} · {today}",
            "body": body,
            "stats": {"pooled": 0, "formatted": 0},
        }

    provider = get_llm_provider()
    summary = _generate_summary(
        today_items,
        use_llm=use_llm and provider is not None,
        language=language,
    )
    if use_llm and provider:
        body = _format_llm_report(vertical, today, today_items, summary=summary, language=language)
    else:
        body = _format_simple_report(vertical, today, today_items, summary=summary, language=language)

    # Editorial review pool
    body += _format_editorial_review_pool(today_borderline, language=language)

    lines = body.splitlines()
    lines.append("")
    lines.append("---")
    stats_label = "Aperture 统计" if language == "zh" else "Aperture Stats"
    lines.append(stats_label)

    frontpages = tape.query(vertical, type="frontpage")
    today_fp = [
        f for f in frontpages
        if _utc_ts_to_local_date(f.get("ts", f"{f.get('date', '')}T00:00:00+00:00")) == today
    ]
    total_scanned = sum(f.get("count", 0) for f in today_fp)

    today_item_records = [
        i for i in all_items
        if _utc_ts_to_local_date(i.get("ts", "")) == today
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

    alerts = [
        f"{s['name']}({s['health']['fail_count']} fails)"
        for s in source_map.values()
        if s.get("health", {}).get("fail_count", 0) >= 3
    ]

    if language == "zh":
        lines.append(f"- 来源：{len(source_map)} 个（{ok_sources} 个健康）→ 扫描：{total_scanned}")
        lines.append(
            f"- 初筛：{prescreened_count} → 拒：{rejected_count} → "
            f"入池：{len(today_items)} → 成稿：{len(today_items)}"
        )
        if timings:
            lines.append(f"- 耗时：{_format_timing_footer(timings)}")
        if alerts:
            lines.append(f"- 告警：{', '.join(alerts)}")
        lines.append("")
        lines.append("## 来源注册表")
    else:
        lines.append(f"- Sources: {len(source_map)} ({ok_sources} healthy) → scanned: {total_scanned}")
        lines.append(
            f"- Prescreened: {prescreened_count} → rejected: {rejected_count} → "
            f"pooled: {len(today_items)} → report: {len(today_items)}"
        )
        if timings:
            lines.append(f"- Timings: {_format_timing_footer(timings)}")
        if alerts:
            lines.append(f"- Alerts: {', '.join(alerts)}")
        lines.append("")
        lines.append("## Source registry")
    hf_active_today = _human_feed_sources_with_items_today(vertical, today)
    for sid in sorted(source_map):
        s = source_map[sid]
        health = s.get("health", {})
        fails = health.get("fail_count", 0)
        is_hf = _is_human_feed_source(s)

        if fails > 0:
            status = "🔴"
        elif is_hf and sid not in hf_active_today:
            # Human-feed sources that are healthy but contributed nothing today
            # show a standby indicator rather than a false "active" green.
            status = "⚪"
        else:
            status = "🟢"

        name = s.get("name", sid)
        list_url = s.get("list_url", "")
        badge = _source_acquisition_badge(s.get("extract_profile", {}), list_url)
        if list_url:
            name_link = f"[{name}]({list_url})"
        else:
            name_link = name
        lines.append(f"- {status} {name_link} · {badge}")

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

    report_title = f"{_vertical_display_name(vertical)} · {today}"
    return {
        "title": report_title,
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
    """Save report body as a Markdown daily issue."""
    import os
    os.makedirs(out_dir, exist_ok=True)
    today = _local_today()
    path = os.path.join(out_dir, f"{today}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report["body"])
