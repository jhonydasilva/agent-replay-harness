"""Command-line interface for recording, replaying, injecting, and reporting."""

import argparse
import json
import sys
from pathlib import Path

from examples.demo_agent import record_example
from src.fault_injector import FaultSpecValidationError
from src.replayer import ReplayMismatchError, Replayer
from src.report import format_report, summarize_directory
from src.trace_schema import TraceValidationError, read_trace, write_trace


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-replay", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="Record a synthetic agent execution")
    record.add_argument("--output", default="runs/recorded.json")

    replay = sub.add_parser("replay", help="Replay a JSON trace without real external calls")
    replay.add_argument("trace")
    replay.add_argument("--output", default="runs/replayed.json")

    inject = sub.add_parser("inject", help="Replay with one controlled tool failure")
    inject.add_argument("trace")
    inject.add_argument("--fault", required=True)
    inject.add_argument("--output", default="runs/injected.json")

    report = sub.add_parser("report", help="Summarize locally stored trace files")
    report.add_argument("directory", nargs="?", default="runs/")
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "record":
            record_example(args.output)
        elif args.command in {"replay", "inject"}:
            trace = read_trace(args.trace)
            fault = None
            if args.command == "inject":
                try:
                    fault = json.loads(Path(args.fault).read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError) as exc:
                    raise FaultSpecValidationError(f"cannot read fault file: {exc}") from exc
            result = Replayer(trace, fault=fault).execute()
            if fault is not None and result.comparison["identical"]:
                raise ReplayMismatchError("fault injection produced no decision divergence")
            write_trace(args.output, result.trace)
            print(
                f"{args.command}: outcome={result.outcome}; "
                f"decisions_identical={result.comparison['identical']}; "
                f"first_divergence={result.comparison['first_divergence']}; "
                f"output={args.output}"
            )
        elif args.command == "report":
            print(format_report(summarize_directory(args.directory)))
    except (
        TraceValidationError,
        ReplayMismatchError,
        FaultSpecValidationError,
        ValueError,
        OSError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
