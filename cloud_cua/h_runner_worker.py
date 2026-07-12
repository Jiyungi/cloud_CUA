from __future__ import annotations

import json
import sys

from .h_runner import run_h_task_worker


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    sys.stdout.write(run_h_task_worker(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
