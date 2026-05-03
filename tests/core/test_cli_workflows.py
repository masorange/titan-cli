import json

from typer.testing import CliRunner

from titan_cli.application.models.responses import StartWorkflowResponse
from titan_cli.application.models.responses import KnownPluginSummary
from titan_cli.application.models.responses import PluginMutationResult
from titan_cli.application.models.responses import PluginSourcePreview
from titan_cli.application.models.responses import PluginInspection
from titan_cli.application.models.responses import ProjectInspection
from titan_cli.application.models.responses import WorkflowDetail
from titan_cli.application.models.responses import WorkflowStepSummary
from titan_cli.application.models.responses import WorkflowSummary
from titan_cli.cli import app


def test_headless_workflows_list_outputs_json(monkeypatch):
    class StubWorkflowService:
        def list_workflows(self, project_path=None):
            assert project_path == "/tmp/demo"
            return [
                WorkflowSummary(
                    name="demo",
                    description="Demo workflow",
                    source="project",
                )
            ]

    monkeypatch.setattr(
        "titan_cli.cli._workflow_service",
        lambda: StubWorkflowService(),
    )

    result = CliRunner().invoke(
        app,
        ["headless", "workflows", "list", "--project-path", "/tmp/demo", "--json"],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "items": [
            {
                "name": "demo",
                "description": "Demo workflow",
                "source": "project",
            }
        ]
    }


def test_headless_runs_start_passes_headless_request_and_outputs_json(monkeypatch):
    captured_request = None

    class StubWorkflowService:
        def start_workflow(self, request):
            nonlocal captured_request
            captured_request = request
            return StartWorkflowResponse(
                run_id="run-1",
                status="completed",
                events=[],
            )

    monkeypatch.setattr(
        "titan_cli.cli._workflow_service",
        lambda: StubWorkflowService(),
    )

    result = CliRunner().invoke(
        app,
        [
            "headless",
            "runs",
            "start",
            "demo",
            "--project-path",
            "/tmp/demo",
            "--params-json",
            '{"issue": "ABC-1"}',
            "--prompt-responses-json",
            '["yes"]',
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert captured_request is not None
    assert captured_request.workflow_name == "demo"
    assert captured_request.project_path == "/tmp/demo"
    assert captured_request.params == {"issue": "ABC-1"}
    assert captured_request.prompt_responses == ["yes"]
    assert captured_request.interaction_mode == "headless"
    assert json.loads(result.stdout) == {
        "run_id": "run-1",
        "status": "completed",
        "events": [],
        "pending_prompt": None,
    }


def test_headless_workflows_describe_outputs_resolved_steps(monkeypatch):
    class StubWorkflowService:
        def describe_workflow(self, workflow_name, project_path=None):
            assert workflow_name == "demo"
            assert project_path == "/tmp/demo"
            return WorkflowDetail(
                name="demo",
                description="Demo workflow",
                source="project",
                params={"branch": "main"},
                steps=[
                    WorkflowStepSummary(
                        id="git_status",
                        name="Git Status",
                        plugin="git",
                        step="status",
                    )
                ],
            )

    monkeypatch.setattr(
        "titan_cli.cli._workflow_service",
        lambda: StubWorkflowService(),
    )

    result = CliRunner().invoke(
        app,
        [
            "headless",
            "workflows",
            "describe",
            "demo",
            "--project-path",
            "/tmp/demo",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "name": "demo",
        "description": "Demo workflow",
        "source": "project",
        "params": {"branch": "main"},
        "steps": [
            {
                "id": "git_status",
                "name": "Git Status",
                "plugin": "git",
                "step": "status",
                "command": None,
                "workflow": None,
                "hook": None,
                "requires": [],
                "on_error": "fail",
                "params": {},
            }
        ],
    }


def test_headless_workflows_list_keeps_stdout_json_when_runtime_prints(monkeypatch):
    class StubWorkflowService:
        def list_workflows(self, project_path=None):
            print("plugin noise")
            return [WorkflowSummary(name="demo")]

    monkeypatch.setattr(
        "titan_cli.cli._workflow_service",
        lambda: StubWorkflowService(),
    )

    result = CliRunner().invoke(
        app,
        ["headless", "workflows", "list", "--json"],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "items": [
            {
                "name": "demo",
                "description": None,
                "source": None,
            }
        ]
    }
    assert "plugin noise" in result.stderr


def test_headless_project_inspect_outputs_project_snapshot(monkeypatch):
    class StubProjectInspectionService:
        def inspect_project(self, project_path=None):
            assert project_path == "/tmp/demo"
            return ProjectInspection(
                name="demo",
                type="ios",
                path="/tmp/demo",
                config_path="/tmp/demo/.titan/config.toml",
                configured=True,
                plugins=[
                    PluginInspection(
                        name="git",
                        enabled=True,
                        installed=True,
                        loaded=True,
                        available=True,
                        version="1.2.3",
                        workflows=["commit-ai"],
                        steps=["status"],
                    )
                ],
                workflows=[WorkflowSummary(name="commit-ai", source="project")],
            )

    monkeypatch.setattr(
        "titan_cli.cli._project_inspection_service",
        lambda: StubProjectInspectionService(),
    )

    result = CliRunner().invoke(
        app,
        ["headless", "project", "inspect", "--project-path", "/tmp/demo", "--json"],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "name": "demo",
        "type": "ios",
        "path": "/tmp/demo",
        "config_path": "/tmp/demo/.titan/config.toml",
        "configured": True,
        "plugins": [
            {
                "name": "git",
                "enabled": True,
                "installed": True,
                "loaded": True,
                "available": True,
                "version": "1.2.3",
                "description": None,
                "source": {},
                "workflows": ["commit-ai"],
                "steps": ["status"],
                "error": None,
            }
        ],
        "workflows": [
            {
                "name": "commit-ai",
                "description": None,
                "source": "project",
            }
        ],
        "warnings": [],
        "sync_events": [],
        "diagnostics": [],
    }


def test_headless_ai_list_outputs_connections(monkeypatch):
    class StubTitanConfig:
        def get_ai_connections_config(self):
            return {
                "default_connection": "work",
                "connections": {
                    "work": {
                        "name": "Work Gateway",
                        "connection_type": "gateway",
                        "gateway_backend": "openai_compatible",
                        "base_url": "https://llm.example.com",
                        "default_model": "gemini-2.5-pro",
                        "max_tokens": 4096,
                        "temperature": 0.7,
                    }
                },
            }

    monkeypatch.setattr("titan_cli.cli._ai_config", lambda: StubTitanConfig())

    result = CliRunner().invoke(app, ["headless", "ai", "list", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "default_connection": "work",
        "connections": [
            {
                "id": "work",
                "name": "Work Gateway",
                "connection_type": "gateway",
                "gateway_backend": "openai_compatible",
                "base_url": "https://llm.example.com",
                "default_model": "gemini-2.5-pro",
                "max_tokens": 4096,
                "temperature": 0.7,
                "is_default": True,
            }
        ],
    }


def test_headless_ai_upsert_saves_connection_and_secret(monkeypatch):
    saved_connection = None
    saved_secret = None

    class StubSecrets:
        def set(self, key, value, scope):
            nonlocal saved_secret
            saved_secret = (key, value, scope)

    class StubTitanConfig:
        secrets = StubSecrets()

        def __init__(self):
            self.ai_config = {"default_connection": None, "connections": {}}

        def get_ai_connections_config(self):
            return self.ai_config

        def upsert_ai_connection(self, connection_id, connection_data):
            nonlocal saved_connection
            saved_connection = (connection_id, connection_data)
            self.ai_config["connections"][connection_id] = connection_data
            self.ai_config["default_connection"] = connection_id

    stub_config = StubTitanConfig()
    monkeypatch.setattr("titan_cli.cli._ai_config", lambda: stub_config)

    result = CliRunner().invoke(
        app,
        [
            "headless",
            "ai",
            "upsert",
            "personal",
            "--connection-json",
            json.dumps(
                {
                    "name": "Personal Claude",
                    "connection_type": "direct_provider",
                    "provider": "anthropic",
                    "default_model": "claude-sonnet-4-5",
                }
            ),
            "--api-key-env",
            "TITAN_TEST_AI_API_KEY",
            "--json",
        ],
        env={"TITAN_TEST_AI_API_KEY": "secret-value"},
    )

    assert result.exit_code == 0
    assert saved_connection == (
        "personal",
        {
            "name": "Personal Claude",
            "connection_type": "direct_provider",
            "provider": "anthropic",
            "default_model": "claude-sonnet-4-5",
        },
    )
    assert saved_secret == ("personal_api_key", "secret-value", "user")
    assert json.loads(result.stdout)["default_connection"] == "personal"


def test_headless_ai_models_outputs_direct_provider_suggestions(monkeypatch):
    from titan_cli.core.models import AIConfig, AIConnectionConfig

    class StubTitanConfig:
        secrets = None
        config = type(
            "Config",
            (),
            {
                "ai": AIConfig(
                    default_connection="personal",
                    connections={
                        "personal": AIConnectionConfig(
                            name="Personal Google",
                            connection_type="direct_provider",
                            provider="gemini",
                            default_model="gemini-1.5-flash",
                        )
                    },
                )
            },
        )()

    monkeypatch.setattr("titan_cli.cli._ai_config", lambda: StubTitanConfig())

    result = CliRunner().invoke(
        app,
        ["headless", "ai", "models", "personal", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["connection_id"] == "personal"
    assert payload["default_model"] == "gemini-1.5-flash"
    assert {"id": "gemini-2.5-pro", "name": "gemini-2.5-pro", "owned_by": "gemini", "source": "suggested"} in payload["items"]


def test_headless_plugins_available_outputs_curated_plugins(monkeypatch):
    class StubPluginService:
        def list_available_plugins(self):
            return [
                KnownPluginSummary(
                    name="ragnarok",
                    description="Ragnarok workflows",
                    package_name="titan-plugin-ragnarok",
                    source="community",
                    repo_url="https://github.com/masmovil/ragnarok-titan-cli-workflows",
                    recommended_ref="0.7.0",
                )
            ]

    monkeypatch.setattr(
        "titan_cli.cli._plugin_service",
        lambda: StubPluginService(),
    )

    result = CliRunner().invoke(app, ["headless", "plugins", "available", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "items": [
            {
                "name": "ragnarok",
                "description": "Ragnarok workflows",
                "package_name": "titan-plugin-ragnarok",
                "source": "community",
                "repo_url": "https://github.com/masmovil/ragnarok-titan-cli-workflows",
                "recommended_ref": "0.7.0",
                "dependencies": [],
            }
        ]
    }


def test_headless_plugins_configure_passes_config_payload(monkeypatch):
    captured = None

    class StubPluginService:
        def configure_plugin(self, plugin_name, config_values):
            nonlocal captured
            captured = (plugin_name, config_values)
            return PluginMutationResult(
                plugin_name=plugin_name,
                changed=True,
                message="configured",
                config=config_values,
            )

    monkeypatch.setattr(
        "titan_cli.cli._plugin_service",
        lambda: StubPluginService(),
    )

    result = CliRunner().invoke(
        app,
        [
            "headless",
            "plugins",
            "configure",
            "ragnarok",
            "--config-json",
            '{"platform": "ios"}',
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert captured == ("ragnarok", {"platform": "ios"})
    assert json.loads(result.stdout) == {
        "plugin_name": "ragnarok",
        "changed": True,
        "message": "configured",
        "source": {},
        "config": {"platform": "ios"},
    }


def test_headless_plugins_preview_source_outputs_plugin_metadata(monkeypatch):
    captured = None

    class StubPluginService:
        def preview_stable_source(self, raw_url):
            nonlocal captured
            captured = raw_url
            return PluginSourcePreview(
                repo_url="https://github.com/example/titan-plugin-demo",
                requested_ref="v1.0.0",
                resolved_commit="a" * 40,
                package_name="titan-plugin-demo",
                version="1.0.0",
                description="Demo plugin",
                authors=["Titan Team"],
                titan_entry_points={"demo": "demo.plugin:DemoPlugin"},
                python_dependencies=["titan-cli"],
            )

    monkeypatch.setattr(
        "titan_cli.cli._plugin_service",
        lambda: StubPluginService(),
    )

    source = "https://github.com/example/titan-plugin-demo@v1.0.0"
    result = CliRunner().invoke(
        app,
        ["headless", "plugins", "preview-source", "--source", source, "--json"],
    )

    assert result.exit_code == 0
    assert captured == source
    assert json.loads(result.stdout) == {
        "repo_url": "https://github.com/example/titan-plugin-demo",
        "requested_ref": "v1.0.0",
        "resolved_commit": "a" * 40,
        "package_name": "titan-plugin-demo",
        "version": "1.0.0",
        "description": "Demo plugin",
        "authors": ["Titan Team"],
        "titan_entry_points": {"demo": "demo.plugin:DemoPlugin"},
        "python_dependencies": ["titan-cli"],
        "warnings": [],
    }


def test_headless_plugins_install_outputs_mutation(monkeypatch):
    captured = None

    class StubPluginService:
        def install_stable_source(self, raw_url):
            nonlocal captured
            captured = raw_url
            return PluginMutationResult(
                plugin_name="demo",
                changed=True,
                message="Plugin 'demo' installed.",
                source={
                    "channel": "stable",
                    "repo_url": "https://github.com/example/titan-plugin-demo",
                    "requested_ref": "v1.0.0",
                    "resolved_commit": "a" * 40,
                },
            )

    monkeypatch.setattr(
        "titan_cli.cli._plugin_service",
        lambda: StubPluginService(),
    )

    source = "https://github.com/example/titan-plugin-demo@v1.0.0"
    result = CliRunner().invoke(
        app,
        ["headless", "plugins", "install", "--source", source, "--json"],
    )

    assert result.exit_code == 0
    assert captured == source
    assert json.loads(result.stdout) == {
        "plugin_name": "demo",
        "changed": True,
        "message": "Plugin 'demo' installed.",
        "source": {
            "channel": "stable",
            "repo_url": "https://github.com/example/titan-plugin-demo",
            "requested_ref": "v1.0.0",
            "resolved_commit": "a" * 40,
        },
        "config": {},
    }


def test_headless_plugins_set_dev_source_outputs_mutation(monkeypatch):
    captured = None

    class StubPluginService:
        def set_dev_source(self, plugin_name, path):
            nonlocal captured
            captured = (plugin_name, path)
            return PluginMutationResult(
                plugin_name=plugin_name,
                changed=True,
                message="dev source configured",
                source={"channel": "dev_local", "path": path},
            )

    monkeypatch.setattr(
        "titan_cli.cli._plugin_service",
        lambda: StubPluginService(),
    )

    result = CliRunner().invoke(
        app,
        [
            "headless",
            "plugins",
            "set-dev-source",
            "ragnarok",
            "--path",
            "/tmp/ragnarok",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert captured == ("ragnarok", "/tmp/ragnarok")
    assert json.loads(result.stdout) == {
        "plugin_name": "ragnarok",
        "changed": True,
        "message": "dev source configured",
        "source": {"channel": "dev_local", "path": "/tmp/ragnarok"},
        "config": {},
    }


def test_headless_runs_start_rejects_non_object_params_json(monkeypatch):
    result = CliRunner().invoke(
        app,
        ["headless", "runs", "start", "demo", "--params-json", '["bad"]', "--json"],
    )

    assert result.exit_code != 0
    assert "--params-json must be a JSON object" in result.output
