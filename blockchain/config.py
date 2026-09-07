"""Configuration and Web3 connection helpers for Polygon Amoy."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import Web3Exception

load_dotenv()

DEFAULT_AMOY_RPC_URL = "https://polygon-amoy.drpc.org"
AMOY_EXPLORER_URL = "https://amoy.polygonscan.com"


class BlockchainConfigError(RuntimeError):
    """Raised when the wallet or RPC configuration is not usable."""


@dataclass(frozen=True)
class BlockchainConfig:
    rpc_url: str
    wallet_address: str
    private_key: str
    explorer_url: str = AMOY_EXPLORER_URL

    @classmethod
    def from_env(cls) -> "BlockchainConfig":
        private_key = os.getenv("WALLET_PRIVATE_KEY", "").strip()
        wallet_address = os.getenv("WALLET_ADDRESS", "").strip()
        rpc_url = os.getenv("AMOY_RPC_URL", DEFAULT_AMOY_RPC_URL).strip()

        missing = []
        if not private_key:
            missing.append("WALLET_PRIVATE_KEY")
        if not wallet_address:
            missing.append("WALLET_ADDRESS")
        if missing:
            raise BlockchainConfigError(
                "Missing blockchain settings: " + ", ".join(missing) + ". "
                "Add them to .env before uploading to Polygon Amoy."
            )

        if not Web3.is_address(wallet_address):
            raise BlockchainConfigError("WALLET_ADDRESS is not a valid EVM address.")

        return cls(
            rpc_url=rpc_url,
            wallet_address=Web3.to_checksum_address(wallet_address),
            private_key=private_key,
        )

    def connect(self) -> Web3:
        """Connect to the configured RPC and fail with an actionable message."""
        try:
            w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 30}))
            if not w3.is_connected():
                raise BlockchainConfigError(f"Could not connect to RPC: {self.rpc_url}")
            return w3
        except BlockchainConfigError:
            raise
        except (OSError, Web3Exception) as exc:
            raise BlockchainConfigError(f"RPC connection failed: {exc}") from exc
