# claudecast

Generate narrated slide decks and videos from a prompt — usable as a CLI or a Claude Code skill.

```bash
claudecast generate "the history of the internet" --slides 10
```

Outputs a PPTX, per-slide voiceover audio, and a compiled MP4.

---

## Install

```bash
pip install claudecast
```

**Register as a Claude Code skill** (one-time, per machine):

```bash
claudecast install-skill
```

After that, Claude can invoke `claudecast` directly — no manual setup.

---

## Usage

```bash
# generate full deck + audio + video
claudecast generate "topic" --slides 8 --voice en-US-AriaNeural --out ./output

# list available tts voices
claudecast voices
```

---

## Requirements

- Python 3.11+
- `ANTHROPIC_API_KEY` in environment

---

## Status

v0.1.0 — scaffold only, implementation in progress.

Built on the [claude-skill-template](https://github.com/shivpalit/claude-skill-template) pattern.
