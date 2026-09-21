from app.core.config import Settings


class TestAnjBookmakerKeys:
    def test_defaults_to_a_non_empty_list(self):
        settings = Settings(_env_file=None)
        assert settings.anj_bookmaker_keys == [
            "winamax_fr",
            "betclic",
            "unibet_fr",
            "zebet_fr",
            "pmu_fr",
        ]

    def test_parses_comma_separated_env_value(self, monkeypatch):
        monkeypatch.setenv("ANJ_BOOKMAKER_KEYS", "winamax_fr,betclic")
        settings = Settings(_env_file=None)
        assert settings.anj_bookmaker_keys == ["winamax_fr", "betclic"]

    def test_strips_whitespace_around_entries(self, monkeypatch):
        monkeypatch.setenv("ANJ_BOOKMAKER_KEYS", " winamax_fr , betclic ")
        settings = Settings(_env_file=None)
        assert settings.anj_bookmaker_keys == ["winamax_fr", "betclic"]


class TestDatabaseUrlNormalization:
    def test_rewrites_postgres_scheme_to_psycopg_dialect(self):
        settings = Settings(
            _env_file=None, database_url="postgres://u:p@host:5432/db"
        )
        assert settings.database_url == "postgresql+psycopg://u:p@host:5432/db"

    def test_rewrites_plain_postgresql_scheme_to_psycopg_dialect(self):
        settings = Settings(
            _env_file=None, database_url="postgresql://u:p@host:5432/db"
        )
        assert settings.database_url == "postgresql+psycopg://u:p@host:5432/db"

    def test_leaves_an_already_explicit_dialect_untouched(self):
        settings = Settings(
            _env_file=None, database_url="postgresql+psycopg://u:p@host:5432/db"
        )
        assert settings.database_url == "postgresql+psycopg://u:p@host:5432/db"
