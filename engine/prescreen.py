"""
prescreen.py — Rule-based first-pass scoring (the "edit" stage).

score = sum(matched keyword weights)
      + category match bonuses
      - sum(matched negative weights)

Items scoring below the threshold are rejected with reject_reason=low_score
but still written to the tape. Those rejected records are the engine's
self-evolution fuel.
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from . import tape
from .profile import get_categories, get_keyword_map, get_profile, record_hit

DEFAULT_THRESHOLD = 2


def _term_matches(text_lower: str, term: str) -> bool:
    """
    Match a keyword term against lowercased text.
    - ASCII-only terms require word boundaries to avoid 'ai' matching 'daily'.
    - CJK or mixed terms use substring matching.
    """
    term_lower = term.lower()
    if term_lower in text_lower:
        # If term contains only ASCII letters/digits, enforce word boundary.
        if re.match(r'^[a-z0-9]+$', term_lower):
            pattern = r'(?:^|[^a-z0-9])' + re.escape(term_lower) + r'(?:$|[^a-z0-9])'
            return bool(re.search(pattern, text_lower))
        return True
    return False


def prescreen_item(title: str, _url_norm: str, vertical: str) -> Dict[str, Any]:
    """
    Score a single candidate. Returns a dict with score, matches,
    pass/borderline/reject flag, and reject_reason.
    """
    profile = get_profile(vertical) or {}
    threshold = profile.get("threshold", DEFAULT_THRESHOLD)
    editorial_scores = set(profile.get("editorial_review_scores", []))
    pos_kw, neg_kw = get_keyword_map(vertical)
    categories = get_categories(vertical)

    text_lower = title.lower()
    score = 0
    matched_keywords = []
    matched_categories = []
    matched_negatives = []

    for term, weight in pos_kw.items():
        if _term_matches(text_lower, term):
            score += weight
            matched_keywords.append({"term": term, "weight": weight})
            record_hit(vertical, term)

    for cat in categories:
        cat_keywords = cat.get("keywords", [])
        cat_bonus = cat.get("bonus", 0)
        for ck in cat_keywords:
            if _term_matches(text_lower, ck):
                score += cat_bonus
                matched_categories.append({"category": cat["name"], "bonus": cat_bonus})
                break  # one bonus per category

    for term, weight in neg_kw.items():
        if _term_matches(text_lower, term):
            score -= weight
            matched_negatives.append({"term": term, "weight": weight})
            record_hit(vertical, term)

    if score in editorial_scores:
        # Editorial-review scores are a "maybe" zone: hold for human review
        # even if they clear the threshold.
        status = "borderline"
        reject_reason = None
    elif score >= threshold:
        status = "pass"
        reject_reason = None
    else:
        status = "reject"
        reject_reason = "low_score"

    return {
        "score": score,
        "matched_keywords": matched_keywords,
        "matched_categories": matched_categories,
        "matched_negatives": matched_negatives,
        "status": status,
        "reject_reason": reject_reason,
    }


def prescreen_candidates(candidates: List[Dict[str, Any]],
                         vertical: str) -> Dict[str, Any]:
    """
    Batch prescreen. Passed items become stage=prescreened; borderline items
    become stage=borderline for editorial review; failed items become
    stage=rejected with reject_reason.
    """
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    passed = []
    borderline = []
    rejected = []

    for c in candidates:
        title = c.get("title", "")
        url_norm = c.get("url_norm", "")
        result = prescreen_item(title, url_norm, vertical)

        item_record = {
            "type": "item",
            "vertical": vertical,
            "source_id": c.get("source_id", ""),
            "source_name": c.get("source_name", ""),
            "title": title,
            "url": c.get("url", ""),
            "url_norm": url_norm,
            "scores": {
                "prescreen": result["score"],
                "matched_keywords": result["matched_keywords"],
                "matched_categories": result["matched_categories"],
                "matched_negatives": result["matched_negatives"],
            },
            "published_at": c.get("pub_date", ""),
        }

        if result["status"] == "pass":
            item_record["stage"] = "prescreened"
            tape.append(vertical, item_record)
            passed.append(item_record)
        elif result["status"] == "borderline":
            item_record["stage"] = "borderline"
            tape.append(vertical, item_record)
            borderline.append(item_record)
        else:
            item_record["stage"] = "rejected"
            item_record["reject_reason"] = result["reject_reason"]
            tape.append(vertical, item_record)
            rejected.append(item_record)

    scores = [p["scores"]["prescreen"] for p in passed]
    reject_reasons: Dict[str, int] = {}
    for r in rejected:
        reason = r.get("reject_reason", "unknown")
        reject_reasons[reason] = reject_reasons.get(reason, 0) + 1

    kw_hits: Dict[str, int] = {}
    for p in passed:
        for mk in p["scores"]["matched_keywords"]:
            kw_hits[mk["term"]] = kw_hits.get(mk["term"], 0) + 1

    return {
        "vertical": vertical,
        "date": today,
        "total_candidates": len(candidates),
        "passed": len(passed),
        "borderline": len(borderline),
        "rejected": len(rejected),
        "reject_reasons": reject_reasons,
        "score_min": min(scores) if scores else 0,
        "score_max": max(scores) if scores else 0,
        "score_avg": round(sum(scores) / len(scores), 1) if scores else 0,
        "top_keywords": sorted(kw_hits.items(), key=lambda x: -x[1])[:10],
        "passed_items": passed,
        "borderline_items": borderline,
        "rejected_items": rejected,
    }


def print_prescreen_stats(stats: Dict[str, Any]) -> str:
    """Format prescreen stats as human-readable text."""
    borderline = stats.get("borderline", 0)
    lines = [
        f"=== Prescreen {stats['date']} ===",
        f"Candidates: {stats['total_candidates']} -> passed: {stats['passed']} / borderline: {borderline} / rejected: {stats['rejected']}",
    ]
    if stats["passed"] > 0:
        lines.append(f"Score range: {stats['score_min']}~{stats['score_max']} (avg {stats['score_avg']})")
    if stats["reject_reasons"]:
        for reason, count in stats["reject_reasons"].items():
            lines.append(f"  Reject reason: {reason} x {count}")
    if stats["top_keywords"]:
        lines.append("Top keywords:")
        for term, count in stats["top_keywords"]:
            lines.append(f"  {term}: {count}")
    return "\n".join(lines)
