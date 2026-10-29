"""
Titan TUI Widgets

Reusable Textual widgets for the Titan TUI.
"""
from .dock import Dock, DockItem
from .header import HeaderWidget
from .panel import Panel
from .error_card import ErrorCard
from .panel_container import PanelContainer
from .table import Table
from .json_tree import (
    JsonTree,
    JsonTreeDetail,
    build_json_entry,
)
from .button import Button
from .step_container import StepContainer
from .multiline_input import MultilineInput
from .prompt_input import PromptInput
from .prompt_textarea import PromptTextArea
from .prompt_selection_list import PromptSelectionList, SelectionOption
from .prompt_choice import PromptChoice, ChoiceOption
from .chip import Chip
from .workflow_card import WorkflowCard
from .mod_home_card import ModHomeCard
from .decision_badge import DecisionBadge
from .prompt_option_list import PromptOptionList, OptionItem
from .styled_option_list import StyledOptionList, StyledOption
from .wizard import StepStatus, WizardStep, StepIndicator
from .segmented_switch import SegmentedSwitch, SegmentedSwitchOption
from .labeled_switch import LabeledSwitch
from .list_detail_panel import ListDetailPanel
from .tabs import TabbedPanel, TabPanel
from .dev_source_path_modal import DevSourcePathModal
from .collapsible_list import (
    CollapsibleEntry,
    build_collapsible_list,
    escape_markup,
)
from .text import (
    Text,
    DimText,
    BoldText,
    PrimaryText,
    BoldPrimaryText,
    SuccessText,
    WarningText,
    ItalicText,
    DimItalicText,
)

__all__ = [
    "Dock",
    "DockItem",
    "HeaderWidget",
    "Panel",
    "ErrorCard",
    "PanelContainer",
    "Table",
    "JsonTree",
    "JsonTreeDetail",
    "build_json_entry",
    "Button",
    "StepContainer",
    "MultilineInput",
    "PromptInput",
    "PromptTextArea",
    "PromptSelectionList",
    "SelectionOption",
    "PromptChoice",
    "ChoiceOption",
    "Chip",
    "WorkflowCard",
    "ModHomeCard",
    "DecisionBadge",
    "PromptOptionList",
    "OptionItem",
    "StyledOptionList",
    "StyledOption",
    "SegmentedSwitch",
    "SegmentedSwitchOption",
    "LabeledSwitch",
    "ListDetailPanel",
    "TabbedPanel",
    "TabPanel",
    "DevSourcePathModal",
    "CollapsibleEntry",
    "build_collapsible_list",
    "escape_markup",
    "Text",
    "DimText",
    "BoldText",
    "PrimaryText",
    "BoldPrimaryText",
    "SuccessText",
    "WarningText",
    "ItalicText",
    "DimItalicText",
    "StepStatus",
    "WizardStep",
    "StepIndicator",
]
