"""Choose an OCR configuration on Ingolf and compare paired predictions on Challenger."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
CONFIGS = [(8, False), (7, False), (8, True), (7, True)]
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def read_rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows or len({row["id"] for row in rows}) != len(rows):
        raise ValueError(f"empty file or duplicate IDs in {path}")
    return rows


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def normalize(text):
    return re.sub("[^0-9A-Za-z]", "", text).upper()


def distance(a, b):
    last = list(range(len(b) + 1))
    for i, char in enumerate(a, 1):
        row = [i]
        for j, other in enumerate(b, 1):
            row.append(min(last[j] + 1, row[j-1] + 1, last[j-1] + (char != other)))
        last = row
    return last[-1]


def references(rows):
    result = {r["id"]: normalize(r["text"]) for r in rows}
    if not all(result.values()):
        raise ValueError("empty reference")
    return result


def metrics(refs, predictions):
    guesses = {p["id"]: normalize(p["text"]) for p in predictions}
    if len(guesses) != len(predictions) or refs.keys() != guesses.keys():
        raise ValueError("predictions and references must have identical unique IDs")
    errors = sum(distance(text, guesses[i]) for i, text in refs.items())
    chars = sum(map(len, refs.values()))
    return {"correct": sum(text == guesses[i] for i, text in refs.items()), "cells": len(refs),
            "edits": errors, "reference_characters": chars, "cer": errors / chars}


def predict(rows, psm, enlarge):
    guesses = []
    for row in rows:
        path = ROOT / row["image"]
        image = path.read_bytes()
        if enlarge:
            image = subprocess.run(["magick", "-", "-colorspace", "Gray", "-auto-level", "-filter",
                                    "Lanczos", "-resize", "x72", "-bordercolor", "white", "-border",
                                    "10x10", "png:-"], input=image, stdout=subprocess.PIPE, check=True).stdout
        proc = subprocess.run(["tesseract", "stdin", "stdout", "-l", "eng", "--oem", "1", "--psm",
                               str(psm), "-c", "tessedit_char_whitelist=" + ALPHABET],
                              input=image, capture_output=True)
        if proc.returncode:
            raise ValueError(f"OCR failed on {row['id']}: {proc.stderr.decode(errors='replace')}")
        guesses.append({"id": row["id"], "text": proc.stdout.decode().strip()})
    return guesses


def tune(args):
    rows = read_rows(args.validation)
    if {r["expedition"].casefold() for r in rows} != {"ingolf"}:
        raise ValueError("configuration selection requires the Ingolf validation set")
    refs = references(rows)
    trials = []
    for psm, enlarge in CONFIGS:
        scores = metrics(refs, predict(rows, psm, enlarge))
        trials.append({"psm": psm, "enlarge": enlarge, **scores})
    best = min(trials, key=lambda t: (-t["correct"], t["edits"]))
    result = {"selection_manifest_sha256": hashlib.sha256(args.validation.read_bytes()).hexdigest(),
              "tesseract": subprocess.check_output(["tesseract", "--version"], text=True).splitlines()[0],
              "imagemagick": subprocess.check_output(["magick", "--version"], text=True).splitlines()[0],
              "trials": trials, "selected": {"psm": best["psm"], "enlarge": best["enlarge"]}}
    save(args.out, result)
    print(json.dumps(result["selected"]))


def infer(args):
    config = json.loads(args.selection.read_text())["selected"]
    rows = read_rows(args.inputs)
    if any("text" in r for r in rows):
        raise ValueError("inference requires an unlabeled manifest")
    guesses = predict(rows, **config)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(row) + "\n" for row in guesses))


def paired(args):
    gold = read_rows(args.gold)
    refs = references(gold)
    inputs = read_rows(args.inputs)
    if {r["id"] for r in inputs} != refs.keys():
        raise ValueError("unlabeled manifest and key cover different cells")
    systems = {"tuned": args.tuned, "ocr_primary": args.baseline, "ocr_selected": args.challenger,
               "before_adaptation": args.untuned}
    scores, exact = {}, {}
    for name, path in systems.items():
        rows = read_rows(path)
        scores[name] = metrics(refs, rows)
        exact[name] = {r["id"] for r in rows if normalize(r["text"]) == refs[r["id"]]}
        scores[name]["correct_by_reference_length"] = dict(sorted(
            Counter(len(refs[i]) for i in exact[name]).items()
        ))
    comparisons = {}
    for name in ("before_adaptation", "ocr_primary", "ocr_selected"):
        a, b = exact["tuned"], exact[name]
        comparisons[name] = {"both_correct": len(a & b), "tuned_only": len(a - b),
                             "comparator_only": len(b - a), "both_wrong": len(refs) - len(a | b)}
    save(args.out, {"distinct_station_ids": len(set(refs.values())),
                    "reference_length_counts": dict(sorted(Counter(map(len, refs.values())).items())),
                    "scores": scores, "paired_against_tuned": comparisons})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(required=True)
    t = commands.add_parser("select")
    t.add_argument("--validation", type=Path, default=ROOT / "corpus/validation.jsonl")
    t.add_argument("--out", type=Path, required=True)
    t.set_defaults(fn=tune)
    p = commands.add_parser("predict")
    p.add_argument("--selection", type=Path, required=True)
    p.add_argument("--inputs", type=Path, default=ROOT / "corpus/test.jsonl")
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(fn=infer)
    s = commands.add_parser("paired")
    for arg in ("gold", "inputs", "tuned", "untuned", "baseline", "challenger", "out"):
        s.add_argument("--" + arg, required=True, type=Path)
    s.set_defaults(fn=paired)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
