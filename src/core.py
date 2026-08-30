import asyncio
import logging

from src.bot.fast_router import parse_fast_intent
from src.bot.intent_executor import execute_intent
from src.llm.intent_parser import parse_intent


logger = logging.getLogger(__name__)


# Es darf immer nur eine lokale LLM-Anfrage gleichzeitig laufen.
# Dadurch können mehrere Discord-Nachrichten nicht gleichzeitig
# Ollama belasten.
LLM_LOCK = asyncio.Lock()


async def process_message(
    message,
    text: str,
) -> None:

    text = text.strip()

    if not text:
        return

    # -------------------------------------------------
    # 1. Schneller deterministischer Router
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

        await execute_intent(
            message,
            fast_result,
        )
        return

    # -------------------------------------------------
    # 2. Lokales LLM nur als Fallback
    # -------------------------------------------------

    logger.info(
        "No Fast Router match. "
        "Waiting for local LLM."
    )

    async with LLM_LOCK:

        logger.info(
            "Using local LLM."
        )

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
