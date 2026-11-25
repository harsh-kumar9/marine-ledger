"""Join the unsealed scan evidence, blind readings and catalog packets for each station mention."""

import json
from pathlib import Path
import re
from layout import ROOT, rows, save


def build():
    packets = {r["id"]: r for r in json.loads((ROOT / "catalog/packets.json").read_text())}
    audit = {r["packet_id"]: r for r in json.loads((ROOT / "review/luna-catalog.json").read_text())["accounts"]}
    vouchers = json.loads((ROOT / "catalog/label-readings.json").read_text())
    museum = json.loads((ROOT / "catalog/museum.json").read_text())
    indexed = {v["unit"]: v["gbif_provider_id_lookup"]["records"] for v in museum["vouchers"]}
    if set(audit) != set(packets):
        raise ValueError("Every catalog packet needs a distinct review")
    accounts = json.loads((ROOT / "review/account-map.json").read_text())
    luna = json.loads((ROOT / "review/luna-scan.json").read_text())
    by_page = {page: [r for r in luna if str(r["page"]) == page] for page in accounts}
    for page, ids in accounts.items():
        if len(by_page[page]) != len(ids):
            raise ValueError(f"Unassigned Luna heading on page {page}")
    sources = {r["id"]:r["source_url"] for r in rows(ROOT / "corpus/pages.jsonl")}
    corrections = {key: err for err in json.loads((ROOT / "review/errata.json").read_text())
                   for key in err["reference_ids"]}
    scores = json.loads((ROOT / "results/scores.json").read_text())["methods"]
    gold = rows(ROOT / "corpus/gold.jsonl")
    for g in gold:
        page = g["page_id"]
        number = page.replace("siboga-p", "")
        # Bind by the actual header position. The reference includes a printed
        # station only where a header has numbered material; one p113 account
        # has an unnumbered locality and is absent from this denominator.
        header = tuple(g["taxon_bbox"])
        seen_headers = sorted({tuple(r["taxon_bbox"]) for r in gold if r["taxon_page_id"] == page},
                              key=lambda b: b[1])
        numbered = [(case,read) for case,read in zip(accounts[number],by_page[number])
                    if case != "tuberosus"]
        if len(seen_headers) != len(numbered):
            raise ValueError(f"Reference and visual report differ in heading coverage on {page}")
        case, read = numbered[seen_headers.index(header)]
        packet = packets[case]
        individual = [line for line in read["stations"] if re.match(r"^Stat\.\s*" + re.escape(g["station"]) + r"(?![a-z0-9])",line,re.I)]
        corrected = corrections.get(g["id"])
        taxon = g["verbatim_taxon"]
        if corrected:
            taxon = taxon.replace(corrected["sealed_epithet"],corrected["scan_epithet"])
        yield {"id":g["id"],"source":sources[page],"kind":g["kind"],
               "scan_taxon":taxon,"reference_erratum":bool(corrected),"station":g["station"],
               "evidence":g["evidence_line"],"remarks":g["identification_remarks"],
               "station_located_exactly":{k:g["id"] in v["matches"] for k,v in scores.items()},
               "luna_heading":read["heading"],"luna_station_rows":individual if g["kind"] == "collection" else [],
               "catalog_packet_id":case,"accepted_name_in_packet":packet["taxonomy"].get("accepted"),
               "catalog_interpretation_basis":packet["taxonomy"]["basis"],
               "luna_catalog_review":audit[case]["disposition"],
               "station_linked_vouchers":[{"unit_id": unit, "admission":v["admission"],
                                           "gbif_ids":[g["key"] for g in indexed[unit]],
                                           "url":"https://data.biodiversitydata.nl/naturalis/specimen/"+unit}
                                          for unit,v in vouchers.items()
                                          if v["case"] == case and v["station"] == g["station"]
                                          and g["kind"] == "collection"]}


if __name__ == "__main__":
    save(ROOT / "review/station-ledger.jsonl", build())
