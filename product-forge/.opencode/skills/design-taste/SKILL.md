---
name: design-taste
description: Anti-slop frontend discipline for greenfield UIs. Apply when building a new component, page, or app shell from scratch and the user has NOT given a reference site to mimic. Provides 3 dials (variance / motion / density), typography + spacing rules, anti-cliché checks. For reverse-engineering an existing site's taste use design-dna-extractor. For Anthropic's canonical design-lead principles use frontend-design.
license: MIT
source: https://github.com/Leonxlnx/taste-skill (skill v2)
attribution: Leon Lee (@Leonxlnx), ported to Product Forge 2026-09-03
---

# Design Taste — Anti-Slop Frontend Discipline

## Purpose

Stop agents from producing generic, templated UIs. Three dials let the agent dial intensity; a banned-pattern list prevents the AI-cliché looks; a brief-inference protocol forces concrete choices tied to the subject.

## When to use

- Building a new UI from scratch
- User has not given a reference site to mimic
- User wants "polished", "premium", "looks expensive", "not generic", "design-forward"
- Need to make typographic, motion, or density trade-offs

## When NOT to use

- User says "looks like X" / "like Linear" → use `design-dna-extractor` instead
- Auditing an existing UI → use `heuristic-evaluation`
- Anthropic-canonical design-lead voice → use `frontend-design`
- Broad UX research / journey maps / design system definition → use `product-designer`

## The 3 dials

Set these at the very top of the work. They govern every downstream choice.

| Dial | Range | What it controls | 1 | 10 |
|---|---|---|---|---|
| `DESIGN_VARIANCE` | 1-10 | Layout experimentation | Centered, clean, single-column | Asymmetric, broken-grid, layered |
| `MOTION_INTENSITY` | 1-10 | Animation depth | Hover-only micro-interactions | Scroll-triggered reveals + magnetic effects + page-load choreography |
| `VISUAL_DENSITY` | 1-10 | Information per viewport | Spacious, airy, generous whitespace | Dense dashboards, packed, every pixel earns rent |

**Defaults**: variance=5, motion=3, density=5. Adjust based on subject and platform (mobile usually wants density=7, marketing site wants density=2).

## Banned patterns (the "AI-cliché" detector)

If your output contains these without a specific reason, regenerate.

1. **Cream background** (~#F4F1EA) + serif display + terracotta accent
2. **Near-black background** + single neon accent (acid green / vermilion)
3. **Broadsheet layout** + hairline rules + zero border-radius + dense newspaper columns
4. **Em-dash abuse** — more than 2 per paragraph of body copy
5. **"Solutions" / "leverage" / "seamlessly"** in copy
6. **Numbered markers (01/02/03)** unless content is genuinely a sequence
7. **Gradient hero** with no other design intention
8. **Gradient text** with low contrast
9. **"AI-generated illustration"** style with soft pastel blobs
10. **Drop shadow on + rounded corner + everything** — pick one shadow strategy and own it

## Brief inference protocol (run before designing)

```
1. Subject: What is the product? (name, category)
2. Audience: Who uses it? (job, context)
3. Single job: What's the ONE thing this page does for them?
4. Material reference: What real-world material/artifact echoes the brand?
5. Risk: What bold choice can we defend?
```

If any of these is missing from the user brief, INFER them and state your inference at the top of the design.

## Design principles

### Typography is personality

- Pick a **display face** (serif/sans/mono/script) deliberately — not the family you'd reach for on any project
- Pick a **body face** that complements, not matches
- Optional utility face for captions/data
- Define a type scale with intentional weights, widths, line-heights
- The type treatment itself should be memorable

### Structure is information

- Numbered markers, eyebrows, dividers, labels should encode truth about the content
- If the content isn't a sequence, don't number it
- White space inside sections > between sections

### Motion is deliberate

- One orchestrated moment > scattered effects
- Page-load sequence, scroll-trigger, hover micro-interactions, ambient atmosphere
- Sometimes less is more; extra animation reads "AI-generated"

### Restraint is the signature

- Pick ONE memorable element and let everything else be quiet
- A signature element embodies the brief in a specific way

### Complexity matches vision

- Maximalist directions need elaborate execution
- Minimalist directions need precision in spacing and type
- Elegance is executing the chosen vision well

## Process: brainstorm → plan → critique → build → critique

1. **Brainstorm** a short design plan based on brief + dials
2. **Plan** — create a compact token system:
   - **Color**: 4-6 named hex values with roles
   - **Type**: 2+ role faces (display, body, optional utility)
   - **Layout**: one-sentence prose + ASCII wireframe
   - **Signature**: the single memorable element
3. **Critique against the brief** — if any part reads generic, revise and explain why
4. **Build** — derive every color/type from the plan; no drift
5. **Critique again** — take a screenshot, look at it, remove one thing

## Type scale template

```
--font-display: "Fraunces", serif;   /* example */
--font-body: "Inter", sans-serif;
--font-utility: "JetBrains Mono", monospace;

--fs-display: clamp(2.5rem, 5vw, 4.5rem);
--fs-h1: clamp(2rem, 3.5vw, 3rem);
--fs-h2: clamp(1.5rem, 2.5vw, 2rem);
--fs-body: 1rem;
--fs-small: 0.875rem;
--fs-caption: 0.75rem;

--lh-tight: 1.1;
--lh-normal: 1.5;
--lh-loose: 1.7;
```

## Color roles (pick by content, not template)

Don't default to a primary + secondary + neutral palette. Roles:
- **Surface** (page background)
- **Surface-raised** (cards)
- **Surface-inset** (inputs, wells)
- **Text-primary**
- **Text-secondary**
- **Text-muted**
- **Brand accent** (used SPARINGLY — once per screen max)
- **Border** (often a 1px hairline)
- **State colors** (success, warn, error, info) — for feedback only

## Spacing scale

Use a 4 or 8 px base. Pick ONE:

```
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-6: 24px;
--space-8: 32px;
--space-12: 48px;
--space-16: 64px;
--space-24: 96px;
```

## Quality checks (run before declaring done)

- [ ] Dials stated at top of output
- [ ] Brief inferred + stated when missing
- [ ] Token system complete (color, type, layout, signature)
- [ ] None of the banned patterns present (or defended in commentary)
- [ ] Em-dashes ≤ 2 per paragraph
- [ ] Type scale committed (no ad-hoc font sizes)
- [ ] One signature element, one supporting element max
- [ ] Screenshot taken + reviewed against brief
- [ ] Mobile breakpoint tested
- [ ] Keyboard focus visible
- [ ] Reduced-motion media query respected

## Anti-slop final review

After completing the build, ask:
1. Could I delete this and substitute a different product? (If yes, design is generic.)
2. Does the type do work, or just deliver content?
3. Is there one thing I'd remember about this page tomorrow?
4. Did I take one real aesthetic risk I can justify?

## Attribution

This skill is a port of [Leon Lee's taste-skill v2](https://github.com/Leonxlnx/taste-skill) (MIT License, 84K+ stars). Adapted for Product Forge on 2026-09-03 with disambiguating description so it composes cleanly with `design-dna-extractor` and `frontend-design`.

Original install command for reference: `npx skills add Leonxlnx/taste-skill`.