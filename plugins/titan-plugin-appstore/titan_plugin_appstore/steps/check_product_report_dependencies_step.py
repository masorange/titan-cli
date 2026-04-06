"""
Check product report dependencies step for App Store Connect.

Verifies that all required packages for the iOS product report are installed:
  - App Store Connect API client (built-in)
  - fpdf2 (PDF export)
  - matplotlib (charts generation)
"""

import importlib
import subprocess
import sys

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


_REQUIRED_PACKAGES = [
    ("fpdf", "fpdf2"),
    ("matplotlib", "matplotlib"),
]

_PIP_PACKAGES = [
    "fpdf2",
    "matplotlib",
]


def check_product_report_dependencies_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Check that all product report packages are installed, offering to install if missing.

    Returns:
        Success: All dependencies available.
        Error: Missing packages and user declined, or install failed.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Check Dependencies")

    missing_packages = _find_missing_packages()

    if not missing_packages:
        ctx.textual.text("")
        ctx.textual.success_text("✓ All dependencies available")
        ctx.textual.text("")
        ctx.textual.end_step("success")
        return Success("All dependencies available")

    ctx.textual.text("")
    ctx.textual.warning_text("⚠ Missing required packages:")
    for _, pkg in missing_packages:
        ctx.textual.dim_text(f"  • {pkg}")
    ctx.textual.text("")

    install = ctx.textual.ask_confirm("Install missing packages now?", default=True)

    if not install:
        ctx.textual.text("")
        ctx.textual.bold_text("Run manually to install:")
        ctx.textual.primary_text(
            f"  {sys.executable} -m pip install {' '.join(_PIP_PACKAGES)}"
        )
        ctx.textual.text("")
        ctx.textual.end_step("error")
        return Error(f"Missing packages: {', '.join(pkg for _, pkg in missing_packages)}")

    ctx.textual.text("")

    try:
        with ctx.textual.loading("Installing packages..."):
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install"] + _PIP_PACKAGES,
                capture_output=True,
                text=True,
            )

        if result.returncode != 0:
            ctx.textual.error_text("Installation failed:")
            ctx.textual.dim_text(result.stderr or result.stdout)
            ctx.textual.text("")
            ctx.textual.end_step("error")
            return Error(f"pip install failed: {result.stderr}")

    except Exception as e:
        ctx.textual.error_text(f"Installation error: {e}")
        ctx.textual.text("")
        ctx.textual.end_step("error")
        return Error(f"Installation error: {e}")

    # Invalidate import cache so newly installed packages are importable
    importlib.invalidate_caches()

    still_missing = _find_missing_packages()
    if still_missing:
        ctx.textual.error_text(
            f"Installed but still not importable: "
            f"{', '.join(pkg for _, pkg in still_missing)}"
        )
        ctx.textual.dim_text("Try running titan again.")
        ctx.textual.text("")
        ctx.textual.end_step("error")
        return Error(f"Packages not importable after install: {still_missing}")

    ctx.textual.success_text("✓ Packages installed successfully")
    ctx.textual.text("")
    ctx.textual.end_step("success")
    return Success("Dependencies installed and available")


def _find_missing_packages() -> list[tuple[str, str]]:
    """Return list of (module_name, package_name) for packages that cannot be imported."""
    missing = []
    for module_name, package_name in _REQUIRED_PACKAGES:
        try:
            __import__(module_name)
        except ImportError:
            missing.append((module_name, package_name))
    return missing


__all__ = ["check_product_report_dependencies_step"]
