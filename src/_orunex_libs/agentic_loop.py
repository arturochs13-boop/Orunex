"""Bounded ReAct-style reasoning loop for Orunex.

The loop borrows the useful control flow from OpenCodeInterpreter:

1. ask the model for the next step;
2. if it requests a tool, execute it and append the result to the transcript;
3. ask again with the evidence;
4. finish with a user-facing answer.

Unlike the reference code-interpreter, this loop only exposes read-only,
sandboxed tools.  It never executes generated Python or shell commands, and it
never touches the trading executor.  That keeps Muse as the only decision maker
while making long repository/analysis questions evidence-driven instead of
one-shot guesses.

The loop is deliberately bounded by both a step budget and a wall-clock budget.
When either is exhausted it makes one final, tool-free synthesis request so the
user receives an answer instead of a raw tool envelope.
"""

from __future__ import annotations

import inspect
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from _orunex_libs.agent_tools import ToolRegistry, build_default_registry
from _orunex_libs.conversation_context import normalize_history, omission_note

MAX_TRANSCRIPT_CHARS = 28_000
DEFAULT_MAX_TOOL_CALLS = 6
DEFAULT_MAX_STEPS = 8
DEFAULT_TIME_BUDGET_SECONDS = 120.0


@dataclass
class LoopResult:
    answer: str = ""
    steps: int = 0
    tools_used: List[str] = field(default_factory=list)
    finish_reason: str = ""
    truncated: bool = False
    usage: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _tool_payload(value: Any) -> Optional[Tuple[str, Dict[str, Any]]]:
    if not isinstance(value, dict):
        return None
    name = value.get("tool") or value.get("name")
    args = value.get("args") or value.get("arguments") or {}
    if isinstance(name, str) and isinstance(args, dict):
        return name.strip(), args
    return None


def parse_tool_call(
    text: str, known_tools: Iterable[str]
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Extract one allow-listed tool request from a model response.

    Models are inconsistent about fences and wrappers, so the parser accepts a
    fenced ``tool``/``json`` block, ``<tool_call>`` XML, a bare JSON object, or
    a JSON object embedded in a short explanation.  A block is only a tool call
    when its name is in the allow-list and its arguments are a JSON object.
    This prevents a normal answer containing a JSON example from being executed.
    """

    known = {str(name) for name in known_tools}
    if not text or not known:
        return None

    candidates: List[str] = []
    for pattern in (
        r"```(?:tool|json)?\s*(.*?)```",
        r"<tool_call>\s*(.*?)\s*</tool_call>",
    ):
        candidates.extend(
            match.group(1).strip()
            for match in re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)
        )

    stripped = text.strip()
    if stripped:
        candidates.append(stripped)

    # A short explanation may precede the object; only inspect balanced-looking
    # objects with a tool/name key.  This is intentionally conservative.
    for match in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL):
        candidate = match.group(0).strip()
        if '"tool"' in candidate or '"name"' in candidate:
            candidates.append(candidate)

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        parsed = _tool_payload(payload)
        if parsed is None:
            # Some models wrap the action in {"action": {...}}.
            action = payload.get("action") if isinstance(payload, dict) else None
            parsed = _tool_payload(action)
        if parsed is None:
            continue
        name, args = parsed
        if name in known:
            return name, args
    return None


def _strip_tool_blocks(text: str) -> str:
    cleaned = re.sub(
        r"```(?:tool|json)?\s*\{.*?\}\s*```",
        "",
        str(text or ""),
        flags=re.DOTALL | re.IGNORECASE,
    )
    cleaned = re.sub(
        r"<tool_call>.*?</tool_call>",
        "",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return cleaned.strip()


def extract_final_answer(text: str) -> str:
    """Return a natural final answer, unwrapping a JSON final envelope."""

    raw = str(text or "").strip()
    if not raw:
        return ""
    for candidate in (raw, _strip_tool_blocks(raw)):
        try:
            payload = json.loads(candidate)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            for key in ("final", "answer", "response"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return _strip_tool_blocks(raw) or raw


def _describe_tool_call(name: str, args: Dict[str, Any]) -> str:
    """A compact, OpenCode-style line for the activity log."""

    path = str(args.get("path") or "").strip()
    if name == "read_file":
        line_range = ""
        if args.get("start_line") or args.get("end_line"):
            line_range = (
                f" (lines {args.get('start_line') or 1}-"
                f"{args.get('end_line') or 'end'})"
            )
        return f"Read {path or 'file'}{line_range}"
    if name == "list_files":
        pattern = str(args.get("pattern") or "*")
        return f"List {path or '.'} · {pattern}"
    if name == "search_text":
        query = str(args.get("query") or "").strip()
        scope = path or "."
        return f"Search \"{query[:80]}\" in {scope}"
    if name == "recall_memory":
        query = str(args.get("query") or "").strip()
        return f"Recall memory · {query[:80]}"
    return f"Call {name}"


def _result_line(
    name: str, args: Dict[str, Any], result: Any, duration: float
) -> str:
    label = _describe_tool_call(name, args)
    if not result.ok:
        detail = str(result.error or "tool failed").replace("\n", " ")[:120]
        return f"{label} → error: {detail}"
    body = str(result.output or "").strip()
    suffix = " · truncated" if getattr(result, "truncated", False) else ""
    return f"{label} · {len(body):,} chars{suffix} · {duration:.2f}s"


def run_reasoning_loop(
    *,
    task: str,
    prompt: str,
    system_prompt: str,
    model_call: Callable[[str, str, List[Dict[str, str]]], Dict[str, Any]],
    history: Optional[Iterable[Any]] = None,
    tools: Optional[ToolRegistry] = None,
    max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
    max_steps: Optional[int] = None,
    time_budget_seconds: float = DEFAULT_TIME_BUDGET_SECONDS,
    trace_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> LoopResult:
    """Run a bounded tool-using reasoning turn.

    ``task`` is the raw user message (used to avoid replaying the current turn
    from history); ``prompt`` is the fully prepared prompt, including project
    and memory context.  ``model_call`` must return the same dict shape as
    :func:`_orunex_libs.ollama_client.call_ollama`.

    ``trace_callback`` receives small structured events (thinking, tool_call,
    tool_result, answer, error).  When it is omitted the events are published
    on :mod:`_orunex_libs.activity_log`, which is what the desktop activity
    panel subscribes to.
    """

    registry = tools or build_default_registry()
    messages, omitted = normalize_history(history, current_task=task)
    system = str(system_prompt or "").rstrip()
    system += omission_note(omitted)

    tool_budget = max(1, int(max_tool_calls or DEFAULT_MAX_TOOL_CALLS))
    step_budget = max(
        tool_budget + 1,
        int(max_steps or max(tool_budget + 2, DEFAULT_MAX_STEPS)),
    )
    system += "\n\n" + registry.describe()
    system += (
        f"\n\nTOOL BUDGET FOR THIS TURN: at most {tool_budget} tool calls "
        f"across at most {step_budget} steps. Use the smallest number needed."
    )

    try:
        budget_seconds = float(time_budget_seconds)
    except (TypeError, ValueError):
        budget_seconds = DEFAULT_TIME_BUDGET_SECONDS
    deadline = (
        time.monotonic() + budget_seconds
        if budget_seconds and budget_seconds > 0
        else None
    )

    # Newer model callbacks accept an optional per-call timeout.  The desktop
    # client uses it to keep each HTTP request inside the loop's wall-clock
    # budget; the test doubles with three arguments keep working unchanged.
    try:
        accepts_timeout = "timeout" in inspect.signature(model_call).parameters
    except (TypeError, ValueError):
        accepts_timeout = False

    def remaining_seconds() -> Optional[float]:
        if deadline is None:
            return None
        return max(0.0, deadline - time.monotonic())

    def invoke_model(
        prompt_text: str,
        system_text: str,
        history_messages: List[Dict[str, str]],
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        if timeout is not None and accepts_timeout:
            return model_call(  # type: ignore[call-arg]
                prompt_text, system_text, history_messages, timeout=timeout
            )
        return model_call(prompt_text, system_text, history_messages)

    transcript = ""
    tools_used: List[str] = []
    seen_calls: set[tuple[str, str]] = set()
    last_response: Dict[str, Any] = {}
    last_text = ""

    def trace(kind: str, message: str, level: str = "info", **data: Any) -> None:
        event = {
            "kind": kind,
            "message": message,
            "level": level,
            "ts": time.time(),
        }
        event.update(data)
        if callable(trace_callback):
            try:
                trace_callback(event)
                return
            except Exception:
                # A broken UI trace must never abort the reasoning turn.
                pass
        try:
            from _orunex_libs import activity_log

            activity_log.emit(kind, message, level, **data)
        except Exception:
            pass

    def finalise(reason: str, steps: int) -> LoopResult:
        """Ask once for a tool-free synthesis after a budget is exhausted."""

        nonlocal last_response, last_text
        remaining = remaining_seconds()
        if remaining is not None and remaining <= 1.0:
            # Never start another network call after the wall-clock deadline.
            # If the model already produced prose, return it; otherwise report
            # the real timeout instead of pretending the task completed.
            fallback = _strip_tool_blocks(last_text)
            if fallback:
                trace(
                    "answer",
                    f"Answer ready ({len(fallback):,} chars, deadline fallback)",
                    "warn",
                    step=steps,
                    chars=len(fallback),
                    finish_reason=reason,
                )
                return LoopResult(
                    answer=fallback,
                    steps=steps,
                    tools_used=list(tools_used),
                    finish_reason=reason,
                    truncated=bool(last_response.get("truncated")),
                    usage=dict(last_response.get("usage") or {}),
                )
            message = (
                "The reasoning time budget was exhausted before Muse could "
                "produce a final answer. Please retry with a narrower request."
            )
            trace("error", message, "error", step=steps)
            return LoopResult(
                error=message,
                steps=steps,
                tools_used=list(tools_used),
                finish_reason=reason,
            )

        trace(
            "thinking",
            "Synthesizing the final answer from the evidence gathered...",
            step=steps,
            final=True,
        )
        final_prompt = str(prompt or "").strip()
        if transcript:
            final_prompt += (
                "\n\nTOOL EVIDENCE SO FAR:\n"
                f"{transcript}\n\n"
                "FINAL ANSWER REQUIRED. Do not request another tool. "
                "Answer every part of the user's request using the evidence "
                "above. If something could not be verified, say so explicitly."
            )
        else:
            final_prompt += (
                "\n\nFINAL ANSWER REQUIRED. Do not request a tool. "
                "Answer the user's request completely now."
            )
        try:
            response = invoke_model(
                final_prompt,
                system,
                messages,
                timeout=(
                    max(1.0, min(45.0, remaining))
                    if remaining is not None
                    else None
                ),
            )
        except Exception as exc:  # pragma: no cover - model client boundary
            response = {"error": f"{type(exc).__name__}: {exc}"}

        if isinstance(response, dict):
            last_response = response
            text = str(response.get("response") or "").strip()
            if text:
                last_text = text
                answer = extract_final_answer(text)
                if answer and parse_tool_call(answer, registry.names()) is None:
                    trace(
                        "answer",
                        f"Answer ready ({len(answer):,} chars)",
                        "success",
                        step=steps,
                        chars=len(answer),
                        finish_reason=reason,
                    )
                    return LoopResult(
                        answer=answer,
                        steps=steps,
                        tools_used=list(tools_used),
                        finish_reason=reason,
                        truncated=bool(response.get("truncated")),
                        usage=dict(response.get("usage") or {}),
                    )
            error = str(response.get("error") or "").strip()
        else:
            error = "The model client returned an invalid response."

        fallback = _strip_tool_blocks(last_text)
        if fallback:
            trace(
                "answer",
                f"Answer ready ({len(fallback):,} chars, fallback)",
                "warn",
                step=steps,
                chars=len(fallback),
                finish_reason=reason,
            )
            return LoopResult(
                answer=fallback,
                steps=steps,
                tools_used=list(tools_used),
                finish_reason=reason,
                truncated=bool(last_response.get("truncated")),
                usage=dict(last_response.get("usage") or {}),
            )
        trace(
            "error",
            error or "The reasoning loop reached its budget without an answer.",
            "error",
            step=steps,
        )
        return LoopResult(
            error=error or "The reasoning loop reached its budget without an answer.",
            steps=steps,
            tools_used=list(tools_used),
            finish_reason=reason,
            truncated=bool(last_response.get("truncated")),
            usage=dict(last_response.get("usage") or {}),
        )

    for step in range(1, step_budget + 1):
        if deadline is not None and time.monotonic() > deadline:
            return finalise("time_budget", step - 1)

        current_prompt = str(prompt or "").strip()
        if transcript:
            current_prompt = (
                f"{current_prompt}\n\n"
                f"TOOL EVIDENCE SO FAR:\n{transcript}\n\n"
                "Check the user's complete request against the evidence. If a "
                "required fact is still missing, request the next tool; "
                "otherwise write the complete final answer now."
            )

        remaining = remaining_seconds()
        if remaining is not None and remaining <= 1.0:
            return finalise("time_budget", step - 1)

        trace(
            "thinking",
            f"Thinking… step {step}/{step_budget}",
            step=step,
            max_steps=step_budget,
        )
        try:
            response = invoke_model(
                current_prompt,
                system,
                messages,
                timeout=(
                    max(1.0, min(60.0, remaining))
                    if remaining is not None
                    else None
                ),
            )
        except Exception as exc:  # pragma: no cover - model client boundary
            response = {"error": f"{type(exc).__name__}: {exc}"}

        if not isinstance(response, dict):
            message = "The model client returned an invalid response."
            trace("error", message, "error", step=step)
            return LoopResult(
                error=message,
                steps=step,
                tools_used=list(tools_used),
            )
        last_response = response
        if response.get("error") and not response.get("response"):
            message = str(response.get("error"))
            trace("error", message, "error", step=step)
            return LoopResult(
                error=message,
                steps=step,
                tools_used=list(tools_used),
                finish_reason=str(response.get("finish_reason") or ""),
                truncated=bool(response.get("truncated")),
                usage=dict(response.get("usage") or {}),
            )

        last_text = str(response.get("response") or "").strip()
        if not last_text:
            message = "Muse returned an empty response."
            trace("error", message, "error", step=step)
            return LoopResult(
                error=message,
                steps=step,
                tools_used=list(tools_used),
                finish_reason=str(response.get("finish_reason") or ""),
                truncated=bool(response.get("truncated")),
                usage=dict(response.get("usage") or {}),
            )

        call = parse_tool_call(last_text, registry.names())
        if call is None:
            answer = extract_final_answer(last_text)
            trace(
                "answer",
                f"Answer ready ({len(answer):,} chars)",
                "success",
                step=step,
                chars=len(answer),
            )
            return LoopResult(
                answer=answer,
                steps=step,
                tools_used=list(tools_used),
                finish_reason=str(response.get("finish_reason") or ""),
                truncated=bool(response.get("truncated")),
                usage=dict(response.get("usage") or {}),
            )

        if deadline is not None and time.monotonic() >= deadline:
            trace(
                "limit",
                "Time budget reached; synthesizing from the evidence gathered.",
                "warn",
                step=step,
            )
            return finalise("time_budget", step)

        name, args = call
        label = _describe_tool_call(name, args)
        call_key = (
            name,
            json.dumps(args, sort_keys=True, ensure_ascii=False, default=str),
        )
        if call_key in seen_calls:
            message = f"Skipped duplicate tool call · {label}"
            trace("tool_skipped", message, "warn", step=step, tool=name)
            transcript += (
                f"\n\nTOOL RESULT [{name}] SKIPPED: this exact call was already "
                "executed. Use the evidence above instead of repeating it."
            )
            continue
        if len(tools_used) >= tool_budget:
            trace(
                "limit",
                f"Tool budget reached ({tool_budget}); synthesizing the answer.",
                "warn",
                step=step,
                tools_used=list(tools_used),
            )
            return finalise("tool_budget", step)

        seen_calls.add(call_key)
        trace("tool_call", label, step=step, tool=name, args=args)
        started = time.monotonic()
        result = registry.execute(name, args)
        duration = time.monotonic() - started
        tools_used.append(name)
        body = result.output if result.ok else result.error
        if not body:
            body = "No output."
        transcript += (
            f"\n\nTOOL RESULT [{name}] {'OK' if result.ok else 'ERROR'}:\n{body}"
        )
        if result.truncated:
            transcript += "\n[Tool output truncated to keep the context bounded.]"
        if len(transcript) > MAX_TRANSCRIPT_CHARS:
            transcript = (
                "[Earlier tool evidence trimmed to keep the context bounded.]\n"
                + transcript[-MAX_TRANSCRIPT_CHARS:]
            )
        trace(
            "tool_result",
            _result_line(name, args, result, duration),
            "success" if result.ok else "error",
            step=step,
            tool=name,
            ok=bool(result.ok),
            chars=len(body),
            truncated=bool(result.truncated),
            duration_s=round(duration, 3),
        )

    return finalise("step_budget", step_budget)
