# Progress

Last updated: 13 November 2026

## Done

- **Research:** [researh.md](../researh.md).
- **Design:** [system design](superpowers/specs/2026-11-10-crop-disease-app-design.md), covering screens, models and backend.
- **Backend** (`backend/`): FastAPI, PostgreSQL with PostGIS, SQLAdmin and Docker. It provides the partner API with keys and quotas, nearby places, advice, phone update packs and the staff admin site. The paid tier adds phone sign-in, farmer records, scan sync, reports with CSV export, and upgrade requests that staff approve. All 76 tests pass. Containers restart automatically. See [backend/README.md](../backend/README.md).
- **Models** (all tested on photos they never saw; files in `ml/export_v3/`, not in git):
  - **Leaf check v0.2** (own model, notebook 02): accepts 97% of cassava, 100% of maize and 97% of fall armyworm maize photos; rejects every bean leaf and 83% of noise images.
  - **Cassava v0.1** (Google CropNet, centre 60% crop, threshold 0.8): 90% correct, 4.7% of confident answers wrong. Green mite removed, bacterial blight experimental. Licence unconfirmed.
  - **Maize v0.3** (Julians30 fine-tuned in notebook 03 on Makerere/NaCRRI photos plus KaraAgro fall armyworm): 96.8% correct, 0.5% of confident answers wrong; fall armyworm found 94.8% of the time. Fall armyworm stays experimental until tested on Ugandan armyworm photos.
  - Tools: `ml/evaluate_uganda.py` (final test), `ml/validate_models.py` (stress test), `ml/make_*_photos.py` (training zips), `ml/fetch_faw.sh` (fall armyworm photos).
- **Phone app** (`app/`): Flutter, covering every farmer screen in the design. The three models run on the phone, offline (`lib/data/tflite_diagnosis.dart`); the demo engine is only a fallback. 22 tests pass. Models are copied into `app/assets/models/` from `ml/export_v3/`.

## Not in git

- Model files (`*.tflite`, `converted_models.zip`) are too large and are kept locally in `ml/export/`. Recreate them with notebook 01.
- Test photos (`ml/data/`) are recreated with `ml/evaluate_uganda.py download`.
- `backend/.env` holds secrets. Copy `.env.example` to create it.

## Next

1. Test the app end to end on the phone with the new models.
2. Add paid-tier screens to the app, and connect a real sign-in code provider.
3. Put the backend online.
4. Pests still missing: whitefly (NaCRRI photos, licence to confirm), green mite and mealybug (no open photos).
5. Later: agronomist review of advice, real Wakiso dealer list, CropNet licence, Ugandan fall armyworm photos.

## Useful commands

- Backend tests: `cd backend && env -u PYTHONPATH uv run pytest`
- App tests: `cd app && flutter test`
- Android build: `cd app && JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 flutter build apk --debug`
- Colab training: Colab cannot reach Harvard Dataverse, so photo zips are made on the laptop, split into 9 MB parts (`ml/upload/`) and uploaded.
- Phone over Wi-Fi: `~/Android/Sdk/platform-tools/adb connect <phone IP:port>`, then `adb install -r app/build/app/outputs/flutter-apk/app-debug.apk`
