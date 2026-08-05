---
name: aperture
description: >-
  A skill for AI agents that want to produce better daily reports and discover
  more of what their users actually want. Scans source front pages, diffs them
  against yesterday, prescreens with a weighted profile, reviews with an LLM,
  deduplicates, publishes, and evolves the profile from user feedback. All
  decisions go to an append-only tape for audit and replay.
version: 0.1.0
---

# Skill: Aperture

> **TL;DR** — A skill for AI agents that want to produce better daily reports and discover more of what their users actually want. Aperture scans source front pages, diffs them against yesterday, prescreens with a weighted profile, reviews with an LLM, deduplicates, publishes, and evolves the profile from user feedback. All decisions go to an append-only tape.

This skill is **implementation-agnostic**. An agent can execute it by reading this file, by calling the included Python reference implementation, or by porting the patterns to its own runtime.

---

## 1. Purpose

Give agents a deterministic, auditable news-curation skill that replaces static RSS readers and one-shot LLM summarizers:

1. **Scan the front page** — treat "reading the front page" as a first-class operation, not just feed polling.
2. **Tape every decision** — record every source snapshot, item, rejection reason, profile version, and report in an append-only log for audit and replay.
3. **Learn from user feedback** — update the agent's taste through explicit feedback and keep every change versioned and reversible.

When an agent runs this skill, it can answer "why was this selected?" and "what would have been different yesterday?" from the tape.

---

## 2. Core concepts

| Concept | Meaning |
|---------|---------|
| **Vertical** | A configured news beat (e.g. tech, auto, AI policy). Each vertical has its own sources, profile, and tape. |
| **Tape** | Append-only JSONL log. One file per vertical. Every source snapshot, item, profile version, feedback, and report is a record. |
| **Profile** | The vertical's "taste": weighted keywords, categories with bonuses, and negative terms. Versioned; every change is logged. |
| **Scan** | Fetch each source's list page, extract titles/links, normalize URLs, diff against the previous snapshot. |
| **Reflection loop** | User feedback → parsed profile operations → version bump → evolution record → recheck recently pooled items. |

---

## 3. Four-stage pipeline

```
┌─────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐
│ collect │ -> │   edit   │ -> │ review  │ -> │ publish  │
│ (scan)  │    │(prescreen│    │  (LLM)  │    │ (dedup + │
│         │    │  rules)  │    │         │    │  report) │
└─────────┘    └──────────┘    └─────────┘    └──────────┘
     │               │               │               │
     └───────────────┴───────────────┴───────────────┘
                         │
                    append-only TAPE
```

### 3.1 Collect — scan the front page

**Goal:** produce today's candidate items from each configured source.

**Steps:**

1. For each source, fetch `list_url`.
2. Extract `{title, url}` pairs using the source's `extract_profile`:
   - `rss` — parse `<item>` blocks.
   - `generic_links` — parse `<a href>` tags.
   - `regex` — apply a regex with named groups for title/url/date.
   - `json_api` — navigate a JSON path and read title/url keys.
3. Normalize every URL:
   - Drop fragments and tracking parameters (`utm_*`, `fbclid`, etc.).
   - Strip trailing slash and leading `www.`.
   - Force `https` scheme, lowercase host.
4. Diff against the **previous frontpage snapshot** for this source (read from tape).
   - New `url_norm` values become candidates.
   - Save the full current snapshot as a new `frontpage` tape record.
5. Update source health:
   - Success → reset `fail_count`.
   - Failure → increment `fail_count`; alert if ≥ 3 consecutive failures.

**Why diff against the frontpage instead of parsing publish dates?**
Because many sources have unreliable timestamps or anti-scraping layouts. "New on the front page" is a robust proxy for "news in today's window".

**Time-window guard (deterministic, not LLM):**
For pull sources that do expose `pubDate` (RSS/Atom), the scanner applies a hard cutoff before diffing. Default window is **36 hours**; override with `extract_profile.window_hours`. Items older than the window are dropped. Items with missing or unparseable dates are **excluded by default** (`missing_date_policy: exclude`) because a date the engine cannot verify is a date it cannot trust. Set `missing_date_policy: include` only for sources where dates are known to be unreliable and frontpage diff is the primary signal.

This rule exists because date-window enforcement is bookkeeping, not judgment. It must be deterministic and auditable — never delegated to an LLM, which is prone to misreading dates and mixing stale stories into today's report.

### 3.2 Edit — prescreen with the profile

**Goal:** score candidates with cheap rules; keep the wide funnel.

**Formula:**

```
score = sum(matched keyword weights)
      + sum(category match bonuses)
      - sum(matched negative weights)
```

**Steps:**

1. Load the vertical's latest profile.
2. For each candidate title:
   - Match keywords and categories (whole-word boundary for ASCII terms).
   - Subtract negatives.
   - Record `last_hit` for any matched term.
3. Threshold: default `score >= 2` passes; lower scores are **rejected with `reject_reason: low_score`**.
4. Write every candidate to the tape as an `item` record:
   - Passed → `stage: prescreened`.
   - Rejected → `stage: rejected`, with `reject_reason`.

> Rejected items are the fuel for calibration. Never delete them.

### 3.3 Review — structured second pass

**Goal:** verify that prescreened items are real news, on-topic, and not ads/jobs.

**Steps:**

1. Sort prescreened items by score (descending).
2. Cap per-source representation (e.g. max 4 per source) to avoid monopoly.
3. For each item, fetch article text (first ~1000 chars) and extract a publish date via a fallback chain:
   - JSON-LD `datePublished`
   - `<meta article:published_time>`
4. Send a batch prompt to the configured LLM provider. Ask for each item:
   - `is_news` — not ad/job/announcement
   - `is_ad`, `is_job` — disqualifiers
   - `vertical_fit` — 0 to 1 relevance score
   - `summary` — 2-3 sentence summary
5. Apply rejection reasons:
   - `not_news`, `is_ad`, `is_job`, `low_fit`.
6. Write results to the tape as `item` records with `stage: verified` or `stage: rejected`.

**If no LLM provider is configured:** the pipeline runs in `--dry` rule-only mode and promotes prescreened items directly.

### 3.4 Publish — deduplicate and report

**Goal:** collapse duplicates and produce a readable daily report.

**Steps:**

1. Load recently pooled items (last 14 days, excluding today).
2. Two-level dedup for verified items:
   - Exact `url_norm` match → skip.
   - Title `simhash` with hamming distance ≤ 3 → same event; group into a cluster.
3. For each cluster, pick the highest-scored item as the main item; others become related sources.
4. Sort clusters by source count and score.
5. Format the report. Append a status footer:
   - sources scanned, items prescreened, rejected, pooled, report item count
   - source health alerts
   - stage timings
6. Write a `report` record to the tape.

---

## 4. Reflection loop (self-evolution)

**Trigger:** user reads a report and gives feedback, e.g.

> "More AI safety stories, fewer sponsored posts, and keep an eye on EU regulation."

**Steps:**

1. Parse feedback into profile operations:
   - `add_keyword: {term, weight}`
   - `adjust_weight: {term, delta}`
   - `remove_keyword: {term}`
   - `add_negative: {term, weight}`
   - `adjust_negative_weight: {term, delta}`
   - `remove_negative: {term}`
2. Apply operations to the profile; bump version.
3. Write an `evolution` tape record containing the operations and original feedback text.
4. Recheck recently pooled items (last 7 days) against the new negatives/lowered weights.
   - If any would now be filtered, report the count to the user.
5. Return a confirmation summary.

**Decay rule (weekly):**
- `origin: learned` terms that have not hit for 30 days lose 1 weight.
- Weight 0 → move to a pending-delete list; ask user before removing.
- `origin: manual` terms never auto-delete, only warn.

---

## 5. Source-acquisition taxonomy

A source can be acquired in five ways. The engine treats them uniformly once they reach the tape. The report's source registry renders each source as `status [name](url) · method` so a reader can see at a glance how the source is acquired.

| Type | Mechanism | When to use | Registry display |
|------|-----------|-------------|------------------|
| **pull** | RSS/API/curl on cron | Stable feeds and APIs | `🟢 [Hacker News](https://news.ycombinator.com/rss) · pull` |
| **scan** | Frontpage diff + prescreen | SPAs, irregular sites | `🟢 [TechCrunch](https://techcrunch.com) · scan` |
| **push** | Webhook/SSE/bridge | Internal alerts or closed ecosystems | `🟢 [Internal Alerts](...) · push` |
| **search** | Ad-hoc search | New-source discovery or major-event catch-up | `🟢 [Search](...) · search` |
| **human-feed** | User drops a link | Exclusive tips and first-hand signals | `🟢 Weixin Tip · human-feed` |

Add a source by registering `{id, name, list_url, extract_profile}` in the vertical config. A human-feed source sets `extract_profile = { method = "human_feed" }` and may omit `list_url`.

### Agent-facilitated human-feed

A useful variant is **agent-facilitated human-feed**: the agent itself performs a
platform search (e.g. on X for posts under an AI hashtag in the last 24–36
hours), curates ≥1 candidate, and injects it through the human-feed channel.
The injected item still goes through the same prescreen, review, and dedup
stages as pull/scan items — human-feed guarantees entry into the candidate
pool, not a free pass into the report.

**Reference implementation (`scripts/x_hunt.py`):**

```bash
# Search DuckDuckGo for AI posts on X and inject the top candidate
python scripts/x_hunt.py --vertical ai-frontier \
  --query "AI artificial intelligence site:x.com" --inject

# Inject a manually chosen X URL (preferred when the agent has already curated)
python scripts/x_hunt.py --vertical ai-frontier \
  --title "OpenAI announces GPT-5" \
  --url "https://x.com/OpenAI/status/1234567890" \
  --inject

# Review without injecting
python scripts/x_hunt.py --vertical ai-frontier \
  --query "AI artificial intelligence site:x.com"
```

The injected record is written to the tape as an `item` with:

- `source_id`: the human-feed source id (default `owner_tips`).
- `stage`: `scanned` — it enters the pipeline at prescreen.
- `facilitated_by`: `agent` — auditable provenance.

This mode turns the platform from a passive content source into an active
source-discovery hunt: when the agent repeatedly finds good stories from the
same outlet, ECHO can ask "Add '<outlet>' as a tracked source?" and, on yes,
promote the outlet to a formal pull/scan source. That closed loop is the
skill's self-evolution in action.

---

## 6. Tape record types

Each tape line is a JSON object with a `type` field.

| type | fields |
|------|--------|
| `source` | `id`, `name`, `vertical`, `list_url`, `extract_profile`, `health` |
| `frontpage` | `source_id`, `date`, `items[]`, `count` |
| `profile` | `vertical`, `version`, `keywords[]`, `negatives[]`, `categories[]`, `reason` |
| `item` | `id`, `vertical`, `source_id`, `title`, `url`, `url_norm`, `stage`, `scores`, `reject_reason`, `simhash`, `cluster_id` |
| `report` | `date`, `vertical`, `item_ids[]`, `generated_at`, `stats` |
| `feedback` | `date`, `vertical`, `text`, `applied_ops[]`, `status` |
| `evolution` | `vertical`, `from_version`, `to_version`, `ops[]`, `reason`, `date` |

---

## 7. Running the reference implementation

```bash
# Rule-only dry run (no LLM required)
python -m engine.pipeline --dry --vertical tech --config config/example_vertical.toml

# With LLM review
export APERTURE_LLM_API_KEY="sk-..."
python -m engine.pipeline --vertical tech --config config/example_vertical.toml

# Apply feedback
python -c "from engine.feedback import apply_feedback; apply_feedback('More AI safety, fewer ads', 'tech')"
```

After publishing, optionally run ECHO to ask the user up to two clarification questions:

```python
from engine.echo import ask

questions = ask("tech")
for q in questions:
    print(q["question"])

# Later, apply a one-word answer: yes / no / skip / silence
from engine.echo import apply_answer
apply_answer(question_id, "tech", "yes")
```

---

## 8. ECHO — proactive clarification

ECHO is an optional proactive layer that asks the user up to two one-word
clarification questions after each report. It turns passive readers into active
profile trainers.

ECHO is intentionally split into four stages with the tape as the boundary
between each. This makes delivery failures safe to retry and makes the whole
loop auditable.

### Four-stage flow

```
┌─────────┐   ┌──────────┐   ┌─────────┐   ┌──────────┐
│ prepare │ → │  deliver │ → │ ingest  │ → │ distill  │
│(generate│   │(post to  │   │(record  │   │(apply to │
│ questions│   │ channel) │   │ answer) │   │ profile) │
└────┬────┘   └────┬─────┘   └────┬────┘   └────┬─────┘
     │             │              │             │
     └─────────────┴──────────────┴─────────────┘
                    append-only TAPE
```

1. **prepare** — after `publish`, generate today's clarification questions from
   the pooled items and write them to the tape as `echo_question` records with
   `status: pending`. Expire any unanswered questions from the previous day first.
   Human-feed items additionally trigger a source-proposal question:
   "Add '<source name>' as a tracked source?"  The question is generated from
   today's human-feed items on the tape **regardless of whether the item survived
   prescreen** — the question is about the source, not the item's score. If the
   sample URL is on `mp.weixin.qq.com`, the question notes that Weixin is a closed
   platform and that expansion research is needed. A positive answer records a
   `source_proposal` tape entry; it does **not** automatically register the source
   (owner confirmation is required).
2. **deliver** — the cron/delivery layer reads pending questions, posts them
   alongside the report, and marks them `delivered`. No generation happens here;
   the layer is pure read + mark.
3. **ingest** — when the user replies, record the raw answer on the tape as an
   `echo_raw_answer` record before any interpretation.
4. **distill** — before the next run, read yesterday's `echo_raw_answer`
   records, call `apply_answer`, and mark the questions `answered`. Any
   `delivered` questions without a raw answer are marked `expired` and count
   toward the ignored limit.

### Rules

- **Evidence-backed**: every question cites tape evidence (e.g. "3 items about
  'quantum' appeared today").
- **One-word answer**: questions must be answerable with yes / no / skip /
  silence.
- **Polite backoff**:
  - Maximum 2 questions per day.
  - After 3 consecutive unanswered questions, pause for 3 days.
  - The user can silence ECHO permanently with the answer `silence`.

### Example questions

- "Add 'quantum' as a keyword? (appeared in 3 items today)"
- "Filter 'sponsored' as a negative? (appeared twice this week)"

### Tape record types

| type | fields |
|------|--------|
| `echo_state` | `consecutive_ignored`, `silenced`, `last_prepare_date`, `daily_count` |
| `echo_question` | `id`, `date`, `topic`, `question`, `evidence`, `status` (`pending`/`delivered`/`answered`/`expired`) |
| `echo_delivery` | `date`, `question_ids`, `channel`, `message_id` |
| `echo_raw_answer` | `date`, `question_id`, `answer_text` |
| `echo_answer` | `question_id`, `answer`, `applied_ops`, `profile_version` |

### Reference API

```python
from engine.echo import prepare, record_delivery, record_raw_answer, distill, apply_answer, enable

# 1. Prepare today's questions after publish.
questions = prepare("tech")

# 2. Deliver them (caller's responsibility to post to the channel).
question_ids = [q["id"] for q in questions]
record_delivery("tech", question_ids, channel="#daily", message_id="msg-123")

# 3. Ingest a raw answer when the user replies.
record_raw_answer("tech", question_ids[0], "yes")

# 4. Distill answers into profile operations before the next run.
distill("tech")

# Re-enable after silence.
enable("tech")
```

---

## 9. Why this matters

Static filters drift. One-shot LLMs hallucinate and ignore date windows. This skill separates **deterministic bookkeeping** (scan, URL normalization, dedup, tape) from **judgment** (LLM review, feedback parsing) so that:

- Every decision is auditable.
- Every rejection is a training signal.
- The engine's taste evolves with the user's priorities.

---

## 9. License

MIT. See [LICENSE](LICENSE).
