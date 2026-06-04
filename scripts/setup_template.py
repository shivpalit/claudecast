#!/usr/bin/env python3
"""
One-off script — generates the default claudecast template.

Creates:
  ~/.claudecast/templates/default/start.pptx      — blank base deck (masters only)
  ~/.claudecast/templates/default/examples/*.xml  — example slide XMLs
  ~/.claudecast/templates/default/LAYOUTS.md      — layout reference for Claude

Run from the claudecast project root:
    python scripts/setup_template.py
"""

import zipfile
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

TEMPLATE_DIR = Path.home() / ".claudecast" / "templates" / "default"


def create_start_pptx():
    """Minimal base deck — slide masters + theme only, no content slides."""
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)
    out = TEMPLATE_DIR / "start.pptx"
    prs.save(str(out))
    print(f"  created {out}")


def create_example_xmls():
    """Generate one slide per layout type, extract raw OOXML into examples/."""
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    layouts = prs.slide_layouts
    # default python-pptx layout indices
    # 0=Title Slide, 1=Title and Content, 2=Section Header, 6=Blank

    slide_defs = [
        (0, "title",   lambda s: _fill_title_slide(s)),
        (1, "bullets", lambda s: _fill_bullets_slide(s)),
        (2, "section", lambda s: _fill_section_slide(s)),
        (6, "blank",   lambda s: None),
    ]

    for layout_idx, name, fill in slide_defs:
        slide = prs.slides.add_slide(layouts[layout_idx])
        fill(slide)

    tmp = TEMPLATE_DIR / "_tmp_examples.pptx"
    prs.save(str(tmp))

    examples_dir = TEMPLATE_DIR / "examples"
    examples_dir.mkdir(exist_ok=True)

    with zipfile.ZipFile(tmp) as z:
        for i, (_, name, _) in enumerate(slide_defs, start=1):
            xml = z.read(f"ppt/slides/slide{i}.xml").decode("utf-8")
            out = examples_dir / f"{name}.xml"
            out.write_text(xml)
            print(f"  extracted {out}")

    tmp.unlink()


def _fill_title_slide(slide):
    slide.shapes.title.text = "Presentation Title"
    try:
        slide.placeholders[1].text = "Subtitle goes here"
    except KeyError:
        pass


def _fill_bullets_slide(slide):
    slide.shapes.title.text = "Slide Title"
    try:
        tf = slide.placeholders[1].text_frame
        tf.text = "First bullet point"
        tf.add_paragraph().text = "Second bullet point"
        tf.add_paragraph().text = "Third bullet point"
    except KeyError:
        pass


def _fill_section_slide(slide):
    slide.shapes.title.text = "Section Header"


def write_layouts_md():
    path = TEMPLATE_DIR / "LAYOUTS.md"
    path.write_text("""\
# Default Template Layouts

Generated from the default python-pptx theme.
Replace with your own by running: claudecast ingest template your_deck.pptx

## Slide dimensions
- 12192000 x 6858000 EMUs (16:9 — 13.33" x 7.5")

## Available layouts

### title.xml
Full-bleed title slide.
- Placeholder 0: title (centered, large)
- Placeholder 1: subtitle

### bullets.xml
Standard content slide with title + bullet list.
- Placeholder 0: title
- Placeholder 1: body (bulleted paragraphs)

### section.xml
Section divider.
- Placeholder 0: section title (centered)

### blank.xml
No placeholders — use for fully custom OOXML layouts.

## OOXML notes
- Text lives in `<a:r><a:t>` runs inside `<a:p>` paragraphs inside `<p:txBody>`
- Bullets: `<a:buChar char="•"/>` or `<a:buNone/>` inside `<a:pPr>`
- Prefer `<a:schemeClr>` over hardcoded RGB to inherit theme colors
- Shapes positioned with `<p:spPr><a:xfrm>` using EMU units (914400 EMU = 1 inch)
""")
    print(f"  wrote {path}")


def main():
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"setting up default template at {TEMPLATE_DIR}\n")
    create_start_pptx()
    create_example_xmls()
    write_layouts_md()
    print("\ndone.")


if __name__ == "__main__":
    main()
