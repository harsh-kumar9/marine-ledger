# Can a reader trained on expedition scans beat OCR on a new expedition?

**On this Challenger report, ordinary OCR recovered more complete station identifiers.** We trained the reader on one NVIDIA RTX A6000 GPU. It got 25 of 31 right. The preregistered Tesseract configuration got 26, and the configuration selected on the separate Ingolf report got 27. This experiment supplies the location of each printed field. An end-to-end expedition reader would also need to locate the field and associate it with the correct taxon or event.

| Reader | Exact identifiers on Challenger | Character edits / 94 characters |
|---|---:|---:|
| Tesseract, preregistered single-word setting | 26 / 31 (83.9%) | 7 |
| Tesseract, validation-selected single-line setting | 27 / 31 (87.1%) | 5 |
| Neural reader trained on synthetic text | 27 / 31 (87.1%) | 4 |
| Same reader after adaptation to real expedition crops | 25 / 31 (80.6%) | 6 |

A follow-up ran two published Hugging Face checkpoints on the same GPU and two independent Luna subagents on the same fields. All four recovered the 31 Challenger identifiers. The labels were already public for that follow-up. [Pretrained readers, Luna and the shared Ingolf errors](pretrained/README.md)

## What transferred

Training used 115 real crops from Pola and Albatross. Ingolf supplied 67 validation identifiers for checkpoint and OCR configuration selection. During development, adaptation improved the neural reader from 21 to 30 exact on Ingolf. The stronger Tesseract setting read 47 of the same 67 exactly. A separate evaluator kept the answer key for Hoyle's 1886 Challenger report sealed until all model and OCR outputs were frozen. A second visual reading of the 31 shuffled test crops agreed with all 31 labels. [Edition selection and source scans](corpus/README.md) · [Model and decoder](MODEL.md) · [Blind second reading](comparison/second-read.jsonl)

On Challenger, adaptation changed two previously correct identifiers into errors: the printed **163A** became **1634**, and **216A** became **2164**. It fixed zero previously incorrect fields by the exact-identifier metric. Of the 115 training identifiers, only two ended in letters. Ingolf had zero letter suffixes, while Challenger had five. This distribution difference is one explanation worth testing. One edition and 31 fields give limited evidence about how often it occurs elsewhere.

The adapted reader and validation-selected OCR agreed on 23 readings, all correct. Their eight disagreements included all the errors made by either system. This suggests an experiment for a new expedition: route disagreements to a source-checking agent, audit a sample of agreements and measure review minutes per verified record. The 23/23 was observed after unsealing. It needs replication before being used as a rule for accepting records. [Paired counts and results by length](comparison/test-scores.json)

## Reproduce the comparison offline

Run from this directory. Scoring uses only Python's standard library and the committed predictions. The two trained checkpoints are in `run/`. A CPU replay reproduced all 62 GPU predictions. Two fonts used during synthetic training lacked the target glyphs. The training commit and subsequent correction are documented in the run record. [GPU jobs, environment and inference](RUN.md) · [Primary OCR](primary-ocr/README.md) · [Secondary baseline protocol](comparison-plan.md) · [Model freeze receipt](run/freeze.json)

```sh
python3 compare_ocr.py paired --gold corpus/test-gold.jsonl --inputs corpus/test.jsonl \
  --tuned run/adapted-test.jsonl --untuned run/synthetic-test.jsonl \
  --baseline primary-ocr/test.jsonl --challenger comparison/ocr-selected-test.jsonl \
  --out /tmp/challenger-paired.json
diff comparison/test-scores.json /tmp/challenger-paired.json
```

The public history records the sequence. The [split and primary metric](https://github.com/harsh-kumar9/marine-ledger/commit/f48e459), [frozen corpus and answer-key hash](https://github.com/harsh-kumar9/marine-ledger/commit/992b1c9), [checkpoint freeze](https://github.com/harsh-kumar9/marine-ledger/commit/c8c7ff5), [blind GPU predictions](https://github.com/harsh-kumar9/marine-ledger/commit/6135a79), and [key release](https://github.com/harsh-kumar9/marine-ledger/commit/5501859) can be inspected independently.
