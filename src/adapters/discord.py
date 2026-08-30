import logging
import os
from pathlib import Path

import discord
from dotenv import load_dotenv

from src.config import validate_config
from src.core import process_message


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(
    PROJECT_ROOT / ".env"
)


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


TOKEN = os.getenv(
    "DISCORD_BOT_TOKEN",
    "",
).strip()

ALLOWED_USER_ID_RAW = os.getenv(
    "DISCORD_ALLOWED_USER_ID",
    "",
).strip()

ALLOWED_CHANNEL_ID_RAW = os.getenv(
    "DISCORD_ALLOWED_CHANNEL_ID",
    "",
).strip()


def required_int(
    name: str,
    value: str,
) -> int:

    if not value:
        raise RuntimeError(
            f"{name} fehlt."
        )

    try:
        return int(value)

    except ValueError as exc:
        raise RuntimeError(
            f"{name} muss eine numerische Discord-ID sein."
        ) from exc


ALLOWED_USER_ID = required_int(
    "DISCORD_ALLOWED_USER_ID",
    ALLOWED_USER_ID_RAW,
)

ALLOWED_CHANNEL_ID = required_int(
    "DISCORD_ALLOWED_CHANNEL_ID",
    ALLOWED_CHANNEL_ID_RAW,
)


class DiscordMessageAdapter:
    """
    Übersetzt eine Discord-Nachricht auf die kleine
    Schnittstelle, die der Assistant-Core erwartet.
    """

    def __init__(
        self,
        message: discord.Message,
    ):
        self.message = message

    async def reply_text(
        self,
        text: str,
    ) -> None:

        await self.message.reply(
            text,
            mention_author=False,
        )


class AssistantClient(
    discord.Client
):

    async def on_ready(self) -> None:

        logger.info(
            "Discord verbunden als %s (%s)",
            self.user,
            getattr(
                self.user,
                "id",
                None,
            ),
        )

        logger.info(
            "Erlaubter Benutzer: %s",
            ALLOWED_USER_ID,
        )

        logger.info(
            "Erlaubter Channel: %s",
            ALLOWED_CHANNEL_ID,
        )

    async def on_message(
        self,
        message: discord.Message,
    ) -> None:

        # Niemals Nachrichten von Bots verarbeiten.
        # Verhindert insbesondere Antwort-Loops.
        if message.author.bot:
            return

        # Nur dein Discord-Account.
        if message.author.id != ALLOWED_USER_ID:
            logger.warning(
                "Nicht erlaubter Discord-Benutzer abgelehnt: %s",
                message.author.id,
            )
            return

        # Nur der festgelegte Assistant-Channel.
        if message.channel.id != ALLOWED_CHANNEL_ID:
            logger.warning(
                "Nachricht aus nicht erlaubtem Channel ignoriert: %s",
                message.channel.id,
            )
            return

        text = message.content.strip()

        if not text:
            return

        logger.info(
            "Discord-Nachricht empfangen"
        )

        adapter = DiscordMessageAdapter(
            message
        )

        try:
            await process_message(
                adapter,
                text,
            )

        except Exception:
            logger.exception(
                "Verarbeitung der Discord-Nachricht fehlgeschlagen"
            )

            await adapter.reply_text(
                "Beim Verarbeiten der Nachricht ist ein Fehler "
                "aufgetreten. Ich habe nichts weiter verändert."
            )


def main() -> None:

    if not TOKEN:
        raise RuntimeError(
            "DISCORD_BOT_TOKEN fehlt."
        )

    validate_config()

    intents = discord.Intents.default()

    # Muss zusätzlich im Discord Developer Portal
    # aktiviert sein.
    intents.message_content = True

    client = AssistantClient(
        intents=intents,
    )

    logger.info(
        "Starte Discord Personal Assistant..."
    )

    client.run(
        TOKEN,
        log_handler=None,
    )


if __name__ == "__main__":
    main()
