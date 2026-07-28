# Productization record

Last updated: 2026-07-28

This is the living decision, implementation, and release record for
`Deathcharge/helix-integration`. Command results are recorded only when actually
run in this repository.

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

**Helix Integration Guard** is a zero-runtime-dependency Python library and CLI for
bounded, deterministic scanning and irreversible redaction of common secrets and
PII in local text, JSON, and JSONL integration payloads.

- **Target user:** a Python developer or operator preparing logs, webhook events,
  support exports, or API payloads for a third-party integration.
- **Problem:** sensitive values are easily copied into outbound payloads and logs;
  teams need a small preflight control that is simple to install, audit, script,
  and run offline.
- **Primary journey:** install locally; run `helix-integration redact input.json
  --output safe.json --report`; receive a complete redacted payload plus a report
  that contains categories and counts but no matched values; optionally use
  `scan` as a CI gate.
- **Independent reason to exist:** it does not import or call `helix-unified`, need
  a hosted Helix service, or duplicate the flagship application. It is useful in
  any integration pipeline.
- **Product form:** Python package and CLI, not a web application or hosted proxy.

## Product and architecture decisions

1. The installed package lives under `src/helix_integration/`; the monolith
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
9. Public distribution is deferred until the owner clarifies the checked-in
   license text. Package metadata includes the file without making a contradictory
   license claim.

## Assumptions

- The owner prefers preserving the extracted code for provenance over deleting it.
- Python 3.10 through 3.13 is an appropriate initial support window.
- A dependency-free, English-oriented deterministic baseline is more supportable
  in this repository than an ML/NLP detector.
- Replacement labels are appropriate for outbound copies; this product does not
  modify source data in place.
- GitHub is the initial source distribution and issue channel. No package registry,
  domain, billing account, or production service is assumed.

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
- [x] Package metadata claims MIT while the repository contains a BSL 1.1 text.
  Removed the MIT claim; final license scope remains owner-blocked.

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
- [ ] Allow organization-owned, versioned policy files after defining a safe schema
  and regular-expression denial rules.
- [ ] Add stable salted pseudonymization only if a validated use case justifies the
  re-identification and key-management risk.
- [ ] Add benchmark and fuzz/property suites for detector performance and parser
  boundaries.
- [ ] Publish signed artifacts and provenance attestations after owner approval.

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
- Documentation makes detection limits, trust boundaries, legacy status, and
  license gate explicit.
- No locally actionable P0 remains.

## Completed work

See the implementation checklist and `CHANGELOG.md`. The final adversarial pass
also closed four issues found after the first green test run: idempotent rescanning
of replacement markers, duplicate/non-standard JSON rejection, bounded file reads,
and a CPU-heavy 10 MiB default.

## Deferred and externally blocked work

### Owner/legal gate

The checked-in BSL 1.1 parameters name “Helix Licensing System” as the Licensed
Work and state a 2024 copyright, while this repository is `helix-integration` and
was extracted in 2026. The previous package metadata claimed MIT. The owner or
qualified counsel must specify whether the file applies to this repository,
correct its parameters if intended, and approve publication. Verification: the
license file, package metadata, README, and repository settings must agree.

### Publication gate

No package index project, signing identity, release token, protected environment,
or approval was provided. After the license gate, the owner must choose a version,
create/approve the release, configure trusted publishing, and verify installation
from the public index. No package was published or production infrastructure
changed in this work.

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
GitHub/PyPI after the owner resolves licensing. The tool has no hosted operating
cost: CPU and memory scale with the caller's bounded input, and there are no API,
model, telemetry, database, or network charges.

A plausible sustainability model is owner-funded maintenance, sponsorship, or paid
support for organization-specific detector policy and review. A subscription SaaS
is deliberately out of scope because it would add a sensitive-data processor,
security obligations, and recurring cost without evidence of demand.

## Final verification and disposition

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
| `python -m build` | Exit 0 in isolated build environments; produced the 0.2.0 sdist and pure-Python wheel. |
| `python scripts/verify_distribution.py dist` | Exit 0; one wheel and one sdist verified, with no legacy code or runtime dependency in the wheel. |
| 1 MiB adversarial text probe | Two maximum-default strings scanned in about 2.026 seconds total with zero false detections on this host. This is an observation, not a cross-platform SLA. |

The wheel was then installed with `--no-deps` into a newly created temporary venv.
Inside that environment:

- `helix-integration --version` printed `helix-integration 0.2.0`;
- `helix-integration redact examples/sample-event.json --output <temp>/safe.json --report`
  exited 0 and reported four findings without values;
- `helix-integration scan <temp>/safe.json` exited 0 with `changed: false` and
  zero detections;
- `from helix_integration import Redactor` succeeded and redacted a synthetic
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

- The GitHub Actions workflow was created but not pushed, so its Linux runs and
  Python 3.10/3.12/3.13 jobs have not executed. Local tests cover Windows and
  Python 3.11.9 only.
- No package was published, signed, or installed from a public index; no production
  endpoint or external integration was contacted.
- No live secret/PII corpus was used because that would violate fixture and data-
  minimization goals. Detection quality is covered with synthetic cases, not a
  compliance benchmark.
- Formal regex fuzzing, property testing, and a cross-platform performance suite
  remain P2.
- License applicability cannot be validated technically and remains an owner/legal
  gate.

### Release disposition

**Release candidate with named external gates.** All locally actionable P0 issues
for the supported redaction journey are closed, local checks are green, and the
wheel is independently installable. It should not be publicly published or
described as production-ready until:

1. the owner clarifies/corrects the license scope;
2. the hosted CI matrix passes on the target GitHub repository; and
3. the owner approves the version and publication/signing path.

Remaining work ordered by value is the license/CI/publication gates above, then the
P2 detector-locale fixtures, fuzz/performance suite, transactional streaming for
larger JSONL inputs, safe organization policy schema, and signed artifact
provenance. None is silently required for the documented local 0.2.0 journey.
