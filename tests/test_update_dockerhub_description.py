import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import importlib
dockerhub = importlib.import_module("update-dockerhub-description")

clean_tag = dockerhub.clean_tag
format_tag_line = dockerhub.format_tag_line
get_versions_table = dockerhub.get_versions_table
update_docker_description = dockerhub.update_docker_description


# ---------------------------------------------------------------------------
# clean_tag
# ---------------------------------------------------------------------------
class TestCleanTag:
    def test_with_colon(self):
        assert clean_tag("valkey/valkey-bundle:9.0.1-bookworm") == "9.0.1-bookworm"

    def test_without_colon(self):
        assert clean_tag("9.0.1") == "9.0.1"

    def test_multiple_colons(self):
        assert clean_tag("a:b:c") == "b:c"


# ---------------------------------------------------------------------------
# format_tag_line
# ---------------------------------------------------------------------------
class TestFormatTagLine:
    def test_valid_entry(self):
        entry = {
            "name": "9.0-debian",
            "meta": {
                "entries": [{
                    "tags": ["valkey/valkey-bundle:9.0.1", "valkey/valkey-bundle:9.0"],
                    "directory": "9.0/debian",
                }]
            },
        }
        result = format_tag_line(entry)
        assert "`9.0.1`" in result
        assert "`9.0`" in result
        assert "9.0/debian/Dockerfile" in result

    def test_missing_entries_raises(self):
        with pytest.raises(KeyError):
            format_tag_line({"meta": {"entries": []}})

    def test_missing_tags_raises(self):
        entry = {"meta": {"entries": [{"tags": [], "directory": "x"}]}}
        with pytest.raises(KeyError):
            format_tag_line(entry)

    def test_missing_directory_raises(self):
        entry = {"meta": {"entries": [{"tags": ["t:v"]}]}}
        with pytest.raises(KeyError):
            format_tag_line(entry)


# ---------------------------------------------------------------------------
# get_versions_table
# ---------------------------------------------------------------------------
class TestGetVersionsTable:
    def test_generates_table_rows(self, tmp_path, monkeypatch):
        versions = {
            "unstable": {
                "version": "unstable",
                "valkey-server": {"version": "unstable"},
                "modules": {
                    "valkey-json": {"version": "1.0.0"},
                    "valkey-bloom": {"version": "1.0.0"},
                    "valkey-search": {"version": "1.0.0"},
                    "valkey-ldap": {"version": "1.0.0"},
                },
            },
            "9.0": {
                "version": "9.0.1",
                "valkey-server": {"version": "9.0.2"},
                "modules": {
                    "valkey-json": {"version": "1.0.1"},
                    "valkey-bloom": {"version": "1.0.1"},
                    "valkey-search": {"version": "1.0.1"},
                    "valkey-ldap": {"version": "1.0.0"},
                },
            },
        }
        vfile = tmp_path / "versions.json"
        vfile.write_text(json.dumps(versions))
        monkeypatch.chdir(tmp_path)

        table = get_versions_table()
        lines = table.strip().split("\n")
        assert len(lines) == 2  # unstable + 9.0
        # unstable row should NOT have a bundle link
        assert "| unstable |" in lines[0]
        # 9.0 row should have a bundle release link
        assert "9.0.1" in lines[1]
        assert "valkey-bundle/releases/tag/9.0.1" in lines[1]

    def test_sorts_numeric_descending(self, tmp_path, monkeypatch):
        versions = {
            "unstable": {
                "version": "unstable",
                "valkey-server": {"version": "unstable"},
                "modules": {
                    "valkey-json": {"version": "1.0.0"},
                    "valkey-bloom": {"version": "1.0.0"},
                    "valkey-search": {"version": "1.0.0"},
                    "valkey-ldap": {"version": "1.0.0"},
                },
            },
            "8.1": {
                "version": "8.1.1",
                "valkey-server": {"version": "8.1.2"},
                "modules": {
                    "valkey-json": {"version": "1.0.0"},
                    "valkey-bloom": {"version": "1.0.0"},
                    "valkey-search": {"version": "1.0.0"},
                    "valkey-ldap": {"version": "1.0.0"},
                },
            },
            "9.0": {
                "version": "9.0.1",
                "valkey-server": {"version": "9.0.2"},
                "modules": {
                    "valkey-json": {"version": "1.0.0"},
                    "valkey-bloom": {"version": "1.0.0"},
                    "valkey-search": {"version": "1.0.0"},
                    "valkey-ldap": {"version": "1.0.0"},
                },
            },
        }
        vfile = tmp_path / "versions.json"
        vfile.write_text(json.dumps(versions))
        monkeypatch.chdir(tmp_path)

        table = get_versions_table()
        lines = table.strip().split("\n")
        # Order: unstable, 9.0, 8.1
        assert "unstable" in lines[0]
        assert "9.0.1" in lines[1]
        assert "8.1.1" in lines[2]


# ---------------------------------------------------------------------------
# update_docker_description (integration-style)
# ---------------------------------------------------------------------------
class TestUpdateDockerDescription:
    def _setup_files(self, tmp_path, monkeypatch):
        versions = {
            "unstable": {
                "version": "unstable",
                "valkey-server": {"version": "unstable"},
                "modules": {
                    "valkey-json": {"version": "1.0.0"},
                    "valkey-bloom": {"version": "1.0.0"},
                    "valkey-search": {"version": "1.0.0"},
                    "valkey-ldap": {"version": "1.0.0"},
                },
            },
            "9.0": {
                "version": "9.0.1",
                "valkey-server": {"version": "9.0.2"},
                "modules": {
                    "valkey-json": {"version": "1.0.1"},
                    "valkey-bloom": {"version": "1.0.1"},
                    "valkey-search": {"version": "1.0.1"},
                    "valkey-ldap": {"version": "1.0.0"},
                },
            },
        }
        (tmp_path / "versions.json").write_text(json.dumps(versions))
        monkeypatch.chdir(tmp_path)

        template = "{official_releases}{release_candidates_section}{unstable_section}\nTable:\n{versions_table}"
        template_file = tmp_path / "template.md"
        template_file.write_text(template)

        strategy = {
            "matrix": {
                "include": [
                    {
                        "name": "9.0-debian",
                        "meta": {"entries": [{"tags": ["bundle:9.0.1"], "directory": "9.0/debian"}]},
                    },
                    {
                        "name": "unstable-debian",
                        "meta": {"entries": [{"tags": ["bundle:unstable"], "directory": "unstable/debian"}]},
                    },
                ]
            }
        }
        strategy_file = tmp_path / "strategy.json"
        strategy_file.write_text(json.dumps(strategy))

        return strategy_file, template_file

    def test_produces_output_file(self, tmp_path, monkeypatch):
        strategy_file, template_file = self._setup_files(tmp_path, monkeypatch)
        output_file = tmp_path / "output.md"

        update_docker_description(str(strategy_file), str(template_file), str(output_file))
        assert output_file.exists()
        content = output_file.read_text()
        assert "Official releases" in content
        assert "Latest unstable" in content

    def test_no_rc_section_when_none(self, tmp_path, monkeypatch):
        strategy_file, template_file = self._setup_files(tmp_path, monkeypatch)
        output_file = tmp_path / "output.md"

        update_docker_description(str(strategy_file), str(template_file), str(output_file))
        content = output_file.read_text()
        assert "Release candidates" not in content
