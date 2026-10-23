"""Entry point: ``geoseo-mcp`` (script) and ``python -m geoseo_mcp``.

With no arguments this starts the MCP server on stdio, which is what MCP
clients expect. Subcommands expose the keyless tools directly so you can try
the project without wiring up a client:

    geoseo-mcp audit https://example.com
    geoseo-mcp llms-txt https://example.com
    geoseo-mcp serve --transport http --port 8000
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from . import __version__


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _print_audit(rep: dict[str, Any]) -> None:
    print(f"{rep.get('url') or rep.get('source')}")
    print(f"  score: {rep['score']}/100")
    print(f"  title: {rep.get('title')!r}")
    words = f"  words: {rep['word_count']}"
    if rep.get("rendered"):
        words += f" (without JavaScript: {rep.get('raw_word_count')})"
    print(words)
    failing = [f for f in rep["findings"] if not f["ok"]]
    passing = [f for f in rep["findings"] if f["ok"]]
    if failing:
        print(f"\n  {len(failing)} issue(s):")
        for f in failing:
            detail = f"  [{f['detail']}]" if f.get("detail") else ""
            print(f"   ✗ {f['key']}: {f['message']}{detail}")
    print(f"\n  {len(passing)} check(s) passed. Use --json for the full report.")


def _cmd_serve(args: argparse.Namespace) -> int:
    from .server import build_server

    server = build_server()
    transport = args.transport or os.getenv("GEOSEO_TRANSPORT", "stdio")
    if transport in ("http", "streamable-http"):
        host = args.host or os.getenv("GEOSEO_HOST", "127.0.0.1")
        port = args.port or int(os.getenv("GEOSEO_PORT") or os.getenv("PORT") or 8000)
        server.run(transport="http", host=host, port=port)
    elif transport == "stdio":
        server.run()
    else:
        print(f"Unknown transport {transport!r}; use stdio or http.", file=sys.stderr)
        return 2
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    from .audit import on_page

    try:
        rep = on_page.audit(args.source, render=args.render)
    except on_page.RenderUnavailableError as e:
        print(str(e), file=sys.stderr)
        return 2
    except Exception as e:
        print(f"audit failed: {e}", file=sys.stderr)
        return 1
    _print_json(rep) if args.json else _print_audit(rep)
    return 0


def _cmd_audit_site(args: argparse.Namespace) -> int:
    from .tools.audit_tools import audit_folder

    rep = audit_folder(args.folder, pattern=args.pattern, limit=args.limit)
    if "error" in rep:
        print(rep["error"], file=sys.stderr)
        return 1
    if args.json:
        _print_json(rep)
        return 0
    print(f"{rep['folder']}: {rep['files_audited']} files, mean score {rep['mean_score']}")
    print("\nWorst pages:")
    for p in rep["worst_pages"]:
        print(f"  {p['score']:>3}  {p['path']}")
    print("\nMost common issues:")
    for f in rep["most_common_findings"][:10]:
        print(f"  {f['count']:>4}  {f['key']}")
    return 0


def _llms_txt_target(source: str) -> str:
    """Bare site roots (``https://example.com``) point at ``/llms.txt``."""
    from urllib.parse import urlparse

    if source.startswith(("http://", "https://")):
        u = urlparse(source)
        if u.path in ("", "/"):
            return source.rstrip("/") + "/llms.txt"
    return source


def _cmd_llms_txt(args: argparse.Namespace) -> int:
    from .audit import llms_txt

    target = _llms_txt_target(args.source)
    try:
        rep = llms_txt.validate(target)
    except Exception as e:
        print(f"Could not read {target}: {e}", file=sys.stderr)
        print(
            "No llms.txt yet? Draft one with: geoseo-mcp generate-llms-txt <folder> <site_url>",
            file=sys.stderr,
        )
        return 1
    if args.json:
        _print_json(rep)
        return 0
    issues = rep.get("issues") or []
    verdict = "valid" if rep.get("ok") else f"{len(issues)} issue(s)"
    print(f"{target}: {verdict}")
    print(f"  sections: {rep.get('section_count', 0)}, links: {rep.get('link_count', 0)}")
    for k in ("title", "summary"):
        if rep.get(k):
            print(f"  {k}: {rep[k]}")
    for i in issues:
        line = f"line {i['line']}: " if i.get("line") else ""
        print(f"  ✗ {line}{i.get('message', i)}")
    return 0 if rep.get("ok") else 1


def _cmd_generate_llms_txt(args: argparse.Namespace) -> int:
    from .audit import llms_txt

    rep = llms_txt.generate(
        folder=args.folder,
        site_url=args.site_url,
        site_title=args.title,
        site_summary=args.summary,
        pattern=args.pattern,
    )
    if "error" in rep:
        print(rep["error"], file=sys.stderr)
        return 1
    print(rep.get("content") or rep.get("markdown") or json.dumps(rep, indent=2))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    import asyncio

    from .server import build_server

    async def _call() -> Any:
        from fastmcp import Client

        async with Client(build_server()) as c:
            res = await c.call_tool("geoseo_status", {})
            return res.data if res.data is not None else res.structured_content

    status = asyncio.run(_call())
    if args.json:
        _print_json(status)
        return 0
    print(f"geoseo-mcp {status['version']}  toolsets: {', '.join(status['toolsets'])}")
    for name, e in status["engines"].items():
        print(f"  {'✓' if e['configured'] else '·'} {name:<22} {e['message']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="geoseo-mcp",
        description="SEO + GEO MCP server. Run with no arguments to start the stdio server.",
    )
    p.add_argument("--version", action="version", version=f"geoseo-mcp {__version__}")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("serve", help="Run the MCP server (default: stdio).")
    s.add_argument("--transport", choices=["stdio", "http", "streamable-http"], default=None)
    s.add_argument("--host", default=None, help="HTTP bind host (default 127.0.0.1).")
    s.add_argument("--port", type=int, default=None, help="HTTP port (default 8000).")
    s.set_defaults(func=_cmd_serve)

    a = sub.add_parser("audit", help="On-page SEO/GEO audit of a URL or HTML file. No keys.")
    a.add_argument("source")
    a.add_argument("--render", action="store_true", help="Render JavaScript (needs [render]).")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=_cmd_audit)

    a = sub.add_parser("audit-site", help="Audit every HTML file in a folder. No keys.")
    a.add_argument("folder")
    a.add_argument("--pattern", default="*.html")
    a.add_argument("--limit", type=int, default=200)
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=_cmd_audit_site)

    v = sub.add_parser("llms-txt", help="Validate a site's llms.txt (URL, site root, or file).")
    v.add_argument("source")
    v.add_argument("--json", action="store_true")
    v.set_defaults(func=_cmd_llms_txt)

    g = sub.add_parser("generate-llms-txt", help="Draft an llms.txt from a folder of HTML.")
    g.add_argument("folder")
    g.add_argument("site_url")
    g.add_argument("--title", default=None)
    g.add_argument("--summary", default=None)
    g.add_argument("--pattern", default="*.html")
    g.set_defaults(func=_cmd_generate_llms_txt)

    st = sub.add_parser("status", help="Show which engines are configured.")
    st.add_argument("--json", action="store_true")
    st.set_defaults(func=_cmd_status)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        args = argparse.Namespace(transport=None, host=None, port=None)
        return _cmd_serve(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
