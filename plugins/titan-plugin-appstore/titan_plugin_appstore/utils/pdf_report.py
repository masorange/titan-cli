"""
Reusable PDF report builder for App Store Connect workflows.

Wraps fpdf2 with a declarative block API so operations only describe *what*
to render. All FPDF2 details are encapsulated here.

Install dependency:
    pipx inject titan-cli fpdf2
"""

import re
from datetime import datetime
from pathlib import Path


# ── Colour palette ────────────────────────────────────────────────────────────
_C_BLACK      = (30, 30, 30)
_C_WHITE      = (255, 255, 255)
_C_ACCENT     = (99, 102, 241)    # indigo — headers / section bars
_C_SUCCESS    = (34, 197, 94)     # green
_C_WARNING    = (234, 179, 8)     # yellow
_C_ERROR      = (239, 68, 68)     # red
_C_MUTED      = (120, 120, 120)
_C_ROW_ALT    = (245, 245, 250)
_C_TABLE_HEAD = (50, 50, 80)


class PdfReport:
    """
    Declarative PDF builder.

    Usage:
        path = (
            PdfReport()
            .header("My Report", "subtitle text")
            .section("Section One")
            .stats_row([("Key", "Value"), ("Another", "42")])
            .table(["#", "Name", "Count"], rows, title="Results")
            .page_break()
            .markdown(ai_text)
            .save(output_dir, "my-report")
        )
    """

    def __init__(self):
        from fpdf import FPDF
        self._pdf = FPDF()
        self._pdf.set_auto_page_break(auto=True, margin=20)
        self._pdf.add_page()

    # ── Public API ────────────────────────────────────────────────────────────

    def header(self, title: str, subtitle: str = "") -> "PdfReport":
        """Full-width accent header bar with title and optional subtitle."""
        pdf = self._pdf
        pdf.set_fill_color(*_C_ACCENT)
        pdf.set_text_color(*_C_WHITE)
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 12, _safe(title), new_x="LMARGIN", new_y="NEXT", fill=True, align="C")

        if subtitle:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_fill_color(220, 220, 240)
            pdf.set_text_color(*_C_BLACK)
            pdf.cell(0, 7, _safe(subtitle), new_x="LMARGIN", new_y="NEXT", fill=True, align="C")

        pdf.ln(6)
        return self

    def section(self, title: str) -> "PdfReport":
        """Dark full-width bar used as a section/subsection heading."""
        pdf = self._pdf
        pdf.set_fill_color(*_C_BLACK)
        pdf.set_text_color(*_C_WHITE)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, f"  {_safe(title)}", new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(3)
        return self

    def stats_row(self, items: list[tuple[str, str]], highlight_last: bool = False, highlight_color: tuple = _C_ERROR) -> "PdfReport":
        """
        Horizontal key/value pairs on one line.

        Args:
            items: List of (label, value) pairs.
            highlight_last: If True, render the last value in highlight_color.
            highlight_color: RGB tuple for the highlighted value.
        """
        pdf = self._pdf
        for i, (label, value) in enumerate(items):
            is_last = i == len(items) - 1
            pdf.set_text_color(*_C_MUTED)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(len(label) * 2.2 + 4, 6, _safe(f"{label}:"))
            color = highlight_color if (highlight_last and is_last) else _C_BLACK
            pdf.set_text_color(*color)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(len(str(value)) * 2.2 + 8, 6, _safe(str(value)))
        pdf.ln()
        pdf.ln(4)
        return self

    def table(
        self,
        headers: list[str],
        rows: list[list],
        title: str = "",
        col_widths: list[float] | None = None,
    ) -> "PdfReport":
        """
        Render a table with a header row and alternating row colours.

        Args:
            headers: Column header labels.
            rows: List of rows; each cell is a string.
            title: Optional bold label printed above the table.
            col_widths: Optional explicit column widths in mm. If None,
                        distributes evenly across available width.
        """
        pdf = self._pdf

        if title:
            pdf.set_text_color(*_C_BLACK)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 7, _safe(title), new_x="LMARGIN", new_y="NEXT")

        if not rows:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*_C_MUTED)
            pdf.cell(0, 6, "  None", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            return self

        widths = col_widths or _auto_col_widths(len(headers), pdf.epw)

        # Header row
        pdf.set_fill_color(*_C_TABLE_HEAD)
        pdf.set_text_color(*_C_WHITE)
        pdf.set_font("Helvetica", "B", 8)
        for header, w in zip(headers, widths):
            pdf.cell(w, 6, _safe(header), border=0, fill=True)
        pdf.ln()

        # Data rows
        pdf.set_font("Helvetica", "", 8)
        for i, row in enumerate(rows, 1):
            fill = i % 2 == 0
            pdf.set_fill_color(*_C_ROW_ALT)
            pdf.set_text_color(*_C_BLACK)
            for value, w in zip(row, widths):
                text = _safe(str(value))
                while pdf.get_string_width(text) > w - 2 and len(text) > 4:
                    text = text[:-4] + "..."
                pdf.cell(w, 5, text, border=0, fill=fill)
            pdf.ln()

        pdf.ln(3)
        return self

    def text(self, content: str, muted: bool = False) -> "PdfReport":
        """Plain paragraph text."""
        pdf = self._pdf
        pdf.set_text_color(*(_C_MUTED if muted else _C_BLACK))
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, _safe(content), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        return self

    def markdown(self, text: str) -> "PdfReport":
        """Render basic markdown (headers, bold, lists, horizontal rules)."""
        for line in text.splitlines():
            _render_md_line(self._pdf, line)
        return self

    def page_break(self) -> "PdfReport":
        """Insert a page break."""
        self._pdf.add_page()
        return self

    def save(self, output_dir: str, filename_stem: str) -> str:
        """
        Write the PDF to disk and return the absolute path.

        Args:
            output_dir: Directory to save into.
            filename_stem: Base name without extension or timestamp.
                           Final filename: {stem}-{YYYYMMDD_HHMM}.pdf
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{filename_stem}-{timestamp}.pdf"
        path = str(Path(output_dir) / filename)
        self._pdf.output(path)
        return path


# ── Internal helpers ──────────────────────────────────────────────────────────

def _auto_col_widths(n_cols: int, available: float) -> list[float]:
    """Distribute available width evenly across columns."""
    w = available / n_cols
    return [w] * n_cols


_UNICODE_REPLACEMENTS = str.maketrans({
    "\u2014": "-", "\u2013": "-",
    "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"',
    "\u2026": "...", "\u00b7": ".", "\u2022": "-",
})


def _safe(text: str) -> str:
    """Make text safe for Helvetica (Latin-1 only)."""
    text = text.translate(_UNICODE_REPLACEMENTS)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _strip_md(text: str) -> str:
    """Strip bold/italic/code markdown markers."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text


def _render_md_line(pdf, line: str) -> None:
    """Render one markdown line with basic formatting."""
    stripped = line.strip()

    if stripped.startswith("### "):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*_C_ACCENT)
        pdf.multi_cell(0, 6, _safe(stripped[4:]), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_C_BLACK)
    elif stripped.startswith("## "):
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*_C_ACCENT)
        pdf.multi_cell(0, 7, _safe(stripped[3:]), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_C_BLACK)
    elif stripped.startswith("# "):
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*_C_ACCENT)
        pdf.multi_cell(0, 8, _safe(stripped[2:]), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_C_BLACK)
    elif stripped in ("---", "***", "___"):
        pdf.set_draw_color(*_C_MUTED)
        pdf.set_line_width(0.3)
        pdf.line(pdf.get_x(), pdf.get_y() + 2, pdf.get_x() + pdf.epw, pdf.get_y() + 2)
        pdf.ln(5)
    elif stripped.startswith(("- ", "* ")):
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_C_BLACK)
        pdf.multi_cell(0, 5, f"  - {_safe(_strip_md(stripped[2:]))}", new_x="LMARGIN", new_y="NEXT")
    elif re.match(r"^\d+\.\s", stripped):
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_C_BLACK)
        num = re.match(r"^(\d+)\.", stripped).group(1)
        clean = _safe(_strip_md(re.sub(r"^\d+\.\s+", "", stripped)))
        pdf.multi_cell(0, 5, f"  {num}. {clean}", new_x="LMARGIN", new_y="NEXT")
    elif stripped == "":
        pdf.ln(3)
    else:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_C_BLACK)
        pdf.multi_cell(0, 5, _safe(_strip_md(stripped)), new_x="LMARGIN", new_y="NEXT")
