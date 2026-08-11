# Samsarix Integration Guard roadmap

This roadmap separates four gates: merge, release, publication, and flagship adoption. Passing one does not imply the next.

## Product boundary

Portfolio role: **reusable library or sdk**. Keep this as a small, independently versioned package. Samsarix Unified should consume it only through a public API adapter; private monorepo imports and copied implementations are out of scope.

Current disposition: 0.3.0 is a release candidate on the competitive-guard branch.
Merge follows exact-head local and hosted verification; public package publication
and flagship adoption remain separate owner decisions.

## Stabilize the productized default

- Keep the default branch buildable from a clean checkout and preserve exact-head CI evidence.
- Keep Samsarix LLC branding, package identity, license metadata, and compatibility aliases internally consistent.
- Preserve the pre-productization default under a rollback ref before merging; do not delete legacy history.
- Completed in 0.2: sensitive-key values count toward `max_nodes`, and regression
  coverage prevents that traversal-limit bypass.
- Completed for 0.3: strict JSON policy files, three detector profiles, category
  controls, organization-specific sensitive keys, and expanded provider-token
  coverage without executable plugins or runtime dependencies.
- Completed for 0.3: bounded recursive batch scans, value-free JSON/SARIF reports,
  and a first-party GitHub Action smoke-tested from the package workflow.
- Completed for 0.3: fail-closed Python logging integration, seeded invariant
  checks, a bounded performance smoke test, and practical boundary recipes.
- Next: evaluate false positives and false negatives on consented representative corpora, then add bounded fuzz and performance suites.
- Review priority: confirm CI/wheel at merge SHA.
- Review priority: run representative corpus, fuzz, and performance evaluations.

## Release candidate

- Build and install the wheel in a clean environment.
- Prove one real consumer and a versioned compatibility fixture.
- Publish only after package-name ownership, licensing, provenance, and rollback are recorded.

Current hardening backlog:

- MPL-2.0 licensing, Samsarix LLC attribution, notices, contribution terms, and
  trademark guidance are established; formal legal review remains an owner gate.
- Synthetic tests do not establish precision/recall on representative, consented corpora.
- No formal fuzz suite, regex complexity guarantee, locale detector coverage, or
  streaming path for larger JSONL inputs; current seeded invariants and synthetic
  throughput smoke are regression evidence, not a performance guarantee.
- The legacy source remains visible and can confuse contributors, scanners, or users despite its exclusion from builds.
- No published package, signed release, usage evidence, or real downstream integration exists.

## Samsarix adoption

- Define a public API, event, schema, artifact, or deployment contract before connecting to Samsarix Unified.
- Add a consumer-owned contract fixture covering authentication, privacy, limits, errors, and version compatibility.
- Make one implementation canonical; remove or freeze duplicate behavior only after parity and rollback are proven.
- Record an owner, support level, compatibility window, and measurable adoption signal.

## Completion evidence

A milestone is complete only when its exact commit, commands and results, artifact digest, consumer or deployment, and rollback path are recorded in a pull request or release record. README claims must not exceed that evidence.
