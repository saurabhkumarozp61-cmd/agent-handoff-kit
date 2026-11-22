import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture import capture_snapshot, compare_repositories  # noqa: E402


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], check=True, text=True, capture_output=True)
    return result.stdout.strip()


class CaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "demo-repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q")
        run_git(self.repo, "config", "user.name", "Handoff Kit tests")
        run_git(self.repo, "config", "user.email", "handoff-tests@localhost")
        (self.repo / "README.md").write_text("prototype\n", encoding="utf-8")
        run_git(self.repo, "add", "README.md")
        run_git(self.repo, "commit", "-qm", "Initial commit")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_snapshot_records_paths_but_not_contents(self) -> None:
        (self.repo / "README.md").write_text("changed secret-like content\n", encoding="utf-8")
        (self.repo / "todo.txt").write_text("private note\n", encoding="utf-8")
        snapshot = capture_snapshot(self.repo)
        repository = snapshot["repository"]
        self.assertEqual(repository["name"], "demo-repo")
        self.assertTrue(repository["head"])
        self.assertEqual(repository["changed_files"], ["README.md", "todo.txt"])
        rendered = str(snapshot)
        self.assertNotIn("changed secret-like content", rendered)
        self.assertNotIn("private note", rendered)

    def test_snapshot_preserves_spaces_and_unicode_in_paths(self) -> None:
        paths = ["notes dir/my file.txt", "naïve.md"]
        for relative in paths:
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("path only\n", encoding="utf-8")

        repository = capture_snapshot(self.repo)["repository"]

        self.assertEqual(repository["changed_files"], sorted(paths))

    def test_snapshot_includes_both_paths_for_staged_rename(self) -> None:
        old_path = "old name.md"
        new_path = "new name.md"
        (self.repo / old_path).write_text("rename me\n", encoding="utf-8")
        run_git(self.repo, "add", old_path)
        run_git(self.repo, "commit", "-qm", "Add rename fixture")
        run_git(self.repo, "mv", old_path, new_path)

        repository = capture_snapshot(self.repo)["repository"]

        self.assertEqual(repository["changed_files"], sorted([old_path, new_path]))

    def test_matching_repository_is_current(self) -> None:
        snapshot = capture_snapshot(self.repo)
        comparison = compare_repositories(snapshot["repository"], snapshot["repository"])
        self.assertFalse(comparison["stale"])
        self.assertTrue(all(check["matches"] for check in comparison["checks"]))

    def test_new_commit_marks_capsule_stale(self) -> None:
        saved = capture_snapshot(self.repo)["repository"]
        (self.repo / "README.md").write_text("second version\n", encoding="utf-8")
        run_git(self.repo, "add", "README.md")
        run_git(self.repo, "commit", "-qm", "Update README")
        current = capture_snapshot(self.repo)["repository"]
        comparison = compare_repositories(saved, current)
        self.assertTrue(comparison["stale"])
        self.assertFalse(next(item for item in comparison["checks"] if item["item"] == "HEAD commit")["matches"])

    def test_check_rejects_non_object_capsule_json_cleanly(self) -> None:
        capture_script = Path(__file__).resolve().parents[1] / "capture.py"
        capsule_path = Path(self.temp.name) / "invalid-capsule.json"
        for contents in ("[]", "null", "1", '"text"'):
            with self.subTest(contents=contents):
                capsule_path.write_text(contents, encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(capture_script), "check", "--repo", str(self.repo), "--capsule", str(capsule_path)],
                    check=False,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("capsule must be a JSON object", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
