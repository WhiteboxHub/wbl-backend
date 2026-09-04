import os
import uuid
import pytest
import logging
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

# Suppress all post-exit closed-stream logging tracebacks during test runs
logging.raiseExceptions = False

# 1. Set Mock Environment Variables BEFORE any imports happen
os.environ["SECRET_KEY"] = "mock_test_secret_key_12345"  # pragma: allowlist secret
os.environ["ALGORITHM"] = "HS256"
os.environ["UPSTASH_REDIS_REST_URL"] = "https://mock-redis.upstash.io"
os.environ["UPSTASH_REDIS_REST_TOKEN"] = "mock_token"
os.environ["DB_PASSWORD"] = "mock_password"  # pragma: allowlist secret
os.environ["DB_HOST"] = "localhost"
os.environ["DB_NAME"] = "wbl_test"
os.environ["ENV"] = "test"
os.environ["MAIL_PORT"] = "587"
os.environ["MAIL_USERNAME"] = "mock_username"
os.environ["MAIL_PASSWORD"] = "mock_password"  # pragma: allowlist secret
os.environ["MAIL_SERVER"] = "smtp.mock.com"
os.environ["MAIL_FROM"] = "mock@mock.com"



from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from jose import jwt
from fastapi.testclient import TestClient

# 2. Setup an In-Memory SQLite Test Database Engine
TEST_DATABASE_URL = "sqlite:///:memory:"  # In-memory SQLite
engine = create_engine(
    TEST_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Globally override SessionLocal and engine BEFORE any other module imports it
import fapi.db.database
fapi.db.database.SessionLocal = TestingSessionLocal
fapi.db.database.engine = engine

# Now it is safe to import backend modules
from fapi.main import app
from fapi.db.database import get_db
from fapi.db.models import Base, AuthUserORM, CandidateORM
from fapi.core.redis_client import redis_client, RedisClient


# ── 4. Helpers ───────────────────────────────────────────────────────────────

_SECRET_KEY = os.environ["SECRET_KEY"]
_ALGORITHM = os.environ.get("ALGORITHM", "HS256")


def _forge_token(user_id: int, uname: str, role: str = "admin", is_admin: bool = True) -> str:
    """Forge a signed JWT for testing — same secret the app uses."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "uname": uname,
        "role": role,
        "is_admin": is_admin,
        "exp": now + timedelta(hours=2),
        "iat": now,
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all tables at the start of the testing session, clean up at the end."""
    # SQLite requires index names to be unique across the entire database.
    # We dynamically rename duplicate indexes so production code doesn't need to change.
    seen_indexes = {}
    for table in Base.metadata.tables.values():
        for index in list(table.indexes):
            if index.name:
                if index.name in seen_indexes:
                    index.name = f"{index.name}_{table.name}"
                else:
                    seen_indexes[index.name] = table.name
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session():
    """Yields a clean database session for a single test, then rolls back changes."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

# 4. Intercept FastAPI's DB dependency and route it to our Test Database
@pytest.fixture(autouse=True)
def override_db_dependency(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()

# 5. Mock the Upstash Redis Client so it never hits the actual internet
@pytest.fixture(autouse=True)
def mock_redis():
    mock_client = MagicMock()
    # Stub common redis operations — ping() succeeds by default on MagicMock
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    # Patch the CLASS attribute so get_client() (a classmethod) returns our mock
    original_client = RedisClient._client
    RedisClient._client = mock_client
    yield mock_client
    RedisClient._client = original_client


# Mock the AIPrep YouTube Client so unit tests never hit live YouTube Data API
@pytest.fixture(autouse=True)
def mock_youtube_client_in_tests(monkeypatch):
    try:
        from fapi.ai_prep.clients.youtube_client import youtube_client
        from fapi.ai_prep.clients.youtube_account_manager import youtube_account_pool, YouTubeAccount

        mock_acc = YouTubeAccount(
            account_id="test_mock_account",
            refresh_token="mock_refresh_token",
            client_id="mock_client_id",
            client_secret="mock_client_secret",
            daily_limit=9999,
        )
        monkeypatch.setattr(youtube_account_pool, "_accounts", [mock_acc])
        monkeypatch.setattr(youtube_client, "has_live_credentials", lambda: True)
        monkeypatch.setattr(youtube_client, "_upload_live_api", lambda *args, **kwargs: {
            "video_id": "yt_test_mock_vid123",
            "youtube_url": "https://youtube.com/watch?v=yt_test_mock_vid123",
            "status": "unlisted",
            "account_id": "test_mock_account",
        })
        monkeypatch.setattr(youtube_client, "delete_video", lambda vid: True)
    except Exception:
        pass
    yield




# Mock FFmpeg execution in unit tests if ffmpeg binary is not installed on test host
@pytest.fixture(autouse=True)
def mock_ffmpeg_in_tests(monkeypatch):
    import subprocess
    original_run = subprocess.run

    def safe_subprocess_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and cmd and ("ffmpeg" in str(cmd[0]) or "ffmpeg" in str(cmd)):
            output_file = cmd[-1]
            if isinstance(output_file, str) and (output_file.endswith(".wav") or "audio" in output_file):
                with open(output_file, "wb") as f:
                    f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
            res = MagicMock()
            res.returncode = 0
            res.stdout = b""
            res.stderr = b""
            return res
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", safe_subprocess_run)
    yield



# 6. Create a Reusable API Client for our Tests
@pytest.fixture
def client():
    """Provides a TestClient to make mock HTTP requests to our FastAPI app."""
    with TestClient(app) as c:
        yield c

@pytest.fixture
def admin_user(db_session):
    uid = uuid.uuid4().hex[:8]
    user = AuthUserORM(
        uname=f"admin_{uid}@test.com",
        passwd="hashed_password",  # pragma: allowlist secret
        status="active",
        role="admin",
        enddate=date(1990,1 ,1),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def admin_headers(admin_user):
    """Authorization headers pre-loaded with a valid admin JWT."""
    token = _forge_token(admin_user.id, admin_user.uname, role="admin", is_admin=True)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def candidate_db_user(db_session):
    uid = uuid.uuid4().hex[:8]
    email = f"candidate_{uid}@test.com"
    auth_user = AuthUserORM(
        uname=email,
        passwd="hashed_password",  # pragma: allowlist secret
        status="active",
        role="candidate",
        enddate=date(1990,1 ,1),
    )
    db_session.add(auth_user)
    db_session.commit()
    db_session.refresh(auth_user)

    candidate = CandidateORM(
        full_name="Test Candidate",
        email=email,
        status="active",
        phone="555-0000",
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)

    return {"auth_user": auth_user, "candidate": candidate}

@pytest.fixture
def candidate_headers(candidate_db_user):
    auth_user = candidate_db_user["auth_user"]
    token = _forge_token(auth_user.id, auth_user.uname, role="candidate", is_admin=False)
    return {"Authorization": f"Bearer {token}"}