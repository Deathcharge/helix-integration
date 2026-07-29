"""Command-line interface for scanning and redacting integration payloads."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from contextlib import suppress
from pathlib import Path
from typing import Any, Final, TextIO

from . import __version__
from .redaction import RedactionLimitError, RedactionReport, Redactor

DEFAULT_MAX_BYTES: Final = 1024 * 1024
EXIT_CLEAN: Final = 0
EXIT_FINDINGS: Final = 1
EXIT_ERROR: Final = 2


class CLIError(ValueError):
    """An expected input or processing error safe to show to the user."""


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="samsarix-guard",
        description="Scan or redact sensitive values in local text, JSON, and JSONL payloads.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_input_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("input", nargs="?", default="-", help="input file, or - for stdin (default: -)")
        command.add_argument(
            "--format",
            choices=("auto", "text", "json", "jsonl"),
            default="auto",
            help="input format; auto uses the extension and content (default: auto)",
        )
        command.add_argument(
            "--max-bytes",
            type=_positive_int,
            default=DEFAULT_MAX_BYTES,
            help=f"maximum UTF-8 input size (default: {DEFAULT_MAX_BYTES})",
        )
        command.add_argument(
            "--sensitive-key",
            action="append",
            default=[],
            metavar="KEY",
            help="additional JSON key to redact; repeatable",
        )

    redact = subparsers.add_parser("redact", help="write a redacted copy of a payload")
    add_input_arguments(redact)
    redact.add_argument("-o", "--output", default="-", help="output file, or - for stdout (default: -)")
    redact.add_argument("--report", action="store_true", help="write a count-only JSON report to stderr")

    scan = subparsers.add_parser("scan", help="report findings without writing payload content")
    add_input_arguments(scan)
    return parser


def _read_input(name: str, max_bytes: int, stdin: TextIO) -> tuple[str, Path | None]:
    if name == "-":
        try:
            text = stdin.read(max_bytes + 1)
            input_size = len(text.encode("utf-8"))
        except (OSError, UnicodeError) as error:
            raise CLIError("cannot read UTF-8 input from stdin") from error
        if input_size > max_bytes:
            raise CLIError(f"stdin exceeds --max-bytes={max_bytes}")
        return text, None

    path = Path(name).expanduser()
    try:
        if not path.is_file():
            raise CLIError(f"input is not a file: {path}")
        with path.open("rb") as input_file:
            payload = input_file.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise CLIError(f"input exceeds --max-bytes={max_bytes}")
        return payload.decode("utf-8-sig"), path.resolve()
    except UnicodeDecodeError as error:
        raise CLIError(f"input is not valid UTF-8: {path}") from error
    except OSError as error:
        raise CLIError(f"cannot read input {path}: {error.strerror or error}") from error


def _resolve_format(requested: str, input_path: Path | None, text: str) -> str:
    if requested != "auto":
        return requested
    if input_path is not None:
        suffix = input_path.suffix.casefold()
        if suffix == ".json":
            return "json"
        if suffix in {".jsonl", ".ndjson"}:
            return "jsonl"
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        return "json"
    return "text"


def _reject_json_constant(value: str) -> None:
    raise CLIError(f"non-standard JSON constant {value!r} is not allowed")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise CLIError("duplicate JSON object keys are not allowed")
        output[key] = value
    return output


def _load_json(text: str) -> Any:
    return json.loads(
        text,
        parse_constant=_reject_json_constant,
        object_pairs_hook=_reject_duplicate_keys,
    )


def _process(text: str, format_name: str, redactor: Redactor) -> tuple[str, RedactionReport]:
    if format_name == "text":
        text_result = redactor.redact_text(text)
        return text_result.text, text_result.report
    if format_name == "json":
        try:
            data = _load_json(text)
        except json.JSONDecodeError as error:
            raise CLIError(f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}") from error
        except RecursionError as error:
            raise CLIError("JSON nesting exceeds the parser limit") from error
        data_result = redactor.redact_data(data)
        return (
            json.dumps(data_result.data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            data_result.report,
        )
    if format_name == "jsonl":
        output: list[str] = []
        counts: Counter[str] = Counter()
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                output.append("")
                continue
            try:
                data = _load_json(line)
            except json.JSONDecodeError as error:
                raise CLIError(
                    f"invalid JSONL record at line {line_number}, column {error.colno}: {error.msg}"
                ) from error
            except RecursionError as error:
                raise CLIError(f"JSONL nesting exceeds the parser limit at line {line_number}") from error
            data_result = redactor.redact_data(data)
            counts.update(data_result.report.counts)
            output.append(json.dumps(data_result.data, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        suffix = "\n" if text.endswith(("\n", "\r")) or output else ""
        return "\n".join(output) + suffix, RedactionReport(dict(sorted(counts.items())))
    raise CLIError(f"unsupported format: {format_name}")


def _report_json(report: RedactionReport, format_name: str) -> str:
    return json.dumps(
        {
            "changed": report.changed,
            "counts": report.counts,
            "detections": report.detection_count,
            "format": format_name,
        },
        sort_keys=True,
    )


def _write_output(text: str, output_name: str, input_path: Path | None, stdout: TextIO) -> None:
    if output_name == "-":
        try:
            stdout.write(text)
            stdout.flush()
        except (OSError, UnicodeError) as error:
            raise CLIError("cannot write redacted output to stdout") from error
        return

    output_path = Path(output_name).expanduser()
    try:
        resolved_output = output_path.resolve()
    except OSError as error:
        raise CLIError(f"cannot resolve output path {output_path}: {error.strerror or error}") from error
    if input_path is not None and resolved_output == input_path:
        raise CLIError("refusing to overwrite the input file; choose a different --output path")
    parent = resolved_output.parent
    if not parent.is_dir():
        raise CLIError(f"output directory does not exist: {parent}")

    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=parent,
            prefix=f".{resolved_output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name, resolved_output)
    except OSError as error:
        if temporary_name is not None:
            with suppress(OSError):
                Path(temporary_name).unlink(missing_ok=True)
        raise CLIError(f"cannot write output {output_path}: {error.strerror or error}") from error


def run(args: argparse.Namespace, *, stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
    text, input_path = _read_input(args.input, args.max_bytes, stdin)
    format_name = _resolve_format(args.format, input_path, text)
    redactor = Redactor(extra_sensitive_keys=args.sensitive_key, max_text_chars=args.max_bytes)
    try:
        redacted, report = _process(text, format_name, redactor)
    except (RedactionLimitError, TypeError, ValueError) as error:
        if isinstance(error, CLIError):
            raise
        raise CLIError(str(error)) from error

    report_json = _report_json(report, format_name)
    if args.command == "scan":
        stdout.write(report_json + "\n")
        stdout.flush()
        return EXIT_FINDINGS if report.changed else EXIT_CLEAN

    _write_output(redacted, args.output, input_path, stdout)
    if args.report:
        stderr.write(report_json + "\n")
        stderr.flush()
    return EXIT_CLEAN


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    except CLIError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:
        return EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
