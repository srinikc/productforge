---
name: google-stitch-uiux
description: Google Stitch / Material Design 3 UI/UX design system. Provides design tokens, component patterns, and theme guidance for building modern Material Design interfaces.
version: 1.0
---

# Google Stitch / Material Design 3 UI/UX System

## Design Tokens

### Color Palette (Material 3)
- Primary: #6750A4
- On Primary: #FFFFFF
- Primary Container: #EADDFF
- On Primary Container: #21005D
- Secondary: #625B71
- Secondary Container: #E8DEF8
- Tertiary: #7D5260
- Surface: #FFFBFE
- Surface Variant: #E7E0EC
- Background: #FFFBFE
- On Background: #1C1B1F
- Outline: #79747E
- Error: #B3261E
- Success: #2E7D32
- Warning: #ED6C02

### Typography
- Display Large: 57px / 64px line-height
- Headline Medium: 28px / 36px
- Title Large: 22px / 28px
- Body Large: 16px / 24px
- Body Medium: 14px / 20px
- Label Medium: 12px / 16px

### Elevation (Shadow Tokens)
- Level 0: none
- Level 1: 0 1px 2px rgba(0,0,0,0.3), 0 1px 3px 1px rgba(0,0,0,0.15)
- Level 2: 0 1px 2px rgba(0,0,0,0.3), 0 2px 6px 2px rgba(0,0,0,0.15)
- Level 3: 0 4px 8px 3px rgba(0,0,0,0.15), 0 1px 3px rgba(0,0,0,0.3)
- Level 4: 0 6px 10px 4px rgba(0,0,0,0.15), 0 2px 3px rgba(0,0,0,0.3)

## Component Patterns

### Cards
- Rounded corners: 12px
- Padding: 16px
- Background: surface
- Border: 1px solid outline-variant

### Buttons
- Filled: bg=primary, text=on-primary
- Outlined: border=outline, text=primary
- Text: text=primary
- Rounded: 20px (pill) or 4px (rectangular)

### Navigation Rail / Drawer
- Width: 240px (drawer) / 80px (rail)
- Background: surface
- Active item: secondary-container

### Status Indicators
- Completed: #2E7D32 (green)
- In Progress: #1976D2 (blue) + pulse animation
- Blocked: #ED6C02 (warning/orange)
- Failed: #B3261E (red)
- Pending: #79747E (gray)
- Generic/Neutral: #E7E0EC (surface variant)

## Pipeline Stage Color Coding
For pipeline dashboards, use:
- pending: var(--md-outline) - gray
- running: var(--md-blue) - blue
- verifying: var(--md-warning) - orange (compliance check)
- completed: var(--md-success) - green (passed compliance)
- failed: var(--md-error) - red
- blocked: var(--md-warning) - orange

## Usage

Apply these tokens via CSS custom properties:

```css
:root {
  --md-primary: #6750A4;
  --md-success: #2E7D32;
  --md-warning: #ED6C02;
  --md-error: #B3261E;
  --md-surface: #FFFBFE;
  --md-outline: #79747E;
}
```

For dark mode:
```css
[data-theme="dark"] {
  --md-primary: #D0BCFF;
  --md-surface: #1C1B1F;
  --md-on-surface: #E6E1E5;
}
```
