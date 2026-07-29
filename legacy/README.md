# Legacy Helix Unified snapshot

This directory preserves the integration modules extracted from `helix-unified` in
the repository's first commit. They are retained for provenance and portfolio
review, not shipped in the `samsarix-integration-guard` distribution.

The snapshot is not independently runnable: most modules import private
`apps.backend` or `learning` packages, and its dependency and infrastructure
contracts were not included in this repository. Do not copy these modules into a
deployment or treat them as supported examples without first extracting their
dependencies, threat-modeling their external side effects, and adding tests.

The supported product lives under `src/samsarix_guard/` and is distributed as
Samsarix Integration Guard. The Helix names in this snapshot are historical.

The current repository license applies as described in the root `LICENSING.md`;
historical revisions remain subject to the terms distributed with those revisions.
