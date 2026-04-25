# geoseo-mcp

> The only open-source MCP server that covers traditional SEO **and** Generative Engine Optimization (GEO) across Google, Bing, Yandex, and the major LLMs — in one server.

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
| **Bing / Yandex / Naver / Seznam** | IndexNow submission |
| **LLM citations** | Perplexity, ChatGPT (web search), Claude (web search), Gemini (Google Search grounding), plus a `multi_llm_*` super-tool that fans out across all four in parallel. Grok / Google AIO planned. |
| **On-page** | Title / meta / heading / schema / internal-link audit + 0-100 score |
| **`llms.txt`** | Generate from a folder of HTML, validate against the spec |

MIT licensed. Runs locally over stdio. No hosting, no API key gating, your credentials never leave your machine.

## Status

**v0.2 — alpha.** Multi-LLM citation tracking shipped. See [`ROADMAP`](#roadmap).

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
        "GEOSEO_INDEXNOW_KEY": "your-indexnow-key",
        "GEOSEO_PERPLEXITY_API_KEY": "pplx-...",
        "GEOSEO_OPENAI_API_KEY": "sk-...",
        "GEOSEO_ANTHROPIC_API_KEY": "sk-ant-...",
        "GEOSEO_GEMINI_API_KEY": "AIza..."
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
        "GEOSEO_INDEXNOW_KEY": "your-indexnow-key",
        "GEOSEO_PERPLEXITY_API_KEY": "pplx-...",
        "GEOSEO_OPENAI_API_KEY": "sk-...",
        "GEOSEO_ANTHROPIC_API_KEY": "sk-ant-...",
        "GEOSEO_GEMINI_API_KEY": "AIza..."
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

All credentials are optional — tools that need a key you don't have will return a clear error, the rest still work.

## Tools (v0.2)

### Status / discovery
- `geoseo_status` — show which engines are configured.
- `list_llm_engines` — show which LLM engines have keys.

### Google Search Console
- `gsc_list_sites`, `gsc_performance`, `gsc_inspect_url`, `gsc_submit_sitemap`

### Indexing
- `indexnow_submit_url` — single URL → Bing/Yandex/Naver/Seznam/Yep.
- `indexnow_submit_urls` — batch up to 10,000 URLs.

### LLM citations (the GEO/AEO core)
- `perplexity_query` / `perplexity_citation_check`
- `openai_query` — ChatGPT with web search.
- `claude_query` — Claude with server-side web search.
- `gemini_query` — Gemini with Google Search grounding (proxy for AI Overviews).
- **`multi_llm_query`** — fan out one question to every configured LLM in parallel.
- **`multi_llm_citation_check`** — citation-share metrics for your domain across ChatGPT + Claude + Gemini + Perplexity in one call. *This is the headline tool.*

### On-page audit
- `audit_page` — local file or URL: title, meta, H1-H3, word count, schema, OG, freshness, GEO quotability, 0-100 score, list of findings.
- `audit_site` — recursive audit over a folder, with worst-pages report.

### llms.txt
- `generate_llms_txt` — produce a spec-compliant `llms.txt` from a folder of HTML pages, grouped by URL prefix.
- `validate_llms_txt` — validate an existing file/URL with line-numbered issue list.

## Roadmap

- **v0.3** — Bing Webmaster Tools API, Yandex Webmaster API, Google AI Overviews tracking via SerpAPI/Bright Data, internal link graph + suggestions, SQLite snapshots for trend tracking.
- **v0.4** — Vertical packs (YMYL/health, e-commerce), schema linter, broken-link prospector.
- **v1.0** — Stable API, full test coverage, optional remote (HTTP) transport.

See [`docs/architecture.md`](docs/architecture.md) for the engine plug-in interface — adding a new search engine or LLM is one file.

## Contributing

PRs welcome. Each engine lives in `src/geoseo_mcp/engines/<name>.py` and implements the `Engine` ABC. Add yours, register it in `engines/__init__.py`, expose tools in `tools/`, ship.

## License

MIT. See [`LICENSE`](LICENSE).
