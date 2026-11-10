# Crop Disease and Pest App: System Design

Date: 10 November 2026. Status: draft for approval.

Background evidence and sources are in [researh.md](../../../researh.md).

## 1. Intent

A Ugandan farmer, or an extension worker helping one, photographs leaves of a sick plant. With no internet, the phone says what the problem probably is, what to do about it, and the nearest right place to get help. When the app is unsure, it says so.

The project is for Dr. Margaret Nagwovuma's entrepreneurship course and must run as a working app. It must also show the business angle from the brief: freemium for farmers, and paid API or white-label for organisations.

## 2. Goals, non-goals and anti-goals

**Goals**

- Full diagnosis, advice and nearest-help flow works in airplane mode.
- Cassava and maize are supported, including one pest (fall armyworm).
- A real paid-style API with keys, quotas and usage tracking runs and can be demonstrated.
- Dealers and advice can be updated without releasing a new app.

**Not in version 1**

- Banana, coffee and beans.
- Local-language content (all text is externalised so it can be added).
- iPhone.
- Real payments (plans and quotas exist, money does not move).
- Farmer accounts.

**Anti-goals: failure even if the software works**

- A confident wrong answer that sends a farmer to buy a useless product.
- A pesticide dose shown without agronomist review.
- A dealer paying for a higher ranking.
- A core feature that needs internet.
- Sample dealers or unreviewed advice presented as real.
- Photos or location leaving the phone without consent.

## 3. System overview

```
PHONE (works fully offline)
  Flutter screens
    |  calls a small set of services (section 6)
  Engine: quality check > leaf gate model > crop model > plant verdict
  Local SQLite: scans, advice, places
  Bundled packs: models + content (updated when online)
          |
          | optional, only when online:
          | pack updates, consented photo uploads
          v
BACKEND (FastAPI, one server)
  Pack service      Partner API       Admin site
          |              |                |
  PostgreSQL + PostGIS        File storage (packs, model files)
          ^
          | publishes model files and metrics
ML PIPELINE (Google Colab)
  Data > clean and split > train > calibrate > export TFLite
```

The phone and the partner API run the same `.tflite` files and the same verdict rules, so offline and API answers agree.

**Repository layout**

```
app/       Flutter Android app
backend/   FastAPI service, Docker Compose
ml/        Colab notebooks and training scripts
content/   Source files for advice, places and class definitions
docs/
```

## 4. Screens

### Flow

```
First launch: Welcome > Home
Home > Photo guide (first time only) > Capture > Check photos > Result
Result > What to do > Nearby help > Place details
Home > History > Past result
Home > Disease library > What to do
Home > Settings
```

The bottom navigation has Home, History, Library and Help. A "Demo: advice not yet reviewed" banner shows on Home, Result and What to do for as long as content is unreviewed. Every screen works offline.

The support phone number is a configured value. If no real, agreed number is set, every Call extension officer button and phone shortcut is hidden, and the app says "Ask your nearest extension office" and links to Nearby help. A placeholder number is never shown.

### 4.1 Welcome (first launch only)

- App name and one-sentence purpose.
- Plain notice: "This app can be wrong. It does not replace an extension officer."
- Language choice (English only in version 1, but the control exists).
- Explanation of why camera and location are needed, shown before the system permission prompts.
- Photo-sharing choice, off by default: "Help improve the app by sharing photos."
- Continue button.

### 4.2 Home

- Large primary choice: two crop tiles, Cassava and Maize, each starting a scan.
- Offline-ready indicator, for example "Works without internet".
- Up to three recent scans with thumbnail, result and date.
- Shortcut to Nearby help.
- Extension or support phone number.

### 4.3 Photo guide

- Three or four pictures showing good and bad photos: one leaf filling the frame, daylight, no shadow, in focus.
- Text: "Take photos of up to 6 leaves from the same plant. More leaves gives a better answer."
- Continue button and "Do not show again".

### 4.4 Capture

- Live camera with a leaf-shaped frame.
- Counter: "Leaf 2 of 6".
- Shutter, flash and "Choose from gallery" controls.
- Instant warning on blurry or dark photos, with a retake option.
- Thumbnail strip with a remove option on each photo.
- "Check plant" button, enabled from one photo. With fewer than three photos, it warns that the answer will be weaker.

### 4.5 Check photos

- Each thumbnail shows a state: checking, accepted, too blurry, too dark, not a leaf, or looks like a different crop.
- Retake button on each rejected photo.
- Progress indicator while the phone analyses.
- If every photo is rejected, the screen says so and returns to Capture.

### 4.6 Result

The same screen has four states.

| State | Shows | Main buttons |
|---|---|---|
| Problem found | Plain name (plus technical name), disease or pest tag, certainty in words (Likely or Very likely), "Seen on 4 of 6 leaves", a photo, one-sentence meaning. If two problems are found, both are listed. | What to do; Find help |
| Looks healthy | Healthy message, "based on N leaves", prevention tip | Scan another plant |
| Not sure | Clear "We are not sure", possible reasons, photo tips | Retake; Call extension officer; Find help |
| Weak evidence | The Problem found layout, marked "Based on few leaves" | Add more leaves; What to do |

All states also have Save (automatic) and Share. Certainty is given in words rather than percentages, because a percentage suggests more precision than the model has.

### 4.7 What to do

- Problem name.
- Do this now: numbered steps.
- Prevent it next season.
- Do not: for example, "Do not buy a spray for this virus."
- Safety card, only for chemical advice: protective clothing, read the label, keep away from children and water. No dose in version 1.
- Review status: reviewer and date, or "Not yet reviewed".
- Find help button, labelled by need: "Find clean cuttings" or "Find a certified dealer".
- Share.

### 4.8 Nearby help

- Heading naming what is being looked for, with a filter: dealer, clean-cutting source, extension office.
- List sorted by distance. Each row shows name, type, distance, town or landmark, certified badge, "Last checked" date, and a Call button.
- A "Sample data" tag on any sample record.
- Note: "Phone first to check they have it in stock."
- If location is denied or GPS has no fix: a district picker replaces distance sorting.
- If nothing is found: extension phone number.

### 4.9 Place details

- Name, type, certified status, source and date last checked.
- Address or landmark, district, opening hours, and what it stocks by category.
- Call button.
- Directions button: opens the phone's map app, disabled with an explanation if none is available or usable.
- "Report wrong information", which is queued until online.

### 4.10 History and past result

- List of past scans with thumbnail, crop, result, date.
- Filter by crop.
- Past result reuses the Result screen and adds date and model version.
- Delete one scan or all scans.

### 4.11 Disease library

- Problems grouped by crop, with symptom photo, plain name and disease or pest tag.
- Opens the same What to do screen.

### 4.12 Settings

- Language.
- Photo sharing on or off.
- Check for updates, with last update date and pack versions.
- Delete all my data.
- About, privacy and disclaimer.

### 4.13 Error states

Each has plain text and one action: camera permission denied, storage full, model failed to load, photo unreadable.

## 5. Model architecture

### 5.1 On-device pipeline

Runs for each photo, then once per plant.

```
Photo
  > 1. Quality check (no model): blur and brightness; reject bad photos
  > 2. Leaf gate model: cassava leaf / maize leaf / other
         other, or wrong crop: reject with a reason
  > 3. Crop model for the chosen crop: class probabilities
  > 4. Calibrate scores (temperature)
After all photos:
  > 5. Plant verdict rules
```

**Models**

| Model | Classes | Backbone | Size target |
|---|---|---|---|
| Leaf gate | cassava_leaf, maize_leaf, other | MobileNetV3Small | Under 5 MB |
| Cassava | healthy, cassava_mosaic, cassava_brown_streak | Better of two below | Under 25 MB |
| Maize | healthy, maize_leaf_blight, maize_streak_virus, fall_armyworm | Better of two below | Under 25 MB |

Backbone candidates are MobileNetV3Large and EfficientNetB0, both at 224 x 224 from ImageNet weights. The winner is picked per crop on field macro-recall, then size and speed. Classification is used instead of object detection because it is simpler, smaller and needs only image-level labels.

A separate gate catches non-leaf photos and wrong crop choices, and it can be retrained alone.

Cassava bacterial blight and green mite have no open training data, and maize has diseases outside the trained classes too. These should come out as "Not sure", but calibrated thresholds often fail on unseen problems. The rate at which they get a confident label is measured and reported, and it does not block a course demo. Any release to real farmers needs an explicit unknown-rejection method tested on a legally clean set. Kaggle photos may be used for this measurement in the course evaluation only, and must not be used to tune a model intended for sale.

### 5.2 Plant verdict rules

Averaging would dilute a disease visible on only some leaves, so leaves are counted.

For each accepted leaf, take the calibrated top class and its score.

1. A leaf counts toward a class only if its score is at or above that class's threshold.
2. **Weak evidence:** a disease has exactly 1 counted leaf, or fewer than 3 leaves were accepted and a disease has at least 1 counted leaf. Weak evidence never reads "Very likely".
3. **Problem found:** at least 3 leaves were accepted and a disease has at least 2 counted leaves. It reads "Very likely" if at least 3 leaves are counted and they are at least half of accepted leaves. Otherwise it reads "Likely".
4. **Two problems:** every disease meeting rule 2 or 3 is reported, at its own level. Mosaic and brown streak can occur together.
5. **Looks healthy:** at least 3 accepted leaves, all counted as healthy.
6. **Not sure:** everything else.
7. **Experimental classes:** a class listed as experimental in the model card is capped at "Likely" and carries the note "This check is still being tested". The API returns `experimental: true` for it.

Disease rules are checked before the healthy rule. The rules are implemented in Dart and Python, and both must pass one shared `verdict_cases.json` test file.

Thresholds, the temperature and the experimental list live in each model's metadata file, so tuning does not need a new app.

**Fall armyworm ships as experimental.** It leaves that state only after the Ugandan test photos exist and it clears the release bars in section 5.4. If the photos never arrive, it stays experimental.

### 5.3 Training data

| Use | Source |
|---|---|
| Cassava | Makerere cassava, 9,103 images |
| Maize disease | Makerere maize, 15,821 images |
| Fall armyworm | KaraAgro maize, 16,552 images, using image-level labels derived from its annotations |
| Gate "other" | iBean leaves, other non-target leaves and general photos, licence-checked |

**Licence gate:** confirm CC0 on each Harvard Dataverse record before training any model intended for sale.

**Main risk: the model learning the dataset instead of the disease.** If fall armyworm images come only from KaraAgro, the model can learn "KaraAgro camera style means fall armyworm". To reduce this:

- Include KaraAgro healthy and streak images, so those classes come from both sources.
- Report results separately per source.
- Collect 50 to 100 Ugandan fall armyworm photos as a final test. If these perform poorly, label fall armyworm as experimental in the app.

### 5.4 Pipeline (`ml/`, on Google Colab)

The laptop has no GPU and 7.6 GB of memory, so training runs on Colab.

1. **Manifest:** one CSV with path, crop, class, source, region (if available).
2. **Clean:** remove near-duplicates by perceptual hash, and drop corrupt files.
3. **Split:** 70% train, 15% validation, 15% test. Split by region if metadata allows, otherwise by collection batch. Duplicates never cross splits.
4. **Train with Keras:** frozen backbone first, then unfreeze the top layers with a low learning rate. Use class weights and augmentation: flips, rotation, brightness, zoom, JPEG noise. Preprocessing lives inside the model, so the phone only needs to resize.
5. **Calibrate:** fit the temperature on validation data, and set per-class thresholds there. Thresholds are chosen to meet the confident-wrong bar first, then to answer as many photos as possible.
6. **Evaluate on the test split:** per-class recall, macro-F1, confusion matrix, confident-wrong rate, share of photos answered, per-source results.
7. **Baselines:** compare cassava against CropNet and the rpnugroho model on the same test images. For comparison only, neither is shipped.
8. **Export:** TFLite with float16 quantisation by default, with dynamic-range as an option if size is over target. Re-measure accuracy after export.
9. **Publish:** `model.tflite` plus `model_card.json` (name, version, input, classes, temperature, thresholds, metrics, SHA-256).

**Release bars (our starting targets, measured on the test split):** confident-wrong rate at or below 5% of answered photos, recall of at least 80% per class among answered photos, and at least 60% of photos answered. A class that misses a bar ships as experimental. A class with confident-wrong above 15% is removed from the app and falls through to "Not sure".

This design uses plain Keras rather than the MediaPipe Model Maker mentioned in the research, because it gives calibration control and avoids depending on a tool whose install on current Colab has not been tested.

**Consistency check:** a set of 20 reference images with expected outputs must match between Python and the phone within a small tolerance. This catches resize and colour-order bugs, which are common failures in on-device models.

**App targets (ours, to be measured):** under 2 seconds per leaf on a low-cost Android phone, CPU only.

## 6. App internals

Flutter, Android minimum API 26.

| Need | Package |
|---|---|
| Inference | `tflite_flutter`, in a background isolate |
| Camera and gallery | `camera`, `image_picker` |
| Local database | `drift` (SQLite) |
| Location | `geolocator` |
| Calling and maps | `url_launcher` |
| Background sync | `workmanager` |
| State management | Riverpod |

**Screen-to-engine contract.** Screens only use these, so the UI and engine can be built separately:

```dart
abstract class DiagnosisService {
  Future<PhotoCheck> checkPhoto(Crop crop, String imagePath);
  Future<PlantResult> diagnose(Crop crop, List<String> imagePaths);
}

abstract class AdviceRepository {
  Future<Advice> forClass(String classId, String languageCode);
  Future<List<ProblemSummary>> library(Crop crop);
}

abstract class PlacesRepository {
  Future<List<PlaceWithDistance>> nearest({
    required PlaceType type, required double lat, required double lng, int limit = 20});
  Future<List<PlaceWithDistance>> byDistrict(PlaceType type, String district);
  Future<List<String>> districts();
}

abstract class ScanRepository {
  Stream<List<ScanSummary>> watchAll({Crop? crop});
  Future<PlantResult> byId(String id);
  Future<void> delete(String id);
  Future<void> deleteAll();
}

abstract class SettingsRepository {
  Future<PackVersions> versions();
  Future<UpdateResult> checkForUpdates();
  Future<void> setPhotoSharing(bool enabled);
}
```

`PhotoCheck` has `status` (accepted, tooBlurry, tooDark, notLeaf, wrongCrop). `PlantResult` has `state` (problemFound, weakEvidence, healthy, notSure), `findings` (class, certainty, leaf count), `acceptedLeaves` and `modelVersion`.

Fake versions of these services are built first, so screens can be developed before the real engine exists.

**Local tables:** `scans`, `scan_leaves`, `advice`, `places`, `packs`, `outbox` (reports and consented uploads waiting for internet).

**Nearest place offline:** load places of the needed type, compute Haversine distance, sort. No map tiles in version 1.

**Packs.** Two kinds: a model pack and a content pack. Both ship inside the app. When online, the app checks for newer versions, downloads on Wi-Fi by default, verifies SHA-256, then swaps atomically. A failed update leaves the current pack running.

## 7. Backend

**Stack:** Python 3.12, FastAPI, PostgreSQL with PostGIS, SQLAlchemy and Alembic, `ai-edge-litert` for inference, SQLAdmin for the admin site, Docker Compose. Files are stored on server disk behind a storage interface, replaceable by S3-compatible storage later. It deploys to one small cloud server, and the hosting provider is left to the builder.

The farmer app never depends on this server for its core flow.

### 7.1 Data model

| Table | Key fields |
|---|---|
| `tenants` | name, slug, plan_id, branding (logo, colours, support phone) |
| `plans` | name, monthly_quota, rate_limit_per_minute, features |
| `api_keys` | tenant_id, key_hash, prefix, status, last_used_at |
| `usage_events` | tenant_id, endpoint, status, latency_ms, created_at |
| `classes` | id, crop, kind (disease, pest, healthy), referral_type |
| `advice` | class_id, language, steps_now, prevention, do_not, safety, review_status, reviewer, reviewed_at |
| `places` | type, name, phone, location (geography), district, landmark, hours, stocks, certified, last_checked, source, is_sample |
| `model_versions` | name, version, file, sha256, metrics, status (draft, live, retired) |
| `packs` | kind, version, file, sha256, min_app_version, published_at |
| `diagnosis_log` | tenant_id, crop, verdict, model_version, created_at. No images and no coordinates. |
| `contributions` | consent_version, crop, predicted_class, image file, created_at |
| `reports` | place_id, message, status |

Keys are stored only as hashes.

`classes.referral_type` decides where help points: cassava viruses go to clean-cutting sources, fall armyworm goes to dealers, and unknowns go to extension offices.

### 7.2 Partner API

Authenticated with `X-API-Key`. Interactive docs at `/docs`.

| Method and path | Purpose |
|---|---|
| `POST /v1/diagnose` | Multipart: `crop` and 1 to 6 images. Returns per-leaf checks, the plant verdict, referral type and model version. Images are processed in memory and discarded. |
| `GET /v1/advice/{class_id}?lang=en` | Advice, with review status |
| `GET /v1/places/nearby?type=&lat=&lng=&radius_km=` | Nearest places using PostGIS |
| `GET /v1/classes` | Supported crops and classes |
| `GET /v1/usage` | Calls used against quota |

Errors use one JSON format. Quota returns `429`, bad key `401`, bad image `422`.

### 7.3 App endpoints (no login)

| Method and path | Purpose |
|---|---|
| `GET /app/v1/packs/latest?app_version=` | Latest model and content pack versions, with URLs and hashes |
| `GET /app/v1/packs/{id}/download` | Download a pack |
| `POST /app/v1/reports` | Wrong dealer information |
| `POST /app/v1/contributions` | Consented photos only |
| `GET /app/v1/tenants/{slug}/config` | White-label branding |

These are rate-limited by IP.

### 7.4 Admin site (`/admin`, staff login)

Managed through SQLAdmin:

- Places: add, edit, bulk CSV import, mark as sample or checked.
- Advice: edit, record review.
- Tenants, plans, API keys.
- Model versions and pack publishing.
- Reports inbox, usage summary.

**Publishing a content pack** builds a SQLite file from live data, and only includes a real-mode pack if advice is reviewed. Otherwise the pack sets a demo flag, which the app uses for its banner.

**White-label** is a Flutter build flavour plus the tenant config: logo, colours, support phone, optional place filter.

## 8. Privacy and security

- Photos and GPS stay on the phone by default.
- Photo sharing needs explicit consent, can be withdrawn, and removes location metadata before upload.
- `diagnose` stores no images. Partner coordinates sent to `/places/nearby` are not logged.
- API keys are hashed and shown once. HTTPS is required.
- A data protection impact assessment is needed before any collection of location data. See section 12 of the research.

## 9. Build order

1. Scaffold the repository, define classes and sample content, and make Android builds work (the installed Java 26 may need a compatible JDK alongside it).
2. Build fake services so the screens can start.
3. Train the cassava model end to end, then the maize model, then the gate.
4. Build the real on-device engine and pass the consistency check.
5. Build the backend, packs and partner API.
6. Connect sync.
7. Test on a real low-cost Android phone in airplane mode.

## 10. Testing and demo

- **ML:** evaluation report from section 5.4, and the consistency check.
- **Backend:** pytest for API, auth, quotas and PostGIS queries.
- **App:** unit tests for verdict rules, widget tests for each Result state.
- **Demo:** phone in airplane mode, scan a cassava leaf and a maize leaf, try a non-leaf photo to show rejection, open advice and nearby help. Then call `/v1/diagnose` with an API key and show usage rise in admin.

## 11. Decisions and what is open

**Decided by the project owner**

- A running, fully functional product is required, not a demo. Backend runs online.
- Screens are specified here.
- Freemium and white-label run for real. Paid tier adds worker sign-in, farmer records and reports, and adds Plans, Sign in, Farmers, Farmer details and Reports screens. Plan upgrades are activated by staff after mobile money payment, until a merchant account exists. This supersedes the "not in version 1" entries on farmer accounts and on running these two features.
- Pilot district is Wakiso (proposed, not yet confirmed).

**Default choices made in this design, open to change**

- Flutter and Android only.
- Cassava and maize first, in one district.
- FastAPI, PostgreSQL and PostGIS.
- Keras on Colab.
- Separate gate and crop models.
- Up to six leaves.
- Words instead of percentages for certainty.
- All farmer features free in version 1. A paid farmer tier could later add human expert review of "Not sure" cases.

**Needs outside input**

- Dataset licence confirmation.
- Real dealer data for the pilot district.
- Agronomist review of advice.
- 50 to 100 Ugandan fall armyworm photos.
