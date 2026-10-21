# Social Source Adapters

> Status: **proposal** — see issue [#5](https://github.com/lukethecat/aperture/issues/5) (adapter method) and [#6](https://github.com/lukethecat/aperture/issues/6) (event-level dedup).
> Audience: external systems integrating social channels (Weibo / Douyin / Xiaohongshu / X / WeChat) into Aperture.

## Why adapters

Aperture's built-in `method` enum (`rss` / `regex` / `json_api` / `generic_links` / `human_feed`)
assumes a **stable list URL**, a **`pub_date` per item**, **URL-unique identity**, and **no auth**.

Social platforms violate all four:

| Dimension | Aperture assumes | Social reality |
|---|---|---|
| Entry | stable `list_url` | hot-search / query results change on every call |
| Time | `pub_date` present | hot-search entries have **no publish time**, only rank/heat |
| Identity | URL is unique | one event → many URLs across platforms/accounts |
| Access | no auth | cookie / anti-bot / captcha / JS rendering |

Forcing social feeds into `generic_links` produces *silent* misbehaviour: unknown `method`
values currently fall back to `generic_links` without warning.

## Contract

An **adapter** is an external command that emits items on **stdout**.

### Invocation

```toml
[[sources]]
id = "weibo_hot"
name = "微博热搜"
list_url = "adapter://weibo_hot"          # identifier only; no request is made
extract_profile = { method = "adapter",
                    command = "dsh-collect weibo_hot",
                    window_hours = 3,
                    missing_date_policy = "include" }
```

### stdout — NDJSON

One JSON object **per line** (streaming: emit as you collect; do not buffer the whole run).

```json
{"title":"问界回应起火","url":"https://s.weibo.com/weibo?q=...","pub_date":null,"rank":1,"heat":3064909,"platform":"weibo","event_key":"问界-起火"}
```

| Field | Required | Notes |
|---|---|---|
| `title` | ✅ | item headline |
| `url` | ✅ | item-level URL; Aperture computes `url_norm` |
| `pub_date` | ⬜ | RFC822 or ISO-8601; `null` for social |
| `rank` / `heat` | ⬜ | carried to tape via `extra_keys` |
| `platform` | ⬜ | `weibo` / `douyin` / … |
| `event_key` | ⬜ | event grouping key, see issue [#6](https://github.com/lukethecat/aperture/issues/6) |

### Exit codes — three-state, not boolean

A boolean (success / failure) is not enough: "collected nothing" and "couldn't collect" are
different facts and must not collapse into the same signal.

| Code | Meaning | Effect on health |
|---|---|---|
| `0` | **collected** — may be N>0, or 0 lines meaning *genuinely nothing new* | healthy; badge ⚪ if 0 lines from a feed-style source |
| `2` | **endpoint unreachable / blocked** — not "no content", but "did not get it" | `fail_count += 1`; badge 🟡/🔴 |
| `3` | **parse failure** — got bytes but could not interpret them | `fail_count += 1`; badge 🟡/🔴 |
| other non-zero | unexpected failure — treat as `2` (unreachable) for health purposes | `fail_count += 1` |

Write failure reasons to **stderr** only.

> This mirrors the `0` / `1` / `3` three-state pattern used by `check_rendered.py` in the
> website project: *passed* / *found problems* / *could not check*. The third state is the
> one that stops "I couldn't verify" from silently becoming "verified clean".

### Optional `--out <path>`

When passed, the adapter MAY additionally write the same NDJSON to `<path>` for debugging/replay.
This is **not part of the contract** — the engine never reads it.

## Why stdout, not a shared directory

1. **Stateless contract** — the adapter never needs to know the host's filesystem layout; the two systems stay decoupled.
2. **A directory convention adds coupling** — cleanup policy, concurrent writes, permissions, path escaping each become new failure modes.
3. **Cross-machine** — a cloud runtime and a local Aperture instance can exchange stdout over SSH/HTTP/pipes; a directory would require mounting.

## Date handling

Social items usually have no `pub_date`. Set:

```toml
missing_date_policy = "include"
```

and keep `window_hours` short (1–3h) so stale hot-search rows do not accumulate.

## Failure semantics (important)

```text
exit 0, N>0 lines   → healthy, N items
                        → badge 🟢
exit 0, 0 lines     → healthy, genuinely nothing new
                        → badge ⚪ (feed-style idle)
exit 2              → endpoint unreachable / blocked
                        → fail_count += 1 → badge 🟡/🔴
exit 3              → got bytes, could not parse
                        → fail_count += 1 → badge 🟡/🔴
timeout             → treat as exit 2
```

Never conflate "couldn't collect" with "collected nothing". That distinction is exactly what
the status footer exists to surface — and it is the same three-state discipline the website
project adopted after "the checker said clean but it had only checked the data layer".

## Reference implementation: Weibo hot search

Verified working (2026-10-21): **52 live entries**, no cookie required.

```bash
curl -s 'https://weibo.com/ajax/side/hotSearch' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/140.0' \
  -H 'Referer: https://weibo.com/'
```

Response shape: `{"ok":1,"data":{"realtime":[{"word","num","label_name","rank"}...]}}`

Mapping:

```python
{"title": e["word"],
 "url": f'https://s.weibo.com/weibo?q={quote(e["word"])}',
 "pub_date": None,
 "rank": e.get("rank"),
 "heat": e.get("num"),
 "platform": "weibo"}
```

> ⚠️ This is an **unofficial** endpoint. It can change without notice.
> Pair it with health monitoring and a `human_feed` fallback. Do not make it the only source.

## Endpoints that do **not** work (verified 2026-10-21)

Worth recording so nobody re-tries them:

| Endpoint | Result |
|---|---|
| `https://s.weibo.com/top/summary` | returns *Sina Visitor System* login wall |
| `https://m.weibo.cn/api/container/getIndex?...` | HTTP **432** (anti-bot) |
| `https://36kr.com/feed` (and `/feed-newsflash`) | returns an HTML shell, **not RSS** |
| `https://www.toutiao.com` | JS-only shell ("requires JavaScript") |
| `https://www.autohome.com.cn` | works but **GBK-encoded** — decode as `gbk`, not UTF-8 |
| `https://tophub.today/...` | client-side rendered, not scrapable without a browser |

## Roadmap

1. `method="adapter"` in `engine/scanner.py` ([#5](https://github.com/lukethecat/aperture/issues/5))
2. `event_key` aggregation in dedup ([#6](https://github.com/lukethecat/aperture/issues/6))
3. This document becomes normative once #5 lands.
