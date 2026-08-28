import sqlite3
import hashlib
from pathlib import Path

from config_loader import load_config

REQUIRED_FIELDS = ["id", "title", "topic", "type", "status", "score"]

ALLOWED_STATUS = {
    "active",
    "future",
    "dormant",
    "blocked",
    "archived",
    "superseded"
}


config = load_config()

DB_PATH = Path(config["paths"]["database"])
VAULT_PATH = Path(config["paths"]["vault_base"])


def init_database():
    """Erstellt oder migriert die SQLite-Datenbank."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_index (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            title TEXT,
            topic TEXT,
            type TEXT,
            status TEXT,
            score INTEGER,
            confidence TEXT,
            summary TEXT,
            tags TEXT,
            content_hash TEXT,
            updated TEXT,
            content_preview TEXT
        )
    """)

    cursor.execute("PRAGMA table_info(memory_index)")
    columns = {row[1] for row in cursor.fetchall()}

    migrations = {
        "confidence": "ALTER TABLE memory_index ADD COLUMN confidence TEXT",
        "summary": "ALTER TABLE memory_index ADD COLUMN summary TEXT",
        "tags": "ALTER TABLE memory_index ADD COLUMN tags TEXT",
        "content_preview": "ALTER TABLE memory_index ADD COLUMN content_preview TEXT",
    }

    for column, sql in migrations.items():
        if column not in columns:
            cursor.execute(sql)
            print(f"Migration: Spalte hinzugefügt: {column}")

    conn.commit()
    conn.close()


def parse_markdown_file(file_path: Path):
    """Liest eine Markdown-Datei und trennt YAML-Frontmatter vom Inhalt."""
    text = file_path.read_text(encoding="utf-8")

    if not text.startswith("---\n"):
        return None, None, text

    parts = text.split("---", 2)

    if len(parts) < 3:
        return None, None, text

    frontmatter_text = parts[1].strip()
    content_text = parts[2].lstrip()

    try:
        metadata = yaml.safe_load(frontmatter_text) or {}
        return metadata, content_text, text
    except Exception as e:
        print(f"YAML-Fehler in {file_path}: {e}")
        return None, None, text


def validate_metadata(metadata, rel_path):
    if not metadata:
        print(f"Übersprungen ohne Frontmatter: {rel_path}")
        return False

    missing = [field for field in REQUIRED_FIELDS if field not in metadata]
    if missing:
        print(f"Übersprungen wegen fehlender Felder {missing}: {rel_path}")
        return False

    status = metadata.get("status")
    if status not in ALLOWED_STATUS:
        print(f"Übersprungen wegen ungültigem status '{status}': {rel_path}")
        return False

    try:
        int(metadata.get("score"))
    except Exception:
        print(f"Übersprungen wegen ungültigem score: {rel_path}")
        return False

    return True


def should_skip_path(path: Path):
    parts = set(path.parts)

    if ".git" in parts:
        return True

    if "90_Inbox" in parts and any(x in parts for x in ["queue", "processed", "failed"]):
        return True

    return False


def normalize_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]

    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]

    return []


def scan_and_index_vault():
    """Scannt den Vault und indiziert alle gültigen Markdown-Dateien."""
    print(f"Scanne Vault unter: {VAULT_PATH}")
    init_database()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    found_ids = set()
    indexed_count = 0

    for file_path in VAULT_PATH.rglob("*.md"):
        if should_skip_path(file_path):
            continue

        rel_path = file_path.relative_to(VAULT_PATH)

        metadata, content, full_text = parse_markdown_file(file_path)

        if not validate_metadata(metadata, rel_path):
            continue

        memory_id = metadata["id"]
        found_ids.add(memory_id)

        tags = normalize_list(metadata.get("tags")) + normalize_list(metadata.get("keywords"))
        tags = sorted(set(tags))

        content_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
        content_preview = content[:8000]

        cursor.execute("""
            INSERT OR REPLACE INTO memory_index
            (id, path, title, topic, type, status, score, confidence, summary, tags, content_hash, updated, content_preview)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory_id,
            str(rel_path),
            metadata.get("title"),
            metadata.get("topic"),
            metadata.get("type"),
            metadata.get("status"),
            int(metadata.get("score")),
            metadata.get("confidence", ""),
            metadata.get("summary", ""),
            ",".join(tags),
            content_hash,
            str(metadata.get("updated", "")),
            content_preview
        ))

        indexed_count += 1
        print(f"✓ Indiziert: {rel_path} [{memory_id}]")

    cursor.execute("SELECT id FROM memory_index")
    existing_ids = {row[0] for row in cursor.fetchall()}

    stale_ids = existing_ids - found_ids

    for stale_id in stale_ids:
        cursor.execute("DELETE FROM memory_index WHERE id = ?", (stale_id,))
        print(f"− Entfernt aus Index, nicht mehr im Vault: {stale_id}")

    conn.commit()
    conn.close()

    print(f"Fertig. {indexed_count} Dateien im Index. {len(stale_ids)} veraltete Einträge entfernt.")


if __name__ == "__main__":
    scan_and_index_vault()
