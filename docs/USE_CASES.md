# Practical use cases

Samsarix Integration Guard is most useful at a narrow outbound boundary where a
payload is about to leave the component that created it.

## AI prompts and tool results

Redact user text, retrieved context, and tool output before constructing a request
to an external model provider. A checked-in policy makes the same category and
organization-key choices repeatable across development and production.

```python
from samsarix_guard import Policy

guard = Policy.load("samsarix-policy.json").create_redactor()
safe_prompt = guard.redact_text(untrusted_prompt).text
model_response = model_client.generate(safe_prompt)
```

## Application and worker logs

Wrap each outbound Python logging handler with `RedactingFormatter`, including
handlers that forward records to an observability vendor. See
[`LOGGING.md`](LOGGING.md) for the complete setup and trust boundary.

## Webhook and event relays

Use `redact` between an event producer and a file, queue, or transport owned by
another system. JSON and JSONL parsing fails before output when the complete input
is invalid, and output-file replacement is atomic.

```console
samsarix-guard redact outbound-events.jsonl --format jsonl --output safe-events.jsonl
```

## Support bundles and export audits

Recursively scan a bounded export directory without printing its content. The
aggregate JSON report can be retained for internal evidence; SARIF can be loaded
by compatible code-scanning systems.

```console
samsarix-guard scan ./support-bundle --recursive --report-output guard-report.json
```

## CI-generated artifacts

Run the composite GitHub Action against generated fixtures, logs, documentation,
or example payloads. A finding fails the job after an optional SARIF upload. See
[`CI.md`](CI.md).

## Where another product is a better fit

Use a repository-history scanner for committed-secret response, an NLP/image
de-identification system for names and documents, or a managed DLP service for
organization-wide discovery, consoles, and incident workflows. This project does
not proxy traffic, monitor endpoints, inventory data stores, rotate credentials,
or prove regulatory compliance.
