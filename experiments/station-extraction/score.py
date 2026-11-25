"""Score a page reader on station lines in the next three pages of Sturany."""
import argparse
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from pilot import extract


def triples(pages):
    if not isinstance(pages, dict):
        raise ValueError("expected page IDs mapped to binomials and station lists")
    result = set()
    for page, names in pages.items():
        for name, stations in names.items():
            if not name.strip() or not isinstance(stations, list) or any(type(s) != int or s < 1 for s in stations):
                raise ValueError("expected a binomial and an array of positive station numbers")
            result.update((page, name, s) for s in stations)
    return result


def parser_predictions(pages, text_dir, normalize):
    outputs = {}
    for page in pages:
        by_name = {}
        text = (text_dir / f"{page}.txt").read_text()
        if normalize:
            # Score binomials. Strip a printed subgenus only in a numbered heading.
            text = re.sub(r"^(\d+\. [A-Z][a-z]+) \([A-Z][a-z]+\) (?=[a-z]+\b)",
                          r"\1 ", text, flags=re.M)
            # A period in a parenthesized specimen count (e.g. "1 Ex.") does not end the list.
            text = re.sub(r"^Von (?:den )?Station(?:en)? .*$",
                          lambda m: re.sub(r"\([^()\n]*\)", "", m[0]), text, flags=re.M)
        for r in extract(text, int(page)):
            if not r["subfossil"]:
                by_name.setdefault(r["name"], []).append(r["station"])
        outputs[page] = by_name
    return outputs


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    source = cli.add_mutually_exclusive_group()
    source.add_argument("--predictions", type=Path, help="model output in the gold.json layout")
    source.add_argument("--ocr-dir", type=Path, default=HERE / "sources")
    cli.add_argument("--normalize", action="store_true", help="handle parenthesized subgenera and specimen counts")
    cli.add_argument("--gold", type=Path, default=HERE / "gold.json", help="scan-verified page set")
    args = cli.parse_args()
    labels = json.loads(args.gold.read_text())
    if args.predictions:
        predicted = json.loads(args.predictions.read_text())
    else:
        predicted = parser_predictions(labels, args.ocr_dir, args.normalize)
    if set(predicted) != set(labels):
        cli.error("provide every benchmark page exactly once; use {} for a page with no predictions")
    expected, actual = triples(labels), triples(predicted)
    tp = len(actual & expected)
    print(json.dumps({"correct": tp, "predicted": len(actual), "expected": len(expected),
                      "precision": round(tp / len(actual), 4) if actual else None,
                      "recall": round(tp / len(expected), 4),
                      "spurious": sorted(actual - expected), "missed": sorted(expected - actual)}, indent=2))


if __name__ == "__main__":
    main()
