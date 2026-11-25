# Reading complete Siboga species accounts

This independent transfer sample contains the first four consecutive pages of numbered mollusc accounts in Schepman’s 1909 *Prosobranchia of the Siboga Expedition*, part II. The ship sampled the Dutch East Indies during 1899–1900. The four prior reader expeditions used other publications, ships and cruises. The [protocol](PROTOCOL.md) fixes the inclusion rules. The [edition record](edition.json) identifies the MBLWHOI Library scan, the BHL public-domain designation and the original PDF digest.

| Printed page | BHL scan | PNG |
|---:|---|---|
| 110 | [BHL 2205141](https://www.biodiversitylibrary.org/page/2205141) | [View scan](pages/siboga-p110.png) |
| 111 | [BHL 2205140](https://www.biodiversitylibrary.org/page/2205140) | [View scan](pages/siboga-p111.png) |
| 112 | [BHL 2205139](https://www.biodiversitylibrary.org/page/2205139) | [View scan](pages/siboga-p112.png) |
| 113 | [BHL 2204983](https://www.biodiversitylibrary.org/page/2204983) | [View scan](pages/siboga-p113.png) |

**Inference inputs.** Use only the PNG files and [page manifest](pages.jsonl). The embedded OCR layer of the library PDF helped locate the beginning of the inventory and supplied no gold station transcriptions. The distributed grayscale PNGs contain no OCR layer. Pixel boxes for each taxon heading and station token, the supporting transcribed line, identification caveats and a distinction between collection and repeat mentions belong to the evaluator’s key. A second pass viewed cropped station tokens with added contrast to check the coordinates and labels. The [reference commitment](sealed.sha256) was recorded before inference.

For offline integrity verification, run `python3 verify.py` in this directory. For a byte-level rebuild, install Pillow 12.3.0 and pypdfium2 5.13.0, download the [original source PDF](https://archive.org/download/sibogaexpeditie43sibo/sibogaexpeditie43sibo.pdf), and run `python3 verify.py --pdf /path/to/sibogaexpeditie43sibo.pdf`. The script also verifies the released answer key when present.

The specimen counts and historical identifications express the author’s account. Present-day taxonomic names, exact event dates, independent catalog duplicates and the fate of specific specimen lots require other sources. [BHL METS record and rights statement](https://archive.org/download/sibogaexpeditie43sibo/sibogaexpeditie43sibo_bhlmets.xml) · [BHL volume](https://www.biodiversitylibrary.org/item/18900)
