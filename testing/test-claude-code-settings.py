#!/usr/bin/env python3
"""Test Claude settings in temporary homes without installing or running Claude."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = json.loads((ROOT / "config/claude/settings.json").read_text())


class ClaudeSettingsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.target = self.home / ".claude/settings.json"
        self.env = dict(os.environ, HOME=str(self.home))
        self.env.pop("CLAUDE_CONFIG_DIR", None)
        self.env.pop("SKIP_CLAUDE_CODE", None)
        self.env["XDG_CONFIG_HOME"] = str(self.home / ".config")
        self.env["GIT_CONFIG_GLOBAL"] = str(self.home / ".gitconfig")
        self.env["GIT_CONFIG_NOSYSTEM"] = "1"

    def run_script(self, script="configure-claude-code.sh", success=True, **overrides):
        result = subprocess.run(
            ["bash", str(ROOT / "scripts" / script)],
            env=dict(self.env, **overrides),
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def write_existing(self, text):
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.target.write_text(text)

    def test_fresh_settings(self):
        self.run_script()
        self.assertEqual(json.loads(self.target.read_text()), DEFAULTS)
        self.assertEqual(DEFAULTS["attribution"]["commit"], "")
        self.assertFalse(DEFAULTS["attribution"]["sessionUrl"])
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)

    def test_merge_preserves_other_settings_and_is_idempotent(self):
        existing = {
            "permissions": {"allow": ["Bash(git status)"], "deny": ["Read(.env)"]},
            "attribution": {"commit": "old trailer", "pr": "custom PR text", "sessionUrl": True},
        }
        self.write_existing(json.dumps(existing))
        self.run_script()
        existing["attribution"].update(DEFAULTS["attribution"])
        self.assertEqual(json.loads(self.target.read_text()), existing)
        contents = self.target.read_bytes()
        mtime = self.target.stat().st_mtime_ns
        self.run_script()
        self.assertEqual(self.target.read_bytes(), contents)
        self.assertEqual(self.target.stat().st_mtime_ns, mtime)
        self.assertEqual(list(self.target.parent.glob(".settings.json.*")), [])

    def test_invalid_existing_settings_are_not_overwritten(self):
        for text in ("", "{broken", "[]", "null", "true", '"text"', "{}\n{}"):
            with self.subTest(text=text):
                self.write_existing(text)
                result = self.run_script(success=False)
                self.assertIn("Invalid Claude Code settings JSON", result.stderr)
                self.assertEqual(self.target.read_text(), text)

    def test_custom_config_directory(self):
        directory = self.home / "custom claude"
        self.run_script(CLAUDE_CONFIG_DIR=str(directory))
        self.assertEqual(json.loads((directory / "settings.json").read_text()), DEFAULTS)
        self.assertFalse(self.target.exists())

    def test_apply_config_integration(self):
        self.run_script("apply-config.sh")
        self.assertEqual(json.loads(self.target.read_text()), DEFAULTS)
        self.assertFalse((self.home / ".config/claude").exists())
        self.assertTrue((self.home / ".config/fish/config.fish").is_file())

    def test_apply_config_skip_preserves_existing_settings(self):
        contents = '{"attribution": {"commit": "keep this"}}\n'
        self.write_existing(contents)
        self.run_script("apply-config.sh", SKIP_CLAUDE_CODE="1")
        self.assertEqual(self.target.read_text(), contents)
        self.assertFalse((self.home / ".config/claude").exists())


if __name__ == "__main__":
    unittest.main()
