"""One small LLMClient interface; LangChain chat models sit behind it.

Switch provider with LLM_PROVIDER=claude|ollama - nothing else changes.
"""
from collections.abc import AsyncIterator
from typing import Protocol

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.config import settings


class LLMClient(Protocol):
    def stream(self, system: str, messages: list[dict], hard: bool = False) -> AsyncIterator[str]: ...


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")


class LangChainLLM:
    def __init__(self) -> None:
        if settings.llm_provider == "ollama":
            from langchain_ollama import ChatOllama

            m = ChatOllama(model=settings.ollama_model, base_url=settings.ollama_base_url,
                           temperature=settings.temperature, num_predict=settings.max_output_tokens)
            self._fast = self._smart = m
        else:
            if not settings.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not set")
            from langchain_anthropic import ChatAnthropic

            def make(name: str) -> ChatAnthropic:
                return ChatAnthropic(model=name, api_key=settings.anthropic_api_key,
                                     temperature=settings.temperature,
                                     max_tokens=settings.max_output_tokens,
                                     timeout=settings.llm_timeout_s)

            self._fast, self._smart = make(settings.llm_model_fast), make(settings.llm_model_smart)

    async def stream(self, system: str, messages: list[dict], hard: bool = False) -> AsyncIterator[str]:
        model = self._smart if hard else self._fast
        lc = [SystemMessage(content=system)] + [
            HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"])
            for m in messages
        ]
        async for chunk in model.astream(lc):
            piece = _text(chunk.content)
            if piece:
                yield piece


_llm: LangChainLLM | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LangChainLLM()
    return _llm
