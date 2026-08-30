import re

from src.config import VAULT_PATH
from src.memory.router import get_domain


def shopping_file():
    domain = get_domain("shopping")

    if not domain:
        raise RuntimeError(
            "Shopping-Domain fehlt in routing.yaml"
        )

    relative = domain.get("target_file")

    if not relative:
        raise RuntimeError(
            "Shopping target_file fehlt"
        )

    path = (VAULT_PATH / relative).resolve()

    if VAULT_PATH not in path.parents:
        raise RuntimeError(
            "Ungültiger Shopping-Pfad"
        )

    if not path.parent.exists():
        raise RuntimeError(
            f"Shopping-Ordner fehlt: {path.parent}"
        )

    return path


def normalize_item(item: str) -> str:
    item = item.strip()
    item = re.sub(r"\s+", " ", item)
    return item


def read_items() -> list[str]:
    path = shopping_file()

    if not path.exists():
        return []

    items: list[str] = []

    for line in path.read_text(
        encoding="utf-8"
    ).splitlines():

        match = re.match(
            r"^\s*[-*]\s+(?:\[[ xX]\]\s+)?(.+?)\s*$",
            line,
        )

        if match:
            item = normalize_item(match.group(1))

            if item:
                items.append(item)

    return items


def write_items(items: list[str]) -> None:
    path = shopping_file()

    content = "# Einkaufsliste\n\n"

    if items:
        content += "".join(
            f"- {item}\n"
            for item in items
        )

    path.write_text(
        content,
        encoding="utf-8",
        newline="\n",
    )


def add_items(new_items: list[str]) -> list[str]:
    items = read_items()

    existing = {
        item.casefold()
        for item in items
    }

    added: list[str] = []

    for item in new_items:
        item = normalize_item(item)

        if not item:
            continue

        if item.casefold() in existing:
            continue

        items.append(item)
        existing.add(item.casefold())
        added.append(item)

    write_items(items)

    return added


def remove_items(
    requested: list[str],
) -> list[str]:

    items = read_items()
    requested_lower = {
        normalize_item(item).casefold()
        for item in requested
    }

    kept: list[str] = []
    removed: list[str] = []

    for item in items:
        if item.casefold() in requested_lower:
            removed.append(item)
        else:
            kept.append(item)

    write_items(kept)

    return removed
