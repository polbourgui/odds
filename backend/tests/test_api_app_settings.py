class TestSettingsEndpoint:
    def test_get_creates_default_settings(self, client):
        response = client.get("/api/settings")
        assert response.status_code == 200
        body = response.json()
        assert body["devig_method"] == "multiplicative"
        assert body["kelly_fraction"] == 0.25

    def test_patch_updates_fields(self, client):
        client.get("/api/settings")
        response = client.patch(
            "/api/settings", json={"kelly_fraction": 0.5, "edge_threshold": 0.05}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["kelly_fraction"] == 0.5
        assert body["edge_threshold"] == 0.05

    def test_patch_rejects_out_of_range_kelly_fraction(self, client):
        response = client.patch("/api/settings", json={"kelly_fraction": 2.0})
        assert response.status_code == 422  # Pydantic Field(le=1) validation

    def test_patch_rejects_invalid_devig_method(self, client):
        response = client.patch("/api/settings", json={"devig_method": "banana"})
        assert response.status_code == 422  # Pydantic enum validation

    def test_patch_can_set_and_clear_monthly_loss_limit(self, client):
        set_response = client.patch("/api/settings", json={"monthly_loss_limit": 300})
        assert set_response.json()["monthly_loss_limit"] == 300

        clear_response = client.patch("/api/settings", json={"monthly_loss_limit": None})
        assert clear_response.json()["monthly_loss_limit"] is None

    def test_effective_settings_edge_threshold_affects_kelly_stake(self, client, db_session):
        from tests.test_value_bets import build_1x2_market

        # home_odds=2.10 -> edge ~1.4%, below the default 3% threshold -> stake 0.
        build_1x2_market(db_session, home_odds=2.10)

        with_default_threshold = client.get("/api/value-bets").json()
        assert len(with_default_threshold) == 1
        assert with_default_threshold[0]["kelly_stake"] == 0.0

        client.patch("/api/settings", json={"edge_threshold": 0.01})

        with_lower_threshold = client.get("/api/value-bets").json()
        assert with_lower_threshold[0]["kelly_stake"] > 0
