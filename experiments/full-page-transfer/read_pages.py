"""Apply the frozen TrOCR reader to every segment of a complete-page layout on Grace."""

import argparse
import json
import os
from pathlib import Path
import sys

from PIL import Image, ImageOps
import torch
import transformers

from layout import ROOT, rows, save

sys.path.insert(0, str(ROOT.parent / "grace-reader/pretrained"))
from fetch import MODELS, digest
from infer import reader


def run(pages_file, layout, weights, out):
    spec = MODELS["trocr"]
    folder = weights / "trocr" / spec["revision"]
    pretrained = {f: digest(folder / f) for f in spec["files"]}
    if pretrained["model.safetensors"] != spec["weights_sha256"]:
        raise ValueError("Unexpected TrOCR weights")
    pred = reader("trocr", folder)
    pages = {r["id"]: r for r in rows(pages_file)}
    lines = rows(layout)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    with torch.inference_mode():
        for key, page in pages.items():
            filepath = ROOT / page["image"]
            if digest(filepath) != page["sha256"]:
                raise ValueError(f"Changed page: {key}")
            with Image.open(filepath) as scan:
                for line in (line for line in lines if line["page"] == key):
                    guesses = []
                    for segment in line["segments"]:
                        pixels = scan.crop(segment["box"]).convert("RGB")
                        crop = ImageOps.expand(pixels, border=3, fill="white")
                        guesses.append(pred(crop))
                    results.append({"page": key, "line": line["line"], "segments": guesses})
            print(f"Completed {key}", flush=True)
    if len(results) != len(lines) or any(not any(r["page"] == page for r in results) for page in pages):
        raise ValueError("A page had no layout or some lines were not read")
    save(out / "readings.jsonl", results)
    receipt = {"model": spec["repo"], "revision": spec["revision"], "files": pretrained,
               "torch": str(torch.__version__), "transformers": transformers.__version__,
               "gpu": torch.cuda.get_device_name(0), "job": os.environ.get("SLURM_JOB_ID"),
               "page_manifest_sha256": digest(pages_file), "layout_sha256": digest(layout),
               "readings_sha256": digest(out / "readings.jsonl"), "lines": len(results),
               "segments": sum(len(r["segments"]) for r in results)}
    (out / "runtime.json").write_text(json.dumps(receipt, indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for item in ("pages", "layout", "weights", "out"):
        parser.add_argument(item, type=Path)
    args = parser.parse_args()
    run(args.pages, args.layout, args.weights, args.out)
