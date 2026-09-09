#!/usr/bin/env python3
"""Wait for the public catalog to match the inventory being published."""

import hashlib
import time
import urllib.error
import urllib.request
from pathlib import Path


def wait_for_catalog(expected: bytes, timeout: float = 600, interval: float = 15) -> None:
    digest = hashlib.sha256(expected).hexdigest()
    deadline = time.monotonic() + timeout
    while True:
        request = urllib.request.Request(
            f"https://papeleriasolnaciente.com/products.csv?inventory={digest}&check={time.time_ns()}",
            headers={"Cache-Control": "no-cache"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.read() == expected:
                    print(f"Public catalog verified: SHA256 {digest}")
                    return
        except (urllib.error.URLError, TimeoutError) as error:
            print(f"Waiting for publication: {error}", flush=True)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("The public catalog did not match the updated inventory within the publication timeout.")
        time.sleep(min(interval, remaining))


if __name__ == "__main__":
    wait_for_catalog((Path(__file__).resolve().parents[1] / "products.csv").read_bytes())
