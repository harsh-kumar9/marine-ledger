"""Replay cached public taxon and occurrence queries, or acquire missing responses serially."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
WORMS = "https://www.marinespecies.org/rest/"
OBIS = "https://api.obis.org/v3/occurrence"
GBIF = "https://api.gbif.org/v1/"
REGION = "POLYGON ((92 -13,143 -13,143 12,92 12,92 -13))"
FIELDS = "id,dataset_id,occurrenceID,scientificName,originalScientificName,aphiaID,decimalLatitude,decimalLongitude,eventDate,locality,fieldNumber,verbatimLocality,recordedBy,eventID,catalogNumber,occurrenceRemarks,eventRemarks,verbatimEventDate,absence,institutionCode,collectionCode,coordinateUncertaintyInMeters"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--fetch", action="store_true", help="GET missing snapshots, serially")
args = parser.parse_args()
manifest_path = ROOT / "requests.json"
requests = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}


def dump(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def get(url, **params):
    if params:
        url += "?" + urlencode(params)
    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    path = RAW / (key + ".gz")
    if key not in requests:
        if not args.fetch:
            raise RuntimeError(f"Missing cached request {url}")
        RAW.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile() as response:
            result = subprocess.run(["curl", "--silent", "--show-error", "--location", "--max-time", "35",
                                     "--retry", "2", "--user-agent", "MarineLedger-scientific-pilot/0.1",
                                     "-o", response.name, "-w", "%{http_code}", url], check=True,
                                    capture_output=True, text=True)
            raw = Path(response.name).read_bytes()
        status = int(result.stdout)
        if status not in (200, 204):
            raise RuntimeError(f"{status} {url}: {raw[:240]!r}")
        if status == 200:
            json.loads(raw)
        path.write_bytes(gzip.compress(raw, mtime=0))
        requests[key] = {"url": url, "utc": datetime.now(timezone.utc).isoformat(),
                         "http_status": status, "sha256_raw": hashlib.sha256(raw).hexdigest()}
        dump(manifest_path, requests)
        print(key, status, url, flush=True)
        time.sleep(0.22)
    raw = gzip.decompress(path.read_bytes())
    if requests[key]["url"] != url or hashlib.sha256(raw).hexdigest() != requests[key]["sha256_raw"]:
        raise ValueError(f"Invalid cached response for {url}")
    return key, json.loads(raw) if raw else None


def exact(name):
    return get(WORMS + "AphiaRecordsByName/" + quote(name, safe=""), like="false", marine_only="true")


def taxon(case):
    hits = []
    for name in case["forms"]:
        key, records = exact(name)
        candidates = [r for r in records or [] if r["scientificname"].casefold() == name.casefold()
                      and r["class"] == "Gastropoda" and case["author"].casefold() in (r["authority"] or "").casefold()]
        hits.append({"query_name": name, "request": key, "returned": len(records or []),
                     "matching_ids": [r["AphiaID"] for r in candidates],
                     "other_names": [{k:r.get(k) for k in ("scientificname", "authority", "AphiaID", "valid_name", "valid_AphiaID")}
                                     for r in records or [] if r not in candidates]})
        if len({r["valid_AphiaID"] for r in candidates}) == 1 and candidates[0]["valid_AphiaID"]:
            hit = candidates[0]
            key, valid = get(WORMS + "AphiaRecordByAphiaID/" + str(hit["valid_AphiaID"]))
            return {"queries": hits, "matching_name": hit["scientificname"], "matching_author": hit["authority"],
                    "matching_status": hit["status"], "matching_id": hit["AphiaID"], "accepted_request": key,
                    "accepted": valid["scientificname"], "accepted_author": valid["authority"],
                    "accepted_status": valid["status"], "aphia_id": valid["AphiaID"], "url": valid["url"],
                    "basis": "historical name" if name == case["forms"][0] else "author-matched alternative combination; subject to historical concept review"}
    if "disputed_form" in case:
        _, alternatives = exact(case["disputed_form"])
        if len(alternatives or []) == 1:
            candidate = alternatives[0]
            key, accepted = get(WORMS + "AphiaRecordByAphiaID/" + str(candidate["valid_AphiaID"]))
            return {"queries": hits, "basis": "AUTHOR CONFLICT: sensitivity query only",
                    "matching_name": candidate["scientificname"], "matching_author": candidate["authority"],
                    "matching_status": candidate["status"], "matching_id": candidate["AphiaID"],
                    "accepted_request": key, "accepted": accepted["scientificname"],
                    "accepted_author": accepted["authority"], "accepted_status": accepted["status"],
                    "aphia_id": accepted["AphiaID"], "url": accepted["url"]}
    return {"queries": hits, "basis": "no author-verified species match"}


def subset(row, fields):
    return {field: row.get(field) for field in fields}


OCC_FIELDS = ("occurrenceID", "eventID", "fieldNumber", "eventDate", "scientificName", "locality",
              "verbatimLocality", "recordedBy", "catalogNumber", "decimalLatitude", "decimalLongitude",
              "occurrenceRemarks", "eventRemarks", "verbatimEventDate", "locationID")
STATION = re.compile(r"\b(?:stations?|sta?t?|stn)\s*[.\-:#]?\s*(\d+)([a-z]?)\b", re.I)


def audit(key, data, gbif, stations, list_history=False):
    rows = data["results"]
    total = data["count"] if gbif else data["total"]
    links = []
    for r in rows:
        searchable = " | ".join(str(r.get(f) or "") for f in OCC_FIELDS)
        ship = bool(re.search(r"\bsiboga\b", searchable, re.I))
        found = sorted({str(int(x)) + suffix.upper() for x, suffix in STATION.findall(searchable)})
        agreement = sorted(set(found).intersection(stations)) if ship else []
        if ship or agreement:
            links.append({"url": ("https://www.gbif.org/occurrence/" + str(r["key"]) if gbif else
                                  "https://obis.org/occurrence/" + str(r["id"])),
                          "explicit_stations": found, "target_station_overlap": agreement,
                          "fields": {k:v for k,v in subset(r, OCC_FIELDS).items() if v is not None}})
    report = {"request": key, "total": total, "returned": len(rows), "truncated": len(rows) < total,
            "null_or_blank_in_returned": {f: sum(r.get(f) in (None, "") for r in rows) for f in
                                          ("eventDate","decimalLatitude","decimalLongitude","fieldNumber","eventID","locality")},
            "siboga_text_records": links}
    if list_history:
        report["returned_record_context"] = [subset(r, ("key","id","occurrenceID","datasetName","country","locality",
                                                       "fieldNumber","eventID","eventDate","recordedBy")) for r in rows]
    return report


def occurrence(taxon_result, stations):
    ident = taxon_result["aphia_id"]
    result = {}
    key, data = get(OBIS, taxonid=ident, startdate="1899-01-01", enddate="1900-12-31", size=100, fields=FIELDS)
    result["obis_global_expedition_years"] = audit(key, data, False, stations)
    key, data = get(OBIS, taxonid=ident, geometry=REGION, size=100, fields=FIELDS)
    result["obis_regional_all_years"] = audit(key, data, False, stations)
    key, data = get(GBIF + "species/match", name=taxon_result["accepted"], kingdom="Animalia")
    result["gbif_match"] = {"request":key, **subset(data, ["matchType", "confidence", "canonicalName", "usageKey", "acceptedUsageKey","status"])}
    if data.get("matchType") == "EXACT" and data.get("canonicalName","").casefold() == taxon_result["accepted"].casefold():
        taxon_key = data.get("acceptedUsageKey") or data["usageKey"]
        key, data = get(GBIF + "occurrence/search", taxonKey=taxon_key, q="Siboga", limit=100)
        result["gbif_siboga_all_years"] = audit(key, data, True, stations)
        key, data = get(GBIF + "occurrence/search", taxonKey=taxon_key, year="1899,1900", limit=100)
        result["gbif_global_expedition_years"] = audit(key, data, True, stations, list_history=True)
    return result


def main():
    cases = json.loads((ROOT / "candidates.json").read_text())
    pages = {r["printed_page"]: r for r in map(json.loads, (ROOT.parent / "corpus/pages.jsonl").read_text().splitlines())}
    key, positive = get(WORMS + "AphiaRecordByAphiaID/266750")
    control = {"accepted": positive["scientificname"], "aphia_id": positive["AphiaID"], "request": key}
    control["occurrence"] = occurrence(control, ["88", "89"])
    _, specimen = get(GBIF + "occurrence/2442739280")
    control["published_gbif_voucher"] = subset(specimen, OCC_FIELDS)
    control["shared_occurrence_id"] = specimen["occurrenceID"]
    control["register"] = json.loads((ROOT / "register.json").read_text())
    dump(ROOT / "control.json", control)
    results = []
    for case in cases:
        tx = taxon(case)
        page = pages[case["page"]]
        packet = dict(case, taxonomy=tx, source_page=page["source_url"], source_image_sha256=page["sha256"])
        if "aphia_id" in tx:
            packet["occurrence"] = occurrence(tx, case["stations"])
        results.append(packet)
    dump(ROOT / "packets.json", results)


if __name__ == "__main__":
    main()
