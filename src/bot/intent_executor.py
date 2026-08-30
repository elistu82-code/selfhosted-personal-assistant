import logging

from src.llm.intent_parser import IntentResult
from src.memory.writer import write_note
from src.tasks.shopping import (
    add_items,
    read_items,
    remove_items,
)
from src.tasks.todos import (
    add_todo,
    complete_todo,
    list_todos,
)


logger = logging.getLogger(__name__)


async def execute_intent(
    message,
    result: IntentResult,
) -> None:

    logger.info(
        "Intent=%s scope=%s confidence=%.2f",
        result.intent,
        result.scope,
        result.confidence,
    )

    if result.intent == "unknown" or result.confidence < 0.50:
        await message.reply_text(
            "Ich bin mir nicht sicher, was du meinst. "
            "Ich habe deshalb nichts verändert."
        )
        return

    # Einkauf hinzufügen
    if result.intent == "shopping_add":

        if not result.items:
            logger.warning(
                "shopping_add ohne items: %s",
                result.model_dump(),
            )

            await message.reply_text(
                "Ich habe verstanden, dass du etwas einkaufen möchtest, "
                "aber den Artikel nicht sicher erkannt. "
                "Ich habe nichts verändert."
            )
            return

        added = add_items(result.items)

        if added:
            await message.reply_text(
                "Einkauf hinzugefügt: "
                + ", ".join(added)
            )
        else:
            await message.reply_text(
                "Diese Artikel stehen bereits auf der Liste: "
                + ", ".join(result.items)
            )

        return

    # Einkauf entfernen
    if result.intent == "shopping_remove":

        if not result.items:
            logger.warning(
                "shopping_remove ohne items: %s",
                result.model_dump(),
            )

            await message.reply_text(
                "Ich habe verstanden, dass du etwas gekauft hast, "
                "aber den Artikel nicht sicher erkannt. "
                "Ich habe nichts verändert."
            )
            return

        removed = remove_items(result.items)

        if removed:
            await message.reply_text(
                "Einkauf entfernt: "
                + ", ".join(removed)
            )
        else:
            await message.reply_text(
                "Nicht auf der Einkaufsliste gefunden: "
                + ", ".join(result.items)
            )

        return

    # Einkaufsliste anzeigen
    if result.intent == "shopping_list":
        items = read_items()

        if not items:
            await message.reply_text(
                "Die Einkaufsliste ist leer."
            )
            return

        await message.reply_text(
            "Einkaufsliste:\n\n"
            + "\n".join(
                f"• {item}"
                for item in items
            )
        )
        return

    # Todo hinzufügen
    if result.intent == "todo_add":

        if not result.content:
            await message.reply_text(
                "Die Aufgabe war nicht eindeutig."
            )
            return

        created = add_todo(
            content=result.content,
            scope=result.scope,
            priority=result.priority,
        )

        if created:
            scope = (
                f" [{result.scope}]"
                if result.scope
                else ""
            )

            await message.reply_text(
                f"Todo{scope} gespeichert "
                f"({result.priority})."
            )
        else:
            await message.reply_text(
                "Dieses Todo ist bereits offen."
            )

        return

    # Todos anzeigen
    if result.intent == "todo_list":
        tasks = list_todos(result.scope)

        if not tasks:
            await message.reply_text(
                "Keine passenden offenen Todos."
            )
            return

        lines = []

        for task in tasks:
            scope = (
                f' [{task["scope"]}]'
                if task["scope"]
                else ""
            )

            lines.append(
                f'• [{task["priority"].upper()}]'
                f'{scope} {task["content"]}'
            )

        await message.reply_text(
            "Offene Todos:\n\n"
            + "\n".join(lines)
        )
        return

    # Todo erledigen
    if result.intent == "todo_complete":

        if not result.content:
            await message.reply_text(
                "Welches Todo meinst du?"
            )
            return

        task = complete_todo(
            result.content,
            result.scope,
        )

        if task:
            await message.reply_text(
                f'Erledigt: {task["content"]}'
            )
        else:
            await message.reply_text(
                "Kein passendes offenes Todo gefunden."
            )

        return

    # Memory speichern
    if result.intent == "memory_add":

        if not result.content:
            await message.reply_text(
                "Die Notiz war nicht eindeutig."
            )
            return

        topic = result.scope or "unbekannt"

        target, routed = write_note(
            topic,
            result.content,
        )

        if routed:
            await message.reply_text(
                f"Notiert unter {result.scope}."
            )
        else:
            await message.reply_text(
                "Kein eindeutiges Oberthema. "
                "Ich habe es in die Inbox gelegt."
            )

        logger.info(
            "Memory target: %s",
            target,
        )
        return

    # Memory-Suche kommt als nächstes
    if result.intent == "memory_search":
        await message.reply_text(
            "Die Memory-Suche habe ich verstanden. "
            "Die bauen wir als nächsten Schritt ein."
        )
        return

    await message.reply_text(
        "Intent erkannt, aber noch nicht implementiert."
    )
