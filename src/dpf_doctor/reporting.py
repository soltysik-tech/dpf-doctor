"""Stage 4: build a human-readable DPF report from data/summary.json."""
import io
import json
import os
import statistics as st
import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO


def render(summary: list[dict], out: TextIO) -> None:
    """Render the report for one loaded summary.json into the given text stream."""
    S = [s for s in summary if s.get("start")]
    S.sort(key=lambda x: x["start"])

    if not S:
        return

    print("=== DPF Report ===", file=out)
    print(f"total trips logged     : {len(S)}", file=out)
    print(f"first log              : {S[0]['start']}", file=out)
    print(f"last log               : {S[-1]['start']}", file=out)

    events = []
    for s in S:
        fstart = datetime.fromisoformat(s["start"])
        for e in s.get("regen_events", []):
            ev = dict(e); ev["file"] = s["file"]; ev["file_start"] = fstart
            events.append(ev)
    active = [e for e in events if (e.get("duration_s") or 0) > 0]
    print(f"active regen events    : {len(active)}", file=out)

    trips_w_regen = sum(1 for s in S if (s.get("regen_max") or 0) >= 1.5)
    print(f"trips with active regen: {trips_w_regen}", file=out)

    soot_series = [(s["start"], s.get("soot_trig_last")) for s in S if s.get("soot_trig_last") is not None]
    if soot_series:
        print(f"\nSoot trigger % over time (last value per trip):", file=out)
        print(f"  min  {min(v for _,v in soot_series):.1f}%   max {max(v for _,v in soot_series):.1f}%", file=out)
        step = max(1, len(soot_series) // 20)
        for i in range(0, len(soot_series), step):
            t, v = soot_series[i]; print(f"  {t[:16]}  {v:6.1f} %", file=out)
    else:
        print("\nSoot trigger: N/A - required PID 'DPF/GPF soot' not in logs.", file=out)

    dp_lasts = [s["dpf_dp_last"] for s in S if s.get("dpf_dp_last") is not None]
    dp_maxes = [s["dpf_dp_max"] for s in S if s.get("dpf_dp_max") is not None]
    if dp_lasts:
        print(f"\nDPF differential pressure (kPa, last-of-trip):", file=out)
        print(f"  avg {st.mean(dp_lasts):.2f}  median {st.median(dp_lasts):.2f}  min {min(dp_lasts):.2f}  max {max(dp_lasts):.2f}", file=out)
        if dp_maxes:
            print(f"  per-trip MAX dp avg {st.mean(dp_maxes):.2f}  overall max {max(dp_maxes):.2f}", file=out)
    else:
        print("\nDPF dp: N/A - required PID 'DPF differential pressure' not in logs.", file=out)

    ad = [s.get("avg_d_regen_last") for s in S if s.get("avg_d_regen_last") not in (None, 0)]
    at = [s.get("avg_t_regen_last") for s in S if s.get("avg_t_regen_last") not in (None, 0)]
    if ad:
        print(f"\nECM-reported average distance between regens (km):", file=out)
        print(f"  start {ad[0]:.0f}  end {ad[-1]:.0f}  min {min(ad):.0f}  max {max(ad):.0f}  avg {st.mean(ad):.0f}", file=out)
    if at:
        print(f"ECM-reported average time between regens (s):", file=out)
        print(f"  start {at[0]:.0f}  end {at[-1]:.0f}  min {min(at):.0f}  max {max(at):.0f}  avg {st.mean(at):.0f}", file=out)

    dsr = [(s["start"], s.get("d_since_regen_last")) for s in S if s.get("d_since_regen_last") is not None]
    if dsr:
        print(f"\n'Distance since last regen' last value per trip (km):", file=out)
        step = max(1, len(dsr) // 20)
        for i in range(0, len(dsr), step):
            t, v = dsr[i]; print(f"  {t[:16]}  {v:7.2f} km", file=out)

    if active:
        print(f"\n=== Active regen events ({len(active)}) ===", file=out)
        durs = [e["duration_s"] for e in active]
        print(f"duration s: avg {st.mean(durs):.0f}  med {st.median(durs):.0f}  min {min(durs):.0f}  max {max(durs):.0f}", file=out)

        soot_deltas = [e["soot_start"] - e["soot_end"] for e in active
                       if e.get("soot_start") is not None and e.get("soot_end") is not None]
        if soot_deltas:
            print(f"soot drop (start-end %): avg {st.mean(soot_deltas):.1f}  max {max(soot_deltas):.1f}  min {min(soot_deltas):.1f}", file=out)
        dp_drops = [e["dp_start"] - e["dp_end"] for e in active
                    if e.get("dp_start") is not None and e.get("dp_end") is not None]
        if dp_drops:
            print(f"dp drop start-end (kPa): avg {st.mean(dp_drops):.2f}  max {max(dp_drops):.2f}  min {min(dp_drops):.2f}", file=out)

        n_show = min(30, len(active))
        print(f"\nLatest {n_show} active regens:", file=out)
        print(f"{'date':16} {'dur s':>6} {'soot %s>e':>11} {'dp s>e kPa':>12} {'speed avg':>9} {'rpm avg':>8} {'cool C':>7} {'trunc':>5}", file=out)
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
                  f'{(co if co is not None else 0):7.1f} {"Y" if e.get("truncated") else "":>5}', file=out)

        abs_times = sorted([e["file_start"].timestamp() for e in active])
        if len(abs_times) > 1:
            diffs = [(abs_times[i+1] - abs_times[i]) / 3600 for i in range(len(abs_times) - 1)]
            print(f"\nIntervals between regen events (hours):", file=out)
            print(f"  avg {st.mean(diffs):.1f}  med {st.median(diffs):.1f}  min {min(diffs):.1f}  max {max(diffs):.1f}", file=out)
    else:
        print("\nNo active regeneration events detected in the logs.", file=out)


def render_to_string(summary: list[dict]) -> str:
    buf = io.StringIO()
    render(summary, buf)
    return buf.getvalue()


def run(data_dir: str) -> None:
    """Load summary.json from data_dir and print the report to stdout."""
    summary_path = Path(data_dir) / "summary.json"
    if not summary_path.exists():
        print(f"{summary_path} not found; run `dpf-doctor analyze` first (or `dpf-doctor run`).",
              file=sys.stderr)
        sys.exit(1)

    with open(summary_path) as fh:
        summary = json.load(fh)
    filtered = [s for s in summary if s.get("start")]
    if not filtered:
        print("No trips found in summary.json. Are your CarScanner CSVs named YYYY-MM-DD HH-MM-SS.csv?",
              file=sys.stderr)
        sys.exit(1)

    render(summary, sys.stdout)
