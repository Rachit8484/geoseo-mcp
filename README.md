# geoseo-mcp

<!-- mcp-name: io.github.Rachit8484/geoseo-mcp -->

> An open-source MCP server for traditional SEO **and** Generative Engine Optimization (GEO): Google Search Console, Bing, IndexNow, Google AI Overviews, and citation tracking across ChatGPT, Claude, Gemini, Perplexity, Grok and Brave, all in one server.

[![PyPI](https://img.shields.io/pypi/v/geoseo-mcp.svg)](https://pypi.org/project/geoseo-mcp/)
[![CI](https://github.com/Rachit8484/geoseo-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Rachit8484/geoseo-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)

<!-- TODO: demo GIF (multi_llm_citation_check in Cursor), e.g. docs/demo.gif -->

## Try it in 30 seconds (no API keys)

```bash
# Audit any page: title, meta, headings, schema, freshness, GEO quotability, 0-100 score
uvx geoseo-mcp audit https://example.com

# Check a site's llms.txt against the spec
uvx geoseo-mcp llms-txt https://llmstxt.org

# Same audit after running JavaScript (for SPAs); needs the [render] extra
uvx --from 'geoseo-mcp[render]' geoseo-mcp audit https://your-spa.com --render
```

Sample output:

```text
$ uvx geoseo-mcp audit https://example.com
https://example.com
  score: 15/100
  title: 'Example Domain'
  words: 27

  8 issue(s):
   ✗ meta_description: Meta description should be 70-160 chars  [length=0]
   ✗ h1: Exactly one H1 expected  [found=0]
   ✗ word_count: Pages under 300 words rarely rank or get cited  [words=27]
   ✗ schema: No JSON-LD schema found; LLMs and Google use this heavily
   ✗ canonical: Missing canonical URL
   ✗ open_graph: Missing core Open Graph tags (og:title, og:description)
   ✗ freshness: No published-date signal found; LLMs deprioritize stale content
   ✗ quotability: Few short, fact-dense sentences; LLMs prefer quotable lines  [quotable_sentences=0]

  3 check(s) passed. Use --json for the full report.
```

Other keyless commands: `audit-site ./content`, `generate-llms-txt ./content https://yourdomain.com`, `status`. Run `uvx geoseo-mcp --help` for everything.

Poke at all 47 tools in the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uvx geoseo-mcp
```

Running `geoseo-mcp` with no arguments starts the MCP server over stdio, which is what MCP clients expect.

## Add it to your MCP client

### Cursor

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=geoseo&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJnZW9zZW8tbWNwIl19)

Or add it to `~/.cursor/mcp.json` by hand (see [`examples/cursor-mcp.json`](examples/cursor-mcp.json)).

### Claude Code

```bash
claude mcp add geoseo -- uvx geoseo-mcp

# with keys
claude mcp add geoseo \
  -e GEOSEO_OPENAI_API_KEY=sk-... \
  -e GEOSEO_PERPLEXITY_API_KEY=pplx-... \
  -- uvx geoseo-mcp
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "geoseo": {
      "command": "uvx",
      "args": ["geoseo-mcp"],
      "env": {
        "GEOSEO_OPENAI_API_KEY": "sk-...",
        "GEOSEO_ANTHROPIC_API_KEY": "sk-ant-...",
        "GEOSEO_GEMINI_API_KEY": "AIza...",
        "GEOSEO_XAI_API_KEY": "xai-...",
        "GEOSEO_BRAVE_API_KEY": "...",
        "GEOSEO_PERPLEXITY_API_KEY": "pplx-...",
        "GEOSEO_SERPAPI_API_KEY": "...",
        "GEOSEO_GOOGLE_CLIENT_SECRET": "/absolute/path/to/client_secret.json",
        "GEOSEO_BING_WEBMASTER_API_KEY": "...",
        "GEOSEO_YANDEX_OAUTH_TOKEN": "y0_...",
        "GEOSEO_INDEXNOW_KEY": "..."
      }
    }
  }
}
```

Every key is optional; drop the ones you don't have. Other clients (Continue, Cline, Windsurf, VS Code) take the same `command` / `args` / `env` block. See [`examples/`](examples/).

Then just ask:

> "Which of ChatGPT, Claude, Gemini and Perplexity cite acme.com for 'best CRM for startups'? Run 3 samples each."
> "Audit my `./content` folder and show the 5 worst pages."
> "Build the internal link graph and find orphan pages."

## What it covers

| Surface | Tools |
| --- | --- |
| **Google Search** | GSC performance, URL inspection, sitemaps |
| **Bing Webmaster** | Site stats, query/page stats, URL info, URL submission, crawl issues |
| **Yandex Webmaster** | Site quality index, popular queries, important-page status, recrawl queue, diagnostics + broken internal links |
| **Bing / Yandex / Naver / Seznam** | IndexNow submission |
| **Google AI Overviews** | `aio_check` + `aio_citation_check` via SerpAPI |
| **LLM citations** | ChatGPT (web search), Claude (web search), Gemini (Google Search grounding), Perplexity (Agent API), Grok (xAI web search), Brave (Answers API), plus `multi_llm_*` tools that fan out across all of them |
| **On-page** | Title / meta / heading / schema / internal-link audit, 0-100 score, optional JS rendering |
| **Internal link graph** | Orphans, dead-ends, hubs, dangling links, related-page suggestions with anchor hints (TF-IDF by default, or OpenAI / Gemini / local embeddings) |
| **`llms.txt`** | Generate from a folder of HTML, validate against the spec |
| **Trend tracking** | Local SQLite snapshots of GSC, LLM citations and AIO, with trend tools |

MIT licensed and local-first: your credentials and data stay on your machine.

## How citation checks work

`multi_llm_citation_check(questions, target_domain)` asks every configured engine each question several times (`samples`, default 3), because LLM answers vary from run to run. For each engine you get:

- `citation_rate` with a 95% Wilson interval, plus a per-question `cited_rate` and a `stable` flag
- `mention_rate` and `unlinked_mention_rate`: answers that name your brand without linking to you
- `top_competing_domains`: who gets cited instead of you
- subdomain-aware matching (`docs.acme.com` counts for `acme.com`)

Brand aliases are derived from the domain (`acme.com` → `acme`) and you can pass your own via `brand_aliases`. Requests run in parallel up to `GEOSEO_MAX_CONCURRENCY` (default 8).

## Rough costs

Approximate list prices as of October 2026; check each provider's pricing page before running large batches.

| Engine | What we call | Approx. cost per query |
| --- | --- | --- |
| ChatGPT ([pricing](https://platform.openai.com/docs/pricing)) | Responses API, `gpt-5-mini` + `web_search` | ~$0.01 search fee + tokens, roughly $0.01-0.02 |
| Claude ([pricing](https://docs.anthropic.com/en/docs/about-claude/pricing)) | Messages API + `web_search` tool | $10 / 1k searches + tokens |
| Gemini ([pricing](https://ai.google.dev/gemini-api/docs/pricing)) | `gemini-3.5-flash-lite` + Google Search grounding | 5,000 free grounded requests / month, then $14 / 1k + tokens |
| Perplexity ([pricing](https://docs.perplexity.ai/docs/getting-started/pricing)) | Agent API, `fast` preset | ~$2.50 / 1k searches + tokens |
| Brave ([pricing](https://api-dashboard.search.brave.com/documentation/services/answers)) | Answers API, streaming with citations | ~$4 / 1k searches + $5 / M tokens |
| Google AI Overviews ([pricing](https://serpapi.com/pricing)) | SerpAPI | 250 free searches / month, then plan pricing |

A 10-question check with 3 samples across four engines is 120 calls, which is usually well under $2. Use `samples=1` for quick spot checks.

## Get credentials

- **OpenAI**: [API key](https://platform.openai.com/api-keys). Uses the Responses API with the `web_search` tool. Override the model with `GEOSEO_OPENAI_MODEL`.
- **Anthropic**: [API key](https://console.anthropic.com/settings/keys). Uses Claude with the server-side web search tool.
- **Gemini**: [API key from AI Studio](https://aistudio.google.com/app/apikey). Uses Google Search grounding (the same index AI Overviews use).
- **Perplexity**: [API key](https://www.perplexity.ai/settings/api). Uses the Agent API with the `fast` preset; set `GEOSEO_PERPLEXITY_EFFORT` or `GEOSEO_PERPLEXITY_MODEL` to change it.
- **xAI Grok**: [API key from the xAI console](https://console.x.ai), set as `GEOSEO_XAI_API_KEY`. Uses the Responses API with the `web_search` tool; override the model (default `grok-4.3`) with `GEOSEO_GROK_MODEL`.
- **Brave Answers**: [API key with the Answers plan](https://api-dashboard.search.brave.com), set as `GEOSEO_BRAVE_API_KEY`. Answers come from Brave's own index.
- **SerpAPI**: [API key](https://serpapi.com/manage-api-key). Free plan: 250 searches/month. Used for AI Overviews tracking.
- **Google Search Console**: see [`docs/setup-gsc.md`](docs/setup-gsc.md). One-time OAuth flow.
- **Bing Webmaster**: API key from [Bing Webmaster Tools](https://www.bing.com/webmasters/) → Settings → API access.
- **Yandex Webmaster**: OAuth token. [Register an app](https://oauth.yandex.com/client/new) with both `webmaster:hostinfo` and `webmaster:verify` (hostinfo alone only lists sites), then get a token via `https://oauth.yandex.com/authorize?response_type=token&client_id=<id>` and set `GEOSEO_YANDEX_OAUTH_TOKEN`. [Docs](https://yandex.com/dev/webmaster/doc/en/tasks/how-to-get-oauth).
- **IndexNow**: any random 32-char hex string hosted at `https://yourdomain.com/<key>.txt`. [Spec](https://www.indexnow.org/documentation).

Tools that need a key you haven't set return a clear error; everything else keeps working.

## Configuration

| Env var | Default | What it does |
| --- | --- | --- |
| `GEOSEO_TOOLSETS` | all | Comma-separated toolsets to expose: `gsc,bing,yandex,indexing,llm,aio,audit,graph,trend`. Fewer tools means less context for your agent. |
| `GEOSEO_CITATION_SAMPLES` | `3` | Default samples per question for `multi_llm_citation_check` (max 10). |
| `GEOSEO_MAX_CONCURRENCY` | `8` | Max parallel LLM requests. |
| `GEOSEO_OPENAI_MODEL` | `gpt-5-mini` | Model for ChatGPT checks. |
| `GEOSEO_ANTHROPIC_MODEL` | `claude-sonnet-5-5` | Model for Claude checks. |
| `GEOSEO_GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model for Gemini checks. |
| `GEOSEO_GROK_MODEL` | `grok-4.3` | Model for Grok checks. |
| `GEOSEO_PERPLEXITY_EFFORT` / `GEOSEO_PERPLEXITY_MODEL` | `fast` / unset | Perplexity Agent API preset, or a pinned model. |
| `GEOSEO_TRANSPORT` | `stdio` | `stdio` or `http` (streamable HTTP). |
| `GEOSEO_HOST` / `GEOSEO_PORT` | `127.0.0.1` / `8000` | Bind address for HTTP. |
| `GEOSEO_DB` | user data dir | SQLite file for trend snapshots. |

Example: only the keyless audit tools, for a lean agent context:

```json
"env": { "GEOSEO_TOOLSETS": "audit,graph" }
```

### Streamable HTTP

```bash
uvx geoseo-mcp serve --transport http --port 8000
# MCP endpoint: http://127.0.0.1:8000/mcp
```

It binds to localhost by default. There is no built-in auth, so put it behind a proxy you trust before exposing it anywhere.

### JavaScript rendering

`audit_page` reads raw HTML by default. If a page looks like a JS shell (an empty SPA root or almost no text), it adds a `js_rendering` finding. Install the extra and pass `render=True` (or `--render` on the CLI) to audit the rendered DOM:

```bash
pip install 'geoseo-mcp[render]' && playwright install chromium
```

## Tools (47)

- **Status**: `geoseo_status`, `list_llm_engines`
- **Google Search Console**: `gsc_list_sites`, `gsc_performance`, `gsc_inspect_url`, `gsc_submit_sitemap`
- **Bing Webmaster**: `bing_list_sites`, `bing_query_stats`, `bing_page_stats`, `bing_url_info`, `bing_submit_url`, `bing_crawl_issues`
- **Yandex Webmaster**: `yandex_list_sites`, `yandex_site_summary`, `yandex_query_stats`, `yandex_url_info`, `yandex_submit_url`, `yandex_crawl_issues`
- **Indexing**: `indexnow_submit_url`, `indexnow_submit_urls`
- **LLM citations**: `perplexity_query`, `perplexity_citation_check`, `openai_query`, `claude_query`, `gemini_query`, `grok_query`, `brave_query`, `multi_llm_query`, **`multi_llm_citation_check`**
- **Google AI Overviews**: `aio_check`, `aio_citation_check`
- **On-page**: `audit_page`, `audit_site`, `find_broken_external_links`, `lint_schema_page`, `lint_schema_site`
- **Link graph**: `internal_link_graph`, `suggest_internal_links`
- **llms.txt**: `generate_llms_txt`, `validate_llms_txt`
- **Trends**: `trend_init`, `trend_stats`, `snapshot_gsc`, `snapshot_llm_citations`, `snapshot_serp_aio`, `trend_gsc`, `trend_llm_citations`

`suggest_internal_links` uses TF-IDF by default (offline, free). Pass `mode="openai"`, `"gemini"` or `"local"` (sentence-transformers) for embedding similarity; vectors are cached in SQLite by content hash.

For Yandex tools, pass a normal URL as `site`; it's matched to the Yandex host id (`https:example.com:443`), following the main mirror. `yandex_url_info` only covers pages in "Monitoring important pages" (Yandex has no arbitrary-URL inspect endpoint).

Snapshots are append-only and stored at `$GEOSEO_DB`. Schedule the `snapshot_*` tools weekly to build a private time series of your AI-search visibility.

## Roadmap

Tracked in [issues](https://github.com/Rachit8484/geoseo-mcp/issues): broken-link prospector, schema linter, Grok and Brave citation engines, embedding-based link suggestions, Yandex Webmaster.

## Contributing

PRs welcome. Each engine is a module in `src/geoseo_mcp/engines/` that exposes `query()` and returns the standard `{engine, question, model, answer, citations, cited_domains, usage}` shape; tools live in `src/geoseo_mcp/tools/`. See [`docs/architecture.md`](docs/architecture.md).

```bash
git clone https://github.com/Rachit8484/geoseo-mcp.git && cd geoseo-mcp
uv sync --extra dev
uv run ruff check src tests && uv run pytest
```

## License

MIT. See [`LICENSE`](LICENSE).
