import csv
import io

from app.models.enums import BetStatus
from tests.test_value_bets import build_1x2_market


class TestStatsEndpoint:
    def test_returns_summary_shape(self, client):
        response = client.get("/api/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["total_bets"] == 0
        assert body["roi"] is None
        assert len(body["bankroll_curve"]) == 1

    def test_reflects_placed_and_settled_bets(self, client, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        placed = client.post(
            "/api/paper-bets",
            json={
                "selection_id": scenario["selections"]["home"].id,
                "bookmaker_slug": "winamax_fr",
            },
        ).json()
        client.post(f"/api/paper-bets/{placed['id']}/settle", json={"status": "won"})

        response = client.get("/api/stats")
        body = response.json()
        assert body["total_bets"] == 1
        assert body["wins"] == 1
        assert body["win_rate"] == 1.0
        assert body["profit"] > 0


class TestExportEndpoint:
    def test_returns_csv_with_expected_header_and_rows(self, client, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        placed = client.post(
            "/api/paper-bets",
            json={
                "selection_id": scenario["selections"]["home"].id,
                "bookmaker_slug": "winamax_fr",
            },
        ).json()
        client.post(f"/api/paper-bets/{placed['id']}/settle", json={"status": "won"})

        response = client.get("/api/paper-bets/export.csv")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers["content-disposition"]

        rows = list(csv.reader(io.StringIO(response.text)))
        header, data_row = rows[0], rows[1]
        assert header[0] == "id"
        assert "status" in header
        status_index = header.index("status")
        assert data_row[status_index] == BetStatus.WON.value

    def test_empty_history_still_returns_header_only(self, client):
        response = client.get("/api/paper-bets/export.csv")
        assert response.status_code == 200
        rows = list(csv.reader(io.StringIO(response.text)))
        assert len(rows) == 1
