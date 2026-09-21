from app.services.normalization import normalize_name, similarity


class TestNormalizeName:
    def test_strips_accents_and_lowercases(self):
        assert normalize_name("Étoile Rouge") == "etoile rouge"

    def test_removes_generic_club_suffixes(self):
        assert normalize_name("Arsenal FC") == "arsenal"
        assert normalize_name("AC Milan") == "milan"

    def test_collapses_punctuation_and_whitespace(self):
        assert normalize_name("Paris  Saint-Germain") == "paris saint germain"

    def test_idempotent(self):
        name = "Real Madrid CF"
        assert normalize_name(normalize_name(name)) == normalize_name(name)


class TestSimilarity:
    def test_identical_strings_score_one(self):
        assert similarity("arsenal", "arsenal") == 1.0

    def test_unrelated_strings_score_low(self):
        assert similarity("arsenal", "real sociedad") <= 0.4

    def test_close_variants_score_high(self):
        a = normalize_name("Manchester United")
        b = normalize_name("Manchester Utd")
        assert similarity(a, b) > 0.85
