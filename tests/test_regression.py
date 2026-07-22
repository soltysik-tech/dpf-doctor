"""End-to-end regression: run the pipeline against the sample CSV and diff outputs."""
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from dpf_doctor.analysis import extract, passive, summary
from dpf_doctor import reporting

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE_DIR = FIXTURES / "sample_data"


class TestPipelineRegression(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for src in SAMPLE_DIR.glob("*.csv"):
            shutil.copy(src, self.tmp / src.name)
        # Suppress noisy per-stage stdout/stderr during test runs.
        self._out = io.StringIO()
        self._err = io.StringIO()
        self._out_ctx = redirect_stdout(self._out)
        self._err_ctx = redirect_stderr(self._err)
        self._out_ctx.__enter__()
        self._err_ctx.__enter__()

    def tearDown(self):
        self._out_ctx.__exit__(None, None, None)
        self._err_ctx.__exit__(None, None, None)
        shutil.rmtree(self.tmp)

    def _assert_json_equal(self, produced_path, expected_name):
        produced = json.loads(produced_path.read_text())
        expected = json.loads((FIXTURES / expected_name).read_text())
        self.assertEqual(produced, expected, f"{produced_path.name} drifted from {expected_name}")

    def test_summary_json_stable(self):
        summary.run(str(self.tmp))
        self._assert_json_equal(self.tmp / "summary.json", "expected_summary.json")

    def test_trips_json_stable(self):
        extract.run(str(self.tmp))
        self._assert_json_equal(self.tmp / "trips.json", "expected_trips.json")

    def test_passive_summary_stable(self):
        passive.run(str(self.tmp), print_summary=False)
        self._assert_json_equal(self.tmp / "passive_summary.json", "expected_passive_summary.json")

    def test_report_stdout_stable(self):
        summary.run(str(self.tmp))
        with open(self.tmp / "summary.json") as fh:
            data = json.load(fh)
        rendered = reporting.render_to_string(data)
        expected = (FIXTURES / "expected_report.txt").read_text()
        self.assertEqual(rendered, expected)


if __name__ == "__main__":
    unittest.main()
