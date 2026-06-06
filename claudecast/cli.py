import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import (
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

def _cmd_init(quiet: bool = False, reset: bool = False):
    import shutil
    base = claudecast_dir()
    if reset and base.exists():
        confirm = input(f"delete {base} and reinitialize? [y/N]: ").strip().lower()
        if confirm != "y":
            print("aborted.")
            return
        shutil.rmtree(base)
        print(f"removed {base}")
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

_PROJECT_SETUP_KEYS = [
    ("default_slides",  "slides per deck",          int),
    ("default_voice",   "tts voice",                str),
    ("default_model",   "claude model",             str),
    ("default_aspect",  "slide aspect ratio",       str),
    ("output_dir",      "output directory",         str),
]


def _cmd_project_create(name: str):
    _check_init()
    if project_exists(name):
        print(f"project '{name}' already exists")
        sys.exit(1)

    global_cfg = load_config()
    print(f"\nsetting up project: {name}")
    print("press enter to accept the default shown in brackets.\n")

    overrides = {}
    for key, label, coerce in _PROJECT_SETUP_KEYS:
        default = global_cfg.get(key, DEFAULT_CONFIG.get(key, ""))
        raw = input(f"  {label} [{default}]: ").strip()
        if raw:
            overrides[key] = coerce(raw)

    d = project_dir(name)
    (d / "history").mkdir(parents=True)
    save_project_config(name, overrides)

    prefs = preferences_path(name)
    prefs.write_text(
        f"# Preferences — {name}\n\n"
        "Instructions here are appended after global preferences for this project.\n"
        f"Add preferences using: claudecast train \"your instruction\" --project {name}\n\n"
        "<!-- preferences below this line -->\n"
    )

    print(f"\ncreated project: {name}")
    print(f"  {d}")
    if overrides:
        for k, v in overrides.items():
            print(f"  {k} = {v}")
    else:
        print("  (using global defaults)")
    print(f"\nrun `claudecast project use {name}` to make it active.")


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
{cmd} project create morning-briefing    # interactive setup wizard
{cmd} project list
{cmd} project use morning-briefing
{cmd} project deactivate
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

**Generation**
```
# per-slide audio (N mp3s + combined.mp3)
{cmd} generate "topic" --audio-only
{cmd} generate notes.txt --audio-only --slides 5 --voice en-US-GuyNeural
{cmd} generate data.csv --audio-only --project morning-briefing
{cmd} generate - --audio-only            # read from stdin
{cmd} generate "topic" --audio-only --no-combine

# podcast (single continuous narration → one mp3)
{cmd} generate "topic" --podcast
{cmd} generate article.pdf --podcast --voice en-US-AriaNeural
{cmd} generate - --podcast --output ~/out/

# shared flags
# --slides N        number of slides (audio-only)
# --voice NAME      edge-tts voice
# --output DIR      override output directory
# --project NAME    override active project
```

PPTX + video pipeline coming soon.

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
    init_p = sub.add_parser("init", help="initialize ~/.claudecast/")
    init_p.add_argument("--reset", action="store_true", help="wipe and reinitialize")

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
    proj_sub.add_parser("deactivate", help="clear the active project")
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

    # generate
    gen_p = sub.add_parser("generate", help="generate output from input")
    gen_p.add_argument("input", help="topic string, file path, or - for stdin")
    gen_p.add_argument("--full", action="store_true", help="full pipeline: pptx + audio + video")
    gen_p.add_argument("--audio-only", action="store_true", help="generate audio only (no slides)")
    gen_p.add_argument("--slides-only", action="store_true", help="generate pptx only (no audio)")
    gen_p.add_argument("--podcast", action="store_true", help="single continuous narration, one mp3")
    gen_p.add_argument("--slides", type=int, default=None, help="number of slides/sections")
    gen_p.add_argument("--voice", default=None, help="edge-tts voice name")
    gen_p.add_argument("--model", default=None, help="claude model id")
    gen_p.add_argument("--output", default=None, help="output directory")
    gen_p.add_argument("--project", default=None, help="project name (overrides active)")
    gen_p.add_argument("--no-combine", action="store_true", help="skip combined.mp3")

    # ingest
    ingest_p = sub.add_parser("ingest", help="ingest assets into claudecast")
    ingest_sub = ingest_p.add_subparsers(dest="ingest_cmd", required=True)
    ingest_tpl = ingest_sub.add_parser("template", help="ingest a pptx as a template")
    ingest_tpl.add_argument("pptx", help="path to .pptx file")
    ingest_tpl.add_argument("--name", default="default", help="template name (default: default)")
    ingest_tpl.add_argument("--interactive", action="store_true", help="interactively name each slide layout")

    # voices
    voices_p = sub.add_parser("voices", help="list available tts voices")
    voices_p.add_argument("--lang", default=None, help="filter by locale prefix e.g. en-US")

    # install-skill
    sub.add_parser("install-skill", help="install claude code skill")

    args = parser.parse_args()

    if args.command == "init":
        _cmd_init(reset=args.reset)

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
        elif args.project_cmd == "deactivate":
            _check_init()
            cfg = load_config()
            if not cfg.get("active_project"):
                print("no active project.")
            else:
                prev = cfg["active_project"]
                cfg["active_project"] = None
                save_config(cfg)
                print(f"deactivated project: {prev}")
                print("outputs will go to output_dir/default/")
        elif args.project_cmd == "use":
            _cmd_project_use(args.name)
        elif args.project_cmd == "show":
            _cmd_project_show(args.name)
        elif args.project_cmd == "set":
            _cmd_project_set(args.key, args.value, args.project)

    elif args.command == "train":
        _cmd_train(args.text, args.project, args.file, args.show, args.edit, args.clear)

    elif args.command == "generate":
        _check_init()
        project = args.project or load_config().get("active_project")
        if args.podcast:
            from .core import generate_podcast
            result = generate_podcast(
                args.input,
                project=project,
                output_base=args.output,
                voice=args.voice,
            )
            print(f"\ndone. output: {result['output_dir']}")
            print(f"  podcast  : {result['audio_path']}")
        if args.full:
            from .core import generate_full
            result = generate_full(
                args.input,
                project=project,
                output_base=args.output,
                slides=args.slides,
                voice=args.voice,
            )
            print(f"\ndone. output: {result['output_dir']}")
            print(f"  pptx  : {result['pptx_path']}")
            if result.get("video_path"):
                print(f"  video : {result['video_path']}")
            print(f"  {len(result['audio_paths'])} audio files")
        elif args.slides_only:
            from .core import generate_slides
            result = generate_slides(
                args.input,
                project=project,
                output_base=args.output,
                slides=args.slides,
                model=args.model,
            )
            print(f"\ndone. output: {result['output_dir']}")
            print(f"  pptx : {result['pptx_path']}")
        elif args.audio_only:
            from .core import generate_audio
            result = generate_audio(
                args.input,
                project=project,
                output_base=args.output,
                slides=args.slides,
                voice=args.voice,
                model=args.model,
                combine=not args.no_combine,
            )
            print(f"\ndone. output: {result['output_dir']}")
            if result.get("combined"):
                print(f"  combined : {result['combined']}")
            print(f"  {len(result['audio_paths'])} audio files")
        elif not args.full:
            print("specify --full, --audio-only, --slides-only, or --podcast.")
            sys.exit(1)

    elif args.command == "ingest":
        _check_init()
        if args.ingest_cmd == "template":
            import sys as _sys
            _sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
            from parse_pptx import ingest
            out_dir = ingest(args.pptx, args.name, interactive=args.interactive)
            cfg = load_config()
            if cfg.get("active_template") != args.name:
                print(f"\nto use this template: claudecast config set active_template {args.name}")

    elif args.command == "voices":
        from .compilers.audio import list_voices
        voices = list_voices()
        lang = getattr(args, "lang", None)
        if lang:
            voices = [v for v in voices if v["locale"].startswith(lang)]
        print()
        for v in voices:
            print(f"  {v['name']:<40} {v['locale']:<10} {v['gender']}")
        print(f"\n  {len(voices)} voices")

    elif args.command == "install-skill":
        _install_skill()


if __name__ == "__main__":
    main()
