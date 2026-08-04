# Aperture promotional copy

Ready-to-post versions for Hacker News, Reddit, X (Twitter), and 掘金.

---

## Hacker News

**Title:** Show HN: Aperture — a self-evolving news engine that shows you the tape for every decision

**Body:**
https://github.com/lukethecat/aperture

Most AI news tools are stateless prompt wrappers: they search, summarize, and forget. The same stories reappear, the same event shows up five times, and "less crypto, more AI safety" changes nothing.

Aperture is different:
- Reads front pages like a human — it diffs them against yesterday instead of trusting unreliable publish dates.
- Tapes everything — every source snapshot, item, rejection reason, profile version, and report is append-only JSONL.
- Learns from your feedback — "more AI safety, fewer sponsored posts" becomes versioned profile operations you can roll back.

It runs rule-only (`--dry`) without an LLM, or plugs into any OpenAI-compatible provider. MIT licensed.

---

## Reddit

**Title:** [OC] Aperture — a self-evolving news engine that reads front pages like a human

**Body:**
Repo: https://github.com/lukethecat/aperture

What it does:
- Scans source front pages and diffs them like a human checking a newspaper.
- Prescreens with a weighted keyword/category/negative-word profile.
- Reviews with an LLM provider (optional; rule-only mode works too).
- Deduplicates by URL and title simhash clustering.
- Learns from your feedback: "more AI safety, fewer sponsored posts" becomes profile operations, versioned and logged.

Everything is stored in an append-only "tape" (JSONL), so you can always answer "why was this selected?"

There's also an agent-orchestrated runner (`agent_runner.py`) that reads SKILL.md and decides the pipeline stages.

MIT licensed, stdlib-only core. Feedback welcome!

---

## X (Twitter)

**Single-post version:**

Your AI news digest is amnesiac: same stories every day, five duplicates of one event, and "less crypto, more AI safety" changes nothing.

Aperture reads front pages like a human, dedupes by meaning, learns from your feedback, and logs every decision.

Open source, MIT → github.com/lukethecat/aperture

**Thread version:**

1/ Pain: Most AI news tools are stateless — no memory of yesterday, no dedup (same event ×5 feeds), no feedback loop. "Less X, more Y" goes nowhere.

2/ Fix: Aperture — scans front pages like a human reads a newspaper, verifies before it publishes, and turns your feedback into a versioned profile it can roll back. Every decision is append-only logged.

3/ It's open source, runs rule-only without an LLM or with any OpenAI-compatible provider. → github.com/lukethecat/aperture

---

## 掘金

**标题：** 开源发布：Aperture —— 一套会自我进化的新闻引擎核心

**正文：**
仓库：https://github.com/lukethecat/aperture

核心设计：
- 采编审发四段式：collect（扫版面）→ edit（规则初筛）→ review（LLM 二验）→ publish（去重+日报）
- 反思循环：用户反馈解析成画像操作，画像版本化并写 evolution 日志
- Tape 审计：所有状态 append-only 入 JSONL，可回放任意决策
- Agent Native：SKILL.md 是主文档，`agent_runner.py` 让 LLM agent 直接驱动流水线
- 零具体源绑定：示例仅用 Hacker News / Ars Technica RSS
- LLM 供应商配置化：OpenAI 兼容接口，无 key 时 `--dry` 纯规则运行

适合想从静态摘要器升级成可反馈、可审计的新闻/情报系统的团队。MIT 协议，欢迎 Star 和 Issue。
