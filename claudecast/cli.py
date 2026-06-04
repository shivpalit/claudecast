import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .core import generate, list_voices


def _output(data, fmt: str = "json"):
    print(json.dumps(data, indent=2) if fmt == "json" else data)


def _add_output(p):
    p.add_argument("--output", choices=["json", "text"], default="json")


def _generate_skill_md(cmd: str) -> str:
    return f"""\
# claudecast

Generate narrated slide decks and videos from a prompt.

**CLI:** `{cmd}`

## Commands

**Generate a full deck + video**
```
{cmd} generate "your topic here"
{cmd} generate "your topic here" --slides 10 --voice en-US-GuyNeural --out ./output
```

**List available voices**
```
{cmd} voices
```

## Options for generate

- `--slides N` — number of slides (default: 8)
- `--voice NAME` — edge-tts voice name (default: en-US-AriaNeural)
- `--out DIR` — output directory (default: current dir)

## Notes

- Requires ANTHROPIC_API_KEY in environment
- Outputs: deck.pptx, per-slide wav files, final.mp4
- Run `{cmd} voices` to browse available TTS voices
"""


def _install_skill(pkg_name: str, cli_name: str, skill_slug: str):
    python_path = sys.executable
    cmd = str(Path(python_path).parent / cli_name)

    cwd = Path.cwd()
    project_claude_dir = cwd / ".claude"

    if project_claude_dir.exists():
        print(f"Claude project detected: {cwd}")
        print(f"  [1] Global  (~/.claude/skills/{skill_slug}/)  [default]")
        print(f"  [2] Project ({cwd}/.claude/skills/{skill_slug}/)")
        choice = input("Choice [1/2, Enter=global]: ").strip()
    else:
        print("No .claude/ folder found — installing globally.")
        choice = "1"

    dest_dir = (
        project_claude_dir / "skills" / skill_slug
        if choice == "2"
        else Path.home() / ".claude" / "skills" / skill_slug
    )
    print(f"\nTarget: {dest_dir}")

    paths_file = dest_dir / "paths.json"
    if paths_file.exists():
        try:
            existing = json.loads(paths_file.read_text())
            print("\nExisting install found:")
            print(f"  version : {existing.get('version', 'unknown')}")
            print(f"  python  : {existing.get('python', 'unknown')}")
            if existing.get("version") != __version__:
                print(f"  version mismatch (installed: {existing.get('version')}, current: {__version__})")
            if existing.get("python") != python_path:
                print("  python path differs — skill will point to a different environment")
            if input("\nOverwrite? [y/N]: ").strip().lower() != "y":
                print("Aborted.")
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

    print(f"\nSkill installed to {dest_dir}")
    print(f"  SKILL.md  — uses {cmd}")
    print(f"  paths.json — version {__version__}")


def main():
    parser = argparse.ArgumentParser(
        prog="claudecast",
        description="generate narrated slide decks and videos from a prompt",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen_p = sub.add_parser("generate", help="generate deck + audio + video from a topic")
    gen_p.add_argument("topic", help="topic or prompt for the presentation")
    gen_p.add_argument("--slides", type=int, default=8)
    gen_p.add_argument("--voice", default="en-US-AriaNeural")
    gen_p.add_argument("--out", default=".", dest="output_dir")
    _add_output(gen_p)

    sub.add_parser("voices", help="list available tts voices")

    sub.add_parser("install-skill", help="install claude code skill to ~/.claude/skills/")

    args = parser.parse_args()

    if args.command == "generate":
        result = generate(args.topic, slides=args.slides, voice=args.voice, output_dir=args.output_dir)
        _output(result)

    elif args.command == "voices":
        _output(list_voices())

    elif args.command == "install-skill":
        _install_skill(
            pkg_name="claudecast",
            cli_name="claudecast",
            skill_slug="claudecast",
        )


if __name__ == "__main__":
    main()
