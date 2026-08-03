# Module Showcase

Each module in Aperture solves one specific problem in the news curation pipeline. Together they form a deterministic backbone that keeps the expensive judgment layers (LLM review, feedback parsing) honest and auditable.

---

## `tape` — the single source of truth

**One-line pitch:** An append-only JSONL log that remembers every decision, rejection, and profile change so you can replay history months later.

**Key mechanisms:**
- One file per vertical (`tape/{vertical}.jsonl`).
- Every record has `type`, `ts`, and a deterministic schema.
- Records are never mutated; corrections are new records that reference old ones.

**Quantitative edge:**
- 7 record types cover the full lifecycle: `source`, `frontpage`, `profile`, `item`, `report`, `feedback`, `evolution`.
- Rejected items stay in the tape with `reject_reason`, creating a free negative-signal dataset.

**Why it wins:** Most news tools delete rejected items. Here, rejection is the fuel for calibration.

---

## `scanner` — read the front page like a human

**One-line pitch:** Treat "what is new on the front page today" as a more robust signal than parsing unreliable publish dates.

**Key mechanisms:**
- Fetches each source's list page, extracts `{title, url}` pairs.
- Normalizes URLs: drops fragments and tracking params (`utm_*`, `fbclid`), strips trailing slash, lowercases host, forces `https`.
- Diffs against the previous snapshot; only newly appearing URLs become candidates.
- Tracks source health with consecutive failure counts.

**Quantitative edge:**
- Supports 4 extraction methods out of the box: `rss`, `generic_links`, `regex`, `json_api`.
- URL normalization prevents duplicates caused by tracking parameters or `www` vs. bare host.

**Why it wins:** Anti-scraping layouts and inconsistent timestamps break date-based pipelines. Frontpage diff works as long as humans can read the page.

---

## `prescreen` — wide funnel, cheap rules

**One-line pitch:** A zero-token first gate that scores candidates against a weighted profile so the LLM only sees the most relevant items.

**Key mechanisms:**
- `score = sum(keyword weights) + sum(category bonuses) - sum(negative weights)`.
- Whole-word boundary matching for ASCII terms.
- Records `last_hit` for every matched term.
- Rejected candidates are written to tape as `stage: rejected`, `reject_reason: low_score`.

**Quantitative edge:**
- Runs entirely offline; no API cost.
- Threshold is configurable; default `score >= 2` keeps the funnel wide.

**Why it wins:** It separates "cheap filtering" from "expensive judgment", cutting LLM token usage and keeping the system explainable.

---

## `verifier` — structured second pass

**One-line pitch:** An LLM review step that asks the same structured questions for every item, so hallucinations are easier to catch and correct.

**Key mechanisms:**
- Sorts prescreened items by score and caps per-source representation.
- Fetches article text and extracts publish date through a fallback chain (`JSON-LD`, `meta article:published_time`).
- Prompts the LLM for: `is_news`, `is_ad`, `is_job`, `vertical_fit`, `summary`.
- Rejects with explicit reasons: `not_news`, `is_ad`, `is_job`, `low_fit`.

**Quantitative edge:**
- Provider-agnostic: works with any OpenAI-compatible endpoint or a custom callable.
- Falls back to rule-only `--dry` mode when no provider is configured.

**Why it wins:** Most LLM summarizers mix selection and generation in one prompt. This pipeline separates verification from writing, so you can audit why something was rejected without re-running the model.

---

## `dedup` — one event, one entry

**One-line pitch:** Two-level deduplication that collapses the same story across multiple sources without requiring exact URLs.

**Key mechanisms:**
- Level 1: exact `url_norm` match.
- Level 2: title `simhash` clustering with hamming distance ≤ 3.
- Clusters keep the highest-scored item as the main item; related sources become alternatives.

**Quantitative edge:**
- `simhash` catches reworded headlines about the same event.
- Hamming distance threshold is configurable per vertical.

**Why it wins:** Readers do not need to see "Company X raises $50M" five times from five feeds. The engine reports it once with all sources attached.

---

## `report` — the readable daily digest

**One-line pitch:** Formats clusters into a daily summary and appends a status footer that tells you what the engine did, not just what it found.

**Key mechanisms:**
- Sorts clusters by source count and profile score.
- Generates a status footer: sources scanned, items prescreened, rejected, pooled, source health alerts, stage timings.
- Writes a `report` record to the tape for reproducibility.

**Quantitative edge:**
- Footer exposes operational health, not just output.
- Report format is swappable: replace `report.generate_report` to produce Markdown, email, Slack, etc.

**Why it wins:** You can look at any past report and know exactly which sources were healthy, how many items were filtered at each stage, and how long each stage took.

---

## `profile` + `feedback` — taste that evolves

**One-line pitch:** Your feedback becomes versioned profile operations, so the engine's taste changes deliberately and can be rolled back.

**Key mechanisms:**
- Feedback is parsed into ops: `add_keyword`, `adjust_weight`, `remove_keyword`, `add_negative`, `adjust_negative_weight`, `remove_negative`.
- Profile version bumps with every change; an `evolution` record is written.
- Recently pooled items are rechecked against the new profile.
- Decay rule: `origin: learned` terms that do not hit for 30 days lose weight; `origin: manual` terms never auto-delete.

**Quantitative edge:**
- Every preference change is auditable (`from_version` → `to_version`).
- Negative feedback (`fewer sponsored posts`) is as actionable as positive feedback.

**Why it wins:** Static filters drift. One-shot prompts forget. A versioned profile makes preference evolution a first-class feature.

---

## `echo` — proactive one-word calibration

**One-line pitch:** Turns passive readers into active trainers by asking up to two one-word questions after each report.

**Key mechanisms:**
- Extracts frequent noun phrases from today's pooled items.
- Asks evidence-backed questions like "Add 'quantum' as a keyword? (appeared in 3 items today)".
- Answers: `yes`, `no`, `skip`, `silence`.
- Rate limits: max 2 questions/day; 3 ignored questions trigger a 3-day pause.

**Quantitative edge:**
- Questions are backed by tape evidence, not guesses.
- `silence` permanently disables ECHO; user consent is respected.

**Why it wins:** Most systems wait for users to write feedback. ECHO meets them where they are — one word at a time.
