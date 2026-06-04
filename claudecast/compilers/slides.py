"""
Slides compiler — generates PPTX from narration scripts.

Today: uses python-pptx directly as a placeholder.
Eventually: agent generates OOXML per slide → inject_slides wires into template.
"""

from pathlib import Path


def generate_pptx(
    scripts: list[str],
    output_path: str,
    aspect: str = "16:9",
) -> str:
    """
    Generate a PPTX from a list of narration scripts.
    One slide per script — title extracted from first sentence, rest as body.
    Returns output_path.
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt

    prs = Presentation()
    if aspect == "16:9":
        prs.slide_width = Inches(13.33)
        prs.slide_height = Inches(7.5)
    else:
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)

    layout = prs.slide_layouts[1]  # Title and Content

    for script in scripts:
        sentences = [s.strip() for s in script.split(".") if s.strip()]
        title = sentences[0] if sentences else "Slide"
        body = ". ".join(sentences[1:]).strip() if len(sentences) > 1 else script

        slide = prs.slides.add_slide(layout)
        slide.shapes.title.text = title
        try:
            slide.placeholders[1].text = body
        except KeyError:
            pass

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    prs.save(output_path)
    return output_path


def render_slide_images(
    scripts: list[str],
    output_dir: str,
    width: int = 1280,
    height: int = 720,
) -> list[str]:
    """
    Render basic slide images from scripts using Pillow.
    Placeholder until LibreOffice rendering is in place.
    Returns list of PNG paths.
    """
    from PIL import Image, ImageDraw, ImageFont

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []

    for i, script in enumerate(scripts, start=1):
        sentences = [s.strip() for s in script.split(".") if s.strip()]
        title = sentences[0] if sentences else f"Slide {i}"
        body = ". ".join(sentences[1:]).strip() if len(sentences) > 1 else ""

        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except OSError:
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        # title
        draw.text((80, 100), title, fill=(30, 30, 30), font=title_font)
        # divider
        draw.line([(80, 180), (width - 80, 180)], fill=(200, 200, 200), width=2)
        # body — wrap text
        _draw_wrapped(draw, body, body_font, x=80, y=210, max_width=width - 160, fill=(80, 80, 80))
        # slide number
        draw.text((width - 60, height - 40), str(i), fill=(180, 180, 180), font=body_font)

        path = str(out / f"slide_{i:02d}.png")
        img.save(path)
        paths.append(path)

    return paths


def _draw_wrapped(draw, text: str, font, x: int, y: int, max_width: int, fill, line_height: int = 40):
    words = text.split()
    line = ""
    for word in words:
        test = f"{line} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and line:
            draw.text((x, y), line, fill=fill, font=font)
            y += line_height
            line = word
        else:
            line = test
    if line:
        draw.text((x, y), line, fill=fill, font=font)
