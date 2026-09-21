from app.core.config import Settings, get_settings
from app.main import app
from tests.test_value_bets import build_1x2_market


class TestApiKeyAuth:
    def test_no_key_configured_lets_requests_through(self, client):
        response = client.get("/api/value-bets")
        assert response.status_code == 200

    def test_configured_key_rejects_missing_header(self, client, db_session):
        build_1x2_market(db_session, home_odds=2.30)
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, api_key="secret123"
        )
        try:
            response = client.get("/api/value-bets")
        finally:
            del app.dependency_overrides[get_settings]
        assert response.status_code == 401

    def test_configured_key_rejects_wrong_header(self, client, db_session):
        build_1x2_market(db_session, home_odds=2.30)
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, api_key="secret123"
        )
        try:
            response = client.get("/api/value-bets", headers={"X-API-Key": "wrong"})
        finally:
            del app.dependency_overrides[get_settings]
        assert response.status_code == 401

    def test_configured_key_accepts_matching_header(self, client, db_session):
        build_1x2_market(db_session, home_odds=2.30)
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, api_key="secret123"
        )
        try:
            response = client.get("/api/value-bets", headers={"X-API-Key": "secret123"})
        finally:
            del app.dependency_overrides[get_settings]
        assert response.status_code == 200

    def test_health_endpoint_stays_open_even_with_a_key_configured(self, client):
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, api_key="secret123"
        )
        try:
            response = client.get("/api/health")
        finally:
            del app.dependency_overrides[get_settings]
        assert response.status_code == 200
