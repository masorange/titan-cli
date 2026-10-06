"""
The chain every mod hook runs in.

A hook is `hook(m, e, next)`:

- `m` is the mod's own handle on Titan (`ModAPI`),
- `e` is the event's frozen input,
- `next(e)` runs the hooks below it and then Titan's own behaviour, and
  returns that result.

A hook answers on its own by returning without calling `next` (`m.deny(...)`),
rewrites what the rest of the chain sees with `next(replace(e, ...))`, or
observes with `r = next(e)` and acts on `r` before returning it.

A mod is user code, so a hook that raises never takes a workflow down: it is
logged and the chain carries on as if the hook had called `next(e)`, or with
the result `next` already produced if it raised after calling it, so a step
never runs twice.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol

from titan_cli.core.logging import get_logger
from titan_cli.engine.results import Error

from . import store as _store
from .state import ModState
from .store import ModStore

logger = get_logger(__name__)

Next = Callable[[Any], Any]
Hook = Callable[["ModAPI", Any, Next], Any]


class ModHost(Protocol):
    """
    What Titan lends a mod beyond the chain: the TUI provides one. Without it
    (tests, headless runs) `m.ui` only logs, timers never fire and no client
    is reachable.
    """

    def status(self, mod: str, text: Optional[str]) -> None: ...

    def toast(self, mod: str, text: str, severity: str) -> None: ...

    def open_pane(self, mod: str, pane: str, title: str) -> None: ...

    def repaint(self, mod: str) -> None: ...

    def every(self, mod: str, seconds: float, fn: Callable[[], None], immediately: bool) -> None: ...

    def client(self, name: str) -> Any: ...

    def run(self, mod: str, fn: Callable[[], None]) -> None: ...

    def ai(self, mod: str, prompt: str, system: Optional[str], max_tokens: Optional[int],
           model: Optional[str], timeout: int) -> "AIAnswer": ...

    def ai_pinned(self, mod: str) -> Optional[str]: ...

    def ai_configure(self, mod: str, title: str, on_done: Optional[Callable[[], None]]) -> None: ...

    def ai_describe(self, mod: str) -> str: ...


@dataclass(frozen=True)
class AIAnswer:
    """What `m.ai.complete` returns: the text, or why there is none."""

    text: str = ""
    model: Optional[str] = None  # the model that answered, as the routing resolved it
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


class _HeadlessHost:
    def status(self, mod: str, text: Optional[str]) -> None:
        logger.debug("mod_status", mod=mod, text=text)

    def toast(self, mod: str, text: str, severity: str) -> None:
        logger.debug("mod_toast", mod=mod, text=text, severity=severity)

    def open_pane(self, mod: str, pane: str, title: str) -> None:
        logger.debug("mod_pane_opened", mod=mod, pane=pane)

    def repaint(self, mod: str) -> None:
        pass

    def every(self, mod: str, seconds: float, fn: Callable[[], None], immediately: bool) -> None:
        logger.debug("mod_timer_ignored", mod=mod, seconds=seconds)

    def client(self, name: str) -> Any:
        return None

    def run(self, mod: str, fn: Callable[[], None]) -> None:
        logger.debug("mod_run_ignored", mod=mod)

    def ai(self, mod, prompt, system, max_tokens, model, timeout) -> "AIAnswer":
        return AIAnswer(error="AI is not available here")

    def ai_pinned(self, mod: str) -> Optional[str]:
        return None

    def ai_configure(self, mod: str, title: str, on_done: Optional[Callable[[], None]]) -> None:
        logger.debug("mod_ai_configure_ignored", mod=mod)

    def ai_describe(self, mod: str) -> str:
        return "AI not available"


class _ModUI:
    def __init__(self, bus: "ModBus", mod: str):
        self._bus = bus
        self._mod = mod

    def status(self, text: Optional[str]) -> None:
        """Show `text` in this mod's slot of the status bar; `None` clears it."""
        self._bus.host.status(self._mod, text)

    def toast(self, text: str, severity: str = "information") -> None:
        """Show a toast. `severity` is `information`, `warning` or `error`."""
        self._bus.host.toast(self._mod, text, severity)

    def open(self, pane: str, title: str) -> None:
        """Give this mod a pane in the side panel, drawn by its `ui.render` hook for `pane`."""
        self._bus.host.open_pane(self._mod, pane, title)


class _ModClock:
    def __init__(self, bus: "ModBus", mod: str):
        self._bus = bus
        self._mod = mod

    def every(self, seconds: float, fn: Callable[[], None], immediately: bool = True) -> None:
        """
        Run `fn` every `seconds` on a background thread, first right away unless
        `immediately` is False. A run still going when the next is due is not
        doubled; an exception is logged and the timer keeps going.
        """
        self._bus.host.every(self._mod, seconds, fn, immediately)


class _ModAI:
    def __init__(self, bus: "ModBus", mod: str):
        self._bus = bus
        self._mod = mod

    @property
    def task(self) -> str:
        """The routing task this mod's AI calls run under; the user pins it like any other."""
        return f"mods.{self._mod}"

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        timeout: int = 180,
    ) -> AIAnswer:
        """
        One text generation through Titan's AI routing, under `task`: the
        connection or headless CLI and its model are the user's choice (task
        pin, F2/F3 for the session), `model` overriding only the model. Blocks:
        call it from `m.run` or a timer, never from a hook on the UI thread.
        """
        return self._bus.host.ai(self._mod, prompt, system, max_tokens, model, timeout)

    def pinned(self) -> Optional[str]:
        """What this mod's task is pinned to ("remote:<connection>" / "cli:<cli>"), or None when AI routing decides."""
        return self._bus.host.ai_pinned(self._mod)

    def configure(self, title: str, on_done: Optional[Callable[[], None]] = None) -> None:
        """
        Let the person choose who answers this mod's task: the same pickers the AI
        screen opens for any task (remote or CLI, then which one and its model),
        writing the same task pin. `on_done` runs after each saved change, on the UI
        thread: refresh what the pane shows from there. Call it from a button.
        """
        self._bus.host.ai_configure(self._mod, title, on_done)

    def describe(self) -> str:
        """Who would answer right now, e.g. "MasOrange LLM · qwen3-coder". May probe: call off the UI thread."""
        return self._bus.host.ai_describe(self._mod)


class ModAPI:
    """What a mod reaches Titan through."""

    def __init__(self, bus: "ModBus", name: str):
        self.name = name
        self.ui = _ModUI(bus, name)
        self.clock = _ModClock(bus, name)
        self.ai = _ModAI(bus, name)
        self.state = ModState(on_change=lambda: bus.host.repaint(name))
        # Read through the module so tests can point every store elsewhere.
        self.store = ModStore(name, root=lambda: _store.STORE_DIR)
        self.log = logger.bind(mod=name)
        self._bus = bus

    def client(self, name: str) -> Any:
        """
        The client of an installed, enabled plugin (`"git"`, `"github"`, ...),
        or None. Its methods return `ClientResult` exactly as steps see them.
        Calls block on the network: make them from a `clock.every` callback.
        """
        return self._bus.host.client(name)

    def run(self, fn: Callable[[], None]) -> None:
        """Run `fn` once on a background thread, e.g. slow work a button starts. Exceptions are logged."""
        self._bus.host.run(self.name, fn)

    def deny(self, reason: str) -> Error:
        """The answer for a `step.call` hook that refuses the step."""
        return Error(f"Blocked by mod '{self.name}': {reason}")


@dataclass(frozen=True)
class _Registration:
    mod: str
    event: str
    match: Mapping[str, Any]
    hook: Hook


def _matches(match: Mapping[str, Any], e: Any) -> bool:
    return all(getattr(e, key, None) == value for key, value in match.items())


class ModBus:
    """Holds every loaded mod's hooks and runs them as one chain per event."""

    EVENTS = ("app.start", "workflow.run", "step.call", "ui.render")

    def __init__(self) -> None:
        self._hooks: Dict[str, List[_Registration]] = {event: [] for event in self.EVENTS}
        self._apis: Dict[str, ModAPI] = {}
        self.host: ModHost = _HeadlessHost()

    @property
    def mods(self) -> List[str]:
        return list(self._apis)

    def on_for(self, mod: str) -> Callable[..., Callable[[Hook], Hook]]:
        """The `on` a mod's `register` receives: `@on(event, match={...})`."""
        self._apis.setdefault(mod, ModAPI(self, mod))

        def on(event: str, match: Optional[Mapping[str, Any]] = None) -> Callable[[Hook], Hook]:
            if event not in self._hooks:
                raise ValueError(f"Unknown mod event '{event}'. Known: {', '.join(self.EVENTS)}")

            def decorator(hook: Hook) -> Hook:
                self._hooks[event].append(_Registration(mod, event, dict(match or {}), hook))
                return hook

            return decorator

        return on

    def has_hooks(self, event: str) -> bool:
        return bool(self._hooks.get(event))

    def dispatch(self, event: str, e: Any, final: Next) -> Any:
        """Run `e` through the hooks that match it, ending in `final` (Titan's own behaviour)."""
        chain = [r for r in self._hooks.get(event, []) if _matches(r.match, e)]

        def run(index: int, current: Any) -> Any:
            if index == len(chain):
                return final(current)

            registration = chain[index]
            called = False
            downstream: Any = None

            def next_(rewritten: Any = current) -> Any:
                nonlocal called, downstream
                if called:
                    raise RuntimeError("next() may be called only once per hook")
                called = True
                downstream = run(index + 1, rewritten)
                return downstream

            try:
                answer = registration.hook(self._apis[registration.mod], current, next_)
            except Exception:
                logger.exception("mod_hook_failed", mod=registration.mod, mod_event=event)
                return downstream if called else run(index + 1, current)

            if answer is None:
                # A hook that forgot `return next(e)` must not swallow the
                # step's result, nor skip the step.
                if not called:
                    logger.warning("mod_hook_returned_nothing", mod=registration.mod, mod_event=event)
                    return run(index + 1, current)
                return downstream
            return answer

        return run(0, e)
