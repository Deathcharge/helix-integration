# Policy files

Samsarix Integration Guard 0.3 uses a strict, versioned JSON policy so the same
detector scope and safety limits can be reviewed once and reused in local tools,
CI, logging pipelines, and integration boundaries. Policy files never load Python
code, plugins, or regular expressions.

Create a template and validate it before use:

```console
samsarix-guard policy init --profile balanced --output samsarix-policy.json
samsarix-guard policy validate samsarix-policy.json
samsarix-guard scan event.json --policy samsarix-policy.json
```

## Schema version 1

```json
{
  "version": 1,
  "profile": "balanced",
  "sensitive_keys": ["customer_reference"],
  "disabled_categories": ["ipv4"],
  "replacement": "[REDACTED:{category}]",
  "limits": {
    "max_bytes": 1048576,
    "max_depth": 64,
    "max_nodes": 100000
  }
}
```

- `version` is required and must be `1`.
- `profile` is `balanced`, `secrets-only`, or `privacy-only`.
- `sensitive_keys` adds normalized JSON field names to the built-in key catalog.
- `disabled_categories` removes individual detectors from the selected profile.
- `replacement` must contain `{category}` exactly once and cannot contain control
  characters.
- `limits` bounds UTF-8 bytes, structured nesting, and visited values.

Unknown fields, duplicate keys, duplicate list entries, unsupported categories,
non-standard JSON constants, invalid UTF-8, and files over 64 KiB fail validation.
Command-line limit and detector options override or extend a loaded policy without
modifying it.

## Profiles

- `balanced` enables every built-in PII, credential, provider-token, and sensitive-
  key detector.
- `secrets-only` disables email, phone, SSN, payment-card, and IPv4 detection. It
  is useful where ordinary contact information is expected but credentials are
  forbidden.
- `privacy-only` disables credential and sensitive-key detectors. It is useful
  for contact-data minimization where credential-like configuration text is
  expected.

A profile is a starting point, not a compliance preset. Review synthetic fixtures
for organization-specific identifiers and use `sensitive_keys` rather than adding
unbounded custom regular expressions.
