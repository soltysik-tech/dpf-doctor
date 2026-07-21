"""Read a CarScanner CSV export into a Trip value object.

One reader for the whole pipeline. Owns: delimiter, encoding fallback,
float coercion, filename timestamp parsing, PID classification via
pids.classify. Returns a Trip whose series are sorted by timestamp so
downstream consumers can bisect without re-sorting.
"""
import csv
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from pids import classify

_FNAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2})-(\d{2})-(\d{2})\.csv$")


@dataclass
class Trip:
    path: str
    start: Optional[datetime]
    duration_s: float
    series: dict[str, list[tuple[float, float]]] = field(default_factory=dict)


def parse_trip_start(path: str) -> Optional[datetime]:
    m = _FNAME_RE.search(path)
    if not m:
        return None
    try:
        return datetime.strptime(
            f"{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}",
            "%Y-%m-%d %H:%M:%S",
        )
    except ValueError:
        return None


def _f(x: str) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def read_trip(path: str) -> Optional[Trip]:
    """Parse a CarScanner CSV into a Trip. Returns None only if zero classified samples."""
    raw: dict[str, list[tuple[float, float]]] = defaultdict(list)
    t_min: Optional[float] = None
    t_max: Optional[float] = None
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        r = csv.reader(fh, delimiter=";")
        next(r, None)  # header
        for row in r:
            if len(row) < 4:
                continue
            t = _f(row[0])
            pid = row[1].strip().strip('"')
            v = _f(row[2])
            if t is None or v is None:
                continue
            key = classify(pid)
            if key is None:
                continue
            raw[key].append((t, v))
            if t_min is None or t < t_min:
                t_min = t
            if t_max is None or t > t_max:
                t_max = t
    if not raw:
        return None
    # Preserve insertion order (dict iteration is stable in 3.7+), but sort per-key points by t.
    series = {k: sorted(pts) for k, pts in raw.items()}
    duration = (t_max - t_min) if (t_min is not None and t_max is not None) else 0.0
    return Trip(
        path=os.path.basename(path),
        start=parse_trip_start(path),
        duration_s=duration,
        series=series,
    )
