from app.models.bookmakers import Bookmaker
from app.models.odds import OddsSnapshot
from tests.test_value_bets import NOW, build_1x2_market


class TestEventComparisonEndpoint:
    def test_unknown_event_returns_404(self, client):
        response = client.get("/api/events/999/comparison")
        assert response.status_code == 404

    def test_returns_expected_shape(self, client, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30, extra_books=["betclic"])
        home_sel = scenario["selections"]["home"]
        betclic = db_session.query(Bookmaker).filter_by(slug="betclic").one()
        db_session.add(
            OddsSnapshot(
                selection_id=home_sel.id, bookmaker_id=betclic.id, odds=2.20, captured_at=NOW
            )
        )
        db_session.flush()

        response = client.get(f"/api/events/{scenario['event'].id}/comparison")
        assert response.status_code == 200
        body = response.json()

        assert body["event_id"] == scenario["event"].id
        assert body["home_name"] == "Arsenal"
        assert body["away_name"] == "Chelsea"
        assert len(body["markets"]) == 1

        market = body["markets"][0]
        assert market["market_type"] == "1x2"
        home_selection = next(s for s in market["selections"] if s["selection_code"] == "home")

        slugs = {q["bookmaker_slug"] for q in home_selection["quotes"]}
        assert slugs == {"pinnacle", "winamax_fr", "betclic"}

        best = next(q for q in home_selection["quotes"] if q["is_best"])
        assert best["bookmaker_slug"] == "winamax_fr"
        assert home_selection["fair_odds"] is not None
