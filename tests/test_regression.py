"""End-to-end regression: run the pipeline against the sample CSV and diff outputs."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE_DIR = FIXTURES / "sample_data"


class TestPipelineRegression(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for src in SAMPLE_DIR.glob("*.csv"):
            shutil.copy(src, self.tmp / src.name)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run(self, script, capture_stdout=False):
        r = subprocess.run(
            [sys.executable, str(REPO_ROOT / script), "--data-dir", str(self.tmp)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout if capture_stdout else None

    def _assert_json_equal(self, produced_path, expected_name):
        produced = json.loads(produced_path.read_text())
        expected = json.loads((FIXTURES / expected_name).read_text())
        self.assertEqual(produced, expected, f"{produced_path.name} drifted from {expected_name}")

    def test_summary_json_stable(self):
        self._run("analyze.py")
        self._assert_json_equal(self.tmp / "summary.json", "expected_summary.json")

    def test_trips_json_stable(self):
        self._run("deep.py")
        self._assert_json_equal(self.tmp / "trips.json", "expected_trips.json")

    def test_passive_summary_stable(self):
        self._run("passive.py")
        self._assert_json_equal(self.tmp / "passive_summary.json", "expected_passive_summary.json")

    def test_report_stdout_stable(self):
        self._run("analyze.py")
        stdout = self._run("report.py", capture_stdout=True)
        expected = (FIXTURES / "expected_report.txt").read_text()
        self.assertEqual(stdout, expected)


if __name__ == "__main__":
    unittest.main()
