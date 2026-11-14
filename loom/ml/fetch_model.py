"""Download GPT-2 weights (resumable, retries on flaky connections).

    python -m loom.ml.fetch_model [--dir models/gpt2]
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import requests

BASE = "https://huggingface.co/openai-community/gpt2/resolve/main/"
FILES = ["config.json", "model.safetensors"]


def remote_size(url: str) -> int:
    r = requests.head(url, allow_redirects=False, timeout=30)
    # Hugging Face redirects LFS files to a CDN and reports the real size here.
    size = r.headers.get("x-linked-size") or requests.head(url, allow_redirects=True, timeout=30).headers["content-length"]
    return int(size)


def fetch(url: str, dest: Path, retries: int = 50) -> int:
    size = remote_size(url)
    if dest.exists() and dest.stat().st_size == size:
        return size
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(retries):
        have = part.stat().st_size if part.exists() else 0
        if have >= size:
            break
        try:
            headers = {"Range": f"bytes={have}-"} if have else {}
            with requests.get(url, headers=headers, stream=True, timeout=(15, 30)) as r:
                r.raise_for_status()
                if have and r.status_code != 206:  # server ignored Range: start over
                    have = 0
                with open(part, "ab" if have else "wb") as out:
                    for chunk in r.iter_content(1 << 20):
                        out.write(chunk)
        except (requests.ConnectionError, requests.Timeout) as e:
            print(f"  retry {attempt + 1}: {type(e).__name__} at {have / 1e6:.1f} MB", flush=True)
            time.sleep(2)
    if part.stat().st_size != size:
        raise RuntimeError(f"{dest.name}: got {part.stat().st_size} bytes, expected {size}")
    os.replace(part, dest)
    return size


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="models/gpt2")
    args = ap.parse_args()
    d = Path(args.dir)
    d.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        t = time.time()
        size = fetch(BASE + name, d / name)
        print(f"{name}: {size / 1e6:.1f} MB in {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
