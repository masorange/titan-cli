# titan_cli/utils/cli_launcher.py
import subprocess
import sys
import shutil
from typing import Optional

class CLILauncher:
    """Generic CLI launcher."""

    def __init__(self, cli_name: str, install_instructions: Optional[str] = None, prompt_flag: Optional[str] = None):
        self.cli_name = cli_name
        self.install_instructions = install_instructions
        self.prompt_flag = prompt_flag

    def is_available(self) -> bool:
        """Check if the CLI tool is installed."""
        return shutil.which(self.cli_name) is not None

    def launch(self, prompt: Optional[str] = None, cwd: Optional[str] = None) -> int:
        """
        Launch the CLI tool in the current terminal.

        Args:
            prompt: Optional initial prompt to send to the CLI
            cwd: Working directory (default: current)

        Returns:
            Exit code from the CLI tool
        """
        cmd = [self.cli_name]

        if prompt:
            if self.prompt_flag:
                cmd.extend([self.prompt_flag, prompt])
            else:
                cmd.append(prompt)

        result = subprocess.run(
            cmd,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            cwd=cwd
        )

        return result.returncode
