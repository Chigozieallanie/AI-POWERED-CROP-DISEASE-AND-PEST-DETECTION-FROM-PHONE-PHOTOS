# %% [markdown]
# # Fine-tune the maize model on Ugandan photos
#
# Starts from the pretrained Julians30 MobileNetV3, which knows maize diseases from
# Ghana, Kenya and PlantVillage, and trains it further on Ugandan photos from Makerere AI
# Lab and NaCRRI (CC0): healthy, leaf blight and streak virus.
#
# **Before running:** use Runtime > Change runtime type > T4 GPU if available (CPU works,
# but slowly). Upload `maize_photos.zip` (made by `ml/make_maize_photos.py`) with the
# Files panel into `/content`. Run the first cell; it restarts the session once. Then run
# every remaining cell. The last cell downloads `maize_finetuned.zip`.
#
# The final test runs on the laptop with `ml/evaluate_uganda.py`, on photos this notebook
# never sees.

# %%
import os
from pathlib import Path

if not Path("/content/.maize_installed").exists():
    !pip -q install timm huggingface_hub ai-edge-litert litert-torch
    # litert-torch may upgrade PyTorch; torchao must then match the new version.
    !pip -q install -U torchao
    Path("/content/.maize_installed").touch()
    os.kill(os.getpid(), 9)  # Restart once so the new libraries load cleanly.

# %%
import copy
import hashlib
import io
import json
import time
import zipfile

import numpy as np
import timm
import torch
import torch.nn.functional as F
from huggingface_hub import hf_hub_download
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

SEED = 7
SIZE = 224
EVAL_KEEP = 0.75  # Of the stored 80% crop, which equals the backend's centre 60%.
EPOCHS = 8
WORK = Path("/content/maize")
OUT = WORK / "export" / "maize"
OUT.mkdir(parents=True, exist_ok=True)
torch.manual_seed(SEED)
rng = np.random.default_rng(SEED)
device = "cuda" if torch.cuda.is_available() else "cpu"
print("device:", device)

MAIZE_LABELS = [
    "fall_armyworm", "grasshopper", "healthy", "leaf_beetle", "leaf_blight",
    "leaf_spot", "lethal_necrosis", "rust", "streak_virus",
]
FOLDER_TO_LABEL = {"healthy": "healthy", "mlb": "leaf_blight", "msv": "streak_virus", "faw": "fall_armyworm"}
MAIZE_IDS = {
    "fall_armyworm": "fall_armyworm", "grasshopper": "grasshopper", "healthy": "healthy",
    "leaf_beetle": "leaf_beetle", "leaf_blight": "maize_leaf_blight", "leaf_spot": "maize_leaf_spot",
    "lethal_necrosis": "maize_lethal_necrosis", "rust": "maize_rust", "streak_virus": "maize_streak_virus",
}

# %% [markdown]
# ## 1. Photos and split (85% train, 15% check)

# %%
photos, targets = [], []
# maize_photos.zip: Ugandan healthy, blight, streak. faw_photos.zip (optional): fall armyworm.
for archive in ("/content/maize_photos.zip", "/content/faw_photos.zip"):
    if not Path(archive).exists():
        print("not found, skipped:", archive)
        continue
    with zipfile.ZipFile(archive) as bundle:
        for name in sorted(bundle.namelist()):
            if name.endswith(".jpg"):
                photos.append(Image.open(io.BytesIO(bundle.read(name))).convert("RGB"))
                targets.append(MAIZE_LABELS.index(FOLDER_TO_LABEL[name.split("/")[0]]))
print({label: targets.count(MAIZE_LABELS.index(label)) for label in FOLDER_TO_LABEL.values()})
targets = np.array(targets)
train_idx, val_idx = [], []
for c in np.unique(targets):
    idx = rng.permutation(np.where(targets == c)[0])
    n_val = int(len(idx) * 0.15)
    val_idx += idx[:n_val].tolist()
    train_idx += idx[n_val:].tolist()
print("train", len(train_idx), "check", len(val_idx))

MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
train_tf = transforms.Compose([
    transforms.RandomResizedCrop(SIZE, scale=(0.35, 0.9), ratio=(0.8, 1.25)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.RandomRotation(20),
    transforms.ColorJitter(0.3, 0.3, 0.2, 0.03),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])
eval_tf = transforms.Compose([
    transforms.CenterCrop(int(320 * EVAL_KEEP)),
    transforms.Resize((SIZE, SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])


class Photos(Dataset):
    def __init__(self, idx, tf):
        self.idx, self.tf = idx, tf

    def __len__(self):
        return len(self.idx)

    def __getitem__(self, i):
        j = self.idx[i]
        return self.tf(photos[j]), int(targets[j])


train_dl = DataLoader(Photos(train_idx, train_tf), batch_size=32, shuffle=True, num_workers=2)
val_dl = DataLoader(Photos(val_idx, eval_tf), batch_size=64, num_workers=2)

# %% [markdown]
# ## 2. Load the pretrained model and measure it first

# %%
checkpoint = torch.load(
    hf_hub_download("Julians30/maize-disease-models", "mobilenetv3_best.pth"), map_location="cpu", weights_only=True
)
model = timm.create_model("mobilenetv3_large_100", num_classes=len(MAIZE_LABELS), pretrained=False)
model.load_state_dict(checkpoint["model_state_dict"], strict=True)
model.to(device)


def check(net):
    net.eval()
    predicted, truth = [], []
    with torch.no_grad():
        for x, y in val_dl:
            predicted.append(net(x.to(device)).argmax(1).cpu())
            truth.append(y)
    predicted, truth = torch.cat(predicted).numpy(), torch.cat(truth).numpy()
    recall = {MAIZE_LABELS[c]: round(float((predicted[truth == c] == c).mean()), 3) for c in np.unique(truth)}
    return round(float((predicted == truth).mean()), 3), recall


BEFORE = check(model)
print("before fine-tuning:", BEFORE)

# %% [markdown]
# ## 3. Fine-tune
#
# Low learning rate, so the model adapts to Ugandan photos without forgetting
# what it already knows.

# %%
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0.01)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
best_acc, best_state, HISTORY = -1.0, None, []
for epoch in range(EPOCHS):
    model.train()
    started, total = time.time(), 0.0
    for x, y in train_dl:
        x, y = x.to(device), y.to(device)
        loss = F.cross_entropy(model(x), y, label_smoothing=0.05)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total += loss.item() * len(y)
    scheduler.step()
    acc, recall = check(model)
    HISTORY.append({"epoch": epoch + 1, "loss": round(total / len(train_idx), 4), "check_accuracy": acc, "recall": recall})
    print(HISTORY[-1], f"{time.time() - started:.0f}s")
    if acc > best_acc:
        best_acc, best_state = acc, copy.deepcopy(model.state_dict())

model.load_state_dict(best_state)
# Saved before conversion, so a converter problem never loses the training.
torch.save(best_state, WORK / "finetuned_state.pt")
AFTER = check(model)
print("before:", BEFORE, "\nafter:", AFTER)

# %% [markdown]
# ## 4. Convert to TFLite and check it matches

# %%
import litert_torch
from ai_edge_litert.interpreter import Interpreter


class PhoneInput(torch.nn.Module):
    """App input: [1, 224, 224, 3] RGB 0-255, already centre-cropped by the backend or app."""

    def __init__(self, net):
        super().__init__()
        self.net = net
        self.register_buffer("mean", torch.tensor(MEAN).view(1, 3, 1, 1) * 255)
        self.register_buffer("std", torch.tensor(STD).view(1, 3, 1, 1) * 255)

    def forward(self, x):
        return torch.softmax(self.net((x.permute(0, 3, 1, 2) - self.mean) / self.std), dim=-1)


phone_model = PhoneInput(model.cpu().eval()).eval()
path = OUT / "model.tflite"
litert_torch.convert(phone_model, (torch.zeros(1, SIZE, SIZE, 3),)).export(str(path))

crop = transforms.Compose([transforms.CenterCrop(int(320 * EVAL_KEEP)), transforms.Resize((SIZE, SIZE))])
sample = np.stack([np.asarray(crop(photos[j]), dtype=np.float32) for j in val_idx[:150]])
with torch.no_grad():
    original = phone_model(torch.from_numpy(sample)).numpy()
interpreter = Interpreter(model_path=str(path))
interpreter.allocate_tensors()
i, o = interpreter.get_input_details()[0]["index"], interpreter.get_output_details()[0]["index"]
converted = []
for image in sample:
    interpreter.set_tensor(i, image[None])
    interpreter.invoke()
    converted.append(interpreter.get_tensor(o)[0].copy())
agreement = float((np.stack(converted).argmax(1) == original.argmax(1)).mean())
print("TFLite agreement:", agreement, "| size MB:", round(path.stat().st_size / 1e6, 1))
assert agreement >= 0.98, "Conversion changed results. Do not ship."

# %% [markdown]
# ## 5. Model card and download

# %%
classes = [MAIZE_IDS[label] for label in MAIZE_LABELS]
tested = {"healthy", "maize_leaf_blight", "maize_streak_virus"}
if Path("/content/faw_photos.zip").exists():
    tested.add("fall_armyworm")  # Trained here; ml/evaluate_uganda.py tests it on held-back photos.
card = {
    "name": "maize",
    "version": "0.3.0" if Path("/content/faw_photos.zip").exists() else "0.2.0",
    "input_size": SIZE,
    "classes": classes,
    "temperature": 1.0,
    "center_crop": 0.6,
    "default_threshold": 0.8,
    "thresholds": {c: 0.8 for c in classes},
    # Classes without training photos here stay experimental.
    "experimental_classes": sorted(c for c in classes if c not in tested),
    "removed_classes": [],
    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "metrics": {
        "check_split_before": BEFORE,
        "check_split_after": AFTER,
        "history": HISTORY,
        "tflite_agreement": agreement,
        "training_photos": len(train_idx),
    },
    "source": "Julians30/maize-disease-models mobilenetv3_best.pth, fine-tuned on Makerere/NaCRRI maize photos (CC0)",
    "licence": "Apache-2.0 base model; Ugandan photos CC0.",
    "notes": "Run ml/evaluate_uganda.py on the laptop before shipping; it updates thresholds and the experimental list.",
}
(OUT / "model_card.json").write_text(json.dumps(card, indent=2))

archive = WORK / "maize_finetuned.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
    for file in OUT.iterdir():
        bundle.write(file, f"maize/{file.name}")
from google.colab import files

files.download(str(archive))
