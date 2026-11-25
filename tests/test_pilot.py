import csv
import shutil
import tempfile
import unittest
from pathlib import Path

import pilot


class HistoricalPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = pilot.DATA / "source"

    def test_calibration_and_station_synonyms(self):
        out = self.root / "results"
        self.assertEqual(pilot.replay(self.source, out), (True, 3))
        score = pilot.read_json(out / "calibration.json")
        self.assertEqual((score["correct_positive"], score["evaluation_predictions"]), (8, 8))
        self.assertTrue(all(c["passed"] for c in score["negative_controls"]))
        candidates = list(csv.DictReader((out / "candidates.tsv").read_text().splitlines(), delimiter="\t"))
        card = next(r for r in candidates if r["id"] == "pola-41-139945")
        self.assertEqual(card["verbatimIdentification"], "Pterotrachea hippocampus | Pterotrachea mutica")
        self.assertIn("uncertain synonym", card["taxonRemarks"])
        self.assertEqual(card["eventDate"], "1890-09-06")
        self.assertEqual(card["catalogNumber"], "")

    def test_missing_positive_with_provenance_stops_gate_and_replaces_old_packet(self):
        source = self.root / "source"
        shutil.copytree(self.source, source)
        out = self.root / "out"
        pilot.replay(source, out)
        path = source / "obis-pola.json"
        data = pilot.read_json(path)
        data["results"] = [r for r in data["results"] if r.get("occurrenceID") != "Pola_Mollusca_98"]
        data["total"] = len(data["results"])
        pilot.write_json(path, data)
        manifest = pilot.read_json(source / "manifest.json")
        manifest["files"][path.name]["sha256"] = pilot.digest(path.read_bytes())
        pilot.write_json(source / "manifest.json", manifest)
        self.assertEqual(pilot.replay(source, out), (False, 0))
        self.assertEqual(pilot.read_json(out / "review_packet.json"), {"gate_passed": False,"cases":[]})

    def test_source_checksum_and_query_completeness(self):
        source = self.root / "source"
        shutil.copytree(self.source, source)
        (source / "32372962.txt").write_text("damaged")
        with self.assertRaisesRegex(ValueError, "Checksum"):
            pilot.checked_manifest(source)
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            pilot.complete_rows({"results": [], "total": 1})

    def test_scan_correction_is_local_and_auditable(self):
        page = 32372963
        text = (self.source / f"{page}.txt").read_text()
        corrections = pilot.read_json(pilot.DATA / "ocr-corrections.json")
        before = {r["station"] for r in pilot.extract(text, page) if r["name"] == "Trophon vaginatus"}
        after = {r["station"] for r in pilot.extract(text, page, corrections) if r["name"] == "Trophon vaginatus"}
        self.assertEqual((before, after), ({1, 218}, {1, 213}))
        with self.assertRaisesRegex(ValueError, "anchor"):
            pilot.extract("replacement OCR", page, corrections)

    def test_collision_on_date_and_coordinates_preserves_station_and_taxon(self):
        row = {"station":38, "aphiaID":139945, "scientificName":"Pterotrachea hippocampus",
               "verbatimIdentification":"Pterotrachea hippocampus"}
        checks = {key: [] for key in ["pola", "family-world", "family-area", "day-area"]}
        checks["day-area"] = pilot.complete_rows(pilot.read_json(self.source / "obis-day-area.json"))
        self.assertEqual(len(checks["day-area"]), 9)
        self.assertEqual(pilot.screen(row, checks), [])
        checks["day-area"].append({"id":"unresolved", "aphiaID":139945, "locality":"station37"})
        self.assertEqual(pilot.screen(row, checks), ["unresolved"])

    def test_any_local_family_overlap_is_retained_even_without_date(self):
        row = {"station":41, "aphiaID":139945, "scientificName":"Pterotrachea hippocampus",
               "verbatimIdentification":"Pterotrachea hippocampus | Pterotrachea mutica"}
        checks = {"pola":[], "family-world":[], "family-area":[{"id":"undated"}], "day-area":[]}
        self.assertEqual(pilot.screen(row, checks), ["undated"])
        checks["pola"].append({"id":"synonym","locality":"station41","originalScientificName":"Pterotrachea mutica"})
        self.assertEqual(pilot.screen(row, checks), ["synonym","undated"])


if __name__ == "__main__":
    unittest.main()
