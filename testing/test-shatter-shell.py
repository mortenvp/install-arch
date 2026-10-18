#!/usr/bin/env python3
"""Test Shatter Shell installation and migration with isolated, mocked commands."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
REPOSITORY = "https://github.com/adil192/shatter-shell.git"
SHATTER = "shatter-shell@adilhanney.com"
POP = "pop-shell@system76.com"
GSCONNECT = "gsconnect@andyholmes.github.io"


class ShatterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.bins = self.directory / "bin"
        self.bins.mkdir()
        for command in ("dirname", "mkdir", "cp", "touch", "grep", "head", "jq"):
            executable = shutil.which(command)
            self.assertIsNotNone(executable, f"Test dependency missing: {command}")
            (self.bins / command).symlink_to(executable)
        for name in ("install-shatter-shell.sh", "enable-gnome-extensions.sh", "logging.sh"):
            content = (ROOT / "scripts" / name).read_text()
            # Keep system-extension discovery independent of the host desktop.
            content = content.replace(
                "/usr/share/gnome-shell/extensions",
                str(self.directory / "system-extensions"),
            )
            (self.directory / name).write_text(content)
        self.log = self.directory / "commands.log"
        self.log.touch()
        self.home = self.directory / "home"
        self.home.mkdir()
        self.cache = self.directory / "cache with spaces"
        self.data = self.directory / "data with spaces"
        self.source = self.cache / "install-arch/shatter-shell"
        self.extension = self.data / "gnome-shell/extensions" / SHATTER
        metadata = self.directory / "metadata.json"
        metadata.write_text(json.dumps({"uuid": SHATTER, "shell-version": ["48", "49", "50", "51"]}))
        self.env = dict(
            os.environ,
            PATH=str(self.bins),
            HOME=str(self.home),
            XDG_CACHE_HOME=str(self.cache),
            XDG_DATA_HOME=str(self.data),
            TEST_LOG=str(self.log),
            TEST_METADATA=str(metadata),
            TEST_EXTENSIONS="",
        )
        for key in ("SKIP_SHATTER_SHELL", "TEST_GIT_DIRTY", "TEST_GIT_BRANCH", "TEST_GIT_ORIGIN"):
            self.env.pop(key, None)
        self.mock("git", '''
if [[ "$1" == clone ]]; then
  target="${@: -1}"
  mkdir -p "$target/node_modules/.bin"
  cp "$TEST_METADATA" "$target/metadata.json"
else
  shift 2
  case "$1" in
    remote) printf '%s\\n' "${TEST_GIT_ORIGIN:-https://github.com/adil192/shatter-shell.git}" ;;
    branch) printf '%s\\n' "${TEST_GIT_BRANCH:-master_resolute}" ;;
    status) printf '%s' "${TEST_GIT_DIRTY:-}" ;;
    pull) exit "${TEST_PULL_STATUS:-0}" ;;
    *) exit 99 ;;
  esac
fi
''')
        self.mock("make", '''
case "$1" in
  clean) ;;
  compile)
    [[ "$PATH" == "$PWD/node_modules/.bin:"* ]] || exit 98
    [[ "${TEST_BUILD_STATUS:-0}" == 0 ]] || exit "$TEST_BUILD_STATUS"
    mkdir -p _build/schemas
    touch _build/extension.js
    ;;
  install)
    [[ "$2" == DESTDIR= && "$3" == INSTALLBASE=* ]] || exit 97
    target="${3#INSTALLBASE=}/shatter-shell@adilhanney.com"
    mkdir -p "$target"
    cp -r _build/* "$target/"
    ;;
  *) exit 99 ;;
esac
''')
        self.mock("glib-compile-schemas", 'touch "$1/gschemas.compiled"\n')
        for command in ("node", "npm", "sudo"):
            self.mock(command, "exit 0\n")
        self.mock("gnome-shell", 'printf "GNOME Shell %s\\n" "${TEST_GNOME_VERSION:-51.0}"\n')
        self.mock("gnome-extensions", '''
case "$1" in
  list) printf '%s\\n' "$TEST_EXTENSIONS" ;;
  enable) [[ "$2" != "${TEST_ENABLE_FAIL_UUID:-}" ]] ;;
  disable) [[ "$2" != "${TEST_DISABLE_FAIL_UUID:-}" ]] ;;
  *) exit 99 ;;
esac
''')
        self.mock("gsettings", '''
if [[ "$1" == get ]]; then printf '%s\\n' "${TEST_DISABLE_USER_EXTENSIONS:-false}"; fi
''')

    def mock(self, name, body):
        path = self.bins / name
        path.write_text(
            f"#!{BASH}\nset -euo pipefail\n"
            f"printf '%s\\n' \"{name} $*\" >> \"$TEST_LOG\"\n" + body
        )
        path.chmod(0o755)

    def run_script(self, name="install-shatter-shell.sh", success=True, **overrides):
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
        return result

    def commands(self):
        return self.log.read_text().splitlines()

    def checkout(self):
        self.source.mkdir(parents=True)
        shutil.copy(self.env["TEST_METADATA"], self.source / "metadata.json")

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_install_and_update_without_configuring_gnome(self):
        self.run_script()
        self.assertIn(f"git clone --single-branch --branch master_resolute {REPOSITORY} {self.source}", self.commands())
        self.assertTrue((self.extension / "schemas/gschemas.compiled").is_file())
        commands = self.commands()
        self.assertLess(commands.index("make compile"), commands.index("glib-compile-schemas _build/schemas"))
        self.assertLess(commands.index("glib-compile-schemas _build/schemas"), commands.index(f"make install DESTDIR= INSTALLBASE={self.extension.parent}"))
        self.assertFalse(any(line.startswith(("sudo ", "gsettings ", "gnome-extensions ")) for line in commands))
        self.run_script()
        self.assertIn(f"git -C {self.source} pull --ff-only", self.commands())
        self.assertFalse(any(" clone " in line for line in self.commands()))

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_installs_only_missing_dependencies(self):
        (self.bins / "node").unlink()
        self.run_script()
        self.assertIn("sudo pacman -S --noconfirm --needed nodejs", self.commands())

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_unsupported_gnome_does_not_build_or_replace_extension(self):
        result = self.run_script(success=False, TEST_GNOME_VERSION="47.9")
        self.assertIn("does not declare support for GNOME 47", result.stderr)
        self.assertFalse(any(line.startswith("make ") for line in self.commands()))
        self.assertFalse(self.extension.exists())

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_refuses_modified_or_unexpected_checkout(self):
        self.checkout()
        for override in (
            {"TEST_GIT_DIRTY": " M src/extension.ts"},
            {"TEST_GIT_BRANCH": "my-work"},
            {"TEST_GIT_ORIGIN": "https://example.invalid/other.git"},
        ):
            with self.subTest(override=override):
                result = self.run_script(success=False, **override)
                self.assertIn("Refusing to overwrite", result.stderr)
                self.assertFalse(any(" pull " in line or line.startswith("make ") for line in self.commands()))

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_failed_update_stops_before_build(self):
        self.checkout()
        self.run_script(success=False, TEST_PULL_STATUS="1")
        self.assertFalse(any(line.startswith("make ") for line in self.commands()))

    @unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
    def test_failed_build_preserves_installed_extension(self):
        self.extension.mkdir(parents=True)
        sentinel = self.extension / "old-extension.js"
        sentinel.write_text("keep me")
        self.run_script(success=False, TEST_BUILD_STATUS="1")
        self.assertEqual(sentinel.read_text(), "keep me")
        self.assertFalse(any(line.startswith("make install") for line in self.commands()))

    def test_skip_install_does_nothing(self):
        self.run_script(SKIP_SHATTER_SHELL="1")
        self.assertEqual(self.commands(), [])
        self.assertFalse(self.source.exists())

    def test_disables_pop_before_enabling_shatter(self):
        for _ in range(2):
            self.run_script("enable-gnome-extensions.sh", TEST_EXTENSIONS=f"{POP}\n{SHATTER}\n{GSCONNECT}")
            commands = self.commands()
            self.assertLess(commands.index(f"gnome-extensions disable {POP}"), commands.index(f"gnome-extensions enable {SHATTER}"))
            self.assertNotIn(f"gnome-extensions enable {POP}", commands)
            self.assertIn("gsettings set org.gnome.mutter workspaces-only-on-primary false", commands)
            self.assertIn(f"gnome-extensions enable {GSCONNECT}", commands)

    def test_fresh_extension_not_yet_visible_does_not_abort_other_enables(self):
        self.extension.mkdir(parents=True)
        result = self.run_script(
            "enable-gnome-extensions.sh",
            TEST_EXTENSIONS=f"{POP}\n{GSCONNECT}",
            TEST_ENABLE_FAIL_UUID=SHATTER,
        )
        self.assertIn("log out/in and run this script again", result.stdout)
        self.assertIn(f"gnome-extensions disable {POP}", self.commands())
        self.assertIn(f"gnome-extensions enable {GSCONNECT}", self.commands())

    def test_skip_configuration_leaves_pop_and_workspaces_unchanged(self):
        self.run_script("enable-gnome-extensions.sh", SKIP_SHATTER_SHELL="1", TEST_EXTENSIONS=f"{POP}\n{SHATTER}")
        self.assertFalse(any(line.startswith(("gnome-extensions disable", "gnome-extensions enable")) for line in self.commands()))
        self.assertFalse(any("workspaces-only-on-primary" in line for line in self.commands()))

    def test_no_shatter_leaves_pop_unchanged(self):
        self.run_script("enable-gnome-extensions.sh", TEST_EXTENSIONS=POP)
        self.assertFalse(any(line.startswith(("gnome-extensions disable", "gnome-extensions enable")) for line in self.commands()))

    def test_failed_pop_disable_does_not_enable_shatter(self):
        self.run_script("enable-gnome-extensions.sh", success=False, TEST_EXTENSIONS=f"{POP}\n{SHATTER}", TEST_DISABLE_FAIL_UUID=POP)
        self.assertNotIn(f"gnome-extensions enable {SHATTER}", self.commands())


if __name__ == "__main__":
    unittest.main()
