import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

BENCH = Path(__file__).resolve().parents[1] / "experiments/station-extraction"


class StationBenchmark(unittest.TestCase):
    def test_frozen_images_and_archive_ocr(self):
        manifest = json.loads((BENCH / "sources.json").read_text())
        for entry in manifest["inputs"]:
            data = (BENCH / entry["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"], entry["file"])

    def test_original_and_challenger_transfer_scores(self):
        for options, correct, total_predictions in [
            ([], 23, 25),
            (["--ocr-dir", "german-ocr", "--normalize"], 39, 39),
        ]:
            with self.subTest(options=options):
                raw = subprocess.check_output([sys.executable, "score.py", "--gold", "transfer.json", *options],
                                              cwd=BENCH)
                score = json.loads(raw)
                self.assertEqual((score["correct"], score["predicted"], score["expected"]),
                                 (correct, total_predictions, 53))
