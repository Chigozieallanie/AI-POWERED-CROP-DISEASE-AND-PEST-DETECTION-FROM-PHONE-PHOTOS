import hmac
from datetime import UTC, datetime
from html import escape

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqladmin import Admin, ModelView, action
from sqladmin.authentication import AuthenticationBackend

from app.config import Settings, get_settings
from app.db import SessionLocal, engine
from app.models import (
    Advice,
    ApiKey,
    Contribution,
    DiagnosisLog,
    Farmer,
    FarmerScan,
    ModelVersion,
    Pack,
    Place,
    Plan,
    ProblemClass,
    Report,
    Tenant,
    UpgradeRequest,
    UpgradeStatus,
    UsageEvent,
    Worker,
)
from app.packs import publish_content_pack
from app.security import IpRateLimiter, client_ip, new_key
from app.workers_auth import normalise_phone


class StaffAuth(AuthenticationBackend):
    def __init__(self, settings: Settings) -> None:
        super().__init__(secret_key=settings.session_secret)
        self.settings = settings
        self.limiter = IpRateLimiter(settings.login_rate_limit_per_minute)

    async def login(self, request: Request) -> bool:
        if not self.limiter.allow(client_ip(request)):
            return False
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))
        valid_user = hmac.compare_digest(username.encode(), self.settings.admin_username.encode())
        valid_password = hmac.compare_digest(
            password.encode(), self.settings.admin_password.encode()
        )
        if valid_user and valid_password:
            request.session.update({"staff": True})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return bool(request.session.get("staff"))


class ReadOnlyView(ModelView):
    can_create = False
    can_edit = False
    can_delete = False


class PlanAdmin(ModelView, model=Plan):
    column_list = [Plan.id, Plan.name, Plan.monthly_quota, Plan.rate_limit_per_minute]


def _generate_key(tenant_id: int) -> tuple[str, str]:
    raw_key, prefix, key_hash = new_key()
    with SessionLocal() as db:
        tenant = db.get(Tenant, tenant_id)
        if tenant is None:
            raise ValueError("Unknown organisation")
        db.add(ApiKey(tenant_id=tenant.id, key_hash=key_hash, prefix=prefix))
        db.commit()
        return tenant.name, raw_key


class TenantAdmin(ModelView, model=Tenant):
    column_list = [Tenant.id, Tenant.name, Tenant.slug, Tenant.plan, Tenant.is_active]
    column_searchable_list = [Tenant.name, Tenant.slug]

    @action(name="generate_key", label="Generate API key", add_in_detail=True, add_in_list=False)
    async def generate_key(self, request: Request) -> Response:
        pks = [pk for pk in request.query_params.get("pks", "").split(",") if pk]
        if len(pks) != 1 or not pks[0].isdigit():
            return HTMLResponse("<p>Choose one organisation.</p>", status_code=400)
        try:
            name, raw_key = await run_in_threadpool(_generate_key, int(pks[0]))
        except ValueError:
            return HTMLResponse("<p>Unknown organisation.</p>", status_code=404)
        return HTMLResponse(
            f"<h1>API key for {escape(name)}</h1>"
            "<p>Copy it now. It will not be shown again.</p>"
            f"<pre>{escape(raw_key)}</pre>"
            f'<a href="{request.url_for("admin:list", identity="tenant")}">Back</a>',
            headers={"Cache-Control": "no-store"},
        )


class ApiKeyAdmin(ModelView, model=ApiKey):
    can_create = False
    column_list = [ApiKey.id, ApiKey.tenant, ApiKey.prefix, ApiKey.status, ApiKey.last_used_at]
    column_details_exclude_list = [ApiKey.key_hash]
    form_columns = [ApiKey.status]


class ClassAdmin(ModelView, model=ProblemClass):
    name_plural = "Classes"
    column_list = [
        ProblemClass.id,
        ProblemClass.crop,
        ProblemClass.kind,
        ProblemClass.name,
        ProblemClass.referral_type,
    ]


class AdviceAdmin(ModelView, model=Advice):
    name_plural = "Advice"
    column_list = [Advice.id, Advice.class_id, Advice.language, Advice.review_status, Advice.reviewer]
    column_searchable_list = [Advice.class_id]
    column_sortable_list = [Advice.class_id, Advice.review_status]


class PlaceAdmin(ModelView, model=Place):
    column_list = [
        Place.id,
        Place.name,
        Place.type,
        Place.district,
        Place.certified,
        Place.last_checked,
        Place.is_sample,
    ]
    column_searchable_list = [Place.name, Place.district]
    column_sortable_list = [Place.name, Place.district, Place.last_checked]


class ModelVersionAdmin(ReadOnlyView, model=ModelVersion):
    column_list = [ModelVersion.name, ModelVersion.version, ModelVersion.status, ModelVersion.sha256]


def _publish_content(settings: Settings) -> None:
    with SessionLocal() as db:
        publish_content_pack(db, settings)


class PackAdmin(ReadOnlyView, model=Pack):
    column_list = [Pack.id, Pack.kind, Pack.name, Pack.version, Pack.size_bytes, Pack.published_at]

    @action(
        name="publish_content",
        label="Publish new content pack",
        confirmation_message="Build a new content pack from current advice and places?",
        add_in_list=True,
        add_in_detail=False,
    )
    async def publish_content(self, request: Request) -> Response:
        await run_in_threadpool(_publish_content, get_settings())
        return RedirectResponse(request.url_for("admin:list", identity="pack"), status_code=303)


class ReportAdmin(ModelView, model=Report):
    can_create = False
    column_list = [Report.id, Report.place_id, Report.status, Report.created_at]
    form_columns = [Report.status]


class ContributionAdmin(ReadOnlyView, model=Contribution):
    column_list = [Contribution.id, Contribution.crop, Contribution.consent_version, Contribution.created_at]


class UsageAdmin(ReadOnlyView, model=UsageEvent):
    column_list = [
        UsageEvent.tenant_id,
        UsageEvent.endpoint,
        UsageEvent.status,
        UsageEvent.latency_ms,
        UsageEvent.created_at,
    ]
    column_default_sort = ("created_at", True)


class DiagnosisLogAdmin(ReadOnlyView, model=DiagnosisLog):
    column_list = [
        DiagnosisLog.tenant_id,
        DiagnosisLog.crop,
        DiagnosisLog.verdict,
        DiagnosisLog.model_version,
        DiagnosisLog.created_at,
    ]
    column_default_sort = ("created_at", True)


class WorkerAdmin(ModelView, model=Worker):
    column_list = [Worker.id, Worker.name, Worker.phone, Worker.tenant, Worker.role, Worker.is_active]
    column_searchable_list = [Worker.name, Worker.phone]
    form_columns = [Worker.tenant, Worker.name, Worker.phone, Worker.role, Worker.is_active]

    async def on_model_change(self, data: dict, model: Worker, is_created: bool, request: Request) -> None:
        if data.get("phone"):
            data["phone"] = normalise_phone(str(data["phone"]), get_settings().default_country_code)


class FarmerAdmin(ModelView, model=Farmer):
    can_create = False
    can_edit = False
    column_list = [Farmer.id, Farmer.name, Farmer.village, Farmer.district, Farmer.tenant_id, Farmer.created_at]
    column_searchable_list = [Farmer.name, Farmer.village]


class FarmerScanAdmin(ReadOnlyView, model=FarmerScan):
    column_list = [
        FarmerScan.id,
        FarmerScan.tenant_id,
        FarmerScan.farmer_id,
        FarmerScan.crop,
        FarmerScan.verdict,
        FarmerScan.primary_class,
        FarmerScan.scanned_at,
    ]
    column_default_sort = ("scanned_at", True)


def _decide_upgrade(request_id: int, approve: bool) -> None:
    with SessionLocal() as db:
        upgrade = db.get(UpgradeRequest, request_id)
        if upgrade is None or upgrade.status != UpgradeStatus.pending:
            raise ValueError("Only pending requests can be decided.")
        upgrade.status = UpgradeStatus.approved if approve else UpgradeStatus.rejected
        upgrade.decided_at = datetime.now(UTC)
        if approve:
            upgrade.tenant.plan_id = upgrade.plan_id
        db.commit()


class UpgradeRequestAdmin(ModelView, model=UpgradeRequest):
    can_create = False
    column_list = [
        UpgradeRequest.id,
        UpgradeRequest.tenant,
        UpgradeRequest.plan,
        UpgradeRequest.payment_reference,
        UpgradeRequest.payer_phone,
        UpgradeRequest.status,
        UpgradeRequest.created_at,
    ]
    column_default_sort = ("created_at", True)
    form_columns = [UpgradeRequest.staff_note]

    async def _decide(self, request: Request, approve: bool) -> Response:
        pks = [pk for pk in request.query_params.get("pks", "").split(",") if pk.isdigit()]
        for pk in pks:
            try:
                await run_in_threadpool(_decide_upgrade, int(pk), approve)
            except ValueError as error:
                return HTMLResponse(f"<p>{escape(str(error))}</p>", status_code=409)
        return RedirectResponse(request.url_for("admin:list", identity="upgrade-request"), status_code=303)

    @action(
        name="approve",
        label="Approve: payment received",
        confirmation_message="Only approve after checking the mobile money payment arrived.",
        add_in_detail=True,
        add_in_list=False,
    )
    async def approve(self, request: Request) -> Response:
        return await self._decide(request, True)

    @action(name="reject", label="Reject", add_in_detail=True, add_in_list=False)
    async def reject(self, request: Request) -> Response:
        return await self._decide(request, False)


def install_admin(app: FastAPI, settings: Settings) -> None:
    admin = Admin(app, engine, authentication_backend=StaffAuth(settings), title="Crop admin")
    for view in (
        TenantAdmin,
        PlanAdmin,
        ApiKeyAdmin,
        ClassAdmin,
        AdviceAdmin,
        PlaceAdmin,
        PackAdmin,
        ModelVersionAdmin,
        ReportAdmin,
        ContributionAdmin,
        UsageAdmin,
        DiagnosisLogAdmin,
        WorkerAdmin,
        FarmerAdmin,
        FarmerScanAdmin,
        UpgradeRequestAdmin,
    ):
        admin.add_view(view)
