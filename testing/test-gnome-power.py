#!/usr/bin/env python3
"""Test GNOME power defaults using mocked hardware detection and gsettings."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
POWER_SCHEMA = "org.gnome.settings-daemon.plugins.power"
DESKTOP_SETTINGS = [
    "set org.gnome.desktop.session idle-delay 0",
    f"set {POWER_SCHEMA} idle-dim false",
    f"set {POWER_SCHEMA} sleep-inactive-ac-type nothing",
    f"set {POWER_SCHEMA} sleep-inactive-ac-timeout 0",
    f"set {POWER_SCHEMA} sleep-inactive-battery-type nothing",
    f"set {POWER_SCHEMA} sleep-inactive-battery-timeout 0",
]


class PowerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.bins = self.directory / "bin"
        self.bins.mkdir()
        (self.bins / "dirname").symlink_to(shutil.which("dirname"))
        self.log = self.directory / "gsettings.log"
        self.log.touch()
        gsettings = self.bins / "gsettings"
        gsettings.write_text(
            f'#!{BASH}\nprintf "%s\\n" "$*" >> "$TEST_SETTINGS_LOG"\n'
            'exit "${TEST_SETTINGS_STATUS:-0}"\n'
        )
        gsettings.chmod(0o755)
        for name in ("apply-gnome-power.sh", "logging.sh", "select-gnome-keybindings-profile.sh"):
            shutil.copy(ROOT / "scripts" / name, self.directory / name)
        # Detection itself is covered in test-gnome-keybindings-profile.py.
        # Force predictable hardware and make any extra selector call fail.
        with (self.directory / "select-gnome-keybindings-profile.sh").open("a") as selector:
            selector.write(
                '\ndetect_gnome_keybindings_profile() { printf "%s\\n" "$TEST_DETECTED_PROFILE"; }\n'
                'select_gnome_keybindings_profile() { exit 99; }\n'
            )
        self.env = dict(
            os.environ,
            PATH=str(self.bins),
            TEST_SETTINGS_LOG=str(self.log),
            TEST_DETECTED_PROFILE="desktop",
            TEST_SETTINGS_STATUS="0",
        )
        self.env.pop("GNOME_KEYBINDINGS_PROFILE", None)

    def run_script(self, success=True, **overrides):
        self.log.write_text("")
        result = subprocess.run(
            [BASH, str(self.directory / "apply-gnome-power.sh")],
            env=dict(self.env, **overrides),
            input="",
            capture_output=True,
            text=True,
            start_new_session=True,
            timeout=5,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_desktop_override_and_repeat(self):
        for _ in range(2):
            self.run_script(GNOME_KEYBINDINGS_PROFILE="desktop", TEST_DETECTED_PROFILE="laptop")
            self.assertEqual(self.log.read_text().splitlines(), DESKTOP_SETTINGS)

    def test_laptop_override_leaves_settings_unchanged(self):
        self.run_script(GNOME_KEYBINDINGS_PROFILE="laptop")
        self.assertEqual(self.log.read_text(), "")

    def test_detected_profiles_without_prompt(self):
        for profile, expected in (("desktop", DESKTOP_SETTINGS), ("laptop", [])):
            with self.subTest(profile=profile):
                self.run_script(TEST_DETECTED_PROFILE=profile)
                self.assertEqual(self.log.read_text().splitlines(), expected)

    def test_invalid_override_does_not_change_settings(self):
        result = self.run_script(success=False, GNOME_KEYBINDINGS_PROFILE="invalid")
        self.assertIn("Supported values: laptop, desktop", result.stderr)
        self.assertEqual(self.log.read_text(), "")

    def test_missing_gsettings_skips(self):
        (self.bins / "gsettings").unlink()
        result = self.run_script()
        self.assertIn("gsettings not available; skipping", result.stdout)
        self.assertEqual(self.log.read_text(), "")

    def test_gsettings_failure_stops_script(self):
        result = self.run_script(success=False, TEST_SETTINGS_STATUS="1")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.log.read_text().splitlines(), DESKTOP_SETTINGS[:1])


if __name__ == "__main__":
    unittest.main()
