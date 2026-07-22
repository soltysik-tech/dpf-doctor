"""Stage 4: build a human-readable DPF report from data/summary.json."""
import io
import json
import os
import statistics as st
import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO


_ANSI = {
    "reset":   "\x1b[0m",
    "bold":    "\x1b[1m",
    "title":   "\x1b[1;96m",   # bold bright cyan
    "section": "\x1b[1;93m",   # bold bright yellow
    "label":   "\x1b[36m",     # cyan
    "value":   "\x1b[92m",     # bright green
    "warn":    "\x1b[33m",     # yellow
    "table":   "\x1b[1;97m",   # bold bright white
}


class _Palette:
    """ANSI codes when colors are enabled, empty strings when they are not."""

    def __init__(self, enabled: bool):
        for k, v in _ANSI.items():
            setattr(self, k, v if enabled else "")

    def wrap(self, code: str, s: str) -> str:
        return f"{code}{s}{self.reset}" if code else s


def _palette_for(out: TextIO) -> _Palette:
    # NO_COLOR (no-color.org): any non-empty value disables color.
    if os.environ.get("NO_COLOR"):
        return _Palette(False)
    # FORCE_COLOR (supports-color convention): "0" disables, other non-empty values enable.
    force = os.environ.get("FORCE_COLOR")
    if force is not None and force != "0":
        return _Palette(True)
    if force == "0":
        return _Palette(False)
    isatty = getattr(out, "isatty", None)
    return _Palette(bool(isatty and isatty()))


def render(summary: list[dict], out: TextIO, *, palette: _Palette | None = None) -> None:
    """Render the report for one loaded summary.json into the given text stream.

    ``palette`` overrides the env/TTY-driven color decision; pass ``_Palette(False)``
    to guarantee plain output regardless of NO_COLOR/FORCE_COLOR.
    """
    S = [s for s in summary if s.get("start")]
    S.sort(key=lambda x: x["start"])

    if not S:
        return

    p = palette if palette is not None else _palette_for(out)
    w = p.wrap

    print(w(p.title, "=== DPF Report ==="), file=out)
    print(f"{w(p.label, 'total trips logged     :')} {w(p.value, str(len(S)))}", file=out)
    print(f"{w(p.label, 'first log              :')} {w(p.value, S[0]['start'])}", file=out)
    print(f"{w(p.label, 'last log               :')} {w(p.value, S[-1]['start'])}", file=out)

    events = []
    for s in S:
        fstart = datetime.fromisoformat(s["start"])
        for e in s.get("regen_events", []):
            ev = dict(e); ev["file"] = s["file"]; ev["file_start"] = fstart
            events.append(ev)
    active = [e for e in events if (e.get("duration_s") or 0) > 0]
    print(f"{w(p.label, 'active regen events    :')} {w(p.value, str(len(active)))}", file=out)

    trips_w_regen = sum(1 for s in S if (s.get("regen_max") or 0) >= 1.5)
    print(f"{w(p.label, 'trips with active regen:')} {w(p.value, str(trips_w_regen))}", file=out)

    soot_series = [(s["start"], s.get("soot_trig_last")) for s in S if s.get("soot_trig_last") is not None]
    if soot_series:
        print(f"\n{w(p.section, 'Soot trigger % over time (last value per trip):')}", file=out)
        mn = min(v for _, v in soot_series); mx = max(v for _, v in soot_series)
        print(f"  {w(p.label, 'min')}  {w(p.bold, f'{mn:.1f}%')}   {w(p.label, 'max')} {w(p.bold, f'{mx:.1f}%')}", file=out)
        step = max(1, len(soot_series) // 20)
        for i in range(0, len(soot_series), step):
            t, v = soot_series[i]; print(f"  {t[:16]}  {v:6.1f} %", file=out)
    else:
        msg = "Soot trigger: N/A - required PID 'DPF/GPF soot' not in logs."
        print(f"\n{w(p.warn, msg)}", file=out)

    dp_lasts = [s["dpf_dp_last"] for s in S if s.get("dpf_dp_last") is not None]
    dp_maxes = [s["dpf_dp_max"] for s in S if s.get("dpf_dp_max") is not None]
    if dp_lasts:
        print(f"\n{w(p.section, 'DPF differential pressure (kPa, last-of-trip):')}", file=out)
        print(f"  {w(p.label, 'avg')} {st.mean(dp_lasts):.2f}  {w(p.label, 'median')} {st.median(dp_lasts):.2f}  "
              f"{w(p.label, 'min')} {w(p.bold, f'{min(dp_lasts):.2f}')}  "
              f"{w(p.label, 'max')} {w(p.bold, f'{max(dp_lasts):.2f}')}", file=out)
        if dp_maxes:
            print(f"  {w(p.label, 'per-trip MAX dp avg')} {st.mean(dp_maxes):.2f}  "
                  f"{w(p.label, 'overall max')} {w(p.bold, f'{max(dp_maxes):.2f}')}", file=out)
    else:
        msg = "DPF dp: N/A - required PID 'DPF differential pressure' not in logs."
        print(f"\n{w(p.warn, msg)}", file=out)

    ad = [s.get("avg_d_regen_last") for s in S if s.get("avg_d_regen_last") not in (None, 0)]
    at = [s.get("avg_t_regen_last") for s in S if s.get("avg_t_regen_last") not in (None, 0)]
    if ad:
        print(f"\n{w(p.section, 'ECM-reported average distance between regens (km):')}", file=out)
        print(f"  {w(p.label, 'start')} {ad[0]:.0f}  {w(p.label, 'end')} {ad[-1]:.0f}  "
              f"{w(p.label, 'min')} {w(p.bold, f'{min(ad):.0f}')}  "
              f"{w(p.label, 'max')} {w(p.bold, f'{max(ad):.0f}')}  "
              f"{w(p.label, 'avg')} {st.mean(ad):.0f}", file=out)
    if at:
        print(f"{w(p.section, 'ECM-reported average time between regens (s):')}", file=out)
        print(f"  {w(p.label, 'start')} {at[0]:.0f}  {w(p.label, 'end')} {at[-1]:.0f}  "
              f"{w(p.label, 'min')} {w(p.bold, f'{min(at):.0f}')}  "
              f"{w(p.label, 'max')} {w(p.bold, f'{max(at):.0f}')}  "
              f"{w(p.label, 'avg')} {st.mean(at):.0f}", file=out)

    dsr = [(s["start"], s.get("d_since_regen_last")) for s in S if s.get("d_since_regen_last") is not None]
    if dsr:
        heading = "'Distance since last regen' last value per trip (km):"
        print(f"\n{w(p.section, heading)}", file=out)
        step = max(1, len(dsr) // 20)
        for i in range(0, len(dsr), step):
            t, v = dsr[i]; print(f"  {t[:16]}  {v:7.2f} km", file=out)

    if active:
        print(f"\n{w(p.title, f'=== Active regen events ({len(active)}) ===')}", file=out)
        durs = [e["duration_s"] for e in active]
        print(f"{w(p.label, 'duration s:')} {w(p.label, 'avg')} {st.mean(durs):.0f}  "
              f"{w(p.label, 'med')} {st.median(durs):.0f}  "
              f"{w(p.label, 'min')} {w(p.bold, f'{min(durs):.0f}')}  "
              f"{w(p.label, 'max')} {w(p.bold, f'{max(durs):.0f}')}", file=out)

        soot_deltas = [e["soot_start"] - e["soot_end"] for e in active
                       if e.get("soot_start") is not None and e.get("soot_end") is not None]
        if soot_deltas:
            print(f"{w(p.label, 'soot drop (start-end %):')} {w(p.label, 'avg')} {st.mean(soot_deltas):.1f}  "
                  f"{w(p.label, 'max')} {w(p.bold, f'{max(soot_deltas):.1f}')}  "
                  f"{w(p.label, 'min')} {w(p.bold, f'{min(soot_deltas):.1f}')}", file=out)
        dp_drops = [e["dp_start"] - e["dp_end"] for e in active
                    if e.get("dp_start") is not None and e.get("dp_end") is not None]
        if dp_drops:
            print(f"{w(p.label, 'dp drop start-end (kPa):')} {w(p.label, 'avg')} {st.mean(dp_drops):.2f}  "
                  f"{w(p.label, 'max')} {w(p.bold, f'{max(dp_drops):.2f}')}  "
                  f"{w(p.label, 'min')} {w(p.bold, f'{min(dp_drops):.2f}')}", file=out)

        n_show = min(30, len(active))
        print(f"\n{w(p.section, f'Latest {n_show} active regens:')}", file=out)
        header = f"{'date':16} {'dur s':>6} {'soot %s>e':>11} {'dp s>e kPa':>12} {'speed avg':>9} {'rpm avg':>8} {'cool C':>7} {'trunc':>5}"
        print(w(p.table, header), file=out)
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
            print(f"\n{w(p.section, 'Intervals between regen events (hours):')}", file=out)
            print(f"  {w(p.label, 'avg')} {st.mean(diffs):.1f}  {w(p.label, 'med')} {st.median(diffs):.1f}  "
                  f"{w(p.label, 'min')} {w(p.bold, f'{min(diffs):.1f}')}  "
                  f"{w(p.label, 'max')} {w(p.bold, f'{max(diffs):.1f}')}", file=out)
    else:
        print(f"\n{w(p.warn, 'No active regeneration events detected in the logs.')}", file=out)


def render_to_string(summary: list[dict]) -> str:
    """Render to a plain (uncolored) string, ignoring NO_COLOR/FORCE_COLOR."""
    buf = io.StringIO()
    render(summary, buf, palette=_Palette(False))
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
