#!/usr/bin/env python3
"""Stage 1: scan CarScanner CSVs, build per-trip and regen-event summary."""
import argparse, csv, glob, os, re, sys, json, time
from collections import defaultdict
from datetime import datetime

# Substring match, first hit wins; order matters (longer prefixes first).
NEEDLES = [
    ("Regeneration in progress", "regen"),
    ("DPF differential pressure", "dpf_dp"),
    ("DPF/GPF soot", "soot_trig"),
    ("Average Time Between PF Regens", "avg_t_regen"),
    ("Average Distance Between PF Regens", "avg_d_regen"),
    ("Distance since last regeneration", "d_since_regen"),
    ("Total distance travelled", "odo_total"),
    ("Distance travelled", "trip_dist"),
    ("Vehicle speed", "speed"),
    ("Engine RPM x1000", "rpm_k"),
    ("Engine RPM", "rpm"),
    ("Engine coolant temperature", "coolant_t"),
    ("Engine oil temperature", "oil_t"),
    ("Oil level", "oil_lvl"),
    ("NOx adsorber regeneration status", "nox_regen"),
]
_pid_cache = {}
def classify(pid):
    if pid in _pid_cache: return _pid_cache[pid]
    res = None
    for needle, key in NEEDLES:
        if needle in pid:
            res = key; break
    _pid_cache[pid] = res
    return res

def parse_fname(p):
    m = re.search(r"(\d{4}-\d{2}-\d{2}) (\d{2})-(\d{2})-(\d{2})\.csv$", p)
    if not m: return None
    return datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}",
                             "%Y-%m-%d %H:%M:%S")

def f(x):
    try: return float(x)
    except: return None

def scan_file(path):
    start = parse_fname(path)
    # Track time series per key
    series = defaultdict(list)  # key -> [(t, v)]
    t_min, t_max = None, None
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        r = csv.reader(fh, delimiter=";")
        next(r, None)
        for row in r:
            if len(row) < 4: continue
            t = f(row[0]); pid = row[1].strip(); v = f(row[2])
            if t is None or v is None: continue
            k = classify(pid)
            if k is None: continue
            series[k].append((t, v))
            if t_min is None or t < t_min: t_min = t
            if t_max is None or t > t_max: t_max = t
    summary = {
        "file": os.path.basename(path),
        "start": start.isoformat() if start else None,
        "duration_s": (t_max - t_min) if (t_min and t_max) else 0.0,
    }
    # snapshot last + min/max
    for k, pts in series.items():
        vals = [v for _, v in pts]
        if not vals: continue
        summary[f"{k}_first"] = vals[0]
        summary[f"{k}_last"] = vals[-1]
        summary[f"{k}_min"] = min(vals)
        summary[f"{k}_max"] = max(vals)
    # regen events: contiguous spans where regen==2 (active)
    events = []
    regen = series.get("regen", [])
    if regen:
        # Build index by time of speed, rpm, coolant, soot etc. for sampling
        def latest_before(key, t):
            arr = series.get(key, [])
            if not arr: return None
            # binary search would be ideal but linear OK for small N
            v = None
            for tt, vv in arr:
                if tt <= t: v = vv
                else: break
            return v
        cur = None
        for t, v in regen:
            active = (v >= 1.5)  # 2 == active
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
    # compact events
    compact = []
    for e in events:
        def stat(arr):
            if not arr: return None
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

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default="./data",
                    help="directory holding CarScanner *.csv exports (default: ./data)")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.data_dir, "*.csv")))
    if not files:
        print(f"No CSVs found in {args.data_dir!r}; drop CarScanner exports there or pass --data-dir DIR.",
              file=sys.stderr)
        sys.exit(1)

    t0 = time.perf_counter()
    out = []
    for i, p in enumerate(files):
        try:
            out.append(scan_file(p))
        except Exception as ex:
            print(f"ERR {p}: {ex}", file=sys.stderr)

    # PID coverage summary: which keys appear in any per-trip summary?
    seen = set()
    for s in out:
        for field in s:
            for _, key in NEEDLES:
                if field == f"{key}_last":
                    seen.add(key)
    all_keys = {k for _, k in NEEDLES}
    missing = sorted(all_keys - seen)
    coverage = "found: " + (", ".join(sorted(seen)) or "(none)")
    if missing:
        coverage += "  |  missing: " + ", ".join(missing)

    out_path = os.path.join(args.data_dir, "summary.json")
    with open(out_path, "w") as fh:
        json.dump(out, fh, default=str)
    dt = time.perf_counter() - t0
    print(f"Scanned {len(files)} CSVs -> {out_path} ({dt:.1f}s)")
    print(f"  PIDs {coverage}", file=sys.stderr)

if __name__ == "__main__": main()
