"""
The TUI side of mods: where `m.ui`, `m.clock` and `m.client` land.

Hooks run on whichever thread raised the event (a workflow worker, a timer
worker, the app thread), so everything that touches a widget is marshalled
onto the app thread first.
"""
import importlib
import pkgutil
import threading
from typing import Any, Callable, Dict, Optional, Set, Tuple

from rich.markup import escape
from textual.app import App

from titan_cli.core.logging import get_logger
from titan_cli.core.mods import AIAnswer, ModBus, UIRender
from titan_cli.core.mods.keys import key_refusal

logger = get_logger(__name__)


class TitanModHost:
    def __init__(self, app: App, bus: ModBus, registry: Any = None):
        self._app = app
        self._bus = bus
        self._registry = registry
        self._statuses: Dict[str, str] = {}
        # pane id -> (mod that opened it, title), in the order they were opened
        self.panes: Dict[str, Tuple[str, str]] = {}
        self.collapsed = False
        self._repaint_pending = False
        self._lock = threading.Lock()
        self._clients: Dict[str, Any] = {}
        self._executor = None
        # key -> (mod, description, fn)
        self._keys: Dict[str, Tuple[str, str, Callable[[], None]]] = {}
        self._titan_keys: Optional[Set[str]] = None

    # -- status bar and toasts -------------------------------------------

    def status_text(self) -> str:
        return "  ·  ".join(self._statuses.values())

    def status(self, mod: str, text: Optional[str]) -> None:
        if text:
            self._statuses[mod] = text
        else:
            self._statuses.pop(mod, None)
        self._on_app_thread(self._paint_status)

    def toast(self, mod: str, text: str, severity: str) -> None:
        # Escaped: a mod's text is not markup, and a stray `[/x]` would raise.
        self._on_app_thread(
            lambda: self._app.notify(escape(text), title=mod, severity=severity)
        )

    def copy(self, mod: str, text: str, what: str) -> None:
        from titan_cli.ui.tui.clipboard import copy_with_feedback

        self._on_app_thread(lambda: copy_with_feedback(self._app, text, what))

    def _paint_status(self) -> None:
        from titan_cli.ui.tui.widgets.status_bar import StatusBarWidget

        try:
            bar = self._app.screen.query_one("#status-bar", StatusBarWidget)
        except Exception:
            return  # this screen has no bar; the next one reads status_text()
        bar.mods_info = self.status_text()

    # -- the side panel ---------------------------------------------------

    def open_pane(self, mod: str, pane: str, title: str) -> None:
        self.panes[pane] = (mod, title)
        self.repaint(mod)

    def toggle_collapsed(self) -> None:
        self.collapsed = not self.collapsed
        self.repaint("")

    def render(self, pane: str, width: int) -> Any:
        """Ask the mods for the tree of one pane; None when no hook answers."""
        return self._bus.dispatch("ui.render", UIRender(component="Pane", pane=pane, width=width), lambda e: None)

    def repaint(self, mod: str) -> None:
        # State changes come in bursts (three refreshes landing together):
        # one repaint covers them all.
        with self._lock:
            if self._repaint_pending:
                return
            self._repaint_pending = True
        self._on_app_thread(lambda: self._app.call_later(self._repaint_now))

    def _repaint_now(self) -> None:
        from titan_cli.ui.tui.widgets.mod_side_panel import ModSidePanel

        with self._lock:
            self._repaint_pending = False
        try:
            panel = self._app.screen.query_one(ModSidePanel)
        except Exception:
            return  # this screen has no panel; the next one paints on mount
        panel.refresh_panes()

    # -- keys ---------------------------------------------------------------

    def bind_key(self, mod: str, key: str, description: str, fn: Callable[[], None]) -> Optional[str]:
        from textual.binding import Binding

        if key and "," not in key:
            # Textual's own spelling, the one titan_keys() holds: "?" -> "question_mark".
            key = next(iter(Binding.make_bindings([Binding(key, "")]))).key
        with self._lock:
            mod_keys = {k: holder for k, (holder, _, _) in self._keys.items()}
            refusal = key_refusal(key, self.titan_keys(), mod_keys, mod)
            if refusal is not None:
                return refusal
            self._keys[key] = (mod, description, fn)

        def bind() -> None:
            self._app.bind(key, f"mod_key({key!r})", description=description, show=True)

        if getattr(self._app, "is_running", True):
            self._on_app_thread(bind)
        else:
            bind()  # from a mod's register(), before the app runs: nothing else touches it yet
        return None

    def press_key(self, key: str) -> None:
        """Run the mod function bound to `key` (the app's `mod_key` action lands here)."""
        entry = self._keys.get(key)
        if entry is None:
            return
        mod, _, fn = entry
        try:
            fn()
        except Exception:
            logger.exception("mod_key_failed", mod=mod, key=key)

    def titan_keys(self) -> Set[str]:
        """Every key Titan itself binds: the app's, and every screen's and widget's in titan_cli.ui.tui."""
        if self._titan_keys is None:
            from textual.binding import Binding
            from textual.dom import DOMNode

            import titan_cli.ui.tui as tui

            # Screens and widgets are imported lazily across the TUI: import them
            # all so none of their bindings is missed.
            for info in pkgutil.walk_packages(tui.__path__, tui.__name__ + "."):
                try:
                    importlib.import_module(info.name)
                except Exception:
                    logger.debug("mod_keys_import_skipped", module=info.name, exc_info=True)

            def subclasses(cls):
                for sub in cls.__subclasses__():
                    yield sub
                    yield from subclasses(sub)

            owners = [c for c in type(self._app).__mro__ if "BINDINGS" in vars(c)]
            owners += [c for c in subclasses(DOMNode) if c.__module__.startswith("titan_cli.")]
            keys: Set[str] = set()
            for owner in owners:
                for binding in Binding.make_bindings(vars(owner).get("BINDINGS", [])):
                    keys.add(binding.key)
            self._titan_keys = keys
        return self._titan_keys

    # -- timers and clients ----------------------------------------------

    def every(self, mod: str, seconds: float, fn: Callable[[], None], immediately: bool) -> None:
        running = threading.Event()

        def work() -> None:
            try:
                fn()
            except Exception:
                logger.exception("mod_timer_failed", mod=mod)
            finally:
                running.clear()

        def tick() -> None:
            # A refresh slower than its interval must not pile up behind itself.
            if running.is_set() or not self._app.is_running:
                return
            running.set()
            self._app.run_worker(work, thread=True, group=f"mod:{mod}", exit_on_error=False)

        def start() -> None:
            self._app.set_interval(seconds, tick)
            if immediately:
                tick()

        self._on_app_thread(start)

    def client(self, name: str) -> Any:
        # Cached once found: is_available() can be a network round-trip
        # (github runs `gh auth status`), and timers ask on every tick.
        if name in self._clients:
            return self._clients[name]
        if self._registry is None:
            return None
        try:
            plugin = self._registry.ensure_initialized(name)
            if plugin is None or not plugin.is_available():
                return None
            client = plugin.get_client()
        except Exception:
            logger.warning("mod_client_unavailable", plugin=name, exc_info=True)
            return None
        self._clients[name] = client
        return client

    def run(self, mod: str, fn: Callable[[], None]) -> None:
        def work() -> None:
            try:
                fn()
            except Exception:
                logger.exception("mod_run_failed", mod=mod)

        self._on_app_thread(lambda: self._app.run_worker(work, thread=True, group=f"mod:{mod}", exit_on_error=False))

    # -- AI -------------------------------------------------------------------

    @staticmethod
    def _policy(mod: str):
        from titan_cli.ai.router import AIProviderType, AIRoutePolicy

        # A mod can run a remote connection or a headless CLI; it never drives an
        # interactive session, so that type is not offered for its task.
        return AIRoutePolicy(
            task=f"mods.{mod}",
            executes=[AIProviderType.REMOTE, AIProviderType.CLI_HEADLESS],
            preferred=[AIProviderType.REMOTE, AIProviderType.CLI_HEADLESS],
        )

    def _ai_config(self):
        return getattr(getattr(getattr(self._app, "config", None), "config", None), "ai", None)

    def ai_pinned(self, mod: str) -> Optional[str]:
        ai_config = self._ai_config()
        prefs = getattr(ai_config, "preferences", None)
        pin = prefs.tasks.get(f"mods.{mod}") if prefs is not None else None
        if pin is None:
            return None
        if pin.provider == "remote":
            return f"remote:{pin.connection or ai_config.default_connection}"
        return f"cli:{pin.cli or ai_config.default_cli}"

    def ai_routings(self) -> list:
        """A task row for every loaded mod whose manifest declares `ai_task`, for the AI screen."""
        return [
            self._task_routing(name, manifest.ai_task)
            for name, manifest in self._bus.manifests.items()
            if manifest.ai_task
        ]

    def _task_routing(self, mod: str, title: str):
        """This mod's task as the AI screen's task rows see one."""
        from titan_cli.ui.tui.screens.ai_routing import TaskRouting

        ai_config = self._ai_config()
        prefs = getattr(ai_config, "preferences", None)
        pin = prefs.tasks.get(f"mods.{mod}") if prefs is not None else None
        policy = self._policy(mod)
        return TaskRouting(
            task=policy.task,
            label=title,
            executes=list(policy.executes),
            resolution=self._ai_executor().resolve(policy=policy),
            has_preference=pin is not None,
            pinned_cli=pin.cli if pin else None,
            pinned_connection=pin.connection if pin else None,
            pinned_model=pin.model if pin else None,
            mod=mod,
        )

    def ai_configure(self, mod: str, title: str, on_done: Optional[Callable[[], None]]) -> None:
        """Remote or CLI first, then which one and its model: the AI screen's own two steps."""
        from titan_cli.ai.router.availability import AIAvailabilityChecker
        from titan_cli.core.security import create_broker_factory
        from titan_cli.ui.tui.screens.task_ai_picker import pick_task_provider, pin_task_instance

        config = getattr(self._app, "config", None)
        if config is None or self._ai_executor() is None:
            self.toast(mod, "AI is not configured", "warning")
            return

        def saved(notice: str) -> None:
            self._app.notify(notice, severity="information")
            if on_done is not None:
                on_done()

        def provider_saved(notice: str) -> None:
            saved(notice)
            # Rebuilt: the instance step offers what the kind just chosen resolves to.
            # A fresh checker, as the AI screen does, so a CLI installed since is seen.
            availability = AIAvailabilityChecker(
                self._ai_config(), create_broker_factory().for_plugin("core")
            )
            pin_task_instance(self._app, config, self._task_routing(mod, title), availability, saved)

        self._on_app_thread(
            lambda: pick_task_provider(self._app, config, self._task_routing(mod, title), provider_saved)
        )

    def ai_describe(self, mod: str) -> str:
        from titan_cli.ai.router import AIRouteNeedsInput

        executor = self._ai_executor()
        if executor is None:
            return "AI not configured"
        try:
            decision = executor.resolve(policy=self._policy(mod))
        except Exception:
            logger.warning("mod_ai_describe_failed", mod=mod, exc_info=True)
            return "AI routing could not resolve"
        if isinstance(decision, AIRouteNeedsInput):
            return "nothing available"
        if decision.provider == "off":
            return "turned off"
        if decision.connection_id:
            cfg = self._ai_config().connections.get(decision.connection_id)
            who = getattr(cfg, "name", None) or decision.connection_id
        else:
            from titan_cli.external_cli.configs import CLI_REGISTRY

            who = CLI_REGISTRY.get(decision.cli, {}).get("display_name") or decision.cli
            who = who if who.endswith("CLI") else f"{who} CLI"
        return f"{who} · {decision.model or 'default'}"

    def ai(self, mod, prompt, system, max_tokens, model, timeout) -> AIAnswer:
        from titan_cli.ai.router import AIExecutionSuccess

        executor = self._ai_executor()
        if executor is None:
            return AIAnswer(error="AI is not configured")
        policy = self._policy(mod)
        try:
            result = executor.generate_text(
                prompt, policy=policy, system_prompt=system, max_tokens=max_tokens, model=model, timeout=timeout,
            )
        except Exception as e:
            logger.exception("mod_ai_failed", mod=mod)
            return AIAnswer(error=str(e))
        decision_model = getattr(getattr(result, "decision", None), "model", None)
        if isinstance(result, AIExecutionSuccess):
            return AIAnswer(text=result.data, model=decision_model or model)
        return AIAnswer(error=result.error_message, model=decision_model or model)

    def _ai_executor(self):
        # Rebuilt whenever the AI config object changes: TitanConfig.load() replaces
        # it on every screen transition, and an executor kept from before would go on
        # resolving with the old one - blind to a task pin saved since, the picker's
        # included.
        with self._lock:
            ai_config = self._ai_config()
            if ai_config is None:
                return None
            if self._executor is None or self._executor.ai_config is not ai_config:
                from titan_cli.ai.router import AIExecutor
                from titan_cli.core.security import create_ai_provider, create_broker_factory

                self._executor = AIExecutor(
                    ai_config,
                    provider_factory=create_ai_provider,
                    secret_broker=create_broker_factory().for_plugin("core"),
                    session_override=getattr(self._app, "ai_session_override", None),
                )
            return self._executor

    # -- threading ----------------------------------------------------------

    def _on_app_thread(self, fn: Callable[[], None]) -> None:
        if getattr(self._app, "_thread_id", None) == threading.get_ident():
            fn()
            return
        if not self._app.is_running:
            return
        try:
            self._app.call_from_thread(fn)
        except Exception:
            logger.debug("mod_ui_call_dropped", exc_info=True)
