"""Unit tests for the Muse Spark hackathon agent (no network, no device)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("META_API_KEY", "test-key")

from bridges.vscode_bridge import PatchError, VSCodeBridge  # noqa: E402
from core.config import Settings  # noqa: E402
from core.faiss_memory import FAISSMemory  # noqa: E402
from core.meta_api import MetaAPIClient, MetaNotConfigured, parse_json_object  # noqa: E402
from tasks.bugfix_task import AndroidBugfixTask, BugfixRequest  # noqa: E402
from tasks.trading_task import PaperTradingEngine, TradingRequest, TradingTask  # noqa: E402


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

    def json(self):
        return {"choices": [{"message": {"content": "hola desde muse"}}]}


class FakeSession:
    def __init__(self):
        self.payload = None

    def post(self, url, headers=None, json=None, timeout=None):
        self.payload = json
        return FakeResponse()


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


if __name__ == "__main__":
    unittest.main()
