"""Cheap deterministic checks that run BEFORE any LLM call (Step 5.4 / 8.3)."""
import re
from dataclasses import dataclass

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
# stop users/history from forging our prompt delimiters
TAG_RE = re.compile(r"</?\s*(knowledge|passage|verified_numbers|question|system)\s*>", re.I)

INJECTION = [
    r"ignore\s+(all\s+|any\s+|your\s+|the\s+|previous\s+|prior\s+|above\s+)*(instructions|rules|prompts?)",
    r"disregard\s+.{0,30}(instructions|rules)",
    r"forget\s+(all\s+|your\s+)?(instructions|rules)",
    r"(reveal|show|print|repeat|leak).{0,30}(system prompt|your instructions|your rules|your prompt)",
    r"\byou are now\b",
    r"\bact as\b.{0,20}\b(dan|unrestricted|jailbroken)\b",
    r"developer mode|jailbreak|pretend you have no (rules|restrictions)",
]
OTHER_USER = [
    r"\buser\s*(id\s*)?#?\d+",
    r"\b(another|other|different)\s+users?\b",
    r"\b(someone|somebody)\s+else'?s?\b",
    r"\b(all|every)\s*(users?|one'?s)\b.{0,30}(spending|data|transactions|balance)",
]
STOCK_TIPS = [
    r"\b(which|what|best|top)\b.{0,40}\b(stocks?|shares?)\b.{0,40}\b(buy|invest|pick|purchase)\b",
    r"\b(stock|share|market)\s+tips?\b",
    r"\bmultibaggers?\b",
]

MESSAGES = {
    "injection": "I can't change my rules or share my internal instructions. I'm happy to help with budgeting, saving, UPI safety or your own spending numbers.",
    "other_user": "I can only see your own account data, so I can't look at anyone else's transactions or spending.",
    "stock_tip": "I can't give stock tips or tell you what to buy. I can explain how index funds, SIPs or diversification work if that helps.",
    "empty": "Please type a question about your money and I'll do my best to help.",
    "too_long": "That message is too long. Please shorten it to a couple of sentences.",
}


@dataclass(frozen=True)
class GuardResult:
    blocked: bool
    reason: str | None = None
    message: str | None = None
    clean: str = ""


def sanitize(text: str) -> str:
    return TAG_RE.sub("", CONTROL_CHARS.sub("", text)).strip()


def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def check_input(text: str, max_chars: int) -> GuardResult:
    clean = sanitize(text)
    if not clean:
        return GuardResult(True, "empty", MESSAGES["empty"], clean)
    if len(clean) > max_chars:
        return GuardResult(True, "too_long", MESSAGES["too_long"], clean)
    norm = re.sub(r"\s+", " ", clean.lower())
    for reason, pats in (("other_user", OTHER_USER), ("injection", INJECTION), ("stock_tip", STOCK_TIPS)):
        if _any(pats, norm):
            return GuardResult(True, reason, MESSAGES[reason], clean)
    return GuardResult(False, None, None, clean)