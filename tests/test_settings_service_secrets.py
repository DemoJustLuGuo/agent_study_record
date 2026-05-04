import yaml

from services import settings_service


def test_save_connection_settings_does_not_persist_raw_api_key(
    tmp_path, monkeypatch
) -> None:
    config_path = tmp_path / "agent.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "openai_base_url": "https://old.example/v1",
                "OPENAI_API_KEY": "SILICONFLOW_API_KEY",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_service, "AGENT_CONFIG_PATH", str(config_path))

    result = settings_service.save_connection_settings(
        "https://api.example/v1",
        "sk-test-secret",
    )

    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved["openai_base_url"] == "https://api.example/v1"
    assert saved["OPENAI_API_KEY"] == "SILICONFLOW_API_KEY"
    assert "sk-test-secret" not in config_path.read_text(encoding="utf-8")
    assert "未把真实 API Key 写入配置文件" in result
