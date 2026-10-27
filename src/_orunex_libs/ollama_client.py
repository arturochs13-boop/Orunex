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
from typing import Any, Iterable, Optional

import requests


DEFAULT_API_BASE = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3"
DEFAULT_TIMEOUT = 120
DEFAULT_MAX_TOKENS = 4096
DEFAULT_EMBEDDING_DIMENSION = 384

# Compatibility with UI code that used to inspect the local model path.
_MODEL_PATH = ""
_MODEL_INSTANCE = None

_API_KEY_ENV_VARS = ("META_API_KEY", "MODEL_API_KEY", "META_AI_API_KEY")
_API_BASE_ENV_VARS = ("META_API_BASE", "META_API_ENDPOINT", "META_AI_ENDPOINT")
_MODEL_ENV_VARS = ("META_MODEL", "ORUNEX_MODEL")


def get_api_key() -> str:
    """Return the configured Meta Model API key without logging it."""
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
    """Resolve Orunex's legacy model aliases to a Meta Model API model."""
    for name in _MODEL_ENV_VARS:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value

    candidate = (model or "").strip()
    if candidate and not candidate.lower().startswith("orunex"):
        return candidate
    return DEFAULT_MODEL


def get_api_model() -> str:
    return resolve_model()


def is_available() -> bool:
    """True when a key is configured; this does not make a network request."""
    return bool(get_api_key())


def get_status() -> dict[str, Any]:
    return {
        "provider": "Meta Model API",
        "base_url": get_api_base(),
        "model": get_api_model(),
        "configured": is_available(),
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
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if system and str(system).strip():
        messages.append({"role": "system", "content": str(system)})
    messages.append({"role": "user", "content": _build_content(prompt, images)})
    return messages


def _request_options(options: Optional[dict[str, Any]]) -> dict[str, Any]:
    opts = dict(options or {})
    try:
        max_tokens = int(
            opts.get("max_tokens")
            or opts.get("num_predict")
            or DEFAULT_MAX_TOKENS
        )
    except (TypeError, ValueError):
        max_tokens = DEFAULT_MAX_TOKENS
    max_tokens = max(256, min(32768, max_tokens))

    try:
        temperature = float(opts.get("temperature", 0.1))
    except (TypeError, ValueError):
        temperature = 0.1
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
        or "medium"
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


def call_ollama(
    model: Optional[str] = None,
    prompt: Optional[str] = None,
    images: Optional[Iterable[Any]] = None,
    stream: bool = False,
    system: Optional[str] = None,
    options: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Send a chat completion to Meta Model API.

    ``model`` is kept for compatibility.  Legacy names such as ``orunex_v37``
    are mapped to ``muse-spark-1.3`` (or ``META_MODEL``).  A one-argument call is
    treated as the prompt for compatibility with older workers.
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
    payload_options["messages"] = _build_messages(str(prompt), system, images)
    timeout = payload_options.pop("timeout", DEFAULT_TIMEOUT)

    try:
        response = requests.post(
            get_chat_endpoint(),
            headers=_headers(),
            json=payload_options,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return {"error": f"Meta API connection failed: {exc}"}

    if response.status_code != 200:
        return {"error": _error_from_response(response)}

    try:
        data = response.json()
    except ValueError:
        return {"error": "Meta API returned invalid JSON."}

    content = _extract_content(data)
    if content:
        return {"response": content}

    finish_reason = ""
    try:
        finish_reason = str(
            ((data.get("choices") or [{}])[0] or {}).get("finish_reason") or ""
        )
    except Exception:
        pass
    return {
        "error": (
            "Meta API returned no final content"
            + (f" (finish_reason={finish_reason})." if finish_reason else ".")
        )
    }


def call_ollama_stream(
    model: Optional[str] = None,
    prompt: Optional[str] = None,
    system: Optional[str] = None,
    callback=None,
    options: Optional[dict[str, Any]] = None,
    images: Optional[Iterable[Any]] = None,
) -> dict[str, Any]:
    """Stream one Meta Model API response and invoke ``callback(token)``."""
    if prompt is None:
        prompt = model or ""
        model = None

    key = get_api_key()
    if not key:
        return {"error": "Meta API key is not configured. Set META_API_KEY."}

    payload_options = _request_options(options)
    payload_options["model"] = resolve_model(model or payload_options.get("model"))
    payload_options["messages"] = _build_messages(str(prompt), system, images)
    payload_options["stream"] = True
    timeout = payload_options.pop("timeout", DEFAULT_TIMEOUT)

    collected: list[str] = []
    try:
        with requests.post(
            get_chat_endpoint(),
            headers=_headers(),
            json=payload_options,
            timeout=timeout,
            stream=True,
        ) as response:
            if response.status_code != 200:
                return {"error": _error_from_response(response)}

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
                        error = error.get("message") or error.get("type") or error
                    return {"error": f"Meta API stream error: {error}"}

                token = _extract_stream_text(event)
                if token:
                    collected.append(token)
                    if callback and callable(callback):
                        try:
                            callback(token)
                        except Exception:
                            pass
    except requests.RequestException as exc:
        return {"error": f"Meta API connection failed: {exc}"}

    final = "".join(collected)
    if final:
        return {"response": final}
    return {"error": "Meta API stream returned no final content."}


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
