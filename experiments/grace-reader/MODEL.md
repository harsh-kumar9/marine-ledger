# Station reader

The model receives a single grayscale crop targeting the printed station identifier. Its four convolutional blocks reduce each field to a horizontal sequence. A bidirectional GRU provides character context, and a CTC objective learns the alignment between pixels and labels. Decoding greedily collapses repeated path symbols and removes blanks. The alphabet contains ten digits and 26 uppercase Latin letters.

First train on synthetic digit strings and strings with letter prefixes and suffixes in local open fonts. Then adapt the model on real training crops, retaining synthetic rehearsal examples to cover infrequent characters. Save both models. The optimization settings, normalization and training seed are in `reader.py`. Every 20 adaptation steps, evaluate exact field accuracy on the development expedition. Break ties with lower character error rate, then earlier step. The adapted reader and the synthetic-only reader are evaluated separately. The final expedition remains with the evaluator until checkpoints and inference settings are frozen. See the [corpus protocol](corpus/PROTOCOL.md).

This script requires Python, PyTorch with GPU support, Pillow, NumPy and DejaVu or Liberation TrueType fonts. Training uses FontTools to check the font character maps. The training run records font digests, library versions, device, manifests, training steps and model digests. Image inputs are read on demand for each stage and no external weights are downloaded. Each stage can be run separately. A completed stage is skipped on scheduler requeue. An interrupted short stage restarts from its preceding checkpoint. See the [NVIDIA RTX A6000 GPU run and held-out results](RUN.md) for the exact historical recipe.

```sh
python reader.py pretrain --out runs/reader
python reader.py adapt --out runs/reader
python reader.py predict --out runs/reader
```

For SLURM, create a run directory and a log directory accessible from the cluster node named Grace, then submit `train.sbatch` with `--output` pointing there. Set `READER_PYTHON` to a CUDA-capable Python executable when the batch environment lacks one on its path. Pass an absolute copy of this experiment directory, the absolute run output directory and the stage name. Capture the code commit and use one run directory per model/configuration. Inference emits one JSON object per line with `id` and `text` keys. Evaluation uses exact agreement and edit distance against independently held reference strings.
