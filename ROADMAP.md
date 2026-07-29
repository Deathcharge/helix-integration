# Samsarix Integration Guard roadmap

This roadmap separates four gates: merge, release, publication, and flagship adoption. Passing one does not imply the next.

## Product boundary

Portfolio role: **reusable library or sdk**. Keep this as a small, independently versioned package. Samsarix Unified should consume it only through a public API adapter; private monorepo imports and copied implementations are out of scope.

Current disposition: Merge the productization branch after exact-head verification and rollback-ref creation; release and adoption remain separate decisions.

## Stabilize the productized default

- Keep the default branch buildable from a clean checkout and preserve exact-head CI evidence.
- Keep Samsarix LLC branding, package identity, license metadata, and compatibility aliases internally consistent.
- Preserve the pre-productization default under a rollback ref before merging; do not delete legacy history.
- Completed in this pass: sensitive-key values now count toward `max_nodes`; a regression test covers the bypass, and lint, types, and 25 tests pass.
- Next: evaluate false positives and false negatives on consented representative corpora, then add bounded fuzz and performance suites.
- Review priority: authorize license.
- Review priority: confirm CI/wheel at merge SHA.
- Review priority: run representative corpus, fuzz, and performance evaluations.

## Release candidate

- Build and install the wheel in a clean environment.
- Prove one real consumer and a versioned compatibility fixture.
- Publish only after package-name ownership, licensing, provenance, and rollback are recorded.

Current hardening backlog:

- Material BSL-to-MPL relicensing is embedded in the draft branch.
- Synthetic tests do not establish precision/recall on representative, consented corpora.
- No formal fuzz/property suite, regex complexity guarantee, locale detector coverage, or streaming path for larger JSONL inputs.
- The legacy source remains visible and can confuse contributors, scanners, or users despite its exclusion from builds.
- No published package, signed release, usage evidence, or real downstream integration exists.

## Samsarix adoption

- Define a public API, event, schema, artifact, or deployment contract before connecting to Samsarix Unified.
- Add a consumer-owned contract fixture covering authentication, privacy, limits, errors, and version compatibility.
- Make one implementation canonical; remove or freeze duplicate behavior only after parity and rollback are proven.
- Record an owner, support level, compatibility window, and measurable adoption signal.

## Completion evidence

A milestone is complete only when its exact commit, commands and results, artifact digest, consumer or deployment, and rollback path are recorded in a pull request or release record. README claims must not exceed that evidence.
