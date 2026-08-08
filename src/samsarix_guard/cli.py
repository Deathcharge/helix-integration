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
from .policy import POLICY_VERSION, PROFILE_NAMES, Policy, PolicyError
from .redaction import SUPPORTED_CATEGORIES, RedactionLimitError, RedactionReport, Redactor
from .reporting import ScanRecord, json_scan_report, sarif_scan_report

DEFAULT_MAX_BYTES: Final = 1024 * 1024
DEFAULT_MAX_FILES: Final = 1_000
DEFAULT_MAX_TOTAL_BYTES: Final = 10 * 1024 * 1024
DEFAULT_SCAN_GLOBS: Final[tuple[str, ...]] = (
    "*.csv",
    "*.json",
    "*.jsonl",
    "*.log",
    "*.md",
    "*.ndjson",
    "*.txt",
    "*.xml",
    "*.yaml",
    "*.yml",
)
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
            default=None,
            help=f"maximum UTF-8 input size (default policy: {DEFAULT_MAX_BYTES})",
        )
        command.add_argument("--max-depth", type=_positive_int, default=None, help="maximum structured nesting depth")
        command.add_argument("--max-nodes", type=_positive_int, default=None, help="maximum structured values visited")
        policy_group = command.add_mutually_exclusive_group()
        policy_group.add_argument("--policy", metavar="FILE", help="strict JSON policy file")
        policy_group.add_argument(
            "--profile",
            choices=PROFILE_NAMES,
            default="balanced",
            help="built-in detector profile (default: balanced)",
        )
        command.add_argument(
            "--sensitive-key",
            action="append",
            default=[],
            metavar="KEY",
            help="additional JSON key to redact; repeatable",
        )
        command.add_argument(
            "--disable-category",
            action="append",
            choices=sorted(SUPPORTED_CATEGORIES),
            default=[],
            metavar="CATEGORY",
            help="disable a detector category; repeatable",
        )

    redact = subparsers.add_parser("redact", help="write a redacted copy of a payload")
    add_input_arguments(redact)
    redact.add_argument("-o", "--output", default="-", help="output file, or - for stdout (default: -)")
    redact.add_argument("--report", action="store_true", help="write a count-only JSON report to stderr")

    scan = subparsers.add_parser("scan", help="report findings without writing payload content")
    add_input_arguments(scan)
    scan.add_argument(
        "--recursive",
        action="store_true",
        help="scan a directory recursively; hidden paths and symlinks are skipped",
    )
    scan.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="GLOB",
        help="directory file glob; repeatable (default: common payload and log formats)",
    )
    scan.add_argument(
        "--max-files",
        type=_positive_int,
        default=DEFAULT_MAX_FILES,
        help=f"maximum directory files scanned (default: {DEFAULT_MAX_FILES})",
    )
    scan.add_argument(
        "--max-total-bytes",
        type=_positive_int,
        default=DEFAULT_MAX_TOTAL_BYTES,
        help=f"maximum directory bytes read (default: {DEFAULT_MAX_TOTAL_BYTES})",
    )
    scan.add_argument(
        "--report-format",
        choices=("json", "sarif"),
        default="json",
        help="count-only report format (default: json)",
    )
    scan.add_argument(
        "--report-output",
        default="-",
        metavar="FILE",
        help="report file, or - for stdout (default: -)",
    )

    policy = subparsers.add_parser("policy", help="create or validate a strict JSON policy")
    policy_commands = policy.add_subparsers(dest="policy_command", required=True)
    policy_init = policy_commands.add_parser("init", help="write a documented policy template")
    policy_init.add_argument("--profile", choices=PROFILE_NAMES, default="balanced")
    policy_init.add_argument("-o", "--output", default="-", help="output file, or - for stdout (default: -)")
    policy_validate = policy_commands.add_parser("validate", help="validate a policy without scanning payloads")
    policy_validate.add_argument("input", help="policy file to validate")
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


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return Path(os.path.relpath(path, Path.cwd())).as_posix()


def _validate_scan_globs(patterns: tuple[str, ...]) -> tuple[str, ...]:
    selected = patterns or DEFAULT_SCAN_GLOBS
    for pattern in selected:
        pattern_path = Path(pattern)
        if (
            not pattern
            or len(pattern) > 128
            or not pattern.isprintable()
            or pattern_path.is_absolute()
            or ".." in pattern_path.parts
        ):
            raise CLIError("--include patterns must be relative, printable globs without '..'")
    return selected


def _collect_scan_paths(args: argparse.Namespace) -> tuple[tuple[Path | None, ...], bool]:
    if args.input == "-":
        if args.recursive:
            raise CLIError("--recursive requires a directory input")
        return (None,), True

    input_path = Path(args.input).expanduser()
    try:
        resolved = input_path.resolve()
    except OSError as error:
        raise CLIError(f"cannot resolve input path {input_path}: {error.strerror or error}") from error
    if resolved.is_file():
        if args.recursive:
            raise CLIError("--recursive requires a directory input")
        return (resolved,), True
    if not resolved.is_dir():
        raise CLIError(f"input is not a file or directory: {input_path}")
    if not args.recursive:
        raise CLIError("directory input requires --recursive")

    patterns = _validate_scan_globs(tuple(args.include))
    try:
        paths = tuple(
            sorted(
                (
                    candidate
                    for candidate in resolved.rglob("*")
                    if not candidate.is_symlink()
                    and candidate.is_file()
                    and not any(part.startswith(".") for part in candidate.relative_to(resolved).parts)
                    and any(candidate.relative_to(resolved).match(pattern) for pattern in patterns)
                ),
                key=lambda path: path.as_posix().casefold(),
            )
        )
    except OSError as error:
        raise CLIError(f"cannot enumerate directory {input_path}: {error.strerror or error}") from error
    if len(paths) > args.max_files:
        raise CLIError(f"directory contains {len(paths)} matching files; exceeds --max-files={args.max_files}")
    return paths, False


def _safe_process(text: str, format_name: str, redactor: Redactor) -> tuple[str, RedactionReport]:
    try:
        return _process(text, format_name, redactor)
    except (RedactionLimitError, TypeError, ValueError) as error:
        if isinstance(error, CLIError):
            raise
        raise CLIError(str(error)) from error


def _run_scan(
    args: argparse.Namespace,
    *,
    redactor: Redactor,
    max_bytes: int,
    stdin: TextIO,
    stdout: TextIO,
) -> int:
    paths, single_input = _collect_scan_paths(args)
    records: list[ScanRecord] = []
    protected_paths: list[Path] = []
    total_bytes = 0

    for path in paths:
        input_name = "-" if path is None else str(path)
        text, resolved_path = _read_input(input_name, max_bytes, stdin)
        if not single_input:
            total_bytes += len(text.encode("utf-8"))
            if total_bytes > args.max_total_bytes:
                raise CLIError(f"directory input exceeds --max-total-bytes={args.max_total_bytes}")
        format_name = _resolve_format(args.format, resolved_path, text)
        _, report = _safe_process(text, format_name, redactor)
        record_path = "stdin" if resolved_path is None else _display_path(resolved_path)
        records.append(ScanRecord(record_path, format_name, report))
        if resolved_path is not None:
            protected_paths.append(resolved_path)

    if args.policy:
        try:
            protected_paths.append(Path(args.policy).expanduser().resolve())
        except OSError as error:
            raise CLIError(f"cannot resolve policy path: {error.strerror or error}") from error

    record_tuple = tuple(records)
    if args.report_format == "sarif":
        report_data = sarif_scan_report(record_tuple, semantic_version=__version__)
        report_text = json.dumps(report_data, indent=2, sort_keys=True) + "\n"
    else:
        report_data = json_scan_report(record_tuple, single_input=single_input)
        report_text = json.dumps(report_data, sort_keys=True) + "\n"
    _write_output(
        report_text,
        args.report_output,
        None,
        stdout,
        protected_paths=tuple(protected_paths),
    )
    return EXIT_FINDINGS if any(record.report.changed for record in records) else EXIT_CLEAN


def _load_policy(args: argparse.Namespace) -> Policy:
    try:
        return Policy.load(args.policy) if args.policy else Policy.for_profile(args.profile)
    except PolicyError as error:
        raise CLIError(str(error)) from error


def _run_policy(args: argparse.Namespace, *, stdout: TextIO) -> int:
    if args.policy_command == "init":
        policy = Policy.for_profile(args.profile)
        output = json.dumps(policy.to_mapping(), indent=2, sort_keys=True) + "\n"
        _write_output(output, args.output, None, stdout)
        return EXIT_CLEAN
    if args.policy_command == "validate":
        try:
            policy = Policy.load(args.input)
        except PolicyError as error:
            raise CLIError(str(error)) from error
        stdout.write(
            json.dumps(
                {"profile": policy.profile, "valid": True, "version": POLICY_VERSION},
                sort_keys=True,
            )
            + "\n"
        )
        stdout.flush()
        return EXIT_CLEAN
    raise CLIError(f"unsupported policy command: {args.policy_command}")


def _write_output(
    text: str,
    output_name: str,
    input_path: Path | None,
    stdout: TextIO,
    *,
    protected_paths: tuple[Path, ...] = (),
) -> None:
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
    forbidden_paths = frozenset((*protected_paths, *((input_path,) if input_path is not None else ())))
    if resolved_output in forbidden_paths:
        raise CLIError("refusing to overwrite an input or policy file; choose a different output path")
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
    if args.command == "policy":
        return _run_policy(args, stdout=stdout)

    policy = _load_policy(args)
    max_bytes = args.max_bytes if args.max_bytes is not None else policy.max_bytes
    redactor = policy.create_redactor(
        extra_sensitive_keys=tuple(args.sensitive_key),
        disabled_categories=tuple(args.disable_category),
        max_bytes=max_bytes,
        max_depth=args.max_depth,
        max_nodes=args.max_nodes,
    )
    if args.command == "scan":
        return _run_scan(args, redactor=redactor, max_bytes=max_bytes, stdin=stdin, stdout=stdout)

    text, input_path = _read_input(args.input, max_bytes, stdin)
    format_name = _resolve_format(args.format, input_path, text)
    redacted, report = _safe_process(text, format_name, redactor)
    report_json = _report_json(report, format_name)
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
