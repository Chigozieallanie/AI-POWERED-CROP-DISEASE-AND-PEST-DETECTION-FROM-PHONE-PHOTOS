from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.cli import create_key, create_worker
from app.models import OtpCode, Plan, Tenant, UpgradeRequest, WorkerSession
from app.workers_auth import get_sender, normalise_phone

PHONE = "0772123456"
E164 = "+256772123456"


class FakeSender:
    def __init__(self) -> None:
        self.sent: dict[str, str] = {}

    def send(self, phone: str, code: str) -> None:
        self.sent[phone] = code


@pytest.fixture
def sender(client):
    fake = FakeSender()
    client.app.dependency_overrides[get_sender] = lambda: fake
    yield fake
    client.app.dependency_overrides.clear()


@pytest.fixture
def org(db):
    create_key(db, "agri", "Agri Co", "starter")
    return db.scalar(select(Tenant).where(Tenant.slug == "agri"))


@pytest.fixture
def admin(db, org):
    return create_worker(db, "agri", PHONE, "Amina", "admin")


def sign_in(client, sender, phone=PHONE):
    assert client.post("/app/v1/auth/request-code", json={"phone": phone}).status_code == 202
    response = client.post(
        "/app/v1/auth/verify", json={"phone": phone, "code": sender.sent[normalise_phone(phone, "256")]}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def scan_body(client_id="scan-000001", verdict="problem_found", class_id="cassava_mosaic"):
    return {
        "client_id": client_id,
        "crop": "cassava",
        "verdict": verdict,
        "findings": [{"class_id": class_id, "certainty": "likely", "leaf_count": 3}] if class_id else [],
        "model_version": "0.1.0",
        "scanned_at": datetime.now(UTC).isoformat(),
    }


@pytest.mark.parametrize(
    "raw", ["0772123456", "772123456", "256772123456", "+256 772 123 456", "00256772123456"]
)
def test_phone_formats_normalise(raw):
    assert normalise_phone(raw, "256") == E164


def test_invalid_phone_rejected(client, sender):
    response = client.post("/app/v1/auth/request-code", json={"phone": "07abc12345"})
    assert response.status_code == 422


def test_sign_in_flow_and_me(client, sender, admin):
    headers = sign_in(client, sender)
    me = client.get("/app/v1/me", headers=headers).json()
    assert me["worker"]["phone"] == E164
    assert (me["organisation"], me["plan"], me["worker_tools"]) == ("Agri Co", "starter", True)


def test_codes_are_hashed(client, sender, admin, db):
    client.post("/app/v1/auth/request-code", json={"phone": PHONE})
    stored = db.scalar(select(OtpCode))
    assert sender.sent[E164] not in stored.code_hash


def test_unknown_number_gets_same_answer_and_no_code(client, sender, admin):
    response = client.post("/app/v1/auth/request-code", json={"phone": "0700000001"})
    assert response.status_code == 202
    assert "+256700000001" not in sender.sent


def test_wrong_code_and_attempt_limit(client, sender, admin):
    client.post("/app/v1/auth/request-code", json={"phone": PHONE})
    right = sender.sent[E164]
    wrong = "000000" if right != "000000" else "111111"
    for _ in range(5):
        assert client.post("/app/v1/auth/verify", json={"phone": PHONE, "code": wrong}).status_code == 401
    # After 5 wrong tries even the right code fails.
    assert client.post("/app/v1/auth/verify", json={"phone": PHONE, "code": right}).status_code == 401


def test_code_works_once_and_expires(client, sender, admin, db):
    sign_in(client, sender)
    used = sender.sent[E164]
    assert client.post("/app/v1/auth/verify", json={"phone": PHONE, "code": used}).status_code == 401

    client.post("/app/v1/auth/request-code", json={"phone": PHONE})
    db.execute(update(OtpCode).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    db.commit()
    assert client.post("/app/v1/auth/verify", json={"phone": PHONE, "code": sender.sent[E164]}).status_code == 401


def test_code_request_rate_limit(client, sender, admin):
    for _ in range(3):
        assert client.post("/app/v1/auth/request-code", json={"phone": PHONE}).status_code == 202
    assert client.post("/app/v1/auth/request-code", json={"phone": PHONE}).status_code == 429


def test_sign_out_ends_session(client, sender, admin, db):
    headers = sign_in(client, sender)
    assert client.post("/app/v1/auth/sign-out", headers=headers).status_code == 204
    assert client.get("/app/v1/me", headers=headers).status_code == 401
    assert db.scalar(select(func.count()).select_from(WorkerSession)) == 0


def test_inactive_worker_and_missing_token(client, sender, admin, db):
    assert client.get("/app/v1/me").status_code == 401
    headers = sign_in(client, sender)
    admin.is_active = False
    db.commit()
    assert client.get("/app/v1/me", headers=headers).status_code == 401


def test_free_plan_blocks_farmer_records(client, sender, db):
    create_key(db, "freeorg", "Free Org", "free")
    create_worker(db, "freeorg", "0772000111", "Bo", "worker")
    headers = sign_in(client, sender, "0772000111")
    response = client.get("/app/v1/farmers", headers=headers)
    assert response.status_code == 402
    assert response.json()["error"]["code"] == "plan_required"


def test_farmer_crud_and_search(client, sender, admin):
    headers = sign_in(client, sender)
    created = client.post(
        "/app/v1/farmers",
        headers=headers,
        json={"name": "Okello John", "phone": "0701111222", "village": "Kakiri", "district": "Wakiso"},
    )
    assert created.status_code == 201
    farmer = created.json()
    assert farmer["phone"] == "+256701111222"
    client.post("/app/v1/farmers", headers=headers, json={"name": "Nakato Sarah", "village": "Matugga"})

    assert [f["name"] for f in client.get("/app/v1/farmers", headers=headers, params={"q": "kakiri"}).json()] == [
        "Okello John"
    ]
    updated = client.put(f"/app/v1/farmers/{farmer['id']}", headers=headers, json={"name": "Okello J.", "village": "Kakiri"})
    assert updated.json()["name"] == "Okello J."
    assert client.delete(f"/app/v1/farmers/{farmer['id']}", headers=headers).status_code == 204
    assert client.get(f"/app/v1/farmers/{farmer['id']}", headers=headers).status_code == 404


def test_only_admin_deletes_farmers(client, sender, admin, db):
    create_worker(db, "agri", "0772555666", "Wasswa", "worker")
    farmer = client.post("/app/v1/farmers", headers=sign_in(client, sender), json={"name": "X"}).json()
    worker_headers = sign_in(client, sender, "0772555666")
    assert client.delete(f"/app/v1/farmers/{farmer['id']}", headers=worker_headers).status_code == 403


def test_organisations_cannot_see_each_others_farmers(client, sender, admin, db):
    farmer = client.post("/app/v1/farmers", headers=sign_in(client, sender), json={"name": "Private"}).json()
    create_key(db, "rival", "Rival", "starter")
    create_worker(db, "rival", "0772999888", "Eve", "admin")
    rival = sign_in(client, sender, "0772999888")
    assert client.get("/app/v1/farmers", headers=rival).json() == []
    assert client.get(f"/app/v1/farmers/{farmer['id']}", headers=rival).status_code == 404
    assert client.post(f"/app/v1/farmers/{farmer['id']}/scans", headers=rival, json=scan_body()).status_code == 404


def test_scan_sync_is_idempotent(client, sender, admin):
    headers = sign_in(client, sender)
    farmer = client.post("/app/v1/farmers", headers=headers, json={"name": "A"}).json()
    url = f"/app/v1/farmers/{farmer['id']}/scans"
    first = client.post(url, headers=headers, json=scan_body())
    again = client.post(url, headers=headers, json=scan_body())
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"]
    assert first.json()["primary_class"] == "cassava_mosaic"
    assert len(client.get(url, headers=headers).json()) == 1


def test_scan_validation(client, sender, admin):
    headers = sign_in(client, sender)
    farmer = client.post("/app/v1/farmers", headers=headers, json={"name": "A"}).json()
    bad = scan_body(verdict="cured")
    assert client.post(f"/app/v1/farmers/{farmer['id']}/scans", headers=headers, json=bad).status_code == 422


def test_report_summary_and_export(client, sender, admin):
    headers = sign_in(client, sender)
    a = client.post("/app/v1/farmers", headers=headers, json={"name": "=HYPERLINK(1)", "village": "Kakiri"}).json()
    b = client.post("/app/v1/farmers", headers=headers, json={"name": "B", "village": "Matugga"}).json()
    client.post(f"/app/v1/farmers/{a['id']}/scans", headers=headers, json=scan_body("scan-a-00001"))
    client.post(f"/app/v1/farmers/{a['id']}/scans", headers=headers, json=scan_body("scan-a-00002"))
    client.post(f"/app/v1/farmers/{b['id']}/scans", headers=headers, json=scan_body("scan-b-00001", "healthy", None))

    summary = client.get("/app/v1/reports/summary", headers=headers).json()
    assert (summary["scans"], summary["farmers"]) == (3, 2)
    assert {"village": "Kakiri", "class_id": "cassava_mosaic", "count": 2} in summary["by_village"]

    export = client.get("/app/v1/reports/export.csv", headers=headers)
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    lines = export.text.strip().splitlines()
    assert len(lines) == 4
    assert "'=HYPERLINK(1)" in export.text  # Formula cells are neutralised.


def test_report_range_validation(client, sender, admin):
    headers = sign_in(client, sender)
    response = client.get("/app/v1/reports/summary", headers=headers, params={"start": "2026-02-01", "end": "2026-01-01"})
    assert response.status_code == 422


def test_export_is_admin_only(client, sender, admin, db):
    create_worker(db, "agri", "0772555666", "Wasswa", "worker")
    assert client.get("/app/v1/reports/export.csv", headers=sign_in(client, sender, "0772555666")).status_code == 403


def test_upgrade_request_and_staff_approval(client, sender, db):
    create_key(db, "freeorg", "Free Org", "free")
    create_worker(db, "freeorg", "0772000111", "Bo", "admin")
    headers = sign_in(client, sender, "0772000111")
    plans = client.get("/app/v1/plans").json()
    assert [p["name"] for p in plans] == ["free", "starter", "business"]
    starter = next(p for p in plans if p["name"] == "starter")

    free_plan = next(p for p in plans if p["name"] == "free")
    bad = client.post("/app/v1/upgrade-requests", headers=headers,
                      json={"plan_id": free_plan["id"], "payment_reference": "MM123456", "payer_phone": "0772000111"})
    assert bad.status_code == 422

    body = {"plan_id": starter["id"], "payment_reference": "MM123456", "payer_phone": "0772000111"}
    created = client.post("/app/v1/upgrade-requests", headers=headers, json=body)
    assert created.status_code == 201
    assert client.post("/app/v1/upgrade-requests", headers=headers, json=body).status_code == 409

    client.post("/admin/login", data={"username": "staff", "password": "test-password"})
    approved = client.get(
        f"/admin/upgrade-request/action/approve?pks={created.json()['id']}", follow_redirects=False
    )
    assert approved.status_code == 303
    db.expire_all()
    assert db.scalar(select(Tenant).where(Tenant.slug == "freeorg")).plan.name == "starter"
    assert db.scalar(select(UpgradeRequest)).status == "approved"
    assert client.get("/app/v1/farmers", headers=headers).status_code == 200
    # A decided request cannot be approved twice.
    again = client.get(f"/admin/upgrade-request/action/approve?pks={created.json()['id']}", follow_redirects=False)
    assert again.status_code == 409


def test_upgrade_approval_requires_staff_login(client, sender, db):
    create_key(db, "freeorg", "Free Org", "free")
    create_worker(db, "freeorg", "0772000111", "Bo", "admin")
    headers = sign_in(client, sender, "0772000111")
    starter = db.scalar(select(Plan).where(Plan.name == "starter"))
    created = client.post(
        "/app/v1/upgrade-requests", headers=headers,
        json={"plan_id": starter.id, "payment_reference": "MM1", "payer_phone": "0772000111"},
    )
    assert created.status_code == 422  # Reference too short.
    created = client.post(
        "/app/v1/upgrade-requests", headers=headers,
        json={"plan_id": starter.id, "payment_reference": "MM123456", "payer_phone": "0772000111"},
    ).json()
    response = client.get(f"/admin/upgrade-request/action/approve?pks={created['id']}", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert db.scalar(select(Tenant).where(Tenant.slug == "freeorg")).plan.name == "free"


def test_admin_pages_for_paid_tier(client):
    client.post("/admin/login", data={"username": "staff", "password": "test-password"})
    for page in ("worker", "farmer", "farmer-scan", "upgrade-request"):
        assert client.get(f"/admin/{page}/list").status_code == 200, page
