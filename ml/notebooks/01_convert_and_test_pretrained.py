# %% [markdown]
# # Convert pretrained crop models to TFLite
#
# Converts two pretrained models into phone format and checks the converted files give the
# same answers as the originals:
#
# - **Maize:** Julians30 MobileNetV3 (PyTorch, Apache 2.0), 9 classes.
# - **Cassava:** Google CropNet (TensorFlow), 6 classes. Licence still unconfirmed.
#
# Testing on Ugandan photos happens on the laptop with `ml/evaluate_uganda.py`, because
# Harvard Dataverse refuses downloads from Colab.
#
# **Run on Google Colab, CPU runtime.** Run the first cell; it restarts the session once.
# Then run every remaining cell in order. The last cell downloads `pretrained_models.zip`.
# Unzip it into `ml/export/` in the project.

# %%
# Install. torchao must match Colab's PyTorch 2.9, or the converter fails to import.
import os
from pathlib import Path

if not Path("/content/.crop_installed").exists():
    !pip -q install timm huggingface_hub tensorflow_hub ai-edge-litert litert-torch "torchao==0.14.1" datasets
    Path("/content/.crop_installed").touch()
    os.kill(os.getpid(), 9)  # Restart once so the new libraries load cleanly.

# %%
import hashlib
import json
import time
import zipfile

import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
import timm
import torch
import litert_torch
from ai_edge_litert.interpreter import Interpreter
from datasets import load_dataset
from huggingface_hub import hf_hub_download
from PIL import Image

SIZE = 224
WORK = Path("/content/crop")
OUT = WORK / "export"
for crop in ("maize", "cassava"):
    (OUT / crop).mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## 1. Load the pretrained models

# %%
MAIZE_REPO = "Julians30/maize-disease-models"
# Output order is not published. This order is taken from the alphabetical
# class_weights.json; ml/evaluate_uganda.py confirms it on Ugandan photos.
MAIZE_LABELS = [
    "fall_armyworm", "grasshopper", "healthy", "leaf_beetle", "leaf_blight",
    "leaf_spot", "lethal_necrosis", "rust", "streak_virus",
]
MAIZE_IDS = {
    "fall_armyworm": "fall_armyworm", "grasshopper": "grasshopper", "healthy": "healthy",
    "leaf_beetle": "leaf_beetle", "leaf_blight": "maize_leaf_blight", "leaf_spot": "maize_leaf_spot",
    "lethal_necrosis": "maize_lethal_necrosis", "rust": "maize_rust", "streak_virus": "maize_streak_virus",
}
checkpoint = torch.load(
    hf_hub_download(MAIZE_REPO, "mobilenetv3_best.pth"), map_location="cpu", weights_only=True
)  # weights_only blocks code inside the file from running.
maize_net = timm.create_model("mobilenetv3_large_100", num_classes=len(MAIZE_LABELS), pretrained=False)
maize_net.load_state_dict(checkpoint["model_state_dict"], strict=True)
maize_net.eval()
# The checkpoint's own config: 224 px, ImageNet mean and std, test images only resized.
config = checkpoint["config"]
assert config["img_size"] == SIZE
MEAN, STD = config["normalize_mean_imagenet"], config["normalize_std_imagenet"]


class PhoneInput(torch.nn.Module):
    """Takes what the app sends: [1, 224, 224, 3] RGB values 0-255. Returns probabilities."""

    def __init__(self, net):
        super().__init__()
        self.net = net
        self.register_buffer("mean", torch.tensor(MEAN).view(1, 3, 1, 1) * 255)
        self.register_buffer("std", torch.tensor(STD).view(1, 3, 1, 1) * 255)

    def forward(self, x):
        return torch.softmax(self.net((x.permute(0, 3, 1, 2) - self.mean) / self.std), dim=-1)


maize_model = PhoneInput(maize_net).eval()

CROPNET_URL = "https://tfhub.dev/google/cropnet/classifier/cassava_disease_V1/2"
CROPNET_LABELS = ["cbb", "cbsd", "cgm", "cmd", "healthy", "unknown"]
CASSAVA_IDS = {
    "cbb": "cassava_bacterial_blight", "cbsd": "cassava_brown_streak",
    "cgm": "cassava_green_mite",  # CropNet's "cgm" means green mite.
    "cmd": "cassava_mosaic", "healthy": "healthy", "unknown": "unknown",
}
cropnet = hub.load(CROPNET_URL)


def cropnet_probabilities(x):
    """CropNet needs training=False and RGB values 0-1. It already returns probabilities."""
    out = cropnet(x, training=False)
    return tf.convert_to_tensor(next(iter(out.values())) if isinstance(out, dict) else out)


print("models loaded")

# %% [markdown]
# ## 2. Convert

# %%
class CassavaPhoneInput(tf.Module):
    @tf.function(input_signature=[tf.TensorSpec([1, SIZE, SIZE, 3], tf.float32)])
    def __call__(self, x):
        return cropnet_probabilities(x / 255.0)


started = time.time()
litert_torch.convert(maize_model, (torch.zeros(1, SIZE, SIZE, 3),)).export(str(OUT / "maize" / "model.tflite"))
print(f"maize converted in {time.time() - started:.0f}s")

started = time.time()
module = CassavaPhoneInput()
converter = tf.lite.TFLiteConverter.from_concrete_functions([module.__call__.get_concrete_function()], module)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_types = [tf.float16]
(OUT / "cassava" / "model.tflite").write_bytes(converter.convert())
print(f"cassava converted in {time.time() - started:.0f}s")

# %% [markdown]
# ## 3. Check converted files agree with the originals
#
# Uses Makerere's bean leaf photos (MIT licence) only as realistic leaf images.

# %%
beans = load_dataset("AI-Lab-Makerere/beans", split="validation")
check = np.stack(
    [np.asarray(e["image"].convert("RGB").resize((SIZE, SIZE), Image.Resampling.BILINEAR), dtype=np.float32) for e in beans]
)


def run_tflite(path, images):
    interpreter = Interpreter(model_path=str(path))
    interpreter.allocate_tensors()
    i = interpreter.get_input_details()[0]["index"]
    o = interpreter.get_output_details()[0]["index"]
    rows = []
    for image in images:
        interpreter.set_tensor(i, image[None])
        interpreter.invoke()
        rows.append(interpreter.get_tensor(o)[0].copy())
    return np.stack(rows)


with torch.no_grad():
    maize_original = maize_model(torch.from_numpy(check)).numpy()
cassava_original = np.concatenate(
    [cropnet_probabilities(tf.constant(check[i : i + 32] / 255.0)).numpy() for i in range(0, len(check), 32)]
)

AGREEMENT = {}
for crop, original in (("maize", maize_original), ("cassava", cassava_original)):
    converted = run_tflite(OUT / crop / "model.tflite", check)
    AGREEMENT[crop] = {
        "top1_agreement": round(float((original.argmax(1) == converted.argmax(1)).mean()), 4),
        "max_abs_diff": round(float(np.abs(original - converted).max()), 5),
        "images": len(check),
    }
    print(crop, AGREEMENT[crop])
    assert AGREEMENT[crop]["top1_agreement"] >= 0.98, f"{crop} conversion changed results. Do not ship."

# %% [markdown]
# ## 4. Write model cards
#
# Thresholds and the experimental list are provisional here. `ml/evaluate_uganda.py`
# replaces them after testing on Ugandan photos. Until then, every class except healthy
# is experimental, so the app never says "Very likely".

# %%
def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_card(crop, labels, ids, source, licence, notes):
    classes = [ids[label] for label in labels]
    counted = [c for c in classes if c != "unknown"]
    path = OUT / crop / "model.tflite"
    card = {
        "name": crop,
        "version": "0.1.0",
        "input_size": SIZE,
        "classes": classes,
        "temperature": 1.0,
        "thresholds": {c: 0.7 for c in counted},
        "experimental_classes": sorted(c for c in counted if c != "healthy"),
        "removed_classes": [],
        "sha256": sha256(path),
        "metrics": {"tflite_agreement": AGREEMENT[crop]},
        "source": source,
        "licence": licence,
        "notes": notes,
    }
    (OUT / crop / "model_card.json").write_text(json.dumps(card, indent=2))
    print(crop, round(path.stat().st_size / 1e6, 1), "MB", card["classes"])


write_card(
    "maize", MAIZE_LABELS, MAIZE_IDS, f"huggingface.co/{MAIZE_REPO} mobilenetv3_best.pth", "Apache-2.0",
    "Pretrained on Ghana, Kenya and PlantVillage photos. Threshold not tuned.",
)
write_card(
    "cassava", CROPNET_LABELS, CASSAVA_IDS, CROPNET_URL, "unconfirmed",
    "Google CropNet. Licence must be confirmed before commercial use. Threshold not tuned.",
)

# %% [markdown]
# ## 5. Download

# %%
archive = WORK / "pretrained_models.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
    for path in OUT.rglob("*"):
        if path.is_file():
            bundle.write(path, path.relative_to(OUT))
print("wrote", archive, round(archive.stat().st_size / 1e6, 1), "MB")

from google.colab import files

files.download(str(archive))
