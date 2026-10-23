# Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               MCP client (Cursor, Claude, ...)              │
└──────────────────────────┬──────────────────────────────────┘
                           │ stdio, or streamable HTTP at /mcp
┌──────────────────────────▼──────────────────────────────────┐
│  server.py    FastMCP("geoseo-mcp")                         │
│   ├─ geoseo_status()                                        │
│   └─ TOOLSETS (filtered by GEOSEO_TOOLSETS)                 │
│       gsc, bing, indexing, llm, aio, audit, graph, trend    │
│       → tools/<name>_tools.register(mcp)                    │
│                                                             │
│  __main__.py  CLI: serve / audit / llms-txt / status ...    │
│                                                             │
│  engines/  (external service wrappers, return plain dicts)  │
│   ├─ gsc.py, bing.py, indexnow.py                           │
│   ├─ openai.py, anthropic.py, gemini.py, perplexity.py      │
│   ├─ serpapi.py     Google AI Overviews                     │
│   ├─ multi_llm.py   parallel fan-out + citation stats       │
│   └─ _domains.py    domain matching + brand mentions        │
│                                                             │
│  audit/on_page.py  BeautifulSoup analysis (+ Playwright)    │
│  auth/google.py    OAuth installed-app flow + token cache   │
│  config.py         env-var driven, all credentials optional │
│  storage/          SQLite trend snapshots                   │
└─────────────────────────────────────────────────────────────┘
```

## Engine plug-in contract

To add a new engine (e.g. `brave`, `grok`, `yandex`):

1. Create `src/geoseo_mcp/engines/<name>.py`.
2. Expose plain functions that return JSON-serializable `dict` / `list`.
3. Raise `EngineNotConfiguredError("<name>", hint)` when credentials are missing.
4. Raise `EngineError(message)` for upstream failures.
5. Add a credential field to `Config` in `config.py`.
6. Surface its `configured` status in `server.py::geoseo_status`.
7. Create / extend a tool module in `tools/` with `register(mcp)`.
8. Add it to `server.py::TOOLSETS` (new module = new toolset name).
9. Add mocked tests under `tests/` (see `conftest.py::mock_http`). No live API calls in CI.

LLM engines should return `{engine, question, model, answer, citations,
cited_domains, usage}` and use `_domains.domain_of()` so subdomain matching
and brand-mention detection in `multi_llm.py` work unchanged.

That's the entire contract. No registry, no DI container, no plugin discovery
— just import-and-register, which keeps the dependency graph debuggable.

## Transports

- Zero hosting cost.
- User credentials never leave the user's machine.
- Easy contribution: clone, `pip install -e .`, run.
- All major MCP clients (Cursor, Claude Desktop, Windsurf, Zed) support stdio.

stdio is the default. `geoseo-mcp serve --transport http` serves the same
tools over streamable HTTP at `/mcp` (FastMCP handles it; no tool code
changes). It binds to 127.0.0.1 and has no auth of its own, so put a proxy in
front before sharing it.

## Why Python

- Best-in-class libraries for the targets we wrap (Google API client,
  BeautifulSoup, httpx, lxml).
- FastMCP is the most ergonomic MCP SDK in the Python ecosystem in 2026.
