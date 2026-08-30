import re
from difflib import SequenceMatcher
from pathlib import Path

from src.config import VAULT_PATH
from src.memory.router import (
    aliases_for,
    normalize,
    resolve_topic,
)


STOPWORDS = {
    "was", "habe", "hab", "hatte", "ich",
    "zu", "ueber", "bei", "unter", "von",
    "mir", "bitte", "mal",
    "weiss", "wissen",
    "steht", "gespeichert", "notiert",
    "suche", "suchen", "finde", "finden",
    "zeig", "zeige",
    "search", "memory",
}


def _safe_path(relative_path: str) -> Path:
    target = (VAULT_PATH / relative_path).resolve()

    if VAULT_PATH not in target.parents and target != VAULT_PATH:
        raise ValueError("Ungültiger Vault-Pfad")

    return target


def _query_terms(
    query: str | None,
    scope_name: str,
) -> list[str]:

    if not query:
        return []

    scope = resolve_topic(scope_name)

    alias_words = set()

    if scope:
        for alias in aliases_for(scope):
            alias_words.update(
                normalize(alias).split()
            )

    words = re.findall(
        r"[a-z0-9_-]+",
        normalize(query),
    )

    return [
        word
        for word in words
        if (
            len(word) >= 2
            and word not in STOPWORDS
            and word not in alias_words
        )
    ]


def _markdown_files(target: Path) -> list[Path]:
    if target.is_file():
        if target.suffix.lower() == ".md":
            return [target]
        return []

    if not target.is_dir():
        return []

    return list(target.rglob("*.md"))


def search_memory(
    scope_name: str,
    query: str | None = None,
    limit: int = 8,
) -> list[dict]:

    scope = resolve_topic(scope_name)

    if scope is None:
        return []

    relative_path = scope.get("path")

    if not relative_path:
        return []

    target = _safe_path(relative_path)

    if not target.exists():
        return []

    terms = _query_terms(
        query,
        scope_name,
    )

    results = []

    for file in _markdown_files(target):

        try:
            lines = file.read_text(
                encoding="utf-8",
            ).splitlines()
        except (OSError, UnicodeError):
            continue

        try:
            mtime = file.stat().st_mtime
        except OSError:
            mtime = 0

        for line_number, line in enumerate(
            lines,
            start=1,
        ):
            text = line.strip()

            if not text:
                continue

            if text.startswith("#"):
                continue

            normalized = normalize(text)

            if terms:
                score = 0.0

                for term in terms:
                    if term in normalized:
                        score += 2.0
                        continue

                    words = normalized.split()

                    best = max(
                        (
                            SequenceMatcher(
                                None,
                                term,
                                word,
                            ).ratio()
                            for word in words
                        ),
                        default=0.0,
                    )

                    if best >= 0.78:
                        score += best

                if score == 0:
                    continue
            else:
                score = 1.0

            results.append(
                {
                    "path": str(
                        file.relative_to(
                            VAULT_PATH
                        )
                    ),
                    "line": line_number,
                    "text": text,
                    "score": score,
                    "mtime": mtime,
                }
            )

    if terms:
        results.sort(
            key=lambda item: (
                item["score"],
                item["mtime"],
                item["line"],
            ),
            reverse=True,
        )
    else:
        results.sort(
            key=lambda item: (
                item["mtime"],
                item["line"],
            ),
            reverse=True,
        )

    return results[:limit]
