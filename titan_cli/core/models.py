# core/models.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class ProjectConfig(BaseModel):
    name: str
    type: Optional[str] = "generic"  # fullstack, backend, frontend, etc.

class AIConfig(BaseModel):
    provider: str = "anthropic"  # anthropic, openai, gemini
    model: Optional[str] = None
    api_key: Optional[str] = None  # From global config

class PluginConfig(BaseModel):
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)

class CoreConfig(BaseModel):
    """Core Titan CLI settings, typically defined in the global config."""
    project_root: Optional[str] = None

class TitanConfigModel(BaseModel):
    project: Optional[ProjectConfig] = None # Project section is not guaranteed
    core: Optional[CoreConfig] = None
    ai: Optional[AIConfig] = None
    plugins: Dict[str, PluginConfig] = Field(default_factory=dict)