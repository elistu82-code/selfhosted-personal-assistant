import re
from difflib import SequenceMatcher

from src.llm.intent_parser import IntentResult
from src.memory.router import (
    all_scopes,
    aliases_for,
    normalize,
    resolve_scope_from_text,
)
from src.tasks.shopping import read_items


def split_items(text: str) -> list[str]:
    text = re.sub(
        r"\s+und\s+",
        ",",
        text,
        flags=re.IGNORECASE,
    )

    return [
        item.strip(" .,!?")
        for item in re.split(r"[,;]", text)
        if item.strip(" .,!?")
    ]


def fuzzy_scope(text: str) -> str | None:
    # Erst normale/exakte Scope-Erkennung.
    scope = resolve_scope_from_text(text)

    if scope:
        return scope["key"]

    normalized = normalize(text)
    words = normalized.split()

    best_score = 0.0
    best_scope = None

    for scope in all_scopes():
        for alias in aliases_for(scope):
            alias_normalized = normalize(alias)

            # Für mehrteilige Aliase passende Wortgruppen prüfen.
            alias_words = alias_normalized.split()
            size = len(alias_words)

            candidates = []

            for index in range(len(words) - size + 1):
                candidates.append(
                    " ".join(words[index:index + size])
                )

            for candidate in candidates:
                score = SequenceMatcher(
                    None,
                    candidate,
                    alias_normalized,
                ).ratio()

                if score > best_score:
                    best_score = score
                    best_scope = scope["key"]

    # Absichtlich relativ streng, um falsches Routing zu vermeiden.
    if best_score >= 0.80:
        return best_scope

    return None


def match_existing_shopping_item(
    requested: str,
) -> str:
    existing = read_items()

    if not existing:
        return requested.strip().capitalize()

    requested_normalized = normalize(requested)

    best_score = 0.0
    best_item = None

    for item in existing:
        score = SequenceMatcher(
            None,
            requested_normalized,
            normalize(item),
        ).ratio()

        if score > best_score:
            best_score = score
            best_item = item

    # Beispiel: "milhc" -> vorhandenes "Milch"
    if best_item and best_score >= 0.72:
        return best_item

    return requested.strip().capitalize()


def shopping_list_intent(text: str) -> IntentResult | None:
    lower = normalize(text)

    shopping_words = (
        "einkauf",
        "einkaufen",
        "einkaufsliste",
        "laden",
        "supermarkt",
    )

    question_words = (
        "was ",
        "was muss",
        "was brauch",
        "was brauche",
        "was steht",
        "zeig",
        "liste",
    )

    if (
        any(word in lower for word in shopping_words)
        and any(word in lower for word in question_words)
    ):
        return IntentResult(
            intent="shopping_list",
            scope=None,
            items=[],
            content=None,
            priority="normal",
            confidence=0.99,
        )

    return None


def shopping_remove_intent(
    text: str,
) -> IntentResult | None:

    patterns = [
        r"^(?:ich habe |ich hab |hab )?(.+?) gekauft[.!]?$",
        r"^(?:ich habe |ich hab |hab )?(.+?) geholt[.!]?$",
        r"^(.+?) (?:ist|sind) gekauft[.!]?$",

    ]

    for pattern in patterns:
        match = re.match(
            pattern,
            text.strip(),
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        raw_items = split_items(match.group(1))

        items = [
            match_existing_shopping_item(item)
            for item in raw_items
        ]

        if not items:
            return None

        return IntentResult(
            intent="shopping_remove",
            scope=None,
            items=items,
            content=None,
            priority="normal",
            confidence=0.98,
        )

    return None


def shopping_add_intent(
    text: str,
) -> IntentResult | None:

    patterns = [
        r"^ich muss noch (.+?) (?:kaufen|einkaufen|holen|besorgen)[.!]?$",
        r"^ich muss (.+?) (?:kaufen|einkaufen|holen|besorgen)[.!]?$",
        r"^ich brauche noch (.+?)[.!]?$",
        r"^ich brauche (.+?)[.!]?$",
        r"^brauch noch (.+?)[.!]?$",
        r"^brauche noch (.+?)[.!]?$",
        r"^(.+?) muss ich noch (?:kaufen|einkaufen|holen|besorgen)[.!]?$",
    ]

    for pattern in patterns:
        match = re.match(
            pattern,
            text.strip(),
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        items = [
            item.capitalize()
            for item in split_items(match.group(1))
        ]

        if not items:
            return None

        return IntentResult(
            intent="shopping_add",
            scope=None,
            items=items,
            content=None,
            priority="normal",
            confidence=0.98,
        )

    return None


def todo_intent(text: str) -> IntentResult | None:
    lower = normalize(text)
    scope = fuzzy_scope(text)

    if not scope:
        return None

    # Fragen nach offenen Aufgaben.
    todo_question_markers = (
        "was muss ich noch",
        "was ist noch offen",
        "welche todos",
        "welche aufgaben",
    )

    if any(marker in lower for marker in todo_question_markers):
        return IntentResult(
            intent="todo_list",
            scope=scope,
            items=[],
            content=None,
            priority="normal",
            confidence=0.96,
        )

    # Sehr typische Aufgabenformulierungen.
    todo_markers = (
        "muss ich noch",
        "muss noch",
        "noch machen",
        "noch erledigen",
        "steht noch aus",
    )

    if not any(marker in lower for marker in todo_markers):
        return None

    priority = "normal"

    if any(
        marker in lower
        for marker in (
            "oberste prio",
            "sehr wichtig",
            "dringend",
        )
    ):
        priority = "high"

    if any(
        marker in lower
        for marker in (
            "kritisch",
            "unbedingt sofort",
        )
    ):
        priority = "critical"

    # Spezialfall:
    # "immich muss ich noch machen"
    simple_pattern = re.match(
        r"^(.+?) muss ich noch machen",
        text.strip(),
        flags=re.IGNORECASE,
    )

    if simple_pattern:
        content = (
            simple_pattern.group(1).strip().capitalize()
            + " fertigstellen"
        )
    else:
        content = re.sub(
            r"\b(?:oberste prio|sehr wichtig|dringend)\b",
            "",
            text,
            flags=re.IGNORECASE,
        )

        content = re.sub(
            r"\s+",
            " ",
            content,
        ).strip(" .,!")

    return IntentResult(
        intent="todo_add",
        scope=scope,
        items=[],
        content=content,
        priority=priority,
        confidence=0.93,
    )

def memory_search_intent(
    text: str,
) -> IntentResult | None:

    lower = normalize(text)
    scope = fuzzy_scope(text)

    if not scope:
        return None

    markers = (
        "was weiss ich",
        "was habe ich",
        "was hab ich",
        "was hatte ich",
        "was steht",
        "was ist gespeichert",
        "was habe ich notiert",
        "was hab ich notiert",
        "was hatte ich notiert",
        "zeig mir",
        "zeige mir",
        "suche",
        "/search",
    )

    if not any(
        marker in lower
        for marker in markers
    ):
        return None

    return IntentResult(
        intent="memory_search",
        scope=scope,
        items=[],
        content=text.strip(),
        priority="normal",
        confidence=0.98,
    )

def parse_fast_intent(
    text: str,
) -> IntentResult | None:

    handlers = (
    shopping_list_intent,
    shopping_remove_intent,
    shopping_add_intent,
    todo_intent,
    memory_search_intent,
)

    for handler in handlers:
        result = handler(text)

        if result is not None:
            return result

    # Keine eindeutige Regel:
    # jetzt darf das lokale LLM übernehmen.
    return None
