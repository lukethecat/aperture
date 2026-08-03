# Self-Evolving News Engine

A minimal, open-source core of a news engine that learns from your feedback.
Unlike static summarizers, it keeps an append-only audit log (tape) of every
decision, so you can always ask: "Why was this item selected?" and "When was
this keyword added, and why?"

## One-sentence positioning

A news engine that evolves its own taste through explicit feedback and full
lifecycle auditing.

## What makes it different

1. **Reflection loop** — User feedback is parsed into profile operations,
   versioned, and logged. The engine's preferences evolve.
2. **Scan mode** — It reads sources like a human reads a newspaper front page:
   scan the front page → keyword prescreen → structured review → pool/dedup.
3. **Tape audit** — Every source snapshot, item, rejection reason, profile
   version, and report is stored in an append-only JSONL log.

> Rejected items are not deleted. Their `reject_reason` is the fuel for
calibration and self-evolution.

## Architecture: collect → edit → review → publish

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

All stages write to the same tape, decoupled from each other. You can replay,
inspect, or debug any step independently.

## Quick start

Requires Python 3.11+ (for `tomllib`; JSON configs work on earlier versions).

```bash
# 1. Configure an LLM provider (optional; dry mode works without it)
export SENE_LLM_API_KEY="sk-..."
export SENE_LLM_BASE_URL="https://api.openai.com/v1"   # default
export SENE_LLM_MODEL="gpt-4o-mini"                    # default: gpt-3.5-turbo

# 2. Run the example vertical in dry mode (no LLM, rule-only)
python -m engine.pipeline --dry --vertical tech --config config/example_vertical.toml

# 3. Run with LLM review
python -m engine.pipeline --vertical tech --config config/example_vertical.toml
```

## Customizing a vertical

Copy `config/example_vertical.toml` and edit:

- `keywords` — terms the vertical cares about, with weights
- `negatives` — terms to penalize
- `categories` — topic bonuses (e.g. policy, security, business)
- `sources` — list of sources with `list_url` and `extract_profile`

The engine ships with generic RSS-based example sources (Hacker News,
Ars Technica). Add your own sources without touching the engine code.

## Provider configuration

The engine talks to LLMs through a provider interface:

- **Default**: OpenAI-compatible `chat/completions` endpoint configured via
  environment variables.
- **Custom**: Set `SENE_LLM_PROVIDER=module.submodule.callable` to any function
  that takes a prompt string and returns parsed JSON.

If no provider is available, the pipeline falls back to rule-only mode
(`--dry`).

## Reflection loop example

After reading a report, tell the engine what you think:

```python
from engine.feedback import apply_feedback

result = apply_feedback("More AI safety stories, fewer sponsored posts", "tech")
print(result["message"])
```

The profile version bumps, an evolution record is written to the tape, and
recently pooled items are rechecked against the new profile.

## Tests

```bash
python -m pytest tests/test_smoke.py
# or
python tests/test_smoke.py
```

All tests are offline.

## Project structure

```
self-evolving-news-engine/
├── README.md
├── LICENSE
├── DESIGN.md
├── engine/
│   ├── __init__.py
│   ├── tape.py          # append-only JSONL audit log
│   ├── profile.py       # versioned interest profile
│   ├── feedback.py      # reflection loop
│   ├── scanner.py       # collect: frontpage scanning + URL normalization
│   ├── prescreen.py     # edit: rule-based scoring
│   ├── verifier.py      # review: LLM provider interface
│   ├── dedup.py         # publish: URL/simhash dedup + clustering
│   ├── report.py        # publish: daily report generation
│   └── pipeline.py      # four-stage orchestration
├── config/
│   └── example_vertical.toml
└── tests/
    └── test_smoke.py
```

## FAQ

**Q: Can I run this without an LLM?**  
A: Yes. `python -m engine.pipeline --dry` runs scan → prescreen → dedup →
report using only rules.

**Q: Does it include any real news sources?**  
A: The example config only uses Hacker News and Ars Technica RSS feeds. No
specific domestic sources are bundled.

**Q: How do I add a new source type?**  
A: Set `extract_profile.method` to one of `rss`, `generic_links`, `regex`, or
`json_api`.

**Q: Where is the state stored?**  
A: In the `tape/` directory, one `.jsonl` file per vertical.

## Acknowledgments

The append-only **tape** design is inspired by [bub](https://github.com/bubbuild/bub) —
a hook-first, tape-driven agent framework that records every decision in an
append-only log and reconstructs context from it. Thank you to the bub
contributors for the elegant idea.

## License

MIT
