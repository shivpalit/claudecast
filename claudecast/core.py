"""
Orchestration layer — stubs for content generation pipeline.
Not yet implemented; structural commands live in cli.py + config.py.
"""


def generate(topic: str, **kwargs) -> dict:
    raise NotImplementedError("coming soon")


def generate_outline(topic: str, slides: int = 8) -> list[dict]:
    raise NotImplementedError("coming soon")


def build_pptx(outline: list[dict], output_path: str) -> str:
    raise NotImplementedError("coming soon")


def build_audio(outline: list[dict], output_dir: str, voice: str = "en-US-AriaNeural") -> list[str]:
    raise NotImplementedError("coming soon")


def build_video(pptx_path: str, audio_paths: list[str], output_path: str) -> str:
    raise NotImplementedError("coming soon")
