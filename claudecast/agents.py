"""
Claude API agents — each agent wraps a single-purpose claude call.
"""

import json
import re


def _extract_json(text: str) -> str:
    """Pull the first {...} block out of a response that may have prose around it."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def run_script_agent(
    input_text: str,
    system_prompt: str,
    slides: int,
    model: str,
) -> list[str]:
    """
    Generate narration scripts for each slide from input_text.
    Returns a list of strings, one per slide/section.
    """
    import anthropic

    client = anthropic.Anthropic()

    user_msg = (
        f"Generate exactly {slides} narration scripts from the input below.\n\n"
        f"Each script is a short paragraph (2-4 sentences) to be read aloud for one slide.\n"
        f"Return ONLY a JSON object in this exact format:\n"
        f'  {{"scripts": ["script for slide 1", "script for slide 2", ...]}}\n\n'
        f"No prose, no markdown, no explanation — just the JSON.\n\n"
        f"Input:\n{input_text}"
    )

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt or "You generate concise, engaging narration scripts for slide presentations.",
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = message.content[0].text.strip()
    parsed = json.loads(_extract_json(raw))
    scripts = parsed["scripts"]

    if len(scripts) != slides:
        # trim or pad to match requested count
        scripts = scripts[:slides]
        while len(scripts) < slides:
            scripts.append(scripts[-1] if scripts else "")

    return scripts
