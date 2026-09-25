---
name: visual-regression-aesthetics
description: Aesthetic regression testing for UIs. Combines Playwright pixel diffs with semantic checks for typography, spacing, color contrast, and alignment. Catches what pixel-only visual regression misses: a button at the right pixel position with the wrong font weight. Use during pre-production visual audit and as a quality gate for design changes. Does NOT replace playwright-pro or e2e-testing-claude-code - complements them with aesthetic dimension.
license: MIT
requires: playwright
---

# Visual Regression — Aesthetic Dimension

## Purpose

Standard visual regression (pixel diff) catches pixel-level changes but misses **aesthetic regressions** where pixels are identical (or near-identical) but the design intent is violated:

- Button at correct position but wrong font weight (lost design system update)
- Same colors used but contrast ratio dropped below WCAG AA
- Typography scale drifted (someone used 13px instead of 12px or 14px)
- Spacing on a card no longer matches the 8-px grid
- Border radius drifted from 6px to 8px after a refactor
- A banned-pattern from design-taste appeared (cream + serif + terracotta)

This skill adds the **aesthetic dimension** to visual regression testing.

## When to use

- Before declaring pre-production ready (Stage 10 of pipeline)
- After any design-system change (component library update, theme change, design token rename)
- After any "design polish" PR
- When reviewing screenshots from heuristic-evaluation
- During `/pipeline present` workflow to verify deck aesthetics
- On every PR that touches CSS files (run as CI step)

## When NOT to use

- Functional regression testing (use `playwright-pro` or `e2e-testing-claude-code`)
- Performance regression (use `performance` agent)
- Visual accessibility (use `a11y-audit` agent — partially overlaps with contrast checks but more comprehensive)
- Pure design taste audit (use `design-taste` skill)

## Three layers of check

### Layer 1: Pixel diff (standard visual regression)

Capture screenshots, diff against baseline.

```python
# Pseudo-code
baseline = capture_screenshot(url, viewport=(1440, 900))
current = capture_screenshot(url, viewport=(1440, 900))
diff = pixel_diff(baseline, current, threshold=0.05)  # 5% pixel threshold
assert diff.pixels_changed < 0.01  # Less than 1% of pixels should change
```

Multi-viewport: capture at 1440x900, 768x1024, 375x667.

Mask before diff:
- Text content (font rendering varies)
- Date/time displays
- Random data placeholders
- User avatars (if any)

### Layer 2: Token compliance

For every visible element, check that:
- font-size matches the type scale (12, 14, 16, 18, 20, 24, 30, 36, 48, 60 — common scales)
- spacing follows the 4/8-px grid
- border-radius matches design system tokens
- color comes from the palette (no ad-hoc hex values)
- font family matches the system fonts

```python
# Per-element token check
for el in visible_elements(page):
    fs = get_computed_style(el, 'font-size')
    assert fs in ALLOWED_FONT_SIZES, f"{el.selector}: {fs}px not in scale"
    
    pad = parse_spacing(get_computed_style(el, 'padding'))
    assert all(p % 4 == 0 for p in pad), f"{el.selector}: padding not on 4-grid"
```

### Layer 3: Aesthetic / heuristic checks

These are subjective, but measurable proxies:

| Check | What it measures | Threshold |
|---|---|---|
| Color contrast (text on bg) | WCAG AA compliance | ratio >= 4.5:1 for body, >= 3:1 for large |
| Hierarchy clarity | Distinct sizes for h1/h2/body | >= 1.25 ratio between adjacent levels |
| Whitespace consistency | Card padding within ±2px of token | mean < ±2px from token value |
| Alignment | Elements on a common vertical axis | < 4px drift in column alignment |
| Banned-pattern scan | design-taste 10 anti-cliches | 0 matches |
| Animation duration | Animation timings within 100-400ms | all in range |
| Focus visibility | :focus-visible has visible outline | non-empty outline + >= 2px width |

## Implementation

### Setup

```bash
pip install playwright pillow axe-playwright-python
playwright install chromium
```

### Baseline capture script

```python
# scripts/capture-baseline.py
from playwright.sync_api import sync_playwright
from pathlib import Path

PAGES = [
    ("/", "home"),
    ("/pricing", "pricing"),
    ("/dashboard", "dashboard"),
]
VIEWPORTS = [
    ("desktop", 1440, 900),
    ("tablet", 768, 1024),
    ("mobile", 375, 667),
]

def capture_all(base_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for url, name in PAGES:
            for vp_name, w, h in VIEWPORTS:
                page = browser.new_page(viewport={"width": w, "height": h})
                page.goto(f"{base_url}{url}", wait_until="networkidle")
                out = Path(f"baselines/{name}-{vp_name}.png")
                out.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=out, full_page=False)
                page.close()
        browser.close()

if __name__ == "__main__":
    capture_all("http://localhost:3000")
```

### Token compliance check

```python
# scripts/check-tokens.py
from playwright.sync_api import sync_playwright
from axe_playwright_python.sync_playwright import Axe

ALLOWED_FONT_SIZES = {12, 13, 14, 15, 16, 18, 20, 24, 30, 36, 48, 60}
ALLOWED_RADII = {0, 2, 4, 6, 8, 12, 16, 24, 9999}
GRID = 4

def check_tokens(url):
    issues = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        
        for el in page.query_selector_all("*"):
            box = el.bounding_box()
            if not box:
                continue
            fs = page.evaluate("(el) => getComputedStyle(el).fontSize", el)
            fs_px = int(float(fs.replace("px", "")))
            if fs_px not in ALLOWED_FONT_SIZES:
                issues.append(f"{el}: font-size {fs_px}px not in scale")
            
            r = page.evaluate("(el) => getComputedStyle(el).borderRadius", el)
            r_px = int(float(r.replace("px", "")))
            if r_px not in ALLOWED_RADII:
                issues.append(f"{el}: border-radius {r_px}px not in tokens")
            
            for prop in ("padding", "margin"):
                val = page.evaluate(f"(el) => getComputedStyle(el).{prop}", el)
                for piece in val.split():
                    if piece.endswith("px"):
                        n = float(piece[:-2])
                        if n != 0 and n % GRID != 0:
                            issues.append(f"{el}: {prop} {n}px not on {GRID}px grid")
        
        browser.close()
    return issues
```

### Banned-pattern scan (design-taste integration)

```python
# scripts/scan-banned-patterns.py
"""
Check the current build for the 10 banned patterns from design-taste.
"""
from PIL import Image
from collections import Counter

def detect_cream_serif_terracotta(screenshot_path):
        img = Image.open(screenshot_path)
        pixels = list(img.getdata())
        # Cream ~ (245, 241, 234) — sample top 5% of pixels
        cream_count = sum(1 for p in pixels if 240 <= p[0] <= 250 and 235 <= p[1] <= 245 and 225 <= p[2] <= 240)
        terracotta_count = sum(1 for p in pixels if 180 <= p[0] <= 220 and 80 <= p[1] <= 110 and 60 <= p[2] <= 90)
        return cream_count / len(pixels) > 0.4 and terracotta_count / len(pixels) > 0.01

# Run on every page in baselines/
import glob
for f in glob.glob("baselines/*.png"):
    if detect_cream_serif_terracotta(f):
        print(f"WARN: {f} matches banned pattern #1 (cream + serif + terracotta)")
```

(Real implementation would also OCR for serif fonts; this is a color proxy.)

## Output report

```json
{
  "test_run": "2026-09-03T18:00:00Z",
  "url": "http://localhost:3000",
  "pages_checked": ["/", "/pricing", "/dashboard"],
  "viewports": ["desktop", "tablet", "mobile"],
  "pixel_diff": {
    "home-desktop": {"pixels_changed_pct": 0.002, "threshold": 0.01, "pass": true},
    "home-tablet": {"pixels_changed_pct": 0.008, "threshold": 0.01, "pass": true},
    "home-mobile": {"pixels_changed_pct": 0.001, "threshold": 0.01, "pass": true}
  },
  "token_compliance": {
    "violations": [
      {"page": "/dashboard", "element": ".stat-card .value", "rule": "font-size", "actual": "13px", "expected": "12px or 14px"}
    ]
  },
  "aesthetic_checks": {
    "contrast_violations": 0,
    "alignment_violations": 2,
    "banned_patterns_detected": []
  },
  "verdict": "PASS" | "FAIL"
}
```

## Quality gates

For pre-production ready:
- Pixel diff: < 1% pixels changed on all pages
- Token compliance: 0 violations
- Aesthetic checks: 0 critical, < 3 minor
- Banned patterns: 0 detected

For PR merge to main:
- Pixel diff: < 5% (allows for design refreshes)
- Token compliance: 0 NEW violations (existing allowed)
- Aesthetic checks: < 1 new violation

## CI integration

```yaml
# .github/workflows/visual-aesthetic.yml
name: Visual Aesthetic Regression
on:
  pull_request:
    paths: ['**/*.css', '**/*.tsx', '**/*.jsx', 'src/tokens/**']
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install playwright pillow axe-playwright-python
      - run: playwright install chromium
      - run: python scripts/check-tokens.py http://localhost:3000
      - run: python scripts/scan-banned-patterns.py
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: visual-aesthetic-report
          path: report.json
```

## Composition with other skills

| Need | Use |
|---|---|
| Visual aesthetic regression (this skill) | CI gate on PRs |
| Functional regression (e2e) | `e2e-testing-claude-code` |
| Visual pixel diffs (no semantic check) | `playwright-pro` |
| Anti-cliché checklist (manual) | `design-taste` |
| Nielsen/Shneiderman audit | `heuristic-evaluation` |

## Attribution

Created for Product Forge 2026-09-03 — fills a gap not covered by Leonxlnx/taste-skill, anthropics/skills, or existing Product Forge skills.