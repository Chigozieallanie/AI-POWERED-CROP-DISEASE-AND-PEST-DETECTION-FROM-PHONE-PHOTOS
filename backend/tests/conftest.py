import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_files = tempfile.mkdtemp(prefix="crop-tests-")

os.environ.update(
    DATABASE_URL=os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://crop_tester:test-only@127.0.0.1:5544/crop_test"
    ),
    ADMIN_USERNAME="staff",
    ADMIN_PASSWORD="test-password",
    SESSION_SECRET="test-secret",
    STORAGE_DIR=f"{_files}/storage",
    MODEL_DIR=f"{_files}/models",
    CONTENT_DIR=str(ROOT.parent / "content"),
    APP_RATE_LIMIT_PER_MINUTE="100000",
    # Synthetic test images use a low threshold.
    MIN_SHARPNESS="30",
)

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.cli import create_key, seed  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.inference import ModelCard, ModelRegistry  # noqa: E402
from app.main import create_app  # noqa: E402


class FakeModel:
    def __init__(self, card: ModelCard, output: list[float]) -> None:
        self.card = card
        self.output = output

    def predict(self, batch: np.ndarray) -> np.ndarray:
        assert batch.shape == (1, self.card.input_size, self.card.input_size, 3)
        return np.array([self.output], dtype=np.float32)


def _card(name: str, classes: list[str], experimental: list[str] | None = None) -> ModelCard:
    return ModelCard(
        name=name,
        version="1.0.0",
        input_size=224,
        classes=classes,
        temperature=1.0,
        thresholds={label: 0.7 for label in classes},
        experimental_classes=experimental or [],
    )


@pytest.fixture(scope="session", autouse=True)
def migrated():
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clean_database(migrated):
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE plans, tenants, api_keys, usage_counters, usage_events, classes, advice,"
                " places, model_versions, packs, diagnosis_log, contributions, reports"
                " RESTART IDENTITY CASCADE"
            )
        )
    with SessionLocal() as db:
        seed(db, get_settings().content_dir)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def models() -> ModelRegistry:
    return ModelRegistry(
        {
            "gate": FakeModel(_card("gate", ["cassava_leaf", "maize_leaf", "other"]), [0.98, 0.01, 0.01]),
            "cassava": FakeModel(
                _card("cassava", ["healthy", "cassava_mosaic", "cassava_brown_streak"]),
                [0.02, 0.95, 0.03],
            ),
            "maize": FakeModel(
                _card(
                    "maize",
                    ["healthy", "maize_leaf_blight", "maize_streak_virus", "fall_armyworm"],
                    ["fall_armyworm"],
                ),
                [0.01, 0.01, 0.01, 0.97],
            ),
        }
    )


@pytest.fixture
def client(models):
    with TestClient(create_app(models)) as test_client:
        yield test_client


@pytest.fixture
def api_key(db) -> str:
    return create_key(db, "acme", "Acme Agri", "starter")


@pytest.fixture
def auth(api_key) -> dict[str, str]:
    return {"X-API-Key": api_key}
