import json
import re

from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from src.config import VAULT_PATH
from src.memory.router import (
    inbox_path,
    normalize,
    resolve_scope_from_text,
)


SYSTEM_DIR = VAULT_PATH / "_System"
INDEX_DIR = SYSTEM_DIR / "indexes"
LOG_DIR = SYSTEM_DIR / "logs"

INDEX_FILE = INDEX_DIR / "memory-index.json"


def markdown_files() -> list[Path]:
    files = []

    for path in VAULT_PATH.rglob("*.md"):
        relative = path.relative_to(VAULT_PATH)

        if not relative.parts:
            continue

        # Obsidian-Konfiguration und generierte
        # Systemdateien nicht erneut indexieren.
        if relative.parts[0] in {
            ".obsidian",
            "_System",
        }:
            continue

        files.append(path)

    return files


def clean_entry(line: str) -> str | None:
    text = line.strip()

    if not text.startswith("- "):
        return None

    text = text[2:].strip()

    # Timestamp entfernen:
    # 2026-08-30 22:21 — ...
    text = re.sub(
        r"^\d{4}-\d{2}-\d{2} "
        r"\d{2}:\d{2}\s+—\s+",
        "",
        text,
    )

    return text.strip() or None


def build_index() -> list[dict]:
    entries = []

    for path in markdown_files():

        try:
            lines = path.read_text(
                encoding="utf-8"
            ).splitlines()
        except (OSError, UnicodeError):
            continue

        relative = str(
            path.relative_to(VAULT_PATH)
        )

        for line_number, line in enumerate(
            lines,
            start=1,
        ):
            content = clean_entry(line)

            if not content:
                continue

            entries.append(
                {
                    "path": relative,
                    "line": line_number,
                    "text": content,
                    "normalized": normalize(
                        content
                    ),
                }
            )

    return entries


def write_index(entries: list[dict]) -> None:
    INDEX_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = {
        "generated_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),
        "entry_count": len(entries),
        "entries": entries,
    }

    INDEX_FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def exact_duplicates(
    entries: list[dict],
) -> list[list[dict]]:

    groups = defaultdict(list)

    for entry in entries:
        key = entry["normalized"]

        if len(key) < 10:
            continue

        groups[key].append(entry)

    return [
        group
        for group in groups.values()
        if len(group) > 1
    ]


def near_duplicates(
    entries: list[dict],
    limit: int = 20,
) -> list[dict]:

    by_file = defaultdict(list)

    for entry in entries:
        by_file[entry["path"]].append(
            entry
        )

    matches = []

    for path, file_entries in by_file.items():

        # Schutz vor quadratischem Wachstum.
        file_entries = file_entries[:250]

        for index, first in enumerate(
            file_entries
        ):
            for second in file_entries[
                index + 1:
            ]:

                if (
                    first["normalized"]
                    == second["normalized"]
                ):
                    continue

                if (
                    len(first["normalized"]) < 20
                    or len(second["normalized"]) < 20
                ):
                    continue

                score = SequenceMatcher(
                    None,
                    first["normalized"],
                    second["normalized"],
                ).ratio()

                if score >= 0.90:
                    matches.append(
                        {
                            "path": path,
                            "first": first["text"],
                            "second": second["text"],
                            "score": round(
                                score,
                                3,
                            ),
                        }
                    )

                    if len(matches) >= limit:
                        return matches

    return matches


def analyze_inbox() -> list[dict]:
    target = (
        VAULT_PATH / inbox_path()
    ).resolve()

    if not target.exists():
        return []

    candidates = []

    try:
        lines = target.read_text(
            encoding="utf-8"
        ).splitlines()
    except (OSError, UnicodeError):
        return []

    for line_number, line in enumerate(
        lines,
        start=1,
    ):
        content = clean_entry(line)

        if not content:
            continue

        scope = resolve_scope_from_text(
            content
        )

        if not scope:
            continue

        candidates.append(
            {
                "line": line_number,
                "text": content,
                "scope": scope["key"],
                "target": scope.get(
                    "path"
                ),
            }
        )

    return candidates


def write_log(
    entries: list[dict],
    duplicates: list[list[dict]],
    near: list[dict],
    inbox: list[dict],
) -> Path:

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = (
        datetime.now()
        .astimezone()
    )

    filename = (
        "nightly-"
        + timestamp.strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
        + ".md"
    )

    log_path = LOG_DIR / filename

    lines = [
        "# Nightly Maintenance",
        "",
        f"Zeit: {timestamp.isoformat()}",
        "",
        "## Zusammenfassung",
        "",
        f"- Indexierte Einträge: {len(entries)}",
        f"- Exakte Duplikatgruppen: {len(duplicates)}",
        f"- Ähnliche Einträge: {len(near)}",
        f"- Inbox-Routing-Kandidaten: {len(inbox)}",
        "",
        "## Inbox-Routing-Kandidaten",
        "",
    ]

    if inbox:
        for item in inbox:
            lines.append(
                f'- `{item["scope"]}` → '
                f'{item["text"]}'
            )
    else:
        lines.append(
            "- Keine eindeutigen Kandidaten."
        )

    lines.extend(
        [
            "",
            "## Exakte Duplikate",
            "",
        ]
    )

    if duplicates:
        for group in duplicates:
            lines.append(
                f'- "{group[0]["text"]}"'
            )

            for item in group:
                lines.append(
                    f'  - {item["path"]}:'
                    f'{item["line"]}'
                )
    else:
        lines.append(
            "- Keine exakten Duplikate."
        )

    lines.extend(
        [
            "",
            "## Ähnliche Einträge",
            "",
        ]
    )

    if near:
        for item in near:
            lines.append(
                f'- Score {item["score"]}: '
                f'{item["first"]} '
                f'↔ {item["second"]}'
            )
    else:
        lines.append(
            "- Keine auffälligen ähnlichen Einträge."
        )

    log_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return log_path


def run() -> None:
    entries = build_index()

    write_index(entries)

    duplicates = exact_duplicates(
        entries
    )

    near = near_duplicates(
        entries
    )

    inbox = analyze_inbox()

    log_path = write_log(
        entries,
        duplicates,
        near,
        inbox,
    )

    print("Nightly Maintenance abgeschlossen")
    print(
        f"Indexierte Einträge: {len(entries)}"
    )
    print(
        f"Exakte Duplikatgruppen: "
        f"{len(duplicates)}"
    )
    print(
        f"Ähnliche Einträge: {len(near)}"
    )
    print(
        f"Inbox-Kandidaten: {len(inbox)}"
    )
    print(
        "Log: "
        + str(
            log_path.relative_to(
                VAULT_PATH
            )
        )
    )


if __name__ == "__main__":
    run()
