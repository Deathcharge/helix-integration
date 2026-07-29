# Contributing

Use Python 3.10 or newer and keep the supported package dependency-free unless a
new dependency has a demonstrated product and security benefit.

```console
python -m pip install -e ".[dev]"
python -m ruff check src tests
python -m mypy src
python -m unittest discover -s tests -v
python -m build
python scripts/verify_distribution.py dist
```

Changes to detection rules must include positive, negative, overlap, and
non-disclosure tests where applicable. Never commit real secrets or personal data
as fixtures. Document false-positive tradeoffs and keep regular expressions
bounded enough for untrusted input.

Do not expand or claim support for `legacy/` modules without extracting their
dependencies, defining a public contract, threat-modeling side effects, and adding
end-to-end tests.

Unless agreed otherwise in writing, contributions are submitted under the
Mozilla Public License 2.0 as described in [`LICENSING.md`](LICENSING.md). By
submitting a contribution, you represent that you have the right to do so. For
licensing questions, contact `contact@samsarix.com`; for security reports, follow
[`SECURITY.md`](SECURITY.md).
