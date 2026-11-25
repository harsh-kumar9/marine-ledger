"""Verify frozen input hashes and optionally re-render all 213 crops from original scans."""

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path

CORPUS = Path(__file__).resolve().parent
EXPERIMENT = CORPUS.parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest():
    provenance = json.loads((CORPUS / "provenance.json").read_text())
    seen_ids, editions = set(), {}
    for split in ("train", "validation", "test"):
        rows = [json.loads(line) for line in (CORPUS / f"{split}.jsonl").read_text().splitlines()]
        for row in rows:
            case = row["id"]
            source = provenance[case]
            if case in seen_ids or editions.setdefault(source["edition"], split) != split:
                raise ValueError("Repeated identifier or expedition overlap across splits")
            if (split == "test") == ("text" in row):
                raise ValueError(f"Incorrect label visibility in {split}")
            path = EXPERIMENT / row["image"]
            if source["sha256"] != sha256(path) or path.stem != case:
                raise ValueError(f"Unverified image {case}")
            seen_ids.add(case)
    if seen_ids != set(provenance) or seen_ids != {p.stem for p in (CORPUS / "images").glob("*.png")}:
        raise ValueError("Unused or missing source fields or images")
    return provenance


def rebuild(provenance, cache):
    from PIL import Image
    import pypdfium2 as pdfium

    editions = json.loads((CORPUS / "editions.json").read_text())
    for edition, info in editions.items():
        pdf = None
        if "download_url" in info:
            path = cache / Path(info["download_url"]).name
            if sha256(path) != info["sha256"]:
                raise ValueError(f"Original PDF mismatch: {edition}")
            pdf = pdfium.PdfDocument(path)
        selected = [(case, src) for case, src in provenance.items() if src["edition"] == edition]
        for index in sorted({s["page_index"] for _, s in selected}):
            if pdf is None:
                source = info["individual_scans"][str(index)]
                path = cache / Path(source["url"]).name
                if sha256(path) != source["sha256"]:
                    raise ValueError(f"Original scan mismatch: {path}")
                with Image.open(path) as original:
                    height = round(1800 * original.height / original.width)
                    page = original.resize((1800, height), Image.Resampling.LANCZOS).convert("L")
            else:
                original = pdf[index]
                page = original.render(scale=1800 / original.get_width()).to_pil().convert("L")
            for case, src in selected:
                if src["page_index"] == index:
                    buf = BytesIO()
                    page.crop(src["crop_xyxy"]).save(buf, format="PNG")
                    if hashlib.sha256(buf.getvalue()).hexdigest() != src["sha256"]:
                        raise ValueError(f"Rerender mismatch: {case}")
        if pdf is not None:
            pdf.close()


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--scan-cache", type=Path, help="Directory with the original downloads under their URL basenames")
    args = cli.parse_args()
    fields = verify_manifest()
    if args.scan_cache:
        rebuild(fields, args.scan_cache)
    print(f"Verified {len(fields)} station-field crops.")
