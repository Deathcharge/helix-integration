# Productization record

Last updated: 2026-08-11

This is the living decision, implementation, and release record for
`Deathcharge/samsarix-integration-guard` (renamed from `helix-integration`).
Command results are recorded only when actually
run in this repository.

## 0.3.0 competitive release

The 0.3 candidate extends the independently useful boundary without turning the
project into a hosted service or repository-history scanner:

- strict, non-executable JSON policies and balanced, secrets-only, and
  privacy-only profiles;
- deterministic provider-token coverage for AI, developer, payment, messaging,
  package-registry, and email services;
- bounded recursive scans with aggregate value-free JSON and SARIF 2.1.0;
- a first-party composite GitHub Action;
- a fail-closed Python `RedactingFormatter` that covers interpolated messages and
  rendered exceptions; and
- seeded redaction invariants, a bounded throughput smoke, practical boundary
  recipes, and evidence-linked competitive positioning.

Current Windows/Python 3.11 verification passed Ruff lint and format, strict mypy
over seven package modules, Bandit, bytecode compilation, 55 unit/command/
invariant tests, and `git diff --check`. The 128 KiB synthetic smoke observed
0.644 MiB/s on this host; that threshold detects pathological regressions and is
not a cross-platform performance guarantee.

A fresh isolated build produced the 0.3.0 wheel and source distribution. The
artifact verifier confirmed the package surface, MPL-2.0 metadata and notices,
console entry point, absence of runtime dependencies, and exclusion of legacy
code. A temporary Python 3.11 environment installed only the wheel and passed
version, policy validation, redact-then-clean-scan, recursive SARIF, and logging
API smoke journeys. The merge commit `91de804` passed all seven hosted jobs:
Python 3.10 through 3.13 on Ubuntu, Python 3.10 and 3.13 on Windows, and the
isolated package job.

## Repository assessment

The repository began as a direct extraction of 19,012 lines across 34 Python files
from `helix-unified` (`25af51b`). Its apparent purpose was an integration and agent-
coordination suite, but the extraction omitted the monorepo services, shared
models, dependency declarations, tests, examples, documentation, and deployment
contracts that those modules require.

Static inventory found 71 imports rooted at `apps`, plus imports from absent
`learning`, `annotation_engine`, `experiment_tracker`, `ml_hub`, and `verticals`
packages. Network-facing modules reference Discord, Reddit, Telegram, Teams,
GitHub, Notion, Anthropic, Perplexity, Zapier, PostgreSQL, and Redis, but none has a
standalone configuration or test contract in this repository. Advertising the
snapshot as production-ready integrations would be misleading and would create an
undocumented runtime dependency on private Helix infrastructure.

The reusable evidence in the extraction is the privacy boundary represented by
`privacy_anonymizer.py`: integration payloads should be inspected locally before
being sent to external systems. The original implementation is not suitable as a
public contract because it claims differential privacy without adding noise,
defaults to a shared pseudonymization salt, stores profiles only in memory, and
does not expose a runnable package journey. It nevertheless provides a defensible
product wedge consistent with the repository's name and intent.

The original tree is preserved under `legacy/helix_unified_snapshot/`, excluded
from builds and support claims, and documented as provenance.

## Chosen product

**Samsarix Integration Guard** is a zero-runtime-dependency Python library and CLI
from Samsarix LLC for
bounded, deterministic scanning and irreversible redaction of common secrets and
PII in local text, JSON, and JSONL integration payloads.

- **Target user:** a Python developer or operator preparing logs, webhook events,
  support exports, or API payloads for a third-party integration.
- **Problem:** sensitive values are easily copied into outbound payloads and logs;
  teams need a small preflight control that is simple to install, audit, script,
  and run offline.
- **Primary journey:** install locally; run `samsarix-guard redact input.json
  --output safe.json --report`; receive a complete redacted payload plus a report
  that contains categories and counts but no matched values; optionally use
  `scan` as a CI gate.
- **Independent reason to exist:** it does not import or call `helix-unified`, need
  another Samsarix/Helix repository, or require a hosted service. The broader
  portfolio exists and provides context, but this package is useful on its own in
  any integration pipeline.
- **Product form:** Python package and CLI, not a web application or hosted proxy.

## Product and architecture decisions

1. The installed package lives under `src/samsarix_guard/`; the monolith
   extraction is a non-packaged legacy snapshot.
2. The supported path uses only the Python standard library. This keeps first-run
   setup deterministic and offline after installation, and avoids NLP model or
   service costs.
3. Detection is rule-based and explicit. The product does not claim that it can
   identify names, arbitrary addresses, domain-specific identifiers, or every
   secret.
4. Reports never retain or print matched values. `Finding` exposes category and
   span only.
5. JSON sensitive-key redaction complements value patterns and supports custom
   keys. Inputs are copied rather than mutated.
6. CLI and library text inputs are size-bounded; structured traversal is depth- and node-bounded;
   JSON/JSONL is completely validated before output; file output is atomic; and
   input paths cannot be overwritten.
7. `scan` uses stable exit codes: 0 clean, 1 findings, 2 error. `redact` returns 0
   after successful output and 2 on error.
8. The package performs no network access, telemetry, credential storage,
   pseudonymization, or reversible encryption.
9. The supported tree is licensed under MPL-2.0. Package metadata, the unmodified
   license text, attribution notice, licensing explanation, contribution terms,
   and trademark guidance consistently identify Samsarix LLC.

## Assumptions

- The owner prefers preserving the extracted code for provenance over deleting it.
- Python 3.10 through 3.13 is an appropriate initial support window.
- A dependency-free, English-oriented deterministic baseline is more supportable
  in this repository than an ML/NLP detector.
- Replacement labels are appropriate for outbound copies; this product does not
  modify source data in place.
- GitHub is the initial source distribution and issue channel. The working support
  contacts are `contact@samsarix.com` and `support@samsarix.com`. No package
  registry, billing account, or production service is assumed.

## Bounded ecosystem research

- The [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
  recommends removing, masking, sanitizing, hashing, or encrypting access tokens,
  passwords, connection strings, encryption keys, sensitive personal data, and
  some PII rather than recording them directly. This informed the default key and
  value categories.
- [Microsoft Presidio](https://microsoft.github.io/presidio/) covers richer text,
  image, and structured de-identification with regular expressions, rules, checksums,
  and NLP. Its documentation explicitly warns that automated detection cannot
  guarantee finding all sensitive information. Integration Guard therefore makes
  the same limitation prominent and chooses a much smaller offline setup.
- [scrubadub](https://github.com/LeapBeyond/scrubadub) demonstrates demand for a
  simple Python free-text cleaning API. Integration Guard's wedge is structured
  payload keys, count-only CI scanning, bounded processing, and zero runtime
  dependencies rather than broad entity detection.
- The [Python packaging specification](https://packaging.python.org/en/latest/specifications/pyproject-toml/)
  defines `[project.scripts]` console entry points. The release uses that standard
  and removes duplicate `setup.py` metadata.
- The [Mozilla Public License 2.0](https://www.mozilla.org/MPL/2.0/) provides
  source-code and patent grants, requires preservation of notices, and does not
  grant trademark rights. Mozilla's
  [MPL FAQ](https://www.mozilla.org/MPL/2.0/FAQ/) describes its file-level
  copyleft: covered-file modifications stay available under the MPL, while the
  files can be combined with a larger work under different terms. This is the
  chosen balance between adoption, attribution, and protection for a reusable
  library.
- MariaDB's [Business Source License 1.1](https://mariadb.com/bsl11/) limits
  production use before a future change date and is not open source during that
  period. That is a worse fit for broad adoption of this local developer tool
  than MPL-2.0. This product record explains the project choice; it is not legal
  advice.

## Baseline command results

Baseline was taken from clean `main` at `30bef9b` on Windows with Python 3.11.9.

| Command | Actual baseline result |
| --- | --- |
| `git status --short --branch` | Clean; `main...origin/main`. |
| `python --version` | `Python 3.11.9`. |
| `python -m compileall -q helix_integration` | Exit 0. This checked syntax only, not imports. |
| `python -m pip install --dry-run --retries 0 --timeout 5 .` | Exit 1: no distribution matched `helix-hub-shared>=0.1.0`. |
| `python -m pytest -q` | Exit 5: `no tests ran`. |
| `python -m ruff check .` | Exit 1 with 20 `E402` errors in the extracted Notion/Zapier modules. |
| `python -m mypy helix_integration` | Did not complete after more than two minutes and was terminated; before termination it emitted many absent `apps.backend` import errors and local type errors. |
| `python -m build` | Exit 0 with deprecation/license warnings, but the wheel contained only `.dist-info` metadata and no importable package code. |

The README simultaneously claimed a missing `requirements.txt`, `requirements-dev.txt`,
`examples/`, `docs/`, `.github/workflows/ci.yml`, MIT licensing, full CI/security
coverage, and production readiness. Those claims were false at baseline.

## Findings and priorities

### P0 — release blockers

- [x] Installation cannot resolve the nonexistent public `helix-hub-shared`
  dependency. Removed it; the supported product has no runtime dependencies.
- [x] Built artifacts contain no package code because `helix_integration` lacked
  an initializer. Replaced packaging with a tested `src` layout and artifact
  verification.
- [x] No independently runnable primary journey exists. Added complete `scan` and
  `redact` CLI/API paths with an example.
- [x] Documentation advertises nonexistent files and production readiness. Replaced
  it with behavior-based setup, scope, limitations, and release status.
- [x] The public tree imports private Helix services. Isolated it from the package
  and quality claims under `legacy/`.
- [x] Package metadata claimed MIT while the repository contained a mismatched BSL
  1.1 text. Replaced both with an owner-approved, internally consistent MPL-2.0
  model and Samsarix LLC attribution/support documents.

### P1 — credibility, safety, and reliability

- [x] No tests or CI. Added standard-library unit/command tests and cross-platform
  GitHub Actions checks.
- [x] Existing privacy code uses a shared default salt and overstates differential
  privacy. The supported product performs explicit irreversible replacement and
  makes no differential-privacy claim.
- [x] No resource bounds or safe failure contract. Added byte, depth, node, parse,
  timeout-in-test, exit-code, and atomic-write behavior.
- [x] Detection reports risk disclosing matches. The supported report contains only
  category counts; findings contain spans but not values.
- [x] No published-package verification. Added artifact content and runtime-
  dependency checks.
- [x] No changelog, security scope, or contribution contract. Added concise files.

### P2 — valuable follow-up

- [ ] Add opt-in detectors for locale-specific government IDs and phone formats,
  each with false-positive fixtures.
- [ ] Add streaming JSONL processing with transactional output for payloads larger
  than the current in-memory limit.
- [x] Add organization-owned, versioned policy files with a strict schema and no
  executable plugins or regular-expression input.
- [ ] Add stable salted pseudonymization only if a validated use case justifies the
  re-identification and key-management risk.
- [x] Add seeded invariants and a bounded synthetic throughput smoke.
- [ ] Add formal fuzz/property suites and representative consented corpora for
  detector and parser boundaries.
- [x] Automate tokenless PyPI publication and provenance attestations after owner approval.

## Implementation checklist

- [x] Protect clean worktree and create `codex/productize-integration` branch.
- [x] Inventory tree, history, imports, environment use, placeholders, networking,
  persistence, packaging, license, and security-sensitive paths.
- [x] Record actual baseline command outcomes.
- [x] Define narrow independent product and out-of-scope boundaries.
- [x] Implement library scan/redact path.
- [x] Implement CLI stdin/file, text/JSON/JSONL, report, limits, and safe output.
- [x] Add representative unit and command tests.
- [x] Add packaging, artifact verification, example, CI, security, contribution,
  changelog, and user documentation.
- [x] Complete final clean verification and adversarial review.
- [x] Record final verification outcomes and release disposition below.

## Release acceptance criteria

- A fresh Python 3.10+ environment can install the wheel without private or runtime
  dependencies.
- `--help` and `--version` work; the documented example can be redacted and then
  scanned clean.
- Text, JSON, and JSONL success, finding, malformed, oversized, deep, and safe-
  output behavior is covered by tests.
- Ruff, strict mypy on the supported source, unit/command tests, build, artifact
  verification, and wheel smoke tests pass.
- No legacy module appears in the wheel or source distribution.
- Documentation makes detection limits, trust boundaries, legacy status, license,
  ownership, support, and trademark boundaries explicit.
- No locally actionable P0 remains.

## Completed work

See the implementation checklist and `CHANGELOG.md`. The final adversarial pass
also closed four issues found after the first green test run: idempotent rescanning
of replacement markers, duplicate/non-standard JSON rejection, bounded file reads,
and a CPU-heavy 10 MiB default.

## Deferred and externally blocked work

### Licensing decision resolved

The prior BSL 1.1 parameters named a different work (“Helix Licensing System”)
while package metadata claimed MIT. The owner supplied the current Samsarix LLC
identity and asked for a protective, attribution-preserving license. MPL-2.0 was
selected for its file-level copyleft and compatibility with larger open or
proprietary works. `LICENSE`, package metadata, `NOTICE`, `LICENSING.md`,
`CONTRIBUTING.md`, `TRADEMARKS.md`, and the user documentation now agree. Formal
legal advice remains the owner's responsibility.

### Publication path

`.github/workflows/release.yml` builds distributions in a job without publishing
credentials, verifies and smoke-tests them, and passes the build artifact to a
separate PyPI environment. That job uses Trusted Publishing and short-lived OIDC
credentials; it stores no package-index token and generates PyPI attestations by
default. After publication, the same wheel and source distribution plus their
SHA-256 checksums are attached to the GitHub release. The operational runbook is
in `docs/RELEASING.md`.

### Legacy portfolio decision

The owner may delete the legacy snapshot later or fund independent extraction of a
specific connector. No connector should be advertised until its external API,
credentials, permissions, data model, retry/idempotency behavior, and end-to-end
tests are independently defined.

## Known risks

- Rule-based detection has unavoidable false positives and false negatives.
- Regex performance is bounded by input size, but formal complexity/property
  testing remains P2. An adversarial local probe took about 61.6 seconds for two
  10 MiB inputs on Windows, so the default was reduced to 1 MiB and rules gained
  cheap content prefilters; larger limits are an explicit caller choice.
- Input and redacted output coexist in process memory during processing.
- IPv4 addresses are redacted by default even when they are not personal data.
- Atomic replace protects against partial output but inherits the destination
  directory's access controls and filesystem semantics.
- Source checkouts still contain unsupported legacy code; consumers must use the
  built package surface and heed `legacy/README.md`.

## Distribution and sustainability

The simplest distribution is a signed source release and pure-Python wheel from
GitHub/PyPI after hosted CI and publication approval. The tool has no hosted operating
cost: CPU and memory scale with the caller's bounded input, and there are no API,
model, telemetry, database, or network charges.

A plausible sustainability model is owner-funded maintenance, sponsorship, or paid
support for organization-specific detector policy and review. A subscription SaaS
is deliberately out of scope because it would add a sensitive-data processor,
security obligations, and recurring cost without evidence of demand.

## 0.2.0 final verification and disposition

Final local verification used Windows, PowerShell, and Python 3.11.9. Commands were
run after the hardening pass unless explicitly described as a probe.

| Command | Actual final result |
| --- | --- |
| `python -m ruff check src tests scripts` | Exit 0: `All checks passed!` |
| `python -m mypy src` | Exit 0: no issues in 4 source files under strict configuration. |
| `python -m unittest discover -s tests -v` | Exit 0: 25 tests passed. |
| `python -m bandit -q -r src` | Exit 0 with no findings. |
| `python -m compileall -q src tests scripts` | Exit 0. |
| `git diff --check` | Exit 0. |
| `python -m build` | Exit 0 in isolated build environments; produced `samsarix_integration_guard-0.2.0.tar.gz` and the pure-Python wheel. |
| `python scripts/verify_distribution.py dist` | Exit 0; one wheel and one sdist verified. The wheel contains the expected name, namespace, entry point, MPL license/notice, and no runtime dependency; neither artifact contains legacy code. |
| GitHub Actions [push](https://github.com/Deathcharge/samsarix-integration-guard/actions/runs/30416676777) and [pull-request](https://github.com/Deathcharge/samsarix-integration-guard/actions/runs/30416698149) runs | Exit 0 for both complete runs: Python 3.10–3.13 on Ubuntu, Python 3.10 and 3.13 on Windows, and the isolated package job all passed. |
| 1 MiB adversarial text probe | Two maximum-default strings scanned in about 2.026 seconds total with zero false detections on this host. This is an observation, not a cross-platform SLA. |

The wheel was then installed with `--no-deps` into a newly created temporary venv.
Inside that environment:

- `samsarix-guard --version` printed `samsarix-guard 0.2.0`;
- `samsarix-guard redact examples/sample-event.json --output <temp>/safe.json --report`
  exited 0 and reported four findings without values;
- `samsarix-guard scan <temp>/safe.json` exited 0 with `changed: false` and
  zero detections;
- `from samsarix_guard import Redactor` succeeded and redacted a synthetic
  email; and
- the temporary environment and output were removed after verification.

### Adversarial review outcomes

- A first wheel smoke test showed that already-redacted sensitive JSON keys were
  reported again. Replacement recognition and text/structured idempotency tests
  fixed the dead-end primary journey.
- Complete file reads after a size check had a growth race. Files are now read as
  at most `max_bytes + 1` binary bytes before UTF-8 decoding.
- Python's permissive JSON defaults could accept `NaN` and silently overwrite
  duplicate keys. Both now fail without payload output.
- Two adversarial 10 MiB strings took about 61.627 seconds total. The default was
  reduced to 1 MiB, the library gained its own text limit, and irrelevant pattern
  passes are prefiltered. Raising the CLI limit is an explicit caller decision.
- Source search found no network/execution imports in the supported package and no
  GitHub/AWS/private-key signatures outside synthetic tests. Synthetic fixtures
  are intentionally nonfunctional.

### Validation not run

- No package was published, signed, or installed from a public index; no production
  endpoint or external integration was contacted.
- No live secret/PII corpus was used because that would violate fixture and data-
  minimization goals. Detection quality is covered with synthetic cases, not a
  compliance benchmark.
- Formal regex fuzzing, property testing, and a cross-platform performance suite
  remain P2.
- License selection is documented and internally consistent, but this engineering
  review is not a substitute for advice from qualified counsel.

### Release disposition

**Release candidate with named external gates.** All locally actionable P0 issues
for the supported redaction journey are closed, local checks are green, and the
wheel is independently installable. It should not be publicly published or
described as production-ready until the owner approves the version and
publication/signing path.

At 0.2, the remaining work was the publication gate. The 0.3 release automation
now addresses that path; detector-locale fixtures, fuzz/performance evaluation,
transactional streaming for larger JSONL inputs, a real consumer, and usage
evidence remain follow-up work. None was silently required for the documented
local 0.2.0 journey.
