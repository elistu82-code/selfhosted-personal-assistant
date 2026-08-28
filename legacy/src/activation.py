import re
from typing import Dict, Any, List, Set


LONG_TERM_TERMS = {
    "später",
    "langfristig",
    "irgendwann",
    "zukunft",
    "zukünftig",
    "future",
    "long-term",
    "roadmap",
    "vision",
    "architektur später",
    "homelab später",
}

EXPLICIT_LOCAL_AI_TERMS = {
    "lokale ki",
    "local ai",
    "offline ki",
    "offline-ki",
    "ollama",
    "llama",
    "llama.cpp",
    "local model",
    "lokales modell",
    "homelab ki",
    "eigener ki server",
    "api kosten",
    "api-kosten",
}


def normalize_text(text: str) -> str:
    """Normalisiert Text für einfache Keyword-Vergleiche."""
    if not text:
        return ""

    text = text.lower()
    text = text.replace("-", " ")
    text = re.sub(r"[^a-zA-Z0-9äöüÄÖÜß\s/_.]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> Set[str]:
    """Zerlegt Text in einfache Tokens."""
    text = normalize_text(text)
    return {token for token in text.split(" ") if len(token) >= 3}


def split_list_field(value: Any) -> List[str]:
    """Verarbeitet tags/keywords aus SQLite oder Metadaten."""
    if value is None:
        return []

    if isinstance(value, list):
        return [str(x).strip().lower() for x in value if str(x).strip()]

    if isinstance(value, str):
        return [x.strip().lower() for x in value.split(",") if x.strip()]

    return []


def query_mentions_any(query: str, terms: Set[str]) -> bool:
    """Prüft, ob die Query einen expliziten Trigger enthält."""
    q = normalize_text(query)

    for term in terms:
        if normalize_text(term) in q:
            return True

    return False


def asks_for_long_term_planning(query: str) -> bool:
    """Erkennt langfristige Planung."""
    return query_mentions_any(query, LONG_TERM_TERMS)


def build_memory_text(memory: Dict[str, Any]) -> str:
    """Baut aus Indexdaten einen Suchtext."""
    parts = [
        str(memory.get("id", "")),
        str(memory.get("title", "")),
        str(memory.get("topic", "")),
        str(memory.get("type", "")),
        str(memory.get("summary", "")),
        str(memory.get("tags", "")),
    ]

    return " ".join(parts)


def is_topic_relevant(memory: Dict[str, Any], query: str) -> bool:
    """
    Einfache Relevanzprüfung.
    Für Version 0.1 reicht Token-Overlap.
    Später kann hier Embedding-Suche ergänzt werden.
    """
    query_tokens = tokenize(query)
    memory_tokens = tokenize(build_memory_text(memory))

    if not query_tokens or not memory_tokens:
        return False

    overlap = query_tokens.intersection(memory_tokens)

    if overlap:
        return True

    # Zusatz: Topic-Teile prüfen, z.B. Global/Codex -> codex
    topic = normalize_text(str(memory.get("topic", ""))).replace("/", " ")
    title = normalize_text(str(memory.get("title", "")))

    q = normalize_text(query)

    for part in topic.split(" "):
        if len(part) >= 3 and part in q:
            return True

    for part in title.split(" "):
        if len(part) >= 3 and part in q:
            return True

    return False


def is_explicitly_about_memory(memory: Dict[str, Any], query: str) -> bool:
    """
    Prüft, ob eine dormant/future Memory explizit gemeint ist.
    Wichtig für future/dormant.
    """
    q = normalize_text(query)

    title = normalize_text(str(memory.get("title", "")))
    topic = normalize_text(str(memory.get("topic", ""))).replace("/", " ")
    tags = split_list_field(memory.get("tags", ""))

    for part in title.split(" "):
        if len(part) >= 4 and part in q:
            return True

    for part in topic.split(" "):
        if len(part) >= 4 and part in q:
            return True

    for tag in tags:
        tag_norm = normalize_text(tag)
        if len(tag_norm) >= 3 and tag_norm in q:
            return True

    # Spezialfall lokale KI
    if "local" in topic or "lokal" in topic or "ki" in topic:
        if query_mentions_any(query, EXPLICIT_LOCAL_AI_TERMS):
            return True

    return False


def should_load_memory(memory: Dict[str, Any], query: str) -> bool:
    """
    Zentrale Aktivierungslogik.

    active:
        Nutzbar, wenn relevant.

    future:
        Nur wenn explizit danach gefragt wird oder langfristige Planung Thema ist.

    dormant:
        Nur wenn die Frage das Thema direkt betrifft.

    blocked:
        Nur wenn explizit danach gefragt wird.

    archived/superseded:
        Nicht als aktuelle Antwort laden.
    """
    status = str(memory.get("status", "active")).lower().strip()

    if status == "active":
        return is_topic_relevant(memory, query)

    if status == "future":
        return is_explicitly_about_memory(memory, query) or asks_for_long_term_planning(query)

    if status == "dormant":
        return is_explicitly_about_memory(memory, query)

    if status == "blocked":
        return is_explicitly_about_memory(memory, query)

    if status in {"archived", "superseded"}:
        return False

    return False


def activation_reason(memory: Dict[str, Any], query: str) -> str:
    """Erklärt kurz, warum eine Memory geladen oder blockiert wurde."""
    status = str(memory.get("status", "active")).lower().strip()
    allowed = should_load_memory(memory, query)

    if allowed:
        return f"loaded: status={status}, relevant_or_triggered=true"

    return f"blocked: status={status}, not relevant or activation condition missing"


def relevance_score(memory: Dict[str, Any], query: str) -> float:
    """
    Simple Ranking-Funktion für Version 0.1.
    Höher = relevanter.
    """
    query_tokens = tokenize(query)
    memory_tokens = tokenize(build_memory_text(memory))

    if not query_tokens or not memory_tokens:
        return 0.0

    overlap = query_tokens.intersection(memory_tokens)
    base = len(overlap) / max(len(query_tokens), 1)

    status = str(memory.get("status", "active")).lower().strip()
    memory_score = int(memory.get("score") or 1)

    status_bonus = {
        "active": 0.20,
        "future": 0.05,
        "dormant": 0.03,
        "blocked": 0.0,
        "archived": -1.0,
        "superseded": -1.0,
    }.get(status, 0.0)

    score_bonus = min(memory_score, 5) * 0.02

    return base + status_bonus + score_bonus
