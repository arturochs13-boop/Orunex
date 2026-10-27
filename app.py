#!/usr/bin/env python3
"""Orunex Muse Spark Autonomous Agent — entry point.

Usage:
    python app.py                  # Meta-style desktop UI
    python app.py --check          # headless diagnostics (no GUI, no device)
    python app.py --index-code     # index the workspace into FAISS, then exit
    python app.py --demo-paper     # run one paper-trading decision, then exit

Requires META_API_KEY in the environment or in a local .env file.
Paper trading only: this program has no real-broker code path.
"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Orunex Muse Spark Agent")
    parser.add_argument("--check", action="store_true", help="print diagnostics and exit")
    parser.add_argument("--index-code", action="store_true", help="index codebase into FAISS")
    parser.add_argument("--demo-paper", action="store_true", help="run a demo paper decision")
    parser.add_argument(
        "--alert",
        default='{"symbol":"BTCUSDT","side":"BUY","price":67000,"rsi":61,"ema_trend":"up"}',
        help="TradingView-style alert JSON for --demo-paper",
    )
    args = parser.parse_args()

    from core.agent_brain import AgentBrain

    brain = AgentBrain()
    try:
        if args.check:
            print(json.dumps(brain.diagnostics(), indent=2, default=str))
            return 0
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
    finally:
        if args.check or args.index_code or args.demo_paper:
            brain.shutdown()

    from ui.main_window import launch_ui

    launch_ui(brain)
    return 0


if __name__ == "__main__":
    sys.exit(main())
