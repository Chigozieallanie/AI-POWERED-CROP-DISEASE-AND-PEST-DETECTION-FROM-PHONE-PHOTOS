"""Pack KaraAgro fall armyworm photos (CC0) for notebooks 02 and 03.

20% of the photos are held back in faw_test_list.txt and never packed, so the
retrained models can be tested fairly afterwards.

Writes:
- faw_photos.zip: centre 80% crops at 320 px, folder "faw/", for maize training.
- gate_faw.zip: whole photos at 256 px, folder "maize_leaf/", for the leaf check.

    cd backend
    env -u PYTHONPATH .venv/bin/python ../ml/make_faw_photos.py
"""

import io
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ML = Path(__file__).resolve().parent
SOURCE = ML / "data" / "faw"
TEST_LIST = ML / "faw_test_list.txt"
TYPES = {".jpg", ".jpeg"}
TEST_SHARE = 0.2


def jpeg(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, "JPEG", quality=88)
    return out.getvalue()


def centre(image: Image.Image, keep: float) -> Image.Image:
    side = round(min(image.size) * keep)
    left, top = (image.width - side) // 2, (image.height - side) // 2
    return image.crop((left, top, left + side, top + side))


def main() -> None:
    photos = sorted(p for p in SOURCE.rglob("*") if p.suffix.lower() in TYPES)
    order = np.random.default_rng(31).permutation(len(photos))
    n_test = int(len(photos) * TEST_SHARE)
    test = [photos[i] for i in order[:n_test]]
    train = [photos[i] for i in order[n_test:]]
    TEST_LIST.write_text("\n".join(str(p.relative_to(SOURCE)) for p in test) + "\n")

    written = 0
    with zipfile.ZipFile(ML / "faw_photos.zip", "w", zipfile.ZIP_STORED) as maize_zip, \
         zipfile.ZipFile(ML / "gate_faw.zip", "w", zipfile.ZIP_STORED) as gate_zip:
        for path in train:
            try:
                image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
            except OSError:
                continue  # A few dataset files are corrupt.
            maize_zip.writestr(f"faw/{written:04d}.jpg", jpeg(centre(image, 0.8).resize((320, 320))))
            gate_zip.writestr(f"maize_leaf/faw_{written:04d}.jpg", jpeg(image.resize((256, 256))))
            written += 1
    print(f"{len(photos)} photos: {written} packed for training, {len(test)} held back for testing")
    for name in ("faw_photos.zip", "gate_faw.zip"):
        print(name, round((ML / name).stat().st_size / 1e6), "MB")


if __name__ == "__main__":
    main()
