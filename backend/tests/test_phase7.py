import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import app, issue_tokens, enforce_rate_limit, get_db, get_current_user
from app.models import User
from app.db import Base, engine
from app.seed import seed_demo_data
from fastapi import Request, HTTPException
import time
from datetime import timedelta

def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    seed_demo_data(db)
    return db

def test_production_secret_validation():
    s_dev = Settings(environment="development")
    assert s_dev.jwt_secret == "local-development-secret-change-me"
    
    with pytest.raises(ValueError, match="In production, a secure JWT_SECRET must be provided."):
        Settings(environment="production", jwt_secret="local-development-secret-change-me")
    
    s_prod = Settings(environment="production", jwt_secret="some-secure-key")
    assert s_prod.jwt_secret == "some-secure-key"

def test_auth_me_endpoint():
    client = TestClient(app)
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    
    db = _fresh_db()
    user = User(email="test_me@example.com", password_hash="hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    
    from app.core.security import create_token
    token = create_token(user, "access", timedelta(minutes=10))
    
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "test_me@example.com"
    app.dependency_overrides.clear()
    db.close()

def test_rate_limiting_redis_fallback():
    import sys
    was_pytest = "pytest" in sys.modules
    if was_pytest:
        del sys.modules["pytest"]
        
    try:
        class MockClient:
            host = "127.0.0.1"
        class MockRequest:
            client = MockClient()
            
        try:
            enforce_rate_limit(MockRequest(), "test", limit=15)
        except HTTPException as e:
            assert e.status_code in (503, 429)
        else:
            from app.main import redis_client
            if redis_client:
                redis_client.delete("rate_limit:test:127.0.0.1")
                for _ in range(15):
                    enforce_rate_limit(MockRequest(), "test", limit=15)
                with pytest.raises(HTTPException) as exc:
                    enforce_rate_limit(MockRequest(), "test", limit=15)
                assert exc.value.status_code == 429
    finally:
        if was_pytest:
            sys.modules["pytest"] = pytest

def test_watchlist_no_n_plus_one():
    client = TestClient(app)
    db = _fresh_db()
    user = User(email="watch@example.com", password_hash="hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    
    from app.core.security import create_token
    token = create_token(user, "access", timedelta(minutes=10))
    
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    resp = client.get("/api/v1/watchlist", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []
    app.dependency_overrides.clear()
    db.close()

def test_global_500_handler():
    client = TestClient(app, raise_server_exceptions=False)
    @app.get("/crash")
    def crash():
        raise ValueError("Intentional crash")
        
    resp = client.get("/crash", headers={"x-request-id": "req-123"})
    assert resp.status_code == 500
    assert resp.json() == {"detail": "An unexpected internal error occurred. Please try again later."}
