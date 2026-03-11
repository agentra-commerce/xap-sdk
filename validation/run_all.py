#!/usr/bin/env python3
"""Run all validation tests.

python validation/run_all.py
"""

import subprocess
import sys
import time


TESTS = [
    ("Continuous agents (100 rounds)", ["python", "validation/continuous_agents.py", "--rounds", "100", "--seed", "42"]),
    ("100 concurrent negotiations", ["python", "validation/stress_negotiations.py"]),
    ("50 concurrent settlements", ["python", "validation/stress_settlements.py"]),
    ("10 split scenarios", ["python", "validation/stress_splits.py"]),
]


def main() -> None:
    print("=== XAP SDK Validation Suite ===\n")

    total_start = time.monotonic()
    all_passed = True

    for i, (name, cmd) in enumerate(TESTS, 1):
        label = f"[{i}/{len(TESTS)}] {name}..."
        print(f"{label:<50}", end="", flush=True)

        test_start = time.monotonic()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        elapsed = time.monotonic() - test_start

        if result.returncode == 0:
            print(f"PASSED ({elapsed:.1f}s)")
        else:
            print(f"FAILED ({elapsed:.1f}s)")
            all_passed = False
            print(f"\n--- stdout ---\n{result.stdout}")
            print(f"--- stderr ---\n{result.stderr}")

    total_time = time.monotonic() - total_start
    print()

    if all_passed:
        print(f"All validation tests passed. Total: {total_time:.1f}s")
    else:
        print(f"Some validation tests FAILED. Total: {total_time:.1f}s")
        sys.exit(1)


if __name__ == "__main__":
    main()
