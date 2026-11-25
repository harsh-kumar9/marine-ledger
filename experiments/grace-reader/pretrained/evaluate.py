"""Replay Ingolf reader selection and the retrospective Challenger comparison."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compare_ocr import metrics, normalize, read_rows, references


def luna_predictions():
    slots = read_rows(ROOT / "luna/packet/slots.jsonl")
    lookup = {row["slot"]: row for row in slots}
    if len(lookup) != len(slots):
        raise ValueError("Duplicate Luna packet slot")
    result = {"validation": {}, "test": {}}
    for reader in ("a", "b"):
        path = ROOT / f"luna/reads/{reader}.jsonl"
        readings = [json.loads(line) for line in path.read_text().splitlines()]
        if len(readings) != len(slots) or {r["slot"] for r in readings} != lookup.keys():
            raise ValueError(f"Incomplete or duplicate slots in {path}")
        for split in result:
            result[split][f"luna_{reader}"] = [
                {"id": lookup[r["slot"]]["id"], "text": r["text"]}
                for r in readings if lookup[r["slot"]]["split"] == split
            ]
    return result


def render(outputs):
    manifest = json.loads(Path(__file__).with_name("models.json").read_text())
    names = list(manifest)
    validation = references(read_rows(ROOT / "corpus/validation.jsonl"))
    validation_rows = {name: read_rows(outputs / f"{name}-validation.jsonl") for name in names}
    validation_scores = {name: metrics(validation, rows) for name, rows in validation_rows.items()}
    selected = min(names, key=lambda name: (-validation_scores[name]["correct"],
                                            validation_scores[name]["edits"], name != "paddle"))
    luna = luna_predictions()
    validation_rows.update(luna["validation"])
    validation_scores.update({name: metrics(validation, rows) for name, rows in luna["validation"].items()})
    configurations = json.loads((ROOT / "comparison/selection.json").read_text())
    baseline = next(trial for trial in configurations["trials"]
                    if all(trial[key] == val for key, val in configurations["selected"].items()))
    validation_scores["tesseract_single_line"] = {key: baseline[key] for key in validation_scores[selected]}

    gold = references(read_rows(ROOT / "corpus/test-gold.jsonl"))
    systems = {name: read_rows(outputs / f"{name}-test.jsonl") for name in names}
    systems.update(luna["test"])
    systems["tesseract_single_line"] = read_rows(ROOT / "comparison/ocr-selected-test.jsonl")
    test_scores = {name: metrics(gold, rows) for name, rows in systems.items()}
    decoded = {name: {r["id"]: normalize(r["text"]) for r in rows} for name, rows in systems.items()}
    by_id = []
    for key, target in gold.items():
        guesses = {name: preds[key] for name, preds in decoded.items()}
        if any(text != target for text in guesses.values()):
            by_id.append({"id": key, "reference": target, **guesses})
    correct = {name: {i for i in gold if pred[i] == gold[i]} for name, pred in decoded.items()}
    tess = correct["tesseract_single_line"]
    paired = {name: {"both_correct": len(correct[name] & tess), "reader_only": len(correct[name] - tess),
                     "tesseract_only": len(tess - correct[name]), "both_wrong": len(gold.keys() - (correct[name] | tess))}
              for name in [*names, *luna["test"]]}
    shared_errors = []
    for split, refs, rows in (("ingolf", validation, validation_rows), ("challenger", gold, systems)):
        answers = {name: {r["id"]: normalize(r["text"]) for r in rows[name]}
                   for name in ("luna_a", "luna_b", selected)}
        for key, target in refs.items():
            guess = answers["luna_a"][key]
            if guess == answers["luna_b"][key] and guess != target:
                shared_errors.append({"expedition": split, "id": key, "reference": target,
                                      "both_luna_readers": guess, selected: answers[selected][key]})
    return {"selected_on_ingolf": selected, "ingolf": validation_scores, "challenger": test_scores,
            "paired_challenger_vs_single_line_tesseract": paired, "challenger_errors": by_id,
            "shared_luna_errors": shared_errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", type=Path, default=Path(__file__).with_name("results"))
    args = parser.parse_args()
    print(json.dumps(render(args.outputs), indent=2))
