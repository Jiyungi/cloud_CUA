from __future__ import annotations

import json
import sys

from .h_runner import run_h_task_worker


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    def emit(event: dict) -> None:
        sys.stdout.write(json.dumps({"kind": "event", "event": event}) + "\n")
        sys.stdout.flush()

    result = json.loads(run_h_task_worker(payload, emit))
    sys.stdout.write(json.dumps({"kind": "result", "result": result}) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
