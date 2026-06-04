"""
Orchestration layer — content generation pipeline.
"""

import json
from datetime import datetime
from pathlib import Path

from .config import preferences_path, resolve_config


def _read_input(source: str) -> str:
    """Read input from a file path, '-' (stdin), or treat as literal text."""
    if source == "-":
        import sys
        return sys.stdin.read()

    p = Path(source)
    if p.exists():
        suffix = p.suffix.lower()
        if suffix in (".txt", ".md"):
            return p.read_text()
        if suffix == ".pdf":
            import pdfplumber
            with pdfplumber.open(p) as pdf:
                return "\n\n".join(page.extract_text() or "" for page in pdf.pages)
        if suffix == ".docx":
            import docx
            doc = docx.Document(p)
            return "\n\n".join(para.text for para in doc.paragraphs if para.text.strip())
        if suffix == ".csv":
            import pandas as pd
            df = pd.read_csv(p)
            return df.to_string(index=False)
        # fallback for unknown extensions
        return p.read_text()

    # treat as literal string
    return source


def _build_system_prompt(project: str | None) -> str:
    """Concatenate global + project preferences, stripping comment headers."""
    parts = []
    for path in [preferences_path(None), preferences_path(project) if project else None]:
        if path and path.exists():
            text = path.read_text()
            # strip everything up to and including the marker
            marker = "<!-- preferences below this line -->"
            if marker in text:
                text = text.split(marker, 1)[1]
            text = text.strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def _output_dir(base: str, project: str | None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = project or "default"
    out = Path(base) / folder / stamp
    out.mkdir(parents=True, exist_ok=True)
    return out


def generate_audio(
    source: str,
    *,
    project: str | None = None,
    output_base: str | None = None,
    slides: int | None = None,
    voice: str | None = None,
    model: str | None = None,
    combine: bool = True,
) -> dict:
    """
    Full audio-only pipeline: input → scripts → per-slide MP3s → combined.mp3

    Returns a dict with keys: scripts, audio_paths, output_dir, combined (if combine=True).
    """
    from .agents import run_script_agent
    from .compilers.audio import combine_audio, generate_all

    cfg = resolve_config(project)
    _slides = slides or cfg.get("default_slides", 8)
    _voice = voice or cfg.get("default_voice", "en-US-AriaNeural")
    _model = model or cfg.get("default_model", "claude-sonnet-4-6")
    _base = output_base or cfg.get("output_dir", str(Path.home() / "claudecast-output"))

    input_text = _read_input(source)
    system_prompt = _build_system_prompt(project)

    print(f"generating {_slides} scripts with {_model}...")
    scripts = run_script_agent(input_text, system_prompt, _slides, _model)

    out = _output_dir(_base, project)
    audio_dir = out / "audio"

    print(f"generating audio ({_voice})...")
    audio_paths = generate_all(scripts, str(audio_dir), _voice)

    result: dict = {
        "scripts": scripts,
        "audio_paths": audio_paths,
        "output_dir": str(out),
    }

    if combine:
        combined_path = str(out / "combined.mp3")
        print("combining audio...")
        combine_audio(audio_paths, combined_path)
        result["combined"] = combined_path

    # save manifest
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(result, indent=2))

    return result
