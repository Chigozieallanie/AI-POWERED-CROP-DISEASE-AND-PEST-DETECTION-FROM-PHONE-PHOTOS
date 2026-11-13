"""Staff commands. Run with: python -m app.cli <command> --help"""

import argparse
import csv
import json
from datetime import date
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    Advice,
    ApiKey,
    ClassKind,
    Crop,
    Place,
    PlaceType,
    Plan,
    ProblemClass,
    Tenant,
    Worker,
    WorkerRole,
)
from app.packs import publish_content_pack, publish_model
from app.security import new_key
from app.workers_auth import normalise_phone

TRUE_VALUES = {"1", "true", "yes", "y"}


def seed(db: Session, content_dir: Path) -> None:
    for item in json.loads((content_dir / "plans.json").read_text()):
        if db.scalar(select(Plan).where(Plan.name == item["name"])) is None:
            db.add(Plan(**item))

    for item in json.loads((content_dir / "classes.json").read_text()):
        db.merge(
            ProblemClass(
                id=item["id"],
                crop=Crop(item["crop"]),
                kind=ClassKind(item["kind"]),
                name=item["name"],
                technical_name=item.get("technical_name"),
                referral_type=PlaceType(item["referral_type"]) if item.get("referral_type") else None,
            )
        )
    db.flush()

    # Existing advice is left alone so a re-seed cannot undo an agronomist's review.
    for item in json.loads((content_dir / "advice.en.json").read_text()):
        exists = db.scalar(
            select(Advice).where(Advice.class_id == item["class_id"], Advice.language == "en")
        )
        if exists is None:
            db.add(Advice(language="en", **item))

    has_places = (db.scalar(select(func.count()).select_from(Place)) or 0) > 0
    if not has_places:
        import_places(db, content_dir / "sample_places.csv")
    db.commit()


def import_places(db: Session, path: Path) -> int:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        db.add(
            Place(
                type=PlaceType(row["type"]),
                name=row["name"],
                phone=row.get("phone") or None,
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                district=row["district"],
                landmark=row.get("landmark") or None,
                hours=row.get("hours") or None,
                stocks=row.get("stocks") or None,
                certified=row.get("certified", "").strip().lower() in TRUE_VALUES,
                last_checked=date.fromisoformat(row["last_checked"]) if row.get("last_checked") else None,
                source=row.get("source") or None,
                # A row is sample data unless the file says otherwise.
                is_sample=row.get("is_sample", "true").strip().lower() in TRUE_VALUES,
            )
        )
    db.commit()
    return len(rows)


def create_key(db: Session, slug: str, name: str | None, plan_name: str) -> str:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant is None:
        plan = db.scalar(select(Plan).where(Plan.name == plan_name))
        if plan is None:
            raise SystemExit(f"Unknown plan: {plan_name}")
        tenant = Tenant(name=name or slug, slug=slug, plan_id=plan.id)
        db.add(tenant)
        db.flush()
    raw_key, prefix, key_hash = new_key()
    db.add(ApiKey(tenant_id=tenant.id, key_hash=key_hash, prefix=prefix))
    db.commit()
    return raw_key


def create_worker(db: Session, slug: str, phone: str, name: str, role: str) -> Worker:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant is None:
        raise SystemExit(f"Unknown organisation: {slug}. Create it with create-key first.")
    worker = Worker(
        tenant_id=tenant.id,
        phone=normalise_phone(phone, get_settings().default_country_code),
        name=name,
        role=WorkerRole(role),
    )
    db.add(worker)
    db.commit()
    return worker


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed", help="Load plans, classes, advice and sample places")
    commands.add_parser("publish-content", help="Build a content pack from the database")

    places = commands.add_parser("import-places", help="Add places from a CSV file")
    places.add_argument("path", type=Path)

    key = commands.add_parser("create-key", help="Create an API key, and the organisation if new")
    key.add_argument("--slug", required=True)
    key.add_argument("--name")
    key.add_argument("--plan", default="free")

    worker = commands.add_parser("create-worker", help="Add a paid-tier worker who signs in by phone")
    worker.add_argument("--slug", required=True)
    worker.add_argument("--phone", required=True)
    worker.add_argument("--name", required=True)
    worker.add_argument("--role", choices=[r.value for r in WorkerRole], default="worker")

    model = commands.add_parser("publish-model", help="Install and publish a trained model")
    model.add_argument("path", type=Path)
    model.add_argument("--min-app-version", default="0.0.0")

    args = parser.parse_args()
    settings = get_settings()
    with SessionLocal() as db:
        if args.command == "seed":
            seed(db, settings.content_dir)
            print("Seed complete.")
        elif args.command == "publish-content":
            print(f"Published content pack {publish_content_pack(db, settings).version}.")
        elif args.command == "import-places":
            print(f"Imported {import_places(db, args.path)} places.")
        elif args.command == "create-key":
            print(create_key(db, args.slug, args.name, args.plan))
        elif args.command == "create-worker":
            created = create_worker(db, args.slug, args.phone, args.name, args.role)
            print(f"Added {created.name} ({created.phone}) as {created.role.value}.")
        elif args.command == "publish-model":
            pack = publish_model(db, settings, args.path, args.min_app_version)
            print(f"Published {pack.name} {pack.version}. Restart the API to load it.")


if __name__ == "__main__":
    main()
