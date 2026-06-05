"""
Orchestration layer — content generation pipeline.
"""

import json
from datetime import datetime
from pathlib import Path

from .config import claudecast_dir, preferences_path, resolve_config


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
            from docx import Document
            doc = Document(p)
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

    print(f"generating {_slides} scripts...")
    scripts = run_script_agent(input_text, system_prompt, _slides)

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

    (out / "manifest.json").write_text(json.dumps(result, indent=2))
    return result


def generate_slides(
    source: str,
    *,
    project: str | None = None,
    output_base: str | None = None,
    slides: int | None = None,
    model: str | None = None,
    aspect: str | None = None,
) -> dict:
    """
    Slides-only pipeline: input → scripts → PPTX.
    Returns dict with keys: scripts, pptx_path, output_dir.
    """
    from .agents import run_script_agent
    from .compilers.slides import generate_pptx

    cfg = resolve_config(project)
    _slides = slides or cfg.get("default_slides", 8)
    _aspect = aspect or cfg.get("default_aspect", "16:9")
    _base = output_base or cfg.get("output_dir", str(Path.home() / "claudecast-output"))

    input_text = _read_input(source)
    system_prompt = _build_system_prompt(project)

    print(f"generating {_slides} scripts...")
    scripts = run_script_agent(input_text, system_prompt, _slides)

    out = _output_dir(_base, project)
    pptx_path = str(out / "slides.pptx")

    print("building slides...")
    generate_pptx(scripts, pptx_path, _aspect)

    result = {
        "scripts": scripts,
        "pptx_path": pptx_path,
        "output_dir": str(out),
    }

    (out / "manifest.json").write_text(json.dumps(result, indent=2))
    return result


def _load_template_assets(template_name: str) -> tuple[str, dict[str, str]]:
    """Load LAYOUTS.md and example XMLs from template dir. Returns (layouts_md, example_xmls)."""
    tdir = claudecast_dir() / "templates" / template_name
    layouts_md = (tdir / "LAYOUTS.md").read_text() if (tdir / "LAYOUTS.md").exists() else ""
    example_xmls = {}
    examples_dir = tdir / "examples"
    if examples_dir.exists():
        for f in examples_dir.glob("*.xml"):
            example_xmls[f.stem] = f.read_text()
    return layouts_md, example_xmls


def generate_full(
    source: str,
    *,
    project: str | None = None,
    output_base: str | None = None,
    slides: int | None = None,
    voice: str | None = None,
    aspect: str | None = None,
    video: bool = True,
) -> dict:
    """
    Full sequential pipeline:
      outline → analysis (per slide) → ooxml (per slide) → script (per slide)
      → inject pptx → render images → audio → video

    Returns dict with all artifact paths + intermediate data.
    """
    from .agents import run_analysis_agent, run_outline_agent, run_ooxml_agent, run_script_agent_v2
    from .compilers.audio import generate_all as generate_all_audio
    from .compilers.slides import render_slide_images
    from .compilers.video import build_video

    cfg = resolve_config(project)
    _slides = slides or cfg.get("default_slides", 8)
    _voice = voice or cfg.get("default_voice", "en-US-AriaNeural")
    _aspect = aspect or cfg.get("default_aspect", "16:9")
    _template = cfg.get("active_template", "default")
    _base = output_base or cfg.get("output_dir", str(Path.home() / "claudecast-output"))

    input_text = _read_input(source)
    system_prompt = _build_system_prompt(project)
    layouts_md, example_xmls = _load_template_assets(_template)

    out = _output_dir(_base, project)

    # Stage 1: outline
    print(f"[1/4] generating outline ({_slides} slides)...")
    outline = run_outline_agent(input_text, system_prompt, _slides)
    (out / "outline.json").write_text(json.dumps(outline, indent=2))

    # Stages 2-4: per-slide, context builds
    slide_specs = []
    ooxml_strings = []
    scripts = []

    for slide in outline["slides"]:
        i = slide["index"]
        n = len(outline["slides"])

        print(f"[2/4] analyzing slide {i}/{n}...")
        spec = run_analysis_agent(slide, outline, input_text, system_prompt)
        slide_specs.append(spec)

        print(f"[3/4] generating ooxml for slide {i}/{n}...")
        ooxml = run_ooxml_agent(spec, layouts_md, example_xmls, system_prompt)
        ooxml_strings.append(ooxml)

        print(f"[4/4] writing script for slide {i}/{n}...")
        script = run_script_agent_v2(spec, ooxml, system_prompt)
        scripts.append(script)

    (out / "slide_specs.json").write_text(json.dumps(slide_specs, indent=2))

    # inject OOXML into template → pptx
    print("building pptx...")
    template_pptx = str(claudecast_dir() / "templates" / _template / "start.pptx")
    pptx_path = str(out / "slides.pptx")
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from inject_slides import inject_slides
        inject_slides(ooxml_strings, template_pptx, pptx_path)
    except Exception as e:
        print(f"  inject_slides failed ({e}), falling back to python-pptx")
        from .compilers.slides import generate_pptx
        generate_pptx(scripts, pptx_path, _aspect)

    # render slide images
    print("rendering slide images...")
    image_paths = render_slide_images(scripts, str(out / "images"))

    # audio
    print(f"generating audio ({_voice})...")
    audio_paths = generate_all_audio(scripts, str(out / "audio"), _voice)

    result: dict = {
        "outline": outline,
        "slide_specs": slide_specs,
        "scripts": scripts,
        "pptx_path": pptx_path,
        "image_paths": image_paths,
        "audio_paths": audio_paths,
        "output_dir": str(out),
    }

    if video:
        print("building video...")
        video_path = str(out / "video.mp4")
        build_video(image_paths, audio_paths, video_path)
        result["video_path"] = video_path

    (out / "manifest.json").write_text(json.dumps(result, indent=2))
    return result


def generate_podcast(
    source: str,
    *,
    project: str | None = None,
    output_base: str | None = None,
    voice: str | None = None,
) -> dict:
    """
    Podcast pipeline: input → single narration script → one MP3.
    Returns a dict with keys: script, audio_path, output_dir.
    """
    from .agents import run_podcast_agent
    from .compilers.audio import generate_slide_audio

    cfg = resolve_config(project)
    _voice = voice or cfg.get("default_voice", "en-US-AriaNeural")
    _base = output_base or cfg.get("output_dir", str(Path.home() / "claudecast-output"))

    input_text = _read_input(source)
    system_prompt = _build_system_prompt(project)

    print("generating narration script...")
    script = run_podcast_agent(input_text, system_prompt)

    out = _output_dir(_base, project)
    audio_path = str(out / "podcast.mp3")

    print(f"generating audio ({_voice})...")
    generate_slide_audio(script, _voice, audio_path)

    result = {
        "script": script,
        "audio_path": audio_path,
        "output_dir": str(out),
    }

    (out / "manifest.json").write_text(json.dumps(result, indent=2))
    return result
