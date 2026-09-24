"""Integration tests for the Kev installer, using disposable homes only."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "scripts" / "install_kev.py"
BEGIN = "<!-- BEGIN CODEX-CONFIG KEV -->"
END = "<!-- END CODEX-CONFIG KEV -->"


class InstallKevTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="kev-installer-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.home = self.root / "home"
        self.skill_source = self.source / "skills" / "kev-decisions"
        self.skill_codex = self.home / ".agents" / "skills" / "kev-decisions"
        self.skill_claude = self.home / ".claude" / "skills" / "kev-decisions"
        self.codex_instructions = self.home / ".codex" / "AGENTS.md"
        self.claude_instructions = self.home / ".claude" / "CLAUDE.md"
        self.override = self.home / ".codex" / "AGENTS.override.md"
        self.payload = "Use the kev-decisions skill for decisions.\n"
        self.skill_files = {
            "SKILL.md": "---\nname: kev-decisions\n---\nKev decision skill.\n",
            "scripts/kev.py": "print('kev fixture')\n",
            "references/local.md": "Run locally.\n",
            "references/nested/usage.md": "Nested reference.\n",
            "agents/openai.yaml": "display_name: Kev\n",
        }
        self.write_source_block(self.payload)
        for relative, content in self.skill_files.items():
            self.write(self.skill_source / relative, content.encode("utf-8"))
        self.write(self.skill_source / ".hidden" / "secret.txt", b"ignored\n")
        self.write(self.skill_source / "scripts" / "__pycache__" / "kev.pyc", b"ignored\n")
        self.write(self.skill_source / "references" / ".cache" / "cache.txt", b"ignored\n")
        self.environment = os.environ.copy()
        self.environment.pop("CODEX_HOME", None)
        self.environment.pop("CLAUDE_CONFIG_DIR", None)
        self.environment["HOME"] = str(self.home)
        self.environment["USERPROFILE"] = str(self.home)
        self.environment["PYTHONDONTWRITEBYTECODE"] = "1"

    @staticmethod
    def write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def write_source_block(self, payload: str) -> None:
        self.write(
            self.source / "AGENTS.md",
            ("Repository-only preface.\n\n" + BEGIN + "\n" + payload + END +
             "\n\nRepository-only suffix.\n").encode("utf-8"),
        )

    def run_installer(
        self,
        *arguments: str,
        explicit_home: bool = True,
        environment: dict[str, str] | None = None,
        expected_code: int | None = 0,
    ) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, str(INSTALLER), "--source", str(self.source)]
        if explicit_home:
            command.extend(["--home", str(self.home)])
        command.extend(arguments)
        result = subprocess.run(
            command,
            env=environment if environment is not None else self.environment,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        if expected_code is not None:
            self.assertEqual(
                result.returncode,
                expected_code,
                msg=f"{command!r}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
        return result

    def snapshot(self) -> dict[str, tuple]:
        """Include mtimes so read-only operations cannot silently rewrite files."""
        result = {}
        for directory, directories, files in os.walk(self.root, followlinks=False):
            for name in directories + files:
                path = Path(directory) / name
                relative = str(path.relative_to(self.root))
                stat = path.lstat()
                if path.is_symlink():
                    result[relative] = ("symlink", os.readlink(path), stat.st_mtime_ns)
                elif path.is_dir():
                    result[relative] = ("directory", stat.st_mtime_ns)
                else:
                    result[relative] = ("file", path.read_bytes(), stat.st_mtime_ns)
        return result

    def assert_preflight_failure(self, *arguments: str) -> None:
        before = self.snapshot()
        result = self.run_installer(*arguments, expected_code=None)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before, "Failed preflight wrote to disk")

    def backups(self, path: Path) -> list[Path]:
        return sorted(path.parent.glob(path.name + ".*.bak"))

    def test_fresh_install_copies_skill_and_managed_block_for_both_clients(self) -> None:
        self.run_installer()
        for destination in (self.skill_codex, self.skill_claude):
            for relative, content in self.skill_files.items():
                self.assertEqual((destination / relative).read_text(), content)
            self.assertFalse((destination / ".hidden").exists())
            self.assertFalse((destination / "scripts" / "__pycache__").exists())
            self.assertFalse((destination / "references" / ".cache").exists())
        for destination in (self.codex_instructions, self.claude_instructions):
            installed = destination.read_text()
            self.assertIn(BEGIN + "\n" + self.payload + END, installed)
            self.assertNotIn("Repository-only", installed)
            self.assertEqual(installed.count(BEGIN), 1)
            self.assertEqual(installed.count(END), 1)
        self.assertFalse(self.override.exists())
        self.assertFalse(list(self.home.rglob("*.bak")))

    def test_repeat_install_and_successful_check_do_not_change_any_files(self) -> None:
        self.run_installer()
        before = self.snapshot()
        self.run_installer()
        self.assertEqual(self.snapshot(), before)
        self.run_installer("--check")
        self.assertEqual(self.snapshot(), before)

    def test_check_reports_missing_install_without_creating_home(self) -> None:
        before = self.snapshot()
        self.run_installer("--check", expected_code=1)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.home.exists())

    def test_check_reports_skill_drift_without_repairing_it(self) -> None:
        self.run_installer()
        (self.skill_claude / "scripts" / "kev.py").write_text("changed locally\n")
        before = self.snapshot()
        self.run_installer("--check", expected_code=1)
        self.assertEqual(self.snapshot(), before)

    def test_check_reports_managed_block_drift_without_repairing_it(self) -> None:
        self.run_installer()
        self.codex_instructions.write_text(BEGIN + "\nStale instructions.\n" + END + "\n")
        before = self.snapshot()
        self.run_installer("--check", expected_code=1)
        self.assertEqual(self.snapshot(), before)

    def test_dry_run_prints_planned_paths_without_creating_home(self) -> None:
        before = self.snapshot()
        result = self.run_installer("--dry-run")
        self.assertEqual(self.snapshot(), before)
        for path in (
            self.codex_instructions,
            self.claude_instructions,
            self.skill_codex / "SKILL.md",
            self.skill_claude / "SKILL.md",
        ):
            self.assertIn(str(path), result.stdout + result.stderr)

    def test_append_preserves_arabic_bom_crlf_and_backs_up_original(self) -> None:
        original = b"\xef\xbb\xbf" + "# تعليمات شخصية\r\nاحتفظ بهذا النص.\r\n".encode("utf-8")
        for path in (self.codex_instructions, self.claude_instructions):
            self.write(path, original)
        self.run_installer()
        for path in (self.codex_instructions, self.claude_instructions):
            installed = path.read_bytes()
            self.assertTrue(installed.startswith(original))
            self.assertEqual(installed.count(b"\xef\xbb\xbf"), 1)
            self.assertNotIn(b"\n", installed.replace(b"\r\n", b""))
            self.assertEqual(len(self.backups(path)), 1)
            self.assertEqual(self.backups(path)[0].read_bytes(), original)
        before = self.snapshot()
        self.run_installer()
        self.run_installer("--check")
        self.assertEqual(self.snapshot(), before)

    def test_update_preserves_exact_content_outside_existing_block(self) -> None:
        prefix = b"\xef\xbb\xbf" + "# ملاحظات\r\n\r\n".encode("utf-8")
        suffix = "\r\n\r\nنص بعد القسم.\r\n".encode("utf-8")
        original = prefix + (BEGIN + "\r\nOld managed text.\r\n" + END).encode() + suffix
        self.write(self.codex_instructions, original)
        self.run_installer()
        installed = self.codex_instructions.read_bytes()
        expected = prefix + (BEGIN + "\r\n" + self.payload.replace("\n", "\r\n") + END).encode() + suffix
        self.assertEqual(installed, expected)
        self.assertEqual(self.backups(self.codex_instructions)[0].read_bytes(), original)
        self.write_source_block("Use the updated Kev instructions.\n")
        self.run_installer()
        updated = self.codex_instructions.read_bytes()
        self.assertTrue(updated.startswith(prefix + BEGIN.encode()))
        self.assertTrue(updated.endswith(END.encode() + suffix))
        self.assertIn(b"Use the updated Kev instructions.\r\n", updated)
        self.assertNotIn(self.payload.encode(), updated)
        self.assertEqual(len(self.backups(self.codex_instructions)), 2)
        self.run_installer("--check")

    def test_existing_nonempty_codex_override_receives_managed_block(self) -> None:
        original = "# Local override\nKeep this setting.\n"
        self.write(self.override, original.encode())
        self.run_installer()
        self.assertTrue(self.override.read_text().startswith(original))
        self.assertIn(self.payload, self.override.read_text())
        self.assertEqual(self.backups(self.override)[0].read_text(), original)
        self.run_installer("--check")

    def test_empty_override_is_left_empty(self) -> None:
        self.write(self.override, b"")
        self.run_installer()
        self.assertEqual(self.override.read_bytes(), b"")
        self.assertEqual(self.backups(self.override), [])

    def test_modified_existing_skill_is_backed_up_and_unrelated_files_survive(self) -> None:
        self.run_installer()
        path = self.skill_codex / "scripts" / "kev.py"
        original = b"# local modification\n"
        path.write_bytes(original)
        unrelated = self.skill_codex / "my-notes.txt"
        unrelated.write_text("Personal notes.\n")
        self.run_installer()
        self.assertEqual(path.read_text(), self.skill_files["scripts/kev.py"])
        self.assertEqual(self.backups(path)[0].read_bytes(), original)
        self.assertEqual(unrelated.read_text(), "Personal notes.\n")
        self.run_installer("--check")

    def test_default_paths_follow_home_when_environment_dirs_are_unset(self) -> None:
        self.run_installer(explicit_home=False)
        self.assertTrue(self.codex_instructions.is_file())
        self.assertTrue(self.claude_instructions.is_file())
        self.assertTrue((self.skill_codex / "SKILL.md").is_file())

    def test_environment_selects_client_dirs_but_codex_skill_stays_under_home(self) -> None:
        codex = self.root / "environment-codex"
        claude = self.root / "environment-claude"
        environment = dict(self.environment, CODEX_HOME=str(codex), CLAUDE_CONFIG_DIR=str(claude))
        self.run_installer(explicit_home=False, environment=environment)
        self.assertTrue((codex / "AGENTS.md").is_file())
        self.assertTrue((claude / "CLAUDE.md").is_file())
        self.assertTrue((claude / "skills" / "kev-decisions" / "SKILL.md").is_file())
        self.assertTrue((self.skill_codex / "SKILL.md").is_file())
        self.assertFalse(self.codex_instructions.exists())
        self.assertFalse(self.claude_instructions.exists())

    def test_explicit_home_ignores_client_environment_dirs(self) -> None:
        codex = self.root / "environment-codex"
        claude = self.root / "environment-claude"
        environment = dict(self.environment, CODEX_HOME=str(codex), CLAUDE_CONFIG_DIR=str(claude))
        self.run_installer(environment=environment)
        self.assertTrue(self.codex_instructions.is_file())
        self.assertTrue(self.claude_instructions.is_file())
        self.assertFalse(codex.exists())
        self.assertFalse(claude.exists())

    def test_explicit_client_dirs_override_home_defaults(self) -> None:
        codex = self.root / "chosen-codex"
        claude = self.root / "chosen-claude"
        self.run_installer("--codex-home", str(codex), "--claude-home", str(claude))
        self.assertTrue((codex / "AGENTS.md").is_file())
        self.assertTrue((claude / "CLAUDE.md").is_file())
        self.assertTrue((claude / "skills" / "kev-decisions" / "SKILL.md").is_file())
        self.assertTrue((self.skill_codex / "SKILL.md").is_file())
        self.assertFalse(self.codex_instructions.exists())
        self.assertFalse(self.claude_instructions.exists())

    def test_checkout_in_codex_home_preserves_source_and_updates_global_override(self) -> None:
        self.home.mkdir()
        destination = self.home / ".codex"
        self.source.rename(destination)
        self.source = destination
        self.skill_source = self.source / "skills" / "kev-decisions"
        original_instructions = self.codex_instructions.read_bytes()
        original_mtime = self.codex_instructions.stat().st_mtime_ns
        original_override = b"# Existing global override\nPreserve this preference.\n"
        self.write(self.override, original_override)

        self.run_installer()

        self.assertEqual(self.codex_instructions.read_bytes(), original_instructions)
        self.assertEqual(self.codex_instructions.stat().st_mtime_ns, original_mtime)
        self.assertEqual(self.backups(self.codex_instructions), [])
        self.assertTrue(self.override.read_bytes().startswith(original_override))
        self.assertIn(BEGIN + "\n" + self.payload + END, self.override.read_text())
        self.assertEqual(len(self.backups(self.override)), 1)
        self.assertEqual(self.backups(self.override)[0].read_bytes(), original_override)
        self.assertIn(BEGIN + "\n" + self.payload + END, self.claude_instructions.read_text())
        for skill_destination in (self.skill_codex, self.skill_claude):
            for relative, content in self.skill_files.items():
                self.assertEqual((skill_destination / relative).read_text(), content)
        before = self.snapshot()
        self.run_installer("--check")
        self.run_installer()
        self.assertEqual(self.snapshot(), before)

    def test_malformed_destination_markers_fail_before_any_writes(self) -> None:
        malformed = (
            BEGIN + "\nMissing end.\n",
            "Missing begin.\n" + END + "\n",
            END + "\nWrong order.\n" + BEGIN + "\n",
            BEGIN + "\nOne.\n" + END + "\n" + BEGIN + "\nTwo.\n" + END + "\n",
        )
        for content in malformed:
            with self.subTest(content=content):
                self.write(self.claude_instructions, content.encode())
                self.assert_preflight_failure()

    def test_malformed_source_markers_fail_before_any_writes(self) -> None:
        malformed = (
            "No managed block.\n",
            BEGIN + "\nMissing end.\n",
            BEGIN + "\nOne.\n" + END + "\n" + BEGIN + "\nTwo.\n" + END + "\n",
        )
        for content in malformed:
            with self.subTest(content=content):
                (self.source / "AGENTS.md").write_text(content)
                self.assert_preflight_failure()

    def test_invalid_destination_utf8_fails_before_any_writes(self) -> None:
        self.write(self.claude_instructions, b"Invalid utf-8: \xff\xfe\n")
        self.assert_preflight_failure()

    def test_invalid_source_utf8_fails_before_any_writes(self) -> None:
        (self.skill_source / "SKILL.md").write_bytes(b"Invalid utf-8: \xff\xfe\n")
        self.assert_preflight_failure()

    def test_destination_directory_where_skill_file_is_expected_fails_preflight(self) -> None:
        (self.skill_claude / "references" / "local.md").mkdir(parents=True)
        self.assert_preflight_failure()

    def test_destination_file_where_directory_is_expected_fails_preflight(self) -> None:
        self.write(self.home / ".claude" / "skills", b"A file blocks the skill directory.\n")
        self.assert_preflight_failure()

    def test_destination_directory_where_instructions_file_is_expected_fails_preflight(self) -> None:
        self.claude_instructions.mkdir(parents=True)
        self.assert_preflight_failure()

    def test_client_directory_beneath_planned_skill_file_fails_preflight(self) -> None:
        conflicting_directory = self.skill_codex / "scripts" / "kev.py" / "nested"
        self.assert_preflight_failure("--claude-home", str(conflicting_directory))

    def test_client_destination_inside_source_fails_preflight(self) -> None:
        self.assert_preflight_failure("--claude-home", str(self.source / "new-claude"))

    @unittest.skipUnless(hasattr(os, "symlink"), "Symbolic links unavailable")
    def test_destination_symlink_is_rejected_without_touching_external_target(self) -> None:
        external = self.root / "external-instructions.md"
        self.write(external, b"Do not modify.\n")
        self.claude_instructions.parent.mkdir(parents=True)
        self.claude_instructions.symlink_to(external)
        self.assert_preflight_failure()

    @unittest.skipUnless(hasattr(os, "symlink"), "Symbolic links unavailable")
    def test_broken_destination_symlink_is_rejected(self) -> None:
        self.claude_instructions.parent.mkdir(parents=True)
        self.claude_instructions.symlink_to(self.root / "missing-target")
        self.assert_preflight_failure()

    @unittest.skipUnless(hasattr(os, "symlink"), "Symbolic links unavailable")
    def test_symlink_in_destination_directory_path_is_rejected(self) -> None:
        external = self.root / "external-client"
        external.mkdir()
        self.home.mkdir()
        (self.home / ".claude").symlink_to(external, target_is_directory=True)
        self.assert_preflight_failure()

    @unittest.skipUnless(hasattr(os, "symlink"), "Symbolic links unavailable")
    def test_source_symlink_is_rejected(self) -> None:
        external = self.root / "external-reference.md"
        self.write(external, b"Outside source.\n")
        (self.skill_source / "references" / "linked.md").symlink_to(external)
        self.assert_preflight_failure()

    def test_dry_run_performs_preflight_without_any_writes(self) -> None:
        self.write(self.claude_instructions, (BEGIN + "\nBroken block.\n").encode())
        self.assert_preflight_failure("--dry-run")


if __name__ == "__main__":
    unittest.main()
