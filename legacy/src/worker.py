import json
import time
import shutil
from pathlib import Path

from indexer import scan_and_index_vault
from scorer import evaluate_memory_proposal
from review import append_review_entry
from writer import can_write_automatically, append_memory_entry
from config_loader import load_config


config = load_config()


VAULT_PATH = Path(config["paths"]["vault_base"])
QUEUE_DIR = Path(config["paths"]["queue_dir"])
PROCESSED_DIR = Path(config["paths"]["processed_dir"])
FAILED_DIR = Path(config["paths"]["failed_dir"])
INTERVAL = int(config["settings"]["scan_interval_seconds"])


def ensure_directories():
    for d in [QUEUE_DIR, PROCESSED_DIR, FAILED_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def move_file(src: Path, dst_dir: Path):
    dst_dir.mkdir(parents=True, exist_ok=True)
    target = dst_dir / src.name

    if target.exists():
        target = dst_dir / f"{int(time.time())}_{src.name}"

    shutil.move(str(src), str(target))


def process_memory_proposal(file_path: Path, task: dict) -> bool:
    evaluation = evaluate_memory_proposal(task)

    print(f"Bewertung für {file_path.name}: {evaluation}")

    if evaluation["final_action"] == "DISCARD":
        print(f"Verworfen: {file_path.name}")
        return True

    if can_write_automatically(evaluation):
        written_path = append_memory_entry(task, evaluation)
        print(f"Automatisch gespeichert: {written_path}")
        return True

    append_review_entry(task, evaluation)
    print(f"Review-Eintrag erstellt für: {file_path.name}")
    return True


def process_legacy_task(file_path: Path, task: dict) -> bool:
    evaluation = {
        "final_action": "REVIEW",
        "score": 4,
        "status": "active",
        "target": "90_Inbox/ReviewQueue.md",
        "requires_review": True,
        "risk_flags": ["legacy_direct_write"],
        "reason": "Legacy task tried direct file write. Direct writes are disabled; review required."
    }

    proposal = {
        "id": task.get("id", file_path.stem),
        "source_model": task.get("source_model", "legacy-task"),
        "topic_hint": task.get("path", ""),
        "content": json.dumps(task, ensure_ascii=False, indent=2),
    }

    append_review_entry(proposal, evaluation)
    return True


def process_queue_file(file_path: Path) -> bool:
    print(f"Verarbeite Queue-Datei: {file_path.name}")

    try:
        with file_path.open("r", encoding="utf-8") as f:
            task = json.load(f)

        task_type = task.get("type", "")

        if task_type == "memory_proposal":
            success = process_memory_proposal(file_path, task)
        else:
            success = process_legacy_task(file_path, task)

        if success:
            move_file(file_path, PROCESSED_DIR)
            return True

        move_file(file_path, FAILED_DIR)
        return False

    except Exception as e:
        print(f"Fehler bei Datei {file_path.name}: {e}")
        try:
            move_file(file_path, FAILED_DIR)
        except Exception as move_err:
            print(f"Konnte defekte Datei nicht verschieben: {move_err}")
        return False


def main_loop():
    ensure_directories()

    print(f"Background-Worker aktiv. Überwache Ordner: {QUEUE_DIR}")
    print(f"Scan-Intervall: {INTERVAL} Sekunden.")

    while True:
        files = sorted([p for p in QUEUE_DIR.glob("*.json") if p.is_file()])

        needs_reindex = False

        for file_path in files:
            success = process_queue_file(file_path)
            if success:
                needs_reindex = True

        if needs_reindex:
            print("Änderungen erkannt. Starte automatische Re-Indizierung...")
            scan_and_index_vault()

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main_loop()
