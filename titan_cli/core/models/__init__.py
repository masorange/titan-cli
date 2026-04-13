# core/models/__init__.py
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field, model_validator

from ..plugins.models import PluginConfig


class ProjectConfig(BaseModel):
    """
    Represents the configuration for a specific project.
    Defined in .titan/config.toml.
    """

    name: str = Field(..., description="Name of the project.")
    type: Optional[str] = Field(
        "generic",
        description="Type of the project (e.g., 'fullstack', 'backend', 'frontend').",
    )


class AIConnectionKind(str, Enum):
    """Kinds of AI connections supported by Titan."""

    GATEWAY = "gateway"
    DIRECT_PROVIDER = "direct_provider"


class AIGatewayType(str, Enum):
    """Gateway backends supported by Titan."""

    OPENAI_COMPATIBLE = "openai_compatible"


class AIDirectProvider(str, Enum):
    """Direct providers supported by Titan."""

    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENAI = "openai"
    CUSTOM = "custom"


class AIConnectionConfig(BaseModel):
    """Configuration for an AI connection."""

    name: str = Field(..., description="Human-readable connection name")
    kind: AIConnectionKind = Field(..., description="Connection type")
    gateway_type: Optional[AIGatewayType] = Field(
        None, description="Gateway backend type"
    )
    provider: Optional[AIDirectProvider] = Field(
        None, description="Direct provider type"
    )
    base_url: Optional[str] = Field(None, description="Gateway endpoint URL")
    default_model: Optional[str] = Field(
        None, description="Default model to use for this connection"
    )
    max_tokens: int = Field(4096)
    temperature: float = Field(0.7)

    @model_validator(mode="after")
    def validate_shape(self) -> "AIConnectionConfig":
        """Validate mutually exclusive connection settings."""
        if self.kind == AIConnectionKind.GATEWAY:
            if not self.gateway_type:
                raise ValueError("gateway connections require 'gateway_type'")
            if not self.base_url:
                raise ValueError("gateway connections require 'base_url'")
            if self.provider is not None:
                raise ValueError("gateway connections must not define 'provider'")

        if self.kind == AIConnectionKind.DIRECT_PROVIDER:
            if not self.provider:
                raise ValueError("direct_provider connections require 'provider'")
            if self.gateway_type is not None:
                raise ValueError(
                    "direct_provider connections must not define 'gateway_type'"
                )

        return self

    @property
    def model(self) -> Optional[str]:
        """Backward-compatible alias used by older callers."""
        return self.default_model


AIProviderConfig = AIConnectionConfig


class AIConfig(BaseModel):
    """
    Represents the configuration for AI connections.
    Can be defined globally or per project.
    """

    default_connection: Optional[str] = Field(
        None, description="Default AI connection ID"
    )
    connections: Dict[str, AIConnectionConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_default_connection(self) -> "AIConfig":
        """Ensure the default connection exists when configured."""
        if self.default_connection and self.default_connection not in self.connections:
            raise ValueError(
                f"Default connection '{self.default_connection}' not found in configured connections."
            )
        return self

    @property
    def default(self) -> Optional[str]:
        """Backward-compatible alias used by older callers."""
        return self.default_connection

    @property
    def providers(self) -> Dict[str, AIConnectionConfig]:
        """Backward-compatible alias used by older callers."""
        return self.connections


class TitanConfigModel(BaseModel):
    """
    The main Pydantic model for the entire Titan CLI configuration.
    This model validates the merged configuration from global and project sources.
    """

    config_version: str = Field("1.0", description="Configuration schema version.")
    project: Optional[ProjectConfig] = Field(
        None, description="Project-specific configuration."
    )
    ai: Optional[AIConfig] = Field(None, description="AI connection configuration.")
    plugins: Dict[str, PluginConfig] = Field(
        default_factory=dict, description="Dictionary of plugin configurations."
    )
