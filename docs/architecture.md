# Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP client (Cursor)                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ stdio (JSON-RPC)
┌──────────────────────────▼──────────────────────────────────┐
│  server.py    FastMCP("geoseo-mcp")                         │
│   ├─ geoseo_status()                                        │
│   └─ tools/                                                 │
│       ├─ gsc_tools.register(mcp)                            │
│       ├─ indexing_tools.register(mcp)                       │
│       ├─ llm_tools.register(mcp)                            │
│       └─ audit_tools.register(mcp)                          │
│                                                             │
│  engines/  (external service wrappers, return plain dicts)  │
│   ├─ gsc.py        google-api-python-client                 │
│   ├─ indexnow.py   httpx                                    │
│   └─ perplexity.py httpx                                    │
│                                                             │
│  audit/on_page.py  BeautifulSoup-based static analysis      │
│  auth/google.py    OAuth installed-app flow + token cache   │
│  config.py         env-var driven, all credentials optional │
│  storage/          SQLite (v0.3+ for trend tracking)        │
└─────────────────────────────────────────────────────────────┘
```

## Engine plug-in contract

To add a new engine (e.g. `bing_webmaster`, `chatgpt`, `gemini`):

1. Create `src/geoseo_mcp/engines/<name>.py`.
2. Expose plain functions that return JSON-serializable `dict` / `list`.
3. Raise `EngineNotConfiguredError("<name>", hint)` when credentials are missing.
4. Raise `EngineError(message)` for upstream failures.
5. Add a credential field to `Config` in `config.py`.
6. Surface its `configured` status in `server.py::geoseo_status`.
7. Create / extend a tool module in `tools/` with `register(mcp)`.
8. Wire it in `server.py::build_server`.

That's the entire contract. No registry, no DI container, no plugin discovery
— just import-and-register, which keeps the dependency graph debuggable.

## Why stdio first

- Zero hosting cost.
- User credentials never leave the user's machine.
- Easy contribution: clone, `pip install -e .`, run.
- All major MCP clients (Cursor, Claude Desktop, Windsurf, Zed) support stdio.

A FastAPI / SSE transport can be added later for shared-team or hosted use
without changing tool code: FastMCP supports it natively.

## Why Python

- Best-in-class libraries for the targets we wrap (Google API client,
  BeautifulSoup, httpx, lxml).
- pandas/duckdb available for v0.3 trend math.
- FastMCP is the most ergonomic MCP SDK in the Python ecosystem in 2026.
