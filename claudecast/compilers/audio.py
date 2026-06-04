"""
Audio compiler — per-slide TTS generation via edge-tts + ffmpeg concat.
"""

import asyncio
import subprocess
from pathlib import Path


async def _generate_one(text: str, voice: str, output_path: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


async def _list_voices_async() -> list[dict]:
    import edge_tts
    voices = await edge_tts.list_voices()
    return [
        {
            "name": v["ShortName"],
            "locale": v["Locale"],
            "gender": v["Gender"],
        }
        for v in sorted(voices, key=lambda x: x["ShortName"])
    ]


def list_voices() -> list[dict]:
    return asyncio.run(_list_voices_async())


def generate_slide_audio(text: str, voice: str, output_path: str) -> str:
    """Generate a single audio file. Returns output_path."""
    asyncio.run(_generate_one(text, voice, output_path))
    return output_path


def generate_all(
    scripts: list[str],
    output_dir: str,
    voice: str = "en-US-AriaNeural",
) -> list[str]:
    """
    Generate one MP3 per script entry.
    Returns list of output paths in order.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    paths = []
    for i, text in enumerate(scripts, start=1):
        path = str(out / f"slide_{i:02d}.mp3")
        asyncio.run(_generate_one(text, voice, path))
        paths.append(path)

    return paths


def combine_audio(audio_paths: list[str], output_path: str) -> str:
    """Concatenate audio files into one via ffmpeg. Returns output_path."""
    if not audio_paths:
        raise ValueError("no audio files to combine")

    # write ffmpeg concat list to a temp file
    list_path = Path(output_path).parent / "_concat_list.txt"
    list_path.write_text("\n".join(f"file '{p}'" for p in audio_paths))

    result = subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c", "copy", output_path,
        ],
        capture_output=True,
        text=True,
    )
    list_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg combine failed:\n{result.stderr}")

    return output_path
