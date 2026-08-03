# Sample Issue — Tech Vertical, 2026-08-04

This page shows what a real daily report looks like and, more importantly, **why each item was selected**. Every decision below is backed by a record in the append-only tape.

> The full tape for this sample is available in [`tape/tech.jsonl`](../tape/tech.jsonl) after running the reference implementation.

---

## Engine configuration

```toml
[vertical]
name = "tech"
keywords = [
  { term = "AI", weight = 3 },
  { term = "quantum", weight = 3 },
  { term = "open source", weight = 2 },
  { term = "security", weight = 2 },
]
negatives = [
  { term = "sponsored", weight = 4 },
  { term = "careers", weight = 4 },
  { term = "webinar", weight = 3 },
]
categories = [
  { name = "policy", bonus = 2 },
  { name = "safety", bonus = 2 },
]
```

Sources: Hacker News RSS, Ars Technica RSS.

---

## Today's report

### 1. OpenAI publishes new safety framework

- **Main source:** Ars Technica — `https://arstechnica.com/ai/2026/08/openai-publishes-new-safety-framework/`
- **Related sources:** The Verge, TechCrunch (clustered by title simhash)
- **Tape decision chain:**
  1. **Scan:** New URL on Ars Technica front page at 08:14 UTC.
  2. **URL normalize:** Dropped `?amp=1` fragment → `url_norm` stored.
  3. **Prescreen:** Matched keywords `AI` (+3) and `safety` category (+2) → score **5**, passed.
  4. **Review:** LLM confirmed `is_news=true`, `is_ad=false`, `vertical_fit=0.92`.
  5. **Dedup:** Simhash clustered with 2 related sources; selected as main item because it had the highest score.
- **Why it matters:** Demonstrates the three gates working together — cheap rule gate catches the topic, strict LLM gate confirms quality, dedup gate collapses three sources into one entry.

---

### 2. Linux kernel patch fixes decade-old TCP bug

- **Main source:** Hacker News — `https://news.ycombinator.com/item?id=44445555`
- **Tape decision chain:**
  1. **Scan:** New on HN front page at 09:02 UTC.
  2. **Prescreen:** Matched `security` (+2) and `open source` (+2) → score **4**, passed.
  3. **Review:** LLM confirmed `is_news=true`, `vertical_fit=0.88`.
  4. **Dedup:** No URL or simhash match in the last 14 days → new cluster.
- **Why it matters:** Shows how broad terms like "security" and "open source" surface high-signal engineering news without requiring every possible keyword.

---

### 3. Startup claims quantum breakthrough; experts are skeptical

- **Main source:** Hacker News — `https://news.ycombinator.com/item?id=44446666`
- **Tape decision chain:**
  1. **Scan:** New on HN front page at 10:21 UTC.
  2. **Prescreen:** Matched `quantum` (+3) → score **3**, passed.
  3. **Review:** LLM flagged `vertical_fit=0.71`, noted skepticism in title.
  4. **Dedup:** New cluster.
- **Why it matters:** A lower-fit item still makes the report because the prescreen gate was wide enough to let it through. The reflection loop can later learn whether the user wants more or less quantum hype.

---

## What got rejected (and why)

| Title | Stage | Reason | Learning signal |
|-------|-------|--------|-----------------|
| "10x engineer hiring guide" | prescreen | `low_score` (matched `careers` negative, no positives) | Confirms negative list is working |
| "Sponsored: best cloud GPUs" | prescreen | `low_score` (matched `sponsored` negative) | Negative term is effective |
| "Register for our AI webinar" | prescreen | `low_score` (matched `webinar` negative) | User does not want event marketing |
| "Apple releases iOS 27 beta" | review | `low_fit` | Too product-launch focused for this vertical |

Rejected items are still in the tape. If the user later says "actually include Apple releases", the reflection loop can recheck these exact items.

---

## ECHO question of the day

> "Add 'Apple' as a keyword? (appeared in 2 items today, both rejected as low_fit)"

User answers: `no`.

Result: `Apple` is added to the negative list with weight 2; an `evolution` record is written; the profile version bumps from `v3` to `v4`.

---

## Status footer

```
Sources scanned: 2
Items prescreened: 12
Rejected at prescreen: 6
Verified by LLM: 6
Pooled after dedup: 3
Source health: all green
Pipeline time: 4.2s
```

---

## Compare with a static RSS reader

A static RSS reader would have shown all 12 items, including the sponsored post and the careers guide. A one-shot LLM summarizer might have missed the quantum story because it was not explicitly asked about it.

This engine reports 3 high-signal items, explains why each made it, and uses the rejections to get better tomorrow.
