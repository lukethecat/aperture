<div align="center">

# aperture

_your agent's daily front page — reads the news like a human, shows you the tape_

[![CI](https://img.shields.io/github/actions/workflow/status/lukethecat/aperture/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/lukethecat/aperture/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/lukethecat/aperture?style=flat-square)](LICENSE)
[![v0.1.0](https://img.shields.io/github/v/release/lukethecat/aperture?style=flat-square)](https://github.com/lukethecat/aperture/releases)

[📄 Real issue · 2026-08-06 →](docs/issues/2026-08-06.md) · [Install](docs/installing-for-agents.md) · [Docs](docs/how-it-works.md)

</div>

Aperture is a skill for AI agents that curate better daily reports. It scans source front pages, diffs them against yesterday, prescreens with a weighted profile, reviews with an LLM, deduplicates, publishes, and learns from feedback. Every decision goes to an append-only tape for audit and replay.

## Highlights

Control surfaces that make Aperture different from a static RSS aggregator:

- **Scan — front pages, not just feeds.** Diffs each source's front page against yesterday and uses `missing_date_policy: include` for sites with no RSS. *Verified: Qwen Blog scan source; 36h window bug fixed after first live run.*
- **Decide — tape every decision.** Scans, scores, rejections, and profile changes are append-only JSONL. `scripts/replay.py --item <id>` shows the full chain. *Verified: replay harness passes; you can ask why any item was cut.*
- **Learn — feedback-driven profile evolution.** ECHO loop turns "more AI safety, fewer sponsored posts" into versioned profile operations that can be rolled back or replayed. *Verified: end-to-end ECHO harness passes.*
- **Prove — source registry + bottom status.** Every issue ends with a registry showing pull / scan / human-feed sources and 🟢⚪🔴 health, plus a status bar tracing how the issue was produced. *Verified: today's issue shows Qwen scan and Owner Tips human-feed badges.*
- **Stats — runtime funnel transparency.** Each issue exposes the full pipeline funnel (sources → scanned → prescreened → report) and timing per stage, so readers can see exactly how the front page was produced. *Verified: today's issue includes source/scanned/prescreened/report counts and stage durations.*

## Real output

Daily issues are committed to [`docs/issues/`](docs/issues/) as dogfooding evidence. The [latest issue →](docs/issues/2026-08-06.md) includes source registry status and tape references.

---

<details>
<summary>Project structure</summary>

```
aperture/
├── SKILL.md                 # primary skill specification
├── scripts/
│   ├── replay.py            # replay any item's decision chain
│   └── harness_*.py         # harness tests for sample issue / window / echo
├── DESIGN.md                # design rationale
├── engine/                  # deterministic reference implementation
├── config/                  # example vertical configs
├── docs/                    # deep dives, sample issue, install guides
└── tests/                   # offline smoke tests
```

</details>

## Documentation

- [Why Aperture](docs/why-aperture.md) — the problem with stateless news tools, and what changes
- [How it works](docs/how-it-works.md) — pipeline, tape, and the implementation-agnostic spec
- [Quick start](docs/quickstart.md) — dry run with zero keys, full pipeline, replay a decision

---

## Acknowledgments

The append-only **tape** design is inspired by [bub](https://github.com/bubbuild/bub), a hook-first, tape-driven agent framework.

## License

MIT
