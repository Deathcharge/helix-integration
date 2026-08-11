"""Run a bounded, synthetic redaction throughput smoke test."""

from __future__ import annotations

import argparse
import time

from samsarix_guard import Redactor


def build_payload(size_kib: int) -> str:
    sample = (
        "event=checkout status=ok contact=person@example.test password=synthetic-value-123456 trace=ordinary-metadata\n"
    )
    target_characters = size_kib * 1024
    return (sample * (target_characters // len(sample) + 1))[:target_characters]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size-kib", type=int, default=256)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--minimum-mib-per-second", type=float, default=0.0)
    arguments = parser.parse_args()
    if not 1 <= arguments.size_kib <= 1024:
        parser.error("--size-kib must be from 1 through 1024")
    if not 1 <= arguments.iterations <= 100:
        parser.error("--iterations must be from 1 through 100")
    if arguments.minimum_mib_per_second < 0:
        parser.error("--minimum-mib-per-second cannot be negative")

    payload = build_payload(arguments.size_kib)
    redactor = Redactor(max_text_chars=len(payload))
    started = time.perf_counter()
    detection_count = 0
    for _ in range(arguments.iterations):
        detection_count += redactor.redact_text(payload).report.detection_count
    elapsed = time.perf_counter() - started
    processed_mib = len(payload.encode("utf-8")) * arguments.iterations / (1024 * 1024)
    throughput = processed_mib / elapsed
    print(
        f"processed_mib={processed_mib:.3f} elapsed_seconds={elapsed:.3f} "
        f"throughput_mib_per_second={throughput:.3f} detections={detection_count}"
    )
    if throughput < arguments.minimum_mib_per_second:
        print(
            f"throughput {throughput:.3f} MiB/s is below requested minimum {arguments.minimum_mib_per_second:.3f} MiB/s"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
