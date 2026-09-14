"""Launch only the official CLI, with reading-specific, process-local restrictions."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
import shutil
import tomllib

DISABLED_FEATURES = (
    "apps", "plugins", "remote_plugin", "recommended_plugins", "hooks",
    "shell_tool", "unified_exec", "shell_snapshot", "code_mode", "code_mode_host",
    "browser_use", "browser_use_external", "browser_use_full_cdp_access", "computer_use",
    "multi_agent", "multi_agent_v2", "goals", "sleep_tool", "image_generation",
    "view_image", "memories", "skill_search", "skill_mcp_dependency_install",
    "tool_suggest", "workspace_dependencies", "in_app_local_automation",
    "unbounded_connection_retries",
)

def executable() -> str:
    path = shutil.which("codex.exe" if os.name == "nt" else "codex")
    if not path and os.name == "nt":
        # The desktop app may not add its bundled CLI to Explorer's PATH.
        install = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
        candidates = list(install.glob("*/codex.exe")) if install.is_dir() else []
        if candidates:
            path = str(max(candidates, key=lambda item: item.stat().st_mtime))
    if not path:
        raise ValueError("未找到官方 Codex，请先安装并用 ChatGPT 登录。")
    return path

def launch_arguments(runtime: Path) -> list[str]:
    runtime.mkdir(parents=True, exist_ok=True)
    values = {
        "forced_login_method": "chatgpt", "model_provider": "studycopilot-subscription",
        "model_providers.studycopilot-subscription.name": "OpenAI",
        "model_providers.studycopilot-subscription.requires_openai_auth": True,
        "model_providers.studycopilot-subscription.supports_websockets": False,
        "model_providers.studycopilot-subscription.request_max_retries": 0,
        "model_providers.studycopilot-subscription.stream_max_retries": 0,
        "sandbox_mode": "read-only", "approval_policy": "never",
        "approvals_reviewer": "user", "web_search": "disabled",
        "tools.view_image": False, "project_doc_max_bytes": 0,
        "history.persistence": "none", "hide_agent_reasoning": True,
        "sqlite_home": str(runtime / "state"), "log_dir": str(runtime / "logs"),
        "otel.log_user_prompt": False, "analytics.enabled": False,
    }
    values.update({f"features.{name}": False for name in DISABLED_FEATURES})
    # Only inspect server names to disable inherited MCP. Never access auth.json or return credentials.
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    config_path = home / "config.toml"
    if config_path.is_file():
        try:
            config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ValueError("无法核对 Codex 的工具配置，自动翻译暂未启动。") from None
        for name in config.get("mcp_servers", {}):
            if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
                raise ValueError('Codex MCP 名称无法安全覆盖，请使用独立官方配置。')
            values[f"mcp_servers.{name}.enabled"] = False
    args = ["app-server", "--stdio"]
    for key, value in values.items():
        args += ["-c", f"{key}={json.dumps(value, ensure_ascii=False)}"]
    return args

def child_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in list(environment):
        if name.upper() in {"OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL",
                "CODEX_APP_TOOLS_PIPE_PATH", "CODEX_THREAD_ID", "CODEX_INTERNAL_ORIGINATOR_OVERRIDE"}:
            del environment[name]
    return environment

def thread_parameters(runtime: Path, model: str, instructions: str) -> dict:
    return {
        "model": model, "modelProvider": "studycopilot-subscription", "cwd": str(runtime),
        "ephemeral": True, "baseInstructions": instructions,
        "approvalPolicy": "never", "approvalsReviewer": "user", "sandbox": "read-only",
        "environments": [], "selectedCapabilityRoots": [], "dynamicTools": [],
        "runtimeWorkspaceRoots": [str(runtime)],
    }
