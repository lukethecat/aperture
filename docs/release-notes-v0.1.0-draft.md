> Draft release notes for owner review. Do not publish until approved.

## Aperture v0.1.0 — A skill for AI agents that curate better daily reports

Aperture is a deterministic, auditable news-curation skill for AI agents. It replaces stateless RSS readers and one-shot LLM summarizers with a four-stage pipeline that remembers yesterday, learns from feedback, and can explain every decision.

### What you get

- **Scan the front page** — diff each source's list page against yesterday's snapshot. Robust where timestamps are unreliable.
- **Tape every decision** — every source snapshot, item, rejection reason, profile version, and report is append-only JSONL.
- **Prescreen with taste** — weighted keywords, category bonuses, and negative terms; cheap and deterministic.
- **LLM review** — optional second pass for news verification, on-topic scoring, and summarization.
- **Deduplicate by meaning** — URL normalization + title simhash clustering collapse the same event across feeds.
- **Learn from feedback, reversibly** — user feedback becomes versioned profile operations; roll back any change.
- **Rule-only dry mode** — run the entire pipeline without an LLM API key.
- **Agent-native** — `SKILL.md` is the spec; `agent_runner.py` shows an LLM agent driving the pipeline directly.

### Install

```bash
git clone https://github.com/lukethecat/aperture.git
cd aperture
python -m engine.pipeline --dry --vertical tech --config config/example_vertical.toml
```

Or install it as a skill into OpenClaw, Raft, Hermes, Claude Code, or Codex — see [`docs/installing-for-agents.md`](docs/installing-for-agents.md).

### Explore

- Read the skill spec: [`SKILL.md`](SKILL.md)
- See a real daily issue: [`docs/sample-issue.md`](docs/sample-issue.md)
- Replay any decision: `python scripts/replay.py --item <id>`
- 60-second demo: `python scripts/demo_60s.py`

### Assets

- Source code (tar.gz)
- Source code (zip)

### Full changelog

See [`CHANGELOG.md`](CHANGELOG.md).
