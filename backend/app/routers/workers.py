"""Paid tier: worker sign-in, farmer records, scan sync, reports and upgrades."""

import csv
import io
from datetime import UTC, date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.errors import ApiError
from app.models import (
    Crop,
    Farmer,
    FarmerScan,
    Plan,
    UpgradeRequest,
    UpgradeStatus,
    Worker,
    WorkerSession,
)
from app.security import client_ip
from app.workers_auth import (
    CodeSender,
    admin_worker,
    current_session,
    current_worker,
    get_sender,
    normalise_phone,
    paid_worker,
    request_code,
    verify_code,
)

VERDICTS = r"^(problem_found|weak_evidence|healthy|not_sure)$"


def rate_limited(request: Request) -> None:
    if not request.app.state.app_limiter.allow(client_ip(request)):
        raise ApiError(429, "rate_limited", "Too many requests this minute.")


router = APIRouter(prefix="/app/v1", tags=["Paid tier"], dependencies=[Depends(rate_limited)])


# Schemas -------------------------------------------------------------------


class PhoneIn(BaseModel):
    phone: str = Field(min_length=7, max_length=20)


class VerifyIn(PhoneIn):
    code: str = Field(pattern=r"^\d{6}$")


class WorkerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    role: str


class MeOut(BaseModel):
    worker: WorkerOut
    organisation: str
    plan: str
    worker_tools: bool


class SignedInOut(MeOut):
    token: str


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price_ugx: int
    monthly_quota: int
    features: dict


class FarmerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    village: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


class FarmerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str | None
    village: str | None
    district: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class FindingIn(BaseModel):
    class_id: str = Field(max_length=64)
    certainty: str = Field(pattern=r"^(weak|likely|very_likely)$")
    leaf_count: int = Field(ge=1, le=6)


class ScanIn(BaseModel):
    client_id: str = Field(min_length=8, max_length=64)
    crop: Crop
    verdict: str = Field(pattern=VERDICTS)
    findings: list[FindingIn] = Field(default_factory=list, max_length=6)
    model_version: str = Field(max_length=32)
    scanned_at: datetime


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: str
    farmer_id: int
    crop: str
    verdict: str
    primary_class: str | None
    findings: list
    model_version: str
    scanned_at: datetime


class UpgradeIn(BaseModel):
    plan_id: int
    payment_reference: str = Field(min_length=4, max_length=100)
    payer_phone: str = Field(min_length=7, max_length=20)


class UpgradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    payment_reference: str
    payer_phone: str
    status: str
    staff_note: str | None
    created_at: datetime


def _me(worker: Worker) -> dict:
    return {
        "worker": WorkerOut.model_validate(worker),
        "organisation": worker.tenant.name,
        "plan": worker.tenant.plan.name,
        "worker_tools": bool((worker.tenant.plan.features or {}).get("worker_tools")),
    }


# Sign-in -------------------------------------------------------------------


@router.post("/auth/request-code", status_code=202)
def auth_request_code(
    body: PhoneIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    sender: CodeSender = Depends(get_sender),
) -> dict:
    request_code(db, settings, sender, normalise_phone(body.phone, settings.default_country_code))
    return {"message": "If this number belongs to a worker, a code has been sent."}


@router.post("/auth/verify", response_model=SignedInOut)
def auth_verify(
    body: VerifyIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict:
    token, worker = verify_code(db, settings, normalise_phone(body.phone, settings.default_country_code), body.code)
    return {"token": token, **_me(worker)}


@router.post("/auth/sign-out", status_code=204)
def auth_sign_out(session: WorkerSession = Depends(current_session), db: Session = Depends(get_db)) -> Response:
    db.execute(delete(WorkerSession).where(WorkerSession.id == session.id))
    db.commit()
    return Response(status_code=204)


@router.get("/me", response_model=MeOut)
def me(worker: Worker = Depends(current_worker)) -> dict:
    return _me(worker)


# Plans and upgrades ----------------------------------------------------------


@router.get("/plans", response_model=list[PlanOut])
def plans(db: Session = Depends(get_db)) -> list[Plan]:
    return list(db.scalars(select(Plan).order_by(Plan.price_ugx)))


@router.post("/upgrade-requests", response_model=UpgradeOut, status_code=201)
def create_upgrade(
    body: UpgradeIn,
    worker: Worker = Depends(current_worker),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UpgradeRequest:
    plan = db.get(Plan, body.plan_id)
    if plan is None or plan.price_ugx <= 0:
        raise ApiError(422, "invalid_plan", "Choose a paid plan.")
    pending = db.scalar(
        select(func.count())
        .select_from(UpgradeRequest)
        .where(UpgradeRequest.tenant_id == worker.tenant_id, UpgradeRequest.status == UpgradeStatus.pending)
    )
    if pending:
        raise ApiError(409, "already_pending", "An upgrade request is already waiting for staff.")
    request = UpgradeRequest(
        tenant_id=worker.tenant_id,
        requested_by=worker.id,
        plan_id=plan.id,
        payment_reference=body.payment_reference.strip(),
        payer_phone=normalise_phone(body.payer_phone, settings.default_country_code),
    )
    db.add(request)
    db.commit()
    return request


@router.get("/upgrade-requests", response_model=list[UpgradeOut])
def list_upgrades(worker: Worker = Depends(current_worker), db: Session = Depends(get_db)) -> list[UpgradeRequest]:
    return list(
        db.scalars(
            select(UpgradeRequest)
            .where(UpgradeRequest.tenant_id == worker.tenant_id)
            .order_by(UpgradeRequest.created_at.desc())
        )
    )


# Farmers ---------------------------------------------------------------------


def _farmer(db: Session, worker: Worker, farmer_id: int) -> Farmer:
    farmer = db.get(Farmer, farmer_id)
    # Another organisation's farmer looks the same as a missing one.
    if farmer is None or farmer.tenant_id != worker.tenant_id:
        raise ApiError(404, "not_found", "That farmer does not exist.")
    return farmer


def _clean_farmer(body: FarmerIn, settings: Settings) -> dict:
    data = body.model_dump()
    if data["phone"]:
        data["phone"] = normalise_phone(data["phone"], settings.default_country_code)
    return data


@router.get("/farmers", response_model=list[FarmerOut])
def list_farmers(
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    worker: Worker = Depends(paid_worker),
    db: Session = Depends(get_db),
) -> list[Farmer]:
    query = select(Farmer).where(Farmer.tenant_id == worker.tenant_id)
    if q:
        pattern = f"%{q.replace('%', '').replace('_', '')}%"
        query = query.where(or_(Farmer.name.ilike(pattern), Farmer.village.ilike(pattern)))
    return list(db.scalars(query.order_by(Farmer.name).limit(limit).offset(offset)))


@router.post("/farmers", response_model=FarmerOut, status_code=201)
def create_farmer(
    body: FarmerIn,
    worker: Worker = Depends(paid_worker),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Farmer:
    farmer = Farmer(tenant_id=worker.tenant_id, created_by=worker.id, **_clean_farmer(body, settings))
    db.add(farmer)
    db.commit()
    return farmer


@router.get("/farmers/{farmer_id}", response_model=FarmerOut)
def get_farmer(farmer_id: int, worker: Worker = Depends(paid_worker), db: Session = Depends(get_db)) -> Farmer:
    return _farmer(db, worker, farmer_id)


@router.put("/farmers/{farmer_id}", response_model=FarmerOut)
def update_farmer(
    farmer_id: int,
    body: FarmerIn,
    worker: Worker = Depends(paid_worker),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Farmer:
    farmer = _farmer(db, worker, farmer_id)
    for key, value in _clean_farmer(body, settings).items():
        setattr(farmer, key, value)
    db.commit()
    db.refresh(farmer)
    return farmer


@router.delete("/farmers/{farmer_id}", status_code=204)
def delete_farmer(farmer_id: int, worker: Worker = Depends(admin_worker), db: Session = Depends(get_db)) -> Response:
    db.delete(_farmer(db, worker, farmer_id))
    db.commit()
    return Response(status_code=204)


# Scans -----------------------------------------------------------------------


@router.post("/farmers/{farmer_id}/scans", response_model=ScanOut)
def sync_scan(
    farmer_id: int,
    body: ScanIn,
    response: Response,
    worker: Worker = Depends(paid_worker),
    db: Session = Depends(get_db),
) -> FarmerScan:
    farmer = _farmer(db, worker, farmer_id)
    existing = db.scalar(
        select(FarmerScan).where(FarmerScan.tenant_id == worker.tenant_id, FarmerScan.client_id == body.client_id)
    )
    if existing is not None:
        # The app retries when offline. The same client_id is stored once.
        response.status_code = 200
        return existing
    scan = FarmerScan(
        tenant_id=worker.tenant_id,
        farmer_id=farmer.id,
        worker_id=worker.id,
        client_id=body.client_id,
        crop=body.crop,
        verdict=body.verdict,
        primary_class=body.findings[0].class_id if body.findings else None,
        findings=[f.model_dump() for f in body.findings],
        model_version=body.model_version,
        scanned_at=body.scanned_at,
    )
    db.add(scan)
    try:
        db.commit()
    except IntegrityError:
        # A parallel retry won the race; return the stored copy.
        db.rollback()
        response.status_code = 200
        return db.scalar(
            select(FarmerScan).where(FarmerScan.tenant_id == worker.tenant_id, FarmerScan.client_id == body.client_id)
        )
    response.status_code = 201
    return scan


@router.get("/farmers/{farmer_id}/scans", response_model=list[ScanOut])
def list_scans(farmer_id: int, worker: Worker = Depends(paid_worker), db: Session = Depends(get_db)) -> list[FarmerScan]:
    farmer = _farmer(db, worker, farmer_id)
    return list(db.scalars(select(FarmerScan).where(FarmerScan.farmer_id == farmer.id).order_by(FarmerScan.scanned_at.desc())))


# Reports ---------------------------------------------------------------------


def _range(start: date | None, end: date | None) -> tuple[datetime, datetime]:
    begin = datetime.combine(start or date(2000, 1, 1), time.min, UTC)
    finish = datetime.combine(end or datetime.now(UTC).date(), time.max, UTC)
    if begin > finish:
        raise ApiError(422, "invalid_range", "The start date is after the end date.")
    return begin, finish


@router.get("/reports/summary")
def report_summary(
    start: date | None = None,
    end: date | None = None,
    worker: Worker = Depends(paid_worker),
    db: Session = Depends(get_db),
) -> dict:
    begin, finish = _range(start, end)
    scope = (FarmerScan.tenant_id == worker.tenant_id, FarmerScan.scanned_at.between(begin, finish))

    by_problem = db.execute(
        select(FarmerScan.crop, FarmerScan.verdict, FarmerScan.primary_class, func.count())
        .where(*scope)
        .group_by(FarmerScan.crop, FarmerScan.verdict, FarmerScan.primary_class)
        .order_by(func.count().desc())
    ).all()
    by_village = db.execute(
        select(Farmer.village, FarmerScan.primary_class, func.count())
        .join(Farmer, Farmer.id == FarmerScan.farmer_id)
        .where(*scope, FarmerScan.primary_class.is_not(None))
        .group_by(Farmer.village, FarmerScan.primary_class)
        .order_by(func.count().desc())
    ).all()
    farmers = db.scalar(select(func.count(func.distinct(FarmerScan.farmer_id))).where(*scope))
    return {
        "start": begin.date(),
        "end": finish.date(),
        "scans": sum(row[3] for row in by_problem),
        "farmers": farmers or 0,
        "by_problem": [
            {"crop": crop.value, "verdict": verdict, "class_id": cls, "count": count}
            for crop, verdict, cls, count in by_problem
        ],
        "by_village": [
            {"village": village or "Unknown", "class_id": cls, "count": count} for village, cls, count in by_village
        ],
    }


def _csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    # Stops spreadsheet programs from running cell contents as formulas.
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/reports/export.csv")
def report_export(
    start: date | None = None,
    end: date | None = None,
    worker: Worker = Depends(admin_worker),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    begin, finish = _range(start, end)
    rows = db.execute(
        select(FarmerScan, Farmer)
        .join(Farmer, Farmer.id == FarmerScan.farmer_id)
        .where(FarmerScan.tenant_id == worker.tenant_id, FarmerScan.scanned_at.between(begin, finish))
        .order_by(FarmerScan.scanned_at)
    ).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["scanned_at", "farmer", "village", "district", "crop", "verdict", "problem", "model_version"])
    for scan, farmer in rows:
        writer.writerow(
            [
                _csv_cell(v)
                for v in (
                    scan.scanned_at.isoformat(), farmer.name, farmer.village, farmer.district,
                    scan.crop.value, scan.verdict, scan.primary_class, scan.model_version,
                )
            ]
        )
    filename = f"scans-{begin.date()}-to-{finish.date()}.csv"
    return StreamingResponse(
        iter([out.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )
