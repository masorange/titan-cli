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
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence

from titan_cli.core.logging import get_logger
from titan_cli.engine.results import Error

from . import store as _store
from .events import SectionChange
from .keys import normalize_key
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

    def dock(self, mod: str, slot: Optional["DockSlot"]) -> None: ...

    def home_card(self, mod: str, slot: Optional["HomeCardSlot"]) -> None: ...

    def toast(self, mod: str, text: str, severity: str) -> None: ...

    def copy(self, mod: str, text: str, what: str) -> None: ...

    def open_pane(self, mod: str, pane: str, title: str, icon: Optional[str]) -> None: ...

    def badge(self, mod: str, pane: str, text: Optional[str], severity: Optional[str]) -> None: ...

    def repaint(self, mod: str) -> None: ...

    def every(self, mod: str, seconds: float, fn: Callable[[], None], immediately: bool) -> None: ...

    def client(self, name: str) -> Any: ...

    def run(self, mod: str, fn: Callable[[], None]) -> None: ...

    def ai(self, mod: str, prompt: str, system: Optional[str], max_tokens: Optional[int],
           model: Optional[str], timeout: int) -> "AIAnswer": ...

    def ai_pinned(self, mod: str) -> Optional[str]: ...

    def ai_configure(self, mod: str, title: str, on_done: Optional[Callable[[], None]]) -> None: ...

    def ai_describe(self, mod: str) -> str: ...

    def ai_assist(self, mod: str, prompt: str, cwd: Optional[str]) -> "AssistResult": ...

    def bind_key(self, mod: str, key: str, description: str, fn: Callable[[], None]) -> Optional[str]: ...

    def run_workflow(self, mod: str, name: str, params: Mapping[str, Any]) -> Optional[str]: ...

    def resolve_workflow(self, mod: str, name: str) -> Optional[str]: ...

    def unload(self, mod: str) -> None:
        """Drop everything `mod` put on screen or scheduled: timers, keys, panes, badges, its dock tile, its home card."""
        ...


@dataclass(frozen=True)
class DockSlot:
    """
    What a mod shows in its slot of the dock: a short label behind its icon,
    and an optional badge (a count, a mark) coloured by `severity`.
    """

    label: str
    icon: Optional[str] = None
    badge: Optional[str] = None
    severity: Optional[str] = None  # a semantic color name, as in elements.Text
    on_click: Optional[Callable[[], None]] = None


@dataclass(frozen=True)
class HomeCardSlot:
    """
    What a mod shows as its own card on the home screen, beside the quick-launch
    workflows: its `mod.toml` icon, a short `title` and a `text` body under it.
    A click or Enter runs `on_click`, if given - an independent slot from the
    dock tile and the side panel pane: a mod may fill any mix of the three,
    with different content in each.
    """

    title: str
    text: str = ""
    icon: Optional[str] = None
    on_click: Optional[Callable[[], None]] = None


@dataclass(frozen=True)
class AIAnswer:
    """What `m.ai.complete` returns: the text, or why there is none."""

    text: str = ""
    model: Optional[str] = None  # the model that answered, as the routing resolved it
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class AssistResult:
    """What `m.ai.assist` returns: that the CLI opened, or why it did not."""

    opened: bool
    reason: Optional[str] = None


class _HeadlessHost:
    def dock(self, mod: str, slot: Optional[DockSlot]) -> None:
        logger.debug("mod_dock", mod=mod, has_slot=slot is not None)

    def home_card(self, mod: str, slot: Optional["HomeCardSlot"]) -> None:
        logger.debug("mod_home_card", mod=mod, has_card=slot is not None)

    def toast(self, mod: str, text: str, severity: str) -> None:
        logger.debug("mod_toast", mod=mod, length=len(text), severity=severity)

    def copy(self, mod: str, text: str, what: str) -> None:
        logger.debug("mod_copy_ignored", mod=mod, what=what)

    def open_pane(self, mod: str, pane: str, title: str, icon: Optional[str]) -> None:
        logger.debug("mod_pane_opened", mod=mod, pane=pane)

    def badge(self, mod: str, pane: str, text: Optional[str], severity: Optional[str]) -> None:
        logger.debug("mod_badge", mod=mod, pane=pane, has_badge=text is not None)

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

    def ai_assist(self, mod: str, prompt: str, cwd: Optional[str]) -> AssistResult:
        return AssistResult(False, "no AI CLI in headless mode")

    def ai_describe(self, mod: str) -> str:
        return "AI not available"

    def bind_key(self, mod: str, key: str, description: str, fn: Callable[[], None]) -> Optional[str]:
        return "there are no keys here"

    def run_workflow(self, mod: str, name: str, params: Mapping[str, Any]) -> Optional[str]:
        return "there is no screen to run it on"

    def resolve_workflow(self, mod: str, name: str) -> Optional[str]:
        return None

    def unload(self, mod: str) -> None:
        pass


class _BusView:
    """
    The bus as one `ModAPI` sees it. Once that API's mod is unloaded its `host` is the
    headless one, so a thread the mod left running can no longer open panes, bind keys,
    start timers or toast: whatever it still does goes nowhere.
    """

    def __init__(self, bus: "ModBus", alive: Callable[[], bool]):
        self._bus = bus
        self._alive = alive
        self._stale = _HeadlessHost()

    @property
    def host(self) -> Any:
        return self._bus.host if self._alive() else self._stale

    @property
    def manifests(self) -> Dict[str, Any]:
        return self._bus.manifests


class _ModUI:
    def __init__(self, bus: "ModBus", mod: str):
        self._bus = bus
        self._mod = mod

    def dock(
        self,
        label: Optional[str],
        badge: Optional[str] = None,
        severity: Optional[str] = None,
        on_click: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Show this mod in the dock at the bottom of every screen: its `mod.toml`
        `icon`, `label`, and an optional `badge` coloured by `severity`
        (`success`, `warning`, `error`, ...). A click runs `on_click` on the UI
        thread; without one the tile only informs. `None` as label removes it.
        """
        if not label:
            self._bus.host.dock(self._mod, None)
            return
        manifest = self._bus.manifests.get(self._mod)
        icon = manifest.icon if manifest else None
        self._bus.host.dock(self._mod, DockSlot(label, icon, badge, severity, on_click))

    def home_card(
        self,
        title: Optional[str],
        text: str = "",
        on_click: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Show this mod as a card on the home screen, beside the quick-launch
        workflows: its `mod.toml` `icon`, `title` and `text` below it. A click or
        Enter runs `on_click`, if given. `None` as title removes it.

        Independent from `dock` and `open`: nothing requires the same content in
        the three, so a mod free to use any of them can show something different
        in each (e.g. a count on the dock, detail in the pane, a different
        summary and action here).
        """
        if not title:
            self._bus.host.home_card(self._mod, None)
            return
        manifest = self._bus.manifests.get(self._mod)
        icon = manifest.icon if manifest else None
        self._bus.host.home_card(self._mod, HomeCardSlot(title, text, icon, on_click))

    def toast(self, text: str, severity: str = "information") -> None:
        """Show a toast. `severity` is `information`, `warning` or `error`."""
        self._bus.host.toast(self._mod, text, severity)

    def copy(self, text: str, what: str = "text") -> None:
        """Put `text` on the clipboard, as Titan's own copy buttons do, and say so naming it `what`."""
        self._bus.host.copy(self._mod, text, what)

    def open(self, pane: str, title: str) -> None:
        """
        Give this mod a pane in the side panel, drawn by its `ui.render` hook for `pane`.

        The panel's rail shows the `icon` of the mod's `mod.toml` for it (the
        title's initial when it has none), and clicking it shows this pane.
        """
        manifest = self._bus.manifests.get(self._mod)
        self._bus.host.open_pane(self._mod, pane, title, manifest.icon if manifest else None)

    def badge(self, pane: str, text: Optional[str], severity: Optional[str] = None) -> None:
        """
        Put `text` under this mod's `pane` icon on the rail, coloured by `severity`;
        `None` takes it off. It is what still shows with the panel folded (F4), so
        keep it to a count or a mark: the rail has room for three characters.
        """
        self._bus.host.badge(self._mod, pane, text, severity)


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

    def assist(self, prompt: str, cwd: Optional[str] = None) -> AssistResult:
        """
        Help with `prompt` through the task `mods.<name>.assist`, the one the user pins in
        AI Configuration like any other (remote or CLI, then which one and its model).
        When it resolves to an interactive CLI, Titan suspends, opens it in `cwd` or the
        project with `prompt` already typed, and takes the terminal back when it exits.
        Use it for "help me fix this": an error, a failing check. Call it from a button or
        a key, on the UI thread. The result says whether it opened; when not, the host has
        already toasted why (AI off, no CLI installed, a task that is not interactive), so
        the mod only reads `reason` if it wants to react.
        """
        result = self._bus.host.ai_assist(self._mod, prompt, cwd)
        if not result.opened:
            logger.warning("mod_ai_assist_refused", mod=self._mod, reason=result.reason)
        return result

    def describe(self) -> str:
        """Who would answer right now, e.g. "MasOrange LLM · qwen3-coder". May probe: call off the UI thread."""
        return self._bus.host.ai_describe(self._mod)


class _ModKeys:
    def __init__(self, bus: "ModBus", mod: str):
        self._bus = bus
        self._mod = mod

    def bind(self, key: str, description: str, fn: Callable[[], None]) -> bool:
        """
        Make `key` (Textual's spelling: `"f5"`, `"ctrl+k"`) run `fn` on every
        screen, listed in the footer as `description`. Refused, with a warning
        in the log, when Titan or another mod already uses the key: the return
        says whether it was bound. `fn` runs on the UI thread: hand slow work
        to `m.run`.
        """
        refusal = self._bus.host.bind_key(self._mod, normalize_key(key), description, fn)
        if refusal is not None:
            logger.warning("mod_key_refused", mod=self._mod, key=key, reason=refusal)
            return False
        return True


class _ModWorkflows:
    def __init__(self, bus: "ModBus", mod: str):
        self._bus = bus
        self._mod = mod

    def run(self, name: str, params: Optional[Mapping[str, Any]] = None) -> bool:
        """
        Open the workflow `name` on its execution screen, as if the person had
        picked it, with `params` over its own params (so a step that reads them
        skips asking, e.g. `review_pr_number` for `review-pr`). A project
        workflow extending `name` under another name runs in its place, exactly
        as the menu would. Refused, with a toast, while another workflow runs:
        the return says whether it opened. Call it from a button or a key.
        """
        refusal = self._bus.host.run_workflow(self._mod, name, dict(params or {}))
        if refusal is not None:
            logger.warning("mod_workflow_refused", mod=self._mod, workflow=name, reason=refusal)
            return False
        return True

    def resolve(self, name: str) -> Optional[str]:
        """
        The workflow `run(name)` would open - `name`, or the one extending it
        under another name - or None when this Titan has none. Draw a button
        that runs a workflow only when this says there is one.
        """
        return self._bus.host.resolve_workflow(self._mod, name)


class ModAPI:
    """What a mod reaches Titan through."""

    def __init__(self, bus: "ModBus", name: str):
        self.name = name
        # False once the mod is unloaded: nothing it still holds reaches Titan any more.
        self.alive = True
        view = _BusView(bus, lambda: self.alive)
        self.ui = _ModUI(view, name)
        self.clock = _ModClock(view, name)
        self.ai = _ModAI(view, name)
        self.keys = _ModKeys(view, name)
        self.workflows = _ModWorkflows(view, name)
        self.state = ModState(on_change=lambda: view.host.repaint(name))
        # Read through the module so tests can point every store elsewhere.
        self.store = ModStore(name, root=lambda: _store.STORE_DIR)
        self.log = logger.bind(mod=name)
        self._bus = view

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

    EVENTS = ("app.start", "workflow.run", "step.call", "ui.render", "section.change")

    def __init__(self) -> None:
        self._hooks: Dict[str, List[_Registration]] = {event: [] for event in self.EVENTS}
        self._apis: Dict[str, ModAPI] = {}
        # name -> ModManifest of every mod that loaded (filled by the loader)
        self.manifests: Dict[str, Any] = {}
        # name -> ModStatus of every mod found, loaded or not (filled by the loader)
        self.statuses: Dict[str, Any] = {}
        # name -> the live {section: bool} dict the mod holds as options["sections"]
        self.sections: Dict[str, Dict[str, bool]] = {}
        # name -> ModManifest of every mod found, loaded or not (filled by the loader)
        self.found: Dict[str, Any] = {}
        # Names of the enabled plugins, to check `requires_plugins` against; None = not known.
        self.enabled_plugins: Optional[frozenset] = None
        self.host: ModHost = _HeadlessHost()
        # The `app.start` the TUI dispatched, to replay for a mod loaded afterwards.
        self.started: Optional[Any] = None

    @property
    def mods(self) -> List[str]:
        return list(self._apis)

    def api(self, mod: str) -> ModAPI:
        """The `m` every hook of `mod` receives; tests drive a mod's state and drawing through it."""
        return self._apis.setdefault(mod, ModAPI(self, mod))

    def on_for(self, mod: str, events: Optional[Sequence[str]] = None) -> Callable[..., Callable[[Hook], Hook]]:
        """
        The `on` a mod's `register` receives: `@on(event, match={...})`.

        `events` are the ones its `mod.toml` declares: hooking any other raises,
        so the manifest Titan shows without running the mod is all it can hook.
        `None` (a bus built by hand, as tests do) allows every event.
        """
        self.api(mod)

        def on(event: str, match: Optional[Mapping[str, Any]] = None) -> Callable[[Hook], Hook]:
            if event not in self._hooks:
                raise ValueError(f"Unknown mod event '{event}'. Known: {', '.join(self.EVENTS)}")
            if events is not None and event not in events:
                raise ValueError(f"Mod '{mod}' hooks '{event}', which its mod.toml `events` does not declare")

            def decorator(hook: Hook) -> Hook:
                self._hooks[event].append(_Registration(mod, event, dict(match or {}), hook))
                return hook

            return decorator

        return on

    def forget(self, mod: str) -> None:
        """Drop every hook `mod` registered and its handle, as if it never loaded."""
        for event, registrations in self._hooks.items():
            self._hooks[event] = [r for r in registrations if r.mod != mod]
        api = self._apis.pop(mod, None)
        if api is not None:
            api.alive = False
        self.manifests.pop(mod, None)
        self.sections.pop(mod, None)

    def unload(self, mod: str) -> None:
        """`forget` plus what the mod left on the host: timers, keys, panes, badges, its dock tile."""
        self.forget(mod)
        unload = getattr(self.host, "unload", None)
        if unload is not None:
            unload(mod)

    def has_hooks(self, event: str) -> bool:
        return bool(self._hooks.get(event))

    def set_section(self, mod: str, section: str, enabled: bool) -> bool:
        """
        Switch one of a loaded mod's sections now: updates the dict the mod reads as
        `options["sections"]`, tells the mod's `section.change` hooks and repaints it.
        Returns False when the mod is not loaded or has no such section.
        """
        switches = self.sections.get(mod)
        if switches is None or section not in switches:
            return False
        switches[section] = enabled
        self.dispatch("section.change", SectionChange(section, enabled), lambda e: None, mod=mod)
        self.host.repaint(mod)
        return True

    def dispatch(self, event: str, e: Any, final: Next, mod: Optional[str] = None) -> Any:
        """
        Run `e` through the hooks that match it, ending in `final` (Titan's own behaviour).
        With `mod`, only that mod's hooks take part.
        """
        if event == "app.start" and mod is None:
            self.started = e
        chain = [r for r in self._hooks.get(event, []) if _matches(r.match, e) and (mod is None or r.mod == mod)]

        def run(index: int, current: Any) -> Any:
            if index == len(chain):
                return final(current)

            registration = chain[index]
            called = False
            downstream: Any = None
            downstream_error: Optional[Exception] = None

            def next_(rewritten: Any = current) -> Any:
                nonlocal called, downstream, downstream_error
                if called:
                    raise RuntimeError("next() may be called only once per hook")
                called = True
                try:
                    downstream = run(index + 1, rewritten)
                except Exception as exc:
                    downstream_error = exc
                    raise
                return downstream

            try:
                answer = registration.hook(self._apis[registration.mod], current, next_)
            except Exception as exc:
                if downstream_error is not None and exc is downstream_error:
                    # Titan's own behaviour (or a lower hook) failed, not this
                    # hook: keep the caller's error semantics.
                    raise
                logger.exception("mod_hook_failed", mod=registration.mod, mod_event=event)
                if downstream_error is not None:
                    # The hook caught the downstream failure and raised another
                    # one: `downstream` is None, so returning it would turn a
                    # failed step into a silent success.
                    raise downstream_error from None
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
