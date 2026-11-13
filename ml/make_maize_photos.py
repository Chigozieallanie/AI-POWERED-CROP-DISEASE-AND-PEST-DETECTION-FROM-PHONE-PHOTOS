"""Pack Ugandan maize photos into maize_photos.zip for notebook 03.

Photos used by the final Ugandan test (evaluate_uganda.py) are left out, so the
fine-tuned model is judged on photos it never trained on.

    cd backend
    env -u PYTHONPATH .venv/bin/python ../ml/make_maize_photos.py
"""

import io
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_uganda as ev  # noqa: E402

PER_CLASS = 900
KEEP = 0.8  # Centre share of the photo kept; the notebook crops further.
SIZE = 320
OUT = Path(__file__).resolve().parent / "maize_photos.zip"


def main() -> None:
    rng = np.random.default_rng(21)
    held_out = set(ev.test_set("maize")[0])
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_STORED) as bundle:
        for label in ev.DATASETS["maize"]["archives"].values():
            pool = sorted(
                p for p in (ev.DATA / "maize" / label).rglob("*")
                if p.suffix.lower() in ev.IMAGE_TYPES and p not in held_out
            )
            written = 0
            for index in rng.permutation(len(pool)):
                if written == PER_CLASS:
                    break
                try:
                    image = ImageOps.exif_transpose(Image.open(pool[index])).convert("RGB")
                except OSError:
                    continue  # A few dataset files are corrupt.
                side = round(min(image.size) * KEEP)
                left, top = (image.width - side) // 2, (image.height - side) // 2
                image = image.crop((left, top, left + side, top + side)).resize((SIZE, SIZE), Image.Resampling.BILINEAR)
                data = io.BytesIO()
                image.save(data, "JPEG", quality=88)
                bundle.writestr(f"{label}/{written:04d}.jpg", data.getvalue())
                written += 1
            print(f"{label}: {written} photos from {len(pool)} not used in the final test")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
