# Setting up Google Search Console access

`geoseo-mcp` uses the **OAuth installed-app flow** for GSC. The first time
you call any `gsc_*` tool, your browser opens for one-time consent and a
refresh token is cached on disk. Subsequent calls are silent.

## 1. Verify your site in Search Console

If you haven't already: https://search.google.com/search-console

`sc-domain:` properties (DNS-verified) work best — they cover www, non-www,
http, and https in one shot.

## 2. Create an OAuth client

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or pick a project.
3. **APIs & Services → Library** → enable **Google Search Console API**.
4. **APIs & Services → OAuth consent screen**:
   - User type: **External**.
   - Add yourself as a test user.
   - Scopes: you can leave default; we request only the
     `webmasters.readonly` and `webmasters` scopes at runtime.
5. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Desktop app**.
   - Download the JSON. Save it somewhere safe; refer to it as
     `client_secret.json` below.

## 3. Tell `geoseo-mcp` where the file is

Set the env var in your MCP client config (Cursor, Claude Desktop, etc.):

```jsonc
{
  "mcpServers": {
    "geoseo": {
      "command": "uvx",
      "args": ["geoseo-mcp"],
      "env": {
        "GEOSEO_GOOGLE_CLIENT_SECRET": "/Users/you/.config/geoseo/client_secret.json"
      }
    }
  }
}
```

## 4. First run

In Cursor or Claude, ask the agent:

> "Run `geoseo_status` and then `gsc_list_sites`."

A browser tab opens, you click **Allow**, and the refresh token is cached at
your platform user-data dir (`~/Library/Application Support/geoseo-mcp/gsc_token.json`
on macOS). All subsequent runs are non-interactive.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `EngineNotConfiguredError` | `GEOSEO_GOOGLE_CLIENT_SECRET` is unset or wrong path. |
| `403 / accessNotConfigured` | Enable the **Google Search Console API** for your project. |
| `403 / userNotInTrusted` | You're still on the OAuth test list and your account isn't added. Add yourself as a test user. |
| Browser doesn't open | The MCP runs headless inside the client. Run `geoseo-mcp` from a normal shell once to do the consent flow, then reuse the cached token. |
| `invalid_grant` after weeks | Token expired without refresh. Delete `gsc_token.json` and rerun. |
