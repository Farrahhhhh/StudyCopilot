"""Download the official PyPI wheel in ranges and verify its published SHA-256.
Development helper for slow package downloads. No account or private data involved.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

out = Path(__file__).resolve().parents[1] / "test-results" / "wheels"
out.mkdir(parents=True, exist_ok=True)
with urlopen("https://pypi.org/pypi/PySide6-Essentials/6.11.2/json", timeout=30) as response:
    metadata = json.load(response)
wheel = next(f for f in metadata["urls"] if f["filename"].endswith("cp310-abi3-win_amd64.whl"))
size, url = wheel["size"], wheel["url"]
destination = out / wheel["filename"]
if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == wheel["digests"]["sha256"]:
    print(f"Already verified: {destination}", flush=True)
    raise SystemExit(0)
chunk_size = 4 * 1024 * 1024
segments = [(i, offset, min(offset + chunk_size, size) - 1)
            for i, offset in enumerate(range(0, size, chunk_size))]
print(f"Official wheel: {wheel['filename']}, bytes={size}, ranges={len(segments)}", flush=True)


def fetch(segment):
    index, start, end = segment
    part = out / f"qt-range-{index}.part"
    expected = end - start + 1
    if part.exists() and part.stat().st_size == expected:
        return index, part, expected
    for attempt in range(3):
        try:
            request = Request(url, headers={"Range": f"bytes={start}-{end}"})
            with urlopen(request, timeout=90) as response:
                if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{size}":
                    raise RuntimeError("Server did not honor the requested range")
                data = response.read()
                if len(data) != expected:
                    raise RuntimeError("Incomplete range")
            part.write_bytes(data)
            return index, part, expected
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1)
    raise AssertionError("unreachable")


completed = {}
with ThreadPoolExecutor(max_workers=12) as pool:
    jobs = [pool.submit(fetch, segment) for segment in segments]
    for future in as_completed(jobs):
        index, part, count = future.result()
        completed[index] = part
        print(f"Range {index + 1}/{len(segments)} verified length={count}", flush=True)
with destination.open("wb") as output:
    for index in sorted(completed):
        output.write(completed[index].read_bytes())
digest = hashlib.sha256(destination.read_bytes()).hexdigest()
if digest != wheel["digests"]["sha256"]:
    raise RuntimeError("SHA-256 mismatch; do not install this file")
print(f"SHA-256 verified: {digest}\nWheel ready: {destination}", flush=True)
