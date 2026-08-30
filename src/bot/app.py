import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.bot.fast_router import parse_fast_intent
from src.bot.intent_executor import execute_intent
from src.config import validate_config
from src.llm.intent_parser import parse_intent


load_dotenv()


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "",
).strip()

ALLOWED_USER_ID_RAW = os.getenv(
    "TELEGRAM_ALLOWED_USER_ID",
    "",
).strip()


def get_allowed_user_id() -> int:
    if not ALLOWED_USER_ID_RAW:
        raise RuntimeError(
            "TELEGRAM_ALLOWED_USER_ID fehlt."
        )

    try:
        return int(ALLOWED_USER_ID_RAW)

    except ValueError as exc:
        raise RuntimeError(
            "TELEGRAM_ALLOWED_USER_ID muss eine Zahl sein."
        ) from exc


ALLOWED_USER_ID = get_allowed_user_id()


def user_is_allowed(update: Update) -> bool:
    user = update.effective_user

    return (
        user is not None
        and user.id == ALLOWED_USER_ID
    )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    if not user_is_allowed(update):
        return

    message = update.effective_message

    if message is None:
        return

    await message.reply_text(
        "Personal Assistant läuft.\n\n"
        "Du kannst mir normale Nachrichten schicken."
    )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    if not user_is_allowed(update):
        logger.warning(
            "Unauthorized Telegram user rejected: %s",
            getattr(
                update.effective_user,
                "id",
                None,
            ),
        )
        return

    message = update.effective_message

    if (
        message is None
        or message.text is None
    ):
        return

    text = message.text.strip()

    if not text:
        return

    logger.info(
        "Processing Telegram text message"
    )

    # -------------------------------------------------
    # 1. Schneller deterministischer Router
    # -------------------------------------------------
    #
    # Einfache und eindeutige Nachrichten werden ohne
    # lokales LLM verarbeitet.
    #
    # Beispiele:
    # - "ich muss noch Mehl kaufen"
    # - "Milch habe ich gekauft"
    # - "was muss ich einkaufen"
    # - "Immich muss ich noch machen"
    #
    # -------------------------------------------------

    try:
        fast_result = parse_fast_intent(text)

    except Exception:
        logger.exception(
            "Fast Router failed"
        )
        fast_result = None

    if fast_result is not None:
        logger.info(
            "Fast Router matched: "
            "intent=%s scope=%s confidence=%.2f",
            fast_result.intent,
            fast_result.scope,
            fast_result.confidence,
        )

        try:
            await execute_intent(
                message,
                fast_result,
            )

        except Exception:
            logger.exception(
                "Fast intent execution failed"
            )

            await message.reply_text(
                "Beim Ausführen ist ein Fehler aufgetreten. "
                "Ich habe die Aktion nicht weiter verarbeitet."
            )

        return

    # -------------------------------------------------
    # 2. Lokales LLM
    # -------------------------------------------------
    #
    # Nur wenn die Nachricht vom Fast Router nicht
    # eindeutig erkannt wurde.
    #
    # Das LLM interpretiert lediglich die Nachricht.
    # Die eigentliche Aktion wird weiterhin vom
    # kontrollierten Python-Executor ausgeführt.
    #
    # -------------------------------------------------

    logger.info(
        "No Fast Router match. "
        "Using local intent parser."
    )

    try:
        result = await parse_intent(text)

        logger.info(
            "LLM parsed: "
            "intent=%s scope=%s confidence=%.2f",
            result.intent,
            result.scope,
            result.confidence,
        )

        await execute_intent(
            message,
            result,
        )

    except Exception:
        logger.exception(
            "Local intent parser or executor failed"
        )

        await message.reply_text(
            "Die lokale Sprachverarbeitung ist gerade "
            "nicht verfügbar. Ich habe nichts verändert."
        )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    logger.exception(
        "Unhandled Telegram error",
        exc_info=context.error,
    )


def main() -> None:
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN fehlt."
        )

    validate_config()

    logger.info(
        "Starting Personal Assistant..."
    )

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            handle_message,
        )
    )

    application.add_error_handler(
        error_handler
    )

    application.run_polling(
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
