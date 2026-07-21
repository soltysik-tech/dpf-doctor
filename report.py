#!/usr/bin/env python3
"""Stage 4: build a human-readable DPF report from data/summary.json."""
import argparse, json, os, sys, statistics as st
from datetime import datetime


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default="./data",
                    help="directory holding summary.json (default: ./data)")
    args = ap.parse_args()

    summary_path = os.path.join(args.data_dir, "summary.json")
    if not os.path.exists(summary_path):
        print(f"{summary_path} not found; run analyze.py first (or use run.py to run the whole pipeline).",
              file=sys.stderr)
        sys.exit(1)

    S = json.load(open(summary_path))
    S = [s for s in S if s.get("start")]
    S.sort(key=lambda x: x["start"])

    if not S:
        print("No trips found in summary.json. Are your CarScanner CSVs named YYYY-MM-DD HH-MM-SS.csv?",
              file=sys.stderr)
        sys.exit(1)

    print("=== DPF Report ===")
    print(f"total trips logged     : {len(S)}")
    print(f"first log              : {S[0]['start']}")
    print(f"last log               : {S[-1]['start']}")

    # Regen event roll-up
    events = []
    for s in S:
        fstart = datetime.fromisoformat(s["start"])
        for e in s.get("regen_events", []):
            ev = dict(e); ev["file"] = s["file"]; ev["file_start"] = fstart
            events.append(ev)
    active = [e for e in events if (e.get("duration_s") or 0) > 0]
    print(f"active regen events    : {len(active)}")

    trips_w_regen = sum(1 for s in S if (s.get("regen_max") or 0) >= 1.5)
    print(f"trips with active regen: {trips_w_regen}")

    # Soot trigger evolution over time
    soot_series = [(s["start"], s.get("soot_trig_last")) for s in S if s.get("soot_trig_last") is not None]
    if soot_series:
        print(f"\nSoot trigger % over time (last value per trip):")
        print(f"  min  {min(v for _,v in soot_series):.1f}%   max {max(v for _,v in soot_series):.1f}%")
        step = max(1, len(soot_series) // 20)
        for i in range(0, len(soot_series), step):
            t, v = soot_series[i]; print(f"  {t[:16]}  {v:6.1f} %")
    else:
        print("\nSoot trigger: N/A - required PID 'DPF/GPF soot' not in logs.")

    # DPF differential pressure
    dp_lasts = [s["dpf_dp_last"] for s in S if s.get("dpf_dp_last") is not None]
    dp_maxes = [s["dpf_dp_max"] for s in S if s.get("dpf_dp_max") is not None]
    if dp_lasts:
        print(f"\nDPF differential pressure (kPa, last-of-trip):")
        print(f"  avg {st.mean(dp_lasts):.2f}  median {st.median(dp_lasts):.2f}  min {min(dp_lasts):.2f}  max {max(dp_lasts):.2f}")
        if dp_maxes:
            print(f"  per-trip MAX dp avg {st.mean(dp_maxes):.2f}  overall max {max(dp_maxes):.2f}")
    else:
        print("\nDPF dp: N/A - required PID 'DPF differential pressure' not in logs.")

    # ECM-reported averages
    ad = [s.get("avg_d_regen_last") for s in S if s.get("avg_d_regen_last") not in (None, 0)]
    at = [s.get("avg_t_regen_last") for s in S if s.get("avg_t_regen_last") not in (None, 0)]
    if ad:
        print(f"\nECM-reported average distance between regens (km):")
        print(f"  start {ad[0]:.0f}  end {ad[-1]:.0f}  min {min(ad):.0f}  max {max(ad):.0f}  avg {st.mean(ad):.0f}")
    if at:
        print(f"ECM-reported average time between regens (s):")
        print(f"  start {at[0]:.0f}  end {at[-1]:.0f}  min {min(at):.0f}  max {max(at):.0f}  avg {st.mean(at):.0f}")

    # Distance since last regen evolution
    dsr = [(s["start"], s.get("d_since_regen_last")) for s in S if s.get("d_since_regen_last") is not None]
    if dsr:
        print(f"\n'Distance since last regen' last value per trip (km):")
        step = max(1, len(dsr) // 20)
        for i in range(0, len(dsr), step):
            t, v = dsr[i]; print(f"  {t[:16]}  {v:7.2f} km")

    # Active regen event details
    if active:
        print(f"\n=== Active regen events ({len(active)}) ===")
        durs = [e["duration_s"] for e in active]
        print(f"duration s: avg {st.mean(durs):.0f}  med {st.median(durs):.0f}  min {min(durs):.0f}  max {max(durs):.0f}")

        soot_deltas = [e["soot_start"] - e["soot_end"] for e in active
                       if e.get("soot_start") is not None and e.get("soot_end") is not None]
        if soot_deltas:
            print(f"soot drop (start-end %): avg {st.mean(soot_deltas):.1f}  max {max(soot_deltas):.1f}  min {min(soot_deltas):.1f}")
        dp_drops = [e["dp_start"] - e["dp_end"] for e in active
                    if e.get("dp_start") is not None and e.get("dp_end") is not None]
        if dp_drops:
            print(f"dp drop start-end (kPa): avg {st.mean(dp_drops):.2f}  max {max(dp_drops):.2f}  min {min(dp_drops):.2f}")

        n_show = min(30, len(active))
        print(f"\nLatest {n_show} active regens:")
        print(f"{'date':16} {'dur s':>6} {'soot %s>e':>11} {'dp s>e kPa':>12} {'speed avg':>9} {'rpm avg':>8} {'cool C':>7} {'trunc':>5}")
        for e in active[-n_show:]:
            sp = e["speed"]["avg"] if e.get("speed") else None
            rp = e["rpm"]["avg"] if e.get("rpm") else None
            co = e["coolant"]["avg"] if e.get("coolant") else None
            soot = (f'{e["soot_start"]:5.1f}>{e["soot_end"]:5.1f}'
                    if e.get("soot_start") is not None and e.get("soot_end") is not None else "    -      ")
            dp = (f'{e["dp_start"]:5.2f}>{e["dp_end"]:5.2f}'
                  if e.get("dp_start") is not None and e.get("dp_end") is not None else "     -      ")
            print(f'{e["file_start"].strftime("%Y-%m-%d %H:%M"):16} {e["duration_s"]:6.0f} {soot:>11} {dp:>12} '
                  f'{(sp if sp is not None else 0):9.1f} {(rp if rp is not None else 0):8.0f} '
                  f'{(co if co is not None else 0):7.1f} {"Y" if e.get("truncated") else "":>5}')

        abs_times = sorted([e["file_start"].timestamp() for e in active])
        if len(abs_times) > 1:
            diffs = [(abs_times[i+1] - abs_times[i]) / 3600 for i in range(len(abs_times) - 1)]
            print(f"\nIntervals between regen events (hours):")
            print(f"  avg {st.mean(diffs):.1f}  med {st.median(diffs):.1f}  min {min(diffs):.1f}  max {max(diffs):.1f}")
    else:
        print("\nNo active regeneration events detected in the logs.")


if __name__ == "__main__":
    main()
