#!/usr/bin/env python3
"""
parse_pptx.py — ingest a PPTX as a claudecast template.

Extracts:
  - start.pptx          : theme + masters only (no content slides)
  - examples/<name>.xml : one XML per slide, named by layout
  - LAYOUTS.md          : layout catalog for the OOXML agent

Usage:
    python scripts/parse_pptx.py path/to/deck.pptx [template_name]

    template_name defaults to "default"
"""

import io
import json
import re
import sys
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Layout name inference — maps slide index to a canonical layout name.
# Can be overridden via --map flag or interactive prompt.
# ---------------------------------------------------------------------------

DEFAULT_LAYOUT_MAP = {
    1:  "title",
    2:  "section",
    3:  "body",
    4:  "bullets",
    5:  "two_column",
    6:  "table",
    7:  "big_stat",
    8:  "timeline",
    9:  "image",
    10: "quote",
    11: "blank",
}

LAYOUT_DESCRIPTIONS = {
    "title":       "Full-bleed title slide — large centered title + subtitle",
    "section":     "Section divider — section number label + large section title",
    "body":        "Narrative text — title + one or two body paragraphs",
    "bullets":     "Key findings — title + finding/detail bullet pairs",
    "two_column":  "Two-column — title + left column + right column (opportunities/risks etc.)",
    "table":       "Data table — title + drawn table with header row and data rows",
    "big_stat":    "Big stat callout — title + large metric value + delta + descriptor label",
    "timeline":    "Timeline / schedule — title + horizontal sequence of steps",
    "image":       "Image + caption — title + image placeholder + figure caption",
    "quote":       "Pull quote — large centered quote text + attribution",
    "blank":       "Blank slide — no placeholders, fully custom",
}


def _extract_text(xml: str) -> list[str]:
    return re.findall(r'<a:t[^>]*>([^<]+)</a:t>', xml)


def _slide_number(path: str) -> int:
    m = re.search(r'slide(\d+)\.xml$', path)
    return int(m.group(1)) if m else 0


def _build_start_pptx(src_zip: zipfile.ZipFile) -> bytes:
    """Strip all content slides from the PPTX, keep masters/theme/layouts."""
    entries: dict[str, bytes] = {
        name: src_zip.read(name) for name in src_zip.namelist()
    }

    # remove content slides + their rels
    entries = {
        k: v for k, v in entries.items()
        if not re.match(r'ppt/slides/slide\d+\.xml$', k)
        and not re.match(r'ppt/slides/_rels/slide\d+\.xml\.rels$', k)
    }

    # patch content types — remove slide overrides
    ct = entries['[Content_Types].xml'].decode('utf-8')
    ct = re.sub(
        r'<Override PartName="/ppt/slides/slide\d+\.xml"[^/]*/>\s*', '', ct
    )
    entries['[Content_Types].xml'] = ct.encode('utf-8')

    # patch presentation.xml — empty the sldIdLst
    prs = entries['ppt/presentation.xml'].decode('utf-8')
    prs = re.sub(
        r'<p:sldIdLst>.*?</p:sldIdLst>',
        '<p:sldIdLst/>',
        prs,
        flags=re.DOTALL,
    )
    entries['ppt/presentation.xml'] = prs.encode('utf-8')

    # patch presentation rels — remove slide relationships
    if 'ppt/_rels/presentation.xml.rels' in entries:
        rels = entries['ppt/_rels/presentation.xml.rels'].decode('utf-8')
        rels = re.sub(
            r'<Relationship[^>]+/officeDocument/2006/relationships/slide"[^/]*/>\s*',
            '', rels,
        )
        entries['ppt/_rels/presentation.xml.rels'] = rels.encode('utf-8')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries.items():
            zout.writestr(name, data)
    return buf.getvalue()


def _build_layouts_md(layout_map: dict[int, str], slide_texts: dict[int, list[str]]) -> str:
    pptx_path_note = "Generated from ingested template. Regenerate with: claudecast ingest template your_deck.pptx"
    lines = [
        "# Template Layouts\n",
        f"_{pptx_path_note}_\n",
        "## Slide dimensions",
        "- See start.pptx — preserve exact cx/cy values from example XMLs\n",
        "## Available layouts\n",
    ]

    for idx in sorted(layout_map):
        name = layout_map[idx]
        desc = LAYOUT_DESCRIPTIONS.get(name, "")
        texts = slide_texts.get(idx, [])
        preview = ", ".join(f'"{t}"' for t in texts[:3]) if texts else ""
        lines += [
            f"### {name}.xml  _(slide {idx})_",
            f"{desc}",
        ]
        if preview:
            lines.append(f"Sample text: {preview}")
        lines.append("")

    lines += [
        "## OOXML rules",
        "- Preserve all namespace declarations from the example XML",
        "- Keep exact `<a:xfrm>` position/size values unless content requires resize",
        "- Use `<a:srgbClr>` values from examples to stay on-brand (do not invent colors)",
        "- For tables: replicate the shape-based table pattern from `table.xml` — do NOT use `<a:tbl>`",
        "- Text runs: `<a:r><a:rPr .../><a:t>content</a:t></a:r>` inside `<a:p>` inside `<p:txBody>`",
        "- Bullets: `<a:buNone/>` to suppress, `<a:buChar char='·'/>` to enable",
        "- Replace placeholder text with real content — never leave template strings in output",
    ]

    return "\n".join(lines)


def ingest(pptx_path: str, template_name: str = "default", layout_map: dict | None = None, interactive: bool = False):
    from pathlib import Path
    claudecast_dir = Path.home() / ".claudecast"
    out_dir = claudecast_dir / "templates" / template_name
    examples_dir = out_dir / "examples"

    print(f"\ningesting: {pptx_path}")
    print(f"template:  {out_dir}\n")

    with zipfile.ZipFile(pptx_path) as z:
        slide_paths = sorted(
            [n for n in z.namelist() if re.match(r'ppt/slides/slide\d+\.xml$', n)],
            key=_slide_number,
        )

        slide_xmls = {_slide_number(p): z.read(p).decode('utf-8') for p in slide_paths}
        slide_texts = {i: _extract_text(xml) for i, xml in slide_xmls.items()}

        print(f"found {len(slide_xmls)} slides\n")

        # resolve layout map
        _map = layout_map or DEFAULT_LAYOUT_MAP

        if interactive:
            print("assign a layout name to each slide (enter to accept default):\n")
            for i in sorted(slide_xmls):
                default = _map.get(i, f"slide_{i}")
                texts = slide_texts[i][:3]
                preview = " | ".join(texts) if texts else "(no text)"
                raw = input(f"  slide {i:2d} [{default}]  {preview[:60]}: ").strip()
                if raw:
                    _map[i] = raw

        # write output
        out_dir.mkdir(parents=True, exist_ok=True)
        examples_dir.mkdir(exist_ok=True)

        # start.pptx
        start_bytes = _build_start_pptx(z)
        (out_dir / "start.pptx").write_bytes(start_bytes)
        print(f"  wrote start.pptx ({len(start_bytes)//1024}KB)")

        # example XMLs
        for i, xml in slide_xmls.items():
            name = _map.get(i, f"slide_{i}")
            path = examples_dir / f"{name}.xml"
            path.write_text(xml)
            print(f"  wrote examples/{name}.xml  (slide {i})")

        # LAYOUTS.md
        layouts_md = _build_layouts_md(_map, slide_texts)
        (out_dir / "LAYOUTS.md").write_text(layouts_md)
        print(f"  wrote LAYOUTS.md")

        # manifest
        manifest = {
            "source": str(pptx_path),
            "template": template_name,
            "slides": len(slide_xmls),
            "layout_map": {str(k): v for k, v in _map.items()},
        }
        (out_dir / "ingest_manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\ndone. template '{template_name}' ready at {out_dir}")
    return out_dir


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: parse_pptx.py <deck.pptx> [template_name] [--interactive]")
        sys.exit(1)

    pptx = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "default"
    interactive = "--interactive" in sys.argv

    ingest(pptx, name, interactive=interactive)
