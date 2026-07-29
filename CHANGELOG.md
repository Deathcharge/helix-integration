# Changelog

All notable changes are documented here. The project uses semantic versioning for
the supported package API.

## 0.2.0 - 2026-07-28

- Reframed the repository as Samsarix Integration Guard, an offline redaction library
  and CLI for text, JSON, and JSONL integration payloads.
- Established the `samsarix-integration-guard` distribution, `samsarix_guard`
  Python namespace, and `samsarix-guard` command under the Samsarix LLC brand.
- Added count-only scanning, bounded input and traversal, safe output behavior,
  idempotent structured key redaction, deterministic secret/PII patterns, strict
  JSON semantics, and tests.
- Removed the nonexistent `helix-hub-shared` runtime dependency and replaced the
  contradictory historical license metadata with a consistent MPL-2.0 package,
  notice, licensing explanation, and trademark guidance.
- Isolated the original monolith-coupled extraction under `legacy/` and excluded it
  from package builds.
- Added CI, distribution verification, productization, security, contribution, and
  accurate usage documentation.

## 0.1.0 - 2026-06-17

- Initial extraction of integration modules from `helix-unified`.
