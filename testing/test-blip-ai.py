#!/usr/bin/env python3
"""Test Blip AI installation with isolated homes and mocked network/package commands."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
DOWNLOAD_URL = (
    "https://github.com/abnsl0014/blipai-releases/releases/download/"
    "v0.5.9/Blip-AI-0.5.9.AppImage"
)


@unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
class BlipAITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.bins = self.directory / "bin"
        self.bins.mkdir()
        for name in (
            "bash", "dirname", "mktemp", "rm", "cp", "cat", "install", "jq", "sha256sum"
        ):
            executable = shutil.which(name)
            self.assertIsNotNone(executable, f"Test dependency missing: {name}")
            (self.bins / name).symlink_to(executable)
        for name in (
            "install-blip-ai.sh", "configure-blip-ai.sh", "install-upstream-tools.sh",
            "install-all.sh", "logging.sh",
        ):
            path = self.directory / name
            shutil.copyfile(ROOT / "scripts" / name, path)
            path.chmod(0o755)
        self.home = self.directory / "home with spaces"
        self.home.mkdir()
        self.tmp = self.directory / "temporary downloads"
        self.tmp.mkdir()
        self.log = self.directory / "commands.log"
        self.log.touch()
        self.fixtures = self.directory / "fixtures"
        self.fixtures.mkdir()
        # If the installer accidentally launches the AppImage, fail loudly.
        self.payload = b'#!/bin/sh\necho "APPIMAGE EXECUTED" >> "$TEST_LOG"\nexit 99\n'
        (self.fixtures / "appimage").write_bytes(self.payload)
        self.release = {
            "assets": [
                {"name": "Blip-AI-0.5.9-arm64-mac.zip"},
                {"name": "Blip-AI-0.5.9-x64.exe"},
                {
                    "name": "Blip-AI-0.5.9.AppImage",
                    "browser_download_url": DOWNLOAD_URL,
                    "digest": "sha256:" + hashlib.sha256(self.payload).hexdigest(),
                },
            ]
        }
        self.save_release()
        self.env = dict(
            os.environ,
            PATH=str(self.bins),
            HOME=str(self.home),
            TMPDIR=str(self.tmp),
            TEST_LOG=str(self.log),
            TEST_FIXTURES=str(self.fixtures),
        )
        for key in (
            "SKIP_BLIP_AI", "SKIP_CLAUDE_CODE", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
            "TEST_ARCH",
            "TEST_MISSING_PACKAGES", "TEST_PACKAGE_FAILURE", "TEST_CURL_FAILURE",
        ):
            self.env.pop(key, None)
        self.mock("uname", '[[ "$*" == -m ]]\nprintf "%s\\n" "${TEST_ARCH:-x86_64}"\n')
        self.mock(
            "pacman",
            """
[[ "$1" == -Q ]] || exit 99
case " ${TEST_MISSING_PACKAGES:-} " in
  *" $2 "*) exit 1 ;;
  *) exit 0 ;;
esac
""",
        )
        self.mock(
            "sudo",
            '[[ "$*" == "pacman -S --noconfirm --needed "* ]]\n'
            'exit "${TEST_PACKAGE_FAILURE:-0}"\n',
        )
        self.mock(
            "curl",
            f"""
[[ "$1" == -fsSL && "$3" == -o && "$#" == 4 ]] || exit 98
case "$2" in
  https://api.github.com/repos/abnsl0014/blipai-releases/releases/latest) resource=release ;;
  {DOWNLOAD_URL}) resource=appimage ;;
  *) exit 99 ;;
esac
cp "$TEST_FIXTURES/$resource" "$4"
# Simulate failed downloads that leave a partial file behind.
[[ "$resource" != "${{TEST_CURL_FAILURE:-}}" ]] || exit 22
""",
        )

    @property
    def appimage(self):
        return self.home / ".local/bin/BlipAI.AppImage"

    @property
    def desktop(self):
        return self.home / ".local/share/applications/blip-ai.desktop"

    @property
    def autostart(self):
        return self.home / ".config/autostart/blip-ai.desktop"

    def save_release(self):
        (self.fixtures / "release").write_text(json.dumps(self.release))

    def mock(self, name, body):
        path = self.bins / name
        path.write_text(
            f"#!{BASH}\nset -euo pipefail\n"
            f'printf \'%s\\n\' "{name} $*" >> "$TEST_LOG"\n' + body
        )
        path.chmod(0o755)

    def run_script(self, name="install-blip-ai.sh", *, success=True, **overrides):
        self.log.write_text("")
        result = subprocess.run(
            [BASH, str(self.directory / name)],
            env=dict(self.env, **overrides),
            input="",
            capture_output=True,
            text=True,
            start_new_session=True,
            timeout=10,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.tmp.iterdir()), [], "Temporary files not removed")
        self.assertNotIn("APPIMAGE EXECUTED", self.commands())
        return result

    def commands(self):
        return self.log.read_text().splitlines()

    def assert_no_downloads(self):
        self.assertFalse(any(line.startswith("curl ") for line in self.commands()))

    def test_skip_does_not_query_packages_download_or_configure(self):
        self.run_script(SKIP_BLIP_AI="1")
        self.assertEqual(self.commands(), [])
        self.assertFalse((self.home / ".local").exists())
        self.assertFalse((self.home / ".config").exists())

    def test_unsupported_architecture_is_skipped(self):
        self.run_script(TEST_ARCH="aarch64")
        self.assertEqual(self.commands(), ["uname -m"])
        self.assertFalse((self.home / ".local").exists())

    def test_installs_verified_appimage_and_quoted_gnome_launcher_without_running_it(self):
        self.run_script()
        self.assertEqual(self.appimage.read_bytes(), self.payload)
        self.assertTrue(os.access(self.appimage, os.X_OK))
        desktop = self.desktop.read_text()
        self.assertIn("Name=Blip AI\n", desktop)
        self.assertIn(f'Exec="{self.appimage}"\n', desktop)
        self.assertIn("Terminal=false\n", desktop)
        autostart = self.autostart.read_text()
        self.assertTrue(autostart.startswith(desktop))
        self.assertIn("X-GNOME-Autostart-enabled=true\n", autostart)
        self.assertIn("OnlyShowIn=GNOME;\n", autostart)
        self.assertNotIn("OnlyShowIn=", desktop)
        validator = shutil.which("desktop-file-validate")
        if validator:
            for path in (self.desktop, self.autostart):
                result = subprocess.run(
                    [validator, str(path)], capture_output=True, text=True, timeout=10
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sum(line.startswith("curl ") for line in self.commands()), 2)
        self.assertFalse(any(line.startswith("sudo ") for line in self.commands()))

    def test_rerun_preserves_appimage_and_repairs_launchers_without_downloading(self):
        self.appimage.parent.mkdir(parents=True)
        self.appimage.write_text("existing executable AppImage\n")
        self.appimage.chmod(0o755)
        self.run_script()
        self.assertEqual(self.appimage.read_text(), "existing executable AppImage\n")
        self.assertTrue(self.desktop.exists())
        autostart = self.autostart.read_text()
        self.assert_no_downloads()
        self.desktop.unlink()
        self.autostart.unlink()
        self.run_script()
        self.assertTrue(self.desktop.exists())
        self.assertEqual(self.autostart.read_text(), autostart)
        self.assert_no_downloads()
        self.run_script()
        self.assertEqual(self.autostart.read_text(), autostart)
        self.assert_no_downloads()

    def test_configure_existing_app_without_packages_downloads_or_launching(self):
        self.appimage.parent.mkdir(parents=True)
        self.appimage.write_bytes(self.payload)
        self.appimage.chmod(0o755)
        self.run_script("configure-blip-ai.sh")
        self.assertTrue(self.desktop.exists())
        self.assertTrue(self.autostart.exists())
        self.assertEqual(self.commands(), [])
        self.assertEqual(self.appimage.read_bytes(), self.payload)

    def test_configure_without_installed_app_creates_no_launchers(self):
        self.run_script("configure-blip-ai.sh")
        self.assertFalse((self.home / ".local").exists())
        self.assertFalse((self.home / ".config").exists())
        self.assertEqual(self.commands(), [])

    def test_skip_leaves_existing_autostart_unchanged(self):
        self.run_script()
        disabled = self.autostart.read_text() + "Hidden=true\n"
        self.autostart.write_text(disabled)
        for script in ("install-blip-ai.sh", "configure-blip-ai.sh"):
            with self.subTest(script=script):
                self.run_script(script, SKIP_BLIP_AI="1")
                self.assertEqual(self.autostart.read_text(), disabled)
                self.assertEqual(self.commands(), [])

    def test_installs_only_missing_arch_dependencies_noninteractively(self):
        self.run_script(TEST_MISSING_PACKAGES="fuse2 wtype ydotool")
        self.assertIn(
            "sudo pacman -S --noconfirm --needed fuse2 wtype ydotool", self.commands()
        )

    def test_failed_dependency_install_stops_before_downloads(self):
        result = self.run_script(
            success=False, TEST_MISSING_PACKAGES="curl", TEST_PACKAGE_FAILURE="43"
        )
        self.assertEqual(result.returncode, 43)
        self.assert_no_downloads()
        self.assertFalse((self.home / ".local").exists())

    def test_failed_downloads_leave_no_installation_and_can_be_retried(self):
        for resource in ("release", "appimage"):
            with self.subTest(resource=resource):
                result = self.run_script(success=False, TEST_CURL_FAILURE=resource)
                self.assertEqual(result.returncode, 22)
                self.assertFalse(self.appimage.exists())
                self.assertFalse(self.desktop.exists())
                self.assertFalse(self.autostart.exists())
        self.run_script()
        self.assertTrue(self.appimage.exists())

    def test_malformed_metadata_is_rejected(self):
        (self.fixtures / "release").write_text("not json")
        self.run_script(success=False)
        self.assertFalse(self.appimage.exists())

    def test_missing_or_ambiguous_appimage_asset_is_rejected(self):
        asset = self.release["assets"][-1]
        for assets in ([], [asset, asset]):
            with self.subTest(assets=assets):
                self.release["assets"] = assets
                self.save_release()
                self.run_script(success=False)
                self.assertFalse(self.appimage.exists())
                self.assertEqual(
                    sum(line.startswith("curl ") for line in self.commands()), 1
                )

    def test_missing_or_invalid_digest_is_rejected_before_asset_download(self):
        for digest in (None, "", "sha512:" + "a" * 128, "sha256:invalid"):
            with self.subTest(digest=digest):
                self.release["assets"][-1]["digest"] = digest
                self.save_release()
                result = self.run_script(success=False)
                self.assertIn("no valid AppImage URL or SHA-256 digest", result.stderr)
                self.assertFalse(self.appimage.exists())
                self.assertEqual(
                    sum(line.startswith("curl ") for line in self.commands()), 1
                )

    def test_unexpected_download_host_is_rejected(self):
        self.release["assets"][-1]["browser_download_url"] = "https://example.com/app.AppImage"
        self.save_release()
        self.run_script(success=False)
        self.assertFalse(self.appimage.exists())

    def test_checksum_mismatch_is_rejected_without_installing(self):
        (self.fixtures / "appimage").write_bytes(self.payload + b"tampered")
        result = self.run_script(success=False)
        self.assertIn("checksum verification failed", result.stderr)
        self.assertFalse(self.appimage.exists())
        self.assertFalse(self.desktop.exists())
        self.assertFalse(self.autostart.exists())

    def test_launchers_respect_xdg_directories(self):
        data = self.directory / "custom data"
        config = self.directory / "custom config"
        self.run_script(XDG_DATA_HOME=str(data), XDG_CONFIG_HOME=str(config))
        self.assertTrue((data / "applications/blip-ai.desktop").exists())
        self.assertTrue((config / "autostart/blip-ai.desktop").exists())
        self.assertFalse(self.desktop.exists())
        self.assertFalse(self.autostart.exists())

    def test_full_package_pipeline_installs_blip_ai_and_honors_skip(self):
        for name in (
            "cleanup-npm-global-conflicts", "install-packages", "install-steam",
            "install-warp-terminal", "install-aur-packages", "install-shatter-shell",
            "install-github-tray",
            "install-devbox", "install-uv", "install-claude-code", "install-herdr",
            "install-tailscale", "install-pi-dev", "install-pi-agent-stuff",
            "install-herdr-agent-resume", "install-herdr-worktrees", "install-playwright",
        ):
            child = self.directory / f"{name}.sh"
            child.write_text(f'#!{BASH}\nprintf "step {name}\\n" >> "$TEST_LOG"\n')
            child.chmod(0o755)
        self.run_script("install-all.sh", SKIP_BLIP_AI="1")
        self.assert_no_downloads()
        self.assertFalse(self.appimage.exists())
        self.assertFalse(self.autostart.exists())
        self.run_script("install-all.sh")
        self.assertTrue(self.appimage.exists())
        self.assertTrue(self.desktop.exists())
        self.assertTrue(self.autostart.exists())


if __name__ == "__main__":
    unittest.main()
