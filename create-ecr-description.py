import sys
import json
import re
import os

# Read entire markdown file
with open(sys.argv[1], "r") as f:
    md = f.read()

# Normalize underlined headings
md = re.sub(
    r'(?m)^[ \t]*(.+?)\s*\r?\n[ \t]*-{3,}[ \t]*\r?\n',
    r'## \1\n\n',
    md
)

# Split by top-level headings (# ...)
sections = re.split(r"(?m)^# ", md)

parsed = {}

for sec in sections[1:]:
    # Extract title (text until newline)
    title, _, content = sec.partition("\n")
    title = title.strip()

    # if "## Latest unstable" in content:
    #     sub_parts = content.split("## Latest unstable", 1)
    #     main_content = sub_parts[0].strip()
    #     unstable_content = sub_parts[1].strip()
    #     parsed[title] = main_content
    #     parsed["Latest unstable"] = unstable_content
    #     continue

    parsed[title] = content.strip()

# Sections we want in usage
usage_sections = [
    "How to use this image",
    "Image Variants"
]

usage_text = ""
about_text = ""

# Add sections to appropriate text blocks
for title, content in parsed.items():
    # heading_prefix = "##" if title == "Latest unstable" else "#"
    heading_prefix = "#"

    if title in usage_sections:
        usage_text += f"{heading_prefix} {title}\n{content}\n\n"
    else:
        about_text += f"{heading_prefix} {title}\n{content}\n\n"

# Write to GitHub Actions environment file
with open(os.environ['GITHUB_ENV'], 'a') as f:
    f.write(f"ABOUT_JSON={json.dumps(about_text.strip())}\n")
    f.write(f"USAGE_JSON={json.dumps(usage_text.strip())}\n")