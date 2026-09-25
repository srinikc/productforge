---
name: design-dna-extractor
description: Reverse-engineer any website's design taste via Playwright MCP. Produces concrete tokens + trade-offs (the WHY, not just the WHAT). Use ONLY when the user says "build something that looks like X", "match the aesthetic of Y", or wants tokens extracted from a reference URL. For greenfield UI without a reference use design-taste. For Anthropic's design-lead voice use frontend-design.
license: MIT
source: https://github.com/senlindesign/taste-skill
attribution: Sen Lin (@senlindesign), ported to Product Forge 2026-09-03
requires: playwright-mcp
---

# Design DNA Extractor

## Purpose

Most "AI design" tools give you tokens: "The background is #08090A. The font is Inter. The radius is 6px." That's a spec sheet, not taste. An agent with tokens just applies the stylesheet; an agent with taste makes the right call on pages it's never seen.

This skill extracts both — the WHAT (tokens) AND the WHY (trade-offs, principles).

## When to use

- User says "make it look like Linear", "match Stripe's aesthetic", "feel like Vercel"
- Need a design system reference before building a competitor-style UI
- Competitive design research
- User says "extract the design from <url>"
- Generative brief: "build a B2B SaaS landing page in the spirit of Linear but for our domain"

## When NOT to use

- Greenfield UI with no reference → use `design-taste` instead
- Audit an existing UI for usability issues → use `heuristic-evaluation`
- Pure copy/content extraction → use a web scraper, not this skill

## Prerequisites

- `playwright-mcp` installed and configured
- Each run starts with a FRESH browser state (`--isolated`) so authenticated app dashboards don't leak into the analysis

## Pipeline

```
Phase 0  Parse URL → extract domain → ask export target → ask crawl scope
          Crawl scope 1: single page (default)
          Crawl scope 2: explore 2-3 linked pages (finds Product / Pricing / Changelog etc.)
Phase 1  Playwright reconnaissance:
          viewport screenshot (1440×900) ← primary visual reference
          full-page screenshot ← cross-page systematic check
          DOM extractor (extract.js) ← 8000-element full-page scan
          [multi] extract nav links → visit 2 more pages → capture each
          [multi] merge — cross-page values = system signals
Phase 2  4-step analysis:
          Step 1 (Measure)   20 categories, exact px/hex/ratio
          Step 2 (Pattern)   5-8 system rules, Evidence + Design Goal
          Step 3 (Taste)     4 principles, Trigger/Decision/Reason/Evidence
          Step 4 (Observer)  quality gate → final output
Phase 3  Write {domain}.md + {domain}.json
Phase 4  Anti-slop audit + JSON validation
Phase 5  Export to build tool format
Phase 6  Report
```

**Visual primacy rule**: the screenshot is ground truth. DOM supplies exact numbers, but when they conflict, the screenshot wins. A color at <5% visual surface area is decorative — not a brand color.

## 20 measurement categories (Step 1)

Per page, capture exact values:

1. **Background** — page bg hex/rgba
2. **Surface** — card/section bg
3. **Text primary** — body text color
4. **Text secondary** — muted text
5. **Font families** — display, body, utility
6. **Font weights** — distribution per role
7. **Font sizes** — actual sizes used (not just scale)
8. **Line heights** — by text role
9. **Card radius** — single value + outliers
10. **Primary depth signal** — shadow? border? inset?
11. **Border style** — hairline, 1px solid, 2px, etc.
12. **Spacing distribution** — most common gap values
13. **Container widths** — max-width of main content
14. **Grid columns** — typical grid structure
15. **Buttons** — radius, padding, height, primary/secondary contrast
16. **Color count** — total unique colors used
17. **Background color areas** — % of viewport per color
18. **Hover/focus indicators** — what changes on interaction
19. **Transition timing** — duration + easing
20. **Iconography** — line weight, fill vs stroke, grid

## 5-8 system patterns (Step 2)

Identify recurring rules. Each must have:
- **Pattern name**
- **Design goal** — what it's achieving
- **Evidence** — at least 2 places where it appears across pages
- **Counter-example** — when it would NOT apply

## 4 taste principles (Step 3)

The deepest layer. Each principle has:
- **Principle** — the design philosophy (one sentence)
- **Trigger** — the design decision moment it applies to
- **Decision** — what to do
- **Reason** — why (the why is the value)
- **Evidence** — at least 3 examples from the site

## Output formats

### Always produced
- `{domain}.md` — human-readable Design Map + Taste DNA
- `{domain}.json` — same data, machine-parseable

### Optional, picked at start
- Cursor: `.cursor/rules/{domain}-taste.mdc`
- Windsurf: `.windsurf/rules/{domain}-taste.md`
- Claude Code: append to `CLAUDE.md`
- v0 by Vercel: `taste-tokens.css`
- Figma Make: `taste-figma.css`

## Example output (Linear)

```markdown
## Design Map

Background: #08090A
Surface (card): rgba(255,255,255,0.05)
Text primary: #F7F8F8
Font: Inter Variable — weight 510 (display), 590 (subhead)
Card radius: 6px
Primary depth signal: rgb(35,37,42) 0px 0px 0px 1px inset
Transition: 160ms cubic-bezier(0.25, 0.46, 0.45, 0.94)

## Taste DNA

Principle: Brand lives in white, not in color — RESTRAINT
Trigger: Deciding on an accent color.
Decision: Don't introduce one. Use white (#F7F8F8) on near-black.
Reason: On #08090A, white carries all the emphasis needed. A branded
        CTA button would make it feel like a template.
Evidence: Every nav link and CTA is white or near-white. The pink
          gradient in the hero is a one-time decorative moment,
          not a system. accentCandidates from DOM are 100% grays.
Trade-off: Can't differentiate feature tiers by color. Hierarchy
           comes from weight and size alone.
```

## Composing with other skills

After extraction, hand the tokens + DNA to:

- **`design-taste`** — apply the variance/motion/density dials using extracted constraints as the starting point
- **`frontend-design`** — apply Anthropic's hero-as-thesis and writing rules
- **`product-designer`** — if user also wants process artifacts (journey maps, design system docs)

Order: `design-dna-extractor` → `design-taste` → `frontend-design` → `product-designer` (process).

## Known limitations

- Pages behind login → returns login form
- Cloudflare / bot-detection → returns verify page (try a different page on the same domain)
- Heavy SPAs may still be hydrating after load → wait up to 6s
- CSS custom properties resolve to computed values, not variable names

## Attribution

Ported from [senlindesign/taste-skill](https://github.com/senlindesign/taste-skill) (MIT, 331+ stars) on 2026-09-03. Playwright MCP required.