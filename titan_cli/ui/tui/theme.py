"""
Titan TUI Theme

Centralized theme configuration for the Textual UI.
Defines color variables, CSS utilities, and style constants.
"""

# Titan Theme CSS - Define color variables and base styles
TITAN_THEME_CSS = """
/* Color Variables - Based on your current Rich theme */
$primary: #3b82f6;           /* Blue */
$secondary: #10b981;         /* Green */
$accent: #f59e0b;            /* Amber */
$error: #ef4444;             /* Red */
$warning: #f59e0b;           /* Amber */
$success: #10b981;           /* Green */
$info: #3b82f6;              /* Blue */

$surface: #1e293b;           /* Dark surface */
$surface-lighten-1: #334155; /* Lighter surface */
$surface-lighten-2: #475569; /* Even lighter */

$text: #e2e8f0;              /* Light text */
$text-muted: #94a3b8;        /* Muted text */
$text-disabled: #64748b;     /* Disabled text */

/* Banner gradient colors */
$banner-start: #3b82f6;
$banner-mid: #8b5cf6;
$banner-end: #ec4899;

/* Spacing */
$spacing-small: 1;
$spacing-medium: 2;
$spacing-large: 3;

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
"""
