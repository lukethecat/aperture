"""
feedback.py — Reflection loop (the engine's self-evolution mechanism).

User feedback is parsed into profile operations, applied with version bump,
logged to the tape, and confirmed back. Rejected items are rechecked to
validate that the new profile would have filtered them.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from . import tape
from .profile import get_keyword_map, get_profile, update_profile
from .verifier import call_llm

FEEDBACK_PROMPT = """You are a profile maintenance assistant. Given user feedback on a news digest, parse it into profile operations.

Feedback: "{feedback_text}"

Current keywords (for reference):
{current_keywords}

Output ONLY a JSON array of operations. Supported ops:
  {{"op": "add_keyword", "term": "...", "weight": 3}}
  {{"op": "adjust_weight", "term": "...", "delta": -2}}
  {{"op": "remove_keyword", "term": "..."}}
  {{"op": "add_negative", "term": "...", "weight": 3}}
  {{"op": "adjust_negative_weight", "term": "...", "delta": 2}}
  {{"op": "remove_negative", "term": "..."}}

Rules:
- "more of", "good", "like" -> add_keyword weight=3
- "less of", "don't want", "dislike" -> adjust_weight delta=-2 OR add_negative
- "watch", "keep an eye on" -> add_keyword weight=2
- One operation per topic; do not merge
- Output nothing but a JSON array
"""


def _parse_ops_array(content: str) -> List[Dict[str, Any]]:
    """Try to extract a JSON array of ops from LLM output."""
    if not content:
        return []
    arr_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
    if arr_match:
        try:
            return json.loads(arr_match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        pass
    arr_match = re.search(r'\[.*\]', content, re.DOTALL)
    if arr_match:
        try:
            return json.loads(arr_match.group())
        except json.JSONDecodeError:
            pass
    return []


def parse_feedback(feedback_text: str, vertical: str) -> Tuple[List[Dict[str, Any]], str]:
    """Parse user feedback into profile operations."""
    profile = get_profile(vertical)
    current_kws = []
    if profile:
        for kw in profile.get("keywords", []):
            current_kws.append(f"{kw['term']}({kw['weight']})")
        for neg in profile.get("negatives", []):
            current_kws.append(f"-{neg['term']}({neg['weight']})")

    prompt = FEEDBACK_PROMPT.format(
        feedback_text=feedback_text,
        current_keywords=", ".join(current_kws[:50]),
    )

    result = call_llm(prompt)
    if isinstance(result, str):
        ops = _parse_ops_array(result)
    elif isinstance(result, list):
        ops = result
    else:
        ops = []
    return ops, f"parse feedback: {feedback_text[:80]}"


def _recheck_rejected(vertical: str, ops: List[Dict[str, Any]]) -> str:
    """Recheck recently rejected items against new negatives/lowered weights."""
    new_neg_terms = [op["term"] for op in ops if op.get("op") == "add_negative"]
    lowered_terms = [
        op["term"] for op in ops
        if op.get("op") == "adjust_weight" and op.get("delta", 0) < 0
    ]

    if not new_neg_terms and not lowered_terms:
        return ""

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    cutoff_str = cutoff.isoformat()
    matched = []

    for item in tape.query(vertical, type="item"):
        if item.get("stage") != "pooled":
            continue
        if item.get("ts", "") < cutoff_str:
            continue
        title = item.get("title", "").lower()
        for term in new_neg_terms + lowered_terms:
            if term.lower() in title:
                matched.append((item, term))
                break

    if matched:
        return (
            f"Recheck: {len(matched)} recently pooled items would be filtered "
            "under the new profile."
        )
    return ""


def apply_feedback(feedback_text: str, vertical: str) -> Dict[str, Any]:
    """Run the full reflection loop for a feedback message."""
    now = datetime.now(timezone.utc)

    ops, _reason = parse_feedback(feedback_text, vertical)
    if not ops:
        return {
            "status": "no_ops",
            "message": "No valid profile operations parsed from feedback.",
            "raw_feedback": feedback_text,
        }

    old_profile, new_profile = update_profile(vertical, ops, reason=feedback_text[:200])

    tape.append(
        vertical,
        {
            "type": "feedback",
            "date": now.strftime("%Y-%m-%d"),
            "vertical": vertical,
            "text": feedback_text,
            "applied_ops": ops,
            "status": "applied",
        },
    )

    recheck_msg = _recheck_rejected(vertical, ops)

    changes = []
    for op in ops:
        op_type = op.get("op", "")
        term = op.get("term", "")
        if op_type == "add_keyword":
            changes.append(f"+ keyword '{term}' (weight {op.get('weight', 3)})")
        elif op_type == "adjust_weight":
            delta = op.get("delta", 0)
            direction = "up" if delta > 0 else "down"
            changes.append(f"~ keyword '{term}' weight {direction} {abs(delta)}")
        elif op_type == "remove_keyword":
            changes.append(f"- keyword '{term}'")
        elif op_type == "add_negative":
            changes.append(f"+ negative '{term}' (weight {op.get('weight', 3)})")
        elif op_type == "adjust_negative_weight":
            delta = op.get("delta", 0)
            direction = "up" if delta > 0 else "down"
            changes.append(f"~ negative '{term}' weight {direction} {abs(delta)}")
        elif op_type == "remove_negative":
            changes.append(f"- negative '{term}'")

    summary_lines = [
        f"Profile updated v{old_profile['version']} -> v{new_profile['version']}",
        "",
        "Changes:",
    ] + changes

    if recheck_msg:
        summary_lines.append("")
        summary_lines.append(recheck_msg)

    summary_lines.append("")
    summary_lines.append(
        f"Current profile: {len(new_profile.get('keywords', []))} positive / "
        f"{len(new_profile.get('negatives', []))} negative"
    )

    return {
        "status": "applied",
        "from_version": old_profile["version"],
        "to_version": new_profile["version"],
        "ops": ops,
        "message": "\n".join(summary_lines),
    }


def get_feedback_history(vertical: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Return recent feedback records."""
    return tape.query(vertical, type="feedback", limit=limit)
