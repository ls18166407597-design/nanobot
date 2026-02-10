from nanobot.config.loader import _migrate_config, convert_keys


def test_migrate_exec_restrict_to_workspace():
    data = {"tools": {"exec": {"restrictToWorkspace": True}}}
    migrated = _migrate_config(data)
    assert migrated["tools"]["restrictToWorkspace"] is True
    assert "restrictToWorkspace" not in migrated["tools"]["exec"]


def test_convert_keys_camel_to_snake():
    data = {"tools": {"web": {"proxyUrl": "http://x"}}}
    converted = convert_keys(data)
    assert converted["tools"]["web"]["proxy_url"] == "http://x"
