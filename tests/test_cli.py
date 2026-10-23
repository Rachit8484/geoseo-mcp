"""CLI subcommands (keyless paths only, no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from geoseo_mcp import __main__ as cli
from geoseo_mcp import __version__

from .test_audit import SAMPLE_HTML


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_bare_command_starts_stdio_server(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class FakeServer:
        def run(self, **kw):
            calls.append(kw)

    monkeypatch.setattr("geoseo_mcp.server.build_server", lambda: FakeServer())
    assert cli.main([]) == 0
    assert calls == [{}]


def test_serve_http(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class FakeServer:
        def run(self, **kw):
            calls.append(kw)

    monkeypatch.setattr("geoseo_mcp.server.build_server", lambda: FakeServer())
    assert cli.main(["serve", "--transport", "http", "--port", "9123"]) == 0
    assert calls == [{"transport": "http", "host": "127.0.0.1", "port": 9123}]


def test_audit_file_text_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = tmp_path / "page.html"
    f.write_text(SAMPLE_HTML)
    assert cli.main(["audit", str(f)]) == 0
    out = capsys.readouterr().out
    assert "score:" in out and "/100" in out
    assert cli.main(["audit", str(f), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["title"].startswith("How to Quit Drinking")


def test_audit_missing_file(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["audit", "/nope/missing.html"]) == 1
    assert "audit failed" in capsys.readouterr().err


def test_audit_site(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "a.html").write_text(SAMPLE_HTML)
    (tmp_path / "b.html").write_text("<html><body><p>hi</p></body></html>")
    assert cli.main(["audit-site", str(tmp_path)]) == 0
    assert "2 files" in capsys.readouterr().out


def test_llms_txt_validate_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = tmp_path / "llms.txt"
    f.write_text("# Acme\n\n> CRM for startups.\n\n## Docs\n\n- [Start](https://acme.com/start)\n")
    assert cli.main(["llms-txt", str(f)]) == 0
    assert "valid" in capsys.readouterr().out
    f.write_text("no heading\n")
    assert cli.main(["llms-txt", str(f)]) == 1


def test_llms_txt_site_root_maps_to_file() -> None:
    assert cli._llms_txt_target("https://acme.com") == "https://acme.com/llms.txt"
    assert cli._llms_txt_target("https://acme.com/") == "https://acme.com/llms.txt"
    assert cli._llms_txt_target("https://acme.com/x/llms.txt") == "https://acme.com/x/llms.txt"


def test_status_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["status", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["version"] == __version__
    assert data["engines"]["on_page_audit"]["configured"] is True
    assert data["engines"]["openai"]["configured"] is False
