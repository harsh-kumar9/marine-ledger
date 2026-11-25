import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / "experiments/full-page-transfer"


def data(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


class FullPageTransferTest(unittest.TestCase):
    def test_transfer_inputs_and_frozen_predictions(self):
        receipt = json.loads((ROOT / "results/runtime.json").read_text())
        for key, path in (("layout_sha256","results/layout.jsonl"),("page_manifest_sha256","corpus/pages.jsonl"),
                          ("readings_sha256","results/readings.jsonl")):
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), receipt[key])
        for row in data(ROOT / "corpus/pages.jsonl"):
            self.assertEqual(hashlib.sha256((ROOT / row["image"]).read_bytes()).hexdigest(),row["sha256"])
        commitment = (ROOT / "corpus/sealed.sha256").read_text().split()[0]
        self.assertEqual(hashlib.sha256((ROOT / "corpus/gold.jsonl").read_bytes()).hexdigest(),commitment)
        with tempfile.TemporaryDirectory() as temp:
            pred = Path(temp) / "predictions.jsonl"
            for name in ("control", "results"):
                subprocess.run([sys.executable,"extract.py",f"{name}/layout.jsonl",f"{name}/readings.jsonl",str(pred)],
                               cwd=ROOT,check=True)
                self.assertEqual(pred.read_bytes(), (ROOT / name / "stations.jsonl").read_bytes())
        output = subprocess.check_output([sys.executable,"score.py"],cwd=ROOT)
        self.assertEqual(output, (ROOT / "results/scores.json").read_bytes())

    def test_every_reference_has_a_linked_review(self):
        sys.path.insert(0,str(ROOT))
        try:
            from casebook import build
            ledger = list(build())
        finally:
            sys.path.remove(str(ROOT))
        self.assertEqual(ledger, data(ROOT / "review/station-ledger.jsonl"))
        self.assertEqual({r["id"] for r in ledger},{r["id"] for r in data(ROOT / "corpus/gold.jsonl")})
