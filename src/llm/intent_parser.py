import logging
import os
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError, model_validator

from src.memory.router import all_scopes, aliases_for


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
    os.getenv("LLM_TIMEOUT_SECONDS", "60")
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
    # Alle Felder sind absichtlich REQUIRED.
    # Das Modell darf nicht einfach Pydantic-Defaults übernehmen.
    intent: IntentName
    scope: str | None
    items: list[str]
    content: str | None
    priority: Priority
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def validate_semantics(self):
        if self.intent in {
            "shopping_add",
            "shopping_remove",
        } and not self.items:
            raise ValueError(
                f"{self.intent} benötigt mindestens einen Artikel in items."
            )

        if self.intent in {
            "todo_add",
            "todo_complete",
            "memory_add",
        } and not self.content:
            raise ValueError(
                f"{self.intent} benötigt content."
            )

        return self


def allowed_scopes() -> dict[str, list[str]]:
    result = {}

    for scope in all_scopes():
        result[scope["key"]] = aliases_for(scope)

    return result


def scope_prompt() -> str:
    return "\n".join(
        f"- {key}: {', '.join(aliases)}"
        for key, aliases in allowed_scopes().items()
    )


SYSTEM_PROMPT = """
Du bist ausschließlich der Intent-Parser eines privaten Personal Assistants.

Deine einzige Aufgabe:
Eine deutsche Nutzernachricht in das vorgegebene JSON-Schema übersetzen.

Du bist KEIN Chatbot.
Du beantwortest die Nachricht NICHT.
Du führst KEINE Aktion aus.
Du erfindest KEINE Informationen.

Der Nutzer schreibt oft:
- umgangssprachlich
- ohne Satzzeichen
- mit Tippfehlern
- mit vertauschten Buchstaben
- in unterschiedlichem Satzbau

Verstehe die Bedeutung trotzdem.

ERLAUBTE INTENTS

shopping_add
Der Nutzer möchte einen oder mehrere Artikel kaufen oder auf die
Einkaufsliste setzen.

shopping_remove
Der Nutzer hat einen oder mehrere Artikel gekauft/geholt oder möchte
sie von der Einkaufsliste entfernen.

shopping_list
Der Nutzer möchte wissen, was auf der Einkaufsliste steht.

todo_add
Etwas muss noch erledigt werden.

todo_complete
Eine bestehende Aufgabe wurde erledigt.

todo_list
Der Nutzer fragt nach offenen Aufgaben.

memory_add
Eine Information, Erkenntnis, Entscheidung oder Notiz soll dauerhaft
zu einem Thema gespeichert werden.

memory_search
Der Nutzer fragt danach, was zu einem Thema gespeichert/notiert wurde.

unknown
Die Bedeutung passt nicht ausreichend sicher zu einem erlaubten Intent.


SEHR WICHTIGE REGELN FÜR EINKAUF

Bei shopping_add und shopping_remove MUSS items mindestens einen
genannten Artikel enthalten.

Extrahiere nur die eigentlichen Artikel.

Beispiele:

"ich muss noch mehl kaufen"
=> intent=shopping_add
=> items=["Mehl"]

"ich muss mehl einkaufen"
=> intent=shopping_add
=> items=["Mehl"]

"brauch noch milch"
=> intent=shopping_add
=> items=["Milch"]

"reis und nudeln muss ich noch holen"
=> intent=shopping_add
=> items=["Reis", "Nudeln"]

"ich muss noch eier, milch und butter kaufen"
=> intent=shopping_add
=> items=["Eier", "Milch", "Butter"]

"hab milhc gekauft"
=> intent=shopping_remove
=> items=["Milch"]

"eier hab ich schon geholt"
=> intent=shopping_remove
=> items=["Eier"]

"reis und butter sind gekauft"
=> intent=shopping_remove
=> items=["Reis", "Butter"]

"was muss ich noch einkaufen"
=> intent=shopping_list
=> items=[]

Korrigiere offensichtliche Tippfehler bei Artikeln:
milhc -> Milch
mhel -> Mehl
nudlen -> Nudeln

Bei Einkauf:
- scope=null
- content darf null sein
- priority=normal


REGELN FÜR TODOS UND MEMORY

"immich muss ich noch machen das hat oberste prio"
=> intent=todo_add
=> scope=immich
=> content="Immich fertigstellen"
=> priority=high

"bei immich muss ich noch das backup testen"
=> intent=todo_add
=> scope=immich
=> content="Backup testen"

"bei immich braucht machine learning ziemlich viel ram"
=> intent=memory_add
=> scope=immich
=> content="Machine Learning benötigt ziemlich viel RAM."

"was hatte ich zu immich notiert"
=> intent=memory_search
=> scope=immich

"was muss ich noch bei immich machen"
=> intent=todo_list
=> scope=immich


SCOPE-REGELN

- Verwende ausschließlich einen erlaubten Scope-Key.
- Erfinde niemals einen Scope.
- Wenn kein Thema eindeutig erkannt wird: scope=null.
- Ein genanntes Ober-/Unterthema ist KEIN Grund für memory_add,
  wenn der Satz eigentlich eine Aufgabe beschreibt.


PRIORITÄT

"oberste prio", "sehr wichtig", "dringend"
=> high

"kritisch", "unbedingt sofort"
=> critical

Normale Aufgabe
=> normal


CONFIDENCE

Gib eine realistische Sicherheit zwischen 0 und 1 an.

0.90-1.00 = sehr eindeutig
0.70-0.89 = wahrscheinlich eindeutig
0.50-0.69 = unsicher
unter 0.50 = besser unknown
"""


async def _ollama_request(
    user_text: str,
    correction: str | None = None,
) -> str:

    user_prompt = (
        "Erlaubte Scopes:\n"
        + scope_prompt()
        + "\n\nNutzernachricht:\n"
        + user_text
    )

    if correction:
        user_prompt += (
            "\n\nWICHTIG: Deine vorherige JSON-Ausgabe war ungültig.\n"
            + correction
            + "\nErzeuge die JSON-Ausgabe jetzt vollständig und korrekt neu."
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
        "format": IntentResult.model_json_schema(),
        "options": {
            "temperature": 0,
            "num_ctx": 2048,
            "num_predict": 160,
        },
        "keep_alive": "5m",
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

    return data["message"]["content"]


async def parse_intent(text: str) -> IntentResult:
    raw = await _ollama_request(text)

    try:
        result = IntentResult.model_validate_json(raw)

    except ValidationError as exc:
        logger.warning(
            "Ungültiger LLM-Intent, starte einen Reparaturversuch: %s",
            exc,
        )

        raw = await _ollama_request(
            text,
            correction=str(exc),
        )

        result = IntentResult.model_validate_json(raw)

    scopes = allowed_scopes()

    # Harte Sicherheitsgrenze:
    # Kein vom LLM erfundener Scope darf weitergegeben werden.
    if (
        result.scope is not None
        and result.scope not in scopes
    ):
        logger.warning(
            "LLM erfand unbekannten Scope: %s",
            result.scope,
        )

        result.scope = None
        result.confidence = min(
            result.confidence,
            0.49,
        )

    # Shopping besitzt keinen thematischen Scope.
    if result.intent.startswith("shopping_"):
        result.scope = None
        result.priority = "normal"

    # Memory-Informationen besitzen keine Aufgabenpriorität.
    if result.intent in {
        "memory_add",
        "memory_search",
    }:
        result.priority = "normal"

    return result