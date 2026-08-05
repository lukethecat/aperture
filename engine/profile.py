"""
profile.py — Versioned interest profile for a vertical.

A profile is the engine's "reading preference". Every change is versioned
and written to the tape as an evolution record.
"""
import copy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from . import tape


def get_profile(vertical: str) -> Optional[Dict[str, Any]]:
    """Return the latest profile for a vertical."""
    return tape.latest(vertical, type="profile")


def init_profile(
    vertical: str,
    keywords: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    negatives: List[Dict[str, Any]],
    reason: str = "initial profile",
    threshold: int = 2,
) -> Dict[str, Any]:
    """
    Create an initial profile (version=1). Does not overwrite an existing one.

    keywords: [{"term": "AI", "weight": 5}, ...]
    categories: [{"name": "policy", "keywords": ["regulation"], "bonus": 2}, ...]
    negatives: [{"term": "sponsored", "weight": 3}, ...]
    """
    existing = get_profile(vertical)
    if existing:
        return existing

    now = datetime.now(timezone.utc)

    def _normalize(entries: List[Dict[str, Any]], default_weight: int = 3) -> List[Dict[str, Any]]:
        out = []
        for entry in entries:
            out.append({
                "term": entry["term"],
                "weight": entry.get("weight", default_weight),
                "origin": entry.get("origin", "manual"),
                "last_hit": None,
            })
        return out

    profile = {
        "type": "profile",
        "vertical": vertical,
        "version": 1,
        "threshold": threshold,
        "keywords": _normalize(keywords),
        "negatives": _normalize(negatives),
        "categories": categories,
        "updated_at": now.isoformat(),
        "reason": reason,
    }
    tape.append(vertical, profile)
    return profile


def update_profile(
    vertical: str,
    ops: List[Dict[str, Any]],
    reason: str = "",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Apply profile operations and bump the version.

    Supported ops:
      add_keyword, adjust_weight, remove_keyword,
      add_negative, adjust_negative_weight, remove_negative.

    Returns (old_profile, new_profile).
    """
    old_profile = get_profile(vertical)
    if not old_profile:
        raise ValueError(f"No profile for vertical '{vertical}'; call init_profile first")

    new_profile = copy.deepcopy(old_profile)
    now = datetime.now(timezone.utc)
    new_profile["version"] = old_profile["version"] + 1
    new_profile["updated_at"] = now.isoformat()
    new_profile["reason"] = reason

    keywords = {kw["term"]: kw for kw in new_profile["keywords"]}
    negatives = {n["term"]: n for n in new_profile["negatives"]}
    applied_ops: List[Dict[str, Any]] = []

    for op in ops:
        op_type = op.get("op")
        term = op.get("term", "")

        if op_type == "add_keyword":
            if term in keywords:
                keywords[term]["weight"] = op.get("weight", keywords[term]["weight"])
            else:
                keywords[term] = {
                    "term": term,
                    "weight": op.get("weight", 3),
                    "origin": "learned",
                    "last_hit": None,
                }
            applied_ops.append(op)

        elif op_type == "adjust_weight":
            if term in keywords:
                keywords[term]["weight"] = max(0, keywords[term]["weight"] + op.get("delta", 0))
                applied_ops.append(op)

        elif op_type == "remove_keyword":
            if term in keywords:
                del keywords[term]
                applied_ops.append(op)

        elif op_type == "add_negative":
            if term in negatives:
                negatives[term]["weight"] = op.get("weight", negatives[term]["weight"])
            else:
                negatives[term] = {
                    "term": term,
                    "weight": op.get("weight", 3),
                    "origin": "learned",
                    "last_hit": None,
                }
            applied_ops.append(op)

        elif op_type == "adjust_negative_weight":
            if term in negatives:
                negatives[term]["weight"] = max(0, negatives[term]["weight"] + op.get("delta", 0))
                applied_ops.append(op)

        elif op_type == "remove_negative":
            if term in negatives:
                del negatives[term]
                applied_ops.append(op)

    new_profile["keywords"] = list(keywords.values())
    new_profile["negatives"] = list(negatives.values())

    tape.append(vertical, new_profile)
    tape.append(
        vertical,
        {
            "type": "evolution",
            "vertical": vertical,
            "from_version": old_profile["version"],
            "to_version": new_profile["version"],
            "ops": applied_ops,
            "reason": reason,
            "date": now.isoformat(),
        },
    )
    return old_profile, new_profile


def record_hit(vertical: str, term: str) -> None:
    """Update last_hit for a keyword or negative term (does not bump version)."""
    profile = get_profile(vertical)
    if not profile:
        return
    now = datetime.now(timezone.utc)
    changed = False
    for kw in profile["keywords"]:
        if kw["term"] == term:
            kw["last_hit"] = now.isoformat()
            changed = True
            break
    if not changed:
        for neg in profile["negatives"]:
            if neg["term"] == term:
                neg["last_hit"] = now.isoformat()
                changed = True
                break
    if changed:
        tape.append(vertical, profile)


def get_keyword_map(vertical: str) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Return (positive term -> weight, negative term -> weight) dictionaries."""
    profile = get_profile(vertical)
    if not profile:
        return {}, {}
    pos = {kw["term"]: kw["weight"] for kw in profile.get("keywords", [])}
    neg = {n["term"]: n["weight"] for n in profile.get("negatives", [])}
    return pos, neg


def get_categories(vertical: str) -> List[Dict[str, Any]]:
    """Return category definitions for a vertical."""
    profile = get_profile(vertical)
    if not profile:
        return []
    return profile.get("categories", [])


def decay_profile(vertical: str, decay_days: int = 30) -> Dict[str, Any]:
    """
    Decay learned keywords that have not hit recently.
    Manual keywords are never auto-deleted, only warned.
    """
    profile = get_profile(vertical)
    if not profile:
        return {"status": "no_profile"}

    now = datetime.now(timezone.utc)
    cutoff_str = (now - timedelta(days=decay_days)).isoformat()

    ops = []
    pending_delete = []
    warnings = []

    new_keywords = []
    for kw in profile.get("keywords", []):
        last_hit = kw.get("last_hit")
        origin = kw.get("origin", "manual")
        if origin == "learned" and ((last_hit and last_hit < cutoff_str) or not last_hit):
            kw["weight"] = max(0, kw["weight"] - 1)
            ops.append({"op": "decay", "term": kw["term"], "new_weight": kw["weight"]})
            if kw["weight"] == 0:
                pending_delete.append(kw["term"])
                continue
        elif origin == "manual" and last_hit and last_hit < cutoff_str:
            warnings.append(f"Manual keyword '{kw['term']}' has not hit for {decay_days} days")
        new_keywords.append(kw)

    new_negatives = []
    for neg in profile.get("negatives", []):
        last_hit = neg.get("last_hit")
        origin = neg.get("origin", "manual")
        if origin == "learned" and ((last_hit and last_hit < cutoff_str) or not last_hit):
            neg["weight"] = max(0, neg["weight"] - 1)
            ops.append({"op": "decay_negative", "term": neg["term"], "new_weight": neg["weight"]})
            if neg["weight"] == 0:
                pending_delete.append(f"-{neg['term']}")
                continue
        new_negatives.append(neg)

    if ops:
        old_profile = profile
        new_profile = copy.deepcopy(profile)
        new_profile["version"] = profile["version"] + 1
        new_profile["updated_at"] = now.isoformat()
        new_profile["reason"] = f"decay({decay_days}d no hit)"
        new_profile["keywords"] = new_keywords
        new_profile["negatives"] = new_negatives
        tape.append(vertical, new_profile)
        tape.append(
            vertical,
            {
                "type": "evolution",
                "vertical": vertical,
                "from_version": old_profile["version"],
                "to_version": new_profile["version"],
                "ops": ops,
                "reason": new_profile["reason"],
                "date": now.isoformat(),
            },
        )
        return {
            "status": "done",
            "decayed": len(ops),
            "pending_delete": pending_delete,
            "warnings": warnings,
            "from_version": old_profile["version"],
            "to_version": new_profile["version"],
        }

    return {
        "status": "done",
        "decayed": 0,
        "pending_delete": [],
        "warnings": warnings,
        "from_version": profile["version"],
        "to_version": profile["version"],
    }
