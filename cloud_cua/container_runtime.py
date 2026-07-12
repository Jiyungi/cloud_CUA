from __future__ import annotations

import os
import secrets
import sys
import time

from .service_runtime import ServiceState, save_service_state


def main() -> None:
    port = int(os.environ.get("CLOUD_CUA_DASHBOARD_PORT", "3000"))
    token = os.environ.get("CLOUD_CUA_SERVICE_TOKEN") or secrets.token_urlsafe(32)
    os.environ["CLOUD_CUA_SERVICE_TOKEN"] = token
    save_service_state(
        ServiceState(
            pid=os.getpid(),
            port=port,
            base_url=f"http://127.0.0.1:{port}",
            token=token,
            python=sys.executable,
            started_at=time.time(),
        )
    )
    import uvicorn

    uvicorn.run("cloud_cua.server:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
