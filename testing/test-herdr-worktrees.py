#!/usr/bin/env python3
"""Offline installer tests: disposable homes, mocked Herdr, no desktop changes."""

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODS = ("wt-worktree", "wt-menu", "wt-new-menu", "wt-tabs", "wt-spaces")
MANIFEST = ".install-arch-worktrees.json"


class InstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home with spaces"
        self.home.mkdir()
        self.repo = self.root / "repo"
        self.source = self.repo / "patches/herdr-worktrees"
        shutil.copytree(ROOT / "patches/herdr-worktrees", self.source)
        (self.repo / "scripts").mkdir()
        for name in ("herdr-worktrees.py", "install-herdr-worktrees.sh", "logging.sh"):
            shutil.copyfile(ROOT / "scripts" / name, self.repo / "scripts" / name)
        self.app = self.home / ".config/herdr-app"
        self.bins = self.root / "bin"
        self.bins.mkdir()
        self.log = self.root / "commands.jsonl"
        self.live = self.root / "live.json"
        self.live.write_text('{"layout":"main"}')
        self.env = dict(os.environ, HOME=str(self.home), PATH=f"{self.bins}:{os.defpath}",
                        TEST_LOG=str(self.log), TEST_LIVE=str(self.live))
        for key in ("HERDR_APP_HOME", "XDG_CONFIG_HOME", "SKIP_HERDR",
                    "SKIP_HERDR_WORKTREES", "TEST_RUNNING", "TEST_BAD_STATUS", "TEST_FAIL_CHECK"):
            self.env.pop(key, None)
        executable = self.bins / "herdr-app"
        executable.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
with open(os.environ["TEST_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
args = sys.argv[1:]
live = Path(os.environ["TEST_LIVE"])
if args == ["status"]:
    if os.environ.get("TEST_BAD_STATUS") or not os.environ.get("TEST_RUNNING"):
        raise SystemExit("injected status failure")
    print(live.read_text())
elif args[0] == "check":
    path = Path(args[1])
    assert (path / "main.js").exists()
    assert (path / "mod.json").exists()
    assert path.name.startswith("wt-")
    assert Path(os.environ["HERDR_APP_HOME"]).is_absolute()
    if os.environ.get("TEST_FAIL_CHECK") == path.name:
        raise SystemExit("injected check failure")
elif args[:2] == ["do", "layout.switch"]:
    live.write_text(json.dumps({"layout": json.loads(args[2])["name"]}))
else:
    raise SystemExit(f"Unexpected Herdr command: {args}")
''')
        executable.chmod(0o755)

    def run_installer(self, *args, success=True, shell=False, **env):
        script = self.repo / "scripts" / ("install-herdr-worktrees.sh" if shell else "herdr-worktrees.py")
        result = subprocess.run(["bash" if shell else sys.executable, str(script), *args],
                                env=dict(self.env, **env), capture_output=True, text=True,
                                timeout=15, start_new_session=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def snapshot(self):
        return {str(p.relative_to(self.app)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.app.rglob("*") if p.is_file()}

    def commands(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_fresh_install_selects_layout_and_keeps_shipped_mods(self):
        shipped = self.app / "mods/worktree/main.js"
        shipped.parent.mkdir(parents=True)
        shipped.write_text("shipped original")
        self.run_installer()
        self.assertEqual(shipped.read_text(), "shipped original")
        self.assertEqual(json.loads((self.app / "shared.json").read_text())["layout"], "wt")
        layout = json.loads((self.app / "layouts/wt.json").read_text())
        self.assertEqual(layout["terminal_menu"], "wt-menu")
        for mod in MODS:
            self.assertTrue((self.app / "mods" / mod / "main.js").is_file())
            self.assertTrue((self.app / "mods" / mod / "LICENSE").is_file())
        self.assertEqual(len([c for c in self.commands() if c[0] == "check"]), 5)
        # The installer never invokes git, hc, app.update or any terminal command.
        self.assertTrue(all(c[0] in ("status", "check") for c in self.commands()))

    def test_rerun_changes_no_files(self):
        self.run_installer()
        before = self.snapshot()
        self.run_installer()
        self.assertEqual(self.snapshot(), before)

    def test_stale_socket_allows_offline_install_and_uninstall(self):
        self.app.mkdir(parents=True)
        path = self.app / "herdr-app.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(path))
        original_socket = path.stat().st_ino
        shared = self.app / "shared.json"
        shared.write_text('{"layout":"main","untouched":true}')
        for args, layout in (((), "wt"), (("--uninstall",), "main")):
            result = self.run_installer(*args, TEST_BAD_STATUS="1")
            self.assertIn("socket is stale", result.stdout)
            self.assertEqual(json.loads(shared.read_text()),
                             {"layout": layout, "untouched": True})
            self.assertEqual(path.stat().st_ino, original_socket)

    def test_listening_socket_with_failed_status_does_not_write_state(self):
        self.app.mkdir(parents=True)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(self.app / "herdr-app.sock"))
            listener.listen()
            before = self.snapshot()
            result = self.run_installer(success=False, TEST_BAD_STATUS="1")
            self.assertIn("socket exists", result.stderr)
            self.assertIn("injected status failure", result.stderr)
            self.assertEqual(self.snapshot(), before)

    def test_offline_activation_preserves_other_shared_state_and_backs_up(self):
        self.app.mkdir(parents=True)
        shared = self.app / "shared.json"
        shared.write_text('{"layout":"main","unrelated":{"keep":true}}')
        original = shared.read_bytes()
        self.run_installer()
        self.assertEqual(json.loads(shared.read_text())["unrelated"], {"keep": True})
        backups = list((self.app / "backups/wt-worktrees").glob("*/shared.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)

    def test_running_app_uses_ipc_and_never_writes_shared_json(self):
        self.app.mkdir(parents=True)
        shared = self.app / "shared.json"
        shared.write_text('{"layout":"main","untouched":true}')
        before = shared.read_bytes()
        self.run_installer(TEST_RUNNING="1")
        self.assertEqual(shared.read_bytes(), before)
        self.assertEqual(json.loads(self.live.read_text())["layout"], "wt")
        self.run_installer("--uninstall", TEST_RUNNING="1")
        self.assertEqual(json.loads(self.live.read_text())["layout"], "main")
        self.assertEqual(shared.read_bytes(), before)

    def test_updated_owned_templates_are_backed_up(self):
        self.run_installer()
        relative = "mods/wt-menu/main.js"
        original = (self.app / relative).read_bytes()
        with (self.source / relative).open("a") as stream:
            stream.write("\n// reviewed update\n")
        self.run_installer()
        self.assertTrue((self.app / relative).read_text().endswith("// reviewed update\n"))
        backups = list((self.app / "backups/wt-worktrees").glob(f"*/{relative}"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)

    def test_edited_owned_files_block_install_and_uninstall(self):
        self.run_installer()
        path = self.app / "mods/wt-worktree/main.js"
        path.write_text("my edited mod")
        before = self.snapshot()
        for args in ((), ("--uninstall",)):
            result = self.run_installer(*args, success=False)
            self.assertIn("edited file", result.stderr)
            self.assertEqual(self.snapshot(), before)

    def test_conflicting_unowned_file_is_not_overwritten(self):
        path = self.app / "layouts/wt.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"my":"layout"}')
        before = self.snapshot()
        self.assertIn("unrelated file", self.run_installer(success=False).stderr)
        self.assertEqual(self.snapshot(), before)

    def test_failed_check_installs_nothing(self):
        self.run_installer(success=False, TEST_FAIL_CHECK="wt-tabs")
        self.assertFalse(self.app.exists())
        self.assertEqual(json.loads(self.live.read_text())["layout"], "main")

    def test_socket_with_failed_status_does_not_write_state(self):
        self.app.mkdir(parents=True)
        (self.app / "herdr-app.sock").touch()
        before = self.snapshot()
        result = self.run_installer(success=False, TEST_BAD_STATUS="1")
        self.assertIn("socket exists", result.stderr)
        self.assertIn("injected status failure", result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_symlink_targets_are_refused(self):
        for relative in ("mods", "mods/wt-worktree", "layouts", "shared.json", MANIFEST):
            with self.subTest(relative=relative):
                shutil.rmtree(self.app, ignore_errors=True)
                outside = self.root / "outside"
                outside.mkdir(exist_ok=True)
                target = self.app / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(outside)
                result = self.run_installer(success=False)
                self.assertIn("symlink", result.stderr.lower())
                self.assertEqual(list(outside.iterdir()), [])

    def test_custom_config_roots(self):
        for overrides, target in (({"XDG_CONFIG_HOME": str(self.root / "xdg")}, self.root / "xdg/herdr-app"),
                                  ({"HERDR_APP_HOME": str(self.root / "custom")}, self.root / "custom")):
            with self.subTest(overrides=overrides):
                self.run_installer(**overrides)
                self.assertTrue((target / "mods/wt-worktree/main.js").exists())
                self.assertFalse(self.app.exists())

    def test_uninstall_leaves_worktrees_state_and_unrelated_files_alone(self):
        self.run_installer()
        extra = self.app / "mods/wt-menu/notes.txt"
        extra.write_text("mine")
        outside = self.home / "project.worktrees/branch/keep.txt"
        outside.parent.mkdir(parents=True)
        outside.write_text("working tree")
        self.run_installer("--uninstall")
        self.assertFalse((self.app / MANIFEST).exists())
        self.assertFalse((self.app / "layouts/wt.json").exists())
        self.assertFalse((self.app / "mods/wt-menu/main.js").exists())
        self.assertEqual(extra.read_text(), "mine")
        self.assertEqual(outside.read_text(), "working tree")
        self.assertEqual(json.loads((self.app / "shared.json").read_text())["layout"], "main")
        self.run_installer("--uninstall")

    def test_skip_flags_do_nothing(self):
        for flag in ("SKIP_HERDR", "SKIP_HERDR_WORKTREES"):
            self.run_installer(shell=True, **{flag: "1"})
        self.assertFalse(self.log.exists())
        self.assertFalse(self.app.exists())

    @unittest.skipIf(os.geteuid() == 0, "Shell wrapper must run as a normal user")
    def test_shell_wrapper_runs_installer(self):
        self.run_installer(shell=True)
        self.assertTrue((self.app / MANIFEST).exists())

    def test_pipeline_includes_step(self):
        pipeline = (ROOT / "scripts/install-upstream-tools.sh").read_text()
        self.assertLess(pipeline.index('"$SCRIPT_DIR/install-herdr.sh"'),
                        pipeline.index('"$SCRIPT_DIR/install-herdr-worktrees.sh"'))


if __name__ == "__main__":
    unittest.main()
