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
