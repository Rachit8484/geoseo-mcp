# geoseo-mcp

> The only open-source MCP server that covers traditional SEO **and** Generative Engine Optimization (GEO) across Google, Bing, Yandex, and the major LLMs — in one server.

[![PyPI](https://img.shields.io/pypi/v/geoseo-mcp.svg)](https://pypi.org/project/geoseo-mcp/)
[![CI](https://github.com/Rachit8484/geoseo-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Rachit8484/geoseo-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)

## Why this exists

Every other SEO MCP picks one lane:

- `mcp-gsc` — Google Search Console only.
- `brightdata-mcp` — web access with a GEO bolt-on, vendor-coupled.
- `geo-optimizer-skill` — GEO scoring only, no traditional SEO.
- Frase / Conductor / Cairrot — closed SaaS.

`geoseo-mcp` unifies them. One MCP, one config, every search surface that matters in 2026:

| Surface | Tools |
| --- | --- |
| **Google Search** | GSC performance, URL inspection, sitemaps, Indexing API |
| **Bing Webmaster** | Verified-site stats, query/page stats, URL inspect, fast submit, crawl issues |
| **Bing / Yandex / Naver / Seznam** | IndexNow submission |
| **Google AI Overviews** | `aio_check` + `aio_citation_check` via SerpAPI |
| **LLM citations** | Perplexity, ChatGPT (web search), Claude (web search), Gemini (Google Search grounding), plus a `multi_llm_*` super-tool that fans out across all four in parallel |
| **On-page** | Title / meta / heading / schema / internal-link audit + 0-100 score |
| **Internal link graph** | Orphans, dead-ends, hubs, dangling links, TF-IDF related-page suggestions with anchor hints |
| **`llms.txt`** | Generate from a folder of HTML, validate against the spec |
| **Trend tracking** | Local SQLite snapshots of GSC + LLM citations + AIO; time-series trend tools |

MIT licensed. Runs locally over stdio. No hosting, no API key gating, your credentials never leave your machine.

## Status

**v0.3 — alpha.** 36 tools across GSC, Bing Webmaster, IndexNow, ChatGPT, Claude, Gemini, Perplexity, Google AI Overviews, on-page + folder audits, `llms.txt`, internal link graph + suggestions, and local SQLite trend tracking. See [`ROADMAP`](#roadmap).

## Install

```bash
# Using uv (recommended)
uvx geoseo-mcp

# Or pip
pip install geoseo-mcp
```

Or from source:

```bash
git clone https://github.com/Rachit8484/geoseo-mcp.git
cd geoseo-mcp
pip install -e ".[dev]"
```

## Try it without any credentials

Several tools work with **zero configuration** — useful to kick the tires before you wire up any API keys.

```bash
# audit a single page
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"audit_page","arguments":{"source":"https://example.com"}}}' \
  | uvx geoseo-mcp

# audit a whole folder of HTML
... "audit_site","arguments":{"folder":"./content"}
# build the internal link graph
... "internal_link_graph","arguments":{"folder":"./content","site_host":"yourdomain.com"}
# generate llms.txt
... "generate_llms_txt","arguments":{"folder":"./content","site_url":"https://yourdomain.com"}
```

In an MCP client (Cursor / Claude Desktop / Continue / Cline), it's even simpler — just ask:
> "Audit my `./content` folder and tell me the 5 worst-scoring pages"
> "Build the internal link graph and find orphan pages"
> "Generate an llms.txt for yourdomain.com from `./content`"

## Configure your MCP client

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "geoseo": {
      "command": "uvx",
      "args": ["geoseo-mcp"],
      "env": {
        "GEOSEO_GOOGLE_CLIENT_SECRET": "/absolute/path/to/client_secret.json",
        "GEOSEO_BING_WEBMASTER_API_KEY": "your-bing-key",
        "GEOSEO_INDEXNOW_KEY": "your-indexnow-key",
        "GEOSEO_PERPLEXITY_API_KEY": "pplx-...",
        "GEOSEO_OPENAI_API_KEY": "sk-...",
        "GEOSEO_ANTHROPIC_API_KEY": "sk-ant-...",
        "GEOSEO_GEMINI_API_KEY": "AIza...",
        "GEOSEO_SERPAPI_API_KEY": "..."
      }
    }
  }
}
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or the Windows equivalent:

```json
{
  "mcpServers": {
    "geoseo": {
      "command": "uvx",
      "args": ["geoseo-mcp"],
      "env": {
        "GEOSEO_GOOGLE_CLIENT_SECRET": "/absolute/path/to/client_secret.json",
        "GEOSEO_BING_WEBMASTER_API_KEY": "your-bing-key",
        "GEOSEO_INDEXNOW_KEY": "your-indexnow-key",
        "GEOSEO_PERPLEXITY_API_KEY": "pplx-...",
        "GEOSEO_OPENAI_API_KEY": "sk-...",
        "GEOSEO_ANTHROPIC_API_KEY": "sk-ant-...",
        "GEOSEO_GEMINI_API_KEY": "AIza...",
        "GEOSEO_SERPAPI_API_KEY": "..."
      }
    }
  }
}
```

See [`examples/`](examples/) for ready-to-paste configs.

## Get credentials

- **Google Search Console** — see [`docs/setup-gsc.md`](docs/setup-gsc.md). One-time OAuth flow.
- **IndexNow** — generate any random 32-char hex string and host it at `https://yourdomain.com/<key>.txt`. [Spec.](https://www.indexnow.org/documentation)
- **Perplexity** — [API key from settings](https://www.perplexity.ai/settings/api). Pay-as-you-go, ~$1 per 1000 queries.
- **OpenAI** — [API key](https://platform.openai.com/api-keys). Uses the Responses API + `web_search_preview` tool.
- **Anthropic** — [API key](https://console.anthropic.com/settings/keys). Uses Claude with the `web_search_20250305` server-side tool.
- **Gemini** — [API key from AI Studio](https://aistudio.google.com/app/apikey). Uses Google Search grounding (the same signal Google's AI Overviews are built on).
- **Bing Webmaster** — [API key from Bing Webmaster Tools](https://www.bing.com/webmasters/) → Settings → API access.
- **SerpAPI** — [API key](https://serpapi.com/manage-api-key). Free tier: 100 searches/month. Used for Google AI Overviews tracking (`aio_check`, `aio_citation_check`).

All credentials are optional — tools that need a key you don't have will return a clear error, the rest still work.

## Tools (v0.3 — 36 total)

### Status / discovery
- `geoseo_status` — show which engines are configured.
- `list_llm_engines` — show which LLM engines have keys.

### Google Search Console
- `gsc_list_sites`, `gsc_performance`, `gsc_inspect_url`, `gsc_submit_sitemap`

### Bing Webmaster Tools *(new in v0.3)*
- `bing_list_sites`, `bing_query_stats`, `bing_page_stats`, `bing_url_info`, `bing_submit_url`, `bing_crawl_issues`

### Indexing
- `indexnow_submit_url` — single URL → Bing/Yandex/Naver/Seznam/Yep.
- `indexnow_submit_urls` — batch up to 10,000 URLs.

### LLM citations (the GEO/AEO core)
- `perplexity_query` / `perplexity_citation_check`
- `openai_query` — ChatGPT with web search.
- `claude_query` — Claude with server-side web search.
- `gemini_query` — Gemini with Google Search grounding.
- **`multi_llm_query`** — fan out one question to every configured LLM in parallel.
- **`multi_llm_citation_check`** — citation-share metrics for your domain across ChatGPT + Claude + Gemini + Perplexity in one call. *This is the headline tool.*

### Google AI Overviews *(new in v0.3)*
- `aio_check` — does AIO fire for this query? Which URLs does it cite?
- `aio_citation_check` — AIO fire-rate + citation-share for your domain across a batch of queries.

### On-page audit
- `audit_page` — local file or URL: title, meta, H1-H3, word count, schema, OG, freshness, GEO quotability, 0-100 score, list of findings.
- `audit_site` — recursive audit over a folder, with worst-pages report.

### Internal link graph *(new in v0.3)*
- `internal_link_graph` — orphans, dead-ends, hub pages, dangling hrefs.
- `suggest_internal_links` — TF-IDF related-page suggestions per file with anchor-text hints.

### llms.txt
- `generate_llms_txt` — produce a spec-compliant `llms.txt` from a folder of HTML pages, grouped by URL prefix.
- `validate_llms_txt` — validate an existing file/URL with line-numbered issue list.

### Trend tracking *(new in v0.3 — local SQLite)*
- `trend_init`, `trend_stats`
- `snapshot_gsc` — persist a GSC performance pull as a timestamped snapshot.
- `snapshot_llm_citations` — persist `multi_llm_citation_check` results.
- `snapshot_serp_aio` — persist AIO citation results.
- `trend_gsc` — clicks/impressions/position over time (filterable by query/page).
- `trend_llm_citations` — citation share over time (per engine).

Snapshots are append-only and stored at `$GEOSEO_DB` (default: platform user-data dir / `geoseo.sqlite`). Schedule the `snapshot_*` tools weekly to build a private time-series of your AI-search visibility — no SaaS.

## Roadmap

- **v0.4** — Yandex Webmaster API, Grok citations, schema linter, broken-link prospector, vertical packs (YMYL / health / e-commerce).
- **v1.0** — Stable API, full test coverage, optional remote (HTTP) transport.

See [`docs/architecture.md`](docs/architecture.md) for the engine plug-in interface — adding a new search engine or LLM is one file.

## Contributing

PRs welcome. Each engine lives in `src/geoseo_mcp/engines/<name>.py` and implements the `Engine` ABC. Add yours, register it in `engines/__init__.py`, expose tools in `tools/`, ship.

## License

MIT. See [`LICENSE`](LICENSE).
