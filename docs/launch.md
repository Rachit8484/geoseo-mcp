# Launch copy — geoseo-mcp v0.3.0

Ready-to-paste posts. Tone: builder-to-builder, evidence-first, no buzzword soup.

Repo: https://github.com/Rachit8484/geoseo-mcp
Release: https://github.com/Rachit8484/geoseo-mcp/releases/tag/v0.3.0

---

## 1. Hacker News — Show HN

**Title (≤80 chars):**

> Show HN: geoseo-mcp – open-source MCP for SEO, GEO, and AI Overviews

**Body:**

I built an open-source MCP server that unifies the SEO + GEO toolchain into one place. The premise: every other SEO MCP I found was single-lane (GSC only, GEO scoring only, vendor-coupled), and every "track me in ChatGPT" SaaS is closed-source and $99/mo. So I made the union.

What it does, in one MCP, all credentials local:

- Google Search Console (performance, URL inspect, sitemaps)
- Bing Webmaster Tools (single-key auth, query/page stats, fast submit)
- IndexNow (Bing / Yandex / Naver / Seznam / Yep)
- LLM citation tracking across Perplexity, ChatGPT (web search), Claude (web search), and Gemini (Google Search grounding) — including a `multi_llm_citation_check` that fans out across all four in parallel and reports per-engine citation share for your domain
- Google AI Overviews tracking via SerpAPI (`aio_check`, `aio_citation_check`)
- On-page audit (0–100 score) — single file or recursive folder
- Internal link graph: orphans, dead-ends, hubs, dangling hrefs, plus TF-IDF related-page suggestions with anchor-text hints
- `llms.txt` generator + validator (the [llmstxt.org](https://llmstxt.org) spec)
- Local SQLite snapshot store for trend tracking — schedule the `snapshot_*` tools weekly to build your own time-series of search/LLM visibility, no SaaS

36 tools total. Python 3.11+, FastMCP, runs locally over stdio. MIT.

I'm dogfooding it on a small recovery site I run. The internal-link-graph tool found that the product page (sobriety tracker) had **0 inbound internal links** despite 60+ blog posts — a real "leaving SEO equity on the floor" finding. The suggester ranked 8 pages that should link to it with anchor hints derived from term overlap.

Adding a new search engine or LLM is one file (`engines/<name>.py`) — happy to take PRs for Yandex Webmaster, Grok, You.com, Brave, etc.

Repo: https://github.com/Rachit8484/geoseo-mcp

Honest weaknesses I'd love feedback on:
- AIO tracking depends on SerpAPI (paid after 100/mo). Want to swap in a self-hosted SERP scraper but didn't want to ship something that ToS-trips Google by default.
- The link-suggester is TF-IDF, not embeddings. Cheap and deterministic but obviously dumber than a real semantic model. Pluggable.
- No Yandex Webmaster yet (OAuth flow is hairy). Tracking it for v0.4.

---

## 2. r/mcp

**Title:**

> [Open-source] geoseo-mcp v0.3 — 36 tools across GSC, Bing, ChatGPT/Claude/Gemini/Perplexity citations, Google AI Overviews, and link-graph suggestions

**Body:**

Hey r/mcp,

Shipped v0.3.0 of `geoseo-mcp` — an MCP server that bundles the SEO + Generative Engine Optimization toolchain into one place. Everything runs locally, MIT licensed, 36 tools.

The thing I think will be most relevant to this sub: **every API is pluggable as a one-file engine.** If you want Brave Search, You.com, Mojeek, Kagi citations, Yandex Webmaster, etc., it's `src/geoseo_mcp/engines/<name>.py` + a thin tool wrapper. PRs welcome.

What's in v0.3 specifically:
- Google AI Overviews tracking (via SerpAPI)
- Bing Webmaster Tools (single API key, no OAuth)
- Internal link graph + TF-IDF related-page suggester
- Local SQLite snapshot store for trends — `snapshot_gsc`, `snapshot_llm_citations`, `snapshot_serp_aio`, then read back with `trend_*` tools

What was already in v0.1/v0.2:
- GSC (perf / URL inspect / sitemaps)
- IndexNow (Bing/Yandex/Naver/Seznam)
- Per-LLM citation tools for Perplexity, ChatGPT, Claude, Gemini
- A `multi_llm_citation_check` that fans out across all four in parallel
- Static HTML on-page audit (0–100 score)
- `llms.txt` generator + validator

Configure once, ask Claude/Cursor/whatever: "What's our citation share in ChatGPT vs Claude vs Gemini for these 30 buyer questions, and how is that trending week-over-week?" — and it's one tool call.

```
uvx geoseo-mcp
```

Repo: https://github.com/Rachit8484/geoseo-mcp

Would love bug reports, missing-engine PRs, or "your prompt patterns for `multi_llm_citation_check` suck — try these" comments.

---

## 3. r/SEO + r/bigseo (same body, slightly tightened)

**Title:**

> Built a free open-source tool that tracks your citations in ChatGPT, Claude, Gemini, Perplexity, and Google AI Overviews — all in one place

**Body:**

Hey, I got tired of Profound / Otterly / Peec / [pick your $99-$500/mo SaaS] gating "track me in ChatGPT" behind paywalls and hiding the methodology, so I built an open-source alternative.

It's an MCP server (Model Context Protocol — works with Claude Desktop, Cursor, Continue, Cline, anything that speaks MCP). MIT, runs locally, 36 tools.

What you get for free:

- **GEO / AEO**: One tool — `multi_llm_citation_check` — takes a list of buyer questions and your domain, asks ChatGPT (with web search), Claude (with web search), Gemini (with Google Search grounding), and Perplexity in parallel, and tells you how often each engine cited *you* vs your competitors. Per-engine breakdown, top competing domains.
- **Google AI Overviews**: `aio_check` and `aio_citation_check` use SerpAPI to detect when AIO fires for a query and which URLs it cites. AIO answer text is returned too — this is what you optimize for.
- **Trend tracking**: Schedule the `snapshot_*` tools weekly (cron, n8n, whatever) and the data goes into a local SQLite DB. Read it back with `trend_gsc` and `trend_llm_citations`. No vendor.
- **Traditional SEO**: GSC (performance / URL inspect / sitemaps), Bing Webmaster Tools (query stats / fast submit / crawl issues), IndexNow (Bing + Yandex + Naver + Seznam + Yep).
- **On-page audit**: 0–100 score, file or whole folder.
- **Internal link graph**: orphans, dead-ends, hubs, dangling links, plus a related-page suggester with anchor-text hints. Real finding from dogfooding on my own site: a product page had **zero internal links** despite 60+ blog posts — money on the floor.
- **`llms.txt` generator** for the new spec.

Costs:
- The MCP itself: free
- LLM API calls: ~$0.01–$0.05/query depending on engine
- SerpAPI for AIO: free for 100 searches/mo, then paid

Repo: https://github.com/Rachit8484/geoseo-mcp

Happy to answer questions about how the AIO citation methodology works, how to set up weekly snapshots, prompt patterns that work better than "where is X mentioned", etc.

---

## 4. Twitter / X — thread (8 tweets)

> 1/ I shipped an open-source MCP server that unifies SEO + GEO into one tool.
>
> 36 tools. Tracks your citations across ChatGPT, Claude, Gemini, Perplexity, AND Google AI Overviews. Plus GSC, Bing, IndexNow, on-page audits, internal-link graphs, llms.txt, and local SQLite trends.
>
> Free. MIT. Runs locally.
>
> https://github.com/Rachit8484/geoseo-mcp

> 2/ The headline tool: `multi_llm_citation_check`
>
> Give it a list of buyer questions + your domain. It asks ChatGPT (web search), Claude (web search), Gemini (Google grounding), and Perplexity *in parallel* and tells you how often each cited you vs competitors.
>
> Per-engine. One call.

> 3/ For Google AI Overviews specifically: `aio_check` and `aio_citation_check`.
>
> SerpAPI under the hood. Detects whether AIO fires for a query, parses the answer text + cited URLs, computes fire-rate and citation-share for your domain across a batch.

> 4/ Everything else is in here too:
>
> – Google Search Console
> – Bing Webmaster Tools
> – IndexNow (Bing/Yandex/Naver/Seznam/Yep)
> – On-page audit, file or folder, 0–100 score
> – `llms.txt` generator + validator
> – Internal link graph + related-page suggester
> – Local SQLite trend store

> 5/ Dogfooding finding from my own recovery site:
>
> Internal-link graph showed the product page had **0 inbound internal links** despite 60+ blog posts.
>
> SEO equity flushed down the toilet. The suggester ranked 8 pages that should link to it, with anchor-text hints.

> 6/ Architecture note for builders:
>
> Adding a new search engine or LLM is *one file* in `engines/`. Same shape, same patterns. Yandex Webmaster, Grok, Brave, You.com, Kagi, Mojeek — all welcome as PRs.

> 7/ Why I built it: every existing SEO MCP I found was single-lane (GSC only, GEO scoring only, vendor-coupled). Every "track me in ChatGPT" SaaS is closed-source and $99-$500/mo. So I made the union, MIT.

> 8/ One-liner to install:
>
> `uvx geoseo-mcp`
>
> https://github.com/Rachit8484/geoseo-mcp
>
> Stars / PRs / brutal feedback all welcome.

---

## 5. LinkedIn (single post — slightly more formal)

> The "I'm not getting cited in ChatGPT" anxiety has spawned a whole new SaaS category — Profound, Otterly, Peec, Goodie. They charge $99–$500/month to tell you the same thing: which queries your domain shows up in across the major LLMs.
>
> I built an open-source alternative. MIT, local, free. It's an MCP server, so it plugs straight into Claude Desktop / Cursor / any MCP-compatible AI agent.
>
> Beyond LLM citation tracking, it also covers Google Search Console, Bing Webmaster, IndexNow, Google AI Overviews (the on-SERP version of LLM optimization), on-page SEO audits, internal-link analysis with related-page suggestions, the `llms.txt` standard, and a local SQLite snapshot store so you can build your own week-over-week visibility trends without paying anyone.
>
> 36 tools total. v0.3.0 just shipped.
>
> If you're a tech SEO, an in-house team that doesn't want yet another SaaS subscription, or a developer building agentic SEO workflows — this is for you.
>
> https://github.com/Rachit8484/geoseo-mcp
>
> Feedback, stars, and contributions all welcome. Yandex Webmaster, Grok, Brave Search citations are open PRs waiting to happen — it's a one-file engine plug-in.

---

## 6. PH (Product Hunt) — short

**Tagline:** Open-source MCP for SEO + GEO across Google, Bing, and the major LLMs.

**Description:** geoseo-mcp is a free, open-source MCP server that brings GSC, Bing Webmaster, IndexNow, ChatGPT/Claude/Gemini/Perplexity citation tracking, Google AI Overviews monitoring, on-page audits, internal link graphs, and `llms.txt` tooling into one stdio server. Local-first, MIT, 36 tools.

**First comment from maker:**
Hey PH! I built this because every SEO MCP I tried was single-lane and every LLM-citation SaaS was closed and expensive. The headline feature is `multi_llm_citation_check` — fans out one batch of buyer questions to ChatGPT, Claude, Gemini, and Perplexity in parallel and reports per-engine citation share for your domain. Combined with the new `aio_citation_check` for Google AI Overviews, you get the full "where am I being cited in 2026" picture in two tool calls. Happy to answer anything!

---

## Where to post (priority order)

1. **HN Show HN** — biggest leverage if it sticks. Post Tue/Wed 9–11am PT.
2. **r/mcp** — small but high-signal audience for MCP launches.
3. **r/SEO + r/bigseo** — different demos, same body fine. Read sub rules; some require flair.
4. **Twitter / X** — thread, then DM SEO Twitter folks (Lily Ray, Aleyda Solis, Glen Allsopp, Jess Joyce) for an honest critique, not amplification.
5. **r/AeoSeo, r/aeo** — niche but exact ICP.
6. **LinkedIn** — same day as HN.
7. **Product Hunt** — schedule for the following Tuesday once HN feedback is in.
8. **MCP awesome lists** — open a PR to https://github.com/punkpeye/awesome-mcp-servers under "SEO".

## Pre-flight checks before posting

- [ ] Repo README screenshots / animated GIF of `multi_llm_citation_check` in Cursor (huge conversion lift).
- [ ] PyPI publish — currently install path is "from source". Ship to PyPI so `uvx geoseo-mcp` actually works for outsiders.
- [ ] Pin a Discord / Discussions tab for support.
- [ ] First-issue labels seeded with: "Add Yandex Webmaster engine", "Add Grok engine", "Add Brave Search citations", "Embedding-based link suggester".
