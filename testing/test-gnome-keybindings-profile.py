#!/usr/bin/env python3
"""Test profile detection and selection without installing or applying settings."""

import errno
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / "scripts/select-gnome-keybindings-profile.sh"
BASH = shutil.which("bash")


def environment(**overrides):
    env = dict(os.environ, TERM="xterm")
    env.pop("GNOME_KEYBINDINGS_PROFILE", None)
    env.update(overrides)
    return env


def run_selector(command="select_gnome_keybindings_profile", *args, **env):
    return subprocess.run(
        [BASH, "-c", 'source "$1"; ' + command, "test", str(SELECTOR), *args],
        env=environment(**env),
        input="",
        capture_output=True,
        text=True,
        start_new_session=True,  # No controlling terminal: must not prompt.
        timeout=5,
    )


class ProfileTests(unittest.TestCase):
    def detect(self, chassis=None, battery_type=None, scope=None):
        with tempfile.TemporaryDirectory() as directory:
            sysfs = Path(directory)
            files = {
                "class/dmi/id/chassis_type": chassis,
                "class/power_supply/test/type": battery_type,
                "class/power_supply/test/scope": scope,
            }
            for name, value in files.items():
                if value is not None:
                    path = sysfs / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(f"{value}\n")
            result = run_selector('detect_gnome_keybindings_profile "$2"', directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_mobile_chassis_without_battery(self):
        for chassis in (8, 9, 10, 11, 14, 30, 31, 32):
            with self.subTest(chassis=chassis):
                self.assertEqual(self.detect(chassis=chassis), "laptop")

    def test_desktop_chassis(self):
        for chassis in (3, 4, 5, 6, 7, 13, 15, 16, 23, 24, 35, 36):
            with self.subTest(chassis=chassis):
                self.assertEqual(self.detect(chassis=chassis), "desktop")

    def test_system_battery_fallback(self):
        self.assertEqual(self.detect(battery_type="Battery", scope="System"), "laptop")
        self.assertEqual(self.detect(chassis=1, battery_type="Battery"), "laptop")

    def test_peripheral_batteries_and_unknown_hardware(self):
        self.assertEqual(self.detect(battery_type="Battery", scope="Device"), "desktop")
        self.assertEqual(self.detect(battery_type="UPS"), "desktop")
        self.assertEqual(self.detect(chassis="unknown"), "desktop")
        self.assertEqual(self.detect(), "desktop")

    def test_explicit_profiles_bypass_detection(self):
        for profile in ("laptop", "desktop"):
            result = run_selector(
                "detect_gnome_keybindings_profile() { exit 99; }; select_gnome_keybindings_profile",
                GNOME_KEYBINDINGS_PROFILE=profile,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, profile + "\n")
            self.assertEqual(result.stderr, "")

    def test_invalid_override(self):
        result = run_selector(GNOME_KEYBINDINGS_PROFILE="invalid")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Supported values: laptop, desktop", result.stderr)

    def test_unattended_uses_detected_profile(self):
        for profile in ("laptop", "desktop"):
            result = run_selector(
                f"detect_gnome_keybindings_profile() {{ echo {profile}; }}; "
                "select_gnome_keybindings_profile"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, profile + "\n")
            self.assertIn("No interactive terminal", result.stderr)

    def test_apply_uses_selected_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            bins = Path(directory)
            for name in ("bash", "dirname"):
                (bins / name).symlink_to(shutil.which(name))
            gsettings = bins / "gsettings"
            gsettings.write_text('#!/bin/bash\nprintf "%s\\n" "$@"\n')
            gsettings.chmod(0o755)
            for profile, modifier, overlay in (
                ("laptop", "<Control><Alt>", "Super"),
                ("desktop", "<Alt>", "Super_L"),
            ):
                result = subprocess.run(
                    [BASH, str(ROOT / "scripts/apply-gnome-keybindings.sh")],
                    env=environment(PATH=directory, GNOME_KEYBINDINGS_PROFILE=profile),
                    capture_output=True,
                    text=True,
                    start_new_session=True,
                    timeout=5,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"['{modifier}f']", result.stdout)
                self.assertIn(f"overlay-key\n{overlay}\n", result.stdout)


class TerminalTests(unittest.TestCase):
    def prompt(self, guess, keys, expected, **env):
        # A real controlling PTY, with stdin redirected and stdout captured,
        # exercises the same conditions as the online bootstrap.
        command = (
            'source "$1"; '
            f"detect_gnome_keybindings_profile() {{ echo {guess}; }}; "
            'profile=$(select_gnome_keybindings_profile </dev/null); '
            'printf "RESULT=%s\\n" "$profile"'
        )
        pid, fd = pty.fork()
        if pid == 0:
            os.execve(BASH, [BASH, "-c", command, "test", str(SELECTOR)], environment(**env))

        output = b""
        sent = False
        reaped = False
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if not select.select([fd], [], [], 0.1)[0]:
                    continue
                try:
                    chunk = os.read(fd, 4096)
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
                    break
                if not chunk:
                    break
                output += chunk
                if not sent and b"Left Super overview" in output:
                    # Wait until the selector is reading so Ctrl+C reaches
                    # Bash's read builtin, not the preceding render step.
                    time.sleep(0.05)
                    os.write(fd, keys)
                    sent = True
            else:
                self.fail(f"Prompt timed out: {output!r}")

            _, status = os.waitpid(pid, 0)
            reaped = True
            if expected is None:
                self.assertNotEqual(status, 0, output)
                self.assertNotIn(b"RESULT=", output)
            else:
                self.assertEqual(status, 0, output)
                self.assertIn(f"RESULT={expected}".encode(), output)
            return output
        finally:
            if not reaped:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            os.close(fd)

    def test_enter_accepts_each_guess(self):
        for profile in ("laptop", "desktop"):
            with self.subTest(profile=profile):
                self.prompt(profile, b"\r", profile)

    def test_arrow_keys_change_selection(self):
        self.prompt("laptop", b"\x1b[B\r", "desktop")
        self.prompt("desktop", b"\x1b[A\r", "laptop")
        self.prompt("laptop", b"\x1bOB\r", "desktop")
        self.prompt("desktop", b"\x1bOA\r", "laptop")

    def test_escape_and_interrupt_cancel(self):
        self.prompt("laptop", b"\x1b", None)
        self.prompt("desktop", b"\x03", None)

    def test_override_bypasses_prompt_even_with_terminal(self):
        output = self.prompt("laptop", b"", "desktop", GNOME_KEYBINDINGS_PROFILE="desktop")
        self.assertNotIn(b"Hardware guess", output)

    def test_dumb_terminal_uses_guess_without_prompt(self):
        output = self.prompt("laptop", b"", "laptop", TERM="dumb")
        self.assertNotIn(b"Hardware guess", output)


if __name__ == "__main__":
    unittest.main()
