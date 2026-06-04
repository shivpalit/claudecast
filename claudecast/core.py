"""
Pure Python API — no CLI concerns, importable by anything.
"""

from pathlib import Path


def generate(
    topic: str,
    slides: int = 8,
    voice: str = "en-US-AriaNeural",
    output_dir: str = ".",
) -> dict:
    """
    Full pipeline: outline → PPTX → voiceover scripts → TTS audio → video.
    Returns paths to generated artifacts.
    """
    raise NotImplementedError("coming soon")


def generate_outline(topic: str, slides: int = 8) -> list[dict]:
    """
    Use Claude to generate a slide outline.
    Returns list of {title, bullets, speaker_notes}.
    """
    raise NotImplementedError("coming soon")


def build_pptx(outline: list[dict], output_path: str) -> str:
    """Build a PPTX from an outline. Returns output path."""
    raise NotImplementedError("coming soon")


def build_audio(outline: list[dict], output_dir: str, voice: str = "en-US-AriaNeural") -> list[str]:
    """Generate per-slide TTS audio files. Returns list of wav paths."""
    raise NotImplementedError("coming soon")


def build_video(pptx_path: str, audio_paths: list[str], output_path: str) -> str:
    """Compile PPTX slides + audio into an MP4. Returns output path."""
    raise NotImplementedError("coming soon")


def list_voices() -> list[dict]:
    """List available edge-tts voices."""
    raise NotImplementedError("coming soon")
