import json

import pytest

from entrypoint import (
    _DANGEROUS_ACTIONS,
    _FALLBACK_SAFE_ACTIONS,
    _extract_all_actions,
    inject_authorization_rules,
    load_mcp_server_configs,
    merge_mcp_servers,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mcp_configs():
    return {
        "rbac-mcp-server": {
            "provider_id": "rbac-mcp-provider",
            "url": "http://rbac:8000/mcp/",
            "headers": ["x-rh-identity"],
        },
        "notifications-mcp-server": {
            "provider_id": "notifications-mcp-provider",
            "url": "http://notifications:8000/mcp/",
        },
    }


@pytest.fixture
def base_run_config():
    return {"providers": {"tool_runtime": []}}


@pytest.fixture
def base_stack_config():
    return {"mcp_servers": []}


# ============================================================================
# load_mcp_server_configs TESTS
# ============================================================================

class TestLoadMcpServerConfigs:

    def test_loads_from_env_var(self, monkeypatch, mcp_configs):
        monkeypatch.setenv("CLOWDER_MCP_SERVER_CONFIGS", json.dumps(mcp_configs))
        result = load_mcp_server_configs()
        assert result == mcp_configs

    def test_loads_from_local_file(self, monkeypatch, tmp_path, mcp_configs):
        monkeypatch.delenv("CLOWDER_MCP_SERVER_CONFIGS", raising=False)
        config_file = tmp_path / "local_mcp_server_configs.json"
        config_file.write_text(json.dumps(mcp_configs))
        monkeypatch.setattr("entrypoint.TEMPLATE_DIR", str(tmp_path))

        result = load_mcp_server_configs()
        assert result == mcp_configs

    def test_returns_empty_when_no_config(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLOWDER_MCP_SERVER_CONFIGS", raising=False)
        monkeypatch.setattr("entrypoint.TEMPLATE_DIR", str(tmp_path))

        result = load_mcp_server_configs()
        assert result == {}

    def test_malformed_json_returns_empty(self, monkeypatch):
        monkeypatch.setenv("CLOWDER_MCP_SERVER_CONFIGS", "{invalid json!!}")
        result = load_mcp_server_configs()
        assert result == {}

    def test_env_var_takes_precedence_over_file(self, monkeypatch, tmp_path):
        env_config = {"env-server": {"provider_id": "env", "url": "http://env/mcp/"}}
        file_config = {"file-server": {"provider_id": "file", "url": "http://file/mcp/"}}

        monkeypatch.setenv("CLOWDER_MCP_SERVER_CONFIGS", json.dumps(env_config))
        config_file = tmp_path / "local_mcp_server_configs.json"
        config_file.write_text(json.dumps(file_config))
        monkeypatch.setattr("entrypoint.TEMPLATE_DIR", str(tmp_path))

        result = load_mcp_server_configs()
        assert "env-server" in result
        assert "file-server" not in result


# ============================================================================
# merge_mcp_servers TESTS
# ============================================================================

class TestMergeMcpServers:

    def test_merges_into_empty_configs(self, monkeypatch, mcp_configs, base_run_config, base_stack_config):
        monkeypatch.setenv("CLOWDER_MCP_SERVER_CONFIGS", json.dumps(mcp_configs))

        merge_mcp_servers(base_run_config, base_stack_config, clowder=None)

        assert len(base_stack_config["mcp_servers"]) == 2
        names = [s["name"] for s in base_stack_config["mcp_servers"]]
        assert "rbac-mcp-server" in names
        assert "notifications-mcp-server" in names

        providers = base_run_config["providers"]["tool_runtime"]
        assert len(providers) == 2
        assert all(p["provider_type"] == "remote::model-context-protocol" for p in providers)

    def test_preserves_headers(self, monkeypatch, mcp_configs, base_run_config, base_stack_config):
        monkeypatch.setenv("CLOWDER_MCP_SERVER_CONFIGS", json.dumps(mcp_configs))

        merge_mcp_servers(base_run_config, base_stack_config, clowder=None)

        rbac = next(s for s in base_stack_config["mcp_servers"] if s["name"] == "rbac-mcp-server")
        assert rbac["headers"] == ["x-rh-identity"]

        notif = next(s for s in base_stack_config["mcp_servers"] if s["name"] == "notifications-mcp-server")
        assert "headers" not in notif

    def test_deduplicates_by_name(self, monkeypatch, base_run_config, base_stack_config):
        base_stack_config["mcp_servers"] = [
            {"name": "existing-server", "provider_id": "old-provider", "url": "http://old/mcp/"}
        ]
        base_run_config["providers"]["tool_runtime"] = [
            {"provider_id": "new-provider", "provider_type": "remote::model-context-protocol", "config": {"url": "http://old/mcp/"}}
        ]

        new_configs = {
            "existing-server": {
                "provider_id": "new-provider",
                "url": "http://new/mcp/",
            }
        }
        monkeypatch.setenv("CLOWDER_MCP_SERVER_CONFIGS", json.dumps(new_configs))

        merge_mcp_servers(base_run_config, base_stack_config, clowder=None)

        assert len(base_stack_config["mcp_servers"]) == 1
        assert base_stack_config["mcp_servers"][0]["url"] == "http://new/mcp/"

    def test_no_configs_is_noop(self, monkeypatch, base_run_config, base_stack_config):
        monkeypatch.delenv("CLOWDER_MCP_SERVER_CONFIGS", raising=False)
        monkeypatch.setattr("entrypoint.TEMPLATE_DIR", "/nonexistent")

        original_run = json.dumps(base_run_config)
        original_stack = json.dumps(base_stack_config)

        merge_mcp_servers(base_run_config, base_stack_config, clowder=None)

        assert json.dumps(base_run_config) == original_run
        assert json.dumps(base_stack_config) == original_stack

    def test_creates_missing_keys(self, monkeypatch, mcp_configs):
        monkeypatch.setenv("CLOWDER_MCP_SERVER_CONFIGS", json.dumps(mcp_configs))
        run_config = {}
        stack_config = {}

        merge_mcp_servers(run_config, stack_config, clowder=None)

        assert "mcp_servers" in stack_config
        assert "tool_runtime" in run_config.get("providers", {})

    def test_skips_server_without_url_or_clowder(self, monkeypatch, base_run_config, base_stack_config):
        configs = {
            "bad-server": {
                "provider_id": "bad-provider",
            }
        }
        monkeypatch.setenv("CLOWDER_MCP_SERVER_CONFIGS", json.dumps(configs))

        merge_mcp_servers(base_run_config, base_stack_config, clowder=None)

        assert len(base_stack_config["mcp_servers"]) == 0
        assert len(base_run_config["providers"]["tool_runtime"]) == 0

    def test_clowder_url_resolution(self, monkeypatch, base_run_config, base_stack_config):
        configs = {
            "my-server": {
                "provider_id": "my-provider",
                "clowder_app": "my-app",
                "mcp_server_path": "/mcp/",
            }
        }
        monkeypatch.setenv("CLOWDER_MCP_SERVER_CONFIGS", json.dumps(configs))

        class FakeEndpoint:
            app = "my-app"
            name = "my-service"
            hostname = "resolved-host"
            port = 9999

        class FakeClowder:
            endpoints = [FakeEndpoint()]

        merge_mcp_servers(base_run_config, base_stack_config, clowder=FakeClowder())

        server = base_stack_config["mcp_servers"][0]
        assert server["url"] == "http://resolved-host:9999/mcp/"

        provider = base_run_config["providers"]["tool_runtime"][0]
        assert provider["config"]["url"] == "http://resolved-host:9999/mcp/"

    def test_authorization_preserved_after_clowder_config(self, monkeypatch, base_run_config):
        """Authorization access_rules must survive Clowder config application."""
        from entrypoint import apply_clowder_config

        stack_config = {
            "conversation_cache": {"type": "sqlite", "sqlite": {"db_path": "/tmp/test.db"}},
            "authorization": {
                "access_rules": [
                    {"role": "*", "actions": ["query", "list_conversations"]}
                ]
            },
        }

        class FakeDB:
            hostname = "db-host"
            port = 5432
            name = "testdb"
            username = "user"
            password = "pass"
            sslMode = "prefer"
            rdsCa = None

        class FakeClowder:
            database = FakeDB()

        apply_clowder_config(base_run_config, stack_config, FakeClowder())

        # Authorization section must be preserved after Clowder config application
        assert "authorization" in stack_config
        assert len(stack_config["authorization"]["access_rules"]) == 1
        assert stack_config["authorization"]["access_rules"][0]["role"] == "*"

    def test_clowder_no_matching_endpoint(self, monkeypatch, base_run_config, base_stack_config):
        configs = {
            "my-server": {
                "provider_id": "my-provider",
                "url": "http://fallback/mcp/",
                "clowder_app": "nonexistent-app",
            }
        }
        monkeypatch.setenv("CLOWDER_MCP_SERVER_CONFIGS", json.dumps(configs))

        class FakeEndpoint:
            app = "other-app"
            name = "other-service"
            hostname = "other-host"
            port = 1234

        class FakeClowder:
            endpoints = [FakeEndpoint()]

        merge_mcp_servers(base_run_config, base_stack_config, clowder=FakeClowder())

        server = base_stack_config["mcp_servers"][0]
        assert server["url"] == "http://fallback/mcp/"


# ============================================================================
# AUTHORIZATION CONFIG VALIDATION TESTS (RHCLOUD-48660)
# ============================================================================

# Actions required for the HCC AI Assistant to function.
_REQUIRED_ACTIONS = {
    "query",
    "responses",
    "streaming_query",
    "get_conversation",
    "list_conversations",
    "delete_conversation",
    "update_conversation",
    "feedback",
    "get_models",
    "get_tools",
    "info",
}


class TestExtractAllActions:
    """Validate that _extract_all_actions correctly parses the Action enum."""

    def test_extracts_actions_from_lightspeed_source(self):
        """Should find actions when LightSpeed Core source is available."""
        actions = _extract_all_actions()
        if actions is None:
            pytest.skip("LightSpeed Core source not available in this environment")
        assert isinstance(actions, set)
        assert len(actions) > 0
        # Must contain well-known actions
        assert "query" in actions
        assert "list_conversations" in actions

    def test_returns_none_for_missing_source(self, tmp_path):
        """Should return None when source paths don't exist."""
        result = _extract_all_actions(src_paths=[str(tmp_path / "nonexistent")])
        assert result is None

    def test_returns_none_for_invalid_syntax(self, tmp_path):
        """Should return None when source has syntax errors."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "config.py").write_text("this is not valid python {{{{")
        result = _extract_all_actions(src_paths=[str(tmp_path)])
        assert result is None

    def test_parses_custom_action_enum(self, tmp_path):
        """Should correctly parse string values from an Action enum."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "config.py").write_text(
            'class Action:\n'
            '    ADMIN = "admin"\n'
            '    QUERY = "query"\n'
            '    LIST_OTHER = "list_other_conversations"\n'
        )
        result = _extract_all_actions(src_paths=[str(tmp_path)])
        assert result == {"admin", "query", "list_other_conversations"}


class TestInjectAuthorizationRules:
    """Validate inject_authorization_rules correctly builds access_rules,
    excluding dangerous cross-user actions (RHCLOUD-48660).
    """

    def test_injects_rules_with_wildcard_role(self):
        """Should inject access_rules with role '*'."""
        config = {"authorization": {}}
        inject_authorization_rules(config)
        rules = config["authorization"]["access_rules"]
        assert len(rules) == 1
        assert rules[0]["role"] == "*"
        assert len(rules[0]["actions"]) > 0

    def test_excludes_dangerous_actions(self):
        """No dangerous action must appear in the injected rules."""
        config = {"authorization": {}}
        inject_authorization_rules(config)
        granted = set(config["authorization"]["access_rules"][0]["actions"])
        dangerous = granted & _DANGEROUS_ACTIONS
        assert not dangerous, (
            f"Injected rules must not include dangerous actions: {dangerous}"
        )

    def test_includes_required_actions(self):
        """All actions required for the chatbot must be present."""
        config = {"authorization": {}}
        inject_authorization_rules(config)
        granted = set(config["authorization"]["access_rules"][0]["actions"])
        missing = _REQUIRED_ACTIONS - granted
        assert not missing, f"Injected rules are missing required actions: {missing}"

    def test_dynamic_extraction_includes_all_safe_actions(self, tmp_path):
        """When source is available, all non-dangerous actions are included."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "config.py").write_text(
            'class Action:\n'
            '    ADMIN = "admin"\n'
            '    QUERY = "query"\n'
            '    LIST_OTHER = "list_other_conversations"\n'
            '    FEEDBACK = "feedback"\n'
            '    NEW_FEATURE = "new_feature"\n'
        )
        config = {"authorization": {}}
        inject_authorization_rules(config, src_paths=[str(tmp_path)])
        granted = set(config["authorization"]["access_rules"][0]["actions"])
        assert granted == {"query", "feedback", "new_feature"}

    def test_fallback_when_source_unavailable(self, tmp_path):
        """Should use static fallback when source is not found."""
        config = {"authorization": {}}
        inject_authorization_rules(config, src_paths=[str(tmp_path / "nope")])
        granted = config["authorization"]["access_rules"][0]["actions"]
        assert granted == _FALLBACK_SAFE_ACTIONS

    def test_fallback_excludes_dangerous_actions(self):
        """Static fallback must not contain any dangerous actions."""
        dangerous_in_fallback = set(_FALLBACK_SAFE_ACTIONS) & _DANGEROUS_ACTIONS
        assert not dangerous_in_fallback, (
            f"_FALLBACK_SAFE_ACTIONS must not include: {dangerous_in_fallback}"
        )

    def test_actions_are_sorted(self):
        """Injected actions should be alphabetically sorted for readability."""
        config = {"authorization": {}}
        inject_authorization_rules(config)
        actions = config["authorization"]["access_rules"][0]["actions"]
        assert actions == sorted(actions)

    def test_overwrites_existing_authorization(self):
        """Should replace any pre-existing authorization config."""
        config = {"authorization": {"access_rules": [{"role": "old", "actions": ["admin"]}]}}
        inject_authorization_rules(config)
        rules = config["authorization"]["access_rules"]
        assert len(rules) == 1
        assert rules[0]["role"] == "*"
        assert "admin" not in rules[0]["actions"]
