# Installing Aperture as an agent skill

Aperture is designed as a **skill for AI agents**. An agent that loads this skill can produce better daily reports by scanning front pages, filtering noise, deduplicating stories, and learning from user feedback — while keeping every decision auditable in an append-only tape.

This guide covers installation on common agent runtimes.

---

## What the agent gets

After installation, the agent can:

- Run `python -m engine.pipeline --dry --vertical tech` to produce a rule-only daily report.
- Read `SKILL.md` as the canonical execution spec.
- Use `agent_runner.py` as an agent-orchestrated loop that decides collect → edit → review → publish stages.
- Use `scripts/replay.py --item <id>` or `scripts/replay.py --why <url>` to answer "why was this selected?"

---

## Generic install (any agent with shell access)

```bash
# 1. Clone the repository into a skills directory
git clone https://github.com/lukethecat/aperture.git ~/.skills/aperture
cd ~/.skills/aperture

# 2. Verify Python 3.11+ is available
python --version

# 3. Run a smoke test
python tests/test_smoke.py -v

# 4. Produce a rule-only daily report
python -m engine.pipeline --dry --vertical tech --config config/example_vertical.toml

# 5. (Optional) Set an OpenAI-compatible provider for LLM review
export APERTURE_LLM_API_KEY="sk-..."
python -m engine.pipeline --vertical tech --config config/example_vertical.toml
```

Tell the agent to read `SKILL.md` first. It contains the full execution pattern.

### Windows/Git Bash note

If you see `UnicodeDecodeError: 'gbk' codec can't decode byte ...` while running the pipeline or `scripts/replay.py` on Windows with Git Bash, set the console encoding to UTF-8 before running Python:

```bash
export PYTHONIOENCODING=utf-8
python -m engine.pipeline --dry --vertical tech --config config/example_vertical.toml
```

---

## OpenClaw

OpenClaw loads skills from `~/.openclaw/skills/<skill-name>/`.

```bash
mkdir -p ~/.openclaw/skills/aperture
git clone https://github.com/lukethecat/aperture.git ~/.openclaw/skills/aperture
```

Create `~/.openclaw/skills/aperture/skill.md` as the entry point (or symlink `SKILL.md`):

```bash
ln -s ~/.openclaw/skills/aperture/SKILL.md ~/.openclaw/skills/aperture/skill.md
```

Configure the provider in your OpenClaw settings if you want LLM review:

```toml
[skills.aperture]
env = { APERTURE_LLM_API_KEY = "sk-..." }
```

Verify:

```bash
openclaw run aperture "produce a tech daily report in dry mode"
```

---

## Raft

In a Raft workspace, place the skill in the agent's project directory and expose `SKILL.md` as the entry point.

```bash
cd /path/to/agent/workspace
mkdir -p skills
git clone https://github.com/lukethecat/aperture.git skills/aperture
```

Point the agent at `skills/aperture/SKILL.md` as a loaded skill. The agent can then:

- Run `python skills/aperture/agent_runner.py --dry --vertical tech` for an agent-orchestrated loop.
- Run `python skills/aperture/scripts/replay.py --item <id>` to inspect decisions.

---

## Hermes

Hermes looks for skills under `~/.hermes/skills/`.

```bash
mkdir -p ~/.hermes/skills
git clone https://github.com/lukethecat/aperture.git ~/.hermes/skills/aperture
```

Add to your Hermes gateway configuration so the skill is available to agents:

```yaml
skills:
  - name: aperture
    path: ~/.hermes/skills/aperture
    entry: SKILL.md
```

Verify:

```bash
hermes skill run aperture --prompt "run a dry tech daily report"
```

---

## Claude Code

Claude Code can load skills from `~/.claude/skills/`.

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/lukethecat/aperture.git ~/.claude/skills/aperture
```

When you start Claude Code in a project, reference the skill:

```bash
claude --skill aperture
```

Then ask:

```
Run Aperture in dry mode for the tech vertical and show me the report.
```

---

## Codex

Codex loads skills from `~/.codex/skills/`.

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/lukethecat/aperture.git ~/.codex/skills/aperture
```

The agent will read `~/.codex/skills/aperture/SKILL.md` and can execute:

```bash
python ~/.codex/skills/aperture/agent_runner.py --dry --vertical tech
```

---

## Skill invocation patterns

Once installed, the agent should follow this loop:

1. **Load the skill** — read `SKILL.md`.
2. **Configure a vertical** — copy `config/example_vertical.toml` and edit sources, keywords, categories, and negatives.
3. **Run** — execute the pipeline in dry mode first, then with an LLM provider if desired.
4. **Inspect** — use `scripts/replay.py` to explain any decision.
5. **Evolve** — apply user feedback with `engine.feedback.apply_feedback(...)` and let the profile learn.

---

## Verification checklist

After installation, confirm:

- [ ] `python tests/test_smoke.py -v` passes.
- [ ] `python -m engine.pipeline --dry --vertical tech --config config/example_vertical.toml` produces a report.
- [ ] `python scripts/replay.py --item <id-from-report>` shows a decision chain.

If all three pass, the skill is ready for the agent to use.
