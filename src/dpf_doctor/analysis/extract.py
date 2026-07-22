"""Stage 2: capture full per-trip time series (1Hz-downsampled) for selected PIDs."""
import json
import sys
import time
from pathlib import Path
from typing import Optional

from dpf_doctor.io.reader import read_trip
from dpf_doctor.pids import PID_KEYS
from dpf_doctor.trip import Trip

# Which PIDs get stats + 1Hz buckets in the extracted per-trip record.
_EXTRACT_KEYS: tuple[str, ...] = (
    "regen", "dpf_dp", "soot_trig", "d_since_regen", "oil_t", "coolant_t", "iat",
    "rpm", "speed", "egr_duty", "maf", "load", "tps", "fuel_rate", "fuel_l100",
    "trip_dist", "odo_total", "power_maf", "avg_d_regen",
)
assert set(_EXTRACT_KEYS) <= set(PID_KEYS), (
    f"_EXTRACT_KEYS drift from pids.PID_KEYS: {set(_EXTRACT_KEYS) - set(PID_KEYS)}"
)

# Subset that gets 1Hz bucket dumps. Ordered to preserve historical JSON key order.
_BUCKET_KEYS: tuple[tuple[str, str], ...] = (
    ("b_regen", "regen"),
    ("b_soot", "soot_trig"),
    ("b_speed", "speed"),
    ("b_rpm", "rpm"),
    ("b_fuel_rate", "fuel_rate"),
    ("b_egr", "egr_duty"),
    ("b_load", "load"),
    ("b_iat", "iat"),
    ("b_coolant", "coolant_t"),
    ("b_oil", "oil_t"),
    ("b_dpf_dp", "dpf_dp"),
    ("b_dist", "trip_dist"),
)


def extract_trip(trip: Trip) -> Optional[dict]:
    s = trip.series
    if not s:
        return None
    ts = [pt[0] for arr in s.values() for pt in arr]
    if not ts:
        return None
    t0 = min(ts); t1 = max(ts)
    rec = {"file": trip.path,
           "start": trip.start.isoformat() if trip.start else None,
           "duration_s": t1 - t0}

    def stats(key):
        arr = s.get(key, [])
        if not arr:
            return None
        vals = [v for _, v in arr]
        return {"first": vals[0], "last": vals[-1],
                "min": min(vals), "max": max(vals),
                "avg": sum(vals)/len(vals), "n": len(vals)}
    for k in _EXTRACT_KEYS:
        st = stats(k)
        if st:
            rec[k] = st

    def buckets_1hz(key):
        arr = s.get(key, [])
        out = {}
        for t, v in arr:
            ti = int(t)
            out[ti] = v
        return out
    for out_key, src_key in _BUCKET_KEYS:
        rec[out_key] = buckets_1hz(src_key)
    rec["t_range"] = [t0, t1]
    return rec


def run(data_dir: str, files: Optional[list[str]] = None) -> Path:
    """Extract every CSV in data_dir, write trips.json, return its path."""
    from dpf_doctor.cli._common import csv_files_or_exit
    if files is None:
        files = csv_files_or_exit(data_dir)

    t0 = time.perf_counter()
    out: list[dict] = []
    for p in files:
        try:
            trip = read_trip(p)
            if trip is None:
                continue
            r = extract_trip(trip)
            if r:
                out.append(r)
        except Exception as e:
            print(f"ERR {p}: {e}", file=sys.stderr)

    out_path = Path(data_dir) / "trips.json"
    with open(out_path, "w") as fh:
        json.dump(out, fh, default=str)
    dt = time.perf_counter() - t0
    print(f"Extracted {len(out)} trips -> {out_path} ({dt:.1f}s)")
    return out_path
