# Image Skill

## Purpose
Generate, edit, enhance, and analyze images for any Product Forge project. Backed by ComfyUI (node-based workflow) with Stable Diffusion XL, FLUX, ControlNet, IP-Adapter, and the SDXL ecosystem.

## Stage
Available to any agent that needs image output. Most commonly used by:
- `design` agent — generate UI mockups, hero illustrations
- `marketing` agent — ad creatives, social media graphics
- `presentation` agent — slide visuals, OG images, hero shots
- `ideation` agent — mood boards for brainstorm
- `customer-onboarding` agent — illustrated tutorials
- `document` agent — diagram illustrations

## Source
- Framework: https://github.com/comfyanonymous/ComfyUI (most flexible)
- Models: https://github.com/Stability-AI/sdxl, https://github.com/black-forest-labs/flux
- ControlNet: https://github.com/lllyasviel/ControlNet
- IP-Adapter (style transfer): https://github.com/cubiq/ComfyUI_IPAdapter_plus
- Upscalers: https://github.com/city96/SD-Latent-Upscaler, RealESRGAN
- License: Mostly MIT/Apache for the framework, but **each model has its own license** (often CreativeML Open RAIL-M for SD, FLUX.1-dev is non-commercial)

## When to use
- Need a hero image, illustration, or concept art
- Need product mockups or UI screenshots
- Need to upscale / enhance an existing image
- Need to remove background, inpaint, or outpaint
- Need to apply a style reference to new images
- Need image-to-image transformation (sketch → photo, etc.)

## When NOT to use
- Logos and brand marks (use design tools — vector > generated raster)
- UI components (use design agent + real components)
- Product screenshots of actual app (capture from running app)
- Photographic accuracy of real people (ethics + model limits)
- 3D models (use a 3D skill)

## Inputs
- Text prompt (with optional negative prompt)
- Reference image (for img2img, inpainting, style transfer)
- ControlNet conditioning (edge, depth, pose, canny)
- IP-Adapter reference (for style)
- LoRA (for fine-tuned style/concept)
- Resolution + aspect ratio
- Seed (for reproducibility)
- Sampler settings (steps, CFG, scheduler)

## Outputs
- PNG / WEBP / JPEG image at requested resolution
- Metadata JSON (prompt, seed, settings) for reproducibility
- Optional mask layer (for inpainting workflows)
- Comparison sheet (A/B of variants)

## Workflow

### 1. Choose a model
| Use case | Model |
|---|---|
| Default photoreal / general | SDXL 1.0 (CreativeML Open RAIL-M) |
| High-fidelity realism / text | FLUX.1-dev (non-commercial license) or FLUX.1-schnell (Apache 2.0) |
| Anime / illustration | AnythingXL, CounterfeitXL |
| Product photo | RealVisXL, JuggernautXL |
| Vector / flat illustration | SDXL + flat illustration LoRA |
| Brand-safe for resale | Only use models with permissive license (FLUX.1-schnell, SDXL, SD3) |

### 2. Choose a workflow

**Text → Image** (most common):
```python
# In ComfyUI: load checkpoint, CLIPTextEncode x2 (positive + negative),
# KSampler, VAEDecode, SaveImage
# Or via ComfyUI HTTP API:
import json, urllib.request, websocket
prompt = {
    "3": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 30, "cfg": 7, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0, ...}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "modern hero image of a fintech app on a desk, soft lighting, photoreal", "clip": ["4", 1]}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, distorted", "clip": ["4", 1]}},
    ...
}
```

**Image → Image** (sketch → photo, low denoise):
- Use the same workflow, but pass an input image into a `VAEEncode` first
- Denoise 0.4-0.7 for subtle changes, 0.7-1.0 for strong reinterpretation

**Inpainting** (selective regeneration):
- Use a mask image (white = regenerate, black = keep)
- Connect mask to `SetLatentNoiseMask` before KSampler

**ControlNet** (structure-guided):
- Canny: extract edges → condition on shape
- Depth: extract depth map → condition on3D structure
- Pose: extract human pose → condition on pose

**IP-Adapter** (style transfer):
- Provide reference style image
- Strength controls how much style bleeds in

**Upscale** (resolution boost):
- Use RealESRGAN or SD latent upscaler
- 4x is standard

### 3. Run via HTTP API
ComfyUI exposes a queue API:
```bash
# Submit prompt
curl -X POST http://localhost:8188/prompt \
  -H "Content-Type: application/json" \
  -d @prompt.json

# WebSocket: listen for execution_done, fetch image from /view?filename=...
```

Or use the Python wrapper:
```python
from comfy import ComfyUI
client = ComfyUI("http://localhost:8188")
result = client.run(prompt, output_dir="./outputs")
```

### 4. Common quality settings
| Setting | Value | Why |
|---|---|---|
| Steps | 25-35 | Diminishing returns past ~35 |
| CFG | 5-9 | 7 is the sweet spot; lower = creative, higher = prompt-faithful |
| Sampler | dpmpp_2m + karras | Best general quality/speed tradeoff |
| Resolution | 1024x1024 (SDXL), 1024x1024 or 1024x768 (FLUX) | Native |
| Aspect ratios | 1:1, 16:9, 9:16, 4:3 | Match final use |
| Seed | random or pinned | Pin for reproducibility |

### 5. Manage model licenses
**Critical**: each model has its own license. Check `models/checkpoints/<model>.safetensors` metadata or the HuggingFace model card.

| Model family | License | Commercial use |
|---|---|---|
| SDXL 1.0 | CreativeML Open RAIL-M | ✅ Yes (with use restrictions) |
| FLUX.1-schnell | Apache 2.0 | ✅ Yes |
| FLUX.1-dev | FLUX.1-dev Non-Commercial | ❌ No |
| SD3 / SD3.5 | Stability AI Community License | ✅ Yes (with revenue cap) |
| RealVisXL | CreativeML Open RAIL-M | ✅ Yes |
| JuggernautXL | Custom — check per version | Varies |

**Rule:** Before shipping a generated image commercially, confirm the model license allows it. Add to pre-production stage 7 license scan.

## Quality checks
- [ ] Output saved with metadata JSON (prompt, seed, model, settings)
- [ ] Resolution matches target (no upscaling artifact if pixel-peeped)
- [ ] No NSFW / brand-violating content (run safety checker)
- [ ] Style consistent across the set (use shared LoRA or fixed seed)
- [ ] Model license logged in `reports/license-compliance.md`

## Rules
1. NEVER publish AI-generated images of real people without consent
2. NEVER remove C2PA / watermarks from AI-generated images
3. ALWAYS save metadata (prompt, seed, model) for reproducibility
4. ALWAYS check the model license before commercial use
5. PREFER FLUX.1-schnell or SDXL over FLUX.1-dev for commercial products
6. PREFER node-based workflows over web UIs for reproducibility
7. NEVER generate images that impersonate brands / logos without permission