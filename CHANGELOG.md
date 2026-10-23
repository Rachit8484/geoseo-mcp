# Changelog

## 0.4.0 — unreleased

**The launch-readiness release.** Ready for PyPI, usable without any API keys.

### Added

- **Keyless CLI**: `geoseo-mcp audit <url|file>`, `audit-site <folder>`, `llms-txt <url>`, `generate-llms-txt <folder> <site_url>`, `status`, `--version`. Running with no arguments still starts the stdio server.
- **Streamable HTTP transport**: `geoseo-mcp serve --transport http [--host] [--port]` (or `GEOSEO_TRANSPORT=http`). Serves `/mcp`, binds to 127.0.0.1 by default.
- **`GEOSEO_TOOLSETS`**: expose only some tool groups (`gsc,bing,indexing,llm,aio,audit,graph,trend`). `geoseo_status` reports what is enabled.
- **JS rendering for `audit_page`**: optional `[render]` extra (Playwright). `render=True` / `--render` audits the rendered DOM, and pages that look like empty JS shells get a `js_rendering` finding.
- **`multi_llm_citation_check` sampling**: `samples` (default 3, `GEOSEO_CITATION_SAMPLES`) runs each question several times per engine and reports `citation_rate` with a 95% Wilson interval, per-question `cited_rate`, variance and a `stable` flag.
- **Unlinked brand mentions**: `mention_rate` / `unlinked_mention_rate`, with aliases derived from the domain or passed via `brand_aliases`.
- `server.json` for the official MCP Registry, plus the `mcp-name` marker in the README.
- `find_broken_external_links`: broken outbound-link prospector for a folder of HTML. Concurrent HEAD/GET checks, results grouped by status class with source pages and suggested actions, 7-day SQLite cache. (#7)
- `lint_schema_page` and `lint_schema_site`: JSON-LD linter for Google's structured-data requirements, with `@graph` support, nested Offer/AggregateRating/Review checks and per-site summaries. Rules live in `audit/_schema_rules.py`. (#5)
- xAI Grok engine and `grok_query` tool, using the Responses API `web_search` tool (Live Search `search_parameters` is retired). Grok joins `multi_llm_query` / `multi_llm_citation_check` automatically when `GEOSEO_XAI_API_KEY` is set. (#2)
- Mocked test suite for every LLM engine, citation logic, SerpAPI, CLI, toolsets and JS detection (no network in CI). CI now also runs on Python 3.13.

### Changed

- **Perplexity** moved from the retired Sonar Chat Completions to the Agent API (`/v1/agent`, `fast` preset by default). Cited sources come from the answer's `[n]` markers instead of every search result. New `GEOSEO_PERPLEXITY_EFFORT`; `GEOSEO_PERPLEXITY_MODEL` now pins a model, and legacy Sonar names map to effort levels.
- Default models: OpenAI `gpt-5-mini` (with the GA `web_search` tool instead of `web_search_preview`), Anthropic `claude-sonnet-5-5` (Sonnet 4.5 retires 2026-11-30), Gemini `gemini-3.5-flash-lite` (2.5 models are limited to existing users). All still overridable.
- Citation matching is subdomain-aware everywhere (`docs.acme.com` counts for `acme.com`, `notacme.com` doesn't).
- Gemini `cited_domains` now report the real source domains instead of the `vertexaisearch` redirect host; the API key goes in a header instead of the URL.
- LLM fan-out is capped by `GEOSEO_MAX_CONCURRENCY` (default 8).
- `snapshot_llm_citations` accepts `samples`.
- Packaging: SPDX license metadata, Python 3.13 classifier, `fastmcp>=3,<4`, user agent derived from the package version.
- Release workflow: checks the tag matches the package version, runs lint + tests, smoke-tests the wheel, then publishes via PyPI Trusted Publishing from the `pypi` environment.
- README rewritten around the keyless quickstart, with client install snippets and a rough cost table.

## 0.3.0 — 2026-04-25

**The GEO release.** 36 tools total (up from 19 in v0.2).

### Added

- **Bing Webmaster Tools** engine + 6 tools: `bing_list_sites`, `bing_query_stats`, `bing_page_stats`, `bing_url_info`, `bing_submit_url`, `bing_crawl_issues`. Single-API-key auth, no OAuth.
- **Google AI Overviews tracking** via SerpAPI: `aio_check` (does AIO fire? which URLs cited?), `aio_citation_check` (fire-rate + citation share for your domain across a batch of queries).
- **Internal link graph**: `internal_link_graph` reports orphans, dead-ends, hubs, dangling hrefs. `suggest_internal_links` returns TF-IDF related-page recommendations with anchor-text hints. Resolves both relative and absolute (same-host) URLs and falls back to URL-slug → filename matching, so `/blog/foo` correctly resolves to `foo.html`.
- **Local SQLite trend tracking**: `trend_init`, `trend_stats`, `snapshot_gsc`, `snapshot_llm_citations`, `snapshot_serp_aio`, `trend_gsc`, `trend_llm_citations`. Append-only snapshot store, your data never leaves your machine. Override location with `GEOSEO_DB`.

### Changed

- `geoseo_status` now reports config status for Bing Webmaster, SerpAPI, internal link graph, and trend storage in addition to existing engines.
- Server `instructions` updated to reflect the broader tool surface.
- Default user-agent bumped to `geoseo-mcp/0.3`.

### Config

- New env vars: `GEOSEO_BING_WEBMASTER_API_KEY`, `GEOSEO_SERPAPI_API_KEY`, `GEOSEO_DB`.

## 0.2.0 — 2026-04-25

- Added OpenAI (ChatGPT), Anthropic (Claude), and Google Gemini citation engines.
- `multi_llm_query` and `multi_llm_citation_check` (parallel fan-out across all configured LLMs).
- `generate_llms_txt` and `validate_llms_txt` for the [`llms.txt`](https://llmstxt.org) standard.

## 0.1.0 — 2026-04-25

- Initial release: GSC tools, IndexNow, Perplexity citations, on-page audit (file or folder).
