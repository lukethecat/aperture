"""echo.py — Proactive clarification module (the "ECHO" layer).

ECHO is split into four stages with tape as the boundary between each:

  1. prepare:  after publish, generate pending clarification questions from
              today's pooled items and write them to the tape.
  2. deliver:  the cron/delivery layer reads pending questions and posts them
              alongside the report, then marks them delivered.
  3. ingest:   when the user replies, record the raw answer on the tape first.
  4. distill:  before the next run, apply answers to the profile and expire
              any unanswered questions from the previous day.

All state is append-only. The module is intentionally decoupled from any
channel-specific delivery mechanism.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import tape
from .profile import get_profile, update_profile

MAX_QUESTIONS_PER_DAY = 2
CONSECUTIVE_IGNORE_THRESHOLD = 3
COOLDOWN_DAYS_AFTER_IGNORE = 3


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _yesterday(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (dt - timedelta(days=1)).strftime("%Y-%m-%d")


def _load_echo_state(vertical: str) -> Dict[str, Any]:
    """Load persistent ECHO state from the tape."""
    record = tape.latest(vertical, type="echo_state")
    if record:
        return record
    return {
        "type": "echo_state",
        "vertical": vertical,
        "consecutive_ignored": 0,
        "silenced": False,
        "last_prepare_date": None,
        "daily_count": 0,
    }


def _save_echo_state(vertical: str, state: Dict[str, Any]) -> None:
    state["ts"] = datetime.now(timezone.utc).isoformat()
    tape.append(vertical, state)


def _recent_pooled_items(vertical: str, days: int = 1) -> List[Dict[str, Any]]:
    """Load items pooled in the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.isoformat()
    return [
        item for item in tape.query(vertical, type="item")
        if item.get("stage") == "pooled" and item.get("ts", "") >= cutoff_str
    ]


def _extract_candidate_topics(items: List[Dict[str, Any]]) -> Dict[str, int]:
    """Extract frequent capitalized noun phrases that are not already keywords."""
    counts: Dict[str, int] = {}
    for item in items:
        title = item.get("title", "")
        for word in re.findall(r'[A-Z][a-zA-Z]{2,}', title):
            counts[word] = counts.get(word, 0) + 1
    return counts


def _profile_terms(vertical: str) -> set:
    """Return all terms currently in the profile."""
    profile = get_profile(vertical)
    if not profile:
        return set()
    terms = {kw["term"].lower() for kw in profile.get("keywords", [])}
    terms.update({n["term"].lower() for n in profile.get("negatives", [])})
    return terms


def _questions_for_date(vertical: str, date: str) -> List[Dict[str, Any]]:
    return [
        q for q in tape.query(vertical, type="echo_question")
        if q.get("date") == date
    ]


def _pending_questions(vertical: str, date: str) -> List[Dict[str, Any]]:
    return [
        q for q in _questions_for_date(vertical, date)
        if q.get("status") == "pending"
    ]


def _expirable_questions(vertical: str, date: str) -> List[Dict[str, Any]]:
    """Questions from date that are pending or delivered but not answered."""
    return [
        q for q in _questions_for_date(vertical, date)
        if q.get("status") in ("pending", "delivered")
    ]


def _mark_questions(vertical: str, questions: List[Dict[str, Any]], status: str) -> None:
    for q in questions:
        q["status"] = status
        q["ts"] = datetime.now(timezone.utc).isoformat()
        tape.append(vertical, q)


def _should_prepare(state: Dict[str, Any]) -> bool:
    if state.get("silenced"):
        return False

    today = _today()
    last_date = state.get("last_prepare_date")
    daily_count = state.get("daily_count", 0)

    if last_date != today:
        daily_count = 0

    if daily_count >= MAX_QUESTIONS_PER_DAY:
        return False

    consecutive = state.get("consecutive_ignored", 0)
    if consecutive >= CONSECUTIVE_IGNORE_THRESHOLD:
        if last_date and (datetime.fromisoformat(last_date).date() +
                          timedelta(days=COOLDOWN_DAYS_AFTER_IGNORE) >
                          datetime.now(timezone.utc).date()):
            return False

    return True


def prepare(vertical: str,
            items: Optional[List[Dict[str, Any]]] = None,
            max_questions: int = MAX_QUESTIONS_PER_DAY) -> List[Dict[str, Any]]:
    """
    Generate today's pending clarification questions and write them to the tape.

    Idempotent: if questions have already been prepared for today, returns the
    existing pending questions without generating new ones.

    Before generating, expires any unanswered questions from the previous day
    and updates the ignored counter.
    """
    state = _load_echo_state(vertical)

    today = _today()
    if state.get("last_prepare_date") != today:
        state["daily_count"] = 0

    # Expire yesterday's unanswered questions before deciding whether to ask.
    yesterday = _yesterday(today)
    expired = _expirable_questions(vertical, yesterday)
    if expired:
        _mark_questions(vertical, expired, "expired")
        state["consecutive_ignored"] = state.get("consecutive_ignored", 0) + len(expired)

    # Return existing pending questions if already prepared today.
    existing_pending = _pending_questions(vertical, today)
    if existing_pending:
        state["last_prepare_date"] = today
        _save_echo_state(vertical, state)
        return existing_pending

    if not _should_prepare(state):
        _save_echo_state(vertical, state)
        return []

    items = items or _recent_pooled_items(vertical, days=1)
    if not items:
        _save_echo_state(vertical, state)
        return []

    existing_terms = _profile_terms(vertical)
    topic_counts = _extract_candidate_topics(items)
    candidate_topics = [
        (topic, count) for topic, count in topic_counts.items()
        if topic.lower() not in existing_terms and count >= 2
    ]
    candidate_topics.sort(key=lambda x: -x[1])

    questions: List[Dict[str, Any]] = []
    remaining = max_questions - state.get("daily_count", 0)
    for topic, count in candidate_topics[:remaining]:
        evidence_items = [
            item for item in items
            if topic.lower() in item.get("title", "").lower()
        ][:2]
        evidence_urls = [item.get("url", "") for item in evidence_items if item.get("url")]

        question = {
            "id": f"echo-{today}-{topic.lower()}-{datetime.now(timezone.utc).isoformat()}",
            "type": "echo_question",
            "vertical": vertical,
            "date": today,
            "topic": topic,
            "question": f"Add '{topic}' to the profile?",
            "evidence": {"count": count, "urls": evidence_urls},
            "answerable_in_one_word": True,
            "status": "pending",
        }
        tape.append(vertical, question)
        questions.append(question)

    if questions:
        state["last_prepare_date"] = today
        state["daily_count"] = state.get("daily_count", 0) + len(questions)
        # We do not increment consecutive_ignored here; that happens on expiry.

    _save_echo_state(vertical, state)
    return questions


def mark_delivered(vertical: str, question_ids: List[str]) -> None:
    """Mark pending questions as delivered."""
    today = _today()
    for q in _questions_for_date(vertical, today):
        if q.get("id") in question_ids and q.get("status") == "pending":
            q["status"] = "delivered"
            q["ts"] = datetime.now(timezone.utc).isoformat()
            tape.append(vertical, q)


def record_delivery(vertical: str, question_ids: List[str],
                    channel: str, message_id: str) -> None:
    """Record that a set of pending questions was delivered to a channel."""
    mark_delivered(vertical, question_ids)
    tape.append(
        vertical,
        {
            "type": "echo_delivery",
            "vertical": vertical,
            "date": _today(),
            "question_ids": question_ids,
            "channel": channel,
            "message_id": message_id,
        },
    )


def record_raw_answer(vertical: str, question_id: str, answer_text: str) -> None:
    """Record a raw user answer before distillation."""
    tape.append(
        vertical,
        {
            "type": "echo_raw_answer",
            "vertical": vertical,
            "date": _today(),
            "question_id": question_id,
            "answer_text": answer_text,
        },
    )


def _find_question(vertical: str, question_id: str) -> Optional[Dict[str, Any]]:
    """Return the latest echo_question record with the given id."""
    latest = None
    for q in tape.query(vertical, type="echo_question"):
        if q.get("id") == question_id:
            latest = q
    return latest


def apply_answer(question_id: str, vertical: str, answer: str) -> Dict[str, Any]:
    """
    Apply a one-word/phrase answer to an ECHO question.

    Positive answers add the topic as a keyword; negative answers add it as a
    negative keyword. 'silence' permanently disables ECHO for this vertical.
    """
    positive = {"yes", "y", "sure", "add", "more", "ok"}
    negative = {"no", "n", "skip", "less", "never"}
    silence = {"silence", "mute", "stop", "off"}

    answer_lower = answer.strip().lower()

    question = _find_question(vertical, question_id)
    if not question:
        return {"status": "error", "message": "Question not found"}

    if answer_lower in silence:
        state = _load_echo_state(vertical)
        state["silenced"] = True
        _save_echo_state(vertical, state)
        return {"status": "silenced", "message": "ECHO silenced. Send 'echo on' to re-enable."}

    topic = question.get("topic", "")
    ops: List[Dict[str, Any]] = []
    if answer_lower in positive:
        ops.append({"op": "add_keyword", "term": topic, "weight": 3})
    elif answer_lower in negative:
        ops.append({"op": "add_negative", "term": topic, "weight": 3})
    else:
        return {"status": "unrecognized", "message": "Please answer yes/no/skip/silence"}

    old_profile, new_profile = update_profile(vertical, ops, reason=f"ECHO answer: {answer}")

    # Reset ignored counter on engagement and mark question answered.
    state = _load_echo_state(vertical)
    state["consecutive_ignored"] = 0
    _save_echo_state(vertical, state)

    question["status"] = "answered"
    question["ts"] = datetime.now(timezone.utc).isoformat()
    tape.append(vertical, question)

    tape.append(
        vertical,
        {
            "type": "echo_answer",
            "vertical": vertical,
            "question_id": question_id,
            "answer": answer,
            "applied_ops": ops,
            "profile_version": new_profile["version"],
        },
    )

    return {
        "status": "applied",
        "message": f"Profile updated v{old_profile['version']} -> v{new_profile['version']}",
        "ops": ops,
    }


def distill(vertical: str) -> Dict[str, Any]:
    """
    Process raw answers and expire any remaining unanswered delivered questions.

    This should be called at the start of the next run, before prepare().
    """
    today = _today()
    yesterday = _yesterday(today)

    results = {"applied": 0, "expired": 0, "errors": []}

    # Apply raw answers from yesterday.
    raw_answers = [
        a for a in tape.query(vertical, type="echo_raw_answer")
        if a.get("date") == yesterday
    ]
    for raw in raw_answers:
        qid = raw.get("question_id", "")
        answer = raw.get("answer_text", "")
        res = apply_answer(qid, vertical, answer)
        if res.get("status") in ("applied", "silenced"):
            results["applied"] += 1
        else:
            results["errors"].append({"question_id": qid, "status": res.get("status")})

    # Expire delivered questions from yesterday that still have no answer.
    remaining = [
        q for q in _questions_for_date(vertical, yesterday)
        if q.get("status") == "delivered"
    ]
    if remaining:
        _mark_questions(vertical, remaining, "expired")
        state = _load_echo_state(vertical)
        state["consecutive_ignored"] = state.get("consecutive_ignored", 0) + len(remaining)
        _save_echo_state(vertical, state)
        results["expired"] += len(remaining)

    return results


def enable(vertical: str) -> Dict[str, Any]:
    """Re-enable ECHO after it was silenced."""
    state = _load_echo_state(vertical)
    state["silenced"] = False
    state["consecutive_ignored"] = 0
    _save_echo_state(vertical, state)
    return {"status": "enabled"}


# Backward-compatible aliases for callers that expect the old API.
def ask(vertical: str,
        items: Optional[List[Dict[str, Any]]] = None,
        max_questions: int = MAX_QUESTIONS_PER_DAY) -> List[Dict[str, Any]]:
    """Generate today's pending questions (prepare stage)."""
    return prepare(vertical, items=items, max_questions=max_questions)


def generate_questions(vertical: str,
                       items: Optional[List[Dict[str, Any]]] = None,
                       max_questions: int = MAX_QUESTIONS_PER_DAY) -> List[Dict[str, Any]]:
    """Backward-compatible alias for prepare()."""
    return prepare(vertical, items=items, max_questions=max_questions)
