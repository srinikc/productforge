# Tools & Dependencies (Product Forge)

What tool/execution capabilities PF has today, what it needs but doesn't, how each is obtained (library /
download / cloud API / self-host), and the **licensing & redistribution** implications. **Not legal advice** —
verify each provider's ToS and the LICENSE before shipping.

> PF is **MIT** (`pyproject.toml` / `LICENSE`). Go deps are permissive (`jackc/pgx` MIT, `modernc.org/sqlite`
> BSD-3). Python deps are permissive (FastAPI/uvicorn/pydantic → MIT/BSD/PSF). The rule below keeps PF
> redistributable: **interfaces + adapters, never bundled SaaS clients/keys.**

---

## 1. The tool layer (framework-agnostic)

PF owns its own tools — **not** the agent framework's — and exposes them two ways so any runtime can use them.

| Component | File | Role |
|---|---|---|
| **ToolRegistry** | `core/tool_registry.py` | Neutral `ToolSpec` (JSON schema) + sandboxed execution. Doc: *"mapped to whatever runtime we use (our own loop, MCP, or OpenAI function calling)."* |
| **ToolPolicy** | `core/tool_policy.py` | Dynamic per-agent selection: card base + role/knowledge (research roles get `http_get`). `WEB_TOOLS=("http_get",)` |
| **ToolCache** | `core/tool_cache.py` | Caches tool results (avoids repeat read/list/http calls) |
| **Agent tool loop** | `core/agent_tool_loop.py` | LLM → parse tool calls → execute via registry (wired in `pipeline_executor.py:349`) |
| **MCP bridge** | `core/mcp.py` | Exposes PF tools over MCP (`tools/list`/`tools/call`) **and** consumes external MCP servers' tools |
| **BYOT** | `core/byot_integration.py` | Register a custom **tool** / **MCP server** / **model** |
| **Plugins** | `core/plugins.py` | Third-party plugins may `ToolRegistry.register(ToolSpec)` |

So: **files/commands/http come from PF**, not from opencode/claude-code; MCP lets those runtimes call PF's tools
(and lets PF call theirs).

---

## 2. Tools PF HAS today

### 2a. Registered agent tools (`ToolRegistry`)

| Tool | Purpose | Kind / source | Redistribution |
|---|---|---|---|
| `write_file` | Write a file **inside the workspace** (path-traversal rejected) | PF-owned | MIT (PF) |
| `read_file` | Read a workspace file | PF-owned | MIT (PF) |
| `list_dir` | List a workspace dir | PF-owned | MIT (PF) |
| `run_command` | Run an **allow-listed** executable in the workspace (300 s timeout) | PF-owned wrapper; runs **user-installed** CLIs | MIT (PF); the CLIs are the user's responsibility |
| `http_get` | HTTP **GET a URL** (read-only; returns text) | PF-owned; uses `requests` | PF MIT; `requests` **Apache-2.0** |

`run_command` allow-list (`DEFAULT_ALLOWED_COMMANDS`): `python, python3, pip, pytest, node, npm, npx, pnpm, yarn,
tsc, ruff, mypy, black, eslint, git, make`. PF **does not bundle** these — the user installs them; PF shells out.

### 2b. Adjacent runtime dependencies PF invokes (not agent tools; "if present → degraded without")

| Dependency | Where | Purpose | License / note |
|---|---|---|---|
| **git** | `core/vcs.py` | branching/worktrees/merge/push | GPL-2.0 (**invoked**, not linked/bundled) |
| **Go toolchain** | `workergrid/` build | build the coordinator/agent binaries | BSD-3 (build-time) |
| **ffmpeg** | `core/asset_store.py` (optional) | video frame sampling / media transcode | **LGPL/GPL** (build-dependent) — invoke, don't bundle |
| **Playwright + browsers** | `core/pdf_generator.py`, e2e tests | HTML→PDF, browser tests | Playwright **Apache-2.0**; browsers (Chromium/FF/WebKit) separate licenses |
| **docker** | `core/artifact_registry.py`, `core/build_utility.py` | image build/push (optional) | Apache-2.0 (invoked) |
| **Pillow / numpy / scipy** | `core/asset_store.py`, media (optional) | image/array ops | Pillow (HPND), numpy/scipy (BSD) |
| **requests/httpx/urllib** | net access in several modules | outbound HTTP | Apache-2.0 / BSD / PSF |

PF runs **offline-safe**: absent optional tools degrade, they don't break the pipeline.

---

## 3. Tools PF NEEDS but doesn't have (gaps)

| Need | What it is | Why needed in PF | How to get it | Key? | License / redistribution |
|---|---|---|---|---|---|
| **`web_search`** | General web **search** (query → ranked results) | agents are told to "get latest" on skills/domain/**tech-stack**/market; today only `http_get` (a known URL) exists | pluggable **backend** (see below) | backend-dependent | backend-dependent (below) |
| `web_fetch` + extraction | fetch URL → **clean text** (readability) | `http_get` returns raw HTML; agents need readable content | `trafilatura` (Apache-2.0), `readability-lxml`, `beautifulsoup4` (MIT) | no | **redistributable** (permissive) |
| document extraction | PDF/DOCX/PPTX → text | ingest specs/docs | `pypdf` (BSD), `pdfplumber` (MIT), `python-docx` (MIT) | no | **redistributable** |
| local code/doc search | fast repo search | code agents find usages | `ripgrep` (MIT, invoke) | no | redistributable |
| embeddings / vector | semantic dedup/similarity | better dedup than lexical Jaccard; retrieval | provider embeddings (cloud) **or** local `sentence-transformers`+`sqlite-vec` | cloud: yes | cloud = key/ToS; local = **Apache-2.0/MIT** |
| browser automation | JS-heavy pages / interaction | dynamic sites | Playwright (already present for PDF/e2e) | no | Apache-2.0 (+browser licenses) |
| vision / ASR / media-gen | image/audio/video understanding + generation | media pipeline (optional packs) | provider APIs (cloud) **or** local models (heavy) | cloud: yes | cloud = key/ToS; local = model licenses |

### `web_search` backends (pick per deployment)

| Backend | Key? | Cost | License / redistribution | Note |
|---|---|---|---|---|
| **SearXNG** (self-host) | no | free (your infra) | **AGPL-3.0** (copyleft; network clause) | **Best for self-contained / zero-cost**; ship as an adapter to the user's instance |
| **DuckDuckGo HTML** (scrape) | no | free | **no API; ToS restricts automated scraping** — legally risky | today's `business_models_kb._research_web`; keep as opt-in, not a product feature |
| **Brave Search API** | **yes** | free tier + paid | commercial ToS; **no redistribution/resale**; attribution | bring-your-own-key adapter |
| **Tavily** | **yes** | paid tiers | commercial ToS | BYO-key (LLM-oriented search) |
| **SerpAPI** | **yes** | paid | ToS prohibit redistribution | BYO-key |
| **Bing (Azure) / Google CSE** | **yes** | paid/limited | ToS-restricted | BYO-key |
| **Open scholarly/content**: Wikipedia/Wikidata (CC-BY-SA content), arXiv, OpenAlex, Crossref | mostly no (some polite-pool) | free | open APIs (respect ToS/UA/attribution) | good zero-key options for research |

---

## 4. Redistribution & licensing — the principle

1. **PF ships neutral interfaces + adapters, never bundled SaaS clients or keys.** A vendor API (Brave/Tavily/
   SerpAPI/Bing/Google, cloud embeddings/vision) requires the **user's own key** and its ToS forbids handing the
   bundled feature to third parties. So PF: no keys in the repo; adapters read the key from env/config.
2. **Prefer self-host / local for a zero-key, redistributable default:** SearXNG (web search), `trafilatura`
   (extract), `pypdf` (docs), `ripgrep` (search), `sentence-transformers`+`sqlite-vec` (embeddings). These can
   ship/redistribute with PF (respect **AGPL** for SearXNG if you distribute *it*, and **ffmpeg** LGPL/GPL nuance).
3. **Don't bundle binaries you invoke:** `git`, `ffmpeg`, `docker`, the Go toolchain, Playwright browsers —
   PF **invokes** them (user-installed). This avoids bundling GPL/LGPL components into a MIT product.
4. **Cloud = bring-your-own-key; self-host = bring-your-own-instance.** Either way PF's own code stays MIT and
   stays redistributable.
5. **Model-native search** (if a provider's model searches itself) is the provider's capability/ToS/pricing — PF
   uses it via its provider-agnostic LLM client, adding no bundled dependency.

## 5. Recommended next step
Implement **`web_search`** as one neutral `ToolSpec` with a **pluggable backend registry**
(`searxng` self-host default → `none`/disabled offline-safe; `brave`/`tavily`/`serpapi` as BYO-key), add it to
`tool_policy.WEB_TOOLS` for research roles, cache via `tool_cache` — it is then exposed through **both** PF's loop
and **MCP** automatically. (Track as a backlog item; design + approval first.)
