import io
import json
import sqlite3
import zipfile

import numpy as np
from PIL import Image
from sqlalchemy import func, select

from app.cli import create_key
from app.config import get_settings
from app.models import (
    Advice,
    ApiKey,
    Contribution,
    DiagnosisLog,
    Pack,
    Place,
    PlaceType,
    Plan,
    ReviewStatus,
    Tenant,
    UsageEvent,
)
from app.packs import publish_content_pack, publish_model
from app.storage import LocalStorage


def leaf_bytes(seed: int = 1) -> bytes:
    pixels = np.random.default_rng(seed).integers(40, 220, (300, 300, 3), dtype=np.uint8)
    out = io.BytesIO()
    Image.fromarray(pixels).save(out, "PNG")
    return out.getvalue()


def flat_bytes(value: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (300, 300), (value, value, value)).save(out, "PNG")
    return out.getvalue()


def post_diagnose(client, auth, images, crop="cassava"):
    files = [("images", (f"{i}.png", data, "image/png")) for i, data in enumerate(images)]
    return client.post("/v1/diagnose", headers=auth, data={"crop": crop}, files=files)


def test_key_is_required_and_error_format_is_consistent(client):
    response = client.get("/v1/classes")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_unknown_and_revoked_keys_are_rejected(client, db, api_key):
    assert client.get("/v1/classes", headers={"X-API-Key": "ck_nope_nope"}).status_code == 401
    key = db.scalar(select(ApiKey))
    key.status = "revoked"
    db.commit()
    assert client.get("/v1/classes", headers={"X-API-Key": api_key}).status_code == 401


def test_only_the_key_hash_is_stored(db, api_key):
    stored = db.scalar(select(ApiKey))
    assert api_key not in (stored.key_hash, stored.prefix)
    assert len(stored.key_hash) == 64


def test_diagnose_four_leaves_finds_problem(client, auth, db):
    response = post_diagnose(client, auth, [leaf_bytes(i) for i in range(4)])
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"]["state"] == "problem_found"
    finding = body["verdict"]["findings"][0]
    assert finding == {
        "class_id": "cassava_mosaic",
        "certainty": "very_likely",
        "leaf_count": 4,
        "experimental": False,
        "referral_type": "clean_cuttings",
    }
    assert body["verdict"]["referral_type"] == "clean_cuttings"
    log = db.scalar(select(DiagnosisLog))
    assert (log.verdict, log.model_version) == ("problem_found", "1.0.0")


def test_single_leaf_is_weak_evidence(client, auth):
    body = post_diagnose(client, auth, [leaf_bytes()]).json()
    assert body["verdict"]["state"] == "weak_evidence"
    assert body["verdict"]["findings"][0]["certainty"] == "weak"


def test_experimental_pest_is_capped_and_flagged(client, auth, models):
    models.models["gate"].output = [0.01, 0.98, 0.01]
    body = post_diagnose(client, auth, [leaf_bytes(i) for i in range(4)], "maize").json()
    finding = body["verdict"]["findings"][0]
    assert finding["class_id"] == "fall_armyworm"
    assert finding["certainty"] == "likely"
    assert finding["experimental"] is True
    assert finding["referral_type"] == "dealer"


def test_gate_rejects_non_leaf_and_wrong_crop(client, auth, models):
    models.models["gate"].output = [0.01, 0.01, 0.98]
    body = post_diagnose(client, auth, [leaf_bytes()]).json()
    assert body["leaves"][0]["status"] == "not_leaf"
    assert body["verdict"]["state"] == "not_sure"
    assert body["verdict"]["referral_type"] == "extension_office"

    models.models["gate"].output = [0.01, 0.98, 0.01]
    body = post_diagnose(client, auth, [leaf_bytes()]).json()
    assert body["leaves"][0]["status"] == "wrong_crop"


def test_quality_check_rejects_dark_and_blurry(client, auth):
    body = post_diagnose(client, auth, [flat_bytes(5), flat_bytes(128)]).json()
    assert [leaf["status"] for leaf in body["leaves"]] == ["too_dark", "too_blurry"]


def test_image_limits(client, auth):
    assert post_diagnose(client, auth, [leaf_bytes()] * 7).status_code == 422
    response = post_diagnose(client, auth, [b"this is not an image"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_image"


def test_missing_model_returns_503(client, auth, models):
    del models.models["cassava"]
    response = post_diagnose(client, auth, [leaf_bytes()])
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"


def test_monthly_quota_returns_429(client, db, api_key):
    plan = db.scalar(select(Plan).where(Plan.name == "starter"))
    plan.monthly_quota = 2
    db.commit()
    headers = {"X-API-Key": api_key}
    assert client.get("/v1/classes", headers=headers).status_code == 200
    assert client.get("/v1/classes", headers=headers).status_code == 200
    response = client.get("/v1/classes", headers=headers)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "quota_exceeded"
    usage = client.get("/v1/usage", headers=headers).json()
    assert (usage["used"], usage["remaining"]) == (2, 0)


def test_rate_limit_returns_429_with_retry_after(client, db, api_key):
    plan = db.scalar(select(Plan).where(Plan.name == "starter"))
    plan.rate_limit_per_minute = 1
    db.commit()
    headers = {"X-API-Key": api_key}
    assert client.get("/v1/classes", headers=headers).status_code == 200
    response = client.get("/v1/classes", headers=headers)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert "retry-after" in response.headers


def test_usage_is_separate_per_tenant(client, db, auth):
    other = create_key(db, "other", "Other", "free")
    client.get("/v1/classes", headers=auth)
    assert client.get("/v1/usage", headers={"X-API-Key": other}).json()["used"] == 0


def test_usage_log_records_route_template_not_coordinates(client, auth, db):
    client.get(
        "/v1/places/nearby",
        headers=auth,
        params={"type": "dealer", "lat": 0.4, "lng": 32.57},
    )
    event = db.scalar(select(UsageEvent))
    assert event.endpoint == "/v1/places/nearby"
    assert event.status == 200


def test_nearby_sorts_by_real_distance_and_filters(client, auth):
    response = client.get(
        "/v1/places/nearby",
        headers=auth,
        params={"type": "dealer", "lat": 0.3960, "lng": 32.5740, "radius_km": 50},
    )
    assert response.status_code == 200
    places = response.json()["places"]
    assert [p["name"] for p in places] == ["SAMPLE Agro-dealer A", "SAMPLE Agro-dealer B"]
    assert places[0]["distance_km"] < 0.01
    # 0.054 and 0.036 degrees apart near the equator is about 7.2 km.
    assert 6.5 < places[1]["distance_km"] < 8
    assert all(p["is_sample"] for p in places)


def test_nearby_respects_radius(client, auth):
    body = client.get(
        "/v1/places/nearby",
        headers=auth,
        params={"type": "dealer", "lat": 0.3960, "lng": 32.5740, "radius_km": 1},
    ).json()
    assert len(body["places"]) == 1


def test_nearby_validates_coordinates(client, auth):
    response = client.get(
        "/v1/places/nearby", headers=auth, params={"type": "dealer", "lat": 95, "lng": 32}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_advice_shows_review_status_and_no_dose(client, auth):
    body = client.get("/v1/advice/fall_armyworm", headers=auth).json()
    assert body["review_status"] == "unreviewed"
    assert " ml" not in json.dumps(body)
    assert client.get("/v1/advice/nope", headers=auth).status_code == 404


def test_content_pack_is_demo_until_reviewed_and_real(db, client):
    pack = publish_content_pack(db, get_settings())
    path = LocalStorage(get_settings().storage_dir).path(pack.file)
    demo = sqlite3.connect(path).execute(
        "SELECT value FROM metadata WHERE key='demo'"
    ).fetchone()[0]
    assert demo == "1"

    for advice in db.scalars(select(Advice)):
        advice.review_status = ReviewStatus.reviewed
    for place in db.scalars(select(Place)):
        place.is_sample = False
    db.commit()
    second = publish_content_pack(db, get_settings())
    assert second.version == "2"
    path = LocalStorage(get_settings().storage_dir).path(second.file)
    connection = sqlite3.connect(path)
    assert connection.execute("SELECT value FROM metadata WHERE key='demo'").fetchone()[0] == "0"
    assert connection.execute("SELECT count(*) FROM classes").fetchone()[0] == 15


def test_latest_pack_download_matches_hash(db, client):
    publish_content_pack(db, get_settings())
    second = publish_content_pack(db, get_settings())
    body = client.get("/app/v1/packs/latest", params={"app_version": "1.0.0"}).json()
    assert [p["version"] for p in body["packs"]] == [second.version]
    download = client.get(body["packs"][0]["download_url"])
    assert download.status_code == 200
    assert download.headers["x-content-sha256"] == second.sha256


def test_pack_respects_min_app_version(db, client):
    pack = publish_content_pack(db, get_settings())
    pack.min_app_version = "2.0.0"
    db.commit()
    body = client.get("/app/v1/packs/latest", params={"app_version": "1.9.0"}).json()
    assert body["packs"] == []


def test_publish_model_installs_and_retires_previous(db, tmp_path):
    def card(version):
        return {
            "name": "cassava",
            "version": version,
            "input_size": 224,
            "classes": ["healthy"],
            "temperature": 1.0,
            "thresholds": {"healthy": 0.7},
        }

    source = tmp_path / "m"
    source.mkdir()
    (source / "model.tflite").write_bytes(b"fake")
    (source / "model_card.json").write_text(json.dumps(card("1.0.0")))
    first = publish_model(db, get_settings(), source)
    path = LocalStorage(get_settings().storage_dir).path(first.file)
    assert set(zipfile.ZipFile(path).namelist()) == {"model.tflite", "model_card.json"}

    (source / "model_card.json").write_text(json.dumps(card("1.1.0")))
    publish_model(db, get_settings(), source)
    from app.models import ModelStatus, ModelVersion

    statuses = {m.version: m.status for m in db.scalars(select(ModelVersion))}
    assert statuses == {"1.0.0": ModelStatus.retired, "1.1.0": ModelStatus.live}


def test_contribution_strips_gps_metadata(client, db):
    image = Image.fromarray(np.random.default_rng(1).integers(40, 220, (100, 100, 3), dtype=np.uint8))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"
    exif.get_ifd(0x8825)[1] = "N"
    out = io.BytesIO()
    image.save(out, "JPEG", exif=exif)
    assert Image.open(io.BytesIO(out.getvalue())).getexif()

    response = client.post(
        "/app/v1/contributions",
        data={"consent_version": "1", "crop": "cassava"},
        files={"image": ("a.jpg", out.getvalue(), "image/jpeg")},
    )
    assert response.status_code == 201
    stored = db.scalar(select(Contribution))
    saved = Image.open(LocalStorage(get_settings().storage_dir).path(stored.file))
    assert not saved.getexif()


def test_contribution_requires_consent(client):
    response = client.post(
        "/app/v1/contributions",
        data={"crop": "cassava"},
        files={"image": ("a.png", leaf_bytes(), "image/png")},
    )
    assert response.status_code == 422


def test_report_needs_real_place(client, db):
    place = db.scalar(select(Place).where(Place.type == PlaceType.dealer))
    good = client.post("/app/v1/reports", json={"place_id": place.id, "message": "Shop has moved"})
    assert good.status_code == 201
    bad = client.post("/app/v1/reports", json={"place_id": 99999, "message": "Shop has moved"})
    assert bad.status_code == 404


def test_tenant_config(client, db, api_key):
    tenant = db.scalar(select(Tenant))
    tenant.primary_color = "#0a7"
    db.commit()
    body = client.get("/app/v1/tenants/acme/config").json()
    assert (body["name"], body["primary_color"]) == ("Acme Agri", "#0a7")
    assert client.get("/app/v1/tenants/none/config").status_code == 404


def test_app_rate_limit(client):
    client.app.state.app_limiter.limit = 1
    client.get("/app/v1/packs/latest", params={"app_version": "1.0.0"})
    response = client.get("/app/v1/packs/latest", params={"app_version": "1.0.0"})
    assert response.status_code == 429


def login(client):
    return client.post(
        "/admin/login",
        data={"username": "staff", "password": "test-password"},
        follow_redirects=False,
    )


def test_admin_requires_login(client):
    response = client.get("/admin/place/list", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "/admin/login" in response.headers["location"]
    bad = client.post(
        "/admin/login", data={"username": "staff", "password": "wrong"}, follow_redirects=False
    )
    assert bad.status_code == 400


def test_admin_pages_render_after_login(client):
    assert login(client).status_code in (302, 303)
    for page in ("tenant", "plan", "api-key", "problem-class", "advice", "place", "pack", "report"):
        assert client.get(f"/admin/{page}/list").status_code == 200, page


def test_admin_generates_working_key(client, db, api_key):
    login(client)
    tenant = db.scalar(select(Tenant))
    before = db.scalar(select(func.count()).select_from(ApiKey))
    response = client.get(f"/admin/tenant/action/generate-key?pks={tenant.id}")
    assert response.status_code == 200
    assert db.scalar(select(func.count()).select_from(ApiKey)) == before + 1
    raw_key = response.text.split("<pre>")[1].split("</pre>")[0]
    assert client.get("/v1/usage", headers={"X-API-Key": raw_key}).status_code == 200


def test_admin_actions_require_login(client, db, api_key):
    tenant = db.scalar(select(Tenant))
    before = db.scalar(select(func.count()).select_from(ApiKey))
    response = client.get(
        f"/admin/tenant/action/generate-key?pks={tenant.id}", follow_redirects=False
    )
    assert response.status_code in (302, 303)
    assert db.scalar(select(func.count()).select_from(ApiKey)) == before
    client.get("/admin/pack/action/publish-content", follow_redirects=False)
    assert db.scalar(select(func.count()).select_from(Pack)) == 0


def test_admin_publishes_content_pack(client, db):
    login(client)
    response = client.get("/admin/pack/action/publish-content", follow_redirects=False)
    assert response.status_code == 303
    assert db.scalar(select(func.count()).select_from(Pack)) == 1


def test_healthz(client):
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["models"] == ["cassava", "gate", "maize"]
