:root {
  --bg: #0d1117;
  --fg: #c9d1d9;
  --accent: #58a6ff;
  --code: #161b22;
  --border: #30363d;
}

body {
  background: var(--bg);
  color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  line-height: 1.6;
  max-width: 880px;
  margin: 0 auto;
  padding: 32px;
}

h1, h2, h3 { color: #f0f6fc; }
h1 { border-bottom: 1px solid var(--border); padding-bottom: 12px; }
hr { border: 0; border-top: 1px solid var(--border); margin: 24px 0; }
code, pre { background: var(--code); border-radius: 6px; }
pre { padding: 16px; overflow-x: auto; }
code { padding: 2px 6px; font-size: 0.92em; }
a { color: var(--accent); text-decoration: none; }
table { border-collapse: collapse; width: 100%; margin: 16px 0; }
th, td { border: 1px solid var(--border); padding: 8px 12px; text-align: left; }
th { background: var(--code); }

# Skill: Self-Evolving News Engine

> **TL;DR** — A deterministic news-curation skill: scan source front pages, diff them against yesterday, prescreen with a weighted profile, review with an LLM, deduplicate, publish, and evolve the profile from user feedback. All decisions go to an append-only tape.

This skill is **implementation-agnostic**. You can execute it with the included Python reference implementation, with your own code, or directly as an LLM agent pattern.

---

## 1. Purpose

Replace static RSS readers and one-shot LLM summarizers with a **self-evolving news pipeline** that:

1. Treats "reading the front page" as a first-class operation (not just feed polling).
2. Records every decision in an append-only log (the **tape**) for audit and replay.
3. Updates its own taste through explicit user feedback (the **reflection loop**).

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

A source can be acquired in five ways. The engine treats them uniformly once they reach the tape.

| Type | Mechanism | When to use |
|------|-----------|-------------|
| **pull** | RSS/API/curl on cron | Stable feeds and APIs |
| **scan** | Frontpage diff + prescreen | SPAs, irregular sites, human-fed links |
| **push** | Webhook/SSE/bridge | Internal alerts or closed ecosystems |
| **search** | Ad-hoc search | New-source discovery or major-event catch-up |
| **human-feed** | User drops a link | Exclusive tips and first-hand signals |

Add a source by registering `{id, name, list_url, extract_profile}` in the vertical config.

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
export SENE_LLM_API_KEY="sk-..."
python -m engine.pipeline --vertical tech --config config/example_vertical.toml

# Apply feedback
python -c "from engine.feedback import apply_feedback; apply_feedback('More AI safety, fewer ads', 'tech')"
```

---

## 8. ECHO — proactive clarification

ECHO is an optional proactive layer that asks the user up to two one-word
clarification questions after each report. It turns passive readers into active
profile trainers.

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

### Execution steps

1. After `publish`, load today's pooled items.
2. Extract frequent capitalized noun phrases that are not already in the profile.
3. Filter for terms that appear at least twice.
4. Check rate limits and silence state.
5. Generate up to 2 questions, record them on the tape as `echo_question`.
6. Present questions to the user; record answers as `echo_answer`.
7. Apply positive answers as `add_keyword` and negative answers as
   `add_negative`, then reset the ignored counter.

### Reference API

```python
from engine.echo import ask, apply_answer, enable

questions = ask("tech")
for q in questions:
    print(q["question"])

apply_answer(q["id"], "tech", "yes")   # adds topic as keyword
apply_answer(q["id"], "tech", "no")    # adds topic as negative
apply_answer(q["id"], "tech", "silence")  # permanently silences ECHO
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
