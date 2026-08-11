# Changelog

All notable changes are documented here. The project uses semantic versioning for
the supported package API.

## 0.3.0 - 2026-08-08

- Added strict, versioned JSON policies with built-in balanced, privacy-only, and
  secrets-only profiles plus `policy init` and `policy validate` commands.
- Added safe category disabling and reusable byte, depth, node, replacement, and
  sensitive-key controls across the CLI and Python API.
- Added deterministic token-family detection for major AI, developer, messaging,
  payment, package-registry, and email providers.
- Kept policies dependency-free and non-executable: unknown fields, duplicate
  keys, invalid categories, invalid UTF-8, and oversized policy files fail closed.
- Added bounded recursive directory scanning with explicit globs, hidden/symlink
  exclusion, aggregate value-free reports, and input/report overwrite protection.
- Added SARIF 2.1.0 output with stable non-secret fingerprints and a first-party
  composite GitHub Action that can upload results before enforcing the scan gate.
- Added a fail-closed `RedactingFormatter` for completely rendered Python log
  messages, arguments, fields, and exception text.
- Added deterministic adversarial invariants, a bounded synthetic performance
  smoke test, practical integration recipes, and an evidence-linked competitive
  landscape.
- Added formatter and Bandit gates to CI plus weekly Python and GitHub Actions
  dependency update checks.
- Fixed batch and SARIF report paths for Windows inputs located on a different
  drive from the working directory without exposing absolute host paths.

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
