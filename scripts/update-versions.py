#!/usr/bin/env python3

import json
import sys
import re
import logging
import subprocess
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def parse_version(version: str) -> tuple:
    """Parse version string into (major, minor, patch, rc)."""
    match = re.match(r'(\d+)\.(\d+)\.(\d+)(?:-rc(\d+))?', version)
    if not match:
        raise ValueError(f"Invalid version format: {version}. The version must be in the form of Major.Minor.Patch")
    major, minor, patch, rc = match.groups()
    return (int(major), int(minor), int(patch), int(rc) if rc else None)

def get_latest_major_minor(versions_data: Dict[str, Any]) -> str:
    """Get the latest major.minor version (bottom most block)."""
    return max(versions_data.keys(), key=lambda x: [int(i) for i in x.split('.')])

def get_latest_stable_module_release(repository: str) -> str:
    """Use GitHub CLI to fetch the latest stable release tag for each module."""
    try:
        github_cli_output = subprocess.check_output(['gh', 'release', 'list', '--repo', repository], text=True)
        for line in github_cli_output.splitlines():
            columns = line.split() # Format is: Title | Type | Tag Name | Published
            if len(columns) >= 4 and columns[1] == 'Latest':
                return columns[2]
        raise RuntimeError(f"No stable release found for {repository}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get release list for {repository}: {e}")

def update_versions(versions_data: Dict[str, Any], module: str, new_version: str) -> Dict[str, Any]:
    """Update versions.json according to Valkey and module versioning strategy."""
    major, minor, patch, rc = parse_version(new_version)
    new_major_minor_release = f"{major}.{minor}"

    if module == 'valkey':
        existing_entry = new_major_minor_release in versions_data

        if existing_entry:
            # Patch or RC update
            versions_data[new_major_minor_release]["version"] = new_version
            versions_data[new_major_minor_release]["valkey-server"]["version"] = new_version
        else:
            # New major/minor version
            module_repositories = {
                "valkey-json": "valkey-io/valkey-json",
                "valkey-bloom": "valkey-io/valkey-bloom",
                "valkey-search": "valkey-io/valkey-search"
            }

            module_versions = {}
            for name, repository in module_repositories.items():
                latest_version = get_latest_stable_module_release(repository)
                module_versions[name] = {"version": latest_version}

            new_entry = {
                "version": new_version,
                "valkey-server": {
                    "version": new_version
                },
                "modules": module_versions
            }
            
            versions_data[new_major_minor_release] = new_entry

        return versions_data

    else:
        # Handle module update
        module_key = f"valkey-{module}"
        latest = get_latest_major_minor(versions_data)

        is_module_major_release = (minor == 0 and patch == 0)

        if is_module_major_release:
            valkey_version = versions_data[latest]["valkey-server"]["version"]
            if not re.match(r'^\d+\.0\.0(?:-rc\d+)?$', valkey_version):
                logging.error(
                    f"Can't release {module} {new_version}: "
                    f"The latest Valkey version is '{valkey_version}', which is not a new major version release (X.0.0 or X.0.0-rcY)."
                )
                sys.exit(1)

        if module_key in versions_data[latest]["modules"]:
            versions_data[latest]["modules"][module_key]["version"] = new_version
        else:
            logging.error(f"Unknown module: {module_key}")
        return versions_data

if __name__ == "__main__":
    if len(sys.argv) != 4:
        logging.error("Usage: update_versions.py <json_file> <module> <new_version>")
        sys.exit(1)

    json_file = sys.argv[1]
    module = sys.argv[2]
    new_version = sys.argv[3]

    try:
        with open(json_file, 'r') as f:
            versions_data = json.load(f)
        
        parse_version(new_version)
    except FileNotFoundError as file_error:
        logging.error(f"File not found: {file_error}")
        sys.exit(1)
    except ValueError as version_error:
        logging.error(version_error)
        sys.exit(1)

    updated_file = update_versions(versions_data, module, new_version)

    with open(json_file, 'w') as f:
        json.dump(updated_file, f, indent=2)
        f.write('\n')

    logging.info(f"Updated {module} to {new_version}")