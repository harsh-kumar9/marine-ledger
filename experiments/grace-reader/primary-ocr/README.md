# Primary OCR reference

The preregistered baseline ran Tesseract 5.1.0 (Leptonica 1.82.0) on each original PNG, with the English LSTM, one-word segmentation (PSM 8), and the 62-character Latin-letter and digit whitelist. Exact normalization and Levenshtein scoring are implemented in [baseline.py](../baseline.py). The SHA-256 of the installed `eng.traineddata` was `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`. Selection of the primary configuration preceded scoring. [Experiment protocol](../corpus/PROTOCOL.md)

From `experiments/grace-reader`, reproduce the validation predictions and metrics directly.

```sh
python3 baseline.py predict --manifest corpus/validation.jsonl --out /tmp/ingolf-predictions.jsonl
python3 baseline.py score --gold corpus/validation.jsonl --predictions /tmp/ingolf-predictions.jsonl
```

| Source | Correct full identifiers | Character edits / reference characters |
|---|---:|---:|
| Albatross (train) | 62/90 | 29/452 |
| Pola (train) | 16/25 | 17/62 |
| Ingolf (validation) | 24/67 | 60/125 |

Train results use real crops seen by the eventual specialist, enabling an implementation check. The unseen source for validation uses small, lightly printed numerals in a three-column station list. The cases come from one printed table and have related typography. Per-cell metrics here describe this corpus and do not estimate variability across expeditions.
