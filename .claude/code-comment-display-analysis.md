# Code Comment Display Analysis

## Overview

Este documento recopila toda la información sobre cómo se muestran comentarios y fragmentos de código en los dos workflows de PR review principales:

1. **Review PR (Iterative AI)** - `review-pr-iterative.yaml`
2. **Respond to PR Comments** - `respond-pr-comments.yaml`

## Problem Statement

Los comentarios generales (issue comments) no se están mostrando correctamente con el fragmento de código (hunk) en el workflow iterativo. La lógica para mostrar código está dispersa en varios steps y widgets, lo que causa:

- Inconsistencia visual entre comentarios inline y generales
- Dificultad de reutilización de código
- Falta de componente centralizado para gestionar ambos tipos de comentarios

## Architecture Current

### 1. Models Layer - Data Structures

```
UIComment (models/view.py:18)
├── id: int
├── body: str
├── author_login: str
├── author_name: str
├── formatted_date: str
├── path: Optional[str]          ← Null for general comments
├── line: Optional[int]          ← Null for general comments
└── diff_hunk: Optional[str]     ← Null for general comments

UICommentThread (models/view.py:68)
├── thread_id: str
├── main_comment: UIComment
├── replies: List[UIComment]
├── is_resolved: bool
├── is_outdated: bool
└── is_general_comment: bool     ← Property checks if thread_id starts with "general_"
```

**Key insight**: General comments se diferencian de inline comments mediante:
- `thread_id.startswith("general_")` → general comment
- `main_comment.path is None` → general comment
- `main_comment.line is None` → general comment

### 2. Widgets Layer - Display Components

#### A. Comment Widget (`widgets/comment.py`)

Displays a single comment with full context:

```
Comment Widget
├── Outdated badge (if is_outdated=True)
├── Metadata container (author + date)
├── File info container (only if comment.path exists)
│   └── ItalicText: filepath
│   └── DimText: "Line X" or "General file comment"
├── Code context widget (only if comment.diff_hunk exists)
│   └── CodeBlock with diff_context extracted around target_line
└── Parsed & rendered comment body
    └── Markdown text, code blocks, suggestions
```

**Problem**: Assumes `comment.path` exists. For general comments, the file info container is NOT rendered, so context is lost.

#### B. ReviewSuggestion Widget (`widgets/review_suggestion.py`)

Displays an AI-generated review suggestion:

```
ReviewSuggestion Widget (for AI iterative review)
├── Severity badge (🔴 CRITICAL, 🟡 IMPROVEMENT, 🔵 SUGGESTION)
├── File info container
│   └── file_path + "Line X" / "General file comment" / snippet preview
├── Code context widget (if suggestion.diff_context exists)
│   └── CodeBlock with extracted diff context
└── Parsed suggestion body
    └── Markdown, code blocks, etc.
```

#### C. CommentThread Widget (`widgets/comment_thread.py`)

Organizes a review comment thread:

```
CommentThread Widget
├── Comment widget (main_comment)
├── Replies section (if replies exist)
│   ├── "💬 X replies:"
│   ├── _ReplyPanel → ReplyComment widget (per reply)
│   │   └── Author + date + body (no path/line/diff_hunk)
│   └── ...
└── Action buttons (if options provided)
    └── PromptChoice for user actions
```

### 3. Comment Utilities - Display Logic

#### `comment_utils.py` provides parsing and rendering:

**Key Functions**:

1. **`parse_comment_body(body, diff_hunk, line)`** (line 36)
   - Parses comment body into structured elements:
     - `TextElement` - Plain text (rendered as Markdown)
     - `SuggestionElement` - Code suggestion blocks (rendered as CodeBlock)
     - `CodeBlockElement` - Regular code blocks (rendered as CodeBlock)
   - Handles multiline suggestions with original line extraction

2. **`render_comment_elements(body, diff_hunk, line)`** (line 171)
   - Converts parsed elements to Textual widgets
   - Returns list of widgets ready to be yielded in compose()

3. **`extract_diff_context(diff_hunk, target_line, is_outdated)`** (line 232)
   - Extracts relevant context around commented line
   - Strategy: 4 lines before + target + 3 lines after (total ~7 context lines)
   - Falls back to last 10 lines if target not found
   - For outdated comments: shows last 10 lines or full diff
   - Marks target line with "◄" marker
   - Handles both added (+), removed (-), and context ( ) lines

4. **`_extract_lines_from_diff(diff_hunk, target_line, num_lines)`** (line 123)
   - Extracts multiple consecutive lines for multiline suggestions
   - Parses @@ header to get starting line number
   - Skips diff markers (+, -, space)

### 4. Steps Layer - UI Orchestration

#### A. `respond-pr-comments.yaml` Workflow

```yaml
steps:
  - fetch_pending_comments_step
    └── Fetches:
        • review_threads: List[UICommentThread] from GraphQL review threads
        • general_comments: List[UICommentThread] wrapped from issue comments
        • Stored as single list: all_threads

  - review_comments_step (pr_review_steps.py:691)
    ├── Helper: _show_thread_and_get_action() - Displays individual thread
    │   ├── Mounts CommentThread widget
    │   ├── Shows action buttons
    │   └── Returns user choice: ai_review | change_manually | reply | skip | resolve | exit
    │
    ├── Handler: _handle_ai_review() - Launches AI CLI for code changes
    ├── Handler: _handle_manual_reply() - Asks user for text reply
    ├── Handler: _handle_manual_change() - Detects and commits changes
    └── Handler: _handle_resolve_thread() - Marks thread as resolved (inline only)
```

**Problem**: All logic concentrated in steps. No reusable component.

#### B. `review-pr-iterative.yaml` Workflow

```yaml
steps:
  - fetch_pr_changes()
    └── Fetches:
        • review_changed_files: List[str]
        • review_diff: str (full diff)
        • review_pr: UIPullRequest
        • review_threads: List[UICommentThread] (existing comments for context)

  - ai_review_pr() (code_review_steps.py:387)
    └── Generates:
        • review_suggestions: List[UIReviewSuggestion]
        └── Enriches each suggestion with:
            • file_diff = extract_diff_for_file(diff, suggestion.file_path)
            • hunk = extract_hunk_for_line(file_diff, suggestion.line)
            • suggestion.diff_context = hunk or first 3000 chars of file_diff

  - validate_review_comments() (code_review_steps.py:552)
    ├── Helper: _show_suggestion_and_get_action()
    │   ├── Mounts ReviewSuggestion widget
    │   ├── Shows action buttons
    │   └── Returns: approve | edit | refine | skip | exit
    └── Handles refinement with headless CLI
```

**Architecture difference**: ReviewSuggestion widget is used here, not CommentThread.

## Display Flow - Detailed

### Path 1: Inline Review Comments (has path + line)

```
UICommentThread (thread_id="t-xyz", is_general_comment=False)
  └── main_comment: UIComment
      ├── path: "src/main.py"
      ├── line: 42
      ├── diff_hunk: "@@ -40,7 +40,9 @@\n..."
      └── body: "This logic is wrong"

CommentThread Widget
  └── Comment Widget (comment=main_comment, is_outdated=False)
      ├── Metadata: author + date
      ├── File info: "src/main.py" + "Line 42"
      ├── Code context:
      │   └── extract_diff_context(diff_hunk, line=42)
      │   └── Shows: lines 36-45 (4 before + 42 + 3 after) + marker "◄"
      │   └── CodeBlock renders with syntax highlighting
      └── Body: parsed markdown/code blocks

User sees:
┌─────────────────────────────────────────┐
│ Alice • 25/03/2026 10:30                │
│                                         │
│ src/main.py  Line 42                    │
│                                         │
│  35   if x == 0:                        │
│  36       return None                   │
│  37   ↓ old code                        │
│ -38    result = x / y  ← OLD            │
│ +38    result = divide(x, y)  ◄         │
│  39   else:                             │
│  40       return result                 │
│                                         │
│ This logic is wrong                     │
└─────────────────────────────────────────┘
```

### Path 2: General PR Comments (no path, no line)

**Problem in respond-pr-comments.yaml:**

```
UICommentThread (thread_id="general_101", is_general_comment=True)
  └── main_comment: UIComment
      ├── path: None                     ← NO FILE INFO
      ├── line: None                     ← NO LINE INFO
      ├── diff_hunk: None                ← NO CODE CONTEXT
      └── body: "Need to add more tests"

CommentThread Widget
  └── Comment Widget (comment=main_comment, is_outdated=False)
      ├── Metadata: author + date
      ├── File info: SKIPPED (path is None)
      │   └── ❌ Lost context about which file this applies to
      ├── Code context: SKIPPED (diff_hunk is None)
      │   └── ❌ No visual reference to what code was being discussed
      └── Body: just text
          └── "Need to add more tests"

User sees:
┌─────────────────────────────────────────┐
│ Bob • 25/03/2026 14:00                  │
│                                         │
│ Need to add more tests                  │
└─────────────────────────────────────────┘
  ↑ Lost context!
```

### Path 3: AI Review Suggestions (structured differently)

```
UIReviewSuggestion (from AI)
  ├── file_path: "src/main.py"
  ├── line: 42
  ├── diff_context: "@@ -40,7 +40,9 @@\n..."  ← Enriched by ai_review_pr()
  ├── severity: "critical"
  ├── body: "Potential division by zero..."
  └── snippet: Optional[str]

ReviewSuggestion Widget (code_review_steps.py)
  ├── Severity badge: 🔴 CRITICAL
  ├── File info: "src/main.py" + "Line 42"
  ├── Code context:
  │   └── extract_diff_context(diff_context, line=42)
  │   └── CodeBlock renders diff with syntax highlighting
  └── Body: parsed markdown

User sees:
┌─────────────────────────────────────────┐
│ 🔴 CRITICAL                             │
│                                         │
│ src/main.py  Line 42                    │
│                                         │
│  36   return None                       │
│ -37   result = x / y                    │
│ +37   result = divide(x, y)  ◄          │
│  38   return result                     │
│                                         │
│ Potential division by zero - need check │
└─────────────────────────────────────────┘
```

## Code Fetching & Hunk Extraction - Details

### In `code_review_operations.py`:

**`extract_diff_for_file(full_diff, file_path)`**
- Returns the unified diff for a single file from the full PR diff
- Extracts lines between "diff --git a/FILE b/FILE" markers

**`extract_hunk_for_line(file_diff, line)`**
- Extracts the specific hunk from file_diff that contains the line
- Returns ONE hunk (one @@ ... @@ block) that includes target line
- Used when suggestion has specific line number

**Flow in `ai_review_pr()` (line 446)**:
```python
for suggestion in suggestions:
    file_diff = extract_diff_for_file(diff, suggestion.file_path)
    if file_diff:
        target_line = suggestion.line

        # If snippet but no line, resolve snippet to line
        if suggestion.snippet and not target_line:
            target_line = find_line_by_snippet(file_diff, suggestion.snippet)
            suggestion.line = target_line

        # Extract just the hunk around that line
        hunk = extract_hunk_for_line(file_diff, target_line)
        suggestion.diff_context = hunk or file_diff[:3000]  # Fallback to first 3000 chars
```

**Key difference from respond-pr-comments**:
- respond-pr-comments: Gets diff_hunk from GraphQL (pre-filled)
- review-pr-iterative: Enriches suggestions by extracting hunks from full PR diff

## Identified Issues

### Issue 1: General Comments Missing Context

**Location**: `pr_review_steps.py` - `_show_thread_and_get_action()` → `CommentThread` → `Comment` widget

**Problem**:
- General PR comments have `path=None, line=None, diff_hunk=None`
- Comment widget skips file info and code context display
- User sees only comment text, no reference to what code is being discussed

**Impact**:
- Users can't see what code the general comment relates to
- Makes it hard to understand context when reviewing comments
- Especially problematic for comments like "Need more tests" without context

### Issue 2: Scattered Display Logic

**Locations**:
1. `comment_utils.py` - Core display logic (parse, render, extract context)
2. `code_review_steps.py:_show_suggestion_and_get_action()` - ReviewSuggestion display
3. `pr_review_steps.py:_show_thread_and_get_action()` - CommentThread display
4. `widgets/comment.py` - Comment widget
5. `widgets/review_suggestion.py` - ReviewSuggestion widget
6. `widgets/comment_thread.py` - CommentThread widget

**Problem**:
- Display logic is split between steps, widgets, and utilities
- Can't reuse from one step/widget in another
- If display needs to change, must update in multiple places

### Issue 3: No Reusable Component

**Current**:
- Steps must manually handle displaying code + metadata
- Each workflow step reimplements similar logic
- Hard to ensure consistency between workflows

**Needed**:
- Single component for displaying comments (inline or general) with code context
- Callable from steps, reusable across workflows
- Handles all code extraction/display logic internally

## Proposed Solution Architecture

### New Component: `CodeCommentDisplay` Widget

```python
# widgets/code_comment_display.py

class CodeCommentDisplay(Widget):
    """
    Unified widget for displaying any comment (inline or general) with code context.

    Handles:
    - Metadata (author, date, path, line)
    - Code context extraction and rendering
    - Comment body parsing (markdown, code blocks, suggestions)
    - Both inline and general comments seamlessly
    - Outdated state styling
    """

    def __init__(
        self,
        comment: UIComment,
        diff_hunk: Optional[str] = None,  # Extra diff if needed
        is_outdated: bool = False,
        show_actions: bool = False,
        action_options: Optional[List[ChoiceOption]] = None,
        on_action: Optional[Callable] = None,
    ):
        """
        Initialize comment display.

        Args:
            comment: UIComment with all data
            diff_hunk: Additional diff context (overrides comment.diff_hunk)
            is_outdated: Mark as outdated
            show_actions: Show action buttons
            action_options: Buttons to display
            on_action: Callback for action selection
        """
```

### Benefits:

1. **Unified Display**
   - Same widget for inline and general comments
   - Consistent styling and layout
   - Automatically handles missing path/line

2. **Smart Context Display**
   - Shows file path + line if available
   - Falls back to "General comment" if not
   - Extracts and renders code context intelligently

3. **Reusable**
   - Can be used in any step
   - Mountable directly, or composable in other widgets
   - Handles its own internal flow

4. **Extensible**
   - Optional diff_hunk override for enrichment
   - Callback system for actions
   - Customizable styling

### Usage Examples:

**In respond-pr-comments.py:**
```python
def _show_thread_and_get_action(...):
    # Replace CommentThread widget with CodeCommentDisplay
    display = CodeCommentDisplay(
        comment=pr_thread.main_comment,
        diff_hunk=pr_thread.main_comment.diff_hunk,
        is_outdated=pr_thread.is_outdated,
        show_actions=True,
        action_options=options,
        on_action=on_choice_selected
    )
    ctx.textual.mount(display)
    # ... wait for result
```

**In code_review_steps.py:**
```python
def _show_suggestion_and_get_action(...):
    # Convert ReviewSuggestion to CodeCommentDisplay-based display
    comment = UIComment(
        id=suggestion.id,
        body=suggestion.body,
        author_login="ai",
        author_name="AI Review",
        formatted_date=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        path=suggestion.file_path,
        line=suggestion.line,
        diff_hunk=None  # Use suggestion.diff_context via override
    )

    display = CodeCommentDisplay(
        comment=comment,
        diff_hunk=suggestion.diff_context,
        show_actions=True,
        action_options=options,
        on_action=on_choice_selected
    )
```

## Summary Table

| Component | Location | Purpose | Needs Refactor |
|-----------|----------|---------|---|
| `UIComment` | models/view.py | Data model for single comment | No |
| `UICommentThread` | models/view.py | Thread wrapper + is_general_comment | No |
| `Comment` widget | widgets/comment.py | Display main comment | Yes - migrate to CodeCommentDisplay |
| `ReviewSuggestion` widget | widgets/review_suggestion.py | Display AI suggestion | Partial - share logic with CodeCommentDisplay |
| `CommentThread` widget | widgets/comment_thread.py | Organize thread + replies | Keep, but delegate comment display |
| `comment_utils` | widgets/comment_utils.py | Parsing/rendering utilities | Keep - core utility |
| `_show_thread_and_get_action()` | pr_review_steps.py | Display thread in respond workflow | Simplify with new component |
| `_show_suggestion_and_get_action()` | code_review_steps.py | Display suggestion in review workflow | Simplify with new component |

## Recommendations

### Phase 1: Analysis (Done ✅)
- [x] Understand current architecture
- [x] Identify display logic
- [x] Find inconsistencies

### Phase 2: Create Unified Component
- [ ] Create `CodeCommentDisplay` widget
  - Combines Comment + file context logic
  - Handles both inline and general comments
  - Reuses comment_utils internally

- [ ] Update `CommentThread` widget
  - Use CodeCommentDisplay for main_comment
  - Keep reply rendering as is

- [ ] Update respond-pr-comments steps
  - Replace CommentThread usage with CodeCommentDisplay
  - Simplify _show_thread_and_get_action()

### Phase 3: Unify Review Suggestion Display
- [ ] Refactor ReviewSuggestion widget
  - Consider migrating to CodeCommentDisplay-based approach
  - OR share more logic with CodeCommentDisplay
  - Maintain severity badge as differentiator

### Phase 4: Documentation
- [ ] Document component API
- [ ] Add usage examples
- [ ] Update architecture guide

## Files to Modify

1. **Create**: `plugins/titan-plugin-github/titan_plugin_github/widgets/code_comment_display.py`
2. **Modify**: `widgets/comment_thread.py` - Use CodeCommentDisplay internally
3. **Modify**: `steps/pr_review_steps.py` - Simplify display logic
4. **Modify**: `steps/code_review_steps.py` - Consider refactoring
5. **Keep**: `widgets/comment.py`, `widgets/comment_utils.py` - Utility layer

## Testing Strategy

- Unit tests for CodeCommentDisplay widget
- Integration tests with both workflows
- Visual regression tests for inline vs general comments
- Test with outdated comments
- Test with very large diffs (fallback behavior)
