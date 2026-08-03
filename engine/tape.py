"""
tape.py — Append-only JSONL audit log.

Every state change lands in the tape. Three months later you can still answer:
"Why was this item selected?" and "When was this keyword added, and why?"
"""
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

_TAPE_LOCK = threading.Lock()


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tape_dir() -> str:
    path = os.path.join(_project_root(), "tape")
    os.makedirs(path, exist_ok=True)
    return path


def _tape_path(vertical: str) -> str:
    return os.path.join(_tape_dir(), f"{vertical}.jsonl")


def append(vertical: str, record: Dict[str, Any]) -> None:
    """Append a single record to the vertical's tape."""
    record.setdefault("ts", datetime.now(timezone.utc).isoformat())
    path = _tape_path(vertical)
    with _TAPE_LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())


def append_many(vertical: str, records: List[Dict[str, Any]]) -> None:
    """Append multiple records in one lock acquisition."""
    if not records:
        return
    path = _tape_path(vertical)
    with _TAPE_LOCK:
        with open(path, "a", encoding="utf-8") as f:
            for record in records:
                record.setdefault("ts", datetime.now(timezone.utc).isoformat())
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())


def read_all(vertical: str) -> List[Dict[str, Any]]:
    """Read all records for a vertical."""
    path = _tape_path(vertical)
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def query(
    vertical: str,
    type: Optional[str] = None,
    since: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Query tape records by type, time, and/or limit."""
    records = read_all(vertical)
    if type:
        records = [r for r in records if r.get("type") == type]
    if since:
        records = [r for r in records if r.get("ts", "") >= since]
    if limit:
        records = records[-limit:]
    return records


def latest(vertical: str, type: str) -> Optional[Dict[str, Any]]:
    """Return the most recent record of a given type."""
    results = query(vertical, type=type, limit=1)
    return results[-1] if results else None


def count(vertical: str, type: Optional[str] = None) -> int:
    """Count records, optionally filtered by type."""
    return len(query(vertical, type=type))


def tape_path(vertical: str) -> str:
    """Expose the tape file path for external tools."""
    return _tape_path(vertical)
