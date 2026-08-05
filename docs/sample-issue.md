# Sample Issue — Aperture Daily Report

## Latest real issue

Aperture dogfoods its own `ai-frontier` vertical every day. The latest real daily issue is here:

**→ [docs/issues/2026-08-06.md](issues/2026-08-06.md)** — English sources, English report.

Older issues live in [`docs/issues/`](issues/).

---

## What you are looking at

Aperture's daily reports are not summaries of summaries. Each item carries its full decision chain:

1. **Scan** — when the URL first appeared on the source front page / feed.
2. **Prescreen** — which keywords, categories, and negatives fired and the exact score.
3. **Review** — LLM verification result (or dry-run stub if no provider is configured).
4. **Dedup / cluster** — whether the item was merged with a near-duplicate and why.

Every stage is append-only to the vertical's `tape/*.jsonl`. You can replay any item with `scripts/replay.py --item <id>`.

---

## Illustrated example: tech vertical dry run

The rest of this page shows a real dry-run of the `tech` vertical (`--dry` mode: prescreen and dedup run for real, the LLM review gate is stubbed — `verify.llm_called=false` on every item). Every selection and rejection below is backed by an append-only record in [`tape/sample-tech.jsonl`](../tape/sample-tech.jsonl); you can replay the run end to end from that file.

> Run stats for this issue: 50 items scanned, 64 prescreened, 43 rejected, 7 pooled, 7 formatted.

---

## Engine configuration (profile v1, loaded from config)

- **Keywords:** `AI` (5), `machine learning` (4), `open source` (4), `security` (4), `startup` (3), `Linux` (3)
- **Negatives:** `sponsored` (5), `deals` (3), `review` (2)
- **Category bonuses:** `policy` (+3), `security` (+3), `business` (+2)
- **Sources:** Hacker News RSS, Ars Technica RSS

---

## Today's report

### 1. Devtools must be open source

- **Source:** Hacker News — `https://blog.exe.dev/devtools-must-be-open-source`
- **Tape decision chain:**
  1. **Scan:** New URL on HN RSS at 00:11:00.785 UTC.
  2. **Prescreen:** Matched keyword `open source` (+4) → score **4**, passed.
  3. **Review:** Dry run — LLM gate stubbed, item carried through unverified.
  4. **Dedup/cluster:** No prior URL or simhash match → new cluster `cc78beeb3765`, item is its own main entry.
- **Why it's here:** A single high-weight keyword was enough. The tape records exactly which term fired and its weight, so the decision is explainable without guessing.

---

### 2. What's the largest software project AI can complete on its own?

- **Source:** Hacker News — `https://epoch.ai/MirrorCode`
- **Tape decision chain:**
  1. **Scan:** New URL on HN RSS at 00:11:01.170 UTC.
  2. **URL normalize:** Host lowercased, path lowercased → `url_norm = https://epoch.ai/mirrorcode`.
  3. **Prescreen:** Matched keyword `AI` (+5) → score **5**, passed.
  4. **Review:** Dry run — LLM gate stubbed.
  5. **Dedup/cluster:** New cluster `d02fcce3d996`.
- **Why it's here:** The `AI` keyword is the heaviest term in the profile (weight 5) and drove most of today's pool — visible in the profile's `last_hit` timestamps.

---

### 3. An AI-supervised remote exam went so badly that 58,000 students must retake it

- **Source:** Ars Technica — `https://arstechnica.com/culture/2026/08/an-ai-supervised-remote-exam-went-so-badly-that-58000-students-must-retake-it/`
- **Tape decision chain:**
  1. **Scan:** New URL on Ars Technica RSS at 00:11:01.249 UTC.
  2. **Prescreen:** Matched keyword `AI` (+5) → score **5**, passed. No category bonus, no negatives.
  3. **Review:** Dry run — LLM gate stubbed.
  4. **Dedup/cluster:** New cluster `9be40713503f`.
- **Why it's here:** Keyword match only — no category fired. In a live run, the review gate would be the next check on whether an AI-in-education story fits the vertical; in this dry run the tape shows that check was not exercised.

---

### 4. Defcon's new badge is a security key you can see inside

- **Source:** Ars Technica — `https://arstechnica.com/security/2026/08/defcons-new-badge-is-a-security-key-you-can-see-inside/`
- **Tape decision chain:**
  1. **Scan:** New URL on Ars Technica RSS at 00:11:01.395 UTC.
  2. **Prescreen:** Matched keyword `security` (+4) → score **4**, passed. Note: the `security` *category* did not fire — none of its terms (`vulnerability`, `breach`, `exploit`, `CVE`, `malware`) appear in the title.
  3. **Review:** Dry run — LLM gate stubbed.
  4. **Dedup/cluster:** New cluster `18a19624c95f`.
- **Why it's here:** A clean example of keyword vs. category scoring being recorded separately in the tape — same word, different gates.

The remaining 3 pooled items (`1f66fc2d1745`, `fdb78af59ef8`, `c3f986b171fd`) followed the same chain: single `AI` keyword match, score 5, new cluster each.

---

## What got rejected (and why)

All 43 rejections are in the tape with `stage: rejected` and a machine-readable `reject_reason`. Representative sample:

| Title | Stage | Reason | Learning signal |
|-------|-------|--------|-----------------|
| "Ask HN: Who is hiring? (August 2026)" | prescreen | `low_score` (score 0, no keyword matched) | Recurring HN threads are filtered without needing a negative term |
| "Review: Yes, we're still arguing about Nolan's The Odyssey" | prescreen | `low_score` (score −2, matched negative `review` weight 2) | Negative list is working; `last_hit` on `review` updated in the profile |
| "LLMs reward expertise" | prescreen | `low_score` (score 0, no keyword matched) | Borderline — arguably on-topic, but "LLM" is not a profile keyword |
| "Ten advances in mathematics and theoretical computer science" | prescreen | `low_score` (score 0, no keyword matched) | Correct rejection for this vertical |
| "Windows XP 2002 for the Itanium: Unbridled rage" | prescreen | `low_score` (score 0, no keyword matched) | Correct rejection — retrocomputing is out of scope |
| "Smaller, faster, safer: running Kimi and GLM at scale" | prescreen | `low_score` (score 0, no keyword matched) | Borderline — an LLM-infrastructure story the current keyword set misses |

Rejections stay in the tape. If the reflection loop later adds a keyword, these exact items can be re-evaluated against the new profile.

---

## ECHO question of the day

> "2 of today's rejected items were LLM-infrastructure stories that scored 0 because `LLM` is not a keyword. Add `LLM` with weight 4 to the profile?"

User answers: `yes`.

Result: an `evolution` record is appended to the tape, the keyword is added with `origin: echo`, and the profile version bumps. Tomorrow's prescreen will score these stories instead of dropping them silently.

---

## Status footer

```
Vertical:            tech
Sources scanned:     50 items
Items prescreened:   64
Rejected:            43 (all low_score, prescreen gate)
Pooled after dedup:  7
Formatted:           7
LLM calls:           0 (dry run)
Profile version:     1 (loaded from config)
```

---

## Compare with a static RSS reader

A static RSS reader would have shown all 50+ items, including the hiring thread and the movie review. A one-shot LLM summarizer would give you no record of why anything was included or dropped.

This engine reports 7 items, stores the full decision chain for each — scan timestamp, exact matched terms and weights, review status, cluster assignment — and keeps the 43 rejections on the tape so tomorrow's profile can learn from them.
