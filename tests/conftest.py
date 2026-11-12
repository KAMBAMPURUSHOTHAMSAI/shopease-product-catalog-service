import os
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-characters")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_ISSUER", "shopease-auth-service")
os.environ.setdefault("LOW_STOCK_THRESHOLD", "5")
import pytest
from datetime import datetime, timedelta, timezone
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database.connection import Base, get_db
from app.main import app

TEST_KEY = os.environ["JWT_SECRET_KEY"]
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def override_get_db():
    db=TestingSessionLocal()
    try: yield db
    finally: db.close()
app.dependency_overrides[get_db]=override_get_db
@pytest.fixture
def client():
    return TestClient(app)

def make_token(user_id=1, role="admin", minutes=30):
    now=datetime.now(timezone.utc)
    return jwt.encode({"sub":str(user_id),"role":role,"iss":"shopease-auth-service","iat":now,"exp":now+timedelta(minutes=minutes)}, TEST_KEY, algorithm="HS256")
@pytest.fixture
def admin_headers(): return {"Authorization": f"Bearer {make_token(1,'admin')}"}
@pytest.fixture
def customer_headers(): return {"Authorization": f"Bearer {make_token(2,'customer')}"}
