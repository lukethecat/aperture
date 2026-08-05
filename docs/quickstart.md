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

## Try it in 60 seconds

No install, no API key — just Python:

```bash
python scripts/demo_60s.py
```

![60 second demo](../assets/demo-60s.png)

The script runs the pipeline in `--dry` mode, prints the latest daily report, and exits. Every decision it shows is also written to `tape/tech.jsonl`.
