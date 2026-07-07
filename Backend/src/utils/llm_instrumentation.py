"""
LLM analytics instrumentation layer.

Provides two public functions:
  - count_message_tokens(messages)  — categorise messages into system/user/history/tool/memory/rag
  - record_llm_request(...)         — persist one LlmRequest row, never raises

All token counts use a fast character-based estimate (1 token ≈ 4 chars).
The authoritative input/output totals always come from the LLM API response;
the category breakdown is an approximation useful for spotting where context
is being spent (system prompt vs history vs tool results vs memory).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token estimation helpers
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Fast character-based token estimate (1 token ≈ 4 chars)."""
    return max(0, len(text) // 4)


def _content_text(content: Any) -> str:
    """Extract plain text from a message content (str or list of content parts)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text", ""))
            else:
                parts.append(getattr(part, "text", ""))
        return " ".join(p for p in parts if p)
    return str(content) if content else ""


# ---------------------------------------------------------------------------
# Message token categoriser
# ---------------------------------------------------------------------------

_MEMORY_MARKERS = (
    "EXECUTION MEMORY",
    "RETRIEVED MEMORIES",
    "EPISODIC MEMORY",
    "SEMANTIC MEMORY",
    "PROCEDURAL MEMORY",
    "COGNITIVE MEMORY",
)

_RAG_MARKERS = (
    "RETRIEVED CONTEXT",
    "RAG CONTEXT",
    "RETRIEVED DOCUMENTS",
    "DOCUMENT CONTEXT",
    "KNOWLEDGE BASE",
)


def count_message_tokens(messages: Sequence) -> Dict[str, int]:
    """
    Walk a message list and bin each message's token estimate into categories.

    Returns a dict with keys:
        system_tokens, user_tokens, history_tokens, tool_tokens,
        memory_tokens, rag_tokens
    """
    try:
        from langchain_core.messages import (
            SystemMessage, HumanMessage, AIMessage, ToolMessage,
        )
    except ImportError:
        return {
            "system_tokens": 0, "user_tokens": 0, "history_tokens": 0,
            "tool_tokens": 0, "memory_tokens": 0, "rag_tokens": 0,
        }

    counts: Dict[str, int] = {
        "system_tokens": 0,
        "user_tokens": 0,
        "history_tokens": 0,
        "tool_tokens": 0,
        "memory_tokens": 0,
        "rag_tokens": 0,
    }

    if not messages:
        return counts

    # Identify the last HumanMessage so we can label it "user" (current turn)
    last_human_idx = -1
    for i, m in enumerate(messages):
        if isinstance(m, HumanMessage):
            last_human_idx = i

    for i, m in enumerate(messages):
        content = _content_text(getattr(m, "content", ""))
        tokens = estimate_tokens(content)

        if isinstance(m, SystemMessage):
            counts["system_tokens"] += tokens

        elif isinstance(m, ToolMessage):
            counts["tool_tokens"] += tokens

        elif isinstance(m, AIMessage):
            counts["history_tokens"] += tokens

        elif isinstance(m, HumanMessage):
            if i == last_human_idx:
                # The current user turn — estimate sub-portions for memory/RAG blocks
                content_upper = content.upper()
                memory_frac = 0.0
                rag_frac = 0.0

                if any(k in content_upper for k in _MEMORY_MARKERS):
                    # Memory blocks typically occupy ~20 % of the context message
                    memory_frac = 0.20

                if any(k in content_upper for k in _RAG_MARKERS):
                    rag_frac = 0.10

                remainder_frac = max(0.0, 1.0 - memory_frac - rag_frac)
                counts["memory_tokens"] += int(tokens * memory_frac)
                counts["rag_tokens"] += int(tokens * rag_frac)
                counts["user_tokens"] += int(tokens * remainder_frac)

            else:
                counts["history_tokens"] += tokens

        else:
            # Unknown message type — treat as history
            counts["history_tokens"] += tokens

    return counts


# ---------------------------------------------------------------------------
# DB writer
# ---------------------------------------------------------------------------

async def record_llm_request(
    *,
    user_id: str,
    chat_id: Optional[str],
    model: str,
    source: str,
    category_tokens: Dict[str, int],
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: Optional[int] = None,
    finish_reason: Optional[str] = None,
) -> None:
    """
    Persist one LlmRequest analytics row.

    Never raises — any DB failure is logged at WARNING so the caller's
    main path is never disrupted by an analytics write error.
    """
    try:
        from src.database.chat_db import AsyncSessionLocal, LlmRequest  # noqa: PLC0415

        total_tokens = input_tokens + output_tokens
        row = LlmRequest(
            id=str(uuid.uuid4()),
            user_id=user_id,
            chat_id=chat_id,
            model=model,
            source=source,
            system_tokens=category_tokens.get("system_tokens", 0),
            user_tokens=category_tokens.get("user_tokens", 0),
            history_tokens=category_tokens.get("history_tokens", 0),
            memory_tokens=category_tokens.get("memory_tokens", 0),
            tool_tokens=category_tokens.get("tool_tokens", 0),
            rag_tokens=category_tokens.get("rag_tokens", 0),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
        )
        async with AsyncSessionLocal() as session:
            session.add(row)
            await session.commit()
    except Exception as exc:
        logger.warning(f"[instrumentation] LlmRequest write failed (non-fatal): {exc}")
