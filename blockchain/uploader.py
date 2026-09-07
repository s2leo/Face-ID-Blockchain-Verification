"""Upload record hashes to Polygon Amoy using a zero-value self-transfer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eth_account import Account
from web3 import Web3

from blockchain.config import AMOY_EXPLORER_URL, BlockchainConfig
from blockchain.record_builder import hash_record, record_hash_bytes


@dataclass(frozen=True)
class UploadResult:
    tx_hash: str
    block_number: int
    record_hash: str
    explorer_url: str


def upload_record(record: dict[str, Any], config: BlockchainConfig | None = None) -> UploadResult:
    """Commit a record hash in transaction data and wait for confirmation.

    This uses a normal self-transfer rather than a custom contract to keep the
    hackathon demo small. The transaction is still public, timestamped, and
    independently verifiable on PolygonScan.
    """
    config = config or BlockchainConfig.from_env()
    w3 = config.connect()
    account = Account.from_key(config.private_key)
    if account.address.lower() != config.wallet_address.lower():
        raise ValueError("WALLET_ADDRESS does not match WALLET_PRIVATE_KEY.")

    balance = w3.eth.get_balance(account.address)
    nonce = w3.eth.get_transaction_count(account.address, "pending")
    gas_price = w3.eth.gas_price
    gas_limit = 21_000 + 32 * 16
    required = gas_limit * gas_price
    if balance < required:
        raise RuntimeError(
            f"Insufficient Amoy POL balance. Need at least {required} wei for gas; "
            f"wallet has {balance} wei. Fund {account.address} from an Amoy faucet."
        )

    tx = {
        "chainId": w3.eth.chain_id,
        "nonce": nonce,
        "to": account.address,
        "value": 0,
        "gas": gas_limit,
        "gasPrice": gas_price,
        "data": record_hash_bytes(record),
    }

    try:
        signed = account.sign_transaction(tx)
        raw_transaction = getattr(signed, "raw_transaction", None)
        if raw_transaction is None:  # web3.py 6.x compatibility
            raw_transaction = signed.rawTransaction
        tx_hash = w3.eth.send_raw_transaction(raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    except Exception as exc:
        message = str(exc)
        if "nonce" in message.lower():
            message += " Try again after refreshing the pending nonce."
        elif "timeout" in message.lower() or "timed out" in message.lower():
            message += " The RPC timed out; check PolygonScan before retrying."
        raise RuntimeError(f"Blockchain upload failed: {message}") from exc

    tx_hex = tx_hash.hex()
    return UploadResult(
        tx_hash=tx_hex,
        block_number=receipt["blockNumber"],
        record_hash=hash_record(record),
        explorer_url=f"{config.explorer_url or AMOY_EXPLORER_URL}/tx/{tx_hex}",
    )
