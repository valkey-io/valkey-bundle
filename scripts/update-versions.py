#!/usr/bin/env python3

import json
import sys
import re
import logging
import subprocess
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(message)s")

def parse_version(version: str) -> tuple:
    """Parse version string into (major, minor, patch, rc)."""
    match = re.match(r'(\d+)\.(\d+)\.(\d+)(?:-rc(\d+))?', version)
    if not match:
        raise ValueError(f"Invalid version format: {version}. The version must be in the form of Major.Minor.Patch")
    major, minor, patch, rc = match.groups()
    return (int(major), int(minor), int(patch), int(rc) if rc else None)

def get_latest_major_minor(versions_data: Dict[str, Any]) -> str:
    """Get the latest major.minor version (bottom most block), skipping non-numeric keys like 'unstable'."""
    numeric_keys = [k for k in versions_data.keys() if re.match(r'^\d+\.\d+$', k)]
    return max(numeric_keys, key=lambda x: [int(i) for i in x.split('.')])

def get_known_modules_from_versions(versions_data: Dict[str, Any]) -> Dict[str, str]:
    """Get all modules from the latest version block in versions.json."""
    latest = get_latest_major_minor(versions_data)
    modules = {}
    
    for module_name in versions_data[latest]["modules"].keys():
        repo_name = f"valkey-io/{module_name}"
        modules[module_name] = repo_name
    
    logging.info(f"Found modules in versions.json: {list(modules.keys())}")
    return modules

def get_debian_version(valkey_version: str) -> str:
    """Get debian version from the container repo's versions.json."""
    if valkey_version == 'unstable':
        version_key = 'unstable'
        api_url = 'repos/valkey-io/valkey-container/contents/versions.json'
    else:
        major, minor, _, _ = parse_version(valkey_version)
        version_key = f"{major}.{minor}"
        pr_branch = f"update-{valkey_version}"
        api_url = f'repos/valkey-io/valkey-container/contents/versions.json?ref={pr_branch}'
    
    try:
        result = subprocess.check_output(['gh', 'api', api_url, '-H', 'Accept: application/vnd.github.raw'], text=True, stderr=subprocess.DEVNULL)
        container_versions = json.loads(result)
    except subprocess.CalledProcessError:
        with open('../valkey-container/versions.json', 'r') as f:
            container_versions = json.load(f)
    
    return container_versions[version_key]["debian"]["version"]

def get_latest_stable_module_release(repository: str) -> str:
    """Use GitHub CLI to fetch the latest stable release tag for each module."""
    try:
        result = subprocess.check_output(
            ['gh', 'release', 'list', '--repo', repository, '--limit', '50',
             '--json', 'tagName,isPrerelease', '-q',
             '[.[] | select(.isPrerelease == false) | select(.tagName | test("-rc") | not)] | .[].tagName'],
            text=True)
        tags = [t.lstrip('v') for t in result.strip().splitlines() if t.strip()]
        tags.sort(key=lambda v: [int(x) for x in v.split('.')])
        return tags[-1]
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get release list for {repository}: {e}")

def update_unstable(versions_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update the unstable block with latest stable module releases."""
    known_modules = get_known_modules_from_versions(versions_data)

    module_versions = {}
    for name, repository in known_modules.items():
        version = get_latest_stable_module_release(repository)
        module_versions[name] = {"version": version}

    versions_data["unstable"]["modules"] = module_versions
    versions_data["unstable"]["debian"]["version"] = get_debian_version('unstable')
    return versions_data

def update_versions(versions_data: Dict[str, Any], component_name: str, new_version: str) -> Dict[str, Any]:
    """Update versions.json according to Valkey and module versioning strategy."""
    major, minor, patch, rc = parse_version(new_version)
    new_major_minor_release = f"{major}.{minor}"
    latest = get_latest_major_minor(versions_data)

    if component_name == 'valkey':
        existing_entry = new_major_minor_release in versions_data

        if existing_entry:
            # Patch or RC update
            existing_bundle_version = versions_data[new_major_minor_release]["version"]
            versions_data[new_major_minor_release]["valkey-server"]["version"] = new_version
            versions_data[new_major_minor_release]["debian"]["version"] = get_debian_version(new_version)

            try:
                subprocess.check_output(
                    ["git", "ls-remote", "--exit-code", "--heads", "origin", "valkey-bundle-update"], stderr=subprocess.DEVNULL)
                logging.info("There is an open PR for the branch valkey-bundle-update - bundle patch version won't be bumped.")
            except subprocess.CalledProcessError:
                bundle_major, bundle_minor, bundle_patch, bundle_rc = parse_version(existing_bundle_version)
                
                if rc is not None or bundle_rc is not None:
                    if rc is not None:
                        versions_data[new_major_minor_release]["version"] = f"{bundle_major}.{bundle_minor}.{bundle_patch}-rc{bundle_rc + 1}"
                    else:
                        versions_data[new_major_minor_release]["version"] = f"{bundle_major}.{bundle_minor}.{bundle_patch}"
                else:
                    versions_data[new_major_minor_release]["version"] = f"{bundle_major}.{bundle_minor}.{bundle_patch + 1}"
                    logging.info("There is no open PR for the branch valkey-bundle-update — bumping bundle patch version.")
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
                "modules": module_versions,
                "debian": {
                    "version": get_debian_version(new_version)
                }
            }
            
            versions_data[new_major_minor_release] = new_entry

        return versions_data

    else:
        # Handle module update
        module_key = f"valkey-{component_name}"

        is_module_major_release = (minor == 0 and patch == 0)

        valkey_version = versions_data[latest]["valkey-server"]["version"]
        valkey_major, valkey_minor, valkey_patch, valkey_rc = parse_version(valkey_version)
        
        if is_module_major_release:
            if not re.match(r'^\d+\.0\.0(?:-rc\d+)?$', valkey_version):
                logging.error(
                    f"Can't release {component_name} {new_version}: "
                    f"The latest Valkey version is '{valkey_version}', which is not a new major version release (X.0.0 or X.0.0-rcY)."
                )
                sys.exit(0)
        
        # Skip the automation process if we release a minor version for a module
        is_module_minor_release = (minor > 0 and patch == 0)
        if is_module_minor_release and valkey_minor == 0:
            logging.error(
                f"Can't release {component_name} {new_version}: "
                f"The latest Valkey version is '{valkey_version}', which is not a minor version release."
            )
            sys.exit(0)
        
        if patch > 0:
            # For patch releases we will update all version entries with the same major.minor version as the module patch we just released
            for version_block in versions_data.keys():
                if not re.match(r'^\d+\.\d+$', version_block):
                    continue
                current_module_version = versions_data[version_block]["modules"][module_key]["version"]
                current_major, current_minor, _, _ = parse_version(current_module_version)
                current_major_minor = f"{current_major}.{current_minor}"
                
                if current_major_minor == new_major_minor_release:
                    versions_data[version_block]["modules"][module_key]["version"] = new_version
                    logging.info(f"Patch release: Updated {module_key} to {new_version} in Bundle version {version_block}")
        else:
            # For major or minor releases we will only update latest version entry
            versions_data[latest]["modules"][module_key] = {"version": new_version}

        try:
            subprocess.check_output(
                ["git", "ls-remote", "--exit-code", "--heads", "origin", "valkey-bundle-update"], stderr=subprocess.DEVNULL)
            logging.info("There is an open PR for the branch valkey-bundle-update - bundle patch version won't be bumped.")
        except subprocess.CalledProcessError:
            current_version = versions_data[latest]["version"]
            bundle_major, bundle_minor, bundle_patch, bundle_rc = parse_version(current_version)
            
            if bundle_rc is not None:
                # For RC versions, increment RC number
                versions_data[latest]["version"] = f"{bundle_major}.{bundle_minor}.{bundle_patch}-rc{bundle_rc + 1}"
            else:
                # For stable versions, increment patch
                versions_data[latest]["version"] = f"{bundle_major}.{bundle_minor}.{bundle_patch + 1}"
                logging.info("There is no open PR for the branch valkey-bundle-update — bumping bundle patch version.")
        
        return versions_data

if __name__ == "__main__":
    if len(sys.argv) < 3 or (sys.argv[2] != 'unstable' and len(sys.argv) != 4):
        logging.error("Incorrect parameters. Usage: update_versions.py <json_file> <component [valkey, json, bloom, etc | unstable]> [new_version]")
        sys.exit(1)

    json_file = sys.argv[1]
    component_name = sys.argv[2]

    try:
        with open(json_file, 'r') as f:
            versions_data = json.load(f)
    except FileNotFoundError as file_error:
        logging.error(f"File not found: {file_error}")
        sys.exit(1)

    if component_name == 'unstable':
        updated_file = update_unstable(versions_data)
    else:
        new_version = sys.argv[3]
        try:
            parse_version(new_version)
        except ValueError as version_error:
            logging.error(version_error)
            sys.exit(1)
        updated_file = update_versions(versions_data, component_name, new_version)

    with open(json_file, 'w') as f:
        json.dump(updated_file, f, indent=2)
        f.write('\n')

    if component_name == 'unstable':
        logging.info("Updated unstable block")
    elif component_name == 'valkey':
        logging.info(f"Updated {component_name} to {new_version}")
    else:
        logging.info(f"Updated valkey-{component_name} to {new_version}")