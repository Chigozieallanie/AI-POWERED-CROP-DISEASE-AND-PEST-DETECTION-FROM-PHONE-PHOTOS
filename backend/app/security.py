import hashlib
import secrets
import threading
import time
from datetime import UTC, datetime

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.models import ApiKey, KeyStatus, Tenant, UsageCounter

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_key(raw_key: str) -> str:
    # Keys carry 256 bits of randomness, so a plain fast hash is appropriate.
    return hashlib.sha256(raw_key.encode()).hexdigest()


def new_key() -> tuple[str, str, str]:
    """Return (raw key, prefix, hash). The raw key is shown once and never stored."""
    prefix = secrets.token_hex(4)
    raw_key = f"ck_{prefix}_{secrets.token_urlsafe(32)}"
    return raw_key, prefix, hash_key(raw_key)


def month_bucket(now: datetime) -> str:
    return f"month:{now:%Y-%m}"


def minute_bucket(now: datetime) -> str:
    return f"minute:{now:%Y-%m-%dT%H:%M}"


def require_tenant(
    request: Request,
    raw_key: str | None = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> Tenant:
    if raw_key is None:
        raise ApiError(401, "invalid_api_key", "Send a valid key in the X-API-Key header.")
    key = db.scalar(
        select(ApiKey).where(
            ApiKey.key_hash == hash_key(raw_key), ApiKey.status == KeyStatus.active
        )
    )
    if key is None or not key.tenant.is_active:
        raise ApiError(401, "invalid_api_key", "Send a valid key in the X-API-Key header.")
    key.last_used_at = datetime.now(UTC)
    db.commit()
    request.state.tenant_id = key.tenant_id
    return key.tenant


def _consume(db: Session, tenant_id: int, bucket: str, limit: int) -> int | None:
    """Atomically add one to a counter. Returns the new count, or None at the limit."""
    if limit <= 0:
        return None
    return db.execute(
        text(
            """
            INSERT INTO usage_counters (tenant_id, bucket, count)
            VALUES (:tenant_id, :bucket, 1)
            ON CONFLICT (tenant_id, bucket) DO UPDATE
                SET count = usage_counters.count + 1
                WHERE usage_counters.count < :limit
            RETURNING count
            """
        ),
        {"tenant_id": tenant_id, "bucket": bucket, "limit": limit},
    ).scalar()


def metered_tenant(
    tenant: Tenant = Depends(require_tenant),
    db: Session = Depends(get_db),
) -> Tenant:
    now = datetime.now(UTC)
    minute = minute_bucket(now)
    used = _consume(db, tenant.id, minute, tenant.plan.rate_limit_per_minute)
    if used is None:
        db.commit()
        raise ApiError(
            429,
            "rate_limited",
            "Too many requests this minute.",
            headers={"Retry-After": str(60 - now.second)},
        )
    if used == 1:
        db.execute(
            delete(UsageCounter).where(
                UsageCounter.tenant_id == tenant.id,
                UsageCounter.bucket.like("minute:%"),
                UsageCounter.bucket != minute,
            )
        )
    if _consume(db, tenant.id, month_bucket(now), tenant.plan.monthly_quota) is None:
        db.commit()
        raise ApiError(429, "quota_exceeded", "This plan's monthly quota is used up.")
    db.commit()
    return tenant


class IpRateLimiter:
    """Per-minute limiter held in memory. It assumes one server process."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._hits: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def allow(self, ip: str) -> bool:
        minute = int(time.time() // 60)
        with self._lock:
            if len(self._hits) > 10_000:
                self._hits = {k: v for k, v in self._hits.items() if v[0] == minute}
            seen_minute, count = self._hits.get(ip, (minute, 0))
            if seen_minute != minute:
                count = 0
            if count >= self.limit:
                return False
            self._hits[ip] = (minute, count + 1)
            return True


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
