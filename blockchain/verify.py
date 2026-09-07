"""Independent verification of a record hash stored in a Polygon transaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from blockchain.config import BlockchainConfig
from blockchain.record_builder import hash_record, record_hash_bytes


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    tx_hash: str
    expected_hash: str
    on_chain_hash: str
    block_number: int | None
    confirmations: int
    chain_id: int
    chain_valid: bool = True
    error: str | None = None


def verify_transaction(
    record: dict[str, Any],
    tx_hash: str,
    config: BlockchainConfig | None = None,
) -> VerificationResult:
    """Fetch a transaction and compare its data field with the record hash."""
    config = config or BlockchainConfig.from_env()
    w3 = config.connect()
    expected_hash = hash_record(record)

    try:
        tx = w3.eth.get_transaction(tx_hash)
        raw_data = tx.get("input", tx.get("data", b""))
        on_chain_bytes = bytes(raw_data)
        on_chain_hash = on_chain_bytes.hex()
        block_number = tx.get("blockNumber")
        latest = w3.eth.block_number
        confirmations = max(0, latest - block_number + 1) if block_number is not None else 0
        matches = on_chain_bytes == record_hash_bytes(record)
        return VerificationResult(
            passed=matches,
            tx_hash=tx_hash,
            expected_hash=expected_hash,
            on_chain_hash=on_chain_hash,
            block_number=block_number,
            confirmations=confirmations,
            chain_id=w3.eth.chain_id,
            chain_valid=True,
            error=None if matches else "Transaction data does not match the recomputed record hash.",
        )
    except Exception as exc:
        return VerificationResult(
            passed=False,
            tx_hash=tx_hash,
            expected_hash=expected_hash,
            on_chain_hash="",
            block_number=None,
            confirmations=0,
            chain_id=w3.eth.chain_id,
            chain_valid=True,
            error=f"Could not verify transaction: {exc}",
        )


def print_verification_report(result: VerificationResult) -> None:
    """Print a clear report suitable for the demo recording."""
    status = "PASS" if result.passed else "FAIL"
    print(f"Blockchain verification: {status}")
    print(f"  Transaction: {result.tx_hash}")
    print(f"  Network chain ID: {result.chain_id}")
    print(f"  Block: {result.block_number if result.block_number is not None else 'pending/not found'}")
    print(f"  Confirmations: {result.confirmations}")
    print(f"  Expected hash: {result.expected_hash}")
    print(f"  On-chain hash: {result.on_chain_hash or 'not available'}")
    if result.error:
        print(f"  Reason: {result.error}")
