#!/usr/bin/env python3
"""Run the full 4-stage DPF analysis pipeline: analyze -> deep -> passive -> report."""
import argparse, subprocess, sys, time

STAGES = [
    ("analyze.py", "scanning CSVs -> summary.json"),
    ("deep.py",    "extracting time series -> trips.json"),
    ("passive.py", "detecting passive regens -> passive_summary.json"),
    ("report.py",  "generating report"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default="./data",
                    help="directory holding CarScanner *.csv exports (default: ./data)")
    args = ap.parse_args()

    for i, (script, label) in enumerate(STAGES, 1):
        print(f"\n[{i}/{len(STAGES)}] {script}: {label}", file=sys.stderr)
        t0 = time.perf_counter()
        rc = subprocess.call([sys.executable, script, "--data-dir", args.data_dir])
        if rc != 0:
            print(f"\n[{i}/{len(STAGES)}] {script} failed with exit code {rc}", file=sys.stderr)
            sys.exit(rc)
        print(f"    done ({time.perf_counter() - t0:.1f}s)", file=sys.stderr)


if __name__ == "__main__":
    main()
