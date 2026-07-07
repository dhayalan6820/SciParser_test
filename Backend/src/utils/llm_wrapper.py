import logging
from typing import Any, List, Optional, Type, TypeVar, overload
from pydantic import BaseModel
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import BaseMessage
from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage, BaseMessage as LCBaseMessage

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


def _extract_usage(response: Any) -> tuple[int, int, int]:
    """
    Extract (prompt_tokens, completion_tokens, cached_tokens) from a LangChain LLM response.

    Tries two locations in order:
    1. response.usage_metadata  — newer LangChain (≥0.3) unified format
    2. response.response_metadata["token_usage"] — OpenAI-compat / OpenRouter format
    Falls back to (0, 0, 0) if neither is present so callers never crash.
    """
    # 1. Newer LangChain unified metadata
    meta = getattr(response, "usage_metadata", None)
    if meta and isinstance(meta, dict):
        inp = meta.get("input_tokens", 0) or 0
        out = meta.get("output_tokens", 0) or 0
        details = meta.get("input_token_details") or {}
        cached = details.get("cache_read", 0) or 0
        if inp or out:
            return int(inp), int(out), int(cached)

    # 2. OpenAI-compat response_metadata (OpenRouter, older LangChain)
    rm = getattr(response, "response_metadata", None) or {}
    tu = rm.get("token_usage") or {}
    if tu:
        inp = tu.get("prompt_tokens", 0) or 0
        out = tu.get("completion_tokens", 0) or 0
        return int(inp), int(out), 0

    return 0, 0, 0


class LangChainChatModelWrapper(BaseChatModel):
    """
    Wraps a LangChain ChatModel to be compatible with browser-use's BaseChatModel protocol.
    Captures real token usage from the API response instead of returning mock zeros.
    """
    def __init__(self, langchain_llm: Any, provider: str = "openai"):
        self.langchain_llm = langchain_llm
        self._provider = provider
        self.model = getattr(langchain_llm, "model_name", getattr(langchain_llm, "model", "unknown"))

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def name(self) -> str:
        return f"wrapped_{self.model}"

    def _convert_to_langchain_messages(self, messages: List[BaseMessage]) -> List[LCBaseMessage]:
        lc_messages = []
        for m in messages:
            role = getattr(m, "role", "user")
            content = getattr(m, "content", "")
            
            if isinstance(content, list):
                text_parts = [part.text for part in content if hasattr(part, "text")]
                content = " ".join(text_parts)

            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            elif role == "system":
                lc_messages.append(SystemMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        return lc_messages

    async def ainvoke(
        self, messages: List[BaseMessage], output_format: Optional[Type[T]] = None, **kwargs: Any
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        lc_messages = self._convert_to_langchain_messages(messages)

        if output_format:
            # Structured output — LangChain strips usage metadata from the parsed result,
            # so we fall back to zeros rather than attempt a fragile workaround.
            structured_llm = self.langchain_llm.with_structured_output(output_format)
            response = await structured_llm.ainvoke(lc_messages)
            usage = ChatInvokeUsage(
                prompt_tokens=0,
                prompt_cached_tokens=0,
                prompt_cache_creation_tokens=0,
                prompt_image_tokens=0,
                completion_tokens=0,
                total_tokens=0,
            )
            return ChatInvokeCompletion(completion=response, usage=usage)
        else:
            response = await self.langchain_llm.ainvoke(lc_messages)
            prompt_tokens, completion_tokens, cached_tokens = _extract_usage(response)
            usage = ChatInvokeUsage(
                prompt_tokens=prompt_tokens,
                prompt_cached_tokens=cached_tokens,
                prompt_cache_creation_tokens=0,
                prompt_image_tokens=0,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            )
            return ChatInvokeCompletion(completion=response.content, usage=usage)
