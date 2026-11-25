"""Detect text throughout each full page and prepare short, automatically located lines."""

import argparse
from collections import defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def save(path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items))


def bounds(words):
    return [min(w["box"][0] for w in words), min(w["box"][1] for w in words),
            max(w["box"][2] for w in words), max(w["box"][3] for w in words)]


def chunks(words):
    group = []
    for word in words:
        if group and (len(group) == 4 or len(" ".join(w["text"] for w in [*group, word])) > 26):
            yield group
            group = []
        group.append(word)
    if group:
        yield group


def analyze(page):
    path = ROOT / page["image"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != page["sha256"]:
        raise ValueError(f"Scan checksum changed for {path}")
    tsv = subprocess.check_output(["tesseract", str(path), "stdout", "-l", "eng", "--oem", "1",
                                   "--psm", "3", "tsv"], text=True)
    lines = defaultdict(list)
    for w in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if w["level"] == "5" and w["text"].strip():
            key = tuple(w[k] for k in ("block_num", "par_num", "line_num"))
            x, y, width, height = (int(w[k]) for k in ("left", "top", "width", "height"))
            lines[key].append({"text": w["text"], "box": [x, y, x+width, y+height]})
    for index, words in enumerate(lines.values(), 1):
        segments = [{"box": bounds(group), "text": " ".join(w["text"] for w in group)}
                    for group in chunks(words)]
        yield {"page": page["id"], "line": index, "box": bounds(words), "segments": segments}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    save(args.out, (line for page in rows(args.pages) for line in analyze(page)))
