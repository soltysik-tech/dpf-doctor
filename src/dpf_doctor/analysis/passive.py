"""Stage 3: infer passive regeneration episodes from soot-trigger drops under load."""
import bisect
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from dpf_doctor.analysis.timeseries import TS
from dpf_doctor.io.reader import read_trip
from dpf_doctor.trip import Trip

# Thresholds
WIN_MIN, WIN_MAX = 60, 300
DROP_MIN = 1.5
OIL_MIN, COOLANT_MIN, SPEED_MIN, RPM_MIN, MAF_MIN = 80.0, 85.0, 50.0, 1500.0, 15.0
MIN_EP = 60


def detect_passive(trip: Trip) -> dict:
    series = trip.series
    ts_obj = {k: TS(v) for k, v in series.items()}  # series values already sorted by reader
    soot = series.get("soot_trig", [])

    out = {
        "file": trip.path,
        "start": trip.start.isoformat() if trip.start else None,
    }

    if len(soot) < 10:
        out["passive_episodes"] = []
        out["passive_count"] = 0
        out["passive_total_drop"] = 0
        out["passive_total_s"] = 0
        return out

    out["duration_s"] = round(soot[-1][0] - soot[0][0], 1)
    out["soot_start"] = round(soot[0][1], 1)
    out["soot_end"] = round(soot[-1][1], 1)

    # active spans
    active = []
    cur = None
    for t, v in series.get("regen", []):
        a = v >= 1.5
        if a and cur is None: cur = [t, t]
        elif a: cur[1] = t
        elif cur is not None:
            if cur[1] - cur[0] >= 5: active.append((cur[0], cur[1]))
            cur = None
    if cur and cur[1] - cur[0] >= 5: active.append((cur[0], cur[1]))
    active_starts = [s for s, _ in active]
    active_ends = [e for _, e in active]
    out["active_spans"] = len(active)

    # regen completed?
    ds = series.get("d_since_regen", [])
    out["regen_completed"] = False
    for i in range(1, len(ds)):
        if ds[i][1] < ds[i-1][1] - 10:
            out["regen_completed"] = True
            break

    def in_active(t):
        if not active: return False
        i = bisect.bisect_right(active_starts, t + 30) - 1
        if i < 0: return False
        return active_starts[i] - 30 <= t <= active_ends[i] + 30

    oil_t = ts_obj.get("oil_t", TS([]))
    coolant = ts_obj.get("coolant_t", TS([]))
    speed = ts_obj.get("speed", TS([]))
    rpm = ts_obj.get("rpm", TS([]))
    maf = ts_obj.get("maf", TS([]))

    def conditions_ok(t):
        if in_active(t): return False
        oil = oil_t.at(t); cool = coolant.at(t)
        warm = True
        if oil is not None: warm = oil >= OIL_MIN
        elif cool is not None: warm = cool >= COOLANT_MIN
        if not warm: return False
        sp = speed.at(t); rp = rpm.at(t)
        loaded = False
        if sp is not None and sp >= SPEED_MIN: loaded = True
        elif rp is not None and rp >= RPM_MIN: loaded = True
        elif sp is None and rp is None: loaded = True
        if not loaded: return False
        mf = maf.at(t)
        if mf is not None and mf < MAF_MIN: return False
        return True

    # Greedy episodes: scan forward, mark start when conditions ok and soot dropping
    episodes = []
    i = 0
    n = len(soot)
    while i < n:
        t_i, sv_i = soot[i]
        if not conditions_ok(t_i):
            i += 1; continue
        # extend while conditions hold and soot not rising significantly
        j = i + 1
        min_v = sv_i; min_j = i
        while j < n:
            t_j, sv_j = soot[j]
            if t_j - t_i > WIN_MAX: break
            if not conditions_ok(t_j): break
            if sv_j > min_v + 1.0: break  # soot rising back, end episode
            if sv_j < min_v:
                min_v = sv_j; min_j = j
            j += 1
        drop = sv_i - min_v
        dur = soot[min_j][0] - t_i
        if drop >= DROP_MIN and dur >= MIN_EP:
            t_start = t_i
            sps, oils, mafs, rpms = [], [], [], []
            for k in range(i, min_j+1):
                t_k = soot[k][0]
                sp_v = speed.at(t_k); oil_v = oil_t.at(t_k)
                maf_v = maf.at(t_k); rpm_v = rpm.at(t_k)
                if sp_v is not None: sps.append(sp_v)
                if oil_v is not None: oils.append(oil_v)
                if maf_v is not None: mafs.append(maf_v)
                if rpm_v is not None: rpms.append(rpm_v)
            episodes.append({
                "t_start": round(t_start - soot[0][0]),
                "duration_s": round(dur),
                "soot_start": round(sv_i, 1),
                "soot_end": round(min_v, 1),
                "soot_drop": round(drop, 1),
                "burn_rate_per_min": round(drop / (dur/60), 2),
                "speed_avg": round(sum(sps)/len(sps), 0) if sps else None,
                "oil_avg": round(sum(oils)/len(oils), 0) if oils else None,
                "maf_avg": round(sum(mafs)/len(mafs), 1) if mafs else None,
                "rpm_avg": round(sum(rpms)/len(rpms), 0) if rpms else None,
            })
            i = min_j + 1
        else:
            i = j if j > i else i + 1

    out["passive_episodes"] = episodes
    out["passive_count"] = len(episodes)
    out["passive_total_drop"] = round(sum(e["soot_drop"] for e in episodes), 1)
    out["passive_total_s"] = round(sum(e["duration_s"] for e in episodes), 0)
    return out


def _print_summary(results: list[dict]) -> None:
    n = len(results)
    n_with = sum(1 for r in results if r.get("passive_count", 0) > 0)
    n_completed = sum(1 for r in results if r.get("regen_completed"))
    total_eps = sum(r.get("passive_count", 0) for r in results)
    total_drop = sum(r.get("passive_total_drop", 0) for r in results)
    total_t = sum(r.get("passive_total_s", 0) for r in results)

    print(f"\n=== GLOBAL (v3) ===")
    print(f"Files: {n}")
    print(f"Files with passive: {n_with} ({100*n_with/n:.1f}%)")
    print(f"Files with regen completed: {n_completed}")
    print(f"Total passive episodes: {total_eps}")
    print(f"Total soot drop via passive: {total_drop:.1f} pkt")
    print(f"Total passive time: {total_t/3600:.1f} h ({total_t/60:.0f} min)")
    if total_eps:
        print(f"Avg drop/episode: {total_drop/total_eps:.2f} pkt, avg dur: {total_t/total_eps:.0f}s")

    by_year = defaultdict(lambda: {"eps":0,"drop":0,"t":0,"files":0,"files_with":0})
    for r in results:
        if not r.get("start"): continue
        yr = r["start"][:4]
        by_year[yr]["files"] += 1
        by_year[yr]["eps"] += r.get("passive_count", 0)
        by_year[yr]["drop"] += r.get("passive_total_drop", 0)
        by_year[yr]["t"] += r.get("passive_total_s", 0)
        if r.get("passive_count", 0) > 0: by_year[yr]["files_with"] += 1

    print(f"\n=== BY YEAR ===")
    print(f"{'year':6s} {'files':6s} {'with_passive':14s} {'eps':6s} {'drop':10s} {'min':10s}")
    for yr in sorted(by_year):
        d = by_year[yr]
        pct = 100*d['files_with']/d['files']
        print(f"{yr:6s} {d['files']:6d} {d['files_with']:6d} ({pct:4.1f}%)  {d['eps']:6d} {d['drop']:10.1f} {d['t']/60:10.1f}")

    all_eps = []
    for r in results:
        for e in r.get("passive_episodes", []):
            all_eps.append({**e, "file": r["file"][:30]})
    all_eps.sort(key=lambda x: x["soot_drop"], reverse=True)
    print(f"\n=== TOP 25 PASSIVE EPISODES ===")
    print(f"{'file':30s} {'dur_s':6s} {'drop':6s} {'rate':9s} {'sp':5s} {'oil':5s} {'maf':6s} {'rpm':5s}")
    for e in all_eps[:25]:
        print(f"{e['file']:30s} {e['duration_s']:6.0f} {e['soot_drop']:6.1f} {e['burn_rate_per_min']:5.2f}/min "
              f"{str(e['speed_avg']):>5s} {str(e['oil_avg']):>5s} {str(e['maf_avg']):>6s} {str(e['rpm_avg']):>5s}")

    print(f"\n=== BURN RATE vs AVG SPEED ===")
    buckets = [(0,40,"city slow"), (40,60,"city fast"), (60,80,"backroad"),
               (80,100,"main road"), (100,120,"highway"), (120,200,"fast highway")]
    for lo, hi, lab in buckets:
        eps_b = [e for e in all_eps if e["speed_avg"] is not None and lo <= e["speed_avg"] < hi]
        if eps_b:
            drops = [e["soot_drop"] for e in eps_b]
            rates = [e["burn_rate_per_min"] for e in eps_b]
            print(f"  {lab:14s} ({lo:3d}-{hi:3d} km/h): n={len(eps_b):3d}  avg_drop={sum(drops)/len(drops):.1f} pkt  rate={sum(rates)/len(rates):.2f} pkt/min")


def run(data_dir: str, files: Optional[list[str]] = None, print_summary: bool = True) -> Path:
    """Detect passive regens across every CSV in data_dir, write passive_summary.json, return its path."""
    from dpf_doctor.cli._common import csv_files_or_exit
    if files is None:
        files = csv_files_or_exit(data_dir)

    t0 = time.perf_counter()
    results: list[dict] = []
    for p in files:
        try:
            trip = read_trip(p)
            if trip is None:
                continue
            results.append(detect_passive(trip))
        except Exception as ex:
            print(f"ERR {p}: {ex}", file=sys.stderr)

    if print_summary and results:
        _print_summary(results)

    out_path = Path(data_dir) / "passive_summary.json"
    with open(out_path, "w") as fh:
        json.dump(results, fh, default=str)
    dt = time.perf_counter() - t0
    print(f"\nSaved passive-detection results -> {out_path} ({dt:.1f}s)")
    return out_path
