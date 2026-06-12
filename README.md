# claudecast

Generate narrated slide decks, voiceover audio, and videos from a prompt, file, or data input — via CLI or as a Claude Code skill.

```bash
claudecast generate "the history of the internet" --mode video
```

---

## How It Works

claudecast runs a multi-stage pipeline:

1. **Slide agent** — a `claude -p` subprocess reads your input and generates a fully designed PPTX deck. It uses the `/pptx` skill (pptxgenjs) if available, and writes a `slides.json` manifest with per-slide content and details.
2. **Script agent** — takes the slide manifest and writes natural spoken voiceover narration for each slide (interprets and contextualises, doesn't read the slide aloud).
3. **Audio compiler** — converts narration to MP3s per slide via `edge-tts`, then combines them.
4. **Video compiler** — renders the PPTX to images via LibreOffice, then stitches each slide image + audio clip into an MP4 using ffmpeg.

For `--mode podcast`, steps 2-4 are replaced by a single continuous narration → one MP3.

---

## Install

```bash
pip install claudecast
```

Then initialize the config directory:

```bash
claudecast init
```

Optionally register as a Claude Code skill so Claude can invoke it directly:

```bash
claudecast install-skill
```

---

## System Dependencies

These must be installed separately — they cannot be installed via pip.

### Required

**Claude CLI** — the slide agent runs as a `claude -p` subprocess:
```bash
npm install -g @anthropic-ai/claude-code
```
Set `ANTHROPIC_API_KEY` in your environment.

**ffmpeg** — audio combining and video rendering:
```bash
# Ubuntu/Debian
apt install ffmpeg

# macOS
brew install ffmpeg
```

### Required for video mode (high quality)

**LibreOffice** and **Poppler** — converts PPTX to images for video rendering. Without these, claudecast falls back to a python-pptx + Pillow renderer (lower quality):

```bash
# Ubuntu/Debian
apt install libreoffice poppler-utils

# macOS
brew install libreoffice poppler
```

Then install the Python wrapper:
```bash
pip install pptxtoimages
```

### Optional (for video optional extras)
```bash
pip install claudecast[video]   # includes pptxtoimages + imageio-ffmpeg
pip install claudecast[all]     # everything
```

---

## Usage

### Modes

| Mode | What it produces |
|------|-----------------|
| `--mode slides` | PPTX deck only |
| `--mode video` | PPTX + per-slide MP3s + combined.mp3 + video.mp4 |
| `--mode podcast` | Single continuous narration → one MP3 |

### Generate

```bash
# slides only
claudecast generate "topic" --mode slides
claudecast generate notes.txt --mode slides --slide-count 6

# video — full pipeline
claudecast generate "topic" --mode video
claudecast generate notes.txt --mode video --slide-count 8 --voice en-US-GuyNeural
claudecast generate data.csv --mode video --project my-project

# podcast
claudecast generate "topic" --mode podcast
claudecast generate article.pdf --mode podcast --voice en-US-AriaNeural

# read from stdin
cat notes.txt | claudecast generate - --mode podcast

# long prompts — pass as a file to avoid OS arg length limits
claudecast generate /path/to/prompt.txt --mode video --slide-count 6
```

**Flags:**

| Flag | Description |
|------|-------------|
| `--mode` | `podcast`, `slides`, or `video` (required) |
| `--slide-count N` | Number of slides for slides/video modes. Omit to let Claude decide. |
| `--voice NAME` | edge-tts voice name (default: `en-US-AvaNeural`) |
| `--output DIR` | Override output directory |
| `--project NAME` | Use a named project's config and preferences |

**Supported input formats:** plain text, `.md`, `.txt`, `.pdf`, `.docx`, `.csv`, or stdin (`-`).

---

### Voices

```bash
claudecast voices                  # list all voices
claudecast voices --lang en-US     # filter by locale
```

---

### Config

Global config stored at `~/.claudecast/config.json`.

```bash
claudecast config show
claudecast config set default_voice en-US-GuyNeural
claudecast config set output_dir ~/Presentations
claudecast config set active_project my-project
```

**Valid keys:**

| Key | Default | Description |
|-----|---------|-------------|
| `default_voice` | `en-US-AvaNeural` | edge-tts voice |
| `default_model` | `claude-sonnet-4-6` | Claude model for script agent |
| `output_dir` | `~/claudecast-output` | Base output directory |
| `active_project` | `null` | Active project (overrides global config) |

---

### Projects

Projects let you set per-use-case defaults and style preferences.

```bash
claudecast project create my-project      # interactive setup wizard
claudecast project list                   # list all projects
claudecast project use my-project         # set active project
claudecast project deactivate             # clear active project
claudecast project show [NAME]            # show config + preferences
claudecast project set default_voice en-US-GuyNeural --project my-project
```

---

### Style Preferences (train)

Preferences are prepended to every Claude call as a system prompt. Use them to set persistent style, tone, and content guidelines.

```bash
# global preferences
claudecast train "always open with a bold headline stat"
claudecast train "keep voiceover under 30 seconds per slide"
claudecast train --show
claudecast train --edit
claudecast train --clear

# project-scoped preferences
claudecast train "use dark backgrounds" --project my-project
claudecast train --file my_style_guide.md --project my-project
claudecast train --show --project my-project
```

---

### Init / Reset

```bash
claudecast init             # create ~/.claudecast/ structure (safe to re-run)
claudecast init --reset     # wipe and reinitialize
```

---

## Output Structure

Each run writes to a timestamped folder under `output_dir`:

```
~/claudecast-output/
└── {project or "default"}/
    └── {YYYYMMDD_HHMMSS}/
        ├── slides.pptx         # generated deck
        ├── slides.json         # per-slide content manifest
        ├── images/             # rendered slide images (video mode)
        ├── audio/
        │   ├── slide_01.mp3
        │   └── slide_02.mp3
        ├── combined.mp3        # all slides concatenated
        ├── video.mp4           # final video (video mode)
        └── manifest.json       # full run artifact paths
```

---

## ~/.claudecast/ Structure

```
~/.claudecast/
├── config.json                    # global defaults + active project
├── style/
│   └── preferences.md             # global style — prepended to every Claude call
├── templates/
│   └── default/
│       └── LAYOUTS.md             # layout reference (scaffolded by init)
└── projects/
    └── {name}/
        ├── config.json            # overrides global config for this project
        ├── preferences.md         # appended after global preferences
        └── history/               # reserved for future run history
```

---

## As a Claude Code Skill

After `claudecast install-skill`, Claude can invoke the CLI directly from any conversation in the project (or globally, depending on install choice).

The skill is installed to `~/.claude/skills/claudecast/SKILL.md` (global) or `.claude/skills/claudecast/SKILL.md` (project). It bakes in the full binary path so it works regardless of which Python environment is active.

To update the skill after upgrading claudecast:
```bash
claudecast install-skill    # prompts to overwrite
```

---

## Requirements

- Python 3.11+
- Claude CLI on PATH (`claude`)
- `ANTHROPIC_API_KEY` in environment
- ffmpeg (audio + video)
- LibreOffice + poppler + pptxtoimages (video mode, high quality)

---

## Status

v0.1.0 — active development.
