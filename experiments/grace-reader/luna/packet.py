"""Build shuffled visual packets for independent Luna readers from input fields."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
CELLS_PER_SHEET = 16


def make(out):
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for split in ("validation", "test"):
        for line in (ROOT / "corpus" / f"{split}.jsonl").read_text().splitlines():
            row = json.loads(line)
            rows.append((row["id"], row["image"], split))
    rows.sort(key=lambda x: hashlib.sha256(("luna-v1/" + x[0]).encode()).digest())
    font = ImageFont.load_default(size=16)
    mapping = []
    for index, (case, filename, split) in enumerate(rows):
        position = index % CELLS_PER_SHEET
        if position == 0:
            page = Image.new("RGB", (960, 416), "#ebeff1")
            draw = ImageDraw.Draw(page)
        x, y = (position % 4) * 240, (position // 4) * 104
        draw.rectangle((x+2, y+2, x+237, y+101), fill="white")
        draw.text((x+10, y+6), f"{index+1:03}", font=font, fill="#164357")
        with Image.open(ROOT / filename) as source:
            crop = source.convert("RGB")
            scale = min(207 / crop.width, 66 / crop.height, 3)
            crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.NEAREST)
        page.paste(crop, (x+(240-crop.width)//2, y+29+(66-crop.height)//2))
        mapping.append({"slot": index+1, "id": case, "split": split})
        if position == CELLS_PER_SHEET-1 or index == len(rows)-1:
            page.save(out / f"sheet-{index//CELLS_PER_SHEET+1:02}.png")
    return mapping


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--mapping", type=Path, required=True)
    args = parser.parse_args()
    args.mapping.write_text(json.dumps(make(args.directory), indent=2) + "\n")
