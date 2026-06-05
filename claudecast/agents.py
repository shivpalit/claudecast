"""
Claude agents — sequential pipeline stages, each builds on prior context.

Pipeline: outline → analysis (per slide) → ooxml (per slide) → script (per slide)
"""

import json
import re
import subprocess
import sys


def _run_claude(prompt: str, system_prompt: str | None = None) -> str:
    cmd = ["claude", "-p", prompt]
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"claude exited with code {result.returncode}")
    return result.stdout.strip()


def _parse_json(raw: str) -> dict | list:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # try to extract first JSON object or array
        match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', raw)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"no valid JSON found in response:\n{raw[:500]}")


def _extract_xml(raw: str) -> str:
    """Pull the <p:sld ...>...</p:sld> block out of a response."""
    match = re.search(r'<p:sld[\s\S]*?</p:sld>', raw)
    if match:
        return match.group(0)
    # fallback: strip markdown fences
    raw = re.sub(r'```xml\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)
    return raw.strip()


# ---------------------------------------------------------------------------
# Stage 1: Outline
# ---------------------------------------------------------------------------

def run_outline_agent(
    input_text: str,
    system_prompt: str,
    slides: int,
) -> dict:
    """
    Input → high-level deck outline.
    Returns: {title, slides: [{index, title, purpose, content_hint}]}
    """
    prompt = (
        f"Analyze the input and create a {slides}-slide presentation outline.\n\n"
        f"Return ONLY valid JSON, no prose:\n"
        f'{{\n'
        f'  "title": "presentation title",\n'
        f'  "slides": [\n'
        f'    {{\n'
        f'      "index": 1,\n'
        f'      "title": "slide title",\n'
        f'      "purpose": "what this slide accomplishes in the overall narrative",\n'
        f'      "content_hint": "what specific data, facts, or content belongs here"\n'
        f'    }}\n'
        f'  ]\n'
        f'}}\n\n'
        f"Input:\n{input_text}"
    )
    raw = _run_claude(prompt, system_prompt or None)
    return _parse_json(raw)


# ---------------------------------------------------------------------------
# Stage 2: Analysis (per slide)
# ---------------------------------------------------------------------------

def run_analysis_agent(
    slide: dict,
    outline: dict,
    input_text: str,
    system_prompt: str,
) -> dict:
    """
    Per slide: decides layout and extracts exact content from source data.
    Returns slide spec: {index, title, layout, content: {bullets?, table?, takeaway}}
    """
    n = len(outline["slides"])
    prompt = (
        f"You are analyzing content for slide {slide['index']} of {n} "
        f"in a presentation titled \"{outline['title']}\".\n\n"
        f"Slide purpose: {slide['purpose']}\n"
        f"Content hint: {slide['content_hint']}\n\n"
        f"Decide exactly what goes on this slide:\n"
        f"- Choose the best layout: bullets, table, section, or blank\n"
        f"- If table: extract the exact rows and columns from the source data\n"
        f"- If bullets: extract the key points (max 5 bullets)\n"
        f"- Identify the single most important takeaway\n\n"
        f"Return ONLY valid JSON:\n"
        f'{{\n'
        f'  "index": {slide["index"]},\n'
        f'  "title": "slide title",\n'
        f'  "layout": "bullets|table|section|blank",\n'
        f'  "content": {{\n'
        f'    "bullets": ["point 1", "point 2"],\n'
        f'    "table": {{"headers": ["col1", "col2"], "rows": [["val", "val"]]}},\n'
        f'    "takeaway": "the single key message"\n'
        f'  }}\n'
        f'}}\n\n'
        f"Full deck outline (for narrative context):\n"
        f"{json.dumps(outline, indent=2)}\n\n"
        f"Source data:\n{input_text}"
    )
    raw = _run_claude(prompt, system_prompt or None)
    return _parse_json(raw)


# ---------------------------------------------------------------------------
# Stage 3: OOXML generation (per slide)
# ---------------------------------------------------------------------------

def run_ooxml_agent(
    slide_spec: dict,
    layouts_md: str,
    example_xmls: dict[str, str],
    system_prompt: str,
) -> str:
    """
    Per slide: generates raw OOXML from slide spec + template examples.
    Returns a complete <p:sld>...</p:sld> XML string.
    """
    layout = slide_spec.get("layout", "bullets")
    example = example_xmls.get(layout) or example_xmls.get("bullets") or ""

    prompt = (
        f"Generate valid OOXML for a single PowerPoint slide.\n\n"
        f"Slide spec:\n{json.dumps(slide_spec, indent=2)}\n\n"
        f"Layout to use: {layout}\n\n"
        f"Reference example XML for this layout (adapt, don't copy verbatim):\n"
        f"{example}\n\n"
        f"Layout and OOXML rules:\n{layouts_md}\n\n"
        f"Return ONLY the raw XML — the complete <p:sld> element and its children. "
        f"No prose, no markdown fences, no explanation."
    )
    raw = _run_claude(prompt, system_prompt or None)
    return _extract_xml(raw)


# ---------------------------------------------------------------------------
# Stage 4: Script (per slide)
# ---------------------------------------------------------------------------

def run_script_agent_v2(
    slide_spec: dict,
    ooxml: str,
    system_prompt: str,
) -> str:
    """
    Per slide: writes spoken narration knowing exactly what's on screen.
    Returns a single narration string.
    """
    prompt = (
        f"Write spoken narration for this slide. "
        f"The audience is looking at it right now.\n\n"
        f"Slide spec:\n{json.dumps(slide_spec, indent=2)}\n\n"
        f"Actual slide XML (what's visually on screen):\n{ooxml}\n\n"
        f"Write 2-4 sentences of natural spoken narration. "
        f"Don't read bullets aloud — explain, connect, give context. "
        f"Reference what the viewer sees.\n\n"
        f'Return ONLY JSON: {{"script": "narration text"}}'
    )
    raw = _run_claude(prompt, system_prompt or None)
    return _parse_json(raw)["script"]


# ---------------------------------------------------------------------------
# Standalone agents (audio-only / podcast — no slide context needed)
# ---------------------------------------------------------------------------

def run_script_agent(
    input_text: str,
    system_prompt: str,
    slides: int,
) -> list[str]:
    """Simple per-slide scripts without full pipeline. Used by audio-only mode."""
    prompt = (
        f"Generate exactly {slides} narration scripts from the input below.\n\n"
        f"Each script is a short paragraph (2-4 sentences) to be read aloud for one slide.\n"
        f'Return ONLY JSON: {{"scripts": ["script 1", "script 2", ...]}}\n\n'
        f"Input:\n{input_text}"
    )
    raw = _run_claude(prompt, system_prompt or None)
    parsed = _parse_json(raw)
    scripts = parsed["scripts"]
    scripts = scripts[:slides]
    while len(scripts) < slides:
        scripts.append(scripts[-1] if scripts else "")
    return scripts


def run_podcast_agent(
    input_text: str,
    system_prompt: str,
) -> str:
    """Single continuous narration for podcast mode."""
    prompt = (
        "Write a single continuous narration from the input below.\n\n"
        "Flow naturally as spoken audio — no slide breaks, no bullet points, no headings.\n"
        'Return ONLY JSON: {"script": "full narration text"}\n\n'
        f"Input:\n{input_text}"
    )
    raw = _run_claude(prompt, system_prompt or None)
    return _parse_json(raw)["script"]
