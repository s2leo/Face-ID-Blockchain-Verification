# Face-ID-Blockchain-Verification

This project detects and encodes a face, searches for matching public web/social
results, verifies candidate faces biometrically, and records the top verified
match in a local tamper-evident blockchain ledger by default.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add the search API keys to `.env`. The default local ledger does not need a
wallet or RPC. Polygon Amoy remains available as an optional backend:

```text
AMOY_RPC_URL=https://polygon-amoy.drpc.org
WALLET_ADDRESS=0x...
WALLET_PRIVATE_KEY=...
```

The local ledger writes to `chain.json`. Polygon mode requires a funded
throwaway wallet and writes the canonical match hash in a zero-value
self-transfer, verifiable independently on PolygonScan.

## Run

```powershell
python run_pipeline.py --image samples\Anuj.jpg --provider serpapi
```

The run saves an audit file under `results/` and writes a block to `chain.json`.
To verify the recorded match later:

```powershell
python run_pipeline.py --verify-only --record-json results\pipeline_run_<timestamp>.json
python run_pipeline.py --show-chain
```

Use `--blockchain-mode polygon` to opt into Polygon Amoy, or `--no-blockchain`
for face/search testing without any ledger write.

## Known Limitations

- The default blockchain step is a local ledger, not a decentralized public
  chain. Polygon Amoy is available with `--blockchain-mode polygon`.
- Polygon mode requires test POL and a reachable RPC.
- Reverse-image providers may return no public match or may rate-limit requests.
- A transaction stores the canonical hash, not the private face image or full
  biometric vector.
