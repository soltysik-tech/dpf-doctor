"""dpf-doctor CLI: subcommand dispatch to the pipeline stages."""
import argparse

from dpf_doctor.analysis import extract, passive, summary
from dpf_doctor.cli._common import add_data_dir
from dpf_doctor import pipeline, reporting


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="dpf-doctor",
        description="Analyze OBD-II logs for DPF regeneration health.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    p_run = sub.add_parser("run", help="run the full 4-stage pipeline (analyze -> extract -> passive -> report)")
    add_data_dir(p_run)

    p_analyze = sub.add_parser("analyze", help="stage 1: build per-trip and regen-event summary")
    add_data_dir(p_analyze)

    p_extract = sub.add_parser("extract", help="stage 2: capture per-trip time series (1Hz)")
    add_data_dir(p_extract)

    p_passive = sub.add_parser("passive", help="stage 3: infer passive regeneration episodes")
    add_data_dir(p_passive)

    p_report = sub.add_parser("report", help="stage 4: print human-readable report from summary.json")
    add_data_dir(p_report)

    return ap


def main() -> None:
    args = _build_parser().parse_args()
    if args.cmd == "run":
        pipeline.run_all(args.data_dir)
    elif args.cmd == "analyze":
        summary.run(args.data_dir)
    elif args.cmd == "extract":
        extract.run(args.data_dir)
    elif args.cmd == "passive":
        passive.run(args.data_dir)
    elif args.cmd == "report":
        reporting.run(args.data_dir)


if __name__ == "__main__":
    main()
