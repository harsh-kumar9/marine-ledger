"""Predeclared Tesseract station-field baseline and expedition-macro metrics."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parent
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def normalize(value):
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def edit_distance(reference, prediction):
    previous = list(range(len(prediction) + 1))
    for i, char in enumerate(reference, 1):
        current = [i]
        for j, observed in enumerate(prediction, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (char != observed)))
        previous = current
    return previous[-1]


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def score(gold, predictions):
    ref = {r["id"]: r for r in gold}
    pred = {r["id"]: normalize(r["text"]) for r in predictions}
    if not ref or len(ref) != len(gold) or len(pred) != len(predictions) or ref.keys() != pred.keys():
        raise ValueError("Scores require nonempty identical ID sets with one prediction per field.")

    by_expedition = defaultdict(list)
    for item in gold:
        target = normalize(item["text"])
        if not target:
            raise ValueError(f"Empty reference for {item['id']}")
        by_expedition[item["expedition"]].append((target, pred[item["id"]]))

    counts = {}
    for expedition, pairs in sorted(by_expedition.items()):
        exact = sum(reference == candidate for reference, candidate in pairs)
        characters = sum(len(reference) for reference, _ in pairs)
        edits = sum(edit_distance(reference, candidate) for reference, candidate in pairs)
        lengths = {}
        for length in sorted({len(reference) for reference, _ in pairs}):
            group = [(ref, pred) for ref, pred in pairs if len(ref) == length]
            lengths[str(length)] = {"exact": sum(ref == pred for ref, pred in group), "n": len(group)}
        counts[expedition] = {"exact": exact, "n": len(pairs), "exact_accuracy": exact / len(pairs),
                              "edits": edits, "characters": characters, "cer": edits / characters,
                              "by_target_length": lengths}
    return {"macro_exact_accuracy": sum(r["exact_accuracy"] for r in counts.values()) / len(counts),
            "macro_cer": sum(r["cer"] for r in counts.values()) / len(counts), "expeditions": counts}


def predict(records, tessdata):
    # Tesseract receives each original PNG. Its built-in preprocessing is part
    # of this reference algorithm. PSM/OEM/language were fixed before scoring.
    results = []
    params = ["-l", "eng", "--oem", "1", "--psm", "8", "-c", f"tessedit_char_whitelist={ALPHABET}"]
    if tessdata:
        params.extend(["--tessdata-dir", str(tessdata)])
    for row in records:
        image = ROOT / row["image"]
        run = subprocess.run(["tesseract", str(image), "stdout", *params],
                             text=True, check=True, capture_output=True)
        results.append({"id": row["id"], "text": normalize(run.stdout)})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    run = commands.add_parser("predict")
    run.add_argument("--manifest", required=True, type=Path)
    run.add_argument("--out", required=True, type=Path)
    run.add_argument("--tessdata", type=Path)
    evaluate = commands.add_parser("score")
    evaluate.add_argument("--gold", required=True, type=Path)
    evaluate.add_argument("--predictions", required=True, type=Path)
    evaluate.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.action == "predict":
        records = read_jsonl(args.manifest)
        predictions = predict(records, args.tessdata)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in predictions))
        return
    report = json.dumps(score(read_jsonl(args.gold), read_jsonl(args.predictions)), indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
