from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import re


from config_loader import load_config


config = load_config()
VAULT_PATH = Path(config["paths"]["vault_base"])


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-") or "memory"


def ensure_file_with_frontmatter(rel_path: str, title: str, topic: str, type_: str = "lessons", score: int = 3):
    """
    Erstellt eine Zieldatei, falls sie noch nicht existiert.
    Bestehende Dateien werden nicht überschrieben.
    """
    full_path = VAULT_PATH / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    if full_path.exists() and full_path.read_text(encoding="utf-8").strip():
        return

    memory_id = slugify(rel_path.replace("/", ".").replace(".md", ""))

    content = f"""---
id: {memory_id}
title: {title}
topic: {topic}
type: {type_}
status: active
score: {score}
confidence: medium
summary: Automatisch gepflegte Memory-Datei für {topic}.
tags:
  - memory
  - auto
---

# {title}

"""

    full_path.write_text(content, encoding="utf-8")


def append_memory_entry(proposal: Dict[str, Any], evaluation: Dict[str, Any]) -> str:
    """
    Hängt eine neue Memory append-only an die Zieldatei an.
    Kein Replace, kein Löschen, kein blindes Merge.
    """
    target = evaluation.get("target")

    if not target or target == "DISCARD" or target.endswith("ReviewQueue.md"):
        raise ValueError(f"Ungültiges Writer-Ziel: {target}")

    topic_hint = proposal.get("topic_hint", "Unknown")
    content = proposal.get("content", "").strip()
    proposal_id = proposal.get("id", "unknown")
    source_model = proposal.get("source_model", "unknown")
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    ensure_file_with_frontmatter(
        rel_path=target,
        title=Path(target).stem,
        topic=topic_hint,
        type_="lessons",
        score=int(evaluation.get("score", 3))
    )

    full_path = VAULT_PATH / target

    entry_title = infer_entry_title(topic_hint, content)

    entry = f"""

---

## {entry_title}

### Metadata

- Proposal ID: {proposal_id}
- Source Model: {source_model}
- Created: {now}
- Score: {evaluation.get("score")}
- Status: {evaluation.get("status")}
- Risk Flags: {", ".join(evaluation.get("risk_flags", [])) if evaluation.get("risk_flags") else "none"}
- Evaluation: {evaluation.get("reason", "")}

### Inhalt

{content}

### Lesson

Diese Erkenntnis wurde automatisch als sichere, wiederverwendbare Memory gespeichert.
"""

    with full_path.open("a", encoding="utf-8") as f:
        f.write(entry)

    return str(full_path)


def infer_entry_title(topic_hint: str, content: str) -> str:
    """
    Erzeugt eine kurze Überschrift.
    """
    text = content.strip().splitlines()[0] if content.strip() else topic_hint
    text = text.replace("#", "").strip()

    if len(text) > 90:
        text = text[:87].rstrip() + "..."

    if not text:
        text = topic_hint or "Memory Entry"

    return text


def can_write_automatically(evaluation: Dict[str, Any]) -> bool:
    """
    Harte Sicherheitsgrenze.
    Nur wirklich sichere ADD/MERGE-Fälle dürfen automatisch geschrieben werden.
    """
    if evaluation.get("requires_review"):
        return False

    if evaluation.get("final_action") in {"BLOCKED", "REVIEW", "DISCARD"}:
        return False

    if evaluation.get("final_action") not in {"ADD", "MERGE"}:
        return False

    score = int(evaluation.get("score", 1))

    if score not in {2, 3}:
        return False

    risk_flags = set(evaluation.get("risk_flags", []))

    blocked_flags = {
        "security",
        "cost",
        "architecture",
        "global_rule",
        "arr_stack",
        "legacy_direct_write",
    }

    if risk_flags.intersection(blocked_flags):
        return False

    target = evaluation.get("target", "")

    if not target or target == "DISCARD":
        return False

    if target.startswith("00_Global/"):
        return False

    if target.endswith("ReviewQueue.md"):
        return False

    return True
