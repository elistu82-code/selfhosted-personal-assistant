import json
import logging
import os
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from src.memory.router import (
    all_scopes,
    aliases_for,
    resolve_scope_from_text,
)


logger = logging.getLogger(__name__)


OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434",
).rstrip("/")

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3.5:0.8b",
)

TIMEOUT = float(
    os.getenv(
        "LLM_TIMEOUT_SECONDS",
        "120",
    )
)

KEEP_ALIVE = os.getenv(
    "OLLAMA_KEEP_ALIVE",
    "30s",
)


IntentName = Literal[
    "shopping_add",
    "shopping_remove",
    "shopping_list",
    "todo_add",
    "todo_complete",
    "todo_list",
    "memory_add",
    "memory_search",
    "unknown",
]

Priority = Literal[
    "low",
    "normal",
    "high",
    "critical",
]


class IntentResult(BaseModel):
    intent: IntentName
    scope: str | None = None
    items: list[str] = Field(
        default_factory=list
    )
    content: str | None = None
    priority: Priority = "normal"
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
    )


def allowed_scopes() -> set[str]:
    return {
        scope["key"]
        for scope in all_scopes()
    }


SYSTEM_PROMPT = """
Klassifiziere deutsche Nachrichten für einen Assistenten.

Intents:
shopping_add, shopping_remove, shopping_list,
todo_add, todo_complete, todo_list,
memory_add, memory_search, unknown.

Fakten/Notizen = memory_add.
Etwas erledigen müssen = todo_add.
Frage nach Notizen = memory_search.
Frage nach Aufgaben = todo_list.

Antworte nur als kurzes JSON mit:
intent, items, content, priority, confidence.

items nur für Einkauf.
priority: normal, high oder critical.
Tippfehler sinngemäß korrigieren.
"""


async def parse_intent(
    text: str,
) -> IntentResult:

    detected_scope = resolve_scope_from_text(
        text
    )

    scope = (
        detected_scope["key"]
        if detected_scope
        else None
    )

    user_prompt = (
        f"scope={scope}\n"
        f"text={text}"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "stream": False,
        "think": False,

        # Nur gültiges JSON erzwingen.
        # KEIN großes Pydantic-Schema mehr.
        "format": "json",

        "options": {
            "temperature": 0,
            "num_ctx": 512,
            "num_predict": 80,
        },

        "keep_alive": KEEP_ALIVE,
    }

    async with httpx.AsyncClient(
        timeout=TIMEOUT
    ) as client:

        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
        )

        response.raise_for_status()

    data = response.json()

    raw = data[
        "message"
    ][
        "content"
    ]

    logger.info(
        "Ollama duration: %.2fs | "
        "prompt tokens: %s | "
        "output tokens: %s",
        data.get(
            "total_duration",
            0,
        ) / 1_000_000_000,
        data.get(
            "prompt_eval_count",
            "?",
        ),
        data.get(
            "eval_count",
            "?",
        ),
    )

    parsed = json.loads(raw)

    result = IntentResult(
        intent=parsed.get(
            "intent",
            "unknown",
        ),
        scope=scope,
        items=parsed.get(
            "items",
            [],
        ) or [],
        content=parsed.get(
            "content",
        ),
        priority=parsed.get(
            "priority",
            "normal",
        ),
        confidence=float(
            parsed.get(
                "confidence",
                0.8,
            )
        ),
    )

    # -----------------------------------------------
    # Harte Python-Normalisierung
    # -----------------------------------------------

    if result.scope not in allowed_scopes():
        result.scope = None

    if result.intent.startswith(
        "shopping_"
    ):
        result.scope = None
        result.priority = "normal"

    if result.intent in {
        "memory_add",
        "memory_search",
    }:
        result.priority = "normal"

    # Ein Shopping-Intent ohne Artikel ist nicht
    # sicher genug für eine schreibende Aktion.
    if (
        result.intent in {
            "shopping_add",
            "shopping_remove",
        }
        and not result.items
    ):
        result.intent = "unknown"
        result.confidence = 0.0

    return result
