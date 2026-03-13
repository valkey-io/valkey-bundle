import json
import os
import subprocess
import sys
import pytest


SCRIPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'create-ecr-description.py')


class TestCreateEcrDescription:
    SAMPLE_MD = """\
# Quick reference

Some quick reference content here.

# How to use this image

Usage instructions go here.

## Subheading

More usage details.

# Image Variants

Variant info here.

# License

License text.
"""

    SAMPLE_MD_UNDERLINE = """\
# Quick reference

Some content.

Underlined heading
-------------------

Underlined content here.

# How to use this image

Usage text.
"""

    def _run_script(self, tmp_path, md_content):
        md_file = tmp_path / "input.md"
        md_file.write_text(md_content)

        env_file = tmp_path / "github_env"
        env_file.write_text("")

        env = os.environ.copy()
        env["GITHUB_ENV"] = str(env_file)

        subprocess.check_call(
            [sys.executable, SCRIPT_PATH, str(md_file)],
            env=env,
        )
        return env_file.read_text()

    def test_usage_sections_extracted(self, tmp_path):
        output = self._run_script(tmp_path, self.SAMPLE_MD)
        # Parse the USAGE_JSON line
        for line in output.strip().split("\n"):
            if line.startswith("USAGE_JSON="):
                usage = json.loads(line.split("=", 1)[1])
                assert "How to use this image" in usage
                assert "Image Variants" in usage
                break
        else:
            pytest.fail("USAGE_JSON not found in output")

    def test_about_sections_extracted(self, tmp_path):
        output = self._run_script(tmp_path, self.SAMPLE_MD)
        for line in output.strip().split("\n"):
            if line.startswith("ABOUT_JSON="):
                about = json.loads(line.split("=", 1)[1])
                assert "Quick reference" in about
                assert "License" in about
                # Usage sections should NOT be in about
                assert "How to use this image" not in about
                assert "Image Variants" not in about
                break
        else:
            pytest.fail("ABOUT_JSON not found in output")

    def test_underlined_headings_normalized(self, tmp_path):
        output = self._run_script(tmp_path, self.SAMPLE_MD_UNDERLINE)
        for line in output.strip().split("\n"):
            if line.startswith("ABOUT_JSON="):
                about = json.loads(line.split("=", 1)[1])
                # The underlined heading should have been converted
                assert "Underlined heading" in about
                break

    def test_empty_markdown(self, tmp_path):
        output = self._run_script(tmp_path, "Just some text without headings.\n")
        for line in output.strip().split("\n"):
            if line.startswith("ABOUT_JSON="):
                about = json.loads(line.split("=", 1)[1])
                assert about == ""
                break
        for line in output.strip().split("\n"):
            if line.startswith("USAGE_JSON="):
                usage = json.loads(line.split("=", 1)[1])
                assert usage == ""
                break
