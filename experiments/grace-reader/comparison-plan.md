# Paired comparison on a held-out expedition

This secondary comparison was specified before the Ingolf crops, OCR predictions or Challenger labels were available. The primary comparison remains the one in the [corpus protocol](corpus/PROTOCOL.md). All readers get the same source image and the same field location. The output is the full printed station identifier. No reader gets the page number, station inventory, or earlier rows as input.

In addition to the fixed English Tesseract single-word baseline, try these four English LSTM configurations in order on the validation report. The order breaks exact ties.

1. Single word, original crop (PSM 8).
2. Single line, original crop (PSM 7).
3. Single word, enlarged crop (PSM 8).
4. Single line, enlarged crop (PSM 7).

For the enlarged treatments, convert to grayscale, auto-level the image, resize to 72 pixels high with Lanczos interpolation, and add a 10-pixel white border. Keep the same ASCII alphanumeric whitelist for every run. Select the highest exact-cell accuracy on Ingolf. Break ties using lower character error rate and then the order above. Freeze the chosen configuration and the GPU checkpoint before opening Challenger labels.

Write a prediction for every test crop, including empty OCR reads. Join outcomes by crop ID and use the same normalization across readers. Report exact correct / total, character errors / reference characters and the paired counts of cells only the model or only the comparator got right. Count pages and distinct reference identifiers so repeated printings are visible. Interpret the result as transfer to this one report with field locations supplied. A comparison on one edition cannot estimate performance across expeditions.
