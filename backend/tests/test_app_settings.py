import pytest

from app.core.config import Settings
from app.models.enums import DevigMethod
from app.models.settings import AppSettings
from app.services.app_settings import (
    AppSettingsError,
    get_effective_settings,
    get_or_create_app_settings,
    update_app_settings,
)

ENV_SETTINGS = Settings(_env_file=None)


class TestGetOrCreateAppSettings:
    def test_creates_singleton_seeded_from_env_settings(self, db_session):
        row = get_or_create_app_settings(db_session, env_settings=ENV_SETTINGS)
        assert row.devig_method == DevigMethod(ENV_SETTINGS.devig_method)
        assert float(row.kelly_fraction) == pytest.approx(ENV_SETTINGS.kelly_fraction)
        assert float(row.default_bankroll) == pytest.approx(ENV_SETTINGS.default_bankroll)

    def test_is_idempotent(self, db_session):
        first = get_or_create_app_settings(db_session, env_settings=ENV_SETTINGS)
        second = get_or_create_app_settings(db_session, env_settings=ENV_SETTINGS)
        assert first.id == second.id
        assert db_session.query(AppSettings).count() == 1


class TestUpdateAppSettings:
    def test_updates_only_provided_fields(self, db_session):
        row = get_or_create_app_settings(db_session, env_settings=ENV_SETTINGS)
        updated = update_app_settings(db_session, row, kelly_fraction=0.5)
        assert float(updated.kelly_fraction) == pytest.approx(0.5)
        assert float(updated.edge_threshold) == pytest.approx(ENV_SETTINGS.edge_threshold)

    def test_devig_method_accepts_valid_string(self, db_session):
        row = get_or_create_app_settings(db_session, env_settings=ENV_SETTINGS)
        updated = update_app_settings(db_session, row, devig_method="shin")
        assert updated.devig_method == DevigMethod.SHIN

    def test_rejects_invalid_devig_method(self, db_session):
        row = get_or_create_app_settings(db_session, env_settings=ENV_SETTINGS)
        with pytest.raises(AppSettingsError):
            update_app_settings(db_session, row, devig_method="banana")

    def test_rejects_kelly_fraction_out_of_range(self, db_session):
        row = get_or_create_app_settings(db_session, env_settings=ENV_SETTINGS)
        with pytest.raises(AppSettingsError):
            update_app_settings(db_session, row, kelly_fraction=1.5)
        with pytest.raises(AppSettingsError):
            update_app_settings(db_session, row, kelly_fraction=0)

    def test_rejects_negative_default_bankroll(self, db_session):
        row = get_or_create_app_settings(db_session, env_settings=ENV_SETTINGS)
        with pytest.raises(AppSettingsError):
            update_app_settings(db_session, row, default_bankroll=-1)

    def test_rejects_non_positive_stale_odds_minutes(self, db_session):
        row = get_or_create_app_settings(db_session, env_settings=ENV_SETTINGS)
        with pytest.raises(AppSettingsError):
            update_app_settings(db_session, row, stale_odds_minutes=0)

    def test_monthly_loss_limit_can_be_set_and_cleared(self, db_session):
        row = get_or_create_app_settings(db_session, env_settings=ENV_SETTINGS)
        updated = update_app_settings(db_session, row, monthly_loss_limit=200.0)
        assert float(updated.monthly_loss_limit) == pytest.approx(200.0)

        cleared = update_app_settings(db_session, row, monthly_loss_limit=None)
        assert cleared.monthly_loss_limit is None

    def test_rejects_explicit_null_for_non_nullable_field(self, db_session):
        row = get_or_create_app_settings(db_session, env_settings=ENV_SETTINGS)
        with pytest.raises(AppSettingsError):
            update_app_settings(db_session, row, kelly_fraction=None)

    def test_rejects_unknown_field(self, db_session):
        row = get_or_create_app_settings(db_session, env_settings=ENV_SETTINGS)
        with pytest.raises(AppSettingsError):
            update_app_settings(db_session, row, not_a_real_field=1)


class TestGetEffectiveSettings:
    def test_overrides_only_tunable_fields(self, db_session):
        row = get_or_create_app_settings(db_session, env_settings=ENV_SETTINGS)
        update_app_settings(db_session, row, kelly_fraction=0.4, edge_threshold=0.05)

        effective = get_effective_settings(db_session, env_settings=ENV_SETTINGS)

        assert effective.kelly_fraction == pytest.approx(0.4)
        assert effective.edge_threshold == pytest.approx(0.05)
        # Untouched infra-level fields still come straight from the env settings.
        assert effective.database_url == ENV_SETTINGS.database_url
        assert effective.odds_api_base_url == ENV_SETTINGS.odds_api_base_url

    def test_defaults_match_env_settings_when_no_overrides_made(self, db_session):
        effective = get_effective_settings(db_session, env_settings=ENV_SETTINGS)
        assert effective.devig_method == ENV_SETTINGS.devig_method
        assert effective.kelly_cap_pct == pytest.approx(ENV_SETTINGS.kelly_cap_pct)
        assert effective.stale_odds_minutes == ENV_SETTINGS.stale_odds_minutes
