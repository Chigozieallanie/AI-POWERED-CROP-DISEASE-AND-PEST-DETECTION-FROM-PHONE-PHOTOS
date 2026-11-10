import json
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.inference import ModelCard
from app.models import (
    Advice,
    ModelStatus,
    ModelVersion,
    Pack,
    PackKind,
    Place,
    ProblemClass,
    ReviewStatus,
)
from app.storage import LocalStorage, sha256_file

CONTENT_PACK_NAME = "content"


def version_key(version: str) -> tuple[int, ...]:
    parts = []
    for part in version.split("."):
        if not part.isdigit():
            raise ValueError(f"Version must be dotted numbers: {version}")
        parts.append(int(part))
    return tuple(parts)


def latest_packs(db: Session, app_version: str) -> list[Pack]:
    current = version_key(app_version)
    best: dict[tuple[str, str], Pack] = {}
    for pack in db.scalars(select(Pack)):
        if version_key(pack.min_app_version) > current:
            continue
        key = (pack.kind.value, pack.name)
        if key not in best or version_key(pack.version) > version_key(best[key].version):
            best[key] = pack
    return sorted(best.values(), key=lambda pack: (pack.kind.value, pack.name))


def _write_content_database(path: Path, db: Session, version: str) -> bool:
    classes = list(db.scalars(select(ProblemClass)))
    advice = list(db.scalars(select(Advice)))
    places = list(db.scalars(select(Place)))
    demo = any(item.review_status != ReviewStatus.reviewed for item in advice) or any(
        place.is_sample for place in places
    )

    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE classes (
                id TEXT PRIMARY KEY, crop TEXT NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL,
                technical_name TEXT, referral_type TEXT
            );
            CREATE TABLE advice (
                class_id TEXT NOT NULL, language TEXT NOT NULL, steps_now TEXT NOT NULL,
                prevention TEXT NOT NULL, do_not TEXT NOT NULL, safety TEXT NOT NULL,
                review_status TEXT NOT NULL, reviewer TEXT, reviewed_at TEXT,
                PRIMARY KEY (class_id, language)
            );
            CREATE TABLE places (
                id INTEGER PRIMARY KEY, type TEXT NOT NULL, name TEXT NOT NULL, phone TEXT,
                latitude REAL NOT NULL, longitude REAL NOT NULL, district TEXT NOT NULL,
                landmark TEXT, hours TEXT, stocks TEXT, certified INTEGER NOT NULL,
                last_checked TEXT, source TEXT, is_sample INTEGER NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO metadata VALUES (?, ?)",
            [("version", version), ("demo", "1" if demo else "0")],
        )
        connection.executemany(
            "INSERT INTO classes VALUES (?, ?, ?, ?, ?, ?)",
            [
                (c.id, c.crop.value, c.kind.value, c.name, c.technical_name,
                 c.referral_type.value if c.referral_type else None)
                for c in classes
            ],
        )
        connection.executemany(
            "INSERT INTO advice VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (a.class_id, a.language, json.dumps(a.steps_now), json.dumps(a.prevention),
                 json.dumps(a.do_not), json.dumps(a.safety), a.review_status.value, a.reviewer,
                 a.reviewed_at.isoformat() if a.reviewed_at else None)
                for a in advice
            ],
        )
        connection.executemany(
            "INSERT INTO places VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (p.id, p.type.value, p.name, p.phone, p.latitude, p.longitude, p.district,
                 p.landmark, p.hours, p.stocks, int(p.certified),
                 p.last_checked.isoformat() if p.last_checked else None, p.source,
                 int(p.is_sample))
                for p in places
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return demo


def publish_content_pack(db: Session, settings: Settings) -> Pack:
    storage = LocalStorage(settings.storage_dir)
    versions = db.scalars(select(Pack.version).where(Pack.kind == PackKind.content)).all()
    version = str(max((int(v) for v in versions), default=0) + 1)
    key = f"packs/content/content-{version}.sqlite"
    target = storage.path(key)
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as directory:
        built = Path(directory) / "content.sqlite"
        _write_content_database(built, db, version)
        shutil.move(built, target)

    pack = Pack(
        kind=PackKind.content,
        name=CONTENT_PACK_NAME,
        version=version,
        file=key,
        sha256=sha256_file(target),
        size_bytes=target.stat().st_size,
    )
    db.add(pack)
    db.commit()
    return pack


def publish_model(
    db: Session, settings: Settings, source: Path, min_app_version: str = "0.0.0"
) -> Pack:
    """Install a trained model for the API and publish it as a pack for phones."""
    model_file, card_file = source / "model.tflite", source / "model_card.json"
    if not model_file.is_file() or not card_file.is_file():
        raise FileNotFoundError(f"{source} needs model.tflite and model_card.json")
    card = ModelCard.from_file(card_file)
    version_key(card.version)

    declared = json.loads(card_file.read_text()).get("sha256")
    actual = sha256_file(model_file)
    if declared and declared != actual:
        raise ValueError(f"{model_file} does not match the SHA-256 in its model card")

    storage = LocalStorage(settings.storage_dir)
    key = f"packs/model/{card.name}-{card.version}.zip"
    target = storage.path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(model_file, "model.tflite")
        archive.write(card_file, "model_card.json")

    installed = settings.model_dir / card.name
    installed.mkdir(parents=True, exist_ok=True)
    shutil.copy2(model_file, installed / "model.tflite")
    shutil.copy2(card_file, installed / "model_card.json")

    for previous in db.scalars(
        select(ModelVersion).where(
            ModelVersion.name == card.name, ModelVersion.status == ModelStatus.live
        )
    ):
        previous.status = ModelStatus.retired
    metrics = json.loads(card_file.read_text()).get("metrics", {})
    db.add(
        ModelVersion(
            name=card.name, version=card.version, file=key, sha256=actual, metrics=metrics,
            status=ModelStatus.live,
        )
    )
    pack = Pack(
        kind=PackKind.model,
        name=card.name,
        version=card.version,
        file=key,
        sha256=sha256_file(target),
        size_bytes=target.stat().st_size,
        min_app_version=min_app_version,
    )
    db.add(pack)
    db.commit()
    return pack


def count_packs(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Pack)) or 0
