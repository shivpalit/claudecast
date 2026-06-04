"""
Video compiler — combines slide images + audio into MP4 via ffmpeg.
"""

import subprocess
import sys
from pathlib import Path


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def build_slide_video(image_path: str, audio_path: str, output_path: str) -> str:
    """Combine a single slide image + audio clip into an MP4. Returns output_path."""
    ffmpeg = _ffmpeg_exe()
    result = subprocess.run(
        [
            ffmpeg, "-y",
            "-loop", "1", "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            output_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"ffmpeg failed for slide video: {output_path}")
    return output_path


def concat_videos(video_paths: list[str], output_path: str) -> str:
    """Concatenate MP4 segments into one file. Returns output_path."""
    if not video_paths:
        raise ValueError("no video segments to concatenate")

    list_path = Path(output_path).parent / "_concat_list.txt"
    list_path.write_text("\n".join(f"file '{p}'" for p in video_paths))

    ffmpeg = _ffmpeg_exe()
    result = subprocess.run(
        [
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            output_path,
        ],
        capture_output=True,
        text=True,
    )
    list_path.unlink(missing_ok=True)

    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"ffmpeg concat failed:\n{result.stderr}")

    return output_path


def build_video(
    image_paths: list[str],
    audio_paths: list[str],
    output_path: str,
) -> str:
    """
    Build a full video from per-slide images + audio clips.
    Returns output_path.
    """
    if len(image_paths) != len(audio_paths):
        raise ValueError(f"image/audio count mismatch: {len(image_paths)} vs {len(audio_paths)}")

    segments_dir = Path(output_path).parent / "segments"
    segments_dir.mkdir(exist_ok=True)

    segment_paths = []
    for i, (img, aud) in enumerate(zip(image_paths, audio_paths), start=1):
        seg = str(segments_dir / f"seg_{i:02d}.mp4")
        build_slide_video(img, aud, seg)
        segment_paths.append(seg)

    return concat_videos(segment_paths, output_path)
