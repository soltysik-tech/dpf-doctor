#!/usr/bin/env python3
"""Stage 2: capture full per-trip time series (1Hz-downsampled) for selected PIDs."""
import argparse, glob, os, json, sys, time
from typing import Optional
from reader import read_trip, Trip

def deep_trip(trip: Trip) -> Optional[dict]:
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
    for k in ["regen","dpf_dp","soot_trig","d_since_regen","oil_t","coolant_t","iat",
              "rpm","speed","egr_duty","maf","load","tps","fuel_rate","fuel_l100",
              "trip_dist","odo_total","power_maf","avg_d_regen"]:
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
    rec["b_regen"] = buckets_1hz("regen")
    rec["b_soot"]  = buckets_1hz("soot_trig")
    rec["b_speed"] = buckets_1hz("speed")
    rec["b_rpm"]   = buckets_1hz("rpm")
    rec["b_fuel_rate"] = buckets_1hz("fuel_rate")
    rec["b_egr"]   = buckets_1hz("egr_duty")
    rec["b_load"]  = buckets_1hz("load")
    rec["b_iat"]   = buckets_1hz("iat")
    rec["b_coolant"] = buckets_1hz("coolant_t")
    rec["b_oil"]   = buckets_1hz("oil_t")
    rec["b_dpf_dp"]= buckets_1hz("dpf_dp")
    rec["b_dist"]  = buckets_1hz("trip_dist")
    rec["t_range"] = [t0, t1]
    return rec

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
            trip = read_trip(p)
            if trip is None:
                continue
            r = deep_trip(trip)
            if r:
                out.append(r)
        except Exception as e:
            print(f"ERR {p}: {e}", file=sys.stderr)

    out_path = os.path.join(args.data_dir, "trips.json")
    with open(out_path, "w") as fh:
        json.dump(out, fh, default=str)
    dt = time.perf_counter() - t0
    print(f"Extracted {len(out)} trips -> {out_path} ({dt:.1f}s)")

if __name__ == "__main__": main()
