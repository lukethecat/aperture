"""
scanner.py — Frontpage scanning + URL normalization + frontpage diff.

The "collect" stage of the pipeline: fetch each source's list page,
extract title/link pairs, diff against the previous snapshot, and return
candidates. Everything is logged to the tape.
"""
import html as html_module
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from . import tape

DEFAULT_TIMEOUT = 15
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_source_platform", "utm_creative_format",
    "fbclid", "gclid", "gclsrc", "dclid", "gbraid", "wbraid",
    "msclkid", "twclid", "li_fat_id",
    "mc_cid", "mc_eid",
    "ref", "referer", "referrer", "source", "from",
    "isappinstalled", "nsukey", "wxfid",
    "s_cid", "_ga", "_gl", "oly_enc_id", "oly_anon_id",
}


def _fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Fetch a URL using urllib (stdlib only)."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            # Try charset from Content-Type header
            charset = resp.headers.get_content_charset()
            if charset:
                return data.decode(charset, errors="replace")
            # Fallback: try utf-8 then latin-1
            try:
                return data.decode("utf-8", errors="replace")
            except UnicodeDecodeError:
                return data.decode("latin-1", errors="replace")
    except urllib.error.URLError:
        return ""
    except Exception:
        return ""


def normalize_url(url: str) -> str:
    """
    Normalize a URL:
      - drop fragments
      - drop tracking query params
      - strip trailing slash
      - lowercase host and strip leading www.
      - force https scheme
    """
    if not url:
        return ""
    try:
        p = urlparse(url.strip())
        scheme = "https"
        host = (p.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        port = p.port
        port_str = "" if port in (80, 443, None) else f":{port}"
        path = (p.path or "").rstrip("/")
        qs = parse_qs(p.query, keep_blank_values=False)
        clean_qs = {k: v for k, v in qs.items() if k.lower() not in TRACKING_PARAMS}
        query = urlencode(clean_qs, doseq=True)
        return urlunparse((scheme, f"{host}{port_str}", path, "", query, "")).lower()
    except Exception:
        return url.strip().lower().rstrip("/")


def _abs_url(href: str, base_url: str, link_prefix: str = "") -> str:
    """Resolve a possibly relative URL."""
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("//"):
        return "https:" + href
    base = urlparse(base_url)
    if href.startswith("/"):
        return f"{base.scheme}://{base.netloc}{href}"
    if link_prefix:
        if link_prefix.endswith("/") and href.startswith("/"):
            return link_prefix[:-1] + href
        if not link_prefix.endswith("/") and not href.startswith("/"):
            return f"{link_prefix}/{href}"
        return link_prefix + href
    return href


def _extract_generic_links(raw: str, base_url: str, link_prefix: str = "") -> List[Dict[str, str]]:
    """Generic <a href> extraction."""
    items = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>([^<]{8,150})</a>', raw, re.IGNORECASE)
    results = []
    for href, title in items:
        title = html_module.unescape(title).strip()
        if not title or len(title) < 8:
            continue
        url = _abs_url(html_module.unescape(href).strip(), base_url, link_prefix)
        if not url.startswith("http"):
            continue
        results.append({"title": title, "url": url})
    return results


def _parse_rfc822_date(value: str) -> Optional[datetime]:
    """Parse an RSS/Atom style date into an aware UTC datetime."""
    value = value.strip()
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _extract_rss(raw: str, base_url: str) -> List[Dict[str, str]]:
    """Extract items from RSS/XML, including pubDate when available."""
    items = re.findall(r'<item>(.*?)</item>', raw, re.DOTALL | re.IGNORECASE)
    results = []
    for item in items:
        t = re.search(r'<title[^>]*>(.*?)</title>', item, re.DOTALL | re.IGNORECASE)
        l = re.search(r'<link[^>]*>(.*?)</link>', item, re.DOTALL | re.IGNORECASE)
        if not l:
            l = re.search(r'<guid[^>]*>(.*?)</guid>', item, re.DOTALL | re.IGNORECASE)
        d = re.search(r'<pubDate[^>]*>(.*?)</pubDate>', item, re.DOTALL | re.IGNORECASE)
        if not t or not l:
            continue
        title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', t.group(1).strip(), flags=re.DOTALL)
        link = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', l.group(1).strip(), flags=re.DOTALL)
        title = html_module.unescape(title).strip()
        link = html_module.unescape(link).strip()
        if not link.startswith("http"):
            continue
        entry = {"title": title, "url": link}
        if d:
            entry["pub_date"] = d.group(1).strip()
        results.append(entry)
    return results


def _extract_regex(raw: str, profile: Dict[str, Any], base_url: str) -> List[Dict[str, str]]:
    """Regex-based extraction using groups defined in profile."""
    pattern = profile.get("pattern", "")
    if not pattern:
        return []
    title_g = profile.get("title_group", -1)
    url_g = profile.get("url_group", 0)
    url_prefix = profile.get("url_prefix", "")
    date_group = profile.get("date_group", None)

    matches = re.findall(pattern, raw, re.DOTALL)
    results = []
    for match in matches:
        if not isinstance(match, tuple):
            continue
        if title_g >= len(match) or url_g >= len(match):
            continue
        title = match[title_g].strip() if title_g >= 0 else ""
        href = match[url_g].strip() if url_g >= 0 else ""
        if not title or len(title) < 5:
            continue
        url = _abs_url(href, base_url, url_prefix)
        if not url.startswith("http"):
            continue
        entry = {"title": html_module.unescape(title), "url": url}
        if date_group is not None and 0 <= date_group < len(match):
            entry["pub_date"] = match[date_group].strip()
        results.append(entry)
    return results


def _extract_json_api(raw: str, profile: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract items from a JSON API response."""
    try:
        data = json.loads(raw, strict=False)
    except json.JSONDecodeError:
        return []

    list_path = profile.get("list_path", "")
    title_key = profile.get("title_key", "title")
    url_key = profile.get("url_key", "url")

    node = data
    for key in list_path.split(".") if list_path else []:
        if isinstance(node, dict):
            node = node.get(key, [])
        else:
            break
    if not isinstance(node, list):
        return []

    results = []
    for item in node:
        if not isinstance(item, dict):
            continue
        title = re.sub(r'<[^>]+>', '', str(item.get(title_key, ""))).strip()
        url = str(item.get(url_key, "")).strip()
        if title and url and url.startswith("http"):
            entry = {"title": title, "url": url}
            for extra in profile.get("extra_keys", []):
                if extra in item:
                    entry[extra] = str(item[extra])
            results.append(entry)
    return results


def extract_items(raw: str, profile: Dict[str, Any], base_url: str) -> List[Dict[str, str]]:
    """Dispatch extraction based on profile.method."""
    method = profile.get("method", "generic_links")
    if method == "rss":
        return _extract_rss(raw, base_url)
    if method == "regex":
        return _extract_regex(raw, profile, base_url)
    if method == "json_api":
        return _extract_json_api(raw, profile)
    return _extract_generic_links(raw, base_url, profile.get("link_prefix", ""))


def _apply_time_window(
    items: List[Dict[str, str]],
    window_hours: float,
    missing_date_policy: str,
    now: datetime,
) -> List[Dict[str, str]]:
    """
    Filter items to only those published within the last window_hours.
    Items without a parseable pub_date are dropped by default (conservative).
    Set missing_date_policy='include' to keep them for sources where dates are unreliable.
    """
    cutoff = now - timedelta(hours=window_hours)
    kept: List[Dict[str, str]] = []
    for item in items:
        raw_date = item.get("pub_date")
        if not raw_date:
            if missing_date_policy == "include":
                kept.append(item)
            continue
        dt = _parse_rfc822_date(raw_date) if isinstance(raw_date, str) else raw_date
        if dt is None:
            if missing_date_policy == "include":
                kept.append(item)
            continue
        if dt >= cutoff:
            kept.append(item)
    return kept


def fetch_frontpage(source: Dict[str, Any]) -> Tuple[List[Dict[str, str]], bool]:
    """
    Fetch a source's list page and extract items.
    Applies a configurable publication-date window (default 36h) before diffing.
    Returns (items, success).
    """
    list_url = source["list_url"]
    profile = source.get("extract_profile", {})

    raw = _fetch_url(list_url)
    if not raw or len(raw) < 200:
        return [], False

    items = extract_items(raw, profile, list_url)
    now = datetime.now(timezone.utc)
    window_hours = profile.get("window_hours", 36)
    missing_policy = profile.get("missing_date_policy", "exclude")
    items = _apply_time_window(items, window_hours, missing_policy, now)

    valid_items = []
    for item in items:
        url = normalize_url(item.get("url", ""))
        if not url or len(url) < 10:
            continue
        if any(url.endswith(ext) for ext in ["/rss", "/rss/", ".xml", "/feed"]):
            continue
        item["url_norm"] = url
        valid_items.append(item)
    return valid_items, True


def diff_frontpage(source_id: str, current_items: List[Dict[str, str]],
                   vertical: str) -> List[Dict[str, str]]:
    """Return items whose url_norm did not appear in the previous snapshot."""
    all_frontpages = tape.query(vertical, type="frontpage")
    prev_urls: Set[str] = set()
    for fp in reversed(all_frontpages):
        if fp.get("source_id") == source_id:
            prev_urls = {item.get("url_norm", "") for item in fp.get("items", [])}
            break
    return [item for item in current_items if item.get("url_norm") not in prev_urls]


def save_frontpage(vertical: str, source_id: str, date: str,
                   items: List[Dict[str, str]]) -> None:
    """Write a frontpage snapshot to the tape."""
    tape.append(
        vertical,
        {
            "type": "frontpage",
            "source_id": source_id,
            "date": date,
            "items": items,
            "count": len(items),
        },
    )


def _update_health(vertical: str, source_id: str, success: bool) -> None:
    """Update source health state in the tape."""
    sources = tape.query(vertical, type="source")
    latest = None
    for s in reversed(sources):
        if s.get("id") == source_id:
            latest = s
            break
    if not latest:
        return
    health = latest.get("health", {"last_ok": None, "fail_count": 0})
    if success:
        health["last_ok"] = datetime.now(timezone.utc).isoformat()
        health["fail_count"] = 0
    else:
        health["fail_count"] = health.get("fail_count", 0) + 1
    latest["health"] = health
    tape.append(vertical, latest)


def scan_all(vertical: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Collect stage: scan every source, diff, save snapshot, update health.
    Returns stats dict including the list of candidate items.
    """
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    stats = {
        "vertical": vertical,
        "date": today,
        "scanned_at": now.isoformat(),
        "sources_total": len(sources),
        "sources_ok": 0,
        "sources_fail": 0,
        "items_total": 0,
        "candidates_total": 0,
        "per_source": {},
        "health_alerts": [],
    }

    all_candidates: List[Dict[str, str]] = []

    for src in sources:
        sid = src["id"]
        sname = src.get("name", sid)
        profile = src.get("extract_profile", {})
        method = profile.get("method", "") if isinstance(profile, dict) else ""

        # Human-feed sources have no list_url to fetch; their items are injected
        # separately and picked up by the pipeline after the scan stage.
        if method == "human_feed":
            stats["per_source"][sid] = {
                "name": sname,
                "items": 0,
                "candidates": 0,
                "status": "human-feed",
            }
            continue

        items, success = fetch_frontpage(src)

        if success:
            candidates = diff_frontpage(sid, items, vertical)
            save_frontpage(vertical, sid, today, items)
            _update_health(vertical, sid, True)

            stats["sources_ok"] += 1
            stats["items_total"] += len(items)
            stats["candidates_total"] += len(candidates)
            stats["per_source"][sid] = {
                "name": sname,
                "items": len(items),
                "candidates": len(candidates),
                "status": "ok",
            }

            for c in candidates:
                c["source_id"] = sid
                c["source_name"] = sname
            all_candidates.extend(candidates)
        else:
            _update_health(vertical, sid, False)
            stats["sources_fail"] += 1
            fail_count = 0
            # look up latest health after update
            for s in reversed(tape.query(vertical, type="source")):
                if s.get("id") == sid:
                    fail_count = s.get("health", {}).get("fail_count", 0)
                    break
            stats["per_source"][sid] = {
                "name": sname,
                "items": 0,
                "candidates": 0,
                "status": "fail",
            }
            if fail_count >= 3:
                stats["health_alerts"].append({
                    "source_id": sid,
                    "name": sname,
                    "fail_count": fail_count,
                    "msg": f"Source {sname} has failed {fail_count} times consecutively",
                })

    stats["candidates"] = all_candidates
    return stats


def print_scan_stats(stats: Dict[str, Any]) -> str:
    """Format scan stats as human-readable text."""
    lines = [
        f"=== Scan {stats['date']} ===",
        f"Sources: {stats['sources_ok']}/{stats['sources_total']} responded",
        f"Frontpage items: {stats['items_total']}",
        f"New candidates (diff): {stats['candidates_total']}",
        "",
    ]
    for sid, info in stats["per_source"].items():
        icon = "OK" if info["status"] == "ok" else "FAIL"
        lines.append(f"  [{icon}] {info['name']}: {info['items']} items / {info['candidates']} new")
    if stats["health_alerts"]:
        lines.append("")
        for alert in stats["health_alerts"]:
            lines.append(f"  ! {alert['msg']}")
    return "\n".join(lines)
