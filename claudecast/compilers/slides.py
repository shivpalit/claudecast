"""
Slides compiler — renders slide images from PPTX.

Primary: pptxtoimages (LibreOffice + poppler) — requires system deps.
Fallback: python-pptx + Pillow — lower quality but no system deps.
"""

from pathlib import Path

EMU_PER_INCH = 914400


def render_slide_images(
    pptx_path: str,
    output_dir: str,
    width: int = 1280,
) -> list[str]:
    """
    Render slides from a PPTX to PNG images.
    Uses pptxtoimages (LibreOffice) if available, falls back to python-pptx + Pillow.
    Returns list of image paths in slide order.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    try:
        return _render_libreoffice(pptx_path, str(out))
    except Exception as e:
        print(f"  pptxtoimages unavailable ({e}), falling back to python-pptx renderer")
        return _render_pillow(pptx_path, str(out), width)


def _render_libreoffice(pptx_path: str, output_dir: str) -> list[str]:
    from pptxtoimages.tools import PPTXToImageConverter
    converter = PPTXToImageConverter(pptx_path, output_dir=output_dir)
    images = converter.convert()
    return sorted(str(p) for p in images)


def _render_pillow(pptx_path: str, output_dir: str, width: int) -> list[str]:
    from PIL import Image, ImageDraw
    from pptx import Presentation

    prs = Presentation(pptx_path)
    out = Path(output_dir)
    scale = width / prs.slide_width
    height = int(prs.slide_height * scale)

    paths = []
    for i, slide in enumerate(prs.slides, start=1):
        bg = _get_slide_bg(slide)
        img = Image.new("RGB", (width, height), color=bg)
        draw = ImageDraw.Draw(img)

        for shape in slide.shapes:
            fill = _get_fill_color(shape)
            if fill:
                x, y, w, h = _shape_rect(shape, scale)
                draw.rectangle([x, y, x + w, y + h], fill=fill)

            if not shape.has_text_frame:
                continue

            x, y, w, h = _shape_rect(shape, scale)
            pad = int(width * 0.01)
            cy = y + pad
            text_default = (0, 0, 0) if sum(bg) > 382 else (255, 255, 255)

            for para in shape.text_frame.paragraphs:
                if not para.text.strip():
                    cy += int(height * 0.01)
                    continue
                bold, size_pt, color = _para_style(para, text_default)
                font = _load_font(bold, size_pt * scale * 72 / 96)
                line_h = int(size_pt * scale * 72 / 96 * 1.3)
                for line in _wrap(draw, para.text, font, w - pad * 2):
                    if cy + line_h > y + h:
                        break
                    draw.text((x + pad, cy), line, fill=color, font=font)
                    cy += line_h
                cy += int(line_h * 0.2)

        path = str(out / f"slide_{i:02d}.png")
        img.save(path)
        paths.append(path)

    return paths


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _emu_px(emu: int, scale: float) -> int:
    return int(emu * scale)


def _shape_rect(shape, scale: float) -> tuple[int, int, int, int]:
    return (
        _emu_px(shape.left, scale),
        _emu_px(shape.top, scale),
        _emu_px(shape.width, scale),
        _emu_px(shape.height, scale),
    )


def _get_rgb(color) -> tuple[int, int, int] | None:
    try:
        if color and color.type is not None:
            rgb = color.rgb
            return (rgb.red, rgb.green, rgb.blue)
    except Exception:
        pass
    return None


def _get_fill_color(shape) -> tuple[int, int, int] | None:
    try:
        fill = shape.fill
        if fill.type is not None:
            return _get_rgb(fill.fore_color)
    except Exception:
        pass
    return None


def _get_slide_bg(slide) -> tuple[int, int, int]:
    try:
        fill = slide.background.fill
        if fill.type is not None:
            rgb = _get_rgb(fill.fore_color)
            if rgb:
                return rgb
    except Exception:
        pass
    return (255, 255, 255)


def _para_style(para, default_color) -> tuple[bool, float, tuple]:
    bold, size_pt, color = False, 18.0, default_color
    if para.runs:
        run = para.runs[0]
        bold = run.font.bold or False
        if run.font.size:
            size_pt = run.font.size / 12700
        rc = _get_rgb(run.font.color) if run.font.color else None
        if rc:
            color = rc
    return bold, size_pt, color


def _load_font(bold: bool, size_pt: float):
    from PIL import ImageFont
    size = max(8, int(size_pt))
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        if bold else
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines, line = [], ""
    for word in words:
        test = f"{line} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] > max_width and line:
            lines.append(line)
            line = word
        else:
            line = test
    if line:
        lines.append(line)
    return lines
