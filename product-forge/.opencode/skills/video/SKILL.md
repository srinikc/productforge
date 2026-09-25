# Video Skill

## Purpose
Generate, edit, and analyze videos for any Product Forge project: text-to-video, image-to-video, video-to-video, lip-sync, dubbing, motion transfer. Backed by AnimateDiff (motion from text), Stable Video Diffusion (image → video), and complementary tools.

## Stage
Available to any agent that needs video output. Most commonly used by:
- `presentation` agent — demo videos, animated walkthroughs
- `marketing` agent — ad videos, social media reels, product trailers
- `customer-onboarding` agent — video tutorials, explainers
- `ideation` agent — concept visualization
- `design` agent — animated mockups

## Source
- **AnimateDiff**: https://github.com/guoyww/AnimateDiff (text → motion adapter for SD)
- **Stable Video Diffusion (SVD)**: https://github.com/Stability-AI/generative-models (image → video)
- **AnimateDiff Lightning**: https://github.com/bytedance/AnimateDiff-Lightning (fast version)
- **Hotshot-XL**: https://github.com/hotshotco/Hotshot-XL (text → GIF)
- **Deforum**: https://github.com/deforum-art/deforum-stable-diffusion (parameterized video)
- **ComfyUI-AnimateDiff-Evolved**: https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved (ComfyUI integration)
- License: Mostly MIT/Apache for code; **model licenses vary**

## When to use
- Need a 5-30s video clip from a text prompt
- Need to animate a still image (image → video)
- Need a stylized animation (AnimateDiff + LoRA)
- Need product demo footage (animate screenshots)
- Need a lip-synced avatar talking (use LivePortrait + audio skill)
- Need short social media reels

## When NOT to use
- Long-form videos >1 min (too compute-intensive, use traditional editing)
- Realistic human faces for marketing (use Sora / Runway / proprietary tools, not these open ones)
- High frame-rate >30fps action footage (current models cap at ~24fps)
- Production broadcast content (models still have artifacts)

## Inputs
- Text prompt (motion description)
- Reference image (for image → video)
- Optional LoRA (style, motion direction)
- Optional ControlNet (depth, pose conditioning)
- Audio (for lip-sync or motion-anchored video)
- Resolution, fps, length

## Outputs
- MP4 / WebM / GIF video file
- Metadata (prompt, seed, frame count, model)
- Optional audio track (synced or separate)

## Workflow

### 1. Choose a tool by use case
| Use case | Recommended tool |
|---|---|
| Stylized short clip (anime, painterly, etc.) | AnimateDiff + SDXL |
| Image → short video (subtle motion) | Stable Video Diffusion (SVD) |
| Fast iteration (<5s/clip) | AnimateDiff Lightning |
| Text → GIF sticker | Hotshot-XL |
| Parameterized video (camera, zoom, rotation) | Deforum |
| Lip-sync to audio | LivePortrait + SadTalker (separate workflow) |
| Long storyboard scenes | SVD-XT up to 4s, or chain via frame interpolation |

### 2. AnimateDiff workflow (most common)

**Setup in ComfyUI:**
1. Load SDXL checkpoint
2. Load AnimateDiff motion module (e.g., `mm_sd15_v2.ckpt` or `mm_sdxl_v10_beta.ckpt`)
3. Apply AnimateDiff LoRA for speed (`lightning` style)
4. Optional: apply ControlNet (e.g., depth for camera motion)
5. Prompt for both content AND motion style
6. KSampler with `frame_count=16-32`, `steps=15-25`
7. Save as MP4 / GIF

**Prompt template:**
```
[content description], [motion keywords]
# Good motion keywords:
- "slow camera push-in", "static shot with gentle wind", "subtle parallax",
  "smooth dolly right", "handheld gentle shake", "smooth pan left"
# Avoid:
- "fast action", "explosive", "rapid zoom"  (current models struggle)
```

**Example ComfyUI workflow JSON** (AnimateDiff Lightning):
```python
{
  "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdxl_base_1.0.safetensors"}},
  "2": {"class_type": "AnimateDiffLoader", "inputs": {"model": ["1", 0], "motion_model": "mm_sdxl_v10_beta.ckpt"}},
  "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "modern fintech app on a wooden desk, slow camera push-in, soft window light", "clip": ["1", 1]}},
  "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, distorted, jittery, low quality", "clip": ["1", 1]}},
  "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 576, "batch_size": 16}},
  "6": {"class_type": "KSamplerAdvanced", "inputs": {"model": ["2", 0], "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["5", 0], "steps": 15, "cfg": 7, "sampler_name": "dpmpp_2m", "scheduler": "karras"}},
  "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
  "8": {"class_type": "VHS_VideoCombine", "inputs": {"frames": ["7", 0], "fps": 8, "format": "video/h264-mp4", "save_output": True}}
}
```

### 3. Stable Video Diffusion (image → video)
Best for "make this still image move slightly":
1. Input image → SVD encoder
2. Motion conditioning (motion bucket ID + augmentation)
3. 14-25 frames, 4s @ 6fps or 576x1024
4. Decode → save as MP4

Use cases: subtle product shots, "breathing" UI mockups, parallax hero images.

### 4. Lip-sync (when voice is involved)
For a talking head or avatar:
1. Generate base video (AnimateDiff or SVD) with neutral face
2. Apply SadTalker or LivePortrait to drive face with audio
3. Mux with audio track

For multilingual dubbing:
1. Extract source audio → STT (audio skill) → translated text
2. TTS translated text (audio skill)
3. Apply lip-sync to translated audio
4. Mux with original video

### 5. Quality settings
| Setting | Typical value | Notes |
|---|---|---|
| Frames | 16-32 | Sweet spot; longer = drift |
| FPS | 8-12 | AnimateDiff native; interpolate to 24/30 |
| Steps | 15-25 | Higher = better, slower |
| CFG | 6-8 | Lower = more motion |
| Resolution | 512x512 (SD1.5), 1024x576 (SDXL) | Native model size |
| Motion strength | 1.0 default | Higher = more motion, more drift |

### 6. Frame interpolation (optional)
For smoother output, use RIFE or FILM to interpolate 8fps → 24fps:
```bash
# RIFE CLI
python inference_video.py --exp=1 --video=input.mp4 --output=output_24fps.mp4
```

### 7. Audio integration
- Combine with audio skill for: voice-over narration, lip-sync, background music
- Tools: ffmpeg for muxing, Auto-Editor for silence removal

## Quality checks
- [ ] Output saved with metadata JSON
- [ ] Frame count + fps logged
- [ ] No NSFW / brand-violating content (safety checker)
- [ ] Lip-sync accurate to ±100ms (if applicable)
- [ ] Audio levels normalized to -16 LUFS
- [ ] Resolution consistent (no upscaling artifacts)
- [ ] Model license logged

## Model licenses
| Model | License | Commercial use |
|---|---|---|
| AnimateDiff v1/v2 (mm_sd15) | CreativeML Open RAIL-M | ✅ Yes (with restrictions) |
| AnimateDiff SDXL | CreativeML Open RAIL-M | ✅ Yes |
| AnimateDiff Lightning | Apache 2.0 | ✅ Yes |
| Stable Video Diffusion | Stability AI Non-Commercial | ❌ No (commercial license required) |
| Hotshot-XL | CreativeML Open RAIL-M | ✅ Yes |
| MotionCtrl | MIT | ✅ Yes |

**Rule:** SVD is non-commercial. For commercial video generation, prefer **AnimateDiff** (CreativeML Open RAIL-M with revenue threshold) or **AnimateDiff Lightning** (Apache 2.0).

## Rules
1. NEVER generate videos of real people without documented consent
2. NEVER use SVD for commercial products without obtaining Stability AI commercial license
3. ALWAYS save metadata (prompt, model, frames, settings)
4. PREFER AnimateDiff Lightning for iteration speed
5. ALWAYS check model license before commercial use
6. PREFER 16-32 frames at 8-12fps + RIFE interpolation over direct 24fps generation
7. NEVER ship un-interpolated low-fps video to production