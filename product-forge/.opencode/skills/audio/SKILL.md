# Audio Skill

## Purpose
Add voice capabilities to any Product Forge project: text-to-speech, speech-to-text, voice cloning, voice design, dictation widget, audio narration. Backed by VoiceStudio — a local-first, open-source ElevenLabs alternative.

## Stage
Available to any agent that needs audio output. Most commonly used by:
- `presentation` agent — narrate slides
- `customer-onboarding` agent — voice welcome + tutorials
- `marketing` agent — audio ads, podcast intros
- `ideation` agent — voice-driven idea capture
- `maintenance` agent — voice alerts / call-tree

## Source
- Repo: https://github.com/debpalash/VoiceStudio
- License: AGPL-3.0 (application) — see "License caveats" below
- Stars: 15.7K, actively updated (Sep 2026)
- Local-first: runs on your hardware, audio never leaves your machine unless you opt in

## When to use
- User wants "voice commands in AI prompt/chats" — use the dictation widget
- User wants product narrated for demos — use OpenAI-compatible TTS endpoint
- User wants voice cloning for personalized messages — use VoiceStudio clone flow
- User wants call-tree alerts / voice notifications — use TTS API + outbound call
- User wants podcast / audiobook generation — use VoiceStudio batch

## When NOT to use
- Real-time conversational voice agents (use LiveKit + an STT/LLM pipeline, not VoiceStudio)
- Music generation (use AudioCraft/MusicGen — separate audio-music skill)
- Pure backend code that (no audio voice) — skip

## Inputs
- Text to text to-speech: plain string or SSML
- Voice reference: 3-15s WAV clip of speaker (for cloning)
- Language code: ISO 639-1 (646 supported)
- Engine choice: see engines table below
- For dictation: user microphone + push-to-talk shortcut

## Outputs
- Audio file (WAV / MP3 / Opus / AAC / FLAC / PCM)
- Transcript (text + word-level timing)
- Cloned voice profile (saved locally)
- Dubbed video (audio + subtitle track)

## Workflow

### 1. Pick an engine
VoiceStudio exposes 16 TTS + 11 ASR engines via a unified registry.

| Use case | Recommended engine |
|---|---|
| Default, high-fidelity zero-shot clone | OmniVoice (default) or CosyVoice 3 |
| Apple Silicon | MLX-Audio or OmniVoice MPS |
| NVIDIA GPU 8GB+ VRAM | OmniVoice or CosyVoice 3 |
| Low VRAM / CPU only | PocketTTS, Sherpa-ONNX, or KittenTTS |
| Real-time dictation | Sherpa-ONNX (CPU streaming) or Faster-Whisper |
| Subtitle-grade transcription with diarization | WhisperX |
| Multilingual dubbing | OmniVoice + WhisperX |

### 2. Use the OpenAI-compatible HTTP API
VoiceStudio serves `localhost:3900` with drop-in OpenAI client support:

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:3900/v1", api_key="local")

# Text → speech
with client.audio.speech.with_streaming_response.create(
    model="tts-1",
    voice="<profile-id>",          # or "default"
    input="Made on my own hardware.",
    response_format="wav",
) as response:
    response.stream_to_file("speech.wav")

# Speech → text
with open("speech.wav", "rb") as f:
    transcript = client.audio.transcriptions.create(
        model="whisperx",
        file=f,
        response_format="verbose_json",   # includes word timestamps
    )
```

Or via curl:
```bash
curl http://localhost:3900/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"tts-1","input":"Hello world","voice":"default","response_format":"wav"}' \
  --output speech.wav
```

### 3. Use the MCP server (preferred for agents)
VoiceStudio mounts MCP at `http://localhost:3900/mcp` for Claude Code, Cursor, AI agents:

```json
{
  "mcpServers": {
    "voicestudio": {
      "url": "http://localhost:3900/mcp"
    }
  }
}
```

Exposed tools: `generate_speech`, `clone_voice`, `transcribe`, plus file streaming modes.

### 4. Install the official skill (alternative)
```bash
npx skills add debpalash/VoiceStudio
```
Drops two skills: `omnivoice` (TTS/STT) and `oss-maintainer` (repo workflow).

### 5. Dictation widget (voice commands in prompts)
- System-wide shortcut: Win/Cmd+Shift+D (configurable)
- Live partial transcript + final utterance
- Optional local-LLM cleanup before text insertion
- Use the bundled Rust control sidecar to insert text into any focused input

### 6. Voice cloning best practice
- Use 5-15s clean reference (one speaker, close mic, no music/reverb)
- Match tone + pace to desired output
- Cloning is zero-shot — clip is a prompt, not training data
- Consent required — only clone voices you have permission for

## Quality checks
- [ ] VoiceStudio service running on localhost:3900 (check `curl http://localhost:3900/.well-known/voicestudio-speech`)
- [ ] Selected engine compatible with hardware (CPU vs CUDA vs MPS)
- [ ] At least one voice profile exists (`GET /v1/audio/voices`)
- [ ] Watermark detection (AudioSeal) enabled by default
- [ ] If customer-facing: license compliance documented (see License caveats)

## License caveats — AGPL-3.0 (CRITICAL)

VoiceStudio's application license is **AGPL-3.0**, which has stricter requirements than MIT/Apache:

| Scenario | Risk | What to do |
|---|---|---|
| **Internal tool** — only your team uses it | ✅ Low | Use freely. Just keep attribution. |
| **Customer-facing SaaS** — users reach VoiceStudio over the network | ⚠️ High | You must either: (a) release your full SaaS source under AGPL, or (b) buy a commercial license from VoiceStudio@palash.dev |
| **Bundled in on-prem product** — you ship a binary to customers | ✅ Low | AGPL only triggers on network service. Ship as offline app, fine. |
| **REST/MCP calls from your backend** — your backend calls VoiceStudio as an internal service | ⚠️ Grey zone | If your backend is a SaaS others reach, the AGPL "network clause" applies. Document or license. |
| **Voice cloning output** — you clone someone's voice and ship that audio | ✅ Low | Audio is not "the work" — license doesn't restrict generated audio. But check the model license (OmniVoice weights are CC-BY-NC; some engines Apache-2.0). |
| **Just listing VoiceStudio as a dependency** in docs | ✅ Low | Attribution only. |

### Concrete rule for Product Forge

If your product has a **voice agent** that customers reach over the network (chat-with-voice, voice assistant, call bot), and that voice agent is powered by VoiceStudio on your backend, you have two options:

1. **Open-source your voice agent module** under AGPL-3.0 (the entire module that interacts with VoiceStudio)
2. **Buy a commercial license** from `VoiceStudio@palash.dev` (VoiceStudio-owned code only — does not relicense third-party models)

If your voice feature is **purely internal** (your team's dictation, internal call tree, internal demo), no licensing action needed.

### License compliance audit

Run as part of pre-production stage 7 (Legal/Compliance):

```bash
# Detect AGPL/GPL/SSPL in dependency tree
pip-licenses --format=markdown --with-system | grep -iE "agpl|sspl|gpl"
npm ls --json | jq -r '.dependencies | keys[]' | xargs -I {} npm view {} license

# Document VoiceStudio usage scope
cat > reports/license-compliance.md <<EOF
# License Compliance Report
Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

## VoiceStudio usage
- Component: [TTS / STT / clone / dictation]
- Scope: [internal tool / customer-facing SaaS / on-prem binary]
- License: AGPL-3.0 (VoiceStudio app) + per-engine terms
- Resolution: [n/a / commercial license obtained / open-source module / only internal use]
- License file: reports/voicestudio-commercial-license.pdf (if applicable)
EOF
```

## Rules
1. NEVER clone a voice without documented consent
2. ALWAYS enable AudioSeal watermark by default
3. ALWAYS check engine model license before commercial use (OmniVoice weights are CC-BY-NC)
4. ALWAYS document AGPL scope before customer-facing deployment
5. PREFER local-only operation; remote workers + external ASR require explicit opt-in
6. NEVER expose VoiceStudio's REST/MCP endpoint to the public internet — keep it loopback