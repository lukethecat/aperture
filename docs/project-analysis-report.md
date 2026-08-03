# Independent Improvement Analysis

> This report was produced by github-dev using the project's own documents and code. It follows the eight-question brief prepared for an external model review.

## Executive summary

1. **The three differentiators (reflection loop, scan mode, tape audit) are genuinely scarce** in the open-source news curation space, but the project currently under-sells the *consequence* of those differences. The README explains the mechanism; it does not yet make the reader feel the pain of living without it.
2. **Naming is the highest-leverage near-term decision.** "Self-Evolving News Engine" is accurate but forgettable. **Paperboy** is the strongest candidate because it carries a story, not just a description.
3. **The sample issue is the most persuasive asset the project can build.** A real-looking daily report with visible tape decision chains turns an abstract architecture into proof.
4. **The biggest current weakness is lack of a single, stunning first impression.** The repo is complete and correct, but nothing in the first 10 seconds screams "this is obviously better."
5. **AI Nativeness is claimed but not yet demonstrated.** The project describes an agent harness model; it should ship a minimal agent runner that actually executes SKILL.md steps with an LLM.

---

## 1. Positioning and naming

### Candidate evaluation

| Name | Strength | Weakness | Verdict |
|------|----------|----------|---------|
| Self-Evolving News Engine | Searchable, literal | No story, no emotion, hard to remember | Keep as subtitle, not brand |
| **Paperboy** | Human story, growth metaphor, visualizable, short | Could sound consumer-ish | **Lead candidate** |
| Kiosk | Strong front-page metaphor, pairs with visual identity | Less evolution signal | Runner-up |
| Scoop | Industry term, punchy | Weak link to feedback/auditing | Too narrow |
| Molt | Strongest evolution metaphor | Cold, biological, potentially off-putting | Avoid |

### Recommendation

Use **Paperboy** as the project brand.

- Repo: `lukethecat/paperboy`
- PyPI: `paperboy-engine`
- Display: **Paperboy**
- Subtitle: *A self-evolving news curation engine*

The name works because a paperboy learns a route, remembers preferences, and improves delivery over time — exactly the narrative the project wants.

---

## 2. Differentiation and competitive landscape

### Are the three differentiators still scarce in 2026?

Yes, but with caveats.

**Reflection loop / taste evolution:** Still rare. Most open-source news tools (RSS-Bridge, FreshRSS, Miniflux) use static filters. LLM-based summarizers (e.g., open-source Perplexity clones) are stateless prompt chains. A versioned, auditable profile is genuinely different.

**Scan mode / frontpage diff:** Scarce as a first-class primitive. Many scrapers exist, but few treat "new on the front page" as a robust timestamp replacement and integrate it with dedup and review.

**Tape audit:** The strongest moat. Append-only decision logs are almost nonexistent in consumer or developer news tools. This is the feature that makes the project defensible.

### Closest competitors

| Project | What it does | Our gap vs. them |
|---------|--------------|------------------|
| FreshRSS / Miniflux | Self-hosted RSS reader | We have feedback loops, auditing, and LLM review |
| Hacker News / Reddit (manual) | Human curation | We automate with explainable rules + optional LLM |
| LLM summarizer repos (various) | One-shot summary generation | We separate determinism from judgment and remember state |
| Memos / Obsidian web clipper | Personal knowledge capture | We are a pipeline, not a notebook |

### Key gap table

| Dimension | Static RSS reader | One-shot LLM | Paperboy (this project) |
|-----------|-------------------|--------------|-------------------------|
| Remembers yesterday | No | No | Yes (tape) |
| Explains why an item was selected | No | Sometimes | Yes (tape chain) |
| Learns from feedback | No | No | Yes (reflection loop) |
| Avoids duplicate events | No | Poorly | Yes (simhash) |
| Works without LLM API key | Yes | No | Yes (dry mode) |

---

## 3. Critical weaknesses

1. **No "wow" first impression.** The README is correct but not gripping. A visitor scrolling for 10 seconds does not yet see a concrete before/after.
2. **No live demo or recorded run.** A 30-second GIF or terminal cast of a real dry run would convert better than paragraphs.
3. **AI Native is described, not demonstrated.** SKILL.md says an agent can run it, but there is no `agent_runner.py` or example of an LLM actually orchestrating the pipeline.
4. **Sample issue is illustrative, not real.** It uses invented headlines. A sample based on an actual dry-run output would be more credible.
5. **Missing social proof signals.** Zero stars, zero issues, zero discussions. The first external visitor sees a project that looks unloved, even if the code is good.

---

## 4. Sample issue design for maximum impact

### Recommended page structure

```
docs/sample-issue.md
├── Hero section
│   ├── Date and vertical
│   ├── One-sentence summary: "Today the engine read 2 front pages, filtered 50 candidates, and produced 7 high-signal items."
│   └── Link to the actual tape file used
├── "What you would see in a static reader" column
│   └── All 50 raw items (collapsed)
├── "What Paperboy reports" column
│   └── 7 pooled items with decision chains
├── One expanded item
│   ├── Title + source
│   ├── Tape chain: scan → prescreen score → LLM verification → simhash cluster
│   └── Why it beat the alternatives
├── Rejected items (3 examples)
│   ├── Title + stage + reject_reason
│   └── Learning signal
├── ECHO question
│   └── "Add 'quantum' as a keyword? (appeared 3 times today)"
└── Status footer
```

### Concrete improvement

Replace invented headlines with output from a real dry run. Run `python -m engine.pipeline --dry`, pick the top 3 items, and annotate each with its actual tape record IDs. This makes the sample reproducible.

---

## 5. Visual identity: Kandinsky for developers

### Is Kandinsky a plus or minus?

A plus, if executed with restraint. Developers are tired of generic hero illustrations. A bold, geometric identity signals "this project has opinions." But it must not look unprofessional or playful to the point of undermining credibility.

### Recommended visual specification

**Palette:**
- Background: `#0d1117`
- Surface: `#161b22`
- Text: `#f0f6fc` (headings), `#c9d1d9` (body), `#8b949e` (meta)
- Primary red: `#e63946`
- Primary blue: `#58a6ff`
- Primary yellow: `#f4a261`
- Accent line: `#c9d1d9` at 60% opacity

**Geometry:**
- Circles: represent sources / tape records.
- Rectangles: represent pages / front pages.
- Triangles: represent direction / gates.
- Intersecting lines: represent pipeline flow.

**Typography:**
- UI text: system sans-serif (`-apple-system`, `BlinkMacSystemFont`, `Segoe UI`).
- Headings: bold, generous tracking on small caps labels.

**Rules:**
- No gradients.
- No photographs.
- Maximum 4 colors per composition.
- Every shape must map to a system concept (scan, filter, verify, publish, tape).

---

## 6. Growth channels for 2026

Beyond HN/Reddit/X/掘金:

1. **Agent skill marketplaces.** If platforms like Anthropic's Computer Use, OpenAI's GPTs, or Kimi skills allow uploaded instructions, package SKILL.md as a installable skill.
2. **LLM tool directories.** Submit to directories that catalog tools for LLM agents (e.g., MCP server lists, agent tool registries).
3. **Newsletter and podcast outreach.** Niche newsletters about AI/LLM tooling and open source are often hungry for a fresh angle.
4. **Conference lightning talks.** A 5-minute demo of "why was this item selected?" replaying the tape is compelling on stage.
5. **Academic / research Twitter.** The audit/reproducibility angle appeals to ML reproducibility advocates.
6. **Vertical-specific subreddits.** r/MachineLearning, r/dataengineering, r/selfhosted, r/homelab.
7. **Showcases in model context protocol (MCP) communities.** If the engine exposes an MCP interface, it becomes usable by any MCP client.

---

## 7. AI Native assessment

### Current state: described, not demonstrated

The project has the right ideas:
- SKILL.md is implementation-agnostic.
- The pipeline separates deterministic bookkeeping from LLM judgment.
- ECHO is designed for LLM-driven proactive interaction.

But there is no working example of an LLM agent actually running the skill. A visitor reading "agent-native" has to take it on faith.

### How to make it real

1. **Add `engine/agent_runner.py`.** A minimal harness that takes SKILL.md, parses each step, and calls the deterministic engine functions. The LLM decides *what* to do; the engine does it.
2. **Add an example conversation.** A markdown file showing an LLM reading SKILL.md and executing a full cycle.
3. **Consider an MCP server.** Wrap the pipeline as a Model Context Protocol tool so any MCP client can invoke it.

---

## 8. Productization: first 100 users

### First priority: make the sample issue the landing page

The fastest path to 100 real users is a single, shareable proof point. Recommend:

1. **Generate a real sample issue** from a dry run and make it the README's central showcase.
2. **Add a 60-second demo GIF** showing setup, dry run, and feedback application.
3. **Create one vertical config that is immediately useful** (e.g., "AI safety" or "open-source devtools") and promote it.
4. **Rename to Paperboy** to make the project memorable.
5. **Post to Hacker News, Reddit r/selfhosted, and X** with the sample issue as the lead link.
6. **Add a "Deploy to Replit / GitHub Codespaces" button** so visitors can run it in one click.

### How to get 3 community vertical configs

- Open a GitHub Discussion titled "Share your vertical."
- Provide a template config and ask users to PR their own.
- Recognize contributors in README.

---

## Action plan

### Do this week

1. Rename project to **Paperboy** (owner approval required).
2. Replace the sample issue with a real dry-run output.
3. Add a 60-second demo GIF or terminal cast to README.
4. Add a "Deploy to GitHub Codespaces" button.

### Do this month

1. Implement `engine/agent_runner.py` to demonstrate AI-native execution.
2. Add a comparison page (`docs/comparison.md`).
3. Submit to agent tool directories and MCP server lists.
4. Post launch threads on HN, Reddit, X, and 掘金.

### Do this quarter

1. Build a taste-profile visualization.
2. Add an evolution-log public page.
3. Package SKILL.md as an installable skill for major agent platforms.
4. Pursue conference/community talks.

---

## Naming final recommendation

**Paperboy.**

Reason: it tells a story, is easy to spell and visualize, and maps cleanly onto the project's core loop (scan route → deliver → learn → improve). Keep "Self-Evolving News Engine" as the subtitle for SEO and clarity.
