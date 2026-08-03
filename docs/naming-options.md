# Naming Options

The current name, **Self-Evolving News Engine**, is descriptive and search-friendly, but it reads like a feature list rather than a story. Below are candidates that trade a little literal clarity for memorability, emotion, and visual identity.

---

## Shortlist

### 1. Paperboy *(recommended)*

**Rationale:**
- A paperboy delivers the day's news, learns your preferences over time, and grows into the route. The metaphor maps cleanly onto "scan → deliver → learn → evolve".
- It is short, human, and slightly nostalgic without feeling dated.
- Easy to pronounce and spell across languages.

**Tagline fit:** "Paperboy — your news route, learned."

**Trade-offs:**
- Could imply a single-user, consumer app rather than an engine/skill.
- Domain and PyPI namespace may be contested.

**Verdict:** Best balance of warmth, memorability, and thematic fit.

---

### 2. Kiosk

**Rationale:**
- A kiosk is where front pages are displayed; it naturally maps to the "scan the front page" concept.
- Pairs beautifully with a Kandinsky/constructivist visual style (the logo can look like a modernist newsstand).
- Short and distinctive.

**Tagline fit:** "Kiosk — the front page, curated by you."

**Trade-offs:**
- Less direct "evolution" signal.
- Slightly more abstract; users may need the tagline to understand what it does.

**Verdict:** Strong if the visual identity and "front page" metaphor are the lead story.

---

### 3. Scoop

**Rationale:**
- A news-industry term for an exclusive story; short and punchy.
- Implies discovery and quality.

**Tagline fit:** "Scoop — find the signal, train the taste."

**Trade-offs:**
- Weak connection to self-evolution and feedback loops.
- Very common word; SEO and namespace competition are high.

**Verdict:** Good for a product, less good for this architecture-first project.

---

### 4. Molt

**Rationale:**
- "Molt" means to shed an old form and grow a new one — the strongest evolution metaphor in the list.
- Distinctive and short.

**Tagline fit:** "Molt — news curation that sheds what no longer fits."

**Trade-offs:**
- Cold, biological imagery; less accessible.
- May sound like a skin disease to non-native speakers.

**Verdict:** Conceptually precise but emotionally distant.

---

### 5. Tapedeck

**Rationale:**
- Directly references the append-only "tape" concept.
- Suggests recording, replay, and retro reliability.

**Tagline fit:** "Tapedeck — record the news, replay the decisions."

**Trade-offs:**
- Highlights the tape but underweights the evolution/feedback loop.
- Feels like a tool name rather than a system name.

**Verdict:** Good if the audit/replay angle becomes the primary differentiator.

---

## Recommendation

**Lead with Paperboy.** It is the only candidate that simultaneously:
- Communicates "news delivery",
- Implies learning/growth (a paperboy learns the route),
- Sounds human and approachable,
- Works across consumer and developer contexts.

If the team prefers to keep the project name more abstract/architectural, **Kiosk** is the runner-up.

**Suggested naming migration:**
- Repo: `lukethecat/paperboy`
- PyPI: `paperboy-engine` (if `paperboy` is taken)
- Display name: **Paperboy**
- Subtitle: *A self-evolving news curation engine*

**Decision required from owner:** Confirm whether to rename the GitHub repository. Renaming breaks old URLs unless a redirect is preserved; GitHub automatically preserves redirects for renamed repos, but external links should be updated.
