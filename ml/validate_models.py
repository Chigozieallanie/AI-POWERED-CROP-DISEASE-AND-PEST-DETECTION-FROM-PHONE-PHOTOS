"""Stress-test the converted models and check them against their authors' claims.

    cd backend
    env -u PYTHONPATH .venv/bin/python ../ml/validate_models.py ../ml/export

Writes ml/validation_report.json. Uses the Ugandan test photos from evaluate_uganda.py,
Makerere bean leaves (MIT) and synthetic images.
"""

import io
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_uganda as ev  # noqa: E402

BEANS_URL = "https://huggingface.co/datasets/AI-Lab-Makerere/beans/resolve/main/data/validation.zip"
BEANS_ZIP = ev.DATA / "beans_validation.zip"
REPORT = Path(__file__).resolve().parent / "validation_report.json"
THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95]
ROBUST_PER_CLASS = 60
SIZE = 224
CLAIMS = {
    "cassava": "Google CropNet notebook: 0.88 accuracy on 1,000 cassava test images (6 classes).",
    "maize": "Julians30 model card: macro F1 0.948 on its own Ghana, Kenya and PlantVillage test data (9 classes).",
}


class Model:
    def __init__(self, folder: Path) -> None:
        from ai_edge_litert.interpreter import Interpreter

        self.card = json.loads((folder / "model_card.json").read_text())
        self.classes = self.card["classes"]
        self.interpreter = Interpreter(model_path=str(folder / "model.tflite"))
        self.interpreter.allocate_tensors()
        self.input = self.interpreter.get_input_details()[0]["index"]
        self.output = self.interpreter.get_output_details()[0]["index"]

    def predict(self, images: list[Image.Image]) -> np.ndarray:
        rows = []
        for image in images:
            array = np.asarray(image.convert("RGB").resize((SIZE, SIZE), Image.Resampling.BILINEAR), dtype=np.float32)
            self.interpreter.set_tensor(self.input, array[None])
            self.interpreter.invoke()
            rows.append(self.interpreter.get_tensor(self.output)[0].copy())
        return np.stack(rows)


def open_photo(path: Path) -> Image.Image | None:
    try:
        return ImageOps.exif_transpose(Image.open(path)).convert("RGB").resize((448, 448), Image.Resampling.BILINEAR)
    except OSError:
        return None


def load_test(crop: str) -> tuple[list[Image.Image], list[str]]:
    paths, labels = ev.test_set(crop)
    images, kept = [], []
    for path, label in zip(paths, labels):
        image = open_photo(path)
        if image is not None:
            images.append(image)
            kept.append(label)
    return images, kept


def disease_mask(model: Model, probabilities: np.ndarray, threshold: float) -> np.ndarray:
    """True where the model gives a confident answer that is not healthy or unknown."""
    labels = np.array(model.classes)[probabilities.argmax(1)]
    return (probabilities.max(1) >= threshold) & ~np.isin(labels, ["healthy", "unknown"])


def threshold_sweep(model: Model, probabilities: np.ndarray, labels: list[str], expected: dict) -> list[dict]:
    predicted = np.array(model.classes)[probabilities.argmax(1)]
    correct = np.array([predicted[i] == expected[l] for i, l in enumerate(labels)])
    confidence = probabilities.max(1)
    rows = []
    for t in THRESHOLDS:
        answered = confidence >= t
        rows.append(
            {
                "threshold": t,
                "answered_share": round(float(answered.mean()), 3),
                "confident_wrong_rate": round(float((~correct[answered]).mean()) if answered.any() else 0.0, 3),
                "accuracy_when_answered": round(float(correct[answered].mean()) if answered.any() else 0.0, 3),
            }
        )
    return rows


def best_threshold(rows: list[dict], target: float = 0.05) -> dict | None:
    meeting = [r for r in rows if r["confident_wrong_rate"] <= target and r["answered_share"] > 0]
    return max(meeting, key=lambda r: r["answered_share"]) if meeting else None


DISTORTIONS = {
    "blurry": lambda im: im.filter(ImageFilter.GaussianBlur(4)),
    "dark": lambda im: ImageEnhance.Brightness(im).enhance(0.35),
    "rotated_90": lambda im: im.rotate(90, expand=True),
    "low_quality_jpeg": lambda im: Image.open(io.BytesIO(_jpeg(im, 15))),
    "zoomed_in": lambda im: im.crop((112, 112, 336, 336)),
    "zoomed_out": lambda im: ImageOps.pad(im.resize((200, 200)), (448, 448), color=(120, 110, 90)),
}


def _jpeg(image: Image.Image, quality: int) -> bytes:
    out = io.BytesIO()
    image.save(out, "JPEG", quality=quality)
    return out.getvalue()


def robustness(model: Model, images: list[Image.Image], labels: list[str], expected: dict) -> dict:
    rng = np.random.default_rng(3)
    chosen = []
    for label in expected:
        idx = [i for i, l in enumerate(labels) if l == label]
        chosen += list(rng.permutation(idx)[:ROBUST_PER_CLASS])
    base_images = [images[i] for i in chosen]
    base_labels = [labels[i] for i in chosen]
    truth = np.array([expected[l] for l in base_labels])

    def accuracy(probabilities: np.ndarray) -> float:
        return round(float((np.array(model.classes)[probabilities.argmax(1)] == truth).mean()), 3)

    base = model.predict(base_images)
    result = {"photos": len(base_images), "original_accuracy": accuracy(base)}
    for name, change in DISTORTIONS.items():
        probabilities = model.predict([change(im) for im in base_images])
        result[name] = {
            "accuracy": accuracy(probabilities),
            "same_answer_as_original": round(float((probabilities.argmax(1) == base.argmax(1)).mean()), 3),
        }
    return result


def bean_leaves(limit: int = 133) -> list[Image.Image]:
    if not BEANS_ZIP.exists():
        subprocess.run(["curl", "-sfL", "-m", "300", "-o", str(BEANS_ZIP), BEANS_URL], check=True)
    images = []
    with zipfile.ZipFile(BEANS_ZIP) as bundle:
        for name in sorted(n for n in bundle.namelist() if n.lower().endswith((".jpg", ".jpeg", ".png"))):
            images.append(Image.open(io.BytesIO(bundle.read(name))).convert("RGB"))
            if len(images) >= limit:
                break
    return images


def synthetic(count: int = 40) -> list[Image.Image]:
    rng = np.random.default_rng(5)
    images = [Image.fromarray(rng.integers(0, 256, (SIZE, SIZE, 3), dtype=np.uint8)) for _ in range(count)]
    images += [Image.new("RGB", (SIZE, SIZE), tuple(int(v) for v in rng.integers(0, 256, 3))) for _ in range(count)]
    return images


def confident_disease_share(model: Model, images: list[Image.Image]) -> dict:
    probabilities = model.predict(images)
    labels = np.array(model.classes)[probabilities.argmax(1)]
    confident = disease_mask(model, probabilities, 0.7)
    top = {}
    for label in labels[confident]:
        top[label] = top.get(label, 0) + 1
    return {
        "images": len(images),
        "confident_disease_share": round(float(confident.mean()), 3),
        "said_unknown_share": round(float((labels == "unknown").mean()), 3),
        "most_common_wrong_labels": sorted(top.items(), key=lambda kv: -kv[1])[:3],
    }


def main(export: Path) -> None:
    models = {crop: Model(export / crop) for crop in ev.DATASETS}
    tests = {crop: load_test(crop) for crop in ev.DATASETS}
    beans, noise = bean_leaves(), synthetic()
    report = {}

    for crop, model in models.items():
        expected = ev.DATASETS[crop]["expected"]
        images, labels = tests[crop]
        started = time.perf_counter()
        probabilities = model.predict(images)
        ms = (time.perf_counter() - started) / len(images) * 1000
        summary = ev.evaluate(probabilities, labels, model.classes, expected)
        sweep = threshold_sweep(model, probabilities, labels, expected)
        other = "maize" if crop == "cassava" else "cassava"
        report[crop] = {
            "author_claim": CLAIMS[crop],
            "uganda_accuracy": summary["accuracy"],
            "uganda_recall": {k: v["recall"] for k, v in summary["per_label"].items()},
            "threshold_sweep": sweep,
            "best_threshold_for_5pct_wrong": best_threshold(sweep),
            "wrong_crop_photos": confident_disease_share(model, tests[other][0]),
            "bean_leaves": confident_disease_share(model, beans),
            "noise_and_blank_images": confident_disease_share(model, noise),
            "bad_photos": robustness(model, images, labels, expected),
            "laptop_ms_per_photo": round(ms, 1),
            "size_mb": round((export / crop / "model.tflite").stat().st_size / 1e6, 1),
        }
        print(f"\n===== {crop} =====")
        print(json.dumps(report[crop], indent=1, default=str))

    REPORT.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nwrote {REPORT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
