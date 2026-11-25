import asyncio

from app.auth import AuthedUser
from app.orchestrator import Advisor
from app.prompts import DONT_KNOW
from app.retriever import RetrievedChunk
from app.tools import ToolResult

CHUNK = RetrievedChunk("c1", "tax-80c-basics", "80C allows Rs 1.5 lakh.", "Section 80C", "https://x.gov/", "Intro", "2025-04-01", 0.3)


class FakeRetriever:
    def __init__(self, chunks):
        self.chunks = chunks

    def search(self, q, k=None, use_threshold=True):
        return self.chunks


class FakeLLM:
    def __init__(self):
        self.called = False

    async def stream(self, system, messages, hard=False):
        self.called = True
        for t in ["Hello ", "world [1]"]:
            yield t


class FakeTools:
    def __init__(self):
        self.saved = None

    async def call(self, c):
        return ToolResult(c.name, True, {"total_spend_display": "₹100.00"})

    async def save_chat(self, q, a, s):
        self.saved = (q, a, s)


def run(adv, q):
    async def go():
        return [e async for e in adv.run(q, [], AuthedUser("1", "tok"))]

    return asyncio.run(go())


def test_normal_flow_streams_sources_and_saves():
    tools, llm = FakeTools(), FakeLLM()
    events = run(Advisor(FakeRetriever([CHUNK]), lambda: llm, lambda t: tools), "What is Section 80C?")
    assert "".join(e["text"] for e in events if e["type"] == "token") == "Hello world [1]"
    src = next(e for e in events if e["type"] == "sources")["sources"]
    assert src[0]["index"] == 1 and src[0]["as_of"] == "2025-04-01"
    assert events[-1]["type"] == "done" and tools.saved[1] == "Hello world [1]"


def test_no_context_says_i_dont_know_without_calling_llm():
    llm = FakeLLM()
    events = run(Advisor(FakeRetriever([]), lambda: llm, lambda t: FakeTools()), "Who won the IPL?")
    assert events[0]["text"] == DONT_KNOW and not llm.called


def test_personal_question_reports_used_tools():
    events = run(Advisor(FakeRetriever([]), lambda: FakeLLM(), lambda t: FakeTools()), "How much did I spend last month?")
    assert events[-1]["used_tools"] == ["get_spending_summary"]
