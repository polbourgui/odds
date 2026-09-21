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
