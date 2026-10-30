"""
The TUI side of mods: where `m.ui`, `m.clock` and `m.client` land.

Hooks run on whichever thread raised the event (a workflow worker, a timer
worker, the app thread), so everything that touches a widget is marshalled
onto the app thread first.
"""
import importlib
import pkgutil
import threading
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Tuple

from rich.markup import escape
from textual.app import App

from titan_cli.core.logging import get_logger
from titan_cli.core.mods import AIAnswer, AssistResult, DockSlot, HomeCardSlot, ModBus, UIRender
from titan_cli.core.mods.keys import key_refusal
from titan_cli.ui.tui.widgets.registry import register_widget, unregister_widget

logger = get_logger(__name__)


class TitanModHost:
    def __init__(self, app: App, bus: ModBus, registry: Any = None):
        from titan_cli.ui.tui.widgets.mod_side_panel import PANEL_WIDTH

        self._app = app
        self._bus = bus
        self._registry = registry
        # mod -> its slot in the dock, in the order the mods first asked for one
        self._dock: Dict[str, DockSlot] = {}
        # mod -> its card on the home screen, in the order the mods first asked for one
        self._home_cards: Dict[str, HomeCardSlot] = {}
        # mod -> the widget names it registered, to take them back when it is unloaded
        self._widgets: Dict[str, List[str]] = {}
        # pane id -> (mod that opened it, title, rail icon), in the order they were opened
        self.panes: Dict[str, Tuple[str, str, str]] = {}
        # pane id -> (text, severity) its mod put under its rail icon
        self.badges: Dict[str, Tuple[str, Optional[str]]] = {}
        # The one pane shown; the rest wait behind their rail icon.
        self.active: Optional[str] = None
        # Closed at start: only the rail shows until the person opens a pane (F4 or a click).
        self.collapsed = True
        # Shared by every screen's panel, so a resize on one holds on all; for this session only.
        self.width = PANEL_WIDTH
        self._repaint_pending = False
        self._lock = threading.Lock()
        self._clients: Dict[str, Any] = {}
        # mod -> the timers it started, to stop them when it is unloaded
        self._timers: Dict[str, List[Any]] = {}
        self._executor = None
        # key -> (mod, description, fn)
        self._keys: Dict[str, Tuple[str, str, Callable[[], None]]] = {}
        self._titan_keys: Optional[Set[str]] = None

    # -- dock and toasts ---------------------------------------------------

    def dock_slots(self) -> List[Tuple[str, DockSlot]]:
        return list(self._dock.items())

    def dock(self, mod: str, slot: Optional[DockSlot]) -> None:
        if slot is not None:
            self._dock[mod] = slot
        else:
            self._dock.pop(mod, None)
        self._on_app_thread(self._paint_dock)

    def widget(self, mod: str, name: str, widget: Any) -> None:
        register_widget(name, widget)
        with self._lock:
            names = self._widgets.setdefault(mod, [])
            if name not in names:
                names.append(name)

    def open_workspace(self, mod: str, name: str, focus: Any = None) -> Optional[str]:
        from titan_cli.ui.tui.screens.workspace_screen import WorkspaceScreen

        bus = getattr(self._app, "workspaces", None)
        config = getattr(self._app, "config", None)
        refusal = None
        if bus is None or name not in bus.views:
            refusal = f"there is no workspace '{name}'"
        elif config is None:
            refusal = "Titan has no configuration loaded"
        if refusal is not None:
            self.toast(mod, f"Cannot open workspace {name}: {refusal}", "warning")
            return refusal
        top = self._app.screen
        if isinstance(top, WorkspaceScreen) and top.workspace == name:
            self._on_app_thread(lambda: bus.opened(name, focus))
            return None  # already there
        title = bus.views[name][0] or name
        logger.info("workspace_opened", mod=mod, workspace=name)

        def push():
            # Its `w.on_open` first, so the first draw already shows what was asked for.
            bus.opened(name, focus)
            self._app.push_screen(WorkspaceScreen(config, name, title))

        self._on_app_thread(push)
        return None

    def press_dock(self, mod: str) -> None:
        """A click on a mod's dock tile: its own action, if it gave one."""
        slot = self._dock.get(mod)
        if slot is None or slot.on_click is None:
            return
        try:
            slot.on_click()
        except Exception:
            logger.exception("mod_dock_click_failed", mod=mod)

    def toast(self, mod: str, text: str, severity: str) -> None:
        # An error is never a toast: it opens the error card, with its copy button.
        if severity == "error":
            self._on_app_thread(lambda: self._app.show_error(text, mod))
            return
        # Escaped: a mod's text is not markup, and a stray `[/x]` would raise.
        self._on_app_thread(
            lambda: self._app.notify(escape(text), title=mod, severity=severity)
        )

    # -- the home screen ---------------------------------------------------

    def home_card_slots(self) -> List[Tuple[str, HomeCardSlot]]:
        return list(self._home_cards.items())

    def home_card(self, mod: str, slot: Optional[HomeCardSlot]) -> None:
        if slot is not None:
            self._home_cards[mod] = slot
        else:
            self._home_cards.pop(mod, None)
        self._on_app_thread(self._paint_home_cards)

    def press_home_card(self, mod: str) -> None:
        """Enter or a click on a mod's home card: its own action, if it gave one."""
        slot = self._home_cards.get(mod)
        if slot is None or slot.on_click is None:
            return
        try:
            slot.on_click()
        except Exception:
            logger.exception("mod_home_card_click_failed", mod=mod)

    def _paint_home_cards(self) -> None:
        from titan_cli.ui.tui.screens.main_menu import MainMenuScreen

        screen = self._app.screen
        if isinstance(screen, MainMenuScreen):
            screen.refresh_mod_cards()

    def copy(self, mod: str, text: str, what: str) -> None:
        from titan_cli.ui.tui.clipboard import copy_with_feedback

        self._on_app_thread(lambda: copy_with_feedback(self._app, text, what))

    def _paint_dock(self) -> None:
        from titan_cli.ui.tui.widgets.dock import Dock

        try:
            dock = self._app.screen.query_one(Dock)
        except Exception:
            return  # this screen has no dock; the next one reads dock_slots() on mount
        dock.refresh_tiles()

    # -- the side panel ---------------------------------------------------

    def pane_snapshot(self) -> Tuple[Dict[str, Tuple[str, str, str]], Dict[str, Tuple[str, Optional[str]]]]:
        """Copies of the panes and badges, safe to iterate while mods change them from other threads."""
        with self._lock:
            return dict(self.panes), dict(self.badges)

    def open_pane(self, mod: str, pane: str, title: str, icon: Optional[str] = None) -> None:
        with self._lock:
            self.panes[pane] = (mod, title, icon or title[:1].upper() or "?")
            if self.active is None:
                self.active = pane
        self.repaint(mod)

    def badge(self, mod: str, pane: str, text: Optional[str], severity: Optional[str]) -> None:
        """A mark under a pane's rail icon; only the mod that opened the pane may set it."""
        with self._lock:
            owner = self.panes.get(pane, (None,))[0]
            if owner == mod:
                if text:
                    self.badges[pane] = (text, severity)
                else:
                    self.badges.pop(pane, None)
        if owner != mod:
            logger.warning("mod_badge_foreign_pane", mod=mod, pane=pane, owner=owner)
            return
        self.repaint(mod)

    def toggle_collapsed(self) -> None:
        self.collapsed = not self.collapsed
        self.repaint("")

    def select(self, pane: str) -> None:
        """A click on a rail icon: show that pane, or fold the panel when it is already showing."""
        if pane not in self.panes:
            return
        if pane == self.active and not self.collapsed:
            self.collapsed = True
        else:
            self.active, self.collapsed = pane, False
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
        if not self._on_app_thread(lambda: self._app.call_later(self._repaint_now)):
            # Dropped call: _repaint_now will never clear the flag.
            with self._lock:
                self._repaint_pending = False

    def _repaint_now(self) -> None:
        from titan_cli.ui.tui.screens.workspace_screen import WorkspaceScreen
        from titan_cli.ui.tui.widgets.mod_side_panel import ModSidePanel

        with self._lock:
            self._repaint_pending = False
        screen = self._app.screen
        if isinstance(screen, WorkspaceScreen):
            screen.refresh_view()
        try:
            panel = screen.query_one(ModSidePanel)
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

    # -- workflows ----------------------------------------------------------

    def run_workflow(self, mod: str, name: str, params: Mapping[str, Any]) -> Optional[str]:
        from titan_cli.ui.tui.screens.workflow_execution import WorkflowExecutionScreen

        config = getattr(self._app, "config", None)
        # What the menu would run for this name: a project workflow extending it
        # takes its place, so a mod button and the menu entry do the same thing.
        resolved = self.resolve_workflow(mod, name) or name
        refusal = None
        if config is None:
            refusal = "Titan has no configuration loaded"
        elif any(isinstance(screen, WorkflowExecutionScreen) for screen in self._app.screen_stack):
            refusal = "another workflow is running; finish it first"
        elif config.workflows.get_workflow(resolved) is None:
            refusal = f"there is no workflow '{name}'"
        if refusal is not None:
            self.toast(mod, f"Cannot run {name}: {refusal}", "warning")
            return refusal
        logger.info("mod_workflow_opened", mod=mod, workflow=resolved, asked=name, params=sorted(params))
        self._on_app_thread(lambda: self._app.push_screen(WorkflowExecutionScreen(config, resolved, params=params)))
        return None

    def resolve_workflow(self, mod: str, name: str) -> Optional[str]:
        """The workflow this Titan runs for `name`, or None when it has none (see `effective_name`)."""
        config = getattr(self._app, "config", None)
        if config is None:
            return None
        try:
            return config.workflows.effective_name(name)
        except Exception:
            logger.warning("mod_workflow_resolve_failed", mod=mod, workflow=name, exc_info=True)
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
            self._timers.setdefault(mod, []).append(self._app.set_interval(seconds, tick))
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

    # -- unloading ------------------------------------------------------------

    def unload(self, mod: str) -> None:
        """Take down everything `mod` put on screen or scheduled; the bus has dropped its hooks."""
        self._on_app_thread(lambda: self._unload(mod))

    def _unload(self, mod: str) -> None:
        for timer in self._timers.pop(mod, []):
            timer.stop()
        try:
            self._app.workers.cancel_group(self._app, f"mod:{mod}")
        except Exception:
            logger.debug("mod_workers_cancel_failed", mod=mod, exc_info=True)
        with self._lock:
            keys = [key for key, (holder, _, _) in self._keys.items() if holder == mod]
            for key in keys:
                del self._keys[key]
        for key in keys:
            # Textual has no public unbind: drop the app's binding so the footer stops listing it.
            try:
                self._app._bindings.key_to_bindings.pop(key, None)
            except Exception:
                logger.debug("mod_key_unbind_failed", mod=mod, key=key, exc_info=True)
        with self._lock:
            for pane in [pane for pane, (owner, _, _) in self.panes.items() if owner == mod]:
                del self.panes[pane]
                self.badges.pop(pane, None)
                if self.active == pane:
                    self.active = next(iter(self.panes), None)
        with self._lock:
            names = self._widgets.pop(mod, [])
        for name in names:
            unregister_widget(name)
        self._dock.pop(mod, None)
        self._paint_dock()
        self._home_cards.pop(mod, None)
        self._paint_home_cards()
        self.repaint(mod)

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

    @staticmethod
    def _assist_policy(mod: str):
        from titan_cli.ai.router import AIProviderType, AIRoutePolicy

        # The help button opens an interactive CLI, which a one-shot `m.ai.complete` could
        # never run: that is why it has a task of its own, and why the task a mod's
        # `complete` calls run under never offers it. Only what the button can drive is
        # offered. A remote or headless pin is refused with a toast: showing its answer would
        # take `ask_ai`, and the button has nowhere to draw it.
        return AIRoutePolicy(
            task=f"mods.{mod}.assist",
            executes=[AIProviderType.CLI_INTERACTIVE],
            preferred=[AIProviderType.CLI_INTERACTIVE],
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
        executor = self._ai_executor()
        if executor is None:
            return []
        rows = []
        workspaces = getattr(self._app, "workspaces", None)
        for bus in (self._bus, workspaces):
            for name, manifest in (bus.manifests.items() if bus is not None else ()):
                ident = bus.prefix + name
                if manifest.ai_task:
                    rows.append(self._task_routing(ident, manifest.ai_task, executor))
                if getattr(manifest, "ai_assist_task", None):
                    rows.append(self._task_routing(ident, manifest.ai_assist_task, executor, assist=True))
        return rows

    def _task_routing(self, mod: str, title: str, executor=None, assist: bool = False):
        """One of this mod's tasks (`mods.<mod>`, or `mods.<mod>.assist`) as the AI screen's task rows see it."""
        from titan_cli.ui.tui.screens.ai_routing import TaskRouting

        executor = executor or self._ai_executor()
        ai_config = self._ai_config()
        prefs = getattr(ai_config, "preferences", None)
        policy = self._assist_policy(mod) if assist else self._policy(mod)
        pin = prefs.tasks.get(policy.task) if prefs is not None else None
        return TaskRouting(
            task=policy.task,
            label=title,
            executes=list(policy.executes),
            resolution=executor.resolve(policy=policy),
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

    def ai_assist(self, mod: str, prompt: str, cwd: Optional[str]) -> AssistResult:
        """Open the interactive AI CLI the person set for this mod's help task, suspending Titan while it runs.

        Resolved under `mods.<mod>.assist`, so it is the CLI and model chosen in AI
        Configuration for that task (or pinned for the session), never one asked for
        here. Runs on the app thread; a refusal is toasted once, here.
        """
        from titan_cli.ai.router import AIProviderType, AIRouteDecision
        from titan_cli.external_cli.configs import CLI_REGISTRY
        from titan_cli.core.utils import find_project_root
        from titan_cli.external_cli.launcher import launcher_for

        refusal: list = []

        def launch() -> None:
            executor = self._ai_executor()
            if executor is None:
                refusal.append("AI is not configured")
                return
            try:
                decision = executor.resolve(policy=self._assist_policy(mod))
            except Exception as e:
                logger.warning("mod_ai_assist_resolve_failed", mod=mod, exc_info=True)
                refusal.append(f"AI routing could not resolve: {e}")
                return
            if not isinstance(decision, AIRouteDecision):
                refusal.append(f"{decision.reason}. Pick a CLI for this task in AI Configuration.")
                return
            if decision.provider == AIProviderType.OFF:
                refusal.append("AI is turned off for this task")
                return
            if decision.provider != AIProviderType.CLI_INTERACTIVE or not decision.cli:
                refusal.append("this task needs an interactive CLI: pick one in AI Configuration")
                return
            name = CLI_REGISTRY.get(decision.cli, {}).get("display_name", decision.cli)
            logger.info("mod_ai_assist", mod=mod, cli=decision.cli)
            with self._app.suspend():
                launcher_for(decision.cli).launch(
                    prompt=prompt,
                    cwd=cwd or str(find_project_root()),
                    model=self._app.model_for_cli(decision.cli),
                )
            self._app.notify(f"Back in Titan from {name}", severity="information")

        if not self._on_app_thread(launch):
            return AssistResult(False, "Titan is closing")
        if refusal:
            self.toast(mod, refusal[0], "warning")
            return AssistResult(False, refusal[0])
        return AssistResult(True)

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
        started = time.monotonic()
        try:
            result = executor.generate_text(
                prompt, policy=policy, system_prompt=system, max_tokens=max_tokens, model=model, timeout=timeout,
            )
        except Exception as e:
            logger.exception("mod_ai_failed", mod=mod)
            return AIAnswer(error=str(e))
        decision = getattr(result, "decision", None)
        decision_model = getattr(decision, "model", None)
        # One line per request, the prompt left out: what a mod asked, of whom, and how it ended.
        provider = getattr(decision, "provider", None)
        who = {"task": policy.task, "provider": getattr(provider, "value", provider), "cli": getattr(decision, "cli", None),
               "model": decision_model or model, "duration": round(time.monotonic() - started, 3)}
        if isinstance(result, AIExecutionSuccess):
            logger.info("mod_ai_answered", mod=mod, chars=len(result.data or ""), **who)
            return AIAnswer(text=result.data, model=decision_model or model)
        logger.warning("mod_ai_refused_or_failed", mod=mod, error_code=getattr(result, "error_code", None),
                       error=(result.error_message or "")[:500], **who)
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

    def _on_app_thread(self, fn: Callable[[], None]) -> bool:
        """Run ``fn`` on the app thread; False when the call was dropped."""
        if getattr(self._app, "_thread_id", None) == threading.get_ident():
            fn()
            return True
        if not self._app.is_running:
            return False
        try:
            self._app.call_from_thread(fn)
        except Exception:
            logger.debug("mod_ui_call_dropped", exc_info=True)
            return False
        return True
