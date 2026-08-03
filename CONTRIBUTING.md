# Contributing

Thanks for considering a contribution. This project is intentionally small and opinionated; the goal is to keep the core skill easy to understand, audit, and adapt.

## Project values

1. **Skill-first.** `SKILL.md` is the primary specification. Code changes should be explainable in terms of the skill steps.
2. **Determinism first.** Date windows, URL normalization, dedup, and tape writes must be deterministic. LLM judgment is wrapped, not trusted.
3. **No source lock-in.** The core must not depend on any specific news source, domestic source, or paid API beyond an optional LLM provider.
4. **English only.** All user-facing docs, comments, commit messages, and variable names are in English.

## How to contribute

1. Open an issue first for significant changes.
2. Fork the repo and create a branch.
3. Make your change.
4. Run the checks below.
5. Open a pull request with a clear description and a reference to the issue.

## Local checks

```bash
# Run tests
python -m pytest tests/test_smoke.py -v

# Run the pipeline in dry mode
python -m engine.pipeline --dry --vertical tech --config config/example_vertical.toml

# Check for non-ASCII characters in source files (excluding SVG assets)
python -c "import pathlib, sys; bad=[p for p in pathlib.Path('.').rglob('*') if p.is_file() and p.suffix in {'.py','.md','.toml'} and any(ord(c)>127 for c in p.read_text(encoding='utf-8'))]; print('FAIL:', bad) if bad else print('OK')"
```

## What to avoid

- Adding heavy dependencies. The core reference implementation uses the Python standard library.
- Bundling real news sources that cannot be publicly scraped or that introduce legal/policy risk.
- Mutating tape records. The tape is append-only.

## Questions?

Open a discussion issue or comment on an existing one.
