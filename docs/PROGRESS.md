# Progress

Last updated: 12 November 2026

## Done

- **Research:** [researh.md](../researh.md).
- **Design:** [system design](superpowers/specs/2026-11-10-crop-disease-app-design.md), covering screens, models and backend.
- **Backend** (`backend/`): FastAPI, PostgreSQL with PostGIS, SQLAdmin and Docker. It provides the partner API with keys and quotas, nearby places, advice, phone update packs and the staff admin site. The paid tier adds phone sign-in, farmer records, scan sync, reports with CSV export, and upgrade requests that staff approve. All 76 tests pass. Containers restart automatically. See [backend/README.md](../backend/README.md).
- **Models:**
  - Pretrained cassava (Google CropNet) and maize (Julians30 MobileNetV3) models were converted to TFLite in Colab with notebook 01. Converted files match the originals on 133 leaf photos.
  - Validation report: `ml/validation_report.json`, made by `ml/validate_models.py`.
  - **Cassava (CropNet):** ready. Author claimed 88%. On Ugandan photos it scored 79% as-is. Keeping the centre 60% of the photo raised it to 90% on 696 unused photos. At threshold 0.8 it answers 84% of photos with 4.8% confident wrong, within the 5% target. Brown streak passes; bacterial blight is experimental; green mite is removed. It answers "unknown" for maize, beans, noise and blank images, so it rarely invents a disease. Blurry photos drop accuracy to 24% and dark ones to 55%, so the app's quality check matters.
  - **Maize (Julians30):** not ready. Author claimed F1 0.948. On Ugandan photos it scored 50%, or 70% with centre crop, and about 1 in 4 confident answers was wrong. It labels bean leaves (79%), cassava (66%) and noise (38%) as maize diseases. It needs fine-tuning on Makerere maize photos, and it must never run without the leaf check.
- **Phone app** (`app/`): Flutter, covering every farmer screen in the design. It runs on a real phone over Wi-Fi debugging. Its 18 tests pass, including the shared verdict cases.

## Not in git

- Model files (`*.tflite`, `converted_models.zip`) are too large and are kept locally in `ml/export/`. Recreate them with notebook 01.
- Test photos (`ml/data/`) are recreated with `ml/evaluate_uganda.py download`.
- `backend/.env` holds secrets. Copy `.env.example` to create it.

## Next

1. Train the leaf-check model with notebook 02 in Colab, uploading `ml/gate_photos.zip` (ready, 42 MB).
2. Fine-tune the maize model on Ugandan photos (notebook to write).
3. Install the models in the backend with `publish-model`.
4. Connect the real TFLite engine in the app, replacing the demo engine.
5. Add paid-tier screens to the app, and connect a real sign-in code provider (iotec, if confirmed).
6. Put the backend online.
7. Tune thresholds to bring confident wrong answers under 5%.
8. Later: agronomist review of advice, real Wakiso dealer list, and checking the CropNet licence.

## Useful commands

- Backend tests: `cd backend && env -u PYTHONPATH uv run pytest`
- App tests: `cd app && flutter test`
- Android build: `cd app && JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 flutter build apk --debug`
- Phone over Wi-Fi: `~/Android/Sdk/platform-tools/adb connect <phone IP:port>`, then `adb install -r app/build/app/outputs/flutter-apk/app-debug.apk`
