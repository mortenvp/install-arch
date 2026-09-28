#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "questionary>=2,<3",
#     "rich>=13.9,<15",
# ]
# ///
"""Exercise wt cleanup with disposable local Git repositories; no network needed."""

import importlib.machinery
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader("wt_ui", str(ROOT / "bin/wt-ui"))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
wt = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = wt
with patch.object(sys, "dont_write_bytecode", True):
    LOADER.exec_module(wt)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        env.update(
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_CONFIG_NOSYSTEM="1",
            GIT_TERMINAL_PROMPT="0",
            GIT_ALLOW_PROTOCOL="file",
            GIT_AUTHOR_NAME="Test",
            GIT_AUTHOR_EMAIL="test@example.invalid",
            GIT_COMMITTER_NAME="Test",
            GIT_COMMITTER_EMAIL="test@example.invalid",
        )
        self.enterContext(patch.dict(os.environ, env, clear=True))
        self.output = io.StringIO()
        self.enterContext(
            patch.object(wt, "console", Console(file=self.output, width=200))
        )
        self.repo = self.root / "main repo"
        self.remote = self.root / "remote.git"
        self.git("init", "--initial-branch=main", str(self.repo), cwd=self.root)
        (self.repo / "tracked").write_text("initial\n")
        self.git("add", ".")
        self.git("commit", "-m", "initial")
        self.git("init", "--bare", "--initial-branch=main", str(self.remote))
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "-u", "origin", "main")
        self.git("remote", "set-head", "origin", "--auto")

    def git(self, *args, cwd=None):
        return subprocess.run(
            ["git", *args],
            cwd=cwd or self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def worktree(self, branch="feature", *, publish=False):
        path = self.root / "work trees" / branch
        self.git("worktree", "add", "-b", branch, str(path), "main")
        if publish:
            self.git("push", "-u", "origin", branch, cwd=path)
        return path

    def commit(self, path):
        (path / "tracked").write_text("feature change\n")
        self.git("add", ".", cwd=path)
        self.git("commit", "-m", "feature", cwd=path)
        return self.git("rev-parse", "HEAD", cwd=path)

    def candidates(self):
        return wt.cleanup_candidates(self.repo, wt.list_worktrees(self.repo))

    def cleanup(self, *, select=None):
        with (
            patch.object(
                wt,
                "select_cleanup_candidates",
                side_effect=select or (lambda items: items),
            ),
            patch.object(
                wt, "confirm", side_effect=AssertionError("cleanup must not confirm")
            ) as prompt,
        ):
            result = wt.cleanup_worktrees(self.repo)
        prompt.assert_not_called()
        return result, prompt

    @contextmanager
    def prompt_input(self, keys):
        with (
            create_pipe_input() as pipe,
            create_app_session(input=pipe),
            patch.object(wt, "prompt_output", DummyOutput()),
        ):
            pipe.send_text(keys)
            yield

    def test_clean_worktree_and_merged_reason(self):
        path = self.worktree(publish=True)
        self.commit(path)
        self.git("push", cwd=path)
        self.git("merge", "--ff-only", "feature")
        self.git("push")
        (candidate,) = self.candidates()
        self.assertEqual(candidate.worktree.path, path)
        self.assertIn("merged into origin/main", candidate.reason)
        self.assertIn("clean", candidate.reason)
        self.assertIn("0 unpushed commit(s)", candidate.reason)

    def test_clean_unmerged_commits_are_not_called_merged(self):
        self.worktree(publish=True)
        self.commit(self.root / "work trees/feature")
        (candidate,) = self.candidates()
        self.assertIn("1 unpushed commit(s)", candidate.reason)
        self.assertNotIn("merged into", candidate.reason)

    def test_cleanup_fetches_and_prunes_before_suggesting(self):
        path = self.worktree(publish=True)
        head = self.commit(path)
        self.git("push", cwd=path)
        # Simulate a merge/deletion by somebody else, leaving tracking refs stale.
        self.git("--git-dir", str(self.remote), "update-ref", "refs/heads/main", head)
        self.git(
            "--git-dir", str(self.remote), "update-ref", "-d", "refs/heads/feature"
        )
        seen = []
        self.cleanup(select=lambda items: seen.extend(items) or [])
        self.assertIn("merged into origin/main", seen[0].reason)
        self.assertIn("upstream origin/feature gone", seen[0].reason)
        self.assertTrue(path.exists())

    def test_gone_upstream_is_not_proof_of_merge(self):
        path = self.worktree(publish=True)
        self.commit(path)
        self.git("push", cwd=path)
        self.git("push", "origin", "--delete", "feature")
        (candidate,) = self.candidates()
        self.assertIn("gone (not proof of merge)", candidate.reason)
        self.assertNotIn("merged into", candidate.reason)

    def test_unknown_remote_default_does_not_prevent_cleanup(self):
        path = self.worktree(publish=True)
        self.git("symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
        (candidate,) = self.candidates()
        self.assertNotIn("merged into", candidate.reason)
        self.assertIn("clean", candidate.reason)
        self.cleanup()
        self.assertFalse(path.exists())

    def test_merge_label_uses_upstream_remote_not_an_unrelated_remote(self):
        path = self.worktree(publish=True)
        head = self.commit(path)
        self.git("remote", "add", "other", str(self.remote))
        self.git("update-ref", "refs/remotes/other/main", head)
        self.git("symbolic-ref", "refs/remotes/other/HEAD", "refs/remotes/other/main")
        (candidate,) = self.candidates()
        self.assertNotIn("merged into", candidate.reason)
        self.git("branch", "--unset-upstream", "feature")
        (candidate,) = self.candidates()
        self.assertIn("merged into other/main", candidate.reason)

    def test_skips_main_locked_detached_and_dirty(self):
        clean = self.worktree("clean")
        for branch in ("modified", "staged", "untracked"):
            path = self.worktree(branch)
            (path / ("new" if branch == "untracked" else "tracked")).write_text(
                "dirty\n"
            )
            if branch == "staged":
                self.git("add", ".", cwd=path)
            # A user's status preferences must not hide untracked work.
            self.git("config", "status.showUntrackedFiles", "no", cwd=path)
        for branch, reason in (("locked", []), ("locked-reason", ["--reason", "keep"])):
            path = self.worktree(branch)
            self.git("worktree", "lock", *reason, str(path))
        detached = self.root / "detached"
        self.git("worktree", "add", "--detach", str(detached), "main")
        self.assertEqual([item.worktree.path for item in self.candidates()], [clean])

    def test_dirty_submodule_is_skipped_even_when_configured_ignored(self):
        self.git(
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(self.remote),
            "sub",
        )
        self.git("commit", "-am", "add submodule")
        path = self.worktree()
        self.git("submodule", "update", "--init", cwd=path)
        self.git("config", "submodule.sub.ignore", "all", cwd=path)
        (path / "sub/untracked").write_text("keep\n")
        self.assertEqual(self.candidates(), [])

    def test_no_remotes_or_upstream_is_supported(self):
        path = self.worktree()
        self.commit(path)
        self.git("remote", "remove", "origin")
        (candidate,) = self.candidates()
        self.assertIn("no remote upstream", candidate.reason)
        self.cleanup()
        self.assertFalse(path.exists())
        self.assertTrue(wt.local_branch_exists(self.repo, "feature"))

    def test_cleanup_keeps_local_and_remote_branches_and_unpushed_commits(self):
        path = self.worktree(publish=True)
        head = self.commit(path)
        remote_head = self.git("rev-parse", "origin/feature")
        _, prompt = self.cleanup()
        prompt.assert_not_called()
        self.assertFalse(path.exists())
        self.assertEqual(self.git("rev-parse", "feature"), head)
        self.assertEqual(
            self.git("--git-dir", str(self.remote), "rev-parse", "feature"), remote_head
        )
        # Repeating cleanup with nothing left is a harmless no-op.
        with patch.object(wt, "select_cleanup_candidates") as select:
            wt.cleanup_worktrees(self.repo)
        select.assert_not_called()

    def test_missing_directory_registration_is_removed_without_force(self):
        path = self.worktree()
        shutil.rmtree(path)
        (candidate,) = self.candidates()
        self.assertIn("directory missing", candidate.reason)
        self.cleanup()
        self.assertEqual(len(wt.list_worktrees(self.repo)), 1)
        self.assertTrue(wt.local_branch_exists(self.repo, "feature"))

    def test_cleanup_handles_cancelled_or_empty_selector_results(self):
        path = self.worktree()
        for answer in (None, []):
            _, prompt = self.cleanup(select=lambda items, answer=answer: answer)
            prompt.assert_not_called()
            self.assertTrue(path.exists())

    def test_only_selected_worktrees_are_removed(self):
        first = self.worktree("first")
        second = self.worktree("second")
        self.cleanup(
            select=lambda items: [item for item in items if item.worktree.path == first]
        )
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())

    def test_rechecks_dirty_lock_and_head_after_selection(self):
        for change in ("dirty", "locked", "commit"):
            with self.subTest(change=change):
                path = self.worktree(change)

                def select(items, path=path, change=change):
                    selected = [item for item in items if item.worktree.path == path]
                    if change == "dirty":
                        (path / "new").write_text("keep\n")
                    elif change == "locked":
                        self.git("worktree", "lock", str(path))
                    else:
                        self.commit(path)
                    return selected

                self.cleanup(select=select)
                self.assertTrue(path.exists())

    def ignored_worktree(self):
        (self.repo / ".gitignore").write_text("build/\nignored\n")
        self.git("add", ".gitignore")
        self.git("commit", "-m", "ignore files")
        path = self.worktree()
        (path / "build").mkdir()
        (path / "build/output").write_text("build output\n")
        (path / "ignored").write_text("ignored output\n")
        return path

    def test_ignored_files_are_eligible_with_warning_but_cancel_keeps_them(self):
        path = self.ignored_worktree()
        self.assertFalse(wt.worktree_is_dirty(path))
        (candidate,) = self.candidates()
        self.assertEqual(candidate.worktree.path, path)
        self.assertIn("clean", candidate.reason)
        self.assertIn("ignored files will also be deleted", candidate.reason)
        for answer in (None, []):
            self.cleanup(select=lambda items, answer=answer: answer)
            self.assertEqual((path / "ignored").read_text(), "ignored output\n")
            self.assertTrue((path / "build/output").exists())

    def test_selected_cleanup_removes_ignored_files_without_confirmation_or_force(self):
        path = self.ignored_worktree()
        with patch.object(wt, "run_git", wraps=wt.run_git) as run_git:
            self.cleanup()
        run_git.assert_any_call("worktree", "remove", "--", str(path), cwd=self.repo)
        self.assertFalse(any("--force" in call.args for call in run_git.call_args_list))
        self.assertFalse(path.exists())
        self.assertTrue(wt.local_branch_exists(self.repo, "feature"))

    def test_ignored_files_do_not_hide_real_uncommitted_work(self):
        path = self.ignored_worktree()
        for filename in ("tracked", "untracked"):
            with self.subTest(filename=filename):
                (path / filename).write_text("keep\n")
                self.assertEqual(self.candidates(), [])
                self.cleanup()
                self.assertEqual((path / filename).read_text(), "keep\n")
                self.git("restore", "tracked", cwd=path)
        self.assertIn("uncommitted changes or untracked files", self.output.getvalue())

    def test_rechecks_real_changes_in_worktree_with_ignored_files(self):
        path = self.ignored_worktree()

        def select(items):
            self.assertEqual(len(items), 1)
            (path / "tracked").write_text("new work\n")
            return items

        self.cleanup(select=select)
        self.assertEqual((path / "tracked").read_text(), "new work\n")
        self.assertTrue((path / "build/output").exists())

    def test_fetch_failure_aborts_before_selection(self):
        path = self.worktree()
        self.git("remote", "set-url", "origin", str(self.root / "nonexistent"))
        with (
            patch.object(wt, "select_cleanup_candidates") as select,
            self.assertRaises(wt.WorktreeError),
        ):
            wt.cleanup_worktrees(self.repo)
        select.assert_not_called()
        self.assertTrue(path.exists())

    def test_current_worktree_moves_to_main_even_if_later_removal_fails(self):
        path = self.worktree("current")
        other = self.worktree("other")
        (path / "subdirectory").mkdir()
        previous = Path.cwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(path / "subdirectory")
        original_run_git = wt.run_git

        def run_git(*args, **kwargs):
            if args[:2] == ("worktree", "remove") and args[-1] == str(other):
                raise wt.WorktreeError("simulated removal failure")
            return original_run_git(*args, **kwargs)

        with patch.object(wt, "run_git", side_effect=run_git):
            destination, _ = self.cleanup()
        self.assertEqual(destination, self.repo)
        self.assertFalse(path.exists())
        self.assertTrue(other.exists())
        os.chdir(destination)

    def test_selector_does_not_preselect_candidates(self):
        self.worktree()
        candidates = self.candidates()
        with (
            patch.object(wt.questionary, "checkbox") as checkbox,
            patch.object(wt, "ask", return_value=None),
        ):
            wt.select_cleanup_candidates(candidates)
        choices = checkbox.call_args.kwargs["choices"]
        self.assertIn(
            "enter to delete checked or highlighted",
            checkbox.call_args.kwargs["instruction"],
        )
        self.assertEqual([choice.value for choice in choices], candidates)
        self.assertTrue(all(not choice.checked for choice in choices))

    def test_selector_enter_uses_highlighted_worktree_when_none_checked(self):
        self.worktree("first")
        self.worktree("second")
        candidates = self.candidates()
        for keys, index in (("\r", 0), ("\x1b[B\r", 1), ("\x1b[B\x1b[A\r", 0)):
            with self.subTest(keys=repr(keys)), self.prompt_input(keys):
                self.assertEqual(
                    wt.select_cleanup_candidates(candidates), [candidates[index]]
                )

    def test_selector_checked_worktrees_take_precedence_over_highlight(self):
        for branch in ("first", "second", "third"):
            self.worktree(branch)
        candidates = self.candidates()
        # Check first and third, but leave the pointer on the unchecked second.
        with self.prompt_input(" \x1b[B\x1b[B \x1b[A\r"):
            self.assertEqual(
                wt.select_cleanup_candidates(candidates), [candidates[0], candidates[2]]
            )

    def test_selector_cancellation_never_falls_back_to_highlighted_worktree(self):
        self.worktree()
        candidates = self.candidates()
        for keys in ("\x03", " \x03"):
            with self.subTest(keys=repr(keys)), self.prompt_input(keys):
                self.assertIsNone(wt.select_cleanup_candidates(candidates))

    def test_enter_removes_highlighted_worktree_without_confirmation(self):
        path = self.ignored_worktree()
        other = self.worktree("keep")
        with (
            self.prompt_input("\r"),
            patch.object(
                wt, "confirm", side_effect=AssertionError("unexpected confirmation")
            ),
        ):
            wt.cleanup_worktrees(self.repo)
        self.assertFalse(path.exists())
        self.assertTrue(other.exists())
        self.assertTrue(wt.local_branch_exists(self.repo, "feature"))

    def test_ctrl_c_cancels_cleanup_without_removing_worktrees(self):
        path = self.ignored_worktree()
        with self.prompt_input("\x03"):
            wt.cleanup_worktrees(self.repo)
        self.assertTrue(path.exists())
        self.assertTrue((path / "build/output").exists())

    def test_cli_aliases_and_menu_keep_stdout_reserved_for_destination(self):
        for args in (["cleanup"], ["prune"], []):
            with (
                patch.object(wt, "find_repository", return_value=self.repo),
                patch.object(wt, "select_action", return_value="cleanup") as menu,
                patch.object(
                    wt, "cleanup_worktrees", return_value=self.repo
                ) as cleanup,
                patch("sys.stdout", new_callable=io.StringIO) as stdout,
            ):
                self.assertEqual(wt.main(args), 0)
                self.assertEqual(stdout.getvalue(), f"{self.repo}\n")
                cleanup.assert_called_once_with(self.repo)
                self.assertEqual(menu.call_count, 0 if args else 1)
        with (
            patch.object(wt, "find_repository", return_value=self.repo),
            patch.object(wt, "cleanup_worktrees", return_value=None),
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            self.assertEqual(wt.main(["cleanup"]), 0)
            self.assertEqual(stdout.getvalue(), "")
        with patch.object(wt, "find_repository") as find:
            self.assertEqual(wt.main(["cleanup", "--force"]), 2)
            self.assertEqual(wt.main(["--help"]), 0)
        find.assert_not_called()


if __name__ == "__main__":
    unittest.main()
