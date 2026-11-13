from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Crop(StrEnum):
    cassava = "cassava"
    maize = "maize"


class ClassKind(StrEnum):
    disease = "disease"
    pest = "pest"
    healthy = "healthy"


class PlaceType(StrEnum):
    dealer = "dealer"
    clean_cuttings = "clean_cuttings"
    extension_office = "extension_office"


class KeyStatus(StrEnum):
    active = "active"
    revoked = "revoked"


class ReviewStatus(StrEnum):
    unreviewed = "unreviewed"
    reviewed = "reviewed"


class ModelStatus(StrEnum):
    draft = "draft"
    live = "live"
    retired = "retired"


class PackKind(StrEnum):
    content = "content"
    model = "model"


class ReportStatus(StrEnum):
    open = "open"
    resolved = "resolved"


def enum_column(enum_type: type[StrEnum]) -> Enum:
    return Enum(
        enum_type,
        native_enum=False,
        length=32,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class Base(DeclarativeBase):
    pass


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    monthly_quota: Mapped[int] = mapped_column(Integer)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer)
    price_ugx: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    features: Mapped[dict] = mapped_column(JSON, default=dict)

    def __str__(self) -> str:
        return self.name


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    logo_url: Mapped[str | None] = mapped_column(String(500))
    primary_color: Mapped[str | None] = mapped_column(String(16))
    support_phone: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    plan: Mapped[Plan] = relationship(lazy="joined")

    def __str__(self) -> str:
        return self.name


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    prefix: Mapped[str] = mapped_column(String(16))
    status: Mapped[KeyStatus] = mapped_column(enum_column(KeyStatus), default=KeyStatus.active)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped[Tenant] = relationship(lazy="joined")

    def __str__(self) -> str:
        return self.prefix


class UsageCounter(Base):
    __tablename__ = "usage_counters"

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    bucket: Mapped[str] = mapped_column(String(32), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_events_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    endpoint: Mapped[str] = mapped_column(String(200))
    status: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProblemClass(Base):
    __tablename__ = "classes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    crop: Mapped[Crop] = mapped_column(enum_column(Crop))
    kind: Mapped[ClassKind] = mapped_column(enum_column(ClassKind))
    name: Mapped[str] = mapped_column(String(200))
    technical_name: Mapped[str | None] = mapped_column(String(200))
    referral_type: Mapped[PlaceType | None] = mapped_column(enum_column(PlaceType))

    def __str__(self) -> str:
        return self.id


class Advice(Base):
    __tablename__ = "advice"
    __table_args__ = (UniqueConstraint("class_id", "language"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"))
    language: Mapped[str] = mapped_column(String(8), default="en")
    steps_now: Mapped[list] = mapped_column(JSON, default=list)
    prevention: Mapped[list] = mapped_column(JSON, default=list)
    do_not: Mapped[list] = mapped_column(JSON, default=list)
    safety: Mapped[list] = mapped_column(JSON, default=list)
    review_status: Mapped[ReviewStatus] = mapped_column(
        enum_column(ReviewStatus), default=ReviewStatus.unreviewed
    )
    reviewer: Mapped[str | None] = mapped_column(String(200))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    problem_class: Mapped[ProblemClass] = relationship(lazy="joined")

    def __str__(self) -> str:
        return f"{self.class_id} ({self.language})"


class Place(Base):
    """A help location. The PostGIS `location` column is generated in the migration."""

    __tablename__ = "places"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[PlaceType] = mapped_column(enum_column(PlaceType))
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(32))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    district: Mapped[str] = mapped_column(String(100))
    landmark: Mapped[str | None] = mapped_column(String(200))
    hours: Mapped[str | None] = mapped_column(String(100))
    stocks: Mapped[str | None] = mapped_column(Text)
    certified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_checked: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(String(200))
    # A place counts as sample data until someone has confirmed it.
    is_sample: Mapped[bool] = mapped_column(Boolean, default=True)

    def __str__(self) -> str:
        return self.name


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("name", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32))
    file: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[ModelStatus] = mapped_column(enum_column(ModelStatus), default=ModelStatus.draft)

    def __str__(self) -> str:
        return f"{self.name} {self.version}"


class Pack(Base):
    __tablename__ = "packs"
    __table_args__ = (UniqueConstraint("kind", "name", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[PackKind] = mapped_column(enum_column(PackKind))
    name: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32))
    file: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    min_app_version: Mapped[str] = mapped_column(String(32), default="0.0.0")
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __str__(self) -> str:
        return f"{self.kind} {self.name} {self.version}"


class DiagnosisLog(Base):
    """Holds no images and no coordinates, by design."""

    __tablename__ = "diagnosis_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    crop: Mapped[Crop] = mapped_column(enum_column(Crop))
    verdict: Mapped[str] = mapped_column(String(32))
    model_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Contribution(Base):
    __tablename__ = "contributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    consent_version: Mapped[str] = mapped_column(String(32))
    crop: Mapped[Crop] = mapped_column(enum_column(Crop))
    predicted_class: Mapped[str | None] = mapped_column(String(64))
    file: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id", ondelete="CASCADE"))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[ReportStatus] = mapped_column(enum_column(ReportStatus), default=ReportStatus.open)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WorkerRole(StrEnum):
    worker = "worker"
    admin = "admin"


class UpgradeStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Worker(Base):
    """A paid-tier user, such as an extension worker. Staff or an organisation admin adds them."""

    __tablename__ = "workers"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    phone: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[WorkerRole] = mapped_column(enum_column(WorkerRole), default=WorkerRole.worker)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tenant: Mapped[Tenant] = relationship(lazy="joined")

    def __str__(self) -> str:
        return f"{self.name} ({self.phone})"


class OtpCode(Base):
    __tablename__ = "otp_codes"
    __table_args__ = (Index("ix_otp_codes_phone_created", "phone", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(16))
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WorkerSession(Base):
    __tablename__ = "worker_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    worker: Mapped[Worker] = relationship(lazy="joined")


class Farmer(Base):
    __tablename__ = "farmers"
    __table_args__ = (Index("ix_farmers_tenant_name", "tenant_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("workers.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(16))
    village: Mapped[str | None] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __str__(self) -> str:
        return self.name


class FarmerScan(Base):
    """A diagnosis result synced from the app. No photos and no coordinates are stored."""

    __tablename__ = "farmer_scans"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id"),
        Index("ix_farmer_scans_tenant_scanned", "tenant_id", "scanned_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"))
    worker_id: Mapped[int | None] = mapped_column(ForeignKey("workers.id", ondelete="SET NULL"))
    client_id: Mapped[str] = mapped_column(String(64))
    crop: Mapped[Crop] = mapped_column(enum_column(Crop))
    verdict: Mapped[str] = mapped_column(String(32))
    primary_class: Mapped[str | None] = mapped_column(String(64))
    findings: Mapped[list] = mapped_column(JSON, default=list)
    model_version: Mapped[str] = mapped_column(String(32))
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UpgradeRequest(Base):
    __tablename__ = "upgrade_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("workers.id", ondelete="SET NULL"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    payment_reference: Mapped[str] = mapped_column(String(100))
    payer_phone: Mapped[str] = mapped_column(String(16))
    status: Mapped[UpgradeStatus] = mapped_column(
        enum_column(UpgradeStatus), default=UpgradeStatus.pending
    )
    staff_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped[Tenant] = relationship(lazy="joined")
    plan: Mapped[Plan] = relationship(lazy="joined")

    def __str__(self) -> str:
        return f"#{self.id} {self.status}"
