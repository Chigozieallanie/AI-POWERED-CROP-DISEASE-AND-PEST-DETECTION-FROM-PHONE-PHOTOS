# Progress

Last updated: 10 November 2026

## Done

- **Research:** [researh.md](../researh.md).
- **Design:** [system design](superpowers/specs/2026-11-10-crop-disease-app-design.md), covering screens, models and backend.
- **Backend** (`backend/`): FastAPI, PostgreSQL with PostGIS, SQLAdmin and Docker. It provides the partner API with keys and quotas, nearby places, advice, phone update packs and the staff admin site. All 50 tests pass. See [backend/README.md](../backend/README.md).
- **Models:**
  - Pretrained cassava (Google CropNet) and maize (Julians30 MobileNetV3) models were converted to TFLite in Colab with notebook 01. Converted files match the originals on 133 leaf photos.
  - The cassava model was tested on 900 Ugandan photos from Makerere and NaCRRI. It was 80% correct overall: mosaic 94%, healthy 85%, brown streak 63%. Brown streak is experimental, and green mite was removed for too many confident wrong answers. 11% of confident answers were wrong, above the 5% target.
- **Phone app** (`app/`): Flutter, covering every farmer screen in the design. It runs on a real phone over Wi-Fi debugging. Its 18 tests pass, including the shared verdict cases.

## Not in git

- Model files (`*.tflite`, `converted_models.zip`) are too large and are kept locally in `ml/export/`. Recreate them with notebook 01.
- Test photos (`ml/data/`) are recreated with `ml/evaluate_uganda.py download`.
- `backend/.env` holds secrets. Copy `.env.example` to create it.

## Next

1. Finish downloading maize photos, then run `ml/evaluate_uganda.py evaluate ../ml/export maize`.
2. Run `ml/make_gate_photos.py`, then train the leaf-check model with notebook 02 in Colab.
3. Install the models in the backend with `publish-model`.
4. Connect the real TFLite engine in the app, replacing the demo engine.
5. Build the paid tier: sign-in, farmer records, reports and upgrade requests.
6. Tune thresholds to bring confident wrong answers under 5%.
7. Later: agronomist review of advice, real Wakiso dealer list, and checking the CropNet licence.

## Useful commands

- Backend tests: `cd backend && env -u PYTHONPATH uv run pytest`
- App tests: `cd app && flutter test`
- Android build: `cd app && JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 flutter build apk --debug`
- Phone over Wi-Fi: `~/Android/Sdk/platform-tools/adb connect <phone IP:port>`, then `adb install -r app/build/app/outputs/flutter-apk/app-debug.apk`
