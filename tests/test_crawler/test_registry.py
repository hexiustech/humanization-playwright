"""Tests for the script registry."""

import json
import pytest

from humanization.crawler.registry import ScriptRegistry


@pytest.fixture
def registry(tmp_path):
    return ScriptRegistry(tmp_path / "scripts")


class TestScriptRegistry:
    def test_creates_dir(self, tmp_path):
        scripts_dir = tmp_path / "new_scripts"
        ScriptRegistry(scripts_dir)
        assert scripts_dir.exists()

    def test_find_pattern_script_empty(self, registry):
        assert registry.find_pattern_script("table_data") is None

    def test_find_domain_script_empty(self, registry):
        assert registry.find_domain_script("example.com") is None

    def test_save_and_find_pattern_script(self, registry):
        code = "async def extract(page): return {'data': 'test'}"
        filename = registry.save_script(code, "table_data", "example.com")
        assert filename == "pattern_table_data.py"

        found = registry.find_pattern_script("table_data")
        assert found == "pattern_table_data.py"

    def test_save_and_find_domain_script(self, registry):
        code = "async def extract(page): return {'data': 'test'}"
        filename = registry.save_script(
            code, "table_data", "example.com", is_domain_specific=True
        )
        assert filename == "domain_example_com.py"

        found = registry.find_domain_script("example.com")
        assert found == "domain_example_com.py"

    def test_load_script(self, registry):
        code = "async def extract(page): return {'data': 'hello'}"
        filename = registry.save_script(code, "generic", "test.com")
        loaded = registry.load_script(filename)
        assert loaded == code

    def test_record_success(self, registry):
        code = "async def extract(page): return {'data': 'test'}"
        registry.save_script(code, "table_data", "a.com")
        registry.record_success("table_data", "a.com")
        registry.record_success("table_data", "b.com")

        data = json.loads(registry.registry_file.read_text())
        entry = data["patterns"]["table_data"]
        assert entry["success_count"] == 2
        assert "b.com" in entry["domains_tested"]

    def test_record_failure(self, registry):
        code = "async def extract(page): return {'data': 'test'}"
        registry.save_script(code, "table_data", "a.com")
        registry.record_failure("table_data", "a.com")

        data = json.loads(registry.registry_file.read_text())
        assert data["patterns"]["table_data"]["fail_count"] == 1

    def test_domain_sanitization(self, registry):
        code = "async def extract(page): return {'data': 'test'}"
        filename = registry.save_script(
            code, "generic", "my-site.example.com", is_domain_specific=True
        )
        assert filename == "domain_my_site_example_com.py"

    def test_domain_tracks_patterns(self, registry):
        code = "async def extract(page): return {'data': 'test'}"
        registry.save_script(code, "table_data", "example.com", is_domain_specific=True)

        data = json.loads(registry.registry_file.read_text())
        assert "table_data" in data["domains"]["example.com"]["patterns_handled"]

    def test_registry_persists_across_instances(self, tmp_path):
        scripts_dir = tmp_path / "scripts"
        reg1 = ScriptRegistry(scripts_dir)
        code = "async def extract(page): return {'data': 'ok'}"
        reg1.save_script(code, "table_data", "a.com")

        reg2 = ScriptRegistry(scripts_dir)
        assert reg2.find_pattern_script("table_data") == "pattern_table_data.py"
