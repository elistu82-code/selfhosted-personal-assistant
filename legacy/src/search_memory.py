import sqlite3
import sys
from pathlib import Path
from typing import Dict, Any, List

from activation import should_load_memory, relevance_score, activation_reason
from config_loader import load_config


config = load_config()

DB_PATH = Path(config["paths"]["database"])
VAULT_PATH = Path(config["paths"]["vault_base"])


def row_to_dict(row) -> Dict[str, Any]:
    return {
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
        "content_hash": row[10],
        "updated": row[11],
    }


def load_index_rows() -> List[Dict[str, Any]]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Index-Datenbank nicht gefunden: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, path, title, topic, type, status, score, confidence, summary, tags, content_hash, updated
        FROM memory_index
    """)

    rows = [row_to_dict(row) for row in cursor.fetchall()]

    conn.close()
    return rows


def read_memory_content(rel_path: str, max_chars: int = 4000) -> str:
    full_path = VAULT_PATH / rel_path

    if not full_path.exists():
        return ""

    text = full_path.read_text(encoding="utf-8")

    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[TRUNCATED]"

    return text


def search_memory(query: str, limit: int = 5, include_content: bool = True) -> List[Dict[str, Any]]:
    """
    Sucht relevante Memories.
    Wichtig: Lädt zuerst nur den SQLite-Index.
    Erst danach werden die Top-Dateien gelesen.
    """
    rows = load_index_rows()

    candidates = []

    for memory in rows:
        if not should_load_memory(memory, query):
            continue

        score = relevance_score(memory, query)

        if score <= 0:
            continue

        memory["_rank_score"] = score
        memory["_activation_reason"] = activation_reason(memory, query)

        candidates.append(memory)

    candidates.sort(key=lambda x: x["_rank_score"], reverse=True)

    top = candidates[:limit]

    if include_content:
        for memory in top:
            memory["content"] = read_memory_content(memory["path"])

    return top


def print_results(results: List[Dict[str, Any]]):
    if not results:
        print("Keine aktivierbaren Memories gefunden.")
        return

    for i, memory in enumerate(results, start=1):
        print("=" * 80)
        print(f"{i}. {memory.get('title')} [{memory.get('id')}]")
        print(f"Pfad: {memory.get('path')}")
        print(f"Topic: {memory.get('topic')}")
        print(f"Status: {memory.get('status')}")
        print(f"Score: {memory.get('score')}")
        print(f"Rank: {memory.get('_rank_score'):.3f}")
        print(f"Activation: {memory.get('_activation_reason')}")
        print("-" * 80)

        content = memory.get("content", "")
        if content:
            print(content[:1500])
            if len(content) > 1500:
                print("\n[CONTENT gekürzt]")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Nutzung:")
        print('  python3 src/search_memory.py "deine Suchfrage"')
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    results = search_memory(query=query, limit=5, include_content=True)
    print_results(results)
