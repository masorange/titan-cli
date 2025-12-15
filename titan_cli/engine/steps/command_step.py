import os
from pathlib import Path
from subprocess import Popen, PIPE
import re
from titan_cli.core.workflows.models import WorkflowStepModel
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Success, Error, WorkflowResult


def resolve_parameters_in_string(text: str, ctx: WorkflowContext) -> str:
    """
    Substitutes ${placeholder} in a string using values from ctx.data.
    Public function so it can be used by workflow_executor.
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

    command = resolve_parameters_in_string(command_template, ctx)

    if ctx.ui:
        ctx.ui.text.info(f"Executing command: {command}")

    try:
        use_venv = step.params.get("use_venv", False)
        process_env = os.environ.copy()
        cwd = ctx.get("cwd") or os.getcwd()

        if use_venv:
            if ctx.ui:
                ctx.ui.text.body("Activating poetry virtual environment for step...", style="dim")
            
            env_proc = Popen(["poetry", "env", "info", "-p"], stdout=PIPE, stderr=PIPE, text=True, cwd=cwd)
            venv_path, err = env_proc.communicate()
            
            if env_proc.returncode == 0 and venv_path.strip():
                bin_path = Path(venv_path.strip()) / "bin"
                process_env["PATH"] = f"{bin_path}:{process_env['PATH']}"
            else:
                return Error(f"Could not determine poetry virtual environment. Error: {err}")

        # We capture stdout now instead of streaming to be able to parse it.
        process = Popen(command, shell=True, stdout=PIPE, stderr=PIPE, text=True, cwd=cwd, env=process_env)
        
        stdout_output, stderr_output = process.communicate()

        if stdout_output:
            # Print any output from the command
            print(stdout_output)
        
        if process.returncode != 0:
            error_message = f"Command failed with exit code {process.returncode}"
            if stderr_output:
                error_message += f"\n{stderr_output}"

            return Error(error_message)

        return Success(
            message=f"Command '{command}' executed successfully.",
            metadata={"command_output": stdout_output}
        )

    except FileNotFoundError:
        return Error(f"Command not found: {command.split()[0]}")
    except Exception as e:
        return Error(f"An unexpected error occurred: {e}", exception=e)

