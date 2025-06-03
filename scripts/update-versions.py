#!/usr/bin/env python3

import json
import sys
import re
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def parse_version(version: str) -> tuple:
    """Parse version string into (major, minor, patch, rc) tuple."""
    match = re.match(r'(\d+)\.(\d+)\.(\d+)(?:-rc(\d+))?', version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    major, minor, patch, rc = match.groups()
    return (int(major), int(minor), int(patch), int(rc) if rc else None)

def get_major_minor(version: str) -> str:
    """Return major.minor string from version."""
    major, minor, *_ = parse_version(version)
    return f"{major}.{minor}"

def read_versions_file(filename: str = "versions.json") -> Dict[str, Any]:
    """Read and parse the versions.json file."""
    with open(filename, 'r') as f:
        return json.load(f)

def get_latest_major_minor(versions_data: Dict[str, Any]) -> str:
    """Get the latest major.minor version (bottom most block)."""
    return max(versions_data.keys(), key=lambda x: [int(i) for i in x.split('.')])

def update_versions(versions_data: Dict[str, Any], module: str, new_version: str) -> Dict[str, Any]:
    """Update versions.json according to Valkey and module versioning strategy."""
    new_major_minor = get_major_minor(new_version)

    if module == 'valkey':
        existing_entry = new_major_minor in versions_data

        if existing_entry:
            # Patch or RC update
            versions_data[new_major_minor]["version"] = new_version
            versions_data[new_major_minor]["valkey-server"]["version"] = new_version
        else:
            # New minor/major version
            current_latest = get_latest_major_minor(versions_data)
            new_entry = {
                "version": new_version,
                "valkey-server": {
                    "version": new_version
                },
                "modules": {
                    "valkey-json": versions_data[current_latest]["modules"]["valkey-json"].copy(),
                    "valkey-bloom": versions_data[current_latest]["modules"]["valkey-bloom"].copy(),
                    "valkey-search": versions_data[current_latest]["modules"]["valkey-search"].copy()
                }
            }
            versions_data[new_major_minor] = new_entry
            
        return versions_data

    else:
        # Handle module update
        module_key = f"valkey-{module}"
        latest = get_latest_major_minor(versions_data)

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
        versions_data = read_versions_file(json_file)
    except FileNotFoundError:
        logging.error(f"File not found: {json_file}")
        sys.exit(1)

    try:
        parse_version(new_version)
    except ValueError as e:
        logging.error(str(e))
        sys.exit(1)

    updated = update_versions(versions_data, module, new_version)

    with open(json_file, 'w') as f:
        json.dump(updated, f, indent=2)
        f.write('\n')

    logging.info(f"Updated {module} to {new_version}")