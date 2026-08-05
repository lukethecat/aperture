# How it works

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

The spec in [SKILL.md](../SKILL.md) is implementation-agnostic: run it with the included Python reference implementation, port it to your own stack, or hand it to an agent as-is.

## Further reading

- **Understand the system** → [SKILL.md](../SKILL.md) (start here)
- **Design rationale** → [DESIGN.md](../DESIGN.md)
- **Install as an agent skill** → [installing-for-agents.md](installing-for-agents.md)
- **Replay any decision** → `python scripts/replay.py --item <id>`
- **Adapt it to your beat** → copy [config/example_vertical.toml](../config/example_vertical.toml), edit sources, keywords, and negatives
