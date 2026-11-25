"""Verify the held-out source images and optionally rebuild them from the original PDF."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(pdf=None):
    rows = [json.loads(line) for line in (ROOT / "pages.jsonl").read_text().splitlines()]
    edition = json.loads((ROOT / "edition.json").read_text())
    if [r["printed_page"] for r in rows] != list(range(110, 114)):
        raise ValueError("The four consecutive pages must be scored as a single held-out selection")
    doc = None
    if pdf:
        import pypdfium2
        if sha256(pdf.read_bytes()) != edition["pdf_sha256"]:
            raise ValueError("Original PDF digest has changed")
        doc = pypdfium2.PdfDocument(pdf)
    for row in rows:
        data = (ROOT.parent / row["image"]).read_bytes()
        size = struct.unpack(">II", data[16:24])
        if sha256(data) != row["sha256"] or size != (row["width"], row["height"]):
            raise ValueError(f"Invalid page bytes or dimensions: {row['id']}")
        if doc is not None:
            page = doc[row["pdf_index"]]
            img = page.render(scale=edition["render_width"] / page.get_width()).to_pil().convert("L")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            if buffer.getvalue() != data:
                raise ValueError(f"Original source rerender differs: {row['id']}")
    if doc is not None:
        doc.close()
    key = ROOT / "gold.jsonl"
    if key.exists():
        if sha256(key.read_bytes()) != (ROOT / "sealed.sha256").read_text().split()[0]:
            raise ValueError("Transcriptions differ from pre-inference commitment")
        dims = {r["id"]: (r["width"], r["height"]) for r in rows}
        references = [json.loads(line) for line in key.read_text().splitlines()]
        if len(references) != len({r["id"] for r in references}):
            raise ValueError("Reference IDs must be unique")
        for ref in references:
            for name, page in [("station_bbox","page_id"),("taxon_bbox","taxon_page_id")]:
                left, top, right, bottom = ref[name]
                width, height = dims[ref[page]]
                if not (0 <= left < right <= width and 0 <= top < bottom <= height):
                    raise ValueError(f"Box outside page in {ref['id']}")
    print(f"Verified {len(rows)} full-page scans.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, help="Path to the original PDF downloaded from the pinned URL.")
    verify(parser.parse_args().pdf)
