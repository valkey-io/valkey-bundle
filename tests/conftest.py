import copy
import json
import pytest


def make_versions_data():
    """Return a minimal versions.json structure for testing."""
    return {
        "unstable": {
            "version": "unstable",
            "valkey-server": {"version": "unstable"},
            "modules": {
                "valkey-json": {"version": "1.0.0"},
                "valkey-bloom": {"version": "1.0.0"},
                "valkey-search": {"version": "1.0.0"},
                "valkey-ldap": {"version": "1.0.0"},
            },
            "debian": {"version": "bookworm"},
        },
        "8.1": {
            "version": "8.1.2",
            "valkey-server": {"version": "8.1.4"},
            "modules": {
                "valkey-json": {"version": "1.0.1"},
                "valkey-bloom": {"version": "1.0.0"},
                "valkey-search": {"version": "1.0.1"},
                "valkey-ldap": {"version": "1.0.0"},
            },
            "debian": {"version": "bookworm"},
        },
        "9.0": {
            "version": "9.0.1",
            "valkey-server": {"version": "9.0.2"},
            "modules": {
                "valkey-json": {"version": "1.0.1"},
                "valkey-bloom": {"version": "1.0.0"},
                "valkey-search": {"version": "1.0.1"},
                "valkey-ldap": {"version": "1.0.0"},
            },
            "debian": {"version": "bookworm"},
        },
    }


@pytest.fixture
def versions_data():
    return make_versions_data()


@pytest.fixture
def versions_data_rc():
    """Versions data where the latest block has an RC bundle version."""
    data = make_versions_data()
    data["9.0"]["version"] = "9.0.1-rc2"
    data["9.0"]["valkey-server"]["version"] = "9.0.2-rc1"
    return data
