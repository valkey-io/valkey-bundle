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

def get_known_modules_from_versions(versions_data: Dict[str, Any]) -> Dict[str, str]:
    """Get all modules from the latest version block in versions.json."""
    latest = get_latest_major_minor(versions_data)
    modules = {}
    
    for module_name in versions_data[latest]["modules"].keys():
        repo_name = f"valkey-io/{module_name}"
        modules[module_name] = repo_name
    
    logging.info(f"Found modules in versions.json: {list(modules.keys())}")
    return modules

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

def update_versions(versions_data: Dict[str, Any], component_name: str, new_version: str) -> tuple[Dict[str, Any], list]:
    """Update versions.json according to Valkey and module versioning strategy."""
    changed_bundles = []
    major, minor, patch, rc = parse_version(new_version)
    new_major_minor_release = f"{major}.{minor}"
    latest = get_latest_major_minor(versions_data)

    if component_name == "bundle":
        versions_data[latest]["version"] = new_version
        changed_bundles.append(latest)
        versions_data[latest]["valkey-server"]["version"] = get_latest_stable_module_release("valkey-io/valkey")

        for module_key in versions_data[latest]["modules"].keys():
            repo = f"valkey-io/{module_key}"
            versions_data[latest]["modules"][module_key]["version"] = get_latest_stable_module_release(repo)
        return versions_data, changed_bundles

    if component_name == 'valkey':
        existing_entry = new_major_minor_release in versions_data

        if existing_entry:
            # Patch or RC update
            existing_bundle_version = versions_data[new_major_minor_release]["version"]
            versions_data[new_major_minor_release]["valkey-server"]["version"] = new_version

            try:
                subprocess.check_output(
                    ["git", "ls-remote", "--exit-code", "--heads", "origin", "valkey-bundle-update"], stderr=subprocess.DEVNULL)
                logging.info("PR exists — skipping bundle version bump.")
            except subprocess.CalledProcessError:
                bundle_major, bundle_minor, bundle_patch, bundle_rc = parse_version(existing_bundle_version)
                versions_data[new_major_minor_release]["version"] = f"{bundle_major}.{bundle_minor}.{bundle_patch + 1}"
                changed_bundles.append(new_major_minor_release)
                logging.info("No PR — bumped bundle version.")
        else:
            # New major/minor version
            known_modules = get_known_modules_from_versions(versions_data)

            module_versions = {}
            for name, repository in known_modules.items():
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
            changed_bundles.append(new_major_minor_release)

        return versions_data, changed_bundles

    else:
        # Handle module update
        module_key = f"valkey-{component_name}"

        is_module_major_release = (minor == 0 and patch == 0)

        if is_module_major_release:
            valkey_version = versions_data[latest]["valkey-server"]["version"]
            if not re.match(r'^\d+\.0\.0(?:-rc\d+)?$', valkey_version):
                logging.error(
                    f"Can't release {component_name} {new_version}: "
                    f"The latest Valkey version is '{valkey_version}', which is not a new major version release (X.0.0 or X.0.0-rcY)."
                )
                sys.exit(1)
            
        if module_key not in versions_data[latest]["modules"]:
            logging.info(f"Adding new module {module_key} to existing version block")
            versions_data[latest]["modules"][module_key] = {"version": new_version}
        else:
            versions_data[latest]["modules"][module_key]["version"] = new_version

        try:
            subprocess.check_output(
                ["git", "ls-remote", "--exit-code", "--heads", "origin", "valkey-bundle-update"], stderr=subprocess.DEVNULL)
            logging.info("Branch valkey-bundle-update exists — skipping bundle version patch bump.")
        except subprocess.CalledProcessError:
            current_version = versions_data[latest]["version"]
            bundle_major, bundle_minor, bundle_patch, bundle_rc = parse_version(current_version)
            versions_data[latest]["version"] = f"{bundle_major}.{bundle_minor}.{bundle_patch + 1}"
            changed_bundles.append(latest)
            logging.info("Branch valkey-bundle-update not found — bumping patch version.")
        
        return versions_data, changed_bundles

if __name__ == "__main__":
    if len(sys.argv) != 4:
        logging.error("Usage: update_versions.py <json_file> <component> <new_version>")
        sys.exit(1)

    json_file = sys.argv[1]
    component_name = sys.argv[2]
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

    updated_file, changed_bundles = update_versions(versions_data, component_name, new_version)

    with open(json_file, 'w') as f:
        json.dump(updated_file, f, indent=2)
        f.write('\n')
    
    # Write changed bundle versions to file for CI
    if changed_bundles:
        with open('.changed-bundles', 'a') as f:
            for bundle in changed_bundles:
                f.write(f"{bundle}\n")
        logging.info(f"Bundle Version updates written to .changed-bundles: {changed_bundles}")

    logging.info(f"Updated {component_name} to {new_version}")