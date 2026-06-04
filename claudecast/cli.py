import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import (
    CLAUDECAST_DIR,
    DEFAULT_CONFIG,
    VALID_CONFIG_KEYS,
    claudecast_dir,
    is_initialized,
    list_projects,
    load_config,
    load_project_config,
    preferences_path,
    project_dir,
    project_exists,
    save_config,
    save_project_config,
    template_dir,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_init():
    if not is_initialized():
        _cmd_init(quiet=True)


def _print_config(cfg: dict, title: str = "config"):
    print(f"\n{title}")
    print("-" * len(title))
    for k, v in cfg.items():
        print(f"  {k} = {v}")
    print()


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def _cmd_init(quiet: bool = False):
    base = claudecast_dir()
    created = []

    dirs = [
        base,
        base / "style",
        base / "templates" / "default" / "examples",
        base / "projects",
    ]
    for d in dirs:
        if not d.exists():
            d.mkdir(parents=True)
            created.append(str(d))

    config_path = base / "config.json"
    if not config_path.exists():
        config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
        created.append(str(config_path))

    prefs = base / "style" / "preferences.md"
    if not prefs.exists():
        prefs.write_text(
            "# Global Style Preferences\n\n"
            "Instructions here are prepended to every Claude call.\n"
            "Add preferences using: claudecast train \"your instruction\"\n\n"
            "<!-- preferences below this line -->\n"
        )
        created.append(str(prefs))

    layouts = base / "templates" / "default" / "LAYOUTS.md"
    if not layouts.exists():
        layouts.write_text(
            "# Default Template Layouts\n\n"
            "Populate this by running: claudecast ingest template your_deck.pptx\n"
        )
        created.append(str(layouts))

    if quiet:
        return

    if created:
        for path in created:
            print(f"  created  {path}")
        print(f"\nclaudecast initialized at {base}")
    else:
        print(f"already initialized at {base}")
        print("run `claudecast config show` to see current settings.")

    print("run `claudecast install-skill` to register the claude code skill.")


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

def _cmd_config_show():
    _check_init()
    cfg = load_config()
    _print_config(cfg, "global config")


def _cmd_config_set(key: str, value: str):
    _check_init()
    if key not in VALID_CONFIG_KEYS:
        print(f"unknown key: {key}")
        print(f"valid keys: {', '.join(sorted(VALID_CONFIG_KEYS))}")
        sys.exit(1)
    cfg = load_config()
    # coerce numeric fields
    if key in ("default_slides",):
        value = int(value)
    cfg[key] = value
    save_config(cfg)
    print(f"set {key} = {value}")


# ---------------------------------------------------------------------------
# project
# ---------------------------------------------------------------------------

def _cmd_project_create(name: str):
    _check_init()
    if project_exists(name):
        print(f"project '{name}' already exists")
        sys.exit(1)
    d = project_dir(name)
    (d / "history").mkdir(parents=True)
    save_project_config(name, {})
    prefs = preferences_path(name)
    prefs.write_text(
        f"# Preferences — {name}\n\n"
        "Instructions here are appended after global preferences for this project.\n"
        f"Add preferences using: claudecast train \"your instruction\" --project {name}\n\n"
        "<!-- preferences below this line -->\n"
    )
    print(f"created project: {name}")
    print(f"  {d}")
    print(f"run `claudecast project use {name}` to make it active.")


def _cmd_project_list():
    _check_init()
    projects = list_projects()
    if not projects:
        print("no projects yet. run: claudecast project create <name>")
        return
    active = load_config().get("active_project")
    print()
    for p in projects:
        marker = " *" if p == active else ""
        print(f"  {p}{marker}")
    print()
    if active:
        print(f"  (* = active project)")


def _cmd_project_use(name: str):
    _check_init()
    if not project_exists(name):
        print(f"project '{name}' not found. run: claudecast project create {name}")
        sys.exit(1)
    cfg = load_config()
    cfg["active_project"] = name
    save_config(cfg)
    print(f"active project set to: {name}")


def _cmd_project_show(name: str | None):
    _check_init()
    if not name:
        name = load_config().get("active_project")
    if not name:
        print("no active project. pass a name or run: claudecast project use <name>")
        sys.exit(1)
    if not project_exists(name):
        print(f"project '{name}' not found.")
        sys.exit(1)
    proj_cfg = load_project_config(name)
    _print_config(proj_cfg or {}, f"project: {name}")
    prefs = preferences_path(name)
    if prefs.exists():
        content = prefs.read_text().strip()
        print("preferences.md:")
        print("-" * 14)
        print(content)
        print()


def _cmd_project_set(key: str, value: str, project: str | None):
    _check_init()
    name = project or load_config().get("active_project")
    if not name:
        print("no project specified and no active project. use --project NAME")
        sys.exit(1)
    if not project_exists(name):
        print(f"project '{name}' not found.")
        sys.exit(1)
    if key not in VALID_CONFIG_KEYS:
        print(f"unknown key: {key}")
        print(f"valid keys: {', '.join(sorted(VALID_CONFIG_KEYS))}")
        sys.exit(1)
    cfg = load_project_config(name)
    if key in ("default_slides",):
        value = int(value)
    cfg[key] = value
    save_project_config(name, cfg)
    print(f"[{name}] set {key} = {value}")


# ---------------------------------------------------------------------------
# train
# ---------------------------------------------------------------------------

def _resolve_train_project(project: str | None) -> str | None:
    if project:
        if not project_exists(project):
            print(f"project '{project}' not found.")
            sys.exit(1)
    return project


def _cmd_train(text: str | None, project: str | None, file: str | None,
               show: bool, edit: bool, clear: bool):
    _check_init()
    project = _resolve_train_project(project)
    prefs = preferences_path(project)
    scope = f"project '{project}'" if project else "global"

    if show:
        if not prefs.exists():
            print(f"no preferences set for {scope}.")
            return
        print(f"\n{scope} preferences:\n")
        print(prefs.read_text())
        return

    if edit:
        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, str(prefs)])
        return

    if clear:
        confirm = input(f"clear all {scope} preferences? [y/N]: ").strip().lower()
        if confirm == "y":
            header = (
                f"# Preferences — {project}\n\n"
                f"Instructions here are appended after global preferences for this project.\n"
                f"Add preferences using: claudecast train \"your instruction\" --project {project}\n\n"
                "<!-- preferences below this line -->\n"
            ) if project else (
                "# Global Style Preferences\n\n"
                "Instructions here are prepended to every Claude call.\n"
                "Add preferences using: claudecast train \"your instruction\"\n\n"
                "<!-- preferences below this line -->\n"
            )
            prefs.write_text(header)
            print(f"cleared {scope} preferences.")
        return

    instruction = None
    if text:
        instruction = text.strip()
    elif file:
        instruction = Path(file).read_text().strip()

    if not instruction:
        print("provide an instruction, --file, --show, --edit, or --clear")
        sys.exit(1)

    # append to preferences.md
    if not prefs.exists():
        prefs.parent.mkdir(parents=True, exist_ok=True)
        prefs.write_text(
            f"# Preferences — {project or 'global'}\n\n"
            "<!-- preferences below this line -->\n"
        )

    existing = prefs.read_text()
    timestamp = datetime.now().strftime("%Y-%m-%d")
    entry = f"\n- [{timestamp}] {instruction}\n"
    prefs.write_text(existing + entry)
    print(f"added to {scope} preferences.")


# ---------------------------------------------------------------------------
# install-skill
# ---------------------------------------------------------------------------

def _generate_skill_md(cmd: str) -> str:
    return f"""\
# claudecast

Generate narrated slide decks and videos from a prompt, file, or data input.

**CLI:** `{cmd}`

## Before generating — read these files

- `~/.claudecast/config.json` — active template, active project, defaults
- `~/.claudecast/templates/{{active_template}}/LAYOUTS.md` — available layouts + OOXML rules
- `~/.claudecast/style/preferences.md` — global style instructions
- `~/.claudecast/projects/{{active_project}}/preferences.md` — project preferences (if set)
- `~/.claudecast/projects/{{active_project}}/config.json` — project config overrides

Always read the live files above before generating — never assume defaults.

## Commands

**Setup**
```
{cmd} init
{cmd} install-skill
```

**Config**
```
{cmd} config show
{cmd} config set default_voice en-US-GuyNeural
{cmd} config set default_slides 8
{cmd} config set active_template custom
{cmd} config set active_project morning-briefing
{cmd} config set output_dir ~/Presentations
```

**Projects**
```
{cmd} project create morning-briefing
{cmd} project list
{cmd} project use morning-briefing
{cmd} project show [NAME]
{cmd} project set default_slides 5
{cmd} project set default_voice en-US-GuyNeural --project morning-briefing
```

**Style preferences**
```
{cmd} train "always open with a headline number"
{cmd} train "keep under 5 slides" --project morning-briefing
{cmd} train --show [--project NAME]
{cmd} train --edit [--project NAME]
{cmd} train --clear [--project NAME]
{cmd} train --file style_guide.md [--project NAME]
```

**Generation (coming soon)**
```
{cmd} generate "topic"
{cmd} generate report.pdf --project morning-briefing
{cmd} generate data.csv --slides 8 --voice en-US-AriaNeural
{cmd} generate "topic" --pptx-only
{cmd} generate "topic" --audio-only
{cmd} generate "topic" --video-only
{cmd} generate outline.json --video-only
```

**Voices**
```
{cmd} voices
```

## ~/.claudecast/ structure

```
~/.claudecast/
├── config.json                    # global defaults + active template/project
├── style/preferences.md           # global style — prepended to every Claude call
├── templates/
│   ├── default/
│   │   ├── start.pptx             # base deck (theme + masters only)
│   │   ├── examples/*.xml         # named example slide XMLs
│   │   └── LAYOUTS.md             # layout catalog + OOXML rules
│   └── custom/                    # from claudecast ingest template
├── projects/
│   └── {{name}}/
│       ├── config.json            # overrides global config for this project
│       ├── preferences.md         # appended after global preferences
│       └── history/               # past runs
└── agents/                        # optional system prompt overrides
```
"""


def _install_skill():
    python_path = sys.executable
    cmd = str(Path(python_path).parent / "claudecast")

    cwd = Path.cwd()
    project_claude_dir = cwd / ".claude"

    if project_claude_dir.exists():
        print(f"claude project detected: {cwd}")
        print(f"  [1] global  (~/.claude/skills/claudecast/)  [default]")
        print(f"  [2] project ({cwd}/.claude/skills/claudecast/)")
        choice = input("choice [1/2, enter=global]: ").strip()
    else:
        print("no .claude/ folder found — installing globally.")
        choice = "1"

    dest_dir = (
        project_claude_dir / "skills" / "claudecast"
        if choice == "2"
        else Path.home() / ".claude" / "skills" / "claudecast"
    )
    print(f"\ntarget: {dest_dir}")

    paths_file = dest_dir / "paths.json"
    if paths_file.exists():
        try:
            existing = json.loads(paths_file.read_text())
            print("\nexisting install found:")
            print(f"  version : {existing.get('version', 'unknown')}")
            print(f"  python  : {existing.get('python', 'unknown')}")
            if existing.get("version") != __version__:
                print(f"  version mismatch (installed: {existing.get('version')}, current: {__version__})")
            if existing.get("python") != python_path:
                print("  python path differs — skill will point to a different environment")
            if input("\noverwrite? [y/N]: ").strip().lower() != "y":
                print("aborted.")
                return
        except Exception:
            pass

    dest_dir.mkdir(parents=True, exist_ok=True)
    paths_file.write_text(json.dumps({
        "version": __version__,
        "python": python_path,
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    (dest_dir / "SKILL.md").write_text(_generate_skill_md(cmd))

    print(f"\nskill installed to {dest_dir}")
    print(f"  SKILL.md  — uses {cmd}")
    print(f"  paths.json — version {__version__}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="claudecast",
        description="generate narrated slide decks and videos from a prompt",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    sub.add_parser("init", help="initialize ~/.claudecast/")

    # config
    config_p = sub.add_parser("config", help="manage global config")
    config_sub = config_p.add_subparsers(dest="config_cmd", required=True)
    config_sub.add_parser("show", help="show current config")
    config_set = config_sub.add_parser("set", help="set a config value")
    config_set.add_argument("key")
    config_set.add_argument("value")

    # project
    proj_p = sub.add_parser("project", help="manage projects")
    proj_sub = proj_p.add_subparsers(dest="project_cmd", required=True)
    proj_create = proj_sub.add_parser("create", help="create a new project")
    proj_create.add_argument("name")
    proj_sub.add_parser("list", help="list all projects")
    proj_use = proj_sub.add_parser("use", help="set active project")
    proj_use.add_argument("name")
    proj_show = proj_sub.add_parser("show", help="show project config + preferences")
    proj_show.add_argument("name", nargs="?", default=None)
    proj_set = proj_sub.add_parser("set", help="set a project config value")
    proj_set.add_argument("key")
    proj_set.add_argument("value")
    proj_set.add_argument("--project", default=None)

    # train
    train_p = sub.add_parser("train", help="manage style preferences")
    train_p.add_argument("text", nargs="?", default=None, help="instruction to add")
    train_p.add_argument("--project", default=None)
    train_p.add_argument("--file", default=None, help="read instruction from file")
    train_p.add_argument("--show", action="store_true")
    train_p.add_argument("--edit", action="store_true")
    train_p.add_argument("--clear", action="store_true")

    # voices (stub)
    sub.add_parser("voices", help="list available tts voices")

    # install-skill
    sub.add_parser("install-skill", help="install claude code skill")

    args = parser.parse_args()

    if args.command == "init":
        _cmd_init()

    elif args.command == "config":
        if args.config_cmd == "show":
            _cmd_config_show()
        elif args.config_cmd == "set":
            _cmd_config_set(args.key, args.value)

    elif args.command == "project":
        if args.project_cmd == "create":
            _cmd_project_create(args.name)
        elif args.project_cmd == "list":
            _cmd_project_list()
        elif args.project_cmd == "use":
            _cmd_project_use(args.name)
        elif args.project_cmd == "show":
            _cmd_project_show(args.name)
        elif args.project_cmd == "set":
            _cmd_project_set(args.key, args.value, args.project)

    elif args.command == "train":
        _cmd_train(args.text, args.project, args.file, args.show, args.edit, args.clear)

    elif args.command == "voices":
        print("voices command coming soon — requires edge-tts install")

    elif args.command == "install-skill":
        _install_skill()


if __name__ == "__main__":
    main()
