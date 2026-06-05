#!/usr/bin/env python3
"""
inject_slides.py — wire OOXML slide strings into a template PPTX.

Reads start.pptx, replaces all content slides with the provided XMLs,
and writes a new PPTX. Uses full zip-rebuild to avoid duplicate entry bugs.

Usage:
    from scripts.inject_slides import inject_slides
    inject_slides(xml_strings, template_path, output_path)
"""

import io
import re
import sys
import zipfile
from pathlib import Path

_CONTENT_TYPE_SLIDE = (
    "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
)

_SLIDE_REL = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" \
Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" \
Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>"""


def inject_slides(
    xml_strings: list[str],
    template_path: str,
    output_path: str,
) -> str:
    """
    Inject OOXML slide strings into template_path, write to output_path.
    Returns output_path.
    """
    # read entire template into memory as {path: bytes}
    with zipfile.ZipFile(template_path, "r") as zin:
        entries: dict[str, bytes] = {name: zin.read(name) for name in zin.namelist()}

    # remove existing slide entries (content + rels)
    entries = {
        k: v for k, v in entries.items()
        if not re.match(r"ppt/slides/slide\d+\.xml$", k)
        and not re.match(r"ppt/slides/_rels/slide\d+\.xml\.rels$", k)
    }

    # inject new slides
    for i, xml in enumerate(xml_strings, start=1):
        entries[f"ppt/slides/slide{i}.xml"] = xml.encode("utf-8")
        entries[f"ppt/slides/_rels/slide{i}.xml.rels"] = _SLIDE_REL.encode("utf-8")

    # patch [Content_Types].xml
    entries["[Content_Types].xml"] = _patch_content_types(
        entries["[Content_Types].xml"].decode("utf-8"), len(xml_strings)
    ).encode("utf-8")

    # patch ppt/_rels/presentation.xml.rels
    entries["ppt/_rels/presentation.xml.rels"] = _patch_prs_rels(
        entries["ppt/_rels/presentation.xml.rels"].decode("utf-8"), len(xml_strings)
    ).encode("utf-8")

    # patch ppt/presentation.xml sldIdLst
    entries["ppt/presentation.xml"] = _patch_presentation_xml(
        entries["ppt/presentation.xml"].decode("utf-8"), len(xml_strings)
    ).encode("utf-8")

    # write new zip
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries.items():
            zout.writestr(name, data)
    Path(output_path).write_bytes(buf.getvalue())

    return output_path


def _patch_content_types(xml: str, n: int) -> str:
    xml = re.sub(
        r'<Override PartName="/ppt/slides/slide\d+\.xml"[^/]*/>\s*', "", xml
    )
    overrides = "\n".join(
        f'  <Override PartName="/ppt/slides/slide{i}.xml" ContentType="{_CONTENT_TYPE_SLIDE}"/>'
        for i in range(1, n + 1)
    )
    return xml.replace("</Types>", f"{overrides}\n</Types>")


def _patch_prs_rels(xml: str, n: int) -> str:
    xml = re.sub(
        r'<Relationship[^>]+/officeDocument/2006/relationships/slide"[^/]*/>\s*',
        "",
        xml,
    )
    rels = "\n".join(
        f'  <Relationship Id="rId{100 + i}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
        f'Target="slides/slide{i}.xml"/>'
        for i in range(1, n + 1)
    )
    return xml.replace("</Relationships>", f"{rels}\n</Relationships>")


def _patch_presentation_xml(xml: str, n: int) -> str:
    sld_ids = "\n".join(
        f'      <p:sldId id="{256 + i}" r:id="rId{100 + i}"/>'
        for i in range(1, n + 1)
    )
    return re.sub(
        r"<p:sldIdLst>.*?</p:sldIdLst>",
        f"<p:sldIdLst>\n{sld_ids}\n    </p:sldIdLst>",
        xml,
        flags=re.DOTALL,
    )


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: inject_slides.py template.pptx out.pptx slide1.xml [slide2.xml ...]")
        sys.exit(1)
    xmls = [Path(f).read_text() for f in sys.argv[3:]]
    inject_slides(xmls, sys.argv[1], sys.argv[2])
    print(f"wrote {sys.argv[2]} ({len(xmls)} slides)")
