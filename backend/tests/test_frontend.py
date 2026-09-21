from app.core.frontend import resolve_frontend_path


class TestResolveFrontendPath:
    def test_root_path_serves_index_html(self, tmp_path):
        (tmp_path / "index.html").write_text("<html>root</html>")

        assert resolve_frontend_path(tmp_path, "") == tmp_path / "index.html"

    def test_existing_asset_is_served_as_is(self, tmp_path):
        (tmp_path / "index.html").write_text("<html>root</html>")
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        bundle = assets_dir / "index-abc123.js"
        bundle.write_text("console.log('hi')")

        assert resolve_frontend_path(tmp_path, "assets/index-abc123.js") == bundle

    def test_client_side_route_falls_back_to_index_html(self, tmp_path):
        (tmp_path / "index.html").write_text("<html>root</html>")

        assert resolve_frontend_path(tmp_path, "stats") == tmp_path / "index.html"
        assert resolve_frontend_path(tmp_path, "events/3") == tmp_path / "index.html"
