# When to use Aperture

Use Aperture when at least one of these three questions is true for you.

## The three questions

### 1. Do you have hard-to-reach sources?

- No stable RSS/API.
- Publish dates are unreliable, missing, or manipulated.
- The site is a SPA, changes layout often, or has anti-scraping behavior.
- You need to know what is *new on the front page* today.

If yes → **Aperture's scan mode is built for this.**

RSS says "wait for the source to push." Web search says "ask the index and hope the date is right." Aperture's scan says "read the front page like a human every day" — it works on any page that has links.

### 2. Do you need to answer "why was this selected?"

- You run a newsletter, research team, or community digest.
- Stakeaders or readers ask for the reasoning behind curation.
- Compliance or audit requires a decision trail.

If yes → **Aperture's tape is the point.**

Every candidate, score, rejection reason, profile version, and final report is append-only logged. You can replay why any item made or missed the cut.

### 3. Does your taste evolve faster than static filters?

- You often say things like "more AI safety, fewer sponsored posts."
- You want profile changes versioned and reversible.
- You want to recheck yesterday's items against today's taste.

If yes → **Aperture's reflection loop is for you.**

Feedback becomes profile operations, and every operation is logged. Roll back any change and see what would have been filtered.

---

## When you do not need Aperture

Be honest. You probably do not need it if:

- You follow two or three low-noise RSS feeds and skim them by hand.
- Every source has a clean API and honest timestamps.
- You only need a one-time answer, not continuous monitoring.
- Nobody will ever ask why an item was included or excluded.
- Your keyword list is static and rarely changes.

In those cases, a good RSS reader, a scheduled web-search script, or a one-shot LLM prompt is simpler and faster. Do not over-engineer.

---

## Scan vs RSS vs web search

| Capability | RSS subscription | Web search | Aperture scan |
|------------|------------------|------------|---------------|
| Works without RSS/API | No | Yes | Yes |
| Stable daily signal | Yes | No | Yes |
| Trustworthy date | Depends on source | Often wrong | Not required |
| Cross-source dedup | No | No | Yes |
| Audit trail | No | No | Yes |
| Learns from feedback | No | No | Yes |
| Setup effort | Low | Low | Higher |

RSS is "wait for push." Search is "ask once." Scan is "read the newspaper every morning."

---

## Decision tree

```
Do you monitor more than 3 sources for the same beat?
├── No → RSS reader / web search is enough
└── Yes
    Are the sources noisy, front-page only, or date-unreliable?
    ├── Yes → Aperture's scan mode is built for this
    └── No
        Do you need to explain or audit your selections?
        ├── Yes → Aperture's tape is the point
        └── No
            Does your interest profile change often?
            ├── Yes → Aperture's reflection loop helps
            └── No → static filters are fine
```

---

## Concrete examples

| Scenario | Plain RSS / search | Aperture |
|----------|-------------------|----------|
| Track 20 tech blogs, remove duplicates | Manual scanning | Scan + simhash clustering |
| Filter out sponsored posts and hiring threads | Add negative keywords once | Weighted negatives + feedback-driven updates |
| Explain why a story made the newsletter | Memory/hunch | Tape decision chain |
| Monitor a site with no RSS | Cannot | Generic link extraction + front-page diff |
| Rebuild yesterday's digest with a stricter profile | Impossible | Roll back profile, recheck tape |

## The bottom line

Aperture trades simplicity for auditability and adaptability. If your problem is "too many sources, too much noise, and no record of why," it is a good fit. If your problem is "I want to read three blogs," it is not.
