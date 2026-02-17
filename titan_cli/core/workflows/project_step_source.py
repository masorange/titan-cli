import importlib.util
import sys
from pathlib import Path
from typing import Callable, Dict, Any, Optional, List
from dataclasses import dataclass

from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import WorkflowResult

# Define a type alias for a Step Function
StepFunction = Callable[[WorkflowContext, Dict[str, Any]], WorkflowResult]

@dataclass
class StepInfo:
    """
    Metadata for a discovered project step.
    """
    name: str
    path: Path
    
class BaseStepSource:
    """
    Base class for discovering and loading Python step functions.
    """
    EXCLUDED_FILES = {"__init__.py", "__pycache__"}

    def __init__(self, steps_dir: Path):
        self._steps_dir = steps_dir
        self._step_info_cache: Optional[List[StepInfo]] = None
        self._step_function_cache: Dict[str, StepFunction] = {}

    def discover(self) -> List[StepInfo]:
        """
        Discovers all available step files in the project's .titan/steps directory.
        Supports subdirectories (e.g., .titan/steps/jira/step.py).
        """
        if self._step_info_cache is not None:
            return self._step_info_cache

        if not self._steps_dir.is_dir():
            self._step_info_cache = []
            return []

        discovered = []
        for step_file in self._steps_dir.glob("**/*.py"):
            if step_file.name not in self.EXCLUDED_FILES and not any(part.startswith("__") for part in step_file.parts):
                step_name = step_file.stem
                discovered.append(StepInfo(name=step_name, path=step_file))

        self._step_info_cache = discovered
        return discovered

    def get_step(self, step_name: str) -> Optional[StepFunction]:
        """
        Retrieves a step function by name, loading it from its file if necessary.
        Searches all Python files in the directory (including subdirectories) for the function.
        """
        if step_name in self._step_function_cache:
            return self._step_function_cache[step_name]

        if not self._steps_dir.is_dir():
            return None

        # Search all Python files (including subdirectories) for the function
        for step_file in self._steps_dir.glob("**/*.py"):
            if step_file.name in self.EXCLUDED_FILES or any(part.startswith("__") for part in step_file.parts):
                continue

            try:
                # Use a unique module name to avoid conflicts
                module_name = f"_titan_step_{step_file.stem}_{id(step_file)}"
                spec = importlib.util.spec_from_file_location(module_name, step_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Look for the function in this module
                    step_func = getattr(module, step_name, None)
                    if callable(step_func):
                        self._step_function_cache[step_name] = step_func
                        return step_func

            except Exception:
                # Continue searching other files
                continue

        return None


class ProjectStepSource(BaseStepSource):
    """
    Discovers and loads Python step functions from a project's .titan/steps/ directory.
    Supports relative imports by properly setting module __package__ attribute.
    """
    def __init__(self, project_root: Path):
        steps_dir = project_root / ".titan" / "steps"
        super().__init__(steps_dir)
        self._project_root = project_root
        self._titan_dir = project_root / ".titan"

        # Add .titan directory to sys.path to enable absolute imports
        titan_dir_str = str(self._titan_dir)
        if titan_dir_str not in sys.path:
            sys.path.insert(0, titan_dir_str)

    def get_step(self, step_name: str) -> Optional[StepFunction]:
        """
        Retrieves a step function by name.
        Project steps should use absolute imports from .titan/ as the root.
        """
        if step_name in self._step_function_cache:
            return self._step_function_cache[step_name]

        if not self._steps_dir.is_dir():
            return None

        # Search all Python files for the function
        for step_file in self._steps_dir.glob("**/*.py"):
            if step_file.name in self.EXCLUDED_FILES or any(part.startswith("__") for part in step_file.parts):
                continue

            try:
                # Use a unique module name to avoid conflicts
                module_name = f"_titan_step_{step_file.stem}_{id(step_file)}"
                spec = importlib.util.spec_from_file_location(module_name, step_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Look for the function
                    step_func = getattr(module, step_name, None)
                    if callable(step_func):
                        self._step_function_cache[step_name] = step_func
                        return step_func

            except Exception as e:
                # Log import errors to help with debugging
                import traceback
                error_info = f"Error loading {step_file}: {type(e).__name__}: {e}"
                # Store error in a class variable for later retrieval
                if not hasattr(self, '_load_errors'):
                    self._load_errors = {}
                self._load_errors[str(step_file)] = {
                    'error': error_info,
                    'traceback': traceback.format_exc()
                }
                # Continue searching other files
                continue

        # If step wasn't found but we had load errors, write them to a debug file
        if hasattr(self, '_load_errors') and self._load_errors:
            debug_file = Path("/tmp/titan_step_load_errors.txt")
            with open(debug_file, 'w') as f:
                f.write(f"Step '{step_name}' not found. Errors during module loading:\n\n")
                for file_path, error_data in self._load_errors.items():
                    f.write(f"File: {file_path}\n")
                    f.write(f"Error: {error_data['error']}\n")
                    f.write(f"Full traceback:\n{error_data['traceback']}\n")
                    f.write("="*80 + "\n\n")

        return None


class UserStepSource(BaseStepSource):
    """
    Discovers and loads Python step functions from user's ~/.titan/steps/ directory.
    """
    def __init__(self):
        steps_dir = Path.home() / ".titan" / "steps"
        super().__init__(steps_dir)
