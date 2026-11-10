import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.errors import ApiError
from app.inference import decode_image
from app.models import Contribution, Crop, Pack, Place, Report, Tenant
from app.packs import latest_packs, version_key
from app.schemas import CreatedOut, PackOut, PacksOut, ReportIn, TenantConfigOut
from app.security import client_ip
from app.storage import LocalStorage


def rate_limited(request: Request) -> None:
    if not request.app.state.app_limiter.allow(client_ip(request)):
        raise ApiError(429, "rate_limited", "Too many requests this minute.")


router = APIRouter(prefix="/app/v1", tags=["Mobile app"], dependencies=[Depends(rate_limited)])


@router.get("/packs/latest", response_model=PacksOut)
def packs_latest(
    app_version: Annotated[str, Query(pattern=r"^\d+(\.\d+)*$", max_length=32)],
    db: Session = Depends(get_db),
) -> PacksOut:
    return PacksOut(
        packs=[
            PackOut(
                id=pack.id,
                kind=pack.kind.value,
                name=pack.name,
                version=pack.version,
                sha256=pack.sha256,
                size_bytes=pack.size_bytes,
                download_url=f"/app/v1/packs/{pack.id}/download",
            )
            for pack in latest_packs(db, app_version)
        ]
    )


@router.get("/packs/{pack_id}/download")
def pack_download(
    pack_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    pack = db.get(Pack, pack_id)
    path = LocalStorage(settings.storage_dir).path(pack.file) if pack else None
    if path is None or not path.is_file():
        raise ApiError(404, "not_found", "That pack does not exist.")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=path.name,
        headers={"X-Content-SHA256": pack.sha256},
    )


@router.post("/reports", response_model=CreatedOut, status_code=201)
def create_report(body: ReportIn, db: Session = Depends(get_db)) -> Report:
    if db.get(Place, body.place_id) is None:
        raise ApiError(404, "not_found", "That place does not exist.")
    report = Report(place_id=body.place_id, message=body.message)
    db.add(report)
    db.commit()
    return report


@router.post("/contributions", response_model=CreatedOut, status_code=201)
def create_contribution(
    consent_version: Annotated[str, Form(min_length=1, max_length=32)],
    crop: Annotated[Crop, Form()],
    image: Annotated[UploadFile, File()],
    predicted_class: Annotated[str | None, Form(max_length=64)] = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Contribution:
    decoded = decode_image(image.file.read(settings.max_image_bytes + 1), 0, settings)
    # Saving only the pixels drops EXIF, which is where phones put GPS.
    clean = io.BytesIO()
    decoded.save(clean, "JPEG", quality=90)

    key = f"contributions/{uuid.uuid4().hex}.jpg"
    LocalStorage(settings.storage_dir).put_bytes(key, clean.getvalue())
    contribution = Contribution(
        consent_version=consent_version, crop=crop, predicted_class=predicted_class, file=key
    )
    db.add(contribution)
    db.commit()
    return contribution


@router.get("/tenants/{slug}/config", response_model=TenantConfigOut)
def tenant_config(slug: str, db: Session = Depends(get_db)) -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == slug, Tenant.is_active.is_(True)))
    if tenant is None:
        raise ApiError(404, "not_found", "That organisation does not exist.")
    return tenant
