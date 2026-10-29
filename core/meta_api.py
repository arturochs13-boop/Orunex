"""Unified Meta API client — Meta Muse is the ONLY brain.

All reasoning, multimodal (vision/text) analysis and decision-making in
this project goes through this client.  No other LLM, local model or
heuristic engine is allowed to make semantic decisions:

* FAISS only stores/recalls vectors (deterministic hashing, not a model).
* ADB / Simplex / VS Code bridges only transport bytes and commands.
* Risk arithmetic in paper trading only *enforces* limits Muse must respect.

The primary model is configurable (``META_MODEL``) and defaults to Muse
Wonder, the stronger long-horizon model.  Muse Spark remains the fast model
for routing, extraction and screen vision.  Both are Meta Muse models; no
non-Muse provider is accepted.

Endpoint contract (OpenAI-compatible, same as the production Orunex app):
``POST {META_API_BASE}/chat/completions`` with a Bearer ``META_API_KEY``.
"""

from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

import requests

from .config import Settings, get_settings
from .events import BRAIN, META, EventBus

MUSE_PREFIX = "muse-"
MUSE_SPARK = "muse-spark"  # kept for compatibility with older callers
MUSE_WONDER = "muse-wonder"


class MetaNotConfigured(RuntimeError):
    """Raised when META_API_KEY / model are missing or invalid."""


class MetaAPIError(RuntimeError):
    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class MetaResponseError(RuntimeError):
    """Raised when Muse answers but not in the requested shape."""


def _image_part(image: bytes | str | Path) -> dict[str, Any]:
    if isinstance(image, (bytes, bytearray)):
        url = "data:image/png;base64," + base64.b64encode(bytes(image)).decode("ascii")
    elif isinstance(image, Path) or (isinstance(image, str) and Path(str(image)).exists()):
        data = Path(image).read_bytes()
        url = "data:image/png;base64," + base64.b64encode(data).decode("ascii")
    else:
        url = str(image)  # already a data:/http(s): URL
    return {"type": "image_url", "image_url": {"url": url}}


class MetaAPIClient:
    """Thin, retrying, JSON-aware client for Meta Muse models."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        bus: Optional[EventBus] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.bus = bus
        self.session = session or requests.Session()
        self.model = (self.settings.meta_model or MUSE_WONDER).strip()
        if not self.model.lower().startswith(MUSE_PREFIX):
            raise MetaNotConfigured(
                f"Refusing non-Muse model {self.model!r}: this agent uses Meta Muse only."
            )
        self.endpoint = self.settings.meta_api_base.rstrip("/")
        if not self.endpoint.endswith("/chat/completions"):
            self.endpoint += "/chat/completions"

    # ------------------------------------------------------------------ state
    @property
    def configured(self) -> bool:
        return bool(self.settings.meta_api_key)

    def _log(self, message: str, *, level: str = "INFO", next_stage: str = "") -> None:
        if self.bus:
            self.bus.log(META, message, level=level, next_stage=next_stage)

    def _require_configured(self) -> None:
        if not self.configured:
            raise MetaNotConfigured("META_API_KEY is not configured. Set it in .env.")

    # ------------------------------------------------------------- low level
    def chat(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        reasoning_effort: Optional[str] = None,
        model: Optional[str] = None,
        retries: int = 3,
    ) -> str:
        """Send a chat completion and return the assistant text.

        ``model`` and ``reasoning_effort`` are optional per-call overrides.
        The defaults come from :class:`Settings`; this lets the app use Muse
        Wonder for deep reasoning while keeping Muse Spark for fast routing
        and vision without creating a second global client.
        """
        self._require_configured()
        selected_model = (model or self.model).strip()
        if not selected_model.lower().startswith(MUSE_PREFIX):
            raise MetaNotConfigured(
                f"Refusing non-Muse model {selected_model!r}: this agent uses Meta Muse only."
            )
        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": list(messages),
            "max_tokens": int(max_tokens or self.settings.meta_max_tokens),
            "temperature": float(
                self.settings.meta_temperature if temperature is None else temperature
            ),
        }
        effort = (
            (reasoning_effort or self.settings.meta_reasoning_effort or "")
            .strip()
            .lower()
        )
        if effort:
            payload["reasoning_effort"] = effort
        headers = {
            "Authorization": f"Bearer {self.settings.meta_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        def next_effort(value: str) -> str:
            """Lower effort only after the token budget is already maxed."""
            if value in {"max", "xhigh", "high"}:
                return "medium"
            if value == "medium":
                return "low"
            return value

        last_error: Optional[Exception] = None
        budget = int(max_tokens or self.settings.meta_max_tokens)
        for attempt in range(1, max(1, retries) + 1):
            payload["max_tokens"] = budget
            try:
                started = time.monotonic()
                response = self.session.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.settings.meta_timeout,
                )
                elapsed = time.monotonic() - started
                if response.status_code == 200:
                    data = response.json()
                    finish = self._finish_reason(data)
                    try:
                        text = self._extract_text(data)
                    except MetaResponseError:
                        usage = data.get("usage") or {}
                        reasoning_tokens = 0
                        try:
                            reasoning_tokens = int(
                                ((usage.get("completion_tokens_details") or {}).get(
                                    "reasoning_tokens"
                                ))
                                or 0
                            )
                        except (TypeError, ValueError):
                            pass
                        if attempt < retries:
                            # Muse spent the whole budget on hidden reasoning.
                            # Raise the budget first and keep the requested
                            # effort: lowering effort on the first retry was
                            # making answers noticeably shallower.
                            if budget < 8192:
                                budget = min(8192, max(budget * 2, 2048))
                                self._log(
                                    f"Muse returned no visible text "
                                    f"(finish={finish or 'unknown'}, "
                                    f"reasoning_tokens={reasoning_tokens}); "
                                    f"retrying with max_tokens={budget} "
                                    f"and reasoning_effort={payload.get('reasoning_effort', 'default')}",
                                    level="WARN",
                                )
                                continue
                            lowered = next_effort(str(payload.get("reasoning_effort") or ""))
                            if lowered and lowered != payload.get("reasoning_effort"):
                                payload["reasoning_effort"] = lowered
                                self._log(
                                    f"Muse still returned no visible text at "
                                    f"max_tokens={budget}; last-resort retry with "
                                    f"reasoning_effort={lowered}",
                                    level="WARN",
                                )
                                continue
                        raise

                    # A response can contain text and still be cut off. This
                    # happened with the trading JSON: the rationale ended in
                    # the middle of a string, so parse_json_object failed.
                    # Widen the budget first; only lower effort at the hard
                    # token ceiling.
                    if finish == "length":
                        if attempt < retries:
                            if budget < 8192:
                                budget = min(8192, max(budget * 2, 2048))
                                self._log(
                                    f"Muse answer truncated (finish=length, "
                                    f"{len(text)} chars); retrying with "
                                    f"max_tokens={budget} "
                                    f"and reasoning_effort={payload.get('reasoning_effort', 'default')}",
                                    level="WARN",
                                )
                                continue
                            lowered = next_effort(str(payload.get("reasoning_effort") or ""))
                            if lowered and lowered != payload.get("reasoning_effort"):
                                payload["reasoning_effort"] = lowered
                                self._log(
                                    f"Muse answer still truncated at "
                                    f"max_tokens={budget}; last-resort retry with "
                                    f"reasoning_effort={lowered}",
                                    level="WARN",
                                )
                                continue
                        raise MetaResponseError(
                            "Muse response was truncated "
                            f"(finish_reason=length, {len(text)} chars) even "
                            f"after max_tokens={budget}."
                        )

                    self._log(
                        f"Muse {selected_model} replied in {elapsed:.1f}s "
                        f"({len(text)} chars, effort={payload.get('reasoning_effort', 'default')})"
                    )
                    return text
                message = self._error_message(response)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < retries:
                    wait = min(2.0 * attempt, 8.0)
                    self._log(
                        f"HTTP {response.status_code}, retry {attempt} in {wait:.0f}s",
                        level="WARN",
                    )
                    time.sleep(wait)
                    continue
                hint = ""
                if response.status_code in {400, 404} and "model" in message.lower():
                    hint = (
                        " Hint: if your Meta tenant exposes the deployment as "
                        "'muse-wonder-1.0' or 'muse-spark-1.3', set META_MODEL "
                        "to that exact value in .env."
                    )
                raise MetaAPIError(
                    f"Meta API HTTP {response.status_code}: {message or 'request failed'}{hint}",
                    status=response.status_code,
                )
            except MetaAPIError:
                raise
            except MetaResponseError:
                raise
            except Exception as exc:  # network, timeout, malformed JSON
                last_error = exc
                if attempt < retries:
                    time.sleep(min(2.0 * attempt, 8.0))
                    continue
        raise MetaAPIError(f"Meta API unreachable: {type(last_error).__name__}: {last_error}")

    @staticmethod
    def _finish_reason(data: Any) -> str:
        try:
            return str(
                ((data.get("choices") or [{}])[0] or {}).get("finish_reason") or ""
            )
        except Exception:
            return ""

    @staticmethod
    def _extract_text(data: Any) -> str:
        if not isinstance(data, dict):
            raise MetaResponseError("Meta API returned a non-object payload.")
        choices = data.get("choices") or []
        if not choices:
            raise MetaResponseError("Meta API returned no choices.")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            content = "\n".join(
                str(block.get("text", "")).strip()
                for block in content
                if isinstance(block, dict) and block.get("text")
            ).strip()
        if not isinstance(content, str) or not content.strip():
            raise MetaResponseError("Meta API returned empty content.")
        return content.strip()

    @staticmethod
    def _error_message(response: requests.Response) -> str:
        try:
            body = response.json()
            error = body.get("error") if isinstance(body, dict) else None
            if isinstance(error, dict):
                return str(error.get("message") or error.get("type") or "")[:400]
            if error:
                return str(error)[:400]
        except Exception:
            pass
        try:
            return response.text.strip()[:400]
        except Exception:
            return ""

    # ------------------------------------------------------------- high level
    def reason_text(
        self,
        prompt: str,
        *,
        system: str = "",
        images: Optional[Iterable[bytes | str | Path]] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        """Free-form reasoning (optionally multimodal)."""
        content: Any = prompt
        image_list = list(images or [])
        if image_list:
            content = [{"type": "text", "text": prompt}] + [
                _image_part(image) for image in image_list
            ]
        messages: list[dict[str, Any]] = []
        if system.strip():
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})
        self._log(
            f"Reasoning with {(model or self.model)} (images={len(image_list)})",
            next_stage=BRAIN,
        )
        return self.chat(
            messages,
            max_tokens=max_tokens,
            model=model,
            reasoning_effort=reasoning_effort,
        )

    def reason_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str,
        images: Optional[Iterable[bytes | str | Path]] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> dict[str, Any]:
        """Ask Muse for exactly one JSON object and parse it defensively."""
        instruction = (
            f"{user}\n\nRespond with ONE JSON object only, no markdown fences, "
            f"matching this schema:\n{schema_hint}"
        )
        raw = self.reason_text(
            instruction,
            system=system,
            images=images,
            max_tokens=max_tokens,
            model=model,
            reasoning_effort=reasoning_effort,
        )
        return parse_json_object(raw)

    def analyze_image(
        self,
        image: bytes | str | Path,
        prompt: str,
        *,
        system: str = "You are Muse, a precise multimodal UI analyst.",
        max_tokens: Optional[int] = 2400,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> dict[str, Any]:
        """Multimodal diagnosis used by the Android bugfix flow."""
        return self.reason_json(
            system=system,
            user=prompt,
            images=[image],
            max_tokens=max_tokens,
            model=model,
            reasoning_effort=reasoning_effort,
            schema_hint=(
                '{"has_error": bool, "severity": "none|low|medium|high|critical", '
                '"screen": str, "component": str, "visible_text": [str], '
                '"suspected_cause": str, "search_query": str, "confidence": 0.0}'
            ),
        )


def parse_json_object(raw: str) -> dict[str, Any]:
    """Extract the first JSON object from a model reply, or raise."""
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except Exception:
        pass
    start, depth = -1, 0
    for index, char in enumerate(text):
        if char == "{":
            if start < 0:
                start = index
            depth += 1
        elif char == "}" and start >= 0:
            depth -= 1
            if depth == 0:
                try:
                    value = json.loads(text[start : index + 1])
                    if isinstance(value, dict):
                        return value
                except Exception:
                    break
    raise MetaResponseError(f"Muse did not return a JSON object: {text[:240]!r}")
