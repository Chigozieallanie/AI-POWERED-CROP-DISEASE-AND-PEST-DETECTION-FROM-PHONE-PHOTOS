from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.errors import ApiError
from app.inference import diagnose as run_diagnosis
from app.models import Advice, Crop, DiagnosisLog, PlaceType, ProblemClass, Tenant, UsageCounter
from app.schemas import (
    AdviceOut,
    ClassOut,
    DiagnosisOut,
    FindingOut,
    LeafOut,
    NearbyOut,
    PlaceOut,
    UsageOut,
    VerdictOut,
)
from app.security import metered_tenant, month_bucket, require_tenant
from app.verdict import HEALTHY

MAX_LEAVES = 6

router = APIRouter(prefix="/v1", tags=["Partner API"])


def class_id_for(crop: str, label: str) -> str:
    return f"{crop}_{HEALTHY}" if label == HEALTHY else label


@router.post("/diagnose", response_model=DiagnosisOut)
def diagnose(
    request: Request,
    crop: Annotated[Crop, Form()],
    images: Annotated[list[UploadFile], File(description="1 to 6 leaves from one plant")],
    tenant: Tenant = Depends(metered_tenant),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DiagnosisOut:
    if len(images) > MAX_LEAVES:
        raise ApiError(422, "invalid_request", f"Send at most {MAX_LEAVES} images.")
    raw_images = [upload.file.read(settings.max_image_bytes + 1) for upload in images]
    result = run_diagnosis(request.app.state.models, crop.value, raw_images, settings)

    referrals = {c.id: c.referral_type for c in db.scalars(select(ProblemClass))}

    def referral(class_id: str) -> str | None:
        value = referrals.get(class_id)
        return value.value if value else None

    findings = [
        FindingOut(
            class_id=class_id_for(crop.value, finding.label),
            certainty=finding.certainty,
            leaf_count=finding.leaf_count,
            experimental=finding.experimental,
            referral_type=referral(class_id_for(crop.value, finding.label)),
        )
        for finding in result.verdict.findings
    ]
    if findings:
        overall_referral = findings[0].referral_type
    elif result.verdict.state == "healthy":
        overall_referral = None
    else:
        overall_referral = PlaceType.extension_office.value

    db.add(
        DiagnosisLog(
            tenant_id=tenant.id,
            crop=crop,
            verdict=result.verdict.state,
            model_version=result.crop_version,
        )
    )
    db.commit()

    return DiagnosisOut(
        crop=crop.value,
        leaves=[
            LeafOut(index=leaf.index, status=leaf.status, label=leaf.label, score=leaf.score)
            for leaf in result.leaves
        ],
        verdict=VerdictOut(
            state=result.verdict.state,
            accepted_leaves=result.verdict.accepted_leaves,
            findings=findings,
            referral_type=overall_referral,
        ),
        model_versions={"gate": result.gate_version, "crop": result.crop_version},
    )


@router.get("/classes", response_model=list[ClassOut])
def classes(
    _: Tenant = Depends(metered_tenant), db: Session = Depends(get_db)
) -> list[ProblemClass]:
    return list(db.scalars(select(ProblemClass).order_by(ProblemClass.crop, ProblemClass.id)))


@router.get("/advice/{class_id}", response_model=AdviceOut)
def advice(
    class_id: str,
    lang: str = "en",
    _: Tenant = Depends(metered_tenant),
    db: Session = Depends(get_db),
) -> Advice:
    item = db.scalar(select(Advice).where(Advice.class_id == class_id, Advice.language == lang))
    if item is None:
        raise ApiError(404, "not_found", "No advice exists for that class and language.")
    return item


@router.get("/places/nearby", response_model=NearbyOut)
def nearby(
    type: PlaceType,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(gt=0, le=500)] = 50,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    _: Tenant = Depends(metered_tenant),
    db: Session = Depends(get_db),
) -> NearbyOut:
    rows = db.execute(
        text(
            """
            WITH origin AS (
                SELECT ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography AS point
            )
            SELECT p.id, p.type, p.name, p.phone, p.latitude, p.longitude, p.district,
                   p.landmark, p.hours, p.stocks, p.certified, p.last_checked, p.is_sample,
                   ST_Distance(p.location, origin.point) / 1000 AS distance_km
            FROM places p, origin
            WHERE p.type = :type AND ST_DWithin(p.location, origin.point, :radius_m)
            ORDER BY distance_km
            LIMIT :limit
            """
        ),
        {
            "lat": lat,
            "lng": lng,
            "type": type.value,
            "radius_m": radius_km * 1000,
            "limit": limit,
        },
    ).mappings()
    return NearbyOut(places=[PlaceOut(**row) for row in rows])


@router.get("/usage", response_model=UsageOut)
def usage(tenant: Tenant = Depends(require_tenant), db: Session = Depends(get_db)) -> UsageOut:
    bucket = month_bucket(datetime.now(UTC))
    counter = db.get(UsageCounter, (tenant.id, bucket))
    used = counter.count if counter else 0
    return UsageOut(
        plan=tenant.plan.name,
        period=bucket.removeprefix("month:"),
        used=used,
        monthly_quota=tenant.plan.monthly_quota,
        remaining=max(tenant.plan.monthly_quota - used, 0),
    )
