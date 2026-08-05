# Why Aperture

## The problem with AI news tools today

Most of them are **stateless prompt wrappers**: they search, summarize, and forget. The same stories reappear every day, the same event shows up five times across five feeds, and telling the tool "less crypto, more AI safety" changes nothing.

Aperture is different: it remembers everything, learns from your feedback, and can explain itself.

## What you get

| Without Aperture | With Aperture |
|------------------|---------------|
| The same funding round summarized 5 times, across 5 feeds | One event, one entry — deduplicated by meaning |
| "Why did it pick this?" — no answer | A full tape record: scan → score → review → cluster |
| "Less crypto" — and tomorrow, more crypto | A versioned taste profile that actually evolves, and rolls back |
| A wall of notifications | ECHO: one-word questions, only when there's evidence |
| Needs an LLM API key to do anything | Rule-only dry mode runs with zero keys |

## Three ideas that matter

1. **Scan the front page, not the timestamp.** Aperture diffs each source's front page against yesterday's — because "new on the front page" is what an editor would notice, and it's a far more robust signal than the unreliable publish dates feeds give you.
2. **Tape everything.** Every source snapshot, item, rejection reason, profile version, and report goes into an append-only JSONL tape. Nothing is silently dropped: rejected items are fuel for calibration. Ask *"why was #14 cut?"* — the tape answers.
3. **Learn from feedback, reversibly.** "More AI safety, fewer sponsored posts" becomes versioned profile operations — not a re-prompt. Roll back any change and replay what would have been filtered.

Aperture is also AI-native: [SKILL.md](../SKILL.md) is the primary spec, executable directly as an LLM-agent pattern, and [`agent_runner.py`](../agent_runner.py) is a working agent-orchestrated loop. And it degrades gracefully — `--dry` runs the whole pipeline on rules alone, no API key needed.

## See it

- [Real daily issue, 2026-08-05](issues/2026-08-05.md)
- [Annotated sample issue](sample-issue.md)
- [When is this the right tool?](when-to-use-aperture.md)
- [Module-by-module advantages](module-showcase.md)
