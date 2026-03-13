import copy
import json
import subprocess
import sys
import os
import pytest

# Add scripts dir to path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import importlib
update_versions = importlib.import_module("update-versions")

parse_version = update_versions.parse_version
get_latest_major_minor = update_versions.get_latest_major_minor
get_known_modules_from_versions = update_versions.get_known_modules_from_versions
update_unstable = update_versions.update_unstable
update_versions_fn = update_versions.update_versions


# ---------------------------------------------------------------------------
# parse_version
# ---------------------------------------------------------------------------
class TestParseVersion:
    def test_stable_version(self):
        assert parse_version("9.0.3") == (9, 0, 3, None)

    def test_rc_version(self):
        assert parse_version("8.1.0-rc1") == (8, 1, 0, 1)

    def test_zero_version(self):
        assert parse_version("1.0.0") == (1, 0, 0, None)

    def test_invalid_version_raises(self):
        with pytest.raises(ValueError, match="Invalid version format"):
            parse_version("not-a-version")

    def test_incomplete_version_raises(self):
        with pytest.raises(ValueError):
            parse_version("9.0")

    def test_large_numbers(self):
        assert parse_version("100.200.300-rc99") == (100, 200, 300, 99)


# ---------------------------------------------------------------------------
# get_latest_major_minor
# ---------------------------------------------------------------------------
class TestGetLatestMajorMinor:
    def test_returns_highest(self, versions_data):
        assert get_latest_major_minor(versions_data) == "9.0"

    def test_skips_unstable(self, versions_data):
        result = get_latest_major_minor(versions_data)
        assert result != "unstable"

    def test_single_numeric_key(self):
        data = {"unstable": {}, "7.2": {}}
        assert get_latest_major_minor(data) == "7.2"

    def test_ordering(self):
        data = {"unstable": {}, "8.1": {}, "9.0": {}, "10.0": {}}
        assert get_latest_major_minor(data) == "10.0"


# ---------------------------------------------------------------------------
# get_known_modules_from_versions
# ---------------------------------------------------------------------------
class TestGetKnownModules:
    def test_returns_modules_from_latest(self, versions_data):
        modules = get_known_modules_from_versions(versions_data)
        assert set(modules.keys()) == {
            "valkey-json", "valkey-bloom", "valkey-search", "valkey-ldap"
        }

    def test_repo_names(self, versions_data):
        modules = get_known_modules_from_versions(versions_data)
        assert modules["valkey-json"] == "valkey-io/valkey-json"


# ---------------------------------------------------------------------------
# update_unstable
# ---------------------------------------------------------------------------
class TestUpdateUnstable:
    def test_updates_module_versions(self, versions_data, mocker):
        mocker.patch.object(
            update_versions, "get_latest_module_release",
            side_effect=lambda repo: {
                "valkey-io/valkey-json": "1.1.0",
                "valkey-io/valkey-bloom": "1.1.0",
                "valkey-io/valkey-search": "1.1.0",
                "valkey-io/valkey-ldap": "1.1.0",
            }[repo],
        )
        mocker.patch.object(
            update_versions, "get_debian_version", return_value="trixie"
        )

        result = update_unstable(versions_data)
        for mod in ["valkey-json", "valkey-bloom", "valkey-search", "valkey-ldap"]:
            assert result["unstable"]["modules"][mod]["version"] == "1.1.0"

    def test_updates_debian_version(self, versions_data, mocker):
        mocker.patch.object(
            update_versions, "get_latest_module_release", return_value="1.0.0"
        )
        mocker.patch.object(
            update_versions, "get_debian_version", return_value="trixie"
        )

        result = update_unstable(versions_data)
        assert result["unstable"]["debian"]["version"] == "trixie"

    def test_does_not_touch_other_blocks(self, versions_data, mocker):
        original_81 = copy.deepcopy(versions_data["8.1"])
        mocker.patch.object(
            update_versions, "get_latest_module_release", return_value="1.0.0"
        )
        mocker.patch.object(
            update_versions, "get_debian_version", return_value="bookworm"
        )

        result = update_unstable(versions_data)
        assert result["8.1"] == original_81


# ---------------------------------------------------------------------------
# update_versions — valkey component
# ---------------------------------------------------------------------------
class TestUpdateVersionsValkey:
    def _no_open_pr(self, mocker):
        """Simulate no open PR branch (git ls-remote fails)."""
        mocker.patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "git"))

    def _open_pr_exists(self, mocker):
        """Simulate open PR branch exists."""
        mocker.patch("subprocess.check_output", return_value=b"abc123\trefs/heads/valkey-bundle-update\n")

    def test_patch_update_bumps_server_version(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._no_open_pr(mocker)

        result = update_versions_fn(versions_data, "valkey", "9.0.5")
        assert result["9.0"]["valkey-server"]["version"] == "9.0.5"

    def test_patch_update_bumps_bundle_when_no_pr(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._no_open_pr(mocker)

        result = update_versions_fn(versions_data, "valkey", "9.0.5")
        # Original bundle was 9.0.1, should become 9.0.2
        assert result["9.0"]["version"] == "9.0.2"

    def test_patch_update_no_bundle_bump_when_pr_exists(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._open_pr_exists(mocker)

        original_bundle = versions_data["9.0"]["version"]
        result = update_versions_fn(versions_data, "valkey", "9.0.5")
        assert result["9.0"]["version"] == original_bundle

    def test_rc_update_bumps_rc_number(self, versions_data_rc, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._no_open_pr(mocker)

        # Bundle is 9.0.1-rc2, new valkey is RC so should become 9.0.1-rc3
        result = update_versions_fn(versions_data_rc, "valkey", "9.0.3-rc1")
        assert result["9.0"]["version"] == "9.0.1-rc3"

    def test_stable_after_rc_drops_rc(self, versions_data_rc, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._no_open_pr(mocker)

        # Bundle is 9.0.1-rc2, new valkey is stable so bundle should drop RC
        result = update_versions_fn(versions_data_rc, "valkey", "9.0.3")
        assert result["9.0"]["version"] == "9.0.1"

    def test_new_major_minor_creates_entry(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="trixie")
        mocker.patch.object(
            update_versions, "get_latest_stable_module_release", return_value="2.0.0"
        )

        result = update_versions_fn(versions_data, "valkey", "10.0.0")
        assert "10.0" in result
        assert result["10.0"]["valkey-server"]["version"] == "10.0.0"
        assert result["10.0"]["version"] == "10.0.0"
        for mod in ["valkey-json", "valkey-bloom", "valkey-search", "valkey-ldap"]:
            assert result["10.0"]["modules"][mod]["version"] == "2.0.0"


# ---------------------------------------------------------------------------
# update_versions — module component
# ---------------------------------------------------------------------------
class TestUpdateVersionsModule:
    def _no_open_pr(self, mocker):
        mocker.patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "git"))

    def _open_pr_exists(self, mocker):
        mocker.patch("subprocess.check_output", return_value=b"abc123\trefs/heads/valkey-bundle-update\n")

    def test_module_patch_updates_matching_blocks(self, versions_data, mocker):
        self._no_open_pr(mocker)

        # valkey-json 1.0.1 exists in 8.1 and 9.0 — patch 1.0.2 should update both
        result = update_versions_fn(versions_data, "json", "1.0.2")
        assert result["8.1"]["modules"]["valkey-json"]["version"] == "1.0.2"
        assert result["9.0"]["modules"]["valkey-json"]["version"] == "1.0.2"

    def test_module_patch_does_not_update_different_major_minor(self, versions_data, mocker):
        self._no_open_pr(mocker)

        # valkey-search is 1.0.1 in both blocks. Releasing 2.0.1 should not match 1.0.x
        # First, set up a scenario: 8.1 has search 1.0.1, 9.0 has search 2.0.0
        versions_data["9.0"]["modules"]["valkey-search"]["version"] = "2.0.0"
        result = update_versions_fn(versions_data, "search", "2.0.1")
        assert result["9.0"]["modules"]["valkey-search"]["version"] == "2.0.1"
        assert result["8.1"]["modules"]["valkey-search"]["version"] == "1.0.1"  # unchanged

    def test_module_major_release_only_updates_latest(self, versions_data, mocker):
        self._no_open_pr(mocker)
        # For major module release, valkey must be X.0.0
        versions_data["9.0"]["valkey-server"]["version"] = "9.0.0"

        result = update_versions_fn(versions_data, "json", "2.0.0")
        assert result["9.0"]["modules"]["valkey-json"]["version"] == "2.0.0"
        assert result["8.1"]["modules"]["valkey-json"]["version"] == "1.0.1"  # unchanged

    def test_module_major_release_rejected_if_valkey_not_major(self, versions_data, mocker):
        # valkey is 9.0.2 (not X.0.0), so major module release should be rejected
        with pytest.raises(SystemExit):
            update_versions_fn(versions_data, "json", "2.0.0")

    def test_module_minor_release_rejected_if_valkey_minor_is_zero(self, versions_data, mocker):
        # valkey is 9.0.2 (minor=0), so module minor release should be rejected
        with pytest.raises(SystemExit):
            update_versions_fn(versions_data, "json", "1.1.0")

    def test_module_bumps_bundle_patch_when_no_pr(self, versions_data, mocker):
        self._no_open_pr(mocker)

        original_bundle = versions_data["9.0"]["version"]  # "9.0.1"
        result = update_versions_fn(versions_data, "json", "1.0.2")
        assert result["9.0"]["version"] == "9.0.2"

    def test_module_bumps_rc_when_bundle_is_rc(self, versions_data_rc, mocker):
        self._no_open_pr(mocker)

        # Bundle is 9.0.1-rc2, valkey-server is 9.0.2-rc1
        # Module minor release: valkey_minor != 0 check — valkey is 9.0.x so minor=0
        # Use a patch release instead
        result = update_versions_fn(versions_data_rc, "json", "1.0.2")
        assert result["9.0"]["version"] == "9.0.1-rc3"
