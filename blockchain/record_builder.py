"""Build canonical records for verified face-search matches."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def build_match_record(
    face_embedding_hash: str,
    match: Any,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Return the small, stable record that will be committed on-chain."""
    return {
        "face_embedding_hash": face_embedding_hash,
        "matched_post_url": match.url,
        "matched_platform": match.platform or match.domain or "unknown",
        "match_confidence": match.biometric_similarity,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }


def canonical_json(record: dict[str, Any]) -> str:
    """Serialize a record deterministically for hashing and verification."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"))


def hash_record(record: dict[str, Any]) -> str:
    """Return the SHA-256 digest used as the blockchain transaction payload."""
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


def record_hash_bytes(record: dict[str, Any]) -> bytes:
    """Return the digest as 32 bytes for the transaction data field."""
    return bytes.fromhex(hash_record(record))
