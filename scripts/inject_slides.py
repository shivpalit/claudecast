#!/usr/bin/env python3
"""
inject_slides.py — zip OOXML slide strings into a template PPTX.

Usage:
    from scripts.inject_slides import inject_slides
    inject_slides(xml_strings, template_path, output_path)

Or as a CLI:
    python scripts/inject_slides.py template.pptx out.pptx slide1.xml slide2.xml ...
"""

import shutil
import sys
import zipfile
from pathlib import Path


_SLIDE_REL_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>"""

_CONTENT_TYPE_SLIDE = (
    "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
)


def inject_slides(
    xml_strings: list[str],
    template_path: str,
    output_path: str,
) -> str:
    """
    Inject OOXML slide strings into a template PPTX.

    Replaces all existing content slides in the template with the provided XMLs.
    Returns output_path.
    """
    template = Path(template_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(template, output)

    with zipfile.ZipFile(output, "a") as zout:
        # read existing zip contents to know what's already there
        existing = set(zout.namelist())

        for i, xml in enumerate(xml_strings, start=1):
            slide_path = f"ppt/slides/slide{i}.xml"
            rel_path = f"ppt/slides/_rels/slide{i}.xml.rels"

            # write slide XML
            _zip_write(zout, slide_path, xml, existing)
            # write slide relationship file
            _zip_write(zout, rel_path, _SLIDE_REL_TEMPLATE, existing)

        # rewrite [Content_Types].xml to register all slides
        content_types = _build_content_types(zout, len(xml_strings))
        _zip_write(zout, "[Content_Types].xml", content_types, existing)

        # rewrite ppt/_rels/presentation.xml.rels to reference all slides
        prs_rels = _build_presentation_rels(zout, len(xml_strings))
        _zip_write(zout, "ppt/_rels/presentation.xml.rels", prs_rels, existing)

        # rewrite ppt/presentation.xml sldIdLst
        prs_xml = _read_zip_text(zout, "ppt/presentation.xml")
        prs_xml = _patch_presentation_xml(prs_xml, len(xml_strings))
        _zip_write(zout, "ppt/presentation.xml", prs_xml, existing)

    return str(output)


def _zip_write(zf: zipfile.ZipFile, path: str, content: str, existing: set):
    """Write or overwrite a file inside the zip."""
    if path in existing:
        # zipfile doesn't support in-place replace — rebuild approach needed
        # for now, duplicate entry (last one wins in most readers)
        pass
    zf.writestr(path, content.encode("utf-8"))


def _read_zip_text(zf: zipfile.ZipFile, path: str) -> str:
    return zf.read(path).decode("utf-8")


def _build_content_types(zf: zipfile.ZipFile, n_slides: int) -> str:
    existing = zf.read("[Content_Types].xml").decode("utf-8")
    # strip existing slide overrides
    import re
    existing = re.sub(
        r'<Override PartName="/ppt/slides/slide\d+\.xml"[^/]*/>', "", existing
    )
    # inject new ones before closing tag
    overrides = "\n".join(
        f'  <Override PartName="/ppt/slides/slide{i}.xml" ContentType="{_CONTENT_TYPE_SLIDE}"/>'
        for i in range(1, n_slides + 1)
    )
    return existing.replace("</Types>", f"{overrides}\n</Types>")


def _build_presentation_rels(zf: zipfile.ZipFile, n_slides: int) -> str:
    import re
    existing = zf.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
    # strip existing slide relationships
    existing = re.sub(
        r'<Relationship[^>]+officeDocument/2006/relationships/slide"[^/]*/>\s*', "",
        existing,
    )
    rels = "\n".join(
        f'  <Relationship Id="rId{100+i}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
        f'Target="slides/slide{i}.xml"/>'
        for i in range(1, n_slides + 1)
    )
    return existing.replace("</Relationships>", f"{rels}\n</Relationships>")


def _patch_presentation_xml(xml: str, n_slides: int) -> str:
    import re
    # replace sldIdLst contents
    sld_ids = "\n".join(
        f'      <p:sldId id="{256+i}" r:id="rId{100+i}"/>'
        for i in range(1, n_slides + 1)
    )
    patched = re.sub(
        r"<p:sldIdLst>.*?</p:sldIdLst>",
        f"<p:sldIdLst>\n{sld_ids}\n    </p:sldIdLst>",
        xml,
        flags=re.DOTALL,
    )
    return patched


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: inject_slides.py template.pptx out.pptx slide1.xml [slide2.xml ...]")
        sys.exit(1)
    template = sys.argv[1]
    output = sys.argv[2]
    xmls = [Path(f).read_text() for f in sys.argv[3:]]
    inject_slides(xmls, template, output)
    print(f"wrote {output} ({len(xmls)} slides)")
