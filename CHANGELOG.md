# Changelog

All notable changes to Aperture will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-04

### Added
- Initial release of Aperture as an agent-first news-curation skill.
- Four-stage pipeline: collect (scan) → edit (prescreen) → review (LLM) → publish (dedup + report).
- Append-only `tape` JSONL log for every source snapshot, item, profile version, feedback, and report.
- Versioned taste `profile` with weighted keywords, category bonuses, and negative terms.
- Reflection loop that parses user feedback into profile operations and rechecks recent items.
- ECHO proactive clarification layer.
- `--dry` rule-only mode: runs without any LLM API key.
- `scripts/replay.py` to replay any item's full decision chain (`--item`, `--why`).
- `agent_runner.py` LLM-agent orchestration demo.
- `docs/installing-for-agents.md` with platform-specific install steps (OpenClaw, Raft, Hermes, Claude Code, Codex, generic shell agent).
- `docs/when-to-use-aperture.md` usage guide with honest reverse checklist and decision tree.
- Sample issue at `docs/sample-issue.md` generated from real tape output.

[0.1.0]: https://github.com/lukethecat/aperture/releases/tag/v0.1.0
