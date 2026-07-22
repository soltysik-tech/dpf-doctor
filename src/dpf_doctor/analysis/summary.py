"""Stage 1: scan CarScanner CSVs, build per-trip and regen-event summary."""
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from dpf_doctor.io.reader import read_trip
from dpf_doctor.pids import PID_KEYS
from dpf_doctor.trip import Trip

# Summary only tracks a subset of the shared PID registry.
_SUMMARY_KEYS = frozenset({
    "regen", "dpf_dp", "soot_trig", "avg_t_regen", "avg_d_regen",
    "d_since_regen", "odo_total", "trip_dist", "speed", "rpm_k", "rpm",
    "coolant_t", "oil_t", "oil_lvl", "nox_regen",
})
# Fail fast at import if a key was renamed in pids.py without updating this set.
assert _SUMMARY_KEYS <= set(PID_KEYS), (
    f"_SUMMARY_KEYS drift from pids.PID_KEYS: {_SUMMARY_KEYS - set(PID_KEYS)}"
)


def analyze_trip(trip: Trip) -> dict:
    series = {k: v for k, v in trip.series.items() if k in _SUMMARY_KEYS}
    summary = {
        "file": trip.path,
        "start": trip.start.isoformat() if trip.start else None,
        "duration_s": trip.duration_s,
    }
    for k, pts in series.items():
        vals = [v for _, v in pts]
        if not vals:
            continue
        summary[f"{k}_first"] = vals[0]
        summary[f"{k}_last"] = vals[-1]
        summary[f"{k}_min"] = min(vals)
        summary[f"{k}_max"] = max(vals)

    events = []
    regen = series.get("regen", [])
    if regen:
        def latest_before(key, t):
            arr = series.get(key, [])
            if not arr:
                return None
            v = None
            for tt, vv in arr:
                if tt <= t:
                    v = vv
                else:
                    break
            return v
        cur = None
        for t, v in regen:
            active = (v >= 1.5)
            if active and cur is None:
                cur = {"t_start": t,
                       "soot_start": latest_before("soot_trig", t),
                       "dp_start": latest_before("dpf_dp", t),
                       "d_since_start": latest_before("d_since_regen", t),
                       "speed_samples": [], "rpm_samples": [],
                       "coolant_samples": [], "dp_samples": [], "soot_samples": []}
            if cur is not None:
                sp = latest_before("speed", t); rp = latest_before("rpm", t)
                co = latest_before("coolant_t", t); dp = latest_before("dpf_dp", t)
                so = latest_before("soot_trig", t)
                if sp is not None: cur["speed_samples"].append(sp)
                if rp is not None: cur["rpm_samples"].append(rp)
                if co is not None: cur["coolant_samples"].append(co)
                if dp is not None: cur["dp_samples"].append(dp)
                if so is not None: cur["soot_samples"].append(so)
            if not active and cur is not None:
                cur["t_end"] = t
                cur["duration_s"] = t - cur["t_start"]
                cur["soot_end"] = latest_before("soot_trig", t)
                cur["dp_end"] = latest_before("dpf_dp", t)
                cur["d_since_end"] = latest_before("d_since_regen", t)
                events.append(cur); cur = None
        if cur is not None:
            cur["t_end"] = regen[-1][0]
            cur["duration_s"] = cur["t_end"] - cur["t_start"]
            cur["soot_end"] = latest_before("soot_trig", cur["t_end"])
            cur["dp_end"] = latest_before("dpf_dp", cur["t_end"])
            cur["d_since_end"] = latest_before("d_since_regen", cur["t_end"])
            cur["truncated"] = True
            events.append(cur)
    compact = []
    for e in events:
        def stat(arr):
            if not arr:
                return None
            return {"avg": sum(arr)/len(arr), "min": min(arr), "max": max(arr)}
        compact.append({
            "duration_s": round(e.get("duration_s", 0), 1),
            "soot_start": e.get("soot_start"), "soot_end": e.get("soot_end"),
            "dp_start": e.get("dp_start"), "dp_end": e.get("dp_end"),
            "d_since_start": e.get("d_since_start"), "d_since_end": e.get("d_since_end"),
            "speed": stat(e["speed_samples"]),
            "rpm": stat(e["rpm_samples"]),
            "coolant": stat(e["coolant_samples"]),
            "dp": stat(e["dp_samples"]),
            "soot": stat(e["soot_samples"]),
            "truncated": e.get("truncated", False),
        })
    summary["regen_events"] = compact
    summary["regen_active_count"] = len([e for e in compact if e["duration_s"] > 0])
    return summary


def run(data_dir: str, files: Optional[list[str]] = None) -> Path:
    """Analyze every CSV in data_dir, write summary.json, return its path."""
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
            out.append(analyze_trip(trip))
        except Exception as ex:
            print(f"ERR {p}: {ex}", file=sys.stderr)

    seen = set()
    for s in out:
        for field in s:
            for key in _SUMMARY_KEYS:
                if field == f"{key}_last":
                    seen.add(key)
    missing = sorted(set(_SUMMARY_KEYS) - seen)
    coverage = "found: " + (", ".join(sorted(seen)) or "(none)")
    if missing:
        coverage += "  |  missing: " + ", ".join(missing)

    out_path = Path(data_dir) / "summary.json"
    with open(out_path, "w") as fh:
        json.dump(out, fh, default=str)
    dt = time.perf_counter() - t0
    print(f"Scanned {len(files)} CSVs -> {out_path} ({dt:.1f}s)")
    print(f"  PIDs {coverage}", file=sys.stderr)
    return out_path
