"""
Video Generation Engine
Programmatically generate demo videos with annotations, highlights, and narration
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class VideoScene:
    """A scene in a demo video"""
    id: str
    title: str
    description: str
    duration_seconds: int
    actions: List[str] = field(default_factory=list)
    highlights: List[str] = field(default_factory=list)  # UI elements to highlight
    narration: str = ""
    annotations: List[str] = field(default_factory=list)  # Text overlays


@dataclass
class VideoConfig:
    """Video generation configuration"""
    title: str
    width: int = 1920
    height: int = 1080
    fps: int = 30
    output_format: str = "mp4"
    include_narration: bool = True
    include_annotations: bool = True
    include_highlights: bool = True
    background_color: str = "#1a1a2e"
    text_color: str = "#ffffff"
    highlight_color: str = "#ff6b6b"


class VideoGenerationEngine:
    """Engine for generating demo videos"""

    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)

    def create_demo_script(self, product_data: Dict[str, Any]) -> List[VideoScene]:
        """Create a video demo script from product data"""
        name = product_data.get("name", "Product")
        description = product_data.get("description", "")
        features = product_data.get("features", [])

        scenes = []

        # Scene 1: Introduction
        scenes.append(VideoScene(
            id="intro",
            title=f"Welcome to {name}",
            description=description,
            duration_seconds=10,
            actions=["fade_in_logo", "show_title", "display_tagline"],
            highlights=[],
            narration=f"Welcome to {name}! {description}",
            annotations=[f"{name}", "Revolutionize Your Workflow"]
        ))

        # Scene 2: Problem Statement
        scenes.append(VideoScene(
            id="problem",
            title="The Problem",
            description="Challenges users face",
            duration_seconds=8,
            actions=["show_pain_points", "animate_icons"],
            highlights=["problem_icon"],
            narration="Many teams struggle with inefficient workflows and complex tools.",
            annotations=["Time-consuming", "Complex", "Expensive"]
        ))

        # Scene 3: Solution Overview
        scenes.append(VideoScene(
            id="solution",
            title=f"How {name} Solves It",
            description="Our solution",
            duration_seconds=10,
            actions=["show_solution", "animate_features"],
            highlights=["solution_icon"],
            narration=f"{name} provides a simple, powerful solution to these challenges.",
            annotations=["Simple", "Powerful", "Affordable"]
        ))

        # Scene 4-N: Feature walkthroughs
        for i, feature in enumerate(features[:5], 1):
            scenes.append(VideoScene(
                id=f"feature-{i}",
                title=f"Feature {i}: {feature.get('name', 'Feature')}",
                description=feature.get("description", ""),
                duration_seconds=12,
                actions=[f"show_feature_{i}", "demonstrate_workflow"],
                highlights=[f"feature_{i}_button", f"feature_{i}_output"],
                narration=f"Feature {i}: {feature.get('description', '')}",
                annotations=[
                    f"Click here to {feature.get('name', 'use feature')}",
                    "See the results instantly"
                ]
            ))

        # Final scene: Call to action
        scenes.append(VideoScene(
            id="cta",
            title="Get Started Today",
            description="How to begin",
            duration_seconds=8,
            actions=["show_pricing", "display_cta"],
            highlights=["signup_button", "pricing"],
            narration=f"Ready to get started with {name}? Sign up today and transform your workflow.",
            annotations=["Start Free Trial", "No Credit Card Required"]
        ))

        return scenes

    def generate_video_script_markdown(self, scenes: List[VideoScene],
                                       product_name: str) -> str:
        """Generate video script as markdown"""
        script = f"""# {product_name} - Demo Video Script

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Video Overview

- **Total Scenes:** {len(scenes)}
- **Estimated Duration:** {sum(s.duration_seconds for s in scenes)} seconds
- **Format:** 1920x1080 @ 30fps

## Scenes

"""

        for i, scene in enumerate(scenes, 1):
            script += f"### Scene {i}: {scene.title}\n\n"
            script += f"**Duration:** {scene.duration_seconds} seconds\n\n"
            script += f"**Description:** {scene.description}\n\n"

            if scene.narration:
                script += f"**Narration:**\n> {scene.narration}\n\n"

            if scene.actions:
                script += "**Actions:**\n"
                for action in scene.actions:
                    script += f"- {action}\n"
                script += "\n"

            if scene.highlights:
                script += "**UI Elements to Highlight:**\n"
                for highlight in scene.highlights:
                    script += f"- `{highlight}` (red circle/arrow)\n"
                script += "\n"

            if scene.annotations:
                script += "**Text Overlays:**\n"
                for annotation in scene.annotations:
                    script += f"- \"{annotation}\"\n"
                script += "\n"

            script += "---\n\n"

        script += """## Production Notes

### Visual Style
- Background: Dark theme (#1a1a2e)
- Text: White (#ffffff)
- Highlights: Red (#ff6b6b)
- Font: Modern sans-serif
- Transitions: Smooth fades (0.5s)

### Audio
- Background music: Soft, professional
- Narration: Clear, friendly voice
- Sound effects: Subtle UI sounds

### Tools
- Screen recording: Playwright/Selenium
- Video editing: ffmpeg/moviepy
- Annotations: OpenCV/PIL
- TTS: Google TTS / Azure Speech
- Music: Royalty-free library

### Generation Pipeline
1. Capture screenshots of key features
2. Record screen interactions
3. Add highlights and annotations
4. Generate narration audio
5. Combine with background music
6. Export final video

### Output Formats
- MP4 (1920x1080)
- WebM (smaller file size)
- GIF (for previews)
"""
        return script

    def generate_ffmpeg_commands(self, scenes: List[VideoScene],
                                 output_dir: Path) -> List[str]:
        """Generate ffmpeg commands for video creation"""
        commands = []

        # Create video from scenes
        for i, scene in enumerate(scenes, 1):
            # Create individual scene
            commands.append(
                f"# Scene {i}: {scene.title}\n"
                f"ffmpeg -f lavfi -i color=c=0x1a1a2e:s=1920x1080:d={scene.duration_seconds} "
                f"-vf \"drawtext=text='{scene.title}':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=(h-text_h)/2\" "
                f"-c:v libx264 -pix_fmt yuv420p {output_dir}/scene_{i:03d}.mp4"
            )

        # Concatenate all scenes
        scene_list = "|".join(f"{output_dir}/scene_{i:03d}.mp4" for i in range(1, len(scenes) + 1))
        commands.append(
            f"# Concatenate all scenes\n"
            f"ffmpeg -i \"concat:{scene_list}\" -c copy {output_dir}/final.mp4"
        )

        # Add background music
        commands.append(
            f"# Add background music\n"
            f"ffmpeg -i {output_dir}/final.mp4 -i background_music.mp3 "
            f"-filter_complex \"[0:a][1:a]amix=inputs=2:duration=first\" "
            f"{output_dir}/final_with_music.mp4"
        )

        return commands

    def create_video_project(self, product_name: str,
                              product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create complete video project"""
        output_dir = self.products_dir / product_name / "videos"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create scenes
        scenes = self.create_demo_script(product_data)

        # Generate script
        script = self.generate_video_script_markdown(scenes, product_name)
        script_path = output_dir / "demo-script.md"
        script_path.write_text(script, encoding="utf-8")

        # Generate ffmpeg commands
        commands = self.generate_ffmpeg_commands(scenes, output_dir)
        commands_path = output_dir / "video-commands.sh"
        with open(commands_path, "w", encoding="utf-8") as f:
            f.write("#!/bin/bash\n\n")
            f.write("# Video generation commands\n")
            f.write(f"# Run these commands to create the {product_name} demo video\n\n")
            for cmd in commands:
                f.write(f"{cmd}\n\n")

        return {
            "product": product_name,
            "scenes": len(scenes),
            "duration_seconds": sum(s.duration_seconds for s in scenes),
            "script_path": str(script_path),
            "commands_path": str(commands_path),
            "scenes_detail": [
                {
                    "id": s.id,
                    "title": s.title,
                    "duration": s.duration_seconds
                }
                for s in scenes
            ]
        }
