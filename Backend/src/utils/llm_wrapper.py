import logging
from typing import Any, List, Optional, Type, TypeVar, overload
from pydantic import BaseModel
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import BaseMessage
from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage, BaseMessage as LCBaseMessage

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class LangChainChatModelWrapper(BaseChatModel):
    """
    Wraps a LangChain ChatModel to be compatible with browser-use's BaseChatModel protocol.
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
            
            # Handle list content (e.g. vision)
            if isinstance(content, list):
                # Simple conversion for now, browser-use uses specific parts
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
        
        # Mock usage for now
        usage = ChatInvokeUsage(
            prompt_tokens=0,
            prompt_cached_tokens=0,
            prompt_cache_creation_tokens=0,
            prompt_image_tokens=0,
            completion_tokens=0,
            total_tokens=0
        )

        # Handle structured output if requested
        if output_format:
            structured_llm = self.langchain_llm.with_structured_output(output_format)
            response = await structured_llm.ainvoke(lc_messages)
            return ChatInvokeCompletion(completion=response, usage=usage)
        else:
            response = await self.langchain_llm.ainvoke(lc_messages)
            return ChatInvokeCompletion(completion=response.content, usage=usage)
