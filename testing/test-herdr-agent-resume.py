#!/usr/bin/env python3
"""Offline wrapper tests: isolated homes, fake Git checkout and upstream installer."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
REVISION = "a62a3eeb9d2fc46f60490ecd44042b0a0b77cb28"


@unittest.skipIf(os.geteuid() == 0, "Installation must run as a normal user")
class ResumeTests(unittest.TestCase):
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
        self.log = self.directory / "commands.log"
        self.log.touch()
        self.invocations = self.directory / "installer.jsonl"
        for name in ("bash", "dirname", "mkdir", "mktemp", "rm", "cp", "python3"):
            (self.bins / name).symlink_to(shutil.which(name))
        for name in ("install-herdr-agent-resume.sh", "install-upstream-tools.sh", "logging.sh",
                     "herdr-pi-session-hook.js"):
            path = self.directory / name
            shutil.copyfile(ROOT / "scripts" / name, path)
            path.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bins),
                        TMPDIR=str(self.tmp), TEST_LOG=str(self.log),
                        TEST_INVOCATIONS=str(self.invocations))
        for key in ("SKIP_HERDR", "SKIP_HERDR_AGENT_RESUME", "SKIP_CLAUDE_CODE",
                    "HERDR_APP_HOME", "XDG_CONFIG_HOME", "ZDOTDIR", "HC_TERMINAL_ID",
                    "HC_SCOPE", "HC_SESSION", "TEST_FETCH_FAIL", "TEST_BAD_REVISION",
                    "TEST_INSTALL_FAIL"):
            self.env.pop(key, None)
        for name in ("herdr-app", "hc", "fish"):
            self.mock(name, "exit 99\n")  # Presence only; must not be executed by the wrapper.
        self.mock("sudo", "exit 91\n")
        self.fixture = self.directory / "fixture.py"
        self.fixture.write_text('''import argparse, json, os
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("--home", required=True)
p.add_argument("--app-home", required=True)
for flag in ("--update", "--auto", "--no-adopt", "--uninstall"):
    p.add_argument(flag, action="store_true")
a = p.parse_args()
with open(os.environ["TEST_INVOCATIONS"], "a") as f:
    f.write(json.dumps(vars(a)) + "\\n")
assert os.environ["HERDR_APP_HOME"] == a.app_home
assert json.loads((Path(a.app_home) / "keys.json").read_text()) is not None
if os.environ.get("TEST_INSTALL_FAIL"):
    raise SystemExit(42)
if not a.uninstall:
    template = (Path(__file__).parent / "pi_extension.js").read_text()
    extension = Path(a.home) / ".pi/agent/extensions/herdr-agent-resume.js"
    extension.parent.mkdir(parents=True, exist_ok=True)
    extension.write_text(template.replace("__SCRIPT__", json.dumps(str(
        Path(a.app_home) / "mods/agent-resume/agent_resume.py"))))
''')
        self.env["TEST_FIXTURE"] = str(self.fixture)
        self.mock("git", '''directory=""
while [[ "$1" == -c || "$1" == -C ]]; do
  [[ "$1" != -C ]] || directory="$2"
  shift 2
done
case "$1" in
  init) mkdir -p "${@: -1}" ;;
  remote) [[ "$*" == "remote add origin https://github.com/mortenvp/herdr-agent-resume.git" ]] ;;
  fetch) [[ "${TEST_FETCH_FAIL:-}" != 1 ]] || exit 41 ;;
  checkout)
    mkdir -p "$directory/scripts"
    cp "$TEST_FIXTURE" "$directory/scripts/install.py"
    ;;
  rev-parse) printf '%s\\n' "${TEST_BAD_REVISION:-a62a3eeb9d2fc46f60490ecd44042b0a0b77cb28}" ;;
  *) exit 98 ;;
esac
''')

    def mock(self, name, body):
        path = self.bins / name
        path.write_text(f"#!{BASH}\nset -euo pipefail\n"
                        f'printf "%s\\n" "{name} $*" >> "$TEST_LOG"\n' + body)
        path.chmod(0o755)

    @property
    def app(self):
        return self.home / ".config/herdr-app"

    def run_script(self, *args, success=True, script="install-herdr-agent-resume.sh", **env):
        result = subprocess.run([BASH, str(self.directory / script), *args],
                                env=dict(self.env, **env), capture_output=True, text=True,
                                input="", start_new_session=True, timeout=15)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(self.tmp.iterdir()), [], "Temporary checkout not cleaned up")
        return result

    def installed(self):
        return [json.loads(line) for line in self.invocations.read_text().splitlines()]

    def test_skip_flags_make_no_changes(self):
        for key in ("SKIP_HERDR", "SKIP_HERDR_AGENT_RESUME"):
            self.run_script(**{key: "1"})
        self.assertEqual(self.log.read_text(), "")
        self.assertEqual(list(self.home.iterdir()), [])

    def test_fresh_install_fetches_pinned_fork_and_enables_auto_without_adoption(self):
        self.run_script()
        invocation = self.installed()[0]
        self.assertTrue(invocation["auto"])
        self.assertTrue(invocation["update"])
        self.assertTrue(invocation["no_adopt"])
        self.assertFalse(invocation["uninstall"])
        self.assertIn("https://github.com/mortenvp/herdr-agent-resume.git", self.log.read_text())
        self.assertIn(f"fetch --quiet --depth=1 origin {REVISION}", self.log.read_text())
        self.assertEqual(json.loads((self.app / "keys.json").read_text()), {})
        extension = self.home / ".pi/agent/extensions/herdr-agent-resume.js"
        expected = (ROOT / "scripts/herdr-pi-session-hook.js").read_text().replace(
            "__SCRIPT__", json.dumps(str(self.app / "mods/agent-resume/agent_resume.py")))
        self.assertEqual(extension.read_text(), expected)
        self.assertTrue((self.home / ".config/fish/conf.d").is_dir())
        self.assertNotIn("sudo ", self.log.read_text())
        self.assertNotIn("hc ", self.log.read_text())
        self.assertNotIn("herdr-app ", self.log.read_text())

    def test_rerun_preserves_existing_keys_and_refreshes_auto_mode(self):
        self.app.mkdir(parents=True)
        keys = self.app / "keys.json"
        original = '{"global": {"ctrl-a": "something"}}\n'
        keys.write_text(original)
        self.run_script()
        self.run_script()
        self.assertEqual(keys.read_text(), original)
        self.assertEqual(len(self.installed()), 2)
        self.assertTrue(all(i["auto"] and i["update"] for i in self.installed()))

    def test_commands_in_local_bin_are_found(self):
        local = self.home / ".local/bin"
        local.mkdir(parents=True)
        for name in ("herdr-app", "hc"):
            (self.bins / name).rename(local / name)
        self.run_script()

    def test_missing_herdr_stops_before_fetch(self):
        (self.bins / "hc").unlink()
        result = self.run_script(success=False)
        self.assertIn("run scripts/install-herdr.sh first", result.stderr)
        self.assertEqual(self.log.read_text(), "")

    def test_download_failure_does_not_run_installer(self):
        result = self.run_script(success=False, TEST_FETCH_FAIL="1")
        self.assertEqual(result.returncode, 41)
        self.assertFalse(self.invocations.exists())
        self.assertFalse(self.app.exists())

    def test_wrong_commit_does_not_run_installer(self):
        result = self.run_script(success=False, TEST_BAD_REVISION="bad")
        self.assertIn("Unexpected Herdr agent resume revision", result.stderr)
        self.assertFalse(self.invocations.exists())
        self.assertFalse(self.app.exists())

    def test_upstream_failure_propagates(self):
        result = self.run_script(success=False, TEST_INSTALL_FAIL="1")
        self.assertEqual(result.returncode, 42)
        self.assertNotIn("Auto resume enabled", result.stdout)

    def test_symlinked_config_is_refused_without_changing_it(self):
        target = self.home / "dotfiles-bashrc"
        target.write_text("# my shell configuration\n")
        link = self.home / ".bashrc"
        link.symlink_to(target)
        result = self.run_script(success=False)
        self.assertIn("Refusing to replace symlink", result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertEqual(target.read_text(), "# my shell configuration\n")
        self.assertFalse(self.invocations.exists())

    def test_unrelated_pi_extension_is_refused(self):
        extension = self.home / ".pi/agent/extensions/herdr-agent-resume.js"
        extension.parent.mkdir(parents=True)
        extension.write_text("// mine\n")
        result = self.run_script(success=False)
        self.assertIn("unrelated Pi extension", result.stderr)
        self.assertEqual(extension.read_text(), "// mine\n")
        self.assertFalse(self.invocations.exists())

    def test_known_pi_extension_can_be_updated(self):
        extension = self.home / ".pi/agent/extensions/herdr-agent-resume.js"
        extension.parent.mkdir(parents=True)
        extension.write_text("// herdr-agent-resume pi session hook\n")
        self.run_script()

    def test_missing_pi_template_stops_before_changing_configuration(self):
        (self.directory / "herdr-pi-session-hook.js").unlink()
        self.run_script(success=False)
        self.assertFalse(self.invocations.exists())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_app_home_overrides_and_xdg_config_home(self):
        for env, app in (({"XDG_CONFIG_HOME": str(self.home / "config")}, self.home / "config/herdr-app"),
                         ({"HERDR_APP_HOME": str(self.home / "custom app")}, self.home / "custom app")):
            with self.subTest(env=env):
                self.run_script(**env)
                self.assertEqual(self.installed()[-1]["app_home"], str(app))
                self.assertTrue((app / "keys.json").exists())

    def test_uninstall_does_not_enable_auto_or_adopt(self):
        (self.directory / "herdr-pi-session-hook.js").unlink()
        self.app.mkdir(parents=True)
        (self.app / "keys.json").write_text("{}")
        self.run_script("--uninstall")
        invocation = self.installed()[0]
        self.assertTrue(invocation["uninstall"])
        self.assertFalse(invocation["auto"])
        self.assertFalse(invocation["update"])
        self.assertFalse((self.home / ".pi").exists())

    def test_unknown_or_extra_arguments_are_rejected(self):
        self.run_script("--unknown", success=False)
        self.run_script("--uninstall", "extra", success=False)
        self.assertEqual(self.log.read_text(), "")

    def test_pipeline_runs_after_herdr_and_pi_and_respects_skip(self):
        for name in ("install-devbox", "install-uv", "install-claude-code", "install-herdr",
                     "install-blip-ai", "install-tailscale", "install-pi-dev",
                     "install-pi-agent-stuff", "install-playwright"):
            child = self.directory / f"{name}.sh"
            child.write_text(f'#!{BASH}\nprintf "step {name}\\n" >> "$TEST_LOG"\n')
            child.chmod(0o755)
        self.mock("curl", "exit 99\n")
        self.run_script(script="install-upstream-tools.sh", SKIP_HERDR="1")
        self.assertFalse(self.invocations.exists())
        self.log.write_text("")
        self.run_script(script="install-upstream-tools.sh")
        log = self.log.read_text()
        self.assertLess(log.index("step install-herdr"), log.index("git "))
        self.assertLess(log.index("step install-pi-agent-stuff"), log.index("git "))
        self.assertEqual(len(self.installed()), 1)


if __name__ == "__main__":
    unittest.main()
