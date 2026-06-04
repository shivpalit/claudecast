"""
Claude agents — each wraps a single-purpose `claude -p` subprocess call.
"""

import json
import re
import subprocess
import sys


def _extract_json(text: str) -> str:
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def _run_claude(prompt: str, system_prompt: str | None = None) -> str:
    cmd = ["claude", "-p", prompt]
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"claude exited with code {result.returncode}")

    return result.stdout.strip()


def run_script_agent(
    input_text: str,
    system_prompt: str,
    slides: int,
) -> list[str]:
    """
    Generate narration scripts for each slide/section from input_text.
    Returns a list of strings, one per slide.
    """
    prompt = (
        f"Generate exactly {slides} narration scripts from the input below.\n\n"
        f"Each script is a short paragraph (2-4 sentences) to be read aloud for one slide.\n"
        f"Return ONLY a JSON object in this exact format, no prose or markdown:\n"
        f'  {{"scripts": ["script for slide 1", "script for slide 2", ...]}}\n\n'
        f"Input:\n{input_text}"
    )

    raw = _run_claude(prompt, system_prompt or None)
    parsed = json.loads(_extract_json(raw))
    scripts = parsed["scripts"]

    # ensure correct count
    scripts = scripts[:slides]
    while len(scripts) < slides:
        scripts.append(scripts[-1] if scripts else "")

    return scripts
