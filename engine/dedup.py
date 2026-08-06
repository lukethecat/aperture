"""
dedup.py — Deduplication and clustering (publish-pool stage).

Two-level dedup:
  1. Exact url_norm match.
  2. Title simhash clustering: hamming distance <= threshold => same event.

Each cluster keeps the richest item as the main item; related sources are
recorded as alternatives.
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Set, Tuple

from . import tape

DEDUP_LOOKBACK_DAYS = 14
HAMMING_THRESHOLD = 3
TOKEN_OVERLAP_THRESHOLD = 3
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "must", "shall", "can",
    "need", "dare", "ought", "used", "this", "that", "these", "those",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "us", "them", "my", "your", "his", "its", "our", "their",
}


def _tokenize(text: str) -> List[str]:
    """Tokenize for simhash: English words + Chinese character bigrams."""
    text = text.lower()
    en_tokens = re.findall(r'[a-z]+', text)
    cn_chars = re.findall(r'[\u4e00-\u9fff]', text)
    cn_bigrams = [cn_chars[i] + cn_chars[i + 1] for i in range(len(cn_chars) - 1)]
    return en_tokens + cn_bigrams


def simhash(text: str, bits: int = 64) -> int:
    """Compute a simhash fingerprint for a title."""
    tokens = _tokenize(text)
    if not tokens:
        return 0
    v = [0] * bits
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        for i in range(bits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1
    fingerprint = 0
    for i in range(bits):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def _significant_tokens(text: str) -> Set[str]:
    """Return non-stopword tokens for overlap comparison."""
    return set(_tokenize(text)) - _STOPWORDS


def _title_overlap(t1: str, t2: str) -> int:
    """Count shared significant tokens between two titles."""
    return len(_significant_tokens(t1) & _significant_tokens(t2))


def hamming_distance(h1: int, h2: int) -> int:
    """Hamming distance between two simhash values."""
    return bin(h1 ^ h2).count('1')


def load_recent_items(vertical: str, days: int = DEDUP_LOOKBACK_DAYS) -> List[Dict[str, Any]]:
    """Load pooled/verified items from the past N days (excluding today)."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = now - timedelta(days=days)
    cutoff_str = cutoff.isoformat()
    today_str = today_start.isoformat()

    recent = []
    for item in tape.query(vertical, type="item"):
        if item.get("stage") in ("pooled", "verified"):
            ts = item.get("ts", "")
            if cutoff_str <= ts < today_str:
                recent.append(item)
    return recent


def dedup_and_cluster(candidates: List[Dict[str, Any]],
                      vertical: str) -> Dict[str, Any]:
    """
    Deduplicate verified candidates and cluster similar titles.
    Returns pooled items and cluster metadata.
    """
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    recent = load_recent_items(vertical)
    seen_urls: Set[str] = {r.get("url_norm", "") for r in recent if r.get("url_norm")}
    history_hashes: List[Tuple[int, str]] = []
    history_items: Dict[str, Dict[str, Any]] = {}
    for r in recent:
        sh = r.get("simhash")
        rid = r.get("id", "")
        if sh:
            history_hashes.append((sh, rid))
        if rid:
            history_items[rid] = r

    for c in candidates:
        title = c.get("title", "")
        c["simhash"] = simhash(title)
        c["id"] = c.get("id") or hashlib.md5(
            (c.get("url_norm", "") + title).encode()
        ).hexdigest()[:12]

    pooled = []
    url_deduped = 0
    simhash_deduped = 0
    clusters: Dict[str, List[Dict[str, Any]]] = {}

    for c in candidates:
        url_n = c.get("url_norm", "")
        sh = c["simhash"]

        if url_n in seen_urls:
            url_deduped += 1
            continue

        matched_cluster = None
        candidate_title = c.get("title", "")
        for hist_hash, hist_id in history_hashes:
            if hamming_distance(sh, hist_hash) <= HAMMING_THRESHOLD:
                matched_cluster = hist_id
                break
            # Fallback: same-event items from different outlets often have
            # very different headlines. If they share enough significant
            # tokens, treat them as the same cluster.
            hist_item = history_items.get(hist_id) or next((i for i in pooled if i.get("id") == hist_id), None)
            if hist_item and _title_overlap(candidate_title, hist_item.get("title", "")) >= TOKEN_OVERLAP_THRESHOLD:
                matched_cluster = hist_id
                break

        if matched_cluster:
            c["cluster_id"] = matched_cluster
            simhash_deduped += 1
            if matched_cluster not in clusters:
                clusters[matched_cluster] = []
            clusters[matched_cluster].append(c)
        else:
            c["cluster_id"] = c["id"]
            clusters[c["id"]] = [c]
            history_hashes.append((sh, c["id"]))
            history_items[c["id"]] = c

        seen_urls.add(url_n)
        c["stage"] = "pooled"
        tape.append(vertical, c)
        pooled.append(c)

    cluster_results = []
    for cid, items in clusters.items():
        items.sort(key=lambda x: x.get("scores", {}).get("prescreen", 0), reverse=True)
        main = items[0]
        related = items[1:] if len(items) > 1 else []
        cluster_results.append({
            "cluster_id": cid,
            "main_item": main,
            "related_items": related,
            "source_count": len(items),
        })

    cluster_results.sort(
        key=lambda x: (x["source_count"],
                       x["main_item"].get("scores", {}).get("prescreen", 0)),
        reverse=True,
    )

    return {
        "vertical": vertical,
        "date": today,
        "input_count": len(candidates),
        "pooled_count": len(pooled),
        "url_deduped": url_deduped,
        "simhash_deduped": simhash_deduped,
        "cluster_count": len(cluster_results),
        "clusters": cluster_results,
        "pooled_items": pooled,
    }


def print_dedup_stats(stats: Dict[str, Any]) -> str:
    """Format dedup stats as human-readable text."""
    lines = [
        f"=== Pool/Dedup {stats['date']} ===",
        f"Input: {stats['input_count']} -> pooled: {stats['pooled_count']}",
        f"URL deduped: {stats['url_deduped']} / simhash deduped: {stats['simhash_deduped']}",
        f"Clusters: {stats['cluster_count']}",
    ]
    multi = [c for c in stats["clusters"] if c["source_count"] > 1]
    if multi:
        lines.append("Multi-source events:")
        for cl in multi[:5]:
            sources = [r.get("source_name", "?") for r in cl["related_items"]]
            title = cl["main_item"].get("title", "")[:50]
            lines.append(f"  [{cl['source_count']} sources] {title} <- {', '.join(sources)}")
    return "\n".join(lines)
