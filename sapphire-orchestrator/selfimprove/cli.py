"""CLI for the active-learning feedback path (spec §6.3): ingest a real/wet-lab outcome for a
proposed experiment, or write the metrics report."""
from __future__ import annotations

import argparse

from memory import record_outcome
from .metrics import write_report


def main(argv) -> int:
    parser = argparse.ArgumentParser(prog="selfimprove", description="Sapphire self-improvement loop CLI")
    sub = parser.add_subparsers(dest="cmd")

    ro = sub.add_parser("record-outcome", help="ingest an outcome for a proposed experiment")
    ro.add_argument("proposal_id")
    ro.add_argument("result", choices=["confirmed", "refuted", "partial"])
    ro.add_argument("--data", default="")
    ro.add_argument("--source", default="")
    ro.add_argument("--engagement", default="")

    sub.add_parser("report", help="write the improvement metrics report")

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2     # argparse already printed the error (missing/invalid args)

    if args.cmd == "record-outcome":
        rec = record_outcome(args.proposal_id,
                             {"result": args.result, "data": args.data, "source": args.source},
                             engagement_id=args.engagement)
        print(rec["id"])
        return 0
    if args.cmd == "report":
        m = write_report()
        print(f"records={m['records']} accuracy={m['prediction_accuracy']} blindspots={m['blindspots']}")
        return 0

    parser.print_help()
    return 2
