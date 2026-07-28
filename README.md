# Helix Integration Guard

Helix Integration Guard is a local Python library and command-line tool that
detects and redacts common secrets and personally identifiable information (PII)
before text, logs, webhook events, or JSON payloads are sent to another system.

It is for developers and operators who need a small, auditable safety layer in an
integration pipeline. It has no runtime dependencies, makes no network requests,
and reports categories and counts without echoing detected values.

> **Maturity:** 0.2.0 release candidate. The supported redaction path is tested;
> automated pattern matching is not a compliance guarantee and cannot identify
> every form of sensitive data.

## Quick start

Prerequisites: Python 3.10 or newer.

```console
git clone https://github.com/Deathcharge/helix-integration.git
cd helix-integration
python -m pip install .
python -m helix_integration redact examples/sample-event.json
```

The example emits valid JSON with sensitive keys and detected values replaced by
labels such as `[REDACTED:sensitive_key]` and `[REDACTED:email]`.

To write a separate file and print a count-only report to stderr:

```console
helix-integration redact examples/sample-event.json --output sanitized.json --report
```

The command refuses to use the input path as its output path. Output files are
replaced atomically after the complete input has been parsed and redacted.

## Scan without emitting content

`scan` is suitable for a preflight check or CI gate. It writes only a JSON report,
returns `0` when no finding is detected, `1` when findings exist, and `2` for an
input or processing error.

```console
helix-integration scan examples/sample-event.json
```

Example report:

```json
{"changed": true, "counts": {"email": 1, "sensitive_key": 2}, "detections": 3, "format": "json"}
```

Use `-` or omit the input path to read stdin. Specify `--format text`,
`--format json`, or `--format jsonl` when automatic detection is not appropriate.

```console
helix-integration redact --format jsonl < events.jsonl > safe-events.jsonl
```

Run `helix-integration --help` and `helix-integration redact --help` for all
options. Inputs default to a 1 MiB limit; change it with `--max-bytes` only when the
pipeline has an appropriate CPU and memory budget.

## Python API

```python
from helix_integration import Redactor

redactor = Redactor(extra_sensitive_keys=["customer_reference"])
result = redactor.redact_data(
    {
        "authorization": "Bearer example-token",
        "message": "Contact person@example.com",
        "customer_reference": "C-123",
    }
)

send_to_integration(result.data)
print(result.report.counts)
```

The input object is not mutated. Reports and `Finding` objects do not retain the
matched secret or PII value.

## What it detects

The default detector covers:

- sensitive JSON keys such as passwords, authorization values, cookies, API keys,
  connection strings, private keys, and access/refresh/session tokens;
- bearer and basic authentication values, JWTs, GitHub tokens, AWS access-key IDs,
  common secret/connection assignments, secret URL query values, and PEM private-
  key blocks up to 16 KiB;
- email addresses, conservatively formatted phone numbers and US Social Security
  numbers, Luhn-valid payment-card numbers, and valid IPv4 addresses.

JSON keys can be extended with repeated `--sensitive-key KEY` options or the
`extra_sensitive_keys` API argument. Detection is deliberately deterministic and
explainable. It does not guess names, street addresses, health information, free-
form credentials, or domain-specific identifiers. Review output and add upstream
data minimization or a specialized detector when those categories matter.

## Formats and failure behavior

- **Text:** scans the entire UTF-8 input and preserves non-matching text.
- **JSON:** parses the complete document, recursively redacts keys and strings,
  and writes formatted valid JSON.
- **JSONL/NDJSON:** parses every non-empty line before writing output and preserves
  blank records.
- **Auto:** uses `.json`, `.jsonl`, or `.ndjson` extensions, then cautiously
  recognizes an object or array from content; otherwise it treats input as text.

Malformed JSON/JSONL, duplicate object keys, non-standard numbers such as `NaN`,
invalid UTF-8 files, unsupported structured Python values, excessive nesting,
excess node counts, oversized input, or I/O failures return an error without
printing payload content. The library defaults to 1,048,576 text characters, 64
structured levels, and 100,000 structured nodes.

## Development

```console
python -m pip install -e ".[dev]"
python -m ruff check src tests
python -m mypy src
python -m unittest discover -s tests -v
python -m build
python scripts/verify_distribution.py dist
```

The CI workflow runs these checks on Python 3.10 through 3.13 on Linux and at the
supported-version boundaries on Windows. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the change workflow and
[`docs/PRODUCTIZATION.md`](docs/PRODUCTIZATION.md) for the evidence and release
record.

## Architecture and trust boundaries

The installed package contains two layers:

1. `redaction.py` performs bounded pattern matching and recursive structured-data
   redaction.
2. `cli.py` handles local UTF-8 input, format parsing, count-only reports, and
   atomic output.

Raw input exists in process memory while it is inspected. The tool does not open
network connections, persist state, load plugins, execute input, or log payloads.
Anyone who can read the input, process memory, or chosen output already crosses the
tool's trust boundary. Protect those locations with normal OS access controls.

The initial `helix-unified` extraction remains under
[`legacy/helix_unified_snapshot`](legacy/helix_unified_snapshot) for provenance.
It is excluded from the distribution and is not a supported API or runnable
integration suite.

## Limitations and project scope

- False positives and false negatives are possible. A clean scan does not prove
  that a payload contains no sensitive data.
- This release handles text, JSON, and JSONL; it does not parse images, PDFs,
  archives, Office documents, or arbitrary binary formats.
- Redaction is irreversible replacement, not encryption or stable pseudonymization.
- The tool is local and single-process. It is not a hosted proxy, DLP service,
  policy engine, or data-retention system.
- No telemetry or external API cost is introduced.

For broader NLP and structured-data de-identification, evaluate specialized tools
such as [Microsoft Presidio](https://microsoft.github.io/presidio/). Its own
documentation likewise warns that automated detection does not guarantee finding
all sensitive information.

## Security and license status

Report vulnerabilities privately through the repository owner's preferred
security channel; do not include real secrets or personal data in a public issue.
See [`SECURITY.md`](SECURITY.md) for supported scope and reporting guidance.

The repository contains a Business Source License 1.1 text whose `Licensed Work`
field names “Helix Licensing System,” not this package. Package metadata no longer
makes the previous contradictory MIT claim. The owner must clarify the license's
scope before public distribution or third-party production adoption. See
[`LICENSE`](LICENSE) and the external-gates section of the productization record.
