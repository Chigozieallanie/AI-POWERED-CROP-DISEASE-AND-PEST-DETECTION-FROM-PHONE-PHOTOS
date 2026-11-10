from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import PlaceType


class ClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    crop: str
    kind: str
    name: str
    technical_name: str | None
    referral_type: str | None


class AdviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    class_id: str
    language: str
    steps_now: list[str]
    prevention: list[str]
    do_not: list[str]
    safety: list[str]
    review_status: str
    reviewer: str | None
    reviewed_at: datetime | None


class PlaceOut(BaseModel):
    id: int
    type: str
    name: str
    phone: str | None
    latitude: float
    longitude: float
    district: str
    landmark: str | None
    hours: str | None
    stocks: str | None
    certified: bool
    last_checked: date | None
    is_sample: bool
    distance_km: float


class NearbyOut(BaseModel):
    places: list[PlaceOut]


class LeafOut(BaseModel):
    index: int
    status: str
    label: str | None
    score: float | None


class FindingOut(BaseModel):
    class_id: str
    certainty: str
    leaf_count: int
    experimental: bool
    referral_type: str | None


class VerdictOut(BaseModel):
    state: str
    accepted_leaves: int
    findings: list[FindingOut]
    referral_type: str | None


class DiagnosisOut(BaseModel):
    crop: str
    leaves: list[LeafOut]
    verdict: VerdictOut
    model_versions: dict[str, str]


class UsageOut(BaseModel):
    plan: str
    period: str
    used: int
    monthly_quota: int
    remaining: int


class PackOut(BaseModel):
    id: int
    kind: str
    name: str
    version: str
    sha256: str
    size_bytes: int
    download_url: str


class PacksOut(BaseModel):
    packs: list[PackOut]


class ReportIn(BaseModel):
    place_id: int
    message: str = Field(min_length=3, max_length=2000)


class CreatedOut(BaseModel):
    id: int


class TenantConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    logo_url: str | None
    primary_color: str | None
    support_phone: str | None


__all__ = ["PlaceType"]
