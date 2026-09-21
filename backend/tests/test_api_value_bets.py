import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from tests.test_value_bets import build_1x2_market


@pytest.fixture
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestHealth:
    def test_health_endpoint(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestValueBetsEndpoint:
    def test_returns_expected_shape_and_values(self, client, db_session):
        build_1x2_market(db_session, home_odds=2.30)

        response = client.get("/api/value-bets")
        assert response.status_code == 200

        body = response.json()
        assert len(body) == 1
        bet = body[0]

        assert bet["bookmaker_slug"] == "winamax_fr"
        assert bet["sport_slug"] == "soccer"
        assert bet["home_name"] == "Arsenal"
        assert bet["away_name"] == "Chelsea"
        assert bet["selection_code"] == "home"
        assert bet["market_type"] == "1x2"
        assert bet["book_odds"] == pytest.approx(2.30)
        assert bet["edge"] > 0
        assert bet["kelly_stake"] > 0
        assert "captured_at" in bet
        assert "reference_captured_at" in bet

    def test_edge_min_filter(self, client, db_session):
        build_1x2_market(db_session, home_odds=2.30)
        response = client.get("/api/value-bets", params={"edge_min": 0.5})
        assert response.status_code == 200
        assert response.json() == []

    def test_sport_filter(self, client, db_session):
        build_1x2_market(db_session, home_odds=2.30)
        response = client.get("/api/value-bets", params={"sport": "tennis"})
        assert response.status_code == 200
        assert response.json() == []

    def test_market_filter(self, client, db_session):
        build_1x2_market(db_session, home_odds=2.30)

        matching = client.get("/api/value-bets", params={"market": "1x2"})
        assert len(matching.json()) == 1

        non_matching = client.get("/api/value-bets", params={"market": "over_under"})
        assert non_matching.json() == []

    def test_bookmaker_filter(self, client, db_session):
        build_1x2_market(db_session, home_odds=2.30)
        response = client.get("/api/value-bets", params={"bookmaker": "betclic"})
        assert response.status_code == 200
        assert response.json() == []


class TestMetaEndpoints:
    def test_sports_endpoint(self, client, db_session):
        build_1x2_market(db_session, home_odds=2.30)
        response = client.get("/api/sports")
        assert response.status_code == 200
        slugs = {s["slug"] for s in response.json()}
        assert slugs == {"soccer"}

    def test_bookmakers_endpoint_only_lists_anj_licensed(self, client, db_session):
        build_1x2_market(db_session, home_odds=2.30)
        response = client.get("/api/bookmakers")
        assert response.status_code == 200
        slugs = {b["slug"] for b in response.json()}
        assert slugs == {"winamax_fr"}
        assert "pinnacle" not in slugs
