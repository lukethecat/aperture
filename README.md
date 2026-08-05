# Aperture

![Aperture one-sheet](assets/one-sheet.png)

[![CI](https://github.com/lukethecat/aperture/actions/workflows/ci.yml/badge.svg)](https://github.com/lukethecat/aperture/actions/workflows/ci.yml)

A self-evolving news engine that reads front pages like a human — and can show you the tape for every decision it makes.

Real output, not a mockup: [daily issue, 2026-08-05](docs/issues/2026-08-05.md) — every selection is backed by an append-only tape record.

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
├── assets/                  # logo, banner, social card, one-sheet
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
