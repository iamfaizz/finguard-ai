
import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.auth import AuthedUser, get_current_user
from app.config import settings
from app.llm_client import get_llm
from app.orchestrator import Advisor
from app.rate_limit import RateLimiter
from app.retriever import Retriever
from app.tools import BackendTools
from shared.contracts.advisor import ChatRequest, ChatResponse, Source

log = logging.getLogger("advisor")

retriever = Retriever()
rate_limiter = RateLimiter(settings.rate_limit_per_min)

advisor = Advisor(
    retriever=retriever,
    llm_factory=get_llm,
    tools_factory=lambda token: BackendTools(token),
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await asyncio.to_thread(retriever.warm)
    except Exception:  # noqa: BLE001
        log.exception("retriever warm-up failed")
    yield


app = FastAPI(
    title="FinGuard Advisor",
    version="1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    ],
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type"],
)


def _llm_configuration() -> tuple[bool, str]:
    """Check whether the selected provider has its required configuration."""

    provider = settings.llm_provider.strip().lower()

    if provider == "ollama":
        configured = bool(
            settings.ollama_base_url.strip()
            and settings.ollama_model.strip()
        )
        return configured, provider

    if provider == "claude":
        configured = bool(settings.anthropic_api_key.strip())
        return configured, provider

    return False, provider


@app.get("/health")
def health() -> dict:
    configured, provider = _llm_configuration()

    return {
        "status": "ok",
        "provider": provider,
        "llm_configured": configured,
    }


def _sse(event: dict) -> str:
    payload = {
        key: value
        for key, value in event.items()
        if key != "type"
    }
    return (
        f"event: {event['type']}\n"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    )


async def _event_stream(
    req: ChatRequest,
    user: AuthedUser,
) -> AsyncIterator[str]:
    try:
        async for event in advisor.run(
            req.message,
            req.history,
            user,
        ):
            yield _sse(event)

    except Exception:  # noqa: BLE001
        log.exception("chat failed")
        yield _sse({
            "type": "error",
            "message": (
                "The advisor is temporarily unavailable. "
                "Please try again."
            ),
        })


@app.post("/chat")
async def chat(
    req: ChatRequest,
    user: AuthedUser = Depends(get_current_user),
):
    if not rate_limiter.check(user.user_id):
        raise HTTPException(
            status_code=429,
            detail="Too many requests",
            headers={"Retry-After": "30"},
        )

    configured, provider = _llm_configuration()

    if not configured:
        log.error(
            "LLM provider '%s' is not properly configured",
            provider,
        )

        if req.stream:
            return StreamingResponse(
                _event_stream(req, user),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        raise HTTPException(
            status_code=503,
            detail="Advisor LLM is not configured",
        )

    if req.stream:
        return StreamingResponse(
            _event_stream(req, user),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    answer: list[str] = []
    sources: list[dict] = []
    used: list[str] = []
    refused = False

    try:
        async for event in advisor.run(
            req.message,
            req.history,
            user,
        ):
            if event["type"] == "token":
                answer.append(event["text"])

            elif event["type"] == "sources":
                sources = event["sources"]

            elif event["type"] == "done":
                used = event["used_tools"]
                refused = event["refused"]

    except Exception:  # noqa: BLE001
        log.exception("chat failed")
        raise HTTPException(
            status_code=503,
            detail="Advisor temporarily unavailable",
        ) from None

    return ChatResponse(
        answer="".join(answer),
        sources=[Source(**source) for source in sources],
        used_tools=used,
        refused=refused,
    )
