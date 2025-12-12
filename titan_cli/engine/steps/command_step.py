import os
from pathlib import Path
from subprocess import Popen, PIPE
import re
from typing import Any
from titan_cli.core.workflows.models import WorkflowStepModel
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Success, Error, WorkflowResult

def _resolve_parameters_in_string(text: str, ctx: WorkflowContext) -> str:
    """
    Substitutes ${placeholder} in a string using values from ctx.data.
    """
    def replace_placeholder(match):
        placeholder = match.group(1)
        if placeholder in ctx.data:
            return str(ctx.data[placeholder])
        return match.group(0)

    return re.sub(r'\$\{(\w+)\}', replace_placeholder, text)


def execute_command_step(step: WorkflowStepModel, ctx: WorkflowContext) -> WorkflowResult:
    """
    Executes a shell command defined in a workflow step.
    """
    command_template = step.command
    if not command_template:
        return Error("Command step is missing the 'command' attribute.")

    # Resolve parameters in the command string
    command = _resolve_parameters_in_string(command_template, ctx)

    if ctx.ui:
        ctx.ui.text.info(f"Executing command: [primary]{command}[/primary]")

    try:
        use_venv = step.params.get("use_venv", False)
        process_env = os.environ.copy()

        if use_venv:
            # Get the poetry virtualenv path
            if ctx.ui:
                ctx.ui.text.body("Activating poetry virtual environment for step...", style="dim")
            
            env_proc = Popen(["poetry", "env", "info", "-p"], stdout=PIPE, stderr=PIPE, text=True, cwd=ctx.get("cwd"))
            venv_path, err = env_proc.communicate()
            
            if env_proc.returncode == 0 and venv_path.strip():
                bin_path = Path(venv_path.strip()) / "bin"
                process_env["PATH"] = f"{bin_path}:{process_env['PATH']}"
            else:
                return Error(f"Could not determine poetry virtual environment. Error: {err}")

        process = Popen(command, shell=True, stdout=PIPE, stderr=PIPE, text=True, cwd=ctx.get("cwd"), env=process_env)

        stdout_lines = []
        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                print(line, end='') # Stream output to the console in real-time
                stdout_lines.append(line)
        
        process.wait()

        if process.returncode != 0:
            stderr_output = ""
            if process.stderr:
                stderr_output = process.stderr.read()
            
            error_message = f"Command failed with exit code {process.returncode}"
            if stderr_output:
                error_message += f"\n[stderr]{stderr_output}[/stderr]"

            return Error(error_message)

        return Success(
            message=f"Command '{command}' executed successfully.",
            metadata={"command_output": "".join(stdout_lines)}
        )

    except FileNotFoundError:
        return Error(f"Command not found: {command.split()[0]}")
    except Exception as e:
        return Error(f"An unexpected error occurred: {e}", exception=e)
