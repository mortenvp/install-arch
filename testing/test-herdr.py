#!/usr/bin/env python3
"""Test Herdr installation with isolated homes and mocked downloads/package commands."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
COMPONENTS = (("core", "herdr-core"), ("app", "herdr-app"), ("terminal", "herdr"))


class HerdrTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.bins = self.directory / "bin"
        self.bins.mkdir()
        for name in ("bash", "sh", "dirname", "mkdir", "mktemp", "rm", "cp", "chmod"):
            executable = shutil.which(name)
            self.assertIsNotNone(executable, f"Test dependency missing: {name}")
            (self.bins / name).symlink_to(executable)
        for name in (
            "install-herdr.sh",
            "install-upstream-tools.sh",
            "install-all.sh",
            "logging.sh",
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
        self.fixtures = self.directory / "installers"
        self.fixtures.mkdir()
        self.env = dict(
            os.environ,
            PATH=str(self.bins),
            HOME=str(self.home),
            TMPDIR=str(self.tmp),
            TEST_LOG=str(self.log),
            TEST_FIXTURES=str(self.fixtures),
        )
        for key in (
            "SKIP_HERDR",
            "SKIP_CLAUDE_CODE",
            "TEST_MISSING_PACKAGES",
            "TEST_PACKAGE_FAILURE",
            "TEST_CURL_FAILURE",
            "TEST_INSTALL_FAILURE",
            "TEST_NOOP_COMPONENT",
        ):
            self.env.pop(key, None)
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
            """
[[ "$1" == -fsSL && "$3" == -o && "$#" == 4 ]] || exit 98
case "$2" in
  https://releases.herdr.dev/core/install.sh) component=core ;;
  https://releases.herdr.dev/app/install.sh) component=app ;;
  https://herdr.dev/install.sh) component=terminal ;;
  *) exit 99 ;;
esac
cp "$TEST_FIXTURES/$component.sh" "$4"
# Leave partial executable content behind to catch accidental execution on failure.
[[ "$component" != "${TEST_CURL_FAILURE:-}" ]] || exit 22
""",
        )
        for component, command in COMPONENTS:
            installer = self.fixtures / f"{component}.sh"
            installer.write_text(
                "#!/bin/sh\nset -eu\n"
                f'printf "run {component}\\n" >> "$TEST_LOG"\n'
                f'[ "${{TEST_INSTALL_FAILURE:-}}" != "{component}" ] || exit 42\n'
                f'[ "${{TEST_NOOP_COMPONENT:-}}" != "{component}" ] || exit 0\n'
                + (
                    '[ "$HC_INSTALL_DIR" = "$HOME/.local/bin" ] || exit 97\n'
                    if component == "core"
                    else (
                        '[ "$HERDR_INSTALL_DIR" = "$HOME/.local/bin" ] || exit 97\n'
                        if component == "terminal"
                        else ""
                    )
                )
                + 'mkdir -p "$HOME/.local/bin"\n'
                f'printf "#!/bin/sh\\nexit 0\\n" > "$HOME/.local/bin/{command}"\n'
                f'chmod 755 "$HOME/.local/bin/{command}"\n'
            )

    def mock(self, name, body):
        path = self.bins / name
        path.write_text(
            f"#!{BASH}\nset -euo pipefail\n"
            f'printf \'%s\\n\' "{name} $*" >> "$TEST_LOG"\n' + body
        )
        path.chmod(0o755)

    def existing_command(self, name, *, on_path=False):
        path = self.bins / name if on_path else self.home / ".local/bin" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n# existing user installation\nexit 0\n")
        path.chmod(0o755)
        return path

    def run_script(self, name="install-herdr.sh", *, success=True, **overrides):
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
        self.assertEqual(
            list(self.tmp.iterdir()), [], "Temporary downloads not removed"
        )
        return result

    def commands(self):
        return self.log.read_text().splitlines()

    def test_skip_does_not_download_install_or_query_packages(self):
        self.run_script(SKIP_HERDR="1")
        self.assertEqual(self.commands(), [])
        self.assertFalse((self.home / ".local").exists())

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_installs_core_before_app_plus_terminal_and_rerun_is_a_noop(self):
        self.run_script()
        commands = self.commands()
        self.assertLess(commands.index("run core"), commands.index("run app"))
        downloads = [command for command in commands if command.startswith("curl ")]
        self.assertEqual(len(downloads), 3)
        for component, command in COMPONENTS:
            url = (
                "https://herdr.dev/install.sh"
                if component == "terminal"
                else f"https://releases.herdr.dev/{component}/install.sh"
            )
            self.assertIn(url, "\n".join(downloads))
            self.assertTrue(os.access(self.home / ".local/bin" / command, os.X_OK))
        self.assertFalse(any(command.startswith("sudo ") for command in commands))
        self.run_script()
        self.assertEqual(self.commands(), [])

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_existing_commands_on_path_skip_installers_and_dependencies(self):
        for _, command in COMPONENTS:
            self.existing_command(command, on_path=True)
        self.run_script(
            TEST_MISSING_PACKAGES="curl gawk tar libxkbcommon-x11 vulkan-icd-loader"
        )
        self.assertEqual(self.commands(), [])
        self.assertFalse((self.home / ".local").exists())

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_existing_core_is_preserved_when_installing_the_app(self):
        core = self.existing_command("herdr-core")
        before = core.read_bytes()
        self.run_script()
        self.assertNotIn("run core", self.commands())
        self.assertIn("run app", self.commands())
        self.assertEqual(core.read_bytes(), before)

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_existing_app_with_missing_core_is_repaired_without_reinstalling_app(self):
        app = self.existing_command("herdr-app")
        before = app.read_bytes()
        self.run_script()
        self.assertIn("run core", self.commands())
        self.assertNotIn("run app", self.commands())
        self.assertEqual(app.read_bytes(), before)

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_existing_desktop_and_core_only_install_terminal_without_gui_dependencies(self):
        existing = [self.existing_command(name) for name in ("herdr-app", "herdr-core")]
        before = [path.read_bytes() for path in existing]
        self.run_script(
            TEST_MISSING_PACKAGES="tar libxkbcommon-x11 vulkan-icd-loader",
            HERDR_INSTALL_DIR=str(self.directory / "not the install directory"),
        )
        self.assertIn("run terminal", self.commands())
        self.assertNotIn("run core", self.commands())
        self.assertNotIn("run app", self.commands())
        self.assertFalse(any(command.startswith("sudo ") for command in self.commands()))
        self.assertFalse(any("libxkbcommon-x11" in command for command in self.commands()))
        self.assertEqual([path.read_bytes() for path in existing], before)
        self.assertTrue(os.access(self.home / ".local/bin/herdr", os.X_OK))

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_existing_terminal_is_preserved_when_installing_desktop(self):
        terminal = self.existing_command("herdr")
        before = terminal.read_bytes()
        self.run_script()
        self.assertNotIn("run terminal", self.commands())
        self.assertIn("run core", self.commands())
        self.assertIn("run app", self.commands())
        self.assertEqual(terminal.read_bytes(), before)

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_terminal_only_installs_missing_terminal_dependencies(self):
        for name in ("herdr-app", "herdr-core"):
            self.existing_command(name)
        self.run_script(TEST_MISSING_PACKAGES="gawk tar libxkbcommon-x11 vulkan-icd-loader")
        self.assertIn("sudo pacman -S --noconfirm --needed gawk", self.commands())
        self.assertIn("run terminal", self.commands())

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_installs_only_missing_arch_dependencies_noninteractively(self):
        self.run_script(TEST_MISSING_PACKAGES="libxkbcommon-x11 vulkan-icd-loader")
        self.assertIn(
            "sudo pacman -S --noconfirm --needed libxkbcommon-x11 vulkan-icd-loader",
            self.commands(),
        )

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_failed_dependency_install_stops_before_downloads(self):
        result = self.run_script(
            success=False, TEST_MISSING_PACKAGES="curl", TEST_PACKAGE_FAILURE="43"
        )
        self.assertEqual(result.returncode, 43)
        self.assertFalse(
            any(command.startswith("curl ") for command in self.commands())
        )
        self.assertFalse((self.home / ".local").exists())

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_failed_core_download_is_not_executed(self):
        result = self.run_script(success=False, TEST_CURL_FAILURE="core")
        self.assertEqual(result.returncode, 22)
        self.assertNotIn("run core", self.commands())
        self.assertNotIn("run app", self.commands())
        self.assertFalse((self.home / ".local").exists())

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_failed_app_download_is_not_executed_and_retry_reuses_core(self):
        self.run_script(success=False, TEST_CURL_FAILURE="app")
        self.assertIn("run core", self.commands())
        self.assertNotIn("run app", self.commands())
        self.run_script()
        self.assertNotIn("run core", self.commands())
        self.assertIn("run app", self.commands())

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_failed_terminal_download_is_not_executed_and_can_be_retried(self):
        for name in ("herdr-app", "herdr-core"):
            self.existing_command(name)
        result = self.run_script(success=False, TEST_CURL_FAILURE="terminal")
        self.assertEqual(result.returncode, 22)
        self.assertNotIn("run terminal", self.commands())
        self.assertFalse((self.home / ".local/bin/herdr").exists())
        self.run_script()
        self.assertIn("run terminal", self.commands())
        self.assertNotIn("run core", self.commands())
        self.assertNotIn("run app", self.commands())

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_failed_installer_stops_the_script(self):
        for component, _ in COMPONENTS:
            with self.subTest(component=component):
                result = self.run_script(success=False, TEST_INSTALL_FAILURE=component)
                self.assertEqual(result.returncode, 42)
                if component == "core":
                    self.assertNotIn("run app", self.commands())
                if component != "terminal":
                    self.assertNotIn("run terminal", self.commands())

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_success_without_an_installed_command_is_reported_as_failure(self):
        for component, command in COMPONENTS:
            with self.subTest(component=component):
                result = self.run_script(success=False, TEST_NOOP_COMPONENT=component)
                self.assertIn(f"did not install {command}", result.stderr)
                if component == "core":
                    self.assertNotIn("run app", self.commands())

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_full_package_pipeline_installs_herdr_and_honors_skip(self):
        for name in (
            "cleanup-npm-global-conflicts",
            "install-packages",
            "install-steam",
            "install-warp-terminal",
            "install-aur-packages",
            "install-shatter-shell",
            "install-devbox",
            "install-uv",
            "install-claude-code",
            "install-blip-ai",
            "install-tailscale",
            "install-pi-dev",
            "install-pi-agent-stuff",
            "install-herdr-agent-resume",
            "install-playwright",
        ):
            child = self.directory / f"{name}.sh"
            child.write_text(f'#!{BASH}\nprintf "step {name}\\n" >> "$TEST_LOG"\n')
            child.chmod(0o755)
        self.run_script("install-all.sh", SKIP_HERDR="1")
        self.assertNotIn("run core", self.commands())
        self.assertNotIn("run app", self.commands())
        self.assertNotIn("run terminal", self.commands())
        self.run_script("install-all.sh")
        self.assertIn("run core", self.commands())
        self.assertIn("run app", self.commands())
        self.assertIn("run terminal", self.commands())


if __name__ == "__main__":
    unittest.main()
