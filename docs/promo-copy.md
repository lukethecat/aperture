# Aperture promotional copy

Ready-to-post versions for Hacker News, Reddit, X (Twitter), and 掘金.

Core positioning: **Aperture is a skill that helps AI agents produce better daily reports — and discover more of what you actually want.**

---

## Hacker News

**Title:** Show HN: Aperture — a skill that helps AI agents curate better daily reports

**Body:**
https://github.com/lukethecat/aperture

Most AI agents that produce daily reports are stateless: they search, summarize, and forget. The same stories reappear, the same event shows up five times across feeds, and telling the agent "less crypto, more AI safety" changes nothing.

Aperture is a deterministic skill for agents that:
- Reads front pages like a human — diffs them against yesterday instead of trusting unreliable publish dates.
- Tapes every decision — every source snapshot, item, rejection reason, profile version, and report is append-only JSONL.
- Learns from feedback — "more AI safety, fewer sponsored posts" becomes versioned profile operations the agent can roll back.
- Explains itself — `scripts/replay.py --item <id>` shows why any story made or missed the cut.

Install it into any agent that can run shell commands, or read `SKILL.md` and execute the pattern directly. It runs rule-only (`--dry`) without an LLM, or plugs into any OpenAI-compatible provider. MIT licensed.

---

## Reddit

**Title:** [OC] Aperture — a skill for AI agents that curates news like a human

**Body:**
Repo: https://github.com/lukethecat/aperture

Aperture is a skill you install into an AI agent to make its daily reports better:
- Scans source front pages and diffs them like a human checking a newspaper.
- Prescreens with a weighted keyword/category/negative-word profile.
- Reviews with an LLM provider (optional; rule-only mode works too).
- Deduplicates by URL and title simhash clustering.
- Learns from your feedback: "more AI safety, fewer sponsored posts" becomes profile operations, versioned and logged.

Everything is stored in an append-only "tape" (JSONL), so the agent can always answer "why was this selected?" There's also an agent-orchestrated runner (`agent_runner.py`) that reads `SKILL.md` and decides the pipeline stages.

Installation guides for OpenClaw, Raft, Hermes, Claude Code, and Codex are in `docs/installing-for-agents.md`.

MIT licensed, stdlib-only core. Feedback welcome!

---

## X (Twitter) — single post

Your AI agent's daily report is amnesiac: same stories every day, five duplicates of one event, and "less crypto, more AI safety" changes nothing.

Aperture is a skill that helps agents read front pages like a human, dedupe by meaning, learn from feedback, and explain every decision with `replay.py`.

Open source, MIT → github.com/lukethecat/aperture

## X — thread

1/ Pain: Most AI agents that produce daily reports are stateless — no memory of yesterday, no dedup (same event ×5 feeds), no feedback loop. "Less X, more Y" goes nowhere.

2/ Fix: Aperture — a skill agents install to scan front pages like a human, verify before publishing, and turn feedback into a versioned profile they can roll back. Every decision is append-only logged and replayable.

3/ It runs rule-only without an LLM or with any OpenAI-compatible provider. Install guides for OpenClaw, Claude Code, Codex, and more are in the repo. → github.com/lukethecat/aperture

---

## 掘金

**标题：** 开源发布：Aperture —— 一个帮 AI Agent 做更好日报的 Skill

**正文：**
仓库：https://github.com/lukethecat/aperture

Aperture 不是给人手动刷的新闻工具，而是一个给 AI Agent 用的自进化新闻策展 Skill：
- 采编审发四段式：collect（扫版面）→ edit（规则初筛）→ review（LLM 二验）→ publish（去重+日报）
- 反思循环：用户反馈解析成画像操作，画像版本化并写 evolution 日志
- Tape 审计：所有状态 append-only 入 JSONL，可回放任意决策
- 一键解释：`scripts/replay.py --item <id>` 或 `--why <url>` 查为什么入选/未入选
- Agent Native：`SKILL.md` 是主文档，`agent_runner.py` 让 LLM agent 直接驱动流水线
- 多平台安装：OpenClaw / Raft / Hermes / Claude Code / Codex，详见 `docs/installing-for-agents.md`
- 零具体源绑定：示例仅用 Hacker News / Ars Technica RSS
- LLM 供应商配置化：OpenAI 兼容接口，无 key 时 `--dry` 纯规则运行

适合想让 Agent 从"无状态摘要器"升级成可反馈、可审计、可进化的新闻/情报策展系统的团队。MIT 协议，欢迎 Star 和 Issue。
