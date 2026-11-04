#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "questionary>=2,<3",
#     "rich>=13.9,<15",
# ]
# ///
"""Test CI merge polling with mocked GitHub/Git calls; never merge a real PR."""

import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader(
    "ci_merge_agent", str(ROOT / "bin/ci-merge-agent")
)
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
ci = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ci
with patch.object(sys, "dont_write_bytecode", True):
    LOADER.exec_module(ci)


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path("/unused-test-repository")
        self.pr = ci.PullRequest(
            number=42,
            title="Example change",
            url="https://github.com/example/repository/pull/42",
            state="OPEN",
            is_draft=False,
            base_branch="main",
            head_branch="feature",
            head_sha="a" * 40,
            mergeable="MERGEABLE",
            merge_state="CLEAN",
            review_decision="APPROVED",
        )
        self.local = ci.LocalState("feature", self.pr.head_sha, "")
        self.pending = [ci.Check("tests", "CI", "QUEUED", "pending", "")]
        self.passing = [ci.Check("tests", "CI", "SUCCESS", "pass", "")]
        self.failed = [ci.Check("tests", "CI", "FAILURE", "fail", "")]
        self.output = io.StringIO()
        self.stdout = io.StringIO()
        self.enterContext(patch.object(sys, "stdout", self.stdout))
        self.stdin_tty = self.enterContext(
            patch.object(sys.stdin, "isatty", return_value=True)
        )
        self.stderr_tty = self.enterContext(
            patch.object(sys.stderr, "isatty", return_value=True)
        )
        self.mock("console", Console(file=self.output, width=160))
        self.status = self.enterContext(
            patch.object(ci.console, "status", return_value=nullcontext())
        )
        self.live = self.mock("Live")
        self.skill_sync = self.mock("sync_agent_skills", return_value=[])
        self.enterContext(patch.dict(os.environ))
        os.environ.pop("SKIP_CI_MERGE_SKILLS", None)
        # Guard against accidental real Git/GitHub commands, even if a mock is missing.
        self.enterContext(
            patch.object(
                ci.subprocess,
                "run",
                side_effect=AssertionError("external commands are forbidden"),
            )
        )
        self.mock("find_repository", return_value=self.repo)
        self.mock("require_gh_auth")
        self.get_pr = self.mock("get_pull_request", return_value=self.pr)
        self.get_local = self.mock("get_local_state", return_value=self.local)
        self.mock("gh_json", return_value={"squashMergeAllowed": True})
        self.get_checks = self.mock("get_checks", return_value=self.passing)
        self.confirm = self.mock("confirm_merge", return_value=True)
        self.merge = self.mock("merge_pull_request", return_value="b" * 40)
        self.elapsed = 0
        self.enterContext(
            patch.object(ci.time, "monotonic", side_effect=lambda: self.elapsed)
        )
        self.sleep = self.enterContext(
            patch.object(ci.time, "sleep", side_effect=self.advance_clock)
        )

    def mock(self, name, *args, **kwargs):
        return self.enterContext(patch.object(ci, name, *args, **kwargs))

    def advance_clock(self, seconds):
        self.elapsed += seconds

    def run_failure(self, message, *, exit_code=1):
        self.output.seek(0)
        self.output.truncate()
        self.assertEqual(
            ci.main(["--interactive", "42"]), exit_code, self.output.getvalue()
        )
        self.assertIn(message, self.output.getvalue())
        self.merge.assert_not_called()

    def run_agent(self, *arguments, exit_code=0):
        self.stdout.seek(0)
        self.stdout.truncate()
        result = ci.main(["--yes", *arguments])
        self.assertEqual(result, exit_code, self.stdout.getvalue())
        payload = json.loads(self.stdout.getvalue())
        self.assertEqual(payload["exit_code"], exit_code)
        self.confirm.assert_not_called()
        self.live.assert_not_called()
        self.status.assert_not_called()
        return payload

    def test_existing_successful_checks_merge_without_delay(self):
        self.assertEqual(ci.main(["--interactive", "42"]), 0, self.output.getvalue())
        self.sleep.assert_not_called()
        self.merge.assert_called_once()
        self.assertEqual(self.merge.call_args.args[1].pull_request, self.pr)

    def test_delayed_checks_appear_then_complete(self):
        self.get_checks.side_effect = [
            [],  # Inspection before confirmation.
            [],  # First poll: GitHub still has not reported any checks.
            self.pending,
            self.passing,
            self.passing,  # Final revalidation must still run.
        ]
        self.assertEqual(ci.main(["--interactive", "42"]), 0, self.output.getvalue())
        self.assertEqual(self.elapsed, 2 * ci.POLL_INTERVAL_SECONDS)
        self.assertEqual(self.get_checks.call_count, 5)
        self.assertEqual(self.get_pr.call_count, 5)
        self.assertEqual(self.get_local.call_count, 5)
        self.confirm.assert_called_once()
        self.assertEqual(self.confirm.call_args.args[0].checks, [])
        self.assertIn("No checks reported yet", self.output.getvalue())
        self.merge.assert_called_once()

    def test_delayed_checks_can_already_be_complete_when_reported(self):
        self.get_checks.side_effect = [[], [], self.passing, self.passing]
        self.assertEqual(ci.main(["--interactive", "42"]), 0, self.output.getvalue())
        self.assertEqual(self.elapsed, ci.POLL_INTERVAL_SECONDS)
        self.merge.assert_called_once()

    def test_no_checks_eventually_times_out_without_merging(self):
        self.get_checks.return_value = []
        self.run_failure(
            f"no CI checks were reported within {ci.CHECK_DISCOVERY_TIMEOUT_SECONDS}s",
            exit_code=124,
        )
        self.assertEqual(self.elapsed, ci.CHECK_DISCOVERY_TIMEOUT_SECONDS)
        self.confirm.assert_called_once()

    def test_discovery_timeout_does_not_limit_running_checks(self):
        self.mock("CHECK_DISCOVERY_TIMEOUT_SECONDS", ci.POLL_INTERVAL_SECONDS)
        self.get_checks.side_effect = [
            [],
            [],
            self.pending,
            self.pending,
            self.passing,
            self.passing,
        ]
        self.assertEqual(ci.main(["--interactive", "42"]), 0, self.output.getvalue())
        self.assertGreater(self.elapsed, ci.CHECK_DISCOVERY_TIMEOUT_SECONDS)
        self.merge.assert_called_once()

    def test_initial_failed_checks_still_stop_before_confirmation(self):
        self.get_checks.return_value = self.failed
        self.run_failure("CI already has blocking checks: tests")
        self.confirm.assert_not_called()
        self.sleep.assert_not_called()

    def test_delayed_failed_checks_stop_waiting(self):
        self.get_checks.side_effect = [[], [], self.failed]
        self.run_failure("CI has blocking checks: tests")
        self.assertEqual(self.elapsed, ci.POLL_INTERVAL_SECONDS)

    def test_existing_checks_disappearing_still_fail_immediately(self):
        self.get_checks.side_effect = [self.pending, []]
        self.run_failure("CI checks disappeared while waiting")
        self.sleep.assert_not_called()

    def test_newly_reported_checks_disappearing_do_not_restart_grace_period(self):
        self.get_checks.side_effect = [[], self.pending, []]
        self.run_failure("CI checks disappeared while waiting")
        self.assertEqual(self.elapsed, ci.POLL_INTERVAL_SECONDS)

    def test_pr_changes_during_discovery_stop_waiting(self):
        changes = [
            ({"head_sha": "c" * 40}, "head SHA changed"),
            ({"head_branch": "other"}, "base or head branch changed"),
            ({"base_branch": "other"}, "base or head branch changed"),
            ({"state": "CLOSED"}, "no longer open"),
            ({"is_draft": True}, "became a draft"),
        ]
        self.get_checks.return_value = []
        for fields, message in changes:
            with self.subTest(fields=fields):
                self.get_pr.side_effect = [self.pr, replace(self.pr, **fields)]
                self.run_failure(message)
        self.sleep.assert_not_called()

    def test_local_changes_during_discovery_stop_waiting(self):
        changes = [
            ({"status": "?? untracked"}, "working tree has"),
            ({"head_sha": "c" * 40}, "does not match the pushed PR head"),
            ({"branch": "other"}, "current branch is other"),
            ({"branch": ""}, "HEAD is detached"),
        ]
        self.get_checks.return_value = []
        for fields, message in changes:
            with self.subTest(fields=fields):
                self.get_local.side_effect = [
                    self.local,
                    replace(self.local, **fields),
                ]
                self.run_failure(message)
        self.sleep.assert_not_called()

    def test_final_revalidation_still_rejects_missing_or_failed_checks(self):
        for checks, message in [
            ([], "CI is no longer fully complete"),
            (self.failed, "CI changed before merging; blocking checks: tests"),
            (self.pending, "CI is no longer fully complete"),
        ]:
            with self.subTest(checks=checks):
                self.get_checks.side_effect = [[], self.passing, checks]
                self.run_failure(message)

    def test_final_revalidation_still_rejects_changed_head(self):
        self.get_checks.side_effect = [[], self.passing]
        self.get_pr.side_effect = [
            self.pr,
            self.pr,
            replace(self.pr, head_sha="c" * 40),
        ]
        self.run_failure("head SHA changed")

    def test_final_revalidation_still_rejects_review_blockers(self):
        self.get_checks.side_effect = [[], self.passing, self.passing]
        self.get_pr.side_effect = [
            self.pr,
            self.pr,
            replace(self.pr, review_decision="CHANGES_REQUESTED"),
        ]
        self.run_failure("reviews block merging")

    def test_github_errors_are_not_retried_as_missing_checks(self):
        self.get_checks.side_effect = [[], ci.MergeError("GitHub unavailable")]
        self.run_failure("GitHub unavailable")
        self.sleep.assert_not_called()

    def test_declining_confirmation_does_not_start_discovery(self):
        self.get_checks.return_value = []
        self.confirm.return_value = False
        self.assertEqual(ci.main(["--interactive", "42"]), 3)
        self.get_checks.assert_called_once()
        self.sleep.assert_not_called()
        self.merge.assert_not_called()

    def test_ctrl_c_during_discovery_does_not_merge(self):
        self.get_checks.return_value = []
        self.sleep.side_effect = KeyboardInterrupt
        self.assertEqual(ci.main(["--interactive", "42"]), 130)
        self.merge.assert_not_called()

    def test_empty_checks_display_explains_waiting(self):
        ci.console.print(ci.checks_table([], next_poll=10))
        self.assertIn("Waiting for GitHub to report CI checks", self.output.getvalue())
        self.assertIn("Refreshing in 10s", self.output.getvalue())

    def test_agent_merges_without_terminal_and_emits_one_json_result(self):
        self.stdin_tty.return_value = False
        self.stderr_tty.return_value = False
        result = self.run_agent("42", "--timeout", "20")
        self.assertEqual(
            result,
            {
                "status": "merged",
                "exit_code": 0,
                "message": "PR #42 was squash-merged",
                "pr_number": 42,
                "pr_url": self.pr.url,
                "head_sha": self.pr.head_sha,
                "merge_commit": "b" * 40,
                "merge_attempted": True,
            },
        )
        self.merge.assert_called_once()

    def test_agent_accepts_url_and_inferred_target(self):
        for arguments, target in [((self.pr.url,), self.pr.url), ((), None)]:
            with self.subTest(target=target):
                self.get_pr.reset_mock()
                self.run_agent(*arguments)
                self.assertEqual(
                    self.get_pr.call_args_list[0].args, (self.repo, target)
                )

    def test_noninteractive_invocation_requires_explicit_authorization(self):
        for stdin_tty, stderr_tty in [(False, True), (True, False), (False, False)]:
            with self.subTest(stdin=stdin_tty, stderr=stderr_tty):
                self.stdin_tty.return_value = stdin_tty
                self.stderr_tty.return_value = stderr_tty
                self.assertEqual(ci.main(["--interactive", "42"]), 2)
        self.confirm.assert_not_called()
        ci.find_repository.assert_not_called()
        self.merge.assert_not_called()

    def test_agent_default_never_authorizes_merge_even_in_terminal(self):
        self.assertEqual(ci.main(["42"]), 2)
        result = json.loads(self.stdout.getvalue())
        self.assertEqual(result["status"], "error")
        self.assertIn("requires --yes", result["message"])
        self.assertFalse(result["merge_attempted"])
        self.assertIsNone(result["pr_url"])
        ci.find_repository.assert_not_called()
        self.confirm.assert_not_called()
        self.merge.assert_not_called()

    def test_yes_without_json_supports_headless_human_readable_output(self):
        self.stdin_tty.return_value = False
        self.stderr_tty.return_value = False
        self.assertEqual(ci.main(["--interactive", "42", "-y"]), 0)
        self.assertIn("was squash-merged", self.output.getvalue())
        self.assertEqual(self.stdout.getvalue(), "")
        self.confirm.assert_not_called()
        self.live.assert_not_called()
        self.status.assert_not_called()

    def test_json_flag_overrides_interactive_mode(self):
        result = self.run_agent("--interactive", "42", "--json")
        self.assertEqual(result["status"], "merged")

    def test_option_like_target_after_separator_does_not_change_output_mode(self):
        result = self.run_agent("--", "--interactive", exit_code=2)
        self.assertEqual(result["status"], "error")
        self.merge.assert_not_called()

    def test_agent_rejects_invalid_options_before_inspection(self):
        cases = [
            ("--timeout", "0"),
            ("--timeout", "-1"),
            ("--timeout", "1.5"),
            ("--timeout", "abc"),
            ("--timeout",),
            ("42", "43"),
            ("not-a-pr",),
            ("--force",),
            ("--tim", "5"),
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result = self.run_agent(*arguments, exit_code=2)
                self.assertEqual(result["status"], "error")
                self.assertFalse(result["merge_attempted"])
        ci.find_repository.assert_not_called()
        self.merge.assert_not_called()

    def test_json_help_does_not_require_authorization_or_repository(self):
        self.assertEqual(ci.main(["--help"]), 0)
        result = json.loads(self.stdout.getvalue())
        self.assertEqual(result["status"], "help")
        self.assertIn("ci-merge-agent", result["message"])
        self.assertIn("--timeout", result["message"])
        self.assertIn("--yes", result["message"])
        self.assertFalse(result["merge_attempted"])
        ci.find_repository.assert_not_called()

    def test_agent_refreshes_skills_before_merging(self):
        def merge_after_sync(*_args):
            self.skill_sync.assert_called_once()
            return "b" * 40

        self.merge.side_effect = merge_after_sync
        self.run_agent("42")

    def test_automatic_skill_sync_failure_does_not_block_authorized_merge(self):
        self.skill_sync.return_value = ["skill directory is read-only"]
        result = self.run_agent("42")
        self.assertEqual(result["status"], "merged")
        self.skill_sync.assert_called_once()
        self.merge.assert_called_once()

    def test_agent_handles_initial_scheduling_delay(self):
        self.get_checks.side_effect = [[], [], self.pending, self.passing, self.passing]
        result = self.run_agent("42")
        self.assertEqual(result["status"], "merged")
        self.assertEqual(self.elapsed, 2 * ci.POLL_INTERVAL_SECONDS)
        self.merge.assert_called_once()

    def test_agent_reports_discovery_timeout(self):
        self.get_checks.return_value = []
        result = self.run_agent("42", exit_code=124)
        self.assertEqual(result["status"], "timeout")
        self.assertFalse(result["merge_attempted"])
        self.assertEqual(self.elapsed, ci.CHECK_DISCOVERY_TIMEOUT_SECONDS)
        self.merge.assert_not_called()

    def test_timeout_can_be_shorter_than_poll_interval_or_discovery_grace(self):
        for checks in ([], self.pending):
            with self.subTest(checks=checks):
                self.elapsed = 0
                self.get_checks.return_value = checks
                result = self.run_agent("42", "--timeout", "3", exit_code=124)
                self.assertEqual(result["status"], "timeout")
                self.assertIn("CI wait timeout expired", result["message"])
                self.assertFalse(result["merge_attempted"])
                self.assertEqual(self.elapsed, 3)
        self.merge.assert_not_called()

    def test_default_waiting_limit_is_finite(self):
        self.get_checks.return_value = self.pending
        result = self.run_agent("42", exit_code=124)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(self.elapsed, ci.DEFAULT_WAIT_TIMEOUT_SECONDS)
        self.merge.assert_not_called()

    def test_expired_deadline_rejects_even_successful_checks(self):
        def slow_checks(*_args):
            self.advance_clock(6)
            return self.passing

        self.get_checks.side_effect = slow_checks
        result = self.run_agent("42", "--timeout", "5", exit_code=124)
        self.assertEqual(result["status"], "timeout")
        self.merge.assert_not_called()

    def test_deadline_is_checked_after_final_revalidation(self):
        def slow_checks(*_args):
            self.advance_clock(2)
            return self.passing

        self.get_checks.side_effect = slow_checks
        result = self.run_agent("42", "--timeout", "3", exit_code=124)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(self.get_checks.call_count, 3)
        self.merge.assert_not_called()

    def test_agent_does_not_bypass_dirty_worktree_check(self):
        self.get_local.return_value = replace(self.local, status=" M tracked")
        result = self.run_agent("42", exit_code=1)
        self.assertEqual(result["status"], "error")
        self.assertIn("working tree has", result["message"])
        self.assertFalse(result["merge_attempted"])
        self.merge.assert_not_called()

    def test_agent_does_not_bypass_head_change_or_review_checks(self):
        for fields, message in [
            ({"head_sha": "c" * 40}, "head SHA changed"),
            ({"review_decision": "CHANGES_REQUESTED"}, "reviews block merging"),
        ]:
            with self.subTest(fields=fields):
                self.get_pr.side_effect = [
                    self.pr,
                    self.pr,
                    replace(self.pr, **fields),
                ]
                result = self.run_agent("42", exit_code=1)
                self.assertEqual(result["status"], "error")
                self.assertIn(message, result["message"])
                self.assertFalse(result["merge_attempted"])
        self.merge.assert_not_called()

    def test_agent_does_not_bypass_failed_or_disappeared_checks(self):
        for checks, message in [
            (self.failed, "CI changed before merging"),
            ([], "CI is no longer fully complete"),
        ]:
            with self.subTest(checks=checks):
                self.get_checks.side_effect = [self.passing, self.passing, checks]
                result = self.run_agent("42", exit_code=1)
                self.assertIn(message, result["message"])
                self.assertFalse(result["merge_attempted"])
        self.merge.assert_not_called()

    def test_agent_reports_cancellation_before_merge(self):
        self.get_checks.return_value = self.pending
        self.sleep.side_effect = KeyboardInterrupt
        result = self.run_agent("42", exit_code=130)
        self.assertEqual(result["status"], "cancelled")
        self.assertFalse(result["merge_attempted"])
        self.merge.assert_not_called()

    def test_agent_marks_uncertain_outcome_after_merge_attempt(self):
        for error, exit_code in [
            (ci.MergeError("GitHub unavailable"), 1),
            (KeyboardInterrupt(), 130),
        ]:
            with self.subTest(error=error):
                self.merge.side_effect = error
                result = self.run_agent("42", exit_code=exit_code)
                self.assertTrue(result["merge_attempted"])
                self.assertIsNone(result["merge_commit"])
                self.assertIn(
                    "verify the pull request state before retrying", result["message"]
                )


class SkillTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ci merge skills ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.enterContext(patch.dict(os.environ, HOME=str(self.home)))
        for name in (
            "CLAUDE_CONFIG_DIR",
            "PI_CODING_AGENT_DIR",
            "SKIP_CI_MERGE_SKILLS",
        ):
            os.environ.pop(name, None)
        self.output = io.StringIO()
        self.stdout = io.StringIO()
        self.enterContext(
            patch.object(ci, "console", Console(file=self.output, width=200))
        )
        self.enterContext(patch.object(sys, "stdout", self.stdout))
        self.process = self.enterContext(
            patch.object(
                ci.subprocess,
                "run",
                side_effect=AssertionError(
                    "skill management must not run external commands"
                ),
            )
        )
        self.paths = [
            self.home / ".claude/skills/ci-merge-agent/SKILL.md",
            self.home / ".pi/agent/skills/ci-merge-agent/SKILL.md",
        ]

    def run_cli(self, *arguments, exit_code=0):
        self.stdout.seek(0)
        self.stdout.truncate()
        self.assertEqual(ci.main(list(arguments)), exit_code, self.output.getvalue())
        result = json.loads(self.stdout.getvalue())
        self.assertEqual(result["exit_code"], exit_code)
        self.assertFalse(result["merge_attempted"])
        self.assertIsNone(result["pr_number"])
        self.process.assert_not_called()
        return result

    def test_install_skills_seeds_both_agents_without_repository_or_authorization(self):
        result = self.run_cli("--install-skills")
        self.assertEqual(result["status"], "skills_installed")
        self.assertEqual(ci.agent_skill_paths(), self.paths)
        for path in self.paths:
            self.assertEqual(path.read_text(), ci.agent_skill_content())
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
        self.assertIn("Updated CI merge skill:", self.output.getvalue())

    def test_skill_has_portable_frontmatter_and_authorization_instructions(self):
        text = ci.agent_skill_content()
        self.assertTrue(text.startswith("---\nname: ci-merge-agent\ndescription: "))
        self.assertIn("\n---\n" + ci.SKILL_MANAGED_MARKER, text)
        self.assertIn("Loading this skill is NOT authorization to merge", text)
        self.assertIn(f"--timeout {ci.DEFAULT_WAIT_TIMEOUT_SECONDS}", text)
        self.assertIn("merge_attempted: true", text)
        self.assertIn('Only `status: "merged"`', text)
        self.assertNotIn("allowed-tools:", text)
        self.assertNotIn("disable-model-invocation:", text)

    def test_identical_content_leaves_inode_mtime_and_permissions_unchanged(self):
        self.run_cli("--install-skills")
        for path in self.paths:
            path.chmod(0o600)
            os.utime(path, ns=(1_000_000_000, 1_000_000_000))
        before = [
            (p.stat().st_ino, p.stat().st_mtime_ns, p.stat().st_mode)
            for p in self.paths
        ]
        self.output.seek(0)
        self.output.truncate()
        self.run_cli("--install-skills")
        after = [
            (p.stat().st_ino, p.stat().st_mtime_ns, p.stat().st_mode)
            for p in self.paths
        ]
        self.assertEqual(after, before)
        self.assertEqual(self.output.getvalue(), "")

    def test_stale_managed_skills_are_replaced_on_help(self):
        for path in self.paths:
            path.parent.mkdir(parents=True)
            path.write_text(ci.SKILL_MANAGED_MARKER + "\nold instructions\n")
        result = self.run_cli("--help")
        self.assertEqual(result["status"], "help")
        for path in self.paths:
            self.assertEqual(path.read_text(), ci.agent_skill_content())
            self.assertEqual(list(path.parent.glob(".SKILL-*")), [])

    def test_new_bundled_content_is_detected_without_manual_version_bump(self):
        self.run_cli("--install-skills")
        updated = ci.agent_skill_content().replace(
            "# CI merge agent", "# Updated CI merge agent"
        )
        with patch.object(ci, "agent_skill_content", return_value=updated):
            self.run_cli("--help")
        for path in self.paths:
            self.assertEqual(path.read_text(), updated)

    def test_custom_config_roots_are_honored(self):
        claude = self.root / "custom Claude"
        pi = self.root / "custom Pi"
        with patch.dict(
            os.environ, CLAUDE_CONFIG_DIR=str(claude), PI_CODING_AGENT_DIR=str(pi)
        ):
            self.run_cli("--install-skills")
        for root in (claude, pi):
            self.assertEqual(
                (root / "skills/ci-merge-agent/SKILL.md").read_text(),
                ci.agent_skill_content(),
            )
        for path in self.paths:
            self.assertFalse(path.exists())

    def test_tilde_config_roots_expand_and_empty_values_use_defaults(self):
        with patch.dict(
            os.environ, CLAUDE_CONFIG_DIR="~/custom Claude", PI_CODING_AGENT_DIR=""
        ):
            self.run_cli("--install-skills")
        self.assertTrue(
            (self.home / "custom Claude/skills/ci-merge-agent/SKILL.md").is_file()
        )
        self.assertTrue(self.paths[1].is_file())
        self.assertFalse(self.paths[0].exists())

    def test_unmanaged_collision_and_unrelated_files_are_preserved(self):
        claude = self.paths[0]
        claude.parent.mkdir(parents=True)
        claude.write_text("---\nname: ci-merge-agent\n---\nMy own skill\n")
        unrelated = claude.parent.parent / "other-skill/SKILL.md"
        unrelated.parent.mkdir()
        unrelated.write_text("Unrelated instructions\n")
        settings = self.home / ".claude/settings.json"
        settings.write_text('{"permissions": {"deny": ["Bash"]}}\n')
        before = {path: path.read_bytes() for path in (claude, unrelated, settings)}
        result = self.run_cli("--install-skills", exit_code=1)
        self.assertEqual(result["status"], "error")
        self.assertIn("not managed by this tool", result["message"])
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)
        self.assertEqual(self.paths[1].read_text(), ci.agent_skill_content())

    def test_file_symlinks_are_preserved_without_modifying_their_target(self):
        target = self.root / "external-skill.md"
        original = ci.SKILL_MANAGED_MARKER + "\nold instructions\n"
        target.write_text(original)
        self.paths[0].parent.mkdir(parents=True)
        self.paths[0].symlink_to(target)
        self.run_cli("--install-skills", exit_code=1)
        self.assertTrue(self.paths[0].is_symlink())
        self.assertEqual(target.read_text(), original)
        self.assertTrue(self.paths[1].is_file())

    def test_skill_directory_symlinks_are_preserved(self):
        target = self.root / "external-skill"
        target.mkdir()
        self.paths[0].parent.parent.mkdir(parents=True)
        self.paths[0].parent.symlink_to(target, target_is_directory=True)
        self.run_cli("--install-skills", exit_code=1)
        self.assertEqual(list(target.iterdir()), [])
        self.assertTrue(self.paths[0].parent.is_symlink())
        self.assertTrue(self.paths[1].is_file())

    def test_dangling_symlink_is_not_followed_or_replaced(self):
        target = self.root / "missing-skill.md"
        self.paths[0].parent.mkdir(parents=True)
        self.paths[0].symlink_to(target)
        self.run_cli("--install-skills", exit_code=1)
        self.assertTrue(self.paths[0].is_symlink())
        self.assertFalse(target.exists())

    def test_non_regular_skill_path_is_not_replaced(self):
        self.paths[0].mkdir(parents=True)
        result = self.run_cli("--install-skills", exit_code=1)
        self.assertIn("not a regular file", result["message"])
        self.assertTrue(self.paths[0].is_dir())
        self.assertTrue(self.paths[1].is_file())

    def test_unwritable_destination_does_not_prevent_other_agent_installation(self):
        write = ci.write_managed_skill

        def deny_claude(path, content):
            if path == self.paths[0]:
                raise PermissionError("read-only skill directory")
            return write(path, content)

        with patch.object(ci, "write_managed_skill", side_effect=deny_claude):
            result = self.run_cli("--install-skills", exit_code=1)
        self.assertIn("read-only skill directory", result["message"])
        self.assertTrue(self.paths[1].is_file())

    def test_failed_atomic_replace_keeps_original_and_cleans_temporary_file(self):
        path = self.paths[0]
        path.parent.mkdir(parents=True)
        original = ci.SKILL_MANAGED_MARKER + "\nold instructions\n"
        path.write_text(original)
        with (
            patch.object(Path, "replace", side_effect=OSError("replace failed")),
            self.assertRaisesRegex(OSError, "replace failed"),
        ):
            ci.write_managed_skill(path, ci.agent_skill_content().encode())
        self.assertEqual(path.read_text(), original)
        self.assertEqual(list(path.parent.iterdir()), [path])

    def test_automatic_sync_warns_without_turning_help_into_failure(self):
        self.paths[0].parent.mkdir(parents=True)
        self.paths[0].write_text("My own skill\n")
        result = self.run_cli("--help")
        self.assertEqual(result["status"], "help")
        self.assertIn("Warning:", self.output.getvalue())
        self.assertTrue(self.paths[1].is_file())

    def test_missing_merge_authorization_can_seed_skills_but_never_touches_git(self):
        result = self.run_cli("42", exit_code=2)
        self.assertIn("requires --yes", result["message"])
        for path in self.paths:
            self.assertTrue(path.is_file())

    def test_human_help_does_not_automatically_install_skills(self):
        self.assertEqual(ci.main(["--interactive", "--help"]), 0)
        for path in self.paths:
            self.assertFalse(path.exists())
        self.process.assert_not_called()

    def test_skip_flag_suppresses_automatic_sync_but_allows_explicit_install(self):
        with patch.dict(os.environ, SKIP_CI_MERGE_SKILLS="1"):
            self.run_cli("--help")
            for path in self.paths:
                self.assertFalse(path.exists())
            self.run_cli("--install-skills")
            for path in self.paths:
                self.assertTrue(path.is_file())

    def test_install_only_rejects_merge_arguments_without_writing_or_merging(self):
        for arguments in [("42",), ("--yes",)]:
            with self.subTest(arguments=arguments):
                result = self.run_cli("--install-skills", *arguments, exit_code=2)
                self.assertEqual(result["status"], "error")
                for path in self.paths:
                    self.assertFalse(path.exists())


class CommandEntryPointTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ci merge commands ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.agent = self.root / "ci-merge-agent"
        # Reuse this test's isolated Python dependencies; never download via uv.
        source = (ROOT / "bin/ci-merge-agent").read_text().split("\n", 1)[1]
        self.agent.write_text(f"#!{sys.executable}\n{source}")
        self.agent.chmod(0o755)
        self.wrapper = self.root / "ci-merge"
        self.env = dict(
            os.environ,
            HOME=str(self.home),
            CLAUDE_CONFIG_DIR=str(self.home / ".claude"),
            PI_CODING_AGENT_DIR=str(self.home / ".pi/agent"),
            SKIP_CI_MERGE_SKILLS="0",
        )

    def run_command(self, command, *arguments):
        return subprocess.run(
            [str(command), *arguments],
            cwd=self.root,
            env=self.env,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_agent_alone_bootstraps_skills_with_clean_json_output(self):
        self.assertFalse(self.wrapper.exists())
        result = self.run_command(self.agent, "--install-skills")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "skills_installed")
        self.assertFalse(payload["merge_attempted"])
        for config in (self.home / ".claude", self.home / ".pi/agent"):
            self.assertEqual(
                (config / "skills/ci-merge-agent/SKILL.md").read_text(),
                ci.agent_skill_content(),
            )
        self.assertIn("Updated CI merge skill:", result.stderr)

    def test_human_command_uses_human_help_without_installing_skills(self):
        shutil.copy2(ROOT / "bin/ci-merge", self.wrapper)
        result = self.run_command(self.wrapper, "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("usage: ci-merge ", result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_human_wrapper_can_explicitly_request_json(self):
        shutil.copy2(ROOT / "bin/ci-merge", self.wrapper)
        result = self.run_command(self.wrapper, "--json", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "help")

    def test_human_wrapper_preserves_arguments_and_propagates_exit_code(self):
        shutil.copy2(ROOT / "bin/ci-merge", self.wrapper)
        self.agent.write_text(
            f"#!{sys.executable}\n"
            "import json, sys\n"
            "print(json.dumps(sys.argv[1:]))\n"
            "sys.exit(23)\n"
        )
        arguments = [
            "https://github.com/example/repository/pull/42",
            "--yes",
            "--timeout",
            "7",
        ]
        result = self.run_command(self.wrapper, *arguments)
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["--interactive", *arguments])
        self.assertEqual(result.stderr, "")

    @unittest.skipUnless(shutil.which("fish"), "Fish is not installed")
    def test_fish_function_delegates_without_recursion(self):
        shutil.copy2(ROOT / "bin/ci-merge", self.wrapper)
        self.agent.write_text(
            f"#!{sys.executable}\n"
            "import json, sys\n"
            "print(json.dumps(sys.argv[1:]))\n"
            "sys.exit(23)\n"
        )
        arguments = ["42", "--timeout", "7"]
        result = subprocess.run(
            [
                shutil.which("fish"),
                "--no-config",
                "-c",
                'source "$argv[1]"; ci-merge $argv[2..]',
                str(ROOT / "config/fish/functions/ci-merge.fish"),
                *arguments,
            ],
            cwd=self.root,
            env=dict(
                self.env, PATH=f"{self.root}{os.pathsep}{os.environ.get('PATH', '')}"
            ),
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["--interactive", *arguments])


class GitHubTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path("/unused")
        self.pr = ci.PullRequest(
            42,
            "Example",
            "https://github.com/example/repository/pull/42",
            "OPEN",
            False,
            "main",
            "feature",
            "a" * 40,
            "MERGEABLE",
            "CLEAN",
            "APPROVED",
        )

    def test_empty_json_and_no_checks_message_both_mean_no_checks(self):
        for code, stdout, stderr in [
            (0, b"[]", b""),
            (1, b"", b"no checks reported on the 'feature' branch"),
        ]:
            with self.subTest(code=code):
                result = subprocess.CompletedProcess([], code, stdout, stderr)
                with patch.object(ci, "run_process", return_value=result):
                    self.assertEqual(ci.get_checks(self.repo, self.pr), [])

    def test_merge_submits_exact_head_guard_and_verifies_remote_result(self):
        inspection = ci.Inspection(
            self.pr,
            "example/repository",
            ci.LocalState("feature", self.pr.head_sha, ""),
            [],
        )
        result = subprocess.CompletedProcess([], 0, b"", b"")
        with (
            patch.object(ci, "run_process", return_value=result) as run,
            patch.object(
                ci,
                "gh_json",
                return_value={"state": "MERGED", "mergeCommit": {"oid": "b" * 40}},
            ) as query,
        ):
            self.assertEqual(ci.merge_pull_request(self.repo, inspection), "b" * 40)
        run.assert_called_once_with(
            [
                "gh",
                "pr",
                "merge",
                self.pr.url,
                "--squash",
                "--match-head-commit",
                self.pr.head_sha,
            ],
            cwd=self.repo,
            check=False,
        )
        query.assert_called_once_with(
            self.repo, "pr", "view", self.pr.url, "--json", "state,url,mergeCommit"
        )

    def test_accepted_command_without_verified_merge_is_not_success(self):
        inspection = ci.Inspection(
            self.pr,
            "example/repository",
            ci.LocalState("feature", self.pr.head_sha, ""),
            [],
        )
        with (
            patch.object(
                ci,
                "run_process",
                return_value=subprocess.CompletedProcess([], 0, b"", b""),
            ),
            patch.object(ci, "gh_json", return_value={"state": "OPEN"}),
            self.assertRaisesRegex(ci.MergeError, "PR remains open"),
        ):
            ci.merge_pull_request(self.repo, inspection)


if __name__ == "__main__":
    unittest.main()
