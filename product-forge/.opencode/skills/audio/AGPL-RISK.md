# AGPL-3.0 License Risk Analysis for Product Forge

## TL;DR

**VoiceStudio is AGPL-3.0**. This affects Product Forge only if (a) you ship a network-accessible SaaS that uses VoiceStudio as a backend service, or (b) you distribute VoiceStudio itself with a closed-source product. **For internal tools and on-prem binaries, no action needed.** For customer-facing SaaS, you need either a commercial license from `VoiceStudio@palash.dev` or to open-source the integrating module.

---

## What is AGPL-3.0?

GNU Affero General Public License v3.0. It's GPL with one critical addition — **the "network clause"**:

> "If you modify the Program, your modified version must prominently offer all users interacting with it remotely (through a network) an opportunity to receive the Corresponding Source of your version."

In other words: if a user reaches your code over the network, and your code is derived from AGPL work, they can demand the source of your version.

**This is what differentiates AGPL from regular GPL.** Regular GPL only triggers when you *distribute* binaries. AGPL triggers when you *operate as a service* over the network.

## Why this matters for Product Forge

Product Forge is a multi-agent orchestration system. If a Product Forge project has a **voice agent** (chat with voice, voice assistant, call bot, voice command in AI prompts) that customers reach over the network, and that voice agent is backed by VoiceStudio on your backend:

- You have a network-accessible service
- That service is derived from VoiceStudio (which is AGPL)
- AGPL clause 13 triggers
- You must either:
  - **Release the source** of the voice agent module (and any code that links VoiceStudio) under AGPL-3.0, OR
  - **Buy a commercial license** from VoiceStudio (palash offers one — `VoiceStudio@palash.dev`)

## Risk matrix by usage scenario

| Scenario | AGPL risk | Required action |
|---|---|---|
| Your team uses VoiceStudio internally (dictation, call tree, demos) | ✅ None | No action — internal team is not "users interacting via the network" |
| You ship an on-prem binary to a customer (they run it themselves) | ✅ None | AGPL doesn't trigger on distribution; the binary is offline once delivered |
| You build a SaaS that internally calls VoiceStudio via REST/MCP | ⚠️ **HIGH** | (a) open-source the integrating module, or (b) buy commercial license |
| You build a SaaS where VoiceStudio is the *user-facing* voice agent (users talk to it) | ⚠️ **HIGH** | Same — open-source or commercial license |
| You clone a voice and ship the audio file (e.g., personalized greetings) | ✅ None | License doesn't restrict generated audio. But check the model license (OmniVoice weights are CC-BY-NC). |
| You list VoiceStudio as a dependency in your docs | ✅ None | Attribution only |
| You fork VoiceStudio, add features, and run the fork as your service | ⚠️ **VERY HIGH** | Modified version definitely triggers — you must release source |
| You only use VoiceStudio's HTTP API (no code link) | ⚠️ Grey | Linking at the HTTP API level is debated. VoiceStudio's commercial license covers this case explicitly. Safer to obtain commercial license. |

## What's NOT AGPL-3.0

The AGPL applies to the **VoiceStudio application code** (the Tauri shell, FastAPI backend, engine registry). It does **not** extend to:

- **Generated audio output** — your users have rights to use the audio however they want (subject to the model license).
- **Models loaded into VoiceStudio** — each model has its own license (CosyVoice Apache-2.0, OmniVoice CC-BY-NC, PocketTTS CC-BY-4.0, etc.). VoiceStudio's AGPL doesn't relicense them.
- **Your original code that doesn't link VoiceStudio** — only the integrating module is in scope.

## Commercial licensing path

VoiceStudio offers a commercial license for the VoiceStudio-owned code. Contact: **VoiceStudio@palash.dev**

**What the commercial license covers (per VoiceStudio's README):**
- VoiceStudio-owned code only
- Does **not** relicense third-party models
- For proprietary embedding of VoiceStudio

**What it does NOT cover:**
- Models you load (CosyVoice, OmniVoice, etc. — check each)
- Engine weights (CC-BY-NC for OmniVoice default)

So even with a VoiceStudio commercial license, you may still need to:
- Use only commercially-licensed models (e.g., CosyVoice 3 Apache-2.0)
- Or get separate licenses for non-commercial models

## Concrete checklist for Product Forge projects

When a project includes a voice feature, the pre-production agent (stage 7 — Legal/Compliance) must check:

1. **Is VoiceStudio in the dependency graph?**
   - Yes → continue below
   - No → no action needed

2. **How is it used?**
   - Internal tool only → ✅ documented in `reports/license-compliance.md`, no further action
   - On-prem binary → ✅ documented, no further action
   - Customer-facing SaaS → continue below

3. **For customer-facing SaaS:**
   - Do you have a commercial license from VoiceStudio? (PDF in `reports/voicestudio-commercial-license.pdf`)
   - Which engine/model is in use? (must be commercially licensed)
   - Is the integrating module open-source under AGPL-3.0?
   - If none of the above: **BLOCKED** — go back to design and pick a different voice stack

## Alternative voice engines (no AGPL concern)

If AGPL is a blocker for your SaaS, consider these alternatives:

| Engine | License | Quality | Notes |
|---|---|---|---|
| **CosyVoice 3** | Apache 2.0 | High | Bundled in VoiceStudio but standalone-installable |
| **Piper** | MIT | Good | Local TTS, fast, lower fidelity |
| **Coqui TTS** | MPL-2.0 | Good | Local, multi-language |
| **Kokoro** | Apache 2.0 | Good | Newer, lightweight |
| **ElevenLabs API** | Proprietary | Excellent | Paid SaaS, no AGPL concern |
| **OpenAI TTS** | Proprietary | Excellent | Paid SaaS |
| **Azure Speech** | Proprietary | Excellent | Paid SaaS |

For STT (speech-to-text), Whisper (MIT) and Faster-Whisper (MIT) are safe.

## How to mitigate AGPL risk now

If you're planning a voice-enabled SaaS, here are the options ranked by effort:

### Option 1: Obtain commercial license from VoiceStudio
- Contact: `VoiceStudio@palash.dev`
- Cost: not published (negotiated)
- Time: depends on negotiation
- Result: clean ship path, no AGPL obligations

### Option 2: Open-source the integrating module under AGPL-3.0
- Cost: $0 but you publish your voice agent code
- Time: 1 day (add LICENSE file + header to source files)
- Result: AGPL compliance, but your code becomes AGPL
- ⚠️ Caveat: AGPL is viral — anything that links your module must also be AGPL or compatible. Be careful about what else is in the same code base.

### Option 3: Use a different voice stack (above alternatives)
- Cost: integration effort
- Time: 1-2 weeks to swap
- Result: no AGPL concern at all

### Option 4: Keep voice as on-prem / internal only
- Cost: $0
- Time: $0
- Result: AGPL doesn't trigger; document the boundary clearly

## Bottom line

**Use VoiceStudio freely if:**
- The voice feature is for your internal team
- The product is an on-prem binary customers run themselves
- You're experimenting / prototyping (irrespective of license, just don't ship yet)

**Get a commercial license or switch stacks if:**
- The product is a SaaS where end-users reach a voice agent over the network
- You're forking VoiceStudio and operating the fork as a service

**Document the scope** in `reports/license-compliance.md` for every release. The pre-production agent now does this check automatically.

## References

- VoiceStudio license: https://github.com/debpalash/VoiceStudio/blob/main/LICENSE
- VoiceStudio commercial contact: VoiceStudio@palash.dev
- AGPL v3 full text: https://www.gnu.org/licenses/agpl-3.0.html
- AGPL FAQ (key scenarios): https://www.gnu.org/licenses/agpl-3.0.html#section13
- VoiceStudio license notice: https://github.com/debpalash/VoiceStudio/blob/main/LICENSE-NOTICE.md

---

*Last updated: 2026-09-03*
*Maintainer: Product Forge pipeline team*