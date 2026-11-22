import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which("node"), "Node.js is required for browser regression tests")
class BrowserRegressionTests(unittest.TestCase):
    def test_browser_import_export_regressions(self) -> None:
        harness = Path(__file__).resolve().with_name("browser_regressions.js")
        result = subprocess.run([shutil.which("node"), str(harness)], check=False, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self.assertIn("PASS import without a snapshot clears the old repository", result.stdout)
        self.assertIn("PASS imported empty goal/state fields clear old text", result.stdout)
        self.assertIn("PASS malformed changed_files is rejected and exports stay usable", result.stdout)


if __name__ == "__main__":
    unittest.main()
