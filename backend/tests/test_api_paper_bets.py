from tests.test_value_bets import build_1x2_market


class TestBankrollEndpoints:
    def test_get_creates_default_bankroll(self, client):
        response = client.get("/api/bankroll")
        assert response.status_code == 200
        body = response.json()
        assert body["current_balance"] == body["initial_balance"]
        assert body["current_balance"] > 0

    def test_patch_updates_name_and_balance(self, client):
        client.get("/api/bankroll")  # ensure it exists
        response = client.patch(
            "/api/bankroll", json={"name": "Ma bankroll", "initial_balance": 2000}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Ma bankroll"
        assert body["initial_balance"] == 2000

    def test_patch_rejects_negative_balance(self, client):
        response = client.patch("/api/bankroll", json={"initial_balance": -5})
        assert response.status_code == 422  # Pydantic ge=0 validation

    def test_reset_restores_current_balance(self, client, db_session):
        client.get("/api/bankroll")
        client.patch("/api/bankroll", json={"initial_balance": 500})
        response = client.post("/api/bankroll/reset")
        assert response.status_code == 200
        body = response.json()
        assert body["current_balance"] == body["initial_balance"] == 500


class TestPaperBetEndpoints:
    def test_place_and_list_bet(self, client, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        home_sel = scenario["selections"]["home"]

        response = client.post(
            "/api/paper-bets",
            json={"selection_id": home_sel.id, "bookmaker_slug": "winamax_fr"},
        )
        assert response.status_code == 201
        bet = response.json()
        assert bet["status"] == "pending"
        assert bet["odds_taken"] == 2.3
        assert bet["home_name"] == "Arsenal"
        assert bet["bookmaker_slug"] == "winamax_fr"

        listing = client.get("/api/paper-bets")
        assert listing.status_code == 200
        assert len(listing.json()) == 1

    def test_place_bet_with_insufficient_edge_returns_400(self, client, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.10)
        home_sel = scenario["selections"]["home"]

        response = client.post(
            "/api/paper-bets",
            json={"selection_id": home_sel.id, "bookmaker_slug": "winamax_fr"},
        )
        assert response.status_code == 400

    def test_settle_bet(self, client, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        home_sel = scenario["selections"]["home"]
        placed = client.post(
            "/api/paper-bets",
            json={"selection_id": home_sel.id, "bookmaker_slug": "winamax_fr"},
        ).json()

        response = client.post(f"/api/paper-bets/{placed['id']}/settle", json={"status": "won"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "won"
        assert body["payout"] == body["stake"] * body["odds_taken"]

    def test_settle_already_settled_bet_returns_400(self, client, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        home_sel = scenario["selections"]["home"]
        placed = client.post(
            "/api/paper-bets",
            json={"selection_id": home_sel.id, "bookmaker_slug": "winamax_fr"},
        ).json()
        client.post(f"/api/paper-bets/{placed['id']}/settle", json={"status": "won"})

        response = client.post(f"/api/paper-bets/{placed['id']}/settle", json={"status": "lost"})
        assert response.status_code == 400

    def test_list_filters_by_status(self, client, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        home_sel = scenario["selections"]["home"]
        placed = client.post(
            "/api/paper-bets",
            json={"selection_id": home_sel.id, "bookmaker_slug": "winamax_fr"},
        ).json()
        client.post(f"/api/paper-bets/{placed['id']}/settle", json={"status": "won"})

        pending = client.get("/api/paper-bets", params={"status": "pending"})
        assert pending.json() == []

        won = client.get("/api/paper-bets", params={"status": "won"})
        assert len(won.json()) == 1
