# Quick start

Requires Python 3.11+ (for `tomllib`; JSON configs work on earlier versions).

```bash
git clone https://github.com/lukethecat/aperture.git
cd aperture

# Rule-only dry run — no LLM, no API key
python -m engine.pipeline --dry --vertical tech --config config/example_vertical.toml

# Full pipeline with LLM review
export APERTURE_LLM_API_KEY="sk-..."
python -m engine.pipeline --vertical tech --config config/example_vertical.toml
```

Tests are offline: `python tests/test_smoke.py -v`

## Replay a decision

No API key needed:

```bash
python scripts/replay.py --item d02fcce3d996 --vertical tech
```

This reconstructs the full decision chain for one pooled item from `tape/sample-tech.jsonl`: when it was scanned, how the URL was normalized, which keywords fired, and why it made the pool.
