import json
from pathlib import Path

CLAUDECAST_DIR = Path.home() / ".claudecast"

DEFAULT_CONFIG = {
    "active_project": None,
    "default_voice": "en-US-AriaNeural",
    "default_model": "claude-sonnet-4-6",
    "output_dir": str(Path.home() / "claudecast-output"),
}

VALID_CONFIG_KEYS = set(DEFAULT_CONFIG.keys())


def claudecast_dir() -> Path:
    return CLAUDECAST_DIR


def is_initialized() -> bool:
    return (CLAUDECAST_DIR / "config.json").exists()


def load_config() -> dict:
    path = CLAUDECAST_DIR / "config.json"
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    return {**DEFAULT_CONFIG, **json.loads(path.read_text())}


def save_config(data: dict):
    path = CLAUDECAST_DIR / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def list_projects() -> list[str]:
    projects_dir = CLAUDECAST_DIR / "projects"
    if not projects_dir.exists():
        return []
    return sorted(p.name for p in projects_dir.iterdir() if p.is_dir())


def project_dir(name: str) -> Path:
    return CLAUDECAST_DIR / "projects" / name


def project_exists(name: str) -> bool:
    return project_dir(name).exists()


def load_project_config(name: str) -> dict:
    path = project_dir(name) / "config.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_project_config(name: str, data: dict):
    path = project_dir(name) / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def preferences_path(project: str | None = None) -> Path:
    if project:
        return project_dir(project) / "preferences.md"
    return CLAUDECAST_DIR / "style" / "preferences.md"


def resolve_config(project: str | None = None) -> dict:
    """Merge global config with project overrides."""
    cfg = load_config()
    if project:
        cfg.update(load_project_config(project))
    return cfg
