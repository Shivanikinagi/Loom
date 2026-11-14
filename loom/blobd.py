"""Content-addressed blob store for stage inputs and outputs.

Blobs are addressed by their keccak256, the same hash committed on-chain, so
the store is untrusted: every reader re-hashes what it downloads and rejects
anything that does not match the commitment. The store only provides
availability (the data-availability assumption is documented in the README).

    python -m loom.blobd --port 8700
"""

from __future__ import annotations

import argparse
from pathlib import Path

import requests
from eth_hash.auto import keccak
from fastapi import FastAPI, HTTPException, Request, Response

from .chain import ROOT

STORE = ROOT / ".loom" / "blobs"


def make_app(store: Path = STORE):
    store.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="LOOM blob store")

    @app.put("/blob")
    async def put(request: Request):
        data = await request.body()
        h = "0x" + keccak(data).hex()
        (store / h).write_bytes(data)
        return {"hash": h, "size": len(data)}

    @app.get("/blob/{h}")
    def get(h: str):
        p = store / h.lower()
        if not p.exists():
            raise HTTPException(404, "unknown blob")
        return Response(p.read_bytes(), media_type="application/octet-stream")

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


class BlobClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    def put(self, data: bytes) -> str:
        r = requests.put(f"{self.base}/blob", data=data, timeout=60)
        r.raise_for_status()
        return f"{self.base}/blob/{r.json()['hash']}"

    @staticmethod
    def get(uri: str, expected: bytes | None = None) -> bytes:
        """Fetch a blob and check it against its on-chain commitment."""
        r = requests.get(uri, timeout=60)
        r.raise_for_status()
        data = r.content
        if expected is not None and keccak(data) != bytes(expected):
            raise ValueError(f"blob at {uri} does not match its commitment")
        return data


def main() -> None:
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8700)
    args = ap.parse_args()
    uvicorn.run(make_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
