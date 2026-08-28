import sqlite3
import re
from pathlib import Path
from typing import Dict, Any, List


from config_loader import load_config


config = load_config()
DB_PATH = Path(config["paths"]["database"])


STOPWORDS = {
    "und", "oder", "der", "die", "das", "ein", "eine", "ist", "mit",
    "für", "von", "im", "in", "auf", "zu", "den", "dem", "des",
    "unter", "braucht", "nutzen", "lösung", "problem", "lesson",
    "the", "and", "or", "with", "for", "to", "of", "a", "an",
}


def normalize(text: str) -> str:
    if not text:
        return ""

    text = text.lower()
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9äöüß\s/_.]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokens(text: str) -> set:
    return {
        t for t in normalize(text).split()
        if len(t) >= 3 and t not in STOPWORDS
    }


def load_index_rows() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            path,
            title,
            topic,
            type,
            status,
            score,
            confidence,
            summary,
            tags,
            content_preview
        FROM memory_index
    """)

    rows = []

    for row in cursor.fetchall():
        rows.append({
            "id": row[0],
            "path": row[1],
            "title": row[2],
            "topic": row[3],
            "type": row[4],
            "status": row[5],
            "score": row[6],
            "confidence": row[7],
            "summary": row[8],
            "tags": row[9],
            "content_preview": row[10] or "",
        })

    conn.close()
    return rows


def memory_search_text(memory: Dict[str, Any]) -> str:
    return " ".join([
        str(memory.get("id", "")),
        str(memory.get("title", "")),
        str(memory.get("topic", "")),
        str(memory.get("type", "")),
        str(memory.get("summary", "")),
        str(memory.get("tags", "")),
        str(memory.get("content_preview", "")),
    ])


def jaccard_similarity(a: str, b: str) -> float:
    ta = tokens(a)
    tb = tokens(b)

    if not ta or not tb:
        return 0.0

    return len(ta.intersection(tb)) / len(ta.union(tb))


def containment_similarity(a: str, b: str) -> float:
    """
    Besser für kurze neue Proposals gegen lange Sammeldateien.
    Misst: Wie viel vom neuen Proposal kommt im bestehenden Memory-Text vor?
    """
    ta = tokens(a)
    tb = tokens(b)

    if not ta or not tb:
        return 0.0

    return len(ta.intersection(tb)) / len(ta)


def combined_similarity(a: str, b: str) -> float:
    """
    Kombiniert Jaccard und Containment.
    Containment wird stärker gewichtet, weil Sammeldateien länger sind.
    """
    j = jaccard_similarity(a, b)
    c = containment_similarity(a, b)

    return max(j, c * 0.90)


def find_similar_memories(content: str, topic_hint: str = "", limit: int = 5) -> List[Dict[str, Any]]:
    query_text = f"{topic_hint}\n{content}"
    rows = load_index_rows()

    results = []

    for memory in rows:
        memory_path = str(memory.get("path", ""))

        # Inbox-/Review-Dateien sind Audit-Logs, keine eigentlichen Memories.
        # Sie dürfen nicht als Duplicate-Match verwendet werden.
        if memory_path.startswith("90_Inbox/"):
            continue

        if memory.get("type") in {"review_queue"}:
            continue

        if memory.get("status") in {"archived", "superseded"}:
            continue

        sim = combined_similarity(query_text, memory_search_text(memory))

        if sim > 0:
            memory["_similarity"] = sim
            results.append(memory)

    results.sort(key=lambda x: x["_similarity"], reverse=True)
    return results[:limit]


def classify_similarity(similar: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Für Version 0.1:
    >= 0.75: wahrscheinlich Duplikat
    >= 0.45: mögliche Ergänzung / Review
    < 0.45: neu genug
    """
    if not similar:
        return {
            "duplicate_risk": "none",
            "top_similarity": 0.0,
            "top_match": None,
            "requires_review": False,
        }

    top = similar[0]
    sim = float(top.get("_similarity", 0.0))

    if sim >= 0.75:
        return {
            "duplicate_risk": "high",
            "top_similarity": sim,
            "top_match": top,
            "requires_review": True,
        }

    if sim >= 0.45:
        return {
            "duplicate_risk": "medium",
            "top_similarity": sim,
            "top_match": top,
            "requires_review": True,
        }

    return {
        "duplicate_risk": "low",
        "top_similarity": sim,
        "top_match": top,
        "requires_review": False,
    }


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print('Nutzung: python3 src/similarity.py "Text"')
        sys.exit(1)

    text = " ".join(sys.argv[1:])
    results = find_similar_memories(text)

    print(json.dumps(results, indent=2, ensure_ascii=False))
    print(json.dumps(classify_similarity(results), indent=2, ensure_ascii=False))
