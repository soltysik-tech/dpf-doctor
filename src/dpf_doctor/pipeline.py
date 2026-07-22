"""In-process orchestration of the 4-stage DPF analysis pipeline.

Replaces the old run.py, which subprocess-called each stage's script.
Running in-process means: install as a wheel, run from any CWD, get real
tracebacks instead of `subprocess exit code 1`.
"""
import sys
import time

from dpf_doctor.analysis import extract, passive, summary
from dpf_doctor.cli._common import csv_files_or_exit
from dpf_doctor import reporting


def run_all(data_dir: str) -> None:
    """Run analyze -> extract -> passive -> report against data_dir."""
    files = csv_files_or_exit(data_dir)

    stages = [
        ("analyze", "scanning CSVs -> summary.json",
         lambda: summary.run(data_dir, files=files)),
        ("extract", "extracting time series -> trips.json",
         lambda: extract.run(data_dir, files=files)),
        ("passive", "detecting passive regens -> passive_summary.json",
         lambda: passive.run(data_dir, files=files)),
        ("report", "generating report",
         lambda: reporting.run(data_dir)),
    ]

    for i, (name, label, fn) in enumerate(stages, 1):
        print(f"\n[{i}/{len(stages)}] {name}: {label}", file=sys.stderr)
        t0 = time.perf_counter()
        fn()
        print(f"    done ({time.perf_counter() - t0:.1f}s)", file=sys.stderr)
