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
            update_versions, "get_latest_module_release", return_value="2.0.0"
        )

        result = update_versions_fn(versions_data, "valkey", "10.0.0")
        assert "10.0" in result
        assert result["10.0"]["valkey-server"]["version"] == "10.0.0"
        assert result["10.0"]["version"] == "10.0.0"
        for mod in ["valkey-json", "valkey-bloom", "valkey-search", "valkey-ldap"]:
            assert result["10.0"]["modules"][mod]["version"] == "2.0.0"

    def test_new_major_minor_rc_creates_entry(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="trixie")
        mocker.patch.object(update_versions, "get_latest_module_release", return_value="2.0.0-rc1")

        result = update_versions_fn(versions_data, "valkey", "10.0.0-rc1")
        assert "10.0" in result
        assert result["10.0"]["valkey-server"]["version"] == "10.0.0-rc1"
        assert result["10.0"]["version"] == "10.0.0-rc1"
        for mod in ["valkey-json", "valkey-bloom", "valkey-search", "valkey-ldap"]:
            assert result["10.0"]["modules"][mod]["version"] == "2.0.0-rc1"

    def test_backported_valkey_always_bumps_bundle(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        result = update_versions_fn(versions_data, "valkey", "8.1.5")
        assert result["8.1"]["valkey-server"]["version"] == "8.1.5"
        assert result["8.1"]["version"] == "8.1.3"  # 8.1.2 -> 8.1.3

    def test_backported_valkey_does_not_touch_latest(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        original_latest = copy.deepcopy(versions_data["9.0"])
        update_versions_fn(versions_data, "valkey", "8.1.5")
        assert versions_data["9.0"] == original_latest

    def test_ga_downgrades_rc_modules_to_stable(self, versions_data_rc_latest, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        mocker.patch.object(
            update_versions, "get_latest_module_release",
            side_effect=lambda repo, include_rc=True: {
                "valkey-io/valkey-json": "1.0.1",
                "valkey-io/valkey-bloom": "1.0.0",
                "valkey-io/valkey-search": "1.0.1",
                "valkey-io/valkey-ldap": "1.0.0",
            }[repo],
        )
        # Simulate no open PR
        mocker.patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "git"))

        # 9.0 has valkey-server 9.0.0-rc1, search 1.1.0-rc1, ldap 1.1.0-rc1
        result = update_versions_fn(versions_data_rc_latest, "valkey", "9.0.0")
        assert result["9.0"]["valkey-server"]["version"] == "9.0.0"
        # RC modules should be downgraded to latest stable
        assert result["9.0"]["modules"]["valkey-search"]["version"] == "1.0.1"
        assert result["9.0"]["modules"]["valkey-ldap"]["version"] == "1.0.0"
        # Already-stable modules should be untouched
        assert result["9.0"]["modules"]["valkey-json"]["version"] == "1.0.1"
        assert result["9.0"]["modules"]["valkey-bloom"]["version"] == "1.0.0"

    def test_ga_does_not_downgrade_when_no_rc_modules(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        mocker.patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "git"))
        # Set valkey-server to RC so the GA path triggers, but all modules are stable
        versions_data["9.0"]["valkey-server"]["version"] = "9.0.0-rc1"
        versions_data["9.0"]["version"] = "9.0.0-rc1"

        original_modules = copy.deepcopy(versions_data["9.0"]["modules"])
        result = update_versions_fn(versions_data, "valkey", "9.0.0")
        assert result["9.0"]["modules"] == original_modules

    def test_ga_downgrade_only_on_latest_block(self, versions_data_three_blocks, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        # 9.1 is latest, 8.1 has valkey-server set to RC for this test
        versions_data_three_blocks["8.1"]["valkey-server"]["version"] = "8.1.0-rc1"
        versions_data_three_blocks["8.1"]["modules"]["valkey-search"]["version"] = "1.1.0-rc1"

        result = update_versions_fn(versions_data_three_blocks, "valkey", "8.1.0")
        # 8.1 is not latest, so GA downgrade should NOT run — RC module stays
        assert result["8.1"]["modules"]["valkey-search"]["version"] == "1.1.0-rc1"


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

    def test_module_patch_does_not_touch_unstable(self, versions_data, mocker):
        self._no_open_pr(mocker)
        original_unstable = copy.deepcopy(versions_data["unstable"])
        update_versions_fn(versions_data, "json", "1.0.2")
        assert versions_data["unstable"] == original_unstable

    def test_module_patch_updates_three_blocks(self, versions_data_three_blocks, mocker):
        self._no_open_pr(mocker)
        # json is 1.0.1 in 8.1, 9.0, and 9.1 — patch should update all three
        result = update_versions_fn(versions_data_three_blocks, "json", "1.0.2")
        assert result["8.1"]["modules"]["valkey-json"]["version"] == "1.0.2"
        assert result["9.0"]["modules"]["valkey-json"]["version"] == "1.0.2"
        assert result["9.1"]["modules"]["valkey-json"]["version"] == "1.0.2"

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

    def test_module_minor_release_allowed_when_valkey_minor_gt_zero(self, versions_data_three_blocks, mocker):
        self._no_open_pr(mocker)
        # 9.1 is latest, valkey-server is 9.1.0-rc1 (minor=1), so module minor release should be allowed
        result = update_versions_fn(versions_data_three_blocks, "json", "1.1.0")
        assert result["9.1"]["modules"]["valkey-json"]["version"] == "1.1.0"
        # Other blocks should be untouched
        assert result["8.1"]["modules"]["valkey-json"]["version"] == "1.0.1"
        assert result["9.0"]["modules"]["valkey-json"]["version"] == "1.0.1"

    def test_module_major_release_allowed_with_rc_valkey(self, versions_data, mocker):
        self._no_open_pr(mocker)
        versions_data["9.0"]["valkey-server"]["version"] = "9.0.0-rc1"
        result = update_versions_fn(versions_data, "json", "2.0.0")
        assert result["9.0"]["modules"]["valkey-json"]["version"] == "2.0.0"

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

    def test_module_no_bundle_bump_when_pr_exists(self, versions_data, mocker):
        def mock_check_output(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', [])
            if cmd[0] == 'git' and 'ls-remote' in cmd:
                return b"abc123\trefs/heads/valkey-bundle-update\n"
            if cmd[0] == 'git' and 'show' in cmd:
                return json.dumps(versions_data)
            raise subprocess.CalledProcessError(1, "unknown")

        mocker.patch("subprocess.check_output", side_effect=mock_check_output)
        original_bundle = versions_data["9.0"]["version"]
        result = update_versions_fn(versions_data, "json", "1.0.2")
        assert result["9.0"]["version"] == original_bundle

    def test_module_patch_dedup_non_latest_already_bumped(self, versions_data_three_blocks, mocker):
        """When a non-latest block's bundle was already bumped (differs from mainline), skip the bump."""
        def mock_check_output(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', [])
            if cmd[0] == 'git' and 'ls-remote' in cmd:
                raise subprocess.CalledProcessError(1, "git")
            if cmd[0] == 'git' and 'show' in cmd:
                # Simulate mainline has 8.1 bundle at 8.1.2 (same as current)
                # but 9.0 bundle at 9.0.0 (different from current 9.0.1 — already bumped)
                import json
                mainline = copy.deepcopy(versions_data_three_blocks)
                mainline["9.0"]["version"] = "9.0.0"
                return json.dumps(mainline)
            raise subprocess.CalledProcessError(1, "unknown")

        mocker.patch("subprocess.check_output", side_effect=mock_check_output)

        result = update_versions_fn(versions_data_three_blocks, "json", "1.0.2")
        # 8.1 should bump (mainline matches current)
        assert result["8.1"]["version"] == "8.1.3"
        # 9.0 should NOT bump (mainline differs — already bumped)
        assert result["9.0"]["version"] == "9.0.1"
