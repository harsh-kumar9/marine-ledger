"""Reconcile a bounded Pola expedition sample using checked BHL, WoRMS and OBIS evidence."""

import argparse
import csv
import hashlib
import fcntl
import json
import os
import re
import shutil
import ssl
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
BHL = "https://www.biodiversitylibrary.org/page/"
OBIS = "https://obis.org/occurrence/"
HEADER = re.compile(r"^(?:\d+|o)\. ([A-Z][a-z]+ [a-z]+)\b[^\n]*", re.M)
STATION_LINE = re.compile(r"^Von (?:den )?Station(?:en)? ([^\n]+)", re.M)


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def checked_manifest(source):
    manifest = read_json(source / "manifest.json")
    baseline = read_json(DATA / "source" / "manifest.json")["files"]
    if set(manifest["files"]) != set(baseline):
        raise ValueError("Snapshot sources differ from this pilot's bounded corpus.")
    for name, item in manifest["files"].items():
        if item["url"] != baseline[name]["url"]:
            raise ValueError(f"Unexpected source URL for {name}")
        if name.endswith(".jp2") and item["sha256"] != baseline[name]["sha256"]:
            raise ValueError(f"Scan changed. Recheck control and station transcriptions for {name}.")
        if digest((source / name).read_bytes()) != item["sha256"]:
            raise ValueError(f"Checksum mismatch for {name}")
    return manifest


def fetch(out):
    """Refresh the fixed queries serially. Never mutate the checked-in reference."""
    if out.exists():
        raise ValueError("Choose a new snapshot directory.")
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(dir=out.parent))
    try:
        manifest = read_json(DATA / "source" / "manifest.json")
        tls = ssl.create_default_context()
        # Framework Python on macOS may lack an installed CA bundle.
        if sys.platform == "darwin" and Path("/etc/ssl/cert.pem").is_file():
            tls.load_verify_locations("/etc/ssl/cert.pem")
        for name, item in manifest["files"].items():
            request = Request(item["url"], headers={"User-Agent": "marine-ledger/0.1 (bounded archival research)"})
            with urlopen(request, context=tls, timeout=30) as response:
                raw = response.read(3_000_001)
            if len(raw) > 3_000_000:
                raise ValueError(f"Download exceeded pilot budget for {name}")
            if name.startswith("obis-"):
                complete_rows(json.loads(raw))
            item["sha256"] = digest(raw)
            (stage / name).write_bytes(raw)
        manifest["retrieved_utc_day"] = datetime.now(timezone.utc).date().isoformat()
        write_json(stage / "manifest.json", manifest)
        stage.rename(out)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def complete_rows(payload):
    rows = payload["results"]
    if not isinstance(rows, list) or len(rows) != payload["total"]:
        raise ValueError("Incomplete OBIS result. Split the query or use the bulk export.")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate row IDs in OBIS result.")
    return rows


def extract(text, page, corrections=()):
    """Only station lines beneath a numbered species heading support an association."""
    for change in corrections:
        if change["page"] == page:
            if text.count(change["old"]) != 1:
                raise ValueError(f"Scan correction anchor changed on page {page}")
            text = text.replace(change["old"], change["new"])
    found = []
    headings = list(HEADER.finditer(text))
    for i, head in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        account = text[head.end():end]
        attestation = STATION_LINE.search(account)
        if not attestation:
            continue
        quote = attestation.group().strip()
        # Remove depth expressions before reading numbers. A later clause may
        # contain counts, localities or literature comparisons.
        clause = re.sub(r"\([^)]*\)", "", attestation[1].split(";")[0].split(".")[0])
        numbers = re.match(r"[\d* ,]+(?:und [\d* ,]+)?", clause)
        if not numbers:
            continue
        for station in re.findall(r"\d+", numbers[0]):
            found.append({"name": head[1], "station": int(station), "page": page,
                          "heading": head[0].strip(), "station_text": quote,
                          "subfossil": "subfossil" in quote.lower()})
    return found


def matches(name, station, rows):
    def aliases(row):
        return {field.casefold() for field in (
            row.get("originalScientificName") or "", row.get("scientificName") or "",
            " ".join((row.get("verbatimIdentification") or "").split()[:2]))}
    return sorted((row for row in rows if row.get("locality") == f"station{station}"
                   and name.casefold() in aliases(row)), key=lambda row: row["id"])


def calibrate(source, catalog, corrections):
    key = read_json(DATA / "control-key.json")
    inventory, evaluated = [], []
    negatives = []
    for page in (key["development_page"], key["evaluation_page"]):
        text = (source / f"{page}.txt").read_text()
        records = extract(text, page, corrections)
        for record in records:
            hits = matches(record["name"], record["station"], catalog)
            record["comparison_ids"] = [row["occurrenceID"] for row in hits]
            record["comparison_urls"] = [OBIS + row["id"] for row in hits]
            record["state"] = ("excluded_subfossil" if record["subfossil"] else
                               "represented" if len(hits) == 1 else
                               "ambiguous" if hits else "unmatched_in_pola_subset")
            if page == key["evaluation_page"] and not record["subfossil"]:
                evaluated.append([record["name"], record["station"],
                                  hits[0]["occurrenceID"] if len(hits) == 1 else None])
            inventory.append(record)
        accepted = {r["name"] for r in records if not r["subfossil"]}
        for test in key["negatives"]:
            if test["page"] == page:
                negatives.append({**test, "passed": test["anchor"] in text and test["name"] not in accepted})
    expected = key["expected_evaluation_matches"]
    correct = sum(item in evaluated for item in expected)
    passed = sorted(evaluated, key=str) == sorted(expected, key=str) and all(item["passed"] for item in negatives)
    return {"gate_passed": passed, "expected_positive": len(expected), "correct_positive": correct,
            "evaluation_predictions": len(evaluated), "negative_controls": negatives,
            "associations": inventory}


def degree(parts):
    d, m, s = parts
    return round(d + m / 60 + s / 3600, 6)


def screen(row, checks):
    """Return plausible overlaps for review. Err toward retention on incomplete metadata."""
    taxon = row["aphiaID"]
    station = row["station"]
    overlaps = set()
    for name in [row["scientificName"], *row["verbatimIdentification"].split(" | ")]:
        overlaps.update(hit["id"] for hit in matches(name, station, checks["pola"]))
    for candidate in checks["pola"]:
        if candidate.get("aphiaID") == taxon and candidate.get("locality") == f"station{station}":
            overlaps.add(candidate["id"])
    # Every family hit in the local rectangle remains reviewable regardless of date.
    overlaps.update(hit["id"] for hit in checks["family-area"])
    for hit in checks["family-world"]:
        lat, lon = hit.get("decimalLatitude"), hit.get("decimalLongitude")
        if lat is None or lon is None or (31 <= lat <= 34 and 18 <= lon <= 22):
            overlaps.add(hit["id"])
    # This query includes different stations at the same coordinates and date.
    # Compare taxon or actual station, retaining unidentified organisms.
    for hit in checks["day-area"]:
        if (not hit.get("aphiaID") or hit["aphiaID"] == taxon or
                hit.get("locality") == f"station{station}"):
            overlaps.add(hit["id"])
    return sorted(overlaps)


def investigate(source, manifest, checks):
    study = read_json(DATA / "station-transcriptions.json")
    species_page, table_page = study["species_page"], study["station_page"]
    accounts = extract((source / f"{species_page}.txt").read_text(), species_page)
    by_event = {(r["station"], r["name"]): r for r in accounts}
    taxa = {}
    for path in sorted(source.glob("worms-*.json")):
        listing = read_json(path)
        if len(listing) != 1 or listing[0].get("rank") != "Species":
            raise ValueError(f"WoRMS name resolution requires review for {path.name}")
        name = listing[0]["scientificname"]
        taxa[name] = listing[0]

    rows, cases = [], []
    for event in study["stations"]:
        station = event["station"]
        grouped = defaultdict(list)
        for name in event["names"]:
            if (station, name) not in by_event:
                raise ValueError(f"Station table and species-account OCR disagree for {name} at {station}")
            grouped[taxa[name]["valid_AphiaID"]].append(name)
        for aphia_id, names in grouped.items():
            accepted = {taxa[n]["valid_name"] for n in names}
            if len(accepted) != 1:
                raise ValueError(f"Inconsistent accepted name for AphiaID {aphia_id}")
            row = {
                "id": f"pola-{station}-{aphia_id}", "station": station, "scientificName": accepted.pop(),
                "aphiaID": aphia_id, "scientificNameID": f"urn:lsid:marinespecies.org:taxname:{aphia_id}",
                "verbatimIdentification": " | ".join(names),
                "taxonRemarks": " | ".join(f"{n}: {taxa[n]['unacceptreason']}"
                                           for n in names if taxa[n].get("unacceptreason")),
                "eventDate": event["date"],
                "verbatimEventDate": event["verbatimEventDate"], "verbatimLatitude": event["verbatimLatitude"],
                "verbatimLongitude": event["verbatimLongitude"], "decimalLatitude": degree(event["latitude_dms"]),
                "decimalLongitude": degree(event["longitude_dms"]), "samplingProtocol": event["gear"],
                "occurrenceStatus": "present", "geodeticDatum": "", "catalogNumber": "",
                "references": f"{BHL}{table_page} | {BHL}{species_page}",
            }
            row["possible_obis_ids"] = " | ".join(screen(row, checks))
            row["review_status"] = "possible_overlap" if row["possible_obis_ids"] else "unmatched_in_frozen_checks"
            rows.append(row)
            evidence = [
                {"id":"station-table","source":BHL + str(table_page),
                 "detail":f"Printed p. 5, station {station}: {event['verbatimEventDate']}, {event['verbatimLatitude']}, {event['verbatimLongitude']}; {event['gear']} (surface net). Names transcribed from the scan: {', '.join(names)}. The geodetic datum is unspecified."},
            ]
            for i, name in enumerate(names, 1):
                account = by_event[(station, name)]
                evidence.append({"id":f"account-{i}","source":BHL + str(species_page),
                                 "detail":f"{account['heading']} {account['station_text']} (raw OCR line). The scan specifies eastern Mediterranean captures and explicitly excludes the Adriatic here."})
                status = taxa[name].get("unacceptreason") or taxa[name]["status"]
                evidence.append({"id":f"worms-{i}","source":taxa[name]["url"],
                                 "detail":f"WoRMS lists {name} as {status}, with accepted name {row['scientificName']} (AphiaID {aphia_id}). The station review groups names under that ID. Historical identifications and specimen counts remain unresolved."})
            for label, scope in [
                ("pola","Entire curated Pola Mollusken I dataset, a different report from the same expedition."),
                ("family-world","Worldwide Pterotracheidae, 1885 through 1900; records outside the station rectangle are retained in the snapshot."),
                ("family-area","Pterotracheidae with all dates in 18–22 E, 31–34 N, covering the stations."),
                ("day-area","All taxa in the same rectangle on the collecting date. Station 37 is a separate operation at the coordinates of station 38."),
            ]:
                evidence.append({"id":label,"source":manifest["files"][f"obis-{label}.json"]["url"],
                                 "detail":f"{len(checks[label])} matching rows in the query. {scope}"})
            evidence.append({"id":"overlap-screen","source":manifest["files"]["obis-day-area.json"]["url"],
                             "detail":f"Possible catalog row IDs under the declared comparisons: {row['possible_obis_ids'] or 'none'}. Missing or mistranscribed locality, taxonomy or date and uncatalogued physical lots can defeat this search."})
            cases.append({"id":row["id"],"question":f"Does the historical {row['scientificName']} sample at Pola station {station} duplicate an existing record, and what would establish its identity?", "evidence":evidence})
    return rows, cases


def replay(source, out):
    manifest = checked_manifest(source)
    checks = {label: complete_rows(read_json(source / f"obis-{label}.json"))
              for label in ("pola", "family-world", "family-area", "day-area")}
    score = calibrate(source, checks["pola"], read_json(DATA / "ocr-corrections.json"))
    rows, cases = investigate(source, manifest, checks) if score["gate_passed"] else ([], [])
    packet = {"gate_passed": score["gate_passed"], "cases": cases}
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out) as directory:
        stage = Path(directory)
        write_json(stage / "review_packet.json", packet)
        write_json(stage / "calibration.json", score)
        write_json(stage / "coverage.json", {"snapshot_day": manifest["retrieved_utc_day"],
                   "checks": {k: {"rows": len(v), "request": manifest["files"][f"obis-{k}.json"]["url"]} for k,v in checks.items()},
                   "review_units":len(rows), "candidate_status_counts":{
                       k: sum(r["review_status"] == k for r in rows) for k in sorted({r["review_status"] for r in rows})}})
        with (stage / "candidates.tsv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["id","review_status"],
                                    delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        # Promote the new gate last after all other files have been produced.
        for filename in ["calibration.json","coverage.json","candidates.tsv","review_packet.json"]:
            os.replace(stage / filename, out / filename)
    return score["gate_passed"], len(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    run = subcommands.add_parser("replay", help="Generate evidence and scores offline.")
    run.add_argument("--source", type=Path, default=DATA / "source")
    run.add_argument("--out", type=Path, default=ROOT / "results")
    refresh = subcommands.add_parser("fetch", help="Refresh the fixed public source list serially.")
    refresh.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "fetch":
        # Advisory locking the script requires no cache directory. Multiple
        # fetch processes from this checkout must not overlap on the OBIS API.
        with Path(__file__).open("rb") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                parser.exit(2, "Another fetch is active in this checkout. Retry when it finishes.\n")
            fetch(args.out)
        return 0
    passed, count = replay(args.source, args.out)
    print(f"Calibration {'passed' if passed else 'failed'}; {count} taxon–station cases for review.")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
