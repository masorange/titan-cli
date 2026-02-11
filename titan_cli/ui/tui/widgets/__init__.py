"""
Titan TUI Widgets

Reusable Textual widgets for the Titan TUI.
"""
from .status_bar import StatusBarWidget
from .header import HeaderWidget
from .panel import Panel
from .panel_container import PanelContainer
from .table import Table
from .button import Button
from .step_container import StepContainer
from .comment import Comment
from .comment_thread import CommentThread
from .code_block import CodeBlock
from .multiline_input import MultilineInput
from .prompt_input import PromptInput
from .prompt_textarea import PromptTextArea
from .prompt_selection_list import PromptSelectionList, SelectionOption
from .prompt_choice import PromptChoice, ChoiceOption
from .prompt_option_list import PromptOptionList, OptionItem
from .styled_option_list import StyledOptionList, StyledOption
from .text import (
    Text,
    DimText,
    BoldText,
    PrimaryText,
    BoldPrimaryText,
    SuccessText,
    ErrorText,
    WarningText,
    ItalicText,
    DimItalicText,
)
from .comment_utils import (
    TextElement,
    SuggestionElement,
    CodeBlockElement,
    CommentElement,
    parse_comment_body,
)

__all__ = [
    "StatusBarWidget",
    "HeaderWidget",
    "Panel",
    "PanelContainer",
    "Table",
    "Button",
    "StepContainer",
    "Comment",
    "CommentThread",
    "CodeBlock",
    "MultilineInput",
    "PromptInput",
    "PromptTextArea",
    "PromptSelectionList",
    "SelectionOption",
    "PromptChoice",
    "ChoiceOption",
    "PromptOptionList",
    "OptionItem",
    "StyledOptionList",
    "StyledOption",
    "Text",
    "DimText",
    "BoldText",
    "PrimaryText",
    "BoldPrimaryText",
    "SuccessText",
    "ErrorText",
    "WarningText",
    "ItalicText",
    "DimItalicText",
    "TextElement",
    "SuggestionElement",
    "CodeBlockElement",
    "CommentElement",
    "parse_comment_body",
]
