# titan_cli/utils/cli_configs.py
"""
Centralized registry for external CLI tool configurations.
"""

CLI_REGISTRY = {
    "claude": {
        "display_name": "Claude CLI",
        "install_instructions": "Install: npm install -g @anthropic/claude-code",
        "prompt_flag": None,
        "model_flag": "--model"
    },
    "gemini": {
        "display_name": "Gemini CLI",
        "install_instructions": None,
        "prompt_flag": "-i",
        "model_flag": "-m"
    },
    "codex": {
        "display_name": "Codex CLI",
        "install_instructions": "Install: pip install openai[cli]",
        "prompt_flag": None,
        "model_flag": "-m"
    },
    "opencode": {
        "display_name": "OpenCode",
        "install_instructions": "Install: npm install -g opencode-ai",
        "prompt_flag": "--prompt",
        "model_flag": "-m"
    },
    "agy": {
        "display_name": "Antigravity CLI",
        "install_instructions": None,
        "prompt_flag": "-i",
        "model_flag": "--model"
    },
    "grok": {
        "display_name": "Grok Build CLI",
        "install_instructions": "Install: curl -fsSL https://x.ai/cli/install.sh | bash",
        # A positional prompt opens the TUI with that first turn; -p would run
        # headless instead, which is not what the interactive launcher wants.
        "prompt_flag": None,
        "model_flag": "-m"
    }
}
