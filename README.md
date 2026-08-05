<div align="center">

# aperture

_your agent's daily front page — reads the news like a human, shows you the tape_

[![CI](https://img.shields.io/github/actions/workflow/status/lukethecat/aperture/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/lukethecat/aperture/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/lukethecat/aperture?style=flat-square)](LICENSE)
[![v0.1.0](https://img.shields.io/github/v/release/lukethecat/aperture?style=flat-square)](https://github.com/lukethecat/aperture/releases)

[📄 Real issue · 2026-08-05 →](docs/issues/2026-08-05.md) · [Install](docs/installing-for-agents.md) · [Docs](docs/how-it-works.md)

</div>

Aperture is a skill for AI agents that curate better daily reports. It scans source front pages, diffs them against yesterday, prescreens with a weighted profile, reviews with an LLM, deduplicates, publishes, and learns from feedback. Every decision goes to an append-only tape for audit and replay.

1. **Scan front pages like a human.** Aperture diffs each source's front page against yesterday's, instead of trusting unreliable feed timestamps.
2. **Tape every decision.** Scans, scores, rejections, profile changes — all append-only JSONL. Ask *"why was #14 cut?"* and the tape answers.
3. **Learn from feedback.** "More AI safety, fewer sponsored posts" becomes versioned profile operations you can roll back and replay.

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
