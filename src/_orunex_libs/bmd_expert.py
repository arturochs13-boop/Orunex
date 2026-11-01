"""BMD expert for Orunex: real CLI/FFI operations on Blockchain Markdown.

This module is deliberately independent from the language model.  Every
operation either runs the real ``bmd_engine/bin/bmd_cli.exe`` or the real
``bmd_engine.dll`` through ``bmd_ffi.py``; nothing is simulated.  The agent
uses it to:

* create valid ``.bmd`` drafts (hash computed by the C11 engine);
* verify, inspect, render, export and audit real files;
* freeze/sign and co-sign blocks with explicit seeds;
* build hash-linked chains;
* answer deterministic BMD orders without a model round-trip.

The public entry point for the UI/executor is :func:`handle_request`, which
returns ``None`` when the text is not a concrete BMD action so the normal
conversation path can answer it.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = PROJECT_ROOT / "bmd_engine"
BIN_DIR = ENGINE_DIR / "bin"
CLI_PATH = BIN_DIR / "bmd_cli.exe"
DLL_PATH = BIN_DIR / "bmd_engine.dll"
FFI_DIR = ENGINE_DIR / "python"
OUTPUT_DIR = PROJECT_ROOT / "orunex_outputs" / "artifacts"

ZERO_HASH = "0" * 128

# Public demo seeds used only when the caller does not provide a real seed.
# The engine CLI also defaults to these values; they must never be used for
# legally binding production documents.
DEMO_EMITTER_SEED = "42" * 32
DEMO_RECEIVER_SEED = "99" * 32

_CREATE_VERBS = re.compile(
    r"\b(crea|crear|genera|generar|redacta|redactar|haz|hacer|escribe|"
    r"escribir|programa|programar|elabora|elaborar|create|make|generate|"
    r"write|draft|prepare|compose)\b",
    re.IGNORECASE,
)
_BMD_WORD = re.compile(
    r"(\.bmd\b|blockchain\s*markdown|\bbmd\b|\bbmd_engine\b)", re.IGNORECASE
)
_VERIFY_RE = re.compile(
    r"\b(verifica|verificar|valida|validar|verify|comprueba|comprobar)\b",
    re.IGNORECASE,
)
_INSPECT_RE = re.compile(
    r"\b(inspecciona|inspeccionar|inspect|analiza|analizar|muestra|mostrar|"
    r"lee|leer)\b",
    re.IGNORECASE,
)
_RENDER_RE = re.compile(
    r"\b(renderiza|renderizar|render|genera\s+html|generar\s+html|"
    r"vista\s+html|visor)\b",
    re.IGNORECASE,
)
_EXPORT_RE = re.compile(
    r"\b(exporta|exportar|export|office|acta|word|excel)\b", re.IGNORECASE
)
_AUDIT_RE = re.compile(
    r"\b(audita|auditar|audit|auditoria|auditoría|cadena|ledger|consenso)\b",
    re.IGNORECASE,
)
_SIGN_RE = re.compile(
    r"\b(firma|firmar|sign|compila|compilar|compile|freeze|congela|congelar)\b",
    re.IGNORECASE,
)
_COSIGN_RE = re.compile(
    r"\b(co-?firma|co-?firmar|cosign|co-sign|acepta|aceptar|accept)\b",
    re.IGNORECASE,
)
_EXPLAIN_RE = re.compile(
    r"\b(que\s+es|qué\s+es|como\s+funciona|cómo\s+funciona|explica|explicar|"
    r"ensename|enséñame|documentacion|documentación|what\s+is|what\s+are|"
    r"how\s+does|how\s+do|explain|tell\s+me|documentation)\b",
    re.IGNORECASE,
)
_QUESTION_RE = re.compile(
    r"^\s*(¿|que\b|qué\b|como\b|cómo\b|cual\b|cuál\b|para\s+que\b|para\s+qué\b|"
    r"explica\b|explícame\b|dime\b|puedes\s+explicar\b|what\b|how\b|which\b|"
    r"why\b|explain\b|tell\s+me\b|can\s+you\s+explain\b)",
    re.IGNORECASE,
)
_EXPLICIT_ACTION_RE = re.compile(
    r"\b(verifica|verificar|valida|validar|crea|crear|genera|generar|renderiza|"
    r"renderizar|audita|auditar|firma\s+el|firmar\s+el|co-?firma\s+el|"
    r"exporta|exportar|inspecciona|inspeccionar|create|make|generate|write|"
    r"draft|prepare|compose)\b",
    re.IGNORECASE,
)
_PATH_RE = re.compile(r"\"([^\"]+\.bmd)\"|'([^']+\.bmd)'|([^\s\"']+\.bmd)", re.IGNORECASE)

# Explicit "contrato/acuerdo de X" heads win over incidental clause mentions.
# Example: "contrato de servicios con cláusulas de propiedad intelectual" is a
# services agreement, not an IP transfer.
_DOC_HEAD_PATTERNS = (
    (
        r"\b(contrato|acuerdo)\s+(?:(?:de|sobre|para)\s+)?"
        r"(?:prestaci[oó]n\s+de\s+)?servicios\b",
        "services",
    ),
    (
        r"\b(contrato|acuerdo)\s+(?:(?:de|sobre|para)\s+)?"
        r"(?:desarrollo\s+de\s+software|consultor[ií]a)\b",
        "services",
    ),
    (
        r"\b(contrato|acuerdo)\s+(?:(?:de|sobre|para)\s+)?"
        r"(licencia|licenciamiento)\b",
        "license",
    ),
    (
        r"\b(contrato|acuerdo)\s+(?:(?:de|sobre|para)\s+)?"
        r"(confidencialidad|nda|non-disclosure)\b",
        "nda",
    ),
    (
        r"\b(contrato|acuerdo)\s+(?:(?:de|sobre|para)\s+)?"
        r"(?:transferencia\s+de\s+)?propiedad\s+intelectual\b",
        "ip_transfer",
    ),
    (
        r"\b(contrato|acuerdo)\s+(?:(?:de|sobre|para)\s+)?"
        r"transferencia\s+de\s+propiedad\b",
        "ip_transfer",
    ),
    (
        r"\b(contrato|acuerdo)\s+(?:(?:de|sobre|para)\s+)?compraventa\b",
        "contract",
    ),
    (
        r"\b(services|consulting|software\s+development)\s+"
        r"(agreement|contract)\b",
        "services",
    ),
    (
        r"\b(license|licensing)\s+(agreement|contract)\b",
        "license",
    ),
    (
        r"\b(non-disclosure|confidentiality|nda)\s+(agreement|contract)\b",
        "nda",
    ),
    (
        r"\b(intellectual\s+property|ip)\s+(?:transfer\s+)?"
        r"(agreement|contract)\b",
        "ip_transfer",
    ),
    (
        r"\b(contract|agreement)\s+(?:for|of|on)\s+"
        r"(services|consulting|software\s+development)\b",
        "services",
    ),
)

# Ordered from most specific to most generic.  Matching is anchored at a word
# boundary so the short key "ip" does not match words like "tipo".
_DOC_TYPES = (
    ("propiedad intelectual", "ip_transfer"),
    ("transferencia de propiedad", "ip_transfer"),
    ("prestacion de servicios", "services"),
    ("prestación de servicios", "services"),
    ("desarrollo de software", "services"),
    ("software development", "services"),
    ("consultoria", "services"),
    ("consultoría", "services"),
    ("consulting", "services"),
    ("licenciamiento", "license"),
    ("licencia", "license"),
    ("licensing", "license"),
    ("non-disclosure", "nda"),
    ("confidencialidad", "nda"),
    ("confidentiality", "nda"),
    ("nda", "nda"),
    ("servicios", "services"),
    ("servicio", "services"),
    ("services", "services"),
    ("service", "services"),
    ("desarrollo", "services"),
    ("intellectual property", "ip_transfer"),
    ("ip transfer", "ip_transfer"),
    ("testamento", "testament"),
    ("testament", "testament"),
    ("herencia", "testament"),
    ("propiedad", "ip_transfer"),
    ("codigo", "ip_transfer"),
    ("código", "ip_transfer"),
    ("ip", "ip_transfer"),
    ("declaracion", "declaration"),
    ("declaración", "declaration"),
    ("declaration", "declaration"),
    ("decreto", "decree"),
    ("decree", "decree"),
    ("contrato", "contract"),
    ("contract", "contract"),
    ("acuerdo", "contract"),
    ("agreement", "contract"),
)

_ES_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "que",
    "y", "o", "para", "por", "con", "sin", "sobre", "como", "cómo", "es", "son",
    "crea", "crear", "genera", "generar", "verifica", "verificar", "archivo",
    "documento", "contrato", "quiero", "necesito", "haz", "favor", "por",
}
_EN_STOPWORDS = {
    "the", "a", "an", "of", "for", "with", "without", "about", "how", "what",
    "is", "are", "create", "make", "generate", "verify", "file", "document",
    "contract", "please", "need", "want", "this", "that", "and", "or",
}


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------
@dataclass
class BMDResult:
    """Outcome of one real engine operation."""

    action: str
    ok: bool
    returncode: int = -1
    stdout: str = ""
    stderr: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    duration_s: float = 0.0
    command: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "ok": bool(self.ok),
            "returncode": int(self.returncode),
            "stdout": self.stdout,
            "stderr": self.stderr,
            "data": dict(self.data),
            "duration_s": round(float(self.duration_s), 3),
            "command": list(self.command),
        }


def _hidden_kwargs() -> Dict[str, Any]:
    if os.name == "nt":
        return {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
            "startupinfo": None,
        }
    return {}


def _language(text: str) -> str:
    """Small ES/EN vote, aligned with office_expert.detect_language."""
    try:
        from .office_expert import detect_language

        return detect_language(text)
    except Exception:
        lowered = str(text or "").lower()
        words = re.findall(r"[a-záéíóúüñ]+", lowered)
        es = sum(1 for word in words if word in _ES_STOPWORDS)
        en = sum(1 for word in words if word in _EN_STOPWORDS)
        return "en" if en > es else "es"


def _msg(lang: str, es: str, en: str) -> str:
    return en if str(lang).lower().startswith("en") else es


def _slug(value: str, fallback: str = "documento") -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return (text or fallback)[:60]


def _extract_path(text: str) -> str:
    match = _PATH_RE.search(str(text or ""))
    if not match:
        return ""
    raw = next((group for group in match.groups() if group), "")
    return raw.strip().strip("\"'") if raw else ""


def _latest_bmd(directory: Optional[Path] = None) -> str:
    root = Path(directory or OUTPUT_DIR)
    if not root.exists():
        return ""
    files = [
        path
        for path in root.rglob("*.bmd")
        if path.is_file()
    ]
    if not files:
        return ""
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return str(files[0])


def _parse_json_output(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except Exception:
            return {}
    return {}


def _parse_inspect(text: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    patterns = {
        "block_id": r"BLOCK METADATA \[(.*?)\]",
        "document_type": r"Document Type\s*:\s*(.+)",
        "previous_hash": r"Previous Hash\s*:\s*(\S+)",
        "current_hash": r"Current Hash\s*:\s*(\S+)",
        "computed_hash": r"Computed Hash\s*:\s*(\S+)",
        "mode": r"Operational Mode\s*:\s*(.+?)(?:\s*\(|$)",
        "signer_role": r"Signer Role\s*:\s*(.+)",
        "timestamp": r"Timestamp\s*:\s*(\d+)",
        "public_key": r"Emitter Public Key\s*:\s*(.+)",
        "signature": r"Emitter Signature\s*:\s*(.+)",
        "receiver_public_key": r"Receiver Public Key\s*:\s*(.+)",
        "receiver_signature": r"Receiver Signature\s*:\s*(.+)",
        "max_signatures": r"Max Signatures\s*:\s*(\d+)",
        "validation": r"Validation Status\s*:\s*(.+)",
        "failure": r"Failure Detail\s*:\s*(.+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            if value and value not in {"(none)", "N/A"}:
                fields[key] = value
    if "timestamp" in fields:
        try:
            fields["timestamp"] = int(fields["timestamp"])
        except ValueError:
            pass
    if "max_signatures" in fields:
        try:
            fields["max_signatures"] = int(fields["max_signatures"])
        except ValueError:
            pass
    if "require_cosigner" in fields:
        fields["require_cosigner"] = str(fields["require_cosigner"]).lower() in {
            "true",
            "yes",
            "1",
        }
    fields["valid"] = "INVALID" not in str(fields.get("validation", "")).upper()
    return fields


def _parse_sign_output(text: str) -> Dict[str, Any]:
    """Parse the human-readable output of the v2.1 ``bmd sign`` command."""
    data: Dict[str, Any] = {}
    patterns = {
        "block_id": r"Block ID\s*:\s*(\S+)",
        "public_key": r"Public Key\s*:\s*(\S+)",
        "signature": r"Signature\s*:\s*(\S+)",
        "mode": r"Mode\s*:\s*(\S+)",
        "file": r"File\s*:\s*(.+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            data[key] = match.group(1).strip()
    # SHA-512 is printed over two consecutive lines.
    digest = re.search(
        r"SHA-512\s*:\s*([0-9a-fA-F]{64})\s*\r?\n\s*:\s*([0-9a-fA-F]{64})",
        text,
    )
    if digest:
        data["current_hash"] = digest.group(1) + digest.group(2)
    return data


def _parse_audit(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    patterns = {
        "total_blocks": r"Total Blocks Evaluated\s*:\s*(\d+)",
        "valid_blocks": r"Valid Blocks\s*:\s*(\d+)",
        "corrupted_blocks": r"Corrupted Blocks\s*:\s*(\d+)",
        "last_valid_hash": r"Last Valid Hash\s*:\s*(\S+)",
        "ruling": r"Security Ruling\s*:\s*(.+)",
        "summary": r"Executive Summary\s*:\s*(.+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            if key in {"total_blocks", "valid_blocks", "corrupted_blocks"}:
                try:
                    value = int(value)
                except ValueError:
                    pass
            data[key] = value
    data["consensus"] = "POSITIVE CONSENSUS" in text.upper()
    return data


# ---------------------------------------------------------------------------
# Engine wrapper
# ---------------------------------------------------------------------------
class BMDEngine:
    """Thin, explicit wrapper around the real BMD CLI and DLL."""

    def __init__(
        self,
        *,
        cli_path: Optional[os.PathLike[str] | str] = None,
        engine_dir: Optional[os.PathLike[str] | str] = None,
        timeout: float = 45.0,
    ) -> None:
        if engine_dir is not None:
            self.engine_dir = Path(engine_dir).resolve()
            self.cli_path = self.engine_dir / "bin" / "bmd_cli.exe"
            self.dll_path = self.engine_dir / "bin" / "bmd_engine.dll"
            self.ffi_dir = self.engine_dir / "python"
        else:
            self.engine_dir = ENGINE_DIR
            self.cli_path = Path(cli_path).resolve() if cli_path else CLI_PATH
            self.dll_path = self.cli_path.parent / "bmd_engine.dll"
            self.ffi_dir = self.engine_dir / "python"
        self.timeout = max(5.0, float(timeout))
        self._ffi: Any = None

    # ------------------------------------------------------------- state
    @property
    def cli_available(self) -> bool:
        return self.cli_path.is_file()

    @property
    def dll_available(self) -> bool:
        return self.dll_path.is_file()

    @property
    def available(self) -> bool:
        return self.cli_available and self.dll_available

    def status(self) -> Dict[str, Any]:
        return {
            "engine_dir": str(self.engine_dir),
            "cli": str(self.cli_path),
            "cli_available": self.cli_available,
            "dll": str(self.dll_path),
            "dll_available": self.dll_available,
            "available": self.available,
            "ffi_dir": str(self.ffi_dir),
        }

    def load_ffi(self) -> Any:
        """Import ``bmd_ffi`` lazily so Orunex starts without the DLL."""
        if self._ffi is not None:
            return self._ffi
        if not self.dll_available:
            raise RuntimeError(
                f"bmd_engine.dll not found at {self.dll_path}. "
                "Build the BMD engine or restore the bin directory."
            )
        ffi_dir = str(self.ffi_dir)
        if ffi_dir not in sys.path:
            sys.path.insert(0, ffi_dir)
        import bmd_ffi  # type: ignore

        self._ffi = bmd_ffi
        return bmd_ffi

    # ------------------------------------------------------------- runner
    def _run(
        self,
        action: str,
        args: Sequence[str],
        *,
        timeout: Optional[float] = None,
        cwd: Optional[os.PathLike[str] | str] = None,
    ) -> BMDResult:
        command = [str(self.cli_path), *[str(arg) for arg in args]]
        started = time.monotonic()
        if not self.cli_available:
            return BMDResult(
                action=action,
                ok=False,
                returncode=-1,
                stderr=f"BMD CLI not found at {self.cli_path}",
                command=command,
            )
        kwargs: Dict[str, Any] = {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": float(timeout or self.timeout),
            "cwd": str(cwd or PROJECT_ROOT),
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            completed = subprocess.run(command, **kwargs)
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            returncode = int(completed.returncode)
            return BMDResult(
                action=action,
                ok=returncode == 0,
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
                duration_s=time.monotonic() - started,
                command=command,
            )
        except subprocess.TimeoutExpired:
            return BMDResult(
                action=action,
                ok=False,
                returncode=-2,
                stderr=f"BMD command timed out after {timeout or self.timeout}s",
                duration_s=time.monotonic() - started,
                command=command,
            )
        except Exception as exc:
            return BMDResult(
                action=action,
                ok=False,
                returncode=-3,
                stderr=f"{type(exc).__name__}: {exc}",
                duration_s=time.monotonic() - started,
                command=command,
            )

    # ------------------------------------------------------------- read ops
    def inspect(self, path: os.PathLike[str] | str) -> BMDResult:
        result = self._run("inspect", ["inspect", str(path)])
        result.data = _parse_inspect(result.stdout)
        return result

    def verify(self, path: os.PathLike[str] | str) -> BMDResult:
        result = self._run("verify", ["verify", str(path)])
        result.data = {"valid": result.returncode == 0}
        if result.returncode == 2:
            result.data["failure"] = (result.stderr or result.stdout).strip()
        return result

    def verify_json(self, path: os.PathLike[str] | str) -> BMDResult:
        # v2.1 canonical form is `verify --json`; `--verify` remains as a
        # backwards-compatible alias in the same binary.
        result = self._run("verify-json", ["verify", "--json", str(path)])
        result.data = _parse_json_output(result.stdout)
        if not result.data:
            result = self._run("verify-json", ["--verify", str(path)])
            result.data = _parse_json_output(result.stdout)
        if "valid" not in result.data:
            result.data["valid"] = bool(
                result.data.get("status") in {"ok", "valid", "verified"}
                or result.data.get("hash_valid")
            )
        return result

    def export_office(self, path: os.PathLike[str] | str) -> BMDResult:
        result = self._run("export-office", ["--export-office", str(path)])
        result.data = _parse_json_output(result.stdout)
        return result

    def audit(self, paths: Sequence[os.PathLike[str] | str]) -> BMDResult:
        files = [str(path) for path in paths]
        result = self._run("audit", ["audit", *files])
        result.data = _parse_audit(result.stdout)
        return result

    def genkey(self) -> BMDResult:
        result = self._run("genkey", ["genkey"])
        text = result.stdout or ""
        seed = re.search(r"(?i)seed[^0-9a-f]*([0-9a-f]{64})", text)
        public_key = re.search(
            r"(?i)(?:public|pub)[^0-9a-f]*([0-9a-f]{64})", text
        )
        result.data = {
            "seed": seed.group(1) if seed else "",
            "public_key": public_key.group(1) if public_key else "",
        }
        return result

    # ------------------------------------------------------------- write ops
    def render(
        self,
        path: os.PathLike[str] | str,
        out_path: Optional[os.PathLike[str] | str] = None,
    ) -> BMDResult:
        args = ["render", str(path)]
        if out_path:
            args.append(str(out_path))
        result = self._run("render", args)
        if result.ok:
            return result
        # The CLI forwards to `python script.py`; if the launcher is not on
        # PATH, call the same script with the current interpreter.
        script = self.ffi_dir / "bmd_viewer_generator.py"
        if not script.is_file():
            return result
        command = [sys.executable, str(script), str(path)]
        if out_path:
            command.append(str(out_path))
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                cwd=str(PROJECT_ROOT),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return BMDResult(
                action="render",
                ok=completed.returncode == 0,
                returncode=int(completed.returncode),
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
                duration_s=time.monotonic() - started,
                command=command,
            )
        except Exception as exc:
            return BMDResult(
                action="render",
                ok=False,
                returncode=-3,
                stderr=f"{type(exc).__name__}: {exc}",
                duration_s=time.monotonic() - started,
                command=command,
            )

    def compile_sign(
        self,
        path: os.PathLike[str] | str,
        *,
        seed: Optional[str] = None,
        role: str = "emisor",
    ) -> BMDResult:
        """Freeze a draft as transfer and sign it as emitter.

        This is the v2.1 ``bmd sign <file> <seed>`` command: it recomputes the
        SHA-512 hash, switches ``draft`` to ``transfer``, stores the Ed25519
        signature and applies the OS read-only lock.  ``role`` is kept for API
        compatibility; the transition always signs as emitter.
        """
        seed_value = str(seed or DEMO_EMITTER_SEED)
        result = self._run("compile-sign", ["sign", str(path), seed_value])
        result.data = _parse_json_output(result.stdout)
        if not result.data:
            result.data = _parse_sign_output(result.stdout)
        result.data.setdefault("status", "ok" if result.ok else "error")
        if result.ok:
            result.data.setdefault("mode", "transfer")
            result.data.setdefault("demo_seed", not bool(seed))
        return result

    def co_sign(
        self,
        path: os.PathLike[str] | str,
        *,
        seed: Optional[str] = None,
        role: str = "receptor",
    ) -> BMDResult:
        """Co-sign a transfer block as receiver (v2.1 ``bmd cosign``).

        The engine only accepts a co-signature when the block declares
        ``max_signatures >= 2``.  ``sign``/``cosign`` set the file read-only,
        so the lock is cleared before the engine writes the co-signature.
        """
        self._make_writable(path)
        seed_value = str(seed or DEMO_RECEIVER_SEED)
        result = self._run("co-sign", ["cosign", str(path), seed_value])
        result.data = _parse_json_output(result.stdout)
        result.data.setdefault("status", "ok" if result.ok else "error")
        if result.ok:
            result.data.setdefault("demo_seed", not bool(seed))
        return result

    def freeze(
        self, path: os.PathLike[str] | str, seed: str
    ) -> BMDResult:
        """Backwards-compatible alias for :meth:`compile_sign`."""
        return self.compile_sign(path, seed=seed)

    def accept(
        self, path: os.PathLike[str] | str, seed: str
    ) -> BMDResult:
        """Backwards-compatible alias for :meth:`co_sign`."""
        return self.co_sign(path, seed=seed)

    def lock(self, path: os.PathLike[str] | str) -> BMDResult:
        """Apply the OS read-only attribute with the real ``bmd lock`` command."""
        return self._run("lock", ["lock", str(path)])

    def seal(
        self, path: os.PathLike[str] | str, key_hex: str
    ) -> BMDResult:
        """Encrypt the payload with ChaCha20 through the DLL (CLI v2.1 has no seal)."""
        return self._seal_with_ffi(path, key_hex, encrypt=True)

    def unseal(
        self, path: os.PathLike[str] | str, key_hex: str
    ) -> BMDResult:
        """Decrypt the payload with ChaCha20 through the DLL."""
        return self._seal_with_ffi(path, key_hex, encrypt=False)

    def _seal_with_ffi(
        self,
        path: os.PathLike[str] | str,
        key_hex: str,
        *,
        encrypt: bool,
    ) -> BMDResult:
        action = "seal" if encrypt else "unseal"
        try:
            key = bytes.fromhex(str(key_hex).strip())
            if len(key) != 32:
                raise ValueError(
                    "key_hex must be 64 hexadecimal characters (32 bytes)"
                )
            self._make_writable(path)
            ffi = self.load_ffi()
            doc = ffi.BMDWrapper.load_file(str(path))
            if encrypt:
                doc.seal(key)
            else:
                doc.unseal(key)
            doc.save(str(path))
            return BMDResult(
                action=action,
                ok=True,
                returncode=0,
                stdout=f"{action}: {path}",
            )
        except Exception as exc:
            return BMDResult(
                action=action,
                ok=False,
                returncode=-3,
                stderr=f"{type(exc).__name__}: {exc}",
            )

    @staticmethod
    def _make_writable(path: os.PathLike[str] | str) -> None:
        """Clear the read-only attribute applied by ``sign``/``cosign``."""
        try:
            if os.name == "nt":
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            else:
                os.chmod(path, 0o644)
        except OSError:
            pass

    # ------------------------------------------------------------- draft API
    def _frontmatter(
        self,
        *,
        block_id: str,
        previous_hash: str,
        mode: str,
        signer_role: str,
        timestamp: int,
        document_type: str,
        jurisdiction: str,
        require_cosigner: bool,
        co_sign_label: str,
        expiry_timestamp: int,
        witnesses_required: int,
        max_signatures: int,
    ) -> str:
        lines = [
            "---",
            f'block_id: "{block_id}"',
            f'previous_hash: "{previous_hash}"',
            f'current_hash: "{ZERO_HASH}"',
            f'mode: "{mode}"',
            f'signer_role: "{signer_role}"',
            f"timestamp: {int(timestamp)}",
            'public_key: ""',
            'signature_layer_2: ""',
            "payload_encrypted: false",
        ]
        if document_type:
            lines.append(f'document_type: "{document_type}"')
        if jurisdiction:
            lines.append(f'jurisdiction: "{jurisdiction}"')
        if expiry_timestamp:
            lines.append(f"expiry_timestamp: {int(expiry_timestamp)}")
        if witnesses_required:
            lines.append(f"witnesses_required: {int(witnesses_required)}")
        if require_cosigner:
            lines.append("require_cosigner: true")
        if co_sign_label:
            lines.append(f'co_sign_label: "{co_sign_label}"')
        if int(max_signatures or 0) > 0:
            lines.append(f'max_signatures: "{int(max_signatures)}"')
        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    def finalize_draft(self, path: os.PathLike[str] | str) -> Dict[str, Any]:
        """Compute the real hash with the engine and persist it.

        Strategy 1 uses the DLL through ``bmd_ffi`` (fast, no subprocess).
        Strategy 2 asks ``bmd_cli.exe inspect`` for ``Computed Hash`` and
        rewrites the frontmatter.  Both are real engine calculations.
        """
        target = Path(path)
        if not target.is_file():
            return {"ok": False, "error": f"File not found: {target}"}

        try:
            ffi = self.load_ffi()
            doc = ffi.BMDWrapper.load_file(str(target))
            buffer = ctypes.create_string_buffer(int(ffi.BMD_HASH_HEX_LEN) + 1)
            ret = ffi._LIB.bmd_compute_hash(doc._doc, buffer)
            if ret != 0:
                raise RuntimeError(
                    f"bmd_compute_hash returned {ret}: "
                    f"{ffi._LIB.bmd_status_string(ret).decode('utf-8', 'replace')}"
                )
            digest = buffer.value.decode("ascii")
            header = doc._doc.contents.header
            address = ctypes.addressof(header) + ffi.BMDHeader.current_hash.offset
            payload = buffer.value
            ctypes.memmove(address, payload, len(payload) + 1)
            doc.save(str(target))
            reloaded = ffi.BMDWrapper.load_file(str(target))
            valid, message = reloaded.verify()
            return {
                "ok": bool(valid),
                "hash": digest,
                "message": str(message),
                "method": "ffi",
            }
        except Exception as ffi_error:
            ffi_message = f"{type(ffi_error).__name__}: {ffi_error}"

        inspected = self.inspect(target)
        digest = str(inspected.data.get("computed_hash") or "")
        if not digest:
            return {
                "ok": False,
                "error": ffi_message,
                "message": "The engine did not return a computed hash.",
            }
        text = target.read_text(encoding="utf-8", errors="replace")
        updated, count = re.subn(
            r'(?m)^current_hash:\s*"[^"]*"',
            f'current_hash: "{digest}"',
            text,
            count=1,
        )
        if count != 1:
            return {
                "ok": False,
                "error": "current_hash line not found",
                "message": ffi_message,
            }
        target.write_text(updated, encoding="utf-8", newline="\n")
        verified = self.verify(target)
        return {
            "ok": bool(verified.ok),
            "hash": digest,
            "message": (verified.stdout or verified.stderr).strip(),
            "method": "cli-inspect",
            "ffi_error": ffi_message,
        }

    def create_draft(
        self,
        path: os.PathLike[str] | str,
        *,
        payload: str,
        block_id: Optional[str] = None,
        previous_hash: Optional[str] = None,
        mode: str = "draft",
        signer_role: str = "emisor",
        timestamp: Optional[int] = None,
        document_type: str = "contract",
        jurisdiction: str = "",
        require_cosigner: bool = False,
        co_sign_label: str = "",
        expiry_timestamp: int = 0,
        witnesses_required: int = 0,
        max_signatures: int = 0,
    ) -> Dict[str, Any]:
        """Write a real .bmd draft and let the engine compute its hash.

        ``max_signatures`` is the v2.1 governance cap: 0 = unlimited,
        1 = emitter-only unilateral, 2 = bilateral (emitter + receiver),
        N = multi-party.  A receiver can only co-sign when the value is 0 or
        greater than the signatures already present.
        """
        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        stamp = int(timestamp or time.time())
        resolved_id = str(block_id or f"0xORUNEX_{stamp}_{_slug(target.stem, 'BMD').upper()[:24]}")
        resolved_previous = str(previous_hash or ZERO_HASH)
        if len(resolved_previous) not in {64, 128}:
            return {
                "ok": False,
                "error": "previous_hash must contain 64 or 128 hexadecimal characters",
            }
        if mode not in {"draft", "transfer"}:
            return {"ok": False, "error": "mode must be 'draft' or 'transfer'"}
        if signer_role not in {"emisor", "emitter", "receptor", "receiver"}:
            return {"ok": False, "error": "signer_role must be emisor or receptor"}

        frontmatter = self._frontmatter(
            block_id=resolved_id,
            previous_hash=resolved_previous,
            mode=mode,
            signer_role="emisor" if signer_role in {"emisor", "emitter"} else "receptor",
            timestamp=stamp,
            document_type=document_type,
            jurisdiction=jurisdiction,
            require_cosigner=bool(require_cosigner),
            co_sign_label=co_sign_label,
            expiry_timestamp=int(expiry_timestamp or 0),
            witnesses_required=int(witnesses_required or 0),
            max_signatures=int(max_signatures or 0),
        )
        body = str(payload or "").strip()
        content = frontmatter + body + ("\n" if not body.endswith("\n") else "")
        target.write_text(content, encoding="utf-8", newline="\n")

        finalized = self.finalize_draft(target)
        return {
            "ok": bool(finalized.get("ok")),
            "path": str(target),
            "block_id": resolved_id,
            "document_type": document_type,
            "mode": mode,
            "max_signatures": int(max_signatures or 0),
            "hash": finalized.get("hash", ""),
            "message": finalized.get("message", ""),
            "method": finalized.get("method", ""),
            "error": finalized.get("error", ""),
        }

    def create_chain(
        self,
        items: Sequence[Mapping[str, Any]],
        *,
        directory: os.PathLike[str] | str,
        prefix: str = "bloque",
    ) -> Dict[str, Any]:
        """Create a hash-linked chain of drafts.

        ``items`` is a sequence of mappings with ``title`` and optional
        ``payload``, ``document_type`` and ``block_id``.  Each child uses the
        parent ``current_hash`` as ``previous_hash``.
        """
        out_dir = Path(directory).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        previous = ZERO_HASH
        created: List[Dict[str, Any]] = []
        for index, item in enumerate(items, start=1):
            title = str(item.get("title") or f"{prefix} {index}")
            body = str(item.get("payload") or f"# {title}\n\nBloque {index} de la cadena.\n")
            path = out_dir / f"{_slug(title, prefix)}_{index:02d}.bmd"
            result = self.create_draft(
                path,
                payload=body,
                block_id=str(item.get("block_id") or f"0xORUNEX_CHAIN_{index:02d}_{int(time.time())}"),
                previous_hash=previous,
                document_type=str(item.get("document_type") or "contract"),
                jurisdiction=str(item.get("jurisdiction") or ""),
                max_signatures=int(item.get("max_signatures") or 0),
            )
            created.append(result)
            if not result.get("ok"):
                return {
                    "ok": False,
                    "created": created,
                    "error": result.get("error") or result.get("message"),
                }
            previous = str(result.get("hash") or "")
        audit = self.audit([item["path"] for item in created])
        return {
            "ok": bool(audit.ok),
            "created": created,
            "audit": audit.to_dict(),
        }


# ---------------------------------------------------------------------------
# Deterministic intent handling
# ---------------------------------------------------------------------------
def _detect_document_type(text: str) -> str:
    lowered = str(text or "").lower()
    # Ignore the file extension and the language name when looking for the
    # document head ("contrato .bmd de servicios" -> "contrato de servicios").
    lowered = re.sub(r"\.bmd\b|blockchain\s*markdown|\bbmd\b", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    for pattern, value in _DOC_HEAD_PATTERNS:
        if re.search(pattern, lowered):
            return value
    for key, value in _DOC_TYPES:
        if re.search(r"\b" + re.escape(key), lowered):
            return value
    return "contract"


def _document_label(document_type: str, lang: str) -> str:
    labels = {
        "contract": ("Contrato", "Contract"),
        "license": ("Contrato de licencia", "License agreement"),
        "nda": ("Acuerdo de confidencialidad", "Non-disclosure agreement"),
        "services": ("Contrato de prestación de servicios", "Services agreement"),
        "testament": ("Testamento", "Testament"),
        "ip_transfer": ("Transferencia de propiedad intelectual", "IP transfer"),
        "declaration": ("Declaración", "Declaration"),
        "decree": ("Decreto", "Decree"),
    }
    es, en = labels.get(document_type, ("Documento", "Document"))
    return _msg(lang, es, en)


def _clean_topic(text: str) -> str:
    value = str(text or "").strip()
    value = re.sub(
        r"(?i)\b(crea|crear|genera|generar|redacta|redactar|haz|hacer|"
        r"escribe|escribir|programa|programar|elabora|elaborar|create|make|"
        r"generate|write|draft|prepare|compose)\b",
        " ",
        value,
    )
    value = re.sub(r"(?i)\.bmd\b|blockchain\s*markdown|\bbmd\b", " ", value)
    value = re.sub(
        r"(?i)^\s*(un|una|unos|unas|el|la|los|las|archivo|documento|a|an|the)\s+",
        " ",
        value,
    )
    value = re.sub(
        r"(?i)^\s*(sobre|acerca\s+de|de|para|titulado|titulada|llamado|llamada|"
        r"about|for|titled|called)\s+",
        " ",
        value,
    )
    value = re.sub(r"\s*\.\s*", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .,:;-\"'")
    return value


def _payload_template(
    *,
    title: str,
    topic: str,
    document_type: str,
    lang: str,
    jurisdiction: str,
) -> str:
    """Build the Markdown payload for a new BMD block.

    Contract-like documents receive a professional, type-specific clause
    skeleton.  Other document types keep the compact generic template.
    """
    if document_type in {"contract", "license", "nda", "services", "ip_transfer"}:
        return _professional_contract_payload(
            title=title,
            topic=topic,
            document_type=document_type,
            lang=lang,
            jurisdiction=jurisdiction,
        )
    return _legacy_payload_template(
        title=title,
        topic=topic,
        document_type=document_type,
        lang=lang,
        jurisdiction=jurisdiction,
    )


def _contract_sections_es(
    document_type: str, topic: str, jurisdiction: str
) -> list[tuple[str, str]]:
    """Spanish clause skeleton for the supported contract families."""
    parties = (
        "- **Emisor:** [Razón social o nombre completo], identificado con "
        "[NIT/ID], con domicilio en [dirección], representado por [nombre y "
        "cargo].\n"
        "- **Receptor:** [Razón social o nombre completo], identificado con "
        "[NIT/ID], con domicilio en [dirección], representado por [nombre y "
        "cargo]."
    )
    background = (
        f"Las partes celebran el presente documento para regular "
        f"{topic or 'la operación declarada'}. El emisor declara ser titular "
        "de los derechos necesarios y el receptor declara contar con capacidad "
        "legal para obligarse. Las partes reconocen que el bloque .bmd, una vez "
        "firmado y congelado, es la fuente única de verdad de sus términos."
    )
    definitions = (
        "Para efectos de este documento: **Documento** es el bloque .bmd y su "
        "payload; **Servicios** o **Activos** son los bienes, derechos o "
        "entregables descritos en el objeto; **Día hábil** es cualquier día "
        "distinto de sábado, domingo o feriado en la jurisdicción aplicable; "
        "**Confidencialidad** es la obligación definida en la cláusula "
        "correspondiente."
    )
    common_tail = [
        (
            "Confidencialidad",
            "Cada parte mantendrá en reserva la información técnica, comercial "
            "y financiera de la otra que reciba con ocasión de este documento, "
            "la usará solo para ejecutar su objeto y la protegerá con el mismo "
            "cuidado que aplica a su propia información confidencial. La "
            "obligación sobrevive a la terminación durante [3/5] años.",
        ),
        (
            "Propiedad intelectual",
            "Cada parte conserva la titularidad de sus derechos preexistentes. "
            "El emisor conserva la titularidad de [software, marca, obra o "
            "activo] hasta que se perfeccione la transferencia o licencia "
            "descrita en este documento. El receptor recibe únicamente los "
            "derechos expresamente otorgados y no adquiere derechos implícitos.",
        ),
        (
            "Declaraciones y garantías",
            "Cada parte declara que: (i) tiene capacidad legal y autorización "
            "para celebrar este documento; (ii) no existe conflicto contractual "
            "que impida su cumplimiento; (iii) la información entregada es "
            "veraz y completa; y (iv) cumplirá las leyes aplicables, incluidas "
            "las de protección de datos y propiedad intelectual.",
        ),
        (
            "Limitación de responsabilidad",
            "Salvo dolo o culpa grave, ninguna parte responderá por daños "
            "indirectos, lucro cesante o pérdida de datos. La responsabilidad "
            "total agregada de cada parte se limitará a [monto o porcentaje] "
            "del valor del documento. Esta limitación no aplica a obligaciones "
            "de confidencialidad, indemnidad o infracción de propiedad "
            "intelectual.",
        ),
        (
            "Indemnización",
            "Cada parte indemnizará a la otra frente a reclamaciones de "
            "terceros derivadas de su incumplimiento, de la infracción de "
            "derechos de propiedad intelectual o del uso no autorizado de la "
            "información confidencial, siempre que la parte indemnizada "
            "notifique la reclamación y permita dirigir su defensa.",
        ),
        (
            "Fuerza mayor",
            "Ninguna parte será responsable por retrasos o incumplimientos "
            "causados por eventos imprevisibles e irresistibles, ajenos a su "
            "control razonable. La parte afectada notificará dentro de [5] días "
            "hábiles y adoptará medidas de mitigación. Si el evento persiste "
            "más de [60] días, cualquiera podrá terminar el documento.",
        ),
        (
            "Notificaciones",
            "Las notificaciones se enviarán por escrito a los correos y "
            "direcciones indicados en la cláusula de partes, con acuse de "
            "recibo o confirmación electrónica. Un cambio de datos debe "
            "notificarse con [5] días hábiles de anticipación.",
        ),
        (
            "Ley aplicable y controversias",
            f"Este documento se rige por las leyes de "
            f"{jurisdiction or '[jurisdicción aplicable]'}. Las partes "
            "intentarán resolver cualquier controversia de buena fe durante "
            "[30] días. Si no lo logran, se someterán a [tribunales ordinarios "
            "o arbitraje] con sede en [ciudad], renunciando a cualquier otro "
            "fuero.",
        ),
        (
            "Disposiciones generales",
            "Este documento reemplaza los acuerdos previos sobre su objeto. "
            "Solo puede modificarse mediante un nuevo bloque .bmd firmado por "
            "ambas partes. La nulidad de una cláusula no afecta las demás. "
            "Ninguna parte puede ceder el documento sin consentimiento escrito "
            "de la otra. El documento se firma electrónicamente y las firmas "
            "Ed25519 se verifican contra el hash SHA-512 del bloque.",
        ),
    ]

    if document_type == "license":
        return [
            ("Partes", parties),
            ("Antecedentes", background),
            ("Definiciones", definitions),
            (
                "Objeto de la licencia",
                f"El emisor otorga al receptor una licencia para usar "
                f"{topic or '[software, obra o activo]'} en los términos de "
                "este documento. La licencia es [exclusiva/no exclusiva], "
                "[transferible/no transferible] y [sublicenciable/no "
                "sublicenciable].",
            ),
            (
                "Derechos otorgados",
                "El receptor puede: (i) instalar y ejecutar el activo en "
                "[número] entornos; (ii) realizar copias de respaldo; y (iii) "
                "usar la documentación asociada. Todo uso no expresamente "
                "autorizado queda prohibido.",
            ),
            (
                "Restricciones",
                "El receptor no puede: (i) modificar, descompilar o hacer "
                "ingeniería inversa salvo autorización legal imperativa; (ii) "
                "redistribuir, vender, alquilar o sublicenciar el activo; "
                "(iii) eliminar avisos de propiedad intelectual; ni (iv) usar "
                "el activo para fines ilícitos o para competir deslealmente.",
            ),
            (
                "Contraprestación y regalías",
                "El receptor pagará [monto] en [moneda] mediante "
                "[transferencia/otro medio] dentro de [plazo]. Las regalías, "
                "si existen, se calcularán sobre [base] a una tasa de [%] y se "
                "liquidarán [periodicidad]. Los pagos vencidos generan "
                "intereses a la tasa máxima permitida.",
            ),
            (
                "Plazo y terminación",
                "La licencia tiene una vigencia de [plazo] desde la fecha de "
                "este documento. Cualquiera de las partes podrá terminarla por "
                "incumplimiento grave no subsanado en [15] días desde la "
                "notificación. A la terminación, el receptor dejará de usar el "
                "activo y certificará su eliminación.",
            ),
            *common_tail,
        ]

    if document_type == "nda":
        return [
            ("Partes", parties),
            ("Antecedentes", background),
            ("Definiciones", definitions),
            (
                "Información confidencial",
                "Comprende toda información técnica, comercial, financiera, "
                "legal o de negocio revelada por una parte a la otra, en "
                "cualquier formato, incluyendo código fuente, algoritmos, "
                "precios, clientes, planes y secretos comerciales. No incluye "
                "información pública, de conocimiento general o recibida "
                "lícitamente de un tercero.",
            ),
            (
                "Obligaciones del receptor",
                "El receptor: (i) usará la información solo para evaluar o "
                "ejecutar la relación comercial; (ii) la divulgará únicamente a "
                "empleados y asesores que la necesiten y estén obligados por "
                "confidencialidad; (iii) aplicará medidas de seguridad "
                "razonables; y (iv) notificará de inmediato cualquier acceso o "
                "uso no autorizado.",
            ),
            (
                "Excepciones",
                "No habrá incumplimiento cuando el receptor: (i) revele la "
                "información por mandato legal, previa notificación al "
                "revelador cuando sea posible; (ii) demuestre que la conocía "
                "antes de la revelación; o (iii) la desarrolle de forma "
                "independiente sin usar la información confidencial.",
            ),
            (
                "Plazo",
                "Este acuerdo entra en vigor en la fecha del documento y "
                "obliga durante [plazo] años. Las obligaciones sobre secretos "
                "comerciales subsisten mientras la información conserve esa "
                "naturaleza.",
            ),
            (
                "Devolución o destrucción",
                "A solicitud del revelador o al terminar el acuerdo, el "
                "receptor devolverá o destruirá la información confidencial y "
                "certificará por escrito su eliminación, salvo copias exigidas "
                "por ley o políticas de respaldo.",
            ),
            (
                "Remedios",
                "El incumplimiento puede causar un daño irreparable. El "
                "revelador podrá solicitar medidas cautelares y la reparación "
                "de los daños, sin perjuicio de otras acciones legales.",
            ),
            *common_tail,
        ]

    if document_type == "services":
        return [
            ("Partes", parties),
            ("Antecedentes", background),
            ("Definiciones", definitions),
            (
                "Objeto y servicios",
                f"El emisor prestará los siguientes servicios: "
                f"{topic or '[descripción de los servicios]'}. El alcance, "
                "las exclusiones, los supuestos y las dependencias se detallan "
                "en el anexo técnico.",
            ),
            (
                "Entregables y aceptación",
                "Los entregables, formatos y fechas se describen en el anexo. "
                "El receptor revisará cada entregable dentro de [10] días "
                "hábiles y lo aceptará o rechazará por escrito con observaciones "
                "concretas. Un entregable no observado en plazo se entiende "
                "aceptado.",
            ),
            (
                "Obligaciones del prestador",
                "El emisor ejecutará los servicios con diligencia, calidad y "
                "personal idóneo; cumplirá los hitos; documentará el trabajo; "
                "informará riesgos y retrasos; y corregirá defectos reportados "
                "dentro de [10] días hábiles.",
            ),
            (
                "Obligaciones del cliente",
                "El receptor entregará información, accesos y aprobaciones "
                "oportunamente; designará un interlocutor; pagará en los plazos "
                "acordados; y no solicitará al emisor actos contrarios a la ley "
                "o a derechos de terceros.",
            ),
            (
                "Precio y pagos",
                "El precio es [monto] en [moneda], pagadero [forma de pago] "
                "contra [factura/hito/entregable]. Los gastos reembolsables "
                "requieren aprobación previa. Los pagos vencidos generan "
                "intereses a la tasa máxima permitida.",
            ),
            (
                "Plazo y terminación",
                "El contrato tiene una vigencia de [plazo] desde su fecha. "
                "Cualquiera podrá terminarlo por incumplimiento grave no "
                "subsanado en [15] días, por insolvencia o por conveniencia con "
                "[30] días de aviso. El receptor pagará los servicios ejecutados "
                "hasta la terminación.",
            ),
            *common_tail,
        ]

    if document_type == "ip_transfer":
        return [
            ("Partes", parties),
            ("Antecedentes", background),
            ("Definiciones", definitions),
            (
                "Activos transferidos",
                "El emisor transfiere al receptor los siguientes activos de "
                "propiedad intelectual: "
                f"{topic or '[software, código, marca, obra, base de datos o know-how]'}, "
                "incluyendo el código fuente, la documentación, los derechos de "
                "autor, las marcas y las solicitudes o registros asociados que "
                "se detallan en el anexo.",
            ),
            (
                "Contraprestación",
                "El receptor pagará [monto] en [moneda] mediante [forma de "
                "pago] dentro de [plazo]. La transferencia se perfecciona con "
                "el pago y la firma del bloque en modo transfer.",
            ),
            (
                "Transferencia de titularidad",
                "El emisor transfiere al receptor todos los derechos "
                "patrimoniales sobre los activos, por el plazo máximo legal y "
                "para todos los territorios. La transferencia incluye el "
                "derecho a reproducir, modificar, distribuir, comunicar "
                "públicamente y sublicenciar. Los derechos morales permanecen "
                "en sus autores cuando la ley no permita su cesión.",
            ),
            (
                "Declaraciones del emisor",
                "El emisor declara ser el único titular de los activos, que "
                "están libres de gravámenes y que no infringen derechos de "
                "terceros. Se obliga a defender al receptor frente a "
                "reclamaciones de titularidad y a entregar los documentos de "
                "registro disponibles.",
            ),
            (
                "Entrega y aceptación",
                "El emisor entregará los activos en [repositorio/medio] dentro "
                "de [plazo]. El receptor verificará la integridad técnica y "
                "jurídica dentro de [15] días hábiles y aceptará o rechazará "
                "por escrito. La aceptación no limita las garantías.",
            ),
            *common_tail,
        ]

    # Generic commercial contract
    return [
        ("Partes", parties),
        ("Antecedentes", background),
        ("Definiciones", definitions),
        (
            "Objeto y alcance",
            f"El emisor se obliga a {topic or '[describir el objeto]'} y el "
            "receptor se obliga a [describir la contraprestación]. El alcance "
            "comprende [entregables, exclusiones y dependencias].",
        ),
        (
            "Obligaciones del emisor",
            "1. Ejecutar el objeto con diligencia y calidad profesional.\n"
            "2. Entregar documentos, accesos y evidencias necesarios.\n"
            "3. Informar por escrito riesgos o retrasos relevantes.\n"
            "4. Mantener la confidencialidad y cumplir la ley aplicable.",
        ),
        (
            "Obligaciones del receptor",
            "1. Pagar la contraprestación en los plazos acordados.\n"
            "2. Entregar información y aprobaciones oportunas.\n"
            "3. Designar un interlocutor y facilitar la ejecución.\n"
            "4. Usar los entregables solo para los fines previstos.",
        ),
        (
            "Entregables y aceptación",
            "Los entregables y fechas se detallan en el anexo. El receptor "
            "revisará cada entregable dentro de [10] días hábiles y lo aceptará "
            "o rechazará por escrito con observaciones concretas. Un entregable "
            "no observado en plazo se entiende aceptado.",
        ),
        (
            "Precio y forma de pago",
            "El precio es [monto] en [moneda], pagadero [forma de pago] contra "
            "[factura/hito/entregable]. Los gastos reembolsables requieren "
            "aprobación previa. Los pagos vencidos generan intereses a la tasa "
            "máxima permitida.",
        ),
        (
            "Plazo y terminación",
            "El contrato tiene una vigencia de [plazo] desde su fecha. "
            "Cualquiera podrá terminarlo por incumplimiento grave no subsanado "
            "en [15] días, por insolvencia o por conveniencia con [30] días de "
            "aviso. El receptor pagará lo ejecutado hasta la terminación.",
        ),
        *common_tail,
    ]


def _contract_sections_en(
    document_type: str, topic: str, jurisdiction: str
) -> list[tuple[str, str]]:
    """English clause skeleton for the supported contract families."""
    parties = (
        "- **Emitter:** [legal name], identified by [tax ID], domiciled at "
        "[address], represented by [name and title].\n"
        "- **Receiver:** [legal name], identified by [tax ID], domiciled at "
        "[address], represented by [name and title]."
    )
    background = (
        f"The parties enter into this document to govern "
        f"{topic or 'the declared operation'}. The emitter represents that it "
        "holds the necessary rights and the receiver represents that it has "
        "legal capacity to be bound. Once signed and frozen, the .bmd block is "
        "the single source of truth for its terms."
    )
    definitions = (
        "For this document: **Document** means the .bmd block and its payload; "
        "**Services** or **Assets** means the goods, rights or deliverables "
        "described in the object; **Business Day** means any day other than "
        "Saturday, Sunday or a public holiday in the applicable jurisdiction; "
        "**Confidentiality** means the obligation defined in the relevant "
        "clause."
    )
    common_tail = [
        (
            "Confidentiality",
            "Each party will keep the other party's technical, commercial and "
            "financial information confidential, use it only to perform this "
            "document and protect it with the same care it applies to its own "
            "confidential information. The obligation survives termination for "
            "[3/5] years.",
        ),
        (
            "Intellectual property",
            "Each party retains its pre-existing rights. The emitter retains "
            "title to [software, trademark, work or asset] until the transfer or "
            "license described here is perfected. The receiver obtains only the "
            "rights expressly granted and no implied rights.",
        ),
        (
            "Representations and warranties",
            "Each party represents that: (i) it has legal capacity and authority "
            "to enter into this document; (ii) no contractual conflict prevents "
            "performance; (iii) the information provided is true and complete; "
            "and (iv) it will comply with applicable law, including data "
            "protection and intellectual property laws.",
        ),
        (
            "Limitation of liability",
            "Except for wilful misconduct or gross negligence, neither party "
            "will be liable for indirect damages, lost profits or data loss. "
            "Each party's aggregate liability is limited to [amount or "
            "percentage] of the document value. This limitation does not apply "
            "to confidentiality, indemnity or intellectual property "
            "infringement obligations.",
        ),
        (
            "Indemnity",
            "Each party will indemnify the other against third-party claims "
            "arising from its breach, intellectual property infringement or "
            "unauthorised use of confidential information, provided the "
            "indemnified party gives notice and allows the indemnifying party to "
            "direct the defence.",
        ),
        (
            "Force majeure",
            "Neither party is liable for delays or failures caused by "
            "unforeseeable events beyond its reasonable control. The affected "
            "party will notify within [5] business days and mitigate. If the "
            "event persists for more than [60] days, either party may terminate.",
        ),
        (
            "Notices",
            "Notices must be in writing to the emails and addresses stated in "
            "the parties clause, with acknowledgement or electronic "
            "confirmation. A change of details must be notified [5] business "
            "days in advance.",
        ),
        (
            "Governing law and disputes",
            f"This document is governed by the laws of "
            f"{jurisdiction or '[applicable jurisdiction]'}. The parties will "
            "attempt to resolve any dispute in good faith for [30] days. If "
            "they fail, they will submit to [courts or arbitration] seated in "
            "[city], waiving any other forum.",
        ),
        (
            "General provisions",
            "This document supersedes prior agreements on its subject. It may "
            "only be amended through a new .bmd block signed by both parties. "
            "If one clause is invalid, the others remain in force. Neither party "
            "may assign without the other's written consent. The document is "
            "electronically signed and the Ed25519 signatures are verified "
            "against the block's SHA-512 hash.",
        ),
    ]

    if document_type == "license":
        return [
            ("Parties", parties),
            ("Background", background),
            ("Definitions", definitions),
            (
                "License grant",
                f"The emitter grants the receiver a license to use "
                f"{topic or '[software, work or asset]'} under this document. "
                "The license is [exclusive/non-exclusive], "
                "[transferable/non-transferable] and "
                "[sublicensable/non-sublicensable].",
            ),
            (
                "Granted rights",
                "The receiver may: (i) install and run the asset in [number] "
                "environments; (ii) make backup copies; and (iii) use the "
                "associated documentation. Any use not expressly authorised is "
                "prohibited.",
            ),
            (
                "Restrictions",
                "The receiver may not: (i) modify, decompile or reverse "
                "engineer the asset except as mandatory law allows; (ii) "
                "redistribute, sell, rent or sublicense it; (iii) remove "
                "intellectual property notices; or (iv) use it for unlawful or "
                "unfairly competitive purposes.",
            ),
            (
                "Fees and royalties",
                "The receiver will pay [amount] in [currency] by [payment "
                "method] within [term]. Royalties, if any, will be calculated on "
                "[base] at [%] and settled [periodicity]. Late payments bear "
                "interest at the maximum lawful rate.",
            ),
            (
                "Term and termination",
                "The license is valid for [term] from the document date. Either "
                "party may terminate for a material breach not cured within "
                "[15] days of notice. On termination, the receiver will stop "
                "using the asset and certify its deletion.",
            ),
            *common_tail,
        ]

    if document_type == "nda":
        return [
            ("Parties", parties),
            ("Background", background),
            ("Definitions", definitions),
            (
                "Confidential information",
                "Includes all technical, commercial, financial, legal or "
                "business information disclosed by one party to the other in any "
                "format, including source code, algorithms, prices, customers, "
                "plans and trade secrets. It excludes public information, "
                "general knowledge or information lawfully received from a third "
                "party.",
            ),
            (
                "Receiver obligations",
                "The receiver will: (i) use the information only to evaluate or "
                "perform the business relationship; (ii) disclose it only to "
                "employees and advisers who need it and are bound by "
                "confidentiality; (iii) apply reasonable security measures; and "
                "(iv) promptly notify any unauthorised access or use.",
            ),
            (
                "Exceptions",
                "No breach occurs where the receiver: (i) discloses the "
                "information under legal compulsion, after notifying the "
                "discloser where possible; (ii) shows it knew the information "
                "before disclosure; or (iii) independently develops it without "
                "using the confidential information.",
            ),
            (
                "Term",
                "This agreement starts on the document date and binds the "
                "parties for [term] years. Trade secret obligations continue "
                "while the information retains that nature.",
            ),
            (
                "Return or destruction",
                "On the discloser's request or termination, the receiver will "
                "return or destroy the confidential information and certify "
                "deletion in writing, except for copies required by law or "
                "backup policies.",
            ),
            (
                "Remedies",
                "A breach may cause irreparable harm. The discloser may seek "
                "injunctive relief and damages, without prejudice to other legal "
                "actions.",
            ),
            *common_tail,
        ]

    if document_type == "services":
        return [
            ("Parties", parties),
            ("Background", background),
            ("Definitions", definitions),
            (
                "Services",
                f"The emitter will provide: "
                f"{topic or '[description of services]'}. The scope, "
                "exclusions, assumptions and dependencies are detailed in the "
                "technical annex.",
            ),
            (
                "Deliverables and acceptance",
                "Deliverables, formats and dates are described in the annex. "
                "The receiver will review each deliverable within [10] business "
                "days and accept or reject it in writing with specific comments. "
                "A deliverable not rejected in time is deemed accepted.",
            ),
            (
                "Emitter obligations",
                "The emitter will perform the services with diligence, quality "
                "and qualified personnel; meet milestones; document the work; "
                "report risks and delays; and correct reported defects within "
                "[10] business days.",
            ),
            (
                "Receiver obligations",
                "The receiver will provide information, access and approvals on "
                "time; appoint a contact person; pay on the agreed terms; and not "
                "ask the emitter to act contrary to law or third-party rights.",
            ),
            (
                "Fees and payment",
                "The fee is [amount] in [currency], payable [payment method] "
                "against [invoice/milestone/deliverable]. Reimbursable expenses "
                "require prior approval. Late payments bear interest at the "
                "maximum lawful rate.",
            ),
            (
                "Term and termination",
                "The agreement is valid for [term] from its date. Either party "
                "may terminate for a material breach not cured within [15] days, "
                "for insolvency or for convenience with [30] days' notice. The "
                "receiver will pay for services performed up to termination.",
            ),
            *common_tail,
        ]

    if document_type == "ip_transfer":
        return [
            ("Parties", parties),
            ("Background", background),
            ("Definitions", definitions),
            (
                "Transferred assets",
                "The emitter transfers the following intellectual property "
                "assets to the receiver: "
                f"{topic or '[software, code, trademark, work, database or know-how]'}, "
                "including source code, documentation, copyrights, trademarks "
                "and associated applications or registrations listed in the "
                "annex.",
            ),
            (
                "Consideration",
                "The receiver will pay [amount] in [currency] by [payment "
                "method] within [term]. The transfer is perfected upon payment "
                "and the signature of the block in transfer mode.",
            ),
            (
                "Transfer of title",
                "The emitter transfers all economic rights in the assets to the "
                "receiver for the maximum legal term and all territories. The "
                "transfer includes the right to reproduce, modify, distribute, "
                "communicate publicly and sublicense. Moral rights remain with "
                "their authors where law does not allow assignment.",
            ),
            (
                "Emitter representations",
                "The emitter represents that it is the sole owner of the assets, "
                "that they are free of encumbrances and that they do not infringe "
                "third-party rights. It will defend the receiver against title "
                "claims and deliver available registration documents.",
            ),
            (
                "Delivery and acceptance",
                "The emitter will deliver the assets in [repository/medium] "
                "within [term]. The receiver will verify technical and legal "
                "integrity within [15] business days and accept or reject in "
                "writing. Acceptance does not limit the warranties.",
            ),
            *common_tail,
        ]

    return [
        ("Parties", parties),
        ("Background", background),
        ("Definitions", definitions),
        (
            "Object and scope",
            f"The emitter agrees to {topic or '[describe the object]'} and the "
            "receiver agrees to [describe the consideration]. The scope includes "
            "[deliverables, exclusions and dependencies].",
        ),
        (
            "Emitter obligations",
            "1. Perform the object with diligence and professional quality.\n"
            "2. Deliver necessary documents, access and evidence.\n"
            "3. Report material risks or delays in writing.\n"
            "4. Maintain confidentiality and comply with applicable law.",
        ),
        (
            "Receiver obligations",
            "1. Pay the consideration on the agreed terms.\n"
            "2. Provide timely information and approvals.\n"
            "3. Appoint a contact person and facilitate performance.\n"
            "4. Use deliverables only for the intended purposes.",
        ),
        (
            "Deliverables and acceptance",
            "Deliverables and dates are detailed in the annex. The receiver will "
            "review each deliverable within [10] business days and accept or "
            "reject it in writing with specific comments. A deliverable not "
            "rejected in time is deemed accepted.",
        ),
        (
            "Price and payment",
            "The price is [amount] in [currency], payable [payment method] "
            "against [invoice/milestone/deliverable]. Reimbursable expenses "
            "require prior approval. Late payments bear interest at the maximum "
            "lawful rate.",
        ),
        (
            "Term and termination",
            "The agreement is valid for [term] from its date. Either party may "
            "terminate for a material breach not cured within [15] days, for "
            "insolvency or for convenience with [30] days' notice. The receiver "
            "will pay for work performed up to termination.",
        ),
        *common_tail,
    ]


def _professional_contract_payload(
    *,
    title: str,
    topic: str,
    document_type: str,
    lang: str,
    jurisdiction: str,
) -> str:
    es = lang != "en"
    label = _document_label(document_type, lang)
    now = datetime.now().strftime("%Y-%m-%d")
    sections = (
        _contract_sections_es(document_type, topic, jurisdiction)
        if es
        else _contract_sections_en(document_type, topic, jurisdiction)
    )
    if es:
        header = f"""# {title}

**Tipo de documento:** {label}
**Jurisdicción:** {jurisdiction or "No especificada"}
**Emitido por:** Orunex · muse-spark
**Fecha:** {now}
**Objeto:** {topic or "la operación declarada"}

> **Nota de uso:** completa los campos entre corchetes antes de firmar. Esta
> plantilla no sustituye la revisión de un abogado en la jurisdicción aplicable.
"""
    else:
        header = f"""# {title}

**Document type:** {label}
**Jurisdiction:** {jurisdiction or "Not specified"}
**Issued by:** Orunex · muse-spark
**Date:** {now}
**Subject:** {topic or "the declared operation"}

> **Usage note:** complete the bracketed fields before signing. This template
> does not replace review by a lawyer in the applicable jurisdiction.
"""
    body = "\n".join(
        f"## {index}. {heading}\n\n{content.strip()}\n"
        for index, (heading, content) in enumerate(sections, start=1)
    )
    return (
        header
        + "\n"
        + body
        + "\n<!-- bmd:parties -->\n<!-- bmd:signatures -->\n<!-- bmd:seal -->\n"
    )


def _legacy_payload_template(
    *,
    title: str,
    topic: str,
    document_type: str,
    lang: str,
    jurisdiction: str,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d")
    label = _document_label(document_type, lang)
    if lang == "en":
        return f"""# {title}

**Document type:** {label}
**Jurisdiction:** {jurisdiction or "Not specified"}
**Issued by:** Orunex · muse-spark
**Date:** {now}
**Subject:** {topic}

## 1. Purpose

This block records {topic or "the declared operation"} as a verifiable
Blockchain Markdown document. Its content is immutable once the block is
frozen in transfer mode.

## 2. Declarations

1. The emitter declares authority over the content and the attached rights.
2. The receiver may verify the SHA-512 digest and the Ed25519 signature
   before accepting the transfer.
3. Any later modification invalidates the canonical hash and is rejected by
   the ledger audit.

## 3. Clauses

### 3.1 Integrity

The canonical hash covers the block identifier, the previous hash, the mode,
the signer role, the timestamp, the public key, the encryption flag and the
payload digest. Verification is performed by the C11 engine, not by this text.

### 3.2 Validity

This document is valid from its timestamp until the expiry date, when one is
declared. If no expiry date is declared, it remains valid indefinitely.

### 3.3 Transfer

Ownership is transferred only when the emitter signs the block and the
receiver adds a valid co-signature over the same immutable hash.

## 4. Evidence

- Engine: BMD Engine v2.1.0 (C11 / FFI / CLI).
- Digest: SHA-512, 128 hexadecimal characters.
- Signature: Ed25519 (RFC 8032).
- Ledger: previous_hash links this block to its parent.

## 5. Acceptance

The parties accept the terms recorded in this block and authorise its
inclusion in the BMD ledger.

<!-- bmd:parties -->
<!-- bmd:signatures -->
<!-- bmd:seal -->
"""
    return f"""# {title}

**Tipo de documento:** {label}
**Jurisdicción:** {jurisdiction or "No especificada"}
**Emitido por:** Orunex · muse-spark
**Fecha:** {now}
**Objeto:** {topic}

## 1. Objeto

Este bloque documenta {topic or "la operación declarada"} como un documento
Blockchain Markdown verificable. Su contenido es inmutable una vez que el
bloque se congela en modo transfer.

## 2. Declaraciones

1. El emisor declara autoridad sobre el contenido y los derechos anexos.
2. El receptor puede verificar el digest SHA-512 y la firma Ed25519 antes de
   aceptar la transferencia.
3. Cualquier modificación posterior invalida el hash canónico y es rechazada
   por la auditoría del ledger.

## 3. Cláusulas

### 3.1 Integridad

El hash canónico cubre el identificador del bloque, el hash anterior, el modo,
el rol del firmante, la marca temporal, la clave pública, el indicador de
cifrado y el digest del payload. La verificación la realiza el motor C11, no
este texto.

### 3.2 Vigencia

Este documento es válido desde su marca temporal hasta la fecha de expiración,
cuando se declare. Si no se declara expiración, permanece vigente de forma
indefinida.

### 3.3 Transferencia

La propiedad se transfiere solo cuando el emisor firma el bloque y el receptor
añade una co-firma válida sobre el mismo hash inmutable.

## 4. Evidencia

- Motor: BMD Engine v2.1.0 (C11 / FFI / CLI).
- Digest: SHA-512, 128 caracteres hexadecimales.
- Firma: Ed25519 (RFC 8032).
- Ledger: previous_hash enlaza este bloque con su padre.

## 5. Aceptación

Las partes aceptan los términos registrados en este bloque y autorizan su
inclusión en el ledger BMD.

<!-- bmd:parties -->
<!-- bmd:signatures -->
<!-- bmd:seal -->
"""


def _artifact(path: str, title: str, summary: str) -> Dict[str, Any]:
    return {
        "path": path,
        "kind": "bmd",
        "label": "BMD",
        "title": title,
        "summary": summary,
    }


def _result(
    *,
    handled: bool,
    intent: str,
    ok: bool,
    message: str,
    lang: str,
    path: str = "",
    artifact: Optional[Dict[str, Any]] = None,
    data: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "handled": handled,
        "intent": intent,
        "ok": bool(ok),
        "message": message,
        "lang": lang,
        "path": path,
        "artifact": artifact,
        "data": dict(data or {}),
    }


def handle_request(
    text: str,
    *,
    out_dir: Optional[os.PathLike[str] | str] = None,
    engine: Optional[BMDEngine] = None,
) -> Optional[Dict[str, Any]]:
    """Handle a concrete BMD order, or return ``None`` for normal chat.

    This is the zero-latency path used by ``src/main.py`` before the model.
    It never raises: engine errors become an ``ok=False`` result with a clear
    message.
    """
    raw = str(text or "").strip()
    if not raw or not _BMD_WORD.search(raw):
        return None
    # A pure question ("¿qué es la firma BMD?") must be answered with the
    # knowledge pack, never turned into a real signature/audit action.
    if _QUESTION_RE.search(raw) and not _EXPLICIT_ACTION_RE.search(raw):
        return None
    lang = _language(raw)
    engine = engine or BMDEngine()
    output_dir = Path(out_dir).resolve() if out_dir else OUTPUT_DIR

    try:
        # ---------------------------------------------------------- verify
        if _VERIFY_RE.search(raw):
            path = _extract_path(raw) or _latest_bmd(output_dir)
            if not path:
                return _result(
                    handled=True,
                    intent="verify",
                    ok=False,
                    lang=lang,
                    message=_msg(
                        lang,
                        "Indica la ruta del archivo .bmd que debo verificar.",
                        "Tell me the path of the .bmd file to verify.",
                    ),
                )
            result = engine.verify(path)
            if result.ok:
                message = _msg(
                    lang,
                    f"Verificación correcta. El bloque **{os.path.basename(path)}** "
                    "es íntegro según el motor BMD.",
                    f"Verification passed. **{os.path.basename(path)}** is intact "
                    "according to the BMD engine.",
                )
            else:
                detail = (result.stderr or result.stdout).strip()
                message = _msg(
                    lang,
                    f"La verificación falló para **{os.path.basename(path)}**. "
                    f"Motor: {detail[:500]}",
                    f"Verification failed for **{os.path.basename(path)}**. "
                    f"Engine: {detail[:500]}",
                )
            return _result(
                handled=True,
                intent="verify",
                ok=result.ok,
                message=message,
                lang=lang,
                path=str(path),
                data=result.to_dict(),
            )

        # --------------------------------------------------------- inspect
        if _INSPECT_RE.search(raw):
            path = _extract_path(raw) or _latest_bmd(output_dir)
            if not path:
                return _result(
                    handled=True,
                    intent="inspect",
                    ok=False,
                    lang=lang,
                    message=_msg(
                        lang,
                        "Indica la ruta del archivo .bmd que debo inspeccionar.",
                        "Tell me the path of the .bmd file to inspect.",
                    ),
                )
            result = engine.inspect(path)
            data = result.data
            valid = bool(data.get("valid"))
            message = _msg(
                lang,
                f"**{os.path.basename(path)}** · bloque `{data.get('block_id', '?')}` · "
                f"modo `{data.get('mode', '?')}` · "
                f"{'válido' if valid else 'inválido'}.\n"
                f"Hash actual: `{data.get('current_hash', '?')}`\n"
                f"Hash calculado: `{data.get('computed_hash', '?')}`",
                f"**{os.path.basename(path)}** · block `{data.get('block_id', '?')}` · "
                f"mode `{data.get('mode', '?')}` · "
                f"{'valid' if valid else 'invalid'}.\n"
                f"Current hash: `{data.get('current_hash', '?')}`\n"
                f"Computed hash: `{data.get('computed_hash', '?')}`",
            )
            return _result(
                handled=True,
                intent="inspect",
                ok=result.ok or bool(data),
                message=message,
                lang=lang,
                path=str(path),
                data=result.to_dict(),
            )

        # ---------------------------------------------------------- render
        if _RENDER_RE.search(raw):
            path = _extract_path(raw) or _latest_bmd(output_dir)
            if not path:
                return _result(
                    handled=True,
                    intent="render",
                    ok=False,
                    lang=lang,
                    message=_msg(
                        lang,
                        "Indica la ruta del archivo .bmd que debo renderizar.",
                        "Tell me the path of the .bmd file to render.",
                    ),
                )
            out_path = str(Path(path).with_suffix(".html"))
            result = engine.render(path, out_path)
            ok = result.ok and os.path.exists(out_path)
            message = _msg(
                lang,
                f"Render HTML {'generado' if ok else 'falló'}: `{out_path}`"
                if ok
                else f"No pude renderizar el bloque: {(result.stderr or result.stdout)[:400]}",
                f"HTML render {'created' if ok else 'failed'}: `{out_path}`"
                if ok
                else f"Could not render the block: {(result.stderr or result.stdout)[:400]}",
            )
            return _result(
                handled=True,
                intent="render",
                ok=ok,
                message=message,
                lang=lang,
                path=out_path if ok else str(path),
                artifact=_artifact(
                    out_path,
                    f"Vista HTML · {Path(path).stem}",
                    "Documento .bmd renderizado como HTML standalone.",
                )
                if ok
                else None,
                data=result.to_dict(),
            )

        # ---------------------------------------------------------- export
        if _EXPORT_RE.search(raw) and not _CREATE_VERBS.search(raw):
            path = _extract_path(raw) or _latest_bmd(output_dir)
            if not path:
                return _result(
                    handled=True,
                    intent="export",
                    ok=False,
                    lang=lang,
                    message=_msg(
                        lang,
                        "Indica la ruta del archivo .bmd que debo exportar.",
                        "Tell me the path of the .bmd file to export.",
                    ),
                )
            result = engine.export_office(path)
            data = result.data
            message = _msg(
                lang,
                f"Metadatos BMD exportados para **{os.path.basename(path)}**: "
                f"estado `{data.get('status', '?')}`, modo `{data.get('mode', '?')}`, "
                f"doble firma `{data.get('dual_signed', False)}`.\n"
                "Puedo convertir este bloque en Word, Excel o PowerPoint con "
                "Artifact Studio si lo pides.",
                f"BMD metadata exported for **{os.path.basename(path)}**: "
                f"status `{data.get('status', '?')}`, mode `{data.get('mode', '?')}`, "
                f"dual signed `{data.get('dual_signed', False)}`.\n"
                "I can turn this block into Word, Excel or PowerPoint with "
                "Artifact Studio on request.",
            )
            return _result(
                handled=True,
                intent="export",
                ok=result.ok,
                message=message,
                lang=lang,
                path=str(path),
                data=result.to_dict(),
            )

        # ----------------------------------------------------------- audit
        if _AUDIT_RE.search(raw):
            path = _extract_path(raw)
            if path:
                paths = [path]
            else:
                candidates = sorted(
                    output_dir.rglob("*.bmd"),
                    key=lambda item: item.stat().st_mtime,
                )
                paths = [str(item) for item in candidates]
            if not paths:
                return _result(
                    handled=True,
                    intent="audit",
                    ok=False,
                    lang=lang,
                    message=_msg(
                        lang,
                        "No encontré archivos .bmd para auditar. Indica la ruta.",
                        "I found no .bmd files to audit. Please give me the path.",
                    ),
                )
            result = engine.audit(paths)
            data = result.data
            ok = bool(data.get("consensus"))
            message = _msg(
                lang,
                f"Auditoría de {len(paths)} bloque(s): "
                f"{data.get('valid_blocks', 0)} válidos, "
                f"{data.get('corrupted_blocks', 0)} corruptos. "
                f"Veredicto: **{data.get('ruling', 'sin veredicto')}**.",
                f"Audit of {len(paths)} block(s): "
                f"{data.get('valid_blocks', 0)} valid, "
                f"{data.get('corrupted_blocks', 0)} corrupted. "
                f"Ruling: **{data.get('ruling', 'no ruling')}**.",
            )
            return _result(
                handled=True,
                intent="audit",
                ok=ok,
                message=message,
                lang=lang,
                path=str(paths[0]) if len(paths) == 1 else "",
                data=result.to_dict(),
            )

        # ---------------------------------------------------------- co-sign
        if _COSIGN_RE.search(raw):
            path = _extract_path(raw) or _latest_bmd(output_dir)
            if not path:
                return _result(
                    handled=True,
                    intent="co-sign",
                    ok=False,
                    lang=lang,
                    message=_msg(
                        lang,
                        "Indica la ruta del archivo .bmd que debo co-firmar.",
                        "Tell me the path of the .bmd file to co-sign.",
                    ),
                )
            result = engine.co_sign(path)
            data = result.data
            ok = result.ok and str(data.get("status", "")).lower() == "ok"
            message = _msg(
                lang,
                f"Co-firma {'aplicada' if ok else 'falló'} en "
                f"**{os.path.basename(path)}**."
                + (f"\nReceptor: `{data.get('receiver_pubkey', '')[:32]}...`" if ok else
                   f"\nMotor: {(result.stderr or result.stdout)[:400]}"),
                f"Co-sign {'applied' if ok else 'failed'} on "
                f"**{os.path.basename(path)}**."
                + (f"\nReceiver: `{data.get('receiver_pubkey', '')[:32]}...`" if ok else
                   f"\nEngine: {(result.stderr or result.stdout)[:400]}"),
            )
            return _result(
                handled=True,
                intent="co-sign",
                ok=ok,
                message=message,
                lang=lang,
                path=str(path),
                data=result.to_dict(),
            )

        # ------------------------------------------------------------- sign
        if _SIGN_RE.search(raw):
            path = _extract_path(raw) or _latest_bmd(output_dir)
            if not path:
                return _result(
                    handled=True,
                    intent="compile-sign",
                    ok=False,
                    lang=lang,
                    message=_msg(
                        lang,
                        "Indica la ruta del archivo .bmd que debo firmar.",
                        "Tell me the path of the .bmd file to sign.",
                    ),
                )
            result = engine.compile_sign(path)
            data = result.data
            ok = result.ok and str(data.get("status", "")).lower() == "ok"
            message = _msg(
                lang,
                f"Bloque {'firmado y congelado' if ok else 'no firmado'}: "
                f"**{os.path.basename(path)}**."
                + (f"\nModo: `{data.get('mode', 'transfer')}` · hash `{data.get('current_hash', '')[:24]}...`"
                   if ok else f"\nMotor: {(result.stderr or result.stdout)[:400]}"),
                f"Block {'signed and frozen' if ok else 'not signed'}: "
                f"**{os.path.basename(path)}**."
                + (f"\nMode: `{data.get('mode', 'transfer')}` · hash `{data.get('current_hash', '')[:24]}...`"
                   if ok else f"\nEngine: {(result.stderr or result.stdout)[:400]}"),
            )
            return _result(
                handled=True,
                intent="compile-sign",
                ok=ok,
                message=message,
                lang=lang,
                path=str(path),
                data=result.to_dict(),
            )

        # ----------------------------------------------------------- create
        if _CREATE_VERBS.search(raw):
            topic = _clean_topic(raw)
            document_type = _detect_document_type(raw)
            title = (
                topic[:1].upper() + topic[1:]
                if topic
                else _document_label(document_type, lang)
            )
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bmd_{_slug(topic or document_type, 'documento')}_{stamp}.bmd"
            path = output_dir / filename
            payload = _payload_template(
                title=title,
                topic=topic,
                document_type=document_type,
                lang=lang,
                jurisdiction="",
            )
            bilateral = document_type in {
                "contract",
                "license",
                "nda",
                "services",
                "ip_transfer",
            }
            result = engine.create_draft(
                path,
                payload=payload,
                document_type=document_type,
                require_cosigner=bilateral,
                co_sign_label=_msg(
                    lang, "Aceptar y co-firmar", "Accept and co-sign"
                ),
                max_signatures=2 if bilateral else 1,
            )
            ok = bool(result.get("ok"))
            message = _msg(
                lang,
                f"Creé el bloque BMD **{filename}** en modo borrador y el motor "
                f"calculó su hash SHA-512.\n`{result.get('hash', '')}`\n"
                + (
                    "Es un documento bilateral (`max_signatures: 2`): puedo "
                    "firmarlo como emisor y luego co-firmarlo como receptor.\n"
                    if bilateral
                    else "Es un documento unilateral (`max_signatures: 1`): "
                    "solo requiere la firma del emisor.\n"
                )
                + "Puedes pedirme que lo verifique, lo renderice, lo firme o lo "
                "audite junto con otros bloques.",
                f"I created the BMD block **{filename}** in draft mode and the "
                f"engine computed its SHA-512 hash.\n`{result.get('hash', '')}`\n"
                + (
                    "It is a bilateral document (`max_signatures: 2`): I can "
                    "sign it as emitter and then co-sign it as receiver.\n"
                    if bilateral
                    else "It is a unilateral document (`max_signatures: 1`): "
                    "only the emitter signature is required.\n"
                )
                + "You can ask me to verify it, render it, sign it or audit it "
                "together with other blocks.",
            )
            if not ok:
                message = _msg(
                    lang,
                    f"No pude crear el bloque BMD: {result.get('error') or result.get('message')}",
                    f"Could not create the BMD block: {result.get('error') or result.get('message')}",
                )
            return _result(
                handled=True,
                intent="create",
                ok=ok,
                message=message,
                lang=lang,
                path=str(path),
                artifact=_artifact(
                    str(path),
                    f"Bloque BMD · {title}",
                    f"{_document_label(document_type, lang)} en modo borrador, "
                    "hash calculado por el motor C11.",
                )
                if ok
                else None,
                data=result,
            )

        # "qué es BMD" and similar questions: let the model answer with the
        # FAISS knowledge pack instead of forcing an action.
        if _EXPLAIN_RE.search(raw):
            return None
        return None
    except Exception as exc:
        return _result(
            handled=True,
            intent="error",
            ok=False,
            lang=lang,
            message=_msg(
                lang,
                f"El motor BMD devolvió un error inesperado: {type(exc).__name__}: {exc}",
                f"The BMD engine returned an unexpected error: {type(exc).__name__}: {exc}",
            ),
        )


# ---------------------------------------------------------------------------
# [BMD: ...] tag support for os_executor
# ---------------------------------------------------------------------------
_TAG_RE = re.compile(r"\[BMD:\s*([^\]]+)\]", re.IGNORECASE)


def parse_bmd_tags(text: str) -> List[Tuple[str, str, str]]:
    """Parse ``[BMD: action | path | extra]`` tags.

    Returns a list of ``(action, path, extra)`` tuples.  The path may be empty
    when the action is ``audit`` (audit all generated blocks) or ``create``
    (the engine generates the filename).
    """
    tags: List[Tuple[str, str, str]] = []
    for match in _TAG_RE.finditer(str(text or "")):
        parts = [part.strip() for part in match.group(1).split("|")]
        action = (parts[0] if parts else "").strip().lower().replace("_", "-")
        path = parts[1] if len(parts) > 1 else ""
        extra = "|".join(parts[2:]).strip() if len(parts) > 2 else ""
        if action:
            tags.append((action, path, extra))
    return tags


def execute_tag(
    action: str,
    path: str = "",
    extra: str = "",
    *,
    engine: Optional[BMDEngine] = None,
) -> Dict[str, Any]:
    """Execute one parsed BMD tag and return a JSON-friendly result."""
    engine = engine or BMDEngine()
    action = str(action or "").strip().lower().replace("_", "-")
    path = str(path or "").strip()
    extra = str(extra or "").strip()

    if action in {"create", "crear", "new"}:
        text = f"crea un .bmd sobre {extra or path or 'documento verificado'}"
        return handle_request(text, engine=engine) or {
            "handled": False,
            "ok": False,
            "message": "No pude interpretar la creación BMD.",
        }

    if not path:
        path = _latest_bmd()
    if not path:
        return {
            "handled": True,
            "intent": action,
            "ok": False,
            "message": "No hay archivos .bmd disponibles. Indica la ruta.",
        }

    if action in {"verify", "verificar", "validate"}:
        result = engine.verify(path)
        return {
            "handled": True,
            "intent": "verify",
            "ok": result.ok,
            "message": (
                f"BMD verify: {'OK' if result.ok else 'FAILED'} · {os.path.basename(path)}"
            ),
            "path": path,
            "data": result.to_dict(),
        }
    if action in {"inspect", "inspeccionar"}:
        result = engine.inspect(path)
        return {
            "handled": True,
            "intent": "inspect",
            "ok": result.ok or bool(result.data),
            "message": f"BMD inspect: {result.data.get('block_id', '?')}",
            "path": path,
            "data": result.to_dict(),
        }
    if action in {"render", "renderizar"}:
        out_path = extra or str(Path(path).with_suffix(".html"))
        result = engine.render(path, out_path)
        return {
            "handled": True,
            "intent": "render",
            "ok": result.ok and os.path.exists(out_path),
            "message": f"BMD render: {out_path}",
            "path": out_path,
            "data": result.to_dict(),
        }
    if action in {"export", "export-office", "office"}:
        result = engine.export_office(path)
        return {
            "handled": True,
            "intent": "export",
            "ok": result.ok,
            "message": f"BMD export-office: {result.data.get('status', '?')}",
            "path": path,
            "data": result.to_dict(),
        }
    if action in {"audit", "auditar"}:
        if path:
            files = [
                part.strip()
                for part in re.split(r"[,;]", path)
                if part.strip()
            ]
        else:
            files = [str(item) for item in OUTPUT_DIR.rglob("*.bmd")]
        result = engine.audit(files)
        return {
            "handled": True,
            "intent": "audit",
            "ok": bool(result.data.get("consensus")),
            "message": f"BMD audit: {result.data.get('ruling', 'no ruling')}",
            "path": path,
            "data": result.to_dict(),
        }
    if action in {"sign", "compile-sign", "firmar", "freeze"}:
        result = engine.compile_sign(path, seed=extra or None)
        return {
            "handled": True,
            "intent": "compile-sign",
            "ok": result.ok,
            "message": f"BMD compile-sign: {'OK' if result.ok else 'FAILED'}",
            "path": path,
            "data": result.to_dict(),
        }
    if action in {"co-sign", "cosign", "cofirmar"}:
        result = engine.co_sign(path, seed=extra or None)
        return {
            "handled": True,
            "intent": "co-sign",
            "ok": result.ok,
            "message": f"BMD co-sign: {'OK' if result.ok else 'FAILED'}",
            "path": path,
            "data": result.to_dict(),
        }
    return {
        "handled": True,
        "intent": action,
        "ok": False,
        "message": f"Acción BMD no reconocida: {action}",
        "path": path,
    }


def status() -> Dict[str, Any]:
    """Diagnostics used by ``app.py --check`` and the UI."""
    engine = BMDEngine()
    result = engine.status()
    try:
        from .bmd_knowledge import BMD_KNOWLEDGE, BMD_KNOWLEDGE_VERSION

        result["knowledge_entries"] = len(BMD_KNOWLEDGE)
        result["knowledge_version"] = BMD_KNOWLEDGE_VERSION
    except Exception as exc:
        result["knowledge_error"] = f"{type(exc).__name__}: {exc}"
    return result


__all__ = [
    "BMDEngine",
    "BMDResult",
    "ENGINE_DIR",
    "OUTPUT_DIR",
    "execute_tag",
    "handle_request",
    "parse_bmd_tags",
    "status",
]
