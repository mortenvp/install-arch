#!/usr/bin/env python3
"""Offline GitHub Tray tests: isolated homes, release bundles and GNOME commands."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
UUID = "github-tray@debba.github.com"
GSCONNECT = "gsconnect@andyholmes.github.io"
URL = ("https://github.com/debba/github-tray-gnome-extension/releases/download/"
       "v19/github-tray%40debba.github.com.zip")


def patch_preimages():
    """Minimal offline release sources: exact old hunks, comments elsewhere.

    These are not executable full modules. JS behavior tests extract the complete
    methods added by the patch; the real pinned bundle is checked separately.
    """
    sources = {}
    lines = None
    for line in (ROOT / "patches/github-tray-v19-done.patch").read_text().splitlines(True):
        if line.startswith("--- a/"):
            lines = sources.setdefault(line[6:].strip(), [])
        elif line.startswith("@@ "):
            start = int(re.match(r"@@ -(\d+)", line)[1])
            lines.extend(["// upstream fixture\n"] * (start - 1 - len(lines)))
        elif line.startswith((" ", "-")):
            lines.append(line[1:])
    return {name: "".join(content) for name, content in sources.items()}


@unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
class GitHubTrayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.home = self.directory / "home with spaces"
        self.home.mkdir()
        self.bins = self.directory / "bin"
        self.bins.mkdir()
        self.tmp = self.directory / "downloads"
        self.tmp.mkdir()
        self.data = self.directory / "custom data"
        self.extension = self.data / "gnome-shell/extensions" / UUID
        self.log = self.directory / "commands.log"
        self.log.touch()
        for name in ("bash", "dirname", "mktemp", "rm", "unzip", "jq", "sha256sum", "python3", "grep", "head", "cat", "install", "patch"):
            executable = shutil.which(name)
            self.assertIsNotNone(executable, f"Test dependency missing: {name}")
            (self.bins / name).symlink_to(executable)
        for name in ("logging.sh", "install-all.sh", "enable-gnome-extensions.sh", "configure-github-tray.sh"):
            content = (ROOT / "scripts" / name).read_text().replace(
                "/usr/share/gnome-shell/extensions", str(self.directory / "system-extensions"))
            (self.directory / name).write_text(content)
            (self.directory / name).chmod(0o755)
        self.launcher = self.data / "applications/github-tray-settings.desktop"
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bins),
                        XDG_DATA_HOME=str(self.data), TMPDIR=str(self.tmp),
                        TEST_LOG=str(self.log), SKIP_SHATTER_SHELL="1", TEST_EXTENSIONS="")
        for key in ("SKIP_GITHUB_TRAY", "TEST_MISSING_PACKAGES", "TEST_PACKAGE_FAIL",
                    "TEST_CURL_FAIL", "TEST_ENABLE_FAIL", "TEST_GNOME_VERSION"):
            self.env.pop(key, None)
        self.bundle = self.directory / "release.zip"
        self.env["TEST_BUNDLE"] = str(self.bundle)
        self.metadata = {"uuid": UUID, "version": 19, "shell-version": ["45", "50", "51"]}
        self.schema = '''<schemalist>
  <schema id="org.gnome.shell.extensions.github-tray" path="/org/gnome/shell/extensions/github-tray/">
    <key name="test-enabled" type="b"><default>true</default></key>
  </schema>
</schemalist>
'''
        self.sources = patch_preimages()
        patches = self.directory / "patches"
        patches.mkdir()
        shutil.copy2(ROOT / "patches/github-tray-v19-done.patch", patches)
        self.save_bundle()
        self.mock("gnome-shell", 'printf "GNOME Shell %s\\n" "${TEST_GNOME_VERSION:-51.1}"\n')
        self.mock("pacman", '''[[ "$1" == -Q ]] || exit 99
case " ${TEST_MISSING_PACKAGES:-} " in
  *" $2 "*) exit 1 ;;
  *) exit 0 ;;
esac
''')
        self.mock("sudo", '[[ "$*" == "pacman -S --noconfirm --needed "* ]]\n'
                  'exit "${TEST_PACKAGE_FAIL:-0}"\n')
        self.mock("curl", f'''[[ "$#" == 4 && "$1" == -fsSL && "$2" == "{URL}" && "$3" == -o ]]
python3 -c 'import shutil,sys; shutil.copyfile(sys.argv[1], sys.argv[2])' "$TEST_BUNDLE" "$4"
exit "${{TEST_CURL_FAIL:-0}}"
''')
        self.mock("glib-compile-schemas", f'exec "{shutil.which("glib-compile-schemas")}" "$@"\n')
        self.unpack = self.directory / "unpack.py"
        self.unpack.write_text('''import os, sys, zipfile
from pathlib import Path
root = Path(os.environ["XDG_DATA_HOME"]) / "gnome-shell/extensions/github-tray@debba.github.com"
with zipfile.ZipFile(sys.argv[1]) as archive:
    archive.extractall(root)
''')
        self.env["TEST_UNPACK"] = str(self.unpack)
        self.mock("gnome-extensions", '''case "$1" in
  install) [[ "$#" == 3 && "$2" == --force ]]; python3 "$TEST_UNPACK" "$3" ;;
  list) printf '%s\\n' "$TEST_EXTENSIONS" ;;
  enable) [[ "$2" != "${TEST_ENABLE_FAIL:-}" ]] ;;
  *) exit 99 ;;
esac
''')
        self.mock("gsettings", 'if [[ "$1" == get ]]; then printf "false\\n"; fi\n')

    def save_bundle(self):
        with zipfile.ZipFile(self.bundle, "w") as archive:
            archive.writestr("metadata.json", json.dumps(self.metadata))
            archive.writestr("schemas/org.gnome.shell.extensions.github-tray.gschema.xml", self.schema)
            for name, content in self.sources.items():
                archive.writestr(name, content)
        digest = hashlib.sha256(self.bundle.read_bytes()).hexdigest()
        # Only the pinned checksum changes for our offline fixture; production URL/version stay intact.
        source, count = re.subn(r'SHA256="[a-f0-9]{64}"', f'SHA256="{digest}"',
                               (ROOT / "scripts/install-github-tray.sh").read_text())
        self.assertEqual(count, 1)
        source = source.replace("$SCRIPT_DIR/../patches/", "$SCRIPT_DIR/patches/")
        (self.directory / "install-github-tray.sh").write_text(source)

    def mock(self, name, body):
        path = self.bins / name
        path.write_text(f"#!{BASH}\nset -euo pipefail\n"
                        f'printf "%s\\n" "{name} $*" >> "$TEST_LOG"\n' + body)
        path.chmod(0o755)

    def run_script(self, script="install-github-tray.sh", success=True, **overrides):
        self.log.write_text("")
        result = subprocess.run([BASH, str(self.directory / script)],
                                env=dict(self.env, **overrides), input="", capture_output=True,
                                text=True, start_new_session=True, timeout=15)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(self.tmp.iterdir()), [], "Temporary downloads not cleaned up")
        return result

    def commands(self):
        return self.log.read_text().splitlines()

    def test_skip_does_not_query_packages_or_change_files(self):
        self.run_script(SKIP_GITHUB_TRAY="1")
        self.assertEqual(self.commands(), [])
        self.assertFalse(self.data.exists())

    def test_installs_verified_release_compiles_schema_and_rerun_is_a_noop(self):
        self.run_script()
        self.assertEqual(json.loads((self.extension / "metadata.json").read_text()), self.metadata)
        self.assertTrue((self.extension / "schemas/gschemas.compiled").is_file())
        self.assertTrue(any(line.startswith("gnome-extensions install --force ") for line in self.commands()))
        self.assertFalse(any(line.startswith(("gsettings ", "gnome-extensions enable ", "sudo "))
                             for line in self.commands()))
        self.assertIn("Name=GitHub Tray Settings\n", self.launcher.read_text())
        self.assertIn(f"Exec=gnome-extensions prefs {UUID}\n", self.launcher.read_text())
        validator = shutil.which("desktop-file-validate")
        if validator:
            subprocess.run([validator, str(self.launcher)], check=True, capture_output=True, timeout=10)
        original = (self.extension / "extension.js").read_bytes()
        launcher = self.launcher.read_text()
        self.launcher.unlink()
        self.run_script()
        self.assertFalse(any(line.startswith(("curl ", "gnome-extensions install ")) for line in self.commands()))
        self.assertEqual((self.extension / "extension.js").read_bytes(), original)
        self.assertEqual(self.launcher.read_text(), launcher)

    def test_existing_pristine_v19_gets_done_without_downloading(self):
        with zipfile.ZipFile(self.bundle) as archive:
            archive.extractall(self.extension)
        self.run_script()
        self.assertIn("async markNotificationDone(", (self.extension / "githubApi.js").read_text())
        self.assertFalse(any(line.startswith(("curl ", "gnome-extensions install ")) for line in self.commands()))

    def test_incompatible_existing_sources_are_not_partially_patched(self):
        with zipfile.ZipFile(self.bundle) as archive:
            archive.extractall(self.extension)
        api = self.extension / "githubApi.js"
        api.write_text(api.read_text().replace("async fetchRepoWorkflowRuns(", "async customWorkflowRuns("))
        original = {name: (self.extension / name).read_bytes() for name in self.sources}
        result = self.run_script(success=False)
        self.assertIn("do not match the v19 Done patch", result.stderr)
        self.assertEqual(original, {name: (self.extension / name).read_bytes() for name in self.sources})
        self.assertFalse(any(self.extension.glob("*.rej")))

    def test_incompatible_bundle_is_rejected_before_installing(self):
        self.sources["githubApi.js"] = "// unsupported source\n"
        self.save_bundle()
        self.run_script(success=False)
        self.assertFalse(self.extension.exists())
        self.assertFalse(any(line.startswith("gnome-extensions install ") for line in self.commands()))

    def test_symlinked_source_is_not_patched(self):
        with zipfile.ZipFile(self.bundle) as archive:
            archive.extractall(self.extension)
        source = self.extension / "ui.js"
        target = self.directory / "external-ui.js"
        source.rename(target)
        original = target.read_bytes()
        source.symlink_to(target)
        self.run_script(success=False)
        self.assertEqual(target.read_bytes(), original)

    @unittest.skipUnless(shutil.which("node"), "JS behavior tests require Node.js")
    def test_done_behavior(self):
        self.run_script()
        result = subprocess.run(
            [shutil.which("node"), str(ROOT / "testing/test-github-tray-done.mjs"),
             str(self.extension)], capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_installs_only_missing_dependencies_noninteractively(self):
        self.run_script(TEST_MISSING_PACKAGES="libsoup3 zenity")
        self.assertIn("sudo pacman -S --noconfirm --needed libsoup3 zenity", self.commands())

    def test_dependency_failure_stops_before_download(self):
        self.run_script(success=False, TEST_MISSING_PACKAGES="curl", TEST_PACKAGE_FAIL="42")
        self.assertFalse(any(line.startswith("curl ") for line in self.commands()))
        self.assertFalse(self.extension.exists())

    def test_missing_gnome_stops_before_installing_dependencies(self):
        (self.bins / "gnome-shell").unlink()
        result = self.run_script(success=False)
        self.assertIn("install GNOME", result.stderr)
        self.assertEqual(self.commands(), [])

    def test_failed_download_is_not_installed_and_can_be_retried(self):
        result = self.run_script(success=False, TEST_CURL_FAIL="22")
        self.assertEqual(result.returncode, 22)
        self.assertFalse(self.extension.exists())
        self.run_script()
        self.assertTrue(self.extension.exists())

    def test_checksum_failure_preserves_existing_installation(self):
        self.extension.mkdir(parents=True)
        old = self.extension / "extension.js"
        old.write_text("keep existing extension\n")
        self.bundle.write_bytes(self.bundle.read_bytes() + b"tampered")
        result = self.run_script(success=False)
        self.assertIn("checksum verification failed", result.stderr)
        self.assertEqual(old.read_text(), "keep existing extension\n")
        self.assertFalse(any(line.startswith("gnome-extensions install ") for line in self.commands()))

    def test_unsupported_gnome_leaves_extension_unchanged(self):
        result = self.run_script(success=False, TEST_GNOME_VERSION="52.0")
        self.assertIn("does not declare support for GNOME 52", result.stderr)
        self.assertFalse(self.extension.exists())

    def test_unexpected_uuid_or_release_version_is_rejected(self):
        for key, value in (("uuid", "other@example.invalid"), ("version", 20)):
            with self.subTest(key=key):
                original = dict(self.metadata)
                self.metadata[key] = value
                self.save_bundle()
                self.run_script(success=False)
                self.assertFalse(self.extension.exists())
                self.metadata = original

    def test_invalid_schema_fails_before_installation(self):
        self.schema = "not valid XML"
        self.save_bundle()
        self.run_script(success=False)
        self.assertFalse(self.extension.exists())
        self.assertFalse(any(line.startswith("gnome-extensions install ") for line in self.commands()))

    def test_newer_extension_is_not_downgraded_and_missing_schema_is_repaired(self):
        self.run_script()
        metadata = self.extension / "metadata.json"
        metadata.write_text(json.dumps(dict(self.metadata, version=20)))
        (self.extension / "schemas/gschemas.compiled").unlink()
        self.run_script()
        self.assertEqual(json.loads(metadata.read_text())["version"], 20)
        self.assertTrue((self.extension / "schemas/gschemas.compiled").is_file())
        self.assertFalse(any(line.startswith("curl ") for line in self.commands()))

    def test_symlinked_extension_is_refused(self):
        target = self.directory / "managed extension"
        target.mkdir()
        self.extension.parent.mkdir(parents=True)
        self.extension.symlink_to(target)
        result = self.run_script(success=False)
        self.assertIn("symlinked extension", result.stderr)
        self.assertTrue(self.extension.is_symlink())
        self.assertEqual(list(target.iterdir()), [])

    def test_configure_existing_extension_creates_launcher_without_running_preferences(self):
        self.extension.mkdir(parents=True)
        (self.extension / "metadata.json").write_text(json.dumps(self.metadata))
        self.run_script("configure-github-tray.sh")
        self.assertTrue(self.launcher.is_file())
        self.assertEqual(self.commands(), [])
        self.assertEqual(list(self.home.iterdir()), [])

    def test_configure_without_installed_extension_creates_no_launcher(self):
        self.run_script("configure-github-tray.sh")
        self.assertFalse(self.data.exists())
        self.assertEqual(self.commands(), [])

    def test_skip_keeps_existing_launcher_unchanged(self):
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_text("my existing launcher\n")
        self.run_script("configure-github-tray.sh", SKIP_GITHUB_TRAY="1")
        self.assertEqual(self.launcher.read_text(), "my existing launcher\n")
        self.assertEqual(self.commands(), [])

    def test_configuration_enables_github_tray(self):
        self.run_script("enable-gnome-extensions.sh", TEST_EXTENSIONS=UUID)
        self.assertIn(f"gnome-extensions enable {UUID}", self.commands())

    def test_configuration_skip_does_not_disable_an_existing_extension(self):
        self.run_script("enable-gnome-extensions.sh", SKIP_GITHUB_TRAY="1", TEST_EXTENSIONS=UUID)
        self.assertNotIn(f"gnome-extensions enable {UUID}", self.commands())
        self.assertFalse(any(line.startswith("gnome-extensions disable ") for line in self.commands()))

    def test_not_yet_visible_extension_reports_relogin_without_aborting(self):
        self.extension.mkdir(parents=True)
        result = self.run_script("enable-gnome-extensions.sh", TEST_ENABLE_FAIL=UUID,
                                 TEST_EXTENSIONS=GSCONNECT)
        self.assertIn("log out/in and run this script again", result.stdout)
        self.assertIn(f"gnome-extensions enable {UUID}", self.commands())
        self.assertIn(f"gnome-extensions enable {GSCONNECT}", self.commands())

    def test_full_pipeline_runs_extension_installer(self):
        for name in ("cleanup-npm-global-conflicts", "install-packages", "install-steam",
                     "install-warp-terminal", "install-aur-packages", "install-shatter-shell",
                     "install-upstream-tools"):
            path = self.directory / f"{name}.sh"
            path.write_text(f'#!{BASH}\nprintf "step {name}\\n" >> "$TEST_LOG"\n')
            path.chmod(0o755)
        (self.directory / "install-github-tray.sh").chmod(0o755)
        self.run_script("install-all.sh", SKIP_GITHUB_TRAY="1")
        self.assertFalse(self.extension.exists())
        self.run_script("install-all.sh")
        self.assertTrue(self.extension.exists())


if __name__ == "__main__":
    unittest.main()
