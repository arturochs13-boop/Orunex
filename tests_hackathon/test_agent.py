"""Unit tests for the Muse Spark hackathon agent (no network, no device)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("META_API_KEY", "test-key")

from bridges.vscode_bridge import PatchError, VSCodeBridge  # noqa: E402
from _orunex_libs import artifact_studio, bmd_expert, bmd_knowledge, office_expert  # noqa: E402
from core.config import Settings  # noqa: E402
from core.faiss_memory import FAISSMemory  # noqa: E402
from core.meta_api import MetaAPIClient, MetaNotConfigured, parse_json_object  # noqa: E402
from core.trade_intent import is_explicit_entry_request  # noqa: E402
from tasks.bugfix_task import AndroidBugfixTask, BugfixRequest  # noqa: E402
from tasks.trading_task import PaperTradingEngine, TradingRequest, TradingTask  # noqa: E402
from tasks.tradingview_gui import (  # noqa: E402
    GuiAgentResult,
    TradingViewGuiAgent,
    _norm_coord,
    _safe_keys,
    _safe_text,
)


def make_settings(root: Path, **overrides) -> Settings:
    values = dict(
        meta_api_key="test-key",
        meta_model="muse-spark",
        workspace_root=root,
        android_project_dir=root / "android",
        memory_index_path=root / "data" / "memory.index",
        paper_state_path=root / "data" / "paper.json",
        android_package="com.orunex.mobile",
    )
    values.update(overrides)
    return Settings(**values)


class FakeResponse:
    status_code = 200

    def __init__(self, data=None):
        self._data = data or {
            "choices": [{"message": {"content": "hola desde muse"}}]
        }

    def json(self):
        return self._data


class FakeSession:
    def __init__(self):
        self.payload = None

    def post(self, url, headers=None, json=None, timeout=None):
        self.payload = json
        return FakeResponse()


class ScriptedSession:
    """Returns scripted responses and records every request payload."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.payloads.append(dict(json or {}))
        if not self.responses:
            raise AssertionError("unexpected extra Meta request")
        return self.responses.pop(0)


class MetaApiTests(unittest.TestCase):
    def test_parse_json_object_from_fenced_reply(self):
        self.assertEqual(parse_json_object('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(parse_json_object('texto {"a": 2} fin'), {"a": 2})

    def test_rejects_non_muse_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp), meta_model="gpt-example")
            with self.assertRaises(MetaNotConfigured):
                MetaAPIClient(settings)

    def test_chat_uses_muse_spark(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = FakeSession()
            client = MetaAPIClient(make_settings(Path(tmp)), session=session)
            text = client.chat([{"role": "user", "content": "hola"}])
            self.assertEqual(text, "hola desde muse")
            self.assertEqual(session.payload["model"], "muse-spark")

    def test_chat_uses_wonder_budget_and_high_effort(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = FakeSession()
            settings = make_settings(
                Path(tmp),
                meta_model="muse-wonder-1.0",
                meta_max_tokens=16384,
                meta_reasoning_effort="high",
            )
            client = MetaAPIClient(settings, session=session)
            client.chat([{"role": "user", "content": "razona"}])
            self.assertEqual(session.payload["model"], "muse-wonder-1.0")
            self.assertEqual(session.payload["max_tokens"], 16384)
            self.assertEqual(session.payload["reasoning_effort"], "high")

    def test_per_call_fast_model_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = FakeSession()
            settings = make_settings(
                Path(tmp),
                meta_model="muse-wonder-1.0",
                meta_max_tokens=16384,
                meta_reasoning_effort="high",
                meta_fast_model="muse-spark-1.3",
                meta_fast_max_tokens=2048,
                meta_fast_reasoning_effort="low",
            )
            client = MetaAPIClient(settings, session=session)
            client.chat(
                [{"role": "user", "content": "clasifica"}],
                model=settings.meta_fast_model,
                max_tokens=settings.meta_fast_max_tokens,
                reasoning_effort=settings.meta_fast_reasoning_effort,
            )
            self.assertEqual(session.payload["model"], "muse-spark-1.3")
            self.assertEqual(session.payload["max_tokens"], 2048)
            self.assertEqual(session.payload["reasoning_effort"], "low")

    def test_truncated_retry_keeps_requested_effort(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = ScriptedSession(
                [
                    FakeResponse(
                        {
                            "choices": [
                                {
                                    "message": {"content": "partial answer"},
                                    "finish_reason": "length",
                                }
                            ]
                        }
                    ),
                    FakeResponse(
                        {
                            "choices": [
                                {
                                    "message": {"content": "complete answer"},
                                    "finish_reason": "stop",
                                }
                            ]
                        }
                    ),
                ]
            )
            settings = make_settings(
                Path(tmp),
                meta_model="muse-wonder-1.0",
                meta_max_tokens=4096,
                meta_reasoning_effort="high",
            )
            client = MetaAPIClient(settings, session=session)
            text = client.chat(
                [{"role": "user", "content": "razona"}],
                max_tokens=2048,
                retries=2,
            )
            self.assertEqual(text, "complete answer")
            self.assertEqual(len(session.payloads), 2)
            self.assertEqual(session.payloads[0]["max_tokens"], 2048)
            self.assertEqual(session.payloads[0]["reasoning_effort"], "high")
            self.assertEqual(session.payloads[1]["max_tokens"], 4096)
            self.assertEqual(session.payloads[1]["reasoning_effort"], "high")


class CerebroOutputTests(unittest.TestCase):
    def test_reasoning_cleanup_preserves_markdown_and_drops_action_tags(self):
        from agents.cerebro import clean_reasoning_output

        cleaned = clean_reasoning_output(
            "**HOLD** porque el setup no alcanza.\n"
            "[GUI_NAVIGATE: https://example.com]\n"
            "La invalidación es perder 82.300."
        )
        self.assertIn("**HOLD**", cleaned)
        self.assertNotIn("GUI_NAVIGATE", cleaned)
        self.assertIn("invalidación", cleaned)


class FaissAndPatchTests(unittest.TestCase):
    def test_index_and_find_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "MainActivity.kt"
            source.write_text(
                "class LoginButton {\n fun render() { Text(\"Entar\") }\n}\n",
                encoding="utf-8",
            )
            settings = make_settings(root)
            memory = FAISSMemory(settings=settings)
            self.assertGreaterEqual(memory.index_codebase(root), 1)
            hits = memory.find_code_candidates("LoginButton broken label Entar", top_k=3)
            self.assertTrue(hits)
            self.assertEqual(hits[0]["metadata"]["path"], "MainActivity.kt")

    def test_patch_guardrails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "MainActivity.kt"
            source.write_text('Text("Entar")\n', encoding="utf-8")
            bridge = VSCodeBridge(make_settings(root))
            dry = bridge.apply_patch(
                "MainActivity.kt",
                [{"search": 'Text("Entar")', "replace": 'Text("Entrar")'}],
                dry_run=True,
            )
            self.assertFalse(dry.applied)
            self.assertEqual(source.read_text(encoding="utf-8"), 'Text("Entar")\n')
            applied = bridge.apply_patch(
                "MainActivity.kt",
                [{"search": 'Text("Entar")', "replace": 'Text("Entrar")'}],
            )
            self.assertTrue(applied.applied)
            self.assertTrue(applied.backup_path and applied.backup_path.exists())
            self.assertIn("Entrar", source.read_text(encoding="utf-8"))
            with self.assertRaises(PatchError):
                bridge.apply_patch(
                    "MainActivity.kt",
                    [{"search": "no-existe", "replace": "x"}],
                )
            with self.assertRaises(PatchError):
                bridge.resolve_source_file("../outside.py")


class FakeMeta:
    """Muse stand-in returning scripted structured decisions."""

    def __init__(self):
        self.verify_calls = 0

    def analyze_image(self, image, prompt, system=""):
        return {
            "has_error": True, "severity": "medium", "screen": "Login",
            "component": "LoginButton", "visible_text": ["Entar"],
            "suspected_cause": "Typo in the login button label",
            "search_query": "LoginButton Entar login label",
            "confidence": 0.95,
        }

    def reason_json(self, *, system, user, schema_hint, images=None, max_tokens=None):
        if "replacements" in schema_hint:
            return {
                "file": "MainActivity.kt", "line_hint": 2,
                "rationale": "Fix the visible typo",
                "replacements": [
                    {"search": 'Text("Entar")', "replace": 'Text("Entrar")'}
                ],
                "confidence": 0.95,
            }
        self.verify_calls += 1
        return {"fixed": True, "still_visible_error": "", "confidence": 0.9, "notes": "ok"}


class FakeGuiAgent:
    """Deterministic stand-in for the native TradingView cursor executor."""

    def __init__(self, result: GuiAgentResult | None = None):
        self.calls: list[dict] = []
        self.result = result or GuiAgentResult(
            ok=True,
            status="confirmed",
            submitted=True,
            confirmed=True,
            paper_verified=True,
            ready=True,
            reference="FAKE-UI",
            fill_price=100.0,
        )

    def place_order(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class FakeADB:
    def __init__(self):
        self.restarted = False

    def screencap(self, save_to=None):
        return b"\x89PNG\r\n\x1a\nfake"

    def current_focus(self):
        return "com.orunex.mobile/.MainActivity"

    def ui_hierarchy(self):
        return "<node text='Entar'/>"

    def recent_errors(self):
        return ""

    def restart_app(self, package=None):
        self.restarted = True


class BugfixTaskTests(unittest.TestCase):
    def test_end_to_end_patch_and_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "MainActivity.kt").write_text(
                'class LoginButton {\n fun render() { Text("Entar") }\n}\n',
                encoding="utf-8",
            )
            settings = make_settings(root)
            memory = FAISSMemory(settings=settings)
            adb = FakeADB()
            vscode = VSCodeBridge(settings)
            vscode.open_in_vscode = lambda path, line=1: True  # never spawn an editor in tests
            task = AndroidBugfixTask(
                meta=FakeMeta(), memory=memory, adb=adb,
                vscode=vscode, settings=settings,
            )
            result = task.run(BugfixRequest(auto_apply=True, rebuild=False))
            self.assertEqual(result.state.value, "completed", result.error)
            self.assertIn("Entrar", (root / "MainActivity.kt").read_text(encoding="utf-8"))
            self.assertTrue(adb.restarted)


class PaperTradingTests(unittest.TestCase):
    def test_position_sizing_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = PaperTradingEngine(make_settings(Path(tmp)))
            order = engine.execute({
                "action": "BUY", "symbol": "BTCUSDT", "entry": 100,
                "stop_loss": 90, "take_profit": 120, "rationale": "test",
            })
            # $100 risk budget / $10 per unit = 10 units.
            self.assertEqual(order.quantity, 10)
            self.assertTrue(order.order_id.startswith("PAPER-"))
            with self.assertRaises(ValueError):
                engine.execute({
                    "action": "BUY", "symbol": "X", "entry": 100,
                    "stop_loss": 110, "take_profit": 120,
                })
            engine.kill_switch = True
            with self.assertRaises(RuntimeError):
                engine.execute({
                    "action": "BUY", "symbol": "X", "entry": 100,
                    "stop_loss": 90, "take_profit": 120,
                })

    def test_trading_task_opens_paper_order_and_notifies(self):
        class TradeMeta:
            def reason_json(self, **kwargs):
                return {
                    "action": "BUY", "symbol": "BTCUSDT", "entry": 100,
                    "stop_loss": 95, "take_profit": 110, "confidence": 0.9,
                    "rationale": "Trend confirmed", "strategy_refs": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = make_settings(root)
            memory = FAISSMemory(settings=settings)
            memory.remember("strategy", "BTC trend following with tight stops")
            notes: list[str] = []
            task = TradingTask(
                meta=TradeMeta(), memory=memory,
                engine=PaperTradingEngine(settings), settings=settings,
                notifier=notes.append,
            )
            result = task.run(TradingRequest(raw='{"symbol":"BTCUSDT","price":100}'))
            self.assertEqual(result.state.value, "completed", result.error)
            self.assertIn("PAPER ORDER CONFIRMED", result.summary)
            self.assertTrue(notes and "PAPER ORDER CONFIRMED" in notes[0])

    def test_explicit_order_uses_explicit_threshold(self):
        class TradeMeta:
            def reason_json(self, **kwargs):
                return {
                    "action": "BUY", "symbol": "BTCUSDT", "entry": 100,
                    "stop_loss": 95, "take_profit": 110, "confidence": 0.62,
                    "rationale": "Valid paper setup", "strategy_refs": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = make_settings(
                root,
                min_trade_confidence=0.70,
                explicit_trade_min_confidence=0.60,
            )
            engine = PaperTradingEngine(settings)
            task = TradingTask(
                meta=TradeMeta(), memory=FAISSMemory(settings=settings),
                engine=engine, settings=settings,
                gui_agent=FakeGuiAgent(),
            )
            alert = {
                "symbol": "BTCUSDT",
                "execute": True,
                "note": (
                    "Delegated order: execute the best paper entry. "
                    "Paper only, no real broker."
                ),
            }
            result = task.run(TradingRequest(raw=json.dumps(alert)))
            self.assertEqual(result.state.value, "completed", result.error)
            self.assertIn("PAPER ORDER CONFIRMED", result.summary)
            self.assertTrue(result.data.get("explicit_execution"))
            self.assertAlmostEqual(result.data.get("confidence_threshold"), 0.60)
            self.assertEqual(len(engine.snapshot()["open_orders"]), 1)

    def test_analysis_below_autonomous_threshold_does_not_trade(self):
        class TradeMeta:
            def reason_json(self, **kwargs):
                return {
                    "action": "BUY", "symbol": "BTCUSDT", "entry": 100,
                    "stop_loss": 95, "take_profit": 110, "confidence": 0.62,
                    "rationale": "Valid but not autonomous-grade", "strategy_refs": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = make_settings(
                root,
                min_trade_confidence=0.70,
                explicit_trade_min_confidence=0.60,
            )
            engine = PaperTradingEngine(settings)
            task = TradingTask(
                meta=TradeMeta(), memory=FAISSMemory(settings=settings),
                engine=engine, settings=settings,
            )
            alert = {
                "symbol": "BTCUSDT",
                "execute": False,
                "note": "Delegated analysis: propose a paper setup. Paper only.",
            }
            result = task.run(TradingRequest(raw=json.dumps(alert)))
            self.assertEqual(result.state.value, "rejected", result.error)
            self.assertIn("autonomous threshold 0.70", result.summary)
            self.assertFalse(result.data.get("explicit_execution"))
            self.assertEqual(engine.snapshot()["open_orders"], [])

    def test_explicit_order_still_rejects_weak_confidence(self):
        class TradeMeta:
            def reason_json(self, **kwargs):
                return {
                    "action": "BUY", "symbol": "BTCUSDT", "entry": 100,
                    "stop_loss": 95, "take_profit": 110, "confidence": 0.55,
                    "rationale": "Weak setup", "strategy_refs": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = make_settings(
                root,
                min_trade_confidence=0.70,
                explicit_trade_min_confidence=0.60,
            )
            engine = PaperTradingEngine(settings)
            task = TradingTask(
                meta=TradeMeta(), memory=FAISSMemory(settings=settings),
                engine=engine, settings=settings,
            )
            alert = {
                "symbol": "BTCUSDT",
                "execute": True,
                "note": "Delegated order: execute the best paper entry.",
            }
            result = task.run(TradingRequest(raw=json.dumps(alert)))
            self.assertEqual(result.state.value, "rejected", result.error)
            self.assertIn("explicit-order threshold 0.60", result.summary)
            self.assertEqual(engine.snapshot()["open_orders"], [])

    def test_natural_language_entry_phrases_are_explicit(self):
        for phrase in (
            "abre TradingView y haz una entrada",
            "haz una entrada",
            "abre una orden paper",
            "toma posición",
            "compra BTCUSDT",
            "vende ETHUSDT",
            "ejecuta la entrada",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(is_explicit_entry_request(phrase))
        for phrase in (
            "abre TradingView",
            "analiza BTCUSDT",
            "haz un análisis para una entrada",
            "¿debo comprar BTCUSDT?",
            "¿qué opinas de una entrada en BTC?",
        ):
            with self.subTest(phrase=phrase):
                self.assertFalse(is_explicit_entry_request(phrase))

    def test_explicit_order_retries_hold_and_enters(self):
        class RetryTradeMeta:
            def __init__(self):
                self.calls = []

            def reason_json(self, **kwargs):
                self.calls.append(kwargs)
                if len(self.calls) == 1:
                    return {
                        "action": "HOLD", "symbol": "BTCUSDT", "entry": 0,
                        "stop_loss": 0, "take_profit": 0, "confidence": 0.35,
                        "rationale": "Hesitant first answer",
                        "strategy_refs": [],
                    }
                return {
                    "action": "BUY", "symbol": "BTCUSDT", "entry": 100,
                    "stop_loss": 95, "take_profit": 110, "confidence": 0.72,
                    "rationale": "Valid paper setup", "strategy_refs": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = make_settings(
                root,
                min_trade_confidence=0.70,
                explicit_trade_min_confidence=0.60,
            )
            meta = RetryTradeMeta()
            engine = PaperTradingEngine(settings)
            task = TradingTask(
                meta=meta, memory=FAISSMemory(settings=settings),
                engine=engine, settings=settings,
                gui_agent=FakeGuiAgent(),
            )
            alert = {
                "symbol": "BTCUSDT",
                "execute": True,
                "note": "Delegated order: the user explicitly ordered a paper entry.",
            }
            result = task.run(TradingRequest(raw=json.dumps(alert)))
            self.assertEqual(result.state.value, "completed", result.error)
            self.assertIn("PAPER ORDER CONFIRMED", result.summary)
            self.assertEqual(len(meta.calls), 2)
            self.assertNotIn("HOLD", meta.calls[1]["schema_hint"])
            self.assertIn("HOLD and REJECT are not available", meta.calls[1]["system"])
            self.assertTrue(result.data.get("force_entry"))
            self.assertEqual(len(engine.snapshot()["open_orders"]), 1)

    def test_explicit_order_never_reports_hold_after_retries(self):
        class HoldTradeMeta:
            def __init__(self):
                self.calls = 0

            def reason_json(self, **kwargs):
                self.calls += 1
                return {
                    "action": "HOLD", "symbol": "BTCUSDT", "entry": 0,
                    "stop_loss": 0, "take_profit": 0, "confidence": 0.4,
                    "rationale": "No setup", "strategy_refs": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = make_settings(
                root,
                min_trade_confidence=0.70,
                explicit_trade_min_confidence=0.60,
                explicit_trade_decision_attempts=3,
            )
            meta = HoldTradeMeta()
            engine = PaperTradingEngine(settings)
            task = TradingTask(
                meta=meta, memory=FAISSMemory(settings=settings),
                engine=engine, settings=settings,
            )
            alert = {
                "symbol": "BTCUSDT",
                "execute": True,
                "note": "Delegated order: the user explicitly ordered a paper entry.",
            }
            result = task.run(TradingRequest(raw=json.dumps(alert)))
            self.assertEqual(result.state.value, "rejected", result.error)
            self.assertEqual(meta.calls, 3)
            self.assertNotIn("Muse decided HOLD", result.summary)
            self.assertIn("no pudo validar una entrada", result.summary)
            self.assertEqual(engine.snapshot()["open_orders"], [])

    def test_analysis_request_can_still_hold(self):
        class HoldTradeMeta:
            def __init__(self):
                self.calls = 0

            def reason_json(self, **kwargs):
                self.calls += 1
                return {
                    "action": "HOLD", "symbol": "BTCUSDT", "entry": 0,
                    "stop_loss": 0, "take_profit": 0, "confidence": 0.35,
                    "rationale": "No coherent setup", "strategy_refs": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = make_settings(root)
            meta = HoldTradeMeta()
            engine = PaperTradingEngine(settings)
            task = TradingTask(
                meta=meta, memory=FAISSMemory(settings=settings),
                engine=engine, settings=settings,
            )
            alert = {
                "symbol": "BTCUSDT",
                "execute": False,
                "note": "Delegated analysis: propose a paper setup. Paper only.",
            }
            result = task.run(TradingRequest(raw=json.dumps(alert)))
            self.assertEqual(result.state.value, "completed", result.error)
            self.assertEqual(meta.calls, 1)
            self.assertIn("Muse decided HOLD", result.summary)
            self.assertFalse(result.data.get("explicit_execution"))


class TradingViewGuiTests(unittest.TestCase):
    """The GUI loop must act through the agent cursor and guard paper-only."""

    @staticmethod
    def _action(action, **overrides):
        payload = {
            "observation": "TradingView order ticket is visible",
            "ui_state": "ticket",
            "paper_trading_visible": True,
            "paper_text": "Paper Trading",
            "symbol": "ETHUSDT",
            "selected_side": "SELL",
            "order_type": "market",
            "price_value": "100",
            "units_value": "1",
            "take_profit_enabled": True,
            "take_profit_value": "110",
            "stop_loss_enabled": True,
            "stop_loss_value": "95",
            "submit_text": "Sell 1 ETHUSDT MARKET",
            "ad_visible": False,
            "ready_to_submit": True,
            "confidence": 0.95,
            "thought": "",
            "action": action,
            "x": 0.5,
            "y": 0.5,
        }
        payload.update(overrides)
        return payload

    class _Meta:
        def __init__(self, actions, *, submit_ok=True, confirm_ok=True):
            self.actions = list(actions)
            self.submit_ok = submit_ok
            self.confirm_ok = confirm_ok
            self.calls = []

        def reason_json(self, *, system, user, schema_hint, images=None, **kwargs):
            self.calls.append({"user": user, "schema": schema_hint})
            if "safe_to_submit" in schema_hint:
                return {
                    "paper_trading_visible": self.submit_ok,
                    "paper_text": "Paper Trading" if self.submit_ok else "",
                    "symbol": "ETHUSDT",
                    "side": "SELL",
                    "order_type": "MARKET",
                    "price_value": "100",
                    "units": "1",
                    "take_profit_enabled": True,
                    "take_profit": "110",
                    "stop_loss_enabled": True,
                    "stop_loss": "95",
                    "submit_text": "Sell 1 ETHUSDT MARKET",
                    "safe_to_submit": self.submit_ok,
                    "reason": "" if self.submit_ok else "paper panel not visible",
                    "confidence": 0.95,
                }
            if "position_visible" in schema_hint:
                return {
                    "paper_trading_visible": self.confirm_ok,
                    "submitted": self.confirm_ok,
                    "position_visible": self.confirm_ok,
                    "symbol": "ETHUSDT",
                    "side": "SELL",
                    "units": "1",
                    "evidence": "position row visible",
                    "confidence": 0.95,
                }
            if not self.actions:
                raise AssertionError("unexpected GUI action request")
            return self.actions.pop(0)

    class _Input:
        def __init__(self):
            self.actions = []

        def attach_window(self, window):
            return True

        def maximize(self):
            return {"ok": True}

        def focus(self):
            return True

        def click(self, x, y, **kwargs):
            self.actions.append(("click", x, y))
            return {"ok": True, "x": x, "y": y, "focused": True}

        def move_to(self, x, y, **kwargs):
            self.actions.append(("move", x, y))
            return {"ok": True, "x": x, "y": y, "duration": 0.01}

        def type_text(self, text, **kwargs):
            self.actions.append(("type", text))
            return True

        def press(self, key, **kwargs):
            self.actions.append(("press", key))
            return True

        def hotkey(self, *keys, **kwargs):
            self.actions.append(("hotkey", keys))
            return True

        def scroll(self, amount, **kwargs):
            self.actions.append(("scroll", amount))
            return True

    def _agent(self, meta, *, paper_ok=True, allow_submit=True):
        from PIL import Image

        fake_input = self._Input()

        def capture():
            return Image.new("RGB", (1000, 700), "black"), (0, 0, 1000, 700)

        agent = TradingViewGuiAgent(
            meta=meta,
            input_factory=lambda: fake_input,
            window_finder=lambda: object(),
            capture_func=capture,
            paper_checker=lambda image: {"ok": paper_ok, "score": 0.99},
            max_steps=16,
            timeout_s=30,
        )
        return agent, fake_input

    def test_loop_fills_ticket_and_submits_through_cursor(self):
        actions = [
            self._action("click", x=0.88, y=0.08),
            self._action("click", x=0.62, y=0.30),
            self._action("click", x=0.62, y=0.50),
            self._action("type", text="1"),
            self._action("click", x=0.62, y=0.70),
            self._action("hotkey", keys=["ctrl", "a"]),
            self._action("type", text="110"),
            self._action("click", x=0.62, y=0.80),
            self._action("hotkey", keys=["ctrl", "a"]),
            self._action("type", text="95"),
            self._action("press", key="tab"),
            self._action("submit", x=0.62, y=0.90),
            self._action("done"),
        ]
        meta = self._Meta(actions)
        agent, fake_input = self._agent(meta)
        result = agent.place_order(
            symbol="ETHUSDT", side="SELL", quantity=1, entry=100,
            stop_loss=95, take_profit=110, allow_submit=True,
        )
        self.assertTrue(result.ok, result.reason)
        self.assertTrue(result.submitted)
        self.assertTrue(result.confirmed)
        self.assertTrue(result.paper_verified)
        expected_submit = agent._screen_point(0.62, 0.90, (0, 0, 1000, 700))
        self.assertIn(("click", *expected_submit), fake_input.actions)
        self.assertIn(("type", "1"), fake_input.actions)
        self.assertIn(("type", "110"), fake_input.actions)
        self.assertIn(("type", "95"), fake_input.actions)
        self.assertTrue(any("safe_to_submit" in call["schema"] for call in meta.calls))

    def test_submit_is_blocked_when_paper_panel_is_not_visible(self):
        actions = [
            self._action("submit", x=0.62, y=0.90, paper_trading_visible=False),
            self._action("submit", x=0.62, y=0.90, paper_trading_visible=False),
        ]
        meta = self._Meta(actions, submit_ok=False)
        agent, fake_input = self._agent(meta, paper_ok=False)
        result = agent.place_order(
            symbol="ETHUSDT", side="SELL", quantity=1, entry=100,
            stop_loss=95, take_profit=110, allow_submit=True,
        )
        self.assertFalse(result.ok)
        self.assertFalse(result.submitted)
        self.assertNotIn(("click", 620, 630), fake_input.actions)
        self.assertTrue(
            any("submit blocked" in step.get("result", "") for step in result.steps)
        )

    def test_dry_run_never_clicks_submit(self):
        actions = [self._action("submit", x=0.62, y=0.90)]
        meta = self._Meta(actions)
        agent, fake_input = self._agent(meta)
        result = agent.place_order(
            symbol="ETHUSDT", side="SELL", quantity=1, entry=100,
            stop_loss=95, take_profit=110, allow_submit=False,
        )
        self.assertTrue(result.ready)
        self.assertFalse(result.submitted)
        self.assertNotIn(("click", 620, 630), fake_input.actions)

    def test_unsafe_actions_are_rejected(self):
        self.assertIsNone(_safe_keys(["alt", "f4"]))
        self.assertIsNone(_safe_keys(["ctrl", "w"]))
        self.assertIsNone(_safe_text("110\n95"))
        self.assertIsNone(_safe_text(""))
        self.assertEqual(_norm_coord(0.5, 1000), 0.5)
        self.assertEqual(_norm_coord(500, 1000), 0.5)
        self.assertEqual(_norm_coord(50, 1000), 0.5)
        self.assertIsNone(_norm_coord(-1, 1000))

    def test_stale_pending_reservation_is_expired(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = PaperTradingEngine(make_settings(Path(tmp)))
            order = engine.reserve({
                "action": "BUY", "symbol": "BTCUSDT", "entry": 100,
                "stop_loss": 95, "take_profit": 110, "rationale": "test",
            })
            self.assertEqual(order.status, "PENDING_UI")
            order.opened_at -= 10_000
            self.assertEqual(engine.expire_stale_reservations(max_age_s=60), 1)
            self.assertEqual(order.status, "UI_FAILED")
            self.assertIn("stale reservation", order.ui_error)
            self.assertIsNone(engine.find_open_order("BTCUSDT", "BUY"))
            self.assertEqual(engine.expire_stale_reservations(max_age_s=60), 0)

    def test_reserve_confirm_and_fail_ui(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = PaperTradingEngine(make_settings(Path(tmp)))
            decision = {
                "action": "BUY", "symbol": "BTCUSDT", "entry": 100,
                "stop_loss": 95, "take_profit": 110, "rationale": "test",
            }
            order = engine.reserve(decision)
            self.assertEqual(order.status, "PENDING_UI")
            self.assertFalse(order.ui_verified)
            self.assertIsNotNone(engine.find_open_order("BTCUSDT", "BUY"))
            engine.confirm_ui(order, reference="TV-1", price=101)
            self.assertEqual(order.status, "OPEN")
            self.assertTrue(order.ui_verified)
            self.assertEqual(order.ui_reference, "TV-1")
            self.assertEqual(order.ui_price, 101)

            other = engine.reserve({
                "action": "SELL", "symbol": "ETHUSDT", "entry": 100,
                "stop_loss": 105, "take_profit": 90, "rationale": "test",
            })
            engine.fail_ui(other, "paper panel missing")
            self.assertEqual(other.status, "UI_FAILED")
            self.assertFalse(other.ui_verified)
            self.assertIsNone(engine.find_open_order("ETHUSDT", "SELL"))

    def test_explicit_task_uses_gui_and_registers_after_confirmation(self):
        class TradeMeta:
            def reason_json(self, **kwargs):
                return {
                    "action": "BUY", "symbol": "BTCUSDT", "entry": 100,
                    "stop_loss": 95, "take_profit": 110, "confidence": 0.9,
                    "rationale": "Trend confirmed", "strategy_refs": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp))
            engine = PaperTradingEngine(settings)
            gui = FakeGuiAgent()
            task = TradingTask(
                meta=TradeMeta(), memory=FAISSMemory(settings=settings),
                engine=engine, settings=settings, gui_agent=gui,
            )
            result = task.run(TradingRequest(raw=json.dumps({
                "symbol": "BTCUSDT", "execute": True,
                "note": "Delegated order: explicit paper entry.",
            })))
            self.assertEqual(result.state.value, "completed", result.error)
            self.assertEqual(len(gui.calls), 1)
            self.assertEqual(gui.calls[0]["quantity"], 20)
            self.assertTrue(result.data.get("gui_verified"))
            self.assertIn("Paper Trading verified", result.summary)
            order = engine.snapshot()["open_orders"][0]
            self.assertTrue(order["ui_verified"])
            self.assertEqual(order["ui_reference"], "FAKE-UI")

    def test_explicit_task_does_not_register_when_gui_fails(self):
        class TradeMeta:
            def reason_json(self, **kwargs):
                return {
                    "action": "BUY", "symbol": "BTCUSDT", "entry": 100,
                    "stop_loss": 95, "take_profit": 110, "confidence": 0.9,
                    "rationale": "Trend confirmed", "strategy_refs": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp))
            engine = PaperTradingEngine(settings)
            gui = FakeGuiAgent(GuiAgentResult(
                ok=False, status="failed", reason="Paper Trading no visible",
                submitted=False,
            ))
            task = TradingTask(
                meta=TradeMeta(), memory=FAISSMemory(settings=settings),
                engine=engine, settings=settings, gui_agent=gui,
            )
            result = task.run(TradingRequest(raw=json.dumps({
                "symbol": "BTCUSDT", "execute": True,
                "note": "Delegated order: explicit paper entry.",
            })))
            self.assertEqual(result.state.value, "rejected", result.error)
            self.assertIn("No se abrió orden paper en TradingView", result.summary)
            self.assertEqual(engine.snapshot()["open_orders"], [])
            self.assertEqual(result.data["order"]["status"], "UI_FAILED")
            self.assertFalse(result.data["order"]["ui_verified"])

    def test_explicit_task_without_gui_is_not_faked(self):
        class TradeMeta:
            def reason_json(self, **kwargs):
                return {
                    "action": "BUY", "symbol": "BTCUSDT", "entry": 100,
                    "stop_loss": 95, "take_profit": 110, "confidence": 0.9,
                    "rationale": "Trend confirmed", "strategy_refs": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp))
            engine = PaperTradingEngine(settings)
            task = TradingTask(
                meta=TradeMeta(), memory=FAISSMemory(settings=settings),
                engine=engine, settings=settings,
            )
            result = task.run(TradingRequest(raw=json.dumps({
                "symbol": "BTCUSDT", "execute": True,
                "note": "Delegated order: explicit paper entry.",
            })))
            self.assertEqual(result.state.value, "rejected", result.error)
            self.assertIn("No se abrió orden paper", result.summary)
            self.assertEqual(engine.snapshot()["open_orders"], [])


class DesktopDelegationTests(unittest.TestCase):
    def test_delegation_works_with_script_sys_path(self):
        """Regression: ``pythonw src\\main.py`` only has ``src`` on sys.path.

        The UI imports ``core.trade_intent`` while routing the order.  Without
        the repository root on sys.path that import raised inside the worker
        thread and the composer stayed on "Thinking..." forever.
        """
        root = Path(__file__).resolve().parent.parent
        code = r'''
import os, sys
root = os.getcwd()
sys.path = [os.path.join(root, "src")] + [
    p for p in sys.path
    if p and os.path.abspath(p) != root
]
os.environ.setdefault("META_API_KEY", "test-key")
import main

class Dummy:
    def _current_tradingview_symbol(self):
        return "ETHUSDT"
    _detect_agent_delegation = main.OrunexApp._detect_agent_delegation
    _format_delegated_result = main.OrunexApp._format_delegated_result

d = Dummy()
result = d._detect_agent_delegation(
    "abre TradingView y haz una entrada"
)
assert result is not None, "delegation was not detected"
payload, message = result
assert payload.startswith("!trade "), payload
assert '"execute": true' in payload, payload
assert "ETHUSDT" in payload, payload
formatted = d._format_delegated_result(
    "paper_trading rejected No paper order: confidence 0.35 "
    "below explicit-order threshold 0.50."
)
assert "no abrió orden paper" in formatted.lower(), formatted
assert "Muse ejecutó" not in formatted, formatted
english = d._detect_agent_delegation(
    "open TradingView and make an entry"
)
assert english is not None, "English delegation was not detected"
payload_en, message_en = english
assert payload_en.startswith("!trade "), payload_en
assert '"execute": true' in payload_en, payload_en
assert "Delegating the paper execution" in message_en, message_en
formatted_en = d._format_delegated_result(
    "paper_trading rejected No paper order: confidence 0.35 "
    "below explicit-order threshold 0.50.",
    language="en",
)
assert "did not open a paper order" in formatted_en.lower(), formatted_en
assert "no abrió" not in formatted_en.lower(), formatted_en
print("OK")
'''
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=90,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("OK", completed.stdout)


class OfficeExtractionTests(unittest.TestCase):
    """Extracción de título y métricas sin depender de red ni de LLM."""

    def test_detect_marketing_pptx(self):
        detected = artifact_studio.detect_request(
            "Crea una presentación ejecutiva de marketing B2B con investigación"
        )
        self.assertIsNotNone(detected)
        self.assertEqual(detected["kind"], "pptx")
        self.assertIn("Marketing", detected["title"])

    def test_detect_excel(self):
        detected = artifact_studio.detect_request("Crea un Excel de ventas B2B")
        self.assertIsNotNone(detected)
        self.assertEqual(detected["kind"], "xlsx")

    def test_detect_word(self):
        detected = artifact_studio.detect_request("Crea un Word sobre energía solar")
        self.assertIsNotNone(detected)
        self.assertEqual(detected["kind"], "docx")

    def test_extract_strong_metrics(self):
        text = (
            "Crea una presentación ejecutiva de marketing B2B con investigación de mercado "
            "y estas métricas: Inversión publicitaria 45.000 USD, Ingresos generados 187.500 USD, "
            "Tasa de conversión 3,2%, CAC 420 USD"
        )
        metrics = artifact_studio.extract_metrics(text)
        labels = {m["label"] for m in metrics}
        self.assertIn("Inversión publicitaria", labels)
        self.assertIn("Ingresos", labels)
        self.assertIn("Tasa de conversión", labels)
        self.assertIn("CAC", labels)
        by_label = {m["label"]: m for m in metrics}
        self.assertEqual(by_label["Inversión publicitaria"]["value"], 45000.0)
        self.assertEqual(by_label["Ingresos"]["value"], 187500.0)
        self.assertEqual(by_label["Tasa de conversión"]["value"], 3.2)
        self.assertEqual(by_label["CAC"]["value"], 420.0)
        self.assertEqual(by_label["Inversión publicitaria"]["unit"], "USD")

    def test_parse_number_thousands_and_decimals(self):
        parse = artifact_studio._parse_number
        self.assertEqual(parse("45.000"), 45000.0)
        self.assertEqual(parse("187.500"), 187500.0)
        self.assertEqual(parse("3,2"), 3.2)
        self.assertEqual(parse("1,234.56"), 1234.56)
        self.assertEqual(parse("1.234,56"), 1234.56)
        self.assertEqual(parse("420"), 420.0)

    def test_title_cuts_data_intro(self):
        title = artifact_studio.extract_request_data(
            "Crea una presentación de marketing B2B con estas métricas: Inversión 45.000 USD",
            "Marketing B2B",
        )["title"]
        self.assertEqual(title, "Marketing B2B")


class OfficeArtifactTests(unittest.TestCase):
    """Generación real de PPTX, XLSX y DOCX sin red (research desactivado)."""

    def _build_plan(self, lang="es"):
        raw = (
            "Crea una presentación ejecutiva de marketing B2B con investigación de mercado "
            "y estas métricas: Inversión publicitaria 45.000 USD, Ingresos generados 187.500 USD, "
            "Tasa de conversión 3,2%, CAC 420 USD"
        )
        detected = artifact_studio.detect_request(raw)
        data = artifact_studio.extract_request_data(raw, detected["title"])
        return office_expert.build_plan(
            detected["title"], raw, data, lang, research_enabled=False
        )

    def _assert_real_file(self, path, kind):
        self.assertTrue(os.path.isfile(path), path)
        self.assertGreater(os.path.getsize(path), 1000, path)
        self.assertTrue(path.lower().endswith("." + kind), path)

    def test_write_pptx(self):
        plan = self._build_plan("es")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test_marketing.pptx")
            result = office_expert.write_pptx(path, plan)
            self._assert_real_file(path, "pptx")
            self.assertGreaterEqual(result["slides"], 5)
            self.assertTrue(result["animated"])

    def test_write_xlsx(self):
        plan = self._build_plan("es")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test_marketing.xlsx")
            result = office_expert.write_xlsx(path, plan)
            self._assert_real_file(path, "xlsx")
            self.assertIn("Dashboard", result.get("sheets", []))

    def test_write_docx(self):
        plan = self._build_plan("es")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test_marketing.docx")
            result = office_expert.write_docx(path, plan)
            self._assert_real_file(path, "docx")
            self.assertGreaterEqual(result.get("sections", 0), 1)

    def test_plan_has_metrics_and_deep_dives(self):
        plan = self._build_plan("es")
        self.assertEqual(len(plan["metrics"]), 4)
        self.assertGreaterEqual(len(plan["deep_dives"]), 1)
        # Cada deep dive debe traer su propio tipo de análisis (kind), no repetir el primero.
        kinds = {d.get("kind") for d in plan["deep_dives"] if d.get("kind")}
        self.assertGreater(len(kinds), 1)
        # El helper de métrica por tipo debe devolver la métrica del tema, no siempre la primera.
        metrics_by_kind = {
            d["kind"]: office_expert._metric_for_kind(plan, d["kind"])
            for d in plan["deep_dives"]
            if d.get("kind")
        }
        self.assertGreater(len(set(metrics_by_kind.values())), 1)


class BmdTests(unittest.TestCase):
    """Operaciones reales con el motor Blockchain Markdown (CLI + DLL, sin simulación)."""

    @classmethod
    def setUpClass(cls):
        cls.engine = bmd_expert.BMDEngine()
        if not cls.engine.available:
            raise unittest.SkipTest("bmd_engine binarios no disponibles")

    def test_status(self):
        status = self.engine.status()
        self.assertTrue(status["available"])
        self.assertTrue(status["cli"])
        self.assertTrue(status["dll"])

    def test_create_draft_verify_and_inspect(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "contrato.bmd")
            result = self.engine.create_draft(
                path=path,
                payload="Contrato de licencia de software entre Orunex y Cliente.",
                document_type="contract",
                require_cosigner=True,
                max_signatures=2,
            )
            self.assertTrue(result["ok"], result.get("error"))
            self.assertTrue(os.path.isfile(result["path"]))

            verified = self.engine.verify(result["path"])
            self.assertTrue(verified.ok, verified.stderr)

            inspected = self.engine.inspect(result["path"])
            self.assertTrue(inspected.ok, inspected.stderr)
            self.assertEqual(inspected.data.get("max_signatures"), 2)

    def test_compile_sign_and_co_sign(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "firmar.bmd")
            result = self.engine.create_draft(
                path=path,
                payload="Contrato bilateral para firmar entre A y B.",
                document_type="contract",
                require_cosigner=True,
                max_signatures=2,
            )
            self.assertTrue(result["ok"], result.get("error"))

            signed = self.engine.compile_sign(path)
            self.assertTrue(signed.ok, signed.stderr)
            self.assertEqual(signed.returncode, 0)

            signed_json = self.engine.verify_json(path)
            self.assertTrue(signed_json.ok, signed_json.stderr)
            self.assertTrue(signed_json.data.get("hash_valid"))
            self.assertEqual(
                signed_json.data.get("current_state"), "compiled_transfer"
            )

            co_signed = self.engine.co_sign(path)
            self.assertTrue(co_signed.ok, co_signed.stderr or co_signed.stdout)

            dual_json = self.engine.verify_json(path)
            self.assertTrue(dual_json.ok, dual_json.stderr)
            self.assertTrue(dual_json.data.get("hash_valid"))
            self.assertEqual(dual_json.data.get("current_state"), "dual_signed")

            inspected = self.engine.inspect(path)
            self.assertTrue(inspected.ok, inspected.stderr)
            self.assertEqual(inspected.data.get("max_signatures"), 2)

            self.engine._make_writable(path)

    def test_signature_governance_rejects_cosign(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "unilateral.bmd")
            result = self.engine.create_draft(
                path=path,
                payload="Declaración unilateral de prueba.",
                document_type="declaration",
                max_signatures=1,
            )
            self.assertTrue(result["ok"], result.get("error"))

            signed = self.engine.compile_sign(path)
            self.assertTrue(signed.ok, signed.stderr)

            co_signed = self.engine.co_sign(path)
            self.assertFalse(co_signed.ok)
            self.assertIn("max_signatures", co_signed.stdout + co_signed.stderr)

            self.engine._make_writable(path)

    def test_lock_applies_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bloqueado.bmd")
            result = self.engine.create_draft(
                path=path,
                payload="Documento para bloquear.",
                document_type="declaration",
            )
            self.assertTrue(result["ok"], result.get("error"))

            locked = self.engine.lock(path)
            self.assertTrue(locked.ok, locked.stderr)
            self.assertFalse(os.access(path, os.W_OK))

            self.engine._make_writable(path)
            self.assertTrue(os.access(path, os.W_OK))

    def test_export_office_and_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "exportar.bmd")
            result = self.engine.create_draft(
                path=path,
                payload="Contrato de licencia para exportar a Orunex.",
                document_type="license",
                require_cosigner=True,
                max_signatures=2,
            )
            self.assertTrue(result["ok"], result.get("error"))

            exported = self.engine.export_office(result["path"])
            self.assertTrue(exported.ok, exported.stderr)
            self.assertEqual(exported.data.get("status"), "verified")

            rendered = self.engine.render(result["path"])
            self.assertTrue(rendered.ok, rendered.stderr)
            self.assertTrue(
                os.path.isfile(os.path.splitext(result["path"])[0] + ".html")
            )

    def test_audit_consensus(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "auditar.bmd")
            result = self.engine.create_draft(
                path=path,
                payload="Contrato para auditar entre A y B.",
                document_type="contract",
                max_signatures=2,
            )
            self.assertTrue(result["ok"], result.get("error"))
            audited = self.engine.audit([result["path"]])
            self.assertTrue(audited.ok, audited.stderr)

    def test_bmd_knowledge_search(self):
        ctx = bmd_knowledge.bmd_context("¿qué es la firma BMD?")
        self.assertIsInstance(ctx, str)
        self.assertGreater(len(ctx), 0)

        self.assertEqual(
            bmd_knowledge.BMD_KNOWLEDGE_VERSION,
            "bmd-engine-2.1.0/orunex-pack-3",
        )
        self.assertEqual(len(bmd_knowledge.BMD_KNOWLEDGE), 21)

        hits = bmd_knowledge.search_bmd_knowledge("max_signatures", top_k=3)
        ids = [hit["metadata"].get("knowledge_id") for hit in hits]
        self.assertIn("bmd.signature.governance", ids)

        contract_hits = bmd_knowledge.search_bmd_knowledge(
            "contrato bilateral de servicios", top_k=3
        )
        contract_ids = [
            hit["metadata"].get("knowledge_id") for hit in contract_hits
        ]
        self.assertIn("bmd.contracts", contract_ids)

        sha_hits = bmd_knowledge.search_bmd_knowledge("SHA-512", top_k=3)
        sha_ids = [hit["metadata"].get("knowledge_id") for hit in sha_hits]
        self.assertIn("bmd.hash.canonical", sha_ids)

    def test_handle_request_returns_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = bmd_expert.handle_request(
                "Crea un contrato .bmd de prestación de servicios "
                "con cláusulas de confidencialidad",
                out_dir=tmp,
            )
            self.assertIsNotNone(out)
            self.assertTrue(out["ok"], out.get("message"))
            artifact = out.get("artifact")
            self.assertTrue(artifact)
            path = out.get("path") or artifact.get("path")
            self.assertTrue(path and os.path.isfile(path))

            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("max_signatures", content)
            self.assertIn("## 1. Partes", content)
            self.assertIn("Confidencialidad", content)

            inspected = self.engine.inspect(path)
            self.assertTrue(inspected.ok, inspected.stderr)
            self.assertEqual(inspected.data.get("max_signatures"), 2)

    def test_document_type_detection(self):
        cases = {
            "Crea un contrato .bmd de prestación de servicios": "services",
            "Crea un contrato .bmd sobre licencia de software": "license",
            "Crea un acuerdo de confidencialidad .bmd": "nda",
            "Crea un contrato de transferencia de propiedad intelectual": (
                "ip_transfer"
            ),
            "Crea un contrato de compraventa": "contract",
            "Crea un testamento .bmd": "testament",
            "Create a .bmd services agreement for software development": (
                "services"
            ),
            "Create a non-disclosure agreement in .bmd": "nda",
            "Create a license agreement in .bmd": "license",
            "Create an intellectual property transfer agreement in .bmd": (
                "ip_transfer"
            ),
        }
        for text, expected in cases.items():
            self.assertEqual(
                bmd_expert._detect_document_type(text),
                expected,
                text,
            )

    def test_handle_request_english_services_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = bmd_expert.handle_request(
                "Create a .bmd services agreement for software development",
                out_dir=tmp,
            )
            self.assertIsNotNone(out)
            self.assertTrue(out["ok"], out.get("message"))
            self.assertEqual(out["lang"], "en")
            self.assertEqual(out["data"].get("document_type"), "services")
            self.assertEqual(out["data"].get("max_signatures"), 2)
            with open(out["path"], encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("## 1. Parties", content)
            self.assertIn("## 4. Services", content)
            self.assertIn("max_signatures", content)

    def test_bmd_question_does_not_create_document(self):
        self.assertIsNone(
            bmd_expert.handle_request(
                "What is a BMD signature and how does max_signatures work?"
            )
        )


if __name__ == "__main__":
    unittest.main()
