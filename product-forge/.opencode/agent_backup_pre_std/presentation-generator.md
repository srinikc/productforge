# Presentation Generator Agent

## Purpose
Generate product presentations, documentation packages, and demo videos after successful product build.

## Trigger
- After `validate` stage completes with PASS verdict
- After `package` stage produces artifacts
- On-demand: `/pipeline present [project]`

## Capabilities

### 1. Presentation Generation (PPT/PDF)

**Auto-generate product presentation with:**

1. **Cover Slide**
   - Product name, tagline, version
   - Company/developer branding
   - Date

2. **Product Overview**
   - What it does (1-2 sentences)
   - Who it's for
   - Key value proposition

3. **Features Overview**
   - Core features list (5-10)
   - Feature screenshots/diagrams
   - Use cases

4. **Getting Started**
   - Installation steps
   - Quick start guide
   - Configuration

5. **How to Use**
   - Main workflows
   - Key interactions
   - Tips and tricks

6. **Architecture Overview**
   - System diagram
   - Tech stack
   - Integration points

7. **API Reference**
   - Key endpoints
   - Code examples
   - SDKs available

8. **Deployment**
   - Deployment options
   - Cloud providers
   - Self-hosted

9. **Support & Resources**
   - Documentation links
   - Community channels
   - Contact information

10. **Call to Action**
    - Try it now
    - Schedule demo
    - Contact sales

**Output Formats:**
- PowerPoint (.pptx) - for sales/team presentations
- PDF - for documentation/sharing
- HTML - for web embedding

### 2. Documentation Package

**Complete documentation bundle:**

```
docs/
├── getting-started/
│   ├── installation.md
│   ├── quickstart.md
│   └── configuration.md
├── user-guide/
│   ├── overview.md
│   ├── features.md
│   └── workflows.md
├── api-reference/
│   ├── endpoints.md
│   ├── authentication.md
│   └── examples.md
├── deployment/
│   ├── options.md
│   ├── cloud.md
│   └── self-hosted.md
├── support/
│   ├── faq.md
│   ├── troubleshooting.md
│   └── contact.md
└── index.md
```

### 3. Demo Video Generation

**Automated video demo with inline highlighting:**

**Video Structure (2-5 minutes):**

1. **Intro (10-15s)**
   - Product name and tagline
   - Problem statement
   - What you'll see

2. **Feature Walkthrough (60-120s)**
   - Screen recording with annotations
   - Highlight key UI elements
   - Show core workflows
   - Inline text overlays explaining actions

3. **Key Benefits (30-45s)**
   - Before/after comparison
   - Time saved
   - Cost savings

4. **Call to Action (10-15s)**
   - How to get started
   - Links and contacts

**Video Generation Technical Approach:**

```python
# Pseudocode for video generation
class VideoGenerator:
    def generate_demo_video(self, product):
        # 1. Capture screenshots of key features
        screenshots = self.capture_feature_screenshots(product)

        # 2. Generate narration script
        script = self.generate_narration_script(product)

        # 3. Create video with overlays
        video = self.create_video(
            screenshots=screenshots,
            script=script,
            overlays=self.generate_overlays(product),
            transitions=self.select_transitions(product)
        )

        # 4. Add audio (TTS or music)
        video = self.add_audio(video, script)

        # 5. Export
        video.export("demo.mp4")
        return video
```

**Highlighting Features:**
- Red circles/arrows on important UI elements
- Text callouts explaining functionality
- Progress indicators showing user journey
- Before/after comparisons
- Code snippets for technical demos

### 4. Marketing Materials

**Auto-generated marketing assets:**

1. **Social Media Content**
   - Twitter/X thread (280 chars each)
   - LinkedIn post (professional)
   - Reddit post (community-focused)
   - Product Hunt description

2. **Email Templates**
   - Launch announcement
   - Feature highlight
   - Customer testimonial request

3. **Landing Page Content**
   - Hero section
   - Features section
   - Pricing section
   - FAQ section

4. **Blog Post Draft**
   - Introduction
   - Problem/solution
   - Features deep dive
   - How to get started
   - Conclusion

## Implementation Files

```
core/presentation_generator.py    # Main presentation generation
core/video_generator.py          # Video demo generation
core/marketing_generator.py      # Marketing materials
core/doc_package.py              # Documentation packaging
templates/
├── presentation.pptx            # PowerPoint template
├── presentation.html            # HTML presentation template
├── video_script.md               # Video script template
└── marketing/
    ├── twitter.md
    ├── linkedin.md
    ├── reddit.md
    └── email.md
```

## Commands

| Command | Description |
|---------|-------------|
| `/pipeline present [project]` | Generate full presentation package |
| `/pipeline present ppt [project]` | Generate PowerPoint only |
| `/pipeline present pdf [project]` | Generate PDF only |
| `/pipeline present video [project]` | Generate demo video |
| `/pipeline present docs [project]` | Generate documentation package |
| `/pipeline present marketing [project]` | Generate marketing materials |

## Model Recommendations

| Task | Recommended Model | Free Alternative |
|------|-------------------|------------------|
| Script writing | mimo-v2.5-free | mimo-v2.5-free |
| Narration (TTS) | See `.opencode/skills/audio/SKILL.md` (VoiceStudio) | Piper TTS (MIT) |
| Video editing | Use ffmpeg/moviepy | Use ffmpeg |
| Screenshot capture | Use Playwright | Use Playwright |

## Skills

This agent composes results from multiple skills in `.opencode/skills/`:

| Skill | Use for | Reference |
|---|---|---|
| **slides** | Interactive React-based decks (preferred over PPTX) | `.opencode/skills/slides/SKILL.md` |
| **audio** | Voice narration, podcast version of deck, lip-sync videos | `.opencode/skills/audio/SKILL.md` |
| **image** | Hero images, OG images, slide visuals | `.opencode/skills/image/SKILL.md` |
| **video** | Demo videos, animated walkthroughs, social media reels | `.opencode/skills/video/SKILL.md` |

**Recommended workflow for new projects:**
1. Start with `slides` skill to scaffold interactive React deck (preferred — better quality than PPTX)
2. Generate hero / OG / illustration assets via `image` skill
3. Add voice narration via `audio` skill (optional — turn deck into podcast)
4. Generate demo video via `video` skill (animated walkthrough)
5. Fall back to PPTX/PDF export only if the user explicitly requests it

**Note on AGPL:** If voice narration is needed, follow the license guidance in `.opencode/skills/audio/AGPL-RISK.md`. For customer-facing SaaS, obtain a VoiceStudio commercial license or use a non-AGPL alternative (CosyVoice 3, Piper, OpenAI TTS, etc.).

## Quality Checks

Before generating:
- All tests passing
- Documentation complete
- Screenshots captured
- Scripts reviewed
- Branding consistent

## Integration Points

- Reads from `pipeline/` for product data
- Reads from `docs/` for documentation
- Reads from `reports/` for test results
- Outputs to `presentations/` directory
- Outputs to `videos/` directory
- Outputs to `marketing/` directory
