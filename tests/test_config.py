from repo_courier.config import load_config


def test_environment_overrides_yaml(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "github:\n  limit: 5\nsummary:\n  model: yaml-model\n", encoding="utf-8"
    )
    monkeypatch.setenv("AI_MODEL", "env-model")
    monkeypatch.setenv("FEISHU_WEBHOOK", "https://example.invalid/hook")
    monkeypatch.setenv("REPO_COURIER_INTERESTS", "rust, cli, database")

    config = load_config(config_file)

    assert config.github.limit == 5
    assert config.summary.model == "env-model"
    assert config.push.feishu_webhook.endswith("/hook")
    assert config.profile.interests == ["rust", "cli", "database"]
