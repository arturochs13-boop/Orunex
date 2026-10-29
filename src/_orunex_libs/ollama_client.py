"""Meta Model API inference client for Orunex.

The module keeps the historic ``ollama_client`` function names so the existing
agents and workers do not need to change.  Inference is now routed to Meta's
hosted Model API instead of a local GGUF file.

The API key is read from the environment (``META_API_KEY`` by default).  It is
never stored in this file or in the public repository.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from typing import Any, Iterable, Optional

import requests


DEFAULT_API_BASE = "https://api.meta.ai/v1"
# Muse Wonder is the stronger long-horizon reasoning model; Muse Spark stays
# available through META_FAST_MODEL for routing, extraction and vision.
DEFAULT_MODEL = "muse-wonder-1.0"
DEFAULT_TIMEOUT = 120
DEFAULT_MAX_TOKENS = 8192
DEFAULT_REASONING_EFFORT = "high"
MAX_TOKEN_BUDGET = 8192
DEFAULT_EMBEDDING_DIMENSION = 384

# Compatibility with UI code that used to inspect the local model path.
_MODEL_PATH = ""
_MODEL_INSTANCE = None

_API_KEY_ENV_VARS = ("META_API_KEY", "MODEL_API_KEY", "META_AI_API_KEY")
_API_BASE_ENV_VARS = ("META_API_BASE", "META_API_ENDPOINT", "META_AI_ENDPOINT")
_MODEL_ENV_VARS = ("META_MODEL", "ORUNEX_MODEL")


def get_api_key() -> str:
    """Return the configured Meta Model API key without logging it.

    Delegates to :mod:`meta_credentials` so a ``pythonw`` launch finds the
    Windows user key even when the shortcut did not inherit a shell variable.
    """
    try:
        from _orunex_libs.meta_credentials import get_api_key as _resolve

        value = _resolve()
        if value:
            return value
    except Exception:
        pass

    for name in _API_KEY_ENV_VARS:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value

    # Optional fallback for users who prefer the existing config file.
    try:
        from _orunex_libs import config_manager

        value = config_manager.get_val("meta_api_key")
        if isinstance(value, str) and value.strip():
            return value.strip()
    except Exception:
        pass
    return ""


def get_api_base() -> str:
    """Return the Meta Model API base URL, without a trailing slash."""
    for name in _API_BASE_ENV_VARS:
        value = (os.environ.get(name) or "").strip()
        if value:
            base = value.rstrip("/")
            if base.endswith("/chat/completions"):
                base = base[: -len("/chat/completions")]
            return base
    return DEFAULT_API_BASE


def get_chat_endpoint() -> str:
    return get_api_base().rstrip("/") + "/chat/completions"


def resolve_model(model: Optional[str] = None) -> str:
    """Resolve Orunex's legacy model aliases to a Meta Model API model.

    An explicit, non-legacy model wins over ``META_MODEL`` so callers can use
    Muse Spark for a fast router/vision call while the primary brain stays on
    Muse Wonder.  Legacy names such as ``orunex_v37`` still resolve through the
    environment for backwards compatibility.
    """
    candidate = (model or "").strip()
    if candidate and not candidate.lower().startswith("orunex"):
        return candidate

    for name in _MODEL_ENV_VARS:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value

    return DEFAULT_MODEL


def get_api_model() -> str:
    return resolve_model()


def is_available() -> bool:
    """True when a key is configured; this does not make a network request."""
    return bool(get_api_key())


def get_status() -> dict[str, Any]:
    source = "missing"
    try:
        from _orunex_libs.meta_credentials import get_api_key_source

        source = get_api_key_source()
    except Exception:
        pass
    return {
        "provider": "Meta Model API",
        "base_url": get_api_base(),
        "model": get_api_model(),
        "configured": is_available(),
        "key_source": source,
        "local_gguf": False,
    }


def get_model():
    """Compatibility shim for old callers that expected a local model."""
    raise RuntimeError(
        "The local GGUF model is disabled. Orunex is using the Meta Model API."
    )


def _build_content(prompt: str, images: Optional[Iterable[Any]]) -> Any:
    if not images:
        return prompt

    parts: list[dict[str, Any]] = [{"type": "text", "text": str(prompt)}]
    for image in images:
        url = ""
        if isinstance(image, (bytes, bytearray)):
            encoded = base64.b64encode(bytes(image)).decode("ascii")
            url = f"data:image/png;base64,{encoded}"
        elif isinstance(image, str):
            value = image.strip()
            if value.startswith(("data:", "http://", "https://")):
                url = value
            elif os.path.isfile(value):
                try:
                    with open(value, "rb") as handle:
                        encoded = base64.b64encode(handle.read()).decode("ascii")
                    url = f"data:image/png;base64,{encoded}"
                except OSError:
                    url = ""
        if url:
            parts.append({"type": "image_url", "image_url": {"url": url}})

    return parts if len(parts) > 1 else prompt


def _build_messages(
    prompt: str,
    system: Optional[str],
    images: Optional[Iterable[Any]],
    history: Optional[Iterable[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """Build an OpenAI-compatible message list.

    ``history`` is the bounded prior conversation supplied by the desktop
    store.  Only user/assistant turns are replayed; system notices and tool
    output stay internal so an old tool result can never become an instruction.
    """

    messages: list[dict[str, Any]] = []
    if system and str(system).strip():
        messages.append({"role": "system", "content": str(system)})
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = item.get("content")
        if content is None:
            content = item.get("text")
        if not str(content or "").strip():
            continue
        messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": _build_content(prompt, images)})
    return messages


def _request_options(options: Optional[dict[str, Any]]) -> dict[str, Any]:
    opts = dict(options or {})
    try:
        max_tokens = int(
            opts.get("max_tokens")
            or opts.get("num_predict")
            or os.environ.get("META_MAX_TOKENS")
            or DEFAULT_MAX_TOKENS
        )
    except (TypeError, ValueError):
        max_tokens = DEFAULT_MAX_TOKENS
    max_tokens = max(256, min(MAX_TOKEN_BUDGET, max_tokens))

    try:
        temperature = float(
            opts.get("temperature", os.environ.get("META_TEMPERATURE", 0.3))
        )
    except (TypeError, ValueError):
        temperature = 0.3
    temperature = max(0.0, min(2.0, temperature))

    payload: dict[str, Any] = {
        "model": resolve_model(opts.get("model")),
        "messages": [],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    # Meta Model API currently rejects the OpenAI ``stop`` parameter.  Keep
    # accepting it from legacy callers but do not send it upstream.
    effort = (
        opts.get("reasoning_effort")
        or os.environ.get("META_REASONING_EFFORT")
        or DEFAULT_REASONING_EFFORT
    )
    effort = str(effort).strip().lower()
    if effort:
        payload["reasoning_effort"] = effort

    try:
        payload["timeout"] = float(
            opts.get("timeout")
            or os.environ.get("META_API_TIMEOUT")
            or DEFAULT_TIMEOUT
        )
    except (TypeError, ValueError):
        payload["timeout"] = float(DEFAULT_TIMEOUT)
    return payload


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_api_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _error_from_response(response: requests.Response) -> str:
    message = ""
    try:
        data = response.json()
        error = data.get("error") if isinstance(data, dict) else None
        if isinstance(error, dict):
            message = str(error.get("message") or error.get("type") or "")
        elif error:
            message = str(error)
    except Exception:
        pass
    if not message:
        try:
            message = response.text.strip()[:400]
        except Exception:
            message = ""
    if not message:
        message = "request failed"
    return f"Meta API HTTP {response.status_code}: {message}"


def _extract_content(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _extract_stream_text(event: Any) -> str:
    if not isinstance(event, dict):
        return ""
    choices = event.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    return ""


def _finish_reason(data: Any) -> str:
    try:
        return str(
            ((data.get("choices") or [{}])[0] or {}).get("finish_reason") or ""
        )
    except Exception:
        return ""


def _token_budget(value: Any, fallback: int = DEFAULT_MAX_TOKENS) -> int:
    try:
        return max(256, min(MAX_TOKEN_BUDGET, int(value or fallback)))
    except (TypeError, ValueError):
        return fallback


def _debug_meta(
    payload: dict[str, Any],
    finish: str,
    usage: Any,
    chars: int,
) -> None:
    """Print the real request/usage when the operator asks for diagnostics.

    ``max_tokens`` is a ceiling, not a quota: a complete answer can use far
    fewer tokens.  This line makes that distinction visible without leaking the
    API key or the prompt.
    """

    if os.environ.get("ORUNEX_META_DEBUG") != "1":
        return
    usage = usage if isinstance(usage, dict) else {}
    details = usage.get("completion_tokens_details") or {}
    reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else 0
    print(
        "[META] "
        f"model={payload.get('model')} "
        f"max_tokens={payload.get('max_tokens')} "
        f"temperature={payload.get('temperature')} "
        f"effort={payload.get('reasoning_effort')} "
        f"finish={finish or 'unknown'} "
        f"prompt_tokens={usage.get('prompt_tokens', '?')} "
        f"completion_tokens={usage.get('completion_tokens', '?')} "
        f"reasoning_tokens={reasoning or 0} "
        f"chars={chars}",
        flush=True,
    )


def _next_effort(value: Any) -> str:
    """Lower reasoning effort only after the token budget is maxed."""
    effort = str(value or "").strip().lower()
    if effort in {"max", "xhigh", "high"}:
        return "medium"
    if effort == "medium":
        return "low"
    return effort


def _retry_wait(attempt: int) -> None:
    # Short, bounded backoff: long sleeps make Live feel dead.
    time.sleep(min(0.8 * (2 ** (attempt - 1)), 4.0))


def _is_transient_exception(exc: Exception) -> bool:
    return isinstance(exc, (requests.ConnectionError, requests.Timeout))


def _max_attempts() -> int:
    try:
        return max(1, min(5, int(os.environ.get("META_REQUEST_RETRIES", "3"))))
    except (TypeError, ValueError):
        return 3


def call_ollama(
    model: Optional[str] = None,
    prompt: Optional[str] = None,
    images: Optional[Iterable[Any]] = None,
    stream: bool = False,
    system: Optional[str] = None,
    options: Optional[dict[str, Any]] = None,
    history: Optional[Iterable[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Send a chat completion to Meta Model API.

    ``model`` is kept for compatibility.  Legacy names such as ``orunex_v37``
    are mapped to ``muse-spark-1.3`` (or ``META_MODEL``).  A one-argument call is
    treated as the prompt for compatibility with older workers.

    Muse counts its hidden reasoning against ``max_tokens``.  If the whole
    budget is consumed before it writes an answer, the API replies
    ``finish_reason=length`` with empty content.  Retrying the same request is
    pointless, so the retry doubles the budget instead (up to the configured
    8192-token ceiling).
    """
    if prompt is None:
        prompt = model or ""
        model = None

    key = get_api_key()
    if not key:
        return {
            "error": "Meta API key is not configured. Set META_API_KEY.",
        }

    payload_options = _request_options(options)
    payload_options["model"] = resolve_model(model or payload_options.get("model"))
    payload_options["messages"] = _build_messages(
        str(prompt), system, images, history
    )
    timeout = payload_options.pop("timeout", DEFAULT_TIMEOUT)
    payload_options["max_tokens"] = _token_budget(
        payload_options.get("max_tokens"), DEFAULT_MAX_TOKENS
    )

    attempts = _max_attempts()
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(
                get_chat_endpoint(),
                headers=_headers(),
                json=payload_options,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            last_error = f"Meta API connection failed: {exc}"
            if attempt < attempts and _is_transient_exception(exc):
                _retry_wait(attempt)
                continue
            return {"error": last_error}

        if response.status_code != 200:
            last_error = _error_from_response(response)
            if (
                response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}
                and attempt < attempts
            ):
                _retry_wait(attempt)
                continue
            return {"error": last_error}

        try:
            data = response.json()
        except ValueError:
            last_error = "Meta API returned invalid JSON."
            if attempt < attempts:
                _retry_wait(attempt)
                continue
            return {"error": last_error}

        content = _extract_content(data)
        finish = _finish_reason(data)
        budget = int(payload_options.get("max_tokens") or DEFAULT_MAX_TOKENS)

        if content and finish == "length" and attempt < attempts:
            # Text can be present and still be cut off mid-sentence. Retrying
            # the same truncated request cannot fix it. Widen the budget first
            # and keep the requested effort; only lower effort at the ceiling.
            if budget < MAX_TOKEN_BUDGET:
                payload_options["max_tokens"] = min(
                    MAX_TOKEN_BUDGET, max(budget * 2, 2048)
                )
                _retry_wait(1)
                continue
            effort = str(payload_options.get("reasoning_effort") or "").lower()
            lowered = _next_effort(effort)
            if lowered and lowered != effort:
                payload_options["reasoning_effort"] = lowered
                _retry_wait(1)
                continue

        if content:
            usage = data.get("usage") or {}
            _debug_meta(payload_options, finish, usage, len(content))
            return {
                "response": content,
                "finish_reason": finish,
                "truncated": finish == "length",
                "usage": usage if isinstance(usage, dict) else {},
                "max_tokens": budget,
                "model": payload_options.get("model"),
                "temperature": payload_options.get("temperature"),
                "reasoning_effort": payload_options.get("reasoning_effort"),
            }

        # No final answer.  If the model ran out of budget while reasoning,
        # double it and try once more; otherwise retry once in case the empty
        # answer was a transient generation hiccup.
        usage = data.get("usage") or {}
        reasoning_tokens = (
            (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
            if isinstance(usage, dict)
            else 0
        )
        _debug_meta(payload_options, finish, usage, 0)
        last_error = (
            "Meta API returned no final content"
            + (f" (finish_reason={finish})" if finish else "")
            + (
                f" after {reasoning_tokens} reasoning tokens"
                if reasoning_tokens
                else ""
            )
            + "."
        )
        if attempt < attempts:
            if budget < MAX_TOKEN_BUDGET:
                payload_options["max_tokens"] = min(
                    MAX_TOKEN_BUDGET, max(budget * 2, 2048)
                )
                _retry_wait(1)
                continue
            effort = str(payload_options.get("reasoning_effort") or "").lower()
            lowered = _next_effort(effort)
            if lowered and lowered != effort:
                payload_options["reasoning_effort"] = lowered
                _retry_wait(1)
                continue
        return {"error": last_error}

    return {"error": last_error or "Meta API request failed."}



def call_ollama_stream(
    model: Optional[str] = None,
    prompt: Optional[str] = None,
    system: Optional[str] = None,
    callback=None,
    options: Optional[dict[str, Any]] = None,
    images: Optional[Iterable[Any]] = None,
    history: Optional[Iterable[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Stream one Meta Model API response and invoke ``callback(token)``.

    If Muse consumes its whole budget on hidden reasoning the stream ends with
    no visible token.  The final fallback makes one non-streamed call with a
    larger budget so the user gets an answer instead of an empty bubble.
    """
    if prompt is None:
        prompt = model or ""
        model = None

    key = get_api_key()
    if not key:
        return {"error": "Meta API key is not configured. Set META_API_KEY."}

    payload_options = _request_options(options)
    payload_options["model"] = resolve_model(model or payload_options.get("model"))
    payload_options["messages"] = _build_messages(
        str(prompt), system, images, history
    )
    payload_options["stream"] = True
    payload_options["max_tokens"] = _token_budget(
        payload_options.get("max_tokens"), DEFAULT_MAX_TOKENS
    )
    timeout = payload_options.pop("timeout", DEFAULT_TIMEOUT)
    attempts = _max_attempts()
    last_error = ""

    for attempt in range(1, attempts + 1):
        collected: list[str] = []
        finish_reason = ""
        try:
            with requests.post(
                get_chat_endpoint(),
                headers=_headers(),
                json=payload_options,
                timeout=timeout,
                stream=True,
            ) as response:
                if response.status_code != 200:
                    last_error = _error_from_response(response)
                    if (
                        response.status_code
                        in {408, 409, 425, 429, 500, 502, 503, 504}
                        and attempt < attempts
                    ):
                        _retry_wait(attempt)
                        continue
                    return {"error": last_error}

                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    line = raw_line.strip()
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if not line or line == "[DONE]":
                        if line == "[DONE]":
                            break
                        continue

                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue

                    if isinstance(event, dict) and event.get("error"):
                        error = event.get("error")
                        if isinstance(error, dict):
                            error = (
                                error.get("message") or error.get("type") or error
                            )
                        return {"error": f"Meta API stream error: {error}"}

                    finish_reason = _finish_reason(event) or finish_reason
                    token = _extract_stream_text(event)
                    if token:
                        collected.append(token)
                        if callback and callable(callback):
                            try:
                                callback(token)
                            except Exception:
                                pass
        except requests.RequestException as exc:
            last_error = f"Meta API connection failed: {exc}"
            if collected:
                # Part of the answer already reached the UI; do not duplicate
                # it by retrying the whole request.
                return {"response": "".join(collected), "truncated": True}
            if attempt < attempts and _is_transient_exception(exc):
                _retry_wait(attempt)
                continue
            return {"error": last_error}

        final = "".join(collected)
        if final:
            # The UI already received these tokens, so retrying would duplicate
            # text. Surface the truncation instead of silently cutting off.
            _debug_meta(payload_options, finish_reason, {}, len(final))
            return {
                "response": final,
                "finish_reason": finish_reason,
                "truncated": finish_reason == "length",
                "usage": {},
                "max_tokens": int(
                    payload_options.get("max_tokens") or DEFAULT_MAX_TOKENS
                ),
                "model": payload_options.get("model"),
                "temperature": payload_options.get("temperature"),
                "reasoning_effort": payload_options.get("reasoning_effort"),
            }

        last_error = (
            "Meta API stream returned no final content"
            + (f" (finish_reason={finish_reason})" if finish_reason else "")
            + "."
        )
        budget = int(payload_options.get("max_tokens") or DEFAULT_MAX_TOKENS)
        if attempt < attempts:
            if budget < MAX_TOKEN_BUDGET:
                payload_options["max_tokens"] = min(
                    MAX_TOKEN_BUDGET, max(budget * 2, 2048)
                )
                continue
            effort = str(payload_options.get("reasoning_effort") or "").lower()
            lowered = _next_effort(effort)
            if lowered and lowered != effort:
                payload_options["reasoning_effort"] = lowered
                continue

    # Last resort: a normal request with a larger budget and a slightly lower
    # effort. Never fall back to ``minimal`` for a reasoning answer: that was
    # producing noticeably shallow replies after an empty stream.
    fallback_options = dict(options or {})
    fallback_options["max_tokens"] = min(
        MAX_TOKEN_BUDGET,
        max(
            2048,
            int(payload_options.get("max_tokens") or DEFAULT_MAX_TOKENS) * 2,
        ),
    )
    stream_effort = str(
        payload_options.get("reasoning_effort") or DEFAULT_REASONING_EFFORT
    ).lower()
    fallback_options["reasoning_effort"] = _next_effort(stream_effort) or "medium"
    fallback_model = str(payload_options.get("model") or DEFAULT_MODEL)
    fallback = call_ollama(
        fallback_model,
        prompt,
        system=system,
        images=images,
        options=fallback_options,
        history=history,
    )
    if fallback.get("response"):
        if callback and callable(callback):
            try:
                callback(str(fallback["response"]))
            except Exception:
                pass
        return fallback
    return {"error": last_error or fallback.get("error") or "Meta API stream failed."}



def verify_connection(timeout: float = 20.0) -> dict[str, Any]:
    """Make one real, minimal Meta request and report whether it succeeded.

    Used by the desktop startup check and by ``app.py --check``.  It never
    returns or logs the API key; only its origin is reported.
    """
    status = get_status()
    if not status.get("configured"):
        return {
            **status,
            "ok": False,
            "latency_s": 0.0,
            "error": (
                "Meta API key is not configured. Set META_API_KEY in the "
                "Windows user environment or in .env."
            ),
        }

    started = time.monotonic()
    result = call_ollama(
        "orunex_v37",
        "Reply with exactly one word: OK",
        system="You are a connectivity probe. Reply briefly.",
        options={
            "max_tokens": 256,
            "reasoning_effort": "minimal",
            "temperature": 0.0,
            "timeout": max(5.0, float(timeout)),
        },
    )
    latency = round(time.monotonic() - started, 2)
    if result.get("response"):
        return {
            **status,
            "ok": True,
            "latency_s": latency,
            "reply": str(result["response"])[:80],
        }
    return {
        **status,
        "ok": False,
        "latency_s": latency,
        "error": result.get("error") or "Meta API returned an empty response.",
    }


def get_local_embedding(text: str) -> list[float]:
    """Return a deterministic local vector for the existing memory store.

    Meta Model API does not expose a text-embedding model in the current
    catalog, so the local hash embedding keeps FAISS memory operational without
    a GGUF model.  The vectors are lightweight lexical features, not semantic
    transformer embeddings.
    """
    tokens = re.findall(r"[A-Za-z0-9_]+", str(text or "").lower())
    if not tokens:
        return []

    vector = [0.0] * DEFAULT_EMBEDDING_DIMENSION
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "little") % DEFAULT_EMBEDDING_DIMENSION
        sign = 1.0 if (digest[4] & 1) else -1.0
        vector[index] += sign

    norm = sum(value * value for value in vector) ** 0.5
    if norm <= 0:
        return []
    return [value / norm for value in vector]


# Explicit aliases for new callers and for readability.
call_meta = call_ollama
call_meta_stream = call_ollama_stream
