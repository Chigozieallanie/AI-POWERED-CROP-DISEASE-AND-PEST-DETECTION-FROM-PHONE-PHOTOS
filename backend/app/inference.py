import io
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import Settings
from app.errors import ApiError
from app.verdict import LeafScore, PlantVerdict, plant_verdict

GATE_MODEL = "gate"
ALLOWED_FORMATS = ("JPEG", "PNG", "WEBP")


@dataclass(frozen=True)
class ModelCard:
    name: str
    version: str
    input_size: int
    classes: list[str]
    temperature: float
    thresholds: dict[str, float]
    experimental_classes: list[str]
    # Share of the photo's centre kept before resizing. 1.0 keeps the whole photo.
    center_crop: float = 1.0

    @classmethod
    def from_file(cls, path: Path) -> "ModelCard":
        data = json.loads(path.read_text())
        return cls(
            name=data["name"],
            version=data["version"],
            input_size=int(data["input_size"]),
            classes=list(data["classes"]),
            temperature=float(data["temperature"]),
            thresholds={k: float(v) for k, v in data["thresholds"].items()},
            experimental_classes=list(data.get("experimental_classes", [])),
            center_crop=float(data.get("center_crop", 1.0)),
        )


class Model(Protocol):
    card: ModelCard

    def predict(self, batch: np.ndarray) -> np.ndarray: ...


class LiteRtModel:
    def __init__(self, directory: Path) -> None:
        from ai_edge_litert.interpreter import Interpreter

        self.card = ModelCard.from_file(directory / "model_card.json")
        self._interpreter = Interpreter(model_path=str(directory / "model.tflite"))
        self._interpreter.allocate_tensors()
        self._input = self._interpreter.get_input_details()[0]["index"]
        self._output = self._interpreter.get_output_details()[0]["index"]
        self._lock = threading.Lock()  # An interpreter must not run concurrently.

    def predict(self, batch: np.ndarray) -> np.ndarray:
        with self._lock:
            self._interpreter.set_tensor(self._input, batch)
            self._interpreter.invoke()
            return self._interpreter.get_tensor(self._output).copy()


class ModelRegistry:
    def __init__(self, models: dict[str, Model]) -> None:
        self.models = models

    @classmethod
    def from_directory(cls, root: Path) -> "ModelRegistry":
        models: dict[str, Model] = {}
        if root.is_dir():
            for directory in sorted(root.iterdir()):
                if (directory / "model.tflite").is_file():
                    models[directory.name] = LiteRtModel(directory)
        return cls(models)

    def require(self, crop: str) -> tuple[Model, Model]:
        gate, crop_model = self.models.get(GATE_MODEL), self.models.get(crop)
        if gate is None or crop_model is None:
            raise ApiError(
                503, "model_unavailable", f"The {crop} model is not installed on this server."
            )
        return gate, crop_model


@dataclass(frozen=True)
class LeafResult:
    index: int
    status: str
    label: str | None = None
    score: float | None = None


@dataclass(frozen=True)
class Diagnosis:
    leaves: list[LeafResult]
    verdict: PlantVerdict
    gate_version: str
    crop_version: str


def calibrate(probabilities: np.ndarray, temperature: float) -> np.ndarray:
    logits = np.log(np.clip(probabilities, 1e-12, 1.0)) / temperature
    exponent = np.exp(logits - logits.max())
    return exponent / exponent.sum()


def decode_image(data: bytes, index: int, settings: Settings) -> Image.Image:
    if len(data) > settings.max_image_bytes:
        raise ApiError(422, "invalid_image", f"Image {index} is too large.")
    try:
        image = Image.open(io.BytesIO(data), formats=ALLOWED_FORMATS)
        if image.width * image.height > settings.max_image_pixels:
            raise ApiError(422, "invalid_image", f"Image {index} has too many pixels.")
        image = ImageOps.exif_transpose(image)
        return image.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ApiError(422, "invalid_image", f"Image {index} cannot be read.") from exc


def quality_status(image: Image.Image, settings: Settings) -> str | None:
    gray = np.asarray(ImageOps.contain(image.convert("L"), (512, 512)), dtype=np.float32)
    if gray.mean() < settings.min_brightness:
        return "too_dark"
    laplacian = (
        gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4 * gray[1:-1, 1:-1]
    )
    if laplacian.size == 0 or float(laplacian.var()) < settings.min_sharpness:
        return "too_blurry"
    return None


def center_square(image: Image.Image, keep: float) -> Image.Image:
    """Crop the centre square that keeps `keep` of the shorter side."""
    side = max(1, round(min(image.size) * keep))
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    return image.crop((left, top, left + side, top + side))


def _batch(image: Image.Image, size: int, keep: float = 1.0) -> np.ndarray:
    resized = center_square(image, keep).resize((size, size), Image.Resampling.BILINEAR)
    return np.expand_dims(np.asarray(resized, dtype=np.float32), 0)


def _top(model: Model, image: Image.Image) -> tuple[str, float]:
    raw = model.predict(_batch(image, model.card.input_size, model.card.center_crop))[0]
    calibrated = calibrate(raw, model.card.temperature)
    best = int(calibrated.argmax())
    return model.card.classes[best], float(calibrated[best])


def diagnose(
    registry: ModelRegistry, crop: str, images: list[bytes], settings: Settings
) -> Diagnosis:
    gate, crop_model = registry.require(crop)
    decoded = [decode_image(data, index, settings) for index, data in enumerate(images)]

    leaves: list[LeafResult] = []
    scores: list[LeafScore] = []
    for index, image in enumerate(decoded):
        problem = quality_status(image, settings)
        if problem is not None:
            leaves.append(LeafResult(index, problem))
            continue
        gate_label, gate_score = _top(gate, image)
        if gate_label == "other" or gate_score < settings.gate_min_score:
            leaves.append(LeafResult(index, "not_leaf"))
            continue
        if gate_label != f"{crop}_leaf":
            leaves.append(LeafResult(index, "wrong_crop"))
            continue
        label, score = _top(crop_model, image)
        leaves.append(LeafResult(index, "accepted", label, round(score, 4)))
        scores.append(LeafScore(label, score))

    card = crop_model.card
    verdict = plant_verdict(scores, card.thresholds, card.experimental_classes)
    return Diagnosis(leaves, verdict, gate.card.version, card.version)
