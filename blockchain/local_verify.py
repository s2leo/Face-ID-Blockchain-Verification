"""Verification helpers for the local tamper-evident ledger."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from blockchain.local_chain import LocalChain
from blockchain.record_builder import hash_record


@dataclass(frozen=True)
class LocalVerificationResult:
    passed: bool
    record_hash: str
    block_index: int | None
    chain_valid: bool
    reason: str | None = None


def verify_local_record(record: dict[str, Any], chain_path: str = "chain.json") -> LocalVerificationResult:
    chain = LocalChain(chain_path)
    record_hash_value = hash_record(record)
    block = chain.find_record(record_hash_value)
    chain_valid = chain.validate_chain()
    passed = block is not None and chain_valid
    reason = None
    if block is None:
        reason = "The record hash was not found in the local chain."
    elif not chain_valid:
        reason = "The local chain has an invalid hash or previous-hash link."
    return LocalVerificationResult(
        passed=passed,
        record_hash=record_hash_value,
        block_index=block.index if block else None,
        chain_valid=chain_valid,
        reason=reason,
    )


def print_local_verification_report(result: LocalVerificationResult) -> None:
    print(f"Local blockchain verification: {'PASS' if result.passed else 'FAIL'}")
    print(f"  Record hash: {result.record_hash}")
    print(f"  Block index: {result.block_index if result.block_index is not None else 'not found'}")
    print(f"  Chain valid: {result.chain_valid}")
    if result.reason:
        print(f"  Reason: {result.reason}")


def print_chain(chain_path: str = "chain.json") -> None:
    chain = LocalChain(chain_path)
    print(f"Local chain: {chain.path}")
    print(f"Blocks: {len(chain.blocks)}")
    print(f"Chain valid: {chain.validate_chain()}")
    for block in chain.blocks:
        print(f"  [{block.index}] {block.timestamp} hash={block.hash}")
        print(f"      previous={block.previous_hash}")
        if block.data.get("record_hash"):
            print(f"      record_hash={block.data['record_hash']}")
