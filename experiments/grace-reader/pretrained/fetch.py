"""Stage the exact public files for offline inference."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


MODELS = json.loads(Path(__file__).with_name("models.json").read_text())


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def fetch(root):
    for name, model in MODELS.items():
        folder = root / name / model["revision"]
        folder.mkdir(parents=True, exist_ok=True)
        for filename in model["files"]:
            path = folder / filename
            url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{filename}"
            with tempfile.NamedTemporaryFile(dir=folder, delete=False) as file:
                temporary = Path(file.name)
            try:
                subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                                "--retry", "3", "--max-time", "300", "-o", str(temporary), url],
                               check=True)
                if filename == "model.safetensors" and digest(temporary) != model["weights_sha256"]:
                    raise ValueError(f"Weight checksum mismatch for {name}")
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        print(f"Verified {name} at {model['revision']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    fetch(parser.parse_args().destination)
