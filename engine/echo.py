"""
echo.py — Proactive clarification module (the "ECHO" layer).

After publishing a report, ECHO asks the user up to two one-word-answer
questions that help refine the profile. Each question must carry tape evidence,
be answerable in a single word or phrase, and back off if the user is not
engaging.

Rate limits:
- Maximum 2 questions per day.
- After 3 consecutive unanswered questions, reduce frequency.
- User can permanently silence ECHO.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from . import tape

MAX_QUESTIONS_PER_DAY = 2
CONSECUTIVE_IGNORE_THRESHOLD = 3
COOLDOWN_DAYS_AFTER_IGNORE = 3


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


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
        "last_asked_date": None,
        "daily_count": 0,
    }


def _save_echo_state(vertical: str, state: Dict[str, Any]) -> None:
    state["ts"] = datetime.now(timezone.utc).isoformat()
    tape.append(vertical, state)


def _recent_pooled_items(vertical: str, days: int = 1) -> List[Dict[str, Any]]:
    """Load items pooled in the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.isoformat()
    items = []
    for item in tape.query(vertical, type="item"):
        if item.get("stage") == "pooled" and item.get("ts", "") >= cutoff_str:
            items.append(item)
    return items


def _extract_candidate_topics(items: List[Dict[str, Any]]) -> Dict[str, int]:
    """Extract frequent capitalized noun phrases that are not already keywords."""
    counts: Dict[str, int] = {}
    for item in items:
        title = item.get("title", "")
        # Simple heuristic: capitalized words of length >= 3
        for word in re.findall(r'[A-Z][a-zA-Z]{2,}', title):
            counts[word] = counts.get(word, 0) + 1
    return counts


def _profile_terms(vertical: str) -> set:
    """Return all terms currently in the profile."""
    from .profile import get_profile
    profile = get_profile(vertical)
    if not profile:
        return set()
    terms = {kw["term"].lower() for kw in profile.get("keywords", [])}
    terms.update({n["term"].lower() for n in profile.get("negatives", [])})
    return terms


def should_ask(vertical: str) -> bool:
    """Check rate limits and silence state before asking."""
    state = _load_echo_state(vertical)
    if state.get("silenced"):
        return False

    today = _today()
    last_date = state.get("last_asked_date")
    daily_count = state.get("daily_count", 0)
    consecutive = state.get("consecutive_ignored", 0)

    # Reset daily count on a new day
    if last_date != today:
        daily_count = 0

    if daily_count >= MAX_QUESTIONS_PER_DAY:
        return False

    # Cooldown after too many ignored questions
    if consecutive >= CONSECUTIVE_IGNORE_THRESHOLD:
        if last_date and (datetime.fromisoformat(last_date).date() +
                          timedelta(days=COOLDOWN_DAYS_AFTER_IGNORE) >
                          datetime.now(timezone.utc).date()):
            return False

    return True


def generate_questions(vertical: str,
                       items: Optional[List[Dict[str, Any]]] = None,
                       max_questions: int = MAX_QUESTIONS_PER_DAY) -> List[Dict[str, Any]]:
    """
    Generate up to `max_questions` one-word-answer clarification questions.
    Returns a list of question dicts with evidence.
    """
    if not should_ask(vertical):
        return []

    items = items or _recent_pooled_items(vertical, days=1)
    if not items:
        return []

    existing_terms = _profile_terms(vertical)
    topic_counts = _extract_candidate_topics(items)

    # Filter out topics already in profile and low-frequency topics
    candidate_topics = [
        (topic, count) for topic, count in topic_counts.items()
        if topic.lower() not in existing_terms and count >= 2
    ]
    candidate_topics.sort(key=lambda x: -x[1])

    questions = []
    for topic, count in candidate_topics[:max_questions]:
        evidence_items = [
            item for item in items
            if topic.lower() in item.get("title", "").lower()
        ][:2]
        evidence_urls = [item.get("url", "") for item in evidence_items if item.get("url")]

        questions.append({
            "id": f"echo-{datetime.now(timezone.utc).isoformat()}-{topic.lower()}",
            "type": "echo_question",
            "vertical": vertical,
            "date": _today(),
            "topic": topic,
            "question": f"Add '{topic}' to the profile?",
            "evidence": {
                "count": count,
                "urls": evidence_urls,
            },
            "answerable_in_one_word": True,
        })

    return questions


def ask(vertical: str,
        items: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Generate and record ECHO questions. Returns the questions to present to the user.
    """
    state = _load_echo_state(vertical)
    today = _today()
    if state.get("last_asked_date") != today:
        state["daily_count"] = 0

    questions = generate_questions(vertical, items=items,
                                   max_questions=MAX_QUESTIONS_PER_DAY - state.get("daily_count", 0))
    if questions:
        for q in questions:
            tape.append(vertical, q)
        state["last_asked_date"] = today
        state["daily_count"] = state.get("daily_count", 0) + len(questions)
        state["consecutive_ignored"] = state.get("consecutive_ignored", 0) + len(questions)
        _save_echo_state(vertical, state)

    return questions


def apply_answer(question_id: str, vertical: str, answer: str) -> Dict[str, Any]:
    """
    Apply a one-word/phrase answer to an ECHO question.

    Positive answers (yes/y/sure/add/more) add the topic as a keyword.
    Negative answers (no/n/skip/less) add it as a negative keyword.
    """
    positive = {"yes", "y", "sure", "add", "more", "ok"}
    negative = {"no", "n", "skip", "less", "never"}
    silence = {"silence", "mute", "stop", "off"}

    answer_lower = answer.strip().lower()

    # Find the question on the tape
    question = None
    for rec in tape.query(vertical, type="echo_question"):
        if rec.get("id") == question_id:
            question = rec
            break

    if not question:
        return {"status": "error", "message": "Question not found"}

    if answer_lower in silence:
        state = _load_echo_state(vertical)
        state["silenced"] = True
        _save_echo_state(vertical, state)
        return {"status": "silenced", "message": "ECHO silenced. Send 'echo on' to re-enable."}

    from .profile import update_profile
    topic = question.get("topic", "")
    ops: List[Dict[str, Any]] = []
    if answer_lower in positive:
        ops.append({"op": "add_keyword", "term": topic, "weight": 3})
    elif answer_lower in negative:
        ops.append({"op": "add_negative", "term": topic, "weight": 3})
    else:
        return {"status": "unrecognized", "message": "Please answer yes/no/skip/silence"}

    old_profile, new_profile = update_profile(vertical, ops, reason=f"ECHO answer: {answer}")

    # Reset ignored counter on engagement
    state = _load_echo_state(vertical)
    state["consecutive_ignored"] = 0
    _save_echo_state(vertical, state)

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


def enable(vertical: str) -> Dict[str, Any]:
    """Re-enable ECHO after it was silenced."""
    state = _load_echo_state(vertical)
    state["silenced"] = False
    state["consecutive_ignored"] = 0
    _save_echo_state(vertical, state)
    return {"status": "enabled"}
