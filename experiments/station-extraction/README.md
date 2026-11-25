# Reading station numbers from a printed page

One omitted line on printed page 15 dropped fourteen real species–station pairs. A reader looking at the scan can recover the line. Both OCR systems damaged the words identifying the station list and misread some numbers. This gives a candidate vision model a concrete job, with verifiable answers and an inexpensive baseline.

The scoring unit is an exact (page, printed genus and species, station) triple. Labels come from a Codex visual inspection of each scan's numbered accounts and station lines. They describe what the historical author printed. Some historical identifications were tentative. Only station-line assertions are scored, and parenthesized subgenera are omitted from the binomial. Agreement with a present-day species assignment or accession is a separate question.

| Page set | Method | Correct / printed | Incorrect predictions |
|---|---|---:|---:|
| 10–12, error analysis | BHL OCR and original parser | 19 / 26 | 4 |
| 10–12 | English Tesseract and original parser | 19 / 26 | 4 |
| 10–12 | German Tesseract and original parser | 23 / 26 | 0 |
| 10–12 | German Tesseract with heading and station-line normalization | 26 / 26 | 0 |
| 13–15, subsequent check | BHL OCR and original parser | 23 / 53 | 2 |
| 13–15 | German Tesseract and original parser | 25 / 53 | 0 |
| 13–15 | German Tesseract with the same normalization | **39 / 53** | **0** |

The first three pages immediately follow the original calibration page. Four archive OCR substitutions read a printed 3 as an 8, including station 36 becoming 86. German Tesseract fixed these four. We then added two rules on these pages to handle parenthesized subgenera and periods inside specimen counts. The last three pages were selected by print order and opened after the revised rules were fixed. On them the strongest baseline recovered 17 of 18 numbered accounts. The only missed account was *Syndosmya longicallis*. All 14 of its stations dropped out together, so treating these as 14 independent examples would overstate the evidence. [First scan](https://www.biodiversitylibrary.org/page/32372961) · [Failed line on page 15](https://www.biodiversitylibrary.org/page/32372956)

## Reproduce the comparison

From this directory, the following commands use the frozen OCR. Each prints precision, recall, missing triples and spurious triples.

```sh
python3 score.py
python3 score.py --ocr-dir tesseract
python3 score.py --ocr-dir german-ocr
python3 score.py --ocr-dir german-ocr --normalize
python3 score.py --gold transfer.json
python3 score.py --gold transfer.json --ocr-dir german-ocr --normalize
```

To score a different reader, pass `--predictions run.json` and the corresponding `--gold`. The predictions have the same layout as the labels, mapping page IDs to dictionaries of binomials and integer station lists. Give readers only the page images or OCR. Keep `gold.json`, `transfer.json`, and catalog data out of the inference context.

All six public-domain BHL scans and raw OCR files have download URLs and SHA-256 digests in [the input manifest](sources.json). Regenerate German OCR using Tesseract 5.1.0 and the official `tessdata_best/deu.traineddata` weights with SHA-256 `8407331d6aa0229dc927685c01a7938fc5a641d1a9524f74838cdac599f0d06e`. The English comparison used SHA-256 `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`. [Tesseract models](https://github.com/tesseract-ocr/tessdata_best)

```sh
tesseract sources/32372956.jp2 /tmp/page15 --tessdata-dir "$TESSDATA_DIR" -l deu --psm 6
```

## What would justify fine-tuning a station reader?

Build a collection of paired scan crops and verified station lines from additional expeditions. Include correct easy lines, damaged numbers, non-occurrence comparisons and lines that use specimen counts or depths. Record an evidence crop and allow abstention. Split by report or expedition and keep reprints of the same material in the same split. Reserve these six inspected pages for regression testing.

Run an untuned vision reader and the German OCR baseline on the held-out reports first. Fine-tune a small vision-to-text model or adapter on a single GPU if repeated error types justify it. Compare correct pairs at matched false-station count, complete station lists per account, reviewer minutes per verified record and GPU time. The first six pages document one residual failure mode. They are too few to estimate a volume-level improvement from training.
