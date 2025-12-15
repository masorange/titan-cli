import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from titan_cli.core.workflows.project_step_source import ProjectStepSource
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Success

# --- Fixtures ---

@pytest.fixture
def mock_project_root(tmp_path: Path):
    """Creates a mock project root with a .titan/steps directory."""
    steps_dir = tmp_path / ".titan" / "steps"
    steps_dir.mkdir(parents=True)
    return tmp_path

@pytest.fixture
def mock_step_file(mock_project_root: Path):
    """Creates a mock Python step file."""
    step_path = mock_project_root / ".titan" / "steps" / "my_step.py"
    step_path.write_text("""
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Success, Error

def my_step(ctx: WorkflowContext) -> Success:
    return Success("Mock step executed")
""")
    return step_path

@pytest.fixture
def mock_non_callable_step_file(mock_project_root: Path):
    """Creates a mock Python step file with a non-callable object."""
    step_path = mock_project_root / ".titan" / "steps" / "bad_step.py"
    step_path.write_text("""
not_a_function = "I am a string"
""")
    return step_path

@pytest.fixture
def mock_error_step_file(mock_project_root: Path):
    """Creates a mock Python step file that raises an error on import."""
    step_path = mock_project_root / ".titan" / "steps" / "error_step.py"
    step_path.write_text("""
raise ValueError("Error during import")
""")
    return step_path

# --- Tests for discover() ---

def test_discover_no_steps_directory(tmp_path: Path):
    """Tests discover() when .titan/steps directory does not exist."""
    source = ProjectStepSource(tmp_path)
    assert source.discover() == []

def test_discover_empty_steps_directory(mock_project_root: Path):
    """Tests discover() when .titan/steps directory is empty."""
    source = ProjectStepSource(mock_project_root)
    assert source.discover() == []

def test_discover_valid_step_file(mock_step_file: Path, mock_project_root: Path):
    """Tests discover() finds a valid step file."""
    source = ProjectStepSource(mock_project_root)
    steps = source.discover()
    assert len(steps) == 1
    assert steps[0].name == "my_step"
    assert steps[0].path == mock_step_file

def test_discover_excludes_init_py(mock_project_root: Path):
    """Tests discover() excludes __init__.py."""
    (mock_project_root / ".titan" / "steps" / "__init__.py").write_text("my_var = 1")
    source = ProjectStepSource(mock_project_root)
    assert source.discover() == []

def test_discover_excludes_pycache(mock_project_root: Path):
    """Tests discover() excludes __pycache__ (even though glob would already)."""
    (mock_project_root / ".titan" / "steps" / "__pycache__").mkdir()
    source = ProjectStepSource(mock_project_root)
    assert source.discover() == []

def test_discover_caches_results(mock_step_file: Path, mock_project_root: Path):
    """Tests that discover() caches its results."""
    source = ProjectStepSource(mock_project_root)
    first_call = source.discover()
    # Modify filesystem after first call
    (mock_project_root / ".titan" / "steps" / "new_step.py").write_text("def new_step(): pass")
    second_call = source.discover()
    assert first_call == second_call # Should return cached result
    assert len(second_call) == 1


# --- Tests for get_step() ---

def test_get_step_non_existent(mock_project_root: Path):
    """Tests get_step() for a non-existent step."""
    source = ProjectStepSource(mock_project_root)
    assert source.get_step("non_existent_step") is None

def test_get_step_valid_function(mock_step_file: Path, mock_project_root: Path):
    """Tests get_step() retrieves a valid callable function."""
    source = ProjectStepSource(mock_project_root)
    step_func = source.get_step("my_step")
    assert callable(step_func)

    # Test execution of the mock step
    mock_ctx = MagicMock(spec=WorkflowContext)
    result = step_func(mock_ctx)
    assert isinstance(result, Success)
    assert result.message == "Mock step executed"

def test_get_step_non_callable_object(mock_non_callable_step_file: Path, mock_project_root: Path):
    """Tests get_step() returns None for a file with a non-callable object."""
    source = ProjectStepSource(mock_project_root)
    assert source.get_step("bad_step") is None

def test_get_step_error_during_import(mock_error_step_file: Path, mock_project_root: Path):
    """Tests get_step() returns None when an error occurs during module import."""
    source = ProjectStepSource(mock_project_root)
    with patch('builtins.print'): # Suppress the print statement from ProjectStepSource if it were still there
        assert source.get_step("error_step") is None

def test_get_step_caches_functions(mock_step_file: Path, mock_project_root: Path):
    """Tests that get_step() caches the loaded step functions."""
    source = ProjectStepSource(mock_project_root)
    first_call = source.get_step("my_step")
    second_call = source.get_step("my_step")
    assert first_call is second_call # Should return the same cached function object