"""Central configuration for the Orunex Hackathon Agent.

Every value comes from the environment (optionally through a local ``.env``
file).  Secrets are never hard-coded and never logged.  The only reasoning
model allowed anywhere in this package is Meta ``muse-spark``; see
:mod:`core.meta_api`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Load ``.env`` when python-dotenv is available, else parse it manually."""
    env_path = PROJECT_ROOT / ".env"
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(env_path)
        return
    except Exception:
        pass
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _simplex_contact_default() -> str:
    """Reuse the contact already paired by the production Orunex bridge."""
    try:
        import json

        path = PROJECT_ROOT / "src" / "config" / "simplex.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("last_contact_name") or "")
    except Exception:
        return ""


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name) or default)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name) or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings resolved once at startup."""

    # --- Meta / Muse Spark (the ONLY reasoning engine) ---------------------
    meta_api_key: str = field(default_factory=lambda: _env("META_API_KEY"))
    meta_api_base: str = field(
        default_factory=lambda: _env("META_API_BASE", "https://api.meta.ai/v1")
    )
    meta_model: str = field(default_factory=lambda: _env("META_MODEL", "muse-spark"))
    meta_timeout: float = field(default_factory=lambda: _env_float("META_API_TIMEOUT", 120.0))
    meta_max_tokens: int = field(default_factory=lambda: _env_int("META_MAX_TOKENS", 4096))
    meta_temperature: float = field(default_factory=lambda: _env_float("META_TEMPERATURE", 0.1))
    meta_reasoning_effort: str = field(
        default_factory=lambda: _env("META_REASONING_EFFORT", "medium")
    )

    # --- Workspace / Android project ---------------------------------------
    workspace_root: Path = field(
        default_factory=lambda: Path(_env("AGENT_WORKSPACE", str(PROJECT_ROOT))).expanduser()
    )
    android_project_dir: Path = field(
        default_factory=lambda: Path(
            _env("ANDROID_PROJECT_DIR", str(PROJECT_ROOT / "android"))
        ).expanduser()
    )
    android_package: str = field(default_factory=lambda: _env("ANDROID_PACKAGE", "com.orunex.mobile"))
    android_activity: str = field(default_factory=lambda: _env("ANDROID_ACTIVITY", ""))
    adb_path: str = field(default_factory=lambda: _env("ADB_PATH", ""))
    adb_serial: str = field(default_factory=lambda: _env("ADB_SERIAL", ""))
    android_avd: str = field(
        default_factory=lambda: _env("ANDROID_AVD", "") or _env("DEMO_AVD", "")
    )

    # --- FAISS memory --------------------------------------------------------
    memory_index_path: Path = field(
        default_factory=lambda: Path(
            _env("FAISS_INDEX_PATH", str(PROJECT_ROOT / "data" / "hackathon_memory.index"))
        ).expanduser()
    )

    # --- Autonomous fix safety ----------------------------------------------
    auto_apply_fixes: bool = field(default_factory=lambda: _env_bool("AGENT_AUTO_APPLY_FIXES", False))
    max_patch_replacements: int = field(default_factory=lambda: _env_int("AGENT_MAX_PATCH_REPLACEMENTS", 3))

    # --- Simplex --------------------------------------------------------------
    simplex_ws_url: str = field(
        default_factory=lambda: _env("SIMPLEX_WS_URL", "ws://127.0.0.1:5227")
    )
    simplex_contact: str = field(
        default_factory=lambda: _env("SIMPLEX_CONTACT", "") or _simplex_contact_default()
    )
    simplex_enabled: bool = field(default_factory=lambda: _env_bool("SIMPLEX_ENABLED", False))

    # --- Paper trading (NEVER real money) -------------------------------------
    paper_trading_only: bool = True  # hard invariant, not configurable off
    paper_initial_balance: float = field(
        default_factory=lambda: _env_float("PAPER_INITIAL_BALANCE", 10_000.0)
    )
    paper_currency: str = field(default_factory=lambda: _env("PAPER_CURRENCY", "USD"))
    max_risk_per_trade_pct: float = field(
        default_factory=lambda: _env_float("MAX_RISK_PER_TRADE_PCT", 1.0)
    )
    max_position_pct: float = field(default_factory=lambda: _env_float("MAX_POSITION_PCT", 20.0))
    min_trade_confidence: float = field(
        default_factory=lambda: _env_float("MIN_TRADE_CONFIDENCE", 0.70)
    )
    paper_state_path: Path = field(
        default_factory=lambda: Path(
            _env("PAPER_STATE_PATH", str(PROJECT_ROOT / "data" / "paper_trading.json"))
        ).expanduser()
    )

    def validate(self) -> list[str]:
        """Return human-readable configuration problems (empty when healthy)."""
        problems: list[str] = []
        if not self.meta_api_key:
            problems.append("META_API_KEY is not set (copy .env.example to .env).")
        if not self.meta_model.lower().startswith("muse-spark"):
            problems.append(
                f"META_MODEL must be a Muse Spark deployment, got {self.meta_model!r}."
            )
        if not self.workspace_root.exists():
            problems.append(f"AGENT_WORKSPACE does not exist: {self.workspace_root}")
        if self.max_risk_per_trade_pct <= 0 or self.max_risk_per_trade_pct > 5:
            problems.append("MAX_RISK_PER_TRADE_PCT must be in (0, 5].")
        if not 0 < self.min_trade_confidence <= 1:
            problems.append("MIN_TRADE_CONFIDENCE must be in (0, 1].")
        return problems


def get_settings() -> Settings:
    return Settings()
