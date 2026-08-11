# Redacting Python logs

`RedactingFormatter` wraps an existing standard-library `logging.Formatter` and
redacts the complete rendered record immediately before a handler emits it. This
includes interpolated arguments, formatter fields, and rendered exception
tracebacks.

```python
import logging

from samsarix_guard import Policy, RedactingFormatter

handler = logging.StreamHandler()
handler.setFormatter(
    RedactingFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"),
        policy=Policy.for_profile("balanced"),
    )
)

logger = logging.getLogger("checkout")
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.info("customer=%s password=%s", "person@example.com", "synthetic-secret")
```

The wrapper uses only standard logging APIs, so it also composes with JSON or
structured formatters that render to a string. Attach it to every outbound
handler that must be protected; records sent to an unwrapped handler remain
unredacted.

## Failure behavior

The default is fail-closed for redaction size-limit errors: the entire rendered
record becomes `[REDACTED:log_record_limit]`. Set `fail_closed=False` only when a
handler or logging error path reliably drops the record after an exception.
Configuration errors and errors raised by the wrapped formatter are not hidden.

This boundary reduces accidental disclosure; it is not a substitute for avoiding
sensitive values in logs. The unredacted `LogRecord`, its arguments, and exception
remain in process memory and may be observed by filters or handlers that run
before or alongside the protected handler.
