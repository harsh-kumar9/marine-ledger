"""Read station images with the two pinned Hugging Face checkpoints on one GPU."""

import argparse
import json
import os
from pathlib import Path
import platform

from PIL import Image, __version__ as pillow_version
import torch
import transformers
from transformers import (
    AutoImageProcessor, AutoModelForTextRecognition, TrOCRProcessor, VisionEncoderDecoderModel,
)

from fetch import MODELS, digest


ROOT = Path(__file__).resolve().parents[1]


def reader(name, folder):
    if name == "paddle":
        processor = AutoImageProcessor.from_pretrained(folder, local_files_only=True)
        model = AutoModelForTextRecognition.from_pretrained(folder, local_files_only=True).eval().cuda()

        def predict(image):
            inputs = processor(images=image, return_tensors="pt").to("cuda")
            return processor.post_process_text_recognition(model(**inputs))[0]["text"]
    else:
        processor = TrOCRProcessor.from_pretrained(folder, local_files_only=True)
        model = VisionEncoderDecoderModel.from_pretrained(folder, local_files_only=True).eval().cuda()

        def predict(image):
            pixels = processor(images=image, return_tensors="pt").pixel_values.cuda()
            tokens = model.generate(pixel_values=pixels, do_sample=False, max_new_tokens=24)
            return processor.batch_decode(tokens, skip_special_tokens=True)[0]
    return predict


def run(weights, out):
    out.mkdir(parents=True, exist_ok=True)
    receipt = {
        "device": torch.cuda.get_device_name(0), "python": platform.python_version(),
        "torch": str(torch.__version__), "cuda_runtime": torch.version.cuda,
        "transformers": transformers.__version__, "pillow": pillow_version,
        "slurm_job": os.getenv("SLURM_JOB_ID"), "models": {}, "predictions": {},
    }
    with torch.inference_mode():
        for name, model in MODELS.items():
            folder = weights / name / model["revision"]
            file_hashes = {f: digest(folder / f) for f in model["files"]}
            if file_hashes["model.safetensors"] != model["weights_sha256"]:
                raise ValueError(f"Unexpected weights for {name}")
            receipt["models"][name] = {"revision": model["revision"], "files": file_hashes}
            predict = reader(name, folder)
            for split in ("validation", "test"):
                rows = [json.loads(line) for line in (ROOT / "corpus" / f"{split}.jsonl").read_text().splitlines()]
                output = out / f"{name}-{split}.jsonl"
                records = []
                for row in rows:
                    with Image.open(ROOT / row["image"]) as image:
                        text = predict(image.convert("RGB"))
                    records.append({"id": row["id"], "text": text})
                temporary = output.with_suffix(".tmp")
                temporary.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in records))
                temporary.replace(output)
                receipt["predictions"][output.name] = {"rows": len(rows), "sha256": digest(output)}
                print(f"{name} {split}: {len(rows)} fields", flush=True)
            del predict
    (out / "runtime.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("weights", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    run(args.weights, args.out)
