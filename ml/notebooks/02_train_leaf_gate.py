# %% [markdown]
# # Train the "is this a leaf?" gate model
#
# Three classes: `cassava_leaf`, `maize_leaf`, `other`. The backend and app run it before
# the disease model, so a photo of a shoe, a person or a bean leaf is rejected instead of
# getting a disease name.
#
# **Before running:** upload `gate_photos.zip` (made on the laptop by
# `ml/make_gate_photos.py`) with the Files panel on the left, into `/content`.
# Then use Runtime > Run all. The last cell downloads `gate_model.zip`.
#
# Data:
# - Cassava and maize leaves: Makerere AI Lab and NaCRRI photos from Uganda (CC0).
# - Other: COCO 2017 validation photos (Flickr images, COCO annotations CC BY 4.0) and
#   Makerere bean leaves (MIT), so other crops' leaves are rejected too.

# %%
!pip -q install ai-edge-litert

# %%
import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from datasets import load_dataset
from huggingface_hub import hf_hub_download
from PIL import Image

SIZE = 224
SEED = 7
CLASSES = ["cassava_leaf", "maize_leaf", "other"]
OTHER_COCO = 1100
WORK = Path("/content/gate")
OUT = WORK / "export" / "gate"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(SEED)
tf.keras.utils.set_random_seed(SEED)

# %% [markdown]
# ## 1. Load photos

# %%
def to_array(image):
    image = image.convert("RGB").resize((SIZE, SIZE), Image.Resampling.BILINEAR)
    return np.asarray(image, dtype=np.uint8)


images, labels = [], []
with zipfile.ZipFile("/content/gate_photos.zip") as bundle:
    for name in bundle.namelist():
        if name.endswith(".jpg"):
            images.append(to_array(Image.open(io.BytesIO(bundle.read(name)))))
            labels.append(CLASSES.index(name.split("/")[0]))
print("leaf photos:", len(images))

coco = pd.read_parquet(
    hf_hub_download("detection-datasets/coco", "data/val-00000-of-00002-c4f2e391ee4aba11.parquet", repo_type="dataset"),
    columns=["image"],
)
for index in rng.permutation(len(coco))[:OTHER_COCO]:
    images.append(to_array(Image.open(io.BytesIO(coco.iloc[index]["image"]["bytes"]))))
    labels.append(CLASSES.index("other"))

for example in load_dataset("AI-Lab-Makerere/beans", split="train"):
    images.append(to_array(example["image"]))
    labels.append(CLASSES.index("other"))

X, y = np.stack(images), np.array(labels)
print({c: int((y == i).sum()) for i, c in enumerate(CLASSES)})

# %% [markdown]
# ## 2. Split 80 / 10 / 10, keeping class shares

# %%
train_idx, val_idx, test_idx = [], [], []
for c in range(len(CLASSES)):
    idx = rng.permutation(np.where(y == c)[0])
    n_val = n_test = len(idx) // 10
    test_idx += idx[:n_test].tolist()
    val_idx += idx[n_test : n_test + n_val].tolist()
    train_idx += idx[n_test + n_val :].tolist()

counts = np.bincount(y[train_idx], minlength=len(CLASSES))
class_weight = {i: len(train_idx) / (len(CLASSES) * counts[i]) for i in range(len(CLASSES))}


def dataset(idx, shuffle):
    ds = tf.data.Dataset.from_tensor_slices((X[idx].astype(np.float32), y[idx]))
    if shuffle:
        ds = ds.shuffle(len(idx), seed=SEED)
    return ds.batch(32).prefetch(tf.data.AUTOTUNE)


train_ds, val_ds, test_ds = dataset(train_idx, True), dataset(val_idx, False), dataset(test_idx, False)

# %% [markdown]
# ## 3. Train
#
# MobileNetV3Small with ImageNet weights. Its preprocessing is built in, so the model takes
# RGB values 0-255, like the disease models.

# %%
augment = tf.keras.Sequential(
    [
        tf.keras.layers.RandomFlip("horizontal_and_vertical"),
        tf.keras.layers.RandomRotation(0.15),
        tf.keras.layers.RandomZoom(0.2),
        tf.keras.layers.RandomBrightness(0.2, value_range=(0, 255)),
    ]
)
base = tf.keras.applications.MobileNetV3Small(
    input_shape=(SIZE, SIZE, 3), include_top=False, weights="imagenet", pooling="avg", include_preprocessing=True
)
base.trainable = False
inputs = tf.keras.Input((SIZE, SIZE, 3))
x = base(augment(inputs), training=False)
x = tf.keras.layers.Dropout(0.2)(x)
outputs = tf.keras.layers.Dense(len(CLASSES), activation="softmax")(x)
model = tf.keras.Model(inputs, outputs)

model.compile(tf.keras.optimizers.Adam(1e-3), "sparse_categorical_crossentropy", ["accuracy"])
model.fit(train_ds, validation_data=val_ds, epochs=6, class_weight=class_weight, verbose=2)

base.trainable = True
for layer in base.layers[:-30]:
    layer.trainable = False
model.compile(tf.keras.optimizers.Adam(1e-5), "sparse_categorical_crossentropy", ["accuracy"])
model.fit(
    train_ds, validation_data=val_ds, epochs=6, class_weight=class_weight, verbose=2,
    callbacks=[tf.keras.callbacks.EarlyStopping(patience=2, restore_best_weights=True)],
)

# %% [markdown]
# ## 4. Test on photos the model never saw

# %%
GATE_MIN_SCORE = 0.6  # Same as the backend's gate_min_score.
probabilities = model.predict(test_ds, verbose=0)
predicted, confidence, truth = probabilities.argmax(1), probabilities.max(1), y[test_idx]
confusion = np.zeros((3, 3), int)
for t, p in zip(truth, predicted):
    confusion[t, p] += 1
recall = {c: round(float(confusion[i, i] / confusion[i].sum()), 3) for i, c in enumerate(CLASSES)}
# The costly mistake: something that is not our crop's leaf passed as a leaf.
other = truth == CLASSES.index("other")
accepted = (predicted != CLASSES.index("other")) & (confidence >= GATE_MIN_SCORE)
leaf = ~other
cross_crop = leaf & accepted & (predicted != truth)
GATE_METRICS = {
    "test_photos": int(len(truth)),
    "recall": recall,
    "confusion_rows_true_cols_predicted": {"classes": CLASSES, "matrix": confusion.tolist()},
    "other_wrongly_accepted_rate": round(float(accepted[other].mean()), 4),
    "leaf_wrongly_rejected_rate": round(float((~accepted[leaf]).mean()), 4),
    "wrong_crop_accepted_rate": round(float(cross_crop[leaf].mean()), 4),
    "gate_min_score": GATE_MIN_SCORE,
}
print(json.dumps(GATE_METRICS, indent=1))

# %% [markdown]
# ## 5. Convert, check, download

# %%
class PhoneInput(tf.Module):
    def __init__(self, keras_model):
        super().__init__()
        self.keras_model = keras_model

    @tf.function(input_signature=[tf.TensorSpec([1, SIZE, SIZE, 3], tf.float32)])
    def __call__(self, x):
        return self.keras_model(x, training=False)


module = PhoneInput(model)
converter = tf.lite.TFLiteConverter.from_concrete_functions([module.__call__.get_concrete_function()], module)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_types = [tf.float16]
path = OUT / "model.tflite"
path.write_bytes(converter.convert())

from ai_edge_litert.interpreter import Interpreter

interpreter = Interpreter(model_path=str(path))
interpreter.allocate_tensors()
i, o = interpreter.get_input_details()[0]["index"], interpreter.get_output_details()[0]["index"]
sample = X[test_idx[:200]].astype(np.float32)
converted = []
for image in sample:
    interpreter.set_tensor(i, image[None])
    interpreter.invoke()
    converted.append(interpreter.get_tensor(o)[0].copy())
agreement = float((np.stack(converted).argmax(1) == model.predict(sample, verbose=0).argmax(1)).mean())
print("TFLite agreement:", agreement, "| size MB:", round(path.stat().st_size / 1e6, 1))
assert agreement >= 0.98, "Conversion changed results. Do not ship."

card = {
    "name": "gate",
    "version": "0.1.0",
    "input_size": SIZE,
    "classes": CLASSES,
    "temperature": 1.0,
    "thresholds": {},
    "experimental_classes": [],
    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "metrics": {"test": GATE_METRICS, "tflite_agreement": agreement},
    "source": "Trained in notebook 02 on Makerere/NaCRRI cassava and maize (CC0), COCO 2017 val, Makerere beans (MIT)",
    "licence": "Own model. COCO images keep their Flickr licences.",
}
(OUT / "model_card.json").write_text(json.dumps(card, indent=2))

archive = WORK / "gate_model.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
    for file in OUT.iterdir():
        bundle.write(file, f"gate/{file.name}")
from google.colab import files

files.download(str(archive))
