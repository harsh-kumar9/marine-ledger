# Station-field corpus

The 213 grayscale PNGs record complete station identifiers from four expedition publications, each sampled once in one split. An evaluator selected the field bounds and transcribed the page scans, then checked the labels again in shuffled crop order with contrast enhanced for inspection. The distributed crops contain their original grayscale values. The second pass was by the same evaluator. These are deliberately localized reading examples. Detecting the field on a new full page remains a separate task.

| Assignment | Expedition | Printed pages selected | Identifiers |
|---|---|---|---:|
| Train | Pola | Sturany (1896), pp. 4–8 inclusive, entire first station table | 25 |
| Train | Albatross | California cruise station tables pp. 10, 12, 14, 16, 18, 20. Facing pages continue other columns. | 90 |
| Validation | Ingolf | First station-list leaf following Stephensen (1923), p. 100, all three columns of the recto | 67 |
| Final | Challenger | Hoyle (1886), geographical distribution station accounts, pp. 201–206 inclusive | 31 |

The Albatross field includes the series prefix D or H. Three table footnotes attach italic reference markers to station codes D4321, D4326 and D4333. The adjacent footnotes explain these markers, and the crops stop at the final digit. Two roman-letter suffixes distinguish the separate 4308 operations and are retained. The parenthetical alternate station identifier on p. 10 is its own crop. In the Ingolf table, depth-only continuation rows with blank station cells supply no identifier and are omitted. Unnumbered Challenger locality headings supply no identifier. Every explicit station in the stated excerpts is represented.

Start with the precommitted [protocol](PROTOCOL.md). Each JSONL row lists the expedition, opaque case ID and PNG path relative to the experiment root. Only train and validation manifests expose `text` before checkpoint freeze. The [edition manifest](editions.json) pins original scan downloads and rights. [Per-field provenance](provenance.json) records original page links, crop rectangles, render size and the SHA-256 of each distributed PNG. `crop_xyxy` uses pixel boundaries from the top-left with exclusive right and bottom edges. PDF page indices are zero-based, and Pola uses BHL’s 1-based sequence number. For PDFs, renders used PDFium at scale 1800 divided by the page width in points, then Pillow grayscale conversion. Pola JPEG2000 originals were resized with Lanczos to 1800 pixels wide and converted to grayscale.

All selected pages are from publications dated 1886–1923 and in the U.S. public domain. See the edition records for source credits and which part of the bound Danish volume is used. [Smithsonian Pola item](https://www.biodiversitylibrary.org/item/100795) · [Library of Congress Albatross scan](https://archive.org/details/dredginghydrogra00unit_0) · [University of Toronto Ingolf scan](https://archive.org/details/danishingolfex3cpt8daniuoft) · [Smithsonian Challenger scan](https://archive.org/details/reportoncephalop00hoyl)

Run `python3 verify.py` from this directory for an offline integrity and split check. To rebuild the crops, download the exact URLs listed under `download_url` and `individual_scans` in the edition manifest into one directory under their URL basenames. Run `python3 verify.py --scan-cache /path/to/downloads` with Pillow 12.3.0 and pypdfium2 5.13.0. This checks full source hashes before rendering and compares the rebuilt PNG bytes against every recorded crop.

The [final answer key](test-gold.jsonl) was unsealed at commit `5501859` after the model, both OCR configurations, all four prediction sets, and a separate visual read had been frozen. The integrity check also validates the unsealed file against the original commitment.
