# Security policy

## Supported scope

Security fixes are accepted for the current `0.2.x` package under
`src/samsarix_guard/`. The code under `legacy/` is an unsupported historical
snapshot and must not be deployed as part of this package.

## Reporting

Use GitHub's private **Report a vulnerability** / Security Advisory flow if it is
enabled. Otherwise email support@samsarix.com with `[SECURITY]` in the subject
before opening a public issue. Do not send real credentials, access tokens, private
keys, production payloads, or personal data. Provide a synthetic reproduction,
affected version, impact, and suggested remediation when possible.

## Security model

Samsarix Integration Guard is a best-effort preprocessing control. It processes data
locally and performs no network access, but unredacted input is present in process
memory. Detection can miss context-specific or novel sensitive values, so users
remain responsible for upstream data minimization, access control, retention, and
review appropriate to their risk and legal obligations.
