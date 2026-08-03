"""
verifier.py — Structured second-pass review (the "review" stage).

LLM calls are abstracted behind a provider interface. The engine ships with
an OpenAI-compatible provider; users can supply their own by setting
SENE_LLM_PROVIDER to a dotted callable path.

Without a configured provider, the pipeline falls back to a rule-only pass.
"""
import importlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from . import tape
from .scanner import _fetch_url

DEFAULT_TIMEOUT = 15
VERTICAL_FIT_THRESHOLD = 0.3
CONTENT_MAX_CHARS = 1000

_LLM_PROVIDER: Optional[Callable[[str], Any]] = None

BATCH_PROMPT = """You are a news-quality reviewer. Evaluate each item below.

For each item, output:
  is_news: true if it is a news article (not ad/job/announcement)
  is_ad: true if it is promotional
  is_job: true if it is a job posting
  vertical_fit: 0 (unrelated) to 1 (core relevant)
  summary: a 2-3 sentence summary in plain language

Input items:
{items_text}

Output ONLY a JSON array. Do not include markdown, explanations, or any text outside the array.
[
  {{"id": 0, "is_news": true, "is_ad": false, "is_job": false, "vertical_fit": 0.8, "summary": "..."}},
  ...
]
"""


def _openai_compatible_provider(prompt: str) -> Optional[Any]:
    """Default provider: OpenAI-compatible chat completions endpoint."""
    base_url = os.environ.get("SENE_LLM_BASE_URL", "https://api.openai.com/v1")
    api_key = os.environ.get("SENE_LLM_API_KEY", "")
    model = os.environ.get("SENE_LLM_MODEL", "gpt-3.5-turbo")

    if not api_key:
        return None

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 4000,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            if not content or not content.strip():
                return None
            arr_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
            if arr_match:
                return json.loads(arr_match.group(1))
            try:
                return json.loads(content.strip())
            except json.JSONDecodeError:
                pass
            arr_match = re.search(r'\[.*\]', content, re.DOTALL)
            if arr_match:
                return json.loads(arr_match.group())
    except Exception:
        return None
    return None


def get_llm_provider() -> Optional[Callable[[str], Any]]:
    """Return the configured LLM provider callable, or None if unavailable."""
    global _LLM_PROVIDER
    if _LLM_PROVIDER is not None:
        return _LLM_PROVIDER

    provider_path = os.environ.get("SENE_LLM_PROVIDER", "")
    if provider_path:
        try:
            module_name, callable_name = provider_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            _LLM_PROVIDER = getattr(module, callable_name)
            return _LLM_PROVIDER
        except Exception:
            return None

    if os.environ.get("SENE_LLM_API_KEY", ""):
        _LLM_PROVIDER = _openai_compatible_provider
        return _LLM_PROVIDER

    return None


def set_llm_provider(provider: Callable[[str], Any]) -> None:
    """Allow tests or callers to inject a provider directly."""
    global _LLM_PROVIDER
    _LLM_PROVIDER = provider


def call_llm(prompt: str) -> Optional[Any]:
    """Call the configured LLM provider."""
    provider = get_llm_provider()
    if not provider:
        return None
    return provider(prompt)


def fetch_article(url: str, max_chars: int = CONTENT_MAX_CHARS) -> str:
    """Fetch article text and strip HTML."""
    raw = _fetch_url(url)
    if not raw:
        return ""
    text = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_chars]


def extract_published_at(raw_html: str) -> str:
    """Best-effort published-date extraction."""
    ld_match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', raw_html)
    if ld_match:
        return ld_match.group(1)[:10]
    meta_match = re.search(
        r'<meta[^>]*(?:article:published_time|pubdate|publish_date)[^>]*content="([^"]+)"',
        raw_html, re.IGNORECASE)
    if not meta_match:
        meta_match = re.search(
            r'<meta[^>]*content="([^"]+)"[^>]*(?:article:published_time|pubdate)',
            raw_html, re.IGNORECASE)
    if meta_match:
        date_str = meta_match.group(1)[:10]
        if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
            return date_str
    return ""


def verify_candidates(prescreened_items: List[Dict[str, Any]],
                      vertical: str,
                      max_items: int = 50) -> Dict[str, Any]:
    """
    Review stage: verify prescreened items with the configured LLM provider.
    If no provider is available, returns all items as verified with a marker.
    """
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    to_verify = [i for i in prescreened_items if i.get("stage") == "prescreened"]
    to_verify.sort(key=lambda x: x.get("scores", {}).get("prescreen", 0), reverse=True)

    # Cap per-source representation
    MAX_PER_SOURCE = 4
    source_count: Dict[str, int] = {}
    balanced = []
    for item in to_verify:
        sid = item.get("source_id", "unknown")
        if source_count.get(sid, 0) < MAX_PER_SOURCE:
            balanced.append(item)
            source_count[sid] = source_count.get(sid, 0) + 1
    to_verify = balanced[:max_items]

    if not to_verify:
        return {
            "vertical": vertical,
            "date": today,
            "total_prescreened": len(prescreened_items),
            "verified_count": 0,
            "passed": 0,
            "rejected": 0,
            "llm_errors": 0,
            "reject_reasons": {},
            "fit_avg": 0,
            "passed_items": [],
            "rejected_items": [],
            "provider_used": False,
        }

    provider = get_llm_provider()
    items_data = []
    for idx, item in enumerate(to_verify):
        url = item.get("url", "")
        content = fetch_article(url)
        pub_at = ""
        if content:
            pub_at = extract_published_at(_fetch_url(url))
        items_data.append({
            "idx": idx,
            "item": item,
            "content": content,
            "pub_at": pub_at,
        })

    llm_results = None
    if provider:
        items_text_parts = []
        for d in items_data:
            item = d["item"]
            items_text_parts.append(
                f"[id {d['idx']}] Source: {item.get('source_name', '')} | "
                f"Title: {item.get('title', '')}\n"
                f"Text: {d['content'][:CONTENT_MAX_CHARS]}\n"
            )
        prompt = BATCH_PROMPT.format(
            count=len(items_data),
            items_text="\n---\n".join(items_text_parts),
        )
        llm_results = call_llm(prompt)

    result_map = {}
    if llm_results and isinstance(llm_results, list):
        for r in llm_results:
            rid = r.get("id")
            if rid is not None:
                result_map[rid] = r

    passed = []
    rejected = []

    for d in items_data:
        idx = d["idx"]
        item = d["item"]
        llm_r = result_map.get(idx)

        if llm_r:
            is_news = llm_r.get("is_news", True)
            is_ad = llm_r.get("is_ad", False)
            is_job = llm_r.get("is_job", False)
            summary = llm_r.get("summary", "")
            vertical_fit = llm_r.get("vertical_fit", 0.5)

            item["scores"]["verify"] = {
                "is_news": is_news,
                "is_ad": is_ad,
                "is_job": is_job,
                "vertical_fit": vertical_fit,
                "llm_called": True,
            }
            item["summary"] = summary
            if d["pub_at"]:
                item["published_at"] = d["pub_at"]

            reject_reason = None
            if not is_news:
                reject_reason = "not_news"
            elif is_ad:
                reject_reason = "is_ad"
            elif is_job:
                reject_reason = "is_job"
            elif vertical_fit < VERTICAL_FIT_THRESHOLD:
                reject_reason = "low_fit"

            if reject_reason:
                item["stage"] = "rejected"
                item["reject_reason"] = reject_reason
                tape.append(vertical, item)
                rejected.append(item)
            else:
                item["stage"] = "verified"
                tape.append(vertical, item)
                passed.append(item)
        else:
            # No provider or missing result: rule-only pass
            item["scores"]["verify"] = {"llm_called": False}
            if d["pub_at"]:
                item["published_at"] = d["pub_at"]
            item["stage"] = "verified"
            tape.append(vertical, item)
            passed.append(item)

    fit_scores = [
        p["scores"]["verify"].get("vertical_fit", 0.5)
        for p in passed
        if "vertical_fit" in p.get("scores", {}).get("verify", {})
    ]
    reject_reasons: Dict[str, int] = {}
    for r in rejected:
        reason = r.get("reject_reason", "unknown")
        reject_reasons[reason] = reject_reasons.get(reason, 0) + 1

    return {
        "vertical": vertical,
        "date": today,
        "total_prescreened": len(prescreened_items),
        "verified_count": len(to_verify),
        "passed": len(passed),
        "rejected": len(rejected),
        "llm_errors": 0 if (not provider or result_map) else 1,
        "reject_reasons": reject_reasons,
        "fit_avg": round(sum(fit_scores) / len(fit_scores), 2) if fit_scores else 0,
        "passed_items": passed,
        "rejected_items": rejected,
        "provider_used": provider is not None,
    }


def print_verify_stats(stats: Dict[str, Any]) -> str:
    """Format verification stats as human-readable text."""
    lines = [
        f"=== Verify {stats['date']} ===",
        f"Prescreened: {stats['total_prescreened']} -> reviewed: {stats['verified_count']}",
        f"Passed: {stats['passed']} / rejected: {stats['rejected']}",
    ]
    if stats["llm_errors"]:
        lines.append(f"LLM parse errors: {stats['llm_errors']}")
    if stats["fit_avg"]:
        lines.append(f"Avg vertical_fit: {stats['fit_avg']}")
    if stats["reject_reasons"]:
        for reason, count in stats["reject_reasons"].items():
            lines.append(f"  Reject reason: {reason} x {count}")
    return "\n".join(lines)
