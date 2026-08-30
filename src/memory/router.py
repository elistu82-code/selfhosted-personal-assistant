import re
from typing import Any

import yaml

from src.config import ROUTING_CONFIG


def normalize(text: str) -> str:
    text = text.lower().strip()

    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+", " ", text)
    return text


def load_routing() -> dict[str, Any]:
    with ROUTING_CONFIG.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _scope(
    key: str,
    config: dict[str, Any],
    parent: str | None = None,
) -> dict[str, Any]:
    result = dict(config)
    result["key"] = key
    result["parent"] = parent
    return result


def all_scopes() -> list[dict[str, Any]]:
    config = load_routing()
    domains = config.get("domains", {})

    scopes: list[dict[str, Any]] = []

    # Unterthemen zuerst.
    # "Immich" soll also Immich treffen und nicht nur Homelab.
    for domain_key, domain in domains.items():
        for topic_key, topic in domain.get("topics", {}).items():
            scopes.append(
                _scope(topic_key, topic, parent=domain_key)
            )

    for domain_key, domain in domains.items():
        scopes.append(
            _scope(domain_key, domain)
        )

    return scopes


def aliases_for(scope: dict[str, Any]) -> list[str]:
    aliases = [scope["key"]]
    aliases.extend(scope.get("aliases", []))
    return aliases


def resolve_topic(name: str) -> dict[str, Any] | None:
    wanted = normalize(name)

    for scope in all_scopes():
        for alias in aliases_for(scope):
            if normalize(alias) == wanted:
                return scope

    return None


def resolve_scope_from_text(text: str) -> dict[str, Any] | None:
    normalized_text = normalize(text)

    candidates: list[tuple[int, dict[str, Any]]] = []

    for scope in all_scopes():
        for alias in aliases_for(scope):
            alias_normalized = normalize(alias)

            pattern = (
                r"(?<![a-z0-9])"
                + re.escape(alias_normalized)
                + r"(?![a-z0-9])"
            )

            if re.search(pattern, normalized_text):
                candidates.append(
                    (len(alias_normalized), scope)
                )

    if not candidates:
        return None

    # Spezifischsten / längsten Treffer bevorzugen.
    candidates.sort(
        key=lambda entry: entry[0],
        reverse=True,
    )

    return candidates[0][1]


def get_domain(name: str) -> dict[str, Any] | None:
    config = load_routing()
    domain = config.get("domains", {}).get(name)

    if not domain:
        return None

    return _scope(name, domain)


def inbox_path() -> str:
    config = load_routing()

    return config.get(
        "settings",
        {},
    ).get(
        "default_fallback",
        "00_Inbox/Inbox.md",
    )
