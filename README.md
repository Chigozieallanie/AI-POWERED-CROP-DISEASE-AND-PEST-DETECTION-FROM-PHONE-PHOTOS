# CropCheck 🌱

**CropCheck** is a phone-based crop health project built to help farmers and field workers make a first check for crop disease or pest damage from photos. The app is designed to run its image models on the phone, so a connection to the backend is not required for diagnosis. It also brings together practical advice and nearby agricultural support.

This repository contains the Flutter app, a FastAPI service, and the machine-learning research and evaluation tools behind the project. It is an active project, so some parts—especially model packaging, agronomy review, and production deployment—are still in progress.

## What it can do

- Take or choose crop photos and run an on-device check for supported crop types.
- Show a diagnosis result and related guidance from bundled content.
- Browse saved checks, crop information, and nearby places.
- Use phone location to help find nearby agricultural services.
- Run a separate backend for partner integrations, app content/model updates, place data, and staff administration.

The current app and model work focuses on **cassava and maize**, including fall armyworm checks for maize. The diagnosis is an aid—not a substitute for an agronomist or extension worker. If a photo is unclear or a result is uncertain, seek local expert advice before taking action.

## How the pieces fit together

```text
app/       Flutter mobile app and on-device inference
backend/  FastAPI service, PostgreSQL/PostGIS, partner API and admin tools
ml/       Model preparation, evaluation and validation scripts/notebooks
content/  Advice, crop classes, plans, sample locations and example cases
docs/     Project progress and design notes
```

The app is intended to perform diagnosis offline with TensorFlow Lite models. The backend is complementary: it provides partner and staff features, and can publish content and model updates to phones. See [`backend/README.md`](backend/README.md) for backend-specific details and [`docs/PROGRESS.md`](docs/PROGRESS.md) for the latest recorded project status.

## Try the mobile app

### Requirements

- Flutter SDK compatible with the version in `app/pubspec.yaml`
- Android toolchain/device or emulator for the Android build

From the repository root:

```bash
cd app
flutter pub get
flutter test
flutter run
```

To build a debug APK:

```bash
cd app
flutter build apk --debug
```

### Model files

The app expects model assets under `app/assets/models/` (gate, cassava, and maize). Large trained model artifacts are not necessarily committed to this repository; check `docs/PROGRESS.md` and the model export instructions in `ml/` before expecting on-device diagnosis to work in a fresh checkout. The app includes a demo fallback, but that should not be mistaken for a trained production model.

## Run the backend

The backend uses Docker Compose to start the API and a PostgreSQL/PostGIS database.

### Requirements

- Docker and Docker Compose
- Copy the example environment file and replace the example credentials/secrets

```bash
cd backend
cp .env.example .env
```

Edit `.env` and set strong, private values for every placeholder. Then start and seed the services:

```bash
docker compose up -d --build
docker compose exec api python -m app.cli seed
docker compose exec api python -m app.cli publish-content
```

When the services are running:

- API documentation: <http://127.0.0.1:8010/docs>
- Staff admin: <http://127.0.0.1:8010/admin>

Do not commit `.env` or use the example credentials outside local development. For staff commands, tests, and deployment notes, see [`backend/README.md`](backend/README.md).

## Machine-learning work

The `ml/` directory contains evaluation and validation scripts, dataset preparation helpers, and notebooks. Project notes describe work on image acceptance checks and cassava/maize classifiers. Model scores recorded in the progress notes come from specific evaluation sets; they are not a guarantee of accuracy on every farm, phone, region, or lighting condition.

Datasets and pretrained models can have usage restrictions. Check their original licenses and the research notes in [`researh.md`](researh.md) before reusing data, code, or model weights. Do not treat experimental or unreviewed pesticide recommendations as authoritative guidance.

## Tests

Run the Flutter tests with:

```bash
cd app
flutter test
```

The backend tests require the configured PostGIS test database. Follow the setup in [`backend/README.md`](backend/README.md), then run:

```bash
cd backend
env -u PYTHONPATH uv run pytest
```

## Current limitations and next steps

This is still being developed. The project progress notes call out work such as end-to-end testing with packaged models, agronomist review of advice, a verified local agro-dealer list, and a production SMS provider for worker sign-in. Some potential pest classes and local-language support also need more data and validation.

Because crop conditions vary and a wrong treatment can cause harm, use the app as an initial screening and information tool—not as a definitive diagnosis or pesticide prescription.

## Contributing

Issues, suggestions, and contributions are welcome. For changes to diagnosis or farming advice, please include the source of the data or recommendation and explain how it was validated. Advice intended for farmers should be reviewed by qualified local agricultural specialists before release.

## License

No repository-wide license file was present when this README was prepared. Until a license is added, do not assume the project code, datasets, or model artifacts are available for unrestricted reuse. Check each component's applicable license and contact the maintainers if you need clarification.
