"""
What turns a CLI's bytes into a screen: `Sanitizer` (lets pyte see only what it implements and answers
the queries a program asks a terminal), `TermScreen`/`TermStream` (pyte plus what full-screen programs
rely on), the key and paste encoders, and `render_line` (a screen row as Rich text). Pure: no threads,
no Textual.
"""
from collections import defaultdict, deque
from functools import lru_cache
from typing import List, Optional

import pyte
from pyte.screens import Cursor, Margins
from rich.style import Style
from rich.text import Text as RichText

_KEYS = {
    "enter": "\r", "tab": "\t", "shift+tab": "\x1b[Z", "backspace": "\x7f", "escape": "\x1b",
    "up": "\x1b[A", "down": "\x1b[B", "right": "\x1b[C", "left": "\x1b[D",
    "home": "\x1b[H", "end": "\x1b[F", "pageup": "\x1b[5~", "pagedown": "\x1b[6~",
    "delete": "\x1b[3~", "insert": "\x1b[2~", "space": " ",
}
_COLORS = {"default": None, "brown": "yellow", "brightblack": "bright_black"}
SCROLLBACK_LINES = 2000  # rows kept above the screen; bounds the session's memory
_MOUSE_TRACKING = {1000 << 5, 1002 << 5, 1003 << 5}  # pyte stores private modes shifted by 5 bits
_SGR_MOUSE = 1006 << 5

class TermScreen(pyte.Screen):
    """pyte's screen plus what full-screen programs rely on and it lacks: scroll up/down (`CSI n S/T`),
    repeat (`CSI n b`), save/restore cursor (`CSI s/u`), the alternate screen (`?47/?1047/?1049`) and a
    bounded scrollback (`history`: the rows that left the top of the main screen, oldest first)."""

    def __init__(self, columns: int, lines: int) -> None:
        super().__init__(columns, lines)
        self._last = ""
        self._main: Optional[tuple] = None
        self.history: deque = deque(maxlen=SCROLLBACK_LINES)

    @property
    def alternate(self) -> bool:
        return self._main is not None

    @property
    def mouse_tracking(self) -> bool:
        """Whether the program asked for mouse reports (DECSET 1000/1002/1003)."""
        return bool(_MOUSE_TRACKING & self.mode)

    @property
    def sgr_mouse(self) -> bool:
        return _SGR_MOUSE in self.mode

    def index(self) -> None:
        """A row scrolled off the top of the whole main screen goes to the scrollback."""
        top, bottom = self.margins or Margins(0, self.lines - 1)
        if self.cursor.y == bottom and top == 0 and self._main is None:
            self.history.append(self.buffer[0])
        super().index()

    def erase_in_display(self, how: int = 0, *args, **kwargs) -> None:
        if how == 3:  # ED 3: the program clears the scrollback too
            self.history.clear()
        super().erase_in_display(how, *args, **kwargs)

    def draw(self, data: str) -> None:
        if data:
            self._last = data[-1]
        super().draw(data)

    def repeat(self, count: int = 1, *_: int) -> None:
        if self._last:
            self.draw(self._last * min(max(count or 1, 1), self.columns * self.lines))

    def scroll_up(self, count: int = 1, *_: int) -> None:
        self._scroll(count, up=True)

    def scroll_down(self, count: int = 1, *_: int) -> None:
        self._scroll(count, up=False)

    def _scroll(self, count: int, up: bool) -> None:
        top, bottom = self.margins or Margins(0, self.lines - 1)
        y, self.cursor.y = self.cursor.y, bottom if up else top
        for _ in range(min(max(count or 1, 1), self.lines)):
            self.index() if up else self.reverse_index()
        self.cursor.y = y

    def csi_save_cursor(self, *_: int) -> None:
        self.save_cursor()

    def csi_restore_cursor(self, *_: int) -> None:
        self.restore_cursor()

    def set_mode(self, *modes: int, **kwargs) -> None:
        if kwargs.get("private") and {47, 1047, 1049} & set(modes):
            self._alternate(True)
        super().set_mode(*modes, **kwargs)

    def reset_mode(self, *modes: int, **kwargs) -> None:
        if kwargs.get("private") and {47, 1047, 1049} & set(modes):
            self._alternate(False)
        super().reset_mode(*modes, **kwargs)

    def _alternate(self, on: bool) -> None:
        if on and self._main is None:
            self._main = (self.buffer, self.cursor, self.margins)
            self.buffer = defaultdict(self.buffer.default_factory)
            self.cursor, self.margins = Cursor(0, 0), None
        elif not on and self._main is not None:
            self.buffer, self.cursor, self.margins = self._main
            self._main = None
        self.dirty.update(range(self.lines))


class TermStream(pyte.ByteStream):
    csi = {**pyte.ByteStream.csi, "S": "scroll_up", "T": "scroll_down", "b": "repeat",
           "s": "csi_save_cursor", "u": "csi_restore_cursor"}


_PYTE_FINALS = {ord(final) for final in TermStream.csi}
_FG, _BG = "cccc/cccc/cccc", "0000/0000/0000"  # what an OSC 10/11 query is told: light text on black
_CELL_W, _CELL_H = 8, 16  # a made-up cell size in pixels, for the window-size queries


def _sgr(body: str) -> str:
    """An SGR's parameters reduced to what pyte reads: numbers, `38;5;n`, `38;2;r;g;b`; no sub-parameters."""
    out, items, i = [], body.split(";"), 0
    while i < len(items):
        p = items[i]
        if ":" in p:
            parts = p.split(":")
            if parts[0] in ("38", "48") and len(parts) >= 3 and parts[1] == "2":
                out += [parts[0], "2", *parts[-3:]]
            elif parts[0] in ("38", "48") and len(parts) >= 3 and parts[1] == "5":
                out += [parts[0], "5", parts[2]]
            elif parts[0] == "4":
                out.append("24" if parts[1:2] == ["0"] else "4")
            i += 1
        elif p in ("38", "48", "58"):  # colours consume their arguments; an underline colour is dropped
            mode = items[i + 1] if i + 1 < len(items) else ""
            width = 3 if mode == "5" else 5 if mode == "2" else 1
            if p != "58":
                out += items[i:i + width]
            i += width
        else:
            if p.isdigit() or p == "":
                out.append(p)
            i += 1
    return ";".join(out)


class Sanitizer:
    """
    Lets through to pyte only what it implements, and answers what a CLI asks a terminal.

    A program's output is cut into its escape sequences. Text, the C0 controls, the simple escapes,
    the CSI sequences pyte has a handler for (SGR rewritten to plain numbers) and its private modes
    pass; everything else is dropped: strings (OSC, APC, DCS, PM, SOS: kitty graphics, titles), CSI
    with a prefix (`>`, `<`, `=`) or an intermediate, and finals pyte does not know. A new CLI can
    therefore make the screen miss a feature but never draw garbage or break the parser.

    The queries that sequences carry (version, colours, modes, window size, keyboard protocol) get
    a reply in `take_replies()` so a program that waits for one does not wait for a timeout.
    A sequence split across reads is held back until it is whole.
    """

    def __init__(self) -> None:
        self.rows, self.cols = 24, 80
        self._held = b""
        self._string: Optional[str] = None  # "osc" or "st" while inside a string
        self._osc = b""
        self._replies: List[bytes] = []

    def take_replies(self) -> List[bytes]:
        replies, self._replies = self._replies, []
        return replies

    def feed(self, data: bytes) -> bytes:
        buf, self._held = self._held + data, b""
        out, i, n = bytearray(), 0, len(buf)
        while i < n:
            if self._string:
                i = self._skip_string(buf, i)
                continue
            e = buf.find(b"\x1b", i)
            if e < 0:
                out += buf[i:]
                break
            out += buf[i:e]
            i = self._escape(buf, e, out)
            if i < 0:
                self._held = buf[e:]
                break
        return bytes(out)

    # -- strings --------------------------------------------------------------------------
    def _skip_string(self, buf: bytes, i: int) -> int:
        n = len(buf)
        esc = buf.find(b"\x1b", i)
        bel = buf.find(b"\x07", i) if self._string == "osc" else -1
        if bel >= 0 and (esc < 0 or bel < esc):
            self._collect(buf[i:bel])
            self._end_string(b"\x07")
            return bel + 1
        if esc < 0:
            self._collect(buf[i:])
            return n
        self._collect(buf[i:esc])
        if esc + 1 >= n:
            self._held = b"\x1b"
            return n
        if buf[esc + 1] == 0x5C:  # ESC \ : the string terminator
            self._end_string(b"\x1b\\")
            return esc + 2
        self._end_string(b"")  # an ESC that is not one: the string is over, the escape is read next
        return esc

    def _collect(self, chunk: bytes) -> None:
        if self._string == "osc" and len(self._osc) < 256:
            self._osc += chunk[: 256 - len(self._osc)]

    def _end_string(self, terminator: bytes) -> None:
        if self._string == "osc":
            ps, _, pt = self._osc.partition(b";")
            if pt == b"?" and ps in (b"10", b"11"):
                colour = _FG if ps == b"10" else _BG
                self._replies.append(b"\x1b]" + ps + b";rgb:" + colour.encode() + (terminator or b"\x1b\\"))
        self._string, self._osc = None, b""

    # -- escapes --------------------------------------------------------------------------
    def _escape(self, buf: bytes, e: int, out: bytearray) -> int:
        """Handle the escape at `e`; the index after it, or -1 when it is not complete yet."""
        n = len(buf)
        if e + 1 >= n:
            return -1
        c = buf[e + 1]
        if c == 0x5B:
            return self._csi(buf, e, out)
        if c == 0x5D:
            self._string, self._osc = "osc", b""
            return e + 2
        if c in b"PX^_":
            self._string = "st"
            return e + 2
        if 0x20 <= c <= 0x2F:  # ESC ( B, ESC ) 0, ESC # 8
            j = e + 2
            while j < n and 0x20 <= buf[j] <= 0x2F:
                j += 1
            if j >= n:
                return -1 if n - e < 8 else e + 1
            if c in b"()#" and j == e + 3:
                out += buf[e:j + 1]
            return j + 1
        if 0x30 <= c <= 0x7E:
            out += buf[e:e + 2]
            return e + 2
        return e + 1

    def _csi(self, buf: bytes, e: int, out: bytearray) -> int:
        n, j = len(buf), e + 2
        while j < n and 0x30 <= buf[j] <= 0x3F:
            j += 1
        k = j
        while k < n and 0x20 <= buf[k] <= 0x2F:
            k += 1
        if k >= n:
            return -1 if n - e < 64 else e + 2
        if not 0x40 <= buf[k] <= 0x7E:
            return k  # malformed: dropped whole
        sequence = self._rewrite(buf[e + 2:j].decode("ascii", "ignore"), buf[j:k], buf[k])
        if sequence is not None:
            out += sequence
        return k + 1

    def _rewrite(self, params: str, inter: bytes, final: int) -> Optional[bytes]:
        """The sequence as pyte should get it, None to drop it; replies to queries are queued."""
        prefix = params[:1] if params[:1] in ("?", "<", "=", ">") else ""
        body, f = params[len(prefix):], chr(final)
        if inter:
            if prefix == "?" and inter == b"$" and f == "p":  # DECRQM: mode not recognized
                self._replies.append(f"\x1b[?{body};0$y".encode())
            return None
        if prefix == ">":
            if f == "q":
                self._replies.append(b"\x1bP>|titan\x1b\\")
            elif f == "c":
                self._replies.append(b"\x1b[>0;10;1c")
            return None
        if prefix == "?":
            if f == "u":  # kitty keyboard protocol: none
                self._replies.append(b"\x1b[?0u")
            return f"\x1b[?{body}{f}".encode() if f in "hlJK" else None
        if prefix:
            return None
        if f == "t":
            ask = body.split(";")[0]
            if ask == "18":
                self._replies.append(f"\x1b[8;{self.rows};{self.cols}t".encode())
            elif ask == "14":
                self._replies.append(f"\x1b[4;{self.rows * _CELL_H};{self.cols * _CELL_W}t".encode())
            elif ask == "16":
                self._replies.append(f"\x1b[6;{_CELL_H};{_CELL_W}t".encode())
            return None
        if final not in _PYTE_FINALS:
            return None
        if f == "m":
            body = _sgr(body)
        return f"\x1b[{body}{f}".encode()


def key_bytes(key: str, character: Optional[str]) -> Optional[bytes]:
    """The bytes a terminal sends for a Textual key; None when there are none."""
    if key in _KEYS:
        return _KEYS[key].encode()
    if key.startswith("ctrl+") and len(key) == 6 and key[-1].isalpha():
        return bytes([ord(key[-1]) - 96])
    if character:
        return character.encode()
    return None


def paste_bytes(text: str, bracketed: bool) -> bytes:
    """Pasted text as a terminal sends it: wrapped in bracketed-paste marks when the CLI asked for them."""
    if bracketed:
        return b"\x1b[200~" + text.encode() + b"\x1b[201~"
    return text.replace("\r\n", "\r").replace("\n", "\r").encode()


def _colour(value: str) -> Optional[str]:
    if value in _COLORS:
        return _COLORS[value]
    if len(value) == 6 and all(c in "0123456789abcdefABCDEF" for c in value):
        return f"#{value}"
    return value


@lru_cache(maxsize=512)
def _style(fg: str, bg: str, bold: bool, italics: bool, underscore: bool, reverse: bool) -> Style:
    return Style(color=_colour(fg), bgcolor=_colour(bg), bold=bold, italic=italics,
                 underline=underscore, reverse=reverse)


def wheel_bytes(up: bool, col: int, row: int, sgr: bool) -> bytes:
    """A wheel notch as a mouse report, `col`/`row` 1-based: SGR (`?1006`) or the classic X10 form."""
    button = 64 if up else 65
    if sgr:
        return f"\x1b[<{button};{col};{row}M".encode()
    return b"\x1b[M" + bytes([32 + button, 32 + min(col, 223), 32 + min(row, 223)])


def scrollback_window(history_len: int, lines: int, offset: int) -> range:
    """Which rows of history-then-screen fill the view when scrolled `offset` rows back."""
    end = history_len + lines - offset
    return range(max(end - lines, 0), end)


def render_line(screen: "pyte.Screen", y: int) -> RichText:
    """One screen row as Rich text, runs of equal style joined into one segment."""
    cursor_x = screen.cursor.x if screen.cursor.y == y and not screen.cursor.hidden else None
    return render_row(screen.buffer[y], screen.columns, cursor_x)


def render_row(row, columns: int, cursor_x: Optional[int] = None) -> RichText:
    """A buffer row (of the screen or the scrollback) as Rich text; `cursor_x` is drawn reversed."""
    text = RichText(no_wrap=True, end="")
    run: List[str] = []
    current = None
    for x in range(columns):
        ch = row[x]
        key = (ch.fg, ch.bg, ch.bold, ch.italics, ch.underscore, ch.reverse)
        if x == cursor_x:
            key = (ch.fg, ch.bg, ch.bold, ch.italics, ch.underscore, not ch.reverse)
        if key != current and run:
            text.append("".join(run), _style(*current))
            run = []
        current = key
        if ch.data == "":  # the second cell of a wide character is part of the first
            continue
        run.append(ch.data)
    if run:
        text.append("".join(run), _style(*current))
    return text
