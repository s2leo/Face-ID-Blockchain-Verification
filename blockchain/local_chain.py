"""A small persistent local blockchain for tamper-evident demo records.

This is intentionally dependency-free. Each block commits to its data and the
previous block hash, so modifying a record or reordering blocks invalidates the
chain. A public Polygon deployment could use the same record hash as transaction
data via the optional web3.py uploader in this package.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


@dataclass
class Block:
    index: int
    timestamp: str
    data: dict[str, Any]
    previous_hash: str
    hash: str = ""

    def calculate_hash(self) -> str:
        payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
        }
        return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()

    def seal(self) -> "Block":
        self.hash = self.calculate_hash()
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Block":
        return cls(
            index=int(value["index"]),
            timestamp=str(value["timestamp"]),
            data=dict(value["data"]),
            previous_hash=str(value["previous_hash"]),
            hash=str(value.get("hash", "")),
        )


class LocalChain:
    """Persistent local tamper-evident ledger backed by a JSON file."""

    def __init__(self, path: str | os.PathLike[str] = "chain.json"):
        self.path = Path(path)
        self.blocks: list[Block] = []
        self._load()

    def _genesis(self) -> Block:
        return Block(
            index=0,
            timestamp="2026-01-01T00:00:00+00:00",
            data={"type": "genesis", "description": "Face ID verification ledger"},
            previous_hash="0",
        ).seal()

    def _load(self) -> None:
        if not self.path.exists():
            self.blocks = [self._genesis()]
            self._persist()
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.blocks = [Block.from_dict(item) for item in raw.get("blocks", [])]
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise RuntimeError(f"Could not read local chain {self.path}: {exc}") from exc
        if not self.blocks:
            self.blocks = [self._genesis()]
            self._persist()

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": "LOCAL_FACE_ID_CHAIN_V1", "blocks": [b.to_dict() for b in self.blocks]}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def add_block(self, data: dict[str, Any]) -> Block:
        previous = self.blocks[-1]
        block = Block(
            index=previous.index + 1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=data,
            previous_hash=previous.hash,
        ).seal()
        self.blocks.append(block)
        self._persist()
        return block

    def validate_chain(self) -> bool:
        if not self.blocks or self.blocks[0].to_dict() != self._genesis().to_dict():
            return False
        for previous, current in zip(self.blocks, self.blocks[1:]):
            if current.previous_hash != previous.hash:
                return False
            if current.hash != current.calculate_hash():
                return False
            if current.index != previous.index + 1:
                return False
        return True

    def find_record(self, record_hash: str) -> Block | None:
        for block in self.blocks:
            if block.data.get("record_hash") == record_hash:
                return block
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "LOCAL_FACE_ID_CHAIN_V1", "blocks": [b.to_dict() for b in self.blocks]}
