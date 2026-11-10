"""Pack Ugandan leaf photos into gate_photos.zip for notebook 02.

Photos picked for the Ugandan model test are left out, so that test stays fair.

    cd backend
    env -u PYTHONPATH .venv/bin/python ../ml/make_gate_photos.py
"""

import io
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_uganda as ev  # noqa: E402

PER_CROP = 900
SIZE = 256  # A little larger than 224, so the notebook can crop and zoom.
OUT = Path(__file__).resolve().parent / "gate_photos.zip"


def main() -> None:
    rng = np.random.default_rng(11)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_STORED) as bundle:
        for crop in ev.DATASETS:
            held_out = set(ev.test_set(crop)[0])
            candidates = [
                p
                for label in ev.DATASETS[crop]["archives"].values()
                for p in sorted((ev.DATA / crop / label).rglob("*"))
                if p.suffix.lower() in ev.IMAGE_TYPES and p not in held_out
            ]
            chosen = rng.permutation(len(candidates))[:PER_CROP]
            n = 0
            for index in chosen:
                try:
                    image = ImageOps.exif_transpose(Image.open(candidates[index])).convert("RGB")
                except OSError:
                    continue  # A few dataset files are corrupt.
                image = image.resize((SIZE, SIZE), Image.Resampling.BILINEAR)
                data = io.BytesIO()
                image.save(data, "JPEG", quality=88)
                bundle.writestr(f"{crop}_leaf/{n:04d}.jpg", data.getvalue())
                n += 1
            print(f"{crop}: {n} photos from {len(candidates)} not used in the model test")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
