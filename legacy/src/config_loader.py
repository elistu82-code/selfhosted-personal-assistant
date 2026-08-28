from pathlib import Path
import yaml


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_config():
    config_path = get_project_root() / "config.yaml"

    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
