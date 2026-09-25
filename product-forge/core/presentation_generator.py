"""
Presentation Generator
Generates product presentations, documentation packages, and demo videos
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
import json

try:
    from dataclasses import dataclass, asdict
except ImportError:
    pass


@dataclass
class PresentationConfig:
    """Configuration for presentation generation"""
    product_name: str
    version: str
    tagline: str = ""
    company: str = ""
    date: str = ""
    output_dir: str = "presentations"
    formats: List[str] = None
    include_video: bool = True
    include_marketing: bool = True

    def __post_init__(self):
        if self.formats is None:
            self.formats = ["pptx", "pdf", "html"]
        if not self.date:
            self.date = datetime.now().strftime("%Y-%m-%d")


@dataclass
class Slide:
    """Presentation slide"""
    title: str
    content: str
    layout: str = "default"
    notes: str = ""
    image: Optional[str] = None
    bullets: List[str] = None


class PresentationGenerator:
    """Generates product presentations"""

    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.templates_dir = Path("templates")
        self.templates_dir.mkdir(exist_ok=True)

    def generate_full_package(self, config: PresentationConfig,
                              product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate complete presentation package"""
        output_dir = self.products_dir / config.product_name / config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {
            "product": config.product_name,
            "version": config.version,
            "generated_at": datetime.now().isoformat(),
            "files": {}
        }

        # Generate slides
        slides = self._generate_slides(config, product_data)

        # Generate PPTX
        if "pptx" in config.formats:
            pptx_path = self._generate_pptx(config, slides, output_dir)
            results["files"]["pptx"] = str(pptx_path)

        # Generate PDF
        if "pdf" in config.formats:
            pdf_path = self._generate_pdf(config, slides, output_dir)
            results["files"]["pdf"] = str(pdf_path)

        # Generate HTML
        if "html" in config.formats:
            html_path = self._generate_html(config, slides, output_dir)
            results["files"]["html"] = str(html_path)

        # Generate markdown source
        md_path = self._generate_markdown(config, slides, output_dir)
        results["files"]["markdown"] = str(md_path)

        # Save config
        config_path = output_dir / "presentation.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results

    def _generate_slides(self, config: PresentationConfig,
                         product_data: Dict[str, Any]) -> List[Slide]:
        """Generate slide content"""
        slides = []

        # Cover slide
        slides.append(Slide(
            title=config.product_name,
            content=f"{config.tagline}\n\nVersion {config.version}\n{config.company}\n{config.date}",
            layout="cover"
        ))

        # Product overview
        overview = product_data.get("overview", "Product overview not available")
        slides.append(Slide(
            title="Product Overview",
            content=overview,
            layout="content"
        ))

        # Features
        features = product_data.get("features", [])
        if features:
            feature_bullets = [f"**{f.get('name', 'Feature')}**: {f.get('description', '')}"
                             for f in features[:10]]
            slides.append(Slide(
                title="Key Features",
                content="\n\n".join(feature_bullets),
                layout="bullets",
                bullets=feature_bullets
            ))

        # Getting started
        getting_started = product_data.get("getting_started", {})
        if getting_started:
            steps = getting_started.get("steps", [])
            slides.append(Slide(
                title="Getting Started",
                content="\n".join(f"{i+1}. {step}" for i, step in enumerate(steps)),
                layout="steps"
            ))

        # Architecture
        architecture = product_data.get("architecture", {})
        if architecture:
            tech_stack = architecture.get("tech_stack", [])
            slides.append(Slide(
                title="Architecture",
                content=f"Tech Stack: {', '.join(tech_stack)}",
                layout="content"
            ))

        # API Reference
        api = product_data.get("api", {})
        if api:
            endpoints = api.get("endpoints", [])
            slides.append(Slide(
                title="API Reference",
                content=f"{len(endpoints)} endpoints available",
                layout="content"
            ))

        # Deployment
        deployment = product_data.get("deployment", {})
        if deployment:
            options = deployment.get("options", [])
            slides.append(Slide(
                title="Deployment Options",
                content="\n".join(f"- {opt}" for opt in options),
                layout="bullets"
            ))

        # Support
        slides.append(Slide(
            title="Support & Resources",
            content="Documentation: docs/\nGitHub: [repo]\nEmail: support@example.com",
            layout="content"
        ))

        # CTA
        slides.append(Slide(
            title="Get Started Today",
            content="Try it now: [link]\nSchedule demo: [link]\nContact sales: [link]",
            layout="cta"
        ))

        return slides

    def _generate_pptx(self, config: PresentationConfig,
                       slides: List[Slide], output_dir: Path) -> Path:
        """Generate PowerPoint file"""
        pptx_path = output_dir / f"{config.product_name}-presentation.pptx"

        # Use python-pptx if available
        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt

            prs = Presentation()

            for slide_data in slides:
                slide_layout = prs.slide_layouts[1]  # Title and Content
                slide = prs.slides.add_slide(slide_layout)

                # Set title
                title = slide.shapes.title
                title.text = slide_data.title

                # Set content
                content = slide.placeholders[1]
                content.text = slide_data.content

            prs.save(str(pptx_path))
        except ImportError:
            # Fallback: create placeholder
            with open(pptx_path, "w", encoding="utf-8") as f:
                f.write(f"# {config.product_name} Presentation\n\n")
                f.write("Note: python-pptx not installed. Install with: pip install python-pptx\n\n")
                for slide in slides:
                    f.write(f"## {slide.title}\n\n{slide.content}\n\n---\n\n")

        return pptx_path

    def _generate_pdf(self, config: PresentationConfig,
                      slides: List[Slide], output_dir: Path) -> Path:
        """Generate PDF file"""
        pdf_path = output_dir / f"{config.product_name}-presentation.pdf"

        # Use reportlab if available
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet

            doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            for slide in slides:
                # Add title
                story.append(Paragraph(slide.title, styles['Heading1']))
                story.append(Spacer(1, 12))

                # Add content
                story.append(Paragraph(slide.content, styles['Normal']))
                story.append(Spacer(1, 24))

            doc.build(story)
        except ImportError:
            # Fallback: create markdown-based PDF
            md_path = self._generate_markdown(config, slides, output_dir)
            with open(pdf_path, "w", encoding="utf-8") as f:
                f.write(f"# {config.product_name} Presentation\n\n")
                f.write("Note: reportlab not installed. Install with: pip install reportlab\n\n")
                for slide in slides:
                    f.write(f"## {slide.title}\n\n{slide.content}\n\n---\n\n")

        return pdf_path

    def _generate_html(self, config: PresentationConfig,
                       slides: List[Slide], output_dir: Path) -> Path:
        """Generate HTML presentation"""
        html_path = output_dir / f"{config.product_name}-presentation.html"

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{config.product_name} Presentation</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .slide {{ border: 1px solid #ccc; padding: 20px; margin: 20px 0; page-break-after: always; }}
        .slide h1 {{ color: #333; }}
        .cover {{ text-align: center; background: #f5f5f5; }}
        .cta {{ background: #e8f5e9; text-align: center; }}
    </style>
</head>
<body>
"""
        for i, slide in enumerate(slides):
            layout_class = slide.layout if slide.layout in ["cover", "cta"] else ""
            html_content += f"""
    <div class="slide {layout_class}">
        <h1>{slide.title}</h1>
        <div class="content">
            {slide.content.replace(chr(10), '<br>')}
        </div>
    </div>
"""
        html_content += """
</body>
</html>"""

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return html_path

    def _generate_markdown(self, config: PresentationConfig,
                           slides: List[Slide], output_dir: Path) -> Path:
        """Generate markdown source"""
        md_path = output_dir / f"{config.product_name}-presentation.md"

        md_content = f"# {config.product_name} Presentation\n\n"
        md_content += f"Version: {config.version} | Date: {config.date}\n\n"
        md_content += "---\n\n"

        for slide in slides:
            md_content += f"## {slide.title}\n\n{slide.content}\n\n---\n\n"

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return md_path


class VideoGenerator:
    """Generates demo videos with inline highlighting"""

    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.videos_dir = Path("videos")
        self.videos_dir.mkdir(exist_ok=True)

    def generate_demo_video(self, product_name: str,
                            product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate demo video for product"""
        output_dir = self.products_dir / product_name / "videos"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate script
        script = self._generate_script(product_data)
        script_path = output_dir / "demo-script.md"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        # Generate ffmpeg commands for video creation
        commands = self._generate_ffmpeg_commands(product_name, product_data, output_dir)
        commands_path = output_dir / "video-commands.sh"
        with open(commands_path, "w", encoding="utf-8") as f:
            f.write("#!/bin/bash\n\n")
            f.write("# Video generation commands\n")
            f.write("# Run these commands to create the demo video\n\n")
            for cmd in commands:
                f.write(f"{cmd}\n\n")

        return {
            "product": product_name,
            "script": str(script_path),
            "commands": str(commands_path),
            "output": str(output_dir / "demo.mp4")
        }

    def _generate_script(self, product_data: Dict[str, Any]) -> str:
        """Generate video narration script"""
        name = product_data.get("name", "Product")
        features = product_data.get("features", [])[:5]

        script = f"""# {name} Demo Video Script

## Intro (10-15 seconds)
[Narrator]
"Welcome to {name} - the solution that helps you [value proposition].
Let me show you how it works."

## Feature Walkthrough (60-120 seconds)
[Narrator]
"First, let's look at [Feature 1]..."
[Screen: Show feature with red circle highlight]
[Text overlay: "Feature 1: Description"]

[Continue for each feature...]

## Key Benefits (30-45 seconds)
[Narrator]
"Here's what {name} saves you:"
[Screen: Before/After comparison]
[Text overlay: "Time saved: X hours/week"]
[Text overlay: "Cost savings: $X/month"]

## Call to Action (10-15 seconds)
[Narrator]
"Ready to get started? Visit [link] or contact us at [email]."
[Screen: Landing page with CTA button highlighted]
"""
        return script

    def _generate_ffmpeg_commands(self, product_name: str,
                                  product_data: Dict[str, Any],
                                  output_dir: Path) -> List[str]:
        """Generate ffmpeg commands for video creation"""
        commands = []

        # Create video from images with transitions
        commands.append(
            f"# Create video from screenshots\n"
            f"ffmpeg -framerate 1 -i {output_dir}/screenshots/%03d.png "
            f"-c:v libx264 -pix_fmt yuv420p {output_dir}/demo.mp4"
        )

        # Add text overlays
        commands.append(
            f"# Add text overlays\n"
            f"ffmpeg -i {output_dir}/demo.mp4 "
            f"-vf \"drawtext=text='Feature Name':fontsize=24:fontcolor=red:x=10:y=10\" "
            f"{output_dir}/demo-with-overlays.mp4"
        )

        # Add audio (if available)
        commands.append(
            f"# Add narration audio\n"
            f"ffmpeg -i {output_dir}/demo-with-overlays.mp4 "
            f"-i {output_dir}/narration.wav "
            f"-c:v copy -c:a aac {output_dir}/demo-final.mp4"
        )

        return commands


class MarketingGenerator:
    """Generates marketing materials"""

    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)

    def generate_marketing_package(self, product_name: str,
                                   product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate complete marketing package"""
        output_dir = self.products_dir / product_name / "marketing"
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {
            "product": product_name,
            "files": {}
        }

        # Generate social media content
        social = self._generate_social_content(product_data)
        social_path = output_dir / "social-media.md"
        with open(social_path, "w", encoding="utf-8") as f:
            f.write(social)
        results["files"]["social_media"] = str(social_path)

        # Generate email templates
        emails = self._generate_email_templates(product_data)
        emails_path = output_dir / "email-templates.md"
        with open(emails_path, "w", encoding="utf-8") as f:
            f.write(emails)
        results["files"]["emails"] = str(emails_path)

        # Generate landing page content
        landing = self._generate_landing_page(product_data)
        landing_path = output_dir / "landing-page.md"
        with open(landing_path, "w", encoding="utf-8") as f:
            f.write(landing)
        results["files"]["landing_page"] = str(landing_path)

        # Generate blog post draft
        blog = self._generate_blog_post(product_data)
        blog_path = output_dir / "blog-post.md"
        with open(blog_path, "w", encoding="utf-8") as f:
            f.write(blog)
        results["files"]["blog_post"] = str(blog_path)

        return results

    def _generate_social_content(self, product_data: Dict[str, Any]) -> str:
        """Generate social media content"""
        name = product_data.get("name", "Product")
        features = product_data.get("features", [])[:3]

        return f"""# Social Media Content for {name}

## Twitter/X Thread
1/ Introducing {name}! 🚀

{product_data.get('description', 'A revolutionary product')}

Here's what makes it special:

2/ Key Features:
{chr(10).join(f"✅ {f.get('name', 'Feature')}" for f in features)}

3/ How it works:
[Simple explanation]

4/ Who is it for?
[Target audience]

5/ Get started today:
[Link]

## LinkedIn Post
We're excited to announce {name}! 

{product_data.get('description', 'A revolutionary product')}

Key highlights:
{chr(10).join(f"• {f.get('name', 'Feature')}" for f in features)}

Perfect for [target audience] who want to [benefit].

Try it now: [link]

## Reddit Post
Title: I built {name} - here's what I learned

Hi r/[subreddit],

I've been working on {name} - {product_data.get('description', 'a new tool')}.

Key features:
{chr(10).join(f"- {f.get('name', 'Feature')}" for f in features)}

Looking for feedback! What do you think?

[Link to project]
"""

    def _generate_email_templates(self, product_data: Dict[str, Any]) -> str:
        """Generate email templates"""
        name = product_data.get("name", "Product")

        return f"""# Email Templates for {name}

## Launch Announcement
Subject: Introducing {name} - [Value Proposition]

Hi [Name],

We're excited to announce {name}!

[Product description]

Key features:
{chr(10).join(f"- {f.get('name', 'Feature')}" for f in product_data.get('features', [])[:5])}

Try it now: [link]

Best regards,
[Company]

## Feature Highlight
Subject: See how {name} can [benefit]

Hi [Name],

Did you know {name} can help you [benefit]?

Here's how:
[Feature explanation]

Learn more: [link]

## Customer Testimonial Request
Subject: Share your {name} experience?

Hi [Name],

We'd love to hear about your experience with {name}!

Would you be willing to:
1. Share a brief testimonial
2. Provide a case study
3. Leave a review

Thank you for being a valued user!

Best,
[Company]
"""

    def _generate_landing_page(self, product_data: Dict[str, Any]) -> str:
        """Generate landing page content"""
        name = product_data.get("name", "Product")

        return f"""# Landing Page Content for {name}

## Hero Section
Headline: {name}
Subheadline: {product_data.get('tagline', 'Revolutionize your workflow')}
CTA: Get Started Free
Secondary CTA: Watch Demo

## Features Section
### Feature 1: [Name]
[Description]
[Benefit]

### Feature 2: [Name]
[Description]
[Benefit]

### Feature 3: [Name]
[Description]
[Benefit]

## How It Works
Step 1: [Action]
Step 2: [Action]
Step 3: [Action]

## Pricing
### Free Tier
- [Feature]
- [Feature]

### Pro Tier - $X/month
- Everything in Free
- [Feature]
- [Feature]

### Enterprise - Contact Us
- Everything in Pro
- [Feature]
- [Feature]

## FAQ
Q: What is {name}?
A: [Answer]

Q: How much does it cost?
A: [Answer]

Q: Is there a free trial?
A: [Answer]

## CTA Section
Ready to get started?
[Button: Start Free Trial]
[Button: Schedule Demo]
"""

    def _generate_blog_post(self, product_data: Dict[str, Any]) -> str:
        """Generate blog post draft"""
        name = product_data.get("name", "Product")

        return f"""# Introducing {name}: [Value Proposition]

Published: [Date]
Author: [Author]

## The Problem
[Problem description]

## The Solution
Introducing {name} - {product_data.get('description', 'a revolutionary product')}

## Key Features
{chr(10).join(f"### {f.get('name', 'Feature')}\n{f.get('description', '')}" for f in product_data.get('features', [])[:5])}

## How It Works
[Explanation]

## Getting Started
1. [Step 1]
2. [Step 2]
3. [Step 3]

## What's Next
[Future plans]

## Try It Today
[Link to product]

## Conclusion
[Summary]
"""
