from datetime import datetime
from pathlib import Path

from src.config import VAULT_PATH
from src.memory.router import inbox_path, resolve_topic


def _safe_target(relative_path: str) -> Path:
    target = (VAULT_PATH / relative_path).resolve()

    if VAULT_PATH not in target.parents and target != VAULT_PATH:
        raise ValueError("Ungültiger Vault-Pfad")

    return target


def _append(target: Path, content: str) -> None:
    # WICHTIG:
    # Der Bot erzeugt keine neuen Ordner.
    if not target.parent.exists():
        raise FileNotFoundError(
            f"Zielordner existiert nicht: {target.parent}"
        )

    timestamp = datetime.now().astimezone().strftime(
        "%Y-%m-%d %H:%M"
    )

    if not target.exists():
        target.write_text(
            f"# {target.stem}\n\n",
            encoding="utf-8",
        )

    with target.open("a", encoding="utf-8", newline="\n") as file:
        file.write(
            f"\n- {timestamp} — {content.strip()}\n"
        )


def write_note(topic: str, content: str) -> tuple[str, bool]:
    scope = resolve_topic(topic)

    # Nicht verstanden -> Inbox.
    if scope is None:
        target = _safe_target(inbox_path())
        _append(
            target,
            f"[Unklar: {topic}] {content}",
        )

        return str(
            target.relative_to(VAULT_PATH)
        ), False

    relative_directory = scope.get("path")

    if not relative_directory:
        target = _safe_target(inbox_path())
        _append(target, content)

        return str(
            target.relative_to(VAULT_PATH)
        ), False

    directory = _safe_target(relative_directory)

    # Existiert der registrierte Ordner nicht:
    # KEIN mkdir. -> Inbox.
    if not directory.exists() or not directory.is_dir():
        target = _safe_target(inbox_path())

        _append(
            target,
            f"[Ordner fehlt: {topic}] {content}",
        )

        return str(
            target.relative_to(VAULT_PATH)
        ), False

    target = directory / "Notes.md"

    _append(target, content)

    return str(
        target.relative_to(VAULT_PATH)
    ), True
