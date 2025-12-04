from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

class WorkflowStepModel(BaseModel):
    """
    Represents a single step in a workflow.
    """
    id: Optional[str] = Field(None, description="Unique identifier for the step.")
    name: str = Field(..., description="Human-readable name for the step.")
    plugin: Optional[str] = Field(None, description="The plugin providing the step (e.g., 'git', 'github').")
    step: Optional[str] = Field(None, description="The name of the step function within the plugin.")
    command: Optional[str] = Field(None, description="A shell command to execute.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters to pass to the step or command.")
    on_error: Literal["fail", "continue"] = Field("fail", description="Action to take if the step fails.")
    
    # Used only in base workflow definitions to mark injection points for hooks
    hook: Optional[str] = Field(None, description="Marks this step as a hook point for extension.")

class WorkflowConfigModel(BaseModel):
    """
    Represents the overall configuration of a workflow.
    """
    name: str = Field(..., description="The name of the workflow.")
    description: Optional[str] = Field(None, description="A description of what the workflow does.")
    source: Optional[str] = Field(None, description="Where the workflow is defined (e.g., 'plugin:github').")
    extends: Optional[str] = Field(None, description="The base workflow this workflow extends.")
    
    params: Dict[str, Any] = Field(default_factory=dict, description="Workflow-level parameters that can be overridden.")
    
    # For base workflows: list of hook names (e.g., ["before_commit"])
    # For extending workflows: dict of hook_name -> list of steps to inject
    # This will be handled during loading/merging by the WorkflowLoader,
    # so we define it broadly here and refine during processing.
    hooks: Optional[Union[List[str], Dict[str, List[WorkflowStepModel]]]] = Field(None, description="Hook definitions or steps to inject into hooks.")
    
    steps: List[WorkflowStepModel] = Field(default_factory=list, description="The sequence of steps in the workflow.")
