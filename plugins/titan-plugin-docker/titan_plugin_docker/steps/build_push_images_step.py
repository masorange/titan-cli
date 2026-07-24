# plugins/titan-plugin-docker/titan_plugin_docker/steps/build_push_images_step.py
from textual.widgets import Log

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError

from ..operations import resolve_build_targets
from ..exceptions import DockerError


def build_push_images_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Build (and push, per target config) one or all configured Docker images.

    Streams `docker buildx build` output into a live scrollable console per
    target, instead of a plain spinner, so progress is visible for long builds.

    Inputs (from ctx.data):
        build_target_name (str, optional): Name of a single configured build target
            (absent builds every target configured for the project)

    Outputs (saved to ctx.data):
        docker_build_results (List[UIBuildResult]): One result per built image

    Returns:
        Success: All requested targets built
        Error: Docker client not available, no targets configured/matched, or a build failed
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.docker:
        return Error("Docker client not available in context")

    ctx.textual.begin_step("Build Docker Images")

    target_name = ctx.get("build_target_name")

    try:
        targets = resolve_build_targets(ctx.docker.build_targets, name=target_name)
    except DockerError as e:
        ctx.textual.error_text(str(e))
        ctx.textual.end_step("error")
        return Error(str(e))

    if not targets:
        ctx.textual.error_text("No build targets configured for this project.")
        ctx.textual.end_step("error")
        return Error("No build targets configured for this project.")

    results = []
    for target in targets:
        ctx.textual.dim_text(f"Building {target.name} ({target.platforms})...")

        console = Log(highlight=False)
        console.styles.height = 14
        console.styles.border = ("round", "gray")
        ctx.textual.mount(console)

        def on_output(line: str, console=console) -> None:
            try:
                ctx.textual.app.call_from_thread(console.write_line, line)
            except Exception:
                pass

        result = ctx.docker.build_target(target, on_output=on_output)

        match result:
            case ClientSuccess(data=build_result):
                ctx.textual.success_text(build_result.summary)
                results.append(build_result)
            case ClientError(error_message=err):
                ctx.textual.error_text(f"Failed to build {target.name}: {err}")
                ctx.textual.end_step("error")
                return Error(f"Failed to build {target.name}: {err}")

    ctx.textual.end_step("success")
    return Success(
        f"Built {len(results)} image(s)",
        metadata={"docker_build_results": results},
    )


__all__ = ["build_push_images_step"]
