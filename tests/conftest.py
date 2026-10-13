import os
import sys
import tempfile
from pathlib import Path

import pytest

# Isolated data directory for the whole test session (set before the app is imported).
os.environ["AHDAF_DATA_DIR"] = tempfile.mkdtemp(prefix="ahdaf-test-")
os.environ["AI_PROVIDER"] = "rules"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.data import db, seed  # noqa: E402
from app.data import repositories as repo  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded():
    db.reset_connection(config.DB_PATH)
    seed.ensure_seeded(with_demo=True)
    yield


@pytest.fixture()
def library():
    return repo.library.all_active()


@pytest.fixture()
def settings():
    return repo.settings.get_all()


def make_inputs(**over):
    base = {
        "client": {"name": "شركة النموذج للتجارب", "sector": "automotive", "about": ""},
        "project": {"name": "إدارة حساب تيك توك", "type": "social_media", "description": "إدارة حساب الشركة على تيك توك.",
                    "audience": "", "platforms": ["tiktok"]},
        "scope": {"description": "", "out_of_scope": ""},
        "services": {"selected": [], "custom": []},
        "timeline": {"duration_value": 6, "duration_unit": "month", "start_date": "2026-11-01"},
        "goals": {"objectives": "", "deliverables": ""},
        "preferences": {"tone": "corporate", "detail": "medium"},
    }
    for k, v in over.items():
        base[k] = {**base.get(k, {}), **v}
    return base
