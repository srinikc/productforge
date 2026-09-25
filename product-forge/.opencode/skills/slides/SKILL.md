# Slides Skill

## Purpose
Generate stunning, interactive presentation decks where every slide is a live, responsive React component — not a static PPTX. Built on top of the bolt-slides framework (Stackblitz, MIT, 917+ stars).

## Stage
Stage 7: Presentation (after Document, before Package). May also be invoked by the marketing agent for GTM decks and by the presentation-generator agent.

## Source
- Repo: https://github.com/stackblitz/bolt-slides
- License: MIT (safe for commercial use)
- Skill: `.bolt/skills/slides/SKILL.md` (the agent-facing authoring guide)

## When to use
- Client pitch decks
- Internal product reviews
- GTM strategy decks (marketing agent)
- Demo decks where you want live data / interactive prototypes
- Any presentation where "static slides" would feel weak

## When NOT to use
- Short printed handouts (use PPTX export instead)
- One-pagers (use document agent)
- Audit/compliance reports (use PDF export of markdown)

## Inputs
- Product info from `docs/product-plan.md`
- Features from `docs/feature-status.md`
- Architecture highlights from `docs/architecture.md`
- Screenshots / diagrams from `docs/`
- Audience: pitch / internal / demo / training
- Tone: editorial luxury / playful / dark technical / minimal / etc.

## Outputs
- `products/<project>/presentation/` — full React app
  - `src/App.tsx` — deck source ( Cover, Agenda, Split, Bento, Charts, Pricing, etc.)
  - `src/styles/tokens.css` — themed via CSS custom properties (--primary, --bg, --fg, --font-display, etc.)
  - `public/` — favicon, screenshots, OG image
- Live URL — shareable link (Stackblitz deploy or local `npm run dev`)
- PDF export — optional, via Slidev-style print stylesheet or via Chrome headless
- Recorded walkthrough — optional, via Playwright/FFmpeg

## Workflow

### 1. Pick a theme
Start with one of the 9 preset themes from bolt-slides' skill:
- editorial-luxury — serif display, generous whitespace, gold accents
- playful — rounded, pastel, friendly
- dark-technical — monospace, neon-on-dark, code-friendly
- minimal — single accent color, big type, lots of whitespace
- corporate — clean sans, conservative
- magazine — large pull-quotes, mixed fonts
- brutalist — raw, asymmetric, intentional
- product-launch — gradient hero, feature grid
- keynote — stage backdrop feel

Set in `tokens.css`:
```css
:root {
  --primary: #58a6ff;
  --bg: #0d1117;
  --fg: #e6edf3;
  --font-display: "Fraunces", serif;
  --font-body: "Inter", sans-serif;
  --radius: 12px;
}
```

### 2. Pick components from the library
| Category | Components |
|---|---|
| Structure | Cover, Agenda, Section, Split, Bento, Slide |
| Data | Charts (bar, line, donut), Table, StatGrid, BigNumber, CountUp, VisualDashboard |
| Story | Quote, Contrast, Comparison, Timeline, Steps, Chat |
| Product | CodeWindow, BrowserFrame, Pricing, Team |
| Flair | Globe, TiltCard, SpotlightCard, Marquee, Accordion, Tabs |

### 3. Compose the deck in App.tsx
```tsx
<Deck>
  <Cover kicker="Product · v1.0" title={<>MyMoney</>} subtitle="Personal finance, finally simple." />
  <Slide center nav="Thesis">
    <h2 className="headline">Dashboards are everywhere. <span className="accent-text">Insight isn't.</span></h2>
    <Build at={1}>
      <p className="subhead">We turn raw events into answers — automatically.</p>
    </Build>
  </Slide>
  <Agenda kicker="Agenda" title="What we'll cover." items={["Problem","How","Pricing","Ask"]} />
  {/* ... */}
</Deck>
```

### 4. Use `<Build at={n}>` for click-reveals
- Arrow keys step through builds before advancing slides
- `<Build at={1}>` reveals on first click within that slide
- `<Build at={2}>` reveals on second click

### 5. Set tab title + favicon
```tsx
useEffect(() => {
  document.title = "MyMoney Pitch";
  const link = document.querySelector("link[rel='icon']") as HTMLLinkElement;
  if (link) link.href = "/favicon.svg";
}, []);
```

### 6. Set OG image for shared link
Place 1200x630 image at `public/og.png` for rich link previews.

### 7. Deliver
- Local: `npm run dev` opens hot-reload dev server
- Share: deploy to Stackblitz or Vercel
- Print: enable print stylesheet and use Chrome headless for PDF
- Record: Playwright script that drives the deck + records

## Presenter controls (built in)
| Key | Action |
|---|---|
| `→` `↓` `Space` | Next (reveals builds first) |
| `←` `↑` | Previous (rewinds builds) |
| `Home`/`End` | First/last slide |
| `S` | Thumbnail sidebar |
| `G` | Grid view — every slide at once |
| `A` | Annotate — pen, highlighter, shapes |
| `F` | Fullscreen |
| `P` | Presenter mode — synced new tab with timer + notes |
| `H` | Hide UI |
| `Esc` | Close overlays |

## Quality checks
- [ ] Deck opens in <2s on a cold load
- [ ] Responsive: works on 13" laptop and 6" phone
- [ ] All builds reveal in correct order
- [ ] Notes show in presenter mode
- [ ] Annotations persist per-slide
- [ ] URL hash deep-links to each slide
- [ ] Favicon + tab title set
- [ ] OG image present for shared links

## Installation
```bash
npx skills add stackblitz/bolt-slides
```
Or copy this SKILL.md and the bolt-slides repo into `products/<project>/presentation/`.

## Rules
1. NEVER ship generic bullet walls — every slide must justify its existence visually
2. NEVER use stock gradients — pick a theme and own it
3. ALWAYS set tab title + favicon
4. ALWAYS test responsive (resize browser before declaring done)
5. ALWAYS include presenter notes for non-obvious slides
6. PREFER live data over screenshots where possible