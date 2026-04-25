# Changelog

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
