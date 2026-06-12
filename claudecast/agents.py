"""
Claude agents — generation pipeline stages.
"""

import json
import re
import subprocess
import sys
from pathlib import Path


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
        match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', raw)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"no valid JSON found in response:\n{raw[:500]}")


def _find_pptx_plugin_dir() -> str | None:
    import glob
    matches = glob.glob("/root/.claude/remote/plugins/*/skills/pptx")
    if matches:
        return matches[0].replace("/skills/pptx", "")
    return None


def run_slide_agent(
    input_text: str,
    output_dir: str,
    system_prompt: str,
    slide_count: int | None = None,
) -> dict:
    """
    Runs claude -p to generate a PPTX. Claude decides layout and design.
    Writes slides.pptx and slides.json to output_dir.
    Returns parsed slide JSON: {slides: [{index, title, content, details}], pptx_path}
    """
    pptx_path = str(Path(output_dir) / "slides.pptx")
    json_path = str(Path(output_dir) / "slides.json")

    slide_instruction = (
        f"The deck should have exactly {slide_count} slides."
        if slide_count
        else "Decide how many slides best suits the content."
    )

    prompt = (
        f"Generate a PowerPoint presentation and save it to: {pptx_path}\n\n"
        f"{slide_instruction}\n\n"
        f"After saving the PPTX, write a JSON file to: {json_path}\n"
        f"The JSON must have this exact structure:\n"
        f'{{\n'
        f'  "slides": [\n'
        f'    {{\n'
        f'      "index": 1,\n'
        f'      "title": "slide title",\n'
        f'      "content": "text and bullets visible on the slide",\n'
        f'      "details": "additional context, data, or nuance not shown on the slide — used for voiceover"\n'
        f'    }}\n'
        f'  ]\n'
        f'}}\n\n'
        f"Input:\n{input_text}"
    )

    cmd = ["claude", "-p", prompt, "--allowedTools", "Bash,Write,Read"]

    plugin_dir = _find_pptx_plugin_dir()
    if plugin_dir:
        cmd += ["--plugin-dir", plugin_dir]

    if system_prompt:
        cmd += ["--system-prompt", system_prompt]

    print("generating slides...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"slide agent exited with code {result.returncode}")

    json_file = Path(json_path)
    if not json_file.exists():
        raise RuntimeError(f"slide agent did not produce slides.json at {json_path}")

    data = _parse_json(json_file.read_text())
    data["pptx_path"] = pptx_path
    return data


def run_script_agent(
    slides: list[dict],
    system_prompt: str,
) -> list[str]:
    """
    Takes slide JSON from slide agent, generates per-slide voiceover narration.
    Returns list of narration strings in slide order.
    """
    prompt = (
        f"You are writing spoken voiceover narration for a presentation.\n\n"
        f"For each slide below, write 2-4 sentences of natural spoken narration. "
        f"Do NOT read the slide text aloud — interpret, connect, and add context. "
        f"Use the 'details' field for additional depth.\n\n"
        f"Return ONLY valid JSON:\n"
        f'{{"scripts": ["narration for slide 1", "narration for slide 2", ...]}}\n\n'
        f"Slides:\n{json.dumps(slides, indent=2)}"
    )
    raw = _run_claude(prompt, system_prompt or None)
    parsed = _parse_json(raw)
    return parsed["scripts"]


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
