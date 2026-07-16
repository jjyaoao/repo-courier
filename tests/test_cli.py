from types import SimpleNamespace

import pytest

from repo_courier import cli
from repo_courier.cli import build_parser, parse_channels
from repo_courier.config import AppConfig, RssChannelConfig, RssConfig


def _config() -> AppConfig:
    channels = {
        name: RssChannelConfig(
            name, name.title(), f"repo_courier.prompts.{name}:build_messages"
        )
        for name in ("news", "blogs", "academic", "products", "security")
    }
    return AppConfig(rss=RssConfig(channels=channels))


def test_parse_channels_supports_defaults_selection_and_all() -> None:
    config = _config()
    assert parse_channels(None, config) is None
    assert parse_channels("news,academic", config) == ["news", "academic"]
    assert parse_channels("github,academic", config) == ["github", "academic"]
    assert parse_channels("all", config) == ["github", *config.rss.channels]


@pytest.mark.parametrize("raw", ["", "news,", "news,news", "all,news", "unknown"])
def test_parse_channels_rejects_invalid_values(raw) -> None:
    with pytest.raises(ValueError):
        parse_channels(raw, _config())


def test_parser_uses_channels_without_legacy_academic_only() -> None:
    args = build_parser().parse_args(["--channels", "news", "--dry-run"])
    assert args.channels == "news"
    assert "academic_only" not in vars(args)


def test_cli_prints_all_report_paths(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "load_config", lambda path: _config())
    monkeypatch.setattr(
        cli,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            rss_channels={},
            scanned_count=0,
            ran_github=False,
            report_paths={
                "markdown": "reports/day/daily.md",
                "html": "reports/day/daily.html",
                "json": "reports/day/daily.json",
            },
        ),
    )

    assert cli.main(["--channels", "academic", "--dry-run"]) == 0

    output = capsys.readouterr().out
    assert "Markdown：reports/day/daily.md" in output
    assert "HTML：reports/day/daily.html" in output
    assert "JSON：reports/day/daily.json" in output
