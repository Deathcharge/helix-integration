# CI and SARIF integration

`scan` is a value-free CI gate: exit `0` means no finding, exit `1` means one or
more findings, and exit `2` means the input or policy could not be safely
processed. Payload values never appear in JSON or SARIF reports.

## Scan a directory

Directory traversal is explicit, bounded, and deterministic:

```console
samsarix-guard scan ./outbound-events --recursive \
  --include "*.json" --include "*.jsonl" --include "*.log"
```

Hidden paths and symbolic links are skipped. Defaults cover common payload, log,
markup, and tabular text formats. `--max-files`, `--max-total-bytes`, and the
policy's per-file `max_bytes` prevent an accidental unbounded CI job. A batch JSON
report contains aggregate counts and one value-free result per scanned file.

## Generate SARIF 2.1.0

```console
samsarix-guard scan ./outbound-events --recursive \
  --policy samsarix-policy.json \
  --report-format sarif --report-output samsarix-guard.sarif
```

Each file/category pair becomes one alert with a stable, non-secret fingerprint.
Locations identify the file, not the matched payload value. GitHub accepts SARIF
2.1.0 from third-party scanners and displays it through code scanning.

## First-party GitHub Action

After the `v0.3.0` release, a workflow can install the action code locally, scan a
generated payload directory, upload SARIF, and fail when findings exist:

```yaml
name: Payload privacy gate

on:
  pull_request:

permissions:
  contents: read
  security-events: write

jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: Deathcharge/samsarix-integration-guard@v0.3.0
        with:
          path: outbound-events
          recursive: "true"
          include: "*.json,*.jsonl,*.log"
          policy: samsarix-policy.json
          upload-sarif: "true"
```

The action does not contact Samsarix or send payload data anywhere. When SARIF
upload is enabled, only category counts, file locations, tool metadata, and stable
fingerprints are submitted to GitHub. Review whether even file names are suitable
for the repository's threat model before enabling upload.
