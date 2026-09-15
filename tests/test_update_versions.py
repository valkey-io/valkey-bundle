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
get_mainline_bundle_version = update_versions.get_mainline_bundle_version


# ---------------------------------------------------------------------------
# get_mainline_bundle_version
# ---------------------------------------------------------------------------
class TestGetMainlineBundleVersion:
    def test_returns_version_when_block_exists(self, mocker):
        mainline_data = {"9.0": {"version": "9.0.4"}, "8.1": {"version": "8.1.8"}}
        mocker.patch("subprocess.check_output", return_value=json.dumps(mainline_data))
        assert get_mainline_bundle_version("9.0") == "9.0.4"

    def test_returns_none_when_block_missing(self, mocker):
        """A brand-new major.minor line first introduced on the branch won't exist on mainline yet."""
        mainline_data = {"9.0": {"version": "9.0.4"}, "8.1": {"version": "8.1.8"}}
        mocker.patch("subprocess.check_output", return_value=json.dumps(mainline_data))
        assert get_mainline_bundle_version("10.0") is None

    def test_raises_when_git_fails(self, mocker):
        """Git failures propagate — callers must not silently proceed when mainline is unreadable."""
        mocker.patch(
            "subprocess.check_output",
            side_effect=subprocess.CalledProcessError(128, "git", stderr=b"fatal: bad revision"),
        )
        with pytest.raises(subprocess.CalledProcessError):
            get_mainline_bundle_version("9.0")


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
    def _mainline_matches_current(self, mocker, versions_data):
        """Simulate origin/mainline having the same bundle versions as current (no prior bump)."""
        mocker.patch.object(
            update_versions,
            "get_mainline_bundle_version",
            side_effect=lambda block: versions_data.get(block, {}).get("version"),
        )

    def _mainline_bundle_lower_than_current(self, mocker, block, mainline_version):
        """Simulate a prior bump: origin/mainline has a lower bundle version than current for the block."""
        mocker.patch.object(
            update_versions,
            "get_mainline_bundle_version",
            side_effect=lambda b: mainline_version if b == block else None,
        )

    def test_patch_update_bumps_server_version(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._mainline_matches_current(mocker, versions_data)

        result = update_versions_fn(versions_data, "valkey", "9.0.5")
        assert result["9.0"]["valkey-server"]["version"] == "9.0.5"

    def test_patch_update_bumps_bundle_when_not_already_bumped(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._mainline_matches_current(mocker, versions_data)

        result = update_versions_fn(versions_data, "valkey", "9.0.5")
        # Original bundle was 9.0.1, should become 9.0.2
        assert result["9.0"]["version"] == "9.0.2"

    def test_patch_update_no_bundle_bump_when_already_ahead_of_mainline(self, versions_data, mocker):
        """When the current branch already carries a bumped bundle version (differs from
        mainline), a subsequent valkey update on the same branch should not double-bump."""
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        # Simulate mainline has 9.0.0 while current is 9.0.1 (already bumped)
        self._mainline_bundle_lower_than_current(mocker, "9.0", "9.0.0")

        original_bundle = versions_data["9.0"]["version"]
        result = update_versions_fn(versions_data, "valkey", "9.0.5")
        assert result["9.0"]["version"] == original_bundle

    def test_rc_update_bumps_rc_number(self, versions_data_rc, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._mainline_matches_current(mocker, versions_data_rc)

        # Bundle is 9.0.1-rc2, new valkey is RC so should become 9.0.1-rc3
        result = update_versions_fn(versions_data_rc, "valkey", "9.0.3-rc1")
        assert result["9.0"]["version"] == "9.0.1-rc3"

    def test_stable_after_rc_drops_rc(self, versions_data_rc, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._mainline_matches_current(mocker, versions_data_rc)

        # Bundle is 9.0.1-rc2, new valkey is stable so bundle should drop RC
        result = update_versions_fn(versions_data_rc, "valkey", "9.0.3")
        assert result["9.0"]["version"] == "9.0.1"

    def test_ga_strips_rc_when_bundle_already_rc_bumped_in_pr(self, versions_data_rc, mocker):
        """An open PR already bumped the bundle RC (differs from mainline),
        then valkey GA releases into the SAME PR."""
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        # Current bundle is 9.0.1-rc2; mainline is 9.0.1-rc1 (already bumped in this PR).
        self._mainline_bundle_lower_than_current(mocker, "9.0", "9.0.1-rc1")

        result = update_versions_fn(versions_data_rc, "valkey", "9.0.3")
        # GA event must strip the -rc suffix rather than being skipped as "already bumped".
        assert result["9.0"]["version"] == "9.0.1"
        assert result["9.0"]["valkey-server"]["version"] == "9.0.3"

    def test_rc_bump_still_skipped_when_already_bumped_in_pr(self, versions_data_rc, mocker):
        """The guard still holds for RC-into-RC: a second RC valkey event on a PR whose
        bundle RC was already bumped must not double-bump."""
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        # Current bundle 9.0.1-rc2, mainline 9.0.1-rc1 (already bumped).
        self._mainline_bundle_lower_than_current(mocker, "9.0", "9.0.1-rc1")

        result = update_versions_fn(versions_data_rc, "valkey", "9.0.3-rc1")
        # Not a GA event, so the guard skips — bundle stays at the already-bumped rc2.
        assert result["9.0"]["version"] == "9.0.1-rc2"

    def test_new_major_minor_creates_entry(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="trixie")
        mocker.patch.object(
            update_versions, "get_latest_module_release", return_value="2.0.0"
        )
        self._mainline_matches_current(mocker, versions_data)

        result = update_versions_fn(versions_data, "valkey", "10.0.0")
        assert "10.0" in result
        assert result["10.0"]["valkey-server"]["version"] == "10.0.0"
        assert result["10.0"]["version"] == "10.0.0"
        for mod in ["valkey-json", "valkey-bloom", "valkey-search", "valkey-ldap"]:
            assert result["10.0"]["modules"][mod]["version"] == "2.0.0"

    def test_new_major_minor_rc_creates_entry(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="trixie")
        mocker.patch.object(update_versions, "get_latest_module_release", return_value="2.0.0-rc1")
        self._mainline_matches_current(mocker, versions_data)

        result = update_versions_fn(versions_data, "valkey", "10.0.0-rc1")
        assert "10.0" in result
        assert result["10.0"]["valkey-server"]["version"] == "10.0.0-rc1"
        assert result["10.0"]["version"] == "10.0.0-rc1"
        for mod in ["valkey-json", "valkey-bloom", "valkey-search", "valkey-ldap"]:
            assert result["10.0"]["modules"][mod]["version"] == "2.0.0-rc1"

    def test_backported_valkey_bumps_bundle_when_not_already_bumped(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._mainline_matches_current(mocker, versions_data)
        result = update_versions_fn(versions_data, "valkey", "8.1.5")
        assert result["8.1"]["valkey-server"]["version"] == "8.1.5"
        assert result["8.1"]["version"] == "8.1.3"  # 8.1.2 -> 8.1.3

    def test_backported_valkey_no_double_bump_when_already_ahead(self, versions_data, mocker):
        """Running the same backported valkey update twice should not double-bump the bundle."""
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        # Simulate mainline has 8.1.1 while current has 8.1.2 (already bumped in a prior run)
        self._mainline_bundle_lower_than_current(mocker, "8.1", "8.1.1")

        result = update_versions_fn(versions_data, "valkey", "8.1.5")
        assert result["8.1"]["valkey-server"]["version"] == "8.1.5"
        assert result["8.1"]["version"] == "8.1.2"  # unchanged

    def test_valkey_update_bumps_bundle_when_mainline_matches_current(self, versions_data, mocker):
        """Regression for issue #121: when the current branch has the same bundle version as
        mainline (i.e. no prior bump on this branch), a valkey-server update must bump the bundle."""
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        # Mainline and current both at 9.0.1 — this is the state right after a fresh checkout
        self._mainline_bundle_lower_than_current(mocker, "9.0", "9.0.1")

        result = update_versions_fn(versions_data, "valkey", "9.0.5")
        assert result["9.0"]["valkey-server"]["version"] == "9.0.5"
        # Bundle must bump because mainline == current (no prior bump on this branch)
        assert result["9.0"]["version"] == "9.0.2"

    def test_valkey_replay_no_bump_when_version_unchanged(self, versions_data, mocker):
        """Regression: a replayed valkey event whose version already matches the block must
        not bump the bundle, even when mainline == current (post-merge replay)."""
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._mainline_matches_current(mocker, versions_data)
        original = copy.deepcopy(versions_data)
        result = update_versions_fn(versions_data, "valkey", "9.0.2")
        assert result == original

    def test_backported_valkey_replay_no_bump_when_version_unchanged(self, versions_data, mocker):
        """Regression: replayed backported valkey event with unchanged version is a no-op."""
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._mainline_matches_current(mocker, versions_data)
        original = copy.deepcopy(versions_data)
        result = update_versions_fn(versions_data, "valkey", "8.1.4")
        assert result == original

    def test_backported_valkey_does_not_touch_latest(self, versions_data, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._mainline_matches_current(mocker, versions_data)
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
        self._mainline_matches_current(mocker, versions_data_rc_latest)

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
        self._mainline_matches_current(mocker, versions_data)
        # Set valkey-server to RC so the GA path triggers, but all modules are stable
        versions_data["9.0"]["valkey-server"]["version"] = "9.0.0-rc1"
        versions_data["9.0"]["version"] = "9.0.0-rc1"

        original_modules = copy.deepcopy(versions_data["9.0"]["modules"])
        result = update_versions_fn(versions_data, "valkey", "9.0.0")
        assert result["9.0"]["modules"] == original_modules

    def test_ga_downgrade_only_on_latest_block(self, versions_data_three_blocks, mocker):
        mocker.patch.object(update_versions, "get_debian_version", return_value="bookworm")
        self._mainline_matches_current(mocker, versions_data_three_blocks)
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
    def _mainline_matches_current(self, mocker, versions_data):
        """Simulate origin/mainline having the same bundle versions as current (no prior bump)."""
        mocker.patch.object(
            update_versions,
            "get_mainline_bundle_version",
            side_effect=lambda block: versions_data.get(block, {}).get("version"),
        )

    def _mainline_bundle_lower_than_current(self, mocker, block, mainline_version):
        """Simulate a prior bump: origin/mainline has a lower bundle version than current for the block."""
        mocker.patch.object(
            update_versions,
            "get_mainline_bundle_version",
            side_effect=lambda b: mainline_version if b == block else None,
        )

    def test_module_patch_updates_matching_blocks(self, versions_data, mocker):
        self._mainline_matches_current(mocker, versions_data)

        # valkey-json 1.0.1 exists in 8.1 and 9.0 — patch 1.0.2 should update both
        result = update_versions_fn(versions_data, "json", "1.0.2")
        assert result["8.1"]["modules"]["valkey-json"]["version"] == "1.0.2"
        assert result["9.0"]["modules"]["valkey-json"]["version"] == "1.0.2"

    def test_module_patch_does_not_touch_unstable(self, versions_data, mocker):
        self._mainline_matches_current(mocker, versions_data)
        original_unstable = copy.deepcopy(versions_data["unstable"])
        update_versions_fn(versions_data, "json", "1.0.2")
        assert versions_data["unstable"] == original_unstable

    def test_module_patch_updates_three_blocks(self, versions_data_three_blocks, mocker):
        self._mainline_matches_current(mocker, versions_data_three_blocks)
        # json is 1.0.1 in 8.1, 9.0, and 9.1 — patch should update all three
        result = update_versions_fn(versions_data_three_blocks, "json", "1.0.2")
        assert result["8.1"]["modules"]["valkey-json"]["version"] == "1.0.2"
        assert result["9.0"]["modules"]["valkey-json"]["version"] == "1.0.2"
        assert result["9.1"]["modules"]["valkey-json"]["version"] == "1.0.2"

    def test_module_patch_does_not_update_different_major_minor(self, versions_data, mocker):
        self._mainline_matches_current(mocker, versions_data)

        # valkey-search is 1.0.1 in both blocks. Releasing 2.0.1 should not match 1.0.x
        # First, set up a scenario: 8.1 has search 1.0.1, 9.0 has search 2.0.0
        versions_data["9.0"]["modules"]["valkey-search"]["version"] = "2.0.0"
        result = update_versions_fn(versions_data, "search", "2.0.1")
        assert result["9.0"]["modules"]["valkey-search"]["version"] == "2.0.1"
        assert result["8.1"]["modules"]["valkey-search"]["version"] == "1.0.1"  # unchanged

    def test_module_major_release_only_updates_latest(self, versions_data, mocker):
        self._mainline_matches_current(mocker, versions_data)
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
        self._mainline_matches_current(mocker, versions_data_three_blocks)
        # 9.1 is latest, valkey-server is 9.1.0-rc1 (minor=1), so module minor release should be allowed
        result = update_versions_fn(versions_data_three_blocks, "json", "1.1.0")
        assert result["9.1"]["modules"]["valkey-json"]["version"] == "1.1.0"
        # Other blocks should be untouched
        assert result["8.1"]["modules"]["valkey-json"]["version"] == "1.0.1"
        assert result["9.0"]["modules"]["valkey-json"]["version"] == "1.0.1"

    def test_module_major_release_allowed_with_rc_valkey(self, versions_data, mocker):
        self._mainline_matches_current(mocker, versions_data)
        versions_data["9.0"]["valkey-server"]["version"] = "9.0.0-rc1"
        result = update_versions_fn(versions_data, "json", "2.0.0")
        assert result["9.0"]["modules"]["valkey-json"]["version"] == "2.0.0"

    def test_module_bumps_bundle_patch_when_no_pr(self, versions_data, mocker):
        self._mainline_matches_current(mocker, versions_data)

        original_bundle = versions_data["9.0"]["version"]  # "9.0.1"
        result = update_versions_fn(versions_data, "json", "1.0.2")
        assert result["9.0"]["version"] == "9.0.2"

    def test_module_bumps_rc_when_bundle_is_rc(self, versions_data_rc, mocker):
        self._mainline_matches_current(mocker, versions_data_rc)

        # Bundle is 9.0.1-rc2, valkey-server is 9.0.2-rc1
        # Module minor release: valkey_minor != 0 check — valkey is 9.0.x so minor=0
        # Use a patch release instead
        result = update_versions_fn(versions_data_rc, "json", "1.0.2")
        assert result["9.0"]["version"] == "9.0.1-rc3"

    def test_module_no_bundle_bump_when_already_ahead_of_mainline(self, versions_data, mocker):
        """When the current branch already carries a bumped bundle version (differs from
        mainline), a subsequent module update on the same branch should not double-bump."""
        # Simulate mainline has 9.0.0 while current is 9.0.1 (already bumped)
        self._mainline_bundle_lower_than_current(mocker, "9.0", "9.0.0")
        original_bundle = versions_data["9.0"]["version"]
        result = update_versions_fn(versions_data, "json", "1.0.2")
        assert result["9.0"]["version"] == original_bundle

    def test_module_patch_no_bump_when_no_block_matches(self, versions_data, mocker):
        """Regression: dispatching a patch release whose major.minor line isn't present in
        any block (e.g. search 1.1.1 when blocks are on 1.0.x and 1.2.x) must not bump the
        latest bundle version."""
        self._mainline_matches_current(mocker, versions_data)
        # Set up: 8.1 and 9.0 have search on 1.0.x, and no block has search on 1.1.x
        original = copy.deepcopy(versions_data)
        result = update_versions_fn(versions_data, "search", "1.1.1")
        # Nothing should have changed: no module versions, no bundle versions
        assert result == original

    def test_module_patch_dedup_non_latest_already_bumped(self, versions_data_three_blocks, mocker):
        """When a non-latest block's bundle was already bumped (differs from mainline), skip the bump."""
        # Mainline: 8.1 at 8.1.2 (same as current, will bump); 9.0 at 9.0.0 (differs from
        # current 9.0.1, already bumped, will NOT bump).
        mocker.patch.object(
            update_versions,
            "get_mainline_bundle_version",
            side_effect=lambda block: {"8.1": "8.1.2", "9.0": "9.0.0"}.get(block),
        )

        result = update_versions_fn(versions_data_three_blocks, "json", "1.0.2")
        # 8.1 should bump (mainline matches current)
        assert result["8.1"]["version"] == "8.1.3"
        # 9.0 should NOT bump (mainline differs — already bumped)
        assert result["9.0"]["version"] == "9.0.1"
