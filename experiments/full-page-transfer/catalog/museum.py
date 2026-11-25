"""Query the Naturalis source system with bounded, control-checked expedition and date filters."""
import hashlib
import json
import subprocess
from queries import args, dump, get, GBIF, ROOT, subset

BASE = "https://api.biodiversitydata.nl/v2/"
GENERA = ["Cymatium", "Turritriton", "Reticutriton", "Septa", "Monoplex", "Distorsio",
          "Lotoria", "Gutturnium", "Aquillus", "Distortrix", "Triton"]
CASES = json.loads((ROOT / "label-readings.json").read_text())


def search(field, operator, value, genera):
    conditions = [{"field": "identifications.defaultClassification.genus", "operator": "IN", "value": genera},
                  {"field": field, "operator": operator, "value": value}]
    query = json.dumps({"conditions": conditions, "size": 100}, separators=(",", ":"))
    return get(BASE + "specimen/query/", _querySpec=query)


def picture(ref, expected):
    url = ref["accessUri"]
    ident = url.split("/id/")[1].split("/")[0]
    rights_request, rights = get(BASE + "multimedia/find/" + ident + "@CRS")
    info = {"url": url, "rights_request": rights_request, **subset(rights, ["owner", "license"])}
    if rights.get("license") != "CC0 1.0":
        return info
    path = ROOT / "labels" / (ident + ".jpg")
    if not path.exists():
        if not args.fetch:
            raise RuntimeError(f"Missing {path.name}")
        path.parent.mkdir(exist_ok=True)
        subprocess.run(["curl", "-fsSL", "--max-time", "30", "--retry", "2", url, "-o", str(path)], check=True)
    contents = path.read_bytes()
    digest = hashlib.sha256(contents).hexdigest()
    if not contents.startswith(b"\xff\xd8\xff") or digest != expected[url]:
        raise ValueError(f"Photograph differs from the visually reviewed image: {path.name}")
    return dict(info, local=str(path.relative_to(ROOT)), sha256=digest)


def main():
    audit = {}
    related = {}
    for name, field, op, value, genera in [
        ("target_collector", "gatheringEvent.gatheringPersons.fullName", "MATCHES", "Siboga", GENERA),
        ("target_indexed_date", "gatheringEvent.dateTimeBegin", "BETWEEN", ["1899-01-01", "1900-12-31"], GENERA),
        ("target_project", "gatheringEvent.projectTitle", "MATCHES", "Siboga", GENERA),
        ("target_previous_source", "previousSourceID", "MATCHES", "Siboga", GENERA),
        ("control_project", "gatheringEvent.projectTitle", "MATCHES", "Siboga", ["Cephalodiscus"]),
    ]:
        key, data = search(field, op, value, genera)
        rows = [r["item"] for r in data["resultSet"]]
        audit[name] = {"request": key, "total": data["totalSize"], "returned": len(rows),
                       "truncated": len(rows) < data["totalSize"], "unit_ids": [r["unitID"] for r in rows],
                       "null_indexed_date": sum(not r.get("gatheringEvent", {}).get("dateTimeBegin") for r in rows),
                       "null_site_coordinates": sum(not r.get("gatheringEvent", {}).get("siteCoordinates") for r in rows)}
        if name.startswith("target_"):
            related.update({r["unitID"]:r for r in rows})
    details = []
    for ident, record in sorted(related.items()):
        key, detailed = get(BASE + "specimen/findByUnitID/" + ident)
        row = next(r for r in detailed if r["id"] == record["id"])
        entry = {"unit": ident, "url": row["unitGUID"], "request": key,
                 "museum_count": row.get("numberOfSpecimen"), "event": row.get("gatheringEvent"),
                 "identifications": [dict(name=r["scientificName"]["fullScientificName"],
                                          preferred=r.get("preferred")) for r in row["identifications"]],
                 "label_read": CASES.get(ident)}
        if ident in CASES:
            entry["photographs"] = [picture(ref, CASES[ident]["source_image_sha256"])
                                    for ref in row["associatedMultiMediaUris"]]
        ref, reported = get(GBIF + "occurrence/search", occurrenceID=row["unitGUID"], limit=10)
        entry["gbif_provider_id_lookup"] = {
            "request": ref, "total": reported["count"], "truncated": reported["count"] > len(reported["results"]),
            "records": [dict(subset(r, ("key","scientificName","eventDate","verbatimEventDate","fieldNumber",
                             "eventID","locality","recordedBy","occurrenceID")),
                             url="https://www.gbif.org/occurrence/" + str(r["key"])) for r in reported["results"]]}
        details.append(entry)
    key, control = get(BASE + "specimen/findByUnitID/ZMA.COEL.4855")
    control = control[0]
    dump(ROOT / "museum.json", {"queries": audit, "vouchers": details, "positive_control": {
        "request": key, "url": control["unitGUID"], "event": control["gatheringEvent"],
        "comparison": "Siboga Exped. stat. 089, 11 m, 21-06-1899 and Pulu Kaniungan Ketjil independently agree with the 1902 printed station register. No decimal coordinates in museum event."
    }})


if __name__ == "__main__":
    main()
