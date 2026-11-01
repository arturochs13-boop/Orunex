#!/usr/bin/env python3
"""Orunex Muse Spark Autonomous Agent — entry point.

Usage:
    python app.py                  # headless agent backend (no Muse Agent panel)
    python app.py --check          # headless diagnostics (no GUI, no device)
    python app.py --index-code     # index the workspace into FAISS, then exit
    python app.py --demo-paper     # run one paper-trading decision, then exit
    python app.py --warmup         # open emulator + TradingView, then exit
    python app.py --command "!fix ..."  # rehearse one remote order locally

Requires META_API_KEY in the environment or in a local .env file.
Paper trading only: this program has no real-broker code path.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# The delegated agent runs from the repository root (``app.py --command``).
# ``src`` must be importable there too: the trading task drives TradingView
# through ``_orunex_libs.virtual_input`` (the agent-owned cursor).  Without
# this, the delegated process silently fell back to "cursor unavailable".
_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description="Orunex Muse Spark Agent")
    parser.add_argument("--check", action="store_true", help="print diagnostics and exit")
    parser.add_argument("--index-code", action="store_true", help="index codebase into FAISS")
    parser.add_argument("--demo-paper", action="store_true", help="run a demo paper decision")
    parser.add_argument("--warmup", action="store_true", help="open emulator + TradingView")
    parser.add_argument("--command", default="", help="rehearse one Simplex-style remote order")
    parser.add_argument("--tradingview", default="", help="open this symbol in TradingView")
    parser.add_argument(
        "--alert",
        default='{"symbol":"BTCUSDT","side":"BUY","price":67000,"rsi":61,"ema_trend":"up"}',
        help="TradingView-style alert JSON for --demo-paper",
    )
    args = parser.parse_args()

    from core.agent_brain import AgentBrain

    brain = AgentBrain()
    try:
        from concurrent.futures import TimeoutError as FutureTimeout

        if args.check:
            diagnostics = brain.diagnostics()
            try:
                import sys as _sys
                from pathlib import Path as _Path

                _src = str(_Path(__file__).resolve().parent / "src")
                if _src not in _sys.path:
                    _sys.path.insert(0, _src)
                from _orunex_libs.ollama_client import verify_connection

                diagnostics["meta_health"] = verify_connection(timeout=25.0)
            except Exception as exc:
                diagnostics["meta_health"] = {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            print(json.dumps(diagnostics, indent=2, default=str))
            return 0 if diagnostics["meta_health"].get("ok") else 1
        if args.index_code:
            future = brain.submit_index_codebase()
            print(future.result(timeout=600).summary)
            return 0
        if args.demo_paper:
            from tasks.trading_task import TradingRequest

            future = brain.submit_trading(TradingRequest(raw=args.alert, source="cli"))
            result = future.result(timeout=300)
            print(result.summary)
            return 0 if result.state.value != "failed" else 1
        if args.warmup:
            try:
                result = brain.warmup_async("cli").result(timeout=360)
            except FutureTimeout:
                print("Warm-up timed out; check emulator/TradingView and retry.")
                return 1
            print(result.summary)
            return 0 if result.state.value != "failed" else 1
        if args.tradingview:
            try:
                result = brain.submit_tradingview(args.tradingview).result(timeout=120)
            except FutureTimeout:
                print("TradingView did not confirm the chart before the timeout.")
                return 1
            print(result.summary)
            return 0 if result.state.value != "failed" else 1
        if args.command:
            brain.handle_remote_text(args.command, contact="cli")
            idle = brain.wait_for_idle(timeout=900)
            for kind, state, summary in brain.completed_summaries():
                clean = " | ".join(str(summary).splitlines())[:1200]
                print(f"AGENT_RESULT {kind} {state} {clean}")
            print("Remote command finished." if idle else "Remote command timed out.")
            return 0 if idle else 1
    finally:
        brain.shutdown()

    print(
        "Agent backend ready. The Muse Agent panel was removed; "
        "use --command, --warmup, --tradingview, or --check."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
