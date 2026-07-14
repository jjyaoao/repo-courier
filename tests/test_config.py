from repo_courier.config import load_config


def test_environment_overrides_yaml(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "github:\n  limit: 5\nsummary:\n  model: yaml-model\n  api_key: yaml-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_MODEL", "env-model")
    monkeypatch.setenv("AI_API_KEY", "env-secret")
    monkeypatch.setenv("ACADEMIC_API_KEY", "academic-env-secret")
    monkeypatch.setenv("FEISHU_WEBHOOK", "https://example.invalid/hook")
    monkeypatch.setenv("REPO_COURIER_INTERESTS", "rust, cli, database")

    config = load_config(config_file)

    assert config.github.limit == 5
    assert config.summary.model == "env-model"
    assert config.summary.api_key == "env-secret"
    assert config.academic.api_key == "academic-env-secret"
    assert config.push.feishu_webhook.endswith("/hook")
    assert config.profile.interests == ["rust", "cli", "database"]


def test_academic_source_config(tmp_path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "academic:\n  enabled: true\n  base_url: https://www.dmxapi.cn/v1\n"
        "  api_key: yaml-secret\n  sources:\n    arxiv:\n      final_picks: 4\n",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.academic.enabled is True
    assert config.academic.base_url == "https://www.dmxapi.cn/v1"
    assert config.academic.model == ""
    assert config.academic.verify_ssl is True
    assert config.academic.api_key == ""
    assert config.academic.arxiv.final_picks == 4
    assert config.academic.arxiv.candidate_limit == 500
    assert config.academic.arxiv.page_size == 100


def test_academic_is_opt_in_by_default(tmp_path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("profile:\n  daily_picks: 3\n", encoding="utf-8")

    config = load_config(config_file)

    assert config.academic.enabled is False
    assert config.academic.verify_ssl is True


def test_legacy_lowercase_academic_key_is_still_supported(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("academic:\n  enabled: true\n", encoding="utf-8")
    monkeypatch.setenv("academic_api_key", "legacy-secret")

    assert load_config(config_file).academic.api_key == "legacy-secret"


def test_academic_numeric_strings_are_coerced_and_expressions_are_rejected(tmp_path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        'academic:\n  sources:\n    arxiv:\n      max_analysis_workers: "50"\n',
        encoding="utf-8",
    )
    assert load_config(config_file).academic.arxiv.max_analysis_workers == 50

    config_file.write_text(
        "academic:\n  sources:\n    arxiv:\n      max_analysis_workers: final_picks * 2\n",
        encoding="utf-8",
    )
    try:
        load_config(config_file)
    except ValueError as exc:
        assert "不能使用表达式" in str(exc)
    else:
        raise AssertionError("表达式形式的 max_analysis_workers 应被拒绝")


def test_technology_feed_sources_are_loaded_separately(tmp_path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "tech_blog:\n  enabled: true\n  final_picks: 5\n  sources:\n"
        "    - id: openai\n      name: OpenAI News\n      url: https://openai.com/news/rss.xml\n"
        "tech_news:\n  enabled: true\n  final_picks: 3\n  sources:\n"
        "    - id: apple\n      name: Apple Newsroom\n"
        "      url: https://www.apple.com/newsroom/rss-feed.rss\n",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.tech_blog.final_picks == 5
    assert config.tech_blog.sources[0].source_id == "openai"
    assert config.tech_news.final_picks == 3
    assert config.tech_news.sources[0].name == "Apple Newsroom"
