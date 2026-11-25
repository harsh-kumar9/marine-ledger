import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / "experiments/grace-reader"


class GraceTransferTest(unittest.TestCase):
    def test_seal_weights_and_corpus(self):
        def digest(path):
            return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

        freeze = json.loads((ROOT / "run/freeze.json").read_text())
        for split in ("train", "validation"):
            self.assertEqual(digest(f"corpus/{split}.jsonl"), freeze[f"{split}_manifest_sha256"])
        self.assertEqual(digest("corpus/test-gold.jsonl"), (ROOT / "corpus/sealed.sha256").read_text().split()[0])
        for stage in ("synthetic", "adapted"):
            self.assertEqual(digest(f"run/{stage}.pt"), freeze["checkpoint_sha256"][stage])
        seen_expeditions = set()
        seen_images = set()
        for split in ("train", "validation", "test"):
            rows = [json.loads(line) for line in (ROOT / f"corpus/{split}.jsonl").read_text().splitlines()]
            expeditions = {row["expedition"] for row in rows}
            images = {digest(row["image"]) for row in rows}
            self.assertTrue(seen_expeditions.isdisjoint(expeditions))
            self.assertTrue(seen_images.isdisjoint(images))
            seen_expeditions.update(expeditions)
            seen_images.update(images)

    def test_paired_scores_match_saved_results(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "results.json"
            subprocess.run([sys.executable, "compare_ocr.py", "paired",
                            "--gold", "corpus/test-gold.jsonl", "--inputs", "corpus/test.jsonl",
                            "--tuned", "run/adapted-test.jsonl", "--untuned", "run/synthetic-test.jsonl",
                            "--baseline", "primary-ocr/test.jsonl", "--challenger", "comparison/ocr-selected-test.jsonl",
                            "--out", str(out)], cwd=ROOT, check=True)
            self.assertEqual(out.read_bytes(), (ROOT / "comparison/test-scores.json").read_bytes())
