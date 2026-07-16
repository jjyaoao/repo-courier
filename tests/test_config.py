import pytest

from repo_courier.config import load_config

CONFIG_PATH = __file__.replace("tests/test_config.py", "config/config.yaml")


def test_default_config_loads_five_unique_rss_channels() -> None:
    config = load_config(CONFIG_PATH)

    assert config.github.enabled is True
    assert list(config.rss.channels) == ["news", "blogs", "academic", "products", "security"]
    assert all(channel.enabled for channel in config.rss.channels.values())
    assert config.rss.defaults.max_items_per_source > 0
    assert config.rss.defaults.llm_candidates > 0
    assert 0 < config.rss.defaults.top_k <= config.rss.defaults.llm_candidates
    assert config.rss.defaults.max_input_tokens > 0
    urls = [
        source.url
        for channel in config.rss.channels.values()
        for source in channel.sources
    ]
    assert len(urls) == 17
    assert len(urls) == len(set(urls))
    assert config.rss.channels["academic"].sources[0].url.endswith("cs.AI+cs.CL+cs.CV+cs.LG")
    assert config.report.product_display_names["openai-codex"] == "OpenAI Codex"


def test_environment_overrides_yaml(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "repo_llm:\n  model: yaml-model\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("REPO_LLM_MODEL", "shared-model")
    monkeypatch.setenv("REPO_LLM_API_KEY", "shared-secret")
    monkeypatch.setenv("REPO_LLM_BASE_URL", "https://example.com/v1/chat/completions")

    config = load_config(config_file)

    assert config.repo_llm.model == "shared-model"
    assert config.repo_llm.api_key == "shared-secret"
    assert config.repo_llm.base_url == "https://example.com/v1/chat/completions"


def test_duplicate_rss_urls_keep_first_occurrence(tmp_path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
rss:
  channels:
    one:
      title: One
      prompt: repo_courier.prompts.news:build_messages
      sources:
        - {id: first, name: First, url: 'https://example.com/feed/'}
    two:
      title: Two
      prompt: repo_courier.prompts.blogs:build_messages
      sources:
        - {id: duplicate, name: Duplicate, url: 'https://EXAMPLE.com/feed'}
        - {id: second, name: Second, url: 'https://example.com/other'}
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert [source.source_id for source in config.rss.channels["one"].sources] == ["first"]
    assert [source.source_id for source in config.rss.channels["two"].sources] == ["second"]


def test_invalid_prompt_and_numeric_limits_fail_fast(tmp_path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
rss:
  defaults: {top_k: nope}
  channels:
    news:
      title: News
      prompt: missing.module:builder
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_config(config_file)

    config_file.write_text(
        """
rss:
  channels:
    news:
      title: News
      enabled: true
      prompt: missing.module:builder
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="无法加载 Prompt"):
        load_config(config_file)


def test_disabled_channel_does_not_import_prompt(tmp_path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
rss:
  channels:
    future:
      title: Future
      enabled: false
      prompt: not.installed.yet:build_messages
""",
        encoding="utf-8",
    )

    assert load_config(config_file).rss.channels["future"].enabled is False
