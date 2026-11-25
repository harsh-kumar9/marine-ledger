"""Score exact station mentions in place, with one-to-one matching on page and position."""

import argparse
from collections import Counter
import json
from pathlib import Path
from layout import ROOT, rows


def contains_center(region, target):
    x = (target[0]+target[2])/2
    y = (target[1]+target[3])/2
    return region[0] <= x < region[2] and region[1] <= y < region[3]


def match(gold, guesses):
    # Maximum one-to-one matching. Repeated station IDs in nearby prose are
    # independent mentions even when several labels lie on the same printed line.
    candidates = [[g["id"] for g in gold if g["page_id"] == p["page"] and
                   g["station"].upper() == p["station"].upper() and contains_center(p["box"],g["station_bbox"])]
                  for p in guesses]
    owners = {}

    def assign(index, visited):
        for key in candidates[index]:
            if key in visited:
                continue
            visited.add(key)
            if key not in owners or assign(owners[key], visited):
                owners[key] = index
                return True
        return False

    for index in range(len(guesses)):
        assign(index, set())
    return owners


def report(gold, predictions):
    if not gold or len({g["id"] for g in gold}) != len(gold):
        raise ValueError("Invalid reference IDs")
    methods = ("tesseract","trocr")
    if set(p["method"] for p in predictions) - set(methods):
        raise ValueError("Unknown prediction method")
    output = {"gold_mentions":len(gold), "methods":{}, "paired":{}}
    correct = {}
    for method in methods:
        guesses = [p for p in predictions if p["method"] == method]
        owners = match(gold, guesses)
        correct[method] = set(owners)
        unpaired = set(range(len(guesses))) - set(owners.values())
        counts = Counter(g["kind"] for g in gold)
        hits = Counter(g["kind"] for g in gold if g["id"] in owners)
        output["methods"][method] = {
            "proposed":len(guesses), "correct":len(owners), "precision":len(owners)/len(guesses) if guesses else None,
            "recall":len(owners)/len(gold), "by_kind":{s:{"correct":hits[s],"total":n} for s,n in counts.items()},
            "matches": {g["id"]:guesses[owners[g["id"]]]["line"] for g in gold if g["id"] in owners},
            "false_positives":[guesses[i] for i in sorted(unpaired)],
            "missed_ids":[g["id"] for g in gold if g["id"] not in owners],
        }
    for label, keys in (("both",correct["tesseract"] & correct["trocr"]),
                        ("only_tesseract",correct["tesseract"]-correct["trocr"]),
                        ("only_trocr",correct["trocr"]-correct["tesseract"]),
                        ("neither",{g["id"] for g in gold}-correct["trocr"]-correct["tesseract"])):
        output["paired"][label] = sorted(keys)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=ROOT / "corpus/gold.jsonl")
    parser.add_argument("--predictions", type=Path, default=ROOT / "results/stations.jsonl")
    args = parser.parse_args()
    print(json.dumps(report(rows(args.gold),rows(args.predictions)),indent=2))
