# Reader training on an NVIDIA RTX A6000 GPU, November 25, 2026

Two 657–658 KiB checkpoints and their blind predictions are in [run](run/). The run used one NVIDIA RTX A6000 GPU with driver 570.195.03, Python 3.11.15, PyTorch 2.11.0+cu129, NumPy 2.4.4 and Pillow 12.2.0. The GPU jobs ran on the cluster node named Grace in the `ashton` SLURM partition.

| SLURM job | Stage | Elapsed | Outcome |
|---|---|---:|---|
| 520752 | Hardware and filesystem canary | 10 s | Confirmed the GPU model and a working directory accessible from the node. System Python lacked PyTorch. |
| 520754 | Conda CUDA check | 21 s | GPU convolution succeeded. The final optional font-directory listing returned status 2 for a missing directory. |
| 520762 | First synthetic fit | 34 s | 128/160 exact on a synthetic check. Subsequent development increased training steps and varied separators before looking at archive validation accuracy. |
| 520765 | Selected synthetic fit | 59 s | 2,200 optimization steps on 12,288 generated images. Reached 138/160 on a separate generated check. |
| 520768 | Real-crop adaptation | 22 s | Selected step 40 of 240 using Ingolf. The training expeditions provided 115 labeled crops. |
| 520771 | Blind final inference | 16 s | Both frozen models returned predictions for all 31 Challenger crops. |

The two synthetic checks use different generators and are descriptive. The full rendered-font hashes are in [pretrain-config.json](run/pretrain-config.json). The original training code is commit `cfdcfc2`, the crop and key freeze is `992b1c9`, and both checkpoints were committed at `c8c7ff5`. No Challenger images were staged to the training directory before that checkpoint freeze. Commit `6135a79` fixed both prediction files before the key was revealed in `5501859`. [Checkpoint and manifest digests](run/freeze.json)

| Readout | Synthetic-only reader | Archive-adapted reader |
|---|---:|---:|
| Development, Ingolf | 21/67 exact, 64 edits / 125 characters | 30/67 exact, 47 edits / 125 characters |
| Final, Challenger | 27/31 exact, 4 edits / 94 characters | 25/31 exact, 6 edits / 94 characters |

The adapted checkpoint read 114/115 training fields correctly. Its gain on the selection expedition reversed on Challenger. It introduced two whole-field errors on crops the synthetic-only reader had read correctly. The [paired comparison](comparison/test-scores.json) includes the fixed and validation-selected OCR baselines.

A post-freeze audit found that two of the 15 synthetic font files, DejaVuSansDisplay and DejaVuSerifDisplay, have no digit or Latin letter mappings. They were eligible to generate placeholder glyphs with character labels during this run. Subsequent training now checks each font's character map. To reproduce the historical training recipe, use the `reader.py` from `cfdcfc2`. To reproduce the actual blind predictions, use the saved checkpoints with `python reader.py predict --out run`. GPU training can vary between environments, and rerunning the later character-map check changes the training distribution.

The updated character-map check retained 13 eligible fonts in the reference environment. A CPU replay with the saved weights reproduced all 62 locked GPU prediction strings exactly.
