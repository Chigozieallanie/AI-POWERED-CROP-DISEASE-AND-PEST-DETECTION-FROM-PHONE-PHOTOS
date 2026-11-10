"""Test converted models on Ugandan field photos and finish their model cards.

Dataverse blocks downloads from Google Colab, so this runs on the laptop with the
backend's Python environment, which already has LiteRT.

    cd backend
    env -u PYTHONPATH .venv/bin/python ../ml/evaluate_uganda.py download
    env -u PYTHONPATH .venv/bin/python ../ml/evaluate_uganda.py evaluate ../ml/export [cassava] [maize]

`evaluate` expects <export>/<crop>/model.tflite and model_card.json from notebook 01.
It writes Ugandan test results into each model card, marks weak classes experimental,
and removes classes that give too many confident wrong answers.
"""

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

DATA = Path(__file__).resolve().parent / "data"
DATAVERSE = "https://dataverse.harvard.edu"
SAMPLE_PER_CLASS = 300
SEED = 7
THRESHOLD = 0.7
MIN_RECALL = 0.8
MAX_CONFIDENT_WRONG = 0.15
MIN_CONFIDENT_FOR_JUDGEMENT = 5
IMAGE_TYPES = {".jpg", ".jpeg", ".png"}

# One archive per class keeps the download small. Labels come from archive names.
DATASETS = {
    "cassava": {
        "doi": "doi:10.7910/DVN/T4RB0B",
        "archives": {"healthy_001.rar": "healthy", "cmd_005.rar": "cmd", "cbsd-2.rar": "cbsd"},
        "expected": {"healthy": "healthy", "cmd": "cassava_mosaic", "cbsd": "cassava_brown_streak"},
    },
    "maize": {
        "doi": "doi:10.7910/DVN/LPGHKK",
        "archives": {"MLB_2.rar": "mlb", "MSV_1.rar": "msv", "Healthy_2.rar": "healthy"},
        "expected": {"healthy": "healthy", "mlb": "maize_leaf_blight", "msv": "maize_streak_virus"},
    },
}


def dataset_files(doi: str) -> tuple[str | None, dict]:
    raw = subprocess.run(
        ["curl", "-sfL", "-m", "60", f"{DATAVERSE}/api/datasets/:persistentId/?persistentId={doi}"],
        check=True, capture_output=True,
    ).stdout
    version = json.loads(raw)["data"]["latestVersion"]
    licence = version.get("license")
    licence = licence if isinstance(licence, str) else (licence or {}).get("name")
    return licence, {f["dataFile"]["filename"]: f["dataFile"] for f in version["files"]}


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while chunk := handle.read(8 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def download() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    for crop, spec in DATASETS.items():
        licence, files = dataset_files(spec["doi"])
        print(crop, "licence:", licence, flush=True)
        if licence != "CC0 1.0":
            sys.exit("Licence changed. Stop and check before using this data.")
        for name, label in spec["archives"].items():
            target = DATA / crop / label
            if target.exists() and any(target.iterdir()):
                print("already extracted", name, flush=True)
                continue
            archive = DATA / name
            info = files[name]
            print(f"downloading {name} ({info['filesize'] / 1e9:.1f} GB)", flush=True)
            # -C - resumes a broken download.
            subprocess.run(
                ["curl", "-fL", "-sS", "-C", "-", "--retry", "5", "-o", str(archive),
                 f"{DATAVERSE}/api/access/datafile/{info['id']}"],
                check=True,
            )
            expected = (info.get("checksum") or {}).get("value") or info.get("md5")
            if expected and md5(archive) != expected:
                archive.unlink()
                sys.exit(f"Checksum mismatch for {name}. Run download again.")
            target.mkdir(parents=True, exist_ok=True)
            subprocess.run(["unrar", "x", "-o+", "-inul", str(archive), f"{target}/"], check=True)
            archive.unlink()
            print("extracted", name, flush=True)
    print("download complete", flush=True)


def load_image(path: Path, size: int) -> np.ndarray:
    # Same steps as the backend: fix rotation, RGB, straight resize.
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    return np.asarray(image.resize((size, size), Image.Resampling.BILINEAR), dtype=np.float32)


def test_set(crop: str) -> tuple[list[Path], list[str]]:
    rng = np.random.default_rng(SEED)
    paths, labels = [], []
    for label in DATASETS[crop]["archives"].values():
        files = sorted(p for p in (DATA / crop / label).rglob("*") if p.suffix.lower() in IMAGE_TYPES)
        chosen = rng.permutation(len(files))[:SAMPLE_PER_CLASS]
        print(f"{crop} {label}: {len(files)} photos, testing {len(chosen)}", flush=True)
        paths += [files[i] for i in chosen]
        labels += [label] * len(chosen)
    return paths, labels


def evaluate(probabilities: np.ndarray, true_labels: list[str], classes: list[str], expected: dict) -> dict:
    predicted = np.array(classes)[probabilities.argmax(1)]
    confidence = probabilities.max(1)
    truth = np.array(true_labels)
    correct = np.array([predicted[i] == expected[label] for i, label in enumerate(truth)])
    answered = confidence >= THRESHOLD

    per_label = {}
    for label, cls in expected.items():
        mask = truth == label
        per_label[label] = {
            "n": int(mask.sum()),
            "recall": round(float((predicted[mask] == cls).mean()), 3),
            "answered_recall": round(
                float((predicted[mask & answered] == cls).mean()) if (mask & answered).any() else 0.0, 3
            ),
            "top_predictions": Counter(predicted[mask].tolist()).most_common(3),
        }
    confident_wrong_by_class = {}
    for cls in classes:
        confident = answered & (predicted == cls)
        if confident.sum() >= MIN_CONFIDENT_FOR_JUDGEMENT:
            confident_wrong_by_class[cls] = round(float((~correct[confident]).mean()), 3)
    return {
        "accuracy": round(float(correct.mean()), 3),
        "answered_share": round(float(answered.mean()), 3),
        "answered_accuracy": round(float(correct[answered].mean()) if answered.any() else 0.0, 3),
        "confident_wrong_rate": round(float((~correct[answered]).mean()) if answered.any() else 0.0, 3),
        "confident_wrong_by_class": confident_wrong_by_class,
        "per_label": per_label,
        "class_order_confirmed": all(
            per_label[label]["top_predictions"][0][0] == cls for label, cls in expected.items()
        ),
        "threshold": THRESHOLD,
        "photos_per_class": SAMPLE_PER_CLASS,
    }


def finish_card(card: dict, report: dict, expected: dict) -> dict:
    tested = {cls: label for label, cls in expected.items()}
    experimental, removed = [], []
    for cls in card["classes"]:
        if cls == "unknown":
            continue
        if report["confident_wrong_by_class"].get(cls, 0) > MAX_CONFIDENT_WRONG:
            removed.append(cls)
        elif cls not in tested or report["per_label"][tested[cls]]["recall"] < MIN_RECALL:
            experimental.append(cls)
    card["thresholds"] = {c: THRESHOLD for c in card["classes"] if c != "unknown" and c not in removed}
    card["experimental_classes"] = sorted(set(experimental) - {"healthy"})
    card["removed_classes"] = removed
    card.setdefault("metrics", {})["uganda_test"] = report
    if "healthy" in experimental:
        card["notes"] = card.get("notes", "") + " Healthy recall is below the release bar."
    return card


def run_evaluation(export: Path, crops: list[str]) -> None:
    from ai_edge_litert.interpreter import Interpreter

    for crop in crops:
        spec = DATASETS[crop]
        folder = export / crop
        card_path = folder / "model_card.json"
        card = json.loads(card_path.read_text())
        interpreter = Interpreter(model_path=str(folder / "model.tflite"))
        interpreter.allocate_tensors()
        input_index = interpreter.get_input_details()[0]["index"]
        output_index = interpreter.get_output_details()[0]["index"]

        paths, all_labels = test_set(crop)
        rows, labels, unreadable = [], [], 0
        for n, (path, label) in enumerate(zip(paths, all_labels), 1):
            try:
                image = load_image(path, card["input_size"])
            except OSError:
                unreadable += 1  # A few dataset files are corrupt.
                continue
            interpreter.set_tensor(input_index, image[None])
            interpreter.invoke()
            rows.append(interpreter.get_tensor(output_index)[0].copy())
            labels.append(label)
            if n % 200 == 0:
                print(f"  {crop}: {n}/{len(paths)}", flush=True)
        report = evaluate(np.stack(rows), labels, card["classes"], spec["expected"])
        report["unreadable_photos_skipped"] = unreadable

        print(f"\n== {crop}: accuracy {report['accuracy']}, answered {report['answered_share']}, "
              f"confident wrong {report['confident_wrong_rate']}, order confirmed {report['class_order_confirmed']}")
        for label, row in report["per_label"].items():
            print(f"  {label}: recall {row['recall']}, top {row['top_predictions']}")
        if not report["class_order_confirmed"]:
            print(f"  STOP: {crop} class order not confirmed. Card left unchanged.")
            continue
        card_path.write_text(json.dumps(finish_card(card, report, spec["expected"]), indent=2))
        print(f"  experimental: {card['experimental_classes']} | removed: {card['removed_classes']}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "download":
        download()
    elif command == "evaluate" and len(sys.argv) >= 3:
        run_evaluation(Path(sys.argv[2]), sys.argv[3:] or list(DATASETS))
    else:
        sys.exit(__doc__)
