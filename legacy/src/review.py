from pathlib import Path
from datetime import datetime
from typing import Dict, Any


from config_loader import load_config


config = load_config()
VAULT_PATH = Path(config["paths"]["vault_base"])
REVIEW_QUEUE_PATH = VAULT_PATH / "90_Inbox" / "ReviewQueue.md"


def ensure_review_queue():
    REVIEW_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not REVIEW_QUEUE_PATH.exists() or REVIEW_QUEUE_PATH.read_text(encoding="utf-8").strip() == "":
        REVIEW_QUEUE_PATH.write_text("""---
id: inbox.review-queue
title: Review Queue
topic: Inbox/Review
type: review_queue
status: active
score: 4
confidence: high
summary: Manuelle Review-Liste für riskante oder unklare Memory-Vorschläge.
tags:
  - inbox
  - review
  - memory
---

# Review Queue

""", encoding="utf-8")


def append_review_entry(proposal: Dict[str, Any], evaluation: Dict[str, Any]) -> None:
    ensure_review_queue()

    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    entry = f"""
---

## {now} - {proposal.get("id", "unknown-proposal")}

### Status

pending

### Quelle

{proposal.get("source_model", "unknown")}

### Topic Hint

{proposal.get("topic_hint", "")}

### Vorschlag

{proposal.get("content", "")}

### Bewertung

- Final Action: {evaluation.get("final_action")}
- Score: {evaluation.get("score")}
- Status: {evaluation.get("status")}
- Target: {evaluation.get("target")}
- Requires Review: {evaluation.get("requires_review")}
- Risk Flags: {", ".join(evaluation.get("risk_flags", [])) if evaluation.get("risk_flags") else "none"}
- Duplicate Risk: {evaluation.get("duplicate_risk", "unknown")}
- Top Similarity: {evaluation.get("top_similarity", 0)}
- Top Match ID: {evaluation.get("top_match_id", "none")}
- Top Match Path: {evaluation.get("top_match_path", "none")}

### Grund

{evaluation.get("reason", "")}

### Entscheidung

- [ ] Akzeptieren
- [ ] Ablehnen
- [ ] Als normale Lesson speichern
- [ ] Als Global Lesson speichern
- [ ] Als Global Rule vorschlagen
- [ ] Als superseded/archived markieren
"""

    with REVIEW_QUEUE_PATH.open("a", encoding="utf-8") as f:
        f.write(entry)
