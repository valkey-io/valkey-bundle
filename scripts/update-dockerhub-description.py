#!/usr/bin/env python3

import json
import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

def clean_tag(tag: str) -> str:
    if ":" in tag:
        return tag.split(":", 1)[1]
    return tag

def format_tag_line(entry: dict) -> str:
    try:
        meta_entries = entry.get("meta", {}).get("entries", [])
        if not meta_entries:
            raise KeyError("Missing or empty 'entries' list in 'meta'.")
        
        first_entry = meta_entries[0]
        raw_tags = first_entry.get("tags", [])
        if not raw_tags:
            raise KeyError("Missing or empty 'tags' list in entry.")
        
        directory = first_entry.get("directory", None)
        if not directory:
            raise KeyError("Missing 'directory' field in entry.")

        formatted_tags = [f'`{clean_tag(tag)}`' for tag in raw_tags]
        tags = ", ".join(formatted_tags)

        return f"- [{tags}](https://github.com/valkey-io/valkey-bundle/blob/mainline/{directory}/Dockerfile)"
    
    except KeyError as e:
        logging.error(f"JSON structure error: {e}")
        raise
    
    except Exception as e:
        logging.error(f"Unexpected error in format_tag_line: {e}")
        raise

def get_versions_table() -> str:
    """Generate versions table from versions.json"""
    with open('versions.json', 'r') as f:
        data = json.load(f)

    sorted_versions = sorted(data.keys(), key=lambda x: [int(i) for i in x.split('.')], reverse=True)
    table_rows = []
    
    for version_key in sorted_versions:
        version_data = data[version_key]
        
        bundle_version = version_data['version']
        valkey_version = version_data['valkey-server']['version']
        
        modules = version_data['modules']
        json_version = modules['valkey-json']['version']
        bloom_version = modules['valkey-bloom']['version']
        search_version = modules['valkey-search']['version']
        ldap_version = modules['valkey-ldap']['version']
        
        row = f"| [{bundle_version}](https://github.com/valkey-io/valkey-bundle/releases/tag/{bundle_version}) |[{valkey_version}](https://github.com/valkey-io/valkey/releases/tag/{valkey_version}) | [{json_version}](https://github.com/valkey-io/valkey-json/releases/tag/{json_version})| [{bloom_version}](https://github.com/valkey-io/valkey-bloom/releases/tag/{bloom_version})| [{search_version}](https://github.com/valkey-io/valkey-search/releases/tag/{search_version}) | [{ldap_version}](https://github.com/valkey-io/valkey-ldap/releases/tag/{ldap_version}) |"
        
        table_rows.append(row)
    
    return "\n".join(table_rows)
    
def update_docker_description(json_file: str, template_file: str, output_file: str) -> None:
    try:
        # Read the strategy JSON file
        with open(json_file, 'r') as f:
            strategy_data = json.load(f)
            
        with open(template_file, 'r') as f:
            template = f.read()

        official_releases = []
        release_candidates = []

        for entry in strategy_data["matrix"]["include"]:
            line = format_tag_line(entry)
            if "rc" in entry["name"]:
                release_candidates.append(line)
            else:
                official_releases.append(line)

        if official_releases:
            official_releases_section = "\n## Official releases\n" + "\n".join(official_releases)
        else:
            official_releases_section = ""

        if release_candidates:
            rc_section = "\n## Release candidates\n" + "\n".join(release_candidates)
        else:
            rc_section = ""

        versions_table = get_versions_table()

        content = template.format(
            update_date=datetime.now().strftime("%Y-%m-%d"),
            official_releases=official_releases_section,
            release_candidates_section=rc_section,
            versions_table=versions_table
        )

        with open(output_file, 'w') as f:
            f.write(content)

    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        sys.exit(1)
    except json.JSONDecodeError:
        logging.error(f"Failed to parse JSON file '{json_file}'. Please check its syntax.")
        sys.exit(1)
    except KeyError as e:
        logging.error(f"Invalid JSON structure: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error processing data: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        logging.error("Invalid number of arguments.")
        logging.error("Usage: python update-dockerhub-description.py <json_file> <template_file> <output_file>")
        sys.exit(1)

    try:
        update_docker_description(sys.argv[1], sys.argv[2], sys.argv[3])
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)