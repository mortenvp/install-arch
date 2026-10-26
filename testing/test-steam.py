#!/usr/bin/env python3
"""Test Steam setup without installing packages or changing host configuration."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
BASE_CONFIG = """[options]
Architecture = auto
[core]
Include = /etc/pacman.d/mirrorlist
# [multilib]
# Include = /etc/pacman.d/mirrorlist
[multilib-testing]
Server = https://example.invalid/$repo/os/$arch
"""


class SteamTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.bins = self.directory / "bin"
        self.bins.mkdir()
        # An isolated PATH ensures tests cannot invoke host sudo or pacman.
        for command in ("bash", "dirname", "grep", "cp", "tee"):
            executable = shutil.which(command)
            self.assertIsNotNone(executable, f"Test dependency missing: {command}")
            (self.bins / command).symlink_to(executable)
        self.conf = self.directory / "pacman.conf"
        self.conf.write_text(BASE_CONFIG)
        self.backup = self.directory / "pacman.conf.before-steam"
        self.mirrorlist = self.directory / "mirrorlist"
        self.mirrorlist.write_text("Server = https://example.invalid/$repo/os/$arch\n")
        self.include = self.directory / "custom-repos.conf"
        self.include.touch()
        self.pci = self.directory / "pci"
        self.pci.mkdir()
        for name in ("install-steam.sh", "configure-multilib.sh", "logging.sh"):
            content = (ROOT / "scripts" / name).read_text()
            content = content.replace("/etc/pacman.conf", str(self.conf))
            content = content.replace("/etc/pacman.d/mirrorlist", str(self.mirrorlist))
            content = content.replace("/sys/bus/pci/devices", str(self.pci))
            target = self.directory / name
            target.write_text(content)
            target.chmod(0o755)
        self.log = self.directory / "commands.log"
        self.log.touch()
        self.env = dict(
            PATH=str(self.bins),
            HOME=str(self.directory),
            TEST_LOG=str(self.log),
            TEST_CONF=str(self.conf),
            TEST_INCLUDE=str(self.include),
        )
        self.mock("sudo", 'exec "$@"\n')
        self.mock("uname", 'printf "%s\\n" "${TEST_ARCH:-x86_64}"\n')
        self.mock("pacman-conf", '''
[[ "$*" == --repo-list ]] || exit 99
[[ "${TEST_CONFIG_STATUS:-0}" == 0 ]] || exit "$TEST_CONFIG_STATUS"
printf 'core\\nextra\\nmultilib-testing\\n'
if grep -Eq '^\\[multilib\\]' "$TEST_CONF" "$TEST_INCLUDE"; then
  printf 'multilib\\n'
fi
''')
        self.mock("pacman", '''
[[ "$1" == -Syu && "$2" == --noconfirm && "$3" == --needed ]] || exit 99
grep -Eq '^\\[multilib\\]' "$TEST_CONF" "$TEST_INCLUDE"
exit "${TEST_PACMAN_STATUS:-0}"
''')

    def mock(self, name, body):
        path = self.bins / name
        path.write_text(
            f"#!{BASH}\nset -euo pipefail\n"
            f"printf '%s\\n' \"{name} $*\" >> \"$TEST_LOG\"\n" + body
        )
        path.chmod(0o755)

    def gpu(self, vendor, device_class="0x030000"):
        device = self.pci / str(len(list(self.pci.iterdir())))
        device.mkdir()
        (device / "class").write_text(device_class + "\n")
        (device / "vendor").write_text(vendor + "\n")

    def run_script(self, *arguments, success=True, **overrides):
        self.log.write_text("")
        result = subprocess.run(
            [BASH, str(self.directory / "install-steam.sh"), *arguments],
            env=dict(self.env, **overrides),
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def commands(self):
        return self.log.read_text().splitlines()

    def packages(self):
        installs = [line for line in self.commands() if line.startswith("pacman ")]
        self.assertEqual(len(installs), 1)
        self.assertTrue(installs[0].startswith("pacman -Syu --noconfirm --needed "))
        return installs[0].split()[4:]

    def assert_no_writes(self):
        self.assertFalse(any(line.startswith("sudo ") for line in self.commands()))
        self.assertEqual(self.conf.read_text(), BASE_CONFIG)
        self.assertFalse(self.backup.exists())

    def test_enables_multilib_preserving_config_and_backup_on_rerun(self):
        self.gpu("0x1002")
        self.run_script()
        configured = self.conf.read_text()
        self.assertTrue(configured.startswith(BASE_CONFIG))
        self.assertEqual(configured.count("\n[multilib]\n"), 1)
        self.assertIn(f"Include = {self.mirrorlist}", configured)
        self.assertEqual(self.backup.read_text(), BASE_CONFIG)
        self.assertIn("steam", self.packages())
        self.run_script()
        self.assertEqual(self.conf.read_text(), configured)
        self.assertEqual(self.backup.read_text(), BASE_CONFIG)
        self.assertFalse(any(line.startswith(("sudo cp ", "sudo tee ")) for line in self.commands()))

    def test_preserves_existing_multilib_including_custom_include(self):
        custom = "[multilib]\nServer = https://custom.invalid/$repo/os/$arch\n"
        for included in (False, True):
            with self.subTest(included=included):
                config = BASE_CONFIG + (f"Include = {self.include}\n" if included else custom)
                self.conf.write_text(config)
                self.include.write_text(custom if included else "")
                self.run_script()
                self.assertEqual(self.conf.read_text(), config)
                self.assertFalse(self.backup.exists())
                self.assertFalse(any(line.startswith("sudo tee ") for line in self.commands()))

    def test_does_not_overwrite_an_older_backup(self):
        self.backup.write_text("original backup\n")
        self.run_script()
        self.assertEqual(self.backup.read_text(), "original backup\n")

    def test_gpu_libraries(self):
        for vendor, expected in (
            ("0x8086", {"vulkan-intel", "lib32-vulkan-intel"}),
            ("0x1002", {"vulkan-radeon", "lib32-vulkan-radeon"}),
            ("0x10de", {"nvidia-utils", "lib32-nvidia-utils"}),
        ):
            with self.subTest(vendor=vendor):
                for device in self.pci.iterdir():
                    shutil.rmtree(device)
                self.gpu(vendor)
                self.run_script()
                self.assertEqual(set(self.packages()), expected | {
                    "steam", "mesa", "lib32-mesa", "vulkan-icd-loader", "lib32-vulkan-icd-loader",
                })

    def test_hybrid_gpus_and_duplicate_devices(self):
        self.gpu("0x8086")
        self.gpu("0x10de", "0x030200")
        self.gpu("0x10de", "0x030200")
        self.run_script()
        packages = self.packages()
        self.assertIn("lib32-vulkan-intel", packages)
        self.assertIn("lib32-nvidia-utils", packages)
        self.assertNotIn("lib32-vulkan-swrast", packages)
        self.assertEqual(len(packages), len(set(packages)))

    def test_non_display_devices_do_not_select_gpu_drivers(self):
        self.gpu("0x8086", "0x020000")
        self.gpu("0x10de", "0x040300")
        self.run_script()
        self.assertIn("lib32-vulkan-swrast", self.packages())
        self.assertNotIn("lib32-nvidia-utils", self.packages())
        self.assertNotIn("lib32-vulkan-intel", self.packages())

    def test_no_gpu_uses_software_vulkan(self):
        result = self.run_script()
        self.assertIn("limited gaming performance", result.stdout)
        self.assertIn("vulkan-swrast", self.packages())
        self.assertIn("lib32-vulkan-swrast", self.packages())

    def test_check_is_read_only(self):
        self.gpu("0x1002")
        result = self.run_script("--check")
        self.assertIn("lib32-vulkan-radeon", result.stdout)
        self.assert_no_writes()

    def test_skip_has_no_side_effects(self):
        self.run_script(SKIP_STEAM="1")
        self.assertEqual(self.commands(), [])
        self.assert_no_writes()

    def test_bad_arguments_and_unsupported_architecture(self):
        for arguments in (("--unknown",), ("--check", "extra")):
            self.run_script(*arguments, success=False)
            self.assert_no_writes()
        self.run_script(success=False, TEST_ARCH="aarch64")
        self.assert_no_writes()

    def test_missing_pacman_fails_before_changes(self):
        (self.bins / "pacman").unlink()
        self.run_script(success=False)
        self.assert_no_writes()

    def test_invalid_pacman_config_stops_before_changes(self):
        self.run_script(success=False, TEST_CONFIG_STATUS="1")
        self.assert_no_writes()

    def test_missing_mirrorlist_stops_before_changes(self):
        self.mirrorlist.unlink()
        self.run_script(success=False)
        self.assert_no_writes()

    def test_package_failure_is_reported(self):
        result = self.run_script(success=False, TEST_PACMAN_STATUS="1")
        self.assertNotIn("Steam installed;", result.stdout)


if __name__ == "__main__":
    unittest.main()
