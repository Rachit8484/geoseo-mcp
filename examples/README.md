# Example client configs

- `cursor-mcp.json`: merge into `~/.cursor/mcp.json` (or `.cursor/mcp.json` in a project).
- `claude-desktop.json`: merge into `claude_desktop_config.json`.
- `audit-only.json`: no keys, just the audit / link-graph / llms.txt tools.

Every key is optional. Remove the ones you don't use; tools that need a missing key return a clear error.
