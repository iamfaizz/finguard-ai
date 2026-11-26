"""Chat pipeline: guard -> route tools -> retrieve -> (LLM explains) -> stream + cite."""
import asyncio
import json
import re
from collections.abc import AsyncIterator, Callable

from app.auth import AuthedUser
from app.config import settings
from app.guards import check_input, sanitize
from app.prompts import DONT_KNOW, NEEDS_AMOUNT, SYSTEM_PROMPT, TOOLS_DOWN
from app.retriever import RetrievedChunk
from app.router import needs_amount, route
from shared.contracts.advisor import HistoryItem, Source

HARD_HINT = re.compile(r"\b(compare|vs|versus|which is better|tax|regime|should i|explain)\b", re.I)


def build_context(chunks: list[RetrievedChunk], results: list, extra_note: str = "") -> str:
    parts = ["<knowledge>"]
    for i, c in enumerate(chunks, 1):
        parts.append(f"[{i}] {c.title} | section: {c.section} | as of {c.as_of}\n{c.text}")
    parts.append("</knowledge>")
    verified = {r.name: (r.data if r.ok else "UNAVAILABLE") for r in results}
    if extra_note:
        verified["note"] = extra_note
    parts.append("<verified_numbers>\n" + json.dumps(verified, ensure_ascii=False, default=str) + "\n</verified_numbers>")
    return "\n".join(parts)


def build_sources(chunks: list[RetrievedChunk]) -> list[dict]:
    return [
        Source(index=i, title=c.title, source_url=c.source_url, section=c.section,
               as_of=c.as_of, snippet=c.text[:300]).model_dump()
        for i, c in enumerate(chunks, 1)
    ]


class Advisor:
    def __init__(self, retriever, llm_factory: Callable, tools_factory: Callable) -> None:
        self._retriever = retriever
        self._llm_factory = llm_factory
        self._tools_factory = tools_factory

    async def run(self, question: str, history: list[HistoryItem], user: AuthedUser) -> AsyncIterator[dict]:
        guard = check_input(question, settings.max_question_chars)
        if guard.blocked:
            yield {"type": "token", "text": guard.message}
            yield {"type": "sources", "sources": []}
            yield {"type": "done", "refused": True, "used_tools": [], "reason": guard.reason}
            return

        question = guard.clean
        calls = route(question)
        tools = self._tools_factory(user.token)
        tool_task = asyncio.gather(*(tools.call(c) for c in calls))
        chunks = await asyncio.to_thread(self._retriever.search, question, settings.top_k)
        results = await tool_task
        ok = [r for r in results if r.ok]

        if not chunks and not ok:
            msg = TOOLS_DOWN if calls else DONT_KNOW
            yield {"type": "token", "text": msg}
            yield {"type": "sources", "sources": []}
            yield {"type": "done", "refused": not calls, "used_tools": []}
            return

        note = NEEDS_AMOUNT if needs_amount(question, calls) else ""
        user_msg = f"{build_context(chunks, results, note)}\n<question>\n{question}\n</question>"
        messages = [{"role": h.role, "content": sanitize(h.content)} for h in history]
        messages.append({"role": "user", "content": user_msg})
        hard = bool(ok) or len(question) > 200 or bool(HARD_HINT.search(question))

        parts: list[str] = []
        async for piece in self._llm_factory().stream(SYSTEM_PROMPT, messages, hard=hard):
            parts.append(piece)
            yield {"type": "token", "text": piece}

        sources = build_sources(chunks)
        yield {"type": "sources", "sources": sources}
        await tools.save_chat(question, "".join(parts), sources)
        yield {"type": "done", "refused": False, "used_tools": [r.name for r in ok]}
