# Design Notes

## Two core principles

1. **Prescreen wide, review strict, pool with dedup.**
   Precision comes from the second-pass review and deduplication, not from an
   over-tight first filter. The first stage is cheap and rules-based; the
   second stage can use an LLM; the pool stage collapses duplicates so the
   final report stays readable.

2. **Everything goes to the tape, append-only.**
   The tape is the single source of truth. Source snapshots, items at every
   stage, profile versions, evolution records, feedback, and reports are all
   stored as JSONL lines. This makes the system debuggable, auditable, and
   replayable months later.

## Four-stage pipeline: collect → edit → review → publish

### collect (scanner)

For each configured source, fetch its list page, extract titles and URLs,
normalize URLs, and diff against the previous snapshot. Only newly appearing
URLs become candidates.

Why diff against the frontpage instead of parsing publish times? Because a
frontpage diff is robust across sources with inconsistent timestamps or
anti-scraping layouts.

### edit (prescreen)

Score each candidate with a simple rule:

```
score = sum(matched keyword weights)
      + category-match bonuses
      - sum(matched negative weights)
```

Candidates below the threshold are rejected with `reject_reason=low_score`,
but still written to the tape. Those rejected records are the negative samples
that make reflection possible.

### review (verifier)

A second pass checks whether prescreened items are real news, on-topic, and
not ads/jobs. This stage calls an LLM through a provider interface. Without a
provider the pipeline can skip this step (dry mode) or treat prescreened items
as verified.

### publish (dedup + report)

Two-level deduplication:

1. Exact `url_norm` match.
2. Title `simhash` clustering: hamming distance ≤ 3 means the same event.

Each cluster keeps the highest-scored item as the main item; related sources
are recorded as alternatives. The report stage formats clusters into a daily
summary and appends a status footer.

## Reflection loop

Feedback from the user is parsed into profile operations (`add_keyword`,
`adjust_weight`, etc.). The profile version is bumped, an evolution record is
written, and recently pooled items are rechecked so the user can see whether
the new profile would have filtered them.

Learned keywords that do not hit for a configurable period are decayed;
manual keywords are never auto-deleted.

## ECHO — proactive clarification

An optional layer that asks the user up to two one-word clarification questions
after each report, backed by tape evidence. Positive answers add keywords;
negative answers add negative terms. ECHO respects rate limits and can be
silenced by the user.

This turns passive readers into active profile trainers without forcing them
to write full feedback queries.

## Source-acquisition taxonomy

Sources can be acquired in five ways, but the engine treats them uniformly
once they land on the tape:

| type | mechanism | example |
|---|---|---|
| pull | RSS/API/curl on cron | RSS feeds |
| scan | frontpage diff + keyword prescreen | SPA or irregular sites |
| push | webhook/SSE/bridge | internal alerts |
| search | ad-hoc search for new leads | major-event catch-up |
| human-feed | user drops a link | exclusive tips |

The engine only needs a `list_url` and an `extract_profile`. How the HTML
arrives is a source-level concern.

## Why stdlib-only

The open-source core avoids external dependencies so it can be dropped into
any Python environment without resolving a dependency tree. LLM interaction
uses `urllib` against a configurable endpoint. Extraction uses regex and
simple HTML parsing rather than full DOM libraries.

## Extending the engine

- New vertical: add a config file; no engine changes.
- New source method: add a handler in `scanner.extract_items`.
- New LLM backend: implement a provider callable and point
  `APERTURE_LLM_PROVIDER` to it (the legacy `SENE_LLM_PROVIDER` name still works).
- New report format: replace or extend `report.generate_report`.
