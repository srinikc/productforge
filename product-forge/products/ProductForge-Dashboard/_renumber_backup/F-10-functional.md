## F-10: Voice Companion

**Feature ID:** F-10
**Summary:** F-10 defines the hands-free, spoken-modality companion for Product Forge: a voice layer that lets an operator talk to the product-wide AI companion (F-9) and hear its grounded answers, without touching the keyboard. It owns the *voice I/O contract* — activation and microphone lifecycle, streaming speech-to-text, spoken synthesis of grounded answers, spoken citations, barge-in, hands-free human-in-the-loop (HIL) gate announcements, voice-driven navigation, voice *drafting* of commands, multilingual speech, transcript/audio privacy controls, and graceful degradation to text. F-10 owns no domain state: it reads the authoritative surfaces already published by F-1 (projects/runs), F-2 (model tiers), F-3 (runs, stages, HIL gates, telemetry), F-4 (portfolios), F-5 (multi-project run groups), F-6 (manual command surface), and F-7 (auto-mode policy/ledger), and it reuses the context binding, grounding and refusal rules of F-9 rather than redefining them.

**Boundary note:** F-10 does not own conversational reasoning, grounding, or refusal policy (F-9), the command preview/confirmation/execution surface (F-6), run/stage execution or gate definitions (F-3), auto-mode policy or ledger (F-7), or presentation components and design tokens (F-8). F-10 converts speech to text, text to speech, and speech to *drafts*; it never mutates pipeline state on its own authority. Where F-10 produces a command draft, the draft is previewed, confirmed and executed under the rules of F-6; where F-10 answers a question, the answer text and its citations come from F-9.

### Requirements

#### Functional Requirements

| ID | Requirement | Description |
|---|---|---|
| FR-226 | Voice companion activation | Provide multiple activation affordances — press-and-hold push-to-talk, tap-to-toggle listening, configurable wake phrase, and a keyboard shortcut — available from every dashboard surface. Activation requires an explicit operator gesture before microphone capture begins (browser/OS permission rules), and the companion always shows an unmistakable audio-state indicator (idle / listening / transcribing / thinking / speaking / muted). |
| FR-227 | Voice session lifecycle and audio device management | Create, resume, and end voice sessions. Enumerate available input and output devices, let the operator select them, and react to device change, unplug, or hot-plug mid-session by pausing capture and prompting for a new device. Device and voice preferences persist per operator. |
| FR-228 | Streaming speech recognition | Transcribe operator speech as a stream: emit interim partial transcripts while the operator is still speaking and a finalized transcript at utterance end, each with a confidence value and language tag. Support spelling out identifiers used across the product (project names, run ids, stage numbers, gate names, requirement ids such as “FR two two six”, “F dash ten”) through spoken-form normalization. |
| FR-229 | Utterance intent routing | Classify every finalized utterance into exactly one intent — state query, explanation/diagnosis request, navigation command, command dictation, voice-session control (mute, stop, repeat, slower, faster, cancel), or unrecognized. Query, explanation and navigation intents are handed to the F-9 companion; dictation enters the drafting flow (FR-234); unrecognized or low-confidence utterances trigger a single clarifying question instead of a guess. |
| FR-230 | Spoken answer synthesis | Speak the F-9 companion's grounded answer: lead with a concise summary, then offer depth on request (“say *more*”, “*why*”, “*read the detail*”). Long answers are chunked into speakable segments, verbosity and speech rate are operator-configurable, and everything spoken is simultaneously rendered as on-screen captions (never audio-only). |
| FR-231 | Spoken citations | Attribute every factual statement about pipeline state aloud to the authoritative object it came from (for example “per run 4f2a, stage 12, gate *Architecture Review*”). When the companion cannot cite a source, F-10 speaks the refusal — it never speaks invented state, invented ids, or invented commands. |
| FR-232 | Barge-in and interruption | Operator speech, activation, or an explicit “stop” while synthesis is playing halts playback within a short bound. The interrupted answer is truncated at a sentence boundary, never mid-word, and “repeat” / “continue” resumes from the interruption point. |
| FR-233 | Hands-free HIL gate announcements | When a run reaches a human-in-the-loop gate defined by F-3, the voice companion may announce it if the operator has opted in, naming the project, run, stage and gate, and stating the allowed decisions. Announcements respect per-project subscription, quiet hours, and rate limits. F-10 reads the gate's content aloud and answers grounded questions about it, but never selects a decision on the operator's behalf. |
| FR-234 | Voice command drafting with mandatory non-voice confirmation | Dictated commands are parsed into a structured command draft and handed to the manual command surface (F-6) as a preview. Voice alone can never execute a mutating command: final confirmation is always an explicit non-voice confirm action on the F-6 preview surface. Voice may read the preview back, may correct it by re-dictating, and may cancel it. Destructive and emergency actions (cancel run, skip stage, emergency halt) are excluded from voice execution entirely and require typed confirmation. |
| FR-235 | Voice-driven navigation and focus | Support non-mutating navigation by voice — open a project, run, stage, gate, portfolio or run group; show gate backlog, failure list, or run telemetry. Navigation obeys the operator's authorization scope: the companion never reveals, names, or counts objects the operator is not permitted to see, and does not leak existence through error wording. |
| FR-236 | Multilingual and locale-aware speech | Recognize and synthesize speech in the operator's configured language(s), switchable by setting or by voice within a session. Spoken numbers, dates, durations, currency and percentages use the operator's locale conventions, and transcript rendering supports right-to-left languages. |
| FR-237 | Transcript, audio and privacy controls | Retain transcripts according to an operator-configurable policy (default: session-scoped and deletable). Raw audio is not persisted unless the operator explicitly opts in for a session, and is never persisted for sessions that touch classified or credential-bearing content. Provide a persistent visible capture indicator, one-action mute, first-use consent, transcript history review, and transcript deletion. |
| FR-238 | Degraded and fallback modes | Degrade explicitly rather than silently: if speech recognition is unavailable, disable voice input with an actionable message and keep typed text to the F-9 companion available; if synthesis is unavailable, switch to captions-only with screen-reader-friendly output; if the assistant backend is unavailable, serve deterministic help/search answers (mirroring F-9's degradation) and say so aloud. Never fabricate state to fill a gap. |
| FR-239 | Accessibility of the voice experience | Voice is always an optional modality — no task in the product requires it. Every spoken answer is captioned; synthesized output is exposed to assistive technology exactly once (no double-speaking); all voice controls are keyboard- and screen-reader-operable with visible focus; captions are configurable in size, contrast, and persistence so they work for deaf and hard-of-hearing operators. |
| FR-240 | Voice safety guardrails | Apply shared redaction rules so secrets, tokens, credentials, provider keys and personal data are neither spoken nor written into transcripts. A kill phrase (“stop listening”) and a visible mute end capture immediately. Voice sessions inherit and never exceed the operator's authorization scope from F-9, and are rate-limited to prevent runaway recognition, synthesis or dictation loops. |

#### Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-136 | Recognition latency | First interim transcript ≤ 300 ms (p50) / ≤ 700 ms (p95) after utterance onset; final transcript ≤ 1.0 s (p95) for utterances up to 30 s. |
| NFR-137 | Synthesis latency | First audible output ≤ 500 ms (p95) after the first sentence of an answer is finalized. |
| NFR-138 | End-to-end voice turn latency | ≤ 2.5 s (p95) from end-of-utterance to start of spoken answer for registry-read queries; ≤ 6 s (p95) for diagnostic/explanation answers. |
| NFR-139 | Availability and scalability | Voice session service ≥ 99.5% monthly availability; ≥ 200 concurrent voice sessions per deployment; speech providers accessed through an abstraction so no single provider is a hard dependency. |
| NFR-140 | Security | Voice sessions authenticated by the same session/identity as the dashboard; no voice-only or biometric authentication; speech-provider calls authenticated, scoped and minimized; audio and transcripts excluded from logs by default; all audio transport over TLS. |
| NFR-141 | Data residency and retention | Audio and transcripts stored only in the operator's configured region; default transcript retention session-scoped, hard maximum 30 days; deletions propagate to derived caches within 24 h. |
| NFR-142 | Privacy and compliance | Explicit, revocable microphone consent captured before first capture; per-operator opt-out of all audio persistence honored platform-wide; data-classification rules block transcription of classified fields. |
| NFR-143 | Accessibility standard | WCAG 2.1 AA for captions and voice controls (≥ 4.5:1 text contrast, ≥ 44×44 px touch targets, visible focus, no audio-only information path). |
| NFR-144 | Internationalization | Speech support for every language the F-9 companion supports; locale-correct spoken numbers, dates and durations; RTL transcript rendering; no hard-coded English strings in voice prompts. |
| NFR-145 | Deployment and environment | Runs in current and previous major versions of Chromium, Firefox and Safari over HTTPS with no native install; microphone permission is requested with clear explanation; the entire feature is flaggable off per deployment. |
| NFR-146 | Observability | Per-session metrics (activation source, recognition error rate, synthesis failure rate, barge-in success, fallback rate, draft creation rate) with a correlation id linking any voice session to the audit trail of commands it drafted. |
| NFR-147 | Cost and quota guardrails | Configurable per-operator/per-tenant speech-minute quotas; exceeding quota degrades to text with a clear notice rather than failing opaquely. |
| NFR-148 | Fail-closed safety | Any failure in the redaction, authorization or confirmation path disables voice command drafting immediately; the voice path never fails open. |
| NFR-149 | Client resource limits | Bounded client memory and CPU; audio buffers and media streams released on session end or mute; no background capture while the indicator shows idle. |
| NFR-150 | Protocol versioning | The voice session protocol and intent annotation layer are explicitly versioned; changes remain backward compatible for at least one release, and pinned pipeline versions never change their voice behavior retroactively. |

#### User Stories

| ID | Story |
|---|---|
| US-136 | As an operator away from my desk, I want to ask aloud what my runs are doing, so that I can stay informed without returning to the keyboard. |
| US-137 | As an operator with a visual impairment, I want spoken, cited answers and fully captioned controls, so that I can operate Product Forge entirely by voice and keyboard. |
| US-138 | As an operator running a long pipeline, I want to be told aloud when a run reaches a human-in-the-loop gate, so that I can decide promptly without watching the dashboard. |
| US-139 | As a cautious operator, I want to dictate a command and have it drafted for my review, so that a misheard word can never change pipeline state. |
| US-140 | As an operator in a shared or noisy space, I want to mute instantly and use captions instead, so that no audio is captured or broadcast that I did not intend. |
| US-141 | As a multilingual operator, I want to speak and listen in my own language with locally formatted numbers and dates, so that I don't have to translate pipeline state in my head. |
| US-142 | As a privacy-conscious operator, I want transcripts to be session-scoped by default and audio never stored unless I opt in, so that confidential project discussions are not retained. |
| US-143 | As an operator on an unreliable connection, I want a clear fallback to text and a plain statement of what is unavailable, so that I always know whether the companion actually heard me. |
| US-144 | As an operator mid-answer, I want to interrupt and redirect the companion, so that I don't have to wait through an answer I no longer need. |
| US-145 | As an operator who prefers keyboard, I want voice to remain optional everywhere, so that nothing in the product requires me to speak. |
| US-146 | As an operator, I want every spoken fact to name its source object, so that I can trust the answer and go look at the underlying record. |
| US-147 | As an operator tracking many projects, I want to navigate by voice to a specific run, stage or gate, so that I can move quickly without hunting through lists. |

### Behaviour

1. **Activation.** The companion exposes an always-visible microphone affordance on every dashboard surface. Press-and-hold, tap-to-toggle, keyboard shortcut or the operator's configured wake phrase starts a *capture attempt*; no audio leaves the client until the gesture completes and the audio-state indicator reflects *listening*.
2. **Turn lifecycle.** A turn is: capture → streaming recognition (interim transcripts shown live as captions) → utterance finalization → intent routing → either a grounded answer from F-9 (spoken via FR-230 plus on-screen captions) or a command draft handed to F-6 (FR-234). Every turn carries the session's context binding.
3. **Context binding.** By default the voice session is bound to the operator's current dashboard context using the same binding rules as F-9 (project, run, stage, gate, portfolio, run group, auto-mode session). The operator can rebind by voice (“switch to project Atlas”) or by navigating in the UI, and can ask the companion to state its current context.
4. **Grounded answering.** Voice answers are the F-9 answer text, not a re-summarization. Spoken output is truncated only at sentence boundaries, and the full text with citations is always available as captions and as transcript entries.
5. **Hands-free gate flow.** When an opted-in subscription and the F-3 gate event both fire, F-10 announces the gate, states the permitted decisions, and answers follow-up questions grounded in the gate payload. Deciding the gate is a command: it follows FR-234 and lands on the F-6 preview surface with a non-voice confirmation.
6. **Command drafting.** Dictation produces a structured draft (target object, action, parameters, operator, session correlation id, source = voice, transcript span used). The draft is a proposal only. F-10 displays and may speak the preview, and the operator confirms or cancels it in F-6. Nothing is dispatched by F-10.
7. **Navigation and query.** Non-mutating actions (navigate, read, explain, list) may be satisfied by voice alone within the operator's authorization scope. Mutating actions may not.
8. **Session end.** Ending a session, muting, or losing the device stops capture, releases audio resources, and applies the transcript retention policy in force. Ending a session never affects a pending F-6 draft beyond marking it stale.
9. **Degradation.** Unavailable recognition disables input; unavailable synthesis switches to captions-only; unavailable assistant serves deterministic help/search only. Each degradation is announced in the same modality that still works, and the state is visible in the UI.

### Business rules

| ID | Rule |
|---|---|
| BR-1 | Voice is a modality, not an authority: it inherits exactly the F-9 companion's authorization scope and never elevates it. |
| BR-2 | No mutating pipeline action may be executed by voice alone; FR-234's non-voice confirmation is mandatory for every mutating command. |
| BR-3 | Destructive and emergency actions (cancel run, skip stage, emergency halt) are never voice-executable, at any autonomy level, including full-auto (F-7). |
| BR-4 | Every factual statement spoken about pipeline state must carry a spoken citation to the authoritative object; uncitable statements are refused aloud. |
| BR-5 | Raw audio is not persisted by default; opt-in is per session, explicit, revocable, and never available for classified content. |
| BR-6 | Transcript retention defaults to session-scoped; the configured maximum is 30 days; deletion is honored within 24 hours including derived caches. |
| BR-7 | Voice sessions bind to the operator identity, never to a shared device identity; a device change does not change the operator. |
| BR-8 | Redaction rules are shared with the text companion: secrets, tokens, credentials and personal data are masked in both transcripts and synthesis. |
| BR-9 | HIL announcements require explicit opt-in, honor quiet hours, and are rate-limited; an announcement is informational and never counts as a decision. |
| BR-10 | Voice navigation must not leak the existence of unauthorized objects through names, counts, or error wording. |
| BR-11 | Each command draft records the transcript span it was derived from, so the operator can audit why the draft says what it says; drafts are never silently rewritten after confirmation is requested. |
| BR-12 | Low-confidence or ambiguous utterances resolve to a clarifying question, never to a best-guess query or draft. |
| BR-13 | Feature flags may disable voice per deployment or per tenant; when disabled, no microphone permission is ever requested. |
| BR-14 | Speech providers are interchangeable behind an abstraction; provider change must not alter grounding, refusal, or confirmation behavior. |

### Validation

| ID | Validation |
|---|---|
| V-1 | Activation gesture is present and completed before any capture begins; the audio-state indicator transitions to *listening* only then. |
| V-2 | Microphone consent recorded for the operator before first capture; absence of consent blocks start with an explanatory message. |
| V-3 | Selected input device is available and returns non-silent frames; silent/absent device yields a device error, not an empty transcript. |
| V-4 | Session context binding resolves to an object the operator is authorized to read; unresolvable or unauthorized context degrades to “no context” rather than an implicit guess. |
| V-5 | Finalized transcript is non-empty, above the confidence floor, and within the maximum utterance duration (§ NFR-136); below floor → clarification, above duration → truncation notice. |
| V-6 | Intent classification returns exactly one intent with a confidence value; multi-intent utterances are split at sentence boundaries or clarified. |
| V-7 | Command drafts validate against the F-6 command schema (target object exists and is visible to the operator, action is permitted for that object type, required parameters present, values within allowed ranges). |
| V-8 | Draft target is re-checked for authorization and existence at preview time, not only at dictation time. |
| V-9 | Spoken answer text is byte-identical to the F-9 answer text it synthesizes (modulo chunk boundaries); captions and audio are generated from one source. |
| V-10 | Every citation spoken resolves to a real, currently-readable object; unresolvable citations abort the spoken claim. |
| V-11 | Redaction pass runs before synthesis and before transcript persistence for every utterance and answer. |
| V-12 | Retention policy in force is applied at session end, and the applied policy is recorded with the session. |

### Edge cases

| ID | Case | Expected behaviour |
|---|---|---|
| EC-1 | Operator speaks while the assistant is speaking (barge-in). | Synthesis stops at the last sentence boundary; the new utterance becomes the next turn; “continue” resumes the truncated answer. |
| EC-2 | Wake phrase appears inside a normal sentence, or a similar-sounding phrase is spoken. | False triggers are suppressed by requiring the configured phrase plus a confidence threshold; the companion never starts a mutating flow from a suspected false trigger. |
| EC-3 | Two operators share a physical space and both speak. | The session accepts only the bound operator's chosen device and voice profile; ambiguous overlapping speech yields a clarification or an ignored-turn, never a draft. |
| EC-4 | Identifier dictation ambiguity (“FR two two six” vs “FR 226” vs “F-10”). | Spoken-form normalization maps all variants to the same canonical identifier and the companion reads the resolved identifier back in the preview. |
| EC-5 | Operator dictates a command referring to an object they cannot see. | The draft is rejected with a neutral message that does not confirm the object's existence. |
| EC-6 | Gates fire while the operator is mid-dictation. | The announcement is queued until the current turn completes, or delivered as a caption if quiet mode is on; it never interrupts a confirmation in progress. |
| EC-7 | Microphone permission revoked or device unplugged mid-session. | Capture stops immediately, indicator shows muted/error, in-flight transcript is finalized or discarded per policy, and an actionable prompt offers device re-selection. |
| EC-8 | Network drops between recognition and answer. | The turn fails with an explicit “I didn't get an answer” message; no partial answer is spoken as if complete; the transcript entry is marked incomplete. |
| EC-9 | Assistant backend unavailable. | Deterministic help/search answers are served and identified as such aloud (mirrors F-9 degradation). |
| EC-10 | Very long answer (for example, a full gate backlog). | The companion speaks a bounded summary and offers “more”, “next”, or “read the list on screen”, never an unbounded monologue. |
| EC-11 | Operator switches language mid-session. | Subsequent recognition and synthesis use the new language; the switch is confirmed aloud and recorded on the session. |
| EC-12 | Session touches classified or credential-bearing content. | Audio persistence option is unavailable for that session, redaction is enforced on transcript and synthesis, and the restriction is stated to the operator. |
| EC-13 | Operator loses authorization scope mid-session (role change). | Subsequent queries, navigation and drafts re-evaluate scope on each turn; already-displayed content is not retroactively spoken again. |
| EC-14 | Quota exhausted mid-session. | Companion announces the quota state and degrades to text; no silent failure. |
| EC-15 | Repeated identical dictation due to a recognition loop. | Rate limiting and deduplication collapse repeats into one draft; the operator is told the turn was deduplicated. |

### Error handling

| ID | Code | Condition | Handling |
|---|---|---|---|
| EH-1 | VOICE-0001 | Microphone permission denied or blocked by policy. | Do not capture; show an inline explanation with a link to browser/OS permission steps; keep text companion fully usable. |
| EH-2 | VOICE-0002 | No usable input device. | Pause session, list detected devices, offer a retry; no empty transcripts are recorded. |
| EH-3 | VOICE-0003 | Recognition service unavailable or timed out. | Disable voice input for the session with a visible notice and auto-retry with backoff; keep captions and typed input working. |
| EH-4 | VOICE-0004 | Recognition confidence below floor. | Ask one clarifying question; after two failed attempts, offer typed input. |
| EH-5 | VOICE-0005 | Utterance exceeds maximum duration. | Finalize the partial transcript, notify the operator of truncation, and continue as a new turn. |
| EH-6 | VOICE-0006 | Synthesis service unavailable. | Switch to captions-only mode, announce the mode change in text, expose the answer to assistive tech. |
| EH-7 | VOICE-0007 | Spoken citation cannot be resolved. | Suppress the spoken claim, state that the source could not be verified, and point to the on-screen record. |
| EH-8 | VOICE-0008 | Command draft fails F-6 schema or authorization validation. | Do not create a draft; explain the failing field(s) neutrally without leaking object existence; allow re-dictation. |
| EH-9 | VOICE-0009 | Attempt to voice-execute a destructive or emergency action. | Refuse, explain that typed confirmation is required, and (if the operator insists) surface the normal non-voice flow. |
| EH-10 | VOICE-0010 | Redaction service failure. | Fail closed: suspend synthesis and transcript persistence for that turn, notify the operator, and log the suspension without content. |
| EH-11 | VOICE-0011 | Session or authentication expired. | Stop capture, discard unsent audio, prompt re-authentication, and re-bind context after re-auth. |
| EH-12 | VOICE-0012 | Client-side audio failure (media stream, buffer, or codec error). | Tear down the media pipeline, release resources, restart the session cleanly, and report a bounded number of automatic retries before requiring operator action. |

### Acceptance criteria

| ID | Criterion |
|---|---|
| AC-1 | From any dashboard surface, push-and-hold activation begins capture and the indicator reflects *listening*; releasing ends capture. (FR-226) |
| AC-2 | Interim partial transcripts appear while the operator is still speaking; a final transcript with confidence appears at utterance end. (FR-228) |
| AC-3 | A spoken question about a run's current stage yields a spoken answer that names the run and stage and cites the underlying record. (FR-229, FR-230, FR-231) |
| AC-4 | A spoken question whose answer cannot be grounded produces an explicit refusal, not a fabricated statement. (FR-231) |
| AC-5 | Speaking over a playing answer stops playback at the last sentence boundary within the barge-in bound. (FR-232) |
| AC-6 | With gate announcements enabled, reaching an F-3 HIL gate produces a spoken announcement naming project, run, stage, gate and allowed decisions — and no decision is applied. (FR-233) |
| AC-7 | A dictated mutating command creates a draft visible on the F-6 preview surface and executes nothing until a non-voice confirmation is given. (FR-234) |
| AC-8 | A dictated destructive command (cancel run, emergency halt) is refused and routed to typed confirmation. (FR-234, BR-3) |
| AC-9 | A voice navigation request opens the named object; a request for an unauthorized object produces a neutral failure with no existence leak. (FR-235) |
| AC-10 | Switching language mid-session changes both recognition and synthesis for subsequent turns, with locale-correct numbers and dates. (FR-236) |
| AC-11 | Transcripts are session-scoped by default; no raw audio is stored unless the operator opted in for that session. (FR-237) |
| AC-12 | Secret-like content dictated into the companion is masked in both the transcript and the spoken output. (FR-240) |
| AC-13 | With recognition disabled, a clear message appears and typed input to the F-9 companion still works end to end. (FR-238) |
| AC-14 | With synthesis disabled, answers appear as captions and are exposed to assistive technology exactly once. (FR-238, FR-239) |
| AC-15 | Every voice control is reachable and operable by keyboard and screen reader, with visible focus. (FR-239) |
| AC-16 | Every task reachable by voice is also completable without voice. (FR-239, BR-1) |
| AC-17 | The kill phrase and the visible mute both stop capture immediately and the indicator reflects *muted*. (FR-240) |
| AC-18 | Device unplug mid-session pauses the session and offers re-selection without losing session context. (FR-227) |
| AC-19 | A session that touched classified content offers no audio-persistence option and states the restriction. (FR-237, BR-6) |
| AC-20 | Every command draft is traceable to the transcript span it came from, and the voice session id appears in the F-6 audit trail of that command. (FR-234, NFR-146) |
| AC-21 | Exceeding the speech-minute quota degrades to text with an explicit notice rather than failing opaquely. (NFR-147) |

### API behaviour

| ID | Operation | Contract |
|---|---|---|
| API-1 | `POST /voice/sessions` | Starts a voice session. Body: operator id (from auth), requested language(s), optional context binding (object type + id), retention policy. Returns session id, resolved context, applied retention policy, protocol version, and capability flags (recognition available, synthesis available, audio persistence permitted). |
| API-2 | `GET /voice/sessions/{sessionId}` | Returns session state (idle / listening / transcribing / thinking / speaking / muted / degraded / ended), resolved context, active language, device selections, quota remaining, and applied retention policy. |
| API-3 | `DELETE /voice/sessions/{sessionId}` | Ends the session: stops capture, finalizes or discards the in-flight transcript per policy, releases resources, marks any pending command draft stale, and returns the retention outcome. |
| API-4 | `POST /voice/sessions/{sessionId}/audio` (chunked/bidirectional stream) | Streams captured audio for the current turn. Accepts audio frames plus turn metadata; rejects frames when the session is muted, ended, or the operator lacks capture consent. Never persists raw audio when persistence is not permitted. |
| API-5 | `POST /voice/sessions/{sessionId}/utterances/{utteranceId}` | Finalizes an utterance: body carries the final transcript, confidence, language, capture start/end, and audio-persistence flag. Returns the classified intent, the routed outcome (answer reference, navigation result, or draft id), and a clarification request when confidence or schema resolution is insufficient. |
| API-6 | `POST /voice/sessions/{sessionId}/synthesize` | Requests synthesis of a text span (the F-9 answer text plus citation spans). Returns an audio stream plus a caption stream generated from the identical text, with the redaction pass applied. Returns a degraded response when synthesis is unavailable. |
| API-7 | `POST /voice/sessions/{sessionId}/drafts` | Creates a command draft from a transcript span. Body: transcript span reference, target object reference, action, parameters, confidence. Returns draft id, the F-6 preview payload, and validation results (V-7/V-8). Rejects with neutral errors when the target is unauthorized, invisible, or the action is voice-excluded. |
| API-8 | `GET /voice/sessions/{sessionId}/drafts/{draftId}` | Returns the draft's current state (proposed / confirmed / cancelled / stale / rejected) as decided on the F-6 surface, plus the transcript span that produced it. Read-only: F-10 never mutates draft state. |
| API-9 | `GET /voice/devices` · `GET /voice/preferences` · `PUT /voice/preferences` | Enumerates selectable audio devices and reads/writes per-operator preferences (devices, language, voice, speech rate, verbosity, captions, activation mode, wake phrase, gate-announcement subscription, quiet hours, retention policy, capture consent). |
| API-10 | `GET /voice/transcripts` · `DELETE /voice/transcripts/{transcriptId}` | Lists retained transcripts (never raw audio unless explicitly opted in) and deletes a transcript or the operator's whole history, with deletion propagating to derived caches. |

Emitted events: E-1 `voice.session.started`, E-2 `voice.transcript.partial`, E-3 `voice.transcript.final`, E-4 `voice.answer.speaking.started`, E-5 `voice.answer.speaking.completed` (with interruption reason), E-6 `voice.draft.created`, E-7 `voice.gate.announced`, E-8 `voice.session.ended` (with applied retention outcome). Every event carries the session id and, where a draft is involved, the draft id and its correlation id for the F-6 audit trail.

### Priority

| ID | Priority |
|---|---|
| FR-226 Activation | must-have |
| FR-227 Session lifecycle and devices | must-have |
| FR-228 Streaming recognition | must-have |
| FR-229 Intent routing | must-have |
| FR-230 Spoken answer synthesis | must-have |
| FR-231 Spoken citations | must-have |
| FR-232 Barge-in and interruption | should-have |
| FR-233 Hands-free HIL gate announcements | should-have |
| FR-234 Voice command drafting with non-voice confirmation | must-have |
| FR-235 Voice-driven navigation | should-have |
| FR-236 Multilingual and locale-aware speech | should-have |
| FR-237 Transcript, audio and privacy controls | must-have |
| FR-238 Degraded and fallback modes | must-have |
| FR-239 Accessibility of the voice experience | must-have |
| FR-240 Voice safety guardrails | must-have |
| NFR-136 to NFR-138 Latency budgets | must-have |
| NFR-139 Availability and scalability | should-have |
| NFR-140 to NFR-142 Security, residency, privacy | must-have |
| NFR-143 Accessibility standard | must-have |
| NFR-144 Internationalization | should-have |
| NFR-145 Deployment and environment | must-have |
| NFR-146 Observability | should-have |
| NFR-147 Cost and quota guardrails | nice-to-have |
| NFR-148 Fail-closed safety | must-have |
| NFR-149 Client resource limits | nice-to-have |
| NFR-150 Protocol versioning | should-have |

### Open Questions

| ID | Question | Owner |
|---|---|---|
| OQ-1 | Which speech recognition and synthesis providers must be supported at first release, and does any deployment require an entirely on-premises/self-hosted speech path (no outbound audio)? | USER |
| OQ-2 | Is a wake-phrase activation mode desired at all, or should activation be restricted to explicit push-to-talk / toggle to avoid accidental capture? | USER |
| OQ-3 | Should transcripts be visible to tenant administrators, or strictly private to the operator who spoke them? | USER |
| OQ-4 | May voice confirmation ever substitute for typed confirmation on any non-destructive command, or is a non-voice confirm always mandatory (as specified in FR-234)? | USER |
| OQ-5 | What is the maximum permitted transcript retention for regulated deployments — is 30 days acceptable, or must retention be session-only with no opt-in? | USER |
| OQ-6 | Are hands-free HIL gate announcements in scope for mobile/browser background operation (for example a notification while the tab is closed), or only while the dashboard is open? | USER |
