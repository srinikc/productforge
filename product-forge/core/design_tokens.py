"""Design Tokens - manages design system tokens for consistent UI across projects.

Stores colors, typography, spacing, and other design primitives as structured data.
Can generate CSS custom properties or Tailwind config from tokens.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ColorToken:
    name: str
    value: str  # hex, rgb, etc.
    description: str = ""
    category: str = "base"  # base, neutral, primary, secondary, semantic


@dataclass
class TypographyToken:
    name: str
    font_family: str
    font_size: str
    font_weight: str
    line_height: str
    description: str = ""


@dataclass
class SpacingToken:
    name: str
    value: str  # px, rem
    description: str = ""


@dataclass
class DesignTokenSet:
    project: str
    colors: List[ColorToken] = field(default_factory=list)
    typography: List[TypographyToken] = field(default_factory=list)
    spacing: List[SpacingToken] = field(default_factory=list)
    border_radius: List[Dict[str, str]] = field(default_factory=list)
    shadows: List[Dict[str, str]] = field(default_factory=list)


MATERIAL_DESIGN_COLORS = [
    ColorToken("md-primary", "#6750A4", "Primary brand color", "primary"),
    ColorToken("md-on-primary", "#FFFFFF", "Text on primary", "primary"),
    ColorToken("md-primary-container", "#EADDFF", "Primary container", "primary"),
    ColorToken("md-secondary", "#625B71", "Secondary brand color", "secondary"),
    ColorToken("md-tertiary", "#7D5260", "Tertiary accent", "secondary"),
    ColorToken("md-surface", "#FFFBFE", "Surface background", "base"),
    ColorToken("md-surface-variant", "#E7E0EC", "Surface variant", "base"),
    ColorToken("md-on-surface", "#1C1B1F", "Text on surface", "base"),
    ColorToken("md-on-surface-variant", "#49454F", "Secondary text", "base"),
    ColorToken("md-outline", "#79747E", "Borders and outlines", "neutral"),
    ColorToken("md-error", "#B3261E", "Error state", "semantic"),
    ColorToken("md-success", "#386A20", "Success state", "semantic"),
    ColorToken("md-warning", "#7C5800", "Warning state", "semantic"),
    ColorToken("md-info", "#0061A4", "Info state", "semantic"),
]

MATERIAL_DESIGN_TYPOGRAPHY = [
    TypographyToken("display-large", "Roboto", "57px/64px", "400", "Large display text"),
    TypographyToken("display-medium", "Roboto", "45px/52px", "400", "Medium display text"),
    TypographyToken("headline-large", "Roboto", "32px/40px", "400", "Large headline"),
    TypographyToken("headline-medium", "Roboto", "28px/36px", "400", "Medium headline"),
    TypographyToken("title-large", "Roboto", "22px/28px", "400", "Large title"),
    TypographyToken("title-medium", "Roboto", "16px/24px", "500", "Medium title (subtitle1)"),
    TypographyToken("body-large", "Roboto", "16px/24px", "400", "Large body text"),
    TypographyToken("body-medium", "Roboto", "14px/20px", "400", "Medium body text (body1)"),
    TypographyToken("body-small", "Roboto", "12px/16px", "400", "Small body text"),
    TypographyToken("label-large", "Roboto", "14px/20px", "500", "Large label"),
    TypographyToken("label-medium", "Roboto", "12px/16px", "500", "Medium label"),
    TypographyToken("label-small", "Roboto", "11px/16px", "500", "Small label"),
]

MATERIAL_DESIGN_SPACING = [
    SpacingToken("spacing-0", "0px", "No spacing"),
    SpacingToken("spacing-1", "4px", "Extra small spacing"),
    SpacingToken("spacing-2", "8px", "Small spacing"),
    SpacingToken("spacing-3", "12px", "Medium-small spacing"),
    SpacingToken("spacing-4", "16px", "Medium spacing"),
    SpacingToken("spacing-5", "20px", "Medium-large spacing"),
    SpacingToken("spacing-6", "24px", "Large spacing"),
    SpacingToken("spacing-8", "32px", "Extra large spacing"),
    SpacingToken("spacing-10", "40px", "2x large spacing"),
    SpacingToken("spacing-12", "48px", "3x large spacing"),
    SpacingToken("spacing-16", "64px", "4x large spacing"),
]


def get_default_tokens(project: str = "default") -> DesignTokenSet:
    return DesignTokenSet(
        project=project,
        colors=MATERIAL_DESIGN_COLORS,
        typography=MATERIAL_DESIGN_TYPOGRAPHY,
        spacing=MATERIAL_DESIGN_SPACING,
        border_radius=[
            {"name": "none", "value": "0px"},
            {"name": "sm", "value": "4px"},
            {"name": "md", "value": "8px"},
            {"name": "lg", "value": "12px"},
            {"name": "xl", "value": "16px"},
            {"name": "full", "value": "9999px"},
        ],
        shadows=[
            {"name": "sm", "value": "0 1px 2px rgba(0,0,0,0.05)"},
            {"name": "md", "value": "0 4px 6px rgba(0,0,0,0.07)"},
            {"name": "lg", "value": "0 10px 15px rgba(0,0,0,0.1)"},
            {"name": "xl", "value": "0 20px 25px rgba(0,0,0,0.15)"},
        ],
    )


def tokens_to_css_custom_properties(tokens: DesignTokenSet) -> str:
    """Generate CSS custom properties from design tokens."""
    lines = [":root {"]
    for color in tokens.colors:
        var_name = f"--{color.name}"
        lines.append(f"  {var_name}: {color.value};")
    for typo in tokens.typography:
        var_prefix = f"--{typo.name}"
        lines.append(f"  {var_prefix}-font: {typo.font_family};")
        lines.append(f"  {var_prefix}-size: {typo.font_size.split('/')[0]};")
        lines.append(f"  {var_prefix}-weight: {typo.font_weight};")
        lines.append(f"  {var_prefix}-leading: {typo.line_height};")
    for spacing in tokens.spacing:
        lines.append(f"  --{spacing.name}: {spacing.value};")
    for br in tokens.border_radius:
        lines.append(f"  --radius-{br['name']}: {br['value']};")
    for shadow in tokens.shadows:
        lines.append(f"  --shadow-{shadow['name']}: {shadow['value']};")
    lines.append("}")
    return "\n".join(lines)


def tokens_to_dict(tokens: DesignTokenSet) -> Dict[str, Any]:
    return {
        "project": tokens.project,
        "colors": [{"name": c.name, "value": c.value, "category": c.category} for c in tokens.colors],
        "typography": [{"name": t.name, "family": t.font_family, "size": t.font_size, "weight": t.font_weight} for t in tokens.typography],
        "spacing": [{"name": s.name, "value": s.value} for s in tokens.spacing],
        "border_radius": tokens.border_radius,
        "shadows": tokens.shadows,
    }


def save_tokens(project_dir: str, tokens: DesignTokenSet) -> str:
    """Save tokens to project directory."""
    tokens_dir = os.path.join(project_dir, "design-tokens")
    os.makedirs(tokens_dir, exist_ok=True)

    # Save JSON
    json_path = os.path.join(tokens_dir, "tokens.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(tokens_to_dict(tokens), f, indent=2)

    # Save CSS
    css_path = os.path.join(tokens_dir, "tokens.css")
    with open(css_path, "w", encoding="utf-8") as f:
        f.write(tokens_to_css_custom_properties(tokens))

    return json_path
