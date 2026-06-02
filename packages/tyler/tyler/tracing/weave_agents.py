"""Optional Weave Agents tracing adapter.

This module deliberately avoids importing new Weave Agents APIs directly. Tyler
supports older Weave runtimes and uninitialized Weave sessions, so every call is
checked dynamically and degrades to a no-op.
"""

from __future__ import annotations

import logging
import json
from typing import Any, Dict, Optional

try:  # pragma: no cover - exercised through adapter behavior
    import weave  # type: ignore
except Exception:  # pragma: no cover
    weave = None  # type: ignore


logger = logging.getLogger(__name__)


class WeaveAgentsTracer:
    """Small no-op-safe adapter around Weave Agents tracing APIs."""

    _REQUIRED_APIS = ("start_session", "start_turn", "start_llm", "start_tool")

    def __init__(self, weave_module: Any = None):
        """Initialize the adapter.

        Args:
            weave_module: Optional module-like object for tests. Defaults to the
                imported `weave` module.
        """
        self._weave = weave_module if weave_module is not None else weave
        self._active: Optional[bool] = None

    @property
    def active(self) -> bool:
        """Whether Weave Agents tracing can be used right now."""
        if self._active is None:
            self._active = self._detect_active()
        return self._active

    def _detect_active(self) -> bool:
        if self._weave is None:
            return False
        if not all(hasattr(self._weave, api) for api in self._REQUIRED_APIS):
            return False

        get_client = getattr(self._weave, "get_client", None)
        if callable(get_client):
            try:
                return get_client() is not None
            except Exception:
                return False

        # If a future Weave module exposes the Agents APIs but not get_client,
        # treat the presence of the APIs as enough and still catch call failures.
        return True

    def start_session(
        self,
        *,
        agent_name: str,
        session_id: str,
        model_name: str,
    ) -> Any:
        """Start a Weave Agents session, or return None when inactive."""
        return self._call(
            "start_session",
            agent_name=agent_name,
            session_id=session_id,
            model=model_name,
        )

    def start_turn(
        self,
        *,
        session: Any,
        user_content: Any,
    ) -> Any:
        """Start a Weave Agents turn, or return None when inactive."""
        return self._call(
            "start_turn",
            user_message=str(user_content or ""),
            model=getattr(session, "model", ""),
            agent_name=getattr(session, "agent_name", ""),
        )

    def start_llm(
        self,
        *,
        turn: Any,
        model_name: str,
        input_messages: Any,
        output_messages: Any,
        usage: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Start a Weave Agents LLM span, or return None when inactive."""
        system_instructions = [
            str(message.get("content", ""))
            for message in input_messages or []
            if isinstance(message, dict) and message.get("role") == "system"
        ]
        span = self._call(
            "start_llm",
            model=model_name,
            provider_name="",
            system_instructions=system_instructions or None,
        )
        self._record_llm_payload(
            span,
            input_messages=input_messages,
            output_messages=output_messages,
            usage=usage or {},
        )
        return span

    def start_tool(
        self,
        *,
        turn: Any,
        tool_name: str,
        arguments: Any,
        tool_call_id: Optional[str],
    ) -> Any:
        """Start a Weave Agents tool span, or return None when inactive."""
        if not isinstance(arguments, str):
            try:
                arguments = json.dumps(arguments)
            except TypeError:
                arguments = str(arguments)
        return self._call(
            "start_tool",
            name=tool_name,
            arguments=arguments,
            tool_call_id=tool_call_id or "",
        )

    def finish_span(self, span: Any, **payload: Any) -> None:
        """Best-effort span finalization for changing Weave APIs."""
        if span is None:
            return
        self._apply_span_payload(span, payload)
        for method_name in ("finish", "end", "close"):
            method = getattr(span, method_name, None)
            if callable(method):
                try:
                    method(**payload)
                except TypeError:
                    try:
                        method()
                    except Exception:
                        logger.debug("Weave Agents span finalization failed", exc_info=True)
                except Exception:
                    logger.debug("Weave Agents span finalization failed", exc_info=True)
                return

    def _call(self, api_name: str, **kwargs: Any) -> Any:
        if not self.active:
            return None
        api = getattr(self._weave, api_name, None)
        if not callable(api):
            return None
        try:
            span = api(**kwargs)
            enter = getattr(span, "__enter__", None)
            if callable(enter):
                try:
                    enter()
                except Exception:
                    logger.debug("Weave Agents span enter failed: %s", api_name, exc_info=True)
            return span
        except Exception:
            logger.debug("Weave Agents tracing call failed: %s", api_name, exc_info=True)
            return None

    def _record_llm_payload(
        self,
        span: Any,
        *,
        input_messages: Any,
        output_messages: Any,
        usage: Dict[str, Any],
    ) -> None:
        if span is None:
            return
        record = getattr(span, "record", None)
        if not callable(record):
            return
        try:
            record(
                input_messages=self._to_weave_messages(input_messages),
                output_messages=self._to_weave_messages(output_messages),
                usage=self._to_weave_usage(usage),
            )
        except Exception:
            logger.debug("Weave Agents LLM payload recording failed", exc_info=True)

    def _apply_span_payload(self, span: Any, payload: Dict[str, Any]) -> None:
        if "result" in payload and hasattr(span, "result"):
            try:
                result = payload["result"]
                span.result = result if isinstance(result, str) else json.dumps(result)
            except Exception:
                try:
                    span.result = str(payload["result"])
                except Exception:
                    pass
        if "error" in payload and payload["error"] is not None and hasattr(span, "result"):
            try:
                span.result = json.dumps({"error": payload["error"]})
            except Exception:
                pass

    def _to_weave_messages(self, messages: Any) -> Any:
        try:
            from weave.session.types import Message
        except Exception:
            return messages

        converted = []
        for message in messages or []:
            if not isinstance(message, dict):
                converted.append(message)
                continue
            role = message.get("role")
            if role not in {"user", "assistant", "system", "tool"}:
                continue
            content = message.get("content") or ""
            if not isinstance(content, str):
                try:
                    content = json.dumps(content)
                except TypeError:
                    content = str(content)
            converted.append(Message(
                role=role,
                content=content,
                tool_call_id=str(message.get("tool_call_id") or ""),
                tool_name=str(message.get("name") or message.get("tool_name") or ""),
            ))
        return converted

    def _to_weave_usage(self, usage: Dict[str, Any]) -> Any:
        try:
            from weave.session.types import Usage
        except Exception:
            return usage
        return Usage(
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
            reasoning_tokens=int(usage.get("reasoning_tokens", 0) or 0),
        )
