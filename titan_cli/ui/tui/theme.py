"""
Titan TUI Theme

Centralized theme configuration for the Textual UI.
Defines color variables, CSS utilities, and style constants.

Color values are imported from colors.py to ensure consistency
between CSS and Python code (e.g., Rich Text objects).
"""

from .colors import (
    PRIMARY, SECONDARY, ACCENT, ERROR, WARNING, SUCCESS, INFO,
    SURFACE, SURFACE_LIGHTEN_1, SURFACE_LIGHTEN_2,
    TEXT, TEXT_MUTED, TEXT_DISABLED
)

# Titan Theme CSS - Dracula Edition
# Uses color constants from colors.py for consistency
TITAN_THEME_CSS = f"""
/* Color Variables - Imported from colors.py */
$primary: {PRIMARY};           /* Purple (Dracula standard) */
$secondary: {SECONDARY};       /* Green */
$accent: {ACCENT};             /* Pink */
$error: {ERROR};               /* Red */
$warning: {WARNING};           /* Yellow */
$success: {SUCCESS};           /* Green */
$info: {INFO};                 /* Cyan */

/* Backgrounds */
$surface: {SURFACE};
$surface-lighten-1: {SURFACE_LIGHTEN_1};
$surface-lighten-2: {SURFACE_LIGHTEN_2};

/* Text Colors */
$text: {TEXT};                 /* Foreground (Almost white) */
$text-muted: {TEXT_MUTED};     /* Comment */
$text-disabled: {TEXT_DISABLED}; /* Disabled */

/* Banner gradient colors */
$banner-start: {TEXT_MUTED};
$banner-mid: {PRIMARY};
$banner-end: {ACCENT};

/* Base widget styles */
.title {{
    color: $primary;
    text-style: bold;
}}

.subtitle {{
    color: $secondary;
    text-style: bold;
}}

.body {{
    color: $text;
}}

.muted {{
    color: $text-muted;
    text-style: italic;
}}

.error-text {{
    color: $error;
    text-style: bold;
}}

.success-text {{
    color: $success;
    text-style: bold;
}}

.warning-text {{
    color: $warning;
    text-style: bold;
}}

.info-text {{
    color: $info;
}}

/* Text widget styles (from widgets/text.py) */
.dim, DimText, DimItalicText {{
    color: $text-muted;
}}

.bold, BoldText, BoldPrimaryText {{
    text-style: bold;
}}

.italic, ItalicText, DimItalicText {{
    text-style: italic;
}}

.primary, PrimaryText, BoldPrimaryText {{
    color: $primary;
}}

.success, SuccessText {{
    color: $success;
}}

.error, ErrorText {{
    color: $error;
}}

.warning, WarningText {{
    color: $warning;
}}

/* Global scrollbar styles - applies to all widgets */
* {{
    scrollbar-background: $surface;
    scrollbar-background-hover: $surface-lighten-1;
    scrollbar-background-active: $surface-lighten-2;
    scrollbar-color: $primary;
    scrollbar-color-hover: $accent;
    scrollbar-color-active: $accent;
    scrollbar-corner-color: $surface;
}}

/* Global OptionList styles - transparent to inherit parent background */
OptionList {{
    border: none;
    background: transparent;
}}

OptionList > .option-list--option {{
    background: transparent;
}}

OptionList > .option-list--option-highlighted {{
    background: $primary;
}}

Screen {{
    background: $surface;
    color: $text;
}}
"""
