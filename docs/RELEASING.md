# Release process

Samsarix Integration Guard releases are built once in GitHub Actions, published
to PyPI with short-lived OpenID Connect credentials, and then attached to the
matching GitHub release. No long-lived PyPI token belongs in GitHub secrets or a
maintainer workstation.

## One-time publisher setup

Create a PyPI Trusted Publisher with these exact identity fields:

| Field | Value |
| --- | --- |
| PyPI project | `samsarix-integration-guard` |
| GitHub owner | the repository's current owner |
| GitHub repository | `samsarix-integration-guard` |
| Workflow | `release.yml` |
| Environment | `pypi` |

The `pypi` GitHub environment should require a maintainer's approval. If the
repository is renamed or transferred, update the PyPI publisher before the next
release because the OIDC identity includes the owner, repository, workflow file,
and environment.

## Prepare and publish a release

1. Update the version in `pyproject.toml` and
   `src/samsarix_guard/__init__.py`, then add a dated `CHANGELOG.md` section.
2. Run the complete local verification documented in `README.md`, including a
   clean build and `python scripts/verify_distribution.py dist`.
3. Run `python scripts/verify_release.py vMAJOR.MINOR.PATCH` and merge the exact
   reviewed commit to `main` only after hosted CI passes.
4. Create a non-prerelease GitHub release for `vMAJOR.MINOR.PATCH` targeting that
   exact `main` commit. Do not attach locally built distributions.
5. Publish the GitHub release and approve the `pypi` environment deployment. The
   release workflow builds and verifies a wheel and source distribution in a job
   without publishing credentials, publishes those files to PyPI, generates PyPI
   attestations, and attaches the same files plus `SHA256SUMS` to GitHub.
6. Verify the workflow, PyPI file hashes and attestations, GitHub asset digests,
   and installation in a fresh environment with
   `python -m pip install --no-deps samsarix-integration-guard==VERSION`.

PyPI filenames and versions are immutable. Never attempt to replace a published
file. If a release is defective, yank it on PyPI, explain the issue on GitHub,
and publish a corrected patch version. A yank is a compatibility signal, not a
deletion or rollback of installations already completed.
