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
| **LLM citations** | Perplexity (v0.1), ChatGPT / Claude / Gemini / Grok / Google AIO (v0.2+) |
| **On-page** | Title / meta / heading / schema / internal-link audit |
| **`llms.txt`** | Generate, validate (v0.2) |

MIT licensed. Runs locally over stdio. No hosting, no API key gating, your credentials never leave your machine.

## Status

**v0.1 — alpha.** Narrow scope, ships first, iterates fast. See [`ROADMAP`](#roadmap) below.

## Install

```bash
# Using uv (recommended)
uvx geoseo-mcp

# Or pip
pip install geoseo-mcp
```

Or from source:

```bash
git clone https://github.com/your-org/geoseo-mcp.git
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
        "GEOSEO_PERPLEXITY_API_KEY": "pplx-..."
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
        "GEOSEO_PERPLEXITY_API_KEY": "pplx-..."
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

All credentials are optional — tools that need a key you don't have will return a clear error, the rest still work.

## Tools (v0.1)

### Google Search Console
- `gsc_list_sites` — list verified properties.
- `gsc_performance` — clicks/impressions/CTR/position by query, page, country, device, date.
- `gsc_inspect_url` — index status for a single URL.
- `gsc_submit_sitemap` — submit/resubmit a sitemap.

### Indexing
- `indexnow_submit_url` — submit one URL (hits Bing, Yandex, Naver, Seznam, Yep at once).
- `indexnow_submit_urls` — batch up to 10,000 URLs.
- `google_indexing_submit_url` — Google Indexing API (only valid for `JobPosting` / `BroadcastEvent` per Google's policy; documented honestly).

### LLM citations
- `perplexity_query` — ask Perplexity a question, return answer + cited sources.
- `perplexity_citation_check` — given a list of queries and your domain, return citation rate + competing domains.

### On-page audit
- `audit_page` — given a local file path or URL, return findings: title, meta description, H1/H2 structure, word count, schema (JSON-LD), internal/external links, image alt coverage, OG tags, canonical, `llms.txt` presence.
- `audit_site` — recursive audit over a folder of HTML files.

## Roadmap

- **v0.2** — Bing Webmaster Tools API, Yandex Webmaster API, ChatGPT + Claude + Gemini citation tools, `llms.txt` generator.
- **v0.3** — Google AI Overviews tracking via SerpAPI/Bright Data, internal link graph + suggestions, SQLite snapshots for trend tracking.
- **v0.4** — Vertical packs (YMYL/health, e-commerce), schema linter, broken-link prospector.
- **v1.0** — Stable API, full test coverage, optional remote (HTTP) transport.

See [`docs/architecture.md`](docs/architecture.md) for the engine plug-in interface — adding a new search engine or LLM is one file.

## Contributing

PRs welcome. Each engine lives in `src/geoseo_mcp/engines/<name>.py` and implements the `Engine` ABC. Add yours, register it in `engines/__init__.py`, expose tools in `tools/`, ship.

## License

MIT. See [`LICENSE`](LICENSE).
