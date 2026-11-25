"""Find explicit station mentions in both transcripts, preserving line and segment location."""

import argparse
import re
from pathlib import Path
from layout import ROOT, bounds, rows, save


# "Sration" occurs twice on the known Challenger control with English Tesseract.
DESIGNATOR = re.compile(r"\b(?:stations?|srations?|stats?|stns?|st)[.\s:]+(\d{1,4}[a-z]?)\b", re.I)


def extract(layout, readings):
    neural = {(r["page"], r["line"]): r["segments"] for r in readings}
    if len(neural) != len(readings) or len(neural) != len(layout):
        raise ValueError("Duplicate or missing neural lines")
    for line in layout:
        key = (line["page"], line["line"])
        sources = {"tesseract": [s["text"] for s in line["segments"]], "trocr": neural[key]}
        for method, pieces in sources.items():
            if len(pieces) != len(line["segments"]):
                raise ValueError(f"Lost segment at {key}")
            text = " ".join(pieces)
            offsets = []
            pos = 0
            for segment, piece in zip(line["segments"], pieces):
                offsets.append((pos, pos+len(piece), segment))
                pos += len(piece)+1
            for match in DESIGNATOR.finditer(text):
                left, right = match.span(1)
                segments = [s for start, end, s in offsets if left < end and right > start]
                yield {"page": key[0], "line": key[1], "method": method,
                       "station": match.group(1).upper(), "box": bounds(segments),
                       "context": text}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("layout", "readings", "out"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    save(args.out, extract(rows(args.layout), rows(args.readings)))
