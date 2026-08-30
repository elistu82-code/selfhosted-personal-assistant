import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]

VAULT_PATH = Path(
    os.environ.get(
        "VAULT_PATH",
        PROJECT_ROOT / "examples" / "demo-vault",
    )
).resolve()

ROUTING_CONFIG = Path(
    os.environ.get(
        "ROUTING_CONFIG",
        PROJECT_ROOT / "config" / "routing.example.yaml",
    )
).resolve()


def validate_config() -> None:
    if not VAULT_PATH.exists():
        raise RuntimeError(
            f"VAULT_PATH existiert nicht: {VAULT_PATH}"
        )

    if not ROUTING_CONFIG.exists():
        raise RuntimeError(
            f"Routing-Konfiguration existiert nicht: {ROUTING_CONFIG}"
        )
