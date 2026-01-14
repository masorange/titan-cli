"""
Titan TUI Theme

Centralized theme configuration for the Textual UI.
Defines color variables, CSS utilities, and style constants.
"""

# Titan Theme CSS - Dracula Edition (Grises y Púrpuras)
TITAN_THEME_CSS = """
/* Color Variables */
$primary: #bd93f9;           /* Purple (Dracula standard) */
$secondary: #50fa7b;         /* Green */
$accent: #ff79c6;            /* Pink */
$error: #ff5555;             /* Red */
$warning: #f1fa8c;           /* Yellow */
$success: #50fa7b;           /* Green */
$info: #8be9fd;              /* Cyan */

/* Backgrounds */
$surface: #282a36;           
$surface-lighten-1: #343746; 
$surface-lighten-2: #44475a;

/* Text Colors */
$text: #f8f8f2;              /* Foreground (Almost white) */
$text-muted: #6272a4;        /* Comment */
$text-disabled: #44475a;     /* Disabled */

/* Banner gradient colors */
$banner-start: #6272a4;      
$banner-mid: #bd93f9;        
$banner-end: #ff79c6;     

/* Base widget styles */
.title {
    color: $primary;
    text-style: bold;
}

.subtitle {
    color: $secondary;
    text-style: bold;
}

.body {
    color: $text;
}

.muted {
    color: $text-muted;
    text-style: italic;
}

.error-text {
    color: $error;
    text-style: bold;
}

.success-text {
    color: $success;
    text-style: bold;
}

.warning-text {
    color: $warning;
    text-style: bold;
}

.info-text {
    color: $info;
}

/* Global scrollbar styles - applies to all widgets */
* {
    scrollbar-background: $surface;
    scrollbar-background-hover: $surface-lighten-1;
    scrollbar-background-active: $surface-lighten-2;
    scrollbar-color: $primary;
    scrollbar-color-hover: $accent;
    scrollbar-color-active: $accent;
    scrollbar-corner-color: $surface;
}

/* Global OptionList styles - transparent to inherit parent background */
OptionList {
    border: none;
    background: transparent;
}

OptionList > .option-list--option {
    background: transparent;
}

OptionList > .option-list--option-highlighted {
    background: $primary;
}

Screen {
    background: $surface;
    color: $text;
}
"""
