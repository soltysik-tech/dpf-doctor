# dpf-doctor

Analyze OBD-II logs from a Volvo XC60 II to check whether your Diesel Particulate Filter is healthy, when it last regenerated, and how much soot it is accumulating between burns.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)

## What it does

Point it at a folder of CarScanner CSV exports and it produces a plain-text report telling you:

- How many active DPF regenerations happened, when, how long they took, and how much soot each one burned off
- Your DPF differential-pressure baseline over time (rising = clogging trouble)
- Soot accumulation rate (percent-per-kilometre between regenerations)
- Trip taxonomy (how much of your driving is short cold trips vs sustained highway runs, since only the latter lets the DPF passively regenerate)
- Seasonal pattern (are you doing more regens in winter?)
- Regen fuel efficiency (if your CarScanner profile logged instantaneous fuel rate)

Sample output (from the single trip shipped as `data/2026-06-23 10-26-50.csv`; drop your own CSVs into `data/` and rerun to get the full picture — the aggregate sections gain shape only once you have many trips):

```
=== DPF Report ===
total trips logged     : 1
first log              : 2026-06-23T10:26:50
last log               : 2026-06-23T10:26:50
active regen events    : 0
trips with active regen: 0

Soot trigger % over time (last value per trip):
  min  97.6%   max 97.6%
  2026-06-23T10:26    97.6 %

DPF differential pressure (kPa, last-of-trip):
  avg 5.40  median 5.40  min 5.40  max 5.40
  per-trip MAX dp avg 5.40  overall max 5.40

ECM-reported average distance between regens (km):
  start 637  end 637  min 637  max 637  avg 637
ECM-reported average time between regens (s):
  start 1196  end 1196  min 1196  max 1196  avg 1196

'Distance since last regen' last value per trip (km):
  2026-06-23T10:26   603.52 km

No active regeneration events detected in the logs.
```

With a few hundred trips loaded, the report grows tables of recent active regenerations (with soot start-to-end drops, dp deltas, average speed/RPM/coolant), regen-interval histograms, and passive-regen episode detail.

## Requirements

- Volvo XC60 II (2018+, VEA-platform D4 diesel). May work on other VEA Volvos; PRs welcome to extend.
- CarScanner (Android/iOS) with the **English** PID profile, logging to CSV. Polish or other locales are not supported out of the box.
- Python 3.10+; no other dependencies.

The tool assumes your CarScanner CSVs use the semicolon separator and the standard column set (`SECONDS;PID;VALUE;UNITS;LATITUDE;LONGTITUDE`). GPS columns are not read, so you can strip them if you prefer not to keep coordinate history around.

## Quickstart

```
git clone https://github.com/soltysik-tech/dpf-doctor
cd dpf-doctor
pip install -e .
cp ~/carscanner-exports/*.csv data/
dpf-doctor run
```

That's it. `dpf-doctor run` runs the four pipeline stages in order and prints the report at the end. A hand-anonymized sample trip ships at `data/2026-06-23 10-26-50.csv` (GPS columns stripped) so the pipeline runs end-to-end on a fresh clone.

Individual stages if you want them:

```
dpf-doctor analyze    # data/*.csv -> data/summary.json (per-trip)
dpf-doctor extract    # data/*.csv -> data/trips.json (1Hz time series)
dpf-doctor passive    # passive-regen detection -> data/passive_summary.json
dpf-doctor report     # reads summary.json -> stdout report
```

All subcommands accept `--data-dir DIR` to point somewhere other than `./data/`.

## Optional: virtualenv

Not needed (zero dependencies), but if you prefer isolation:

```
python -m venv .venv && source .venv/bin/activate
```

## What a DPF is (short primer)

Diesel engines produce soot. Modern diesels trap it in a ceramic filter (the DPF) in the exhaust, then periodically burn the trapped soot off inside the filter itself. That burn is called a **regeneration**.

Three flavours: **passive** (happens silently when exhaust gets hot enough on a sustained highway run), **active** (ECU-commanded, extra fuel injected to heat the filter to ~600 C, takes 10-20 min), and **forced** (dealer tool, engine at standstill). Active regen needs the trip to last 15-25 min at operating temperature; if you interrupt it, the burn stays incomplete and the ECU tries again next trip.

Failure modes this tool helps you spot:

- Rising DPF differential pressure over months = the filter is clogging faster than it can burn off (short-trip driver)
- Short-duration regen attempts that don't drop the soot trigger = trips too short for a complete burn
- Long gap since last regen + high soot trigger = imminent regen or a sensor problem

The "soot trigger" PID this tool relies on is a normalized 0-100% value the ECU uses to decide when to trigger a burn, not raw soot mass. Open an issue if you want more depth on the semantics or the failure-mode heuristics.

## How the pipeline works

1. `dpf-doctor analyze` scans every CSV and produces a per-trip summary (first/last/min/max of each PID, regen events detected, trip duration and distance).
2. `dpf-doctor extract` scans every CSV again and produces a per-trip 1Hz time series for the PIDs used in richer analyses.
3. `dpf-doctor passive` looks at the time series and infers **passive regeneration** events - the ECU never flags these directly, but you can detect them from soot-trigger drops during sustained high load.
4. `dpf-doctor report` reads `summary.json` and prints the report.

The intermediate JSONs land under `data/` and are gitignored. Rerun the pipeline whenever you add new CSVs to `data/`.

## Contributing

PRs welcome, especially for:

- Extending PID matching to other Volvo diesel models (Denso-ECU-based cars share a lot of the same PID surface)
- Additional analyses that use PIDs the current report doesn't touch

Open an issue first for anything larger than a small fix.

## License

MIT - see [LICENSE](LICENSE). Copyright (c) 2026 Mateusz Soltysik.
