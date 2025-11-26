"""
Core abstractions for TitanAgents system.

This module contains the base classes and interfaces that are completely
framework-agnostic. No dependencies on LangGraph, LangChain, or any other
AI framework should exist here.
"""

from typing import Any, Callable, Dict, List, Optional, Protocol, TypeVar
from dataclasses import dataclass, field
from enum import Enum
import inspect
from functools import wraps

# Type variable for generic tool functions
T = TypeVar("T", bound=Callable[..., Any])


class StepType(str, Enum):
    """
    Defines the architectural layer where a tool operates.
    
    - LIBRARY: Low-level, atomic operations (e.g., read_file, http_request)
    - SERVICE: Business logic orchestration (e.g., download_swagger_specs)
    - STEP: High-level tasks (e.g., generate_and_publish_mocks)
    """
    LIBRARY = "library"
    SERVICE = "service"
    STEP = "step"


@dataclass
class ToolParameter:
    """Metadata for a tool parameter."""
    name: str
    type_hint: str
    description: Optional[str] = None
    required: bool = True
    default: Any = None


@dataclass
class ToolSchema:
    """Schema definition for a tool, framework-agnostic."""
    name: str
    description: str
    parameters: Dict[str, ToolParameter] = field(default_factory=dict)
    step_type: StepType = StepType.SERVICE
    requires_ai: bool = False
    return_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert schema to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                k: {
                    "type": v.type_hint,
                    "description": v.description,
                    "required": v.required,
                    "default": v.default
                }
                for k, v in self.parameters.items()
            },
            "step_type": self.step_type.value,
            "requires_ai": self.requires_ai,
            "return_type": self.return_type
        }


class TitanTool:
    """
    Framework-agnostic wrapper for tools.
    
    This class encapsulates a function and its metadata, providing
    a unified interface regardless of the AI framework being used.
    
    Example:
        @titanTool(name="read_file", description="Reads a file")
        def read_file(path: str) -> str:
            with open(path) as f:
                return f.read()
    """
    
    def __init__(
        self,
        func: Callable,
        name: str,
        description: str,
        step_type: StepType = StepType.SERVICE,
        requires_ai: bool = False,
    ):
        self.func = func
        self.name = name
        self.description = description
        self.step_type = step_type
        self.requires_ai = requires_ai
        self.schema = self._generate_schema()
    
    def _generate_schema(self) -> ToolSchema:
        """Generate tool schema from function signature."""
        sig = inspect.signature(self.func)
        parameters: Dict[str, ToolParameter] = {}
        
        for param_name, param in sig.parameters.items():
            # Get type hint as string
            type_hint = "Any"
            if param.annotation != inspect.Parameter.empty:
                type_hint = (
                    param.annotation.__name__
                    if hasattr(param.annotation, "__name__")
                    else str(param.annotation)
                )
            
            # Determine if required
            required = param.default == inspect.Parameter.empty
            default = None if required else param.default
            
            parameters[param_name] = ToolParameter(
                name=param_name,
                type_hint=type_hint,
                required=required,
                default=default
            )
        
        # Get return type
        return_type = None
        if sig.return_annotation != inspect.Signature.empty:
            return_type = (
                sig.return_annotation.__name__
                if hasattr(sig.return_annotation, "__name__")
                else str(sig.return_annotation)
            )
        
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=parameters,
            step_type=self.step_type,
            requires_ai=self.requires_ai,
            return_type=return_type
        )
    
    def execute(self, **kwargs: Any) -> Any:
        """
        Execute the tool with the given parameters.
        
        This method can be overridden to add pre/post-processing,
        logging, validation, etc.
        """
        return self.func(**kwargs)
    
    def __call__(self, **kwargs: Any) -> Any:
        """Allow the tool to be called directly."""
        return self.execute(**kwargs)
    
    def __repr__(self) -> str:
        return f"TitanTool(name='{self.name}', step_type='{self.step_type.value}')"


# Global registry for tools
_TOOL_REGISTRY: Dict[str, TitanTool] = {}


def titanTool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    step_type: StepType = StepType.SERVICE,
    requires_ai: bool = False,
) -> Callable[[T], T]:
    """
    Decorator to create a TitanTool from a function.
    
    This decorator is completely framework-agnostic. It creates a tool
    that can later be adapted to any AI framework (LangGraph, OpenAI, etc.)
    
    Args:
        name: Tool name (defaults to function name)
        description: Tool description (defaults to docstring)
        step_type: Architectural layer (library/service/step)
        requires_ai: Whether the tool needs AI assistance
    
    Example:
        @titanTool(
            name="read_file",
            description="Reads the content of a file",
            step_type=StepType.LIBRARY,
            requires_ai=False
        )
        def read_file(path: str) -> str:
            '''Reads a file and returns its content.'''
            with open(path, 'r') as f:
                return f.read()
    
    Returns:
        The decorated function, enhanced with tool metadata
    """
    def decorator(func: T) -> T:
        tool_name = name or func.__name__
        tool_description = description or (func.__doc__ or "No description provided").strip()
        
        # Create the TitanTool instance
        titan_tool = TitanTool(
            func=func,
            name=tool_name,
            description=tool_description,
            step_type=step_type,
            requires_ai=requires_ai,
        )
        
        # Register in global registry
        _TOOL_REGISTRY[tool_name] = titan_tool
        
        # Create a wrapper that preserves the original function behavior
        # but also carries the tool metadata
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return titan_tool.execute(*args, **kwargs)
        
        # Attach the TitanTool instance to the wrapper
        wrapper._titan_tool = titan_tool  # type: ignore
        
        return wrapper  # type: ignore
    
    return decorator


def get_tool(name: str) -> Optional[TitanTool]:
    """Retrieve a tool from the global registry by name."""
    return _TOOL_REGISTRY.get(name)


def get_all_tools() -> List[TitanTool]:
    """Retrieve all registered tools."""
    return list(_TOOL_REGISTRY.values())


def clear_registry() -> None:
    """Clear the tool registry (useful for testing)."""
    _TOOL_REGISTRY.clear()
