"""Shared CLI helpers: --data-dir arg, CSV glob, empty-dir bail."""
import argparse
import glob
import os
import sys
from pathlib import Path


def add_data_dir(ap: argparse.ArgumentParser) -> None:
    ap.add_argument(
        "--data-dir",
        default="./data",
        help="directory holding CarScanner *.csv exports (default: ./data)",
    )


def csv_files_or_exit(data_dir: str) -> list[str]:
    files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    if not files:
        print(
            f"No CSVs found in {data_dir!r}; drop CarScanner exports there or pass --data-dir DIR.",
            file=sys.stderr,
        )
        sys.exit(1)
    return files
